# Releasing Jira Peek

This source targets **0.18.0 experimental**. Package and mod versions must match.
Never reuse an existing release tag, including `v0.4.0`. Keep mod ID `jira-peek`, installation owner `herdr-jira-peek`, and
installed runtime paths stable.

## Scope and publication

Preparation, committing, pushing, changing visibility, publishing a tag/release,
and catalog submission are separate actions. Follow the user's authorized
scope. Do not move or delete an existing tag or release as routine cleanup.
The published `v0.1.0` tag identifies the first public experimental release.
Leave it intact; choose an unused numbered tag for the next release. Never
silently publish old source under new release notes. Never run
`git push --mirror`; push only reviewed branch commits and numbered tags.

A public repository with the `herdr-mod` topic is eligible for automatic Herdr
catalog discovery. Check tags, releases, visibility and topics before publication,
and verify the public result afterward. Do not confuse eligibility with indexing.
No Pages site or separately distributed host binary is needed.

Keep AI-assisted/use-with-caution notices in the README, recipe and release notes.
Collaboration, pull requests, issue reports, feature requests and support are
closed for now. Disable **Issues**, **Pull requests** and **Discussions** in
GitHub repository settings before making it public, then read the settings back.
GitHub supports [disabling Issues](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-issues)
and [Pull requests](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/).
Verify the private vulnerability-reporting route separately; retain the email
fallback in [SECURITY.md](SECURITY.md).

## Candidate checks

Review JP-001 through JP-046 in the [product dictionary](docs/FEATURE-DICTIONARY.md).
Keep the evidence matrix outside the published tree, reconcile implementation
and documentation in both directions, and record native/platform gaps.

1. Inspect the complete tree and reachable history for private data, including
   untracked files, images and metadata. Visually review screenshots. Use only
   entirely fictional fixtures; never ship configuration, credentials or caches.
   Retain the scanned commit/ref IDs and timestamp with QA evidence; local
   checkpoint refs can grow later. Recheck the exact publication commit.
2. Review scripts and hooks before running checks. From the repository root:

   ```sh
   python3 scripts/package-runtime.py
   node --test tests/*.test.js tests/reliability/*.test.js rust-backend/tests/setup_controller.test.js
   cargo build --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
   history_parent=$(mktemp -d)
   history_dir="$history_parent/history"
   python3 -B scripts/prepare-lifecycle-fixtures.py --output "$history_dir"
   JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY="$PWD/rust-backend/target/release/jira-peek-bridge" \
   JIRA_PEEK_LEGACY_SOURCE="$history_dir/v0.9.1" \
   JIRA_PEEK_HISTORICAL_SOURCES="$history_dir" \
   PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*_test.py' -v
   JIRA_PEEK_MANAGEMENT_BINARY="$PWD/rust-backend/target/production/release/jira-peek-bridge" \
   JIRA_PEEK_SOURCE_FIXTURE="$PWD" \
   JIRA_PEEK_FIXTURE_BINARY="$PWD/rust-backend/target/release/jira-peek-bridge" \
   JIRA_PEEK_LEGACY_SOURCE_FIXTURE="$history_dir/v0.9.1" \
   PYTHONDONTWRITEBYTECODE=1 python3 rust-backend/tests/lifecycle_acceptance_test.py -v
   python3 scripts/release.py --check --tag v0.18.0
   for file in config.example.sh scripts/*.sh; do sh -n "$file" || exit; done
   shellcheck -s sh -e SC1090 config.example.sh scripts/*.sh
   git diff --check
   ```

   Run the complete CI sequence in `.github/workflows/ci.yml`, including frozen
   historical fixture preparation and all required environment variables for
   management and lifecycle acceptance. A skipped prerequisite is not a pass.
   `python3 scripts/verify.py --full` is a quicker local pass over the runtime
   build and both suites; it does not replace this list, cargo checks,
   transport/TLS, parity, lifecycle acceptance or the native fixture.
   Also run Rust formatting, Clippy, unit/parity and production TLS tests. Keep
   the production target separate from fixture builds.

   Match CI's ShellCheck version. Check local documentation links and notices.
   The metadata check does not prove an existing tag points at this candidate.
3. Install into a fresh canonical absolute temporary app home with the matching
   production executable and `manage install --source-root ABS --app-home PATH --check`.
   Also exercise the retained Python compatibility installer. Verify bundle hashes and
   run the fictional runtime outside the source checkout. Exercise managed
   updates from the previous release and historical 0.3.0, repeated updates,
   settings preservation and backup restore, including shell → Rust → shell → Rust.
   Retain the new helper when restoring old bundles: historical helpers copy files
   without executable modes and cannot safely restore a Rust backup. Verify separate configuration
   folders retain independent caches/epochs, same-folder aliases share state,
   and an update leaves old shared caches and unrelated settings untouched.
   Confirm the key example has no global or custom-host commands, and that
   conflicting layout IDs/toolbar targets are refused. Do not change the user's app.
