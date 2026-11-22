# Fictional screenshots and native checks

Only entirely fictional issues, identities, tenant URLs, credentials and
terminal output may appear in public captures. Never substitute real records,
even with identifiers renamed or blurred. Keep temporary QA evidence outside
the published tree.

## Native panel

```sh
python3 docs/screenshots/capture.py --app
```

Requires `herdr-app`, `hc`, `jq`, Python 3, OpenSSL and native GUI access. The rig creates
a separate temporary app home, core session/socket and XDG directories. It
disables telemetry, directs host release checks to an inactive loopback endpoint,
and uses an offline fictional backend. It reads no live Jira account or existing
terminal and closes only the app/core it created.
Current Rust setup uses an ephemeral TLS certificate and a loopback proxy that
accepts only `fictional-peek.atlassian.net`; other destinations are refused without
DNS resolution. The historical curl substitute remains for older panel comparisons.

On macOS the rig selects the installed `/Applications/Herdr.app` or
`~/Applications/Herdr.app` executable before consulting PATH. Multiple installed
bundles require an explicit `--app-binary` choice. On other platforms, or without
a macOS bundle, it uses PATH. An explicit binary always wins. This avoids silently
testing an old development CLI instead of the desktop installation.

The rig prints the selected executable/version and records its absolute path,
SHA-256 and bundle version in `verification.json`. Metadata/version mismatches
and staged desktop updates stop QA before launch; the host can apply an update
and exit during startup. The rig checks the executable identity again after
startup and before recording successful completion. A same-version binary
replacement invalidates the run too. Keep this machine-specific evidence outside
the published tree. Tests in `tests/screenshot_test.py` verify these guards
without starting an app.

The fixture deliberately uses fictional content and separate layouts, themes and
font cases. Those visuals need not match a personal live layout. Matching host
and mod code establishes the implementation under test, while the walkthrough
below checks actual interactions and painted content.

The integration fixture controls a fictional focus observation while the native
host renders, forcing automatic source adoption and then a shared toolbar browse
request. Render errors fail acceptance, including errors the host recovers from
by retaining the last frame. This covers a path absent from static checks and
from the earlier integration sequence that directly selected and pinned its
source in a task. Mock checks also reject notification and native mutations in
render/layout and emit synchronous programmatic input change callbacks.

The rig checks that Paused startup collects unread keys without Jira issue or
metadata reads, then exercises settled screen/history discovery, lookup, automatic filter
previews, source-local Clear list and Follow/Paused baselines, unread navigation,
older filtered-key title preloading within the configured window,
fields/preferences (including adding structured Linked Issues through the named
Fields action and a retired `highlightSource` value loading as inert
data), asynchronous request priority, cache clearing and reconnects.
It also checks Fields focus after invalidation, native focus recovery when a
same-issue Linked Issues count replacement removes Show all/fewer (and no focus
theft when that control is unfocused), local idle pause/resume,
TTL-zero logical body retention, and the generated toolbar with the selected
native host's checker.
It then renders a labeled fictional transcript beside the panel. Pointer,
clipboard and the user's actual entry chord require separate native interaction
checks; the focused `--keyboard-entry` check below covers `pane.go` entry and
PID-targeted Escape.

The default command updates four public screenshots: the root
[reader preview](../../preview.png), [light mode](app-light.png),
[keyboard guide](app-help.png), and [compact browsing](app-short.png).
Keep this gallery focused on distinct user-facing features. Regenerate and
review it after UI changes, before release. Keep duplicate, historical and
QA-only views outside Git. Lossless file compression is fine; preserve the rendered pixels
and inspect PNG metadata before publishing.

