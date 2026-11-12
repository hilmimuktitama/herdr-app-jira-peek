// Event/state integration only. Native geometry is checked with Computer Use.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as model from "../../mods/jira-peek/model.js";
import { seedDemo } from "../../mods/jira-peek/demo.js";

const code = readFileSync(new URL("../../mods/jira-peek/main.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export default class", "return class");

function harness(nativeInput = false, cacheRetained = false) {
  const elements = new Map();
  const host = { settings: { ui_font_size: 13, font_size: 14, zoom: 1 }, focus: null, panes: [], terminals: [], runs: [], urls: [], clipboard: [], traversal: [], rendererHighlights: [], textViews: [], folder: Promise.resolve(null) };
  host.props = { demo: true };
  host.theme = { accent: "#82aaff", foreground: "#eeeeee", muted: "#999999" };
  host.layout = { id: "root", children: [{ id: "fixture-peek", content: { mod: "jira-peek" }, size: { px: 360 } }] };
  host.closedOverlays = [];
  host.storage = new Map([["preferences", '{"live":false,"readerFocus":false}']]);
  host.files = new Map(); host.jobs = []; host.timers = []; host.nestedViews = [];
  let active = null;
  const activate = target => {
    if (active === target) return;
    const previous = active; active = target;
    previous?.blur?.(); target?.onFocus?.();
  };
  const element = (id) => {
    const state = { nativeId: id, childNodes: [], events: {}, properties: {}, owned: false };
    const own = child => {
      if (child && typeof child === "object" && child.childNodes) {
        assert.equal(child.owned, false, "native elements are single-use values"); child.owned = true;
      }
    };
    const node = new Proxy(state, { get(target, property) {
      if (property in target) return target[property];
      return (...args) => {
        assert.equal(state.owned, false, "finish native elements before attaching them to a parent");
        if (property === "id") { state.nativeId = args[0]; elements.set(args[0], node); }
        else if (property === "when" && args[0]) args[1](node);
        else if (property === "child") { const child = args[0]?.renderView ? args[0].renderView() : args[0]; own(child); state.childNodes.push(child); }
        else if (property === "header" || property === "panel") { own(args[0]); state.childNodes.push(args[0]); state.properties[property] = args; }
        else if (property === "children") { args[0].forEach(own); state.childNodes.push(...args[0]); }
        else if (property.startsWith("on_")) state.events[property] = ["on_mouse_down", "on_mouse_up"].includes(property) ? args[1] : args[0];
        else state.properties[property] = args;
        return node;
      };
    }});
    if (id) elements.set(id, node);
    return node;
  };
  const focus = () => {
    const handle = { focus() {
      assert.ok(!host.rendering, "FocusHandle.focus() cannot run during render/layout");
      activate(handle);
    }, is_focused() { return active === handle; } };
    return handle;
  };
  const cloneDescription = node => {
    if (!node || typeof node !== "object" || !node.childNodes) return node;
    const copy = element(node.nativeId);
    copy.properties = { ...node.properties }; copy.events = { ...node.events };
    copy.children(node.childNodes.map(cloneDescription));
    return copy;
  };
  let spawned = 0;
  const cx = { stopped: false, notify() {}, new(Class, p) {
    assert.ok(!host.rendering, "retained entities must be created outside render/layout");
    const child = new Class(); child.init?.(p, cx); let description, released = false;
    const entity = { get released() { return released; }, renderView() {
      if (cacheRetained) {
        description ||= child.render(cx);
        return cloneDescription(description);
      }
      return child.render(cx);
    }, set_props(next) {
      if (released) throw new Error("this Entity has been released and can no longer be updated");
      p = next; child.update?.(p); description = null;
    }, release() { const previous = released; released = true; return !previous; } };
    host.nestedViews.push(entity); return entity;
  }, stop_propagation() { this.stopped = true; }, focus_handle: focus, spawn() {},
    timer: { after(ms, fn) { const timer = { ms, cancel() {}, fire: () => fn(cx) }; host.timers.push(timer); return timer; },
      every(ms, fn) {
        const timer = { ms, repeating: true, cancelled: false, cancel() { this.cancelled = true; }, fire() { if (!this.cancelled) fn(cx); } };
        host.timers.push(timer); return timer;
      } },
    open_url(url) { host.urls.push(url); }, write_to_clipboard(value) { host.clipboard.push(value); } };
  // Model cached retained descriptions without a notify(target) extension.
  // Run the real row worker; explicit props updates invalidate its cached text.
  if (cacheRetained) cx.spawn = body => { if (++spawned === 1) body(cx); return { cancel() {} }; };
  const InputState = { new(options = {}) { return { options, text: options.value || "", events: {},
    on(name, fn) { this.events[name] = fn; }, value() { return this.text; },
    set_value(value) { this.text = value; },
    edit(value) { this.text = value; this.events.change?.({}, cx); },
    focus() { activate(this); }, onFocus() { this.events.focus?.({}, cx); }, blur() { this.events.blur?.({}, cx); },
    is_focused() { return active === this; }, set_selected_range(range) { this.selection = range; }, set_masked() {}, release() {} }; } };
  const api = { herdr: { setTerminalHighlight(...args) { host.rendererHighlights.push(args); return true; } }, ...model, View: class {}, seedDemo, div: () => element(), h_flex: () => element(), v_flex: () => element(),
    svg: path => { const node = element(); node.properties.asset = path; node.properties.imageKind = "tinted"; return node; },
    image: path => { const node = element(); node.properties.asset = path; node.properties.imageKind = "full-color"; return node; },
    TextView: { html: (id, html) => {
      const node = element(id);
      node.properties.textViewHtml = html;
      node.properties.textViewText = String(html)
        .replace(/^<pre>/, "").replace(/<\/pre>$/, "")
        .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'").replace(/&amp;/g, "&");
      node.child(node.properties.textViewText);
      host.textViews.push(node);
      return node;
    } },
    Button: { new: id => { const node = element(id); node.properties.nativeType = "Button"; return node; } }, Toggle: { new: element }, Input: { new: () => element() }, InputState,
    Scrollbar: { vertical: () => element() }, v_virtual_list: (id, count, _height, getKey, render) => {
      const node = element(id); node.itemKeys = Array.from({ length: count }, (_, index) => getKey(index));
      node.renderRange = range => {
        host.rendering = true;
        try { return render(range); } finally { host.rendering = false; }
      };
      const start = host.virtualStart || 0;
      return node.children(render({ start, end: Math.min(count, start + (host.virtualCount || count)) }));
    },
    VirtualListScrollHandle: { new: () => ({ scroll_to_item() {} }) },
    localStorage: { getItem: key => host.storage.get(key) || null, setItem(key, value) {
      if (host.saveThrows) throw new Error("fictional storage failure");
      host.storage.set(key, value);
    }, removeItem: key => host.storage.delete(key) },
    appHome: () => "/fictional/herdr-app",
    readTextFile: async path => host.readFile ? host.readFile(path) : host.files.get(path) ?? null,
    writeTextFile: async (path, text, expected) => {
      if (host.writeFile) return host.writeFile(path, text, expected);
      host.beforeWrite?.();
      if (host.fileWriteThrows || (host.files.get(path) ?? null) !== expected) throw new Error("File changed or unavailable");
      host.files.set(path, text);
    },
    props: () => host.props, layout: () => host.layout, settings: () => host.settings, theme: () => host.theme, panes: () => host.panes,
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
  const frame = () => {
    elements.clear(); host.textViews = []; host.rendering = true;
    try { view.render(cx); } finally { host.rendering = false; }
    return elements;
  };
  const render = (settleRows = true) => {
    frame();
    if (settleRows && view.linkedFocusRecovery) { view.rowWakeTimer.fire(); frame(); }
    // Advance the panel's scheduled native wake outside the frame. Cached
    // layout alone cannot be assumed to drain JavaScript Promise jobs.
    if (settleRows && (view.rowRefreshPending || view.pendingResultActionRange)) {
      const created = host.nestedViews.length;
      view.rowWakeTimer.fire();
      if (host.nestedViews.length !== created) frame();
    }
    return elements;
  };
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

function clickResult(h, key) {
  const nodes = h.render(), list = nodes.get("jira-issue-options");
  const index = list.childNodes.indexOf(nodes.get(`issue-${key}`));
  assert.ok(index >= 0, `${key} must be a displayed compact result`);
  list.events.on_item_click(list.itemKeys[index], h.cx);
}

function pressRowAction(h, nodes, key, action) {
  const button = nodes.get(`row-${action}-${key}`);
  button.events.on_mouse_down({}, h.cx);
  const row = nodes.get(`issue-${key}`);
  if (row.events.on_click) row.events.on_click({}, h.cx);
  else {
    const list = nodes.get("jira-issue-options"), index = list.childNodes.indexOf(row);
    assert.ok(index >= 0); list.events.on_item_click(list.itemKeys[index], h.cx);
  }
  button.events.on_click({}, h.cx);
  h.view.drainRowActions(h.cx);
}

function pressReaderText(h, predicate = () => true) {
  const nodes = h.render();
  const text = h.host.textViews.find(node => predicate(node));
  assert.ok(text, "a matching reader TextView must be rendered");
  const wrapper = nodes.get(`reader-text-wrap-${text.nativeId}`);
  assert.ok(wrapper?.events.on_mouse_down, "reader text has a pointer wrapper");
  wrapper.events.on_mouse_down({}, h.cx);
  return { nodes, text, wrapper };
}

export { harness, childText, descendants };
