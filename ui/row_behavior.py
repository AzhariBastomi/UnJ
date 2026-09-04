"""
ui/row_behavior.py — Strategy + Polymorphism untuk TestRowWidget.

Setiap TestType (progress/manual/auto) punya kelas RowBehavior sendiri yang tahu:
  - cara membangun tombol kontrolnya (Run, atau OK/NG)
  - cara merespons saat mulai jalan / selesai / direset
  - warna badge nomor urut

TestRowWidget tidak perlu tahu tipe konkretnya sama sekali — ia cukup pegang satu
objek `self._behavior` dan panggil method di situ. Menambah TestType baru = menambah
1 class baru + daftarkan di BEHAVIOR_REGISTRY, tanpa mengubah TestRowWidget sama
sekali (Open/Closed Principle). Instansiasi objeknya sendiri lewat get_behavior()
(Factory Pattern).
"""

from test_modules import TestResult
from config import COLORS


class RowBehavior:
    """Default behavior — dipakai AutoTest: satu tombol Run, tanpa progress bar."""

    badge_color = "#27ae60"
    supports_validation = True   # tombol Run bisa di-disable proaktif oleh validate_fn

    # -- membangun UI --------------------------------------------------

    def build_control(self, row):
        row._run_btn = row._mk_btn("Run", "#27ae60", row._request_run)
        row._run_btn.pack(side="left")

    def build_progress_area(self, row, area, indent, bar_h):
        """No-op untuk tipe tanpa progress bar."""
        pass

    # -- siklus hidup test ----------------------------------------------

    def _run_btn_color(self) -> str:
        """Warna default tombol Run — di-override ProgressBehavior."""
        return "#27ae60"

    def set_running(self, row):
        """Jika item punya cancel_fn, tombol berubah jadi Stop (merah).
        Jika tidak, tombol di-disable seperti biasa."""
        fn = getattr(row.test_item, "cancel_fn", None)
        if fn:
            row._run_btn.config(
                text="Stop", bg="#e74c3c", state="normal",
                command=fn)
        else:
            row._run_btn.config(state="disabled")

    def _restore_run_btn(self, row):
        """Kembalikan tombol ke state Run normal."""
        row._run_btn.config(
            text="Run", bg=self._run_btn_color(), state="normal",
            command=row._request_run)

    def set_result(self, row, result, ok_brief, ok_detail, err_brief, err_detail, err_full):
        self._restore_run_btn(row)
        if result == TestResult.OK:
            row._status_lbl.config(
                text=ok_brief, fg=COLORS["ok"] if ok_brief else COLORS["sub"])
            row._bind_detail(ok_detail)
        else:
            row._status_lbl.config(text=err_brief, fg=COLORS["ng"])
            row._bind_detail(err_detail or err_full, leave_color=COLORS["ng"])

    def reset(self, row):
        self._restore_run_btn(row)


class ProgressBehavior(RowBehavior):
    """Auto test dengan progress bar (mis. flashing, sensor calibration)."""

    badge_color = "#3498db"

    def _run_btn_color(self) -> str:
        return "#3498db"

    def build_control(self, row):
        row._run_btn = row._mk_btn("Run", "#3498db", row._request_run)
        row._run_btn.pack(side="left")

    def build_progress_area(self, row, area, indent, bar_h):
        import tkinter as tk
        bg = COLORS["card"]
        tk.Frame(area, bg=bg, width=indent).pack(side="left")
        row._bar_cv = tk.Canvas(area, height=bar_h, bg=bg, highlightthickness=0, bd=0)
        row._bar_cv.pack(side="left", fill="x", expand=True, padx=(0, int(6 * row.scale)))
        row._bar_cv.bind("<Configure>", row._draw_bar)
        row._pct_lbl = tk.Label(
            area, text="0%", bg=bg, fg=COLORS["sub"],
            font=("TkDefaultFont", row._fs("small"), "bold"), width=4)
        row._pct_lbl.pack(side="right")

    def set_running(self, row):
        # Gunakan logika cancel_fn dari base class (tombol jadi Stop jika ada)
        super().set_running(row)
        row._pct = 0
        row._draw_bar()
        row._pct_lbl.config(text="0%", fg=COLORS["sub"])

    def set_result(self, row, result, ok_brief, ok_detail, err_brief, err_detail, err_full):
        if result == TestResult.OK:
            row._pct = 100
        row._draw_bar()
        row._pct_lbl.config(
            text=f"{row._pct}%",
            fg=COLORS["ok"] if result == TestResult.OK else COLORS["ng"])
        self._restore_run_btn(row)
        if result == TestResult.NG:
            row._status_lbl.config(text=err_brief, fg=COLORS["ng"])
            row._bind_detail(err_detail or err_full, leave_color=COLORS["ng"])
        else:
            row._status_lbl.config(
                text=ok_brief, fg=COLORS["ok"] if ok_brief else COLORS["sub"])
            row._bind_detail(ok_detail)

    def reset(self, row):
        self._restore_run_btn(row)
        row._pct = 0
        row._draw_bar()
        row._pct_lbl.config(text="0%", fg=COLORS["sub"])


class ManualBehavior(RowBehavior):
    """Test manual — operator konfirmasi lewat tombol OK/NG, tidak ada Run."""

    badge_color          = "#8e44ad"
    supports_validation  = False   # tidak ada tombol Run untuk di-disable

    def build_control(self, row):
        row._ok_btn = row._mk_btn(
            "OK", COLORS["ok"], lambda: row._manual_result(TestResult.OK))
        row._ok_btn.pack(side="left", padx=(0, int(3 * row.scale)))
        row._ng_btn = row._mk_btn(
            "NG", COLORS["ng"], lambda: row._manual_result(TestResult.NG))
        row._ng_btn.pack(side="left")

    def set_running(self, row):
        pass  # tidak ada tombol untuk didisable

    def set_result(self, row, result, ok_brief, ok_detail, err_brief, err_detail, err_full):
        pass  # teks status diatur langsung oleh TestRowWidget._manual_result

    def reset(self, row):
        pass


# ---------------------------------------------------------------------------
# Factory Pattern — satu titik untuk memilih behavior berdasar type_key milik
# TestItem (lihat lib/test_modules.py). Behavior stateless -> aman di-share satu
# instance untuk semua row.
# ---------------------------------------------------------------------------

BEHAVIOR_REGISTRY = {
    "progress": ProgressBehavior(),
    "manual":   ManualBehavior(),
    "auto":     RowBehavior(),
}


def get_behavior(type_key: str) -> RowBehavior:
    return BEHAVIOR_REGISTRY.get(type_key, BEHAVIOR_REGISTRY["auto"])
