// Offline fixture controls, copied only into the disposable --app-review home.
// These are never installed with Jira Peek or connected to a real Jira service.
import { View, div } from "gpui-kit";
import { Button, h_flex, v_flex } from "gpui-base";
import { appHome, props, readTextFile, run, theme, writeTextFile } from "herdr";

export default class ReviewControls extends View {
  init(_props, cx) {
    this.mode = "loading";
    cx.spawn(async cx => {
      const saved = await readTextFile(appHome() + "/fixture-response.json");
      this.mode = JSON.parse(saved || "{}").mode || "success"; cx.notify();
    });
  }

  response(mode, cx) {
    cx.spawn(async cx => {
      const path = appHome() + "/fixture-response.json";
      const previous = await readTextFile(path);
      await writeTextFile(path, JSON.stringify({ mode, rich: true }), previous);
      this.mode = mode; cx.notify();
    });
  }

  discover(cx) {
    cx.spawn(async cx => {
      const path = appHome() + "/fixture-discovery";
      const previous = await readTextFile(path);
      const key = `ABC-${previous ? Number(previous.split("-")[1]) + 1 : 31}`;
      await writeTextFile(path, key, previous);
      this.discovery = `${key} queued for the fictional terminal.`; cx.notify();
    });
  }

  button(id, label, action, t) {
    return Button.new(id).accessibility_label(label).h(36).px(12).rounded(6)
      .bg(t.surface || t.background).border_1().border_color(t.border)
      .hover(el => el.bg(t.hover)).focus(el => el.border_color(t.accent))
      .on_click((_e, cx) => action(cx)).child(label);
  }

  render() {
    const t = theme();
    if (props()?.spacer) return div().size_full().bg(t.canvas);
    const variants = [
      ["peek-review", "Dark · 300px"], ["peek-review-light", "Light · 420px"],
      ["peek-review-short", "Short · 400px high"], ["peek-review-many", "Long issue list"],
      ["peek-review-empty", "No terminal"], ["peek-review-setup", "Setup needed"],
      ["peek-review-demo", "Fictional demo"],
      ["peek-review-toolbar", "Toolbar and hide/reopen"],
    ];
    return v_flex().size_full().min_w(0).overflow_y_scrollbar().p(24).gap(18)
      .bg(t.canvas).text_color(t.foreground).text_size(14)
      .child(div().text_size(11).text_color(t.accent).child("OFFLINE UX LAB"))
      .child(div().text_size(24).font_semibold().child("Jira Peek interaction review"))
      .child(div().text_color(t.muted).child("Every issue, identity, and response in this window is fictional. The local backend has no network implementation."))
      .child(v_flex().gap(8).children(variants.map(([name, label]) =>
        this.button(name, label, () => run("layout.switch", { name }), t))))
      .child(h_flex().gap(8).children([300, 420].map(width =>
        this.button(`resize-${width}`, `Resize panel to ${width}px`, () =>
          run("layout.resize", { id: props()?.resizeId || "review-panel", px: width }), t))))
      .child(div().font_semibold().child("Next backend response"))
      .child(h_flex().gap(8).flex_wrap().children([
        ["success", "Success"], ["slow", "Slow success (6s)"], ["failure", "Failure"],
      ].map(([mode, label]) => this.button(mode, label, cx => this.response(mode, cx), t))))
      .child(div().text_color(t.muted).child(`Selected response: ${this.mode}. Use Refresh in Jira Peek to exercise it.`))
      .child(this.button("discover", "Discover a new issue", cx => this.discover(cx), t))
      .when(!!this.discovery, el => el.child(div().text_color(t.muted).child(this.discovery)))
      .child(div().text_color(t.muted).child("Review search, keyboard traversal, list navigation, reading, Options, refresh recovery, and copy feedback. Close this test window through the capture script when finished."));
  }
}
