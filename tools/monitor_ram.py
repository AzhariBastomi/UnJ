"""
tools/monitor_ram.py — Monitor RAM & CPU penggunaan proses Jig (main.py)

Cara pakai:
  1. Jalankan main.py dulu
  2. Di terminal lain: python tools/monitor_ram.py
     (otomatis cari proses python yang menjalankan main.py)

  Atau tunjuk PID langsung:
     python tools/monitor_ram.py --pid 12345

  Hentikan dengan Ctrl+C — akan cetak ringkasan peak usage.
"""

import argparse
import os
import sys
import time

try:
    import psutil
except ImportError:
    print("Install dulu: pip install psutil --break-system-packages")
    sys.exit(1)


def find_jig_pid() -> int | None:
    """Cari PID proses Python yang menjalankan main.py (Jig)."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if any("main.py" in c for c in cmd):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def bytes_to_mb(b: int) -> float:
    return b / 1024 / 1024


def monitor(pid: int, interval: float = 1.0):
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[ERROR] PID {pid} tidak ditemukan.")
        sys.exit(1)

    print(f"Monitoring PID {pid} — {' '.join(proc.cmdline()[:3])}")
    print(f"{'Waktu':>8}  {'RSS (MB)':>10}  {'VMS (MB)':>10}  {'CPU %':>7}  {'Threads':>8}")
    print("-" * 55)

    peak_rss = 0.0
    samples = 0

    try:
        while True:
            try:
                mem  = proc.memory_info()
                cpu  = proc.cpu_percent(interval=None)
                thrd = proc.num_threads()
                rss  = bytes_to_mb(mem.rss)
                vms  = bytes_to_mb(mem.vms)

                peak_rss = max(peak_rss, rss)
                samples += 1

                ts = time.strftime("%H:%M:%S")
                print(f"{ts:>8}  {rss:>10.1f}  {vms:>10.1f}  {cpu:>7.1f}  {thrd:>8}")

            except psutil.NoSuchProcess:
                print("\n[INFO] Proses sudah berhenti.")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{'─'*55}")
        print(f"Peak RSS : {peak_rss:.1f} MB")
        print(f"Samples  : {samples}")
        print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Monitor RAM/CPU proses Jig")
    parser.add_argument("--pid",      type=int,   default=None, help="PID target (opsional)")
    parser.add_argument("--interval", type=float, default=1.0,  help="Interval sampling detik (default 1.0)")
    args = parser.parse_args()

    pid = args.pid
    if pid is None:
        pid = find_jig_pid()
        if pid is None:
            print("[ERROR] Proses main.py (Jig) tidak ditemukan. Jalankan dulu, atau pakai --pid.")
            sys.exit(1)

    monitor(pid, interval=args.interval)


if __name__ == "__main__":
    main()
