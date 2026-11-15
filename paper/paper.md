# A WoT gateway for heterogeneous building devices (4 pages)

Each person writes their own section, P6 merges. Numbers come from `eval/plots/`.

## 1. Introduction (P6)
Problem: MQTT, CoAP and HTTP devices, one app. Contribution: TD-based gateway + measured overhead.

## 2. Design (P1, P6)
Contract, Thing Descriptions, gateway proxying, Directory. Figure: architecture.

## 3. Devices and simulator (P2, P3)
DHT22 sensor, CoAP/MQTT relay, HTTP plug, 10-100 simulated sensors.

## 4. Application and swap test (P4)
Temperature rule, notifications. Swap CoAP relay for MQTT relay with the app frozen: what changed (nothing / only the gateway TD list).

## 5. Evaluation (P5)
Latency direct vs gateway (read, action), CPU/RAM at 10/25/50/100 sensors. Figures: latency.png, resources.png.

## 6. Discussion and limits (all)
Single Pi, lab network, HTTP long-poll events, in-memory Directory.

## References
W3C WoT Architecture 1.1, W3C WoT Thing Description 1.1, Eclipse Thingweb node-wot.
