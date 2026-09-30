-- Skema PostgreSQL untuk Jig test database.
-- Dijalankan otomatis oleh server/app.py saat start (init_db()),
-- file ini disediakan hanya sebagai referensi / untuk setup manual.

CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    created_at  TEXT    NOT NULL,
    station     TEXT    NOT NULL DEFAULT '',
    device_id   TEXT    NOT NULL DEFAULT '',
    project     TEXT    DEFAULT NULL,
    notes       TEXT    DEFAULT '',
    finished_at TEXT    DEFAULT NULL,
    result      TEXT    DEFAULT NULL    -- 'OK' | 'NG' | NULL (belum selesai)
);

CREATE TABLE IF NOT EXISTS test_results (
    id           SERIAL PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    timestamp    TEXT    NOT NULL,
    test_name    TEXT    NOT NULL,
    command      TEXT    DEFAULT '',
    result       TEXT    NOT NULL,      -- 'OK' | 'NG'
    duration_ms  INTEGER DEFAULT 0,
    notes        TEXT    DEFAULT '',
    raw_response TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_results_session ON test_results(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_device  ON sessions(device_id);
