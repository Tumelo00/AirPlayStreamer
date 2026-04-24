"""Play/Stop and volume controls."""

import customtkinter as ctk
from typing import Callable

from ui.theme import *


class ControlPanel(ctk.CTkFrame):
    """Panel with streaming controls and volume slider."""

    def __init__(self, master, on_start: Callable, on_stop: Callable,
                 on_volume: Callable, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_volume = on_volume
        self._is_streaming = False

        # Header
        ctk.CTkLabel(
            self, text=S["controls"],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Start/Stop button
        self._action_btn = ctk.CTkButton(
            self, text=S["start"], height=48,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._toggle,
        )
        self._action_btn.pack(fill="x", padx=15, pady=(0, 15))

        # Volume section
        vol_frame = ctk.CTkFrame(self, fg_color="transparent")
        vol_frame.pack(fill="x", padx=15, pady=(0, 15))
        vol_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            vol_frame, text=S["volume"],
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        self._volume_var = ctk.DoubleVar(value=50)
        self._volume_slider = ctk.CTkSlider(
            vol_frame, from_=0, to=100,
            variable=self._volume_var,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT,
            fg_color=BG_INPUT,
            command=self._on_volume_change,
        )
        self._volume_slider.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        self._volume_label = ctk.CTkLabel(
            vol_frame, text="50%", width=45,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        )
        self._volume_label.grid(row=0, column=2)

    def _toggle(self):
        if self._is_streaming:
            self._on_stop()
        else:
            self._on_start()

    def _on_volume_change(self, value):
        vol = int(value)
        self._volume_label.configure(text=f"{vol}%")
        self._on_volume(vol)

    def set_streaming(self, streaming: bool):
        """Update button state based on streaming status."""
        self._is_streaming = streaming
        if streaming:
            self._action_btn.configure(
                text=S["stop"],
                fg_color=ERROR,
                hover_color="#ff6b6b",
            )
        else:
            self._action_btn.configure(
                text=S["start"],
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
            )

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._action_btn.configure(state=state)

    @property
    def volume(self) -> float:
        return self._volume_var.get()
