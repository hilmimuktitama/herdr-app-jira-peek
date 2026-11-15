//! Integration transaction primitives. The caller must hold the lifecycle lock.
//! No function selects a layout or establishes that a control rendered.
use std::{
    collections::BTreeMap,
    fmt,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt},
    path::{Component, Path, PathBuf},
};
const FILE_LIMIT: u64 = 4 * 1024 * 1024;
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IntegrationError {
    UnsafePath,
    InvalidFile,
    Changed,
    Conflict,
    Limit,
    Io,
    NativeCheck,
}
impl fmt::Display for IntegrationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::UnsafePath => "Unsafe integration path; files were preserved",
            Self::InvalidFile => "Invalid integration file",
            Self::Changed => "Integration inputs changed; review personal files and retry repair",
            Self::Conflict => "Personal integration differs; conflicting files were preserved",
            Self::Limit => "Integration exceeds automatic integration limits",
            Self::Io => "Integration filesystem operation failed; integration may be incomplete",
            Self::NativeCheck => "Native toolbar check failed; integration was not published",
        })
    }
}
impl std::error::Error for IntegrationError {}
impl From<std::io::Error> for IntegrationError {
    fn from(_: std::io::Error) -> Self {
        Self::Io
    }
}
type Result<T> = std::result::Result<T, IntegrationError>;
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Snapshot {
    identity: (u64, u64, u32, u32, u64, i64, i64),
    pub bytes: Vec<u8>,
}
fn identity(m: &fs::Metadata) -> (u64, u64, u32, u32, u64, i64, i64) {
    (
        m.dev(),
        m.ino(),
        m.mode(),
        m.uid(),
        m.size(),
        m.mtime(),
        m.mtime_nsec(),
    )
}
pub fn safe_path(path: &Path) -> Result<()> {
    if !path.is_absolute()
        || path.parent().is_none()
        || path
            .components()
            .any(|c| matches!(c, Component::ParentDir | Component::CurDir))
    {
        return Err(IntegrationError::UnsafePath);
    }
    for p in path.ancestors() {
        match fs::symlink_metadata(p) {
            Ok(m) if m.file_type().is_symlink() => return Err(IntegrationError::UnsafePath),
            Ok(_) => (),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(_) => return Err(IntegrationError::Io),
        }
    }
    Ok(())
}
pub fn integration_snapshot(path: &Path) -> Result<Snapshot> {
    safe_path(path)?;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let before = file.metadata()?;
    if !before.is_file() {
        return Err(IntegrationError::InvalidFile);
    }
    if before.len() > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    let mut bytes = Vec::new();
    (&file).take(FILE_LIMIT + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    let after = file.metadata()?;
    safe_path(path)?;
    if identity(&before) != identity(&after)
        || identity(&after) != identity(&fs::symlink_metadata(path)?)
    {
        return Err(IntegrationError::Changed);
    }
    Ok(Snapshot {
        identity: identity(&after),
        bytes,
    })
}
fn optional_snapshot(path: &Path) -> Result<Option<Snapshot>> {
    safe_path(path)?;
    match fs::symlink_metadata(path) {
        Ok(_) => integration_snapshot(path).map(Some),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(_) => Err(IntegrationError::Io),
    }
}
pub fn toolbar_files(root: &Path) -> Result<Vec<PathBuf>> {
    safe_path(root)?;
    let mut pending = vec![(root.to_path_buf(), 0)];
    let mut files = Vec::new();
    let mut entries = 0;
    while let Some((dir, depth)) = pending.pop() {
        if depth > 64 {
            return Err(IntegrationError::Limit);
        }
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            safe_path(&path)?;
            entries += 1;
            if entries > 4096 {
                return Err(IntegrationError::Limit);
            }
            let m = fs::symlink_metadata(&path)?;
            if m.is_dir() {
                pending.push((path, depth + 1));
            } else if m.is_file() {
                if matches!(
                    path.strip_prefix(root).ok().and_then(Path::to_str),
                    Some("gpui-kit.d.ts" | "jsconfig.json")
                ) {
                    continue;
                }
                files.push(path);
                if files.len() > 256 {
                    return Err(IntegrationError::Limit);
                }
            } else {
                return Err(IntegrationError::InvalidFile);
            }
        }
    }
    files.sort();
    Ok(files)
}
/// Opaque captured transaction; construction validates paths and total size.
#[derive(Debug)]
pub struct AttachmentPlan {
    pub name: String,
    home: PathBuf,
    files: BTreeMap<PathBuf, Vec<u8>>,
    inputs: BTreeMap<PathBuf, Option<Snapshot>>,
    directories: BTreeMap<PathBuf, Vec<PathBuf>>,
}
impl AttachmentPlan {
    /// Capture after a planner has computed bytes. Source snapshots must be those
    /// used by the planner, not fresh reads taken after transformation.
    pub fn from_parts(
        name: String,
        home: PathBuf,
        files: BTreeMap<PathBuf, Vec<u8>>,
        inputs: BTreeMap<PathBuf, Option<Snapshot>>,
        directories: BTreeMap<PathBuf, Vec<PathBuf>>,
        check_conflicts: bool,
    ) -> Result<Self> {
        safe_path(&home)?;
        if name.is_empty()
            || name.len() > 100
            || !name
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_-".contains(&c))
        {
            return Err(IntegrationError::UnsafePath);
        }
        let plan = Self {
            name,
            home,
            files,
            inputs,
            directories,
        };
        let mut size = 0usize;
        for (path, bytes) in &plan.files {
            safe_path(path)?;
            if !path.starts_with(&plan.home) || path == &plan.home {
                return Err(IntegrationError::UnsafePath);
            }
            if bytes.len() as u64 > FILE_LIMIT {
                return Err(IntegrationError::Limit);
            }
            size = size
                .checked_add(bytes.len())
                .ok_or(IntegrationError::Limit)?;
            if check_conflicts && optional_snapshot(path)?.is_some_and(|s| s.bytes != *bytes) {
                return Err(IntegrationError::Conflict);
            }
        }
        if size > 16 * 1024 * 1024 || plan.files.len() > 258 {
            return Err(IntegrationError::Limit);
        }
        validate_attachment(&plan)?;
        Ok(plan)
    }
    pub fn files(&self) -> &BTreeMap<PathBuf, Vec<u8>> {
        &self.files
    }
}
pub fn validate_attachment(plan: &AttachmentPlan) -> Result<()> {
    for (path, expected) in &plan.inputs {
        if optional_snapshot(path)?.as_ref() != expected.as_ref() {
            return Err(IntegrationError::Changed);
        }
    }
    for (dir, expected) in &plan.directories {
        if toolbar_files(dir)? != *expected {
            return Err(IntegrationError::Changed);
        }
    }
    Ok(())
}
fn publish(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(existing) = optional_snapshot(path)? {
        return if existing.bytes == bytes {
            Ok(())
        } else {
            Err(IntegrationError::Conflict)
        };
    }
    let parent = path.parent().ok_or(IntegrationError::UnsafePath)?;
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(parent)?;
    safe_path(path)?;
    let mut staged = tempfile::Builder::new()
        .prefix(".jira-peek-attach-")
        .suffix(".tmp")
        .tempfile_in(parent)?;
    staged.write_all(bytes)?;
    staged.as_file().sync_all()?;
    safe_path(path)?;
    match fs::hard_link(staged.path(), path) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
            if integration_snapshot(path)?.bytes != bytes {
                return Err(IntegrationError::Conflict);
            }
        }
        Err(_) => return Err(IntegrationError::Io),
    }
    File::open(parent)?.sync_all()?;
    Ok(())
}
/// Partial completion is retained on failure; retry is idempotent. Never undo
/// published files, which may already be referenced or edited by the user.
pub fn apply_attachment(plan: &AttachmentPlan, app_home: &Path) -> Result<()> {
    if app_home != plan.home {
        return Err(IntegrationError::UnsafePath);
    }
    validate_attachment(plan)?;
    for (path, bytes) in &plan.files {
        validate_attachment(plan)?;
        publish(path, bytes)?;
    }
    validate_attachment(plan)?;
    for (path, bytes) in &plan.files {
        if integration_snapshot(path)?.bytes != *bytes {
            return Err(IntegrationError::Changed);
        }
    }
    Ok(())
}
/// Stage only the generated toolbar. The lifecycle core supplies its isolated,
/// version-checked native checker (herdr-app >= 0.1.10; hc is separate).
pub fn check_attachment<F>(plan: &AttachmentPlan, toolbar: &Path, checker: F) -> Result<()>
where
    F: FnOnce(&Path) -> Result<()>,
{
    validate_attachment(plan)?;
    if !toolbar.starts_with(plan.home.join("mods")) {
        return Err(IntegrationError::UnsafePath);
    }
    let staged = tempfile::Builder::new()
        .prefix("jira-peek-toolbar-")
        .tempdir()?;
    let mut count = 0;
    for (path, bytes) in &plan.files {
        if let Ok(relative) = path.strip_prefix(toolbar) {
            let target = staged.path().join(relative);
            fs::create_dir_all(target.parent().ok_or(IntegrationError::UnsafePath)?)?;
            fs::write(target, bytes)?;
            count += 1;
        }
    }
    if count == 0 {
        return Err(IntegrationError::InvalidFile);
    }
    checker(staged.path()).map_err(|_| IntegrationError::NativeCheck)?;
    validate_attachment(plan)
}
