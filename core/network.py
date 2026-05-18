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


# VPN interface name hints - de-prioritized when picking a LAN route
_VPN_HINTS = ("tailscale", "zerotier", "wireguard", "wg", "tun", "tap",
              "openvpn", "vpn", "utun")


def find_lan_route(target_ip: str):
    """Return (local_ip, interface_name) for the interface whose subnet
    directly contains target_ip. Returns (None, None) if not found.

    Never raises - all failures degrade to (None, None).
    """
    try:
        target = ipaddress.ip_address(target_ip)
        if target.version != 4:
            return None, None
    except (ValueError, TypeError):
        return None, None

    try:
        import ifaddr
    except Exception:
        _LOGGER.warning("ifaddr unavailable, cannot detect LAN interface")
        return None, None

    best_ip = None
    best_name = None
    best_prefix = -1
    best_is_vpn = True  # prefer non-VPN

    try:
        adapters = ifaddr.get_adapters()
    except Exception as e:
        _LOGGER.warning("ifaddr.get_adapters() failed: %s", e)
        return None, None

    for adapter in adapters:
        name = getattr(adapter, "nice_name", "") or getattr(adapter, "name", "")
        is_vpn = any(h in str(name).lower() for h in _VPN_HINTS)
        for ip in getattr(adapter, "ips", []):
            if not isinstance(ip.ip, str):  # skip IPv6 (tuple)
                continue
            try:
                network = ipaddress.ip_network(
                    f"{ip.ip}/{ip.network_prefix}", strict=False)
            except (ValueError, TypeError):
                continue
            if target not in network:
                continue
            # Prefer: non-VPN, then longest prefix
            better = (
                (best_is_vpn and not is_vpn)
                or (best_is_vpn == is_vpn and ip.network_prefix > best_prefix)
            )
            if better:
                best_ip = ip.ip
                best_name = str(name)
                best_prefix = ip.network_prefix
                best_is_vpn = is_vpn

    if best_ip:
        _LOGGER.info("Route: target=%s -> local=%s iface=%r (/%d)",
                     target_ip, best_ip, best_name, best_prefix)
    else:
        _LOGGER.warning("No LAN interface for %s, using OS default route",
                        target_ip)
    return best_ip, best_name


def find_lan_ip(target_ip: str) -> Optional[str]:
    """Return only the local IP for target_ip (compat helper)."""
    return find_lan_route(target_ip)[0]


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
    Safe to call multiple times (no-op after first). Never raises - if
    patching fails for any reason, pyatv keeps its default behavior.
    """
    try:
        _do_patch()
    except Exception as e:
        _LOGGER.error("patch_pyatv_connection failed (non-fatal): %s", e)


def friendly_error(error: Exception) -> str:
    """Map a streaming exception to a user-friendly Turkish message."""
    msg = str(error)
    if "400" in msg and ("SETUP" in msg or "Bad Request" in msg):
        return ("HomePod baglantiyi reddetti. VPN (Tailscale vb.) acaksa "
                "kapatip tekrar deneyin veya HomePod'u yeniden baslatin.")
    if "not connected" in msg.lower() or "connection" in msg.lower():
        return "Cihaz baglantisi koptu. Yeniden baglaniliyor..."
    return msg


def _do_patch() -> None:
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
        local_ip = None
        try:
            local_ip, _ = find_lan_route(address)
        except Exception as e:
            _LOGGER.warning("LAN route lookup failed for %s: %s", address, e)

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

        # Fallback: original pyatv behavior (OS picks source)
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
        except Exception:
            continue

    _patched = True
    _LOGGER.info("pyatv http_connect patched in %d modules for LAN binding",
                 patched_count)
