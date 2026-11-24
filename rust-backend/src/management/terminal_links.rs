//! An explicit opt-in installs the companion. Herdr discovers link handlers
//! automatically, so the main Jira Peek mod carries no link rules.
use super::{doctor, fs, manifest};
use crate::{fail, storage::hash, Result};
use serde_json::{json, Map, Value};
use std::{io::Write, os::unix::fs::OpenOptionsExt, path::Path};

const COMPANION: &str = "jira-peek-terminal-links";
const OWNER: &str = "herdr-jira-peek";
const MARKER: &str = "OWNER.json";
const FILES: [&str; 3] = ["mod.json", "link.js", "binding.json"];
const LINK_JS: &str = include_str!("../terminal-link.js");

pub fn enable(home: &Path, config_dir: &Path) -> Result<()> {
    if !host_supported(doctor::app_version().as_deref()) {
        return Err(fail("terminal_links_host_unsupported"));
    }
    fs::safe_path(config_dir)?;
    let canonical =
        std::fs::canonicalize(config_dir).map_err(|_| fail("invalid_config_directory"))?;
    let config = crate::terminal_link_config(&canonical)?;
    let origin = origin(config.get("JIRA_BASE"))?;
    let config_dir = canonical
        .to_str()
        .ok_or_else(|| fail("invalid_config_directory"))?;
    install_companion(home, config_dir, &origin)?;
    println!("Terminal link previews enabled. Select a personal Herdr layout.");
    Ok(())
}

pub fn disable(home: &Path) -> Result<()> {
    fs::safe_path(home)?;
    let mods = home.join("mods");
    fs::safe_path(&mods)?;
    if !mods.is_dir() {
        return Ok(());
    }
    let _lock = fs::InstallLock::acquire(&mods)?;
    let dir = mods.join(COMPANION);
    if !is_directory(&dir)? {
        return Ok(());
    }
    read_owned(&dir)?;
    // Herdr skips dot-prefixed mod directories. Detach the entire companion
    // first so Herdr always sees either an intact handler or no handler.
    let retired = tempfile::Builder::new()
        .prefix(".jira-peek-terminal-links-retired-")
        .tempdir_in(&mods)?;
    std::fs::rename(&dir, retired.path().join(COMPANION))?;
    retired.close()?;
    println!("Terminal link previews disabled.");
    Ok(())
}

fn host_supported(version: Option<&str>) -> bool {
    version.is_some_and(|version| {
        version
            .split('.')
            .map(str::parse::<u64>)
            .collect::<std::result::Result<Vec<_>, _>>()
            .is_ok_and(|parts| parts.len() == 3 && parts.as_slice() >= [0, 1, 17].as_slice())
    })
}

fn origin(base: &str) -> Result<String> {
    let url = url::Url::parse(base).map_err(|_| fail("invalid_terminal_link_origin"))?;
    if url.scheme() != "https"
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.path() != "/"
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(fail("invalid_terminal_link_origin"));
    }
    Ok(url.origin().ascii_serialization())
}

fn link_pattern(origin: &str) -> String {
    let port = if url::Url::parse(origin).is_ok_and(|url| url.port().is_none()) {
        "(?::443)?"
    } else {
        ""
    };
    format!(
        "^(?i:{}){port}/browse/[A-Z][A-Z0-9_]*-[0-9]+(?:[?#]|$)",
        regex::escape(origin)
    )
}

fn main_capable(main: &Path) -> Result<()> {
    manifest::managed(main).map_err(|_| fail("terminal_links_main_unavailable"))?;
    if manifest::json(&main.join("mod.json"))?["terminalLinkPreview"] != json!(1) {
        return Err(fail("terminal_links_capability_missing"));
    }
    Ok(())
}

fn install_companion(home: &Path, config_dir: &str, origin: &str) -> Result<()> {
    let mods = home.join("mods");
    let _lock = fs::InstallLock::acquire(&mods)?;
    main_capable(&mods.join("jira-peek"))?;
    let dir = mods.join(COMPANION);
    let files = companion_files(config_dir, origin, &link_pattern(origin))?;
    let digests: Map<_, _> = files
        .iter()
        .map(|(name, value)| ((*name).to_owned(), json!(hash(value.as_bytes()))))
        .collect();
    let marker = json!({"owner":OWNER,"kind":COMPANION,"schema":1,"files":digests});
    if is_directory(&dir)? {
        if read_owned(&dir)? == marker {
            return Ok(());
        }
        return Err(fail("terminal_links_companion_exists"));
    }
    let staging = tempfile::Builder::new()
        .prefix(".jira-peek-terminal-links-stage-")
        .tempdir_in(&mods)?;
    for (name, contents) in files {
        write_new(&staging.path().join(name), contents.as_bytes())?;
    }
    write_new(
        &staging.path().join(MARKER),
        &serde_json::to_vec_pretty(&marker)?,
    )?;
    if is_directory(&dir)? {
        return Err(fail("terminal_links_companion_exists"));
    }
    std::fs::rename(staging.path(), &dir)?;
    Ok(())
}