Use `--output-dir /absolute/path/to/frames` for the full QA set,
including My work and Search list/reader, collection loading/failure and Search
initial/empty states, narrow (300px) and reader (360px), Options, browsing,
status alignment and a scrolled sticky-pin fixture, filtered results, direct
lookup, Clear list access (a Terminal filtered list with and without matches,
`clear-list-*`), and the same long-title filter at widths 300, 360 and 420.
The key-width fixtures pair a short fictional key with a long project key at
widths 300/360/420 for font 13 and 450/562 for fonts 16/20. The large-font
widths are 28u+2, the narrowest Stack size: 300px is Guard at font 20, and the
short font-16 title frames would be Card. Their enabled key button records
Open locally without launching a browser. In those layouts, the fixture-only
commands `jira-peek.fixture-key-short` and `jira-peek.fixture-key-long` select
the cached issues for before/after frame comparisons. Pointer and keyboard
checks still require actual native interaction.
Native font fixtures exercise sizes 16/20 at heights 379/380/499/500 plus a
624px custom-header case, in 450px (font 16) and 562px (font 20) Stack columns.
The four short heights stay below the 26u title boundary, so those frames show
the long list row and reader title instead of a panel title. The custom-header
frame uses a one-line fictional title, a one-line body and a Details comments
block, so its configured header grid paints inside the 624px frame. Its in-app
evidence fails when the render that painted the frame did not call the reader
grid builder. Only the disposable copy substitutes that one host setting;
published mod code continues to inherit the actual host settings.
The fixture forwards its simulated font to retained row entities as well as the
parent panel, so virtual row extents and row content use the same typography.
The QA-only toolbar frame shows the generated personal layout.
The custom-toolbar frame uses a host-created stock tabs clone, a supporting
relative import, a preserved Q control, and the existing `peek-sidebar` panel ID.
The QA set also includes initial loading, inline refresh progress at font 20 in
the 562px Stack frame (300px at font 20 is Guard), and the Paused list before
Jira data loads. This writes all frames and `verification.json` (integration
results and separate component versions) to that directory without replacing
public images.

### Presentation modes

The QA run also writes one native frame per shipped presentation, plus short
Stack and configured-header cases. Each frame is the only panel in its fixture
layout, sized exactly, and comes with the measured size and named in-app
assertions under `modes` in `verification.json`:

| Frame | Size | What it records |
| --- | --- | --- |
| `mode-split.png` | 1120×700 | Split keeps the rail and reader columns: Issues and the filter in the rail, the selected reader beside it; the captured frame has no in-panel list resize grip. |
| `mode-card.png` | 300×250 | Card shows one issue identity, its labelled meta line and one action row inside a 16 px inset; the captured frame has no shared footer and no issue list. |
| `mode-guard.png` | 220×180 | Guard reports the count, the selected key and status, and the resize hint on the raised surface; the captured frame has no More, card actions, footer or list. |
| `mode-stack.png` | 360×624 | Stack shows four list rows and a painted reader body for the selected issue. |
| `mode-stack-short.png` | 360×312 | Stack hides the panel title below 26u while the captured frame still shows the reader body. 360×300 is a Card under the shipped 24u boundary, so 312 is the first Stack height at 360px. |
| `mode-stack-fields.png` | 360×624 | Two configured header fields (Assignee, Priority) form the reader grid after the body and before Details. |

The in-app checks evaluate the shipped presentation predicates from the measured
state, and the captured frame beside each one is the visual proof of what
painted. They are not view-tree probes: this fixture cannot walk the native
tree, so each predicate check records `{predicate, visual}` and no mount claim.
Real mount assertions for these element IDs live in the Node view tests. The
header-grid checks come from the actual `renderReaderFieldGrid` call order. A
failed assertion sets `ok:false` and makes the run exit nonzero. Review each
frame for the painted result; these frames do not replace the pointer, clipboard
and focused keyboard checks below.

The title fixtures also write `title-headers.png` at 562×624 font 20. Its
`titleHeaders` entry in `verification.json` records the measured size, the short
title, the two configured header-field IDs, and `headerGridMounted`, which is
true only when the render that painted the frame called the reader grid builder.

Add `--row-stress` to create and retire over 10,000 native row-action views
cumulatively while scrolling a fictional 200-issue list and simulating native
row disposal. It checks the seven-action viewport bound and that collapsing
Issues releases the actions. `row-stress.json` records allocation counts and
the result; `verification.json` includes the same evidence. This exercises the
host's real retirement path beyond its 10,000 simultaneously retained-object
limit without intentionally exhausting it. It is separate from pointer QA.

### Surface and list review

These are native checks; unit and view tests do not establish the paint. Use the
isolated fictional host and record the measured size with each result.

- **Card and Guard surface.** Confirm the host `raised` fill (or its `surface`
  fallback) one step off the terminal background, a 1 px border and a 12 px
  radius inside the host block. The surface does not inherit the terminal fill
  with only the title bar visible.
