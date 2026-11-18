#!/usr/bin/env python3
"""Run the local verification loop. Fast by default; --full before handoff.

Cheap checks run first so a broken table or release file fails in well under a
second. Neither tier replaces CI or the isolated native fixture.
"""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FAST_SKIPS = ("runtime assets, Python compatibility suites, cargo, "
              "transport/TLS, parity, lifecycle acceptance, native acceptance")
FULL_SKIPS = ("cargo fmt/clippy/test, transport/TLS, parity, lifecycle acceptance, "
              "native acceptance")


def node_files():
    patterns = ("tests/*.test.js", "tests/reliability/*.test.js",
                "rust-backend/tests/setup_controller.test.js")
    return sorted(path.relative_to(ROOT).as_posix() for pattern in patterns for path in ROOT.glob(pattern))


def base_revision():
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", "origin/main"],
                            capture_output=True)
    return "origin/main" if result.returncode == 0 else "HEAD"


def stages(full, fixtures=None):
    node = shutil.which("node")
    if not node:
        raise SystemExit("jira-peek: node is required for the verification loop")
    cargo = shutil.which("cargo")
    plan = [
        ("Reliability checklist", [PYTHON, "scripts/verify-plan.py", "--check"]),
        ("Reliability plan", [PYTHON, "scripts/verify-plan.py", "--diff", base_revision()]),
        ("Verifier tests", [PYTHON, "-B", "-m", "unittest", "-q", "tests.verification_test"]),
        ("Release metadata", [PYTHON, "scripts/release.py", "--check"]),
        ("Whitespace", ["git", "diff", "--check", "HEAD"]),
    ]
    if full:
        plan.append(("Runtime assets", [PYTHON, "scripts/package-runtime.py"]))
    plan.append(("Node suite", [node, "--test", *node_files()]))
    if full and fixtures:
        plan.append(("Fixture runtime", [cargo, "build", "--locked", "--release", "--features",
                                        "fixture-http", "--manifest-path",
                                        "rust-backend/Cargo.toml"]))
    if full:
        plan.append(("Python compatibility suites",
                     [PYTHON, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "*_test.py"]))
    return plan


def environment(fixtures=None):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if fixtures:
        env.update({
            "JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY": str(ROOT / "rust-backend/target/release/jira-peek-bridge"),
            "JIRA_PEEK_LEGACY_SOURCE": str(fixtures / "v0.9.1"),
            "JIRA_PEEK_HISTORICAL_SOURCES": str(fixtures),
        })
    return env


def notes(full, fixtures=None):
    if not full or fixtures:
        return
    if not os.environ.get("JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY"):
        print("note: fixture-backed management tests skip; set "
              "JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY to a fixture-http build to run them")
    if not os.environ.get("JIRA_PEEK_LEGACY_SOURCE") or not os.environ.get("JIRA_PEEK_HISTORICAL_SOURCES"):
        print("note: historical lifecycle tests skip; set JIRA_PEEK_LEGACY_SOURCE and "
              "JIRA_PEEK_HISTORICAL_SOURCES from scripts/prepare-lifecycle-fixtures.py to run them")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    tier = parser.add_mutually_exclusive_group()
    tier.add_argument("--fast", action="store_true", help="Cheap local loop while iterating (default)")
    tier.add_argument("--full", action="store_true", help="Complete local loop before handoff")
    parser.add_argument("--keep-going", action="store_true", help="Run later stages after a failure")
    parser.add_argument("--list", action="store_true", help="Print the stages without running them")
    parser.add_argument("--fixtures", type=Path, metavar="DIRECTORY",
                        help="Use prepare-lifecycle-fixtures.py output with --full to run fixture-backed tests")
    args = parser.parse_args()
    full = bool(args.full)
    fixtures = args.fixtures.resolve() if args.fixtures else None
    if fixtures and not full:
        parser.error("--fixtures requires --full")
    if fixtures and not ((fixtures / "complete.json").is_file() and (fixtures / "v0.9.1").is_dir()):
        parser.exit(1, "jira-peek: --fixtures needs a complete prepare-lifecycle-fixtures.py directory\n")
    plan = stages(full, fixtures)
    if args.list:
        for name, command in plan:
            print(f"{name}: {shlex.join(command)}")
        return
    if not (ROOT / "docs/RELIABILITY.md").is_file():
        parser.exit(1, "jira-peek: run from the source checkout\n")
    if full and not shutil.which("cargo"):
        parser.exit(1, "jira-peek: cargo is required for --full to build runtime assets\n")
    notes(full, fixtures)
    failed, started = [], time.monotonic()
    for name, command in plan:
        print(f"\n== {name} ==", flush=True)
        print("   " + shlex.join(command), flush=True)
        step = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=environment(fixtures))
        elapsed = time.monotonic() - step
        if result.returncode:
            print(f"FAILED {name} ({elapsed:.1f}s)", flush=True)
            print("rerun: " + shlex.join(command), flush=True)
            failed.append(name)
            if not args.keep_going:
                break
        else:
            print(f"ok {name} ({elapsed:.1f}s)", flush=True)
    total = time.monotonic() - started
    if failed:
        parser.exit(1, f"\nFAILED {len(failed)} stage(s) in {total:.1f}s: {', '.join(failed)}\n")
    print(f"\nPASS {'full local' if full else 'fast'} loop in {total:.1f}s ({len(plan)} stages)")
    print("Not covered: " + (FULL_SKIPS if full else FAST_SKIPS) + ".")


if __name__ == "__main__":
    main()
