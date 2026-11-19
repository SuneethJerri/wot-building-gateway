#!/usr/bin/env bash
# lab.sh - stop stray processes and bring up EXACTLY what a demo level needs.
# See "Demo levels" in README.md for the fallback strategy.
#
#   ./lab.sh stop            kill all local devices + gateway + app (broker left up)
#   ./lab.sh status          show what is currently running
#   ./lab.sh level1          Level 1 sim: broker + mock devices(+GUIs) + gateway + app, all on this laptop
#   ./lab.sh level2          Level 2: REAL devices + gateway + app  (run this ON the Pi)
#   ./lab.sh level3          Level 3 distributed: broker + gateway + app only; the 3 chips are the devices
#
# Addresses are DHCP; this script auto-detects the laptop IP and (for level3)
# calls ./netconf.sh to refresh every TD/firmware address first.
# Env overrides: LAPTOP_IP, BROKER, FAN_HOST, PLUG_HOST, HI, LO, FAN_TD (gateway's fan TD, default fan.json),
#   SPEED (app clock, default 60 = 1 h per minute), START (clock start hour, default 8),
#   SIM (level1: also run N simulated MQTT sensors, e.g. SIM=50; shown on /scale)
set -uo pipefail
cd "$(dirname "$0")" || exit 1

PY="devices/.venv/bin/python"; [ -x "$PY" ] || PY="python3"
detect_ip(){ ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[0-9.]+'; }
LAPTOP_IP="${LAPTOP_IP:-$(detect_ip)}"; LAPTOP_IP="${LAPTOP_IP:-127.0.0.1}"
HI="${HI:-28}"; LO="${LO:-26}"   # same as the app defaults and eval.py energy
log(){ echo "[lab] $*"; }

start(){ local name="$1"; shift; setsid "$@" >"/tmp/wot-$name.log" 2>&1 </dev/null & log "started $name (pid $!) -> /tmp/wot-$name.log"; }

stop_devices(){ for p in sensor coap_relay mqtt_relay http_plug sim/sim.py; do pkill -f "devices/$p" 2>/dev/null; done; }
stop_infra(){ pkill -f 'node gateway.js' 2>/dev/null; pkill -f 'app/app.py' 2>/dev/null; }

ensure_broker(){
  if ss -ltn 2>/dev/null | grep -q ':1883'; then log "broker already listening on :1883";
  else start broker mosquitto -c devices/mosquitto.conf; sleep 1; fi
}

start_gateway(){ # extra TD/dir args beyond the three rooms are passed through
  # fan.json = CoAP + MQTT forms, the gateway fails over between them; FAN_TD=fan-coap.json for one protocol
  start gateway env -C gateway node gateway.js --host "$LAPTOP_IP" \
      ../tds/sensor.json "../tds/${FAN_TD:-fan.json}" ../tds/plug.json "$@"
}
start_app(){ start app "$PY" app/app.py --hi "$HI" --lo "$LO" --host "$LAPTOP_IP" --speed "${SPEED:-60}" --start "${START:-8}"; }

case "${1:-}" in
  stop)
    log "stopping local devices + gateway + app (broker left running; use 'pkill mosquitto' to stop it)"
    stop_devices; stop_infra; sleep 1; log "stopped." ;;

  status)
    echo "-- device/infra processes --"
    ps -eo pid,etime,cmd | grep -E "devices/(sensor|coap_relay|mqtt_relay|http_plug|sim/sim)\.py|node gateway\.js|app/app\.py" | grep -v grep || echo "  (none running)"
    echo "-- listening ports --"
    ss -ltn 2>/dev/null | grep -E ':(1883|8080|8081|8093|9000|5683)' || echo "  (none of 1883/8080/8081/8093/9000/5683)"
    echo "-- laptop IP: $LAPTOP_IP" ;;

  level1)
    log "Level 1 (simulation, all local on $LAPTOP_IP)"
    stop_devices; stop_infra; sleep 1
    python3 tds/gen.py --broker "$LAPTOP_IP" --coap "$LAPTOP_IP" --plug "$LAPTOP_IP"
    ensure_broker
    # the mock room cools while the fan runs (status read through the gateway, so the swap test still works)
    start sensor     "$PY" devices/sensor.py     --mock --broker "$LAPTOP_IP" --gui 8090 \
        --fan-status "http://$LAPTOP_IP:8080/room1-fan/properties/status"
    start coap_relay "$PY" devices/coap_relay.py --mock --gui 8092 --mqtt "$LAPTOP_IP"   # CoAP + MQTT fan
    start http_plug  "$PY" devices/http_plug.py          --gui 8091
    if [ "${SIM:-0}" -gt 0 ]; then
      start sim "$PY" devices/sim/sim.py "$SIM" --broker "$LAPTOP_IP"; sleep 3; start_gateway ../tds/sim
    else
      sleep 2; start_gateway
    fi
    sleep 8; start_app
    log "dashboard: http://$LAPTOP_IP:9000/   (device GUIs on :8090/8091/8092)" ;;

  level2)
    log "Level 2 (RPi all-in-one). Run this ON the Pi; uses REAL GPIO (no --mock)."
    stop_devices; stop_infra; sleep 1
    python3 tds/gen.py --broker "$LAPTOP_IP" --coap "$LAPTOP_IP" --plug "$LAPTOP_IP"
    ensure_broker
    start sensor     "$PY" devices/sensor.py     --broker "$LAPTOP_IP" --pin 4
    start coap_relay "$PY" devices/coap_relay.py --pin 17 --active-low --mqtt "$LAPTOP_IP"   # SRD-05VDC: LOW = on
    start http_plug  "$PY" devices/http_plug.py
    sleep 2; start_gateway; sleep 6; start_app
    log "dashboard: http://$LAPTOP_IP:9000/" ;;

  level3)
    log "Level 3 (distributed chips). Devices are the ESP32/ESP8266 boards - not launched here."
    stop_devices; stop_infra; sleep 1
    ./netconf.sh                      # refresh TD/firmware addresses for the current network
    ensure_broker
    sleep 1; FAN_TD=fan-coap.json start_gateway; sleep 6; start_app   # the ESP8266 fan speaks CoAP only
    log "now POWER the 3 chips (sensor=ESP32, fan=ESP8266/CoAP, plug=ESP8266/HTTP)."
    log "dashboard: http://$LAPTOP_IP:9000/   (check they appear; see firmware/health-check/chip-registry.md)" ;;

  *)
    sed -n '2,16p' "$0"; exit 1 ;;
esac
