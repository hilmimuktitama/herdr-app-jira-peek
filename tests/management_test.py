"""Rust lifecycle parity against unchanged Python oracles, using fictional homes.
Run after scripts/package-runtime.py. No native host or Jira is contacted.
"""
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_current_version = json.loads((ROOT / 'package.json').read_text())['version'].split('.')
NEXT_VERSION = '.'.join([*_current_version[:2], str(int(_current_version[2]) + 1)])
UNAVAILABLE_VERSION = '.'.join([*_current_version[:2], str(int(_current_version[2]) + 2)])
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
installer = module('management_oracle', 'install-app.py')
bundle = module('management_bundle_oracle', 'runtime-bundle.py')

class ManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary_name, cls.manifest_name, cls.notices = bundle.asset_names()
        cls.binary = ROOT / '.release-runtime' / cls.binary_name
        if not cls.binary.exists():
            raise RuntimeError('Build production assets with scripts/package-runtime.py first')
        if json.loads(subprocess.check_output([cls.binary, '--build-info']))['fixtureTransport']:
            raise RuntimeError('Production executable required')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='peek-management-fictional-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'app'
        self.source = self.base / 'source'
        self.source.mkdir()
        for name in ('mods', 'scripts', 'docs', 'rust-backend', '.release-runtime'):
            shutil.copytree(ROOT / name, self.source / name, ignore=shutil.ignore_patterns('target', '__pycache__'))
        for name in ('LICENSE', 'package.json', 'config.example.sh'):
            shutil.copyfile(ROOT / name, self.source / name)
        self.target = self.home / 'mods/jira-peek'

    def run_manage(self, *args, ok=True, env=None):
        result = subprocess.run([self.binary, 'manage', *map(str, args)], capture_output=True, text=True, env=env, timeout=30)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def install(self, *args, ok=True):
        return self.run_manage('install', '--source-root', self.source, '--app-home', self.home, *args, ok=ok)

    def test_production_install_python_oracle_and_no_cli_dependencies(self):
        empty = self.base / 'empty-path'; empty.mkdir()
        self.run_manage('install', '--source-root', self.source, '--app-home', self.home,
                        '--config-dir', '/fictional/private/config', env={'PATH': str(empty)})
        manifest = installer.managed_install(self.target)
        self.assertEqual(set(manifest['files']), installer.REQUIRED_FILES)
        self.assertEqual(manifest['configDir'], '/fictional/private/config')
        self.assertEqual((self.target / 'runtime/jira-peek-bridge').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.target / 'install.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(bundle.source_digest(self.source / 'rust-backend'),
                         json.loads((self.source / '.release-runtime' / self.manifest_name).read_text())['sourceSha256'])

    def test_management_help_and_invalid_arguments_are_consistent(self):
        for args in (('--help',), ('help',), ('integration', '--help'),
                     ('integration', 'diagnose', '--help'), ('integration', 'repair', '--help'),
                     ('install', '--help'), ('update', '--help'), ('rollback', '--help'),
                     ('clear-cache', '--help'), ('help', 'clear-cache')):
            with self.subTest(args=args):
                result = self.run_manage(*args)
                self.assertIn('Usage: jira-peek-bridge manage', result.stdout)
        for args in (('update', '--json'), ('integration', 'repair', '--bogus')):
            with self.subTest(args=args):
                result = self.run_manage(*args, ok=False)
                self.assertIn('invalid_management_arguments', result.stderr)

    def test_personal_repair_names_preserved_files_and_changes_nothing(self):
        self.install()
        mods = self.home / 'mods'
        (mods / 'tabs').mkdir()
        shutil.copyfile(ROOT / 'tests/fixtures/tabs.js', mods / 'tabs/main.js')
        (self.home / 'layouts').mkdir()
        layout = {'id': 'root', 'type': 'column', 'children': [
            {'id': 'tabs', 'type': 'block', 'content': {'mod': 'tabs'}},
            {'id': 'work-body', 'type': 'row', 'children': [
                {'id': 'terminal', 'type': 'block', 'content': {'tab': 'active'}},
                {'id': 'jira-peek', 'type': 'block', 'content': {'mod': 'jira-peek'}}]}]}
        (self.home / 'layouts/main.json').write_text(json.dumps(layout))
        personal = mods / 'tabs-jira-peek'
        personal.mkdir()
        (personal / 'main.js').write_text('// fictional personal toolbar\n')
        (personal / 'mod.json').write_text('{"title":"Fictional personal tabs"}\n')
        (self.home / 'layouts/main-jira-peek.json').write_text('{"id":"fictional-personal"}\n')
        before = (personal / 'main.js').read_bytes()
        result = self.run_manage('integration', 'repair', '--app-home', self.home,
                                 '--layout', 'main', ok=False)
        for path in ('mods/tabs-jira-peek/main.js', 'mods/tabs-jira-peek/mod.json',
                     'layouts/main-jira-peek.json'):
            self.assertIn("'" + path + "'", result.stdout)
        self.assertIn('personal_integration_detected', result.stderr)
        self.assertIn('docs/PANEL-INTEGRATION.md', result.stdout)
        self.assertEqual((personal / 'main.js').read_bytes(), before)
        self.assertEqual((self.home / 'layouts/main-jira-peek.json').read_text(),
                         '{"id":"fictional-personal"}\n')

    def test_personal_diagnosis_reports_origin_and_does_not_claim_broken(self):
        self.install()
        mods = self.home / 'mods'
        (mods / 'tabs').mkdir()
        shutil.copyfile(ROOT / 'tests/fixtures/tabs.js', mods / 'tabs/main.js')
        (self.home / 'layouts').mkdir()
        main = {'id': 'root', 'type': 'column', 'children': [
            {'id': 'tabs', 'type': 'block', 'content': {'mod': 'tabs'}},
            {'id': 'work-body', 'type': 'row', 'children': [
                {'id': 'terminal', 'type': 'block', 'content': {'tab': 'active'}}]}]}
        (self.home / 'layouts/main.json').write_text(json.dumps(main))
        personal = mods / 'tabs-jira-peek'
        personal.mkdir()
        (personal / 'main.js').write_text('// fictional personal toolbar\n')
        (personal / 'mod.json').write_text(json.dumps({
            'place': 'none', 'title': 'Tabs',
            'cloned_from': {'name': 'tabs', 'version': '0.1.11'}}))
        personal_layout = {'id': 'root', 'type': 'column', 'children': [
            {'id': 'tabs', 'type': 'block', 'content': {'mod': 'tabs-jira-peek'}},
            {'id': 'work-body', 'type': 'row', 'children': [
                {'id': 'terminal', 'type': 'block', 'content': {'tab': 'active'}},
                {'id': 'jira-peek', 'type': 'block', 'content': {'mod': 'jira-peek'}}]}]}
        (self.home / 'layouts/main-jira-peek.json').write_text(json.dumps(personal_layout))
        tools = self.base / 'tools'; tools.mkdir()
        checker = tools / 'herdr-app'
        checker.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "herdr-app 0.1.16"; '
                           'else printf \'{"layout":"main-jira-peek","errors":[]}\\n\'; fi\n')
        checker.chmod(0o700)
        result = self.run_manage('integration', 'diagnose', '--app-home', self.home,
                                 env={'PATH': str(tools)})
        self.assertIn('Active integration configured: personal (active layout uses personal toolbar files)', result.stdout)
        self.assertIn('Personal toolbar copy: derived from stock tabs 0.1.11; current herdr-app 0.1.16', result.stdout)
        self.assertIn('Next action: personal integration detected', result.stdout)
        self.assertNotIn('Active integration configured: no', result.stdout)

    def test_update_rollback_preserve_personal_settings_and_executable(self):
        self.home.mkdir(); (self.home / 'keys.json').write_text('fictional personal keys')
        self.install('--config-dir', '/fictional/first')
        (self.target / 'gpui-kit.d.ts').write_text('// generated fixture')
        (self.target / 'runtime/app-bridge.sh').chmod(0o755)
        state = self.home / 'data/jira-peek/fields.json'; state.write_text('{"fictional":true}')
        self.install('--update', '--config-dir', '/fictional/current')
        backup = next((self.home / 'mods').glob('.jira-peek-backup-*'))
        self.run_manage('rollback', backup.name, '--app-home', self.home)
        self.assertEqual(installer.managed_install(self.target)['configDir'], '/fictional/current')
        self.assertTrue(os.access(self.target / 'runtime/jira-peek-bridge', os.X_OK))
        self.assertTrue(backup.exists())
        self.assertEqual((self.target / 'runtime/app-bridge.sh').stat().st_mode & 0o777, 0o755)
        self.assertEqual(state.read_text(), '{"fictional":true}')
        self.assertEqual((self.home / 'keys.json').read_text(), 'fictional personal keys')

    def test_edited_symlink_hardlink_and_unmanaged_rejection(self):
        self.install(); main = self.target / 'main.js'; original = main.read_bytes()
        main.write_text('// fictional personal edit'); self.install('--update', ok=False)
        main.write_bytes(original)
        outside = self.base / 'outside'; main.rename(outside); main.symlink_to(outside)
        self.install('--update', ok=False); main.unlink(); os.link(outside, main)
        self.install('--update', ok=False); main.unlink(); main.write_bytes(original)
        (self.target / 'unmanaged.txt').write_text('fictional extra'); self.install('--update', ok=False)
        self.assertEqual(outside.read_bytes(), original)

    def test_lock_and_unsafe_destination(self):
        self.install()
        with (self.home / 'mods/.jira-peek-install.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn('installation_in_progress', self.install('--update', ok=False).stderr)
        alias = self.base / 'alias'; alias.symlink_to(self.home, target_is_directory=True)
        self.run_manage('install', '--source-root', self.source, '--app-home', alias, ok=False)
        self.run_manage('install', '--source-root', self.source, '--app-home', '/', ok=False)
        self.run_manage('install', '--source-root', self.source, '--app-home', self.home / '..' / 'other', ok=False)

    def test_interrupted_replacement_recovers_and_changed_backup_refuses(self):
        self.install(); mods = self.home / 'mods'; name = '.jira-peek-backup-012345abcdef'
        journal = mods / '.jira-peek-replacement.json'
        record = {'backup': name, 'manifest': installer.digest(self.target / 'install.json')}
        self.target.rename(mods / name); journal.write_text(json.dumps(record))
        self.install('--update'); self.assertFalse(journal.exists()); installer.managed_install(self.target)
        self.target.rename(mods / name); (mods / name / 'main.js').write_text('// edited backup')
        journal.write_text(json.dumps(record)); self.install('--update', ok=False)
        self.assertTrue(journal.exists()); self.assertFalse(self.target.exists())

    def test_runtime_manifest_strictness_and_source_symlink(self):
        path = self.source / '.release-runtime' / self.manifest_name
        original = path.read_text()
        for field, value in [('format', True), ('format', 1.0), ('releaseVersion', '9.9.9'),
                             ('platform', 'fictional'), ('sourceSha256', '0' * 64)]:
            data = json.loads(original); data[field] = value; path.write_text(json.dumps(data))
            with self.subTest(field=field, value=value): self.install(ok=False)
        path.write_text(original.replace('"format": 1', '"format": 1, "format": 1'))
        self.install(ok=False); path.write_text(original)
        (self.source / 'rust-backend/src/alias').symlink_to(self.source / 'rust-backend/src', target_is_directory=True)
        self.install(ok=False)
        self.assertFalse(self.target.exists())

    def test_current_source_inventory_mismatch_preserves_install_and_settings(self):
        self.install()
        before = installer.managed_install(self.target)
        settings = self.home / 'data/jira-peek/fields.json'
        settings.write_text('{"fictional":true}')
        for name in ('future-reader.js', 'icons/future.svg'):
            path = self.source / 'mods/jira-peek' / name
            path.write_text('fictional future module')
            with self.subTest(name=name):
                result = self.install('--update', ok=False)
                self.assertIn('unsupported_source_inventory', result.stderr)
                self.assertEqual(installer.managed_install(self.target), before)
                self.assertEqual(settings.read_text(), '{"fictional":true}')
                self.assertFalse(list((self.home / 'mods').glob('.jira-peek-backup-*')))
            path.unlink()
        missing = self.source / 'mods/jira-peek/icons/search.svg'
        original = missing.read_bytes(); missing.unlink()
        self.assertIn('unsupported_source_inventory', self.install('--update', ok=False).stderr)
        missing.write_bytes(original)
        guide = self.source / 'docs/PANEL-INTEGRATION.md'
        guide_original = guide.read_bytes(); guide.unlink()
        self.assertIn('unsupported_source_inventory', self.install('--update', ok=False).stderr)
        guide.write_bytes(guide_original)
        for name in ('gpui-kit.d.ts', 'jsconfig.json'):
            (self.source / 'mods/jira-peek' / name).write_text('// generated fictional host file')
        self.install('--update')

    def test_asset_size_hash_identity_and_executable_checks(self):
        path = self.source / '.release-runtime' / self.manifest_name; original = path.read_text()
        for change in (lambda d: d['files'][self.binary_name].update(size=True),
                       lambda d: d['files'][self.binary_name].update(size=33*1024*1024),
                       lambda d: d['files'][self.binary_name].update(sha256='0'*64),
                       lambda d: d['buildInfo'].update(version='999.0.0'),
                       lambda d: d['buildInfo'].update(fixtureTransport=True)):
            data = json.loads(original); change(data); path.write_text(json.dumps(data)); self.install(ok=False)
        path.write_text(original); self.install()
        (self.target / 'runtime/jira-peek-bridge').chmod(0o600)
        self.install('--update', ok=False)

    def test_historical_inventories_match_python_oracle(self):
        self.install(); original = json.loads((self.target / 'install.json').read_text())
        saved = self.base / 'saved'; shutil.copytree(self.target, saved)
        # Current-only icons are not part of the frozen historical profiles.
        historical = (installer.REQUIRED_FILES - installer.RUST_FILES - installer.DOC_FILES
                      - installer.CURRENT_ONLY_ICON_FILES)
        cases = []
        for required in (historical, historical-installer.NATIVE_PROJECTION_FILES,
                         historical-installer.WORKSPACE_ICON_FILES,
                         historical-installer.WORKSPACE_ICON_FILES-installer.NATIVE_PROJECTION_FILES):
            former = required-installer.UPDATE_FILES-installer.ICON_FILES
            previous = former-installer.AGENT_FILES
            cases.extend((('0.4.0', required), ('0.4.0', required-installer.ICON_FILES),
                          ('0.4.0', former), ('0.4.0', previous),
                          ('0.3.0', previous-{'runtime/app-setup.py'}),
                          ('0.5.0', previous|{'runtime/app-document.py'})))
        for version, names in cases:
            with self.subTest(version=version, count=len(names)):
                shutil.rmtree(self.target); shutil.copytree(saved, self.target)
                m = dict(original, version=version); m.pop('format'); m['files'] = {}
                for file in list(self.target.rglob('*')):
                    if file.is_file() and file.relative_to(self.target).as_posix() not in names: file.unlink()
                for name in names:
                    file = self.target / name
                    if not file.exists(): file.write_text('# fictional historical helper')
                    m['files'][name] = installer.digest(file)
                for directory in sorted(self.target.rglob('*'), reverse=True):
                    if directory.is_dir() and not any(directory.iterdir()): directory.rmdir()
                (self.target / 'install.json').write_text(json.dumps(m)); installer.managed_install(self.target)
                self.install('--update'); installer.managed_install(self.target)

    def test_actual_fixture_binary_cannot_be_installed(self):
        fixture = os.environ.get('JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY')
        if not fixture:
            self.skipTest('Set JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY to a fixture-http build')
        path = self.source / '.release-runtime' / self.binary_name
        shutil.copyfile(fixture, path)
        self.assertTrue(json.loads(subprocess.check_output([path, '--build-info']))['fixtureTransport'])
        manifest_path = self.source / '.release-runtime' / self.manifest_name
        m = json.loads(manifest_path.read_text())
        m['files'][self.binary_name] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest_path.write_text(json.dumps(m))
        result = self.install(ok=False)
        self.assertIn('runtime_build_identity_mismatch', result.stderr)
        self.assertFalse(self.target.exists())

    def test_concurrent_active_or_staged_edit_during_checker_is_preserved(self):
        self.install(); original = (self.target / 'main.js').read_bytes()
        tools = self.base / 'tools'; tools.mkdir()
        hc = tools / 'hc'; hc.write_text('#!/bin/sh\necho hc 0.0.1\n'); hc.chmod(0o700)
        checker = tools / 'herdr-app'
        for target in ('active', 'staged'):
            checker.write_text('#!' + sys.executable + '\nimport sys,pathlib\n' +
                'if sys.argv[1]=="--version": print("herdr-app 0.1.10")\n' +
                'else:\n mods=pathlib.Path(' + repr(str(self.home / 'mods')) + ')\n' +
                (' p=mods/"jira-peek/main.js"\n' if target == 'active' else ' p=next(mods.glob(".jira-peek-install-*/main.js"))\n') +
                ' p.write_text("// fictional concurrent edit")\n')
            checker.chmod(0o700)
            self.run_manage('install', '--source-root', self.source, '--app-home', self.home,
                            '--update', '--check', env={'PATH': str(tools)}, ok=False)
            self.assertEqual((self.target / 'main.js').read_bytes(),
                             b'// fictional concurrent edit' if target == 'active' else original)
            self.assertFalse(list((self.home / 'mods').glob('.jira-peek-backup-*')))
            (self.target / 'main.js').write_bytes(original)

    def updater_fixture(self, release_version=NEXT_VERSION):
        self.install('--config-dir', '/fictional/current')
        release = self.base / 'release'; shutil.copytree(self.source, release)
        for name in ('package.json', 'mods/jira-peek/mod.json'):
            path = release / name; data = json.loads(path.read_text()); data['version'] = release_version; path.write_text(json.dumps(data))
        path = release / '.release-runtime' / self.manifest_name
        data = json.loads(path.read_text()); data['releaseVersion'] = release_version; path.write_text(json.dumps(data))
        tools = self.base / 'tools'; tools.mkdir(); log = self.base / 'git-log'
        plan = self.base / 'git-plan.json'
        plan.write_text(json.dumps({'tags': ['v'+release_version], 'sha': 'a'*40}))
        git = tools / 'git'
        git.write_text('#!' + sys.executable + '\n' +
            'import sys, pathlib, shutil, json, os\n' +
            'assert sys.argv[1:7] == ["-c","core.hooksPath=/dev/null","-c","maintenance.auto=false","-c","gc.auto=0"]\n' +
            'assert os.environ.get("GIT_TERMINAL_PROMPT")=="0"\n' +
            'assert "GIT_DIR" not in os.environ\n' +
            'args=sys.argv[7:]; plan=json.loads(pathlib.Path(' + repr(str(plan)) + ').read_text())\n' +
            'with open(' + repr(str(log)) + ',"a") as f: f.write(" ".join(args)+"\\n")\n' +
            'if plan.get("error"): print("fictional-private-git-diagnostic",file=sys.stderr); sys.exit(1)\n' +
            'if args[0]=="ls-remote":\n for tag in plan["tags"]: print("a"*40+"\\trefs/tags/"+tag)\n' +
            'elif args[0]=="init": pathlib.Path(args[-1]).mkdir()\n' +
            'elif args[0]=="rev-parse": print(plan["sha"])\n' +
            'elif args[0]=="fetch" and plan.get("edit"): pathlib.Path(' + repr(str(self.target / 'main.js')) + ').write_text("// fictional concurrent edit")\n' +
            'elif args[0]=="checkout": shutil.copytree(' + repr(str(release)) + ', pathlib.Path.cwd(), dirs_exist_ok=True, symlinks=True)\n')
        git.chmod(0o700)
        checker = tools / 'herdr-app'
        checker.write_text('#!' + sys.executable + '\nimport sys,json,pathlib,os\n' +
            'if sys.argv[1]=="--version": print("herdr-app 0.1.10")\n' +
            'else:\n p=pathlib.Path(sys.argv[2]); assert json.loads((p/"install.json").read_text())["configDir"] is None\n assert os.environ["HERDR_APP_HOME"] != ' + repr(str(self.home)) + '\n')
        checker.chmod(0o700)
        hc = tools / 'hc'; hc.write_text('#!/bin/sh\necho hc 0.0.1\n'); hc.chmod(0o700)
        return {'PATH': str(tools), 'GIT_DIR': '/fictional/ignored'}, plan, log, release

    def test_rust_update_with_fictional_git_and_isolated_checker(self):
        env, plan, log, release = self.updater_fixture()
        before = installer.managed_install(self.target)
        plan.write_text(json.dumps({'tags': ['v0.9.0', 'v' + NEXT_VERSION, 'v999.0.0-preview', 'v01.0.0'], 'sha': 'a'*40}))
        result = self.run_manage('update', '--app-home', self.home, '--check', env=env)
        self.assertIn('selected release: ' + NEXT_VERSION, result.stdout)
        self.assertEqual(installer.managed_install(self.target), before)
        self.run_manage('update', '--app-home', self.home, '--version', NEXT_VERSION, env=env)
        installed = installer.managed_install(self.target)
        self.assertEqual(installed['version'], NEXT_VERSION)
        self.assertEqual(installed['configDir'], '/fictional/current')
        self.assertIn('refs/tags/v' + NEXT_VERSION, log.read_text())
        count = len(list((self.home / 'mods').glob('.jira-peek-backup-*')))
        self.run_manage('update', '--app-home', self.home, env=env)
        self.assertEqual(len(list((self.home / 'mods').glob('.jira-peek-backup-*'))), count)
        self.run_manage('update', '--app-home', self.home, '--version', '1.2.3-preview', env=env, ok=False)
        self.run_manage('update', '--app-home', self.home, '--version', UNAVAILABLE_VERSION, env=env, ok=False)

    def test_rust_updater_tag_source_and_git_failures_preserve_bundle(self):
        env, plan, log, release = self.updater_fixture()
        before = installer.managed_install(self.target)
        for changes, expected in [({'sha': 'b'*40}, 'release_tag_changed'),
                                  ({'tags': []}, 'numbered_release_unavailable'),
                                  ({'error': True}, 'git_release_read_failed')]:
            data = {'tags': ['v' + NEXT_VERSION], 'sha': 'a'*40}; data.update(changes); plan.write_text(json.dumps(data))
            result = self.run_manage('update', '--app-home', self.home, env=env, ok=False)
            self.assertIn(expected, result.stderr)
            self.assertNotIn('fictional-private-git-diagnostic', result.stderr)
            self.assertEqual(installer.managed_install(self.target), before)
        plan.write_text(json.dumps({'tags': ['v' + NEXT_VERSION], 'sha': 'a'*40}))
        metadata = release / 'package.json'; original = metadata.read_text(); metadata.write_text('{"version":"0.99.0"}')
        self.run_manage('update', '--app-home', self.home, env=env, ok=False); metadata.write_text(original)
        (release / 'unmanaged-symlink').symlink_to(release / 'LICENSE')
        self.run_manage('update', '--app-home', self.home, env=env, ok=False)
        self.assertEqual(installer.managed_install(self.target), before)

    def test_rust_updater_requires_explicit_downgrade(self):
        env, plan, log, release = self.updater_fixture('0.10.1')
        before = installer.managed_install(self.target)
        self.run_manage('update', '--app-home', self.home, '--check', env=env)
        self.run_manage('update', '--app-home', self.home, env=env, ok=False)
        self.run_manage('update', '--app-home', self.home, '--version', '0.10.1', env=env, ok=False)
        self.run_manage('update', '--app-home', self.home, '--allow-downgrade', env=env, ok=False)
        self.assertEqual(installer.managed_install(self.target), before)
        self.run_manage('update', '--app-home', self.home, '--version', '0.10.1', '--allow-downgrade', env=env)
        self.assertEqual(installer.managed_install(self.target)['version'], '0.10.1')

    def test_rust_updater_detects_edits_during_download(self):
        env, plan, log, release = self.updater_fixture()
        plan.write_text(json.dumps({'tags': ['v' + NEXT_VERSION], 'sha': 'a'*40, 'edit': True}))
        result = self.run_manage('update', '--app-home', self.home, env=env, ok=False)
        self.assertIn('Installed state is unconfirmed', result.stderr)
        self.assertEqual((self.target / 'main.js').read_text(), '// fictional concurrent edit')
        self.assertFalse(list((self.home / 'mods').glob('.jira-peek-backup-*')))

    def test_rust_updater_real_git_local_release(self):
        git = shutil.which('git')
        if not git: self.skipTest('Git is the explicit release updater dependency')
        env, plan, log, release = self.updater_fixture()
        git_env = {'PATH': os.defpath, 'HOME': str(self.base), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
        def local_git(*args):
            subprocess.run([git, '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                            '-c', 'user.name=Fictional Fixture', '-c', 'user.email=fixture@example.test', *args],
                           cwd=release, env=git_env, capture_output=True, check=True, timeout=30)
        local_git('init', '--quiet'); local_git('add', '--force', '.'); local_git('commit', '--quiet', '-m', 'Fictional release fixture')
        local_git('tag', 'v' + NEXT_VERSION)
        fake_git = self.base / 'tools/git'; fake_git.unlink(); fake_git.symlink_to(git)
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, HOME=str(self.base),
                   GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='url.'+release.as_uri()+'.insteadOf',
                   GIT_CONFIG_VALUE_0='https://github.com/hilmimuktitama/herdr-app-jira-peek.git')
        self.run_manage('update', '--app-home', self.home, env=env)
        self.assertEqual(installer.managed_install(self.target)['version'], NEXT_VERSION)

    def test_updater_check_does_not_recover_and_installed_binary_targets_own_home(self):
        env, plan, log, release = self.updater_fixture()
        current = installer.managed_install(self.target)
        plan.write_text(json.dumps({'tags': ['v'+current['version']], 'sha': 'a'*40}))
        journal = self.home / 'mods/.jira-peek-replacement.json'; journal.write_text('interrupted intent')
        self.run_manage('update', '--app-home', self.home, '--check', env=env)
        self.assertTrue(journal.exists())
        installed = self.target / 'runtime/jira-peek-bridge'
        result = subprocess.run([installed, 'manage', 'update'], env=dict(env, HERDR_APP_HOME=str(self.base / 'different-home')),
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(journal.exists()); self.assertFalse((self.base / 'different-home').exists())

    def test_shell_rust_shell_rust_rollback_transition(self):
        self.install('--config-dir', '/fictional/current')
        m = installer.managed_install(self.target)
        names = (installer.REQUIRED_FILES - installer.RUST_FILES - installer.UPDATE_FILES
                 - installer.ICON_FILES - installer.AGENT_FILES - installer.DOC_FILES
                 - {'runtime/app-setup.py'})
        for path in list(self.target.rglob('*')):
            if path.is_file() and path.relative_to(self.target).as_posix() not in names: path.unlink()
        for path in sorted(self.target.rglob('*'), reverse=True):
            if path.is_dir() and not any(path.iterdir()): path.rmdir()
        m.pop('format'); m['version'] = '0.3.0'; m['files'] = {name: installer.digest(self.target / name) for name in names}
        (self.target / 'install.json').write_text(json.dumps(m)); installer.managed_install(self.target)
        self.install('--update')
        old = next((self.home / 'mods').glob('.jira-peek-backup-*'))
        self.run_manage('rollback', old.name, '--app-home', self.home)
        self.assertEqual(installer.managed_install(self.target)['version'], '0.3.0')
        rust = next(p for p in (self.home / 'mods').glob('.jira-peek-backup-*') if p != old)
        self.run_manage('rollback', rust.name, '--app-home', self.home)
        self.assertTrue(os.access(self.target / 'runtime/jira-peek-bridge', os.X_OK))
        self.assertEqual(installer.managed_install(self.target)['configDir'], '/fictional/current')

    def test_exact_historical_source_downgrade_and_return_to_rust(self):
        fixture = os.environ.get('JIRA_PEEK_LEGACY_SOURCE')
        if not fixture: self.skipTest('Set JIRA_PEEK_LEGACY_SOURCE to immutable public v0.9.1 source')
        env, plan, log, release = self.updater_fixture()
        shutil.rmtree(release); shutil.copytree(fixture, release)
        plan.write_text(json.dumps({'tags': ['v0.9.1'], 'sha': 'a'*40}))
        result = self.run_manage('update', '--app-home', self.home, '--version', '0.9.1', '--allow-downgrade', env=env)
        self.assertIn('Repair integration: ' + repr(str(self.binary)), result.stdout)
        self.assertNotIn(str(self.target / 'runtime/jira-peek-bridge'), result.stdout)
        legacy = installer.managed_install(self.target)
        self.assertEqual(legacy['version'], '0.9.1')
        self.assertEqual(legacy['configDir'], '/fictional/current')
        self.assertNotIn('runtime/jira-peek-bridge', legacy['files'])
        self.assertNotIn('runtime/runtime-bundle.py', legacy['files'])
        self.assertNotIn('icons/terminal.svg', legacy['files'])
        self.assertEqual((self.target / 'runtime/app-bridge.sh').read_bytes(), (Path(fixture) / 'scripts/app-bridge.sh').read_bytes())
        shutil.rmtree(release); shutil.copytree(self.source, release)
        version = json.loads((release / 'package.json').read_text())['version']
        plan.write_text(json.dumps({'tags': ['v'+version], 'sha': 'a'*40}))
        self.run_manage('update', '--app-home', self.home, env=env)
        self.assertTrue(os.access(self.target / 'runtime/jira-peek-bridge', os.X_OK))
        self.assertEqual(installer.managed_install(self.target)['version'], version)

    def test_installed_caller_downgrade_keeps_repair_guidance_usable(self):
        fixture = os.environ.get('JIRA_PEEK_LEGACY_SOURCE')
        if not fixture: self.skipTest('Set JIRA_PEEK_LEGACY_SOURCE to immutable public v0.9.1 source')
        env, plan, log, release = self.updater_fixture()
        shutil.rmtree(release); shutil.copytree(fixture, release)
        plan.write_text(json.dumps({'tags': ['v0.9.1'], 'sha': 'a'*40}))
        result = subprocess.run([self.target / 'runtime/jira-peek-bridge', 'manage', 'update',
                                 '--version', '0.9.1', '--allow-downgrade'],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installer.managed_install(self.target)['version'], '0.9.1')
        self.assertNotIn(str(self.target / 'runtime/jira-peek-bridge'), result.stdout)
        self.assertTrue('retained executable' in result.stdout or '.jira-peek-backup-' in result.stdout)

    def test_historical_source_profile_rejects_edits_and_current_damage(self):
        fixture = os.environ.get('JIRA_PEEK_LEGACY_SOURCE')
        if not fixture: self.skipTest('Set JIRA_PEEK_LEGACY_SOURCE to immutable public v0.9.1 source')
        self.install(); before = installer.managed_install(self.target)
        source = self.base / 'legacy'; shutil.copytree(fixture, source)
        main = source / 'mods/jira-peek/main.js'; original = main.read_bytes()
        main.write_text('// altered historical code')
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        main.write_bytes(original); (source / 'rust-backend').mkdir()
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        (source / 'rust-backend').rmdir(); main.unlink()
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        (self.source / 'scripts/runtime-bundle.py').unlink()
        self.install('--update', ok=False)
        self.assertEqual(installer.managed_install(self.target), before)

    def test_frozen_profiles_match_all_locally_tagged_installer_inventories(self):
        # Developer oracle only: evaluate reviewed constant declarations, never
        # import or execute historical installer functions in the product.
        import ast
        profiles = json.loads((ROOT / 'rust-backend/src/management/source-profiles.json').read_text())
        tags = subprocess.check_output(['git', 'tag', '--list', 'v*'], cwd=ROOT, text=True).split()
        expected = {tag[1:] for tag in tags if re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag) and tuple(map(int, tag[1:].split('.'))) <= (0, 10, 0)}
        if not set(profiles) <= expected:
            self.skipTest('Fetch the frozen release tags to run the historical source oracle')
        self.assertEqual(set(profiles), expected)
        for version, profile in profiles.items():
            with self.subTest(version=version):
                commit = profile['commit']
                self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'v'+version+'^{commit}'], cwd=ROOT, text=True).strip(), commit)
                code = subprocess.check_output(['git', 'show', commit+':scripts/install-app.py'], cwd=ROOT, text=True)
                scope = {}
                names = {'RUNTIME','MOD_FILES','ICON_FILES','WORKSPACE_ICON_FILES','AGENT_FILES','UPDATE_FILES','REQUIRED_FILES','NATIVE_PROJECTION_FILES','RUST_FILES'}
                for node in ast.parse(code).body:
                    if (isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets) and node.targets[0].id in names) or (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == 'REQUIRED_FILES'):
                        exec(compile(ast.Module(body=[node], type_ignores=[]), '<immutable release constants>', 'exec'), scope)
                self.assertEqual(set(profile['files']), scope['REQUIRED_FILES'])
                self.assertEqual(profile['rust'], 'RUST_FILES' in scope)
                for name, expected_hash in profile['files'].items():
                    if expected_hash is None: continue
                    source = 'scripts/'+name[8:] if name.startswith('runtime/') else 'docs/AGENT-GUIDE.md' if name == 'AGENTS.md' else name if name == 'LICENSE' else 'mods/jira-peek/'+name
                    content = subprocess.check_output(['git','show',commit+':'+source], cwd=ROOT)
                    self.assertEqual(hashlib.sha256(content).hexdigest(), expected_hash)
                for name, expected_hash in profile['checks'].items():
                    content = subprocess.check_output(['git','show',commit+':'+name], cwd=ROOT)
                    self.assertEqual(hashlib.sha256(content).hexdigest(), expected_hash)

    def historical_sources(self):
        root = os.environ.get('JIRA_PEEK_HISTORICAL_SOURCES')
        if not root: self.skipTest('Set JIRA_PEEK_HISTORICAL_SOURCES to extracted tagged sources, with packaged v0.10.0 runtime')
        return Path(root).resolve()

    def test_all_frozen_sources_install_with_exact_inventory_without_utilities(self):
        root = self.historical_sources()
        profiles = json.loads((ROOT / 'rust-backend/src/management/source-profiles.json').read_text())
        self.install('--config-dir', '/fictional/preserved')
        for version, profile in profiles.items():
            with self.subTest(version=version):
                self.run_manage('install', '--source-root', root/('v'+version), '--app-home', self.home, '--update', env={'PATH': '/fictional/no-tools'})
                installed = installer.managed_install(self.target)
                self.assertEqual(set(installed['files']), set(profile['files']))
                self.assertEqual(installed['version'], version)
                self.assertEqual(installed['configDir'], '/fictional/preserved')
                for name, expected_hash in profile['files'].items():
                    if expected_hash is not None and not (profile['rust'] and name == 'runtime/app-bridge.sh'):
                        self.assertEqual(installed['files'][name], expected_hash)
                self.assertEqual((self.target/'runtime/jira-peek-bridge').exists(), profile['rust'])
                self.assertFalse((self.target/'icons/terminal.svg').exists())
        self.install('--update')
        self.assertTrue(os.access(self.target/'runtime/jira-peek-bridge', os.X_OK))

    def test_real_historical_source_updater_early_mid_latest_shell_and_rust(self):
        root = self.historical_sources()
        env, plan, log, release = self.updater_fixture()
        for version in ('0.1.0', '0.5.1', '0.9.1', '0.10.0'):
            with self.subTest(version=version):
                shutil.rmtree(release)
                shutil.copytree(root/('v'+version), release, ignore=shutil.ignore_patterns('target'))
                plan.write_text(json.dumps({'tags': ['v'+version], 'sha': 'a'*40}))
                self.run_manage('update', '--app-home', self.home, '--version', version, '--allow-downgrade', env=env)
                self.assertEqual(installer.managed_install(self.target)['version'], version)
                self.assertEqual((self.target/'runtime/jira-peek-bridge').exists(), version == '0.10.0')
        self.install('--update')

    def test_historical_rust_requires_unchanged_source_and_valid_runtime_assets(self):
        root = self.historical_sources(); self.install()
        before = installer.managed_install(self.target)
        source = self.base/'old-rust'
        shutil.copytree(root/'v0.10.0', source, ignore=shutil.ignore_patterns('target'))
        manifest = source/'.release-runtime'/self.manifest_name
        original_manifest = manifest.read_text(); data = json.loads(original_manifest)
        data['files'][self.binary_name]['sha256'] = '0'*64
        manifest.write_text(json.dumps(data))
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        manifest.write_text(original_manifest)
        code = source/'rust-backend/src/main.rs'; original_code = code.read_bytes(); code.write_bytes(original_code+b'\n// altered\n')
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        code.write_bytes(original_code); manifest.unlink()
        self.run_manage('install', '--source-root', source, '--app-home', self.home, '--update', ok=False)
        self.assertEqual(installer.managed_install(self.target), before)

    def test_doctor_offline_backend_requirements_and_argument_rejection(self):
        tools = self.base / 'tools'; tools.mkdir()
        for name, text in [('herdr-app', 'herdr-app 0.1.10'), ('hc', 'herdr-core 0.0.1')]:
            path = tools / name; path.write_text('#!/bin/sh\nprintf "%s\\n" "'+text+'"\n'); path.chmod(0o700)
        env = {'PATH': str(tools)}
        report = json.loads(self.run_manage('doctor', '--json', env=env).stdout)
        self.assertTrue(report['ok']); self.assertFalse(report['optional']['git'])
        self.assertEqual(set(report['required']), {'posix', 'herdr-app >= 0.1.10', 'hc'})
        (tools / 'herdr-app').write_text('#!/bin/sh\necho herdr-app 0.1.9\n')
        self.run_manage('doctor', '--json', env=env, ok=False)
        self.install('--attach', ok=False); self.assertFalse(self.target.exists())
        self.run_manage('rollback', '../escape', '--app-home', self.home, ok=False)
        self.run_manage('install', '--source-root', self.source, '--app-home', self.home, '--check', '--check', ok=False)

if __name__ == '__main__': unittest.main()
