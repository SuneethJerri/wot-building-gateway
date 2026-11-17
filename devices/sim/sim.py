"""N fake MQTT sensors (10, 25, 50, 100) + a TD for each, for the scale test.
python3 sim.py 50 --broker PI_IP   # run from a different machine than the gateway
TDs go to tds/sim/, feed that folder to the gateway: node gateway.js ../tds/sim"""
import argparse
import pathlib
import random
import sys
import time

import paho.mqtt.client as mqtt

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "tds"))
from gen import sensor_td, write  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("n", type=int)
    p.add_argument("--broker", default="localhost")
    p.add_argument("--period", type=float, default=2.0)
    p.add_argument("--out", default=str(pathlib.Path(__file__).parents[2] / "tds" / "sim"))
    a = p.parse_args()
    for old in pathlib.Path(a.out).glob("sim*.json"):
        old.unlink()
    for i in range(a.n):
        write(pathlib.Path(a.out) / f"sim{i}.json", sensor_td(f"sim{i}", a.broker, f"building/sim{i}"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(a.broker)
    c.loop_start()
    temps = [random.uniform(20, 28) for _ in range(a.n)]
    print(f"{a.n} sensors every {a.period}s, TDs in {a.out}", flush=True)
    while True:
        for i in range(a.n):
            temps[i] = min(32, max(18, temps[i] + random.uniform(-0.2, 0.2)))  # a random walk drifts away otherwise
            c.publish(f"building/sim{i}/temp", f"{temps[i]:.1f}", retain=True)
            c.publish(f"building/sim{i}/humidity", f"{random.uniform(40, 60):.1f}", retain=True)
        time.sleep(a.period)


if __name__ == "__main__":
    main()
