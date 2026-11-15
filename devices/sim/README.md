# sim

`python3 sim.py N --broker PI_IP` starts N fake MQTT sensors (10, 25, 50, 100) and writes a
TD for each to `tds/sim/` (not committed). Run it from a different machine than the gateway,
then start the gateway on that folder: `node gateway.js ../tds/sim`.
The real sensor is `devices/sensor.py` (DHT22, `--mock` to try without hardware).
Broker config: `devices/mosquitto.conf` (`mosquitto -c devices/mosquitto.conf`).
