"""Settings persistence via JSON file."""

import json
import logging
import os
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), "AirPlayStreamer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

# Latency profiles: name -> milliseconds. Converted to samples at 44100Hz.
# Lower = less delay but less jitter tolerance.
LATENCY_PROFILES = {
    "ultra_low": ("Ultra Dusuk (~100ms)", 100),
    "low": ("Dusuk (~250ms)", 250),
    "balanced": ("Dengeli (~500ms)", 500),
    "stable": ("Kararli (~1500ms)", 1500),
}
DEFAULT_LATENCY_PROFILE = "balanced"


def latency_profile_to_samples(profile_key: str, sample_rate: int = 44100) -> int:
    """Convert a latency profile key to a sample count."""
    entry = LATENCY_PROFILES.get(profile_key)
    ms = entry[1] if entry else LATENCY_PROFILES[DEFAULT_LATENCY_PROFILE][1]
    return int(sample_rate * ms / 1000)


DEFAULTS = {
    "window_x": None,
    "window_y": None,
    "window_width": 520,
    "window_height": 800,
    "selected_audio_device_index": None,
    "last_device_ids": [],
    "volume_levels": {},
    "minimize_to_tray": True,
    "start_minimized": False,
    "auto_connect": False,
    "latency_profile": DEFAULT_LATENCY_PROFILE,
    "device_delays": {},  # device_id -> calibration delay ms
}


class Config:
    """Simple JSON-based settings store."""

    def __init__(self):
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data.update(saved)
            except Exception as e:
                _LOGGER.warning("Failed to load config: %s", e)

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            _LOGGER.error("Failed to save config: %s", e)

    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value
