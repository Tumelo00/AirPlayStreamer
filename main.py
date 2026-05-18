"""AirPlay Streamer - Windows sistem sesini HomePod'a aktar.

Entry point: asyncio event loop'u arka plan thread'inde calistirarak
customtkinter UI ile birlikte calismasini saglar.
"""

import logging
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Config
from core.network import patch_pyatv_connection
from core.streamer import Streamer
from ui.app import AirPlayStreamerApp

# Holds the single-instance mutex for the process lifetime
_SINGLE_INSTANCE_MUTEX = []


def ensure_single_instance() -> bool:
    """Return True if this is the only instance.

    If another instance is already running, brings its window to the
    front and returns False so the caller can exit.
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        mutex = kernel32.CreateMutexW(None, False, "AirPlayStreamerSingleInstance")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "AirPlay Streamer")
            if hwnd:
                user32.ShowWindow(hwnd, 9)        # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            return False
        _SINGLE_INSTANCE_MUTEX.append(mutex)  # keep handle alive
        return True
    except Exception:
        return True  # never block startup on this check


def setup_logging():
    log_dir = os.path.join(os.environ.get("APPDATA", ""), "AirPlayStreamer")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "streamer.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce noise from libraries
    logging.getLogger("pyatv").setLevel(logging.WARNING)
    logging.getLogger("zeroconf").setLevel(logging.WARNING)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    # Single instance: if already running, focus it and exit
    if not ensure_single_instance():
        logger.info("Already running, focusing existing window.")
        return

    logger.info("AirPlay Streamer starting...")

    # Force AirPlay connections onto the physical LAN interface.
    # Without this, an active VPN (Tailscale etc.) makes pyatv report a
    # non-LAN source IP and HomePods reject the session (RTSP 400).
    patch_pyatv_connection()

    config = Config()
    streamer = Streamer()
    streamer.start()

    try:
        app = AirPlayStreamerApp(streamer, config)
        app.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception("Fatal error: %s", e)
    finally:
        streamer.shutdown()
        logger.info("AirPlay Streamer stopped.")


if __name__ == "__main__":
    main()
