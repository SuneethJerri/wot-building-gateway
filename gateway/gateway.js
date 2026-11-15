// node-wot gateway: consumes device TDs (mqtt/coap/http forms), re-exposes each Thing over HTTP on
// :8080 with the same names, and registers it in the Directory. Clients only see HTTP.
// usage: node gateway.js [--host H] [--dir URL] [--no-dir] <td.json|folder>...
const fs = require("fs");
const path = require("path");
const { Servient } = require("@node-wot/core");
const { HttpServer, HttpClientFactory } = require("@node-wot/binding-http");
const { MqttClientFactory } = require("@node-wot/binding-mqtt");
const { CoapClientFactory } = require("@node-wot/binding-coap");
const { startDirectory } = require("./directory");

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); if (i < 0) return d; return args.splice(i, 2)[1]; };
const noDir = args.includes("--no-dir") && args.splice(args.indexOf("--no-dir"), 1);
const HOST = opt("--host", process.env.GW_HOST || "localhost"); // address clients use to reach the gateway
const PORT = +opt("--port", 8080);
const DIR = opt("--dir", process.env.DIRECTORY || "http://localhost:9000");
const files = args.length ? args : [path.join(__dirname, "../tds/sensor.json"), path.join(__dirname, "../tds/fan-coap.json"), path.join(__dirname, "../tds/plug.json")];

const tdFiles = files.flatMap((f) => (fs.statSync(f).isDirectory() ? fs.readdirSync(f).filter((n) => n.endsWith(".json")).map((n) => path.join(f, n)) : [f]));
const isMqtt = (form) => /^mqtt/.test(form.href);

async function proxy(wot, consumed, td) {
  const model = { title: td.title, id: "urn:gw:" + td.title, properties: {}, actions: {}, events: {} };
  for (const [n, p] of Object.entries(td.properties || {})) {
    const { forms, ...rest } = p;
    model.properties[n] = { ...rest, observable: false };
  }
  for (const [n, a] of Object.entries(td.actions || {})) model.actions[n] = { input: a.input, output: a.output };
  for (const [n, e] of Object.entries(td.events || {})) model.events[n] = { data: e.data };
  const exposed = await wot.produce(model);
  for (const n of Object.keys(model.properties))
    exposed.setPropertyReadHandler(n, async () => (await consumed.readProperty(n)).value());
  for (const [n, a] of Object.entries(td.actions || {})) {
    // contract: the mqtt relay wants a bare on/off on its cmd topic
    const arg = isMqtt(a.forms[0]) ? (n === "switchOn" ? "on" : "off") : undefined;
    exposed.setActionHandler(n, async (params) => {
      const out = await consumed.invokeAction(n, arg);
      return out ? out.value() : undefined;
    });
  }
  for (const n of Object.keys(model.events))
    await consumed.subscribeEvent(n, async (data) => exposed.emitEvent(n, await data.value()));
  await exposed.expose();
  return exposed.getThingDescription();
}

async function main() {
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
main().catch((e) => { console.error(e); process.exit(1); });
