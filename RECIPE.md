# Jira Peek

A quiet Jira reader beside the terminal you are working in. New issue keys
arrive automatically; deliberate reading stays put. Its colors follow Herdr's
current theme and font-size settings.

![Jira Peek with entirely fictional issue and terminal content](preview.png)

**Experimental 0.1.0 — private preview.**

Requires **herdr-app >= 0.1.10** and the separately versioned **herdr-core**
backend (`hc` on PATH). See [component requirements](#built-from).

## What you see

A right panel with Issues, Following/Paused, and Options.
Options and Help have a visible ← Issues button that returns to the main view.
Help explains every option using the exact label shown in Options.
The terminal's session title appears only in source tooltips, never as a visible row.
Pinned source appears as a brief indicator when focus no longer chooses the source.
The default layout puts the current issue first: key and status stay above the scrolling reader,
followed by a semibold title and the complete loaded description. All panel text
uses Herdr's `ui_font_size`; the host applies zoom. Long descriptions
use the reader's normal scroll region.
Details reveals fetch time and configured metadata; Comments expands separately.
Compact header values retain text-preview
tooltips, and partial comments are identified when opened. With the REST
backend, core issue data loads before optional comments; opening Comments
fetches a bounded page independently, and its failure keeps the description
readable with a local retry. Unsupported document content is identified rather
than silently omitted. The default summary becomes the issue title. Open in Jira
leads the action row, with copy-link and refresh icons on the right. Clicking
the key copies it. The plain header groups an ellipsis for Options and a close
icon; Options includes a named Help entry. Icon buttons have 32px targets, accessible names, tooltips
and visible keyboard focus. Focus shows the icon name and shortcut in reserved
footer space without resizing the reader. Fully displayed text has no tooltip.
Known titles occupy their final slot while loading; actions wait for unknown
pinned headings before becoming clickable. Ordinary tables repeat column names
beside values; merged cells retain text with an explicit limitation.
Copy success changes the glyph to a checkmark
without resizing the control or adding a footer.
Selected rows use a neutral fill and checkmark, with no decorative side bars.
Custom field labels, placement and visibility are preserved. Below 500px panel
height, the title scrolls with the reader while the key and actions stay pinned.

Issues reveals search and the discovered list. Options contains pinning,
refresh, copy, Highlight source, screen/history reads, Auto-refresh issue, Fields, connection settings, and
cache clearing. Its rows scroll at short heights. Status feedback appears
when needed; there is no permanent operation footer. Theme tokens govern colors.

## How it behaves

**Options → Fields** saves one reader layout per configuration folder and Jira
site. Place fields in Header, Body, Details, or Hidden; rename labels; reorder
within each section; add standard/custom Jira IDs; and optionally show empty
values. Apply rebuilds the reader; Back/Escape discards the draft. Reset restores
the configured field defaults in the draft. The issue key and Open in Jira stay
available. Comments support Body, Details, or Hidden. The limit is 32 fields;
there are no project/type variants or field-catalog discovery.

The UI and agents share `${HERDR_APP_HOME}/data/jira-peek/fields.json`.
The installed `mods/jira-peek/AGENTS.md` documents the versioned format;
`fields.schema.json` supplies editor validation. Copy config path in Fields
reveals the exact path. The root `preferences` object stores the shared
`autoRefresh` and `highlightSource` booleans, using the same values as Options.
Watch the file for edits; reject invalid documents
without replacing the working layout. Save UI edits with the native file API's
expected-text guard, retaining the draft if another writer changed the file.
Migrate prior per-connection UI preferences on connection. Keep the file outside
the managed bundle so updates preserve it. The demo uses separate preferences.
See [the agent contract](docs/AGENT-GUIDE.md) and
[researched workflow ideas](docs/AGENT-WORKFLOWS.md).

The installed guide also maps connection/data settings, host typography,
placement, width, keys, and session actions. Expose existing actions through
`nextCommand` so agents can use the native `herdr-app do jira-peek.<command>`
route. Pause/resume and pin/unpin set explicit states; reader actions cannot
interrupt a settings draft. Commands reach shown copies, so their dispatch
acknowledgment is not proof that a particular Jira request completed.

The main issue view's header × hides the attached panel. Options, Help and
settings use explicit Back controls. A persistent Jira Peek toggle in a
[personal tabs mod](docs/PANEL-INTEGRATION.md) reopens it beside Files/Changes.
The optional [native input patch](native/APP-INPUT.md) for herdr-app 0.1.12
adds `layout.focus:jira-peek`: a synchronous shortcut into the retained native
filter, including when the panel is hidden. Immediate typing belongs to the
input. Replace the old asynchronous toolbar binding when opting into this
host. The same shortcut returns to the originating terminal with the filter
intact. Hiding preserves width, filter, selection, Paused state and the scroll
position. Stock 0.1.11/0.1.12 still has the [three host gaps](docs/HOST-INPUT-GAPS.md);
use Issues or Tab to reach its filter before typing.
Escape returns to the terminal after choosing an issue. A pinned issue source
does not change that return target. Open forms keep their draft. No focus
changes happen on startup or refresh, and no terminal input is sent.

With the reader focused, Up/Down peeks at adjacent issues without opening
the list, Enter opens Jira, and Y
copies the key. Slash or Cmd+F opens search. A small hint appears only while
the reader has keyboard focus. Native buttons and text fields retain their
own Enter, Space, and editing behavior. Modified arrow keys are not consumed.
In the reader or issue list, Shift+Y copies the link, R refreshes, O opens
Options and ? opens Help. These letters remain ordinary text in inputs.
Options and general Help restore focus to the retained filter, list or reader.

Following selects the latest visible issue, including a previously discovered
key when the agent returns to it. Opening Issues, filtering, selecting, scrolling,
or expanding content pauses Follow and keeps deliberate reading in place.
The optional mod-scoped F2 binding resumes Follow or pauses it; F5 refreshes
the issue. Both are dispatched only through Herdr's configurable keys.json
and nextCommand, with no raw-key fallback. Pin locks the terminal
address; Unpin resumes following focus. With the dedicated issue list focused,
Up/Down selects adjacent filtered issues and Home/End selects the first/last;
selection scrolls into view. Enter commits a visible result and closes browsing.
Page Up/Down moves by the visible row count in both the filter and list.
An explicit keyboard preview takes precedence over direct lookup on Enter;
editing the input restores normal key/URL lookup behavior.

The native input patch supplies ordinary-pane Page Up/Down, Home/End and
Space/Shift+Space, plus visibility of focused descendants. Text editing and
button activation retain precedence. Stock 0.1.11 requires wheel scrolling
for long reader/Help content. Positions are retained only with the living mod
copy, bounded to 64 named panes; they are not persisted across app restarts.
Pointer selection previews in place, keeping the list and its viewport stable;
Back to issue expands the reader. Opening Issues focuses the filter and selects
its previous text; its clear button retains the selected issue and list mode.
Clear explicitly updates both the native field and the model. An excluded
selection keeps its reader mounted but invisible, with actions disabled until
a result is selected or the user explicitly returns to the reader. Native
commands and local copy/open/manual-refresh handlers use the same guard.
The +new badge reads the newest unseen key and acknowledges only that key,
preserving Paused and the query for the return to Issues.
The list shows up to four full 56px rows at normal height and shrinks in short
panels. In search, plain Up/Down previews visible
results while preserving input focus and query; a small focus-only hint explains
this path. If the prior selection is filtered out, the first arrow selects the
first result. Movement clamps at both ends; other editing keys and modified
arrows stay native. Without an explicit preview, Enter submits an allowed key or a `/browse/KEY` URL on the
configured Jira origin, otherwise commits the selected visible match or the
first result. A wrong-project key or foreign URL shows validation beside search.
An allowed direct key outside the results has a clickable lookup action.
Hyphenated title text can select a matching row; URLs still require origin validation.
Direct search commands capture the originating terminal before moving focus,
using the same live identity checks as Peek entry and return.
Options uses grouped native rows in the same panel. Up/Down skips unavailable
rows; Enter/Space uses native activation. Commands close Options, while the
Pin, Highlight source and Auto-refresh toggles stay open with their state visible. Its Back path
is explicit: setup → Connection → Options; direct setup returns to Connect Jira.
Folder-picker cancellation retains Connection. Navigation preserves the issue,
query, disclosures, and reader scroll position. The covered reader stays mounted
but invisible and outside native Tab traversal. No reader command should act
behind these screens.
Options and general Help are sibling screens: ← Issues or plain Escape returns
directly to the retained issue/filter view, even when Help was opened from Options.
Options includes a named Help row; Help's header links to Options. Neither shows ×.
Help describes all eleven issue/settings rows in their displayed order and terminology.
Topics start collapsed and open one at a time. Full-width 36px heading controls
show chevrons and visible focus; click or native Enter/Space toggles them.
Closed explanations and their links are absent from the rendered tree.
Help from Fields, Connection or setup returns to that form and preserves its
unfinished values. It is unavailable during a save. Guidance is bundled with
the mod; only the explicit API token guide link opens the browser. Tooltips
supplement keyboard-accessible help and never replace native accessible labels.
Escape closes Options first, otherwise clearing visible lookup browsing and
returning to the issue. A hidden saved filter does not consume Escape.
It next collapses expanded content, then returns to
the originating terminal. Empty lookup can also return to that terminal.
Native buttons have descriptive names and visible focus feedback; the list
and reader also indicate focus.

Each panel starts with browsing closed, regardless of old reader preferences.
herdr-app 0.1.10 requires wheel or trackpad scrolling
for the reader; Page Up/Down is not functional there. Its macOS accessibility
tree exposes action names, toggle states, and named issue options, but omits
the supplied native Input name. See [UI acceptance](docs/UX-REVIEW.md).

Auto-refresh (formerly Live) is off for new users. Its saved UI choice enables selected-issue refresh
at most once every 60 seconds, skipping busy requests; five minutes without
actual panel input turns it off.
Automatic work does not renew this lease. Hidden panels remain alive and may
refresh within it. Fetch time comes from payload file mtime, including cache
hits. Default unchanged screen scans do no Jira refresh.

Source highlighting is on by default when the optional renderer API is present.
It marks exact visible occurrences of the selected key in the selected terminal,
including keyboard selection and Following; Paused and pinning retain that
choice. It changes no terminal text, focus, input or scroll position. Off,
source loss, setup, reset and closing clear the mark; hiding suspends it and
showing restores it. Off-screen keys and manual lookup without a source have
nothing to mark. Stock hosts show an unavailable option with an explanation.
The native extension owns cleanup and isolates copies; successful requests can
be reasserted after a terminal restart without creating a redraw loop.

Read history explicitly reads up to 200 available host history lines without
scrolling or input. Automatic discovery remains screen only; alternate-screen
history may be absent. Clear cache discards this panel's issue memory and the
app state's issue disk cache, invalidates in-flight results, and reconnects.
Private configuration, credentials, and UI choices remain; other open panels
can rediscover data.

The source status dot uses Herdr's working, blocked, done, idle, or dim token.
Source state is informational; it never triggers agent control. Issue statuses
use done for resolved/closed work, blocked for holds, working for progress or
review, and muted otherwise. No decorative animation or animation timer is used.

Empty setup, queued/loading requests, no source, no matches, missing issues,
and changed connections have explicit messages. Refreshing is shown near the
reader. A failed refresh retains the last loaded issue with a nearby stale
content warning and Retry. A failed request backs off automatic work. Manual
Refresh also retries failed summary lookups for the current source; successful
responses that omit an inaccessible issue do not cause a retry loop. Overlapping
screen scans coalesce into one pending read and remain serialized with History.
Clipboard confirmation does not replace or clear persistent operation errors.
A closed source keeps its discovered keys with a notice.

The latest selected issue can start alongside one earlier issue or metadata
request. Two slots bound this work; rapid choices coalesce to the latest key,
and same-key requests stay serialized. Cached issues appear without a request;
known titles appear while details load. Late metadata cannot overwrite a newer
detail's title. Background failures stay local, while automatic reads retain
their cooldown; a deliberate new selection can try immediately. Deferred
comments keep their existing separate request. Feedback stays below the fixed
issue actions, so refresh does not move the controls.
The last successful fetch time is visible in the fixed action area and remains
unchanged after a failed refresh. It reuses the existing timestamp without polling.

## Built from

Requirements refer to two different components. **`herdr-app` >= 0.1.10** is
the desktop UI/mod host (`herdr-app --version`). **`herdr-core`** is the
terminal backend, exposed as **`hc`** (`hc --version`); `hc` must be on PATH,
but this mod does not currently enforce a numeric core minimum. Their versions
are independent. Preserve the literal **0.1.10**; do not report **1.10.0** or
the ambiguous "Herdr version", and do not compare a core/TUI version against
the app minimum. Use the doctor's component-specific results.

Use the complete repository checkout, including its root `scripts/` directory.
Do not copy `mods/jira-peek` alone: the installer assembles its required
shell/JQ/Python runtime from the included source files. From the repository root:

```sh
python3 scripts/install-app.py --doctor
python3 scripts/install-app.py --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

For an existing managed installation, including 0.13.0, use `--update --check`.
This installs the current checkout. For later releases, use
`python3 scripts/update-app.py --check` to inspect availability, then omit
`--check` to install the latest numbered tag with native validation. The helper
also ships at `mods/jira-peek/runtime/update-app.py`, so users need not retain
the source checkout. See [updates and rollback](README.md#update-remove-and-inspect).
Read [requirements and attachment instructions](README.md#install) first.
Source ZIPs work without Git. `--attach` creates a personal layout containing
the panel and the Jira Peek toolbar button. It preserves original layouts and
keybindings, and refuses conflicting personal edits. Omit `--attach` on later
updates. The global example in
[keys.json](keys.json) requires the [native input patch](native/APP-INPUT.md)
and the actual attached block ID; verify `layout.focus` before merging the key.
Resolve occupied shortcuts with the user. The personal layout is derived from
the user's stock layout when they request attachment.
Publication is a separate step in [RELEASING.md](RELEASING.md).

Ordinary installation uses stock Herdr. Source-terminal highlighting needs an
optional local renderer extension; do not rebuild or replace the host as part
of a normal mod install. See [highlighting](native/APP-HIGHLIGHT.md).

One `mods/jira-peek` native GPUI mod, with `main.js`, a pure `model.js`, and
`mod.json` declaring right placement. `demo.js` supplies only fictional data
when `props.demo` is true; the live path never falls back to it. `props.configDir`
optionally chooses a private configuration folder.

Use `focused`, `terminals`, and `panes` for live source identity and status;
`hc` for explicit screen reads; `exec` with an argument array for the packaged
shell adapter; `watchFolder` and a local stamp for connection invalidation;
`pickFolder` for existing configuration; `nextCommand` for optional key commands;
`run("pane.focus", ...)` only for an explicit keyboard return to a validated
origin. Use native
buttons with names and focus feedback, InputState, a dedicated keyboard issue
list with selection scrolling, scrolling regions with stable IDs, theme colors, clipboard writes,
and `cx.open_url` for a validated configured Jira origin.

Keyboard integration was checked against the installed herdr-app 0.1.10
`AGENTS.md` sections **Keys**, **Commands**, and **Mods**, plus the generated
`herdr.d.ts` and `gpui-kit.d.ts` focus, KeyEvent, and traversal contracts.
The supplied bindings are examples, not Herdr defaults or automatically installed
keys. Use global scope only for entry,
mod scope for Follow/Refresh, and local focus-path handlers for navigation.
Never claim terminal Ctrl-letter, Option typing, or AltGr chords implicitly.
Keep modifiers intact, including Escape in setup. Tab/Shift+Tab use host
traversal on every panel screen, after native fields can handle their own
input. Moving to settings focuses Set up Jira; loading setup focuses Cancel
until the first field is ready, so removed controls cannot strand focus.
The current terminal-to-filter retest covers stock and patched herdr-app
0.1.12; see [results and limits](docs/VERIFICATION.md#reader-controls-and-0112-retest).

The search interaction follows the shipped picker and community quick-switcher
pattern, with a bounded virtual list and local focus-path events. The
[Mods research record](docs/MOD-REFERENCES.md) records sources and popularity limits.

Inline setup uses masked InputState and a bundled Python helper. The helper
prepares a private empty request file; `writeTextFile` transfers the form with
compare-and-swap, and `exec` passes only the helper operation and file ticket.
The token never appears in process arguments or localStorage. A read-only
account check precedes an atomic configuration switch; failed or stale saves
preserve the active connection. Setup owns only the separate private
`data/jira-peek/connection` folder. See [connection setup](README.md#connect-jira)
for token scopes, dependencies, storage, and replacement behavior.

The installer copies an explicit allowlist of shared shell/JQ runtime files
into the mod, validates before replacement when `--check` is supplied, and
keeps the full previous mod as a backup on update. `--doctor [--json]` checks
executable presence and native version offline, not authentication. Updates
reject symlinks, unmanaged files, and edited managed files; only generated
`gpui-kit.d.ts` and `jsconfig.json` are accepted as extras and omitted from the
new bundle so Herdr regenerates paths. No shipped layouts or keys change.
Concurrent managed installs are refused, and files are revalidated after the
native check. A named backup can be restored offline with the update helper's
`--rollback` option; current user settings and both code bundles are retained.

## Watch out

Herdr sends mod commands only to shown copies. The documented personal toolbar
handler reveals the attached block before handing focus to Peek. Install it
before merging the supplied key snippet, and use the actual block ID. A
separate `layout.toggle:<block-id>` binding can still control visibility.
Never substitute `mod.open`, which creates an overlay. The installer preserves
keys; retain unrelated bindings. Escape must not restore
a dead terminal, a changed pane identity, or a different tab.

This mod runs local programs, reads the chosen private config, and makes
read-only requests to its configured Jira backend. Terminal reads may address
remote machines, but credentials and Jira requests stay local. No source
control, agent input, or Jira writes occur. Never send body text through a
shell or render it as active HTML/Markdown. Do not persist issue data in Herdr
shared state or localStorage; only the chosen configuration path and UI
choices for Auto-refresh, reader focus, source highlighting and per-connection
field layouts are stored locally.

Automatic native reads return only the screen; Read history is explicit. Respect
`AUTO_REFRESH_SEC=0`, serialize screen/history reads, bound issue/metadata work
to two slots, discard stale source responses, and reject connection epochs before
publishing a result. Retain at most 200 keys per source, 12 sources, and 40
details. Details and metadata are separate; metadata discovery is capped and
missing-only. Reader fields start from existing preferences; the saved layout
can request additional supported IDs through the same validated read path. The
POSIX adapter targets macOS/Linux; Linux GUI verification is not established here.
Descriptions are limited to 100,000 characters, comments to 100 at 20,000
characters each and 1,000,000 body characters total. Reader field values are
limited to 20,000 characters, picker values to 4,096. Preserve headings, ordered lists, quotes, code, and tables
as plain text, with no active body links or images.

## Done when

- Herdr's native checker accepts the mod and a real isolated app renders it.
- New allowlisted keys follow automatically; Browse preserves selection,
  filter, and reader position during discovery.
- Pinning survives focus changes; remote/local addresses do not collide.
- With the optional renderer, selection changes mark the matching terminal key
  on an idle source, and Off/hide/close remove it. Stock hosts remain usable.
- Source, search, Follow, and reader/list controls remain directly available;
  Options contains secondary controls; icon actions remain named, focusable
  and fully visible at 300px, with text guidance in Help and named secondary
  actions in Options.
- With list focus, Up/Down/Home/End select and reveal the matching issue;
  search editing remains independent and invalid direct lookups show validation.
- Loading, refreshing, and stale refresh errors appear near the reader;
  clipboard confirmation preserves operation errors.
- A late result cannot cross source or connection boundaries. Unchanged
  reads perform no Jira work. Errors back off and explicit refresh retries.
- Configured fields render as safe text; browser links stay on the configured
  origin. Zero TTL leaves no durable issue payloads.
- The installer preserves layouts, bindings, private config, and local edits.
- With the personal toolbar integration, Ctrl+Shift+J reveals the attached
  panel and focuses its filter; repeating it returns to the original terminal.
  The main issue view's header close action hides the panel, and the shortcut can reopen it.
- The screenshot rig exercises its own temporary fictional terminal/history,
  URL lookup, freshness, Options/Help return with the filter retained, reader
  focus, clear/reconnect, and invalidation before compact-reader captures at
  420px in dark/light themes and 300px in dark mode, plus Options and Help.
