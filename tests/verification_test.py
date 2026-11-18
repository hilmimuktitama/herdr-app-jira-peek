"""The reliability checklist and its selector must stay truthful."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_plan", ROOT / "scripts/verify-plan.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

ROW = "| RC-{id} | Risk {id} | `mods/jira-peek/main.js` `~rowActions` | Keep it true. | {cases} |"


class ChecklistTests(unittest.TestCase):
    def test_repository_table_is_complete_and_linked(self):
        rows = planner.parse(planner.CHECKLIST.read_text())
        planner.validate(rows, planner.scenarios_text())
        self.assertGreaterEqual(len(rows), 8)
        self.assertLessEqual(len(rows), 12, "prune the checklist before adding more rows")

    def test_parsing_requires_five_columns(self):
        with self.assertRaisesRegex(planner.ChecklistError, "expected 5 columns"):
            planner.parse("| RC-01 | Risk | `mods/a.js` | Check it. |")

    def test_matching_requires_a_path_and_a_symbol(self):
        rows = planner.parse(ROW.format(id="01", cases="HC-01"))
        sections = {"mods/jira-peek/main.js": ["+ rowActions"]}
        self.assertEqual(len(planner.match(rows, ["mods/jira-peek/main.js"], sections)), 1)
        self.assertEqual(planner.match(rows, ["mods/jira-peek/main.js"],
                                       {"mods/jira-peek/main.js": ["+ unrelated"]}), [])
        self.assertEqual(planner.match(rows, ["docs/README.md"],
                                       {"docs/README.md": ["+ rowActions"]}), [])

    def test_symbols_only_match_the_rows_own_files(self):
        rows = planner.parse(ROW.format(id="01", cases="HC-01"))
        files = ["mods/jira-peek/main.js", "docs/README.md"]
        self.assertEqual(planner.match(rows, files, {
            "mods/jira-peek/main.js": ["+ unrelated"],
            "docs/README.md": ["+ rowActions"],
        }), [])

    def test_parse_diff_separates_files_and_keeps_content_lines(self):
        diff = (
            "diff --git a/mods/jira-peek/main.js b/mods/jira-peek/main.js\n"
            "--- a/mods/jira-peek/main.js\n"
            "+++ b/mods/jira-peek/main.js\n"
            "@@ -1 +1,2 @@\n"
            "-old\n"
            "+rowActions\n"
            "+++ literal content\n"
            "diff --git a/docs/README.md b/docs/README.md\n"
            "--- a/docs/README.md\n"
            "+++ b/docs/README.md\n"
            "@@ -1 +1 @@\n"
            "+docs\n"
            "diff --git a/docs/new name.md b/docs/new name.md\n"
            "--- a/docs/new name.md\n"
            "+++ b/docs/new name.md\t\n"
            "@@ -0,0 +1 @@\n"
            "+new\n"
        )
        self.assertEqual(planner.parse_diff(diff), {
            "mods/jira-peek/main.js": ["-old", "+rowActions", "+++ literal content"],
            "docs/README.md": ["+docs"],
            "docs/new name.md": ["+new"],
        })

    def test_untracked_file_content_is_parsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "new.js"
            path.write_text("rowActions\nsecond\n")
            self.assertEqual(planner.file_sections(path), ["+rowActions", "+second"])
            self.assertIsNone(planner.file_sections(Path(temporary) / "missing.js"))

    def test_path_only_rows_match_changes_without_a_symbol(self):
        rows = planner.parse("| RC-01 | Risk | `rust-backend/src/clear_cache.rs` | Keep it true. | HC-01 |")
        self.assertEqual(len(planner.match(rows, ["rust-backend/src/clear_cache.rs"], {})), 1)
        self.assertEqual(planner.match(rows, ["rust-backend/src/main.rs"], {}), [])

    def test_missing_or_extra_cases_are_rejected(self):
        rows = planner.parse(ROW.format(id="01", cases="HC-01"))
        with self.assertRaisesRegex(planner.ChecklistError, "missing cases"):
            planner.validate(rows, "test('HC-02 other', () => {});")
        with self.assertRaisesRegex(planner.ChecklistError, "absent from the checklist"):
            planner.validate(rows, "test('HC-01 mine', () => {}); test('HC-02 extra', () => {});")

    def test_duplicate_ids_are_rejected(self):
        rows = planner.parse(ROW.format(id="01", cases="HC-01")) * 2
        with self.assertRaisesRegex(planner.ChecklistError, "duplicate checklist ids"):
            planner.validate(rows, "test('HC-01 mine', () => {});")


if __name__ == "__main__":
    unittest.main()
