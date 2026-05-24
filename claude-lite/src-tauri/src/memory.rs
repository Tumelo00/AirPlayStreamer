use anyhow::Result;
use std::path::Path;

const FILENAME: &str = "memory.md";
const MAX_BYTES: usize = 32 * 1024;

pub fn load(dir: &Path) -> Result<String> {
    let path = dir.join(FILENAME);
    if !path.exists() {
        return Ok(String::new());
    }
    let text = std::fs::read_to_string(&path)?;
    Ok(text)
}

pub fn save(dir: &Path, content: &str) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join(FILENAME);
    let tmp = dir.join(format!("{}.tmp", FILENAME));
    let trimmed = if content.len() > MAX_BYTES {
        &content[..MAX_BYTES]
    } else {
        content
    };
    std::fs::write(&tmp, trimmed)?;
    std::fs::rename(&tmp, &path)?;
    Ok(())
}

pub fn append(dir: &Path, entry: &str) -> Result<()> {
    let existing = load(dir).unwrap_or_default();
    let mut new_content = if existing.trim().is_empty() {
        entry.trim_start().to_string()
    } else {
        format!("{}\n\n{}", existing.trim_end(), entry.trim_start())
    };

    while new_content.len() > MAX_BYTES {
        if let Some(first_sep) = new_content.find("\n## ") {
            if let Some(second_sep_rel) = new_content[first_sep + 4..].find("\n## ") {
                new_content =
                    new_content[first_sep + 4 + second_sep_rel + 1..].to_string();
                continue;
            }
        }
        new_content = new_content[new_content.len() - MAX_BYTES..].to_string();
        break;
    }

    save(dir, &new_content)
}

pub fn merge_into_system_prompt(memory: &str, user_prompt: Option<&str>) -> Option<String> {
    let mem = memory.trim();
    let user = user_prompt.map(|s| s.trim()).filter(|s| !s.is_empty());

    if mem.is_empty() && user.is_none() {
        return None;
    }

    let mut out = String::new();
    if !mem.is_empty() {
        out.push_str("# Kullanıcı Hafızası (kalıcı notlar)\n\n");
        out.push_str(mem);
    }
    if let Some(u) = user {
        if !out.is_empty() {
            out.push_str("\n\n# Sohbet Sistem Promptu\n\n");
        }
        out.push_str(u);
    }
    Some(out)
}

pub fn read_workspace_claude_md(workspace: &Path) -> Option<String> {
    let candidates = [workspace.join("CLAUDE.md"), workspace.join(".claude/CLAUDE.md")];
    for p in &candidates {
        if let Ok(text) = std::fs::read_to_string(p) {
            return Some(text);
        }
    }
    None
}
