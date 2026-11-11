#!/usr/bin/env python3
"""Private, transactional REST connection setup for the native app."""

import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
import tempfile
import urllib.parse

MAX_REQUEST = 16 * 1024
MAX_BODY = 64 * 1024
SETTINGS = ("JIRA_BACKEND", "JIRA_BASE", "JIRA_PROJECTS", "JIRA_NETRC_FILE", "JIRA_CLOUD_ID")
ERRORS = {"invalid_site", "invalid_email", "invalid_projects", "invalid_token", "invalid_cloud_id",
          "authentication_failed", "permission_denied", "rate_limited", "connection_failed",
          "config_changed", "unsafe_path", "dependencies_missing", "setup_failed"}


class Failure(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else "setup_failed"


def fail(code):
    raise Failure(code)


def revision(config):
    try:
        data = read_regular(config, 1024 * 1024)
    except FileNotFoundError:
        return "missing"
    return hashlib.sha256(data).hexdigest()


def check_component(path, directory=False, allow_missing=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None
        fail("unsafe_path")
    if stat.S_ISLNK(info.st_mode) or (directory and not stat.S_ISDIR(info.st_mode)) or (not directory and not stat.S_ISREG(info.st_mode)):
        fail("unsafe_path")
    if info.st_uid != os.getuid() or (not directory and info.st_nlink != 1):
        fail("unsafe_path")
    if directory and stat.S_IMODE(info.st_mode) != 0o700:
        fail("unsafe_path")
    if not directory and stat.S_IMODE(info.st_mode) & 0o077:
        fail("unsafe_path")
    return info


def read_regular(path, limit):
    try:
        path.lstat()
    except FileNotFoundError:
        raise
    info = check_component(path)
    if info.st_size > limit:
        fail("unsafe_path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev or opened.st_nlink != 1:
            fail("unsafe_path")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            fail("unsafe_path")
        return data
    finally:
        os.close(fd)


def check_tree(path):
    path = path.absolute()
    if not path.is_absolute() or path == Path("/") or ".." in path.parts:
        fail("unsafe_path")
    root_parts = path.parts if path.name == "connection" else path.parent.parts
    if root_parts[-3:] != ("data", "jira-peek", "connection") or any(ord(ch) < 32 for ch in str(path)) or "'" in str(path):
        fail("unsafe_path")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.exists() or current.is_symlink():
            try:
                info = current.lstat()
            except OSError:
                fail("unsafe_path")
            system_alias = str(current) in ("/private", "/var", "/tmp") and stat.S_ISLNK(info.st_mode)
            if (stat.S_ISLNK(info.st_mode) and not system_alias) or (current != path and not stat.S_ISDIR(info.st_mode) and not system_alias):
                fail("unsafe_path")
    for parent in (path, *path.parents):
        if (parent / ".git").exists() or (parent / ".git").is_symlink():
            fail("unsafe_path")


def ensure_dir(path):
    check_tree(path)
    connection_root = path if path.name == "connection" else path.parent
    if connection_root.exists() or connection_root.is_symlink():
        check_component(connection_root, directory=True)
    # Host data directories may already be 0755. They contain no credential
    # directly; require ownership and no other-user writes, keeping our leaf 0700.
    for managed_parent in (connection_root.parent, connection_root.parent.parent):
        if managed_parent.exists() or managed_parent.is_symlink():
            info = managed_parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
                fail("unsafe_path")
    missing = []
    current = path
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    for item in reversed(missing):
        item.mkdir(mode=0o700)
        check_component(item, directory=True)
    check_component(path, directory=True)


def config_path(root):
    return root / "config.sh"


def parse_config(data):
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        fail("unsafe_path")
    values, kept = {}, []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(?:'([^'\r\n]*)'|\"([^\"\r\n]*)\"|([^\s'\"]+))", stripped)
        if not match:
            fail("unsafe_path")
        key = match.group(1)
        # Keep retired imported assignments accepted as declarative data; the
        # runtime validates or ignores them without executing the file.
        if key not in SETTINGS and key not in {"JIRA_SITE", "CACHE_TTL_MIN", "MAX_CANDIDATES", "PICKER_LAYOUT", "AUTO_REFRESH_SEC", "KEY_RE", "SOURCE_HIGHLIGHT", "PICKER_FIELDS", "PREVIEW_FIELDS", "READER_FIELDS", "FIELD_LABELS", "TEXT_STYLE", "COLOR_THEME"}:
            fail("unsafe_path")
        value = next(v for v in match.groups()[1:] if v is not None)
        values[key] = value
        if key not in SETTINGS:
            kept.append(line)
    return values, kept


def load_config(root):
    path = config_path(root)
    try:
        return read_regular(path, 1024 * 1024)
    except FileNotFoundError:
        return None


def inspect(root):
    config = load_config(root)
    values, _ = parse_config(config or b"")
    return {"ok": True, "revision": "missing" if config is None else hashlib.sha256(config).hexdigest(),
            "configured": values.get("JIRA_BACKEND") == "rest" and bool(values.get("JIRA_NETRC_FILE")),
            "settings": {"base": values.get("JIRA_BASE", ""), "email": extract_email(config or b""),
                         "projects": values.get("JIRA_PROJECTS", ""), "cloudId": values.get("JIRA_CLOUD_ID", "")}}


def extract_email(data):
    for line in data.decode("utf-8", "ignore").splitlines():
        match = re.fullmatch(r"# JIRA_EMAIL=([^\s\r\n]+)", line)
        if match and valid_email(match.group(1)):
            return match.group(1)
    return ""


def valid_email(value):
    return isinstance(value, str) and value.isascii() and len(value) <= 254 and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value) is not None and ".." not in value


