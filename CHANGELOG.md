# Changelog

## Unreleased

- Name herdr-app and herdr-core separately in installation instructions and
  agent guidance. Doctor reports both versions; the >= 0.1.10 minimum applies
  only to herdr-app, while herdr-core is checked through its `hc` executable.
- Add explicit ZIP-friendly `--attach` installation: create a personal layout
  with the panel and Jira Peek toolbar button together, preserving originals.
- Make the whole setup field a native input with a focus outline. Request
  initial and retry focus only after the input is mounted.
- Guard issue actions when a filter excludes the selection; make Clear update
  the model without relying on a native input event. Read one unseen issue
  from +new while preserving Paused and the query. Offer direct lookup and
  accept hyphenated title matches. Keep fetch time visible beside Refresh.
  Record the unresolved host input race, keyboard scrolling and hide/show
  reading-position gaps; put the browser fallback in the reader hint.
- Start Help with collapsed topics; reveal one explanation at a time using
  full-width headings with mouse and keyboard activation.
- Restore working focus after Options/Help, add local link-copy, refresh,
  Options and Help shortcuts, and page issue results with Page Up/Down.
  Enter now respects an explicit preview when the filter also resembles a key.
  Document the stock host's remaining keyboard-scrolling limitation.
- Prioritize the latest selected issue over slow metadata or an earlier issue,
  with two bounded request slots, immediate cached previews and known titles
  during loading. Background failures do not block deliberate issue changes.
- Compare issues with one click each while the list stays open and stationary;
  opening Issues focuses the filter, and its clear control retains selection.
- Keep Open in Jira, Copy link and Refresh beside the issue key; click the key
  to copy it. Inline copy confirmation and stable action placement reduce
  pointer travel and layout shifts. Normal-height lists show four full rows.
- Return directly from Options or Help with a visible ← Issues button;
  keep the filter and selected issue, and show panel close only on the main view.
  Help explains all eleven Options rows using the same labels and order.
- Update to the newest numbered release with one command, check availability,
  or select a specific release. The installed helper works without the source
  checkout and uses existing Git access for private repositories.
- Validate releases with Herdr before replacing the mod, protect local edits
  and concurrent installs, and restore a named backup while retaining current
  configuration, field preferences, layouts and shortcuts.
- Prepare versions and release notes with a local helper; CI checks manifest,
  changelog and tag consistency. Publishing remains an explicit maintainer step.

## 0.1.0 experimental — 2026-11-01

Private source checkpoint for the standalone native mod. Git history restarts
with one initial commit and the `v0.1.0` tag; the earlier 0.13.0 tag and GitHub
release are retired by the explicitly authorized reset. Historical development
notes remain below. Managed installations retain their identity and can update
from earlier development versions.

- Read Jira beside the current terminal, with automatic key discovery, a
  compact reader, explicit refresh, source pinning and Follow/Paused selection.
- Follow Herdr's UI font size and zoom; hide the attached panel with its
  header close action and reopen it through personal toolbar integration.
- Move from terminal to filtering and back with the optional Ctrl+Shift+J
  integration; preserve queries and unfinished forms during loading.
- Configure field placement, order, labels and visibility once per connection.
  The UI and agents share a validated JSON file, with safe reloads and conflict
  handling. Reader preferences use that same file.
- Ship the agent guide and field schema with the installed runtime, covering
  connection settings, layout, typography, shortcuts and session commands.
- Keep installation local and explicit; preserve private configuration,
  personal layouts and keys. Publishing and catalog indexing are separate
  actions. See [release preparation](RELEASING.md).

