#!/usr/bin/env python3
"""Parallel test runs must cover every test exactly once."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_parallel_tests", ROOT / "scripts/ci_parallel_tests.py")
assert SPEC and SPEC.loader
parallel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parallel)


class ParallelTests(unittest.TestCase):
    def test_bridge_partition_covers_every_test_exactly_once(self):
        ids = parallel.load_ids(ROOT / "tests/bridge_test.py")
        groups = parallel.partition(ids, 2)
        assigned = [name for group in groups for name in group]
        self.assertEqual(sorted(assigned), ids)
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_both_processes_get_work(self):
        groups = parallel.partition(parallel.load_ids(ROOT / "tests/bridge_test.py"), 2)
        self.assertTrue(all(groups))

    def test_partition_is_deterministic(self):
        ids = parallel.load_ids(ROOT / "tests/bridge_test.py")
        self.assertEqual(parallel.partition(ids, 2), parallel.partition(ids, 2))


if __name__ == "__main__":
    unittest.main()
