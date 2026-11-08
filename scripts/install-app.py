#!/usr/bin/env python3
"""Install the native mod without modifying shipped layouts or keybindings."""
import argparse
import ast
from collections import namedtuple
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import warnings

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "app-bridge.sh", "app-setup.py", "app-issue.jq", "app-fields.jq", "app-metadata.jq", "common.sh", "connection.sh",
    "preferences.sh", "field-plan.sh", "fields.jq", "jira-rest.sh", "clear-cache.sh",
    "install-app.py", "update-app.py",
)
MOD_FILES = ("main.js", "model.js", "demo.js", "mod.json", "fields.schema.json")
ICON_FILES = {"icons/" + name + ".svg" for name in (
    "options", "help", "close", "external-link", "link", "refresh", "copy", "check",
    "chevron-right", "chevron-down", "more", "pin", "play", "pause",
)}
AGENT_FILES = {"AGENTS.md", "fields.schema.json"}
UPDATE_FILES = {"runtime/install-app.py", "runtime/update-app.py"}
REQUIRED_FILES = set(MOD_FILES) | ICON_FILES | {"LICENSE", "AGENTS.md"} | {"runtime/" + name for name in RUNTIME}
NATIVE_PROJECTION_FILES = {"runtime/app-fields.jq", "runtime/app-metadata.jq"}
HERDR_GENERATED = {"gpui-kit.d.ts", "jsconfig.json"}
AttachmentPlan = namedtuple("AttachmentPlan", "name files inputs directories", defaults=(None,))


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
    # Format 1 inventories every managed file, allowing later releases to add
    # helpers without making an older updater reject the successful update.
    # Unversioned manifests retain their historical, exact allowlists.
    if "format" in old:
        known_files = (type(old["format"]) is int and old["format"] == 1 and
                       {"main.js", "mod.json", "LICENSE", "runtime/app-bridge.sh"} <= set(files))
    else:
        known_files = False
        # Preserve exact historical inventories when a release adds helpers.
        for required in (REQUIRED_FILES, REQUIRED_FILES - NATIVE_PROJECTION_FILES):
            former = required - UPDATE_FILES - ICON_FILES
            previous = former - AGENT_FILES
            legacy = previous - {"runtime/app-setup.py"}
            known_files |= set(files) in (required, required - ICON_FILES, former, previous) or (
                old.get("version") in {"0.1.0", "0.2.0", "0.3.0"} and set(files) == legacy) or (
                old.get("version") == "0.5.0" and set(files) == previous | {"runtime/app-document.py"})
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
            recover_replacement(mods)
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


