# AirPlay Streamer

Windows sistem sesini AirPlay uzerinden HomePod'lara aktaran uygulama.

## Ozellikler

- Windows sistem sesini (WASAPI loopback) AirPlay 2 ile HomePod'lara aktarir
- Modern koyu temali Turkce UI (customtkinter)
- Otomatik cihaz kesfi (mDNS)
- Otomatik akilli ses cihazi secimi (fiziksel cihaz tercih edilir)
- Dusuk gecikme icin optimize edilmis ring buffer
- Eslestirme gerekmez - Home'da "Ayni Aga Baglililar" izni yeterli
- System tray destegi
- Ayarlar dialog'u ile ses cihazi secimi

## Ek Paket: Browser Extension

`extension/` klasorunde bulunan Opera/Chrome uzantisi YouTube, Twitch, Zoom gibi
DRM'siz sitelerde video'yu AirPlay ses gecikmesiyle (yaklasik 1.5sn) senkronize eder.
Netflix gibi DRM korumali sitelerde calismaz (tarayici kisitlamasi).

## Kurulum

### Python ile
```bash
pip install -r requirements.txt
python main.py
```

### EXE build
```bash
pyinstaller --noconfirm --onedir --windowed \
    --name "AirPlayStreamer" --icon "assets/icon.ico" \
    --add-data "<customtkinter_path>;customtkinter/" \
    --collect-all pyatv --collect-all zeroconf --collect-all numpy --collect-all miniaudio \
    --hidden-import pyaudiowpatch --hidden-import pystray --hidden-import PIL \
    main.py
```

### Extension
1. Opera'da `opera://extensions` ac
2. "Gelistirici modu" ac
3. "Paketlenmemis yukle" -> `extension/` klasorunu sec

## Mimari

```
WASAPI Loopback -> Ring Buffer -> LiveAudioSource -> pyatv RAOP -> HomePod
```

- `core/ring_buffer.py` - Thread-safe broadcast ring buffer (multi-reader)
- `core/audio_capture.py` - PyAudioWPatch loopback capture + resampling
- `core/audio_source.py` - pyatv AudioSource subclass for live PCM
- `core/device_manager.py` - AirPlay device discovery/pairing/connection
- `core/streamer.py` - Asyncio orchestrator in daemon thread
- `ui/` - customtkinter UI components

## Teknik Notlar

- pyatv'nin internal `RaopStream` API'si kullanilir (FacadeStream.instances uzerinden)
- `context.latency = 4410` ile (~0.1sn) minimum gecikmeye ayarlanmistir
- Ring buffer 50ms (ultra-low latency)
- HomePod stereo pair icin sadece BIR cihaza stream at, digeri otomatik senkron calar

## Lisans

Kisisel kullanim.
