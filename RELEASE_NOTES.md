# Surum Notlari

## v1.1.0

- **VPN/Tailscale RTSP 400 fix**: VPN acikken AirPlay trafigi fiziksel
  LAN arayuzune zorla yonlendiriliyor. Onceden VPN aktifken HomePod
  baglantiyi reddediyordu (RTSP 400 Bad Request).
- **Latency profilleri**: Ultra Dusuk (~100ms), Dusuk (~250ms),
  Dengeli (~500ms), Kararli (~1500ms). Ayarlar'dan secilir.
- **Reconnect / recovery**: baglanti koparsa exponential backoff ile
  otomatik yeniden baglanir, yayin devam eder.
- **soxr resampler**: yuksek kaliteli ornek hizi donusumu (yoksa
  numpy linear fallback, crash etmez).
- **Diagnostics paneli**: canli ag/ses/yayin durumu, "Loglari Ac"
  butonu.
- pyatv internal API'leri `airplay_backend.py` icinde izole edildi.

## v1.0.0

- Ilk surum: Windows sistem sesini AirPlay 2 ile HomePod'a aktarir.
