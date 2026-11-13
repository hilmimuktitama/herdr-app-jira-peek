"""Production libcurl checks through an exclusively fictional loopback proxy."""
import json
import os
from pathlib import Path
import select
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))
from fixture import Fixture


class ProductionTransport(unittest.TestCase):
    def setUp(self):
        self.binary = Path(os.environ["JIRA_PEEK_PRODUCTION_BINARY"]).resolve()
        self.info = json.loads(subprocess.check_output([str(self.binary), "--build-info"], text=True))
        self.assertFalse(self.info["fixtureTransport"], "This suite requires a production build")
        self.temp = tempfile.TemporaryDirectory(prefix="peek-production-transport-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = Fixture(self.root, tls=True, populated=True)
        self.addCleanup(self.fixture.close)
        self.connects = []
        outer = self

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_CONNECT(self):
                outer.connects.append(self.path)
                # Never resolve or connect to the requested host. Only this
                # fictional authority is mapped to the in-process TLS fixture.
                if self.path != "jira.example.test:443":
                    self.send_error(403)
                    return
                with socket.create_connection(("127.0.0.1", outer.fixture.server.server_port)) as upstream:
                    self.send_response(200)
                    self.end_headers()
                    sockets = [self.connection, upstream]
                    while True:
                        ready, _, _ = select.select(sockets, [], [], 10)
                        if not ready: return
                        for source in ready:
                            try:
                                data = source.recv(65536)
                                if not data: return
                                (upstream if source is self.connection else self.connection).sendall(data)
                            except (ConnectionError, OSError):
                                return  # Expected when a client rejects the TLS certificate.

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True

        self.proxy = Server(("127.0.0.1", 0), Proxy)
        thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        thread.start()
        def close_proxy():
            self.proxy.shutdown()
            self.proxy.server_close()
            thread.join()
        self.addCleanup(close_proxy)
        self.config = self.root / "config"
        self.config.mkdir()
        self.netrc = self.root / "fictional.netrc"
        self.netrc.write_text("machine JIRA.EXAMPLE.TEST login fictional password fictional\n")
        self.netrc.chmod(0o600)
        (self.config / "config.sh").write_text(
            "JIRA_BASE='https://jira.example.test'\nJIRA_BACKEND='rest'\n"
            f"JIRA_NETRC_FILE='{self.netrc}'\nJIRA_PROJECTS='ABC'\n")
        self.env = {k: v for k, v in os.environ.items()
                    if "proxy" not in k.lower() and not k.startswith(("HERDR_", "VIEWER_", "TWG_", "CURL_", "SSL_", "JIRA_PEEK_"))}
        self.env.update(HOME=str(self.root), XDG_CONFIG_HOME=str(self.root),
                        HTTPS_PROXY=f"http://127.0.0.1:{self.proxy.server_address[1]}",
                        NO_PROXY="", CURL_CA_BUNDLE=str(self.fixture.certificate),
                        JIRA_PEEK_FIXTURE_HTTP="http://127.0.0.1:1", JIRA_PEEK_FIXTURE_CA="/nonexistent/fictional")
        # Both libcurl and the shell's curl -q must ignore this private .curlrc.
        (self.root / ".curlrc").write_text("proxy = http://127.0.0.1:1\n")
        self.curl = shutil.which("curl")
        self.assertIsNotNone(self.curl)
        self.context = self.call("config")["context"]

    def call(self, op, *args):
        result = subprocess.run([str(self.binary), op, str(self.config), str(self.root / "state"), *args],
                                env={**self.env, "PATH": "/nonexistent/fictional"},
                                capture_output=True, text=True, check=True, timeout=40)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def curl_issue(self):
        return subprocess.run([self.curl, "-q", "-sS", "--connect-timeout", "5", "--max-time", "30",
                               "--netrc-file", str(self.netrc), "https://jira.example.test/rest/api/3/issue/ABC-1"],
                              env=self.env, capture_output=True, text=True, timeout=40)

    def test_production_proxy_tls_authentication_and_no_utilities(self):
        for op, args in (("issue", ("ABC-1", "refresh")), ("metadata", ("ABC-1", "ABC-2")), ("comments", ("ABC-1",))):
            self.assertTrue(self.call(op, self.context, *args)["ok"])
        self.assertTrue(self.call("issue", self.context, "ABC-1")["ok"])
        self.assertEqual(len(self.fixture.calls), 3, "Cached read must not use transport")
        self.assertTrue(self.call("stamp")["ok"])
        self.assertTrue(self.call("clear", self.context)["ok"])
        baseline = self.curl_issue()
        self.assertEqual(baseline.returncode, 0)
        self.assertEqual(json.loads(baseline.stdout)["key"], "ABC-1")
        self.assertEqual(self.connects, ["jira.example.test:443"] * 4)
        self.assertEqual(len(self.fixture.calls), 4)
        self.assertTrue(all(call["auth_is_fixture"] for call in self.fixture.calls))

    def test_production_rejects_untrusted_certificate_like_curl(self):
        self.env.pop("CURL_CA_BUNDLE")
        self.assertEqual(self.call("issue", self.context, "ABC-1", "refresh"), {"ok": False, "error": "request_failed"})
        self.assertNotEqual(self.curl_issue().returncode, 0)
        self.assertEqual(len(self.fixture.calls), 0)
        self.assertEqual(self.connects, ["jira.example.test:443"] * 2)


if __name__ == "__main__": unittest.main()
