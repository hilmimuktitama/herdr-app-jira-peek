# Native UI acceptance record

Historical observations from the original native development checkpoints.
Dates, host versions and coverage limits below remain applicable to those runs;
[current candidate validation](VERIFICATION.md#experimental-010-readiness)
is recorded separately.

## 0.13.0 public preview refresh

On 2026-11-01, the isolated fictional `capture.py --app` fixture passed its
native integration checks and refreshed `preview.png`, `app-light.png`,
`app-narrow.png` and `app-reader.png` with stock Herdr 0.1.10 on macOS. Primary
visually reviewed all four: the compact reader, persistent issue identity,
Help/Options, description and optional details/comments are readable at 420px
in Graphite/Paper and at 300px in Graphite. The two 300px files now show the
same default reader state. PNG metadata and trailing-data checks passed.

The left-hand context is a labeled, entirely fictional transcript rendered by
the capture fixture. These are current native frames, not a new human workflow
or keyboard/accessibility review. They do not show the optional renderer
extension; its separate evidence follows below.

## 0.13.0 selected-key working-area highlight

Reviewed on 2026-11-01 in an isolated macOS development build of Herdr app
0.1.10 with the pinned renderer extension. The fixture used its own app home,
core and idle terminal, entirely fictional `DEMO` issues, and no Jira transport.
Primary inspected actual native renderer captures produced by
[capture.py](screenshots/capture.py). This was a focused feature check,
not a repeat of the real document-workflow review below.

| Check | Result and evidence |
| --- | --- |
| Selected key | **Pass.** All four visible `DEMO-1042` occurrences have readable amber marks, including punctuation, a browse path and text after Chinese characters. |
| Exact boundaries | **Pass.** `DEMO-10420`, `XDEMO-1042` and `DEMO-1042_extra` remain unmarked. Wrap and clipped-boundary cases have native test coverage rather than visual evidence here. |
| Selection on an idle terminal | **Pass.** Selecting `DEMO-1038` through the real controller removes the old marks and marks the new key without waiting for output. The issue reader matches it. |
| Off and source integrity | **Pass.** Off removes every mark. Reading the source before and after selection/toggle actions returns identical text. Input, focus and scroll preservation also have regression coverage. |
| Themes and visibility | **Pass.** Graphite and Paper captures are readable. Hiding Peek removes marks; showing it restores them. |
| Native control | **Partial Computer Use evidence.** The named Highlight selected key in source terminal toggle exposed On/Off state. Pointer activation changed it to Off; a separate native renderer capture confirmed the Off label and absent marks. Computer Use screenshots did not refresh consistently with the accessibility state, so they do not establish a full pointer/keyboard visual pass. No product defect was isolated from this tool discrepancy. |
| Fixture privacy | **Pass.** All six fixture images prepared for publication were visually reviewed; PNG chunks contain no text, EXIF or timestamp metadata. The fixture closed only its own app/core. |

Captured states: [dark](screenshots/app-highlight-dark.png),
[changed key](screenshots/app-highlight-changed.png),
[off](screenshots/app-highlight-off.png),
[light](screenshots/app-highlight-light.png),
[hidden](screenshots/app-highlight-hidden.png), and
[restored](screenshots/app-highlight-restored.png).

Implementation and regression changes received independent source review. Live Jira, remote machines,
full screen-reader use, release builds and other platforms were not exercised.
The normal app was unchanged during that run. Stock Herdr requires the
[optional local build](../native/APP-HIGHLIGHT.md) to display terminal marks.

## 0.12.1 independent daily-workflow review

Reviewed on 2026-11-01 in Herdr 0.1.10. An independent reviewer used only
Computer Use for a private, read-only document workflow. It read two existing
issues, exercised lookup and recovery, changed its own terminal context, and
tested Help and Connection navigation. Issue records, screenshots, terminal
content, and the detailed session report remain outside this repository.
Primary verified the installed version by source/manifest hashes; the UI did
not display a version number.

| Observed friction in 0.12.0 | Change in 0.12.1 |
| --- | --- |
| A long description lost its identifying header; filtering could show another result above the old preview. | The displayed issue key and status remain outside the scrolling description. |
| Quick help started with shortcuts that required the reader to be focused already. | It now explains the configurable entry/return command and labels Ctrl+Shift+J as an example binding. |
| Auto-refresh was mistaken for terminal-key detection. | The control says Auto-refresh issue, and Options help distinguishes the two behaviors. |
| A failed lookup suggested checking only access. | The error suggests checking both the key and access. |

The baseline native pass verified keyboard search, title filtering, direct
lookup, arrow preview/selection, two-stage Escape to the original shell,
invalid-key recovery, pause/follow behavior, and source pinning across two
owned terminals. Help and Connection Back preserved the reading position,
selected issue, and search text. Full descriptions had no disclosure gate.

The focused 0.12.1 retest reported **four passes, one partial, and no new
confirmed defect**:

| Check | Native result |
| --- | --- |
| Persistent issue identity | **Pass.** A scrolled preview kept its key/status while filtering another issue. Selecting the result changed the label, showed its loading state, then showed matching content. The fixed row remained compact at the attached width. |
| Keyboard entry and return | **Pass in this installation.** Quick help identified the configurable command and example chord. Ctrl+Shift+J entered and returned in one chord each; shell return was confirmed through ordinary terminal work. This does not establish a default binding on other installations. |
| Refresh scope | **Pass.** The control and its Help distinguish issue refresh from terminal-key detection. The setting was not changed. |
| Invalid lookup recovery | **Pass.** The revised message covered the key and access, Retry was visible, and a valid issue was recovered in four keyboard actions. |
| Optional comments | **Partial.** An empty result opened while the description and identity remained visible. Loading completed before capture; slow-loading and comment-error behavior were not established by this live pass. |

The initial discovery delay was not isolated: manual scanning recovered the
first reference, and subsequent terminal output added references automatically.
Issue auto-refresh is separate from discovery, so its Off state does not
explain that observation. Page Down did not scroll despite a visible reader
focus border; this remains the documented native scrolling limitation.
The test did not establish an accessibility-tree equivalent to the visual UI.
External Jira navigation and credential forms were not exercised. Final state
was a valid issue, Paused, Pin off, empty search, comments closed, with the owned
document-work shell focused. Existing user tabs remained intact. No live Jira
writes, credential changes, or public screenshots were made.

## 0.11.0 contextual Help without reader clutter

Reviewed on 2026-11-01 in Herdr 0.1.10 with Computer Use, applying the
Emil design engineering skill's restraint and native interaction guidance.
The [reference record](MOD-REFERENCES.md) distinguishes Herdr's documented
tooltip contract from the placement decision made for Jira Peek.

| Before | After | Why |
| --- | --- | --- |
| Explanations depended on pointer tooltips and external documentation. | A keyboard-reachable Help button opens guidance for the current screen. | Keyboard users can find explanations while the ordinary reader stays concise. |
| Input and non-row Toggle tooltips used unsupported direct forwarding. | Supported layout wrappers own their tooltips; accessible names remain on controls. | Hints follow the installed Herdr API contract. |
| There was no contextual help return path. | Back and plain Escape restore the parent screen with Help focused. | Reading guidance preserves the issue position and unfinished setup values. |
| Token documentation required leaving the workflow to find it. | Setup and Connection help offer an explicit API token guide link. | Detailed account instructions have a specific destination. |

| Check | Result and evidence |
| --- | --- |
| Narrow panel | **Pass for tested screens.** Quick help, Connection help, and Setup help fit at 300×400 in the dark theme. Quick help was trimmed to three useful groups. Back destinations remained readable. |
| Keyboard | **Pass.** Native Shift+Tab and Enter reached and opened contextual Help. Plain Escape returned; Shift+Escape left Help open. Tab reached the API token guide without entering the covered form. |
| Reading and setup continuity | **Pass with inert fictional fixtures.** The same description position returned after Help. Entered site and email values survived Setup help → Escape. Connection help → Back returned to Connection. |
| Installed panel | **Pass at 360px.** Quick help and the final concise Options help rendered correctly. Back to Options restored its nine controls. The existing focus shortcut and native Tab navigation reached Help. |
| Restoration | **Pass.** Normal layout restored; original layout and keys match their baseline hashes. All 15 installed files match source and manifest for 0.11.0; Herdr reported zero errors. Four temporary layouts and the inert review mod were archived outside Herdr. |

Implementation and regression changes received independent source review.
Primary integrated fixes, trimmed copy after visual inspection, and completed
134 Node and 15 Python installer checks plus the native checker. No real
credentials were entered, no setup was submitted, and no screenshots were saved.
The disconnected fixture visibly exposed Help; its routing is covered by tests.
Computer Use later returned pointer-targeting errors, so remaining navigation
used the keyboard. Tooltip hover, Help scrolling, Paper/420px Help variants,
Linux GUI, and full screen-reader behavior were not verified in this pass.

## 0.10.1 remove the session-title row

Reviewed on 2026-11-01 in Herdr 0.1.10 with Computer Use. Moving the repeated
terminal title into Options had not addressed the user's objection to the title
itself. This correction supersedes the source-row placement described below.

| Before | After | Why |
| --- | --- | --- |
| Options repeated the terminal session title in a separate labeled row. | No session-title row in either Options or the reader; Pin source retains identity in its tooltip. | The visible panel stays focused on Jira and actionable controls. |

Native inspection confirmed the row is absent in the installed 360px Options
view and the normal empty reader. All nine Options controls remain visible.
The existing regression now verifies no visible title across ordinary, pinned,
manual, and missing-source states. No screenshots were saved.

## 0.10.0 scannable Options and predictable return

Reviewed on 2026-11-01 (Asia/Jakarta) in Herdr 0.1.10 on macOS with
Computer Use. The acceptance bar was to scan every option at a small size,
understand action versus state, and return to the same reading position.
The Apple design and Emil design engineering skills informed the review;
[reference evidence](MOD-REFERENCES.md) records Herdr's own menus and settings
alongside Apple's menu guidance. Keyboard actions remain immediate.

| Before | After | Why |
| --- | --- | --- |
| Mixed commands and toggles wrapped into outlined pills. | Aligned native rows in three groups, explicit On/Off values, and a Connection chevron. | Stable positions distinguish actions, state, and navigation. |
| A small nested scroll region hid lower options. | Options uses the attached panel's available body; all nine controls fit at 300×400. | The complete choice set is visible without hunting. |
| Connection → Back dismissed Options. | Back to Options restores that screen with Connection focused. | Back follows the path taken. |
| Setup and folder cancellation could lose the parent screen or focus. | Setup returns to its caller; folder cancellation stays in Connection. | A cancelled detour leaves an obvious next action. |
| Opening Options could reset the reader's scroll position. | The covered reader retains its layout and scroll state, without hidden tab stops. | Returning resumes the same glance. |

| Check | Result and evidence |
| --- | --- |
| Geometry and theme | **Pass.** All nine controls fit in dark 300×400 and 420×400 fixtures, and in the Paper theme at 300×400. Labels, separators, toggle state, and the focused row remained readable. |
| Installed return path | **Pass at 360px.** Options → Connection → Back to Options restored Connection focus in the normal attached panel. |
| Cancellation | **Pass with inert fixtures.** Setup Cancel/Escape returned to Connection; direct first-time setup returned to Connect Jira. Cancelling the native folder picker retained Connection and Choose existing folder focus. |
| Keyboard focus | **Pass for tested paths.** Options arrows moved between rows; Shift+Tab from its first action reached the header without entering the covered reader. Moving away from Set up Jira left only the actual focused row highlighted. |
| Reading continuity | **Pass.** After scrolling a fictional description, opening Options, visiting setup, cancelling, returning to Options, and pressing Escape restored the same visible reading position. The full loaded description remained immediately rendered. |
| Restoration | **Pass.** Normal attached layout restored; original layout and keys unchanged byte-for-byte. Four temporary layouts and the inert QA mod were archived outside Herdr. All 15 installed files matched source and manifest; Herdr reported zero errors. |

Implementation and regression changes received independent source review. Primary integrated their work and corrected issues exposed
by native testing and review. Final checks passed 126 Node and 56 Python tests;
The final independent review found no remaining concrete findings. No credentials were
entered or saved, and populated QA used fictional issues. Linux GUI, reader
PageUp/PageDown, and full screen-reader coverage remain unverified.

## 0.9.2 source details belong in Options

Reviewed on 2026-11-01 (Asia/Jakarta) with Computer Use in Herdr 0.1.10.
The user's clarification concerned the repeated terminal session title itself;
adding a Terminal label had not removed that distraction. This supersedes the
0.9.1 source-row placement while retaining the immediately available description.

| Before | After | Why |
| --- | --- | --- |
| Every glance repeated the terminal's session title above search or the issue. | The labeled source row appears only inside Options, beside its controls. | Routine session information no longer competes with issue context. |
| Pinning exposed the full source title in the main view. | Only Pinned source appears there, with its target in a tooltip. | A relevant exception remains visible without repeating the session title. |

Native checks confirmed the normal empty panel has no source title. At 300×400,
the fictional populated reader immediately showed key, status, title, description,
and acceptance criteria without Show more. Options revealed the labeled source;
pinning and Escape left only the brief indicator. Scrolling Options reached
Connection and Clear cache. The normal layout was then restored.

Implementation and regression changes received independent source review. Primary integrated, checked, installed, and verified
the native result. The existing accessibility and keyboard-scrolling limits remain.
Populated QA used fictional data; no repository screenshots were added.

## 0.9.1 immediate context and clear labels

Reviewed on 2026-11-01 (Asia/Jakarta) in Herdr 0.1.10 with Computer Use,
applying the Emil design engineering skill's clear defaults and restraint.
User feedback rejected the 0.9.0 tradeoff: removing labels made the source
ambiguous, and Show more delayed the context that Peek exists to provide.
The acceptance bar is now **identify the source, read the issue immediately,
return with one Escape**. Visible word count alone does not establish usability.

| Before | After | Why |
| --- | --- | --- |
| An unexplained dot preceded a terminal title. | Terminal: or Pinned terminal: identifies the source; manual lookup and missing-source states have explicit names. | The title's role is understandable without a tooltip. |
| Search or enter key left the scope and key type unclear. | Filter issues or enter a Jira key; empty guidance explains automatic discovery or manual scanning as configured. | Users can identify what the field does and how issues arrive. |
| The description stopped at 180 characters or two source lines behind Show more. | The entire loaded description renders immediately in the existing scroll region. | Context and acceptance criteria need no disclosure action. |
| Expanded descriptions added a Space shortcut and an extra Escape state. | No description disclosure state; one Escape returns from the ordinary reader. | Reading adds no extra keyboard step. |

| Check | Result and evidence |
| --- | --- |
| First glance | **Pass.** At 360px, the fictional key, status, full title, description, and all acceptance criteria appeared immediately without Show more. |
| Narrow and short reader | **Pass at 300×400.** Ordinary scrolling reached the final criterion and Details/Comments controls; Open in Jira remained fixed below. Longer issues require scrolling, not expansion. |
| Source and search meaning | **Pass.** Terminal: and the explicit Jira-key placeholder remained readable at 300px. The normal empty panel explained that keys in the terminal appear automatically. Pinned, manual, missing-source, and manual-scan variants have automated coverage. |
| Quick return | **Pass.** Ctrl+Shift+J focused the populated reader; one Escape returned to the originating terminal with the description still rendered. |
| Content and state | **Automated.** Complete multiline descriptions, including their final criterion, survive refresh and source changes. Optional Details/Comments retain their existing disclosure behavior; Space is no longer intercepted by the reader. |
| Restoration | **Pass.** Normal attached layout restored; keys and layout unchanged byte-for-byte. Temporary fixture archived; all 15 installed files verified; Herdr reported zero errors. |

Implementation and regression changes received independent source review. Primary integrated, passed 110 Node and 56 Python tests, installed 0.9.1,
and performed native checks. Populated QA used fictional issues; no new repository
screenshots were captured. Backend content limits and their visible warning remain;
the view adds no description truncation. Existing host keyboard-scrolling and
accessibility limits remain.

## 0.9.0 less text by default

Historical record: the source-label removal and description disclosure below
were rejected by user feedback and are superseded by 0.9.1 above.

Reviewed on 2026-11-01 (Asia/Jakarta) in Herdr 0.1.10 with Computer Use,
applying the Emil design engineering skill's restraint and progressive disclosure.
The default fictional reader fell from **72 to 36 visible words**. This counts
rendered labels and issue content in `demo.js`'s first issue, with Options and
disclosures closed and focus outside Peek. Whitespace-separated tokens containing
a letter or number count as words; punctuation, tooltips, and hidden content do
not. This is a controlled fixture comparison, not a promise for every issue.

| Before | After | Why |
| --- | --- | --- |
| Metadata and fetch date preceded the description. | Details reveals both; its tooltip also provides the exact fetch time. | The first glance prioritizes the issue itself. |
| The excerpt allowed 320 characters or seven source lines. | Up to 180 characters or two source lines, with Show more and Space retaining full access. | A brief excerpt keeps the panel a Peek. Wrapped visual lines depend on width. |
| Source, DESCRIPTION, and OPTIONS repeated obvious context. | Remove these redundant headings; retain source identity, tooltips, and accessible names. | Fewer labels compete with issue content. |
| Empty states listed projects and repeated instructions; failures repeated headings. | Short next steps and one failure message with Retry. | Guidance remains actionable without a paragraph. |

| Check | Result and evidence |
| --- | --- |
| Optional detail | **Pass.** Native Tab/Enter opened Details with complete fixture metadata and fetch timestamp; Tab/Space opened Comments. Escape collapsed both. Reader Space revealed the complete description. |
| Narrow panel | **Pass at 300×400.** Default key, full fixture title, status, excerpt, Show more, Details/Comments, footer, and focus hint fit without scrolling. Expanded content retains the scroll region. |
| Empty search | **Pass.** An unmatched fictional filter showed one concise notice while retaining the selected issue. The normal empty source showed lookup and one short next step. |
| State boundaries | **Automated.** Four new view regressions cover disclosure visibility, Follow pause, refresh preservation, source/issue reset, shorter excerpts, and Escape before return. |
| Restoration | **Pass.** Normal attached layout restored; layout and keys unchanged byte-for-byte. Temporary fixture archived; all 15 installed files verified; Herdr reported zero errors. |

Implementation and regression changes received independent source review.
Primary integrated, passed 106 Node and 56 Python tests, and verified native behavior.
The existing keyboard-scrolling and host accessibility limits remain. No new
repository screenshots were captured.

## 0.8.0 continuous search preview

Reviewed on 2026-10-31 in official Herdr 0.1.10 on macOS with Computer Use.
The acceptance bar was **type → arrows → preview → Enter → Escape**, keeping
focus in search until the user chooses a result. The [Mods research](MOD-REFERENCES.md)
records the community references and the shipped picker precedent.

| Before | After | Why |
| --- | --- | --- |
| Plain Down in search left the first issue selected. | Up/Down previews results without leaving the input. | Continuing to refine a query needs no focus detour. |
| Input Enter always chose the first text match. | Enter commits the highlighted visible result. | Preview and action agree. |
| Filtering could leave no highlighted row and list Down skipped the first. | First movement selects the first visible match. | Navigation has a predictable starting point. |
| Direct search could depend on a preceding render to capture its origin. | Search records the terminal before changing focus. | Return is tied to the actual entry context. |

| Check | Result and evidence |
| --- | --- |
| Search and preview | **Pass.** With fictional data, `add` produced two matches. First Down selected the first; second Down selected the second. Search kept its outline and query while the reader changed. |
| Continue typing | **Pass.** After navigating, appending ` keyboard` refined the same input. The next arrow selected the remaining match. |
| Commit and return | **Pass.** Enter committed the highlighted second match, hid browsing and focused the compact reader. One Escape returned to the originating terminal and removed the hints. |
| Direct command and modifiers | **Pass for tested native path.** `jira-peek.search` focused the existing lookup; Shift+Down did not change the selected issue. Automated cases cover other modifiers and changed/deleted/replaced return targets. |
| Narrow geometry | **Pass at 300×400.** Search, selected row, key/title preview, footer and one-line hint remained visible. Longer details retained the existing scroll region. |
| Restoration | **Pass.** The normal attached layout and existing connection were restored. Keys and normal layout are byte-for-byte unchanged; the temporary fictional layout was archived. Herdr status reported no errors. |

Implementation and regression changes received independent source review. Primary integrated,
performed native verification, and retained the exact fetch timestamp after
the existing idle-truthfulness regression rejected a relative-age proposal.
No new timer or persistent control was added. This iteration does not extend
the earlier Linux GUI, reader scrolling, or screen-reader coverage.

## 0.7.1 Herdr keyboard guidance audit

Reviewed on 2026-10-31 in official Herdr 0.1.10 on macOS. The acceptance bar
was configurable host shortcuts, continuous visible focus, ordinary text
editing, and the same quick entry/return loop. The installed app guide and
generated API definitions supplied the integration contract; the shortcut
choices themselves belong to Jira Peek.

| Before | After | Why |
| --- | --- | --- |
| Raw F2/F5 handlers could run independently of optional bindings. | Follow/Refresh arrive only through native keys.json commands. | Remapping and removing bindings have one source of truth. |
| Setup/settings returned before the panel's Tab handler. | Both use host forward/reverse traversal. | Native buttons no longer end the keyboard path. |
| Opening settings could strand focus on the removed entry button. | Settings focuses Set up Jira; loading setup focuses Cancel until Site URL is ready. | Every transition has a visible keyboard starting point. |
| Setup treated modified Escape as cancellation. | Only plain Escape cancels idle setup. | Host chords retain their meaning and busy-save protection remains. |

| Check | Result and evidence |
| --- | --- |
| Native binding ownership | **Pass.** Default F2 resumed Follow after reader Down. Temporarily remapping F2 to Search and F5 to Peek-return produced those actions. The original key file was restored byte-for-byte. |
| Settings entry and traversal | **Pass.** Tab after opening settings reached Choose existing folder with visible focus. Shift+Tab returned to Set up Jira; Enter opened setup. |
| Form traversal | **Pass for tested path.** Tab traversed Site URL, Email, token, the token-help button, and Project keys. Shift+Tab returned to the button. No field values were changed. |
| Escape and return | **Pass.** Shift+Escape left setup open. Plain Escape returned to settings with Set up Jira focused; Escape closed settings; Ctrl+Shift+J returned to the terminal. Busy cancellation remains covered by automated tests. |
| Installation and restoration | **Pass.** Native validation and runtime status were clean. Normal layout and keys were unchanged; the temporary fictional layout was archived. |

Independent review checked the routing and focus corrections and passed the
35 affected view/setup-controller tests. Primary performed the native checks.
The existing reader scrolling and accessibility limits below remain; this
audit does not establish full accessibility support.

## 0.7.0 keyboard Peek

Reviewed on 2026-10-31 in official Herdr 0.1.10 on macOS with Computer Use.
The acceptance bar was **one chord in, a useful glance, one Escape back**.
Search and optional depth should not add steps to the ordinary glance. No
keyboard action animates, and the panel remains attached to the main window.

| Before | After | Why |
| --- | --- | --- |
| The example shortcut toggled visibility without focusing the reader. | Ctrl+Shift+J focuses the visible reader and repeats to return to the originating terminal. | A glance has a direct keyboard entry and exit. |
| Adjacent issues required opening the list. | Reader Up/Down changes issue while retaining the compact view. | Comparing nearby context takes one key. |
| Search required navigating to its field. | Slash or Cmd+F reveals and focuses search; Enter returns to the reader. | Looking up a key stays short and predictable. |
| A retained hidden filter consumed the first Escape. | Compact-reader Escape returns immediately and preserves the filter for next time. | Invisible state does not add a keystroke. |
| Native Tab did not advance from the reader. | Tab/Shift+Tab invoke host traversal through explicit enabled tab stops. | Secondary controls remain reachable without more custom shortcuts. |
| Return could retain the reader's focus styling for a frame. | A deferred repaint clears the outline and hints after the host focus command. | Feedback agrees with where typing will go. |

| Check | Result and evidence |
| --- | --- |
| Enter and return | **Pass.** Ctrl+Shift+J focused the fictional reader. Repeating it returned to the original terminal; the terminal cursor resumed and reader hints disappeared. Empty-source entry focused lookup, and Escape returned. |
| Compact navigation | **Pass.** Down selected the next fictional issue without showing search or the list. Automated tests also cover Up, Follow pause, and modified chords. |
| Find and commit | **Pass.** Slash focused search; a text filter and Enter selected a result in the compact reader. One Escape returned to the terminal after the hidden-filter fix. |
| Secondary controls | **Pass for tested path.** Tab reached Show comments with a visible outline; Space opened comments. Shift+Tab, Escape, and Ctrl+Shift+J collapsed depth and returned to the terminal. |
| Origin integrity | **Automated and independent review.** Pinned sources do not change the return target. Regressions cover removed terminals, changed tabs/panes, shown replacements, layout terminals, and retained host terminal identity during mod focus. |
| Reader action isolation | **Automated evidence.** Enter opens the configured fictional Jira URL; Y copies only the key; Space toggles a long description. Typing, button focus, setup, and modified chords do not trigger reader actions. |
| Restoration | **Pass.** The normal attached layout was restored, its file hash is unchanged, and the temporary demo layout was archived. Existing keybindings were preserved. |

Implementation and regression changes received independent source review. Primary integrated,
corrected native discrepancies, and verified the final app behavior. The
shortcut needs a visible attached panel because of Herdr's command-delivery
contract. This record does not establish full keyboard scrolling or screen-
reader support. See [verification](VERIFICATION.md) for coverage boundaries.

## 0.6.0 compact Peek

Reviewed on 2026-10-31 in official Herdr 0.1.10 on macOS with Computer Use.
The acceptance bar was a useful current-issue glance, fewer persistent
controls, optional depth, and no interruption while deliberately reading.
The panel stayed attached to the main window. Demo geometry used fictional
records; live observation is described without copying records or images.

| Before | After | Why |
| --- | --- | --- |
| Search, list, mode controls, and passive notices stayed visible. | The current issue opens first; Issues reveals browsing and search. Empty sources still show direct lookup. | The initial view prioritizes issue context. |
| A large heading, raw dates, and expanded content competed for space. | A smaller full title, status beside the key, readable dates, and a short description preview establish hierarchy. | More context fits in the narrow panel without hiding the issue title. |
| Description and comments always occupied the reader. | Show more and Show comments reveal detail; opening either pauses Follow. | Readers choose depth and keep their place. |
| Copy, Refresh, and Pin occupied persistent rows. | Open in Jira remains the primary footer action; secondary actions live in Options. | The glance has fewer competing actions. |
| Options rows shrank and clipped in short panels. | Options has a bounded scroll area with nonshrinking rows. | Connection settings and cache actions remain reachable. |

| Check | Result and evidence |
| --- | --- |
| Default and live connection | **Pass.** The updated normal panel loaded the existing connection and showed key, full title, status, metadata, description preview, and collapsed comments. No token re-entry was needed. |
| Browsing and keyboard | **Pass.** Issues revealed search/list and paused Follow. Down selected another issue while retaining the list; Enter returned to the compact reader. A fictional direct-key lookup also returned to the compact reader. |
| Optional content | **Pass.** Description expansion and comment disclosure worked with visible focus. Short descriptions stayed complete. Automated tests verify same-issue refresh retains disclosure state and another issue resets it. |
| Small and light layouts | **Pass for inspected sizes.** Dark 300px and light 420px panels displayed the compact hierarchy. At 300×400px, the key, title, status, metadata, and description opening remained visible with Open in Jira fixed below. |
| Options recovery | **Pass.** After the scrolling fix, a wheel scroll exposed Connection settings and Clear cache in the 300×400px panel. Escape closed Options and restored reader space. |
| Empty source and source switch | **Pass.** A terminal without discovered keys showed the input and brief next-step guidance without disabled browsing controls. Returning to the work terminal restored its issue. |
| Search during discovery | **Automated evidence.** A focused empty-source search remains visible when the first key appears; typing keeps browsing active. Independent review rechecked the fix. |
| Filtered-list selection | **Automated evidence.** Enter chooses a visible result when the former selected issue is excluded by the filter. Independent review rechecked the fix. |
| Restoration | **Pass.** The original normal layout was restored with an unchanged file hash. Temporary demo layouts were archived outside the app's layouts directory. |

Implementation and regression changes received independent source review. Primary integrated and corrected the findings, added view
regressions, and performed native checks. The existing host accessibility
limits below remain; this iteration does not establish full screen-reader
support. No new documentation screenshots were captured. See
[verification](VERIFICATION.md) for test counts and coverage boundaries.

## 0.5.1 terminal workflow correction

Reviewed on 2026-10-31 in the normal Herdr 0.1.10 window on macOS. A bounded
read-only Jira activity ran in a terminal rooted in a work repository while
Peek remained attached on the right. Live records and screenshots are excluded
from this repository. Fictional regressions reproduce the defects separately.

| Check | Result and evidence |
| --- | --- |
| Relevant controls | **Pass.** The document importer is absent. Options retains screen/history reads, Auto-refresh, connection settings, and cache clearing. |
| Live discovery | **Pass.** Real agent output populated issue rows with Jira summaries and statuses; selecting a Task displayed its description. |
| Revisiting an issue | **Pass.** Before the fix, Follow remained on an earlier topic when the agent returned to a known key. After the fix, a further live read selected that already-known Task automatically. |
| Deliberate reading | **Pass.** Selecting another issue paused Follow. An explicit screen scan preserved that selection. Follow latest returned to the Task visible in the terminal. |
| Attached update and connection | **Pass.** The update reloaded in the existing right panel and used the saved connection without token re-entry. No separate Peek window was opened. |
| Concurrent reads and failure recovery | **Automated evidence.** Deferred-response tests cover scan coalescing, history serialization, source changes, and manual retry of failed row metadata. These failures were not induced against the live account. |

The 200-key boundary was checked with fictional regressions and independent
review. Native accessibility and reader keyboard-scrolling limits recorded
below remain; this iteration does not establish full accessibility support.

## 0.4.0 connection setup

Reviewed on 2026-10-31 with official Herdr 0.1.10 on macOS. Primary used
Computer Use against the same isolated **Jira Peek UX** fixture described
below. Every account, token, issue, and response was fictional; the curl
substitute has no network implementation. The setup form occupies the
existing right-hand panel inside Herdr's main window.

Implementation and regression changes received independent source review. Primary owned installation changes, integration tests,
and native verification. The acceptance bar was a clear first connection,
preserved working configuration on failure, no saved-token readback, and
usable setup at narrow and short panel sizes.

| Before | After | Why |
| --- | --- | --- |
| First connection required preparing a configuration folder elsewhere. | Set up Jira collects site, email, token, and project keys inline; existing-folder setup remains available. | Users can connect without leaving the attached panel to edit a file. |
| Connection settings immediately opened a folder picker. | A dedicated view offers Set up Jira, Choose existing folder, and Reconnect. | Token setup and existing backend configuration have explicit entry points. |
| There was no native credential-entry flow. | A masked token field is never prefilled and is replaced after submission or cancellation. | Saved tokens stay out of the form; Undo cannot restore a submitted token. |
| A new token had no guided verification or recovery. | Test & save checks the account before switching config; safe errors preserve other fields and require a fresh token. | Failed verification leaves the working connection intact. |
| A longer scoped-token form could crowd a small panel. | Fields scroll independently while Cancel, Test & save, and status remain visible. | Cloud ID stays reachable at 300×400px, and users can see progress without scrolling. |
| Cancellation could be ambiguous once a credential change began. | The busy form disables edits and actions; Escape cannot dismiss an active save. | The UI does not imply that a committed change was cancelled. |

| Check | Result and evidence |
| --- | --- |
| Attached layout | **Pass.** Setup replaced the reader within the right panel. The production manifest remains `place: "right"`; no plugin-created standalone window was introduced. |
| Successful save and rotation | **Pass.** Unscoped and scoped fictional account checks saved through the real native file API. The panel reconnected; reopening setup restored nonsecret fields with an empty token. Private-file inspection confirmed one active credential after rotation and no pending submission. |
| Failure recovery | **Pass.** A fictional authentication failure produced safe inline guidance, preserved nonsecret fields, and left the previously working config unchanged. A fresh token could be submitted successfully. |
| Token visibility and disposal | **Pass for observed surfaces.** Typed input rendered as bullets; the AX snapshot contained no token value. Submission cleared the field, and Undo did not restore it. Source/tests cover cancellation and fresh InputState allocation; this is not a memory-erasure guarantee. |
| Busy state and keyboard | **Pass for tested actions.** Tab traversed fields. During a six-second check, Cancel and Test & save were disabled and Escape did not dismiss the transaction. Before saving, Escape returned to Connection settings. |
| Narrow, short, and light layouts | **Pass for tested sizes.** A populated scoped form survived 300→420→300 resizing. At 300×400px, scrolling reached Cloud ID while the action row stayed visible. Light mode at 420px displayed all fields and controls without clipping. |

Input names remain absent from the host's macOS AX tree despite supplied
labels. This review establishes the interactions above, not full screen-reader
support. No real Jira permissions, Linux GUI behavior, or normal app
installation were exercised. See [verification](VERIFICATION.md) for the
automated checks and local-file security boundary.

## 0.3.0 reader and navigation

App edition 0.3.0, reviewed on 2026-10-31 with official Herdr 0.1.10 on macOS.
Primary used Computer Use against a temporary copy named **Jira Peek UX**
(`dev.herdr.jirapeek.ux`), with the isolated fictional app/core/backend in
[capture.py](screenshots/capture.py). The normal app received no input.
Implementation and regression changes received independent source review.
Primary integrated their work and performed the runtime checks.

The acceptance bar was usable reading at 300px, explicit state and recovery,
native keyboard actions, and preservation of deliberate reading. Host limits
below prevent a claim of complete keyboard or accessibility support.

| Before | After | Why |
| --- | --- | --- |
| Pointer-oriented controls were absent from the accessibility tree. | Named native Buttons and Toggles expose actions and on/off states; visible focus outlines reserve space. | Keyboard and assistive users can identify and operate the main actions. |
| Issue rows lacked accessible identity and dedicated keyboard navigation. | Named options include key, summary, status, and an explicit selected label; Home/End and arrows reveal selection. | Long lists remain navigable without hunting for an offscreen selection. |
| Permanent secondary controls and a fixed list crowded short readers. | Options contains secondary controls; short panels default to reader focus; full action labels fit at 300px. | More space goes to the task while actions remain discoverable. |
| Long source titles and retained horizontal layout positions could clip controls on shrink. | Compact groups keep Options, Pin, status, Refresh, and Follow controls beside their context. Retry and Dismiss precede wrapping messages. Bounded text has a full-title tooltip; reader/list identities stay stable. | Actions remain visible after resize without resetting reading state. |
| Copy confirmation shared a mutable operation message. | Separate confirmation expires after 2.2 seconds with a revision guard. | An older timer cannot erase newer feedback or an operation failure. |
| Invalid direct lookups could silently fall through. | Inline validation explains allowed projects and origin, preserves the selected issue, and clears on recovery. | Rejected input has a clear next step and never triggers a foreign request. |
| Cached refreshes had unclear waiting and failure states. | Queued/loading feedback and Retry sit outside the scrollable body; stale content remains available. | Readers can distinguish waiting, failure, and recovery. |
| Passive Browse updates could recenter the list. | Only an actual selection change recenters it; new-key controls explicitly resume Follow. | Background discovery preserves deliberate reading. |

## Runtime outcomes

| Check | Result and evidence |
| --- | --- |
| Main action access | **Pass for tested actions.** Computer Use observed named Button/Toggle roles and on/off values. Tab, Shift-Tab, Enter, and Space reached and activated controls, with visible focus. Escape closed Options and returned focus to its visible control. |
| List access | **Pass.** Native AX options expose key/summary/status and a selected label. Clicking a row then End selected and revealed the last issue; Home then Down selected and revealed the next issue at the top. The long fixture contained 30 keys plus a newly discovered key. |
| Narrow and short geometry | **Pass for tested sizes.** 300px and 420px full-height panels, light/dark themes, and 300×400px were inspected. Long source titles, validation, status, and full copy labels fit. With Options closed, the 300×400px panel had about 130px of reader viewport. Options remained reachable; Escape restored that viewport. A continuous 300→420→300 resize retained the filter, selected issue, and same scrolled passage; title/source/status/Refresh controls stayed visible. |
| Validation recovery | **Pass.** A foreign fictional URL produced wrapped inline guidance while the previous issue stayed open. Clicking “+1 new” cleared both rejected input and guidance and selected the newest issue. Controller tests also cover rejected projects, no backend request, editing, valid submission, and source/connection resets. |
| Passive discovery | **Pass.** In Browse, a new terminal key updated the unseen badge while preserving the selected issue and the same scrolled description passage. Controller/model tests cover query retention, list viewport, source switching, and pinning. |
| Refresh and clipboard feedback | **Pass.** A six-second refresh visibly retained cached content and showed progress. Failure retained content with Retry. Copy confirmation appeared separately and expired without removing the failure. Retry with the successful fixture cleared the failure and updated fetch time. Tests cover superseded requests and copy-timer races. |
| Empty and setup recovery | **Pass.** With no terminal, an allowed key opened an issue. The native folder picker selected only the fixture configuration; a subsequent manual key loaded successfully. Missing configuration displayed an actionable setup button. |
| Fixture provenance | **Pass.** All issues, identities, source output, and URLs were invented. The backend has no network implementation. Final documentation images were regenerated through the fixture script, visually inspected, and checked for metadata. |

## Remaining host limits and coverage

- The native Input accepts an accessibility label in code, but Herdr 0.1.10
  did not expose that name in the macOS accessibility tree. Buttons and rows
  did expose their supplied names. This is not a screen-reader certification.
- Page Down did not scroll the focused plain reader. An isolated native
  TextView probe also failed this interaction, so the product retains its
  safe plain-text reader. Use a wheel or trackpad. No unsupported host API
  or synthetic terminal input was added as a workaround.
- AX reports the selected row through its explicit label; the host did not
  reliably expose the supplied native selected flag. Focus was assessed with
  actual keyboard actions and visible outlines, not the window-level AX
  focused-element report alone.
- A full screen-reader session, Linux GUI behavior, and live Jira/remote-machine
  access were not verified here. Resize was checked only at the stated sizes.
  Source and request-isolation behavior is covered separately by tests.

See [verification](VERIFICATION.md) for automated coverage and
[screenshot instructions](screenshots/README.md) to reproduce the lab.
