# Screenshots

Documentation captures of the Level-1 / Level-1.m work, taken over the phone hotspot with
the laptop running the broker + mock devices and the Raspberry Pi running the gateway.
Captured headless (Chrome DevTools protocol) on 2026-11-16.

| File | What it shows |
|------|---------------|
| `dashboard-room.png` | Single-room dashboard (`/`): live temperature + sparkline, Fan On, Smart Plug On, overheat alerts, and the Things registered in the Directory. |
| `dashboard-scale.png` | Multi-client scale dashboard (`/scale`) at **121 sensors**: aggregate tiles (count, average, min/max, over-threshold), the **Raspberry Pi host stats** card (CPU util, CPU temp, RAM, load, uptime), and the live temperature heatmap (cold→hot, red outline = over threshold). |
| `device-sensor.png` | Sensor device GUI (`:8090`, MQTT) — temperature/humidity + sparkline, with Heat/Cool **nudge** demo controls. |
| `device-plug.png` | Smart-plug device GUI (`:8091`, HTTP) — on/off + power, with switch controls. |
| `device-fan.png` | Fan-relay device GUI (`:8092`, CoAP) — on/off status with switch controls. |

All pages are protocol-agnostic: every reading is resolved through the Thing Descriptions
in the Directory, never a device address. See `../demo-day-runbook.md` for how to bring each
view up and `../../logs/devlog.md` for the build history.
