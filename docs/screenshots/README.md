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

The rig checks that Paused startup collects unread keys without Jira issue or
metadata reads, then exercises settled screen/history discovery, lookup, automatic filter
previews, source-local Clear list and Follow/Paused baselines, unread navigation,
fields/preferences (including a retired `highlightSource` value loading as inert
data), asynchronous request priority, cache clearing and reconnects.
It also checks Fields focus after invalidation, local idle pause/resume,
TTL-zero logical body retention, and the generated toolbar with the selected
native host's checker.
It then renders a labeled fictional transcript beside the panel. Pointer,
keyboard and clipboard behavior require separate native interaction checks.

The default command updates four public screenshots: the root
[reader preview](../../preview.png), [light mode](app-light.png),
[keyboard guide](app-help.png), and [compact browsing](app-short.png).
Keep this gallery focused on distinct user-facing features. Regenerate and
review it after UI changes, before release. Keep duplicate, historical and
QA-only views outside Git. Lossless file compression is fine; preserve the rendered pixels
and inspect PNG metadata before publishing.

Use `--output-dir /absolute/path/to/frames` for the full QA set,
including narrow/reader, Options, browsing, status alignment and a scrolled sticky-pin fixture, filtered results, direct lookup,
and the same long-title filter at widths 300, 360 and 420.
The key-width fixtures pair a short fictional key with a long project key at
widths 300/360/420 and font sizes 13/16/20. Their enabled key button records
Open locally without launching a browser. In those layouts, the fixture-only
commands `jira-peek.fixture-key-short` and `jira-peek.fixture-key-long` select
the cached issues for before/after frame comparisons. Pointer and keyboard
checks still require actual native interaction.
Native font fixtures exercise sizes 16/20 at heights 379/380/499/500 and a
custom-header case. Only
the disposable copy substitutes that one host setting; published mod code
continues to inherit the actual host settings.
The fixture forwards its simulated font to retained row entities as well as the
parent panel, so virtual row extents and row content use the same typography.
The QA-only toolbar frame shows the generated personal layout.
The custom-toolbar frame uses a host-created stock tabs clone, a supporting
relative import, a preserved Q control, and the existing `peek-sidebar` panel ID.
The QA set also includes initial loading, inline refresh progress (including
font size 20 at 300px width), and the Paused list before Jira data loads.
This writes all frames and `verification.json` (integration results and separate
component versions) to that directory without replacing public images.

Add `--row-stress` to create and retire over 10,000 native row-action views
cumulatively while scrolling a fictional 200-issue list and simulating native
row disposal. It checks the seven-action viewport bound and that collapsing
Issues releases the actions. `row-stress.json` records allocation counts and
the result; `verification.json` includes the same evidence. This exercises the
host's real retirement path beyond its 10,000 simultaneously retained-object
limit without intentionally exhausting it. It is separate from pointer QA.

Add `--app-review` to retain the isolated window for interaction checks, or
`--app-binary /absolute/path/to/herdr-app` to select a separate host. The lab
includes narrow/light/short layouts, loading/failure controls, unread arrivals,
a clipboard receiver and a fictional setup transport. Setup values are
`https://fictional-peek.atlassian.net`, `reader@example.test`, project `ABC`, and
a made-up token. Never replace them with real credentials. Review mode defaults
to a new temporary output directory unless `--output-dir` is provided; the rig
prints its location.

Identify the isolated app before automating input. Use a distinct app name and
bundle identifier when needed; never target an ambiguous window or the everyday
app. Press Enter in the fixture process to close review mode. Inspect every
published image visually and inspect its PNG metadata before committing.

Record the running desktop bundle's version separately from the CLI's version;
they can point to different builds. Use `--app-binary` to include the user's
stock host in native verification. Select several already cached fictional
tickets with distinct titles by click and Up/Down, and compare the rendered
key, title and status with the preview and Copy/Open targets. Model selection
and accessibility labels alone do not prove the retained row painted new text.
Before release, exercise repeated Pin → Unpin → Pin with the pointer on the
selected row, check the visible pin state and target after each action, and
repeat after scrolling and changing selection.

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
   using the toolbar. Selection and pin survive. **Options → Clear list**
   then removes the list and pin while preserving Paused and Keep this terminal.
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
