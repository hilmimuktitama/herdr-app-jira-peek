# Native verification record

## Component version reporting

2026-11-02, local unpublished 0.1.0 candidate.

- **Passed:** 31 installer tests, 9 updater tests, and 232 JavaScript tests.
  Regression coverage verifies that a newer core cannot satisfy an old or
  missing desktop app, and that core version discovery does not introduce an
  undocumented numeric minimum.
- **Passed:** offline doctor text and JSON report `herdr-app 0.1.11` and
  `herdr-core` through `hc 0.1.16` as separate components. The app gate is
  `herdr-app >= 0.1.10`; the core gate remains executable availability.
- README, recipe, repository instructions, installed agent guide and versioned
  host references now name the relevant component explicitly. The recipe and
  agent guides also distinguish 0.1.10 from the incorrect 1.10.0 transcription.
- Release metadata remains 0.1.0. No remote publication is included.

## ZIP installation and setup focus

2026-11-02, local unpublished 0.1.0 candidate; stock herdr-app 0.1.11 on macOS.
Remote `main` still pointed to the initial source checkpoint during this review.

- **Passed:** 232 JavaScript tests and 92 Python tests, including attachment
  preservation, custom panel IDs, conflicting edits, unsupported toolbars,
  unsafe paths, deferred form focus and stale/Help mount callbacks.
- **Passed:** complete source ZIP extracted outside a Git checkout; first
  installation and managed update with `--check --attach`. Both generated
  toolbar and mod passed Herdr's native checker. All 19 installed file hashes
  matched; stock layout, stock tabs and unrelated keys remained byte-identical.
  The sandboxed checker initially timed out; the same isolated test passed with
  approved native app access.
- **Passed:** offline native integration waits for real input focus events on
  Site URL after inspection and on the replacement token after local validation
  fails. The generated personal layout loaded without host errors, with the
  Jira Peek button beside Files/Changes. A native capture showed the focused
  Site URL outline and readable form fields. No real credentials or Jira
  connection were used.
- **Passed:** local managed update with native validation and a rollback
  backup. All 19 installed files matched the candidate; layout/key/settings
  hashes and private configuration metadata were preserved.
- **Not verified:** pointer clicks across each input and immediate typing/paste
  into the form. Computer Use failed at native pipe startup. The full field is
  now the native Input frame, including its padding and border; that removes the
  outer wrapper's unfocusable padding, but the user's report of all clicks
  failing is not independently reproduced. Their host version/install command
  remains unknown. The separate shortcut race in
  [host input gaps](HOST-INPUT-GAPS.md) remains open.

No commit, push, release, catalog change or version bump was performed.

## Field review follow-up

**2026-11-02, unreleased 0.1.0, stock herdr-app 0.1.11 on macOS arm64.**

- **230 JavaScript tests passed.** Six new regressions cover silent native
  programmatic input, excluded-action guarding, unread navigation, direct
  lookup, hyphenated title matching/origin validation and visible freshness.
- Isolated native integration passed Clear from matching/zero-result filters,
  title lookup, unseen-key navigation with retained Paused/query, existing
  screen/history discovery, same-origin lookup, Options/Help return,
  settings/conflicts/recovery, commands, cache clear and reconnection.
- Eight documentation captures and two temporary acceptance frames used only
  fictional catalog records. Reviewed the native exclusion prompt, direct
  lookup, persistent fetch time, dark/light and narrow/short layouts. Host
  update checks are redirected to the inactive loopback test endpoint so
  update notifications do not obscure captures or contact release services.
- **No new real pointer/keyboard pass:** Computer Use reported
  `Sky Computer Use native pipe startup failed` on both connection attempts.
  Background native integration does not prove focus, clipboard interaction,
  per-paint timing, short-Help traversal or human input safety.
- Exact v0.1.11 source inspection confirmed the absence of an ordinary
  mod scroll-position API and synchronous focus ownership in the current
  toolbar path. Three defects remain open in [host input gaps](HOST-INPUT-GAPS.md).
