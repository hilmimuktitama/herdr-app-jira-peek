#!/usr/bin/env python3
"""Install the native mod without modifying shipped layouts or keybindings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "app-bridge.sh", "app-setup.py", "app-issue.jq", "common.sh", "connection.sh",
    "preferences.sh", "field-plan.sh", "fields.jq", "jira-rest.sh", "clear-cache.sh",
)
MOD_FILES = ("main.js", "model.js", "demo.js", "mod.json", "fields.schema.json")
AGENT_FILES = {"AGENTS.md", "fields.schema.json"}
REQUIRED_FILES = set(MOD_FILES) | {"LICENSE", "AGENTS.md"} | {"runtime/" + name for name in RUNTIME}
HERDR_GENERATED = {"gpui-kit.d.ts", "jsconfig.json"}


def isolated_environment(base):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HERDR_", "HC_", "TWG_", "CURL_", "XDG_"))}
    env.update(HERDR_APP_HOME=str(base / "app"), HERDR_TELEMETRY="0",
               HC_SESSION="jira-peek-check", HC_SOCKET=str(base / "hc.sock"),
               XDG_STATE_HOME=str(base / "state"), XDG_CONFIG_HOME=str(base / "config"),
               XDG_CACHE_HOME=str(base / "cache"), XDG_RUNTIME_DIR=str(base / "run"))
    (base / "run").mkdir(mode=0o700, exist_ok=True)
    return env


def capabilities():
    """Inspect executable availability without contacting services or reading configuration."""
    found = {name: bool(shutil.which(name)) for name in
             ("herdr-app", "hc", "sh", "jq", "python3", "sha256sum", "shasum", "twg", "curl")}
    version = None
    if found["herdr-app"]:
        try:
            with tempfile.TemporaryDirectory(prefix="jira-peek-version-") as temporary:
                result = subprocess.run([shutil.which("herdr-app"), "--version"],
                                        env=isolated_environment(Path(temporary)),
                                        capture_output=True, text=True, timeout=10, check=True)
            match = re.fullmatch(r"(?:herdr-app\s+)?(\d+)\.(\d+)\.(\d+)(?:\s*)", result.stdout.strip())
            if match:
                version = tuple(int(part) for part in match.groups())
        except (OSError, subprocess.SubprocessError, UnicodeError):
            pass
    checks = {
        "posix": os.name == "posix", "herdr-app >= 0.1.10": version is not None and version >= (0, 1, 10),
        "hc": found["hc"], "sh": found["sh"], "jq": found["jq"], "python3": found["python3"],
        "sha256sum or shasum": found["sha256sum"] or found["shasum"],
        "twg or curl": found["twg"] or found["curl"],
    }
    return {"ok": all(checks.values()), "required": checks,
            "herdr_app_version": ".".join(map(str, version)) if version else None,
            "token_setup": {"ok": found["python3"] and found["curl"],
                            "required": {"python3": found["python3"], "curl": found["curl"]}},
            "alternatives": {name: found[name] for name in ("sha256sum", "shasum", "twg", "curl")}}


def require_capabilities(report):
    missing = [name for name, available in report["required"].items() if not available]
    if missing:
        raise ValueError("Missing or unsupported required capabilities: " + ", ".join(missing))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest key")
        result[key] = value
    return result


def managed_install(destination):
    marker = destination / "install.json"
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("Existing mod is not managed; move it aside before installing")
    try:
        old = json.loads(marker.read_text(), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid installation manifest; move the mod aside and reinstall")
    if not isinstance(old, dict) or old.get("owner") != "herdr-jira-peek" or not isinstance(old.get("files"), dict):
        raise ValueError("Invalid installation manifest; move the mod aside and reinstall")
    files = old["files"]
    previous_files = REQUIRED_FILES - AGENT_FILES
    legacy_files = previous_files - {"runtime/app-setup.py"}
    known_legacy = set(files) == previous_files or (
        old.get("version") in {"0.1.0", "0.2.0", "0.3.0"} and set(files) == legacy_files) or (
        old.get("version") == "0.5.0" and set(files) == previous_files | {"runtime/app-document.py"})
    if (set(files) != REQUIRED_FILES and not known_legacy) or not isinstance(old.get("configDir"), (str, type(None))):
        raise ValueError("Incomplete or unexpected installation manifest; move the mod aside and reinstall")
    for name, expected in files.items():
        if (not isinstance(name, str) or not name or "\\" in name or
                name.startswith("/") or any(part in ("", ".", "..") for part in name.split("/")) or
                name == "install.json" or not isinstance(expected, str) or
                not re.fullmatch(r"[0-9a-f]{64}", expected)):
            raise ValueError("Invalid installation manifest; move the mod aside and reinstall")
        path = safe_path(destination / name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("Installed mod has local edits or missing files; preserve them before updating")
    allowed_dirs = {str(parent) for name in files for parent in Path(name).parents if str(parent) != "."}
    for path in destination.rglob("*"):
        relative = path.relative_to(destination).as_posix()
        if relative in HERDR_GENERATED and not path.is_symlink() and path.is_file():
            continue
        if path.is_symlink() or (path.is_dir() and relative not in allowed_dirs) or (
                not path.is_dir() and relative not in files and relative != "install.json"):
            raise ValueError("Installed mod contains unmanaged files or symlinks; move them aside before updating")
    return old


def safe_path(path):
    path = Path(os.path.abspath(path.expanduser()))
    if path == Path(path.anchor):
        raise ValueError("Refusing a filesystem root as the installation directory")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Refusing a symlink in the installation path")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(app_home, config_dir=None, update=False, check=False):
    os.umask(0o077)
    app_home = safe_path(app_home)
    mods = safe_path(app_home / "mods")
    destination = safe_path(mods / "jira-peek")
    config = safe_path(app_home / "data/jira-peek/config")
    example = safe_path(config / "config.example.sh")
    if destination.exists():
        if not update:
            raise ValueError("Jira Peek already exists; use --update for a managed installation")
        old = managed_install(destination)
        config_dir = config_dir or old.get("configDir")
    if config_dir is not None:
        config_dir = str(Path(os.path.abspath(Path(config_dir).expanduser())))
    if check:
        require_capabilities(capabilities())
    mods.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = Path(tempfile.mkdtemp(prefix=".jira-peek-install-", dir=mods))
    backup = None
    try:
        for name in MOD_FILES:
            shutil.copyfile(ROOT / "mods/jira-peek" / name, staged / name)
        runtime = staged / "runtime"
        runtime.mkdir(mode=0o700)
        for name in RUNTIME:
            shutil.copyfile(ROOT / "scripts" / name, runtime / name)
        shutil.copyfile(ROOT / "LICENSE", staged / "LICENSE")
        shutil.copyfile(ROOT / "docs/AGENT-GUIDE.md", staged / "AGENTS.md")
        files = {str(p.relative_to(staged)): digest(p) for p in sorted(staged.rglob("*")) if p.is_file()}
        (staged / "install.json").write_text(json.dumps({
            "owner": "herdr-jira-peek", "version": "0.1.0", "configDir": config_dir, "files": files,
        }, indent=2) + "\n")
        if check:
            with tempfile.TemporaryDirectory(prefix="jira-peek-check-") as home:
                base = Path(home)
                checked = base / "mod"
                shutil.copytree(staged, checked)
                # The checker must not connect to the user's selected folder,
                # even if a future host starts running deferred initialization.
                check_manifest = json.loads((checked / "install.json").read_text())
                check_manifest["configDir"] = None
                (checked / "install.json").write_text(json.dumps(check_manifest))
                result = subprocess.run([shutil.which("herdr-app"), "check", str(checked)],
                                        env=isolated_environment(base), capture_output=True, timeout=60)
                if result.returncode:
                    raise ValueError("Herdr native check failed; existing installation was preserved")
        config.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not example.exists():
            with example.open("x") as stream:
                stream.write((ROOT / "config.example.sh").read_text())
        if destination.exists():
            backup = mods / (".jira-peek-backup-" + uuid.uuid4().hex[:12])
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
        print("Installed Jira Peek files for Herdr app 0.1.10+. Layouts and keys were preserved.")
        print("If the panel is not visible, attach it to a personal layout: README.md#show-the-panel")
        print("Choose Set up Jira in the panel, or select an existing private configuration folder.")
        print("Agent configuration guide: " + str(destination / "AGENTS.md"))
        if backup is not None:
            print("Previous mod preserved in mods/" + backup.name)
        return destination
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-home", type=Path, default=Path(os.environ.get("HERDR_APP_HOME", "~/.config/herdr-app")))
    parser.add_argument("--config-dir", help="Existing private config.sh directory; its contents are never copied")
    parser.add_argument("--update", action="store_true", help="Update an unmodified managed installation, keeping a backup")
    parser.add_argument("--check", action="store_true", help="Run Herdr's native mod checker before installing")
    parser.add_argument("--doctor", action="store_true", help="Report required capabilities without installing")
    parser.add_argument("--json", action="store_true", help="Print doctor results as JSON")
    args = parser.parse_args()
    try:
        if args.json and not args.doctor:
            raise ValueError("--json requires --doctor")
        if args.doctor:
            report = capabilities()
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("Herdr app version: " + (report["herdr_app_version"] or "unavailable or unrecognized"))
                for name, available in report["required"].items():
                    print(f"Required {name}: {'available' if available else 'missing or unsupported'}")
                for name, available in report["alternatives"].items():
                    print(f"Alternative {name}: {'available' if available else 'missing'}")
                for name, available in report["token_setup"]["required"].items():
                    print(f"Token setup {name}: {'available' if available else 'missing'}")
            if not report["ok"]:
                parser.exit(1)
            return
        install(args.app_home, args.config_dir, args.update, args.check)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