fn companion_files(
    config_dir: &str,
    origin: &str,
    pattern: &str,
) -> Result<Vec<(&'static str, String)>> {
    let manifest = json!({"name":"Jira Peek Terminal Links","place":"none",
        "link_handlers":[{"kind":"url","pattern":pattern}]});
    let binding = json!({"configDir":config_dir,"origin":origin});
    Ok(vec![
        ("mod.json", serde_json::to_string_pretty(&manifest)? + "\n"),
        ("link.js", LINK_JS.to_owned()),
        (
            "binding.json",
            serde_json::to_string_pretty(&binding)? + "\n",
        ),
    ])
}

fn is_directory(dir: &Path) -> Result<bool> {
    match std::fs::symlink_metadata(dir) {
        Ok(metadata) if metadata.is_dir() => Ok(true),
        Ok(_) => Err(fail("terminal_links_companion_unowned")),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err(fail("unsafe_management_path")),
    }
}

fn read_owned(dir: &Path) -> Result<Value> {
    let marker =
        manifest::json(&dir.join(MARKER)).map_err(|_| fail("terminal_links_companion_unowned"))?;
    let entries = marker["files"]
        .as_object()
        .ok_or_else(|| fail("terminal_links_companion_unowned"))?;
    if marker["owner"] != OWNER
        || marker["kind"] != COMPANION
        || marker["schema"] != 1
        || entries.len() != FILES.len()
    {
        return Err(fail("terminal_links_companion_unowned"));
    }
    for name in FILES {
        let expected = entries
            .get(name)
            .and_then(Value::as_str)
            .filter(|s| manifest::hash(s))
            .ok_or_else(|| fail("terminal_links_companion_unowned"))?;
        if fs::digest(&dir.join(name))? != expected {
            return Err(fail("terminal_links_companion_edited"));
        }
    }
    if manifest::walk(dir)?
        .iter()
        .any(|name| name != MARKER && !FILES.contains(&name.as_str()))
    {
        return Err(fail("terminal_links_companion_edited"));
    }
    Ok(marker)
}

