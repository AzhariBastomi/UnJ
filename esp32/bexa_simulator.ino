/**
 * bexa_simulator.ino
 * ==================
 * ESP32 — Simulator device BEXA untuk keperluan test jig.
 *
 * Cara kerja:
 *   1. ESP32 advertise sebagai Bluetooth Classic SPP dengan nama "BEXA_TEST"
 *   2. Jig PC pair + connect → muncul sebagai COM port
 *   3. Jig mengirim FTM frame (header 0x0E) ke COM port
 *   4. ESP32 parse frame, jalankan aksi, kirim ACK kembali
 *
 * Protocol: Bexa Wireless Protocol
 *   FTM Frame  : [0x0E][LEN_L][LEN_H][TID=0x00][CMD][CRC_L][CRC_H]
 *   ACK Frame  : [0xFF][LEN_L][LEN_H][TID][MSG_ID][STATUS][PL_PRESENT][PL_L][PL_H][PAYLOAD...][CRC_L][CRC_H]
 *   CRC        : CRC-16/KERMIT (poly=0x1021 reflected, init=0x0000)
 *
 * Board: ESP32 (pilih "ESP32 Dev Module" di Arduino IDE)
 * Library: BluetoothSerial (built-in ESP32 Arduino core)
 *
 * Pin mock (sesuaikan ke hardware BEXA yang sebenarnya):
 *   GPIO 25 — Haptic Left
 *   GPIO 26 — Haptic Right
 *   GPIO 27 — Buzzer
 *   GPIO 32 — LED Action
 *   GPIO 33 — LED Power
 *   GPIO 18 — Lightbar Data (SPI/TLC5940 mock → just blink)
 */

#include "BluetoothSerial.h"

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────

#define BT_DEVICE_NAME    "BEXA_TEST"
#define RX_BUF_SIZE       256
#define FTM_HEADER        0x0E
#define CMD_HEADER_ACK    0xFF

// Mock peripheral pins
#define PIN_HAPTIC_L   25
#define PIN_HAPTIC_R   26
#define PIN_BUZZER     27
#define PIN_LED_ACTION 32
#define PIN_LED_POWER  33
#define PIN_LIGHTBAR   18   // mock — SPI/TLC5940 simplified

BluetoothSerial SerialBT;

// ─────────────────────────────────────────────────────────────────────────────
// FTM Command Codes
// ─────────────────────────────────────────────────────────────────────────────

#define FTM_GET_BT_INFO           0x00
#define FTM_GET_TACTILE_INFO      0x01
#define FTM_GET_HAPTIC_INFO       0x02
#define FTM_GET_COULOMB_INFO      0x03
#define FTM_BLUETOOTH_BURST       0x04
#define FTM_TACTILE_SENSOR_READ   0x05
#define FTM_HAPTIC_VIBRATING      0x06
#define FTM_COULOMB_COUNTER_READ  0x07
#define FTM_LED_ACTION_RGB        0x08
#define FTM_LED_POWER_RGB         0x09
#define FTM_LIGHTBAR_PULSING      0x0A
#define FTM_BUZZER_PLAYING        0x0B
#define FTM_IMU_READ              0x0C
#define FTM_WATCHDOG_RESET        0x0D
#define FTM_BT_RF_SIG             0x0E
#define FTM_CHARGING_INFO         0x0F
#define FTM_TESTING_ALL           0x10
#define FTM_STOP                  0x11

// ─────────────────────────────────────────────────────────────────────────────
// CRC-16/KERMIT
// ─────────────────────────────────────────────────────────────────────────────

uint16_t crc16_kermit(const uint8_t* data, size_t len) {
    uint16_t crc = 0x0000;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 0x0001)
                crc = (crc >> 1) ^ 0x8408;  // 0x1021 reversed
            else
                crc >>= 1;
        }
    }
    return crc;
}

// ─────────────────────────────────────────────────────────────────────────────
// ACK Builder
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Kirim ACK frame.
 *   msg_id  : command yang di-ACK (sama dengan CMD dari FTM frame)
 *   status  : 0 = OK, non-zero = error
 *   payload : data tambahan (null jika tidak ada)
 *   pl_len  : panjang payload
 */
