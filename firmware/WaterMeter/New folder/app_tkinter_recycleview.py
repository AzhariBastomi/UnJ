"""
Program GUI Tkinter dengan:
1. "Recycle view" -> di Tkinter tidak ada widget bernama RecyclerView (itu istilah Android).
   Yang setara & lazim dipakai adalah Listbox/Treeview yang bisa di-scroll dan
   hanya menampilkan data sebanyak yang terlihat di viewport (widget lain di-reuse
   saat scroll). Di sini dipakai ttk.Treeview + Scrollbar sebagai "recycle view".
2. 4 tombol utama.
3. Setiap tombol membuka popup (Toplevel) tersendiri.
4. Setiap popup punya list (Treeview + scrollbar) dan tombol aksi.
5. Data dummy dibuat banyak (100+ baris) agar list bisa di-scroll.

Cara jalankan:
    python app_tkinter_recycleview.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random

# ---------------------------------------------------------------------------
# DATA DUMMY
# ---------------------------------------------------------------------------

NAMA_DEPAN = ["Andi", "Budi", "Citra", "Dewi", "Eka", "Fajar", "Gita", "Hadi",
              "Indah", "Joko", "Kirana", "Lutfi", "Maya", "Nanda", "Oki",
              "Putri", "Rahmat", "Sari", "Taufik", "Umar"]
NAMA_BELAKANG = ["Saputra", "Wijaya", "Kusuma", "Pratama", "Hidayat",
                  "Santoso", "Setiawan", "Nugroho", "Permadi", "Gunawan"]
KOTA = ["Jakarta", "Bandung", "Surabaya", "Medan", "Semarang", "Makassar",
        "Yogyakarta", "Malang", "Denpasar", "Palembang"]
BARANG = ["Laptop", "Mouse", "Keyboard", "Monitor", "Headset", "Printer",
          "Kabel HDMI", "Flashdisk", "Hardisk Eksternal", "Webcam",
          "Speaker", "Router WiFi", "Power Bank", "Charger", "Tas Laptop"]
STATUS_TRANSAKSI = ["Menunggu Pembayaran", "Dibayar", "Dikirim", "Selesai", "Dibatalkan"]
JENIS_NOTIF = ["Info", "Peringatan", "Promo", "Sistem", "Pengingat"]


def buat_data_pengguna(jumlah=120):
    data = []
    for i in range(1, jumlah + 1):
        nama = f"{random.choice(NAMA_DEPAN)} {random.choice(NAMA_BELAKANG)}"
        kota = random.choice(KOTA)
        umur = random.randint(18, 55)
        data.append((i, nama, umur, kota))
    return data


def buat_data_barang(jumlah=100):
    data = []
    for i in range(1, jumlah + 1):
        nama = f"{random.choice(BARANG)} #{i}"
        stok = random.randint(0, 200)
        harga = random.randint(1, 200) * 1000
        data.append((i, nama, stok, f"Rp {harga:,}".replace(",", ".")))
    return data


def buat_data_transaksi(jumlah=100):
    data = []
    for i in range(1, jumlah + 1):
        kode = f"TRX-{1000 + i}"
        status = random.choice(STATUS_TRANSAKSI)
        total = random.randint(10, 500) * 1000
        data.append((i, kode, status, f"Rp {total:,}".replace(",", ".")))
    return data


def buat_data_notifikasi(jumlah=100):
    data = []
    for i in range(1, jumlah + 1):
        jenis = random.choice(JENIS_NOTIF)
        pesan = f"Notifikasi #{i}: {jenis} - ada aktivitas baru pada sistem"
        data.append((i, jenis, pesan))
    return data


# ---------------------------------------------------------------------------
# KOMPONEN "RECYCLE VIEW" (Treeview + Scrollbar yang bisa dipakai berulang)
# ---------------------------------------------------------------------------

def buat_recycle_view(parent, kolom, data, lebar_kolom=None):
    """
    Membuat widget mirip RecyclerView: list yang bisa discroll dengan cepat
    walau datanya banyak, karena Treeview hanya merender baris yang tampak
    di viewport dan menggunakan ulang (recycle) baris saat discroll.

    kolom      : tuple nama kolom, misal ("id", "nama", "umur", "kota")
    data       : list of tuple, tiap tuple = 1 baris data
    lebar_kolom: dict opsional {nama_kolom: lebar_px}
    """
    frame = ttk.Frame(parent)

    tree = ttk.Treeview(frame, columns=kolom, show="headings", height=15)
    for col in kolom:
        tree.heading(col, text=col.capitalize())
        lebar = 100
        if lebar_kolom and col in lebar_kolom:
            lebar = lebar_kolom[col]
        tree.column(col, width=lebar, anchor="w")

    scrollbar_y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar_y.set)

    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar_y.grid(row=0, column=1, sticky="ns")

    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    for baris in data:
        tree.insert("", "end", values=baris)

    return frame, tree


# ---------------------------------------------------------------------------
# POPUP GENERIK: list (recycle view) + tombol aksi
# ---------------------------------------------------------------------------

def buka_popup(root, judul, kolom, data, lebar_kolom, teks_tombol, aksi_tombol):
    """
    Membuat 1 window popup (Toplevel) berisi:
      - Judul
      - List (Treeview + scrollbar) dengan data dummy
      - Tombol aksi yang memproses item yang sedang dipilih di list
    """
    popup = tk.Toplevel(root)
    popup.title(judul)
    popup.geometry("480x420")
    popup.transient(root)
    popup.grab_set()  # jadikan modal terhadap window utama

    label_judul = ttk.Label(popup, text=judul, font=("Segoe UI", 13, "bold"))
    label_judul.pack(pady=(12, 6))

    label_info = ttk.Label(popup, text=f"Total data dummy: {len(data)} baris (scroll ke bawah)")
    label_info.pack(pady=(0, 8))

    frame_list, tree = buat_recycle_view(popup, kolom, data, lebar_kolom)
    frame_list.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    frame_tombol = ttk.Frame(popup)
    frame_tombol.pack(fill="x", padx=12, pady=(0, 12))

    def on_klik_aksi():
        pilihan = tree.selection()
        if not pilihan:
            messagebox.showwarning("Belum ada pilihan", "Pilih salah satu baris di list terlebih dahulu.",
                                    parent=popup)
            return
        nilai = tree.item(pilihan[0], "values")
        aksi_tombol(tree, pilihan[0], nilai)

    btn_aksi = ttk.Button(frame_tombol, text=teks_tombol, command=on_klik_aksi)
    btn_aksi.pack(side="left")

    btn_tutup = ttk.Button(frame_tombol, text="Tutup", command=popup.destroy)
    btn_tutup.pack(side="right")

    return popup


# ---------------------------------------------------------------------------
# AKSI TOMBOL DI SETIAP POPUP
# ---------------------------------------------------------------------------

def aksi_hapus_baris(tree, item_id, nilai):
    tree.delete(item_id)


def aksi_lihat_detail(tree, item_id, nilai):
    messagebox.showinfo("Detail", "Data terpilih:\n" + " | ".join(str(v) for v in nilai))


def aksi_tandai_selesai(tree, item_id, nilai):
    kolom = tree["columns"]
    idx_status = kolom.index("status") if "status" in kolom else None
    baru = list(nilai)
    if idx_status is not None:
        baru[idx_status] = "Selesai"
        tree.item(item_id, values=baru)
    else:
        messagebox.showinfo("Info", "Ditandai selesai:\n" + " | ".join(str(v) for v in nilai))


def aksi_tandai_dibaca(tree, item_id, nilai):
    tree.item(item_id, tags=("dibaca",))
    tree.tag_configure("dibaca", foreground="grey")


# ---------------------------------------------------------------------------
# APLIKASI UTAMA
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        root.title("Contoh Recycle View - Tkinter")
        root.geometry("640x520")

        ttk.Label(root, text="Daftar Pengguna (Recycle View Utama)",
                  font=("Segoe UI", 14, "bold")).pack(pady=(14, 6))

        self.data_pengguna = buat_data_pengguna(120)

        frame_list, self.tree_utama = buat_recycle_view(
            root,
            kolom=("id", "nama", "umur", "kota"),
            data=self.data_pengguna,
            lebar_kolom={"id": 50, "nama": 180, "umur": 60, "kota": 120},
        )
        frame_list.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        ttk.Label(root, text="Pilih salah satu tombol di bawah untuk membuka popup:",
                  font=("Segoe UI", 10)).pack(pady=(0, 6))

        frame_tombol = ttk.Frame(root)
        frame_tombol.pack(pady=(0, 16))

        ttk.Button(frame_tombol, text="1. Daftar Barang",
                   command=self.buka_popup_barang, width=20).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(frame_tombol, text="2. Daftar Transaksi",
                   command=self.buka_popup_transaksi, width=20).grid(row=0, column=1, padx=6, pady=6)
        ttk.Button(frame_tombol, text="3. Daftar Notifikasi",
                   command=self.buka_popup_notifikasi, width=20).grid(row=1, column=0, padx=6, pady=6)
        ttk.Button(frame_tombol, text="4. Daftar Pengguna",
                   command=self.buka_popup_pengguna, width=20).grid(row=1, column=1, padx=6, pady=6)

    # --- Tombol 1: Barang ------------------------------------------------
    def buka_popup_barang(self):
        data = buat_data_barang(100)
        buka_popup(
            self.root,
            judul="Popup 1 - Daftar Barang",
            kolom=("id", "nama", "stok", "harga"),
            data=data,
            lebar_kolom={"id": 40, "nama": 180, "stok": 60, "harga": 100},
            teks_tombol="Hapus Barang Terpilih",
            aksi_tombol=aksi_hapus_baris,
        )

    # --- Tombol 2: Transaksi ----------------------------------------------
    def buka_popup_transaksi(self):
        data = buat_data_transaksi(100)
        buka_popup(
            self.root,
            judul="Popup 2 - Daftar Transaksi",
            kolom=("id", "kode", "status", "total"),
            data=data,
            lebar_kolom={"id": 40, "kode": 100, "status": 140, "total": 100},
            teks_tombol="Tandai Selesai",
            aksi_tombol=aksi_tandai_selesai,
        )

    # --- Tombol 3: Notifikasi ----------------------------------------------
    def buka_popup_notifikasi(self):
        data = buat_data_notifikasi(100)
        buka_popup(
            self.root,
            judul="Popup 3 - Daftar Notifikasi",
            kolom=("id", "jenis", "pesan"),
            data=data,
            lebar_kolom={"id": 40, "jenis": 90, "pesan": 300},
            teks_tombol="Tandai Dibaca",
            aksi_tombol=aksi_tandai_dibaca,
        )

    # --- Tombol 4: Pengguna (lihat detail) ---------------------------------
    def buka_popup_pengguna(self):
        data = buat_data_pengguna(120)
        buka_popup(
            self.root,
            judul="Popup 4 - Daftar Pengguna",
            kolom=("id", "nama", "umur", "kota"),
            data=data,
            lebar_kolom={"id": 40, "nama": 180, "umur": 60, "kota": 120},
            teks_tombol="Lihat Detail",
            aksi_tombol=aksi_lihat_detail,
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
