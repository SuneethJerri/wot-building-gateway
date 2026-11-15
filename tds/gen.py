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


def relay_td(title, kind, host):
    on = {"type": "object", "properties": {"on": {"type": "boolean"}}}
    if kind == "coap":
        b = f"coap://{host}:5683"
        st = [{"href": f"{b}/status", "op": "readproperty", "contentType": "application/json"}]
        act = lambda p: [{"href": f"{b}/{p}", "op": "invokeaction", "cov:method": "PUT"}]
        on_f, off_f = act("on"), act("off")
    else:
        b = f"mqtt://{host}:1883/building/room1/fan"
        st = [{"href": f"{b}/status", "op": ["readproperty", "observeproperty"]}]
        on_f = off_f = [{"href": f"{b}/cmd", "op": "invokeaction"}]
    return {"@context": CTX, "id": f"urn:dev:{title}-{kind}", "title": title,
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
    write(d / "fan-coap.json", relay_td("room1-fan", "coap", a.coap))
    write(d / "fan-mqtt.json", relay_td("room1-fan", "mqtt", a.broker))
    write(d / "plug.json", plug_td("room1-plug", a.plug))
