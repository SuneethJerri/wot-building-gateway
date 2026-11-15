// Minimal Thing Directory (subset of the W3C API): GET/POST /things, GET/PUT/DELETE /things/<id>
// ponytail: in-memory, lost on restart; gateway re-registers on start. Swap for thingweb.directory if needed.
const http = require("http");

function startDirectory(port = 9000) {
  const things = new Map();
  const srv = http.createServer((req, res) => {
    const id = decodeURIComponent(req.url.split("?")[0].replace(/^\/things\/?/, ""));
    const send = (code, body) => { res.writeHead(code, { "content-type": "application/json" }); res.end(body === undefined ? "" : JSON.stringify(body)); };
    let buf = "";
    req.on("data", (c) => (buf += c));
    req.on("end", () => {
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
