import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-release-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "mods/jira-peek").mkdir(parents=True)
        for name in release.MANIFESTS:
            (self.root / name).write_text('{"version":"0.1.0","name":"Fictional package"}\n')
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- A fictional fix.\n\n## 0.1.0 experimental — 2026-11-01\n\n- Initial version.\n")
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True, capture_output=True)

    def test_prepare_updates_versions_and_notes_without_creating_refs(self):
        release.prepare(self.root, "0.1.1")
        self.assertEqual(release.check(self.root, "v0.1.1"), "0.1.1")
        for name in release.MANIFESTS:
            self.assertEqual(json.loads((self.root / name).read_text())["version"], "0.1.1")
        self.assertIn("## Unreleased\n\n## 0.1.1 experimental", (self.root / "CHANGELOG.md").read_text())
        self.assertIn("- A fictional fix.", (self.root / "CHANGELOG.md").read_text())
        result = subprocess.run(["git", "show-ref"], cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_consistency_gate_rejects_wrong_tag_version_and_notes(self):
        release.check(self.root, "v0.1.0")
        with self.assertRaisesRegex(ValueError, "tag"):
            release.check(self.root, "v0.1.1")
        (self.root / "mods/jira-peek/mod.json").write_text('{"version":"0.1.1"}')
        with self.assertRaisesRegex(ValueError, "same numbered version"):
            release.check(self.root)
        (self.root / "package.json").write_text('{"version":"0.1.1"}')
        with self.assertRaisesRegex(ValueError, "changelog"):
            release.check(self.root)

    def test_prepare_refuses_reused_version_or_empty_notes_without_writes(self):
        before = (self.root / "package.json").read_bytes()
        for version in ("0.1.0", "0.0.9", "01.1.1", "0.1.1-rc.1"):
            with self.assertRaises(ValueError):
                release.prepare(self.root, version)
        changelog = self.root / "CHANGELOG.md"
        changelog.write_text(changelog.read_text().replace("- A fictional fix.", ""))
        with self.assertRaisesRegex(ValueError, "user-facing notes"):
            release.prepare(self.root, "0.1.1")
        self.assertEqual((self.root / "package.json").read_bytes(), before)

    def test_prepare_refuses_existing_tag_and_historical_version(self):
        command = ["git", "-c", "user.name=Fictional Author", "-c", "user.email=author@example.invalid",
                   "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
        subprocess.run([*command, "commit", "--quiet", "--allow-empty", "-m", "Fictional release"],
                       cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "tag.gpgsign=false", "tag", "v0.1.1"], cwd=self.root, check=True)
        before = (self.root / "package.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "tag already exists"):
            release.prepare(self.root, "0.1.1")
        changelog = self.root / "CHANGELOG.md"
        changelog.write_text(changelog.read_text() + "\n## Historical 0.13.0 — 2026-11-01\n\nFictional historical release.\n")
        with self.assertRaisesRegex(ValueError, "already appears"):
            release.prepare(self.root, "0.13.0")
        self.assertEqual((self.root / "package.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
