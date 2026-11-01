import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_app", ROOT / "scripts/install-app.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-app-install-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()

    def install(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return installer.install(self.home, **kwargs)

    def test_bundle_is_self_contained_and_preserves_user_files(self):
        (self.home / "keys.json").write_text('{"global":{"f2":"terminal"}}')
        (self.home / "layouts").mkdir(); (self.home / "layouts/main.json").write_text('{"id":"original"}')
        target = self.install(config_dir="/fictional/private/config")
        self.assertTrue((target / "runtime/common.sh").is_file())
        self.assertTrue((target / "runtime/app-bridge.sh").is_file())
        self.assertTrue((target / "runtime/app-setup.py").is_file())
        self.assertEqual((target / "AGENTS.md").read_bytes(), (ROOT / "docs/AGENT-GUIDE.md").read_bytes())
        self.assertEqual(json.loads((target / "fields.schema.json").read_text())["properties"]["version"]["const"], 1)
        self.assertEqual(json.loads((target / "mod.json").read_text())["version"],
                         json.loads((target / "install.json").read_text())["version"])
        self.assertEqual(json.loads((ROOT / "package.json").read_text())["version"],
                         json.loads((target / "install.json").read_text())["version"])
        self.assertEqual(json.loads((target / "install.json").read_text())["configDir"], "/fictional/private/config")
        self.assertEqual((self.home / "keys.json").read_text(), '{"global":{"f2":"terminal"}}')
        self.assertEqual((self.home / "layouts/main.json").read_text(), '{"id":"original"}')
        self.assertFalse((self.home / "data/jira-peek/config/config.sh").exists())
        self.assertFalse(any(p.name.endswith(".netrc") for p in target.rglob("*")))

    def test_conflict_update_backup_and_local_edit_protection(self):
        target = self.install()
        with self.assertRaises(ValueError): self.install()
        self.install(update=True)
        backups = list((self.home / "mods").glob(".jira-peek-backup-*"))
        self.assertEqual(len(backups), 1)
        (target / "main.js").write_text("// personal edit\n")
        with self.assertRaises(ValueError): self.install(update=True)
        self.assertEqual((target / "main.js").read_text(), "// personal edit\n")

    def test_update_from_03_adds_setup_without_losing_configuration(self):
        target = self.install(config_dir="/fictional/private/config")
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        previous["version"] = "0.3.0"
        self.remove_agent_files(target, previous)
        previous["files"].pop("runtime/app-setup.py")
        (target / "runtime/app-setup.py").unlink()
        marker.write_text(json.dumps(previous))
        self.install(update=True)
        current = json.loads(marker.read_text())
        self.assertEqual(current["version"], "0.1.0")
        self.assertEqual(current["configDir"], "/fictional/private/config")
        self.assertTrue((target / "runtime/app-setup.py").is_file())
        self.assertEqual(len(list((self.home / "mods").glob(".jira-peek-backup-*"))), 1)

    def test_update_from_05_removes_importer_and_preserves_private_state(self):
        target = self.install(config_dir="/fictional/private/config")
        private = self.home / "data/jira-peek/connection"
        private.mkdir()
        (private / "config.sh").write_text("# Fictional connection must stay unchanged\n")
        helper = target / "runtime/app-document.py"
        helper.write_text("# Former managed helper\n")
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        previous["version"] = "0.5.0"
        self.remove_agent_files(target, previous)
        previous["files"]["runtime/app-document.py"] = installer.digest(helper)
        marker.write_text(json.dumps(previous))
        self.install(update=True)
        current = json.loads(marker.read_text())
        self.assertEqual(current["version"], "0.1.0")
        self.assertEqual(current["configDir"], "/fictional/private/config")
        self.assertFalse(helper.exists())
        self.assertEqual((private / "config.sh").read_text(), "# Fictional connection must stay unchanged\n")
        backups = list((self.home / "mods").glob(".jira-peek-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "runtime/app-document.py").read_text(), "# Former managed helper\n")

    def test_update_from_05_rejects_locally_edited_importer(self):
        target = self.install()
        helper = target / "runtime/app-document.py"
        helper.write_text("# Former managed helper\n")
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        previous["version"] = "0.5.0"
        self.remove_agent_files(target, previous)
        previous["files"]["runtime/app-document.py"] = installer.digest(helper)
        marker.write_text(json.dumps(previous))
        helper.write_text("# Personal edit\n")
        with self.assertRaisesRegex(ValueError, "local edits"):
            self.install(update=True)
        self.assertEqual(helper.read_text(), "# Personal edit\n")

    def remove_agent_files(self, target, manifest):
        for name in installer.AGENT_FILES:
            manifest["files"].pop(name)
            (target / name).unlink()

    def mark_previous_version(self, target, manifest):
        manifest["version"] = "0.13.0"
        mod = target / "mod.json"
        info = json.loads(mod.read_text())
        info["version"] = "0.13.0"
        mod.write_text(json.dumps(info))
        manifest["files"]["mod.json"] = installer.digest(mod)

    def test_update_from_013_installs_agent_contract_and_preserves_field_preferences(self):
        target = self.install(config_dir="/fictional/private/config")
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        self.mark_previous_version(target, previous)
        self.remove_agent_files(target, previous)
        marker.write_text(json.dumps(previous))
        fields = self.home / "data/jira-peek/fields.json"
        settings = '{"version":1,"connections":[]}'
        fields.write_text(settings)
        self.install(update=True)
        self.assertTrue((target / "AGENTS.md").is_file())
        self.assertTrue((target / "fields.schema.json").is_file())
        self.assertEqual(fields.read_text(), settings)
        self.assertEqual(json.loads(marker.read_text())["configDir"], "/fictional/private/config")

    def test_experimental_version_reset_preserves_current_managed_install_state(self):
        target = self.install(config_dir="/fictional/private/config")
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        self.mark_previous_version(target, previous)
        marker.write_text(json.dumps(previous))
        fields = self.home / "data/jira-peek/fields.json"
        settings = '{"version":1,"preferences":{"autoRefresh":false},"connections":[]}'
        fields.write_text(settings)
        (self.home / "keys.json").write_text('{"global":{"f2":"terminal"}}')
        self.install(update=True)
        current = json.loads(marker.read_text())
        self.assertEqual(current["version"], "0.1.0")
        self.assertEqual(current["owner"], previous["owner"])
        self.assertEqual(current["configDir"], previous["configDir"])
        self.assertEqual(fields.read_text(), settings)
        self.assertEqual((self.home / "keys.json").read_text(), '{"global":{"f2":"terminal"}}')
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        self.assertEqual(json.loads((backup / "install.json").read_text()), previous)

    def test_symlink_and_foreign_installation_are_not_overwritten(self):
        (self.home / "mods").mkdir()
        outside = self.home / "other"; outside.mkdir()
        target = self.home / "mods/jira-peek"; target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.install()
        target.unlink(); target.mkdir(); (target / "main.js").write_text("personal")
        with self.assertRaises(ValueError): self.install(update=True)
        self.assertEqual((target / "main.js").read_text(), "personal")

    def test_unsafe_config_path_is_rejected_before_mod_installation(self):
        (self.home / "data").mkdir(); (self.home / "data/jira-peek").symlink_to(self.home / "other")
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.home / "mods/jira-peek").exists())

    def fixture_commands(self, version="0.1.10", check_exit=0):
        bindir = self.home / "bin"
        bindir.mkdir(exist_ok=True)
        for name in ("hc", "sh", "jq", "python3", "sha256sum", "curl"):
            path = bindir / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        app = bindir / "herdr-app"
        app.write_text("#!/bin/sh\n"
                       "if [ \"$1\" = --version ]; then printf 'herdr-app " + version + "\\n'; exit 0; fi\n"
                       "printf generated > \"$2/gpui-kit.d.ts\"\n"
                       "printf generated > \"$2/jsconfig.json\"\n"
                       "exit " + str(check_exit) + "\n")
        app.chmod(0o755)
        return bindir

    def test_doctor_reports_required_and_alternative_capabilities(self):
        bindir = self.fixture_commands()
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}):
            report = installer.capabilities()
            self.assertTrue(report["ok"])
            self.assertEqual(report["herdr_app_version"], "0.1.10")
            self.assertTrue(report["alternatives"]["curl"])
            self.assertFalse(report["alternatives"]["twg"])
            (bindir / "jq").unlink()
            self.assertFalse(installer.capabilities()["required"]["jq"])

    def test_native_check_cannot_use_the_selected_private_configuration(self):
        bindir = self.fixture_commands()
        run = installer.subprocess.run
        checked = []
        def inspect_check(args, **kwargs):
            if args[1] == "check":
                marker = json.loads((Path(args[2]) / "install.json").read_text())
                self.assertIsNone(marker["configDir"])
                checked.append(True)
            return run(args, **kwargs)
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}), mock.patch.object(installer.subprocess, "run", side_effect=inspect_check):
            target = self.install(config_dir="/fictional/private/config", check=True)
        self.assertEqual(checked, [True])
        self.assertEqual(json.loads((target / "install.json").read_text())["configDir"], "/fictional/private/config")

    def test_twg_can_work_while_token_setup_reports_missing_curl(self):
        bindir = self.fixture_commands()
        (bindir / "curl").rename(bindir / "twg")
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}):
            report = installer.capabilities()
        self.assertTrue(report["ok"])
        self.assertFalse(report["token_setup"]["ok"])
        self.assertEqual(report["token_setup"]["required"], {"python3": True, "curl": False})

    def test_check_preflight_and_native_failure_keep_previous_install(self):
        target = self.install()
        original = (target / "install.json").read_bytes()
        bindir = self.fixture_commands(version="0.1.9")
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}):
            with self.assertRaisesRegex(ValueError, "herdr-app"):
                self.install(update=True, check=True)
            self.fixture_commands(check_exit=1)
            (bindir / "hc").unlink()
            with self.assertRaisesRegex(ValueError, "hc"):
                self.install(update=True, check=True)
            self.fixture_commands(check_exit=1)
            with self.assertRaisesRegex(ValueError, "native check failed"):
                self.install(update=True, check=True)
            self.assertEqual((target / "install.json").read_bytes(), original)
            self.assertEqual(list((self.home / "mods").glob(".jira-peek-backup-*")), [])
            self.fixture_commands()
            self.install(update=True, check=True)
        self.assertFalse((target / "gpui-kit.d.ts").exists())
        self.assertFalse((target / "jsconfig.json").exists())

    def test_unmanaged_and_symlink_files_are_not_discarded(self):
        target = self.install()
        extra = target / "personal.txt"
        extra.write_text("personal")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            self.install(update=True)
        self.assertEqual(extra.read_text(), "personal")
        extra.unlink()
        (target / "link").symlink_to(self.home / "missing")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.install(update=True)

    def test_update_preserves_herdr_generated_files_only_in_backup(self):
        target = self.install()
        marker = target / "install.json"
        legacy = json.loads(marker.read_text()); legacy["version"] = "0.1.0"
        marker.write_text(json.dumps(legacy))
        generated = {"gpui-kit.d.ts": "generated types", "jsconfig.json": "generated paths"}
        for name, content in generated.items():
            (target / name).write_text(content)
        self.install(update=True)
        backups = list((self.home / "mods").glob(".jira-peek-backup-*"))
        self.assertEqual(len(backups), 1)
        for name, content in generated.items():
            self.assertEqual((backups[0] / name).read_text(), content)
            self.assertFalse((target / name).exists())

    def test_generated_file_names_do_not_allow_symlinks_or_directories(self):
        target = self.install()
        for name in ("gpui-kit.d.ts", "jsconfig.json"):
            path = target / name
            path.symlink_to(self.home / "missing")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                self.install(update=True)
            path.unlink()
            path.mkdir()
            with self.assertRaisesRegex(ValueError, "unmanaged"):
                self.install(update=True)
            path.rmdir()

    def test_malformed_manifests_are_rejected(self):
        target = self.install()
        marker = target / "install.json"
        original = json.loads(marker.read_text())
        cases = ["{", "[]", json.dumps({"owner": "herdr-jira-peek", "files": {}})]
        for name in ("../escape", "/absolute", "runtime//bad", "runtime/./bad", "runtime/link"):
            changed = json.loads(json.dumps(original))
            changed["files"][name] = "0" * 64
            cases.append(json.dumps(changed))
        (target / "runtime/link").symlink_to(self.home / "missing")
        for payload in cases:
            with self.subTest(payload=payload):
                marker.write_text(payload)
                with self.assertRaises(ValueError):
                    self.install(update=True)
        self.assertTrue((target / "main.js").exists())


if __name__ == "__main__":
    unittest.main()
