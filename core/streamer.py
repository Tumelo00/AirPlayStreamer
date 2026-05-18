"""Orchestrator: bridges audio capture with AirPlay streaming via pyatv."""

import asyncio
import logging
import threading
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

# AirPlay tuning constants
MIN_AIRPLAY_LATENCY_SAMPLES = 4410  # ~0.1s at 44100Hz (default is 22050+sr ~1.5s)
RING_BUFFER_BYTES = 17640           # ~100ms at 44100Hz stereo 16-bit (jitter tolerance)

from pyatv.const import Protocol
from pyatv.interface import AppleTV, Audio, MediaMetadata, Metadata, PushUpdater, RemoteControl
from pyatv.protocols.airplay.auth import extract_credentials
from pyatv.protocols.raop import RaopStream

from core.audio_capture import AudioCapture, AudioDevice
from core.audio_source import LiveAudioSource
from core.device_manager import AirPlayDevice, DeviceManager, DeviceState
from core.network import friendly_error
from core.ring_buffer import RingBuffer

_LOGGER = logging.getLogger(__name__)


class StreamerState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class StreamerStatus:
    """Thread-safe snapshot of streamer state for UI polling."""
    state: StreamerState = StreamerState.IDLE
    devices: List[AirPlayDevice] = None
    audio_level: float = 0.0
    packets_sent: int = 0
    error_message: str = ""
    is_capturing: bool = False

    def __post_init__(self):
        if self.devices is None:
            self.devices = []


