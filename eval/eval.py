"""Latency + resource harness. Raw CSVs go to raw/ (not committed).
  python3 eval.py latency --gw HOST --plug HOST --coap HOST [-n 200]   direct vs through gateway
  python3 eval.py resources --procs node,mosquitto --seconds 120 --label n50   CPU/RAM sampling (run on the Pi)
  python3 eval.py plot                                                  raw/*.csv -> plots/*.png
  python3 eval.py energy [--rooms 50]          plain thermostat vs energy manager, settings sweep, payback
  python3 eval.py control --seconds 60 [--probe URL]   app control-loop latency + gaps (run a swap test meanwhile)
"""
import argparse
import asyncio
import csv
import glob
import json
import os
import pathlib
import statistics
import sys
import time
import urllib.request
from argparse import Namespace

HERE = pathlib.Path(__file__).parent
RAW = HERE / "raw"
sys.path.insert(0, str(HERE.parent / "app"))
from app import policy_args, replay  # noqa: E402


def http(method, url):
    t = time.perf_counter()
    req = urllib.request.Request(url, data=b"" if method == "POST" else None, method=method,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()
    return (time.perf_counter() - t) * 1000


def latency(a):
    import aiocoap
    RAW.mkdir(exist_ok=True)

    async def coap_run(op):
        ctx = await aiocoap.Context.create_client_context()
        out = []
        for i in range(a.n):
            if op == "read":
                msg = aiocoap.Message(code=aiocoap.GET, uri=f"coap://{a.coap}:5683/status")
            else:
                msg = aiocoap.Message(code=aiocoap.PUT, uri=f"coap://{a.coap}:5683/{'on' if i % 2 else 'off'}")
            t = time.perf_counter()
            await ctx.request(msg).response
            out.append((time.perf_counter() - t) * 1000)
        return out

    gw = f"http://{a.gw}:8080"
    sw = lambda i: "switchOn" if i % 2 else "switchOff"
    cases = {
        ("plug", "read", "direct"): lambda: [http("GET", f"http://{a.plug}:8081/status") for _ in range(a.n)],
        ("plug", "read", "gateway"): lambda: [http("GET", f"{gw}/room1-plug/properties/status") for _ in range(a.n)],
        ("plug", "action", "direct"): lambda: [http("POST", f"http://{a.plug}:8081/{'on' if i % 2 else 'off'}") for i in range(a.n)],
        ("plug", "action", "gateway"): lambda: [http("POST", f"{gw}/room1-plug/actions/{sw(i)}") for i in range(a.n)],
        ("coap", "read", "direct"): lambda: asyncio.run(coap_run("read")),
        ("coap", "read", "gateway"): lambda: [http("GET", f"{gw}/room1-fan/properties/status") for _ in range(a.n)],
        ("coap", "action", "direct"): lambda: asyncio.run(coap_run("action")),
        ("coap", "action", "gateway"): lambda: [http("POST", f"{gw}/room1-fan/actions/{sw(i)}") for i in range(a.n)],
    }
    with open(RAW / f"latency_{int(time.time())}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["device", "op", "path", "ms"])
        for (dev, op, path), fn in cases.items():
            try:
                fn()  # warm-up, discarded
                ms = fn()
            except Exception as e:  # one dead device shouldn't lose the rest
                print("skip", dev, op, path, e)
                continue
            w.writerows([dev, op, path, round(x, 3)] for x in ms)
            s = sorted(ms)
            print(f"{dev:5} {op:6} {path:8} median {statistics.median(ms):7.2f} ms  p95 {s[int(.95 * len(s))]:7.2f} ms")


def resources(a):
    import psutil
    RAW.mkdir(exist_ok=True)
    names = a.procs.split(",")
    watched = {}  # keep Process objects so cpu_percent has a previous sample
    with open(RAW / f"resources_{a.label}_{int(time.time())}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "label", "proc", "cpu_pct", "rss_mb"])
        t0 = time.time()
        while time.time() - t0 < a.seconds:
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                if p.pid == os.getpid():  # our own cmdline contains the names we look for
                    continue
                if any(n in (p.info["name"] or "") or n in " ".join(p.info["cmdline"] or []) for n in names):
                    watched.setdefault(p.pid, p)
            for pid, p in list(watched.items()):
                try:
                    w.writerow([round(time.time() - t0, 1), a.label, p.name(), p.cpu_percent(None), round(p.memory_info().rss / 1e6, 1)])
                except psutil.NoSuchProcess:
                    del watched[pid]
            f.flush()
            time.sleep(1)


def plot(a):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (HERE / "plots").mkdir(exist_ok=True)
    rows = [r for p in sorted(glob.glob(str(RAW / "latency_*.csv"))) for r in csv.DictReader(open(p))]
    if rows:
        groups = sorted({(r["device"], r["op"]) for r in rows})
        fig, axs = plt.subplots(1, len(groups), figsize=(3 * len(groups), 4), squeeze=False)
        for ax, (dev, op) in zip(axs[0], groups):
            data = [[float(r["ms"]) for r in rows if (r["device"], r["op"], r["path"]) == (dev, op, pa)] for pa in ("direct", "gateway")]
            ax.boxplot(data, tick_labels=["direct", "gateway"], showfliers=False)
            ax.set_title(f"{dev} {op}")
            ax.set_ylabel("ms")
        fig.tight_layout()
        fig.savefig(HERE / "plots" / "latency.png", dpi=150)
    res = sorted(glob.glob(str(RAW / "resources_*.csv")))
    if res:
        fig, (c, m) = plt.subplots(1, 2, figsize=(9, 4))
        for p in res:
            r = list(csv.DictReader(open(p)))
            if not r:
                continue
            for ax, key in ((c, "cpu_pct"), (m, "rss_mb")):
                by_t = {}
                for x in r:
                    by_t[float(x["t"])] = by_t.get(float(x["t"]), 0) + float(x[key])
                ax.plot(*zip(*sorted(by_t.items())), label=r[0]["label"])
        c.set_ylabel("CPU %")
        m.set_ylabel("RSS MB")
        for ax in (c, m):
            ax.set_xlabel("s")
            ax.legend()
        fig.tight_layout()
        fig.savefig(HERE / "plots" / "resources.png", dpi=150)
    print("plots in", HERE / "plots")


def energy(a):
    """Business case from the replay (toy thermal model, see app.replay): one room-day under the
    plain thermostat vs the energy manager, a settings sweep, and the payback of the hardware."""
    plain, smart = replay(a, False), replay(a, True)
    print(f"{'one room, one working day':28}{'kWh':>8}{'cost':>8}{'peak W':>8}{'min too hot':>13}")
    for name, m in (("plain thermostat", plain), ("energy manager", smart)):
        print(f"{name:28}{m.kwh:8.3f}{m.cost:8.2f}{m.peak_w:8.0f}{m.hot_min:13.0f}")
    day = plain.cost - smart.cost
    month = day * a.workdays * a.rooms
    hw = a.hw_gateway + a.hw_room * a.rooms
    print(f"saving {100 * day / plain.cost:.0f}%: {day:.2f}/room/day, {month:.0f}/month for {a.rooms} rooms "
          f"({a.workdays} working days); hardware {hw:.0f} -> payback {hw / month:.1f} months\n")
    # cost vs comfort: tighter office band costs more, "too hot" stays fixed at --hi so rows compare
    print(f"settings sweep, too hot = above {a.hi:g} degC in office hours")
    print(f"{'fan on/off degC':>16}{'cap W':>8}{'kWh':>8}{'cost':>8}{'saving':>8}{'peak W':>8}{'min too hot':>13}")
    for hi in (25, 26, 27, 28):
        for cap in (100, 1000):  # 100 W sheds the plug while the fan runs, 1000 W never does
            m = replay(Namespace(**{**vars(a), "hi": hi, "lo": hi - 2, "cap": cap}), True, limit=a.hi)
            print(f"{f'{hi}/{hi - 2}':>16}{cap:8}{m.kwh:8.3f}{m.cost:8.2f}{100 * (1 - m.cost / plain.cost):7.0f}%{m.peak_w:8.0f}{m.hot_min:13.0f}")


def control(a):
    """Polls the energy manager's summary: control-loop time (3 reads + actions through the
    gateway) and every gap where the app lost control, e.g. while the gateway restarts for the
    CoAP -> MQTT swap test."""
    loops, gaps, outages, last, down, seen, t0 = [], [], [], None, None, 0.0, time.time()
    while time.time() - t0 < a.seconds:
        now = time.time()
        if a.probe:  # 20 Hz: how long the gateway itself is unreachable
            try:
                urllib.request.urlopen(a.probe, timeout=1).read()
                if down is not None:
                    outages.append(time.time() - down)
                    print(f"gateway unreachable for {outages[-1]:.2f} s", flush=True)
                    down = None
            except OSError:
                down = down or now
        if now - seen >= 0.2:
            seen = now
            try:
                with urllib.request.urlopen(a.app + "/state", timeout=2) as r:
                    s = json.load(r)
                if s.get("ts") != last:
                    if last is not None and s["ts"] - last > a.gap:
                        gaps.append(s["ts"] - last)
                        print(f"control lost for {s['ts'] - last:.1f} s", flush=True)
                    last = s["ts"]
                    loops.append(s["loop_ms"])
            except (OSError, ValueError, KeyError):
                pass
        time.sleep(0.05)
    if loops:
        q = sorted(loops)
        print(f"control loop: {len(q)} rounds, median {statistics.median(q):.1f} ms, p95 {q[int(.95 * (len(q) - 1))]:.1f} ms, max {q[-1]:.1f} ms")
    print(f"gaps over {a.gap} s: {len(gaps)}" + (f", longest {max(gaps):.1f} s" if gaps else ""))
    if a.probe:
        print(f"gateway outages: {len(outages)}" + (f", longest {max(outages):.2f} s" if outages else ""))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    l = s.add_parser("latency")
    l.add_argument("--gw", default="localhost")
    l.add_argument("--plug", default="localhost")
    l.add_argument("--coap", default="localhost")
    l.add_argument("-n", type=int, default=200)
    r = s.add_parser("resources")
    r.add_argument("--procs", default="node,mosquitto")
    r.add_argument("--seconds", type=int, default=120)
    r.add_argument("--label", default="run")
    s.add_parser("plot")
    e = s.add_parser("energy")
    policy_args(e)
    e.add_argument("--rooms", type=int, default=50)
    e.add_argument("--workdays", type=int, default=22)
    e.add_argument("--hw-room", type=float, default=1500, help="sensor + relay + plug boards per room")
    e.add_argument("--hw-gateway", type=float, default=6000, help="Raspberry Pi gateway")
    c = s.add_parser("control")
    c.add_argument("--app", default="http://localhost:8093")
    c.add_argument("--seconds", type=int, default=60)
    c.add_argument("--gap", type=float, default=3.0, help="report pauses longer than this (normal round is ~2 s)")
    c.add_argument("--probe", help="also poll this URL at 20 Hz, e.g. http://GW:8080/room1-fan/properties/status")
    a = p.parse_args()
    {"latency": latency, "resources": resources, "plot": plot, "energy": energy, "control": control}[a.cmd](a)