def validate(data):
    if not isinstance(data, dict):
        fail("setup_failed")
    base, email, token = data.get("base"), data.get("email"), data.get("token")
    projects, cloud = data.get("projects"), data.get("cloudId", "")
    if not isinstance(base, str):
        fail("invalid_site")
    if not base.isascii() or any(ord(ch) <= 32 or ord(ch) == 127 for ch in base):
        fail("invalid_site")
    if not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.atlassian\.net/?", base, re.IGNORECASE):
        fail("invalid_site")
    try:
        parsed = urllib.parse.urlsplit(base.rstrip("/"))
        hostname = parsed.hostname
    except ValueError:
        fail("invalid_site")
    base = f"https://{hostname.lower()}"
    if not valid_email(email):
        fail("invalid_email")
    if not isinstance(projects, str) or not projects.strip():
        fail("invalid_projects")
    keys = re.split(r"[|,\s]+", projects.strip())
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) for key in keys) or len(set(keys)) != len(keys):
        fail("invalid_projects")
    if not isinstance(cloud, str) or (cloud and not re.fullmatch(r"[A-Za-z0-9-]{1,128}", cloud)):
        fail("invalid_cloud_id")
    if not isinstance(token, str) or not token or len(token) > 4096 or not token.isascii() or any(ord(ch) < 33 or ord(ch) == 127 for ch in token) or any(ch in token for ch in '"\\'):
        fail("invalid_token")
    return {"base": base, "email": email, "token": token, "projects": "|".join(keys), "cloudId": cloud}


def make_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def prepare(root, expected):
    check_tree(root)
    ensure_dir(root)
    lock_fd = acquire_lock(root)
    try:
        config = config_path(root)
        current = revision(config)
        if current != expected:
            fail("config_changed")
        pending = root / ".setup-pending"
        ensure_dir(pending)
        cleanup_abandoned(root)
        ticket = secrets.token_hex(24)
        request_dir = pending / ticket
        request_dir.mkdir(mode=0o700)
        request = request_dir / "request.json"
        make_file(request, b"")
        make_file(request_dir / "revision", current.encode("ascii"))
        return {"ok": True, "ticket": ticket, "path": str(request)}
    finally:
        release_lock(lock_fd)


def safe_pending(root, ticket):
    if not re.fullmatch(r"[0-9a-f]{48}", ticket):
        fail("unsafe_path")
    pending = root / ".setup-pending"
    check_component(pending, directory=True)
    directory = pending / ticket
    check_component(directory, directory=True)
    request = directory / "request.json"
    request_info = check_component(request)
    if stat.S_IMODE(request_info.st_mode) != 0o600 or request_info.st_size > MAX_REQUEST:
        fail("unsafe_path")
    return directory, request


def remove_pending(directory):
    children = list(directory.iterdir())
    names = {child.name for child in children}
    if not {"request.json", "revision"}.issubset(names) or names - {"request.json", "revision", "response.json"}:
        fail("unsafe_path")
    limits = {"request.json": MAX_REQUEST, "revision": 128}
    for child in children:
        info = check_component(child)
        if stat.S_IMODE(info.st_mode) != 0o600 or (child.name in limits and info.st_size > limits[child.name]):
            fail("unsafe_path")
    for child in children:
        child.unlink()
    directory.rmdir()


