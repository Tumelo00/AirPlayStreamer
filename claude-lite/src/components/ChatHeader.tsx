import { MODELS, type UsageInfo } from "@/lib/types";

interface Props {
  model: string;
  onModelChange: (model: string) => void;
  onOpenSettings: () => void;
  onNewChat: () => void;
  usage?: UsageInfo | null;
}

export function ChatHeader({
  model,
  onModelChange,
  onOpenSettings,
  onNewChat,
  usage,
}: Props) {
  return (
    <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2.5 bg-zinc-900/40">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold tracking-tight">Claude Lite</span>
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
  );
}

function formatNum(n: number): string {
  if (n < 1000) return n.toString();
  if (n < 10000) return `${(n / 1000).toFixed(1)}k`;
  return `${Math.round(n / 1000)}k`;
}
