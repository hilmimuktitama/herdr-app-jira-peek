import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


bundle = module("release_assets_bundle", "runtime-bundle.py")
assets = module("release_assets_verifier", "verify-release-assets.py")


class ReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-release-assets-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.version = json.loads((ROOT / "package.json").read_text())["version"]
        self.source = bundle.source_digest(ROOT / "rust-backend")
        for platform in assets.PLATFORMS:
            self.write_platform(platform)

    def write_platform(self, platform, source=None, version=None, platform_name=None):
        binary = f"jira-peek-bridge-{platform}"
        payloads = {binary: f"binary {platform}".encode(), binary + "-NOTICES.txt": b"notices\n"}
        files = {}
        for name, payload in payloads.items():
            (self.root / name).write_bytes(payload)
            files[name] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        manifest = {
            "format": 1,
            "releaseVersion": version or self.version,
            "platform": platform_name or platform,
            "sourceSha256": source or self.source,
            "buildInfo": {"fixtureTransport": False, "protocol": 1},
            "files": files,
        }
        (self.root / (binary + ".json")).write_text(json.dumps(manifest))

    def manifest_path(self, platform="linux-aarch64"):
        return self.root / f"jira-peek-bridge-{platform}.json"

    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return assets.verify(self.root, self.version)

    def test_verifies_the_complete_set(self):
        self.assertEqual(self.verify(), self.source)

    def test_rejects_missing_and_extra_files(self):
        (self.root / "jira-peek-bridge-linux-aarch64").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.verify()
        self.write_platform("linux-aarch64")
        (self.root / "checksums.txt").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.verify()

    def test_rejects_changed_bytes(self):
        path = self.root / "jira-peek-bridge-linux-aarch64"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "size|checksum"):
            self.verify()

    def test_rejects_wrong_manifest_identity(self):
        original = self.manifest_path().read_text()
        for field, value in (("releaseVersion", "0.0.0"), ("platform", "macos-aarch64"),
                             ("sourceSha256", "0" * 64)):
            self.manifest_path().write_text(original)
            manifest = json.loads(self.manifest_path().read_text())
            manifest[field] = value
            self.manifest_path().write_text(json.dumps(manifest))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "does not match|source digest"):
                self.verify()
        self.manifest_path().write_text(original)

    def test_rejects_fixture_build_and_split_source_digest(self):
        original = self.manifest_path().read_text()
        manifest = json.loads(original)
        manifest["buildInfo"]["fixtureTransport"] = True
        self.manifest_path().write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.verify()
        self.manifest_path().write_text(original)
        self.write_platform("macos-aarch64", source="1" * 64)
        with self.assertRaisesRegex(ValueError, "source digest"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
