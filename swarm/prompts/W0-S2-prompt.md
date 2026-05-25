# W0-S2: Add retention policy

## Task
Add automatic pruning of old dialogue turns to prevent unbounded DB growth.

## Context
- Files: `/home/pook/dialogue-memory/db.py`, `/home/pook/dialogue-memory/config.py`
- SQLite DB grows with every conversation — no cleanup mechanism exists
- FTS5 triggers must stay in sync during deletes

## Requirements
1. Add `DIALOGUE_MEMORY_RETENTION_DAYS` env var to `config.py` (default: 90)
2. Add `prune_old_turns()` to `db.py`
3. Call prune on `get_connection()` if row count > 1000 (avoid running on every call)
4. DELETE triggers auto-sync FTS via existing `dialogue_fts_ad` trigger
5. Log pruned count

## Acceptance Criteria
- [ ] Turns older than RETENTION_DAYS are deleted
- [ ] FTS index stays consistent after prune
- [ ] Prune only runs when row count > 1000
- [ ] Pruned count logged to dialogue_capture.log

## Files to modify
- `config.py` — add RETENTION_DAYS
- `db.py` — add `prune_old_turns(conn)`

## Verification
```bash
python3 -c "
from db import get_connection, prune_old_turns
conn = get_connection()
# Insert old test data, verify prune works
"
```
