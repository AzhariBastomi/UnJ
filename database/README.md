# Setup Database PostgreSQL untuk Universal-JIG

Folder ini isinya setup PostgreSQL lokal via Docker untuk backend `server/app.py`
(dashboard + REST API hasil test). **PostgreSQL sekarang wajib** — backend
SQLite sudah dihapus dari `server/db.py`. Server tidak akan bisa jalan kalau
Postgres belum menyala.

## 1. Syarat

- Docker Desktop sudah terinstall dan berjalan (Windows: WSL2 backend).

## 2. Jalankan Postgres

Dari folder ini:

```powershell
cd database
docker compose up -d
```

Ini akan menyalakan:
- **jig-postgres** — PostgreSQL 16 (alpine) di `localhost:5432` (user: `jig`, password: `jig`, db: `jig`)
- **jig-adminer** — UI web opsional untuk lihat isi tabel: http://localhost:8081
  (System: PostgreSQL, Server: `jig-postgres`, Username: `jig`, Password: `jig`, Database: `jig`)

Cek statusnya:

```powershell
docker compose ps
```

Matikan (data tetap tersimpan di volume `jig_pgdata`):

```powershell
docker compose down
```

Hapus total termasuk datanya:

```powershell
docker compose down -v
```

## 3. Arahkan server Jig ke Postgres

Install dependency server (sekali saja):

```powershell
pip install -r server\requirements.txt
```

`JIG_DB_URL` opsional — kalau tidak diset, `server/db.py` otomatis pakai
default yang cocok dengan `docker-compose.yml` di atas
(`postgresql://jig:jig@localhost:5432/jig`). Set env var ini hanya kalau
host/kredensial Postgres-nya beda dari default:

```powershell
$env:JIG_DB_URL = "postgresql://jig:jig@localhost:5432/jig"
python server\app.py
```

**Postgres (`docker compose up -d`) harus sudah jalan sebelum `server/app.py`
di-start** — tidak ada lagi fallback ke SQLite.

Tabel (`sessions`, `test_results`) dibuat otomatis saat server pertama kali
jalan (lihat `schema.sql` di folder ini kalau mau buat manual / referensi).

## 4. Enable pengiriman hasil test dari Universal-JIG

Di `config/config.json`, set:

```json
"database": {
    "enabled": 1,
    "server_url": "http://localhost:5001"
}
```

Setelah itu, setiap kali Start ditekan di Universal-JIG:
- setiap test yang selesai (OK/NG) otomatis dikirim ke server dengan
  station, nama test, command, hasil, durasi, dan jam — lewat
  `LocalServerUploader.upload()` yang sudah terpasang di
  `controllers/test_controller.py`.
- saat semua test dalam 1 SN selesai, sesi otomatis ditutup dengan status
  `"OK"` (semua PASS) atau `"NG"` (ada yang gagal) — logika ini reuse dari
  fitur cek-NG yang sudah ada di `app/_run_mixin.py` (`_on_seq_done`).

## 5. Lihat dashboard

Buka http://localhost:5001/ — akan tampil:
- **Daftar station** -> klik salah satu
- **Daftar SN** yang pernah ditest di station itu -> klik salah satu
- **Daftar test** (dengan hasil, durasi, jam) untuk SN tsb, dikelompokkan per sesi
