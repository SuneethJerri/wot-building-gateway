# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this is

A W3C **Web of Things (WoT)** smart-building gateway (class lab project). Heterogeneous
devices (MQTT / CoAP / HTTP) are each described by a **Thing Description (TD)**. A
**node-wot gateway** consumes those TDs and re-exposes every Thing over plain HTTP with
the same names, registering each in an in-memory **Thing Directory**. A thin **app** runs
a temperature→fan rule knowing only the Directory URL and Thing *titles* — never device
addresses or protocols (every URL comes from a TD form). Swapping the fan CoAP↔MQTT means
loading a different TD; the app is untouched. The project also measures the latency and
CPU/RAM overhead the gateway adds.

## Layout

| Folder | What |
|--------|------|
| `gateway/` | `gateway.js` (node-wot, HTTP :8080), `directory.js` (Directory :9000 + `dashboard.html`) |
| `devices/` | `sensor.py` (MQTT), `coap_relay.py`, `mqtt_relay.py`, `http_plug.py`, `common.py` (GPIO `Relay`), `sim/` |
| `app/` | `app.py` temperature→fan rule + overheat notify |
| `tds/` | `gen.py` generates TDs; `sensor/plug/fan-coap/fan-mqtt.json` |
| `eval/` | latency + resource harness, plots |

## Demo levels (fallback strategy — see `logs/devlog.md`)

1. **Simulation** — all mocked, nice GUI on host laptop. Zero hardware risk.
2. **RPi 4B all-in-one** — all 3 protocols + real sensor/actuator on one Pi (current design).
3. **Distributed ESP32** — 3 protocols on 3 standalone ESP32 boards, one each, into the RPi gateway.

If a level crashes during the demo, fall back to the level below.

## Hardware map (real Pi, no `--mock`)

- Board: **Raspberry Pi 4 Model B**.
- **DHT11 temp/humidity sensor** → BCM **GPIO4** (`board.D4`), via `adafruit_dht`. `sensor.py --pin 4`.
  NOTE: `sensor.py` still constructs `adafruit_dht.DHT22` — change to `DHT11` for real hardware.
- **SRD-05VDC-SL-C relay** (SONGLE, 5 V, **active-LOW** input) driving the fan → BCM **GPIO17**,
  via `gpiozero.OutputDevice`. `coap_relay.py --pin 17`. NOTE: `common.py` is active-high by
  default; set `active_high=False` so on/off match the module.
- **MQTT broker**: mosquitto on `:1883`. Topics under `building/room1/` (`/temp`, `/humidity`, `/overheat`, fan `/cmd` + `/status`).
- **Ports**: gateway HTTP `:8080`, Directory/dashboard `:9000`, CoAP `:5683`, HTTP plug `:8081`.
- `--mock` on sensor/relays keeps state in memory (no GPIO) for desk testing.

## Run (one machine, mock)

```sh
mosquitto -c devices/mosquitto.conf &
python3 tds/gen.py
python3 devices/sensor.py --mock &
python3 devices/coap_relay.py --mock &
python3 devices/http_plug.py &
(cd gateway && node gateway.js)        # :8080 + Directory :9000
python3 app/app.py --hi 25 --lo 22
```

On the Pi: `python3 tds/gen.py --broker PI --coap H --plug H` and `node gateway.js --host PI_IP`,
drop `--mock`. Dashboard: http://localhost:9000/

## Tests

- `cd gateway && npm test` — Directory API
- `python3 app/test_app.py` — rule logic (hysteresis)
- `python3 devices/test_devices.py` — CoAP relay + plug

## Conventions

- Interfaces (topics, paths, ports, Thing titles) live in the code and the generated TDs — keep them in sync via `tds/gen.py`, don't hardcode URLs in the app.
- The app must stay protocol-agnostic: resolve everything through Directory + TD forms.
- Keep `--mock` paths working so the lab is testable without hardware.

## Working log & runbook

- `logs/devlog.md` — chronological build log; one dated entry per session/change.
- `docs/demo-day-runbook.md` — the demo-day cheat sheet: addresses, per-level bring-up,
  pre-demo checklist, and the **hotspot ARP gotcha** (see below).

## ⚠️ Network gotcha (Realme hotspot)

Shared net is a Realme phone hotspot with **lazy ARP forwarding**: after devices (re)join,
the laptop often can't reach the Pi ("No route to host", ARP FAILED) though addressing is
correct — it is NOT client isolation. **Fix: ping the laptop from the Pi once** to prime the
bridge; a running gateway keeps it warm. Full detail in the runbook.

Pi: `ssh pi@10.164.189.4` (host `raspberrypi`, passwordless key installed). IPs are DHCP —
re-check each session with `hostname -I`.
