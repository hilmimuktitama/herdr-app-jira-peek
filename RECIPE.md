# Jira Peek

A native Jira reader beside the terminal you are working in. Issue keys arrive
automatically; deliberate reading stays put. Colors and typography follow Herdr.

![Jira Peek with entirely fictional issue and terminal content](preview.png)

**Experimental 0.9.1. AI-assisted — use with caution.** Developed with AI
assistance and provided as-is under the [MIT License](LICENSE), without warranty.
Collaboration, pull requests, issue reports, feature requests and support are
closed for now. See the [project policy](CONTRIBUTING.md) and [security policy](SECURITY.md).

## What you see

A right panel with Issues, an icon button for Following/Paused, Options and a close control. The
current issue's key, status, title, fetch time and actions lead the reader.
Descriptions are directly readable; Details and Comments reveal more content.
Open in Jira, copy and refresh remain accessible above the scrolling body.
The heading, actions and reading text share an aligned gutter. Compact spacing
groups issue identity and metadata; straight separators organize disclosures.
Titles lead the reading hierarchy; smaller metadata and a consistent spacing
rhythm keep controls quiet. The complete fetched date and UTC time stay visible
at narrow widths, wrapping when needed. Rows grow with Herdr's UI font.
Reading surfaces keep a full accent outline while focused and a quiet boundary
otherwise. Help uses its empty footer space while preserving the hidden reader's
viewport and reading position; focused icon captions still have their own strip.

