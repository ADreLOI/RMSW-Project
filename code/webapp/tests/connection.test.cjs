const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../static/connection.js"), "utf8");

function fixture(fetch, config = {}) {
  const nodes = new Map(), events = [];
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, { value: "", listeners: {}, attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      removeAttribute(name) { delete this.attributes[name]; },
      addEventListener(name, fn) { this.listeners[name] = fn; } });
    return nodes.get(id);
  };
  const window = { LAB_CONFIG: { static: true, relayUrl: "https://relay.example", ...config },
    dispatchEvent(event) { events.push(event.type); } };
  const context = {
    window, document: { baseURI: "https://owner.github.io/RMSW-Project/", getElementById: node, addEventListener() {} },
    location: { origin: "https://owner.github.io" }, I18N: { t: (key) => key },
    URL, Headers, TextEncoder, btoa, Event, fetch, setTimeout,
  };
  vm.runInNewContext(source, context);
  const transport = window.LabConnection;
  transport.init();
  const connect = (url = "https://relay.example", password = "a-password") => {
    node("relay-url").value = url; node("relay-password").value = password;
    node("remote-form").listeners.submit({ preventDefault() {} });
  };
  return { transport, node, events, connect };
}

test("offline Pages uses the project subpath, canonical queries and blocks jobs", async () => {
  const calls = [];
  const { transport } = fixture(async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify(calls.length === 1
      ? { "/api/trace?run=demo": { path: "data/demo.json" } } : { policy: "S4-T" }));
  });
  assert.equal((await (await transport.request("/api/trace?run=demo&dataset=core")).json()).policy, "S4-T");
  assert.deepEqual(calls, ["./data/manifest.json", "https://owner.github.io/RMSW-Project/data/demo.json"]);
  await assert.rejects(transport.request("/api/jobs", { method: "POST" }), /remote.required/);
  await assert.rejects(transport.request("/api/trace?run=missing"), /remote.notPublished/);
});

test("password authenticates the fixed origin; live URL uses a disposable ticket", async () => {
  const calls = [];
  const f = fixture(async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ ticket: "single-use-ticket" }));
  });
  f.connect(undefined, "secret-è");
  assert.equal(f.node("relay-password").value, "");
  assert.deepEqual(f.events, ["lab-connect"]);
  const address = await f.transport.liveUrl();
  assert.equal(address, "wss://relay.example/live?ticket=single-use-ticket");
  assert.ok(!address.includes("secret"));
  assert.equal(Buffer.from(calls[0].options.headers.get("Authorization").slice(6), "base64").toString("utf8"), "lab:secret-è");
  f.transport.setOnline(true);
  await f.transport.request("/api/catalog");
  assert.equal(calls[1].url, "https://relay.example/api/catalog");
  assert.equal(calls[1].options.credentials, "omit");
  assert.equal(calls[1].options.redirect, "error");
  f.node("remote-disconnect").listeners.click();
  assert.equal(f.transport.remote, false);
  assert.equal(f.transport.online, false);
});

test("invalid relay addresses never send credentials", () => {
  const f = fixture(() => { throw Error("must not fetch"); });
  for (const url of ["http://relay.example", "https://user:pass@relay.example", "https://relay.example/path", "https://relay.example?key=x"]) {
    f.connect(url);
    assert.equal(f.node("remote-status").textContent, "remote.invalid");
    assert.equal(f.transport.remote, false);
  }
});

test("old responses cannot populate a new engine session", async () => {
  let finish;
  const f = fixture(() => new Promise((resolve) => { finish = resolve; }));
  f.connect(); f.transport.setOnline(true);
  const request = f.transport.request("/api/catalog");
  f.node("remote-disconnect").listeners.click();
  finish(new Response("{}"));
  await assert.rejects(request, /remote.changed/);
});

test("wrong browser password stops automatic authentication retries", async () => {
  const f = fixture(async () => new Response("{}", { status: 401 }));
  f.connect();
  await assert.rejects(f.transport.liveUrl(), (error) => error.stopRetry && error.message === "remote.passwordError");
});

test("public Pages prepares automatic connection without credentials and falls back when engine disconnects", async () => {
  const calls = [];
  const f = fixture(async (url, options) => {
    calls.push({ url: String(url), options });
    if (String(url).endsWith("/live-ticket")) return new Response(JSON.stringify({ ticket: "public-ticket" }));
    if (url === "./data/manifest.json") return new Response(JSON.stringify({ "/api/catalog": { path: "data/catalog.json" } }));
    return new Response("{}");
  }, { publicAccess: true });
  assert.equal(f.transport.remote, true);
  assert.equal(f.transport.online, false);
  assert.equal(f.node("remote-form").hidden, true);
  assert.equal(f.node("relay-password").hidden, true);
  assert.deepEqual(f.events, []); // app.js starts the watcher after loading static data.
  assert.equal(await f.transport.liveUrl(), "wss://relay.example/live?ticket=public-ticket");
  assert.equal(calls[0].options.headers.has("Authorization"), false);
  await assert.rejects(f.transport.request("/api/jobs", { method: "POST" }), /remote.required/);
  f.transport.setOnline(true);
  await f.transport.request("/api/jobs", { method: "POST", body: "{}" });
  assert.equal(calls[1].url, "https://relay.example/api/jobs");
  assert.equal(calls[1].options.headers.has("Authorization"), false);
  f.transport.setOnline(false);
  await f.transport.request("/api/catalog");
  assert.equal(calls.at(-1).url, "https://owner.github.io/RMSW-Project/data/catalog.json");
  assert.equal(f.transport.remote, true); // Stay subscribed; the engine may reconnect.
});

test("public connection without a configured URL offers only URL entry and rejects invalid origins", () => {
  const f = fixture(() => { throw Error("must not fetch"); }, { publicAccess: true, relayUrl: "" });
  assert.equal(f.transport.remote, false);
  assert.notEqual(f.node("remote-form").hidden, true);
  f.connect("http://relay.example");
  assert.equal(f.transport.remote, false);
  f.connect("https://relay.example", "unused-password");
  assert.equal(f.transport.remote, true);
  assert.equal(f.node("relay-password").value, "");
  assert.deepEqual(f.events, ["lab-connect"]);
});
