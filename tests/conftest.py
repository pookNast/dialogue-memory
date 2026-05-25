"""Shared fixtures for dialogue-memory tests.

All tests use in-memory SQLite — never the live DB.
"""

import sqlite3
import pytest

from db import init_schema


class NonClosingConnection:
    """Wraps a sqlite3.Connection, making close() a no-op during tests.
    The real close happens in the fixture teardown."""

    def __init__(self, real_conn):
        self._conn = real_conn

    def close(self):
        pass  # no-op — fixture handles teardown

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def conn():
    """In-memory SQLite connection with schema initialized."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA journal_mode=WAL")
    init_schema(c)
    yield NonClosingConnection(c)
    c.close()
