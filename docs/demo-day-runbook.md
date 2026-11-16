# Demo-day runbook

Everything ad-hoc we learned setting this up, plus the exact steps to bring each level up.
Keep this open during the demo. Newest gotchas get added as we find them.
Companion to the chronological `../logs/devlog.md`.

---

## 0. The setup (fixed for all levels + final demo)

- **RPi 4 Model B** = the WoT gateway. Has its **own monitor + keyboard/mouse**.
- **Laptop** = runs the app + GUI (and, for Level 1, all the mock devices + broker).
- **Phone hotspot** = the shared network for *everything*: **Realme narzo 60x 5G (realme UI 6.0)**.
- **ESP32 ×3** = Level 3 only (2.4 GHz — the hotspot handles both bands fine).

Current addresses (⚠️ **re-check every session — hotspot DHCP can reassign**):

| Device | Address | Notes |
|--------|---------|-------|
| Pi | `10.164.189.4`, user `pi`, host `raspberrypi` | `ssh pi@10.164.189.4` (passwordless key installed) |
| Laptop | `10.164.189.251` | `ip -4 addr show wlo1` |
| Hotspot gateway | `10.164.189.28` | the phone |

Find current IPs: on Pi `hostname -I`; on laptop `ip -4 addr show wlo1 | grep inet`.
If they changed, update `tds/gen.py --broker/--coap/--plug` + `gateway.js --host` accordingly.

---

## 1. ⚠️⚠️ THE BIG NETWORK GOTCHA — read this first

The **Realme hotspot does lazy / asymmetric ARP forwarding.** After everyone (re)joins the
hotspot, the laptop often **cannot** reach the Pi even though addressing is correct:

- Symptom: laptop→Pi `ping` = 100% loss, `ssh` = "No route to host", `ip neigh` shows the
  Pi as **FAILED/INCOMPLETE**. Meanwhile the hotspot gateway pings fine.
- It is **NOT** client isolation and **NOT** a laptop misconfig. The hotspot just won't
  forward the laptop's ARP-for-Pi until the Pi has sent traffic first.

**THE FIX (do this first, every time the link looks dead):**
```sh
# On the Pi:
ping -c3 10.164.189.251        # ping the LAPTOP once — this primes the hotspot bridge
```
Then laptop→Pi works both ways. Keeping the **gateway running** (constant traffic) keeps the
path warm, so once the demo is up this won't recur. If it ever drops: ping laptop from Pi.

Other triggers that re-break it until you re-prime: changing the hotspot band, toggling the
hotspot off/on, a device rejoining the network.

### Quick link check (laptop)
```sh
ping -c2 10.164.189.4 && ssh pi@10.164.189.4 'echo link-ok'
```
If that fails → go ping the laptop from the Pi, then retry.

---

## 2. SSH / access

- Passwordless key auth is set up: laptop `~/.ssh/id_ed25519` → Pi `pi@10.164.189.4`.
- To re-install after a reflash: `ssh-copy-id pi@<pi-ip>` (needs the Pi password once).
- Pi has its own monitor too, so you always have a local console as backup.

## 3. Pi toolchain (checked 2026-11-16)

| Tool | Version | OK? |
|------|---------|-----|
| Node | v20.19.1 | ✅ gateway needs 20+ |
| npm | 10.8.2 | ✅ |
| git | 2.30.2 | ✅ |
| Python3 | **3.9.2** | ⚠️ README wants 3.10+. Fine for the Node gateway; verify before running Python *devices* on the Pi (Level 2) — check for 3.10-only syntax or just test. |
| mosquitto | **not installed** | ❌ Only needed if the broker runs on the Pi. Level 1 broker is on the laptop. `sudo apt install mosquitto mosquitto-clients` if required. |

## 4. Getting code onto the Pi

Gateway runs on the Pi, so it needs `gateway/` + the generated `tds/*.json`.
```sh
# rsync from laptop repo root (re-run after each change):
rsync -av --exclude node_modules --exclude .git ./ pi@10.164.189.4:~/wot-building-gateway/
# then, once on the Pi:
cd ~/wot-building-gateway/gateway && npm install
```

---

## 5. Bring-up per level  (TODO — fill in as each level is built)

### Level 1 — Simulation (laptop devices + GUI, Pi as gateway)  ✅ VERIFIED 2026-11-16
Laptop mock devices + app + GUI; Pi runs the gateway + Directory. All over the hotspot.