void send_ack(uint8_t msg_id, uint8_t status,
              const uint8_t* payload = nullptr, uint16_t pl_len = 0) {
    // Body: [TID][MSG_ID][STATUS][PAYLOAD_PRESENT][PL_LEN_L][PL_LEN_H][PAYLOAD...]
    uint8_t tid = 0x00;
    uint8_t pl_present = (payload != nullptr && pl_len > 0) ? 1 : 0;

    uint16_t body_len = 3 + 1 + (pl_present ? 2 + pl_len : 0);
    // Frame: [0xFF][LEN_L][LEN_H][BODY...][CRC_L][CRC_H]
    uint16_t frame_len = 3 + body_len + 2;
    uint8_t* frame = new uint8_t[frame_len];

    frame[0] = CMD_HEADER_ACK;
    frame[1] = body_len & 0xFF;
    frame[2] = (body_len >> 8) & 0xFF;

    // Body
    size_t idx = 3;
    frame[idx++] = tid;
    frame[idx++] = msg_id;
    frame[idx++] = status;
    frame[idx++] = pl_present;
    if (pl_present) {
        frame[idx++] = pl_len & 0xFF;
        frame[idx++] = (pl_len >> 8) & 0xFF;
        memcpy(&frame[idx], payload, pl_len);
        idx += pl_len;
    }

    // CRC over [header + length + body]
    uint16_t crc = crc16_kermit(frame, idx);
    frame[idx++] = crc & 0xFF;
    frame[idx++] = (crc >> 8) & 0xFF;

    SerialBT.write(frame, frame_len);
    Serial.printf("[ACK] MSG=0x%02X STATUS=0x%02X PL=%d bytes\n",
                  msg_id, status, pl_len);
    delete[] frame;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mock hardware actions
// ─────────────────────────────────────────────────────────────────────────────

void mock_haptic_vibrate() {
    // Getar kiri dan kanan bergantian
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_HAPTIC_L, HIGH); delay(200);
        digitalWrite(PIN_HAPTIC_L, LOW);  delay(100);
        digitalWrite(PIN_HAPTIC_R, HIGH); delay(200);
        digitalWrite(PIN_HAPTIC_R, LOW);  delay(100);
    }
}

void mock_led_flash_rgb(uint8_t pin) {
    // Kedip 3 kali per warna (mock: 3 kali on/off)
    for (int i = 0; i < 3; i++) {
        analogWrite(pin, 255); delay(200);  // RED (mock)
        analogWrite(pin, 0);   delay(100);
    }
    delay(100);
    for (int i = 0; i < 3; i++) {
        analogWrite(pin, 128); delay(200);  // GREEN (mock)
        analogWrite(pin, 0);   delay(100);
    }
    delay(100);
    for (int i = 0; i < 3; i++) {
        analogWrite(pin, 64);  delay(200);  // BLUE (mock)
        analogWrite(pin, 0);   delay(100);
    }
}

void mock_lightbar_pulsing() {
    // Pulsing dari 0 ke 8 kiri dan kanan (mock: naik turun brightness)
    for (int level = 0; level <= 255; level += 32) {
        analogWrite(PIN_LIGHTBAR, level);
        delay(50);
    }
    for (int level = 255; level >= 0; level -= 32) {
        analogWrite(PIN_LIGHTBAR, level);
        delay(50);
    }
}

void mock_buzzer_play() {
    // Tone: buzzer high-low beberapa kali
    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_BUZZER, HIGH); delay(100);
        digitalWrite(PIN_BUZZER, LOW);  delay(100);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Mock sensor data
// ─────────────────────────────────────────────────────────────────────────────

// Mock IMU (ax, ay, az mg, gx, gy, gz raw) — 12 bytes little-endian int16
void build_mock_imu(uint8_t* buf) {
    int16_t ax =  100, ay = -50, az = 980;   // ~1g on Z
    int16_t gx =    2, gy =   1, gz =   0;
    memcpy(buf + 0, &ax, 2); memcpy(buf + 2, &ay, 2); memcpy(buf + 4, &az, 2);
    memcpy(buf + 6, &gx, 2); memcpy(buf + 8, &gy, 2); memcpy(buf + 10, &gz, 2);
}

// Mock Coulomb Counter (voltage mV uint16, temp 0.1°C int16, ACR uint16) — 6 bytes
void build_mock_coulomb(uint8_t* buf) {
    uint16_t voltage = 3800;    // 3.800 V
    int16_t  temp    = 250;     // 25.0 °C
    uint16_t acr     = 1500;    // mock ACR
    memcpy(buf + 0, &voltage, 2);
    memcpy(buf + 2, &temp,    2);
    memcpy(buf + 4, &acr,     2);
}

// Mock Charging Info (state, level, voltage) — 4 bytes
void build_mock_charging(uint8_t* buf) {
    buf[0] = 1;     // 1 = Charging
    buf[1] = 75;    // 75%
    uint16_t voltage = 4050;
    memcpy(buf + 2, &voltage, 2);
}

