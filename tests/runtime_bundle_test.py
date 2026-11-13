"""Production artifact/migration checks with local fictional installations."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


bundle = module("bundle", "runtime-bundle.py")
installer = module("installer_runtime", "install-app.py")


class RuntimeBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-runtime-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "source"
        self.root.mkdir()
        shutil.copytree(ROOT / "rust-backend", self.root / "rust-backend", ignore=shutil.ignore_patterns("target"))
        shutil.copytree(ROOT / ".release-runtime", self.root / ".release-runtime")
        self.runtime = self.base / "runtime"
        self.runtime.mkdir()
        self.binary, self.manifest, self.notices = bundle.asset_names()
        self.path = self.root / ".release-runtime" / self.manifest
        self.version = json.loads((ROOT / "package.json").read_text())["version"]

    def stage(self):
        bundle.stage(self.root, self.runtime, self.version)

    def change(self, function):
        data = json.loads(self.path.read_text())
        function(data)
        self.path.write_text(json.dumps(data))

    def test_production_bundle_and_legacy_entry_work_without_checkout(self):
        self.stage()
        shutil.rmtree(self.root)
        info = bundle.build_info(self.runtime / "jira-peek-bridge")
        legacy = subprocess.check_output(["sh", str(self.runtime / "app-bridge.sh"), "--build-info"])
        self.assertEqual(json.loads(legacy), info)
        self.assertFalse(info["fixtureTransport"])
        data = (self.runtime / "jira-peek-bridge").read_bytes()
        self.assertNotIn(str(ROOT).encode(), data)
        self.assertNotIn(str(Path.home()).encode(), data)
        self.assertTrue((self.runtime / "THIRD-PARTY-NOTICES.txt").is_file())

    def test_changed_artifact_is_rejected_before_execution(self):
        with (self.root / ".release-runtime" / self.binary).open("ab") as stream:
            stream.write(b"changed")
        with mock.patch.object(bundle, "build_info") as inspect, self.assertRaisesRegex(ValueError, "unsafe runtime"):
            self.stage()
        inspect.assert_not_called()

    def test_wrong_source_release_and_platform_fail_closed(self):
        original = self.path.read_text()
        for field in ("sourceSha256", "releaseVersion", "platform"):
            self.path.write_text(original)
            self.change(lambda data: data.update({field: "wrong"}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "does not match"):
                self.stage()

    def test_wrong_checksum_is_rejected_before_execution(self):
        self.change(lambda data: data["files"][self.binary].update(sha256="0" * 64))
        with mock.patch.object(bundle, "build_info") as inspect, self.assertRaisesRegex(ValueError, "checksum"):
            self.stage()
        inspect.assert_not_called()

    def test_fixture_build_is_not_installable(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({"protocol": 1, "os": bundle.target()[0],
            "arch": bundle.target()[1], "fixtureTransport": True}).encode(), b"")
        with mock.patch.object(bundle.subprocess, "run", return_value=result), self.assertRaisesRegex(ValueError, "fixture build"):
            self.stage()

    def test_system_curl_tls_versions_can_differ_from_build_host(self):
        self.change(lambda data: data["buildInfo"].update(libcurl="fictional-other-system-version", tls="fictional-other-tls-version"))
        self.stage()
        self.assertFalse(bundle.build_info(self.runtime / "jira-peek-bridge")["fixtureTransport"])

    def test_executable_identity_must_match_manifest(self):
        self.change(lambda data: data["buildInfo"].update(version="999.0.0"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.stage()

    def test_release_download_uses_exact_version_and_verifies_all_assets(self):
        assets = self.base / "assets"
        (self.root / ".release-runtime").rename(assets)
        calls = []
        def download(url, destination, limit, deadline):
            calls.append(url)
            shutil.copyfile(assets / url.rsplit("/", 1)[1], destination)
        with mock.patch.object(bundle, "download", side_effect=download):
            self.stage()
        self.assertEqual(calls, [bundle.RELEASES + "/v" + self.version + "/" + name
                                 for name in (self.manifest, self.binary, self.notices)])
        self.assertEqual(bundle.build_info(self.runtime / "jira-peek-bridge")["protocol"], 1)

    def test_http_redirect_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-HTTPS"):
            bundle.HTTPSRedirect().redirect_request(None, None, 302, "redirect", {}, "http://example.test/asset")

    def test_symlink_asset_and_manifest_are_rejected(self):
        for name in (self.manifest, self.binary):
            path = self.root / ".release-runtime" / name
            saved = self.base / (name + ".saved")
            path.rename(saved)
            path.symlink_to(saved)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "unsafe"):
                self.stage()
            path.unlink()
            saved.rename(path)

    def test_rollback_preserves_executable_and_current_settings(self):
        home = self.base / "app"
        with contextlib.redirect_stdout(io.StringIO()):
            target = installer.install(home, config_dir="/fictional/first")
            installer.install(home, config_dir="/fictional/current", update=True)
            backup = next((home / "mods").glob(".jira-peek-backup-*"))
            installer.rollback(home, backup.name)
        info = installer.managed_install(target)
        self.assertEqual(info["configDir"], "/fictional/current")
        self.assertTrue(os.access(target / "runtime/jira-peek-bridge", os.X_OK))
        self.assertFalse(bundle.build_info(target / "runtime/jira-peek-bridge")["fixtureTransport"])


if __name__ == "__main__":
    unittest.main()
