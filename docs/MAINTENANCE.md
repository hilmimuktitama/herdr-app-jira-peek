# Maintaining Jira Peek

This page holds the update, rollback, repair, cache, and uninstall details kept
out of the main README. The [README](../README.md) covers installation and daily
use.

## Update

To update an installed release:

```sh
python3 scripts/update-app.py --check  # report availability
python3 scripts/update-app.py          # install the newest numbered release
```

`--check` compares the installed and newest release. A release update may prepare
`main-jira-peek` without switching to it; select that layout once. The bundled
helper works without the checkout and targets its own app home:

```sh
python3 "${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/update-app.py"
```

The installed helper targets the app home that contains it; pass `--app-home` to
override. The source helper also honors `HERDR_APP_HOME`.

The updater requires Python 3.9+ and Git. It selects the highest numbered release
tag (including tags marked as GitHub prereleases), validates the source, and
runs the native checker before replacement; it is
not signature verification or a security audit. `--version 0.8.1` chooses a
release; older versions require `--allow-downgrade`. Both helpers accept
`--app-home`.

**Upgrading from a private preview?** Some previews used the same 0.1.0 version,
so version checks cannot identify them; extract 0.8.1 and run
`python3 scripts/install-app.py --update --check` once. See
[CHANGELOG.md](../CHANGELOG.md).

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
python3 scripts/update-app.py --rollback .jira-peek-backup-012345abcdef
# Installed copy:
python3 "${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/update-app.py" --rollback .jira-peek-backup-012345abcdef
```

Rollback works offline and does not need Git. It restores only the mod bundle and
preserves current settings, credentials, and caches; it does not restore personal
toolbar or layout files. Keep the source checkout if the older bundle lacks the
helper.

## Repair the toolbar

`--diagnose-integration` reports the bundle, layout, toolbar, panel ID, and next
action; it does not prove rendering.

```sh
python3 scripts/update-app.py --diagnose-integration
python3 scripts/update-app.py --diagnose-integration YOUR_LAYOUT
python3 scripts/update-app.py --repair-integration
python3 scripts/update-app.py --repair-integration YOUR_LAYOUT
# Without a checkout:
python3 "${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/update-app.py" --repair-integration
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
