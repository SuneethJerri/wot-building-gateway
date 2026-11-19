// smoke test: failover choice + directory API (the rest needs real devices + broker)
const assert = require("assert");
const { startDirectory } = require("./directory");
const { pick } = require("./gateway");

// failover choice: [ok, smoothed ms] per protocol, TD order coap then mqtt
const H = (c, m, n = 9) => ({ coap: { ok: c[0], ms: c[1], n }, mqtt: { ok: m[0], ms: m[1], n } });
const order = ["coap", "mqtt"];
assert.strictEqual(pick(order, H([true, 0.6], [true, 3]), "coap"), "coap");   // both fine: keep the TD's first
assert.strictEqual(pick(order, H([false, 0.6], [true, 3]), "coap"), "mqtt");  // active down: fail over
assert.strictEqual(pick(order, H([true, 0.4], [true, 3]), "mqtt"), "mqtt");   // back, but not clearly faster: stay
assert.strictEqual(pick(order, H([true, 2], [true, 40]), "mqtt"), "coap");    // clearly faster: switch
assert.strictEqual(pick(order, H([false, 1], [false, 1]), "mqtt"), "mqtt");   // all down: keep trying
assert.strictEqual(pick(order, H([true, 90], [true, 3], 2), "coap"), "coap"); // still warming up: no switch
(async () => {
  const s = await startDirectory(9911);
  const u = "http://localhost:9911/things";
  await fetch(u + "/urn%3Aa", { method: "PUT", body: JSON.stringify({ id: "urn:a", title: "a" }) });
  await fetch(u, { method: "POST", body: JSON.stringify({ id: "urn:b", title: "b" }) });
  assert.strictEqual((await (await fetch(u)).json()).length, 2);
  await fetch(u + "/urn%3Aa", { method: "DELETE" });
  assert.strictEqual((await (await fetch(u)).json()).length, 1);
  assert.strictEqual((await fetch(u + "/nope")).status, 404);
  s.close(); console.log("ok");
})();
