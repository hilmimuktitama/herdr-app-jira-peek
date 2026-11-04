# Native input and reading fixes

These fixes require a patched **herdr-app 0.1.12**, pinned to
`4aa3460749947e7771aa39a8a2cec58d46649926`. Installing the mod alone cannot
correct asynchronous shortcut dispatch or ordinary scroll panes in stock
0.1.11 and 0.1.12.
The ordinary Jira Peek minimum remains **herdr-app >= 0.1.10**; herdr-core
and its `hc` executable are a separate component.

The [patch](herdr-app-input.patch) makes three focused changes:

- `layout.focus {id}` shows the attached mod and calls its synchronous
  `focus(cx)` method in the same native command dispatch. GPUI publishes the
  new input handler before returning from a focus-changing key. Text, paste
  and IME use the native input directly; there is no text buffer or replay.
  A missing target or failed handler focuses the window and reports the error.
- Ordinary scroll panes handle Page Up/Down and Home/End. Space/Shift+Space
  pages the focused pane; native button activation and text editing keep
  precedence. Newly focused controls request visibility in the nearest
  scroll ancestor using GPUI's existing autoscroll mechanism.
- A surviving mod copy retains up to 64 named scroll positions in memory.
  Hiding unmounts the pane without dropping its handle. Peek names readers
  by connection epoch, source and issue; another issue starts independently.
  Native layout clamps positions when content shrinks. Nothing is persisted.

The build also disables an unused Ghostty xcframework so macOS Command Line
Tools suffice for the static library used by Herdr. It adds no dependency.
This patch is separate from the optional 0.1.10 terminal-highlight extension;
do not stack patches for different host versions.

## Build and verify separately

With Rust 1.95.0, Zig 0.16.0 and the upstream platform build prerequisites:

```sh
sh native/build-input-host.sh /absolute/path/to/new-build-directory
python3 docs/screenshots/capture.py --app-review \
  --app-binary "$PWD/.local/bin/herdr-app-input" \
  --output-dir /absolute/path/to/fictional-qa-frames
```

The builder writes `.local/bin/herdr-app-input`; it leaves the signed vendor
bundle intact and does not restart the app. The fixture creates a private app home and core with
entirely fictional issues. Its terminal records input bytes without executing
them. Use the toolbar/hide review layout for shortcut trials. See the
[fixture instructions](../docs/screenshots/README.md) and
[known limitations](../README.md#known-limitations).

The earlier implementation was tested on patched 0.1.11. The same host changes
apply to 0.1.12; the current builder uses that version. Stock 0.1.12 with the old
toolbar binding still failed the isolated 40-opening retest. Updating the app
version alone does not activate these fixes.

## Activate the shortcut

Use a separate launcher for the patched executable and keep the signed vendor
bundle intact. Confirm which executable the launcher resolves to: both stock
and patched builds report 0.1.12, so the version string alone is insufficient.

After choosing to run this patched host, check that `herdr-app commands`
lists `layout.focus`, install the matching Peek mod, and replace the old
global Peek binding with:

```json
{ "global": { "ctrl-shift-j": "layout.focus:jira-peek" } }
```

Use the actual attached block ID after the colon. Merge only that binding;
preserve unrelated keys. The old `tabs-jira-peek.browse-jira` binding still
uses asynchronous delivery and must be replaced. No toolbar keyboard handler
is needed. The toolbar's visibility toggle still works.

Press the shortcut to open the filter, then type immediately. Press it again
to return to the original terminal. Open forms retain their drafts and take
focus. × hides Peek; the toolbar toggle reopens it at the same reading position.

Do not replace a running work app as part of a test. Returning to stock Herdr
requires removing the unsupported global `layout.focus` binding; pointer
browsing and the mod's other commands continue to work.
Reopening the stock app icon does not activate the patch; use the patched
launcher for everyday use until a vendor build incorporates these changes.
