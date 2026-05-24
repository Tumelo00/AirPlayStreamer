import { memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SyntaxHighlighter, oneDark } from "@/lib/highlight";
import type { Attachment, Message } from "@/lib/types";

interface Props {
  messages: Message[];
  streaming: boolean;
  memoryMode?: boolean;
  pinnedIds?: Set<string>;
  onAttachmentClick?: (a: Attachment) => void;
  onPinMessage?: (m: Message) => void;
}

export function MessageList({
  messages,
  streaming,
  memoryMode,
  pinnedIds,
  onAttachmentClick,
  onPinMessage,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickyRef.current = distance < 80;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickyRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, streaming]);

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto scrollbar-thin px-6 py-4 space-y-4"
    >
      {messages.length === 0 && (
        <div className="text-center text-zinc-500 mt-20">
          <p className="text-sm">Bir mesaj yazarak başla.</p>
          <p className="text-xs mt-2 text-zinc-600">
            Görsel veya dosya sürükleyip bırakabilirsin.
          </p>
        </div>
      )}
      {messages.map((m) => (
        <MessageBubble
          key={m.id}
          message={m}
          memoryMode={memoryMode}
          pinned={pinnedIds?.has(m.id) ?? false}
          onAttachmentClick={onAttachmentClick}
          onPin={onPinMessage}
        />
      ))}
      {streaming && (
        <div className="text-xs text-zinc-500 animate-pulse">Yazıyor…</div>
      )}
    </div>
  );
}

const MessageBubble = memo(
  function MessageBubble({
    message,
    memoryMode,
    pinned,
    onAttachmentClick,
    onPin,
  }: {
    message: Message;
    memoryMode?: boolean;
    pinned?: boolean;
    onAttachmentClick?: (a: Attachment) => void;
    onPin?: (m: Message) => void;
  }) {
    const isUser = message.role === "user";
    return (
      <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
        <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
          <div
            className={`rounded-lg px-4 py-2.5 ${
              isUser ? "bg-blue-600 text-white" : "bg-zinc-800/80 text-zinc-100"
            }`}
          >
            {message.attachments && message.attachments.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {message.attachments.map((a, i) => (
                  <AttachmentChip
                    key={i}
                    attachment={a}
                    onClick={() => onAttachmentClick?.(a)}
                  />
                ))}
              </div>
            )}
            <div className="markdown-body text-sm leading-relaxed">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    if (match) {
                      return (
                        <SyntaxHighlighter
                          language={match[1]}
                          style={oneDark as any}
                          PreTag="div"
                          customStyle={{
                            margin: 0,
                            borderRadius: 6,
                            fontSize: 12,
                          }}
                        >
                          {String(children).replace(/\n$/, "")}
                        </SyntaxHighlighter>
                      );
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content || (isUser ? "" : "…")}
              </ReactMarkdown>
            </div>
          </div>
          {memoryMode && onPin && message.content && (
            <PinButton message={message} pinned={pinned} onPin={onPin} />
          )}
        </div>
      </div>
    );
  },
  (prev, next) =>
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.message.attachments === next.message.attachments &&
    prev.memoryMode === next.memoryMode &&
    prev.pinned === next.pinned
);

function PinButton({
  message,
  pinned,
  onPin,
}: {
  message: Message;
  pinned?: boolean;
  onPin: (m: Message) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(pinned ?? false);

  useEffect(() => {
    if (pinned !== undefined) setDone(pinned);
  }, [pinned]);

  const handleClick = async () => {
    if (busy || done) return;
    setBusy(true);
    try {
      await onPin(message);
      setDone(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={busy || done}
      className={`text-[10px] px-2 py-0.5 rounded border self-start ${
        done
          ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
          : "border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50"
      }`}
      title={done ? "Hafızaya eklendi" : "Bu mesajı hafızaya sabitle"}
    >
      {done ? "📌 sabitlendi" : busy ? "📌 ekleniyor…" : "📌 hafızaya sabitle"}
    </button>
  );
}

function AttachmentChip({
  attachment,
  onClick,
}: {
  attachment: Attachment;
  onClick?: () => void;
}) {
  if (attachment.kind === "image" && attachment.preview) {
    return (
      <img
        src={`data:${attachment.mimeType};base64,${attachment.preview}`}
        alt={attachment.name}
        onClick={onClick}
        className="max-h-32 rounded border border-zinc-700 cursor-pointer hover:opacity-80"
      />
    );
  }
  return (
    <button
      onClick={onClick}
      className="text-xs bg-zinc-900/60 border border-zinc-700 rounded px-2 py-1 hover:bg-zinc-800 hover:border-zinc-600"
    >
      {attachment.name}
    </button>
  );
}
