"""WASAPI loopback audio capture using PyAudioWPatch."""

import logging
import threading
from typing import List, Optional, Tuple

import numpy as np
import pyaudiowpatch as pyaudio

from core.ring_buffer import RingBuffer

_LOGGER = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 44100
TARGET_CHANNELS = 2
TARGET_SAMPLE_WIDTH = 2
FRAMES_PER_BUFFER = 352  # Aligned with pyatv FRAMES_PER_PACKET


class AudioDevice:
    def __init__(self, index: int, name: str, sample_rate: int, channels: int,
                 is_loopback: bool = False):
        self.index = index
        self.name = name
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_loopback = is_loopback

    def __repr__(self):
        return f"AudioDevice({self.name}, {self.sample_rate}Hz, {self.channels}ch)"


class AudioCapture:
    def __init__(self, ring_buffer: RingBuffer):
        self._buffer = ring_buffer
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._running = False
        self._device: Optional[AudioDevice] = None
        self._lock = threading.Lock()
        self._callback_errors = 0
        self._max_callback_errors = 50  # Stop after too many consecutive errors

        # Pre-computed resample interpolation coefficients (filled on start())
        self._resample_x_old: Optional[np.ndarray] = None
        self._resample_x_new: Optional[np.ndarray] = None
        self._resample_dst_frames = 0

    def get_loopback_devices(self) -> List[AudioDevice]:
        devices: List[AudioDevice] = []
        pa = pyaudio.PyAudio()
        try:
            for loopback in pa.get_loopback_device_info_generator():
                dev = AudioDevice(
                    index=loopback["index"],
                    name=loopback["name"],
                    sample_rate=int(loopback["defaultSampleRate"]),
                    channels=loopback["maxInputChannels"],
                    is_loopback=True,
                )
                if not any(d.index == dev.index for d in devices):
                    devices.append(dev)
        except Exception as e:
            _LOGGER.error("Failed to enumerate loopback devices: %s", e)
        finally:
            pa.terminate()
        return devices

    def get_default_loopback(self) -> Optional[AudioDevice]:
        """Pick the best loopback device (prefer physical output)."""
        devices = self.get_loopback_devices()
        if not devices:
            return None

        virtual_keywords = ["sonar", "virtual", "vb-audio", "cable", "voicemeeter"]
        skip_keywords = ["digital output", "spdif", "microphone", "mikrofon"]

        for dev in devices:
            name_lower = dev.name.lower()
            is_virtual = any(kw in name_lower for kw in virtual_keywords)
            is_skip = any(kw in name_lower for kw in skip_keywords)
            if not is_virtual and not is_skip:
                _LOGGER.info("Selected physical loopback: %s", dev.name)
                return dev

        for dev in devices:
            name_lower = dev.name.lower()
            is_virtual = any(kw in name_lower for kw in virtual_keywords)
            is_mic = "microphone" in name_lower or "mikrofon" in name_lower
            if not is_virtual and not is_mic:
                _LOGGER.info("Selected non-virtual loopback: %s", dev.name)
                return dev

        pa = pyaudio.PyAudio()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_idx = wasapi_info["defaultOutputDevice"]
            default_info = pa.get_device_info_by_index(default_idx)
            default_name = default_info["name"]
            for dev in devices:
                if default_name in dev.name:
                    _LOGGER.info("Selected default loopback: %s", dev.name)
                    return dev
        except Exception:
            pass
        finally:
            pa.terminate()

        _LOGGER.info("Using first available loopback: %s", devices[0].name)
        return devices[0]

    def _precompute_resample(self, src_rate: int, src_frames_per_buffer: int) -> None:
        """Pre-compute interp arrays for fast hot-path resampling."""
        dst_frames = int(src_frames_per_buffer * TARGET_SAMPLE_RATE / src_rate)
        self._resample_dst_frames = dst_frames
        if dst_frames > 0:
            self._resample_x_old = np.linspace(0, 1, src_frames_per_buffer, dtype=np.float64)
            self._resample_x_new = np.linspace(0, 1, dst_frames, dtype=np.float64)

    def start(self, device: Optional[AudioDevice] = None) -> None:
        with self._lock:
            if self._running:
                return

            chosen = device or self.get_default_loopback()
            if chosen is None:
                raise RuntimeError("No loopback device found")

            self._device = chosen
            self._pa = pyaudio.PyAudio()
            self._callback_errors = 0

            src_rate = chosen.sample_rate
            src_ch = chosen.channels
            needs_convert = (src_rate != TARGET_SAMPLE_RATE or src_ch != TARGET_CHANNELS)

            if needs_convert and src_rate != TARGET_SAMPLE_RATE:
                self._precompute_resample(src_rate, FRAMES_PER_BUFFER)

            def audio_callback(in_data, frame_count, time_info, status):
                try:
                    data = in_data
                    if needs_convert:
                        data = self._convert_audio(data, src_rate, src_ch,
                                                   TARGET_SAMPLE_RATE, TARGET_CHANNELS)
                    self._buffer.write(data)
                    self._callback_errors = 0
                except Exception as e:
                    self._callback_errors += 1
                    if self._callback_errors <= 3:
                        _LOGGER.error("Audio callback error (%d): %s",
                                      self._callback_errors, e)
                    if self._callback_errors >= self._max_callback_errors:
                        _LOGGER.error("Too many callback errors, stopping stream")
                        return (None, pyaudio.paAbort)
                return (None, pyaudio.paContinue)

            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=chosen.channels,
                rate=chosen.sample_rate,
                input=True,
                input_device_index=chosen.index,
                frames_per_buffer=FRAMES_PER_BUFFER,
                stream_callback=audio_callback,
            )

            self._stream.start_stream()
            self._running = True
            _LOGGER.info("Audio capture started: %s (%dHz, %dch)",
                         chosen.name, chosen.sample_rate, chosen.channels)

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._pa:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
                self._pa = None
            _LOGGER.info("Audio capture stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_device(self) -> Optional[AudioDevice]:
        return self._device

    def _convert_audio(self, data: bytes, src_rate: int, src_channels: int,
                       dst_rate: int, dst_channels: int) -> bytes:
        samples = np.frombuffer(data, dtype=np.int16)
        if src_channels > 0:
            samples = samples.reshape(-1, src_channels)

        # Channel conversion
        if src_channels != dst_channels:
            if dst_channels == 2 and src_channels == 1:
                samples = np.column_stack([samples, samples])
            elif dst_channels == 1 and src_channels == 2:
                samples = samples.mean(axis=1, keepdims=True).astype(np.int16)
            elif dst_channels == 2 and src_channels > 2:
                samples = samples[:, :2]

        # Resample using pre-computed interpolation arrays when possible
        if src_rate != dst_rate:
            src_frames = samples.shape[0]
            if (self._resample_x_old is not None
                    and src_frames == len(self._resample_x_old)
                    and self._resample_dst_frames > 0):
                # Fast path: pre-computed coefficients
                resampled = np.empty(
                    (self._resample_dst_frames, samples.shape[1]), dtype=np.int16)
                for ch in range(samples.shape[1]):
                    resampled[:, ch] = np.interp(
                        self._resample_x_new, self._resample_x_old,
                        samples[:, ch].astype(np.float64)
                    ).astype(np.int16)
                samples = resampled
            else:
                # Slow path: dynamic computation
                dst_frames = int(src_frames * dst_rate / src_rate)
                if dst_frames > 0:
                    x_old = np.linspace(0, 1, src_frames)
                    x_new = np.linspace(0, 1, dst_frames)
                    resampled = np.empty((dst_frames, samples.shape[1]), dtype=np.int16)
                    for ch in range(samples.shape[1]):
                        resampled[:, ch] = np.interp(
                            x_new, x_old, samples[:, ch].astype(np.float64)
                        ).astype(np.int16)
                    samples = resampled

        return samples.tobytes()