- **Stack list, 530×660 and 360×624.** Confirm four complete rows plus the
  border, no horizontal scrollbar inside the list, and a grip that stays
  invisible until hover or drag. The six-pixel strip keeps its resize cursor.
- **Short Split, 1200×300.** Confirm two complete 48 px rows plus one
  deliberately clipped row as the scroll cue, a 28 px shared footer, a 24 px
  rail footer, a 20 px reader title, 14 px body, 6 px reader gaps and 16 px
  content-end padding. Page Down advances by two rows, not the clipped cue. The
  Issues control stays visible in the reader title row, and the reader shows at
  least one body or bullet line instead of ending on an `Acceptance criteria`
  heading.
- **Card, 300×250 or wider.** Confirm a 16 px content inset on each side
  (measure = width − 32 px), one action row with Open at the leading edge and
  Copy key plus Pin trailing, and only one primary action. A configured date
  keeps its field label, for example `Updated 31 Oct 2026`.
- **Status dots.** Confirm In progress is blue (`info` or the accent fallback),
  In review and Testing are amber (`working`), Done uses `success` when the
  theme exposes it and the `done` role otherwise, Blocked uses the blocked
  colour, and other labels stay muted. Labels stay muted sentence case and dots
  stay 7 px; no dot uses a hardcoded board ember.
- **Pin and copy note.** Trigger Pin, Unpin and a key copy. Confirm the
  confirmation floats over the reader for 2.5 seconds without changing footer
  height or moving the reader. Dismiss clears it, the next selection clears it,
  and a later rejection replaces it.

### Header More menu

The QA run writes `menu-360.png`, `menu-480.png` and `menu-530.png` and records
each result under `menus` in `verification.json`. For every width the isolated
fixture opens the configured Terminal list, then a real pointer press on the
header ellipsis opens the card. The check parks the pointer, captures a settled
frame, and reads the painted card border from the image rather than trusting the
builder's `right`, `left` or padding values. Run only this check with:

```sh
python3 docs/screenshots/capture.py --menu-check --output-dir /absolute/temporary/menu-evidence
```

It writes the three frames, each fixture measurement and the checks above to
`menu-verification.json`. It uses a separate temporary app home, activates only
that window and posts PID-targeted Escape; it never uses the everyday app. The
pointer part is macOS-only because it uses CoreGraphics events and `sips` for
the pixel read. A non-macOS host can still run the view and mutation checks.

Each frame must pass these checks:

- **Right-aligned under the ellipsis.** Measure the card's trailing border and
  the painted More target's trailing edge. They differ by at most 4 physical
  pixels. The card's right border also matches
  `panelWidth − (surfaceInset + 26)` within 4 pixels.
- **Below the header.** The card's top border sits at or below the header's
  bottom edge (`chromeHeight + 4`). This proves the card does not cover the
  More target.
- **Card width.** The painted card is 184 logical pixels wide, within 5 physical
  pixels at the captured scale.
- **Outside press.** A native press in the panel body below the card closes the
  menu; the next captured frame has no card border at the expected position.
- **More remains clickable.** A second native press on the ellipsis opens the
  card again.
- **Escape.** A PID-targeted Escape closes it; the final frame has no card.

The pixel read starts from the fixture's measured panel size and the theme's
recorded border and chrome colours. It fails when the card paints at another
edge or under the header. The frames are QA-only evidence; do not publish them
without reviewing the fictional content and PNG metadata. View tests also keep
the backdrop below the header and the card inside the right-aligned row
(`the header menu exposes Clear list without taking filter width`,
`the header menu row stays below the header at narrow Stack widths`, and
`header menu presses stay on the card instead of its backdrop`). M-23 and M-24
in `scripts/mutation-check.py` fail those tests when the backdrop top or row
alignment regresses.

The automated pixel check covers the graphite theme at zoom 1.0 and the three
Stack widths. Split at 1120 px, the light theme, and zoom 0.9/1.25 remain
pointer-review checks; the thresholds can change the presentation (for example
360 px at zoom 1.25 resolves to Guard). Do not describe a passing view test or
the fixture's measured geometry as proof that the native card painted.

### Native keyboard entry and Escape

