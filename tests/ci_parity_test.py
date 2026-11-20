#!/usr/bin/env python3
"""Parallel parity runs must cover every test exactly once."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_parity", ROOT / "scripts/ci_parity.py")
assert SPEC and SPEC.loader
ci_parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_parity)


class ParityTests(unittest.TestCase):
    def test_partition_covers_every_test_exactly_once(self):
        ids = ci_parity.load_ids()
        groups = ci_parity.partition(ids, 2)
        assigned = [name for group in groups for name in group]
        self.assertEqual(sorted(assigned), ids)
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_both_processes_get_work(self):
        groups = ci_parity.partition(ci_parity.load_ids(), 2)
        self.assertTrue(all(groups))

    def test_partition_is_deterministic(self):
        ids = ci_parity.load_ids()
        self.assertEqual(ci_parity.partition(ids, 2), ci_parity.partition(ids, 2))


if __name__ == "__main__":
    unittest.main()
