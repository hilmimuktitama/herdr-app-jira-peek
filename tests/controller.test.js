// Exercise the actual mod methods with fake native services. Rendering is
// checked separately with `herdr-app check` and the isolated screenshot rig.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PeekModel, focusedSource, extractKeys, issueLink, parseIssueKey, statusColor, uiPreferences, MAX_KEYS, descriptionPreview, displayDate, defaultFieldLayout, requestedReaderFields } from "../mods/jira-peek/model.js";

const code = readFileSync(new URL("../mods/jira-peek/main.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export default class", "return class");
const config = { context: "connection-one", projects: ["ABC"], base: "https://jira.example.test", ttl: 10, limit: 20 };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const turn = () => new Promise(r => setImmediate(r));

function harness(highlight = false) {
  const state = { focus: { terminal: "t1" }, live: [{ address: "t1", state: "live" }, { address: "remote/t1", state: "live" }], reads: [], requests: [], jobs: [], timers: [], clipboard: [], scrolls: [], highlights: [], saved: [] };
  const makeCx = () => ({ notify() {}, spawn(fn) { const promise = fn(makeCx()); state.jobs.push(promise); return { cancel() {} }; },
    write_to_clipboard(value) { state.clipboard.push(value); },
    timer: { after(ms, fn) { const timer = { ms, cancel() {}, fire: () => fn(makeCx()) }; state.timers.push(timer); return timer; } } });
  const cx = makeCx();
  const read = args => { const wait = deferred(); state.reads.push({ args, ...wait }); return wait.promise; };
  const Constructor = new Function("View", "PeekModel", "focusedSource", "extractKeys", "issueLink", "parseIssueKey", "statusColor", "uiPreferences", "MAX_KEYS", "descriptionPreview", "displayDate", "focused", "terminals", "hc", "herdr", "localStorage", "defaultFieldLayout", "requestedReaderFields", code)(
    class {}, PeekModel, focusedSource, extractKeys, issueLink, parseIssueKey, statusColor, uiPreferences, MAX_KEYS, descriptionPreview, displayDate, () => state.focus, () => state.live, read, highlight ? { setTerminalHighlight(...args) { state.highlights.push(args); if (state.highlightThrows) throw new Error("fictional native failure"); return state.highlightResult !== false; } } : {}, { setItem(...args) { state.saved.push(args); } }, defaultFieldLayout, requestedReaderFields);
  const view = new Constructor();
  // These tests isolate request/focus behavior; file persistence is exercised
  // with native services in view.test.js and the native fixture.
  view.savePreferences = () => state.saved.push(["preferences", JSON.stringify({ live: view.live === true, highlightSource: view.highlightSource !== false })]);
  let inputValue = "";
  Object.assign(view, { model: new PeekModel(), epoch: 1, revision: 0, watchers: [], lastLiveAttempt: 0,
    width: 400, height: 800, copyNoteRevision: 0, listScroll: { scroll_to_item(...args) { state.scrolls.push(args); } },
    input: { value: () => inputValue, set_value(value) { inputValue = value; }, focus() {} },
    handle: { focus() {}, is_focused: () => false }, readerHandle: { focus() {}, is_focused: () => false } });
  view.model.reset(config); view.model.useSource("t1");
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

test("filter edits select immediately, coalesce body requests, and Enter reuses the preview", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
  view.model.accept({ key: "ABC-1", summary: "Harbor" });
  view.model.metadata.set("ABC-2", { key: "ABC-2", summary: "Orchard" });
  view.model.metadata.set("ABC-3", { key: "ABC-3", summary: "Orchard paths" });
  view.issuesExpanded = true;
  view.input.set_value("orchard"); view.inputChanged(cx);
  assert.equal(view.model.current.selected, "ABC-2"); assert.equal(state.requests.length, 0);
  const old = state.timers.at(-1);
  view.input.set_value("orchard paths"); view.inputChanged(cx);
  assert.equal(view.model.current.selected, "ABC-3");
  old.fire(); assert.equal(state.requests.length, 0);
  state.timers.at(-1).fire();
  assert.deepEqual(state.requests[0].args, ["issue", config.context, "ABC-3"]);
  view.submit(cx);
  assert.equal(view.issuesExpanded, false); assert.equal(view.input.value(), "orchard paths");
  assert.equal(state.requests.length, 1);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-3", summary: "Orchard paths" } });
  await turn(); assert.equal(view.model.details.get("ABC-3").summary, "Orchard paths");
});

test("passive screen and metadata matches preserve unread state, cooldown and inactivity until a user edit", async () => {
  for (const query of ["ABC-2", "orchard"]) {
    const { view, state, cx } = harness(); view.now = () => 1000;
    view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1", summary: "Harbor" });
    view.input.set_value(query); view.inputChanged(cx);
    const interaction = view.lastInteraction;
    view.scan(cx); state.reads[0].resolve({ code: 0, stdout: "ABC-1 ABC-2" }); await turn();
    await confirmScreen(view, state, "ABC-1 ABC-2");
    assert.deepEqual(state.requests[0].args, ["metadata", config.context, "ABC-2"]);
    const cooldown = view.model.retryAfter = view.now() + 30000;
    state.requests[0].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-2", summary: "Orchard paths" }] }); await turn();
    assert.equal(view.model.current.selected, "ABC-2"); assert.equal(view.model.current.follow, false);
    assert.deepEqual([...view.model.current.unseen], ["ABC-2"]);
    assert.equal(view.model.retryAfter, cooldown); assert.equal(view.lastInteraction, interaction);
    view.input.set_value(query + " "); view.inputChanged(cx);
    assert.deepEqual([...view.model.current.unseen], [], "a deliberate query edit acknowledges its preview");
  }
});

test("list placeholders reflect valid detail loading, failure and a returned empty title", async () => {
  for (const outcome of ["failed", "empty"]) {
    const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx);
    assert.equal(view.rowPlaceholder("ABC-1"), "Loading title…");
    state.requests[0].resolve(outcome === "failed" ? { ok: false, error: "request_failed" }
      : { ok: true, context: config.context, issue: { key: "ABC-1", summary: "" } }); await turn();
    assert.equal(view.rowPlaceholder("ABC-1"), outcome === "failed" ? "Issue failed to load · Refresh to retry" : "No title returned");
  }
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]);
  view.model.useSource("remote/t1"); view.model.merge(["ABC-1"]); view.model.useSource("t1"); view.pump(cx);
  view.clearList(cx);
  assert.equal(view.rowPlaceholder("ABC-1"), "Not loaded yet", "a retired request does not claim to load a shared row");
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.equal(view.rowPlaceholder("ABC-1"), "Not loaded yet");
  view.model.useSource("remote/t1"); view.pump(cx);
  assert.equal(view.rowPlaceholder("ABC-1"), "Loading title…");
});

