# Suite TM81 Factory Outgoing Reset -- reset operasional sebelum unit dikirim
# ke customer (hapus history/key/config; DevEui & Serial Number TETAP), lalu
# verifikasi lewat EEPROM sweep bahwa page yang seharusnya wipe memang 0x00
# dan page yang harus dipertahankan (SN, record sesi BL) tidak ikut terhapus.
# Suite terpisah dari commissioning utama (tm81_test.feature) -- destruktif,
# jalankan manual per unit yang mau dikirim, bukan bagian dari flow rutin.
# Simpan -> otomatis muncul di Add Test.

Feature: TM81 Factory Outgoing Reset

  Scenario: TM81 Factory Outgoing Reset
    Given factory_outgoing_reset: Reset operasional sebelum unit dikirim ke customer (destruktif - DevEui & SN dipertahankan)
    Then eeprom_page_sweep: Verifikasi EEPROM pasca reset - page wipe harus 0x00, page preserved (SN, sesi BL) harus tetap terisi
