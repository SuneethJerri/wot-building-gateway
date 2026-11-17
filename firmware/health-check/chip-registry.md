# Chip Registry — Level 3 bring-up

ESP8266 / ESP32 boards, health-checked one by one before being assigned a
device role (sensor / fan-coap / fan-mqtt).

Health check: `firmware/health-check` — dual-arch `main.cpp`; `-e nodemcuv2`
(ESP8266, `/dev/ttyUSB*`) or `-e esp32dev` (ESP32, `/dev/ttyACM*`).

| # | MAC | Chip | Flash | Port | Checked (date) | Health | Role |
|---|-----|------|-------|------|----------------|--------|------|
| 1 | `B4:E6:2D:6A:B7:44` | ESP8266EX (`6AB744`) | 4096 KB | ttyUSB0 | 2026-11-17 | ✅ PASS (heap 51.5 KB, frag 0%, Vcc 3.00 V, WiFi 9 APs) | **room1-fan → CoAP** (`firmware/fan-coap`, flashed+verified 2026-11-17) |
| 2 | `CC:50:E3:56:7F:8E` | ESP8266EX (`567F8E`) | 4096 KB | ttyUSB0 | 2026-11-17 | ✅ PASS (heap 51.5 KB, frag 0%, Vcc 3.07 V, WiFi 8 APs) | **room1-plug → HTTP** (`firmware/plug-http`, flashed+verified 2026-11-17) |
| 3 | `A0:B7:65:48:A7:58` | ESP32-D0WD-V3 (dual, 240 MHz) | 4096 KB | ttyACM0 | 2026-11-17 | ✅ PASS (heap 310 KB, die 50 °C, WiFi 9 APs) | **room1-sensor → MQTT** (`firmware/sensor-mqtt`, flashed+verified 2026-11-17) |

## Notes
- Chip 1/2 (ESP8266): all green. Vcc ~3.0 V is normal for ESP8266 `getVcc()`
  on USB, not a weak supply. Flash vendor differs (chip IDs `0016400E` /
  `001640EF`), both genuine 4 MB.
- Chip 3 (ESP32): no PSRAM, no runtime Vcc; die temp (~50 °C) used as the
  thermal/liveness signal instead. Enumerates as `/dev/ttyACM0` (native-USB
  style), unlike the 8266s on `/dev/ttyUSB0`.
