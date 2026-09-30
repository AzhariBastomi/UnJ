# File ini digenerate otomatis dari commands/flash/config/tm81.json
# Regenerasi setelah edit JSON: python tools/json_to_gherkin.py commands/flash/config/tm81.json
# Untuk ubah alur test cukup edit file ini -- tidak perlu sentuh JSON/Python.
# Urutan baris = urutan eksekusi. Hapus baris = step dilewati.
# prefix: flash:tm81

Feature: TM81

  Scenario: TM81
    Given Bootloader
    And Application
