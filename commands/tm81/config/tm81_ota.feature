# Suite OTA TM81 (dulu tm81_ota.json) -- fw_version tetap diatur lewat
# tombol "OTA Settings" di GUI, disimpan di tm81_ota.json (sudah diperkecil,
# tidak lagi berisi daftar step). Daftar/urutan step di sini.
# prefix: tm81_ota

Feature: TM81 OTA

  Scenario: TM81 OTA
    Given user_reset_config: Reset konfigurasi user ke default
    Then user_get_config: Verifikasi config sudah ter-reset — cek Activation harus Deactivated
      | Activation | Deactivated |
    And app_goto_bl: Reboot device dari App ke mode Bootloader (CMD 0x05, boot reason = IrDA OTA)
    And write_fw_v1 => write_fw: Kirim BL_SET_RDY lalu transfer chunk firmware ke bootloader
    And bl_goto_app_ota => bl_goto_app: Perintahkan bootloader lompat ke App (BL_GOTO_APP)
    And get_version: Baca versi App dan Bootloader
