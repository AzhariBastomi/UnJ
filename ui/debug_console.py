"""
ui/debug_console.py — Floating debug log window.

Menampilkan log dari semua logger Python secara real-time dengan:
- Warna per level (DEBUG / INFO / WARNING / ERROR)
- Filter minimum level via radio button
- Filter by logger name (pre-set saat buka, bisa diubah)
- Auto-scroll (pause saat scroll naik, lanjut saat kembali ke bawah)
- Max 1000 baris (baris lama otomatis dihapus)
- Tombol Clear

Bisa dibuka multiple instance dengan filter berbeda (misal satu untuk serial_comm,
satu untuk semua log).
"""

import logging
import queue
import sys
import os
import tkinter as tk

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from config import COLORS

# ---------------------------------------------------------------------------
# Warna per level — dark-terminal palette
# ---------------------------------------------------------------------------
_LEVEL_FG = {
    logging.DEBUG:    "#6e7681",
    logging.INFO:     "#c9d1d9",
    logging.WARNING:  "#e3b341",
    logging.ERROR:    "#f85149",
    logging.CRITICAL: "#ff7b72",
}
_BG        = "#0d1117"
_HEADER_BG = "#161b22"
_BORDER    = "#30363d"

_LEVELS    = ["DEBUG", "INFO", "WARNING", "ERROR"]
_LEVEL_NUM = {n: getattr(logging, n) for n in _LEVELS}


# ---------------------------------------------------------------------------
# Thread-safe queue handler
# ---------------------------------------------------------------------------
class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord):
        try:
            self._q.put_nowait(record)
        except queue.Full:
            pass