```sh
python3 docs/screenshots/capture.py --keyboard-entry --output-dir /absolute/temporary/keyboard-evidence
```

This focused check is macOS only; the Escape step uses
`CGEventPostToPid`. It uses the isolated fictional app home and a source copy of
`mods/jira-peek`; it needs no runtime build or Jira account. It creates a
fictional space with `input-receiver.py`, splits a demo Peek pane to its right,
focuses the terminal, waits past the panel's 100 ms origin tracker, and runs the
host's `pane.go` right action. Entry passes only when `herdr-app status` names
the Peek pane and the host reports no errors or overlays. Review
`keyboard-entry.png` for the painted focus ring and panel content.
`keyboard-entry.json` records the exact terminal/Peek pane IDs and observed
`focused_pane` values before and after.

Escape is a real key event posted only to the isolated process with
`CGEventPostToPid` (key code 53), compiled by
`clang -framework ApplicationServices`. Before posting, the harness checks that
`ps -o pid=,command=` names that PID as the selected executable and that it is
not another running Herdr. It never uses System Events: macOS collapses
same-bundle Herdr instances and can target the everyday app. Escape passes only
when `focused_pane` returns to the terminal pane; the mod's key log is advisory
because the host can consume Escape before dispatch. If posting is denied or
focus does not return, `escape.verified` stays false with the exact blocker. The
command exits nonzero unless entry and Escape are both verified, so a blocked
Escape fails the check rather than passing on entry alone.

The instrumented disposable mod logs its `init` and key events under the
isolated `HERDR_APP_HOME`. The run checks every record's `home` and that the
same log under `~/.config/herdr-app` is unchanged; if that check fails it stops
without touching personal files. Observed on **herdr-app 0.1.16** with
`hc 0.1.21`: entry and Escape both passed. Frames are
`keyboard-terminal.png`, `keyboard-entry.png` and `keyboard-escape.png`;
`keyboard-app.log` retains the isolated host log and
`keyboard-event-log.jsonl` the instrumented mod log. Keep all output outside
the published tree. This automates the host focus command and Escape return,
not the user's entry chord, pointer actions or clipboard.

Add `--app-review` to retain the isolated window for interaction checks. If the
integration sequence fails, review mode retains access for investigation and
keeps `ok:false` in its verification evidence; it does not turn that run into an
acceptance pass. Non-review runs still stop on failure. Use `--panel-revision REF`
to compare a local Git revision's panel/model in the disposable installation.
Failure evidence records the named wait, connection invalidation path and app log.
It also records panel render counts and whether the Fields editor was rendered,
and establishes input focus before testing invalidation. Keep the isolated
window visible and active during focus checks; `--await-activation` pauses before
the integration sequence so a distinct QA window can be raised. A timeout before
the requested frame or focus precondition is not a successful interaction check.

Use `--app-binary /absolute/path/to/herdr-app` to select a separate host. The lab
includes narrow/light/short layouts, loading/failure controls, unread arrivals,
a clipboard receiver and a fictional setup transport. Setup values are
`https://fictional-peek.atlassian.net`, `reader@example.test`, project `ABC`, and
a made-up token. Never replace them with real credentials. Review mode defaults
to a new temporary output directory unless `--output-dir` is provided; the rig
prints its location.

Identify the isolated app before automating input. Use a distinct app name and
bundle identifier when needed; never target an ambiguous window or the everyday
app. The `--keyboard-entry` mode proves the isolated PID with `ps` and posts only
to it; do not use System Events for a same-bundle instance. Press Enter in the
fixture process to close review mode. Inspect every published image visually and
inspect its PNG metadata before committing.

Record the running desktop bundle's version separately from the CLI's version;
they can point to different builds. Use `--app-binary` to include the user's
stock host in native verification. Select several already cached fictional
tickets with distinct titles by click and Up/Down, and compare the rendered
key, title and status with the preview and Copy/Open targets. Model selection
and accessibility labels alone do not prove the retained row painted new text.
Before release, exercise repeated Pin → Unpin → Pin with the pointer on the
selected row, check the visible pin state and target after each action, and
repeat after scrolling and changing selection.

### Local install pointer smoke

