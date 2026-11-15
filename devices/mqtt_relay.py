import argparse
import json

import paho.mqtt.client as mqtt

from common import Relay

CMD = "building/room1/fan/cmd"        # payload: on / off
STATUS = "building/room1/fan/status"  # retained json, {"on": true}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--pin", type=int, default=17)
    p.add_argument("--mock", action="store_true", help="no GPIO, state only")
    a = p.parse_args()
    relay = Relay(a.pin, a.mock)

    def publish():
        c.publish(STATUS, json.dumps({"on": relay.on}), retain=True)

    def on_connect(c, userdata, flags, rc, props=None):
        c.subscribe(CMD)
        publish()

    def on_message(c, userdata, msg):
        cmd = msg.payload.decode().strip().strip('"').lower()  # node-wot may send "on" json-quoted
        if cmd in ("on", "off"):
            relay.set(cmd == "on")
            publish()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(a.broker, a.port)
    print(f"mqtt relay, broker {a.broker}:{a.port}", flush=True)
    c.loop_forever()


if __name__ == "__main__":
    main()
