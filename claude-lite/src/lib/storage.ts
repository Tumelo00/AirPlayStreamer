import { invoke } from "@tauri-apps/api/core";
import type { Conversation } from "./types";

export async function listConversations(): Promise<Conversation[]> {
  return invoke<Conversation[]>("list_conversations");
}

export async function loadConversation(id: string): Promise<Conversation | null> {
  return invoke<Conversation | null>("load_conversation", { id });
}

export async function saveConversation(c: Conversation): Promise<void> {
  await invoke("save_conversation", { conversation: c });
}

export async function deleteConversation(id: string): Promise<void> {
  await invoke("delete_conversation", { id });
}
