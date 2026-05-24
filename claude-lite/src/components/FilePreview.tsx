import { convertFileSrc } from "@tauri-apps/api/core";
import { SyntaxHighlighter, oneDark } from "@/lib/highlight";
import type { Attachment } from "@/lib/types";

interface Props {
  attachment: Attachment | null;
  onClose: () => void;
}

export function FilePreview({ attachment, onClose }: Props) {
  if (!attachment) return null;

  return (
    <div className="w-[420px] border-l border-zinc-800 bg-zinc-950/60 flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/50">
        <span className="text-xs text-zinc-300 truncate flex-1" title={attachment.path}>
          {attachment.name}
        </span>
        <button
          onClick={onClose}
          className="text-zinc-500 hover:text-zinc-200 text-sm ml-2"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-auto scrollbar-thin p-3">
        <PreviewBody attachment={attachment} />
      </div>
      <div className="border-t border-zinc-800/50 px-3 py-1.5 text-[10px] text-zinc-600 flex justify-between">
        <span>{attachment.mimeType}</span>
        <span>{formatSize(attachment.size)}</span>
      </div>
    </div>
  );
}

function PreviewBody({ attachment }: { attachment: Attachment }) {
  if (attachment.kind === "image" && attachment.preview) {
    return (
      <img
        src={`data:${attachment.mimeType};base64,${attachment.preview}`}
        alt={attachment.name}
        className="max-w-full rounded border border-zinc-800"
      />
    );
  }

  if (attachment.kind === "pdf") {
    return (
      <iframe
        src={convertFileSrc(attachment.path)}
        title={attachment.name}
        className="w-full h-full min-h-[500px] bg-white rounded"
      />
    );
  }

  if (attachment.kind === "text" && attachment.preview) {
    const lang = detectLanguage(attachment.name);
    if (lang) {
      return (
        <SyntaxHighlighter
          language={lang}
          style={oneDark as any}
          customStyle={{
            margin: 0,
            borderRadius: 6,
            fontSize: 12,
            background: "rgb(24 24 27)",
          }}
          wrapLongLines
        >
          {attachment.preview}
        </SyntaxHighlighter>
      );
    }
    return (
      <pre className="text-xs text-zinc-200 whitespace-pre-wrap font-mono leading-relaxed">
        {attachment.preview}
      </pre>
    );
  }

  return (
    <div className="text-xs text-zinc-500 text-center mt-12">
      <p>Bu dosya türü için önizleme yok.</p>
      <p className="mt-1 text-zinc-600">{attachment.mimeType}</p>
    </div>
  );
}

function detectLanguage(name: string): string | null {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "tsx",
    js: "javascript",
    jsx: "jsx",
    py: "python",
    rs: "rust",
    go: "go",
    java: "java",
    c: "c",
    cpp: "cpp",
    cs: "csharp",
    rb: "ruby",
    php: "php",
    swift: "swift",
    kt: "kotlin",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    toml: "toml",
    xml: "xml",
    html: "html",
    css: "css",
    scss: "scss",
    sql: "sql",
    md: "markdown",
  };
  return map[ext] ?? null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
