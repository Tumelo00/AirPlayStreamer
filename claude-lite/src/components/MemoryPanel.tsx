import { useEffect, useState } from "react";
import {
  loadMemory,
  readWorkspaceClaudeMd,
  saveMemory,
  writeWorkspaceClaudeMd,
} from "@/lib/memory";

interface Props {
  workspaceDir?: string;
}

export function MemoryPanel({ workspaceDir }: Props) {
  const [memory, setMemory] = useState("");
  const [memoryLoaded, setMemoryLoaded] = useState(false);
  const [memoryDirty, setMemoryDirty] = useState(false);
  const [memorySaving, setMemorySaving] = useState(false);
  const [memoryStatus, setMemoryStatus] = useState<string | null>(null);

  const [claudeMd, setClaudeMd] = useState<string | null>(null);
  const [claudeMdDirty, setClaudeMdDirty] = useState(false);
  const [claudeMdSaving, setClaudeMdSaving] = useState(false);
  const [claudeMdStatus, setClaudeMdStatus] = useState<string | null>(null);

  useEffect(() => {
    loadMemory()
      .then((m) => {
        setMemory(m);
        setMemoryLoaded(true);
      })
      .catch(() => setMemoryLoaded(true));
  }, []);

  useEffect(() => {
    if (!workspaceDir) {
      setClaudeMd(null);
      return;
    }
    readWorkspaceClaudeMd()
      .then((c) => setClaudeMd(c ?? ""))
      .catch(() => setClaudeMd(""));
  }, [workspaceDir]);

  const saveMem = async () => {
    setMemorySaving(true);
    setMemoryStatus(null);
    try {
      await saveMemory(memory);
      setMemoryDirty(false);
      setMemoryStatus("Kaydedildi.");
      setTimeout(() => setMemoryStatus(null), 2000);
    } catch (e) {
      setMemoryStatus(`Hata: ${e}`);
    } finally {
      setMemorySaving(false);
    }
  };

  const saveClaudeMd = async () => {
    if (claudeMd === null) return;
    setClaudeMdSaving(true);
    setClaudeMdStatus(null);
    try {
      await writeWorkspaceClaudeMd(claudeMd);
      setClaudeMdDirty(false);
      setClaudeMdStatus("Kaydedildi.");
      setTimeout(() => setClaudeMdStatus(null), 2000);
    } catch (e) {
      setClaudeMdStatus(`Hata: ${e}`);
    } finally {
      setClaudeMdSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Kullanıcı hafızası</h3>
          <span className="text-[10px] text-zinc-600">
            {memory.length} / 32K
          </span>
        </div>
        <p className="text-xs text-zinc-500">
          Bu notlar her sohbette Claude'a otomatik gönderilir. Tercihlerini,
          projenin bağlamını, hatırlanmasını istediğin kuralları yaz.
        </p>
        <textarea
          value={memory}
          onChange={(e) => {
            setMemory(e.target.value);
            setMemoryDirty(true);
          }}
          disabled={!memoryLoaded}
          rows={8}
          placeholder="Örn:&#10;- Beni Tumelo diye çağır.&#10;- TypeScript'te tab değil 2 space kullanıyorum.&#10;- React projelerimde Zustand tercih ediyorum.&#10;- Cevapları kısa ve Türkçe ver."
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-xs font-mono resize-y min-h-[160px] focus:outline-none focus:border-blue-500 scrollbar-thin"
        />
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-500">
            {memoryStatus ?? (memoryDirty ? "Değişti." : "")}
          </span>
          <button
            onClick={saveMem}
            disabled={!memoryDirty || memorySaving}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded px-3 py-1 text-xs"
          >
            {memorySaving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </section>

      <section className="space-y-2 pt-3 border-t border-zinc-800/60">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Workspace CLAUDE.md</h3>
          {workspaceDir && (
            <code className="text-[10px] text-zinc-600 truncate max-w-[280px]">
              {workspaceDir}/CLAUDE.md
            </code>
          )}
        </div>
        {!workspaceDir && (
          <p className="text-xs text-zinc-500">
            Önce Genel sekmesinden çalışma dizini seç. Claude CLI bu dizindeki
            CLAUDE.md'yi otomatik okur.
          </p>
        )}
        {workspaceDir && claudeMd !== null && (
          <>
            <p className="text-xs text-zinc-500">
              Workspace'e özel notlar (kod stili, mimari kararlar, vs).
              Yalnızca bu workspace için geçerli; kullanıcı hafızasının üstüne
              eklenir.
            </p>
            <textarea
              value={claudeMd}
              onChange={(e) => {
                setClaudeMd(e.target.value);
                setClaudeMdDirty(true);
              }}
              rows={8}
              placeholder="# Proje bağlamı&#10;&#10;Bu proje X için Y kullanıyor..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-xs font-mono resize-y min-h-[160px] focus:outline-none focus:border-blue-500 scrollbar-thin"
            />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-zinc-500">
                {claudeMdStatus ?? (claudeMdDirty ? "Değişti." : "")}
              </span>
              <button
                onClick={saveClaudeMd}
                disabled={!claudeMdDirty || claudeMdSaving}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded px-3 py-1 text-xs"
              >
                {claudeMdSaving ? "Kaydediliyor…" : "CLAUDE.md kaydet"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
