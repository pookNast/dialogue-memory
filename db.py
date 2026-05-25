"""
SQLite database initialization and helpers for dialogue-memory.
"""

import sqlite3
from pathlib import Path

from config import DB_PATH


def get_connection(timeout: int = 2) -> sqlite3.Connection:
    """Get a WAL-mode SQLite connection, creating DB if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection):
    """Create tables, indexes, and FTS on first run."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dialogue_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_num INTEGER NOT NULL,
            ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
            speaker TEXT NOT NULL CHECK(speaker IN ('user','assistant')),
            content TEXT NOT NULL,
            tokens_est INTEGER,
            embedding_done INTEGER DEFAULT 0,
            project_dir TEXT,
            UNIQUE(session_id, turn_num)
        );
        CREATE INDEX IF NOT EXISTS idx_dt_session ON dialogue_turns(session_id, ts);
        CREATE INDEX IF NOT EXISTS idx_dt_embed ON dialogue_turns(embedding_done) WHERE embedding_done = 0;
        CREATE INDEX IF NOT EXISTS idx_dt_project ON dialogue_turns(project_dir, ts DESC);
    """)
    # FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS dialogue_fts USING fts5(
            content, speaker, session_id,
            content='dialogue_turns', content_rowid='id'
        )
    """)
    # Auto-sync triggers for FTS
    for op, sql in [
        ("ai", "INSERT INTO dialogue_fts(rowid, content, speaker, session_id) VALUES (new.id, new.content, new.speaker, new.session_id)"),
        ("ad", "INSERT INTO dialogue_fts(dialogue_fts, rowid, content, speaker, session_id) VALUES('delete', old.id, old.content, old.speaker, old.session_id)"),
        ("au", "INSERT INTO dialogue_fts(dialogue_fts, rowid, content, speaker, session_id) VALUES('delete', old.id, old.content, old.speaker, old.session_id); INSERT INTO dialogue_fts(rowid, content, speaker, session_id) VALUES (new.id, new.content, new.speaker, new.session_id)"),
    ]:
        trigger_name = f"dialogue_fts_{op}"
        event = {"ai": "AFTER INSERT", "ad": "AFTER DELETE", "au": "AFTER UPDATE"}[op]
        conn.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {trigger_name}
            {event} ON dialogue_turns BEGIN {sql}; END
        """)
    conn.commit()
