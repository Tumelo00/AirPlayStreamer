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
RING_BUFFER_BYTES = 88200           # ~500ms at 44100Hz stereo 16-bit (jitter headroom)

# Reconnect / recovery
RECONNECT_BACKOFF_START = 1.0       # seconds
RECONNECT_BACKOFF_MAX = 30.0        # seconds
RECONNECT_MAX_ATTEMPTS = 10

from core.airplay_backend import RaopSession
from core.audio_capture import AudioCapture, AudioDevice
from core.audio_source import LiveAudioSource
from core.device_manager import AirPlayDevice, DeviceManager, DeviceState
from core.network import find_lan_route, friendly_error
from core.resampler import resampler_backend
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
    reconnect_attempts: int = 0

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
        self._reconnect_attempts: Dict[str, int] = {}
        self._stop_requested = False
        self._latency_samples = MIN_AIRPLAY_LATENCY_SAMPLES

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

    def set_latency_samples(self, samples: int) -> None:
        """Set the AirPlay latency buffer size in samples (thread-safe)."""
        self._latency_samples = max(2205, int(samples))

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

    def request_add_device(self, device_id: str) -> None:
        """Add a device to the live stream (no-op if not streaming)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._do_add_device(device_id), self._loop)

    def request_remove_device(self, device_id: str) -> None:
        """Stop streaming to one device, keep the rest running."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._do_remove_device(device_id), self._loop)

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
                reconnect_attempts=max(self._reconnect_attempts.values(),
                                       default=0),
            )

    def get_loopback_devices(self) -> List[AudioDevice]:
        """Get available loopback audio devices (thread-safe)."""
        return self._capture.get_loopback_devices()

    def get_diagnostics(self) -> dict:
        """Return a diagnostics snapshot for the diagnostics panel."""
        dev = self._capture.current_device
        connected = self._device_manager.get_connected_devices()
        homepod_ip = connected[0].address if connected else "-"

        local_ip, iface = (None, None)
        if homepod_ip and homepod_ip != "-":
            try:
                local_ip, iface = find_lan_route(homepod_ip)
            except Exception:
                pass

        with self._state_lock:
            state = self._state.value
            error = self._error_message or "-"
            reconnects = max(self._reconnect_attempts.values(), default=0)

        return {
            "state": state,
            "capture_device": dev.name if dev else "-",
            "capture_rate": dev.sample_rate if dev else 0,
            "homepod_ip": homepod_ip,
            "local_ip": local_ip or "-",
            "interface": iface or "-",
            "latency_samples": self._latency_samples,
            "reconnect_attempts": reconnects,
            "resampler": resampler_backend(),
            "error": error,
        }

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

            # Start audio capture and let the buffer build a jitter cushion
            # before readers attach (prevents initial underruns/crackle)
            self._ring_buffer.clear()
            self._capture.start(audio_device)
            await asyncio.sleep(0.25)

            # Start a supervised stream task per device (handles reconnect)
            self._stop_requested = False
            for device in connected:
                task = asyncio.ensure_future(
                    self._supervise_device(device)
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

    async def _supervise_device(self, device: AirPlayDevice):
        """Supervise streaming to one device: auto-reconnect with backoff.

        Retries on unexpected stream drops. Stops cleanly when the user
        presses Stop (CancelledError or _stop_requested).
        """
        backoff = RECONNECT_BACKOFF_START
        self._reconnect_attempts[device.identifier] = 0

        while not self._stop_requested:
            try:
                await self._stream_to_device(device)
                # Clean return = user stopped (source returned NO_FRAMES)
                return
            except asyncio.CancelledError:
                return
            except Exception as e:
                friendly = friendly_error(e)
                device.error_message = friendly
                _LOGGER.warning("Stream to %s dropped: %s", device.name, e)

            if self._stop_requested:
                return

            # Reconnect with exponential backoff
            attempts = self._reconnect_attempts.get(device.identifier, 0) + 1
            self._reconnect_attempts[device.identifier] = attempts
            if attempts > RECONNECT_MAX_ATTEMPTS:
                _LOGGER.error("Giving up on %s after %d attempts",
                              device.name, attempts)
                device.state = DeviceState.ERROR
                return

            device.state = DeviceState.CONNECTING
            _LOGGER.info("Reconnecting to %s in %.1fs (attempt %d)",
                         device.name, backoff, attempts)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return
            backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

            if self._stop_requested:
                return

            try:
                await self._device_manager.connect(device.identifier)
                if device.connection:
                    backoff = RECONNECT_BACKOFF_START  # reset on success
            except Exception as e:
                _LOGGER.warning("Reconnect to %s failed: %s", device.name, e)

    async def _stream_to_device(self, device: AirPlayDevice):
        """One streaming attempt. Returns on clean stop, raises on failure."""
        atv = device.connection
        if not atv:
            raise RuntimeError(f"{device.name} baglantisi yok")

        device.state = DeviceState.STREAMING
        source = None
        session = RaopSession(atv, device.name)

        try:
            await session.open(latency_samples=self._latency_samples)

            source = LiveAudioSource(
                self._ring_buffer,
                sample_rate=session.sample_rate,
                channels=session.channels,
                sample_size=session.sample_size,
                reader_id=device.identifier,
            )
            self._active_sources[device.identifier] = source

            _LOGGER.info("Starting stream to %s (%dHz, %dch)",
                         device.name, session.sample_rate, session.channels)

            # Blocks until source returns NO_FRAMES (when we stop)
            await session.stream(source)
            # Reset reconnect counter on a healthy session end
            self._reconnect_attempts[device.identifier] = 0

        finally:
            await session.close()
            if source:
                source.stop()
                self._active_sources.pop(device.identifier, None)
            if not self._stop_requested and device.connection:
                device.state = DeviceState.CONNECTED

    async def _do_add_device(self, device_id: str):
        """Connect and start a supervised stream to one more device."""
        with self._state_lock:
            streaming = self._state == StreamerState.STREAMING
        if not streaming or device_id in self._stream_tasks:
            return

        device = self._device_manager.get_device(device_id)
        if not device:
            return
        try:
            if device.state != DeviceState.CONNECTED:
                await self._device_manager.connect(device_id)
            if not device.connection:
                return
            task = asyncio.ensure_future(self._supervise_device(device))
            task.add_done_callback(self._on_stream_task_done)
            self._stream_tasks[device_id] = task
            _LOGGER.info("Added device to live stream: %s", device.name)
        except Exception as e:
            _LOGGER.error("Failed to add device %s: %s", device_id, e)

    async def _do_remove_device(self, device_id: str):
        """Stop streaming to one device without touching the others."""
        source = self._active_sources.pop(device_id, None)
        if source:
            source.stop()
        task = self._stream_tasks.pop(device_id, None)
        if task:
            task.cancel()
        _LOGGER.info("Removed device from live stream: %s", device_id)

    async def _do_stop_streaming(self):
        with self._state_lock:
            self._state = StreamerState.STOPPING

        await self._stop_all_streams()
        self._capture.stop()

        with self._state_lock:
            self._state = StreamerState.IDLE
            self._packets_sent = 0

    async def _stop_all_streams(self):
        # Stop reconnect supervision first
        self._stop_requested = True

        # Signal all sources to stop
        for source in list(self._active_sources.values()):
            source.stop()

        # Cancel all supervisor tasks
        for task in list(self._stream_tasks.values()):
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
