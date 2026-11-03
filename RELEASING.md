# Experimental release procedure

Version: **0.1.0 experimental, private preview**.
Target: [hilmimuktitama/herdr-app-jira-peek](https://github.com/hilmimuktitama/herdr-app-jira-peek).
Mod ID: `jira-peek`. Installation owner: `herdr-jira-peek`.
Keep those identities and installed runtime paths stable when updating from 0.13.0.
This release stream is independent of the [TUI project](https://github.com/hilmimuktitama/herdr-jira-peek).

## Current publication state

The explicitly authorized **2026-11-01** delivery resets this repository to
one initial commit on `main`, tagged `v0.1.0`, and pushes it while keeping it
**private**. The superseded `v0.13.0` GitHub release and tag are retired; a local
recovery bundle and release metadata preserve the former state outside tracked
source. No new GitHub release, public visibility or catalog submission is part
of this delivery. This is a one-time authorized history reset, not a routine
release step.

The repository has the `herdr-mod`, `jira` and `terminal` topics. **Making it
public would enable Herdr catalog discovery through the existing topic.**
Check visibility immediately before and after every authorized push. GitHub
Pages was disabled at the reset preflight, and CI contains only verification.
Historical records of the earlier public extraction do not describe current
visibility. Do not delete or retag history during routine release preparation.

Preparation, a local commit, a private push, a GitHub release, public visibility
and catalog submission are distinct actions. Perform only the actions the user
has authorized. Do not infer publication permission from “prepare” or “commit.”
CI has read-only repository permissions and only runs checks; `package.json`
remains `private: true`.

## Verify the candidate

- Review the complete proposed tree and reachable history for private data,
  including untracked files, images and their metadata. Use wholly fictional
  fixtures. Never ship installed state, credentials, caches or logs.
- Confirm root `RECIPE.md`, `preview.png`, `mods/jira-peek`, and optional
  `keys.json`. Ship no personal `layouts/`. The recipe must explain that the
  installer bundles the runtime; copying the source mod alone is insufficient.
  The global key example requires the optional patched host's `layout.focus`
  capability and the actual attached block ID.
- Keep package, mod and installer versions equal. Run the
  [contributor checks](CONTRIBUTING.md#development-and-verification), shell
  syntax and ShellCheck. Check local links, notices and the final diff.
- Install into isolated state with the real Herdr checker. Verify all bundle
  hashes and run its fictional runtime from outside the source checkout.
  Exercise a managed 0.13.0 → 0.1.0 update, preserving private configuration,
  saved fields, personal layouts and keys; verify the previous bundle backup.
- Review [native workflow evidence and known limits](docs/VERIFICATION.md#experimental-010-readiness).
  Re-run affected native interactions after UI changes. The checker alone does
  not validate layout or focus. Linux GUI, full accessibility and the optional
  renderer release build remain unverified.
- Record exact local results. Remote CI must pass on the actual candidate commit
  after an authorized push; earlier CI runs do not verify an uncommitted tree.

## Frequent release workflow

The update helper distributes **numbered Git tags**, using existing Git access
for this private repository. Pushing `vMAJOR.MINOR.PATCH` makes that version
eligible for the next user-requested update. A GitHub release is useful for
notifications and notes, but is not required by the updater. Its pre-release
flag does not exclude a numbered tag. Tags with a suffix, such as
`v0.2.0-rc.1`, and branch tips are excluded. All 0.x releases remain experimental.

1. Keep work on `main` and collect concise user-facing notes under
   `## Unreleased` in `CHANGELOG.md`. Describe fixes, requirements, migrations
   and any rollback limits. Use patch versions for compatible fixes and minor
   versions for new features or breaking changes during 0.x; call out breaking
   changes explicitly. Keep private settings outside the managed bundle.
2. Select an unused version newer than this stream's current version. The
   retired 0.13.0 stream is historical; do not recreate its tag. Run, for example:

   ```sh
   python3 scripts/release.py --version 0.1.1
   python3 scripts/release.py --check --tag v0.1.1
   ```

   The helper updates package/mod versions and dates the pending changelog
   entry. The installer reads the version rather than maintaining a third copy.
   No commit, tag, push, release or visibility change is made. Update current
   release labels and the example install tag in README and this procedure;
   leave dated historical evidence intact.
3. Follow all candidate checks above. Include an update from the previous
   release, repeated update, custom app home, preservation of settings, and
   restore from the retained backup. The offline suite covers tag selection,
   failed validation and replacement, local edits and concurrent installation.
   Run the real Herdr checker separately and record the distinction.
4. After an authorized commit/push, wait for Linux and macOS CI on that exact
   commit. Recheck remote tags/releases, repository visibility and topics.
   With explicit tag-publication authorization, create an annotated tag on
   that verified commit and push only that tag. **The tag push is distribution**:
   do not push a numbered tag merely to test CI. CI also validates tag/version
   consistency, but a failing tag check cannot retract a user's download.
5. If separately authorized, create a GitHub pre-release using that existing
   tag, with the changelog entry, host requirements, update command and known
   limits. Subscribers can watch GitHub releases for notifications. Do not move
   a released tag to fix a mistake: publish a new patch version. The user's
   updater checks the selected tag object again after fetching it.

Users run `python3 scripts/update-app.py --check`, then the same command without
`--check`. Installed helpers work without the checkout; see
[the user update guide](README.md#update-remove-and-inspect). They always run
the native checker before replacement and retain the previous bundle. Updates
are explicit; no automatic updater service, scheduled job or dependency on
GitHub Actions write permissions is introduced. CI remains read-only.

The helper first ships in a future release containing this change. Existing
0.1.0 users bootstrap once with that release's `install-app.py --update --check`.
During the historical 0.13.0 → 0.1.x transition, the release updater requires
an explicit `--version` and `--allow-downgrade`; local managed installation
continues to support the transition. Backup restore preserves current user
data, so maintain compatibility or document migrations before changing its
schema. Keep backups until users have verified the new release; do not prune
them automatically.

Installation manifest `format: 1` records the owner, version, configuration
reference and SHA-256 hash of every managed file. Its file inventory can grow
between releases, so older helpers can verify a new bundle. Retain support for
historical unversioned manifests and the owner `herdr-jira-peek`. Changing the
manifest format itself requires an explicit migration plan; unsupported formats
are refused. Hashes detect local edits; they are not a publisher signature.
Release source is trusted through the repository and Git transport. Keep normal
Git credentials outside the mod and never include credential-bearing URLs.

## Commit and later publication

1. When asked to commit, stage only reviewed paths, inspect the staged diff,
   and make the local commit. Do not push or change GitHub state implicitly.
2. When an authorized private push is requested, recheck visibility first and
   push the reviewed commit. Check the Linux/macOS CI result for that commit.
3. Before public sharing, inspect all current refs/releases and the existing
   `herdr-mod` topic. If catalog submission should happen later, removal of
   that topic must be explicitly authorized before changing visibility.
4. For an authorized GitHub release of 0.1.0, use its existing reviewed tag;
   never silently move it. Title the release **Jira Peek 0.1.0 — Experimental**
   and set GitHub's **pre-release** flag. Use the [changelog](CHANGELOG.md),
   installation instructions and known limits as the release notes. Update
   private-preview labels only within the separately authorized public scope.
5. Change visibility or submit to the catalog only within the authorized scope.
   Verify public links, license/notices and installation from the exact public
   source archive. Recheck private vulnerability reporting before advertising
   it. Publish no preconfigured bundle and no optional host binary without its
   own build and verification.

## Herdr sharing reference

The official [Herdr app mod instructions](https://github.com/herdrdev/herdr-app/blob/master/defaults/AGENTS.md)
and [sharing guide](https://herdr.dev/mods/#share), checked on 2026-11-01, specify
`mods/<name>/`, `RECIPE.md`, `preview.png`, optional keys and no layouts folder.
The recipe presents the experience first: What you see, How it behaves,
Built from, Watch out, Done when. Installation adapts an existing window,
resolves shortcut conflicts and includes both `herdr-app check` and real app QA.

A public GitHub repository with the `herdr-mod` topic is eligible for automatic
catalog indexing. Eligibility is not proof of indexing: inspect the
[catalog](https://herdr.dev/mods/) after an authorized submission and verify the
exact repository, preview and installation instructions. No Herdr-owned
repository changes, catalog submission or publication are needed to prepare
this candidate locally.