def recover_replacement(mods):
    """Recover only the recorded replacement, under installation_lock."""
    journal = safe_path(mods / ".jira-peek-replacement.json")
    if not journal.exists():
        return
    destination = safe_path(mods / "jira-peek")
    if destination.exists():
        # Includes a crash while writing intent, before either rename, and a
        # crash after activation. A valid active bundle always wins.
        managed_install(destination)
        journal.unlink()
        return
    try:
        record = json.loads(integration_snapshot(journal)[1], object_pairs_hook=unique_object)
        if (not isinstance(record, dict) or set(record) != {"backup", "manifest"} or
                not isinstance(record["backup"], str) or
                not re.fullmatch(r"\.jira-peek-backup-[0-9a-f]{12}", record["backup"]) or
                not isinstance(record["manifest"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["manifest"])):
            raise ValueError("Invalid replacement journal; inspect the installation before retrying")
        backup = safe_path(mods / record["backup"])
        managed_install(backup)
        if digest(backup / "install.json") != record["manifest"]:
            raise ValueError("Replacement backup changed; inspect before retrying")
        backup.rename(destination)
        print("Recovered the previous Jira Peek bundle after an interrupted replacement.")
        journal.unlink()
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not recover interrupted replacement; inspect the installation before retrying") from error


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
        journal = safe_path(destination.parent / ".jira-peek-replacement.json")
        # Persist intent before moving the live bundle. The next mutating
        # installer invocation can restore this exact validated backup.
        with journal.open("x") as stream:
            json.dump({"backup": backup.name, "manifest": digest(destination / "install.json")}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        destination.rename(backup)
    try:
        staged.rename(destination)
    except OSError:
        if backup is not None:
            backup.rename(destination)
            journal.unlink()
        raise
    if backup is not None:
        journal.unlink()
        print("Previous mod preserved in mods/" + backup.name)
        print("To restore, pass --rollback " + backup.name + " to the update helper.")


def integration_snapshot(path):
    """Read one bounded regular file and retain its identity as well as bytes."""
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 4 * 1024 * 1024:
            raise ValueError("Invalid or oversized integration file; existing files were preserved")
        data = stream.read(4 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    identity = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_size, info.st_mtime_ns)
    if identity(before) != identity(after) or identity(after) != identity(path.lstat()):
        raise ValueError("Integration file changed while reading; try again")
    return identity(after), data


def validate_attachment(plan):
    if (any((integration_snapshot(path) if path.exists() or path.is_symlink() else None) != expected
            for path, expected in plan.inputs.items()) or
            any(toolbar_files(path) != expected for path, expected in (plan.directories or {}).items())):
        raise ValueError("Source layout or toolbar changed; integration is incomplete. Retry repair after reviewing personal files")


class IntegrationError(ValueError):
    """Safe, user-facing integration guidance without file contents."""


def read_layout(app_home, source):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", source):
        raise IntegrationError("Use a layout name, such as main")
    source_path = safe_path(app_home / "layouts" / (source + ".json"))
    if not source_path.is_file():
        raise IntegrationError("Source layout is unavailable. Open Herdr once or select an existing source layout")
    source_snapshot = integration_snapshot(source_path)
    try:
        layout = json.loads(source_snapshot[1], object_pairs_hook=unique_object)
    except RecursionError:
        raise IntegrationError("Source layout nesting is too deep; use manual integration") from None
    all_nodes = [node for node, _ in layout_entries(layout)]
    node_ids = [n["id"] for n in all_nodes if isinstance(n.get("id"), str)]
    if len(node_ids) != len(set(node_ids)):
        raise IntegrationError("Source layout has duplicate IDs; resolve them before attaching. No layout was changed")
    return source_path, source_snapshot, layout, all_nodes


def layout_entries(layout):
    pending, count = [(layout, ())], 0
    while pending:
        node, parents = pending.pop()
        count += 1
        if count > 4096 or len(parents) > 64:
            raise IntegrationError("Source layout is too large or deeply nested; use manual integration")
        if (not isinstance(node, dict) or not isinstance(node.get("children", []), list) or
                not isinstance(node.get("content", {}), dict)):
            raise IntegrationError("Invalid source layout")
        yield node, parents
        pending.extend((child, parents + (node,)) for child in reversed(node.get("children", [])))


def parse_integration_json(data, label):
    too_deep = label + " is too deeply nested; use manual integration"
    try:
        value = json.loads(data, object_pairs_hook=unique_object)
    except RecursionError:
        raise IntegrationError(too_deep) from None
    # Decoder recursion limits differ across supported Python versions.
    pending = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        if isinstance(node, (dict, list)):
            if depth >= 128:
                raise IntegrationError(too_deep)
            children = node.values() if isinstance(node, dict) else node
            pending.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))
    return value


def parse_toolbar_metadata(data):
    return parse_integration_json(data, "Toolbar metadata")


def toolbar_node(app_home, all_nodes):
    candidates = []
    for node in all_nodes:
        name = node.get("content", {}).get("mod")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", name):
            continue
        candidate = name == "tabs" or node.get("id") == "tabs"
        if not candidate and name != "jira-peek":
            metadata = safe_path(app_home / "mods" / name / "mod.json")
            if metadata.is_file():
                info = parse_toolbar_metadata(integration_snapshot(metadata)[1])
                origin = info.get("cloned_from") if isinstance(info, dict) else None
                candidate = isinstance(origin, dict) and origin.get("name") == "tabs"
        if candidate:
            candidates.append(node)
    if len(candidates) != 1:
        raise IntegrationError("This layout needs one identifiable tabs toolbar; use manual integration in docs/PANEL-INTEGRATION.md")
    return candidates[0]


