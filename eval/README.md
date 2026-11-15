# eval

Latency harness (direct vs through gateway), CPU/RAM logging and plots, all in `eval.py`.
Raw timings go in `raw/` (not committed), plots in `plots/`.

    python3 eval.py latency --gw PI --plug PLUG_HOST --coap COAP_HOST -n 200
    python3 eval.py resources --procs node,mosquitto --seconds 120 --label n50   # on the Pi, while sim runs N sensors
    python3 eval.py plot

Run latency from a laptop (not the Pi) so the client doesn't steal Pi CPU. Not covered:
direct MQTT latency (not included).
