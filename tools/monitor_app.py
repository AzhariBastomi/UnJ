"""
tools/monitor_app.py — Monitor RAM, CPU (kecepatan), I/O, thread & handle
untuk proses Jig (main.py) beserta seluruh child process-nya
(mis. proses flashing STM32/ESP32 yang dijalankan lewat subprocess).

Cara pakai:
  1. Jalankan main.py dulu (di terminal lain)
  2. python tools/monitor_app.py
     (otomatis cari proses python yang menjalankan main.py, plus child-nya)

  Atau tunjuk PID langsung:
     python tools/monitor_app.py --pid 12345

  Opsi lain:
     --interval 2        # detik antar sample (default 1.0)
     --no-children        # jangan ikutkan child process
     --no-csv             # jangan tulis log CSV
     --no-chart           # jangan buat grafik PNG saat selesai
     --log-dir tools/logs # folder output log (default: tools/logs)

  Hentikan dengan Ctrl+C — akan cetak ringkasan (peak/avg) dan (jika
  matplotlib tersedia) menyimpan grafik RSS & CPU per waktu.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass, field

try:
    import psutil
except ImportError:
    print("Install dulu: pip install psutil --break-system-packages")
    sys.exit(1)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def bytes_to_mb(b: int) -> float:
    return b / 1024 / 1024


def bytes_to_kb(b: float) -> float:
    return b / 1024


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


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


def get_handles(proc: psutil.Process) -> int | str:
    try:
        return proc.num_handles()  # Windows only
    except AttributeError:
        try:
            return len(proc.open_files())
        except Exception:
            return "-"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "-"


# --------------------------------------------------------------------------
# Per-process sample
# --------------------------------------------------------------------------

@dataclass
class ProcSample:
    pid: int
    name: str
    rss_mb: float
    vms_mb: float
    mem_pct: float
    cpu_pct: float
    io_kb_s: float
    threads: int
    handles: object


@dataclass
class History:
    """Rolling history used for the end-of-run summary + chart."""
    t: list = field(default_factory=list)
    rss: list = field(default_factory=list)
    cpu: list = field(default_factory=list)
    io: list = field(default_factory=list)


def sample_proc(proc: psutil.Process, prev_io: dict, dt: float) -> ProcSample | None:
    try:
        with proc.oneshot():
            mem = proc.memory_info()
            cpu = proc.cpu_percent(interval=None)
            mem_pct = proc.memory_percent()
            threads = proc.num_threads()
            name = proc.name()

        io_kb_s = 0.0
        try:
            io = proc.io_counters()
            prev = prev_io.get(proc.pid)
            total_bytes = io.read_bytes + io.write_bytes
            if prev is not None and dt > 0:
                io_kb_s = bytes_to_kb(max(0.0, total_bytes - prev) / dt)
            prev_io[proc.pid] = total_bytes
        except (psutil.AccessDenied, AttributeError, NotImplementedError):
            io_kb_s = -1  # not available on this platform / permission

        return ProcSample(
            pid=proc.pid,
            name=name,
            rss_mb=bytes_to_mb(mem.rss),
            vms_mb=bytes_to_mb(mem.vms),
            mem_pct=mem_pct,
            cpu_pct=cpu,
            io_kb_s=io_kb_s,
            threads=threads,
            handles=get_handles(proc),
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


# --------------------------------------------------------------------------
# Main monitor loop
# --------------------------------------------------------------------------

def monitor(pid: int, interval: float, include_children: bool,
            write_csv: bool, write_chart: bool, log_dir: str) -> None:
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[ERROR] PID {pid} tidak ditemukan.")
        sys.exit(1)

    root_cmd = " ".join(root.cmdline()[:3]) if root.cmdline() else root.name()
    print(f"Monitoring PID {pid} — {root_cmd}")
    if include_children:
        print("(termasuk child process, mis. tool flashing STM32/ESP32)")

    # Warm up cpu_percent() so the first real sample isn't always 0.0
    root.cpu_percent(interval=None)

    csv_writer = None
    csv_file = None
    csv_path = None
    if write_csv:
        os.makedirs(log_dir, exist_ok=True)
        csv_path = os.path.join(log_dir, time.strftime("monitor_%Y%m%d_%H%M%S.csv"))
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "timestamp", "pid", "name", "rss_mb", "vms_mb", "mem_pct",
            "cpu_pct", "io_kb_s", "threads", "handles",
        ])

    history = History()
    prev_io: dict[int, float] = {}
    peak_total_rss = 0.0
    cpu_sum = 0.0
    io_sum = 0.0
    samples = 0
    start_t = time.time()
    last_t = start_t

    try:
        while True:
            now = time.time()
            dt = now - last_t
            last_t = now

            try:
                procs = [root] + (root.children(recursive=True) if include_children else [])
            except psutil.NoSuchProcess:
                print("\n[INFO] Proses utama sudah berhenti.")
                break

            rows: list[ProcSample] = []
            for p in procs:
                s = sample_proc(p, prev_io, dt)
                if s is not None:
                    rows.append(s)

            if not rows:
                print("\n[INFO] Proses sudah berhenti.")
                break

            total_rss = sum(r.rss_mb for r in rows)
            total_cpu = sum(r.cpu_pct for r in rows)
            total_io = sum(r.io_kb_s for r in rows if r.io_kb_s >= 0)
            peak_total_rss = max(peak_total_rss, total_rss)
            cpu_sum += total_cpu
            io_sum += total_io
            samples += 1

            ts = time.strftime("%H:%M:%S")
            history.t.append(now - start_t)
            history.rss.append(total_rss)
            history.cpu.append(total_cpu)
            history.io.append(total_io)

            clear_screen()
            print(f"Monitoring PID {pid} — {root_cmd}")
            print(f"Berjalan: {int(now - start_t)}s  |  Sample #{samples}  |  Ctrl+C untuk berhenti\n")
            print(f"{'PID':>7}  {'Proses':<18}  {'RSS MB':>9}  {'VMS MB':>9}  {'Mem %':>6}  "
                  f"{'CPU %':>7}  {'I/O KB/s':>9}  {'Thr':>4}  {'Handle':>7}")
            print("-" * 92)
            for r in sorted(rows, key=lambda x: -x.rss_mb):
                io_disp = f"{r.io_kb_s:>9.1f}" if r.io_kb_s >= 0 else f"{'n/a':>9}"
                print(f"{r.pid:>7}  {r.name:<18.18}  {r.rss_mb:>9.1f}  {r.vms_mb:>9.1f}  "
                      f"{r.mem_pct:>6.1f}  {r.cpu_pct:>7.1f}  {io_disp}  {r.threads:>4}  {str(r.handles):>7}")
            print("-" * 92)
            print(f"{'TOTAL':>7}  {'(' + str(len(rows)) + ' proses)':<18}  {total_rss:>9.1f}  "
                  f"{'':>9}  {'':>6}  {total_cpu:>7.1f}  {total_io:>9.1f}")

            if csv_writer:
                for r in rows:
                    csv_writer.writerow([ts, r.pid, r.name, f"{r.rss_mb:.1f}", f"{r.vms_mb:.1f}",
                                          f"{r.mem_pct:.1f}", f"{r.cpu_pct:.1f}",
                                          f"{r.io_kb_s:.1f}" if r.io_kb_s >= 0 else "n/a",
                                          r.threads, r.handles])
                csv_file.flush()

            time.sleep(interval)

    except KeyboardInterrupt:
        pass
    finally:
        if csv_file:
            csv_file.close()

        duration = time.time() - start_t
        print(f"\n{'=' * 60}")
        print("RINGKASAN")
        print(f"{'=' * 60}")
        print(f"Durasi         : {duration:.1f} s")
        print(f"Jumlah sample  : {samples}")
        if samples:
            print(f"Peak total RSS : {peak_total_rss:.1f} MB")
            print(f"Avg total CPU  : {cpu_sum / samples:.1f} %")
            print(f"Avg total I/O  : {io_sum / samples:.1f} KB/s")
        if csv_path:
            print(f"Log CSV        : {csv_path}")

        if write_chart and samples >= 2:
            make_chart(history, csv_path)


def make_chart(history: History, csv_path: str | None) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib tidak terpasang — lewati pembuatan grafik. "
              "Install dengan: pip install matplotlib --break-system-packages)")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)

    ax1.plot(history.t, history.rss, color="#2563eb")
    ax1.set_ylabel("RSS total (MB)")
    ax1.set_title("Penggunaan memory & CPU seiring waktu")
    ax1.grid(alpha=0.3)

    ax2.plot(history.t, history.cpu, color="#dc2626")
    ax2.set_ylabel("CPU total (%)")
    ax2.set_xlabel("Waktu (s)")
    ax2.grid(alpha=0.3)

    fig.tight_layout()

    if csv_path:
        chart_path = os.path.splitext(csv_path)[0] + ".png"
    else:
        chart_path = time.strftime("monitor_%Y%m%d_%H%M%S.png")

    fig.savefig(chart_path, dpi=120)
    plt.close(fig)
    print(f"Grafik         : {chart_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor RAM/CPU/I-O proses Jig")
    parser.add_argument("--pid", type=int, default=None, help="PID target (opsional)")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval sampling detik (default 1.0)")
    parser.add_argument("--no-children", action="store_true", help="Jangan ikutkan child process")
    parser.add_argument("--no-csv", action="store_true", help="Jangan tulis log CSV")
    parser.add_argument("--no-chart", action="store_true", help="Jangan buat grafik PNG di akhir")
    parser.add_argument("--log-dir", default=os.path.join(os.path.dirname(__file__), "logs"),
                         help="Folder untuk log CSV & grafik (default: tools/logs)")
    args = parser.parse_args()

    pid = args.pid
    if pid is None:
        pid = find_jig_pid()
        if pid is None:
            print("[ERROR] Proses main.py (Jig) tidak ditemukan. Jalankan dulu, atau pakai --pid.")
            sys.exit(1)

    monitor(
        pid,
        interval=args.interval,
        include_children=not args.no_children,
        write_csv=not args.no_csv,
        write_chart=not args.no_chart,
        log_dir=args.log_dir,
    )


if __name__ == "__main__":
    main()
