import argparse
import asyncio
import json

import aiocoap
import aiocoap.resource as resource

from common import Relay

JSON = 50  # content format id for application/json


class Status(resource.Resource):
    def __init__(self, relay):
        super().__init__()
        self.relay = relay

    async def render_get(self, request):
        body = json.dumps({"on": self.relay.on}).encode()
        return aiocoap.Message(payload=body, content_format=JSON)


class Switch(resource.Resource):
    def __init__(self, relay, value):
        super().__init__()
        self.relay = relay
        self.value = value

    async def render_put(self, request):
        self.relay.set(self.value)
        return aiocoap.Message(code=aiocoap.CHANGED)

    render_post = render_put


def make_site(relay):
    site = resource.Site()
    site.add_resource(["status"], Status(relay))
    site.add_resource(["on"], Switch(relay, True))
    site.add_resource(["off"], Switch(relay, False))
    return site


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5683)
    p.add_argument("--pin", type=int, default=17)
    p.add_argument("--mock", action="store_true", help="no GPIO, state only")
    p.add_argument("--gui", type=int, default=0, help="serve a device GUI on this port (0 = off)")
    p.add_argument("--mqtt", metavar="BROKER", help="also serve the relay over MQTT, so the gateway can fail over")
    a = p.parse_args()
    relay = Relay(a.pin, a.mock)
    loop, ctx = asyncio.get_running_loop(), None

    async def serve_coap(up):
        nonlocal ctx
        if up and ctx is None:
            ctx = await aiocoap.Context.create_server_context(make_site(relay), bind=(a.host, a.port))
        elif not up and ctx is not None:
            await ctx.shutdown()
            ctx = None

    await serve_coap(True)
    links = {"CoAP": lambda up: asyncio.run_coroutine_threadsafe(serve_coap(up), loop).result()}
    if a.mqtt:
        from mqtt_relay import attach
        links["MQTT"] = attach(relay, a.mqtt)
    live = dict.fromkeys(links, True)

    def set_link(name, up):  # demo trigger: one protocol path goes down, the device keeps running
        links[name](up)
        live[name] = up

    if a.gui:
        from gui import run_gui
        actions = {"Switch on": lambda: relay.set(True), "Switch off": lambda: relay.set(False)}
        if len(links) > 1:
            for name in links:
                actions[f"Drop {name}"] = lambda n=name: set_link(n, False)
                actions[f"Restore {name}"] = lambda n=name: set_link(n, True)
        run_gui(a.gui, "room1 fan", " + ".join(links) + " · relay",
                lambda: {"on": relay.on, **{f"{n} link": up for n, up in live.items()}}, actions)
    print(f"coap relay on {a.host}:{a.port}" + (f", mqtt via {a.mqtt}" if a.mqtt else ""), flush=True)
    await loop.create_future()  # run until killed


if __name__ == "__main__":
    asyncio.run(main())
