#!/usr/bin/env bash
# netconf.sh - re-point the TDs + sensor firmware at the CURRENT network addresses.
#
# All IPs are DHCP on the Realme hotspot, so they change every session and WILL
# change on demo day. Run this once after the laptop, Pi and chips have joined
# the network; it rewrites every address that is baked into a file.
#
#   ./netconf.sh                         # auto laptop IP; fan/plug via mDNS .local names
#   BROKER=10.0.0.5 ./netconf.sh         # broker somewhere else (e.g. the Pi)
#   FAN_HOST=10.0.0.21 PLUG_HOST=10.0.0.22 ./netconf.sh   # pin chip IPs instead of mDNS
#   PI=pi@raspberrypi.local ./netconf.sh # also SSH the Pi and print its current IP
#
# Which host goes into which TD (see tds/gen.py):
#   sensor   -> MQTT broker              = $BROKER    (default: this laptop)
#   fan-coap -> CoAP server ON the chip  = $FAN_HOST  (default: room1-fan.local)
#   plug     -> HTTP server ON the chip  = $PLUG_HOST (default: room1-plug.local)
# Only MQTT is centralised; CoAP/HTTP servers live on the chips, so their TD host
# is each chip's own address. mDNS .local names survive DHCP changes IF the chip
# firmware advertises them and the gateway host can resolve .local (avahi/nss-mdns).
set -uo pipefail
cd "$(dirname "$0")" || exit 1

detect_ip() { ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[0-9.]+'; }

LAPTOP_IP="${LAPTOP_IP:-$(detect_ip)}"; LAPTOP_IP="${LAPTOP_IP:-127.0.0.1}"
BROKER="${BROKER:-$LAPTOP_IP}"
FAN_HOST="${FAN_HOST:-room1-fan.local}"
PLUG_HOST="${PLUG_HOST:-room1-plug.local}"

PI_IP=""
if [ -n "${PI:-}" ]; then
  PI_IP="$(ssh -o ConnectTimeout=4 -o BatchMode=yes "$PI" 'hostname -I' 2>/dev/null | awk '{print $1}')"
  if [ -n "$PI_IP" ]; then echo "[netconf] Pi reachable via $PI -> $PI_IP"
  else echo "[netconf] WARN: could not SSH the Pi via '$PI' (prime the hotspot ARP: ping the laptop from the Pi once)"; fi
fi

echo "[netconf] laptop=$LAPTOP_IP  broker=$BROKER  fan=$FAN_HOST  plug=$PLUG_HOST${PI_IP:+  pi=$PI_IP}"

# 1) regenerate the room TDs with the current hosts
python3 tds/gen.py --broker "$BROKER" --coap "$FAN_HOST" --plug "$PLUG_HOST"
echo "[netconf] TDs regenerated: tds/{sensor,fan-coap,fan-mqtt,plug}.json"

# 2) patch the sensor firmware's broker so a reflash points at the right MQTT host
SEC="firmware/sensor-mqtt/include/secrets.h"
if [ -f "$SEC" ]; then
  sed -i -E "s|(#define[[:space:]]+MQTT_HOST[[:space:]]+\").*(\")|\1$BROKER\2|" "$SEC"
  echo "[netconf] $SEC: MQTT_HOST -> $BROKER"
  echo "[netconf]   if the broker IP changed, reflash the ESP32:"
  echo "[netconf]   (cd firmware/sensor-mqtt && pio run -e esp32dev -t upload)"
else
  echo "[netconf] (no $SEC yet - skipping firmware patch)"
fi

case "$FAN_HOST$PLUG_HOST" in
  *.local*) echo "[netconf] NOTE: fan/plug use mDNS .local - needs chip mDNS firmware + avahi on the gateway host; pass FAN_HOST/PLUG_HOST=<ip> to pin raw IPs." ;;
esac
