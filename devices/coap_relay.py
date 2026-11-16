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
    a = p.parse_args()
    relay = Relay(a.pin, a.mock)
    if a.gui:
        from gui import run_gui
        run_gui(a.gui, "room1 fan", "CoAP · relay",
                lambda: {"on": relay.on},
                {"Switch on": lambda: relay.set(True),
                 "Switch off": lambda: relay.set(False)})
    await aiocoap.Context.create_server_context(make_site(relay), bind=(a.host, a.port))
    print(f"coap relay on {a.host}:{a.port}", flush=True)
    await asyncio.get_running_loop().create_future()  # run until killed


if __name__ == "__main__":
    asyncio.run(main())
