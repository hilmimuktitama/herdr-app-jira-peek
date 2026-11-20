#!/usr/bin/env python3
"""Split the Python compatibility suite into duration-balanced shards.

Weights are local wall times measured on 2026-11-20 with the fixture runtime
and Python 3.9. New test files are never dropped: an unknown file gets a small
default weight and is assigned to the lightest shard.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {
    "bridge_test.py": 88.3,
    "management_test.py": 78.5,
    "update_test.py": 39.0,
    "install_test.py": 24.9,
    "setup_test.py": 9.8,
    "runtime_bundle_test.py": 1.6,
    "screenshot_test.py": 1.6,
    "release_test.py": 0.8,
    "release_assets_test.py": 0.2,
    "verification_test.py": 0.1,
    "ci_plan_test.py": 0.1,
}
DEFAULT_WEIGHT = 1.0


def suite_files():
    return sorted(path.name for path in (ROOT / "tests").glob("*_test.py"))


def assign(names, count):
    if count < 1:
        raise ValueError("shard count must be positive")
    shards = [[] for _ in range(count)]
    loads = [0.0] * count
    ordered = sorted(names, key=lambda name: (-WEIGHTS.get(name, DEFAULT_WEIGHT), name))
    for name in ordered:
        index = min(range(count), key=lambda item: (loads[item], item))
        shards[index].append(name)
        loads[index] += WEIGHTS.get(name, DEFAULT_WEIGHT)
    return shards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, help="zero-based shard (required unless --check)")
    parser.add_argument("--count", type=int, default=2, help="number of shards")
    parser.add_argument("--check", action="store_true",
                        help="print every shard and fail if any file is unassigned")
    args = parser.parse_args()
    files = suite_files()
    shards = assign(files, args.count)
    assigned = [name for shard in shards for name in shard]
    if sorted(assigned) != files or len(assigned) != len(set(assigned)):
        parser.exit(1, "shard assignment dropped or duplicated a test file\n")
    if args.check:
        for index, shard in enumerate(shards):
            weight = sum(WEIGHTS.get(name, DEFAULT_WEIGHT) for name in shard)
            print(f"shard {index}: {weight:.1f}s  {' '.join(shard)}")
        return
    if args.shard is None:
        parser.error("--shard is required unless --check")
    if not 0 <= args.shard < args.count:
        parser.error("--shard is outside --count")
    for name in sorted(shards[args.shard]):
        print(name)


if __name__ == "__main__":
    sys.exit(main())
