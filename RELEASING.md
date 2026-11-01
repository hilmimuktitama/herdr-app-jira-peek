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
  The global key example also requires its personal toolbar handler.
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
