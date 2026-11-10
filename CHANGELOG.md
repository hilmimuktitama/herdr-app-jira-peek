# Changelog

## Unreleased

## 0.7.0 experimental — 2026-11-10

- Fix a one-frame black flicker in the issue list. Virtual-list range work is
  now recorded during layout and processed by the panel's native timer, so
  retained row actions are not woken inside a paint frame.
- Make reader prose selectable: the title, Body field values, open Details
  values and comment bodies now support native pointer selection with
  Cmd+C/Ctrl+C copy and Cmd+A/Ctrl+A for one text block. Labels, header values,
  issue rows, Help/Options/forms and collapsed or Hidden content stay plain.
  Selection copy is silent and separate from Y, Shift+Y and Copy issue as
  Markdown. Issue text is HTML-escaped into a non-scrolling text view, so it
  cannot become Markdown, active links, images or markup. Reader shortcuts,
  Escape/back, Follow pausing and the reader focus ring are intended to remain
  active while text is selected; native interaction checks remain.

## 0.6.0 experimental — 2026-11-10

- Add **Copy issue as Markdown** to Options and the `copy-issue` command. It
  copies the viewed issue's already-loaded key, summary, URL, fetch time,
  Header fields, Body sections, Details and loaded comments as one bounded
  document. Hidden fields and empty non-comment values are excluded; comments
  are never fetched for a copy, and their loaded/loading/deferred/error states
  are named. The copied text is Peek's unescaped plain-text projection of
  untrusted Jira content. The whole payload is capped at 262,144 characters
  (Unicode code points), including one truncation marker. Clipboard feedback uses the
  accessible footer status strip, not a new reader icon or default key.

## 0.5.4 experimental — 2026-11-09

- Retain row-action views only for the native viewport instead of preallocating
  200 per panel. Release outgoing actions before replacements and avoid
  recreating dormant rows during passive refreshes, reducing pressure on the
  host's shared retained-object limit.
- Wake pending viewport actions through a panel-owned native timer, so cached
  list scrolling can populate copy/pin controls with scanning and auto-refresh
  disabled. Idle ticks do not redraw; closing cancels the timer.

## 0.5.3 experimental — 2026-11-08

- Prevent late issue failures from deleting newer cache entries or overwriting
  their diagnostics. Revalidate cached issue identity and field selection before
  projecting a response to a native panel.
- Retire denied issues consistently for REST and explicit TWG permission errors,
  including failed single-item envelopes with a zero process exit status.
- Verify scoped-token site URLs against their Cloud ID before activation and
  once per runtime connection epoch. Preserve the previous setup on mismatch.
- Reject unresolved shared state roots in the standalone cache-clear helper;
  the native Clear cache action remains scoped to its connection.

## 0.5.2 experimental — 2026-11-08

- Reject pending comments immediately when Refresh starts, including when the
  issue refresh fails. Preserve independent comment retries and connection
  revocation handling.
- Give metadata batches and issue details the same privacy filtering and
  4,096-character picker limits. Preserve the reader's 20,000-character metadata
  limit and reject oversized batches before returning them to the panel. Keep
  shared projection helpers compatible with jq 1.8.2.
- Recover abandoned empty cache locks and prevent older cache misses from
  overwriting later attempts, including when the newer attempt fails.
- Recover interrupted bundle replacement from its recorded, validated backup on
  the next mutating installer/updater invocation. Preserve edited backups and
  keep availability checks read-only.
- Validate custom field IDs consistently as `customfield_` followed by 1–12
  digits. Preserve upgrade compatibility with historical installation manifests.
- Remove unused terminal-viewer helpers and centralize issue failure, refresh
  and field-invalidation transitions in the model.

## 0.5.1 experimental — 2026-11-08

- Shorten control tooltips to actions, shortcuts and essential consequences;
  keep detailed instructions in Help and full values in data tooltips.
- Keep Follow icon-only and show the next action: pause while Following, play
  while Paused. Remove pressed styling and name the action in its tooltip.
- Remove the separate issue lookup prompt from filtering. Show No matches for
  empty results, including valid issue keys; keep direct lookup through Enter.

## 0.5.0 experimental — 2026-11-08

- Keep matching pinned issues visible once above the scrolling results. Save
  filtered-out pins for Return, and restore browsing order when unpinned.
