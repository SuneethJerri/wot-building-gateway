"""Temperature -> fan rule. Only knows the Directory URL and Thing titles, never device
addresses or protocols: every URL comes out of a Thing Description form.
python3 app.py --directory http://PI:9000 [--notify-url URL]"""
import argparse
import json
import threading
import time
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def find(directory, title):
    for td in get(directory + "/things"):
        if td["title"] == title:
            return td
    raise SystemExit(f"no Thing called {title!r} in {directory}")


def href(td, kind, name, op):
    for f in td[kind][name]["forms"]:
        if op in (f["op"] if isinstance(f["op"], list) else [f["op"]]):
            return f["href"]
    raise SystemExit(f"{td['title']}.{name} has no {op} form")


def invoke(td, name):
    req = urllib.request.Request(href(td, "actions", name, "invokeaction"), data=b"", method="POST", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def decide(temp, fan_on, hi, lo):
    """Hysteresis so the fan doesn't chatter around one threshold. None = leave it alone."""
    if temp >= hi and not fan_on:
        return "switchOn"
    if temp <= lo and fan_on:
        return "switchOff"


def notify(msg, url):
    print("NOTIFY:", msg, flush=True)
    if url:
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=msg.encode(), method="POST"), timeout=5)
        except OSError as e:
            print("notify failed:", e)


def watch_overheat(sensor, url):
    link = href(sensor, "events", "overheat", "subscribeevent")
    while True:  # node-wot HTTP events are long-poll: one GET blocks until one event arrives
        try:
            with urllib.request.urlopen(link, timeout=None) as r:
                notify(f"overheat: {json.load(r)} degC", url)
        except OSError:
            time.sleep(5)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--directory", default="http://localhost:9000")
    p.add_argument("--sensor", default="room1-sensor")
    p.add_argument("--fan", default="room1-fan")
    p.add_argument("--hi", type=float, default=28.0)
    p.add_argument("--lo", type=float, default=26.0)
    p.add_argument("--period", type=float, default=2.0)
    p.add_argument("--notify-url")
    a = p.parse_args()
    while True:
        # looked up each round, so a swapped fan (CoAP <-> MQTT) is picked up without a restart
        sensor, fan = find(a.directory, a.sensor), find(a.directory, a.fan)
        threading.Thread(target=watch_overheat, args=(sensor, a.notify_url), daemon=True).start()
        try:
            while True:
                temp = get(href(sensor, "properties", "temperature", "readproperty"))
                on = get(href(fan, "properties", "status", "readproperty"))["on"]
                act = decide(temp, on, a.hi, a.lo)
                print(f"temp {temp} fan {'on' if on else 'off'}" + (f" -> {act}" if act else ""), flush=True)
                if act:
                    invoke(fan, act)
                time.sleep(a.period)
        except OSError as e:
            print("gateway unreachable:", e, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
