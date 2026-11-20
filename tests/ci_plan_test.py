#!/usr/bin/env python3
"""The CI selector must narrow feedback without hiding a reachable check."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ci_plan", ROOT / "scripts/ci_plan.py")
assert SPEC and SPEC.loader
ci_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_plan)


class PlanTests(unittest.TestCase):
    def assert_plan(self, files, full=False, **expected):
        plan = ci_plan.classify(files, full)
        for key, value in expected.items():
            self.assertEqual(plan[key], value, f"{key} for {files}")

    def test_docs_only_skips_executable_checks(self):
        self.assert_plan(["README.md", "docs/RELIABILITY.md"],
                         static=True, rust=False, integration=False, mode="fast")

    def test_unknown_docs_screenshot_code_fails_closed(self):
        # capture.py is not plain documentation; until it has its own rule,
        # the selector runs every check on every platform.
        self.assert_plan(["docs/screenshots/capture.py"],
                         rust=True, integration=True, mode="full",
                         os=list(ci_plan.FULL_OS))

    def test_rust_change_runs_the_bridge(self):
        self.assert_plan(["rust-backend/src/main.rs"], rust=True, integration=True)

    def test_a_rust_change_hidden_among_docs_still_runs_the_bridge(self):
        self.assert_plan(["README.md", "docs/CHANGELOG.md", "rust-backend/src/main.rs"],
                         rust=True, integration=True)

    def test_node_change_runs_integration_without_rebuilding_rust(self):
        self.assert_plan(["mods/jira-peek/main.js"], rust=False, integration=True)

    def test_workflow_change_forces_the_full_matrix(self):
        self.assert_plan([".github/workflows/ci.yml"], rust=True, integration=True,
                         mode="full", os=list(ci_plan.FULL_OS))

    def test_unknown_path_fails_closed(self):
        self.assert_plan(["docs/new-page.rst", ".github/dependabot.yml"],
                         rust=True, integration=True, mode="full",
                         os=list(ci_plan.FULL_OS))

    def test_empty_diff_fails_closed(self):
        self.assert_plan([], rust=True, integration=True, mode="full")

    def test_full_mode_keeps_every_platform(self):
        self.assert_plan(["docs/RELIABILITY.md"], full=True,
                         rust=True, integration=True, mode="full",
                         os=list(ci_plan.FULL_OS))

    def test_fast_mode_uses_the_fastest_platform(self):
        self.assert_plan(["tests/model.test.js"], os=list(ci_plan.FAST_OS))

    def test_selector_change_tests_the_selector(self):
        self.assert_plan(["scripts/ci_plan.py", "tests/ci_plan_test.py"],
                         rust=True, integration=True, mode="full",
                         os=list(ci_plan.FULL_OS))

    def test_parity_harness_change_runs_the_bridge(self):
        self.assert_plan(["scripts/ci_parity.py"],
                         rust=True, integration=True, mode="full",
                         os=list(ci_plan.FULL_OS))


if __name__ == "__main__":
    unittest.main()