test("field changes keep the comments slot occupied through stale success or failure", async () => {
  for (const failed of [false, true]) {
    const { view, state, cx } = harness();
    const payload = { key: "ABC-1", summary: "Harbor", commentsDeferred: true };
    view.model.merge([payload.key]); view.model.accept(payload);
    const old = view.model.details.get(payload.key);
    view.syncDisclosures(); view.toggleComments(cx);
    const next = defaultFieldLayout(config); next.fields.push({ id: "priority", label: "Priority", section: "body" });
    view.useFieldLayout(next, cx);
    const body = state.requests.find(r => r.args[0] === "issue");
    body.resolve({ ok: true, context: config.context, issue: { ...payload } }); await turn();
    const current = view.model.details.get(old.key);
    view.loadComments(cx);
    assert.equal(state.requests.filter(r => r.args[0] === "comments" && !r.done).length, 1);
    state.requests[0].resolve(failed ? { ok: false, error: "request_failed" }
      : { ok: true, context: config.context, comments: { key: old.key, comments: [{ body: "Retired" }] } }); await turn();
    assert.equal(current.comments, undefined); assert.equal(current.commentsError, undefined);
    assert.equal(old.commentsLoading, false); assert.equal(current.commentsLoading, true);
    const comments = state.requests.filter(r => r.args[0] === "comments");
    assert.equal(comments.length, 2); assert.equal(comments.filter(r => !r.done).length, 1);
    comments[1].resolve({ ok: true, context: config.context, comments: { key: old.key, comments: [{ body: "Current" }] } }); await turn();
    assert.equal(current.comments[0].body, "Current"); assert.equal(current.commentsLoading, false);
  }
});

test("clear retires old screen/history and waits for a post-clear baseline in both Follow states", async () => {
  for (const follow of [true, false]) {
    const { view, state, cx } = harness(); view.pump = () => {};
    view.model.merge(["ABC-1"]); view.model.current.follow = follow;
    view.scan(cx); view.history(cx); view.clearList(cx);
    assert.equal(view.scanning.state.baselinePending, false, "the old read remains counted");
    assert.equal(view.historyPending, null);
    assert.deepEqual(view.model.current.keys, []);
    state.reads[0].resolve({ code: 0, stdout: "ABC-9" }); await turn();
    assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "0"]);
    state.reads[1].resolve({ code: 0, stdout: "ABC-1" }); await turn();
    assert.equal(view.model.current.baselinePending, false); assert.deepEqual(view.model.current.keys, []);
    view.scan(cx); state.reads[2].resolve({ code: 0, stdout: "ABC-1 ABC-2" }); await turn();
    await confirmScreen(view, state, "ABC-1 ABC-2");
    assert.deepEqual(view.model.current.keys, ["ABC-2"]);
    assert.equal(view.model.current.selected, follow ? "ABC-2" : null);
    assert.equal(view.model.current.follow, follow);
    assert.deepEqual([...view.model.current.unseen], follow ? [] : ["ABC-2"]);
    assert.ok(state.reads.every(read => read.args[3] === "0"));
  }
});

test("explicit screen confirmation retains its suppression bypass without starting a polling loop", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.model.merge(["ABC-1"]); view.clearList(cx);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  view.scan(cx, { bypass: true }); state.reads[1].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  await confirmScreen(view, state, "ABC-1");
  assert.deepEqual(view.model.current.keys, ["ABC-1"]); assert.equal(view.confirmRead, null);
  const count = state.reads.length;
  state.timers.filter(timer => timer.ms === 250).at(-1).fire();
  assert.equal(state.reads.length, count);
});

test("cleared batches release only their pending shared markers while occupied issue slots settle", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2"]); view.model.accept({ key: "ABC-1", summary: "Selected" }); view.pump(cx);
  view.select("ABC-2", cx, false);
  assert.equal(state.requests.length, 2);
  view.model.useSource("remote/t1"); view.model.merge(["ABC-2"]);
  view.model.useSource("t1"); view.clearList(cx);
  assert.equal([view.request, view.backgroundRequest].filter(Boolean).length, 2);
  state.requests[0].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-2", summary: "Retired metadata" }] }); await turn();
  assert.equal(view.model.metadataAttempts.has("ABC-2"), false);
  assert.equal(view.model.metadata.has("ABC-2"), false);
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2", summary: "Retired detail" } }); await turn();
  assert.equal(view.model.details.has("ABC-2"), false);
  view.model.useSource("remote/t1"); view.pump(cx);
  assert.deepEqual(state.requests[2].args, ["issue", config.context, "ABC-2"]);
  assert.deepEqual(view.model.sources.get("t1").keys, []);
});

test("retained-source results survive an ordinary source switch, but revocation wins over Clear", async () => {
  for (const clear of [false, true]) {
    const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx);
    if (clear) view.clearList(cx); else view.model.useSource("remote/t1");
    state.requests[0].resolve(clear ? { ok: false, error: "connection_changed" }
      : { ok: true, context: config.context, issue: { key: "ABC-1", summary: "Retained source" } });
    await turn();
    if (clear) assert.equal(view.model.config, null);
    else assert.equal(view.model.metadata.get("ABC-1").summary, "Retained source");
  }
});

test("closed panels retire comments success and failure without restarting requests", async () => {
  for (const failed of [false, true]) {
    const { view, state, cx } = harness();
    view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1", summary: "Orchard", commentsDeferred: true });
    view.syncDisclosures(); view.toggleComments(cx);
    const issue = view.model.details.get("ABC-1"), token = view.commentsRequest;
    assert.equal(state.requests.length, 1); assert.equal(issue.commentsLoading, true);
    await view.close(cx);
    assert.equal(view.commentsRequest, token, "closing keeps the actual occupied slot until settlement");
    view.loadComments(cx, true); assert.equal(state.requests.length, 1);
    state.requests[0].resolve(failed ? { ok: false, error: "request_failed" }
      : { ok: true, context: config.context, comments: { key: issue.key, comments: [{ body: "Late" }] } }); await turn();
    assert.equal(state.requests.length, 1); assert.equal(view.commentsRequest, null);
    assert.equal(issue.comments, undefined); assert.equal(issue.commentsDeferred, true);
    assert.equal(issue.commentsLoading, false); assert.equal(issue.commentsError, undefined);
    view.loadComments(cx, true);
    assert.equal(state.requests.length, 1); assert.equal(issue.commentsLoading, false);
  }
});

test("a cleared comments request cannot populate shared content or clear a successor's loading state", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1", summary: "Orchard", commentsDeferred: true });
  view.model.useSource("remote/t1"); view.model.merge(["ABC-1"]); view.model.useSource("t1");
  view.toggleComments(cx); view.clearList(cx);
  view.model.useSource("remote/t1"); view.commentsOpen = true; view.loadComments(cx);
  assert.equal(state.requests.length, 1);
  state.requests[0].resolve({ ok: true, context: config.context, comments: { key: "ABC-1", comments: [{ body: "Old" }] } }); await turn();
  assert.equal(state.requests.length, 2); assert.equal(view.model.details.get("ABC-1").comments, undefined);
  assert.equal(view.model.details.get("ABC-1").commentsLoading, true);
  state.requests[1].resolve({ ok: true, context: config.context, comments: { key: "ABC-1", comments: [{ body: "New" }] } }); await turn();
  assert.equal(view.model.details.get("ABC-1").comments[0].body, "New");
  assert.equal(view.model.details.get("ABC-1").commentsLoading, false);
});

