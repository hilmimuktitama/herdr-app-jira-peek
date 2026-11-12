// Exercise the actual mod methods with fake native services. Rendering is
// checked separately with `herdr-app check` and the isolated screenshot rig.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PeekModel, focusedSource, extractKeys, issueLink, parseIssueKey, statusColor, uiPreferences, displayDate, defaultFieldLayout, requestedReaderFields, issueAsMarkdown } from "../../mods/jira-peek/model.js";

const code = readFileSync(new URL("../../mods/jira-peek/main.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export default class", "return class");
const config = { context: "connection-one", projects: ["ABC"], base: "https://jira.example.test", ttl: 10, limit: 20 };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const turn = () => new Promise(r => setImmediate(r));

function harness() {
  const state = { focus: { terminal: "t1" }, live: [{ address: "t1", state: "live" }, { address: "remote/t1", state: "live" }], reads: [], requests: [], jobs: [], timers: [], clipboard: [], scrolls: [], saved: [] };
  const makeCx = () => ({ notify() {}, spawn(fn) { const promise = fn(makeCx()); state.jobs.push(promise); return { cancel() {} }; },
    write_to_clipboard(value) { state.clipboard.push(value); },
    timer: { after(ms, fn) { const timer = { ms, cancel() {}, fire: () => fn(makeCx()) }; state.timers.push(timer); return timer; } } });
  const cx = makeCx();
  const read = args => { const wait = deferred(); state.reads.push({ args, ...wait }); return wait.promise; };
  const Constructor = new Function("View", "PeekModel", "focusedSource", "extractKeys", "issueLink", "parseIssueKey", "statusColor", "uiPreferences", "displayDate", "focused", "terminals", "hc", "herdr", "localStorage", "defaultFieldLayout", "requestedReaderFields", "issueAsMarkdown", "settings", code)(
    class {}, PeekModel, focusedSource, extractKeys, issueLink, parseIssueKey, statusColor, uiPreferences, displayDate, () => state.focus, () => state.live, read, {}, { setItem(...args) { state.saved.push(args); } }, defaultFieldLayout, requestedReaderFields, issueAsMarkdown, () => ({ ui_font_size: 13 }));
  const view = new Constructor();
  // These tests isolate request/focus behavior; file persistence is exercised
  // with native services in view.test.js and the native fixture.
  view.savePreferences = () => state.saved.push(["preferences", JSON.stringify({ live: view.live === true })]);
  let inputValue = "";
  Object.assign(view, { model: new PeekModel(), epoch: 1, revision: 0, watchers: [], lastLiveAttempt: 0,
    width: 400, height: 800, copyNoteRevision: 0, listScroll: { scroll_to_item(...args) { state.scrolls.push(args); } },
    input: { value: () => inputValue, set_value(value) { inputValue = value; }, focus() {} },
    handle: { focus() {}, is_focused: () => false }, readerHandle: { focus() {}, is_focused: () => false } });
  view.model.reset(config); view.model.useSource("t1"); view.model.follow();
  view.bridge = (...args) => {
    const wait = deferred(), request = { args, done: false, resolve(value) { request.done = true; wait.resolve(value); } };
    state.requests.push(request); return wait.promise;
  };
  return { view, state, cx };
}

// Advance the one bounded confirmation, without hiding it from read counts.
async function confirmScreen(view, state, stdout) {
  assert.ok(view.confirmRead, "new screen keys need confirmation");
  const after = Math.max(...view.model.current.candidates.values()) + 250;
  view.now = () => after;
  const count = state.reads.length;
  state.timers.filter(timer => timer.ms === 250).at(-1).fire();
  assert.equal(state.reads.length, count + 1);
  state.reads.at(-1).resolve({ code: 0, stdout }); await turn();
}

export { harness, config, turn };
