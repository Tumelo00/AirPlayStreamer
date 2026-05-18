"""AirPlay backend - isolates all pyatv internal RAOP API usage.

pyatv has no public real-time streaming API, so we drive its internal RAOP
pipeline (FacadeStream -> RaopStream -> playback_manager -> StreamClient).
Keeping every internal call in this one module means a future pyatv update
breaks (at most) this file instead of the whole app.
"""

import logging
from typing import Optional

from pyatv.interface import (
    AppleTV, Audio, MediaMetadata, Metadata, PushUpdater, RemoteControl,
)
from pyatv.protocols.airplay.auth import extract_credentials
from pyatv.protocols.raop import RaopStream

_LOGGER = logging.getLogger(__name__)


class AirPlayError(Exception):
    """Raised for AirPlay backend failures."""


class RaopSession:
    """A single RAOP streaming session to one AirPlay device.

    Lifecycle: open() -> stream() -> close(). close() is idempotent and
    safe to call from a finally block even if open() failed midway.
    """

    def __init__(self, atv: AppleTV, device_name: str = ""):
        self._atv = atv
        self._device_name = device_name or "device"
        self._raop_stream = None
        self._client = None
        self._context = None
        self._takeover_release = None
        self._acquired = False
        self._requested_latency = None

    @staticmethod
    def find_raop_stream(atv: AppleTV):
        """Locate the internal RaopStream inside a connected device."""
        stream = getattr(atv, "stream", None)
        instances = getattr(stream, "instances", None)
        if not instances:
            return None
        for inst in instances:
            if isinstance(inst, RaopStream):
                return inst
        return None

    async def open(self, latency_samples: Optional[int] = None) -> None:
        """Set up the RAOP session. Raises AirPlayError on failure."""
        raop = self.find_raop_stream(self._atv)
        if raop is None:
            raise AirPlayError(f"RaopStream bulunamadi: {self._device_name}")
        self._raop_stream = raop

        try:
            raop.playback_manager.acquire()
            self._acquired = True
            self._takeover_release = raop.core.takeover(
                Audio, Metadata, PushUpdater, RemoteControl
            )

            client, context = await raop.playback_manager.setup(raop.core.service)
            self._client = client
            self._context = context

            context.credentials = extract_credentials(raop.core.service)
            context.password = raop.core.service.password
            client.listener = raop.listener
            await client.initialize(raop.core.service.properties)

            if latency_samples is not None:
                self._apply_latency(context, latency_samples)
        except Exception as e:
            await self.close()
            raise AirPlayError(f"RAOP setup hatasi: {e}") from e

    def _apply_latency(self, context, latency_samples: int) -> None:
        """Set context.latency and keep it after StreamContext.reset().

        pyatv's send_audio() calls context.reset() which restores the
        default latency. We shadow reset() on the instance so our value
        survives.
        """
        self._requested_latency = latency_samples
        context.latency = latency_samples
        original_reset = context.reset

        def reset_keeping_latency():
            before = context.latency
            original_reset()
            after_reset = context.latency
            context.latency = latency_samples
            _LOGGER.info("latency: reset patch [%s] before=%s after_reset=%s "
                         "-> kept=%d", self._device_name, before, after_reset,
                         latency_samples)

        context.reset = reset_keeping_latency
        _LOGGER.info("latency: requested=%d samples for %s",
                     latency_samples, self._device_name)

    @property
    def sample_rate(self) -> int:
        return self._context.sample_rate if self._context else 44100

    @property
    def channels(self) -> int:
        return self._context.channels if self._context else 2

    @property
    def sample_size(self) -> int:
        return self._context.bytes_per_channel if self._context else 2

    async def stream(self, source, title: str = "Sistem Sesi",
                     artist: str = "AirPlay Streamer") -> None:
        """Stream audio from `source` until it returns NO_FRAMES.

        Blocks for the whole streaming duration.
        """
        if self._client is None:
            raise AirPlayError("Session not opened")
        if self._context is not None:
            _LOGGER.info("latency: before send_audio [%s] context.latency=%s "
                         "(requested=%s)", self._device_name,
                         self._context.latency, self._requested_latency)
        metadata = MediaMetadata(title=title, artist=artist)
        await self._client.send_audio(source, metadata)

    async def set_volume(self, volume: float) -> None:
        """Set device volume (0-100). Best effort."""
        try:
            await self._atv.audio.set_volume(max(0.0, min(100.0, float(volume))))
        except Exception as e:
            _LOGGER.debug("set_volume failed for %s: %s", self._device_name, e)

    async def close(self) -> None:
        """Tear down the session. Idempotent, never raises."""
        if self._takeover_release is not None:
            try:
                self._takeover_release()
            except Exception:
                pass
            self._takeover_release = None

        if self._acquired and self._raop_stream is not None:
            try:
                await self._raop_stream.playback_manager.teardown()
            except Exception as e:
                _LOGGER.debug("teardown failed for %s: %s", self._device_name, e)
            self._acquired = False

        self._client = None
        self._context = None
