"""Energy cost manager for one office room. Only knows the Directory URL and Thing titles, never
device addresses or protocols: every URL comes out of a Thing Description form.
python3 app.py --directory http://PI:9000 [--speed 60 --start 8] [--host LAPTOP_IP] [--notify-url URL]
Report numbers (replay, settings sweep, payback): python3 ../eval/eval.py energy"""
import argparse
import collections
import csv
import datetime
import json
import math
import pathlib
import statistics
import sys
import threading
import time
import urllib.request

# Time-of-day tariff: (from hour, to hour, price per kWh). Example numbers, use your board's.
TARIFF = [(0, 6, 6.0), (6, 18, 8.0), (18, 22, 10.0), (22, 24, 6.0)]
FAN_W, PLUG_W = 50, 60  # rated loads; the fan reports no power, the plug draws ~60 W when on
SETTINGS = ("open", "close", "cap", "hi", "lo", "setback")  # writable from the dashboard
HISTORY = pathlib.Path(__file__).parents[1] / "eval" / "raw" / "energy_days.csv"


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def find(directory, title):
    for td in get(directory + "/things"):
        if td["title"] == title:
            return td
    raise LookupError(f"no Thing called {title!r} in {directory}")


def href(td, kind, name, op):
    for f in td[kind][name]["forms"]:
        if op in (f["op"] if isinstance(f["op"], list) else [f["op"]]):
            return f["href"]
    raise LookupError(f"{td['title']}.{name} has no {op} form")