// Mock BT Info — name(8B) + MAC(6B) + FW(2B) — 16 bytes
void build_mock_bt_info(uint8_t* buf) {
    const char* name = "BEXA_TST";
    memcpy(buf, name, 8);
    // Mock MAC
    buf[8]  = 0xAA; buf[9]  = 0xBB; buf[10] = 0xCC;
    buf[11] = 0xDD; buf[12] = 0xEE; buf[13] = 0xFF;
    // FW version 1.0
    buf[14] = 0x01; buf[15] = 0x00;
}

// Mock Config Request response
void build_mock_config(uint8_t* buf, uint16_t* out_len) {
    buf[0] = 8;    // sensor_row
    buf[1] = 8;    // sensor_cols
    uint16_t sv = 0x0101;
    memcpy(buf + 2, &sv, 2);
    buf[4] = 72;   // position_length (72 bytes Position_Data)
    buf[5] = 0x01; // protocol_version
    buf[6] = 0b00111111; // peripheral_status: semua OK (BT|TACTILE|CC|IMU|HAPTIC|TLC5940)
    // FW version string
    const char* fw = "1.0.0";
    memcpy(buf + 7, fw, strlen(fw));
    *out_len = 7 + strlen(fw);
}

// ─────────────────────────────────────────────────────────────────────────────
// FTM Dispatch
// ─────────────────────────────────────────────────────────────────────────────

