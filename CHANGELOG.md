# Changelog

## Unreleased

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
