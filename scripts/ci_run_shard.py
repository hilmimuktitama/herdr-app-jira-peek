#!/usr/bin/env python3
"""Run one integration shard with at most two test files at a time.

Files are ordered by measured duration, so management and update overlap.
The bridge file uses its own two-process runner. Every log and exit code is
kept and printed, and a failure in any file fails the shard.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_shards", ROOT / "scripts/ci_shards.py")
if not SPEC or not SPEC.loader:
    raise RuntimeError("cannot load ci_shards.py")
ci_shards = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_shards)


def command(name):
    if name == "bridge_test.py":
        return [sys.executable, "scripts/ci_parallel_tests.py",
                "--file", "tests/bridge_test.py", "--count", "2"]
    return [sys.executable, "-m", "unittest", "discover",
            "-s", "tests", "-p", name, "-v"]


def shard_files(shard, count):
    files = ci_shards.assign(ci_shards.suite_files(), count)[shard]
    return sorted(files, key=lambda name: (-ci_shards.WEIGHTS.get(name, ci_shards.DEFAULT_WEIGHT), name))


def run(files, limit=2):
    failed = False
    for start in range(0, len(files), limit):
        batch = files[start:start + limit]
        processes = []
        for name in batch:
            output = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            process = subprocess.Popen(command(name), cwd=ROOT,
                                       stdout=output, stderr=subprocess.STDOUT, text=True)
            processes.append((name, process, output))
        for name, process, output in processes:
            code = process.wait()
            output.seek(0)
            print(f"=== {name} (exit {code}) ===")
            print(output.read(), end="")
            output.close()
            failed = failed or code != 0
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--list", action="store_true", help="print the run order")
    args = parser.parse_args()
    if not 0 <= args.shard < args.count:
        parser.error("--shard is outside --count")
    files = shard_files(args.shard, args.count)
    if not files:
        parser.exit(1, "empty shard\n")
    if args.list:
        print("\n".join(files))
        return 0
    return run(files)


if __name__ == "__main__":
    sys.exit(main())
