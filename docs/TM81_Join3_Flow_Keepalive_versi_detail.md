# Suite TM81 Join 3 — flow eksekusi, detail tiap step & penggunaan keepalive

Status: dibuat 2026-09-18, detail per-step ditambahkan 2026-09-18. Suite
`commands/tm81/config/tm81_join3.feature` (lean, tanpa JSON) — detail
migrasi Gherkin umum ada di `features/README.md`, dokumen ini fokus ke
suite Join 3 spesifik: isi tiap step, flow eksekusi, dan keepalive.

## Isi `tm81_join3.feature`

```
user_reset_config → lora_set_dev_eui → lora_set_join_eui →
lora_set_app_key → lora_set_nw_key → lora_set_dev_addr →
lora_set_join_mode → lora_set_dev_class → lora_set_config →
lora_get_config → rtc_set → rtc_get → sensor_data →
user_set_config (tunggu 2 detik) → user_get_config_post_set
(expect Activation=Activated) → dev_info
```

Terdeteksi otomatis sebagai suite baru lewat prefix `tm81_join3` (pola lean
sama seperti `tm81_join`/`tm81_join2`) — tidak perlu JSON atau file map
tambahan. Diverifikasi lewat `get_tm81_extra_sources()` + `load_one()`:
16 step ter-resolve tanpa NG.

## Detail tiap step (command, data, default value, kriteria OK)

Nilai default di bawah diambil dari `commands/tm81/config/commissioning.json`
(dipakai kalau step tidak dikasih `params` eksplisit).

| # | Step | CMD | Data dikirim | Default (commissioning.json) | Kriteria OK |
|---|------|-----|---------------|-------------------------------|-------------|
| 1 | `user_reset_config` | 0x09 | — (tanpa payload) | — | Device balas ACK. Semua config user di device balik ke default (activation → Deactivated). |
| 2 | `lora_set_dev_eui` | 0x0F | DevEUI 8 byte | `0080E10101010169` | Validasi panjang 8 byte SEBELUM kirim (NG kalau bukan 16 hex char) + device balas ACK. |
| 3 | `lora_set_join_eui` | 0x10 | JoinEUI 8 byte | `FFFFFFFFFFFFFFFF` | Sama pola: panjang 8 byte + ACK. |
| 4 | `lora_set_app_key` | 0x11 | AppKey 16 byte | `8833E75406D203F48D1F6D2CCC2815D8` | Panjang 16 byte + ACK. Dipakai untuk join OTAA. |
| 5 | `lora_set_nw_key` | 0x12 | NwKey 16 byte | `8833E75406D203F48D1F6D2CCC2815D8` | Panjang 16 byte + ACK. Dipakai untuk sesi ABP (NwkSKey). |
| 6 | `lora_set_dev_addr` | 0x13 | DevAddr 4 byte (little-endian) | `0x0100000B` | Ditolak (NG) kalau DevAddr = 0x00000000 + ACK. Dipakai untuk ABP. |
| 7 | `lora_set_join_mode` | 0x14 | 1 byte: 0=None, 1=ABP, 2=OTAA | `2` (OTAA) | ACK. Menentukan device pakai OTAA (join pakai DevEUI/JoinEUI/AppKey) atau ABP (pakai DevAddr/NwKey langsung). |
| 8 | `lora_set_dev_class` | 0x15 | 1 byte: 0=A, 1=B, 2=C | `0` (Class A) | ACK. |
| 9 | `lora_set_config` | 0x1D | 3 byte: tx_power, data_rate, rx1_delay(detik) | tx_power=0, data_rate=0, rx1_delay=5 | ACK. |
| 10 | `lora_get_config` | 0x16 | — (read-only) | — | Baca balik 57 byte: class, join_mode, dev_addr, dev_eui, join_eui, app_key, nwk_key, tx_power, data_rate, rx1_delay — ditampilkan detail untuk dicocokkan manual ke step 2–9. **Catatan**: step ini di `.feature` TIDAK dikasih Data Table `expect`, jadi pencocokan nilainya masih manual lewat detail yang tampil di UI, bukan PASS/FAIL otomatis per-field (beda dari `user_get_config_post_set` yang punya `expect`). |
| 11 | `rtc_set` | 0x0B | 6 byte: year-2000, month, day, hour, minute, second | waktu PC saat ini | ACK. |
| 12 | `rtc_get` | 0x0A | — (read-only) | — | Baca balik 6 byte, ditampilkan sebagai waktu device untuk dibandingkan manual ke `rtc_set`. **Catatan potensi bug**: `rtc_set` encode tahun sebagai `year-2000` (mis. 2026→26), tapi `rtc_get_time.py` decode tahun sebagai `1900+yr` (26→1926) — kalau firmware echo balik byte yang sama persis, tahun yang ditampilkan `rtc_get` akan salah 100 tahun. Belum dikonfirmasi apakah firmware benar-benar echo raw byte yang sama; kalau ketemu RTC tampil tahun 19xx, ini penyebabnya. |
| 13 | `sensor_data` | 0x04 | — (read-only) | — | Baca 14 byte: versi sensor, signal intensity/indication, pulsa forward/backward, status byte (kalibrasi gagal, sampling mode, modul lepas, interferensi metal, pernah dikalibrasi, tegangan rendah), debug byte. Snapshot kondisi sensor — suite ini TIDAK menjalankan `sensor_calibration` (beda dari `tm81_join`). |
| 14 | `user_set_config` | 0x07 | 8 byte: activation(selalu 1/hardcoded di kode), initial_counter(4B), counter_res(1B), alarm(1B), submit_id(1B), timezone(1B, signed), msg_type(1B) | initial_counter=31913, counter_res=1 (10L), alarm=0, submit_id=2 (1 jam), timezone=7 (UTC+7), msg_type=1 (Confirmed) | ACK. Data Table `tunggu: 2` di `.feature` → `post_wait_s=2`, runner jeda 2 detik setelah step ini sebelum lanjut ke step berikutnya, kasih device waktu proses aktivasi. |
| 15 | `user_get_config_post_set` | 0x08 | — (read-only, class command sama dengan `user_get_config`, dibedakan lewat nama step) | — | Baca balik config user (activation, init/last usage m³, counter res, alarm bits, submit rate, timezone, msg type). Data Table `Activation: Activated` di `.feature` → masuk `expect`, dibandingkan otomatis ke hasil device — baris jadi NG kalau field `Activation` yang dibaca bukan "Activated". |
| 16 | `dev_info` | 0x1A | — (read-only) | — | Baca 20 byte: sensor intensity/indication, baterai (INTP, impedance mOhm, usage mAh, remaining mAh, persentase), LoRaWAN Network ID, RSSI/SNR downlink terakhir, `in_join_session`, `ever_joined`, `last_uplink_success`. Step terakhir ini yang jadi indikator paling relevan untuk memastikan device benar-benar sudah join jaringan LoRaWAN setelah seluruh commissioning di atas (`ever_joined`/`in_join_session` di summary UI). |

