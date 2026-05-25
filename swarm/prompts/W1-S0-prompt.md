# W1-S0: Add pyproject.toml

## Task
Create a pyproject.toml for the dialogue-memory package.

## Context
- Project: `/home/pook/dialogue-memory/`
- Pure Python, stdlib only for core (no pip deps)
- Optional deps: httpx (for Qdrant/Ollama in embed batch)

## Requirements
1. Project name: `dialogue-memory`
2. Version: `0.1.0`
3. Python requires: `>=3.8`
4. No required dependencies (core is stdlib-only)
5. Optional extras: `[embed]` = httpx, `[test]` = pytest
6. Entry points for CLI: `dialogue-health`, `dialogue-search`

## Files to create
- `pyproject.toml`

## Verification
```bash
python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'])"
```
