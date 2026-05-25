"""Tests for dialogue_capture.py — clean_text, estimate_tokens, turn numbering, capture logic."""

import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

from dialogue_capture import (
    clean_text,
    estimate_tokens,
    insert_turn_atomic,
    capture_user_prompt,
    capture_assistant_response,
    validate_transcript_path,
)


class TestCleanText:
    def test_strips_think_blocks(self):
        result = clean_text("Hello <think>thinking content</think> more")
        assert "thinking content" not in result
        assert "Hello" in result
        assert "more" in result

    def test_strips_thinking_tags(self):
        result = clean_text("Before <thinking>secret thoughts</thinking> After")
        assert "secret" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_function_calls(self):
        result = clean_text("Text <function_calls>{\"tool\": \"run\"}</function_calls> More")
        assert "function_calls" not in result
        assert "Text" in result
        assert "More" in result

    def test_strips_invoke_tags(self):
        result = clean_text("Start <invoke name=\"tool\">payload</invoke> End")
        assert "invoke" not in result
        assert "Start" in result
        assert "End" in result

    def test_preserves_normal_text(self):
        result = clean_text("This is normal text with no special tags.")
        assert result == "This is normal text with no special tags."

    def test_collapses_excessive_newlines(self):
        result = clean_text("Line1\n\n\n\n\nLine2")
        assert "\n\n\n" not in result
        assert "Line1" in result
        assert "Line2" in result

    def test_truncates_to_max_content_len(self):
        from config import MAX_CONTENT_LEN
        long_text = "x" * (MAX_CONTENT_LEN + 500)
        result = clean_text(long_text)
        assert len(result) <= MAX_CONTENT_LEN

    def test_strips_whitespace(self):
        result = clean_text("  hello world  ")
        assert result == "hello world"

    def test_empty_after_cleaning(self):
        result = clean_text("<thinking>all removed</thinking>")
        assert result == ""


class TestEstimateTokens:
    def test_returns_len_div_4(self):
        assert estimate_tokens("abcdefghijklmnop") == 4

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        assert estimate_tokens("abc") == 0  # 3 // 4 = 0

    def test_approximate_ratio(self):
        text = "Hello world, this is a test of token estimation."
        assert estimate_tokens(text) == len(text) // 4


class TestInsertTurnAtomic:
    def test_first_user_turn_is_zero(self, conn):
        insert_turn_atomic(conn, "s1", "user", "hello", 2, "/test")
        row = conn.execute("SELECT turn_num FROM dialogue_turns WHERE session_id='s1'").fetchone()
        assert row[0] == 0

    def test_first_assistant_turn_is_one(self, conn):
        insert_turn_atomic(conn, "s1", "assistant", "hi there friend", 3, "/test")
        row = conn.execute("SELECT turn_num FROM dialogue_turns WHERE session_id='s1'").fetchone()
        assert row[0] == 1

    def test_user_turns_are_even(self, conn):
        insert_turn_atomic(conn, "s1", "user", "hello world", 3, "/test")
        insert_turn_atomic(conn, "s1", "user", "second message", 3, "/test")
        rows = conn.execute("SELECT turn_num FROM dialogue_turns WHERE speaker='user' ORDER BY turn_num").fetchall()
        assert [r[0] for r in rows] == [0, 2]

    def test_assistant_turns_are_odd(self, conn):
        insert_turn_atomic(conn, "s1", "assistant", "first response here", 4, "/test")
        insert_turn_atomic(conn, "s1", "assistant", "second response here", 4, "/test")
        rows = conn.execute("SELECT turn_num FROM dialogue_turns WHERE speaker='assistant' ORDER BY turn_num").fetchall()
        assert [r[0] for r in rows] == [1, 3]

    def test_independent_sessions(self, conn):
        insert_turn_atomic(conn, "s1", "user", "hello world", 3, "/test")
        insert_turn_atomic(conn, "s2", "user", "hello world too", 3, "/test")
        r1 = conn.execute("SELECT turn_num FROM dialogue_turns WHERE session_id='s1'").fetchone()
        r2 = conn.execute("SELECT turn_num FROM dialogue_turns WHERE session_id='s2'").fetchone()
        assert r1[0] == 0
        assert r2[0] == 0


