# Maintaining Jira Peek

This page holds the update, rollback, repair, cache, and uninstall details kept
out of the main README. The [README](../README.md) covers installation and daily
use.

## Rust maintenance (0.12.0+)

Version 0.12.0 uses the bundled executable for maintenance. For 0.11.0 and
earlier, use the [older-installation transition](#older-installations).

```sh
# Run from the installed mods/jira-peek directory.
runtime/jira-peek-bridge manage update --check
runtime/jira-peek-bridge manage update
runtime/jira-peek-bridge manage rollback .jira-peek-backup-012345abcdef --check
runtime/jira-peek-bridge manage integration diagnose
runtime/jira-peek-bridge manage integration repair --layout main
```

These REST lifecycle commands and in-app setup need no Python, jq, curl CLI or
external SHA tooling. Git is required for release updates; rollback and repair
work offline. `--app-home` overrides the installed executable's own home.
Explicit downgrades require both `--version VERSION` and `--allow-downgrade`.
Preserve a compatible newer executable or source package before restoring an
older bundle that lacks these commands. Current builds retain historical helper
files for compatibility; their older entry points keep their own dependencies.

The panel's Clear cache action remains preferred. Low-level maintenance can use
`runtime/jira-peek-bridge manage clear-cache --state-dir ABSOLUTE_NAMESPACE`
for one initialized connection directory below `state/connections`; the shared
state root is refused. It preserves other state and retires in-flight reads,
including when no disk cache exists. See [runtime details](../rust-backend/README.md).

## Update

From the installed `mods/jira-peek` directory:

```sh
runtime/jira-peek-bridge manage update --check  # report availability
runtime/jira-peek-bridge manage update          # install newest numbered release
```

Without changing directories:

```sh
"${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/jira-peek-bridge" manage update
```

The installed executable targets its own app home; `--app-home` overrides it.
The updater needs Git. It selects the highest numbered release tag (including
GitHub prereleases), validates the source/assets and runs the native checker
before replacement. A release update may prepare `main-jira-peek` without
switching to it; select the printed layout once. These checks do not establish
release signatures or a security audit. `--version VERSION` selects a numbered
release; a downgrade also requires `--allow-downgrade`.

**Same-version private preview?** Availability checks cannot distinguish it.
Use the complete new release package and its Rust
`manage install --source-root ABS --update --check` command once.

Managed updates replace only `mods/jira-peek`; `data/jira-peek` settings,
credentials, and caches are preserved. Updates refuse symlinks and edited or
unmanaged files, apart from Herdr's generated editor files. If an interrupted
replacement leaves the active bundle missing, rerunning the source installer
with `--update` can restore the recorded backup when it validates. If recovery
fails, inspect the reported state before retrying. Availability checks do not
perform recovery. No background updater is installed.

## Rollback

Use the exact backup name printed by the installer:

```sh
runtime/jira-peek-bridge manage rollback .jira-peek-backup-012345abcdef --check
```

Rollback works offline and does not need Git. It restores only the mod bundle and
preserves current settings, credentials, and caches; it does not restore personal
toolbar or layout files. Keep the source checkout if the older bundle lacks the
helper.

## Repair the toolbar

`manage integration diagnose` reports the bundle, layout, toolbar, panel ID and
next action; it does not prove rendering. From the installed mod directory:

```sh
runtime/jira-peek-bridge manage integration diagnose
runtime/jira-peek-bridge manage integration diagnose --layout YOUR_LAYOUT
runtime/jira-peek-bridge manage integration repair --layout YOUR_LAYOUT
```

Diagnosis without a layout inspects the active layout; repair defaults to `main`.
Pass the original source layout, not its generated copy. Select the printed
layout. See the [toolbar guide](PANEL-INTEGRATION.md).

## Cache

Each configuration folder has its own disk cache and connection epoch.
**Options → Connection → Clear cache** clears that folder's cache and panel
memory, then reconnects; credentials and preferences remain. The former shared
cache under `data/jira-peek/state/cache` may retain issue data and is not removed
automatically; close all copies before removing it. See
[SECURITY.md](../SECURITY.md).

## Older installations

The Python helpers remain for upgrades from 0.11.0 and earlier. From the old
installed mod directory, use `python3 runtime/update-app.py --check`, then
`python3 runtime/update-app.py` when ready. From an old source checkout, use
`python3 scripts/update-app.py`. This transition retains the old helper's Python,
Git and validation dependencies; it downloads the new release's compatibility
installer. Once on 0.12.0, use the Rust commands above.

The legacy Python **setup** helper needs curl/libcurl 7.84.0+ to read its quoted
credential files. The 0.12.0 Rust setup and reader support the older system
libcurl on Ubuntu 22.04; upgrading does not require rerunning legacy setup.

You can instead download the full 0.13.0 source and assets and use the Rust
`manage install --source-root ABS --update --check` command. Retain the new
executable or source package before downgrading: older bundles may not contain
Rust lifecycle commands. For a shell-era rollback, use a retained 0.10.0+ helper
to restore a Rust backup so executable permissions survive.

## Uninstall

To uninstall:

1. Switch to the original layout and close all Peek copies.
2. Review the generated `<layout>-jira-peek` layout and generated toolbar
   (`tabs-jira-peek` for stock `tabs`; `<source-layout>-tabs-jira-peek` for a
   personal toolbar clone). Preserve personal edits and check whether other
   layouts reference the toolbar; delete only files you no longer need.
3. Remove any shortcut you added, `mods/jira-peek`, and review
   `.jira-peek-backup-*`.
4. For a manual integration, retarget the tabs block back to `tabs` or its
   original toolbar, then remove the Peek block.
5. Remove `HERDR_APP_HOME/data/jira-peek` only to delete locally saved setup
   credentials, configuration, preferences, and caches; external configuration,
   TWG state, terminal history, clipboard, and backups need separate handling.
   Deletion is not secure erasure. See [SECURITY.md](../SECURITY.md) and the
   [toolbar guide](PANEL-INTEGRATION.md).
