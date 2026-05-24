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

## Özellikler

**Çekirdek:**
- [x] Tauri 2 + React iskeleti (lazy chunks, ErrorBoundary)
- [x] Claude CLI subprocess wrapper (streaming, abort destekli)
- [x] Otomatik native CLI kurulum (`curl install.sh`)
- [x] Login akışı (Terminal'de `claude login` aç)
- [x] Model seçimi (Opus 4.7, Sonnet 4.6, Haiku 4.5)
- [x] Token usage göstergesi (header'da ↑/↓)

**Mesajlaşma:**
- [x] Streaming chat, **Durdur** butonu (process abort)
- [x] Markdown + GitHub-flavored + syntax highlight
- [x] Sticky-bottom otomatik scroll
- [x] Memoize'li MessageBubble (büyük chat'lerde akıcı)
- [x] Conversation continuity (`--session-id`)
- [x] Otomatik başlık (ilk mesajdan)

**Dosyalar:**
- [x] Dosya sürükle-bırak (Tauri native drag-drop)
- [x] Görsel **kopyala-yapıştır** (clipboard image → tmp file → vision)
- [x] Dosya önizleme paneli (görsel + 20+ dil kod + PDF iframe)

**Konuşma yönetimi:**
- [x] SQLite ile lokal geçmiş
- [x] Sidebar (daralt/genişlet, ara, seç, sil, **çift tık ile yeniden adlandır**)

**OS entegrasyonu:**
- [x] Sistem tray (Göster/Gizle/Yeni/Çıkış)
- [x] Cmd+Shift+Space global hotkey (toggle)
- [x] Klavye kısayolları: ⌘N yeni · ⌘T terminal · ⌘, ayarlar
- [x] Pencere durumu hatırlama (boyut/pozisyon)
- [x] Otomatik yeniden boyutlanan textarea

**Terminal:**
- [x] Tam pty wrapper (`portable-pty` + `@xterm/xterm`)
- [x] Lazy loaded (chat startup'ı yavaşlatmaz)
- [x] Chat/Terminal tab switcher
- [x] Mode geçişlerinde session korunur

**Yapılandırma:**
- [x] MCP server listesi UI (Settings → MCP)
- [x] Konuşma export (markdown, sidebar ↓ butonu)
- [x] Custom system prompt UI (header'da · prompt butonu, per-sohbet)
- [x] Varsayılan sistem promptu (Settings → Genel)
- [x] Workspace selector (Settings → Genel → çalışma dizini, claude + terminal cwd)
- [x] Tema toggle (koyu/açık)
- [x] Son konuşmayı geri yükle (açılışta)

**Hafıza Sistemi:**
- [x] **Hafıza Modu** (opt-in, per-sohbet, default KAPALI, persist edilmez):
  - Header'da 🧠 toggle butonu — AÇIK iken sarı uyarı şeridi gösterir
  - Her mesaj kartının altında 📌 buton — tıklayınca o mesajı
    `memory.md`'ye sabitler (tarih + rol + sohbet başlığı ile)
  - Yeni sohbet açınca veya app restart sonrası **otomatik KAPALI** —
    yanlışlıkla açık kalmaz
  - ⌘M klavye kısayolu
- [x] Kullanıcı hafızası — `~/Library/Application Support/com.claudelite.app/memory.md`
  her sohbete otomatik prepend; 32KB cap, FIFO eviction (Settings → Hafıza)
- [x] Workspace CLAUDE.md — workspace'teki notları oku/düzenle/kaydet
- [x] Claude CLI cwd workspace'e set → CLAUDE.md zaten doğal olarak yüklenir
- [x] Attachment preview'i DB'ye yazılmıyor (RAM/disk tasarrufu)

**Backlog:**
- [ ] Çoklu terminal sekmeleri
- [ ] Conversation pinning
- [ ] Cmd+K hızlı arama
- [ ] Conversation summarization (uzun sohbetler için)

## Kurulum (Son Kullanıcı)

İki seçenek var:

### A) Hazır .DMG indir (önerilen)

1. GitHub Actions sayfasına git → **Build Claude Lite (macOS)** workflow → en son başarılı run
2. Sayfanın altındaki **Artifacts** bölümünden `claude-lite-aarch64-apple-darwin-dmg` indir (Apple Silicon Mac için; Intel Mac için x86_64 build manuel tetiklenmeli)
3. ZIP'i aç → içindeki `.dmg`'ye çift tıkla
4. Açılan pencerede **Claude Lite** ikonunu **Applications** klasörüne sürükle
5. İlk açışta macOS imzasız uygulamayı engeller → Applications'tan **sağ tık → Aç → tekrar Aç**
6. Uygulama açıldığında otomatik olarak Claude CLI kurulumunu önerir (tek tıkla); sonra Claude hesabınla giriş yap

> **Release** olarak çıkarmak için: `git tag claude-lite-v0.1.0 && git push --tags` — workflow otomatik GitHub Release oluşturur, kalıcı indirme linki olur.

### B) Kendin derle (geliştirici)

`SETUP_MACOS.md` dosyasına bak — adım adım kurulum var. Özetle:

```bash
cd claude-lite
npm install
npm run tauri dev   # geliştirme
npm run tauri build # üretim .dmg
```

## İlk Açılış Akışı

Uygulama Claude CLI durumunu kontrol eder:
- CLI yoksa → tek tıkla otomatik kurulum (`curl install.sh`)
- CLI varsa ama login değilsen → "Login Aç" Terminal'de `claude login` açar
- Her şey hazırsa → direkt chat'e başla

## Lisans

MIT
