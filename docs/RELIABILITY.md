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

References checked 2026-11-11. Required host remains **herdr-app >= 0.1.10**;
herdr-core has an independent version and must provide `hc`.
The native rig now prefers the installed desktop bundle on macOS and records
executable version/hash and bundle metadata. Staged updates or inconsistent
identity stop the run; see [host selection and provenance](screenshots/README.md).
Fixture layouts, font cases and fictional content are intentional differences
from a user's personal layout.

## Development loop

1. Identify the affected [JP contracts](FEATURE-DICTIONARY.md). Write the
   expected visible result and action target before changing code.
2. Make the failure deterministic with fictional data: delay the worker or
   transport, reorder responses, retire a native row, switch source, hide/reopen,
   or exclude the selection with a filter. Verify the regression fails first.
3. Fix the narrow owning layer. Keep source/connection generation checks,
   loaded content on transient failure, and explicit pin/unpin intent. Never
   recover by silently clearing user state or blindly replaying actions.
4. Run relevant model/controller/view/bridge tests, then the native fixture.
   Check painted content and action targets separately. A correct selected key
   in memory does not prove the retained reader displays it.
5. Record versions, results and remaining gaps outside the published tree.
   Before release, repeat pointer Pin → Unpin → Pin after scroll, selection,
   filtering and hide/reopen, and verify clipboard targets. Follow
   [the native walkthrough](screenshots/README.md#pin-interaction-walkthrough).

Use `python3 docs/screenshots/capture.py --app --row-stress --output-dir
/absolute/temporary/qa-directory` on one shell line. It isolates app/core state
and uses a fictional backend. The rig also disables the Promise row worker and
checks three queued pin/unpin cycles plus copy feedback using native timer
callbacks. This proves scheduler fallback, not native pointer dispatch or a
clipboard paste round-trip.

## Current findings and remaining work

**Queued-action starvation — fixed in this change (JP-012–014).** The native
100 ms wake serviced virtual rows but did not drain queued row actions. With a
dormant Promise worker, pin and copy remained queued. The wake now also drains
actions through existing validation. Removing entries before execution prevents
the worker and timer from applying the same action twice. Idle ticks do not
redraw or request Jira data. The regression checks repeated pin/unpin, one copy,
and rejection after the selected target changes.

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

**Transport cooldown — confirmed gap, follow-up (JP-028–029, JP-033).**
`scripts/jira-rest.sh` maps HTTP 429 to a failure code without propagating
response headers; the controller uses a fixed 30-second selected-issue cooldown.
Design a bounded, validated retry-delay field across transport/bridge/controller,
shared appropriately across copies of a connection. Test 429/503, malformed or
missing headers, expiry and manual retry before shipping it. This gap is not
established as the cause of the reported blanks.

Release acceptance requires the automated suites, a passing native checker,
isolated integration/stress evidence and actual pointer/keyboard checks on the
chosen stock host. Live Jira, Linux GUI and full accessibility need their own
evidence; none follows from offline tests.
