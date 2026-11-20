#!/usr/bin/env python3
"""The shard runner must cover every file in the shard exactly once."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_run_shard", ROOT / "scripts/ci_run_shard.py")
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunShardTests(unittest.TestCase):
    def test_each_shard_matches_the_planner(self):
        for shard in range(2):
            expected = runner.ci_shards.assign(runner.ci_shards.suite_files(), 2)[shard]
            self.assertEqual(runner.shard_files(shard, 2), expected)

    def test_bridge_uses_its_parallel_runner(self):
        self.assertIn("scripts/ci_parallel_tests.py", runner.command("bridge_test.py"))

    def test_plain_file_uses_unittest(self):
        command = runner.command("management_test.py")
        self.assertIn("unittest", command)
        self.assertIn("management_test.py", command)


if __name__ == "__main__":
    unittest.main()
