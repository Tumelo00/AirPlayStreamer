"""Thread-safe ring buffer for bridging audio capture and AirPlay streaming.

Supports multiple readers: each reader gets its own cursor so both HomePods
receive the same audio data independently.
"""

import threading
from typing import Dict

import numpy as np


class RingBuffer:
    """Broadcast ring buffer: one writer, multiple independent readers."""

    def __init__(self, capacity_bytes: int = 176400):
        self._capacity = capacity_bytes
        self._buffer = np.zeros(capacity_bytes, dtype=np.uint8)
        self._write_pos = 0
        self._total_written = 0  # monotonically increasing byte counter
        self._lock = threading.Lock()
        self._peak_level = 0.0
        # Each reader has its own "total_read" counter
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

    def register_reader(self, reader_id: str) -> None:
        """Register a new reader. It starts reading from the current position."""
        with self._lock:
            self._readers[reader_id] = self._total_written

    def unregister_reader(self, reader_id: str) -> None:
        """Remove a reader."""
        with self._lock:
            self._readers.pop(reader_id, None)

    def write(self, data: bytes) -> int:
        """Write audio data. All registered readers can read it independently."""
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

            # If any reader fell behind more than capacity, advance it
            oldest_valid = self._total_written - self._capacity
            for rid in self._readers:
                if self._readers[rid] < oldest_valid:
                    self._readers[rid] = oldest_valid

            return n

    def read(self, n: int, reader_id: str = "default") -> bytes:
        """Read up to n bytes for a specific reader. Returns silence if not enough data."""
        with self._lock:
            if reader_id not in self._readers:
                self._readers[reader_id] = self._total_written

            reader_pos = self._readers[reader_id]
            available_bytes = self._total_written - reader_pos

            if available_bytes <= 0:
                return bytes(n)

            to_read = min(n, available_bytes)

            # Calculate where in the circular buffer this reader's data starts
            buf_start = reader_pos % self._capacity

            result = bytearray(n)
            first_chunk = min(to_read, self._capacity - buf_start)
            result[:first_chunk] = self._buffer[buf_start:buf_start + first_chunk].tobytes()

            remainder = to_read - first_chunk
            if remainder > 0:
                result[first_chunk:first_chunk + remainder] = self._buffer[:remainder].tobytes()

            self._readers[reader_id] = reader_pos + to_read

            return bytes(result)

    def clear(self):
        with self._lock:
            self._write_pos = 0
            self._total_written = 0
            self._peak_level = 0.0
            for rid in self._readers:
                self._readers[rid] = 0
