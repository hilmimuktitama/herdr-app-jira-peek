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
        # Fixture repositories are cloned/deleted immediately after commands.
        self.git("config", "maintenance.auto", "false")
        self.git("config", "gc.auto", "0")
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

    def test_release_check_does_not_recover_but_mutating_update_does(self):
        backup = self.target.parent / ".jira-peek-backup-0123456789ab"
        manifest = installer.digest(self.target / "install.json")
        self.target.rename(backup)
        journal = self.target.parent / ".jira-peek-replacement.json"
        journal.write_text(json.dumps({"backup": backup.name, "manifest": manifest}))
        with self.assertRaisesRegex(ValueError, "Install Jira Peek first"):
            updater.update(self.home, check_only=True)
        self.assertFalse(self.target.exists())
        self.assertTrue(journal.exists())
        with mock.patch.object(updater, "release_tags", return_value={"0.1.0": "0" * 40}), contextlib.redirect_stdout(io.StringIO()):
            updater.update(self.home)
        installer.managed_install(self.target)
        self.assertFalse(journal.exists())

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

    def stock(self):
        (self.home / 'layouts').mkdir()
        (self.home / 'layouts/main.json').write_text(json.dumps({'id': 'root', 'children': [
            {'id': 'tabs', 'content': {'mod': 'tabs'}},
            {'id': 'work-body', 'type': 'row', 'children': []}]}))
        stock = self.home / 'mods/tabs'
        stock.mkdir()
        stock.joinpath('main.js').write_text((ROOT / 'tests/fixtures/tabs.js').read_text())

    def test_same_release_preserves_integration_and_offers_conditional_guidance(self):
        self.stock()
        self.release('0.1.0')
        for check_only in (True, False):
            before = self.snapshot()
            output = io.StringIO()
            with contextlib.redirect_stdout(output): updater.update(self.home, check_only=check_only)
            self.assertEqual(self.snapshot(), before)
            self.assertIn('no files changed', output.getvalue())
            if not check_only:
                self.assertIn('If the button is missing', output.getvalue())
                self.assertIn('--repair-integration LAYOUT', output.getvalue())
                self.assertNotIn('integration is incomplete', output.getvalue())

    def test_installed_repair_is_offline_source_free_and_targets_its_own_home(self):
        self.stock()
        shutil.rmtree(self.repo)
        helper = self.target / 'runtime/update-app.py'
        bundle = {p.relative_to(self.target): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        (self.base / 'bin/sh').symlink_to('/bin/sh')
        (self.base / 'bin/python3').symlink_to(sys.executable)
        env = dict(os.environ, PATH=str(self.base / 'bin'), HERDR_APP_HOME=str(self.base / 'wrong-home'), GIT_CONFIG_COUNT='1',
                   GIT_CONFIG_KEY_0='url.file:///fictional-unavailable.insteadOf',
                   GIT_CONFIG_VALUE_0=updater.REPOSITORY)
        for _ in range(2):
            result = subprocess.run([sys.executable, '-B', str(helper), '--repair-integration'], cwd=self.base,
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Integration ready', result.stdout)
        self.assertTrue((self.home / 'layouts/main-jira-peek.json').exists())
        self.assertFalse((self.base / 'wrong-home').exists())
        self.assertEqual(list((self.home / 'mods').glob('.jira-peek-backup-*')), [])
        self.assertEqual({p.relative_to(self.target): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}, bundle)

    def test_invalid_repair_flags_fail_without_changes(self):
        before = self.snapshot()
        for flags in (['--check'], ['--allow-downgrade'], ['--version', '0.1.0'], ['--rollback', '.jira-peek-backup-012345abcdef']):
            result = subprocess.run([sys.executable, '-B', str(self.target / 'runtime/update-app.py'),
                                     '--repair-integration', 'main', *flags], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.snapshot(), before)

    def test_installed_diagnostics_are_offline_and_target_the_helpers_own_home(self):
        self.stock()
        shutil.rmtree(self.repo)
        helper = self.target / 'runtime/update-app.py'
        before = self.snapshot()
        env = dict(os.environ, PATH=str(self.base / 'bin'), HERDR_APP_HOME=str(self.base / 'wrong-home'))
        result = subprocess.run([sys.executable, '-B', str(helper), '--diagnose-integration', 'main'],
                                cwd=self.base, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Bundle installed: Jira Peek 0.1.0 (validated)', result.stdout)
        self.assertIn('Active layout: unavailable', result.stdout)
        self.assertIn('Automatic integration support: supported', result.stdout)
        self.assertIn('--repair-integration main', result.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.base / 'wrong-home').exists())

    def test_diagnostics_reject_mutating_or_release_flags(self):
        before = self.snapshot()
        for flags in (['--check'], ['--allow-downgrade'], ['--version', '0.1.0'],
                      ['--repair-integration'], ['--rollback', '.jira-peek-backup-012345abcdef']):
            result = subprocess.run([sys.executable, '-B', str(self.target / 'runtime/update-app.py'),
                                     '--diagnose-integration', 'main', *flags], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.snapshot(), before)

    def test_old_style_wrapper_receives_postcommit_warning_and_repair_can_finish(self):
        self.stock()
        script = self.repo / 'scripts/install-app.py'
        script.write_text(script.read_text().replace('os.link(staged, path, follow_symlinks=False)',
                                                     '(_ for _ in ()).throw(OSError("fictional publication failure"))'))
        self.release('0.1.1')
        output = io.StringIO()
        with contextlib.redirect_stdout(output): updater.update(self.home)
        self.assertEqual(installer.managed_install(self.target)['version'], '0.1.1')
        self.assertIn('Bundle installed successfully; toolbar integration is incomplete', output.getvalue())
        self.assertIn('--repair-integration', output.getvalue())
        self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())
        # A source helper can finish the installed integration without reinstalling.
        with contextlib.redirect_stdout(io.StringIO()): installer.repair_integration(self.home, check=False)
        self.assertTrue((self.home / 'layouts/main-jira-peek.json').exists())

    def test_lost_postcommit_acknowledgement_reads_back_instead_of_assuming_failure(self):
        real_run = subprocess.run
        for index, mode in enumerate(('timeout', 'terminated'), start=1):
            version = '0.1.' + str(index)
            self.release(version)
            def lose_ack(args, **kwargs):
                result = real_run(args, **kwargs)
                if any(str(arg).endswith('/scripts/install-app.py') for arg in args):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if mode == 'timeout': raise subprocess.TimeoutExpired(args, 90, output='FICTIONAL_RAW_SENTINEL')
                    return subprocess.CompletedProcess(args, -15, 'FICTIONAL_RAW_SENTINEL', 'FICTIONAL_RAW_SENTINEL')
                return result
            with mock.patch.object(updater.subprocess, 'run', side_effect=lose_ack):
                with self.assertRaisesRegex(ValueError, 'Installed version ' + version) as error:
                    self.update()
            self.assertIn('integration was not verified', str(error.exception))
            self.assertNotIn('FICTIONAL_RAW', str(error.exception))
            self.assertEqual(installer.managed_install(self.target)['version'], version)

    def test_interrupted_readback_that_cannot_validate_reports_unknown(self):
        (self.target / 'main.js').write_text('// fictional drift')
        message = str(updater.installation_failure(self.home, self.target))
        self.assertIn('installed state is unknown', message)

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

    def test_release_download_does_not_start_background_maintenance(self):
        self.release("0.1.1")
        expected = self.git("rev-parse", "refs/tags/v0.1.1")
        trace = self.base / "git-trace.jsonl"
        with mock.patch.dict(os.environ, {"GIT_TRACE2_EVENT": str(trace)}):
            updater.download_release(self.base / "download", "0.1.1", expected)
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertTrue(any(event.get("event") == "start" for event in events))
        maintenance = [event for event in events if event.get("event") == "child_start"
                       and any(arg in {"maintenance", "gc"} for arg in event.get("argv", []))]
        self.assertEqual(maintenance, [])

    def test_actual_v030_installed_helper_updates_without_checkout(self):
        self.historical_helper_update('a935896048a26aef19c0b17fb748c9ebebb0bb19')

    def test_actual_v032_installed_helper_updates_without_checkout(self):
        self.historical_helper_update('a8cf15409e9173800ed7de8da29e57f4f5834cf0')

    def test_actual_v034_installed_helper_updates_to_next_release_without_checkout(self):
        self.historical_helper_update('6cdb73c8dae87389c7755357a0d51432d6327e92',
                                      json.loads((ROOT / 'package.json').read_text())['version'])

    def test_actual_v040_installed_helper_updates_to_candidate_without_checkout(self):
        self.historical_helper_update('2e732ba7c34402216ab11a7e46da11778989496d',
                                      json.loads((ROOT / 'package.json').read_text())['version'])

    def test_actual_v051_installed_helper_updates_to_candidate_without_checkout(self):
        self.historical_helper_update('77c9b08ec876be33f7f822f69a4bc61e036ec9d5',
                                      json.loads((ROOT / 'package.json').read_text())['version'])

    def historical_helper_update(self, revision, release_version='0.3.3'):
        # Immutable historical code, not current scripts with an older version.
        historical = self.base / 'historical'
        historical.mkdir()
        archive = self.base / 'historical.tar'
        subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar',
                        '--output=' + str(archive), revision], check=True, capture_output=True)
        subprocess.run(['tar', '-xf', str(archive), '-C', str(historical)], check=True, capture_output=True)
        old_spec = importlib.util.spec_from_file_location('historical_installer', historical / 'scripts/install-app.py')
        old = importlib.util.module_from_spec(old_spec)
        old_spec.loader.exec_module(old)
        shutil.rmtree(self.target)
        with contextlib.redirect_stdout(io.StringIO()): old.install(self.home)
        shutil.rmtree(historical)
        self.stock()
        (self.home / 'keys.json').write_text('{"global":{"f2":"fictional-action"}}')
        self.release(release_version)
        helper = self.target / 'runtime/update-app.py'
        env = dict(os.environ, GIT_CONFIG_COUNT='1',
                   GIT_CONFIG_KEY_0='url.' + self.repo.as_uri() + '.insteadOf',
                   GIT_CONFIG_VALUE_0='https://github.com/hilmimuktitama/herdr-app-jira-peek.git')
        result = subprocess.run([sys.executable, '-B', str(helper)], cwd=self.base,
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installer.managed_install(self.target)['version'], release_version)
        self.assertTrue((self.home / 'layouts/main-jira-peek.json').exists())
        self.assertIn('activation is unverified', result.stdout)
        self.assertEqual((self.home / 'keys.json').read_text(), '{"global":{"f2":"fictional-action"}}')

    def test_release_installer_adds_toolbar_without_new_updater_flags(self):
        (self.home / 'layouts').mkdir()
        layout = {'id': 'root', 'children': [
            {'id': 'tabs', 'content': {'mod': 'tabs'}},
            {'id': 'work-body', 'type': 'row', 'children': []}]}
        original = json.dumps(layout)
        (self.home / 'layouts/main.json').write_text(original)
        stock = self.home / 'mods/tabs'
        stock.mkdir()
        stock.joinpath('main.js').write_text((ROOT / 'tests/fixtures/tabs.js').read_text())
        self.release('0.1.1')
        before = self.snapshot()
        self.update(check_only=True)
        self.assertEqual(self.snapshot(), before)
        self.update()
        self.assertIn('Jira Peek', (self.home / 'mods/tabs-jira-peek/main.js').read_text())
        self.assertTrue((self.home / 'layouts/main-jira-peek.json').is_file())
        self.assertEqual((self.home / 'layouts/main.json').read_text(), original)

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
