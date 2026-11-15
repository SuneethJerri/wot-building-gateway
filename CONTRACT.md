# Interface contract (DRAFT)

Agree on this on Day 1, then change it only by telling everyone. Anything marked TBD
gets filled in at the meeting.

## Temperature sensor (MQTT) - P2

| Name | Kind | Type | Unit | Topic |
|------|------|------|------|-------|
| temperature | property | number | degC | `building/room1/temp` |
| humidity | property | number | % | `building/room1/humidity` |
| overheat | event | number (temp when it tripped) | degC | `building/room1/overheat` |

Property topics are retained so a read returns the latest value. Payload is the plain
number, e.g. `27.4`. Published every 2 s.

## Fan relay - P3

Same names whichever protocol it runs on. Only the forms change.

| Name | Kind | Type |
|------|------|------|
| status | property | `{"on": boolean}` |
| switchOn | action | no input |
| switchOff | action | no input |

CoAP (port 5683):
- `GET /status` returns `{"on": true}`
- `PUT /on`, `PUT /off` (POST works too)

MQTT version:
- command topic `building/room1/fan/cmd`, payload `on` or `off`
- status topic `building/room1/fan/status`, retained, same json as above

## Smart plug (HTTP, simulated) - P3

| Name | Kind | Type |
|------|------|------|
| status | property | `{"on": boolean, "power": number}` (W) |
| switchOn | action | no input |
| switchOff | action | no input |

Port 8081: `GET /status`, `POST /on`, `POST /off`. The last two return the new status.

## Gateway and Directory

| Thing | Address |
|-------|---------|
| MQTT broker | Pi (mosquitto, `devices/mosquitto.conf`), port 1883 |
| Gateway HTTP (events are long-poll, no WebSocket yet) | Pi:8080 |
| Thing Directory | Pi:9000 (started by the gateway) |
| CoAP relay | relay host:5683 |
| HTTP plug | plug host:8081 |

## Who runs what during development

Pi runs the broker, gateway and Directory. Devices run on laptops or an ESP32 until the
Pi is wired. Sim runs on a separate machine. Real addresses go into the TDs with `tds/gen.py`.

Thing titles (what the app looks up in the Directory): `room1-sensor`, `room1-fan`, `room1-plug`.
Both fan versions use the title `room1-fan`.

## Repo layout

`devices/` `gateway/` `app/` `eval/` `tds/` `paper/` `docs/`
