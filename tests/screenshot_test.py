"""Offline host selection/provenance checks; never launch the desktop app."""
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
