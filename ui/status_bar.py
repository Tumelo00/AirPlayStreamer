"""Status bar with audio level meter and connection info."""

import customtkinter as ctk

from core.streamer import StreamerState
from ui.theme import *


class AudioMeter(ctk.CTkFrame):
    """Visual audio level meter."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_INPUT, corner_radius=6,
                         height=20, **kwargs)
        self.pack_propagate(False)

        self._bar = ctk.CTkFrame(
            self, fg_color=SUCCESS, corner_radius=4,
            height=14, width=0,
        )
        self._bar.place(x=3, y=3)
        self._max_width = 200
        self._level = 0.0

    def set_level(self, level: float):
        """Set audio level (0.0 to 1.0)."""
        self._level = max(0.0, min(1.0, level))
        width = int(self._level * self._max_width)

        # Color based on level
        if self._level > 0.85:
            color = ERROR
        elif self._level > 0.6:
            color = WARNING
        else:
            color = SUCCESS

        self._bar.configure(width=max(1, width), fg_color=color)

    def update_width(self, container_width: int):
        self._max_width = max(50, container_width - 6)


class StatusBar(ctk.CTkFrame):
    """Status bar showing streaming state, latency, and audio level."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)

        # Header
        ctk.CTkLabel(
            self, text=S["status"],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # Status info frame
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=15, pady=(0, 5))
        info_frame.grid_columnconfigure(1, weight=1)

        # Status row
        ctk.CTkLabel(
            info_frame, text="Durum:",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self._status_label = ctk.CTkLabel(
            info_frame, text=S["status_idle"],
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self._status_label.grid(row=0, column=1, sticky="w")

        # Latency indicator
        self._latency_label = ctk.CTkLabel(
            info_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        )
        self._latency_label.grid(row=0, column=2, sticky="e")

        # Audio level label
        ctk.CTkLabel(
            self, text=S["audio_level"],
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=15, pady=(5, 2))

        # Audio meter
        self._meter = AudioMeter(self)
        self._meter.pack(fill="x", padx=15, pady=(0, 15))

    def update_status(self, state: StreamerState, audio_level: float = 0.0,
                      error_message: str = ""):
        """Update status display."""
        status_map = {
            StreamerState.IDLE: (S["status_idle"], TEXT_SECONDARY),
            StreamerState.SCANNING: (S["status_scanning"], WARNING),
            StreamerState.CONNECTING: (S["status_connecting"], WARNING),
            StreamerState.STREAMING: (S["status_streaming"], SUCCESS),
            StreamerState.STOPPING: (S["status_stopping"], WARNING),
            StreamerState.ERROR: (error_message or S["status_error"], ERROR),
        }

        text, color = status_map.get(state, (S["status_idle"], TEXT_SECONDARY))
        self._status_label.configure(text=text, text_color=color)

        # Show latency only when streaming
        if state == StreamerState.STREAMING:
            self._latency_label.configure(text=f"{S['latency']}: {S['latency_value']}")
        else:
            self._latency_label.configure(text="")

        self._meter.set_level(audio_level)
