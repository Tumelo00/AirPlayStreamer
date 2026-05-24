import { MODELS } from "@/lib/types";

interface Props {
  model: string;
  onModelChange: (model: string) => void;
  onOpenSettings: () => void;
  onNewChat: () => void;
}

export function ChatHeader({
  model,
  onModelChange,
  onOpenSettings,
  onNewChat,
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
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={onNewChat}
          className="text-xs text-zinc-400 hover:text-zinc-100 px-2 py-1 rounded hover:bg-zinc-800"
        >
          + Yeni
        </button>
        <button
          onClick={onOpenSettings}
          className="text-xs text-zinc-400 hover:text-zinc-100 px-2 py-1 rounded hover:bg-zinc-800"
        >
          ⚙ Ayarlar
        </button>
      </div>
    </div>
  );
}
