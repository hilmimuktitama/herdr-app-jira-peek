# Browse, hide and reopen Jira Peek

Jira Peek's header × hides its attached layout block. Herdr keeps that mod
instance alive, preserving selection, filter, Paused state and panel width.
On herdr-app 0.1.11 the native reader scroll offset resets when the block reappears;
the mod API has no ordinary scroll-offset handle to restore it.
Escape still steps back through the reader and returns focus to the terminal.

The optional keyboard flow starts with **Ctrl+Shift+J**.
It reveals Peek if hidden, requests search focus and selects the previous filter so
typing replaces it. Browsing pauses Follow. Press the same shortcut to return
to the terminal without clearing the filter, or Escape after choosing an
issue. Header × and the toolbar toggle still control visibility.

**Known input race on stock 0.1.11:** the shortcut does not synchronously take
input away from the terminal. Immediate typing or paste plus Return can reach
the terminal before search receives focus. Use Issues or Tab to reach the
filter for reliable entry. A delay is not an input-ownership guarantee. See
the [host requirements and acceptance cases](HOST-INPUT-GAPS.md).

The optional [keys.json](../keys.json) routes this shortcut through the
personal toolbar below. Herdr only delivers mod commands to visible copies,
so a direct `jira-peek.search` binding cannot reopen a hidden panel.

## Persistent toolbar toggle

For a source ZIP or checkout, `python3 scripts/install-app.py --check --attach`
creates the personal toolbar and a `main-jira-peek` layout together. Add
`--update` for an existing managed installation. Select the new layout with
the command printed by the installer. This preserves shipped files, existing
personal files and shortcuts. A toolbar button is not part of a bare mod-folder
copy or an installation without `--attach`.

The steps below are the manual alternative for a customized layout. If you
used `--attach`, skip these steps and only add the optional keyboard handler
below if you want it.

For the stock herdr-app **0.1.11** tabs mod, add a Jira Peek toggle beside
Files/Changes in a personal copy.

1. Clone the tabs mod using Herdr's command:

   ```sh
   herdr-app do mod.clone '{"name":"tabs","as":"tabs-jira-peek"}'
   ```

2. In `HERDR_APP_HOME/mods/tabs-jira-peek/main.js`, add `Toggle` to the
   existing `gpui-base` import. Insert this chain immediately after the
   Files/Changes buttons, before the window buttons. The stock mod already
   supplies `find`, `root`, `t`, `stop`, `settings` and `run`.

   ```js
      .when(!!find(root, "jira-peek"), el => {
        const peek = find(root, "jira-peek");
        return el.child(Toggle.new("panel-jira-peek")
          .accessibility_label("Jira Peek").pressed(!peek.hidden)
          .h(26).px(8).flex_none().rounded(6)
          .text_size(settings().ui_font_size)
          .bg(peek.hidden ? t.chrome : t.selected)
          .text_color(peek.hidden ? t.muted : t.foreground)
          .hover(s => s.bg(t.hover)).focus(s => s.bg(t.selected))
          .on_mouse_down("left", stop)
          .on_change(() => run("layout.toggle", { id: peek.id }))
          .child("Jira Peek"));
      })
   ```

3. In your personal layout, change only the tabs block's
   `content.mod` from `tabs` to `tabs-jira-peek`. Keep the Jira Peek block
   beside the terminal, as shown in the [attachment guide](../README.md#install).
   If that block has a different ID, update both `find` calls above and the
   shortcut suffix to match.

Save the files. The toggle remains in the toolbar when Jira Peek is hidden,
and its pressed state reflects the layout. Try hiding with ×, reopening with
the toggle, and hiding/reopening with the shortcut. The selected issue,
filter, Paused state and width should remain in place. Files/Changes retain their own toggle.

## One shortcut from the terminal

In the same personal `tabs-jira-peek/main.js`, add `nextCommand`, `focused`
and `setShared` to its `herdr` import. Replace the stock `init()` with:

```js
  init(_props, cx) {
    this.pressed = null;
    this.panels = JSON.parse(localStorage.getItem("panels") ?? "{}");
    cx.spawn(async cx => {
      for (;;) {
        if (await nextCommand() !== "browse-jira") continue;
        const panel = find(layout(), "jira-peek");
        if (!panel) continue;
        const context = focused();
        setShared("jira-peek.browse", {
          id: panel.id, at: Date.now(), space: context?.space, tab: context?.tab,
        });
        run("layout.show", { id: panel.id });
        cx.notify();
      }
    });
  }
```

Match `find` to the actual Jira Peek block ID. Merge `keys.json`, preserving
unrelated bindings: `ctrl-shift-j` in `global` becomes
`tabs-jira-peek.browse-jira`. A different personal toolbar name needs the same
change in the command prefix. The normal installer does not edit these files.

The panel consumes this short-lived request on its first visible render,
including its first opening. It clears the request and ignores stale requests
or a changed space/tab. There is no timer retry or separate process. Open
forms retain their draft and receive focus instead of being discarded.

Use only a harmless fictional terminal receiver to stress the unresolved
handoff. Immediate input must not be tested against a working shell or agent.
Once search has visibly received focus, verify arrows, Enter and Escape;
repeat with a previous filter. That settled-state check does not establish
atomic focus transfer. New terminal output must not change selection while browsing.

Do not edit shipped `tabs` or `main.json`: Herdr replaces shipped files on
startup. A personal tabs copy stays yours; review it when updating Herdr.
To remove the toolbar integration, point your personal layout back to `tabs`
before deleting `tabs-jira-peek`, and remove only the shortcut you added.

## References checked 1 November 2026

- [herdr-app 0.1.11 tabs implementation](https://github.com/herdrdev/herdr-app/blob/v0.1.11/defaults/mods/tabs/main.js#L79):
  visible toolbar controls toggle the native side panel.
- [herdr-app 0.1.11 mod and layout contracts](https://github.com/herdrdev/herdr-app/blob/v0.1.11/defaults/AGENTS.md):
  hidden instances stay alive, layout interaction state persists, mod commands
  reach visible copies, and shipped mods should be cloned for customization.
- [Herdr layout commands](https://github.com/herdrdev/herdr-app/blob/v0.1.11/docs/commands.md):
  `layout.hide`, `layout.show` and `layout.toggle` target layout node IDs.
- [Apple split views guidance](https://developer.apple.com/design/human-interface-guidelines/split-views):
  secondary panes can hide to free space, with toolbar and keyboard ways back.

These support a native hide/show interaction with a persistent reopening
control. No separate collapsed rail or custom visibility storage is needed.
