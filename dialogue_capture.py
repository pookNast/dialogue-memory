#!/usr/bin/env python3
"""
dialogue_capture — OpenClaude hook for capturing conversation dialogue to SQLite.

Captures user prompts (UserPromptSubmit) and assistant text responses (Stop).
Strips tool calls, thinking blocks, and tool results — stores only dialogue.

Usage:
  python3 dialogue_capture.py --event UserPromptSubmit  # stdin: {session_id, prompt}
  python3 dialogue_capture.py --event Stop              # stdin: {session_id, transcript_path}

Hook registration (settings.json):
  "UserPromptSubmit": [{"matcher": "*", "hooks": [{"type": "command",
    "command": "python3 /path/to/dialogue_capture.py --event UserPromptSubmit", "timeout": 500}]}]
  "Stop": [{"matcher": "", "hooks": [{"type": "command",
    "command": "python3 /path/to/dialogue_capture.py --event Stop", "timeout": 2000}]}]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))
from config import MAX_CONTENT_LEN, LOG_DIR
from db import get_connection


def log(msg: str):
    """Append to log file."""
    try:
        log_path = LOG_DIR / "dialogue_capture.log"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def clean_text(text: str) -> str:
    """Remove thinking blocks, tool XML, and excessive whitespace."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    text = re.sub(r'<function_calls>.*?</function_calls>', '', text, flags=re.DOTALL)
    text = re.sub(r'<invoke[^>]*>.*?</invoke>', '', text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()[:MAX_CONTENT_LEN]


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def get_next_turn_num(conn, session_id: str, speaker: str) -> int:
    """Get the next turn number. User: even (0,2,4...), Assistant: odd (1,3,5...)."""
    row = conn.execute(
        "SELECT MAX(turn_num) FROM dialogue_turns WHERE session_id = ? AND speaker = ?",
        (session_id, speaker)
    ).fetchone()
    if row[0] is None:
        return 0 if speaker == "user" else 1
    return row[0] + 2


def capture_user_prompt(input_data: dict):
    """Store user prompt from UserPromptSubmit hook."""
    session_id = input_data.get("session_id", "")
    prompt = input_data.get("prompt", "")
    if not session_id or not prompt:
        return
    if prompt.startswith("/") or len(prompt.strip()) < 3:
        return

    content = clean_text(prompt)
    if not content:
        return

    conn = get_connection()
    turn_num = get_next_turn_num(conn, session_id, "user")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    conn.execute(
        "INSERT OR IGNORE INTO dialogue_turns (session_id, turn_num, speaker, content, tokens_est, project_dir) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, turn_num, "user", content, estimate_tokens(content), project_dir)
    )
    conn.commit()
    conn.close()


def capture_assistant_response(input_data: dict):
    """Extract assistant text responses from transcript at Stop."""
    session_id = input_data.get("session_id", "")
    transcript_path = input_data.get("transcript_path", "")
    if not session_id or not transcript_path or not os.path.exists(transcript_path):
        return

    assistant_texts = []
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue
                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if isinstance(content, str):
                    assistant_texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text.strip():
                                assistant_texts.append(text)
    except Exception:
        return

    if not assistant_texts:
        return

    conn = get_connection()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    for text in assistant_texts:
        content = clean_text(text)
        if not content or len(content) < 10:
            continue
        turn_num = get_next_turn_num(conn, session_id, "assistant")
        conn.execute(
            "INSERT OR IGNORE INTO dialogue_turns (session_id, turn_num, speaker, content, tokens_est, project_dir) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, turn_num, "assistant", content, estimate_tokens(content), project_dir)
        )

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Capture dialogue turns to SQLite")
    parser.add_argument("--event", required=True, choices=["UserPromptSubmit", "Stop"])
    args = parser.parse_args()

    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    try:
        if args.event == "UserPromptSubmit":
            capture_user_prompt(input_data)
            log(f"user session={input_data.get('session_id','?')[:8]}")
        elif args.event == "Stop":
            capture_assistant_response(input_data)
            log(f"assistant session={input_data.get('session_id','?')[:8]}")
    except Exception as e:
        log(f"ERROR: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
