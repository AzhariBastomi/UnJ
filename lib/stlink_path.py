"""
stlink_path.py — Cari tool flash STM32 sesuai OS.

Windows : STM32_Programmer_CLI.exe (STM32CubeProgrammer)
Linux   : st-flash
"""

import os
import sys
import shutil

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

IS_WINDOWS = sys.platform == "win32"

# Lokasi kandidat STM32_Programmer_CLI.exe di Windows
_STM32PROG_CANDIDATES = [
    r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
    r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
]

# Lokasi kandidat st-flash di Linux
_STFLASH_CANDIDATES = [
    "/usr/bin/st-flash",
    "/usr/local/bin/st-flash",
    os.path.join(_ROOT, "tools", "stlink", "bin", "st-flash"),
]


def find_flash_tool() -> str:
    """
    Return path tool flash yang valid sesuai OS.
    Raise FileNotFoundError jika tidak ditemukan.
    """
    if IS_WINDOWS:
        which = shutil.which("STM32_Programmer_CLI")
        if which:
            return which
        for path in _STM32PROG_CANDIDATES:
            if os.path.isfile(path):
                return path
        raise FileNotFoundError(
            "STM32_Programmer_CLI.exe tidak ditemukan.\n"
            "Install STM32CubeProgrammer dari:\n"
            "https://www.st.com/en/development-tools/stm32cubeprog.html"
        )
    else:
        which = shutil.which("st-flash")
        if which:
            return which
        for path in _STFLASH_CANDIDATES:
            if os.path.isfile(path):
                return path
        raise FileNotFoundError(
            "st-flash tidak ditemukan.\n"
            "Install dengan: sudo apt install stlink-tools"
        )

