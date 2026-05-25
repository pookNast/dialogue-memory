# W0-S1: Add transcript_path validation

## Task
Add input validation to `dialogue_capture.py` for the `transcript_path` field received from the Stop hook.

## Context
- File: `/home/pook/dialogue-memory/dialogue_capture.py`
- Function: `capture_assistant_response()`
- The `transcript_path` comes from Claude Code's Stop hook via stdin JSON
- Currently no validation — potential path traversal if malicious input

## Requirements
1. Validate `transcript_path` is an absolute path
2. Validate it exists and is a regular file (not a symlink to sensitive files)
3. Validate it ends with `.jsonl` extension
4. Reject paths containing `..`
5. Optional: validate path is under `~/.claude/` directory

## Acceptance Criteria
- [ ] Path must be absolute (starts with `/`)
- [ ] Path must exist as a regular file
- [ ] No `..` components in path
- [ ] Ends with `.jsonl`
- [ ] Invalid paths logged and silently skipped (exit 0)

## Files to modify
- `dialogue_capture.py` — add `validate_transcript_path()` function

## Verification
```bash
echo '{"session_id":"test","transcript_path":"../../etc/passwd"}' | python3 dialogue_capture.py --event Stop
# Should exit 0 with no DB writes
```