test("late metadata cannot downgrade a newer projection after TTL-zero removal or 40-body eviction", async () => {
  for (const removal of ["ttl-zero", "capacity"]) for (const outcome of ["rows", "omitted", "failed", "denied"]) {
    const { view, state, cx } = harness();
    if (removal === "ttl-zero") view.model.config = { ...config, ttl: 0 };
    view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
    view.model.accept({ key: "ABC-1", summary: "Harbor" }); view.pump(cx);
    view.select("ABC-2", cx, false);
    state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2", summary: "Orchard paths", status: "Ready" } }); await turn();
    if (removal === "ttl-zero") view.select("ABC-1", cx, false);
    else {
      const keys = Array.from({ length: 40 }, (_, i) => `ABC-${100 + i}`); view.model.merge(keys);
      for (const key of keys) {
        view.select(key, cx, false);
        assert.ok(state.requests.filter(r => !r.done).length <= 2);
        state.requests.at(-1).resolve({ ok: true, context: config.context, issue: { key, summary: "Harbor" } }); await turn();
      }
    }
    assert.equal(view.model.details.has("ABC-2"), false, removal);
    view.issuesExpanded = true; view.input.set_value("orchard"); view.inputChanged(cx);
    state.requests[0].resolve(outcome === "failed" || outcome === "denied" ? { ok: false, error: outcome === "denied" ? "permission_denied" : "request_failed" }
      : { ok: true, context: config.context, rows: outcome === "rows" ? [{ key: "ABC-2", summary: "Old row", status: "Old" }] : [] });
    await turn();
    assert.equal(view.model.metadata.get("ABC-2").summary, "Orchard paths", `${removal}/${outcome}`);
    assert.equal(view.model.rowStates.get("ABC-2").status, "ready");
    assert.deepEqual(view.model.rows(), ["ABC-2"]); assert.equal(view.model.current.selected, "ABC-2");
    assert.ok(state.requests.filter(r => !r.done).length <= 2);
  }
});

test("manual discovery reads the newly focused source after an old scan finishes", async () => {
  const { view, state, cx } = harness(); view.model.config.interval = 0; view.pump = () => {}; view.scan(cx);
  assert.deepEqual(state.reads[0].args, ["read", "t1", "--lines", "0"]);
  state.focus = { terminal: "remote/t1" }; view.adoptSource(cx);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.deepEqual(view.model.current.keys, []);
  assert.deepEqual(state.reads[1].args, ["read", "remote/t1", "--lines", "0"]);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  await confirmScreen(view, state, "ABC-2");
  assert.deepEqual(view.model.current.keys, ["ABC-2"]);
});

test("overlapping screen scans coalesce, with one bounded confirmation of the latest key", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.scan(cx); view.scan(cx); view.scan(cx);
  assert.equal(state.reads.length, 1);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.equal(state.reads.length, 2);
  assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "0"]);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  await confirmScreen(view, state, "ABC-2");
  assert.deepEqual(view.model.current.keys, ["ABC-2"]);
  assert.equal(state.reads.length, 3);
});

test("queued scans follow the latest source and are discarded on invalidation", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.scan(cx); view.scan(cx);
  state.focus = { terminal: "remote/t1" }; view.scan(cx);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.deepEqual(state.reads[1].args, ["read", "remote/t1", "--lines", "0"]);
  view.scan(cx); view.invalidate(cx);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  assert.equal(state.reads.length, 2); assert.equal(view.model.config, null);
});

test("a delayed scan is discarded after leaving and returning to its source", async () => {
  const { view, state, cx } = harness(); view.pump = () => {}; view.scan(cx);
  view.model.useSource("remote/t1"); view.model.useSource("t1");
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.deepEqual(view.model.current.keys, []);
  assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "0"]);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  await confirmScreen(view, state, "ABC-2");
  assert.deepEqual(view.model.current.keys, ["ABC-2"]);
});

test("Browse entered while a scan is pending wins over discovery", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1" });
  view.scan(cx); view.model.filter("keep");
  state.reads[0].resolve({ code: 0, stdout: "ABC-1 ABC-2" }); await turn();
  await confirmScreen(view, state, "ABC-1 ABC-2");
  assert.equal(view.model.current.selected, "ABC-1"); assert.equal(view.model.current.query, "keep");
  assert.equal(view.model.current.unseen.size, 1);
});

test("passive Browse discovery preserves the list viewport while Follow reveals its new selection", async () => {
  for (const follow of [false, true]) {
    const { view, state, cx } = harness(); view.pump = () => {};
    view.model.merge(["ABC-1"]); view.model.current.follow = follow;
    view.scan(cx); state.reads[0].resolve({ code: 0, stdout: "ABC-1 ABC-2" }); await turn();
    await confirmScreen(view, state, "ABC-1 ABC-2");
    assert.equal(view.model.current.selected, follow ? "ABC-2" : "ABC-1");
    if (follow) assert.ok(state.scrolls.length > 0);
    else assert.deepEqual(state.scrolls, []);
  }
});

test("a new selected issue starts before an earlier issue completes and results keep their own keys", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]); view.pump(cx);
  view.select("ABC-2", cx); assert.equal(state.requests.length, 2);
  assert.equal(view.request.key, "ABC-2"); assert.equal(view.backgroundRequest.key, "ABC-1");
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "One" } }); await turn();
  assert.equal(view.model.current.selected, "ABC-2"); assert.equal(view.model.details.get("ABC-2"), undefined);
  assert.equal(state.requests[1].args[2], "ABC-2");
  assert.equal(view.request.phase, "issue"); assert.equal(view.request.key, "ABC-2");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2", summary: "Two" } }); await turn();
  assert.equal(state.requests.length, 2); assert.equal(view.model.details.get("ABC-2").summary, "Two");
});

test("a connection reset rejects a delayed successful request", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx);
  view.invalidate(cx);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1" } }); await turn();
  assert.equal(view.model.details.size, 0); assert.equal(view.model.config, null);
});

test("a selected issue bypasses slow metadata and a late batch cannot replace its newer summary", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2"]); view.model.accept({ key: "ABC-1" }); view.pump(cx);
  assert.equal(state.requests[0].args[0], "metadata");
  view.select("ABC-2", cx, false);
  assert.deepEqual(state.requests[1].args, ["issue", config.context, "ABC-2"]);
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2", summary: "Fresh detail" } }); await turn();
  assert.equal(view.model.details.get("ABC-2").summary, "Fresh detail");
  state.requests[0].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-2", summary: "Older batch" }] }); await turn();
  assert.equal(view.model.metadata.get("ABC-2").summary, "Fresh detail");
  assert.equal(state.requests.length, 2);
});

test("rapid issue choices use at most two slots and the next free slot loads only the latest choice", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2", "ABC-3", "ABC-4"]);
  for (const key of view.model.current.keys) view.model.metadata.set(key, { key });
  view.pump(cx); view.select("ABC-2", cx, false);
  view.select("ABC-3", cx, false); view.select("ABC-4", cx, false);
  assert.equal(state.requests.length, 2);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1" } }); await turn();
  assert.equal(state.requests.length, 3); assert.equal(state.requests[2].args[2], "ABC-4");
  state.requests[2].resolve({ ok: true, context: config.context, issue: { key: "ABC-4" } }); await turn();
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2" } }); await turn();
  assert.equal(state.requests.length, 3); assert.equal(view.model.current.selected, "ABC-4");
  assert.equal(view.request, null); assert.equal(view.backgroundRequest, null);
});

test("revisiting an in-flight issue reuses it, and refreshing it waits for that same key", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]);
  view.pump(cx); view.select("ABC-2", cx, false); view.select("ABC-1", cx, false);
  assert.equal(state.requests.length, 2); assert.equal(view.request.key, "ABC-1");
  view.refresh(cx); assert.equal(state.requests.length, 2);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Superseded" } }); await turn();
  assert.equal(view.model.details.has("ABC-1"), false);
  assert.deepEqual(state.requests[2].args, ["issue", config.context, "ABC-1", "refresh"]);
});

