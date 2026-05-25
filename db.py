"""
SQLite database initialization and helpers for dialogue-memory.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH, LOG_DIR

_schema_initialized = False


def get_connection(timeout: int = 2) -> sqlite3.Connection:
    """Get a WAL-mode SQLite connection, creating DB if needed.
    Auto-recovers from corruption by moving corrupt DB aside and recreating."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")

    global _schema_initialized

    # Integrity check — auto-recover from corruption
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()
        if result[0] != "ok":
            raise sqlite3.DatabaseError("quick_check failed")
        if not _schema_initialized:
            init_schema(conn)
            _schema_initialized = True
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
        conn.close()
        _recover_corrupt_db(str(e))
        _schema_initialized = False
        conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
        conn.execute("PRAGMA journal_mode=WAL")
        init_schema(conn)
        _schema_initialized = True

    return conn


def _recover_corrupt_db(reason: str):
    """Move corrupt DB aside and log the recovery."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    for suffix in ("", "-wal", "-shm"):
        src = Path(f"{DB_PATH}{suffix}")
        if src.exists():
            dst = Path(f"{DB_PATH}.corrupt-{ts}{suffix}")
            src.rename(dst)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "dialogue_capture.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] DB RECOVERED: {reason} — corrupt files moved to {DB_PATH}.corrupt-{ts}*\n")
    except Exception:
        pass


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
