"""Audio resampler with optional high-quality soxr backend.

soxr (the SoX Resampler library) gives far better quality than linear
interpolation. It is an optional dependency - if not installed, we fall
back to numpy linear interpolation. Either way the app never crashes.
"""

import logging

import numpy as np

_LOGGER = logging.getLogger(__name__)

# Detect soxr once at import time
try:
    import soxr  # type: ignore
    _SOXR_AVAILABLE = True
except Exception:
    soxr = None
    _SOXR_AVAILABLE = False


def resampler_backend() -> str:
    """Return the active resampler backend name."""
    return "soxr" if _SOXR_AVAILABLE else "numpy-linear"


class Resampler:
    """Stateful audio resampler. One instance per (src_rate, dst_rate, channels)."""

    def __init__(self, src_rate: int, dst_rate: int, channels: int):
        self.src_rate = src_rate
        self.dst_rate = dst_rate
        self.channels = channels
        self._needed = src_rate != dst_rate
        self._soxr_stream = None

        if self._needed and _SOXR_AVAILABLE:
            try:
                # Streaming resampler keeps phase continuity between chunks
                self._soxr_stream = soxr.ResampleStream(
                    src_rate, dst_rate, channels,
                    dtype="int16", quality="HQ",
                )
            except Exception as e:
                _LOGGER.warning("soxr stream init failed (%s), using numpy", e)
                self._soxr_stream = None

        _LOGGER.info("Resampler %d->%dHz %dch backend=%s",
                     src_rate, dst_rate, channels,
                     "soxr" if self._soxr_stream else "numpy-linear")

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Resample a (frames, channels) int16 array. Returns same layout."""
        if not self._needed:
            return samples

        if self._soxr_stream is not None:
            try:
                out = self._soxr_stream.resample_chunk(samples)
                return np.asarray(out, dtype=np.int16)
            except Exception as e:
                _LOGGER.warning("soxr resample failed (%s), numpy fallback", e)
                self._soxr_stream = None

        return self._numpy_resample(samples)

    def _numpy_resample(self, samples: np.ndarray) -> np.ndarray:
        """Linear interpolation fallback."""
        src_frames = samples.shape[0]
        if src_frames == 0:
            return samples
        dst_frames = int(src_frames * self.dst_rate / self.src_rate)
        if dst_frames <= 0:
            return samples[:0]
        x_old = np.linspace(0.0, 1.0, src_frames)
        x_new = np.linspace(0.0, 1.0, dst_frames)
        ch = samples.shape[1] if samples.ndim > 1 else 1
        out = np.empty((dst_frames, ch), dtype=np.int16)
        cols = samples if samples.ndim > 1 else samples.reshape(-1, 1)
        for c in range(ch):
            out[:, c] = np.interp(
                x_new, x_old, cols[:, c].astype(np.float64)
            ).astype(np.int16)
        return out
