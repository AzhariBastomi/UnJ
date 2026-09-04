"""
ui/popup_util.py — Perilaku popup (Toplevel) yang ramah layar sentuh.

Masalah yang diselesaikan:

1. Window manager dengan click-to-focus "memakan" sentuhan/klik PERTAMA pada
   window baru untuk keperluan fokus/raise, sehingga event itu tidak sampai ke
   dialog. Akibatnya tap pertama pada popup tidak memilih apa-apa — atau malah
   terbaca sebagai klik di luar sehingga popup langsung tertutup.
   → dialog di-lift + focus_force + grab_set begitu muncul.

2. Close-on-outside-click yang dievaluasi saat tombol DITEKAN membuat geseran
   jari (scroll) dan tap pertama gampang menutup popup.
   → penutupan dinilai saat tombol DILEPAS, dan hanya bila press maupun
     release sama-sama di luar dialog serta bukan akhir dari drag-scroll.

Cara pakai::

    class MyDialog(TouchPopupMixin, tk.Toplevel):
        def __init__(self, parent, ...):
            super().__init__(parent)
            ...
            self.init_popup_behavior()          # panggil paling akhir

Dialog boleh menyetel ``self._suppress_close = True`` sementara (mis. saat
membuka filedialog/messagebox) agar tidak ikut tertutup.
"""

import logging
import tkinter as tk

from ui.scroll_util import was_dragging
from ui.pointer_util import (install_pointer_probe, prime_pointer_repeatedly,
                             install_event_trace, grab_enabled)

log = logging.getLogger("main")


