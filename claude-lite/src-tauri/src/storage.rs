use anyhow::Result;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize)]
pub struct Conversation {
    pub id: String,
    pub title: String,
    pub model: String,
    #[serde(rename = "systemPrompt", default, skip_serializing_if = "Option::is_none")]
    pub system_prompt: Option<String>,
    #[serde(rename = "sessionId", default, skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(rename = "createdAt")]
    pub created_at: i64,
    #[serde(rename = "updatedAt")]
    pub updated_at: i64,
    pub messages: serde_json::Value,
}

pub struct Db {
    conn: Connection,
}

impl Db {
    pub fn open(path: &Path) -> Result<Self> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                system_prompt TEXT,
                session_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                messages TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);",
        )?;
        let has_session_id: bool = conn
            .query_row(
                "SELECT COUNT(*) FROM pragma_table_info('conversations') WHERE name='session_id'",
                [],
                |row| {
                    let count: i64 = row.get(0)?;
                    Ok(count > 0)
                },
            )
            .unwrap_or(false);
        if !has_session_id {
            let _ = conn.execute(
                "ALTER TABLE conversations ADD COLUMN session_id TEXT",
                [],
            );
        }
        Ok(Self { conn })
    }

    pub fn list(&self) -> Result<Vec<Conversation>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, title, model, system_prompt, session_id, created_at, updated_at, messages
             FROM conversations ORDER BY updated_at DESC LIMIT 200",
        )?;
        let rows = stmt.query_map([], row_to_conv)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(Into::into)
    }

    pub fn load(&self, id: &str) -> Result<Option<Conversation>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, title, model, system_prompt, session_id, created_at, updated_at, messages
             FROM conversations WHERE id = ?1",
        )?;
        let mut rows = stmt.query_map(params![id], row_to_conv)?;
        match rows.next() {
            Some(r) => Ok(Some(r?)),
            None => Ok(None),
        }
    }

    pub fn save(&self, c: &Conversation) -> Result<()> {
        let messages_json = serde_json::to_string(&c.messages)?;
        self.conn.execute(
            "INSERT INTO conversations (id, title, model, system_prompt, session_id, created_at, updated_at, messages)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
             ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                model=excluded.model,
                system_prompt=excluded.system_prompt,
                session_id=excluded.session_id,
                updated_at=excluded.updated_at,
                messages=excluded.messages",
            params![
                c.id,
                c.title,
                c.model,
                c.system_prompt,
                c.session_id,
                c.created_at,
                c.updated_at,
                messages_json
            ],
        )?;
        Ok(())
    }

    pub fn delete(&self, id: &str) -> Result<()> {
        self.conn
            .execute("DELETE FROM conversations WHERE id = ?1", params![id])?;
        Ok(())
    }
}

fn row_to_conv(row: &rusqlite::Row<'_>) -> rusqlite::Result<Conversation> {
    let messages: String = row.get(7)?;
    let messages: serde_json::Value = serde_json::from_str(&messages).unwrap_or(serde_json::json!([]));
    Ok(Conversation {
        id: row.get(0)?,
        title: row.get(1)?,
        model: row.get(2)?,
        system_prompt: row.get(3)?,
        session_id: row.get(4)?,
        created_at: row.get(5)?,
        updated_at: row.get(6)?,
        messages,
    })
}