Run this after installing into a disposable app home; never restart the
person's everyday Herdr window for the smoke. The app loads mods only at
startup, so a changed file is not live until that window reopens.

```sh
BASE=/absolute/temporary/pointer-smoke
HERDR_APP_HOME=$BASE/app HC_SOCKET=$BASE/hc.sock HC_SESSION=jp \
  HERDR_TELEMETRY=0 HERDR_RELEASES_URL=http://127.0.0.1:9 \
  python3 scripts/install-app.py --app-home $BASE/app
HERDR_APP_HOME=$BASE/app HC_SOCKET=$BASE/hc.sock HC_SESSION=jp \
  HERDR_TELEMETRY=0 HERDR_RELEASES_URL=http://127.0.0.1:9 \
  herdr-app
```

Bring that isolated window forward and use a real pointer:

1. Open **More**. The card appears under the ellipsis, right-aligned; the header
   stays visible and the ellipsis still accepts a press. Press below the header
   to dismiss, then reopen and press Escape.
2. Choose **Options** and **Help**. Both open; Escape or the back arrow returns
   to the list, and no overlay covers the header or leaves a dead hit target.
3. Trigger a pin or copy confirmation, then press **Dismiss**. The toast clears
   without moving the footer or the reader.
4. Resize the panel to 360, 480 and 530 px and repeat the More press. Repeat at
   host zoom 0.9, 1.0 and 1.25.

Record the `herdr-app --version`, the panel sizes, the pointer actions and any
frame outside the published tree. After the smoke, tell the person to quit and
reopen their personal Herdr app for the final check; do not restart it for them.

### Pin interaction walkthrough

Use the offline review window for these checks (JP-004–005, JP-007–014,
JP-017, JP-028 and JP-041). Bring that specific window to the foreground before
sending input. If accessibility exposes only the window frame, raise the
isolated window and inspect it again. Refresh expired control IDs; if IDs
keep expiring during redraws, use the control's position in a fresh screenshot.
An expired ID or an off-screen control is not evidence of a failed action.

1. Open **Long issue list** and expand Issues. Hover each row without clicking:
   only that row reveals Copy key, Copy link and Pin. Leave the list: only a
   pinned row keeps its pin visible, with no selection checkmark. Copy and pin an
   unselected row in one click; the preview and unread set must stay unchanged.
   Compare selected and unselected long titles at narrow widths: icons share
   the header spacing, titles retain the same width, and clicking the right
   edge of a title selects it without copying or pinning.
   Check quiet dividers, equal row padding, a consistent gap from each key to
   its status, and independent key widths for unequal key lengths. Long keys
   must not widen short-key rows; selection must keep each row's text still.
   Check complete last rows at font sizes 13/16/20 and the short-panel
   boundaries. Page Down should advance by the visible row count.
   On the selected row, click Pin → Unpin → Pin at
   least three times. Check the icon, accessible Pin/Unpin state and Return
   action after each click. Repeat in the collapsed reader with both clicks
   and P.
2. Scroll several pages down and back up inside the results. The matching
   pin remains visible once, above the scrolling rows. Select another issue,
   move the pin to it, then unpin and repin it after it returns to the list.
3. Filter to exclude the pin. Return must still open its reader without
   changing the query. Reopen Issues and clear the filter to restore the pin.
   Use Up/Down and compare each painted key, title, status and action target.
4. While Paused, choose **Discover a new issue**. Selection, pin and existing
   result order stay in place; the arrival becomes unread. Read it with +new
   and use K to return. Copy key/link into the lab receiver during a detour
   to verify the clipboard targets the viewed issue. Also use Options → Copy
   issue as Markdown: the pasted document must include the validated URL and
   fetch time and name any comments that were not loaded. Move one populated
   field to Hidden in Fields and confirm it is absent. To exercise a deferred
   comment notice, copy before opening Comments. To exercise a loading or
   failure notice, set Slow/Failure, open Comments so the request starts or
   fails, then copy. Peek never loads comments for a copy. Confirm the footer
   status is announced, and on a long fictional issue confirm one truncation
   marker inside the documented 262,144-character bound.
5. Choose **Failure** and refresh. Retain the last loaded issue, fetch time
   and pin. Choose **Success** and Retry; check that the error clears.
