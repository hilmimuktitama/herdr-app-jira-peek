mod config;
mod legacy;
mod projection;
mod storage;
mod transport;
use config::Config;
use serde_json::{json, Value};
use std::{
    fs,
    path::{Path, PathBuf},
};
use storage::*;
#[derive(Debug)]
pub struct Error(&'static str);
pub type Result<T> = std::result::Result<T, Error>;
pub fn fail(s: &'static str) -> Error {
    Error(s)
}
impl From<std::io::Error> for Error {
    fn from(_: std::io::Error) -> Self {
        fail("request_failed")
    }
}
impl From<curl::Error> for Error {
    fn from(_: curl::Error) -> Self {
        fail("request_failed")
    }
}
impl From<serde_json::Error> for Error {
    fn from(_: serde_json::Error) -> Self {
        fail("request_failed")
    }
}
struct Context {
    config: ConfigDirectory,
    state: PathBuf,
    digest: String,
    id: String,
    epoch: String,
    auth: String,
    c: Config,
}
impl Context {
    fn check(&self, identity: bool) -> Result<()> {
        if marker(&self.state)? != (self.id.clone(), self.epoch.clone())
            || hash(&self.config.read().map_err(|_| fail("connection_changed"))?) != self.digest
        {
            return Err(fail("connection_changed"));
        }
        if self.c.get("JIRA_BACKEND") == "rest"
            && hash(&transport::netrc(&self.c).map_err(|_| fail("connection_changed"))?)
                != self.auth
        {
            return Err(fail("connection_changed"));
        }
        if identity
            && transport::fingerprint(&self.c)
                .map_err(|_| fail("connection_changed"))?
                .0
                != self.id
        {
            return Err(fail("connection_changed"));
        }
        Ok(())
    }
    fn context(&self) -> String {
        format!("{}:{}", self.digest, self.epoch)
    }
    fn lock(&self) -> Result<Lock> {
        Lock::take(&self.state.join(".connection-lock"), true)
    }
    fn keylock(&self, k: &str) -> Result<Lock> {
        Lock::take(
            &self.state.join(format!("cache-generations/.{k}.lock")),
            false,
        )
    }
    fn generation(&self, k: &str) -> PathBuf {
        self.state.join("cache-generations").join(k)
    }
    fn cache(&self, k: &str) -> PathBuf {
        self.state.join("cache").join(format!("{k}.json"))
    }
    fn cached(&self, k: &str) -> Option<(Value, u64)> {
        let p = self.cache(k);
        let m = fs::symlink_metadata(&p).ok()?;
        if !m.is_file()
            || self.c.number("CACHE_TTL_MIN") == 0
            || m.modified().ok()?.elapsed().unwrap_or_default().as_secs()
                >= self.c.number("CACHE_TTL_MIN").saturating_mul(60)
        {
            return None;
        }
        let v: Value = serde_json::from_slice(&read(&p).ok()?).ok()?;
        if !v.is_object() || v["key"] != k || v["_peek_request"] != self.c.signature() {
            return None;
        }
        Some((v, mtime(&p).ok()?))
    }
    fn revoke(&self) -> Result<()> {
        let _lock = self.lock()?;
        self.check(false)?;
        if marker(&self.state)? == (self.id.clone(), self.epoch.clone()) {
            purge(&self.state.join("cache"), 0)?;
            epoch(&self.state, &self.id)?;
        }
        Ok(())
    }
    fn normalize(&self, v: Value, k: &str) -> Result<Value> {
        if !v.is_object() {
            return Err(fail("request_failed"));
        }
        let issue = if let Some(a) = v["data"].as_array() {
            if a.len() != 1 {
                return Err(fail("request_failed"));
            }
            a[0].clone()
        } else if v["data"].is_object() {
            v["data"].clone()
        } else {
            v
        };
        if !issue.is_object() || issue["key"] != k {
            return Err(fail("request_failed"));
        }
        let mut out = issue["fields"].as_object().cloned().unwrap_or_default();
        out.extend(issue.as_object().unwrap().clone());
        out.insert("_peek_request".into(), json!(self.c.signature()));
        Ok(Value::Object(out))
    }
    fn issue(&self, k: &str, refresh: bool) -> Result<Value> {
        if refresh {
            let _key = self.keylock(k)?;
            increment(&self.generation(k))?;
            remove(&self.cache(k))?;
        }
        {
            let _lock = self.lock()?;
            self.check(false)?;
            if let Some((v, t)) = self.cached(k) {
                remove(&self.state.join(format!("fetch-errors/fetch-error-{k}")))?;
                return self.project(v, t);
            }
        }
        let attempt = {
            let _key = self.keylock(k)?;
            increment(&self.generation(k))?
        };
        let result =
            transport::fetch(&self.c, "issue", &[k.into()]).and_then(|v| self.normalize(v, k));
        if matches!(&result, Err(Error("authentication_failed"))) {
            self.check(false)?;
            self.revoke()?;
            return Err(fail("connection_changed"));
        }
        self.check(true)?;
        let _key = self.keylock(k)?;
        let _lock = self.lock()?;
        self.check(false)?;
        if generation(&self.generation(k))? != attempt {
            return Err(fail("request_failed"));
        }
        match result {
            Ok(v) => {
                let time = if self.c.number("CACHE_TTL_MIN") > 0 {
                    atomic(&self.cache(k), &serde_json::to_vec(&v)?)?;
                    mtime(&self.cache(k))?
                } else {
                    now()
                };
                remove(&self.state.join(format!("fetch-errors/fetch-error-{k}")))?;
                self.project(v, time)
            }
            Err(e) => {
                if e.0 == "permission_denied" {
                    increment(&self.generation(k))?;
                    remove(&self.cache(k))?;
                }
                let message = if e.0 == "permission_denied" {
                    "Access to this Jira operation was denied (HTTP 403)"
                } else if self.c.get("JIRA_BACKEND") == "rest" {
                    "Jira request failed"
                } else {
                    "TWG request failed"
                };
                atomic(
                    &self.state.join(format!("fetch-errors/fetch-error-{k}")),
                    format!("{message}\n").as_bytes(),
                )?;
                Err(e)
            }
        }
    }
    fn project(&self, v: Value, time: u64) -> Result<Value> {
        let mut issue = projection::issue(&v, &self.c);
        issue["fetchedAt"] = json!(time);
        self.check(false)?;
        Ok(json!({"ok":true,"context":self.context(),"issue":issue}))
    }
}
fn bridge(a: &[String]) -> Result<Value> {
    if a.len() < 3
        || !matches!(
            a[0].as_str(),
            "config" | "stamp" | "clear" | "issue" | "metadata" | "comments"
        )
    {
        return Err(fail("invalid_request"));
    }
    let op = &a[0];
    let config_dir = Path::new(&a[1]);
    let root = Path::new(&a[2]);
    if !config_dir.is_absolute()
        || !root.is_absolute()
        || config_dir == Path::new("/")
        || root == Path::new("/")
        || symlink(config_dir)
        || symlink(root)
    {
        return Err(fail("invalid_request"));
    }
    let config = config_dir.join("config.sh");
    if symlink(&config) || !config.is_file() {
        return Err(fail("configuration_missing"));
    }
    let config = ConfigDirectory::open(config_dir)?;
    let state = root.join("connections").join(hash(
        format!("directory-v1:{}:{}", config.device, config.inode).as_bytes(),
    ));
    if symlink(&root.join("connections")) || symlink(&state) {
        return Err(fail("invalid_request"));
    }
    let digest = hash(&config.read()?);
    if op == "stamp" {
        return Ok(json!({"ok":true,"context":format!("{}:{}",digest,marker(&state)?.1)}));
    }
    if op == "clear" {
        if a.len() != 4 || a[3].is_empty() {
            return Err(fail("invalid_request"));
        }
        let cache = state.join("cache");
        if !state.is_dir() || symlink(&cache) || cache.exists() && !cache.is_dir() {
            return Err(fail("request_failed"));
        }
        let _lock = Lock::take(&state.join(".connection-lock"), true)?;
        let (id, ep) = marker(&state)?;
        let digest = hash(&config.read()?);
        if id.is_empty() || ep.is_empty() || a[3] != format!("{digest}:{ep}") {
            return Err(fail("connection_changed"));
        }
        epoch(&state, &id)?;
        purge(&cache, 0)?;
        if hash(&config.read()?) != digest {
            return Err(fail("connection_changed"));
        }
        return Ok(json!({"ok":true}));
    }
    let mut c = Config::load(&config.read()?)?;
    if c.get("JIRA_BACKEND") == "twg" {
        transport::twg_path()?;
    } else {
        transport::netrc(&c).map_err(|_| fail("connection_failed"))?;
    }
    for p in [
        root.to_path_buf(),
        root.join("connections"),
        state.clone(),
        state.join("cache"),
        state.join("cache-generations"),
        state.join("fetch-errors"),
    ] {
        private(&p)?;
    }
    legacy::initialize(&state)?;
    let (id, auth, ep) = {
        let _lock = Lock::take(&state.join(".connection-lock"), true)?;
        let (id, auth) = transport::fingerprint(&c).map_err(|_| fail("connection_failed"))?;
        if hash(&config.read()?) != digest {
            return Err(fail("connection_changed"));
        }
        let (saved, ep) = marker(&state)?;
        let ep = if saved == id && !ep.is_empty() {
            ep
        } else {
            purge(&state.join("cache"), 0)?;
            let next = epoch(&state, &id)?;
            if !saved.is_empty() {
                legacy::retire_keys(&state)?;
            }
            next
        };
        purge(&state.join("cache"), c.number("CACHE_TTL_MIN"))?;
        if c.get("JIRA_BACKEND") == "rest" && !c.get("JIRA_CLOUD_ID").is_empty() {
            let file = state.join("site-context");
            if symlink(&file) {
                return Err(fail("connection_failed"));
            }
            let expected = format!("{id}:{ep}\n");
            if read(&file).ok().as_deref() != Some(expected.as_bytes()) {
                transport::verify_site(&c).map_err(|_| fail("connection_failed"))?;
                if hash(&config.read()?) != digest || hash(&transport::netrc(&c)?) != auth {
                    return Err(fail("connection_changed"));
                }
                atomic(&file, expected.as_bytes())?;
            }
        }
        (id, auth, ep)
    };
    if (op == "issue" && a.len() == 7) || (op == "comments" && a.len() == 6) {
        let value = a.last().unwrap();
        if value.len() > 2048 || !config::fields(value, false) {
            return Err(fail("invalid_request"));
        }
        c.v.insert("READER_FIELDS".into(), value.clone());
    }
    let ctx = Context {
        config,
        state,
        digest,
        id,
        epoch: ep,
        auth,
        c,
    };
    if op == "config" {
        return Ok(
            json!({"ok":true,"context":ctx.context(),"base":ctx.c.get("JIRA_BASE"),"projects":ctx.c.get("JIRA_PROJECTS").split('|').collect::<Vec<_>>(),"backend":ctx.c.get("JIRA_BACKEND"),"interval":ctx.c.number("AUTO_REFRESH_SEC"),"limit":ctx.c.number("MAX_CANDIDATES"),"ttl":ctx.c.number("CACHE_TTL_MIN"),"fields":config::csv(&format!("summary,{}",ctx.c.get("READER_FIELDS"))).iter().filter(|id|id.as_str()!="link").map(|id|json!({"id":id,"label":projection::label(id,ctx.c.get("FIELD_LABELS"))})).collect::<Vec<_>>()}),
        );
    }
    if a.get(3) != Some(&ctx.context()) {
        return Err(fail("connection_changed"));
    }
    let args = &a[4..];
    if op == "issue" {
        if args.is_empty()
            || args.len() > 3
            || !ctx.c.key(&args[0])
            || args.get(1).is_some_and(|s| !s.is_empty() && s != "refresh")
        {
            return Err(fail("invalid_request"));
        }
        return ctx.issue(&args[0], args.get(1).is_some_and(|s| s == "refresh"));
    }
    if op == "comments" {
        if !(1..=2).contains(&args.len())
            || ctx.c.get("JIRA_BACKEND") != "rest"
            || !ctx.c.comments()
            || !ctx.c.key(&args[0])
        {
            return Err(fail("invalid_request"));
        }
    } else if args.is_empty()
        || args.len() > ctx.c.number("MAX_CANDIDATES") as usize
        || !args.iter().all(|k| ctx.c.key(k))
    {
        return Err(fail("invalid_request"));
    }
    let result = transport::fetch(&ctx.c, op, if op == "comments" { &args[..1] } else { args });
    if matches!(&result, Err(Error("authentication_failed"))) {
        ctx.check(false)?;
        ctx.revoke()?;
        return Err(fail("connection_changed"));
    }
    ctx.check(true)?;
    let v = result?;
    let value = if op == "comments" {
        let mut c = ctx.c.clone();
        c.v.insert("READER_FIELDS".into(), "comments".into());
        let p = projection::issue(&v, &c);
        let comments = json!({"key":p["key"],"comments":p["comments"],"commentsTotal":p["commentsTotal"],"truncated":p["truncated"],"unsupportedContent":p["unsupportedContent"]});
        ctx.check(false)?;
        return Ok(json!({"ok":true,"context":ctx.context(),"comments":comments}));
    } else {
        let docs: Vec<&Value> = if ctx.c.get("JIRA_BACKEND") == "rest" {
            v["issues"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .filter(|x| x.is_object() && x["fields"].is_object())
                        .collect()
                })
                .unwrap_or_default()
        } else if let Some(a) = v.as_array() {
            a.iter().collect()
        } else if let Some(a) = v["data"].as_array() {
            a.iter().collect()
        } else if let Some(a) = v["data"]["items"].as_array() {
            a.iter()
                .filter(|x| x["ok"] == true && x["data"].is_object())
                .map(|x| &x["data"])
                .collect()
        } else if v["data"].is_object() {
            vec![&v["data"]]
        } else {
            vec![&v]
        };
        let rows: Vec<_> = args
            .iter()
            .filter_map(|k| {
                docs.iter()
                    .find(|v| v["key"] == *k)
                    .map(|v| projection::row(v, ctx.c.get("PICKER_FIELDS")))
            })
            .collect();
        json!({"ok":true,"context":ctx.context(),"rows":rows})
    };
    ctx.check(false)?;
    Ok(value)
}
fn main() {
    unsafe {
        libc::umask(0o077);
    };
    let a: Vec<String> = std::env::args().skip(1).collect();
    if a == ["--build-info"] {
        let curl = curl::Version::get();
        println!(
            "{}",
            json!({"protocol":1,"version":env!("CARGO_PKG_VERSION"),
            "fixtureTransport":cfg!(feature="fixture-http"),"os":std::env::consts::OS,
            "arch":std::env::consts::ARCH,"transport":"libcurl","libcurl":curl.version(),"tls":curl.ssl_version()})
        );
        return;
    }
    let output = bridge(&a)
        .and_then(|v| {
            let b = serde_json::to_vec(&v)?;
            if b.len() > 7340032 {
                return Err(fail("request_failed"));
            }
            Ok(v)
        })
        .unwrap_or_else(|e| json!({"ok":false,"error":e.0}));
    println!("{output}");
}
