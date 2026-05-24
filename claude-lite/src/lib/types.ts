export type Role = "user" | "assistant" | "system";

export type ContentBlock =
  | { type: "text"; text: string }
  | {
      type: "image";
      source: { type: "base64"; media_type: string; data: string };
    };

export interface Message {
  id: string;
  role: Role;
  content: string;
  attachments?: Attachment[];
  createdAt: number;
}

export interface UsageInfo {
  inputTokens: number;
  outputTokens: number;
}

export interface Attachment {
  name: string;
  path: string;
  mimeType: string;
  size: number;
  kind: "image" | "text" | "pdf" | "other";
  preview?: string;
}

export interface Conversation {
  id: string;
  title: string;
  model: string;
  systemPrompt?: string;
  sessionId?: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

export const MODELS = [
  { id: "claude-opus-4-7", label: "Opus 4.7", tier: "smartest" },
  { id: "claude-sonnet-4-6", label: "Sonnet 4.6", tier: "balanced" },
  { id: "claude-haiku-4-5-20251001", label: "Haiku 4.5", tier: "fast" },
] as const;

export type ModelId = (typeof MODELS)[number]["id"];

export interface StreamEvent {
  type: "delta" | "done" | "error";
  text?: string;
  error?: string;
  sessionId?: string;
  usage?: { input_tokens: number; output_tokens: number };
}
