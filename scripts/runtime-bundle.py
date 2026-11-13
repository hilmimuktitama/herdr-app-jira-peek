#!/usr/bin/env python3
"""Validate and stage a production runtime from local or numbered release assets."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

RELEASES = "https://github.com/hilmimuktitama/herdr-app-jira-peek/releases/download"
MAX_BINARY = 32 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate runtime manifest key")
        result[key] = value
    return result


def target():
    system = {"Darwin": "macos", "Linux": "linux"}.get(platform.system())
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64", "AMD64": "x86_64"}.get(platform.machine())
    if not system or not arch:
        raise ValueError("Rust runtime supports macOS/Linux on arm64 or x86_64; build and validate other targets separately")
    return system, arch


def asset_names():
    name = "jira-peek-bridge-" + "-".join(target())
    return name, name + ".json", name + "-NOTICES.txt"


def source_digest(root):
    required = [root / name for name in ("Cargo.toml", "Cargo.lock", "build.rs", "src/main.rs")]
    if any(not path.is_file() for path in required):
        raise ValueError("Complete Rust runtime source is required")
    paths = [root / "Cargo.toml", root / "Cargo.lock", root / "build.rs", *sorted((root / "src").rglob("*"))]
    digest = hashlib.sha256()
    for path in paths:
        if path.is_symlink():
            raise ValueError("Runtime source contains a symlink")
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def build_info(binary):
    # --build-info reads no Jira configuration. Discard inherited routing/auth
    # overrides and use a temporary HOME for this executable compatibility check.
    with tempfile.TemporaryDirectory(prefix="jira-peek-runtime-check-") as temporary:
        env = {"PATH": os.defpath, "HOME": temporary, "LANG": "C"}
        try:
            result = subprocess.run([str(binary), "--build-info"], env=env, capture_output=True, timeout=5, check=True)
            info = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ValueError("Production runtime could not start on this system; existing installation was preserved") from None
    system, arch = target()
    if (not isinstance(info, dict) or type(info.get("protocol")) is not int or info["protocol"] != 1 or
            info.get("fixtureTransport") is not False or info.get("os") != system or info.get("arch") != arch):
        raise ValueError("Runtime is a fixture build, wrong architecture, or unsupported bridge protocol")
    return info


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("Runtime download refused a non-HTTPS redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, limit, deadline):
    opener = urllib.request.build_opener(HTTPSRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "jira-peek-installer"})
    try:
        with opener.open(request, timeout=max(1, deadline - time.monotonic())) as response, destination.open("xb") as output:
            count = 0
            while True:
                if time.monotonic() > deadline:
                    raise ValueError("Runtime download timed out")
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > limit:
                    raise ValueError("Runtime download exceeded its size limit")
                output.write(chunk)
    except (OSError, ValueError):
        raise ValueError("Could not obtain the numbered release runtime. Existing installation was preserved. "
                         "Retry when release assets are available, or run scripts/package-runtime.py from trusted source first.") from None


def stage(root, runtime, version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid runtime release version")
    binary_name, manifest_name, notices_name = asset_names()
    local = root / ".release-runtime"
    with tempfile.TemporaryDirectory(prefix="jira-peek-runtime-") as temporary:
        source = local if local.exists() else Path(temporary)
        if source == local:
            if local.is_symlink() or not local.is_dir():
                raise ValueError("Local runtime directory must be a regular directory")
        else:
            deadline = time.monotonic() + 35
            base = RELEASES + "/v" + version + "/"
            download(base + manifest_name, source / manifest_name, 16384, deadline)
        manifest_path = source / manifest_name
        if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 16384:
            raise ValueError("Missing or unsafe runtime manifest; run scripts/package-runtime.py for this source")
        manifest = json.loads(manifest_path.read_text(), object_pairs_hook=unique_object)
        if (not isinstance(manifest, dict) or type(manifest.get("format")) is not int or manifest["format"] != 1 or
                manifest.get("releaseVersion") != version or manifest.get("platform") != "-".join(target()) or
                manifest.get("sourceSha256") != source_digest(root / "rust-backend") or
                not isinstance(manifest.get("files"), dict) or
                set(manifest["files"]) != {binary_name, notices_name}):
            raise ValueError("Runtime manifest does not match this release, source, or platform")
        for name, installed, limit in ((binary_name, "jira-peek-bridge", MAX_BINARY),
                                       (notices_name, "THIRD-PARTY-NOTICES.txt", 4 * 1024 * 1024)):
            entry = manifest["files"][name]
            if (not isinstance(entry, dict) or type(entry.get("size")) is not int or not 0 < entry["size"] <= limit or
                    not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
                raise ValueError("Invalid runtime asset metadata")
            if source != local:
                download(base + name, source / name, entry["size"], deadline)
            path = source / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size"]:
                raise ValueError("Missing or unsafe runtime asset")
            output = runtime / installed
            shutil.copyfile(path, output)
            if hashlib.sha256(output.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Runtime checksum mismatch; existing installation was preserved")
            output.chmod(0o700 if name == binary_name else 0o600)
        info = build_info(runtime / "jira-peek-bridge")
        if info != manifest.get("buildInfo"):
            raise ValueError("Runtime build information does not match its manifest")
        (runtime / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # Preserve the legacy entry point for older UI modules/agent callers.
        (runtime / "app-bridge.sh").write_text('#!/bin/sh\nexec "${0%/*}/jira-peek-bridge" "$@"\n')
