import { useEffect, useState } from "react";
import {
  deleteConversation,
  listConversations,
} from "@/lib/storage";
import type { Conversation } from "@/lib/types";

interface Props {
  activeId: string;
  onSelect: (c: Conversation) => void;
  onNew: () => void;
  refreshKey: number;
}

export function Sidebar({ activeId, onSelect, onNew, refreshKey }: Props) {
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await listConversations();
      setItems(list);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [refreshKey]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Bu konuşmayı sil?")) return;
    await deleteConversation(id);
    refresh();
    if (id === activeId) onNew();
  };

  if (collapsed) {
    return (
      <div className="w-10 border-r border-zinc-800 bg-zinc-950/60 flex flex-col items-center py-2 gap-1">
        <button
          onClick={() => setCollapsed(false)}
          className="text-zinc-500 hover:text-zinc-200 p-1.5 rounded hover:bg-zinc-800"
          title="Genişlet"
        >
          ☰
        </button>
        <button
          onClick={onNew}
          className="text-zinc-500 hover:text-zinc-200 p-1.5 rounded hover:bg-zinc-800"
          title="Yeni sohbet"
        >
          +
        </button>
      </div>
    );
  }

  return (
    <div className="w-60 border-r border-zinc-800 bg-zinc-950/60 flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/50">
        <button
          onClick={() => setCollapsed(true)}
          className="text-zinc-500 hover:text-zinc-200 text-sm"
          title="Daralt"
        >
          ☰
        </button>
        <button
          onClick={onNew}
          className="text-xs text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 rounded px-2 py-1"
        >
          + Yeni
        </button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin py-1">
        {loading && (
          <div className="text-xs text-zinc-600 px-3 py-2">Yükleniyor…</div>
        )}
        {!loading && items.length === 0 && (
          <div className="text-xs text-zinc-600 px-3 py-2">
            Henüz konuşma yok.
          </div>
        )}
        {items.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c)}
            className={`group w-full text-left px-3 py-2 text-xs border-l-2 transition flex items-center justify-between ${
              c.id === activeId
                ? "bg-zinc-800/60 border-blue-500 text-zinc-100"
                : "border-transparent text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
            }`}
          >
            <span className="truncate flex-1">{c.title || "Adsız sohbet"}</span>
            <span
              onClick={(e) => handleDelete(e, c.id)}
              className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 ml-2 px-1"
              role="button"
              aria-label="Sil"
            >
              ×
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
