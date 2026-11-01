import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const code = readFileSync(new URL("../mods/jira-peek/main.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export default class", "return class");
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const ticket = "a".repeat(48);
const requestPath = `/fictional/home/data/jira-peek/connection/.setup-pending/${ticket}/request.json`;
const tick = () => new Promise(r => setImmediate(r));
const inspect = { ok: true, revision: "missing", settings: { base: "https://fictional-peek.atlassian.net", email: "reader@example.test", projects: "ABC", cloudId: "" } };

function harness() {
  const state = { folder: deferred(), calls: [], writes: [], storage: [], jobs: [], connections: [] };
  const InputState = { new({ value = "" } = {}) { return { text: value, masked: false, released: false,
    value() { return this.text; }, set_value(v) { this.text = v; }, set_masked(v) { this.masked = v; }, focus() { this.focused = true; }, release() { this.released = true; } }; } };
  const exec = (command, args) => { const wait = deferred(); state.calls.push({ command, args, ...wait }); return wait.promise; };
  const writeTextFile = (...args) => { state.writes.push(args); return state.write ? state.write(...args) : Promise.resolve(null); };
  const localStorage = { setItem(...args) { state.storage.push(args); }, getItem() { return null; } };
  const Constructor = new Function("View", "InputState", "exec", "writeTextFile", "appHome", "localStorage", "pickFolder", code)(class {}, InputState, exec, writeTextFile, () => "/fictional/home", localStorage, () => state.folder.promise);
  const view = new Constructor();
  view.model = { config: null }; view.actionFocus = { "setup-open": { focus() {} }, more: { focus() {} } };
  view.connect = (_cx, root) => state.connections.push(root);
  const cx = { notify() {}, spawn(fn) { const job = fn(cx); state.jobs.push(job); return { cancel() {} }; } };
  const respond = (index, value) => state.calls[index].resolve({ code: 0, stdout: JSON.stringify(value) });
  return { view, state, cx, respond };
}
async function ready(h) { h.view.openSetup(h.cx); h.respond(0, inspect); await tick(); h.view.setup.token.set_value("fictional-secret"); }

test("cancel discards masked input and ignores stale inspect responses", async () => {
  const h = harness(); h.view.openSetup(h.cx); const first = h.view.setup; first.token.set_value("fictional-secret");
  assert.equal(first.token.masked, true); h.view.cancelSetup(h.cx); assert.equal(first.token.released, true); assert.equal(first.token.value(), "");
  for (const key of ["base", "email", "projects", "cloudId"]) assert.equal(first[key].released, true);
  h.view.openSetup(h.cx); const second = h.view.setup;
  h.respond(0, inspect); await tick(); assert.equal(second.loading, true); assert.equal(second.base.value(), "");
  h.respond(1, { ...inspect, settings: { ...inspect.settings, base: "https://other.example" } }); await tick();
  assert.equal(second.base.value(), "https://other.example");
});

test("submit writes secret only through empty-file CAS, blocks duplicate and cancel, and connects on success", async () => {
  const h = harness(); await ready(h); const form = h.view.setup, oldToken = form.token;
  h.view.saveSetup(h.cx); h.view.saveSetup(h.cx); h.view.cancelSetup(h.cx);
  assert.equal(h.state.calls.length, 2); assert.equal(h.view.setup, form); assert.equal(oldToken.released, true); assert.equal(oldToken.value(), ""); assert.notEqual(oldToken, form.token); assert.equal(form.token.value(), "");
  h.respond(1, { ok: true, ticket, path: requestPath }); await tick();
  assert.deepEqual(h.state.writes, [[requestPath, JSON.stringify({ base: inspect.settings.base, email: inspect.settings.email, token: "fictional-secret", projects: "ABC", cloudId: "" }), ""]]);
  assert.deepEqual(h.state.calls[2].args.slice(-2), ["/fictional/home/data/jira-peek/connection", ticket]);
  h.respond(2, { ok: true }); await tick();
  assert.deepEqual(h.state.connections, ["/fictional/home/data/jira-peek/connection"]); assert.equal(h.view.note, "Account verified. Connection saved.");
  assert.equal(h.view.setup, null); assert.equal(h.state.calls[3].args.at(-2), "/fictional/home/data/jira-peek/connection");
  h.respond(3, { ok: true }); await tick();
  assert.equal(JSON.stringify(h.state.calls.map(c => [c.command, c.args])).includes("fictional-secret"), false);
  assert.equal(JSON.stringify(h.state.storage).includes("fictional-secret"), false);
});

test("write failure cancels ticket and preserves nonsecret fields with generic error", async () => {
  const h = harness(); await ready(h); h.state.write = () => Promise.reject(new Error("fictional-secret"));
  h.view.saveSetup(h.cx); h.respond(1, { ok: true, ticket, path: requestPath }); await tick();
  assert.equal(h.state.calls[2].args.at(-3), "cancel"); assert.equal(h.view.setup.base.value(), inspect.settings.base);
  assert.equal(h.view.setup.token.value(), ""); assert.doesNotMatch(h.view.setup.error, /fictional-secret/);
  h.respond(2, { ok: true }); await tick(); assert.equal(h.view.setup.busy, false);
});

test("helper failure is mapped to safe feedback and cancellation; scoped value is sent only in payload", async () => {
  const h = harness(); await ready(h); h.view.setup.scoped = true; h.view.setup.cloudId.set_value("cloud-fixture");
  h.view.saveSetup(h.cx); h.respond(1, { ok: true, ticket, path: requestPath }); await tick();
  assert.equal(JSON.parse(h.state.writes[0][1]).cloudId, "cloud-fixture");
  h.respond(2, { ok: false, error: "authentication_failed", detail: "fictional-secret" }); await tick();
  assert.match(h.view.setup.error, /could not verify/); assert.doesNotMatch(h.view.setup.error, /fictional-secret/);
  assert.equal(h.state.calls[3].args.at(-3), "cancel"); h.respond(3, { ok: true }); await tick();
  assert.equal(h.view.setup.busy, false); assert.equal(h.state.connections.length, 0);
});

test("missing fields clear the token without starting a helper", async () => {
  const h = harness(); await ready(h); h.view.setup.projects.set_value(""); h.view.saveSetup(h.cx);
  assert.equal(h.state.calls.length, 1); assert.equal(h.view.setup.token.value(), ""); assert.match(h.view.setup.error, /required fields/);
});

test("verified setup remembers its folder even when reader initialization fails", async () => {
  const h = harness(); await ready(h);
  h.view.connect = Object.getPrototypeOf(h.view).connect;
  h.view.model = { config: null, reset(value) { this.config = value || null; } };
  h.view.input = { value: () => "", set_value() {} };
  h.view.watchers = []; h.view.epoch = 1;
  h.view.bridge = async () => ({ ok: false, error: "dependencies_missing" });
  h.view.saveSetup(h.cx);
  h.respond(1, { ok: true, ticket, path: requestPath }); await tick();
  h.respond(2, { ok: true }); await tick();
  h.respond(3, { ok: true }); await tick();
  assert.equal(h.view.error, "dependencies_missing");
  assert.equal(h.view.setup, null);
  assert.ok(h.state.storage.some(([key, value]) => key === "configDir" && value === "/fictional/home/data/jira-peek/connection"));
});


test("invalid request paths never receive a token and valid tickets are cancelled", async () => {
  for (const path of ["/fictional/request", `${requestPath}/../request.json`, requestPath.toUpperCase()]) {
    const h = harness(); await ready(h); h.view.saveSetup(h.cx);
    h.respond(1, { ok: true, ticket, path }); await tick();
    assert.equal(h.state.writes.length, 0); assert.equal(h.state.calls[2].args.at(-3), "cancel");
    h.respond(2, { ok: true }); await tick(); assert.ok(h.view.setup.token.focused);
  }
});

test("invalid ticket never reaches write or cleanup", async () => {
  const h = harness(); await ready(h); h.view.saveSetup(h.cx);
  h.respond(1, { ok: true, ticket: "../request", path: requestPath }); await tick();
  assert.equal(h.state.writes.length, 0); assert.equal(h.state.calls.length, 2);
  assert.match(h.view.setup.error, /Could not save/);
});

test("site and cloud validation reject lookalikes, ports and unsafe cloud IDs", async () => {
  for (const site of ["https://fictional-peek.atlassian.net.evil.test", "https://fictional-peek.atlassian.net:443", "https://user@fictional-peek.atlassian.net", "https://other.example"]) {
    const h = harness(); await ready(h); h.view.setup.base.set_value(site); h.view.saveSetup(h.cx);
    assert.equal(h.state.calls.length, 1); assert.match(h.view.setup.error, /site URL/); assert.ok(h.view.setup.token.focused);
  }
  const h = harness(); await ready(h); h.view.setup.scoped = true; h.view.setup.cloudId.set_value("../bad"); h.view.saveSetup(h.cx);
  assert.equal(h.state.calls.length, 1); assert.match(h.view.setup.error, /Cloud ID/);
});

test("escape and shortcuts cannot dismiss or act behind a busy transaction", async () => {
  const h = harness(); await ready(h); let stopped = 0;
  const eventCx = { ...h.cx, stop_propagation() { stopped++; } };
  h.view.saveSetup(h.cx); const form = h.view.setup;
  assert.equal(h.view.setupKeyDown({ key: "escape" }, eventCx), true);
  for (const key of ["f2", "f5"]) assert.equal(h.view.setupKeyDown({ key }, eventCx), false);
  assert.equal(stopped, 1); assert.equal(h.view.setup, form);
  h.respond(1, { ok: false, error: "permission_denied" }); await tick();
  assert.match(form.error, /account read permission/); assert.ok(form.token.focused);
  h.view.setupKeyDown({ key: "escape" }, eventCx); assert.equal(h.view.setup, null);
  for (const key of ["base", "email", "token", "projects", "cloudId"]) assert.equal(form[key].released, true);
});

test("entering setup invalidates a pending folder selection", async () => {
  const h = harness(); h.view.chooseConfig(h.cx); h.view.openSetup(h.cx);
  h.state.folder.resolve("/fictional/old-folder"); await tick();
  assert.deepEqual(h.state.connections, []); h.respond(0, inspect); await tick();
});

test("inspect failure permits retry and releases previous input states", async () => {
  const h = harness(); h.view.openSetup(h.cx); const old = h.view.setup;
  h.respond(0, { ok: false, error: "fictional-secret" }); await tick();
  assert.match(old.error, /Could not load/); h.view.openSetup(h.cx);
  for (const key of ["base", "email", "token", "projects", "cloudId"]) assert.equal(old[key].released, true);
  h.respond(1, inspect); await tick(); assert.equal(h.view.setup.revision, "missing");
});


test("connection entry and watcher invalidation leave a busy setup transaction intact", async () => {
  const h = harness(); await ready(h); h.view.saveSetup(h.cx); const form = h.view.setup;
  const realConnect = Object.getPrototypeOf(h.view).connect;
  realConnect.call(h.view, h.cx, "/fictional/other");
  assert.deepEqual(h.state.connections, []); assert.equal(h.view.setup, form);
  Object.assign(h.view, { epoch: 1, model: { reset() {} }, timer: { cancel() {} }, input: { value: () => "" } });
  h.view.invalidate(h.cx);
  assert.equal(h.view.setup, form); assert.equal(form.busy, true);
  h.respond(1, { ok: false, error: "config_changed" }); await tick();
  assert.equal(h.view.setup, form); assert.match(form.error, /changed/);
});
