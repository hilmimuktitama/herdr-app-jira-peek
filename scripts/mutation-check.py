#!/usr/bin/env python3
"""Check that named tests actually fail when their guards are removed.

Each mutation runs in a disposable copy; the working tree is never edited. A
surviving mutation is a verifier gap, not a product bug: either add the missing
regression or record why the guard is untested. This does not prove coverage.
Rust mutations (`--rust`) rebuild the crate and are slower than the JS set.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY = ("mods", "scripts", "tests", "package.json")
FAILED = re.compile(r"^\s*not ok \d+ - (.+)$", re.MULTILINE)
RUST_FAILED = re.compile(r"^test (.+) \.\.\. FAILED$", re.MULTILINE)
MUTANTS = [
    {
        "id": "M-01",
        "file": "mods/jira-peek/model.js",
        "old": "if (configured.origin !== supplied.origin || supplied.username || supplied.password ||",
        "new": "if (supplied.username || supplied.password ||",
        "test": "tests/model.test.js",
        "expect": "effective URL matches share strict origin validation",
    },
    {
        "id": "M-02",
        "file": "mods/jira-peek/model.js",
        "old": "const budget = Math.max(0, limit - marker.length);",
        "new": "const budget = Math.max(0, limit);",
        "test": "tests/markdown.test.js",
        "expect": "exactly-limit document",
    },
    {
        "id": "M-03",
        "file": "mods/jira-peek/model.js",
        "old": "/^customfield_[0-9]{1,12}$/",
        "new": "/^customfield_[0-9]{1,13}$/",
        "test": "tests/field-layout.test.js",
        "expect": "shell, native model and schema agree",
    },
    {
        "id": "M-04",
        "file": "mods/jira-peek/main.js",
        "old": 'const intent = value ? "pin-issue" : "unpin-issue";',
        "new": 'const intent = value ? "unpin-issue" : "pin-issue";',
        "test": "tests/reliability/scenarios.test.js",
        "expect": "HC-01",
    },
    {
        "id": "M-05",
        "file": "mods/jira-peek/model.js",
        "old": 'seen.has(field.id) || (["comments", "issuelinks"].includes(field.id) && field.section === "header")) return null;',
        "new": '(["comments", "issuelinks"].includes(field.id) && field.section === "header")) return null;',
        "test": "tests/markdown.test.js",
        "expect": "invalid or mismatched inputs return null",
    },
    {
        "id": "M-06",
        "file": "mods/jira-peek/main.js",
        "old": "this.rowActions.splice(0)",
        "new": "this.rowActions.slice()",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "each queued row action executes once",
    },
    {
        "id": "M-07",
        "file": "mods/jira-peek/main.js",
        "old": "    for (const { action, context, rowKey } of this.rowActions.splice(0)) {",
        "new": "    const batch = this.rowActions.splice(0);\n    for (const { action, context, rowKey } of batch) { this.rowActions = [];",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "each queued row action executes once",
    },
    {
        "id": "M-08",
        "file": "mods/jira-peek/main.js",
        "old": "      if (this.rowActions.length) this.drainRowActions(cx);",
        "new": "",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "each queued row action executes once per timer wake",
    },
    {
        "id": "M-09",
        "file": "mods/jira-peek/main.js",
        "old": "this.rowActions.push({ action, context }); this.rowWake?.();",
        "new": "this.rowActions.push({ action, context });",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "HC-08",
    },
    {
        "id": "M-10",
        "file": "mods/jira-peek/main.js",
        "old": "    for (const { action, context, rowKey } of this.rowActions.splice(0)) {",
        "new": "    const batch = this.rowActions.splice(0);\n    for (const { action, context, rowKey } of new Map(batch.map(item => [item.rowKey, item])).values()) {",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "each queued row action executes once per timer wake",
    },
    {
        "id": "M-11",
        "file": "mods/jira-peek/main.js",
        "old": "    for (const { action, context, rowKey } of this.rowActions.splice(0)) {",
        "new": "    for (const { action, context, rowKey } of this.rowActions.splice(0).slice(0, 2)) {",
        "test": "tests/reliability/scenarios.test.js",
        "expect": "each queued row action executes once per timer wake",
    },
    {
        "id": "M-12",
        "file": "mods/jira-peek/main.js",
        "old": "          if (this.closed) return;\n          this.drainRowActions(cx);",
        "new": "          if (this.closed) return;\n          this.rowActions = [];",
        "test": "tests/reliability/worker.test.js",
        "expect": "HC-09",
    },
    {
        "id": "M-13",
        "file": "mods/jira-peek/main.js",
        "old": "Math.min(MAX_LIST_ROWS * this.issueRowHeight + 2, this.listResize.start + delta)",
        "new": "Math.min(Math.min(this.model.compactSlots().length, MAX_LIST_ROWS) * this.issueRowHeight + 2, this.listResize.start + delta)",
        "test": "tests/view.test.js",
        "expect": "resizing while fewer matches are shown keeps the chosen height",
    },
    {
        "id": "M-14",
        "file": "mods/jira-peek/main.js",
        "old": "if (resize.moved && resize.height !== resize.start) this.listHeightPx = resize.height;",
        "new": "if (resize.moved) this.listHeightPx = resize.height;",
        "test": "tests/view.test.js",
        "expect": "resizing while fewer matches are shown keeps the chosen height",
    },
    {
        "id": "M-15",
        "file": "mods/jira-peek/main.js",
        "old": "if (!this.listResize.moved && Math.abs(delta) < RESIZE_DRAG_THRESHOLD) return;",
        "new": "if (false) return;",
        "test": "tests/view.test.js",
        "expect": "resizing while fewer matches are shown keeps the chosen height",
    },
]

RUST_MUTANTS = [
    {
        "id": "R-01",
        "file": "rust-backend/src/discovery.rs",
        "old": '        "project in ({projects}) AND ({predicate}) ORDER BY updated DESC, key ASC"',
        "new": '        "({predicate}) ORDER BY updated DESC, key ASC"',
        "test": "scope_and_literals",
        "expect": "scope_and_literals",
    },
    {
        "id": "R-02",
        "file": "rust-backend/src/clear_cache.rs",
        "old": "        Ok(_) => return Err(ROOT),",
        "new": "        Ok(_) => {}",
        "test": "shared_root_and_uninitialized_state_are_rejected_without_invalidation",
        "expect": "shared_root_and_uninitialized_state_are_rejected_without_invalidation",
    },
    {
        "id": "R-03",
        "file": "rust-backend/src/clear_cache.rs",
        "old": "        Ok(meta) if meta.is_dir() => Ok(true),",
        "new": "        Ok(_) => Ok(true),",
        "test": "unsafe_paths_and_cache_shapes_never_change_the_marker",
        "expect": "unsafe_paths_and_cache_shapes_never_change_the_marker",
    },
]


class MutationError(ValueError):
    """The working tree no longer matches a mutation's expected source text."""


