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

## Publication scope

Preparing or committing a release does not authorize pushing, changing repository
visibility, creating a GitHub release, or submitting to a catalog. Follow the
user's explicit scope and [RELEASING.md](RELEASING.md). A public repository with
the `herdr-mod` topic is eligible for automatic Herdr catalog indexing; changing
visibility can therefore publish the mod indirectly. Check existing releases,
tags and topics before an authorized publication. Never move or delete an
existing release or tag as routine cleanup.

## Continuing native app development

Read [docs/HANDOFF.md](docs/HANDOFF.md) before continuing native app work. It
links the implementation, verification, UX evidence, product constraints, and
remaining investigations. Treat its dated checkpoint as historical evidence;
revalidate the current environment and preserve existing uncommitted changes.
