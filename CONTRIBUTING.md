# Contributing to native Jira Peek

Start with the [handoff](docs/HANDOFF.md), [installation guide](README.md),
and [recipe](RECIPE.md). This repository contains the native Herdr app edition.
Contributions are distributed under its existing [MIT License](LICENSE).
Jira and Atlassian are Atlassian trademarks; this is an unaffiliated project.

## Public data

Use entirely fictional issues, identities, tenant URLs, terminal output and
credentials in fixtures and examples. Never publish real records, even renamed
or blurred. Keep live configuration, caches and logs outside the checkout.
Follow [AGENTS.md](AGENTS.md) and inspect diffs and image metadata before sharing.
Use the [isolated screenshot fixture](docs/screenshots/README.md).

## Development and verification

Use Node with its built-in test runner, Python 3.9+, `jq`, a POSIX shell and
SHA-256 tooling. Review scripts before running them. From the repository root:

```sh
node --test tests/*.test.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v
python3 scripts/release.py --check
```

The JavaScript suite exercises model, controller, presentation, setup and view
behavior. Python tests cover the bridge, setup helper and installer with
fictional transports. These tests do not establish native rendering or live
Jira permissions. See [the current verification record](docs/VERIFICATION.md#experimental-010-readiness)
for dated results.

The installer must assemble the runtime from `scripts/`. Copying
`mods/jira-peek` alone omits required files. Preserve the mod ID `jira-peek`,
installation owner `herdr-jira-peek`, and installed `runtime/` paths. Keep
package and mod versions aligned; the installer derives its version from them. Preserve
managed updates from the earlier 0.13.0 version. Keep the required installer and personal
layout/shortcut choices explicit in the recipe.
Do not change shipped layouts or unrelated keybindings.

Add user-facing changes under `## Unreleased` in `CHANGELOG.md`. When preparing
a release, `python3 scripts/release.py --version 0.1.1` (with the chosen new
version) updates both manifests and promotes those notes. It creates no commit,
tag or remote change. CI checks versions, notes and any pushed tag. Follow
[the release checklist](RELEASING.md#frequent-release-workflow) before publishing.
Updater tests use local Git repositories and fictional installations; they
never need GitHub credentials or contact Jira.

For host validation, install into a new canonical absolute temporary app home:

```sh
peek_check_home=$(python3 -c 'import pathlib,tempfile; print(pathlib.Path(tempfile.mkdtemp(prefix="jira-peek-check-")).resolve())')
python3 scripts/install-app.py --app-home "$peek_check_home" --check
```

The checker requires Herdr app and its runtime tools. It is not visual QA.
Use `python3 docs/screenshots/capture.py --app --app-review` for an isolated
fictional app/core, and inspect the UI through native interaction. Record exact
host/platform, commands, results and coverage limits in [verification](docs/VERIFICATION.md)
and [UX acceptance](docs/UX-REVIEW.md). Never capture a connected work session.

The optional [renderer extension](native/APP-HIGHLIGHT.md) needs its own native
matching, lifecycle, build and visual checks. Its historical development build
does not validate release mode or Linux GUI behavior. Follow
[RELEASING.md](RELEASING.md) for publication gates.

## Reviews and reports

Keep changes focused and preserve unrelated work. Explain the problem, changed
behavior and actual checks; distinguish source review from runtime evidence.
Report bugs with fictional reproduction steps, the native package and host
versions, platform, expected behavior and actual behavior. Do not attach local
configuration, credentials, raw terminal output or issue caches. Report
vulnerabilities privately using [SECURITY.md](SECURITY.md).
