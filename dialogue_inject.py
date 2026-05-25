#!/usr/bin/env python3
"""
dialogue_inject — Claude Code hook for injecting prior dialogue context.

Queries SQLite for recent dialogue turns and prints them to stdout so
Claude Code injects them as system context.

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH, MAX_INJECT_TURNS, MAX_INJECT_CHARS
from db import get_connection


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
        ("SELECT speaker, content, ts FROM dialogue_turns WHERE project_dir = ? ORDER BY id DESC LIMIT ?",
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


def main():
    if not DB_PATH.exists():
        return

    try:
        conn = get_connection()
    except Exception:
        return

    session_id = get_session_id()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    try:
        turns = query_recent_turns(conn, session_id, project_dir)
        output = format_turns(turns)
        if output:
            print(output)
    except Exception:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()