6. Visit Comments, Details, Options, Fields and contextual Help, then return.
   With **Toolbar and hide/reopen**, pin an issue, hide Peek and reopen it
   using the toolbar. Selection and pin survive. **Options → Clear list**, or
   **Clear list** in the header `...` menu, then removes the list and pin while
   preserving Paused and Keep this terminal. Click both entry points in separate
   cycles.
7. Repeat list scrolling in **Short · 400px high**. Scroll over the unpinned
   rows to exercise the inner list. At constrained heights the surrounding
   content can also scroll; that moves the list itself. Return remains in
   the footer. Distinguish these two scroll surfaces in the evidence.
8. After hide/reopen and Clear list, look up two issues with distinct titles,
   clear the filter and navigate between them. Check that the selected row,
   full reader title and Copy/Open/Refresh all name the same issue. Repeat
   Pin → Unpin → Pin after this sequence; native row disposal must not freeze
   the selected row's text or event handlers.

Record actual interactions separately from the fixture's automated integration
results. Keep the report and any extra frames outside the published tree.

The automated integration fixture also disables the Promise row worker, then
checks three queued pin/unpin cycles and copy feedback through native timers.
This fault injection proves fallback scheduling; it does not replace the
pointer and clipboard walkthrough above.

## Selectable reader text

Use the isolated review window and the fictional issues. Drag over the title,
description, an open Details value and a comment body; press Cmd+C/Ctrl+C and
paste into the lab receiver. Verify internal spaces, tabs and line breaks,
that labels and header values are not included, and that links/images remain
literal text. After a drag, check that Y copies the viewed key, Escape still
returns, Tab still moves controls, the footer keeps its reading hint and the
reader keeps one ring. Switch issues, refresh, collapse Details/Comments,
filter the issue out, open Options/Help and hide/reopen; no previous text may
remain copyable. Also check Cmd+A/Ctrl+A selects one text block and that a
large description never shows another issue's text.

## Idle redraw benchmark

`idle-benchmark.py` creates a separate app/core and a key-free fictional terminal.
It retains the normal 100ms recovery timer and measures app process CPU time and
instrumented panel renders during a fixed interval. It also enables the host's
`HERDR_APP_BENCH` counters and retains the per-second records and total window
render calls, or reports `hostFrames:null` if that host emits none. Window render
calls are not physical display presentations. The sample boundaries can include
partial first/last host intervals; compare equal durations and retain raw records.

```sh
python3 docs/screenshots/idle-benchmark.py --revision f9e20d3 --seconds 30 --output /tmp/peek-before.json
python3 docs/screenshots/idle-benchmark.py --seconds 30 --output /tmp/peek-after.json
python3 docs/screenshots/idle-benchmark.py --stop-polling --seconds 30 --output /tmp/peek-stopped.json
```

Use the same installed app, duration and machine conditions for each run; alternate
before/after order for repeated samples. Keep the window visible and active;
`--await-activation` pauses before measurement so its specific QA window can be
raised. `--revision` substitutes that local Git
revision's panel and model in the disposable installation only. It does not switch
the checkout. The stopped-polling variant is diagnostic, not a production setting.
These idle samples do not replace the full native fixture or interaction checks.

Build production assets with `python3 scripts/package-runtime.py` before running
the fixture; normal fixture installation now uses Rust. To test an alternate
immutable executable as documented in [the runtime guide](../../rust-backend/README.md), add
`--bridge-binary /absolute/path/to/jira-peek-bridge --output-dir /tmp/peek-rust-native`
to `capture.py`. Only the disposable runtime's bridge launcher is substituted;
the report records the executable hash. The walkthrough uses fictional TWG, not
real Jira. Use `--await-activation` to pause before integration and activate the
isolated window for focus checks. A focus-precondition timeout remains a failed
check, even if an interactive review continues afterward. Keep baseline and changed
runs on the same host and distinguish app render calls from actual window redraws.

`--diagnostic-without-focus-tests` is an investigation-only option for separating
the rest of the walkthrough from Linked Issues replacement focus and Fields
invalidation focus. It records both omitted checks and `nativeAcceptance:false`,
even when all remaining checks pass. Preserve a full failing run alongside such
a diagnostic; never use it to claim the full fixture passed.


