# app

The temperature to fan rule. Talks only to Thing Descriptions, finds Things through the
Directory, no hard-coded addresses.

    python3 app.py --directory http://PI:9000 [--hi 28 --lo 26] [--notify-url https://ntfy.sh/topic]

Fan on at >= hi, off at <= lo. The overheat event prints a notification (and POSTs it to
`--notify-url` if given). Swap test: restart the gateway with `fan-mqtt.json` instead of
`fan-coap.json`; the app is untouched. Check: `python3 test_app.py`.