void handle_ftm_command(uint8_t cmd) {
    Serial.printf("[FTM] CMD=0x%02X\n", cmd);

    uint8_t buf[64];
    uint16_t buf_len = 0;

    switch (cmd) {

        case FTM_GET_BT_INFO:
            build_mock_bt_info(buf);
            send_ack(cmd, 0x00, buf, 16);
            break;

        case FTM_GET_TACTILE_INFO:
            // Mock: rows=8, cols=8, version=0x0101
            buf[0] = 8; buf[1] = 8;
            buf[2] = 0x01; buf[3] = 0x01;
            send_ack(cmd, 0x00, buf, 4);
            break;

        case FTM_GET_HAPTIC_INFO:
            // Mock: left_ok=1, right_ok=1, driver_version=0x01
            buf[0] = 1; buf[1] = 1; buf[2] = 0x01;
            send_ack(cmd, 0x00, buf, 3);
            break;

        case FTM_GET_COULOMB_INFO:
            build_mock_coulomb(buf);
            send_ack(cmd, 0x00, buf, 6);
            break;

        case FTM_BLUETOOTH_BURST:
            // Kirim ACK dulu, lalu disconnect
            send_ack(cmd, 0x00);
            delay(100);
            SerialBT.end();
            delay(2000);
            SerialBT.begin(BT_DEVICE_NAME);   // re-advertise
            break;

        case FTM_TACTILE_SENSOR_READ: {
            // Mock: 8x8 = 64 sensor values (semua 0x20)
            memset(buf, 0x20, 64);
            send_ack(cmd, 0x00, buf, 64);
            break;
        }

        case FTM_HAPTIC_VIBRATING:
            mock_haptic_vibrate();
            send_ack(cmd, 0x00);
            break;

        case FTM_COULOMB_COUNTER_READ:
            build_mock_coulomb(buf);
            send_ack(cmd, 0x00, buf, 6);
            break;

        case FTM_LED_ACTION_RGB:
            mock_led_flash_rgb(PIN_LED_ACTION);
            send_ack(cmd, 0x00);
            break;

        case FTM_LED_POWER_RGB:
            mock_led_flash_rgb(PIN_LED_POWER);
            send_ack(cmd, 0x00);
            break;

        case FTM_LIGHTBAR_PULSING:
            mock_lightbar_pulsing();
            send_ack(cmd, 0x00);
            break;

        case FTM_BUZZER_PLAYING:
            mock_buzzer_play();
            send_ack(cmd, 0x00);
            break;

        case FTM_IMU_READ:
            build_mock_imu(buf);
            send_ack(cmd, 0x00, buf, 12);
            break;

        case FTM_WATCHDOG_RESET:
            send_ack(cmd, 0x00);
            delay(200);
            esp_task_wdt_reset();   // reset WDT
            break;

        case FTM_BT_RF_SIG:
            // Mock RF signal test — kembalikan mock RSSI
            buf[0] = (uint8_t)(-65 + 128);  // mock RSSI = -65 dBm, dikodekan sebagai uint8
            send_ack(cmd, 0x00, buf, 1);
            break;

        case FTM_CHARGING_INFO:
            build_mock_charging(buf);
            send_ack(cmd, 0x00, buf, 4);
            break;

        case FTM_TESTING_ALL:
            // Jalankan semua test secara berurutan
            Serial.println("[FTM] TESTING_ALL — start");
            mock_haptic_vibrate();
            mock_led_flash_rgb(PIN_LED_ACTION);
            mock_led_flash_rgb(PIN_LED_POWER);
            mock_lightbar_pulsing();
            mock_buzzer_play();
            // Kirim ACK lalu disconnect (sesuai spec)
            send_ack(cmd, 0x00);
            delay(100);
            SerialBT.end();
            delay(2000);
            SerialBT.begin(BT_DEVICE_NAME);
            break;

        case FTM_STOP:
            // Tidak ada aksi khusus — hanya ACK
            send_ack(cmd, 0x00);
            Serial.println("[FTM] STOP");
            break;

        default:
            Serial.printf("[FTM] Unknown CMD 0x%02X\n", cmd);
            send_ack(cmd, 0xFF);    // status 0xFF = unknown command
            break;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Frame Parser
// ─────────────────────────────────────────────────────────────────────────────

uint8_t  rx_buf[RX_BUF_SIZE];
uint16_t rx_len = 0;

void parse_rx_buffer() {
    while (rx_len >= 5) {
        // Cari header FTM (0x0E)
        if (rx_buf[0] != FTM_HEADER) {
            // Geser buffer — buang byte pertama yang tidak dikenal
            memmove(rx_buf, rx_buf + 1, rx_len - 1);
            rx_len--;
            continue;
        }

        uint16_t body_len = rx_buf[1] | ((uint16_t)rx_buf[2] << 8);
        uint16_t needed   = 3 + body_len + 2;  // header(3) + body + crc(2)

        if (rx_len < needed) break;  // belum cukup data

        // Validasi CRC
        uint16_t crc_recv = rx_buf[3 + body_len] | ((uint16_t)rx_buf[3 + body_len + 1] << 8);
        uint16_t crc_calc = crc16_kermit(rx_buf, 3 + body_len);

        if (crc_recv != crc_calc) {
            Serial.printf("[RX] CRC error: calc=0x%04X recv=0x%04X\n", crc_calc, crc_recv);
            // Geser untuk cari frame berikutnya
            memmove(rx_buf, rx_buf + 1, rx_len - 1);
            rx_len--;
            continue;
        }

        // Frame valid — body[0]=TID, body[1]=CMD
        uint8_t tid = rx_buf[3];
        uint8_t cmd = rx_buf[4];

        handle_ftm_command(cmd);

        // Consume frame dari buffer
        memmove(rx_buf, rx_buf + needed, rx_len - needed);
        rx_len -= needed;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Setup & Loop
// ─────────────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    Serial.println("[BEXA Simulator] Starting...");

    // Init pins
    pinMode(PIN_HAPTIC_L,   OUTPUT);
    pinMode(PIN_HAPTIC_R,   OUTPUT);
    pinMode(PIN_BUZZER,     OUTPUT);
    pinMode(PIN_LED_ACTION, OUTPUT);
    pinMode(PIN_LED_POWER,  OUTPUT);
    pinMode(PIN_LIGHTBAR,   OUTPUT);

    digitalWrite(PIN_HAPTIC_L,   LOW);
    digitalWrite(PIN_HAPTIC_R,   LOW);
    digitalWrite(PIN_BUZZER,     LOW);
    digitalWrite(PIN_LED_ACTION, LOW);
    digitalWrite(PIN_LED_POWER,  LOW);
    digitalWrite(PIN_LIGHTBAR,   LOW);

    // Start Bluetooth Classic SPP
    if (!SerialBT.begin(BT_DEVICE_NAME)) {
        Serial.println("[BT] Failed to start BluetoothSerial!");
        while (1) delay(1000);
    }
    Serial.printf("[BT] Device \"%s\" siap di-pair\n", BT_DEVICE_NAME);
    Serial.println("[BT] Menunggu koneksi dari Jig PC...");

    // Self-test singkat
    digitalWrite(PIN_LED_ACTION, HIGH); delay(200);
    digitalWrite(PIN_LED_ACTION, LOW);
    digitalWrite(PIN_LED_POWER, HIGH);  delay(200);
    digitalWrite(PIN_LED_POWER, LOW);
    Serial.println("[BEXA Simulator] Ready");
}

void loop() {
    // Baca data Bluetooth masuk
    while (SerialBT.available()) {
        uint8_t b = SerialBT.read();
        if (rx_len < RX_BUF_SIZE) {
            rx_buf[rx_len++] = b;
        } else {
            // Buffer penuh — reset
            Serial.println("[RX] Buffer overflow, reset");
            rx_len = 0;
        }
    }

    // Parse frames yang terkumpul
    if (rx_len > 0) {
        parse_rx_buffer();
    }

    delay(5);
}