The native integration sequence also exercises fictional My work/Search pages,
explicit pagination, shared-reader entry, Back selection retention and Terminal
restoration. It also checks shared Search-field focus through Issues and Help,
non-fetching draft edits and separation from the submitted query. The disposable subclass supplies collection pages; issue details
still use the installed production runtime against fictional TWG. The independent
production TLS suite verifies REST enhanced-search requests and projections.
Review mode enables those same fictional collection pages for pointer/keyboard
checks through the visible source controls. This is not live Jira evidence.

Icon-header review (JP-010, JP-014, JP-043–044): check 300px, 360px and 420px
widths at UI size 13, and 360px, 420px and 562px widths at UI size 20; 300px is
Guard at size 20. Verify that all three source targets stay beside the title
without shrinking, clipping or duplicate controls; the title may truncate; the
active source and keyboard focus must remain distinguishable. Use Tab and
Enter/Space across Terminal/My work/Search, repeat activation on the selected
source, and check reader → other source → reader → Back with the same draft,
submitted query, local filter, loaded pages and selection. Check hover names and
footer focus captions, plus Options/Help Escape priority. Record visible list
scroll restoration separately from model/handle retention.

The native integration fixture also checks late issue-denial retirement after a
workspace switch, collection Refresh metadata used by local filtering, and older
cached details arriving after a newer list projection. These use fictional
responses and do not establish live Jira permission behavior.


Shared-frame review (JP-008, JP-010, JP-014–016, JP-043–044): compare Terminal,
My work and Search at the same size. Issues, the single input, result rows and
reader actions must align. My work has toolbar Refresh; Search has toolbar
Search and the **Search Jira…** placeholder, with no second filter or Results
button. Verify query typing/clearing preserves results, Enter submits, arrows
move to results and Enter there reads. Check Issues, Cmd+F, Help/Options return,
Cancel, Load more, failure messages and source switching with an unsent draft.
Collection controls remain in the bottom strip, with full status/scope on hover.

Check My work refresh from an open reader: keep the reader/body while loading,
after a successful refresh containing that issue, and on failure/cancel. If the
refreshed page omits it, return to the list without choosing another issue.
The native fixture verifies surviving-reader refresh; view regression tests also
cover omission, cancellation and a deliberate return to the list during refresh.
Check that empty Search states name the submitted query rather than an unsent
draft, and that partial empty pages still offer Load more. Failure text must be
concise in the footer with full details and scope in its tooltip/accessibility name.

Explicit QA output also captures the selected-list layout in both Graphite and Paper
at 300/360/420 logical pixels for host UI fonts 13 and 16, and at 360/420 for
font 20. A 300px panel is Guard at font 20 (below 18u), so that cell is omitted.
Use `--panel-revision` with the same host to compare a prior panel against the
working tree. These matrix frames stay out of the public gallery. The font-20
title, key, spacing, refresh and alignment frames use 562px, the 28u+2 Stack
minimum. Their freshness row shows the full one-line stamp, as it does at
360/20 and 420/20; these Stack widths do not take the compact date/UTC form.
`mode-card.png` proves that compact stamp with no blank reserved line.
`spacing-nested-*` at 562/20 keeps the full stamp row and the secondary-size
Details stamp without an orphaned zone.

The `clear-list-*` frames show the Terminal filtered list with the header `...`
menu open on Clear list and Options at 300/360/420 for fonts 13/16, and at
360/420/562 for font 20, in both themes, with matching rows, No matches, and a
large `+N new` badge. The `clear-list-closed-*` frames show the same list with
the menu closed, so the full-width filter and the `+N new` badge are visible
together. The fixture renders the configured-Terminal surface with its fictional
data; the offline demo still shows only Options. Confirm the filter and Issues
row keep full width, the in-field × still clears only the query, the menu's
trailing edge aligns with the ellipsis and sits 4px below the header with a
visibly open trigger, and the Clear list row remains reachable at the largest
font. Regression tests cover
its present-but-inert state after a fresh empty baseline and its availability
while reading; these frames capture the list expanded.

The `spacing-*` QA frames cover collapsed and expanded Comments/Linked Issues,
plus disclosures nested inside Details, in both themes at 360px/font 13 and
562px/font 20. Their fictional content is intentionally short so section
boundaries and the shared label/content gutter can be compared in a real native
frame.
