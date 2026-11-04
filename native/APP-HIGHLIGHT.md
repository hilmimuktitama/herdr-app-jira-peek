# Highlighting in the desktop working area

Jira Peek can mark the selected issue key in its source terminal. The
mark follows clicks, keyboard selection, direct lookup and Following. Paused
keeps the same key highlighted as more output arrives. Pin source keeps the
mark attached to that terminal. **Options → Highlight source** turns it off.

Stock Herdr app 0.1.10 does not expose a terminal-decoration API. The optional
[desktop patch](herdr-app-0.1.10-highlight.patch) adds one to its renderer.
This is an experimental local extension, not an upstream release. Ordinary Jira
Peek features continue to work on the stock app; its Highlight source option
explains when the renderer extension is unavailable.

This extension is experimental. The recorded validation covers a macOS
development build against exactly v0.1.10; release mode, Linux and Windows
have not been validated. It is not required for normal mod installation.

## Build and use

Install Rust 1.95.0, Zig 0.16.0 and the platform build tools required by
[Herdr app](https://github.com/herdrdev/herdr-app/tree/v0.1.10), then run the release-build helper (documented, but not executed in the
2026-11-01 validation checkpoint):

```sh
sh native/build-herdr-app.sh
python3 scripts/install-app.py --update --check
```

If `.local/bin/herdr-app-peek` has already been prepared, skip the build command
and update/check the mod before switching app windows.

For a first mod installation, omit `--update`. The build is pinned to
Herdr app v0.1.10, commit `36725d47c89cd19345994363d6d9cdee5c42c80b`, and
uses its locked dependencies and pinned Ghostty submodule. It writes only a
separate `.local/bin/herdr-app-peek` executable and its build checkout. It does
not replace an installed app or change the core, layout or keybindings.

After saving any work in the app, quit the original Herdr window yourself,
then launch the local build from this checkout:

```sh
.local/bin/herdr-app-peek
```

The terminal processes remain in herdr-core when a window closes. Do not run
two app builds against the same app home concurrently. To return to the stock
app, quit the local build and reopen your normal Herdr app. Source builds do
not receive Herdr's automatic app updates; this patch must be reviewed and
rebuilt for later host versions.

## Behavior and privacy

Highlighting decorates displayed cells only. It does not send terminal input,
move the cursor or scroll position, change copied text, or query Jira. A key
that is off screen has no visible mark until it appears. Manual lookup without
a source terminal has nothing to mark. Private keys and terminal snapshots
are not written to shared state or logs by this feature; only the on/off
preference is saved.

The host validates the terminal address and key, isolates each mod copy's
ownership, and removes stale marks as copies or terminals disappear. Disabling
the option, clearing the connection or closing Peek also clears its mark.
Use the [isolated highlight fixture](../docs/screenshots/README.md#selected-key-highlights)
to check matching and lifecycle behavior before using a new host build.
