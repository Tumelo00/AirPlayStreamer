"""Screen capture video delay using DXGI.
Uses ultra-fast show/hide cycle (2ms hidden per frame) to minimize flicker.
"""

import ctypes
import logging
import threading
import time
from collections import deque

_LOGGER = logging.getLogger(__name__)

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
HWND_TOPMOST = -1
SWP_NOMOVE = 0x2
SWP_NOSIZE = 0x1
SWP_NOACTIVATE = 0x10


class VideoDelay:
    def __init__(self, delay_ms=1500, fps=20):
        self.delay_ms = delay_ms
        self.fps = fps
        self._running = False
        self._thread = None

    @property
    def is_running(self):
        return self._running

    def start(self, region=None):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set_delay(self, delay_ms):
        self.delay_ms = delay_ms

    def _run(self):
        import tkinter as tk
        from PIL import Image, ImageTk
        import dxcam

        root = tk.Tk()
        root.overrideredirect(True)
        root.configure(bg='black')
        root.bind('<Escape>', lambda e: _close())

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{sw}x{sh}+0+0")
        root.attributes('-topmost', True)

        label = tk.Label(root, bg='black', bd=0)
        label.pack(fill='both', expand=True)

        def _close():
            self._running = False
            try:
                root.destroy()
            except:
                pass

        root.protocol("WM_DELETE_WINDOW", _close)
        root.update_idletasks()

        hwnd = user32.GetParent(root.winfo_id())
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE,
                                 ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)

        # Phase 1: CAPTURE (overlay hidden)
        root.attributes('-alpha', 0.0)

        cam = dxcam.create(output_color="BGR")
        buf = deque(maxlen=int(3 * self.fps))
        photo = [None]
        ms = int(1000 / self.fps)

        # Pre-fill buffer while overlay is invisible
        fill_count = int((self.delay_ms / 1000) * self.fps) + 5

        def fill_buffer():
            if not self._running:
                _close()
                return

            frame = cam.grab()
            if frame is not None:
                img = Image.fromarray(frame[:, :, ::-1])
                buf.append((time.monotonic(), img))

            if len(buf) < fill_count:
                root.after(ms, fill_buffer)
            else:
                # Buffer full - start display phase
                root.attributes('-alpha', 1.0)
                root.attributes('-topmost', True)
                root.after(10, display_loop)

        def display_loop():
            if not self._running:
                _close()
                return

            now = time.monotonic()

            try:
                # Ultra-fast: hide → grab → show (2ms hidden)
                user32.SetLayeredWindowAttributes(hwnd, 0, 0, 2)  # alpha=0
                frame = cam.grab()
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, 2)  # alpha=255

                if frame is not None:
                    img = Image.fromarray(frame[:, :, ::-1])
                    buf.append((now, img))

                # Find delayed frame
                target = now - self.delay_ms / 1000
                found = None
                for t, f in buf:
                    if t <= target:
                        found = f

                if found:
                    if found.size != (sw, sh):
                        found = found.resize((sw, sh), Image.NEAREST)
                    photo[0] = ImageTk.PhotoImage(found, master=root)
                    label.configure(image=photo[0])

            except Exception as e:
                _LOGGER.debug("display error: %s", e)

            root.after(ms, display_loop)

        root.after(200, fill_buffer)
        root.mainloop()
        del cam
        self._running = False
