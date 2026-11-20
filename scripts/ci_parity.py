#!/usr/bin/env python3
"""Run the Rust parity suite in parallel, never dropping a test.

The suite subclasses the shell bridge tests and exercises the real fixture
binary. Each test isolates its own temp root and loopback server, so two
processes can share the runner without shared state.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "rust-backend/tests"
BINARY = ROOT / "rust-backend/target/release/jira-peek-bridge"


def load_ids():
    sys.path.insert(0, str(TESTS))
    spec = importlib.util.spec_from_file_location("parity_test", TESTS / "parity_test.py")
    if not spec or not spec.loader:
        raise RuntimeError("cannot load parity_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(module.RustParity)

    def flatten(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                yield from flatten(child)
        else:
            yield item.id()

    return sorted(flatten(suite))


def partition(ids, count):
    if count < 1:
        raise ValueError("count must be positive")
    return [ids[index::count] for index in range(count)]


def run(groups):
    env = dict(os.environ)
    env.setdefault("JIRA_PEEK_RUST_BINARY", str(BINARY))
    failed = False
    processes = []
    for group in groups:
        output = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "unittest", *group],
            cwd=TESTS, env=env, stdout=output, stderr=subprocess.STDOUT, text=True)
        processes.append((process, output))
    for index, (process, output) in enumerate(processes):
        code = process.wait()
        output.seek(0)
        print(f"=== parity shard {index} (exit {code}) ===")
        print(output.read(), end="")
        output.close()
        failed = failed or code != 0
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=2, help="parallel processes")
    parser.add_argument("--list", action="store_true", help="print the partition")
    args = parser.parse_args()
    ids = load_ids()
    if not ids:
        parser.exit(1, "parity suite is empty\n")
    groups = partition(ids, args.count)
    if args.list:
        for index, group in enumerate(groups):
            print(f"shard {index}: {len(group)} tests")
            print("\n".join(group))
        return 0
    return run(groups)


if __name__ == "__main__":
    sys.exit(main())
