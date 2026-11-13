"""Reuse the shell contract assertions against the opt-in Rust executable.

Shell implementation hooks/dependency tests are excluded explicitly below.
REST goes to a fictional loopback server; no real config or network is used.
"""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"benchmarks"))
from fixture import Fixture
spec=importlib.util.spec_from_file_location("shell_contract",ROOT/"tests/bridge_test.py")
shell=importlib.util.module_from_spec(spec); spec.loader.exec_module(shell)
BINARY=Path(os.environ.get("JIRA_PEEK_RUST_BINARY",ROOT/"rust-backend/target/release/jira-peek-bridge"))

class RustParity(shell.BridgeTests):
    def setUp(self):
        super().setUp()
        self.bridge=self.root/"rust-wrapper.sh"
        self.bridge.write_text("#!/bin/sh\nexec "+shlex.quote(str(BINARY))+" \"$@\"\n")
        self.fixture=Fixture(self.root)
        self.addCleanup(self.fixture.close)
        self.env["JIRA_PEEK_FIXTURE_HTTP"]=self.fixture.url
    def use_rest(self):
        super().use_rest()
        # The scoped gateway uses its own machine entry in actual netrc files.
        with (self.root/"fixture.netrc").open("a") as f:
            f.write("machine api.atlassian.com login fictional password fictional\n")

    def test_rest_ignores_utility_paths_and_handles_http_errors(self):
        self.use_rest()
        self.env.update(CURL_BIN_PATH="/nonexistent/fictional",TWG_BIN_PATH="/nonexistent/fictional",PATH="/nonexistent/fictional")
        # Run the binary directly: even sh/python/curl/jq/stat are unavailable.
        def call(op,*args):
            p=subprocess.run([str(BINARY),op,str(self.config),str(self.state_root),*args],env=self.env,capture_output=True,text=True,check=True)
            self.assertEqual(p.stderr,""); return json.loads(p.stdout)
        ctx=call("config")["context"]
        self.assertTrue(call("issue",ctx,"ABC-1")["ok"])
        self.assertTrue(call("metadata",ctx,"ABC-1")["ok"])
        self.assertTrue(call("comments",ctx,"ABC-1")["ok"])
        self.assertTrue(call("stamp")["ok"])
        self.assertTrue(call("clear",ctx)["ok"])

    def test_rest_older_denial_and_success_cannot_replace_newer_attempt(self):
        self.use_rest(); ctx=self.connect()
        for old_status,new_status in ((403,200),(200,503)):
            with self.subTest(old_status=old_status,new_status=new_status):
                started=threading.Event(); release=threading.Event(); calls=0
                def hook(call):
                    nonlocal calls
                    if call["kind"]!="issue": return None
                    calls+=1
                    if calls==1:
                        started.set(); release.wait(10)
                        return old_status,{"key":"ABC-2","fields":{"summary":"Fictional old response"}}
                    return new_status,{"key":"ABC-2","fields":{"summary":"Fictional newer response"}}
                self.fixture.hook=hook
                child=subprocess.Popen(self.command("issue",ctx,"ABC-2","refresh"),env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    self.assertTrue(started.wait(10))
                    newer=self.call("issue",ctx,"ABC-2","refresh")
                    self.assertEqual(newer["ok"],new_status==200)
                    release.set(); stdout,stderr=child.communicate(timeout=10)
                    self.assertEqual(stderr,"")
                    self.assertEqual(json.loads(stdout),{"ok":False,"error":"request_failed"})
                    if new_status==200:
                        self.assertEqual(self.call("issue",ctx,"ABC-2")["issue"]["summary"],"Fictional newer response")
                    else: self.assertFalse((self.state/"cache/ABC-2.json").exists())
                finally:
                    release.set()
                    if child.poll() is None: child.kill(); child.communicate()
                    self.fixture.hook=None

    def test_rest_token_rotation_retires_inflight_comments(self):
        self.use_rest(); ctx=self.connect(); started=threading.Event(); release=threading.Event()
        def hook(call):
            if call["kind"]=="comments": started.set(); release.wait(10)
        self.fixture.hook=hook
        child=subprocess.Popen(self.command("comments",ctx,"ABC-1"),env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(started.wait(10))
            path=self.root/"fixture.netrc"; path.write_text(path.read_text().replace("password fictional","password fictional-rotated"))
            self.assertNotEqual(self.connect(),ctx)
            release.set(); stdout,stderr=child.communicate(timeout=10)
            self.assertEqual(stderr,"")
            self.assertEqual(json.loads(stdout),{"ok":False,"error":"connection_changed"})
        finally:
            release.set()
            if child.poll() is None: child.kill(); child.communicate()

    def test_shell_and_rust_share_cache_context_and_clear(self):
        self.use_rest(); from fixture import FAKE_CURL
        (self.root/"curl").write_text(FAKE_CURL)
        ctx=self.connect()
        def baseline(op,*args):
            p=subprocess.run(["sh",str(shell.BRIDGE),op,str(self.config),str(self.state_root),*args],env=self.env,text=True,capture_output=True,check=True)
            self.assertEqual(p.stderr,""); return json.loads(p.stdout)
        self.assertEqual(baseline("config")["context"],ctx)
        first=baseline("issue",ctx,"ABC-1"); count=len(self.fixture.calls)
        self.assertEqual(self.call("issue",ctx,"ABC-1"),first)
        self.assertEqual(len(self.fixture.calls),count)
        second=self.call("issue",ctx,"ABC-1","refresh"); count=len(self.fixture.calls)
        self.assertEqual(baseline("issue",ctx,"ABC-1"),second)
        self.assertEqual(len(self.fixture.calls),count)
        self.assertTrue(baseline("clear",ctx)["ok"])
        self.assertEqual(self.call("issue",ctx,"ABC-1")["error"],"connection_changed")

    def test_projection_matches_jq_on_diverse_fictional_documents(self):
        fields="status,assignee,customfield_10016,description,comments,issuelinks"
        self.write_config(f"READER_FIELDS='{fields}'\n")
        context=self.connect()
        scalars=[None, False, 0, "", "Fictional\r\ntext\u202e", {"id":"PRIVATE_METADATA_SENTINEL"},
                 {"name":"Fictional name"}, {"displayName":"Fictional display","accountId":"PRIVATE_METADATA_SENTINEL"},
                 ["North",None,False,0,{"value":"South","id":"PRIVATE_METADATA_SENTINEL"}]]
        nodes=[{"type":kind,"attrs":{"text":"Visible","url":"https://untrusted.example.test","id":"PRIVATE_METADATA_SENTINEL"},
                "content":[{"type":"paragraph","content":[{"type":"text","text":"Fictional nested content"}]}]}
               for kind in ("panel","expand","taskItem","decisionItem","heading","codeBlock","blockquote","orderedList","unknownExtension")]
        for i,scalar in enumerate(scalars):
            with self.subTest(case=i):
                document={"key":"ABC-1","fields":{"summary":scalar,"status":scalar,"assignee":scalar,
                    "customfield_10016":scalar,"description":{"type":"doc","content":nodes[:i+1]},
                    "comments":{"total":12,"comments":[{"author":scalar,"body":nodes[i],"created":"2026-01-01"}]},
                    "issuelinks":[{"type":{"id":"fictional-relation","outward":"relates to"},"outwardIssue":{
                        "key":"ABC-2","fields":{"summary":scalar,"status":scalar,"self":"PRIVATE_METADATA_SENTINEL"}}}]}}
                (self.root/"override.json").write_text(json.dumps(document))
                actual=self.call("issue",context,"ABC-1","refresh")["issue"]; actual.pop("fetchedAt")
                result=subprocess.run(["jq","-c","-L",str(ROOT/"scripts"),"--arg","fields",fields,
                    "--arg","picker_fields","status,summary","--arg","labels","customfield_10016:Points",
                    "-f",str(ROOT/"scripts/app-issue.jq")],input=json.dumps(document),text=True,capture_output=True,check=True)
                self.assertEqual(actual,json.loads(result.stdout))

    def test_netrc_syntax_matches_actual_curl(self):
        self.use_rest();self.fixture.close();self.fixture=Fixture(self.root,tls=True)
        self.addCleanup(self.fixture.close)
        self.env.update(JIRA_PEEK_FIXTURE_HTTP=self.fixture.url,JIRA_PEEK_FIXTURE_CA=str(self.fixture.certificate))
        curl=self.root/"curl";self.fixture.curl_wrapper(curl)
        variants=[
            'machine jira.example.test login "fictional user" password "fictional pass"\n',
            'machine jira.example.test login fictional password ""\n',
            'macdef inert\nprint FICTIONAL_NEVER_EXECUTED\n\nmachine jira.example.test login fictional password fictional\n',
            'machine other.example.test login unused password unused\ndefault login fictional password fictional\n',
            'default login fallback password fallback\nmachine jira.example.test login fictional password fictional\n',
            'machine jira.example.test account ignored login fictional password fictional\n',
            'machine missing.example.test login fictional password fictional\n',
            'machine jira.example.test login "unclosed\n',
        ]
        for contents in variants:
            with self.subTest(netrc_syntax=variants.index(contents)):
                (self.root/"fixture.netrc").write_text(contents)
                context=self.connect(); before=len(self.fixture.calls)
                actual=self.call("issue",context,"ABC-1","refresh")
                rust_calls=self.fixture.calls[before:];before=len(self.fixture.calls)
                baseline=subprocess.run([str(curl),"-q","-sS","--netrc-file",str(self.root/"fixture.netrc"),
                    "https://jira.example.test/rest/api/3/issue/ABC-1"],env=self.env,text=True,capture_output=True)
                curl_calls=self.fixture.calls[before:]
                self.assertEqual(actual["ok"],baseline.returncode==0)
                self.assertEqual([c["auth_digest"] for c in rust_calls],[c["auth_digest"] for c in curl_calls])

    def test_netrc_host_case_matches_actual_curl_over_tls(self):
        self.use_rest()
        self.fixture.close()
        self.fixture=Fixture(self.root,tls=True)
        self.addCleanup(self.fixture.close)
        self.env.update(JIRA_PEEK_FIXTURE_HTTP=self.fixture.url,JIRA_PEEK_FIXTURE_CA=str(self.fixture.certificate))
        curl=self.root/"curl";self.fixture.curl_wrapper(curl)
        netrc=self.root/"fixture.netrc"
        netrc.write_text("machine JIRA.EXAMPLE.TEST login fictional password fictional\ndefault login wrong-fictional password wrong-fictional\n")
        context=self.connect()
        self.assertTrue(self.call("issue",context,"ABC-1")["ok"])
        p=subprocess.run([str(curl),"-q","-sS","--netrc-file",str(netrc),"https://jira.example.test/rest/api/3/issue/ABC-1"],
            env=self.env,text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(p.stdout)["key"],"ABC-1")
        self.assertEqual(len(self.fixture.calls),2)
        self.assertTrue(all(call["auth_is_fixture"] for call in self.fixture.calls))
        self.fixture.close()

    def test_projection_edge_cases_match_jq(self):
        self.write_config("PICKER_FIELDS=''\nREADER_FIELDS='description'\n")
        context=self.connect()
        document={"key":"ABC-1","fields":{"summary":"Fictional edge cases","description":{"type":"doc","content":[
            {"type":"orderedList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"• keep bullet"}]}]}]},
            {"type":"emoji","attrs":{"text":None,"shortName":":smile:"}},
            {"type":"emoji","attrs":{"text":False,"shortName":":wave:"}}]}}}
        (self.root/"override.json").write_text(json.dumps(document))
        actual=self.call("issue",context,"ABC-1")["issue"]; actual.pop("fetchedAt")
        result=subprocess.run(["jq","-c","-L",str(ROOT/"scripts"),"--arg","fields","description",
            "--arg","picker_fields","","--arg","labels","","-f",str(ROOT/"scripts/app-issue.jq")],
            input=json.dumps(document),text=True,capture_output=True,check=True)
        self.assertEqual(actual,json.loads(result.stdout))

    def test_marker_symlink_and_invalid_generation_fail_closed(self):
        ctx=self.connect(); marker=self.state/"connection-context"
        marker.rename(self.root/"outside-marker"); marker.symlink_to(self.root/"outside-marker")
        self.assertFalse(self.call("stamp")["ok"])
        marker.unlink(); marker.write_bytes((self.root/"outside-marker").read_bytes())
        (self.state/"cache-generations/ABC-1").write_text("1\nextra\n")
        self.assertEqual(self.call("issue",ctx,"ABC-1")["error"],"request_failed")
        self.assertFalse(self.requests())

    def test_rest_rejects_redirect_and_netrc_permissions(self):
        self.use_rest(); ctx=self.connect()
        self.fixture.hook=lambda call:(302,{"fictional":"redirect rejected"})
        self.assertEqual(self.call("issue",ctx,"ABC-1")["error"],"request_failed")
        self.assertEqual(len(self.fixture.calls),1)
        self.fixture.hook=None
        (self.root/"fixture.netrc").chmod(0o644)
        self.assertEqual(self.call("config")["error"],"connection_failed")
        self.assertEqual(len(self.fixture.calls),1)

# These exercise shell source instrumentation, the shell installer, or replaced
# utility dependencies rather than the executable's observable bridge contract.
EXCLUDED={
 "test_old_denial_cannot_delete_newer_success_after_generation_check":"Shell-source barrier; replaced by REST ordered-attempt race test",
 "test_projection_rejects_replaced_cache_with_another_field_signature":"Shell pathname barrier; Rust owns its validated snapshot under connection lock",
 "test_hash_failure_cannot_publish_a_partial_fingerprint":"SHA-256 is in-process; shell helper only",
 "test_connection_marker_reads_literal_lines_and_rejects_symlinks":"Shell helper unit test; separate Rust marker test",
 "test_connection_marker_replacement_cannot_mix_generations":"Shell read interception; Rust reads one open file",
 "test_missing_backend_dependencies_have_fixed_actionable_code":"REST no longer depends on curl; separate utility-free test",
 "test_missing_jq_is_reported_for_local_stamp_and_clear":"No jq dependency by design",
 "test_native_rest_adapter_does_not_fall_back_to_twg":"Special fake curl program; replaced by utility-free REST test",
 "test_token_rotation_retires_an_inflight_comment_request":"Special fake curl barrier; replaced by loopback rotation test",
}
for name,reason in EXCLUDED.items():
    setattr(RustParity,name,unittest.skip(reason)(lambda self:None))

if __name__=="__main__": unittest.main()
