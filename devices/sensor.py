import argparse
import json
import math
import random
import time
import urllib.request

import paho.mqtt.client as mqtt

# topics: <base>/temp, /humidity (retained numbers), /overheat (event)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--base", default="building/room1")
    p.add_argument("--pin", type=int, default=4, help="BCM pin of the DHT11")
    p.add_argument("--mock", action="store_true", help="random walk instead of a DHT11")
    p.add_argument("--threshold", type=float, default=35.0, help="overheat event above this degC")
    p.add_argument("--offset", type=float, default=0.0, help="calibration, added to temperature")
    p.add_argument("--gui", type=int, default=0, help="serve a device GUI on this port (0 = off)")
    p.add_argument("--fan-status", help="mock only: URL of the fan's status ({on}); while it runs the room cools")
    a = p.parse_args()
    if not a.mock:
        import adafruit_dht
        import board
        dht = adafruit_dht.DHT11(getattr(board, f"D{a.pin}"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(a.broker, a.port)
    c.loop_start()
    # shared with the GUI; nudge = manual demo offset, window open = the fan can't cool the room
    live = {"temperature": 24.0, "humidity": 50.0, "nudge": 0.0, "window": False, "cooling": 0.0}
    if a.gui:
        from gui import run_gui
        run_gui(a.gui, "room1 sensor", "MQTT · sensor",
                lambda: {k: live[k] for k in ("temperature", "humidity", "nudge", "window", "cooling")},
                {"Heat +2°C": lambda: live.update(nudge=live["nudge"] + 2),
                 "Cool −2°C": lambda: live.update(nudge=live["nudge"] - 2),
                 "Clear nudge": lambda: live.update(nudge=0.0),
                 "Open/close window": lambda: live.update(window=not live["window"])})
    t, h, hot = 24.0, 50.0, False
    while True:
        if a.mock:
            t = 27 + 4 * math.sin(time.time() / 20) + random.uniform(-0.2, 0.2)  # slow swing, crosses 26 and 28
            if a.fan_status:  # ponytail: crude room model, the running fan pulls up to 6 degC off the swing
                try:
                    with urllib.request.urlopen(a.fan_status, timeout=2) as r:
                        fan = json.load(r)["on"]
                except (OSError, ValueError, KeyError, TypeError):
                    fan = False
                cooling = min(6.0, live["cooling"] + 0.6) if fan and not live["window"] else max(0.0, live["cooling"] - 0.3)
                live["cooling"] = round(cooling, 1)
                t -= cooling
            h = min(100, max(0, h + random.uniform(-1, 1)))
        else:
            try:
                t, h = dht.temperature, dht.humidity
            except RuntimeError:  # DHT sensors misread often, just try again
                time.sleep(2)
                continue
        t = round(t + a.offset + live["nudge"], 1)  # live["nudge"] = GUI demo control
        live["temperature"], live["humidity"] = t, round(h, 1)
        c.publish(f"{a.base}/temp", str(t), retain=True)
        c.publish(f"{a.base}/humidity", str(round(h, 1)), retain=True)
        if t > a.threshold and not hot:  # one event per crossing
            c.publish(f"{a.base}/overheat", str(t))
        hot = t > a.threshold
        time.sleep(2)


if __name__ == "__main__":
    main()
