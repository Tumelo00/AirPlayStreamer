use std::sync::Mutex;
use tauri::{Emitter, Manager, State};

mod claude;
mod storage;

pub struct AppState {
    pub db: Mutex<storage::Db>,
}

#[tauri::command]
async fn check_claude_cli() -> claude::CliStatus {
    claude::check_cli().await
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
    channel: String,
    payload: claude::ChatRequest,
) -> Result<(), String> {
    let emit = move |evt: claude::StreamEvent| {
        let _ = app.emit(&channel, evt);
    };
    claude::stream_messages(payload, emit)
        .await
        .map_err(|e| e.to_string())
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
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
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_claude_cli,
            open_claude_login,
            install_claude_cli,
            send_message_stream,
            read_file_as_attachment,
            list_conversations,
            load_conversation,
            save_conversation,
            delete_conversation,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