test("a stale request failure cannot stall the latest queued choice or show an unrelated error", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
  view.pump(cx); view.select("ABC-2", cx, false); view.select("ABC-3", cx, false);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.equal(view.model.retryAfter, 0); assert.equal(view.note, "");
  assert.equal(state.requests[2].args[2], "ABC-3");
});

test("a deliberate choice bypasses the failed issue cooldown while passive retry remains bounded", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.ok(view.model.retryAfter > view.now());
  view.select("ABC-2", cx, false);
  assert.equal(state.requests[1].args[2], "ABC-2"); assert.equal(view.model.retryAfter, 0);
});

test("connection revocation from either parallel slot clears both and ignores late success", async () => {
  for (const failed of [0, 1]) {
    const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]);
    view.pump(cx); view.select("ABC-2", cx, false);
    state.requests[failed].resolve({ ok: false, error: "connection_changed" }); await turn();
    assert.equal(view.model.config, null); assert.equal(view.request, null); assert.equal(view.backgroundRequest, null);
    state.requests[1 - failed].resolve({ ok: true, context: config.context, issue: { key: `ABC-${2 - failed}` } }); await turn();
    assert.equal(view.model.details.size, 0); assert.equal(state.requests.length, 2);
  }
});

test("TTL zero drops late unselected bodies while retaining useful row metadata", async () => {
  const { view, state, cx } = harness(); view.model.config = { ...config, ttl: 0 };
  view.model.merge(["ABC-1", "ABC-2"]); view.pump(cx); view.select("ABC-2", cx, false);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Old choice" } }); await turn();
  assert.equal(view.model.details.has("ABC-1"), false); assert.equal(view.model.metadata.get("ABC-1").summary, "Old choice");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2" } }); await turn();
  assert.equal(view.model.details.has("ABC-2"), true);
});

test("TTL zero Follow refetches on A to B to A without discarding searchable rows", async () => {
  const { view, state, cx } = harness(); view.model.config = { ...config, ttl: 0 };
  view.model.merge(["ABC-1"]); view.pump(cx);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Fictional first" } }); await turn();
  view.model.merge(["ABC-2"]); view.pump(cx);
  assert.equal(view.model.details.has("ABC-1"), false); assert.equal(state.requests.length, 2);
  assert.equal(view.model.metadata.get("ABC-1").summary, "Fictional first");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2" } }); await turn();
  view.model.merge(["ABC-1"]); view.pump(cx);
  assert.equal(state.requests.length, 3); assert.equal(state.requests[2].args[2], "ABC-1");
  state.requests[2].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Fictional updated" } }); await turn();
  assert.deepEqual([...view.model.details.keys()], ["ABC-1"]);
  assert.equal(view.model.details.get("ABC-1").summary, "Fictional updated");
});

test("TTL zero same-key source adoption reuses a valid pending issue without duplicate requests", async () => {
  const { view, state, cx } = harness(); view.model.config = { ...config, ttl: 0 };
  view.model.merge(["ABC-1"]); view.pump(cx);
  view.model.useSource("remote/t1"); view.model.merge(["ABC-1"]); view.pump(cx);
  assert.equal(state.requests.length, 1);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Fictional shared context" } }); await turn();
  assert.equal(view.model.details.get("ABC-1").summary, "Fictional shared context");
  view.model.useSource("t1"); view.pump(cx); assert.equal(state.requests.length, 1);
});

test("TTL zero late comments cannot restore a retired body or contaminate a reselected issue", async () => {
  const { view, state, cx } = harness(); view.model.config = { ...config, ttl: 0 };
  view.model.merge(["ABC-1", "ABC-2"]);
  view.model.accept({ key: "ABC-1", summary: "Fictional first", commentsDeferred: true });
  view.model.metadata.set("ABC-2", { key: "ABC-2" }); view.toggleComments(cx);
  view.select("ABC-2", cx, false);
  assert.equal(view.model.details.has("ABC-1"), false);
  state.requests[0].resolve({ ok: true, context: config.context, comments: { key: "ABC-1", comments: [{ body: "Fictional obsolete comment" }] } }); await turn();
  assert.equal(view.model.details.has("ABC-1"), false); assert.equal(view.commentsRequest, null);
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2" } }); await turn();
  view.select("ABC-1", cx, false); assert.equal(state.requests.length, 3);
  state.requests[2].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", commentsDeferred: true } }); await turn();
  assert.equal(view.model.details.get("ABC-1").comments, undefined);
});

test("an explicit refresh rejects a previous result and queues a forced request", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx); view.refresh(cx);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Old" } }); await turn();
  assert.equal(view.model.details.size, 0); assert.equal(state.requests[1].args.at(-1), "refresh");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "New" } }); await turn();
  assert.equal(view.model.details.get("ABC-1").summary, "New");
});

test("failed requests back off; unchanged scans never authenticate or fetch again", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  view.pump(cx); view.scan(cx); state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.equal(state.requests.length, 1); assert.ok(view.model.retryAfter > Date.now());
  view.refresh(cx); assert.equal(state.requests.length, 2);
});

test("an automatically selected issue deferred by backoff wakes once at the deadline", async () => {
  const { view, state, cx } = harness(); let now = 1000; view.now = () => now;
  view.model.merge(["ABC-1", "ABC-2"]); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  view.model.select("ABC-2"); view.pump(cx);
  assert.equal(state.requests.length, 1);
  assert.equal(state.timers.length, 1);
  now = 32000; state.timers[0].fire();
  assert.equal(state.requests.length, 2);
  assert.equal(state.requests[1].args[2], "ABC-2");
  state.timers[0].fire(); assert.equal(state.requests.length, 2);
});

test("connection invalidation retires a pending backoff wake-up", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  view.model.select("ABC-2"); view.pump(cx); const pending = state.timers.at(-1);
  view.invalidate(cx); pending.fire();
  assert.equal(state.requests.length, 1); assert.equal(view.retryWait, null);
});

test("optional comments load separately and never block another issue", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2"]);
  view.model.accept({ key: "ABC-1", description: "Core context", commentsDeferred: true });
  view.model.metadata.set("ABC-2", { key: "ABC-2" });
  view.toggleComments(cx);
  assert.deepEqual(state.requests[0].args, ["comments", config.context, "ABC-1"]);
  assert.equal(view.model.details.get("ABC-1").description, "Core context");
  view.select("ABC-2", cx, false);
  assert.deepEqual(state.requests[1].args, ["issue", config.context, "ABC-2"]);
  state.requests[0].resolve({ ok: false, error: "permission_denied" }); await turn();
  assert.equal(view.model.config.context, config.context);
  assert.equal(view.model.details.get("ABC-1").description, "Core context");
  assert.equal(view.model.details.get("ABC-1").commentsError, "permission_denied");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-2", summary: "Second issue" } }); await turn();
  assert.equal(view.model.details.get("ABC-2").summary, "Second issue");
});

test("comment results cannot overwrite a refreshed issue or a changed connection", async () => {
  for (const action of ["refresh", "invalidate"]) {
    const { view, state, cx } = harness(); view.model.merge(["ABC-1"]);
    view.model.accept({ key: "ABC-1", commentsDeferred: true }); view.loadComments(cx);
    if (action === "refresh") view.model.accept({ key: "ABC-1", description: "New body", commentsDeferred: true });
    else view.invalidate(cx);
    state.requests[0].resolve({ ok: true, context: config.context,
      comments: { key: "ABC-1", comments: [{ body: "Old comment" }], commentsTotal: 1 } }); await turn();
    assert.equal(view.model.details.get("ABC-1")?.comments, undefined);
  }
});

