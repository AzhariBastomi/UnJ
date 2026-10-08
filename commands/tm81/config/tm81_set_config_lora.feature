# Suite TM81 Set Config LoRa -- daftar/urutan step di sini, isi tiap step
# dari _steps.json (semua step SUDAH ADA, dipakai bareng juga di
# tm81_test.feature). Simpan -> otomatis muncul di Add Test.

Feature: TM81 Set Config LoRa

  Scenario: TM81 Set Config LoRa
    Given user_reset_config: Reset user config ke default
    And lora_set_dev_eui: Set DevEUI device (8 bytes)
    And lora_set_join_eui: Set JoinEUI / AppEUI (8 bytes)
    And lora_set_app_key: Set AppKey LoRaWAN (16 bytes)
    And lora_set_nw_key: Set NwKey LoRaWAN (16 bytes)
    And lora_set_dev_addr: Set DevAddr ABP (4 bytes)
    And lora_set_join_mode: Set LoRa join mode (0=None, 1=ABP, 2=OTAA)
    And lora_set_dev_class: Set LoRa device class (0=A, 1=B, 2=C)
    And lora_set_config: Set LoRa TX power, data rate, RX1 delay
    And lora_set_cflist: Set mask added channel AS923-2 (dipakai saat join berikutnya)
    And lora_get_config: Baca konfigurasi LoRaWAN - validasi semua lora_set_*
    And lora_get_cflist: Baca mask added channel - validasi lora_set_cflist
    And dev_reset: Reset device via ST-Link (STM32_Programmer_CLI/st-flash) - popup 10s sama seperti Bootloader to App
    And lora_get_config_post_reset: Baca ulang konfigurasi LoRaWAN setelah reset - pastikan data yang di-set tetap tersimpan sama
    Then user_get_config: Baca konfigurasi user - pastikan activation Deactivated
      | Activation | Deactivated |
