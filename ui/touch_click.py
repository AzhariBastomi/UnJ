"""
ui/touch_click.py — Membuat tombol Tk/ttk bisa ditekan sekali tap di layar sentuh.

MASALAH
-------
Tombol Tk tidak dijalankan saat ditekan, melainkan saat DILEPAS — dan hanya
kalau Tk yakin pointer "sedang berada di atas" tombol itu. Keyakinan tersebut
datang dari event <Enter> (crossing), bukan dari koordinat klik:

    tk::ButtonDown  (<Button-1>)        -> Priv(buttonWindow) = tombol
    tk::ButtonEnter (<Enter>)           -> Priv(window)       = tombol
    tk::ButtonUp    (<ButtonRelease-1>) -> invoke HANYA bila kedua-duanya sama

ttk (TButton, dipakai messagebox di Linux) memakai pola yang sama lewat state
``pressed`` + ``active``; ``active`` juga hanya diset oleh <Enter>.

Di layar sentuh, jari "meloncat": tidak ada gerakan pointer yang melewati
tombol, dan popup sering muncul persis di bawah/di dekat jari. Banyak driver
touch (evdev/libinput di X11, apalagi saat ada grab aktif) mengirim ButtonPress
tanpa crossing event yang mendahuluinya, sehingga Priv(window) masih menunjuk
window lama → tap pertama TIDAK menjalankan command apa pun.

Begitu jari digeser sedikit, barulah muncul <Motion>/<Enter>, Priv(window)
terisi, dan tap berikutnya bekerja. Itulah kenapa "harus digeser dulu baru bisa
memilih" — dan kenapa gejalanya juga muncul di messagebox bawaan Tk
(Clear All), yang sama sekali tidak memakai kode popup kita.

SOLUSI
------
Pasang class binding tambahan: begitu sebuah tombol menerima <Button-1> dan
koordinat pressnya memang berada di dalam tombol itu, kirim <Enter> buatan ke
tombol tersebut. Priv(window)/state ``active`` jadi terisi sebelum jari
dilepas, sehingga tap tunggal langsung menjalankan command.

Aman untuk mouse: kalau pointer memang sudah di atas tombol, <Enter> tambahan
tidak mengubah apa pun. Kalau press ternyata jatuh di luar geometri tombol
(event nyasar), kita tidak melakukan apa-apa — tombol tidak akan ter-invoke
diam-diam.

Cukup dipanggil SEKALI pada root window; class binding berlaku untuk semua
window di interpreter yang sama, termasuk messagebox dan filedialog bawaan Tk.

    from ui.touch_click import enable_touch_click
    enable_touch_click(root)
"""

import logging
import tkinter as tk

log = logging.getLogger("main")

# Kelas widget yang aktivasinya bergantung pada crossing event.
_CLASSES = (
    "Button", "TButton",
    "Checkbutton", "TCheckbutton",
    "Radiobutton", "TRadiobutton",
    "Menubutton", "TMenubutton",
)

_INSTALLED = False


def _press_inside(widget, event) -> bool:
    """True bila koordinat press benar-benar di dalam kotak widget."""
    try:
        return (0 <= event.x < widget.winfo_width()
                and 0 <= event.y < widget.winfo_height())
    except Exception:
        return False


def _is_disabled(widget) -> bool:
    try:
        state = widget.cget("state")
    except Exception:
        try:                                   # ttk
            return bool(widget.instate(["disabled"]))
        except Exception:
            return False
    return str(state) == "disabled"


def _arm(event):
    """Tandai tombol sebagai 'sedang di bawah pointer' sebelum jari dilepas."""
    w = getattr(event, "widget", None)
    if w is None:
        return None
    try:
        if not w.winfo_exists():
            return None
    except Exception:
        return None
    if _is_disabled(w) or not _press_inside(w, event):
        return None
    try:
        # when="now": event diproses langsung, bukan diantrikan. Kalau
        # diantrikan, ButtonRelease bisa terlanjur diproses lebih dulu dan
        # tombol tetap tidak jalan.
        w.event_generate("<Enter>", when="now", x=event.x, y=event.y,
                         rootx=event.x_root, rooty=event.y_root)
    except Exception:
        pass
    return None


def enable_touch_click(root: tk.Misc):
    """Aktifkan perbaikan tap-sekali untuk seluruh aplikasi. Idempoten."""
    global _INSTALLED
    if _INSTALLED:
        return
    for cls in _CLASSES:
        try:
            root.bind_class(cls, "<Button-1>", _arm, add="+")
        except Exception as e:                 # kelas ttk belum ter-load
            log.debug("touch_click: lewati class %s (%s)", cls, e)
    _INSTALLED = True
    log.debug("touch_click: aktif untuk %s", ", ".join(_CLASSES))
