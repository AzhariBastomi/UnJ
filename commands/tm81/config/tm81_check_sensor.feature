# Suite TM81 Check Sensor -- daftar/urutan step di sini, isi tiap step
# dari _steps.json (semua step SUDAH ADA). Simpan -> otomatis muncul di
# Add Test.

Feature: TM81 Check Sensor

  Scenario: TM81 Check Sensor
    Given sensor_do_reset_config: Reset konfigurasi sensor
    And sensor_do_get_config: Trigger satu siklus pembacaan sensor
    And sensor_data: Baca data mentah sensor
