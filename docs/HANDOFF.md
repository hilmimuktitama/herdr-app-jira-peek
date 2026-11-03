# Native Jira Peek development handoff

Current checkpoint: **2026-11-01, experimental 0.1.0 private preview**.
Target: [hilmimuktitama/herdr-app-jira-peek](https://github.com/hilmimuktitama/herdr-app-jira-peek).
This checkout carries forward the native edition from the
[original public TUI repository](https://github.com/hilmimuktitama/herdr-jira-peek).
The authorized delivery resets Git history to one initial commit and the
`v0.1.0` tag, removes the superseded 0.13.0 tag/release and keeps the repository
private. Recovery material stays outside tracked source. No new GitHub release
or catalog submission is included. The existing `herdr-mod` topic would enable
catalog discovery if visibility changed; follow [RELEASING.md](../RELEASING.md).
The [current verification record](VERIFICATION.md#experimental-010-readiness)
separates local candidate checks from historical CI and native workflow evidence.

Included functionality **2026-11-01, after the earlier extraction:** native typography
follows Herdr settings, the panel has a close action, and agents and the UI
share field layouts and reader preferences. The installed
[agent guide](AGENT-GUIDE.md) maps supported settings and native commands;
the [personal toolbar integration](PANEL-INTEGRATION.md) adds one keyboard
handoff from the terminal into filtering and back, including a hidden panel.
[Current validation](VERIFICATION.md#terminal-to-peek-keyboard-handoff)
records the local update and its checks. Earlier working-tree and public-release
statements below describe their dated historical checkpoints.

**Unreleased update tooling, 2026-11-01:** the installed update helper selects
numbered release tags, checks before replacement and restores named backups.
Version preparation and CI consistency checks support frequent releases.
See [update verification](VERIFICATION.md#release-update-tooling) and the
[release workflow](../RELEASING.md#frequent-release-workflow). This working-tree
change does not create a release, tag or remote change; package/mod remain
0.1.0 until the next release is prepared.

**Unreleased navigation fix, 2026-11-01:** Options and general Help now have
an explicit ← Issues return. Help explains all eleven Options with matching
labels; nested form help preserves drafts. See the [UI review](UX-REVIEW.md#options-and-help-navigation)
and [validation](VERIFICATION.md#options-and-help-navigation). This also keeps
package/mod version 0.1.0.

**Unreleased efficiency pass, 2026-11-01:** issue rows preview without closing
or jumping the list; opening Issues focuses the filter. Copy and refresh are
beside the issue key, with inline confirmation and stable action placement.
Two bounded request slots prioritize the latest selection over slow background
work; cached issues remain immediate. The [UI review](UX-REVIEW.md#user-efficiency-pass)
records click counts and native latency comparisons; [validation](VERIFICATION.md#user-efficiency-pass)
records regression and native interaction coverage. Version remains 0.1.0.

## Start here

**Mouse-return hint fix, 2026-11-03:** the reader now invalidates its cached
render on an outside pointer press. The existing focus condition hides the
hint without changing its reserved space. Three mouse returns and three Escape
controls showed a blank hint in the first sampled frame and identical passage
pixels; three hide/reopen cycles also had zero movement. All 239 JavaScript
tests and the native checker passed. The checked mod update is installed in
the active everyday app with a rollback copy; host, keys, layouts and core
were preserved. See [focused verification](VERIFICATION.md#mouse-return-hint).

**Everyday activation, 2026-11-03:** the user approved the desktop switch.
The verified patched 0.1.12 executable, current mod and `layout.focus:jira-peek`
binding are now active together. The personal `herdr-app` launcher points to
that executable; the signed stock bundle remains intact. All 19 managed files
match this checkout, native focus/rendering passed, and the same core process
and six live terminals survived. Keys and launcher rollback details are stored
privately alongside the managed mod backup. See [activation verification](VERIFICATION.md#everyday-activation).

**Refresh focus and truthful hints, 2026-11-03:** issue-action shortcuts now
include Refresh, and an already focused disabled button retains its handle
through loading. The reader hint hides when unfocused while reserving its
space. [Fresh verification](VERIFICATION.md#refresh-focus-and-shortcut-hints)
passed both clipboard directions, delayed request/native activation checks,
three zero-movement End cycles and 40 complete shortcut queries with zero
terminal bytes. All 238 JavaScript tests and the native checker pass. The
stock app still lacks the patched capability; the later approved activation
above uses the separate patched host.

**Reader controls and current-host retest, 2026-11-03:** Shift+Y now works
from Comments and Details, and the reader hint keeps a stable height across
focus changes. Three fresh-End hide/reopen cycles had zero passage movement.
The [0.1.12 retest](VERIFICATION.md#reader-controls-and-0112-retest) found
14 terminal leaks in 40 openings with the everyday configuration, plus one
truncated query. The corrected mod and patched 0.1.12 host passed all 40 with
zero bytes. The [build recipe](../native/APP-INPUT.md) now pins 0.1.12; 260
native tests and 237 JavaScript tests passed. The installed app and personal
binding are unchanged, so activation is still separate from this verified
candidate. Earlier checkpoints below describe historical evidence.

**Native input follow-up, 2026-11-03:** the remaining shortcut, keyboard
reading and hide/reopen findings now have a small, separate
[herdr-app 0.1.11 patch](../native/APP-INPUT.md). The mod exposes synchronous
focus entry and retains an initial query even before the native focus event.
[Verification](VERIFICATION.md#native-input-follow-up) records zero terminal
bytes in 20 visible + 20 hidden live openings, native regressions, Help focus,
and three position cycles. These fixes require the patched host and the new
`layout.focus:jira-peek` binding. Stock 0.1.11 still has the documented gaps;
this work did not replace the installed app or publish anything. Earlier
checkpoints below remain historical evidence.

**Component version clarity, 2026-11-02:** the app minimum is explicitly
`herdr-app >= 0.1.10`. `herdr-core` has its own version, reported through `hc`;
the installer only requires its executable, not a numeric core minimum.
Doctor reports both separately. The recipe and installed agent guide forbid
conflating the components or transposing 0.1.10 into 1.10.0. Jira Peek remains
0.1.0; see [verification](VERIFICATION.md#component-version-reporting).

**ZIP/setup follow-up, 2026-11-02:** explicit `--attach` creates a personal
layout plus the toolbar toggle; the normal update path still preserves layout
and shortcut choices. Setup uses the native input as its entire visible field
and waits for mount before initial/retry focus. See
[verification](VERIFICATION.md#zip-installation-and-setup-focus). Version is 0.1.0;
no remote publication is included.

**Field-review follow-up, 2026-11-02:** filtered issue actions, Clear,
unread navigation, direct lookup/title matching and visible fetch time have
mod-level corrections. See [verification](VERIFICATION.md#field-review-follow-up)
and [UX evidence](UX-REVIEW.md#field-review-follow-up). Native integration and
static captures passed; the native Computer Use pipe could not start, so
pointer/keyboard retesting remains outstanding. The three
[host input gaps](HOST-INPUT-GAPS.md) remain open, including the terminal
shortcut race. This is not a complete keyboard-only pass. Version stays 0.1.0.

**Collapsible Help, 2026-11-01:** Help starts with topic headings and opens
one explanation at a time. Native toggles support pointer and Enter/Space
activation. See [verification](VERIFICATION.md#collapsible-help).

**Keyboard follow-up, 2026-11-01:** Options/Help restore working focus;
local actions and issue-list paging are documented in the
[keyboard guide](../README.md#keyboard-first). Enter commits an explicit
preview instead of overriding it with a key-shaped filter. Native testing
confirmed that stock 0.1.11 still cannot keyboard-scroll long reader/Help
content or reveal off-screen Tab targets. See [keyboard verification](VERIFICATION.md#keyboard-follow-up).

Read the [public data policy](../AGENTS.md), inspect the current checkout and
preserve unrelated changes. Then read the [guide](../README.md),
[recipe](../RECIPE.md), [verification](VERIFICATION.md),
[UX acceptance](UX-REVIEW.md), and [research](MOD-REFERENCES.md).
Commands run from the repository root; there is no `app/` prefix.

| Area | Entry points |
| --- | --- |
| Native UI, focus, navigation and requests | [main.js](../mods/jira-peek/main.js) |
| Discovery, selection and cache freshness | [model.js](../mods/jira-peek/model.js) |
| Bridge, content and transport | [app-bridge.sh](../scripts/app-bridge.sh), [app-issue.jq](../scripts/app-issue.jq), [jira-rest.sh](../scripts/jira-rest.sh), [common.sh](../scripts/common.sh) |
| Setup and managed installation | [app-setup.py](../scripts/app-setup.py), [install-app.py](../scripts/install-app.py) |
| Release updates, rollback and version preparation | [update-app.py](../scripts/update-app.py), [release.py](../scripts/release.py) |
| Agent configuration and native commands | [agent guide](AGENT-GUIDE.md), [JSON schema](../mods/jira-peek/fields.schema.json) |
| Optional terminal decoration | [renderer guide](../native/APP-HIGHLIGHT.md), [pinned patch](../native/herdr-app-0.1.10-highlight.patch) |
| Regression coverage | [tests](../tests/) |

## Packaging and product constraints

- Keep package and mod versions aligned; the installer derives its version
  from those manifests. Use `scripts/release.py` for later releases and
  `scripts/update-app.py` for tag-based updates. See the
  [release workflow](../RELEASING.md#frequent-release-workflow).
  Preserve managed updates from the earlier 0.13.0 version. Mod ID `jira-peek`,
  owner marker `herdr-jira-peek` and installed runtime paths are compatibility
  contracts, not repository-name typos.
- The root catalog entry is `RECIPE.md`, `preview.png`, `mods/jira-peek` and
  optional `keys.json`. The recipe documents manual installation. The installer must
  assemble the runtime; copying the source mod alone is insufficient. Verify
  installation without access to the original source repository.
- Keep Peek attached to the main Herdr window, with concise copy and a compact
  default reader. Keep issue identity visible while scrolling/filtering; do
  not restore a redundant terminal-title row or a description disclosure gate.
- Incoming output must respect Paused selection. Help and Connection return
  paths preserve search, selection and reading position. Issue auto-refresh
  and terminal discovery are separate controls and behaviors.
- Use native configurable shortcuts. Ctrl+Shift+J is an optional example,
  not a Herdr default. Installation preserves layouts and keys; attachment and
  shortcut merging are explicit personal choices. The current example requires
  the patched host's `layout.focus` command and the attached block ID; the
  old asynchronous toolbar handler must not remain the shortcut target.
- Keep live configuration, credentials, issues and screenshots outside the
  repository. Use wholly fictional fixtures. A read-only workflow does not
  authorize Jira writes. Local document import is outside product scope.

## Historical evidence

On 2026-11-01, the original native 0.13.0 feature checkpoint passed **161
JavaScript tests and 15 Python installer tests**. The optional renderer passed
**225 native tests, with one existing release-download test ignored**, and a
macOS development build. Release mode and Linux GUI were not tested.

The renderer is pinned to herdr-app 0.1.10. It highlights exact selected keys
without terminal input or scrolling, synchronizes Follow/Paused/pinning, and
cleans up marks on lifecycle changes. Stock herdr-app 0.1.10 supports ordinary
Peek; terminal decoration requires the experimental local extension.

Four stock-host previews and six optional-renderer captures used entirely
fictional fixtures and received visual/metadata review on 2026-11-01. The
0.12.1 workflow retest recorded four passes and one partial; comment delay/error
timing was not observed live. Earlier 0.12.0 evidence includes 61 Python tests
and transport/auth checks. None of these results replaces extraction checks.
Details and limitations are in [verification](VERIFICATION.md) and
[UX acceptance](UX-REVIEW.md).

## Remaining investigations

1. **First discovery:** a first reference required a manual scan while later
   output was detected automatically. Reproduce with focus, source, Follow state
   and timing recorded before changing behavior. Auto-refresh Off does not
   explain missing discovery.
2. **Host adoption:** keyboard scrolling, shortcut ownership and hide/reopen
   position now pass on the optional patched 0.1.12 build. Stock hosts retain
   those defects. Upstream adoption and newer host versions remain separate
   work; use [the activation guide](../native/APP-INPUT.md).
3. **Comments under delay/failure:** automated coverage exists, but the live
   pass saw only a quick empty response. Use isolated fictional fixtures for
   controlled failures, preserving core context and a local retry.
4. **Accessibility and platforms:** native AX output was sparse. Full screen
   reader use, hosts newer than the tested 0.1.12, Linux GUI, and optional release builds
   remain unverified. External navigation and credential forms were outside
   the latest workflow pass; earlier fictional setup evidence is separate.

## Verify and deliver

Review scripts before execution, then follow [CONTRIBUTING.md](../CONTRIBUTING.md)
for Node/Python checks and an isolated real-host install. Verify bundle hashes,
managed updates and preservation of layout/keybindings. The checker does not
replace native visual QA. Keep source inspection, automated checks and observed
interaction evidence distinct, with dates and limitations.

Update [candidate validation](VERIFICATION.md#experimental-010-readiness)
when the standalone tree or its delivery status changes. Follow
[RELEASING.md](../RELEASING.md); no historical
checkpoint implies that a target tag, release or catalog entry exists.
