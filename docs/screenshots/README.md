# Screenshot captures

Only entirely fictional data may appear in public screenshots. Never substitute
real issues, identities, tenant URLs, or source terminal output into these
fixtures, even with identifiers renamed or blurred.

## Native Herdr app

The eight standard native PNGs were refreshed on **2026-11-03** for the composed
layout polish, using patched herdr-app **0.1.12 on macOS**. Text follows Herdr's
UI font size and zoom; the issue title adds two logical pixels. They show the current compact
reader at 420px in dark/light themes and 300px in dark mode. The narrow and
reader captures now show the same default collapsed-list state. The left side
is a labeled fictional transcript rendered by the fixture, not a live shell.
The separate highlight captures below use the optional renderer extension.
The 300×400px panel scrolls the title with the body while retaining its key and
actions above. Neutral selected rows use checkmarks without decorative side bars.
See the current [UI record](../UX-REVIEW.md).
Browsing and short-panel images were refreshed on **2026-11-04 WIB** to show
the match count beside the filter; the remaining six keep their earlier capture.

```sh
python3 docs/screenshots/capture.py --app
```

Requires the installed `herdr-app`, `hc`, `jq`, and Python 3, with native GUI
access. This path does not require Pillow or pyte. It creates a separate
temporary app home, core session/socket, and XDG state/config directories,
disables telemetry, redirects host release checks to an inactive loopback
test endpoint, and uses an offline fictional backend. It reads no real
terminal session, Jira account, private configuration, or credentials, and
closes only its own app and core afterward.

Before capturing, the rig creates a live temporary terminal containing only
fictional output. It exercises screen-only discovery and explicit available
history, native asynchronous loading, same-origin URL lookup, freshness,
Follow synchronization, Options/Help return with the same filter and selection,
reader focus, shared field/preference reloads, stale UI
save protection, malformed-file recovery, native agent commands, cache
clear/reconnect, and configuration invalidation.
It also checks Clear without depending on a native input-change event,
hyphenated title lookup and reading one unseen issue while keeping Paused/query.
Focus, pointer activation and clipboard behavior require separate interaction QA.
It also delays a fictional metadata request and an earlier issue request by
two seconds, verifies that the latest selection finishes first, and measures
selection latency. Cached selection must start no request. These measurements
include the real native bridge and offline backend, not a live Jira service.

It then renders the explicit fictional demo beside a labeled fictional
transcript. Outputs are the repository-root `preview.png` plus `app-light.png`,
`app-narrow.png`, `app-reader.png`, `app-options.png`, `app-help.png`,
`app-browse.png`, and `app-short.png` in this
directory. The 300px captures exercise compact controls and wrapping;
`app-reader.png` shows the list collapsed for reading. Options is captured at
300px and Help at 420px; both show the explicit ← Issues return.
Help shows the collapsed topic list; explanations open one at a time.
`app-browse.png` shows four complete issue rows at 300px; `app-short.png`
shows the same browsing flow bounded to a 300×400px panel. The issue actions
and last successful fetch time remain above the scrolling body. Demo fetch
time is fixed for reproducibility. Two extra acceptance frames (excluded
selection and direct lookup) stay in the temporary fixture directory and are
not published. The eight captures received visual and PNG
metadata review; see the dated verification record.
Add `--app-review` to keep the isolated window open for interaction review;
the offline lab offers 300px dark, 420px light, 300×400px, long-list, no-terminal,
setup, demo, and a stock toolbar layout with the documented Jira Peek toggle.
The toolbar layout also loads the example shortcut for hide/reopen checks.
Its fictional backend can succeed, delay six seconds,
or fail. Discover a new issue adds a fictional key to the rig's terminal
without sending terminal input. Use these controls to check Browse retention,
validation, keyboard navigation, refresh recovery, and copy feedback.
The resize controls change the same panel between 300px, 360px and 420px without
remounting it, so query, selection, and reading position can be checked.
Load next known title alternates one-line/two-line fictional summaries and
delays the uncached issue response for six seconds. Its body includes a labeled
table and twenty reading checkpoints. The clipboard receiver is a native input
for pasting copied fictional URLs. Shared fixture state records the current
selection, loaded state, focus caption and native Tab timestamp for measurement.
Prepare unread review creates twelve fictional issues, with four matching
`Viewport`, and clears the fixture terminal's visible output. Discover a new
issue then exercises the thirteenth, unrelated result through terminal scanning.
The receiver also accepts a local fixture JSON envelope with a `keys` array
and optional `reset` flag for repeatable arrival bursts. Shared state records
the total and unread keys so counts can be compared before and after reading.
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
