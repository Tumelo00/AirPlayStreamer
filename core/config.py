"""Settings persistence via JSON file."""

import json
import logging
import os
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), "AirPlayStreamer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "window_x": None,
    "window_y": None,
    "window_width": 520,
    "window_height": 700,
    "selected_audio_device_index": None,
    "last_device_ids": [],
    "volume_levels": {},
    "minimize_to_tray": True,
    "start_minimized": False,
    "auto_connect": False,
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
