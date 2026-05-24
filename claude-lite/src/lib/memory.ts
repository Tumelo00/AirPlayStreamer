import { invoke } from "@tauri-apps/api/core";

export async function loadMemory(): Promise<string> {
  return invoke<string>("load_memory");
}

export async function saveMemory(content: string): Promise<void> {
  await invoke("save_memory", { content });
}

export async function readWorkspaceClaudeMd(): Promise<string | null> {
  return invoke<string | null>("read_workspace_claude_md");
}

export async function writeWorkspaceClaudeMd(content: string): Promise<void> {
  await invoke("write_workspace_claude_md", { content });
}
