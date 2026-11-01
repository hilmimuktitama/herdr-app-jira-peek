# Screenshot captures

Only entirely fictional data may appear in public screenshots. Never substitute
real issues, identities, tenant URLs, or source terminal output into these
fixtures, even with identifiers renamed or blurred.

## Native Herdr app

The four standard native PNGs were refreshed on **2026-11-01** for the working-tree
typography, panel hide, and configurable field layout updates, using stock Herdr **0.1.11 on macOS**. Text follows Herdr's
UI font size and zoom. They show the current compact
reader at 420px in dark/light themes and 300px in dark mode. The narrow and
reader captures now show the same default collapsed-list state. The left side
is a labeled fictional transcript rendered by the fixture, not a live shell.
The separate highlight captures below use the optional renderer extension.
See the current [UI record](../UX-REVIEW.md).

```sh
python3 docs/screenshots/capture.py --app
```

Requires the installed `herdr-app`, `hc`, `jq`, and Python 3, with native GUI
access. This path does not require Pillow or pyte. It creates a separate
temporary app home, core session/socket, and XDG state/config directories,
disables telemetry, and uses an offline fictional backend. It reads no real
terminal session, Jira account, private configuration, or credentials, and
closes only its own app and core afterward.

Before capturing, the rig creates a live temporary terminal containing only
fictional output. It exercises screen-only discovery and explicit available
history, native asynchronous loading, same-origin URL lookup, freshness,
Follow synchronization, reader focus, shared field/preference reloads, stale UI
save protection, malformed-file recovery, native agent commands, cache
clear/reconnect, and configuration invalidation.

It then renders the explicit fictional demo beside a labeled fictional
transcript. Outputs are the repository-root `preview.png` plus `app-light.png`,
`app-narrow.png`, and `app-reader.png` in this directory. The 300px captures exercise compact
controls and wrapping; `app-reader.png` shows the list collapsed for reading.
Add `--app-review` to keep the isolated window open for interaction review;
the offline lab offers 300px dark, 420px light, 300×400px, long-list, no-terminal,
setup, demo, and a stock toolbar layout with the documented Jira Peek toggle.
The toolbar layout also loads the example shortcut for hide/reopen checks.
Its fictional backend can succeed, delay six seconds,
or fail. Discover a new issue adds a fictional key to the rig's terminal
without sending terminal input. Use these controls to check Browse retention,
validation, keyboard navigation, refresh recovery, and copy feedback.
The resize controls change the same panel between 300px and 420px without
remounting it, so query, selection, and reading position can be checked.
The lab's `app-setup-curl.py` also exercises the real token-setup helper with
fictional credentials. Its response controls apply to the account check, so
failed authentication and delayed saves can be reviewed without network access.
Use `https://fictional-peek.atlassian.net`, `reader@example.test`, project `ABC`,
and a made-up token. These values must never be replaced with real credentials.
The lab is test tooling and is not included in the installed mod.

For Computer Use, identify the isolated app before sending input. The recorded
review used a temporary copy of the official app with a distinct name and
bundle identifier, launched through its resolved executable, so automation
could distinguish it from the normal app. Never send input to an ambiguous
app target. Press Enter in the capture process to close the review fixture.
Inspect every image and its
PNG chunks before publication. Do not use screenshots of the normal app home.
See the [verification record](../VERIFICATION.md) for recorded checks.

## Selected-key highlights in the native terminal

Use the optional desktop renderer build with the entirely fictional fixture:

```sh
python3 docs/screenshots/capture.py --app-highlight --app-binary "$PWD/.local/bin/herdr-app-peek"
```

Add `--app-review` to leave the isolated window open for keyboard and pointer
review. This creates its own core, app home, idle terminal and in-memory demo
issues; it has no Jira transport. It captures dark/light, changed selection,
disabled, hidden and restored states as `app-highlight-*.png`. It also checks
that changing or disabling the mark leaves the terminal text unchanged.
Visually inspect the key matches and token boundaries in the captures; command
success alone does not establish correct rendering. The fixture stops only its
own app and core when it finishes.
