# Native verification record

## Experimental 0.1.0 readiness

**2026-11-01, local validation before the private history reset.** Package,
mod manifest and installer are version 0.1.0. The following checks were run on
the candidate before committing; they do not claim a public release.

The subsequent authorized delivery scope is one initial commit on `main`, a
`v0.1.0` tag and a push to the **private** repository, retiring the older 0.13.0
tag/release. Local recovery material preserves the former history. No new
GitHub release or catalog submission is included. CI results for the pushed
commit are available in [GitHub Actions](https://github.com/hilmimuktitama/herdr-app-jira-peek/actions);
historical CI runs below do not verify the new commit.

| Check | Result |
| --- | --- |
| JavaScript suite | **200 passed**, zero failures or skips |
| Full Python suite | **67 passed**, including configuration conflicts, isolated transports, installed-runtime independence and both former/current bundle updates from 0.13.0 |
| Shell validation | Syntax and ShellCheck **0.11.0** passed for all **9** shipped shell files |
| Capability check | Offline doctor passed with stock Herdr **0.1.11**, macOS arm64 |
| Fresh installation | Real native checker passed in a temporary app home; all **17** managed file hashes matched |
| Historical managed update | Installed actual source from `2c62cc6` (0.13.0), then updated to 0.1.0 with the real checker; config reference, fictional config contents, saved fields, layout, keys and prior bundle backup preserved |
| Installed runtime | Checked installed bridge retrieved a fictional issue from outside the checkout; the automated suite separately removes its source copy before retrieval |
| Privacy review | **66** candidate files and both reachable commits reviewed with secret/pattern scans; Gitleaks **8.30.1** found zero secrets. URL/email flags were public references, placeholders, fictional rejection fixtures or the already-published maintainer contact |
| Images | All **10** candidate PNGs and **11** distinct PNG images across candidate/history visually reviewed; entirely fictional content, only IHDR/sRGB/IDAT/IEND chunks, no text/EXIF metadata |
| Sharing format | Root recipe, preview, mod folder and optional keys; no personal layouts. Recipe follows official Herdr section order and explains the required bundling installer and toolbar dependency |
| Documentation and metadata | **136** local Markdown links/anchors resolve; all **4** candidate JSON files parse; final whitespace check passed |
| Publication behavior at validation | CI only checks, with `contents: read`; npm package stays private. No active local Git hooks. Preparation itself performed no remote mutation; the later private rewrite/push was explicitly authorized |

The first sandboxed native check timed out; the same isolated installation
check passed with native app access outside the sandbox. It did not use live
configuration or contact Jira. Release preparation changes metadata, tests and
documentation; UI/runtime behavior is the previously exercised working tree.
The [keyboard handoff checkpoint](#terminal-to-peek-keyboard-handoff) below
contains the latest native visual and interaction evidence on stock 0.1.11.
It was not replaced by a fresh full UI run during this metadata-only preparation.

Experimental limits remain explicit:

- Native keyboard checks passed with 100 ms keypresses. A zero-duration
  synthetic shortcut immediately followed by text can race host focus dispatch
  and lose the first character. No terminal input forwarding is added.
- Reader Page Up/Down was not functional on 0.1.10; use wheel/trackpad scrolling.
  A fix on 0.1.11, full screen-reader behavior and Linux GUI are not established.
  Hiding/reopening the panel on 0.1.11 resets reader scroll position, while
  selection, query and panel width remain intact.
- Source highlighting needs the optional renderer pinned to 0.1.10. Its
  historical macOS development build does not verify a release build or current
  host compatibility. Ordinary Peek works without it.
- Live Jira access and fresh Linux/macOS CI for this candidate were not run.
  Earlier CI below is evidence only for its recorded commit.

Before the reset, read-only GitHub inspection found the repository **private**,
with a published, non-prerelease `v0.13.0` release and `herdr-mod` topic, and no
`v0.1.0` tag. This finding led to the authorized history reset. The topic is
still relevant: public visibility would enable catalog discovery. Follow
[RELEASING.md](../RELEASING.md); a private push does not authorize public sharing.
The private-vulnerability-reporting endpoint returned HTTP 404 while the
repository was private, so current availability could not be confirmed. The
documented maintainer email remains the fallback; recheck reporting on release.

## Terminal-to-Peek keyboard handoff

**2026-11-01, working tree:** the personal toolbar's Ctrl+Shift+J handler
reveals the attached panel and focuses its filter. Repeat returns to the
originating terminal. The previous filter is selected on focus; typing during
connection loading is retained. Browsing pauses Follow and open forms keep
their drafts. Header × and the toolbar toggle retain their visibility role.

- **200 JavaScript tests passed**, including first visibility, connection
  loading, filter replacement, pending focus events, source adoption, return
  identity, draft preservation and stale/context-changed requests.
- **66 Python tests passed.** The installer still preserves personal integration
  files; the keyboard handler and binding are explicit personal changes.
- **Stock Herdr 0.1.11, macOS arm64, isolated fictional fixture:** native
  terminal/history, preferences, fields, commands, cache and reconnect checks
  passed. Computer Use then verified cold hidden opening, replacement of a
  previous filter, repeat-shortcut return, arrows/Enter/Escape inspection and
  reopening a retained panel. Native state confirmed the full query, selected
  issue, Paused state and focus return. Host status had **zero runtime errors**.
- Keyboard checks used **100 ms keypresses**, without added pauses before
  typing. A zero-duration synthetic shortcut followed immediately by text can
  race Herdr's asynchronous command/focus dispatch and lose the first character.
  The integration adds no terminal-input forwarding or artificial delay.
- The fixture's accessibility tree and screenshots sometimes lagged native
  state. Raising/resizing its window refreshed the display; the fixture also
  records only fictional keyboard state in `shared.json` for corroboration.
  No live Jira account or real terminal content was used.
- The local `--update --check` passed and all **17 installed files** matched
  source and manifest hashes. The reviewed personal toolbar handler and
  Ctrl+Shift+J binding were applied with backups and concurrent-edit checks.
  The personal layout and every unrelated binding were unchanged. The running
  host reported **zero runtime errors** after installation.
- All four regenerated fictional previews received visual review and contain
  no PNG text or EXIF metadata.

## Complete agent configuration guide and native controls

**2026-11-01, working tree, after the field-file checkpoint below:** the
installed agent guide now maps every supported setting to its authoritative
file or native command, including connection/data settings, field layouts,
reader preferences, host typography, placement, width and keys. Existing
session actions have documented native commands; no new service or dependency
was added.

- **192 JavaScript tests passed.** Added migration of reader preferences into
  the shared file, agent/UI round trips, preservation of field layouts, failed
  and conflicting saves, malformed preference recovery, idempotent session
  commands, draft protection and idle pause despite a failed preference save.
- **66 Python tests passed**, including transport, setup, update preservation
  and installed-runtime independence from the source checkout.
- **Stock Herdr 0.1.11, macOS arm64:** the final isolated native run passed
  shared preference reload/save, field edits/conflicts/recovery, native
  pause/resume and pin/unpin commands, opening/closing Fields without losing a
  draft to reconnect, cache clearing and reconnect after config invalidation.
- **Computer Use plus native CLI, wholly fictional fixture:** an external
  atomic edit turned Auto-refresh on; the native UI turned it off and the
  shared JSON reflected that change while retaining layouts. CLI pause,
  Options and Fields commands produced the corresponding visible states.
  Host status reported **zero runtime errors**. Highlight preferences are
  stored and tested with a simulated extension; stock Herdr correctly showed
  the feature as unsupported.
- Managed local update with `--update --check` passed. All **17 installed
  files** matched both source and manifest hashes. The three personal
  integration files (layout, toolbar and key bindings) were unchanged, and
  the running host reported **zero runtime errors** after the update.
- Reviewed all four regenerated fictional preview images, including light
  and narrow layouts. Their PNG files contain no text or EXIF metadata.

The file retains its existing name, `fields.json`. Its root `preferences`
object is shared by native panels; connection entries still hold one field
layout each. Session state remains transient. Authentication uses the existing
private setup. Live Jira access, Linux GUI and native rendering with the
optional highlighting extension were not part of this pass.

## Agent-editable field configuration

**2026-11-01, working tree, after the UI checkpoint below:** native panels and
agents now share `data/jira-peek/fields.json` under the Herdr app home.
The installer includes a dedicated agent guide and JSON schema. One entry per
connection controls placement, order, labels and visibility. No dependency,
agent-control API or Jira write was added.

- **184 JavaScript tests passed.** Added strict document validation, connection
  isolation, legacy preference migration, failed migration/save preservation,
  invalid-edit recovery, delayed read rejection, and stale saves both before
  and after a watcher notification.
- **66 Python tests passed.** Includes the previous transport/setup coverage,
  installation of the agent contract, migration of the former 15-file bundle,
  preservation of user field preferences, and running the installed runtime
  after deleting its source checkout.
- **Stock Herdr 0.1.11, macOS arm64:** the isolated capture fixture passed real
  file-watch reloads, UI saves, stale draft rejection, invalid JSON retention
  and repair, along with its existing native integration checks.
- **Computer Use with the fictional fixture:** an external atomic JSON edit
  invalidated an open UI draft and disabled Apply. After discarding the draft,
  the 300px reader showed the agent's order and labels, custom rich-text
  paragraphs, a zero value in the header, and hidden comments. A native UI
  label edit wrote back to the same JSON file without altering a second
  connection. Incomplete JSON retained that reader with a visible warning.
  During review, a stale captured native frame was refreshed by resizing the
  test window; automated state checks and the subsequent visible frame agreed.
- Four standard fictional previews were regenerated and visually inspected;
  PNG chunks contain no text or EXIF metadata.
- Managed local update with `--update --check` passed. All **17 installed
  files** match source and manifest. Personal toolbar, layout and keybinding
  hashes are unchanged; the installed host reports **zero runtime errors**.
  The prior managed bundle remains in the installer's local backup.

All issue-bearing QA used wholly fictional transports. Live Jira field
discovery, session linking, task-brief export, Linux GUI and a full accessibility
audit were not exercised. The [research record](AGENT-WORKFLOWS.md) separates
implemented agent configuration from proposed next workflows.

## Configurable reader fields

**2026-11-01, working tree:** Options → Fields saves one layout per configuration
folder and Jira site. Header, Body, Details and Hidden placements, section order,
display labels, custom IDs and empty-value visibility drive the reader directly.
Apply saves; Back/Escape discards the draft; Reset restores configured defaults.
The issue key and Open in Jira remain available. No new dependency was added.

- **175 JavaScript tests passed.** Coverage includes per-connection persistence,
  malformed layouts, ID-based placement, duplicate labels, zero/false values,
  cancel/reset, storage failure, connection drift, hidden comments, and discarding
  an in-flight response after changing the requested fields.
- **65 Python tests passed.** Fictional transport checks cover configured field
  IDs/labels, validated per-read field selection, cache signatures, unchanged
  private configuration, enabling/hiding comments, and safe custom rich-text,
  scalar, list and empty values. Reader fields are bounded to 20,000 characters.
- **Native Computer Use passed on stock Herdr 0.1.11, macOS arm64:** edited a label;
  hid Status; moved Assignee into the header and Description into Details; added
  and reordered a numeric custom field; added a rich-text custom field; displayed
  zero and preserved paragraphs; toggled an empty Due date placeholder; applied,
  canceled with Escape, reset, and reloaded the native mod with the saved layout.
  The editor and reader were inspected at 300px and 125% zoom, and the reader at
  420px in the light theme. Multiple header fields retain the issue key and a
  scrollable reader. The fixture reported **zero runtime errors**.
- The final `capture.py --app` run passed native integration checks and refreshed
  all four standard previews. Visual review passed; PNG chunks contain no text
  or EXIF metadata. The managed local update with `--update --check` passed;
  all **15 installed files** match source and manifest hashes. Personal toolbar,
  layout and shortcut hashes are unchanged, and the installed host reports
  **zero runtime errors**. A backup was retained outside the repository.
- The native review used only `docs/screenshots/capture.py --app-review` with
  wholly fictional transport data. No live Jira service was used. Field-catalog
  discovery, project/type-specific layouts and arbitrary vendor field renderers
  are outside this implementation; custom fields are added by their Jira ID.

The earlier typography and hide/reopen behavior below remains in the regression
suite. Native accessibility trees still omit text-field labels on this host;
full screen-reader and Linux GUI behavior have not been established.
These working-tree changes are uncommitted.

## UI typography and panel controls

**2026-11-01, working tree:** all panel text inherits
`settings().ui_font_size`; headings use weight and secondary text uses color.
Herdr applies zoom. Its terminal `font_size` is a separate setting.

- **164 JavaScript tests passed**, including host UI-size changes with a
  different terminal size, without double zoom or resetting selection/filter,
  hiding the actual layout node, and closing an overlay independently.
- The isolated native installer check passed on **Herdr 0.1.11, macOS arm64**.
  The sandboxed checker timed out; the approved native-runtime retry passed.
- Computer Use in the offline `capture.py --app-review` fixture confirmed
  consistent empty-state, search, list, reader, Options, Help and setup text.
  At **100% and 125% zoom**, the 300px panel remained readable; the selected
  issue and filter survived zooming. The 300×400px reader kept its action visible.
- Four fictional previews were refreshed with `capture.py --app`, covering
  420px dark/light and 300px dark panels. Native integration checks passed.
  Visual and PNG-metadata review passed. No live Jira connection was used.
- The managed local update passed with a backup; all **15 installed files**
  match the reviewed source and installation manifest.

The header **Hide Jira Peek** button uses `layout.hide` on the attached node.
The [documented personal tabs integration](PANEL-INTEGRATION.md) adds a native
Jira Peek toggle next to Files/Changes; Ctrl+Shift+J now uses the host layout
command so it can reopen a hidden panel. No new dependency or visibility store
was added. Escape and the optional visible-panel focus command remain intact.

Native interaction checks on **Herdr 0.1.11, macOS arm64** used only the
isolated fictional `capture.py --app-review` fixture:

- **Passed:** hide with ×; reopen with the persistent toolbar toggle; hide
  and reopen with Ctrl+Shift+J. Toggle state follows visibility.
- **Passed:** selected fictional issue, `catalog` filter and Paused state
  survived repeated hide/show. Both 360px and resized 300px widths returned.
  Changes could stay open while Jira Peek independently hid and reopened.
- **Passed:** the 300px header, Options, Help and × fit at 100% and 125% zoom.
  Terminal font size changed independently of the panel's inherited UI size.
- **Host limitation observed:** the ordinary reader scroll offset resets on
  hide/reopen, although the mod instance stays alive. The version-matched
  API exposes a scroll handle for virtual lists, not ordinary scroll regions.
  No custom scrolling implementation was introduced.
- The real installation received the reviewed mod, personal tabs copy and
  one changed shortcut. Readback confirmed all managed hashes and the toolbar
  snippet, preserved unrelated layout/key settings, and zero reported host
  errors. Backups remain outside this public repository. Changes are uncommitted.

## Current extraction validation

**Historical checkpoint, retained for traceability.** The repository is private
and the earlier Git refs/release are retired by the 0.1.0 reset. Commit IDs and
CI results below identify the former history; they do not validate or publish
experimental 0.1.0. See [candidate readiness](#experimental-010-readiness).

**2026-11-01: standalone v0.13.0 source release published.**
This record separates extraction checks from historical feature validation.

| Gate | Result |
| --- | --- |
| Release tree | **61 files** at former commit `0dd98d4686914323ac553913a4bda4dafc980c4e`; independent native history, without TUI history or local state |
| JavaScript suite: `node --test tests/*.test.js` | **161 passed**, zero failed/skipped |
| Full Python suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -q` | **61 passed**, including bridge, setup and installer |
| Shell syntax and lint | All included shell files passed; ShellCheck **0.11.0** |
| Isolated stock-host check | `scripts/install-app.py --app-home <temporary> --check` passed with stock Herdr **0.1.10** |
| Installed runtime outside checkout | Regression installs from a standalone copy, deletes that copy, then retrieves a wholly fictional issue from the installed runtime |
| Cross-repository managed update | Original native installer → extracted installer; **15 managed hashes**, owner marker, configuration reference, fictional layout/keys and backup preserved |
| Fictional native workflow | Screen/history reads, URL lookup, freshness, Follow, reader focus, cache clear and configuration invalidation passed |
| Public assets | Four stock-host previews regenerated and visually reviewed; all **10 PNGs** contain only IHDR/sRGB/IDAT/IEND, without trailing data. Six highlight captures match the previously reviewed originals |
| Privacy scan | Gitleaks **8.30.1**: zero findings in the publication tree and complete initial release history; no local credentials/state or host binaries included |
| Documentation links | **107** local links resolve; independent documentation review passed |
| Independent source review | Passed; one unsupported catalog-metadata claim removed and focused follow-up confirmed resolution |
| Exact-commit CI | [Linux and macOS jobs passed](https://github.com/hilmimuktitama/herdr-app-jira-peek/actions/runs/41282385744) for the release commit |
| Public clone installation | Fresh clone matched the release commit; real native checker passed and all **15 managed hashes** matched |
| Repository/tag/release at that checkpoint | Former public repository and `v0.13.0` release; its annotated tag resolved to the reviewed commit. These refs/release are retired by the subsequent private reset |
| Catalog and security reporting | `herdr-mod` topic and private vulnerability reporting enabled; catalog feed generated **2026-11-01T06:30:16.067Z** has no entry yet |

The extraction leaves UI, transport/setup behavior and the optional renderer
patch unchanged. A fixture script exercises native integration; it does not
establish a new comprehensive keyboard, accessibility or live-service review.
The renderer's release-mode build, Linux GUI and later host versions remain
unverified. No live Jira request or normal app installation was needed.

Follow [contributor instructions](../CONTRIBUTING.md) for commands and dependencies,
[release procedure](../RELEASING.md) for publication, and [UX evidence](UX-REVIEW.md)
for historical native observations. A stubbed installer checker in unit tests
is not proof that the real host renders the mod.

## Historical 0.13.0 verification

Verified on 2026-11-01 with the optional local Herdr app 0.1.10 renderer
extension on macOS. The mod detects that capability and remains compatible
with the stock host. This is evidence from the original native source checkpoint, not the extracted tree.

A later publication-documentation pass on the same date refreshed the four
standard previews with stock Herdr 0.1.10 using the isolated fictional fixture.
Its native integration checks passed for screen/history reads, URL lookup,
freshness, Follow, reader focus, cache clearing and connection invalidation.
All four images were visually reviewed and contain only IHDR, sRGB, IDAT and
IEND chunks, with no trailing data. Runtime source was unchanged; the unit and
native test counts below belong to the preceding feature-validation run.
This pass does not establish a full release privacy/history audit or new CI.

- **161 JavaScript tests and 15 Python installer tests passed.** New regressions
  cover selection, Following/Paused filtering, exact remote source identity,
  pinning, source loss, setup/reset/close cleanup, boolean-only persistence,
  stock compatibility, rejected/throwing native calls and coalesced restart
  recovery. Successful pairs are reasserted idempotently; failed pairs remain
  suppressed until a meaningful change or explicit off/on retry.
- **225 native tests passed, zero failed, one ignored.** The existing ignored
  test downloads a release. New coverage checks literal token boundaries,
  Unicode/wide cells, soft versus hard wraps, hidden cells, uncertain viewport
  edges, cached/linear matching, owner isolation, hide/show, terminal lifecycle,
  reload retirement and failed-candidate rollback. The full suite required
  native-runtime access for its isolated `/var/tmp` fixtures.
- `cargo build --locked` succeeded with Rust 1.95.0 and Zig 0.16.0. The tested
  build uses the development profile. The patch disables unused XCFramework
  emission so the static Ghostty library builds with macOS Command Line Tools.
  The documented release helper passed shell syntax and ShellCheck; its release
  build was not executed. Linux and Windows were not validated.
- The packaged patch passed `git apply --check` against pristine upstream
  commit `36725d47c89cd19345994363d6d9cdee5c42c80b` (v0.1.10). Independent
  review confirmed all 14 packaged files match the inspected implementation.
  Independent review revisited fixes for token boundaries, matching cost and restart recovery,
  with no remaining concrete finding. That review was source inspection only.
- The isolated stock-host checker passed after a sandboxed native-runtime
  timeout and an approved retry. No live connection or credential was used.
- Six actual native screenshots from the fictional highlight fixture were
  visually reviewed. Selected occurrences, longer-token exclusions, Unicode
  alignment, changed selection, disabled state, both themes and hide/show
  restoration passed. Source terminal text was identical before and after
  changing/disabling the mark. PNGs contain only IHDR, sRGB, IDAT and IEND chunks.
  See [UX evidence](UX-REVIEW.md) for the separate Computer Use check and limits.
- All five existing layout/keybinding hashes stayed unchanged in that run.
  A separate local development executable was tested. Stock Herdr cannot
  paint terminal marks without the [optional extension](../native/APP-HIGHLIGHT.md).

## Prior app edition 0.12.1 verification

Verified on 2026-11-01. The UI changes retain the displayed issue key/status
while scrolling, clarify invalid lookup guidance and issue auto-refresh, and
explain configurable keyboard entry in Quick help.

- **145 Node tests and 15 Python installer tests passed.** The broader backend
  checks below cover the unchanged 0.12.0 transport and cache implementation.
- Herdr's native checker passed with native runtime access after the sandboxed
  invocation timed out. The checker used isolated state and no user connection.
- All **15 installed files** match source and manifest for 0.12.1. Five existing
  layout/keybinding files were unchanged by installation. The previous managed
  bundle is retained by the installer.
- An independent reviewer completed the bounded daily-workflow review through Computer Use,
  including two real issues, keyboard lookup/recovery, pause/follow/pin, and
  safe Help/Connection navigation. The [acceptance record](UX-REVIEW.md)
  contains only generic observations; private evidence remains outside the repo.
- The focused 0.12.1 Computer Use retest reported **four passes and one partial**,
  with no new confirmed defect. Persistent identity, keyboard entry/return,
  refresh wording, and invalid-lookup recovery passed. Comments retained the
  description with an empty response; loading/error timing was not captured.

First-discovery timing remains unisolated. Page Down and native accessibility
limits remain as recorded in the acceptance history.

## Prior 0.12.0 verification

Verified on 2026-11-01. This release fixes the independent review's content
preservation, REST loading, permission scope, retry recovery, and freshness
findings. Descriptions remain immediately readable; optional REST comments
use a separate request with a one-page limit.

- **145 Node tests passed.** Coverage includes original fetch-time expiry,
  backoff wake-up and invalidation, independent comment loading, local comment
  retries, stale comment responses, connection revocation after refresh,
  disclosure state during Follow/source changes, and rendered loading/errors.
- **61 Python tests passed.** New fictional transport cases cover ADF content
  preservation and explicit omissions, immediate core context, bounded recent
  comments, allowlists, partial failures, localized HTTP 403, and HTTP 401
  revocation. All 15 installer tests were also rerun after the version update.
- The original repository’s REST and authentication-lifecycle shell suites
  passed (historical only; these suites are not included in this extraction). Legacy pagination,
  transport parity, credential rotation, and stale-response rejection remain
  covered with isolated fictional fixtures.
- ShellCheck 0.11.0 with followed source dependencies and shell syntax checks
  passed for the changed shell files. `git diff --check` passed.
- Herdr's native checker passed against an isolated installation. The installed
  0.12.0 bundle matches source and manifest hashes for all 15 managed files.
  Existing layout and keybinding files remained byte-for-byte unchanged; the
  previous mod bundle is retained by the managed installer.
- Independent source review identified two concurrency/state cases. The fixes
  passed targeted re-review: 107 controller/view tests plus 14 independent
  in-memory scenarios, with no remaining blockers in the affected behavior.
  The reviewer clarified that the prior render-time disclosure collapse already
  mitigated one controller-only observation.

At this checkpoint, fresh native Computer Use acceptance was pending. The
subsequent daily-workflow review is recorded above; the checker and simulated
view tests alone do not establish native geometry, accessibility, or real-service
behavior. No live Jira writes, credential changes, or documentation screenshots
were made.


## Earlier native checkpoints

The detailed [UX acceptance history](UX-REVIEW.md) preserves earlier native
interaction findings and host limits. Representative automated checkpoints:

| Version | Date | Recorded automated evidence |
| --- | --- | --- |
| 0.11.0 | 2026-11-01 | 134 Node tests; 15 Python installer tests |
| 0.10.1 | 2026-11-01 | 126 Node tests; 15 Python installer tests |
| 0.10.0 | 2026-11-01 | 126 Node tests; 56 Python tests |
| 0.7.1 | 2026-10-31 | 95 Node tests; 56 Python tests; later focus correction reran Node and native checker |
| 0.4.0 | 2026-10-31 | 54 Node tests; 24 adapter, 13 installer and 17 setup Python tests |
| 0.3.0 | 2026-10-31 | 41 Node tests; 23 adapter and 11 installer Python tests |

These are dated source-checkpoint results, not tests run during extraction.
The original runtime's shell transport/authentication checks are provenance,
not commands to missing files in this repository. Use the included bridge,
setup and installer suites for current validation and record any coverage gap.

## Limits

Stock native macOS Herdr 0.1.10 was exercised; later hosts and Linux GUI remain
unknown. The optional renderer's release helper is documented but its release
build was not executed. Development-build success does not prove release-mode
or other-platform behavior. Full screen-reader use is unverified; supplied
Input names were absent from macOS AX and Page Up/Down did not scroll the reader.
First-discovery timing and live delayed/failed comments remain investigations.
No target CI or publication claim follows from the historical evidence here.
