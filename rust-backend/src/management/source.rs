//! Explicit immutable historical source profiles. Missing current files never
//! select legacy mode; supporting another release requires a reviewed profile.
use super::{fs::digest, manifest};
use crate::{fail, Result};
use std::{
    collections::BTreeSet,
    path::{Path, PathBuf},
};
pub fn source_path(root: &Path, name: &str) -> PathBuf {
    if let Some(n) = name.strip_prefix("runtime/") {
        root.join("scripts").join(n)
    } else if name == "AGENTS.md" {
        root.join("docs/AGENT-GUIDE.md")
    } else if name == "LICENSE" {
        root.join(name)
    } else {
        root.join("mods/jira-peek").join(name)
    }
}
pub fn historical(root: &Path, version: &str) -> Result<Option<BTreeSet<String>>> {
    if version != "0.9.1" {
        return Ok(None);
    }
    let mut files = BTreeSet::new();
    for line in include_str!("source-v0.9.1.txt").lines() {
        let (expected, name) = line
            .split_once(' ')
            .ok_or_else(|| fail("invalid_frozen_source_profile"))?;
        let path = if let Some(n) = name.strip_prefix('@') {
            root.join(n)
        } else {
            source_path(root, name)
        };
        if digest(&path)? != expected {
            return Err(fail("historical_source_identity_mismatch"));
        }
        if !name.starts_with('@') {
            files.insert(name.to_string());
        }
    }
    // Reject mixed distributions, rather than treating damaged Rust sources as legacy.
    for name in [
        "rust-backend",
        ".release-runtime",
        "scripts/runtime-bundle.py",
    ] {
        match std::fs::symlink_metadata(root.join(name)) {
            Ok(_) => return Err(fail("mixed_historical_source")),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(_) => return Err(fail("unsafe_historical_source")),
        }
    }
    let actual: BTreeSet<_> = manifest::walk(&root.join("mods/jira-peek"))?
        .into_iter()
        .filter(|s| !s.ends_with('/'))
        .collect();
    let expected: BTreeSet<_> = files
        .iter()
        .filter(|s| !s.starts_with("runtime/") && *s != "AGENTS.md" && *s != "LICENSE")
        .cloned()
        .collect();
    if actual != expected {
        return Err(fail("historical_source_inventory_mismatch"));
    }
    Ok(Some(files))
}

/// Use frozen hashes in install.json as well, so edits between source validation
/// and copying cannot turn into a newly trusted historical bundle.
pub fn historical_hash(name: &str) -> Result<&'static str> {
    include_str!("source-v0.9.1.txt")
        .lines()
        .filter_map(|line| line.split_once(' '))
        .find(|(_, file)| *file == name)
        .map(|(hash, _)| hash)
        .ok_or_else(|| fail("invalid_frozen_source_profile"))
}
