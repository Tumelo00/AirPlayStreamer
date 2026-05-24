use anyhow::{anyhow, Result};
use base64::Engine;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncReadExt, BufReader};
use tokio::process::Command;

#[derive(Debug, Deserialize, Serialize)]
pub struct ChatRequest {
    pub model: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub system: Option<String>,
    #[serde(default)]
    pub max_tokens: u32,
    pub messages: Vec<ApiMessage>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub attachments: Vec<Attachment>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ApiMessage {
    pub role: String,
    pub content: Value,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Attachment {
    pub name: String,
    pub path: String,
    #[serde(rename = "mimeType")]
    pub mime_type: String,
    pub size: u64,
    pub kind: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub preview: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum StreamEvent {
    Delta {
        text: String,
    },
    Done {
        usage: Option<Usage>,
        #[serde(rename = "sessionId", skip_serializing_if = "Option::is_none")]
        session_id: Option<String>,
    },
    Error {
        error: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Usage {
    pub input_tokens: u32,
    pub output_tokens: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct CliStatus {
    pub installed: bool,
    pub version: Option<String>,
    #[serde(rename = "loggedIn")]
    pub logged_in: bool,
    pub path: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct McpServer {
    pub name: String,
    pub status: String,
    pub details: Option<String>,
}

fn resolve_claude_path() -> Option<String> {
    let mut candidates: Vec<String> = vec![
        "/opt/homebrew/bin/claude".into(),
        "/usr/local/bin/claude".into(),
        "/usr/bin/claude".into(),
    ];
    if let Some(home) = std::env::var_os("HOME") {
        let h = Path::new(&home);
        candidates.push(h.join(".local/bin/claude").to_string_lossy().to_string());
        candidates.push(h.join(".claude/bin/claude").to_string_lossy().to_string());
        candidates.push(h.join(".claude/local/claude").to_string_lossy().to_string());
    }
    candidates.push("claude".into());

    for c in &candidates {
        if let Ok(output) = std::process::Command::new(c)
            .arg("--version")
            .stdin(Stdio::null())
            .output()
        {
            if output.status.success() {
                return Some(c.clone());
            }
        }
    }
    None
}

pub async fn check_cli() -> CliStatus {
    let Some(path) = resolve_claude_path() else {
        return CliStatus {
            installed: false,
            version: None,
            logged_in: false,
            path: None,
        };
    };

    let version = Command::new(&path)
        .arg("--version")
        .stdin(Stdio::null())
        .output()
        .await
        .ok()
        .and_then(|o| {
            if o.status.success() {
                String::from_utf8(o.stdout).ok()
            } else {
                None
            }
        })
        .map(|s| s.trim().to_string());

    let logged_in = check_login(&path).await;

    CliStatus {
        installed: true,
        version,
        logged_in,
        path: Some(path),
    }
}

async fn check_login(path: &str) -> bool {
    let home = match std::env::var_os("HOME") {
        Some(h) => h,
        None => return false,
    };
    let creds = Path::new(&home).join(".claude").join(".credentials.json");
    let config = Path::new(&home).join(".claude.json");
    if creds.exists() || config.exists() {
        return true;
    }

    match Command::new(path)
        .args(["config", "get", "-g", "hasCompletedOnboarding"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .await
    {
        Ok(o) if o.status.success() => {
            let out = String::from_utf8_lossy(&o.stdout);
            out.trim() == "true"
        }
        _ => false,
    }
}

fn model_alias(model: &str) -> &str {
    if model.contains("opus") {
        "opus"
    } else if model.contains("haiku") {
        "haiku"
    } else {
        "sonnet"
    }
}

pub async fn stream_messages<F>(
    req: ChatRequest,
    abort: Arc<AtomicBool>,
    cwd: Option<String>,
    mut emit: F,
) -> Result<()>
where
    F: FnMut(StreamEvent) + Send,
{
    let path = resolve_claude_path().ok_or_else(|| {
        anyhow!("Claude CLI bulunamadı. Ayarlardan otomatik kurulum yapabilirsin.")
    })?;

    let last_user = req
        .messages
        .iter()
        .rev()
        .find(|m| m.role == "user")
        .ok_or_else(|| anyhow!("user mesajı yok"))?;

    let prompt = extract_text_from_content(&last_user.content);
    if prompt.trim().is_empty() {
        return Err(anyhow!("boş prompt"));
    }

    let model = model_alias(&req.model);
    let session_id = req.session_id.clone().unwrap_or_else(uuid_v4);

    let mut cmd = Command::new(&path);
    cmd.arg("-p")
        .arg(&prompt)
        .arg("--model")
        .arg(model)
        .arg("--output-format")
        .arg("stream-json")
        .arg("--include-partial-messages")
        .arg("--verbose")
        .arg("--session-id")
        .arg(&session_id);

    if let Some(sys) = req.system.as_ref().filter(|s| !s.is_empty()) {
        cmd.arg("--append-system-prompt").arg(sys);
    }

    if let Some(dir) = cwd.as_ref().filter(|s| !s.is_empty()) {
        if Path::new(dir).is_dir() {
            cmd.current_dir(dir);
        }
    }

    cmd.stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    let mut child = cmd.spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| anyhow!("stdout açılamadı"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| anyhow!("stderr açılamadı"))?;

    let stderr_task = tokio::spawn(async move {
        let mut buf = String::new();
        let _ = BufReader::new(stderr).read_to_string(&mut buf).await;
        buf
    });

    let mut reader = BufReader::new(stdout).lines();
    let mut final_usage: Option<Usage> = None;
    let mut got_any = false;
    let mut aborted = false;

    while let Some(line) = reader.next_line().await? {
        if abort.load(Ordering::SeqCst) {
            let _ = child.start_kill();
            aborted = true;
            break;
        }
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let v: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let event_type = v.get("type").and_then(|s| s.as_str()).unwrap_or("");

        match event_type {
            "stream_event" => {
                if let Some(evt) = v.get("event") {
                    let etype = evt.get("type").and_then(|s| s.as_str()).unwrap_or("");
                    if etype == "content_block_delta" {
                        if let Some(text) = evt
                            .get("delta")
                            .and_then(|d| d.get("text"))
                            .and_then(|t| t.as_str())
                        {
                            got_any = true;
                            emit(StreamEvent::Delta {
                                text: text.to_string(),
                            });
                        }
                    } else if etype == "message_delta" {
                        if let Some(usage) = evt.get("usage") {
                            if let Some(out) =
                                usage.get("output_tokens").and_then(|x| x.as_u64())
                            {
                                let input = usage
                                    .get("input_tokens")
                                    .and_then(|x| x.as_u64())
                                    .unwrap_or(0)
                                    as u32;
                                final_usage = Some(Usage {
                                    input_tokens: input,
                                    output_tokens: out as u32,
                                });
                            }
                        }
                    }
                }
            }
            "assistant" if !got_any => {
                if let Some(content) = v.get("message").and_then(|m| m.get("content")) {
                    if let Some(arr) = content.as_array() {
                        for block in arr {
                            if let Some(t) = block.get("text").and_then(|s| s.as_str()) {
                                emit(StreamEvent::Delta {
                                    text: t.to_string(),
                                });
                                got_any = true;
                            }
                        }
                    }
                }
            }
            "result" => {
                let is_error =
                    v.get("is_error").and_then(|b| b.as_bool()).unwrap_or(false);
                if is_error {
                    let msg = v
                        .get("result")
                        .and_then(|r| r.as_str())
                        .unwrap_or("Claude CLI hata döndü")
                        .to_string();
                    emit(StreamEvent::Error { error: msg });
                } else {
                    if let Some(usage) = v.get("usage") {
                        let input = usage
                            .get("input_tokens")
                            .and_then(|x| x.as_u64())
                            .unwrap_or(0) as u32;
                        let output = usage
                            .get("output_tokens")
                            .and_then(|x| x.as_u64())
                            .unwrap_or(0) as u32;
                        final_usage = Some(Usage {
                            input_tokens: input,
                            output_tokens: output,
                        });
                    }
                    emit(StreamEvent::Done {
                        usage: final_usage.clone(),
                        session_id: Some(session_id.clone()),
                    });
                }
            }
            _ => {}
        }
    }

    let status = child.wait().await?;
    let stderr_buf = stderr_task.await.unwrap_or_default();

    if aborted {
        emit(StreamEvent::Done {
            usage: final_usage,
            session_id: Some(session_id),
        });
    } else if !status.success() {
        let msg = if stderr_buf.trim().is_empty() {
            format!("Claude CLI çıkış kodu {}", status.code().unwrap_or(-1))
        } else {
            stderr_buf.trim().to_string()
        };
        emit(StreamEvent::Error { error: msg });
    }

    Ok(())
}

fn extract_text_from_content(content: &Value) -> String {
    if let Some(s) = content.as_str() {
        return s.to_string();
    }
    if let Some(arr) = content.as_array() {
        let mut text_parts = Vec::new();
        let mut image_paths = Vec::new();
        let mut file_paths = Vec::new();
        for block in arr {
            let btype = block.get("type").and_then(|s| s.as_str()).unwrap_or("");
            match btype {
                "text" => {
                    if let Some(t) = block.get("text").and_then(|s| s.as_str()) {
                        text_parts.push(t.to_string());
                    }
                }
                "image" => {
                    if let Some(path) = block.get("path").and_then(|s| s.as_str()) {
                        image_paths.push(path.to_string());
                    }
                }
                "file" => {
                    if let Some(path) = block.get("path").and_then(|s| s.as_str()) {
                        file_paths.push(path.to_string());
                    }
                }
                _ => {}
            }
        }

        let mut out = text_parts.join("\n");
        for p in image_paths {
            if !out.is_empty() {
                out.push_str("\n\n");
            }
            out.push_str(&format!("Lütfen şu görsele bak: {}", p));
        }
        for p in file_paths {
            if !out.is_empty() {
                out.push_str("\n\n");
            }
            out.push_str(&format!("İlgili dosya: {}", p));
        }
        return out;
    }
    String::new()
}

fn uuid_v4() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let pid = std::process::id() as u128;
    let mix = nanos.wrapping_mul(6364136223846793005).wrapping_add(pid);
    let mut bytes = [0u8; 16];
    bytes[..16].copy_from_slice(&mix.to_le_bytes());
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    format!(
        "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5], bytes[6], bytes[7],
        bytes[8], bytes[9], bytes[10], bytes[11],
        bytes[12], bytes[13], bytes[14], bytes[15]
    )
}

pub async fn list_mcp_servers() -> Result<Vec<McpServer>> {
    let path =
        resolve_claude_path().ok_or_else(|| anyhow!("Claude CLI bulunamadı."))?;

    let output = Command::new(&path)
        .args(["mcp", "list"])
        .stdin(Stdio::null())
        .output()
        .await?;

    if !output.status.success() {
        return Ok(Vec::new());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut servers = Vec::new();

    for line in stdout.lines() {
        let line = line.trim();
        if line.is_empty()
            || line.starts_with("No MCP")
            || line.starts_with("Configured")
            || line.starts_with("─")
            || line.starts_with("=")
        {
            continue;
        }

        if let Some((name, rest)) = line.split_once(':') {
            let rest = rest.trim();
            let (status, details) = if rest.contains("✓")
                || rest.to_lowercase().contains("connect")
            {
                ("connected".to_string(), Some(rest.to_string()))
            } else if rest.contains("✗") || rest.to_lowercase().contains("fail") {
                ("failed".to_string(), Some(rest.to_string()))
            } else {
                ("configured".to_string(), Some(rest.to_string()))
            };
            servers.push(McpServer {
                name: name.trim().to_string(),
                status,
                details,
            });
        } else if !line.is_empty() {
            servers.push(McpServer {
                name: line.to_string(),
                status: "configured".to_string(),
                details: None,
            });
        }
    }

    Ok(servers)
}

pub async fn open_login_terminal() -> Result<()> {
    let path = resolve_claude_path()
        .ok_or_else(|| anyhow!("Claude CLI bulunamadı."))?;

    #[cfg(target_os = "macos")]
    {
        let escaped = path.replace('\\', "\\\\").replace('"', "\\\"");
        let script = format!(
            "tell application \"Terminal\"\nactivate\ndo script \"{} /login || {} auth login || {}\"\nend tell",
            escaped, escaped, escaped
        );
        Command::new("osascript")
            .arg("-e")
            .arg(script)
            .stdin(Stdio::null())
            .spawn()?;
        return Ok(());
    }

    #[cfg(not(target_os = "macos"))]
    {
        Command::new(&path).spawn()?;
        Ok(())
    }
}

pub async fn install_cli<F>(mut emit: F) -> Result<()>
where
    F: FnMut(String) + Send,
{
    emit("Claude Code native installer indiriliyor…".into());

    let mut child = Command::new("sh")
        .arg("-c")
        .arg("curl -fsSL https://claude.ai/install.sh | bash")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| anyhow!("stdout açılamadı"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| anyhow!("stderr açılamadı"))?;

    let stderr_task = tokio::spawn(async move {
        let mut buf = String::new();
        let _ = BufReader::new(stderr).read_to_string(&mut buf).await;
        buf
    });

    let mut reader = BufReader::new(stdout).lines();
    while let Some(line) = reader.next_line().await? {
        emit(line);
    }

    let status = child.wait().await?;
    let stderr_buf = stderr_task.await.unwrap_or_default();

    if !status.success() {
        return Err(anyhow!(
            "Kurulum başarısız (kod {}): {}",
            status.code().unwrap_or(-1),
            stderr_buf.trim()
        ));
    }

    emit("Kurulum tamamlandı.".into());
    Ok(())
}

pub fn read_attachment(path: &str) -> Result<Attachment> {
    let p = Path::new(path);
    let canonical = std::fs::canonicalize(p).unwrap_or_else(|_| p.to_path_buf());
    let metadata = std::fs::metadata(&canonical)?;
    let name = canonical
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string());
    let mime = mime_guess::from_path(&canonical)
        .first_or_octet_stream()
        .to_string();

    let kind = classify(&mime);
    let preview = match kind.as_str() {
        "image" => {
            if metadata.len() > 20 * 1024 * 1024 {
                return Err(anyhow!("görsel 20MB'den büyük"));
            }
            let bytes = std::fs::read(&canonical)?;
            Some(base64::engine::general_purpose::STANDARD.encode(&bytes))
        }
        "text" => {
            if metadata.len() > 1024 * 1024 {
                None
            } else {
                let bytes = std::fs::read(&canonical)?;
                String::from_utf8(bytes).ok()
            }
        }
        _ => None,
    };

    Ok(Attachment {
        name,
        path: canonical.to_string_lossy().to_string(),
        mime_type: mime,
        size: metadata.len(),
        kind,
        preview,
    })
}

fn classify(mime: &str) -> String {
    if mime.starts_with("image/") {
        "image".into()
    } else if mime == "application/pdf" {
        "pdf".into()
    } else if mime.starts_with("text/")
        || mime == "application/json"
        || mime == "application/xml"
        || mime.contains("javascript")
        || mime.contains("typescript")
    {
        "text".into()
    } else {
        "other".into()
    }
}