test("a comment retry succeeds without changing the issue fetch timestamp", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]);
  view.model.accept({ key: "ABC-1", fetchedAt: 1000, commentsDeferred: true }); view.loadComments(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  view.loadComments(cx); assert.equal(state.requests.length, 1);
  view.loadComments(cx, true);
  state.requests[1].resolve({ ok: true, context: config.context,
    comments: { key: "ABC-1", comments: [], commentsTotal: 0, truncated: false } }); await turn();
  const issue = view.model.details.get("ABC-1");
  assert.equal(issue.fetchedAt, 1000); assert.equal(issue.commentsDeferred, false);
  assert.equal(issue.commentsLoaded, true); assert.equal(issue.commentsError, "");
});

test("revocation from an older comments request still invalidates a refreshed issue", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]);
  view.model.accept({ key: "ABC-1", commentsDeferred: true }); view.loadComments(cx);
  view.model.accept({ key: "ABC-1", description: "Refreshed body", commentsDeferred: true });
  state.requests[0].resolve({ ok: false, error: "connection_changed" }); await turn();
  assert.equal(view.model.config, null); assert.equal(view.model.details.size, 0);
});

test("Follow and source adoption close old disclosures before reusing cached detail", () => {
  for (const operation of ["follow", "source"]) {
    const { view, state, cx } = harness(); view.scan = () => {};
    view.model.merge(["ABC-1", "ABC-2"]); view.model.merge(["ABC-2", "ABC-1"]);
    view.model.accept({ key: "ABC-1", commentsDeferred: true });
    view.model.accept({ key: "ABC-2", commentsDeferred: true });
    if (operation === "source") {
      view.model.useSource("remote/t1"); view.model.merge(["ABC-2"]); view.model.useSource("t1");
    }
    view.model.select("ABC-1"); view.syncDisclosures(); view.commentsOpen = true; view.detailsOpen = true;
    if (operation === "follow") view.follow(cx);
    else { state.focus = { terminal: "remote/t1" }; view.adoptSource(cx, false); }
    assert.equal(view.model.current.selected, "ABC-2");
    assert.equal(view.commentsOpen, false); assert.equal(view.detailsOpen, false);
    assert.equal(state.requests.length, 0, "no invisible comments request or false loading state");
  }
});

test("issue permission denial retires only that issue and leaves the connection usable", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1", "ABC-2"]);
  view.model.accept({ key: "ABC-1", description: "Previously readable" });
  view.model.accept({ key: "ABC-2", description: "Unaffected" });
  view.refresh(cx); state.requests[0].resolve({ ok: false, error: "permission_denied" }); await turn();
  assert.equal(view.model.details.has("ABC-1"), false); assert.ok(view.model.denied.has("ABC-1"));
  assert.equal(view.model.details.get("ABC-2").description, "Unaffected");
  assert.equal(view.model.config.context, config.context); assert.equal(view.model.retryAfter, 0);
});

test("connection mismatch wipes in-memory data rather than showing a foreign result", async () => {
  const { view, state, cx } = harness(); view.model.merge(["ABC-1"]); view.pump(cx);
  state.requests[0].resolve({ ok: true, context: "different", issue: { key: "ABC-1" } }); await turn();
  assert.equal(view.model.details.size, 0); assert.equal(view.error, "connection_changed");
});

test("pinning leaves focus changes alone and never invokes a focus command", () => {
  const { view, state, cx } = harness(); view.model.pinned = true;
  state.focus = { terminal: "remote/t1" }; view.adoptSource(cx);
  assert.equal(view.model.source, "t1"); assert.equal(state.reads.length, 0);
});

test("manual lookup works without a terminal and never reads an implicit source", () => {
  const { view, state, cx } = harness(); state.focus = null; state.live = [];
  view.model.useSource(null); view.input.value = () => "ABC-7";
  view.submit(cx); view.scan(cx);
  assert.equal(view.model.source, "manual"); assert.equal(view.model.current.selected, "ABC-7");
  assert.equal(state.reads.length, 0); assert.equal(state.requests[0].args[2], "ABC-7");
});

test("direct lookup accepts the configured Jira browse URL and normalizes to its issue key", () => {
  const { view, state, cx } = harness(); state.focus = null; state.live = [];
  view.model.useSource(null); view.input.value = () => "https://jira.example.test/browse/ABC-8?jql=project%3DABC#details";
  view.submit(cx);
  assert.equal(view.model.current.selected, "ABC-8");
  assert.equal(state.requests[0].args[2], "ABC-8");
  assert.equal(state.reads.length, 0);
});

test("invalid explicit lookups preserve the current selection and make no requests", () => {
  for (const value of ["XYZ-9", "https://other.example.test/browse/ABC-9", "https://[invalid/browse/ABC-9"]) {
    const { view, state, cx } = harness();
    view.model.merge(["ABC-1"]);
    view.input.set_value(value); view.inputChanged(cx); view.submit(cx);
    assert.ok(view.lookupError, `expected an error for ${value}`);
    assert.equal(view.model.current.selected, "ABC-1");
    assert.equal(state.requests.length, 0);
  }
});

test("editing and a valid manual lookup clear lookup errors", () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1"]);
  view.input.set_value("XYZ-9"); view.inputChanged(cx); view.submit(cx);
  assert.ok(view.lookupError);
  view.input.set_value("ABC-7"); view.inputChanged(cx);
  assert.ok(!view.lookupError);
  // A successful submit clears stale feedback even if it was already present.
  view.lookupError = "Previous lookup failed";
  view.submit(cx);
  assert.ok(!view.lookupError);
  assert.equal(view.model.current.selected, "ABC-7");
  assert.equal(state.requests[0].args[2], "ABC-7");
});

test("lookup guidance is retired with its connection or source", () => {
  for (const operation of ["connect", "invalidate", "clear", "source"]) {
    const { view, state, cx } = harness();
    view.lookupError = "Use the previous connection's project";
    if (operation === "connect") view.connect(cx, "/fictional/new-config");
    if (operation === "invalidate") view.invalidate(cx);
    if (operation === "clear") view.clearCache(cx);
    if (operation === "source") { state.focus = { terminal: "remote/t1" }; view.adoptSource(cx); }
    assert.ok(!view.lookupError, `stale guidance after ${operation}`);
  }
});

test("resuming Follow clears validation along with the rejected query", () => {
  const { view, cx } = harness();
  view.model.merge(["ABC-1"]); view.model.filter("XYZ-9"); view.lookupError = "Wrong project";
  view.follow(cx);
  assert.equal(view.model.current.query, "");
  assert.ok(!view.lookupError);
});

