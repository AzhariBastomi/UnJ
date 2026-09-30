# Suite TM81 Join 3 -- daftar/urutan step di sini, isi tiap step dari
# _steps.json. Simpan -> otomatis muncul di Add Test.

Feature: TM81 Join 3

  Scenario: TM81 Join 3
    Given user_reset_config: Reset user config ke default
    And lora_set_dev_eui: Set DevEUI device (8 bytes)
    And lora_set_join_eui: Set JoinEUI / AppEUI (8 bytes)
    And lora_set_app_key: Set AppKey LoRaWAN (16 bytes)
    And lora_set_nw_key: Set NwKey LoRaWAN (16 bytes)
    And lora_set_dev_addr: Set DevAddr ABP (4 bytes)
    And lora_set_join_mode: Set LoRa join mode (0=None, 1=ABP, 2=OTAA)
    And lora_set_dev_class: Set LoRa device class (0=A, 1=B, 2=C)
    And lora_set_config: Set LoRa TX power, data rate, RX1 delay
    Then lora_get_config: Baca konfigurasi LoRaWAN - validasi semua lora_set_*
    And rtc_set: Sinkronisasi RTC device ke waktu PC
    And rtc_get: Baca waktu RTC dari device - validasi rtc_set
    And sensor_data: Baca data mentah sensor
    And user_set_config: Set konfigurasi user (activation, counter, alarm, submit rate, timezone, msg type)
      | tunggu | 2 |
    Then user_get_config_post_set: Baca konfigurasi user setelah set — bandingkan dengan commissioning.json
      | Activation | Activated |
    And dev_info: Baca info device: baterai, sensor, LoRa status
