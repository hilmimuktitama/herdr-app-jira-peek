# Public repository data policy

- Never commit or push real Jira, company, customer, or private personal data.
  This includes issue keys and content, tenant URLs, identities, terminal
  output, logs, cache files, configuration, credentials, and screenshot metadata.
- Use entirely fictional data for examples, fixtures, screenshots, and demos.
  Do not copy real records and merely rename, blur, or redact their identifiers.
- Capture documentation screenshots with the isolated fictional fixtures in
  `docs/screenshots/capture.py`. Never capture a live work session or connected
  Jira account for publication.
- Before committing or pushing, inspect the proposed diff and new assets for
  private data. Visually review screenshots and check their metadata. Replace
  any questionable sample with a fresh fictional example before publishing.
- Keep real local configuration and plugin state outside the public repository.
  Never print credentials or private data while verifying these rules.

## Host component names and versions

This mod requires **herdr-app >= 0.1.10**, the desktop UI/mod host. The separate
**herdr-core** terminal backend provides **hc**; its version is independent.
Check `herdr-app --version` for the app and `hc --version` for the core. The
installer requires `hc` on PATH without enforcing a numeric core minimum.
Always name the component with its version. Keep **0.1.10** exact; do not
report **1.10.0** or use a core/TUI version to satisfy the app requirement.

## Publication scope

Preparing or committing a release does not authorize pushing, changing repository
visibility, creating a GitHub release, or submitting to a catalog. Follow the
user's explicit scope and [RELEASING.md](RELEASING.md). A public repository with
the `herdr-mod` topic is eligible for automatic Herdr catalog indexing; changing
visibility can therefore publish the mod indirectly. Check existing releases,
tags and topics before an authorized publication. Never move or delete an
existing release or tag as routine cleanup.

## Continuing native app development

Read [README.md](README.md), [RECIPE.md](RECIPE.md), and the installed
[agent contract](docs/AGENT-GUIDE.md) before changing native behavior. Revalidate
the current environment and preserve existing uncommitted changes. Use the
isolated fictional [screenshot fixture](docs/screenshots/README.md) for native
checks; keep temporary QA evidence and development notes outside the published
tree. Follow [RELEASING.md](RELEASING.md) for release checks.
