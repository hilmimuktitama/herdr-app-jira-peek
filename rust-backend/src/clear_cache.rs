//! Local maintenance for one initialized connection namespace, never a state root.
use crate::storage;
use std::{
    fs,
    os::unix::fs::MetadataExt,
    path::{Component, Path},
};

const UNSAFE: &str = "refusing an unsafe connection state directory";
const ROOT: &str = "select a connection state directory, or use the native Clear cache action";
const UNINITIALIZED: &str =
    "connection state is not initialized; use the native Clear cache action";

#[derive(Debug, PartialEq)]
pub struct Cleared {
    pub removed: usize,
    pub cache_existed: bool,
}

// Permit only the conventional system aliases also accepted by setup. Do not
// follow a user-created ancestor symlink to a different state namespace.
fn checked_path(path: &Path) -> std::result::Result<(), &'static str> {
    if !path.is_absolute()
        || path == Path::new("/")
        || path
            .components()
            .any(|part| matches!(part, Component::ParentDir))
    {
        return Err(UNSAFE);
    }
    let mut prefix = std::path::PathBuf::new();
    for part in path.components() {
        prefix.push(part);
        match fs::symlink_metadata(&prefix) {
            Ok(meta) => {
                let system_alias =
                    prefix != path && matches!(prefix.to_str(), Some("/tmp" | "/var" | "/private"));
                if !(meta.is_dir() || system_alias && meta.file_type().is_symlink()) {
                    return Err(UNSAFE);
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => return Err(UNSAFE),
        }
    }
    Ok(())
}

fn validate_namespace(state: &Path) -> std::result::Result<bool, &'static str> {
    match fs::symlink_metadata(state.join("connections")) {
        Ok(_) => return Err(ROOT),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err(UNSAFE),
    }
    match fs::symlink_metadata(state.join("cache")) {
        Ok(meta) if meta.is_dir() => Ok(true),
        Ok(_) => Err("cache path must be a directory, not a file or symlink"),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err("could not inspect the issue cache"),
    }
}

pub fn clear(state: &Path) -> std::result::Result<Cleared, &'static str> {
    checked_path(state)?;
    let initial = match fs::symlink_metadata(state) {
        Ok(meta) if meta.is_dir() => meta,
        Ok(_) => return Err(UNSAFE),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Cleared {
                removed: 0,
                cache_existed: false,
            });
        }
        Err(_) => return Err(UNSAFE),
    };
    validate_namespace(state)?;
    let _lock = storage::Lock::take(&state.join(".connection-lock"), true)
        .map_err(|_| "connection state is busy or unsafe")?;
    checked_path(state)?;
    let current = fs::symlink_metadata(state).map_err(|_| UNSAFE)?;
    if current.dev() != initial.dev() || current.ino() != initial.ino() {
        return Err(UNSAFE);
    }
    let cache_existed = validate_namespace(state)?;
    let (id, previous_epoch) = storage::marker(state).map_err(|_| UNINITIALIZED)?;
    if id.is_empty() || previous_epoch.is_empty() {
        return Err(UNINITIALIZED);
    }
    // Advance even with no cache directory: a pending first read must become
    // stale before it can publish. Use the same lock/marker format as readers.
    storage::epoch(state, &id).map_err(|_| "could not invalidate the connection cache")?;
    let mut removed = 0;
    if cache_existed {
        let cache = state.join("cache");
        validate_namespace(state)?;
        for entry in fs::read_dir(cache).map_err(|_| "could not read the issue cache")? {
            let entry = entry.map_err(|_| "could not read an issue-cache entry")?;
            if entry
                .file_type()
                .map_err(|_| "could not inspect an issue-cache entry")?
                .is_file()
            {
                fs::remove_file(entry.path())
                    .map_err(|_| "could not remove an issue-cache file")?;
                removed += 1;
            }
        }
    }
    Ok(Cleared {
        removed,
        cache_existed,
    })
}

