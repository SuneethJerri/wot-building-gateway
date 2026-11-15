# WoT Smart Building Gateway

A Raspberry Pi gateway that puts MQTT, CoAP and HTTP devices behind W3C Web of Things
(WoT) Thing Descriptions, so one app can control all of them without knowing the protocol.
The project also measures how much latency and CPU/RAM the gateway adds compared with
talking to the devices directly. The proposal is in `docs/`.

## Architecture

```
 DHT22 sensor ──MQTT──┐
 Fan relay ──CoAP/MQTT┼──► node-wot gateway ──HTTP :8080──► App (temperature → fan rule)
 Smart plug ───HTTP───┘        │
 Simulated sensors ──MQTT──►   └─ registers each Thing ──► Thing Directory :9000 ◄── App lookup
```

- Each device has a Thing Description (TD) with its native protocol forms (`tds/`).
- The gateway consumes those TDs and re-exposes every Thing over HTTP with the same names.
- The app finds Things by title in the Directory and only uses URLs found in the TDs.
- Swapping the fan from CoAP to MQTT changes only which TD the gateway loads; the app is untouched.

## Repository layout

| Folder | What | Owner |
|--------|------|-------|
| `gateway/` | node-wot gateway and small Thing Directory | P1 |
| `devices/` | MQTT sensor, CoAP relay, MQTT relay, HTTP plug, `sim/` simulator | P2, P3 |
| `app/` | temperature to fan rule, notifications | P4 |
| `eval/` | latency harness, CPU/RAM logging, plots | P5 |
| `tds/` | Thing Description generator and generated TDs | P6 |
| `paper/` | report skeleton | P6 |
| `docs/` | proposal and `TODO.csv` task sheet | all |

`CONTRACT.md` defines names, topics, paths and ports. If your code needs something
different, change the contract first and tell the others.

## Quick start (everything on one machine)

Requirements: Node 20+, Python 3.10+, an MQTT broker (mosquitto).

```sh
pip install -r devices/requirements.txt          # add --break-system-packages or use a venv if needed
(cd gateway && npm install)

mosquitto -c devices/mosquitto.conf &            # broker on :1883
python3 tds/gen.py                               # TDs pointing at localhost

python3 devices/sensor.py --mock &               # fake temperature/humidity
python3 devices/coap_relay.py --mock &           # fan relay, no GPIO
python3 devices/http_plug.py &                   # simulated plug

(cd gateway && node gateway.js)                  # gateway :8080, Directory :9000
python3 app/app.py --hi 25 --lo 22               # watch the fan switch
```

Check it: `curl localhost:8080/room1-sensor/properties/temperature`,
`curl localhost:9000/things`.

On the Pi, pass the real addresses: `python3 tds/gen.py --broker PI --coap H --plug H`
and `node gateway.js --host PI_IP`. Each folder's README has the details.

## Swap test

```sh
node gateway.js ../tds/sensor.json ../tds/fan-coap.json ../tds/plug.json   # CoAP fan
node gateway.js ../tds/sensor.json ../tds/fan-mqtt.json ../tds/plug.json   # MQTT fan
```

Run the app unchanged against both. Tag the app `app-frozen` before the test.

## Evaluation

```sh
python3 eval/eval.py latency --gw PI --plug H --coap H -n 200   # direct vs through gateway
python3 eval/eval.py resources --label n50                       # on the Pi, with the simulator running
python3 eval/eval.py plot
python3 devices/sim/sim.py 50 --broker PI                        # N = 10, 25, 50, 100 sensors
```

## Tests

```sh
cd gateway && npm test      # Directory API
python3 app/test_app.py     # rule logic
```

## Status and limits

Tested on one laptop with mock devices and an in-memory broker; not yet on a Pi or real
GPIO/DHT22. Events use HTTP long-poll (no WebSocket binding). The Directory is in-memory.
The remaining work is in `docs/TODO.csv`.

## Git workflow

- One branch each: `p1-gateway`, `p2-mqtt`, `p3-devices`, `p4-app`, `p5-eval`, `p6-tds`.
- Push to your branch every day. P1 merges to `main`, which must always run.
- Don't commit `node_modules`, `.venv` or raw measurement CSVs.

## Safety

Everything runs on the isolated lab network. Never switch mains power with the relay:
low-voltage DC fan only.
