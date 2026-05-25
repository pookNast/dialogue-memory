"""Tests for dialogue_inject.py — format_turns, query_recent_turns, empty DB behavior."""

import pytest

from dialogue_inject import format_turns, query_recent_turns


def _insert(conn, session_id, turn_num, speaker, content, project_dir=None, ts=None):
    ts = ts or "2025-05-25T12:00:00"
    conn.execute(
        "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content, project_dir, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, turn_num, speaker, content, project_dir, ts)
    )
    conn.commit()


class TestFormatTurns:
    def test_produces_markdown(self):
        turns = [
            ("user", "Hello there", "2025-05-25T12:00:00"),
            ("assistant", "Hi! How can I help?", "2025-05-25T12:00:05"),
        ]
        result = format_turns(turns)
        assert "## Prior Dialogue Context" in result
        assert "**USER**" in result
        assert "**ASSISTANT**" in result
        assert "Hello there" in result

    def test_respects_max_inject_chars(self):
        from config import MAX_INJECT_CHARS
        # Create many long turns
        turns = [
            ("user", "x" * 1000, "2025-05-25T12:00:00")
            for _ in range(50)
        ]
        result = format_turns(turns)
        assert len(result) <= MAX_INJECT_CHARS + 200  # allow header overhead

    def test_empty_list_returns_empty_string(self):
        assert format_turns([]) == ""

    def test_truncates_long_content(self):
        turns = [
            ("user", "x" * 600, "2025-05-25T12:00:00"),
        ]
        result = format_turns(turns)
        # Content should be truncated to 500 chars in the output
        assert "x" * 500 in result
        assert "x" * 600 not in result

    def test_timestamp_formatting(self):
        turns = [
            ("user", "test", "2025-05-25T14:30:00"),
        ]
        result = format_turns(turns)
        assert "(14:30)" in result

    def test_short_timestamp(self):
        turns = [
            ("user", "test", "short"),
        ]
        result = format_turns(turns)
        assert "short" in result


class TestQueryRecentTurns:
    def test_prefers_current_session(self, conn):
        _insert(conn, "s1", 0, "user", "session content", "/project")
        _insert(conn, "s2", 0, "user", "other session", "/project")

        turns = query_recent_turns(conn, "s1", "/project")
        assert len(turns) >= 1
        assert turns[0][1] == "session content"

    def test_falls_back_to_project_dir(self, conn):
        _insert(conn, "s1", 0, "user", "project content", "/project")

        # Query with empty session_id — should fall back to project_dir
        turns = query_recent_turns(conn, "", "/project")
        assert len(turns) == 1
        assert turns[0][1] == "project content"

    def test_returns_reversed_order(self, conn):
        _insert(conn, "s1", 0, "user", "first", ts="2025-05-25T12:00:00")
        _insert(conn, "s1", 1, "assistant", "second", ts="2025-05-25T12:01:00")
        _insert(conn, "s1", 2, "user", "third", ts="2025-05-25T12:02:00")

        turns = query_recent_turns(conn, "s1", "")
        # Should be in chronological order (reversed from DESC query)
        assert turns[0][1] == "first"
        assert turns[-1][1] == "third"

    def test_empty_db_returns_empty(self, conn):
        turns = query_recent_turns(conn, "s-nonexistent", "/nonexistent")
        assert turns == []

    def test_skips_empty_session_id(self, conn):
        _insert(conn, "s1", 0, "user", "data", "/project")

        # Empty session_id skips first query, tries project_dir
        turns = query_recent_turns(conn, "", "/project")
        assert len(turns) == 1

    def test_global_fallback(self, conn):
        _insert(conn, "s1", 0, "user", "global data", "/other-project")

        # No session match, no project match — falls back to global
        turns = query_recent_turns(conn, "s-missing", "/missing-project")
        assert len(turns) == 1
        assert turns[0][1] == "global data"
