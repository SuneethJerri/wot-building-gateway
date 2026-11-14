#!/bin/sh
# ./run.sh coap|mqtt|http [args]
# coap and mqtt are the two versions of the relay, starting one stops the other.
cd "$(dirname "$0")" || exit 1
case "$1" in
  coap|mqtt) pkill -f "(coap|mqtt)_relay.py"; script="$1_relay.py" ;;
  http) pkill -f http_plug.py; script=http_plug.py ;;
  *) echo "usage: $0 coap|mqtt|http [args]"; exit 1 ;;
esac
shift
exec python3 "$script" "$@"