class TestCaptureUserPrompt:
    def test_stores_valid_prompt(self, conn):

        with patch("dialogue_capture.get_connection", return_value=conn), \
             patch("dialogue_capture.os.environ.get", return_value="/test"):
            capture_user_prompt({"session_id": "s1", "prompt": "Tell me about Python"})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 1
        assert "Python" in rows[0][0]

    def test_skips_slash_commands(self, conn):
        with patch("dialogue_capture.get_connection", return_value=conn):
            capture_user_prompt({"session_id": "s1", "prompt": "/commit this change"})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 0

    def test_skips_short_prompts(self, conn):
        with patch("dialogue_capture.get_connection", return_value=conn):
            capture_user_prompt({"session_id": "s1", "prompt": "hi"})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 0

    def test_skips_missing_session_id(self, conn):
        with patch("dialogue_capture.get_connection", return_value=conn):
            capture_user_prompt({"prompt": "Tell me about Python"})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 0

    def test_skips_missing_prompt(self, conn):
        with patch("dialogue_capture.get_connection", return_value=conn):
            capture_user_prompt({"session_id": "s1"})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 0

    def test_duplicate_turn_prevented(self, conn):

        with patch("dialogue_capture.get_connection", return_value=conn), \
             patch("dialogue_capture.os.environ.get", return_value="/test"):
            capture_user_prompt({"session_id": "s1", "prompt": "Hello world test prompt"})
        # Second call: get_next_turn_num returns 2 (same session, user)
        with patch("dialogue_capture.get_connection", return_value=conn), \
             patch("dialogue_capture.os.environ.get", return_value="/test"):
            capture_user_prompt({"session_id": "s1", "prompt": "Different prompt content"})
        rows = conn.execute("SELECT content FROM dialogue_turns ORDER BY turn_num").fetchall()
        # Both inserts succeed with different turn_nums (0, 2)
        assert len(rows) == 2


class TestCaptureAssistantResponse:
    def test_extracts_text_from_transcript(self, conn, tmp_path):
        transcript = tmp_path / "test.jsonl"
        entries = [
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "This is a detailed assistant response about testing."}
            ]}}
        ]
        transcript.write_text("\n".join(json.dumps(e) for e in entries))


        with patch("dialogue_capture.get_connection", return_value=conn), \
             patch("dialogue_capture.validate_transcript_path", return_value=True), \
             patch("dialogue_capture.os.environ.get", return_value="/test"):
            capture_assistant_response({"session_id": "s1", "transcript_path": str(transcript)})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 1
        assert "testing" in rows[0][0]

    def test_skips_short_assistant_text(self, conn, tmp_path):
        transcript = tmp_path / "short.jsonl"
        entries = [
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "short"}
            ]}}
        ]
        transcript.write_text("\n".join(json.dumps(e) for e in entries))

        with patch("dialogue_capture.get_connection", return_value=conn), \
             patch("dialogue_capture.validate_transcript_path", return_value=True), \
             patch("builtins.open", lambda f, *a, **k: open(str(transcript), *a[1:], **k)):
            capture_assistant_response({"session_id": "s1", "transcript_path": str(transcript)})
        rows = conn.execute("SELECT content FROM dialogue_turns").fetchall()
        assert len(rows) == 0


class TestValidateTranscriptPath:
    def test_rejects_relative_path(self):
        assert validate_transcript_path("relative/path.jsonl") is False

    def test_rejects_non_jsonl(self):
        assert validate_transcript_path("/tmp/file.txt") is False

    def test_rejects_path_traversal(self):
        assert validate_transcript_path("/home/user/../etc/passwd.jsonl") is False

    def test_rejects_empty_path(self):
        assert validate_transcript_path("") is False

    def test_rejects_nonexistent_file(self):
        assert validate_transcript_path("/nonexistent/path/test.jsonl") is False
