"""
ui/pointer_util.py — Menyegarkan catatan posisi pointer Tk saat popup muncul.

MASALAH
-------
Semua popup di aplikasi ini modal lewat ``grab_set`` (grab LOKAL). Grab lokal
Tk bukan grab X server: Tk sendiri yang menyaring setiap event pointer menjadi
"di dalam pohon grab" atau "di luar" — dan yang di luar DIBUANG.

Penilaian itu memakai catatan internal Tk tentang window mana yang sedang
ditempati pointer. Catatan tersebut HANYA diperbarui oleh event
``<Motion>`` / ``<Enter>`` / ``<Leave>``.

* Mouse   : kursor bergerak melintasi layar menuju popup, crossing event
            muncul, catatan Tk langsung benar → klik pertama jalan.
* Sentuhan: pointer "meloncat"; tidak ada gerakan sama sekali sebelum tap.
            Saat popup baru muncul, catatan Tk masih menunjuk window utama
            (tempat tap terakhir mendarat), jadi tap PERTAMA di atas popup
            dinilai terjadi di luar pohon grab dan dibuang. Tap itu sendiri
            yang memperbarui catatan, sehingga tap KEDUA baru bekerja.

Persis gejalanya: di popup apa pun (Clear All, Add Test, Settings, …) harus
"menekan sekali dulu di mana saja" sebelum tombol atau geser-scroll bisa
dipakai, sementara di window utama — yang tidak memasang grab, jadi tidak ada
penyaringan — semuanya normal sejak sentuhan pertama.

Ini juga alasan ``ui/touch_click.py`` tidak menolong untuk kasus ini: event-nya
sudah dibuang sebelum sampai ke tombol, jadi ``<Enter>`` buatan tidak pernah
sempat dikirim.

SOLUSI
------
Begitu popup tampil (dan SEBELUM grab dipasang), pointer dipindahkan ke dalam
popup memakai ``event_generate("<Motion>", warp=True)``. X server mengirim
crossing event sungguhan, catatan Tk ikut diperbarui, dan tap pertama pengguna
sudah dinilai "di dalam" popup.

Warp dilakukan hanya bila input dianggap layar sentuh, supaya di LCD dengan
mouse kursor tidak tiba-tiba meloncat ke tengah dialog. Deteksinya sederhana
dan tidak perlu dikonfigurasi: mouse menghasilkan BANYAK ``<Motion>`` tanpa
tombol ditekan (hover) saat digerakkan, layar sentuh nyaris tidak pernah —
sentuhan hanya menghasilkan motion sambil tombol "ditekan" (drag).

Bisa dipaksa lewat ``config.POINTER_WARP_ON_POPUP`` atau variabel lingkungan
``JIG_POINTER_WARP`` (1 / 0 / auto) untuk uji coba tanpa mengubah kode::

    JIG_POINTER_WARP=1 python main.py      # selalu warp
    JIG_POINTER_WARP=0 python main.py      # tidak pernah warp (perilaku lama)
"""

import logging
import os
import time
import tkinter as tk

log = logging.getLogger("main")

# Bit state untuk tombol mouse 1..5 pada event Tk.
_BUTTON_MASK = 0x1F00

# Jejak hover dianggap masih relevan selama ini (ms).
_MOUSE_WINDOW_MS = 4000.0
# Sebanyak ini gerakan hover dalam rentang di atas → yakin ini mouse.
_MOUSE_MIN_EVENTS = 4

# Titik warp: sedikit di bawah tepi atas dialog — biasanya area judul,
# bukan tombol, jadi tidak ada yang ter-highlight tanpa sengaja.
_WARP_Y = 8

_motion_times: list = []


def _now_ms() -> float:
    return time.monotonic() * 1000.0


# ══════════════════════════════════════════════════════════════════════════
# Deteksi jenis input
# ══════════════════════════════════════════════════════════════════════════

def _on_motion(event):
    """Catat gerakan pointer TANPA tombol ditekan (ciri khas mouse)."""
    if getattr(event, "state", 0) & _BUTTON_MASK:
        return None                     # geseran jari / drag mouse, bukan hover
    _motion_times.append(_now_ms())
    if len(_motion_times) > 32:
        del _motion_times[:-32]
    return None


def install_pointer_probe(widget: tk.Misc):
    """Pasang pendeteksi hover pada sebuah toplevel. Aman dipanggil berulang.

    Dipasang di toplevel (bukan ``bind_all``) supaya ikut hilang bersama
    window-nya dan tidak meninggalkan handler zombie.
    """
    try:
        widget.bind("<Motion>", _on_motion, add="+")
    except Exception as e:
        log.debug("pointer_util: probe gagal dipasang pada %s (%s)", widget, e)


def pointer_is_mouse() -> bool:
    """True bila belakangan ini terlihat hover — berarti ada mouse sungguhan."""
    cutoff = _now_ms() - _MOUSE_WINDOW_MS
    return sum(1 for t in _motion_times if t >= cutoff) >= _MOUSE_MIN_EVENTS


# ══════════════════════════════════════════════════════════════════════════
# Pengaturan
# ══════════════════════════════════════════════════════════════════════════

