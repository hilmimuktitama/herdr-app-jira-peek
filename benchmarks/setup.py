#!/usr/bin/env python3
"""Compare Python/curl and production Rust setup using fictional HTTPS only."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'rust-backend/tests/lifecycle_acceptance_test.py'
spec = importlib.util.spec_from_file_location('setup_benchmark_fixture', FIXTURE)
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(values):
    return {'median_ms': statistics.median(values),
            'p95_ms': sorted(values)[math.ceil(len(values) * .95) - 1],
            'samples_ms': values}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=40)
    parser.add_argument('--warmup', type=int, default=5)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.samples < 20 or args.warmup < 0 or args.repeats < 1:
        parser.error('Require samples >= 20, warmup >= 0 and repeats >= 1')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error('Keep evidence outside the repository')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'completed': False, 'started_at': datetime.now(timezone.utc).isoformat(),
              'samples': args.samples, 'warmup': args.warmup, 'repeats': args.repeats,
              'platform': platform.platform(), 'python': sys.version.split()[0],
              'results': {}, 'scope': 'Fresh processes, warm filesystem, fictional loopback HTTPS; no native interaction timing'}
    # Reserve a fresh output before setup. Failure cannot expose an old success.
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)

    def persist():
        temporary = output.with_suffix(output.suffix + '.partial')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(output)

    binary = args.binary.resolve(strict=True)
    curl = shutil.which('curl')
    if not curl:
        raise RuntimeError('Python oracle requires curl for this developer benchmark')
    report['binary_sha256'] = digest(binary)
    report['source_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in
                              [Path(__file__), FIXTURE, ROOT / 'scripts/app-setup.py',
                               ROOT / 'rust-backend/Cargo.toml', ROOT / 'rust-backend/Cargo.lock',
                               ROOT / 'rust-backend/build.rs',
                               *sorted(p for p in (ROOT / 'rust-backend/src').rglob('*') if p.is_file())]}
    report['source_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report['curl_version'] = subprocess.check_output([curl, '--version'], text=True).splitlines()[0]
    started = time.monotonic()
    operations = ['inspect', 'prepare', 'cancel', 'save', 'transaction']
    with tempfile.TemporaryDirectory(prefix='fictional-setup-benchmark-', dir=output.parent) as temporary:
        root = Path(temporary)
        env = {'HOME': str(root), 'PATH': '/nonexistent/fictional', 'LANG': 'C',
               'CURL_BIN_PATH': curl, 'TMPDIR': str(root)}
        info = json.loads(subprocess.check_output([str(binary), '--build-info'], env=env, text=True))
        if info.get('fixtureTransport') is not False:
            raise RuntimeError('Use a production build, with fixture-http disabled')
        report['build_info'] = info
        # Copy immutable inputs so later builds cannot change the measured binary.
        measured = root / 'jira-peek-bridge'
        shutil.copy2(binary, measured)
        python_helper = root / 'app-setup.py'
        shutil.copy2(ROOT / 'scripts/app-setup.py', python_helper)
        commands = {'python': [sys.executable, '-B', str(python_helper)],
                    'rust': [str(measured), 'setup']}
        fixture = fixture_module.JiraTLSFixture(root / 'tls')
        try:
            env.update(fixture.environment())
            payload = {'base': 'https://' + fixture.authority, 'email': fixture.email,
                       'token': fixture.token, 'projects': 'ABC', 'cloudId': ''}
            for repeat in range(args.repeats):
                roots = {kind: root / str(repeat) / kind / 'data/jira-peek/connection' for kind in commands}

                def call(kind, operation, *params):
                    start = time.perf_counter_ns()
                    result = subprocess.run([*commands[kind], operation, str(roots[kind]), *params],
                                            env=env, capture_output=True, text=True, timeout=25, check=True)
                    elapsed = (time.perf_counter_ns() - start) / 1e6
                    value = json.loads(result.stdout)
                    if result.stderr or value.get('ok') is not True:
                        raise RuntimeError(kind + '/' + operation + ' failed')
                    return elapsed, value

                def prepare(kind):
                    revision = call(kind, 'inspect')[1]['revision']
                    return call(kind, 'prepare', revision)[1]

                def submit(ticket):
                    Path(ticket['path']).write_text(json.dumps(payload))

                # Every workload begins with an established, equivalent connection.
                for kind in commands:
                    ticket = prepare(kind)
                    submit(ticket)
                    call(kind, 'save', ticket['ticket'])
                order_ops = operations[repeat % len(operations):] + operations[:repeat % len(operations)]
                for operation in order_ops:
                    samples = {kind: [] for kind in commands}
                    counts = {kind: [] for kind in commands}
                    for sample in range(args.samples + args.warmup):
                        order = list(commands) if (sample + repeat) % 2 == 0 else list(reversed(commands))
                        for kind in order:
                            revision = call(kind, 'inspect')[1]['revision']
                            ticket = prepare(kind) if operation in ('cancel', 'save') else None
                            if operation == 'save':
                                submit(ticket)
                            before = len(fixture.calls)
                            if operation == 'transaction':
                                start = time.perf_counter_ns()
                                ticket = call(kind, 'prepare', revision)[1]
                                submit(ticket)
                                call(kind, 'save', ticket['ticket'])
                                elapsed = (time.perf_counter_ns() - start) / 1e6
                            else:
                                params = ([revision] if operation == 'prepare' else
                                          [ticket['ticket']] if ticket else [])
                                elapsed, value = call(kind, operation, *params)
                                if operation == 'prepare':
                                    ticket = value
                                if operation == 'inspect' and value['settings'] != {
                                        'base': payload['base'], 'email': payload['email'],
                                        'projects': 'ABC', 'cloudId': ''}:
                                    raise RuntimeError('Inspect settings mismatch')
                            count = len(fixture.calls) - before
                            expected = 1 if operation in ('save', 'transaction') else 0
                            if count != expected or any(not c['authenticated'] or c['path'] != '/rest/api/3/myself'
                                                        for c in fixture.calls[before:]):
                                raise RuntimeError('HTTP count, authentication or endpoint mismatch')
                            if operation == 'prepare':
                                call(kind, 'cancel', ticket['ticket'])
                            if sample >= args.warmup:
                                samples[kind].append(elapsed)
                                counts[kind].append(count)
                    row = {kind: dict(metrics(values), http_requests=counts[kind]) for kind, values in samples.items()}
                    report['results'].setdefault(operation, []).append({'repeat': repeat + 1, **row})
                    persist()
                    print(f"run {repeat + 1} {operation}: Python {row['python']['median_ms']:.2f}/{row['python']['p95_ms']:.2f} ms; Rust {row['rust']['median_ms']:.2f}/{row['rust']['p95_ms']:.2f} ms (median/p95)", flush=True)
        finally:
            fixture.close()
    report.update(completed=True, finished_at=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=time.monotonic() - started)
    persist()


if __name__ == '__main__':
    main()
