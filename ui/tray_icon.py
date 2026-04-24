"""System tray icon integration using pystray."""

import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def _create_icon_image(size=64) -> Image.Image:
    """Create a simple AirPlay-style icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # AirPlay triangle icon
    center_x, center_y = size // 2, size // 2 + 4
    tri_size = size // 3
    points = [
        (center_x, center_y - tri_size),
        (center_x - tri_size, center_y + tri_size // 2),
        (center_x + tri_size, center_y + tri_size // 2),
    ]
    draw.polygon(points, fill=(233, 69, 96, 255))

    # WiFi-like arcs
    for r in [size // 2 - 4, size // 2 - 10]:
        bbox = [center_x - r, center_y - r - 10, center_x + r, center_y + r - 10]
        draw.arc(bbox, 200, 340, fill=(255, 255, 255, 200), width=2)

    return img


class TrayIcon:
    """System tray icon with basic controls."""

    def __init__(self, on_show: Callable, on_toggle: Callable,
                 on_exit: Callable):
        self._on_show = on_show
        self._on_toggle = on_toggle
        self._on_exit = on_exit
        self._icon: Optional["pystray.Icon"] = None
        self._is_streaming = False

    def start(self):
        if not PYSTRAY_AVAILABLE:
            return

        icon_image = _create_icon_image()

        menu = pystray.Menu(
            pystray.MenuItem("AirPlay Streamer", self._on_show_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "Durdur" if self._is_streaming else "Yayina Basla",
                self._on_toggle_click,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Cikis", self._on_exit_click),
        )

        self._icon = pystray.Icon("AirPlayStreamer", icon_image, "AirPlay Streamer", menu)

        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def stop(self):
        if self._icon:
            self._icon.stop()
            self._icon = None

    def set_streaming(self, streaming: bool):
        self._is_streaming = streaming
        if self._icon:
            self._icon.update_menu()

    def _on_show_click(self, icon=None, item=None):
        self._on_show()

    def _on_toggle_click(self, icon=None, item=None):
        self._on_toggle()

    def _on_exit_click(self, icon=None, item=None):
        self._on_exit()
