#!/usr/bin/env python3
"""Check release metadata, or prepare a new version locally without publishing."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
MANIFESTS = ("package.json", "mods/jira-peek/mod.json")


def check(root, tag=None):
    versions = [json.loads((root / name).read_text()).get("version") for name in MANIFESTS]
    version = versions[0]
    if not isinstance(version, str) or not VERSION.fullmatch(version) or versions != [version, version]:
        raise ValueError("Package and mod must have the same numbered version")
    headings = re.findall(r"^## (\d+\.\d+\.\d+)(?:\s|$)", (root / "CHANGELOG.md").read_text(), re.M)
    if not headings or headings[0] != version or headings.count(version) != 1:
        raise ValueError("The newest changelog release must match the package version exactly once")
    if tag is not None and tag != "v" + version:
        raise ValueError("Release tag must match v" + version)
    return version


def prepare(root, version):
    current = check(root)
    if not VERSION.fullmatch(version) or tuple(map(int, version.split("."))) <= tuple(map(int, current.split("."))):
        raise ValueError("Choose a numbered version newer than the current version")
    # A local tag must never be repurposed. The publication checklist also
    # checks remote tags; preparation itself does not access the network.
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/tags/v" + version],
                            cwd=root, capture_output=True)
    if result.returncode != 1:
        raise ValueError("The target tag already exists, or Git could not verify it")
    changelog = root / "CHANGELOG.md"
    original = changelog.read_text()
    if re.search(r"^## (?:Historical )?" + re.escape(version) + r"(?:\s|$)", original, re.M):
        raise ValueError("That version already appears in the changelog; choose an unused version")
    pending = re.search(r"^## Unreleased\n(.*?)(?=^## |\Z)", original, re.M | re.S)
    if not pending or not pending.group(1).strip():
        raise ValueError("Add user-facing notes under '## Unreleased' before preparing a release")
    label = " experimental" if version.startswith("0.") else ""
    heading = "## Unreleased\n\n## " + version + label + " — " + date.today().isoformat() + "\n"
    updated = original[:pending.start()] + heading + original[pending.start() + len("## Unreleased\n"):]
    payloads = {}
    for name in MANIFESTS:
        path = root / name
        data = json.loads(path.read_text())
        data["version"] = version
        payloads[path] = json.dumps(data, indent=2) + "\n"
    payloads[changelog] = updated
    for path, content in payloads.items():
        path.write_text(content)
    check(root, "v" + version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="Check versions and release notes (the default)")
    actions.add_argument("--version", help="Bump both manifests and promote Unreleased notes")
    parser.add_argument("--tag", help="Also require this exact tag to match the version")
    args = parser.parse_args()
    try:
        if args.version:
            if args.tag:
                raise ValueError("--tag is only supported when checking a release")
            prepare(ROOT, args.version)
            print("Prepared " + args.version + " locally. Review the diff and follow RELEASING.md.")
        else:
            tag = args.tag or (os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "tag" else None)
            print("Release metadata OK: " + check(ROOT, tag))
    except (ValueError, OSError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
