import { invoke } from "@tauri-apps/api/core";

export interface Preferences {
  theme: "dark" | "light";
  defaultModel: string;
  defaultSystemPrompt?: string;
  workspaceDir?: string;
  restoreLastConversation: boolean;
}

const DEFAULTS: Preferences = {
  theme: "dark",
  defaultModel: "claude-sonnet-4-6",
  restoreLastConversation: true,
};

export async function loadPreferences(): Promise<Preferences> {
  try {
    const p = await invoke<Preferences | null>("load_preferences");
    return { ...DEFAULTS, ...(p ?? {}) };
  } catch {
    return DEFAULTS;
  }
}

export async function savePreferences(p: Preferences): Promise<void> {
  await invoke("save_preferences", { preferences: p });
}
