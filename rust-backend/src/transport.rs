use crate::{
    config::{matches, Config},
    fail,
    storage::{hash, read},
    Result,
};
use serde_json::{json, Value};
use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::Duration,
};
pub fn twg_path() -> Result<PathBuf> {
    let name = std::env::var("TWG_BIN_PATH").unwrap_or("twg".into());
    let paths = if name.contains('/') {
        vec![PathBuf::from(name)]
    } else {
        std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default())
            .map(|p| p.join(&name))
            .collect()
    };
    paths
        .into_iter()
        .find(|p| fs::metadata(p).is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0))
        .ok_or(fail("dependencies_missing"))
}
fn twg(c: &Config, args: &[&str]) -> Result<(bool, Vec<u8>, Vec<u8>)> {
    let output = Command::new(twg_path()?)
        .args([
            "--mode",
            "user",
            "--site",
            c.get("JIRA_SITE"),
            "--output",
            "json",
        ])
        .args(args)
        .env_remove("HERDR_SOCKET_PATH")
        .env_remove("HERDR_PLUGIN_CONTEXT_JSON")
        .stdin(Stdio::null())
        .output()?;
    Ok((output.status.success(), output.stdout, output.stderr))
}
pub fn netrc(c: &Config) -> Result<Vec<u8>> {
    let p = Path::new(c.get("JIRA_NETRC_FILE"));
    let m = fs::symlink_metadata(p)?;
    if !p.is_absolute() || !m.is_file() || !matches!(m.permissions().mode() & 0o7777, 0o400 | 0o600)
    {
        return Err(fail("connection_failed"));
    }
    read(p)
}
pub fn fingerprint(c: &Config) -> Result<(String, String)> {
    let auth = if c.get("JIRA_BACKEND") == "rest" {
        hash(&netrc(c)?)
    } else {
        let (ok, b, _) = twg(c, &["whoami"])?;
        if !ok {
            return Err(fail("connection_failed"));
        }
        let v: Value = serde_json::from_slice(&b)?;
        let user = if !v["data"]["user"].is_null() {
            &v["data"]["user"]
        } else if !v["data"].is_null() {
            &v["data"]
        } else {
            &v
        };
        let id = user["accountId"]
            .as_str()
            .filter(|s| !s.is_empty())
            .ok_or(fail("connection_failed"))?;
        hash(id.as_bytes())
    };
    let target = c.get(if c.get("JIRA_BACKEND") == "rest" {
        "JIRA_CLOUD_ID"
    } else {
        "JIRA_SITE"
    });
    let id = hash(
        format!(
            "{}\n{}\n{target}\n{}\n{auth}\n",
            c.get("JIRA_BACKEND"),
            c.get("JIRA_BASE"),
            c.get("JIRA_PROJECTS")
        )
        .as_bytes(),
    );
    Ok((id, auth))
}
fn origin(c: &Config) -> String {
    if c.get("JIRA_CLOUD_ID").is_empty() {
        c.get("JIRA_BASE").into()
    } else {
        format!(
            "https://api.atlassian.com/ex/jira/{}",
            c.get("JIRA_CLOUD_ID")
        )
    }
}
// libcurl keeps netrc, proxy environment and TLS behavior aligned with the
// shell transport while executing entirely inside this process (no utilities).
fn http(c: &Config, url: String, payload: Option<Value>, auth: bool) -> Result<Value> {
    use curl::easy::{Easy, List, NetRc};
    use std::ffi::CString;
    let mut easy = Easy::new();
    #[allow(unused_mut)]
    let mut destination = url::Url::parse(&url).map_err(|_| fail("request_failed"))?;
    if destination.scheme() != "https" {
        return Err(fail("invalid_request"));
    }
    #[allow(unused_mut)]
    let mut protocols = curl_sys::CURLPROTO_HTTPS;
    #[cfg(feature = "fixture-http")]
    if let Ok(endpoint) = std::env::var("JIRA_PEEK_FIXTURE_HTTP") {
        let fixture = url::Url::parse(&endpoint).map_err(|_| fail("invalid_request"))?;
        if !matches!(fixture.scheme(), "http" | "https")
            || !matches!(fixture.host_str(), Some("127.0.0.1") | Some("[::1]"))
            || !fixture.username().is_empty()
            || fixture.password().is_some()
            || fixture.path() != "/"
            || fixture.query().is_some()
            || fixture.fragment().is_some()
        {
            return Err(fail("invalid_request"));
        }
        destination
            .set_scheme(fixture.scheme())
            .map_err(|_| fail("invalid_request"))?;
        let mut routes = List::new();
        routes.append(&format!(
            "{}:{}:{}:{}",
            destination.host_str().ok_or(fail("invalid_request"))?,
            destination
                .port_or_known_default()
                .ok_or(fail("invalid_request"))?,
            fixture.host_str().unwrap(),
            fixture
                .port_or_known_default()
                .ok_or(fail("invalid_request"))?
        ))?;
        easy.connect_to(routes)?;
        easy.noproxy("*")?;
        if let Some(path) = std::env::var_os("JIRA_PEEK_FIXTURE_CA") {
            easy.cainfo(Path::new(&path))?;
        }
        protocols |= curl_sys::CURLPROTO_HTTP;
    }
    easy.url(destination.as_str())?;
    easy.connect_timeout(Duration::from_secs(5))?;
    easy.timeout(Duration::from_secs(30))?;
    easy.follow_location(false)?;
    easy.max_redirections(0)?;
    // Mirror curl -q: do not parse .curlrc. The CLI's CA environment overrides
    // are explicit here because they are not libcurl options by themselves.
    if let Some(path) = std::env::var_os("CURL_CA_BUNDLE")
        .filter(|s| !s.is_empty())
        .or_else(|| std::env::var_os("SSL_CERT_FILE").filter(|s| !s.is_empty()))
    {
        easy.cainfo(Path::new(&path))?;
    }
    if let Some(path) = std::env::var_os("SSL_CERT_DIR").filter(|s| !s.is_empty()) {
        easy.capath(Path::new(&path))?;
    }
    unsafe {
        if curl_sys::curl_easy_setopt(
            easy.raw(),
            curl_sys::CURLOPT_PROTOCOLS,
            protocols as libc::c_long,
        ) != curl_sys::CURLE_OK
        {
            return Err(fail("request_failed"));
        }
    }
    let mut headers = List::new();
    headers.append("Accept: application/json")?;
    if let Some(body) = payload {
        headers.append("Content-Type: application/json")?;
        easy.post_fields_copy(&serde_json::to_vec(&body)?)?;
    }
    easy.http_headers(headers)?;
    let netrc_file;
    if auth {
        netrc(c)?; // permission, regular-file and no-symlink checks remain ours.
        netrc_file =
            CString::new(c.get("JIRA_NETRC_FILE")).map_err(|_| fail("connection_failed"))?;
        easy.netrc(NetRc::Required)?;
        unsafe {
            if curl_sys::curl_easy_setopt(
                easy.raw(),
                curl_sys::CURLOPT_NETRC_FILE,
                netrc_file.as_ptr(),
            ) != curl_sys::CURLE_OK
            {
                return Err(fail("connection_failed"));
            }
        }
    } else {
        easy.netrc(NetRc::Ignored)?;
    }
    let mut bytes = Vec::new();
    {
        let mut transfer = easy.transfer();
        transfer.write_function(|part| {
            if bytes.len().saturating_add(part.len()) > 64 * 1024 * 1024 {
                return Ok(0);
            }
            bytes.extend_from_slice(part);
            Ok(part.len())
        })?;
        transfer.perform()?;
    }
    match easy.response_code()? {
        200 => Ok(serde_json::from_slice(&bytes)?),
        401 => Err(fail("authentication_failed")),
        403 => Err(fail("permission_denied")),
        _ => Err(fail("request_failed")),
    }
}
pub fn verify_site(c: &Config) -> Result<()> {
    let v = http(
        c,
        format!("{}/_edge/tenant_info", c.get("JIRA_BASE")),
        None,
        false,
    )?;
    if v["cloudId"] != c.get("JIRA_CLOUD_ID") {
        return Err(fail("connection_failed"));
    }
    Ok(())
}
fn denied(v: &Value) -> bool {
    v.is_object()
        && ["status", "statusCode", "httpStatus", "code"]
            .iter()
            .any(|k| {
                v[k] == 403 || v[k] == "403" || v[k] == "FORBIDDEN" || v[k] == "PERMISSION_DENIED"
            })
}
fn permission(v: &Value) -> bool {
    if v["key"].is_string() || v["data"]["key"].is_string() {
        return false;
    }
    denied(v)
        || denied(&v["error"])
        || v["data"]["items"].as_array().is_some_and(|a| {
            a.len() == 1 && a[0]["ok"] == false && (denied(&a[0]) || denied(&a[0]["error"]))
        })
}
pub fn fetch(c: &Config, op: &str, keys: &[String]) -> Result<Value> {
    if c.get("JIRA_BACKEND") == "rest" {
        let url = origin(c);
        let v = match op {
            "metadata" => http(
                c,
                format!("{url}/rest/api/3/issue/bulkfetch"),
                Some(json!({"issueIdsOrKeys":keys,"fields":c.metadata()})),
                true,
            )?,
            "comments" => http(
                c,
                format!(
                    "{url}/rest/api/3/issue/{}/comment?startAt=0&maxResults=100&orderBy=-created",
                    keys[0]
                ),
                None,
                true,
            )?,
            _ => http(
                c,
                format!("{url}/rest/api/3/issue/{}?fields={}", keys[0], c.detail()),
                None,
                true,
            )?,
        };
        return match op {
            "metadata" => {
                if v["issues"].is_array() {
                    Ok(v)
                } else {
                    Err(fail("request_failed"))
                }
            }
            "comments" => {
                let a = v["comments"].as_array().ok_or(fail("request_failed"))?;
                let total = v["total"].as_f64().ok_or(fail("request_failed"))?;
                if v["startAt"] != 0
                    || a.len() > 100
                    || !a.iter().all(Value::is_object)
                    || total < a.len() as f64
                    || total.fract() != 0.
                    || (a.is_empty() && total != 0.)
                {
                    return Err(fail("request_failed"));
                }
                Ok(json!({"key":keys[0],"comments":{"total":v["total"],"comments":a}}))
            }
            _ => {
                if v["key"] != keys[0] || !v["fields"].is_object() {
                    return Err(fail("request_failed"));
                }
                let mut out = v["fields"].clone();
                out["key"] = v["key"].clone();
                out["fields"] = v["fields"].clone();
                out["comments"] = json!([]);
                out["_peek_comments_deferred"] = json!(c.comments());
                Ok(out)
            }
        };
    }
    let fields = if op == "metadata" {
        c.metadata().join(",")
    } else {
        c.detail()
    };
    let mut args = vec!["--api-version", "v2", "jira", "workitem", "get"];
    args.extend(keys.iter().map(String::as_str));
    args.extend(["--fields", &fields]);
    if op == "issue" && c.comments() {
        args.push("--comments")
    }
    let (ok, b, stderr) = twg(c, &args)?;
    let v: Value = serde_json::from_slice(&b).unwrap_or(Value::Null);
    if !ok {
        let msg = format!(
            "{} {}",
            String::from_utf8_lossy(&stderr),
            String::from_utf8_lossy(&b)
        );
        if matches(
            r"(?i)(twg[^\r\n]*(not\s+authenticated|authentication\s+(required|failed|not\s+configured)|credentials?\s+.*(missing|not\s+configured)|setup|login)|run[^a-z0-9]+twg\s+(setup|login)|auth\.conf|no\s+(default\s+)?site|configure\s+twg)",
            &msg,
        ) {
            return Err(fail("authentication_failed"));
        }
    }
    if op == "issue"
        && (permission(&v)
            || !ok
                && matches(
                    r"(^|[^A-Za-z0-9_])(HTTP([ /][0-9.]+)?[ :]+403|PERMISSION_DENIED|FORBIDDEN)([^A-Za-z0-9_]|$)",
                    &String::from_utf8_lossy(&stderr),
                ))
    {
        return Err(fail("permission_denied"));
    }
    if !ok || v.is_null() {
        return Err(fail("request_failed"));
    }
    Ok(v)
}
