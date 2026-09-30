# Suite BEXA utama (dulu bexa_test.json) -- daftar/urutan step di sini,
# isi tiap step (command_class, dll) dari _steps.json. Simpan -> otomatis
# muncul di Add Test.
# prefix: bexa

Feature: BEXA

  Scenario: BEXA
    Given config_request: Baca konfigurasi device: sensor rows/cols, versi, status semua peripheral
    And battery_request: Baca status charging dan level baterai
    And get_bt_info: FTM 0x00 — Baca info Bluetooth (MAC, versi) via DEBUG UART
    And get_tactile_info: FTM 0x01 — Baca info Tactile Sensor via DEBUG UART
    And get_haptic_info: FTM 0x02 — Baca info Haptic Motor via DEBUG UART
    And get_coulomb_info: FTM 0x03 — Baca info Coulomb Counter via DEBUG UART
    And tactile_read: FTM 0x05 — Baca data mentah Tactile Sensor
    And coulomb_read: FTM 0x07 — Baca ACR, Voltage, dan Temperature dari Coulomb Counter
    And imu_read: FTM 0x0C — Baca data Accelerometer + Gyroscope
    And charging_info: FTM 0x0F — Baca status charging dan info daya
    And haptic_vibrating: FTM 0x06 — Haptic motor bergetar bergantian kiri dan kanan
    And led_action_rgb: FTM 0x08 — LED Action berkedip Merah → Hijau → Biru
    And led_power_rgb: FTM 0x09 — LED Power berkedip Merah → Hijau → Biru
    And lightbar_pulsing: FTM 0x0A — Lightbar pulsing dari 0 ke 8, kiri dan kanan
    And buzzer_playing: FTM 0x0B — Buzzer berbunyi
    And bt_rf_sig: FTM 0x0E — BT RF signal test
    And stop: FTM 0x11 — Hentikan semua test case yang sedang berjalan
