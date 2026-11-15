// smoke test: directory API only (the rest needs real devices + broker)
const assert = require("assert");
const { startDirectory } = require("./directory");
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
