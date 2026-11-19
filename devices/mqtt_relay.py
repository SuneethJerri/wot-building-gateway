import argparse
import json
import threading

import paho.mqtt.client as mqtt

from common import Relay

CMD = "building/room1/fan/cmd"        # payload: on / off
STATUS = "building/room1/fan/status"  # retained json, {"on": true}


def attach(relay, broker, port=1883):
    """Serve the relay over MQTT from a background thread. Returns link(up): link(False) makes the
    device go quiet on MQTT, as if that path were cut; link(True) brings it back."""
    live = [True]

    def publish():
        if live[0]:
            c.publish(STATUS, json.dumps({"on": relay.on}), retain=True)

    def on_connect(c, userdata, flags, rc, props=None):
        if live[0]:
            c.subscribe(CMD)
        publish()

    def on_message(c, userdata, msg):
        cmd = msg.payload.decode().strip().strip('"').lower()  # node-wot may send "on" json-quoted
        if cmd in ("on", "off"):
            relay.set(cmd == "on")  # relay.on_change publishes the new status

    def link(up):
        live[0] = up
        if up:
            c.subscribe(CMD)
            publish()
        else:
            c.unsubscribe(CMD)
            c.publish(STATUS, b"", retain=True)  # empty retained = deleted, so a read gets no answer

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.will_set(STATUS, b"", retain=True)  # same if the device dies: the broker must not answer for it
    c.on_connect, c.on_message = on_connect, on_message
    relay.on_change = publish
    c.connect_async(broker, port)  # keeps retrying, so a dead broker doesn't stop the CoAP side
    c.loop_start()
    return link


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--pin", type=int, default=17)
    p.add_argument("--mock", action="store_true", help="no GPIO, state only")
    p.add_argument("--active-low", action="store_true", help="relay switches on when the pin is LOW (SRD-05VDC)")
    a = p.parse_args()
    attach(Relay(a.pin, a.mock, a.active_low), a.broker, a.port)
    print(f"mqtt relay, broker {a.broker}:{a.port}", flush=True)
    threading.Event().wait()  # run until killed


if __name__ == "__main__":
    main()