def toolbar_files(directory):
    """Inventory a bounded personal mod, including relative imports and assets."""
    files = []
    for path in safe_path(directory).rglob("*"):
        safe_path(path)
        if path.relative_to(directory).as_posix() in HERDR_GENERATED and path.is_file():
            continue
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise IntegrationError("Toolbar contains a non-regular file; use manual integration in docs/PANEL-INTEGRATION.md")
        if len(files) > 256:
            raise IntegrationError("Toolbar has too many files for automatic integration; use manual integration in docs/PANEL-INTEGRATION.md")
    return tuple(sorted(files))


def toolbar_code(source, literals=None):
    """Mask supported literals/comments in linear time, retaining source offsets."""
    code = list(source)
    index = 0
    while index < len(source):
        start = index
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise IntegrationError("Unterminated toolbar comment; use manual integration")
            index = end + 2
        elif source[index] in "\"'`":
            quote = source[index]
            index += 1
            while index < len(source) and source[index] != quote:
                if source[index] == "\\":
                    index += 2
                elif source[index] in "\r\n" and quote != "`":
                    raise IntegrationError("Unsupported toolbar strings; use manual integration")
                else:
                    index += 1
            if index >= len(source):
                raise IntegrationError("Unterminated toolbar string; use manual integration")
            index += 1
            if literals is not None:
                value = source[start + 1:index - 1]
                if "\\" in value:
                    if quote == "`":
                        raise IntegrationError("Escaped toolbar templates need manual integration")
                    if re.search(r"\\(?:a|N|U)", value):
                        raise IntegrationError("Unsupported toolbar string escapes; use manual integration")
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("error")
                            value = ast.literal_eval(source[start:index])
                    except (SyntaxError, ValueError, Warning):
                        raise IntegrationError("Unsupported toolbar string escapes; use manual integration") from None
                literals.append(value)
        else:
            index += 1
            continue
        code[start:index] = ["\n" if char == "\n" else " " for char in source[start:index]]
    return "".join(code)


def toolbar_structure(source, offsets, chain_start, chain_end, render_scope):
    """Check anchor nesting without treating strings or comments as JavaScript.

    This deliberately accepts only the stock builder structure. It is not a
    JavaScript parser; ambiguous/custom syntax is left for manual integration.
    Herdr's native checker validates the completed copy before explicit repair.
    """
    code = toolbar_code(source)
    contexts, stack, terminated = {}, [], False
    for index, char in enumerate(code):
        if index in offsets:
            if char.isspace():
                raise IntegrationError("Toolbar anchors are commented out or quoted; use manual integration in docs/PANEL-INTEGRATION.md")
            contexts[index] = tuple(stack)
        if char in "{([":
            stack.append(index)
            if len(stack) > 128:
                raise IntegrationError("Toolbar nesting is too deep; use manual integration")
        elif char in "})]":
            if not stack or code[stack.pop()] != {"}": "{", ")": "(", "]": "["}[char]:
                raise IntegrationError("Unsupported toolbar nesting; use manual integration in docs/PANEL-INTEGRATION.md")
        elif char in "\"'`":
            raise IntegrationError("Unsupported toolbar strings; use manual integration in docs/PANEL-INTEGRATION.md")
        elif char == ";" and chain_start < index < chain_end and tuple(stack) == render_scope:
            terminated = True
    if stack:
        raise IntegrationError("Unsupported toolbar nesting; use manual integration in docs/PANEL-INTEGRATION.md")
    return contexts, terminated, code


