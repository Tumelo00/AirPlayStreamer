import { useState } from "react";
import { MODELS, type UsageInfo } from "@/lib/types";

interface Props {
  model: string;
  systemPrompt?: string;
  onSystemPromptChange?: (sp: string) => void;
  onModelChange: (model: string) => void;
  onOpenSettings: () => void;
  onNewChat: () => void;
  usage?: UsageInfo | null;
}

export function ChatHeader({
  model,
  systemPrompt,
  onSystemPromptChange,
  onModelChange,
  onOpenSettings,
  onNewChat,
  usage,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(systemPrompt ?? "");

  return (
    <>
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5 bg-zinc-900/40">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-tight">
            Claude Lite
          </span>
          <select
            value={model}
            onChange={(e) => onModelChange(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
          >
            {MODELS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          {onSystemPromptChange && (
            <button
              onClick={() => {
                setDraft(systemPrompt ?? "");
                setEditing((v) => !v);
              }}
              className={`text-[10px] border rounded px-1.5 py-0.5 ${
                systemPrompt
                  ? "border-blue-700 text-blue-300 bg-blue-950/30"
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Sistem promptu"
            >
              {systemPrompt ? "● prompt" : "+ prompt"}
            </button>
          )}
          {usage && (
            <span className="text-[10px] text-zinc-500" title="Son cevap">
              {formatNum(usage.inputTokens)} ↑ · {formatNum(usage.outputTokens)} ↓
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onNewChat}
            className="text-xs text-zinc-400 hover:text-zinc-100 px-2 py-1 rounded hover:bg-zinc-800"
            title="⌘N"
          >
            + Yeni
          </button>
          <button
            onClick={onOpenSettings}
            className="text-xs text-zinc-400 hover:text-zinc-100 px-2 py-1 rounded hover:bg-zinc-800"
            title="⌘,"
          >
            Ayarlar
          </button>
        </div>
      </div>
      {editing && onSystemPromptChange && (
        <div className="border-b border-zinc-800 bg-zinc-900/30 px-4 py-2 space-y-1.5">
          <label className="text-[10px] text-zinc-500 uppercase tracking-wider">
            Sistem promptu (sadece bu sohbet)
          </label>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder="Örn: Sen kısa cevap veren bir Türkçe asistansın."
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs resize-y min-h-[60px] focus:outline-none focus:border-blue-500 scrollbar-thin"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setEditing(false)}
              className="text-xs text-zinc-500 hover:text-zinc-200 px-2 py-1"
            >
              Kapat
            </button>
            <button
              onClick={() => {
                onSystemPromptChange(draft);
                setEditing(false);
              }}
              className="text-xs bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1"
            >
              Uygula
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function formatNum(n: number): string {
  if (n < 1000) return n.toString();
  if (n < 10000) return `${(n / 1000).toFixed(1)}k`;
  return `${Math.round(n / 1000)}k`;
}
