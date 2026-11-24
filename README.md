# Jira Peek for herdr-app

**Jira beside your agents.** A native panel for
[Herdr](https://github.com/herdrdev/herdr-app), the desktop terminal workspace.
It watches your focused terminal for Jira issue keys and shows the matching issue
beside it.

> **Unofficial community project, unaffiliated with Atlassian.** Not an Atlassian
> product or endorsed, sponsored, supported, or authorized by Atlassian.
>
> **AI-assisted, experimental software — use with caution.** Provided as-is, without warranty, under
> the [MIT License](LICENSE). Review the code and [limitations](#known-limitations),
> test in an isolated Herdr app home, back up settings, and grant only the Jira
> access you need. Read the [security policy](SECURITY.md) before connecting.

![Jira Peek beside entirely fictional terminal context.](preview.png)

More views: [Light mode](docs/screenshots/app-light.png) · [Compact browsing](docs/screenshots/app-short.png) ·
[Keyboard guide](docs/screenshots/app-help.png).

**Version 0.17.0 experimental.** Native desktop edition: JavaScript/GPUI panel,
Rust runtime, no browser frontend. Peek sends only read requests to Jira and never
sends terminal input or submits agent prompts; only validated allowlisted issue
keys reach Jira. The [Peek for Jira TUI edition](https://github.com/hilmimuktitama/herdr-jira-peek)
is a separate project with independent releases.

## Install

Install [Herdr](https://github.com/herdrdev/herdr-app) first. Its components have
separate versions:

| Component | Requirement | Check |
| --- | --- | --- |
| **herdr-app**, desktop UI/mod host | **0.1.10 or newer** | `herdr-app --version` |
| **herdr-core**, terminal backend | `hc` on PATH; no numeric core minimum enforced | `hc --version` |

Download and extract the
[0.17.0 source ZIP](https://github.com/hilmimuktitama/herdr-app-jira-peek/archive/refs/tags/v0.17.0.zip),
or clone and check out `v0.17.0`. From the same
[release](https://github.com/hilmimuktitama/herdr-app-jira-peek/releases/tag/v0.17.0),
put your platform's executable, manifest and `-NOTICES.txt` into
`.release-runtime` (see the
[platform filenames](rust-backend/README.md#installation-and-distribution)).
Launch Herdr once, then run from the folder with `package.json`:

```sh
# Use the matching platform filename on other systems.
asset=jira-peek-bridge-macos-aarch64
chmod +x ".release-runtime/$asset"
".release-runtime/$asset" manage doctor
".release-runtime/$asset" manage install --source-root "$PWD" --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

`--attach` adds a **Jira Peek** toggle to a personal `main-jira-peek` layout.
`--check` runs trusted mod code with your user access, not a sandbox. Download
only trusted release assets. Other platforms, custom app homes, source builds and
older installs: [install details](docs/USAGE.md#install-details).

## Connect Jira

Choose **Set up Jira** in the panel or under **Options → Connection**; have your
site URL, email, project keys and API token ready.

1. Enter the Jira Cloud site root, such as `https://your-site.atlassian.net`, your
   email, and project keys (`ABC, DEF`); omit `/jira` and `/browse` suffixes.
2. Use **Create API token ↗**, then paste a read-only scoped token.
3. For a scoped token, enable **Scoped token** and enter your **Cloud ID**; classic
   tokens skip this step.
4. Choose **Test & save**. On failure the previous connection stays intact.

Credentials live in private files, **not an encrypted keychain**, under
`HERDR_APP_HOME/data/jira-peek/connection` ([connection details](docs/CONNECTION.md)).

## Show the panel

**×** hides Peek; the **Jira Peek** toolbar button reopens it with selection,
filter, paused state and width intact. Missing button: [repair](docs/MAINTENANCE.md#repair-the-toolbar)
or [manual integration](docs/PANEL-INTEGRATION.md#manual-integration).

## Use it

- **Follow.** Peek follows the focused terminal and selects the latest confirmed
  key; **F** resumes a Paused source. [Details](docs/USAGE.md#follow-and-browse).
- **List and read.** Click **Issues** to filter metadata, then press Enter to read;
  keys and browse URLs work too. [Details](docs/USAGE.md#find-and-read).
- **Preview a terminal link.** On herdr-app 0.1.17+, opt in to Cmd/Ctrl-click a
  Jira browse URL and read it in a separate Peek dialog.
  [Terminal link walkthrough](docs/USAGE.md#preview-a-jira-link-from-the-terminal).
- **Fit the dock.** Peek picks **Stack**, **Split**, **Card** or **Guard** from the
  dock size. [Presentation modes](docs/AGENT-GUIDE.md#presentation-modes).
- **Keyboard.** **? Keys** shows the compact loop and **More shortcuts** the rest;
  [key bindings](keys.json) stay opt-in. [Details](docs/USAGE.md#keyboard).
- **Pin and copy.** **P** pins the viewed issue, **K** returns to it, and
  **Y / Shift+Y** copies the key or link. [Details](docs/USAGE.md#copy-or-pin).
- **Arrange fields.** **Options → Fields** orders, labels, shows or hides fields
  per connection. [Details](docs/USAGE.md#arrange-fields).

## Known limitations

- Offline native checks ran on macOS arm64 with stock **herdr-app 0.1.16** and
  **herdr-core 0.1.21**; Linux GUI and screen-reader use are unverified.
- Keyboard-only entry needs **herdr-app 0.1.12 or newer** and the host's pane
  navigation; unit tests do not prove native keyboard behavior.
- Polling can miss transient keys, and missing metadata does not prove an issue is
  absent. Rich content is bounded plain text; open Jira for the rest.
- Text selection is pointer-driven (**Cmd+A / Ctrl+A** selects one block), and
  clipboard copies can expose private issue content and persist in history or OS
  sync. Treat copied text as data, never shell commands.
- Peek targets stock herdr-app and ships no patched host; hiding retains panel
  memory, while removing or quitting discards it.

[Full list of known limitations](docs/USAGE.md#known-limitations-full-list).

## Documentation

| Task | Guide |
| --- | --- |
| Usage and keyboard details | [Usage](docs/USAGE.md) |
| Token scopes, credential storage, existing TWG/REST setup | [Connection](docs/CONNECTION.md) |
| Update, rollback, repair, clear cache, uninstall | [Maintenance](docs/MAINTENANCE.md) |
| Custom layouts and manual toolbar attachment | [Panel integration](docs/PANEL-INTEGRATION.md) |
| Agent settings, field schema, and native commands | [Agent guide](docs/AGENT-GUIDE.md) |
| Detailed behavior and state lifetimes | [Feature dictionary](docs/FEATURE-DICTIONARY.md) |
| Rust runtime and local benchmarks | [Runtime guide](rust-backend/README.md), [benchmark harness](benchmarks/README.md) |
| Development and release checks | [Recipe](RECIPE.md), [releasing](RELEASING.md#candidate-checks) |

General contributions and bug reports are closed; private vulnerability reports
are the exception ([contribution policy](CONTRIBUTING.md)). By
[hilmimuktitama](https://github.com/hilmimuktitama), adapted from the
[Peek for Jira project](https://github.com/hilmimuktitama/herdr-jira-peek).
[MIT License](LICENSE); [third-party notices](THIRD_PARTY_NOTICES.md). Jira and
Atlassian are Atlassian trademarks.