test("submitting a summary filter selects the first matching issue", () => {
  const { view, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
  view.model.metadata.set("ABC-2", { key: "ABC-2", summary: "Catalog filters" });
  view.model.metadata.set("ABC-3", { key: "ABC-3", summary: "Catalog filters too" });
  view.input.set_value("catalog filters"); view.inputChanged(cx); view.submit(cx);
  assert.equal(view.model.current.selected, "ABC-2");
  assert.ok(!view.lookupError);
});

test("copy feedback preserves the existing note and an old timer cannot clear a newer copy", () => {
  const { view, state, cx } = harness();
  view.note = "Existing status";
  view.copy("ABC-1", cx, "First copy");
  const firstTimer = state.timers.at(-1);
  assert.equal(view.copyNote, "First copy");
  view.copy("https://jira.example.test/browse/ABC-1", cx, "Second copy");
  const secondTimer = state.timers.at(-1);
  assert.deepEqual(state.clipboard, ["ABC-1", "https://jira.example.test/browse/ABC-1"]);
  assert.equal(view.note, "Existing status");
  firstTimer.fire();
  assert.equal(view.copyNote, "Second copy");
  secondTimer.fire();
  assert.ok(!view.copyNote);
  assert.equal(view.note, "Existing status");
});

test("copy supplies default feedback when no label is given", () => {
  const { view, state, cx } = harness();
  view.copy("ABC-1", cx);
  assert.deepEqual(state.clipboard, ["ABC-1"]);
  assert.ok(view.copyNote);
  state.timers.at(-1).fire();
  assert.ok(!view.copyNote);
});

test("History asks for up to 200 history lines explicitly and ignores a source race", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.history(cx);
  assert.deepEqual(state.reads[0].args, ["read", "t1", "--lines", "200"]);
  view.model.useSource("remote/t1");
  view.model.useSource("t1");
  state.reads[0].resolve({ code: 0, stdout: "ABC-7" }); await turn();
  assert.deepEqual(view.model.current.keys, []);
  view.history(cx);
  state.reads[1].resolve({ code: 0, stdout: "ABC-8" }); await turn();
  assert.deepEqual(view.model.current.keys, ["ABC-8"]);
  assert.match(view.note, /alternate-screen history may be unavailable/);
});

test("History coalesces duplicate requests and runs after an in-flight screen read", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.scan(cx); view.history(cx); view.history(cx); view.history(cx);
  assert.equal(state.reads.length, 1);
  assert.deepEqual(state.reads[0].args, ["read", "t1", "--lines", "0"]);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.equal(state.reads.length, 2);
  assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "200"]);
  view.history(cx); view.history(cx);
  assert.equal(state.reads.length, 2);
  state.reads[1].resolve({ code: 0, stdout: "" }); await turn();
  assert.equal(view.model.current.selected, null, "history did not confirm the screen candidate");
  await confirmScreen(view, state, "ABC-1");
  assert.equal(view.model.current.selected, "ABC-1");
  assert.match(view.note, /alternate-screen history may be unavailable/);
  assert.equal(state.reads.length, 3);
});

test("a screen scan requested during History runs after the History result", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.history(cx); view.scan(cx);
  assert.equal(state.reads.length, 1);
  assert.deepEqual(state.reads[0].args, ["read", "t1", "--lines", "200"]);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1 ABC-2" }); await turn();
  assert.deepEqual(view.model.current.keys, ["ABC-2", "ABC-1"]);
  assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "0"]);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  assert.deepEqual(view.model.current.keys, ["ABC-2", "ABC-1"]);
});

test("queued History and screen reads serialize without losing the fresh screen", async () => {
  const { view, state, cx } = harness(); view.pump = () => {};
  view.scan(cx); view.scan(cx); view.history(cx);
  state.reads[0].resolve({ code: 0, stdout: "ABC-1" }); await turn();
  assert.deepEqual(state.reads[1].args, ["read", "t1", "--lines", "200"]);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2" }); await turn();
  assert.deepEqual(state.reads[2].args, ["read", "t1", "--lines", "0"]);
  state.reads[2].resolve({ code: 0, stdout: "ABC-3" }); await turn();
  await confirmScreen(view, state, "ABC-3");
  assert.deepEqual(view.model.current.keys, ["ABC-3", "ABC-2"]);
  assert.equal(state.reads.length, 4);
});

test("programmatic input synchronization and passive scans do not extend Live inactivity", () => {
  const { view, state, cx } = harness();
  view.model.filter("fixture"); view.input.value = () => "fixture";
  view.lastInteraction = 1000;
  view.inputChanged(cx); view.scan(cx);
  assert.equal(view.lastInteraction, 1000);
  assert.deepEqual(state.reads[0].args, ["read", "t1", "--lines", "0"]);
});

test("opt-in live refresh is minute bounded, serialized, and retains stale data on failure", async () => {
  const { view, state, cx } = harness();
  let now = 1_000_000; view.now = () => now;
  view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1", summary: "Cached fixture", fetchedAt: 1000 });
  view.live = true; view.lastInteraction = now; view.lastLiveAttempt = now - 59999; view.scheduleLive(cx);
  assert.equal(state.timers[0].ms, 60000);
  state.timers[0].fire();
  assert.equal(state.requests.length, 0);
  now += 1;
  state.timers[1].fire();
  assert.equal(state.requests.length, 1);
  assert.deepEqual(state.requests[0].args, ["issue", config.context, "ABC-1", "refresh"]);
  assert.equal(view.model.current.selected, "ABC-1");
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.equal(view.model.details.get("ABC-1").summary, "Cached fixture");
  assert.equal(view.model.retryAfter, now + 30000);
  state.timers[2].fire(); assert.equal(state.requests.length, 1);
  now += 30000; state.timers[3].fire(); assert.equal(state.requests.length, 1);
  now += 30000; state.timers[4].fire(); assert.equal(state.requests.length, 2);
  state.requests[1].resolve({ ok: false, error: "request_failed" }); await turn();
  let persisted; view.savePreferences = () => { persisted = { live: view.live }; };
  now = view.lastInteraction + 5 * 60000;
  state.timers[5].fire();
  assert.equal(view.live, false); assert.equal(view.idlePaused, true); assert.equal(persisted, undefined);
  assert.equal(state.timers.length, 6);
});

test("a delayed clear cannot reconnect an older directory after a newer connection starts", async () => {
  const { view, state, cx } = harness(); view.configDir = "/fictional/config";
  view.model.merge(["ABC-1"]); view.pump(cx);
  const clear = deferred(), nextConfig = deferred();
  view.bridge = (operation, ...args) => {
    if (operation === "clear") { state.requests.push({ args, ...clear }); return clear.promise; }
    if (operation === "config") return nextConfig.promise;
    throw new Error("unexpected bridge operation");
  };
  view.clearCache(cx);
  const clearJob = state.jobs.at(-1);
  assert.equal(view.model.config, null); assert.equal(view.model.details.size, 0);
  assert.deepEqual(state.requests[1].args, [config.context]);
  view.connect(cx, "/fictional/new-config");
  const newEpoch = view.epoch;
  assert.equal(view.configDir, "/fictional/new-config");
  assert.equal(view.clearing, false);
  clear.resolve({ ok: true }); await clearJob;
  assert.equal(view.epoch, newEpoch);
  assert.equal(view.configDir, "/fictional/new-config");
  assert.equal(view.model.config, null);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Old" } }); await turn();
  assert.equal(view.model.details.size, 0);
});

test("freshness remains truthful without periodic rendering", () => {
  const { view } = harness();
  const issue = { fetchedAt: Date.UTC(2026, 9, 31, 10, 15), loadedAt: Date.UTC(2026, 9, 31, 11, 15) };
  view.now = () => issue.loadedAt;
  const label = view.freshnessLabel(issue);
  assert.equal(label, "Fetched 31 Oct 2026 · 10:15 UTC");
  view.now = () => issue.loadedAt + 3600000;
  assert.equal(view.freshnessLabel(issue), label);
});

