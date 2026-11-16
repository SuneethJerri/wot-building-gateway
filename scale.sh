#!/usr/bin/env bash
# Level-1 scale test: N fake MQTT sensors on the laptop -> node-wot gateway on the Pi ->
# live heatmap + Pi stats at http://<pi>:9000/scale
#
#   ./scale.sh [N]        N = number of sim sensors (default 30; demo points 3 / 30 / 60 / 120)
#
# Addresses default to this lab's setup; override per machine with env vars, e.g.
#   LAPTOP_IP=192.168.1.50 PI_IP=192.168.1.10 ./scale.sh 60
set -uo pipefail

N="${1:-30}"
LAPTOP_IP="${LAPTOP_IP:-10.164.189.251}"   # where the broker + sim sensors run
PI_USER="${PI_USER:-pi}"
PI_IP="${PI_IP:-10.164.189.4}"             # the gateway host
PI="$PI_USER@$PI_IP"

cd "$(dirname "$0")" || exit 1
PY="devices/.venv/bin/python"; [ -x "$PY" ] || PY="python3"

echo "== scale test: N=$N  laptop=$LAPTOP_IP  pi=$PI_IP =="

# 1. room TDs must point at the laptop, not localhost (committing reverts them to localhost)
python3 tds/gen.py --broker "$LAPTOP_IP" --coap "$LAPTOP_IP" --plug "$LAPTOP_IP"

# 2. (re)start N sim sensors on the laptop; each writes a TD to tds/sim/
pkill -f "sim/sim.py" 2>/dev/null || true
sleep 1
setsid "$PY" devices/sim/sim.py "$N" --broker "$LAPTOP_IP" > /tmp/wot-sim.log 2>&1 < /dev/null &
sleep 3
echo "   sim: $(ls tds/sim/ 2>/dev/null | wc -l) TDs, $(pgrep -fc 'sim/sim.py' || echo 0) proc running"

# 3. push gateway code + all TDs to the Pi. --delete mirrors tds/sim so a smaller N removes
#    the leftover TDs from a bigger previous run (sim.py clears them only on the laptop).
#    Excluded paths (node_modules) are protected from deletion by rsync.
rsync -a --delete --exclude node_modules --exclude .git gateway tds "$PI":~/wot-building-gateway/ || {
  echo "!! rsync failed - is the Pi reachable? (hotspot trick: ping the laptop from the Pi once)"; exit 1; }

# 4. (re)start the gateway on the Pi loading the room TDs + the sim folder (file launcher = reliable detach)
ssh "$PI" "cat > ~/start_gateway_scale.sh <<EOF
#!/bin/bash
cd ~/wot-building-gateway/gateway || exit 1
pkill -f 'node gateway.js' 2>/dev/null
sleep 1
setsid node gateway.js --host $PI_IP ../tds/sensor.json ../tds/fan-coap.json ../tds/plug.json ../tds/sim > ~/gateway.log 2>&1 < /dev/null &
echo launched \\\$!
EOF
chmod +x ~/start_gateway_scale.sh && bash ~/start_gateway_scale.sh"

sleep 10
echo "   exposed $(ssh "$PI" "grep -c '^exposed' ~/gateway.log" 2>/dev/null) things on the Pi"
echo "== done. open  http://$PI_IP:9000/scale   (stop sim: pkill -f sim/sim.py) =="
