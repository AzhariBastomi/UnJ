# File ini digenerate otomatis dari commands/flash/config/bexa.json
# Regenerasi setelah edit JSON: python tools/json_to_gherkin.py commands/flash/config/bexa.json
# Untuk ubah alur test cukup edit file ini -- tidak perlu sentuh JSON/Python.
# Urutan baris = urutan eksekusi. Hapus baris = step dilewati.

Feature: BEXA

  Scenario: BEXA
    Given Bootloader
    And Application
    And Serial Number
