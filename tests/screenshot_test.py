"""Offline host selection/provenance checks; never launch the desktop app."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("capture", Path(__file__).resolve().parents[1] / "docs/screenshots/capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class ScreenshotHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "Herdr.app"
        self.app = self.bundle / "Contents/MacOS/Herdr"
        self.app.parent.mkdir(parents=True)
        self.app.write_text("#!/bin/sh\nprintf 'herdr-app 0.1.15\\n'\n")
        self.app.chmod(0o755)
        self.info = self.bundle / "Contents/Info.plist"
        self.info.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "0.1.15"}))

    def test_macos_prefers_desktop_bundle_over_stale_path(self):
        with patch.object(capture.sys, "platform", "darwin"), patch.object(capture, "desktop_binaries", return_value=[self.app]), patch.object(capture.shutil, "which") as which:
            self.assertEqual(capture.select_app_binary(), str(self.app.resolve()))
            which.assert_not_called()

    def test_setup_tls_fixture_is_local_and_honors_native_failure_control(self):
        home = self.root / 'fictional-app'
        home.mkdir()
        fixture = capture.setup_transport(self.root, home)
        self.addCleanup(fixture.close)
        code, account = fixture.request()
        self.assertEqual(code, 200)
        self.assertEqual(account['accountId'], 'fictional-native-reader')
        code, issue = fixture.request(path='/rest/api/3/issue/ABC-202')
        self.assertEqual(code, 200)
        self.assertEqual(issue['key'], 'ABC-202')
        (home / 'fixture-response.json').write_text(json.dumps({'mode': 'failure'}))
        self.assertEqual(fixture.request()[0], 401)
        before = len(fixture.calls)
        with self.assertRaises(OSError):
            fixture.request(authority='unroutable.example.invalid')
        self.assertEqual(len(fixture.calls), before)

    def test_explicit_binary_wins_and_resolves_symlinks(self):
        link = self.root / "explicit"
        link.symlink_to(self.app)
        with patch.object(capture, "desktop_binaries") as bundles:
            self.assertEqual(capture.select_app_binary(link), str(self.app.resolve()))
            bundles.assert_not_called()

    def test_ambiguous_bundles_require_explicit_choice(self):
        with patch.object(capture.sys, "platform", "darwin"), patch.object(capture, "desktop_binaries", return_value=[self.app, self.app]):
            with self.assertRaisesRegex(RuntimeError, "Multiple desktop bundles"):
                capture.select_app_binary()

    def test_path_fallback_without_desktop_bundle(self):
        with patch.object(capture.sys, "platform", "darwin"), patch.object(capture, "desktop_binaries", return_value=[]), patch.object(capture.shutil, "which", return_value=str(self.app)):
            self.assertEqual(capture.select_app_binary(), str(self.app.resolve()))

    def test_non_executable_fails_before_launch(self):
        self.app.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "not executable"):
            capture.select_app_binary(self.app)

    def test_metadata_mismatch_is_not_reported_as_matching_host(self):
        self.info.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "0.1.14"}))
        with self.assertRaisesRegex(RuntimeError, "versions differ"):
            capture.host_identity(str(self.app), os.environ.copy())

    def test_pending_update_is_rejected_before_startup_can_swap_app(self):
        self.bundle.with_name("Herdr.app.new.noindex").mkdir()
        with self.assertRaisesRegex(RuntimeError, "update is staged"):
            capture.host_identity(str(self.app), os.environ.copy())

    def test_same_version_binary_replacement_invalidates_evidence(self):
        expected = capture.host_identity(str(self.app), os.environ.copy())
        capture.verify_host_identity(str(self.app), os.environ.copy(), expected)
        self.app.write_text(self.app.read_text() + "# different executable, same version\n")
        with self.assertRaisesRegex(RuntimeError, "changed during native QA"):
            capture.verify_host_identity(str(self.app), os.environ.copy(), expected)


class KeyboardEntryOutcomeTests(unittest.TestCase):
    def test_full_pass_requires_entry_and_escape(self):
        outcome = capture.keyboard_outcome(True, True)
        self.assertTrue(outcome["ok"])
        self.assertTrue(outcome["entry_ok"])
        self.assertEqual(outcome["status"], "entry-and-escape-verified")
        self.assertTrue(outcome["entry"]["verified"])
        self.assertTrue(outcome["escape"]["verified"])
        self.assertIsNone(outcome["escape"]["blocker"])

    def test_blocked_escape_is_unverified_not_a_pass(self):
        outcome = capture.keyboard_outcome(True, False, "CGEventPostToPid denied")
        self.assertFalse(outcome["ok"])
        self.assertTrue(outcome["entry_ok"])
        self.assertEqual(outcome["status"], "entry-verified-escape-unverified")
        self.assertTrue(outcome["entry"]["verified"])
        self.assertFalse(outcome["escape"]["verified"])
        self.assertEqual(outcome["escape"]["blocker"], "CGEventPostToPid denied")

    def test_entry_failure_fails_the_run(self):
        outcome = capture.keyboard_outcome(False, False, "pane.go did not move focus")
        self.assertFalse(outcome["ok"])
        self.assertFalse(outcome["entry_ok"])
        self.assertEqual(outcome["status"], "entry-failed")
        self.assertFalse(outcome["entry"]["verified"])

    def test_missing_escape_blocker_stays_explicit(self):
        outcome = capture.keyboard_outcome(True, False)
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["escape"]["blocker"], "Escape was not verified")


class KeyboardTargetTests(unittest.TestCase):
    app = "/Applications/Herdr.app/Contents/MacOS/Herdr"

    def test_isolated_process_is_the_only_target(self):
        command = capture.verify_escape_target(4242, self.app, {4242: self.app}, set())
        self.assertEqual(command, self.app)

    def test_existing_herdr_process_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "another Herdr process"):
            capture.verify_escape_target(4242, self.app, {4242: self.app}, {4242})

    def test_other_executable_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not the selected isolated host"):
            capture.verify_escape_target(4242, self.app, {4242: "/tmp/Herdr"}, set())

    def test_missing_process_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "is not running"):
            capture.verify_escape_target(4242, self.app, {}, set())

    def test_ps_prose_naming_herdr_is_not_a_process(self):
        output = (" 4242 /Applications/Herdr.app/Contents/MacOS/Herdr\n"
                  " 9001 opencode --prompt 'Herdr migration notes'\n"
                  " 9002 herdr-app status\n")
        self.assertEqual(capture.herdr_process_ids(output), {4242, 9002})


if __name__ == "__main__":
    unittest.main()
