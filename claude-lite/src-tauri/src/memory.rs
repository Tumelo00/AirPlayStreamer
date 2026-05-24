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
    let trimmed = truncate_to_char_boundary(content, MAX_BYTES);
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
        let drop_until = find_second_entry_start(&new_content);
        match drop_until {
            Some(idx) => {
                new_content = new_content[idx..].to_string();
            }
            None => {
                let safe_start = floor_char_boundary(
                    &new_content,
                    new_content.len().saturating_sub(MAX_BYTES),
                );
                new_content = new_content[safe_start..].to_string();
                break;
            }
        }
    }

    save(dir, &new_content)
}

fn find_second_entry_start(s: &str) -> Option<usize> {
    let bytes = s.as_bytes();
    let mut i = 0;
    let mut headers_seen = 0;
    while i + 3 < bytes.len() {
        let at_line_start = i == 0 || bytes[i - 1] == b'\n';
        if at_line_start && &bytes[i..i + 3] == b"## " {
            headers_seen += 1;
            if headers_seen == 2 {
                return Some(i);
            }
        }
        i += 1;
    }
    None
}

fn truncate_to_char_boundary(s: &str, max_bytes: usize) -> &str {
    if s.len() <= max_bytes {
        return s;
    }
    let mut end = max_bytes;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

fn floor_char_boundary(s: &str, mut idx: usize) -> usize {
    if idx >= s.len() {
        return s.len();
    }
    while idx > 0 && !s.is_char_boundary(idx) {
        idx -= 1;
    }
    idx
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncate_handles_utf8_boundaries() {
        let s = "merhabaüğşıçÖ".repeat(100);
        for limit in [10, 100, 500, 1000] {
            let out = truncate_to_char_boundary(&s, limit);
            assert!(out.len() <= limit);
            assert!(std::str::from_utf8(out.as_bytes()).is_ok());
        }
    }

    #[test]
    fn floor_char_boundary_works() {
        let s = "üğşı";
        assert_eq!(floor_char_boundary(s, 0), 0);
        assert_eq!(floor_char_boundary(s, 1), 0);
        assert_eq!(floor_char_boundary(s, 2), 2);
        assert_eq!(floor_char_boundary(s, s.len()), s.len());
    }
}
