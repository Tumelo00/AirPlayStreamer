import { save } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { loadConversation } from "./storage";
import type { Conversation, Message } from "./types";

export async function exportConversationToMarkdown(
  c: Conversation
): Promise<boolean> {
  const full = (await loadConversation(c.id)) ?? c;
  const md = conversationToMarkdown(full);

  const safeName = (c.title || "konusma")
    .replace(/[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ\- ]/g, "")
    .slice(0, 60)
    .trim();

  const path = await save({
    defaultPath: `${safeName || "konusma"}.md`,
    filters: [{ name: "Markdown", extensions: ["md"] }],
  });

  if (!path) return false;

  await writeTextFile(path, md);
  return true;
}

function conversationToMarkdown(c: Conversation): string {
  const lines: string[] = [];
  lines.push(`# ${c.title || "Konuşma"}`);
  lines.push("");
  lines.push(`- Model: \`${c.model}\``);
  lines.push(`- Tarih: ${new Date(c.createdAt).toLocaleString("tr-TR")}`);
  if (c.systemPrompt) {
    lines.push("");
    lines.push("## Sistem promptu");
    lines.push("");
    lines.push("```");
    lines.push(c.systemPrompt);
    lines.push("```");
  }
  lines.push("");
  lines.push("---");
  lines.push("");

  for (const m of c.messages) {
    lines.push(...renderMessage(m));
    lines.push("");
  }

  return lines.join("\n");
}

function renderMessage(m: Message): string[] {
  const out: string[] = [];
  const role = m.role === "user" ? "👤 Kullanıcı" : "🤖 Claude";
  out.push(`## ${role}`);
  out.push("");
  if (m.attachments?.length) {
    out.push("**Ekler:**");
    for (const a of m.attachments) {
      out.push(`- \`${a.name}\` (${a.mimeType})`);
    }
    out.push("");
  }
  out.push(m.content || "_(boş)_");
  return out;
}
