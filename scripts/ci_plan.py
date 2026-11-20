#!/usr/bin/env python3
"""Select CI checks for a change without ever narrowing the main-branch gate.

Fast mode is for pull requests and development-branch pushes. Main, tags,
merge-queue entries and manual dispatches always run every check on every
platform. An unknown path or an empty diff fails closed: all checks run.
"""
import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FULL_OS = ("ubuntu-22.04", "ubuntu-22.04-arm", "macos-15", "macos-15-intel")
FAST_OS = ("ubuntu-22.04",)

# Markdown, licences and the README screenshot cannot reach executable code.
DOC_PATTERNS = ("*.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "preview.png")

# A Rust or harness change must build and test the bridge.
RUST_PATTERNS = (
    "rust-backend/**",
    "scripts/package-runtime.py",
    "scripts/runtime-bundle.py",
    "scripts/app-bridge.sh",
    "scripts/ci_plan.py",
    "scripts/ci_parity.py",
    "tests/ci_plan_test.py",
    "tests/ci_parity_test.py",
    ".github/workflows/**",
)

# Everything the Python suites and the integrated runtime can reach.
INTEGRATION_PATTERNS = (
    "tests/**",
    "scripts/**",
    "mods/**",
    "rust-backend/**",
    "benchmarks/**",
    "config.example.sh",
    "package.json",
    "keys.json",
    ".github/workflows/**",
    "scripts/ci_plan.py",
)


def matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def is_doc(name):
    return matches(name, DOC_PATTERNS)


def classify(files, full):
    """Return the check plan. Unknown paths select every check."""
    files = [name for name in files if name]
    if full or not files:
        return {
            "mode": "full",
            "os": list(FULL_OS),
            "static": True,
            "rust": True,
            "integration": True,
        }
    unknown = [name for name in files
               if not is_doc(name)
               and not matches(name, RUST_PATTERNS)
               and not matches(name, INTEGRATION_PATTERNS)]
    docs_only = all(is_doc(name) for name in files) and not unknown
    return {
        "mode": "fast",
        "os": list(FAST_OS),
        "static": True,
        "rust": any(matches(name, RUST_PATTERNS) for name in files) or bool(unknown),
        "integration": (not docs_only) or bool(unknown),
    }


def git_changed(base):
    result = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git diff failed")
    return [name for name in result.stdout.splitlines() if name]


def write_outputs(plan, stream):
    stream.write("mode=" + plan["mode"] + "\n")
    stream.write("os=" + json.dumps(plan["os"], separators=(",", ":")) + "\n")
    for key in ("static", "rust", "integration"):
        stream.write(f"{key}={str(plan[key]).lower()}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "fast"), required=True,
                        help="full keeps every platform; fast selects from the diff")
    parser.add_argument("--base", help="revision to diff against in fast mode")
    parser.add_argument("--files", nargs="*", help="changed paths (testing escape hatch)")
    parser.add_argument("--github-output", action="store_true",
                        help="append GitHub Actions outputs instead of printing JSON")
    args = parser.parse_args()
    try:
        if args.mode == "full":
            plan = classify([], full=True)
        elif args.files is not None:
            plan = classify(args.files, full=False)
        elif args.base:
            plan = classify(git_changed(args.base), full=False)
        else:
            parser.error("fast mode needs --base or --files")
    except ValueError as error:
        print("ci_plan: " + str(error), file=sys.stderr)
        return 1
    if args.github_output:
        path = os.environ.get("GITHUB_OUTPUT")
        if not path:
            parser.error("--github-output needs GITHUB_OUTPUT")
        with open(path, "a", encoding="utf-8") as stream:
            write_outputs(plan, stream)
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
