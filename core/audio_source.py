"""Custom AudioSource that feeds live WASAPI audio into pyatv's RAOP pipeline."""

import array
import sys
import uuid

from pyatv.interface import MediaMetadata
from pyatv.protocols.raop.audio_source import AudioSource

from core.ring_buffer import RingBuffer


class LiveAudioSource(AudioSource):
    """Audio source that reads live PCM data from a RingBuffer.

    Each instance gets a unique reader_id so multiple devices can read
    the same audio data independently from the shared ring buffer.
    """

    # Jitter buffer: start reading this far behind the write head so brief
    # capture/network hiccups don't cause underruns (crackling).
    CUSHION_MS = 120

    def __init__(self, ring_buffer: RingBuffer, sample_rate: int = 44100,
                 channels: int = 2, sample_size: int = 2,
                 reader_id: str = None, delay_ms: int = 0):
        self._buffer = ring_buffer
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_size = sample_size
        self._stopped = False
        self._reader_id = reader_id or str(uuid.uuid4())[:8]
        self._delay_ms = max(0, delay_ms)
        self._buffer.register_reader(self._reader_id,
                                     cushion_bytes=self._total_cushion_bytes())
        self._is_little_endian = (sys.byteorder == "little")

    def _bytes_per_ms(self) -> float:
        return self._sample_rate * self._channels * self._sample_size / 1000.0

    def _total_cushion_bytes(self) -> int:
        """Base jitter cushion + per-device calibration delay."""
        return int(self._bytes_per_ms() * (self.CUSHION_MS + self._delay_ms))

    def set_delay_ms(self, delay_ms: int) -> None:
        """Live per-device delay calibration. Repositions this reader."""
        self._delay_ms = max(0, int(delay_ms))
        self._buffer.set_reader_cushion(self._reader_id,
                                        self._total_cushion_bytes())

    async def readframes(self, nframes: int) -> bytes:
        if self._stopped:
            return AudioSource.NO_FRAMES

        total_bytes = nframes * self._channels * self._sample_size
        data = self._buffer.read(total_bytes, reader_id=self._reader_id)

        if not self._is_little_endian:
            return data

        # Byteswap for AirPlay (in-place via array module)
        output = array.array("h", data)
        output.byteswap()
        return output.tobytes()

    async def get_metadata(self) -> MediaMetadata:
        return MediaMetadata(title="Sistem Sesi", artist="AirPlay Streamer")

    async def close(self) -> None:
        self._unregister_once()

    def stop(self) -> None:
        self._unregister_once()

    def _unregister_once(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            self._buffer.unregister_reader(self._reader_id)
        except Exception:
            pass

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def sample_size(self) -> int:
        return self._sample_size

    @property
    def duration(self) -> int:
        return 0
