"""AirPlay device discovery, pairing, and connection management using pyatv."""

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV, BaseConfig
from pyatv.storage.file_storage import FileStorage

_LOGGER = logging.getLogger(__name__)

SCAN_TIMEOUT = 8
CREDENTIALS_DIR = os.path.join(os.environ.get("APPDATA", ""), "AirPlayStreamer")


class DeviceState(Enum):
    DISCOVERED = "discovered"
    PAIRING = "pairing"
    PAIRED = "paired"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class AirPlayDevice:
    """Represents a discovered AirPlay device."""
    identifier: str
    name: str
    address: str
    config: BaseConfig
    state: DeviceState = DeviceState.DISCOVERED
    connection: Optional[AppleTV] = field(default=None, repr=False)
    error_message: str = ""
    is_group: bool = False  # True = stereo pair / speaker group


class DeviceManager:
    """Manages AirPlay device discovery, pairing, and connections."""

    def __init__(self):
        self._devices: Dict[str, AirPlayDevice] = {}
        self._devices_lock = threading.Lock()
        self._storage: Optional[FileStorage] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ensure_credentials_dir()

    def _ensure_credentials_dir(self):
        os.makedirs(CREDENTIALS_DIR, exist_ok=True)

    async def _get_storage(self) -> FileStorage:
        if self._storage is None:
            cred_file = os.path.join(CREDENTIALS_DIR, "credentials.json")
            self._storage = FileStorage(cred_file, asyncio.get_running_loop())
            await self._storage.load()
        return self._storage

    @staticmethod
    def _select_grouped_configs(configs):
        """Collapse stereo-paired / grouped AirPlay devices.

        HomePods in a stereo pair advertise the same 'gid'. AirPlay
        streaming must go to the group leader (igl=1), which relays
        to followers in perfect sync.

        Returns (visible, followers):
          visible   - list of (config, display_name, is_group) to show
          followers - set of identifiers that are group followers and
                      must be hidden / purged from the device list
        """
        airplay = [c for c in configs if c.get_service(Protocol.AirPlay)]
        visible = []
        followers = set()

        # Count members per gid so a "group of one" is not flagged as a pair
        gid_counts = {}
        for c in airplay:
            props = c.get_service(Protocol.AirPlay).properties or {}
            gid = props.get("gid")
            if gid:
                gid_counts[gid] = gid_counts.get(gid, 0) + 1

        for c in airplay:
            props = c.get_service(Protocol.AirPlay).properties or {}
            gid = props.get("gid")
            igl = props.get("igl")
            gpn = props.get("gpn")
            in_pair = bool(gid) and gid_counts.get(gid, 0) > 1

            # A grouped follower: never shown, streaming goes via leader
            if in_pair and igl == "0":
                followers.add(c.identifier)
                continue

            # Grouped leader: show under the group name, flagged as group
            if in_pair and igl == "1":
                visible.append((c, gpn or c.name, True))
                _LOGGER.info("Group leader '%s' (gid=%s)",
                             gpn or c.name, gid[:16])
            else:
                # Standalone device (no group, or group of one)
                visible.append((c, c.name, False))

        return visible, followers

    async def scan(self, timeout: int = SCAN_TIMEOUT) -> List[AirPlayDevice]:
        """Scan for AirPlay devices on the network."""
        _LOGGER.info("Scanning for AirPlay devices (timeout=%ds)...", timeout)

        storage = await self._get_storage()
        configs = await pyatv.scan(
            asyncio.get_running_loop(),
            timeout=timeout,
            storage=storage,
        )

        with self._devices_lock:
            grouped, followers = self._select_grouped_configs(configs)

            # Purge any follower we may have shown in an earlier scan
            for fid in followers:
                self._devices.pop(fid, None)

            for config, display_name, is_group in grouped:
                identifier = config.identifier
                if identifier in self._devices:
                    dev = self._devices[identifier]
                    dev.name = display_name
                    dev.address = str(config.address)
                    dev.config = config
                    dev.is_group = is_group
                    if dev.state == DeviceState.DISCONNECTED:
                        dev.state = DeviceState.DISCOVERED
                else:
                    self._devices[identifier] = AirPlayDevice(
                        identifier=identifier,
                        name=display_name,
                        address=str(config.address),
                        config=config,
                        is_group=is_group,
                    )

                svc = config.get_service(Protocol.AirPlay)
                if svc and svc.credentials and \
                        self._devices[identifier].state == DeviceState.DISCOVERED:
                    self._devices[identifier].state = DeviceState.PAIRED

            _LOGGER.info("Found %d AirPlay devices", len(self._devices))
            return list(self._devices.values())

    async def pair(self, device_id: str) -> str:
        """Start pairing with a device. Returns a pairing handler to complete with PIN."""
        if device_id not in self._devices:
            raise ValueError(f"Unknown device: {device_id}")

        device = self._devices[device_id]
        device.state = DeviceState.PAIRING
        return device_id

    async def complete_pairing(self, device_id: str, pin: str) -> bool:
        """Complete pairing with a device using the PIN code."""
        if device_id not in self._devices:
            raise ValueError(f"Unknown device: {device_id}")

        device = self._devices[device_id]
        storage = await self._get_storage()

        try:
            pairing = await pyatv.pair(
                device.config,
                protocol=Protocol.AirPlay,
                loop=asyncio.get_running_loop(),
                storage=storage,
            )

            await pairing.begin()
            pairing.pin(int(pin))
            await pairing.finish()

            if pairing.has_paired:
                await storage.save()
                device.state = DeviceState.PAIRED
                _LOGGER.info("Successfully paired with %s", device.name)
                return True
            else:
                device.state = DeviceState.ERROR
                device.error_message = "Eslestirme basarisiz"
                return False

        except Exception as e:
            _LOGGER.error("Pairing failed for %s: %s", device.name, e)
            device.state = DeviceState.ERROR
            device.error_message = str(e)
            return False

    async def connect(self, device_id: str) -> Optional[AppleTV]:
        """Connect to a paired device."""
        if device_id not in self._devices:
            raise ValueError(f"Unknown device: {device_id}")

        device = self._devices[device_id]
        device.state = DeviceState.CONNECTING

        try:
            storage = await self._get_storage()
            atv = await pyatv.connect(
                device.config,
                loop=asyncio.get_running_loop(),
                storage=storage,
            )

            device.connection = atv
            device.state = DeviceState.CONNECTED
            _LOGGER.info("Connected to %s", device.name)

            # Set up disconnection listener
            atv.listener = DeviceListener(device, self)

            return atv

        except Exception as e:
            _LOGGER.error("Connection failed for %s: %s", device.name, e)
            device.state = DeviceState.ERROR
            device.error_message = str(e)
            return None

    async def disconnect(self, device_id: str) -> None:
        """Disconnect from a device."""
        if device_id not in self._devices:
            return

        device = self._devices[device_id]
        if device.connection:
            device.connection.close()
            device.connection = None
        device.state = DeviceState.DISCONNECTED
        _LOGGER.info("Disconnected from %s", device.name)

    async def disconnect_all(self) -> None:
        """Disconnect from all devices."""
        with self._devices_lock:
            ids = list(self._devices.keys())
        for device_id in ids:
            await self.disconnect(device_id)

    def get_device(self, device_id: str) -> Optional[AirPlayDevice]:
        with self._devices_lock:
            return self._devices.get(device_id)

    def get_devices(self) -> List[AirPlayDevice]:
        """Thread-safe snapshot of current devices."""
        with self._devices_lock:
            return list(self._devices.values())

    def get_connected_devices(self) -> List[AirPlayDevice]:
        with self._devices_lock:
            return [d for d in self._devices.values()
                    if d.state in (DeviceState.CONNECTED, DeviceState.STREAMING)]


class DeviceListener:
    """Listens for device state changes."""

    def __init__(self, device: AirPlayDevice, manager: DeviceManager):
        self._device = device
        self._manager = manager

    def connection_lost(self, exception: Optional[Exception]) -> None:
        _LOGGER.warning("Connection lost to %s: %s", self._device.name, exception)
        self._device.state = DeviceState.DISCONNECTED
        self._device.connection = None

    def connection_closed(self) -> None:
        _LOGGER.info("Connection closed to %s", self._device.name)
        self._device.state = DeviceState.DISCONNECTED
        self._device.connection = None
