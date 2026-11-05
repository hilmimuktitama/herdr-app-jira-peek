// Event/state integration only. Native geometry is checked with Computer Use.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as model from "../mods/jira-peek/model.js";
import { seedDemo } from "../mods/jira-peek/demo.js";

const code = readFileSync(new URL("../mods/jira-peek/main.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export default class", "return class");

function harness(highlight = false, nativeInput = false) {
  const elements = new Map();
  const host = { settings: { ui_font_size: 13, font_size: 14, zoom: 1 }, focus: null, panes: [], terminals: [], runs: [], urls: [], clipboard: [], traversal: [], highlights: [], folder: Promise.resolve(null) };
  host.props = { demo: true };
  host.layout = { id: "root", children: [{ id: "fixture-peek", content: { mod: "jira-peek" }, size: { px: 360 } }] };
  host.closedOverlays = [];
  host.storage = new Map([["preferences", '{"live":false,"readerFocus":false}']]);
  host.files = new Map(); host.jobs = []; host.timers = [];
  let active = null;
  const activate = target => {
    if (active === target) return;
    const previous = active; active = target;
    previous?.blur?.(); target?.onFocus?.();
  };
  const element = (id) => {
    const state = { childNodes: [], events: {}, properties: {} };
    const node = new Proxy(state, { get(target, property) {
      if (property in target) return target[property];
      return (...args) => {
        if (property === "id") elements.set(args[0], node);
        else if (property === "when" && args[0]) args[1](node);
        else if (property === "child") state.childNodes.push(args[0]);
        else if (property === "children") state.childNodes.push(...args[0]);
        else if (property.startsWith("on_")) state.events[property] = args[0];
        else state.properties[property] = args;
        return node;
      };
    }});
    if (id) elements.set(id, node);
    return node;
  };
  const focus = () => {
    const handle = { focus() { activate(handle); }, is_focused() { return active === handle; } };
    return handle;
  };
  const cx = { stopped: false, notify() {}, stop_propagation() { this.stopped = true; }, focus_handle: focus, spawn() {},
    timer: { after(ms, fn) { const timer = { ms, cancel() {}, fire: () => fn(cx) }; host.timers.push(timer); return timer; } },
    open_url(url) { host.urls.push(url); }, write_to_clipboard(value) { host.clipboard.push(value); } };
  const InputState = { new(options = {}) { return { options, text: options.value || "", events: {},
    on(name, fn) { this.events[name] = fn; }, value() { return this.text; },
    set_value(value) { this.text = value; },
    edit(value) { this.text = value; this.events.change?.({}, cx); },
    focus() { activate(this); }, onFocus() { this.events.focus?.({}, cx); }, blur() { this.events.blur?.({}, cx); },
    is_focused() { return active === this; }, set_selected_range(range) { this.selection = range; }, set_masked() {}, release() {} }; } };
  const api = { herdr: highlight ? { setTerminalHighlight(...args) { host.highlights.push(args); if (host.highlightThrows) throw new Error("fictional native failure"); if (host.highlightResult === false) return false; host.marked = args[0] ? args : null; return true; } } : {}, ...model, View: class {}, seedDemo, div: () => element(), h_flex: () => element(), v_flex: () => element(),
    svg: path => { const node = element(); node.properties.asset = path; return node; },
    Button: { new: element }, Toggle: { new: element }, Input: { new: () => element() }, InputState,
    Scrollbar: { vertical: () => element() }, v_virtual_list: id => element(id),
    VirtualListScrollHandle: { new: () => ({ scroll_to_item() {} }) },
    localStorage: { getItem: key => host.storage.get(key) || null, setItem(key, value) {
      if (host.saveThrows) throw new Error("fictional storage failure");
      host.storage.set(key, value);
    }, removeItem: key => host.storage.delete(key) },
    appHome: () => "/fictional/herdr-app",
    readTextFile: async path => host.readFile ? host.readFile(path) : host.files.get(path) ?? null,
    writeTextFile: async (path, text, expected) => {
      host.beforeWrite?.();
      if (host.fileWriteThrows || (host.files.get(path) ?? null) !== expected) throw new Error("File changed or unavailable");
      host.files.set(path, text);
    },
    props: () => host.props, layout: () => host.layout, settings: () => host.settings, theme: () => ({}), panes: () => host.panes,
    window: { focus_next: () => host.traversal.push("next"), focus_prev: () => host.traversal.push("previous") },
    focused: () => host.focus, terminals: () => host.terminals,
    run: (name, args) => { host.runs.push({ name, args }); }, pickFolder: () => host.folder };
  api.herdr.closeOverlay = id => host.closedOverlays.push(id);
  api.herdr.commands = () => nativeInput ? [{ name: "layout.focus" }] : [];
  host.shared = new Map();
  api.herdr.shared = key => host.shared.get(key);
  api.herdr.setShared = (key, value) => host.shared.set(key, value);
  const Constructor = new Function(...Object.keys(api), code)(...Object.values(api));
  const view = new Constructor(); view.init({}, cx);
  const render = () => { elements.clear(); view.render(cx); return elements; };
  const key = (value, modifiers = {}) => ({ key: value,
    keystroke: [modifiers.control && "ctrl", modifiers.alt && "alt", modifiers.shift && "shift", modifiers.platform && "cmd", value].filter(Boolean).join("-"),
    modifiers: { control: false, alt: false, shift: false, platform: false, function: false, ...modifiers } });
  const dispatch = (value, modifiers = {}) => {
    cx.stopped = false;
    render().get("jira-peek").events.on_key_down(key(value, modifiers), cx);
    return cx.stopped;
  };
  return { view, cx, render, key, dispatch, host };
}

function childText(node) {
  if (typeof node === "string" || typeof node === "number") return [String(node)];
  return (node?.childNodes || []).flatMap(childText);
}

function readerText(h) {
  const { source, current } = h.view.model;
  return childText(h.render().get(`reader-${h.view.epoch}-${source}-${current.selected}`));
}

async function nativeFields(h) {
  h.view.demo = false; h.view.configDir = "/fictional/connection-one";
  h.cx.spawn = fn => { h.host.jobs.push(fn(h.cx)); return { cancel() {} }; };
  await h.view.loadFieldLayout(h.cx, true);
}

const nextTurn = () => new Promise(resolve => setImmediate(resolve));

function descendants(node) {
  if (!node || typeof node !== "object") return [];
  return [node, ...(node.childNodes || []).flatMap(descendants)];
}

test("Fields applies placement, labels, order and visibility without changing the selected issue or query", () => {
  const h = harness();
  h.view.model.filter("catalog");
  const selected = h.view.model.current.selected;
  h.view.openFields(h.cx);
  h.render().get("field-place-assignee-header").events.on_click({}, h.cx);
  h.render().get("field-place-status-hidden").events.on_click({}, h.cx);
  h.render().get("field-up-description").events.on_click({}, h.cx);
  h.view.fieldEditor.labels.get("description").set_value("Acceptance notes");
  h.render().get("fields-apply").events.on_click({}, h.cx);
  assert.equal(h.view.fieldEditor, null);
  assert.equal(h.view.model.current.selected, selected);
  assert.equal(h.view.model.current.query, "catalog");
  const nodes = h.render();
  assert.ok(nodes.has("header-field-assignee"));
  assert.equal(nodes.has("header-field-status"), false);
  const reader = readerText(h);
  assert.ok(reader.indexOf("Acceptance notes") < reader.indexOf("Summary"));
  assert.ok(childText(nodes.get("jira-reader-title")).join(" ").includes(selected));
  assert.ok(nodes.has("open"));
  assert.equal(JSON.parse(h.host.storage.get(h.view.fieldLayoutKey)).fields.find(f => f.id === "status").section, "hidden");
});

test("default summary leads the heading once; customized placement and labels stay in the reader layout", () => {
  const h = harness(), issue = h.view.model.details.get("DEMO-1042");
  assert.deepEqual(childText(h.render().get("jira-issue-summary")), [issue.summary]);
  assert.equal(readerText(h).includes(issue.summary), false);
  assert.equal(readerText(h).includes("Description"), false);
  h.view.height = 400;
  assert.equal(readerText(h).filter(text => text === issue.summary).length, 1, "short panels scroll the title with the body");
  assert.equal(childText(h.render().get("jira-reader-title")).includes(issue.summary), false);
  h.view.height = 800;
  for (const section of ["hidden", "details", "header"]) {
    h.view.fieldLayout = model.defaultFieldLayout(h.view.model.config);
    h.view.fieldLayout.fields.find(field => field.id === "summary").section = section;
    h.view.detailsOpen = true;
    assert.equal(h.render().has("jira-issue-summary"), false, section);
    assert.equal(childText(h.render().get("jira-peek")).includes(issue.summary), section !== "hidden", section);
  }
  h.view.fieldLayout = model.defaultFieldLayout(h.view.model.config);
  h.view.fieldLayout.fields.find(field => field.id === "summary").label = "Outcome";
  assert.equal(h.render().has("jira-issue-summary"), false);
  assert.deepEqual(childText(h.render().get("reader-field-summary")), ["Outcome", issue.summary]);
});

test("Fields cancel, Escape and draft reset leave the saved layout untouched", () => {
  const h = harness(), before = structuredClone(h.view.fieldLayout);
  h.view.openFields(h.cx);
  h.view.fieldEditor.labels.get("summary").set_value("Discard this");
  assert.equal(h.dispatch("escape"), true);
  assert.equal(h.view.moreOpen, true);
  assert.deepEqual(h.view.fieldLayout, before);
  h.view.openFields(h.cx);
  h.render().get("field-remove-summary").events.on_click({}, h.cx);
  h.render().get("fields-reset").events.on_click({}, h.cx);
  assert.ok(h.view.fieldEditor.fields.some(f => f.id === "summary"));
  h.render().get("fields-back").events.on_click({}, h.cx);
  assert.deepEqual(h.view.fieldLayout, before);
  assert.equal(h.host.storage.has(h.view.fieldLayoutKey), false);
});

test("Fields adds custom IDs and empty fields, validates duplicates, and scopes persistence to the connection", () => {
  const h = harness();
  h.view.configDir = "/fictional/connection-one"; h.view.loadFieldLayout();
  h.view.openFields(h.cx);
  for (const id of ["customfield_10016", "duedate"]) {
    h.view.fieldEditor.add.set_value(id); h.render().get("fields-add").events.on_click({}, h.cx);
  }
  h.view.fieldEditor.labels.get("customfield_10016").set_value("Points");
  h.view.fieldEditor.showEmpty = true;
  h.view.fieldEditor.add.set_value("duedate"); h.view.addField(h.cx);
  assert.match(h.view.fieldEditor.error, /already listed/);
  h.view.fieldEditor.add.set_value("customfield_1;echo"); h.view.addField(h.cx);
  assert.match(h.view.fieldEditor.error, /supported Jira field ID/);
  h.view.model.details.get("DEMO-1042").metadata.push({ id: "customfield_10016", value: "0" });
  h.view.applyFields(h.cx);
  assert.deepEqual(childText(h.render().get("reader-field-customfield_10016")), ["Points", "0"]);
  assert.deepEqual(childText(h.render().get("reader-field-duedate")), ["Due date", "—"]);
  const saved = structuredClone(h.view.fieldLayout);
  h.view.configDir = "/fictional/connection-two"; h.view.loadFieldLayout();
  assert.equal(h.view.fieldLayout.fields.some(f => f.id === "customfield_10016"), false);
  h.view.configDir = "/fictional/connection-one"; h.view.model.config.context = "new-epoch"; h.view.loadFieldLayout();
  assert.deepEqual(h.view.fieldLayout, saved);
  h.view.model.config.base = "https://another.example.test"; h.view.loadFieldLayout();
  assert.equal(h.view.fieldLayout.fields.some(f => f.id === "customfield_10016"), false);
});

test("Fields keeps draft on storage failure, blocks changed connections and isolates reader shortcuts", () => {
  const h = harness(), before = structuredClone(h.view.fieldLayout);
  h.view.openFields(h.cx);
  h.view.fieldEditor.labels.get("summary").set_value("Draft title");
  for (const key of ["/", "up", "down", "enter"]) assert.equal(h.dispatch(key), false);
  h.view.handleCommand("refresh", h.cx);
  h.host.saveThrows = true; h.view.applyFields(h.cx);
  assert.match(h.view.fieldEditor.error, /Could not save/);
  assert.deepEqual(h.view.fieldLayout, before);
  h.host.saveThrows = false; h.view.model.config.context = "changed"; h.view.applyFields(h.cx);
  assert.match(h.view.fieldEditor.error, /connection changed/);
  assert.deepEqual(h.view.fieldLayout, before);
});

test("a field selection change discards an in-flight issue and reloads with the saved selection", async () => {
  const h = harness(), pending = [];
  await nativeFields(h); h.view.model.details.clear();
  h.view.bridge = (...args) => new Promise(resolve => pending.push({ args, resolve }));
  const key = h.view.model.current.selected, context = h.view.model.config.context;
  h.view.pump(h.cx);
  h.view.openFields(h.cx);
  h.render().get("field-place-description-hidden").events.on_click({}, h.cx);
  h.view.applyFields(h.cx);
  await nextTurn();
  assert.equal(pending.length, 1);
  pending[0].resolve({ ok: true, context, issue: { key, description: "Obsolete body" } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.view.model.details.has(key), false);
  assert.equal(pending.length, 2);
  pending[1].resolve({ ok: true, context, issue: { key, summary: "Fresh title", description: "" } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.view.model.details.get(key).summary, "Fresh title");
  assert.equal(h.render().has("reader-field-description"), false);
});

test("label and placement changes reuse already loaded data", async () => {
  const h = harness(); await nativeFields(h);
  const issue = h.view.model.details.get("DEMO-1042"), revision = h.view.revision;
  h.view.openFields(h.cx);
  h.view.fieldEditor.labels.get("summary").set_value("Title");
  h.render().get("field-place-assignee-body").events.on_click({}, h.cx);
  h.view.applyFields(h.cx);
  await nextTurn();
  assert.equal(h.view.fieldEditor, null);
  assert.equal(h.view.fieldLayout.fields.find(field => field.id === "summary").label, "Title");
  assert.equal(h.view.revision, revision);
  assert.equal(h.view.model.details.get("DEMO-1042"), issue);
});

test("native Fields migrates legacy preferences once and shares the file with agent edits", async () => {
  const h = harness(); h.view.pump = () => {};
  const legacyKey = "field-layout:/fictional/connection-one:" + h.view.model.config.base;
  const legacy = { version: 1, showEmpty: true, fields: [{ id: "priority", label: "Urgency", section: "header" }] };
  h.host.storage.set(legacyKey, JSON.stringify(legacy));
  await nativeFields(h);
  const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
  assert.equal(h.host.storage.has(legacyKey), false);
  assert.deepEqual(h.view.fieldLayout, legacy);
  assert.equal(file.connections.length, 1);
  const selected = h.view.model.current.selected;
  file.connections[0].fields[0].label = "Agent label";
  h.host.files.set(path, JSON.stringify(file)); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.fieldLayout.fields[0].label, "Agent label");
  assert.equal(h.view.model.current.selected, selected);
  h.view.openFields(h.cx);
  h.render().get("fields-path").events.on_click({}, h.cx);
  assert.equal(h.host.clipboard.at(-1), path);
  h.view.fieldEditor.labels.get("priority").set_value("UI label");
  h.view.applyFields(h.cx); await nextTurn();
  assert.equal(h.view.fieldEditor, null);
  assert.equal(JSON.parse(h.host.files.get(path)).connections[0].fields[0].label, "UI label");
  assert.equal(h.host.storage.has(legacyKey), false);
});

test("native Fields preserves other connections and restores defaults when an entry is removed", async () => {
  const h = harness(); h.view.pump = () => {}; await nativeFields(h);
  const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
  const other = { configDir: "/fictional/second", base: "https://another.example.test", fields: [] };
  file.connections.push(other); h.host.files.set(path, JSON.stringify(file)); await h.view.loadFieldLayout(h.cx);
  h.view.openFields(h.cx); h.view.fieldEditor.labels.get("summary").set_value("Task");
  h.view.applyFields(h.cx); await nextTurn();
  assert.deepEqual(JSON.parse(h.host.files.get(path)).connections.find(entry => entry.configDir === other.configDir), other);
  h.host.files.set(path, JSON.stringify({ version: 1, connections: [other] })); await h.view.loadFieldLayout(h.cx);
  assert.deepEqual(h.view.fieldLayout, model.defaultFieldLayout(h.view.model.config));
  h.view.configDir = other.configDir; h.view.model.config.base = other.base;
  await h.view.loadFieldLayout(h.cx, true);
  assert.deepEqual(h.view.fieldLayout.fields, []);
});

test("invalid agent edits keep the last valid layout, block UI writes and recover after repair", async () => {
  const h = harness(); h.view.pump = () => {}; await nativeFields(h);
  const path = h.view.fieldFilePath(), validText = h.host.files.get(path), validLayout = h.view.fieldLayout;
  h.view.openFields(h.cx);
  for (const badText of ["{", validText.replace('"header"', '"headre"')]) {
    h.host.files.set(path, badText); await h.view.loadFieldLayout(h.cx);
    assert.equal(h.view.fieldLayout, validLayout);
    assert.match(h.view.fieldFileError, /last valid layout/);
    h.view.applyFields(h.cx); assert.equal(h.host.files.get(path), badText);
  }
  h.host.files.set(path, validText); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.fieldFileError, "");
  h.view.applyFields(h.cx); await nextTurn(); assert.equal(h.view.fieldEditor, null);
});

test("a stale UI draft cannot overwrite an agent edit, even before the file watcher runs", async () => {
  for (const watchFirst of [true, false]) {
    const h = harness(); h.view.pump = () => {}; await nativeFields(h);
    h.view.openFields(h.cx); h.view.fieldEditor.labels.get("summary").set_value("Stale UI");
    const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
    file.connections[0].fields.find(field => field.id === "summary").label = "Agent wins";
    const agentText = JSON.stringify(file);
    if (watchFirst) { h.host.files.set(path, agentText); await h.view.loadFieldLayout(h.cx); }
    else h.host.beforeWrite = () => h.host.files.set(path, agentText);
    h.view.applyFields(h.cx); await nextTurn();
    assert.equal(h.host.files.get(path), agentText);
    assert.match(h.view.fieldEditor.error, /changed/);
    assert.equal(h.view.fieldLayout.fields.find(field => field.id === "summary").label, "Agent wins");
  }
});

test("failed migration retains legacy preferences and failed saves retain the UI draft", async () => {
  const h = harness(); h.view.pump = () => {};
  const legacyKey = "field-layout:/fictional/connection-one:" + h.view.model.config.base;
  const legacy = { version: 1, showEmpty: false, fields: [{ id: "summary", label: "Retained", section: "body" }] };
  h.host.storage.set(legacyKey, JSON.stringify(legacy)); h.host.fileWriteThrows = true;
  await nativeFields(h);
  assert.deepEqual(h.view.fieldLayout, legacy); assert.ok(h.host.storage.has(legacyKey));
  assert.match(h.view.fieldFileError, /Could not load/);
  h.host.fileWriteThrows = false; await h.view.loadFieldLayout(h.cx, true);
  const before = h.host.files.get(h.view.fieldFilePath());
  h.view.openFields(h.cx); h.view.fieldEditor.labels.get("summary").set_value("Unsaved");
  h.host.fileWriteThrows = true; h.view.applyFields(h.cx); await nextTurn();
  assert.equal(h.host.files.get(h.view.fieldFilePath()), before);
  assert.equal(h.view.fieldEditor.labels.get("summary").value(), "Unsaved");
  assert.equal(h.view.fieldEditor.busy, false);
  assert.deepEqual(h.view.fieldLayout, legacy);
});

test("a delayed field file read cannot replace a newer edit or a different connection", async () => {
  const h = harness(); h.view.pump = () => {}; await nativeFields(h);
  const original = h.host.files.get(h.view.fieldFilePath()), pending = [];
  h.host.readFile = () => new Promise(resolve => pending.push(resolve));
  const first = h.view.loadFieldLayout(h.cx), second = h.view.loadFieldLayout(h.cx);
  const edited = JSON.parse(original); edited.connections[0].fields = [];
  pending[1](JSON.stringify(edited)); await second;
  pending[0](original); await first;
  assert.deepEqual(h.view.fieldLayout.fields, []);
  const third = h.view.loadFieldLayout(h.cx); h.view.epoch++;
  pending[2](original); await third;
  assert.deepEqual(h.view.fieldLayout.fields, []);
});

test("Hide targets the attached layout block and retains reading state", () => {
  const h = harness();
  h.view.model.browse();
  h.view.model.filter("catalog");
  h.view.syncDisclosures();
  h.view.commentsOpen = true;
  const state = h.view.model.current;
  const before = structuredClone(state);
  const scroll = h.view.listScroll;
  h.host.focus = { space: "s1", tab: "tab1", pane: "p1", terminal: "t1" };
  h.host.panes = [{ pane: "p1", terminal: "t1", tab: "tab1" }];
  h.host.terminals = [{ address: "t1" }];
  h.view.rememberOrigin();
  h.view.actionFocus.hide.focus();
  const button = h.render().get("hide");
  assert.deepEqual(button.properties.accessibility_label, ["Hide Jira Peek"]);
  button.events.on_click({}, h.cx);
  assert.deepEqual(h.host.runs, [
    { name: "pane.focus", args: { pane: "p1" } },
    { name: "layout.hide", args: { id: "fixture-peek" } },
  ]);
  assert.equal(h.view.model.current, state);
  assert.deepEqual(state, before);
  assert.equal(h.view.listScroll, scroll);
  assert.equal(h.view.commentsOpen, true);
  assert.deepEqual(h.host.layout.children[0].size, { px: 360 });
});

test("closing an overlay leaves an attached Jira Peek panel alone", () => {
  const h = harness();
  h.host.props.overlay = "fixture-overlay";
  h.render().get("hide").events.on_click({}, h.cx);
  assert.deepEqual(h.host.closedOverlays, ["fixture-overlay"]);
  assert.deepEqual(h.host.runs, []);
});

test("Herdr UI font-size changes reach the panel without resetting reading state or applying zoom twice", () => {
  const h = harness();
  h.view.model.browse();
  h.view.model.filter("catalog");
  const selected = h.view.model.current.selected;
  for (const ui_font_size of [12, 13, 18]) {
    h.host.settings = { ui_font_size, font_size: 24, zoom: 1.5 };
    for (const helpTopic of [null, "peek"]) {
      h.view.helpTopic = helpTopic;
      const root = h.render().get("jira-peek");
      assert.deepEqual(root.properties.text_size, [ui_font_size]);
      const title = h.render().get("jira-issue-summary");
      assert.deepEqual(title.properties.text_size, [ui_font_size + 2]);
      assert.ok(descendants(root).slice(1).filter(node => node.properties.text_size).every(node =>
        [ui_font_size + 2, Math.max(11, ui_font_size - 1)].includes(node.properties.text_size[0])), "title and keycaps follow the UI size; the host applies zoom");
      assert.equal(h.view.model.current.selected, selected);
      assert.equal(h.view.model.current.query, "catalog");
      assert.equal(h.view.model.current.follow, false);
    }
  }
});

test("deferred, failed and empty comments retain the complete issue and a usable disclosure", () => {
  const h = harness(); h.render();
  const issue = h.view.model.details.get("DEMO-1042");
  issue.comments = []; issue.commentsTotal = 0; issue.commentsDeferred = true;
  h.view.commentsOpen = true;
  let text = readerText(h);
  assert.ok(text.includes(issue.description)); assert.ok(text.includes("Loading comments…"));
  assert.deepEqual(childText(h.render().get("comments-toggle")), ["Comments", "C"]);
  issue.commentsError = "permission_denied";
  text = readerText(h);
  assert.ok(text.includes(issue.description)); assert.ok(text.includes("Jira denied access to comments."));
  assert.ok(h.render().get("comments-retry"));
  issue.commentsError = ""; issue.commentsDeferred = false; issue.commentsLoaded = true;
  assert.ok(readerText(h).includes("No comments."));
  assert.deepEqual(childText(h.render().get("comments-toggle")), ["Comments (0)", "C"]);
});

test("unsupported content and deferred retry are explained without hiding the description", () => {
  const h = harness(); const issue = h.view.model.details.get("DEMO-1042");
  issue.unsupportedContent = true;
  assert.ok(readerText(h).includes(issue.description));
  assert.ok(readerText(h).includes("Some content is unsupported here. Open in Jira for the full issue."));
  h.view.model.details.delete("DEMO-1042"); h.view.model.retryAfter = h.view.now() + 30000;
  assert.ok(readerText(h).includes("Waiting to retry…"));
  h.view.model.failures.add("DEMO-1042"); h.view.model.denied.add("DEMO-1042");
  assert.ok(childText(h.render().get("jira-peek")).includes("Jira denied this request. Check issue access and token permissions."));
});

test("session titles stay out of the reader and Options; source identity is available in tooltips", () => {
  for (const kind of ["ordinary", "pinned", "manual", "missing"]) {
    const h = harness(); h.view.demo = false;
    const title = "Fictional terminal with a long descriptive title";
    h.host.panes = [{ pane: "p-example", terminal: "t-example", title }];
    h.host.terminals = [{ address: "t-example", title }];
    h.view.model.useSource(kind === "manual" ? "manual" : kind === "missing" ? null : "t-example");
    h.view.model.pinned = kind !== "ordinary";
    const defaultRender = h.render();
    assert.equal(defaultRender.get("jira-source-row"), undefined);
    assert.equal(childText(defaultRender.get("jira-peek")).includes(title), false, "session title must not appear in the default view");
    const indicator = defaultRender.get("jira-pinned-source");
    assert.equal(!!indicator, kind === "pinned", "only a pinned terminal gets the compact toolbar indicator");
    if (indicator) {
      assert.deepEqual(childText(indicator), ["Fixed terminal"]);
      assert.ok(Object.hasOwn(indicator.properties, "flex_none"), "pinned indicator must not shrink");
      assert.match(indicator.properties.tooltip?.[0] || "", /Fictional terminal.*Options/);
    }
    h.view.moreOpen = true;
    const optionsRender = h.render();
    const texts = childText(optionsRender.get("jira-peek-surface"));
    assert.equal(optionsRender.has("jira-source-row"), false, "Options must not render a session-title row");
    assert.equal(texts.includes(title), false, "Options must not repeat the session title");
    assert.doesNotMatch(texts.join(" "), /(?:Pinned )?terminal:/i);
    assert.equal(texts.includes("Fixed terminal"), false, "Options must not duplicate the reader marker");
    assert.deepEqual(childText(optionsRender.get("pin")), ["Keep this terminal", kind !== "ordinary" ? "On" : "Off"]);
    const source = kind === "manual" ? "Manual Jira lookup" : kind === "missing" ? "No terminal selected" : title;
    assert.ok(optionsRender.get("pin").properties.tooltip?.[0]?.includes(source), "Keep this terminal help retains optional source identity");
  }
});

test("search placeholder and accessible help explain filtering and direct Jira lookup", () => {
  const h = harness(); h.view.handleCommand("search", h.cx);
  assert.equal(h.view.input.options.placeholder, "Filter issues or enter a Jira key…");
  const nodes = descendants(h.render().get("search"));
  for (const property of ["accessibility_label", "tooltip"]) {
    const value = nodes.map(n => n.properties[property]?.[0]).find(Boolean);
    assert.ok(value, property);
    assert.match(value, /filter/i, property);
    assert.match(value, /(?:detected|discovered|loaded)/i, property);
    assert.match(value, /(?:Jira|issue).*(?:key|URL)/i, property);
    assert.match(value, /(?:URL|link)/i, property);
  }
});

test("empty guidance distinguishes automatic scanning, manual scanning and no terminal", () => {
  for (const kind of ["automatic", "manual", "missing"]) {
    const h = harness(); h.view.demo = false;
    const config = { ...h.view.model.config, interval: kind === "automatic" ? 5 : 0 };
    h.view.model.reset(config); h.view.model.pinned = true;
    if (kind !== "missing") h.view.model.useSource("t-empty");
    const text = childText(h.render().get("jira-peek"));
    assert.ok(text.includes(kind === "missing" ? "No terminal selected" : "No Jira issues detected"), kind);
    const helper = kind === "automatic" ? "Jira keys in this terminal appear here automatically."
      : kind === "manual" ? "Enter a Jira key, or use Options → Scan screen."
      : "Focus a terminal with Jira activity, or enter a Jira key.";
    assert.ok(text.includes(helper), kind);
  }
});

test("Details reveals freshness and metadata, pauses Follow, and survives a same-issue refresh", () => {
  const h = harness();
  const issue = h.view.model.details.get("DEMO-1042");
  const fetchedAt = Date.parse("2026-10-30T08:45:00Z");
  issue.fetchedAt = fetchedAt;
  issue.metadata = [{ id: "assignee", label: "Assignee", value: "Mira Fiction" }, { id: "priority", label: "Priority", value: "Urgent" }];
  const freshness = `Fetched ${model.displayDate(new Date(fetchedAt).toISOString())} · 08:45 UTC`;
  assert.equal(h.view.model.current.follow, true);
  for (const value of [freshness, ...issue.metadata.flatMap(field => [field.label, field.value])]) {
    assert.equal(readerText(h).includes(value), false, value);
  }
  h.render().get("details-toggle").events.on_click({}, h.cx);
  assert.equal(h.view.model.current.follow, false);
  for (const value of [freshness, ...issue.metadata.flatMap(field => [field.label, field.value])]) {
    assert.ok(readerText(h).includes(value), value);
  }
  h.view.fieldLayout.fields.push({ id: "customfield_10016", label: "Team", section: "details" });
  h.view.model.accept({ ...issue, metadata: [...issue.metadata, { id: "customfield_10016", label: "Team", value: "Orchid" }] });
  assert.ok(readerText(h).includes("Orchid"));
  assert.ok(readerText(h).includes(freshness));
  h.render().get("details-toggle").events.on_click({}, h.cx);
  assert.equal(readerText(h).includes("Orchid"), false);
});

test("Details remains available without metadata and resets for a different issue or source", () => {
  const h = harness();
  const issue = h.view.model.details.get("DEMO-1042");
  issue.metadata = [];
  issue.fetchedAt = Date.parse("2026-10-30T08:45:00Z");
  const freshness = h.view.freshnessLabel(issue);
  h.render().get("details-toggle").events.on_click({}, h.cx);
  assert.ok(readerText(h).includes(freshness));
  h.view.select("DEMO-1038", h.cx);
  assert.equal(readerText(h).includes("Alex Example"), false);
  h.view.select("DEMO-1042", h.cx);
  assert.equal(readerText(h).includes(freshness), false);
  h.render().get("details-toggle").events.on_click({}, h.cx);
  assert.ok(readerText(h).includes(freshness));
  h.view.model.useSource("t-fictional-other");
  h.view.model.merge(["DEMO-1042"]);
  assert.equal(readerText(h).includes(freshness), false);
});

test("the entire multiline description is visible immediately and stays complete on refresh and source switch", () => {
  const h = harness();
  const originalSource = h.view.model.source;
  const issue = h.view.model.details.get("DEMO-1042");
  const description = `Fictional requirements:\n${"Context about the fictional catalog. ".repeat(20)}\nAcceptance criteria:\n- Preserve filters.\n- Final criterion: restore the selected issue.`;
  issue.description = description; issue.truncated = true;
  let text = readerText(h);
  assert.ok(text.includes(description));
  assert.ok(text.includes("Some issue content is shortened."));
  assert.ok(text.indexOf("DEMO-1042") < text.indexOf(description));
  assert.ok(text.indexOf(issue.summary) < text.indexOf(description));
  if (issue.status) assert.ok(text.indexOf(issue.status) < text.indexOf(description));
  assert.equal(h.render().has("description-more"), false);
  assert.equal(text.includes("Show more"), false);
  h.view.model.accept({ ...issue, description: `${description}\nRefreshed context.` });
  assert.ok(readerText(h).includes(`${description}\nRefreshed context.`));
  h.view.model.useSource("t-fictional-other"); h.view.model.merge(["DEMO-1042"]);
  assert.ok(readerText(h).includes(`${description}\nRefreshed context.`));
  h.view.model.useSource(originalSource);
  assert.ok(readerText(h).includes(`${description}\nRefreshed context.`));
});

test("default glance overrides the old expanded-list preference; browsing pauses and arrows keep the list", () => {
  const { view, cx, render, key } = harness();
  assert.equal(render().has("search"), false);
  view.toggleReaderFocus(cx);
  assert.equal(view.model.current.follow, false);
  const list = render().get("issue-list");
  list.events.on_key_down(key("ArrowDown"), cx);
  assert.equal(view.readerFocus, false);
  assert.equal(view.model.current.selected, "DEMO-1038");
  render().get("issue-list").events.on_key_down(key("Enter"), cx);
  assert.equal(render().has("search"), false);
  assert.equal(view.model.current.follow, false);
});

test("opening Issues focuses and selects the retained filter; Clear keeps the list and selection", () => {
  const h = harness(); h.view.model.filter("catalog"); h.view.syncInput();
  const selected = h.view.model.current.selected;
  toggle(h, "reader-focus", true);
  assert.equal(h.view.input.is_focused(), true);
  assert.deepEqual(h.view.input.selection, { start: 0, end: 7 });
  click(h, "clear-filter");
  assert.equal(h.view.input.value(), ""); assert.equal(h.view.model.current.query, "");
  assert.equal(h.view.input.is_focused(), true); assert.equal(h.view.readerFocus, false);
  assert.equal(h.view.model.current.selected, selected); assert.equal(h.view.model.current.follow, false);
  assert.equal(h.render().has("clear-filter"), false);
});

test("Clear restores every result without relying on native programmatic input events", () => {
  for (const query of ["empty-results", "no fictional match"]) {
    const h = harness(), selected = h.view.model.current.selected;
    const all = h.view.model.rows();
    h.view.search(h.cx); h.view.input.edit(query);
    assert.ok(h.view.model.rows().length < all.length);
    h.view.filterPreview = { query, key: selected };
    h.view.lookupError = "Earlier lookup error";
    click(h, "clear-filter");
    assert.equal(h.view.input.value(), ""); assert.equal(h.view.model.current.query, "");
    assert.deepEqual(h.view.model.rows(), all);
    assert.equal(h.view.filterPreview, null); assert.equal(h.view.lookupError, "");
    assert.equal(h.view.model.current.selected, selected); assert.equal(h.view.model.current.follow, false);
    assert.equal(h.view.input.is_focused(), true); assert.equal(h.view.readerFocus, false);
    assert.equal(h.render().has("jira-select-result"), false);
  }
});

test("excluded selections cannot be copied, opened or manually refreshed through any action path", () => {
  for (const query of ["empty-results", "no fictional match"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    const original = h.view.model.current.selected;
    h.view.search(h.cx); h.view.input.edit(query);
    const nodes = h.render();
    assert.ok(nodes.has("jira-select-result"));
    assert.ok(Object.hasOwn(nodes.get("jira-issue-preview").properties, "invisible"));
    for (const id of ["quick-copy-key", "quick-copy-link", "open", "quick-refresh"]) {
      assert.equal(nodes.get(id).properties.disabled[0], true, id);
      nodes.get(id).events.on_click({}, h.cx);
    }
    const revision = h.view.revision;
    for (const command of ["copy-key", "copy-link", "open", "refresh"]) h.view.handleCommand(command, h.cx);
    h.view.handle.focus(); h.dispatch("y"); h.dispatch("y", { shift: true });
    assert.deepEqual(h.host.clipboard, []); assert.deepEqual(h.host.urls, []);
    assert.equal(h.view.revision, revision);
    assert.equal(h.view.optionAvailability()["copy-key"], false);
    assert.equal(h.view.optionAvailability()["copy-link"], false);
    assert.equal(h.view.optionAvailability().refresh, false);
    if (h.view.model.rows().length) {
      h.render().get("jira-issue-options").events.on_item_click("DEMO-1038", h.cx);
      click(h, "quick-copy-key"); click(h, "quick-copy-link"); click(h, "open");
      assert.deepEqual(h.host.clipboard, ["DEMO-1038", "https://jira.example.test/browse/DEMO-1038"]);
      assert.deepEqual(h.host.urls, ["https://jira.example.test/browse/DEMO-1038"]);
    } else {
      toggle(h, "reader-focus", false);
      click(h, "quick-copy-key");
      assert.deepEqual(h.host.clipboard, [original]);
      assert.equal(h.render().has("jira-select-result"), false);
      assert.equal(childText(h.render().get("jira-peek")).includes("No matches"), false);
    }
  }
});

test("new arrivals open one unread issue despite a later known key and preserve Paused and the filter", () => {
  const h = harness(), known = h.view.model.current.selected;
  h.view.search(h.cx); h.view.input.edit("catalog");
  h.view.model.merge(["DEMO-2010"]); h.view.model.merge(["DEMO-2011"]);
  h.view.model.merge([known]);
  assert.equal(h.view.model.current.unseen.size, 2);
  click(h, "unseen");
  assert.equal(h.view.model.current.selected, "DEMO-2011");
  assert.deepEqual([...h.view.model.current.unseen], ["DEMO-2010"]);
  assert.equal(h.view.model.current.follow, false); assert.equal(h.view.input.value(), "catalog");
  assert.equal(h.view.readerFocus, true); assert.equal(h.view.readerHandle.is_focused(), true);
  toggle(h, "reader-focus", true);
  assert.equal(h.view.model.current.query, "catalog"); assert.equal(h.view.input.value(), "catalog");
  click(h, "unseen");
  assert.equal(h.view.model.current.selected, "DEMO-2010");
  assert.equal(h.view.model.current.unseen.size, 0); assert.equal(h.view.model.current.follow, false);
});

test("unread activity stays beside Issues and preserves the current reader and actions", () => {
  const h = harness(), selected = h.view.model.current.selected;
  h.view.readerFocus = true; h.view.model.browse();
  const passage = readerText(h);
  for (const keys of [["DEMO-2010"], ["DEMO-2011", "DEMO-2012"]]) {
    h.view.model.merge(keys);
    const nodes = h.render();
    assert.ok(descendants(nodes.get("jira-navigation")).includes(nodes.get("unseen")));
    assert.equal(h.view.model.current.selected, selected);
    assert.deepEqual(readerText(h), passage);
    click(h, "quick-copy-link");
    assert.equal(h.host.clipboard.at(-1), `https://jira.example.test/browse/${selected}`);
  }
  while (h.view.model.current.unseen.size) click(h, "unseen");
  assert.equal(h.render().has("unseen"), false);
  assert.equal(h.view.model.current.follow, false);
});

test("filter counts remain visible alongside unread activity and survive reading an unrelated issue", () => {
  const h = harness(), m = h.view.model;
  const template = m.details.get(m.current.selected);
  m.reset(m.config); m.useSource("fictional-count-review");
  const matches = ["DEMO-201", "DEMO-202", "DEMO-203", "DEMO-204"];
  const others = Array.from({ length: 8 }, (_, i) => `DEMO-${211 + i}`);
  m.merge([...matches, ...others]);
  for (const key of m.current.keys) m.accept({ ...template, key, summary: matches.includes(key) ? "Navigation review" : "Export review", values: [] });
  h.view.search(h.cx); h.view.input.edit("navigation");
  m.merge(["DEMO-219"]); m.accept({ ...template, key: "DEMO-219", summary: "Export review", values: [] });
  let nodes = h.render();
  assert.deepEqual(m.rows(), matches);
  assert.deepEqual(childText(nodes.get("jira-filter-count")), ["4 of 13"]);
  assert.ok(descendants(nodes.get("jira-filter-bar")).includes(nodes.get("search")));
  assert.ok(descendants(nodes.get("jira-filter-bar")).includes(nodes.get("jira-filter-count")));
  assert.deepEqual(childText(nodes.get("unseen")), ["+1 new"]);
  click(h, "unseen");
  assert.equal(m.current.selected, "DEMO-219");
  assert.equal(m.current.unseen.size, 0);
  toggle(h, "reader-focus", true);
  nodes = h.render();
  assert.equal(h.view.input.value(), "navigation");
  assert.deepEqual(m.rows(), matches);
  assert.deepEqual(childText(nodes.get("jira-filter-count")), ["4 of 13"]);
  h.view.input.edit("no matching fictional issue");
  assert.deepEqual(childText(h.render().get("jira-filter-count")), ["0 of 13"]);
});

test("navigation has a current accessible name without a stale hover instruction across ten toggles", () => {
  const h = harness();
  for (let i = 0; i < 10; i++) {
    const nodes = h.render(), navigation = nodes.get("reader-focus");
    assert.equal(navigation.properties.accessibility_label[0], h.view.readerFocus
      ? "Show discovered issues and search" : "Return to the selected issue");
    const wrapper = nodes.get("jira-navigation").childNodes[0];
    assert.ok(descendants(wrapper).includes(navigation));
    assert.ok(descendants(wrapper).every(node => !node.properties.tooltip), "neither the toggle nor its wrapper owns a tooltip");
    assert.ok(nodes.get("follow").properties.tooltip, "other controls keep their useful help");
    toggle(h, "reader-focus", h.view.readerFocus);
  }
});

test("last successful fetch is visible beside Refresh and survives failed refreshes", () => {
  const h = harness(), key = h.view.model.current.selected;
  const issue = h.view.model.details.get(key);
  issue.fetchedAt = Date.parse("2026-11-02T06:40:00Z");
  assert.deepEqual(childText(h.render().get("jira-freshness")), [h.view.freshnessLabel(issue)]);
  assert.ok(descendants(h.render().get("jira-reader-title")).some(node => childText(node).includes(h.view.freshnessLabel(issue))));
  h.view.model.failures.add(key);
  assert.deepEqual(childText(h.render().get("jira-freshness")), [h.view.freshnessLabel(issue)]);
  h.view.model.accept({ ...issue, fetchedAt: Date.parse("2026-11-02T06:43:00Z") });
  assert.ok(childText(h.render().get("jira-freshness"))[0].includes("06:43 UTC"));
});

test("pointer preview keeps the issue list and its viewport stable across repeated selections", () => {
  const h = harness(); h.view.toggleReaderFocus(h.cx);
  const scrolls = []; h.view.listScroll.scroll_to_item = (...args) => scrolls.push(args);
  for (const key of ["DEMO-1038", "DEMO-1026", "DEMO-1042"]) {
    h.render().get("jira-issue-options").events.on_item_click(key, h.cx);
    assert.equal(h.view.model.current.selected, key); assert.equal(h.view.readerFocus, false);
    assert.equal(h.view.handle.is_focused(), true); assert.ok(h.render().has("issue-list"));
  }
  assert.deepEqual(scrolls, [], "clicked rows must not jump away from the pointer");
  h.render().get("issue-list").events.on_key_down(h.key("Enter"), h.cx);
  assert.equal(h.view.readerFocus, true); assert.equal(h.view.readerHandle.is_focused(), true);
});

test("the selected issue exposes one-click copy, refresh and Jira actions beside its identity", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  const key = h.view.model.current.selected; let refreshed = 0;
  h.view.refresh = () => refreshed++;
  const nodes = h.render();
  for (const id of ["quick-copy-key", "quick-copy-link", "quick-refresh", "open"]) {
    assert.ok(descendants(nodes.get("jira-reader-title")).includes(nodes.get(id)), id);
    assert.ok(nodes.get(id).properties.min_h[0] >= 32, id);
  }
  click(h, "quick-copy-key"); assert.equal(h.host.clipboard.at(-1), key);
  click(h, "quick-copy-link"); assert.equal(h.host.clipboard.at(-1), `https://jira.example.test/browse/${key}`);
  click(h, "quick-refresh"); assert.equal(refreshed, 1);
  click(h, "open"); assert.equal(h.host.urls.at(-1), `https://jira.example.test/browse/${key}`);
  assert.equal(h.view.moreOpen, false); assert.equal(h.view.model.current.selected, key);
});

test("a slow issue immediately shows its known title without borrowing another issue's description", () => {
  const h = harness(); const key = h.view.model.current.selected;
  const summary = h.view.model.metadata.get(key).summary;
  h.view.model.details.delete(key); h.view.request = { phase: "issue", key };
  const nodes = h.render();
  assert.deepEqual(childText(nodes.get("jira-issue-summary")), [summary]);
  assert.ok(descendants(nodes.get("jira-reader-title")).includes(nodes.get("jira-issue-summary")));
  assert.equal(readerText(h).includes(summary), false);
  assert.equal(nodes.get("quick-refresh").properties.disabled[0], true);
  assert.ok(readerText(h).includes("Loading issue…"));
  assert.equal(readerText(h).join("\n").includes("Returning from a product should restore catalog filters and the reading position."), false);
});

test("known loading titles keep their final slot, respect layouts and leave link copying available", () => {
  for (const height of [405, 735]) for (const summary of ["Catalog exports", "Keep catalog filters when returning from a saved item"]) {
    const h = harness(), key = h.view.model.current.selected;
    h.view.height = height; h.view.demo = false;
    const issue = h.view.model.details.get(key);
    issue.summary = summary; h.view.model.metadata.get(key).summary = summary;
    h.view.model.details.delete(key); h.view.request = { phase: "issue", key };
    const before = h.render();
    const heading = childText(before.get("jira-reader-title"));
    assert.equal(before.get("quick-copy-link").properties.disabled[0], false);
    click(h, "quick-copy-link");
    assert.equal(h.host.clipboard.at(-1), `https://jira.example.test/browse/${key}`);
    h.view.model.details.set(key, issue); h.view.request = null;
    const after = h.render();
    // Freshness is below the action row. Only that label appears after loading.
    assert.deepEqual(childText(after.get("jira-reader-title")).slice(0, heading.length), heading);
    assert.equal(readerText(h).includes(summary), height < 500);
    h.view.model.details.delete(key);
    h.view.fieldLayout = model.defaultFieldLayout(h.view.model.config);
    h.view.fieldLayout.fields.find(field => field.id === "summary").section = "hidden";
    assert.equal(childText(h.render().get("jira-peek")).includes(summary), false);
  }
});

test("unknown headings do not expose a clickable link before its final position is known", () => {
  const h = harness(), key = h.view.model.current.selected;
  h.view.demo = false; h.view.model.details.delete(key); h.view.model.metadata.delete(key);
  for (const showEmpty of [false, true]) {
    h.view.fieldLayout = { ...model.defaultFieldLayout(h.view.model.config), showEmpty };
    assert.equal(h.render().get("quick-copy-link").properties.disabled[0], true);
    h.render().get("quick-copy-link").events.on_click({}, h.cx); assert.deepEqual(h.host.clipboard, []);
  }
  h.view.height = 405;
  assert.equal(h.render().get("quick-copy-link").properties.disabled[0], false, "a scrolling title cannot move the actions");
});

test("readable fields and titles have no hover tooltip; clipped header values and actions retain help", () => {
  const h = harness(); h.view.syncDisclosures(); h.view.detailsOpen = true;
  const nodes = h.render();
  for (const id of ["jira-issue-summary", "reader-field-description", "reader-field-assignee"]) {
    assert.ok(nodes.has(id), id);
    assert.equal(descendants(nodes.get(id)).some(node => node.properties.tooltip), false, id);
  }
  assert.ok(nodes.get("header-field-status").properties.tooltip);
  assert.ok(nodes.get("quick-copy-link").properties.tooltip);
});

test("focused icons show concise labels immediately in the reserved footer and clear on blur", () => {
  const h = harness(false, true); h.view.readerFocus = true;
  const { when: _beforeCondition, ...before } = h.render().get("jira-control-hint").properties;
  const timers = h.host.timers.length;
  for (const [id, label] of [["more", "Options · O"], ["hide", "Hide Jira Peek"],
    ["quick-copy-link", "Copy link · Shift+Y"], ["quick-refresh", "Refresh · R"]]) {
    h.view.actionFocus[id].focus();
    assert.deepEqual(childText(h.render().get("jira-focus-caption")), [label]);
    const { when: _condition, ...layout } = h.render().get("jira-control-hint").properties;
    assert.deepEqual(layout, before);
    h.cx.focus_handle().focus();
    assert.equal(h.render().has("jira-focus-caption"), false);
  }
  assert.equal(h.host.timers.length, timers);
  h.view.search(h.cx); h.view.input.edit("catalog");
  h.view.actionFocus["clear-filter"].focus();
  assert.deepEqual(childText(h.render().get("jira-focus-caption")), ["Clear filter"]);
});

test("icon actions retain names, tooltips and native keyboard focus across panel screens", () => {
  const h = harness();
  for (const id of ["more", "hide", "quick-copy-link", "quick-refresh"]) {
    const node = h.render().get(id);
    assert.deepEqual(childText(node), [], id);
    assert.ok(node.properties.accessibility_label[0], id);
    assert.ok(node.properties.tooltip[0], id);
    assert.equal(node.properties.track_focus[0], h.view.actionFocus[id], id);
    assert.ok(descendants(node).some(child => child.properties.asset), id);
  }
  assert.equal(h.render().has("help"), false);
  assert.deepEqual(childText(h.render().get("open")), ["Open in Jira"]);
  h.view.openOptions(h.cx);
  assert.ok(childText(h.render().get("options-back")).includes("← Issues"));
  assert.deepEqual(h.render().get("help").properties.accessibility_label, ["Help"]);
  h.view.openHelp(h.cx);
  assert.ok(childText(h.render().get("help-back")).includes("← Issues"));
  assert.deepEqual(h.render().get("more").properties.accessibility_label, ["Options"]);
});

test("copy confirmation stays on its action without moving the reader or hiding errors", () => {
  const h = harness(); const key = h.view.model.current.selected;
  click(h, "quick-copy-key");
  assert.deepEqual(childText(h.render().get("quick-copy-key")), [key]);
  assert.ok(descendants(h.render().get("quick-copy-key")).some(node => node.properties.asset === "mods/jira-peek/icons/check.svg"));
  assert.equal(h.render().has("dismiss-note"), false, "successful copies do not add a footer");
  h.view.note = "Fictional operation failed";
  const buttonSize = h.render().get("quick-copy-link").properties.size;
  click(h, "quick-copy-link");
  assert.deepEqual(h.render().get("quick-copy-link").properties.accessibility_label, [`Link to ${key} copied`]);
  assert.ok(descendants(h.render().get("quick-copy-link")).some(node => node.properties.asset === "mods/jira-peek/icons/check.svg"));
  assert.deepEqual(h.render().get("quick-copy-link").properties.size, buttonSize);
  assert.ok(childText(h.render().get("jira-peek")).includes("Fictional operation failed"));
  h.view.select("DEMO-1038", h.cx);
  assert.deepEqual(h.render().get("quick-copy-link").properties.accessibility_label, ["Copy link to DEMO-1038"]);
  assert.ok(descendants(h.render().get("quick-copy-link")).some(node => node.properties.asset === "mods/jira-peek/icons/link.svg"));
  h.cx.write_to_clipboard = () => { throw new Error("Unavailable"); };
  click(h, "quick-copy-key");
  assert.ok(childText(h.render().get("jira-peek")).includes("Could not copy to the clipboard."));
});

test("browsing exposes four complete rows normally and gives short panels room to choose an issue", () => {
  const h = harness(); h.view.toggleReaderFocus(h.cx);
  assert.equal(h.render().get("issue-list").properties.h[0], 228);
  h.view.height = 400;
  assert.equal(h.render().get("issue-list").properties.h[0], 210);
  const nodes = h.render();
  const previewParent = descendants(nodes.get("jira-peek")).find(node => node.childNodes.includes(nodes.get("jira-issue-preview")));
  // The retained reader remains in the tree but is hidden until Enter reads a result.
  assert.deepEqual(previewParent.properties.invisible, []);
  nodes.get("issue-list").events.on_key_down(h.key("enter"), h.cx);
  assert.equal(h.view.readerFocus, true);
  assert.equal(h.view.readerHandle.is_focused(), true);
  assert.equal(h.render().has("issue-list"), false);
});

test("loading and failure feedback stay below the issue actions and preserve the loaded body", () => {
  for (const phase of ["loading", "failed"]) {
    const h = harness(); const key = h.view.model.current.selected;
    h.view.demo = false; h.view.model.pinned = true;
    if (phase === "loading") h.view.request = { phase: "issue", key };
    else h.view.model.failures.add(key);
    const nodes = h.render(), children = nodes.get("jira-issue-preview").childNodes;
    assert.ok(children.indexOf(nodes.get("jira-issue-status")) > children.indexOf(nodes.get("jira-reader-title")));
    assert.ok(readerText(h).join("\n").includes("Returning from a product should restore catalog filters and the reading position."));
    assert.equal(nodes.get("quick-refresh").properties.disabled[0], phase === "loading");
    assert.ok(nodes.has("quick-copy-key")); assert.ok(nodes.has("quick-copy-link"));
  }
});

test("first discovery cannot hide focused search or interrupt its query", () => {
  const { view, cx, render } = harness();
  const config = view.model.config; view.model.reset(config); view.model.useSource("t-empty");
  assert.equal(render().has("search"), true);
  assert.equal(render().has("reader-focus"), false);
  view.input.events.focus({}, cx);
  view.input.edit("filters");
  view.model.merge(["DEMO-2001"]);
  assert.equal(render().has("search"), true);
  assert.equal(view.input.value(), "filters");
  assert.equal(view.model.current.follow, false);
});

test("Enter in a filtered list commits a visible result, not the excluded reading selection", () => {
  const { view, cx, render, key } = harness();
  view.toggleReaderFocus(cx);
  view.input.edit("empty-results");
  assert.deepEqual(view.model.rows(), ["DEMO-1038"]);
  assert.equal(view.model.current.selected, "DEMO-1042");
  render().get("issue-list").events.on_key_down(key("Enter"), cx);
  assert.equal(view.model.current.selected, "DEMO-1038");
  assert.equal(view.readerFocus, true);
});

test("optional disclosures pause Follow, survive refresh, and reset on a different issue", () => {
  const { view, cx, render } = harness();
  const issue = view.model.details.get("DEMO-1042");
  issue.description = "Keep fictional filters and the reading position. ".repeat(20);
  issue.commentsTotal = 3;
  render().get("comments-toggle").events.on_click({}, cx);
  assert.equal(view.commentsOpen, true); assert.equal(view.model.current.follow, false);
  render().get("details-toggle").events.on_click({}, cx);
  view.model.accept({ ...issue, summary: "Refreshed fictional summary" }); render();
  assert.equal(view.commentsOpen, true); assert.equal(view.detailsOpen, true);
  view.select("DEMO-1038", cx); render();
  assert.equal(view.commentsOpen, false); assert.equal(view.detailsOpen, false);
});

function terminalFixture(h, shown = null) {
  h.host.terminals = [{ address: "t-origin" }, { address: "t-replacement" }];
  h.host.panes = [{ pane: "p-origin", terminal: "t-origin", tab: "tab-a" }];
  h.host.focus = { space: "space-a", tab: "tab-a", pane: "p-origin", terminal: "t-origin", shown, agent: null, cwd: null };
  h.view.demo = false; h.view.model.pinned = true;
  h.view.adoptSource(h.cx, false);
}
function panelFocus(h) {
  h.host.focus = { space: "space-a", tab: "tab-a", pane: "p-peek", terminal: null, shown: null, agent: null, cwd: null };
}

test("native focus claims the filter before returning, preserves drafts, and toggles back safely", () => {
  const h = harness(false, true); terminalFixture(h);
  h.view.model.filter("old query"); h.view.syncInput();
  assert.equal(h.view.focus(h.cx), undefined, "focus must never return a Promise");
  assert.equal(h.view.input.is_focused(), true);
  assert.deepEqual(h.view.input.selection, { start: 0, end: 9 });
  assert.equal(h.view.model.current.follow, false);
  assert.deepEqual(h.host.runs, [], "entry needs no deferred host command");
  h.view.focus(h.cx);
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
  h.view.openFields(h.cx);
  const draft = h.view.fieldEditor;
  draft.labels.get("summary").set_value("Unfinished fictional label");
  h.cx.focus_handle().focus(); h.view.focus(h.cx);
  assert.equal(h.view.fieldEditor, draft);
  assert.equal(h.view.actionFocus["fields-back"].is_focused(), true);
});

test("reader identity isolates scroll positions by connection, source, and issue", () => {
  const h = harness();
  const original = [...h.render().keys()].find(id => id.startsWith("reader-0-"));
  assert.ok(original);
  h.view.epoch++;
  assert.equal(h.render().has(original), false);
  const id = `reader-${h.view.epoch}-${h.view.model.source}-${h.view.model.current.selected}`;
  assert.ok(h.render().has(id));
  h.view.select("DEMO-1038", h.cx);
  assert.equal(h.render().has(id), false);
  const selected = h.view.model.current.selected;
  const previous = `reader-${h.view.epoch}-${h.view.model.source}-${selected}`;
  h.view.model.useSource("fictional-secondary"); h.view.model.merge([selected]);
  assert.equal(h.render().has(previous), false);
  assert.ok(h.render().has(`reader-${h.view.epoch}-fictional-secondary-${selected}`));
});

test("Help exposes a focusable reading pane and explains the actual host capability", () => {
  for (const nativeInput of [false, true]) {
    const h = harness(false, nativeInput);
    h.view.openHelp(h.cx);
    const content = h.render().get(`jira-peek-help-content-${h.view.helpTopic}`);
    assert.deepEqual(content.properties.track_focus, [h.view.helpHandle]);
    assert.deepEqual(content.properties.tab_index, [0]);
    h.view.helpHandle.focus();
    assert.equal(h.view.isPeekFocused(), true);
    const help = h.view.helpSections().find(([title]) => title === "Keyboard scrolling")[1];
    assert.equal(help.includes("needs the native input patch"), !nativeInput);
    assert.equal(help.includes("Hiding and reopening keeps your place"), nativeInput);
  }
});

test("browse hands off from the terminal to selected search text and back without resuming Follow", () => {
  const h = harness(); terminalFixture(h);
  h.view.model.filter("catalog"); h.view.syncInput();
  h.view.handleCommand("browse", h.cx);
  assert.equal(h.view.input.is_focused(), true);
  assert.deepEqual(h.view.input.selection, { start: 0, end: 7 });
  assert.equal(h.view.model.current.query, "catalog");
  assert.equal(h.view.model.current.follow, false);
  const selected = h.view.model.current.selected;
  h.view.model.merge(["DEMO-1050"]);
  assert.equal(h.view.model.current.selected, selected);
  panelFocus(h); h.view.handleCommand("browse", h.cx);
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
  assert.equal(h.view.model.current.query, "catalog");
  assert.equal(h.view.model.current.follow, false);
});

test("toolbar browse waits for visibility and is consumed once on the first visible render", () => {
  const h = harness(); terminalFixture(h);
  const panel = h.host.layout.children[0]; panel.hidden = true;
  h.host.shared.set("jira-peek.browse", { id: panel.id, at: h.view.now(), space: "space-a", tab: "tab-a" });
  h.render();
  assert.equal(h.view.input.is_focused(), false);
  assert.ok(h.host.shared.get("jira-peek.browse"));
  panel.hidden = false; h.render();
  assert.equal(h.view.input.is_focused(), true);
  assert.equal(h.host.shared.get("jira-peek.browse"), null);
  h.render();
  assert.deepEqual(h.host.runs, []);
});

test("cold browse accepts typing while connecting and retains it when the source becomes available", () => {
  const h = harness(); terminalFixture(h);
  const config = h.view.model.config;
  h.view.model.reset(); h.view.loading = true;
  // A freshly created native input can receive text before its focus event.
  h.view.input.onFocus = () => {};
  h.view.handleCommand("browse", h.cx);
  assert.ok(h.render().has("search"));
  h.view.input.edit("ABC-8"); h.view.submit(h.cx);
  assert.equal(h.view.input.value(), "ABC-8");
  assert.ok(!h.view.lookupError);
  h.view.model.reset(config); h.view.loading = false; h.view.model.pinned = false;
  h.render();
  assert.equal(h.view.model.current.query, "ABC-8");
  assert.equal(h.view.model.current.follow, false);
  assert.equal(h.view.input.is_focused(), true);
});

test("a delayed focus event cannot select the first characters typed into an empty filter", () => {
  const h = harness(); terminalFixture(h);
  const onFocus = h.view.input.onFocus; h.view.input.onFocus = () => {};
  h.view.handleCommand("browse", h.cx);
  h.view.input.edit("c"); onFocus.call(h.view.input);
  assert.equal(h.view.input.selection, undefined);
  assert.equal(h.view.input.value(), "c");
});

test("toolbar requests also work without a selected space or tab", () => {
  const h = harness();
  h.host.shared.set("jira-peek.browse", { id: "fixture-peek", at: h.view.now(), space: null, tab: null });
  h.render();
  assert.equal(h.view.input.is_focused(), true);
  assert.equal(h.host.shared.get("jira-peek.browse"), null);
});

test("browse without a configured connection focuses setup instead of an absent search field", () => {
  const h = harness(); h.view.model.reset(); h.view.loading = false;
  h.view.handleCommand("browse", h.cx);
  assert.equal(h.view.actionFocus["setup-open"].is_focused(), true);
  assert.equal(h.render().has("search"), false);
});

test("expired or context-changed toolbar requests cannot steal focus", () => {
  for (const change of [
    request => { request.at -= 2000; },
    request => { delete request.at; },
    request => { request.space = "another-space"; },
    request => { request.tab = "another-tab"; },
  ]) {
    const h = harness(); terminalFixture(h);
    const request = { id: "fixture-peek", at: h.view.now(), space: "space-a", tab: "tab-a" };
    change(request); h.host.shared.set("jira-peek.browse", request); h.render();
    assert.equal(h.view.input.is_focused(), false);
    assert.equal(h.host.shared.get("jira-peek.browse"), null);
    assert.deepEqual(h.host.runs, []);
  }
});

test("browse returns to an open Fields draft and closes ordinary Options to search", () => {
  const h = harness(); terminalFixture(h); h.view.openFields(h.cx);
  const draft = h.view.fieldEditor; draft.labels.get("summary").set_value("Unsaved title");
  h.cx.focus_handle().focus(); h.view.handleCommand("browse", h.cx);
  assert.equal(h.view.fieldEditor, draft);
  assert.equal(draft.labels.get("summary").value(), "Unsaved title");
  assert.equal(h.view.actionFocus["fields-back"].is_focused(), true);
  h.view.closeFields(h.cx); h.view.moreOpen = true; h.cx.focus_handle().focus();
  h.view.handleCommand("browse", h.cx);
  assert.equal(h.view.moreOpen, false);
  assert.equal(h.view.input.is_focused(), true);
});

test("Escape collapses all disclosures before returning to the terminal", () => {
  const h = harness(); terminalFixture(h);
  const issue = h.view.model.details.get("DEMO-1042");
  issue.description = "Fictional description remains readable. ".repeat(8).trimEnd();
  issue.metadata = [{ id: "assignee", label: "Owner", value: "Fictional owner" }];
  h.view.handleCommand("peek", h.cx); panelFocus(h);
  h.render().get("comments-toggle").events.on_click({}, h.cx);
  h.render().get("details-toggle").events.on_click({}, h.cx);
  for (const text of [issue.description, issue.comments[0].body, "Fictional owner"]) assert.ok(readerText(h).includes(text));
  h.view.readerHandle.focus();
  assert.equal(h.dispatch("escape"), true);
  assert.ok(readerText(h).includes(issue.description));
  for (const text of [issue.comments[0].body, "Fictional owner"]) assert.equal(readerText(h).includes(text), false);
  assert.deepEqual(h.host.runs, []);
  h.dispatch("escape");
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
});

test("peek enters the reader and returns to the actual terminal with a pinned source", () => {
  const h = harness(); terminalFixture(h);
  h.view.handleCommand("peek", h.cx);
  assert.equal(h.view.readerHandle.is_focused(), true);
  panelFocus(h); h.view.handleCommand("peek", h.cx);
  assert.equal(h.host.runs.length, 1);
  assert.equal(h.host.runs[0].name, "pane.focus");
  assert.ok(h.host.runs[0].args.pane === "p-origin" || h.host.runs[0].args.terminal === "t-origin");
});

test("return stays in Peek if the origin disappeared, changed identity, or changed tab", () => {
  for (const change of [
    h => { h.host.terminals = []; h.host.panes = []; },
    h => { h.host.panes[0].terminal = "t-replacement"; },
    h => { h.host.focus.tab = "tab-b"; },
  ]) {
    const h = harness(); terminalFixture(h); h.view.handleCommand("peek", h.cx); panelFocus(h); change(h);
    h.dispatch("escape"); assert.deepEqual(h.host.runs, []);
  }
});

test("shown replacement returns to the live replacement, never a stale terminal", () => {
  for (const valid of [true, false]) {
    const h = harness(); terminalFixture(h, "t-replacement");
    h.view.handleCommand("peek", h.cx); panelFocus(h);
    if (!valid) h.host.terminals = h.host.terminals.filter(t => t.address !== "t-replacement");
    h.dispatch("escape");
    if (valid) {
      assert.equal(h.host.runs.length, 1);
      assert.equal(h.host.runs[0].name, "pane.focus");
      assert.deepEqual(h.host.runs[0].args, { pane: "p-origin" });
    } else assert.deepEqual(h.host.runs, []);
  }
});

test("empty entry focuses search and Escape returns to the origin", () => {
  const h = harness(); terminalFixture(h);
  h.view.model.reset(h.view.model.config); h.view.model.useSource("t-empty");
  h.view.handleCommand("peek", h.cx); assert.equal(h.view.typing, true);
  panelFocus(h); h.dispatch("escape");
  assert.equal(h.host.runs.length, 1); assert.equal(h.host.runs[0].name, "pane.focus");
});

test("choosing a filtered result needs only one Escape to return", () => {
  const h = harness(); terminalFixture(h); h.view.handleCommand("peek", h.cx); panelFocus(h);
  h.dispatch("/"); h.view.input.edit("empty"); h.view.submit(h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-1038");
  assert.equal(h.view.readerHandle.is_focused(), true); assert.equal(h.render().has("search"), false);
  h.dispatch("escape");
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
  assert.equal(h.view.model.current.query, "empty");
});

test("reader arrows select without showing the list, pause Follow, and leave modifier chords alone", () => {
  const h = harness(); h.view.readerHandle.focus();
  assert.equal(h.dispatch("down"), true);
  assert.equal(h.view.model.current.selected, "DEMO-1038");
  assert.equal(h.view.model.current.follow, false); assert.equal(h.render().has("issue-list"), false);
  assert.equal(h.dispatch("up"), true); assert.equal(h.view.model.current.selected, "DEMO-1042");
  for (const modifier of ["shift", "control", "alt", "platform"]) {
    assert.equal(h.dispatch("down", { [modifier]: true }), false);
    assert.equal(h.view.model.current.selected, "DEMO-1042");
  }
});

test("search and Escape clear browsing in one step; Options closes first", () => {
  const h = harness(); h.view.readerHandle.focus();
  assert.equal(h.dispatch("/"), true); assert.equal(h.view.typing, true);
  assert.equal(h.view.model.current.follow, false); assert.equal(h.render().has("search"), true);
  h.view.input.edit("filter"); h.view.moreOpen = true; h.dispatch("escape");
  assert.equal(h.view.moreOpen, false); assert.equal(h.view.input.value(), "filter");
  h.dispatch("escape"); assert.equal(h.view.input.value(), "");
  assert.equal(h.render().has("search"), false); assert.equal(h.view.readerHandle.is_focused(), true);
  h.dispatch("f", { platform: true }); assert.equal(h.view.typing, true); assert.equal(h.render().has("search"), true);
});

test("typing and button focus do not trigger reader shortcuts", () => {
  const h = harness(); h.view.readerHandle.focus(); h.dispatch("/");
  assert.equal(h.dispatch("y"), false); assert.equal(h.dispatch("/"), false);
  assert.deepEqual(h.host.clipboard, []);
  h.view.actionFocus.open.focus(); assert.equal(h.view.typing, false);
  assert.equal(h.dispatch("enter"), false); assert.deepEqual(h.host.urls, []);
});

test("Enter reads inside Peek even when repeated; Space remains native and Y copies the key", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  h.view.model.details.get("DEMO-1042").description = "Fictional description. ".repeat(30);
  h.view.search(h.cx); h.view.input.edit("1042"); h.view.input.events.submit({}, h.cx);
  assert.equal(h.view.readerHandle.is_focused(), true);
  assert.equal(h.dispatch("enter"), true);
  assert.equal(h.dispatch("enter"), true);
  assert.deepEqual(h.host.urls, []);
  assert.equal(h.view.model.current.selected, "DEMO-1042");
  assert.equal(h.view.model.current.query, "1042");
  assert.equal(h.view.model.current.follow, false);
  assert.equal(h.dispatch("space"), false);
  assert.equal(h.dispatch("y"), true);
  assert.deepEqual(h.host.clipboard, ["DEMO-1042"]);
});

test("explicit browser chords open the viewed issue once per press from reader, list and issue controls", () => {
  for (const target of ["reader", "list", "quick-pin"]) for (const modifiers of [{platform:true}, {control:true}]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    h.view.model.toggleIssuePin("DEMO-1042"); h.view.select("DEMO-1038", h.cx);
    if (target === "list") { h.view.search(h.cx); h.view.handle.focus(); }
    else if (target !== "reader") h.view.actionFocus[target].focus();
    assert.equal(h.dispatch("enter", modifiers), true);
    assert.deepEqual(h.host.urls, ["https://jira.example.test/browse/DEMO-1038"]);
    h.view.keyDown({...h.key("enter", modifiers), is_held:true}, h.cx);
    assert.equal(h.host.urls.length, 1, "held key must not open repeated browser tabs");
    assert.equal(h.view.model.current.pinnedIssueKey, "DEMO-1042");
  }
});

test("browser chords respect editing, auxiliary screens, excluded selections and unrelated modifiers", () => {
  for (const target of ["search", "fields", "options", "help", "setup", "connection", "excluded"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true; h.view.readerHandle.focus();
    if (target === "search") h.view.search(h.cx);
    if (target === "fields") h.view.openFields(h.cx);
    if (target === "options") h.view.openOptions(h.cx);
    if (target === "help") h.view.openHelp(h.cx);
    if (target === "setup") h.view.openSetup(h.cx);
    if (target === "connection") h.view.openConnection(h.cx);
    if (target === "excluded") { h.view.search(h.cx); h.view.input.edit("no-matching-result"); h.view.handle.focus(); }
    h.dispatch("enter", {platform:true}); h.dispatch("enter", {control:true});
    assert.deepEqual(h.host.urls, [], target);
  }
  const h = harness(); h.view.demo = false; h.view.model.pinned = true; h.view.readerHandle.focus();
  for (const modifiers of [{shift:true}, {alt:true}, {platform:true,shift:true}, {control:true,alt:true}, {control:true,platform:true}]) {
    assert.equal(h.dispatch("enter", modifiers), false);
  }
  assert.deepEqual(h.host.urls, []);
  h.view.actionFocus.open.focus();
  assert.equal(h.dispatch("enter"), false, "native focused-button activation remains available");
  click(h, "open"); assert.equal(h.host.urls.length, 1);
});

test("issue action buttons copy the current issue and open Options without taking native activation", () => {
  for (const id of ["quick-copy-key", "quick-copy-link", "quick-refresh", "open", "retry-refresh",
    "comments-toggle", "comments-retry", "details-toggle"]) {
    const h = harness(); h.view.readerFocus = true; h.view.readerHandle.focus();
    h.dispatch("y", { shift: true });
    assert.equal(h.host.clipboard.at(-1), "https://jira.example.test/browse/DEMO-1042");
    h.view.select("DEMO-1038", h.cx); h.render();
    h.view.actionFocus[id].focus();
    assert.equal(h.dispatch("y", { shift: true }), true, id);
    assert.equal(h.host.clipboard.at(-1), "https://jira.example.test/browse/DEMO-1038", id);
    assert.deepEqual(h.render().get("quick-copy-link").properties.accessibility_label, ["Link to DEMO-1038 copied"], id);
    assert.equal(h.dispatch("y"), true, id);
    assert.equal(h.host.clipboard.at(-1), "DEMO-1038", id);
    assert.equal(h.dispatch("enter"), false, id);
    assert.equal(h.dispatch("space"), false, id);
    assert.equal(h.dispatch("down"), false, id);
    assert.deepEqual(h.host.urls, [], id);
    assert.equal(h.dispatch("o"), true, id);
    assert.equal(h.view.moreOpen, true, id);
  }
});

test("Refresh focus copies the newly selected link during and after the request in either direction", () => {
  for (const [previous, selected] of [["DEMO-1042", "DEMO-1038"], ["DEMO-1038", "DEMO-1042"]]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    h.view.readerFocus = true; h.view.select(previous, h.cx);
    click(h, "quick-copy-link");
    assert.equal(h.host.clipboard.at(-1), `https://jira.example.test/browse/${previous}`);
    h.view.select(selected, h.cx);
    h.view.pump = () => { h.view.request = { phase: "issue", key: h.view.forceKey }; };
    // Native Button takes focus before invoking its click callback.
    h.render().get("quick-refresh").properties.track_focus[0].focus();
    click(h, "quick-refresh");
    assert.equal(h.view.request.key, selected);
    for (const pending of [true, false]) {
      if (!pending) { h.view.request = null; h.view.forceKey = null; }
      assert.equal(h.render().get("quick-refresh").properties.disabled[0], pending);
      assert.equal(h.dispatch("y", { shift: true }), true);
      assert.equal(h.host.clipboard.at(-1), `https://jira.example.test/browse/${selected}`);
      assert.deepEqual(h.render().get("quick-copy-link").properties.accessibility_label, [`Link to ${selected} copied`]);
      assert.equal(h.dispatch("enter"), false);
      assert.equal(h.dispatch("space"), false);
    }
  }
});

test("the reading hint hides without changing its layout when focus leaves the reader", () => {
  for (const nativeInput of [false, true]) {
    const h = harness(false, nativeInput); h.view.readerFocus = true; h.view.readerHandle.focus();
    const hint = h.render().get("jira-reader-hint");
    assert.ok(hint);
    assert.equal(hint.properties.invisible, undefined);
    const { when: _condition, ...hintLayout } = hint.properties;
    for (const focus of [h.view.actionFocus["quick-refresh"], h.view.actionFocus["comments-toggle"],
      h.view.actionFocus["details-toggle"], h.cx.focus_handle()]) {
      focus.focus();
      const retained = h.render().get("jira-reader-hint");
      assert.deepEqual(childText(retained), childText(hint));
      const { invisible, when: _condition, ...layout } = retained.properties;
      assert.deepEqual(invisible, []);
      assert.deepEqual(layout, hintLayout);
    }
    h.view.readerHandle.focus();
    assert.equal(h.render().get("jira-reader-hint").properties.invisible, undefined);
  }
});

test("an outside pointer press invalidates the cached reader before the next frame", () => {
  const h = harness(false, true); h.view.readerFocus = true; h.view.readerHandle.focus();
  const readerId = `reader-${h.view.epoch}-${h.view.model.source}-${h.view.model.current.selected}`;
  let frame = h.render(), dirty = false;
  h.cx.notify = () => { dirty = true; };
  const hint = frame.get("jira-reader-hint");
  assert.equal(hint.properties.invisible, undefined);
  const selected = h.view.model.current.selected, timers = h.host.timers.length;
  // Outside-press listeners run in capture, before the terminal takes focus.
  frame.get(readerId).events.on_mouse_down_out?.({}, h.cx);
  h.cx.focus_handle().focus();
  if (dirty) frame = h.render();
  const retained = frame.get("jira-reader-hint");
  assert.deepEqual(retained.properties.invisible, [], "the next frame must hide the stale hint");
  assert.deepEqual(childText(retained), childText(hint), "reserve the same text layout");
  assert.equal(h.cx.stopped, false, "let the terminal receive the pointer press");
  assert.equal(h.host.timers.length, timers, "redraw from the event, not a timer");
  assert.equal(h.view.model.current.selected, selected);
  assert.deepEqual(h.host.runs, []);
  assert.deepEqual(h.host.clipboard, []);
  dirty = false;
  frame.get(readerId).events.on_click({}, h.cx);
  if (dirty) frame = h.render();
  assert.equal(frame.get("jira-reader-hint").properties.invisible, undefined);
});

test("reader and list shortcuts copy links, refresh once per press and return from Options ready to continue", () => {
  for (const target of ["reader", "list"]) {
    const h = harness();
    h.view.readerFocus = target === "reader";
    const focus = target === "reader" ? h.view.readerHandle : h.view.handle;
    focus.focus();
    assert.equal(h.dispatch("y", { shift: true }), true);
    assert.deepEqual(h.host.clipboard, ["https://jira.example.test/browse/DEMO-1042"]);
    let refreshes = 0; h.view.refresh = () => refreshes++;
    assert.equal(h.dispatch("r"), true); assert.equal(refreshes, 1);
    h.view.keyDown({ ...h.key("r"), is_held: true }, h.cx);
    assert.equal(refreshes, 1, "holding R must not keep invalidating requests");
    assert.equal(h.dispatch("o"), true); assert.equal(h.view.moreOpen, true);
    h.dispatch("escape"); assert.equal(focus.is_focused(), true, target);
    h.dispatch("y"); assert.equal(h.host.clipboard.at(-1), "DEMO-1042");
  }
});

test("question mark opens shortcut help and Escape restores reader, list or filter through Options", () => {
  for (const target of ["reader", "list", "filter"]) {
    const h = harness();
    h.view.readerFocus = target === "reader";
    const focus = target === "reader" ? h.view.readerHandle : target === "list" ? h.view.handle : h.view.input;
    focus.focus();
    if (target === "filter") h.view.input.edit("add");
    h.view.openOptions(h.cx);
    assert.equal(h.dispatch("/", { shift: true }), true);
    assert.equal(h.view.helpTopic, "options");
    const text = childText(h.render().get(`jira-peek-help-content-${h.view.helpTopic}`));
    assert.equal(text[0], "Keyboard");
    h.dispatch("escape");
    assert.equal(h.view.moreOpen, false); assert.equal(focus.is_focused(), true, target);
    if (target === "filter") assert.equal(h.view.input.value(), "add");
  }
  const h = harness(); h.view.readerHandle.focus();
  h.view.keyDown({ key: "?", key_char: "?", keystroke: "?" }, h.cx);
  assert.equal(h.view.helpTopic, "peek");
});

test("new shortcuts leave text editing, unrelated controls, forms and host chords alone", () => {
  for (const target of ["input", "button", "setup", "fields"]) {
    const h = harness();
    if (target === "input") h.view.search(h.cx);
    else if (target === "button") h.view.actionFocus.more.focus();
    else if (target === "setup") { h.view.openSetup(h.cx); h.view.setup.base.focus(); }
    else { h.view.openFields(h.cx); h.view.fieldEditor.labels.get("summary").focus(); }
    let refreshes = 0; h.view.refresh = () => refreshes++;
    for (const k of ["r", "o", "y"]) assert.equal(h.dispatch(k), false, target);
    assert.equal(h.dispatch("y", { shift: true }), false, target);
    if (target !== "button") assert.equal(h.dispatch("/", { shift: true }), false, target);
    assert.equal(refreshes, 0); assert.deepEqual(h.host.clipboard, []);
    assert.equal(h.view.helpTopic, null);
  }
  const h = harness(); h.view.readerHandle.focus();
  for (const modifier of ["control", "alt", "platform"]) for (const k of ["r", "o", "y", "/"]) {
    assert.equal(h.dispatch(k, { [modifier]: true }), false);
  }
});

test("Page Up/Down move by visible issue rows without leaving the filter or list", () => {
  for (const target of ["input", "list"]) for (const height of [800, 400]) {
    const h = harness(); h.view.height = height;
    h.view.model.merge(Array.from({ length: 30 }, (_, i) => `DEMO-${2000 + i}`));
    h.view.model.select("DEMO-1042");
    h.view.search(h.cx); h.view.input.edit("DEMO-20");
    const focus = target === "input" ? h.view.input : h.view.handle; focus.focus();
    const send = key => target === "input" ? h.dispatch(key)
      : h.render().get("issue-list").events.on_key_down(h.key(key), h.cx);
    const rows = h.view.model.rows(), step = height === 800 ? 4 : 3;
    const scrolls = []; h.view.listScroll.scroll_to_item = i => scrolls.push(i);
    send("pagedown"); assert.equal(h.view.model.current.selected, rows[0]);
    send("pagedown"); assert.equal(h.view.model.current.selected, rows[step]);
    send("pageup"); assert.equal(h.view.model.current.selected, rows[0]);
    send("pageup"); assert.equal(h.view.model.current.selected, rows[0]);
    assert.equal(focus.is_focused(), true); assert.equal(h.view.input.value(), "DEMO-20");
    assert.equal(h.view.readerFocus, false); assert.deepEqual(scrolls, [0, step, 0, 0]);
  }
});

test("Escape returns immediately after reading a long description", () => {
  const h = harness(); terminalFixture(h);
  const description = "Fictional description. ".repeat(30).trimEnd();
  h.view.model.details.get("DEMO-1042").description = description;
  h.view.handleCommand("peek", h.cx); panelFocus(h);
  assert.ok(readerText(h).includes(description));
  assert.equal(h.dispatch("escape"), true);
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
});

test("setup Escape honors busy cancellation guard", () => {
  const h = harness(); h.view.demo = false; h.view.model.reset(); h.view.openSetup(h.cx); h.view.setup.busy = true;
  h.dispatch("escape"); assert.ok(h.view.setup); h.dispatch("f5"); assert.deepEqual(h.host.runs, []);
  h.view.setup.busy = false; h.dispatch("escape");
  assert.equal(h.view.setup, null); assert.equal(!!h.view.connectionSettings, false);
});

test("keyboard commands protect setup and return from the immediately focused filter", () => {
  const h = harness(); terminalFixture(h); h.view.handleCommand("peek", h.cx); panelFocus(h);
  h.view.toggleReaderFocus(h.cx); assert.equal(h.view.input.is_focused(), true);
  h.view.handleCommand("peek", h.cx); assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
  h.view.openSetup(h.cx); h.host.runs = []; h.view.readerHandle.focus();
  h.view.handleCommand("peek", h.cx); h.view.handleCommand("search", h.cx);
  assert.equal(h.dispatch("enter"), false); assert.equal(h.dispatch("y"), false);
  assert.deepEqual(h.host.runs, []); assert.deepEqual(h.host.urls, []); assert.deepEqual(h.host.clipboard, []);
});

test("full keystrokes protect modified arrows even without modifier fields", () => {
  const h = harness(); h.view.readerHandle.focus();
  h.render().get("jira-peek").events.on_key_down({ key: "down", keystroke: "cmd-down" }, h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-1042"); assert.equal(h.cx.stopped, false);
  h.view.toggleReaderFocus(h.cx);
  h.render().get("issue-list").events.on_key_down({ key: "down", keystroke: "cmd-down" }, h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-1042"); assert.equal(h.cx.stopped, false);
});

test("Tab delegates native traversal in reader, setup and settings without consuming host chords", () => {
  for (const screen of ["reader", "setup", "settings"]) {
    const h = harness(); h.view.readerHandle.focus();
    if (screen === "setup") h.view.openSetup(h.cx);
    if (screen === "settings") h.view.connectionSettings = true;
    assert.equal(h.dispatch("tab"), true, screen);
    assert.equal(h.dispatch("tab", { shift: true }), true, screen);
    assert.deepEqual(h.host.traversal, ["next", "previous"], screen);
    assert.equal(h.dispatch("tab", { control: true }), false, screen);
    assert.equal(h.dispatch("tab", { platform: true, shift: true }), false, screen);
    assert.deepEqual(h.host.traversal, ["next", "previous"], screen);
  }
});

test("Follow and Refresh use configurable commands, never hardcoded F2/F5", () => {
  for (const screen of ["reader", "setup", "settings"]) {
    const h = harness(); h.view.readerHandle.focus();
    if (screen === "setup") h.view.openSetup(h.cx);
    if (screen === "settings") h.view.connectionSettings = true;
    const actions = [];
    h.view.follow = () => actions.push("follow");
    h.view.refresh = () => actions.push("refresh");
    assert.equal(h.dispatch("f2"), false, screen);
    assert.equal(h.dispatch("f5"), false, screen);
    assert.deepEqual(actions, [], screen);
    h.view.handleCommand("follow", h.cx); h.view.handleCommand("refresh", h.cx);
    assert.deepEqual(actions, screen === "reader" ? ["follow", "refresh"] : [], screen);
  }
});

test("settings and loading setup keep focus inside the mounted panel", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true; h.view.moreOpen = true;
  h.view.actionFocus.connection.focus();
  h.render().get("connection").events.on_click({}, h.cx);
  assert.equal(h.view.connectionSettings, true); assert.equal(h.view.moreOpen, false);
  assert.equal(h.view.actionFocus["setup-open"].is_focused(), true);
  h.render().get("setup-open").events.on_click({}, h.cx);
  assert.equal(h.view.setup.loading, true); assert.equal(h.view.connectionSettings, false);
  assert.equal(h.view.rootFocus.is_focused(), true);
  h.view.cancelSetup(h.cx);
  assert.equal(h.view.actionFocus["setup-open"].is_focused(), true);
});

test("modified Escape leaves setup and settings intact for host shortcuts", () => {
  for (const screen of ["setup", "settings"]) {
    const h = harness();
    if (screen === "setup") { h.view.demo = false; h.view.model.reset(); h.view.openSetup(h.cx); }
    else h.view.connectionSettings = true;
    for (const modifier of ["control", "alt", "shift", "platform"]) {
      assert.equal(h.dispatch("escape", { [modifier]: true }), false, modifier);
      assert.ok(h.view.setup || h.view.connectionSettings);
    }
    h.render().get("jira-peek").events.on_key_down({ key: "escape", keystroke: "ctrl-alt-shift-escape" }, h.cx);
    assert.equal(h.cx.stopped, false); assert.ok(h.view.setup || h.view.connectionSettings);
    assert.equal(h.dispatch("escape"), true);
    assert.equal(!!h.view.setup, false);
    assert.equal(!!h.view.connectionSettings, false);
  }
});

test("native control focus takes precedence over the host's retained terminal identity", () => {
  const h = harness(); terminalFixture(h);
  h.view.handleCommand("peek", h.cx);
  // Herdr can retain the same terminal context during programmatic mod focus.
  h.view.handleCommand("peek", h.cx);
  assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { pane: "p-origin" } }]);
});

