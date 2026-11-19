"""Writes the Thing Descriptions. Usage: python3 gen.py [--broker H] [--coap H] [--plug H]
Hosts go into the hrefs, so rerun when the addresses change (netconf.sh does)."""
import argparse
import json
import pathlib

# Semantic annotations: what each Thing and affordance IS, from ETSI SAREF (core + buildings), so the
# app finds Things by meaning instead of by title. Terms checked against SAREF 3.2.1 / SAREF4BLDG 1.1.2.
CTX = ["https://www.w3.org/2022/wot/td/v1.1",
       {"saref": "https://saref.etsi.org/core/", "s4bldg": "https://saref.etsi.org/saref4bldg/"}]
ROOM = "urn:building:room1"  # an s4bldg:BuildingSpace


def located(td, room):
    """Says which room the device is in (s4bldg:isContained); None = not in a room (simulated sensors)."""
    return {**td, "s4bldg:isContained": {"@id": room}} if room else td


def sensor_td(title, broker, topic, port=1883, room=None):
    base = f"mqtt://{broker}:{port}/{topic}"
    prop = lambda unit, kind: {"@type": kind, "type": "number", "unit": unit, "readOnly": True, "observable": True,
                               "forms": [{"href": None, "op": ["readproperty", "observeproperty"]}]}
    props = {"temperature": prop("degC", "saref:Temperature"), "humidity": prop("%", "saref:Humidity")}
    props["temperature"]["forms"][0]["href"] = f"{base}/temp"
    props["humidity"]["forms"][0]["href"] = f"{base}/humidity"
    return located({"@context": CTX, "@type": "saref:TemperatureSensor", "id": f"urn:dev:{title}", "title": title,
                    "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec", "properties": props,
                    "events": {"overheat": {"data": {"type": "number", "unit": "degC"},
                                            "forms": [{"href": f"{base}/overheat", "op": "subscribeevent"}]}}}, room)


def relay_td(title, kinds, coap_host, broker, room=ROOM):
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
    return located({"@context": CTX, "@type": ["s4bldg:Fan", "saref:Actuator"], "id": f"urn:dev:{title}-{'-'.join(kinds)}",
                    "title": title, "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec",
                    "properties": {"status": {"@type": "saref:OnOffState", **on, "readOnly": True, "forms": st}},
                    "actions": {"switchOn": {"@type": "saref:OnCommand", "forms": on_f},
                                "switchOff": {"@type": "saref:OffCommand", "forms": off_f}}}, room)


def plug_td(title, host, room=ROOM):
    b = f"http://{host}:8081"
    st = {"type": "object", "properties": {"on": {"type": "boolean"}, "power": {"@type": "saref:Power", "type": "number", "unit": "W"}}}
    act = lambda p, kind: {"@type": kind, "output": st, "forms": [{"href": f"{b}/{p}", "op": "invokeaction", "htv:methodName": "POST"}]}
    return located({"@context": CTX, "@type": ["s4bldg:Outlet", "saref:Switch", "saref:Meter"], "id": f"urn:dev:{title}",
                    "title": title, "securityDefinitions": {"nosec": {"scheme": "nosec"}}, "security": "nosec",
                    "properties": {"status": {"@type": "saref:OnOffState", **st, "readOnly": True,
                                              "forms": [{"href": f"{b}/status", "op": "readproperty"}]}},
                    "actions": {"switchOn": act("on", "saref:OnCommand"), "switchOff": act("off", "saref:OffCommand")}}, room)


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
    write(d / "sensor.json", sensor_td("room1-sensor", a.broker, "building/room1", room=ROOM))
    write(d / "fan-coap.json", relay_td("room1-fan", ["coap"], a.coap, a.broker))
    write(d / "fan-mqtt.json", relay_td("room1-fan", ["mqtt"], a.coap, a.broker))
    write(d / "fan.json", relay_td("room1-fan", ["coap", "mqtt"], a.coap, a.broker))  # failover
    write(d / "plug.json", plug_td("room1-plug", a.plug))
