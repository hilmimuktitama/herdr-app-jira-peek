"""Standalone Rust cache clearing against fictional in-flight REST requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))
from fixture import Fixture

BINARY = Path(os.environ.get("JIRA_PEEK_RUST_BINARY", ROOT / "rust-backend/target/release/jira-peek-bridge")).resolve()


class StandaloneClear(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-rust-clear-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = Fixture(self.root)
        self.addCleanup(self.fixture.close)
        self.config = self.root / "config"
        self.config.mkdir()
        self.netrc = self.root / "fictional.netrc"
        self.netrc.write_text("machine jira.example.test login fictional password fictional\n")
        self.netrc.chmod(0o600)
        self.state = self.root / "state"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("HERDR_", "HC_", "JIRA_PEEK_", "CURL_", "SSL_", "TWG_"))
                    and "proxy" not in k.lower()}
        self.env.update(PATH="/nonexistent/fictional", HOME=str(self.root),
                        JIRA_PEEK_FIXTURE_HTTP=self.fixture.url)
        info = json.loads(subprocess.check_output([str(BINARY), "--build-info"], env=self.env, text=True))
        self.assertIs(info["fixtureTransport"], True, "Use an isolated fixture-http binary")

    def command(self, operation, *args):
        return [str(BINARY), operation, str(self.config), str(self.state), *args]

    def call(self, operation, *args):
        result = subprocess.run(self.command(operation, *args), env=self.env, capture_output=True,
                                text=True, check=True, timeout=15)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def connect(self, ttl=10):
        (self.config / "config.sh").write_text(
            "JIRA_BASE='https://jira.example.test'\nJIRA_BACKEND='rest'\nJIRA_PROJECTS='ABC'\n"
            f"JIRA_NETRC_FILE='{self.netrc}'\nCACHE_TTL_MIN='{ttl}'\n")
        result = self.call("config")
        self.assertTrue(result["ok"])
        namespace, = (self.state / "connections").iterdir()
        return result["context"], namespace

    def clear(self, path, check=True):
        return subprocess.run([str(BINARY), "manage", "clear-cache", "--state-dir", str(path)],
                              env=self.env, text=True, capture_output=True, timeout=15, check=check)

    def test_clear_without_cache_retires_late_response_for_both_ttls(self):
        for ttl in (0, 10):
            with self.subTest(ttl=ttl):
                context, namespace = self.connect(ttl)
                config_before = (self.config / "config.sh").read_bytes()
                auth_before = self.netrc.read_bytes()
                marker_before = (namespace / "connection-context").read_bytes()
                (namespace / "key").write_text("ABC-1\n")
                entered, release = threading.Event(), threading.Event()
                def hook(call):
                    if call["kind"] == "issue":
                        entered.set()
                        if not release.wait(10): return 503, {}
                    return None
                self.fixture.hook = hook
                child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(entered.wait(5))
                    cache = namespace / "cache"
                    cache.rmdir()
                    requests = len(self.fixture.calls)
                    result = self.clear(namespace)
                    self.assertEqual(result.stderr, "")
                    self.assertIn("already empty", result.stdout)
                    self.assertEqual(len(self.fixture.calls), requests)
                    self.assertFalse(cache.exists())
                    cache.mkdir()
                    release.set()
                    stdout, stderr = child.communicate(timeout=10)
                    self.assertEqual(stderr, "")
                    self.assertEqual(json.loads(stdout), {"ok": False, "error": "connection_changed"})
                    self.assertFalse((cache / "ABC-1.json").exists())
                    self.assertNotEqual((namespace / "connection-context").read_bytes(), marker_before)
                    self.assertEqual((self.config / "config.sh").read_bytes(), config_before)
                    self.assertEqual(self.netrc.read_bytes(), auth_before)
                    self.assertEqual((namespace / "key").read_text(), "ABC-1\n")
                finally:
                    release.set()
                    if child.poll() is None:
                        child.kill()
                        child.communicate()

    def test_shared_root_is_rejected_and_missing_state_stays_absent(self):
        context, namespace = self.connect()
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        marker = (namespace / "connection-context").read_bytes()
        cache = (namespace / "cache/ABC-1.json").read_bytes()
        result = self.clear(self.state, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("select a connection", result.stderr)
        self.assertEqual((namespace / "connection-context").read_bytes(), marker)
        self.assertEqual((namespace / "cache/ABC-1.json").read_bytes(), cache)
        self.assertFalse((self.state / "connection-context").exists())
        missing = self.root / "missing"
        self.assertEqual(self.clear(missing).stderr, "")
        self.assertFalse(missing.exists())

    def test_only_regular_cache_entries_are_removed(self):
        _, namespace = self.connect()
        cache = namespace / "cache"
        (cache / "ABC-1.json").write_text("fictional")
        (cache / ".pending.fixture").write_text("fictional")
        (cache / "nested").mkdir()
        (cache / "nested/keep").write_text("fictional")
        (cache / "link").symlink_to(self.netrc)
        result = self.clear(namespace)
        self.assertIn("cleared 2", result.stdout)
        self.assertTrue((cache / "nested/keep").exists())
        self.assertTrue((cache / "link").is_symlink())
        self.assertTrue(self.netrc.exists())


if __name__ == "__main__":
    unittest.main()
