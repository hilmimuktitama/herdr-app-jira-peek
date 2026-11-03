# Browse, hide and reopen Jira Peek

The header × hides Peek; the persistent toolbar toggle reopens it. Selection,
filter, Paused state and width survive. The optional [native input patch](../native/APP-INPUT.md)
also preserves the reading position and enables keyboard scrolling.

**Ctrl+Shift+J** uses the patched host's synchronous `layout.focus` command to
reveal the filter and select its previous query. Type immediately, use arrows
to preview, then Enter to read. Repeat the shortcut to return to the original
terminal. An open form keeps its draft and receives focus.

Stock herdr-app 0.1.11/0.1.12's old toolbar command can leak immediate typing and
Return to the terminal. Use Issues or Tab to reach its filter. Do not install
the new binding on a host without `layout.focus`; see the [host boundary](HOST-INPUT-GAPS.md).

## Persistent toolbar toggle

For a source ZIP or checkout, `python3 scripts/install-app.py --check --attach`
creates the personal toolbar and a `main-jira-peek` layout together. Add
`--update` for an existing managed installation. Select the new layout with
the command printed by the installer. This preserves shipped files, existing
personal files and shortcuts. A toolbar button is not part of a bare mod-folder
copy or an installation without `--attach`.

The steps below are the manual alternative for a customized layout. If you
used `--attach`, skip these steps. The optional shortcut below is separate.

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

Build and test the [native input patch](../native/APP-INPUT.md) separately.
Check that `herdr-app commands` lists `layout.focus`, then merge this entry into
`HERDR_APP_HOME/keys.json`, preserving unrelated bindings:

```json
{ "global": { "ctrl-shift-j": "layout.focus:jira-peek" } }
```

Use the actual attached block ID after the colon. Replace the old
`tabs-jira-peek.browse-jira` binding; its asynchronous handler is no longer needed.
The normal installer leaves shortcuts unchanged. A toolbar toggle is useful
for pointer users, but the shortcut does not depend on a toolbar mod.

The command only targets an attached mod in the visible layout, including a
hidden block. It calls Peek's synchronous native-input focus method. A missing
block, hidden ancestor, or failed method sends focus to the window, preventing
terminal input. There is no text buffer, replay, or timing-based focus retry.

Test immediate input only with the isolated fictional receiver in
`docs/screenshots/capture.py --app-review`. Check both visible and hidden
compact readers, previous queries, paste, Return and repeated entry/return.

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