- Native candidate checker and managed local installation passed; all
  **19 installed files** matched source at **0.1.0**. Settings, layouts,
  keybindings, fields, connection reference and private configuration metadata
  were preserved, with the previous bundle retained as a rollback backup.
- Release metadata, Python fixture syntax, `git diff --check`, **168 local
  Markdown file links**, and **14 PNG metadata/CRC/trailing-data checks** passed.
  The reader PNG is byte-identical to the visually reviewed narrow capture.

The private field review is supplied evidence, not a newly repeated live Jira
test. No live Jira, Documents changes, host replacement or publication was
performed. Package/mod remain 0.1.0.

## Collapsible Help

**2026-11-01, unreleased 0.1.0, stock herdr-app 0.1.11 on macOS arm64.**

- **224 JavaScript tests passed**, including closed initial topics, exclusive
  expansion, collapse/reopen, matching Options labels, conditional guide links,
  native activation delegation, focus and nested draft preservation.
- Isolated native integration passed. Native pointer and keyboard review
  verified expansion, switching topics, Enter/Space activation and Escape
  return at 300px. Runtime errors: **0**. See the [UI record](UX-REVIEW.md#collapsible-help).
- Refreshed and visually reviewed the fictional Help capture; retained the
  other unchanged UI captures. All eight PNG metadata/CRC checks, **159 local
  file links**, release metadata and `git diff --check` passed.
- Managed local installation passed the native checker and verified all
  **19 installed files** at **0.1.0**. Settings, layouts, keybindings, field
  preferences, connection reference and private configuration metadata were
  preserved; the previous bundle remains backed up.

No version, dependency, transport or keybinding change. Existing keyboard
scrolling limitations remain. No live Jira or publication was exercised.

## Keyboard follow-up

**2026-11-01, unreleased 0.1.0, stock herdr-app 0.1.11 on macOS arm64.**

- **222 JavaScript tests passed.** Coverage includes reader/list action keys,
  ignoring held refresh repeats, ordinary editing and host-modifier guards,
  main versus nested focus returns, normal/short-panel paging and clamping,
  explicit keyboard preview precedence, and fresh key/URL lookups.
- Native keyboard review reproduced and verified the Enter-selection fix,
  page navigation, inline key/link copy, Options/Help and filter focus return,
  native Tab/Shift+Tab, slow refresh with the loaded body retained, and return
  to the originating terminal. Final runtime errors: **0**.
- Reader/Help keyboard scrolling and revealing off-screen Tab targets remain
  unsupported on this host. This is recorded as a failed acceptance condition,
  not inferred from passing controller tests. See the [UI record](UX-REVIEW.md#keyboard-follow-up)
  for exact coverage and the asynchronous native focus-handoff caveat.
- Final isolated native integration passed; eight wholly fictional captures
  were refreshed and passed PNG chunk/CRC/trailing-data checks without text
  or EXIF metadata. Changed frames were visually reviewed; the reader and
  narrow captures are identical. The other unchanged frames retain their
  earlier visual review. All **157 local Markdown file links**, release
  metadata and `git diff --check` passed.
- Installed locally after the native checker passed. All **19 installed
  files** match the sources at **0.1.0**. Settings/layout/keybinding/field
  hashes, connection reference and private configuration metadata were
  preserved; the prior bundle remains in a named backup. The preservation
  check did not read configuration or credential contents.

The change adds no dependency, changes no version or keybinding file, and
does not claim full keyboard-only accessibility. Python installer/updater
sources and checks from the earlier pass are unchanged. No live Jira,
screen reader, Linux GUI or publication was exercised.

## User efficiency pass

**2026-11-01, unreleased 0.1.0 working tree, stock herdr-app 0.1.11 on macOS arm64.**

- **217 JavaScript tests passed.** Added coverage for two bounded request
  slots, latest-choice coalescing, same-key deduplication/refresh ordering,
  late metadata, stale request failures, connection revocation from either
  slot, TTL=0 late-body eviction, manual choice versus automatic backoff,
  keeping the spare slot free of automatic refresh, stable pointer previews,
  immediate filter focus, clear behavior, direct actions, loading titles,
  inline copy feedback and stable action placement during loading/failure.
- The isolated real-host integration passed all existing checks and delayed
  backend cases. Selected detail completed while its older metadata/issue
  request was still running. Cached selection started no request. Baseline
  versus candidate: **2,375 → 312ms** behind metadata and **2,381 → 302ms**
  behind a prior issue, with a two-second fictional backend delay and 100ms
  result sampling. Cached controller selection was **0ms**; no native paint
  latency or real Jira response-time claim is made.
- Native pointer/keyboard review passed the focused find/compare/copy/clear/
  read journey and refresh failure/retry. The final error placement was
  inspected after native hot reload; the action row stayed above the error,
  and the loaded body remained available. Final native runtime errors: **0**.
- Eight fictional native PNGs were captured, including 300px browsing and a
  300×400px panel. All eight were visually reviewed and passed PNG chunk,
  CRC and trailing-data checks with no text or EXIF metadata. See the
  [UI record](UX-REVIEW.md#user-efficiency-pass).
- Applied the managed local update after the real native checker passed.
  All **19 installed files** match the working-tree sources at **0.1.0**.
  Layout, keybinding, field-preference and host-settings hashes were retained;
  the connection reference and private configuration file metadata were
  unchanged. The preservation check did not read configuration or credential
  contents. The previous managed bundle remains in a named backup.
- Release metadata, all **154 local Markdown file links** and
  `git diff --check` passed.

No dependency, Jira transport, credential handling or version changed.
The prior Python updater/installer checks below remain applicable; their
sources were unchanged during this pass. Full screen-reader use, physical
touch hardware, Linux GUI and live Jira were not exercised. Publication and
remote CI are outside this local update.

## Options and Help navigation

**2026-11-01, unreleased working tree, stock herdr-app 0.1.11 on macOS arm64.**
Package and mod remain **0.1.0**. No commit, tag, push, release, visibility or
catalog change was performed for this update.

- **202 JavaScript tests passed**, including direct Options/Help navigation,
  matching explanations for all eleven Options labels, filter/selection/Paused
  preservation, main-view-only panel close and nested form help.
- `capture.py --app` passed the real native async integration suite, including
  the new Options → Help → Issues and Help → Options → Issues routes with the
  same filter, selected issue and list mode. It also retained the existing
  discovery/history, URL lookup, freshness, field/preference conflict/recovery,
  agent-command, cache-clear and reconnect checks.
- Captured and visually reviewed all six fictional native PNGs. Options at
  300px and Help at 420px show explicit returns; the four reader captures are
  byte-identical to the previous captures. All six passed PNG chunk, CRC and
  trailing-data checks with no text or EXIF metadata. The fixture reported no
  runtime errors and closed its own app/core.
- Applied a managed local update with the real native checker before
  replacement. All **19 installed files** match the working-tree sources.
  Layout, keybinding, field-preference and host-settings hashes were retained;
  the connection reference and private configuration file metadata were
  unchanged. Configuration and credential contents were not read by this
  preservation check. The prior managed bundle remains in a named backup.
- Release metadata and `git diff --check` passed. Python installer/updater
  coverage is the earlier **88-test** result below; those Python sources did
  not change during this UI fix.

Computer Use screenshots did not consistently refresh with the native
accessibility state. Herdr's own capture showed the current frame, so this is
partial interactive evidence, not a complete keyboard or accessibility pass.
Live Jira, Linux GUI and publication were not exercised. See the
[UI review](UX-REVIEW.md#options-and-help-navigation).

## Release update tooling

**2026-11-01, unreleased working tree on macOS arm64, Python 3.9 and stock
herdr-app 0.1.11.** The package/mod version remains 0.1.0. No commit, tag, push,
GitHub release, visibility change or catalog action was performed for this work.

- **200 JavaScript tests passed.** Panel UI and Jira transport behavior were
  unchanged; no new native visual or live Jira review was performed.
- **88 Python tests passed**, including numbered tag ordering,
  annotated/lightweight tags, ignoring preview tags and branch tips, exact
  versions, explicit downgrades, no-op updates, tag changes during fetching,
  malformed releases, local edits, concurrent installs, failed native checks,
  failed replacement, backup restore and preserving current settings.
  Network operations use isolated local Git repositories and fictional data.
- A separate installed-helper process updated from a local bare repository
  after its source checkout was deleted. Another restored a backup offline
  from its own custom app home, despite a conflicting `HERDR_APP_HOME`.
- **Real native migration passed:** extracted the actual original 0.1.0
  source from `56be806`, installed its **17-file** bundle, updated to the new
  **19-file** bundle, and restored the original backup. All three native
  checks passed; complete manifest hashes, fictional configuration contents
  and reference, field preferences, personal layout, keys and both backups
  were verified. The first sandboxed native check timed out; the same isolated
  check and final recheck passed with native runtime access outside the sandbox.
- Preparing **0.1.1** in a temporary copy of the actual candidate promoted
  release notes, aligned both manifests, passed the tag consistency check and
  passed the installer suite. The final full suite includes **25 installer**,
  **9 updater** and **4 release** tests, covering the candidate-hash and
  historical-version safeguards.
- Shell syntax and pinned, SHA-256-verified **ShellCheck 0.11.0** passed for
  all **9 shell files**. The offline doctor, current-version/tag metadata
  checks, local documentation link targets and `git diff --check` passed.
  Changed source, docs and wholly fictional fixtures were inspected; no
  screenshot asset changed and no private configuration was packaged.

This verifies local tooling and native loading, not GitHub authentication,
remote CI, Linux execution, native hot-reload timing, or a published update.
Existing 0.1.0 users need one managed install from a future release containing
the helper. See [user commands](../README.md#update-remove-and-inspect) and
[release procedure](../RELEASING.md#frequent-release-workflow).

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
| Capability check | Offline doctor passed with stock herdr-app **0.1.11**, macOS arm64 |
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
- **Stock herdr-app 0.1.11, macOS arm64, isolated fictional fixture:** native
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
- **Stock herdr-app 0.1.11, macOS arm64:** the final isolated native run passed
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
- **Stock herdr-app 0.1.11, macOS arm64:** the isolated capture fixture passed real
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
- **Native Computer Use passed on stock herdr-app 0.1.11, macOS arm64:** edited a label;
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
- The isolated native installer check passed on **herdr-app 0.1.11, macOS arm64**.
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

Native interaction checks on **herdr-app 0.1.11, macOS arm64** used only the
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
| Isolated stock-host check | `scripts/install-app.py --app-home <temporary> --check` passed with stock herdr-app **0.1.10** |
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

Verified on 2026-11-01 with the optional local herdr-app 0.1.10 renderer
extension on macOS. The mod detects that capability and remains compatible
with the stock host. This is evidence from the original native source checkpoint, not the extracted tree.

A later publication-documentation pass on the same date refreshed the four
standard previews with stock herdr-app 0.1.10 using the isolated fictional fixture.
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

Stock native macOS herdr-app 0.1.10 was exercised; later hosts and Linux GUI remain
unknown. The optional renderer's release helper is documented but its release
build was not executed. Development-build success does not prove release-mode
or other-platform behavior. Full screen-reader use is unverified; supplied
Input names were absent from macOS AX and Page Up/Down did not scroll the reader.
First-discovery timing and live delayed/failed comments remain investigations.
No target CI or publication claim follows from the historical evidence here.
