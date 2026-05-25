# Dialogue-Memory — Milestone Contract

## Project Summary
Rolling conversation memory for OpenClaude + local LLMs. Captures dialogue turns (stripping tool calls/reasoning), persists in SQLite + FTS5, re-injects on session start/compaction. Optional Qdrant semantic search and Obsidian daily archive.

## Deliverables Status

### Delivered (v0.1.0)
| # | Deliverable | Status | Confidence |
|---|-------------|--------|-----------|
| 1 | `dialogue_capture.py` — UserPromptSubmit + Stop hooks | DONE | 0.95 |
| 2 | `dialogue_inject.py` — SessionStart + PreCompact hooks | DONE | 0.95 |
| 3 | `dialogue_embed_batch.py` — Qdrant batch embedding | DONE | 0.93 |
| 4 | `dialogue_archive.py` — Obsidian daily export | DONE | 0.95 |
| 5 | `db.py` — SQLite + FTS5 + auto-recovery | DONE | 0.96 |
| 6 | `config.py` — env var configuration | DONE | 0.98 |
| 7 | `install.sh` — hook installer | DONE | 0.95 |
| 8 | Hook registrations in settings.json | DONE | 0.97 |
| 9 | Cron jobs (embed + archive) | DONE | 0.95 |
| 10 | GitHub repo + issue on Gitlawb/openclaude | DONE | 1.00 |
| 11 | Forgejo repo | DONE | 1.00 |
| 12 | PRD with 3-wave task breakdown | DONE | 0.95 |
| 13 | Swarm launcher (mega-chief.sh + prompts) | DONE | 0.93 |
| 14 | Git history sanitized (session logs purged) | DONE | 1.00 |
| 15 | DB corruption auto-recovery | DONE | 0.96 |
| 16 | Transcript path validation | DONE | 0.95 |
| 17 | Error logging (no silent swallowing) | DONE | 0.95 |

### Remaining (Swarm Wave Tasks)
| Wave | Task | Status | Agent |
|------|------|--------|-------|
| W0-S2 | Retention policy | PENDING | dev |
| W0-S3 | Health check script | PENDING | siteops |
| W0-S4 | Unit tests | PENDING | dev |
| W1-S0 | pyproject.toml | PENDING | dev |
| W1-S1 | CHANGELOG.md | PENDING | dev |
| W1-S2 | GitHub Actions CI | PENDING | devops |
| W1-S3 | CONTRIBUTING.md | PENDING | dev |
| W2-S0 | Semantic search injection | PENDING | architect |
| W2-S1 | FTS search CLI | PENDING | dev |
| W2-S2 | Prometheus metrics | PENDING | siteops |

## Audit Summary

| Audit | Pre-Fix | Post-Fix | Target |
|-------|---------|----------|--------|
| Preflight | 9/9 | 9/9 | PASS |
| Security | 82/100 | 92/100 | >90 |
| Error Handling | 95/100 | 98/100 | >95 |
| RLM-Ready | 0/8 | 0/8 | Addressed in W1 |
| Sinking-Ship | ~85/100 | ~92/100 | >90 |

**Overall confidence (core deliverables): 0.95**

## Swarm Execution Plan

```bash
# Launch Wave 0 (hardening) — run tonight
bash /home/pook/dialogue-memory/swarm/launchers/mega-chief.sh --wave W0 --model sonnet

# Launch Wave 1 (release) — after W0 completes
bash /home/pook/dialogue-memory/swarm/launchers/mega-chief.sh --wave W1 --model sonnet

# Launch Wave 2 (features) — after W1
bash /home/pook/dialogue-memory/swarm/launchers/mega-chief.sh --wave W2 --model sonnet
```

## Repos
- GitHub: https://github.com/pookNast/dialogue-memory
- Forgejo: ssh://git@192.168.183.110:2222/pook/dialogue-memory.git
- Issue: https://github.com/Gitlawb/openclaude/issues/1355
