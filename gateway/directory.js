// Minimal Thing Directory + serves dashboard.html at / (subset of the W3C API): GET/POST /things, GET/PUT/DELETE /things/<id>
// ponytail: in-memory, lost on restart; gateway re-registers on start. Swap for thingweb.directory if needed.
const fs = require("fs");
const path = require("path");
const http = require("http");
const os = require("os");

// --- host stats (RAM, CPU temp, CPU util) read straight from /proc and /sys; no deps ---
// CPU util needs two samples, so keep a 1s sampler and serve the latest value.
let cpuPrev = null, cpuPct = null;
function cpuSample() {
  try {
    const line = fs.readFileSync("/proc/stat", "utf8").split("\n")[0].trim().split(/\s+/).slice(1).map(Number);
    const idle = line[3] + (line[4] || 0);           // idle + iowait
    const total = line.reduce((a, b) => a + b, 0);
    if (cpuPrev) {
      const dt = total - cpuPrev.total, di = idle - cpuPrev.idle;
      if (dt > 0) cpuPct = Math.max(0, Math.min(100, (100 * (dt - di)) / dt));
    }
    cpuPrev = { idle, total };
  } catch (e) { /* not Linux / no /proc */ }
}
function hostStats() {
  const s = { cpuPct: cpuPct == null ? null : +cpuPct.toFixed(1), tempC: null, memUsedMB: null, memTotalMB: null, memPct: null, load1: null, cores: os.cpus().length, uptimeS: Math.round(os.uptime()) };
  try { s.tempC = +(Number(fs.readFileSync("/sys/class/thermal/thermal_zone0/temp", "utf8")) / 1000).toFixed(1); } catch (e) {}
  try {
    const mi = Object.fromEntries(fs.readFileSync("/proc/meminfo", "utf8").split("\n").map((l) => l.split(":")).filter((x) => x[1]).map(([k, v]) => [k, parseInt(v)]));  // kB
    const total = mi.MemTotal, avail = mi.MemAvailable != null ? mi.MemAvailable : mi.MemFree;
    if (total) { s.memTotalMB = Math.round(total / 1024); s.memUsedMB = Math.round((total - avail) / 1024); s.memPct = +(100 * (total - avail) / total).toFixed(1); }
  } catch (e) {}
  try { s.load1 = +fs.readFileSync("/proc/loadavg", "utf8").split(" ")[0]; } catch (e) {}
  return s;
}

function startDirectory(port = 9000) {
  cpuSample();
  const cpuTimer = setInterval(cpuSample, 1000);
  if (cpuTimer.unref) cpuTimer.unref();
  const things = new Map();
  const srv = http.createServer((req, res) => {
    const id = decodeURIComponent(req.url.split("?")[0].replace(/^\/things\/?/, ""));
    const send = (code, body) => { res.writeHead(code, { "content-type": "application/json", "access-control-allow-origin": "*" }); res.end(body === undefined ? "" : JSON.stringify(body)); };
    let buf = "";
    req.on("data", (c) => (buf += c));
    req.on("end", () => {
      if (req.url === "/" && req.method === "GET") { // the dashboard
        res.writeHead(200, { "content-type": "text/html" });
        return res.end(fs.readFileSync(path.join(__dirname, "dashboard.html")));
      }
      if ((req.url === "/scale" || req.url === "/scale/") && req.method === "GET") { // multi-client scale view
        res.writeHead(200, { "content-type": "text/html" });
        return res.end(fs.readFileSync(path.join(__dirname, "scale.html")));
      }
      if (req.url === "/stats" && req.method === "GET") { // host (Pi) stats: RAM, CPU temp, CPU util
        return send(200, hostStats());
      }
      if (req.method === "OPTIONS") { res.writeHead(204, { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, PUT, DELETE", "access-control-allow-headers": "content-type" }); return res.end(); }
      if (!req.url.startsWith("/things")) return send(404, { error: "not found" });
      if (req.method === "GET") return id ? (things.has(id) ? send(200, things.get(id)) : send(404, { error: "no such thing" })) : send(200, [...things.values()]);
      if (req.method === "DELETE") { things.delete(id); return send(204); }
      if (req.method === "POST" || req.method === "PUT") {
        let td;
        try { td = JSON.parse(buf); } catch { return send(400, { error: "bad json" }); }
        const key = id || td.id;
        if (!key) return send(400, { error: "td needs an id" });
        things.set(key, td);
        return send(201, td);
      }
      send(405, { error: "method" });
    });
  });
  return new Promise((r) => srv.listen(port, () => r(srv)));
}
module.exports = { startDirectory };
