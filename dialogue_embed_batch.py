#!/usr/bin/env python3
"""
dialogue_embed_batch — Cron job for embedding dialogue turns into Qdrant.

Picks up unembedded turns from SQLite, embeds via Ollama, upserts to Qdrant.

Cron: */5 * * * * python3 /path/to/dialogue_embed_batch.py

Requires: Qdrant running, Ollama with embedding model available.
Optional — the core capture/inject pipeline works without this.
"""

import hashlib
import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DB_PATH, LOG_DIR, QDRANT_URL, QDRANT_COLLECTION,
    QDRANT_VECTOR_DIM, OLLAMA_URL, EMBED_MODEL, EMBED_BATCH_SIZE,
)


def log(msg: str):
    try:
        log_path = LOG_DIR / "dialogue_embed.log"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def ensure_collection() -> bool:
    """Create Qdrant collection if it doesn't exist."""
    try:
        urllib.request.urlopen(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", timeout=3)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            payload = json.dumps({
                "vectors": {"size": QDRANT_VECTOR_DIM, "distance": "Cosine"}
            }).encode()
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            urllib.request.urlopen(req, timeout=5)
            log(f"Created collection {QDRANT_COLLECTION}")
            return True
        return False
    except Exception:
        return False


def embed_text(text: str) -> list | None:
    """Get embedding vector from Ollama."""
    try:
        payload = json.dumps({"model": EMBED_MODEL, "input": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            embeddings = data.get("embeddings", [])
            return embeddings[0] if embeddings else None
    except Exception as e:
        log(f"Embed error: {e}")
        return None


def upsert_point(point_id: str, vector: list, payload: dict) -> bool:
    """Upsert a single point to Qdrant."""
    try:
        data = json.dumps({
            "points": [{"id": point_id, "vector": vector, "payload": payload}]
        }).encode()
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        log(f"Upsert error: {e}")
        return False


def make_point_id(session_id: str, turn_num: int) -> str:
    """Deterministic UUID-like ID from session + turn."""
    return hashlib.md5(f"{session_id}:{turn_num}".encode()).hexdigest()


def main():
    if not DB_PATH.exists():
        return

    try:
        urllib.request.urlopen(f"{QDRANT_URL}/healthz", timeout=2)
    except Exception:
        log("Qdrant unreachable")
        return

    if not ensure_collection():
        log("Failed to ensure collection")
        return

    from db import get_connection as _get_conn
    conn = _get_conn(timeout=5)

    try:
        rows = conn.execute(
            "SELECT id, session_id, turn_num, ts, speaker, content, project_dir "
            "FROM dialogue_turns WHERE embedding_done = 0 ORDER BY id LIMIT ?",
            (EMBED_BATCH_SIZE,)
        ).fetchall()

        if not rows:
            return

        embedded = 0
        for row_id, session_id, turn_num, ts, speaker, content, project_dir in rows:
            vector = embed_text(f"{speaker}: {content}")
            if vector is None:
                continue

            payload = {
                "session_id": session_id,
                "turn_num": turn_num,
                "speaker": speaker,
                "content": content[:1000],
                "ts": ts,
                "project_dir": project_dir or "",
            }

            if upsert_point(make_point_id(session_id, turn_num), vector, payload):
                conn.execute("UPDATE dialogue_turns SET embedding_done = 1 WHERE id = ?", (row_id,))
                embedded += 1

        conn.commit()
        log(f"Embedded {embedded}/{len(rows)} turns")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
