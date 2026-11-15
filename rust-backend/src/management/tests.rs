use super::*;
use serde_json::json;
use std::{fs as stdfs, path::Path};
pub(super) fn fixture(root: &Path, version: &str) -> serde_json::Value {
    stdfs::create_dir_all(root.join("runtime")).unwrap();
    let mut files = serde_json::Map::new();
    for name in ["main.js", "mod.json", "LICENSE", "runtime/app-bridge.sh"] {
        stdfs::write(root.join(name), version).unwrap();
        files.insert(name.into(), fs::digest(&root.join(name)).unwrap().into());
    }
    let m = json!({"owner":"herdr-jira-peek","format":1,"version":version,"configDir":null,"files":files});
    stdfs::write(root.join("install.json"), serde_json::to_vec(&m).unwrap()).unwrap();
    m
}
#[test]
fn strict_json_and_type_validation() {
    assert!(manifest::parse(br#"{"files":{"a":1,"a":2}}"#).is_err());
    assert!(manifest::parse(br#"{"a":1} trailing"#).is_err());
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path().canonicalize().unwrap();
    let m = fixture(&root, "1.2.3");
    for bad in [json!(true), json!(1.0), json!("1"), json!(2)] {
        let mut changed = m.clone();
        changed["format"] = bad;
        stdfs::write(
            root.join("install.json"),
            serde_json::to_vec(&changed).unwrap(),
        )
        .unwrap();
        assert!(manifest::managed(&root).is_err());
    }
}
#[test]
fn concurrent_edits_prevent_replacement() {
    let temp = tempfile::tempdir().unwrap();
    let mods = temp.path().canonicalize().unwrap();
    let dest = mods.join("jira-peek");
    let stage = mods.join("stage");
    let old = fixture(&dest, "1.0.0");
    fixture(&stage, "2.0.0");
    stdfs::write(dest.join("main.js"), "edited").unwrap();
    assert!(install::replace(&stage, &dest, Some(&old)).is_err());
    assert_eq!(
        stdfs::read_to_string(dest.join("main.js")).unwrap(),
        "edited"
    );
    assert!(stage.exists());
}
#[test]
fn interrupted_rename_recovers_only_recorded_valid_backup() {
    let temp = tempfile::tempdir().unwrap();
    let mods = temp.path().canonicalize().unwrap();
    let dest = mods.join("jira-peek");
    fixture(&dest, "1.0.0");
    let name = ".jira-peek-backup-012345abcdef";
    let record = json!({"backup":name,"manifest":fs::digest(&dest.join("install.json")).unwrap()});
    stdfs::write(
        mods.join(".jira-peek-replacement.json"),
        serde_json::to_vec(&record).unwrap(),
    )
    .unwrap();
    stdfs::rename(&dest, mods.join(name)).unwrap();
    install::recover(&mods).unwrap();
    assert_eq!(manifest::managed(&dest).unwrap()["version"], "1.0.0");
    assert!(!mods.join(".jira-peek-replacement.json").exists());
    stdfs::rename(&dest, mods.join(name)).unwrap();
    stdfs::write(mods.join(name).join("main.js"), "edited").unwrap();
    stdfs::write(
        mods.join(".jira-peek-replacement.json"),
        serde_json::to_vec(&record).unwrap(),
    )
    .unwrap();
    assert!(install::recover(&mods).is_err());
    assert!(!dest.exists());
    assert!(mods.join(".jira-peek-replacement.json").exists());
}
#[test]
fn active_bundle_wins_after_publication_and_backups_remain() {
    let temp = tempfile::tempdir().unwrap();
    let mods = temp.path().canonicalize().unwrap();
    let dest = mods.join("jira-peek");
    let stage = mods.join("stage");
    let old = fixture(&dest, "1.0.0");
    fixture(&stage, "2.0.0");
    let name = install::replace(&stage, &dest, Some(&old))
        .unwrap()
        .unwrap();
    assert!(install::backup_name(&name));
    assert_eq!(manifest::managed(&mods.join(&name)).unwrap(), old);
    stdfs::write(
        mods.join(".jira-peek-replacement.json"),
        b"interrupted intent",
    )
    .unwrap();
    install::recover(&mods).unwrap();
    assert_eq!(manifest::managed(&dest).unwrap()["version"], "2.0.0");
    assert!(mods.join(name).exists());
}
#[test]
fn source_digest_rejects_directory_symlinks() {
    let temp = tempfile::tempdir().unwrap();
    let root = temp.path().canonicalize().unwrap();
    stdfs::create_dir(root.join("src")).unwrap();
    for n in ["Cargo.toml", "Cargo.lock", "build.rs", "src/main.rs"] {
        stdfs::write(root.join(n), b"fictional").unwrap();
    }
    assert!(bundle::source_digest(&root).is_ok());
    std::os::unix::fs::symlink(root.join("src"), root.join("src/link")).unwrap();
    assert!(bundle::source_digest(&root).is_err());
}
