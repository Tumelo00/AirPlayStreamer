"""Main application window."""

import customtkinter as ctk
import logging
from typing import Optional

from core.config import Config
from core.streamer import Streamer, StreamerState
from ui.control_panel import ControlPanel
from ui.device_panel import DevicePanel
from ui.pairing_dialog import PairingDialog
from ui.settings_dialog import SettingsDialog
from ui.status_bar import StatusBar
from ui.tray_icon import TrayIcon
from ui.theme import *

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL_MS = 100  # UI refresh rate


class AirPlayStreamerApp(ctk.CTk):
    """Main application window."""

    def __init__(self, streamer: Streamer, config: Config):
        super().__init__()
        self._streamer = streamer
        self._config = config

        # Window setup
        self.title(S["app_title"])
        self.geometry(f"{config['window_width']}x{config['window_height']}")
        self.minsize(460, 600)
        self.configure(fg_color=BG_DARK)

        # Restore window position
        if config["window_x"] is not None and config["window_y"] is not None:
            self.geometry(f"+{config['window_x']}+{config['window_y']}")

        ctk.set_appearance_mode("dark")


        # Build UI
        self._build_ui()

        # System tray
        self._tray = TrayIcon(
            on_show=self._show_from_tray,
            on_toggle=self._tray_toggle,
            on_exit=self._on_exit,
        )
        self._tray.start()

        # Window events
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start polling for state updates
        self._poll_id = None
        self._start_polling()

        # Auto-scan on startup (single scan)
        self._initial_scan_done = False
        self.after(300, self._auto_scan)

    def _build_ui(self):
        """Create all UI components."""
        # App header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=S["app_title"],
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        # Settings button
        self._settings_btn = ctk.CTkButton(
            header, text="\u2699", width=36, height=36,
            font=ctk.CTkFont(size=18),
            fg_color=BG_CARD, hover_color=BG_INPUT,
            corner_radius=8,
            command=self._open_settings,
        )
        self._settings_btn.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            header, text=S["app_subtitle"],
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).grid(row=1, column=0, sticky="w", columnspan=2)

        # Device panel
        self._device_panel = DevicePanel(
            self,
            on_scan=self._on_scan,
            on_pair=self._on_pair,
        )
        self._device_panel.pack(fill="both", expand=True, padx=15, pady=(10, 5))

        # Control panel
        self._control_panel = ControlPanel(
            self,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_volume=self._on_volume,
        )
        self._control_panel.pack(fill="x", padx=15, pady=5)

        # Status bar
        self._status_bar = StatusBar(self)
        self._status_bar.pack(fill="x", padx=15, pady=(5, 15))

    def _start_polling(self):
        """Poll streamer status and update UI."""
        status = self._streamer.get_status()

        # Update device panel
        self._device_panel.update_devices(status.devices)

        # Update control panel
        is_streaming = status.state == StreamerState.STREAMING
        self._control_panel.set_streaming(is_streaming)
        self._tray.set_streaming(is_streaming)

        # Update status bar
        self._status_bar.update_status(
            status.state, status.audio_level, status.error_message
        )

        # Schedule next poll
        self._poll_id = self.after(POLL_INTERVAL_MS, self._start_polling)

    def _auto_scan(self):
        if not self._initial_scan_done:
            self._initial_scan_done = True
            self._streamer.request_scan()

    # ── Event handlers ──

    def _on_scan(self):
        self._streamer.request_scan()

    def _on_pair(self, device_id: str):
        device = None
        for d in self._streamer.get_status().devices:
            if d.identifier == device_id:
                device = d
                break

        if device:
            PairingDialog(
                self,
                device_name=device.name,
                on_confirm=lambda pin: self._streamer.request_complete_pairing(
                    device_id, pin
                ),
            )

    def _on_start(self):
        selected = self._device_panel.get_selected_device_ids()
        if not selected:
            return

        # Get audio device from settings
        audio_device = None
        saved_idx = self._config.get("selected_audio_device_index")
        if saved_idx is not None:
            for dev in self._streamer.get_loopback_devices():
                if dev.index == saved_idx:
                    audio_device = dev
                    break

        # Apply latency profile from config
        from core.config import latency_profile_to_samples
        profile = self._config.get("latency_profile", "balanced")
        self._streamer.set_latency_samples(latency_profile_to_samples(profile))

        self._streamer.request_start_streaming(selected, audio_device)

    def _on_stop(self):
        self._streamer.request_stop_streaming()

    def _on_volume(self, volume: float):
        status = self._streamer.get_status()
        for device in status.devices:
            if device.state.value == "streaming":
                self._streamer.request_set_volume(device.identifier, volume)

    def _open_settings(self):
        audio_devices = self._streamer.get_loopback_devices()
        SettingsDialog(
            self,
            config=self._config,
            audio_devices=audio_devices,
            on_save=self._on_settings_saved,
        )

    def _on_settings_saved(self, config: Config):
        self._config = config

    # ── Window management ──

    def _on_close(self):
        if self._config.get("minimize_to_tray", True):
            self.withdraw()
        else:
            self._on_exit()

    def _on_exit(self):
        # Save window position
        try:
            self._config.set("window_x", self.winfo_x())
            self._config.set("window_y", self.winfo_y())
            self._config.set("window_width", self.winfo_width())
            self._config.set("window_height", self.winfo_height())
            self._config.save()
        except Exception:
            pass

        if self._poll_id:
            self.after_cancel(self._poll_id)

        self._tray.stop()
        self._streamer.shutdown()
        self.destroy()

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_toggle(self):
        status = self._streamer.get_status()
        if status.state == StreamerState.STREAMING:
            self._on_stop()
        else:
            self._on_start()