test("layout terminals return by address without borrowing a model pane", () => {
  for (const modelPane of [false, true]) {
    const h = harness(); terminalFixture(h);
    h.host.focus.pane = null;
    if (!modelPane) h.host.panes = [];
    h.view.adoptSource(h.cx, false);
    h.view.handleCommand("peek", h.cx); panelFocus(h);
    h.dispatch("escape");
    assert.deepEqual(h.host.runs, [{ name: "pane.focus", args: { terminal: "t-origin" } }]);
  }
});

test("input arrows browse visible results while retaining focus and query, and clamp at edges", () => {
  const h = harness(); h.view.handleCommand("search", h.cx);
  h.view.input.edit("add");
  assert.deepEqual(h.view.model.rows(), ["DEMO-1038", "DEMO-1019"]);
  for (const [arrow, expected] of [["down", "DEMO-1038"], ["down", "DEMO-1019"], ["down", "DEMO-1019"], ["up", "DEMO-1038"], ["up", "DEMO-1038"]]) {
    assert.equal(h.dispatch(arrow), true);
    assert.equal(h.view.model.current.selected, expected);
    assert.equal(h.view.input.is_focused(), true);
    assert.equal(h.view.input.value(), "add");
    assert.equal(h.view.readerFocus, false);
    assert.equal(h.view.model.current.follow, false);
    assert.ok(h.render().has(`reader-${h.view.epoch}-${h.view.model.source}-${expected}`));
    assert.ok(h.render().has("issue-list"));
  }
  h.view.input.edit("add keyboard");
  assert.equal(h.view.input.is_focused(), true);
  assert.equal(h.view.input.value(), "add keyboard");
  assert.deepEqual(h.view.model.rows(), ["DEMO-1019"]);
});

