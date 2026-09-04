"""
db_uploader.py — Upload hasil test ke Jig Flask server via REST API.

Backend yang didukung:
  - LocalServerUploader: HTTP ke server/app.py (Flask)

Contoh:
    from db_uploader import LocalServerUploader, LocalServerConfig, TestResultRecord

    uploader = LocalServerUploader(
        config=LocalServerConfig(base_url="http://localhost:5001"),
        station="ST-01", device_id="SN-123", project="tm81",
    )
    sid = uploader.new_session()
    rec = TestResultRecord(
        station="ST-01", device_id="SN-123", test_name="LED Test",
        command="TEST_LED", result="OK", duration_ms=1500,
    )
    uploader.upload(rec)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Data record
# ---------------------------------------------------------------------------

@dataclass
class TestResultRecord:
    station:     str
    device_id:   str
    test_name:   str
    command:     str
    result:      str                          # "OK" | "NG"
    duration_ms: int         = 0
    notes:       str         = ""
    timestamp:   datetime    = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        return self.result.upper() == "OK"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class UploaderBase:
    def upload(self, record: TestResultRecord) -> bool:
        raise NotImplementedError

    def upload_batch(self, records: list) -> bool:
        return all(self.upload(r) for r in records)

    def _safe(self, fn, record) -> bool:
        try:
            fn(record)
            return True
        except Exception as e:
            import logging
            logging.getLogger("db_uploader").warning("Upload error: %s", e)
            return False


# ---------------------------------------------------------------------------
# LocalServerUploader — kirim via REST API ke server/app.py (Flask)
# ---------------------------------------------------------------------------

@dataclass
class LocalServerConfig:
    base_url: str = "http://localhost:5001"
    timeout:  int = 5    # seconds


class LocalServerUploader(UploaderBase):
    """
    Upload hasil test ke Jig Flask server (server/app.py) via HTTP REST.
    Session ID dibuat otomatis saat pertama kali upload dipanggil.
    Set ulang dengan set_session_id() / new_session().
    """

    def __init__(self, config: "LocalServerConfig | None" = None,
                 station: str = "", device_id: str = "", project: "str | None" = None):
        self.cfg        = config or LocalServerConfig()
        self._station   = station
        self._device_id = device_id
        self._project   = project
        self._session_id: "int | None" = None

    def set_session_id(self, session_id: int):
        self._session_id = session_id

    def new_session(self, station: str = "", device_id: str = "",
                    project: "str | None" = None) -> "int | None":
        """Buat sesi baru dan simpan id-nya. Return session_id atau None jika gagal."""
        try:
            import urllib.request, json as _json
            payload = _json.dumps({
                "station":   station or self._station,
                "device_id": device_id or self._device_id,
                "project":   project or self._project,
            }).encode()
            req = urllib.request.Request(
                f"{self.cfg.base_url}/api/v1/sessions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                data = _json.loads(resp.read())
                self._session_id = data["id"]
                return self._session_id
        except Exception as e:
            import logging
            logging.getLogger("db_uploader").warning("new_session error: %s", e)
            return None

    def finalize_session(self, result: "str | None") -> bool:
        """Tandai session selesai via PATCH /api/v1/sessions/<id>."""
        if not self._session_id:
            return False
        try:
            import urllib.request, json as _json
            from datetime import datetime, timezone
            payload = _json.dumps({
                "result":      result,
                "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }).encode()
            req = urllib.request.Request(
                f"{self.cfg.base_url}/api/v1/sessions/{self._session_id}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="PATCH",
            )
            with urllib.request.urlopen(req, timeout=self.cfg.timeout):
                pass
            return True
        except Exception as e:
            import logging
            logging.getLogger("db_uploader").warning("finalize_session error: %s", e)
            return False

    def _ensure_session(self, record: "TestResultRecord") -> "int | None":
        if self._session_id:
            return self._session_id
        return self.new_session(station=record.station, device_id=record.device_id)

    def upload(self, record: "TestResultRecord") -> bool:
        def _do(r):
            import urllib.request, json as _json
            session_id = self._ensure_session(r)
            if not session_id:
                raise RuntimeError("Tidak bisa membuat session")
            payload = _json.dumps({
                "test_name":   r.test_name,
                "command":     r.command,
                "result":      r.result,
                "duration_ms": r.duration_ms,
                "notes":       r.notes,
                "timestamp":   r.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            }).encode()
            req = urllib.request.Request(
                f"{self.cfg.base_url}/api/v1/sessions/{session_id}/results",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                if resp.status not in (200, 201):
                    raise RuntimeError(f"HTTP {resp.status}")
        return self._safe(_do, record)
