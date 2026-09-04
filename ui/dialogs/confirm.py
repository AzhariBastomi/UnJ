"""
ui/dialogs/confirm.py — ConfirmDialog / AlertDialog ramah layar sentuh.

MASALAH
-------
``tkinter.messagebox`` memakai dialog bawaan Tk yang TIDAK melewati
``TouchPopupMixin``: tidak ada wait_visibility + lift + focus_force +
grab_set. Di layar sentuh, window manager memakai tap PERTAMA pada sebuah
window baru untuk keperluan focus/raise, sehingga event itu tidak pernah
sampai ke tombol di dalamnya — tombol OK/Yes baru bekerja pada tap kedua.

``ui/touch_click.py`` hanya menutup separuh masalah (crossing event <Enter>
yang dibutuhkan tombol Tk sebelum bisa di-invoke). Tap yang ditelan window
manager memang tidak pernah masuk ke Tk, jadi tidak bisa ditolong dari sana.

Modul ini menyediakan pengganti messagebox yang memakai TouchPopupMixin,
sehingga perilaku aktivasinya sama persis dengan dialog lain di aplikasi.

Cara pakai::

    from ui.dialogs import ask_yes_no, show_warning

    if ask_yes_no(self, "Clear All", "Hapus semua test dari list?"):
        ...
"""

import logging
import tkinter as tk

from config import COLORS
from ui.popup_util import TouchPopupMixin

log = logging.getLogger("main")

# Lebar teks (dalam karakter) sebelum dibungkus ke baris berikutnya.
_WRAP_CHARS = 46


def _metrics(widget):
    """Ukuran kontrol menyesuaikan tinggi layar, sama seperti dialog lain."""
    sh = widget.winfo_screenheight()
    if sh < 400:
        return 10, 6, 260
    if sh < 560:
        return 11, 10, 320
    return 12, 14, 380


class _BaseMessageDialog(TouchPopupMixin, tk.Toplevel):
    """Dialog pesan modal. Hasilnya dibaca lewat atribut ``result``."""

    # Diisi subclass: daftar (teks, nilai_result, gaya) untuk tombol.
    _BUTTONS: tuple = ()
    # Nilai result bila dialog ditutup lewat Escape / tombol close window.
    _DISMISS_RESULT = None

    def __init__(self, parent, title: str, message: str, accent: str = "running"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.configure(bg=COLORS["surface"])

        self.result = self._DISMISS_RESULT
        self._fs, self._pad_y, self._wrap_px = _metrics(self)

        self._build(title, message, accent)
        self.place_over_parent(parent)

        # close_on_outside sengaja mati: tap di luar tidak boleh diartikan
        # sebagai jawaban. Dialog selalu punya tombol batal dan <Escape>.
        self.init_popup_behavior(close_on_outside=False)
        self.bind("<Escape>", lambda e: self._answer(self._DISMISS_RESULT))
        self.protocol("WM_DELETE_WINDOW",
                      lambda: self._answer(self._DISMISS_RESULT))

    # ------------------------------------------------------------------

    def _build(self, title: str, message: str, accent: str):
        C = COLORS

        tk.Label(self, text=title,
                 font=("TkDefaultFont", self._fs, "bold"),
                 bg=C["surface"], fg=C.get(accent, C["text"]),
                 anchor="w", justify="left").pack(
            fill="x", padx=16, pady=(14, 4))

        tk.Label(self, text=message,
                 font=("TkDefaultFont", self._fs),
                 bg=C["surface"], fg=C["text"],
                 anchor="w", justify="left",
                 wraplength=self._wrap_px).pack(
            fill="x", padx=16, pady=(0, 12))

        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=16)

        btn_frame = tk.Frame(self, bg=C["surface"])
        btn_frame.pack(pady=(10, 14))

        for text, value, style in self._BUTTONS:
            primary = (style == "primary")
            tk.Button(
                btn_frame, text=text, width=9,
                command=lambda v=value: self._answer(v),
                bg=C.get(accent, C["running"]) if primary else C["card"],
                fg="white" if primary else C["sub"],
                activebackground=C.get(accent, C["running"]) if primary
                else C["card_hov"],
                activeforeground="white" if primary else C["text"],
                relief="flat", bd=0,
                font=("TkDefaultFont", self._fs,
                      "bold" if primary else "normal"),
                padx=10, pady=max(6, self._pad_y - 2),
                cursor="hand2",
            ).pack(side="left", padx=8)

    def _answer(self, value):
        self.result = value
        try:
            self.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------

    @classmethod
    def ask(cls, parent, title: str, message: str, accent: str = "running"):
        """Tampilkan dialog, tunggu sampai ditutup, kembalikan ``result``."""
        dlg = cls(parent, title, message, accent)
        try:
            parent.wait_window(dlg)
        except Exception:                      # parent keburu hilang
            log.debug("confirm: wait_window gagal untuk %s", title)
        return dlg.result


class ConfirmDialog(_BaseMessageDialog):
    """Pertanyaan Ya/Tidak. ``result`` bernilai True/False."""

    _BUTTONS = (
        ("Ya",    True,  "primary"),
        ("Tidak", False, "secondary"),
    )
    _DISMISS_RESULT = False


class AlertDialog(_BaseMessageDialog):
    """Pemberitahuan satu tombol. ``result`` selalu None."""

    _BUTTONS = (
        ("OK", None, "primary"),
    )
    _DISMISS_RESULT = None


# ══════════════════════════════════════════════════════════════════════════════
# Helper — pengganti langsung tkinter.messagebox
# ══════════════════════════════════════════════════════════════════════════════

def ask_yes_no(parent, title: str, message: str) -> bool:
    """Pengganti ``messagebox.askyesno``."""
    return bool(ConfirmDialog.ask(parent, title, message, accent="warn"))


def show_info(parent, title: str, message: str) -> None:
    """Pengganti ``messagebox.showinfo``."""
    AlertDialog.ask(parent, title, message, accent="running")


def show_warning(parent, title: str, message: str) -> None:
    """Pengganti ``messagebox.showwarning``."""
    AlertDialog.ask(parent, title, message, accent="warn")


def show_error(parent, title: str, message: str) -> None:
    """Pengganti ``messagebox.showerror``."""
    AlertDialog.ask(parent, title, message, accent="ng")
