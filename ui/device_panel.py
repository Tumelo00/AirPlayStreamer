"""Device list panel with scan and pair controls."""

import logging
import customtkinter as ctk
from typing import Callable, Dict, List, Optional

from core.device_manager import AirPlayDevice, DeviceState
from ui.theme import *

_LOGGER = logging.getLogger(__name__)


class DeviceCard(ctk.CTkFrame):
    """A single device entry in the device list."""

    def __init__(self, master, device: AirPlayDevice,
                 on_pair: Callable, on_select: Callable,
                 on_delay_change: Callable = None, delay_ms: int = 0,
                 **kwargs):
        super().__init__(master, fg_color=BG_INPUT, corner_radius=8,
                         height=100, **kwargs)
        self.pack_propagate(False)  # Force fixed height
        self._device = device
        self._on_pair_cb = on_pair
        self._on_select_cb = on_select
        self._on_delay_cb = on_delay_change

        # Internal layout frame
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)
        inner.grid_columnconfigure(1, weight=1)

        # Checkbox for selection
        self._checkbox_var = ctk.BooleanVar(value=False)
        self._checkbox = ctk.CTkCheckBox(
            inner, text="", variable=self._checkbox_var,
            width=22, height=22,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            border_color=BORDER,
            command=self._on_check_changed,
        )
        self._checkbox.grid(row=0, column=0, padx=(5, 8), pady=5, rowspan=2, sticky="w")

        # Device name (stereo pairs get a speaker-pair prefix)
        name_prefix = "\U0001F50A\U0001F50A  " if device.is_group else ""
        self._name_label = ctk.CTkLabel(
            inner, text=name_prefix + device.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._name_label.grid(row=0, column=1, padx=2, pady=(5, 0), sticky="w")

        # Device address + state (groups show "Stereo Cift")
        state_text = S.get(device.state.value, device.state.value)
        state_color = STATUS_COLORS.get(device.state.value, TEXT_MUTED)
        kind = "Stereo Cift (2 HomePod)" if device.is_group else device.address
        self._status_label = ctk.CTkLabel(
            inner, text=f"{kind}  |  {state_text}",
            font=ctk.CTkFont(size=11),
            text_color=state_color, anchor="w",
        )
        self._status_label.grid(row=1, column=1, padx=2, pady=(0, 5), sticky="w")

        # Right side: status dot + pair button
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, padx=(5, 5), sticky="e")

        self._dot = ctk.CTkLabel(
            right, text="\u25CF", width=20,
            font=ctk.CTkFont(size=16),
            text_color=state_color,
        )
        self._dot.pack(side="top", pady=(5, 0))

        # Per-device delay calibration row
        delay_row = ctk.CTkFrame(inner, fg_color="transparent")
        delay_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=2)
        delay_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            delay_row, text="Gecikme", width=58, anchor="w",
            font=ctk.CTkFont(size=10), text_color=TEXT_MUTED,
        ).grid(row=0, column=0, padx=(3, 4))

        self._delay_var = ctk.DoubleVar(value=delay_ms)
        self._delay_slider = ctk.CTkSlider(
            delay_row, from_=0, to=500, variable=self._delay_var,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT, fg_color=BG_CARD, height=14,
            command=self._on_delay_changed,
        )
        self._delay_slider.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self._delay_label = ctk.CTkLabel(
            delay_row, text=f"{int(delay_ms)}ms", width=46,
            font=ctk.CTkFont(size=10), text_color=TEXT_SECONDARY,
        )
        self._delay_label.grid(row=0, column=2, padx=(0, 3))

    def _on_delay_changed(self, value):
        ms = int(value)
        self._delay_label.configure(text=f"{ms}ms")
        if self._on_delay_cb:
            self._on_delay_cb(self._device.identifier, ms)

    def _on_check_changed(self):
        self._on_select_cb(self._device.identifier, self._checkbox_var.get())

    def update_state(self, device: AirPlayDevice):
        """Update the card's display based on device state."""
        self._device = device
        state_text = S.get(device.state.value, device.state.value)
        state_color = STATUS_COLORS.get(device.state.value, TEXT_MUTED)

        name_prefix = "\U0001F50A\U0001F50A  " if device.is_group else ""
        kind = "Stereo Cift (2 HomePod)" if device.is_group else device.address
        self._name_label.configure(text=name_prefix + device.name)
        self._status_label.configure(
            text=f"{kind}  |  {state_text}",
            text_color=state_color,
        )
        self._dot.configure(text_color=state_color)

    @property
    def is_selected(self) -> bool:
        return self._checkbox_var.get()

    def set_selected(self, selected: bool):
        self._checkbox_var.set(selected)