pub fn run(args: &[String]) -> i32 {
    let result = if args.len() == 2 && args[0] == "--state-dir" {
        clear(Path::new(&args[1]))
    } else {
        Err("usage: jira-peek-bridge manage clear-cache --state-dir ABSOLUTE_CONNECTION_DIRECTORY")
    };
    match result {
        Ok(result) => {
            if result.cache_existed {
                println!(
                    "Peek for Jira: cleared {} issue-cache file(s); other plugin state was kept.",
                    result.removed
                );
            } else {
                println!("Peek for Jira: issue cache is already empty.");
            }
            0
        }
        Err(message) => {
            eprintln!("Peek for Jira: {message}.");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;

    fn initialized() -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join("connection-context"),
            b"fictional-id\nprevious-epoch\n",
        )
        .unwrap();
        dir
    }

    #[test]
    fn clear_is_nonrecursive_and_preserves_identity_and_other_state() {
        let dir = initialized();
        let state = dir.path();
        fs::create_dir(state.join("cache")).unwrap();
        fs::create_dir(state.join("cache/nested")).unwrap();
        fs::write(state.join("cache/nested/keep"), b"fictional").unwrap();
        fs::write(state.join("cache/ABC-1.json"), b"fictional").unwrap();
        fs::write(state.join("cache/.fetch.fixture"), b"fictional").unwrap();
        fs::write(state.join("diagnostic"), b"fictional").unwrap();
        symlink(state.join("diagnostic"), state.join("cache/link")).unwrap();
        symlink(state.join("missing"), state.join("cache/broken")).unwrap();
        let result = clear(state).unwrap();
        assert_eq!(result.removed, 2);
        assert_eq!(fs::read(state.join("diagnostic")).unwrap(), b"fictional");
        assert!(state.join("cache/nested/keep").exists());
        assert!(state.join("cache/link").is_symlink());
        assert!(state.join("cache/broken").is_symlink());
        let marker = storage::marker(state).unwrap();
        assert_eq!(marker.0, "fictional-id");
        assert_ne!(marker.1, "previous-epoch");
        assert!(!state.join(".connection-lock").exists());
    }

    #[test]
    fn no_cache_still_retires_pending_requests_without_creating_cache() {
        let dir = initialized();
        assert!(!clear(dir.path()).unwrap().cache_existed);
        assert_ne!(storage::marker(dir.path()).unwrap().1, "previous-epoch");
        assert!(!dir.path().join("cache").exists());
    }

    #[test]
    fn shared_root_and_uninitialized_state_are_rejected_without_invalidation() {
        let dir = initialized();
        fs::create_dir(dir.path().join("connections")).unwrap();
        assert_eq!(clear(dir.path()), Err(ROOT));
        assert_eq!(storage::marker(dir.path()).unwrap().1, "previous-epoch");
        fs::remove_dir(dir.path().join("connections")).unwrap();
        fs::remove_file(dir.path().join("connection-context")).unwrap();
        assert_eq!(clear(dir.path()), Err(UNINITIALIZED));
        assert!(!dir.path().join("connection-context").exists());
        assert!(!dir.path().join(".connection-lock").exists());
    }

    #[test]
    fn unsafe_paths_and_cache_shapes_never_change_the_marker() {
        for kind in ["file", "symlink", "marker", "root-link", "ancestor-link"] {
            let dir = initialized();
            let outside = tempfile::tempdir().unwrap();
            let state = match kind {
                "file" => {
                    fs::write(dir.path().join("cache"), b"fixture").unwrap();
                    dir.path().to_path_buf()
                }
                "symlink" => {
                    symlink(outside.path(), dir.path().join("cache")).unwrap();
                    dir.path().to_path_buf()
                }
                "marker" => {
                    fs::rename(
                        dir.path().join("connection-context"),
                        outside.path().join("keep"),
                    )
                    .unwrap();
                    symlink(
                        outside.path().join("keep"),
                        dir.path().join("connection-context"),
                    )
                    .unwrap();
                    dir.path().to_path_buf()
                }
                "root-link" => {
                    symlink(dir.path(), outside.path().join("link")).unwrap();
                    outside.path().join("link")
                }
                _ => {
                    fs::create_dir(dir.path().join("child")).unwrap();
                    symlink(dir.path(), outside.path().join("link")).unwrap();
                    outside.path().join("link/child")
                }
            };
            assert!(clear(&state).is_err(), "{kind}");
            assert_eq!(
                fs::read(dir.path().join("connection-context")).unwrap(),
                b"fictional-id\nprevious-epoch\n"
            );
        }
        for path in ["/", "relative", "/tmp/../tmp"] {
            assert!(clear(Path::new(path)).is_err());
        }
    }

    #[test]
    fn missing_state_is_read_only_and_publication_lock_is_shared() {
        let dir = initialized();
        let missing = dir.path().join("missing");
        assert!(!clear(&missing).unwrap().cache_existed);
        assert!(!missing.exists());
        let lock = storage::Lock::take(&dir.path().join(".connection-lock"), true).unwrap();
        let state = dir.path().to_path_buf();
        let (sent, received) = std::sync::mpsc::channel();
        let worker = std::thread::spawn(move || {
            sent.send(clear(&state)).unwrap();
        });
        assert!(received
            .recv_timeout(std::time::Duration::from_millis(30))
            .is_err());
        assert_eq!(storage::marker(dir.path()).unwrap().1, "previous-epoch");
        drop(lock);
        assert!(received
            .recv_timeout(std::time::Duration::from_secs(2))
            .unwrap()
            .is_ok());
        worker.join().unwrap();
        assert_ne!(storage::marker(dir.path()).unwrap().1, "previous-epoch");
    }
}
