"""Settings dialog for audio device selection and preferences."""

import customtkinter as ctk
from typing import Callable, List, Optional

from core.audio_capture import AudioDevice
from core.config import Config
from ui.theme import *


class SettingsDialog(ctk.CTkToplevel):
    """Settings/preferences dialog."""

    def __init__(self, master, config: Config,
                 audio_devices: List[AudioDevice],
                 on_save: Callable[[Config], None]):
        super().__init__(master)
        self._config = config
        self._on_save = on_save

        self.title(S["settings"])
        self.geometry("400x320")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.transient(master)
        self.grab_set()

        # Title
        ctk.CTkLabel(
            self, text=S["settings"],
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(20, 15))

        # Audio device selection
        device_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        device_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            device_frame, text=S["audio_device"],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=15, pady=(12, 5))

        device_names = [S["audio_device_default"]] + [d.name for d in audio_devices]
        self._device_var = ctk.StringVar(value=device_names[0])

        saved_idx = config.get("selected_audio_device_index")
        if saved_idx is not None:
            for d in audio_devices:
                if d.index == saved_idx:
                    self._device_var.set(d.name)
                    break

        self._device_dropdown = ctk.CTkComboBox(
            device_frame, values=device_names,
            variable=self._device_var,
            fg_color=BG_INPUT, border_color=BORDER,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            dropdown_fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            dropdown_text_color=TEXT_PRIMARY,
            width=300,
        )
        self._device_dropdown.pack(padx=15, pady=(0, 12))
        self._audio_devices = audio_devices

        # Options
        options_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        options_frame.pack(fill="x", padx=20, pady=(0, 10))

        self._tray_var = ctk.BooleanVar(value=config.get("minimize_to_tray", True))
        ctk.CTkCheckBox(
            options_frame, text=S["minimize_to_tray"],
            variable=self._tray_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=15, pady=(12, 5))

        self._auto_var = ctk.BooleanVar(value=config.get("auto_connect", False))
        ctk.CTkCheckBox(
            options_frame, text=S["auto_connect"],
            variable=self._auto_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=15, pady=(5, 12))

        # Save button
        ctk.CTkButton(
            self, text=S["close"], height=38,
            font=ctk.CTkFont(size=13),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save_and_close,
        ).pack(fill="x", padx=20, pady=(5, 20))

    def _save_and_close(self):
        selected_name = self._device_var.get()
        if selected_name == S["audio_device_default"]:
            self._config.set("selected_audio_device_index", None)
        else:
            for d in self._audio_devices:
                if d.name == selected_name:
                    self._config.set("selected_audio_device_index", d.index)
                    break

        self._config.set("minimize_to_tray", self._tray_var.get())
        self._config.set("auto_connect", self._auto_var.get())
        self._config.save()
        self._on_save(self._config)
        self.destroy()