def copy_tree(destination):
    for name in COPY:
        source = ROOT / name
        target = destination / name
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("target", "__pycache__", "node_modules"))
        else:
            shutil.copyfile(source, target)


def node_tests(node, cwd, test):
    try:
        result = subprocess.run([node, "--test", "--test-reporter=tap", test], cwd=cwd,
                                capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 124, ["<timeout>"]
    return result.returncode, [match.group(1) for match in FAILED.finditer(result.stdout + result.stderr)]


def apply(tree, mutant):
    path = tree / mutant["file"]
    original = path.read_text()
    if original.count(mutant["old"]) != 1:
        raise MutationError(f"{mutant['id']}: expected exactly one occurrence in {mutant['file']}")
    path.write_text(original.replace(mutant["old"], mutant["new"]))


def report(results, started, advisory):
    print()
    for mutant, status, detail in results:
        print(f"{mutant['id']} {status:<9} {detail}")
    failed = [entry for entry in results if entry[1] != "killed"]
    print(f"\n{len(results) - len(failed)} of {len(results)} mutations killed in {time.monotonic() - started:.1f}s")
    if failed:
        print("A survivor means no named test enforces that guard. Add one, or record why it is untested.")
        print("A hang means the test suite cannot terminate; fix the loop or add a bounded test timeout.")
        if not advisory:
            return 1
    return 0


def run(mutants, node, advisory):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="peek-mutation-") as temporary:
        tree = Path(temporary)
        copy_tree(tree)
        baselines = sorted({mutant["test"] for mutant in mutants})
        for test in baselines:
            code, failures = node_tests(node, tree, test)
            if code:
                raise MutationError(f"baseline {test} already fails: {failures[:3]}")
            print(f"baseline ok  {test}")
        results = []
        for mutant in mutants:
            path = tree / mutant["file"]
            pristine = path.read_text()
            try:
                apply(tree, mutant)
                code, failures = node_tests(node, tree, mutant["test"])
            except MutationError as error:
                results.append((mutant, "stale", str(error)))
                path.write_text(pristine)
                continue
            path.write_text(pristine)
            if not code:
                results.append((mutant, "survived", "no failing test"))
            elif code == 124:
                results.append((mutant, "hang", "test process did not terminate in 120s"))
            elif any(mutant["expect"] in name for name in failures):
                name = next(name for name in failures if mutant["expect"] in name)
                results.append((mutant, "killed", name))
            elif not failures:
                results.append((mutant, "invalid", "test process crashed before reporting a failure"))
            else:
                results.append((mutant, "mismatch", failures[0]))
    return report(results, started, advisory)


