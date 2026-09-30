"""
flasher.py — Library untuk flashing firmware ke berbagai target MCU.

Supported targets:
  - STM32     : via st-flash (.bin)

Semua flasher mewarisi FlasherBase dan mengekspos:
  flash(firmware_path) -> FlashResult

"""

import subprocess
import shutil
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class FlashResult:
    ok:       bool
    message:  str
    stdout:   str = ""
    stderr:   str = ""

    def __str__(self):
        status = "OK" if self.ok else "NG"
        return f"[{status}] {self.message}"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class FlasherBase:
    """Base class semua flasher. Override flash() di subclass."""

    def flash(self, firmware_path: str,
              progress_cb: Optional[Callable[[int], None]] = None) -> FlashResult:
        raise NotImplementedError

    def _check_file(self, path: str) -> Optional[str]:
        """Return error string jika file tidak ditemukan, None jika OK."""
        if not os.path.isfile(path):
            return f"File tidak ditemukan: {path}"
        return None

    def _check_tool(self, tool: str) -> Optional[str]:
        """Return error string jika tool tidak ada di PATH."""
        if shutil.which(tool) is None:
            return f"Tool '{tool}' tidak ditemukan di PATH"
        return None

    # ---- pola progress dari masing-masing tool -------------------------
    _RE_ATTEMPT = re.compile(r"Attempting to write\s+(\d+)")
    _RE_ERASED  = re.compile(r"erased\s*\(size:\s*(0x[0-9a-fA-F]+|\d+)\)")
    _RE_PAGES   = re.compile(r"(\d+)\s*/\s*(\d+)\s+pages written")
    _RE_PCT     = re.compile(r"(\d{1,3})\s*%")

    def _run(self, cmd: list[str],
             progress_cb: Optional[Callable[[int], None]] = None,
             success_hint: str = "") -> FlashResult:
        """
        Jalankan command, baca output stream (bukan tunggu selesai) dan
        laporkan progress secara real-time.

        Di Linux/macOS proses dijalankan lewat PTY supaya tool yang
        block-buffered (st-flash) tetap mengeluarkan progress per baris.

        Mapping st-flash:
          "Attempting to write N bytes"   -> tahu total byte  -> 1%
          "-> Flash page at 0x.. erased"  -> fase erase       -> 1-8%
          "  N/M  pages written"          -> fase write       -> 8-96%
          "Starting verification"         -> fase verify      -> 97%
          "Flash written and verified!"   -> 99%  (100% saat exit 0)

        Mapping STM32_Programmer_CLI:
          "Download in Progress"          -> 5%
          "NN%"                           -> download 5-70% / verify 70-99%
          "Download verified"             -> 99%

        Mapping avrdude: hitung karakter '#'.
        """
        _P_NONE, _P_ERASE, _P_WRITE, _P_CLI_DL, _P_CLI_VF = 0, 1, 2, 3, 4

        st = {"phase": _P_NONE, "total_bytes": 0, "page_size": 0,
              "erased": 0, "hash": 0, "last": -1}

        # Set JIG_FLASH_DEBUG=1 untuk melihat tiap baris yang terbaca dan tiap
        # perubahan persentase, berikut waktunya. Berguna untuk memastikan
        # output tool memang mengalir (bukan menumpuk di akhir).
        _dbg = bool(os.environ.get("JIG_FLASH_DEBUG"))
        _t0  = time.monotonic()

        def _log_dbg(tag, text):
            if _dbg:
                print(f"[flash {time.monotonic() - _t0:6.2f}s] {tag} {text}",
                      file=sys.stderr, flush=True)

        _log_dbg("CMD ", " ".join(cmd))
        _log_dbg("CB  ", "progress_cb TERPASANG" if progress_cb
                 else "progress_cb None -> progress bar TIDAK akan bergerak")

        def emit(pct):
            """Kirim ke UI, monotonic naik, dibatasi 99 (100 hanya saat sukses)."""
            pct = max(0, min(int(pct), 99))
            if progress_cb and pct > st["last"]:
                st["last"] = pct
                _log_dbg("PCT ", f"{pct}%")
                progress_cb(pct)

        def total_pages():
            if not st["total_bytes"]:
                return 0
            ps = st["page_size"] or 2048
            return max(1, -(-st["total_bytes"] // ps))

        def handle(line: str):
            # ---------------- st-flash (Linux) ----------------
            m = self._RE_ATTEMPT.search(line)
            if m:
                st["total_bytes"] = int(m.group(1))
                st["phase"] = _P_ERASE
                emit(1)
                return

            if "erased" in line and "page" in line.lower():
                m = self._RE_ERASED.search(line)
                if m and not st["page_size"]:
                    st["page_size"] = int(m.group(1), 0)
                st["erased"] += 1
                tp = total_pages()
                if tp:
                    # Erase biasanya jauh lebih cepat dari write, jadi porsinya
                    # kecil saja (1-8%) supaya bar tidak melompat lalu diam.
                    emit(1 + 7 * st["erased"] / tp)
                return

            m = self._RE_PAGES.search(line)
            if m:
                done  = int(m.group(1))
                total = max(int(m.group(2)), 1)
                st["phase"] = _P_WRITE
                # "  1/13  pages written" -> penggerak utama progress bar.
                emit(8 + 88 * done / total)
                return

            low = line.lower()
            if "verification" in low:
                emit(97)
                return
            if "written and verified" in low:
                emit(99)
                return

            # ------------- STM32_Programmer_CLI (Windows) -------------
            if "Download in Progress" in line:
                st["phase"] = _P_CLI_DL
                emit(5)
                return
            if "Read progress" in line or "Verifying" in line:
                st["phase"] = _P_CLI_VF
                emit(70)
                return
            if "Download verified" in line or "File download complete" in line:
                emit(99)
                return

            m = self._RE_PCT.search(line)
            if m:
                raw = int(m.group(1))
                if st["phase"] == _P_CLI_DL:
                    emit(5 + raw * 0.65)
                elif st["phase"] == _P_CLI_VF:
                    emit(70 + raw * 0.29)
                else:
                    emit(raw)
                return

            # ---------------- avrdude ----------------
            n = line.count("#")
            if n:
                st["hash"] += n
                emit(st["hash"] / 50 * 100)

        master_fd = None
        try:
            if os.name == "posix":
                import pty
                master_fd, slave_fd = pty.openpty()
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                )
                os.close(slave_fd)

                def read_chunk():
                    try:
                        return os.read(master_fd, 1024)
                    except OSError:      # EIO = child menutup pty
                        return b""
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,           # unbuffered
                )

                def read_chunk():
                    return proc.stdout.read(64)

            out_lines: list[str] = []
            buf = b""

            while True:
                chunk = read_chunk()
                if not chunk:
                    break
                buf += chunk

                # tool progress pakai \r (tanpa \n) — split pada keduanya
                parts = re.split(rb"[\r\n]", buf)
                buf   = parts[-1]        # potongan terakhir belum tentu lengkap

                for raw in parts[:-1]:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    out_lines.append(line)
                    _log_dbg("LINE", repr(line))
                    handle(line)

            # sisa buffer (baris terakhir tanpa newline)
            tail = buf.decode("utf-8", errors="replace").strip()
            if tail:
                out_lines.append(tail)
                _log_dbg("TAIL", repr(tail))
                handle(tail)

            proc.wait()
            full_out = "\n".join(out_lines)
            _log_dbg("EXIT", f"returncode={proc.returncode}, "
                             f"{len(out_lines)} baris terbaca")

            if proc.returncode == 0:
                if progress_cb:
                    progress_cb(100)
                return FlashResult(ok=True, message="Flash berhasil", stdout=full_out)

            return FlashResult(
                ok=False,
                message=self._extract_error(full_out, proc.returncode),
                stdout=full_out,
            )

        except FileNotFoundError as e:
            return FlashResult(ok=False, message=str(e))
        except Exception as e:
            return FlashResult(ok=False, message=f"Error: {e}")
        finally:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass

    def _extract_error(self, stdout: str, returncode: int) -> str:
        """
        Cari baris error yang relevan dari output tool.
        Prioritas: baris yang mengandung kata kunci error umum.
        """
        import re

        # Keyword error yang dicari, urutan prioritas
        ERROR_KEYWORDS = [
            "Error",
            "error",
            "FAILED",
            "failed",
            "No ST-LINK",
            "No target",
            "Unable",
            "Cannot",
            "could not",
            "timeout",
            "Timeout",
            "not found",
            "invalid",
        ]

        lines = [l.strip() for l in stdout.splitlines() if l.strip()]

        for kw in ERROR_KEYWORDS:
            for line in lines:
                if kw in line:
                    # Bersihkan prefix berulang seperti "Error: Error:"
                    clean = re.sub(r"^(Error\s*:\s*)+", "Error: ", line)
                    return clean

        # Fallback: ambil baris terakhir yang tidak kosong
        if lines:
            return f"exit {returncode}: {lines[-1]}"

        return f"Flash gagal (exit {returncode})"



