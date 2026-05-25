# dialogue-memory

Rolling conversation memory for Claude Code and OpenClaude with local LLMs.

## Problem

Local LLMs have limited context windows (32K–256K tokens). Long coding sessions hit 503 errors or lose conversation context when auto-compaction triggers. ~90% of the context window is consumed by tool results and reasoning tokens, not actual dialogue.

## Solution

Hook-based pipeline that captures **dialogue only** (user prompts + assistant text responses), stores it in SQLite, and re-injects relevant context on session start or compaction. Tool calls, thinking blocks, and tool results are stripped — only human-readable conversation is preserved.

```
User msg ──→ [UserPromptSubmit hook] ──→ SQLite
                                              │
Assistant ──→ [Stop hook] ─────────────→ SQLite
                                              │
     ┌────────────────────────────────────────┘
     │
     ├──→ [SessionStart / PreCompact hook] ──→ Inject last 8 turns as system context
     ├──→ [Cron 5min] ──→ Embed to Qdrant (semantic search)
     └──→ [Cron daily] ──→ Archive to Obsidian vault
```

## Components

| Script | Hook Event | Purpose |
|--------|-----------|---------|
| `dialogue_capture.py` | UserPromptSubmit, Stop | Store dialogue turns in SQLite |
| `dialogue_inject.py` | SessionStart, PreCompact | Re-inject prior dialogue as system context |
| `dialogue_embed_batch.py` | Cron (5 min) | Embed turns to Qdrant for semantic search |
| `dialogue_archive.py` | Cron (daily) | Export to Obsidian daily notes |

Only `dialogue_capture.py` and `dialogue_inject.py` are required. The Qdrant and Obsidian components are optional enhancements.

## Requirements

- Python 3.8+
- Claude Code or [OpenClaude](https://github.com/Gitlawb/openclaude) with hook support
- SQLite3 (included in Python stdlib)
- **Optional:** Qdrant vector database + Ollama with `nomic-embed-text`
- **Optional:** Obsidian vault

## Install

```bash
git clone <this-repo> ~/dialogue-memory
cd ~/dialogue-memory
bash install.sh
```

Then add the hook entries to your `~/.claude/settings.json` (printed by the installer).

## Configuration

All settings via environment variables (defaults work out of the box):

| Variable | Default | Description |
|----------|---------|-------------|
| `DIALOGUE_MEMORY_DB` | `~/.claude/dialogue_memory.db` | SQLite database path |
| `DIALOGUE_MEMORY_LOG_DIR` | `~/.claude/logs/` | Log directory |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `DIALOGUE_MEMORY_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `DIALOGUE_MEMORY_COLLECTION` | `dialogue_memory` | Qdrant collection name |
| `DIALOGUE_MEMORY_MAX_INJECT_TURNS` | `8` | Max turns to inject |
| `DIALOGUE_MEMORY_MAX_INJECT_CHARS` | `4000` | Max injection size (~1K tokens) |
| `DIALOGUE_MEMORY_MAX_CONTENT` | `2000` | Max chars per stored turn |
| `DIALOGUE_MEMORY_OBSIDIAN_DIR` | `~/obsidian-vault/Daily/` | Obsidian archive directory |

## How It Works

### Capture (UserPromptSubmit + Stop)

On every user prompt, the hook stores the raw text (after stripping slash commands and short inputs). On session stop, it reads the transcript JSONL and extracts only `type=assistant` entries with `content.type=text` — skipping `thinking`, `tool_use`, and `tool_result` blocks.

### Injection (SessionStart + PreCompact)

When a new session starts or auto-compaction triggers, the hook queries SQLite for the most recent dialogue turns (same session for PreCompact, same project directory for SessionStart) and prints them to stdout. Claude Code injects this as a system-level context message.

### Semantic Search (Cron, optional)

Every 5 minutes, unembedded turns are sent to Ollama for vector embedding, then upserted to Qdrant. This enables semantic queries like "what did we discuss about authentication?" across sessions.

### Obsidian Archive (Cron, optional)

At 23:55 daily, all dialogue turns from the day are exported to an Obsidian-compatible markdown file grouped by session.

## Recommended: Auto-Compact Threshold

Set this in your shell profile or launcher script to trigger compaction before the context window fills:

```bash
export CLAUDE_CODE_AUTO_COMPACT_THRESHOLD=80  # compact at 80% of context window
```

## SQLite Schema

```sql
CREATE TABLE dialogue_turns (
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
-- FTS5 full-text search index auto-created
-- Triggers auto-sync FTS on insert/update/delete
```

## Query Examples

```bash
# Recent dialogue
sqlite3 ~/.claude/dialogue_memory.db \
  "SELECT speaker, substr(content,1,80) FROM dialogue_turns ORDER BY id DESC LIMIT 10;"

# Full-text search
sqlite3 ~/.claude/dialogue_memory.db \
  "SELECT speaker, content FROM dialogue_fts WHERE dialogue_fts MATCH 'authentication';"

# Embedding backlog
sqlite3 ~/.claude/dialogue_memory.db \
  "SELECT COUNT(*) FROM dialogue_turns WHERE embedding_done = 0;"

# Stats by session
sqlite3 ~/.claude/dialogue_memory.db \
  "SELECT session_id, COUNT(*), MIN(ts), MAX(ts) FROM dialogue_turns GROUP BY session_id ORDER BY MAX(ts) DESC LIMIT 5;"
```

## License

MIT