## Flow eksekusi

```
1. User klik "+ Add Test" → pilih "TM81 Join 3"
        │
        ▼
2. AddTestDialog → load_test("tm81_join3:<step>") untuk tiap baris
   di tm81_join3.feature → resolve ke command_class via _steps.json
        │
        ▼
3. _add_test() (app/_test_mgmt_mixin.py)
   - deteksi project dari nama modul → "tm81"
   - project == "tm81" / mulai "tm81_" → self._keepalive.start()
     (kalau keepalive belum jalan, thread ping TM81 di-start di sini)
        │
        ▼
4. List test tampil di panel → user klik "Start"
        │
        ▼
5. Runner jalankan step satu-satu SESUAI URUTAN di tm81_join3.feature
   (lihat tabel detail di atas untuk isi tiap step)
        │
        ▼
6. Tiap step .execute() → TM81Command.xfer() → acquire per-connection
   lock (lib/serial_manager.py) → kirim frame → tunggu response →
   release lock → baris jadi OK/NG di UI
```

## Penggunaan keepalive

Keepalive (`controllers/keepalive.py`) jalan sebagai thread background
terpisah, bukan bagian dari urutan step di `.feature`:

- **Start**: otomatis begitu ada test TM81 di-Add (`self._keepalive.start()`
  di `app/_test_mgmt_mixin.py` / `app/_state_mixin.py`), atau saat app
  dibuka kalau project tersimpan sudah `tm81`.
- **Kerjanya**: tiap `interval_ms` (default 5 detik, dari
  `config/config.json → keepalive`), thread ini kirim `Ping` ke TM81 supaya
  device tidak masuk sleep mode selagi menunggu user klik Start / di antara
  test.
- **Tidak bentrok dengan step `tm81_join3`**: setiap `xfer()` — baik dari
  ping keepalive maupun dari step manapun di `tm81_join3`
  (`lora_set_dev_eui`, `rtc_set`, dst) — wajib acquire lock per-koneksi
  (`sm.get_lock(conn)`) dulu (`lib/serial_manager.py`). Kalau keepalive
  sedang ping pas step lain mau kirim, step itu tinggal antre sebentar
  sampai lock dilepas — tidak ada frame yang tabrakan di serial port. Ini
  otomatis, tidak butuh `pause_global()`/`resume_global()` manual.
- **`pause_global()`/`resume_global()`** (mekanisme terpisah, "safety layer
  ke-2") TIDAK dipakai oleh step manapun di `tm81_join3` — itu cuma
  dipanggil di operasi long-running yang sensitif timing:
  `commands/tm81/bl_write_firmware(_v2).py` (proses OTA/flash firmware) dan
  `commands/tm81/sensor_calibration.py`. Jadi selama `tm81_join3` jalan,
  keepalive tetap ping normal di background (cuma diselingi lock), bukan
  di-pause.
- **Stop**: kalau semua test TM81 di-Clear atau ganti ke project lain
  (misal Flash/BEXA), `self._keepalive.stop()` dipanggil dan LED status
  keepalive di UI ikut mati.

Kesimpulan: `tm81_join3` sendiri tidak perlu peduli keepalive sama sekali —
otomatis start begitu suite TM81 ditambahkan, dan aman berjalan bareng
lewat lock serial per-koneksi, tanpa perlu pause manual di step manapun.
