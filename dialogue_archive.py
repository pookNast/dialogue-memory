#!/usr/bin/env python3
"""
dialogue_archive — Daily cron job to export dialogue turns to Obsidian.

Exports today's dialogue turns to an Obsidian daily note, grouped by session.

Cron: 55 23 * * * python3 /path/to/dialogue_archive.py

Optional — the core capture/inject pipeline works without this.
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH, LOG_DIR, OBSIDIAN_DAILY_DIR


def log(msg: str):
    try:
        log_path = LOG_DIR / "dialogue_archive.log"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def main():
    if not DB_PATH.exists():
        return

    today = date.today().isoformat()
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")

    rows = conn.execute(
        "SELECT session_id, turn_num, ts, speaker, content "
        "FROM dialogue_turns WHERE DATE(ts) = ? ORDER BY session_id, turn_num",
        (today,)
    ).fetchall()
    conn.close()

    if not rows:
        log(f"No dialogue for {today}")
        return

    sessions = defaultdict(list)
    for session_id, turn_num, ts, speaker, content in rows:
        sessions[session_id].append((turn_num, ts, speaker, content))

    lines = [
        f"# Dialogue Log — {today}",
        "",
        f"Total: {len(rows)} turns across {len(sessions)} session(s)",
        "",
    ]

    for i, (session_id, turns) in enumerate(sessions.items(), 1):
        lines.append(f"## Session {i} (`{session_id[:8]}...`)")
        lines.append("")
        for turn_num, ts, speaker, content in turns:
            time_short = ts[11:16] if len(ts) > 16 else ts
            label = "**USER**" if speaker == "user" else "**ASSISTANT**"
            display = content[:800] + "..." if len(content) > 800 else content
            lines.append(f"_{time_short}_ {label}")
            lines.append(f"> {display}")
            lines.append("")
        lines.append("---")
        lines.append("")

    OBSIDIAN_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OBSIDIAN_DAILY_DIR / f"{today}-dialogue.md"

    mode = "a" if out_path.exists() else "w"
    with open(out_path, mode) as f:
        if mode == "a":
            f.write("\n\n---\n\n")
        f.write("\n".join(lines))

    log(f"Archived {len(rows)} turns to {out_path}")


if __name__ == "__main__":
    main()
