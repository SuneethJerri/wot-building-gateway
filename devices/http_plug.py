import argparse
import random

from flask import Flask, jsonify

app = Flask(__name__)
state = {"on": False}
WATTS = 60  # pretend load when the plug is on


def reading():
    power = round(WATTS + random.uniform(-2, 2), 1) if state["on"] else 0.0
    return {"on": state["on"], "power": power}


@app.get("/status")
def status():
    return jsonify(reading())


@app.post("/on")
def on():
    state["on"] = True
    return jsonify(reading())


@app.post("/off")
def off():
    state["on"] = False
    return jsonify(reading())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8081)
    a = p.parse_args()
    app.run(host=a.host, port=a.port)
