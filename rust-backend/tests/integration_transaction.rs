#[path = "../src/management/integration.rs"]
#[allow(dead_code)]
mod integration;
use integration::*;
use std::{collections::BTreeMap, fs};
#[test]
fn publication_is_idempotent_and_preserves_conflicts() {
    let home = tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap();
    let target = home.path().join("mods/tabs-jira-peek/main.js");
    let plan = AttachmentPlan::from_parts(
        "main-jira-peek".into(),
        home.path().into(),
        BTreeMap::from([(target.clone(), b"fictional".to_vec())]),
        BTreeMap::new(),
        BTreeMap::new(),
        true,
    )
    .unwrap();
    apply_attachment(&plan, home.path()).unwrap();
    apply_attachment(&plan, home.path()).unwrap();
    fs::write(&target, b"personal").unwrap();
    assert_eq!(
        apply_attachment(&plan, home.path()),
        Err(IntegrationError::Conflict)
    );
    assert_eq!(fs::read(target).unwrap(), b"personal");
}
#[test]
fn detects_identity_replacement_and_inventory_drift() {
    let home = tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap();
    let source = home.path().join("source");
    fs::create_dir(&source).unwrap();
    let file = source.join("main.js");
    fs::write(&file, b"fixture").unwrap();
    let plan = AttachmentPlan::from_parts(
        "fixture".into(),
        home.path().into(),
        BTreeMap::new(),
        BTreeMap::from([(file.clone(), Some(integration_snapshot(&file).unwrap()))]),
        BTreeMap::from([(source.clone(), toolbar_files(&source).unwrap())]),
        true,
    )
    .unwrap();
    fs::write(source.join("extra.js"), b"extra").unwrap();
    assert_eq!(validate_attachment(&plan), Err(IntegrationError::Changed));
    fs::remove_file(source.join("extra.js")).unwrap();
    fs::rename(&file, source.join("old")).unwrap();
    fs::write(&file, b"fixture").unwrap();
    assert_eq!(validate_attachment(&plan), Err(IntegrationError::Changed));
}
#[test]
fn rejects_symlinks_fifo_and_oversized_files() {
    let home = tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap();
    let file = home.path().join("file");
    fs::write(&file, b"fixture").unwrap();
    let link = home.path().join("link");
    std::os::unix::fs::symlink(&file, &link).unwrap();
    assert_eq!(
        integration_snapshot(&link),
        Err(IntegrationError::UnsafePath)
    );
    let fifo = home.path().join("fifo");
    let c = std::ffi::CString::new(fifo.as_os_str().as_encoded_bytes()).unwrap();
    unsafe {
        assert_eq!(libc::mkfifo(c.as_ptr(), 0o600), 0);
    }
    assert_eq!(
        integration_snapshot(&fifo),
        Err(IntegrationError::InvalidFile)
    );
    fs::File::create(&file)
        .unwrap()
        .set_len(4 * 1024 * 1024 + 1)
        .unwrap();
    assert_eq!(integration_snapshot(&file), Err(IntegrationError::Limit));
}
#[test]
fn staged_check_does_not_publish_and_revalidates() {
    let home = tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap();
    let source = home.path().join("source");
    fs::write(&source, b"fixture").unwrap();
    let toolbar = home.path().join("mods/tabs-jira-peek");
    let target = toolbar.join("main.js");
    let plan = AttachmentPlan::from_parts(
        "fixture".into(),
        home.path().into(),
        BTreeMap::from([(target.clone(), b"fixture".to_vec())]),
        BTreeMap::from([(source.clone(), Some(integration_snapshot(&source).unwrap()))]),
        BTreeMap::new(),
        true,
    )
    .unwrap();
    assert_eq!(
        check_attachment(&plan, &toolbar, |staged| {
            assert_eq!(fs::read(staged.join("main.js")).unwrap(), b"fixture");
            fs::write(&source, b"changed").unwrap();
            Ok(())
        }),
        Err(IntegrationError::Changed)
    );
    assert!(!target.exists());
}
