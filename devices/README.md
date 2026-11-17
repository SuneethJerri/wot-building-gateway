# devices

Python 3. Install once:

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt

## What's here

- `coap_relay.py` - fan relay over CoAP (`/status`, `/on`, `/off`)
- `mqtt_relay.py` - same relay over MQTT topics
- `http_plug.py` - fake smart plug (`/status`, `/on`, `/off`)
- `common.py` - the GPIO relay class both relays use
- `sim/` - 10-100 device simulator
- `run.sh` - starts one device

Paths, topics and payloads are in the code and the generated TDs (`../tds/`).

## Running

No hardware? Add `--mock` to the relays, they just keep the state in memory.

    ./run.sh coap --mock
    ./run.sh mqtt --mock --broker 192.168.1.10
    ./run.sh http

### Per-device GUI

Each device can serve its own small web panel with `--gui PORT` (standard library only,
runs in a background thread; `gui.py` is the shared helper). This mirrors the Level-3 story
where each ESP32 hosts its own page.

    python3 sensor.py --mock --gui 8090      # temp/humidity + sparkline; Heat/Cool nudge buttons
    python3 coap_relay.py --mock --gui 8092   # fan on/off status + switch buttons
    python3 http_plug.py --gui 8091           # plug on/off + power + switch buttons (native HTTP stays :8081)

Open `http://<host>:<gui-port>/`. The sensor's **nudge** buttons add/subtract a manual
offset to the reading — handy in a demo to push the temperature across the fan thresholds
on purpose. Endpoints: `GET /state` (JSON), `POST /action/<label>`.

`sensor.py --mock --fan-status URL` makes the mock room react to the fan: while the URL (the
fan's status, e.g. `http://GW:8080/room1-fan/properties/status` through the gateway) says on,
the room cools up to 6 °C below the swing. The **Open/close window** button stops the cooling,
which triggers the energy manager's "fan fault or window open" alert. `lab.sh level1` sets it.

`run.sh coap` kills a running mqtt relay and the other way round, that's the swap
for the interoperability test. On the Pi without `--mock` the relay uses GPIO 17
(`--pin` to change it).

## Trying them by hand

    curl localhost:8081/status
    curl -X POST localhost:8081/on
    coap-client -m get coap://localhost/status
    coap-client -m put coap://localhost/on
    mosquitto_pub -t building/room1/fan/cmd -m on
    mosquitto_sub -t building/room1/fan/status

## Test

    python test_devices.py

Covers the CoAP relay and the plug. The MQTT relay needs a broker, test it by hand
with the mosquitto commands above.
