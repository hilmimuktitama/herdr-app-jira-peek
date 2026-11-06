#!/usr/bin/env python3
"""Install the native mod without modifying shipped layouts or keybindings."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "app-bridge.sh", "app-setup.py", "app-issue.jq", "common.sh", "connection.sh",
    "preferences.sh", "field-plan.sh", "fields.jq", "jira-rest.sh", "clear-cache.sh",
    "install-app.py", "update-app.py",
)
MOD_FILES = ("main.js", "model.js", "demo.js", "mod.json", "fields.schema.json")
ICON_FILES = {"icons/" + name + ".svg" for name in (
    "options", "help", "close", "external-link", "link", "refresh", "copy", "check",
    "chevron-right", "chevron-down", "more", "pin",
)}
AGENT_FILES = {"AGENTS.md", "fields.schema.json"}
UPDATE_FILES = {"runtime/install-app.py", "runtime/update-app.py"}
REQUIRED_FILES = set(MOD_FILES) | ICON_FILES | {"LICENSE", "AGENTS.md"} | {"runtime/" + name for name in RUNTIME}
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


def executable_version(command, prefixes):
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="jira-peek-version-") as temporary:
            result = subprocess.run([executable, "--version"],
                                    env=isolated_environment(Path(temporary)),
                                    capture_output=True, text=True, timeout=10, check=True)
        match = re.fullmatch(r"(?:(?:" + "|".join(map(re.escape, prefixes)) +
                             r")\s+)?(\d+)\.(\d+)\.(\d+)\s*", result.stdout.strip())
        if match:
            return tuple(int(part) for part in match.groups())
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return None


def capabilities():
    """Inspect executable availability without contacting services or reading configuration."""
    found = {name: bool(shutil.which(name)) for name in
             ("herdr-app", "hc", "sh", "jq", "python3", "sha256sum", "shasum", "twg", "curl")}
    version = executable_version("herdr-app", ("herdr-app",))
    core_version = executable_version("hc", ("hc", "herdr-core"))
    checks = {
        "posix": os.name == "posix", "herdr-app >= 0.1.10": version is not None and version >= (0, 1, 10),
        "hc": found["hc"], "sh": found["sh"], "jq": found["jq"], "python3": found["python3"],
        "sha256sum or shasum": found["sha256sum"] or found["shasum"],
        "twg or curl": found["twg"] or found["curl"],
    }
    return {"ok": all(checks.values()), "required": checks,
            "herdr_app_version": ".".join(map(str, version)) if version else None,
            "herdr_core_version": ".".join(map(str, core_version)) if core_version else None,
            "token_setup": {"ok": found["python3"] and found["curl"],
                            "required": {"python3": found["python3"], "curl": found["curl"]}},
            "alternatives": {name: found[name] for name in ("sha256sum", "shasum", "twg", "curl")}}


def require_capabilities(report):
    missing = ["herdr-core CLI (hc)" if name == "hc" else name
               for name, available in report["required"].items() if not available]
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
    if not isinstance(old.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", old["version"]):
        raise ValueError("Invalid installation version; move the mod aside and reinstall")
    former_files = REQUIRED_FILES - UPDATE_FILES - ICON_FILES
    previous_files = former_files - AGENT_FILES
    legacy_files = previous_files - {"runtime/app-setup.py"}
    known_legacy = set(files) in (former_files, previous_files) or (
        old.get("version") in {"0.1.0", "0.2.0", "0.3.0"} and set(files) == legacy_files) or (
        old.get("version") == "0.5.0" and set(files) == previous_files | {"runtime/app-document.py"})
    # Format 1 inventories every managed file, allowing later releases to add
    # helpers without making an older updater reject the successful update.
    # Unversioned manifests retain their historical, exact allowlists.
    if "format" in old:
        known_files = (type(old["format"]) is int and old["format"] == 1 and
                       {"main.js", "mod.json", "LICENSE", "runtime/app-bridge.sh"} <= set(files))
    else:
        known_files = set(files) in (REQUIRED_FILES, REQUIRED_FILES - ICON_FILES) or known_legacy
    if not known_files or not isinstance(old.get("configDir"), (str, type(None))):
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


@contextmanager
def installation_lock(app_home):
    """Serialize installs and restores without leaving a stale lock after a crash."""
    os.umask(0o077)
    mods = safe_path(safe_path(app_home) / "mods")
    mods.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = safe_path(mods / ".jira-peek-install.lock")
    with lock.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another Jira Peek installation is in progress; try again when it finishes")
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def native_check(staged):
    require_capabilities(capabilities())
    with tempfile.TemporaryDirectory(prefix="jira-peek-check-") as home:
        base = Path(home)
        checked = base / "mod"
        shutil.copytree(staged, checked)
        # Never connect the checker to the user's selected configuration.
        marker = checked / "install.json"
        if marker.exists():
            manifest = json.loads(marker.read_text())
            manifest["configDir"] = None
            marker.write_text(json.dumps(manifest))
        result = subprocess.run([shutil.which("herdr-app"), "check", str(checked)],
                                env=isolated_environment(base), capture_output=True, timeout=60)
        if result.returncode:
            raise ValueError("Herdr native check failed; existing installation was preserved")


def replace_install(staged, destination, expected):
    # The checker may take time. Revalidate before moving anything, including
    # edits made by an editor or an older installer that does not take our lock.
    safe_path(destination)
    managed_install(staged)
    if (managed_install(destination) if destination.exists() else None) != expected:
        raise ValueError("Installation changed during validation; try again")
    backup = None
    if destination.exists():
        backup = destination.parent / (".jira-peek-backup-" + uuid.uuid4().hex[:12])
        destination.rename(backup)
    try:
        staged.rename(destination)
    except OSError:
        if backup is not None:
            backup.rename(destination)
        raise
    if backup is not None:
        print("Previous mod preserved in mods/" + backup.name)
        print("To restore, pass --rollback " + backup.name + " to the update helper.")


def attachment_plan(app_home, source):
    """Prepare an explicit personal layout; never edit shipped or existing files."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source):
        raise ValueError("--attach needs a layout name, such as main")
    app_home = safe_path(app_home)
    source_path = safe_path(app_home / "layouts" / (source + ".json"))
    if not source_path.is_file():
        raise ValueError("Open Herdr once to create its layouts, then retry --attach")
    layout = json.loads(source_path.read_text(), object_pairs_hook=unique_object)

    def nodes(node):
        if not isinstance(node, dict):
            raise ValueError("Invalid source layout")
        yield node
        for child in node.get("children", []):
            yield from nodes(child)

    all_nodes = list(nodes(layout))
    node_ids = [n["id"] for n in all_nodes if isinstance(n.get("id"), str)]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Source layout has duplicate IDs; resolve them before attaching. No layout was changed")
    tabs = [n for n in all_nodes if n.get("content", {}).get("mod") == "tabs"]
    body = [n for n in all_nodes if n.get("id") == "work-body" and n.get("type") == "row"]
    panels = [n for n in all_nodes if n.get("content", {}).get("mod") == "jira-peek"]
    if len(tabs) != 1 or len(body) != 1 or len(panels) > 1:
        raise ValueError("This layout needs manual attachment; see docs/PANEL-INTEGRATION.md. No layout was changed")
    if not panels:
        if any(n.get("id") == "jira-peek" for n in all_nodes):
            raise ValueError("Layout ID jira-peek is occupied; no layout was changed")
        panel = {"id": "jira-peek", "type": "block", "size": {"px": 360}, "min": 300, "max": 640,
                 "content": {"mod": "jira-peek"}}
        body[0].setdefault("children", []).append(panel)
    else:
        panel = panels[0]
        if panel not in body[0].get("children", []) or not isinstance(panel.get("id"), str):
            raise ValueError("Existing Peek panel needs manual attachment; no layout was changed")
    panel_id = json.dumps(panel["id"])
    stock = safe_path(app_home / "mods/tabs/main.js").read_text()
    import_line = 'import { h_flex } from "gpui-base";'
    marker = '      .when(w?.buttons,'
    if stock.count(import_line) != 1 or stock.count(marker) != 1 or 'function find(node, id)' not in stock:
        raise ValueError("This Herdr toolbar needs manual integration; see docs/PANEL-INTEGRATION.md")
    toggle = '''      .when(!!find(root, PANEL_ID), el => {
        const peek = find(root, PANEL_ID);
        return el.child(Toggle.new("panel-jira-peek")
          .accessibility_label("Jira Peek").pressed(!peek.hidden)
          .h(26).px(8).flex_none().rounded(6).text_size(settings().ui_font_size)
          .bg(peek.hidden ? t.chrome : t.selected).text_color(peek.hidden ? t.muted : t.foreground)
          .hover(s => s.bg(t.hover)).focus(s => s.bg(t.selected))
          .on_mouse_down("left", stop)
          .on_change(() => run("layout.toggle", { id: peek.id })).child("Jira Peek"));
      })
'''.replace("PANEL_ID", panel_id)
    toolbar = stock.replace(import_line, 'import { h_flex, Toggle } from "gpui-base";').replace(marker, toggle + marker)
    tabs[0]["content"]["mod"] = "tabs-jira-peek"
    name = source + "-jira-peek"
    files = {
        safe_path(app_home / "mods/tabs-jira-peek/main.js"): toolbar,
        safe_path(app_home / "mods/tabs-jira-peek/mod.json"): '{"place":"none","title":"Tabs with Jira Peek"}\n',
        safe_path(app_home / "layouts" / (name + ".json")): json.dumps(layout, indent=2) + "\n",
    }
    for path, content in files.items():
        if path.exists() and (not path.is_file() or path.read_text() != content):
            raise ValueError("Personal toolbar or layout already exists and differs. It was preserved; omit --attach and use docs/PANEL-INTEGRATION.md")
    return name, files


