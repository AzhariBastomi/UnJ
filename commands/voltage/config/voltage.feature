# Daftar titik ukur tegangan (Voltage) yang muncul di Add Test -- satu baris
# per titik. Definisi tiap titik (label/command/description) ada di
# _steps.json di folder yang sama. Tambah titik baru: tambah definisinya di
# _steps.json, lalu tambah satu baris di sini. Hapus baris = titik itu tidak
# muncul di Add Test. Urutan baris = urutan tampil.

Feature: Voltage

  Scenario: Voltage
    Given 1v8
    And 3v3
    And 5v
