"""Network interface helper - ensures AirPlay traffic uses the correct LAN interface.

Problem: When a VPN (Tailscale, WireGuard, etc.) is active, the OS may route
traffic to a LAN AirPlay device through the VPN interface. pyatv then reports
the VPN IP (e.g. 100.x.x.x CGNAT) as the local address in RTSP SETUP, and the
HomePod - which can only reach LAN addresses - rejects the session with
"400 Bad Request".

Fix: Find the physical interface whose subnet directly contains the target
device, and force pyatv's TCP connections to bind their source address to
that interface. Binding the source explicitly bypasses VPN subnet routing.
"""

import asyncio
import ipaddress
import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Set once patch_pyatv_connection() runs, to avoid double-patching
_patched = False


def find_lan_ip(target_ip: str) -> Optional[str]:
    """Return the local interface IP whose subnet directly contains target_ip.

    This is the interface physically on the same LAN as the AirPlay device.
    Returns None if no matching interface is found.
    """
    try:
        target = ipaddress.ip_address(target_ip)
    except ValueError:
        return None

    if target.version != 4:
        return None

    try:
        import ifaddr
    except ImportError:
        _LOGGER.warning("ifaddr not available, cannot detect LAN interface")
        return None

    best_ip: Optional[str] = None
    best_prefix = -1

    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            # IPv4 addresses are plain strings; IPv6 are tuples
            if not isinstance(ip.ip, str):
                continue
            try:
                network = ipaddress.ip_network(
                    f"{ip.ip}/{ip.network_prefix}", strict=False
                )
            except (ValueError, TypeError):
                continue

            if target in network:
                # Prefer the most specific (longest prefix) match
                if ip.network_prefix > best_prefix:
                    best_prefix = ip.network_prefix
                    best_ip = ip.ip

    if best_ip:
        _LOGGER.info("LAN interface for %s: %s/%d", target_ip, best_ip, best_prefix)
    else:
        _LOGGER.warning("No direct LAN interface found for %s", target_ip)
    return best_ip


# pyatv modules that do `from pyatv.support.http import http_connect`
# (direct name import - each needs its reference patched individually)
_PYATV_MODULES_WITH_HTTP_CONNECT = [
    "pyatv.support.http",
    "pyatv.protocols.raop",
    "pyatv.protocols.airplay",
    "pyatv.protocols.airplay.ap2_session",
    "pyatv.protocols.airplay.pairing",
]


def patch_pyatv_connection() -> None:
    """Monkey-patch pyatv's http_connect to bind the source to the LAN interface.

    Must be called once at startup, before any pyatv connection is made.
    Safe to call multiple times (no-op after first).
    """
    global _patched
    if _patched:
        return

    try:
        from pyatv.support import http
    except ImportError:
        _LOGGER.error("Cannot patch pyatv: support.http not importable")
        return

    original_http_connect = http.http_connect

    async def patched_http_connect(address: str, port: int):
        """http_connect that binds the source socket to the matching LAN interface."""
        loop = asyncio.get_event_loop()
        local_ip = find_lan_ip(address)

        if local_ip:
            try:
                _, connection = await loop.create_connection(
                    http.HttpConnection, address, port,
                    local_addr=(local_ip, 0),
                )
                return connection
            except Exception as e:
                # Binding failed (interface gone, etc.) - fall back to default
                _LOGGER.warning("Bound connect to %s failed (%s), using default",
                                local_ip, e)

        # Fallback: original behavior (OS picks source)
        return await original_http_connect(address, port)

    # Patch every module that imported http_connect by name
    import importlib
    patched_count = 0
    for module_name in _PYATV_MODULES_WITH_HTTP_CONNECT:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "http_connect"):
                module.http_connect = patched_http_connect
                patched_count += 1
        except ImportError:
            continue

    _patched = True
    _LOGGER.info("pyatv http_connect patched in %d modules for LAN binding",
                 patched_count)
