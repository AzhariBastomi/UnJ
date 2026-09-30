# Suite test dalam format Gherkin (TM81, BEXA, Flash)

Urutan/isi test ditulis pakai kalimat biasa (bahasa Indonesia) di file
`.feature`, supaya bisa dibaca/diedit non-programmer tanpa sentuh Python.
Tiap suite file-nya nempel di folder config device-nya sendiri — TIDAK ada
lagi folder `features/` terpusat:

```
commands/tm81/config/   tm81_test.feature, tm81_join.feature, tm81_join2.feature,
                         tm81_sesion_bl.feature, tm81_ota.feature, tm81_ota2.feature,
                         tm81_ota_bl.feature  (+ _steps.json, commissioning.json)
commands/bexa/config/   bexa_test.feature  (+ _steps.json)
commands/flash/config/  bexa.feature + bexa.json, tm81.feature + tm81.json
commands/voltage/config/ voltage.feature  (+ _steps.json)
```

## Cakupan & status tiap suite

| Suite | File | Butuh JSON? |
|---|---|---|
| TM81 (semua step utama) | `commands/tm81/config/tm81_test.feature` | Tidak |
| TM81 Join / Join 2 / Session BL | `commands/tm81/config/tm81_{join,join2,sesion_bl}.feature` | Tidak |
| TM81 OTA / OTA v2 / OTA Bootloader | `commands/tm81/config/tm81_ota*.feature` | **Ya, JSON kecil** (`fw_version` + dialog "OTA Settings") |
| BEXA | `commands/bexa/config/bexa_test.feature` | Tidak |
| Flash (TM81 / BEXA) | `commands/flash/config/{tm81,bexa}.feature` | **Ya, JSON penuh** (dialog "Flash Settings" edit `file`/`address` langsung di JSON) |
| Voltage (1.8V / 3.3V / 5V) | `commands/voltage/config/voltage.feature` | Tidak |

Voltage beda modelnya dari yang lain: tiap titik ukur (1.8V/3.3V/5V) tetap
muncul sebagai BARIS SENDIRI-SENDIRI di Add Test (bukan digabung jadi satu
suite), tapi daftarnya sekarang dari SATU `voltage.feature` (baris = titik
mana yang aktif & urutannya) + SATU `_steps.json` (definisi label/command/
description tiap titik) — bukan lagi 1 file JSON per titik. Nambah titik
ukur baru = tambah definisinya di `_steps.json`, lalu tambah satu baris di
`voltage.feature`.

Flash tidak bisa jadi murni `.feature` karena tombol "⚙ Flash Settings"
baca-tulis field `file`/`address` LANGSUNG ke `tests[]` di JSON itu sendiri
(sama alasannya dengan OTA, tapi Flash butuh JSON PENUH karena semua
region-nya memang cuma dikonfig lewat dialog itu, bukan step library).

## Tiga cara suite dibaca (otomatis dipilih, tidak perlu setting manual)

1. **Lean (1 file)** — HANYA `.feature`, tanpa JSON sama sekali. Isi tiap
   step diambil dari `_steps.json` (library step per device) lewat
   pencocokan NAMA atau LABEL step. Dipakai: semua suite TM81 non-OTA,
   BEXA, dan Voltage (walau modelnya sedikit beda -- tiap baris jadi baris
   Add Test sendiri-sendiri, bukan digabung jadi satu suite, lihat tabel di
   bawah).
2. **Lean + JSON kecil (2 file)** — JSON-nya cuma berisi pengaturan yang
   memang perlu dibaca/ditulis dialog GUI (mis. `fw_version`), TANPA daftar
   step (`"steps"`/`"tests"`). Daftar/urutan step 100% dari `.feature` di
   folder yang sama. Dipakai: TM81 OTA/OTA v2/OTA Bootloader.
3. **Replace-in-place (JSON + .feature terpisah)** — JSON tetap sumber data
   penuh (dipakai dialog settings-nya), `.feature` cuma override
   urutan/seleksi. Kalimatnya dicocokkan LANGSUNG ke `name`/`label` tiap
   entry di JSON -- tidak ada file map terpisah. Dipakai: Flash.

