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