**Laptop** (repo root `~/ESI_project/wot-building-gateway`, laptop IP `10.164.189.251`):
```sh
# broker: system mosquitto already runs on 0.0.0.0:1883 anon — nothing to start.
# (verify: mosquitto_pub -h localhost -t test -m hi)
python3 tds/gen.py --broker 10.164.189.251 --coap 10.164.189.251 --plug 10.164.189.251
# device deps live in an isolated venv (paho-mqtt>=2, aiocoap, flask):
PY=devices/.venv/bin/python
$PY devices/sensor.py --mock &          # MQTT temp/humidity (random walk)
$PY devices/coap_relay.py --mock &      # CoAP fan relay, in-memory
$PY devices/http_plug.py &              # HTTP plug (Flask) on :8081
# helper: scratchpad start script used during setup:
#   bash <scratchpad>/start_devices.sh
```

**Pi** (`pi@10.164.189.4`), one-time: `rsync -a --exclude node_modules --exclude .git
gateway tds pi@10.164.189.4:~/wot-building-gateway/ && ssh pi@... 'cd ~/wot-building-gateway/gateway && npm install'`
```sh
ssh pi@10.164.189.4 'bash ~/start_gateway.sh'   # launcher: node gateway.js --host <pi-ip> ../tds/{sensor,fan-coap,plug}.json
# log: ~/gateway.log  → should print "exposed room1-sensor/fan/plug"
```

**App + GUI** (laptop):
```sh
python3 app/app.py --directory http://10.164.189.4:9000 --hi 28 --lo 25
# open the GUI in the laptop browser:  http://10.164.189.4:9000/
```

**Smoke test from laptop:**
```sh
curl -s http://10.164.189.4:9000/things | python3 -m json.tool      # 3 Things registered
curl -s http://10.164.189.4:8080/room1-sensor/properties/temperature
curl -s -X POST http://10.164.189.4:8080/room1-fan/actions/switchOn   # HTTP 204
```
Expected app output: `temp NN fan off -> switchOn` crossing hi, `-> switchOff` crossing lo.

### Level 1.m — Multi-client scale (3 / 30 / 60 / 120 sim sensors)  ✅ VERIFIED 2026-11-16
Many fake MQTT sensors on the laptop → one gateway on the Pi → **scale dashboard** at
`/scale` (live temperature heatmap + aggregate tiles). Same gateway, just more Things.

**Laptop:**
```sh
# start N fake sensors (writes a TD per sensor to tds/sim/, publishes building/simI/temp):
devices/.venv/bin/python devices/sim/sim.py <N> --broker 10.164.189.251    # N = 3,30,60,120
```

**Pi** — load the room TDs *and* the sim folder (helper: `<scratchpad>/deploy_scale.sh`
rsyncs + restarts):
```sh
rsync -a --exclude node_modules --exclude .git gateway tds pi@10.164.189.4:~/wot-building-gateway/
ssh pi@10.164.189.4 'bash ~/start_gateway_scale.sh'   # node gateway.js --host <pi> ../tds/{sensor,fan-coap,plug}.json ../tds/sim
```

**View:** `http://10.164.189.4:9000/scale` (linked from the main dashboard too).

**⚠️ Gotcha that bit us:** committing reverts `tds/*.json` to the committed **localhost**
versions. You MUST regenerate the room TDs for the environment *before* deploying, or the
Pi's room Things point at the Pi's own localhost and go dead (sim Things still work since
`sim.py` writes fresh laptop-IP TDs):
```sh
python3 tds/gen.py --broker 10.164.189.251 --coap 10.164.189.251 --plug 10.164.189.251
```

**Measured (N=120):** 123 Things, `/things` fetch 0.10s, gateway ~35% CPU / 92 MB RSS on the
Pi (3.7 GB RAM, 2 GB free) — lots of headroom. Resource-vs-N numbers → `eval/eval.py resources`.

### Level 2 — RPi all-in-one (real DHT11 + relay on the Pi)
- [ ] DHT22→DHT11 code change; relay active-low (`active_high=False`)
- [ ] decide where the broker lives (laptop vs install on Pi)
- [ ] wiring: DHT11→GPIO4, SRD-05VDC relay→GPIO17, LED as the "fan"

### Level 3 — Distributed ESP32 (one protocol per board)
- [ ] MQTT=sensor, CoAP=fan, HTTP=plug ESP32 firmware
- [ ] ESP32s on 2.4 GHz hotspot; TDs point at each board's IP

---

## 6. Pre-demo checklist (run in order)
1. Power Pi, confirm it joined the hotspot (`hostname -I` shows `10.164.189.x`).
2. **Prime the bridge: ping the laptop from the Pi.**
3. Laptop link check: `ping -c2 <pi-ip> && ssh pi@<pi-ip> 'echo ok'`.
4. Confirm/refresh IPs in TDs if DHCP moved anything; re-run `gen.py` if so.
5. Start the level's services bottom-up (broker → devices → gateway → app → GUI).
6. Have the fallback level ready (if L3 flakes, fall to L2; if L2, fall to L1).
