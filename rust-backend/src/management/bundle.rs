use super::{
    fs::{read_regular, safe_path},
    manifest, process,
};
use crate::{fail, Result};
use sha2::{Digest, Sha256};
use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::Path,
    process::Command,
    time::{Duration, Instant},
};
pub fn source_digest(root: &Path) -> Result<String> {
    safe_path(root)?;
    for name in ["Cargo.toml", "Cargo.lock", "build.rs", "src/main.rs"] {
        read_regular(&root.join(name), 32 * 1024 * 1024)?;
    }
    let mut names = vec!["Cargo.toml".into(), "Cargo.lock".into(), "build.rs".into()];
    let mut sources: Vec<_> = manifest::walk(&root.join("src"))?
        .into_iter()
        .filter(|s| !s.ends_with('/'))
        .map(|s| format!("src/{s}"))
        .collect();
    // Python's sorted(Path) compares components: setup/http.rs precedes
    // setup.rs. Sorting slash-joined strings reverses those two entries.
    sources.sort_by(|a, b| a.split('/').cmp(b.split('/')));
    names.extend(sources);
    let mut h = Sha256::new();
    for name in names {
        h.update(name.as_bytes());
        h.update([0]);
        h.update(read_regular(&root.join(name), 32 * 1024 * 1024)?);
        h.update([0]);
    }
    Ok(format!("{:x}", h.finalize()))
}
pub fn platform() -> Result<String> {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;
    if !["macos", "linux"].contains(&os) || !["aarch64", "x86_64"].contains(&arch) {
        return Err(fail("unsupported_runtime_target"));
    }
    Ok(format!("{os}-{arch}"))
}
fn download(url: &str, limit: usize, deadline: Instant) -> Result<Vec<u8>> {
    let mut easy = curl::easy::Easy::new();
    easy.url(url)?;
    // libcurl does not apply curl CLI trust overrides itself. Match the reader
    // and setup paths, including a caller's explicitly configured private CA.
    if let Some(path) = std::env::var_os("CURL_CA_BUNDLE")
        .filter(|s| !s.is_empty())
        .or_else(|| std::env::var_os("SSL_CERT_FILE").filter(|s| !s.is_empty()))
    {
        easy.cainfo(Path::new(&path))?;
    }
    if let Some(path) = std::env::var_os("SSL_CERT_DIR").filter(|s| !s.is_empty()) {
        easy.capath(Path::new(&path))?;
    }
    easy.follow_location(true)?;
    easy.max_redirections(5)?;
    // Restrict initial requests and every redirect to HTTPS using libcurl's protocol mask.
    unsafe {
        if curl_sys::curl_easy_setopt(
            easy.raw(),
            curl_sys::CURLOPT_PROTOCOLS,
            curl_sys::CURLPROTO_HTTPS as libc::c_long,
        ) != curl_sys::CURLE_OK
            || curl_sys::curl_easy_setopt(
                easy.raw(),
                curl_sys::CURLOPT_REDIR_PROTOCOLS,
                curl_sys::CURLPROTO_HTTPS as libc::c_long,
            ) != curl_sys::CURLE_OK
        {
            return Err(fail("https_policy_failed"));
        }
    }
    easy.timeout(
        deadline
            .checked_duration_since(Instant::now())
            .filter(|d| !d.is_zero())
            .ok_or_else(|| fail("runtime_download_timeout"))?,
    )?;
    easy.useragent("jira-peek-installer")?;
    easy.fail_on_error(true)?;
    let mut bytes = Vec::new();
    {
        let mut t = easy.transfer();
        t.write_function(|b| {
            if bytes.len() + b.len() > limit {
                return Ok(0);
            }
            bytes.extend_from_slice(b);
            Ok(b.len())
        })?;
        t.perform().map_err(|_| fail("runtime_download_failed"))?;
    }
    Ok(bytes)
}
pub fn stage(root: &Path, runtime: &Path, version: &str) -> Result<()> {
    stage_with_download(root, runtime, version, download)
}
fn stage_with_download(
    root: &Path,
    runtime: &Path,
    version: &str,
    fetch: impl Fn(&str, usize, Instant) -> Result<Vec<u8>>,
) -> Result<()> {
    if !manifest::version(version) {
        return Err(fail("invalid_runtime_version"));
    }
    let target = platform()?;
    let binary = format!("jira-peek-bridge-{target}");
    let notices = format!("{binary}-NOTICES.txt");
    let manifest_name = format!("{binary}.json");
    let local = root.join(".release-runtime");
    safe_path(&local)?;
    let local_exists = local.exists();
    if local_exists && !local.is_dir() {
        return Err(fail("unsafe_runtime_directory"));
    }
    let deadline = Instant::now() + Duration::from_secs(35);
    let base = format!(
        "https://github.com/hilmimuktitama/herdr-app-jira-peek/releases/download/v{version}/"
    );
    let get = |name: &str, limit: usize| -> Result<Vec<u8>> {
        if local_exists {
            read_regular(&local.join(name), limit as u64)
        } else {
            fetch(&format!("{base}{name}"), limit, deadline)
        }
    };
    let m = manifest::parse(&get(&manifest_name, 16384)?)?;
    if m["format"].as_u64() != Some(1)
        || m["releaseVersion"] != version
        || m["platform"] != target
        || m["sourceSha256"] != source_digest(&root.join("rust-backend"))?
        || m["files"]
            .as_object()
            .is_none_or(|o| o.len() != 2 || !o.contains_key(&binary) || !o.contains_key(&notices))
    {
        return Err(fail("runtime_manifest_mismatch"));
    }
    for (name, installed, limit, mode) in [
        (&binary, "jira-peek-bridge", 32 * 1024 * 1024, 0o700),
        (&notices, "THIRD-PARTY-NOTICES.txt", 4 * 1024 * 1024, 0o600),
    ] {
        let e = &m["files"][name];
        let size = e["size"]
            .as_u64()
            .filter(|s| *s > 0 && *s <= limit)
            .ok_or_else(|| fail("invalid_asset_size"))?;
        if !e["sha256"].as_str().is_some_and(manifest::hash) {
            return Err(fail("invalid_asset_hash"));
        }
        let bytes = get(name, size as usize)?;
        if bytes.len() as u64 != size || format!("{:x}", Sha256::digest(&bytes)) != e["sha256"] {
            return Err(fail("runtime_checksum_mismatch"));
        }
        fs::write(runtime.join(installed), bytes)?;
        fs::set_permissions(runtime.join(installed), fs::Permissions::from_mode(mode))?;
    }
    let home = tempfile::tempdir()?;
    let mut command = Command::new(runtime.join("jira-peek-bridge"));
    command
        .arg("--build-info")
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("HOME", home.path())
        .env("LANG", "C");
    let info = manifest::parse(&process::run(&mut command, 5)?)?;
    if info["protocol"].as_u64() != Some(1)
        || info["fixtureTransport"] != false
        || info["os"] != std::env::consts::OS
        || info["arch"] != std::env::consts::ARCH
        || !m["buildInfo"].is_object()
        || [
            "version",
            "protocol",
            "os",
            "arch",
            "fixtureTransport",
            "transport",
        ]
        .iter()
        .any(|k| info[*k] != m["buildInfo"][*k])
    {
        return Err(fail("runtime_build_identity_mismatch"));
    }
    fs::write(runtime.join("runtime.json"), serde_json::to_vec_pretty(&m)?)?;
    fs::write(
        runtime.join("app-bridge.sh"),
        b"#!/bin/sh\nexec \"${0%/*}/jira-peek-bridge\" \"$@\"\n",
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    #[test]
    fn source_digest_matches_python_path_component_order() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().canonicalize().unwrap();
        fs::create_dir_all(root.join("src/setup")).unwrap();
        let order = [
            "Cargo.toml",
            "Cargo.lock",
            "build.rs",
            "src/main.rs",
            "src/setup/http.rs",
            "src/setup.rs",
        ];
        let mut expected = Sha256::new();
        for name in order {
            fs::write(root.join(name), b"fictional source").unwrap();
            expected.update(name.as_bytes());
            expected.update(b"\0fictional source\0");
        }
        assert_eq!(
            source_digest(&root).unwrap(),
            format!("{:x}", expected.finalize())
        );
    }
    #[test]
    fn download_requires_https_and_enforces_deadline() {
        assert!(download(
            "http://127.0.0.1:1/fictional",
            10,
            Instant::now() + Duration::from_secs(1)
        )
        .is_err());
        assert!(download(
            "https://127.0.0.1:1/fictional",
            10,
            Instant::now() - Duration::from_secs(1)
        )
        .is_err());
    }
    #[test]
    fn remote_assets_use_exact_version_and_validate_before_executing() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().canonicalize().unwrap();
        fs::create_dir_all(root.join("rust-backend/src")).unwrap();
        for name in ["Cargo.toml", "Cargo.lock", "build.rs", "src/main.rs"] {
            fs::write(root.join("rust-backend").join(name), b"fictional source").unwrap();
        }
        let target = platform().unwrap();
        let binary = format!("jira-peek-bridge-{target}");
        let notices = format!("{binary}-NOTICES.txt");
        let m = serde_json::json!({"format":1,"releaseVersion":"1.2.3","platform":target,"sourceSha256":source_digest(&root.join("rust-backend")).unwrap(),"files":{&binary:{"size":3,"sha256":"0".repeat(64)},&notices:{"size":1,"sha256":"0".repeat(64)}}});
        let calls = RefCell::new(Vec::new());
        let result = stage_with_download(&root, &root, "1.2.3", |url, limit, deadline| {
            calls.borrow_mut().push((url.to_string(), limit));
            assert!(deadline > Instant::now());
            if url.ends_with(".json") {
                Ok(serde_json::to_vec(&m).unwrap())
            } else {
                Ok(b"bad".to_vec())
            }
        });
        assert_eq!(result.unwrap_err().0, "runtime_checksum_mismatch");
        let calls = calls.borrow();
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0],(format!("https://github.com/hilmimuktitama/herdr-app-jira-peek/releases/download/v1.2.3/{binary}.json"),16384));
        assert_eq!(calls[1],(format!("https://github.com/hilmimuktitama/herdr-app-jira-peek/releases/download/v1.2.3/{binary}"),3));
        assert!(!root.join("jira-peek-bridge").exists());
    }
}
