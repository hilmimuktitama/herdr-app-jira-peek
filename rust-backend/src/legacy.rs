//! Guarded cleanup for state created by the shell runtime.
use crate::{
    fail,
    storage::{read, remove, symlink},
    Result,
};
use std::{
    fs,
    path::{Path, PathBuf},
};

fn entries(path: &Path) -> Result<Vec<fs::DirEntry>> {
    match fs::symlink_metadata(path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(vec![]),
        Ok(m) if m.is_dir() => (),
        _ => return Err(fail("connection_failed")),
    }
    Ok(fs::read_dir(path)?.collect::<std::io::Result<Vec<_>>>()?)
}
fn dead_owner(name: &str) -> bool {
    let Some((stem, suffix)) = name.rsplit_once('.') else {
        return false;
    };
    if suffix.is_empty() {
        return false;
    }
    let Some((_, pid)) = stem.rsplit_once('.') else {
        return false;
    };
    let Some(pid) = pid.parse::<i32>().ok().filter(|p| *p > 0) else {
        return false;
    };
    // EPERM means a live process we cannot signal; never reap it.
    (unsafe { libc::kill(pid, 0) }) != 0
        && std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH)
}
fn temporary(name: &str) -> bool {
    [
        ".identity.",
        ".twg-json.",
        ".twg-stderr.",
        ".twg-normalized.",
        ".twg-error.",
        ".issue-",
        ".connection-owner.",
        ".connection.",
        ".site-context.",
    ]
    .iter()
    .any(|prefix| name.starts_with(prefix))
}
fn diagnostics(parent: &Path) -> Result<()> {
    const MESSAGES: &[&str] = &[
        "TWG request failed\n", "TWG is not authenticated or configured; run twg setup, then retry\n",
        "Jira request failed\n", "TWG CLI unavailable; install the official Atlassian TWG CLI, ensure it is on PATH, then run twg setup\n",
        "curl is unavailable; install curl and retry\n", "Jira authentication failed (HTTP 401)\n",
        "Access to this Jira operation was denied (HTTP 403)\n", "Jira issue or endpoint was not found (HTTP 404)\n",
        "Jira rate limit reached (HTTP 429)\n", "Jira response was not valid issue JSON\n",
    ];
    for entry in entries(&parent.join("fetch-errors"))? {
        if !entry.file_type()?.is_file() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with(".fetch-error-") && dead_owner(&name) {
            remove(&entry.path())?;
        } else if name.starts_with("fetch-error-") {
            let bytes = read(&entry.path())?;
            if !MESSAGES.iter().any(|s| s.as_bytes() == bytes) {
                remove(&entry.path())?;
            }
        }
    }
    Ok(())
}
pub fn initialize(state: &Path) -> Result<()> {
    for entry in entries(state)? {
        let name = entry.file_name().to_string_lossy().into_owned();
        let kind = entry.file_type()?;
        if kind.is_file() && temporary(&name) && dead_owner(&name) {
            remove(&entry.path())?;
        } else if kind.is_dir()
            && (name.starts_with(".rest-fetch.") || name.starts_with(".rest-metadata."))
            && dead_owner(&name)
        {
            // std removes directory symlinks themselves, never their targets.
            fs::remove_dir_all(entry.path())?;
        } else if name.starts_with("session-") {
            if !kind.is_dir() {
                return Err(fail("connection_failed"));
            }
            diagnostics(&entry.path())?;
        }
    }
    diagnostics(state)?;
    let lock = state.join(".connection-lock");
    for entry in entries(&lock)? {
        let name = entry.file_name().to_string_lossy().into_owned();
        if entry.file_type()?.is_file()
            && name.starts_with(".connection-owner.")
            && dead_owner(&name)
        {
            remove(&entry.path())?;
            // Keep any other owner/unknown entries; only remove an empty lock.
            let _ = fs::remove_dir(&lock);
        }
    }
    Ok(())
}
fn source_dirs(parent: &Path) -> Result<Vec<PathBuf>> {
    let sources = parent.join("sources");
    if symlink(&sources) {
        return Ok(vec![]);
    }
    Ok(entries(&sources)?
        .into_iter()
        .filter(|e| {
            e.file_type().is_ok_and(|t| t.is_dir())
                && e.file_name().to_string_lossy().starts_with("source-")
        })
        .map(|e| e.path())
        .collect())
}
pub fn retire_keys(state: &Path) -> Result<()> {
    let mut dirs = vec![state.to_path_buf()];
    dirs.extend(source_dirs(state)?);
    for entry in entries(state)? {
        if entry.file_type()?.is_dir()
            && entry.file_name().to_string_lossy().starts_with("session-")
        {
            dirs.extend(source_dirs(&entry.path())?);
            dirs.push(entry.path());
        }
    }
    for dir in dirs {
        for name in ["key", "candidates"] {
            let p = dir.join(name);
            if fs::symlink_metadata(&p).is_ok_and(|m| m.is_file()) {
                remove(&p)?;
            }
        }
    }
    Ok(())
}
