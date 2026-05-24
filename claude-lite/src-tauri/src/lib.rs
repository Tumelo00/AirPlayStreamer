use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, State,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

mod claude;
mod memory;
mod preferences;
mod storage;
mod terminal;

pub struct AppState {
    pub db: Mutex<storage::Db>,
    pub pty: terminal::PtyManager,
    pub abort: Arc<AtomicBool>,
    pub data_dir: std::path::PathBuf,
}

#[tauri::command]
async fn check_claude_cli() -> claude::CliStatus {
    claude::check_cli().await
}

#[tauri::command]
async fn list_mcp_servers() -> Result<Vec<claude::McpServer>, String> {
    claude::list_mcp_servers().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn open_claude_login() -> Result<(), String> {
    claude::open_login_terminal()
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn install_claude_cli(app: tauri::AppHandle, channel: String) -> Result<(), String> {
    let emit = move |line: String| {
        let _ = app.emit(&channel, line);
    };
    claude::install_cli(emit).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn send_message_stream(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    channel: String,
    mut payload: claude::ChatRequest,
) -> Result<(), String> {
    state.abort.store(false, Ordering::SeqCst);
    let abort = state.abort.clone();
    let prefs = preferences::load(&state.data_dir).ok();
    let cwd = prefs.as_ref().and_then(|p| p.workspace_dir.clone());

    let mem = memory::load(&state.data_dir).unwrap_or_default();
    let merged = memory::merge_into_system_prompt(&mem, payload.system.as_deref());
    if merged.is_some() {
        payload.system = merged;
    }

    let emit = move |evt: claude::StreamEvent| {
        let _ = app.emit(&channel, evt);
    };
    claude::stream_messages(payload, abort, cwd, emit)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn abort_stream(state: State<'_, AppState>) {
    state.abort.store(true, Ordering::SeqCst);
}

#[tauri::command]
fn save_pasted_image(
    app: AppHandle,
    bytes: Vec<u8>,
    mime: String,
) -> Result<claude::Attachment, String> {
    let dir = app
        .path()
        .app_cache_dir()
        .map_err(|e| e.to_string())?
        .join("pasted");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let ext = match mime.as_str() {
        "image/png" => "png",
        "image/jpeg" => "jpg",
        "image/gif" => "gif",
        "image/webp" => "webp",
        _ => "png",
    };
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let path = dir.join(format!("pasted-{}.{}", ts, ext));
    std::fs::write(&path, &bytes).map_err(|e| e.to_string())?;
    claude::read_attachment(&path.to_string_lossy()).map_err(|e| e.to_string())
}

#[tauri::command]
async fn read_file_as_attachment(path: String) -> Result<claude::Attachment, String> {
    claude::read_attachment(&path).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_conversations(state: State<'_, AppState>) -> Result<Vec<storage::Conversation>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.list().map_err(|e| e.to_string())
}

#[tauri::command]
fn load_conversation(
    state: State<'_, AppState>,
    id: String,
) -> Result<Option<storage::Conversation>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.load(&id).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_conversation(
    state: State<'_, AppState>,
    conversation: storage::Conversation,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.save(&conversation).map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_conversation(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.delete(&id).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_preferences(state: State<'_, AppState>) -> Result<preferences::Preferences, String> {
    preferences::load(&state.data_dir).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_preferences(
    state: State<'_, AppState>,
    preferences: preferences::Preferences,
) -> Result<(), String> {
    preferences::save(&state.data_dir, &preferences).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_memory(state: State<'_, AppState>) -> Result<String, String> {
    memory::load(&state.data_dir).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_memory(state: State<'_, AppState>, content: String) -> Result<(), String> {
    memory::save(&state.data_dir, &content).map_err(|e| e.to_string())
}

#[tauri::command]
fn append_memory(state: State<'_, AppState>, entry: String) -> Result<(), String> {
    memory::append(&state.data_dir, &entry).map_err(|e| e.to_string())
}

#[tauri::command]
fn read_workspace_claude_md(state: State<'_, AppState>) -> Result<Option<String>, String> {
    let prefs = preferences::load(&state.data_dir).map_err(|e| e.to_string())?;
    let Some(ws) = prefs.workspace_dir else {
        return Ok(None);
    };
    Ok(memory::read_workspace_claude_md(std::path::Path::new(&ws)))
}

#[tauri::command]
fn write_workspace_claude_md(
    state: State<'_, AppState>,
    content: String,
) -> Result<(), String> {
    let prefs = preferences::load(&state.data_dir).map_err(|e| e.to_string())?;
    let ws = prefs
        .workspace_dir
        .ok_or_else(|| "Çalışma dizini ayarlanmamış".to_string())?;
    let path = std::path::Path::new(&ws).join("CLAUDE.md");
    let tmp = std::path::Path::new(&ws).join("CLAUDE.md.tmp");
    std::fs::write(&tmp, &content).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn pty_open(
    app: AppHandle,
    state: State<'_, AppState>,
    id: String,
    cols: u16,
    rows: u16,
    shell: Option<String>,
    cwd: Option<String>,
) -> Result<(), String> {
    state
        .pty
        .open(app, id, cols, rows, shell, cwd)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn pty_write(state: State<'_, AppState>, id: String, data: String) -> Result<(), String> {
    state.pty.write(&id, &data).map_err(|e| e.to_string())
}

#[tauri::command]
fn pty_resize(
    state: State<'_, AppState>,
    id: String,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    state.pty.resize(&id, cols, rows).map_err(|e| e.to_string())
}

#[tauri::command]
fn pty_close(state: State<'_, AppState>, id: String) -> Result<(), String> {
    state.pty.close(&id).map_err(|e| e.to_string())
}

fn toggle_main_window(app: &AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        match win.is_visible() {
            Ok(true) => {
                let _ = win.hide();
            }
            _ => {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }
    }
}

fn cleanup_pasted_images(app: &AppHandle) {
    let Ok(cache) = app.path().app_cache_dir() else {
        return;
    };
    let dir = cache.join("pasted");
    if !dir.exists() {
        return;
    }
    let cutoff = std::time::SystemTime::now()
        .checked_sub(std::time::Duration::from_secs(30 * 24 * 60 * 60));
    let Some(cutoff) = cutoff else { return };

    let mut total_bytes: u64 = 0;
    let mut entries: Vec<_> = std::fs::read_dir(&dir)
        .ok()
        .map(|it| it.flatten().collect())
        .unwrap_or_default();

    for entry in &entries {
        if let Ok(meta) = entry.metadata() {
            total_bytes = total_bytes.saturating_add(meta.len());
        }
    }

    const MAX_BYTES: u64 = 500 * 1024 * 1024;

    if total_bytes > MAX_BYTES {
        entries.sort_by_key(|e| {
            e.metadata().and_then(|m| m.modified()).ok()
        });
        let mut remaining = total_bytes;
        for entry in &entries {
            if remaining <= MAX_BYTES / 2 {
                break;
            }
            if let Ok(meta) = entry.metadata() {
                let size = meta.len();
                if std::fs::remove_file(entry.path()).is_ok() {
                    remaining = remaining.saturating_sub(size);
                }
            }
        }
        return;
    }

    for entry in entries {
        if let Ok(meta) = entry.metadata() {
            if let Ok(modified) = meta.modified() {
                if modified < cutoff {
                    let _ = std::fs::remove_file(entry.path());
                }
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    #[cfg(debug_assertions)]
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if event.state == ShortcutState::Pressed
                        && shortcut.matches(Modifiers::SUPER | Modifiers::SHIFT, Code::Space)
                    {
                        toggle_main_window(app);
                    }
                })
                .build(),
        )
        .setup(|app| {
            let data_dir = app
                .path()
                .app_data_dir()
                .expect("could not resolve app data dir");
            std::fs::create_dir_all(&data_dir).ok();
            let db_path = data_dir.join("claude-lite.db");
            let db = storage::Db::open(&db_path)?;
            app.manage(AppState {
                db: Mutex::new(db),
                pty: terminal::PtyManager::new(),
                abort: Arc::new(AtomicBool::new(false)),
                data_dir: data_dir.clone(),
            });

            let shortcut = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::Space);
            if let Err(_e) = app.global_shortcut().register(shortcut) {
                #[cfg(debug_assertions)]
                tracing::warn!("Global shortcut kaydedilemedi: {}", _e);
            }

            let handle_for_cleanup = app.app_handle().clone();
            cleanup_pasted_images(&handle_for_cleanup);

            let show_item = MenuItem::with_id(app, "show", "Göster / Gizle", true, None::<&str>)?;
            let new_item = MenuItem::with_id(app, "new", "Yeni Sohbet", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Çıkış", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &new_item, &quit_item])?;

            let _tray = TrayIconBuilder::with_id("main-tray")
                .tooltip("Claude Lite")
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => toggle_main_window(app),
                    "new" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                            let _ = app.emit("menu:new-chat", ());
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_claude_cli,
            list_mcp_servers,
            open_claude_login,
            install_claude_cli,
            send_message_stream,
            abort_stream,
            read_file_as_attachment,
            save_pasted_image,
            list_conversations,
            load_conversation,
            save_conversation,
            delete_conversation,
            load_preferences,
            save_preferences,
            load_memory,
            save_memory,
            append_memory,
            read_workspace_claude_md,
            write_workspace_claude_md,
            pty_open,
            pty_write,
            pty_resize,
            pty_close,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