def attach(plan, app_home):
    name, files = plan
    created = []
    try:
        for path, content in files.items():
            safe_path(path)
            if path.exists():
                if path.read_text() != content:
                    raise ValueError("Personal integration changed during installation; existing files were preserved")
                continue
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("x") as stream:
                created.append(path)
                stream.write(content)
    except (OSError, ValueError):
        for path in reversed(created):
            if path.is_file() and path.read_text() == files[path]:
                path.unlink()
        raise
    print("Panel and toolbar ready in personal layout " + name + ". Select it in Herdr's Layout menu, or run:")
    print("HERDR_APP_HOME=" + shlex.quote(str(safe_path(app_home))) + " herdr-app do layout.switch " + shlex.quote(json.dumps({"name": name})))


def install(app_home, config_dir=None, update=False, check=False, attach_layout=None):
    with installation_lock(app_home):
        plan = attachment_plan(app_home, attach_layout) if attach_layout else None
        if plan and check:
            with tempfile.TemporaryDirectory(prefix="jira-peek-toolbar-") as temporary:
                staged = Path(temporary)
                for path, content in plan[1].items():
                    if path.parent.name == "tabs-jira-peek":
                        (staged / path.name).write_text(content)
                native_check(staged)
        destination = install_locked(app_home, config_dir, update, check)
        if plan:
            attach(plan, app_home)
        return destination


