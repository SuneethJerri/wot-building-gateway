"""Latency + resource harness. Raw CSVs go to raw/ (not committed).
  python3 eval.py latency --gw HOST --plug HOST --coap HOST [-n 200]   direct vs through gateway
  python3 eval.py resources --procs node,mosquitto --seconds 120 --label n50   CPU/RAM sampling (run on the Pi)
  python3 eval.py plot                                                  raw/*.csv -> plots/*.png
"""
import argparse
import asyncio
import csv
import glob
import pathlib
import statistics
import time
import urllib.request

HERE = pathlib.Path(__file__).parent
RAW = HERE / "raw"


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
    a = p.parse_args()
    {"latency": latency, "resources": resources, "plot": plot}[a.cmd](a)
