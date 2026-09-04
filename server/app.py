"""
server/app.py — Flask REST API untuk Jig test database.

Run:
    pip install flask
    python server/app.py

atau dari root project:
    python -m server.app

API v1:
  POST   /api/v1/sessions                       Buat sesi baru
  GET    /api/v1/sessions                       List semua sesi (latest first)
  GET    /api/v1/sessions/<id>                  Detail sesi + semua results
  PATCH  /api/v1/sessions/<id>                  Update sesi (finish, notes)
  DELETE /api/v1/sessions/<id>                  Hapus sesi + hasil

  POST   /api/v1/sessions/<id>/results          Tambah hasil test
  GET    /api/v1/sessions/<id>/results          List semua hasil dalam sesi

  GET    /api/v1/devices/<device_id>            Riwayat sesi per device
  GET    /api/v1/stats                          Statistik ringkasan

Health:
  GET    /health                                 Cek server aktif
"""

import sys, os
# Tambah root project ke path agar bisa import dari lib/
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "lib"))

from flask import Flask, request, jsonify, abort
# from server.db import init_db, db_conn, now_iso, row_to_dict, DB_PATH
from db import init_db, db_conn, now_iso, row_to_dict, DB_PATH

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.before_request
def _ensure_db():
    init_db()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok", "db": DB_PATH})


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@app.post("/api/v1/sessions")
def create_session():
    body       = request.get_json(silent=True) or {}
    station    = body.get("station", "")
    device_id  = body.get("device_id", "")
    project    = body.get("project", None)
    notes      = body.get("notes", "")

    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (created_at, station, device_id, project, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (now_iso(), station, device_id, project, notes),
        )
        session_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.get("/api/v1/sessions")
def list_sessions():
    limit  = min(int(request.args.get("limit",  100)), 500)
    offset = int(request.args.get("offset", 0))
    device = request.args.get("device_id", None)

    query  = "SELECT * FROM sessions"
    params = []
    if device:
        query += " WHERE device_id = ?"
        params.append(device)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with db_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/v1/sessions/<int:session_id>")
def get_session(session_id):
    with db_conn() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            abort(404, description=f"Session {session_id} tidak ditemukan")
        results = conn.execute(
            "SELECT * FROM test_results WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()

    data = row_to_dict(session)
    data["test_results"] = [row_to_dict(r) for r in results]
    return jsonify(data)


@app.patch("/api/v1/sessions/<int:session_id>")
def update_session(session_id):
    body = request.get_json(silent=True) or {}

    with db_conn() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            abort(404, description=f"Session {session_id} tidak ditemukan")

        updates = []
        params  = []
        for field in ("notes", "project", "result", "finished_at", "device_id", "station"):
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])

        # Shortcut: jika "finish": true, set finished_at + result otomatis
        if body.get("finish"):
            if "finished_at" not in body:
                updates.append("finished_at = ?")
                params.append(now_iso())
            if "result" not in body and body.get("result"):
                updates.append("result = ?")
                params.append(body["result"])

        if updates:
            params.append(session_id)
            conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params
            )
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

    return jsonify(row_to_dict(row))


@app.delete("/api/v1/sessions/<int:session_id>")
def delete_session(session_id):
    with db_conn() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            abort(404, description=f"Session {session_id} tidak ditemukan")
        conn.execute("DELETE FROM test_results WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    return jsonify({"deleted": session_id})


# ---------------------------------------------------------------------------
# Test results
# ---------------------------------------------------------------------------

@app.post("/api/v1/sessions/<int:session_id>/results")
def add_result(session_id):
    body = request.get_json(silent=True) or {}

    with db_conn() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            abort(404, description=f"Session {session_id} tidak ditemukan")

        test_name   = body.get("test_name", "")
        command     = body.get("command", "")
        result      = body.get("result", "NG").upper()
        duration_ms = int(body.get("duration_ms", 0))
        notes       = body.get("notes", "")
        raw         = body.get("raw_response", "")
        timestamp   = body.get("timestamp", now_iso())

        if result not in ("OK", "NG"):
            abort(400, description="result harus 'OK' atau 'NG'")
        if not test_name:
            abort(400, description="test_name wajib diisi")

        cur = conn.execute(
            "INSERT INTO test_results "
            "(session_id, timestamp, test_name, command, result, duration_ms, notes, raw_response) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, timestamp, test_name, command, result, duration_ms, notes, raw),
        )
        row = conn.execute(
            "SELECT * FROM test_results WHERE id = ?", (cur.lastrowid,)
        ).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.get("/api/v1/sessions/<int:session_id>/results")
def list_results(session_id):
    with db_conn() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            abort(404, description=f"Session {session_id} tidak ditemukan")
        rows = conn.execute(
            "SELECT * FROM test_results WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Device history
# ---------------------------------------------------------------------------

@app.get("/api/v1/devices/<device_id>")
def device_history(device_id):
    limit  = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    with db_conn() as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE device_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (device_id, limit, offset),
        ).fetchall()

    return jsonify([row_to_dict(r) for r in sessions])


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/v1/stats")
def stats():
    with db_conn() as conn:
        total_sessions  = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_results   = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        ok_count        = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE result='OK'"
        ).fetchone()[0]
        ng_count        = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE result='NG'"
        ).fetchone()[0]
        recent_sessions = conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT 5"
        ).fetchall()

    return jsonify({
        "total_sessions":  total_sessions,
        "total_results":   total_results,
        "ok_count":        ok_count,
        "ng_count":        ng_count,
        "ok_rate":         round(ok_count / total_results * 100, 1) if total_results else None,
        "recent_sessions": [row_to_dict(r) for r in recent_sessions],
    })


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    return jsonify({"error": str(e)}), e.code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print(f"Jig DB Server — SQLite: {DB_PATH}")
    print("API: http://localhost:5001/api/v1/")
    app.run(host="0.0.0.0", port=5001, debug=False)
