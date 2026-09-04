"""Button registry — daftar tombol dinamis di header.

Cara pakai:
    from app._btn_registry import register, get_all, ButtonSpec

    register(
        prefixes   = ["myproject:"],
        label      = "⚙ My Settings",
        dialog     = "ui.dialogs.MyDialog",          # importable path
        on_save_attr  = "_reload_my_tests",          # dot-path pada App (opsional)
        kwargs_method = "_get_my_dialog_kwargs",     # method App → dict (opsional)
    )
"""

from dataclasses import dataclass, field
from typing import List, Optional

_REGISTRY: "list[ButtonSpec]" = []


@dataclass
class ButtonSpec:
    label         : str
    dialog        : str                # "ui.dialogs.SomeDialog"
    prefixes      : List[str]
    excludes      : List[str]          = field(default_factory=list)
    on_save_attr  : Optional[str]      = None  # dot-path di App, mis. "_list_panel.refresh_validations"
    kwargs_method : Optional[str]      = None  # nama method di App yang return dict extra kwargs
    static_kwargs : dict               = None  # static kwargs langsung dipass ke DialogClass


def register(
    prefixes      : List[str],
    label         : str,
    dialog        : str,
    excludes      : List[str]     = (),
    on_save_attr  : Optional[str] = None,
    kwargs_method : Optional[str] = None,
    static_kwargs : dict          = None,
):
    _REGISTRY.append(ButtonSpec(
        label         = label,
        dialog        = dialog,
        prefixes      = list(prefixes),
        excludes      = list(excludes),
        on_save_attr  = on_save_attr,
        kwargs_method = kwargs_method,
        static_kwargs = dict(static_kwargs) if static_kwargs else {},
    ))


def get_all() -> "list[ButtonSpec]":
    return list(_REGISTRY)
