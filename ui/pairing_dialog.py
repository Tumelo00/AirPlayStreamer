"""PIN entry dialog for AirPlay device pairing."""

import customtkinter as ctk
from typing import Callable, Optional

from ui.theme import *


class PairingDialog(ctk.CTkToplevel):
    """Modal dialog for entering the 4-digit pairing PIN."""

    def __init__(self, master, device_name: str,
                 on_confirm: Callable[[str], None],
                 on_cancel: Optional[Callable] = None):
        super().__init__(master)
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._result: Optional[str] = None

        self.title(S["pin_title"])
        self.geometry("360x240")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)

        # Center on parent
        self.transient(master)
        self.grab_set()

        # Device name
        ctk.CTkLabel(
            self, text=device_name,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(25, 5))

        # Prompt
        ctk.CTkLabel(
            self, text=S["pin_prompt"],
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(0, 15))

        # PIN entry
        self._pin_entry = ctk.CTkEntry(
            self, width=160, height=45,
            font=ctk.CTkFont(size=24, weight="bold"),
            justify="center",
            fg_color=BG_INPUT, border_color=ACCENT,
            text_color=TEXT_PRIMARY,
            placeholder_text="0000",
        )
        self._pin_entry.pack(pady=(0, 20))
        self._pin_entry.focus_set()
        self._pin_entry.bind("<Return>", lambda e: self._confirm())

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30)

        ctk.CTkButton(
            btn_frame, text=S["pin_cancel"], width=120, height=36,
            fg_color=BG_INPUT, hover_color=BORDER,
            text_color=TEXT_SECONDARY,
            command=self._cancel,
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            btn_frame, text=S["pin_confirm"], width=120, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._confirm,
        ).pack(side="right", expand=True, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        pin = self._pin_entry.get().strip()
        if pin and len(pin) == 4 and pin.isdigit():
            self._result = pin
            self._on_confirm(pin)
            self.destroy()

    def _cancel(self):
        if self._on_cancel:
            self._on_cancel()
        self.destroy()