def invoke(td, name):
    req = urllib.request.Request(href(td, "actions", name, "invokeaction"), data=b"", method="POST", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def decide(temp, fan_on, hi, lo):
    """Hysteresis so the fan doesn't chatter around one threshold. None = leave it alone."""
    if temp >= hi and not fan_on:
        return "switchOn"
    if temp <= lo and fan_on:
        return "switchOff"


def price(hour):
    return next(p for lo, hi, p in TARIFF if lo <= hour < hi)


def policy(hour, temp, fan_on, a, fan_manual=False):
    """The business rules on top of decide(). Office hours: keep the room in the hi/lo band.
    After hours: nobody is there, so relax the band by `setback` and keep the plug off.
    Power cap: the fan (comfort) outranks the plug, so the plug is shed while both would
    exceed `cap`. fan_manual: someone switched the fan by hand, leave it as it is.
    Returns (fan action or None, is the plug allowed on)."""
    occupied = a.open <= hour < a.close
    up = 0 if occupied else a.setback
    act = None if fan_manual else decide(temp, fan_on, a.hi + up, a.lo + up)
    fan_next = {"switchOn": True, "switchOff": False}.get(act, fan_on)
    return act, occupied and (not fan_next or FAN_W + PLUG_W <= a.cap)


def policy_args(p):
    """The business settings, shared with eval/eval.py so the replay uses the same defaults."""
    p.add_argument("--hi", type=float, default=28.0, help="office hours: fan on at or above this")
    p.add_argument("--lo", type=float, default=26.0, help="office hours: fan off at or below this")
    p.add_argument("--setback", type=float, default=4.0, help="after hours the band is raised by this many degC")
    p.add_argument("--open", type=float, default=9.0, help="office opens (hour)")
    p.add_argument("--close", type=float, default=18.0, help="office closes (hour)")
    p.add_argument("--cap", type=float, default=100.0, help="room power cap in W")


def apply_settings(a, new):
    """Write of the settings property (it arrives over the network): validate everything, then
    apply all of it or nothing. Raises ValueError."""
    s = {k: getattr(a, k) for k in SETTINGS}
    for k, v in dict(new).items():
        if k not in s:
            raise ValueError(f"unknown setting {k!r}")
        s[k] = float(v)
    if not all(math.isfinite(v) for v in s.values()):
        raise ValueError("settings must be finite numbers")
    if not 0 <= s["open"] < s["close"] <= 24:
        raise ValueError("need 0 <= open < close <= 24")
    if not s["lo"] < s["hi"]:
        raise ValueError("need lo < hi")
    if s["cap"] <= 0 or s["setback"] < 0:
        raise ValueError("need cap > 0 and setback >= 0")
    vars(a).update(s)


def fan_fault(on_min, temp_at_on, temp, limit_min):
    """Fan has run `limit_min` minutes and the room is no cooler than when it started:
    broken fan, or a window open."""
    return on_min >= limit_min and temp >= temp_at_on


class Meter:
    """One day's totals: energy, cost at the time-of-day price, peak load, minutes too hot."""

    def __init__(self):
        self.kwh = self.cost = self.peak_w = self.hot_min = 0.0

    def add(self, hours, hour, watts, too_hot):
        kwh = watts * hours / 1000
        self.kwh += kwh
        self.cost += kwh * price(hour)
        self.peak_w = max(self.peak_w, watts)
        self.hot_min += 60 * hours * too_hot

    def report(self):
        return {k: round(v, 3) for k, v in vars(self).items()}


def outdoor(hour):
    return 27 + 5 * math.sin(2 * math.pi * (hour - 9) / 24)  # 22 degC at 03:00, 32 degC at 15:00


def replay(a, smart, limit=None):
    """One simulated day in 1-minute steps. plain = today's thermostat with the plug left on.
    limit: "too hot" threshold (default a.hi), fixed when comparing different bands."""
    # ponytail: one-room toy thermal model (leak to outdoors, people/PCs heat, fan cooling, degC/h);
    # replay logged sensor data instead if the numbers have to hold up in the report.
    temp, fan, m = outdoor(0), False, Meter()
    for i in range(24 * 60):
        h = i / 60
        occupied = a.open <= h < a.close
        act, plug = policy(h, temp, fan, a) if smart else (decide(temp, fan, a.hi, a.lo), True)
        fan = {"switchOn": True, "switchOff": False}.get(act, fan)
        m.add(1 / 60, h, FAN_W * fan + PLUG_W * plug, occupied and temp > (limit or a.hi))
        temp += (0.3 * (outdoor(h) - temp) + 1.0 * occupied - 3.0 * fan) / 60
    return m


def load_days(path):
    """The last week of day reports; a missing or damaged file just means no history."""
    try:
        with open(path, newline="") as f:
            return [{k: v if k == "date" else float(v) for k, v in r.items()} for r in csv.DictReader(f)][-7:]
    except (OSError, ValueError, TypeError):
        return []


def save_day(path, row):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    fields = list(row) if new else next(csv.reader(open(path, newline="")), list(row))  # keep an older file's columns
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def register(a):
    """The energy manager is a Thing too: the dashboard finds it by title like any device."""
    base = f"http://{a.host}:{a.port}"
    td = {"@context": "https://www.w3.org/2022/wot/td/v1.1", "id": "urn:app:room1-energy", "title": "room1-energy",
          "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec",
          "properties": {
              "summary": {"type": "object", "readOnly": True, "forms": [{"href": f"{base}/state", "op": "readproperty"}]},
              "settings": {"type": "object", "properties": {k: {"type": "number"} for k in SETTINGS},
                           "forms": [{"href": f"{base}/settings", "op": ["readproperty", "writeproperty"]}]}},
          "actions": {"resumeAuto": {"description": "End manual overrides; automation takes the devices back",
                                     "forms": [{"href": f"{base}/action/resumeAuto", "op": "invokeaction"}]}}}
    req = urllib.request.Request(f"{a.directory}/things/{td['id']}", data=json.dumps(td).encode(), method="PUT")
    urllib.request.urlopen(req, timeout=10).read()


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
    p.add_argument("--plug", default="room1-plug")
    policy_args(p)
    p.add_argument("--override", type=float, default=30.0, help="minutes the rules leave a hand-switched device alone")
    p.add_argument("--fault", type=float, default=15.0, help="minutes the fan may run without the room cooling before an alert")
    p.add_argument("--speed", type=float, default=1.0, help="clock speed, 60 = one hour per minute")
    p.add_argument("--start", type=float, help="clock start hour (default: now)")
    p.add_argument("--host", default="localhost", help="address the dashboard uses to reach this app")
    p.add_argument("--port", type=int, default=8093, help="serves the energy summary and settings")
    p.add_argument("--period", type=float, default=2.0)
    p.add_argument("--history", default=str(HISTORY), help="CSV of day reports")
    p.add_argument("--notify-url")
    a = p.parse_args()

    sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "devices"))
    from gui import run_gui
    live, events, ov = {}, [], {"fan": 0.0, "plug": 0.0}  # ov: manual override ends (elapsed hours)

    def log(kind, text):  # the day's decisions, on the simulated clock, for the dashboard's feed and chart
        events.append({"t": live.get("clock", "--:--"), "h": live.get("h", 0), "kind": kind, "text": text})
        del events[:-60]
        print("EVENT:", kind, text, flush=True)

    def resume():
        ov.update(fan=0.0, plug=0.0)
        log("resume", "Automation was resumed by hand.")

    run_gui(a.port, "room1 energy", "App · energy manager", lambda: dict(live), {"resumeAuto": resume},
            settings=(lambda: {k: getattr(a, k) for k in SETTINGS}, lambda new: apply_settings(a, new)))
    now = time.localtime()
    t0, start = time.time(), a.start if a.start is not None else now.tm_hour + now.tm_min / 60
    elapsed = lambda: (time.time() - t0) * a.speed / 3600  # simulated hours since start
    date0, days, partial = datetime.date.today(), load_days(a.history), start % 24 != 0
    try:  # a sped-up run continues after the last saved day instead of reusing today's date
        date0 = max(date0, datetime.date.fromisoformat(days[-1]["date"]) + datetime.timedelta(days=1))
    except (IndexError, ValueError, TypeError):
        pass
    meter, plain, series, faults = Meter(), Meter(), [], 0  # plain: the old thermostat on the same temperatures
    last, last_day, held_off, plain_fan = 0.0, int(start // 24), False, False  # held_off: the app switched the plug off
    want_fan = want_plug = None  # the state the app left each device in; anything else = switched by hand
    fan_since, fan_temp, fault = None, None, False  # when the fan came on, and the temperature then
    held_reason, yesterday, gateway = "", None, None  # why the plug is held off; last closed day; last outage
    reads, down_since = collections.deque(maxlen=90), None  # ms per read through the gateway; outage start
    watching = set()  # one overheat watcher per sensor link, not one per reconnect
    while True:
        try:
            register(a)  # the Directory is in-memory: register after every reconnect, and every 10 s below
            registered = time.time()  # a fast gateway restart (swap test) can pass between two rounds unseen
            # looked up each round, so a swapped fan (CoAP <-> MQTT) is picked up without a restart
            sensor, fan, plug = find(a.directory, a.sensor), find(a.directory, a.fan), find(a.directory, a.plug)
            link = href(sensor, "events", "overheat", "subscribeevent")
            if link not in watching:
                watching.add(link)
                threading.Thread(target=watch_overheat, args=(sensor, a.notify_url), daemon=True).start()
            while True:
                tick = time.perf_counter()
                if time.time() - registered > 10:
                    register(a)
                    registered = time.time()
                el = elapsed()
                h, day = (start + el) % 24, int((start + el) // 24)
                if day != last_day:  # midnight: close the day
                    row = {"date": str(date0 + datetime.timedelta(days=last_day)), **meter.report(),
                           "plain_cost": round(plain.cost, 3), "faults": faults, "plain_hot_min": round(plain.hot_min, 1)}
                    if partial:  # started mid-day: its totals would understate the day, keep them out of the history
                        print("DAY REPORT (partial day, not saved):", row, flush=True)
                    else:
                        print("DAY REPORT:", row, flush=True)
                        days = (days + [row])[-7:]
                        try:
                            save_day(a.history, row)
                        except OSError as e:
                            print("could not save day report:", e, flush=True)
                    yesterday = {**row, "partial": partial}  # survives midnight on screen
                    meter, plain, series, faults, last_day, partial = Meter(), Meter(), [], 0, day, False
                    events.clear()
                hours, last = el - last, el
                live.update(clock=f"{int(h):02d}:{int(h % 1 * 60):02d}", h=round(h, 3))
                t = time.perf_counter()
                temp = get(href(sensor, "properties", "temperature", "readproperty"))
                on = get(href(fan, "properties", "status", "readproperty"))["on"]
                ps = get(href(plug, "properties", "status", "readproperty"))
                reads.append((time.perf_counter() - t) * 1000 / 3)
                if down_since is not None:  # first good round after the gateway went away (e.g. the swap test)
                    gateway = {"t": live["clock"], "lost_s": round(time.time() - down_since, 1)}
                    log("gateway", f"The gateway came back; control resumed after {gateway['lost_s']} s.")
                    down_since = None
                if want_fan is not None and on != want_fan:
                    ov["fan"] = el + a.override / 60
                    log("manual", f"The fan was switched {'on' if on else 'off'} by hand; automation waits {a.override:g} min.")
                if want_plug is not None and ps["on"] != want_plug:
                    ov["plug"], held_off = el + a.override / 60, False  # the user owns it now
                    log("manual", f"The plug was switched {'on' if ps['on'] else 'off'} by hand; automation waits {a.override:g} min.")
                occupied = a.open <= h < a.close
                limit = a.hi + (0 if occupied else a.setback)
                act, plug_ok = policy(h, temp, on, a, fan_manual=el < ov["fan"])
                if act:
                    invoke(fan, act)
                    on = act == "switchOn"
                    log("fan", f"The fan came on at {temp} °C." if on else f"The fan went off; the room cooled to {temp} °C.")
                want_plug = ps["on"]
                if el >= ov["plug"]:
                    if ps["on"] and not plug_ok:
                        invoke(plug, "switchOff")
                        held_off, want_plug, ps = True, False, {"on": False, "power": 0.0}
                        held_reason = "cap" if occupied else "schedule"
                        log("shed" if occupied else "schedule",
                            f"The plug went off so fan and plug stay under {a.cap:g} W." if occupied
                            else "The plug went off: the office is closed.")
                    elif not ps["on"] and plug_ok and held_off:  # only undo our own switch-off, never the user's
                        invoke(plug, "switchOn")
                        held_off, want_plug = False, True
                        if held_reason == "schedule":
                            log("open", "The plug came back on: the office is open.")
                        else:
                            log("restore", "The plug came back on: the fan is off.")
                want_fan = on
                if not on:
                    fan_since, fault = None, False
                elif fan_since is None:
                    fan_since, fan_temp = el, temp
                elif not fault and fan_fault((el - fan_since) * 60, fan_temp, temp, a.fault):
                    fault, faults = True, faults + 1
                    log("fault", f"The fan ran {a.fault:g} min and the room is still {temp} °C: fan broken or a window open.")
                    notify(f"room1 fan has run {a.fault:.0f} min and the room is still {temp} degC: fan fault or window open", a.notify_url)
                watts = ps["power"] + FAN_W * on
                meter.add(hours, h, watts, occupied and temp > a.hi)
                plain_fan = {"switchOn": True, "switchOff": False}.get(decide(temp, plain_fan, a.hi, a.lo), plain_fan)
                plain.add(hours, h, PLUG_W + FAN_W * plain_fan, occupied and temp > a.hi)
                point = [round(h, 2), round(meter.cost, 3), round(plain.cost, 3), temp]
                if not series or int(h * 6) != int(series[-1][0] * 6):  # chart: one point per 10 simulated minutes
                    series.append(point)
                loop_ms = round((time.perf_counter() - tick) * 1000, 1)  # 3 reads + any actions, through the gateway
                live.update(ts=round(time.time(), 2), price=price(h), speed=a.speed, temp=temp,
                            occupied=occupied, fan=on, plug=ps["on"], held_off=held_off, watts=watts,
                            plug_reason=held_reason if held_off else "", limit=limit,
                            fan_manual_min=round(max(0, ov["fan"] - el) * 60),
                            plug_manual_min=round(max(0, ov["plug"] - el) * 60),
                            fault=fault, faults=faults, loop_ms=loop_ms, read_ms=round(statistics.median(reads), 2),
                            plain_cost=round(plain.cost, 3), plain_hot_min=round(plain.hot_min, 1),
                            plain_peak_w=round(plain.peak_w),
                            **meter.report(), series=series + [point], days=days, yesterday=yesterday,
                            events=list(events), gateway=gateway, tariff=TARIFF,
                            settings={k: getattr(a, k) for k in SETTINGS})
                print(f"{live['clock']} {price(h)}/kWh temp {temp} fan {'on' if on else 'off'} plug {'on' if ps['on'] else 'off'}"
                      + (f" -> {act}" if act else "") + f" | today {meter.kwh:.3f} kWh cost {meter.cost:.2f}"
                      + f" (plain {plain.cost:.2f}) | {loop_ms} ms", flush=True)
                time.sleep(a.period)
        except (OSError, LookupError) as e:  # gateway restarting or Thing not registered yet
            print("waiting for gateway/Directory:", e, flush=True)
            down_since = down_since or time.time()
            time.sleep(1)  # short: a gateway restart (swap test) is back within seconds


if __name__ == "__main__":
    main()