test("first arrow with an excluded selection chooses the first visible result in input and list", () => {
  for (const target of ["input", "list"]) for (const arrow of ["up", "down"]) {
    const h = harness(); h.view.handleCommand("search", h.cx); h.view.input.edit("add");
    assert.equal(h.view.model.current.selected, "DEMO-1042");
    if (target === "input") assert.equal(h.dispatch(arrow), true);
    else {
      h.view.handle.focus(); h.cx.stopped = false;
      h.render().get("issue-list").events.on_key_down(h.key(arrow), h.cx);
      assert.equal(h.cx.stopped, true);
    }
    assert.equal(h.view.model.current.selected, "DEMO-1038", `${target} ${arrow}`);
  }
});

test("empty results and modified arrows leave selection and native editing alone", () => {
  const h = harness(); h.view.handleCommand("search", h.cx); h.view.input.edit("no fictional match");
  let pumps = 0; h.view.pump = () => { pumps++; };
  for (const arrow of ["up", "down"]) h.dispatch(arrow);
  assert.equal(h.view.model.current.selected, "DEMO-1042"); assert.equal(pumps, 0);
  assert.equal(h.view.input.is_focused(), true); assert.equal(h.view.input.value(), "no fictional match");
  h.view.input.edit("add");
  for (const modifier of ["shift", "control", "alt", "platform"]) {
    assert.equal(h.dispatch("down", { [modifier]: true }), false);
  }
  for (const chord of ["shift-up", "ctrl-down", "alt-up", "cmd-down"]) {
    h.cx.stopped = false;
    h.render().get("jira-peek").events.on_key_down({ key: chord.endsWith("up") ? "up" : "down", keystroke: chord }, h.cx);
    assert.equal(h.cx.stopped, false, chord);
  }
  for (const key of ["left", "right", "home", "end", "backspace", "delete", "y", "space"]) assert.equal(h.dispatch(key), false, key);
  assert.equal(h.view.model.current.selected, "DEMO-1042"); assert.equal(pumps, 0);
  assert.deepEqual(h.host.urls, []); assert.deepEqual(h.host.clipboard, []);
  assert.equal(h.view.input.is_focused(), true);
});