# ---------------------------------------------------------------------------
# STM32 (Windows: STM32_Programmer_CLI | Linux: st-flash)
# ---------------------------------------------------------------------------

@dataclass
class Stm32Config:
    stlink_bin:  str   = ""              # kosong = auto-detect via stlink_path
    reset:       bool  = True            # Reset setelah flash
    reset_mode:  str   = "software"      # "software" -> connect mode=NORMAL reset=SWrst (default
                                          # lama, tidak berubah) atau "hardware" -> connect mode=UR
                                          # reset=HWrst (connect-under-reset, reset fisik via
                                          # SWD/JTAG -- setara opsi "Hardware reset" di
                                          # STM32CubeProgrammer GUI). Hanya berlaku di Windows
                                          # (STM32_Programmer_CLI); di Linux (st-flash) tidak ada
                                          # pembedaan ini.
    flash_addr:  str   = "0x08000000"    # Alamat flash STM32
    format:      str   = "binary"        # binary / ihex
    extra_flags: list  = field(default_factory=list)


class Stm32Flasher(FlasherBase):
    """
    Flash STM32.
    Windows : STM32_Programmer_CLI.exe -c port=SWD -w <file> <addr> -v -rst
    Linux   : st-flash write <file> <addr>
    Tool di-detect otomatis via stlink_path.find_flash_tool().
    """

    def __init__(self, config: Stm32Config = None):
        self.cfg = config or Stm32Config()

    def _resolve_tool(self) -> tuple:
        """Return (tool_path, is_windows). Raise FileNotFoundError jika tidak ada."""
        import sys as _sys
        tool = self.cfg.stlink_bin
        if not tool:
            from stlink_path import find_flash_tool
            tool = find_flash_tool()
        return tool, _sys.platform == "win32"

    def flash(self, firmware_path: str,
              progress_cb: Optional[Callable[[int], None]] = None) -> FlashResult:

        if err := self._check_file(firmware_path):
            return FlashResult(ok=False, message=err)

        try:
            tool, is_windows = self._resolve_tool()
        except FileNotFoundError as e:
            return FlashResult(ok=False, message=str(e))

        ext = os.path.splitext(firmware_path)[1].lower()

        if is_windows:
            # reset_mode dipilih lewat parameter connect "-c ... reset=<mode>",
            # BUKAN flag -rst/-hardRst terpisah -- ini yang menentukan gimana
            # STM32_Programmer_CLI konek ke chip:
            #   software -> mode=NORMAL reset=SWrst  (default lama, tidak berubah)
            #   hardware -> mode=UR     reset=HWrst  (connect-under-reset, reset fisik)
            # Contoh persis dari STM32CubeProgrammer:
            #   -c port=SWD freq=4000 mode=NORMAL ap=0 reset=SWrst
            #   -c port=SWD freq=4000 mode=UR ap=0 reset=HWrst
            if self.cfg.reset_mode == "hardware":
                connect_params = ["port=SWD", "freq=4000", "mode=UR", "ap=0", "reset=HWrst"]
            else:
                connect_params = ["port=SWD", "freq=4000", "mode=NORMAL", "ap=0", "reset=SWrst"]
            # Tiap param jadi argv terpisah (bukan digabung 1 string) -- _run()
            # jalankan subprocess pakai list argv langsung, tanpa shell yang
            # biasa mem-tokenize spasi seperti waktu diketik manual di terminal.
            cmd = [
                tool,
                "-c", *connect_params,
                "-w", firmware_path, self.cfg.flash_addr,
                "-v",
                *self.cfg.extra_flags,
            ]
            if self.cfg.reset:
                cmd.append("-rst")   # reset/jalankan app setelah selesai flash
            return self._run(cmd, progress_cb)

        # Linux: st-flash
        if ext == ".hex" or self.cfg.format == "ihex":
            cmd = [
                tool,
                "--format", "ihex",
                *self.cfg.extra_flags,
                "write",
                firmware_path,
            ]
        else:
            cmd = [
                tool,
                *self.cfg.extra_flags,
                "write",
                firmware_path,
                self.cfg.flash_addr,
            ]

        result = self._run(cmd, progress_cb)

        if result.ok and self.cfg.reset:
            subprocess.run([tool, "reset"], capture_output=True)

        return result


