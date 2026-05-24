use anyhow::{anyhow, Result};
use base64::Engine;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[derive(Debug, Deserialize, Serialize)]
pub struct ChatRequest {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
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
    #[serde(skip_serializing_if = "Option::is_none")]
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

fn resolve_claude_path() -> Option<String> {
    let mut candidates: Vec<String> = vec![
        "claude".into(),
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
    for c in &candidates {
        if let Ok(output) = std::process::Command::new(c).arg("--version").output() {
            if output.status.success() {
                return Some(c.clone());
            }
        }
    }
    None
}

pub async fn install_cli<F>(mut emit: F) -> Result<()>
where
    F: FnMut(String) + Send,
{
    emit("Claude Code native installer indiriliyor…".into());

    let mut child = Command::new("sh")
        .arg("-c")
        .arg("curl -fsSL https://claude.ai/install.sh | bash")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    if let Some(stdout) = child.stdout.take() {
        let mut reader = BufReader::new(stdout).lines();
        while let Some(line) = reader.next_line().await? {
            emit(line);
        }
    }

    let status = child.wait().await?;
    if !status.success() {
        let mut err = String::new();
        if let Some(mut e) = child.stderr.take() {
            use tokio::io::AsyncReadExt;
            let _ = e.read_to_string(&mut err).await;
        }
        return Err(anyhow!(
            "Kurulum başarısız (kod {}): {}",
            status.code().unwrap_or(-1),
            err.trim()
        ));
    }

    emit("Kurulum tamamlandı.".into());
    Ok(())
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

    let logged_in = match Command::new(&path)
        .args(["-p", "ping", "--output-format", "json"])
        .stdin(Stdio::null())
        .output()
        .await
    {
        Ok(o) => {
            let stdout = String::from_utf8_lossy(&o.stdout);
            o.status.success() && !stdout.contains("\"is_error\":true")
        }
        Err(_) => false,
    };

    CliStatus {
        installed: true,
        version,
        logged_in,
        path: Some(path),
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

pub async fn stream_messages<F>(req: ChatRequest, mut emit: F) -> Result<()>
where
    F: FnMut(StreamEvent) + Send,
{
    let path = resolve_claude_path()
        .ok_or_else(|| anyhow!("Claude CLI bulunamadı. `npm install -g @anthropic-ai/claude-code` ile kur."))?;

    let last_user = req
        .messages
        .iter()
        .rev()
        .find(|m| m.role == "user")
        .ok_or_else(|| anyhow!("user mesajı yok"))?;

    let prompt = extract_text_from_content(&last_user.content);

    let model = model_alias(&req.model);
    let session_id = req
        .session_id
        .clone()
        .unwrap_or_else(|| uuid_v4());

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

    cmd.stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| anyhow!("stdout açılamadı"))?;
    let mut reader = BufReader::new(stdout).lines();

    let mut accumulated = String::new();
    let mut final_usage: Option<Usage> = None;

    while let Some(line) = reader.next_line().await? {
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
                            accumulated.push_str(text);
                            emit(StreamEvent::Delta {
                                text: text.to_string(),
                            });
                        }
                    }
                }
            }
            "assistant" => {
                if let Some(content) = v.get("message").and_then(|m| m.get("content")) {
                    if let Some(arr) = content.as_array() {
                        let mut text_chunk = String::new();
                        for block in arr {
                            if let Some(t) = block.get("text").and_then(|s| s.as_str()) {
                                text_chunk.push_str(t);
                            }
                        }
                        if !text_chunk.is_empty() && !accumulated.contains(&text_chunk) {
                            let new_part =
                                text_chunk.strip_prefix(&accumulated as &str).unwrap_or("");
                            if !new_part.is_empty() {
                                accumulated.push_str(new_part);
                                emit(StreamEvent::Delta {
                                    text: new_part.to_string(),
                                });
                            }
                        }
                    }
                }
            }
            "result" => {
                let is_error = v.get("is_error").and_then(|b| b.as_bool()).unwrap_or(false);
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
    if !status.success() {
        let mut stderr_buf = String::new();
        if let Some(mut err) = child.stderr.take() {
            use tokio::io::AsyncReadExt;
            let _ = err.read_to_string(&mut stderr_buf).await;
        }
        let msg = format!(
            "Claude CLI çıkış kodu {}: {}",
            status.code().unwrap_or(-1),
            stderr_buf.trim()
        );
        emit(StreamEvent::Error { error: msg });
    }

    Ok(())
}

fn extract_text_from_content(content: &Value) -> String {
    if let Some(s) = content.as_str() {
        return s.to_string();
    }
    if let Some(arr) = content.as_array() {
        let mut out = String::new();
        for block in arr {
            if let Some(t) = block.get("text").and_then(|s| s.as_str()) {
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(t);
            }
            if block.get("type").and_then(|s| s.as_str()) == Some("image") {
                if let Some(path) = block.get("path").and_then(|s| s.as_str()) {
                    if !out.is_empty() {
                        out.push('\n');
                    }
                    out.push_str(&format!("[Görsel ekli: {}]", path));
                }
            }
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
    let mut bytes = [0u8; 16];
    for (i, b) in nanos.to_le_bytes().iter().enumerate() {
        bytes[i] = *b;
    }
    for i in 8..16 {
        bytes[i] = ((nanos.rotate_left((i * 7) as u32)) as u8) ^ (i as u8);
    }
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

pub async fn open_login_terminal() -> Result<()> {
    let path = resolve_claude_path()
        .ok_or_else(|| anyhow!("Claude CLI bulunamadı."))?;

    #[cfg(target_os = "macos")]
    {
        let script = format!(
            "tell application \"Terminal\" to do script \"{} login\"",
            path.replace('"', "\\\"")
        );
        Command::new("osascript").arg("-e").arg(script).spawn()?;
        return Ok(());
    }

    #[cfg(not(target_os = "macos"))]
    {
        Command::new(&path).arg("login").spawn()?;
        Ok(())
    }
}

pub fn read_attachment(path: &str) -> Result<Attachment> {
    let p = Path::new(path);
    let metadata = std::fs::metadata(p)?;
    let name = p
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string());
    let mime = mime_guess::from_path(p)
        .first_or_octet_stream()
        .to_string();

    let kind = classify(&mime);
    let preview = match kind.as_str() {
        "image" => {
            let bytes = std::fs::read(p)?;
            if bytes.len() > 20 * 1024 * 1024 {
                return Err(anyhow!("görsel 20MB'den büyük"));
            }
            Some(base64::engine::general_purpose::STANDARD.encode(&bytes))
        }
        "text" => {
            let bytes = std::fs::read(p)?;
            if bytes.len() > 1024 * 1024 {
                return Err(anyhow!("metin dosyası 1MB'den büyük"));
            }
            String::from_utf8(bytes).ok()
        }
        _ => None,
    };

    Ok(Attachment {
        name,
        path: path.to_string(),
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
