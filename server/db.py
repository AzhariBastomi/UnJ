"""
server/db.py — Database layer untuk Jig server.

Backend: PostgreSQL saja (SQLite tidak lagi dipakai). Koneksi diambil dari
env var JIG_DB_URL; kalau tidak diset, dipakai default yang cocok dengan
`database/docker-compose.yml` (user/password/db = jig, localhost:5432):

    JIG_DB_URL=postgresql://jig:jig@localhost:5432/jig

Semua kode di server/app.py tetap pakai placeholder '?' ala SQLite; modul
ini yang menerjemahkan ke '%s' + RETURNING id, supaya app.py tidak perlu
diubah.

Schema:
  sessions     — satu sesi per device yang ditest
  test_results — hasil tiap test dalam satu sesi

PENTING: Postgres (lewat docker compose di folder database/) harus sudah
jalan sebelum server/app.py di-start, kalau tidak get_connection() akan
melempar error koneksi.
"""

import os
from datetime import datetime, timezone
from contextlib import contextmanager

# Default cocok dengan database/docker-compose.yml. Override lewat env var
# JIG_DB_URL kalau host/kredensial Postgres-nya beda.
DEFAULT_PG_URL = "postgresql://jig:jig@localhost:5432/jig"
PG_URL  = os.environ.get("JIG_DB_URL", "").strip() or DEFAULT_PG_URL
BACKEND = "postgres"


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_SESSIONS_PG = """
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    created_at  TEXT    NOT NULL,
    station     TEXT    NOT NULL DEFAULT '',
    device_id   TEXT    NOT NULL DEFAULT '',
    project     TEXT    DEFAULT NULL,
    notes       TEXT    DEFAULT '',
    finished_at TEXT    DEFAULT NULL,
    result      TEXT    DEFAULT NULL
);
"""

_CREATE_RESULTS_PG = """
CREATE TABLE IF NOT EXISTS test_results (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    timestamp   TEXT    NOT NULL,
    test_name   TEXT    NOT NULL,
    command     TEXT    DEFAULT '',
    result      TEXT    NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    notes       TEXT    DEFAULT '',
    raw_response TEXT   DEFAULT ''
);
"""

_CREATE_IDX1 = "CREATE INDEX IF NOT EXISTS idx_results_session ON test_results(session_id);"
_CREATE_IDX2 = "CREATE INDEX IF NOT EXISTS idx_sessions_device ON sessions(device_id);"


# ---------------------------------------------------------------------------
# Shim: supaya app.py bisa selalu pakai placeholder '?' dan cur.lastrowid,
# sama seperti waktu masih dual-backend.
# ---------------------------------------------------------------------------

class _CursorShim:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def execute(self, sql, params=()):
        pg_sql   = sql.replace("?", "%s")
        stripped = pg_sql.strip().upper()
        if stripped.startswith("INSERT") and "RETURNING" not in stripped:
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
        self._cur.execute(pg_sql, params)
        if stripped.startswith("INSERT"):
            row = self._cur.fetchone()
            self.lastrowid = row["id"] if row else None
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class _ConnShim:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        return _CursorShim(cur).execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection(db_path: str = None):
    """db_path diabaikan (dipertahankan supaya signature lama tetap kompatibel)."""
    import psycopg
    from psycopg.rows import dict_row
    conn = psycopg.connect(PG_URL, row_factory=dict_row, autocommit=False)
    return _ConnShim(conn)


def init_db(db_path: str = None):
    """Buat tabel jika belum ada (idempotent, aman dipanggil tiap request)."""
    conn = get_connection()
    try:
        conn.execute(_CREATE_SESSIONS_PG)
        conn.execute(_CREATE_RESULTS_PG)
        conn.execute(_CREATE_IDX1)
        conn.execute(_CREATE_IDX2)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_conn(db_path: str = None):
    """Context manager untuk koneksi Postgres."""
    conn = get_connection()
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
