# app

Energy cost manager for one office room. Talks only to Thing Descriptions, finds Things through
the Directory, no hard-coded addresses.

    python3 app.py --directory http://PI:9000 [--speed 60 --start 8] [--host LAPTOP_IP] [--notify-url https://ntfy.sh/topic]

Rules (`policy()` in `app.py`):

- **Office hours** (`--open 9 --close 18`): fan on at >= `--hi`, off at <= `--lo` (hysteresis).
- **After hours:** nobody is there, so the band is raised by `--setback` (4 °C) and the plug is
  switched off. It comes back on at opening only if the app switched it off, never against a
  manual "off".
- **Power cap** (`--cap 100` W): the fan (comfort) outranks the plug, so the plug is shed while
  fan + plug would exceed the cap.
- **Manual override** (`--override 30` min): if someone switches the fan or plug by hand (the
  device isn't in the state the app left it in), the rules leave that device alone for that long.
- **Fault detection** (`--fault 15` min): the fan has run that long and the room is no cooler
  than when it started → "fan fault or window open" (printed, POSTed to `--notify-url`, shown
  on the dashboard, counted per day).
- **Metering:** kWh and cost from the plug's `power` reading plus the fan's rated 50 W, priced by
  the time-of-day `TARIFF` at the top of `app.py` (example numbers: edit to your board's).
  Alongside, it meters what the plain thermostat (fan at hi/lo all day, plug always on) would
  have cost on the same temperatures, so the dashboard shows the saving live.
- **Day report** at midnight: kWh, cost, plain cost, peak W, minutes too hot in office hours,
  faults. Appended to `eval/raw/energy_days.csv` (`--history`); the last 7 days are on the dashboard.

The app is itself a Thing, `room1-energy`, registered in the Directory (again every 10 s, since a
fast gateway restart can pass unnoticed). It serves on `--port 8093`:

- `summary` (read): the live numbers, today's cost curve (with temperature), the plain thermostat's
  cost, comfort and peak on the same temperatures, today's decisions as `events` on the simulated
  clock, the last 7 days and yesterday, `read_ms` (one read through the gateway), `loop_ms` (one
  control round) and the last gateway restart with how long control was lost.
- `settings` (read/write): `open close hi lo setback cap`. A write is validated as a whole and
  rejected with HTTP 400 and a reason, so a bad value from the dashboard changes nothing.
- `resumeAuto` (action): ends manual overrides so automation takes the devices back.

`--host` is the address the dashboard's browser uses to reach the app. `--speed 60` runs the
clock at one hour per minute for demos; `--start` sets the starting hour.

The overheat event prints a notification (and POSTs it to `--notify-url` if given). Swap test:
restart the gateway with `fan-mqtt.json` instead of `fan-coap.json`; the app is untouched.
Report numbers: `python3 ../eval/eval.py energy` and `eval.py control`. Check: `python3 test_app.py`.
