//! Private setup protocol. Credentials travel only through private ticket files.
use crate::{config::matches, fail, storage::hash, Result};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::{
        fd::AsRawFd,
        unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt},
    },
    path::{Path, PathBuf},
};
const REQUEST: usize = 16384;
fn bad() -> crate::Error {
    fail("unsafe_path")
}
fn check(p: &Path, dir: bool) -> Result<fs::Metadata> {
    let m = fs::symlink_metadata(p).map_err(|_| bad())?;
    if m.uid() != unsafe { libc::getuid() }
        || (if dir {
            !m.is_dir() || m.mode() & 0o7777 != 0o700
        } else {
            !m.is_file() || m.nlink() != 1 || m.mode() & 0o077 != 0
        })
    {
        return Err(bad());
    }
    Ok(m)
}
fn read(p: &Path, limit: usize) -> Result<Vec<u8>> {
    let m = check(p, false)?;
    let f = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW)
        .open(p)
        .map_err(|_| bad())?;
    let n = f.metadata()?;
    if m.ino() != n.ino() || m.dev() != n.dev() || n.nlink() != 1 || n.len() > limit as u64 {
        return Err(bad());
    }
    let mut b = Vec::new();
    f.take(limit as u64 + 1).read_to_end(&mut b)?;
    if b.len() > limit {
        return Err(bad());
    }
    Ok(b)
}
fn tree(p: &Path) -> Result<()> {
    let s = p.to_str().ok_or_else(bad)?;
    let root = if p.file_name().is_some_and(|n| n == "connection") {
        p
    } else {
        p.parent().ok_or_else(bad)?
    };
    if !p.is_absolute()
        || !root.ends_with("data/jira-peek/connection")
        || s.split('/').any(|s| s == "..")
        || s.contains('\'')
        || s.chars().any(|c| c < ' ')
    {
        return Err(bad());
    }
    for a in p.ancestors() {
        if fs::symlink_metadata(a.join(".git")).is_ok() {
            return Err(bad());
        }
        if let Ok(m) = fs::symlink_metadata(a) {
            let alias = ["/tmp", "/var", "/private"].contains(&a.to_str().unwrap_or(""))
                && m.file_type().is_symlink();
            if !alias && (m.file_type().is_symlink() || a != p && !m.is_dir()) {
                return Err(bad());
            }
        }
    }
    Ok(())
}
fn directory(p: &Path) -> Result<()> {
    tree(p)?;
    let root = if p.file_name().is_some_and(|n| n == "connection") {
        p
    } else {
        p.parent().ok_or_else(bad)?
    };
    if fs::symlink_metadata(root).is_ok() {
        check(root, true)?;
    }
    for a in root.ancestors().skip(1).take(2) {
        if let Ok(m) = fs::symlink_metadata(a) {
            if !m.is_dir() || m.uid() != unsafe { libc::getuid() } || m.mode() & 0o022 != 0 {
                return Err(bad());
            }
        }
    }
    let mut missing = Vec::new();
    let mut cur = p;
    while fs::symlink_metadata(cur).is_err() {
        missing.push(cur);
        cur = cur.parent().ok_or_else(bad)?;
    }
    for a in missing.into_iter().rev() {
        fs::DirBuilder::new().mode(0o700).create(a)?;
        check(a, true)?;
    }
    check(p, true)?;
    Ok(())
}
fn make(p: &Path, b: &[u8]) -> Result<()> {
    let mut f = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(p)?;
    f.write_all(b)?;
    f.sync_all()?;
    Ok(())
}
fn random() -> Result<String> {
    let mut b = [0; 24];
    File::open("/dev/urandom")?.read_exact(&mut b)?;
    Ok(b.iter().map(|x| format!("{x:02x}")).collect())
}
fn config(root: &Path) -> Result<Option<Vec<u8>>> {
    let p = root.join("config.sh");
    match fs::symlink_metadata(&p) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        _ => read(&p, 1048576).map(Some),
    }
}
fn revision(root: &Path) -> Result<String> {
    Ok(config(root)?.map(|b| hash(&b)).unwrap_or("missing".into()))
}
const SETTINGS: [&str; 5] = [
    "JIRA_BACKEND",
    "JIRA_BASE",
    "JIRA_PROJECTS",
    "JIRA_NETRC_FILE",
    "JIRA_CLOUD_ID",
];
fn parse(b: &[u8]) -> Result<(HashMap<String, String>, Vec<String>)> {
    let text = std::str::from_utf8(b).map_err(|_| bad())?;
    let mut values = HashMap::new();
    let mut kept = Vec::new();
    let re = regex::Regex::new(r#"^([A-Z][A-Z0-9_]*)=(?:'([^'\r\n]*)'|"([^"\r\n]*)"|([^\s'"]+))$"#)
        .unwrap();
    for line in text.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            kept.push(line.into());
            continue;
        }
        let c = re.captures(t).ok_or_else(bad)?;
        let k = &c[1];
        if !SETTINGS.contains(&k)
            && ![
                "JIRA_SITE",
                "CACHE_TTL_MIN",
                "MAX_CANDIDATES",
                "PICKER_LAYOUT",
                "AUTO_REFRESH_SEC",
                "KEY_RE",
                "SOURCE_HIGHLIGHT",
                "PICKER_FIELDS",
                "PREVIEW_FIELDS",
                "READER_FIELDS",
                "FIELD_LABELS",
                "TEXT_STYLE",
                "COLOR_THEME",
            ]
            .contains(&k)
        {
            return Err(bad());
        }
        values.insert(
            k.into(),
            (2..=4).find_map(|i| c.get(i)).unwrap().as_str().into(),
        );
        if !SETTINGS.contains(&k) {
            kept.push(line.into());
        }
    }
    Ok((values, kept))
}
fn email(s: &str) -> bool {
    s.is_ascii()
        && s.len() <= 254
        && !s.contains("..")
        && matches(
            r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$",
            s,
        )
}
fn validate(v: Value) -> Result<Value> {
    if !v.is_object() {
        return Err(fail("setup_failed"));
    }
    let get = |k: &str, e| v[k].as_str().ok_or_else(|| fail(e));
    let base = get("base", "invalid_site")?;
    if !base.is_ascii()
        || !matches(
            r"(?i)^https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.atlassian\.net/?$",
            base,
        )
    {
        return Err(fail("invalid_site"));
    }
    let mail = get("email", "invalid_email")?;
    if !email(mail) {
        return Err(fail("invalid_email"));
    }
    let projects = get("projects", "invalid_projects")?;
    let re = regex::Regex::new(r"[|,\s]+").unwrap();
    let keys: Vec<_> = re.split(projects.trim()).collect();
    let mut seen = std::collections::HashSet::new();
    if keys
        .iter()
        .any(|k| !matches(r"^[A-Z][A-Z0-9_]*$", k) || !seen.insert(*k))
    {
        return Err(fail("invalid_projects"));
    }
    let cloud = if v.get("cloudId").is_none() {
        ""
    } else {
        get("cloudId", "invalid_cloud_id")?
    };
    if !cloud.is_empty() && !matches(r"^[A-Za-z0-9-]{1,128}$", cloud) {
        return Err(fail("invalid_cloud_id"));
    }
    let token = get("token", "invalid_token")?;
    if token.is_empty()
        || token.len() > 4096
        || !token
            .bytes()
            .all(|b| (33..127).contains(&b) && b != b'"' && b != b'\\')
    {
        return Err(fail("invalid_token"));
    }
    Ok(
        json!({"base":base.trim_end_matches('/').to_ascii_lowercase(),"email":mail,"projects":keys.join("|"),"cloudId":cloud,"token":token}),
    )
}
fn lock(root: &Path) -> Result<File> {
    let p = root.join(".setup-lock");
    let f = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(&p)
        .map_err(|_| bad())?;
    let m = check(&p, false)?;
    let n = f.metadata()?;
    if m.ino() != n.ino() || m.dev() != n.dev() || n.len() != 0 || n.mode() & 0o7777 != 0o600 {
        return Err(bad());
    }
    if unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
        return Err(fail("config_changed"));
    }
    Ok(f)
}
fn pending(root: &Path, t: &str) -> Result<PathBuf> {
    if !matches(r"^[0-9a-f]{48}$", t) {
        return Err(bad());
    }
    let p = root.join(".setup-pending");
    check(&p, true)?;
    let d = p.join(t);
    check(&d, true)?;
    let m = check(&d.join("request.json"), false)?;
    if m.mode() & 0o7777 != 0o600 || m.len() > REQUEST as u64 {
        return Err(bad());
    }
    Ok(d)
}
fn remove(d: &Path) -> Result<()> {
    check(d, true)?;
    let entries = fs::read_dir(d)?.collect::<std::io::Result<Vec<_>>>()?;
    let mut names = Vec::new();
    for e in &entries {
        let n = e.file_name().into_string().map_err(|_| bad())?;
        let limit = match n.as_str() {
            "request.json" => REQUEST,
            "revision" => 128,
            "response.json" => usize::MAX,
            _ => return Err(bad()),
        };
        let m = check(&e.path(), false)?;
        if m.mode() & 0o7777 != 0o600 || m.len() > limit as u64 {
            return Err(bad());
        }
        names.push(n);
    }
    if !names.iter().any(|n| n == "request.json") || !names.iter().any(|n| n == "revision") {
        return Err(bad());
    }
    for e in entries {
        fs::remove_file(e.path())?;
    }
    fs::remove_dir(d)?;
    Ok(())
}
mod http;
fn request(auth: Option<&Path>, url: String) -> Result<Value> {
    http::http(auth, url).map_err(|e| match e.0 {
        "authentication_failed" | "permission_denied" | "rate_limited" => e,
        _ => fail("connection_failed"),
    })
}
fn verify(base: &str, cloud: &str) -> Result<()> {
    if !matches(
        r"^https://(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(?::[0-9]+)?$",
        base,
    ) {
        return Err(fail("invalid_site"));
    }
    if !matches(r"^[A-Za-z0-9_-]{1,128}$", cloud) {
        return Err(fail("invalid_cloud_id"));
    }
    let v = request(None, format!("{base}/_edge/tenant_info"))?;
    let c = v["cloudId"]
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| fail("connection_failed"))?;
    if c != cloud {
        return Err(fail("invalid_cloud_id"));
    }
    Ok(())
}
fn cleanup_auth(dir: &Path, active: &Path) {
    if check(dir, true).is_err() {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        let name = entry.file_name();
        let Some(n) = name.to_str() else {
            continue;
        };
        if p == active || !matches(r"^\.auth-[0-9a-f]{48}\.netrc$", n) {
            continue;
        }
        let Ok(m) = check(&p, false) else {
            continue;
        };
        if m.mode() & 0o7777 != 0o600 {
            continue;
        }
        let Ok(b) = read(&p, 8192) else {
            continue;
        };
        let Ok(s) = std::str::from_utf8(&b) else {
            continue;
        };
        if s.starts_with(&format!("# herdr-jira-peek-managed:{}\n", &n[6..54]))
            && matches(
                r##"^# herdr-jira-peek-managed:[0-9a-f]{48}\nmachine [a-z0-9.-]+ login "[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+" password "[^"\\\s]+"\n$"##,
                s,
            )
        {
            let _ = fs::remove_file(p);
        }
    }
}
fn save(root: &Path, d: &Path) -> Result<Value> {
    let expected = String::from_utf8(read(&d.join("revision"), 128)?).map_err(|_| bad())?;
    if revision(root)? != expected {
        return Err(fail("config_changed"));
    }
    let v = validate(
        serde_json::from_slice(&read(&d.join("request.json"), REQUEST)?)
            .map_err(|_| fail("setup_failed"))?,
    )?;
    let (_, kept) = parse(&config(root)?.unwrap_or_default())?;
    let authdir = root.join(".credentials");
    directory(&authdir)?;
    let id = random()?;
    let auth = authdir.join(format!(".auth-{id}.netrc"));
    let base = v["base"].as_str().unwrap();
    let cloud = v["cloudId"].as_str().unwrap();
    let mail = v["email"].as_str().unwrap();
    let token = v["token"].as_str().unwrap();
    let host = if cloud.is_empty() {
        base.strip_prefix("https://").unwrap()
    } else {
        "api.atlassian.com"
    };
    let temp = root.join(format!(".config-{}", random()?));
    let mut activated = false;
    let result = (|| {
        make(&auth,format!("# herdr-jira-peek-managed:{id}\nmachine {host} login \"{mail}\" password \"{token}\"\n").as_bytes())?;
        if !cloud.is_empty() {
            verify(base, cloud)?;
        }
        let origin = if cloud.is_empty() {
            base.to_string()
        } else {
            format!("https://api.atlassian.com/ex/jira/{cloud}")
        };
        let account = request(Some(&auth), format!("{origin}/rest/api/3/myself"))?;
        if account["accountId"].as_str().is_none_or(|s| s.is_empty()) {
            return Err(fail("connection_failed"));
        }
        let mut lines: Vec<_> = kept
            .into_iter()
            .filter(|s| !s.starts_with("# JIRA_EMAIL="))
            .collect();
        lines.extend([
            format!("# JIRA_EMAIL={mail}"),
            "JIRA_BACKEND='rest'".into(),
            format!("JIRA_BASE='{base}'"),
            format!("JIRA_PROJECTS='{}'", v["projects"].as_str().unwrap()),
            format!("JIRA_NETRC_FILE='{}'", auth.display()),
            format!("JIRA_CLOUD_ID='{cloud}'"),
        ]);
        if revision(root)? != expected {
            return Err(fail("config_changed"));
        }
        make(&temp, (lines.join("\n") + "\n").as_bytes())?;
        File::open(&authdir)?.sync_all()?;
        if revision(root)? != expected {
            return Err(fail("config_changed"));
        }
        let root_dir = File::open(root)?;
        fs::rename(&temp, root.join("config.sh"))?;
        activated = true;
        // Activation is the commit point. A postcommit durability/cleanup error
        // must not report that the previous connection is still active.
        let _ = root_dir.sync_all();
        cleanup_auth(&authdir, &auth);
        Ok(json!({"ok":true}))
    })();
    let _ = fs::remove_file(temp);
    if !activated {
        let _ = fs::remove_file(auth);
    }
    result
}
fn dispatch(a: &[String]) -> Result<Value> {
    if a.len() == 3 && a[0] == "verify-site" {
        verify(&a[1], &a[2])?;
        return Ok(json!({"ok":true}));
    }
    if a.len() < 2 {
        return Err(fail("setup_failed"));
    }
    let raw = Path::new(&a[1]);
    let root = if raw.is_absolute() {
        raw.to_path_buf()
    } else {
        std::env::current_dir()?.join(raw)
    };
    tree(&root)?;
    match (a[0].as_str(), a.len()) {
        ("inspect", 2) => {
            let b = config(&root)?;
            let (v, _) = parse(b.as_deref().unwrap_or_default())?;
            let get = |k| v.get(k).cloned().unwrap_or_default();
            let mail = String::from_utf8_lossy(b.as_deref().unwrap_or_default())
                .lines()
                .filter_map(|s| s.strip_prefix("# JIRA_EMAIL="))
                .find(|s| email(s))
                .unwrap_or("")
                .to_string();
            Ok(
                json!({"ok":true,"revision":b.map(|b|hash(&b)).unwrap_or("missing".into()),"configured":get("JIRA_BACKEND")=="rest"&&!get("JIRA_NETRC_FILE").is_empty(),"settings":{"base":get("JIRA_BASE"),"email":mail,"projects":get("JIRA_PROJECTS"),"cloudId":get("JIRA_CLOUD_ID")}}),
            )
        }
        ("prepare", 3) => {
            directory(&root)?;
            let _lock = lock(&root)?;
            let rev = revision(&root)?;
            if rev != a[2] {
                return Err(fail("config_changed"));
            }
            let p = root.join(".setup-pending");
            directory(&p)?;
            for e in fs::read_dir(&p)?.flatten() {
                if matches(r"^[0-9a-f]{48}$", &e.file_name().to_string_lossy())
                    && check(&e.path(), true)
                        .ok()
                        .and_then(|m| m.modified().ok())
                        .and_then(|t| t.elapsed().ok())
                        .is_some_and(|t| t.as_secs() > 86400)
                {
                    let _ = remove(&e.path());
                }
            }
            let t = random()?;
            let d = p.join(&t);
            fs::DirBuilder::new().mode(0o700).create(&d)?;
            make(&d.join("request.json"), b"")?;
            make(&d.join("revision"), rev.as_bytes())?;
            Ok(json!({"ok":true,"ticket":t,"path":d.join("request.json")}))
        }
        ("save", 3) => {
            let _lock = lock(&root)?;
            let d = pending(&root, &a[2])?;
            let result = save(&root, &d);
            let _ = remove(&d);
            result
        }
        ("cancel", 3) => {
            if !matches(r"^[0-9a-f]{48}$", &a[2]) {
                return Err(bad());
            }
            let _lock = lock(&root)?;
            match pending(&root, &a[2]) {
                Ok(d) => remove(&d)?,
                Err(e) => {
                    if fs::symlink_metadata(root.join(".setup-pending").join(&a[2])).is_ok() {
                        return Err(e);
                    }
                }
            }
            Ok(json!({"ok":true}))
        }
        _ => Err(fail("setup_failed")),
    }
}
pub fn run(a: &[String]) -> Value {
    dispatch(a).unwrap_or_else(
        |e| json!({"ok":false,"error":if e.0=="request_failed"{"setup_failed"}else{e.0}}),
    )
}
