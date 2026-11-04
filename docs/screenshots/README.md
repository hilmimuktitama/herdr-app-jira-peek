# Fictional screenshots and native checks

Only entirely fictional issues, identities, tenant URLs, credentials and
terminal output may appear in public captures. Never substitute real records,
even with identifiers renamed or blurred. Keep temporary QA evidence outside
the published tree.

## Native panel

```sh
python3 docs/screenshots/capture.py --app
```

Requires `herdr-app`, `hc`, `jq`, Python 3 and native GUI access. The rig creates
a separate temporary app home, core session/socket and XDG directories. It
disables telemetry, directs host release checks to an inactive loopback endpoint,
and uses an offline fictional backend. It reads no live Jira account or existing
terminal and closes only the app/core it created.

The rig exercises screen/history discovery, lookup, filters, unread navigation,
fields/preferences, asynchronous request priority, cache clearing and reconnects.
It then renders a labeled fictional transcript beside the panel. Pointer,
keyboard and clipboard behavior require separate native interaction checks.

Outputs include the root [preview](../../preview.png),
[light](app-light.png), [narrow](app-narrow.png), [reader](app-reader.png),
[Options](app-options.png), [Help](app-help.png), [browsing](app-browse.png),
and [short panel](app-short.png). Use `--output-dir /absolute/path/to/frames`
for temporary evidence rather than replacing published captures.

Add `--app-review` to retain the isolated window for interaction checks, or
`--app-binary /absolute/path/to/herdr-app` to select a separate host. The lab
includes narrow/light/short layouts, loading/failure controls, unread arrivals,
a clipboard receiver and a fictional setup transport. Setup values are
`https://fictional-peek.atlassian.net`, `reader@example.test`, project `ABC`, and
a made-up token. Never replace them with real credentials.

Identify the isolated app before automating input. Use a distinct app name and
bundle identifier when needed; never target an ambiguous window or the everyday
app. Press Enter in the fixture process to close review mode. Inspect every
published image visually and inspect its PNG metadata before committing.

## Selected-key highlights

With the separately built optional renderer extension:

```sh
python3 docs/screenshots/capture.py --app-highlight --app-binary "$PWD/.local/bin/herdr-app-peek"
```

The fixture captures dark/light, changed selection, disabled, hidden and
restored states in `app-highlight-*.png`. It checks that highlighting does not
change terminal text. Visually verify token boundaries and lifecycle cleanup;
command success alone does not establish correct rendering. No Jira transport
is used. Add `--app-review` to retain its isolated window for interaction checks.
