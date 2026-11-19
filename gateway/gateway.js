// node-wot gateway: consumes device TDs (mqtt/coap/http forms), re-exposes each Thing over HTTP on
// :8080 with the same names, and registers it in the Directory. Clients only see HTTP.
// A Thing whose TD has forms in several protocols (tds/fan.json) gets failover: the gateway probes
// each protocol, uses the TD's first working one, and moves to another when it stops answering.
// usage: node gateway.js [--host H] [--dir URL] [--no-dir] <td.json|folder>...
const fs = require("fs");
const path = require("path");
const { Servient } = require("@node-wot/core");
const { HttpServer, HttpClientFactory } = require("@node-wot/binding-http");
const { MqttClientFactory } = require("@node-wot/binding-mqtt");
const { CoapClientFactory } = require("@node-wot/binding-coap");
const { startDirectory } = require("./directory");

const TIMEOUT_MS = 1000; // multi-protocol Things: a protocol that hasn't answered by then is down
const PROBE_MS = 2000;   // how often each of their protocols is probed
// ponytail: fixed margin. A working protocol is left only for one more than 2x faster (+5 ms), so
// LAN noise (CoAP vs MQTT differ by ~1 ms) never flips it; tune both if a real network needs it.
const SWITCH_X = 2, SWITCH_MS = 5;
const WARMUP = 5; // samples before latency counts: the first reads include connection setup

const scheme = (form) => form.href.split(":")[0];
const isMqtt = (form) => /^mqtt/.test(form.href);

// The protocol to use: the TD's order is the preference, skip ones that are down, and stay on a
// working one unless another is clearly faster (smoothed latency).
function pick(order, health, active) {
  const up = order.filter((p) => health[p].ok);
  if (!up.includes(active)) return up[0] ?? active;
  if (up.some((p) => health[p].n < WARMUP)) return active;
  const best = up.reduce((a, b) => (health[b].ms < health[a].ms ? b : a));
  return health[best].ms * SWITCH_X + SWITCH_MS < health[active].ms ? best : active;
}

function timeout(promise, ms) {
  let t;
  const late = new Promise((_, no) => { t = setTimeout(() => no(new Error(`no answer in ${ms} ms`)), ms); });
  return Promise.race([promise, late]).finally(() => clearTimeout(t));
}

