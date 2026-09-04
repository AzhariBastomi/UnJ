"""
ui/scroll_util.py — Helper mousewheel scrolling lintas platform.

Kenapa perlu:
- Windows/macOS  → event <MouseWheel> (punya event.delta)
- Linux/X11      → event <Button-4> (scroll up) dan <Button-5> (scroll down)

Binding dipasang di TOPLEVEL widget (bukan bind_all), sehingga:
- Semua child di window itu ikut terjangkau (event naik ke bindtag toplevel),
  jadi kursor tidak perlu tepat di atas canvas/scrollbar.
- Tidak bentrok antar window: dialog punya toplevel sendiri, jadi wheel di
  dalam popup tidak lagi menggeser list di window utama (dan sebaliknya).
- Tidak perlu Enter/Leave + unbind_all yang rawan "nyangkut".

Handler tetap mengecek posisi pointer: hanya canvas yang berada di bawah
kursor yang di-scroll.
"""

import tkinter as tk


def _pointer_inside(widget, event) -> bool:
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return False
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        return (x <= event.x_root < x + widget.winfo_width()
                and y <= event.y_root < y + widget.winfo_height())
    except Exception:
        return False


def _wheel_units(event, step: int) -> int:
    """Normalisasi arah/jumlah scroll dari berbagai platform."""
    if getattr(event, "num", None) == 4:
        return -step
    if getattr(event, "num", None) == 5:
        return step
    delta = getattr(event, "delta", 0)
    if delta == 0:
        return 0
    if abs(delta) >= 120:            # Windows
        return int(-delta / 120) * step
    return (-1 if delta > 0 else 1) * step   # macOS (delta kecil)


def bind_mousewheel(canvas: tk.Canvas, step: int = 3, area: tk.Misc = None):
    """
    Aktifkan scroll roda mouse untuk `canvas` di seluruh window-nya.

    step : jumlah 'units' per klik roda.
    area : widget pembatas area aktif (default: canvas itu sendiri).
           Berguna kalau ingin area sensitif termasuk scrollbar di sampingnya.
    """
    top    = canvas.winfo_toplevel()
    region = area if area is not None else canvas

    def _handler(event):
        if not canvas.winfo_exists():
            return None
        if not _pointer_inside(region, event):
            return None
        try:
            first, last = canvas.yview()
        except Exception:
            return None
        if float(first) <= 0.0 and float(last) >= 1.0:
            return "break"          # tidak ada yang bisa di-scroll
        units = _wheel_units(event, step)
        if units:
            canvas.yview_scroll(units, "units")
        return "break"

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        top.bind(seq, _handler, add="+")

    return _handler


# ══════════════════════════════════════════════════════════════════════════
# Touch / drag-to-scroll
# ══════════════════════════════════════════════════════════════════════════
#
# Layar sentuh di X11 tidak menghasilkan event roda mouse sama sekali; sentuhan
# diterjemahkan jadi <Button-1> + <B1-Motion> + <ButtonRelease-1>. Jadi supaya
# bisa di-scroll dengan jari, geseran vertikal harus ditangani manual.
#
# Binding dipasang di toplevel (add="+") agar tetap kena walau jari menyentuh
# label/tombol di dalam list — event tetap naik ke bindtag toplevel.

_DRAG_THRESHOLD_PX = 8      # geser < ini dianggap tap, bukan scroll
_last_drag_ms      = [0]    # timestamp drag terakhir (dipakai dialog)


def was_dragging(within_ms: int = 400) -> bool:
    """True bila baru saja terjadi drag-scroll.

    Dipakai handler klik (mis. close-on-outside-click) supaya klik yang
    sebenarnya adalah akhir dari geseran jari tidak diperlakukan sebagai tap.
    """
    try:
        import time
        return (time.monotonic() * 1000 - _last_drag_ms[0]) < within_ms
    except Exception:
        return False


def bind_touch_scroll(canvas: tk.Canvas, area: tk.Misc = None):
    """Aktifkan scroll dengan geser jari / drag mouse pada `canvas`."""
    import time

    top    = canvas.winfo_toplevel()
    region = area if area is not None else canvas
    st     = {"y0": 0, "first0": 0.0, "active": False, "moved": False}

    def _content_height() -> int:
        try:
            bbox = canvas.bbox("all")
            if not bbox:
                return 0
            return max(bbox[3] - bbox[1], 1)
        except Exception:
            return 0

    def _press(event):
        st["active"] = False
        st["moved"]  = False
        if not canvas.winfo_exists() or not _pointer_inside(region, event):
            return None
        try:
            first, last = canvas.yview()
        except Exception:
            return None
        if float(first) <= 0.0 and float(last) >= 1.0:
            return None          # tidak ada yang bisa di-scroll
        st["active"] = True
        st["y0"]     = event.y_root
        st["first0"] = float(first)
        return None

    def _motion(event):
        if not st["active"] or not canvas.winfo_exists():
            return None
        dy = event.y_root - st["y0"]
        if not st["moved"]:
            if abs(dy) < _DRAG_THRESHOLD_PX:
                return None
            st["moved"] = True
        total = _content_height()
        if total <= 0:
            return None
        # jari turun (dy > 0) → konten ikut turun → posisi scroll naik
        canvas.yview_moveto(max(0.0, min(1.0, st["first0"] - dy / total)))
        _last_drag_ms[0] = time.monotonic() * 1000
        return "break"

    def _release(event):
        if st["moved"]:
            _last_drag_ms[0] = time.monotonic() * 1000
        st["active"] = False
        return None

    top.bind("<Button-1>",        _press,   add="+")
    top.bind("<B1-Motion>",       _motion,  add="+")
    top.bind("<ButtonRelease-1>", _release, add="+")


def bind_scroll(canvas: tk.Canvas, step: int = 3, area: tk.Misc = None):
    """Aktifkan roda mouse + drag jari sekaligus."""
    bind_mousewheel(canvas, step=step, area=area)
    bind_touch_scroll(canvas, area=area)