def integrate_toolbar(source, panel_id):
    find = '''function find(node, id) {
  if (node?.id === id) return node;
  for (const child of node?.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}'''
    changes = '      .when(enabled.includes("changes"), el => el.child(panelButton("changes", "Changes", "mods/changes/changes.svg")))\n'
    anchors = (find, '  render() {\n', '    const t = theme();',
               '    const stop = (_e, cx) => cx.stop_propagation();',
               '    const root = layout(), sidebar = find(root, "sidebar"), w = window();', changes)
    if any(source.count(anchor) != 1 for anchor in anchors):
        raise IntegrationError("Toolbar must retain the stock find helper, render bindings and Changes control; use manual integration in docs/PANEL-INTEGRATION.md")
    if 'panel-jira-peek' in source:
        raise IntegrationError("Toolbar already contains a Jira Peek toggle; review its existing target using docs/PANEL-INTEGRATION.md")
    base = re.search(r'^import \{ ([A-Za-z0-9_, ]+) \} from "gpui-base";$', source, re.M)
    host = re.search(r'^import \{ ([A-Za-z0-9_, ]+) \} from "herdr";$', source, re.M)
    view = re.search(r'^export default class [A-Za-z0-9_]+ extends View \{', source, re.M)
    returns = list(re.finditer(r'^    return h_flex\(\)\.', source, re.M))
    if (not base or "h_flex" not in base[1].replace(" ", "").split(",") or not host or
            not {"run", "layout", "settings", "theme"} <= set(host[1].replace(" ", "").split(",")) or not view or len(returns) != 1):
        raise IntegrationError("Toolbar imports or View class differ from the stock contract; use manual integration in docs/PANEL-INTEGRATION.md")
    positions = [source.index(anchor) + len(anchor) - len(anchor.lstrip()) for anchor in anchors]
    returned = returns[0].start() + 4
    render_scope = (view.end() - 1, source.index(anchors[1]) + len(anchors[1]) - 2)
    contexts, terminated, code = toolbar_structure(
        source, {*positions, returned, base.start(), host.start(), view.start()}, returned, positions[-1], render_scope)
    if re.search(r"\\u(?:[0-9A-Fa-f]{4}|\{)", code):
        raise IntegrationError("Escaped toolbar identifiers need manual integration")
    function_call = re.compile(r"[ \t]*\(")
    toggle_call = re.compile(r"[ \t]*\.[ \t]*new[ \t]*\(")
    for binding in re.finditer(r"\b(?:Toggle|find|h_flex|layout|run|settings|theme)\b", code):
        if (base.start() <= binding.start() < base.end() or host.start() <= binding.start() < host.end() or
                binding.start() == positions[0] + len("function ")):
            continue
        call = (toggle_call if binding.group() == "Toggle" else function_call).match(code, binding.end())
        before = binding.start() - 1
        while before >= 0 and code[before].isspace():
            before -= 1
        if before >= 0 and code[before] == "*":
            before -= 1
            while before >= 0 and code[before].isspace():
                before -= 1
        definition = code[max(0, before - 7):before + 1] == "function"
        if not call or definition:
            raise IntegrationError("Toolbar shadows, reassigns or aliases a required stock binding; use manual integration in docs/PANEL-INTEGRATION.md")
    if (contexts[positions[0]] or contexts[positions[1]] != render_scope[:1] or
            any(contexts[position] != render_scope for position in positions[2:]) or
            contexts[returned] != render_scope or not max(positions[2:-1]) < returned < positions[-1] or
            terminated or
            any(contexts[position] for position in (base.start(), host.start(), view.start()))):
        raise IntegrationError("Changes must be in the stock render chain; use manual integration in docs/PANEL-INTEGRATION.md")
    panel_id = json.dumps(panel_id)
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
    toolbar = source.replace(changes, changes + toggle)
    if "Toggle" not in base[1].replace(" ", "").split(","):
        toolbar = toolbar[:base.end(1)] + ", Toggle" + toolbar[base.end(1):]
    return toolbar


def content_bytes(content):
    return content if isinstance(content, bytes) else content.encode("utf-8")


