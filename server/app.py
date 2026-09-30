"""
server/app.py — Flask REST API + website sederhana untuk Jig test database.

Run (SQLite lokal, default):
    pip install -r server/requirements.txt
    python server/app.py

Run dengan PostgreSQL (lihat folder database/ untuk docker-compose):
    set JIG_DB_URL=postgresql://jig:jig@localhost:5432/jig   (Windows PowerShell: $env:JIG_DB_URL=...)
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

Website (dashboard sederhana):
  GET    /                                       List station
  GET    /station/<station>                      List SN dalam station
  GET    /station/<station>/sn/<device_id>        List test untuk SN tsb

Health:
  GET    /health                                 Cek server aktif
"""

import sys, os
# Tambah root project ke path agar bisa import dari lib/
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "lib"))

from flask import Flask, request, jsonify, abort, render_template_string
# from server.db import init_db, db_conn, now_iso, row_to_dict, DB_PATH, BACKEND
from db import init_db, db_conn, now_iso, row_to_dict, BACKEND, PG_URL

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
    return jsonify({"status": "ok", "backend": BACKEND, "db": PG_URL})


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
        total_sessions  = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        total_results   = conn.execute("SELECT COUNT(*) AS c FROM test_results").fetchone()["c"]
        ok_count        = conn.execute(
            "SELECT COUNT(*) AS c FROM test_results WHERE result='OK'"
        ).fetchone()["c"]
        ng_count        = conn.execute(
            "SELECT COUNT(*) AS c FROM test_results WHERE result='NG'"
        ).fetchone()["c"]
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
# Website sederhana — Station -> SN -> Test list
# ---------------------------------------------------------------------------

