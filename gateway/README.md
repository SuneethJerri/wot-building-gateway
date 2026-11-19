# gateway

node-wot gateway. Consumes each device TD through its native binding (MQTT, CoAP, HTTP)
and exposes every Thing over HTTP on :8080 with the same names, registering each one in the
Thing Directory (:9000, a small in-memory one in `directory.js`, started by the gateway).

    npm install
    node gateway.js --host PI_IP                      # default: tds/sensor.json fan.json plug.json
    node gateway.js --host PI_IP ../tds/sim           # scale test, a folder of TDs
    node gateway.js ../tds/sensor.json ../tds/fan-mqtt.json ../tds/plug.json   # swap test

A Thing whose TD has forms in more than one protocol (`fan.json`: CoAP + MQTT) gets failover: each
protocol is probed every 2 s, a request that gets no answer in 1 s is retried on the next protocol,
and the choice is readable as the Thing's extra `protocol` property. See "Protocol failover" in the
top README. Concurrent reads of one MQTT form share one request, because node-wot drops a second
subscriber to the same topic and that read would never answer.

Dashboard: `http://HOST:9000/` (`dashboard.html`, served by the Directory). It finds Things by title in
the Directory and calls the gateway, like the app does.

Flags: `--port`, `--dir URL` (use an external Directory, then none is started), `--no-dir`.
Check: `npm test` (failover choice and the Directory; the rest needs devices and a broker).
Not done: WebSocket binding (HTTP long-poll for events), Directory persistence, security.
Tested locally: HTTP plug and CoAP relay through the gateway, MQTT sensor and MQTT relay against an
in-memory broker, app rule end to end. Not tested on a Pi.
