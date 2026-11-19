# tds

Thing Descriptions for the sensor, CoAP relay, MQTT relay and HTTP plug.
`python3 gen.py --broker X --coap Y --plug Z` regenerates them with the real addresses.
Both relay TDs have title `room1-fan` and the same names, only the forms differ, so the
swap test is: point the gateway at `fan-coap.json` or `fan-mqtt.json`, app unchanged.
`fan.json` has both forms per interaction (CoAP first, the preferred one); the gateway fails over
between them.
Validate each one in the W3C TD playground before committing. `sim/` holds the generated
TDs for the simulator.
