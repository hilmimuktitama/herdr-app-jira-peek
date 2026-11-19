# Reliability development

Treat intermittent pin failures, stale controls and unexplained blank readers as
bugs. Prioritize reproductions and recovery over new features. This guide maps
primary references to this project's actual runtime; it is not a claim that all
reported failures have been resolved.

## The stack and its contracts

Jira Peek runs JavaScript in Herdr's native GPUI shell, using `gpui-kit` and
`gpui-base`, with shell/Python/jq helpers and read-only Jira transports. Node is
the test runner, not the application runtime.

- [Herdr's mod guide](https://github.com/herdrdev/herdr-app/blob/master/defaults/AGENTS.md)
  and [mod development instructions](https://github.com/herdrdev/herdr-app/blob/master/docs/mods.md)
  are the host references. Use the installed `AGENTS.md`, `herdr.d.ts` and
  `gpui-kit.d.ts` for the specific binary being tested. Online master can differ.
  The checker renders once; deferred rendering and repeated interaction need a
  running window. Inspect reported errors even when the previous screen survives.
- [GPUI Kit rendering](https://gpui-kit.com/docs/render/) explains the separation
  between persistent view state and each frame's element description. Keep
  network work, entity construction and action execution outside render/layout.
- [GPUI Kit entities](https://gpui-kit.com/docs/entity/) explains retained
  identity and ownership. Keep native child lifetimes bounded, invalidate the
  child that reads changed state, and recreate released handles outside layout.
- [GPUI Kit contexts](https://gpui-kit.com/docs/context/) explains notification
  and asynchronous access. Use the callback's context; do not retain an event
  context across an await. Rust examples explain the concepts; use Herdr's
  generated JavaScript signatures for implementation.
- [Atlassian's rate-limit implementation guide](https://developer.atlassian.com/cloud/jira/platform/build-an-app-that-respects-rate-limits/)
  specifies response-header-aware pacing, scoped cooldowns, and retry behavior.
  Capture `Retry-After` and respect it before retrying eligible read requests.
  Bound attempts and add jitter to fallback backoff. A fixed delay alone cannot
  represent a server-requested cooldown.

References checked 2026-11-19. Required host remains **herdr-app >= 0.1.10**;
herdr-core has an independent version and must provide `hc`. The installed
**0.1.16** declarations add the native checker flag, window activity,
cancellable folder watches and an `exec` timeout option. Peek feature-detects
them and keeps the previous path when they are absent; this does not change the
installation floor. Keyboard pane entry needs **0.1.12 or newer**.
The focused `--keyboard-entry` fixture verifies `pane.go` entry and a real
PID-targeted Escape on the isolated host; see
[the native keyboard check](screenshots/README.md#native-keyboard-entry-and-escape).
It records entry and Escape separately, and a blocked Escape is never a full
pass. On **0.1.16** with `hc 0.1.21`, both passed.
The native rig now prefers the installed desktop bundle on macOS and records
executable version/hash and bundle metadata. Staged updates or inconsistent
identity stop the run; see [host selection and provenance](screenshots/README.md).
Fixture layouts, font cases and fictional content are intentional differences
from a user's personal layout.

## Diff-triggered reliability checks

Read only the rows whose trigger matches the proposed diff. The
[feature dictionary](FEATURE-DICTIONARY.md#change-preservation-workflow) still
supplies coupled contracts and preservation rules; this table exists so past
failures are re-checked without rereading every finding.

```sh
python3 scripts/verify-plan.py --diff origin/main...HEAD   # matching rows
python3 scripts/verify-plan.py --check                     # table and case links
```

Trigger cells contain backticked file globs and `~symbol` tokens. A row matches
when one path matches the changed files and, if it has symbols, one symbol
appears in an added or removed line of a matching file. If more than half the
rows match, treat the change as cross-cutting and read all of them. A row
records what to verify, not proof that the current code does it.

| ID | Risk | Trigger (diff) | Verify | Evidence |
| --- | --- | --- | --- | --- |
| RC-01 | Row-action delivery | `mods/jira-peek/main.js` `~rowActions` `~drainRowActions` | Each queued action executes once, keeps the Pin/Unpin value painted at click time, and validates its original target; idle wakes never redraw or fetch. | HC-01, HC-02, HC-06, HC-07, HC-08, HC-09 |
| RC-02 | Action leases | `mods/jira-peek/main.js` `~auxiliary` `~lease` | Entering or leaving Options, Help, Fields, Connection or another source retires earlier selected and row-action leases; rejection feedback cannot revive them. | HC-02 |
| RC-03 | Painted identity | `mods/jira-peek/main.js` `~selectedRow` `~render` | After selection, Clear list, lookup, hide/reopen and pin moves, painted key, title, status and Copy/Open/Pin targets name the same issue and never borrow another body. | HC-03, view tests, native walkthrough steps 3 and 8 |
| RC-04 | Request priority | `mods/jira-peek/main.js` `~backgroundRequest` `~request` | At most two issue/metadata reads, no duplicate same-key request, selected details keep priority, and stale completions release only their own slots. | HC-04, controller tests, reliability scenarios |
| RC-05 | Cache identity | `rust-backend/src/storage.rs` `rust-backend/src/main.rs` `~epoch` `~generation` | Publication revalidates key, field signature and connection epoch under the same lock; an older completion cannot project or publish into a newer epoch or field set. | bridge cache tests |
| RC-06 | Clear-cache scope | `rust-backend/src/clear_cache.rs` `scripts/clear-cache.sh` | Remove only immediate regular cache files of an initialized state directory; refuse traversal, symlinked paths and unresolved roots; advance the epoch even without a cache directory. | `rust-backend/tests/clear_cache_test.py`, bridge tests |
| RC-07 | Rate limits | `rust-backend/src/transport.rs` `scripts/jira-rest.sh` `~retry_after` `~Retry-After` | Bound Retry-After to 1–86400 seconds, fall back to 30 on absent or malformed values, and block only eligible read submissions. Known gap: issue and comment refreshes still use a fixed 30-second cooldown. | transport tests; [current findings](#current-findings-and-remaining-work) |
| RC-08 | Credentials and destinations | `rust-backend/src/setup.rs` `rust-backend/src/credentials.rs` `~token` | Tokens never enter arguments, environment, logs or the repository; managed netrc applies only to its matching host; foreign origins, redirects and URL credentials are rejected before a request. | setup and transport tests, lifecycle acceptance |
| RC-09 | Field-layout concurrency | `mods/jira-peek/model.js` `~updateFieldFile` `~readFieldLayout` | A stale save is rejected, unrelated connections and retired keys survive, and an accepted edit round-trips through the shared file. | field-layout tests, setup-controller tests |
| RC-10 | Search scope | `rust-backend/src/discovery.rs` `~query` `~project in` | Generated JQL is always intersected with configured projects, user text cannot close its quoted literal, and non-allowlisted keys are rejected before dispatch. | discovery tests, parity tests |
| RC-11 | Lifecycle recovery | `rust-backend/src/management/install.rs` `rust-backend/src/management/update.rs` `~backup` | A validated backup is recorded before the active bundle moves; interruption recovery never selects an edited backup; availability checks stay read-only. | lifecycle acceptance, management tests |
| RC-12 | Failed refresh retention | `mods/jira-peek/main.js` `~fetchedAt` `~stale` | A failed refresh keeps the last loaded body, fetch time and pin; Retry clears the error, and unrelated old failures cannot replace current feedback. | HC-05, view tests |

## Development loop

1. Identify the affected [JP contracts](FEATURE-DICTIONARY.md) and run
   `python3 scripts/verify-plan.py --diff` to select reliability rows. Write the
   expected visible result and action target before changing code.
2. Make the failure deterministic with fictional data: delay the worker or
   transport, reorder responses, retire a native row, switch source, hide/reopen,
   or exclude the selection with a filter. Verify the regression fails first.
3. Fix the narrow owning layer. Keep source/connection generation checks,
   loaded content on transient failure, and explicit pin/unpin intent. Never
   recover by silently clearing user state or blindly replaying actions.
4. Run `python3 scripts/verify.py --fast` while iterating. It prints the
   reliability rows matching changes since `origin/main` (advisory), then runs
   the cheap table, verifier, release and whitespace checks, then the Node
   suite. Run `python3 scripts/verify.py --full` before handoff; it adds the
   runtime build and the Python compatibility suites.
5. Run the relevant model/controller/view/bridge tests, then the native fixture.
   Check painted content and action targets separately. A correct selected key
   in memory does not prove the retained reader displays it.
6. Record versions, results and remaining gaps outside the published tree.
   Before release, repeat pointer Pin → Unpin → Pin after scroll, selection,
   filtering and hide/reopen, and verify clipboard targets. Follow
   [the native walkthrough](screenshots/README.md#pin-interaction-walkthrough).

`--fast` skips the Python suites, the runtime build and cargo; it says so on
success. Do not report it as a release gate. `--full` is the complete local
loop, not CI: CI additionally runs cargo fmt/clippy/test, transport and TLS
suites, parity, lifecycle acceptance and the platform matrix. Native acceptance
is separate from both. `--full --fixtures DIRECTORY` prepares the fixture
runtime and runs the seven fixture-backed tests instead of skipping them.

Use `python3 docs/screenshots/capture.py --app --row-stress --output-dir
/absolute/temporary/qa-directory` on one shell line. It isolates app/core state
and uses a fictional backend. The rig also disables the Promise row worker and
checks three queued pin/unpin cycles plus copy feedback using native timer
callbacks. This proves scheduler fallback, not native pointer dispatch or a
clipboard paste round-trip.

## Verifier checks

`python3 scripts/mutation-check.py` removes one guard at a time in a disposable
copy and requires a named test to fail. It covers origin validation, the
Markdown cap, custom-field bounds, pin intent, duplicate fields, single
execution of queued row actions, the native timer call site, the enqueue wake,
actions queued while draining and the worker drain. `--rust` applies three
slower Rust mutations: JQL project scoping and the two clear-cache rejection
guards. A survivor is a verifier gap: add the regression or record why the
guard is untested. HC-07 was written for M-06. It does not prove coverage and
is not a CI gate. The harness keeps the Promise row worker dormant in
`scenarios.test.js`; HC-09 in `worker.test.js` exercises the worker wake and
drain. A deleted worker drain would spin synchronously, so M-12 models a worker
that drops actions instead.

## Current findings and remaining work

**Native pane entry and Escape — verified on herdr-app 0.1.16 (JP-014,
JP-017).** The isolated fictional fixture focuses a terminal, enters the demo
Peek pane with `pane.go` right, and posts Escape only to the isolated PID with
`CGEventPostToPid`. It recorded terminal `focused_pane` → Peek pane → terminal
and the mod received `key: escape`. The same run confirmed the instrumented
mod's log stayed under the disposable `HERDR_APP_HOME`; the corresponding log
under `~/.config/herdr-app` was unchanged. This does not synthesize the user's
entry chord, and pointer, clipboard and live-Jira checks remain separate.

**Queued-action starvation — previously fixed (JP-012–014).** The native
100 ms wake serviced virtual rows but did not drain queued row actions. With a
dormant Promise worker, pin and copy remained queued. The wake now also drains
actions through existing validation. Removing entries before execution prevents
the worker and timer from applying the same action twice. Idle ticks do not
redraw or request Jira data. The regression checks repeated pin/unpin, one copy,
and rejection after the selected target changes.

**Queued pin intent and auxiliary return — fixed (JP-012–013, JP-015).**
Repeated activations of the selected Pin control before the native wake could
be executed as opposing toggles. The inline control now retains its requested
Pin/Unpin value; P remains a toggle. Separately, rejection feedback could close
Options and let the next obsolete queued action execute. An auxiliary-screen
revision retires earlier leases across entry and return, for selected and
explicit row actions. These are separate from the earlier starvation fix.

The deterministic fictional cases in `tests/reliability/scenarios.test.js`
cover those failures, rapid selection and delayed reads, failed refresh recovery,
state boundaries and over 10,000 cumulative mock row allocations; HC-07 requires
each queued entry to execute once when the wake repeats. Run them with
`node --test tests/reliability/*.test.js`, or the whole fast loop with
`python3 scripts/verify.py --fast`. A passing mock row or request check still
requires the separate native walkthrough.

**Blank reader/panel — root cause unconfirmed (JP-008, JP-010, JP-028,
JP-031–033).** Distinguish these cases during reproduction:

- A whole blank panel: inspect host render/deferred-row errors and released
  entity ownership in the isolated app.
- A visible key with missing content: inspect request state, response projection,
  field layout and cache identity; preserve known content during refresh failure.
- A legitimate empty result: verify filter, Paused startup, Clear list baseline,
  terminal availability and deliberate reader entry before changing selection.

For each failure, retain only fictional evidence: host versions, transition
sequence, request phase/generation, pending action count, and a fresh frame.
Do not log terminal output, Jira records, origins, tokens or raw transport errors.
An explicit recovery state must name its cause; a catch-all empty state would
hide the failure. Add a regression once a specific path is reproduced.

**Partial-drag clipboard — unresolved (JP-042).** Isolated native checks
confirmed whole-block copying after issue changes, but partial-drag attempts
could retain the preceding clipboard value despite a painted selection. The
cause is unconfirmed. Keep range selection, keyboard focus and actual paste
results separate when reproducing; a whole-block copy does not validate a range.

**Transport cooldown — confirmed gap, follow-up (JP-028–029, JP-033).**
`scripts/jira-rest.sh` maps HTTP 429 to a failure code without propagating
response headers; the controller uses a fixed 30-second selected-issue cooldown.
REST collection discovery now propagates bounded numeric Retry-After and blocks
collection submissions until expiry (JP-043); it never retries automatically.
For existing issue/comment refreshes, design a bounded, validated retry-delay field across transport/bridge/controller,
shared appropriately across copies of a connection. Test 429/503, malformed or
missing headers, expiry and manual retry before shipping it. This gap is not
established as the cause of the reported blanks.

Release acceptance requires the automated suites, a passing native checker,
isolated integration/stress evidence and actual pointer/keyboard checks on the
chosen stock host. Live Jira, Linux GUI and full accessibility need their own
evidence; none follows from offline tests.
