# Screenshots

Documentation captures of the Level-1 / Level-1.m work. The two dashboard captures are from the
2026-11-18 redesign (laptop, mock devices, 50 simulated sensors, Warm theme); the device panels
are from 2026-11-16. Captured headless (Chrome DevTools protocol).

| File | What it shows |
|------|---------------|
| `dashboard-room.png` | Room dashboard (`/`): the day's saving against a plain thermostat as a sentence, the cost race with price periods and numbered decisions, device cards by Thing title, the decisions feed, gateway timing, last 7 days, settings and the Directory. |
| `dashboard-scale.png` | Scale view (`/scale`) at 51 sensors: headline count, average and range, the live temperature of every sensor (blue cool, pale comfortable, red hot, dashed = no reading), and the gateway host's CPU, temperature and memory. |
| `device-sensor.png` | Sensor device GUI (`:8090`, MQTT) — temperature/humidity + sparkline, with Heat/Cool **nudge** demo controls. |
| `device-plug.png` | Smart-plug device GUI (`:8091`, HTTP) — on/off + power, with switch controls. |
| `device-fan.png` | Fan-relay device GUI (`:8092`, CoAP) — on/off status with switch controls. |

All pages are protocol-agnostic: every reading is resolved through the Thing Descriptions
in the Directory, never a device address. See `../demo-day-runbook.md` for how to bring each
view up and `../../logs/devlog.md` for the build history.
