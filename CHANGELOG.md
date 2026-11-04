# Changelog

## Unreleased

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
