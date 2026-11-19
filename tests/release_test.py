import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

GIT = ["git", "-c", "user.name=Fictional Author", "-c", "user.email=author@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "core.hooksPath=/dev/null"]


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

    def commit_all(self):
        subprocess.run([*GIT, "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run([*GIT, "commit", "--quiet", "-m", "Fictional release"], cwd=self.root,
                       check=True, capture_output=True)

    def test_preflight_requires_clean_tree_and_unused_local_and_remote_tags(self):
        origin = self.root.parent / (self.root.name + "-origin.git")
        subprocess.run(["git", "init", "--bare", "--quiet", str(origin)], check=True, capture_output=True)
        subprocess.run([*GIT, "remote", "add", "origin", str(origin)], cwd=self.root, check=True)
        self.commit_all()
        subprocess.run([*GIT, "push", "--quiet", "origin", "HEAD:main"], cwd=self.root, check=True, capture_output=True)
        self.assertEqual(release.preflight(self.root, "v0.1.0"), "0.1.0")

        changelog = self.root / "CHANGELOG.md"
        original = changelog.read_text()
        changelog.write_text(original + "\nDirty note.\n")
        with self.assertRaisesRegex(ValueError, "clean"):
            release.preflight(self.root, "v0.1.0")
        changelog.write_text(original)

        subprocess.run([*GIT, "tag", "v0.1.0"], cwd=self.root, check=True)
        with self.assertRaisesRegex(ValueError, "locally"):
            release.preflight(self.root, "v0.1.0")
        subprocess.run([*GIT, "tag", "-d", "v0.1.0"], cwd=self.root, check=True, capture_output=True)

        subprocess.run([*GIT, "tag", "v0.1.0"], cwd=self.root, check=True)
        subprocess.run([*GIT, "push", "--quiet", "origin", "v0.1.0"], cwd=self.root, check=True, capture_output=True)
        subprocess.run([*GIT, "tag", "-d", "v0.1.0"], cwd=self.root, check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "origin"):
            release.preflight(self.root, "v0.1.0")

    def test_preflight_prints_verify_tag_and_repository(self):
        subprocess.run([*GIT, "remote", "add", "origin", "https://github.com/fictional/repo.git"],
                       cwd=self.root, check=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            release.print_preflight("v0.1.0", "0.1.0", self.root)
        printed = output.getvalue()
        self.assertIn("--verify-tag", printed)
        self.assertIn("-R fictional/repo", printed)
        self.assertIn("jira-peek-bridge-macos-aarch64", printed)
        self.assertIn("git push origin HEAD:main v0.1.0", printed)


if __name__ == "__main__":
    unittest.main()
