#!/usr/bin/env python3
"""Offline lifecycle acceptance. Driver dependencies are not product dependencies.

Required: JIRA_PEEK_MANAGEMENT_BINARY (production native executable),
JIRA_PEEK_SOURCE_FIXTURE (complete source with matching .release-runtime assets).
Optional: JIRA_PEEK_NEXT_SOURCE_FIXTURE for a second packaged source.
Run directly, or with unittest discovery. Missing required inputs are errors;
missing optional transition fixtures are explicit skips, never passing evidence.
No real host, account, credentials, or remote repository is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

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


class LifecycleAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = required_path('JIRA_PEEK_MANAGEMENT_BINARY')
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
        source.write_text(STUB)
        stub = self.root / 'stub'
        subprocess.run([self.compiler, str(source), '-o', str(stub)], check=True, capture_output=True)
        for name in (*FORBIDDEN, 'herdr-app', 'hc'):
            shutil.copy2(stub, self.bin / name)
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
        self.assertFalse(self.json_call('--build-info')['fixtureTransport'],
                         'Acceptance requires production binary, not fixture transport')

    def call(self, *args, success=True):
        result = subprocess.run([str(self.binary), *map(str, args)], env=self.env,
                                cwd=self.root, text=True, capture_output=True, timeout=90)
        self.assertFalse(self.denied.exists(), 'Forbidden product dependency invoked: ' +
                         (self.denied.read_text() if self.denied.exists() else ''))
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, 'Failure must have nonzero exit status')
        return result

    def json_call(self, *args):
        return json.loads(self.call(*args).stdout)

    def install(self, source=None, *flags):
        self.call('manage', 'install', '--source-root', source or self.source,
                  '--app-home', self.home, '--check', *flags)
        return self.verify_bundle()

    def verify_bundle(self):
        target = self.home / 'mods/jira-peek'
        manifest = json.loads((target / 'install.json').read_text())
        self.assertEqual(manifest['owner'], 'herdr-jira-peek')
        self.assertTrue(manifest['files'])
        for name, digest in manifest['files'].items():
            path = target / name
            self.assertTrue(path.resolve().is_relative_to(target.resolve()))
            self.assertFalse(path.is_symlink())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)
        binary = target / 'runtime/jira-peek-bridge'
        self.assertTrue(binary.stat().st_mode & stat.S_IXUSR)
        return manifest

    def test_doctor_is_read_only(self):
        before = snapshot(self.home)
        self.json_call('manage', 'doctor', '--json')
        self.assertEqual(snapshot(self.home), before)

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
        self.assertTrue(request.resolve().is_relative_to(connection))
        self.assertEqual(request.read_bytes(), b'')
        self.assertEqual(stat.S_IMODE(request.stat().st_mode), 0o600)
        for _ in range(2):
            self.assertEqual(self.json_call('setup', 'cancel', connection, ticket['ticket']), {'ok': True})
        self.assertFalse(request.exists())

    def test_second_packaged_source_update(self):
        value = os.environ.get('JIRA_PEEK_NEXT_SOURCE_FIXTURE')
        if not value:
            self.skipTest('Pending second packaged release: set JIRA_PEEK_NEXT_SOURCE_FIXTURE')
        self.install()
        next_source = Path(value).resolve(strict=True)
        expected = json.loads((next_source / 'package.json').read_text())['version']
        self.assertNotEqual(expected, json.loads((self.source / 'package.json').read_text())['version'])
        self.assertEqual(self.install(next_source, '--update')['version'], expected)


class FixtureSelfTest(unittest.TestCase):
    def test_compiled_denial_fixture_records_and_fails(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('Driver prerequisite missing: C compiler')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'stub.c'
            source.write_text(STUB)
            binary = root / 'python3'
            subprocess.run([compiler, str(source), '-o', str(binary)], check=True, capture_output=True)
            log = root / 'denied'
            result = subprocess.run([str(binary)], env={'PATH': str(root), 'DENIED_LOG': str(log)})
            self.assertEqual(result.returncode, 97)
            self.assertEqual(log.read_text(), 'python3\n')
            host = root / 'herdr-app'
            shutil.copy2(binary, host)
            result = subprocess.run([str(host), '--version'], capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), 'herdr-app 0.1.10')
            self.assertEqual(result.returncode, 0)
            self.assertEqual(subprocess.run([str(host), 'do', 'layout.switch']).returncode, 78)

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