class DevicePanel(ctk.CTkFrame):
    """Panel showing discovered AirPlay devices with controls."""

    def __init__(self, master, on_scan: Callable, on_pair: Callable,
                 on_selection_change: Callable = None,
                 on_delay_change: Callable = None,
                 device_delays: dict = None, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self._on_scan = on_scan
        self._on_pair = on_pair
        self._on_selection_change = on_selection_change
        self._on_delay_change = on_delay_change
        self._device_delays = device_delays if device_delays is not None else {}
        self._cards: Dict[str, DeviceCard] = {}
        self._selected_ids: set = set()
        self._last_device_count = -1

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=S["devices"],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self._scan_btn = ctk.CTkButton(
            header, text=S["scan"], width=130, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._on_scan_click,
        )
        self._scan_btn.grid(row=0, column=1, sticky="e")

        # Device list container (simple frame, no scroll needed for 2 devices)
        self._list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Empty state
        self._empty_label = ctk.CTkLabel(
            self._list_frame, text=S["no_devices"],
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self._empty_label.pack(pady=30)
        self._empty_visible = True

        self._is_scanning = False

    def _on_scan_click(self):
        if not self._is_scanning:
            self._is_scanning = True
            self._scan_btn.configure(text=S["scanning"], state="disabled")
            self._on_scan()

    def _on_device_select(self, device_id: str, selected: bool):
        if selected:
            self._selected_ids.add(device_id)
        else:
            self._selected_ids.discard(device_id)
        if self._on_selection_change:
            self._on_selection_change(device_id, selected)

    def get_selected_device_ids(self) -> List[str]:
        return list(self._selected_ids)

    def update_devices(self, devices: List[AirPlayDevice]):
        """Refresh the device list from current state."""
        device_count = len(devices)

        # Only update scan button when scan actually finishes
        if device_count > 0 and self._is_scanning:
            self._is_scanning = False
            self._scan_btn.configure(text=S["scan"], state="normal")

        # Handle state where we have no devices yet but are scanning
        if device_count == 0 and not self._is_scanning:
            self._scan_btn.configure(text=S["scan"], state="normal")

        if device_count == 0:
            if not self._empty_visible:
                self._empty_label.pack(pady=30)
                self._empty_visible = True
            return

        # Hide empty label when devices appear
        if self._empty_visible:
            self._empty_label.pack_forget()
            self._empty_visible = False

        # Skip if device list hasn't changed (avoid unnecessary UI churn)
        current_ids = {d.identifier for d in devices}

        # Remove cards for devices no longer present
        for dev_id in list(self._cards.keys()):
            if dev_id not in current_ids:
                try:
                    self._cards[dev_id].pack_forget()
                    self._cards[dev_id].destroy()
                except Exception:
                    pass
                del self._cards[dev_id]
                self._selected_ids.discard(dev_id)

        # Update or create cards
        for device in devices:
            if device.identifier in self._cards:
                try:
                    self._cards[device.identifier].update_state(device)
                except Exception:
                    # Stale reference - recreate
                    del self._cards[device.identifier]
                    continue
            else:
                _LOGGER.info("Creating card for device: %s (%s)",
                             device.name, device.identifier)
                card = DeviceCard(
                    self._list_frame, device,
                    on_pair=self._on_pair,
                    on_select=self._on_device_select,
                    on_delay_change=self._on_delay_change,
                    delay_ms=self._device_delays.get(device.identifier, 0),
                )
                card.pack(fill="x", pady=4, padx=5)
                self._cards[device.identifier] = card

                # Auto-select the first HomePod / speaker (not a TV)
                name_lower = device.name.lower()
                is_tv = 'tv' in name_lower or 'apple tv' in name_lower
                if not is_tv and len(self._selected_ids) == 0:
                    card.set_selected(True)
                    self._selected_ids.add(device.identifier)

        self._last_device_count = device_count
