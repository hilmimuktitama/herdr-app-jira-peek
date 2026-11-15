#!/usr/bin/env python3
"""Offline lifecycle acceptance; run with Python 3.9+ as a TEST DRIVER.

Required for the full LifecycleAcceptance suite:
  JIRA_PEEK_MANAGEMENT_BINARY: native production jira-peek-bridge.
  JIRA_PEEK_SOURCE_FIXTURE: complete integrated source + matching .release-runtime.
  JIRA_PEEK_FIXTURE_BINARY: actual native fixture-http build for rejection tests.
  JIRA_PEEK_LEGACY_SOURCE_FIXTURE: complete older supported source/package with its
    real historical Python updater (and assets if that version uses Rust).
Optional JIRA_PEEK_NEXT_SOURCE_FIXTURE supplies another matched packaged version;
otherwise a higher fictional version is generated in a temporary COPY, preserving
Rust source/build identity. The actual source checkout is never version-bumped.

Run FixtureSelfTest alone to validate the driver without integrated commands.
Missing prerequisites ERROR; there are no skipped scenario placeholders. Driver
needs a C compiler, Git, OpenSSL and curl (only for the independent setup oracle).
Product subprocess PATH allows compiled fixture host/core, POSIX shell and Git;
Python/jq/curl/SHA/OpenSSL shims fail and record attempts, including when a child
clears its environment. A separate doctor case omits those shims entirely.
No actual Herdr instance, account, credentials or network repository is used.
This is PATH dependency evidence, not an OS sandbox against absolute executables.
"""
import base64
import contextlib
import hashlib
import http.client
import importlib.util
import io
import select
import socket
import ssl
import sys
import threading
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ('python', 'python3', 'jq', 'curl', 'sha256sum', 'shasum', 'sha256', 'openssl')
STUB = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
 const char *name = strrchr(argv[0], '/'); name = name ? name + 1 : argv[0];
 if (!strcmp(name,"herdr-app") || !strcmp(name,"hc")) {
  if (argc == 2 && !strcmp(argv[1],"--version")) {
   puts(!strcmp(name,"hc") ? "hc 0.1.19" : "herdr-app 0.1.10"); return 0;
  }
  if (!strcmp(name,"herdr-app") && argc == 3 && !strcmp(argv[1],"check")) return 0;
  return 78; /* Unsupported host interactions must never look successful. */
 }
 const char *log = getenv("DENIED_LOG"); FILE *f = log ? fopen(log,"a") : NULL;
 if (f) { fprintf(f,"%s\n",name); fclose(f); }
 return 97;
}
'''


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_native(path):
    with path.open('rb') as stream:
        magic = stream.read(4)
    if magic not in (b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                     b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe',
                     b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf'):
        raise RuntimeError('Prerequisite must be a native executable, not an interpreter shim: ' + str(path))
    if not os.access(path, os.X_OK):
        raise RuntimeError('Prerequisite native binary is not executable: ' + str(path))


def snapshot(root):
    """Include directory modes, link targets, bytes and file modes, not atime."""
    result = {}
    if not root.exists():
        return result
    for path in [root, *sorted(root.rglob('*'))]:
        mode = path.lstat().st_mode
        result[str(path.relative_to(root))] = (
            stat.S_IMODE(mode), os.readlink(path) if path.is_symlink() else
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return result


def required_path(name, directory=False):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('Prerequisite missing: set ' + name)
    path = Path(value).resolve(strict=True)
    if directory != path.is_dir():
        raise RuntimeError('Invalid prerequisite type: ' + name)
    return path


# The HTTPS CONNECT relay follows transport_test.py: it never resolves a
# requested authority and forwards only the one fictional authority to loopback.
class JiraTLSFixture:
    authority = 'fictional-lifecycle.atlassian.net'
    token = 'fictional_acceptance_token_123'
    email = 'reader@example.invalid'

    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.calls = []
        self.connects = []
        self.status = 200
        openssl = shutil.which('openssl')
        if not openssl:
            raise RuntimeError('Driver prerequisite missing: openssl for ephemeral TLS certificates')
        self.certificate = root / 'ca.pem'
        config = root / 'openssl.cnf'
        config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n'
                          '[dn]\nCN=Fictional lifecycle CA\n[ca]\nbasicConstraints=critical,CA:TRUE\n'
                          'keyUsage=critical,keyCertSign,cRLSign\n[server]\n'
                          'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
                          'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:' + self.authority + '\n')
        ca_key, key = root / 'ca-key.pem', root / 'key.pem'
        csr, server_cert = root / 'server.csr', root / 'server.pem'
        commands = [
            [openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
             '-config', str(config), '-keyout', str(ca_key), '-out', str(self.certificate)],
            [openssl, 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + self.authority,
             '-keyout', str(key), '-out', str(csr)],
            [openssl, 'x509', '-req', '-in', str(csr), '-CA', str(self.certificate), '-CAkey', str(ca_key),
             '-set_serial', '1', '-days', '1', '-extfile', str(config), '-extensions', 'server',
             '-out', str(server_cert)],
        ]
        for command in commands:
            subprocess.run(command, capture_output=True, check=True, timeout=30)
        ca_key.chmod(0o600)
        key.chmod(0o600)
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                expected = 'Basic ' + base64.b64encode(
                    (fixture.email + ':' + fixture.token).encode()).decode()
                fixture.calls.append({'method': self.command, 'path': self.path,
                                      'authenticated': self.headers.get('Authorization') == expected})
                code = fixture.status
                if self.path.startswith('/rest/api/3/myself'):
                    body = {'accountId': 'fictional-reader', 'active': True}
                elif self.path.startswith('/rest/api/3/issue/ABC-1/comment'):
                    body = {'comments': [], 'startAt': 0, 'total': 0, 'maxResults': 100}
                elif self.path.startswith('/rest/api/3/issue/ABC-1'):
                    body = {'key': 'ABC-1', 'fields': {'summary': 'Fictional orchard plan',
                            'status': {'name': 'Open'}, 'description': 'Entirely invented acceptance data.'}}
                else:
                    code, body = 404, {'errorMessages': ['FICTIONAL_RAW_RESPONSE_SENTINEL']}
                if code != 200:
                    body = {'errorMessages': ['FICTIONAL_RAW_RESPONSE_SENTINEL']}
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(server_cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_CONNECT(self):
                fixture.connects.append(self.path)
                if self.path != fixture.authority + ':443':
                    self.send_error(403)
                    return
                with socket.create_connection(('127.0.0.1', fixture.server.server_port), timeout=5) as upstream:
                    self.send_response(200)
                    self.end_headers()
                    sockets = [self.connection, upstream]
                    while True:
                        ready, _, _ = select.select(sockets, [], [], 5)
                        if not ready:
                            return
                        for source in ready:
                            try:
                                data = source.recv(65536)
                                if not data:
                                    return
                                (upstream if source is self.connection else self.connection).sendall(data)
                            except OSError:
                                return

        self.proxy = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
        self.threads = []
        for server in (self.server, self.proxy):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self):
        for server, thread in zip((self.server, self.proxy), self.threads):
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def environment(self):
        return {'HTTPS_PROXY': 'http://127.0.0.1:' + str(self.proxy.server_port),
                'CURL_CA_BUNDLE': str(self.certificate), 'NO_PROXY': ''}

    def request(self, trusted=True, authority=None, path='/rest/api/3/myself'):
        context = ssl.create_default_context(cafile=str(self.certificate) if trusted else None)
        client = http.client.HTTPSConnection('127.0.0.1', self.proxy.server_port,
                                             context=context, timeout=5)
        client.set_tunnel(authority or self.authority, 443)
        try:
            auth = base64.b64encode((self.email + ':' + self.token).encode()).decode()
            client.request('GET', path, headers={'Authorization': 'Basic ' + auth})
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()


def copy_source(source, destination):
    """Copy only public package inputs; never copy a checkout's Git/config state."""
    destination.mkdir()
    for name in ('scripts', 'mods', 'docs', 'rust-backend', '.release-runtime', 'tests'):
        if (source / name).is_dir():
            shutil.copytree(source / name, destination / name,
                            ignore=shutil.ignore_patterns('target', '__pycache__', '.git', '*.pyc'))
    for name in ('package.json', 'LICENSE', 'config.example.sh', 'CHANGELOG.md',
                 'README.md', 'RECIPE.md', 'keys.json', 'THIRD_PARTY_NOTICES.md'):
        if (source / name).is_file():
            shutil.copy2(source / name, destination / name)
    return destination


def source_version(source):
    return json.loads((source / 'package.json').read_text())['version']


def versioned_source(source, destination, version):
    """Only fictional copied package metadata changes; Rust source identity stays exact."""
    copy_source(source, destination)
    for name in ('package.json', 'mods/jira-peek/mod.json'):
        path = destination / name
        metadata = json.loads(path.read_text())
        metadata['version'] = version
        path.write_text(json.dumps(metadata) + '\n')
    for path in (destination / '.release-runtime').glob('*.json'):
        manifest = json.loads(path.read_text())
        manifest['releaseVersion'] = version
        path.write_text(json.dumps(manifest) + '\n')
    return destination


class LocalReleases:
    repository = 'https://github.com/hilmimuktitama/herdr-app-jira-peek.git'

    def __init__(self, root, sources):
        self.root = root
        self.git_binary = shutil.which('git')
        if not self.git_binary:
            raise RuntimeError('Driver/product prerequisite missing: Git')
        self.env = {'PATH': os.defpath, 'HOME': str(root.parent), 'LANG': 'C',
                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                    'GIT_ALLOW_PROTOCOL': 'file', 'GIT_TERMINAL_PROMPT': '0'}
        root.mkdir()
        self.git('init', '--quiet')
        self.git('config', 'user.name', 'Fictional Release Author')
        self.git('config', 'user.email', 'release@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'tag.gpgsign', 'false')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')
        for source in sources:
            for path in root.iterdir():
                if path.name != '.git':
                    shutil.rmtree(path) if path.is_dir() else path.unlink()
            # copy_source expects an absent destination, so stage then move files.
            with tempfile.TemporaryDirectory(dir=root.parent) as temporary:
                staged = copy_source(source, Path(temporary) / 'source')
                for path in staged.iterdir():
                    shutil.move(str(path), root / path.name)
            self.git('add', '--force', '.')
            self.git('commit', '--quiet', '-m', 'Fictional release ' + source_version(source))
            self.git('tag', 'v' + source_version(source))

    def git(self, *args):
        return subprocess.run([self.git_binary, '-c', 'core.hooksPath=/dev/null', *args],
                              cwd=self.root, env=self.env, check=True, text=True,
                              capture_output=True, timeout=45).stdout.strip()

    def environment(self):
        return {'GIT_CONFIG_COUNT': '1',
                'GIT_CONFIG_KEY_0': 'url.' + self.root.as_uri() + '.insteadOf',
                'GIT_CONFIG_VALUE_0': self.repository,
                'GIT_EXEC_PATH': self.git('--exec-path')}


def stock_layout(home):
    layouts = home / 'layouts'
    layouts.mkdir(exist_ok=True)
    (layouts / 'main.json').write_text(json.dumps({'id': 'root', 'children': [
        {'id': 'tabs', 'content': {'mod': 'tabs'}},
        {'id': 'work-body', 'type': 'row', 'children': []}]}))
    toolbar = home / 'mods/tabs'
    toolbar.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'tests/fixtures/tabs.js', toolbar / 'main.js')


class LifecycleAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = required_path('JIRA_PEEK_MANAGEMENT_BINARY')
        require_native(cls.binary)
        cls.source = required_path('JIRA_PEEK_SOURCE_FIXTURE', directory=True)
        cls.compiler = shutil.which('cc')
        if not cls.compiler:
            raise RuntimeError('Driver prerequisite missing: C compiler for interpreter-free host/denial fixtures')
        if not (cls.source / '.release-runtime').is_dir():
            raise RuntimeError('Source fixture requires matching production .release-runtime assets')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='fictional-lifecycle-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'app'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        source = self.root / 'stub.c'
        source.write_text(STUB.replace('getenv("DENIED_LOG")', json.dumps(str(self.root / 'denied'))))
        stub = self.root / 'stub'
        subprocess.run([self.compiler, str(source), '-o', str(stub)], check=True, capture_output=True)
        for name in (*FORBIDDEN, 'herdr-app', 'hc'):
            shutil.copy2(stub, self.bin / name)
        (self.bin / 'sh').symlink_to('/bin/sh')
        self.denied = self.root / 'denied'
        # Deliberately do not inherit PATH, proxies, credentials, host settings,
        # executable overrides or Git configuration from the developer session.
        self.env = dict(PATH=str(self.bin), HOME=str(self.root),
                        XDG_CONFIG_HOME=str(self.root / 'xdg'),
                        HERDR_APP_HOME=str(self.home), TMPDIR=str(self.root),
                        DENIED_LOG=str(self.denied), LANG='C',
                        HTTPS_PROXY='http://127.0.0.1:1', HTTP_PROXY='http://127.0.0.1:1',
                        ALL_PROXY='http://127.0.0.1:1', NO_PROXY='',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                        GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='file')
        self.assertIs(self.json_call('--build-info')['fixtureTransport'], False,
                      'Acceptance requires production binary, not fixture transport')

    def call(self, *args, success=True, binary=None):
        result = subprocess.run([str(binary or self.binary), *map(str, args)], env=self.env,
                                cwd=self.root, text=True, capture_output=True, timeout=90)
        self.assertFalse(self.denied.exists(), 'Forbidden product dependency invoked: ' +
                         (self.denied.read_text() if self.denied.exists() else ''))
        for secret in (JiraTLSFixture.token, 'FICTIONAL_RAW_RESPONSE_SENTINEL'):
            self.assertNotIn(secret, result.stdout + result.stderr)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, 'Failure must have nonzero exit status')
        return result

    def json_call(self, *args, **kwargs):
        return json.loads(self.call(*args, **kwargs).stdout)

    def install(self, source=None, *flags, native_required=True):
        self.call('manage', 'install', '--source-root', source or self.source,
                  '--app-home', self.home, '--check', *flags)
        return self.verify_bundle(native_required=native_required)

    def verify_bundle(self, native_required=True):
        target = self.home / 'mods/jira-peek'
        manifest = json.loads((target / 'install.json').read_text())
        self.assertEqual(manifest['owner'], 'herdr-jira-peek')
        self.assertTrue(manifest['files'])
        for name, digest in manifest['files'].items():
            path = target / name
            self.assertTrue(inside(path.resolve(), target.resolve()))
            self.assertFalse(path.is_symlink())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)
        binary = target / 'runtime/jira-peek-bridge'
        if native_required or binary.exists():
            require_native(binary)
            self.assertTrue(binary.stat().st_mode & stat.S_IXUSR)
        return manifest

    def test_doctor_without_forbidden_utilities(self):
        for name in FORBIDDEN:
            (self.bin / name).unlink()
        before = snapshot(self.root)
        report = self.json_call('manage', 'doctor', '--json')
        self.assertTrue(report['ok'], report)
        self.assertEqual(snapshot(self.root), before)

    def test_clear_cache_preserves_credentials_and_bridge_clear_contract(self):
        self.install()
        fixture = self.start_tls()
        connection, saved = self.save_connection(fixture)
        self.assertEqual(saved, {'ok': True})
        state = self.read_issue(connection)
        binary = self.installed_binary()
        context = self.json_call('stamp', connection, state, binary=binary)['context']
        # Historical bridge clear still requires config, state root and current context.
        self.assertEqual(self.json_call('clear', connection, state, context, binary=binary), {'ok': True})
        self.assertEqual(self.json_call('clear', connection, state, context, binary=binary),
                         {'ok': False, 'error': 'connection_changed'})
        self.read_issue(connection)
        private = snapshot(connection)
        before = snapshot(state)
        # Low-level helper selects one initialized connection namespace, not a root.
        self.call('manage', 'clear-cache', '--state-dir', state, success=False)
        self.assertEqual(snapshot(state), before)
        namespace, = (state / 'connections').iterdir()
        keep = namespace / 'fictional-session.json'
        keep.write_text('{"preserve":true}\n')
        cached = list((namespace / 'cache').glob('*.json'))
        self.assertTrue(cached, 'Fixture must populate actual issue cache before testing clear')
        old_context = self.json_call('stamp', connection, state, binary=binary)['context']
        self.call('manage', 'clear-cache', '--state-dir', namespace)
        self.assertFalse(list((namespace / 'cache').glob('*.json')))
        self.assertEqual(keep.read_text(), '{"preserve":true}\n')
        self.assertEqual(snapshot(connection), private)
        self.assertNotEqual(self.json_call('stamp', connection, state, binary=binary)['context'], old_context)

    def test_doctor_is_read_only(self):
        before = snapshot(self.root)
        report = self.json_call('manage', 'doctor', '--json')
        self.assertTrue(report['ok'], report)
        self.assertEqual(snapshot(self.root), before)

    def test_install_update_rollback_preserve_settings_hashes_and_modes(self):
        (self.home / 'keys.json').write_text('{"fictional":"preserve"}\n')
        settings = self.home / 'data/jira-peek'
        settings.mkdir(parents=True)
        (settings / 'fields.json').write_text('{"version":1,"connections":[]}\n')
        original_settings = snapshot(settings)
        self.install()
        target = self.home / 'mods/jira-peek'
        original = snapshot(target)
        self.install(self.source, '--update')
        backups = list((self.home / 'mods').glob('.jira-peek-backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(snapshot(backups[0]), original)
        self.call('manage', 'rollback', backups[0].name, '--app-home', self.home, '--check')
        self.verify_bundle()
        self.assertEqual(snapshot(target), original)
        self.assertEqual(snapshot(settings), original_settings)
        self.assertEqual((self.home / 'keys.json').read_text(), '{"fictional":"preserve"}\n')

    def test_edited_managed_file_refuses_replacement(self):
        self.install()
        (self.home / 'mods/jira-peek/main.js').write_text('// fictional personal edit\n')
        before = snapshot(self.home)
        self.call('manage', 'install', '--source-root', self.source, '--app-home', self.home,
                  '--update', success=False)
        self.assertEqual(snapshot(self.home), before)

    def test_setup_inspect_prepare_cancel_contract(self):
        connection = self.home / 'data/jira-peek/connection'
        before = snapshot(self.home)
        report = self.json_call('setup', 'inspect', connection)
        self.assertTrue(report['ok'])
        self.assertEqual(report['revision'], 'missing')
        self.assertEqual(snapshot(self.home), before)
        ticket = self.json_call('setup', 'prepare', connection, report['revision'])
        self.assertTrue(ticket['ok'])
        self.assertRegex(ticket['ticket'], r'^[0-9a-f]{48}$')
        request = Path(ticket['path'])
        self.assertTrue(inside(request.resolve(), connection))
        self.assertEqual(request.read_bytes(), b'')
        self.assertEqual(stat.S_IMODE(request.stat().st_mode), 0o600)
        for _ in range(2):
            self.assertEqual(self.json_call('setup', 'cancel', connection, ticket['ticket']), {'ok': True})
        self.assertFalse(request.exists())



    def installed_binary(self):
        return self.home / 'mods/jira-peek/runtime/jira-peek-bridge'

    def releases(self, include_current=True, older=None):
        version = source_version(self.source)
        major, minor, patch = map(int, version.split('.'))
        value = os.environ.get('JIRA_PEEK_NEXT_SOURCE_FIXTURE')
        next_source = (Path(value).resolve(strict=True) if value else
                       versioned_source(self.source, self.root / 'next', f'{major}.{minor}.{patch + 1}'))
        self.assertGreater(tuple(map(int, source_version(next_source).split('.'))), (major, minor, patch))
        sources = ([older] if older else []) + ([self.source] if include_current else []) + [next_source]
        releases = LocalReleases(self.root / 'remote', sources)
        (self.bin / 'git').symlink_to(releases.git_binary)
        self.env.update(releases.environment())
        return next_source, releases

    def update(self, *flags, success=True):
        return self.call('manage', 'update', '--app-home', self.home, *flags, success=success)

    def save_connection(self, fixture):
        connection = self.home / 'data/jira-peek/connection'
        binary = self.installed_binary()
        report = self.json_call('setup', 'inspect', connection, binary=binary)
        ticket = self.json_call('setup', 'prepare', connection, report['revision'], binary=binary)
        self.assertTrue(ticket['ok'])
        request = Path(ticket['path'])
        self.assertTrue(inside(request.resolve(), connection))
        request.write_text(json.dumps({'base': 'https://' + fixture.authority,
                           'email': fixture.email, 'token': fixture.token, 'projects': 'ABC', 'cloudId': ''}))
        request.chmod(0o600)
        result = self.json_call('setup', 'save', connection, ticket['ticket'], binary=binary)
        self.assertFalse(request.exists(), 'Submitted secret must be consumed')
        return connection, result

    def start_tls(self):
        fixture = JiraTLSFixture(self.root / 'tls')
        self.addCleanup(fixture.close)
        self.env.update(fixture.environment())
        return fixture

    def read_issue(self, connection):
        state = self.home / 'data/jira-peek/acceptance-cache'
        binary = self.installed_binary()
        context = self.json_call('config', connection, state, binary=binary)['context']
        issue = self.json_call('issue', connection, state, context, 'ABC-1', 'refresh', binary=binary)
        self.assertTrue(issue['ok'], issue)
        self.assertIn('Fictional orchard plan', json.dumps(issue))
        self.assertTrue(self.json_call('comments', connection, state, context, 'ABC-1', binary=binary)['ok'])
        return state

    def test_installed_setup_tls_read_git_update_and_rollback(self):
        self.install()
        stock_layout(self.home)
        fixture = self.start_tls()
        connection, saved = self.save_connection(fixture)
        self.assertEqual(saved, {'ok': True})
        self.assertEqual(stat.S_IMODE((connection / 'config.sh').stat().st_mode), 0o600)
        credentials = list((connection / '.credentials').glob('*.netrc'))
        self.assertEqual(len(credentials), 1)
        self.assertEqual(stat.S_IMODE(credentials[0].stat().st_mode), 0o600)
        private = snapshot(connection)
        self.read_issue(connection)
        original = snapshot(self.home / 'mods/jira-peek')
        next_source, _ = self.releases()
        self.update('--version', source_version(next_source))
        self.assertEqual(self.verify_bundle()['version'], source_version(next_source))
        self.assertEqual(snapshot(connection), private)
        self.read_issue(connection)
        backups = list((self.home / 'mods').glob('.jira-peek-backup-*'))
        self.assertEqual(len(backups), 1)
        self.call('manage', 'rollback', backups[0].name, '--app-home', self.home, '--check')
        self.assertEqual(snapshot(self.home / 'mods/jira-peek'), original)
        self.assertEqual(snapshot(connection), private)
        self.read_issue(connection)
        self.assertEqual(fixture.calls[0]['path'], '/rest/api/3/myself')
        self.assertTrue(all(call['method'] == 'GET' and call['authenticated'] for call in fixture.calls))
        self.assertTrue(all(host == fixture.authority + ':443' for host in fixture.connects))

    def test_setup_tls_and_authentication_failure_preserve_previous_connection(self):
        self.install()
        fixture = self.start_tls()
        connection, result = self.save_connection(fixture)
        self.assertEqual(result, {'ok': True})
        config = (connection / 'config.sh').read_bytes()
        credentials = snapshot(connection / '.credentials')
        for status, error in ((401, 'authentication_failed'), (403, 'permission_denied'),
                              (429, 'rate_limited'), (503, 'connection_failed')):
            with self.subTest(status=status):
                fixture.status = status
                _, result = self.save_connection(fixture)
                self.assertEqual(result, {'ok': False, 'error': error})
                self.assertEqual((connection / 'config.sh').read_bytes(), config)
                self.assertEqual(snapshot(connection / '.credentials'), credentials)
        fixture.status = 200
        self.env.pop('CURL_CA_BUNDLE')
        before = len(fixture.calls)
        _, result = self.save_connection(fixture)
        self.assertEqual(result, {'ok': False, 'error': 'connection_failed'})
        self.assertEqual(len(fixture.calls), before, 'Untrusted TLS must fail before HTTP/authentication')
        self.assertEqual((connection / 'config.sh').read_bytes(), config)
        self.assertEqual(snapshot(connection / '.credentials'), credentials)

    def test_git_check_upgrade_downgrade_and_unknown_release(self):
        self.install()
        stock_layout(self.home)
        next_source, _ = self.releases()
        old, new = source_version(self.source), source_version(next_source)
        before = snapshot(self.home)
        report = self.update('--check').stdout
        self.assertIn(new, report)
        self.assertEqual(snapshot(self.home), before)
        self.update('--version', '99999.0.0', success=False)
        self.assertEqual(snapshot(self.home), before)
        self.update()  # Highest numbered release, explicit user action.
        self.assertEqual(self.verify_bundle()['version'], new)
        before = snapshot(self.home)
        self.update('--check', '--version', old)
        self.assertEqual(snapshot(self.home), before)
        self.update('--version', old, success=False)
        self.assertEqual(snapshot(self.home), before)
        self.update('--version', old, '--allow-downgrade')
        self.assertEqual(self.verify_bundle()['version'], old)
        before = snapshot(self.home)
        self.update('--version', old)
        self.assertEqual(snapshot(self.home), before, 'Same-version update must not replace or repair')

    def test_implicit_downgrade_requires_explicit_version_even_with_flag(self):
        self.install()
        major, minor, patch = map(int, source_version(self.source).split('.'))
        newer = versioned_source(self.source, self.root / 'newer', f'{major}.{minor}.{patch + 1}')
        self.install(newer, '--update')
        remote = LocalReleases(self.root / 'remote', [self.source])
        (self.bin / 'git').symlink_to(remote.git_binary)
        self.env.update(remote.environment())
        before = snapshot(self.home)
        for flags in ((), ('--allow-downgrade',)):
            with self.subTest(flags=flags):
                self.update(*flags, success=False)
                self.assertEqual(snapshot(self.home), before)
        self.update('--version', source_version(self.source), '--allow-downgrade')
        self.assertEqual(self.verify_bundle()['version'], source_version(self.source))

    def test_git_update_refuses_edited_bundle(self):
        self.install()
        self.releases()
        (self.home / 'mods/jira-peek/main.js').write_text('// fictional personal edit\n')
        before = snapshot(self.home)
        self.update(success=False)
        self.assertEqual(snapshot(self.home), before)

    def test_partial_integration_diagnose_conflict_preservation_and_repair(self):
        self.install()
        stock_layout(self.home)
        source_layout = (self.home / 'layouts/main.json').read_bytes()
        self.call('manage', 'integration', 'repair', '--app-home', self.home, '--layout', 'main')
        layout = self.home / 'layouts/main-jira-peek.json'
        toolbar = self.home / 'mods/tabs-jira-peek/main.js'
        expected_layout = layout.read_bytes()
        self.assertIn('jira-peek', toolbar.read_text())
        layout.unlink()  # A real partial result: toolbar published, layout absent.
        before = snapshot(self.home)
        diagnosis = self.call('manage', 'integration', 'diagnose', '--app-home', self.home,
                              '--layout', 'main').stdout.lower()
        self.assertIn('partial', diagnosis)
        self.assertEqual(snapshot(self.home), before)
        self.call('manage', 'integration', 'repair', '--app-home', self.home, '--layout', 'main')
        self.assertEqual(layout.read_bytes(), expected_layout)
        layout.unlink()
        toolbar.write_text('// fictional personal toolbar edit\n')
        before = snapshot(self.home)
        self.call('manage', 'integration', 'repair', '--app-home', self.home, '--layout', 'main', success=False)
        self.assertEqual(snapshot(self.home), before)
        next_source, _ = self.releases()
        output = self.update('--version', source_version(next_source)).stdout.lower()
        self.assertEqual(self.verify_bundle()['version'], source_version(next_source))
        self.assertRegex(output, r'integration|toolbar')
        self.assertRegex(output, r'preserv|conflict|skip|incomplete|repair')
        self.assertFalse(layout.exists())
        self.assertEqual(toolbar.read_text(), '// fictional personal toolbar edit\n')
        self.assertEqual((self.home / 'layouts/main.json').read_bytes(), source_layout)

    def test_fixture_enabled_packaged_binary_rejected_without_replacement(self):
        fixture_binary = required_path('JIRA_PEEK_FIXTURE_BINARY')
        require_native(fixture_binary)
        info = self.json_call('--build-info', binary=fixture_binary)
        self.assertIs(info['fixtureTransport'], True, 'Supply an actual fixture-enabled native build')
        self.install()
        source = copy_source(self.source, self.root / 'rejected-source')
        manifests = list((source / '.release-runtime').glob('*.json'))
        self.assertTrue(manifests)
        replaced = False
        for path in manifests:
            manifest = json.loads(path.read_text())
            if manifest['platform'] != info['os'] + '-' + info['arch']:
                continue
            name = next(name for name in manifest['files'] if not name.endswith('-NOTICES.txt'))
            binary = source / '.release-runtime' / name
            shutil.copy2(fixture_binary, binary)
            manifest['files'][name] = {'size': binary.stat().st_size,
                                      'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
            manifest['buildInfo'] = info
            path.write_text(json.dumps(manifest))
            replaced = True
        self.assertTrue(replaced)
        before = snapshot(self.home)
        self.call('manage', 'install', '--source-root', source, '--app-home', self.home,
                  '--update', success=False)
        self.assertEqual(snapshot(self.home), before)

    def test_rust_update_to_older_supported_bundle_and_rollback(self):
        legacy = required_path('JIRA_PEEK_LEGACY_SOURCE_FIXTURE', directory=True)
        old = source_version(legacy)
        self.assertLess(tuple(map(int, old.split('.'))), tuple(map(int, source_version(self.source).split('.'))))
        self.install()
        stock_layout(self.home)
        original = snapshot(self.home / 'mods/jira-peek')
        self.releases(older=legacy)
        self.update('--version', old, '--allow-downgrade')
        self.assertEqual(self.verify_bundle(native_required=False)['version'], old)
        backup, = (self.home / 'mods').glob('.jira-peek-backup-*')
        # Keep invoking the NEW binary: a historical installed helper may not restore modes.
        self.call('manage', 'rollback', backup.name, '--app-home', self.home, '--check')
        self.assertEqual(snapshot(self.home / 'mods/jira-peek'), original)

    def test_historical_python_updater_invokes_new_source_installer(self):
        legacy = required_path('JIRA_PEEK_LEGACY_SOURCE_FIXTURE', directory=True)
        old = source_version(legacy)
        current = source_version(self.source)
        self.assertLess(tuple(map(int, old.split('.'))), tuple(map(int, current.split('.'))))
        self.install(legacy, native_required=False)
        stock_layout(self.home)
        # Only old and current tags: the old updater must fetch the actual new source.
        releases = LocalReleases(self.root / 'remote', [legacy, self.source])
        (self.bin / 'git').symlink_to(releases.git_binary)
        self.env.update(releases.environment())
        settings = self.home / 'data/jira-peek/fields.json'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"version":1,"connections":[]}\n')
        original = settings.read_bytes()
        helper = self.home / 'mods/jira-peek/runtime/update-app.py'
        self.assertTrue(helper.is_file(), 'Historical fixture must include its real Python updater')
        # Python is explicitly the historical driver. The new installer it spawns
        # inherits the forbidden-utility PATH; compatibility files alone are allowed.
        result = subprocess.run([sys.executable, '-B', str(helper), '--app-home', str(self.home),
                                 '--version', current], env=self.env, cwd=self.root,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.denied.exists(), 'New source installer invoked forbidden PATH utility')
        self.assertEqual(self.verify_bundle()['version'], current)
        self.assertEqual(settings.read_bytes(), original)
        backup, = (self.home / 'mods').glob('.jira-peek-backup-*')
        self.assertEqual(json.loads((backup / 'install.json').read_text())['version'], old)


def load_oracle(name):
    spec = importlib.util.spec_from_file_location('lifecycle_oracle_' + name.replace('-', '_'), ROOT / 'scripts' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixtureSelfTest(unittest.TestCase):
    def test_tls_fixture_trust_authentication_and_authority_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = JiraTLSFixture(Path(directory) / 'tls')
            try:
                self.assertEqual(fixture.request(), (200, {'accountId': 'fictional-reader', 'active': True}))
                self.assertTrue(fixture.calls[-1]['authenticated'])
                status, issue = fixture.request(path='/rest/api/3/issue/ABC-1?fields=summary')
                self.assertEqual(status, 200)
                self.assertEqual(issue['key'], 'ABC-1')
                self.assertEqual(issue['fields']['summary'], 'Fictional orchard plan')
                self.assertEqual(fixture.request(path='/rest/api/3/issue/ABC-1/comment')[1]['comments'], [])
                fixture.status = 401
                self.assertEqual(fixture.request()[0], 401)
                count = len(fixture.calls)
                with self.assertRaises(ssl.SSLCertVerificationError):
                    fixture.request(trusted=False)
                with self.assertRaises(OSError):
                    fixture.request(authority='unrelated.example.invalid')
                self.assertEqual(len(fixture.calls), count)
            finally:
                fixture.close()

    def test_tls_fixture_with_historical_setup_oracle(self):
        if not shutil.which('curl'):
            raise RuntimeError('Oracle prerequisite missing: curl (driver only)')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fixture = JiraTLSFixture(root / 'tls')
            try:
                connection = root / 'app/data/jira-peek/connection'
                env = {'PATH': os.defpath, 'HOME': str(root), 'LANG': 'C', **fixture.environment()}
                # Explicit driver dependency, never used by LifecycleAcceptance.call.
                env['PATH'] = str(Path(shutil.which('curl')).parent) + os.pathsep + os.defpath
                def call(*args):
                    result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/app-setup.py'),
                                             *map(str, args)], env=env, capture_output=True,
                                            text=True, check=True, timeout=30)
                    self.assertNotIn(fixture.token, result.stdout + result.stderr)
                    return json.loads(result.stdout)
                ticket = call('prepare', connection, call('inspect', connection)['revision'])
                self.assertTrue(ticket['ok'])
                path = Path(ticket['path'])
                path.write_text(json.dumps({'base': 'https://' + fixture.authority,
                                'email': fixture.email, 'token': fixture.token, 'projects': 'ABC', 'cloudId': ''}))
                path.chmod(0o600)
                self.assertEqual(call('save', connection, ticket['ticket']), {'ok': True})
                self.assertTrue(call('inspect', connection)['configured'])
                self.assertEqual(fixture.calls, [{'method': 'GET', 'path': '/rest/api/3/myself', 'authenticated': True}])
            finally:
                fixture.close()

    def test_local_git_tags_fetch_and_network_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'input'
            (source / 'mods/jira-peek').mkdir(parents=True)
            (source / 'scripts').mkdir()
            (source / 'scripts/install-app.py').write_text('# Fictional Git fixture marker\n')
            (source / '.release-runtime').mkdir()
            for name in ('package.json', 'mods/jira-peek/mod.json'):
                (source / name).write_text('{"version":"0.1.0"}\n')
            (source / '.release-runtime/fixture.json').write_text('{"releaseVersion":"0.1.0"}\n')
            original = snapshot(source)
            next_source = versioned_source(source, root / 'next', '0.1.1')
            self.assertEqual(snapshot(source), original)
            self.assertEqual(json.loads((next_source / '.release-runtime/fixture.json').read_text())['releaseVersion'], '0.1.1')
            remote = LocalReleases(root / 'remote', [source, next_source])
            env = {**remote.env, **remote.environment()}
            args = [remote.git_binary, '-c', 'core.hooksPath=/dev/null']
            result = subprocess.run([*args, 'ls-remote', '--tags', remote.repository], env=env,
                                    capture_output=True, text=True, check=True, timeout=15)
            self.assertIn('refs/tags/v0.1.0', result.stdout)
            self.assertIn('refs/tags/v0.1.1', result.stdout)
            blocked = subprocess.run([*args, 'ls-remote', 'https://unrelated.example.invalid/repo'], env=env,
                                     capture_output=True, text=True, timeout=15)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("transport 'https' not allowed", blocked.stderr)
            checkout = root / 'checkout'
            subprocess.run([*args, 'clone', '--quiet', '--branch', 'v0.1.0', remote.repository, str(checkout)],
                           env=env, capture_output=True, check=True, timeout=15)
            self.assertEqual(source_version(checkout), '0.1.0')
            # The unmodified historical updater independently consumes the same tags/config.
            updater = load_oracle('update-app.py')
            with mock.patch.dict(os.environ, env, clear=True):
                tags = updater.release_tags()
                self.assertEqual(set(tags), {'0.1.0', '0.1.1'})
                fetched = root / 'historical-fetch'
                updater.download_release(fetched, '0.1.1', tags['0.1.1'])
                self.assertEqual(source_version(fetched), '0.1.1')

    def test_partial_integration_fixture_against_independent_oracle(self):
        installer = load_oracle('install-app.py')
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            stock_layout(home)
            source = snapshot(home)
            plan = installer.attachment_plan(home, 'main')
            with contextlib.redirect_stdout(io.StringIO()):
                installer.attach(plan, home)
            layout = home / 'layouts/main-jira-peek.json'
            toolbar = home / 'mods/tabs-jira-peek/main.js'
            expected = layout.read_bytes()
            layout.unlink()
            before = snapshot(home)
            # A matching subset is repairable, without overwriting the survivor.
            plan = installer.attachment_plan(home, 'main')
            self.assertEqual(snapshot(home), before)
            with contextlib.redirect_stdout(io.StringIO()):
                installer.attach(plan, home)
            self.assertEqual(layout.read_bytes(), expected)
            layout.unlink()
            toolbar.write_text('// fictional personal edit\n')
            before = snapshot(home)
            with self.assertRaises(ValueError):
                installer.attachment_plan(home, 'main')
            self.assertEqual(snapshot(home), before)
            self.assertEqual(snapshot(home)['layouts/main.json'], source['layouts/main.json'])


    def test_compiled_denial_fixture_records_and_fails(self):
        compiler = shutil.which('cc')
        if not compiler:
            raise RuntimeError('Driver prerequisite missing: C compiler')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'stub.c'
            source.write_text(STUB.replace('getenv("DENIED_LOG")', json.dumps(str(root / 'denied'))))
            binary = root / 'python3'
            subprocess.run([compiler, str(source), '-o', str(binary)], check=True, capture_output=True)
            log = root / 'denied'
            require_native(binary)
            result = subprocess.run([str(binary)], env={})
            self.assertEqual(result.returncode, 97)
            self.assertEqual(log.read_text(), 'python3\n')
            host = root / 'herdr-app'
            shutil.copy2(binary, host)
            result = subprocess.run([str(host), '--version'], capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), 'herdr-app 0.1.10')
            self.assertEqual(result.returncode, 0)
            self.assertEqual(subprocess.run([str(host), 'do', 'layout.switch']).returncode, 78)

    def test_prerequisites_reject_interpreter_binary_and_missing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'fake-bridge'
            binary.write_text('#!/usr/bin/env python3\n')
            binary.chmod(0o700)
            with self.assertRaisesRegex(RuntimeError, 'native executable'):
                require_native(binary)
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'JIRA_PEEK_MANAGEMENT_BINARY'):
                required_path('JIRA_PEEK_MANAGEMENT_BINARY')

    def test_snapshot_detects_bytes_and_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'fictional'
            file.write_text('first')
            before = snapshot(root)
            file.write_text('other')
            self.assertNotEqual(snapshot(root), before)
            before = snapshot(root)
            file.chmod(file.stat().st_mode ^ stat.S_IXUSR)
            self.assertNotEqual(snapshot(root), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
