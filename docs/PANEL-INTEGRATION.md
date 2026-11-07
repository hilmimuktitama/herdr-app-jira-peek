# Browse, hide and reopen Jira Peek

The header × hides Peek; the persistent toolbar toggle reopens it. Selection,
filter, Paused state and width survive. This integration uses stock Herdr;
no custom host or global shortcut is required.

Click Issues to enter Peek, then use Cmd+F, arrows and Enter. Cmd+F only focuses
the filter while Peek owns the keyboard. The release does not enable reliable
terminal-to-panel keyboard entry or native directional focus participation;
see the [known limitations](../README.md#known-limitations).

## Persistent toolbar toggle

For a source ZIP or checkout, `python3 scripts/install-app.py --check --attach`
creates the personal toolbar and a `main-jira-peek` layout together. Add
`--update` for an existing managed installation. Select the new layout with
the command printed by the installer. This preserves shipped files, existing
personal files and shortcuts. A toolbar button is not part of a bare mod-folder
copy. Ordinary updates now also prepare this integration from a compatible
`main` layout, so older installs receive it without an extra installer flag.
Preparation does not switch the active layout. Select `main-jira-peek` once
after updating; the installed version alone does not prove button visibility.
If personal files conflict or
the source layout is unsupported, the update preserves them and prints manual
setup guidance; use the steps below for that layout.

If an update installed the bundle but could not finish integration, run
`python3 scripts/update-app.py --repair-integration` from the source folder,
or `python3 "${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/update-app.py" --repair-integration`
without a checkout. This works offline at the installed version and checks
the toolbar with Herdr. Pass the original source layout name after the flag
for a custom layout,
not its generated `-jira-peek` copy. The release updater changes no files
when already on the selected version; use explicit repair if needed.
Repair refuses missing, unmanaged or locally edited bundles. Matching complete
integration files are reused; conflicting files are preserved for manual review.
An existing partial file from an older installer is also preserved because it
cannot safely be distinguished from a personal edit. Select the printed layout
once repair succeeds; creating its files does not activate it.

The steps below are the manual alternative for a customized layout. If you
used `--attach`, skip these steps. Keep block IDs unique and attach one Peek
copy per layout. The shared `tabs-jira-peek` toolbar targets one exact block ID;
layouts using different IDs need separate personal toolbar copies. The installer
refuses conflicting personal files instead of silently changing their targets.

If `tabs-jira-peek` conflicts, choose a new personal toolbar name (for example
`tabs-my-peek`) in every step below. Preserve the conflicting copy; do not
clone over it. A conflict blocks automatic repair and does not prove that
your toolbar is broken.

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
   If that block has a different ID, update both `find` calls above to match.

Save the files. The toggle remains in the toolbar when Jira Peek is hidden,
and its pressed state reflects the layout. Try hiding with × and reopening with
the toggle. The selected issue,
filter, Paused state and width should remain in place. Files/Changes retain their own toggle.

Automatic toolbar preparation is best effort: a valid code update can finish
while toolbar setup is skipped. Explicit attachment validation fails before
code replacement. Publication afterward can leave a partial integration;
inspect before retrying. Matching partial files can be reused by repair. Code
rollback restores the bundle, not personal integration files; select your
original layout and review personal toolbar/layout copies separately. Older
helpers may lose the update acknowledgement; inspect state before retrying.

## Optional keys

The source [keys.json](../keys.json) contains only F2/Follow and F5/Refresh
under `mod:jira-peek`. Merge individual entries into your existing file; do not
replace scopes or chords owned by other mods. The installer never edits keys.

For an optional visibility-only binding, stock `layout.show:<actual-block-id>`
can reveal that block in the current layout. It does not focus its filter or
reveal hidden ancestors. A hidden panel is not included in pane navigation.

Historical [native input patch instructions](../native/APP-INPUT.md) are retained
as separate development material. Their `layout.focus` command is unavailable
on stock Herdr and is deliberately absent from the release's key example.

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