Issues is one expandable disclosure with a focused filter and stable list.
Filtering previews the matching selection or the first match without another
action. Enter collapses results for full reading; reopening keeps the query
and browsing order. Every matching ticket keeps its row and a visible highlight marks the
selection. Up/Down moves the highlight without reordering results;
scrolling reveals the selected row only when it leaves the viewport.
The selected result keeps its key, status and copy/pin actions on one row,
with no selection checkmark or repeated identity below the list. Collapsed
reading keeps one identity/action row above the body.
Long statuses truncate with a tooltip; the fetched timestamp and Refresh stay underneath.
Filtered results use individually sized keys, full-width titles and quiet
row dividers. Status follows each key with a consistent gap; long keys do not
widen other rows. The key's hover button fits its text inside its bounded slot.
Long keys truncate with their full identity in the Open tooltip.
Rows stay top-aligned and keep the same key clipping when selection changes.
Balanced vertical padding separates tickets without shrinking the
32px action targets. Rows and the filter grow with host typography; the viewport
defaults to complete rows. Drag its bottom border to resize smoothly up to four
rows, without snapping during drag or release. The choice lasts for the panel
session. Short panels scroll together when needed. This follows the compact
spacing and semantic grouping in
[Atlassian's spacing guidance](https://atlassian.design/foundations/spacing) and
the distinct action targets in [Carbon's table guidance](https://carbondesignsystem.com/components/data-table/usage/).
Its complete default title leads the scrolling reader at every height.
Custom layouts stay intact. While Paused, newly captured or newly matching
issues join the bottom automatically. The existing row order and list height
stay stable during arrivals; selection and scroll stay put. Live metadata
filtering and the 200-issue limit may remove rows. The key opens Jira without a logo.
Copy key, Copy link and Pin appear as one group on the hovered row; its actions
work without selecting it first. The pinned row keeps its accent pin visible
and keyboard-focused controls stay visible. Loading/queued progress and
“Refreshing the issue…” sit immediately left of Refresh. While busy, its tooltip retains the last fetch time; the visible timestamp
returns afterward. Failure feedback and Retry remain separate.
Enabled buttons, clickable keys and available result rows and titles use a pointing-hand cursor.
Copy feedback and shortcuts remain available.
The Follow icon shows the next action: pause while Following, play while Paused.
Its short tooltip names the action and shortcut; pausing keeps the selection
while new issues collect, and resuming selects the latest issue and clears the
filter. Control tooltips stay brief; Help holds detailed instructions. Tooltips
for clipped values, source identity and fetch time retain their content. There is no visible
match counter; the selected position remains in its accessible name.
New unread activity sits beside navigation without moving the issue actions.
Options and Help use an explicit
return to Issues; form Help preserves drafts. Empty fields stay hidden by default.
Long titles scroll with the body while key/actions stay above it.
Short panels budget a smaller list beside a readable preview; extremely short
panels scroll the content together rather than hiding the selected ticket.
The footer shows the current reading/search keys and keeps **? Keys** within
reach. The guide leads with the daily Find → Read → Back loop; other actions
live under More shortcuts. Enter reads inside Peek; Cmd+Enter or Ctrl+Enter
explicitly opens Jira from nonediting issue contexts. Native buttons retain
Enter/Space activation. Comments and Details show their keys; C/D focus those
disclosures, F toggles Follow, and N reads
one unread issue. Keyboard reading pauses Follow without losing the query.
P or the inline pin keeps one issue for this terminal; P again unpins it.
Pinning a different issue moves the pin immediately. During a detour, the existing
footer offers Return to KEY; K returns without clearing the filter. There is no
management screen or added row. Copy key/link, Copy issue as Markdown, Open and
Refresh target the viewed issue; the Markdown copy is built only from loaded
fields and comments, with Hidden fields excluded.

## How it behaves

Use the [product dictionary](docs/FEATURE-DICTIONARY.md) to identify feature
contracts and coupled checks before adapting behavior.
Use the [reliability guide](docs/RELIABILITY.md) for stack references,
failure injection, native acceptance checks and unresolved reliability gaps.

- Read explicitly addressed terminal screens with `hc read --lines 0`.
  Read history only when requested, up to 200 available lines. Do not send
  terminal input, scroll the terminal, or move focus during discovery.
- Start each new source Paused, collecting unread keys without Jira issue or
  metadata reads. Selection, deliberate filter edits or resuming Follow activates
  loading for that source for the session. Keep activation across Clear list and
  source return; reset it on reconnect or eviction. After activation, retain
  normal Paused metadata collection. Follow the latest visible allowlisted key.
  User reading/filtering/selection pauses Follow. Append new matches to the browsing order automatically,
  keeping selection, filter and list height during incoming discovery. Canonical
  recency stays separate for Follow, requests and retention. Query edits rebuild
  matches; acknowledge one issue when reading the unread badge.
- Confirm new screen keys in two observations at least 250ms apart, with one
  bounded extra read per scan. History and direct lookup are deliberate and
  immediate. Distinguish missing, loading and unavailable titles without
  treating a missing metadata row as proof that an issue does not exist.
- Clear list resets only the current terminal's collected issues, query, unread
  keys and issue pin. Preserve Follow/Paused, other sources and caches. Establish
  a fresh complete screen baseline, suppress its continuously visible keys,
  and reject pre-clear results without freeing occupied request slots early.
- Keep this terminal retains one exact source; the panel shows Keeping this
  terminal while it is enabled. Keep machine-qualified addresses distinct;
  Jira authentication and requests remain local even for remote terminals.
- Issue pins retain one key per source within the existing 200-key/12-source
  bounds, without retaining an extra body. They are session-only and reset with
  connection/cache state. Pinning is a direct, reversible action on the currently
  viewed issue. Never pin an issue for a manual source or infer a task.
- Search loaded metadata or look up an allowed key/same-origin Jira browse URL.
  Reject foreign origins and disallowed projects. Preview matching results
  when the filter changes or results are updated, keeping unknown lookups
  explicit through Enter. Unmatched queries show No matches, including valid
  issue keys, without a separate lookup prompt. Hidden filtered selections
  cannot own browsing actions or requests.
  Deliberate unread/pin/direct reader entry remains actionable outside the
  saved filter; reopening results invalidates that reader entry until chosen again.
- Request issue details on selection, reuse valid caches, and keep at most two
  issue/metadata reads in flight. Prioritize the latest selection and preserve
  loaded content on refresh failure. Protect newer searchable rows independently
  of detail-body eviction. With REST, load comments separately.
- Default auto-refresh off. When enabled, refresh at most once per minute,
  pause only the idle panel after five minutes, preserve the shared saved choice,
  and show actual fetch time. Resume is local; turning it Off is shared.
- Share field layouts and reader preferences through the versioned
  `data/jira-peek/fields.json`. Validate edits, preserve last valid state, reject
  stale UI writes, and keep this file outside managed source. Use the
  [installed agent contract](docs/AGENT-GUIDE.md) and
  [schema](mods/jira-peek/fields.schema.json).
- Hide/reopen through a persistent personal toolbar toggle. On stock hosts,
  click Issues to enter Peek; Cmd+F and Tab work once it owns keyboard focus.
  Reliable terminal-to-panel keyboard entry remains unshipped. Retain native
  text editing and focus behavior.

## Built from

**herdr-app >= 0.1.10** is the desktop UI/mod host. **herdr-core** is the separate
terminal backend exposed as `hc`; the installer requires it on PATH without a
numeric core minimum. Check `herdr-app --version` and `hc --version` separately.
Keep **0.1.10** exact; never substitute **1.10.0** or a core/TUI version.

Use the complete source ZIP or checkout, including `scripts/`. Copying only
`mods/jira-peek` omits its runtime. From the source root:

```sh
python3 scripts/install-app.py --doctor
python3 scripts/install-app.py --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

`--attach` creates a personal layout and Jira Peek toolbar toggle, preserves
originals and shortcuts, and refuses conflicts. Use `--attach YOUR_LAYOUT` for
a different layout using stock tabs or a compatible personal toolbar clone.
Use `python3 scripts/update-app.py --diagnose-integration` to inspect the active
layout, then `--repair-integration YOUR_LAYOUT` to prepare its personal copy.
Repair preserves custom controls and reuses an existing Peek panel ID; select
the printed layout explicitly. Unsupported structures receive manual guidance.
Later installs use `--update --check`; the
[update guide](docs/MAINTENANCE.md#update) explains private-preview
0.1.0 migration, numbered releases and rollback. Updates protect edited files
and retain the complete prior bundle. No personal layouts ship in this repository.

Use native GPUI controls, theme colors, argument-array execution and bounded
state. `demo.js` supplies wholly fictional content only when `props.demo` is
true; live operation must never silently fall back to the demo. Installed
`AGENTS.md` documents settings and native commands.

`model.js` owns issue-state transitions, projection ordering and retention;
`main.js` owns native interaction and asynchronous scheduling. The JSON bridge
loads `common.sh` for configuration, connection epochs and cached Jira reads.
That runtime contains no terminal-viewer lifecycle or pane commands. Cache misses
reserve ordered attempts before transport, preventing older completions from
publishing over newer attempts. Publication locks recover old empty directories
after a grace period. Installation replacement journals the exact backup so a
later mutating invocation can recover a missing active bundle after interruption.
Native batch and detail projections share `fields.jq`; preserve its privacy rules
and picker bounds when adding a read path. Keep these helpers in one module:
nested calls between these projection modules abort in jq 1.8.2. Reader rich
text has separate bounds.

Do not rebuild the host during ordinary installation. Jira Peek targets stock
hosts and ships no patched host; the historical input and highlighting
extensions are retired. Stock-host input, scrolling and accessibility limits
remain documented. The optional [keys.json](keys.json) has only
mod-scoped F2/F5 bindings; merge individual entries without replacing existing
keys.
See [toolbar integration](docs/PANEL-INTEGRATION.md) for custom layouts.

## Watch out

Review the code and [known limitations](README.md#known-limitations), test in an
isolated app home, back up settings and grant only necessary Jira access.
No support, fixes or release schedule are promised.

This mod runs local programs and reads terminal content. It makes read-only
Jira requests but an account/token may have broader permissions. Credentials
and issue caches use private local files, not an encrypted keychain. Read
[SECURITY.md](SECURITY.md) for permissions, retention and cleanup limits.

Never render issue bodies as active HTML/Markdown or send their text through a
shell. Mark unsupported/shortened content. Preserve connection/source boundaries
and reject stale responses. Hiding a panel does not close its in-memory state.
Stock-host input gaps, Linux GUI and accessibility limits remain documented.

## Done when

- The assembled mod passes Herdr's native checker and renders in an isolated app.
- Following, Browse, filtering, pinning and unread navigation preserve their
  documented state through asynchronous discovery and failures.
- Setup, fields and Help retain drafts and give errors without exposing secrets.
- Reader actions remain named and available at narrow widths, with hover and
  keyboard focus revealing browsing controls; text remains readable.
- The installer preserves private configuration, layouts, shortcuts and local edits.
- No optional host build is required; stock-host limitations are checked
  separately.
- Shared captures use only the [fictional fixtures](docs/screenshots/README.md).
