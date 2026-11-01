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

## Start here

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
| Agent configuration and native commands | [agent guide](AGENT-GUIDE.md), [JSON schema](../mods/jira-peek/fields.schema.json) |
| Optional terminal decoration | [renderer guide](../native/APP-HIGHLIGHT.md), [pinned patch](../native/herdr-app-0.1.10-highlight.patch) |
| Regression coverage | [tests](../tests/) |

## Packaging and product constraints

- Keep package, mod and installer versions aligned at experimental 0.1.0.
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
  the personal toolbar's `browse-jira` handler; a visible-only mod command
  cannot reopen a hidden panel by itself.
- Keep live configuration, credentials, issues and screenshots outside the
  repository. Use wholly fictional fixtures. A read-only workflow does not
  authorize Jira writes. Local document import is outside product scope.

## Historical evidence

On 2026-11-01, the original native 0.13.0 feature checkpoint passed **161
JavaScript tests and 15 Python installer tests**. The optional renderer passed
**225 native tests, with one existing release-download test ignored**, and a
macOS development build. Release mode and Linux GUI were not tested.

The renderer is pinned to Herdr app 0.1.10. It highlights exact selected keys
without terminal input or scrolling, synchronizes Follow/Paused/pinning, and
cleans up marks on lifecycle changes. Stock Herdr 0.1.10 supports ordinary
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
2. **Keyboard scrolling:** Page Down did not scroll despite reader focus on
   Herdr 0.1.10. Inspect current supported host capabilities; do not use
   undocumented input paths or mistake an automation limitation for a defect.
3. **Comments under delay/failure:** automated coverage exists, but the live
   pass saw only a quick empty response. Use isolated fictional fixtures for
   controlled failures, preserving core context and a local retry.
4. **Accessibility and platforms:** native AX output was sparse. Full screen
   reader use, hosts newer than the tested 0.1.11, Linux GUI, and optional release builds
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
