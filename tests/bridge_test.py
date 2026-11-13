"""Offline adapter contracts. Every identity, host, and issue is fictional."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts/app-bridge.sh"
FAKE_TWG = r'''#!/usr/bin/env python3
import json, os, pathlib, re, sys, time
root = pathlib.Path(os.environ["APP_TEST_ROOT"])
with (root / "calls").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
if "whoami" in sys.argv:
    print(json.dumps({"accountId": "fictional-reader"})); sys.exit(0)
if os.environ.get("APP_TEST_TWG_ERROR"):
    print(os.environ["APP_TEST_TWG_ERROR"])
    print(os.environ.get("APP_TEST_TWG_STDERR", ""), file=sys.stderr)
    sys.exit(int(os.environ.get("APP_TEST_TWG_EXIT", "1")))
if (root / "fail").exists():
    print("FICTIONAL_RAW_RESPONSE_SENTINEL", file=sys.stderr); sys.exit(7)
if (root / "block").exists() and not os.environ.get("APP_TEST_SKIP_BLOCK"):
    (root / "started").touch()
    for _ in range(500):
        if not (root / "block").exists(): break
        time.sleep(.01)
keys = [arg for arg in sys.argv if re.fullmatch(r"ABC-\d+", arg)]
def issue(key):
    if (root / "batch.json").exists(): return {**json.loads((root / "batch.json").read_text()), "key":key}
    if (root / "override.json").exists(): return json.loads((root / "override.json").read_text())
    return {"key":key, "fields":{
      "summary":os.environ.get("APP_TEST_SUMMARY", "Fictional catalog filters"), "status":{"name":"In Progress"},
      "assignee":{"displayName":"Alex Example", "accountId":"PRIVATE_METADATA_SENTINEL"},
      "customfield_10016":5,
      "description":{"type":"doc","content":[{"type":"paragraph","content":[
        {"type":"text","text":"Keep filters.\u001b","marks":[{"type":"link","attrs":{"href":"https://untrusted.example.test"}}]},
        {"type":"media","attrs":{"url":"https://image.example.test", "id":"PRIVATE_METADATA_SENTINEL"}}
      ]}]},
      "comments":[{"author":{"displayName":"Sam Sample","accountId":"PRIVATE_METADATA_SENTINEL"},"created":"2026-10-31T10:00:00Z","body":"Looks good."}]}}
if len(keys) == 1: print(json.dumps({"data":issue(keys[0])}))
else: print(json.dumps({"data":{"items":[{"ok":True,"data":issue(k)} for k in keys + ["FOREIGN-9"]]}}))
'''


FAKE_REST = r'''#!/usr/bin/env python3
import json,os,pathlib,re,sys
from urllib.parse import urlsplit,parse_qs
root=pathlib.Path(os.environ["APP_TEST_ROOT"])
args=sys.argv[1:]; url=urlsplit(args[-1]); query=parse_qs(url.query)
out=pathlib.Path(args[args.index("-o")+1])
mode=os.environ.get("APP_TEST_REST_MODE") or ((root/"rest-mode").read_text() if (root/"rest-mode").exists() else "ok")
kind="site" if url.path.endswith("/_edge/tenant_info") else "comments" if url.path.endswith("/comment") else "metadata" if url.path.endswith("/bulkfetch") else "issue"
key=re.search(r"ABC-\d+",url.path).group(0) if "ABC-" in url.path else "ABC-1"
with (root/"rest-calls").open("a") as f: f.write(json.dumps({"kind":kind,"key":key,"query":query})+"\n")
code="200"
if kind=="site":
    assert "--netrc-file" not in args and "--no-netrc" in args
    body={"cloudId":"fictional-cloud-123" if mode!="site-mismatch" else "another-fictional-cloud"}
elif kind=="comments":
    count=100; total=205
    body={"startAt":0,"maxResults":100,"total":total,"comments":[
      {"author":{"displayName":"Fictional Reader","accountId":"PRIVATE_METADATA_SENTINEL"},
       "body":"Fictional recent comment "+str(total-i)} for i in range(count)]}
    if mode=="comments-denied": code="403"; body={"errorMessages":["FICTIONAL_RAW_RESPONSE_SENTINEL"]}
    if mode=="comments-malformed": body={"startAt":0,"total":205,"comments":[]}
elif kind=="metadata": body={"issues":[]}
else:
    body={"key":key,"fields":{"summary":"Fictional immediate context","description":"Core description", "status":{"name":"Open"}}}
    if key=="ABC-2" and mode in ("issue-denied","issue-unauthorized"):
        code="403" if mode=="issue-denied" else "401"; body={"errorMessages":["FICTIONAL_RAW_RESPONSE_SENTINEL"]}
if kind in ("metadata", "issue") and (root/"override.json").exists():
    issue=json.loads((root/"override.json").read_text())
    body={"issues":[issue]} if kind=="metadata" else issue
out.write_text(json.dumps(body)); print(code,end="")
'''


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="peek-app-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config"; self.config.mkdir()
        self.state_root = self.root / "state"
        self.state = self.config_state(self.config)
        binary = self.root / "twg"; binary.write_text(FAKE_TWG); binary.chmod(0o700)
        self.env = {key:value for key,value in os.environ.items() if not key.startswith(("HERDR_", "VIEWER_", "TWG_", "CURL_", "SSL_", "JIRA_PEEK_"))}
        self.env.update(TWG_BIN_PATH=str(binary), APP_TEST_ROOT=str(self.root))
        self.write_config()

    def write_config(self, extra=""):
        (self.config / "config.sh").write_text(
            "JIRA_BASE='https://jira.example.test'\nJIRA_SITE='jira-example'\nJIRA_PROJECTS='ABC'\n"
            "READER_FIELDS='status,assignee,customfield_10016,description,comments'\n"
            "FIELD_LABELS='customfield_10016:Points'\n" + extra)

    def config_state(self, directory):
        info = directory.stat()
        identity = f'directory-v1:{info.st_dev}:{info.st_ino}'
        return self.state_root / 'connections' / hashlib.sha256(identity.encode()).hexdigest()

    def command(self, op, *args):
        return ["sh", str(getattr(self, "bridge", BRIDGE)), op, str(self.config), str(self.state_root), *args]

    def pause_runtime(self, filename, boundary):
        """Insert a bounded barrier in a disposable runtime, never production hooks."""
        runtime = self.root / "runtime"
        shutil.copytree(ROOT / "scripts", runtime)
        path = runtime / filename
        source = path.read_text()
        self.assertEqual(source.count(boundary), 1)
        barrier = '''
    if [ "${APP_TEST_PAUSE:-}" = yes ]; then
      : > "$APP_TEST_ROOT/boundary"
      wait_count=0
      while [ ! -f "$APP_TEST_ROOT/release" ]; do
        wait_count=$((wait_count + 1)); [ "$wait_count" -lt 1000 ] || exit 13
        sleep 0.01
      done
    fi
'''
        path.write_text(source.replace(boundary, barrier + boundary))
        self.bridge = runtime / "app-bridge.sh"

    def wait_boundary(self, child):
        for _ in range(500):
            if (self.root / "boundary").exists(): return
            if child.poll() is not None: break
            time.sleep(.01)
        self.fail("Fictional request did not reach the barrier")

    def test_legacy_cleanup_preserves_live_owners_links_and_known_diagnostics(self):
        self.connect()
        dead="999999999";live=str(os.getpid())
        stale=[self.state/f"{prefix}.{dead}.fixture" for prefix in
            (".identity", ".twg-json", ".twg-stderr", ".twg-normalized", ".twg-error", ".issue-app-projection", ".connection", ".site-context", ".connection-owner")]
        for path in stale: path.write_text("Fictional abandoned payload")
        active=self.state/f".twg-json.{live}.fixture";active.write_text("Fictional active payload")
        outside=self.root/"outside";outside.mkdir();keep=outside/"keep";keep.write_text("Fictional outside payload")
        linked=self.state/f".twg-json.{dead}.link";linked.symlink_to(keep)
        stale_dir=self.state/f".rest-fetch.{dead}.fixture";stale_dir.mkdir()
        (stale_dir/"body").write_text("Fictional raw transport")
        (stale_dir/"external").symlink_to(outside,target_is_directory=True)
        active_dir=self.state/f".rest-metadata.{live}.fixture";active_dir.mkdir()
        (active_dir/"body").write_text("Fictional active transport")
        diagnostic=self.state/"session-fictional/fetch-errors";diagnostic.mkdir(parents=True)
        (diagnostic/"fetch-error-ABC-1").write_text("Fictional obsolete raw details")
        (diagnostic/"fetch-error-ABC-2").write_text("Jira request failed\n")
        (self.state/"fetch-errors"/f".fetch-error-ABC-1.{dead}.fixture").write_text("Fictional abandoned diagnostic")
        self.assertTrue(self.call("config")["ok"])
        self.assertTrue(all(not p.exists() for p in stale))
        self.assertFalse(stale_dir.exists());self.assertFalse((diagnostic/"fetch-error-ABC-1").exists())
        self.assertEqual((diagnostic/"fetch-error-ABC-2").read_text(),"Jira request failed\n")
        self.assertTrue(active.exists());self.assertTrue(active_dir.exists());self.assertTrue(linked.is_symlink())
        self.assertEqual(keep.read_text(),"Fictional outside payload")

    def test_account_change_retires_legacy_source_keys_but_keeps_other_files(self):
        self.connect()
        dirs=[self.state,self.state/"sources/source-fictional",self.state/"session-fictional",self.state/"session-fictional/sources/source-fictional"]
        for directory in dirs:
            directory.mkdir(parents=True,exist_ok=True)
            for name in ("key","candidates","unrelated"): (directory/name).write_text("ABC-1 fictional")
        (self.root/"twg").write_text(FAKE_TWG.replace('fictional-reader','fictional-other-reader'))
        self.assertTrue(self.call("config")["ok"])
        for directory in dirs:
            self.assertFalse((directory/"key").exists());self.assertFalse((directory/"candidates").exists())
            self.assertTrue((directory/"unrelated").exists())

    def test_legacy_key_pattern_uses_platform_ere_validation(self):
        for pattern in (r"(ABC)-[0-9]+",r"(ABC)\1",r"[[:digit:]]+",r"(?=ABC)",r"[",r"\p{Greek}",
                        r")",r"(",r"*ABC",r"+ABC",r"A{",r"A{2,1}",r"A{0}",r"A{999999999999}",
                        r"\1",r"()\1",r"[z-a]",r"[.]",r"[[:bogus:]]",r"ABC|",r"{1}",r"(?:ABC)",r"(?i)ABC"):
            with self.subTest(pattern=pattern):
                expected=subprocess.run(["grep","-oE",pattern],input="\n",env={**self.env,"LC_ALL":"C"},text=True,capture_output=True).returncode!=2
                self.write_config("KEY_RE='"+pattern+"'\n")
                self.assertEqual(self.call("config")["ok"],expected)

    def test_auth_rejection_revokes_even_when_followup_identity_is_unavailable(self):
        twg = self.root / "twg"
        twg.write_text(FAKE_TWG.replace('if "whoami" in sys.argv:',
            'if "whoami" in sys.argv and (root / "identity-unavailable").exists(): sys.exit(1)\nif "whoami" in sys.argv:')
            .replace('keys = [arg for arg in sys.argv',
            'if "ABC-2" in sys.argv:\n    (root / "identity-unavailable").touch()\n    print("TWG authentication failed"); sys.exit(1)\nkeys = [arg for arg in sys.argv'))
        for operation in ("issue", "metadata"):
            with self.subTest(operation=operation):
                context = self.connect()
                self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
                marker = (self.state / "connection-context").read_bytes()
                self.assertFalse(self.call(operation, context, "ABC-2")["ok"])
                self.assertNotEqual((self.state / "connection-context").read_bytes(), marker)
                self.assertFalse((self.state / "cache/ABC-1.json").exists())
                (self.root / "identity-unavailable").unlink()
                self.assertEqual(self.call("issue", context, "ABC-1")["error"], "connection_changed")

    def test_config_directory_symlink_swap_retires_inflight_response(self):
        context = self.connect()
        (self.root / "block").touch()
        child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(500):
                if (self.root / "started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "started").exists())
            moved = self.root / "moved-config"
            self.config.rename(moved)
            self.config.symlink_to(moved, target_is_directory=True)
            (self.root / "block").unlink()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"ok":False,"error":"connection_changed"})
            self.assertFalse((self.state / "cache/ABC-1.json").exists())
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_empty_legacy_theme_and_label_separators_are_invalid(self):
        for extra in ("COLOR_THEME=''\n", "FIELD_LABELS=',status:State,'\n", "FIELD_LABELS='status:State,,assignee:Owner'\n"):
            with self.subTest(extra=extra):
                self.write_config(extra)
                self.assertEqual(self.call("config")["error"], "connection_failed")

    def test_old_denial_cannot_delete_newer_success_after_generation_check(self):
        self.use_rest()
        context = self.connect()
        self.pause_runtime("common.sh", '    json_error=$(mktemp "$STATE/.twg-error.$$.XXXXXX") || {')
        child = subprocess.Popen(self.command("issue", context, "ABC-2"),
            env={**self.env, "APP_TEST_PAUSE": "yes", "APP_TEST_REST_MODE": "issue-denied"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.wait_boundary(child)
            self.assertTrue(self.call("issue", context, "ABC-2")["ok"])
            cached = (self.state / "cache/ABC-2.json").read_bytes()
            generation = (self.state / "cache-generations/ABC-2").read_bytes()
            (self.root / "release").touch()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"ok": False, "error": "request_failed"})
            self.assertEqual((self.state / "cache/ABC-2.json").read_bytes(), cached)
            self.assertEqual((self.state / "cache-generations/ABC-2").read_bytes(), generation)
            self.assertFalse((self.state / "fetch-errors/fetch-error-ABC-2").exists())
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_projection_rejects_replaced_cache_with_another_field_signature(self):
        context = self.connect()
        self.pause_runtime("app-bridge.sh", '    f=$FETCHED_FILE\n')
        child = subprocess.Popen(self.command("issue", context, "ABC-1", "", "customfield_10017"),
            env={**self.env, "APP_TEST_PAUSE": "yes"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.wait_boundary(child)
            self.assertTrue(self.call("issue", context, "ABC-1", "", "priority")["ok"])
            (self.root / "release").touch()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"ok": False, "error": "request_failed"})
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def call(self, op, *args):
        result = subprocess.run(self.command(op, *args), env=self.env, text=True, capture_output=True, check=True)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("SENTINEL", result.stdout)
        return json.loads(result.stdout)

    def connect(self):
        result = self.call("config")
        self.assertTrue(result["ok"], result)
        return result["context"]

    def test_batch_and_detail_picker_projections_share_bounds_and_private_object_rules(self):
        for backend in ("twg", "rest"):
            with self.subTest(backend=backend):
                if backend == "rest":
                    self.use_rest()
                path = self.config / "config.sh"
                with path.open("a") as stream:
                    stream.write("PICKER_FIELDS='customfield_10016,customfield_10017,customfield_10018'\n")
                fields = {"summary": "Fictional " + "x" * 5000, "status": {"name": "Open"},
                          "customfield_10016": "x" * 25000,
                          "customfield_10017": {"id": "PRIVATE_METADATA_SENTINEL"},
                          "customfield_10018": "Visible\u202e text"}
                (self.root / "override.json").write_text(json.dumps({"key": "ABC-1", "fields": fields}))
                context = self.connect()
                row = self.call("metadata", context, "ABC-1")["rows"][0]
                issue = self.call("issue", context, "ABC-1")["issue"]
                self.assertEqual(row["summary"], issue["summary"])
                self.assertEqual(row["status"], issue["status"])
                self.assertEqual(row["values"], issue["values"])
                self.assertEqual(row["values"], ["x" * 4096, "", "Visible text"])

    def test_native_reads_leave_obsolete_viewer_state_untouched(self):
        self.connect()
        viewer = self.state / ".viewer.999999999.fixture"
        viewer.mkdir()
        marker = viewer / "keep"; marker.write_text("Fictional legacy viewer state")
        self.connect()
        self.assertEqual(marker.read_text(), "Fictional legacy viewer state")

    def test_large_metadata_batches_use_files_and_reject_oversized_output(self):
        keys = [f"ABC-{i}" for i in range(1, 101)]
        for count, accepted in ((4, True), (20, False)):
            with self.subTest(fields=count):
                fields = {f"customfield_{i}": "x" * 4096 for i in range(count)}
                self.write_config("MAX_CANDIDATES=100\nPICKER_FIELDS='" + ",".join(fields) + "'\n")
                (self.root / "batch.json").write_text(json.dumps({"fields": fields}))
                result = self.call("metadata", self.connect(), *keys)
                if accepted:
                    self.assertEqual([r["key"] for r in result["rows"]], keys)
                    self.assertTrue(all(len(row["values"]) == count for row in result["rows"]))
                else:
                    self.assertEqual(result, {"ok": False, "error": "request_failed"})

    def test_old_empty_cache_lock_is_recovered_but_recent_lock_is_preserved(self):
        context = self.connect()
        self.call("issue", context, "ABC-1")
        generation_dir, = self.state.glob("*generation*")
        lock = generation_dir / ".ABC-1.lock"
        lock.mkdir()
        old = time.time() - 180
        os.utime(lock, (old, old))
        self.assertTrue(self.call("issue", context, "ABC-1", "refresh")["ok"])
        self.assertFalse(lock.exists())
        # A fresh directory can belong to a process still publishing its owner.
        lock.mkdir()
        child = subprocess.Popen(self.command("issue", context, "ABC-1", "refresh"),
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(.15)
            self.assertIsNone(child.poll())
            self.assertTrue(lock.is_dir())
            lock.rmdir()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertTrue(json.loads(stdout)["ok"])
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_later_cache_miss_supersedes_slow_earlier_response(self):
        context = self.connect()
        (self.root / "block").touch()
        child = subprocess.Popen(self.command("issue", context, "ABC-1"),
            env={**self.env, "APP_TEST_SUMMARY": "Fictional earlier response"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(300):
                if (self.root / "started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "started").exists())
            latest = subprocess.run(self.command("issue", context, "ABC-1"),
                env={**self.env, "APP_TEST_SKIP_BLOCK": "1", "APP_TEST_SUMMARY": "Fictional later response"},
                capture_output=True, text=True, check=True, timeout=15)
            self.assertEqual(json.loads(latest.stdout)["issue"]["summary"], "Fictional later response")
            (self.root / "block").unlink()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout)["error"], "request_failed")
            self.assertEqual(self.call("issue", context, "ABC-1")["issue"]["summary"], "Fictional later response")
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_failed_later_attempt_still_retires_earlier_cache_response(self):
        context = self.connect()
        (self.root / "block").touch()
        child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(300):
                if (self.root / "started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "started").exists())
            (self.root / "fail").touch()
            self.assertEqual(self.call("issue", context, "ABC-1")["error"], "request_failed")
            (self.root / "fail").unlink()
            (self.root / "block").unlink()
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout)["error"], "request_failed")
            self.assertFalse((self.state / "cache/ABC-1.json").exists())
            self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_configurations_keep_independent_caches_epochs_and_pending_reads(self):
        first_config = self.config
        first_context = self.connect()
        (self.root / "block").touch()
        pending = subprocess.Popen(self.command("issue", first_context, "ABC-1"),
                                   env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def stop_pending():
            if pending.poll() is None: pending.kill()
            pending.communicate(timeout=10)
        self.addCleanup(stop_pending)
        for _ in range(200):
            if (self.root / "started").exists(): break
            time.sleep(.01)
        self.assertTrue((self.root / "started").exists())
        try:
            self.config = self.root / "other-config"; self.config.mkdir()
            (self.config / "config.sh").write_text((first_config / "config.sh").read_text().replace(
                "https://jira.example.test", "https://other.example.test"))
            other_state = self.config_state(self.config)
            other_context = self.connect()
            self.assertTrue(self.call("clear", other_context)["ok"])
            other_context = self.connect()
            other_marker = (other_state / "connection-context").read_bytes()
            self.config = first_config
            self.assertEqual(self.call("stamp")["context"], first_context)
            (self.root / "block").unlink()
            stdout, stderr = pending.communicate(timeout=10)
            self.assertEqual((pending.returncode, stderr), (0, ""))
            self.assertTrue(json.loads(stdout)["ok"])
            cached = (self.state / "cache/ABC-1.json").read_bytes()
            self.config = self.root / "other-config"
            override = self.root / "override.json"
            override.write_text(json.dumps({"key": "ABC-1", "fields": {"summary": "Other fictional issue"}}))
            self.assertEqual(self.call("issue", other_context, "ABC-1")["issue"]["summary"], "Other fictional issue")
            other_cached = (other_state / "cache/ABC-1.json").read_bytes()
            override.unlink()
            self.config = first_config
            self.assertEqual(self.call("issue", first_context, "ABC-1")["issue"]["key"], "ABC-1")
            self.assertEqual((self.state / "cache/ABC-1.json").read_bytes(), cached)
            self.assertTrue(self.call("clear", first_context)["ok"])
            self.assertEqual((other_state / "connection-context").read_bytes(), other_marker)
            self.assertEqual((other_state / "cache/ABC-1.json").read_bytes(), other_cached)
            self.config = self.root / "other-config"
            self.assertEqual(self.call("stamp")["context"], other_context)
        finally:
            self.config = first_config
            (self.root / "block").unlink(missing_ok=True)

    def test_configuration_aliases_share_state_and_legacy_shared_cache_is_preserved(self):
        legacy = self.state_root / "cache"; legacy.mkdir(parents=True)
        old_payload = legacy / "ABC-1.json"; old_payload.write_text("Fictional previous shared cache")
        marker = self.state_root / "connection-context"; marker.write_text("former\nepoch\n")
        context = self.connect()
        command = self.command("config"); command[3] += "/."
        report = subprocess.run(command, env=self.env, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(report.stdout)["context"], context)
        self.assertTrue(self.call("clear", context)["ok"])
        self.assertEqual(old_payload.read_text(), "Fictional previous shared cache")
        self.assertEqual(marker.read_text(), "former\nepoch\n")

    def test_case_alias_clear_retires_cached_and_inflight_reads_without_merging_distinct_folders(self):
        original = self.config
        alternate = original.with_name('CONFIG')
        same_folder = alternate.exists() and original.samefile(alternate)
        if not same_folder:
            alternate.mkdir()
            (alternate / 'config.sh').write_bytes((original / 'config.sh').read_bytes())
        context = self.connect()
        self.assertTrue(self.call('issue', context, 'ABC-1')['ok'])
        self.config = alternate
        alternate_context = self.connect()
        self.assertEqual(context == alternate_context, same_folder)
        self.assertEqual(self.config_state(original) == self.config_state(alternate), same_folder)
        self.assertTrue(self.call('issue', alternate_context, 'ABC-1')['ok'])
        self.config = original
        (self.root / 'block').touch()
        pending = subprocess.Popen(self.command('issue', context, 'ABC-2'),
            env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def stop_pending():
            if pending.poll() is None: pending.kill()
            pending.communicate(timeout=10)
        self.addCleanup(stop_pending)
        try:
            for _ in range(200):
                if (self.root / 'started').exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / 'started').exists())
            self.config = alternate
            self.assertTrue(self.call('clear', alternate_context)['ok'])
            self.config = original
            self.assertEqual(self.call('stamp')['context'] != context, same_folder)
            self.assertEqual(self.call('issue', context, 'ABC-1')['ok'], not same_folder)
            (self.root / 'block').unlink()
            stdout, stderr = pending.communicate(timeout=10)
            self.assertEqual((pending.returncode, stderr), (0, ''))
            response = json.loads(stdout)
            self.assertEqual(response['ok'], not same_folder)
            if same_folder: self.assertEqual(response['error'], 'connection_changed')
            for key in ('ABC-1', 'ABC-2'):
                self.assertEqual((self.state / f'cache/{key}.json').exists(), not same_folder)
            self.assertEqual(len(list((self.state_root / 'connections').iterdir())), 1 if same_folder else 2)
        finally:
            self.config = original
            (self.root / 'block').unlink(missing_ok=True)

    def test_symlinked_connection_namespace_cannot_write_outside_state(self):
        self.state_root.mkdir()
        outside = self.root / "unrelated"; outside.mkdir()
        (self.state_root / "connections").symlink_to(outside, target_is_directory=True)
        self.assertFalse(self.call("config")["ok"])
        self.assertEqual(list(outside.iterdir()), [])
        (self.state_root / "connections").unlink()
        self.state.parent.mkdir()
        self.state.symlink_to(outside, target_is_directory=True)
        self.assertFalse(self.call("config")["ok"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_stamp_does_not_create_state_and_namespace_parents_remain_private(self):
        self.assertTrue(self.call("stamp")["ok"])
        self.assertFalse(self.state_root.exists())
        self.state.parent.mkdir(parents=True)
        self.state_root.chmod(0o777); self.state.parent.chmod(0o777)
        self.connect()
        for directory in (self.state_root, self.state.parent, self.state):
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)

    def test_trailing_newline_in_a_configuration_path_cannot_retarget_another_folder(self):
        original = self.config
        self.config = self.root / 'config\n'; self.config.mkdir()
        (self.config / 'config.sh').write_text((original / 'config.sh').read_text().replace(
            'https://jira.example.test', 'https://other.example.test'))
        self.assertEqual(self.call('config')['base'], 'https://other.example.test')
        expected = self.config_state(self.config)
        self.assertTrue((expected / 'connection-context').is_file())
        self.config = original
        self.assertEqual(self.call('config')['base'], 'https://jira.example.test')

    def requests(self):
        return [json.loads(line) for line in (self.root / "calls").read_text().splitlines() if '"workitem"' in line]

    def use_rest(self):
        netrc = self.root / "fixture.netrc"
        netrc.write_text("machine jira.example.test login fictional password fictional\n"); netrc.chmod(0o600)
        curl = self.root / "curl"; curl.write_text(FAKE_REST); curl.chmod(0o700)
        self.env["CURL_BIN_PATH"] = str(curl)
        self.write_config(f"JIRA_BACKEND='rest'\nJIRA_NETRC_FILE='{netrc}'\n")

    def rest_requests(self):
        return [json.loads(line) for line in (self.root / "rest-calls").read_text().splitlines()]

    def test_projection_cache_and_fields(self):
        self.write_config("PICKER_FIELDS='summary,customfield_10016,assignee'\n")
        context = self.connect()
        result = self.call("issue", context, "ABC-1")
        self.assertTrue(result["ok"], result)
        issue = result["issue"]
        self.assertIn({"id":"customfield_10016", "label":"Points", "value":"5", "truncated":False, "unsupportedContent":False}, issue["metadata"])
        self.assertEqual(issue["values"], ["Fictional catalog filters", "5", "Alex Example"])
        self.assertEqual(issue["comments"][0]["author"], "Sam Sample")
        self.assertNotIn("untrusted", json.dumps(issue)); self.assertNotIn("image.example", json.dumps(issue))
        self.assertNotIn("\x1b", issue["description"])
        self.call("issue", context, "ABC-1")
        self.assertEqual(len(self.requests()), 1)
        self.call("issue", context, "ABC-1", "refresh")
        self.assertEqual(len(self.requests()), 2)

    def test_metadata_is_capped_and_only_requested_keys_return(self):
        context = self.connect()
        result = self.call("metadata", context, "ABC-1", "ABC-2")
        self.assertEqual([r["key"] for r in result["rows"]], ["ABC-1", "ABC-2"])
        self.assertEqual(result["rows"][0]["summary"], "Fictional catalog filters")
        self.assertFalse(self.call("metadata", context, *[f"ABC-{i}" for i in range(21)])["ok"])
        self.assertEqual(len(self.requests()), 1)

    def test_config_exposes_field_ids_and_configured_labels(self):
        fields = self.call("config")["fields"]
        self.assertIn({"id":"customfield_10016", "label":"Points"}, fields)
        self.assertEqual(fields[0], {"id":"summary", "label":"Summary"})
        self.assertNotIn("link", [f["id"] for f in fields])

    def test_config_whitespace_quotes_and_literal_shell_text(self):
        # CRLF, indentation and surrounding whitespace remain accepted.
        label = "Story points"
        (self.config / "config.sh").write_bytes((
            " \t# Fictional configuration\r\n\t \r\n"
            '\tJIRA_BASE= \t"https://jira.example.test" \r\n'
            " JIRA_SITE= jira-example\t\r\n"
            "\vJIRA_PROJECTS= 'ABC'\f\r\n"
            " READER_FIELDS= 'status,customfield_10016' \r\n"
            f" FIELD_LABELS= 'customfield_10016:{label}'\t"
        ).encode())
        result = self.call("config")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["projects"], ["ABC"])
        self.assertIn({"id": "customfield_10016", "label": label}, result["fields"])
        self.write_config("JIRA_SITE='unterminated\n")
        self.assertFalse(self.call("config")["ok"])
        sentinel = self.root / "should-not-exist"
        self.write_config(f'JIRA_SITE="$(touch {sentinel})"\n')
        self.assertFalse(self.call("config")["ok"])
        self.assertFalse(sentinel.exists())

    def test_hash_failure_cannot_publish_a_partial_fingerprint(self):
        binaries = self.root / "hash-bin"; binaries.mkdir()
        env = {**self.env, "PATH": str(binaries)}
        for name in ("sha256sum", "shasum"):
            with self.subTest(name=name):
                binary = binaries / name
                binary.write_text("#!/bin/sh\nprintf 'partial  -\\n'\nexit 7\n")
                binary.chmod(0o700)
                result = subprocess.run(["/bin/sh", "-c", '. "$1"; connection_hash',
                    "test", str(ROOT / "scripts/connection.sh")], env=env,
                    input="Fictional input", text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                binary.unlink()

    def test_connection_marker_reads_literal_lines_and_rejects_symlinks(self):
        self.state.mkdir(parents=True)
        marker = self.state / "connection-context"
        command = ["/bin/sh", "-c",
            '. "$1"; STATE=$2; connection_read_marker || exit 1; '
            'printf "%s\\0%s\\0" "$connection_saved_id" "$connection_saved_epoch"',
            "test", str(ROOT / "scripts/connection.sh"), str(self.state)]
        for value, expected in ((None, b"\0\0"), ("first\nsecond\n", b"first\0second\0"),
                ("first", b"first\0\0"), ("first\nsecond", b"first\0second\0"),
                (" first\\literal \n second\\literal \nignored\n",
                 b" first\\literal \0 second\\literal \0")):
            with self.subTest(value=value):
                if value is not None: marker.write_text(value)
                result = subprocess.run(command, env=self.env, capture_output=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, expected)
        target = self.root / "marker-target"
        marker.rename(target); marker.symlink_to(target)
        self.assertNotEqual(subprocess.run(command, env=self.env, capture_output=True).returncode, 0)

    def test_connection_marker_replacement_cannot_mix_generations(self):
        self.state.mkdir(parents=True)
        marker = self.state / "connection-context"
        replacement = self.state / "replacement"
        marker.write_text("old-identity\nold-epoch\n")
        replacement.write_text("new-identity\nnew-epoch\n")
        # Replace the directory entry after the first line has been read. Both
        # lines must still come from the already-open generation; the next call
        # must see the replacement. No scheduling or sleep is involved.
        script = r'''
            . "$1"
            STATE=$2
            reads=0
            read() {
                read_status=0
                command read "$@" || read_status=$?
                reads=$((reads + 1))
                if [ "$reads" = 1 ]; then
                    /bin/mv "$STATE/replacement" "$STATE/connection-context" || exit 1
                fi
                return "$read_status"
            }
            connection_read_marker || exit 1
            printf '%s\0%s\0' "$connection_saved_id" "$connection_saved_epoch"
            connection_read_marker || exit 1
            printf '%s\0%s\0' "$connection_saved_id" "$connection_saved_epoch"
        '''
        result = subprocess.run(["/bin/sh", "-c", script, "test",
            str(ROOT / "scripts/connection.sh"), str(self.state)],
            env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"old-identity\0old-epoch\0new-identity\0new-epoch\0")
        self.assertEqual(marker.read_text(), "new-identity\nnew-epoch\n")

    def test_reader_override_fetches_added_fields_and_isolates_cached_field_sets(self):
        context = self.connect()
        original = (self.config / "config.sh").read_bytes()
        self.call("issue", context, "ABC-1")
        selection = "customfield_10017,priority"
        result = self.call("issue", context, "ABC-1", "", selection)
        self.assertTrue(result["ok"], result)
        self.assertEqual([f["id"] for f in result["issue"]["metadata"]], selection.split(","))
        self.assertEqual(len(self.requests()), 2)
        self.assertIn("customfield_10017", " ".join(self.requests()[-1]))
        self.call("issue", context, "ABC-1", "", "priority,customfield_10017")
        self.assertEqual(len(self.requests()), 2)  # Placement/order alone reuses raw data.
        empty = self.call("issue", context, "ABC-1", "", "")["issue"]
        self.assertEqual(empty["metadata"], [])
        self.assertEqual(empty["description"], "")
        self.assertEqual((self.config / "config.sh").read_bytes(), original)
        before = len(self.requests())
        for selection in ("priority,priority", "customfield_1;echo nope", "not_a_field", "priority," , "x" * 2049):
            self.assertEqual(self.call("issue", context, "ABC-1", "", selection)["error"], "invalid_request")
        self.assertEqual(len(self.requests()), before)

    def test_linked_issues_project_direction_and_only_embedded_display_data(self):
        links = [
            {"type":{"inward":"is blocked by", "outward":"blocks"},
             "inwardIssue":{"key":"ABC-2", "fields":{"summary":"Fictional prerequisite\ncontinued", "status":{"name":"Open"}},
                            "self":"https://untrusted.example.test/PRIVATE_METADATA_SENTINEL"}},
            {"type":{"inward":"is blocked by", "outward":"blocks"},
             "outwardIssue":{"key":"OTHER-3", "fields":{"summary":"Fictional dependent", "status":{"name":"Done"}}}},
            {"outwardIssue":{"key":"ABC-4"}},
            None, False, "ignored", {"outwardIssue":{"key":"bad key"}},
            {"inwardIssue":5}, {"type":[], "outwardIssue":{"key":"ABC-5", "fields":[]}},
        ]
        expected = ("is blocked by: ABC-2 — Fictional prerequisite continued [Open]\n"
                    "blocks: OTHER-3 — Fictional dependent [Done]\n"
                    "Linked issue: ABC-4\nLinked issue: ABC-5")
        for backend in ("twg", "rest"):
            with self.subTest(backend=backend):
                if backend == "rest": self.use_rest()
                (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "fields":{"issuelinks":links}}))
                context = self.connect()
                result = self.call("issue", context, "ABC-1", "", "issuelinks")
                self.assertTrue(result["ok"], result)
                value = result["issue"]["metadata"][0]
                self.assertEqual(value["id"], "issuelinks")
                self.assertEqual(value["label"], "Linked Issues")
                self.assertEqual(value["value"], expected + "\nSome returned link data could not be displayed.")
                self.assertTrue(value["links"]["malformed"])
                self.assertEqual(len(value["links"]["records"]), 4)
                self.assertEqual([r["direction"] for r in value["links"]["records"]], ["inward", "outward", "outward", "outward"])
                self.assertFalse(value["truncated"])
                self.assertIs(value["unsupportedContent"], False)
                self.assertNotIn("PRIVATE_METADATA_SENTINEL", json.dumps(result))
                if backend == "twg":
                    self.assertEqual(len(self.requests()), 1)
                    self.assertIn("issuelinks", self.requests()[0][self.requests()[0].index("--fields") + 1])
                else:
                    self.assertEqual([r["kind"] for r in self.rest_requests()], ["issue"])
                    self.assertIn("issuelinks", self.rest_requests()[0]["query"]["fields"][0])
                # Hiding removes it from the projection and uses a separate field cache.
                hidden = self.call("issue", context, "ABC-1", "", "")["issue"]
                self.assertEqual(hidden["metadata"], [])

    def test_linked_issues_empty_flattened_and_bounded_projection(self):
        context = self.connect()
        for raw in (None, [], {}, "invalid", [None, {"inwardIssue":{"key":None}}]):
            (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "issuelinks":raw}))
            result = self.call("issue", context, "ABC-1", "refresh", "issuelinks")
            self.assertTrue(result["ok"], result)
            data = result["issue"]["metadata"][0]["links"]
            self.assertEqual(data["records"], [])
            self.assertEqual(data["state"], "available" if isinstance(raw, list) else "unavailable")
            self.assertEqual(data["malformed"], bool(raw) if isinstance(raw, list) else False)
        links = [{"type":{"outward":"blocks"}, "outwardIssue":{"key":"ABC-2", "fields":{"summary":"x" * 20001}}}]
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "issuelinks":links}))
        issue = self.call("issue", context, "ABC-1", "refresh", "issuelinks")["issue"]
        self.assertLessEqual(len(issue["metadata"][0]["value"]), 20000)
        self.assertEqual(len(issue["metadata"][0]["links"]["records"][0]["summary"]), 4096)
        self.assertTrue(issue["metadata"][0]["truncated"])
        self.assertTrue(issue["truncated"])

    def test_linked_projection_bounds_records_and_preserves_type_identity(self):
        links = [{"id":str(i), "type":{"id":str(i % 2), "outward":"relates to"},
                  "outwardIssue":{"key":f"ABC-{i+2}", "fields":{"summary":"Fictional linked item"}}}
                 for i in range(105)]
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "fields":{"issuelinks":links}}))
        issue = self.call("issue", self.connect(), "ABC-1", "", "issuelinks")["issue"]
        data = issue["metadata"][0]["links"]
        self.assertEqual(len(data["records"]), 100)
        self.assertEqual({r["type"] for r in data["records"]}, {"id:0", "id:1"})
        self.assertTrue(data["truncated"])
        self.assertTrue(issue["truncated"])
        self.assertLessEqual(len(issue["metadata"][0]["value"]), 20000)

    def test_custom_fields_keep_rich_text_scalars_arrays_and_content_notices(self):
        rich = {"type":"doc", "content":[
            {"type":"paragraph", "content":[{"type":"text", "text":"First paragraph"}]},
            {"type":"paragraph", "content":[{"type":"text", "text":"Second paragraph"}]},
            {"type":"unknown", "attrs":{"secret":"PRIVATE_METADATA_SENTINEL"}}]}
        fields = {"summary":"Fictional field examples", "customfield_10016":0, "customfield_10017":False,
            "customfield_10018":rich, "customfield_10019":[{"value":"North"}, {"name":"South"}],
            "customfield_10020":None, "customfield_10021":{"accountId":"PRIVATE_METADATA_SENTINEL"},
            "customfield_10022":"x" * 20001}
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "fields":fields}))
        context = self.connect()
        selected = ",".join(k for k in fields if k != "summary")
        issue = self.call("issue", context, "ABC-1", "", selected)["issue"]
        values = {f["id"]:f for f in issue["metadata"]}
        self.assertEqual(values["customfield_10016"]["value"], "0")
        self.assertEqual(values["customfield_10017"]["value"], "false")
        self.assertIn("First paragraph\n\nSecond paragraph", values["customfield_10018"]["value"])
        self.assertTrue(values["customfield_10018"]["unsupportedContent"])
        self.assertEqual(values["customfield_10019"]["value"], "North, South")
        self.assertEqual(values["customfield_10020"]["value"], "")
        self.assertEqual(values["customfield_10021"]["value"], "")
        self.assertEqual(len(values["customfield_10022"]["value"]), 20000)
        self.assertTrue(values["customfield_10022"]["truncated"])

    def test_comments_override_can_enable_and_hide_comments_without_changing_config(self):
        self.use_rest()
        path = self.config / "config.sh"
        path.write_text(path.read_text().replace("READER_FIELDS='status,assignee,customfield_10016,description,comments'", "READER_FIELDS='status,description'"))
        context = self.connect()
        self.assertEqual(self.call("comments", context, "ABC-1")["error"], "invalid_request")
        issue = self.call("issue", context, "ABC-1", "", "status,comments")["issue"]
        self.assertTrue(issue["commentsDeferred"])
        self.assertTrue(self.call("comments", context, "ABC-1", "comments")["ok"])
        before = len(self.rest_requests())
        self.assertEqual(self.call("comments", context, "ABC-1", "status")["error"], "invalid_request")
        self.assertEqual(len(self.rest_requests()), before)

    def test_detail_and_metadata_requests_match_projected_fields(self):
        self.write_config("PREVIEW_FIELDS='customfield_10017,comments'\n")
        context = self.connect()
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        detail = self.requests()[-1]
        self.assertEqual(detail[detail.index("--fields") + 1], "assignee,customfield_10016,description,status,summary")
        self.assertIn("--comments", detail)
        self.assertNotIn("customfield_10017", " ".join(detail))
        self.call("metadata", context, "ABC-1", "ABC-2")
        metadata = self.requests()[-1]
        self.assertEqual(metadata[metadata.index("--fields") + 1], "summary,status")

    def test_preview_fields_no_longer_add_requests_or_comments(self):
        self.write_config("READER_FIELDS='status,description'\nPREVIEW_FIELDS='customfield_10017,comments'\n")
        context = self.connect()
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        detail = self.requests()[-1]
        self.assertEqual(detail[detail.index("--fields") + 1], "description,status,summary")
        self.assertNotIn("--comments", detail)
        self.assertEqual(self.call("comments", context, "ABC-1")["error"], "invalid_request")

    def test_rest_detail_requests_only_projected_fields_and_keeps_comments_deferred(self):
        self.write_config("PREVIEW_FIELDS='customfield_10017,comments'\n")
        self.use_rest()
        context = self.connect()
        issue = self.call("issue", context, "ABC-1")["issue"]
        calls = self.rest_requests()
        self.assertEqual([call["kind"] for call in calls], ["issue"])
        self.assertEqual(calls[-1]["query"]["fields"][0].split(","),
                         ["assignee", "customfield_10016", "description", "status", "summary"])
        self.assertTrue(issue["commentsDeferred"])

    def test_signatureless_legacy_cache_is_refetched_with_explicit_fields(self):
        # Exercise the exact default field set that used to allow unsigned
        # cache entries and omit --fields, rather than a custom-field layout.
        self.write_config("READER_FIELDS='status,assignee,updated,link,description,comments'\n")
        context = self.connect()
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        first = self.requests()[0]
        self.assertIn("--fields", first, "legacy defaults now request the projected fields explicitly")
        cache = self.state / "cache/ABC-1.json"
        payload = json.loads(cache.read_text())
        payload.pop("_peek_request", None)
        cache.write_text(json.dumps(payload))
        before = len(self.requests())
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.assertEqual(len(self.requests()), before + 1, "an unsigned legacy cache is refetched once")
        self.assertIn("_peek_request", json.loads(cache.read_text()))
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.assertEqual(len(self.requests()), before + 1, "the refreshed cache is reused")

    def test_invalid_and_disallowed_keys_never_reach_jira(self):
        context = self.connect()
        for key in ("../ABC-1", "NOPE-1", "--help", "ABC-1;echo nope"):
            self.assertEqual(self.call("issue", context, key)["error"], "invalid_request")
        self.assertEqual(self.requests(), [])

    def test_stamp_is_local_only_and_config_drift_invalidates_requests(self):
        context = self.connect()
        before = (self.root / "calls").read_text()
        self.assertEqual(self.call("stamp")["context"], context)
        self.assertEqual((self.root / "calls").read_text(), before)
        self.write_config("PICKER_LAYOUT='top'\n")
        self.assertNotEqual(self.call("stamp")["context"], context)
        self.assertEqual(self.call("issue", context, "ABC-1")["error"], "connection_changed")
        self.assertEqual(self.requests(), [])

    def test_drift_during_a_request_cannot_publish_or_return_data(self):
        context = self.connect(); (self.root / "block").touch()
        child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (self.root / "started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "started").exists())
            self.write_config("PICKER_LAYOUT='top'\n"); (self.root / "block").unlink()
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(stderr, ""); self.assertEqual(json.loads(stdout)["error"], "connection_changed")
            self.assertFalse((self.state / "cache/ABC-1.json").exists())
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_clear_advances_epoch_and_zero_ttl_removes_payloads(self):
        self.write_config("CACHE_TTL_MIN=0\n"); context = self.connect()
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.assertEqual(list((self.state / "cache").iterdir()), [])
        self.assertEqual(list(self.state.glob(".issue-*")), [])
        self.assertEqual(self.call("clear", context), {"ok": True})
        self.assertNotEqual(self.call("stamp")["context"], context)

    def test_fetched_at_is_payload_mtime_and_cache_reads_preserve_age(self):
        context = self.connect()
        first = self.call("issue", context, "ABC-1")["issue"]
        payload = self.state / "cache/ABC-1.json"
        self.assertEqual(first["fetchedAt"], payload.stat().st_mtime_ns // 1000000)
        # Stay within TTL while giving cached content a visibly older age.
        old_ns = time.time_ns() - 120_123_000_000
        os.utime(payload, ns=(old_ns, old_ns))
        cached = self.call("issue", context, "ABC-1")["issue"]
        self.assertEqual(cached["fetchedAt"], payload.stat().st_mtime_ns // 1000000)
        self.assertLess(cached["fetchedAt"], first["fetchedAt"])
        self.assertEqual(len(self.requests()), 1)
        refreshed = self.call("issue", context, "ABC-1", "refresh")["issue"]
        self.assertEqual(refreshed["fetchedAt"], payload.stat().st_mtime_ns // 1000000)
        self.assertGreater(refreshed["fetchedAt"], cached["fetchedAt"])
        expired_ns = time.time_ns() - 900_000_000_000
        os.utime(payload, ns=(expired_ns, expired_ns))
        expired = self.call("issue", context, "ABC-1")["issue"]
        self.assertEqual(expired["fetchedAt"], payload.stat().st_mtime_ns // 1000000)
        self.assertGreater(expired["fetchedAt"], expired_ns // 1000000)
        self.assertEqual(len(self.requests()), 3)

    def test_zero_ttl_timestamp_comes_from_transient_payload(self):
        self.write_config("CACHE_TTL_MIN=0\n")
        context = self.connect()
        before = time.time_ns() // 1000000
        issue = self.call("issue", context, "ABC-1")["issue"]
        self.assertGreaterEqual(issue["fetchedAt"], before)
        self.assertLessEqual(issue["fetchedAt"], time.time_ns() // 1000000)
        self.assertEqual(list((self.state / "cache").iterdir()), [])
        self.assertEqual(list(self.state.glob(".issue-*")), [])

    def test_bsd_stat_fallback_discards_failed_gnu_output(self):
        binaries = self.root / "bin"; binaries.mkdir()
        stat = binaries / "stat"
        stat.write_text('''#!/usr/bin/env python3
import pathlib, sys
if sys.argv[1] in ("-c", "-Lc"):
    print("FICTIONAL_FAILED_STAT_OUTPUT"); sys.exit(1)
if sys.argv[1:3] == ["-Lf", "%d:%i"]:
    info = pathlib.Path(sys.argv[3]).stat()
    print(f"{info.st_dev}:{info.st_ino}"); sys.exit(0)
if sys.argv[1:3] != ["-f", "%.9Fm"]: sys.exit(1)
seconds, nanos = divmod(pathlib.Path(sys.argv[3]).stat().st_mtime_ns, 1000000000)
print(f"{seconds}.{nanos:09d}")
'''); stat.chmod(0o700)
        self.env["PATH"] = str(binaries) + os.pathsep + self.env.get("PATH", os.defpath)
        context = self.connect()
        issue = self.call("issue", context, "ABC-1")["issue"]
        payload = self.state / "cache/ABC-1.json"
        self.assertEqual(issue["fetchedAt"], payload.stat().st_mtime_ns // 1000000)

    def test_clear_rejects_missing_stale_and_changed_context_without_mutation(self):
        context = self.connect()
        self.call("issue", context, "ABC-1")
        marker = self.state / "connection-context"
        payload = self.state / "cache/ABC-1.json"
        original_marker = marker.read_bytes(); original_payload = payload.read_bytes()
        self.assertEqual(self.call("clear")["error"], "invalid_request")
        self.assertEqual(self.call("clear", "stale:epoch")["error"], "connection_changed")
        self.write_config("PICKER_LAYOUT='top'\n")
        self.assertEqual(self.call("clear", context)["error"], "connection_changed")
        self.assertEqual(marker.read_bytes(), original_marker)
        self.assertEqual(payload.read_bytes(), original_payload)

    def test_clear_preserves_configuration_unrelated_state_and_rejects_old_epoch(self):
        context = self.connect(); self.call("issue", context, "ABC-1")
        config_bytes = (self.config / "config.sh").read_bytes()
        unrelated = self.state / "key"; unrelated.write_text("ABC-1\n")
        before_calls = (self.root / "calls").read_bytes()
        self.assertEqual(self.call("clear", context), {"ok": True})
        self.assertEqual((self.config / "config.sh").read_bytes(), config_bytes)
        self.assertEqual(unrelated.read_text(), "ABC-1\n")
        self.assertEqual((self.root / "calls").read_bytes(), before_calls)
        self.assertEqual(list((self.state / "cache").iterdir()), [])
        self.assertEqual(self.call("clear", context)["error"], "connection_changed")

    def test_clear_while_fetching_cannot_publish_or_return_old_payload(self):
        context = self.connect(); (self.root / "block").touch()
        child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (self.root / "started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "started").exists())
            self.assertEqual(self.call("clear", context), {"ok": True})
            (self.root / "block").unlink()
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"ok": False, "error": "connection_changed"})
            self.assertFalse((self.state / "cache/ABC-1.json").exists())
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_clear_advances_epoch_even_when_cache_directory_is_absent(self):
        context = self.connect()
        (self.state / "cache").rmdir()
        self.assertEqual(self.call("clear", context), {"ok": True})
        self.assertNotEqual(self.call("stamp")["context"], context)

    def test_standalone_clear_without_cache_retires_inflight_reads(self):
        for ttl in (0, 10):
            with self.subTest(ttl=ttl):
                self.write_config(f"CACHE_TTL_MIN={ttl}\n")
                context = self.connect()
                config_bytes = (self.config / "config.sh").read_bytes()
                unrelated = self.state / "key"; unrelated.write_text("ABC-1\n")
                (self.root / "started").unlink(missing_ok=True)
                (self.root / "block").touch()
                child = subprocess.Popen(self.command("issue", context, "ABC-1"), env=self.env,
                                         text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    for _ in range(300):
                        if (self.root / "started").exists(): break
                        time.sleep(.01)
                    self.assertTrue((self.root / "started").exists())
                    cache = self.state / "cache"; cache.rmdir()
                    calls = (self.root / "calls").read_bytes()
                    cleared = subprocess.run(["sh", str(ROOT / "scripts/clear-cache.sh")],
                        env={**self.env, "HERDR_PLUGIN_STATE_DIR": str(self.state)},
                        text=True, capture_output=True, check=True, timeout=10)
                    self.assertEqual(cleared.stderr, "")
                    self.assertEqual((self.root / "calls").read_bytes(), calls)
                    # Another reader may recreate the directory before this
                    # request finishes. It must still be unable to publish.
                    cache.mkdir()
                    (self.root / "block").unlink()
                    stdout, stderr = child.communicate(timeout=10)
                    self.assertEqual(stderr, "")
                    self.assertEqual(json.loads(stdout), {"ok": False, "error": "connection_changed"})
                    self.assertFalse((cache / "ABC-1.json").exists())
                    self.assertEqual(list(self.state.glob(".issue-*")), [])
                    self.assertNotEqual(self.call("stamp")["context"], context)
                    self.assertEqual((self.config / "config.sh").read_bytes(), config_bytes)
                    self.assertEqual(unrelated.read_text(), "ABC-1\n")
                finally:
                    (self.root / "block").unlink(missing_ok=True)
                    if child.poll() is None: child.kill(); child.communicate()

    def test_standalone_clear_missing_state_is_a_noop(self):
        result = subprocess.run(["sh", str(ROOT / "scripts/clear-cache.sh")],
            env={**self.env, "HERDR_PLUGIN_STATE_DIR": str(self.state)},
            text=True, capture_output=True, check=True, timeout=10)
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.state.exists())
        self.assertFalse((self.root / "calls").exists())

    def test_standalone_clear_rejects_unresolved_root_without_changing_any_namespace(self):
        context = self.connect()
        self.call("issue", context, "ABC-1")
        marker = (self.state / "connection-context").read_bytes()
        cached = (self.state / "cache/ABC-1.json").read_bytes()
        result = subprocess.run(["sh", str(ROOT / "scripts/clear-cache.sh")],
            env={**self.env, "HERDR_PLUGIN_STATE_DIR": str(self.state_root)},
            text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("select a connection", result.stderr)
        self.assertFalse((self.state_root / "connection-context").exists())
        self.assertEqual((self.state / "connection-context").read_bytes(), marker)
        self.assertEqual((self.state / "cache/ABC-1.json").read_bytes(), cached)

    def test_scoped_external_configuration_is_verified_once_per_epoch_before_reads(self):
        self.use_rest()
        with (self.config / "config.sh").open("a") as stream:
            stream.write("JIRA_CLOUD_ID='fictional-cloud-123'\n")
        context = self.connect()
        self.assertEqual([r["kind"] for r in self.rest_requests()], ["site"])
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.call("stamp")
        self.assertEqual([r["kind"] for r in self.rest_requests()], ["site", "issue"])
        self.assertTrue(self.call("clear", context)["ok"])
        self.assertEqual([r["kind"] for r in self.rest_requests()], ["site", "issue"])
        (self.root / "rest-mode").write_text("site-mismatch")
        self.assertFalse(self.call("config")["ok"])
        self.assertEqual([r["kind"] for r in self.rest_requests()], ["site", "issue", "site"])
        self.assertFalse(self.call("issue", self.call("stamp")["context"], "ABC-1")["ok"])
        self.assertTrue(all(r["kind"] == "site" for r in self.rest_requests()[2:]))

    def test_standalone_clear_rejects_symlink_and_non_directory_cache(self):
        self.connect()
        marker = self.state / "connection-context"; before = marker.read_bytes()
        cache = self.state / "cache"; cache.rmdir()
        outside = self.root / "unrelated"; outside.mkdir()
        payload = outside / "keep.json"; payload.write_text("fictional unrelated state")
        cache.symlink_to(outside)
        for kind in ("symlink", "file"):
            with self.subTest(kind=kind):
                result = subprocess.run(["sh", str(ROOT / "scripts/clear-cache.sh")],
                    env={**self.env, "HERDR_PLUGIN_STATE_DIR": str(self.state)},
                    text=True, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(marker.read_bytes(), before)
                self.assertEqual(payload.read_text(), "fictional unrelated state")
                cache.unlink()
                if kind == "symlink": cache.write_text("not a directory")

    def test_unclipped_description_does_not_report_truncation(self):
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":"x" * 5000}))
        issue = self.call("issue", self.connect(), "ABC-1")["issue"]
        self.assertEqual(len(issue["description"]), 5000)
        self.assertFalse(issue["truncated"])

    def test_adf_plaintext_structure_ignores_malicious_attributes_and_unknown_nodes(self):
        def text(value): return {"type": "text", "text": value}
        def node(kind, *children):
            return {"type": kind, "content": list(children),
                    "attrs": {"url": "https://untrusted.example.test", "id": "PRIVATE_METADATA_SENTINEL"}}
        document = node("doc", node("heading", text("Plan")),
                        node("orderedList", node("listItem", node("paragraph", text("First"))),
                             node("listItem", node("paragraph", text("Second")))),
                        node("codeBlock", text("one\ntwo")), node("blockquote", node("paragraph", text("Quote"))),
                        node("table", node("tableRow", node("tableHeader", node("paragraph", text("Name"))),
                                           node("tableCell", node("paragraph", text("Value"))))),
                        node("unknownExtension", text("PRIVATE_METADATA_SENTINEL")),
                        node("paragraph", text("Visible\u001b\u202e\u2066\u200b")),
                        {"type":"mention", "attrs":{"id":"PRIVATE_METADATA_SENTINEL", "text":"@Sample"}})
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":document,
            "customfield_10016":{"id":"PRIVATE_METADATA_SENTINEL"},
            "comments":{"total":7,"comments":[{"author":"Sample", "body":document}]}}))
        issue = self.call("issue", self.connect(), "ABC-1")["issue"]
        for fragment in ("Plan\n────────", "1. First\n2. Second", "    one\n    two", "│ Quote", "Name  │  Value", "@Sample"):
            self.assertIn(fragment, issue["description"])
        for control in ("\u001b", "\u202e", "\u2066", "\u200b"):
            self.assertNotIn(control, json.dumps(issue, ensure_ascii=False))
        self.assertNotIn("untrusted.example", json.dumps(issue))
        self.assertEqual(issue["commentsTotal"], 7)
        self.assertTrue(issue["truncated"])

    def test_unicode_content_is_bounded_below_native_stdout_limit(self):
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":"🌱" * 100001,
            "comments":[{"author":"Sample", "body":"🌱" * 20001}] * 101}))
        result = self.call("issue", self.connect(), "ABC-1")
        self.assertTrue(result["ok"], result)
        self.assertLess(len(json.dumps(result, ensure_ascii=False).encode()), 8 * 1024 * 1024)
        self.assertLessEqual(sum(len(c["body"]) for c in result["issue"]["comments"]), 1000000)
        self.assertEqual(result["issue"]["commentsTotal"], 101)
        self.assertTrue(result["issue"]["truncated"])

    def test_narrow_tables_repeat_column_labels_in_description_comments_and_custom_fields(self):
        def cell(kind, value):
            return {"type":kind, "attrs":{"id":"PRIVATE_METADATA_SENTINEL"}, "content":[
                {"type":"paragraph", "content":[{"type":"text", "text":value}]}]}
        headers = ["Capability", "Basic plan", "Team plan"]
        values = ["Saved exports", "Up to 7 days from the time a fictional catalog export finishes",
                  "Up to 42 days, including archived catalog versions kept for review, with the original category and selection preserved so reviewers can compare every saved version"]
        table = {"type":"table", "content":[
            {"type":"tableRow", "content":[cell("tableHeader", label) for label in headers]},
            {"type":"tableRow", "content":[cell("tableCell", value) for value in values]},
            {"type":"tableRow", "content":[cell("tableCell", "Missing value"), cell("tableCell", "")]}]}
        doc = {"type":"doc", "content":[table]}
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":doc,
            "customfield_10016":doc, "comments":[{"body":doc}]}))
        context = self.connect(); issue = self.call("issue", context, "ABC-1")["issue"]
        projected = "\n".join(f"{label}: {value}" for label, value in zip(headers, values))
        for body in [issue["description"], issue["comments"][0]["body"],
                     next(field["value"] for field in issue["metadata"] if field["id"] == "customfield_10016")]:
            self.assertIn(projected, body)
            self.assertIn("Capability: Missing value\nBasic plan: —\nTeam plan: —", body)
            self.assertNotIn("│", body)
        self.assertFalse(issue["unsupportedContent"])
        table["content"][0]["content"][1]["content"][0]["content"][0]["text"] = ""
        table["content"][1]["content"].append(cell("tableCell", "Extra"))
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":doc}))
        body = self.call("issue", context, "ABC-1", "refresh")["issue"]["description"]
        self.assertIn("Column 2: Up to 7 days", body)
        self.assertIn("Column 4: Extra", body)
        # Spanning cells cannot safely borrow positional headers. Keep visible
        # text and explain the limitation instead of assigning a wrong label.
        table["content"][1]["content"][0]["attrs"]["colspan"] = 2
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":doc}))
        body = self.call("issue", context, "ABC-1", "refresh")["issue"]["description"]
        self.assertIn("Table has merged cells", body)
        self.assertIn("Saved exports", body)
        self.assertNotIn("Capability: Saved exports", body)
        table["content"] = table["content"][:1]
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":doc}))
        body = self.call("issue", context, "ABC-1", "refresh")["issue"]["description"]
        self.assertIn("Capability", body, "a header-only table must not disappear")
        self.assertIn("Team plan", body)

    def test_standard_adf_containers_preserve_context_and_unknown_content_is_explicit(self):
        def paragraph(value): return {"type":"paragraph", "content":[{"type":"text","text":value}]}
        document = {"type":"doc","content":[
            {"type":"panel","attrs":{"panelType":"warning","id":"PRIVATE_METADATA_SENTINEL"},
             "content":[paragraph("Wait for the fictional migration.")]},
            {"type":"expand","attrs":{"title":"Acceptance"},"content":[paragraph("Preserve the filters.")]},
            {"type":"table","content":[{"type":"tableRow","content":[{"type":"tableCell","content":[
                {"type":"nestedExpand","attrs":{"title":"Detail"},"content":[paragraph("Keep the selection.")]}]}]}]},
            {"type":"paragraph","content":[{"type":"status","attrs":{"text":"Ready"}}]}]}
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1","description":document,
            "comments":[{"body":document}]}))
        context = self.connect(); issue = self.call("issue", context, "ABC-1")["issue"]
        for fragment in ("Warning", "fictional migration", "Acceptance", "Preserve the filters", "Keep the selection", "Ready"):
            self.assertIn(fragment, issue["description"]); self.assertIn(fragment, issue["comments"][0]["body"])
        self.assertFalse(issue["truncated"]); self.assertFalse(issue["unsupportedContent"])
        document["content"].append({"type":"unknownExtension","content":[paragraph("PRIVATE_METADATA_SENTINEL")]})
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1","description":document}))
        issue = self.call("issue", context, "ABC-1", "refresh")["issue"]
        self.assertTrue(issue["unsupportedContent"]); self.assertIn("[Unsupported content]", issue["description"])

    def test_native_core_is_available_without_requesting_comments(self):
        self.use_rest(); (self.root / "rest-mode").write_text("comments-denied")
        context = self.connect(); issue = self.call("issue", context, "ABC-1")["issue"]
        self.assertEqual(issue["description"], "Core description"); self.assertTrue(issue["commentsDeferred"])
        self.assertEqual([r["kind"] for r in self.rest_requests()], ["issue"])
        self.assertEqual(self.call("comments", context, "ABC-1"), {"ok":False,"error":"permission_denied"})
        self.assertEqual(self.call("stamp")["context"], context)
        self.assertTrue((self.state / "cache/ABC-1.json").exists())
        self.assertTrue(self.call("issue", context, "ABC-2")["ok"])

    def test_native_comments_are_one_recent_page_and_preserve_total(self):
        self.use_rest(); context = self.connect()
        self.call("issue", context, "ABC-1")
        result = self.call("comments", context, "ABC-1")["comments"]
        self.assertEqual(result["key"], "ABC-1"); self.assertEqual(result["commentsTotal"], 205)
        self.assertEqual(len(result["comments"]), 100); self.assertTrue(result["truncated"])
        self.assertEqual(result["comments"][0]["body"], "Fictional recent comment 205")
        requests = self.rest_requests(); self.assertEqual([r["kind"] for r in requests], ["issue", "comments"])
        self.assertEqual(requests[-1]["query"], {"startAt":["0"],"maxResults":["100"],"orderBy":["-created"]})
        self.assertFalse(list(self.state.glob(".rest-*"))); self.assertFalse(list(self.state.glob(".twg-*")))

    def test_native_comments_failure_preserves_core_and_cannot_bypass_allowlist(self):
        self.use_rest(); context = self.connect(); self.call("issue", context, "ABC-1")
        before = len(self.rest_requests())
        for key in ("NOPE-1", "../ABC-1", "ABC-1;echo nope"):
            self.assertEqual(self.call("comments", context, key)["error"], "invalid_request")
        self.assertEqual(len(self.rest_requests()), before)
        (self.root / "rest-mode").write_text("comments-malformed")
        self.assertEqual(self.call("comments", context, "ABC-1")["error"], "request_failed")
        self.assertTrue(self.call("issue", context, "ABC-1")["ok"])
        self.assertEqual(self.call("stamp")["context"], context)

    def test_permission_denial_is_local_but_authentication_loss_still_revokes(self):
        self.use_rest(); context = self.connect(); self.call("issue", context, "ABC-1")
        self.call("issue", context, "ABC-2")
        (self.root / "rest-mode").write_text("issue-denied")
        self.assertEqual(self.call("issue", context, "ABC-2", "refresh")["error"], "permission_denied")
        self.assertTrue((self.state / "cache/ABC-1.json").exists())
        self.assertFalse((self.state / "cache/ABC-2.json").exists())
        self.assertEqual(self.call("stamp")["context"], context)
        (self.root / "rest-mode").write_text("issue-unauthorized")
        self.assertFalse(self.call("issue", context, "ABC-2")["ok"])
        self.assertFalse((self.state / "cache/ABC-1.json").exists())
        self.assertEqual(self.call("issue", context, "ABC-1")["error"], "connection_changed")

    def test_twg_explicit_permission_failures_retire_only_the_requested_issue(self):
        context = self.connect()
        self.call("issue", context, "ABC-1")
        for status, error in ((1, {"error": {"statusCode": 403}}),
                (1, {"error": {"statusCode": "403"}, "data": []}),
                (0, {"data": {"items": [{"ok": False, "error": {"code": "FORBIDDEN"}}]}})):
            with self.subTest(status=status):
                self.assertTrue(self.call("issue", context, "ABC-2")["ok"])
                self.env.update(APP_TEST_TWG_ERROR=json.dumps(error), APP_TEST_TWG_EXIT=str(status))
                try:
                    self.assertEqual(self.call("issue", context, "ABC-2", "refresh"),
                                     {"ok": False, "error": "permission_denied"})
                    self.assertFalse((self.state / "cache/ABC-2.json").exists())
                    self.assertTrue((self.state / "cache/ABC-1.json").exists())
                    self.assertEqual(self.call("stamp")["context"], context)
                finally:
                    self.env.pop("APP_TEST_TWG_ERROR"); self.env.pop("APP_TEST_TWG_EXIT")

    def test_twg_content_and_transient_errors_are_not_permission_denials(self):
        context = self.connect()
        for status in ({"name": "FORBIDDEN"}, "403", "FORBIDDEN"):
            with self.subTest(status=status):
                (self.root / "override.json").write_text(json.dumps({"key": "ABC-1", "code": "FORBIDDEN",
                    "description": "HTTP 403 FORBIDDEN PERMISSION_DENIED", "status": status}))
                self.assertTrue(self.call("issue", context, "ABC-1", "refresh")["ok"])
        self.env["APP_TEST_TWG_ERROR"] = json.dumps({"error": {"statusCode": 503, "message": "Permission service unavailable"}})
        self.assertEqual(self.call("issue", context, "ABC-1", "refresh")["error"], "request_failed")
        self.assertEqual(self.call("stamp")["context"], context)

    def test_missing_backend_dependencies_have_fixed_actionable_code(self):
        self.env["TWG_BIN_PATH"] = str(self.root / "missing-twg")
        self.assertEqual(self.call("config"), {"ok": False, "error": "dependencies_missing"})
        self.write_config("JIRA_BACKEND='rest'\n")
        self.env["CURL_BIN_PATH"] = str(self.root / "missing-curl")
        self.assertEqual(self.call("config"), {"ok": False, "error": "dependencies_missing"})

    def test_missing_jq_is_reported_for_local_stamp_and_clear(self):
        binaries = self.root / "bin"; binaries.mkdir()
        for name in ("sh", "dirname"):
            (binaries / name).symlink_to(shutil.which(name))
        self.env["PATH"] = str(binaries)
        for operation in ("stamp", "clear"):
            self.assertEqual(self.call(operation, "fictional:context"),
                             {"ok": False, "error": "dependencies_missing"})

    def test_errors_are_sanitized_and_config_is_never_executed(self):
        context = self.connect(); (self.root / "fail").touch()
        self.assertEqual(self.call("issue", context, "ABC-1")["error"], "request_failed")
        (self.config / "config.sh").write_text(f"touch '{self.root}/should-not-exist'\n")
        self.assertFalse(self.call("config")["ok"])
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_symlinked_config_is_rejected(self):
        target = self.root / "target"; (self.config / "config.sh").rename(target)
        (self.config / "config.sh").symlink_to(target)
        self.assertEqual(self.call("config")["error"], "configuration_missing")

    def test_shortened_content_is_explicit_and_string_authors_are_supported(self):
        (self.root / "override.json").write_text(json.dumps({"key":"ABC-1", "description":"x" * 100001,
            "comments":[{"author":"Sam Sample", "body":"Comment"}] * 101}))
        issue = self.call("issue", self.connect(), "ABC-1")["issue"]
        self.assertEqual(len(issue["description"]), 100000)
        self.assertEqual(len(issue["comments"]), 100)
        self.assertEqual(issue["commentsTotal"], 101)
        self.assertTrue(issue["truncated"])
        self.assertEqual(issue["comments"][0]["author"], "Sam Sample")

    def test_native_rest_adapter_does_not_fall_back_to_twg(self):
        netrc = self.root / "fixture.netrc"
        netrc.write_text("machine jira.example.test login fictional password fictional\n"); netrc.chmod(0o600)
        curl = self.root / "curl"
        curl.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
args=sys.argv[1:]; out=pathlib.Path(args[args.index("-o")+1]); url=args[-1]
if "/comment?" in url: body={"startAt":0,"maxResults":100,"total":0,"comments":[]}
else: body={"key":"ABC-1","fields":{"summary":"Fictional REST issue","status":{"name":"Open"},"description":"REST body"}}
out.write_text(json.dumps(body)); print("200",end="")
'''); curl.chmod(0o700)
        self.env["CURL_BIN_PATH"] = str(curl)
        self.write_config(f"JIRA_BACKEND='rest'\nJIRA_NETRC_FILE='{netrc}'\n")
        issue = self.call("issue", self.connect(), "ABC-1")["issue"]
        self.assertEqual(issue["summary"], "Fictional REST issue")
        self.assertEqual(issue["fetchedAt"], (self.state / "cache/ABC-1.json").stat().st_mtime_ns // 1000000)
        self.assertFalse((self.root / "calls").exists())

    def test_token_rotation_retires_an_inflight_comment_request(self):
        old = self.root / "old-fictional.netrc"
        new = self.root / "new-fictional.netrc"
        for path, value in ((old, "fictional-old"), (new, "fictional-new")):
            path.write_text(f"machine jira.example.test login fictional password {value}\n")
            path.chmod(0o600)
        curl = self.root / "curl"
        curl.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys,time
root=pathlib.Path(os.environ["APP_TEST_ROOT"])
args=sys.argv[1:]; out=pathlib.Path(args[args.index("-o")+1]); url=args[-1]
if not pathlib.Path(args[args.index("--netrc-file")+1]).is_file(): sys.exit(26)
if "/comment?" in url:
    if "startAt=0&" in url:
        (root/"comment-started").touch()
        for _ in range(500):
            if (root/"continue-comments").exists(): break
            time.sleep(.01)
        body={"startAt":0,"maxResults":100,"total":2,"comments":[{"body":"Fictional old comment"}]}
    else: body={"startAt":1,"maxResults":100,"total":2,"comments":[{"body":"Fictional second comment"}]}
else: body={"key":"ABC-1","fields":{"summary":"Fictional old account","description":"Discard this result"}}
out.write_text(json.dumps(body)); print("200",end="")
''')
        curl.chmod(0o700); self.env["CURL_BIN_PATH"] = str(curl)
        self.write_config(f"JIRA_BACKEND='rest'\nJIRA_NETRC_FILE='{old}'\n")
        context = self.connect()
        child = subprocess.Popen(self.command("comments", context, "ABC-1"), env=self.env,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (self.root / "comment-started").exists(): break
                time.sleep(.01)
            self.assertTrue((self.root / "comment-started").exists())
            # Match setup's commit order: switch config before retiring old credentials.
            self.write_config(f"JIRA_BACKEND='rest'\nJIRA_NETRC_FILE='{new}'\n")
            old.unlink()
            self.assertNotEqual(self.connect(), context)
            (self.root / "continue-comments").touch()
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"ok": False, "error": "connection_changed"})
            self.assertFalse((self.state / "cache/ABC-1.json").exists())
        finally:
            if child.poll() is None: child.kill(); child.communicate()

    def test_installed_runtime_runs_outside_the_checkout(self):
        app_home = (self.root / "native-app").resolve()
        # Reproduce an extracted checkout with no parent app/ or TUI tree.
        checkout = self.root / "extracted"
        checkout.mkdir()
        for name in ("scripts", "mods", "rust-backend", ".release-runtime"):
            shutil.copytree(ROOT / name, checkout / name, ignore=shutil.ignore_patterns("target", "__pycache__"))
        for name in ("LICENSE", "config.example.sh", "package.json"):
            shutil.copyfile(ROOT / name, checkout / name)
        (checkout / "docs").mkdir()
        shutil.copyfile(ROOT / "docs/AGENT-GUIDE.md", checkout / "docs/AGENT-GUIDE.md")
        subprocess.run(["python3", str(checkout / "scripts/install-app.py"), "--app-home", str(app_home)],
                       cwd=self.root, env=self.env, check=True, capture_output=True)
        # An installation must still work after its source checkout is gone.
        shutil.rmtree(checkout)
        script = app_home / "mods/jira-peek/runtime/app-bridge.sh"
        def installed(op, *args):
            result = subprocess.run(["sh", str(script), op, str(self.config), str(self.state_root), *args],
                                    cwd=self.root, env=self.env, text=True, capture_output=True, check=True)
            return json.loads(result.stdout)
        context = installed("config")["context"]
        issue = installed("issue", context, "ABC-1")["issue"]
        self.assertEqual(issue["summary"], "Fictional catalog filters")


if __name__ == "__main__":
    unittest.main()
