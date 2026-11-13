#!/usr/bin/env python3
"""Build production-only runtime assets locally; never upload or publish them."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_bundle", Path(__file__).with_name("runtime-bundle.py"))
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def notices(metadata):
    sections = ["Jira Peek Rust runtime — third-party notices\n\n"
                "This inventory includes the resolved target and build dependencies in Cargo.lock.\n"
                "System libcurl/TLS libraries are dynamically linked, not distributed here.\n"]
    resolved = {node["id"] for node in metadata["resolve"]["nodes"]}
    for package in sorted(metadata["packages"], key=lambda p: (p["name"], p["version"])):
        if package["id"] not in resolved:
            continue
        if package["name"] == "jira-peek-bridge":
            continue
        root = Path(package["manifest_path"]).parent
        paths = sorted(p for p in root.iterdir() if p.is_file() and
                       p.name.lower().startswith(("license", "licence", "copying", "copyright", "notice")))
        for directory in root.iterdir():
            if directory.is_dir() and directory.name.lower() in ("licenses", "licences"):
                paths.extend(sorted(p for p in directory.rglob("*") if p.is_file()))
        if package.get("license_file"):
            paths.append(root / package["license_file"])
        if not paths:
            raise ValueError("Missing license text for " + package["name"])
        sections.append("\n" + "=" * 72 + "\n" + package["name"] + " " + package["version"] +
                        "\nLicense: " + str(package.get("license")) + "\n")
        for path in dict.fromkeys(paths):
            sections.append("\n--- " + path.name + " ---\n" + path.read_text() + "\n")
    return "".join(sections)


def package(output):
    manifest = ROOT / "rust-backend/Cargo.toml"
    # A separate target directory prevents fixture builds from replacing an
    # executable being installed or tested. Build from this source every time.
    target_dir = ROOT / "rust-backend/target/production"
    env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))
    # Rust panic locations can retain source paths even with debug symbols
    # stripped. Never distribute a developer's home/worktree path in a binary.
    flags = (env["CARGO_ENCODED_RUSTFLAGS"].split("\x1f") if env.get("CARGO_ENCODED_RUSTFLAGS")
             else shlex.split(env.get("RUSTFLAGS", "")))
    for source, replacement in ((Path.home(), "/build-home"),
                                (Path(env.get("CARGO_HOME", Path.home() / ".cargo")), "/cargo"),
                                (ROOT, "/jira-peek")):
        flags.append("--remap-path-prefix=" + str(source) + "=" + replacement)
    env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    if bundle.target()[0] == "linux":
        env["CURL_SYS_USE_PKG_CONFIG"] = "1"
    subprocess.run(["cargo", "build", "--locked", "--release", "--no-default-features",
                    "--manifest-path", str(manifest)], env=env, check=True)
    binary = target_dir / "release/jira-peek-bridge"
    info = bundle.build_info(binary)
    host = next(line.removeprefix("host: ") for line in subprocess.check_output(["rustc", "-vV"], text=True).splitlines()
                if line.startswith("host: "))
    metadata = json.loads(subprocess.check_output(["cargo", "metadata", "--locked", "--format-version", "1", "--filter-platform", host,
                                                  "--manifest-path", str(manifest)], env=env))
    version = json.loads((ROOT / "package.json").read_text())["version"]
    if json.loads((ROOT / "mods/jira-peek/mod.json").read_text())["version"] != version:
        raise ValueError("Package and mod versions disagree")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    binary_name, manifest_name, notices_name = bundle.asset_names()
    with tempfile.TemporaryDirectory(prefix=".runtime-stage-", dir=output) as temporary:
        stage = Path(temporary)
        shutil.copy2(binary, stage / binary_name)
        (stage / binary_name).chmod(0o755)
        (stage / notices_name).write_text(notices(metadata))
        files = {name: {"size": (stage / name).stat().st_size,
                        "sha256": hashlib.sha256((stage / name).read_bytes()).hexdigest()}
                 for name in (binary_name, notices_name)}
        (stage / manifest_name).write_text(json.dumps({"format": 1, "releaseVersion": version,
            "platform": "-".join(bundle.target()), "sourceSha256": bundle.source_digest(ROOT / "rust-backend"),
            "buildInfo": info, "files": files}, indent=2) + "\n")
        # Publish the manifest last. A partial local package fails validation.
        for name in (binary_name, notices_name, manifest_name):
            (stage / name).replace(output / name)
    print("Prepared production runtime assets: " + str(output))
    print("No tag, release, upload, or publication was performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".release-runtime")
    args = parser.parse_args()
    try:
        package(args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
