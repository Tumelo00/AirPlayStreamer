import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Message } from "@/lib/types";

interface Props {
  messages: Message[];
  streaming: boolean;
}

export function MessageList({ messages, streaming }: Props) {
  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-4 space-y-4">
      {messages.length === 0 && (
        <div className="text-center text-zinc-500 mt-20">
          <p className="text-sm">Bir mesaj yazarak başla.</p>
          <p className="text-xs mt-2 text-zinc-600">
            Görsel veya dosya sürükleyip bırakabilirsin.
          </p>
        </div>
      )}
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {streaming && (
        <div className="text-xs text-zinc-500 animate-pulse">Yazıyor…</div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-zinc-800/80 text-zinc-100"
        }`}
      >
        {message.attachments && message.attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {message.attachments.map((a, i) => (
              <AttachmentChip key={i} attachment={a} />
            ))}
          </div>
        )}
        <div className="markdown-body text-sm leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || "");
                if (!inline && match) {
                  return (
                    <SyntaxHighlighter
                      language={match[1]}
                      style={oneDark as any}
                      PreTag="div"
                      customStyle={{ margin: 0, borderRadius: 6 }}
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
    </div>
  );
}

function AttachmentChip({ attachment }: { attachment: any }) {
  if (attachment.kind === "image" && attachment.preview) {
    return (
      <img
        src={`data:${attachment.mimeType};base64,${attachment.preview}`}
        alt={attachment.name}
        className="max-h-32 rounded border border-zinc-700"
      />
    );
  }
  return (
    <div className="text-xs bg-zinc-900/60 border border-zinc-700 rounded px-2 py-1">
      📎 {attachment.name}
    </div>
  );
}
