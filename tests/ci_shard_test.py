#!/usr/bin/env python3
"""Sharding must cover every test file exactly once and stay balanced."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_shards", ROOT / "scripts/ci_shards.py")
assert SPEC and SPEC.loader
ci_shards = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_shards)


class ShardTests(unittest.TestCase):
    def test_every_file_appears_exactly_once(self):
        files = ci_shards.suite_files()
        shards = ci_shards.assign(files, 2)
        assigned = [name for shard in shards for name in shard]
        self.assertEqual(sorted(assigned), files)
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_unknown_files_are_assigned_not_dropped(self):
        shards = ci_shards.assign(["bridge_test.py", "new_suite_test.py"], 2)
        self.assertIn("new_suite_test.py", [name for shard in shards for name in shard])

    def test_assignment_is_deterministic(self):
        files = ci_shards.suite_files()
        self.assertEqual(ci_shards.assign(files, 2), ci_shards.assign(files, 2))

    def test_shards_are_duration_balanced(self):
        files = ci_shards.suite_files()
        shards = ci_shards.assign(files, 2)
        loads = [sum(ci_shards.WEIGHTS.get(name, ci_shards.DEFAULT_WEIGHT) for name in shard)
                 for shard in shards]
        self.assertLess(max(loads) / min(loads), 1.5)


if __name__ == "__main__":
    unittest.main()
