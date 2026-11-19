# Hardware implementation devlog

Running log for taking the WoT building gateway from mock to real Raspberry Pi hardware.
One entry per working session. Newest at the bottom. Record: what changed, what was
tested, what broke, and any deviation from the original design.

Legend: ✅ done · 🔧 in progress · ⚠️ issue · ↪ design change

---

## 2026-11-16 — Project onboarding

- ✅ Read through the repo. Software side is complete and tested in mock mode
  (gateway, Directory, dashboard, app rule, eval harness, device sims).
- ✅ Added this devlog (project guide and hardware map now live in the README).
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
  passwordless access so deploy scripts can run commands on the Pi.
- ✅ Passwordless SSH confirmed (`ssh pi@10.164.189.4`). Pi toolchain checked:
  Node v20.19.1 ✅, npm 10.8.2 ✅, git 2.30.2 ✅, **Python 3.9.2 ⚠️** (README wants 3.10+ —
  verify before running Python devices on Pi in L2), **mosquitto ❌ not installed** (only
  needed if broker runs on Pi; L1 broker is on laptop).
- 📓 Created `docs/demo-day-runbook.md` — addresses, the hotspot ARP trick, per-level
  bring-up, pre-demo checklist. Linked from the README.

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

### ✅ LEVEL 1.m (multi-client scale) WORKING
- Built a **scale dashboard** `gateway/scale.html` (served at `/scale` via directory.js):
  live temperature **heatmap grid** (cold→hot HSL ramp) + aggregate tiles (count, avg,
  min/max, # over threshold). Protocol-agnostic like the app (TD forms only). Reuses the
  main dashboard's design tokens; linked both ways.
- Reused existing `devices/sim/sim.py N --broker <laptop>` — N fake MQTT sensors + a TD each
  in `tds/sim/`. Gateway loads room TDs + `../tds/sim` together (`start_gateway_scale.sh`).
- Verified N=30 (33 Things) and **N=120 (123 Things)**: `/things` 0.10s, gateway ~35% CPU /
  92 MB RSS on the Pi 4 (2 GB free) — scales with big headroom. Sample reads across sim0..119
  + room1 all live.
- ⚠️ Gotcha: committing reverts `tds/*.json` to committed **localhost** → re-running deploy
  pushed localhost room TDs to the Pi and room1 Things went dead (sim OK). Fix: regenerate
  room TDs with the laptop IP before each deploy. Documented in runbook.
- Next for 1.m: `eval/eval.py resources` to record CPU/RAM vs N (3/30/60/120) on the Pi.

### ✅ Pi host stats on the scale dashboard
- `directory.js`: added `/stats` endpoint reading straight from `/proc` + `/sys` (no deps,
  respecting the moody-Pi rule): CPU util (1s `/proc/stat` sampler), CPU temp
  (`/sys/class/thermal/thermal_zone0/temp`), RAM (`/proc/meminfo`), load, cores, uptime.
- `scale.html`: added a "Raspberry Pi (gateway host)" card with CPU/temp/RAM bars (green→
  amber→red) + load/uptime, polled every 2s.
- Verified live: `{cpuPct, tempC:62.3, memUsedMB:711/3744, load1:2.68, cores:4}`.

### ✅ Per-device GUIs (the "3 clients" request)
- New `devices/gui.py` — stdlib-only embedded web panel (daemon thread), shared by all
  devices via `--gui PORT`. Generic: `GET /state` (dict), `POST /action/<label>`; booleans
  render as On/Off pills, a `temperature` key gets a sparkline. Matches dashboard styling.
  This is the Level-1 stand-in for the self-hosted page each ESP32 will serve in Level 3.
- Wired `--gui` into `sensor.py` (8090), `http_plug.py` (8091), `coap_relay.py` (8092).
- Sensor GUI adds **nudge** buttons (Heat +2°C / Cool −2°C / Clear) — a manual offset for
  pushing temp across the fan thresholds during a demo. Verified end-to-end: nudge +4°C →
  MQTT 32.0 → gateway room1-sensor 32. Fan/plug switch buttons toggle state too.
- devices/README documents `--gui`.

### ✅ LEVEL 1.m / 1.scale COMPLETE
- Added committed `./scale.sh <N>` (repo root): one command to run the scale test —
  regenerates room TDs with the laptop IP, (re)starts N sim sensors, rsyncs (`--delete`),
  restarts the gateway on room + sim, prints the exposed count + `/scale` URL. Addresses
  overridable via env (LAPTOP_IP / PI_IP / PI_USER).
- Fixed two bugs found while writing it: (1) rsync needed `--delete` or the Pi kept stale
  sim TDs from a larger previous N (got 123 when expecting 63); (2) inline ssh background
  launch returned early → switched to a file launcher + separate count step.
- Verified N=60 → 63 Things (sim0..sim59 live, sim119 gone/404, room1-sensor live).
- Level 1 (sim), Level 1.m (scale), per-device GUIs, and Pi host stats: all done & pushed.

---

## 2026-11-17 — Business logic: energy cost manager

- ↪ Professor called the temperature→fan rule a toy. The app is now an **energy cost manager**
  for an office room (`app/app.py` `policy()` + `Meter`):
  - time-of-day tariff (example: night ₹6, day ₹8, evening peak 18–22 ₹10 per kWh), metered from
    the plug's `power` + the fan's rated 50 W;
  - office hours 09–18 keep the hi/lo band; after hours the band is raised 4 °C and the plug is off;
  - power cap 100 W: the plug is shed while the fan runs (fan has priority);
  - day report at midnight: kWh, cost, peak W, minutes too hot in office hours.
- The app registers itself as Thing `room1-energy` (summary served on :8093). The dashboard has
  an "Energy today" card. `lab.sh` runs the app at `SPEED=60` (1 h per minute) from `START=8`.
- ✅ `python3 app/app.py --replay` (toy thermal model, one day): plain 1.74 kWh / ₹13.42 / 110 W
  peak / 3 min too hot vs manager 0.48 kWh / ₹3.84 / 60 W / 3 min → **71% cheaper, same comfort**.
- ✅ End to end against fake HTTP devices + the real Directory: the plug goes off before opening,
  on at 09:00, is shed when the fan starts, comes back when the fan stops, and goes off at 18:00.
  Not yet run on the Pi or with the real mosquitto devices.
- ↪ **Manual override:** dashboard clicks used to be undone within 2 s by the rules. Now a device
  found in a state the app didn't set is left alone for `--override` (30) simulated minutes; the
  energy card shows the minutes left. ✅ Live (Level 1 sim + 50 sim sensors): fan clicked off at
  10:11 while 30 °C, held off until 10:42, then the rule switched it back on.

### "Do all": data points + features (2026-11-17, Level 1 on the laptop, 50 sim sensors)
- ✅ **Fault detection:** fan on 15 min (`--fault`) and the room no cooler than at switch-on →
  "fan fault or window open" (NOTIFY + dashboard banner + per-day count). Demoed with the new
  **Open/close window** button on the mock sensor (`sensor.py --fan-status URL`: the mock room
  now cools while the fan runs, so the live demo isn't a fixed sine any more).
- ✅ **Settings as a writable WoT property** of `room1-energy` (`open close hi lo setback cap`),
  edited from the dashboard. Validated as a whole: bad input → HTTP 400 with the reason, nothing changes.
- ✅ **Cost chart** on the dashboard: manager vs plain thermostat on the same temperatures, price
  bands behind, hover crosshair. **Day history** in `eval/raw/energy_days.csv`, last 7 days on the dashboard.
- ✅ `lab.sh level1`: `SIM=N` option, mock sensor coupled to the fan, default band 28/26 (= app/eval).
- 📊 `eval.py energy`: 71% cheaper per room-day (₹3.84 vs ₹13.42), same comfort; 50 rooms →
  ₹10,534/month, hardware ₹81,000 → **payback 7.7 months**. Sweep: without the power cap the
  saving is 42–50% (tighter band = dearer, 0 min too hot); with the cap 71–73%, because shedding
  the 60 W plug saves more than the 50 W fan costs. With a real AC load that would flip.
  The after-hours setback shows no effect in the replay (modelled evenings cool down below 28 °C
  by themselves); it does in the live demo.
- 📊 Latency, median direct → gateway: plug read 0.44 → 0.79 ms, plug action 0.45 → 0.79,
  CoAP read 0.42 → 0.58, CoAP action 0.34 → 0.52 ms (laptop, not Pi).
- 📊 `eval.py control`: control loop (3 reads + actions via gateway) median ~4 ms, p95 ~45 ms.
  Swap CoAP ↔ MQTT: app lost control 0–3 s (was 9.9 s before cutting the retry from 5 s to 1 s).
- 📊 Gateway CPU/RAM with all N sensors read every 2 s (laptop): N=10 1.0% / 172 MB, 25 1.0% / 173,
  50 2.0% / 186, 100 2.9% / 193 MB. Pi numbers still to do.
- ⚠️ Fixed: `eval.py resources` sampled its own process (its cmdline contains the names it
  searches for), so every earlier resources CSV included the harness. Contaminated runs moved
  to `eval/raw/self-sampled/`.
- ⚠️ Fixed: a fast gateway restart could pass between two app rounds, leaving `room1-energy`
  missing from the new Directory. The app now re-registers every 30 s.
- ⚠️ Fixed: a run that starts mid-day no longer saves its partial first day; dates continue after
  the last saved day. (The 0.069 kWh row in `energy_days.csv` is one such partial day from before the fix.)

---

## 2026-11-18 — Dashboard redesign, themes, repo renamed to wot-energy-gateway

- ↪ Design review of the old dashboard scored 22/40: the saving was small grey text, the device
  row read as "the toy", no comfort comparison, midnight wiped the day, and the WoT side was a
  54-row list. Rebuilt both pages in a warm, plain-language card style:
  - the day's verdict as a sentence ("You saved ₹3.26 today, 53% less than a plain thermostat"),
    with comfort compared too;
  - a cost race with price periods and numbered decisions;
  - device cards titled by Thing, saying what automation did and why, with Resume auto;
  - one feed of decisions on the simulated clock;
  - a gateway card with live read time, measured overhead and restart stamp;
  - 7-day history, settings with plain-language validation, and the Directory folded to the room
    Things plus a link to /scale.
- ✅ Colour themes Auto / Warm / Night / Ocean / Lilac in `gateway/theme.css`, shared by both pages;
  every text pair checked ≥ 4.5:1. Figtree is self-hosted (`gateway/fonts`, OFL), since the hotspot
  may be offline.
- ✅ App: events log, plain thermostat comfort and peak, yesterday summary across midnight, read
  latency and gateway-restart stamp, `resumeAuto` action on `room1-energy`. Re-registers every 10 s.
- ✅ Worst-case data pass (₹12,345 amounts, manager worse than plain, 30 long events, offline plug)
  found and fixed: axis ticks for large values, number grouping, history table overflow.
- ⚠️ node-wot crashed once with an uncaught "Form not found" in its event-listener registry; the
  gateway needed a restart. Noted in the README limitations.
- Simulated sensors now stay between 18 and 32 °C (the random walk drifted to 8.7 °C over hours).
- Repo renamed `wot-building-gateway` → `wot-energy-gateway`; CLAUDE.md removed; its demo levels,
  hardware map and network notes moved into the README.

---

## 2026-11-19 — Protocol failover in the gateway

- ↪ Professor suggested the gateway choose the devices' protocol by latency. Choosing purely by
  latency is noise on a LAN (CoAP and MQTT reads differ by ~40 ms here, sub-ms on direct access), so
  it's built as failover first: a TD may list several forms per interaction and leaves the choice to
  the consumer, and the gateway is the consumer.
- `tds/fan.json`: CoAP + MQTT forms for `status`, `switchOn`, `switchOff` (CoAP first = preferred).
  `fan-coap.json` / `fan-mqtt.json` unchanged; Level 3 keeps `fan-coap.json` (ESP8266 is CoAP only).
- Gateway: probes each protocol on `status` every 2 s, 1 s timeout = down, a failed request is retried
  on the next protocol, latency switching only after 5 samples and only if > 2× faster (+5 ms).
  Readable as the extra `protocol` property of `room1-fan`; dashboard shows "via CoAP · MQTT standby"
  and logs switches.
- Fan device: `coap_relay.py --mqtt BROKER` serves both from one process. Panel buttons Drop/Restore
  CoAP (stops the CoAP server) and MQTT (unsubscribes, clears the retained status). MQTT will clears
  the retained status if the device dies, so the broker never answers for a dead fan.
- ⚠️ Found and fixed: node-wot ignores a second subscriber to the same MQTT topic, so two concurrent
  reads of an MQTT property (app + dashboard) left one hanging forever. Affected the sensor too.
  The gateway now shares one in-flight read per MQTT form.
- ⚠️ First version flapped at startup (cold-start probes include connection setup); fixed with the
  5-sample warm-up.
- ✅ Level 1 on the laptop: Drop CoAP → `switchOn` through the gateway still reached the fan over MQTT
  (1.0 s), app lost control once for 3.0 s, back to CoAP within one probe after Restore. Drop MQTT
  while on CoAP: no switch. Both down: reads fail with 500 in 2 s, gateway stays up; recovery from
  either side works. Fan status read: CoAP 1.2 ms vs MQTT 42 ms through the gateway.

---

## 2026-11-19 — Semantic discovery (SAREF)

- ↪ The manager and dashboard found Things by title and used fixed affordance names, so renaming a device
  or bringing another vendor's TD broke them. TDs are JSON-LD; now they say what each device is.
- `tds/gen.py`: `@context` adds `saref:` (https://saref.etsi.org/core/) and `s4bldg:`
  (https://saref.etsi.org/saref4bldg/). Terms checked against SAREF 3.2.1 and SAREF4BLDG 1.1.2 (the
  location relation is `s4bldg:isContained`, not `isContainedIn`; SAREF core has no location term).
  Sensor `saref:TemperatureSensor`, fan `s4bldg:Fan`, plug `s4bldg:Outlet` + `saref:Switch` + `saref:Meter`;
  affordances `saref:Temperature/Humidity/OnOffState/OnCommand/OffCommand/Power`; room
  `urn:building:room1`. All TDs still pass the TD 1.1 JSON Schema. Sims are typed but in no room.
- Gateway now copies `@context`, `@type`s and the room into the TDs it exposes (it dropped them before).
  Its MQTT on/off payload mapping now keys on `OnCommand` instead of the action name `switchOn`.
- App: `find(directory, room, iri)` + `typed(td, kind, iri)`, prefixes expanded from each TD's own
  `@context` (stdlib, no JSON-LD library). `--sensor/--fan/--plug` titles replaced by `--room`.
  Dashboard does the same in JS and labels the cards with whatever title it found.
- ✅ Level 1: normal run unchanged. Rename test (titles `acme-thermo-7` / `ceiling-fan` / `desk-socket`,
  prefixes `s:`/`b:`, names `temp`/`state`/`on`/`off`), gateway restarted only: manager resumed after 2 s and
  switched the fan off through `off`; renamed actions also worked over MQTT with CoAP dropped; the
  dashboard's discovery code (run in Node against the live Directory) found all three.
- ⚠️ Noticed, not changed: the manager only switches the plug on if it switched it off itself. `lab.sh level1`
  starts the mock plug off before the manager runs, so the plug stays off all day unless clicked on.
