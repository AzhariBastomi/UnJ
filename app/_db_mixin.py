"""DbMixin — database session (new / finalize / reset)."""

import os, json, threading, logging

log = logging.getLogger("main")


class DbMixin:

    def _reset_db_session(self):
        """Tutup session lama lalu buat session baru (force_new, synchronous)."""
        uploader = self._controller._uploader
        if uploader and getattr(uploader, "_session_id", None):
            self._finalize_db_session(None)
        self._new_db_session(force_new=True)

    @staticmethod
    def _load_db_config() -> dict:
        try:
            path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("database", {})
        except Exception:
            return {}

    def _new_db_session(self, force_new: bool = False):
        db_cfg = self._load_db_config()
        if not db_cfg.get("enabled", True):
            self._controller._uploader = None
            return

        device_id = self._device_var.get().strip() if hasattr(self, "_device_var") else ""
        url       = db_cfg.get("server_url", "http://localhost:5001")

        try:
            from db_uploader import LocalServerUploader, LocalServerConfig
            uploader = LocalServerUploader(
                config=LocalServerConfig(base_url=url),
                station=self._station,
                device_id=device_id,
                project=self._project,
            )
            if force_new:
                sid = uploader.new_session()
                if sid:
                    log.info("DB: session baru #%d (device=%r)", sid, device_id)
                else:
                    log.warning("DB: gagal buat session di %s", url)
            else:
                sid = self._find_open_session_server(url, device_id)
                if sid:
                    uploader.set_session_id(sid)
                    log.info("DB: resume session #%d (device=%r)", sid, device_id)

            self._controller._uploader = uploader

        except Exception as e:
            log.warning("Gagal init DB uploader: %s", e)
            self._controller._uploader = None

    @staticmethod
    def _find_open_session_server(base_url: str, device_id: str) -> "int | None":
        if not device_id:
            return None
        try:
            import urllib.request, urllib.parse, json as _json
            url = f"{base_url}/api/v1/devices/{urllib.parse.quote(device_id)}"
            with urllib.request.urlopen(url, timeout=3) as resp:
                sessions = _json.loads(resp.read())
            for s in sessions:
                if not s.get("finished_at"):
                    return s["id"]
            return None
        except Exception:
            return None

    def _finalize_db_session(self, result: "str | None"):
        uploader = self._controller._uploader
        if not uploader or not getattr(uploader, "_session_id", None):
            return
        sid = uploader._session_id
        def _do():
            ok = uploader.finalize_session(result)
            if ok:
                log.info("DB session #%d selesai: %s", sid, result or "?")
            else:
                log.warning("Gagal finalize DB session #%d", sid)
        threading.Thread(target=_do, daemon=True).start()