class TouchPopupMixin:
    """Perilaku aktivasi + penempatan + close-on-outside-click untuk Toplevel."""

    # ------------------------------------------------------------------
    # Penempatan
    # ------------------------------------------------------------------

    def place_over_parent(self, parent, margin: int = 8):
        """Tengahkan popup di atas parent, tapi paksa tetap di dalam layar.

        Penting untuk preset 7 inch: window utama (1024x600) bisa lebih besar
        dari panel fisiknya, sehingga menengahkan popup terhadap window saja
        bisa melempar sebagian popup — bahkan tombolnya — ke luar layar.
        Popup juga dikecilkan bila lebih tinggi/lebar dari layar.
        """
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w  = min(self.winfo_width(),  sw - 2 * margin)
        h  = min(self.winfo_height(), sh - 2 * margin)
        if w != self.winfo_width() or h != self.winfo_height():
            self.geometry(f"{w}x{h}")

        try:
            cx = parent.winfo_rootx() + parent.winfo_width()  // 2
            cy = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            cx, cy = sw // 2, sh // 2
        # Titik tengah pun dijaga agar berada di dalam layar
        cx = max(margin, min(cx, sw - margin))
        cy = max(margin, min(cy, sh - margin))

        x = max(margin, min(cx - w // 2, sw - w - margin))
        y = max(margin, min(cy - h // 2, sh - h - margin))
        self.geometry(f"+{x}+{y}")
        log.debug("popup %s: layar=%dx%d popup=%dx%d+%d+%d",
                  type(self).__name__, sw, sh, w, h, x, y)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def init_popup_behavior(self, grab: bool = True,
                            close_on_outside: bool = False,
                            arm_delay_ms: int = 80):
        """Aktifkan dialog sebagai window aktif dan pasang handler penutup.

        ``close_on_outside`` sengaja mati secara default. Di layar sentuh,
        tap/geseran yang koordinatnya sedikit meleset (atau event yang nyasar
        saat popup baru muncul) gampang dinilai "di luar" sehingga dialog
        tertutup sendiri saat pengguna baru mau memilih. Semua dialog sudah
        punya tombol Cancel/Tutup dan binding <Escape>, jadi tidak ada jalan
        buntu. Nyalakan per-dialog bila memang diinginkan.
        """
        self._popup_grabbed   = False
        self._popup_want_grab = grab
        self._press_outside   = False

        # Window harus SUDAH termap sebelum di-raise/di-fokus: memanggil
        # focus_force() pada window yang belum tampil tidak berefek, sehingga
        # window manager masih menganggap popup belum aktif dan menelan tap
        # pertama untuk keperluan fokus. Itulah kenapa popup baru bisa dipakai
        # setelah ditekan/digeser sekali.
        try:
            self.wait_visibility()
        except Exception:
            pass

        self._raise_window()
        # Ditegaskan ulang beberapa kali: sebagian window manager memindahkan
        # fokus kembali ke window utama sesaat setelah popup dipetakan.
        for _delay in (30, 120, 300):
            self.after(_delay, self._raise_window)

        # Pointer harus sudah "berada di dalam" dialog SEBELUM grab dipasang.
        # Grab lokal Tk membuang event pointer yang — menurut catatan internal
        # Tk — terjadi di luar pohon grab, dan catatan itu hanya diperbarui
        # oleh <Motion>/<Enter>/<Leave>. Di layar sentuh tidak ada gerakan
        # pointer sebelum tap, jadi catatan itu masih menunjuk window utama dan
        # tap PERTAMA di atas popup ikut terbuang. Lihat ui/pointer_util.py.
        install_pointer_probe(self)
        install_event_trace(self, "popup")
        prime_pointer_repeatedly(self)

        if grab and not grab_enabled():
            log.info("popup %s: grab dimatikan lewat JIG_POPUP_GRAB=0",
                     type(self).__name__)
            grab = False
            self._popup_want_grab = False
        if grab:
            self.after(10, self._acquire_grab)
        if close_on_outside:
            if not grab:
                log.debug("popup %s: close_on_outside butuh grab; "
                          "tanpa grab klik di luar tidak sampai ke dialog",
                          type(self).__name__)
            self.after(arm_delay_ms, self._arm_global_click)

    def _raise_window(self):
        """Angkat popup ke paling atas dan rebut fokus keyboard."""
        if not self.winfo_exists():
            return
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.lift()
        except Exception:
            pass
        try:
            self.focus_force()
        except Exception:
            pass


    def _acquire_grab(self):
        """Arahkan event pointer aplikasi ke dialog ini.

        Grab lokal memastikan sentuhan pertama diterima dialog, bukan hilang di
        window manager. Klik di luar tetap sampai ke sini (dengan koordinat di
        luar) sehingga close-on-outside-click tetap bekerja.
        """
        if not self.winfo_exists() or self._popup_grabbed:
            return
        try:
            self.grab_set()
            self._popup_grabbed = True
        except Exception:
            self.after(50, self._acquire_grab)   # belum viewable, coba lagi

    def _arm_global_click(self):
        """Pasang handler klik PADA DIALOG INI SENDIRI.

        Bukan bind_all: handler bind_all menempel di bindtag "all" milik
        interpreter dan tidak ikut hilang saat dialog di-destroy, sehingga tiap
        popup meninggalkan handler zombie yang terus dipanggil untuk window yang
        sudah mati ("bad window path name .!addtestdialog3").

        Ini cukup karena dialog memegang grab: klik di luar dialog pun dialihkan
        Tk ke widget grab, yaitu toplevel dialog ini, jadi tetap tertangkap di
        sini. Binding-nya otomatis hilang bersama window.
        """
        if not self.winfo_exists():
            return
        self.bind("<Button-1>",        self._on_global_press,   add="+")
        self.bind("<ButtonRelease-1>", self._on_global_release, add="+")

    # ------------------------------------------------------------------
    # Deteksi dalam/luar
    # ------------------------------------------------------------------

    def _widget_in_dialog(self, w) -> bool:
        """True bila widget `w` benar-benar anak dari dialog ini.

        Sengaja hanya menerima DESCENDANT, bukan toplevel dialog itu sendiri:
        selama grab lokal aktif, klik di luar dialog pun dialihkan Tk ke widget
        grab — yaitu toplevel dialog. Jadi `widget == self` bersifat ambigu dan
        harus diputuskan lewat posisi pointer, sementara `widget` berupa anak
        dialog pasti berarti tap benar-benar terjadi di dalam dialog.
        """
        try:
            path = str(w) if w is not None else ""
        except Exception:
            return False
        return bool(path) and path.startswith(str(self) + ".")

    def _inside_by_coords(self, event):
        """True/False dari koordinat root; None bila koordinat tak masuk akal."""
        try:
            cx, cy = int(event.x_root), int(event.y_root)
        except Exception:
            return None
        if not (cx or cy):
            return None
        try:
            dx, dy = self.winfo_rootx(), self.winfo_rooty()
            dw, dh = self.winfo_width(), self.winfo_height()
        except Exception:
            return None
        return dx <= cx <= dx + dw and dy <= cy <= dy + dh

    def _inside_by_pointer(self, event):
        """True/False dari widget yang benar-benar berada di bawah pointer.

        Tidak bergantung pada hitungan geometri dialog, jadi tetap benar walau
        koordinat root dari driver layar sentuh tidak sesuai dengan posisi
        window menurut window manager.
        """
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None
        if w is None:
            return None                     # di luar semua window aplikasi
        path = str(w)
        me   = str(self)
        return path == me or path.startswith(me + ".")

    def _is_inside(self, event) -> bool:
        """True bila event dianggap terjadi di dalam dialog ini.

        Dinilai dari tiga sumber: widget pengirim event, widget di bawah
        pointer, dan koordinat root. Cukup SATU yang bilang "di dalam" untuk
        menganggap event ini milik dialog. Sikap konservatif ini disengaja:
        salah menganggap "di luar" berarti dialog tertutup saat pengguna baru
        mau memilih — jauh lebih mengganggu daripada dialog yang perlu ditutup
        lewat tap kedua, Cancel, atau Escape.
        """
        if self._widget_in_dialog(getattr(event, "widget", None)):
            return True
        by_pointer = self._inside_by_pointer(event)
        if by_pointer:
            return True
        by_coords = self._inside_by_coords(event)
        if by_coords:
            return True
        if by_pointer is None and by_coords is None:
            return True                     # tidak ada info andal → jangan tutup
        return False

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    def _on_global_press(self, event):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._press_outside = not self._is_inside(event)
        if self._press_outside:
            log.debug("popup %s: press dinilai di luar (root=%s,%s widget=%s "
                      "dialog=%sx%s+%s+%s)",
                      type(self).__name__,
                      getattr(event, "x_root", "?"), getattr(event, "y_root", "?"),
                      getattr(event, "widget", "?"),
                      self.winfo_width(), self.winfo_height(),
                      self.winfo_rootx(), self.winfo_rooty())

    def _on_global_release(self, event):
        """Tutup dialog hanya bila satu tap penuh terjadi di luar dialog."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if getattr(self, "_suppress_close", False):
            return
        if was_dragging():              # akhir geseran scroll, bukan tap
            self._press_outside = False
            return
        if not self._press_outside:     # tap dimulai di dalam dialog
            return
        if self._is_inside(event):      # dilepas di dalam dialog
            return
        log.debug("popup %s ditutup: tap di luar (root=%s,%s dialog=%sx%s+%s+%s)",
                  type(self).__name__,
                  getattr(event, "x_root", "?"), getattr(event, "y_root", "?"),
                  self.winfo_width(), self.winfo_height(),
                  self.winfo_rootx(), self.winfo_rooty())
        try:
            self.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------

    def destroy(self):
        try:
            if getattr(self, "_popup_grabbed", False):
                self.grab_release()
                self._popup_grabbed = False
        except Exception:
            pass
        super().destroy()
