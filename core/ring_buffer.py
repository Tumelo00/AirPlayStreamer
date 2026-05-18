"""Thread-safe broadcast ring buffer for live audio streaming.

One writer (audio capture callback), multiple readers (per-device streamers).
Each reader has an independent cursor. When buffer overruns, lagging readers
are advanced to the oldest still-valid byte.
"""

import threading
from typing import Dict

import numpy as np


class RingBuffer:
    """Broadcast ring buffer with per-reader cursors."""

    def __init__(self, capacity_bytes: int = 176400):
        self._capacity = capacity_bytes
        self._buffer = np.zeros(capacity_bytes, dtype=np.uint8)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()
        self._peak_level = 0.0
        self._readers: Dict[str, int] = {}

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def peak_level(self) -> float:
        with self._lock:
            level = self._peak_level
            self._peak_level *= 0.85
            return level

    def register_reader(self, reader_id: str, cushion_bytes: int = 0) -> None:
        """Register a reader. cushion_bytes makes it start that many bytes
        behind the write head, giving a jitter buffer that prevents
        underruns (which cause crackling). Clamped to available data.
        """
        with self._lock:
            start = self._total_written - max(0, cushion_bytes)
            oldest_valid = max(0, self._total_written - self._capacity)
            self._readers[reader_id] = max(oldest_valid, start)

    def unregister_reader(self, reader_id: str) -> None:
        with self._lock:
            self._readers.pop(reader_id, None)

    def write(self, data: bytes) -> int:
        n = len(data)
        if n == 0:
            return 0

        with self._lock:
            if n >= 2:
                samples = np.frombuffer(data, dtype=np.int16)
                if len(samples) > 0:
                    peak = float(np.max(np.abs(samples))) / 32768.0
                    if peak > self._peak_level:
                        self._peak_level = peak

            arr = np.frombuffer(data, dtype=np.uint8)

            if n > self._capacity:
                arr = arr[-self._capacity:]
                n = self._capacity

            first_chunk = min(n, self._capacity - self._write_pos)
            self._buffer[self._write_pos:self._write_pos + first_chunk] = arr[:first_chunk]

            remainder = n - first_chunk
            if remainder > 0:
                self._buffer[:remainder] = arr[first_chunk:]

            self._write_pos = (self._write_pos + n) % self._capacity
            self._total_written += n

            # Advance lagging readers (snapshot keys to allow concurrent unregister)
            oldest_valid = self._total_written - self._capacity
            for rid in list(self._readers.keys()):
                pos = self._readers.get(rid)
                if pos is not None and pos < oldest_valid:
                    self._readers[rid] = oldest_valid

            return n

    def read(self, n: int, reader_id: str) -> bytes:
        """Read up to n bytes for reader_id. Returns silence if not registered or no data."""
        with self._lock:
            if reader_id not in self._readers:
                # Reader not registered: return silence, don't auto-create
                return bytes(n)

            reader_pos = self._readers[reader_id]
            available_bytes = self._total_written - reader_pos

            if available_bytes <= 0:
                return bytes(n)

            to_read = min(n, available_bytes)
            buf_start = reader_pos % self._capacity

            result = bytearray(n)
            first_chunk = min(to_read, self._capacity - buf_start)
            result[:first_chunk] = self._buffer[buf_start:buf_start + first_chunk].tobytes()

            remainder = to_read - first_chunk
            if remainder > 0:
                result[first_chunk:first_chunk + remainder] = self._buffer[:remainder].tobytes()

            self._readers[reader_id] = reader_pos + to_read
            return bytes(result)

    def clear(self) -> None:
        with self._lock:
            self._write_pos = 0
            self._total_written = 0
            self._peak_level = 0.0
            for rid in list(self._readers.keys()):
                self._readers[rid] = 0
