"""
project.py — Project classification helpers.

"Project" = kumpulan test yang saling eksklusif (tm81 / flash / ota).
"Universal" = test yang bisa ditambahkan ke project mana saja.

Prefix tm81_*: (selain tm81: dan tm81_ota:) di-detect otomatis —
tidak perlu di-hardcode di sini ketika JSON baru ditambahkan.
"""

_PROJECT_PREFIXES: dict[str, list[str]] = {
    "tm81":  ["tm81:"],
    "flash": ["flash:"],
    "bexa":  ["bexa:"],
}
_PROJECT_SINGLES: dict[str, list[str]] = {}


def module_project(module_name: str) -> "str | None":
    """Return project name jika modul project-specific, else None (universal).

    Prefix tm81_*: yang tidak ada di _PROJECT_PREFIXES di-detect otomatis
    sebagai project dengan nama = prefix stem-nya (mis. 'tm81_join').
    """
    for proj, prefixes in _PROJECT_PREFIXES.items():
        if any(module_name.startswith(p) for p in prefixes):
            return proj
    for proj, singles in _PROJECT_SINGLES.items():
        if module_name in singles:
            return proj
    # Auto-detect: setiap "tm81_<stem>:<name>" → project "tm81_<stem>"
    if ":" in module_name:
        prefix = module_name.split(":")[0]
        if prefix.startswith("tm81_"):
            return prefix
    return None


def detect_project(test_names: list) -> "str | None":
    """Deteksi project aktif dari daftar modul yang ada."""
    for name in test_names:
        proj = module_project(name)
        if proj:
            return proj
    return None
