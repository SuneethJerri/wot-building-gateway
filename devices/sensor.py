import argparse
import json
import random
import time

import paho.mqtt.client as mqtt

# topics from CONTRACT.md: <base>/temp, /humidity (retained numbers), /overheat (event)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--base", default="building/room1")
    p.add_argument("--pin", type=int, default=4, help="BCM pin of the DHT22")
    p.add_argument("--mock", action="store_true", help="random walk instead of a DHT22")
    p.add_argument("--threshold", type=float, default=35.0, help="overheat event above this degC")
    p.add_argument("--offset", type=float, default=0.0, help="calibration, added to temperature")
    a = p.parse_args()
    if not a.mock:
        import adafruit_dht
        import board
        dht = adafruit_dht.DHT22(getattr(board, f"D{a.pin}"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(a.broker, a.port)
    c.loop_start()
    t, h, hot = 24.0, 50.0, False
    while True:
        if a.mock:
            t += random.uniform(-0.3, 0.4)
            h = min(100, max(0, h + random.uniform(-1, 1)))
        else:
            try:
                t, h = dht.temperature, dht.humidity
            except RuntimeError:  # DHT22 misreads often, just try again
                time.sleep(2)
                continue
        t = round(t + a.offset, 1)
        c.publish(f"{a.base}/temp", str(t), retain=True)
        c.publish(f"{a.base}/humidity", str(round(h, 1)), retain=True)
        if t > a.threshold and not hot:  # one event per crossing
            c.publish(f"{a.base}/overheat", str(t))
        hot = t > a.threshold
        time.sleep(2)


if __name__ == "__main__":
    main()
