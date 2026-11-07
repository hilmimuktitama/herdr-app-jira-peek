// Entirely fictional toolbar fixture matching Herdr's supported builder contract.
import { View, div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { run, theme, window, shared, layout, settings } from "herdr";

function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

export default class Tabs extends View {
  render() {
    const t = theme();
    const stop = (_e, cx) => cx.stop_propagation();
    const root = layout(), sidebar = find(root, "sidebar"), w = window();
    const enabled = shared("workspace.panels") ?? ["files", "changes"];
    const panelButton = (id, label, icon) => div().id(`panel-${id}`).child(label);
    return h_flex().size_full()
      .when(enabled.includes("files"), el => el.child(panelButton("files", "Files", "mods/files/file.svg")))
      .when(enabled.includes("changes"), el => el.child(panelButton("changes", "Changes", "mods/changes/changes.svg")))
      .when(w?.buttons, el => el);
  }
}
