# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-05-25

### Added
- Hook-based dialogue capture — stores user prompts and assistant responses in SQLite, stripping tool calls and thinking blocks
- SQLite storage with WAL mode, FTS5 full-text search index, and automatic corruption recovery
- Session and project directory organization with token estimation and content length limiting
- 90-day retention policy with automatic pruning
- Batch embedding pipeline via Ollama to Qdrant vector DB with semantic search
- Daily export to Obsidian vault format, grouped by session
- Health check CLI for database integrity and Qdrant connectivity
- Install script with Claude Code hook registration
- Configurable environment settings for embedding models, batch sizes, and archive directories

[0.1.0]: https://github.com/pookNast/dialogue-memory/releases/tag/v0.1.0
