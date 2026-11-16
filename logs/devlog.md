# Hardware implementation devlog

Running log for taking the WoT building gateway from mock to real Raspberry Pi hardware.
One entry per working session. Newest at the bottom. Record: what changed, what was
tested, what broke, and any deviation from the original design.

Legend: ✅ done · 🔧 in progress · ⚠️ issue · ↪ design change

---

## 2026-11-16 — Project onboarding

- ✅ Read through the repo. Software side is complete and tested in mock mode
  (gateway, Directory, dashboard, app rule, eval harness, device sims).
- ✅ Added `CLAUDE.md` (project guide + hardware map) and this devlog.
- Baseline hardware map as written in code today:
  - DHT22 → BCM GPIO4 (`adafruit_dht`, `board.D4`)
  - Fan relay → BCM GPIO17 (`gpiozero.OutputDevice`)
  - mosquitto :1883 · gateway :8080 · Directory :9000 · CoAP :5683 · plug :8081
### Hardware on hand
- **Raspberry Pi 4 Model B** (gateway + Pi-connected devices)
- **DHT11** temp/humidity sensor  (NOTE: code currently targets DHT22)
- **SRD-05VDC-SL-C** relay module (SONGLE, 5 V coil — typically **active-LOW** control input)
- 3× **ESP32** (for level-3 standalone demo)

### Three demo levels (fallback strategy — if one crashes, fall back to the one below)
1. **Simulation** — everything mocked, nice GUI on the host laptop. Fully software,
   no hardware risk. (Build on existing `gateway/dashboard.html` + `devices/sim/`.)
2. **RPi all-in-one** — project as-is: all 3 IoT protocols (MQTT/CoAP/HTTP) with real
   sensor + actuator on one **RPi 4B**. This is the current design, minus the DHT22→DHT11
   and relay-polarity fixes.
3. **Distributed ESP32** — the 3 protocols split across **3 standalone ESP32 boards**
   (one protocol each), talking to the RPi gateway. New firmware, biggest change.

### Code changes implied (to tackle per level)
- [ ] L2: `devices/sensor.py` — switch `adafruit_dht.DHT22` → `DHT11`; verify integer/±2°C reads.
- [ ] L2: `devices/common.py` `Relay` — SRD-05VDC is active-low; add `active_high=False`
      (or a `--active-low` flag) so on/off aren't inverted. Confirm with the actual module.
- [ ] L2: confirm DHT11 wiring pin (code default BCM4) and relay pin (BCM17) + common ground/5V.
- [ ] L1: polish dashboard GUI for the laptop-only sim demo.
- [ ] L3: ESP32 firmware — one board per protocol, **matching the current devices**:
      MQTT→sensor, CoAP→fan relay, HTTP→plug. Same TDs/titles as L2, so gateway/app are
      untouched (TD endpoints just point at the ESP32 IPs).

### Decisions
- **Networking (all 3 levels):** every device joins **one shared mobile hotspot** — laptop,
  RPi, and (L3) the ESP32s all on the same SSID/subnet. No direct Ethernet, no per-level net.
  - Caveat: hotspot DHCP hands out IPs that can change between sessions. On demo day, note
    each device's assigned IP (or use `<host>.local` mDNS if available) and pass those to
    `tds/gen.py --broker/--coap/--plug` and `gateway.js --host`. Re-run `gen.py` if IPs change.
  - No pure-laptop fallback — RPi is the gateway at every level by design.
- **Keep levels cleanly separated.** Each level (sim / RPi all-in-one / ESP32) must be
  launchable on its own without disturbing the others — separate run steps/scripts/docs per
  level, no shared mutable state that couples them. Common to all: the **GUI/app runs on the
  laptop** (the app is launched on the laptop; possibly a phone later). RPi is always gateway.
- **Pi setup (fixed for all levels + final demo):** existing lab RPi 4B with its **own
  monitor + keyboard/mouse**, already on the shared network. Laptop connects via **SSH**
  over that network (for pushing/running code); the Pi's own display stays available too.
- L3 protocol↔device mapping: **match current devices** (MQTT=sensor, CoAP=fan relay, HTTP=plug).
- Relay output for the demo: **LED / indicator only** — no motor. Show the relay clicking
  + an LED as the "fan". Safest; matches repo safety note (no mains).

