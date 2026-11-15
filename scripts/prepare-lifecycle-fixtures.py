#!/usr/bin/env python3
"""Developer/CI fixtures from frozen public Git objects; never install or publish."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def prepare(output):
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Keep historical test packages outside the source checkout')
    # Never overwrite or clean up a caller's existing directory.
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    profiles = json.loads((ROOT / 'rust-backend/src/management/source-profiles.json').read_text())
    for version, profile in profiles.items():
        commit = profile['commit']
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Invalid frozen release identity')
        actual = subprocess.check_output(['git', 'rev-parse', 'v' + version + '^{commit}'], cwd=ROOT, text=True).strip()
        if actual != commit:
            raise ValueError('Historical tag differs from the reviewed frozen commit: v' + version)
        data = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
        source = output / ('v' + version)
        source.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                    raise ValueError('Unsafe historical archive member')
            archive.extractall(source)
        if profile['rust']:
            # This is a developer fixture build of trusted, recorded public source.
            # The product never executes historical Python/shell installers.
            subprocess.run([sys.executable, '-B', str(source / 'scripts/package-runtime.py')],
                           cwd=source, check=True)
        print('Prepared historical fixture v' + version, flush=True)
    (output / 'complete.json').write_text(json.dumps({
        'completed': True, 'commits': {v: p['commit'] for v, p in profiles.items()}
    }, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.output)
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        parser.exit(1, 'Historical fixture preparation failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
