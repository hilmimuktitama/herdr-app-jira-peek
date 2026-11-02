"""Release updates against isolated local Git repositories; no service access."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_app", ROOT / "scripts/update-app.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
installer = updater.installer


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "app"
        self.repo = self.base / "remote"
        self.repo.mkdir()
        for directory in ("scripts", "mods", "docs"):
            shutil.copytree(ROOT / directory, self.repo / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.png", "gpui-kit.d.ts", "jsconfig.json"))
        for name in ("package.json", "LICENSE", "config.example.sh", "CHANGELOG.md"):
            shutil.copyfile(ROOT / name, self.repo / name)
        for name in ("package.json", "mods/jira-peek/mod.json"):
            path = self.repo / name
            metadata = json.loads(path.read_text())
            metadata["version"] = "0.1.0"
            path.write_text(json.dumps(metadata) + "\n")
        self.git("init", "--quiet")
        self.git("config", "user.name", "Fictional Release Author")
        self.git("config", "user.email", "release@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(installer, "ROOT", self.repo):
            self.target = installer.install(self.home, config_dir="/fictional/private/config")
        self.patch = mock.patch.object(updater, "REPOSITORY", str(self.repo))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        bindir = self.base / "bin"
        bindir.mkdir()
        for name in ("hc", "jq", "curl", "shasum"):
            command = bindir / name
            command.write_text("#!/bin/sh\nexit 0\n")
            command.chmod(0o755)
        host = bindir / "herdr-app"
        host.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "herdr-app 0.1.11"; exit 0; fi\nexit "${PEEK_TEST_CHECK_EXIT:-0}"\n')
        host.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PATH": str(bindir) + os.pathsep + os.environ["PATH"]})
        patch.start()
        self.addCleanup(patch.stop)

    def git(self, *args):
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=self.repo,
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def release(self, version, annotated=False, tag=None):
        for name in ("package.json", "mods/jira-peek/mod.json"):
            path = self.repo / name
            data = json.loads(path.read_text())
            data["version"] = version
            path.write_text(json.dumps(data) + "\n")
        self.git("add", ".")
        self.git("commit", "--quiet", "--allow-empty", "-m", "Fictional release " + version)
        self.git("tag", *( ["-a", "-m", "Fictional release"] if annotated else []), tag or "v" + version)

    def update(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            updater.update(self.home, **kwargs)

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def test_numeric_latest_ignores_branches_and_preview_tags(self):
        self.release("0.1.2")
        self.release("0.1.10", annotated=True)
        self.release("9.0.0", tag="v9.0.0-rc.1")
        before = self.snapshot()
        self.update(check_only=True)
        self.assertEqual(self.snapshot(), before)
        self.update()
        manifest = installer.managed_install(self.target)
        self.assertEqual(manifest["version"], "0.1.10")
        self.assertEqual(manifest["configDir"], "/fictional/private/config")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "Fictional release 9.0.0")

    def test_update_preserves_settings_and_repeated_update_is_noop(self):
        self.release("0.1.1")
        (self.home / "keys.json").write_text('{"global":{}}')
        (self.home / "layouts").mkdir()
        (self.home / "layouts/personal.json").write_text('{"id":"personal"}')
        (self.home / "data/jira-peek/fields.json").write_text('{"version":1,"connections":[]}')
        before = self.snapshot()
        self.update()
        for name, content in before.items():
            if not name.startswith("mods/"):
                self.assertEqual((self.home / name).read_bytes(), content)
        after = self.snapshot()
        self.update()
        self.assertEqual(self.snapshot(), after)
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        self.assertEqual((backup / "main.js").read_bytes(), before["mods/jira-peek/main.js"])

    def test_exact_version_and_downgrade_require_explicit_intent(self):
        self.release("0.1.1")
        self.release("0.1.2")
        self.update(version="0.1.1")
        self.assertEqual(installer.managed_install(self.target)["version"], "0.1.1")
        self.update(version="0.1.2")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "downgrade"):
            self.update(version="0.1.1")
        self.assertEqual(self.snapshot(), before)
        self.update(version="0.1.1", allow_downgrade=True)
        self.assertEqual(installer.managed_install(self.target)["version"], "0.1.1")

    def test_missing_release_and_mismatched_tag_do_not_change_install(self):
        self.release("0.1.1", tag="v0.1.2")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.update(version="0.1.3")
        with self.assertRaisesRegex(ValueError, "versions disagree"):
            self.update()
        self.assertEqual(self.snapshot(), before)

    def test_tag_change_and_symlink_release_are_rejected(self):
        (self.repo / "outside").symlink_to("/fictional/outside")
        self.release("0.1.1")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "tag changed"):
            updater.download_release(self.base / "changed", "0.1.1", "0" * 40)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.update()
        self.assertEqual(self.snapshot(), before)

    def test_native_check_failure_and_local_edits_preserve_install(self):
        self.release("0.1.1")
        before = self.snapshot()
        with mock.patch.dict(os.environ, {"PEEK_TEST_CHECK_EXIT": "1"}), self.assertRaisesRegex(ValueError, "installation failed"):
            self.update()
        self.assertEqual(self.snapshot(), before)
        (self.target / "main.js").write_text("// keep local changes")
        with self.assertRaisesRegex(ValueError, "local edits"):
            self.update()
        self.assertEqual((self.target / "main.js").read_text(), "// keep local changes")

    def test_installed_helper_can_restore_without_source_or_network(self):
        self.release("0.1.1")
        self.update()
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        shutil.rmtree(self.repo)
        helper = self.target / "runtime/update-app.py"
        result = subprocess.run([sys.executable, "-B", str(helper), "--rollback", backup.name],
                                cwd=self.base, capture_output=True, text=True,
                                env=dict(os.environ, HERDR_APP_HOME=str(self.base / "wrong-home")))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installer.managed_install(self.target)["version"], "0.1.0")
        self.assertFalse((self.base / "wrong-home").exists())

    def test_installed_helper_updates_from_local_remote_after_checkout_removed(self):
        self.release("0.1.1", annotated=True)
        remote = self.base / "remote.git"
        subprocess.run(["git", "clone", "--quiet", "--bare", str(self.repo), str(remote)],
                       check=True, capture_output=True)
        shutil.rmtree(self.repo)
        helper = self.target / "runtime/update-app.py"
        # Redirect only the official repository URL to this local fixture.
        # The helper runs as an independent process with no source checkout.
        env = dict(os.environ, GIT_CONFIG_COUNT="1",
                   GIT_CONFIG_KEY_0="url." + remote.as_uri() + ".insteadOf",
                   GIT_CONFIG_VALUE_0="https://github.com/hilmimuktitama/herdr-app-jira-peek.git",
                   GIT_DIR=str(self.base / "must-not-be-used"))
        result = subprocess.run([sys.executable, "-B", str(helper)], cwd=self.base,
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installer.managed_install(self.target)["version"], "0.1.1")
        self.assertFalse((self.base / "must-not-be-used").exists())

    def test_no_tags_and_git_errors_are_actionable_without_raw_output(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "No numbered release"):
            self.update()
        self.assertEqual(self.snapshot(), before)
        failed = subprocess.CompletedProcess([], 1, "", "FICTIONAL_PRIVATE_GIT_DIAGNOSTIC")
        with mock.patch.object(updater.subprocess, "run", return_value=failed), self.assertRaisesRegex(ValueError, "repository access") as caught:
            updater.git("ls-remote")
        self.assertNotIn("FICTIONAL_PRIVATE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
