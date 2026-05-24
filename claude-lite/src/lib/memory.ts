import { invoke } from "@tauri-apps/api/core";

export async function loadMemory(): Promise<string> {
  return invoke<string>("load_memory");
}

export async function saveMemory(content: string): Promise<void> {
  await invoke("save_memory", { content });
}

export async function appendMemory(entry: string): Promise<void> {
  await invoke("append_memory", { entry });
}

export function formatMemoryEntry(opts: {
  source: "user" | "assistant" | "note";
  conversationTitle: string;
  content: string;
}): string {
  const now = new Date();
  const date = now.toLocaleDateString("tr-TR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const time = now.toLocaleTimeString("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const roleLabel =
    opts.source === "user"
      ? "Kullanıcı"
      : opts.source === "assistant"
      ? "Claude"
      : "Not";
  const title = opts.conversationTitle || "Sohbet";
  return `## ${date} ${time} · ${roleLabel} · ${title}\n${opts.content.trim()}`;
}


export async function readWorkspaceClaudeMd(): Promise<string | null> {
  return invoke<string | null>("read_workspace_claude_md");
}

export async function writeWorkspaceClaudeMd(content: string): Promise<void> {
  await invoke("write_workspace_claude_md", { content });
}
