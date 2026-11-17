# Level 3 — distributed device pinouts

Three standalone boards, one WoT device each, health-checked and assigned in
`firmware/health-check/chip-registry.md`. Each chip joins the `LSPrmn60x`
hotspot and either publishes to the MQTT broker (sensor) or runs its own
CoAP/HTTP server (fan/plug) that the node-wot gateway consumes.

| Chip | MAC | Device | Protocol | Firmware |
|------|-----|--------|----------|----------|
| ESP32-D0WD | `A0:B7:65:48:A7:58` | `room1-sensor` | MQTT (publishes) | `firmware/sensor-mqtt` |
| ESP8266 #1 | `B4:E6:2D:6A:B7:44` | `room1-fan` | CoAP server :5683 | `firmware/fan-coap` *(todo)* |
| ESP8266 #2 | `CC:50:E3:56:7F:8E` | `room1-plug` | HTTP server :8081 | `firmware/plug-http` *(todo)* |

> **Power:** USB 5 V per board for logic. A relay *coil* and especially a real
> fan/motor must NOT be powered from the board's 3V3 rail — use the 5 V pin
> (VIN/VU) or a separate 5 V supply, and tie all grounds together (common GND).
> Keep the motor's own supply off the MCU rails to avoid brownout resets.

---

## 1. ESP32 — `room1-sensor` (DHT11 → MQTT)

Logic level **3.3 V**. GPIO numbers are the raw `GPIOxx` (what the firmware uses).

| DHT11 pin | → ESP32 pin | Note |
|-----------|-------------|------|
| VCC (+)   | **3V3**     | DHT11 runs at 3.3 V |
| DATA      | **GPIO4**   | matches the Pi's `board.D4`; `DHT_PIN` in firmware |
| GND (−)   | **GND**     | |

- Pull-up: **10 kΩ between DATA and 3V3**. Most 3-pin DHT11 breakout modules
  already include it — add the resistor only for a bare 4-pin DHT11.
- Onboard LED is **GPIO2** (used by the health-checker; sensor firmware leaves it free).
- No inbound server → no mDNS needed; the chip only needs to reach the broker.

```
  DHT11            ESP32
  +----+
  |VCC |---------- 3V3
  |DATA|----+----- GPIO4
  |GND |--+ |
  +----+  | +--[10kΩ]--3V3   (omit if the module has it)
          +-------------GND
```

---

## 2. ESP8266 #1 — `room1-fan` (relay → CoAP server :5683)

NodeMCU Amica, **3.3 V** logic. Relay: SONGLE **SRD-05VDC-SL-C**, 5 V coil,
**active-LOW** input (drive LOW = energise, matching `common.py active_high=False`).

| Relay module | → NodeMCU pin | Note |
|--------------|---------------|------|
| VCC          | **VIN (5V)**  | 5 V coil supply from USB |
| IN           | **D1 = GPIO5**| control signal; active-LOW |
| GND          | **GND**       | common ground |

- **Use D1/GPIO5.** Avoid the boot-strapping pins **GPIO0 (D3), GPIO2 (D4),
  GPIO15 (D8)** — a relay board can hold them at the wrong level during boot and
  brick the boot sequence.
- Fan wiring: mains/low-voltage fan through the relay **COM + NO** contacts, on
  its own supply — never through the NodeMCU.
- Advertises mDNS `room1-fan.local` so the TD/gateway survive DHCP changes
  (see `netconf.sh`); falls back to its DHCP IP if mDNS is unavailable.

```
  Relay IN  <--- D1 (GPIO5)      Fan supply --->[ COM ]
  Relay VCC <--- VIN (5V)                        [ NO  ]---> fan
  Relay GND <--- GND  (common)
```

---

## 3. ESP8266 #2 — `room1-plug` (relay → HTTP server :8081)

Same board and relay wiring as the fan; this one exposes an HTTP on/off plug and
reports a (simulated) power figure.

| Relay module | → NodeMCU pin | Note |
|--------------|---------------|------|
| VCC          | **VIN (5V)**  | |
| IN           | **D1 = GPIO5**| active-LOW |
| GND          | **GND**       | common ground |

- Same strapping-pin caution as the fan (use **D1/GPIO5**).
- Optional: onboard LED (**GPIO2**, active-LOW) mirrors plug state for a visible demo.
- Advertises mDNS `room1-plug.local`.

---

## Quick reference

| Signal | ESP32 (sensor) | ESP8266 (fan) | ESP8266 (plug) |
|--------|----------------|---------------|----------------|
| Sensor/relay data | GPIO4 (DHT DATA) | GPIO5 / D1 (relay IN) | GPIO5 / D1 (relay IN) |
| Power to peripheral | 3V3 (DHT) | VIN 5V (relay coil) | VIN 5V (relay coil) |
| Status LED | GPIO2 | GPIO2 | GPIO2 |
| Active level | — | LOW = on | LOW = on |

Pins are also defined at the top of each firmware's `main.cpp` (`DHT_PIN`,
relay pin) — keep this table and the code in sync.
