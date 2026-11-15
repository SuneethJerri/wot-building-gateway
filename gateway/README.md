# gateway (P1)

node-wot gateway. Consumes each device TD through its native binding (MQTT, CoAP, HTTP)
and exposes every Thing over HTTP on :8080 with the same names, registering each one in the
Thing Directory (:9000, a small in-memory one in `directory.js`, started by the gateway).

    npm install
    node gateway.js --host PI_IP                      # default: tds/sensor.json fan-coap.json plug.json
    node gateway.js --host PI_IP ../tds/sim           # scale test, a folder of TDs
    node gateway.js ../tds/sensor.json ../tds/fan-mqtt.json ../tds/plug.json   # swap test

Flags: `--port`, `--dir URL` (use an external Directory, then none is started), `--no-dir`.
Check: `npm test` (Directory only; the rest needs devices and a broker).
Not done: WebSocket binding (HTTP long-poll for events), Directory persistence, security.
Tested locally: HTTP plug and CoAP relay through the gateway, MQTT sensor and MQTT relay against an
in-memory broker, app rule end to end. Not tested on a Pi.