def _as_tristate(raw):
    """None = auto, True/False = paksa."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in ("auto", "", "none"):
        return None
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _warp_setting():
    env = _as_tristate(os.environ.get("JIG_POINTER_WARP"))
    if os.environ.get("JIG_POINTER_WARP") is not None:
        return env
    try:
        from config import POINTER_WARP_ON_POPUP
    except Exception:
        return None
    return _as_tristate(POINTER_WARP_ON_POPUP)


# ══════════════════════════════════════════════════════════════════════════
# Inti perbaikan
# ══════════════════════════════════════════════════════════════════════════

def prime_pointer(win: tk.Misc, force=None) -> bool:
    """Pastikan Tk tahu pointer berada DI DALAM ``win`` sebelum sentuhan pertama.

    Mengembalikan True bila pointer benar-benar dipindahkan.
    Tidak melakukan apa-apa (dan tidak menimbulkan error) bila window sudah
    hilang, belum tampil, atau pointer memang sudah berada di dalamnya.
    """
    try:
        if not win.winfo_exists() or not win.winfo_ismapped():
            return False
        win.update_idletasks()
        x0, y0 = win.winfo_rootx(), win.winfo_rooty()
        w,  h  = win.winfo_width(), win.winfo_height()
        px, py = win.winfo_pointerx(), win.winfo_pointery()
    except Exception:
        return False

    if w <= 1 or h <= 1:
        return False

    if px >= 0 and py >= 0 and x0 <= px < x0 + w and y0 <= py < y0 + h:
        return False                    # sudah di dalam → catatan Tk sudah benar

    want = _warp_setting() if force is None else force
    if want is None:
        want = not pointer_is_mouse()   # auto: warp hanya untuk layar sentuh
    if not want:
        return False

    tx = w // 2
    ty = min(max(h - 1, 0), _WARP_Y)
    try:
        win.event_generate("<Motion>", warp=True, x=tx, y=ty)
        win.update_idletasks()          # paksa warp dieksekusi sekarang juga
    except Exception as e:
        log.debug("pointer_util: warp gagal untuk %s (%s)", type(win).__name__, e)
        return False

    log.debug("pointer_util: pointer dipindah ke %s (%d,%d) dari (%s,%s)",
              type(win).__name__, x0 + tx, y0 + ty, px, py)
    return True


def prime_pointer_repeatedly(win: tk.Misc, delays=(0, 60, 200)):
    """Ulangi ``prime_pointer`` beberapa kali sesudah window muncul.

    Window manager sering baru menempatkan/mengubah ukuran popup beberapa puluh
    milidetik setelah dipetakan; warp pertama bisa mendarat di posisi lama.
    Pemanggilan berikutnya otomatis tidak melakukan apa-apa bila pointer sudah
    berada di dalam window.
    """
    for d in delays:
        if d <= 0:
            prime_pointer(win)
        else:
            try:
                win.after(d, lambda w=win: prime_pointer(w))
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════
# Diagnosa (opsional)
# ══════════════════════════════════════════════════════════════════════════
#
# Nyalakan dengan variabel lingkungan JIG_TOUCH_DEBUG=1, lalu buka satu popup
# di panel sentuh dan sentuh SEKALI. Isi log akan langsung memberi tahu ke mana
# sentuhan pertama itu pergi:
#
#   * tidak ada baris "TRACE" sama sekali untuk sentuhan pertama
#       → event dibuang grab lokal Tk. Coba jalankan dengan JIG_POPUP_GRAB=0;
#         kalau jadi normal, penyebabnya sudah pasti.
#   * ada "TRACE main ... Button-1"
#       → sentuhan pertama masih dialamatkan ke window utama (posisi pointer
#         basi). Warp (JIG_POINTER_WARP=1) yang menyelesaikannya.
#   * ada "TRACE popup ... Button-1" tapi tombol tetap tidak jalan
#       → murni soal crossing event; itu wilayah ui/touch_click.py.

_TRACE_SEQS = ("<Motion>", "<Enter>", "<Leave>",
               "<Button-1>", "<ButtonRelease-1>", "<B1-Motion>",
               "<FocusIn>", "<FocusOut>", "<Map>", "<Visibility>")


def trace_enabled() -> bool:
    return _as_tristate(os.environ.get("JIG_TOUCH_DEBUG")) is True


def install_event_trace(win: tk.Misc, tag: str = "?"):
    """Catat semua event pointer pada sebuah toplevel. Hanya bila JIG_TOUCH_DEBUG=1."""
    if not trace_enabled():
        return

    def _trace(event, tag=tag):
        try:
            under = win.winfo_containing(event.x_root, event.y_root)
        except Exception:
            under = "?"
        log.info("TRACE %-6s %-16s widget=%-32s root=(%s,%s) state=0x%x under=%s",
                 tag,
                 getattr(event, "type", "?"),
                 str(getattr(event, "widget", "?"))[:32],
                 getattr(event, "x_root", "?"), getattr(event, "y_root", "?"),
                 int(getattr(event, "state", 0) or 0),
                 under)
        return None

    for seq in _TRACE_SEQS:
        try:
            win.bind(seq, _trace, add="+")
        except Exception:
            pass
    log.info("TRACE aktif untuk %s (%s)", tag, type(win).__name__)


def grab_enabled() -> bool:
    """False bila grab popup sengaja dimatikan lewat JIG_POPUP_GRAB=0."""
    return _as_tristate(os.environ.get("JIG_POPUP_GRAB")) is not False
