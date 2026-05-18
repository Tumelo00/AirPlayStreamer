"""Diagnostics dialog - live view of network/audio/stream state."""

import logging
import os

import customtkinter as ctk

from ui.theme import *

_LOGGER = logging.getLogger(__name__)

LOG_DIR = os.path.join(os.environ.get("APPDATA", ""), "AirPlayStreamer")

# (key, label) pairs in display order
_ROWS = [
    ("state", "Yayin Durumu"),
    ("interface", "Ag Arayuzu"),
    ("local_ip", "Yerel IP"),
    ("homepod_ip", "HomePod IP"),
    ("capture_device", "Ses Cihazi"),
    ("capture_rate", "Ornek Hizi"),
    ("latency_samples", "Gecikme (sample)"),
    ("resampler", "Resampler"),
    ("reconnect_attempts", "Yeniden Baglanma"),
    ("error", "Son Hata"),
]


class DiagnosticsDialog(ctk.CTkToplevel):
    """Live diagnostics panel. Polls streamer.get_diagnostics()."""

    def __init__(self, master, streamer):
        super().__init__(master)
        self._streamer = streamer
        self._closed = False

        self.title("Tani / Diagnostics")
        self.geometry("420x420")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.transient(master)

        ctk.CTkLabel(
            self, text="Tani Bilgileri",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 12))

        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self._value_labels = {}
        for key, label in _ROWS:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(
                row, text=label, width=140, anchor="w",
                font=ctk.CTkFont(size=11), text_color=TEXT_MUTED,
            ).pack(side="left")
            val = ctk.CTkLabel(
                row, text="-", anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=TEXT_SECONDARY, wraplength=230, justify="left",
            )
            val.pack(side="left", fill="x", expand=True)
            self._value_labels[key] = val

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btns, text="Loglari Ac", height=36,
            font=ctk.CTkFont(size=12),
            fg_color=BG_INPUT, hover_color=BORDER,
            command=self._open_logs,
        ).pack(side="left", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btns, text="Kapat", height=36,
            font=ctk.CTkFont(size=12),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._close,
        ).pack(side="right", expand=True, padx=(5, 0))

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._refresh()

    def _refresh(self):
        if self._closed:
            return
        try:
            diag = self._streamer.get_diagnostics()
            for key, _ in _ROWS:
                val = diag.get(key, "-")
                if key == "capture_rate" and val:
                    val = f"{val} Hz"
                self._value_labels[key].configure(text=str(val))
        except Exception as e:
            _LOGGER.debug("Diagnostics refresh failed: %s", e)
        self.after(1000, self._refresh)

    def _open_logs(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            os.startfile(LOG_DIR)  # noqa: Windows only
        except Exception as e:
            _LOGGER.error("Failed to open logs folder: %s", e)

    def _close(self):
        self._closed = True
        self.destroy()
