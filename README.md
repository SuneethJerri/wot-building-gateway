# WoT smart building gateway

A Raspberry Pi gateway that puts MQTT, CoAP and HTTP devices behind W3C Web of Things
Thing Descriptions, so one app can control all of them without knowing the protocol.
We also measure how much latency and CPU/RAM the gateway adds over talking to the
devices directly. The proposal is in `docs/`.

## Who owns what

| Who | Folder | What |
|-----|--------|------|
| P1 | `gateway/` | node-wot gateway, Pi setup, integration |
| P2 | `devices/sim/` + MQTT sensor | Mosquitto, DHT22 sensor, 10-100 device simulator |
| P3 | `devices/` | CoAP relay, HTTP plug, MQTT relay |
| P4 | `app/` | temperature to fan rule, notifications, swap test, demo |
| P5 | `eval/` | latency harness, CPU/RAM logging, plots |
| P6 | `tds/`, `paper/` | CONTRACT.md, Thing Descriptions, Directory, paper |

## Start here

1. Read `CONTRACT.md`. Names, topics, paths and ports are defined there. If your code
   needs something different, change the contract first and tell the others.
2. Each folder has a README with how to run it.
3. Day 1 is for agreeing on the contract, nobody writes code before that.

## Git

- One branch each: `p1-gateway`, `p2-mqtt`, `p3-devices`, `p4-app`, `p5-eval`, `p6-tds`.
- Push to your branch every day. P1 merges to `main`.
- `main` has to run at all times.
- Don't commit `node_modules`, `.venv` or raw measurement CSVs.

## Network

Everything runs on the isolated lab network. Never switch mains power with the relay,
low voltage DC fan only.
