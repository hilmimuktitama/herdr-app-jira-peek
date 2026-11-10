# Jira Peek product and feature dictionary

This is the intended behavior baseline for the current working source, based on
**0.7.0 experimental**.
Use it to name features, assess change impact, and preserve existing functionality.
The [README](../README.md) explains daily use; the
[agent guide](AGENT-GUIDE.md) specifies supported configuration and commands.
This dictionary connects those instructions to implementation and regression checks.

Feature IDs are stable references. Keep an ID when wording or implementation
changes; give a new capability a new ID. Retire an ID explicitly rather than
reusing it. Entries describe intended behavior of this working source, including current working
changes; **optional host extension** and **development only** are marked. A
preservation rule is a requirement, not proof of release or validation.

Start with the [vocabulary](#vocabulary), then use these feature groups:

- [Discovery and reading intent](#discovery-and-reading-intent): JP-001–013.
- [Navigation and host integration](#navigation-and-host-integration): JP-014–020.
- [Connection and configurable fields](#connection-and-configurable-fields): JP-021–025.
- [Data loading, freshness and privacy](#data-loading-freshness-and-privacy): JP-026–035.
- [Clipboard output](#clipboard-output): JP-041–042.
- [Installation, updates and evidence](#installation-updates-and-evidence): JP-036–040.
- [State lifetimes](#state-lifetime-reference) and [change preservation workflow](#change-preservation-workflow).

## Vocabulary

| Term | Meaning in Jira Peek |
| --- | --- |
| Jira Peek / Peek | The native GPUI Jira reader mod, ID `jira-peek`. The separate Herdr TUI edition has independent behavior and releases. |
| herdr-app | Desktop UI/mod host; requires **0.1.10 or newer**, never `1.10.0`. |
| herdr-core / hc | Separate terminal backend and CLI. `hc` must be on PATH; no numeric core minimum is enforced. |
| App home | Host configuration/data root, selected by `--app-home` or `HERDR_APP_HOME`, normally `~/.config/herdr-app`. |
| Panel copy | One running instance of Peek. Multiple copies can share saved preferences while retaining separate session state. |
| Attached panel / overlay | A block in a personal layout / a separately opened mod surface. Hiding one must target the correct surface. |
| Source | Exact live terminal address, including machine identity. A manual lookup session can exist without a terminal. |
| Connection | Selected private configuration folder and its validated Jira/backend context. Field entries match configuration directory and browse origin; disk namespaces use directory filesystem identity. |
| Project allowlist | Explicit configured project keys eligible for requests. It does not grant Jira permissions or redact locally read terminal text. |
| Candidate / confirmed key | A newly observed screen key awaiting settling / a key admitted after repeated observation. |
| Collected issue | A key in this source's in-memory list. It may have no loaded metadata or body yet. |
| Metadata / projection | Searchable key, summary, status and configured picker values, retained independently of full bodies. |
| Logical selection / actionable issue | The source's retained reading target / the issue currently eligible for visible actions. Filtering can exclude a logical selection. Unread navigation and returning to a pin can deliberately read outside the retained query. |
| Text selection | A native pointer selection inside rendered reader prose. It is separate from the logical issue selection and does not grant actions on another issue. |
| Following / Paused | Whether discoveries may change selection. Paused still permits terminal scanning and unread collection. |
| Unread / +new | Collected arrivals not yet deliberately acknowledged. Reading one does not acknowledge all arrivals. |
| Issue pin | One temporary return-to issue key per terminal source and connection. P and K operate on this feature. |
| Keep this terminal / source pin | Keeps discovery on one terminal while focus moves elsewhere. The commands `pin`/`unpin` operate on this feature. |
| Scan / issue refresh | Read terminal keys / request Jira data again. These are independent operations and settings. |
| Fetch time | Timestamp of the fetched payload, including disk-cache hits. It is not proof of current Jira state or access. |
| Field layout | Ordered IDs, labels, sections and empty-value policy for one connection, shared across its projects and issue types. |
| Draft | Unsaved Fields/setup values; Help can cover a draft without discarding it. |
| Epoch / generation | Internal invalidation identity used to reject results from a previous connection or cache state. |
| Prepared / active / rendered integration | Personal files exist / host selects that layout / a native inspection confirms the button is visible. These are separate claims. |

## Discovery and reading intent

Implementation: [model](../mods/jira-peek/model.js),
[controller and native UI](../mods/jira-peek/main.js).
Regression evidence: [model tests](../tests/model.test.js),
[controller tests](../tests/controller.test.js), [view tests](../tests/view.test.js).

### JP-001 — Passive screen discovery

Read the focused live terminal explicitly through `hc read --lines 0`, collecting
standard uppercase Jira keys only from allowlisted projects. Deduplicate by last
occurrence, with the latest visible key as the Follow target. Preserve exact
machine-qualified identity; never send terminal input, scroll it, or move focus
as a consequence of discovery. Unchanged scans do not authenticate or refetch Jira.

### JP-002 — Screen-key settling

New screen keys require two successful observations at least 250ms apart.
An ordinary or explicit scan can schedule one extra confirmation, without
recursive polling. History and direct lookup bypass settling. Preserve bounded
screen reads and conservative handling of incomplete observations. A stable
fragment can still be collected; polling can miss short-lived keys.

### JP-003 — Scan screen and Read history

Options provides deliberate visible-screen scanning and up to 200 available
history lines. History neither scrolls nor sends input, and may be absent for
alternate screens. Serialize/coalesce overlapping reads and discard stale source
responses. Manual scans remain available when automatic scanning is disabled.

### JP-004 — Following and deliberate reading

New sources start Paused and inactive, with stable append ordering from their
first discovery. Collect unread keys without Jira issue/metadata requests until
Follow, deliberate selection (including lookup/+new) or a user filter edit
activates loading. Query restoration, opening Issues and passive previews do not
activate a source. Keep activation across Clear list and source return; reset it
on connection reset or source eviction. Activation is session-only, separate
from Follow and saved auto-refresh. Once activated, normal Paused metadata
collection continues. With keys but no selection, guide the user to select an
issue or resume Follow.

The icon-only Follow button shows the next action: pause while Following, play
while Paused. Its accessible name, focus caption and short tooltip name that
action. The resume tooltip notes that it clears the filter. Do not use pressed
styling as a second meaning for the icon. Paused still collects discoveries.
Following selects the latest visible confirmed key, including a revisited known
key. Selection, filtering, reader interaction, Tab traversal and keyboard reading
pause Follow. Incoming matching keys and metadata matches append to the paused browsing order
without growing its viewport or acknowledging unread issues. Preserve existing
selection, query and scroll; removals can shift rows.
Resuming Follow chooses the latest observation, clears the query and acknowledges
the collected unread set; move focus
out of a disclosure before a selection change can remove it.

### JP-005 — Unread navigation

While Paused, arrivals remain unread. **+new**, N or `unseen` reads and
acknowledges one issue while preserving Paused and the prior query. Keep the badge
beside Issues without a visible match counter or shifting reader actions. Passive previews must not silently acknowledge arrivals.

### JP-006 — Source sessions and Keep this terminal

Switching terminals restores separate collected keys, selection, query, unread
state, Follow state and issue pin. Keep this terminal retains the exact source
while other tabs receive focus and shows **Keeping this terminal**. It does not
focus that terminal. Remote sources still use local Jira credentials and requests.
Evict older sessions within the 12-source bound.

### JP-007 — Clear list

Forget only this terminal's collected keys, query, unread state and issue pin.
Preserve Following/Paused, Keep this terminal, other sources, saved settings and
disk caches. A fresh post-clear complete screen establishes the suppression
baseline; continuously visible keys remain ignored until observed absent and
then reappearing. Incomplete or over-200-key baselines wait for a smaller complete
screen. Explicit Scan screen, history and lookup can restore old keys. Reject
pre-clear responses without releasing their occupied request slots early.

### JP-008 — Issues list and local filtering

Expanding Issues focuses the filter; all search words match loaded keys, titles,
statuses and configured picker values. Preview a matching selection or the first
result immediately. A matching pinned issue stays visible at the top while the list scrolls; a nonmatching pin remains saved without bypassing the filter. Unpinning restores the underlying browsing order. Arrows/clicks preview while keeping the list open; Enter
collapses it for reading. Reopening retains query and list position. While browsing, a filtered-out
selection cannot own copy/open/refresh, highlighting or hidden body requests.
Explicit unread, pin-return or direct-lookup entry may read outside the saved
query; reopening Issues restores filter eligibility.
Show No matches when the query has no loaded results, including valid issue keys;
do not replace the empty state or add a separate lookup prompt for them.
Keep loading, failed and unavailable titles distinct; missing metadata does not
prove that an issue does not exist.
Only the hovered row reveals its copy and pin controls, immediately and without
selection. Row actions preserve the preview, query and unread state; copying
does not scroll or request details. Keyboard-focused controls remain visible.

### JP-009 — Direct issue lookup

Explicitly look up an allowlisted key or HTTPS `/browse/KEY` URL on the configured
origin, including without a terminal. Reject foreign origins, credentials in
URLs and disallowed projects before making requests. Invalid input preserves
the current selection. Enter commits an explicitly previewed visible result;
unknown keys require explicit lookup with Enter in the filter. A matching
hyphenated title remains selectable without bypassing URL validation.

### JP-010 — Issue reader and responsive presentation

Keep control tooltips to a short action and shortcut, adding only essential
consequences. Put detailed instructions in Help; preserve full clipped-value,
source-identity and fetch-time tooltips.
Show the selected issue's identity, title, complete bounded description and
actions. A slow issue can show its known title but must never borrow another
issue's description. In browsing, default title/status come from the selected
row; filtered results share one bounded key column, so status starts at the same
position for short and long keys whether selected or unselected. Copy and pin
use the same 32-pixel header targets in both states;
the summary keeps the full content width, and clicking it selects the issue.
Use one shared row geometry for selected, hovered and pinned results: balanced
vertical insets, a quieter metadata line, and subtle dividers. Default rows are
64 logical pixels and grow with host typography. The filter grows with larger
fonts. List budgets include their border and end on complete rows; Page Up/Down
uses that visible page. Long summaries and statuses retain bounded tooltips.
Customized labels/placement remain intact. Short panels reduce list height
and retain a preview; extremely short panels scroll together. Follow host theme,
UI font size and zoom without applying zoom twice. Keep selected rows distinct
from hover and retain accessible control names and focus indicators.
If the host discards an unmounted retained row, recreate it without stopping
subsequent row updates. Painted identity/title and action targets must agree
after hide/reopen, Clear list, direct lookups and pin placement changes.
Arrow and pointer selection refresh the retained row before the event returns,
so the first navigation frame does not briefly paint the previous ticket.
Retain action views only for the native viewport (at most six scrolling rows
plus a fixed pin), alongside two selected-row views. Allocate outside render
and layout: virtual-list range requests only record the requested interval, and
the panel's native timer performs the allocation. Release outgoing actions
before allocating replacements, and never recreate dormant actions on passive
refresh. Closing releases all retained rows.
Cached native layout must wake allocation without another panel event or scan.
A panel-owned 100ms native timer processes pending requests outside layout;
idle ticks do not invalidate views, redraw, fetch data or renew activity, and
closing cancels the timer.

### JP-011 — Details and Comments disclosures

Details reveals configured secondary fields and fetch information; Comments
reveals discussion. Both pause Follow, survive a same-issue refresh, and reset
for a different issue/source. C/D respect visibility and placement, including
comments in Details, and reveal/focus the disclosure on capable hosts. The
description remains readable when comments are loading, empty or failed.

### JP-012 — Copy, Open in Jira and feedback

Click the issue key to open it or use Y to copy it; Shift+Y copies its link. Open in Jira or
Cmd+Enter/Ctrl+Enter opens the actionable viewed issue using a validated link
built from the configured origin. Actions target the viewed issue during a pin
detour. Copy feedback changes its icon without shifting controls or hiding
errors. Held browser chords must not open repeated tabs.
Reject queued issue actions after selection, filter eligibility, source, connection
or auxiliary-screen context changes; an old row must never act on a new issue.
Copy issue as Markdown is the separate JP-041 action; it uses the same viewed-issue
lease and footer feedback but has no reader icon or default key.

### JP-013 — Issue pin and return

Scrollbar focus recovery belongs only to the scrolling viewport; the fixed
selected pin keeps its action focus through pointer activation.

P or the inline pin toggles the viewed issue; pinning another moves the pin
immediately. K or **Return to KEY** returns to its reader, pauses Follow and
preserves query and unrelated unread issues. Store only one key per terminal
source/connection within normal bounds, with no additional retained body. Pinning
pauses Follow. Matching pins remain visible atop the scrolling result list without retaining an extra body.
The pinned row keeps an accent pin visible when not hovered and offers one-click
unpin without first selecting it. Pinning an unselected row preserves the preview.
Repeated pointer pin/unpin cycles must work after native row disposal, including
when the selected result moves between the fixed and scrolling list positions.
Manual sources cannot pin. Hiding preserves it; Clear list, reconnect, Clear
cache, source eviction and panel destruction remove it. P/K remain text in inputs.

## Navigation and host integration

Implementation: [native UI](../mods/jira-peek/main.js),
[installer](../scripts/install-app.py), [keys example](../keys.json).
Regression evidence: [view tests](../tests/view.test.js),
[toolbar tests](../tests/toolbar.test.js), [installation tests](../tests/install_test.py).
Host procedures: [panel integration](PANEL-INTEGRATION.md).

### JP-014 — Keyboard ownership and Back

On stock hosts, click Issues to enter Peek; local Cmd+F focuses search. Enter
reads inside Peek, while native buttons keep Enter/Space activation. Letter
shortcuts leave inputs/forms alone; modified host chords and native Tab traversal
remain available. Escape closes disclosures, then collapses Issues retaining the
query, then returns to the actual terminal. With no matches it clears the query
first. Do not return to a vanished or mismatched terminal. Reliable keyboard-only
terminal-to-panel entry is not shipped; stock reader scrolling needs a wheel/trackpad.

### JP-015 — Options, Help and form navigation

Options and general Help are sibling screens; **← Issues** returns directly to
the retained reader/filter. Help opens collapsed topics, with arrows/Home/End
navigation and Enter/Space expansion. **? Keys** leads with daily keys and places
the rest under More shortcuts. Form Help retains drafts and returns to the form.
Do not allow delayed callbacks to focus covered/unmounted inputs, or reader
shortcuts to act behind auxiliary screens. Busy setup cannot be dismissed.

### JP-016 — Native commands and shortcuts

`herdr-app do jira-peek.<command>` shares native handlers with mod keybindings.
Preserve the [complete command table](AGENT-GUIDE.md#native-actions), including
idempotent `pause`/`resume`, source `pin`/`unpin`, navigation, setup and read actions.
Dispatch reaches shown copies and requires normal prerequisites; OK is not proof
of a successful load. The optional F2/F5 example is mod-scoped. The installer
never installs shortcuts or captures global Cmd+F.

### JP-017 — Show, hide and toolbar toggle

The personal Jira Peek toolbar button toggles its actual attached block ID;
**×** hides that panel, or closes its overlay without closing an attached copy.
Preserve surviving session state through hide/show; stock hosts may reset reader
scroll. A generated button follows visibility, appears beside Changes, preserves
custom controls/handlers and stops toolbar dragging. Do not use `mod.open` to
reopen an attached panel.

### JP-018 — Personal layout attachment and repair

`--attach` prepares separately named layout/toolbar copies, preserving shipped
layouts, keys and personal edits. Reuse an existing Peek block's actual ID and
width; refuse duplicate IDs, conflicting files and unsupported structures.
Compatible personal tabs clones retain controls, imports and supporting files.
Diagnosis is read-only and distinguishes validated bundle, prepared files, active
selection and visible rendering. Offline repair changes personal integration
files and prints a layout to select; it does not switch the active layout.

### JP-019 — Source highlighting (optional host extension)

Highlight occurrences of the actionable selected key in its exact live source
only when the renderer API is available. Save only the on/off preference;
decoration must not alter terminal text, send input or fetch Jira. Clear marks
on disable, invalidation and copy retirement; hidden copies do not paint.
Contain API failures and avoid repeated render retries. Stock hosts show the
option as unavailable. Follow the separately version-pinned
[extension guide](../native/APP-HIGHLIGHT.md).

### JP-020 — Native input extensions (optional host extension)

The historical [input patch](../native/APP-INPUT.md) adds synchronous entry,
keyboard scrolling, focus reveal and retained scroll behavior. Treat its
capabilities separately from stock installation and source highlighting. No
patched binary is shipped; a version string alone cannot establish patch
presence. Do not add custom-host commands to stock key examples.

## Connection and configurable fields

Implementation: [native UI](../mods/jira-peek/main.js),
[setup helper](../scripts/app-setup.py), [config parser](../scripts/common.sh),
[field model](../mods/jira-peek/model.js), [schema](../mods/jira-peek/fields.schema.json).
Regression evidence: [setup controller](../tests/setup-controller.test.js),
[setup helper](../tests/setup_test.py), [field layout](../tests/field-layout.test.js),
[view](../tests/view.test.js) and [bridge tests](../tests/bridge_test.py).

### JP-021 — Set up Jira and Test & save

Accept Jira Cloud site, email, projects, masked token and optional scoped-token
Cloud ID. Offer the fixed API-token guide. Validate destinations and perform a
read-only account check before activating a private managed connection. Reject
redirects and unsupported destinations. Failed verification preserves the
previous connection; tokens are never prefilled and must be re-entered to retry.
Cancel discards unsaved values. Prevent duplicate saves, stale activation and
cancellation during a busy transaction. Account checks do not prove issue access.
For scoped tokens, verify that the browse origin reports the supplied Cloud ID
through `/_edge/tenant_info` before the authenticated account check. This
association lookup sends no credentials; a mismatch or failed lookup preserves
the previous connection.

### JP-022 — Existing connection and backend selection

Choose the folder containing a private declarative `config.sh`; remember its
path without copying private configuration into the mod. Support configured
TWG OAuth or REST/netrc, including scoped gateway routing. Reconnect reloads the
chosen configuration. Parse allowlisted assignments as data, never executable
shell. REST must not silently fall back to TWG. Preserve prior settings when
the folder picker is cancelled and ignore late results after navigation away.
Existing REST gateway configurations verify the same origin/Cloud-ID association
before returning data, once per connection epoch. Cached reads reuse that
verification; stamp and Clear stay local-only. An unverifiable association fails
closed, including when its endpoint is unavailable.

### JP-023 — Runtime configuration vocabulary

The [agent settings table](AGENT-GUIDE.md#connection-and-data-settings) and
[configuration template](../config.example.sh) define backend/site/projects,
scan interval, cache TTL, metadata preload, requested fields and labels. Preserve
validation, defaults and empty field lists. Backend edits require reconnect.
Imported `KEY_RE`, `PICKER_LAYOUT`, `SOURCE_HIGHLIGHT`, `TEXT_STYLE` and
`COLOR_THEME` do not control native matching/presentation. `PREVIEW_FIELDS` can
affect fetching but does not arrange the native reader.
Custom IDs use `customfield_` followed by 1–12 digits in shell configuration,
native layouts and the shared schema. Overlong IDs are rejected by configuration
validation rather than silently omitted from the native defaults.

### JP-024 — Fields editor

One connection-wide layout controls Header, Body, Details and Hidden placement,
order, labels and Show empty fields. Support standard IDs and known custom IDs,
up to 32 unique fields; comments cannot occupy Header. There is no site field
catalog discovery. Apply saves; Back/Escape discards; Reset restores configured
defaults in the draft. Keep key/Open available. Preserve zero/false values,
custom labels and explicit placement; layout changes never edit Jira screens.

### JP-025 — Shared agent configuration and safe reload

UI and agents share versioned `data/jira-peek/fields.json`; Copy config path
reveals its path. Field entries use exact connection identity; root preferences
are shared across panels. Validate complete edits, retain the last valid state,
preserve other connections, and reject stale concurrent UI writes. Failed saves
retain drafts. Migrate legacy preferences without losing layouts. Label/order
edits reuse data; requested-field changes invalidate affected requests and reload.
Updates preserve this file. Follow the [agent contract](AGENT-GUIDE.md).

## Data loading, freshness and privacy

Implementation: [controller](../mods/jira-peek/main.js),
[model](../mods/jira-peek/model.js), [bridge](../scripts/app-bridge.sh),
[REST adapter](../scripts/jira-rest.sh), [field planner](../scripts/field-plan.sh).
Regression evidence: [controller](../tests/controller.test.js),
[model](../tests/model.test.js), [view](../tests/view.test.js),
[presentation](../tests/presentation.test.js) and [bridge tests](../tests/bridge_test.py).
Data policy: [SECURITY.md](../SECURITY.md).

### JP-026 — Selected-issue priority and request bounds

Load details on selection, prioritizing the latest choice over metadata work.
Allow at most two issue/metadata reads, no duplicate same-key request, and
coalesce rapid choices. Stale completions release only their own markers/slots.
Newer row projections must survive late metadata even after body eviction.
Before source activation, schedule neither passive issue requests nor metadata.
Deliberate filter edits activate and pump even when no loaded rows match.
Preload missing metadata only within configured candidate bounds; successful
omissions settle without an automatic retry loop.

### JP-027 — Deferred comments

REST loads comments separately from the core issue so slow discussion does not
block the description or another selection. Retry comments independently without
changing the issue fetch time. Bound output to one recent page, up to 100
comments, and explain partial/unsupported content. Reject stale comment results
as soon as refresh begins, including while its body request is pending or fails,
and after field changes, clear, close or connection changes. Keep retired comment
work counted until it settles; replacement comments wait for the same-key body
request to settle. Do not claim
identical deferred transport behavior for TWG.

### JP-028 — Manual refresh, failure and retry

The compact Refresh button follows the freshness label. Initial loading, debounce,
queued work and cooldown appear once in that label; refresh uses **Refreshing the
issue…** immediately left of the icon. Keep errors and Retry separate, retain
known titles and loaded bodies, and do not replace unavailable details with
indefinite loading. Refresh forces a request for the actionable issue; a failed
refresh retains its last successful content and fetch time with Retry. Passive failures use bounded
cooldown rather than repeated scans/authentication; deliberate selection and
manual retry can recover. Manual refresh can retry failed metadata for the current
source without retrying settled omissions. A failure from an unrelated old
request must not replace the current issue's feedback or stall queued work.

### JP-029 — Auto-refresh issue and local idle pause

Off for new users. When enabled, refresh the selected issue at most once per
60 seconds, skipping busy work and respecting retry cooldown. Five minutes
without actual panel interaction pauses only that panel, retaining the shared
saved opt-in. Passive scans, reloads and automatic work do not renew activity.
Resume from Options is local; turning active refresh Off changes the shared
preference. Hide/reopen and reconnect retain local pause; another panel's On
cannot resume it. A new copy uses the saved choice. Hidden active copies can
refresh within their lease.

### JP-030 — Fetch time and date presentation

Display the payload's fetch time beside Refresh, including cache hits. While
progress replaces the visible time, retain the last successful fetch time in the
tooltip and accessible label, then restore it afterward. Never invent a time for
an unloaded issue. Preserve it on refresh failure. Compact layouts retain the complete date and UTC time, wrapping when needed;
tooltip/accessibility text and Details repeat that information. Cache reads do not
restart freshness. Format supported dates in UTC and preserve invalid/custom
values. Neither a timestamp nor cached content proves live permissions or
current Jira state.

### JP-031 — Memory, disk cache and zero TTL

Bound memory to 200 keys per source, 12 sources and 40 full details. Keep
searchable projections independently of full bodies. Durable issue cache obeys
TTL and connection/field-set identity. Cache misses reserve ordered attempts;
a later attempt supersedes earlier in-flight responses, even if it fails.
Failure-side cache invalidation and diagnostics check the attempt generation
under the same locks as publication. Before projecting a canonical cache file,
revalidate its key and field signature under the connection lock; reject a
replacement with another request's field set instead of reporting missing data.
Old empty publication locks recover after an age grace period; fresh or occupied
locks are preserved. Folder aliases share device/inode-based
namespaces; distinct folders retain independent caches/epochs. TTL zero disables
durable caching and retains only the current source's logical body, including
while excluded by a filter, covered by a form/Help or hidden. Selecting another
key retires it; returning can refetch. A pin does not extend body retention.

### JP-032 — Clear cache and reconnect invalidation

Clear cache clears the invoking panel's issue memory and its configuration
folder's disk issue cache, advances invalidation state and reconnects. Retain
credentials, config and saved UI choices; leave other folders and the legacy
shared cache alone. Reconnect resets issue/source sessions and pins. Watch
config/epoch drift and reject old responses before display or cache publication.
Other copies on the same folder can subsequently rediscover/refetch.
The standalone `clear-cache.sh` helper accepts an initialized connection state
directory, not the shared state root. Reject unresolved roots without clearing
their legacy cache or creating a misleading root-level epoch.

### JP-033 — Permission and connection errors

Issue permission denial retires only that issue; authentication loss or context
mismatch invalidates the connection and rejects late success. Report fixed,
actionable errors without raw transport output, credentials or foreign payloads.
Revocation is detected on subsequent backend requests, not continuous polling.
Keep connection/form navigation usable for recovery without stealing focus.
REST HTTP 403 and explicit TWG permission status/code failures share issue-local
retirement. Recognize failed single-item TWG envelopes even with exit status
zero. Ordinary transport errors retain previous content; issue text containing
permission-related words is not an authorization signal.

### JP-034 — Plain-text rich content

Render bounded plain text from supported Jira rich text, preserving useful
paragraph/list/container structure and table column labels. Omit fetched images
and active embedded links; mark unsupported or shortened content. Cap descriptions
at 100,000 characters, comments at 20,000 body characters each and 1,000,000
in total, picker/search values at 4,096 and reader metadata at 20,000.
Batch metadata and issue details share the native picker projection, including
privacy filtering and character bounds. Batch output is size-checked before
crossing the host process boundary. Use Open in Jira for full content. Do not
replace the complete bounded reader description with a short preview helper.
Copy issue as Markdown reuses this projection, omits empty non-comment values,
keeps loaded comments only, reports the Comments state, and adds the separate
262,144-character (Unicode code point) bound for the whole payload including
its marker.

### JP-035 — Read-only access and credential boundaries

Peek reads Jira; it does not change records, send terminal input, submit agent
prompts or execute issue text. Keep tokens out of arguments, environment,
localStorage, repository and diagnostic output. Setup uses a private temporary
submission and mode-600 credentials in a private mode-700 managed directory;
this is file protection, not encrypted keychain storage. Preserve external
credentials/configuration. Only validated allowlisted keys go to Jira. Temporary
files, clipboard, backups and external histories have separate cleanup limits.
User-invoked copies write to the system clipboard; Copy issue as Markdown can
include display names, comments, URLs and unescaped plain-text issue content.
Peek applies no additional redaction beyond the configured layout; any masking
applied by other tools or destinations is not guaranteed. Hidden fields are a
display choice rather than redaction, and the clipboard is not automatically
cleared by Peek or its cache actions. Copied text is data, not commands, and must
not be pasted into a shell.

## Clipboard output

### JP-041 — Copy issue as Markdown

Options → **Copy issue as Markdown** and the `copy-issue` command copy the viewed
issue from already-loaded data. The document includes the validated key/URL,
fetch time when available, Header fields, Body sections, a Details block when
configured and non-empty (even when its disclosure is closed), and configured
comments. Summary is promoted only under
the reader's default first-body title rule; Hidden fields and empty non-comment
values are excluded. Body text keeps internal whitespace and line breaks while
normalizing line endings; Header values collapse to one line. Loaded-but-
collapsed comments are included without opening the disclosure; deferred,
loading, failed, denied, empty, unavailable and partial comment states get an
honest note. Copy never starts a Jira request or comment load. The output is an
unescaped Markdown wrapper around Peek's plain-text projection, so a downstream
renderer or agent can interpret Markdown, HTML or instructions; Peek never
renders the copied document. The whole payload is capped at 262,144 characters
(Unicode code points), including one truncation marker. Footer feedback names the
copy and exposes it as an accessible status; there is no default key or reader
icon. Unit tests prove formatter, layout and selected lease/feedback paths; an
isolated fictional-fixture round-trip confirms the native command-to-clipboard
path. Paste rendering and screen-reader behavior remain manual release checks.

### JP-042 — Selectable reader text

The promoted title, Body field values, open Details values and comment bodies
render as native selectable text. Labels, header-strip values, freshness, issue
rows, Help/Options/forms, and collapsed or Hidden content stay plain. A
shortened Body value remains selectable; its visible note still points to Jira
for the full value. A pointer selection is independent of the logical issue
selection; starting it pauses
Follow and must not change the source or issue. Reader shortcuts, Escape/back,
the footer reading hint and the single reader focus ring remain active while
text is selected. Tab adds no text-block stops. Cmd+C/Ctrl+C copies the visible
selection through the host; Cmd+A/Ctrl+A selects one text block. Selection copy
is silent and separate from Y, Shift+Y and Copy issue as Markdown.

Reader text is escaped into a plain-text HTML document and rendered as
selectable, non-scrolling text; issue content never becomes Markdown, active
links, images or markup. State identity is scoped to connection epoch, source,
issue and field; comment identity also includes its position and a content
digest, so a new issue cannot reuse the previous issue's parsed text and
reordered or duplicate comments cannot share an element. Same-issue refresh may
briefly retain the previous parsed text while it reparses; the host is expected
to clear the selection when the replacement commits, and the native refresh
check remains. The host trims leading and trailing whitespace from a selection
copy while preserving internal spaces, tabs and line breaks. Cross-field
selection, keyboard caret selection and screen-reader selection are not
promised. Unit tests prove escaping, IDs, scope, focus
release, unmounting and key propagation; native drag/Cmd+C/paste, focus,
large-text, link-inertness and Cmd+A behavior remain manual release checks.

## Installation, updates and evidence

Implementation: [installer](../scripts/install-app.py),
[updater](../scripts/update-app.py), [release helper](../scripts/release.py).
Regression evidence: [install](../tests/install_test.py),
[update](../tests/update_test.py), [release](../tests/release_test.py) and
[bridge tests](../tests/bridge_test.py).

### JP-036 — Offline doctor and staged installation

Doctor checks tools and distinct component versions without validating Jira
credentials. `--check` validates a staged mod before replacement. Install a
self-contained runtime with agent contract, schema, scripts and icons that works
outside the checkout. Require the full source distribution, not the mod directory
alone. Honor selected app home. The native checker executes trusted mod code;
it is not a sandbox or security audit. Windows is unsupported.

### JP-037 — Managed updates and conflict protection

The installed updater works without the checkout, chooses numbered release tags,
checks tag stability and matching versions, and validates with Herdr. Preserve
settings/private state and back up the previous full bundle. Refuse edited,
unmanaged or unsafe managed paths. Allow only the specified regular generated
Herdr files as extras, retaining them in backups for regeneration. Availability
checks are read-only; a same-version release update changes no files. Explicit
versions/downgrades require their supported flags.

### JP-038 — Update integration, partial completion and rollback

Updates may prepare supported personal integration without switching layouts;
conflicts receive guidance. A valid code update can succeed while optional
integration fails. Report confirmed/unknown state after interruption rather
than assuming nothing changed. Local repair can complete integration without
redownloading. Named offline rollback restores a validated code backup while
preserving current settings; it does not restore personal toolbar/layout files.
Retain access to newer helpers when rolling back to a bundle without them.
Replacement records its exact backup before moving the active bundle. After
process interruption, the next mutating installer/updater invocation restores
that validated backup if the active path is missing. An existing valid active
bundle wins. Invalid journals or edited backups with no active bundle require
inspection; availability checks never perform recovery.

### JP-039 — Release identity and publication scope

Preserve mod ID `jira-peek`, installation owner `herdr-jira-peek` and runtime
paths; package/mod versions agree. Preparing or committing a release does not
authorize pushing, tagging, changing visibility, publishing or catalog submission.
Keep existing tags/releases intact. Follow [RELEASING.md](../RELEASING.md),
experimental notices and the closed-intake [project policy](../CONTRIBUTING.md).

### JP-040 — Fictional demo, native QA and removal

**Development only:** offline demo/fixture data supports native screenshots and
checks without a live account or existing terminal. Use the isolated
[capture rig](screenshots/README.md); keep QA output outside the published tree.
Pointer, keyboard and clipboard checks require native interaction beyond unit
tests. Use entirely invented public examples, never renamed real records.
Removal closes copies and removes only intended mod/integration files; broader
data deletion must account for saved credentials, external config, old caches,
clipboard and backups. Removal does not prove secure erasure.

## State lifetime reference

| State | Scope and lifetime | Preservation rule |
| --- | --- | --- |
| Keys, query, selection, Follow, activation, unread, issue pin | Per source within a panel session | Restore on source switch; respect bounds; Clear list resets only its source, preserving Follow and activation. |
| Keep this terminal | Panel session | Independent of issue pin; Clear list preserves it. |
| Full issue bodies / metadata | Panel memory plus separately scoped disk cache | Respect TTL, logical selection, projection ordering and eviction independently. |
| Disclosures, list viewport, reading focus/scroll | Native reading session | Preserve same-issue reading where supported; reset disclosures on identity change; retain documented stock scroll limitations. |
| Auto-refresh opt-in / local idle pause | Shared saved boolean / one panel's activity lease | Never persist idle pause over the saved opt-in or let another panel resume it. |
| Field layout / highlight preference | Shared private `fields.json`, per-connection layout / root preference | Preserve concurrent edits and unrelated connections through save, migration and update. |
| Chosen config path | Panel configuration/localStorage | Remember path only; credentials stay outside managed source. |
| Setup/Fields drafts | Mounted form, including nested Help | Discard on cancel; retain on recoverable save failure; guard busy setup and stale writes. |
| Credentials / private config | Managed connection or external private folder | Clear list/cache and code updates do not delete them. |
| Personal layout, toolbar, keys | Host-owned personal files | Preserve conflicting edits; bundle rollback does not roll them back. |

## Change preservation workflow

For every behavior change or refactor:

1. Identify affected JP IDs before editing. Read their preservation rules and
   linked implementation/tests, including dependent features in the table below.
2. Record expected before/after behavior. Preserve existing contracts unless the
   user explicitly requests a change to them; explain migration and state loss
   when a contract intentionally changes. Update its entry in the same change.
3. Run the relevant existing suites. For changed behavior or a bug fix, add a
   meaningful regression case for the externally observable invariant, including
   stale/failed requests when relevant. Documentation-only edits need link and
   consistency checks rather than new behavior tests.
4. Use isolated fictional native QA for changed UI/focus/scroll/clipboard behavior.
   Record component versions, stock versus patched capabilities and actual
   evidence; distinguish dispatch, data loading and rendered interaction.
5. Before handoff, list affected IDs, checks/results and unverified behavior.
   For a release, complete [candidate checks](../RELEASING.md#candidate-checks).
   Passing unit tests alone does not establish native behavior or live Jira access.

| Change area | Review these coupled contracts | Verification starting point |
| --- | --- | --- |
| Discovery, source identity, clear/reset | JP-001–009, JP-013, JP-019, JP-026, JP-031–033 | Model + controller; view for focus/selection; bridge for epoch/cache. |
| Search, reader, keyboard, pins | JP-004–017, JP-024–030 | Model + view + controller; isolated native typing, Escape, Tab, actions and unread arrivals. |
| Fields or shared preferences | JP-011, JP-019, JP-021–029, JP-031–032 | Field-layout + view + bridge; concurrent edit, invalid file and request invalidation cases. |
| Backend, permissions, caching | JP-009, JP-021–023, JP-026–035 | Bridge + setup + controller/model; selected, stale, failed and revoked requests. |
| Copy and clipboard output | JP-012, JP-034–035, JP-041–042 | Model + view + controller; native selection, clipboard/paste and focus with the fictional fixture. |
| Layout, toolbar or host API | JP-014–020, JP-036–038 | Toolbar + install + update + view; isolated stock host, optional patch separately. |
| Packaging, update, release | JP-018, JP-025, JP-031–040 | Install + update + release + bridge; settings preservation, conflicts and partial completion. |

Run automated suites from the repository root:

```sh
node --test tests/*.test.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v
python3 scripts/release.py --check
git diff --check
```

Useful existing regression names include **“clear retires old screen/history and
waits for a post-clear baseline in both Follow states”** (controller), **“P pins
the viewed issue directly and K retains the query and unrelated unread activity”**
(view), **“idle expiry is local across two panels; remote Off/On does not resume
an expired lease”** (view), and
`test_configurations_keep_independent_caches_epochs_and_pending_reads` (bridge).
These are starting points, not exhaustive coverage claims. Keep known gaps in
the [README limitations](../README.md#known-limitations) visible; Linux GUI and
full accessibility remain unverified.

Use this short record in development notes or a change description:

```text
Affected features: JP-...
Behavior preserved or intentionally changed:
Regression evidence (suite/case and result):
Native evidence (component versions and stock/patched host), if applicable:
Migration/state impact, if any:
Unverified behavior:
Dictionary and related usage/agent documentation updated:
```