- Reveal Copy key, Copy link and Pin only on the hovered result, with immediate
  first-click actions that preserve the preview, query and unread state. Keep
  pinned indicators and keyboard-focused controls visible; remove the selection
  checkmark. Clicking a title selects it; clicking the selected key opens Jira.
- Append new matching issues while Paused without changing existing result
  order, selection, filter, scroll or list height. Resume Follow for latest-first
  order. Explicit unread/pin/direct reading can act outside the saved filter;
  reopening Issues restores filter eligibility and rejects stale actions.
- Fix stale selected-row text on arrow/pointer navigation and recover released
  native rows after hide/reopen, Clear list and repeated pin transitions.
- Align row metadata and spacing, preserve full-width titles and 32px copy/pin
  targets, and scale rows/filter with host typography. End visible pages on whole
  rows and keep the complete title in the scrolling reader. Show the full fetched
  date and UTC time beside Refresh, wrapping at narrow widths.
- Show play while Following and pause while Paused, with explicit accessible
  state/action names. Bundle both icons in self-contained installations.
- Add the product dictionary, refresh fictional screenshots and native font/
  boundary fixtures, retain QA verification outside the gallery, and exercise the
  actual v0.4.0 installed updater against the new candidate.

## 0.4.0 experimental — 2026-11-07

- Add offline integration diagnostics for the active layout or an explicit
  source, separating bundle validation, prepared files and active configuration
  from unverified button rendering.
- Repair compatible personal tabs clones from their own source, preserving
  custom controls, imports, supporting files and the existing Peek panel ID.
  Insert the toggle immediately after Changes and keep activation explicit.
  Preserve conflicting files and reject unsupported structures with targeted
  manual guidance; retain source-drift checks and optional update integration.
- Bound toolbar-metadata and status nesting consistently across Python versions.

## 0.3.4 experimental — 2026-11-07

- Refine the native reader with aligned gutters, clearer title and metadata
  hierarchy, quieter toolbars and Help, and distinct selected issue rows.
- Keep a compact fetch time beside the issue key in short panels, with the
  full timestamp available in its accessible label, tooltip and Details.
  Scale issue rows and panel chrome with Herdr's UI font size.
- Preserve compact layouts and scrolling at higher host zoom levels.
- Replace “Fixed terminal” with “Keeping this terminal” and clarify how terminal
  reading differs from automatic issue selection and issue pinning.

## 0.3.3 experimental — 2026-11-07

- Clarify that toolbar preparation creates a personal layout which must be
  selected explicitly. Keep same-version release updates unchanged and give
  original-source repair guidance without overwriting personal layouts.
- Let independently validated code updates finish when optional toolbar
  validation fails; preserve explicit attachment checks and partial-state
  recovery. Reject generated layouts as repair sources and identify conflicts.

## 0.3.2 experimental — 2026-11-07

- Prepare the personal Jira Peek toolbar and layout during ordinary updates,
  including updates launched by older helpers. Print the layout selection
  command; preserve conflicting personal edits and custom layouts. Select
  `main-jira-peek` once to use the button.
- Publish complete integration files without overwriting personal edits; detect
  source drift and report incomplete toolbar setup separately from an installed
  bundle. Add offline `--repair-integration` and read back interrupted updates.
- Retire TTL-zero full bodies on automatic and explicit selection changes while
  preserving searchable rows, pins and unread state.
- Keep Fields drafts and visible focus when a connection is invalidated.
- Preserve the shared auto-refresh opt-in when a panel becomes idle. Resume only
  that panel; late preference writes and reloads cannot renew an expired lease.

## 0.3.1 experimental — 2026-11-06

- Isolate native caches and connection epochs by configuration folder so
  separate Jira connections cannot invalidate each other or reuse overlapping
  issue keys. Use filesystem directory identity so case aliases share cache
  invalidation without merging distinct case-sensitive folders. Preserve the
  former shared cache without reusing it.
- Keep the default key example compatible with stock Herdr: only optional
  mod-scoped F2/F5 bindings. Move custom-host entry instructions out of the
  primary workflow and state the remaining keyboard-entry limitation. Match
  stock Help and its guide image to the available controls.
