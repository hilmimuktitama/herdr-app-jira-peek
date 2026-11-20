#!/usr/bin/env python3
"""Run one unittest file in parallel processes without dropping a test.

Used for the 55-second bridge suite inside integration shard 0. Each test owns
its temporary root and loopback fixture, so separate processes do not share
state. Both outputs and exit codes are kept.
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


def load_ids(path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:
        raise RuntimeError("cannot load " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.TestLoader().loadTestsFromModule(module)

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


def run(path, groups):
    env = dict(os.environ)
    failed = False
    processes = []
    for group in groups:
        output = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "unittest", *group],
            cwd=path.parent, env=env, stdout=output, stderr=subprocess.STDOUT, text=True)
        processes.append((process, output))
    for index, (process, output) in enumerate(processes):
        code = process.wait()
        output.seek(0)
        print(f"=== {path.name} shard {index} (exit {code}) ===")
        print(output.read(), end="")
        output.close()
        failed = failed or code != 0
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="test file under the repository")
    parser.add_argument("--count", type=int, default=2, help="parallel processes")
    parser.add_argument("--list", action="store_true", help="print the partition")
    args = parser.parse_args()
    path = (ROOT / args.file).resolve()
    if not path.is_file():
        parser.error("missing test file: " + str(path))
    ids = load_ids(path)
    if not ids:
        parser.exit(1, "no tests found in " + str(path) + "\n")
    groups = partition(ids, args.count)
    if args.list:
        for index, group in enumerate(groups):
            print(f"shard {index}: {len(group)} tests")
            print("\n".join(group))
        return 0
    return run(path, groups)


if __name__ == "__main__":
    sys.exit(main())
