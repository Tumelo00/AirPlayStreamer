# Claude Lite

Hafif, hızlı, verimli bir Claude masaüstü istemcisi. Resmi Claude Desktop'un sunduğu özellikleri (dosya sürükle-bırak, görsel ekleme, önizleme, streaming chat) **çok daha düşük RAM/CPU** ile sağlar.

**API key gerekmez** — senin Mac'inde kurulu olan `claude` CLI'sini arka planda kullanır, böylece Pro/Max aboneliğin üzerinden çalışır. CLI kurulu değilse Claude Lite tek tıkla otomatik kurar.

## Hedefler

| Metrik | Resmi Claude Desktop | Claude Lite (hedef) |
|---|---|---|
| RAM (idle) | 250-400 MB | 40-80 MB |
| RAM (aktif) | 600 MB-1.5 GB | 120-200 MB |
| Binary boyutu | ~200 MB | ~30 MB |
| Açılış süresi | 3-5 sn | <2 sn |
| Auth | API key veya OAuth | `claude` CLI (Pro/Max abonelik) |

## Mimari

```
┌─────────────────────────────┐
│  Claude Lite (Tauri + React)│
│  ┌───────────────────────┐  │
│  │  React UI (chat/dosya)│  │
│  └──────────┬────────────┘  │
│             │ Tauri IPC      │
│  ┌──────────▼────────────┐  │
│  │  Rust backend         │  │
│  │  - subprocess wrapper │  │
│  │  - SQLite (geçmiş)    │  │
│  │  - dosya okuma        │  │
│  └──────────┬────────────┘  │
└─────────────┼───────────────┘
              │ spawn
              ▼
       ┌──────────────┐
       │  claude CLI  │  ← Anthropic resmi native binary
       │  (Pro/Max)   │
       └──────┬───────┘
              │ OAuth (kullanıcı bir kere login)
              ▼
       Anthropic backend
```

Biz OAuth flow yapmıyoruz, Claude CLI'nin kendi auth'una güveniyoruz. Bu hem **ToS uyumlu** (Anthropic'in Şubat 2026 OAuth yasağına takılmaz) hem de **Pro/Max kotandan** gider (ekstra ücret yok).

## Teknoloji Stack

- **Tauri 2** — Rust + sistem WebView (Electron'un aksine Chromium bundle etmez)
- **React 18 + TypeScript** — UI
- **Tailwind CSS** — styling
- **Vite** — frontend build
- **rusqlite** — lokal konuşma geçmişi
- **tokio** — async subprocess + I/O

## Özellikler (MVP)

- [x] Tauri 2 + React iskeleti
- [x] Claude CLI subprocess wrapper (streaming JSON)
- [x] Otomatik CLI kurulum (`curl install.sh`)
- [x] Login akışı (Terminal'de `claude login` aç)
- [x] Model seçimi (Opus 4.7, Sonnet 4.6, Haiku 4.5)
- [x] Dosya sürükle-bırak (Tauri native drag-drop event)
- [x] Görsel ekleme (görsel path CLI'ye geçer)
- [x] Markdown render + kod syntax highlight
- [x] SQLite ile lokal konuşma geçmişi
- [x] Conversation continuity (`--session-id`)
- [ ] Dosya önizleme paneli (PDF, kod, görsel)
- [ ] Konuşma geçmişi sidebar UI'si
- [ ] Sistem tray + Cmd+Shift+Space global hotkey
- [ ] Terminal modu (xterm.js + pty wrapper)
- [ ] MCP server desteği

## Hızlı Başlangıç

`SETUP_MACOS.md` dosyasına bak — adım adım kurulum var.

Özetle:

```bash
# 1. Bağımlılıkları kur
npm install
cargo install tauri-cli --version "^2.0"

# 2. Dev modunda aç
npm run tauri dev
```

İlk açılışta uygulama Claude CLI durumunu kontrol eder:
- CLI yoksa → tek tıkla otomatik kurulum
- CLI varsa ama login değilsen → "Login Aç" butonu Terminal'de `claude login` açar
- Her şey hazırsa → direkt chat'e başla

## Lisans

MIT