- Reject duplicate layout IDs before attaching Peek. Preserve existing
  toolbar targets, personal edits, credentials, settings and unrelated keys
  when installing, updating or refusing a conflicting integration.

## 0.3.0 experimental — 2026-11-06

- Replace Issues/Back navigation with one disclosure. Preview a matching issue
  while filtering, collapse results with Enter, and retain the query and list
  position on reopening. Keep previews available in short panels.
- Remove repeated default title/status content while browsing, preserving
  custom field labels, placement and visibility. Keep the Issues control clear
  of the boxed shortcut hint; shortcuts remain in the footer and Help.
- Confirm new screen keys before collecting them and distinguish pending,
  unavailable and failed list metadata. Protect newer titles and filter matches
  from older batches after detail bodies leave memory.
- Add source-local Clear list. Suppress the fresh screen baseline, preserve
  Follow/Paused and other terminals, and prevent pending reads from refilling
  cleared state. Keep Clear cache as a separate operation.
- Preserve deliberate filtered selections when reopening Issues, retain unread
  markers for passive matching arrivals, and move focus before asynchronous
  updates replace the preview.
- Keep Comments requests bounded through field-layout changes and stop
  closed panels from restarting requests after a pending response settles.

## 0.2.0 experimental — 2026-11-05

- Make the standalone cache-clear helper invalidate pending reads even when
  its cache directory is already missing, preserving unrelated state.
- Reduce bridge overhead when parsing configuration and checking connection
  identity, including cached reads. Preserve fingerprint checks and reject
  failed hash commands before publishing a connection identity.
- Refine reader spacing and text alignment, use straight disclosure separators,
  and keep unfocused reading surfaces quiet while retaining full focus outlines.
  Align Help and Options with the reader and use consistent native chevrons.
  Let Help use the empty footer without resizing the retained reader.
- Keep Enter inside Peek; use Cmd+Enter or Ctrl+Enter to open the viewed issue
  in Jira. Lead keyboard help with the daily flow and put other actions under
  More shortcuts. Show reading/search hints for the current context.
- Add direct issue pinning: P or the inline pin toggles the viewed issue, and K
  returns to it while preserving the filter and other unread issues. Pinning a
  different issue moves the pin immediately. Keep session and cache bounds intact;
  label the separate source option Keep this terminal.
- Add a directly accessible keyboard guide, visible action shortcuts, and local
  C/D/F/N keys for comments, details, Follow and unread issues. Keep text editing
  intact and reveal focused disclosures on capable hosts.
- Pause Follow during deliberate reader entry and keyboard paging; retain focus
  when closing disclosures. Add keyboard navigation between Help topics.
- Pause Follow during Tab navigation and preserve reader focus when resuming
  Follow from a disclosure that disappears as the selected issue changes.
- Give short panels a dedicated issue list, with Enter returning to the reader.

## 0.1.0 experimental — 2026-11-04

First public release of the native herdr-app edition. The separate
[TUI project](https://github.com/hilmimuktitama/herdr-jira-peek) has its own
release history.

- Discover allowlisted issue keys from the focused terminal and read Jira
  descriptions, fields and comments in an attached native panel.
- Follow new work or pause to browse without losing selection, filters or
  reading position. Pin a source and navigate unread issues independently.
- Set up Jira Cloud API-token access inside the panel, or use an existing
  private REST/TWG configuration. Keep credentials and caches outside the mod.
- Configure reader fields through the UI or the bundled agent guide and schema.
- Install with a personal layout and toolbar toggle; preserve existing layouts,
  settings and shortcuts. Ship explicit updates, validation, backups and rollback.
- Keep temporary update checkouts free of detached Git maintenance so cleanup
  cannot race background repacking.
- Include optional source patches for host input/reading behavior and source-key
  highlighting. No patched host binary is distributed.
- Disclose AI-assisted development and practical precautions. Collaboration,
  issue reports, pull requests, feature requests and support are closed for now;
  the private vulnerability-reporting route remains available.

Requires **herdr-app >= 0.1.10** and the separate **herdr-core** `hc` executable.
See [known limitations](README.md#known-limitations), [installation](README.md#install),
and [security](SECURITY.md) before use.

Earlier private previews also used 0.1.0. Use the source installer once to move
those installations to this release; version-only update checks cannot detect
that transition. See [updates](README.md#update-remove-and-inspect).
