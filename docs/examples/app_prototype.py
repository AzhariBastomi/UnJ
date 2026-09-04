"""
RecycleView Tkinter — OOP Task Manager
Ukuran layar: fixed 360x640 (simulasi 5 inch)
Tidak ada library eksternal — semua built-in Python
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import random
import math

# ══════════════════════════════════════════════════════════════════
#  PALETTE
# ══════════════════════════════════════════════════════════════════
C = {
    "bg":        "#0F0F1A",
    "surface":   "#1A1A2E",
    "card":      "#22223A",
    "card_hov":  "#2C2C44",
    "border":    "#33334A",
    "accent":    "#7B68EE",
    "text":      "#E8E8F0",
    "sub":       "#8888AA",
    "ok":        "#3DD68C",
    "warn":      "#FFB347",
    "err":       "#FF6B6B",
    "bar_bg":    "#2E2E44",
}

# ══════════════════════════════════════════════════════════════════
#  BASE TASK — Abstract base class
# ══════════════════════════════════════════════════════════════════
class BaseTask:
    """
    Abstract base untuk semua jenis task.
    Setiap subclass wajib override:
      - NAME  : str
      - ICON  : str (emoji)
      - COLOR : str (hex)
      - _step_duration()  -> float  (detik per tick)
      - _increment()      -> int    (besar kenaikan per tick)
      - detail_info()     -> str    (teks popup detail)
    """
    NAME  = "Base Task"
    ICON  = "X"
    COLOR = "#7B68EE"

    def __init__(self, label=""):
        self.label    = label or self.NAME
        self.progress = 0
        self.running  = False
        self._stop    = False

    def _step_duration(self):
        return 0.1

    def _increment(self):
        return random.randint(2, 6)

    def detail_info(self):
        return (
            f"{self.ICON}  {self.label}\n"
            f"---------------------\n"
            f"Tipe     : {self.NAME}\n"
            f"Progress : {self.progress}%\n"
            f"Status   : {self._status_text()}"
        )

    def _status_text(self):
        if self.progress >= 100: return "Selesai"
        if self.running:         return "Berjalan"
        if self.progress > 0:    return "Dijeda"
        return "Belum mulai"

    def reset(self):
        self._stop    = True
        self.running  = False
        self.progress = 0

    def run(self, on_tick, on_done):
        if self.running or self.progress >= 100:
            return
        self._stop   = False
        self.running = True

        def _worker():
            while not self._stop and self.progress < 100:
                inc = self._increment()
                self.progress = min(self.progress + inc, 100)
                on_tick(self.progress)
                time.sleep(self._step_duration())
            self.running = False
            if self.progress >= 100:
                on_done()

        threading.Thread(target=_worker, daemon=True).start()


# ══════════════════════════════════════════════════════════════════
#  TASK 1 — DownloadTask
# ══════════════════════════════════════════════════════════════════
class DownloadTask(BaseTask):
    """
    Simulasi unduhan file.
    Cepat di awal, melambat saat hampir selesai (network throttle).
    """
    NAME  = "Download File"
    ICON  = "D"
    COLOR = "#3B9EFF"

    def __init__(self, filename=""):
        super().__init__(label=f"Download: {filename or 'data.zip'}")
        self.filename  = filename or "data.zip"
        self.file_size = random.randint(50, 500)   # MB
        self.speed     = round(random.uniform(5.0, 20.0), 1)

    def _step_duration(self):
        return 0.08 if self.progress <= 80 else 0.16   # throttle di akhir

    def _increment(self):
        if self.progress < 60:   return random.randint(4, 9)
        elif self.progress < 85: return random.randint(2, 5)
        else:                    return random.randint(1, 3)

    def detail_info(self):
        dl = int(self.file_size * self.progress / 100)
        return (
            f"[{self.ICON}] {self.label}\n"
            f"---------------------\n"
            f"Tipe      : {self.NAME}\n"
            f"File      : {self.filename}\n"
            f"Ukuran    : {self.file_size} MB\n"
            f"Terunduh  : {dl} / {self.file_size} MB\n"
            f"Kecepatan : {self.speed} Mbps\n"
            f"Progress  : {self.progress}%\n"
            f"Status    : {self._status_text()}"
        )


# ══════════════════════════════════════════════════════════════════
#  TASK 2 — AITrainingTask
# ══════════════════════════════════════════════════════════════════
class AITrainingTask(BaseTask):
    """
    Simulasi training model AI.
    Lambat, tidak stabil (kadang loss plateau).
    """
    NAME  = "AI Training"
    ICON  = "AI"
    COLOR = "#E040FB"

    def __init__(self, model_name=""):
        super().__init__(label=f"Training: {model_name or 'ResNet-50'}")
        self.model_name = model_name or "ResNet-50"
        self.epochs     = random.randint(3, 10)
        self.batch_size = random.choice([16, 32, 64])
        self.loss       = round(random.uniform(1.5, 3.0), 4)

    def _step_duration(self):
        return random.uniform(0.15, 0.28)

    def _increment(self):
        roll = random.random()
        if roll < 0.1:   return 0                    # plateau
        elif roll < 0.3: return random.randint(1, 2)
        else:            return random.randint(2, 5)

    def detail_info(self):
        epoch_now = max(1, math.ceil(self.progress * self.epochs / 100))
        self.loss = max(0.01, self.loss - random.uniform(0.005, 0.03))
        return (
            f"[{self.ICON}] {self.label}\n"
            f"---------------------\n"
            f"Tipe      : {self.NAME}\n"
            f"Model     : {self.model_name}\n"
            f"Epoch     : {epoch_now} / {self.epochs}\n"
            f"Batch Size: {self.batch_size}\n"
            f"Loss      : {self.loss:.4f}\n"
            f"Progress  : {self.progress}%\n"
            f"Status    : {self._status_text()}"
        )


# ══════════════════════════════════════════════════════════════════
#  TASK 3 — BackupTask
# ══════════════════════════════════════════════════════════════════
class BackupTask(BaseTask):
    """
    Simulasi backup data ke cloud.
    Stabil dan konsisten (tidak ada fluctuasi besar).
    """
    NAME  = "Cloud Backup"
    ICON  = "BK"
    COLOR = "#3DD68C"

    def __init__(self, folder=""):
        super().__init__(label=f"Backup: {folder or '/home/user'}")
        self.folder      = folder or "/home/user"
        self.total_files = random.randint(200, 2000)
        self.total_size  = random.randint(1, 50)

    def _step_duration(self):
        return 0.07

    def _increment(self):
        return random.randint(3, 7)

    def detail_info(self):
        backed = int(self.total_files * self.progress / 100)
        return (
            f"[{self.ICON}] {self.label}\n"
            f"---------------------\n"
            f"Tipe       : {self.NAME}\n"
            f"Folder     : {self.folder}\n"
            f"Total File : {self.total_files:,}\n"
            f"Terbackup  : {backed:,} file\n"
            f"Ukuran     : {self.total_size} GB\n"
            f"Progress   : {self.progress}%\n"
            f"Status     : {self._status_text()}"
        )


# ══════════════════════════════════════════════════════════════════
#  REGISTRY
# ══════════════════════════════════════════════════════════════════
TASK_REGISTRY = [DownloadTask, AITrainingTask, BackupTask]

TASK_DEFAULTS = {
    DownloadTask:   ["model_weights.pt", "dataset.zip", "checkpoint.bin", "pretrained.h5"],
    AITrainingTask: ["ResNet-50", "BERT-base", "YOLOv8", "GPT-2-small"],
    BackupTask:     ["/home/user/docs", "/var/www", "/etc/config", "/home/user/projects"],
}

TASK_DESC = {
    DownloadTask:   "Unduh file dari server / internet",
    AITrainingTask: "Latih model machine learning",
    BackupTask:     "Backup data ke penyimpanan cloud",
}


# ══════════════════════════════════════════════════════════════════
#  DIALOG — Pilih Task
# ══════════════════════════════════════════════════════════════════
class TaskPickerDialog(tk.Toplevel):
    """Modal dialog untuk memilih jenis task."""

    def __init__(self, parent):
        super().__init__(parent)
        self.result = None

        W, H = 320, 340
        px = parent.winfo_rootx() + (parent.winfo_width()  - W) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - H) // 2
        self.geometry(f"{W}x{H}+{px}+{py}")
        self.resizable(False, False)
        self.configure(bg=C["surface"])
        self.title("Pilih Task")
        self.grab_set()
        self._build()

    def _build(self):
        # Header
        tk.Label(self, text="Tambah Task Baru",
                 bg=C["surface"], fg=C["text"],
                 font=("Segoe UI", 12, "bold"), pady=12).pack(fill="x")

        tk.Label(self, text="Pilih jenis task:",
                 bg=C["surface"], fg=C["sub"],
                 font=("Segoe UI", 9)).pack()

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=16, pady=8)

        # Task cards
        for cls in TASK_REGISTRY:
            self._card(cls)

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(8, 6))

        # Batal
        btn = tk.Label(self, text="Batal",
                       bg=C["card"], fg=C["sub"],
                       font=("Segoe UI", 9), pady=7, cursor="hand2")
        btn.pack(fill="x", padx=16)
        btn.bind("<Button-1>", lambda e: self.destroy())

    def _card(self, cls):
        color = cls.COLOR

        card = tk.Frame(self, bg=C["card"], cursor="hand2")
        card.pack(fill="x", padx=16, pady=3)

        # Badge ikon
        badge = tk.Label(card, text=cls.ICON,
                         bg=color, fg="white",
                         font=("Segoe UI", 9, "bold"),
                         width=4, pady=10)
        badge.pack(side="left")

        # Teks
        info = tk.Frame(card, bg=C["card"])
        info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        tk.Label(info, text=cls.NAME,
                 bg=C["card"], fg=C["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")

        tk.Label(info, text=TASK_DESC.get(cls, ""),
                 bg=C["card"], fg=C["sub"],
                 font=("Segoe UI", 8), anchor="w").pack(fill="x")

        tk.Label(card, text=">",
                 bg=C["card"], fg=C["sub"],
                 font=("Segoe UI", 14), padx=10).pack(side="right")

        # Hover + klik
        def _hover(on, f=card):
            bg = C["card_hov"] if on else C["card"]
            f.config(bg=bg)
            for w in f.winfo_children():
                try:
                    if w.cget("cursor") != "hand2":
                        w.config(bg=bg)
                except Exception:
                    pass
                for w2 in w.winfo_children():
                    try: w2.config(bg=bg)
                    except Exception: pass

        def _pick(c=cls):
            param = random.choice(TASK_DEFAULTS[c])
            self.result = c(param)
            self.destroy()

        for w in [card, badge, info] + list(info.winfo_children()):
            w.bind("<Button-1>", lambda e, fn=_pick: fn())
            w.bind("<Enter>",   lambda e, on=True:  _hover(on))
            w.bind("<Leave>",   lambda e, on=False: _hover(on))


# ══════════════════════════════════════════════════════════════════
#  RecycleView ITEM
# ══════════════════════════════════════════════════════════════════
class RecycleViewItem(tk.Frame):
    """Satu baris item: ikon + judul + % + progress bar + tombol."""

    def __init__(self, parent, task, app_ref, **kwargs):
        super().__init__(parent, bg=C["card"], **kwargs)
        self.task    = task
        self.app_ref = app_ref
        self._build()

    def _build(self):
        self.config(padx=12, pady=10)

        # Baris 1: ikon + judul + persen
        r1 = tk.Frame(self, bg=C["card"])
        r1.pack(fill="x")

        tk.Label(r1, text=f"[{self.task.ICON}]",
                 bg=self.task.COLOR, fg="white",
                 font=("Segoe UI", 8, "bold"),
                 padx=5, pady=2).pack(side="left")

        self.lbl_title = tk.Label(r1, text=self.task.label,
                                  bg=C["card"], fg=C["text"],
                                  font=("Segoe UI", 9, "bold"), anchor="w")
        self.lbl_title.pack(side="left", fill="x", expand=True, padx=(7, 0))

        self.lbl_pct = tk.Label(r1, text="0%",
                                bg=C["card"], fg=C["err"],
                                font=("Segoe UI", 9, "bold"), width=4)
        self.lbl_pct.pack(side="right")

        # Progress bar
        self.cv = tk.Canvas(self, height=6, bg=C["card"],
                            highlightthickness=0, bd=0)
        self.cv.pack(fill="x", pady=(5, 7))
        self.cv.bind("<Configure>", self._draw)

        # Baris 2: tombol
        r2 = tk.Frame(self, bg=C["card"])
        r2.pack(fill="x")

        self.btn_start = self._btn(r2, "Start",  self.task.COLOR, self._do_start)
        self.btn_start.pack(side="left")
        self._btn(r2, "Reset", C["warn"], self._do_reset).pack(side="left", padx=(5, 0))
        self._btn(r2, "Info",  C["sub"],  self._do_info ).pack(side="right")

    def _btn(self, parent, text, color, cmd):
        b = tk.Label(parent, text=text, bg=color, fg="white",
                     font=("Segoe UI", 8, "bold"),
                     padx=10, pady=4, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e: b.config(bg=_lighten(color)))
        b.bind("<Leave>",    lambda e: b.config(bg=color))
        return b

    def _draw(self, _=None):
        self.cv.delete("all")
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        r = h // 2
        _pill(self.cv, 0, 0, w, h, r, C["bar_bg"])
        fw = max(int(w * self.task.progress / 100), 0)
        if fw:
            _pill(self.cv, 0, 0, fw, h, r, _pcolor(self.task.progress))

    def _do_start(self):
        self.task.run(
            on_tick=lambda v: self.app_ref.after(0, self._tick, v),
            on_done=lambda:   self.app_ref.after(0, self._done),
        )
        self.app_ref.refresh_status()

    def _do_reset(self):
        self.task.reset()
        self._tick(0)

    def _do_info(self):
        messagebox.showinfo("Detail Task", self.task.detail_info())

    def _tick(self, v):
        self.task.progress = v
        self.lbl_pct.config(text=f"{v}%", fg=_pcolor(v))
        self._draw()
        self.app_ref.refresh_status()

    def _done(self):
        self.lbl_pct.config(text="100%", fg=C["ok"])
        self._draw()
        self.app_ref.refresh_status()


# ══════════════════════════════════════════════════════════════════
#  RECYCLE VIEW
# ══════════════════════════════════════════════════════════════════
class RecycleView(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=C["bg"], **kwargs)
        self._items = []
        self._build_ui() # 1. UBAH NAMA PEMANGGILAN FUNGSI DI SINI

    # 2. UBAH NAMA FUNGSI DI SINI AGAR TIDAK BENTROK DENGAN TKINTER
    def _build_ui(self): 
        sb = ttk.Scrollbar(self, orient="vertical")
        sb.pack(side="right", fill="y")

        self.cv = tk.Canvas(self, bg=C["bg"], highlightthickness=0,
                            yscrollcommand=sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self.cv.yview)

        self.inner = tk.Frame(self.cv, bg=C["bg"])
        self._wid  = self.cv.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>",
            lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>",
            lambda e: self.cv.itemconfig(self._wid, width=e.width))

        self.cv.bind_all("<MouseWheel>", self._scroll)
        self.cv.bind_all("<Button-4>",   self._scroll)
        self.cv.bind_all("<Button-5>",   self._scroll)

    def _scroll(self, e):
        if   e.num == 4: self.cv.yview_scroll(-1, "units")
        elif e.num == 5: self.cv.yview_scroll( 1, "units")
        else:            self.cv.yview_scroll(int(-e.delta / 120), "units")

    def add(self, w):
        self._items.append(w)
        w.pack(in_=self.inner, fill="x", padx=10, pady=(0, 6))

    def items(self):
        return self._items

    def clear(self):
        for w in self._items: w.destroy()
        self._items.clear()
        

# ══════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Task Manager")
        self.attributes("-fullscreen", True)
        self.resizable(False,False)
        self.configure(bg=C["bg"])

        self.W = self.winfo_screenmmwidth()
        self.H = self.winfo_screenmmheight()

        self._build()
        self._load_defaults()

   
    def _build(self):
        self._header()
        self._toolbar()
        self.rv = RecycleView(self)
        self.rv.pack(fill="both", expand=True)
        self._statusbar()

    def _header(self):
        hdr = tk.Frame(self, bg=C["surface"], pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Task Manager",
                 bg=C["surface"], fg=C["text"],
                 font=("Segoe UI", 15, "bold")).pack()
        tk.Label(hdr, text="RecycleView  Tkinter OOP",
                 bg=C["surface"], fg=C["sub"],
                 font=("Segoe UI", 8)).pack()

    def _toolbar(self):
        bar = tk.Frame(self, bg=C["bg"], pady=8)
        bar.pack(fill="x", padx=10)
        self._tbtn(bar, "+ Tambah Task", C["accent"],  self._open_picker).pack(side="left")
        self._tbtn(bar, "Jalankan Semua","#3B9EFF",    self._start_all  ).pack(side="left", padx=(6,0))
        self._tbtn(bar, "Hapus Semua",   C["err"],     self._clear_all  ).pack(side="right")

    def _tbtn(self, parent, text, color, cmd):
        b = tk.Label(parent, text=text, bg=color, fg="white",
                     font=("Segoe UI", 8, "bold"),
                     padx=10, pady=6, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e: b.config(bg=_lighten(color)))
        b.bind("<Leave>",    lambda e: b.config(bg=color))
        return b

    def _statusbar(self):
        self._sv = tk.StringVar(value="Siap.")
        bar = tk.Frame(self, bg="#0A0A14", pady=3)
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, textvariable=self._sv,
                 bg="#0A0A14", fg=C["sub"],
                 font=("Segoe UI", 7), padx=10).pack(side="left")

    def _load_defaults(self):
        defaults = [
            DownloadTask("model_weights.pt"),
            AITrainingTask("ResNet-50"),
            BackupTask("/home/user/docs"),
            DownloadTask("dataset_v2.zip"),
            AITrainingTask("BERT-base"),
        ]
        for t in defaults:
            t.progress = random.randint(0, 55)
            self._add_task(t)
        self.refresh_status()

    def _add_task(self, task):
        w = RecycleViewItem(self.rv.inner, task, app_ref=self)
        self.rv.add(w)
        w._tick(task.progress)

    def _open_picker(self):
        dlg = TaskPickerDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._add_task(dlg.result)
            self.refresh_status()

    def _start_all(self):
        for w in self.rv.items():
            if w.task.progress < 100:
                w._do_start()

    def _clear_all(self):
        if messagebox.askyesno("Konfirmasi", "Hapus semua task?"):
            self.rv.clear()
            self.refresh_status()

    def refresh_status(self):
        items = self.rv.items()
        total = len(items)
        done  = sum(1 for i in items if i.task.progress >= 100)
        run   = sum(1 for i in items if i.task.running)
        self._sv.set(
            f"Total: {total}  |  Selesai: {done}  |  Berjalan: {run}  |  Antri: {total-done-run}"
        )


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def _pill(cv, x1, y1, x2, y2, r, fill):
    cv.create_arc(x1,    y1, x1+2*r, y2, start=90,  extent=180, fill=fill, outline="")
    cv.create_arc(x2-2*r, y1, x2,   y2, start=270, extent=180, fill=fill, outline="")
    cv.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")

def _pcolor(p):
    if p < 30:   return C["err"]
    elif p < 70: return C["warn"]
    else:        return C["ok"]

def _lighten(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(min(r+35,255), min(g+35,255), min(b+35,255))


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()