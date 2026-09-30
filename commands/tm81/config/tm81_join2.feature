# Suite TM81 Join 2 (dulu tm81_join2.json) -- daftar/urutan step di sini,
# isi tiap step dari _steps.json. Simpan -> otomatis muncul di Add Test.

Feature: TM81 Join 2

  Scenario: TM81 Join 2
    Given user_last_usage: Hitung last usage dari sensor pulse + initial counter
    And user_reset_config: Reset konfigurasi user ke default
    Then user_get_config: Baca konfigurasi user setelah reset — cek Activation harus Deactivated
      | Activation | Deactivated |
      | Init usage | 0.00 m3 |
      | Last usage | 0.00 m3 |
      | Submit rate | 30min |
      | Timezone | GMT-0 |
    And rtc_set: Sinkronisasi RTC device ke waktu PC
    And rtc_get: Baca waktu RTC dari device - validasi rtc_set
    And sensor_data: Baca data mentah sensor
    And user_set_config: Set konfigurasi user (activation, counter, alarm, submit rate, timezone, msg type)
      | tunggu | 2 |
    Then user_get_config_post_set: Baca konfigurasi user setelah set — bandingkan dengan commissioning.json
      | Activation | Activated |
    And dev_info: Baca info device: baterai, sensor, LoRa status
