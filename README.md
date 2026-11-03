# Jira Peek for herdr-app

Jira beside your agents. A native panel attached to the right side of your
existing Herdr window. It discovers issue keys in your focused terminal and
keeps the details within reach.

**Experimental 0.1.0 — private preview.** Input fixes are verified on patched
[herdr-app](https://herdr.dev/guide/) **0.1.12 on macOS arm64**. Stock 0.1.12
still has the terminal shortcut race. See the [current retest and limits](docs/VERIFICATION.md#reader-controls-and-0112-retest).
Linux GUI and full screen-reader use remain unverified.
The [Herdr TUI edition](https://github.com/hilmimuktitama/herdr-jira-peek) remains
separate; its releases are independent of this repository.
This is a GPUI mod: no browser, frontend build, fzf or less is needed.
Highlighting keys in the source terminal uses an optional local renderer
extension; ordinary Peek features work with the stock app.

![Jira Peek's compact native reader beside entirely fictional terminal context.](preview.png)

For ongoing development, read the [handoff](docs/HANDOFF.md),
[verification record](docs/VERIFICATION.md), and [native UX review](docs/UX-REVIEW.md).

## Install

Herdr has two separately versioned components:

| Component | Role | Jira Peek requirement | Check version |
| --- | --- | --- | --- |
| `herdr-app` | Desktop UI that loads this mod | **0.1.10 or newer** | `herdr-app --version` |
| `herdr-core` (`hc`) | Terminal backend | `hc` on PATH; no numeric core minimum is currently enforced | `hc --version` |

Keep the component name with every version. The app requirement is **0.1.10**,
not **1.10.0**. A core version or the older `herdr` TUI version cannot satisfy
the desktop app requirement. The doctor reports the two component versions
separately; executable presence alone does not prove full runtime compatibility.

For users with access to this private repository, download and extract the
complete source ZIP, or clone the repository. Open Herdr once before attaching
the panel. Run these commands from the extracted folder (beside `package.json`):

```sh
python3 scripts/install-app.py --doctor
python3 scripts/install-app.py --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

Do not copy `mods/jira-peek` alone. The installer assembles its required
runtime from the root `scripts/` files; the source mod folder is not a standalone install bundle. Read the [recipe](RECIPE.md) when asking an
agent to adapt the mod.

`--doctor` is an offline capability check: executable presence and separate
app/core versions, not authentication or Jira connectivity. Add `--json` for machine
readable output. `--check` checks capabilities and validates a staged mod with
Herdr before replacing an installation.
The report lists Python 3 and `curl` readiness for token setup separately from
the tools needed by an existing TWG connection.

The installer adds `mods/jira-peek` under `~/.config/herdr-app` (or
`HERDR_APP_HOME`). `--attach` creates a personal `main-jira-peek` layout and a
`tabs-jira-peek` toolbar with the **Jira Peek** button beside Files/Changes.
Select that layout using the printed command or Herdr's Layout menu.
The command printed by the installer also works with a custom app home.
The installer bundles the small
Jira runtime, so moving the checkout afterward does not break the panel.
It preserves shipped layouts and existing keyboard shortcuts.

You need Python 3 for installation and connection setup; at runtime, a POSIX shell, `jq`, SHA-256
tooling, and either the official TWG CLI 1.2.6+ with OAuth, or `curl` and a
private netrc for the existing REST backend. Windows is not supported by this
edition's shell adapter.

## Show the panel

If installation succeeds but Jira Peek is absent, add it explicitly to a
personal layout. From the source ZIP or checkout, run:

```sh
python3 scripts/install-app.py --update --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

Both the panel and its toolbar button are included. **×** hides the panel;
the **Jira Peek** toolbar button opens it again. Updates after this only need
`--update --check`. No shortcut is installed automatically.

To start from another layout with the stock tabs toolbar, use
`--attach YOUR_LAYOUT`; select `YOUR_LAYOUT-jira-peek` afterward. The installer
preserves existing files and refuses conflicting personal edits or unsupported
toolbars. For a heavily customized layout, use the manual attachment below
and the [toolbar integration guide](docs/PANEL-INTEGRATION.md).

1. In Herdr's command palette (**Cmd+Shift+P** on macOS), choose
   **Duplicate layout**. This selects a personal copy, such as `main-copy`,
   while preserving the original layout and running terminals.
2. Open that copy under `HERDR_APP_HOME/layouts/` (normally
   `~/.config/herdr-app/layouts/main-copy.json`). In the default Herdr layout,
   append this block to the `children` of the `work-body` row:

   ```json
   {
     "id": "jira-peek",
     "type": "block",
     "content": { "mod": "jira-peek" },
     "size": { "px": 360 },
     "min": 300,
     "max": 640
   }
   ```

3. Save the personal layout. Herdr loads the panel beside the terminal in the
   same window. Choose **Set up Jira**. If space is tight, toggle **Files** or
   **Changes** off from the tab bar.

Add only one Jira Peek block, and edit the personal copy rather than Herdr's
shipped `main.json`. For other layouts, place the block in the row beside the
terminal area. Keep using the personal layout to retain the attached panel.

The main issue view's header **×** hides the panel. Options and Help use
**← Issues** to return to the issue view. Add the persistent **Jira Peek** toolbar
toggle with `--attach` or the [personal tabs integration](docs/PANEL-INTEGRATION.md).
The optional [native input patch](native/APP-INPUT.md) adds safe shortcut entry,
keyboard scrolling and reading-position restoration after hiding. With that
patched herdr-app 0.1.12, merge [keys.json](keys.json): **Ctrl+Shift+J** opens
search immediately, including from a hidden panel. Its suffix must match the
attached block ID. No toolbar keyboard handler is needed. Stock 0.1.11/0.1.12 retains
width, selection, filter and Paused state, but still has the three
[host input gaps](docs/HOST-INPUT-GAPS.md).

## Connect Jira

Peek extracts issue keys from terminal output locally and sends only validated,
allowlisted keys to the configured Jira backend. Inline setup saves a private
local credential file; issue caches are also local. See the
[security policy](SECURITY.md#native-herdr-app-edition) for permissions,
retention and cleanup limits.

Choose **Set up Jira** in the panel, or **Options → Connection →
Set up Jira** when already connected. The form stays inside the attached panel.

1. Enter your Jira Cloud site URL, account email, and project keys, such as
   `ABC, DEF`.
2. Choose **Create API token** to open Atlassian's token page, then paste the
   token into the masked **API token** field.
3. For a token with scopes, turn on **Scoped token** and enter your **Cloud ID**.
4. Choose **Test & save**. Jira Peek checks the account before switching the
   connection. A failed check preserves the previous connection; re-enter the
   token to retry. Cancel discards the form before saving begins.

The form supports Jira Cloud sites under `atlassian.net`. Scoped tokens use
Atlassian's API gateway; see [Atlassian's token and Cloud ID instructions](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).
The read-only account check uses `/rest/api/3/myself`, which needs account-read
permission (`read:jira-user` for classic scopes). Issue access needs its own
read permissions, usually `read:jira-work` for classic scopes. For granular
scopes, use the [current-user API reference](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-myself/#api-rest-api-3-myself-get)
and the issue API reference. A successful account check does not establish
access to every project or issue.

Setup requires `curl` and Python 3. It stores a private configuration and
mode-600 credential file under `HERDR_APP_HOME/data/jira-peek/connection`,
outside this repository. The token is never prefilled, placed in command
arguments, or stored in the mod's localStorage. It clears from the form after
submission or cancellation. Saved credentials are local files protected by
filesystem permissions, not an encrypted keychain. Reopen setup to replace a
token; each save requires a fresh token.

To keep using an existing TWG or REST configuration, choose **Choose existing
folder…** in Connection settings, or **Choose configuration folder…** on the
initial screen, then select the folder containing your private `config.sh`.
You can also supply its location during installation:

```sh
python3 scripts/install-app.py --check --config-dir /absolute/path/to/private/config
```

The installer copies no private configuration or credentials into the mod. The chosen directory
path is kept locally. Issue caches use a separate private directory under
`HERDR_APP_HOME/data/jira-peek/state`.

For manual configuration, the installer creates
`data/jira-peek/config/config.example.sh`. Copy it to `config.sh` in the same
private directory, set your site and project allowlist, and configure the backend described below.
Choose that directory in the panel. For TWG, set `JIRA_BACKEND='twg'`,
`JIRA_BASE`, `JIRA_SITE`, and `JIRA_PROJECTS`, then authenticate separately with
`twg setup`. For REST, prefer the inline setup form; an existing configuration
uses `JIRA_BACKEND='rest'` and `JIRA_NETRC_FILE` pointing to an absolute private
mode-600 netrc containing the site's account email and API token. Scoped tokens
also require `JIRA_CLOUD_ID` and credentials for `api.atlassian.com`. Keep these
files outside the checkout. See [config.example.sh](config.example.sh).
Setup does not import credentials from
another app. **Reconnect** reloads the selected backend configuration.

## Use it

Run your repository's normal Jira tasks in a Herdr terminal. Peek discovers
issue keys from the agent's visible output and reads those issues alongside
the work. Use your repository's approved Jira tools for the activity itself.

- **Follow the work.** Focus a terminal and allowlisted keys appear. Follow
  selects the latest visible key, including one the agent returns to later.
  Newly discovered keys are added at the top of the list. Reads use
  `hc read <explicit-address> --lines 0`, never terminal input,
  scrolling, or a focus command. **Options → Read history** explicitly reads up to 200 available
  host history lines without scrolling or input; alternate-screen history may
  be absent. Automatic reads remain screen only. Machine-qualified addresses
  keep remote and local terminals separate; Jira authentication always runs locally.
- **Settle in to read.** Selecting an issue, typing a filter, or scrolling the
  reader enters Browse. New keys arrive without changing your selection,
  query, or scroll position. Opening Issues or expanding content also pauses
  Follow. The **+new** badge opens the newest unread issue, acknowledges only
  that issue, and keeps Paused and your filter. Click **Paused** to resume following.
- **Pin a source.** **Options → Pin source** keeps this panel on its terminal while you work in
  other tabs. Unpin source follows your current terminal again. Each source remembers
  its own selection and filter while the panel is open. **Pinned source** indicates
  this exception; source identity is available in its tooltip and the **Pin source** tooltip.
- **Find an issue.** Choose **Issues** and start typing; the filter is focused
  immediately and its previous text is selected for replacement. Click rows to
  compare issues without closing the list or moving the clicked row. The filter's
  **×** clears it in one click while keeping your selection. If the filter
  excludes the selected issue, its reader and actions are covered until you
  select a result or explicitly choose **Back to issue**.
  Search keys, summaries, statuses, and configured picker
  fields loaded so far. Enter an allowed issue key or a `/browse/KEY` URL on your
  configured Jira origin and press Enter, even without a source terminal.
  An allowed key outside the results also offers a clickable **Look up KEY**
  action. Enter accepts matching title text, including hyphenated story labels.
  Keys outside your project allowlist and URLs from another origin show a
  validation message beside search.
- **Read and act.** The default layout opens on the current issue: key, status, full title,
  and the complete loaded description, immediately readable in the scrollable
  reader. The last successful fetch time is always visible beside Refresh;
  **Details** reveals secondary fields and **Comments** opens comments.
  With an API-token connection, comments load separately when opened, so a slow
  discussion cannot delay the description. Peek requests one page of up to 100
  recent comments and shows the total when more exist. Comment failures have
  their own Retry action and keep the issue readable.
  Compact header values have text previews in tooltips. Click the issue key to
  copy it; **Open in Jira**, **Copy link**, and **Refresh** stay beside it above
  the scrolling reader. Copy confirmation appears on the control without
  resizing the reader. The copy and refresh actions also remain in **Options**.
  Tab focus shows each icon's name and shortcut in the reserved footer. Readable
  body text has no tooltip. Tables with column headers repeat those labels beside
  each value so narrow wrapping keeps the comparison understandable.
  Manual Refresh also retries failed summary lookups for the current source.
  **Enter** or **Back to issue** expands the selected issue into the compact reader and hides
  browsing without resuming Follow. These actions never edit Jira or submit
  prompts to agents.

## Arrange your fields

Open **Options → Fields** to configure the reader. One layout is saved locally
per connection (configuration folder and Jira site), shared by that connection's
projects and issue types.

- Choose **Header**, **Body**, **Details**, or **Hidden** for each field.
  Header pins compact values above the reader; Body shows full text; Details
  groups secondary fields behind its disclosure.
- Edit display labels and use **↑ / ↓** to order fields within a section.
- Add standard IDs such as `priority`, `labels`, or `duedate`, or a Jira custom
  field ID such as `customfield_10016`. Custom IDs must come from your Jira
  configuration; Peek does not discover your site's field catalog.
- Empty or unavailable values are omitted by default. **Show empty fields**
  displays a dash instead. Numbers such as zero remain visible.
- **Apply** saves and rebuilds the reader. **Back** or **Escape** discards the
  draft. **Reset to configured fields** restores the connection's
  `READER_FIELDS` and `FIELD_LABELS` defaults in the draft; apply to save it.

The issue key and **Open in Jira** stay available. Comments can go in Body or
Details, or be hidden. Up to 32 fields are supported. Adding/removing visible
fields reloads issue details; placement and label changes reuse loaded data.
These choices affect only Peek's presentation, not Jira fields or screens.

Your agent can configure the same layout. Ask it to read the installed
mod guide, normally `~/.config/herdr-app/mods/jira-peek/AGENTS.md`,
then edit `data/jira-peek/fields.json` under your Herdr app home.
**Copy config path** in Fields provides the exact path. The file has a
versioned [JSON schema](mods/jira-peek/fields.schema.json) and one entry per
connection; native panels reload edits automatically. Invalid edits keep the
last valid layout, and stale UI drafts cannot overwrite newer file contents.
Existing UI layouts migrate on connection; managed updates preserve this file.
The same file's root `preferences` object stores `autoRefresh` (default false)
and `highlightSource` (default true). These booleans are shared by native
panels; Options edits them too. The offline demo keeps separate preferences.

The installed guide maps every supported setting: backend and project scope,
scan interval, cache lifetime, metadata preload, connection selection, host
fonts/theme, panel placement and width, and shortcuts. It also documents native
actions such as `herdr-app do jira-peek.reconnect`, `jira-peek.pause`,
`jira-peek.resume` and `jira-peek.fields`. Agents configure the existing files
and commands without editing managed source.

For example: “Put status and priority in the header, acceptance criteria before
the description, and hide comments.” See the [agent guide](docs/AGENT-GUIDE.md)
for the format and [agent workflow research](docs/AGENT-WORKFLOWS.md) for useful
next capabilities and their references.

## Highlight the selected key

With the [optional desktop renderer extension](native/APP-HIGHLIGHT.md),
Peek highlights matching occurrences of the selected Jira key in its source
terminal. Selection changes update the mark immediately, including keyboard
navigation and Following. Paused keeps the mark on the issue you are reading;
Pin source keeps it on that terminal. The mark does not move focus, scroll the
terminal or change terminal text.

Highlighting starts on when supported. Use **Options → Highlight source** to
turn it off. Without the renderer extension, the option shows **Unsupported**.
A key outside the visible working area, or a manual
lookup without a source terminal, has no visible match.

## Keyboard first

With the [native input patch](native/APP-INPUT.md) and optional binding,
**Ctrl+Shift+J** focuses search synchronously, revealing the attached panel if
hidden. The older toolbar binding on stock herdr-app 0.1.11/0.1.12 can send
immediate typing or paste to the terminal. Stock users should use **Issues**
or Tab to reach the filter; see the [host input gap](docs/HOST-INPUT-GAPS.md).
Once the filter has focus, preview with **↑/↓**, then **Enter** to read.
The previous filter is selected so typing replaces it.
Input entered while the connection loads is retained. Browsing pauses Follow.
Press **Ctrl+Shift+J** again to return to the terminal with the filter intact.
Header **×** and the toolbar toggle control visibility.
**Escape** retains its navigation behavior: from the compact reader it returns
focus to the originating terminal, without hiding the panel or resuming Follow.

| Key | In Peek |
| --- | --- |
| **Ctrl+Shift+J** | Open search; repeat to return without hiding Peek. Requires the native input patch and optional binding. |
| **↑ / ↓** | Preview adjacent issues. In search, keep typing in the same field while the highlighted result and preview move together. This pauses Follow. |
| **/** or **Cmd+F** | Find an issue: reveal and focus search. Type a filter, use arrows if needed, then Enter. Direct issue keys also work. |
| **Enter** | From the reader, open Jira. In search/list, choose the highlighted visible result (or the first match) and return to the reader. |
| **Page Up / Page Down** | Page results in the filter/list; page the reader or Help with the native input patch. |
| **Y / Shift+Y** | Copy the key / link from the reader, issue action buttons (including Refresh, Comments and Details), or issue list. |
| **R / O / ?** | Refresh / open Options / open Help from the reader, issue action buttons, or issue list. |
| **Escape** | Return from Options or Help to Issues; close browsing or expanded content first; from the compact reader, return to the terminal. |

Options and general Help restore focus to the filter, list or reader so you
can continue immediately. Help starts with a collapsed Keyboard topic. Letter shortcuts
leave typing, text editing and focused-button activation alone.
**Tab / Shift+Tab** reach the other native
controls, including setup and Connection settings. In Options, **↑/↓** moves
between available rows; **Enter/Space** activates the focused control.
**Escape** returns one level: setup → Connection → Options → issue view.
Canceling setup opened from Connect Jira returns directly to Connect Jira.
In the issue list,
**↑/↓/Home/End** changes selection while keeping it open; **Enter** commits
a visible result. With the optional bindings below, **F2** toggles Follow and
**F5** refreshes while Peek has focus. Search reserves plain Up/Down for results;
other editing keys and modified arrows stay native. Typing a slash in search
does not retrigger Find. Setup retains ordinary text editing.
After previewing with arrows or Page Up/Down, Enter commits that choice even
if the filter looks like a key (for example, `DEMO-10` matching `DEMO-1042`).
Editing the filter resets that choice; a newly typed key or URL is a direct lookup.

With the [native input patch](native/APP-INPUT.md), **Page Up/Down** scrolls
the reader and Help, **Home/End** reaches the top/bottom, and **Space/Shift+Space**
pages a focused text pane. Tab reveals the focused control; Space on buttons
still activates them. Hiding/reopening retains the reading position in memory.
Stock 0.1.11/0.1.12 still requires the wheel for long panes and resets their position
when hidden.

On the patched host, merge the optional [keys.json](keys.json) into
`HERDR_APP_HOME/keys.json`. Replace the old Peek binding with
`ctrl-shift-j: layout.focus:jira-peek`, preserving unrelated shortcuts.
The installer leaves keys alone. The older `tabs-jira-peek.browse-jira`
binding remains asynchronous and must be replaced. Stock users should use
Issues or Tab to reach the filter before typing.
An open form keeps its draft and receives focus.

Herdr does not prescribe a Jira Peek shortcut. Follow and Refresh use
`mod:jira-peek` bindings. Change or remove them in `keys.json`:
there are no hardcoded F2/F5 fallbacks. Local navigation uses native focus
handles and Tab traversal, while terminal Ctrl-letter, Option typing, AltGr,
and modified Escape chords remain available to the host. Options and setup ignore
Peek commands aimed at the hidden reader; plain Escape cancels setup only when
no save is in progress. See the
[guidance audit and native evidence](docs/VERIFICATION.md).

Each new panel starts in the compact reader; an older expanded-list preference
does not override that default. Local keyboard actions are immediate. The focused
reader shows a small shortcut hint, which disappears when focus leaves Peek.
The issue key and status remain above the scrolling description. A filter
that excludes the selected issue covers its reader and disables its actions;
choose a result or return to that issue before copying, opening or refreshing it. Quick help
explains the configurable entry command without assuming the example binding
has been installed.
herdr-app 0.1.10 still requires wheel/trackpad scrolling for longer content;
Page Up/Down does not scroll the reader. Enter provides the direct path to the
full Jira page. Native controls show focus, but the host does not expose the
supplied Input name in macOS AX. See [native UI acceptance](docs/UX-REVIEW.md).

The picker flow draws on Herdr's shipped picker and community quick-switcher.
See [Mods research](docs/MOD-REFERENCES.md) for comparable tools, the observed star
ranking, implementation references, and the limits of those popularity signals.

The header's ellipsis opens **Options**, which includes a named **Help** entry;
the close icon hides Peek. **Open in Jira** leads the issue action row, with
copy-link and refresh icons grouped on the right. Clicking the key copies it.
Hover for action names and shortcuts. Copying changes its icon to a checkmark;
the controls keep their position. All icon buttons have accessible names and
keyboard focus. **Following/Paused**, issue status and fetch time stay visible.
The default summary becomes the issue title, without a repeated Summary label.
Customized field placement, labels and visibility still apply. Below 500px
panel height, the title scrolls with the reading content so the key and actions
remain available. Selected issue rows use a neutral fill and checkmark.

**Options** and **Help** each have a visible **← Issues** button. It returns
directly to your issue view and filter; **Escape** does the same. You can move
to Help from Options, and back to Options from Help's header. These screens have no
panel-close **×**, and preserve your filter, selected issue and reading position.

**Help** explains every Options row using the same label and order, including
what “source” means and how finding keys differs from refreshing issue details.
Every topic starts collapsed. Click a heading, or Tab to it and press
Enter/Space, to read its explanation. Opening another topic closes the previous
one; activate the same heading again to collapse it.
Help opened from Fields, Connection, or setup explains that form and returns
to it, preserving unfinished values. Setup and connection help include an
explicit link to Atlassian's API token guide. Tooltips supplement this
keyboard-accessible guidance. Help is unavailable while a save is running.

**Options** temporarily uses the attached panel for a grouped action list:
**Refresh**, **Copy key**, **Copy link**; **Pin source**,
**Highlight source**, **Scan screen**, **Read history**; **Auto-refresh issue**, **Fields**, **Connection**, and **Clear cache**.
Pin source, Highlight source and Auto-refresh issue show their current state. Actions return to the
issue view; toggles stay open. Closing Options preserves the selected issue,
filter, expanded details, and reader scroll position.
Connection settings offers token setup, an existing configuration folder, and
**Reconnect** for a connection that needs attention. Back returns to Options
with Connection focused. Canceling a folder choice stays in Connection.
**Issues** and
**Following / Paused** remain directly available.

Use `AUTO_REFRESH_SEC=0` for manual **Scan screen**; 1–60 sets the passive scan interval.
Unchanged scans do not authenticate, query Jira, or reload the reader.
**Auto-refresh off** is the default for new users. Turn Auto-refresh on to refresh the selected
issue at most once every 60 seconds, skipping busy requests. The UI choice is
saved locally. Auto-refresh (formerly Live) turns off after
five minutes without actual panel input; automatic scans and requests do not
renew that activity lease. Hidden panels stay alive and may refresh within the
lease. Turn Auto-refresh on again to resume. The reader shows the payload's fetch time
in UTC, including cache hits. This timestamp stays accurate even when the
panel does not redraw.

`MAX_CANDIDATES` caps missing metadata requests. Details load on selection;
Refresh fetches the selected issue; **Retry** is offered after a failed request.
The latest selection can load alongside one slow metadata or previous-issue
request. Rapid choices coalesce to the latest key with at most two issue/metadata
reads in flight; the same issue is never fetched twice concurrently. A cached
issue displays without a request, and a known title appears while full details load.

The reader distinguishes queued/loading requests from refreshes. A failed
refresh keeps the last loaded issue visible with a nearby error and Retry below
the fixed actions. Clipboard confirmation is separate from persistent operation
errors; copying does not dismiss those errors.

The panel retains up to 200 keys per source, 12 recent source sessions, and
40 loaded details in memory. Your reading selection survives list trimming.
Details are reused according to `CACHE_TTL_MIN`, measured from their original
fetch time across disk and memory; zero disables durable issue
caching. No terminal snapshots, queries, or issue lists are written to Herdr's
shared state or localStorage. The configuration path and the Auto-refresh,
reader-focus and source-highlighting choices, plus per-connection field layouts,
are stored locally. Closing the
panel discards its in-memory state;
hidden panels stay alive under Herdr's mod lifecycle.

Configuration and connection-epoch changes clear the panel and request a
reconnect. Account or credential changes are also checked on the next backend
request. Source polling can miss keys that disappear between reads. Use manual
lookup or explicit Read history for an older issue.
Permission denial stays local to the affected operation. A temporary request
failure backs off automatic issue reads for 30 seconds; deliberately choosing
another issue can try it immediately. Failed background titles do not delay
issue details. Peek resumes eligible automatic work when the cooldown expires
without requiring another terminal update.

The standard Jira key syntax and project allowlist govern native discovery.
Native source highlighting is controlled in Options; legacy terminal-only
configuration settings do not change native rendering.
Native content uses safe plain text, with no embedded images or active links
from issue bodies. Headings, lists, quotes, code, tables, warning panels, expandable
sections, task/decision items and status labels retain their readable content.
Unknown rich-content types show an omission marker and a notice to open Jira.
Descriptions are capped at 100,000 characters; the reader shows up to 100
comments, at most 20,000 characters each and 1,000,000 comment-body characters
in total. Reader field values are capped at 20,000 characters and picker values
at 4,096 characters. Custom rich-text fields preserve the same safe text structure.
Shortened content is
marked; open Jira to read the full issue.

## Update, remove, and inspect

From a checkout that includes the update helper:

```sh
python3 scripts/update-app.py --check  # Show installed and available versions
python3 scripts/update-app.py          # Install the newest numbered release
```

After installing this helper once, the checkout is no longer needed:

```sh
python3 "${HERDR_APP_HOME:-$HOME/.config/herdr-app}/mods/jira-peek/runtime/update-app.py"
```

The updater uses Python 3.9+, Git and your existing Git repository access.
It selects the highest `vMAJOR.MINOR.PATCH` tag from this repository, downloads
that exact tag into a temporary directory, checks matching versions, and runs
the release's installer with `--check`. Branch commits and suffixed tags such
as `v0.2.0-rc.1` are excluded. **This is still an experimental release stream**;
GitHub's pre-release flag does not change which numbered tags are selected.
No background update or scheduled network check is installed. Herdr's own
app updates are separate from updating this community mod.

`--check` only reports availability and a release-notes link. A repeated update
to the same version changes no files. `--version 0.1.1` selects a specific
release; an older version also requires `--allow-downgrade`. An installation
from the former 0.13.0 stream needs that explicit downgrade choice when moving
to 0.1.x. Both helpers accept `--app-home` for a custom installation. An
installed helper defaults to the app home containing it.

If your installed version predates the helper, obtain a newer versioned
checkout containing it and run the existing managed installer once:

```sh
python3 scripts/install-app.py --update --check
```

That command installs **the local checkout**; it does not fetch updates.
The updater becomes available to other users when a release containing these
changes is tagged and pushed. Preparing these files does not publish a release.

Updates reject unmanaged files, edited managed files, and symlinks. The only
extra files accepted are Herdr-generated `gpui-kit.d.ts` and `jsconfig.json`.
The complete old mod is preserved in a hidden backup folder under `mods`; those
generated files are omitted from the new bundle so Herdr can regenerate real
paths. Configuration and caches stay outside that folder. Keep a personal fork
if you customize the mod.

To restore a known-good backup, pass its exact folder name printed during the
update (replace the example below). This works offline, checks the backup and
Herdr compatibility, preserves current settings and the selected backup, and
also saves the version being replaced:

```sh
python3 scripts/update-app.py --rollback .jira-peek-backup-012345abcdef
```

The installed update helper accepts the same arguments. From a checkout,
`scripts/install-app.py --rollback NAME --check` is also available. Restoring
a release from before the helper existed removes the helper too; keep this
checkout or the newer backup for the next update. Prefer a backup restore for
these older releases: their installers may not understand newer bundles.
A rollback restores code, not a snapshot of credentials or user data.
Release notes must identify any
future settings migration that makes older code incompatible.

Herdr [hot-reloads mod files](https://github.com/herdrdev/herdr-app/blob/master/defaults/AGENTS.md).
If the old panel persists, reopen the window. A checker pass does not replace
trying the panel; use the backup if the new release misbehaves.

**Options → Clear cache** clears issue data from
this panel's memory and the app state's disk cache, invalidates in-flight
responses, and reconnects. It preserves private configuration, credentials,
and UI preferences. Other open panels can rediscover or fetch data again;
close all copies before a full local cleanup.

Close all Peek copies, remove only the Jira Peek block from your personal
layout, and remove only bindings you added for `jira-peek.*`,
`layout.focus:jira-peek`, `tabs-jira-peek.browse-jira` or the older
`layout.toggle:jira-peek` example
from your keys file. Preserve all unrelated
blocks and shortcuts. Then remove the installed `mods/jira-peek` folder under
your chosen app home. Inspect any hidden Jira Peek update backups separately
before deleting them; do not remove the whole `mods` directory. Clear retained local data separately by
removing `data/jira-peek` after closing all copies. An external configuration
folder and external credential file remain yours to manage. Removing that local
data directory also removes credentials created by the inline setup form.

Development checks, with no Jira account or running core required:

```sh
node --test tests/*.test.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v
```

For the actual host checker, validate the assembled bundle in a fresh temporary
app home. This requires the installed native app and checks no live connection:

```sh
peek_check_home=$(python3 -c 'import pathlib,tempfile; print(pathlib.Path(tempfile.mkdtemp(prefix="jira-peek-check-")).resolve())')
python3 scripts/install-app.py --app-home "$peek_check_home" --check
```

For native visual verification, use the isolated fictional fixture in
`python3 docs/screenshots/capture.py --app`. Add `--app-review` for an interactive
lab with narrow, short, light, long-list, setup, and request-recovery scenarios.
It launches and closes its own
app and core, exercises a temporary fictional terminal and its available
history with an offline backend, and captures the compact reader at 420px in
dark/light themes and at 300px in dark mode. The rig separately exercises reader
focus, URL lookup, freshness, Follow, cache clear,
and configuration invalidation. Never substitute a live session. See the
[recipe](RECIPE.md) and
[verification record](docs/VERIFICATION.md).

## Provenance and license

Native Jira Peek was extracted on 2026-11-01 from the native edition developed
in [hilmimuktitama/herdr-jira-peek](https://github.com/hilmimuktitama/herdr-jira-peek),
which remains the separate TUI project. Experimental 0.1.0 starts a new native
version sequence after the earlier 0.13.0 extraction. It retains mod ID
`jira-peek` and installation owner marker `herdr-jira-peek` so managed
installations can update safely, including from 0.13.0. The root catalog entry consists of
`RECIPE.md`, `preview.png`, `mods/jira-peek`, and optional `keys.json`.
The recipe makes the runtime-bundling installer and personal layout/shortcut
choices explicit. Direct source-folder copying is insufficient.

By [hilmimuktitama](https://github.com/hilmimuktitama) and the Peek for Jira contributors. Distributed under the
[MIT License](LICENSE); see [third-party notices](THIRD_PARTY_NOTICES.md).
This is an unofficial community project, unaffiliated with Atlassian.
Release preparation and publication are separate steps; see
[RELEASING.md](RELEASING.md) and the [verification record](docs/VERIFICATION.md).