test("arrows in setup and on buttons do not browse issues", () => {
  for (const target of ["setup", "button"]) {
    const h = harness(); h.view.handleCommand("search", h.cx);
    if (target === "setup") { h.view.openSetup(h.cx); h.view.setup.base.focus(); }
    else h.view.actionFocus.open.focus();
    for (const arrow of ["up", "down"]) assert.equal(h.dispatch(arrow), false, target);
    assert.equal(h.view.model.current.selected, "DEMO-1042");
  }
});

test("input submit commits the selected visible result once, or the first visible result", () => {
  for (const visibleSelection of [true, false]) {
    const h = harness(); h.view.handleCommand("search", h.cx); h.view.input.edit("add");
    if (visibleSelection) h.view.model.select("DEMO-1019");
    let selects = 0; const select = h.view.select.bind(h.view);
    h.view.select = (...args) => { selects++; return select(...args); };
    assert.equal(h.dispatch("enter"), false);
    h.view.input.events.submit({}, h.cx);
    assert.equal(selects, 1);
    assert.equal(h.view.model.current.selected, visibleSelection ? "DEMO-1019" : "DEMO-1038");
    assert.equal(h.view.readerHandle.is_focused(), true); assert.equal(h.render().has("search"), false);
  }
});

test("Enter commits an explicit keyboard preview even when the filter also looks like an issue key", () => {
  for (const key of ["down", "pagedown"]) {
    const h = harness(); h.view.search(h.cx); h.view.input.edit("DEMO-10");
    h.dispatch(key); const selected = h.view.model.current.selected;
    assert.notEqual(selected, "DEMO-10");
    h.view.input.events.submit({}, h.cx);
    assert.equal(h.view.model.current.selected, selected);
    assert.equal(h.view.readerHandle.is_focused(), true);
    assert.equal(h.view.input.value(), "DEMO-10");
    h.view.search(h.cx); h.view.input.edit("DEMO-1026");
    h.view.input.events.submit({}, h.cx);
    assert.equal(h.view.model.current.selected, "DEMO-1026");
  }
});

