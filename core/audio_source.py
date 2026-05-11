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

    def __init__(self, ring_buffer: RingBuffer, sample_rate: int = 44100,
                 channels: int = 2, sample_size: int = 2,
                 reader_id: str = None):
        self._buffer = ring_buffer
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_size = sample_size
        self._stopped = False
        self._reader_id = reader_id or str(uuid.uuid4())[:8]
        self._buffer.register_reader(self._reader_id)
        self._is_little_endian = (sys.byteorder == "little")

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
