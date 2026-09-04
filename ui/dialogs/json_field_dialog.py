"""
ui/dialogs/json_field_dialog.py — JsonFieldSettingsDialog

Universal JSON-driven settings dialog.
UI spec is read from data["_dialog"] inside the JSON config file.
"""

import sys, os, json, datetime
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LIB  = os.path.join(_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import tkinter as tk
from tkinter import ttk, filedialog
from config import COLORS, BASE_FONTS
from ui.popup_util import TouchPopupMixin
# Dialog pesan sendiri, bukan tkinter.messagebox bawaan Tk: yang bawaan
# tidak melewati TouchPopupMixin sehingga tap pertamanya ditelan window
# manager di layar sentuh. Lihat ui/dialogs/confirm.py.
from .confirm import show_warning, show_error

# ---------------------------------------------------------------------------
# Timezone data
# ---------------------------------------------------------------------------

_TZ_ENTRIES = [
    ("UTC+14 — Kiribati", 14), ("UTC+13 — Samoa, Tonga, Tokelau", 13),
    ("UTC+12:45 — Chatham, NZ  ⚠ tidak didukung", None),
    ("UTC+12 — Selandia Baru, Fiji, Tuvalu", 12),
    ("UTC+11 — Kaledonia Baru, Kep. Solomon", 11),
    ("UTC+10:30 — Lord Howe, Australia  ⚠ tidak didukung", None),
    ("UTC+10 — Sydney, Guam, Papua Nugini", 10),
    ("UTC+9:30 — Adelaide, Darwin  ⚠ tidak didukung", None),
    ("UTC+9  — WIT · Jepang · Korea · Timor Leste", 9),
    ("UTC+8  — WITA · Singapura · Tiongkok · Malaysia", 8),
    ("UTC+7  — WIB · Thailand · Vietnam · Kamboja", 7),
    ("UTC+6:30 — Myanmar, Cocos  ⚠ tidak didukung", None),
    ("UTC+6  — Bangladesh, Bhutan, Kyrgyzstan", 6),
    ("UTC+5:45 — Nepal  ⚠ tidak didukung", None),
    ("UTC+5:30 — India, Sri Lanka  ⚠ tidak didukung", None),
    ("UTC+5  — Pakistan, Uzbekistan, Maladewa", 5),
    ("UTC+4:30 — Afghanistan  ⚠ tidak didukung", None),
    ("UTC+4  — Dubai, Oman, Georgia, Azerbaijan", 4),
    ("UTC+3:30 — Iran  ⚠ tidak didukung", None),
    ("UTC+3  — Arab Saudi, Moskow, Turki, Kenya", 3),
    ("UTC+2  — Mesir, Yunani, Afrika Selatan", 2),
    ("UTC+1  — Jerman, Prancis, Italia, Nigeria", 1),
    ("UTC+0  — Inggris, Portugal, Ghana, Maroko", 0),
    ("UTC-1  — Tanjung Verde, Azores", -1),
    ("UTC-2  — Georgia Selatan", -2),
    ("UTC-3  — Brasil, Argentina, Uruguay", -3),
    ("UTC-3:30 — Newfoundland, Kanada  ⚠ tidak didukung", None),
    ("UTC-4  — Chile, Bolivia, Venezuela", -4),
    ("UTC-5  — New York, Kolombia, Peru", -5),
    ("UTC-6  — Chicago, Meksiko, Nikaragua", -6),
    ("UTC-7  — Denver, Arizona", -7),
    ("UTC-8  — Los Angeles, San Francisco", -8),
    ("UTC-9  — Alaska", -9),
    ("UTC-9:30 — Marquesas  ⚠ tidak didukung", None),
    ("UTC-10 — Hawaii, Tahiti", -10),
    ("UTC-11 — Samoa Amerika, Niue", -11),
    ("UTC-12 — Pulau Baker, Howland", -12),
]


# ---------------------------------------------------------------------------
# Dot-path helpers
# ---------------------------------------------------------------------------

def _is_index(k) -> bool:
    """True kalau segmen dot-path merupakan indeks list (mis. '0')."""
    return k.lstrip("-").isdigit()


def _get_dotpath(data, key, default=None):
    keys = key.split(".")
    v = data
    for k in keys:
        if isinstance(v, dict):
            v = v.get(k, {})
        elif isinstance(v, list) and _is_index(k):
            try:
                v = v[int(k)]
            except IndexError:
                return default
        else:
            return default
    return v if v != {} else default


def _set_dotpath(data, key, value):
    keys = key.split(".")
    d = data
    for i, k in enumerate(keys[:-1]):
        nxt = keys[i + 1]
        if isinstance(d, list):
            if not _is_index(k):
                raise KeyError(f"Path '{key}': '{k}' bukan indeks list yang valid.")
            d = d[int(k)]
        elif isinstance(d, dict):
            if not isinstance(d.get(k), (dict, list)):
                d[k] = [] if _is_index(nxt) else {}
            d = d[k]
        else:
            raise KeyError(f"Path '{key}': tidak bisa menelusuri '{k}' pada {type(d).__name__}.")

    last = keys[-1]
    if isinstance(d, list):
        if not _is_index(last):
            raise KeyError(f"Path '{key}': '{last}' bukan indeks list yang valid.")
        d[int(last)] = value
    else:
        d[last] = value


# ---------------------------------------------------------------------------
# System timezone detection
# ---------------------------------------------------------------------------

def _detect_local_tz_offset() -> int:
    offset = datetime.datetime.now(datetime.timezone.utc).astimezone().utcoffset()
    return int(offset.total_seconds() // 3600)


# ---------------------------------------------------------------------------
# Title template resolution
# ---------------------------------------------------------------------------

def _resolve_title(title: str, data: dict, context: dict) -> str:
    """Substitute {project} from context, then resolve remaining {dot.path} from data."""
    # First pass: substitute context keys
    for k, v in context.items():
        title = title.replace("{" + k + "}", str(v))
    # Second pass: resolve remaining {dot.path} from data (simple, non-nested)
    import re
    def _repl(m):
        path = m.group(1)
        val = _get_dotpath(data, path)
        return str(val) if val is not None else m.group(0)
    title = re.sub(r"\{([^{}]+)\}", _repl, title)
    return title


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class JsonFieldSettingsDialog(TouchPopupMixin, tk.Toplevel):
    """
    Universal settings dialog driven by _dialog spec in a JSON config file.

    Parameters
    ----------
    parent    : tk widget
    json_path : absolute path to JSON config file
    context   : dict of runtime substitution values, e.g. {"project": "stm32"}
    on_save   : callable called after successful save
    """

    def __init__(self, parent, json_path: str, context: dict = None, on_save=None):
        super().__init__(parent)
        self.resizable(False, False)
        self.transient(parent)

        C = COLORS
        self.configure(bg=C["bg"])

        self._json_path   = json_path
        self._context     = context or {}
        self._on_save_cb  = on_save
        self._save_actions = []         # list of callables; each mutates self._data
        self._suppress_close = False

        self._data = self._load()
        spec = self._data.get("_dialog", {})

        title = _resolve_title(spec.get("title", "Settings"), self._data, self._context)
        self.title(title)

        self._build(spec, title)
        self.update_idletasks()

        # Tengahkan + jaga agar tetap muat di layar (lihat popup_util)
        self.place_over_parent(parent)

        # Grab tetap dipakai: close-on-outside-click hanya bekerja bila klik di
        # luar dialihkan ke dialog ini. filedialog/messagebox memasang grab-nya
        # sendiri dan dilindungi flag _suppress_close.
        self.init_popup_behavior()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        try:
            with open(self._json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write(self):
        os.makedirs(os.path.dirname(self._json_path), exist_ok=True)
        with open(self._json_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self, spec: dict, title: str):
        C  = COLORS
        fs = lambda k: max(7, int(BASE_FONTS[k]))

        # Dark header bar
        hdr = tk.Frame(self, bg=C["header_bg"], pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"⚙  {title}",
                 bg=C["header_bg"], fg="white",
                 font=("TkDefaultFont", fs("label"), "bold"),
                 padx=12).pack(side="left")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=8, pady=8)

        tabs = spec.get("tabs")
        if tabs:
            style = ttk.Style()
            style.configure("JF.TNotebook",     background=C["bg"], borderwidth=0)
            style.configure("JF.TNotebook.Tab", padding=[10, 4])
            nb = ttk.Notebook(body, style="JF.TNotebook")
            nb.pack(fill="both", expand=True)
            for tab_spec in tabs:
                tab_frame = tk.Frame(nb, bg=C["bg"], padx=4, pady=4)
                nb.add(tab_frame, text=f"  {tab_spec.get('label', '')}  ")
                for sec in tab_spec.get("sections", []):
                    self._build_section(tab_frame, sec)
        else:
            for sec in spec.get("sections", []):
                self._build_section(body, sec)

        # Bottom buttons
        tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=12, pady=(4, 0))
        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(fill="x", padx=12, pady=8)
        tk.Button(btn_row, text="Batal", command=self.destroy,
                  bg=C["border"], fg=C["text"], relief="flat",
                  width=8, cursor="hand2",
                  font=("TkDefaultFont", fs("button"))
                  ).pack(side="right", padx=(4, 0))
        tk.Button(btn_row, text="Simpan", command=self._on_save,
                  bg=C["running"], fg="white", relief="flat",
                  width=8, cursor="hand2",
                  font=("TkDefaultFont", fs("button"))
                  ).pack(side="right")

    def _build_section(self, parent: tk.Widget, sec: dict):
        C  = COLORS
        fs = lambda k: max(7, int(BASE_FONTS[k]))

        # Dynamic section
        if "dynamic_from" in sec:
            self._build_dynamic_section(parent, sec)
            return

        card = tk.Frame(parent, bg=C["card"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x", pady=6)

        row_idx = 0

        if sec.get("label"):
            tk.Label(card, text=sec["label"],
                     bg=C["card"], fg=C["text"],
                     font=("TkDefaultFont", fs("small"), "bold"),
                     ).grid(row=row_idx, column=0, columnspan=3, sticky="w",
                            padx=8, pady=(6, 2))
            row_idx += 1

        if sec.get("note"):
            tk.Label(card, text=sec["note"],
                     bg=C["card"], fg=C["sub"],
                     font=("TkDefaultFont", fs("small")), justify="left",
                     wraplength=380,
                     ).grid(row=row_idx, column=0, columnspan=3, sticky="w",
                            padx=8, pady=(0, 6))
            row_idx += 1

        for fld in sec.get("fields", []):
            self._build_field(card, fld, row_idx)
            row_idx += 1

    def _build_dynamic_section(self, parent: tk.Widget, sec: dict):
        """Build sections dynamically from a list at a dot-path, with context substitution."""
        C  = COLORS
        fs = lambda k: max(7, int(BASE_FONTS[k]))

        # Resolve dynamic_from path (substitute context)
        raw_path = sec["dynamic_from"]
        for k, v in self._context.items():
            raw_path = raw_path.replace("{" + k + "}", str(v))

        items = _get_dotpath(self._data, raw_path, [])
        if not isinstance(items, list):
            items = []

        item_label_key = sec.get("item_label", "label")
        item_key_key   = sec.get("item_key",   "name")
        item_fields    = sec.get("item_fields", [])

        for item_index, item in enumerate(items):
            item_name  = item.get(item_key_key, "")
            item_label = item.get(item_label_key, item_name)

            card = tk.Frame(parent, bg=C["card"],
                            highlightthickness=1, highlightbackground=C["border"])
            card.pack(fill="x", pady=6)

            tk.Label(card, text=item_label,
                     bg=C["card"], fg=C["text"],
                     font=("TkDefaultFont", fs("small"), "bold"),
                     ).grid(row=0, column=0, columnspan=3, sticky="w",
                            padx=8, pady=(6, 2))

            for r_idx, fld in enumerate(item_fields, start=1):
                # For dynamic items the key is relative to the item dict.
                # We wrap via a per-item path: raw_path[i].key
                # We need to find the item index in the list.
                abs_key = f"{raw_path}.{item_index}.{fld['key']}"
                fld_copy = dict(fld, key=abs_key)
                # Display label override — use fld label as-is
                self._build_field(card, fld_copy, r_idx,
                                  # flash_dir context for firmware browse
                                  flash_dir_data=self._data)

    def _build_field(self, card: tk.Widget, fld: dict, row: int,
                     flash_dir_data: dict = None):
        C  = COLORS
        fs = lambda k: max(7, int(BASE_FONTS[k]))

        key   = fld["key"]
        label = fld.get("label", key)
        ftype = fld.get("type", "text")

        # -- Label column (col 0) --
        tk.Label(card, text=label,
                 bg=C["card"], fg=C["text"],
                 font=("TkDefaultFont", fs("small")),
                 width=17, anchor="w",
                 ).grid(row=row, column=0, sticky="w", padx=8, pady=3)

        current_val = _get_dotpath(self._data, key)

        # ------------------------------------------------------------------
        # text / port / number
        # ------------------------------------------------------------------
        if ftype in ("text", "port", "number"):
            width = {"text": 20, "port": 12, "number": 10}.get(ftype, 20)
            var = tk.StringVar(value="" if current_val is None else str(current_val))
            ent = tk.Entry(card, textvariable=var, width=width,
                           bg=C["surface"], fg=C["text"], relief="flat",
                           insertbackground=C["text"],
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["running"],
                           font=("TkDefaultFont", fs("small")))
            ent.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

            if ftype == "number":
                def _action_number(k=key, v=var):
                    raw = v.get().strip()
                    try:
                        _set_dotpath(self._data, k, int(raw))
                    except ValueError:
                        raise ValueError(f"'{label}' harus berupa angka integer.")
            else:
                def _action_text(k=key, v=var):
                    _set_dotpath(self._data, k, v.get().strip())
                _action_number = _action_text  # reuse variable name

            self._save_actions.append(_action_number)

        # ------------------------------------------------------------------
        # select — Combobox, stores index
        # ------------------------------------------------------------------
        elif ftype == "select":
            options = fld.get("options", [])
            idx = current_val if isinstance(current_val, int) else 0
            idx = max(0, min(idx, len(options) - 1))
            var = tk.IntVar(value=idx)
            cb = ttk.Combobox(card, values=options, state="readonly", width=22,
                              font=("TkDefaultFont", fs("small")))
            cb.current(idx)
            cb.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")
            cb.bind("<<ComboboxSelected>>",
                    lambda e, v=var, c=cb, opts=options: v.set(opts.index(c.get())))

            def _action_select(k=key, v=var):
                _set_dotpath(self._data, k, v.get())
            self._save_actions.append(_action_select)

        # ------------------------------------------------------------------
        # file — Entry readonly + Browse (any file)
        # ------------------------------------------------------------------
        elif ftype == "file":
            var = tk.StringVar(value="" if current_val is None else str(current_val))
            ent = tk.Entry(card, textvariable=var, width=30,
                           bg=C["surface"], fg=C["text"], relief="flat",
                           state="readonly",
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["running"],
                           font=("TkDefaultFont", fs("small")))
            ent.grid(row=row, column=1, padx=(0, 4), pady=3, sticky="w")
            var.trace_add("write", lambda *_, e=ent: e.after(0, lambda: e.xview_moveto(1.0)))

            def _browse_file(v=var, ent_=ent):
                self._suppress_close = True
                self.config(cursor="watch"); self.update()
                cur = v.get().strip()
                init_dir = os.path.dirname(cur) if (cur and os.path.isabs(cur) and os.path.isdir(os.path.dirname(cur))) else _ROOT
                path = filedialog.askopenfilename(parent=self, title="Pilih file",
                                                  filetypes=[("All", "*.*")],
                                                  initialdir=init_dir)
                self.config(cursor="")
                if path:
                    v.set(os.path.normpath(os.path.abspath(path)))
                    ent_.after(0, lambda: ent_.xview_moveto(1.0))
                self.after(300, lambda: setattr(self, "_suppress_close", False))

            tk.Button(card, text="Browse", command=_browse_file,
                      bg=C["border"], fg=C["text"], relief="flat", cursor="hand2",
                      font=("TkDefaultFont", fs("small")),
                      ).grid(row=row, column=2, padx=(0, 8), pady=3)

            def _action_file(k=key, v=var):
                _set_dotpath(self._data, k, v.get().strip())
            self._save_actions.append(_action_file)

        # ------------------------------------------------------------------
        # firmware — Entry readonly + Browse (.bin/.hex), uses flash_dir
        # ------------------------------------------------------------------
        elif ftype == "firmware":
            var = tk.StringVar(value="" if current_val is None else str(current_val))
            ent = tk.Entry(card, textvariable=var, width=30,
                           bg=C["surface"], fg=C["text"], relief="flat",
                           state="readonly",
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["running"],
                           font=("TkDefaultFont", fs("small")))
            ent.grid(row=row, column=1, padx=(0, 4), pady=3, sticky="w")
            var.trace_add("write", lambda *_, e=ent: e.after(0, lambda: e.xview_moveto(1.0)))

            _fdata = flash_dir_data if flash_dir_data is not None else self._data
            flash_dir = os.path.join(_ROOT, _fdata.get("flash_dir", "firmware"))

            def _browse_fw(v=var, ent_=ent, fd=flash_dir):
                self._suppress_close = True
                self.config(cursor="watch"); self.update()
                cur = v.get().strip()
                if cur and os.path.isabs(cur) and os.path.isdir(os.path.dirname(cur)):
                    init_dir = os.path.dirname(cur)
                elif os.path.isdir(fd):
                    init_dir = fd
                else:
                    init_dir = _ROOT
                path = filedialog.askopenfilename(
                    parent=self, title="Pilih firmware",
                    filetypes=[("Binary", "*.bin *.hex"), ("All", "*.*")],
                    initialdir=init_dir)
                self.config(cursor="")
                if path:
                    v.set(os.path.normpath(os.path.abspath(path)))
                    ent_.after(0, lambda: ent_.xview_moveto(1.0))
                self.after(300, lambda: setattr(self, "_suppress_close", False))

            tk.Button(card, text="Browse", command=_browse_fw,
                      bg=C["border"], fg=C["text"], relief="flat", cursor="hand2",
                      font=("TkDefaultFont", fs("small")),
                      ).grid(row=row, column=2, padx=(0, 8), pady=3)

            def _action_fw(k=key, v=var):
                _set_dotpath(self._data, k, v.get().strip())
            self._save_actions.append(_action_fw)

        # ------------------------------------------------------------------
        # hex — monospace Entry, validates hex, bytes: N required
        # ------------------------------------------------------------------
        elif ftype == "hex":
            nbytes = fld.get("bytes", 1)
            width  = nbytes * 2 + 2
            var = tk.StringVar(value="" if current_val is None else str(current_val))
            ent = tk.Entry(card, textvariable=var, width=width,
                           bg=C["surface"], fg=C["text"], relief="flat",
                           insertbackground=C["text"],
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["running"],
                           font=("Courier", fs("small")))
            ent.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

            def _action_hex(k=key, v=var, n=nbytes, lbl=label):
                raw = v.get().strip().replace(":", "").replace(" ", "")
                if len(raw) != n * 2:
                    raise ValueError(f"'{lbl}' harus {n*2} karakter hex ({n} bytes). Sekarang: {len(raw)} karakter.")
                try:
                    int(raw, 16)
                except ValueError:
                    raise ValueError(f"'{lbl}' mengandung karakter non-hex.")
                _set_dotpath(self._data, k, raw.upper())
            self._save_actions.append(_action_hex)

        # ------------------------------------------------------------------
        # hex_addr — monospace Entry, validates/formats as "0xXXXXXXXX"
        # ------------------------------------------------------------------
        elif ftype == "hex_addr":
            var = tk.StringVar(value="" if current_val is None else str(current_val))
            ent = tk.Entry(card, textvariable=var, width=12,
                           bg=C["surface"], fg=C["text"], relief="flat",
                           insertbackground=C["text"],
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["running"],
                           font=("Courier", fs("small")))
            ent.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

            def _action_hex_addr(k=key, v=var, lbl=label):
                raw = v.get().strip().replace(" ", "")
                try:
                    if raw.lower().startswith("0x"):
                        val_int = int(raw, 16)
                    else:
                        val_int = int(raw, 16)
                    _set_dotpath(self._data, k, f"0x{val_int:08X}")
                except (ValueError, AttributeError):
                    raise ValueError(f"'{lbl}' harus hex address (contoh: 0x0100000B).")
            self._save_actions.append(_action_hex_addr)

        # ------------------------------------------------------------------
        # timezone — special combobox
        # ------------------------------------------------------------------
        elif ftype == "timezone":
            _tz_labels  = [lbl for lbl, _ in _TZ_ENTRIES]
            _tz_vals    = [v   for _, v  in _TZ_ENTRIES]

            # Current stored value (int UTC offset) or auto-detect
            stored = current_val if isinstance(current_val, int) else _detect_local_tz_offset()
            def_idx = next((i for i, v in enumerate(_tz_vals) if v == stored), 0)

            var       = tk.IntVar(value=stored)
            tz_prev   = [def_idx]

            cb = ttk.Combobox(card, values=_tz_labels, state="readonly", width=36,
                              font=("TkDefaultFont", fs("small")))
            cb.current(def_idx)
            cb.grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

            def _on_tz_select(event, v=var, _cb=cb, labels=_tz_labels, vals=_tz_vals, prev=tz_prev):
                lbl_sel = _cb.get()
                try:
                    idx = labels.index(lbl_sel)
                except ValueError:
                    return
                val = vals[idx]
                if val is None:
                    _cb.current(prev[0])
                    show_warning(
                        self,
                        "Tidak Didukung",
                        "Timezone ini menggunakan offset setengah jam dan\n"
                        "belum didukung oleh device TM81.\n\n"
                        "Pilih timezone dengan offset jam penuh.")
                else:
                    prev[0] = idx
                    v.set(val)

            cb.bind("<<ComboboxSelected>>", _on_tz_select)

            def _action_tz(k=key, v=var):
                _set_dotpath(self._data, k, v.get())
            self._save_actions.append(_action_tz)

        else:
            # Unknown type — show a label
            tk.Label(card, text=f"(unknown type: {ftype})",
                     bg=C["card"], fg=C["sub"],
                     font=("TkDefaultFont", fs("small")),
                     ).grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        for action in self._save_actions:
            try:
                action()
            except (ValueError, TypeError) as e:
                show_error(self, "Validasi gagal", str(e))
                return

        try:
            self._write()
            self.destroy()
            if self._on_save_cb:
                self._on_save_cb()
        except Exception as e:
            show_error(self, "Gagal simpan", str(e))
