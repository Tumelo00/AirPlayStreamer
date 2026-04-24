"""AirPlay device discovery, pairing, and connection management using pyatv."""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV, BaseConfig
from pyatv.storage.file_storage import FileStorage

_LOGGER = logging.getLogger(__name__)

SCAN_TIMEOUT = 5
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


class DeviceManager:
    """Manages AirPlay device discovery, pairing, and connections."""

    def __init__(self):
        self._devices: Dict[str, AirPlayDevice] = {}
        self._storage: Optional[FileStorage] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ensure_credentials_dir()

    def _ensure_credentials_dir(self):
        os.makedirs(CREDENTIALS_DIR, exist_ok=True)

    async def _get_storage(self) -> FileStorage:
        if self._storage is None:
            cred_file = os.path.join(CREDENTIALS_DIR, "credentials.json")
            self._storage = FileStorage(cred_file, asyncio.get_event_loop())
            await self._storage.load()
        return self._storage

    async def scan(self, timeout: int = SCAN_TIMEOUT) -> List[AirPlayDevice]:
        """Scan for AirPlay devices on the network."""
        _LOGGER.info("Scanning for AirPlay devices (timeout=%ds)...", timeout)

        storage = await self._get_storage()
        configs = await pyatv.scan(
            asyncio.get_event_loop(),
            timeout=timeout,
            storage=storage,
        )

        for config in configs:
            # Only consider devices that support AirPlay
            if not config.get_service(Protocol.AirPlay):
                continue

            identifier = config.identifier
            if identifier in self._devices:
                # Update existing device info
                dev = self._devices[identifier]
                dev.name = config.name
                dev.address = str(config.address)
                dev.config = config
                if dev.state == DeviceState.DISCONNECTED:
                    dev.state = DeviceState.DISCOVERED
            else:
                self._devices[identifier] = AirPlayDevice(
                    identifier=identifier,
                    name=config.name,
                    address=str(config.address),
                    config=config,
                )

            # Check if we have stored credentials (= already paired)
            if config.get_service(Protocol.AirPlay) and \
               config.get_service(Protocol.AirPlay).credentials:
                if self._devices[identifier].state == DeviceState.DISCOVERED:
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
                loop=asyncio.get_event_loop(),
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
                loop=asyncio.get_event_loop(),
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
        for device_id in list(self._devices.keys()):
            await self.disconnect(device_id)

    def get_device(self, device_id: str) -> Optional[AirPlayDevice]:
        return self._devices.get(device_id)

    def get_devices(self) -> List[AirPlayDevice]:
        return list(self._devices.values())

    def get_connected_devices(self) -> List[AirPlayDevice]:
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