test("fresh direct key and Jira URL lookups work without previewing a result and reject invalid input", () => {
  for (const [input, expected] of [["demo-1026", "DEMO-1026"], ["https://jira.example.test/browse/DEMO-1026", "DEMO-1026"]]) {
    const h = harness(); h.view.handleCommand("search", h.cx); h.view.input.edit(input);
    h.view.input.events.submit({}, h.cx);
    assert.equal(h.view.model.current.selected, expected); assert.equal(h.view.readerHandle.is_focused(), true);
  }
  for (const input of ["OTHER-123", "DEMO-oops", "https://foreign.example.test/browse/DEMO-1026"]) {
    const h = harness(); h.view.handleCommand("search", h.cx); h.view.input.edit(input);
    h.view.input.events.submit({}, h.cx);
    assert.equal(h.view.model.current.selected, "DEMO-1042"); assert.ok(h.view.lookupError);
    assert.equal(h.view.input.is_focused(), true);
  }
});

test("an undiscovered allowed key offers one-click lookup instead of claiming no matches", () => {
  for (const input of ["demo-2500", "https://jira.example.test/browse/DEMO-2500"]) {
    for (const selected of [true, false]) {
      const h = harness();
      if (!selected) { h.view.model.reset(h.view.model.config); h.view.model.useSource("fictional-empty"); }
      h.view.search(h.cx); h.view.input.edit(input);
      assert.ok(h.render().has("direct-lookup"));
      assert.equal(childText(h.render().get("jira-peek")).includes("No matches"), false);
      assert.equal(childText(h.render().get("jira-peek")).includes("Look up this Jira key"), false);
      click(h, "direct-lookup");
      assert.equal(h.view.model.current.selected, "DEMO-2500");
      assert.equal(h.view.readerFocus, true); assert.equal(h.view.lookupError, "");
    }
  }
  const h = harness(); h.view.search(h.cx); h.view.input.edit("DEMO-10");
  h.dispatch("down");
  assert.notEqual(h.view.model.current.selected, "DEMO-10");
  click(h, "direct-lookup");
  assert.equal(h.view.model.current.selected, "DEMO-10", "the explicit lookup button must honor its label even after a result preview");
});

