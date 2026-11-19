from argparse import Namespace

import app as appmod
from app import COMMAND, NEEDS, TEMPERATURE, Meter, apply_settings, decide, fan_fault, find, href, policy, price, replay, typed

assert decide(29, False, 28, 26) == "switchOn"
assert decide(29, True, 28, 26) is None
assert decide(27, True, 28, 26) is None  # inside the band, no chatter
assert decide(25, True, 28, 26) == "switchOff"
assert decide(25, False, 28, 26) is None
td = {"title": "t", "properties": {"x": {"forms": [{"href": "a", "op": ["readproperty"]}]}}}
assert href(td, "properties", "x", "readproperty") == "a"

# semantic discovery: another vendor's sensor with its own prefixes, title and names is still found
ctx = ["https://www.w3.org/2022/wot/td/v1.1", {"s": "https://saref.etsi.org/core/", "b": "https://saref.etsi.org/saref4bldg/"}]
vendor = {"@context": ctx, "title": "acme-thermo-7", "b:isContained": {"@id": "urn:building:room1"},
          "properties": {"temp": {"@type": "s:Temperature", "forms": [{"href": "t", "op": "readproperty"}]}}}
hall = {**vendor, "title": "hall-thermo", "b:isContained": {"@id": "urn:building:hall"}}      # wrong room
sim = {"@context": ctx, "title": "sim0", "properties": {"temperature": {"@type": "s:Temperature"}}}  # in no room
fan = {"@context": ctx, "@type": ["b:Fan", "s:Actuator"], "title": "ceiling", "b:isContained": {"@id": "urn:building:room1"},
       "actions": {"go": {"@type": "s:OnCommand"}, "stop": {"@type": "s:OffCommand"}}}
appmod.get = lambda url: [sim, hall, fan, vendor]
assert find("dir", "urn:building:room1", TEMPERATURE) is vendor
assert typed(vendor, "properties", TEMPERATURE) == "temp"
assert find("dir", "urn:building:room1", NEEDS["fan"]) is fan
assert typed(fan, "actions", COMMAND["switchOff"]) == "stop"
assert find("dir", "urn:building:hall", TEMPERATURE) is hall
for missing in (lambda: find("dir", "urn:building:room1", NEEDS["plug"]), lambda: typed(fan, "properties", TEMPERATURE)):
    try:
        missing()
        raise AssertionError("should not be found")
    except LookupError:
        pass

assert [price(h) for h in (3, 12, 19, 23)] == [6.0, 8.0, 10.0, 6.0]

a = Namespace(hi=28, lo=26, setback=4, open=9, close=18, cap=100)
assert policy(12, 25, False, a) == (None, True)            # office hours, cool: plug allowed
assert policy(12, 29, False, a) == ("switchOn", False)     # fan 50 W + plug 60 W > cap: shed the plug
assert policy(20, 29, False, a) == (None, False)           # after hours: band raised, plug off
assert policy(20, 33, False, a) == ("switchOn", False)     # after hours but really hot
assert policy(12, 29, False, Namespace(**{**vars(a), "cap": 200})) == ("switchOn", True)
assert policy(12, 23, True, a) == ("switchOff", True)                    # too cool: fan off
assert policy(12, 23, True, a, fan_manual=True) == (None, False)         # switched on by hand: kept on, cap still sheds the plug
assert policy(12, 29, False, a, fan_manual=True) == (None, True)         # switched off by hand: kept off

m = Meter()
m.add(1, 19, 1000, False)    # 1 kWh at the 18-22 price
m.add(0.5, 12, 100, True)    # 0.05 kWh at the day price, 30 min too hot
assert m.report() == {"kwh": 1.05, "cost": 10.4, "peak_w": 1000, "hot_min": 30}

plain, smart = replay(a, False), replay(a, True)
assert smart.cost < plain.cost and smart.hot_min <= plain.hot_min, (plain.report(), smart.report())

assert not fan_fault(10, 28, 29, 15)   # not long enough yet
assert fan_fault(15, 28, 28, 15)       # 15 min and no cooler: alert
assert not fan_fault(20, 28, 27.5, 15)  # it is cooling

s = Namespace(**vars(a))
apply_settings(s, {"open": 8, "cap": "150"})
assert (s.open, s.cap, s.close) == (8.0, 150.0, 18)
for bad in ({"open": 19}, {"lo": 30}, {"cap": 0}, {"setback": -1}, {"hi": "nan"}, {"hi": "warm"}, {"x": 1}, [1, 2]):
    try:
        apply_settings(s, bad)
        raise AssertionError(f"accepted {bad}")
    except (ValueError, TypeError):
        pass
assert (s.open, s.cap, s.lo, s.hi) == (8.0, 150.0, 26, 28)  # rejected writes changed nothing
print("ok")
