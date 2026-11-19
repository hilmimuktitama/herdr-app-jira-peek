# Jira Peek product and feature dictionary

This is the intended behavior baseline for the current working source, based on
**0.10.0 experimental**.
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
- [Navigation and host integration](#navigation-and-host-integration): JP-014–018; JP-019–020 retired.
- [Connection and configurable fields](#connection-and-configurable-fields): JP-021–025.
- [Data loading, freshness and privacy](#data-loading-freshness-and-privacy): JP-026–035.
- [Clipboard output](#clipboard-output): JP-041–042.
- [Installation, updates and evidence](#installation-updates-and-evidence): JP-036–040.
- [State lifetimes](#state-lifetime-reference) and [change preservation workflow](#change-preservation-workflow).

The installed [Rust runtime](../rust-backend/README.md) implements JP-022–035
behind the existing JSON contract. The JavaScript/GPUI controller executes one
binary per operation; REST uses in-process libcurl without child utilities,
while TWG retains its CLI. The shell source remains the compatibility oracle.
JP-036–039 install verified production assets and preserve existing configuration,
connection/cache formats and guarded legacy-state cleanup. Fixture-enabled
binaries are rejected by packaging and installation. JP-040 substitutions remain
limited to disposable QA homes. Production transport checks exercise fictional
CONNECT proxy, netrc and certificate verification with utility paths unavailable;
they do not establish compatibility with every libcurl/TLS version.

## Vocabulary

| Term | Meaning in Jira Peek |
| --- | --- |
| Jira Peek / Peek | The native GPUI Jira reader mod, ID `jira-peek`. The separate Herdr TUI edition has independent behavior and releases. |
| herdr-app | Desktop UI/mod host; requires **0.1.10 or newer**, never `1.10.0`. |
| herdr-core / hc | Separate terminal backend and CLI. `hc` must be on PATH; no numeric core minimum is enforced. |
| App home | Host configuration/data root, selected by `--app-home` or `HERDR_APP_HOME`, normally `~/.config/herdr-app`. |
| Panel copy | One running instance of Peek. Multiple copies can share saved preferences while retaining separate session state. |
| Attached panel / overlay | A block in a personal layout / a separately opened mod surface. Hiding one must target the correct surface. |
| Source | Terminal, My work or Search workspace view. Terminal sessions use exact live terminal addresses, including machine identity; collections have no terminal address. Manual direct lookup can exist without a terminal. |
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
Process every observation, including identical text, but notify the native panel
only when the scan changes its presentation: keys/order, selection, unread state,
source errors, screen-limit/baseline indicators or settled Options availability.
An in-flight passive read is not a presentation change: it must not repaint
Options or disable Scan screen. Request starts/completions and preview/focus
changes retain their own notifications.
Repeated identical errors do not redraw. Source switches still notify even when
both screens are empty. Keep the 100ms row-action/focus recovery timer; its idle
ticks do not notify.

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
responses. Keep Scan screen actionable while a read is in flight; an explicit
scan queues behind it. Manual scans remain available when automatic scanning is
disabled.

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

Terminal exposes the same action from the header More actions menu as a
**Clear list** row with an eraser icon, beside Options. Both entry points share
one handler, one-click behavior and availability; the row is absent for My work,
Search, manual lookup, demo and panels without a configured terminal source. The
menu keeps the filter and a large `+N new` badge at full width. The row is
enabled while keys, candidates or a pending baseline exist, then inert once the
fresh post-clear baseline settles with none.

### JP-008 — Issues list and local filtering

My work filtering remains local; Search uses this same input position for the
explicit submitted query in JP-043, with no separate local filter. The header
More actions menu's Clear list belongs to JP-007 and never changes results by
itself; it stays distinct from the in-field × and is absent from remote sources.

Expanding Issues focuses the filter; all search words match loaded keys, titles,
statuses and configured picker values. Preview a matching selection or the first
result immediately. A matching pinned issue stays visible at the top while the list scrolls; a nonmatching pin remains saved without bypassing the filter. Unpinning restores the underlying browsing order. Arrows/clicks preview while keeping the list open; Enter
collapses it for reading. Reopening retains query and list position. While browsing, a filtered-out
selection cannot own copy/open/refresh or hidden body requests.
Explicit unread, pin-return or direct-lookup entry may read outside the saved
query; reopening Issues restores filter eligibility.
Show No matches when the query has no loaded results, including valid issue keys;
do not replace the empty state or add a separate lookup prompt for them.
Keep loading, failed and unavailable titles distinct; missing metadata does not
prove that an issue does not exist.
Idle rows say Select to load; they must not imply a request is already running.
Only the hovered row reveals its copy and pin controls, immediately and without
selection. Row actions preserve the preview, query and unread state; copying
does not scroll or request details. Explicit row actions focus the results list,
including the persistent unpin. Keyboard-focused controls remain visible.
The header More actions menu exposes JP-007 without adding a match counter,
changing the filter's ×, moving rows, narrowing the filter or altering the list
height, even when a large `+N new` badge is present.

### JP-009 — Direct issue lookup

This key/URL entry path belongs to Terminal. Remote result-filter Enter reads loaded rows;
remote key discovery uses the explicit Search field (JP-043).

Explicitly look up an allowlisted key or HTTPS `/browse/KEY` URL on the configured
origin, including without a terminal. Reject foreign origins, credentials in
URLs and disallowed projects before making requests. Invalid input preserves
the current selection. Enter commits an explicitly previewed visible result;
unknown keys require explicit lookup with Enter in the filter. A matching
hyphenated title remains selectable without bypassing URL validation.

### JP-010 — Issue reader and responsive presentation

Source navigation uses the integrated icon header and shared Terminal geometry
in JP-043. Collection status uses the existing footer, with no extra height budget.

Keep control tooltips to a short action and shortcut, adding only essential
consequences. Put detailed instructions in Help; preserve full clipped-value,
source-identity and fetch-time tooltips.
Show the selected issue's identity, title, complete bounded description and
actions. A slow issue can show its known title but must never borrow another
issue's description. Use the shared 16-pixel section inset on both sides of the
metadata/reader divider and between the promoted title and description; do not
stack extra title padding on that gap. Configured header fields reserve line
height and only inter-row gaps, with the same bottom inset after the last field.
Include that inset in automatic list budgets and short-panel scroll decisions.
In browsing, default title/status come from the selected row. Each result sizes
its key independently, within a bound that leaves room for status and actions. Status follows its own key with a consistent gap;
long-key arrivals and filtering must not widen other rows. The same issue keeps
its key width and status position when selected, hovered or pinned.
The key's hover/focus button fits its text with balanced padding inside that
key slot; unused slot space stays outside the button. Long keys
truncate within their own slot and retain their full identity in the Open tooltip
and action target. Each key keeps the same clipping budget across selection.
Do not animate key or status positions during selection or hover.
Copy and pin use the same 32-pixel header targets in both states;
the summary keeps the full content width, and clicking it selects the issue.
Available result rows, keys and titles use a pointing-hand cursor, including pinned rows.
The selected key keeps the pointing-hand cursor on its text whenever Open in Jira is enabled.
Use one shared row geometry for selected, hovered and pinned results: balanced
vertical insets, a quieter metadata line, and subtle dividers. Rows are
top-aligned so spare fractional height cannot move key, status or title on
selection. The selected row uses a gentle theme-accent fill and an inset two-pixel
accent edge, independent of pin, unread and keyboard-focus indicators. Default
rows are 64 logical pixels and grow with host typography.
The filter grows with larger fonts. Automatic list budgets include their border
and end on complete rows.
A centered grip marks the existing six-pixel resize strip; hover highlights the
strip and dragging accents the grip without increasing its hit area or height.
Dragging the bottom border tracks the pointer continuously between one and four
rows, overriding the automatic budget for this panel session. Do not snap during
drag or release; partial bottom rows are allowed. Keep the resize cursor active
and suppress row hover/actions during the drag. Page Up/Down uses the number
of fully visible rows, excluding borders. Retain the choice
across filtering, collapse/reopen and hide/reopen; fewer matches temporarily
shrink the list without replacing the choice. A drag started while fewer matches
are visible previews the pointer height and stores that choice on release, then
restores the temporary shrink; releasing at the press point keeps the previous
choice. A click or small pointer wobble must not replace it. A matching fixed pin
reserves at least two rows. Short panels scroll together when the chosen list and
reader do not fit. Long summaries and statuses retain bounded tooltips.
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
Render also queues source adoption, toolbar browse consumption and stale pin
focus recovery for that wake. Re-read live source, visibility, request age/context
and focus before acting; never notify, focus, restore input or start requests
from render. Input restoration suppresses synchronous change callbacks and
always clears its guard. Preserve drafts and reading state across this delay.

### JP-011 — Details and Comments disclosures

Reader disclosure controls use flush rows: the label and expanded content share
the reader gutter. Any shortcut hint and the state chevron trail the label; the
Issues list toggle keeps its leading chevron. Rows use equal space from their
top divider and to the next section: 16 logical pixels in Body, 10 within
Details. Comments and Linked Issues use their placement's spacing, and
Details follows the Body rhythm. Expanded comments and linked rows keep internal
separators/gaps between entries, without an extra trailing gap or duplicate
final linked-row divider.

Details reveals configured secondary fields and fetch information; Comments
reveals discussion. Both pause Follow, survive a same-issue refresh, and reset
for a different issue/source. C/D respect visibility and placement, including
comments in Details, and reveal/focus the disclosure on capable hosts. The
description remains readable when comments are loading, empty or failed.
Configured Linked Issues uses the same trailing chevron and disclosure styling,
with named expanded/collapsed state, independent nesting in Details and scoped
text selection. It starts open, preserves same-issue choices and closes first
on Escape from its focused content. See JP-024 for its field/state contract.

### JP-012 — Copy, Open in Jira and feedback

Click the issue key to open it or use Y to copy it; Shift+Y copies its link. Open in Jira or
Cmd+Enter/Ctrl+Enter opens the actionable viewed issue using a validated link
built from the configured origin. Actions target the viewed issue during a pin
detour. Copy feedback changes its icon without shifting controls or hiding
errors. Held browser chords must not open repeated tabs.
Queued selected-issue actions retain their lease: reject selection, filter
eligibility, source, connection or auxiliary-screen changes with visible feedback.
Entering an auxiliary screen retires earlier leases even after returning to the
reader; rejection feedback must not revive the next queued action.
Explicit row actions validate the clicked key against the current collected and
matching rows and project allowlist. Projection or selection changes alone do
not invalidate that key; source, connection and auxiliary-screen boundaries do.
Rejected enabled actions show a note rather than silently discarding the click.
Stale reader keyboard shortcuts also report rejection while preserving their
rendered target lease; they leave editing, auxiliary screens and unrelated
controls alone. Successful pin/copy/open clears only the action-rejection note
it set, if that note is still current. The single note slot does not retain
earlier warnings replaced by a rejection.
Copy issue as Markdown is the separate JP-041 action; it uses the same viewed-issue
lease and footer feedback but has no reader icon or default key.

### JP-013 — Issue pin and return

Scrollbar focus recovery belongs only to the scrolling viewport; the fixed
selected pin keeps its action focus through pointer activation.

P or the inline pin toggles the viewed issue; pinning another moves the pin
immediately. The inline pin resolves the live actionable issue at click time,
including after selection/source changes without remounting; queued work then
retains that click's lease. An unavailable target gets visible feedback.
Manual/no-terminal sources explain that issue pins require a terminal; excluded
selections ask the user to choose a current result. An obsolete unpin reports
that the issue is no longer pinned without suggesting a blind retry.
K or **Return to KEY** returns to its reader, pauses Follow and
preserves query and unrelated unread issues. Store only one key per terminal
source/connection within normal bounds, with no additional retained body. Pinning
pauses Follow. Matching pins remain visible atop the scrolling result list without retaining an extra body.
The pinned row keeps an actionable accent pin visible when not hovered and
offers one-click unpin without first selecting it. Its hover action keeps a
visible accent pin glyph as well. Hover actions retain their rendered pin/unpin
intent: an obsolete unpin cannot repin an issue, and an obsolete pin cannot unpin it.
The inline selected pin also retains the requested Pin/Unpin value through
queued execution: repeated activations of the still-painted control cannot
reverse that intent. Keyboard P remains a deliberate toggle.
Pinning an unselected row preserves the preview.
Repeated pointer pin/unpin cycles must work after native row disposal, including
when the selected result moves between the fixed and scrolling list positions.
The native row wake also drains queued actions if the Promise worker has not
resumed; each entry executes at most once and still validates its original
target. Idle wakes do not redraw or fetch. See the
[reliability development guide](RELIABILITY.md) for failure injection and references.
Manual sources cannot pin. Hiding preserves it; Clear list, reconnect, Clear
cache, source eviction and panel destruction remove it. P/K remain text in inputs.

## Navigation and host integration

Implementation: [native UI](../mods/jira-peek/main.js),
[installer](../scripts/install-app.py), [keys example](../keys.json).
Regression evidence: [view tests](../tests/view.test.js),
[toolbar tests](../tests/toolbar.test.js), [installation tests](../tests/install_test.py).
Host procedures: [panel integration](PANEL-INTEGRATION.md).

### JP-014 — Keyboard ownership and Back

The three workspace icons keep native Tab/Shift+Tab and Enter/Space activation.
Source changes focus the activated icon; remote reader Back focuses results
(JP-044). No header navigation is active behind auxiliary screens.

On stock hosts, click Issues to enter Peek; local Cmd+F focuses search. Enter
reads inside Peek, while native buttons keep Enter/Space activation. Letter
shortcuts leave inputs/forms alone; modified host chords and native Tab traversal
remain available. The header More actions menu's Clear list is an ordinary Tab
stop; it adds no letter shortcut and leaves C/D, Escape and filter typing
unchanged. Escape closes disclosures, then collapses Issues retaining the
query, then returns to the actual terminal. With no matches it clears the query
first. Do not return to a vanished or mismatched terminal. Reliable keyboard-only
terminal-to-panel entry is not shipped; stock reader scrolling needs a wheel/trackpad.

### JP-015 — Options, Help and form navigation

Options and general Help are sibling screens; the **Back arrow** returns directly to
the retained reader/filter. Options carries the stable action inventory: Copy
issue as Markdown, Keep this terminal, Scan screen, Read history, Clear list,
Auto-refresh issue, Fields, Connection and Help. Clear list is also directly
available from the header More actions menu (JP-007); other reader/list actions
and their shortcuts remain in the reader and rows. That menu aligns its trailing
edge with the ellipsis, sits 4px below the header, uses a shadow, and keeps the
trigger visibly selected while open. Help opens collapsed topics, with
arrows/Home/End navigation and Enter/Space expansion. **? Keys** leads with
daily keys and places the rest under More shortcuts, including complete
shortcut discoverability and copy-safety guidance. Form Help retains drafts and
returns to the form. Do not allow delayed callbacks to focus covered/unmounted
inputs, or reader shortcuts to act behind auxiliary screens. Busy setup cannot
be dismissed.

### JP-016 — Native commands and shortcuts

`herdr-app do jira-peek.<command>` shares native handlers with mod keybindings.
Preserve the [complete command table](AGENT-GUIDE.md#native-actions), including
idempotent `pause`/`resume`, source `pin`/`unpin`, navigation, setup and read actions.
Dispatch reaches shown copies and requires normal prerequisites; OK is not proof
of a successful load. The optional F2/F5 and Alt+1/2/3 examples are mod-scoped.
`source-terminal`, `source-mine` and `source-search` reuse source-icon navigation,
including retained views/drafts, first-entry My work loading and no implicit
Search submission. Auxiliary screens block them; `search` focuses the source's visible filter or Search field. Options, Fields and Connection place a 32px Back arrow in the same header
position, with an accessible destination. Fields Apply stays in that header. The installer
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
selection and visible rendering. It reports managed, personal or missing
configuration; a generated personal copy with preserved edits is not treated as
broken, and `cloned_from` metadata plus the current host version prompts an
intentional refresh. Offline
repair changes personal integration files and prints a layout to select; it does
not switch the active layout. Rust `manage integration repair` preserves every
conflicting file, changes nothing and returns `personal_integration_detected`.
The manual guide ships at `mods/jira-peek/docs/PANEL-INTEGRATION.md` and has an
online fallback. `manage --help` and command help are successful usage paths;
unrecognized or duplicate options use `invalid_management_arguments`.

### JP-019 — Retired: source highlighting (optional host extension)

Retired. The mod no longer calls a renderer highlight API, exposes a Highlight
source option or Help topic, or keeps highlight retry/failure state. A
legacy running copy may still own its local mark; retirement does not control
decorations owned by an older copy. An existing
`highlightSource` value in `fields.json` remains accepted as inert data so a
strict file keeps loading and layouts, auto-refresh and other connections are
preserved; a later preference save omits it. Do not reintroduce terminal
decoration or a patched renderer requirement.

### JP-020 — Retired: native input extensions (optional host extension)

Retired. The historical input patch, build helpers and custom-host guidance are
not shipped or maintained. Stock installation and the key example never depend
on them. Preserve the stock-host limitations: reliable terminal-to-panel
keyboard entry is unshipped, ordinary reader/Help scrolling needs a wheel or
trackpad, and hide/reopen may reset reading position. A host-owned capability
check may still be consulted where it changes only local hints or paging.

## Connection and configurable fields

Implementation: [native UI](../mods/jira-peek/main.js),
[Rust setup](../rust-backend/src/setup.rs), [config parser](../rust-backend/src/config.rs),
[field model](../mods/jira-peek/model.js), [schema](../mods/jira-peek/fields.schema.json).
Regression evidence: [setup controller](../tests/setup-controller.test.js),
[setup helper](../tests/setup_test.py), [field layout](../tests/field-layout.test.js),
[view](../tests/view.test.js) and [bridge tests](../tests/bridge_test.py).
Rust setup also runs the shared [private-file contracts](../rust-backend/tests/setup_test.py)
and [production TLS checks](../rust-backend/tests/setup_transport_test.py).

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

The panel invokes the bundled Rust setup protocol. Account verification uses
in-process libcurl with a 64 KiB response bound and 20-second request timeout;
Python and the curl executable are not required by this flow. The form, private
ticket files, configuration format and failure behavior retain their contracts.
Setup and reader transport recognize the exact generated credential-file format
and pass its validated login/token directly to libcurl only for the matching
destination host. This preserves quoted values, leading `#` and the 4096-byte
token bound on older system libcurl versions. Other netrc files remain delegated
to libcurl's parser; malformed managed files fail before an HTTP request.

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
`PREVIEW_FIELDS` is accepted for imported configurations but no longer
contributes requested fields or comment loading. Imported `KEY_RE`,
`PICKER_LAYOUT`, `SOURCE_HIGHLIGHT` and `TEXT_STYLE` do not control native
matching/presentation; they remain declarative, validated data. `COLOR_THEME`
is rejected as unsupported.
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
`issuelinks` (Linked Issues) is optional. Add/Find Linked Issues near the top
of Fields adds one draft entry at the end of Body or focuses the existing entry,
including Hidden; the 32-field limit has an explanation. Keep existing layouts
unchanged. UI, schema and agent configuration allow Body, Details or Hidden;
Header is rejected with a placement explanation and the last valid layout retained.
Labels, order, Apply/Back and concurrent-edit protection use the same field contract.

Render structured relationships grouped by type identity and inward/outward
direction, using Jira's label and first-seen order. Each row has an eligible key
button, textual wrapping status and a selectable wrapping summary. Out-of-project
keys stay text with an explanation. Keys open Jira using the configured origin;
never follow embedded URLs or change the parent's selection/filter/pin/unread.
Revalidate the parent/source/connection and current relationship before opening.

Use the same trailing chevron-right/down SVGs and flush row-button styling as
Details/Comments, with the same native Button pattern. The configured label,
retained count, expanded/collapsed and unavailable/shortened state appear in the
accessible name. Stock herdr-app 0.1.15 does not forward the script Accordion
trigger label/focus handle; use named keyboard-operable Buttons rather than
claiming a separate native expanded-state attribute.
Start open on addition and issue/source/connection changes. Preserve the user's
open/closed and five/all choices on same-issue refresh and hide/reopen. Details
placement nests an independent disclosure; closing Details retains its inner state.
Show five rows initially, with the stationary Show all/fewer control above groups
and the normal reader scroll. Collapse unmounts text and row actions; expanding
never fetches. Escape from linked content closes that disclosure before Details.
Recover focus only from disappearing focused content: to the surviving expansion
control, Linked Issues toggle, containing Details toggle or reader as appropriate.
Track selectable text by disclosure and record identity; never steal auxiliary focus.
If a refresh reduces the retained count to five or fewer, recover focused
Show all/fewer to the surviving disclosure without changing the preview choice.
Retired disclosure/preview callbacks validate current loaded data and visible
placement before changing state or focus.

Missing/null data is unavailable; an explicit empty array is empty. Show empty
fields controls those states. Malformed returned entries carry a notice. Counts
refer to retained relationships, not guaranteed complete Jira totals. Limit to
100 records and the 20,000-character display budget, marking shortened data;
never fetch additional linked issues. Remote/web links are excluded. Markdown
uses all bounded loaded groups regardless of disclosure/preview, with honest
state/shortening notes; Hidden is excluded (JP-011–012, JP-014, JP-026,
JP-033–035, JP-041–042).

### JP-025 — Shared agent configuration and safe reload

UI and agents share versioned `data/jira-peek/fields.json`; Copy config path
reveals its path. Field entries use exact connection identity; root preferences
are shared across panels. Validate complete edits, retain the last valid state,
preserve other connections, and reject stale concurrent UI writes. Failed saves
retain drafts. Migrate legacy preferences without losing layouts. A retired
`highlightSource` boolean stays accepted and inert so an existing strict file
keeps loading; new preference saves omit it. Label/order edits reuse data;
requested-field changes invalidate affected requests and reload. Updates
preserve this file. Follow the [agent contract](AGENT-GUIDE.md).

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
With a nonempty Terminal filter, matching rows take priority over recent keys
within that same candidate window. Slice the window before excluding loaded or
attempted rows, so completion does not automatically drain every collected key.

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

Display the payload's fetch time beside Refresh, including cache hits.
Durable payloads retain their filesystem modification time, TTL-zero responses
use in-memory receipt/publication time without creating a temporary payload. While
progress replaces the visible time, retain the last successful fetch time in the
tooltip and accessible label, then restore it afterward. Never invent a time for
an unloaded issue. Preserve it on refresh failure. Compact layouts keep the
complete date and UTC time visible beside Refresh. Use the full
`Fetched {date} · {HH:mm} UTC` stamp when it fits; otherwise show
`{date} · {HH:mm} UTC`, which keeps the complete date and zone on one line at the
300-pixel narrow-panel floor. Keep the full `Fetched …` string in the tooltip,
accessible name and copied Markdown.
Reserve only the line count the chosen stamp needs, with a small safety margin;
never add a blank line merely because the full form was considered. Let the row
grow rather than clip when a host font wraps. Details repeats the same visible
stamp at the secondary metadata size with the full accessible name. Cache reads
do not restart freshness. Format supported dates in UTC and preserve
invalid/custom values. Neither a timestamp nor cached content proves live
permissions or current Jira state.

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

Clear cache is available in Connection and as `clear-cache`. It clears the
invoking panel's issue memory and its configuration folder's disk issue cache,
advances invalidation state and reconnects. Retain credentials, config and saved
UI choices; leave other folders and the legacy shared cache alone. Reconnect
resets issue/source sessions and pins. Watch config/epoch drift and reject old
responses before display or cache publication. Other copies on the same folder
can subsequently rediscover/refetch. The action disables while clearing or
loading, reports progress in Connection, and leaves Back/navigation usable.
After a successful clear, report the reconnect's result separately: a failed
configuration reload must replace the success message with an actionable error.
Results from an older reconnect cannot overwrite a newer attempt or steal focus
after the user leaves Connection.
The standalone `jira-peek-bridge manage clear-cache --state-dir ABSOLUTE_DIRECTORY`
command and historical `clear-cache.sh` helper accept an initialized connection
state directory, not the shared state root. Reject unresolved roots without
clearing their legacy cache or creating a misleading root-level epoch. The Rust
command rejects relative paths, parent traversal and symlinked state/cache paths
(including user-created ancestor aliases), needs no utility executables, and
shares the reader's publication lock. Advance the epoch even when the cache
directory is absent, retire pending reads, and remove only immediate regular
cache files; preserve nested directories, symlinks and other state. A missing
state directory is a read-only no-op.

### JP-033 — Permission and connection errors

Issue permission denial retires that issue across retained workspace models even
when its request outlives source navigation, provided the connection epoch is still
current. In-flight collection pages cannot restore denied issue metadata.
Denials survive the empty-row interval of a pending changed query; returned
denied rows stay unavailable until a successful issue retry. Once a collection
settles, keys absent from its results are pruned with the rest of its row state.
Denial broadcasts also prune inactive models so unrelated keys do not accumulate.
Collection denial does not revoke unrelated issues. Authentication loss or context
mismatch invalidates the connection and rejects late success. Report fixed,
actionable errors without raw transport output, credentials or foreign payloads.
Revocation is detected on subsequent backend requests, not continuous polling.
An explicit authentication rejection must advance the current epoch and retire
its cached data even if a subsequent TWG identity lookup cannot succeed. Guard
that revocation with local config/auth/epoch checks; never revoke a newer context.
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
credentials/configuration. From terminal content, only validated allowlisted keys go to Jira. Deliberate
My work entry and explicit Search also send generated project-scoped queries
and user-submitted search text; terminal content never becomes a search query. Temporary
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
The 0.9.1 isolated checks confirmed title and whole-prose-block copying after
issue changes. Partial-range drag copying remains inconclusive; do not infer
that it passed from a successful whole-block or Markdown copy.

## Installation, updates and evidence

Implementation: [Rust lifecycle](../rust-backend/src/management/mod.rs),
[toolbar integration](../rust-backend/src/management/integration.rs),
[Python compatibility installer](../scripts/install-app.py),
[Python compatibility updater](../scripts/update-app.py), [release helper](../scripts/release.py).
Regression evidence: [install](../tests/install_test.py),
[update](../tests/update_test.py), [release](../tests/release_test.py) and
[bridge tests](../tests/bridge_test.py), plus [Rust management](../tests/management_test.py)
and [dependency-denial acceptance](../rust-backend/tests/lifecycle_acceptance_test.py).

### JP-036 — Offline doctor and staged installation

Doctor checks tools and distinct component versions without validating Jira
credentials. `--check` validates a staged mod before replacement. Install a
self-contained runtime with agent contract, schema, scripts and icons that works
outside the checkout. Require the full source distribution, not the mod directory
alone. Honor selected app home. The native checker executes trusted mod code;
it is not a sandbox or security audit. Windows is unsupported.
Stage the platform production executable, third-party notices and manifest before
replacement. Verify exact release/source identity, bounded file sizes, SHA-256,
protocol, architecture and `fixtureTransport:false`; reject missing, altered or
incompatible artifacts without replacing the active bundle. Normal installation
uses HTTPS release assets; a source-local `.release-runtime` package supports
development/offline installation. Doctor never downloads or builds. Keep the
legacy `runtime/app-bridge.sh` path as a forwarding entry point.

The current source adds `jira-peek-bridge manage doctor|install|update|rollback`
and `manage integration diagnose|repair`. REST setup and these lifecycle commands
do not require Python, jq, curl CLI or external SHA tools. Git remains required
for release updates, TWG for existing TWG connections, and system libcurl/TLS for
REST. The JavaScript/GPUI panel remains the supported host interface. Historical
Python/shell entry points remain bundled for compatibility and independent tests.
This does not change the requirements of already published older binaries.

### JP-037 — Managed updates and conflict protection

The installed updater works without the checkout, chooses numbered release tags,
checks tag stability and matching versions, and validates with Herdr. Preserve
settings/private state and back up the previous full bundle. Refuse edited,
unmanaged or unsafe managed paths. Allow only the specified regular generated
Herdr files as extras, retaining them in backups for regeneration. Availability
checks are read-only; a same-version release update changes no files. Explicit
versions/downgrades require their supported flags.
The Rust installer freezes exact source profiles for the 24 existing numbered
tags from 0.1.0 through 0.10.0. Shell releases keep their original inventories;
0.10.0 still requires verified Rust assets with its original icon inventory.
Source checksums and complete inventories must match. Other versions use the
current complete Rust source/bundle contract; missing files never select an
older profile. Unrecognized mod files are rejected before replacement; only the
two regular generated Herdr files are ignored in a current source checkout.
Explicitly restoring an older release restores its original
runtime requirements. Installed legacy backup validation is separate from
source-profile recognition.

### JP-038 — Update integration, partial completion and rollback

Updates may prepare supported personal integration without switching layouts;
conflicts receive guidance. A valid code update can succeed while optional
integration fails. Report confirmed/unknown state after interruption rather
than assuming nothing changed. Local repair can complete integration without
redownloading. Named offline rollback restores a validated code backup while
preserving current settings; it does not restore personal toolbar/layout files.
Retain access to newer helpers when rolling back to a bundle without them.
Use the retained 0.10.0+ installer/updater to restore a Rust backup after a
rollback to shell: historical helpers copy file contents without executable modes.
Current rollback preserves runtime executable permissions and current settings.
Rust `manage install --attach [LAYOUT]` and explicit integration repair use the
same lifecycle lock as replacement. An explicit attachment plan/check failure
prevents installation; optional update integration failure preserves a valid
bundle update and reports partial integration with repair guidance. Diagnosis
uses read-only host status and never establishes rendering or selects a layout.
It distinguishes managed, personal and missing integration and reports personal
toolbar origins without rewriting them. After replacement, repair guidance names
a retained capable caller or gives the installed/online manual guide; it never
assumes an older bundle has the Rust lifecycle CLI.
Publication retains complete partial files for idempotent repair and preserves
conflicts and unverified staging files. Native toolbar checks use isolated host
configuration with the exact herdr-app >= 0.1.10 requirement.
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

Native QA prefers the installed macOS desktop bundle to a potentially stale
PATH command, with an explicit binary override. Record executable version/hash
and bundle metadata separately from the independent core version. Reject pending
updates, metadata mismatches and executable drift rather than attributing a run
to the wrong host. Fixture themes/layouts/fonts remain intentionally isolated
from personal live settings.

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
| Field layout / auto-refresh | Shared private `fields.json`, per-connection layout / root preference | Preserve concurrent edits and unrelated connections through save, migration and update. A retired `highlightSource` key is accepted; preference saves omit it, while field-layout saves may preserve it. |
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
3. Run `python3 scripts/verify-plan.py --diff` and read the matching
   [reliability rows](RELIABILITY.md#diff-triggered-reliability-checks), then the
   relevant existing suites. For changed behavior or a bug fix, add a meaningful
   regression case for the externally observable invariant, including
   stale/failed requests when relevant. Documentation-only edits need link and
   consistency checks rather than new behavior tests. If the change removes or
   narrows a guard in `scripts/mutation-check.py`, rerun it; a surviving
   mutation means no named test enforces that guard.
4. Use isolated fictional native QA for changed UI/focus/scroll/clipboard behavior.
   Record component versions and actual stock-host capabilities and
   evidence; distinguish dispatch, data loading and rendered interaction.
5. Before handoff, run `python3 scripts/verify.py --full`, then list affected
   IDs, checks/results and unverified behavior.
   For a release, complete [candidate checks](../RELEASING.md#candidate-checks).
   Passing unit tests alone does not establish native behavior or live Jira access.

| Change area | Review these coupled contracts | Verification starting point |
| --- | --- | --- |
| Discovery, source identity, clear/reset | JP-001–009, JP-013, JP-026, JP-031–033 | Model + controller; view for focus/selection; bridge for epoch/cache. |
| Search, reader, keyboard, pins | JP-004–017, JP-024–030 | Model + view + controller; isolated native typing, Escape, Tab, actions and unread arrivals. |
| Fields or shared preferences | JP-011, JP-021–029, JP-031–032 | Field-layout + view + bridge; concurrent edit, invalid file and request invalidation cases. |
| Backend, permissions, caching | JP-009, JP-021–023, JP-026–035 | Bridge + setup + controller/model; selected, stale, failed and revoked requests. |
| Copy and clipboard output | JP-012, JP-034–035, JP-041–042 | Model + view + controller; native selection, clipboard/paste and focus with the fictional fixture. |
| Layout, toolbar or host API | JP-014–018, JP-036–038 | Toolbar + install + update + view; isolated stock host, retired extensions kept out. |
| Packaging, update, release | JP-018, JP-025, JP-031–040 | Install + update + release + bridge; settings preservation, conflicts and partial completion. |

Run the verification loop from the repository root:

```sh
python3 scripts/verify.py --fast   # cheap checks and the Node suite, about 4s
python3 scripts/verify.py --full   # runtime assets and Python suites, about 4min
python3 scripts/verify-plan.py --diff origin/main...HEAD
python3 scripts/mutation-check.py  # periodic: do named tests enforce their guards?
python3 scripts/mutation-check.py --rust  # periodic and slower; needs cargo
```

`--fast` checks the reliability table, prints the rows matching changes since
`origin/main` (advisory), runs its verifier tests, then release metadata,
whitespace and the Node suite. `--full` additionally builds
`.release-runtime` and runs
the Python compatibility suites; without
`JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY`, `JIRA_PEEK_LEGACY_SOURCE` and
`JIRA_PEEK_HISTORICAL_SOURCES` some fixture-backed tests skip. Pass
`--fixtures DIRECTORY` from `scripts/prepare-lifecycle-fixtures.py` to build the
fixture runtime and run them. `--fast` does
not build or check Rust; `--full` builds the runtime with cargo but neither
tier runs cargo fmt/clippy/test, transport/TLS, parity, lifecycle acceptance
or the native fixture. `--fast` is not a release gate. CI and the native
walkthrough remain separate evidence.

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
Native evidence (component versions and stock host), if applicable:
Migration/state impact, if any:
Unverified behavior:
Dictionary and related usage/agent documentation updated:
```


### JP-043 — My work and explicit Jira Search

The header source icons are **Terminal** (prompt), **My work** (person with check),
and **Search Jira** (magnifier). Hover or keyboard focus reveals the name; the
selected source stays highlighted and exposes its pressed state. Tab moves among
controls and Enter/Space selects a source. Selecting the active icon again does
not refresh, reset, or go Back. The icons stay beside the title at every panel
width; the title truncates when space is tight.

All sources share Terminal's toolbar, input, list and reader positions. **Issues**
is the visible list/reader disclosure for every source. Its right-hand action is
Follow for Terminal, **Refresh My work** for My work, and **Search Jira** for Search.
In a Search reader, that action opens the query field without submitting it.
Terminal and My work use **Filter issues** locally. Search replaces that field
with **Search Jira…**: Enter or the toolbar magnifier submits words or an issue
key to Jira. Search has no second local filter or input mode switch. Typing and
clearing its draft leave submitted results intact until another explicit search.

Collection status, **Cancel**, **Retry** and **Load more** occupy the existing
bottom strip, so loading and pagination do not move the toolbar or reader. Hover the status for
connection/project scope, full status and collection fetch time. The issue's own
fetch time and Refresh remain beside the reader. Load more appears only in the
list while another page is available; it uses the submitted query, not the draft.

Refreshing My work keeps an open reader while loading and after success if its
issue remains in the refreshed page. Failure or cancellation retains that reader;
if the issue is absent from the refreshed page, the list returns without selecting
another issue. Focus returns to the list only if the removed reader still owns it;
a deliberate focus move is preserved. Issue details keep their own fetch time.
A recoverable My work refresh failure shows **May be stale** and **Retry** in the
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
command focus the visible field. Opening Issues selects its retained text;
Search Enter always submits, while Up/Down moves from its field to the results
for navigation and Enter to read. Escape in the Search field cancels pending
collection work and focuses results without changing source or draft. Escape in
a remote reader returns to results after closing its active disclosures.
Auxiliary screens keep their own Back/Escape behavior.

Terminal remains the initial source (JP-001–009). My work and Search own separate
collection models without terminal addresses or terminal-session eviction slots.
My work loads unresolved assigned issues on first deliberate entry. Search keeps
its draft separate from the submitted literal phrase or allowlisted key;
hyphenated words are text, while project-name plus numeric-suffix inputs must
pass the key allowlist. Only
Enter in that input or Search submits. My work filtering is local (JP-008);
Search exposes only its query field.
REST enhanced search uses generated JQL intersected with configured projects and
validates every returned key (JP-022, JP-035). TWG reports unsupported discovery;
existing direct reading is preserved. No raw JQL, boards or related navigation.

Pages contain at most 50 metadata rows and collections retain at most 200 unique
keys, in stable arrival order. Explicit Load more uses bounded opaque tokens and
rejects repeated tokens. A 200-page ceiling also bounds empty-page cursor history;
the UI reports a partial limit when either ceiling is reached. Counts report loaded/partial results, never a fabricated
total. Initial/empty, loading, canceled, failure/stale, permission-denied,
rate-limited and unsupported states remain distinct. Failed collection permission
checks do not revoke all issues. Authentication loss invalidates connection state.
Collection refresh replaces list projections even for previously read issues;
selected browsing-row status and local filtering use those projections; the reader
keeps its own status and field placement. Older cached detail responses cannot
overwrite newer collection metadata; the reader body retains its own fetch time.
Search has no disk cache and no automatic refresh/retry. Integer Retry-After is
bounded to 1–86400 seconds; absent/invalid/date-form values use 30 seconds.
A late rate limit in the current connection survives source/query cancellation
and blocks queued collections at dispatch. It does not revive canceled results,
and expiry requires explicit retry. Old connection epochs cannot impose a cooldown.

### JP-044 — Source reader and Back

All sources reuse JP-010–017 and JP-041–042 reader controls. Remote Back retains
query, rows and selection, returns focus to results and reuses the retained native
list scroll handle. Exact pixel restoration is host-dependent: the stock host
exposes no scroll-offset getter. Source switching preserves Terminal's session.
TTL-zero drops the departing body on workspace switch while retaining its metadata.
Terminal-only actions are disabled for collections. Nested auxiliary screens
retain the current source and search draft.

Source/query changes, Cancel, Back, connection changes, clear-cache and disposal
retire completion ownership (JP-028, JP-031–033). Retired issue/metadata/discovery
requests occupy the shared two slots until settlement; selected details retain
priority. Connection changes invalidate all collection models. No collection
completion opens a reader or steals focus. A My work refresh preserves an existing
reader grant if its selected issue survives, and opens the list if it does not.
Only focus owned by that removed reader transfers to the list; a deliberate focus
move is preserved. Discovery regression coverage is in
`tests/discovery.test.js`, `tests/controller.test.js`, Rust discovery unit tests,
production TLS transport tests and the isolated native fixture. Passing unit or
fixture checks alone does not establish pointer/keyboard behavior or live access.
