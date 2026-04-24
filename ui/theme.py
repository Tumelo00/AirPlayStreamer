"""UI theme constants and Turkish strings."""

# Colors - Dark modern theme
BG_DARK = "#1a1a2e"
BG_CARD = "#16213e"
BG_INPUT = "#0f3460"
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a0a0b0"
TEXT_MUTED = "#6c6c80"
SUCCESS = "#2ed573"
WARNING = "#ffa502"
ERROR = "#ff4757"
BORDER = "#2a2a4a"

# Status indicator colors
STATUS_COLORS = {
    "discovered": TEXT_SECONDARY,
    "pairing": WARNING,
    "paired": TEXT_SECONDARY,
    "connecting": WARNING,
    "connected": SUCCESS,
    "streaming": ACCENT,
    "disconnected": TEXT_MUTED,
    "error": ERROR,
}

# Turkish UI strings
S = {
    "app_title": "AirPlay Streamer",
    "app_subtitle": "Windows ses cikisini HomePod'a aktar",

    # Device panel
    "devices": "Cihazlar",
    "scan": "Cihazlari Tara",
    "scanning": "Taraniyor...",
    "pair": "Esle",
    "unpair": "Eslemeyi Kaldir",
    "no_devices": "Henuz cihaz bulunamadi.\nTarama yaparak baslayin.",

    # Device states
    "discovered": "Hazir",
    "pairing": "Eslestiriliyor...",
    "paired": "Eslesti",
    "connecting": "Baglaniyor...",
    "connected": "Baglandi",
    "streaming": "Yayin Yapiliyor",
    "disconnected": "Baglanti Kesildi",
    "error": "Hata",

    # Control panel
    "controls": "Kontroller",
    "start": "Yayina Basla",
    "stop": "Durdur",
    "volume": "Ses Seviyesi",

    # Status bar
    "status": "Durum",
    "status_idle": "Hazir",
    "status_scanning": "Cihazlar taraniyor...",
    "status_connecting": "Baglaniyor...",
    "status_streaming": "Yayin yapiliyor",
    "status_stopping": "Durduruluyor...",
    "status_error": "Hata",
    "latency": "Gecikme",
    "latency_value": "~1sn",
    "audio_level": "Ses Seviyesi",

    # Pairing dialog
    "pin_title": "Cihaz Eslestirme",
    "pin_prompt": "iPhone'unuzdaki Home uygulamasinda\ngoruntulenen 4 haneli PIN kodunu girin:",
    "pin_confirm": "Onayla",
    "pin_cancel": "Iptal",
    "pin_success": "Eslestirme basarili!",
    "pin_failed": "Eslestirme basarisiz.",

    # Settings
    "settings": "Ayarlar",
    "audio_device": "Ses Cihazi",
    "audio_device_default": "Varsayilan Cikis",
    "minimize_to_tray": "Kapatinca simge durumuna kucult",
    "auto_connect": "Baslarken otomatik baglan",
    "close": "Kapat",

    # Tray
    "tray_show": "Goster",
    "tray_start": "Yayina Basla",
    "tray_stop": "Durdur",
    "tray_exit": "Cikis",

    # Errors
    "no_device_selected": "Lutfen en az bir cihaz secin",
    "no_devices_found": "Cihaz bulunamadi",
    "connection_error": "Baglanti hatasi",
}