4. Re-run affected native interactions after UI changes using the
   [isolated fixture](docs/screenshots/README.md). Unit tests and the native
   checker do not establish visual behavior, live Jira access, Linux GUI, or
   full accessibility. Verify repeated Pin → Unpin → Pin with native pointer
   interactions and a Copy issue as Markdown paste before release. Regenerate
   and inspect the fictional gallery after UI changes. Retain
   [known limitations](README.md#known-limitations).
   For terminal link previews, check the exact issue opens, Escape returns
   keyboard input to the source terminal, and the dock preserves its state.
   Check normal link handling before enable, for an unavailable route, and
   after disable. Record native coverage for local and remote terminals and
   for Cmd-click on macOS and Ctrl-click on Linux.
5. Commit only reviewed paths. Push the authorized branch commit, check visibility,
   and wait for all four CI targets (Linux/macOS, arm64/x86_64) on that exact commit.
   Only then run `python3 scripts/release.py --preflight --tag v0.18.0` from a
   clean worktree. It refuses an existing local or remote tag and prints the
   manual tag, push and draft-release commands. Create the authorized numbered
   tag only after that preflight; the updater can distribute it immediately.
   Confirm the local tag resolves to that commit before pushing it
   (`test "$(git rev-parse HEAD)" = "$(git rev-parse 'v0.18.0^{commit}')"`).
   The tag push runs CI again and is the run that retains release assets.
6. Prepare a GitHub **draft pre-release** at the verified commit with the complete
   three-file runtime asset set from each of the four passing tag-run CI jobs. Use
   `gh release create --verify-tag --draft -R OWNER/REPO`; without `--verify-tag`,
   GitHub can create the tag from the default branch HEAD. Download and verify
   the assets with `scripts/verify-release-assets.py` before publishing. Inspect
   manifests, dependency notices, build type and checksums. Only publish after
   all twelve assets are present. Numbered tags become visible to the updater
   immediately; during any tag/assets visibility gap, installation fails safely
   and preserves the previous bundle. Do not replace already published assets.
   Enable **immutable releases** and a tag ruleset restricting updates and
   deletions on `v*` before the next release. Immutability applies only to
   future releases; the tag ruleset also protects existing `v*` tags.
   Immutability means a bad published asset cannot be replaced: publish a new
   patch and accept that the burnt version number stays unused.
   Create the GitHub **pre-release** from the verified tag. Include the changelog,
   requirements, installation/update commands, limitations, and AI-assisted and
   closed-intake notices. Link documents to the released source. Verify public
   links, source archive contents, installation from that archive, and settings.

## Later releases

Keep pending notes under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md). Select
an unused version and prepare it locally, for example:

```sh
python3 scripts/release.py --version 0.5.5
python3 scripts/release.py --check --tag v0.5.5
```

The helper changes manifests and notes only. Update current version labels and
source links, then repeat the checks above. Use patches for compatible fixes
and minors for new features or breaking changes during 0.x; explain migrations.
Never move a published tag to fix a mistake: publish a new version.

The updater selects numbered `vMAJOR.MINOR.PATCH` tags, including pre-releases;
suffixed tags and branch tips are excluded. Version-only checks cannot identify
a private preview that shares a public version; its first public upgrade uses
the source installer explicitly, even if the reported versions already match.
Keep rollback compatible with retained user settings. CI stays read-only and
`package.json` stays `private: true`; this mod is not an npm package.

## Runtime assets

CI is read-only with respect to repository contents and releases. It retains
production runtime artifacts for review; it never tags or publishes. A tag run
always retains the four artifact sets. A `workflow_dispatch` run also retains
them, so the 12 files can be verified before a tag exists. Build locally with
`python3 scripts/package-runtime.py --output /absolute/evidence/assets`.
The installer consumes the exact numbered release’s binary, JSON manifest and
third-party notices for its platform. Download the four artifact sets with
`gh run download <run-id> -D /absolute/evidence/raw`, flatten them into one
directory, then run:

```sh
python3 scripts/verify-release-assets.py /absolute/evidence/assets
python3 scripts/verify-release-assets.py /absolute/evidence/assets --install-check
```

The verifier is offline: it checks all 12 manifests, sizes, checksums and the
shared source digest, and `--install-check` installs only the host platform
from `HEAD` with `manage install --check`. Verify published HTTPS downloads
after authorized publication. Assets are not independently signed or notarized.

The four runner labels follow the [GitHub runner matrix](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The macOS 15 and Ubuntu 22.04 build baselines are deliberate; a successful newer
local host run alone cannot establish those minimum-platform builds.
