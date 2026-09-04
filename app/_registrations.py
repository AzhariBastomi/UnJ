"""Daftar semua tombol dinamis header.

Untuk project baru: tambah blok register() di bawah.
Tidak perlu sentuh file lain.
"""

import os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from app._btn_registry import register

# ------------------------------------------------------------------
# TM81 — Commissioning
# ------------------------------------------------------------------
register(
    prefixes      = ["tm81:", "tm81_"],
    excludes      = ["tm81_ota:", "tm81_ota2:", "tm81_ota_bl:"],
    label         = "⚙ Commissioning",
    dialog        = "ui.dialogs.JsonFieldSettingsDialog",
    on_save_attr  = "_on_any_dialog_saved",
    static_kwargs = {"json_path": os.path.join(_ROOT, "commands", "tm81", "config", "commissioning.json")},
)

# ------------------------------------------------------------------
# TM81 — OTA Settings
# ------------------------------------------------------------------
register(
    prefixes      = ["tm81_ota:", "tm81_ota2:", "tm81_ota_bl:"],
    label         = "⚙ OTA Settings",
    dialog        = "ui.dialogs.JsonFieldSettingsDialog",
    on_save_attr  = "_on_any_dialog_saved",
    kwargs_method = "_get_ota_dialog_kwargs",
)

# ------------------------------------------------------------------
# Flash
# ------------------------------------------------------------------
register(
    prefixes      = ["flash:"],
    label         = "⚙ Flash Settings",
    dialog        = "ui.dialogs.JsonFieldSettingsDialog",
    on_save_attr  = "_on_any_dialog_saved",
    kwargs_method = "_get_flash_dialog_kwargs",
)

# ------------------------------------------------------------------
# BEXA
# ------------------------------------------------------------------
register(
    prefixes      = ["bexa:"],
    label         = "⚙ BEXA Settings",
    dialog        = "ui.dialogs.JsonFieldSettingsDialog",
    on_save_attr  = "_on_any_dialog_saved",
    static_kwargs = {"json_path": os.path.join(_ROOT, "config", "bexa.json")},
)
