# Tailscale Acik Canli Test

VPN/Tailscale acikken AirPlay'in calistigini dogrulamak icin:

1. **Tailscale'i ac** (sistem tepsisinden baglan, `100.x` IP alindigini gor).
2. **Uygulamayi baslat** (`AirPlayStreamer.exe`).
3. Cihazlar taransin, bir HomePod sec, **Yayina Basla**.
4. Diagnostics panelini ac (header'daki ≡ butonu).

## Diagnostics'te bakilacaklar

| Alan | Beklenen deger |
|------|----------------|
| Ag Arayuzu | Fiziksel kart ( or. "Realtek Gaming 2.5GbE"), Tailscale DEGIL |
| Yerel IP | `192.168.x.x` (LAN), `100.x` OLMAMALI |
| HomePod IP | `192.168.x.x` |
| Yayin Durumu | `streaming` |
| Son Hata | `-` |

**Yerel IP `100.x` cikiyorsa fix calismiyor demektir.**

## RTSP 400 alirsan

Loglari Ac butonuyla `streamer.log` ac, su satirlari gonder:
- `core.network: Route: target=... -> local=... iface=...`
- `core.network: pyatv http_connect patched in N modules`
- `Stream error for ...` ve altindaki traceback
- `RTSP/1.0 method SETUP failed with code 400`

Bu satirlar hangi interface'in secildigini ve neden reddedildigini gosterir.
