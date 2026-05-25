#!/usr/bin/env python3
"""
dialogue_inject — OpenClaude hook for injecting prior dialogue context.

Queries SQLite for recent dialogue turns and prints them to stdout so
OpenClaude injects them as system context.

On SessionStart: last N turns from most recent session in same project_dir.
On PreCompact: last N turns from current session (preserves across compaction).

Hook registration (settings.json):
  "SessionStart": [{"matcher": "*", "hooks": [{"type": "command",
    "command": "python3 /path/to/dialogue_inject.py", "timeout": 1000}]}]
  "PreCompact": [{"matcher": "*", "hooks": [{"type": "command",
    "command": "python3 /path/to/dialogue_inject.py", "timeout": 1000}]}]
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from datetime import datetime
from config import (
    DB_PATH, LOG_DIR, MAX_INJECT_TURNS, MAX_INJECT_CHARS,
    SEMANTIC_INJECT, QDRANT_URL, QDRANT_COLLECTION,
    OLLAMA_URL, EMBED_MODEL,
)
from db import get_connection


def log(msg: str):
    """Append to log file."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "dialogue_inject.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def get_session_id() -> str:
    """Read session_id from stdin JSON if available."""
    try:
        input_data = json.load(sys.stdin)
        return input_data.get("session_id", "")
    except (json.JSONDecodeError, ValueError):
        return ""


def query_recent_turns(conn, session_id: str, project_dir: str) -> list:
    """Query recent dialogue turns — current session first, then same project, then global."""
    for query, params in [
        ("SELECT speaker, content, ts FROM dialogue_turns WHERE session_id = ? ORDER BY turn_num DESC LIMIT ?",
         (session_id, MAX_INJECT_TURNS)),
        ("SELECT speaker, content, ts FROM dialogue_turns WHERE project_dir = ? ORDER BY ts DESC LIMIT ?",
         (project_dir, MAX_INJECT_TURNS)),
        ("SELECT speaker, content, ts FROM dialogue_turns ORDER BY id DESC LIMIT ?",
         (MAX_INJECT_TURNS,)),
    ]:
        if not params[0]:  # skip empty session_id or project_dir
            continue
        rows = conn.execute(query, params).fetchall()
        if rows:
            return list(reversed(rows))
    return []


def format_turns(turns: list) -> str:
    """Format turns as concise markdown for system context injection."""
    if not turns:
        return ""

    lines = ["## Prior Dialogue Context"]
    total_chars = 0

    for speaker, content, ts in turns:
        truncated = content[:500] if len(content) > 500 else content
        label = "USER" if speaker == "user" else "ASSISTANT"
        time_short = ts[11:16] if len(ts) > 16 else ts
        line = f"**{label}** ({time_short}): {truncated}"

        if total_chars + len(line) > MAX_INJECT_CHARS:
            break
        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines) if len(lines) > 1 else ""


def embed_query(text: str) -> list | None:
    """Get embedding vector from Ollama (timeout 3s)."""
    try:
        payload = json.dumps({"model": EMBED_MODEL, "input": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            embeddings = data.get("embeddings", [])
            return embeddings[0] if embeddings else None
    except Exception:
        return None


def semantic_search(query: str, limit: int = 5) -> list:
    """Search Qdrant for similar dialogue turns. Returns list of payload dicts."""
    vector = embed_query(query)
    if not vector:
        return []

    try:
        data = json.dumps({
            "vector": vector,
            "limit": limit,
            "with_payload": True,
        }).encode()
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            results = json.loads(resp.read()).get("result", [])
            return [r["payload"] for r in results if "payload" in r]
    except Exception:
        return []


def format_semantic_turns(payloads: list) -> str:
    """Format Qdrant results as dialogue context."""
    if not payloads:
        return ""

    lines = ["## Semantic Recall (no recent turns found)"]
    for p in payloads:
        speaker = p.get("speaker", "unknown")
        content = (p.get("content", ""))[:500]
        ts = p.get("ts", "")
        label = "USER" if speaker == "user" else "ASSISTANT"
        time_short = ts[11:16] if len(ts) > 16 else ts
        lines.append(f"**{label}** ({time_short}): {content}")

    return "\n".join(lines)


def main():
    if not DB_PATH.exists():
        return

    try:
        conn = get_connection()
    except Exception as e:
        log(f"ERROR get_connection: {e}")
        return

    session_id = get_session_id()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    try:
        turns = query_recent_turns(conn, session_id, project_dir)
        if turns:
            output = format_turns(turns)
        elif SEMANTIC_INJECT:
            # Fallback: semantic search when no recent SQLite turns
            payloads = semantic_search(project_dir, limit=5)
            output = format_semantic_turns(payloads)
        else:
            output = ""
        if output:
            print(output)
    except Exception as e:
        log(f"ERROR inject: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
