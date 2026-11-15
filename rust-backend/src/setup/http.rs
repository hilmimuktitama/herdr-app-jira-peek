use crate::{fail, Result};
use serde_json::Value;
use std::{path::Path, time::Duration};
pub(super) fn http(netrc: Option<&Path>, url: String) -> Result<Value> {
    use curl::easy::{Easy, List, NetRc};
    use std::ffi::CString;
    let mut easy = Easy::new();
    #[allow(unused_mut)]
    let mut destination = url::Url::parse(&url).map_err(|_| fail("connection_failed"))?;
    if destination.scheme() != "https" {
        return Err(fail("connection_failed"));
    }
    #[allow(unused_mut)]
    let mut protocols = curl_sys::CURLPROTO_HTTPS;
    #[cfg(feature = "fixture-http")]
    if let Ok(endpoint) = std::env::var("JIRA_PEEK_FIXTURE_HTTP") {
        let fixture = url::Url::parse(&endpoint).map_err(|_| fail("connection_failed"))?;
        if !matches!(fixture.scheme(), "http" | "https")
            || !matches!(fixture.host_str(), Some("127.0.0.1") | Some("[::1]"))
            || !fixture.username().is_empty()
            || fixture.password().is_some()
            || fixture.path() != "/"
            || fixture.query().is_some()
            || fixture.fragment().is_some()
        {
            return Err(fail("connection_failed"));
        }
        destination
            .set_scheme(fixture.scheme())
            .map_err(|_| fail("connection_failed"))?;
        let mut routes = List::new();
        routes.append(&format!(
            "{}:{}:{}:{}",
            destination.host_str().ok_or(fail("connection_failed"))?,
            destination
                .port_or_known_default()
                .ok_or(fail("connection_failed"))?,
            fixture.host_str().unwrap(),
            fixture
                .port_or_known_default()
                .ok_or(fail("connection_failed"))?
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
    easy.timeout(Duration::from_secs(20))?;
    easy.max_filesize(64 * 1024)?;
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
            return Err(fail("connection_failed"));
        }
    }
    let mut headers = List::new();
    headers.append("Accept: application/json")?;
    easy.http_headers(headers)?;
    let netrc_file;
    if let Some(path) = netrc {
        super::read(path, 8192)?;
        netrc_file = CString::new(path.as_os_str().as_encoded_bytes())
            .map_err(|_| fail("connection_failed"))?;
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
    let mut retry_after = 30;
    {
        let mut transfer = easy.transfer();
        transfer.header_function(|header| {
            if let Ok(line) = std::str::from_utf8(header) {
                if let Some((name, value)) = line.split_once(':') {
                    if name.eq_ignore_ascii_case("retry-after") {
                        if let Ok(seconds) = value.trim().parse::<u64>() {
                            retry_after = seconds.clamp(1, 86400);
                        }
                    }
                }
            }
            true
        })?;
        transfer.write_function(|part| {
            if bytes.len().saturating_add(part.len()) > 64 * 1024 {
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
        429 => Err(crate::Error("rate_limited", Some(retry_after))),
        _ => Err(fail("connection_failed")),
    }
}
