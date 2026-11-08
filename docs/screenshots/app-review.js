// Offline fixture controls, copied only into the disposable --app-review home.
// These are never installed with Jira Peek or connected to a real Jira service.
import { View, div } from "gpui-kit";
import { Button, Input, InputState, h_flex, v_flex } from "gpui-base";
import { appHome, props, readTextFile, run, setShared, shared, theme, writeTextFile } from "herdr";

export default class ReviewControls extends View {
  init(_props, cx) {
    this.mode = "loading";
    this.clipboard = InputState.new({placeholder:"Paste the copied fictional link here"});
    this.clipboard.on("change", () => setShared("fixture.clipboard", this.clipboard.value()));
    cx.spawn(async cx => {
      const saved = await readTextFile(appHome() + "/fixture-response.json");
      this.mode = JSON.parse(saved || "{}").mode || "success"; cx.notify();
    });
  }

  delayedIssue(cx) {
    cx.spawn(async cx => {
      const file = appHome() + "/fixture-response.json";
      await writeTextFile(file, JSON.stringify({rich:true, readerReview:true, delayIssue:6}), await readTextFile(file));
      const number = (shared("fixture.open")?.number || 100) + 1;
      const summary = number % 2 ? "Catalog exports" : "Keep catalog filters when returning from a saved item";
      setShared("fixture.open", {number, key:`ABC-${number}`, summary});
      this.mode = "delayed reader review"; cx.notify();
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
      const key = `ABC-${Math.max(30, ...[...(previous || "").matchAll(/ABC-(\d+)/g)].map(match => Number(match[1]))) + 1}`;
      await writeTextFile(path, key, previous);
      this.discovery = `${key} queued for the fictional terminal.`; cx.notify();
    });
  }

  unreadReview(cx) {
    cx.spawn(async cx => {
      const response = appHome() + "/fixture-response.json";
      await writeTextFile(response, JSON.stringify({rich:true, unreadReview:true}), await readTextFile(response));
      const discovery = appHome() + "/fixture-discovery";
      const number = Date.now();
      await writeTextFile(discovery, JSON.stringify({keys:["ABC-2"], reset:true, number}), await readTextFile(discovery));
      setShared("fixture.activity", {number});
      this.mode = "unread review: 12 issues, four Viewport matches"; cx.notify();
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
      ["peek-review-tiny", "Very short · 300px high"],
      ["peek-review-499", "Boundary · 499px high"], ["peek-review-500", "Boundary · 500px high"],
      ["peek-review-font16", "Font 16 · 380px high"], ["peek-review-font20", "Font 20 · 500px high"],
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
      .child(h_flex().gap(8).flex_wrap().children([300, 360, 420, 440].map(width =>
        this.button(`resize-${width}`, `Resize panel to ${width}px`, () =>
          run("layout.resize", { id: props()?.resizeId || "review-panel", px: width }), t))))
      .child(div().font_semibold().child("Next backend response"))
      .child(h_flex().gap(8).flex_wrap().children([
        ["success", "Success"], ["slow", "Slow success (6s)"], ["failure", "Failure"],
      ].map(([mode, label]) => this.button(mode, label, cx => this.response(mode, cx), t))))
      .child(div().text_color(t.muted).child(`Selected response: ${this.mode}. Use Refresh in Jira Peek to exercise it.`))
      .child(this.button("discover", "Discover a new issue", cx => this.discover(cx), t))
      .child(this.button("delayed-issue", "Load next known title · 6s delay", cx => this.delayedIssue(cx), t))
      .child(this.button("unread-review", "Prepare unread review · 4 matches", cx => this.unreadReview(cx), t))
      .child(Input.new(this.clipboard).id("fixture-clipboard").w_full())
      .when(!!this.discovery, el => el.child(div().text_color(t.muted).child(this.discovery)))
      .child(div().text_color(t.muted).child("Review search, keyboard traversal, list navigation, reading, Options, refresh recovery, and copy feedback. Close this test window through the capture script when finished."));
  }
}
