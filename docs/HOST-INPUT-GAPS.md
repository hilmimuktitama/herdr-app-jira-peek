# Native input gaps in stock Herdr

**2026-11-02 · stock herdr-app 0.1.11 · Jira Peek 0.1.0.**

**2026-11-03 update:** the same shortcut race reproduced with the everyday
stock **0.1.12** binary and complete key map: 14/40 openings leaked the query
and Return, and one more lost its first character. The corrected configuration
passed 40/40 with zero terminal bytes. See the
[current retest](VERIFICATION.md#reader-controls-and-0112-retest). The build
recipe now targets patched 0.1.12; the original source analysis below is dated
to 0.1.11.

These defects remain in stock herdr-app 0.1.11. The optional
[native input patch](../native/APP-INPUT.md) now implements the three host
changes below. It must be built separately; updating the mod alone does not
fix stock input dispatch or scroll panes. See the
[follow-up verification](VERIFICATION.md#native-input-follow-up).

The private field review and its work captures remain outside this repository.
The public examples use entirely fictional catalog fixtures. The source
analysis below describes the unpatched v0.1.11 host.

## Terminal-to-filter input ownership

The optional shortcut reaches `nextCommand()` through an asynchronous
channel. The toolbar then posts a shared request, shows the panel, and Peek
consumes the request on a visible render. None of those steps atomically
takes the next input event away from the terminal.

Source: [command dispatch](https://github.com/herdrdev/herdr-app/blob/e12fd31866f33cb613922d0b33ea506e6f23ce3c/src/window.rs#L2577)
and [shown-copy channel delivery](https://github.com/herdrdev/herdr-app/blob/e12fd31866f33cb613922d0b33ea506e6f23ce3c/src/mods.rs#L624).
The input leak was observed in the supplied field review; the causal account
above is supported by source inspection, not a new event trace.

Required host behavior: a native show-and-focus operation must claim input
while handling the shortcut, before any later key or paste can reach the
terminal. It must retain ordered input until the actual filter is ready, or
focus a retained native input synchronously. Define handling for Escape,
Return, paste, IME composition, unavailable panels, and context changes;
never replay buffered text into a different terminal or issue source.

Acceptance: in the isolated fixture, use a harmless receiver instead of a
shell/agent. Test 20 visible and 20 hidden openings, including individual
keys, paste plus Return, cold opening and repeat-to-return. Every character
must reach the intended filter and the terminal must receive zero bytes until
explicit return. A fixed sleep or passing only settled-focus trials is not a fix.

Current mitigation: documentation and Help disclose the race; reach the
filter through Issues or Tab before typing. Existing personal bindings are
preserved. This mitigation does not satisfy the acceptance criterion.

## Keyboard scrolling and visible focus

The ordinary scroll wrapper owns a native `ScrollHandle` internally but
exposes no ordinary scroll handle to mods. It wires wheel scrolling and
scrollbars, with no page/home/end keyboard behavior. The script API exposes
programmable scrolling only for virtual lists. See the pinned
[scroll wrapper](https://github.com/herdrdev/herdr-app/blob/e12fd31866f33cb613922d0b33ea506e6f23ce3c/vendor/gpui-kit/crates/shell/src/scroll.rs#L90).

Required host behavior: Page Up/Down, Space/Shift+Space and Home/End should
scroll the focused ordinary pane. Moving focus to a descendant must reveal
that control in its nearest scroll ancestor. Preserve native text editing and
button activation; do not make Space scroll when it should activate a button.

Acceptance: with a three-screen fictional issue, Page Down advances roughly
one viewport, Page Up reverses it, and End exposes the final paragraph.
Every Tab target in the reader and short-height Help stays visible, without
changing issue, Follow state, query or terminal focus. Wheel input remains
usable. Repeat after resizing and after opening/closing an explanation.

Current mitigation: the focused reader hint now names Enter → Open in Jira.
This is a browser fallback, not full keyboard reading inside Peek.

## Reading position after hide/show

The mod instance remains alive while hidden, but the native scroll position
does not survive removal of its rendered scroll area. The ordinary wrapper
stores its handle in window keyed state; the mod has no supported getter or
setter for that position. Options/Help retain the mounted reader, which is
why those transitions can preserve its place. Hiding the whole layout block
removes it from rendering.

Required host behavior: retain ordinary scroll state with the surviving mod
copy, or expose a retained scroll handle that can restore the same content
anchor when that copy reappears. Keep the state scoped to source and issue;
do not restore another issue at the old offset.

Acceptance: at the middle and bottom of the same fictional issue, hide and
reopen three times. Return within one text line, with key, query and Paused
state unchanged. Verify independent positions for different sources/issues
and sensible clamping after content shrinks. No durable content cache is needed.

## Verification boundary

The field-review fixes for filtered actions, Clear, unread navigation, direct
lookup and freshness are covered separately in [verification](VERIFICATION.md#field-review-follow-up).
This session could not start the native Computer Use pipe on two attempts, so
it adds no fresh pointer/keyboard pass for the three host gaps. Short-window
Help focus visibility remains unverified. Do not mark any of these gaps closed
from JavaScript tests, source inspection or static captures alone.
