#!/usr/bin/env python3
"""Verify downloaded release assets without network access.

The release job retains four artifact sets. Download and flatten them first:

    gh run download <run-id> -D /tmp/jira-peek-raw
    mkdir /tmp/jira-peek-assets
    find /tmp/jira-peek-raw -type f -exec cp {} /tmp/jira-peek-assets/ \;
    python3 scripts/verify-release-assets.py /tmp/jira-peek-assets
    python3 scripts/verify-release-assets.py /tmp/jira-peek-assets --install-check

--install-check stages the host platform from HEAD and runs the production
`manage install --check` path. Other platforms are verified by manifest only.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("runtime_bundle", ROOT / "scripts/runtime-bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

PLATFORMS = ("linux-aarch64", "linux-x86_64", "macos-aarch64", "macos-x86_64")
SHA256 = re.compile(r"[0-9a-f]{64}")


def expected_files(platform):
    binary = f"jira-peek-bridge-{platform}"
    return {binary, binary + ".json", binary + "-NOTICES.txt"}


def read_manifest(path):
    try:
        return json.loads(path.read_text(), object_pairs_hook=bundle.unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Invalid runtime manifest {path.name}: {error}") from None


def verify(directory, version, root=ROOT):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Asset path must be a regular directory")
    entries = sorted(directory.iterdir(), key=lambda path: path.name)
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise ValueError("Asset directory must contain regular files only")
    expected = set().union(*(expected_files(platform) for platform in PLATFORMS))
    actual = {path.name for path in entries}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            "Asset inventory mismatch"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; unexpected: {', '.join(extra)}" if extra else "")
        )

    source_sha = bundle.source_digest(root / "rust-backend")
    for platform in PLATFORMS:
        binary = f"jira-peek-bridge-{platform}"
        manifest_path = directory / (binary + ".json")
        manifest = read_manifest(manifest_path)
        if (not isinstance(manifest, dict) or type(manifest.get("format")) is not int or manifest["format"] != 1 or
                manifest.get("releaseVersion") != version or manifest.get("platform") != platform or
                not isinstance(manifest.get("buildInfo"), dict) or
                manifest["buildInfo"].get("fixtureTransport") is not False or
                manifest["buildInfo"].get("protocol") != 1):
            raise ValueError(f"Manifest {manifest_path.name} does not match this release or platform")
        if manifest.get("sourceSha256") != source_sha:
            raise ValueError(
                f"Manifest {manifest_path.name} source digest {manifest.get('sourceSha256')!r} "
                f"does not match {source_sha}"
            )
        files = manifest.get("files")
        names = {binary, binary + "-NOTICES.txt"}
        if not isinstance(files, dict) or set(files) != names:
            raise ValueError(f"Manifest {manifest_path.name} does not list the expected two assets")
        for name, limit in ((binary, bundle.MAX_BINARY), (binary + "-NOTICES.txt", 4 * 1024 * 1024)):
            entry = files[name]
            if (not isinstance(entry, dict) or type(entry.get("size")) is not int or
                    not 0 < entry["size"] <= limit or
                    not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"])):
                raise ValueError(f"Manifest {manifest_path.name} has invalid metadata for {name}")
            payload = (directory / name).read_bytes()
            if len(payload) != entry["size"]:
                raise ValueError(f"{name} size does not match its manifest")
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise ValueError(f"{name} checksum does not match its manifest")
        print(f"ok {platform}")
    print(f"all 12 assets verified; source {source_sha}")
    return source_sha


def install_check(directory, version, root=ROOT):
    directory = Path(directory)
    host = "-".join(bundle.target())
    if host not in PLATFORMS:
        raise ValueError(f"No release asset for the host platform {host}")
    if shutil.which("hc") is None:
        raise ValueError("hc must be on PATH for --install-check")
    with tempfile.TemporaryDirectory(prefix="jira-peek-release-check-") as temporary:
        # Resolve macOS /var -> /private/var; the installer rejects symlinked parents.
        work = Path(temporary).resolve()
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", "HEAD"],
            capture_output=True, check=False,
        )
        if archive.returncode != 0:
            raise ValueError("Could not read HEAD for the install check")
        source = work / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(source)
        runtime = source / ".release-runtime"
        runtime.mkdir()
        binary = f"jira-peek-bridge-{host}"
        for name in (binary, binary + ".json", binary + "-NOTICES.txt"):
            shutil.copyfile(directory / name, runtime / name)
            (runtime / name).chmod(0o700 if name == binary else 0o600)
        app_home = work / "app"
        result = subprocess.run(
            [str(runtime / binary), "manage", "install", "--source-root", str(source),
             "--app-home", str(app_home), "--check"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise ValueError(
                "Host install check failed: " + (result.stderr.strip() or result.stdout.strip() or "unknown error")
            )
        print(f"install check ok: {host} {version}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing the 12 flattened release assets")
    parser.add_argument("--version", help="Expected release version (defaults to package.json)")
    parser.add_argument("--install-check", action="store_true", help="Install the host asset from HEAD with --check")
    args = parser.parse_args()
    try:
        version = args.version or json.loads((ROOT / "package.json").read_text())["version"]
        verify(args.directory, version)
        if args.install_check:
            install_check(args.directory, version)
    except (ValueError, OSError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
