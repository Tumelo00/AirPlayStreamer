import { useEffect, useRef, useState } from "react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import {
  checkClaudeCli,
  installClaudeCli,
  listMcpServers,
  openClaudeLogin,
  type CliStatus,
  type McpServer,
} from "@/lib/claude";
import type { Preferences } from "@/lib/preferences";
import { MODELS } from "@/lib/types";

interface Props {
  prefs: Preferences;
  onPrefsChange: (p: Preferences) => void;
  onClose: () => void;
}

type Tab = "connection" | "general" | "mcp";

export function Settings({ prefs, onPrefsChange, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("connection");
  const [status, setStatus] = useState<CliStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [installLog, setInstallLog] = useState<string[]>([]);
  const [mcpServers, setMcpServers] = useState<McpServer[] | null>(null);
  const [mcpLoading, setMcpLoading] = useState(false);
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

  const refreshMcp = async () => {
    setMcpLoading(true);
    try {
      const list = await listMcpServers();
      setMcpServers(list);
    } catch {
      setMcpServers([]);
    } finally {
      setMcpLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (tab === "mcp" && mcpServers === null && status?.installed && status.loggedIn) {
      refreshMcp();
    }
  }, [tab, mcpServers, status]);

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

  const updatePref = <K extends keyof Preferences>(key: K, value: Preferences[K]) => {
    onPrefsChange({ ...prefs, [key]: value });
  };

  const pickWorkspaceDir = async () => {
    const selected = await openDialog({
      directory: true,
      multiple: false,
      title: "Çalışma dizini seç",
    });
    if (typeof selected === "string") {
      updatePref("workspaceDir", selected);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg w-[600px] max-w-[92vw] max-h-[88vh] flex flex-col overflow-hidden">
        <div className="flex justify-between items-center px-5 py-3 border-b border-zinc-800/60">
          <h2 className="text-base font-semibold">Ayarlar</h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex border-b border-zinc-800/60 bg-zinc-950/40 px-2">
          {(
            [
              ["connection", "Bağlantı"],
              ["general", "Genel"],
              ["mcp", "MCP"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`text-xs px-3 py-2 border-b-2 -mb-px ${
                tab === id
                  ? "border-blue-500 text-zinc-100"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-4">
          {tab === "connection" && (
            <ConnectionTab
              status={status}
              checking={checking}
              installing={installing}
              installLog={installLog}
              logBoxRef={logBoxRef}
              onInstall={handleInstall}
              onLogin={handleLogin}
              onRefresh={refresh}
            />
          )}

          {tab === "general" && (
            <GeneralTab
              prefs={prefs}
              onUpdate={updatePref}
              onPickWorkspace={pickWorkspaceDir}
            />
          )}

          {tab === "mcp" && (
            <McpTab
              loading={mcpLoading}
              servers={mcpServers}
              ready={!!status?.installed && !!status?.loggedIn}
              onRefresh={refreshMcp}
            />
          )}
        </div>

        <div className="flex justify-end gap-2 px-5 py-3 border-t border-zinc-800/60">
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
  );
}

function ConnectionTab({
  status,
  checking,
  installing,
  installLog,
  logBoxRef,
  onInstall,
  onLogin,
  onRefresh,
}: {
  status: CliStatus | null;
  checking: boolean;
  installing: boolean;
  installLog: string[];
  logBoxRef: React.RefObject<HTMLDivElement>;
  onInstall: () => void;
  onLogin: () => void;
  onRefresh: () => void;
}) {
  return (
    <>
      <p className="text-sm text-zinc-400">
        Claude Lite, Mac'inde kurulu olan{" "}
        <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-xs">claude</code>{" "}
        CLI'sini arka planda kullanır. API key gerekmez — Claude Pro/Max
        aboneliğin üzerinden çalışır.
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
                onClick={onInstall}
                className="bg-amber-600 hover:bg-amber-500 text-white rounded px-3 py-1.5 text-xs font-medium"
              >
                Otomatik Kur
              </button>
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

          {status.installed && !status.loggedIn && !installing && (
            <div className="bg-amber-950/30 border border-amber-900/50 rounded p-3 text-xs text-amber-200">
              <p>Henüz Claude hesabına giriş yapmadın.</p>
              <button
                onClick={onLogin}
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

          <button
            onClick={onRefresh}
            disabled={checking || installing}
            className="text-xs text-zinc-500 hover:text-zinc-200 disabled:text-zinc-700"
          >
            Yenile
          </button>
        </div>
      )}
    </>
  );
}

function GeneralTab({
  prefs,
  onUpdate,
  onPickWorkspace,
}: {
  prefs: Preferences;
  onUpdate: <K extends keyof Preferences>(key: K, value: Preferences[K]) => void;
  onPickWorkspace: () => void;
}) {
  return (
    <div className="space-y-5">
      <Field
        label="Varsayılan model"
        hint="Yeni sohbetler bu modelle başlar"
      >
        <select
          value={prefs.defaultModel}
          onChange={(e) => onUpdate("defaultModel", e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500"
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </Field>

      <Field
        label="Varsayılan sistem promptu"
        hint="Her yeni sohbete otomatik eklenir"
      >
        <textarea
          value={prefs.defaultSystemPrompt ?? ""}
          onChange={(e) =>
            onUpdate("defaultSystemPrompt", e.target.value || undefined)
          }
          rows={3}
          placeholder="Boş bırakırsan eklenmez"
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm resize-y min-h-[80px] focus:outline-none focus:border-blue-500 scrollbar-thin"
        />
      </Field>

      <Field
        label="Çalışma dizini"
        hint="Claude CLI bu dizinde çalışır (dosya erişimi, terminal cwd)"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={prefs.workspaceDir ?? ""}
            onChange={(e) =>
              onUpdate("workspaceDir", e.target.value || undefined)
            }
            placeholder="(varsayılan: home)"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={onPickWorkspace}
            className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded px-3 py-1.5 text-xs"
          >
            Seç…
          </button>
        </div>
      </Field>

      <Field label="Tema" hint="Görsel tema (yeniden başlatma gerekebilir)">
        <select
          value={prefs.theme}
          onChange={(e) => onUpdate("theme", e.target.value as "dark" | "light")}
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="dark">Koyu</option>
          <option value="light">Açık</option>
        </select>
      </Field>

      <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
        <input
          type="checkbox"
          checked={prefs.restoreLastConversation}
          onChange={(e) =>
            onUpdate("restoreLastConversation", e.target.checked)
          }
          className="accent-blue-500"
        />
        Açılışta son konuşmayı geri yükle
      </label>
    </div>
  );
}

function McpTab({
  loading,
  servers,
  ready,
  onRefresh,
}: {
  loading: boolean;
  servers: McpServer[] | null;
  ready: boolean;
  onRefresh: () => void;
}) {
  if (!ready) {
    return (
      <p className="text-sm text-zinc-500">
        Önce Bağlantı sekmesinden Claude CLI'yi kurup giriş yap.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-400">
          Claude CLI üzerinden yapılandırılmış MCP sunucuları.
        </p>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="text-xs text-zinc-500 hover:text-zinc-200 disabled:text-zinc-700"
        >
          {loading ? "Yükleniyor…" : "Yenile"}
        </button>
      </div>

      {servers === null && !loading && (
        <p className="text-xs text-zinc-600">Liste henüz alınmadı.</p>
      )}
      {servers && servers.length === 0 && (
        <p className="text-xs text-zinc-600">
          Yapılandırılmış MCP sunucusu yok. Terminal'den{" "}
          <code className="bg-zinc-800 px-1 rounded">claude mcp add</code> ile
          ekleyebilirsin.
        </p>
      )}
      {servers && servers.length > 0 && (
        <ul className="space-y-1.5">
          {servers.map((s) => (
            <li
              key={s.name}
              className="text-xs bg-zinc-950/60 border border-zinc-800 rounded px-3 py-2 flex items-center justify-between gap-2"
            >
              <div className="min-w-0 flex-1">
                <div className="font-mono truncate text-zinc-200">{s.name}</div>
                {s.details && (
                  <div className="text-[10px] text-zinc-500 truncate mt-0.5">
                    {s.details}
                  </div>
                )}
              </div>
              <McpBadge status={s.status} />
            </li>
          ))}
        </ul>
      )}
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

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm text-zinc-300 font-medium">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-zinc-600">{hint}</p>}
    </div>
  );
}

function McpBadge({ status }: { status: string }) {
  const color =
    status === "connected"
      ? "text-green-400 bg-green-950/50 border-green-900/50"
      : status === "failed"
      ? "text-red-400 bg-red-950/50 border-red-900/50"
      : "text-zinc-400 bg-zinc-800 border-zinc-700";
  const label =
    status === "connected" ? "bağlı" : status === "failed" ? "hata" : "tanımlı";
  return (
    <span className={`text-[10px] border rounded px-1.5 py-0.5 ${color}`}>
      {label}
    </span>
  );
}