def toolbar_shortcuts(snapshot, name):
    if snapshot is None:
        return False
    try:
        config = json.loads(snapshot[1], object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise IntegrationError("Shortcut configuration could not be checked safely; preserve it with manual integration") from None
    if not isinstance(config, dict):
        raise IntegrationError("Unsupported shortcut configuration; preserve it with manual integration")
    pending, count = [(config, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > 4096 or depth > 64:
            raise IntegrationError("Shortcut configuration is too large or deeply nested; use manual integration")
        if isinstance(value, dict):
            if value.get("mod:" + name):
                return True
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
        elif isinstance(value, str) and (value.startswith(name + ".") or value == "mod:" + name):
            return True
    return False


def attachment_plan(app_home, source, check_conflicts=True):
    """Prepare an explicit personal layout; never edit shipped or existing files."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source):
        raise IntegrationError("Use a source layout name, such as main")
    if source.endswith("-jira-peek"):
        raise IntegrationError("Use the original source layout, not a generated -jira-peek copy. No layout was changed")
    app_home = safe_path(app_home)
    source_path, source_snapshot, layout, all_nodes = read_layout(app_home, source)
    tabs = toolbar_node(app_home, all_nodes)
    body = [n for n in all_nodes if n.get("id") == "work-body" and n.get("type") == "row"]
    panels = [n for n in all_nodes if n.get("content", {}).get("mod") == "jira-peek"]
    if (not panels and len(body) != 1) or len(panels) > 1:
        raise IntegrationError("This layout needs manual attachment; see docs/PANEL-INTEGRATION.md. No layout was changed")
    if not panels:
        if any(n.get("id") == "jira-peek" for n in all_nodes):
            raise IntegrationError("Layout ID jira-peek is occupied; no layout was changed")
        panel = {"id": "jira-peek", "type": "block", "size": {"px": 360}, "min": 300, "max": 640,
                 "content": {"mod": "jira-peek"}}
        body[0].setdefault("children", []).append(panel)
    else:
        panel = panels[0]
        if not isinstance(panel.get("id"), str) or not panel["id"] or panel.get("type") != "block":
            raise IntegrationError("Existing Peek panel needs manual attachment; no layout was changed")
    parents = next(parents for node, parents in layout_entries(layout) if node is panel)
    if any(parent.get("hidden") or parent.get("type") == "stack" for parent in parents):
        raise IntegrationError("Peek panel has a hidden ancestor or stack placement; use manual integration to preserve its visibility controls")
    toolbar_name = tabs["content"]["mod"]
    directory = safe_path(app_home / "mods" / toolbar_name)
    inventory = toolbar_files(directory)
    inputs = {source_path: source_snapshot}
    total = len(source_snapshot[1])
    for path in inventory:
        snapshot = integration_snapshot(path)
        total += len(snapshot[1])
        if total > 16 * 1024 * 1024:
            raise IntegrationError("Toolbar is too large for automatic integration; use manual integration in docs/PANEL-INTEGRATION.md")
        inputs[path] = snapshot
    keys = safe_path(app_home / "keys.json")
    inputs[keys] = integration_snapshot(keys) if keys.exists() else None
    identity = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(toolbar_name) + r"(?![A-Za-z0-9_/-])")
    if toolbar_shortcuts(inputs[keys], toolbar_name):
        raise IntegrationError("Toolbar commands or shortcuts depend on its original mod name; preserve them with manual integration in docs/PANEL-INTEGRATION.md")
    for path, snapshot in inputs.items():
        if path != keys and snapshot is not None and path.suffix in (".js", ".mjs"):
            code = snapshot[1].decode("utf-8")
            literals = []
            masked = toolbar_code(code, literals)
            if any(identity.search(value) or value == "nextCommand" for value in literals) or re.search(r"\bnextCommand\b", masked):
                raise IntegrationError("Toolbar commands or shortcuts depend on its original mod name; preserve them with manual integration in docs/PANEL-INTEGRATION.md")
    main = directory / "main.js"
    if main not in inputs:
        raise IntegrationError("Toolbar main.js is unavailable; use manual integration in docs/PANEL-INTEGRATION.md")
    toolbar = integrate_toolbar(inputs[main][1].decode("utf-8"), panel["id"])
    generated_toolbar = "tabs-jira-peek" if toolbar_name == "tabs" else source + "-tabs-jira-peek"
    target = safe_path(app_home / "mods" / generated_toolbar)
    metadata = {"place": "none", "title": "Tabs with Jira Peek"}
    if toolbar_name != "tabs" and directory / "mod.json" in inputs:
        metadata = parse_toolbar_metadata(inputs[directory / "mod.json"][1])
        if not isinstance(metadata, dict):
            raise IntegrationError("Invalid toolbar metadata; use manual integration in docs/PANEL-INTEGRATION.md")
        metadata = dict(metadata, place="none", title="Tabs with Jira Peek")
    tabs["content"]["mod"] = generated_toolbar
    name = source + "-jira-peek"
    files = {
        target / "main.js": toolbar,
        target / "mod.json": json.dumps(metadata, separators=(",", ":")) + "\n",
    }
    files.update((safe_path(target / path.relative_to(directory)), inputs[path][1]) for path in inventory
                 if path.name not in ("main.js", "mod.json") or path.parent != directory)
    files[safe_path(app_home / "layouts" / (name + ".json"))] = json.dumps(layout, indent=2) + "\n"
    for path, content in files.items():
        safe_path(path)
        if len(content_bytes(content)) > 4 * 1024 * 1024:
            raise IntegrationError("Generated integration file is oversized; existing files were preserved")
        if check_conflicts and path.exists() and integration_snapshot(path)[1] != content_bytes(content):
            raise IntegrationError("Personal file " + path.relative_to(app_home).as_posix() + " differs and was preserved. Use a separately named personal toolbar for manual integration; see docs/PANEL-INTEGRATION.md")
    return AttachmentPlan(name, files, inputs, {directory: inventory})


def cleanup_attachment_staging(directory, contents):
    for path in directory.glob(".jira-peek-attach-*.tmp"):
        match = re.fullmatch(r"\.jira-peek-attach-([1-9][0-9]*)-[a-z0-9_]+\.tmp", path.name)
        if not match:
            continue
        try:
            os.kill(int(match[1]), 0)
        except ProcessLookupError:
            try:
                info, data = integration_snapshot(path)
                if info[3] == os.getuid() and stat.S_IMODE(info[2]) == 0o600 and data in contents:
                    path.unlink()  # Unlink the staging alias only, never its published target.
                else:
                    print("Unverified toolbar staging file preserved; review temporary files before manual cleanup.")
            except (OSError, ValueError):
                print("Unverified toolbar staging file preserved; review temporary files before manual cleanup.")
        except OSError:
            pass  # Live or uninspectable creator: never reclaim its file.


def publish_attachment(path, content):
    """Publish complete bytes exclusively; a failure never leaves a partial target."""
    safe_path(path)
    if path.exists():
        if integration_snapshot(path)[1] != content_bytes(content):
            raise ValueError("Personal integration changed; existing files were preserved")
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe_path(path)
    fd, name = tempfile.mkstemp(prefix=f".jira-peek-attach-{os.getpid()}-", suffix=".tmp", dir=path.parent)
    staged = Path(name)
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content_bytes(content))
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path)
        try:
            os.link(staged, path, follow_symlinks=False)
        except FileExistsError:
            if integration_snapshot(path)[1] != content_bytes(content):
                raise ValueError("Personal integration changed; existing files were preserved") from None
    finally:
        if staged.exists() and (staged.lstat().st_dev, staged.lstat().st_ino) == (identity.st_dev, identity.st_ino):
            staged.unlink()


def attach(plan, app_home):
    validate_attachment(plan)
    for directory in {path.parent for path in plan.files}:
        if directory.is_dir():
            cleanup_attachment_staging(directory, {content_bytes(content) for path, content in plan.files.items() if path.parent == directory})
    for path, content in plan.files.items():
        validate_attachment(plan)
        publish_attachment(path, content)
    validate_attachment(plan)
    if any(integration_snapshot(path)[1] != content_bytes(content) for path, content in plan.files.items()):
        raise ValueError("Personal integration changed before completion; existing files were preserved")
    print("Integration ready. Prepared layout " + plan.name + " from " + next(iter(plan.inputs)).stem + ". Active layout was not changed; activation is unverified. Select it in Herdr's Layout menu, or run:")
    print(selection_command(app_home, plan.name))


def stage_attachment(plan, staged):
    directory = next(iter(plan.files)).parent
    for path, content in plan.files.items():
        if directory in path.parents:
            target = staged / path.relative_to(directory)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content_bytes(content))


def check_attachment(plan):
    with tempfile.TemporaryDirectory(prefix="jira-peek-toolbar-") as temporary:
        staged = Path(temporary)
        stage_attachment(plan, staged)
        native_check(staged)
    validate_attachment(plan)


def repair_guidance(app_home, source="LAYOUT", current_helper=False):
    try:
        home = safe_path(app_home)
        helper = safe_path(Path(__file__).with_name("update-app.py") if current_helper else
                           home / "mods/jira-peek/runtime/update-app.py")
        if helper.is_file():
            code = integration_snapshot(helper)[1].decode("utf-8")
            command = [sys.executable, str(helper), "--app-home", str(home)]
            if "--repair-integration" in code:
                guidance = "If the button is missing, repair toolbar setup locally (LAYOUT means the original source layout, such as main): " + shlex.join([*command, "--repair-integration", source])
                if "--diagnose-integration" in code:
                    guidance += "\nInspect the active layout and its next action: " + shlex.join([*command, "--diagnose-integration"])
                return guidance
    except (OSError, ValueError):
        pass  # Best-effort guidance must not turn a committed install into a failure.
    return "Review docs/PANEL-INTEGRATION.md to repair toolbar setup from the current source."


def selection_command(app_home, name):
    return ("HERDR_APP_HOME=" + shlex.quote(str(safe_path(app_home))) +
            " herdr-app do layout.switch " + shlex.quote(json.dumps({"name": name})))


def active_layout(app_home):
    """Read only the supported status command; never launch or select a window."""
    try:
        result = subprocess.run(["herdr-app", "status"],
                                env=dict(os.environ, HERDR_APP_HOME=str(safe_path(app_home))),
                                capture_output=True, text=True, timeout=5)
        if result.returncode or len(result.stdout) > 4 * 1024 * 1024:
            return None, None
        status = parse_integration_json(result.stdout, "Herdr status")
        name = status.get("layout") if isinstance(status, dict) else None
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", name):
            return name, bool(status.get("errors"))
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError):
        pass  # Do not print status output: it can contain private session data.
    return None, None


def layout_integration(app_home, name):
    _, _, _, nodes = read_layout(app_home, name)
    toolbar = toolbar_node(app_home, nodes)["content"]["mod"]
    panels = [node.get("id") for node in nodes if node.get("content", {}).get("mod") == "jira-peek"]
    panel = panels[0] if len(panels) == 1 and isinstance(panels[0], str) else None
    return toolbar, panel


def manual_integration_guidance(app_home, source):
    try:
        toolbar, panel = layout_integration(app_home, source)
        target = ("use " + json.dumps(panel) + " in both find calls" if panel else
                  "choose one Peek block with a unique ID and use its actual ID in both find calls")
        return ("In a separately named copy of mods/" + toolbar + "/main.js, add or retarget one toggle from "
                "docs/PANEL-INTEGRATION.md immediately after Changes; " + target +
                ". Point a copy of " + source + " at that toolbar and keep one Peek panel.")
    except (OSError, ValueError):
        return "Review the source layout and follow docs/PANEL-INTEGRATION.md for manual integration."


def diagnose_integration(app_home, source=None):
    """Describe installed files and active selection separately from rendering."""
    home = safe_path(app_home)
    bundle = None
    destination = safe_path(home / "mods/jira-peek")
    bundle_present = destination.exists()
    try:
        bundle = managed_install(destination)["version"]
    except (OSError, ValueError):
        pass
    print("Bundle installed: " + ("Jira Peek " + bundle + " (validated)" if bundle else
          "present; managed bundle validation failed" if bundle_present else "not installed"))
    active, errors = active_layout(home)
    print("Active layout: " + (active or "unavailable (Herdr is not running or status could not be read)"))
    if active:
        try:
            toolbar, panel = layout_integration(home, active)
            print("Active toolbar mod: " + toolbar)
            print("Active Jira Peek panel ID: " + (json.dumps(panel) if panel else "none or ambiguous"))
        except (OSError, ValueError):
            print("Active toolbar and panel: unavailable (layout could not be inspected safely)")
    else:
        print("Active toolbar mod: unavailable")
        print("Active Jira Peek panel ID: unavailable")
    selected = source or active
    if not selected:
        print("Automatic integration support: unavailable without a source layout")
        print("Prepared integration layout: unverified without a source layout")
        print("Active integration configured: unavailable")
        print("Next action: " + repair_guidance(home, current_helper=True))
        print("Inspect a source explicitly with --diagnose-integration LAYOUT, even while Herdr is closed.")
        print("Button rendering is unverified; status and files do not establish visible UI.")
        return
    source = selected.removesuffix("-jira-peek")
    print("Source layout: " + source)
    try:
        toolbar, panel = layout_integration(home, source)
        print("Source toolbar mod: " + toolbar)
        print("Source Jira Peek panel ID: " + (json.dumps(panel) if panel else "none (repair adds one) or ambiguous"))
        plan = attachment_plan(home, source, check_conflicts=False)
        existing = {path: integration_snapshot(path)[1] for path in plan.files if path.exists()}
        conflicts = [path for path, data in existing.items() if data != content_bytes(plan.files[path])]
        prepared = len(existing) == len(plan.files) and not conflicts
        validate_attachment(plan)
    except (OSError, ValueError) as error:
        reason = str(error) if isinstance(error, IntegrationError) else "Layout or toolbar could not be read safely."
        print("Automatic integration support: unsupported or unavailable. " + reason)
        # Existence is useful for recovery, but does not validate this copy.
        if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source):
            path = home / "layouts" / (source + "-jira-peek.json")
            print("Prepared integration layout: " + (source + "-jira-peek (exists; unverified)" if path.exists() or path.is_symlink() else "none"))
        print("Active integration configured: unverified")
        print("Next action: " + manual_integration_guidance(home, source))
    else:
        print("Automatic integration support: supported stock toolbar structure (native validation runs during repair)")
        print("Prepared integration layout: " + (plan.name + " (matching files)" if prepared else
              plan.name + " (partial or conflicting files; preserved)" if existing else "none"))
        configured = active == plan.name and prepared and not errors
        print("Active integration configured: " + ("yes (selected layout and files match)" if configured else
              "unavailable" if active is None else "unverified (Herdr reports errors)" if errors else "no"))
        if not bundle:
            action = ("Preserve the existing mods/jira-peek folder before reinstalling from a complete source checkout. "
                      "Do not overwrite local edits." if bundle_present else
                      "From a complete source checkout, run: " + shlex.join([sys.executable, "scripts/install-app.py", "--app-home", str(home), "--check"]))
        elif conflicts:
            action = "Preserve conflicting " + ", ".join(path.relative_to(home).as_posix() for path in conflicts) + ". " + manual_integration_guidance(home, source)
        elif errors:
            action = "Inspect herdr-app status using this app home and resolve its errors before selecting the integration."
        elif configured:
            action = "Verify the Jira Peek toggle in Herdr; hide the panel and reopen it with the button."
        elif prepared:
            action = selection_command(home, plan.name)
        else:
            action = repair_guidance(home, source, current_helper=True)
        print("Next action: " + action)
    print("Button rendering is unverified; status and files do not establish visible UI.")


def repair_integration(app_home, layout_name="main", check=True):
    destination = safe_path(safe_path(app_home) / "mods/jira-peek")
    current = managed_install(destination)
    with installation_lock(app_home):
        if managed_install(destination) != current:
            raise ValueError("Installation changed; try repair again")
        try:
            plan = attachment_plan(app_home, layout_name)
        except IntegrationError as error:
            raise IntegrationError(str(error) + " " + manual_integration_guidance(app_home, layout_name)) from None
        if check:
            check_attachment(plan)
        if managed_install(destination) != current:
            raise ValueError("Installation changed during validation; try repair again")
        attach(plan, app_home)


def install(app_home, config_dir=None, update=False, check=False, attach_layout=None):
    with installation_lock(app_home):
        plan = attachment_plan(app_home, attach_layout) if attach_layout else None
        # Older helpers call --update --check. Integration is optional on this
        # path; its validation must not prevent an independently valid bundle.
        automatic = update and not attach_layout
        if automatic:
            try:
                plan = attachment_plan(app_home, "main")
            except (ValueError, OSError) as error:
                reason = str(error) if isinstance(error, IntegrationError) else "Source layout or toolbar could not be read safely."
                print("Automatic toolbar preparation skipped. " + reason)
        if plan and check:
            if automatic:
                try:
                    check_attachment(plan)
                except (ValueError, OSError, subprocess.SubprocessError):
                    plan = None
                    print("Automatic toolbar validation failed; integration files were preserved. See docs/PANEL-INTEGRATION.md.")
            else:
                check_attachment(plan)
        destination = install_locked(app_home, config_dir, update, check)
        if plan:
            try:
                attach(plan, app_home)
            except (OSError, ValueError):
                print("Bundle installed successfully; toolbar integration is incomplete and may be partial. Existing personal files were preserved. Inspect before retrying.")
                print(repair_guidance(app_home, attach_layout or "main"))
            else:
                if automatic:
                    print("Inspect the layout currently in use: " + shlex.join([
                        sys.executable, str(destination / "runtime/update-app.py"), "--app-home",
                        str(destination.parents[1]), "--diagnose-integration"]))
        elif update:
            print(repair_guidance(app_home))
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
