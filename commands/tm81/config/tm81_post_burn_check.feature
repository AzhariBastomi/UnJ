# Suite TM81 Post-Burn Check -- cek cepat setelah proses burning/flash:
# set SN, baca balik, pastikan sensor & device hidup normal, lalu reset user
# config dan validasi kembali ke Deactivated.
# Simpan -> otomatis muncul di Add Test.

Feature: TM81 Post Burn Check

  Scenario: TM81 Post Burn Check
    Given set_id: Tulis Serial Number dari field UI ke device setelah burning
    And get_id: Baca balik Device ID dari memori - validasi set_id
    And sensor_data: Baca data mentah sensor - pastikan sensor terdeteksi & tidak error
    And dev_info: Baca info device: baterai, sensor, LoRa status
    And user_get_config: Baca konfigurasi user saat ini
    And user_reset_config: Reset konfigurasi user ke default
    Then user_get_config_post_set: Baca konfigurasi user setelah reset — cek Activation harus Deactivated
      | Activation | Deactivated |
