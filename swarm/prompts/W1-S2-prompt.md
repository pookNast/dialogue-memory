# W1-S2: Add GitHub Actions CI

## Task
Create a CI workflow that runs tests on push to main.

## Context
- Project: `/home/pook/dialogue-memory/`
- Tests in `tests/` directory (pytest)
- Python stdlib only for core
- FTS5 required (available in Python's bundled sqlite3)

## Requirements
1. Trigger on push to main and PRs
2. Python version matrix: 3.8, 3.11, 3.13
3. Install pytest
4. Run syntax check on all .py files
5. Run `python3 -m pytest tests/ -v`
6. Cache pip dependencies

## Files to create
- `.github/workflows/ci.yml`

## Verification
```bash
# Validate YAML
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
