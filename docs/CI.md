# Continuous integration

The workflow is `.github/workflows/ci.yml`. It has two scopes:

| Scope | Triggers | Platforms | Checks |
| --- | --- | --- | --- |
| Fast feedback | ordinary development-branch pushes; dispatch with `mode=fast` | `ubuntu-22.04` | Only what the diff can reach |
| Full gate | `push` to `main`, tags; dispatch with `mode=full` | all four | Everything |

Pull requests and the merge queue are disabled by policy: this repository does
not accept contributions. GitHub cannot run CI before a direct push. Every
`main` push gets its own uncancelled full run, and tags are never cancelled;
runs wait for runner capacity. The `gate` job aggregates the result; it is
informational, not a branch-protection check. The local pre-push hook is the
only check that runs before a push, and `--no-verify` bypasses it.

## Selection

`scripts/ci_plan.py` classifies changed paths. Its unit test runs before the
plan is used, and the plan test itself is in the always-run set.

| Changed path | Static | Rust | Integration |
| --- | --- | --- | --- |
| Markdown, licence, `preview.png` | yes | no | no |
| `mods/**` JavaScript | yes | no | yes |
| `rust-backend/**`, runtime scripts | yes | yes | yes |
| Unknown or CI-own path | yes | yes | yes, all four platforms |

Unknown paths and empty diffs fail closed to the full matrix. A change to
`.github/**`, `scripts/ci_*.py`, or `tests/ci_*_test.py` also forces the full
matrix, even from a development branch. `tests/ci_plan_test.py` includes the
hidden-change case: a Rust change listed alongside documentation files must
still select the Rust job.

## Jobs and budgets

| Job | Budget | What it covers |
| --- | --- | --- |
| `plan` | 2 min | Selector self-test and changed-path classification |
| `static` | 2 min | Shell syntax, ShellCheck 0.11.0, release metadata, `verify.py --fast` |
| `rust-lint` | 4 min fast, 12 min full | fmt, Clippy, unit tests |
| `rust-protocol` | 4 min fast, 12 min full | production and fixture builds, two parallel protocol groups |
| `integration` | 4 min fast, 12 min full | production assets, historical fixtures, two duration-balanced Python shards |
| `acceptance` | 4 min fast, 12 min full | production and fixture assets, lifecycle acceptance |
| `gate` | 1 min | Aggregate status; fails when a selected check fails or is skipped |

A job that exceeds its budget fails. Do not raise a budget to hide a retry or a
slow test; fix the cause.

The 60-second per-shard target is met on Linux fast runs. macOS full-mode
shards can take longer. The Linux fast queue is 3-4 seconds; full-mode macOS
jobs can wait minutes for a runner.

## Caches

Each build role caches `~/.cargo/registry`, `~/.cargo/git` and
`rust-backend/target` under its own key (`lint`, `protocol`, `integration`),
keyed by OS, architecture, Rust 1.93.1 and `Cargo.lock`. Acceptance reuses the
`integration` key because it builds the same production and fixture assets.
Separate lint and protocol keys stop the fast lint job's save from hiding the
production and fixture artifacts. The pinned toolchain is cached separately and
shared by every job. The integration and acceptance jobs also cache the prepared
historical fixtures (253 MB), keyed by `source-profiles.json` and the
preparation script.

The cache key does not include source files, so a run on `main` seeds the
dependency build and later development branches restore it. A `Cargo.lock`
change starts a new cache. Caches are branch-scoped, so a branch restores its
base branch's cache and cannot overwrite `main`'s cache.

Production and fixture builds run in parallel (`scripts/ci_build_assets.sh`)
and use separate target directories, so the two cargo processes do not share a
lock.

Linux setup installs only `libcurl4-openssl-dev`; jq and pkg-config are
preinstalled. It tries `apt-get install` without an index refresh and falls
back to `apt-get update`, which keeps setup near 5 seconds instead of 16.

The checkout is full-history, not shallow or blobless: the lifecycle fixtures
run `git archive` on frozen historical tags, and a lazy blob fetch would move
that cost into every test run. A full checkout measures 1-3 seconds here.

`scripts/ci_shards.py` splits `tests/*_test.py` into two shards by measured
duration. A new test file is assigned to the lightest shard, never dropped;
`tests/ci_shard_test.py` checks coverage and balance. Shard 0 runs the 55-second
bridge suite through `scripts/ci_parallel_tests.py` in two isolated processes;
shard 1 runs management/update. `scripts/ci_run_shard.py` runs the two heaviest
files side by side and then the remainder. A separate `acceptance` job runs the
lifecycle suite beside the shards.

`scripts/ci_parity.py` runs the Rust parity suite in two isolated processes in
`rust-protocol`, so a failing half still fails the job and prints both logs.
The suite collects 83 tests; nine inherited cases are skipped by the pre-existing
`EXCLUDED` block in `rust-backend/tests/parity_test.py`, so 74 execute. The
driver reports the skips; it does not drop them.

## Direct pushes

This repository does not accept pull requests, so it has no merge queue. That
means the full matrix cannot run before `main` moves; it runs after the push,
subject to runner capacity. Do not claim the full gate blocks a direct push.
The local hook is the only pre-push check, and it runs the fast loop, not the
platform matrix.

If the policy changes, add `pull_request` and `merge_group` triggers back and
require the `gate` check in the repository ruleset.

## Local hook

Run once per clone:

```sh
scripts/install-hooks.sh
```

The hook checks shell syntax and Python/JavaScript syntax on changed files, then
runs `python3 scripts/verify.py --fast` (about 5 seconds locally). It is a git
hook, not a checklist item, so an agent that skips documented steps still runs
it. `git push --no-verify` bypasses it, as with every hook.

## Runners and cost

The repository is public, so GitHub-hosted standard runners are free. The fast
Linux queue measured 3 seconds at p50 in the audit; the fast path was not
re-measured after the force-full rule. Ordinary development-branch changes keep
that shape. Full-mode macOS jobs can wait minutes for a runner; that is GitHub
capacity, not queue configuration. Blacksmith was not
adopted: it cannot host `macos-15-intel`, and its macOS rate ($0.08/min at
6 vCPU) is more than GitHub's free public-repository minutes. Linux jobs would
save wall time but add a bill for no gate-time benefit.