class Streamer:
    """Main orchestrator running asyncio in a background thread.

    Provides thread-safe methods for the UI to control streaming.
    """

    def __init__(self):
        self._ring_buffer = RingBuffer(capacity_bytes=RING_BUFFER_BYTES)
        self._capture = AudioCapture(self._ring_buffer)
        self._device_manager = DeviceManager()

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        self._state = StreamerState.IDLE
        self._error_message = ""
        self._packets_sent = 0
        self._stream_tasks: Dict[str, asyncio.Task] = {}
        self._active_sources: Dict[str, LiveAudioSource] = {}

        self._state_lock = threading.Lock()

    def start(self) -> None:
        """Start the asyncio event loop in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def shutdown(self) -> None:
        """Stop everything and shut down the background thread."""
        # Stop capture first to prevent new data
        try:
            self._capture.stop()
        except Exception:
            pass

        if self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)
                future.result(timeout=5)
            except Exception:
                pass
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    async def _shutdown_async(self):
        await self._stop_all_streams()
        await self._device_manager.disconnect_all()

    # ── Thread-safe commands (called from UI thread) ──

    def request_scan(self) -> None:
        """Request device scan."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._do_scan(), self._loop)

    def request_pair(self, device_id: str) -> None:
        """Request device pairing (phase 1: show PIN dialog)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._device_manager.pair(device_id), self._loop
            )

    def request_complete_pairing(self, device_id: str, pin: str) -> None:
        """Complete device pairing with PIN."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._do_complete_pairing(device_id, pin), self._loop
            )

    def request_start_streaming(self, device_ids: List[str],
                                audio_device: Optional[AudioDevice] = None) -> None:
        """Start streaming to selected devices."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._do_start_streaming(device_ids, audio_device), self._loop
            )

    def request_stop_streaming(self) -> None:
        """Stop all streaming."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._do_stop_streaming(), self._loop)

    def request_set_volume(self, device_id: str, volume: float) -> None:
        """Set volume for a device (0-100)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._do_set_volume(device_id, volume), self._loop
            )

    def get_status(self) -> StreamerStatus:
        """Get current status snapshot (thread-safe, called from UI)."""
        with self._state_lock:
            return StreamerStatus(
                state=self._state,
                devices=self._device_manager.get_devices(),
                audio_level=self._ring_buffer.peak_level,
                packets_sent=self._packets_sent,
                error_message=self._error_message,
                is_capturing=self._capture.is_running,
            )

    def get_loopback_devices(self) -> List[AudioDevice]:
        """Get available loopback audio devices (thread-safe)."""
        return self._capture.get_loopback_devices()

    # ── Internal async operations ──

    async def _do_scan(self):
        with self._state_lock:
            self._state = StreamerState.SCANNING
        try:
            await self._device_manager.scan()
        except Exception as e:
            _LOGGER.error("Scan failed: %s", e)
            with self._state_lock:
                self._error_message = f"Tarama hatasi: {e}"
        finally:
            with self._state_lock:
                if self._state == StreamerState.SCANNING:
                    self._state = StreamerState.IDLE

    async def _do_complete_pairing(self, device_id: str, pin: str):
        try:
            success = await self._device_manager.complete_pairing(device_id, pin)
            if not success:
                with self._state_lock:
                    self._error_message = "Eslestirme basarisiz"
        except Exception as e:
            _LOGGER.error("Pairing error: %s", e)
            with self._state_lock:
                self._error_message = f"Eslestirme hatasi: {e}"

    async def _do_start_streaming(self, device_ids: List[str],
                                  audio_device: Optional[AudioDevice] = None):
        with self._state_lock:
            self._state = StreamerState.CONNECTING
            self._error_message = ""

        try:
            # Connect to all selected devices in parallel
            connect_tasks = []
            for device_id in device_ids:
                device = self._device_manager.get_device(device_id)
                if device and device.state != DeviceState.CONNECTED:
                    connect_tasks.append(self._device_manager.connect(device_id))
            if connect_tasks:
                await asyncio.gather(*connect_tasks, return_exceptions=True)

            connected = self._device_manager.get_connected_devices()
            if not connected:
                raise RuntimeError("Hicbir cihaza baglanamadi")

            # Start audio capture
            self._ring_buffer.clear()
            self._capture.start(audio_device)

            # Start streaming to each connected device
            for device in connected:
                task = asyncio.ensure_future(
                    self._stream_to_device(device)
                )
                task.add_done_callback(self._on_stream_task_done)
                self._stream_tasks[device.identifier] = task

            with self._state_lock:
                self._state = StreamerState.STREAMING

        except Exception as e:
            _LOGGER.error("Failed to start streaming: %s", e)
            self._capture.stop()
            with self._state_lock:
                self._state = StreamerState.ERROR
                self._error_message = str(e)

    async def _stream_to_device(self, device: AirPlayDevice):
        """Stream audio to a single device using pyatv's internal RAOP pipeline."""
        atv = device.connection
        if not atv:
            return

        device.state = DeviceState.STREAMING
        source = None

        try:
            # Get the actual RaopStream from FacadeStream instances
            raop_stream = None
            for inst in atv.stream.instances:
                if isinstance(inst, RaopStream):
                    raop_stream = inst
                    break

            if raop_stream is None:
                raise RuntimeError(f"RaopStream bulunamadi: {device.name}")

            # Access internal playback manager to set up RAOP session
            raop_stream.playback_manager.acquire()
            takeover_release = raop_stream.core.takeover(
                Audio, Metadata, PushUpdater, RemoteControl
            )
            try:
                client, context = await raop_stream.playback_manager.setup(
                    raop_stream.core.service
                )
                context.credentials = extract_credentials(raop_stream.core.service)
                context.password = raop_stream.core.service.password

                client.listener = raop_stream.listener
                await client.initialize(raop_stream.core.service.properties)

                # Reduce AirPlay latency buffer for near-real-time streaming
                # (default ~1.5s, we use ~0.1s)
                context.latency = MIN_AIRPLAY_LATENCY_SAMPLES

                # Create our live audio source (unique reader per device)
                source = LiveAudioSource(
                    self._ring_buffer,
                    sample_rate=context.sample_rate,
                    channels=context.channels,
                    sample_size=context.bytes_per_channel,
                    reader_id=device.identifier,
                )
                self._active_sources[device.identifier] = source

                metadata = MediaMetadata(
                    title="Sistem Sesi",
                    artist="AirPlay Streamer",
                )

                _LOGGER.info("Starting stream to %s (%dHz, %dch)",
                             device.name, context.sample_rate, context.channels)

                # This blocks until source returns NO_FRAMES (when we stop)
                await client.send_audio(source, metadata)

            finally:
                takeover_release()
                await raop_stream.playback_manager.teardown()

        except asyncio.CancelledError:
            _LOGGER.info("Stream to %s cancelled", device.name)
        except Exception as e:
            _LOGGER.error("Stream error for %s: %s\n%s", device.name, e,
                          traceback.format_exc())
            friendly = friendly_error(e)
            device.error_message = friendly
            with self._state_lock:
                if not self._error_message:
                    self._error_message = f"{device.name}: {friendly}"
        finally:
            if source:
                source.stop()
                self._active_sources.pop(device.identifier, None)
            device.state = DeviceState.CONNECTED if device.connection else DeviceState.DISCONNECTED

    async def _do_stop_streaming(self):
        with self._state_lock:
            self._state = StreamerState.STOPPING

        await self._stop_all_streams()
        self._capture.stop()

        with self._state_lock:
            self._state = StreamerState.IDLE
            self._packets_sent = 0

    async def _stop_all_streams(self):
        # Signal all sources to stop
        for source in self._active_sources.values():
            source.stop()

        # Cancel all stream tasks
        for task in self._stream_tasks.values():
            task.cancel()

        # Wait for tasks to finish
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks.values(), return_exceptions=True)

        self._stream_tasks.clear()
        self._active_sources.clear()

    async def _do_set_volume(self, device_id: str, volume: float):
        # Clamp to valid range (0-100)
        volume = max(0.0, min(100.0, float(volume)))
        device = self._device_manager.get_device(device_id)
        if device and device.connection:
            try:
                await device.connection.audio.set_volume(volume)
            except Exception as e:
                _LOGGER.error("Volume change failed for %s: %s", device.name, e)

    def _on_stream_task_done(self, task: asyncio.Task) -> None:
        """Surface unexpected task failures to UI state."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc and not isinstance(exc, asyncio.CancelledError):
            _LOGGER.error("Stream task failed: %s", exc)
            with self._state_lock:
                if not self._error_message:
                    self._error_message = f"Yayin hatasi: {exc}"
