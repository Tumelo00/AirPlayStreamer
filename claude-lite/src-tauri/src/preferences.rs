use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preferences {
    pub theme: String,
    #[serde(rename = "defaultModel")]
    pub default_model: String,
    #[serde(
        rename = "defaultSystemPrompt",
        default,
        skip_serializing_if = "Option::is_none"
    )]
    pub default_system_prompt: Option<String>,
    #[serde(
        rename = "workspaceDir",
        default,
        skip_serializing_if = "Option::is_none"
    )]
    pub workspace_dir: Option<String>,
    #[serde(rename = "restoreLastConversation", default = "default_true")]
    pub restore_last_conversation: bool,
}

fn default_true() -> bool {
    true
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            theme: "dark".into(),
            default_model: "claude-sonnet-4-6".into(),
            default_system_prompt: None,
            workspace_dir: None,
            restore_last_conversation: true,
        }
    }
}

pub fn load(dir: &Path) -> Result<Preferences> {
    let path = dir.join("preferences.json");
    if !path.exists() {
        return Ok(Preferences::default());
    }
    let text = std::fs::read_to_string(&path)?;
    Ok(serde_json::from_str(&text).unwrap_or_default())
}

pub fn save(dir: &Path, prefs: &Preferences) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join("preferences.json");
    let json = serde_json::to_string_pretty(prefs)?;
    let tmp = dir.join("preferences.json.tmp");
    std::fs::write(&tmp, json)?;
    std::fs::rename(&tmp, &path)?;
    Ok(())
}
