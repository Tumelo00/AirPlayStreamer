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

### A) Hazır .DMG indir (önerilen)

1. GitHub Actions sayfasına git → **Build Claude Lite (macOS)** workflow → en son başarılı run
2. Sayfanın altındaki **Artifacts** bölümünden `.dmg` indir:
   - **Apple Silicon (M1/M2/M3/M4, Tahoe dahil tüm yeni Mac'ler)**: `claude-lite-aarch64-apple-darwin-dmg`
   - **Intel Mac (eski, Sequoia ve öncesi)**: manuel `workflow_dispatch` ile `x86_64-apple-darwin` tetikle
3. ZIP'i aç → içindeki `.dmg`'ye çift tıkla
4. Açılan pencerede **Claude Lite** ikonunu **Applications** klasörüne sürükle
5. **Applications'tan uygulamayı çift tıkla** → ilk açılış engellenir (imzasız)

### macOS Tahoe (26) / Sequoia (15) için ilk açılış

Apple, Tahoe ile birlikte **"sağ tık → Aç" yöntemini kaldırdı**. Yeni akış:

1. Uygulamayı normal şekilde **çift tıkla** → "Apple bu uygulamayı doğrulayamıyor" hatası alırsın → **Bitti** de
2. **System Settings** aç → **Privacy & Security**
3. En alta scroll et → "Claude Lite engellendi çünkü ..." mesajını gör → yanındaki **"Open Anyway"** (Yine de Aç) butonuna bas
4. Admin şifreni gir
5. Çıkan dialog'da **Open Anyway** de
6. Bu noktadan sonra uygulama her zaman açılır

> Bu engeli kalıcı çözmek için Apple Developer hesabı + code signing/notarization gerek ($99/yıl). Şu an unsigned dağıtıyoruz; ev kullanımı için yeterli.

### macOS Big Sur (11) → Sonoma (14) için

1. Applications'ta uygulamayı bul → **sağ tık → Aç** → çıkan diyalogda yine **Aç**
2. Eski yöntem hala çalışır (Sequoia/Tahoe'de değil)

### Açıldıktan sonra

İlk açılışta uygulama bir Ayarlar penceresi açar:
- **Claude CLI yoksa** → "Otomatik Kur" butonu (`curl install.sh` arka planda çalışır, ~100MB native binary indirir)
- **CLI var ama login değilsen** → "Terminal'de Login Aç" → Terminal açılır + `claude` çalıştırılır + browser'da Claude.ai hesabınla onayla
  - **İlk seferde**: macOS "Claude Lite, Terminal'i kontrol etmek istiyor" der → **OK** de (Info.plist'te `NSAppleEventsUsageDescription` ile açıklandı)
- Her şey hazır → kapat, chat'e başla

### Release (kalıcı download link) olarak yayınla

```bash
git tag claude-lite-v0.1.0
git push --tags
```
CI workflow tag'i görünce **GitHub Release** oluşturur — herkes link üzerinden indirebilir.

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
