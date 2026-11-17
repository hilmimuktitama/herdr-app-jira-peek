//! Numbered release updater. Git is an explicit external dependency; HTTP assets
//! are staged by the same Rust bundle verifier used for local installation.
use super::{
    fs::{safe_path, InstallLock},
    install, manifest, process,
};
use crate::{fail, Result};
use std::{collections::BTreeMap, path::Path, process::Command};
const REPOSITORY: &str = "https://github.com/hilmimuktitama/herdr-app-jira-peek.git";
fn version(v: &str) -> Result<Vec<u64>> {
    if !regex::Regex::new(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
        .unwrap()
        .is_match(v)
    {
        return Err(fail("expected_numbered_release"));
    }
    v.split('.')
        .map(|s| s.parse().map_err(|_| fail("invalid_release_version")))
        .collect()
}
fn git(args: &[&str], cwd: Option<&Path>) -> Result<String> {
    let mut c = Command::new("git");
    c.args([
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "maintenance.auto=false",
        "-c",
        "gc.auto=0",
    ])
    .args(args)
    .env("GIT_TERMINAL_PROMPT", "0");
    for name in [
        "GIT_DIR",
        "GIT_COMMON_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
    ] {
        c.env_remove(name);
    }
    if let Some(p) = cwd {
        c.current_dir(p);
    }
    String::from_utf8(process::run(&mut c, 45).map_err(|_| fail("git_release_read_failed"))?)
        .map(|s| s.trim().into())
        .map_err(|_| fail("invalid_git_output"))
}
pub fn run(home: &Path, selected: Option<&str>, check: bool, allow_downgrade: bool) -> Result<()> {
    safe_path(home)?;
    let mods = home.join("mods");
    if !check && mods.join(".jira-peek-replacement.json").exists() {
        let _lock = InstallLock::acquire(&mods)?;
        install::recover(&mods)?;
    }
    let destination = mods.join("jira-peek");
    let current = manifest::managed(&destination)?;
    let installed = current["version"]
        .as_str()
        .ok_or_else(|| fail("invalid_installed_version"))?;
    let installed_tuple = version(installed)?;
    if let Some(v) = selected {
        version(v)?;
    }
    let output = git(
        &["ls-remote", "--tags", "--refs", REPOSITORY, "refs/tags/v*"],
        None,
    )?;
    let mut tags = BTreeMap::new();
    for line in output.lines() {
        let parts: Vec<_> = line.split_whitespace().collect();
        if parts.len() != 2
            || parts[0].len() != 40
            || !parts[0]
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            continue;
        }
        if let Some(v) = parts[1].strip_prefix("refs/tags/v") {
            if let Ok(tuple) = version(v) {
                tags.insert(tuple, (v.to_string(), parts[0].to_string()));
            }
        }
    }
    let chosen = if let Some(v) = selected {
        tags.get(&version(v)?)
    } else {
        tags.last_key_value().map(|(_, v)| v)
    }
    .ok_or_else(|| fail("numbered_release_unavailable"))?;
    println!("Installed: {installed}; selected release: {}", chosen.0);
    if chosen.0 == installed || check {
        return Ok(());
    }
    if version(&chosen.0)? < installed_tuple && !(selected.is_some() && allow_downgrade) {
        return Err(fail(
            "downgrade_requires_explicit_version_and_allow_downgrade",
        ));
    }
    let temporary = tempfile::tempdir()?;
    let root = temporary.path().canonicalize()?.join("source");
    git(
        &[
            "init",
            "--quiet",
            root.to_str().ok_or_else(|| fail("invalid_source_path"))?,
        ],
        None,
    )?;
    git(
        &[
            "fetch",
            "--quiet",
            "--no-tags",
            "--depth",
            "1",
            REPOSITORY,
            &format!("refs/tags/v{}", chosen.0),
        ],
        Some(&root),
    )?;
    if git(&["rev-parse", "FETCH_HEAD"], Some(&root))? != chosen.1 {
        return Err(fail("release_tag_changed"));
    }
    git(
        &["checkout", "--quiet", "--detach", "FETCH_HEAD"],
        Some(&root),
    )?;
    // walk rejects symlinks, including those outside the current install inventory.
    manifest::walk(&root)?;
    for name in ["package.json", "mods/jira-peek/mod.json"] {
        if manifest::json(&root.join(name))?["version"] != chosen.0 {
            return Err(fail("release_source_version_mismatch"));
        }
    }
    install::install_expected(
        install::Request {
            source_root: &root,
            app_home: home,
            config_dir: None,
            update: true,
            check: true,
        },
        Some(&current),
    )?;
    if manifest::managed(&destination)?["version"] != chosen.0 {
        return Err(fail("installed_version_unconfirmed"));
    }
    println!("Update complete. Toolbar/layout integration remains unverified; run manage integration diagnose if needed.");
    Ok(())
}
