# W0-S4: Add unit tests

## Task
Create comprehensive unit tests for the dialogue-memory pipeline.

## Context
- Project: `/home/pook/dialogue-memory/`
- Core modules: `db.py`, `dialogue_capture.py`, `dialogue_inject.py`
- Uses stdlib only (sqlite3, json, re, pathlib)
- Tests must use in-memory SQLite (not the live DB)

## Requirements
1. `tests/test_db.py`:
   - Schema creation in memory DB
   - FTS5 trigger sync (insert, update, delete)
   - WAL mode enabled
   - Corruption recovery (mock corrupt file)
   - Prune old turns (after W0-S2)

2. `tests/test_capture.py`:
   - `clean_text()` strips think blocks, function_calls, invoke tags
   - `clean_text()` preserves normal text
   - `clean_text()` truncates to MAX_CONTENT_LEN
   - `estimate_tokens()` returns ~len/4
   - `get_next_turn_num()` even for user, odd for assistant
   - `capture_user_prompt()` skips slash commands
   - `capture_user_prompt()` skips short prompts
   - UNIQUE constraint prevents duplicate turns

3. `tests/test_inject.py`:
   - `format_turns()` produces markdown
   - `format_turns()` respects MAX_INJECT_CHARS limit
   - `query_recent_turns()` prefers current session
   - `query_recent_turns()` falls back to project_dir
   - Empty DB returns empty string

## Acceptance Criteria
- [ ] All tests pass: `python3 -m pytest tests/ -v`
- [ ] No tests touch the live DB
- [ ] Tests run in <5 seconds
- [ ] >=80% branch coverage on core modules

## Files to create
- `tests/__init__.py`
- `tests/test_db.py`
- `tests/test_capture.py`
- `tests/test_inject.py`

## Verification
```bash
cd /home/pook/dialogue-memory && python3 -m pytest tests/ -v
```
