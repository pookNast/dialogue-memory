# W0-S3: Add health check script

## Task
Create a health check script that reports system status for monitoring.

## Context
- Project: `/home/pook/dialogue-memory/`
- DB: `~/.claude/dialogue_memory.db`
- Qdrant: configured in `config.py` (QDRANT_URL)
- Needs to work as both CLI tool and cron-scriptable

## Requirements
1. Check DB exists and passes PRAGMA quick_check
2. Report row count, embedding backlog, DB file size
3. Check FTS5 integrity
4. Check Qdrant reachability and collection point count
5. JSON output mode (--json flag)
6. Exit 0 if healthy, exit 1 if any check fails

## Acceptance Criteria
- [ ] `python3 dialogue_health.py` prints human-readable status
- [ ] `python3 dialogue_health.py --json` prints JSON
- [ ] Exit code reflects health
- [ ] Works when Qdrant is unreachable (degrades gracefully)
- [ ] Works when DB doesn't exist yet (reports "not initialized")

## Files to create
- `dialogue_health.py`

## Verification
```bash
python3 dialogue_health.py && echo HEALTHY || echo UNHEALTHY
python3 dialogue_health.py --json | python3 -m json.tool
```
