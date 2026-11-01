import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("app_setup", ROOT / "scripts/app-setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-jira-setup-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "data/jira-peek/connection"
        self.payload = {"base": "https://example.atlassian.net/", "email": "tester@example.invalid",
                        "token": "fictional_token_value-123", "projects": "ABC,XYZ", "cloudId": ""}

    def call(self, *args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/app-setup.py"), *map(str, args)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, 0)
        value = json.loads(result.stdout)
        self.assertEqual(set(value) >= {"ok"}, True)
        return value, result.stdout

    def make_root(self, mode=0o700):
        for path in (self.home / "data", self.home / "data/jira-peek"):
            if not path.exists():
                path.mkdir(mode=0o700)
        if not self.root.exists():
            self.root.mkdir(mode=mode)

    def prepare(self):
        report, _ = self.call("inspect", self.root)
        return self.call("prepare", self.root, report["revision"])[0]

    def submit(self, ticket, payload=None):
        request = self.root / ".setup-pending" / ticket / "request.json"
        request.write_text(json.dumps(payload or self.payload))
        request.chmod(0o600)
        return request

    def fake_curl(self, code="200", body='{"accountId":"fictional-account"}', exit_code=0):
        path = self.home / "curl-fixture"
        path.write_text("#!/usr/bin/env python3\n"
                        "import json, os, sys\n"
                        "args=sys.argv[1:]\n"
                        f"open({str(self.home / 'argv.json')!r}, 'w').write(json.dumps(args))\n"
                        "out=args[args.index('-o')+1]\n"
                        f"open(out, 'w').write({body!r})\n"
                        f"print({code!r}, end='')\n"
                        f"sys.exit({exit_code})\n")
        path.chmod(0o700)
        return path

    def activate_fixture(self, curl):
        os.environ["CURL_BIN_PATH"] = str(curl)
        self.addCleanup(os.environ.pop, "CURL_BIN_PATH", None)

    def test_inspect_missing_is_read_only_and_prepare_files_are_private(self):
        report, _ = self.call("inspect", self.root)
        self.assertEqual(report, {"ok": True, "revision": "missing", "configured": False,
                                  "settings": {"base": "", "email": "", "projects": "", "cloudId": ""}})
        self.assertFalse(self.root.exists())
        ticket = self.prepare()
        self.assertRegex(ticket["ticket"], r"^[0-9a-f]{48}$")
        request = Path(ticket["path"])
        self.assertEqual(request.read_bytes(), b"")
        self.assertEqual(stat.S_IMODE(request.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(request.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(request.parent.parent.stat().st_mode), 0o700)
        for parent in (self.home / "data", self.home / "data/jira-peek", self.root, self.root / ".setup-pending"):
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root / ".setup-lock").stat().st_mode), 0o600)
        self.assertFalse(Path(ticket["path"]).is_symlink())

    def test_prepare_reaps_only_old_owned_submission_files(self):
        pending = self.root / ".setup-pending"
        self.make_root()
        pending.mkdir(mode=0o700)
        expired = pending / ("a" * 48); expired.mkdir(mode=0o700)
        for name, data in (("request.json", b""), ("revision", b"missing")):
            path = expired / name; path.write_bytes(data); path.chmod(0o600)
        old = time.time() - 2 * 24 * 60 * 60
        os.utime(expired, (old, old))
        foreign = pending / ("b" * 48); foreign.mkdir(mode=0o700)
        extra = foreign / "keep.txt"; extra.write_text("fictional local data"); extra.chmod(0o600)
        os.utime(foreign, (old, old))
        ticket = self.prepare()
        self.assertFalse(expired.exists())
        self.assertEqual(extra.read_text(), "fictional local data")
        self.assertTrue((self.root / ".setup-pending" / ticket["ticket"]).is_dir())

    def test_save_verifies_then_activates_compatible_config_without_token_exposure(self):
        self.make_root()
        (self.root / "config.sh").write_text("CACHE_TTL_MIN='0'\nPICKER_LAYOUT='top'\n")
        (self.root / "config.sh").chmod(0o600)
        ticket = self.prepare()
        self.submit(ticket["ticket"])
        curl = self.fake_curl()
        self.activate_fixture(curl)
        saved, output = self.call("save", self.root, ticket["ticket"])
        self.assertEqual(saved, {"ok": True})
        config = (self.root / "config.sh").read_text()
        self.assertIn("JIRA_BACKEND='rest'", config)
        self.assertIn("JIRA_PROJECTS='ABC|XYZ'", config)
        self.assertIn("CACHE_TTL_MIN='0'", config)
        self.assertNotIn(self.payload["token"], config + output)
        settings = self.call("inspect", self.root)[0]["settings"]
        self.assertEqual(settings["email"], self.payload["email"])
        auth_path = Path(next(line.split("=", 1)[1].strip("'\"") for line in config.splitlines() if line.startswith("JIRA_NETRC_FILE=")))
        auth = auth_path.read_text()
        self.assertIn(self.payload["token"], auth)
        self.assertEqual(stat.S_IMODE(auth_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(auth_path.parent.stat().st_mode), 0o700)
        self.assertNotIn(self.payload["token"], (self.home / "argv.json").read_text())
        argv = json.loads((self.home / "argv.json").read_text())
        self.assertNotIn(self.payload["token"], argv)
        self.assertFalse((self.root / ".setup-pending" / ticket["ticket"]).exists())

    def test_validation_failures_never_call_curl_or_replace_active_config(self):
        self.make_root()
        config = self.root / "config.sh"
        config.write_text("JIRA_BACKEND='rest'\nJIRA_BASE='https://old.example.invalid'\nJIRA_PROJECTS='OLD'\nJIRA_NETRC_FILE='/fictional/old.netrc'\nJIRA_CLOUD_ID=''\n")
        config.chmod(0o600)
        original = config.read_bytes()
        self.activate_fixture(self.fake_curl())
        cases = [("base", "https://user:pass@example.invalid", "invalid_site"),
                 ("base", "https://example.atlassian.net.evil.invalid", "invalid_site"),
                 ("base", "https://not-atlassian.invalid", "invalid_site"),
                 ("base", "https://192.0.2.1", "invalid_site"),
                 ("base", "https://example.atlassian.net:443", "invalid_site"),
                 ("email", "bad\nnetrc", "invalid_email"), ("projects", "ABC|bad;touch", "invalid_projects"),
                 ("token", "contains whitespace", "invalid_token"), ("cloudId", "../unsafe", "invalid_cloud_id")]
        for key, value, code in cases:
            with self.subTest(field=key):
                ticket = self.prepare()
                data = dict(self.payload); data[key] = value
                self.submit(ticket["ticket"], data)
                result, output = self.call("save", self.root, ticket["ticket"])
                self.assertEqual(result, {"ok": False, "error": code})
                self.assertNotIn(value, output)
                self.assertEqual(config.read_bytes(), original)
                self.assertFalse((self.root / ".setup-pending" / ticket["ticket"]).exists())
        self.assertFalse((self.home / "argv.json").exists())

    def test_http_failures_preserve_config_and_remove_candidate_credential(self):
        self.make_root()
        auth_dir = self.root / ".credentials"; auth_dir.mkdir(mode=0o700)
        prior_auth = auth_dir / (".auth-" + "a" * 48 + ".netrc")
        prior_auth.write_text("# herdr-jira-peek-managed:" + "a" * 48 + "\n" +
                              "machine old.example.invalid login old@example.invalid password fictional_prior_token\n")
        prior_auth.chmod(0o600)
        config = self.root / "config.sh"
        config.write_text(f"JIRA_BACKEND='rest'\nJIRA_BASE='https://old.example.invalid'\nJIRA_PROJECTS='OLD'\nJIRA_NETRC_FILE='{prior_auth}'\nJIRA_CLOUD_ID=''\n")
        config.chmod(0o600)
        original = config.read_bytes()
        for code, expected in (("401", "authentication_failed"), ("403", "permission_denied"), ("429", "rate_limited"), ("500", "connection_failed")):
            with self.subTest(status=code):
                ticket = self.prepare(); self.submit(ticket["ticket"])
                self.activate_fixture(self.fake_curl(code=code))
                result, output = self.call("save", self.root, ticket["ticket"])
                self.assertEqual(result, {"ok": False, "error": expected})
                self.assertNotIn(self.payload["token"], output)
                self.assertEqual(config.read_bytes(), original)
                self.assertTrue(prior_auth.is_file())
                self.assertEqual(list((self.root / ".credentials").glob(".auth-*.netrc")), [prior_auth])

    def test_stale_ticket_and_concurrent_lock_do_not_activate(self):
        ticket = self.prepare()
        self.submit(ticket["ticket"])
        self.root.joinpath("config.sh").write_text("CACHE_TTL_MIN='5'\n")
        self.root.joinpath("config.sh").chmod(0o600)
        stale, _ = self.call("save", self.root, ticket["ticket"])
        self.assertEqual(stale, {"ok": False, "error": "config_changed"})
        self.assertFalse((self.root / ".credentials").exists())


    def test_cancel_is_idempotent_and_rejects_arbitrary_ticket_paths(self):
        ticket = self.prepare()
        self.assertEqual(self.call("cancel", self.root, ticket["ticket"])[0], {"ok": True})
        self.assertEqual(self.call("cancel", self.root, ticket["ticket"])[0], {"ok": True})
        outside = self.home / "keep"
        outside.write_text("preserve")
        result, _ = self.call("cancel", self.root, "../../keep")
        self.assertEqual(result["ok"], False)
        self.assertEqual(outside.read_text(), "preserve")

    def test_atomic_request_replacement_must_remain_private_and_unlinked(self):
        self.activate_fixture(self.fake_curl())
        for attack in ("mode", "symlink", "hardlink"):
            with self.subTest(attack=attack):
                ticket = self.prepare()
                request = self.submit(ticket["ticket"])
                if attack == "mode":
                    replacement = request.with_name("replacement")
                    replacement.write_text(json.dumps(self.payload)); replacement.chmod(0o644)
                    os.replace(replacement, request)
                elif attack == "symlink":
                    request.unlink(); request.symlink_to(self.home / "outside-request")
                else:
                    os.link(request, self.home / "request-hardlink")
                result, _ = self.call("save", self.root, ticket["ticket"])
                self.assertEqual(result, {"ok": False, "error": "unsafe_path"})
        self.assertFalse((self.home / "argv.json").exists())

    def test_unsupported_config_is_rejected_without_execution_or_replacement(self):
        self.make_root()
        marker = self.home / "should-not-exist"
        config = self.root / "config.sh"
        config.write_text(f"CACHE_TTL_MIN='5'\nprintf hacked > '{marker}'\n")
        config.chmod(0o600)
        original = config.read_bytes()
        report, _ = self.call("inspect", self.root)
        self.assertEqual(report, {"ok": False, "error": "unsafe_path"})
        self.assertFalse(marker.exists())
        self.assertEqual(config.read_bytes(), original)

    def test_destination_normalizes_case_and_email_apostrophe_round_trips(self):
        ticket = self.prepare()
        data = dict(self.payload, base="HTTPS://Fictional-Peek.ATLASSIAN.NET/", email="o'brien@example.invalid")
        self.submit(ticket["ticket"], data)
        self.activate_fixture(self.fake_curl())
        result, _ = self.call("save", self.root, ticket["ticket"])
        self.assertEqual(result, {"ok": True})
        report = self.call("inspect", self.root)[0]
        self.assertEqual(report["settings"]["base"], "https://fictional-peek.atlassian.net")
        self.assertEqual(report["settings"]["email"], "o'brien@example.invalid")

    def test_existing_insecure_directories_are_rejected_without_chmod(self):
        self.make_root(mode=0o755)
        self.root.chmod(0o755)
        result, _ = self.call("prepare", self.root, "missing")
        self.assertEqual(result, {"ok": False, "error": "unsafe_path"})
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)

    def test_host_data_parents_can_be_readable_but_not_writable_by_other_users(self):
        self.make_root()
        for parent in (self.root.parent, self.root.parent.parent):
            parent.chmod(0o755)
        prepared, _ = self.call("prepare", self.root, "missing")
        self.assertTrue(prepared["ok"])
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.call("cancel", self.root, prepared["ticket"])
        self.root.parent.chmod(0o777)
        rejected, _ = self.call("prepare", self.root, "missing")
        self.assertEqual(rejected, {"ok": False, "error": "unsafe_path"})
        self.assertEqual(stat.S_IMODE(self.root.parent.stat().st_mode), 0o777)

    def test_flock_is_released_on_process_death_and_cancel_waits_for_saver(self):
        ticket = self.prepare(); self.submit(ticket["ticket"])
        expired = self.root / ".setup-pending" / ("d" * 48)
        expired.mkdir(mode=0o700)
        for name, data in (("request.json", b""), ("revision", b"missing")):
            path = expired / name; path.write_bytes(data); path.chmod(0o600)
        old = time.time() - 2 * 24 * 60 * 60
        os.utime(expired, (old, old))
        child_code = ("import importlib.util, pathlib, time; "
                      f"s=importlib.util.spec_from_file_location('setup', {str(ROOT / 'scripts/app-setup.py')!r}); "
                      "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                      f"fd=m.acquire_lock(pathlib.Path({str(self.root)!r})); print('locked', flush=True); time.sleep(60)")
        child = subprocess.Popen([sys.executable, "-c", child_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(child.stdout.readline().strip(), "locked")
        busy, _ = self.call("cancel", self.root, ticket["ticket"])
        self.assertEqual(busy, {"ok": False, "error": "config_changed"})
        self.assertTrue((self.root / ".setup-pending" / ticket["ticket"]).exists())
        current_revision = self.call("inspect", self.root)[0]["revision"]
        prepare_busy, _ = self.call("prepare", self.root, current_revision)
        self.assertEqual(prepare_busy, {"ok": False, "error": "config_changed"})
        self.assertTrue(expired.exists())
        child.kill(); child.wait(timeout=5)
        child.stdout.close(); child.stderr.close()
        self.assertEqual(self.call("cancel", self.root, ticket["ticket"])[0], {"ok": True})
        next_ticket = self.call("prepare", self.root, current_revision)[0]
        self.assertFalse(expired.exists())
        self.assertEqual(self.call("cancel", self.root, next_ticket["ticket"])[0], {"ok": True})

    def test_commit_point_failure_semantics(self):
        self.make_root()
        auth_dir = self.root / ".credentials"; auth_dir.mkdir(mode=0o700)
        old = auth_dir / (".auth-" + "c" * 48 + ".netrc")
        old.write_text("# herdr-jira-peek-managed:" + "c" * 48 + "\n" +
                       'machine old.example.invalid login "old@example.invalid" password "fictional_old"\n')
        old.chmod(0o600)
        config = self.root / "config.sh"
        config.write_text(f"JIRA_BACKEND='rest'\nJIRA_BASE='https://old.example.invalid'\nJIRA_PROJECTS='OLD'\nJIRA_NETRC_FILE='{old}'\nJIRA_CLOUD_ID=''\n")
        config.chmod(0o600)
        original = config.read_bytes()
        ticket = self.prepare(); self.submit(ticket["ticket"])
        self.activate_fixture(self.fake_curl())
        with mock.patch.object(setup.os, "replace", side_effect=OSError("fictional precommit failure")):
            with self.assertRaises(OSError):
                setup.save(self.root, ticket["ticket"])
        self.assertEqual(config.read_bytes(), original)
        self.assertTrue(old.exists())
        self.assertEqual(list(auth_dir.glob(".auth-*.netrc")), [old])

        ticket = self.prepare(); self.submit(ticket["ticket"])
        with mock.patch.object(setup, "cleanup_managed_credentials", side_effect=OSError("fictional postcommit cleanup failure")):
            result = setup.save(self.root, ticket["ticket"])
        self.assertEqual(result, {"ok": True})
        self.assertNotEqual(config.read_bytes(), original)
        self.assertTrue(Path(next(line.split("=", 1)[1].strip("'\"") for line in config.read_text().splitlines() if line.startswith("JIRA_NETRC_FILE="))).is_file())

    def test_symlink_hardlink_git_checkout_and_permission_attacks_are_rejected(self):
        outside = self.home / "outside"; outside.mkdir(mode=0o700)
        linked = self.home / "link"; linked.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.call("inspect", linked)[0], {"ok": False, "error": "unsafe_path"})

        self.make_root()
        config = self.root / "config.sh"; config.write_text("CACHE_TTL_MIN='5'\n"); config.chmod(0o600)
        hardlink = self.home / "hardlink"; os.link(config, hardlink)
        self.assertEqual(self.call("inspect", self.root)[0], {"ok": False, "error": "unsafe_path"})
        hardlink.unlink()
        config.chmod(0o644)
        self.assertEqual(self.call("inspect", self.root)[0], {"ok": False, "error": "unsafe_path"})
        config.unlink()

        checkout = self.home / "checkout"; checkout.mkdir(); (checkout / ".git").mkdir()
        self.assertEqual(self.call("inspect", checkout / "connection")[0], {"ok": False, "error": "unsafe_path"})

    def test_cloud_id_routes_to_api_host_and_token_validation_rejects_netrc_controls(self):
        ticket = self.prepare()
        data = dict(self.payload); data["cloudId"] = "fictional-cloud-123"
        self.submit(ticket["ticket"], data)
        curl = self.fake_curl(); self.activate_fixture(curl)
        saved, _ = self.call("save", self.root, ticket["ticket"])
        self.assertEqual(saved, {"ok": True})
        argv = json.loads((self.home / "argv.json").read_text())
        self.assertIn("https://api.atlassian.com/ex/jira/fictional-cloud-123/rest/api/3/myself", argv)
        self.assertIn("api.atlassian.com", Path(argv[argv.index("--netrc-file") + 1]).read_text())

    def test_successful_replacement_removes_only_the_previous_managed_credential(self):
        self.make_root()
        auth_dir = self.root / ".credentials"; auth_dir.mkdir(mode=0o700)
        old = auth_dir / (".auth-" + "b" * 48 + ".netrc")
        old.write_text("# herdr-jira-peek-managed:" + "b" * 48 + "\n" +
                       'machine old.example.invalid login "old@example.invalid" password "fictional_old_token"\n')
        old.chmod(0o600)
        foreign = auth_dir / "user-owned.netrc"
        foreign.write_text("machine safe.example.invalid login safe@example.invalid password fictional_keep\n")
        foreign.chmod(0o600)
        config = self.root / "config.sh"
        config.write_text(f"JIRA_BACKEND='rest'\nJIRA_BASE='https://old.example.invalid'\nJIRA_PROJECTS='OLD'\nJIRA_NETRC_FILE='{old}'\nJIRA_CLOUD_ID=''\n")
        config.chmod(0o600)
        ticket = self.prepare(); self.submit(ticket["ticket"])
        self.activate_fixture(self.fake_curl())
        result, _ = self.call("save", self.root, ticket["ticket"])
        self.assertEqual(result, {"ok": True})
        self.assertFalse(old.exists())
        self.assertEqual(foreign.read_text().splitlines()[0], "machine safe.example.invalid login safe@example.invalid password fictional_keep")


if __name__ == "__main__":
    unittest.main()