def cleanup_abandoned(root):
    pending = root / ".setup-pending"
    try:
        check_component(pending, directory=True)
    except Failure:
        return
    cutoff = time.time() - 24 * 60 * 60
    for directory in pending.iterdir():
        if not re.fullmatch(r"[0-9a-f]{48}", directory.name):
            continue
        try:
            check_component(directory, directory=True)
            if directory.stat().st_mtime >= cutoff:
                continue
            remove_pending(directory)
        except (OSError, Failure):
            continue


def cleanup_managed_credentials(auth_dir, active):
    try:
        check_component(auth_dir, directory=True)
    except Failure:
        return
    for path in auth_dir.iterdir():
        if path == active or not re.fullmatch(r"\.auth-[0-9a-f]{48}\.netrc", path.name):
            continue
        try:
            info = check_component(path)
            if stat.S_IMODE(info.st_mode) != 0o600:
                continue
            contents = read_regular(path, 8192)
            credential_id = path.name[6:-6]
            marker = f"# herdr-jira-peek-managed:{credential_id}\n".encode("ascii")
            if not contents.startswith(marker) or not re.fullmatch(
                rb'# herdr-jira-peek-managed:[0-9a-f]{48}\nmachine (?:[a-z0-9.-]+) login "[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+" password "[^"\\\s]+"\n',
                contents,
            ):
                continue
            path.unlink()
        except (OSError, Failure):
            continue


