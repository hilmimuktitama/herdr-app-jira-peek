use crate::{fail, Result};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::{
        fd::{AsRawFd, FromRawFd},
        unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    },
    path::{Path, PathBuf},
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
pub fn hash(b: &[u8]) -> String {
    format!("{:x}", Sha256::digest(b))
}
pub fn symlink(p: &Path) -> bool {
    fs::symlink_metadata(p).is_ok_and(|m| m.file_type().is_symlink())
}
pub fn read(p: &Path) -> Result<Vec<u8>> {
    let f = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(p)
        .map_err(|_| fail("request_failed"))?;
    read_file(f)
}
fn read_file(f: File) -> Result<Vec<u8>> {
    if !f.metadata()?.is_file() {
        return Err(fail("request_failed"));
    }
    let mut b = vec![];
    f.take(64 * 1024 * 1024 + 1).read_to_end(&mut b)?;
    if b.len() > 64 * 1024 * 1024 {
        return Err(fail("request_failed"));
    }
    Ok(b)
}
// Keep reads anchored to the directory that supplied the connection namespace.
// Checking both sides of each read also rejects a renamed/replaced path.
pub struct ConfigDirectory {
    path: PathBuf,
    dir: File,
    pub device: u64,
    pub inode: u64,
}
impl ConfigDirectory {
    pub fn open(path: &Path) -> Result<Self> {
        let dir = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW)
            .open(path)?;
        let meta = dir.metadata()?;
        let value = Self {
            path: path.into(),
            dir,
            device: meta.dev(),
            inode: meta.ino(),
        };
        value.check()?;
        Ok(value)
    }
    fn check(&self) -> Result<()> {
        let m = fs::symlink_metadata(&self.path).map_err(|_| fail("connection_changed"))?;
        if !m.is_dir() || m.dev() != self.device || m.ino() != self.inode {
            return Err(fail("connection_changed"));
        }
        Ok(())
    }
    pub fn read(&self) -> Result<Vec<u8>> {
        self.check()?;
        let fd = unsafe {
            libc::openat(
                self.dir.as_raw_fd(),
                c"config.sh".as_ptr(),
                libc::O_RDONLY | libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(fail("connection_changed"));
        }
        let data = read_file(unsafe { File::from_raw_fd(fd) })?;
        self.check()?;
        Ok(data)
    }
}
pub fn private(p: &Path) -> Result<()> {
    if symlink(p) {
        return Err(fail("invalid_request"));
    }
    fs::create_dir_all(p)?;
    fs::set_permissions(p, fs::Permissions::from_mode(0o700))?;
    Ok(())
}
pub fn atomic(p: &Path, b: &[u8]) -> Result<()> {
    if symlink(p) {
        return Err(fail("request_failed"));
    }
    let mut f = tempfile::Builder::new()
        .prefix(&format!(".issue-rust.{}.", std::process::id()))
        .tempfile_in(p.parent().ok_or(fail("request_failed"))?)?;
    f.write_all(b)?;
    f.persist(p).map_err(|_| fail("request_failed"))?;
    Ok(())
}
pub fn marker(state: &Path) -> Result<(String, String)> {
    let p = state.join("connection-context");
    if symlink(&p) {
        return Err(fail("connection_changed"));
    }
    if !p.exists() {
        return Ok((String::new(), String::new()));
    }
    let b = read(&p)?;
    let s = String::from_utf8(b).map_err(|_| fail("connection_changed"))?;
    let mut lines = s.split('\n');
    Ok((
        lines.next().unwrap_or("").into(),
        lines.next().unwrap_or("").into(),
    ))
}
pub fn epoch(state: &Path, id: &str) -> Result<String> {
    let f = tempfile::Builder::new()
        .prefix(&format!(".connection.{}.", std::process::id()))
        .tempfile_in(state)?;
    let name = f.path().file_name().unwrap().to_string_lossy().into_owned();
    atomic(
        &state.join("connection-context"),
        format!("{id}\n{name}\n").as_bytes(),
    )?;
    Ok(name)
}
pub fn purge(cache: &Path, ttl: u64) -> Result<()> {
    if symlink(cache) {
        return Err(fail("request_failed"));
    }
    if !cache.exists() {
        return Ok(());
    }
    for e in fs::read_dir(cache)? {
        let e = e?;
        let m = e.metadata()?;
        if e.file_type()?.is_file()
            && (ttl == 0
                || m.modified()?.elapsed().unwrap_or_default().as_secs() >= ttl.saturating_mul(60))
        {
            fs::remove_file(e.path())?;
        }
    }
    Ok(())
}
pub fn generation(p: &Path) -> Result<u64> {
    if symlink(p) {
        return Err(fail("request_failed"));
    }
    if !p.exists() {
        return Ok(0);
    }
    let b = read(p)?;
    let s = String::from_utf8(b).map_err(|_| fail("request_failed"))?;
    let n = s.strip_suffix('\n').ok_or(fail("request_failed"))?;
    if n.is_empty() || !n.bytes().all(|x| x.is_ascii_digit()) {
        return Err(fail("request_failed"));
    }
    n.parse().map_err(|_| fail("request_failed"))
}
pub fn increment(p: &Path) -> Result<u64> {
    let n = generation(p)?
        .checked_add(1)
        .ok_or(fail("request_failed"))?;
    atomic(p, format!("{n}\n").as_bytes())?;
    Ok(n)
}
pub fn remove(p: &Path) -> Result<()> {
    match fs::remove_file(p) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e.into()),
    }
}
pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
pub fn mtime(p: &Path) -> Result<u64> {
    Ok(fs::metadata(p)?
        .modified()?
        .duration_since(UNIX_EPOCH)
        .map_err(|_| fail("request_failed"))?
        .as_millis() as u64)
}
pub struct Lock {
    dir: PathBuf,
    owner: PathBuf,
}
impl Lock {
    pub fn take(dir: &Path, connection: bool) -> Result<Self> {
        if symlink(dir) {
            return Err(fail("request_failed"));
        }
        let prefix = if connection {
            ".connection-owner."
        } else {
            ".owner."
        };
        let owner = tempfile::Builder::new()
            .prefix(&format!("{prefix}{}.", std::process::id()))
            .tempfile_in(dir.parent().ok_or(fail("request_failed"))?)?;
        for _ in 0..1000 {
            match fs::create_dir(dir) {
                Ok(()) => {
                    let path = dir.join(owner.path().file_name().unwrap());
                    owner.persist(&path).map_err(|_| fail("request_failed"))?;
                    return Ok(Self {
                        dir: dir.into(),
                        owner: path,
                    });
                }
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {}
                Err(e) => return Err(e.into()),
            }
            if symlink(dir) {
                return Err(fail("request_failed"));
            }
            if let Ok(entries) = fs::read_dir(dir) {
                for e in entries.flatten() {
                    let name = e.file_name().to_string_lossy().into_owned();
                    if !e.file_type().is_ok_and(|t| t.is_file()) {
                        continue;
                    }
                    if let Some(rest) = name.strip_prefix(prefix) {
                        if let Some(pid) = rest
                            .split('.')
                            .next()
                            .and_then(|x| x.parse::<i32>().ok())
                            .filter(|p| *p > 0)
                        {
                            let dead = unsafe { libc::kill(pid, 0) } != 0
                                && std::io::Error::last_os_error().raw_os_error()
                                    == Some(libc::ESRCH);
                            if dead {
                                let _ = fs::remove_file(e.path());
                                let _ = fs::remove_dir(dir);
                            }
                        }
                    }
                }
            }
            if fs::metadata(dir)
                .and_then(|m| m.modified())
                .is_ok_and(|m| m.elapsed().unwrap_or_default() > Duration::from_secs(120))
            {
                let _ = fs::remove_dir(dir);
            }
            thread::sleep(Duration::from_millis(10));
        }
        Err(fail("request_failed"))
    }
}
impl Drop for Lock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.owner);
        let _ = fs::remove_dir(&self.dir);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;
    #[test]
    fn literal_marker_and_symlink_rejection() {
        let dir = tempfile::tempdir().unwrap();
        assert_eq!(marker(dir.path()).unwrap(), ("".into(), "".into()));
        let p = dir.path().join("connection-context");
        atomic(&p, b" first\\literal \n second\\literal \nignored\n").unwrap();
        assert_eq!(
            marker(dir.path()).unwrap(),
            (" first\\literal ".into(), " second\\literal ".into())
        );
        fs::rename(&p, dir.path().join("outside")).unwrap();
        symlink(dir.path().join("outside"), &p).unwrap();
        assert!(marker(dir.path()).is_err());
    }
    #[test]
    fn generation_is_exact_and_lock_recovers_dead_owner() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("ABC-1");
        assert_eq!(increment(&p).unwrap(), 1);
        atomic(&p, b"2\nextra").unwrap();
        assert!(increment(&p).is_err());
        let lock = dir.path().join(".ABC-1.lock");
        fs::create_dir(&lock).unwrap();
        fs::write(lock.join(".owner.999999999.fixture"), b"").unwrap();
        {
            let _guard = Lock::take(&lock, false).unwrap();
            assert!(lock.is_dir());
        }
        assert!(!lock.exists());
    }
    #[test]
    fn purge_never_follows_links_or_nested_directories() {
        let dir = tempfile::tempdir().unwrap();
        let cache = dir.path().join("cache");
        private(&cache).unwrap();
        let external = dir.path().join("keep");
        fs::write(&external, b"fictional").unwrap();
        symlink(&external, cache.join("linked")).unwrap();
        fs::create_dir(cache.join("nested")).unwrap();
        fs::write(cache.join("nested/keep"), b"fictional").unwrap();
        fs::write(cache.join(".payload"), b"fictional").unwrap();
        purge(&cache, 0).unwrap();
        assert_eq!(read(&external).unwrap(), b"fictional");
        assert!(cache.join("nested/keep").exists());
        assert!(cache.join("linked").is_symlink());
        assert!(!cache.join(".payload").exists());
    }
}