test("Enter accepts a unique hyphenated title match but never bypasses foreign URL validation", () => {
  const h = harness();
  h.view.model.metadata.get("DEMO-1038").summary = "NAV-S03: Catalog keyboard navigation";
  h.view.search(h.cx); h.view.input.edit("NAV-S03");
  assert.deepEqual(h.view.model.rows(), ["DEMO-1038"]);
  h.view.submit(h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-1038"); assert.equal(h.view.lookupError, "");
  h.view.model.metadata.get("DEMO-1042").summary = "https://foreign.example.test/browse/DEMO-1042";
  h.view.search(h.cx); h.view.input.edit("https://foreign.example.test/browse/DEMO-1042");
  assert.deepEqual(h.view.model.rows(), ["DEMO-1042"]);
  assert.equal(h.render().has("direct-lookup"), false);
  h.view.submit(h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-1038"); assert.ok(h.view.lookupError);
});

test("direct search captures the latest terminal before focus moves and guards its identity", () => {
  for (const tab of ["tab-a", "tab-b"]) for (const state of ["valid", "deleted", "replaced"]) {
    const h = harness(); terminalFixture(h);
    h.host.terminals.push({ address: "t-b" });
    h.host.panes.push({ pane: "p-b", terminal: "t-b", tab });
    h.host.focus = { space: "space-a", tab, pane: "p-b", terminal: "t-b", shown: null, agent: null, cwd: null };
    h.view.handleCommand("search", h.cx); // No render between terminal A and B.
    h.host.focus = { ...h.host.focus, pane: "p-peek", terminal: null };
    h.view.handleCommand("search", h.cx); // Search inside Peek must preserve B.
    h.view.input.edit("add"); h.view.input.events.submit({}, h.cx);
    if (state === "deleted") h.host.terminals = h.host.terminals.filter(t => t.address !== "t-b");
    if (state === "replaced") h.host.panes.find(p => p.pane === "p-b").terminal = "t-replacement";
    h.dispatch("escape");
    assert.deepEqual(h.host.runs, state === "valid" ? [{ name: "pane.focus", args: { pane: "p-b" } }] : [], `${tab} ${state}`);
  }
});

function click(h, id) {
  const node = h.render().get(id);
  assert.ok(node, `${id} is mounted`);
  assert.equal(node.properties.disabled?.[0], false, `${id} is enabled`);
  node.properties.track_focus?.[0]?.focus();
  node.events.on_click({}, h.cx);
}
function toggle(h, id, value) {
  const node = h.render().get(id);
  assert.ok(node, `${id} is mounted`);
  assert.equal(node.properties.disabled?.[0], false, `${id} is enabled`);
  node.properties.track_focus?.[0]?.focus();
  node.events.on_change(value, h.cx);
}
function openOptions(h) { click(h, "more"); }
function openHelp(h) {
  // Main-view Help is also a public command; Options and nested forms have a named entry.
  if (h.render().has("help")) click(h, "help");
  else h.view.handleCommand("help", h.cx);
}
function focusedControl(h) {
  return [...h.render()].find(([, node]) => node.properties.track_focus?.[0]?.is_focused())?.[0];
}

test("Options covers the retained reader and preserves search, selection, description and disclosures on close", () => {
  for (const close of ["back", "escape"]) {
    const h = harness();
    const description = "Fictional description that should remain available.";
    h.view.model.details.get("DEMO-1042").description = description;
    click(h, "comments-toggle"); click(h, "details-toggle");
    h.view.handleCommand("search", h.cx); h.view.input.edit("filter");
    const selected = h.view.model.current.selected, mode = h.view.readerFocus;
    openOptions(h);
    const rendered = h.render();
    for (const id of ["refresh", "copy-key", "copy-link", "pin", "scan", "history", "live-refresh", "connection", "clear-cache"]) assert.ok(rendered.has(id), id);
    assert.ok(rendered.has(`reader-${h.view.epoch}-${h.view.model.source}-${selected}`), "keep the native reader mounted so its scroll state survives");
    assert.ok(Object.hasOwn(rendered.get("jira-peek-body").properties, "invisible"), "reader must not paint or participate in focus traversal beneath Options");
    assert.equal(Object.hasOwn(rendered.get("jira-peek-body").properties, "hidden"), false, "collapsing the viewport resets native scroll state");
    assert.equal(childText(rendered.get("jira-peek")).includes("Show more"), false);
    assert.deepEqual(childText(rendered.get("options-back")), ["← Issues"]);
    assert.equal(rendered.has("hide"), false, "Options must not offer an ambiguous panel-wide close button");
    if (close === "back") click(h, "options-back"); else assert.equal(h.dispatch("escape"), true);
    assert.equal(h.view.input.value(), "filter"); assert.equal(h.view.model.current.selected, selected);
    assert.equal(h.view.readerFocus, mode); assert.equal(h.view.commentsOpen, true); assert.equal(h.view.detailsOpen, true);
    assert.ok(readerText(h).includes(description));
    assert.equal(Object.hasOwn(h.render().get("jira-peek-body").properties, "invisible"), false);
    assert.equal(h.view.input.is_focused(), true);
  }
});

test("Connection Back and Escape return one level and preserve the reader state", () => {
  for (const back of ["button", "escape"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    h.view.handleCommand("search", h.cx); h.view.input.edit("filter");
    const selected = h.view.model.current.selected;
    openOptions(h); click(h, "connection");
    assert.equal(h.render().has("jira-peek-options"), false);
    assert.ok(Object.hasOwn(h.render().get("jira-peek-body").properties, "invisible"));
    if (back === "button") click(h, "settings-back"); else assert.equal(h.dispatch("escape"), true);
    assert.ok(h.render().has("jira-peek-options"));
    assert.equal(focusedControl(h), "connection");
    assert.equal(h.view.input.value(), "filter"); assert.equal(h.view.model.current.selected, selected);
    assert.equal(h.dispatch("escape"), true); assert.equal(h.view.input.is_focused(), true);
  }
});

test("disconnected Connection exposes one setup focus target after a failed reconnect", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  openOptions(h); click(h, "connection");
  h.view.model.reset(); h.view.loading = false; h.view.error = "connection_failed";
  const rendered = h.render();
  const setupTargets = descendants(rendered.get("jira-peek"))
    .filter(node => node.properties.track_focus?.[0] === h.view.actionFocus["setup-open"]);
  assert.equal(setupTargets.length, 1, "the hidden entry must not duplicate Connection's setup action");
  assert.ok(descendants(rendered.get("jira-peek-surface")).includes(setupTargets[0]));
  assert.deepEqual(childText(rendered.get("jira-peek-body")), []);
  click(h, "settings-back");
  assert.ok(childText(h.render().get("jira-peek-body")).includes("Connect Jira") ||
    childText(h.render().get("jira-peek-body")).includes("Connection needs attention"));
  assert.equal(focusedControl(h), "setup-open");
});

test("setup Cancel and Escape return to Connection, whose Back returns to Options", () => {
  for (const cancel of ["button", "escape"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    openOptions(h); click(h, "connection"); click(h, "setup-open");
    if (cancel === "button") click(h, "setup-back"); else assert.equal(h.dispatch("escape"), true);
    assert.ok(h.render().has("settings-back")); assert.equal(focusedControl(h), "setup-open");
    click(h, "settings-back"); assert.ok(h.render().has("jira-peek-options"));
    assert.equal(focusedControl(h), "connection");
  }
});

test("direct setup Cancel and Escape return to Connect Jira", () => {
  for (const cancel of ["button", "escape"]) {
    const h = harness(); h.view.demo = false; h.view.model.reset(); h.view.loading = false;
    click(h, "setup-open");
    if (cancel === "button") click(h, "setup-back"); else assert.equal(h.dispatch("escape"), true);
    const nodes = h.render();
    assert.ok(childText(nodes.get("jira-peek")).includes("Connect Jira"));
    assert.equal(nodes.has("settings-back"), false); assert.equal(focusedControl(h), "setup-open");
  }
});

test("canceling the Connection folder picker keeps its screen and focuses its row", async () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  let resolve; h.host.folder = new Promise(r => { resolve = r; });
  h.cx.spawn = fn => { fn(h.cx); return { cancel() {} }; };
  openOptions(h); click(h, "connection"); click(h, "settings-choose");
  resolve(null); await new Promise(r => setImmediate(r));
  assert.ok(h.render().has("settings-choose")); assert.equal(focusedControl(h), "settings-choose");
  click(h, "settings-back"); assert.ok(h.render().has("jira-peek-options"));
});

test("Options toggles stay open and actions dismiss before running with visible focus", async () => {
  for (const id of ["pin", "live-refresh"]) {
    const h = harness(); await nativeFields(h); h.view.model.pinned = true;
    openOptions(h); const before = h.render().get(id).properties.pressed[0];
    toggle(h, id, !before);
    await nextTurn();
    assert.ok(h.render().has("jira-peek-options"));
    assert.equal(h.render().get(id).properties.pressed[0], !before);
  }
  for (const [id, method] of [["refresh", "refresh"], ["scan", "scan"], ["history", "history"], ["clear-cache", "clearCache"], ["copy-key", "copy"], ["copy-link", "copy"]]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    let called = 0; h.view[method] = () => { called++; assert.equal(h.view.moreOpen, false, id); };
    openOptions(h); click(h, id); assert.equal(called, 1, id);
    const rendered = h.render(); assert.equal(rendered.has("jira-peek-options"), false, id);
    assert.ok(focusedControl(h) || h.view.readerHandle.is_focused() || h.view.input.is_focused(), `${id} must focus a visible destination`);
    if (focusedControl(h)) assert.notEqual(rendered.get(focusedControl(h)).properties.disabled?.[0], true, id);
  }
});

test("agents and Options share reader preferences without changing field layouts or other connections", async () => {
  const h = harness(true); h.view.pump = () => {}; await nativeFields(h);
  const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
  const fields = structuredClone(file.connections);
  file.preferences = { autoRefresh: true, highlightSource: false };
  h.host.files.set(path, JSON.stringify(file)); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.live, true); assert.equal(h.view.highlightSource, false);
  h.view.toggleLive(h.cx); await nextTurn();
  let written = JSON.parse(h.host.files.get(path));
  assert.equal(written.preferences.autoRefresh, false);
  assert.equal(written.preferences.highlightSource, false);
  assert.deepEqual(written.connections, fields);
  h.view.toggleHighlight(h.cx); await nextTurn();
  written = JSON.parse(h.host.files.get(path));
  assert.equal(written.preferences.highlightSource, true);
  assert.equal(h.host.storage.has("preferences"), false);
  h.view.openFields(h.cx); h.view.fieldEditor.labels.get("summary").set_value("Task");
  h.view.applyFields(h.cx); await nextTurn();
  assert.deepEqual(JSON.parse(h.host.files.get(path)).preferences, written.preferences);
});

test("older field files migrate UI preferences without changing their layouts", async () => {
  const h = harness(); h.view.pump = () => {};
  h.view.legacyPreferences = { live: true, highlightSource: false };
  const file = { version: 1, connections: [{ configDir: "/fictional/connection-one", base: h.view.model.config.base, fields: [] }] };
  h.host.files.set(h.view.fieldFilePath(), JSON.stringify(file));
  await nativeFields(h);
  const saved = JSON.parse(h.host.files.get(h.view.fieldFilePath()));
  assert.deepEqual(saved.preferences, { autoRefresh: true, highlightSource: false });
  assert.deepEqual(saved.connections[0].fields, []);
  assert.equal(h.view.live, true); assert.equal(h.view.highlightSource, false);
});

test("preference saves cannot overwrite a newer field edit and failed writes restore saved values", async () => {
  for (const conflict of [true, false]) {
    const h = harness(); h.view.pump = () => {}; await nativeFields(h);
    const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
    if (conflict) {
      file.connections[0].fields[0].label = "Agent edit retained";
      h.host.beforeWrite = () => h.host.files.set(path, JSON.stringify(file));
    } else h.host.fileWriteThrows = true;
    h.view.toggleLive(h.cx); await nextTurn();
    assert.equal(h.view.live, false);
    assert.equal(h.view.preferencesSaving, false);
    assert.match(h.view.preferenceError, /not saved/);
    assert.deepEqual(JSON.parse(h.host.files.get(path)), file);
  }
});

test("invalid reader preferences keep the last working settings and repair reloads them", async () => {
  const h = harness(); await nativeFields(h);
  const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
  file.preferences.autoRefresh = "yes";
  h.host.files.set(path, JSON.stringify(file)); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.live, false); assert.ok(h.view.fieldFileError);
  assert.equal(h.view.optionAvailability()["live-refresh"], false);
  file.preferences.autoRefresh = true;
  h.host.files.set(path, JSON.stringify(file)); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.live, true); assert.equal(h.view.fieldFileError, "");
});

test("idle refresh stays paused when its preference cannot be saved", async () => {
  const h = harness(); await nativeFields(h);
  let now = 1_000_000; h.view.now = () => now;
  const path = h.view.fieldFilePath(), file = JSON.parse(h.host.files.get(path));
  file.preferences.autoRefresh = true;
  const valid = JSON.stringify(file);
  h.host.files.set(path, valid); await h.view.loadFieldLayout(h.cx);
  const timer = h.host.timers.findLast(timer => timer.ms === 60000);
  h.host.files.set(path, "{"); await h.view.loadFieldLayout(h.cx);
  now += 5 * 60000; timer.fire();
  assert.equal(h.view.live, false); assert.ok(h.view.preferenceError);
  h.host.files.set(path, valid); await h.view.loadFieldLayout(h.cx);
  assert.equal(h.view.live, false, "repairing an unrelated file error must not undo the idle pause");
  h.view.toggleLive(h.cx); await nextTurn();
  assert.equal(h.view.live, true);
});

test("agent commands set Follow and source pinning idempotently and preserve an open field draft", () => {
  const h = harness(); h.view.scan = () => {}; h.view.pump = () => {};
  for (let i = 0; i < 2; i++) h.view.handleCommand("pause", h.cx);
  assert.equal(h.view.model.current.follow, false);
  for (let i = 0; i < 2; i++) h.view.handleCommand("resume", h.cx);
  assert.equal(h.view.model.current.follow, true);
  for (let i = 0; i < 2; i++) h.view.handleCommand("pin", h.cx);
  assert.equal(h.view.model.pinned, true);
  h.view.handleCommand("unpin", h.cx); assert.equal(h.view.model.pinned, false);
  h.view.handleCommand("fields", h.cx);
  h.view.fieldEditor.labels.get("summary").set_value("Keep this draft");
  let called = 0; h.view.connect = () => called++; h.view.clearCache = () => called++; h.view.history = () => called++;
  for (const command of ["reconnect", "clear-cache", "history", "resume", "connection"]) h.view.handleCommand(command, h.cx);
  assert.equal(called, 0); assert.equal(h.view.fieldEditor.labels.get("summary").value(), "Keep this draft");
  h.view.handleCommand("help", h.cx); assert.equal(h.view.helpTopic, "fields");
  h.view.handleCommand("back", h.cx); assert.equal(h.view.helpTopic, null); assert.ok(h.view.fieldEditor);
  h.view.handleCommand("back", h.cx); assert.equal(h.view.fieldEditor, null);
});

test("agent commands route existing actions without submitting terminal input", () => {
  for (const [command, method] of [["history", "history"], ["reconnect", "connect"], ["clear-cache", "clearCache"], ["open", "openIssue"], ["hide", "hide"]]) {
    const h = harness(); let called = 0; h.view[method] = () => called++;
    h.view.handleCommand(command, h.cx); assert.equal(called, 1, command);
    assert.deepEqual(h.host.runs, []);
  }
  const h = harness();
  h.view.handleCommand("issues", h.cx); assert.equal(h.view.readerFocus, false);
  h.view.handleCommand("reader", h.cx); assert.equal(h.view.readerFocus, true);
  h.view.handleCommand("copy-key", h.cx); assert.equal(h.host.clipboard.at(-1), h.view.model.current.selected);
  h.view.handleCommand("copy-link", h.cx); assert.match(h.host.clipboard.at(-1), /^https:\/\/jira\.example\.test\/browse\//);
});

test("Options arrows skip disabled rows and modified keys and global commands do not leak", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  h.view.scanning = {}; h.view.historyRead = {}; // Both terminal actions are disabled.
  openOptions(h);
  h.view.actionFocus["copy-link"].focus();
  assert.equal(h.dispatch("down"), true);
  assert.equal(focusedControl(h), "pin");
  assert.equal(h.dispatch("down"), true);
  assert.equal(focusedControl(h), "live-refresh", "disabled Scan and History are skipped");
  const selection = h.view.model.current.selected;
  for (const mod of ["shift", "control", "alt", "platform"]) {
    assert.equal(h.dispatch("up", { [mod]: true }), false);
    assert.equal(h.dispatch("escape", { [mod]: true }), false);
  }
  assert.equal(focusedControl(h), "live-refresh"); assert.equal(h.view.model.current.selected, selection);
  assert.equal(h.dispatch("tab"), true); assert.equal(h.dispatch("tab", { shift: true }), true);
  assert.deepEqual(h.host.traversal, ["next", "previous"]);
  let calls = 0; h.view.refresh = () => calls++; h.view.follow = () => calls++; h.view.scan = () => calls++;
  for (const command of ["refresh", "follow", "scan", "search", "peek"]) h.view.handleCommand(command, h.cx);
  assert.equal(calls, 0); assert.ok(h.render().has("jira-peek-options"));
  assert.equal(h.view.model.current.selected, selection);
});

const nextTick = () => new Promise(resolve => setImmediate(resolve));

test("connection invalidation retires Options keyboard mode and restores visible focus", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  openOptions(h); h.view.actionFocus["live-refresh"].focus();
  h.view.invalidate(h.cx);
  const nodes = h.render();
  assert.equal(nodes.has("jira-peek-options"), false);
  assert.equal(h.view.moreOpen, false);
  assert.equal(focusedControl(h), "setup-open");
  assert.equal(nodes.get("setup-open").properties.disabled[0], false);
  assert.equal(h.dispatch("down"), false);
  assert.equal(focusedControl(h), "setup-open");
});

test("connection invalidation preserves active Connection and setup navigation", () => {
  for (const screen of ["connection", "setup"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    openOptions(h); click(h, "connection");
    if (screen === "setup") click(h, "setup-open");
    h.view.invalidate(h.cx);
    if (screen === "setup") {
      assert.ok(h.view.setup); click(h, "setup-back");
    }
    assert.ok(h.render().has("settings-back"), screen);
    click(h, "settings-back");
    assert.equal(focusedControl(h), "setup-open", screen);
    assert.equal(h.view.moreOpen, false);
  }
});

function deferredResult() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function connectionFixture() {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  h.view.configDir = "/fictional/config";
  h.cx.spawn = fn => { fn(h.cx); return { cancel() {} }; };
  openOptions(h); click(h, "connection");
  return h;
}

test("Options arrow navigation reaches enabled Copy link from both neighbors", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  openOptions(h);
  assert.equal(h.render().get("copy-link").properties.disabled[0], false);
  for (const [start, key] of [["copy-key", "down"], ["pin", "up"]]) {
    h.render().get(start).properties.track_focus[0].focus();
    assert.equal(h.dispatch(key), true);
    assert.equal(focusedControl(h), "copy-link", `${start} ${key}`);
  }
});

test("opening Options in demo and empty states focuses an enabled mounted control", () => {
  for (const state of ["demo", "empty"]) {
    const h = harness();
    if (state === "empty") { h.view.demo = false; h.view.model.reset(h.view.model.config); }
    openOptions(h);
    const nodes = h.render();
    assert.equal(nodes.get("refresh").properties.disabled[0], true, state);
    const focused = focusedControl(h);
    assert.ok(focused, state); assert.notEqual(focused, "refresh", state);
    assert.notEqual(nodes.get(focused).properties.disabled?.[0], true, state);
  }
});

