# Suite TM81 Join (dulu tm81_join.json) -- daftar/urutan step di sini,
# isi tiap step dari _steps.json. Simpan -> otomatis muncul di Add Test.

Feature: TM81 Join

  Scenario: TM81 Join
    Given user_reset_config: Reset konfigurasi user ke default
    Then user_get_config: Baca konfigurasi user setelah reset — cek Activation harus Deactivated
      | Activation | Deactivated |
    And rtc_set: Sinkronisasi RTC device ke waktu PC
    And rtc_get: Baca waktu RTC dari device - validasi rtc_set
    And sensor_data: Baca data mentah sensor
    And sensor_calibration: Kalibrasi sensor
    And user_set_config: Set konfigurasi user (activation, counter, alarm, submit rate, timezone, msg type)
    And dev_info: Baca info device: baterai, sensor, LoRa status
