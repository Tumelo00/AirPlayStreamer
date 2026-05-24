import { useEffect, useRef, useState } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { readFileAsAttachment, savePastedImage } from "@/lib/claude";
import type { Attachment } from "@/lib/types";

interface Props {
  onSend: (text: string, attachments: Attachment[]) => void;
  onStop?: () => void;
  streaming?: boolean;
  disabled?: boolean;
}

export function MessageInput({ onSend, onStop, streaming, disabled }: Props) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [pasteBusy, setPasteBusy] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const win = getCurrentWebviewWindow();
    const promise = win.onDragDropEvent(async (event) => {
      if (event.payload.type === "over") {
        setDragOver(true);
      } else if (event.payload.type === "leave") {
        setDragOver(false);
      } else if (event.payload.type === "drop") {
        setDragOver(false);
        const paths = event.payload.paths;
        const loaded = await Promise.all(
          paths.map((p) => readFileAsAttachment(p).catch(() => null))
        );
        setAttachments((prev) => [
          ...prev,
          ...loaded.filter((a): a is Attachment => a !== null),
        ]);
      }
    });
    return () => {
      promise.then((unlisten) => unlisten()).catch(() => {});
    };
  }, []);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`;
  }, [text]);

  const submit = () => {
    if (disabled || streaming) return;
    if (!text.trim() && attachments.length === 0) return;
    onSend(text, attachments);
    setText("");
    setAttachments([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handlePaste = async (
    e: React.ClipboardEvent<HTMLTextAreaElement>
  ) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const blob = item.getAsFile();
        if (!blob) continue;
        setPasteBusy(true);
        try {
          const buf = new Uint8Array(await blob.arrayBuffer());
          const att = await savePastedImage(buf, blob.type);
          setAttachments((prev) => [...prev, att]);
        } catch (err) {
          console.error("paste hatası", err);
        } finally {
          setPasteBusy(false);
        }
        return;
      }
    }
  };

  return (
    <div
      className={`border-t border-zinc-800 bg-zinc-900/50 p-3 transition ${
        dragOver ? "ring-2 ring-blue-500 ring-inset" : ""
      }`}
    >
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {attachments.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs"
            >
              {a.kind === "image" && a.preview ? (
                <img
                  src={`data:${a.mimeType};base64,${a.preview}`}
                  alt=""
                  className="h-8 w-8 object-cover rounded"
                />
              ) : (
                <span className="text-zinc-400">·</span>
              )}
              <span className="max-w-[150px] truncate">{a.name}</span>
              <button
                onClick={() =>
                  setAttachments((prev) => prev.filter((_, idx) => idx !== i))
                }
                className="text-zinc-500 hover:text-zinc-200"
                aria-label="Sil"
              >
                ×
              </button>
            </div>
          ))}
          {pasteBusy && (
            <div className="text-xs text-zinc-500 self-center animate-pulse">
              Görsel kaydediliyor…
            </div>
          )}
        </div>
      )}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Mesaj yaz… (dosya sürükle, görsel yapıştır)"
          rows={1}
          className="flex-1 bg-zinc-800/70 border border-zinc-700 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-blue-500 scrollbar-thin min-h-[40px] max-h-[220px]"
          disabled={disabled}
        />
        {streaming ? (
          <button
            onClick={onStop}
            className="bg-red-600 hover:bg-red-500 text-white rounded-lg px-4 py-2 text-sm font-medium"
          >
            Durdur
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={disabled || (!text.trim() && attachments.length === 0)}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition"
          >
            Gönder
          </button>
        )}
      </div>
      <p className="text-[10px] text-zinc-600 mt-1.5 px-1">
        Enter: gönder · Shift+Enter: yeni satır · ⌘V: görsel yapıştır
      </p>
    </div>
  );
}
