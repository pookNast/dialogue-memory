"""
Shared configuration for dialogue-memory hooks.

All values are configurable via environment variables.
"""

import os
from pathlib import Path

# SQLite database location
DB_PATH = Path(os.environ.get(
    "DIALOGUE_MEMORY_DB",
    str(Path.home() / ".claude" / "dialogue_memory.db")
))

# Log directory
LOG_DIR = Path(os.environ.get(
    "DIALOGUE_MEMORY_LOG_DIR",
    str(Path.home() / ".claude" / "logs")
))

# Qdrant vector database
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("DIALOGUE_MEMORY_COLLECTION", "dialogue_memory")
QDRANT_VECTOR_DIM = int(os.environ.get("DIALOGUE_MEMORY_VECTOR_DIM", "768"))

# Ollama embedding
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("DIALOGUE_MEMORY_EMBED_MODEL", "nomic-embed-text")

# Obsidian vault for daily archives
OBSIDIAN_DAILY_DIR = Path(os.environ.get(
    "DIALOGUE_MEMORY_OBSIDIAN_DIR",
    str(Path.home() / "obsidian-vault" / "Daily")
))

# Tuning
MAX_CONTENT_LEN = int(os.environ.get("DIALOGUE_MEMORY_MAX_CONTENT", "2000"))
MAX_INJECT_TURNS = int(os.environ.get("DIALOGUE_MEMORY_MAX_INJECT_TURNS", "8"))
MAX_INJECT_CHARS = int(os.environ.get("DIALOGUE_MEMORY_MAX_INJECT_CHARS", "4000"))
EMBED_BATCH_SIZE = int(os.environ.get("DIALOGUE_MEMORY_EMBED_BATCH", "20"))
