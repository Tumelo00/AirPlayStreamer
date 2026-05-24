import { useEffect, useRef, useState } from "react";
import { exportConversationToMarkdown } from "@/lib/export";
import {
  deleteConversation,
  listConversations,
  saveConversation,
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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [query, setQuery] = useState("");

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

  const startEdit = (e: React.MouseEvent, c: Conversation) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditText(c.title);
  };

  const handleExport = async (e: React.MouseEvent, c: Conversation) => {
    e.stopPropagation();
    try {
      await exportConversationToMarkdown(c);
    } catch (err) {
      alert(`Export hatası: ${err}`);
    }
  };

  const commitEdit = async (c: Conversation) => {
    if (editingId !== c.id) return;
    const newTitle = editText.trim() || c.title;
    setEditingId(null);
    if (newTitle === c.title) return;
    await saveConversation({ ...c, title: newTitle });
    refresh();
  };

  const cancelEdit = () => setEditingId(null);

  const filtered = query.trim()
    ? items.filter((c) =>
        c.title.toLowerCase().includes(query.trim().toLowerCase())
      )
    : items;

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
      <div className="px-2 py-1.5 border-b border-zinc-800/40">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ara…"
          className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin py-1">
        {loading && (
          <div className="text-xs text-zinc-600 px-3 py-2">Yükleniyor…</div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="text-xs text-zinc-600 px-3 py-2">
            {query.trim() ? "Sonuç yok." : "Henüz konuşma yok."}
          </div>
        )}
        {filtered.map((c) => (
          <ConversationRow
            key={c.id}
            conversation={c}
            active={c.id === activeId}
            editing={editingId === c.id}
            editText={editText}
            onEditTextChange={setEditText}
            onSelect={() => onSelect(c)}
            onStartEdit={(e) => startEdit(e, c)}
            onCommitEdit={() => commitEdit(c)}
            onCancelEdit={cancelEdit}
            onDelete={(e) => handleDelete(e, c.id)}
            onExport={(e) => handleExport(e, c)}
          />
        ))}
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  active,
  editing,
  editText,
  onEditTextChange,
  onSelect,
  onStartEdit,
  onCommitEdit,
  onCancelEdit,
  onDelete,
  onExport,
}: {
  conversation: Conversation;
  active: boolean;
  editing: boolean;
  editText: string;
  onEditTextChange: (s: string) => void;
  onSelect: () => void;
  onStartEdit: (e: React.MouseEvent) => void;
  onCommitEdit: () => void;
  onCancelEdit: () => void;
  onDelete: (e: React.MouseEvent) => void;
  onExport: (e: React.MouseEvent) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  if (editing) {
    return (
      <div
        className={`px-3 py-2 border-l-2 ${
          active ? "border-blue-500 bg-zinc-800/60" : "border-transparent"
        }`}
      >
        <input
          ref={inputRef}
          value={editText}
          onChange={(e) => onEditTextChange(e.target.value)}
          onBlur={onCommitEdit}
          onKeyDown={(e) => {
            if (e.key === "Enter") onCommitEdit();
            else if (e.key === "Escape") onCancelEdit();
          }}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-0.5 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>
    );
  }

  return (
    <div
      onClick={onSelect}
      onDoubleClick={onStartEdit}
      className={`group cursor-pointer px-3 py-2 text-xs border-l-2 transition flex items-center justify-between ${
        active
          ? "bg-zinc-800/60 border-blue-500 text-zinc-100"
          : "border-transparent text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
      }`}
      title="Çift tıkla: yeniden adlandır"
    >
      <span className="truncate flex-1">
        {conversation.title || "Adsız sohbet"}
      </span>
      <span className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 ml-2">
        <button
          onClick={onExport}
          className="text-zinc-500 hover:text-zinc-200 px-1"
          aria-label="Markdown olarak dışa aktar"
          title="Markdown olarak kaydet"
        >
          ↓
        </button>
        <button
          onClick={onStartEdit}
          className="text-zinc-500 hover:text-zinc-200 px-1"
          aria-label="Yeniden adlandır"
        >
          ✎
        </button>
        <button
          onClick={onDelete}
          className="text-zinc-500 hover:text-red-400 px-1"
          aria-label="Sil"
        >
          ×
        </button>
      </span>
    </div>
  );
}
