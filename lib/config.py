"""
config.py — Application-wide configuration and display settings.
"""

# Display presets (width, height) in pixels
DISPLAY_PRESETS = {
    "3 inch  (480x320)":  (480, 320),
    "5 inch  (800x480)":  (800, 480),
    "7 inch  (1024x600)": (1024, 600),
    "Custom":             (800, 480),
}

DEFAULT_PRESET = "5 inch  (800x480)"

FONT_SCALE = {
    "3 inch  (480x320)":  0.75,
    "5 inch  (800x480)":  1.0,
    "7 inch  (1024x600)": 1.3,
    "Custom":             1.0,
}

BASE_FONTS = {
    "title":   14,
    "label":   11,
    "button":  10,
    "small":   9,
}

SERIAL_MOCK_DELAY = 1.5


# ── Dark mode detection ────────────────────────────────────────────────────

def _detect_dark_mode() -> bool:
    import sys
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
        except Exception:
            return False
    # Linux: gsettings (GNOME)
    try:
        import subprocess
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=1)
        if "dark" in r.stdout.lower():
            return True
    except Exception:
        pass
    # macOS
    try:
        import subprocess
        r = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=1)
        if "dark" in r.stdout.lower():
            return True
    except Exception:
        pass
    return False


_DARK = {
    "bg":        "#0F0F1A",
    "surface":   "#1A1A2E",
    "card":      "#22223A",
    "card_hov":  "#2C2C44",
    "border":    "#33334A",
    "header_bg": "#1A1A2E",
    "header_fg": "#E8E8F0",
    "text":      "#E8E8F0",
    "sub":       "#8888AA",
    "ok":        "#3DD68C",
    "warn":      "#FFB347",
    "ng":        "#FF6B6B",
    "running":   "#7B68EE",
    "pending":   "#555570",
    "bar_bg":    "#2E2E44",
    # kept for compat
    "row_even":  "#22223A",
    "row_odd":   "#1E1E34",
}

_LIGHT = {
    "bg":        "#f0f4f8",
    "surface":   "#e4eaf0",
    "card":      "#ffffff",
    "card_hov":  "#eef4ff",
    "border":    "#d0d8e0",
    "header_bg": "#2c3e50",
    "header_fg": "#ffffff",
    "text":      "#1a1a2e",
    "sub":       "#777799",
    "ok":        "#2e7d32",
    "warn":      "#e67e22",
    "ng":        "#c0392b",
    "running":   "#2980b9",
    "pending":   "#9999aa",
    "bar_bg":    "#dde4ec",
    "row_even":  "#ffffff",
    "row_odd":   "#f5f8fc",
}

IS_DARK = _detect_dark_mode()
COLORS  = _DARK if IS_DARK else _LIGHT


# ══════════════════════════════════════════════════════════════════════════════
# Standalone check — python config.py
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Theme     : {'DARK' if IS_DARK else 'LIGHT'}")
    print(f"Preset    : {DEFAULT_PRESET}")
    print(f"Font scale: {FONT_SCALE[DEFAULT_PRESET]}")
    print()
    print("Colors:")
    for k, v in COLORS.items():
        print(f"  {k:<12} {v}")