def copy_rust(destination):
    shutil.copytree(ROOT / "rust-backend", destination / "rust-backend",
                    ignore=shutil.ignore_patterns("target", "__pycache__"))


def rust_tests(cargo, cwd, test, timeout=900):
    try:
        result = subprocess.run(
            [cargo, "test", "--locked", "--release", "--bins", "--", "--test-threads=1", test],
            cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ["<timeout>"]
    return result.returncode, [match.group(1) for match in RUST_FAILED.finditer(result.stdout + result.stderr)]


def run_rust(mutants, cargo, advisory):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="peek-rust-mutation-") as temporary:
        tree = Path(temporary)
        copy_rust(tree)
        crate = tree / "rust-backend"
        baselines = sorted({mutant["test"] for mutant in mutants})
        for test in baselines:
            code, failures = rust_tests(cargo, crate, test)
            if code:
                raise MutationError(f"baseline {test} already fails or does not compile: {failures[:3]}")
            print(f"baseline ok  {test}")
        results = []
        for mutant in mutants:
            path = tree / mutant["file"]
            pristine = path.read_text()
            try:
                apply(tree, mutant)
                code, failures = rust_tests(cargo, crate, mutant["test"])
            except MutationError as error:
                results.append((mutant, "stale", str(error)))
                path.write_text(pristine)
                continue
            path.write_text(pristine)
            if not code:
                results.append((mutant, "survived", "no failing test"))
            elif code == 124:
                results.append((mutant, "hang", "test process did not terminate in 900s"))
            elif any(mutant["expect"] in name for name in failures):
                name = next(name for name in failures if mutant["expect"] in name)
                results.append((mutant, "killed", name))
            elif not failures:
                results.append((mutant, "invalid", "build failed before a test ran"))
            else:
                results.append((mutant, "mismatch", failures[0]))
    return report(results, started, advisory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Print the mutation set")
    parser.add_argument("--only", action="append", metavar="ID", help="Run one mutation id; repeatable")
    parser.add_argument("--rust", action="store_true", help="Mutate Rust guards instead of JavaScript (slow)")
    parser.add_argument("--advisory", action="store_true", help="Report survivors without failing")
    args = parser.parse_args()
    source = RUST_MUTANTS if args.rust else MUTANTS
    mutants = [mutant for mutant in source if not args.only or mutant["id"] in args.only]
    if not mutants:
        parser.exit(1, "jira-peek: no mutation matched --only\n")
    if args.list:
        for mutant in mutants:
            print(f"{mutant['id']}  {mutant['file']}  ->  {mutant['test']}")
        return
    try:
        if args.rust:
            cargo = shutil.which("cargo")
            if not cargo:
                parser.exit(1, "jira-peek: cargo is required for --rust\n")
            code = run_rust(mutants, cargo, args.advisory)
        else:
            node = shutil.which("node")
            if not node:
                parser.exit(1, "jira-peek: node is required\n")
            code = run(mutants, node, args.advisory)
    except MutationError as error:
        parser.exit(1, f"jira-peek: {error}\n")
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