---

## 2026-11-16 — ⚠️ BLOCKER: hotspot client isolation

- Pi: `pi@raspberrypi`, IP `10.164.189.4`, SSH enabled. Laptop `10.164.189.251/24`,
  hotspot gateway `10.164.189.28`. Same /24 subnet — addressing is correct.
- Laptop → Pi: `ping` 100% loss, SSH "no route to host", and **ARP for `.4` = FAILED**
  while hotspot gateway `.28` is REACHABLE and pings fine.
- Diagnosis: the mobile hotspot enforces **AP/client isolation** — clients reach the
  internet but not each other. ⚠️ Breaks ALL levels (gateway↔devices, app↔gateway,
  ESP32↔gateway all need client-to-client traffic), not just SSH.
- Fix needed before any further progress — options:
  1. Disable "AP isolation"/"client isolation" in the phone's hotspot settings (many
     Android phones hide/omit this; **iPhone Personal Hotspot usually does NOT isolate**).
  2. Use a real Wi-Fi router or a cheap travel router as the shared AP instead of a phone.
  3. Try a different phone whose hotspot allows client-to-client.
- ↪ Revisit the "single mobile hotspot" decision based on what the phone supports.

### RESOLVED — not isolation, lazy L2 forwarding
- Hotspot = **Realme narzo 60x 5G (realme UI 6.0)**. NOT client isolation.
- Real cause: **asymmetric/lazy ARP forwarding** — the hotspot wouldn't forward the
  laptop's ARP-for-Pi until the Pi initiated traffic first. Symptom was one-directional:
  Pi→laptop ping worked (0% loss) while laptop→Pi failed with ARP FAILED.
- Fix/trick: **ping the laptop FROM the Pi once** to prime the bridge, then laptop→Pi
  works both ways. Keeping the gateway running (constant chatter) keeps the path warm.
  👉 Demo-day note: if the link looks dead, ping laptop from Pi to wake it.
- ✅ Laptop→Pi ping 0% loss, SSH reaches auth. Both bands fine; 2.4 GHz usable for ESP32.
- Laptop SSH key generated (`~/.ssh/id_ed25519`); installing on Pi via `ssh-copy-id` for
  passwordless access so Claude Code can run commands on the Pi.
- ✅ Passwordless SSH confirmed (`ssh pi@10.164.189.4`). Pi toolchain checked:
  Node v20.19.1 ✅, npm 10.8.2 ✅, git 2.30.2 ✅, **Python 3.9.2 ⚠️** (README wants 3.10+ —
  verify before running Python devices on Pi in L2), **mosquitto ❌ not installed** (only
  needed if broker runs on Pi; L1 broker is on laptop).
- 📓 Created `docs/demo-day-runbook.md` — addresses, the hotspot ARP trick, per-level
  bring-up, pre-demo checklist. Linked from `CLAUDE.md`.

### ✅ LEVEL 1 WORKING end-to-end (across the hotspot)
- Laptop: Python 3.10.12, mosquitto already on `0.0.0.0:1883` anon (used as-is, service
  untouched), Node 22. Device deps in isolated venv `devices/.venv` (paho-mqtt>=2, aiocoap,
  flask) — note `sensor.py` needs paho-mqtt **v2** (CallbackAPIVersion.VERSION2); system had 1.5.1.
- TDs generated with laptop IP so the Pi gateway dials back to the laptop devices.
- Pi: `npm install` in `gateway/` OK (161 pkgs, only deprecation/audit warnings — left
  untouched). Gateway launched via `~/start_gateway.sh` (detached; plain `&`+setsid in a
  one-liner didn't persist). Logs to `~/gateway.log`, prints "exposed room1-sensor/fan/plug".
- Verified from laptop: Directory `:9000` lists 3 Things; gateway `:8080` returns live
  temperature (saw 23→31 sine swing); fan switchOn/Off → 204 and status flips; dashboard 200.
- App (laptop) against `http://<pi>:9000`: full hysteresis cycle — `temp 24.5 ... -> switchOff`,
  `temp 28.1 ... -> switchOn`. Protocol-agnostic path confirmed (app only used Directory + TD forms).
- ↪ Everything that runs on the Pi for L1 is just the Node gateway — no Python/library
  risk on the moody Pi at this level.