_BASE_HTML = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} — Jig Dashboard</title>
<style>
  :root{color-scheme:light dark;
    --bg:#0b0d12; --bg-elev:#12151c; --border:#232833;
    --text:#e8ebf0; --text-dim:#8b95a5; --accent:#5b9df5;
    --ok-bg:rgba(34,197,94,.12); --ok:#4ade80;
    --ng-bg:rgba(248,113,113,.12); --ng:#f87171;
    --pending-bg:rgba(250,204,21,.12); --pending:#facc15;
    --radius:10px;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--text)}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;
    padding:14px 24px;background:var(--bg-elev);border-bottom:1px solid var(--border);flex-wrap:wrap;gap:10px}
  .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px}
  .brand .dot-logo{width:8px;height:8px;border-radius:50%;background:var(--accent)}
  .live{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-dim)}
  .live .pulse{width:8px;height:8px;border-radius:50%;background:var(--ok);animation:pulse 2s infinite}
  .live.paused .pulse{background:var(--text-dim);animation:none}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(74,222,128,.5)}70%{box-shadow:0 0 0 6px rgba(74,222,128,0)}100%{box-shadow:0 0 0 0 rgba(74,222,128,0)}}
  .live button{background:none;border:1px solid var(--border);color:var(--text-dim);border-radius:6px;
    padding:3px 10px;font-size:11px;cursor:pointer}
  .live button:hover{color:var(--text);border-color:var(--accent)}
  .wrap{max-width:1040px;margin:0 auto;padding:28px 20px 60px}
  h1{font-size:21px;margin:0 0 6px}
  .crumb{color:var(--text-dim);font-size:13px;margin-bottom:22px}
  .crumb a{color:var(--text-dim)}
  .crumb a:hover{color:var(--accent)}
  .stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
  .stat-card{background:var(--bg-elev);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px}
  .stat-card .num{font-size:24px;font-weight:700}
  .stat-card .label{font-size:12px;color:var(--text-dim);margin-top:2px}
  .stat-card.ok .num{color:var(--ok)}
  .stat-card.ng .num{color:var(--ng)}
  table{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:var(--bg-elev)}
  th,td{text-align:left;padding:12px 16px;border-bottom:1px solid var(--border);font-size:14px}
  th{color:var(--text-dim);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;
    background:rgba(255,255,255,.02)}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:rgba(255,255,255,.03)}
  .badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
  .badge::before{content:"";width:6px;height:6px;border-radius:50%}
  .badge.ok{background:var(--ok-bg);color:var(--ok)} .badge.ok::before{background:var(--ok)}
  .badge.ng{background:var(--ng-bg);color:var(--ng)} .badge.ng::before{background:var(--ng)}
  .badge.pending{background:var(--pending-bg);color:var(--pending)} .badge.pending::before{background:var(--pending)}
  .empty{color:var(--text-dim);padding:40px 20px;text-align:center;background:var(--bg-elev);
    border:1px solid var(--border);border-radius:var(--radius)}
  .meta{color:var(--text-dim);font-size:13px;font-weight:400}
  .foot{margin-top:28px;color:#4b5262;font-size:12px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}
  details.session{background:var(--bg-elev);border:1px solid var(--border);border-radius:var(--radius);
    margin-bottom:10px;overflow:hidden}
  details.session summary{list-style:none;cursor:pointer;padding:14px 16px;display:flex;align-items:center;
    gap:10px;flex-wrap:wrap}
  details.session summary::-webkit-details-marker{display:none}
  details.session summary::before{content:"▸";color:var(--text-dim);font-size:11px;transition:transform .15s;display:inline-block}
  details.session[open] summary::before{transform:rotate(90deg)}
  details.session .session-body{border-top:1px solid var(--border)}
  details.session .session-body table{border:none;border-radius:0}
  .sess-title{font-weight:600;font-size:14px}
  @media (max-width:600px){.topbar{padding:12px 16px}.wrap{padding:20px 14px 48px}}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand"><span class="dot-logo"></span> Universal-JIG Dashboard</div>
  <div class="live" id="live-wrap">
    <span class="pulse" id="live-dot"></span>
    <span>Live &middot; update tiap 5 detik &middot; terakhir <span id="live-time">-</span></span>
    <button id="live-toggle" type="button">Pause</button>
  </div>
</div>
<div class="wrap">
<h1>{{ heading }}</h1>
<div class="crumb">{{ crumb|safe }}</div>
{% if stats_html %}{{ stats_html|safe }}{% endif %}
<div id="dashboard-body">{{ body|safe }}</div>
<div class="foot"><span>Backend: {{ backend }}</span><span>Klik judul sesi untuk buka/tutup detail</span></div>
</div>
<script>
(function(){
  var live = true;
  function fmtNow(){ return new Date().toLocaleTimeString('id-ID'); }
  function collectOpenIds(){
    var ids = [];
    document.querySelectorAll('details.session[open]').forEach(function(el){ ids.push(el.getAttribute('data-sid')); });
    return ids;
  }
  function applyOpenIds(ids){
    document.querySelectorAll('details.session').forEach(function(el){
      if (ids.indexOf(el.getAttribute('data-sid')) !== -1) { el.setAttribute('open',''); }
    });
  }
  function refresh(){
    if (!live || document.hidden) return;
    fetch(window.location.href, {cache:'no-store'}).then(function(r){ return r.text(); }).then(function(html){
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var fresh = doc.getElementById('dashboard-body');
      var current = document.getElementById('dashboard-body');
      if (fresh && current && fresh.innerHTML !== current.innerHTML) {
        var openIds = collectOpenIds();
        current.innerHTML = fresh.innerHTML;
        applyOpenIds(openIds);
      }
      var t = document.getElementById('live-time');
      if (t) t.textContent = fmtNow();
    }).catch(function(){});
  }
  document.addEventListener('DOMContentLoaded', function(){
    var t = document.getElementById('live-time');
    if (t) t.textContent = fmtNow();
    var btn = document.getElementById('live-toggle');
    if (btn) {
      btn.addEventListener('click', function(){
        live = !live;
        btn.textContent = live ? 'Pause' : 'Resume';
        var wrap = document.getElementById('live-wrap');
        if (wrap) wrap.classList.toggle('paused', !live);
      });
    }
    setInterval(refresh, 5000);
  });
})();
</script>
</body>
</html>
"""


def _badge(result):
    if result == "OK":
        return '<span class="badge ok">OK</span>'
    if result == "NG":
        return '<span class="badge ng">NG</span>'
    return '<span class="badge pending">Berjalan</span>'


@app.get("/")
def dashboard_stations():
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT station, device_id, result FROM sessions ORDER BY station"
        ).fetchall()
        total_sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        ng_sessions = conn.execute(
            "SELECT COUNT(*) AS c FROM sessions WHERE result='NG'"
        ).fetchone()["c"]

    stations = {}
    all_sn = set()
    for r in rows:
        d = row_to_dict(r)
        st = d["station"] or "(tanpa nama)"
        entry = stations.setdefault(st, {"sn_count": set()})
        entry["sn_count"].add(d["device_id"])
        all_sn.add(d["device_id"])

    stats_html = (
        '<div class="stats-row">'
        f'<div class="stat-card"><div class="num">{len(stations)}</div><div class="label">Station</div></div>'
        f'<div class="stat-card"><div class="num">{len(all_sn)}</div><div class="label">Total SN</div></div>'
        f'<div class="stat-card"><div class="num">{total_sessions}</div><div class="label">Total Sesi</div></div>'
        f'<div class="stat-card ng"><div class="num">{ng_sessions}</div><div class="label">Sesi NG</div></div>'
        "</div>"
    )

    if stations:
        body_rows = "\n".join(
            f'<tr><td><a href="/station/{st}">{st}</a></td>'
            f'<td>{len(v["sn_count"])}</td></tr>'
            for st, v in sorted(stations.items())
        )
        body = (
            "<table><tr><th>Station</th><th>Jumlah SN</th></tr>"
            + body_rows + "</table>"
        )
    else:
        body = '<div class="empty">Belum ada data test. Jalankan Universal-JIG dengan database.enabled=1.</div>'

    return render_template_string(
        _BASE_HTML, title="Station", heading="Daftar Station",
        crumb="Station", body=body, backend=BACKEND, stats_html=stats_html,
    )


@app.get("/station/<path:station>")
def dashboard_station_detail(station):
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE station = ? ORDER BY id DESC",
            (station,),
        ).fetchall()

    sns = {}
    for r in rows:
        d = row_to_dict(r)
        sn = d["device_id"] or "(tanpa SN)"
        entry = sns.setdefault(sn, {"last_result": None, "last_created": None})
        if entry["last_created"] is None or d["created_at"] > entry["last_created"]:
            entry["last_created"] = d["created_at"]
            entry["last_result"]  = d["result"]

    ok_count = sum(1 for v in sns.values() if v["last_result"] == "OK")
    ng_count = sum(1 for v in sns.values() if v["last_result"] == "NG")
    stats_html = (
        '<div class="stats-row">'
        f'<div class="stat-card"><div class="num">{len(sns)}</div><div class="label">Serial Number</div></div>'
        f'<div class="stat-card ok"><div class="num">{ok_count}</div><div class="label">Terakhir OK</div></div>'
        f'<div class="stat-card ng"><div class="num">{ng_count}</div><div class="label">Terakhir NG</div></div>'
        "</div>"
    )

    if sns:
        body_rows = "\n".join(
            f'<tr><td><a href="/station/{station}/sn/{sn}">{sn}</a></td>'
            f'<td>{v["last_created"] or "-"}</td>'
            f'<td>{_badge(v["last_result"])}</td></tr>'
            for sn, v in sorted(sns.items(), key=lambda kv: kv[1]["last_created"] or "", reverse=True)
        )
        body = (
            "<table><tr><th>Serial Number</th>"
            "<th>Terakhir Ditest</th><th>Hasil Terakhir</th></tr>" + body_rows + "</table>"
        )
    else:
        body = '<div class="empty">Belum ada SN untuk station ini.</div>'
        stats_html = ""

    crumb = f'<a href="/">Station</a> / {station}'
    return render_template_string(
        _BASE_HTML, title=station, heading=f"Station: {station}",
        crumb=crumb, body=body, backend=BACKEND, stats_html=stats_html,
    )


@app.get("/station/<path:station>/sn/<path:device_id>")
def dashboard_sn_detail(station, device_id):
    with db_conn() as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE station = ? AND device_id = ? ORDER BY id DESC",
            (station, device_id),
        ).fetchall()
        session_ids = [row_to_dict(s)["id"] for s in sessions]
        results_by_session = {}
        for sid in session_ids:
            rs = conn.execute(
                "SELECT * FROM test_results WHERE session_id = ? ORDER BY id",
                (sid,),
            ).fetchall()
            results_by_session[sid] = [row_to_dict(r) for r in rs]

    if sessions:
        # Nomor sesi per-SN: sesi pertama untuk SN ini = #1, dst — bukan
        # id global di tabel sessions (yang dipakai bareng semua SN/station).
        ids_chronological = sorted(row_to_dict(s)["id"] for s in sessions)
        seq_by_id = {sid: i + 1 for i, sid in enumerate(ids_chronological)}

        blocks = []
        for i, s in enumerate(sessions):
            sd = row_to_dict(s)
            trs = results_by_session.get(sd["id"], [])
            if trs:
                test_rows = "\n".join(
                    f'<tr><td>{t["test_name"]}</td><td>{t["command"]}</td>'
                    f'<td>{_badge(t["result"])}</td><td>{t["duration_ms"]} ms</td>'
                    f'<td>{t["timestamp"]}</td><td>{t["notes"]}</td></tr>'
                    for t in trs
                )
                test_table = (
                    '<table><tr><th>Test</th><th>Command</th><th>Hasil</th>'
                    "<th>Durasi</th><th>Jam</th><th>Catatan</th></tr>" + test_rows + "</table>"
                )
            else:
                test_table = '<div class="empty">Belum ada hasil test untuk sesi ini.</div>'

            # Sesi paling baru (index 0, karena diurutkan DESC) tampil terbuka
            # secara default; sesi lama lainnya diciutkan (dropdown/collapse).
            open_attr = " open" if i == 0 else ""
            blocks.append(
                f'<details class="session" data-sid="{sd["id"]}"{open_attr}>'
                f'<summary><span class="sess-title">Sesi #{seq_by_id[sd["id"]]}</span> '
                f'{_badge(sd["result"])} '
                f'<span class="meta">mulai {sd["created_at"]}'
                + (f", selesai {sd['finished_at']}" if sd["finished_at"] else ", masih berjalan")
                + '</span></summary><div class="session-body">' + test_table + "</div></details>"
            )
        body = "\n".join(blocks)
    else:
        body = '<div class="empty">SN ini belum punya riwayat test.</div>'

    crumb = f'<a href="/">Station</a> / <a href="/station/{station}">{station}</a> / {device_id}'
    return render_template_string(
        _BASE_HTML, title=device_id, heading=f"SN: {device_id}",
        crumb=crumb, body=body, backend=BACKEND,
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": str(e)}), e.code
    return f"<h2>Error {e.code}</h2><p>{e.description}</p><p><a href='/'>&larr; Kembali</a></p>", e.code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print(f"Jig DB Server — backend: {BACKEND}")
    print("API:       http://localhost:5001/api/v1/")
    print("Dashboard: http://localhost:5001/")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
