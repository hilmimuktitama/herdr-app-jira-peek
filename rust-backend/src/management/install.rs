use super::{
    bundle,
    fs::{digest, read_regular, safe_path, InstallLock},
    manifest, process,
};
use crate::{fail, Result};
use serde_json::{json, Value};
use std::{
    fs,
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
    process::Command,
};
const JOURNAL: &str = ".jira-peek-replacement.json";
pub fn mkdir(path: &Path) -> Result<()> {
    safe_path(path)?;
    use std::os::unix::fs::DirBuilderExt;
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(path)?;
    Ok(())
}
fn write_new(path: &Path, bytes: &[u8], mode: u32) -> Result<()> {
    safe_path(path)?;
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(mode)
        .custom_flags(libc::O_NOFOLLOW)
        .open(path)?;
    f.write_all(bytes)?;
    f.set_permissions(fs::Permissions::from_mode(mode))?;
    f.sync_all()?;
    Ok(())
}
fn sync_dir(path: &Path) -> Result<()> {
    fs::File::open(path)?.sync_all()?;
    Ok(())
}
pub fn backup_name(name: &str) -> bool {
    regex::Regex::new(r"^\.jira-peek-backup-[0-9a-f]{12}$")
        .unwrap()
        .is_match(name)
}
pub fn recover(mods: &Path) -> Result<()> {
    let journal = mods.join(JOURNAL);
    safe_path(&journal)?;
    if !journal.exists() {
        return Ok(());
    }
    let destination = mods.join("jira-peek");
    safe_path(&destination)?;
    if destination.exists() {
        manifest::managed(&destination)?;
        fs::remove_file(journal)?;
        sync_dir(mods)?;
        return Ok(());
    }
    let record = manifest::json(&journal)?;
    if record.as_object().is_none_or(|o| o.len() != 2)
        || !record["backup"].as_str().is_some_and(backup_name)
        || !record["manifest"].as_str().is_some_and(manifest::hash)
    {
        return Err(fail("invalid_replacement_journal"));
    }
    let backup = mods.join(record["backup"].as_str().unwrap());
    manifest::managed(&backup)?;
    if digest(&backup.join("install.json"))? != record["manifest"] {
        return Err(fail("replacement_backup_changed"));
    }
    fs::rename(backup, destination)?;
    sync_dir(mods)?;
    fs::remove_file(journal)?;
    sync_dir(mods)?;
    println!("Recovered previous Jira Peek bundle.");
    Ok(())
}
/// Caller holds InstallLock. Revalidates both bundles immediately before rename.
pub fn replace(
    staged: &Path,
    destination: &Path,
    expected: Option<&Value>,
) -> Result<Option<String>> {
    replace_with_publish(staged, destination, expected, |from, to| {
        fs::rename(from, to)
    })
}
fn replace_with_publish(
    staged: &Path,
    destination: &Path,
    expected: Option<&Value>,
    publish: impl FnOnce(&Path, &Path) -> std::io::Result<()>,
) -> Result<Option<String>> {
    safe_path(destination)?;
    manifest::managed(staged)?;
    let current = if destination.exists() {
        Some(manifest::managed(destination)?)
    } else {
        None
    };
    if current.as_ref() != expected {
        return Err(fail("installation_changed_during_validation"));
    }
    let mods = destination
        .parent()
        .ok_or_else(|| fail("invalid_install_destination"))?;
    if staged.parent() != Some(mods) {
        return Err(fail("staging_must_share_install_filesystem"));
    }
    let journal = mods.join(JOURNAL);
    let mut backup = None;
    if current.is_some() {
        let random = tempfile::Builder::new()
            .prefix(".jira-peek-name-")
            .tempfile_in(mods)?;
        use sha2::{Digest, Sha256};
        let name = format!(
            ".jira-peek-backup-{}",
            &format!(
                "{:x}",
                Sha256::digest(random.path().as_os_str().as_encoded_bytes())
            )[..12]
        );
        let path = mods.join(&name);
        safe_path(&path)?;
        if path.exists() {
            return Err(fail("backup_collision"));
        }
        write_new(
            &journal,
            &serde_json::to_vec(
                &json!({"backup":name,"manifest":digest(&destination.join("install.json"))?}),
            )?,
            0o600,
        )?;
        sync_dir(mods)?;
        fs::rename(destination, &path)?;
        sync_dir(mods)?;
        backup = Some(name);
    }
    if publish(staged, destination).is_err() {
        if let Some(name) = &backup {
            if fs::rename(mods.join(name), destination).is_err() {
                return Err(fail("replacement_failed_recovery_required"));
            }
            sync_dir(mods)?;
            fs::remove_file(&journal)?;
        }
        return Err(fail("replacement_failed_previous_preserved"));
    }
    // A failure after activation is reported distinctly; the journal allows the
    // next invocation to validate the active bundle before removing intent.
    sync_dir(mods).map_err(|_| fail("installation_activated_cleanup_incomplete"))?;
    if backup.is_some() {
        fs::remove_file(journal).map_err(|_| fail("installation_activated_cleanup_incomplete"))?;
        sync_dir(mods).map_err(|_| fail("installation_activated_cleanup_incomplete"))?;
    }
    Ok(backup)
}
fn copy(source: &Path, target: &Path, preserve_mode: bool) -> Result<()> {
    mkdir(target.parent().ok_or_else(|| fail("invalid_copy_target"))?)?;
    let bytes = read_regular(source, 32 * 1024 * 1024)?;
    let mode = if preserve_mode {
        fs::metadata(source)?.permissions().mode() & 0o777
    } else {
        0o600
    };
    write_new(target, &bytes, mode)
}
fn copy_bundle(source: &Path, target: &Path, m: &Value) -> Result<()> {
    for name in m["files"]
        .as_object()
        .ok_or_else(|| fail("invalid_install_manifest"))?
        .keys()
    {
        copy(&source.join(name), &target.join(name), true)?;
    }
    Ok(())
}
pub fn native_check(staged: &Path) -> Result<()> {
    let report = super::doctor::report();
    if report["ok"] != true {
        return Err(fail("missing_host_capabilities"));
    }
    let temp = tempfile::tempdir()?;
    let base = temp.path().canonicalize()?;
    let checked = base.join("mod");
    mkdir(&checked)?;
    let mut m = manifest::managed(staged)?;
    copy_bundle(staged, &checked, &m)?;
    m["configDir"] = Value::Null;
    write_new(
        &checked.join("install.json"),
        &serde_json::to_vec(&m)?,
        0o600,
    )?;
    mkdir(&base.join("run"))?;
    let mut command = Command::new("herdr-app");
    command.arg("check").arg(&checked);
    process::isolated(&mut command, &base);
    process::run(&mut command, 60).map_err(|_| fail("native_check_failed_previous_preserved"))?;
    Ok(())
}
pub struct Request<'a> {
    pub source_root: &'a Path,
    pub app_home: &'a Path,
    pub config_dir: Option<&'a Path>,
    pub update: bool,
    pub check: bool,
}
pub fn install(request: Request<'_>) -> Result<PathBuf> {
    install_expected(request, None)
}
pub fn install_expected(request: Request<'_>, expected: Option<&Value>) -> Result<PathBuf> {
    super::ui::install_attached(request, expected, None)
}
/// Caller holds InstallLock and has recovered pending replacement intent. This
/// hook lets the coordinator keep bundle and optional integration under one lock.
pub fn install_locked(request: Request<'_>, expected: Option<&Value>) -> Result<PathBuf> {
    safe_path(request.source_root)?;
    safe_path(request.app_home)?;
    let mods = request.app_home.join("mods");
    safe_path(&mods)?;
    let destination = mods.join("jira-peek");
    safe_path(&destination)?;
    let old = if destination.exists() {
        if !request.update {
            return Err(fail("already_installed_use_update"));
        }
        Some(manifest::managed(&destination)?)
    } else {
        None
    };
    if expected.is_some() && old.as_ref() != expected {
        return Err(fail("installation_changed_during_download"));
    }
    let config = if let Some(p) = request.config_dir {
        safe_path(p)?;
        Value::String(
            p.to_str()
                .ok_or_else(|| fail("invalid_config_path"))?
                .into(),
        )
    } else {
        old.as_ref()
            .map(|m| m["configDir"].clone())
            .unwrap_or(Value::Null)
    };
    let stage = tempfile::Builder::new()
        .prefix(".jira-peek-install-")
        .tempdir_in(&mods)?;
    let root = request.source_root;
    let metadata = manifest::json(&root.join("mods/jira-peek/mod.json"))?;
    let version = metadata["version"]
        .as_str()
        .filter(|s| manifest::version(s))
        .ok_or_else(|| fail("invalid_mod_version"))?;
    if manifest::json(&root.join("package.json"))?["version"] != version {
        return Err(fail("package_mod_identity_mismatch"));
    }
    let historical = super::source::historical(root, version)?;
    if historical.is_none() {
        super::source::validate_current(root)?;
    }
    let inventory = historical
        .as_ref()
        .map(|p| p.inventory())
        .unwrap_or_else(manifest::inventory);
    let rust = historical.as_ref().is_none_or(|p| p.rust);
    let runtime = stage.path().join("runtime");
    mkdir(&runtime)?;
    for name in &inventory {
        if rust
            && [
                "runtime/jira-peek-bridge",
                "runtime/runtime.json",
                "runtime/THIRD-PARTY-NOTICES.txt",
            ]
            .contains(&name.as_str())
        {
            continue;
        }
        copy(
            &super::source::source_path(root, name),
            &stage.path().join(name),
            false,
        )?;
    }
    if manifest::json(&stage.path().join("mod.json"))? != metadata {
        return Err(fail("source_metadata_changed_during_staging"));
    }
    if rust {
        bundle::stage(root, &runtime, version)?;
    }
    let mut files = serde_json::Map::new();
    for name in inventory {
        let hash = if let Some(hash) = historical.as_ref().and_then(|p| p.installed_hash(&name)) {
            hash.to_string()
        } else {
            digest(&stage.path().join(&name))?
        };
        files.insert(name, hash.into());
    }
    let m = json!({"owner":"herdr-jira-peek","format":1,"version":version,"configDir":config,"files":files});
    write_new(
        &stage.path().join("install.json"),
        &serde_json::to_vec_pretty(&m)?,
        0o600,
    )?;
    if request.check {
        native_check(stage.path())?;
    }
    let config = request.app_home.join("data/jira-peek/config");
    mkdir(&config)?;
    let example = config.join("config.example.sh");
    safe_path(&example)?;
    if !example.exists() {
        copy(&root.join("config.example.sh"), &example, false)?;
    }
    let backup = replace(stage.path(), &destination, old.as_ref())?;
    println!("Installed Jira Peek {version}. Personal settings, layouts and keys preserved.");
    if let Some(name) = backup {
        println!("Previous bundle: {name}");
    }
    Ok(destination)
}
pub fn rollback(app_home: &Path, name: &str, check: bool) -> Result<PathBuf> {
    if !backup_name(name) {
        return Err(fail("invalid_backup_name"));
    }
    safe_path(app_home)?;
    let mods = app_home.join("mods");
    let _lock = InstallLock::acquire(&mods)?;
    recover(&mods)?;
    let destination = mods.join("jira-peek");
    let current = manifest::managed(&destination)?;
    let backup = mods.join(name);
    let mut restored = manifest::managed(&backup)?;
    let stage = tempfile::Builder::new()
        .prefix(".jira-peek-install-")
        .tempdir_in(&mods)?;
    copy_bundle(&backup, stage.path(), &restored)?;
    restored["configDir"] = current["configDir"].clone();
    write_new(
        &stage.path().join("install.json"),
        &serde_json::to_vec_pretty(&restored)?,
        0o600,
    )?;
    if check {
        native_check(stage.path())?;
    }
    let saved = replace(stage.path(), &destination, Some(&current))?;
    println!(
        "Restored Jira Peek {}. Current settings and selected backup preserved.",
        restored["version"].as_str().unwrap()
    );
    if let Some(n) = saved {
        println!("Previous bundle: {n}");
    }
    Ok(destination)
}

#[cfg(test)]
mod failure_tests {
    use super::*;
    #[test]
    fn failed_publication_restores_previous_bundle() {
        let temp = tempfile::tempdir().unwrap();
        let mods = temp.path().canonicalize().unwrap();
        let destination = mods.join("jira-peek");
        let staged = mods.join("stage");
        let old = crate::management::tests::fixture(&destination, "1.0.0");
        crate::management::tests::fixture(&staged, "2.0.0");
        let result = replace_with_publish(&staged, &destination, Some(&old), |_, _| {
            Err(std::io::Error::from(std::io::ErrorKind::PermissionDenied))
        });
        assert!(result.is_err());
        assert_eq!(manifest::managed(&destination).unwrap(), old);
        assert!(!mods.join(JOURNAL).exists());
        assert!(staged.exists());
    }
}