fn write_new(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)?;
    file.write_all(bytes)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{os::unix::fs::PermissionsExt, path::PathBuf};

    const MAX_FILE: u64 = 1024 * 1024;

    fn home() -> (tempfile::TempDir, PathBuf) {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().canonicalize().unwrap();
        std::fs::create_dir_all(root.join("mods")).unwrap();
        (temp, root)
    }

    fn managed_bundle(home: &Path, capability: Option<Value>) -> PathBuf {
        let main = home.join("mods/jira-peek");
        std::fs::create_dir_all(&main).unwrap();
        let mut files = Map::new();
        for name in manifest::inventory() {
            let path = main.join(&name);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            let bytes = if name == "mod.json" {
                let mut meta = json!({"name": "Jira Peek", "version": "0.16.0", "place": "right"});
                if let Some(value) = capability.as_ref() {
                    meta["terminalLinkPreview"] = value.clone();
                }
                serde_json::to_vec_pretty(&meta).unwrap()
            } else {
                b"fixture\n".to_vec()
            };
            std::fs::write(&path, &bytes).unwrap();
            if name == "runtime/jira-peek-bridge" {
                std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
            }
            files.insert(name, json!(hash(&bytes)));
        }
        let install = json!({
            "owner": OWNER,
            "version": "0.16.0",
            "configDir": null,
            "format": 1,
            "files": files,
        });
        std::fs::write(
            main.join("install.json"),
            format!("{}\n", serde_json::to_string_pretty(&install).unwrap()),
        )
        .unwrap();
        main
    }

    fn install(home: &Path, config: &str, origin: &str) {
        install_companion(home, config, origin).unwrap();
    }

    fn read_json(path: &Path) -> Value {
        serde_json::from_slice(&fs::read_regular(path, MAX_FILE).unwrap()).unwrap()
    }

    #[test]
    fn host_gate_requires_017_and_origin_is_canonical() {
        assert!(!host_supported(None));
        assert!(!host_supported(Some("0.1.16")));
        assert!(!host_supported(Some("herdr-app 0.1.16")));
        assert!(host_supported(Some("0.1.17")));
        assert!(host_supported(Some("0.2.0")));
        assert!(!host_supported(Some("unexpected")));
        assert_eq!(
            origin("https://jira.example.test:443/").unwrap(),
            "https://jira.example.test"
        );
        for bad in [
            "http://jira.example.test",
            "https://user@jira.example.test",
            "https://jira.example.test/browse",
            "https://jira.example.test?x=1",
            "not a url",
        ] {
            assert!(origin(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn companion_has_no_defaults_and_an_escaped_origin_rule() {
        let pattern = link_pattern("https://jira.example.test");
        let files =
            companion_files("/fictional/config", "https://jira.example.test", &pattern).unwrap();
        let manifest: Value = serde_json::from_str(&files[0].1).unwrap();
        assert_eq!(manifest["place"], "none");
        assert_eq!(manifest["link_handlers"].as_array().unwrap().len(), 1);
        assert_eq!(manifest["link_handlers"][0]["kind"], "url");
        assert_eq!(manifest["link_handlers"][0]["pattern"], json!(pattern));
        let regex = regex::Regex::new(&pattern).unwrap();
        assert!(regex.is_match("https://Jira.example.test:443/browse/ABC-1?q=fictional"));
        assert!(!regex.is_match("https://jiraXexample.test/browse/ABC-1"));
        assert!(!regex.is_match("https://jira.example.test:444/browse/ABC-1"));
        assert!(!regex.is_match("https://jira.example.test/browse/ABC-1/extra"));
        assert!(!pattern.contains("atlassian.net"));
        assert_eq!(files[1].1, LINK_JS);
        let binding: Value = serde_json::from_str(&files[2].1).unwrap();
        assert_eq!(binding["configDir"], json!("/fictional/config"));
        assert_eq!(binding["origin"], json!("https://jira.example.test"));
    }

    #[test]
    fn main_bundle_must_be_managed_and_capable() {
        let (_temp, home) = home();
        assert!(main_capable(&home.join("mods/jira-peek")).is_err());
        let main = managed_bundle(&home, Some(json!(1)));
        main_capable(&main).unwrap();
        for bad in [None, Some(json!(0)), Some(json!("1"))] {
            let main = managed_bundle(&home, bad);
            assert!(main_capable(&main).is_err());
        }
        let main = managed_bundle(&home, Some(json!(1)));
        std::fs::write(main.join("link.js"), b"edited\n").unwrap();
        assert!(main_capable(&main).is_err());
    }

    #[test]
    fn enable_is_exact_and_disable_detaches_independently() {
        let (_temp, home) = home();
        let main = managed_bundle(&home, Some(json!(1)));
        let config = "/fictional/jira-config";
        let origin = "https://jira.example.test";
        install(&home, config, origin);
        let dir = home.join("mods").join(COMPANION);
        let mut names: Vec<_> = std::fs::read_dir(&dir)
            .unwrap()
            .map(|e| e.unwrap().file_name().to_str().unwrap().to_owned())
            .collect();
        names.sort();
        assert_eq!(
            names,
            vec!["OWNER.json", "binding.json", "link.js", "mod.json"]
        );
        assert_eq!(
            read_json(&dir.join("binding.json"))["configDir"],
            json!(config)
        );
        assert_eq!(
            read_json(&dir.join("binding.json"))["origin"],
            json!(origin)
        );

        let before: Vec<_> = names
            .iter()
            .map(|n| fs::digest(&dir.join(n)).unwrap())
            .collect();
        install(&home, config, origin);
        let after: Vec<_> = names
            .iter()
            .map(|n| fs::digest(&dir.join(n)).unwrap())
            .collect();
        assert_eq!(before, after, "exact enable must not rewrite the companion");

        // A config change needs an explicit disable first.
        assert!(install_companion(&home, "/fictional/other", origin).is_err());
        assert_eq!(
            read_json(&dir.join("binding.json"))["configDir"],
            json!(config)
        );

        // Disable is independent of the main bundle: it neither edits nor
        // requires it.
        assert!(manifest::managed(&main).is_ok());
        std::fs::remove_dir_all(&main).unwrap();
        disable(&home).unwrap();
        assert!(!dir.exists());
        disable(&home).unwrap();
    }

    #[test]
    fn edits_and_unowned_directories_are_preserved() {
        let (_temp, home) = home();
        managed_bundle(&home, Some(json!(1)));
        let dir = home.join("mods").join(COMPANION);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("mod.json"), b"someone else\n").unwrap();
        assert!(
            install_companion(&home, "/fictional/config", "https://jira.example.test").is_err()
        );
        assert!(disable(&home).is_err());
        assert_eq!(
            fs::read_regular(&dir.join("mod.json"), MAX_FILE).unwrap(),
            b"someone else\n"
        );

        std::fs::remove_dir_all(&dir).unwrap();
        install(&home, "/fictional/config", "https://jira.example.test");
        std::fs::write(dir.join("link.js"), b"user edit\n").unwrap();
        assert!(
            install_companion(&home, "/fictional/config", "https://jira.example.test").is_err()
        );
        assert!(disable(&home).is_err());
        assert_eq!(
            fs::read_regular(&dir.join("link.js"), MAX_FILE).unwrap(),
            b"user edit\n"
        );

        std::fs::write(dir.join("notes.txt"), b"keep me\n").unwrap();
        assert!(
            install_companion(&home, "/fictional/config", "https://jira.example.test").is_err()
        );
        assert!(disable(&home).is_err());
        assert_eq!(
            fs::read_regular(&dir.join("notes.txt"), MAX_FILE).unwrap(),
            b"keep me\n"
        );

        std::fs::remove_dir_all(&dir).unwrap();
        std::os::unix::fs::symlink(home.join("mods/jira-peek"), &dir).unwrap();
        assert!(
            install_companion(&home, "/fictional/config", "https://jira.example.test").is_err()
        );
        assert!(disable(&home).is_err());
    }
}
