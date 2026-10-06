# Suite TM81 Reliability -- reproduksi bug dari SWM firmware reliability review.
# Isi tiap step (command_class) dari _steps.json. Simpan -> otomatis muncul di Add Test.
# prefix: tm81_reliability
#
# URUTAN: non-destruktif dulu (F12, F10), destruktif terakhir (F01, F02) karena
# keduanya bisa memicu HardFault -> IWDG reset (~40 dtk device hang lalu boot).
# Siapkan jalur reflash (recover_bricked_mcu / ST-Link) sebelum menjalankan F01/F02.
#
# Verdict tiap step ada di kolom hasil:
#   "BUG ... TERBUKTI"  = bug tereproduksi (firmware belum dipatch)
#   "TIDAK ..."         = tidak tereproduksi (aman / sudah dipatch)
#   "NG:..."            = tes tidak bisa jalan (koneksi / brick)

Feature: TM81 Reliability

  Scenario: TM81 Reliability
    Given reliability_f12: Slot history basi -- tulis Juni-1 & Sept-2, baca Sept harus NAK karena metadata masih Juni
    And reliability_f10: Panjang respons harian/bulanan tertukar -- seed sebulan, bandingkan payload bulanan vs harian
    And reliability_f07: Tahun RTC/alarm harian -- set periode 1day + force send, cek '[E] mktime.' di log stlink (butuh ST-Link VCP)
    And reliability_f01: OOB serial read -- frame declared-length palsu 65535; cek hang/WDT (DESTRUKTIF)
    Then reliability_f02: History buffer overwrite -- payload 128B, cek device hang lalu IWDG reset via bit WDT (DESTRUKTIF)