# ---------------------------------------------------------------------------
# DebugConsole
# ---------------------------------------------------------------------------
class DebugConsole(tk.Toplevel):
    MAX_LINES = 1000
    POLL_MS   = 80

    def __init__(self, master=None, min_level: str = "DEBUG",
                 title: str = "Debug Console", name_filter: str = ""):
        super().__init__(master)
        self.title(title)
        self.configure(bg=_HEADER_BG)
        self.geometry("860x340")
        self.minsize(480, 200)

        self._q           = queue.Queue(maxsize=2000)
        self._handler     = _QueueHandler(self._q)
        self._handler.setLevel(_LEVEL_NUM.get(min_level, logging.DEBUG))
        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
            datefmt="%H:%M:%S",
        )
        self._handler.setFormatter(fmt)
        logging.getLogger().addHandler(self._handler)

        self._auto_scroll = True
        self._level_var   = tk.StringVar(value=min_level)
        self._filter_var  = tk.StringVar(value=name_filter)
        self._filter_name = name_filter

        self._build()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self):
        # ── Header bar ───────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_HEADER_BG, pady=4)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="Debug Console",
            bg=_HEADER_BG, fg="#58a6ff",
            font=("Consolas", 10, "bold"),
        ).pack(side="left", padx=(10, 16))

        # Level filter
        tk.Label(hdr, text="Level:", bg=_HEADER_BG, fg="#8b949e",
                 font=("Consolas", 9)).pack(side="left")
        for lvl in _LEVELS:
            color = _LEVEL_FG.get(_LEVEL_NUM[lvl], "#c9d1d9")
            tk.Radiobutton(
                hdr, text=lvl,
                variable=self._level_var, value=lvl,
                bg=_HEADER_BG, fg=color,
                selectcolor="#1f2937",
                activebackground=_HEADER_BG, activeforeground=color,
                font=("Consolas", 9),
                command=self._on_level_change,
            ).pack(side="left", padx=(6, 0))

        # Logger name filter
        tk.Label(hdr, text="  Filter:", bg=_HEADER_BG, fg="#8b949e",
                 font=("Consolas", 9)).pack(side="left", padx=(12, 2))
        self._filter_var.trace_add("write", lambda *_: self._on_filter_change())
        tk.Entry(
            hdr, textvariable=self._filter_var, width=14,
            bg="#1c2128", fg="#c9d1d9", insertbackground="#c9d1d9",
            relief="flat", font=("Consolas", 9),
            bd=1, highlightthickness=1,
            highlightbackground=_BORDER, highlightcolor="#58a6ff",
        ).pack(side="left", padx=(0, 8))

        # Scroll lock indicator / toggle
        self._scroll_var = tk.StringVar(value="↓ Auto")
        self._scroll_btn = tk.Button(
            hdr, textvariable=self._scroll_var, width=8,
            bg="#1c2128", fg="#58a6ff",
            activebackground="#1c2128", activeforeground="#58a6ff",
            relief="flat", font=("Consolas", 8),
            cursor="hand2", command=self._toggle_scroll,
        )
        self._scroll_btn.pack(side="left", padx=(0, 4))

        tk.Button(
            hdr, text="Clear",
            bg="#6e1a1a", fg="#f85149",
            activebackground="#7a1e1e", activeforeground="#f85149",
            relief="flat", font=("Consolas", 9),
            cursor="hand2", padx=8, pady=1,
            command=self._clear,
        ).pack(side="right", padx=(4, 10))

        # ── Divider ──────────────────────────────────────────────────
        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")

        # ── Text + scrollbars ─────────────────────────────────────────
        container = tk.Frame(self, bg=_BG)
        container.pack(fill="both", expand=True)

        self._text = tk.Text(
            container,
            bg=_BG, fg="#c9d1d9",
            font=("Consolas", 9),
            state="disabled",
            wrap="none",
            bd=0, highlightthickness=0,
            insertbackground="#c9d1d9",
            selectbackground="#264f78",
        )

        # Store scrollbar as instance var so _on_yscroll can reference it
        self._scrolly = tk.Scrollbar(container, orient="vertical",
                                     command=self._text.yview)
        scrollx       = tk.Scrollbar(self, orient="horizontal",
                                     command=self._text.xview)

        # yscrollcommand: Tkinter calls this with *args = (first, last)
        # Use *args to be safe across Tk versions
        self._text.configure(
            yscrollcommand=self._on_yscroll,
            xscrollcommand=scrollx.set,
        )

        self._scrolly.pack(side="right", fill="y")
        scrollx.pack(side="bottom", fill="x")
        self._text.pack(fill="both", expand=True)

        # Level color tags
        self._text.tag_config("DEBUG",    foreground=_LEVEL_FG[logging.DEBUG])
        self._text.tag_config("INFO",     foreground=_LEVEL_FG[logging.INFO])
        self._text.tag_config("WARNING",  foreground=_LEVEL_FG[logging.WARNING])
        self._text.tag_config("ERROR",    foreground=_LEVEL_FG[logging.ERROR])
        self._text.tag_config("CRITICAL", foreground=_LEVEL_FG[logging.CRITICAL],
                              font=("Consolas", 9, "bold"))

        self._text.bind("<MouseWheel>", self._on_mousewheel)
        self._text.bind("<Button-4>",   self._on_mousewheel)
        self._text.bind("<Button-5>",   self._on_mousewheel)

    # ------------------------------------------------------------------
    # Queue poll
    # ------------------------------------------------------------------

    def _poll(self):
        try:
            while True:
                record = self._q.get_nowait()
                self._append(record)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(self.POLL_MS, self._poll)

    def _append(self, record: logging.LogRecord):
        if self._filter_name and self._filter_name not in record.name:
            return
        tag = record.levelname if record.levelname in (
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO"
        msg = self._handler.format(record) + "\n"

        self._text.configure(state="normal")
        self._text.insert("end", msg, tag)

        total = int(self._text.index("end-1c").split(".")[0])
        if total > self.MAX_LINES:
            self._text.delete("1.0", f"{total - self.MAX_LINES}.0")

        self._text.configure(state="disabled")
        if self._auto_scroll:
            self._text.see("end")

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------

    def _on_yscroll(self, *args):
        """yscrollcommand callback — Tk passes (first, last) as strings."""
        # Forward to scrollbar (standard Tk pattern)
        self._scrolly.set(*args)
        # Detect if at bottom to control auto-scroll
        try:
            last = float(args[-1])
        except (IndexError, ValueError):
            return
        at_bottom = last >= 0.999
        if at_bottom and not self._auto_scroll:
            self._auto_scroll = True
            self._scroll_var.set("↓ Auto")
            self._scroll_btn.config(fg="#58a6ff")
        elif not at_bottom and self._auto_scroll:
            self._auto_scroll = False
            self._scroll_var.set("⏸ Paused")
            self._scroll_btn.config(fg="#e3b341")

    def _on_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        btn   = getattr(event, "num", 0)
        going_up = (delta > 0) or (btn == 4)
        if going_up and self._auto_scroll:
            self._auto_scroll = False
            self._scroll_var.set("⏸ Paused")
            self._scroll_btn.config(fg="#e3b341")

    def _toggle_scroll(self):
        self._auto_scroll = not self._auto_scroll
        if self._auto_scroll:
            self._scroll_var.set("↓ Auto")
            self._scroll_btn.config(fg="#58a6ff")
            self._text.see("end")
        else:
            self._scroll_var.set("⏸ Paused")
            self._scroll_btn.config(fg="#e3b341")

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def _on_level_change(self):
        level = _LEVEL_NUM.get(self._level_var.get(), logging.DEBUG)
        self._handler.setLevel(level)

    def _on_filter_change(self):
        self._filter_name = self._filter_var.get().strip()

    def _on_close(self):
        logging.getLogger().removeHandler(self._handler)
        self.destroy()