test("Live skips busy requests and pausing cannot leave automatic work queued", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1"]); view.live = true; view.lastInteraction = view.now();
  view.pump(cx);
  const revision = view.revision;
  view.refresh(cx, true); view.refresh(cx, true);
  assert.equal(view.revision, revision); assert.equal(state.requests.length, 1);
  view.live = false;
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Completed" } });
  await turn();
  assert.equal(state.requests.length, 1);
  assert.equal(view.model.details.get("ABC-1").summary, "Completed");
  view.refresh(cx, true); assert.equal(state.requests.length, 1);
});

test("an expired Live lease cannot queue another request", () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1"]); view.live = true;
  view.lastInteraction = view.now() - 5 * 60000;
  view.refresh(cx, true);
  assert.equal(state.requests.length, 0); assert.equal(view.forceKey, undefined);
});

test("automatic refresh leaves the spare slot available while an earlier request is still running", () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1"]); view.model.accept({ key: "ABC-1" });
  view.live = true; view.lastInteraction = view.now();
  view.backgroundRequest = { phase: "metadata", epoch: view.epoch };
  const revision = view.revision;
  view.refresh(cx, true);
  assert.equal(state.requests.length, 0); assert.equal(view.revision, revision); assert.equal(view.forceKey, undefined);
});

test("manual refresh restores eligibility for every superseded metadata row", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
  view.model.accept({ key: "ABC-1", summary: "Selected" }); view.pump(cx);
  assert.deepEqual(state.requests[0].args, ["metadata", config.context, "ABC-2", "ABC-3"]);
  assert.equal(view.request.phase, "metadata"); assert.equal(view.request.key, null);
  view.refresh(cx);
  assert.equal(view.request.phase, "issue"); assert.equal(view.request.key, "ABC-1");
  assert.equal(view.backgroundRequest.phase, "metadata");
  state.requests[0].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-2", summary: "Old batch" }] });
  await turn();
  assert.equal(view.model.metadataAttempts.has("ABC-2"), false);
  assert.equal(view.model.metadataAttempts.has("ABC-3"), false);
  assert.deepEqual(state.requests[1].args, ["issue", config.context, "ABC-1", "refresh"]);
  assert.equal(view.request.phase, "issue"); assert.equal(view.request.key, "ABC-1");
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Fresh" } });
  await turn();
  assert.deepEqual(state.requests[2].args, ["metadata", config.context, "ABC-2", "ABC-3"]);
  assert.equal(view.request.phase, "metadata"); assert.equal(view.request.key, null);
  state.requests[2].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-2", summary: "Ready" }, { key: "ABC-3", summary: "Ready too" }] });
  await turn();
  assert.equal(view.request, null);
  assert.equal(view.model.metadata.get("ABC-3").summary, "Ready too");
});

test("manual refresh retries failed metadata for the current source without retrying omissions", async () => {
  const { view, state, cx } = harness(); let now = 1_000_000; view.now = () => now;
  view.model.merge(["ABC-1", "ABC-2", "ABC-3"]);
  view.model.accept({ key: "ABC-1", summary: "Selected" }); view.pump(cx);
  state.requests[0].resolve({ ok: true, context: config.context, rows: [] }); await turn();
  view.model.merge(["ABC-4"]); view.model.select("ABC-1"); view.pump(cx);
  assert.deepEqual(state.requests[1].args, ["metadata", config.context, "ABC-4"]);
  state.requests[1].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.equal(view.model.retryAfter, 0, "metadata failure must not delay issue selection");
  view.live = true; view.lastInteraction = now; now += 30000;
  view.refresh(cx, true);
  assert.deepEqual(state.requests[2].args, ["issue", config.context, "ABC-1", "refresh"]);
  state.requests[2].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Automatic" } }); await turn();
  assert.equal(state.requests.length, 3);
  view.refresh(cx);
  assert.equal(view.model.details.get("ABC-1").summary, "Automatic");
  state.requests[3].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Fresh" } }); await turn();
  assert.deepEqual(state.requests[4].args, ["metadata", config.context, "ABC-4"]);
  state.requests[4].resolve({ ok: true, context: config.context, rows: [{ key: "ABC-4", summary: "Recovered catalog", status: "Ready" }] }); await turn();
  view.model.filter("recovered catalog");
  assert.deepEqual(view.model.rows(), ["ABC-4"]);
  assert.equal(view.model.details.get("ABC-1").summary, "Fresh");
  assert.equal(state.requests.length, 5);
});

test("manual refresh only reopens failed metadata keys in the current source", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2"]); view.model.accept({ key: "ABC-1" }); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  view.model.useSource("remote/t1"); view.model.merge(["ABC-3"]); view.model.accept({ key: "ABC-3" });
  view.refresh(cx);
  state.requests[1].resolve({ ok: true, context: config.context, issue: { key: "ABC-3" } }); await turn();
  assert.equal(view.model.metadataAttempts.has("ABC-2"), true);
  assert.equal(state.requests.length, 2);
});

test("Follow loads a revisited known issue and unchanged screens do not request it again", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-2", "ABC-1"]);
  view.model.accept({ key: "ABC-2", summary: "Earlier topic" });
  view.scan(cx);
  state.reads[0].resolve({ code: 0, stdout: "ABC-2 then ABC-1" }); await turn();
  assert.equal(view.model.current.selected, "ABC-1");
  assert.deepEqual(state.requests[0].args, ["issue", config.context, "ABC-1"]);
  state.requests[0].resolve({ ok: true, context: config.context, issue: { key: "ABC-1", summary: "Current topic" } }); await turn();
  assert.equal(view.model.detail("ABC-1").summary, "Current topic");
  assert.deepEqual(state.scrolls.at(-1), [1, "center"]);
  view.scan(cx);
  state.reads[1].resolve({ code: 0, stdout: "ABC-2 then ABC-1" }); await turn();
  assert.equal(state.requests.length, 1);
});

test("connection invalidation discards failed metadata retry keys", async () => {
  const { view, state, cx } = harness();
  view.model.merge(["ABC-1", "ABC-2"]); view.model.accept({ key: "ABC-1" }); view.pump(cx);
  state.requests[0].resolve({ ok: false, error: "request_failed" }); await turn();
  assert.ok(view.failedMetadata.keys.has("ABC-2"));
  view.invalidate(cx);
  assert.equal(view.failedMetadata, null);
  assert.equal(view.model.metadataAttempts.size, 0);
});

test("highlight follows the selected key, preserves Paused filtering, and persists only boolean preferences", () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  view.model.merge(["ABC-1", "ABC-2"]); view.syncHighlight(); view.syncHighlight();
  assert.deepEqual(state.highlights, [["t1", "ABC-1"]]);
  view.model.filter("no matching rows"); view.syncHighlight();
  assert.equal(view.model.current.follow, false); assert.deepEqual(view.model.rows(), []);
  assert.equal(state.highlights.length, 1);
  view.select("ABC-2", cx); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-2"]);
  view.toggleHighlight(cx); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), [null, null]);
  view.toggleHighlight(cx);
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-2"]);
  for (const [name, json] of state.saved) {
    assert.equal(name, "preferences");
    const saved = JSON.parse(json);
    assert.deepEqual(Object.keys(saved).sort(), ["highlightSource", "live"]);
    assert.ok(Object.values(saved).every(value => typeof value === "boolean"));
  }
});

