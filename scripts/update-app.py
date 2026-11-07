#!/usr/bin/env python3
"""Update Jira Peek from numbered release tags, or restore a local backup."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = "https://github.com/hilmimuktitama/herdr-app-jira-peek.git"
RELEASE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")

# Ship the same ownership, hash and replacement rules with the updater.
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("install_app", Path(__file__).with_name("install-app.py"))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def version_tuple(version):
    if not isinstance(version, str) or not RELEASE.fullmatch(version):
        raise ValueError("Expected a numbered release such as 0.1.1")
    return tuple(map(int, version.split(".")))


def default_app_home():
    # An installed helper targets its own app home, even if the shell has a
    # different HERDR_APP_HOME. --app-home is the explicit override.
    path = Path(__file__).resolve()
    if path.parent.name == "runtime" and path.parents[1].name == "jira-peek" and path.parents[2].name == "mods":
        return path.parents[3]
    return Path(os.environ.get("HERDR_APP_HOME", "~/.config/herdr-app"))


def git(*args, cwd=None):
    if not shutil.which("git"):
        raise ValueError("Git is required for updates; local rollback remains available")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"):
        env.pop(name, None)
    try:
        # Download checkouts are short-lived. Detached maintenance can keep
        # writing their object database after the enclosing command returns.
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null",
                                 "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args], cwd=cwd,
                                env=env, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        raise ValueError("Git timed out; check network access and try again") from None
    if result.returncode:
        # Git's stderr can contain private credential-helper or URL details.
        raise ValueError("Git could not read the release; check network access and your Git repository access")
    return result.stdout.strip()


def release_tags():
    tags = {}
    for line in git("ls-remote", "--tags", "--refs", REPOSITORY, "refs/tags/v*").splitlines():
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            continue
        version = parts[1].removeprefix("refs/tags/v")
        if parts[1].startswith("refs/tags/v") and RELEASE.fullmatch(version):
            tags[version] = parts[0]
    if not tags:
        raise ValueError("No numbered release tags are available; the installed mod was left unchanged")
    return tags


def download_release(directory, version, expected):
    git("init", "--quiet", str(directory))
    git("fetch", "--quiet", "--no-tags", "--depth", "1", REPOSITORY,
        "refs/tags/v" + version, cwd=directory)
    if git("rev-parse", "FETCH_HEAD", cwd=directory) != expected:
        raise ValueError("The release tag changed during download; nothing was installed")
    git("checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=directory)
    for path in directory.rglob("*"):
        if ".git" not in path.relative_to(directory).parts and path.is_symlink():
            raise ValueError("Release contains a symlink; nothing was installed")
    for name in ("package.json", "mods/jira-peek/mod.json"):
        metadata = json.loads((directory / name).read_text())
        if not isinstance(metadata, dict) or metadata.get("version") != version:
            raise ValueError("Release tag and package versions disagree; nothing was installed")
    if not (directory / "scripts/install-app.py").is_file():
        raise ValueError("Release is missing its installer; nothing was installed")
    return git("rev-parse", "HEAD", cwd=directory)


def installation_failure(app_home, destination):
    # A failed acknowledgement does not establish whether replacement happened.
    # Never include subprocess stdout/stderr in this diagnostic.
    try:
        confirmed = installer.managed_install(destination)
        version = confirmed["version"]
    except (OSError, ValueError):
        return ValueError("Release installation failed or was interrupted; installed state is unknown. "
                          "Inspect the installation before retrying or repairing it.")
    return ValueError("Release installation failed or was interrupted. Installed version " + version +
                      " is confirmed; integration was not verified. " + installer.repair_guidance(app_home))


def update(app_home, version=None, check_only=False, allow_downgrade=False):
    app_home = installer.safe_path(app_home)
    destination = installer.safe_path(app_home / "mods/jira-peek")
    if not destination.exists():
        raise ValueError("Install Jira Peek first with scripts/install-app.py --check")
    current = installer.managed_install(destination)
    installed_version = current.get("version")
    installed = version_tuple(installed_version)
    if version is not None:
        version_tuple(version)
    tags = release_tags()
    selected = version or max(tags, key=version_tuple)
    if selected not in tags:
        raise ValueError("The requested release tag is unavailable")
    print("Installed: " + installed_version + "; selected release: " + selected)
    print("Release notes: https://github.com/hilmimuktitama/herdr-app-jira-peek/blob/v" + selected + "/CHANGELOG.md")
    if selected == installed_version:
        print("Already on this release; no files changed. Layout activation is unverified.")
        if not check_only:
            print(installer.repair_guidance(app_home))
        return
    if check_only:
        print("A different release is available. Run without --check to install it." if version_tuple(selected) > installed
              else "The selected release is older; installation requires --version and --allow-downgrade.")
        return
    if version_tuple(selected) < installed and not (version and allow_downgrade):
        raise ValueError("Refusing a downgrade; select --version explicitly and add --allow-downgrade")
    installer.require_capabilities(installer.capabilities())
    with tempfile.TemporaryDirectory(prefix="jira-peek-release-") as temporary:
        source = Path(temporary).resolve() / "source"
        commit = download_release(source, selected, tags[selected])
        # The installed files must still match the pre-download snapshot.
        if installer.managed_install(destination) != current:
            raise ValueError("Installation changed during download; try again")
        print("Installing v" + selected + " at " + commit, flush=True)
        try:
            result = subprocess.run([sys.executable, "-B", str(source / "scripts/install-app.py"),
                                     "--app-home", str(app_home), "--update", "--check"], cwd=source,
                                    capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.SubprocessError):
            raise installation_failure(app_home, destination) from None
        if result.returncode:
            raise installation_failure(app_home, destination)
        print(result.stdout, end="")
    confirmed = installer.managed_install(destination)
    if confirmed.get("version") != selected:
        raise ValueError("Installed version differs from the selected release; inspect the installation before retrying")
    print("Update complete. Herdr hot-reloads mods; reopen the window if it still shows the previous version.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-home", type=Path, default=default_app_home())
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--version", help="Select an exact numbered release (for example 0.1.1)")
    actions.add_argument("--rollback", metavar="BACKUP", help="Restore a named local backup without network access")
    actions.add_argument("--repair-integration", nargs="?", const="main", metavar="LAYOUT",
                         help="Repair personal toolbar/layout locally without downloading or reinstalling")
    actions.add_argument("--diagnose-integration", nargs="?", const="", metavar="LAYOUT",
                         help="Inspect active integration or an explicit source layout without changing files or downloading")
    parser.add_argument("--check", action="store_true", help="Only check release availability; do not install")
    parser.add_argument("--allow-downgrade", action="store_true", help="Allow an explicitly selected older release")
    args = parser.parse_args()
    try:
        if args.diagnose_integration is not None:
            if args.check or args.allow_downgrade:
                raise ValueError("--diagnose-integration cannot be combined with --check or --allow-downgrade")
            installer.diagnose_integration(args.app_home, args.diagnose_integration or None)
            return
        if args.repair_integration is not None:
            if args.check or args.allow_downgrade:
                raise ValueError("--repair-integration cannot be combined with --check or --allow-downgrade")
            installer.repair_integration(args.app_home, args.repair_integration)
            return
        if args.allow_downgrade and not args.version:
            raise ValueError("--allow-downgrade requires --version")
        if args.rollback:
            if args.check:
                raise ValueError("--check cannot be combined with --rollback")
            installer.rollback(args.app_home, args.rollback, check=True)
        else:
            update(args.app_home, args.version, args.check, args.allow_downgrade)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
