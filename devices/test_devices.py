# quick check, run with: python test_devices.py
# mqtt relay is not covered, it needs a broker (see README)
import asyncio

import aiocoap

import coap_relay
import http_plug
from common import Relay


async def coap_test():
    relay = Relay(mock=True)
    server = await aiocoap.Context.create_server_context(
        coap_relay.make_site(relay), bind=("127.0.0.1", 56830))
    client = await aiocoap.Context.create_client_context()
    uri = "coap://127.0.0.1:56830/"
    await client.request(aiocoap.Message(code=aiocoap.PUT, uri=uri + "on")).response
    assert relay.on
    r = await client.request(aiocoap.Message(code=aiocoap.GET, uri=uri + "status")).response
    assert b'"on": true' in r.payload
    await client.request(aiocoap.Message(code=aiocoap.POST, uri=uri + "off")).response
    assert not relay.on
    await client.shutdown()
    await server.shutdown()


def http_test():
    c = http_plug.app.test_client()
    assert c.get("/status").json == {"on": False, "power": 0.0}
    assert c.post("/on").json["power"] > 50
    assert c.post("/off").json["on"] is False


if __name__ == "__main__":
    http_test()
    asyncio.run(coap_test())
    print("ok")
