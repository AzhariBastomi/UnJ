"""
server/db.py — SQLite schema dan helper untuk Jig server.

Database path default: server/jig.db
Schema:
  sessions    — satu sesi per device yang ditest
  test_results — hasil tiap test dalam satu sesi
"""

import sqlite3
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "jig.db")


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    station     TEXT    NOT NULL DEFAULT '',
    device_id   TEXT    NOT NULL DEFAULT '',
    project     TEXT    DEFAULT NULL,
    notes       TEXT    DEFAULT '',
    finished_at TEXT    DEFAULT NULL,
    result      TEXT    DEFAULT NULL    -- "OK" | "NG" | NULL (belum selesai)
);
"""

_CREATE_RESULTS = """
CREATE TABLE IF NOT EXISTS test_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    timestamp   TEXT    NOT NULL,
    test_name   TEXT    NOT NULL,
    command     TEXT    DEFAULT '',
    result      TEXT    NOT NULL,       -- "OK" | "NG"
    duration_ms INTEGER DEFAULT 0,
    notes       TEXT    DEFAULT '',
    raw_response TEXT   DEFAULT ''
);
"""

_CREATE_IDX1 = "CREATE INDEX IF NOT EXISTS idx_results_session ON test_results(session_id);"
_CREATE_IDX2 = "CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions(device_id);"


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH):
    """Buat tabel jika belum ada."""
    with get_connection(db_path) as conn:
        conn.execute(_CREATE_SESSIONS)
        conn.execute(_CREATE_RESULTS)
        conn.execute(_CREATE_IDX1)
        conn.execute(_CREATE_IDX2)
        conn.commit()


@contextmanager
def db_conn(db_path: str = DB_PATH):
    """Context manager untuk koneksi SQLite."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def row_to_dict(row) -> dict:
    return dict(row) if row else {}