Ketiganya sepenuhnya transparan ke GUI — tombol **+ Add Test** tetap
menampilkan SATU baris per suite seperti biasa, prefix/nama modul tidak
berubah, jadi test yang sudah tersimpan di `tasks.json` tetap jalan.

## Cara non-programmer ubah alur test

Edit langsung file `.feature`-nya, contoh `commands/tm81/config/tm81_join.feature`:

```gherkin
Feature: TM81 Join

  Scenario: TM81 Join
    Given user_reset_config: Reset konfigurasi user ke default
    Then user_get_config: Baca konfigurasi user setelah reset — cek Activation harus Deactivated
      | Activation | Deactivated |
    And rtc_set: Sinkronisasi RTC device ke waktu PC
    ...
```

- Ubah urutan baris = ubah urutan eksekusi di list test app.
- Hapus baris, atau kasih `#` di depan baris = step itu dilewati.
- Tiap baris pakai NAMA STEP atau LABEL-nya (lihat `_steps.json` device
  terkait) — kalau labelnya dipakai lebih dari satu step (mis.
  `user_get_config` dan `user_get_config_post_set` sama-sama "Get User
  Config"), wajib tulis nama step-nya langsung, bukan label, supaya jelas.
  Kalau ada kalimat yang tidak dikenali, step itu tetap muncul di list tapi
  sebagai baris NG dengan pesan error — bukan diam-diam hilang/salah pilih.

### Konvensi per baris

- `nama_step` atau `Label Step` — pakai definisi step apa adanya dari
  `_steps.json`.
- `nama_step: teks deskripsi` — override `description` yang tampil di UI.
- `varian_step => nama_baru: deskripsi` — pakai definisi `varian_step` dari
  library, tapi entry hasil akhirnya dipakai dengan nama `nama_baru` (setara
  `"use"+"name"` di suite JSON lama). Contoh dipakai di `tm81_ota.feature`:
  `write_fw_v1 => write_fw: ...`.
- Data Table `| key | value |` nempel di bawah step:
  - key `tunggu`/`wait`/`delay`/`post_wait_s` → set `post_wait_s` (detik)
  - key `label`/`judul` → override judul step yang tampil
  - key berawalan `!` (mis. `!counter_res`) → masuk ke `validate`
  - key lainnya → masuk ke `expect`

## Nambah suite baru

**Suite biasa (paling umum)** — kalau isinya cuma kombinasi/urutan step
yang SUDAH ADA di `_steps.json` device terkait: buat SATU file
`<nama>.feature` LANGSUNG di `commands/tm81/config/` atau
`commands/bexa/config/` (folder yang sama dengan `_steps.json`-nya).
TIDAK perlu JSON, TIDAK perlu file map, TIDAK perlu jalankan converter
apa pun — simpan, langsung muncul di Add Test.

**Suite OTA baru** — 2 file: `<nama>.json` kecil (copy struktur `_dialog`
+ `fw_version` + `label` dari `tm81_ota.json` yang sudah ada) +
`<nama>.feature` (daftar step, base class `TM81OtaTestSource`) di
`commands/tm81/config/`. Otomatis kedeteksi selama JSON-nya punya field
`"fw_version"` — lihat `scan_lean_sources(..., ota_only=True)` di
`lib/loaders/tm81.py`.

**Kalau perlu step baru yang belum ada di `_steps.json`**: tambah dulu
definisinya di situ (`command_class`, `label`, dst — dipakai bareng semua
suite di device yang sama), baru dipakai di `.feature`.

## Tooling (jarang dipakai — cuma buat suite mode "replace-in-place", mis. Flash)

```
python tools/json_to_gherkin.py commands/flash/config/tm81.json
```

Generate `<stem>.feature` di FOLDER YANG SAMA dengan JSON sumbernya (bukan
folder terpusat). Dipakai kalau suite-nya memang masih butuh JSON penuh
(field yang di-edit dialog GUI langsung ke `tests[]` atau `steps[]`) tapi
urutannya mau bisa diedit tanpa buka JSON.
