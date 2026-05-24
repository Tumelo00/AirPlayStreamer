# macOS Kurulum Rehberi

## 1. Ön Gereksinimler (Geliştirme için)

```bash
# Homebrew yoksa (https://brew.sh)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Node.js (Vite frontend build için)
brew install node

# Rust (Tauri için)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Xcode Command Line Tools (linker için)
xcode-select --install
```

**NOT:** `claude` CLI'yi şimdiden kurman gerekmez — Claude Lite uygulaması açıldığında otomatik kurulum sunar. İstersen önceden kurabilirsin:

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude login
```

## 2. Projeyi Çek

```bash
git clone https://github.com/tumelo00/airplaystreamer.git
cd airplaystreamer
git checkout claude/efficient-claude-desktop-alt-jxZig
cd claude-lite
```

## 3. Bağımlılıkları Kur

```bash
# Frontend
npm install

# Tauri CLI
cargo install tauri-cli --version "^2.0"
```

## 4. İkonları Oluştur

```bash
mkdir -p src-tauri/icons
curl -L -o /tmp/placeholder.png \
  https://github.com/tauri-apps/tauri/raw/dev/examples/api/src-tauri/icons/icon.png
npm run tauri icon /tmp/placeholder.png
```

(Sonra kendi logo'nu hazırlarsan tekrar `npm run tauri icon /path/to/logo.png` ile değiştirirsin.)

## 5. Dev Modunda Çalıştır

```bash
npm run tauri dev
```

İlk derleme **5-10 dakika** sürebilir (Rust bağımlılıkları). Sonraki çalıştırmalar saniyeler içinde.

## 6. İlk Açılış

Uygulama açıldığında ayarlar penceresi otomatik gelir:

### Senaryo A: Claude CLI kurulu değil
- Pencere "Claude CLI kurulu değil" der
- **"Otomatik Kur"** butonuna bas
- Arka planda `curl -fsSL https://claude.ai/install.sh | bash` çalışır
- Log'lar pencerede görünür
- ~30 saniye sonra "Kurulum tamamlandı" der

### Senaryo B: CLI kurulu ama login değil
- Pencere "Giriş gerekli" der
- **"Terminal'de Login Aç"** butonuna bas
- Yeni Terminal penceresi açılıp `claude login` çalıştırır
- Browser'da Claude.ai hesabınla onaylarsın
- Bu pencereye dön, **"Yenile"** bas

### Senaryo C: Her şey hazır
- "✓ Kurulu" ve "✓ Giriş yapılmış" yeşil
- Pencereyi kapat, chat'e başla

## 7. Release Build

Paketlenmiş .dmg ve .app:

```bash
npm run tauri build
```

Çıktı:
- `src-tauri/target/release/bundle/dmg/Claude Lite_0.1.0_aarch64.dmg`
- `src-tauri/target/release/bundle/macos/Claude Lite.app`

İmzalanmamış — ilk açışta sağ tık → Aç → Aç.

## Sık Karşılaşılan Sorunlar

### "linker `cc` not found"
```bash
xcode-select --install
```

### Tauri dev penceresi açılmıyor
```bash
lsof -i :1420
kill -9 <PID>
```

### Otomatik kurulum başarısız
Manuel kur:
```bash
curl -fsSL https://claude.ai/install.sh | bash
# PATH'i yenile
source ~/.zshrc
# Test et
claude --version
```

### Login sonrası "Giriş yapılmadı" diyor
- Terminal'i kapatma — `claude login` browser açar, onaylamayı bekler
- Onayladıktan sonra Terminal'de "Login successful" mesajını gör
- Sonra Claude Lite'da "Yenile" bas

### "subscription quota exceeded"
- Pro/Max kotanız dolmuş
- Bekle (saatlik/günlük yenilenir) veya hesabını upgrade et
- API key'e fallback yok (özellikle eklemedik — sen Pro/Max kullanıyorsun)