def curl_json(netrc, url, body):
    curl = os.environ.get("CURL_BIN_PATH", "curl")
    from shutil import which
    if not which(curl):
        fail("dependencies_missing")
    try:
        auth = ["--netrc-file", str(netrc)] if netrc is not None else ["--no-netrc"]
        result = subprocess.run([curl, "-q", "-sS", "--connect-timeout", "5", "--max-time", "20", "--max-filesize", str(MAX_BODY), "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "0", *auth, "-H", "Accept: application/json", "-o", str(body), "-w", "%{http_code}", url], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=22, check=False)
    except subprocess.TimeoutExpired:
        fail("connection_failed")
    except OSError:
        fail("dependencies_missing")
    if result.returncode:
        fail("connection_failed")
    try:
        status = result.stdout.decode("ascii").strip()
    except UnicodeDecodeError:
        fail("connection_failed")
    if status == "401": fail("authentication_failed")
    if status == "403": fail("permission_denied")
    if status == "429": fail("rate_limited")
    if status != "200": fail("connection_failed")
    try:
        if body.stat().st_size > MAX_BODY:
            fail("connection_failed")
        obj = json.loads(read_regular(body, MAX_BODY))
    except (ValueError, OSError):
        fail("connection_failed")
    return obj


def curl_verify(netrc, url, body):
    obj = curl_json(netrc, url, body)
    if not isinstance(obj, dict) or not isinstance(obj.get("accountId"), str) or not obj["accountId"]:
        fail("connection_failed")


def verify_site(base, cloud, body):
    # Existing external configurations may use a custom HTTPS browse origin.
    # Resolve only this configured origin, without forwarding any credential.
    if not re.fullmatch(r"https://(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(?::[0-9]+)?", base):
        fail("invalid_site")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", cloud):
        fail("invalid_cloud_id")
    obj = curl_json(None, base + "/_edge/tenant_info", body)
    if not isinstance(obj, dict) or not isinstance(obj.get("cloudId"), str) or not obj["cloudId"]:
        fail("connection_failed")
    if obj["cloudId"] != cloud:
        fail("invalid_cloud_id")


def acquire_lock(root):
    path = root / ".setup-lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError:
        fail("unsafe_path")
    try:
        opened = os.fstat(fd)
        info = check_component(path)
        if stat.S_IMODE(opened.st_mode) != 0o600 or opened.st_size != 0 or opened.st_ino != info.st_ino or opened.st_dev != info.st_dev:
            fail("unsafe_path")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("config_changed")
        return fd
    except BaseException:
        os.close(fd)
        raise


def release_lock(fd):
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _save_locked(root, ticket):
    directory, request = safe_pending(root, ticket)
    active_config = config_path(root)
    try:
        expected_revision = read_regular(directory / "revision", 128).decode("ascii")
        data = read_regular(request, MAX_REQUEST)
    except (UnicodeDecodeError, OSError):
        fail("unsafe_path")
    if revision(active_config) != expected_revision:
        remove_pending(directory)
        fail("config_changed")
    start_revision = expected_revision
    try:
        setup = validate(json.loads(data.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("setup_failed")
    if start_revision != revision(active_config):
        fail("config_changed")
    generated = None
    scratch = []
    try:
        if revision(active_config) != start_revision:
            fail("config_changed")
        old = load_config(root)
        values, kept = parse_config(old or b"")
        auth_dir = root / ".credentials"
        ensure_dir(auth_dir)
        auth_name = ".auth-" + secrets.token_hex(24) + ".netrc"
        generated = auth_dir / auth_name
        host = "api.atlassian.com" if setup["cloudId"] else urllib.parse.urlsplit(setup["base"]).hostname
        credential_id = auth_name[6:-6]
        netrc = (f"# herdr-jira-peek-managed:{credential_id}\n"
                 f'machine {host} login "{setup["email"]}" password "{setup["token"]}"\n').encode("ascii")
        make_file(generated, netrc)
        body = directory / "response.json"
        scratch.append(body)
        make_file(body, b"")
        if setup["cloudId"]:
            verify_site(setup["base"], setup["cloudId"], body)
        origin = f'https://api.atlassian.com/ex/jira/{setup["cloudId"]}' if setup["cloudId"] else setup["base"]
        curl_verify(generated, origin + "/rest/api/3/myself", body)
        lines = [line for line in kept if not line.startswith("# JIRA_EMAIL=")]
        lines.extend([f"# JIRA_EMAIL={setup['email']}", "JIRA_BACKEND='rest'", f"JIRA_BASE='{setup['base']}'",
                      f"JIRA_PROJECTS='{setup['projects']}'", f"JIRA_NETRC_FILE='{generated}'", f"JIRA_CLOUD_ID='{setup['cloudId']}'"])
        replacement = ("\n".join(lines) + "\n").encode("utf-8")
        if revision(active_config) != start_revision:
            fail("config_changed")
        if active_config.exists():
            check_component(active_config)
        temp = root / (".config-" + secrets.token_hex(16))
        scratch.append(temp)
        make_file(temp, replacement)
        if revision(active_config) != start_revision:
            fail("config_changed")
        os.replace(temp, active_config)
        active_credential = generated
        generated = None
        try:
            cleanup_managed_credentials(auth_dir, active_credential)
        except Exception:
            pass
        return {"ok": True}
    finally:
        for path in scratch:
            try:
                if path.exists():
                    check_component(path)
                    path.unlink()
            except (OSError, Failure):
                pass
        if generated is not None:
            try:
                check_component(generated)
                generated.unlink()
            except (OSError, Failure):
                pass


def save(root, ticket):
    lock_fd = acquire_lock(root)
    directory = None
    try:
        directory, _ = safe_pending(root, ticket)
        return _save_locked(root, ticket)
    finally:
        if directory is not None:
            try:
                remove_pending(directory)
            except (OSError, Failure):
                pass
        release_lock(lock_fd)


def dispatch(argv):
    if len(argv) < 2:
        fail("setup_failed")
    if argv[0] == "verify-site" and len(argv) == 3:
        with tempfile.TemporaryDirectory(prefix="jira-peek-site-") as temporary:
            body = Path(temporary) / "response.json"
            make_file(body, b"")
            verify_site(argv[1], argv[2], body)
        return {"ok": True}
    command = argv[0]
    raw_root = Path(argv[1])
    if ".." in raw_root.parts:
        fail("unsafe_path")
    root = raw_root.absolute()
    check_tree(root)
    if command == "inspect" and len(argv) == 2:
        return inspect(root)
    if command == "prepare" and len(argv) == 3:
        return prepare(root, argv[2])
    if command == "save" and len(argv) == 3:
        return save(root, argv[2])
    if command == "cancel" and len(argv) == 3:
        if not re.fullmatch(r"[0-9a-f]{48}", argv[2]):
            fail("unsafe_path")
        lock_fd = acquire_lock(root)
        try:
            try:
                directory, _ = safe_pending(root, argv[2])
            except Failure as exc:
                if exc.code == "unsafe_path" and not (root / ".setup-pending" / argv[2]).exists():
                    return {"ok": True}
                raise
            remove_pending(directory)
            return {"ok": True}
        finally:
            release_lock(lock_fd)
    fail("setup_failed")


def main():
    try:
        result = dispatch(sys.argv[1:])
    except Failure as exc:
        result = {"ok": False, "error": exc.code}
    except Exception:
        result = {"ok": False, "error": "setup_failed"}
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
