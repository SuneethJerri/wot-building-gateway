# devices (P3, plus P2's MQTT sensor and simulator)

Python 3. Install once:

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt

## What's here

- `coap_relay.py` - fan relay over CoAP (`/status`, `/on`, `/off`)
- `mqtt_relay.py` - same relay over MQTT topics
- `http_plug.py` - fake smart plug (`/status`, `/on`, `/off`)
- `common.py` - the GPIO relay class both relays use
- `sim/` - P2's 10-100 device simulator
- `run.sh` - starts one device

Paths, topics and payloads are in the code and the generated TDs (`../tds/`).

## Running

No hardware? Add `--mock` to the relays, they just keep the state in memory.

    ./run.sh coap --mock
    ./run.sh mqtt --mock --broker 192.168.1.10
    ./run.sh http

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
