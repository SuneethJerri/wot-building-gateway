"""Writes the Thing Descriptions. Usage: python3 gen.py [--broker H] [--coap H] [--plug H]
Hosts go into the hrefs, so rerun when the contract's TBD addresses are decided."""
import argparse
import json
import pathlib

CTX = "https://www.w3.org/2022/wot/td/v1.1"


def sensor_td(title, broker, topic, port=1883):
    base = f"mqtt://{broker}:{port}/{topic}"
    prop = lambda unit: {"type": "number", "unit": unit, "readOnly": True, "observable": True,
                         "forms": [{"href": None, "op": ["readproperty", "observeproperty"]}]}
    props = {"temperature": prop("degC"), "humidity": prop("%")}
    props["temperature"]["forms"][0]["href"] = f"{base}/temp"
    props["humidity"]["forms"][0]["href"] = f"{base}/humidity"
    return {"@context": CTX, "id": f"urn:dev:{title}", "title": title, "securityDefinitions": {"nosec": {"scheme": "nosec"}},
            "security": "nosec", "properties": props,
            "events": {"overheat": {"data": {"type": "number", "unit": "degC"},
                                    "forms": [{"href": f"{base}/overheat", "op": "subscribeevent"}]}}}


def relay_td(title, kinds, coap_host, broker):
    """One form per protocol in kinds, in that order: the gateway prefers the first and fails over."""
    on = {"type": "object", "properties": {"on": {"type": "boolean"}}}
    st, on_f, off_f = [], [], []
    for kind in kinds:
        if kind == "coap":
            b = f"coap://{coap_host}:5683"
            st.append({"href": f"{b}/status", "op": "readproperty", "contentType": "application/json"})
            on_f.append({"href": f"{b}/on", "op": "invokeaction", "cov:method": "PUT"})
            off_f.append({"href": f"{b}/off", "op": "invokeaction", "cov:method": "PUT"})
        else:
            b = f"mqtt://{broker}:1883/building/room1/fan"
            st.append({"href": f"{b}/status", "op": ["readproperty", "observeproperty"]})
            on_f.append({"href": f"{b}/cmd", "op": "invokeaction"})
            off_f.append({"href": f"{b}/cmd", "op": "invokeaction"})
    return {"@context": CTX, "id": f"urn:dev:{title}-{'-'.join(kinds)}", "title": title,
            "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec",
            "properties": {"status": {**on, "readOnly": True, "forms": st}},
            "actions": {"switchOn": {"forms": on_f}, "switchOff": {"forms": off_f}}}


def plug_td(title, host):
    b = f"http://{host}:8081"
    st = {"type": "object", "properties": {"on": {"type": "boolean"}, "power": {"type": "number", "unit": "W"}}}
    act = lambda p: {"output": st, "forms": [{"href": f"{b}/{p}", "op": "invokeaction", "htv:methodName": "POST"}]}
    return {"@context": CTX, "id": f"urn:dev:{title}", "title": title,
            "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec",
            "properties": {"status": {**st, "readOnly": True, "forms": [{"href": f"{b}/status", "op": "readproperty"}]}},
            "actions": {"switchOn": act("on"), "switchOff": act("off")}}


def write(path, td):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(td, indent=2) + "\n")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--broker", default="localhost")
    a.add_argument("--coap", default="localhost")
    a.add_argument("--plug", default="localhost")
    a = a.parse_args()
    d = pathlib.Path(__file__).parent
    write(d / "sensor.json", sensor_td("room1-sensor", a.broker, "building/room1"))
    write(d / "fan-coap.json", relay_td("room1-fan", ["coap"], a.coap, a.broker))
    write(d / "fan-mqtt.json", relay_td("room1-fan", ["mqtt"], a.coap, a.broker))
    write(d / "fan.json", relay_td("room1-fan", ["coap", "mqtt"], a.coap, a.broker))  # failover
    write(d / "plug.json", plug_td("room1-plug", a.plug))
