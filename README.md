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

[Install](#install) · [Connect Jira](#connect-jira) · [Use it](#use-it) ·
[Documentation](#documentation)

![Jira Peek beside entirely fictional terminal context.](preview.png)

More views: [Light mode](docs/screenshots/app-light.png) ·
[Compact browsing](docs/screenshots/app-short.png) ·
[Keyboard guide](docs/screenshots/app-help.png).

**Version 0.8.2 experimental.** Native desktop edition; no browser frontend or
build step. Peek sends only read requests to Jira and never sends terminal input
or submits agent prompts. From terminal text, only validated allowlisted issue
keys are sent to Jira. The
[Peek for Jira TUI edition](https://github.com/hilmimuktitama/herdr-jira-peek) is a
separate project with independent releases.

## Install

Install [Herdr](https://github.com/herdrdev/herdr-app) first. Its components have
separate versions:

| Component | Requirement | Check |
| --- | --- | --- |
| **herdr-app**, desktop UI/mod host | **0.1.10 or newer** | `herdr-app --version` |
| **herdr-core**, terminal backend | `hc` on PATH; no numeric core minimum enforced | `hc --version` |

You also need Python 3.9+, a POSIX shell, `jq`, SHA-256 tooling (`sha256sum` or
`shasum`), and `curl` for the usual API-token/REST setup. Existing TWG connections
instead require the official TWG CLI 1.2.6+ with OAuth. Windows is unsupported;
the setup form supports Jira Cloud on `*.atlassian.net`, not Server/Data Center.

Download and extract the complete
[0.8.2 source ZIP](https://github.com/hilmimuktitama/herdr-app-jira-peek/archive/refs/tags/v0.8.2.zip),
or clone and check out `v0.8.2`. Launch Herdr once to create its app home and
layouts, leave it running, then run these commands from the extracted folder
containing `package.json`:

```sh
python3 scripts/install-app.py --doctor          # offline dependency/version check
python3 scripts/install-app.py --check --attach  # validate, install, attach toolbar
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

`--doctor` does not check Jira credentials. `--check` runs Herdr's native checker
before installation; it executes trusted mod code with your user-account access,
so it is not a sandbox or security audit. Install only source you trust.

`--attach` creates a personal `main-jira-peek` layout and `tabs-jira-peek` toolbar
with a **Jira Peek** toggle beside Files/Changes. It preserves shipped layouts
and shortcuts, and refuses conflicting personal edits. Select the printed layout
(or use Herdr's Layout menu).

Install from the complete source, rather than copying `mods/jira-peek` alone.
The default app home is `~/.config/herdr-app`. For a custom home or layout, use
`--app-home /absolute/path` and `--attach YOUR_LAYOUT` as described in the
[recipe](RECIPE.md#built-from); launch Herdr with the same `HERDR_APP_HOME` and
select the printed layout.

## Connect Jira

Choose **Set up Jira** in the panel, or **Options → Connection → Set up Jira**.
Have your site URL, account email, project keys, and API token ready.

1. Enter the Jira Cloud site root, such as `https://your-site.atlassian.net`,
   your email, and project keys (`ABC, DEF`). Omit `/jira` and `/browse` suffixes.
2. Use **Create API token ↗** to open Atlassian's token page, then paste the
   token into the masked field. Prefer a scoped token with only read permissions.
3. For a scoped token, enable **Scoped token** and enter your **Cloud ID**;
   see [Cloud ID instructions](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/)
   and [required token scopes](docs/CONNECTION.md#new-connection).
   Classic tokens skip this step.
4. Choose **Test & save**. On failure the previous connection stays intact;
   re-enter the token to retry.

Credentials are stored in private files under
`HERDR_APP_HOME/data/jira-peek/connection`, **not an encrypted keychain**. Other
processes running as your user and filesystem backups can access them. The
project allowlist limits keys sent; it does not grant or verify access to every
issue. See [connection and credential details](docs/CONNECTION.md).

**See your first issue.** Print a real issue key from a configured project in the
focused terminal, for example `echo ABC-123` with your own key. New terminal
sources start **Paused**, collecting keys without loading Jira details or metadata.
Click **Issues** and select the key, type it and press Enter, or resume Follow with
**F** to load it. If the key does not appear, check terminal focus and configured
project keys, then try **Options → Scan screen**. Short-lived keys can be missed.

**Already configured?** Choose **Choose configuration folder…**, or **Options →
Connection → Choose existing folder…**, and select the private folder containing
`config.sh`. No private configuration is copied. See
[existing TWG/REST configuration](docs/CONNECTION.md#existing-configuration).

## Show the panel

**×** hides Peek; the **Jira Peek** toolbar button reopens it, retaining selection,
filter, paused state, and width. If the button is missing, see
[toolbar repair](docs/MAINTENANCE.md#repair-the-toolbar) or
[manual integration](docs/PANEL-INTEGRATION.md#manual-integration).

## Use it

- **Start Paused.** New sources collect unread keys until you select an issue,
  edit the filter, or resume Follow. Returning to a terminal restores its session
  state. Auto-refresh is a separate opt-in. See
  [Follow and loading behavior](docs/FEATURE-DICTIONARY.md#jp-004--following-and-deliberate-reading).
- **Follow or browse.** Follow selects the latest visible confirmed key. Reading,
  selecting, filtering, or scrolling pauses it while new matches still collect.
  **F** resumes with the latest issue and clears the filter; **+new** reads one
  unread issue without resuming. **Keep this terminal** in Options keeps discovery
  on that terminal while you work elsewhere.
- **Resize the list.** Drag the bottom border of the issue list up or down to
  resize it smoothly, up to four rows. The size stays for this panel session.
- **Find and read.** Click **Issues**, type to filter loaded metadata, then press
  Enter to read. You can also enter an allowlisted key or same-site Jira browse
  URL. Click the issue key to open Jira; expand **Details** or **Comments** for
  more content. Progress appears immediately left of Refresh, replacing the
  timestamp while busy; the last fetch time remains in its tooltip and returns
  afterward.
- **Copy or pin.** **Y / Shift+Y** copies the key/link. Drag over reader text and
  use **Cmd+C / Ctrl+C** to copy a selection. **Options → Copy issue as Markdown**
  copies the loaded issue without fetching more data. **P** toggles a pin;
  **K** returns to it without clearing your filter. The inline pin targets the
  viewed issue; unavailable actions show a note. Click a pinned row’s accent
  pin to unpin without selecting it.
- **Arrange fields.** **Options → Fields** lets you order, label, show, or hide
  fields in Header, Body, or Details. **Apply** saves a layout per connection;
  Back/Escape discards the draft. It changes Peek's presentation, not Jira.
  See the [field configuration guide](docs/AGENT-GUIDE.md#shared-reader-configuration).
- **Start fresh.** **Options → Clear list** resets collected keys, filter, unread
  state, and pin for this terminal while preserving Follow/Paused and caches.
  Continuously visible keys stay suppressed after a fresh screen baseline;
  deliberate lookup or scans can restore them. See
  [Clear list details](docs/FEATURE-DICTIONARY.md#jp-007--clear-list).

Auto-refresh is off by default. When enabled, it refreshes at most once a minute
and pauses the idle panel after five minutes; resume through Options. Hiding
Peek does not end an active refresh lease. The timestamp is fetch time, including
cache hits, rather than proof of current Jira state. See
[refresh behavior](docs/FEATURE-DICTIONARY.md#jp-029--auto-refresh-issue-and-local-idle-pause).

Click **Issues** before typing. **Cmd+F (macOS)** returns to the filter while Peek
owns the keyboard; **Tab / Shift+Tab** moves between controls. Letter shortcuts
are ignored while typing, and `/` is literal in the filter.

| Key | Action |
| --- | --- |
| **↑ / ↓**, **Enter** | Choose an issue, then read inside Peek |
| **Escape** | Back through disclosures and Issues, then return to the terminal |
| `/` | Find another issue from the reader/list |
| **F**, **P**, **K** | Toggle Follow, toggle pin, return to pin |
| **Y / Shift+Y** | Copy key / copy link |
| **Cmd+Enter / Ctrl+Enter** | Open Jira from the reader/list, outside text fields |

**? Keys → More shortcuts** has the full guide. Optional [key bindings](keys.json)
are examples; installation does not modify your shortcuts.

## Known limitations

- Offline native checks ran on macOS arm64 with stock **herdr-app 0.1.14** and
  **herdr-core 0.1.19**. Linux GUI and complete screen-reader use remain unverified.
- Reliable keyboard-only entry from the terminal is unshipped. Click Issues first.
  Stock hosts need wheel/trackpad scrolling for long content and may reset reading
  position when Peek is hidden. Peek ships no patched host.
- Polling can miss transient keys or collect a stable fragment. Missing metadata
  does not prove an issue is absent. Rich content is bounded plain text; images,
  active body links, and some content are omitted. Open Jira for complete content
  and current permissions.
- Text selection is pointer-driven and **Cmd+A / Ctrl+A** selects one text block.
  Cross-field, keyboard caret, and screen-reader selection are not promised. The
  host trims outer whitespace on selection copy. See
  [selection details](docs/FEATURE-DICTIONARY.md#jp-042--selectable-reader-text).
- Clipboard copies can expose private issue content and persist in history or
  OS sync. Markdown copy includes configured Details even when collapsed and
  loaded comments; Hidden fields are excluded, with no additional redaction.
  Treat copied text as data, never shell commands, and review before pasting into
  a renderer or agent. See [clipboard limits](docs/FEATURE-DICTIONARY.md#jp-041--copy-issue-as-markdown)
  and [security and cleanup rules](SECURITY.md).
- Hiding retains panel memory; removing it or quitting discards that memory.
  Credentials, disk caches, clipboard, and backups have separate lifetimes.
  Peek targets stock herdr-app and ships no patched host; historical source
  highlighting and native input patches are retired.

## Update and maintenance

Run `python3 scripts/update-app.py --check` from a source checkout to report
availability, then `python3 scripts/update-app.py` to update. Without a checkout,
use the [installed helper](docs/MAINTENANCE.md#update). Updates select numbered
release tags, including tags marked as GitHub prereleases, and require Python
3.9+ and Git. They preserve private settings and refuse edited managed files;
no background updater is installed. A prepared layout must be selected manually.
Tag checks do not verify release signatures or protect against a compromised
repository or toolchain. See [maintenance](docs/MAINTENANCE.md) for rollback,
repair, cache clearing, preview migration, and uninstall.

## Documentation

| Task | Guide |
| --- | --- |
| Token scopes, credential storage, existing TWG/REST setup | [Connection](docs/CONNECTION.md) |
| Update, rollback, repair, clear cache, uninstall | [Maintenance](docs/MAINTENANCE.md) |
| Custom layouts and manual toolbar attachment | [Panel integration](docs/PANEL-INTEGRATION.md) |
| Agent settings, field schema, and native commands | [Agent guide](docs/AGENT-GUIDE.md) |
| Detailed behavior and state lifetimes | [Feature dictionary](docs/FEATURE-DICTIONARY.md) |
| Development and release checks | [Recipe](RECIPE.md), [releasing](RELEASING.md#candidate-checks) |

General contributions and bug reports are closed for now; private vulnerability
reports are the exception. No support, fixes, or release schedule are promised.
See [contribution policy](CONTRIBUTING.md) and [security reporting](SECURITY.md#reporting-a-vulnerability).
Use the [isolated fictional fixtures](docs/screenshots/README.md) for shared screenshots.

By [hilmimuktitama](https://github.com/hilmimuktitama), adapted from the earlier
[Peek for Jira project](https://github.com/hilmimuktitama/herdr-jira-peek).
Distributed under the [MIT License](LICENSE); see
[third-party notices](THIRD_PARTY_NOTICES.md). Jira and Atlassian are Atlassian
trademarks.