test("setup cancellation retains Connection as parent during and after failed reconnect", async () => {
  for (const phase of ["loading", "failed"]) {
    const h = connectionFixture(), result = deferredResult();
    h.view.bridge = () => result.promise;
    click(h, "settings-reconnect");
    if (phase === "failed") { result.resolve({ ok: false, error: "configuration_missing" }); await nextTick(); }
    click(h, "setup-open"); click(h, "setup-back");
    assert.ok(h.render().has("settings-back"), phase);
    assert.equal(focusedControl(h), "setup-open", phase);
    if (phase === "loading") { result.resolve({ ok: false, error: "configuration_missing" }); await nextTick(); }
    assert.ok(h.render().has("settings-back"), `${phase} after late result`);
  }
});

test("reconnect exposes enabled Back while pending, reports failure, and can retry", async () => {
  const h = connectionFixture(), first = deferredResult(), second = deferredResult();
  const pending = [first, second]; let requests = 0;
  h.view.bridge = () => pending[requests++].promise;
  click(h, "settings-reconnect");
  let nodes = h.render();
  assert.equal(focusedControl(h), "settings-back");
  assert.equal(nodes.get("settings-back").properties.disabled[0], false);
  assert.equal(nodes.get("settings-reconnect").properties.disabled[0], true);
  assert.ok(childText(nodes.get("settings-reconnect")).includes("Connecting…"));
  first.resolve({ ok: false, error: "configuration_missing" }); await nextTick();
  nodes = h.render();
  assert.match(childText(nodes.get("jira-peek")).join(" "), /Could not reconnect/i);
  assert.equal(nodes.get("settings-reconnect").properties.disabled[0], false);
  click(h, "settings-reconnect"); assert.equal(requests, 2);
  assert.equal(focusedControl(h), "settings-back");
  second.resolve({ ok: false, error: "configuration_missing" }); await nextTick();
  assert.ok(h.render().has("settings-reconnect"));
});

test("a late folder result after Back is ignored and picker errors remain visible in Connection", async () => {
  {
    const h = connectionFixture(), result = deferredResult(); h.host.folder = result.promise;
    let connections = 0; h.view.connect = () => { connections++; };
    click(h, "settings-choose"); click(h, "settings-back");
    result.resolve("/fictional/late-folder"); await nextTick();
    assert.equal(connections, 0); assert.ok(h.render().has("jira-peek-options"));
    assert.equal(focusedControl(h), "connection");
  }
  {
    const h = connectionFixture(), result = deferredResult(); h.host.folder = result.promise;
    click(h, "settings-choose"); result.reject(new Error("fictional picker error")); await nextTick();
    const nodes = h.render();
    assert.ok(nodes.has("settings-choose")); assert.equal(focusedControl(h), "settings-choose");
    assert.match(childText(nodes.get("jira-peek")).join(" "), /could not open the folder picker/i);
  }
});

test("disabled Options controls cannot dismiss the menu or perform their actions", () => {
  const h = harness(); // Demo makes these actions unavailable.
  let actions = 0;
  for (const method of ["refresh", "scan", "history", "clearCache"]) h.view[method] = () => actions++;
  openOptions(h);
  for (const id of ["refresh", "scan", "history", "clear-cache", "connection"]) {
    const node = h.render().get(id);
    assert.equal(node.properties.disabled[0], true, id);
    node.events.on_click({}, h.cx);
    assert.ok(h.render().has("jira-peek-options"), id);
  }
  const live = h.view.live, toggleNode = h.render().get("live-refresh");
  assert.equal(toggleNode.properties.disabled[0], true);
  toggleNode.events.on_change(!live, h.cx);
  assert.equal(h.view.live, live); assert.ok(h.render().has("jira-peek-options"));
  assert.equal(actions, 0); assert.equal(!!h.view.connectionSettings, false);
});

test("Help covers the retained reader and Back restores its state and filter focus", () => {
  const h = harness();
  const description = "Fictional issue description remains complete.";
  h.view.model.details.get("DEMO-1042").description = description;
  click(h, "comments-toggle"); click(h, "details-toggle");
  h.view.handleCommand("search", h.cx); h.view.input.edit("filter");
  const selected = h.view.model.current.selected, source = h.view.model.source, mode = h.view.readerFocus;
  openHelp(h);
  let nodes = h.render();
  assert.equal(h.view.helpTopic, "peek");
  assert.ok(nodes.has("jira-peek-help"));
  assert.ok(nodes.has(`reader-${h.view.epoch}-${source}-${selected}`));
  assert.ok(Object.hasOwn(nodes.get("jira-peek-body").properties, "invisible"));
  assert.equal(Object.hasOwn(nodes.get("jira-peek-body").properties, "hidden"), false);
  assert.equal(nodes.get("more").properties.disabled[0], false, "Help has a direct route to Options");
  assert.equal(nodes.has("hide"), false);
  click(h, "help-back");
  nodes = h.render();
  assert.equal(h.view.helpTopic, null); assert.equal(nodes.has("jira-peek-help"), false);
  assert.equal(h.view.input.is_focused(), true);
  assert.equal(h.view.input.value(), "filter"); assert.equal(h.view.model.current.selected, selected);
  assert.equal(h.view.readerFocus, mode); assert.equal(h.view.commentsOpen, true); assert.equal(h.view.detailsOpen, true);
  assert.ok(readerText(h).includes(description));
});

test("Help returns to Issues from Options and preserves nested forms on Escape", () => {
  for (const parent of ["options", "connection", "disconnected", "setup", "empty"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    if (parent === "disconnected") h.view.model.reset();
    else if (parent === "empty") h.view.model.reset(h.view.model.config);
    else {
      openOptions(h);
      if (parent !== "options") click(h, "connection");
      if (parent === "setup") click(h, "setup-open");
    }
    const form = h.view.setup, settings = h.view.connectionSettings, more = h.view.moreOpen;
    openHelp(h);
    assert.equal(h.view.helpTopic, parent === "disconnected" ? "connection" : parent === "empty" ? "peek" : parent, parent);
    assert.ok(h.render().has("jira-peek-help"), parent);
    const back = {options: "← Issues", connection: "Back to Connection", disconnected: "← Jira Peek", setup: "Back to setup", empty: "← Issues"}[parent];
    assert.deepEqual(childText(h.render().get("help-back")), [back]);
    assert.equal(h.render().has("hide"), false, parent);
    assert.equal(h.dispatch("escape"), true, parent);
    assert.equal(h.view.helpTopic, null, parent);
    assert.equal(h.view.setup, form, parent); assert.equal(h.view.connectionSettings, settings, parent);
    assert.equal(h.view.moreOpen, parent === "options" ? false : more, parent);
    if (parent === "options") assert.equal(h.view.readerHandle.is_focused(), true);
    else if (parent === "empty") assert.equal(h.view.input.is_focused(), true);
    else assert.equal(focusedControl(h), parent === "disconnected" ? "setup-open" : "help", parent);
    if (parent === "options") assert.equal(h.render().has("jira-peek-options"), false);
    if (parent === "connection") assert.ok(h.render().has("settings-back"));
    if (parent === "setup") assert.ok(h.render().has("jira-setup-form"));
  }
});

test("Options and Help navigate directly and return to the same filtered issue view", () => {
  const h = harness();
  h.view.handleCommand("search", h.cx); h.view.input.edit("catalog");
  const selected = h.view.model.current.selected;
  openOptions(h); openHelp(h);
  assert.equal(h.view.moreOpen, false);
  assert.equal(childText(h.render().get("jira-peek")).includes("Back to Options"), false);
  openOptions(h);
  assert.equal(h.view.helpTopic, null); assert.equal(h.view.moreOpen, true);
  assert.ok(focusedControl(h));
  openHelp(h); click(h, "help-back");
  const nodes = h.render();
  assert.equal(nodes.has("jira-peek-options"), false);
  assert.equal(nodes.has("jira-peek-help"), false);
  assert.equal(h.view.input.value(), "catalog");
  assert.equal(h.view.model.current.selected, selected);
  assert.equal(h.view.readerFocus, false);
  assert.equal(h.view.model.current.follow, false);
  assert.equal(nodes.has("hide"), true, "panel close belongs only to the main view");
  assert.deepEqual(h.host.runs, []); assert.deepEqual(h.host.closedOverlays, []);
});

test("Options offers named Help after its issue settings and includes it in arrow navigation", () => {
  const h = harness();
  openOptions(h);
  assert.deepEqual(childText(h.render().get("help")), ["Help", "?"]);
  h.view.actionFocus.fields.focus();
  h.dispatch("down");
  assert.equal(h.view.actionFocus.help.is_focused(), true, "disabled demo settings are skipped");
  click(h, "help");
  assert.equal(h.view.helpTopic, "options");
  click(h, "help-back");
  assert.equal(h.view.readerHandle.is_focused(), true);
});

test("Help explains every Options row under its exact visible label from either entry point", () => {
  for (const from of ["issues", "options"]) {
    const h = harness();
    openOptions(h);
    const nodes = h.render();
    const labels = Object.keys(h.view.optionAvailability()).filter(id => id !== "help").map(id => childText(nodes.get(id))[0]);
    assert.equal(labels.length, 11);
    if (from === "issues") click(h, "options-back");
    openHelp(h);
    const content = h.render().get(`jira-peek-help-content-${h.view.helpTopic}`);
    const headings = content.childNodes.map(group => childText(group)[0]);
    let previous = -1;
    for (const label of labels) {
      const position = headings.indexOf(label);
      assert.ok(position > previous, `${from}: ${label} has its own explanation in Options order`);
      previous = position;
    }
    assert.ok(Object.hasOwn(content.properties, "overflow_y_scrollbar"));
    assert.equal(childText(content).some(text => text.includes("separate from pinning an issue")), false);
    toggle(h, "help-section-keep-this-terminal", true);
    assert.ok(childText(h.render().get(`jira-peek-help-content-${h.view.helpTopic}`)).some(text => text.includes("separate from pinning an issue")));
  }
});

test("Help opens collapsed, reveals only the chosen explanation and can close it again", () => {
  const h = harness(); openHelp(h);
  const bodies = () => [...h.render().keys()].filter(id => id.startsWith("help-section-") && id.endsWith("-body"));
  assert.deepEqual(bodies(), []);
  toggle(h, "help-section-keyboard", true);
  assert.deepEqual(bodies(), ["help-section-keyboard-body"]);
  assert.equal(h.view.actionFocus["help-section-keyboard"].is_focused(), true);
  assert.equal(h.dispatch("enter"), false, "native toggle owns keyboard activation");
  assert.equal(h.dispatch("space"), false);
  toggle(h, "help-section-refresh", true);
  assert.deepEqual(bodies(), ["help-section-refresh-body"]);
  assert.equal(h.render().get("help-section-keyboard").properties.pressed[0], false);
  assert.equal(h.render().get("help-section-refresh").properties.accessibility_label[0], "Hide Refresh help");
  toggle(h, "help-section-refresh", false);
  assert.deepEqual(bodies(), []);
  toggle(h, "help-section-copy-link", true);
  click(h, "help-back"); openHelp(h);
  assert.deepEqual(bodies(), [], "each visit starts with the compact topic list");
});

test("nested Help uses the same collapsed topics and preserves its form draft", () => {
  const h = harness(); h.view.openFields(h.cx);
  h.view.fieldEditor.labels.get("summary").set_value("Fictional draft label");
  const editor = h.view.fieldEditor; openHelp(h);
  assert.equal(h.render().has("help-section-place-fields-body"), false);
  toggle(h, "help-section-place-fields", true);
  assert.ok(h.render().has("help-section-place-fields-body"));
  h.dispatch("escape");
  assert.equal(h.view.fieldEditor, editor);
  assert.equal(editor.labels.get("summary").value(), "Fictional draft label");
});

test("setup Help preserves form values and pending inspection cannot take focus", async () => {
  const h = connectionFixture(), result = deferredResult();
  h.view.setupHelper = () => result.promise;
  click(h, "setup-open");
  const form = h.view.setup;
  form.token.set_value("fictional-token");
  openHelp(h);
  const focusBefore = focusedControl(h);
  result.resolve({ revision: "fictional-revision", settings: { base: "https://example.invalid", email: "person@example.invalid", projects: "FICTION", cloudId: "fictional-cloud" } });
  await nextTick();
  assert.equal(h.view.helpTopic, "setup"); assert.equal(focusedControl(h), focusBefore);
  assert.equal(form.base.is_focused(), false);
  const values = [form.base, form.email, form.token, form.projects, form.cloudId].map(input => input.value());
  assert.equal(form.token.value(), "fictional-token");
  click(h, "help-back");
  assert.equal(h.view.setup, form); assert.equal(form.scoped, true);
  assert.deepEqual([form.base, form.email, form.token, form.projects, form.cloudId].map(input => input.value()), values);
  assert.equal(focusedControl(h), "help");
});

test("Help isolates reader commands while preserving native traversal and modified chords", () => {
  const h = harness(); terminalFixture(h); h.view.handleCommand("peek", h.cx); panelFocus(h);
  const selected = h.view.model.current.selected, follow = h.view.model.current.follow;
  openHelp(h);
  for (const modifier of ["shift", "control", "alt", "platform"]) {
    assert.equal(h.dispatch("escape", { [modifier]: true }), false);
    assert.equal(h.view.helpTopic, "peek");
  }
  assert.equal(h.dispatch("tab"), true); assert.equal(h.dispatch("tab", { shift: true }), true);
  assert.deepEqual(h.host.traversal, ["next", "previous"]);
  for (const key of ["/", "down", "y"]) h.dispatch(key);
  for (const command of ["refresh", "follow", "scan", "search", "peek"]) h.view.handleCommand(command, h.cx);
  assert.equal(h.view.helpTopic, "peek"); assert.equal(h.view.model.current.selected, selected);
  assert.equal(h.view.model.current.follow, follow); assert.equal(h.view.typing, false);
  assert.deepEqual(h.host.runs, []); assert.deepEqual(h.host.clipboard, []); assert.deepEqual(h.host.urls, []);
  assert.equal(h.dispatch("escape"), true); assert.equal(h.view.readerHandle.is_focused(), true);
});

test("connection invalidation does not steal focus from Help", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  openHelp(h);
  const focusBefore = focusedControl(h);
  h.view.invalidate(h.cx);
  assert.equal(h.view.helpTopic, "peek"); assert.ok(h.render().has("jira-peek-help"));
  assert.equal(focusedControl(h), focusBefore);
  assert.deepEqual(childText(h.render().get("help-back")), ["← Jira Peek"]);
  click(h, "help-back"); assert.equal(focusedControl(h), "setup-open");
});

test("pending folder results cannot focus Connection controls behind Help", async () => {
  for (const outcome of ["cancel", "error", "selected"]) {
    const h = connectionFixture(), picker = deferredResult();
    h.host.folder = picker.promise;
    h.view.bridge = async () => ({ok: false, error: "configuration_missing"});
    click(h, "settings-choose"); openHelp(h);
    const focusBefore = focusedControl(h);
    if (outcome === "error") picker.reject(new Error("fictional picker failure"));
    else picker.resolve(outcome === "selected" ? "/fictional/other-config" : null);
    await nextTick();
    assert.equal(h.view.helpTopic, "connection", outcome);
    assert.equal(focusedControl(h), focusBefore, outcome);
    assert.deepEqual(childText(h.render().get("help-back")), ["Back to Connection"]);
    click(h, "help-back"); assert.equal(h.view.connectionSettings, true);
  }
});

test("busy setup disables Help and openHelp cannot alter the form", () => {
  const h = harness(); h.view.demo = false; h.view.model.reset(); h.view.openSetup(h.cx);
  const form = h.view.setup; form.token.set_value("fictional-token"); form.busy = true;
  assert.equal(h.render().get("help").properties.disabled[0], true);
  h.view.openHelp(h.cx);
  assert.equal(h.view.helpTopic, null); assert.equal(h.view.setup, form);
  assert.equal(form.token.value(), "fictional-token"); assert.equal(h.render().has("jira-peek-help"), false);
});

test("only setup and connection Help offer the fixed API token guide URL", () => {
  const guide = "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/";
  for (const topic of ["peek", "options", "connection", "setup"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    if (topic !== "peek") openOptions(h);
    if (topic === "connection" || topic === "setup") click(h, "connection");
    if (topic === "setup") { click(h, "setup-open"); h.view.setup.token.set_value("fictional-token"); }
    openHelp(h);
    assert.equal(h.render().has("help-token-link"), false);
    if (topic === "connection" || topic === "setup") {
      toggle(h, topic === "setup" ? "help-section-connection-details" : "help-section-choose-a-connection", true);
    }
    const link = h.render().get("help-token-link");
    if (topic === "connection" || topic === "setup") {
      assert.ok(link, topic); assert.ok(childText(link).includes("API token guide ↗"));
      click(h, "help-token-link"); assert.deepEqual(h.host.urls, [guide]);
      assert.equal(h.view.helpTopic, topic);
    } else assert.equal(link, undefined, topic);
  }
});

test("stock host Options exposes an inactive unsupported source highlight row and explains it in Help", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  openOptions(h);
  const row = h.render().get("highlight-source");
  assert.equal(row.properties.disabled[0], true); assert.equal(row.properties.pressed[0], false);
  assert.ok(childText(row).includes("Unsupported"));
  row.events.on_change(true, h.cx); assert.deepEqual(h.host.highlights, []);
  h.view.actionFocus.pin.focus(); h.dispatch("down"); assert.equal(focusedControl(h), "scan");
  openHelp(h); toggle(h, "help-section-highlight-source", true);
  assert.match(childText(h.render().get("jira-peek-help")).join(" "), /Unsupported means your Herdr app cannot display these marks/);
});

test("capable Options traverses Highlight source, toggles in place, and Help retains the mark", async () => {
  const h = harness(true); await nativeFields(h); h.view.model.pinned = true;
  const source = h.view.model.source, selected = h.view.model.current.selected;
  h.host.terminals = [{address: source, state: "live"}]; h.render();
  assert.deepEqual(h.host.marked, [source, selected]);
  openOptions(h); h.view.actionFocus.pin.focus(); h.dispatch("down");
  assert.equal(focusedControl(h), "highlight-source");
  h.dispatch("down"); assert.equal(focusedControl(h), "scan");
  h.dispatch("up"); assert.equal(focusedControl(h), "highlight-source");
  toggle(h, "highlight-source", false); await nextTurn();
  assert.ok(h.render().has("jira-peek-options")); assert.deepEqual(h.host.highlights.at(-1), [null, null]);
  toggle(h, "highlight-source", true); await nextTurn();
  assert.deepEqual(h.host.highlights.at(-1), [source, selected]);
  const count = h.host.highlights.length;
  openHelp(h); click(h, "help-back"); h.render();
  assert.deepEqual(h.host.marked, [source, selected]);
  assert.ok(h.host.highlights.slice(count).every(args => args[0] === source && args[1] === selected));
  openOptions(h); click(h, "connection"); assert.deepEqual(h.host.highlights.at(-1), [null, null]);
  click(h, "settings-back"); h.render(); assert.deepEqual(h.host.highlights.at(-1), [source, selected]);
});

