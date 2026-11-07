import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const generated = execFileSync("python3", ["-B", "-c", `
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("installer", "scripts/install-app.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
source = Path("tests/fixtures/tabs.js").read_text()
source = source.replace('      .when(enabled.includes("changes"),',
    '      .child(div().id("custom-before").on_click(() => run("custom.before", {})).child("Before"))\\n      .when(enabled.includes("changes"),')
source = source.replace('      .when(w?.buttons,',
    '      .child(div().id("custom-after").on_click(() => run("custom.after", {})).child("After"))\\n      .when(w?.buttons,')
print(installer.integrate_toolbar(source, "peek-sidebar"))
`], { cwd: root, encoding: "utf8" });

function harness(panel) {
  const nodes = new Map(), calls = [];
  const element = id => {
    const state = { nodeId: id, children: [], events: {}, properties: {} };
    const node = new Proxy(state, { get(target, key) {
      if (key in target) return target[key];
      return (...args) => {
        if (key === "id") { state.nodeId = args[0]; nodes.set(args[0], node); }
        else if (key === "child") state.children.push(args[0]);
        else if (key === "when") { if (args[0]) args[1](node); }
        else if (key.startsWith("on_")) state.events[key] = args.at(-1);
        else state.properties[key] = args[0];
        return node;
      };
    }});
    if (id) nodes.set(id, node);
    return node;
  };
  const api = {
    View: class {}, div: () => element(), h_flex: () => element(), Toggle: { new: element },
    theme: () => ({}), window: () => ({}), settings: () => ({ ui_font_size: 13 }),
    shared: () => ["files", "changes"], layout: () => ({ id: "root", children: panel ? [panel] : [] }),
    run: (command, args) => {
      calls.push({ command, args });
      if (command === "layout.toggle" && args.id === panel?.id) panel.hidden = !panel.hidden;
    },
  };
  const code = generated.replace(/^import .*;\n/gm, "").replace("export default class", "return class");
  const Tabs = new Function(...Object.keys(api), code)(...Object.values(api));
  const view = new Tabs();
  return { calls, render() { nodes.clear(); return { tree: view.render(), nodes }; } };
}

test("generated toggle follows visibility, toggles the actual panel and stops toolbar dragging", () => {
  const panel = { id: "peek-sidebar", hidden: true, content: { mod: "jira-peek" } };
  const h = harness(panel);
  let button = h.render().nodes.get("panel-jira-peek");
  assert.equal(button.properties.pressed, false);
  assert.equal(button.properties.accessibility_label, "Jira Peek");
  let stopped = false;
  button.events.on_mouse_down({}, { stop_propagation() { stopped = true; } });
  assert.equal(stopped, true);
  button.events.on_change();
  assert.deepEqual(h.calls.at(-1), { command: "layout.toggle", args: { id: "peek-sidebar" } });
  assert.equal(panel.hidden, false);
  button = h.render().nodes.get("panel-jira-peek");
  assert.equal(button.properties.pressed, true);
  button.events.on_change();
  assert.equal(panel.hidden, true);
  assert.equal(h.render().nodes.get("panel-jira-peek").properties.pressed, false);
});

test("Jira Peek follows Changes immediately and preserves custom controls and handlers", () => {
  const h = harness({ id: "peek-sidebar", hidden: false });
  const { tree, nodes } = h.render();
  assert.deepEqual(tree.children.map(node => node.nodeId), [
    "panel-files", "custom-before", "panel-changes", "panel-jira-peek", "custom-after",
  ]);
  nodes.get("custom-before").events.on_click();
  nodes.get("custom-after").events.on_click();
  assert.deepEqual(h.calls.map(call => call.command), ["custom.before", "custom.after"]);
});

test("generated toolbar omits the toggle when its panel is absent", () => {
  const h = harness(null);
  const { tree, nodes } = h.render();
  assert.equal(nodes.has("panel-jira-peek"), false);
  assert.deepEqual(tree.children.map(node => node.nodeId), ["panel-files", "custom-before", "panel-changes", "custom-after"]);
  assert.deepEqual(h.calls, []);
});
