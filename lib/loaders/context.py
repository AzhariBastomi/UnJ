"""
loaders/context.py — Shared context untuk test params.

Context diisi oleh app (device_id, field UI, dll.) sebelum test dijalankan.
Test commands membacanya via get_context() saat run time.
Thread-safe; UI watcher dipanggil di main thread saat nilai berubah.
"""

import threading

context: dict = {}
_context_lock = threading.Lock()

_tk_root = None
_ui_watchers: dict = {}  # key → list[callable]


def set_tk_root(root) -> None:
    """Simpan referensi ke root Tk window (dipanggil sekali dari main.py)."""
    global _tk_root
    _tk_root = root


def watch_context(key: str, fn) -> None:
    """Register callback yang dipanggil di main thread saat context[key] berubah."""
    _ui_watchers.setdefault(key, []).append(fn)


def get_context(key: str, default: str = "") -> str:
    """Thread-safe getter untuk context."""
    with _context_lock:
        return context.get(key, default)


def show_countdown_popup(message: str, seconds: int = 5,
                         message2: str = "", phase2_pct: int = 90) -> None:
    """Tampilkan popup countdown dari thread manapun (schedule ke main thread).

    Fase 1 (0% – phase2_pct%): tampilkan `message`
    Fase 2 (phase2_pct% – 100%): tampilkan `message2` (jika diset)
    Popup tutup sendiri setelah `seconds` detik.
    """
    if _tk_root is None:
        return
    try:
        _tk_root.after(0, lambda: _show_countdown_popup_main(
            _tk_root, message, seconds, message2, phase2_pct))
    except Exception:
        pass


def _show_countdown_popup_main(root, message: str, seconds: int,
                                message2: str = "", phase2_pct: int = 90) -> None:
    """Dijalankan di main thread oleh show_countdown_popup."""
    try:
        import tkinter as tk
    except ImportError:
        return

    # Detik saat beralih ke fase 2 (hitung dari akhir)
    # phase2_pct=90 → switch saat sisa = 10% * seconds
    phase2_at = max(1, round(seconds * (100 - phase2_pct) / 100))

    win = tk.Toplevel(root)
    win.title("")
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()
    win.configure(bg="#1e1e2e")

    lbl_msg = tk.Label(win, text=message,
                       bg="#1e1e2e", fg="#cdd6f4",
                       font=("TkDefaultFont", 12, "bold"),
                       wraplength=280, justify="center")
    lbl_msg.pack(padx=28, pady=(20, 8))

    lbl_sec = tk.Label(win, text=f"{seconds}",
                       bg="#1e1e2e", fg="#89b4fa",
                       font=("TkDefaultFont", 28, "bold"))
    lbl_sec.pack(padx=28, pady=(0, 4))

    lbl_sub = tk.Label(win, text="detik",
                       bg="#1e1e2e", fg="#6c7086",
                       font=("TkDefaultFont", 9))
    lbl_sub.pack(padx=28, pady=(0, 20))

    # Tengah layar
    win.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    ww, wh = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")

    # Popup ini juga memasang grab lokal, jadi butuh perlakuan yang sama
    # dengan dialog lain: pointer dipindahkan ke dalamnya supaya sentuhan
    # pertama tidak dibuang Tk. Lihat ui/pointer_util.py.
    try:
        from ui.pointer_util import install_pointer_probe, prime_pointer_repeatedly
        install_pointer_probe(win)
        prime_pointer_repeatedly(win)
    except Exception:
        pass

    _remaining = [seconds]

    def _tick():
        _remaining[0] -= 1
        if _remaining[0] <= 0:
            try:
                win.destroy()
            except Exception:
                pass
            return
        try:
            lbl_sec.config(text=str(_remaining[0]))
            # Switch ke pesan fase 2 saat sisa waktu = phase2_at
            if message2 and _remaining[0] <= phase2_at:
                lbl_msg.config(text=message2, fg="#a6e3a1")
                lbl_sec.config(fg="#a6e3a1")
            win.after(1000, _tick)
        except Exception:
            pass

    win.after(1000, _tick)


def update_context(data: dict) -> None:
    """Thread-safe update untuk context. Notifikasi UI watcher jika nilai berubah."""
    changed = {}
    with _context_lock:
        for k, v in data.items():
            if context.get(k) != v:
                context[k] = v
                changed[k] = v
    if _tk_root and changed:
        for key, value in changed.items():
            for fn in _ui_watchers.get(key, []):
                try:
                    _tk_root.after(0, lambda f=fn, v=value: f(v))
                except Exception:
                    pass
