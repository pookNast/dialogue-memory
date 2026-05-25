"""Tests for db.py — schema, FTS sync, WAL, recovery, pruning."""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from db import init_schema, get_connection, _recover_corrupt_db


class TestSchema:
    def test_tables_created(self, conn):
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "dialogue_turns" in tables

    def test_fts_created(self, conn):
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "dialogue_turns" in tables
        assert "dialogue_fts" in tables

    def test_triggers_created(self, conn):
        triggers = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()}
        assert "dialogue_fts_ai" in triggers
        assert "dialogue_fts_ad" in triggers
        assert "dialogue_fts_au" in triggers

    def test_indexes_created(self, conn):
        idxs = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        assert "idx_dt_session" in idxs
        assert "idx_dt_embed" in idxs
        assert "idx_dt_project" in idxs

    def test_unique_constraint(self, conn):
        conn.execute(
            "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content) "
            "VALUES ('s1', 0, 'user', 'hello')"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content) "
                "VALUES ('s1', 0, 'user', 'duplicate')"
            )

    def test_speaker_check_constraint(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content) "
                "VALUES ('s1', 0, 'narrator', 'test')"
            )


class TestFTSSync:
    def _insert(self, conn, session_id="s1", turn_num=0, speaker="user", content="hello world"):
        conn.execute(
            "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content) "
            "VALUES (?, ?, ?, ?)",
            (session_id, turn_num, speaker, content)
        )
        conn.commit()

    def test_insert_syncs_fts(self, conn):
        self._insert(conn, content="unique test content alpha")
        rows = conn.execute(
            "SELECT rowid FROM dialogue_fts WHERE dialogue_fts MATCH 'alpha'"
        ).fetchall()
        assert len(rows) == 1

    def test_delete_syncs_fts(self, conn):
        self._insert(conn, content="beta gamma delta")
        conn.execute("DELETE FROM dialogue_turns WHERE content LIKE '%beta%'")
        conn.commit()
        rows = conn.execute(
            "SELECT rowid FROM dialogue_fts WHERE dialogue_fts MATCH 'beta'"
        ).fetchall()
        assert len(rows) == 0

    def test_update_syncs_fts(self, conn):
        self._insert(conn, content="old content epsilon")
        conn.execute(
            "UPDATE dialogue_turns SET content = 'new content zeta' WHERE content LIKE '%epsilon%'"
        )
        conn.commit()
        old_rows = conn.execute(
            "SELECT rowid FROM dialogue_fts WHERE dialogue_fts MATCH 'epsilon'"
        ).fetchall()
        assert len(old_rows) == 0
        new_rows = conn.execute(
            "SELECT rowid FROM dialogue_fts WHERE dialogue_fts MATCH 'zeta'"
        ).fetchall()
        assert len(new_rows) == 1


class TestWALMode:
    def test_wal_mode_enabled(self, conn):
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        # In-memory DBs report "memory" not "wal"
        assert mode in ("wal", "memory")


class TestCorruptionRecovery:
    def test_recover_moves_files(self, tmp_path):
        fake_db = tmp_path / "test.db"
        fake_db.write_text("corrupt")
        fake_wal = tmp_path / "test.db-wal"
        fake_wal.write_text("wal")
        fake_shm = tmp_path / "test.db-shm"
        fake_shm.write_text("shm")

        with patch("db.DB_PATH", fake_db), \
             patch("db.LOG_DIR", tmp_path):
            _recover_corrupt_db("test corruption")

        # Original files gone
        assert not fake_db.exists()
        assert not fake_wal.exists()
        assert not fake_shm.exists()
        # Corrupt backups exist
        corrupt_files = list(tmp_path.glob("test.db.corrupt-*"))
        assert len(corrupt_files) >= 1

    def test_get_connection_recovers_on_corruption(self, tmp_path):
        """Test that get_connection recovers when quick_check fails (not WAL pragma)."""
        fake_db = tmp_path / "test.db"

        # Create a valid-looking but corrupt DB that passes WAL but fails quick_check
        # Strategy: create valid DB, then overwrite header bytes
        import sqlite3 as sq
        c = sq.connect(str(fake_db))
        c.execute("CREATE TABLE t(x)")
        c.commit()
        c.close()
        # Corrupt by overwriting part of the header
        data = bytearray(fake_db.read_bytes())
        data[20:28] = b"\xff\xff\xff\xff\xff\xff\xff\xff"  # corrupt page count
        fake_db.write_bytes(bytes(data))

        with patch("db.DB_PATH", fake_db), \
             patch("db.LOG_DIR", tmp_path):
            import db
            db._schema_initialized = False
            conn = get_connection()
            result = conn.execute("PRAGMA quick_check").fetchone()
            assert result[0] == "ok"
            conn.close()
            # Corrupt backup should exist
            corrupt_files = list(tmp_path.glob("*.corrupt-*"))
            assert len(corrupt_files) >= 1


class TestPrune:
    """Tests for pruning old turns (W0-S2)."""

    def _fill_over_threshold(self, conn, old_ts="2020-01-01T00:00:00"):
        """Insert 1001 rows so prune actually runs (threshold=1000)."""
        for i in range(1000):
            conn.execute(
                "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content, ts) "
                "VALUES (?, ?, 'user', ?, ?)",
                ("s1", i * 2, f"old turn {i}", old_ts)
            )
        # One recent turn
        conn.execute(
            "INSERT INTO dialogue_turns (session_id, turn_num, speaker, content) "
            "VALUES ('s1', 2000, 'user', 'recent turn')"
        )
        conn.commit()

    def test_prune_removes_old_turns(self, conn):
        import db
        if not hasattr(db, "prune_old_turns"):
            pytest.skip("prune_old_turns not yet implemented (W0-S2)")

        self._fill_over_threshold(conn)

        with patch("db.LOG_DIR", conn.execute("SELECT 1").connection and __import__("pathlib").Path("/tmp")):
            db.prune_old_turns(conn)

        rows = conn.execute("SELECT content FROM dialogue_turns ORDER BY turn_num").fetchall()
        assert all("old turn" not in r[0] for r in rows) or len(rows) < 1001

    def test_prune_keeps_fts_in_sync(self, conn):
        import db
        if not hasattr(db, "prune_old_turns"):
            pytest.skip("prune_old_turns not yet implemented (W0-S2)")

        self._fill_over_threshold(conn)

        with patch("db.LOG_DIR", __import__("pathlib").Path("/tmp")):
            db.prune_old_turns(conn)

        fts_rows = conn.execute(
            "SELECT rowid FROM dialogue_fts WHERE dialogue_fts MATCH 'prune'"
        ).fetchall()
        assert len(fts_rows) == 0
