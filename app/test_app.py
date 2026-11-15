from app import decide, href

assert decide(29, False, 28, 26) == "switchOn"
assert decide(29, True, 28, 26) is None
assert decide(27, True, 28, 26) is None  # inside the band, no chatter
assert decide(25, True, 28, 26) == "switchOff"
assert decide(25, False, 28, 26) is None
td = {"title": "t", "properties": {"x": {"forms": [{"href": "a", "op": ["readproperty"]}]}}}
assert href(td, "properties", "x", "readproperty") == "a"
print("ok")
