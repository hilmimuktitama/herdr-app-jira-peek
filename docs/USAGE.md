# Using Jira Peek

How the panel behaves, what each control does, and what remains unverified.
For setup, see the [README](../README.md). For credentials, see
[connection](CONNECTION.md). For the full field and state model, see the
[feature dictionary](FEATURE-DICTIONARY.md).

## Install details

The Rust runtime, in-app setup and lifecycle commands need no Python, `jq`, curl
executable or external SHA utility. Git is required for release updates. Existing
TWG connections instead require the official TWG CLI 1.2.6+ with OAuth. Release
binaries target macOS 15+ and glibc Linux (Ubuntu 22.04+) on arm64/x86_64; Linux
needs system libcurl with TLS support. Other Unix versions require a local build
and validation. Windows is unsupported. The setup form supports Jira Cloud on
`*.atlassian.net`, not Server/Data Center.

Keyboard entry through the host's pane navigation needs **herdr-app 0.1.12 or
newer**. Peek detects **0.1.16–0.1.18** host contracts at runtime (native
checker, window activity, cancellable folder watches, bridge timeouts, reader
scroll tracking, GPU loading animations, selection-change hooks, agent status
chips and Command Palette entries); older hosts keep their previous behavior.
The installation floor remains 0.1.10.

`manage doctor` stays offline and does not check Jira credentials or fetch
binaries. Installation checks the matching assets' manifest, source identity,
checksum and startup behavior before replacing anything. Missing or incompatible
assets leave the previous installation intact. Download only trusted release
assets; they are not independently signed or notarized. No Rust toolchain is
needed for a release.

`--check` runs Herdr's native checker before installation; it executes trusted
mod code with your user-account access, so it is not a sandbox or security audit.
Install only source you trust.