Known limits: full accessibility and Linux GUI remain unverified; reader
scrolling and immediate synthetic keyboard handoff have host limitations.
Source-terminal highlighting needs an optional pinned renderer extension.
See [verification](docs/VERIFICATION.md#experimental-010-readiness).

## Historical 0.13.0 — 2026-11-01

Native development history carried forward from
[herdr-jira-peek](https://github.com/hilmimuktitama/herdr-jira-peek).
Earlier native entries describe development source versions. Terminal-only
release history remains in that repository.

First standalone native source release.

### Standalone extraction

- Move the native catalog entry and tests to the repository root and include
  the required runtime and installer. Keep package version 0.13.0, mod ID
  `jira-peek`, and managed installation owner `herdr-jira-peek`.
- Give native documentation, CI and releases an independent home, with
  standalone-install and managed-update validation.

### Selected-key highlighting

- Highlight the selected Jira key in its source terminal with an optional,
  pinned Herdr app renderer extension. Follow, Paused selection, source pinning
  and keyboard navigation keep the mark in sync with the displayed issue.
- Add an on/off Highlight source option, capability detection for stock hosts,
  and cleanup when the selection or source is cleared. Terminal input, focus,
  scroll position and copied text stay intact.
- Provide a separate local host build, preserving the installed app and the
  existing layouts and keybindings.

## Earlier native development

### Herdr app edition 0.12.1

- Keep the selected issue key and status visible while scrolling or filtering,
  so an older preview cannot be mistaken for a different search result.
- Explain the configurable keyboard entry command in Quick help. Name the
  issue auto-refresh control explicitly and distinguish it from key discovery.
- Suggest checking both the issue key and access after an unsuccessful lookup.

### Herdr app edition 0.12.0

- Preserve text in Jira panels, expandable sections, task and decision lists,
  and status labels. Identify unsupported content instead of silently omitting it.
- Return REST issue context before loading comments. Comments load separately
  on demand, limited to one page of up to 100 recent comments with the full count.
  Comment errors leave the description available and offer a local retry.
- Keep permission failures local to the affected request. Authentication loss
  still retires the connection; a denied issue no longer discards unrelated data.
- Resume a newly selected issue after request backoff without requiring another
  interaction. Cancel deferred work when its connection changes.
- Measure cache freshness from the original fetch time, including disk-to-memory
  reuse, while keeping the current description readable during refresh.

### Herdr app edition 0.8.0

- Preview filtered issues with plain Up/Down while continuing to type in the
  search field. Enter chooses the highlighted visible result consistently.
- Start at the first visible result when filtering excludes the old selection;
  keep a small search hint visible only while the field has focus.
- Capture the originating terminal before direct search commands move focus.
  Preserve the attached layout, native editing chords, and exact fetch time.
- Record comparable native Mods, observed repository stars, source references,
  and the design choices that suit a quick Peek.

### Herdr app edition 0.7.0

- Add a keyboard focus loop: Ctrl+Shift+J enters the attached reader and
  returns to the originating terminal. Escape backs out of subviews before
  returning. Pinned issue sources do not redirect keyboard return.
- Inspect adjacent issues with arrows, find with Slash or Cmd+F, open Jira
  with Enter, expand the description with Space, and copy the key with Y.
  Reader shortcuts preserve native input/button behavior and modifier keys.
- Show a quiet shortcut hint only while the reader is focused. Keep keyboard
  actions immediate and preserve the existing compact layout and connection.
- Make enabled secondary controls reachable through native Tab/Shift+Tab
  traversal, and return from a filtered reader with a single Escape.

### Herdr app edition 0.6.0

- Open on the current issue, with search and discovered issues behind Issues.
  Browsing, scrolling, and expanding content pause Follow; Enter commits a
  visible filtered result while arrow navigation keeps the list open.
- Use a compact title, readable dates with original-value tooltips, a short
  description excerpt, and comments that expand on demand. Keep full loaded
  content available and identify partially loaded comments.
- Keep Open in Jira as the persistent action. Move pinning, refresh, and copy
  into Options; make every option reachable in a short panel.
- Preserve the attached layout, saved connection, and existing read-only
  request behavior. Start each panel in the compact reader regardless of an
  older saved expanded-list preference.

### Herdr app edition 0.5.1

- Keep Jira Peek focused on terminal and agent activity; remove local document
  import from the attached panel and runtime bundle.
- Keep the optional shortcut attached to the main layout instead of opening
  a floating copy.
- Follow the latest visible issue when an agent revisits an already discovered
  key. Preserve deliberate reading and retain both targets at the 200-key limit.
- Coalesce overlapping screen scans instead of dropping the requested read;
  keep screen and history reads serialized across source changes.
- Let manual Refresh recover failed summary lookups for the current source,
  preserving automatic backoff and avoiding retries for successful omissions.
- Support managed updates from the 0.5.0 bundle with a complete backup,
  retaining the saved Jira connection and rejecting locally edited helpers.

### Herdr app edition 0.4.0

- Add inline Jira Cloud setup in the attached panel: site, account email,
  project allowlist, masked API token, and scoped-token Cloud ID.
- Test account access before activating a connection. Preserve the prior
  configuration on validation or authentication failure; allow token rotation
  without importing saved credentials into the form.
- Store credentials in private local files outside the repository, using a
  private file handoff instead of command arguments. Keep existing-folder
  support for TWG and manually configured REST connections.
- Bundle the setup helper and support updates from app editions 0.1–0.3.
  Inline setup requires Python 3 and curl.

### Herdr app edition 0.3.0

- Use named native buttons and stateful toggles with visible keyboard focus.
  Show lookup validation for keys outside the project
  allowlist and URLs from another Jira origin.
- Give the issue list its own keyboard focus: Up/Down selects adjacent issues,
  Home/End selects the first/last match, and selection scrolls into view.
- Keep source, search, Follow, and Focus reader / Show list directly available.
  Move Scan screen, Read history, Auto-refresh (formerly Live), connection
  settings, and Clear cache into Options; retain connection recovery.
- Keep full Open in Jira, Copy issue key, and Copy issue link labels at 300px.
  Bound long source titles and rows to the panel; collapse the list by default
  at short heights without changing the saved reader preference.
  Show loading/refreshing states and stale refresh errors near the reader;
  keep clipboard confirmation separate from persistent operation errors.
- Preserve source isolation, safe asynchronous requests, and cache behavior.

- Add an isolated interactive UX lab and a Computer Use acceptance record;
  document host limits for reader keyboard scrolling and native Input naming.

### Herdr app edition 0.2.0

- Add optional selected-issue Live refresh at most once every 60 seconds, off for new users,
  with a saved UI choice and a five-minute input inactivity lease. Hidden
  panels may refresh within that lease. Show fetch time from payload file mtime,
  including cache hits; unchanged default screen scans still do no Jira refresh.
- Add explicit History for up to 200 available host history lines without
  scrolling or input, same-origin Jira URL lookup, and reader focus with a
  return-to-list control for narrow panels.
- Add local issue-cache clearing with in-flight response invalidation and
  reconnect, preserving private configuration and credentials.
- Add offline installer `--doctor [--json]` capability reporting and capability
  checks with `--check` before replacement. Preserve full update backups; allow
  only known generated editor files as extras and regenerate them in the new
  bundle. Continue rejecting unmanaged files, managed edits, and symlinks.
- Improve safe plain-text lists, headings, quotes, code, and tables. Bound
  descriptions to 100,000 characters, comments to 100 at 20,000 characters each
  and 1,000,000 body characters total, and metadata values to 4,096 characters.
- Extend the isolated fictional screenshot rig with a temporary terminal/history,
  URL lookup, freshness, reader focus, cache clear, and a reader-focus capture.

### Earlier native app additions

- Add the separately versioned **Herdr app edition 0.1.0**: a native docked
  panel for Herdr app 0.1.10, with source pinning, per-terminal Follow/Browse,
  metadata filtering, manual issue lookup, and theme-aware detail reading.
- Reuse the existing read-only Jira backends through a JSON adapter, with
  connection invalidation, private caching, safe text projection, and bounded
  background requests. Keep credentials local when reading remote terminals.
- Add a guarded app installer, offline adapter/interaction tests, and native
  screenshot captures using a separate app home and core with fictional data.
