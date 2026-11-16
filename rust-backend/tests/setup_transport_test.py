"""Production setup TLS/proxy tests using entirely fictional credentials."""
import base64
import json
import os
from pathlib import Path
import select
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fictional-setup-tls-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'data/jira-peek/connection'
        self.binary = os.environ['JIRA_PEEK_PRODUCTION_BINARY']
        self.assertFalse(json.loads(subprocess.check_output([self.binary, '--build-info']))['fixtureTransport'])
        cert, key = self.home / 'cert.pem', self.home / 'key.pem'
        conf = self.home / 'openssl.cnf'
        conf.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=Fictional setup\n[ext]\nsubjectAltName=DNS:example.atlassian.net,DNS:api.atlassian.com\nbasicConstraints=critical,CA:TRUE\n')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-config', str(conf), '-keyout', str(key), '-out', str(cert)], capture_output=True, check=True)
        self.send_length = True
        self.calls = []
        self.before_response = lambda: None
        self.status, self.body = 200, b'{"accountId":"fictional-account"}'
        self.tenant = b'{"cloudId":"fictional-cloud"}'
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                outer.calls.append((self.path, self.headers.get('Authorization'), self.headers.get('Host')))
                tenant = self.path == '/_edge/tenant_info'
                body = outer.tenant if tenant else outer.body
                outer.before_response()
                self.send_response(200 if tenant else outer.status)
                self.send_header('Location', 'https://example.atlassian.net/redirect')
                if outer.send_length:
                    self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try: self.wfile.write(body)
                except (OSError, ssl.SSLError): pass
                if not outer.send_length:
                    # An EOF-delimited HTTPS body needs TLS close_notify;
                    # OpenSSL 3 correctly rejects an abrupt socket close.
                    self.wfile.flush()
                    self.connection.settimeout(2)
                    try: self.connection.unwrap().close()
                    except (OSError, ssl.SSLError): pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_CONNECT(self):
                if self.path not in ('example.atlassian.net:443', 'api.atlassian.com:443'):
                    self.send_error(403); return
                with socket.create_connection(outer.server.server_address) as upstream:
                    self.send_response(200); self.end_headers()
                    while True:
                        ready, _, _ = select.select([upstream, self.connection], [], [], 25)
                        if not ready: return
                        for source in ready:
                            try:
                                data = source.recv(65536)
                                if not data: return
                                (upstream if source is self.connection else self.connection).sendall(data)
                            except OSError: return

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
        self.proxy = Server(('127.0.0.1', 0), Proxy)
        for server in (self.server, self.proxy):
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        self.env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower() and not k.startswith(('CURL_', 'SSL_', 'JIRA_PEEK_'))}
        (self.home / '.curlrc').write_text('proxy = http://127.0.0.1:1\n')
        self.env.update(PATH='/nonexistent/fictional', HOME=str(self.home), HTTPS_PROXY=f'http://127.0.0.1:{self.proxy.server_address[1]}', NO_PROXY='', CURL_CA_BUNDLE=str(cert), JIRA_PEEK_FIXTURE_HTTP='http://127.0.0.1:1', JIRA_PEEK_FIXTURE_CA='/nonexistent')

    def call(self, *args):
        p = subprocess.run([self.binary, 'setup', *map(str, args)], env=self.env, capture_output=True, text=True, timeout=25, check=True)
        self.assertEqual(p.stderr, '')
        self.assertNotIn('fictional_token', p.stdout)
        return json.loads(p.stdout)

    def save(self, scoped=False, **changes):
        revision = self.call('inspect', self.root)['revision']
        ticket = self.call('prepare', self.root, revision)
        payload = dict(base='https://example.atlassian.net', email='tester@example.invalid', token='fictional_token', projects='ABC', cloudId='fictional-cloud' if scoped else '')
        payload.update(changes)
        Path(ticket['path']).write_text(json.dumps(payload))
        return self.call('save', self.root, ticket['ticket'])

    def test_classic_scoped_auth_order_and_cleanup(self):
        self.assertEqual(self.save(), {'ok': True})
        self.assertEqual(self.save(True), {'ok': True})
        self.assertEqual([p for p, _, _ in self.calls], ['/rest/api/3/myself', '/_edge/tenant_info', '/ex/jira/fictional-cloud/rest/api/3/myself'])
        self.assertIsNone(self.calls[1][1])
        expected = 'Basic ' + base64.b64encode(b'tester@example.invalid:fictional_token').decode()
        self.assertEqual(self.calls[0][1], expected)
        self.assertEqual(self.calls[2][1], expected)
        self.assertEqual(len(list((self.root / '.credentials').iterdir())), 1)

    def test_failures_limits_and_prior_connection(self):
        self.assertEqual(self.save(), {'ok': True})
        original = (self.root / 'config.sh').read_bytes()
        for status, body, error in [(401,b'{}','authentication_failed'), (403,b'{}','permission_denied'), (429,b'{}','rate_limited'), (302,b'{}','connection_failed'), (200,b'bad JSON','connection_failed'), (200,b'{}','connection_failed'), (200,b'x'*65537,'connection_failed')]:
            self.status, self.body = status, body
            self.assertEqual(self.save(), {'ok': False, 'error': error})
            self.assertEqual((self.root / 'config.sh').read_bytes(), original)
            self.assertEqual(len(list((self.root / '.credentials').iterdir())), 1)
        self.tenant = b'{"cloudId":"wrong-fictional"}'
        before = len(self.calls)
        self.assertEqual(self.save(True), {'ok': False, 'error': 'invalid_cloud_id'})
        self.assertEqual(len(self.calls), before + 1)

    def test_normalized_destination_and_email_apostrophe(self):
        self.assertEqual(self.save(base='HTTPS://EXAMPLE.ATLASSIAN.NET/', email="o'brien@example.invalid"), {'ok': True})
        settings = self.call('inspect', self.root)['settings']
        self.assertEqual(settings['base'], 'https://example.atlassian.net')
        self.assertEqual(settings['email'], "o'brien@example.invalid")

    def test_managed_credentials_preserve_hash_prefix_and_long_token(self):
        for email, token in [("#tester@example.invalid", "#fictional_token"),
                             ("o'brien@example.invalid", "x" * 4096)]:
            self.assertEqual(self.save(email=email, token=token), {'ok': True})
            expected = 'Basic ' + base64.b64encode((email + ':' + token).encode()).decode()
            self.assertEqual(self.calls[-1][1], expected)

    def test_preserved_assignments_and_no_token_in_config(self):
        self.root.mkdir(parents=True, mode=0o700)
        config = self.root / 'config.sh'
        config.write_text("CACHE_TTL_MIN='0'\nPICKER_LAYOUT='top'\n")
        config.chmod(0o600)
        self.assertEqual(self.save(), {'ok': True})
        self.assertIn("CACHE_TTL_MIN='0'", config.read_text())
        self.assertIn("PICKER_LAYOUT='top'", config.read_text())
        self.assertNotIn('fictional_token', config.read_text())

    def test_unverifiable_tenant_never_authenticates(self):
        for body in (b'{}', b'{"cloudId":null}', b'not JSON', b'x'*65537):
            self.tenant = body
            before = len(self.calls)
            self.assertEqual(self.save(True), {'ok': False, 'error': 'connection_failed'})
            self.assertEqual(len(self.calls), before + 1)
            self.assertIsNone(self.calls[-1][1])

    def test_verify_site_compatibility(self):
        self.assertEqual(self.call('verify-site', 'https://example.atlassian.net', 'fictional-cloud'), {'ok': True})
        self.assertIsNone(self.calls[-1][1])
        for base in ('http://example.atlassian.net', 'https://user:password@example.atlassian.net', 'https://example.atlassian.net/path'):
            self.assertEqual(self.call('verify-site', base, 'fictional-cloud'), {'ok': False, 'error': 'invalid_site'})
        self.assertEqual(len(self.calls), 1)

    def test_cleanup_preserves_foreign_and_unrecognized_files(self):
        self.assertEqual(self.save(), {'ok': True})
        auth = self.root / '.credentials'
        old = next(auth.iterdir())
        foreign = auth / 'user-owned.netrc'
        foreign.write_text('fictional foreign contents'); foreign.chmod(0o600)
        unrecognized = auth / ('.auth-' + 'a'*48 + '.netrc')
        unrecognized.write_text('fictional unrecognized contents'); unrecognized.chmod(0o600)
        self.assertEqual(self.save(), {'ok': True})
        self.assertFalse(old.exists())
        self.assertTrue(foreign.exists())
        self.assertTrue(unrecognized.exists())

    def test_precommit_failure_and_postcommit_cleanup(self):
        self.assertEqual(self.save(), {'ok': True})
        config = self.root / 'config.sh'
        original = config.read_bytes()
        def forbid_temp(): self.root.chmod(0o500)
        self.before_response = forbid_temp
        try:
            self.assertEqual(self.save(), {'ok': False, 'error': 'setup_failed'})
            self.assertEqual(config.read_bytes(), original)
        finally:
            self.root.chmod(0o700)
            self.before_response = lambda: None
        self.assertEqual(len(list((self.root / '.credentials').iterdir())), 1)
        # An obsolete credential made unsafe during verification must be retained;
        # failed best-effort cleanup cannot invalidate the newly activated config.
        old = next((self.root / '.credentials').iterdir())
        self.before_response = lambda: old.chmod(0o644)
        self.assertEqual(self.save(), {'ok': True})
        self.assertTrue(old.exists())
        self.assertNotEqual(config.read_bytes(), original)

    def test_submission_and_token_boundaries(self):
        for changes, error in [({'token': 'x'*4097}, 'invalid_token'), ({'token': 'fictional\\token'}, 'invalid_token'), ({'token': 'fictional"token'}, 'invalid_token'), ({'token': 'fictional\ntoken'}, 'invalid_token'), ({'projects': 'ABC,ABC'}, 'invalid_projects'), ({'cloudId': 'fictional_cloud'}, 'invalid_cloud_id'), ({'base': 'https://example.atlassian.net:443'}, 'invalid_site')]:
            self.assertEqual(self.save(**changes), {'ok': False, 'error': error})
        self.assertEqual(self.calls, [])
        ticket = self.call('prepare', self.root, 'missing')
        Path(ticket['path']).write_bytes(b'x'*16385)
        self.assertEqual(self.call('save', self.root, ticket['ticket']), {'ok': False, 'error': 'unsafe_path'})
        self.assertEqual(self.calls, [])

    def test_request_timeout_is_twenty_seconds(self):
        import time
        self.before_response = lambda: time.sleep(22)
        start = time.monotonic()
        self.assertEqual(self.save(), {'ok': False, 'error': 'connection_failed'})
        elapsed = time.monotonic() - start
        self.assertGreater(elapsed, 18)
        self.assertLess(elapsed, 23)
        self.assertFalse((self.root / 'config.sh').exists())

    def test_streaming_response_bound_and_tls_validation(self):
        self.send_length = False
        body = b'{"accountId":"fictional-account"}'
        self.body = body + b' '*(65536-len(body))
        self.assertEqual(self.save(), {'ok': True})
        original = (self.root / 'config.sh').read_bytes()
        self.body += b' '
        self.assertEqual(self.save(), {'ok': False, 'error': 'connection_failed'})
        self.assertEqual((self.root / 'config.sh').read_bytes(), original)
        self.env['CURL_CA_BUNDLE'] = '/nonexistent/fictional-ca'
        self.assertEqual(self.save(), {'ok': False, 'error': 'connection_failed'})
        self.assertEqual((self.root / 'config.sh').read_bytes(), original)

if __name__ == '__main__': unittest.main()
