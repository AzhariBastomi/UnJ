# Suite TM81 Session BL (dulu tm81_sesion_bl.json) -- daftar/urutan step di
# sini, isi tiap step dari _steps.json. Simpan -> otomatis muncul di Add Test.

Feature: TM81 Session BL

  Scenario: TM81 Session BL
    Given app_goto_bl: Reboot device dari App ke mode Bootloader (CMD 0x05, boot reason = IrDA OTA)
    And bl_goto_app: Validasi image lalu soft reset dari Bootloader kembali ke App (safety gate aktif — tolak jika image belum lengkap)
    And bl_clear_ota: Reset metadata OTA di EEPROM (fw_size=0, fw_crc=0, last_frame_id=0xFFFF) — CMD BL 107
    And bl_get_session: Baca record sesi Bootloader: session counter, state, durasi rantai BL (cmd 108)