test("throwing highlight extension preserves rendering and offers a local retry hint", async () => {
  const h = harness(true); await nativeFields(h); h.view.model.pinned = true;
  h.host.terminals = [{address: h.view.model.source, state: "live"}]; h.host.highlightThrows = true;
  assert.doesNotThrow(() => h.render()); assert.ok(readerText(h).length > 0);
  openOptions(h);
  assert.ok(childText(h.render().get("highlight-source")).includes("Failed"));
  assert.equal(h.host.highlights.length, 2, "redraws do not repeat the failed pair");
  openHelp(h);
  toggle(h, "help-section-highlight-source", true);
  assert.match(childText(h.render().get("jira-peek-help")).join(" "), /Turn Highlight source off and on to retry/);
  openOptions(h); toggle(h, "highlight-source", false); await nextTurn();
  h.host.highlightThrows = false; toggle(h, "highlight-source", true); await nextTurn();
  assert.ok(childText(h.render().get("highlight-source")).includes("On"));
  assert.equal(h.view.highlightError, false);
});

test("render restores a cleared native mark after a coalesced live restart without disturbing Paused reading", async () => {
  const h = harness(true); await nativeFields(h); h.view.model.pinned = true;
  const source = h.view.model.source, selected = h.view.model.current.selected;
  h.host.terminals = [{address: source, state: "live"}];
  h.view.model.filter("retained filter"); h.view.syncInput(); h.view.readerHandle.focus();
  h.render(); assert.deepEqual(h.host.marked, [source, selected]);
  const before = JSON.stringify([...h.view.model.sources]);
  const input = h.view.input.value(), readerFocus = h.view.readerFocus;
  let scrolls = 0, notifications = 0, inputWrites = 0;
  h.view.listScroll.scroll_to_item = () => scrolls++;
  h.cx.notify = () => notifications++;
  const setValue = h.view.input.set_value.bind(h.view.input);
  h.view.input.set_value = value => { inputWrites++; setValue(value); };
  // Native Closed cleared its mark, but JS sees only the restarted live record.
  h.host.marked = null;
  const calls = h.host.highlights.length;
  for (let i = 0; i < 4; i++) {
    h.render(); assert.deepEqual(h.host.marked, [source, selected]);
  }
  assert.equal(h.host.highlights.length, calls + 4, "one idempotent reassertion per stable render");
  assert.equal(JSON.stringify([...h.view.model.sources]), before);
  assert.equal(h.view.model.current.follow, false); assert.equal(h.view.input.value(), input);
  assert.equal(h.view.readerFocus, readerFocus); assert.equal(h.view.readerHandle.is_focused(), true);
  assert.deepEqual([scrolls, notifications, inputWrites], [0, 0, 0]);
  assert.deepEqual(h.host.runs, []); assert.deepEqual(h.host.traversal, []);
  h.view.toggleHighlight(h.cx); await nextTurn();
  const clearedCalls = h.host.highlights.length;
  h.render(); h.render();
  assert.equal(h.host.marked, null); assert.equal(h.host.highlights.length, clearedCalls, "no repeated null clears");
});

test("a rejected or throwing successful-pair reassertion is suppressed on subsequent renders", async () => {
  for (const failure of ["reject", "throw"]) {
    const h = harness(true); await nativeFields(h); h.view.model.pinned = true;
    h.host.terminals = [{address: h.view.model.source, state: "live"}]; h.render();
    const count = h.host.highlights.length;
    if (failure === "reject") h.host.highlightResult = false; else h.host.highlightThrows = true;
    assert.doesNotThrow(() => h.render());
    assert.equal(h.view.highlightApplied, false);
    assert.equal(h.host.highlights.length, count + 2, "one failed reassertion and one best-effort clear");
    h.render(); h.render();
    assert.equal(h.host.highlights.length, count + 2, "failed pair stays suppressed");
    h.view.toggleHighlight(h.cx); await nextTurn();
    h.host.highlightResult = true; h.host.highlightThrows = false;
    h.view.toggleHighlight(h.cx); await nextTurn(); h.render();
    assert.deepEqual(h.host.marked, [h.view.model.source, h.view.model.current.selected]);
    assert.equal(h.view.highlightApplied, true);
  }
});

test("disclosure shortcuts reveal their controls, honor field placement, and keep Escape focused", () => {
  const h = harness(); h.render(); h.view.readerHandle.focus();
  assert.equal(h.dispatch("d"), true);
  assert.equal(h.view.detailsOpen, true);
  assert.equal(h.view.actionFocus["details-toggle"].is_focused(), true);
  h.dispatch("escape");
  assert.equal(h.view.detailsOpen, false);
  assert.equal(h.view.readerHandle.is_focused(), true);
  h.view.currentFieldLayout().fields.find(field => field.id === "comments").section = "details";
  assert.equal(h.dispatch("c"), true);
  assert.equal(h.view.detailsOpen, true);
  assert.equal(h.view.commentsOpen, true);
  assert.equal(h.view.actionFocus["comments-toggle"].is_focused(), true);
  assert.ok(childText(h.render().get("jira-details-fields")).includes("Comments (1)"));
  h.dispatch("escape");
  h.view.currentFieldLayout().fields.find(field => field.id === "comments").section = "hidden";
  h.dispatch("c");
  assert.equal(h.view.commentsOpen, false);
  assert.equal(h.view.readerHandle.is_focused(), true);
});

test("follow and unread shortcuts preserve deliberate reading and ignore key repeats", () => {
  const h = harness(); h.view.demo = false; h.view.model.pinned = true;
  h.view.scan = () => {}; h.view.pump = () => {};
  h.view.readerHandle.focus(); h.view.model.browse();
  assert.equal(h.dispatch("f"), true); assert.equal(h.view.model.current.follow, true);
  h.view.keyDown({ ...h.key("f"), is_held: true }, h.cx);
  assert.equal(h.view.model.current.follow, true);
  h.dispatch("f"); assert.equal(h.view.model.current.follow, false);
  h.view.model.filter("catalog"); h.view.syncInput();
  h.view.model.merge(["DEMO-3101", "DEMO-3102"]);
  h.dispatch("n");
  assert.equal(h.view.model.current.selected, "DEMO-3101");
  assert.deepEqual([...h.view.model.current.unseen], ["DEMO-3102"]);
  assert.equal(h.view.model.current.follow, false);
  assert.equal(h.view.model.current.query, "catalog");
  h.view.keyDown({ ...h.key("n"), is_held: true }, h.cx);
  assert.equal(h.view.model.current.selected, "DEMO-3101");
});

test("new reading shortcuts do not change typed text, drafts, excluded selections, or host chords", () => {
  for (const target of ["search", "fields", "setup"]) {
    const h = harness();
    if (target === "search") h.view.search(h.cx);
    if (target === "fields") h.view.openFields(h.cx);
    if (target === "setup") h.view.openSetup(h.cx);
    for (const key of ["c", "d", "f", "n"]) assert.equal(h.dispatch(key), false, target);
    assert.equal(h.view.commentsOpen, false); assert.equal(h.view.detailsOpen, false);
  }
  const h = harness(); h.view.readerHandle.focus();
  for (const modifier of ["shift", "control", "alt", "platform"]) {
    for (const key of ["c", "d", "f", "n"]) {
      if (modifier === "platform" && key === "f") continue; // Existing native Find shortcut.
      assert.equal(h.dispatch(key, { [modifier]: true }), false);
    }
  }
  h.view.search(h.cx); h.view.input.edit("empty-results"); h.view.handle.focus();
  h.dispatch("c"); h.dispatch("d");
  assert.equal(h.view.commentsOpen, false); assert.equal(h.view.detailsOpen, false);
});

test("keyboard paging pauses Follow before native scrolling without swallowing the key", () => {
  const h = harness(false, true); h.view.readerHandle.focus();
  const selected = h.view.model.current.selected;
  for (const key of ["pageup", "pagedown", "home", "end", "space"]) {
    h.view.model.current.follow = true; h.cx.stopped = false;
    h.render().get(`reader-${h.view.epoch}-${h.view.model.source}-${selected}`).events.on_key_down(h.key(key), h.cx);
    assert.equal(h.view.model.current.follow, false, key);
    assert.equal(h.cx.stopped, false, "native pane still handles movement");
    h.view.model.merge(["DEMO-3200"]);
    assert.equal(h.view.model.current.selected, selected);
  }
});

test("shortcut help opens directly, navigates topics with arrows, and returns to the reading focus", () => {
  const h = harness(); h.view.readerHandle.focus();
  h.dispatch("/", { shift: true });
  assert.equal(h.view.helpExpanded, "Keyboard");
  assert.ok(h.render().has("jira-shortcuts"));
  for (const label of ["Find an issue", "Read in Peek", "Back one step", "Pin / return"]) {
    assert.ok(childText(h.render().get("jira-shortcuts")).includes(label));
  }
  assert.equal(childText(h.render().get("jira-shortcuts")).includes("Open in Jira"), false);
  assert.equal(h.render().has("jira-more-shortcuts"), false);
  h.dispatch("down");
  assert.equal(h.view.actionFocus["help-section-keyboard"].is_focused(), true);
  h.dispatch("end");
  const last = h.view.helpSections().at(-1)[0];
  assert.equal(h.view.actionFocus[h.view.helpSectionId(last)].is_focused(), true);
  h.dispatch("/", { shift: true });
  assert.equal(h.view.helpTopic, null); assert.equal(h.view.readerHandle.is_focused(), true);
  click(h, "shortcuts"); assert.ok(h.render().has("jira-shortcuts"));
  toggle(h, "help-section-more-shortcuts", true);
  assert.equal(h.render().has("jira-shortcuts"), false);
  const more = childText(h.render().get("jira-more-shortcuts"));
  for (const label of ["⌘/Ctrl+Enter", "Open in Jira", "Follow / next unread", "Comments / details"]) assert.ok(more.includes(label));
  h.dispatch("escape"); assert.equal(h.view.readerHandle.is_focused(), true);
});

test("Options shortcut labels perform their advertised action and restore focus", () => {
  for (const shift of [false, true]) {
    const h = harness(); h.view.readerHandle.focus(); h.view.openOptions(h.cx);
    h.dispatch("y", { shift });
    assert.equal(h.view.moreOpen, false);
    assert.equal(h.view.readerHandle.is_focused(), true);
    assert.equal(h.host.clipboard.at(-1), shift ? "https://jira.example.test/browse/DEMO-1042" : "DEMO-1042");
  }
});

test("C and D from a short results list reveal the reader before focusing the disclosure", () => {
  for (const key of ["c", "d"]) {
    const h = harness(); h.view.height = 400; h.view.search(h.cx); h.view.handle.focus();
    assert.ok(h.render().has("issue-list"));
    h.dispatch(key);
    assert.equal(h.view.readerFocus, true);
    assert.equal(h.render().has("issue-list"), false);
    assert.equal(h.view.actionFocus[key === "c" ? "comments-toggle" : "details-toggle"].is_focused(), true);
  }
});

test("Tab traversal pauses main-view Follow before discovery without changing auxiliary screens", () => {
  for (const shift of [false, true]) {
    const h = harness(); h.view.actionFocus["quick-copy-key"].focus();
    h.view.model.current.follow = true;
    const selected = h.view.model.current.selected;
    assert.equal(h.dispatch("tab", { shift }), true);
    assert.equal(h.view.model.current.follow, false);
    h.view.model.merge(["DEMO-4100"]);
    assert.equal(h.view.model.current.selected, selected);
    assert.deepEqual([...h.view.model.current.unseen], ["DEMO-4100"]);
    assert.deepEqual(h.host.traversal, [shift ? "previous" : "next"]);
  }
  for (const screen of ["options", "help", "fields", "setup", "connection"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    h.view.handleCommand(screen, h.cx);
    h.view.model.current.follow = true;
    h.dispatch("tab");
    assert.equal(h.view.model.current.follow, true, screen);
  }
});

test("resuming Follow moves disclosure focus to the reader before immediate or delayed selection changes", () => {
  for (const delayed of [false, true]) for (const focus of ["comments-toggle", "comments-retry", "details-toggle", "retry-refresh"]) {
    const h = harness(); h.view.demo = false; h.view.model.pinned = true;
    h.view.scan = () => {}; h.view.pump = () => {};
    h.view.currentFieldLayout().fields.find(field => field.id === "comments").section = "details";
    h.view.readerHandle.focus(); h.dispatch("c"); h.render();
    h.view.actionFocus[focus].focus();
    const old = h.view.model.current.selected;
    if (!delayed) h.view.model.merge(["DEMO-4200"]);
    h.dispatch("f");
    assert.equal(h.view.readerHandle.is_focused(), true, focus);
    assert.equal(h.view.model.current.follow, true);
    if (delayed) { assert.equal(h.view.model.current.selected, old); h.view.model.merge(["DEMO-4200"]); }
    h.render();
    assert.equal(h.view.model.current.selected, "DEMO-4200");
    assert.equal(h.view.detailsOpen, false); assert.equal(h.view.commentsOpen, false);
    assert.equal(h.view.readerHandle.is_focused(), true, focus);
    assert.equal(h.view.actionFocus[focus].is_focused(), false);
  }
});


test("P pins the viewed issue directly and K retains the query and unrelated unread activity", () => {
  const h = harness(); const target = h.view.model.current.selected;
  assert.equal(h.render().has("pinned-return"), false);
  h.view.readerHandle.focus(); h.dispatch("p");
  assert.equal(h.view.model.current.pinnedIssueKey, target);
  assert.equal(h.view.model.current.follow, false);
  assert.equal(h.view.moreOpen, false);
  assert.equal(h.render().get("quick-pin").properties.pressed[0], true);
  assert.equal(h.render().has("pinned-return"), false, "no added row while reading the pin");
  h.view.select("DEMO-1038", h.cx); h.dispatch("y");
  assert.equal(h.host.clipboard.at(-1), "DEMO-1038");
  h.view.model.merge(["DEMO-5001", "DEMO-5002"]);
  h.view.model.current.unseen.add(target);
  h.view.search(h.cx); h.view.input.edit("unmatched-return-query"); h.view.handle.focus();
  assert.equal(h.view.issueActionKey(), null);
  h.dispatch("p"); assert.equal(h.view.model.current.pinnedIssueKey, target, "excluded selection cannot move the pin");
  h.dispatch("k");
  assert.equal(h.view.model.current.selected, target);
  assert.equal(h.view.model.current.query, "unmatched-return-query");
  assert.equal(h.view.model.current.follow, false);
  assert.deepEqual([...h.view.model.current.unseen], ["DEMO-5001", "DEMO-5002"]);
  assert.equal(h.view.readerHandle.is_focused(), true);
  assert.equal(h.view.issueActionKey(), target);
  h.dispatch("y"); assert.equal(h.host.clipboard.at(-1), target);
  h.view.toggleReaderFocus(h.cx); assert.equal(h.view.input.value(), "unmatched-return-query");
  assert.ok(h.render().has("pinned-return"));
  click(h, "pinned-return"); assert.equal(h.view.readerHandle.is_focused(), true);
  assert.deepEqual(h.render().get("jira-control-hint").properties.h, [40]);
});

test("the inline pin moves immediately, toggles off, and never opens management or requests data", () => {
  const h = harness(); const old = h.view.model.current.selected;
  let reads = 0; h.view.pump = () => reads++; h.view.scan = () => reads++;
  toggle(h, "quick-pin", true); assert.equal(h.view.model.current.pinnedIssueKey, old);
  h.view.select("DEMO-1038", h.cx); const expectedReads = reads;
  h.view.actionFocus["quick-pin"].focus();
  h.dispatch("p");
  assert.equal(h.view.model.current.pinnedIssueKey, "DEMO-1038");
  assert.equal(h.view.moreOpen, false); assert.equal(h.view.actionFocus["quick-pin"].is_focused(), true);
  assert.equal(h.render().get("quick-pin").properties.accessibility_label[0], "Unpin issue DEMO-1038");
  toggle(h, "quick-pin", false);
  assert.equal(h.view.model.current.pinnedIssueKey, null);
  assert.equal(h.view.model.current.selected, "DEMO-1038"); assert.equal(reads, expectedReads);
  h.view.openOptions(h.cx);
  const labels = childText(h.render().get("jira-peek-options")).join(" ");
  assert.match(labels, /Keep this terminal/);
  assert.doesNotMatch(labels, /Bookmark|Replace|Clear pin|Pin issue/);
});

test("P and K leave editing, auxiliary screens, modified and held keys alone", () => {
  for (const key of ["p", "k"]) {
    const h = harness(); const target = h.view.model.current.selected;
    h.view.model.toggleIssuePin(target); h.view.select("DEMO-1038", h.cx);
    for (const screen of ["search", "fields", "options", "help"]) {
      if (screen === "search") { h.view.search(h.cx); h.view.input.edit(key); }
      if (screen === "fields") h.view.openFields(h.cx);
      if (screen === "options") h.view.openOptions(h.cx);
      if (screen === "help") h.view.openHelp(h.cx);
      h.dispatch(key);
      assert.equal(h.view.model.current.selected, "DEMO-1038", screen);
      assert.equal(h.view.model.current.pinnedIssueKey, target, screen);
      if (screen === "help") h.view.closeHelp(h.cx);
      if (screen === "fields") h.view.closeFields(h.cx);
      if (h.view.moreOpen) h.view.closeOptions(h.cx);
    }
    h.view.readerHandle.focus(); h.view.readerFocus = true;
    for (const modifiers of [{shift:true},{control:true},{alt:true},{platform:true}]) {
      h.dispatch(key, modifiers);
      assert.equal(h.view.model.current.selected, "DEMO-1038");
      assert.equal(h.view.model.current.pinnedIssueKey, target);
    }
    h.view.keyDown({...h.key(key), is_held:true}, h.cx);
    assert.equal(h.view.model.current.selected, "DEMO-1038");
    assert.equal(h.view.model.current.pinnedIssueKey, target);
  }
});

test("pinned return reloads normally at TTL zero; manual lookup cannot pin an issue", () => {
  const h = harness(); const target = h.view.model.current.selected;
  h.view.model.config.ttl = 0; h.view.model.toggleIssuePin(target);
  h.view.select("DEMO-1038", h.cx); assert.equal(h.view.model.details.has(target), false);
  const loads = []; h.view.pump = () => loads.push(h.view.model.current.selected);
  h.view.readerHandle.focus(); h.dispatch("k"); assert.deepEqual(loads, [target]);
  h.dispatch("p");
  assert.equal(h.view.model.current.pinnedIssueKey, null);
  assert.equal(h.view.model.current.selected, target); assert.equal(h.view.readerHandle.is_focused(), true);
  assert.deepEqual(loads, [target], "unpin does not request issue data");
  h.view.model.useSource("manual"); h.view.model.merge([target]); h.view.readerHandle.focus();
  h.dispatch("p"); assert.equal(h.view.model.current.pinnedIssueKey, null);
  assert.equal(h.render().has("quick-pin"), false);
});
