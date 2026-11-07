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
CURRENT_VERSION = json.loads((ROOT / "package.json").read_text())["version"]
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
        manifest = json.loads((target / "install.json").read_text())
        for name in installer.ICON_FILES:
            self.assertEqual((target / name).read_bytes(), (ROOT / "mods/jira-peek" / name).read_bytes())
            self.assertEqual(manifest["files"][name], installer.digest(target / name))
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
        self.assertEqual(current["version"], CURRENT_VERSION)
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
        self.assertEqual(current["version"], CURRENT_VERSION)
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
        manifest.pop("format", None)
        for name in installer.AGENT_FILES | installer.UPDATE_FILES | installer.ICON_FILES:
            manifest["files"].pop(name)
            (target / name).unlink()
        (target / "icons").rmdir()

    def mark_previous_version(self, target, manifest):
        manifest.pop("format", None)
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
        self.assertEqual(current["version"], CURRENT_VERSION)
        self.assertEqual(current["owner"], previous["owner"])
        self.assertEqual(current["configDir"], previous["configDir"])
        self.assertEqual(fields.read_text(), settings)
        self.assertEqual((self.home / "keys.json").read_text(), '{"global":{"f2":"terminal"}}')
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        self.assertEqual(json.loads((backup / "install.json").read_text()), previous)

    def test_update_from_bundle_without_update_helpers(self):
        target = self.install()
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        previous.pop("format", None)
        for name in installer.UPDATE_FILES | installer.ICON_FILES:
            previous["files"].pop(name)
            (target / name).unlink()
        (target / "icons").rmdir()
        marker.write_text(json.dumps(previous))
        self.install(update=True)
        for name in installer.UPDATE_FILES:
            self.assertTrue((target / name).is_file())
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        self.assertEqual(json.loads((backup / "install.json").read_text()), previous)

    def test_update_adds_icons_to_older_bundle_and_protects_edited_icons(self):
        target = self.install()
        marker = target / "install.json"
        previous = json.loads(marker.read_text())
        previous.pop("format", None)
        for name in installer.ICON_FILES:
            previous["files"].pop(name)
            (target / name).unlink()
        (target / "icons").rmdir()
        marker.write_text(json.dumps(previous))
        self.install(update=True)
        self.assertTrue(all((target / name).is_file() for name in installer.ICON_FILES))
        icon = target / "icons/link.svg"
        icon.write_text("<!-- personal icon -->\n")
        with self.assertRaisesRegex(ValueError, "local edits"):
            self.install(update=True)
        self.assertEqual(icon.read_text(), "<!-- personal icon -->\n")

    def test_rollback_preserves_current_settings_and_both_bundles(self):
        target = self.install(config_dir="/fictional/old/config")
        original = (target / "main.js").read_bytes()
        self.install(update=True, config_dir="/fictional/current/config")
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        (backup / "gpui-kit.d.ts").write_text("generated")
        preferences = self.home / "data/jira-peek/fields.json"
        preferences.write_text('{"version":1,"connections":[]}')
        bindir = self.fixture_commands()
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}), contextlib.redirect_stdout(io.StringIO()):
            installer.rollback(self.home, backup.name, check=True)
        self.assertEqual((target / "main.js").read_bytes(), original)
        self.assertEqual(json.loads((target / "install.json").read_text())["configDir"], "/fictional/current/config")
        self.assertEqual(preferences.read_text(), '{"version":1,"connections":[]}')
        self.assertTrue(backup.is_dir())
        self.assertEqual(len(list((self.home / "mods").glob(".jira-peek-backup-*"))), 2)
        self.assertFalse((target / "gpui-kit.d.ts").exists())

    def test_rollback_rejects_tampered_backup_and_path_traversal(self):
        target = self.install()
        original = (target / "install.json").read_bytes()
        self.install(update=True)
        backup, = (self.home / "mods").glob(".jira-peek-backup-*")
        (backup / "main.js").write_text("// edited backup")
        with self.assertRaisesRegex(ValueError, "local edits"):
            installer.rollback(self.home, backup.name)
        with self.assertRaises(ValueError):
            installer.rollback(self.home, "../jira-peek")
        self.assertEqual((target / "install.json").read_bytes(), original)

    def test_overlapping_installs_fail_without_replacing_files(self):
        target = self.install()
        original = (target / "install.json").read_bytes()
        with installer.installation_lock(self.home), self.assertRaisesRegex(ValueError, "in progress"):
            self.install(update=True)
        self.assertEqual((target / "install.json").read_bytes(), original)

    def test_versioned_manifest_accepts_managed_additions_and_rejects_unknown_format(self):
        target = self.install()
        marker = target / "install.json"
        manifest = json.loads(marker.read_text())
        future = target / "runtime/future-helper.py"
        future.write_text("# Fictional future managed helper\n")
        manifest["files"]["runtime/future-helper.py"] = installer.digest(future)
        marker.write_text(json.dumps(manifest))
        installer.managed_install(target)
        manifest["format"] = 2
        marker.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "unexpected installation manifest"):
            self.install(update=True)
        self.assertTrue(future.is_file())

    def test_local_edit_during_native_check_is_preserved(self):
        target = self.install()
        def edit_during_check(_staged):
            (target / "main.js").write_text("// edit made during check")
        with mock.patch.object(installer, "native_check", side_effect=edit_during_check), \
                mock.patch.object(installer, "require_capabilities"), \
                mock.patch.object(installer, "capabilities"), self.assertRaisesRegex(ValueError, "local edits"):
            self.install(update=True, check=True)
        self.assertEqual((target / "main.js").read_text(), "// edit made during check")
        self.assertEqual(list((self.home / "mods").glob(".jira-peek-backup-*")), [])
        self.assertEqual(list((self.home / "mods").glob(".jira-peek-install-*")), [])

    def test_failed_replacement_restores_previous_bundle(self):
        target = self.install()
        original = (target / "install.json").read_bytes()
        rename = Path.rename
        def fail_staged(path, destination):
            if path.name.startswith(".jira-peek-install-"):
                raise OSError("Fictional failed rename")
            return rename(path, destination)
        with mock.patch.object(Path, "rename", fail_staged), self.assertRaises(OSError):
            self.install(update=True)
        self.assertEqual((target / "install.json").read_bytes(), original)
        installer.managed_install(target)

    def test_candidate_changed_during_check_never_replaces_current_bundle(self):
        target = self.install()
        original = (target / "install.json").read_bytes()
        def change_candidate(staged):
            (staged / "main.js").write_text("// fictional unexpected candidate edit")
        with mock.patch.object(installer, "native_check", side_effect=change_candidate), \
                self.assertRaisesRegex(ValueError, "local edits"):
            self.install(update=True, check=True)
        self.assertEqual((target / "install.json").read_bytes(), original)
        self.assertEqual(list((self.home / "mods").glob(".jira-peek-backup-*")), [])

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

    def fixture_commands(self, version="0.1.10", check_exit=0, core_version="0.1.16"):
        bindir = self.home / "bin"
        bindir.mkdir(exist_ok=True)
        for name in ("hc", "sh", "jq", "python3", "sha256sum", "curl"):
            path = bindir / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        (bindir / "hc").write_text('#!/bin/sh\nif [ "$1" = --version ]; then printf "hc ' + core_version + '\\n"; fi\nexit 0\n')
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
            self.assertEqual(report["herdr_core_version"], "0.1.16")
            self.assertTrue(report["alternatives"]["curl"])
            self.assertFalse(report["alternatives"]["twg"])
            (bindir / "jq").unlink()
            self.assertFalse(installer.capabilities()["required"]["jq"])

    def test_core_version_cannot_satisfy_the_desktop_app_minimum(self):
        bindir = self.fixture_commands(version="0.1.9", core_version="1.10.0")
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}):
            report = installer.capabilities()
            self.assertEqual(report["herdr_core_version"], "1.10.0")
            self.assertTrue(report["required"]["hc"])
            self.assertFalse(report["required"]["herdr-app >= 0.1.10"])
            self.assertFalse(report["ok"])
            (bindir / "herdr-app").unlink()
            self.assertIsNone(installer.capabilities()["herdr_app_version"])
            self.fixture_commands(version="0.1.10", core_version="0.0.1")
            self.assertTrue(installer.capabilities()["ok"])
            (bindir / "hc").write_text('#!/bin/sh\nexit 1\n')
            report = installer.capabilities()
            self.assertIsNone(report["herdr_core_version"])
            self.assertTrue(report["ok"])  # Core minimum is not a numeric gate.

    def test_doctor_names_both_components_and_the_exact_app_minimum(self):
        bindir = self.fixture_commands()
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"PATH": str(bindir)}), \
                mock.patch("sys.argv", ["install-app.py", "--doctor"]), contextlib.redirect_stdout(output):
            installer.main()
        text = output.getvalue()
        self.assertIn("herdr-app version (desktop UI): 0.1.10", text)
        self.assertIn("herdr-core version (hc terminal backend): 0.1.16", text)
        self.assertIn(">= 0.1.10 requirement applies only to herdr-app", text)
        self.assertIn("Required herdr-core CLI (hc on PATH): available", text)

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




