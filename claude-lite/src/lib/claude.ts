import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import type { Attachment, Message, ModelId, StreamEvent } from "./types";

export interface CliStatus {
  installed: boolean;
  version: string | null;
  loggedIn: boolean;
  path: string | null;
}

export async function checkClaudeCli(): Promise<CliStatus> {
  return invoke<CliStatus>("check_claude_cli");
}

export async function openClaudeLogin(): Promise<void> {
  await invoke("open_claude_login");
}

export async function installClaudeCli(
  onLine: (line: string) => void
): Promise<void> {
  const channel = `claude-install-${crypto.randomUUID()}`;
  const unlisten: UnlistenFn = await listen<string>(channel, (e) => {
    onLine(e.payload);
  });
  try {
    await invoke("install_claude_cli", { channel });
  } finally {
    unlisten();
  }
}

export interface SendOptions {
  model: ModelId;
  systemPrompt?: string;
  messages: Message[];
  sessionId?: string;
  attachments?: Attachment[];
  maxTokens?: number;
}

export async function sendMessageStream(
  opts: SendOptions,
  onEvent: (e: StreamEvent) => void
): Promise<void> {
  const channel = `claude-stream-${crypto.randomUUID()}`;
  const unlisten: UnlistenFn = await listen<StreamEvent>(channel, (e) => {
    onEvent(e.payload);
  });

  try {
    await invoke("send_message_stream", {
      channel,
      payload: {
        model: opts.model,
        system: opts.systemPrompt ?? null,
        max_tokens: opts.maxTokens ?? 4096,
        session_id: opts.sessionId ?? null,
        messages: opts.messages.map((m) => ({
          role: m.role,
          content: buildContent(m),
        })),
        attachments: opts.attachments ?? [],
      },
    });
  } finally {
    unlisten();
  }
}

function buildContent(m: Message) {
  const blocks: any[] = [];
  if (m.attachments?.length) {
    for (const a of m.attachments) {
      if (a.kind === "image") {
        blocks.push({ type: "image", path: a.path });
      } else if (a.kind === "text" && a.preview) {
        blocks.push({
          type: "text",
          text: `\n\n--- ${a.name} ---\n${a.preview}\n--- son ---\n`,
        });
      } else {
        blocks.push({ type: "text", text: `[Ekli dosya: ${a.path}]` });
      }
    }
  }
  if (m.content) blocks.push({ type: "text", text: m.content });
  return blocks.length ? blocks : [{ type: "text", text: "" }];
}

export async function readFileAsAttachment(path: string): Promise<Attachment> {
  return invoke<Attachment>("read_file_as_attachment", { path });
}
