import { useEffect, useRef, useState } from "react";
import {
  checkClaudeCli,
  installClaudeCli,
  openClaudeLogin,
  type CliStatus,
} from "@/lib/claude";

interface Props {
  onClose: () => void;
}

export function Settings({ onClose }: Props) {
  const [status, setStatus] = useState<CliStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [installLog, setInstallLog] = useState<string[]>([]);
  const logBoxRef = useRef<HTMLDivElement>(null);

  const refresh = async () => {
    setChecking(true);
    try {
      const s = await checkClaudeCli();
      setStatus(s);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }
  }, [installLog]);

  const handleInstall = async () => {
    setInstalling(true);
    setInstallLog([]);
    try {
      await installClaudeCli((line) => {
        setInstallLog((prev) => [...prev, line]);
      });
      await refresh();
    } catch (e) {
      setInstallLog((prev) => [...prev, `HATA: ${e}`]);
    } finally {
      setInstalling(false);
    }
  };

  const handleLogin = async () => {
    try {
      await openClaudeLogin();
      setTimeout(refresh, 4000);
    } catch (e) {
      alert(`Login başlatılamadı: ${e}`);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 w-[560px] max-w-[90vw] max-h-[85vh] overflow-y-auto scrollbar-thin">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Bağlantı</h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-zinc-400">
            Claude Lite, Mac'inde kurulu olan{" "}
            <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              claude
            </code>{" "}
            CLI'sini arka planda kullanır. API key gerekmez — Claude Pro/Max aboneliğin üzerinden çalışır.
          </p>

          {checking && !status && (
            <div className="text-sm text-zinc-400">Kontrol ediliyor…</div>
          )}

          {status && (
            <div className="space-y-3">
              <Row
                label="Claude CLI"
                value={
                  status.installed ? (
                    <span className="text-green-400">
                      ✓ Kurulu {status.version && `(${status.version})`}
                    </span>
                  ) : (
                    <span className="text-red-400">✗ Kurulu değil</span>
                  )
                }
              />
              {status.path && (
                <Row
                  label="Yol"
                  value={
                    <code className="text-xs bg-zinc-800 px-1.5 py-0.5 rounded">
                      {status.path}
                    </code>
                  }
                />
              )}
              <Row
                label="Giriş"
                value={
                  status.loggedIn ? (
                    <span className="text-green-400">✓ Giriş yapılmış</span>
                  ) : (
                    <span className="text-amber-400">⚠ Giriş gerekli</span>
                  )
                }
              />

              {!status.installed && !installing && (
                <div className="bg-amber-950/30 border border-amber-900/50 rounded p-3 text-xs text-amber-200 space-y-2">
                  <p className="font-semibold">Claude CLI kurulu değil.</p>
                  <p className="text-amber-200/80">
                    Resmi native installer'ı (Node.js gerekmez, ~100MB,
                    auto-update'li) tek tıkla kurabilirim:
                  </p>
                  <button
                    onClick={handleInstall}
                    className="bg-amber-600 hover:bg-amber-500 text-white rounded px-3 py-1.5 text-xs font-medium"
                  >
                    Otomatik Kur
                  </button>
                  <p className="text-amber-200/60 text-[10px] mt-1">
                    Kurulum komutu:{" "}
                    <code>curl -fsSL https://claude.ai/install.sh | bash</code>
                  </p>
                </div>
              )}

              {installing && (
                <div className="bg-zinc-950 border border-zinc-800 rounded p-3 space-y-2">
                  <p className="text-xs text-zinc-400">Kuruluyor…</p>
                  <div
                    ref={logBoxRef}
                    className="bg-black/40 rounded p-2 max-h-40 overflow-y-auto scrollbar-thin font-mono text-[10px] text-zinc-300 space-y-0.5"
                  >
                    {installLog.length === 0 && (
                      <div className="text-zinc-600">Başlatılıyor…</div>
                    )}
                    {installLog.map((l, i) => (
                      <div key={i}>{l}</div>
                    ))}
                  </div>
                </div>
              )}

              {!installing && installLog.length > 0 && (
                <div className="bg-zinc-950 border border-zinc-800 rounded p-3">
                  <details>
                    <summary className="text-xs text-zinc-400 cursor-pointer">
                      Son kurulum log'u ({installLog.length} satır)
                    </summary>
                    <div className="bg-black/40 rounded p-2 mt-2 max-h-40 overflow-y-auto scrollbar-thin font-mono text-[10px] text-zinc-300 space-y-0.5">
                      {installLog.map((l, i) => (
                        <div key={i}>{l}</div>
                      ))}
                    </div>
                  </details>
                </div>
              )}

              {status.installed && !status.loggedIn && !installing && (
                <div className="bg-amber-950/30 border border-amber-900/50 rounded p-3 text-xs text-amber-200">
                  <p>Henüz Claude hesabına giriş yapmadın.</p>
                  <button
                    onClick={handleLogin}
                    className="mt-2 bg-amber-600 hover:bg-amber-500 text-white rounded px-3 py-1.5 text-xs font-medium"
                  >
                    Terminal'de Login Aç
                  </button>
                  <p className="mt-2 text-amber-200/70 text-[10px]">
                    Terminal açılacak, Claude.ai hesabınla giriş yapacaksın.
                    Sonra bu pencereye dön ve "Yenile"ye bas.
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={refresh}
              disabled={checking || installing}
              className="px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 disabled:text-zinc-600"
            >
              Yenile
            </button>
            <button
              onClick={onClose}
              disabled={installing}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 text-white rounded px-4 py-1.5 text-sm"
            >
              Kapat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-zinc-400">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}
