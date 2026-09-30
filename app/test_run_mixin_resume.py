"""Self-check (assert-based, no framework): resume-dari-NG harus reuse sesi
DB yang sama, bukan bikin sesi baru. Jalankan: python -m app.test_run_mixin_resume
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "lib"))  # buat `import test_modules`, dll
sys.path.insert(0, str(_ROOT))          # buat `import config`, dll
from unittest.mock import MagicMock

# Import langsung dari file, tanpa lewat app/__init__.py (yang import tkinter
# -- nggak dibutuhkan sama sekali buat test logika resume ini).
_spec = importlib.util.spec_from_file_location(
    "_run_mixin", Path(__file__).parent / "_run_mixin.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["_run_mixin"] = _mod
_spec.loader.exec_module(_mod)
RunMixin = _mod.RunMixin

from test_modules import TestResult


class _Row:
    def __init__(self, result=None):
        self.test_item = MagicMock(result=result, title="t")
    def reset(self):
        self.test_item.result = None
    def set_result(self, result, ok_msg=None):
        self.test_item.result = result


class _Fake(RunMixin):
    """Objek minimal yang punya semua atribut yang dipakai _do_start/_on_seq_done."""
    def __init__(self):
        self._resume_sn = ""
        self._device_var = MagicMock(get=lambda: "SN-1")
        self._list_panel = MagicMock(get_rows=lambda: self._rows)
        self._toggle_btn = MagicMock()
        self._status_var = MagicMock()
        self._controller = MagicMock()
        self._controller._uploader = None
        self.after = lambda *a, **k: None
        self._save_tasks = lambda: None
        self._load_resume_state = lambda: {}
        self._save_resume_state = lambda: None
        self._clear_resume_state = lambda: None
        self._reset_db_session = MagicMock(side_effect=self._fake_reset)
        self._new_db_session = MagicMock()
        self._finalize_db_session = MagicMock()

    def _fake_reset(self):
        self._controller._uploader = MagicMock(_session_id=40)


f = _Fake()

# 1) Start baru (SN belum pernah dipakai) -> harus bikin sesi baru (sesi 40).
f._rows = [_Row(), _Row()]
f._do_start()
assert f._reset_db_session.call_count == 1, "start baru harus reset_db_session (sesi baru)"
assert f._new_db_session.call_count == 0

# 2) Simulasikan sequence selesai dgn 1 test NG (test ke-2).
f._rows[0].test_item.result = TestResult.OK
f._rows[1].test_item.result = TestResult.NG
f._on_seq_done(None)
assert f._resume_sn == "SN-1"
assert f._finalize_db_session.call_count == 0, "NG tidak boleh langsung finalize sesi (biar bisa di-resume)"

# 3) Start lagi (resume, SN sama, uploader lama MASIH ada di memori dgn sesi 40).
f._do_start()
assert f._reset_db_session.call_count == 1, "resume TIDAK boleh bikin sesi baru"
assert f._new_db_session.call_count == 0, "uploader lama masih ada -> tidak perlu reattach"
assert f._controller._uploader._session_id == 40, "sesi harus tetap sesi 40"

# 4) Simulasikan test ke-2 sekarang PASS -> semua OK -> finalize "OK".
f._rows[1].test_item.result = TestResult.OK
f._on_seq_done(None)
assert f._finalize_db_session.call_args[0] == ("OK",)
assert f._resume_sn == ""

# 5) Resume setelah APP DI-RESTART: uploader hilang (None), _new_db_session harus dipanggil
#    untuk reattach ke sesi lama yang masih open di server.
f2 = _Fake()
f2._rows = [_Row(TestResult.OK), _Row(TestResult.NG)]
f2._resume_sn = ""
f2._controller._uploader = None
f2._load_resume_state = lambda: {"sn": "SN-1", "ok_step_indices": [0]}
f2._device_var = MagicMock(get=lambda: "SN-1")
f2._do_start()
assert f2._new_db_session.call_count == 1, "restart+resume harus coba reattach ke sesi open"
assert f2._reset_db_session.call_count == 0, "restart+resume TIDAK boleh bikin sesi baru"

print("OK - semua self-check resume/DB-session lolos")