test("highlight uses full remote identity, honors pinning, and clears for disappeared or manual sources", () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  view.model.merge(["ABC-1"]); view.syncHighlight(); view.model.pinned = true;
  state.focus = { terminal: "t1", shown: "remote/t1", pane: "pane-only" };
  view.adoptSource(cx, false); assert.equal(state.highlights.length, 1);
  view.model.pinned = false; view.adoptSource(cx, false);
  assert.deepEqual(state.highlights.at(-1), [null, null]);
  view.model.merge(["ABC-2"]); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), ["remote/t1", "ABC-2"]);
  state.live = [{address: "t1", state: "live"}]; view.adoptSource(cx, false);
  assert.deepEqual(state.highlights.at(-1), [null, null]);
  state.live.push({address: "remote/t1", state: "live"}); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), ["remote/t1", "ABC-2"]);
  view.model.useSource("manual"); view.model.merge(["ABC-3"]); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), [null, null]);
});

test("highlight rejects invalid or oversized keys, missing config and pane-only identities", () => {
  const {view, state} = harness(true);
  view.model.merge(["ABC-1"]); view.syncHighlight();
  for (const key of [null, "abc-1", "OTHER-1", "ABC-1 extra", `ABC-${"1".repeat(125)}`, "ABC-１"]) {
    view.model.current.selected = key; view.syncHighlight();
    assert.deepEqual(state.highlights.at(-1), [null, null]);
  }
  view.model.current.selected = "ABC-1"; view.syncHighlight(); view.model.config = null; view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), [null, null]);
  view.model.config = config; view.model.useSource("pane-only"); view.model.merge(["ABC-1"]); view.syncHighlight();
  assert.deepEqual(state.highlights.at(-1), [null, null]);
});

test("passive discovery highlights confirmed keys and ignores stale source reads", async () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  view.model.merge(["ABC-1"]); view.syncHighlight(); view.scan(cx);
  state.reads[0].resolve({code: 0, stdout: "ABC-2"}); await turn();
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-1"]);
  await confirmScreen(view, state, "ABC-2");
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-2"]);
  view.model.browse(); view.scan(cx);
  state.reads[2].resolve({code: 0, stdout: "ABC-3"}); await turn();
  await confirmScreen(view, state, "ABC-3");
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-2"]);
  view.follow(cx); assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-3"]);
  state.focus = {terminal: "remote/t1"}; view.adoptSource(cx, false);
  state.reads[4].resolve({code: 0, stdout: "ABC-4"}); await turn();
  assert.deepEqual(state.highlights.at(-1), [null, null]);
  state.reads[5].resolve({code: 0, stdout: "ABC-5"}); await turn();
  await confirmScreen(view, state, "ABC-5");
  assert.deepEqual(state.highlights.at(-1), ["remote/t1", "ABC-5"]);
});

test("direct lookup highlights its actual source and reset paths immediately clear pending work", () => {
  for (const action of ["invalidate", "clearCache", "connect"]) {
    const {view, state, cx} = harness(true); view.pump = () => {}; view.configDir = "/fictional/config";
    view.input.set_value("abc-8"); view.submit(cx);
    assert.deepEqual(state.highlights, [["t1", "ABC-8"]]);
    view[action](cx); assert.deepEqual(state.highlights.at(-1), [null, null], action);
    view.syncHighlight(); assert.equal(state.highlights.length, 2);
  }
});

test("stock hosts safely skip highlighting on every transition", () => {
  const {view, state, cx} = harness(); view.pump = () => {};
  view.model.merge(["ABC-1"]); view.syncHighlight(); view.select("ABC-1", cx);
  view.toggleHighlight(cx); view.invalidate(cx); view.syncHighlight();
  assert.equal(view.highlightSupported, false); assert.deepEqual(state.highlights, []); assert.deepEqual(state.saved, []);
});

test("a native rejected target clears the old mark without retrying every render", () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  view.model.merge(["ABC-1", "ABC-2"]); view.syncHighlight();
  state.highlightResult = false; view.select("ABC-2", cx);
  assert.deepEqual(state.highlights, [["t1", "ABC-1"], ["t1", "ABC-2"], [null, null]]);
  view.syncHighlight(); view.syncHighlight(); assert.equal(state.highlights.length, 3);
  view.toggleHighlight(cx); state.highlightResult = true; view.toggleHighlight(cx);
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-2"]);
});

test("close clears this copy once and pending scan completion cannot reapply its highlight", async () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  view.model.merge(["ABC-1"]); view.syncHighlight(); view.scan(cx);
  await view.close(cx);
  assert.deepEqual(state.highlights, [["t1", "ABC-1"], [null, null]]);
  state.reads[0].resolve({code: 0, stdout: "ABC-2"}); await turn();
  assert.equal(view.model.current.selected, "ABC-1", "closed copies reject late discovery");
  assert.equal(view.confirmRead, null);
  view.syncHighlight(); view.adoptSource(cx, false); view.toggleHighlight(cx); await view.close(cx);
  assert.deepEqual(state.highlights, [["t1", "ABC-1"], [null, null]]);
});

test("native exceptions are contained, failed pairs do not repeat, and off/on retries", async () => {
  const {view, state, cx} = harness(true); view.pump = () => {};
  state.highlightThrows = true; view.model.merge(["ABC-1"]);
  assert.doesNotThrow(() => view.select("ABC-1", cx));
  assert.equal(view.highlightError, true);
  assert.deepEqual(state.highlights, [["t1", "ABC-1"], [null, null]]);
  view.syncHighlight(); view.syncHighlight(); assert.equal(state.highlights.length, 2);
  assert.doesNotThrow(() => view.toggleHighlight(cx));
  view.syncHighlight(); assert.equal(state.highlights.length, 3);
  state.highlightThrows = false; view.toggleHighlight(cx);
  assert.deepEqual(state.highlights.at(-1), ["t1", "ABC-1"]); assert.equal(view.highlightError, false);
  state.highlightThrows = true; await assert.doesNotReject(view.close(cx));
  view.syncHighlight(); assert.deepEqual(state.highlights.at(-1), [null, null]);
});

test("Paused highlight clears for non-live terminal records and restores at the same live address", () => {
  for (const address of ["t1", "remote/t1"]) {
    const {view, state} = harness(true);
    view.model.useSource(address); view.model.merge(["ABC-1"]); view.model.filter("retain filter");
    view.syncHighlight();
    const terminal = state.live.find(t => t.address === address);
    assert.deepEqual(state.highlights, [[address, "ABC-1"]]);
    for (const unavailable of ["finished", "pending", undefined]) {
      terminal.state = unavailable;
      view.syncHighlight(); view.syncHighlight();
      assert.deepEqual(state.highlights.at(-1), [null, null]);
      assert.equal(view.highlightTarget, null); assert.equal(view.highlightKey, null);
      assert.equal(view.model.current.selected, "ABC-1");
      assert.equal(view.model.current.follow, false); assert.equal(view.model.current.query, "retain filter");
      const count = state.highlights.length;
      view.syncHighlight(); assert.equal(state.highlights.length, count);
      terminal.state = "live"; view.syncHighlight(); view.syncHighlight();
      assert.equal(state.highlights.length, count + 1);
      assert.deepEqual(state.highlights.at(-1), [address, "ABC-1"]);
    }
    assert.equal(state.timers.length, 0); assert.equal(state.reads.length, 0);
  }
});
