# Suite TM81 utama (dulu tm81_test.json) -- daftar/urutan step di sini,
# isi tiap step (command_class, dll) dari _steps.json. Simpan -> otomatis
# muncul di Add Test.
# prefix: tm81

Feature: TM81

  Scenario: TM81
    Given get_version: Baca versi App dan Bootloader - pastikan firmware benar sebelum commissioning
    And set_id: Tulis Device ID dari field UI ke device
    And user_set_config: Set konfigurasi user (activation, counter, alarm, submit rate, timezone, msg type)
      | !counter_res | 1 |
      | !submit_id | 1 |
      | !timezone | 1 |
      | !msg_type | 1 |
    And user_synch_config: Sinkronisasi user config ke device
    And lora_set_dev_eui: Set DevEUI device (8 bytes)
    And lora_set_join_eui: Set JoinEUI / AppEUI (8 bytes)
    And lora_set_app_key: Set AppKey LoRaWAN (16 bytes)
    And lora_set_nw_key: Set NwKey LoRaWAN (16 bytes)
    And lora_set_dev_addr: Set DevAddr ABP (4 bytes)
    And lora_set_join_mode: Set LoRa join mode (0=None, 1=ABP, 2=OTAA)
    And lora_set_dev_class: Set LoRa device class (0=A, 1=B, 2=C)
    And lora_set_config: Set LoRa TX power, data rate, RX1 delay
    And rtc_set: Sinkronisasi RTC device ke waktu PC
    And get_id: Baca Device ID dari memori - validasi set_id
    And dev_info: Baca info device: baterai, sensor, LoRa status
    And bl_get_session: Baca record sesi Bootloader: session counter, state, durasi rantai BL (cmd 108)
    And rtc_get: Baca waktu RTC dari device - validasi rtc_set
    Then user_get_config: Baca konfigurasi user — bandingkan dengan commissioning.json
      | Activation | @user_set_config.activation |
      | Submit rate | @user_set_config.submit_id |
      | Counter res | @user_set_config.counter_res |
      | Timezone | @user_set_config.timezone |
      | Msg type | @user_set_config.msg_type |
    And lora_get_config: Baca konfigurasi LoRaWAN - validasi semua lora_set_*, update commissioning
    And lora_force_send: Paksa device kirim uplink LoRaWAN sekarang
    And lora_last_submit: Baca waktu terakhir device mengirim uplink
    And sensor_do_get_config: Trigger satu siklus pembacaan sensor
    And sensor_data: Baca data mentah sensor
    And user_last_usage: Hitung last usage dari sensor pulse + initial counter
    And sensor_calibration: Kalibrasi sensor
    And backup_write_usage: Tulis usage history ke device
    And mock_activation: Sync RTC + set config + poll join/uplink (max 120s)
    And irda_disable: Nonaktifkan IrDA pada device
    And standby_mode: Masukkan device ke mode standby
    And wdt_test: Test Watchdog Timer (device akan reset)
    And factory_outgoing_reset: Reset operasional sebelum unit dikirim ke customer (destruktif - DevEui & SN dipertahankan)
    And eeprom_page_sweep: Verifikasi EEPROM pasca reset - page wipe harus 0x00, page preserved (SN, sesi BL) harus tetap terisi