`--attach` creates a personal `main-jira-peek` layout and `tabs-jira-peek` toolbar
with a **Jira Peek** toggle beside Files/Changes. It preserves shipped layouts and
shortcuts, and refuses conflicting personal edits. Select the printed layout (or
use Herdr's Layout menu).

Install from the complete source, rather than copying `mods/jira-peek` alone. The
default app home is `~/.config/herdr-app`. For a custom home or layout, use
`--app-home /absolute/path` and `--attach YOUR_LAYOUT` as described in the
[recipe](../RECIPE.md#built-from); launch Herdr with the same `HERDR_APP_HOME` and
select the printed layout.

For an unpublished checkout, build the package with
`python3 scripts/package-runtime.py`; developer requirements are in the
[runtime guide](../rust-backend/README.md).

**Upgrading from 0.11.0 or earlier?** Your existing Python updater remains
supported for the transition. After upgrading, use the installed Rust commands.
See [maintenance](MAINTENANCE.md#older-installations).

## See your first issue

Print a real issue key from a configured project in the focused terminal, for
example `echo ABC-123` with your own key. New terminal sources start **Paused**,
collecting keys without loading Jira details or metadata. Click **Issues** and
select the key, type it and press Enter, or resume Follow with **F** to load it.
If the key does not appear, check terminal focus and configured project keys, then
try **Options → Scan screen**. Short-lived keys can be missed.

**Already configured?** Choose **Choose configuration folder…**, or **Options →
Connection → Choose existing folder…**, and select the private folder containing
`config.sh`. No private configuration is copied. See
[existing TWG/REST configuration](CONNECTION.md#existing-configuration).

## Follow and browse

New sources start Paused. They collect unread keys until you select an issue, edit
the filter, or resume Follow. Returning to a terminal restores its session state.
Auto-refresh is a separate opt-in. See
[Follow and loading behavior](FEATURE-DICTIONARY.md#jp-004--following-and-deliberate-reading).

Follow selects the latest visible confirmed key, and the Terminal toolbar shows
a **Following** or **Paused** indicator beside the Follow button (hidden below
`28u` width). Reading, selecting, filtering, or scrolling pauses it while new
matches still collect. **F** resumes with the latest issue and clears the
filter; when resuming clears a non-empty filter, a `Filter cleared` toast offers
an inline **Undo** button to restore your filter, previous selection, unread set
and Paused state. **+new** reads one unread issue without resuming. **Keep this
terminal** in Options keeps discovery on that terminal while you work
elsewhere, showing an active program/branch chip with a status dot that clicks
to focus that pane when reported by the host (or **Keeping this terminal**
otherwise).

Auto-refresh is off by default. When enabled, it refreshes at most once a minute
and pauses the idle panel after five minutes; resume through Options. Hiding Peek
does not end an active refresh lease. The timestamp is fetch time, including cache
hits, rather than proof of current Jira state. See
[refresh behavior](FEATURE-DICTIONARY.md#jp-029--auto-refresh-issue-and-local-idle-pause).

## Find and read

Click **Issues**, type to filter loaded metadata, then press Enter to read. The
field leads with a search glyph and shows a boxed `/` keycap while empty and idle.
You can also enter an allowlisted key or same-site Jira browse URL. When
Terminal has no detected keys yet, an inline **Scan screen** button appears in
the empty list when terminal scanning is available.

Rows and the reader show status as a small colour dot plus a muted sentence-case
label such as **In progress**, not coloured text. Progress is blue, review and
testing are amber, done uses the theme's success role when it has one and its done
role otherwise, and blocked uses the blocked colour. Each full row adds a quiet
assignee · updated line under the summary, and short Split rows keep two lines.
In Stack, the selected row keeps its Copy/Pin buttons visible while unselected
rows show them on hover; **right-click** any visible row in Stack or Split for a
context menu (**Copy key**, **Copy link**, **Copy as Markdown**, **Pin/Unpin**,
**Open in Jira**, **Refresh**) without changing selection or Follow.

Click the issue key to open Jira; expand **Details (D)**, **Comments (C)**, or
**Linked Issues (L)** for more content. On capable hosts, opening a disclosure
scrolls the reader to reveal it and reader scroll position is preserved across
Options, Help and Fields for the same issue. Progress appears immediately left of
Refresh, replacing the timestamp while busy; the last fetch time remains in its
tooltip and returns afterward.

### Preview a Jira link from the terminal

On **herdr-app 0.1.17 or newer**, enable previews for one existing Jira Peek
connection, then select a personal Herdr layout. [Enable or disable previews](MAINTENANCE.md#terminal-link-previews).

**Cmd-click** on macOS or **Ctrl-click** on Linux opens a full Jira browse URL
from the bound site and an allowed project in a separate reader. Press **Escape**
to return to the terminal. Your docked issue, filter, pin, and Follow state stay
in place. Links printed by remote terminals use the same local connection.

Other links and unavailable preview routes keep Herdr's normal opener. For a
bare issue key, use the **Issues** field described above.

## List resize and presentation modes

**Stack only:** drag the bottom edge of the issue list up or down to resize it
smoothly, up to four rows. Its grip rests quietly at the border tone and
brightens on hover or drag. When more issues remain beyond the visible page,
Stack paints a clipped slice of the next row as a scroll cue. The size stays for
this panel session. Fewer filtered matches shrink it temporarily; clearing the
filter restores your size.

Split has no grip and budgets six rows (two in short chrome), and the list never
paints a horizontal scrollbar. Peek picks **Stack**, **Split**, **Card** or
**Guard** from the width and height the host gives it. A short Stack moves the
selected key into the header when the title hides. Short Split shows two complete
48px rows plus a clipped next row as a scroll cue; under 26u height it uses a 28px
footer with a 20px reader title and 14px body, and Issues folded into the title
row. Card falls back to assignee, priority and updated when no other header fields
are configured, keeps a 16px inset, puts Open, Copy key and Pin in one row with
only one primary action, and labels a configured date such as **Updated 31 Oct
2026**. See [presentation modes](AGENT-GUIDE.md#presentation-modes).

## Copy or pin

**Y / Shift+Y** copies the key/link. Drag over reader text and use **Cmd+C /
Ctrl+C** to copy a selection; on capable hosts, selecting reader text also offers
a **Copy quote (KEY)** button in the reader toast to copy a Markdown blockquote
(`> ...` + `(KEY)`). **M**, the header `...` **More** menu, and **Options →
Copy issue as Markdown** copy the loaded issue as Markdown without fetching
more data.

**P** toggles a pin; **K** returns to it without clearing your filter. The inline
pin targets the viewed issue; unavailable actions show a note, and a successful
change shows **Pinned KEY** or **Unpinned KEY** in a toast over the reader for 2.5
seconds before it clears, or dismiss it directly; the footer height and reader
position never change. Click a pinned row's accent pin to unpin without selecting
it.

## Arrange fields

**Options → Fields** lets you order, label, show, or hide fields in Header, Body,
or Details. **Apply** saves a layout per connection; Back/Escape discards the
draft. It changes Peek's presentation, not Jira.

Choose **Add Linked Issues** for grouped relationships, clickable Jira keys and
embedded summary/status. Its disclosure uses the same chevrons as
Details/Comments; expand five/all loaded links without another request. Agents
configure the same `issuelinks` field with Body, Details or Hidden placement. See
the [field configuration guide](AGENT-GUIDE.md#shared-reader-configuration).

## Clear list

**Options → Clear list**, or **Clear list** in the header `...` menu, resets
collected keys, filter, unread state, and pin for this terminal while preserving
Follow/Paused and caches. Continuously visible keys stay suppressed after a fresh
screen baseline; deliberate lookup or scans can restore them. See
[Clear list details](FEATURE-DICTIONARY.md#jp-007--clear-list).

## Keyboard

Click **Issues** before typing on hosts older than **herdr-app 0.1.12**. On
0.1.12 or newer, the host's pane navigation can land on Peek and hand it the
keyboard (on macOS, **⌘⌥→**; use the host's own pane chord elsewhere). **Cmd+F
(macOS)** or **/** returns to the filter while Peek owns the keyboard; **Tab /
Shift+Tab** moves between controls. Letter shortcuts are ignored while typing, and
`/` is literal in the filter.

| Key | Action |
| --- | --- |
| **↑ / ↓**, **Enter** | Choose an issue, then read inside Peek; on Card, Enter opens the issue in Jira |
| **I** | Swap the Issues list and the reader without editing the query |
| **Escape** | Leave the current layer. In Terminal: disclosure, then reader, then terminal; in Split, the rail collapses before that reader-to-terminal step. In My work/Search: reader back to results. The host pane chord leaves any source; on 0.1.12+ Escape focuses a live terminal in the same tab when the Terminal origin is gone |
| `/` | Find another issue from the reader/list |
| **F**, **P**, **K** | Toggle Follow, toggle pin, return to pin |
| **Y / Shift+Y**, **M** | Copy key / copy link, copy issue as Markdown |
| **C / D / L** | Toggle Comments, Details, or Linked Issues |
| **Cmd+Enter / Ctrl+Enter** | Open Jira from the reader/list, outside text fields |
| **PgUp / PgDn**, **Home / End** | Page the issue list; first / last result |

**? Keys** shows the compact loop; **More shortcuts** has the rest of the guide
and lists the `jira-peek.*` bindings you added. Peek also registers 12 actions
under **Jira Peek** in Herdr's Command Palette on hosts that support mod
palettes. Optional
[key bindings](../keys.json) include F2/F5, Alt+1/2/3 sources, Cmd+Alt+I
list/reader, Cmd/Ctrl+Shift+M for a direct Markdown copy, and the leave chord;
installation does not modify your shortcuts.

For the whole issue as Markdown, press **M** or choose **Copy as Markdown** from
the header `...` **More** menu or **Options (O)**. For text beyond the reader
viewport, **Cmd+Enter / Ctrl+Enter** opens
the issue in Jira, where normal browser keyboard scrolling applies.

## Read-only workspace

The header source icons are **Terminal** (prompt), **My work** (person with check),
and **Search Jira** (magnifier). Hover or keyboard focus reveals the name; the
selected source stays highlighted and exposes its pressed state. Tab moves among
controls and Enter/Space selects a source. Selecting the active icon again does
not refresh, reset, or go Back. The icons stay beside the title at every panel
width; the title truncates when space is tight.

All sources share Terminal's toolbar, input, list and reader positions. **Issues**
is the visible list/reader disclosure for every source. Its right-hand action is
Follow for Terminal, **Refresh My work** for My work, and **Search Jira** for
Search. In a Search reader, that action opens the query field without submitting
it. Terminal and My work use **Filter issues** locally. Search replaces that field
with **Search Jira…**: Enter or the toolbar magnifier submits words or an issue
key to Jira. Search has no second local filter or input mode switch. Typing and
clearing its draft leave submitted results intact until another explicit search.

Collection status, **Cancel**, **Retry** and **Load more** occupy the existing
bottom strip, so loading and pagination do not move the toolbar or reader. Hover
the status for connection/project scope, full status and collection fetch time.
The issue's own fetch time and Refresh remain beside the reader. Load more appears
only in the list while another page is available; it uses the submitted query, not
the draft.

Refreshing My work keeps an open reader while loading and after success if its
issue remains in the refreshed page. Failure or cancellation retains that reader;
if the issue is absent from the refreshed page, the list returns without selecting
another issue. Focus returns to the list only if the removed reader still owns it;
a deliberate focus move is preserved. Issue details keep their own fetch time. A
recoverable My work refresh failure shows **May be stale** and **Retry** in the
footer when results are retained. Retry requests a fresh collection page while
preserving the reader and local filter; it returns focus to the reader or list.
Failed pagination keeps **Load more**. Ready status names **My work** beside the
loaded count; Search keeps its submitted-query status.

Empty states distinguish a new search, searching, no matches for the submitted
query, and an empty page with more pages available. Errors use short footer text;
the full reason, retry guidance and scope remain in its tooltip and accessible
name. Retained results are marked as potentially stale after a failed refresh.

Source switching keeps focus on the activated icon and restores the source's
reader/list view, selection, loaded pages, local filter (Terminal/My work) and
unsubmitted Search draft. **Issues**, Cmd+F, `/` outside inputs and the `search`
command focus the visible field. Opening Issues selects its retained text; Search
Enter always submits, while Up/Down moves from its field to the results for
navigation and Enter to read. Escape in the Search field cancels pending
collection work and focuses results without changing source or draft. Escape in a
remote reader returns to results after closing its active disclosures. Auxiliary
screens keep their own Back/Escape behavior.

Terminal remains the initial source, with its collected keys, local filter,
Follow, unread state and terminal pins. **My work** deliberately loads unresolved
issues assigned to you in the configured projects. Reopening it retains the
session results; Refresh My work requests a new page. **Search** accepts a literal
text phrase or an allowlisted uppercase issue key. Use its Search button or press
Enter in the search field. Typing alone does not fetch, and raw JQL is not
accepted. My work filtering stays local; Enter there opens a loaded result.

Both remote sources show the connection and project scope. Pages contain at most
50 metadata rows; Load more appends unique keys in stable order, up to 200 retained
rows. "Loaded" and "partial" describe this bounded list, not a Jira total. Details
load through the existing reader. Returning to the list retains the selection and
query and focuses the results. Each source retains its native list scroll handle;
the stock host has no readable pixel-offset API, so exact scroll restoration across
unmounts is not guaranteed. Terminal-only actions remain unavailable in remote
sources. Existing `search` focuses the visible filter or Search field; `back`
additionally returns a remote reader to results.

Cancel and source/query changes retire pending results. Requests retain their
occupied slots until completion; selected details have priority within the shared
two-slot budget. Collection failures do not revoke unrelated issue access. Refresh
failures retain loaded results with a stale message. Authentication loss clears
connection state. Rate limiting reports a retry time and blocks collection
submission until that time, including queued work after source switching or
Cancel. Late rate limits from an older connection are ignored. There is no
automatic collection retry or polling.

Discovery requires the REST backend. TWG and the legacy shell bridge retain their
existing issue-reading capability; they do not gain a search transport or silently
switch backends. Explicit search text and generated scoped queries go to Jira only
on deliberate submission/entry. Terminal content never becomes a remote query.
Collection pages are session memory only, with no persistent search cache.
Collection Refresh updates row titles/statuses and local filtering independently of
retained reader bodies. A late issue denial still retires that issue across
retained sources within the same connection; stale connection results are ignored.

Configure source shortcuts in Herdr's personal `keys.json` using the optional
[bindings example](../keys.json): **Alt+1** → Terminal, **Alt+2** → My work,
**Alt+3** → Search Jira, scoped to `mod:jira-peek`. Replace those chords to suit
your preferences. Installation does not overwrite personal shortcuts. These
commands select a source while Peek owns focus; they do not open a hidden panel.
They preserve drafts and views, and leave auxiliary screens untouched. Existing
`jira-peek.search` continues to focus the local results filter.

Options, Fields and Connection use a consistent header Back arrow with a named
destination on hover/focus. Fields keeps Apply in the header; Back/Escape discards
the draft. Connection returns to the screen that opened it.

## Known limitations (full list)

- Offline native checks ran on macOS arm64 with stock **herdr-app 0.1.16** and
  **herdr-core 0.1.21**. Linux GUI, complete screen-reader use, and live
  pointer/keyboard interaction with the 0.1.16–0.1.18 UI/UX additions (Command
  Palette, reader `ScrollHandle`, `Copy quote`, GPU animations, agent status
  chip and row context menu) remain separate from unit tests.
- Linked Issues uses the same native Button disclosure pattern as
  Details/Comments. Its accessible name states expanded/collapsed. Stock
  herdr-app 0.1.15's script Accordion binding drops labels/focus, so no separate
  expanded-state attribute is exposed. Full screen-reader use remains unverified.
- Keyboard-only entry needs **herdr-app 0.1.12 or newer** and the host's pane
  navigation; on older hosts click Issues first. Pane entry and Escape return
  passed the isolated native fixture on herdr-app 0.1.16; the 0.1.16
  checker/window/watch refinements still need a live native check, and unit tests
  do not prove native keyboard behavior. Wheel/trackpad scrolling may still be
  needed for long content, and hiding Peek may reset reading position. Peek ships
  no patched host.
- Polling can miss transient keys or collect a stable fragment. Missing metadata
  does not prove an issue is absent. Rich content is bounded plain text; images,
  active body links, and some content are omitted. Open Jira for complete content
  and current permissions.
- Text selection is pointer-driven and **Cmd+A / Ctrl+A** selects one text block.
  Cross-field, keyboard caret, and screen-reader selection are not promised. The
  host trims outer whitespace on selection copy. Whole-block copying passed
  isolated native checks; partial-drag copying remains inconclusive. Check the
  pasted content, or use **Copy issue as Markdown**. See
  [selection details](FEATURE-DICTIONARY.md#jp-042--selectable-reader-text).
- Clipboard copies can expose private issue content and persist in history or OS
  sync. Markdown copy includes configured Details even when collapsed and loaded
  comments; Hidden fields are excluded, with no additional redaction. Treat copied
  text as data, never shell commands, and review before pasting into a renderer or
  agent. See [clipboard limits](FEATURE-DICTIONARY.md#jp-041--copy-issue-as-markdown)
  and [security and cleanup rules](../SECURITY.md).
- Hiding retains panel memory; removing it or quitting discards that memory.
  Credentials, disk caches, clipboard, and backups have separate lifetimes. Peek
  targets stock herdr-app and ships no patched host; historical source highlighting
  and native input patches are retired.