# ---------------------------------------------------------------------------
# Reset device (tanpa flashing) — dipakai standalone, mis. verifikasi config
# tersimpan di EEPROM/Flash bertahan setelah device benar-benar direset via
# debugger (bukan cuma soft-reboot lewat command serial).
# ---------------------------------------------------------------------------

def reset_device() -> FlashResult:
    """
    Reset device via ST-Link, TANPA menulis firmware apa pun.

    Windows : STM32_Programmer_CLI.exe -c port=SWD -rst
    Linux   : st-flash reset

    Tool di-detect otomatis via stlink_path.find_flash_tool() — sama seperti
    yang dipakai Stm32Flasher untuk flashing.
    """
    try:
        from stlink_path import find_flash_tool
        tool = find_flash_tool()
    except FileNotFoundError as e:
        return FlashResult(ok=False, message=str(e))

    if sys.platform == "win32":
        cmd = [tool, "-c", "port=SWD", "-rst"]
    else:
        cmd = [tool, "reset"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as e:
        return FlashResult(ok=False, message=f"Reset gagal: {e}")

    if proc.returncode == 0:
        return FlashResult(ok=True, message="Reset device berhasil",
                            stdout=proc.stdout or "", stderr=proc.stderr or "")

    err = (proc.stderr or proc.stdout or "").strip()
    return FlashResult(
        ok=False,
        message=f"Reset device gagal (exit {proc.returncode}): {err}",
        stdout=proc.stdout or "", stderr=proc.stderr or "",
    )
