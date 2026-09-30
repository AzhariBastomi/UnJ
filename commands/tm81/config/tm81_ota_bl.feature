# Suite OTA Bootloader TM81 (dulu tm81_ota_bl.json) -- fw_version tetap
# diatur lewat tombol "OTA Settings" di GUI, disimpan di tm81_ota_bl.json
# (sudah diperkecil, tidak lagi berisi daftar step). Daftar/urutan step
# di sini. Device harus dalam mode App saat memulai.
# prefix: tm81_ota_bl

Feature: TM81 OTA Bootloader

  Scenario: TM81 OTA Bootloader
    Given user_reset_config: Reset konfigurasi user ke default
    Then user_get_config: Verifikasi config sudah ter-reset — cek Activation harus Deactivated
      | Activation | Deactivated |
    And bl_unlock: Kirim BL_GOTO_APP 5x (semua NAK = normal) untuk membuka guard OTA Bootloader. Device harus di App mode.
    And write_fw: Transfer chunk firmware Bootloader ke device via IrDA (resume support). Fresh transfer otomatis clear metadata dulu.
      | label | Write BL Firmware |
    And bl_goto_app_bl => bl_goto_app: Validasi image BL lalu soft reset ke Bootloader baru (safety gate aktif — tolak jika image belum lengkap)
    And get_version: Baca versi App dan Bootloader — verifikasi BL baru berhasil aktif
    And get_id: Baca Device ID dari memori - validasi set_id
