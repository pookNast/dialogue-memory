#!/usr/bin/env bash
# Install dialogue-memory hooks into Claude Code / OpenClaude
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="${CLAUDE_HOOKS_DIR:-$HOME/.claude/hooks}"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"

echo "=== dialogue-memory installer ==="
echo "Source:  $SCRIPT_DIR"
echo "Target:  $HOOKS_DIR"
echo "Config:  $SETTINGS"
echo ""

# 1. Copy scripts
mkdir -p "$HOOKS_DIR"
for f in config.py db.py dialogue_capture.py dialogue_inject.py dialogue_embed_batch.py dialogue_archive.py; do
    cp "$SCRIPT_DIR/$f" "$HOOKS_DIR/$f"
    echo "[+] Installed $f"
done

# 2. Print hook registration instructions
cat <<'HOOKS'

=== Manual hook registration ===

Add these entries to your settings.json hooks section:

UserPromptSubmit:
  {"type": "command", "command": "python3 $HOME/.claude/hooks/dialogue_capture.py --event UserPromptSubmit", "timeout": 500}

Stop:
  {"type": "command", "command": "python3 $HOME/.claude/hooks/dialogue_capture.py --event Stop", "timeout": 2000}

SessionStart:
  {"type": "command", "command": "python3 $HOME/.claude/hooks/dialogue_inject.py", "timeout": 1000}

PreCompact:
  {"type": "command", "command": "python3 $HOME/.claude/hooks/dialogue_inject.py", "timeout": 1000}

=== Optional: Qdrant embedding (requires Qdrant + Ollama) ===

  crontab -e
  */5 * * * * python3 ~/.claude/hooks/dialogue_embed_batch.py >> ~/.claude/logs/dialogue_embed.log 2>&1

=== Optional: Obsidian daily archive ===

  crontab -e
  55 23 * * * python3 ~/.claude/hooks/dialogue_archive.py >> ~/.claude/logs/dialogue_archive.log 2>&1

HOOKS

echo "[OK] Installation complete. Restart Claude Code to activate."
