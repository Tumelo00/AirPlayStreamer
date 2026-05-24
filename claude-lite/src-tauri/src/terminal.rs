use anyhow::{anyhow, Result};
use portable_pty::{native_pty_system, CommandBuilder, MasterPty, PtySize};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter};

pub struct PtySession {
    master: Arc<Mutex<Box<dyn MasterPty + Send>>>,
}

pub struct PtyManager {
    sessions: Mutex<HashMap<String, PtySession>>,
}

impl PtyManager {
    pub fn new() -> Self {
        Self {
            sessions: Mutex::new(HashMap::new()),
        }
    }

    pub fn open(
        &self,
        app: AppHandle,
        id: String,
        cols: u16,
        rows: u16,
        shell: Option<String>,
        cwd: Option<String>,
    ) -> Result<()> {
        let pty_system = native_pty_system();
        let pair = pty_system.openpty(PtySize {
            cols,
            rows,
            pixel_width: 0,
            pixel_height: 0,
        })?;

        let shell_path = shell.unwrap_or_else(default_shell);
        let mut cmd = CommandBuilder::new(&shell_path);
        cmd.env("TERM", "xterm-256color");
        cmd.env("LANG", "en_US.UTF-8");
        if let Some(dir) = cwd {
            cmd.cwd(dir);
        } else if let Some(home) = std::env::var_os("HOME") {
            cmd.cwd(home);
        }

        let mut child = pair.slave.spawn_command(cmd)?;
        drop(pair.slave);

        let master = Arc::new(Mutex::new(pair.master));
        let session = PtySession {
            master: master.clone(),
        };
        self.sessions.lock().unwrap().insert(id.clone(), session);

        let reader_master = master.clone();
        let read_channel = format!("pty:{}:data", id);
        let exit_channel = format!("pty:{}:exit", id);
        let app_for_read = app.clone();
        let app_for_exit = app.clone();
        let id_for_exit = id.clone();

        std::thread::spawn(move || {
            let mut reader = match reader_master.lock().unwrap().try_clone_reader() {
                Ok(r) => r,
                Err(_) => return,
            };
            let mut buf = [0u8; 4096];
            loop {
                match reader.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        let chunk = String::from_utf8_lossy(&buf[..n]).to_string();
                        let _ = app_for_read.emit(&read_channel, chunk);
                    }
                    Err(_) => break,
                }
            }
        });

        std::thread::spawn(move || {
            let _ = child.wait();
            let _ = app_for_exit.emit(&exit_channel, id_for_exit);
        });

        Ok(())
    }

    pub fn write(&self, id: &str, data: &str) -> Result<()> {
        let sessions = self.sessions.lock().unwrap();
        let session = sessions
            .get(id)
            .ok_or_else(|| anyhow!("session bulunamadı"))?;
        let mut master = session.master.lock().unwrap();
        let mut writer = master.take_writer()?;
        writer.write_all(data.as_bytes())?;
        writer.flush()?;
        Ok(())
    }

    pub fn resize(&self, id: &str, cols: u16, rows: u16) -> Result<()> {
        let sessions = self.sessions.lock().unwrap();
        let session = sessions
            .get(id)
            .ok_or_else(|| anyhow!("session bulunamadı"))?;
        let master = session.master.lock().unwrap();
        master.resize(PtySize {
            cols,
            rows,
            pixel_width: 0,
            pixel_height: 0,
        })?;
        Ok(())
    }

    pub fn close(&self, id: &str) -> Result<()> {
        self.sessions.lock().unwrap().remove(id);
        Ok(())
    }
}

fn default_shell() -> String {
    std::env::var("SHELL").unwrap_or_else(|_| {
        if cfg!(target_os = "windows") {
            "powershell.exe".into()
        } else if cfg!(target_os = "macos") {
            "/bin/zsh".into()
        } else {
            "/bin/bash".into()
        }
    })
}
