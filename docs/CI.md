# Continuous integration

The workflow is `.github/workflows/ci.yml`. It has two scopes:

| Scope | Triggers | Platforms | Checks |
| --- | --- | --- | --- |
| Fast feedback | `pull_request`, development-branch pushes | `ubuntu-22.04` | Only what the diff can reach |
| Full gate | `push` to `main`, tags, `merge_group`, `workflow_dispatch` | all four | Everything |

The full gate is the only path to `main`. The fast scope narrows feedback; it
never replaces the gate. Unknown paths and empty diffs fail closed: every check
runs. A change to the workflow or to `scripts/ci_plan.py` also runs everything.

## Selection

`scripts/ci_plan.py` classifies changed paths. Its unit test runs before the
plan is used, and the plan test itself is in the always-run set.

| Changed path | Static | Rust | Integration |
| --- | --- | --- | --- |
| Markdown, licence, `preview.png` | yes | no | no |
| `mods/**` JavaScript | yes | no | yes |
| `rust-backend/**`, runtime scripts | yes | yes | yes |
| Any unknown path | yes | yes | yes |

`tests/ci_plan_test.py` includes the hidden-change case: a Rust change listed
alongside documentation files must still select the Rust job.

## Jobs and budgets

| Job | Budget | What it covers |
| --- | --- | --- |
| `plan` | 2 min | Selector self-test and changed-path classification |
| `static` | 2 min | Shell syntax, ShellCheck 0.11.0, release metadata, `verify.py --fast` |
| `rust-lint` | 4 min fast, 12 min full | fmt, Clippy, unit tests |
| `rust-protocol` | 4 min fast, 12 min full | production and fixture builds, transport/setup/clear-cache, parallel parity |
| `integration` | 4 min fast, 12 min full | production assets, historical fixtures, two duration-balanced Python shards, lifecycle acceptance |
| `gate` | 1 min | The only required branch-protection check |

A job that exceeds its budget fails. Do not raise a budget to hide a retry or a
slow test; fix the cause.

## Caches

Each build role caches `~/.cargo/registry`, `~/.cargo/git` and
`rust-backend/target` under its own key (`lint`, `protocol`, `integration`),
keyed by OS, architecture, Rust 1.93.1 and `Cargo.lock`. Separate keys stop the
fast lint job's save from hiding the production and fixture artifacts. The integration job also caches the prepared historical fixtures
(253 MB) keyed by `source-profiles.json` and the preparation script.

The cache key does not include source files, so a run on `main` seeds the
dependency build and later PRs restore it. A `Cargo.lock` change starts a new
cache. Caches are branch-scoped, so a PR restores its base branch's cache and
cannot overwrite `main`'s cache.

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
shard 1 runs management/update and the lifecycle acceptance test. The two
walls land near 40 seconds each. `scripts/ci_parity.py` runs the 83-test Rust
parity suite the same way in `rust-protocol`, so a failing half still fails the
job and prints both logs.

## Merge queue

`merge_group` runs the full gate on all four platforms. Enable the queue in the
repository ruleset and require only the `gate` job; the matrix jobs are
aggregated there. Fast-scope PRs therefore pass without waiting for macOS jobs
that did not run, while queue entries still require every platform.

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

The repository is public, so GitHub-hosted standard runners are free. Queueing
measured 3 seconds at p50 and 6 seconds at p95, already inside the 10-second
budget. Blacksmith was not adopted: it cannot host `macos-15-intel`, which is
the slowest supported platform, and its macOS rate ($0.08/min at 6 vCPU) is
more than GitHub's free public-repository minutes. Linux jobs would save wall
time but add a bill for no gate-time benefit.
