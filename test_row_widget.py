"""
test_row_widget.py - Card-based test row widget.

Run standalone for a visual demo:
    python test_row_widget.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

import tkinter as tk
from test_modules import TestType, TestResult
from config import COLORS, BASE_FONTS

BADGE_TEXT = {
    TestResult.PENDING: "---",
    TestResult.RUNNING: "...",
    TestResult.OK:      " OK ",
    TestResult.NG:      " NG ",
}
BADGE_BG = {
    TestResult.PENDING: COLORS["pending"],
    TestResult.RUNNING: COLORS["running"],
    TestResult.OK:      COLORS["ok"],
    TestResult.NG:      COLORS["ng"],
}
BADGE_FG = "white"

TYPE_COLOR = {
    TestType.PROGRESS: "#3498db",
    TestType.MANUAL:   "#8e44ad",
    TestType.AUTO:     "#27ae60",
}


def _pill(cv, x1, y1, x2, y2, r, fill):
    r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    if r < 1:
        cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        return
    cv.create_arc(x1,        y1, x1 + 2*r, y2, start=90,  extent=180, fill=fill, outline="")
    cv.create_arc(x2 - 2*r, y1, x2,        y2, start=270, extent=180, fill=fill, outline="")
    if x1 + r < x2 - r:
        cv.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")


def _pcolor(p: int) -> str:
    if p < 40:   return COLORS["ng"]
    elif p < 80: return COLORS["warn"]
    else:        return COLORS["ok"]


class TestRowWidget:
    def __init__(self, master, test_item, index, scale, on_run_request):
        self.master         = master
        self.test_item      = test_item
        self.index          = index
        self.scale          = scale
        self.on_run_request = on_run_request
        self._detail_text   = ""
        self._pct           = 0
        self._build()

    def _fs(self, k):
        return max(7, int(BASE_FONTS[k] * self.scale))

    # ------------------------------------------------------------------ build

    def _build(self):
        s  = self.scale
        bg = COLORS["card"]

        # Card frame
        self.frame = tk.Frame(
            self.master, bg=bg,
            highlightbackground=COLORS["border"],
            highlightthickness=1)
        self.frame.pack(fill="x", padx=int(8*s), pady=(0, int(5*s)))

        inner = tk.Frame(self.frame, bg=bg, padx=int(10*s), pady=int(8*s))
        inner.pack(fill="both", expand=True)

        # ── Left: content column ──────────────────────────────────────
        content = tk.Frame(inner, bg=bg)
        content.pack(side="left", fill="both", expand=True)

        # Row 1: type-badge + title
        r1 = tk.Frame(content, bg=bg)
        r1.pack(fill="x")

        tc = TYPE_COLOR.get(self.test_item.test_type, COLORS["running"])
        self._num_badge = tk.Label(
            r1, text=f"{self.index+1:02d}",
            bg=tc, fg="white",
            font=("TkDefaultFont", self._fs("button"), "bold"),
            width=3, pady=int(2*s), anchor="center")
        self._num_badge.pack(side="left", padx=(0, int(8*s)))

        tk.Label(
            r1, text=self.test_item.title,
            bg=bg, fg=COLORS["text"],
            font=("TkDefaultFont", self._fs("label"), "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Row 2: status label + control buttons (inline, same row)
        r2 = tk.Frame(content, bg=bg)
        r2.pack(fill="x", pady=(int(3*s), 0))

        indent = self._num_badge.winfo_reqwidth() + int(8*s)
        tk.Frame(r2, bg=bg, width=indent).pack(side="left")

        self._status_lbl = tk.Label(
            r2, text="",
            bg=bg, fg=COLORS["sub"],
            font=("TkDefaultFont", self._fs("small")),
            anchor="w")
        self._status_lbl.pack(side="left", fill="x", expand=True)
        self._status_lbl.bind("<Configure>",
            lambda e: self._status_lbl.config(wraplength=e.width) if e.width > 20 else None)

        # Control buttons — right of status label
        self._ctrl = tk.Frame(r2, bg=bg)
        self._ctrl.pack(side="left", padx=(int(6*s), 0))
        self._build_control()

        # Row 3: progress area — fixed height for all types
        bar_h   = int(8  * s)
        pad_top = int(5  * s)
        r3 = tk.Frame(content, bg=bg, height=bar_h + pad_top)
        r3.pack(fill="x", pady=(pad_top, 0))
        r3.pack_propagate(False)

        if self.test_item.test_type == TestType.PROGRESS:
            tk.Frame(r3, bg=bg, width=indent).pack(side="left")
            self._bar_cv = tk.Canvas(
                r3, height=bar_h, bg=bg,
                highlightthickness=0, bd=0)
            self._bar_cv.pack(side="left", fill="x", expand=True,
                              padx=(0, int(6*s)))
            self._bar_cv.bind("<Configure>", self._draw_bar)
            self._pct_lbl = tk.Label(
                r3, text="0%",
                bg=bg, fg=COLORS["sub"],
                font=("TkDefaultFont", self._fs("small"), "bold"),
                width=4)
            self._pct_lbl.pack(side="right")

        # ── Right: result badge only, vertically centered ─────────────
        actions = tk.Frame(inner, bg=bg)
        actions.pack(side="right", fill="y", padx=(int(8*s), 0))

        mid = tk.Frame(actions, bg=bg)
        mid.pack(expand=True, anchor="center")

        self._badge_var = tk.StringVar(value=BADGE_TEXT[self.test_item.result])
        self._badge = tk.Label(
            mid, textvariable=self._badge_var,
            bg=BADGE_BG[self.test_item.result],
            fg=BADGE_FG,
            font=("TkDefaultFont", self._fs("small"), "bold"),
            width=5, anchor="center",
            padx=int(3*s), pady=int(2*s))
        self._badge.pack()

    def _build_control(self):
        t = self.test_item.test_type
        s = self.scale
        if t == TestType.PROGRESS:
            self._run_btn = self._mk_btn("Run", "#3498db", self._request_run)
            self._run_btn.pack(side="left")
        elif t == TestType.MANUAL:
            self._ok_btn = self._mk_btn("OK", COLORS["ok"],
                lambda: self._manual_result(TestResult.OK))
            self._ok_btn.pack(side="left", padx=(0, int(3*s)))
            self._ng_btn = self._mk_btn("NG", COLORS["ng"],
                lambda: self._manual_result(TestResult.NG))
            self._ng_btn.pack(side="left")
        elif t == TestType.AUTO:
            self._run_btn = self._mk_btn("Run", "#27ae60", self._request_run)
            self._run_btn.pack(side="left")

    def _mk_btn(self, text, color, cmd):
        s = self.scale
        return tk.Button(
            self._ctrl, text=text, width=5,
            font=("TkDefaultFont", self._fs("button")),
            bg=color, fg="white", relief="flat",
            padx=int(4*s), pady=int(2*s),
            cursor="hand2", command=cmd)

    # ---------------------------------------------------------------- pill bar

    def _draw_bar(self, _=None):
        if not hasattr(self, "_bar_cv"):
            return
        cv = self._bar_cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 4 or h < 2:
            return
        r = h // 2
        _pill(cv, 0, 0, w, h, r, COLORS["bar_bg"])
        fw = max(int(w * self._pct / 100), 0)
        if fw > 0:
            _pill(cv, 0, 0, fw, h, r, _pcolor(self._pct))

    # ---------------------------------------------------------------- state

    def set_running(self):
        self.test_item.result = TestResult.RUNNING
        self._update_badge()
        self._status_lbl.config(text="Running…", fg=COLORS["running"])
        t = self.test_item.test_type
        if t in (TestType.PROGRESS, TestType.AUTO):
            self._run_btn.config(state="disabled")
        if t == TestType.PROGRESS:
            self._pct = 0
            self._draw_bar()
            self._pct_lbl.config(text="0%", fg=COLORS["sub"])

    def set_result(self, result, error: str = "", ok_msg: str = ""):
        self.test_item.result = result
        if error:
            self.test_item.last_error = error
        self._update_badge()
        t = self.test_item.test_type

        BRIEF_MAX = max(20, int(int(220 * self.scale) // 7))
        lines = ok_msg.split("\n") if ok_msg else [""]
        if len(lines) > 1 or len(ok_msg) > BRIEF_MAX:
            first  = lines[0]
            brief  = (first[:BRIEF_MAX] + "…") if len(first) > BRIEF_MAX else first
            detail = ok_msg
        else:
            brief, detail = ok_msg, ""

        if t == TestType.PROGRESS:
            if result == TestResult.OK:
                self._pct = 100
            self._draw_bar()
            self._pct_lbl.config(
                text=f"{self._pct}%",
                fg=COLORS["ok"] if result == TestResult.OK else COLORS["ng"])
            self._run_btn.config(state="normal")
            if result == TestResult.NG:
                self._status_lbl.config(
                    text=error or self.test_item.last_error or "NG",
                    fg=COLORS["ng"])
                self._unbind_detail()
            else:
                self._status_lbl.config(
                    text=brief,
                    fg=COLORS["ok"] if brief else COLORS["sub"])
                self._bind_detail(detail)

        elif t == TestType.MANUAL:
            pass

        elif t == TestType.AUTO:
            self._run_btn.config(state="normal")
            if result == TestResult.OK:
                self._status_lbl.config(
                    text=brief,
                    fg=COLORS["ok"] if brief else COLORS["sub"])
                self._bind_detail(detail)
            else:
                self._status_lbl.config(
                    text=error or self.test_item.last_error or "NG",
                    fg=COLORS["ng"])
                self._unbind_detail()

    def advance_progress(self, percent: int):
        if not hasattr(self, "_bar_cv"):
            return
        self._pct = percent
        self._draw_bar()
        self._pct_lbl.config(text=f"{percent}%", fg=_pcolor(percent))

    def enable_manual_buttons(self):
        if self.test_item.test_type == TestType.MANUAL:
            self._status_lbl.config(text="Periksa & konfirmasi", fg=COLORS["warn"])

    def reset(self):
        self.test_item.reset()
        self._update_badge()
        self._status_lbl.config(text="", fg=COLORS["sub"])
        self._unbind_detail()
        t = self.test_item.test_type
        if t in (TestType.PROGRESS, TestType.AUTO):
            self._run_btn.config(state="normal")
        if t == TestType.PROGRESS:
            self._pct = 0
            self._draw_bar()
            self._pct_lbl.config(text="0%", fg=COLORS["sub"])

    def destroy(self):
        self.frame.destroy()

    # ---------------------------------------------------------------- detail popup

    def _bind_detail(self, detail: str):
        if not detail:
            self._unbind_detail()
            return
        self._detail_text = detail
        self._status_lbl.config(cursor="hand2")
        self._status_lbl.bind("<Button-1>", self._show_detail_popup)
        self._status_lbl.bind("<Enter>",
            lambda e: self._status_lbl.config(fg=COLORS["text"]))
        self._status_lbl.bind("<Leave>",
            lambda e: self._status_lbl.config(fg=COLORS["ok"]))

    def _unbind_detail(self):
        self._detail_text = ""
        self._status_lbl.config(cursor="")
        self._status_lbl.unbind("<Button-1>")
        self._status_lbl.unbind("<Enter>")
        self._status_lbl.unbind("<Leave>")

    def _show_detail_popup(self, event=None):
        detail = getattr(self, "_detail_text", "")
        if not detail:
            return
        popup = tk.Toplevel(self.frame)
        popup.title(self.test_item.title)
        popup.resizable(False, False)
        popup.configure(bg=COLORS["surface"])

        fs_h = max(8, int(11 * self.scale))
        fs_b = max(7, int(10 * self.scale))

        tk.Label(popup, text=self.test_item.title,
                 font=("TkDefaultFont", fs_h, "bold"),
                 bg=COLORS["surface"], fg=COLORS["ok"],
                 pady=8, padx=16).pack(anchor="w")
        tk.Frame(popup, height=1, bg=COLORS["border"]).pack(fill="x", padx=12)

        frm = tk.Frame(popup, bg=COLORS["surface"], padx=16, pady=10)
        frm.pack(fill="both")

        for line in detail.strip().split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                rf = tk.Frame(frm, bg=COLORS["surface"])
                rf.pack(fill="x", pady=1)
                tk.Label(rf, text=key.strip(),
                         bg=COLORS["surface"], fg=COLORS["sub"],
                         font=("TkDefaultFont", fs_b),
                         width=14, anchor="w").pack(side="left")
                tk.Label(rf, text=": " + val.strip(),
                         bg=COLORS["surface"], fg=COLORS["text"],
                         font=("TkDefaultFont", fs_b, "bold"),
                         anchor="w").pack(side="left")
            else:
                tk.Label(frm, text=line,
                         bg=COLORS["surface"], fg=COLORS["text"],
                         font=("TkDefaultFont", fs_b),
                         anchor="w").pack(fill="x", pady=1)

        tk.Frame(popup, height=1, bg=COLORS["border"]).pack(fill="x", padx=12)
        tk.Button(popup, text="Tutup", width=10, command=popup.destroy,
                  bg=COLORS["header_bg"], fg=COLORS["header_fg"], relief="flat",
                  font=("TkDefaultFont", fs_b),
                  pady=4, cursor="hand2").pack(pady=10)

        popup.update_idletasks()
        root = self.frame.winfo_toplevel()
        px = root.winfo_rootx() + root.winfo_width()  // 2 - popup.winfo_width()  // 2
        py = root.winfo_rooty() + root.winfo_height() // 2 - popup.winfo_height() // 2
        popup.geometry(f"+{px}+{py}")

        def _on_root_click(e, p=popup):
            if not p.winfo_exists():
                return
            rx, ry = p.winfo_rootx(), p.winfo_rooty()
            rw, rh = p.winfo_width(), p.winfo_height()
            if not (rx <= e.x_root <= rx + rw and ry <= e.y_root <= ry + rh):
                p.destroy()

        _bid = root.bind("<Button-1>", _on_root_click, add="+")

        def _cleanup(e=None):
            try:
                root.unbind("<Button-1>", _bid)
            except Exception:
                pass

        popup.bind("<Destroy>", lambda e: _cleanup() if e.widget is popup else None)
        popup.protocol("WM_DELETE_WINDOW", lambda: (_cleanup(), popup.destroy()))

    # ---------------------------------------------------------------- internals

    def _update_badge(self):
        r = self.test_item.result
        self._badge_var.set(BADGE_TEXT[r])
        self._badge.config(bg=BADGE_BG[r], fg=BADGE_FG)

    def _request_run(self):
        self.on_run_request(self)

    def _manual_result(self, result):
        print(f"[widget] _manual_result: {self.test_item.title} -> {result}", flush=True)
        self.set_result(result)
        if result == TestResult.NG:
            self._status_lbl.config(text="NG — operator", fg=COLORS["ng"])
        else:
            self._status_lbl.config(text="", fg=COLORS["sub"])


# =============================================================================
# Standalone demo — python test_row_widget.py
# =============================================================================

if __name__ == "__main__":
    from test_modules import TestItem, ProgressBarTest, ManualTest

    root = tk.Tk()
    root.title("TestRowWidget — Demo")
    root.geometry("800x520")
    root.configure(bg=COLORS["bg"])

    cv     = tk.Canvas(root, bg=COLORS["bg"], highlightthickness=0)
    cv.pack(fill="both", expand=True, pady=8)
    inner  = tk.Frame(cv, bg=COLORS["bg"])
    wid    = cv.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
    cv.bind("<Configure>",    lambda e: cv.itemconfig(wid, width=e.width))

    def _noop(row):
        print(f"[demo] Run: {row.test_item.title}")

    items = [
        TestItem("Ping MCU",            "ping",     ""),
        TestItem("Get Firmware Version","fw_ver",   ""),
        ProgressBarTest("Sensor Calibration", "sensor_cal", steps=5),
        ManualTest("Visual Check",      "visual",   ""),
        TestItem("Get Device ID",       "dev_id",   ""),
        TestItem("Set RTC",             "rtc_set",  ""),
    ]

    rows = []
    for i, item in enumerate(items):
        rows.append(TestRowWidget(inner, item, i, scale=1.0, on_run_request=_noop))

    def _demo():
        rows[0].set_result(TestResult.OK, ok_msg="Pong received")
        rows[1].set_result(TestResult.OK,
            ok_msg="App v0.1.0 / BL v0.0.1\nBuild : 2025-05-10\nHW Rev: C")
        rows[2].set_running()
        root.after(600,  lambda: rows[2].advance_progress(40))
        root.after(1200, lambda: rows[2].advance_progress(75))
        root.after(1800, lambda: rows[2].set_result(TestResult.OK, ok_msg="Cal done"))
        rows[3].set_running()
        rows[4].set_result(TestResult.NG, error="Timeout: no response")
        rows[5].set_result(TestResult.OK,
            ok_msg="Serial No  : TM81-00123\nDevice EUI : 00:80:e1:01:01:01:01:69")

    root.after(300, _demo)
    root.mainloop()