def install_locked(app_home, config_dir=None, update=False, check=False):
    os.umask(0o077)
    app_home = safe_path(app_home)
    mods = safe_path(app_home / "mods")
    destination = safe_path(mods / "jira-peek")
    config = safe_path(app_home / "data/jira-peek/config")
    example = safe_path(config / "config.example.sh")
    old = None
    if destination.exists():
        if not update:
            raise ValueError("Jira Peek already exists; use --update for a managed installation")
        old = managed_install(destination)
        config_dir = config_dir or old.get("configDir")
    if config_dir is not None:
        config_dir = str(Path(os.path.abspath(Path(config_dir).expanduser())))
    mods.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = Path(tempfile.mkdtemp(prefix=".jira-peek-install-", dir=mods))
    try:
        for name in (*MOD_FILES, *sorted(ICON_FILES)):
            (staged / name).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(ROOT / "mods/jira-peek" / name, staged / name)
        runtime = staged / "runtime"
        runtime.mkdir(mode=0o700)
        for name in RUNTIME:
            shutil.copyfile(ROOT / "scripts" / name, runtime / name)
        shutil.copyfile(ROOT / "LICENSE", staged / "LICENSE")
        shutil.copyfile(ROOT / "docs/AGENT-GUIDE.md", staged / "AGENTS.md")
        version = json.loads((staged / "mod.json").read_text())["version"]
        if version != json.loads((ROOT / "package.json").read_text())["version"]:
            raise ValueError("Package and mod versions disagree; existing installation was preserved")
        files = {str(p.relative_to(staged)): digest(p) for p in sorted(staged.rglob("*")) if p.is_file()}
        (staged / "install.json").write_text(json.dumps({
            "owner": "herdr-jira-peek", "format": 1, "version": version, "configDir": config_dir, "files": files,
        }, indent=2) + "\n")
        if check:
            native_check(staged)
        config.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not example.exists():
            with example.open("x") as stream:
                stream.write((ROOT / "config.example.sh").read_text())
        replace_install(staged, destination, old)
        print("Installed Jira Peek " + version + " for herdr-app >= 0.1.10 (desktop UI). Layouts and keys were preserved.")
        print("herdr-core is the separate terminal backend: hc must be on PATH; its version is independent of herdr-app.")
        print("To create a personal layout with the panel and toolbar button, use --attach (see README.md#show-the-panel).")
        print("Choose Set up Jira in the panel, or select an existing private configuration folder.")
        print("Agent configuration guide: " + str(destination / "AGENTS.md"))
        return destination
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def rollback(app_home, name, check=False):
    if not re.fullmatch(r"\.jira-peek-backup-[0-9a-f]{12}", name):
        raise ValueError("Use the backup folder name printed by the installer")
    with installation_lock(app_home):
        mods = safe_path(safe_path(app_home) / "mods")
        destination = safe_path(mods / "jira-peek")
        current = managed_install(destination)
        backup = safe_path(mods / name)
        restored = managed_install(backup)
        staged = Path(tempfile.mkdtemp(prefix=".jira-peek-install-", dir=mods))
        try:
            for file in restored["files"]:
                target = staged / file
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(backup / file, target)
            restored["configDir"] = current.get("configDir")
            (staged / "install.json").write_text(json.dumps(restored, indent=2) + "\n")
            if check:
                native_check(staged)
            replace_install(staged, destination, current)
            print("Restored Jira Peek " + restored["version"] + ". Current settings and the selected backup were preserved.")
            return destination
        finally:
            if staged.exists():
                shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-home", type=Path, default=Path(os.environ.get("HERDR_APP_HOME", "~/.config/herdr-app")))
    parser.add_argument("--config-dir", help="Existing private config.sh directory; its contents are never copied")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--update", action="store_true", help="Update an unmodified managed installation, keeping a backup")
    actions.add_argument("--rollback", metavar="BACKUP", help="Restore a named local backup, preserving current settings")
    parser.add_argument("--check", action="store_true", help="Run Herdr's native mod checker before installing")
    parser.add_argument("--attach", nargs="?", const="main", metavar="LAYOUT",
                        help="Create a personal copy of main (or LAYOUT) with the panel and toolbar button; print how to select it")
    actions.add_argument("--doctor", action="store_true", help="Report required capabilities without installing")
    parser.add_argument("--json", action="store_true", help="Print doctor results as JSON")
    args = parser.parse_args()
    try:
        if args.attach and (args.doctor or args.rollback):
            raise ValueError("--attach is for installation or --update, not --doctor or --rollback")
        if args.json and not args.doctor:
            raise ValueError("--json requires --doctor")
        if args.doctor:
            report = capabilities()
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("herdr-app version (desktop UI): " + (report["herdr_app_version"] or "unavailable or unrecognized"))
                print("herdr-core version (hc terminal backend): " + (report["herdr_core_version"] or "unavailable or unrecognized"))
                print("These versions are independent. The >= 0.1.10 requirement applies only to herdr-app; no numeric core minimum is enforced.")
                for name, available in report["required"].items():
                    label = "herdr-core CLI (hc on PATH)" if name == "hc" else name
                    print(f"Required {label}: {'available' if available else 'missing or unsupported'}")
                for name, available in report["alternatives"].items():
                    print(f"Alternative {name}: {'available' if available else 'missing'}")
                for name, available in report["token_setup"]["required"].items():
                    print(f"Token setup {name}: {'available' if available else 'missing'}")
            if not report["ok"]:
                parser.exit(1)
            return
        if args.rollback:
            if args.config_dir:
                raise ValueError("--config-dir cannot be combined with --rollback")
            rollback(args.app_home, args.rollback, args.check)
        else:
            install(args.app_home, args.config_dir, args.update, args.check, args.attach)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
