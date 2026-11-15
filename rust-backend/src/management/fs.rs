//! Filesystem guards shared by lifecycle operations. Errors never contain paths.
use crate::{fail, Result};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    os::unix::fs::{MetadataExt, OpenOptionsExt},
    path::{Component, Path},
};

pub fn safe_path(path: &Path) -> Result<()> {
    if !path.is_absolute()
        || path.parent().is_none()
        || path
            .components()
            .any(|c| matches!(c, Component::ParentDir | Component::CurDir))
    {
        return Err(fail("unsafe_management_path"));
    }
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(m) if m.file_type().is_symlink() => return Err(fail("unsafe_management_path")),
            Ok(_) => (),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(_) => return Err(fail("unsafe_management_path")),
        }
    }
    Ok(())
}

pub fn read_regular(path: &Path, limit: u64) -> Result<Vec<u8>> {
    safe_path(path)?;
    let file = fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.nlink() != 1 || metadata.len() > limit {
        return Err(fail("unsafe_management_file"));
    }
    let mut bytes = Vec::new();
    file.take(limit + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > limit {
        return Err(fail("management_file_too_large"));
    }
    Ok(bytes)
}

pub fn digest(path: &Path) -> Result<String> {
    Ok(format!(
        "{:x}",
        Sha256::digest(read_regular(path, 32 * 1024 * 1024)?)
    ))
}

/// Advisory lock compatible with the historical Python installer. The lock
/// inode remains in place; closing the descriptor releases a crashed process.
pub struct InstallLock(std::fs::File);
impl InstallLock {
    pub fn acquire(mods: &Path) -> Result<Self> {
        safe_path(mods)?;
        if !mods.is_dir() {
            return Err(fail("missing_mods_directory"));
        }
        let path = mods.join(".jira-peek-install.lock");
        safe_path(&path)?;
        let file = fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(path)?;
        let metadata = file.metadata()?;
        if !metadata.is_file() || metadata.nlink() != 1 {
            return Err(fail("unsafe_install_lock"));
        }
        use std::os::fd::AsRawFd;
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err(fail("installation_in_progress"));
        }
        Ok(Self(file))
    }
}
impl Drop for InstallLock {
    fn drop(&mut self) {
        use std::os::fd::AsRawFd;
        unsafe {
            libc::flock(self.0.as_raw_fd(), libc::LOCK_UN);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn guards_links_bounds_and_lock_contention() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().canonicalize().unwrap();
        let file = root.join("file");
        fs::write(&file, b"fixture").unwrap();
        assert!(read_regular(&file, 3).is_err());
        let link = root.join("link");
        std::os::unix::fs::symlink(&file, &link).unwrap();
        assert!(read_regular(&link, 20).is_err());
        fs::remove_file(&link).unwrap();
        fs::hard_link(&file, &link).unwrap();
        assert!(read_regular(&file, 20).is_err());
        let lock = InstallLock::acquire(&root).unwrap();
        assert!(InstallLock::acquire(&root).is_err());
        drop(lock);
        assert!(InstallLock::acquire(&root).is_ok());
        assert!(safe_path(Path::new("/")).is_err());
        assert!(safe_path(&root.join("../escape")).is_err());
    }
}