class AttachmentTests(unittest.TestCase):
    setUp = InstallTests.setUp
    install = InstallTests.install

    def stock(self, panel_id=None):
        # An entirely fictional layout and minimal supported toolbar contract.
        (self.home / 'layouts').mkdir(exist_ok=True)
        stock = self.home / 'mods/tabs'
        stock.mkdir(parents=True)
        self.toolbar = 'import { h_flex } from "gpui-base";\nfunction find(node, id) {}\n      .when(w?.buttons, el => el)\n'
        (stock / 'main.js').write_text(self.toolbar)
        body = {'id': 'work-body', 'type': 'row', 'children': [{'id': 'terminal', 'type': 'block', 'content': {'tab': 'active'}}]}
        if panel_id:
            body['children'].append({'id': panel_id, 'type': 'block', 'size': {'px': 420}, 'content': {'mod': 'jira-peek'}})
        layout = {'id': 'root', 'type': 'column', 'children': [
            {'id': 'tabs', 'type': 'block', 'content': {'mod': 'tabs'}}, body]}
        self.layout_text = json.dumps(layout)
        (self.home / 'layouts/main.json').write_text(self.layout_text)
        (self.home / 'keys.json').write_text('{"global":{"f2":"fictional-action"}}')

    def test_attachment_creates_panel_and_toolbar_and_preserves_originals(self):
        self.stock()
        self.install(attach_layout='main')
        layout = json.loads((self.home / 'layouts/main-jira-peek.json').read_text())
        self.assertEqual(layout['children'][0]['content']['mod'], 'tabs-jira-peek')
        self.assertEqual(layout['children'][1]['children'][-1]['content']['mod'], 'jira-peek')
        toolbar = (self.home / 'mods/tabs-jira-peek/main.js').read_text()
        self.assertIn('layout.toggle', toolbar)
        self.assertIn('find(root, "jira-peek")', toolbar)
        self.assertEqual((self.home / 'mods/tabs/main.js').read_text(), self.toolbar)
        self.assertEqual((self.home / 'layouts/main.json').read_text(), self.layout_text)
        self.assertEqual(json.loads((self.home / 'keys.json').read_text()), {'global': {'f2': 'fictional-action'}})
        self.install(update=True, attach_layout='main')
        self.assertEqual((self.home / 'mods/tabs-jira-peek/main.js').read_text(), toolbar)

    def test_attachment_reuses_existing_panel_id_and_width(self):
        self.stock('fictional-peek')
        self.install(attach_layout='main')
        layout = json.loads((self.home / 'layouts/main-jira-peek.json').read_text())
        panels = layout['children'][1]['children']
        self.assertEqual(len(panels), 2)
        self.assertEqual(panels[-1]['size']['px'], 420)
        self.assertIn('find(root, "fictional-peek")', (self.home / 'mods/tabs-jira-peek/main.js').read_text())

    def test_plain_update_adds_missing_toolbar_and_is_repeatable(self):
        self.stock('fictional-peek')
        self.install()
        self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())
        self.install(update=True)
        layout = self.home / 'layouts/main-jira-peek.json'
        toolbar = self.home / 'mods/tabs-jira-peek/main.js'
        self.assertIn('find(root, "fictional-peek")', toolbar.read_text())
        before = (layout.read_bytes(), toolbar.read_bytes())
        self.install(update=True)
        self.assertEqual((layout.read_bytes(), toolbar.read_bytes()), before)
        self.assertEqual((self.home / 'layouts/main.json').read_text(), self.layout_text)

    def test_plain_update_preserves_custom_integration(self):
        self.stock()
        self.install(attach_layout='main')
        toolbar = self.home / 'mods/tabs-jira-peek/main.js'
        toolbar.write_text('// personal toolbar\n')
        self.install(update=True)
        self.assertEqual(toolbar.read_text(), '// personal toolbar\n')

    def test_automatic_toolbar_is_checked_before_installation(self):
        self.stock()
        target = self.install()
        before = (target / 'install.json').read_bytes()
        with mock.patch.object(installer, 'native_check', side_effect=ValueError('fictional check failure')):
            with self.assertRaisesRegex(ValueError, 'fictional check failure'):
                self.install(update=True, check=True)
        self.assertEqual((target / 'install.json').read_bytes(), before)
        self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())

    def test_partial_publication_is_complete_and_repairable_without_reinstall(self):
        for fail_at in (1, 2, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as temporary:
                previous = self.home
                self.home = Path(temporary).resolve()
                try:
                    self.stock()
                    target = self.install()
                    plan = installer.attachment_plan(self.home, 'main')
                    real_link = installer.os.link
                    calls = 0
                    def fail_link(*args, **kwargs):
                        nonlocal calls
                        calls += 1
                        if calls == fail_at:
                            raise OSError('fictional publication failure')
                        return real_link(*args, **kwargs)
                    output = io.StringIO()
                    with mock.patch.object(installer.os, 'link', side_effect=fail_link), contextlib.redirect_stdout(output):
                        installer.install(self.home, update=True)
                    self.assertIn('Bundle installed successfully', output.getvalue())
                    self.assertIn('--repair-integration', output.getvalue())
                    for path, content in plan.files.items():
                        if path.exists(): self.assertEqual(path.read_text(), content)
                    self.assertEqual(list(self.home.rglob('.jira-peek-attach-*.tmp')), [])
                    bundle = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
                    backups = list((self.home / 'mods').glob('.jira-peek-backup-*'))
                    with contextlib.redirect_stdout(io.StringIO()):
                        installer.repair_integration(self.home, check=False)
                        installer.repair_integration(self.home, check=False)
                    self.assertEqual({p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}, bundle)
                    self.assertEqual(list((self.home / 'mods').glob('.jira-peek-backup-*')), backups)
                    for path, content in plan.files.items(): self.assertEqual(path.read_text(), content)
                finally:
                    self.home = previous

    def test_staging_failure_never_creates_partial_final_file(self):
        self.stock()
        plan = installer.attachment_plan(self.home, 'main')
        with mock.patch.object(installer.os, 'fsync', side_effect=OSError('fictional short write')):
            with self.assertRaises(OSError): installer.attach(plan, self.home)
        self.assertTrue(all(not path.exists() for path in plan.files))
        self.assertEqual(list(self.home.rglob('.jira-peek-attach-*.tmp')), [])

    def test_generation_input_drift_during_check_preserves_old_bundle(self):
        self.stock()
        target = self.install()
        before = (target / 'install.json').read_bytes()
        for source in ('layouts/main.json', 'mods/tabs/main.js'):
            with self.subTest(source=source):
                path = self.home / source
                original = path.read_text()
                def change_source(_staged): path.write_text(original + '\n')
                with mock.patch.object(installer, 'native_check', side_effect=change_source):
                    with self.assertRaisesRegex(ValueError, 'Source layout or toolbar changed'):
                        self.install(update=True, check=True)
                self.assertEqual((target / 'install.json').read_bytes(), before)
                self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())
                path.write_text(original)

    def test_drift_between_publications_stops_without_removing_completed_files(self):
        self.stock()
        plan = installer.attachment_plan(self.home, 'main')
        original = installer.publish_attachment
        def publish_then_drift(path, content):
            original(path, content)
            (self.home / 'mods/tabs/main.js').write_text(self.toolbar + '\n')
        with mock.patch.object(installer, 'publish_attachment', side_effect=publish_then_drift):
            with self.assertRaisesRegex(ValueError, 'Source layout or toolbar changed'):
                installer.attach(plan, self.home)
        first = next(iter(plan.files))
        self.assertEqual(first.read_text(), plan.files[first])
        self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())

    def test_concurrent_personal_creation_wins_over_exclusive_publication(self):
        self.stock()
        plan = installer.attachment_plan(self.home, 'main')
        real_link = installer.os.link
        def competing_link(source, target, **kwargs):
            target.write_text('// fictional personal edit\n')
            return real_link(source, target, **kwargs)
        with mock.patch.object(installer.os, 'link', side_effect=competing_link):
            with self.assertRaisesRegex(ValueError, 'preserved'): installer.attach(plan, self.home)
        self.assertEqual(next(iter(plan.files)).read_text(), '// fictional personal edit\n')
        self.assertEqual(list(self.home.rglob('.jira-peek-attach-*.tmp')), [])

    def test_concurrent_edit_after_publication_is_preserved_and_not_reported_ready(self):
        self.stock()
        plan = installer.attachment_plan(self.home, 'main')
        first, last = next(iter(plan.files)), list(plan.files)[-1]
        original = installer.publish_attachment
        def publish_then_edit(path, content):
            original(path, content)
            if path == last: first.write_text('// fictional concurrent edit\n')
        with mock.patch.object(installer, 'publish_attachment', side_effect=publish_then_edit):
            with self.assertRaisesRegex(ValueError, 'changed before completion'):
                installer.attach(plan, self.home)
        self.assertEqual(first.read_text(), '// fictional concurrent edit\n')

    def test_orphan_link_alias_is_unlinked_without_rewriting_final_or_unknown_files(self):
        self.stock()
        self.install(attach_layout='main')
        final = self.home / 'mods/tabs-jira-peek/main.js'
        orphan = final.parent / '.jira-peek-attach-99999999-fictional.tmp'
        installer.os.link(final, orphan)
        final.chmod(0o600)
        unknown = final.parent / '.jira-peek-attach-99999999-unknown.tmp'
        unknown.write_text('fictional incomplete staging')
        unknown.chmod(0o600)
        before = final.read_bytes()
        with mock.patch.object(installer.os, 'kill', side_effect=ProcessLookupError), contextlib.redirect_stdout(io.StringIO()):
            installer.repair_integration(self.home, check=False)
        self.assertFalse(orphan.exists())
        self.assertEqual(final.read_bytes(), before)
        self.assertTrue(unknown.exists())

    def test_repair_refuses_missing_unmanaged_or_modified_bundle_before_integration(self):
        self.stock()
        with self.assertRaises(ValueError): installer.repair_integration(self.home, check=False)
        target = self.install()
        (target / 'main.js').write_text('// fictional personal modification')
        with self.assertRaisesRegex(ValueError, 'local edits'):
            installer.repair_integration(self.home, check=False)
        self.assertFalse((self.home / 'layouts/main-jira-peek.json').exists())

    def test_postcommit_guidance_inspection_errors_keep_successful_install_and_fall_back(self):
        self.stock()
        target = self.install()
        real_snapshot = installer.integration_snapshot
        for failure in (PermissionError('fictional unreadable helper'), UnicodeError('fictional encoding error')):
            def fail_helper(path):
                if path.name == 'update-app.py' and path.parent.name == 'runtime': raise failure
                return real_snapshot(path)
            output = io.StringIO()
            with mock.patch.object(installer, 'attach', side_effect=OSError('fictional attachment failure')), \
                 mock.patch.object(installer, 'integration_snapshot', side_effect=fail_helper), \
                 contextlib.redirect_stdout(output):
                confirmed = installer.install(self.home, update=True)
            self.assertEqual(confirmed, target)
            self.assertEqual(installer.managed_install(target)['version'], CURRENT_VERSION)
            self.assertIn('Bundle installed successfully', output.getvalue())
            self.assertIn('Review docs/PANEL-INTEGRATION.md', output.getvalue())
            self.assertNotIn('fictional', output.getvalue())

    def test_personal_conflicts_and_unsupported_hosts_fail_before_mod_replacement(self):
        self.stock()
        self.install(attach_layout='main')
        marker = (self.home / 'mods/jira-peek/install.json').read_bytes()
        personal = self.home / 'mods/tabs-jira-peek/main.js'
        personal.write_text('// personal changes\n')
        with self.assertRaisesRegex(ValueError, 'preserved'):
            self.install(update=True, attach_layout='main')
        self.assertEqual(personal.read_text(), '// personal changes\n')
        self.assertEqual((self.home / 'mods/jira-peek/install.json').read_bytes(), marker)
        (self.home / 'mods/tabs/main.js').write_text('// different host implementation\n')
        with self.assertRaisesRegex(ValueError, 'manual integration'):
            self.install(update=True, attach_layout='main')
        self.assertEqual((self.home / 'mods/jira-peek/install.json').read_bytes(), marker)

    def test_attachment_refuses_paths_and_symlinks(self):
        self.stock()
        for name in ('../main', '/main', 'main.json', ''):
            with self.assertRaises(ValueError): installer.attachment_plan(self.home, name)
        (self.home / 'mods/tabs-jira-peek').symlink_to(self.home / 'mods/tabs')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.install(attach_layout='main')
        self.assertEqual((self.home / 'mods/tabs/main.js').read_text(), self.toolbar)

    def test_duplicate_layout_ids_are_rejected_before_replacing_an_installation(self):
        self.stock()
        target = self.install(attach_layout='main')
        marker = (target / 'install.json').read_bytes()
        source = self.home / 'layouts/main.json'
        layout = json.loads(source.read_text())
        layout['children'][1]['children'].append({'id': 'terminal', 'type': 'block', 'content': {'mod': 'jira-peek'}})
        source.write_text(json.dumps(layout))
        with self.assertRaisesRegex(ValueError, 'duplicate IDs'):
            self.install(update=True, attach_layout='main')
        self.assertEqual((target / 'install.json').read_bytes(), marker)
        self.assertEqual(source.read_text(), json.dumps(layout))
        self.assertEqual((self.home / 'mods/tabs/main.js').read_text(), self.toolbar)

    def test_another_layout_cannot_silently_retarget_the_shared_personal_toolbar(self):
        self.stock()
        target = self.install(attach_layout='main')
        marker = (target / 'install.json').read_bytes()
        toolbar = (self.home / 'mods/tabs-jira-peek/main.js').read_bytes()
        layout = json.loads(self.layout_text)
        layout['children'][1]['children'].append({'id': 'other-peek', 'type': 'block', 'content': {'mod': 'jira-peek'}})
        (self.home / 'layouts/other.json').write_text(json.dumps(layout))
        with self.assertRaisesRegex(ValueError, 'preserved'):
            self.install(update=True, attach_layout='other')
        self.assertFalse((self.home / 'layouts/other-jira-peek.json').exists())
        self.assertEqual((target / 'install.json').read_bytes(), marker)
        self.assertEqual((self.home / 'mods/tabs-jira-peek/main.js').read_bytes(), toolbar)


if __name__ == "__main__":
    unittest.main()