async function proxy(wot, consumed, td) {
  // keep what the Thing is (@context, @type, its room) but not the device's own addresses or security
  const { id, base, forms, properties, actions, events, security, securityDefinitions, ...meta } = td;
  const model = { ...meta, id: "urn:gw:" + td.title, properties: {}, actions: {}, events: {} };
  const strip = ({ forms, ...rest }) => rest;
  for (const [n, p] of Object.entries(td.properties || {})) model.properties[n] = { ...strip(p), observable: false };
  for (const [n, a] of Object.entries(td.actions || {})) model.actions[n] = strip(a);
  for (const [n, e] of Object.entries(td.events || {})) model.events[n] = strip(e);

  const protos = [...new Set(Object.values({ ...td.properties, ...td.actions }).flatMap((a) => a.forms.map(scheme)))];
  const multi = protos.length > 1;
  const link = { active: protos[0], health: Object.fromEntries(protos.map((p) => [p, { ok: true, ms: null, n: 0 }])), switched: null };
  if (multi) model.properties.protocol = { type: "object", readOnly: true, observable: false,
    description: "Which protocol the gateway uses for this Thing, and each protocol's health" };

  const switchTo = (p, reason) => {
    console.log(`${td.title}: ${link.active} -> ${p} (${reason === "down" ? `${link.active} stopped answering` : `${p} is faster`})`);
    link.switched = { from: link.active, to: p, reason, at: Date.now() };
    link.active = p;
  };
  const seen = (h, ms) => { h.ok = true; h.ms = h.n++ ? 0.7 * h.ms + 0.3 * ms : ms; };

  // node-wot ignores a second subscriber to an MQTT topic, so a concurrent MQTT read would never
  // answer: concurrent reads of the same MQTT form share one.
  const inflight = new Map();
  const read = (n, i) => {
    const go = () => consumed.readProperty(n, { formIndex: i }).then((out) => out.value());
    if (!isMqtt(td.properties[n].forms[i ?? 0])) return go();
    const key = `${n}#${i}`;
    if (!inflight.has(key)) inflight.set(key, go().finally(() => inflight.delete(key)));
    return inflight.get(key);
  };

  // Run fn(formIndex, protocol) on the active protocol; if that fails, on the others in turn.
  async function use(forms, fn) {
    if (!multi) return fn(undefined, scheme(forms[0]));
    const order = [link.active, ...protos.filter((p) => p !== link.active).sort((a, b) => link.health[b].ok - link.health[a].ok)];
    let err;
    for (const p of order) {
      const i = forms.findIndex((f) => scheme(f) === p);
      if (i < 0) continue;
      const t0 = performance.now();
      try {
        const out = await timeout(fn(i, p), TIMEOUT_MS);
        seen(link.health[p], performance.now() - t0);
        if (p !== link.active) switchTo(p, "down");
        return out;
      } catch (e) {
        link.health[p].ok = false;
        err = e;
      }
    }
    throw err;
  }

  const exposed = await wot.produce(model);
  for (const [n, p] of Object.entries(td.properties || {}))
    exposed.setPropertyReadHandler(n, () => use(p.forms, (i) => read(n, i)));
  if (multi) exposed.setPropertyReadHandler("protocol", async () => link);
  for (const [n, a] of Object.entries(td.actions || {})) {
    // contract: the mqtt relay wants a bare on/off on its cmd topic. switchOn/Off are idempotent,
    // so retrying one on another protocol after a timeout is safe.
    const isOn = n === "switchOn" || [].concat(a["@type"] || []).some((t) => t.endsWith("OnCommand")); // saref:OnCommand, any prefix
    const arg = (p) => (/^mqtt/.test(p) ? (isOn ? "on" : "off") : undefined);
    exposed.setActionHandler(n, async () => {
      const out = await use(a.forms, (i, p) => consumed.invokeAction(n, arg(p), { formIndex: i }));
      return out ? out.value() : undefined;
    });
  }
  for (const n of Object.keys(model.events))
    await consumed.subscribeEvent(n, async (data) => exposed.emitEvent(n, await data.value()));

  // probe every protocol on a property they all serve, so a dead path is found even when idle
  const probe = Object.keys(td.properties || {}).find((n) => protos.every((p) => td.properties[n].forms.some((f) => scheme(f) === p)));
  if (multi && probe)
    setInterval(() => protos.forEach((p) => {
      const h = link.health[p], i = td.properties[probe].forms.findIndex((f) => scheme(f) === p), t0 = performance.now();
      timeout(read(probe, i), TIMEOUT_MS)
        .then(() => seen(h, performance.now() - t0), () => { h.ok = false; })
        .finally(() => {
          const next = pick(protos, link.health, link.active);
          if (next !== link.active) switchTo(next, link.health[link.active].ok ? "faster" : "down");
        });
    }), PROBE_MS);

  await exposed.expose();
  return exposed.getThingDescription();
}

async function main() {
  const args = process.argv.slice(2);
  const opt = (k, d) => { const i = args.indexOf(k); if (i < 0) return d; return args.splice(i, 2)[1]; };
  const noDir = args.includes("--no-dir") && args.splice(args.indexOf("--no-dir"), 1);
  const HOST = opt("--host", process.env.GW_HOST || "localhost"); // address clients use to reach the gateway
  const PORT = +opt("--port", 8080);
  const DIR = opt("--dir", process.env.DIRECTORY || "http://localhost:9000");
  const files = args.length ? args : ["sensor.json", "fan.json", "plug.json"].map((f) => path.join(__dirname, "../tds", f));
  const tdFiles = files.flatMap((f) => (fs.statSync(f).isDirectory() ? fs.readdirSync(f).filter((n) => n.endsWith(".json")).map((n) => path.join(f, n)) : [f]));

  const dirSrv = noDir || !DIR.includes("localhost") ? null : await startDirectory(+new URL(DIR).port || 9000);
  const servient = new Servient();
  servient.addServer(new HttpServer({ port: PORT, address: "0.0.0.0" }));
  servient.addClientFactory(new HttpClientFactory());
  servient.addClientFactory(new MqttClientFactory());
  servient.addClientFactory(new CoapClientFactory());
  const wot = await servient.start();
  for (const f of tdFiles) {
    const td = JSON.parse(fs.readFileSync(f, "utf8"));
    try {
      const gtd = await proxy(wot, await wot.consume(td), td);
      // node-wot writes forms for the bind address; point them at HOST so remote clients can use them
      const text = JSON.stringify(gtd).replace(/\/\/(localhost|0\.0\.0\.0|127\.0\.0\.1|[\d.]+):8080/g, `//${HOST}:${PORT}`);
      if (!noDir) {
        const r = await fetch(`${DIR}/things/${encodeURIComponent(gtd.id)}`, { method: "PUT", body: text });
        if (!r.ok) throw new Error("directory " + r.status);
      }
      console.log("exposed", td.title, "from", path.basename(f));
    } catch (e) {
      console.error("FAILED", f, e.message);
    }
  }
}

module.exports = { pick };
if (require.main === module) main().catch((e) => { console.error(e); process.exit(1); });
