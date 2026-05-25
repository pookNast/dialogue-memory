# W2-S0: Add semantic search fallback to dialogue_inject

## Task
Enhance `dialogue_inject.py` to query Qdrant when SQLite has no recent turns.

## Context
- Project: `/home/pook/dialogue-memory/`
- Qdrant collection: `dialogue_memory` with 768-dim vectors
- Embedding model: `nomic-embed-text` via Ollama
- Config in `config.py`: QDRANT_URL, OLLAMA_URL, EMBED_MODEL

## Requirements
1. Add `DIALOGUE_MEMORY_SEMANTIC_INJECT` env var (default: false)
2. If enabled and SQLite has no recent turns for the project:
   - Embed the project directory name as query
   - Search Qdrant for top 5 similar dialogue turns
   - Format and inject as system context
3. Graceful fallback if Qdrant/Ollama unreachable
4. Total injection time must stay under 1000ms timeout

## Files to modify
- `dialogue_inject.py`
- `config.py` (add SEMANTIC_INJECT flag)

## Verification
```bash
DIALOGUE_MEMORY_SEMANTIC_INJECT=true echo '{"session_id":"new"}' | python3 dialogue_inject.py
```
