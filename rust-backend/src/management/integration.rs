//! Conservative personal layout/toolbar integration. Mutations require the lifecycle lock.
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
/// Public fallback for installations that predate the bundled integration guide.
pub const MANUAL_INTEGRATION_URL: &str = "https://github.com/hilmimuktitama/herdr-app-jira-peek/blob/main/docs/PANEL-INTEGRATION.md#manual-integration";
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IntegrationError {
    UnsafePath,
    InvalidFile,
    Changed,
    Conflict,
    Limit,
    Io,
    NativeCheck,
    InvalidJson,
    DuplicateKey,
    InvalidLayout,
    UnsupportedToolbar,
    ToolbarIdentity,
    InvalidShortcuts,
    BundleChanged,
}
impl fmt::Display for IntegrationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::InvalidJson => "Integration JSON is invalid; use manual integration",
            Self::DuplicateKey => "Integration JSON contains duplicate keys; use manual integration",
            Self::InvalidLayout => "Layout needs manual integration; preserve existing IDs and visibility controls",
            Self::UnsupportedToolbar => "Toolbar differs from the supported stock structure; use manual integration",
            Self::ToolbarIdentity => "Toolbar commands or shortcuts depend on its original mod name; use manual integration",
            Self::InvalidShortcuts => "Shortcut configuration could not be checked safely; preserve it with manual integration",
            Self::BundleChanged => "Managed installation changed; integration was not completed",
            Self::UnsafePath => "Unsafe integration path; files were preserved",
            Self::InvalidFile => "Invalid integration file",
            Self::Changed => "Integration inputs changed; review personal files and retry repair",
            Self::Conflict => "Personal integration differs; conflicting files were preserved",
            Self::Limit => "Integration exceeds automatic integration limits",
            Self::Io => "Integration filesystem operation failed; integration may be incomplete",
            Self::NativeCheck => "Native toolbar check failed; integration was not published",
        };
        if matches!(
            self,
            Self::InvalidJson
                | Self::DuplicateKey
                | Self::InvalidLayout
                | Self::UnsupportedToolbar
                | Self::ToolbarIdentity
                | Self::InvalidShortcuts
        ) {
            write!(f, "{message}; {MANUAL_INTEGRATION_URL}")
        } else {
            f.write_str(message)
        }
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
    #[cfg(test)]
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
    publish_with(path, bytes, |source, target| fs::hard_link(source, target))
}
fn publish_with<F>(path: &Path, bytes: &[u8], link: F) -> Result<()>
where
    F: FnOnce(&Path, &Path) -> std::io::Result<()>,
{
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
        .prefix(&format!(".jira-peek-attach-{}-", std::process::id()))
        .suffix(".tmp")
        .tempfile_in(parent)?;
    staged.write_all(bytes)?;
    staged.as_file().sync_all()?;
    safe_path(path)?;
    match link(staged.path(), path) {
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
#[cfg(test)]
pub fn apply_attachment(plan: &AttachmentPlan, app_home: &Path) -> Result<()> {
    apply_with(plan, app_home, publish).map(|_| ())
}
/// As `apply_attachment`, also reports preserved unverified orphan candidates.
pub fn apply_attachment_report(plan: &AttachmentPlan, app_home: &Path) -> Result<CleanupReport> {
    apply_with(plan, app_home, publish)
}
fn apply_with<F>(
    plan: &AttachmentPlan,
    app_home: &Path,
    mut publish_file: F,
) -> Result<CleanupReport>
where
    F: FnMut(&Path, &[u8]) -> Result<()>,
{
    if app_home != plan.home {
        return Err(IntegrationError::UnsafePath);
    }
    validate_attachment(plan)?;
    let mut cleanup = CleanupReport::default();
    let directories: std::collections::BTreeSet<_> =
        plan.files.keys().filter_map(|p| p.parent()).collect();
    for directory in directories {
        safe_path(directory)?;
        if directory.is_dir() {
            let contents: Vec<_> = plan
                .files
                .iter()
                .filter(|(path, _)| path.parent() == Some(directory))
                .map(|(_, bytes)| bytes.as_slice())
                .collect();
            let report = cleanup_attachment_staging(directory, &contents)?;
            cleanup.removed += report.removed;
            cleanup.preserved += report.preserved;
        }
    }
    // Publish the toolbar first and the layout last, as the Python oracle does.
    let mut ordered: Vec<_> = plan.files.iter().collect();
    ordered.sort_by_key(|(p, _)| {
        (
            p.starts_with(app_home.join("layouts")),
            match p.file_name().and_then(|s| s.to_str()) {
                Some("main.js") => 0,
                Some("mod.json") => 1,
                _ => 2,
            },
            *p,
        )
    });
    for (path, bytes) in ordered {
        validate_attachment(plan)?;
        publish_file(path, bytes)?;
    }
    validate_attachment(plan)?;
    for (path, bytes) in &plan.files {
        if integration_snapshot(path)?.bytes != *bytes {
            return Err(IntegrationError::Changed);
        }
    }
    Ok(cleanup)
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CleanupReport {
    pub removed: usize,
    pub preserved: usize,
}
/// Reclaim only complete, private aliases owned by this user with a dead creator.
/// Unknown or partial staging files are preserved. Never rewrite a final target.
pub fn cleanup_attachment_staging(directory: &Path, contents: &[&[u8]]) -> Result<CleanupReport> {
    safe_path(directory)?;
    let pattern =
        regex::Regex::new(r"^\.jira-peek-attach-([1-9][0-9]*)-[A-Za-z0-9_]+\.tmp$").unwrap();
    let mut report = CleanupReport::default();
    for entry in fs::read_dir(directory)? {
        let path = entry?.path();
        let Some(name) = path.file_name().and_then(|s| s.to_str()) else {
            continue;
        };
        let Some(captures) = pattern.captures(name) else {
            continue;
        };
        let Ok(pid) = captures[1].parse::<i32>() else {
            continue;
        };
        // SAFETY: kill(pid, 0) probes existence only; it sends no signal.
        if unsafe { libc::kill(pid, 0) } == 0
            || std::io::Error::last_os_error().raw_os_error() != Some(libc::ESRCH)
        {
            continue;
        }
        let verified = integration_snapshot(&path).ok().filter(|snapshot| {
            // SAFETY: getuid has no inputs and no memory effects.
            snapshot.identity.3 == unsafe { libc::getuid() }
                && snapshot.identity.2 & 0o7777 == 0o600
                && contents.contains(&snapshot.bytes.as_slice())
        });
        if let Some(snapshot) = verified {
            if fs::symlink_metadata(&path).is_ok_and(|m| identity(&m) == snapshot.identity)
                && fs::remove_file(&path).is_ok()
            {
                report.removed += 1;
            } else {
                report.preserved += 1;
            }
        } else {
            report.preserved += 1;
        }
    }
    Ok(report)
}
/// Stage only the generated toolbar. The lifecycle core supplies its isolated,
/// version-checked native checker (herdr-app >= 0.1.10; hc is separate).
pub fn check_attachment<F>(plan: &AttachmentPlan, toolbar: &Path, checker: F) -> Result<()>
where
    F: FnOnce(&Path) -> Result<()>,
{
    validate_attachment(plan)?;
    if toolbar != plan.toolbar_directory()? {
        return Err(IntegrationError::UnsafePath);
    }
    let staged = tempfile::Builder::new()
        .prefix("jira-peek-toolbar-")
        .tempdir_in(std::env::temp_dir().canonicalize()?)?;
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

// JSON objects retain input order: generated files must match the Python
// installer's bytes, including when repairing an existing personal copy.
#[derive(Clone, Debug, PartialEq)]
enum Json {
    Null,
    Bool(bool),
    Number(String),
    String(String),
    Array(Vec<Json>),
    Object(Vec<(String, Json)>),
}
impl Json {
    fn get(&self, key: &str) -> Option<&Self> {
        match self {
            Self::Object(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    fn string(&self) -> Option<&str> {
        if let Self::String(s) = self {
            Some(s)
        } else {
            None
        }
    }
    fn set(&mut self, key: &str, value: Self) -> Result<()> {
        let Self::Object(items) = self else {
            return Err(IntegrationError::InvalidLayout);
        };
        if let Some((_, v)) = items.iter_mut().find(|(k, _)| k == key) {
            *v = value;
        } else {
            items.push((key.into(), value));
        }
        Ok(())
    }
    fn truthy(&self) -> bool {
        match self {
            Self::Null => false,
            Self::Bool(v) => *v,
            Self::Number(n) => n.parse::<f64>() != Ok(0.0),
            Self::String(s) => !s.is_empty(),
            Self::Array(v) => !v.is_empty(),
            Self::Object(v) => !v.is_empty(),
        }
    }
}
struct JsonReader<'a> {
    data: &'a [u8],
    offset: usize,
    max_depth: usize,
}
impl JsonReader<'_> {
    fn whitespace(&mut self) {
        while self
            .data
            .get(self.offset)
            .is_some_and(|b| b" \t\r\n".contains(b))
        {
            self.offset += 1;
        }
    }
    fn string(&mut self) -> Result<String> {
        let start = self.offset;
        if self.data.get(start) != Some(&b'"') {
            return Err(IntegrationError::InvalidJson);
        }
        self.offset += 1;
        while let Some(&b) = self.data.get(self.offset) {
            self.offset += 1;
            if b == b'"' {
                return serde_json::from_slice(&self.data[start..self.offset])
                    .map_err(|_| IntegrationError::InvalidJson);
            }
            if b == b'\\' {
                self.offset += 1;
            }
        }
        Err(IntegrationError::InvalidJson)
    }
    fn value(&mut self, depth: usize) -> Result<Json> {
        self.whitespace();
        let start = self.offset;
        match self.data.get(start).copied() {
            Some(b'"') => self.string().map(Json::String),
            Some(b'{' | b'[') => {
                if depth >= self.max_depth {
                    return Err(IntegrationError::Limit);
                }
                let object = self.data[start] == b'{';
                let close = if object { b'}' } else { b']' };
                self.offset += 1;
                self.whitespace();
                let mut items = Vec::new();
                let mut pairs = Vec::new();
                let mut keys = std::collections::HashSet::new();
                if self.data.get(self.offset) != Some(&close) {
                    loop {
                        if object {
                            self.whitespace();
                            let key = self.string()?;
                            if !keys.insert(key.clone()) {
                                return Err(IntegrationError::DuplicateKey);
                            }
                            self.whitespace();
                            if self.data.get(self.offset) != Some(&b':') {
                                return Err(IntegrationError::InvalidJson);
                            }
                            self.offset += 1;
                            pairs.push((key, self.value(depth + 1)?));
                        } else {
                            items.push(self.value(depth + 1)?);
                        }
                        self.whitespace();
                        if self.data.get(self.offset) != Some(&b',') {
                            break;
                        }
                        self.offset += 1;
                    }
                }
                if self.data.get(self.offset) != Some(&close) {
                    return Err(IntegrationError::InvalidJson);
                }
                self.offset += 1;
                Ok(if object {
                    Json::Object(pairs)
                } else {
                    Json::Array(items)
                })
            }
            Some(_) => {
                while self
                    .data
                    .get(self.offset)
                    .is_some_and(|b| !b" \t\r\n,]}".contains(b))
                {
                    self.offset += 1;
                }
                let token = std::str::from_utf8(&self.data[start..self.offset])
                    .map_err(|_| IntegrationError::InvalidJson)?;
                match token {
                    "null" => Ok(Json::Null),
                    "true" => Ok(Json::Bool(true)),
                    "false" => Ok(Json::Bool(false)),
                    _ => {
                        static NUMBER: std::sync::LazyLock<regex::Regex> =
                            std::sync::LazyLock::new(|| {
                                regex::Regex::new(
                                    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$",
                                )
                                .unwrap()
                            });
                        if !NUMBER.is_match(token) {
                            return Err(IntegrationError::InvalidJson);
                        }
                        let normalized = if token.contains(['.', 'e', 'E']) {
                            let n: f64 =
                                token.parse().map_err(|_| IntegrationError::InvalidJson)?;
                            if !n.is_finite() {
                                return Err(IntegrationError::InvalidJson);
                            }
                            if n != 0.0 && (n.abs() < 1e-4 || n.abs() >= 1e16) {
                                let scientific = format!("{n:e}");
                                let (base, exp) = scientific.split_once('e').unwrap();
                                let exp: i32 = exp.parse().unwrap();
                                format!("{base}e{exp:+03}")
                            } else {
                                let s = n.to_string();
                                if s.contains('.') {
                                    s
                                } else {
                                    format!("{s}.0")
                                }
                            }
                        } else if token == "-0" {
                            "0".into()
                        } else {
                            token.into()
                        };
                        Ok(Json::Number(normalized))
                    }
                }
            }
            None => Err(IntegrationError::InvalidJson),
        }
    }
}
fn parse_json(data: &[u8]) -> Result<Json> {
    parse_json_depth(data, 128)
}
fn parse_json_depth(data: &[u8], max_depth: usize) -> Result<Json> {
    if data.len() as u64 > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    let mut reader = JsonReader {
        data,
        offset: 0,
        max_depth,
    };
    let value = reader.value(0)?;
    reader.whitespace();
    if reader.offset != data.len() {
        return Err(IntegrationError::InvalidJson);
    }
    Ok(value)
}
fn quoted(s: &str) -> String {
    let raw = serde_json::to_string(s).expect("string serialization");
    let mut out = String::new();
    for c in raw.chars() {
        if !c.is_ascii() || c == '\u{7f}' {
            for unit in c.encode_utf16(&mut [0; 2]) {
                out.push_str(&format!("\\u{unit:04x}"));
            }
        } else {
            out.push(c);
        }
    }
    out
}
fn json_bytes(value: &Json, pretty: bool) -> Vec<u8> {
    fn render(value: &Json, pretty: bool, depth: usize, out: &mut String) {
        match value {
            Json::Null => out.push_str("null"),
            Json::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
            Json::Number(n) => out.push_str(n),
            Json::String(s) => out.push_str(&quoted(s)),
            Json::Object(items) => {
                out.push('{');
                for (i, (key, value)) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    if pretty {
                        out.push('\n');
                        out.push_str(&"  ".repeat(depth + 1));
                    }
                    out.push_str(&quoted(key));
                    out.push(':');
                    if pretty {
                        out.push(' ');
                    }
                    render(value, pretty, depth + 1, out);
                }
                if pretty && !items.is_empty() {
                    out.push('\n');
                    out.push_str(&"  ".repeat(depth));
                }
                out.push('}');
            }
            Json::Array(items) => {
                out.push('[');
                for (i, value) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    if pretty {
                        out.push('\n');
                        out.push_str(&"  ".repeat(depth + 1));
                    }
                    render(value, pretty, depth + 1, out);
                }
                if pretty && !items.is_empty() {
                    out.push('\n');
                    out.push_str(&"  ".repeat(depth));
                }
                out.push(']');
            }
        }
    }
    let mut out = String::new();
    render(value, pretty, 0, &mut out);
    out.push('\n');
    out.into_bytes()
}

const FIND: &str = "function find(node, id) {\n  if (node?.id === id) return node;\n  for (const child of node?.children ?? []) {\n    const found = find(child, id);\n    if (found) return found;\n  }\n  return null;\n}";
const CHANGES: &str = "      .when(enabled.includes(\"changes\"), el => el.child(panelButton(\"changes\", \"Changes\", \"mods/changes/changes.svg\")))\n";
fn string_literal(raw: &str, quote: u8) -> Result<String> {
    if !raw.contains('\\') {
        return Ok(raw.into());
    }
    if quote == b'`' {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    let mut out = String::new();
    let mut chars = raw.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        let escaped = chars.next().ok_or(IntegrationError::UnsupportedToolbar)?;
        match escaped {
            '\\' | '\'' | '"' => out.push(escaped),
            'b' => out.push('\u{8}'),
            'f' => out.push('\u{c}'),
            'n' => out.push('\n'),
            'r' => out.push('\r'),
            't' => out.push('\t'),
            'v' => out.push('\u{b}'),
            '\n' => (),
            '\r' => {
                if chars.peek() == Some(&'\n') {
                    chars.next();
                }
            }
            'x' | 'u' => {
                let mut n = 0;
                for _ in 0..if escaped == 'x' { 2 } else { 4 } {
                    n = n * 16
                        + chars
                            .next()
                            .and_then(|c| c.to_digit(16))
                            .ok_or(IntegrationError::UnsupportedToolbar)?;
                }
                out.push(char::from_u32(n).ok_or(IntegrationError::UnsupportedToolbar)?);
            }
            '0'..='7' => {
                let mut n = escaped.to_digit(8).unwrap();
                for _ in 0..2 {
                    if let Some(d) = chars.peek().and_then(|c| c.to_digit(8)) {
                        n = n * 8 + d;
                        chars.next();
                    } else {
                        break;
                    }
                }
                // Python treats octal values above 255 as a warning/error.
                if n > 255 {
                    return Err(IntegrationError::UnsupportedToolbar);
                }
                out.push(char::from_u32(n).ok_or(IntegrationError::UnsupportedToolbar)?);
            }
            _ => return Err(IntegrationError::UnsupportedToolbar),
        }
    }
    Ok(out)
}
/// Mask supported strings/comments without executing JavaScript. Byte offsets
/// remain valid even for non-ASCII text. Escapes are decoded only for identity checks.
fn toolbar_code(source: &str, decode_literals: bool) -> Result<(String, Vec<String>)> {
    if source.len() as u64 > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    let bytes = source.as_bytes();
    let mut code = bytes.to_vec();
    let mut index = 0;
    let mut literals = Vec::new();
    while index < bytes.len() {
        let start = index;
        if bytes[index..].starts_with(b"//") {
            index += 2;
            while index < bytes.len() && bytes[index] != b'\n' {
                index += 1;
            }
        } else if bytes[index..].starts_with(b"/*") {
            index += 2;
            while index + 1 < bytes.len() && &bytes[index..index + 2] != b"*/" {
                index += 1;
            }
            if index + 1 >= bytes.len() {
                return Err(IntegrationError::UnsupportedToolbar);
            }
            index += 2;
        } else if b"\"'`".contains(&bytes[index]) {
            let quote = bytes[index];
            index += 1;
            while index < bytes.len() && bytes[index] != quote {
                if bytes[index] == b'\\' {
                    index += 2;
                } else if b"\r\n".contains(&bytes[index]) && quote != b'`' {
                    return Err(IntegrationError::UnsupportedToolbar);
                } else {
                    index += 1;
                }
            }
            if index >= bytes.len() {
                return Err(IntegrationError::UnsupportedToolbar);
            }
            if decode_literals {
                literals.push(string_literal(&source[start + 1..index], quote)?);
            }
            index += 1;
        } else {
            index += 1;
            continue;
        }
        for c in &mut code[start..index] {
            if *c != b'\n' {
                *c = b' ';
            }
        }
    }
    Ok((
        String::from_utf8(code).map_err(|_| IntegrationError::UnsupportedToolbar)?,
        literals,
    ))
}
/// Transform only the supported stock builder structure; ambiguous syntax,
/// aliases and rebinding require manual integration. Relative imports and custom
/// controls are retained verbatim. This is deliberately not a JavaScript engine.
pub fn integrate_toolbar(source: &str, panel_id: &str) -> Result<String> {
    if source.len() as u64 > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    let anchors = [
        FIND,
        "  render() {\n",
        "    const t = theme();",
        "    const stop = (_e, cx) => cx.stop_propagation();",
        "    const root = layout(), sidebar = find(root, \"sidebar\"), w = window();",
        CHANGES,
    ];
    if anchors.iter().any(|a| source.matches(a).count() != 1) || source.contains("panel-jira-peek")
    {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    let base_re =
        regex::Regex::new(r#"(?m)^import \{ ([A-Za-z0-9_, ]+) \} from "gpui-base";$"#).unwrap();
    let host_re =
        regex::Regex::new(r#"(?m)^import \{ ([A-Za-z0-9_, ]+) \} from "herdr";$"#).unwrap();
    let view_re =
        regex::Regex::new(r"(?m)^export default class [A-Za-z0-9_]+ extends View \{").unwrap();
    let return_re = regex::Regex::new(r"(?m)^    return h_flex\(\)\.").unwrap();
    let base = base_re
        .captures(source)
        .ok_or(IntegrationError::UnsupportedToolbar)?;
    let host = host_re
        .captures(source)
        .ok_or(IntegrationError::UnsupportedToolbar)?;
    let view = view_re
        .find(source)
        .ok_or(IntegrationError::UnsupportedToolbar)?;
    let returns: Vec<_> = return_re.find_iter(source).collect();
    let imported = |group: &str, name: &str| group.split(',').any(|s| s.trim() == name);
    if !imported(&base[1], "h_flex")
        || ["run", "layout", "settings", "theme"]
            .iter()
            .any(|name| !imported(&host[1], name))
        || returns.len() != 1
    {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    let positions: Vec<_> = anchors
        .iter()
        .map(|a| source.find(a).unwrap() + a.len() - a.trim_start().len())
        .collect();
    let returned = returns[0].start() + 4;
    let render_scope = vec![
        view.end() - 1,
        source.find(anchors[1]).unwrap() + anchors[1].len() - 2,
    ];
    let base_match = base.get(0).unwrap();
    let host_match = host.get(0).unwrap();
    let mut offsets: std::collections::BTreeSet<_> = positions.iter().copied().collect();
    offsets.extend([
        returned,
        base_match.start(),
        host_match.start(),
        view.start(),
    ]);
    let (code, _) = toolbar_code(source, false)?;
    let mut contexts = BTreeMap::new();
    let mut stack = Vec::new();
    let mut terminated = false;
    for (i, c) in code.bytes().enumerate() {
        if offsets.contains(&i) {
            if c.is_ascii_whitespace() {
                return Err(IntegrationError::UnsupportedToolbar);
            }
            contexts.insert(i, stack.clone());
        }
        if b"{([".contains(&c) {
            stack.push(i);
            if stack.len() > 128 {
                return Err(IntegrationError::Limit);
            }
        } else if b"})]".contains(&c) {
            let opening = stack.pop().ok_or(IntegrationError::UnsupportedToolbar)?;
            if code.as_bytes()[opening]
                != match c {
                    b'}' => b'{',
                    b')' => b'(',
                    _ => b'[',
                }
            {
                return Err(IntegrationError::UnsupportedToolbar);
            }
        } else if c == b';' && returned < i && i < positions[5] && stack == render_scope {
            terminated = true;
        }
    }
    if !stack.is_empty()
        || regex::Regex::new(r"\\u(?:[0-9A-Fa-f]{4}|\{)")
            .unwrap()
            .is_match(&code)
    {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    let binding_re =
        regex::Regex::new(r"\b(?:Toggle|find|h_flex|layout|run|settings|theme)\b").unwrap();
    let call_re = regex::Regex::new(r"^[ \t]*\(").unwrap();
    let toggle_re = regex::Regex::new(r"^[ \t]*\.[ \t]*new[ \t]*\(").unwrap();
    for binding in binding_re.find_iter(&code) {
        if (base_match.start()..base_match.end()).contains(&binding.start())
            || (host_match.start()..host_match.end()).contains(&binding.start())
            || binding.start() == positions[0] + "function ".len()
        {
            continue;
        }
        let before = code[..binding.start()]
            .trim_end()
            .strip_suffix('*')
            .unwrap_or(code[..binding.start()].trim_end())
            .trim_end();
        let call = if binding.as_str() == "Toggle" {
            &toggle_re
        } else {
            &call_re
        };
        if !call.is_match(&code[binding.end()..]) || before.ends_with("function") {
            return Err(IntegrationError::UnsupportedToolbar);
        }
    }
    let context = |position| contexts.get(&position).map(Vec::as_slice);
    if context(positions[0]) != Some(&[][..])
        || context(positions[1]) != Some(&render_scope[..1])
        || positions[2..]
            .iter()
            .any(|p| context(*p) != Some(render_scope.as_slice()))
        || context(returned) != Some(render_scope.as_slice())
        || *positions[2..5].iter().max().unwrap() >= returned
        || returned >= positions[5]
        || terminated
        || [base_match.start(), host_match.start(), view.start()]
            .iter()
            .any(|p| context(*p) != Some(&[][..]))
    {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    let toggle = r#"      .when(!!find(root, PANEL_ID), el => {
        const peek = find(root, PANEL_ID);
        return el.child(Toggle.new("panel-jira-peek")
          .accessibility_label("Jira Peek").pressed(!peek.hidden)
          .h(26).px(8).flex_none().rounded(6).text_size(settings().ui_font_size)
          .bg(peek.hidden ? t.chrome : t.selected).text_color(peek.hidden ? t.muted : t.foreground)
          .hover(s => s.bg(t.hover)).focus(s => s.bg(t.selected))
          .on_mouse_down("left", stop)
          .on_change(() => run("layout.toggle", { id: peek.id })).child("Jira Peek"));
      })
"#
    .replace("PANEL_ID", &quoted(panel_id));
    let mut toolbar = source.replace(CHANGES, &format!("{CHANGES}{toggle}"));
    if !imported(&base[1], "Toggle") {
        toolbar.insert_str(base.get(1).unwrap().end(), ", Toggle");
    }
    if toolbar.len() as u64 > FILE_LIMIT {
        return Err(IntegrationError::Limit);
    }
    Ok(toolbar)
}

fn valid_name(name: &str, maximum: usize) -> bool {
    !name.is_empty()
        && name.len() <= maximum
        && name
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"_-".contains(&c))
}
fn node_at<'a>(layout: &'a Json, path: &[usize]) -> &'a Json {
    let mut node = layout;
    for index in path {
        let Json::Array(children) = node.get("children").unwrap() else {
            unreachable!()
        };
        node = &children[*index];
    }
    node
}
fn node_mut<'a>(layout: &'a mut Json, path: &[usize]) -> &'a mut Json {
    let mut node = layout;
    for index in path {
        let Json::Object(items) = node else {
            unreachable!()
        };
        let (_, Json::Array(children)) = items.iter_mut().find(|(k, _)| k == "children").unwrap()
        else {
            unreachable!()
        };
        node = &mut children[*index];
    }
    node
}
fn layout_entries(layout: &Json) -> Result<Vec<Vec<usize>>> {
    let mut pending = vec![Vec::new()];
    let mut paths = Vec::new();
    let mut ids = std::collections::HashSet::new();
    while let Some(path) = pending.pop() {
        if paths.len() >= 4096 || path.len() > 64 {
            return Err(IntegrationError::Limit);
        }
        let node = node_at(layout, &path);
        if !matches!(node, Json::Object(_))
            || node
                .get("content")
                .is_some_and(|v| !matches!(v, Json::Object(_)))
        {
            return Err(IntegrationError::InvalidLayout);
        }
        if let Some(id) = node.get("id").and_then(Json::string) {
            if !ids.insert(id) {
                return Err(IntegrationError::InvalidLayout);
            }
        }
        if let Some(children) = node.get("children") {
            let Json::Array(children) = children else {
                return Err(IntegrationError::InvalidLayout);
            };
            for index in (0..children.len()).rev() {
                let mut child = path.clone();
                child.push(index);
                pending.push(child);
            }
        }
        paths.push(path);
    }
    Ok(paths)
}
fn mod_name(node: &Json) -> Option<&str> {
    node.get("content")
        .and_then(|v| v.get("mod"))
        .and_then(Json::string)
}
struct LayoutSource {
    layout: Json,
    paths: Vec<Vec<usize>>,
    inputs: BTreeMap<PathBuf, Option<Snapshot>>,
}
fn read_layout(app_home: &Path, name: &str) -> Result<LayoutSource> {
    safe_path(app_home)?;
    if !valid_name(name, 100) {
        return Err(IntegrationError::InvalidLayout);
    }
    let path = app_home.join("layouts").join(format!("{name}.json"));
    let snapshot = integration_snapshot(&path)?;
    let layout = parse_json_depth(&snapshot.bytes, 256)?;
    let paths = layout_entries(&layout)?;
    Ok(LayoutSource {
        layout,
        paths,
        inputs: BTreeMap::from([(path, Some(snapshot))]),
    })
}
fn toolbar_node(app_home: &Path, source: &mut LayoutSource) -> Result<Vec<usize>> {
    let mut candidates = Vec::new();
    for path in &source.paths {
        let node = node_at(&source.layout, path);
        let Some(name) = mod_name(node).filter(|name| valid_name(name, 100)) else {
            continue;
        };
        let mut candidate = name == "tabs" || node.get("id").and_then(Json::string) == Some("tabs");
        if !candidate && name != "jira-peek" {
            let metadata = app_home.join("mods").join(name).join("mod.json");
            let snapshot = optional_snapshot(&metadata)?;
            if let Some(snapshot) = &snapshot {
                candidate = parse_json(&snapshot.bytes)?
                    .get("cloned_from")
                    .and_then(|v| v.get("name"))
                    .and_then(Json::string)
                    == Some("tabs");
            }
            if source
                .inputs
                .get(&metadata)
                .is_some_and(|old| old != &snapshot)
            {
                return Err(IntegrationError::Changed);
            }
            source.inputs.insert(metadata, snapshot);
            if source
                .inputs
                .values()
                .flatten()
                .map(|s| s.bytes.len())
                .sum::<usize>()
                > 16 * 1024 * 1024
            {
                return Err(IntegrationError::Limit);
            }
        }
        if candidate {
            candidates.push(path.clone());
        }
    }
    if candidates.len() != 1 {
        return Err(IntegrationError::UnsupportedToolbar);
    }
    Ok(candidates.remove(0))
}
fn toolbar_shortcuts(snapshot: Option<&Snapshot>, name: &str) -> Result<bool> {
    let Some(snapshot) = snapshot else {
        return Ok(false);
    };
    let config = parse_json(&snapshot.bytes).map_err(|_| IntegrationError::InvalidShortcuts)?;
    if !matches!(config, Json::Object(_)) {
        return Err(IntegrationError::InvalidShortcuts);
    }
    let mut pending = vec![(&config, 0)];
    let mut count = 0;
    let scope = format!("mod:{name}");
    let prefix = format!("{name}.");
    while let Some((value, depth)) = pending.pop() {
        count += 1;
        if count > 4096 || depth > 64 {
            return Err(IntegrationError::InvalidShortcuts);
        }
        match value {
            Json::Object(items) => {
                if value.get(&scope).is_some_and(Json::truthy) {
                    return Ok(true);
                }
                pending.extend(items.iter().map(|(_, v)| (v, depth + 1)));
            }
            Json::Array(items) => pending.extend(items.iter().map(|v| (v, depth + 1))),
            Json::String(s) if s.starts_with(&prefix) || s == &scope => return Ok(true),
            _ => (),
        }
    }
    Ok(false)
}
fn mentions_identity(literal: &str, name: &str) -> bool {
    literal.match_indices(name).any(|(i, _)| {
        let before = literal[..i].chars().next_back();
        let after = literal[i + name.len()..].chars().next();
        !before.is_some_and(|c| c.is_ascii_alphanumeric() || "_-".contains(c))
            && !after.is_some_and(|c| c.is_ascii_alphanumeric() || "_/-".contains(c))
    })
}
/// Plan a personal copy without writing or selecting anything. The original
/// source layout, toolbar, imports, assets and shortcuts are expected-state inputs.
pub fn plan_attachment(
    app_home: &Path,
    source_name: &str,
    check_conflicts: bool,
) -> Result<AttachmentPlan> {
    if !valid_name(source_name, 64) || source_name.ends_with("-jira-peek") {
        return Err(IntegrationError::InvalidLayout);
    }
    let mut source = read_layout(app_home, source_name)?;
    let toolbar_path = toolbar_node(app_home, &mut source)?;
    let toolbar_name = mod_name(node_at(&source.layout, &toolbar_path))
        .unwrap()
        .to_owned();
    let panels: Vec<_> = source
        .paths
        .iter()
        .filter(|p| mod_name(node_at(&source.layout, p)) == Some("jira-peek"))
        .cloned()
        .collect();
    let bodies: Vec<_> = source
        .paths
        .iter()
        .filter(|p| {
            let n = node_at(&source.layout, p);
            n.get("id").and_then(Json::string) == Some("work-body")
                && n.get("type").and_then(Json::string) == Some("row")
        })
        .cloned()
        .collect();
    if panels.len() > 1 || (panels.is_empty() && bodies.len() != 1) {
        return Err(IntegrationError::InvalidLayout);
    }
    let panel_path = if let Some(path) = panels.first() {
        path.clone()
    } else {
        if source.paths.iter().any(|p| {
            node_at(&source.layout, p).get("id").and_then(Json::string) == Some("jira-peek")
        }) {
            return Err(IntegrationError::InvalidLayout);
        }
        let body = node_mut(&mut source.layout, &bodies[0]);
        if body.get("children").is_none() {
            body.set("children", Json::Array(Vec::new()))?;
        }
        let Json::Object(items) = body else {
            unreachable!()
        };
        let (_, Json::Array(children)) = items.iter_mut().find(|(k, _)| k == "children").unwrap()
        else {
            unreachable!()
        };
        let mut path = bodies[0].clone();
        path.push(children.len());
        children.push(parse_json(br#"{"id":"jira-peek","type":"block","size":{"px":360},"min":300,"max":640,"content":{"mod":"jira-peek"}}"#)?);
        path
    };
    let panel = node_at(&source.layout, &panel_path);
    let panel_id = panel
        .get("id")
        .and_then(Json::string)
        .filter(|s| !s.is_empty())
        .ok_or(IntegrationError::InvalidLayout)?
        .to_owned();
    if panel.get("type").and_then(Json::string) != Some("block")
        || (0..panel_path.len()).any(|length| {
            let n = node_at(&source.layout, &panel_path[..length]);
            n.get("hidden").is_some_and(Json::truthy)
                || n.get("type").and_then(Json::string) == Some("stack")
        })
    {
        return Err(IntegrationError::InvalidLayout);
    }
    let directory = app_home.join("mods").join(&toolbar_name);
    let inventory = toolbar_files(&directory)?;
    for path in &inventory {
        let snapshot = integration_snapshot(path)?;
        // A candidate metadata read must not be silently refreshed after it was
        // used to identify the toolbar.
        if source
            .inputs
            .get(path)
            .is_some_and(|old| old.as_ref() != Some(&snapshot))
        {
            return Err(IntegrationError::Changed);
        }
        source.inputs.insert(path.clone(), Some(snapshot));
        if source
            .inputs
            .values()
            .flatten()
            .map(|s| s.bytes.len())
            .sum::<usize>()
            > 16 * 1024 * 1024
        {
            return Err(IntegrationError::Limit);
        }
    }
    let total: usize = source
        .inputs
        .values()
        .flatten()
        .map(|s| s.bytes.len())
        .sum();
    if total > 16 * 1024 * 1024 {
        return Err(IntegrationError::Limit);
    }
    let keys = app_home.join("keys.json");
    let key_snapshot = optional_snapshot(&keys)?;
    if toolbar_shortcuts(key_snapshot.as_ref(), &toolbar_name)? {
        return Err(IntegrationError::ToolbarIdentity);
    }
    source.inputs.insert(keys.clone(), key_snapshot);
    let next_command = regex::Regex::new(r"\bnextCommand\b").unwrap();
    for (path, snapshot) in &source.inputs {
        if path == &keys
            || !matches!(
                path.extension().and_then(|v| v.to_str()),
                Some("js" | "mjs")
            )
        {
            continue;
        }
        if let Some(snapshot) = snapshot {
            let code = std::str::from_utf8(&snapshot.bytes)
                .map_err(|_| IntegrationError::UnsupportedToolbar)?;
            let (masked, literals) = toolbar_code(code, true)?;
            if literals
                .iter()
                .any(|s| mentions_identity(s, &toolbar_name) || s == "nextCommand")
                || next_command.is_match(&masked)
            {
                return Err(IntegrationError::ToolbarIdentity);
            }
        }
    }
    let main = source
        .inputs
        .get(&directory.join("main.js"))
        .and_then(Option::as_ref)
        .ok_or(IntegrationError::UnsupportedToolbar)?;
    let toolbar = integrate_toolbar(
        std::str::from_utf8(&main.bytes).map_err(|_| IntegrationError::UnsupportedToolbar)?,
        &panel_id,
    )?;
    let generated = if toolbar_name == "tabs" {
        "tabs-jira-peek".into()
    } else {
        format!("{source_name}-tabs-jira-peek")
    };
    let target = app_home.join("mods").join(&generated);
    let mut metadata = parse_json(br#"{"place":"none","title":"Tabs with Jira Peek"}"#)?;
    if toolbar_name != "tabs" {
        if let Some(Some(snapshot)) = source.inputs.get(&directory.join("mod.json")) {
            metadata = parse_json(&snapshot.bytes)?;
            metadata.set("place", Json::String("none".into()))?;
            metadata.set("title", Json::String("Tabs with Jira Peek".into()))?;
        }
    }
    let tabs = node_mut(&mut source.layout, &toolbar_path);
    let mut content = tabs.get("content").unwrap().clone();
    content.set("mod", Json::String(generated))?;
    tabs.set("content", content)?;
    let name = format!("{source_name}-jira-peek");
    let mut files = BTreeMap::from([
        (target.join("main.js"), toolbar.into_bytes()),
        (target.join("mod.json"), json_bytes(&metadata, false)),
    ]);
    for path in &inventory {
        let relative = path
            .strip_prefix(&directory)
            .map_err(|_| IntegrationError::UnsafePath)?;
        if relative == Path::new("main.js") || relative == Path::new("mod.json") {
            continue;
        }
        files.insert(
            target.join(relative),
            source.inputs[path].as_ref().unwrap().bytes.clone(),
        );
    }
    files.insert(
        app_home.join("layouts").join(format!("{name}.json")),
        json_bytes(&source.layout, true),
    );
    AttachmentPlan::from_parts(
        name,
        app_home.into(),
        files,
        source.inputs,
        BTreeMap::from([(directory, inventory)]),
        check_conflicts,
    )
}
impl AttachmentPlan {
    pub fn toolbar_directory(&self) -> Result<PathBuf> {
        let mut dirs = self
            .files
            .keys()
            .filter(|p| {
                p.starts_with(self.home.join("mods"))
                    && p.file_name().is_some_and(|n| n == "main.js")
                    && p.parent().and_then(Path::parent) == Some(self.home.join("mods").as_path())
            })
            .filter_map(|p| p.parent().map(Path::to_path_buf));
        let dir = dirs.next().ok_or(IntegrationError::InvalidFile)?;
        if dirs.next().is_some() {
            return Err(IntegrationError::InvalidFile);
        }
        Ok(dir)
    }
}

/// Read-only layout inspection. An ID is not evidence that a native panel renders.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutIntegration {
    pub toolbar: String,
    pub panel_id: Option<String>,
}
pub fn layout_integration(app_home: &Path, name: &str) -> Result<LayoutIntegration> {
    let mut source = read_layout(app_home, name)?;
    let path = toolbar_node(app_home, &mut source)?;
    let panels: Vec<_> = source
        .paths
        .iter()
        .filter(|p| mod_name(node_at(&source.layout, p)) == Some("jira-peek"))
        .collect();
    let panel_id = if panels.len() == 1 {
        node_at(&source.layout, panels[0])
            .get("id")
            .and_then(Json::string)
            .map(str::to_owned)
    } else {
        None
    };
    Ok(LayoutIntegration {
        toolbar: mod_name(node_at(&source.layout, &path)).unwrap().into(),
        panel_id,
    })
}
/// Read optional `cloned_from` metadata from an active personal toolbar. The
/// version is the stock host version at clone time, not the installed mod
/// version; absent or malformed metadata is treated as unknown.
pub fn toolbar_clone_origin(app_home: &Path, toolbar: &str) -> Option<(String, String)> {
    if !valid_name(toolbar, 100) {
        return None;
    }
    let snapshot = optional_snapshot(&app_home.join("mods").join(toolbar).join("mod.json"))
        .ok()
        .flatten()?;
    let metadata = parse_json(&snapshot.bytes).ok()?;
    let cloned = metadata.get("cloned_from")?;
    let name = cloned.get("name").and_then(Json::string)?;
    let version = cloned.get("version").and_then(Json::string)?;
    if !valid_name(name, 100)
        || version.is_empty()
        || version.len() > 40
        || version.chars().any(|c| c.is_control())
    {
        return None;
    }
    Some((name.into(), version.into()))
}
/// Relative conflicting target paths without changing files. Used by repair to
/// explain a preserved personal copy instead of reporting the first conflict.
pub fn attachment_conflicts(app_home: &Path, source: &str) -> Result<Vec<PathBuf>> {
    let plan = plan_attachment(app_home, source, false)?;
    planned_conflicts(&plan, app_home)
}
fn planned_conflicts(plan: &AttachmentPlan, app_home: &Path) -> Result<Vec<PathBuf>> {
    let mut conflicts = Vec::new();
    for (path, bytes) in &plan.files {
        if let Some(snapshot) = optional_snapshot(path)? {
            if snapshot.bytes != *bytes {
                conflicts.push(
                    path.strip_prefix(app_home)
                        .map_err(|_| IntegrationError::UnsafePath)?
                        .into(),
                );
            }
        }
    }
    Ok(conflicts)
}
/// Only the sanitized layout name and error presence survive status parsing.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ActiveLayout {
    pub name: Option<String>,
    pub errors: bool,
}
pub fn parse_active_layout(data: &[u8]) -> ActiveLayout {
    let Ok(status) = parse_json(data) else {
        return ActiveLayout::default();
    };
    let name = status
        .get("layout")
        .and_then(Json::string)
        .filter(|s| valid_name(s, 100))
        .map(str::to_owned);
    let errors = name.is_some() && status.get("errors").is_some_and(Json::truthy);
    ActiveLayout { name, errors }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PreparedIntegration {
    None,
    Matching,
    PartialOrConflicting,
    ExistsUnverified,
    Unverified,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConfiguredIntegration {
    Yes,
    /// The active layout has a Jira Peek panel and a personal toolbar. Files may
    /// differ from the current generated copy; that is not evidence of breakage.
    Personal,
    No,
    Unavailable,
    HostErrors,
    Unverified,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NextAction {
    InstallBundle,
    PreserveBundle,
    Repair,
    SelectLayout,
    PreserveConflicts,
    InspectHostErrors,
    VerifyButton,
    PersonalIntegration,
    ManualIntegration,
    ChooseSource,
}
/// Bundle validation belongs to the core; an existing directory is never treated
/// as a validated managed install by this module.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BundleState {
    Missing,
    Invalid,
    Valid,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrationDiagnosis {
    pub active: ActiveLayout,
    pub active_layout: Option<LayoutIntegration>,
    pub source: Option<String>,
    pub source_layout: Option<LayoutIntegration>,
    pub prepared_name: Option<String>,
    pub prepared: PreparedIntegration,
    pub configured: ConfiguredIntegration,
    pub unsupported: Option<IntegrationError>,
    /// Relative paths only; never source file contents or raw native status.
    pub conflicts: Vec<PathBuf>,
    pub next_action: NextAction,
    pub rendering_verified: bool,
}
/// Filesystem-only diagnosis. The core supplies bounded, read-only native status
/// and managed-bundle validation. This function never invokes or launches Herdr.
pub fn diagnose_integration(
    app_home: &Path,
    source: Option<&str>,
    active: ActiveLayout,
    bundle: BundleState,
) -> Result<IntegrationDiagnosis> {
    safe_path(app_home)?;
    let active_layout = active
        .name
        .as_deref()
        .and_then(|name| layout_integration(app_home, name).ok());
    let selected = source.or(active.name.as_deref());
    let name = selected.map(|s| s.strip_suffix("-jira-peek").unwrap_or(s));
    if name.is_some_and(|s| !valid_name(s, 64)) {
        return Err(IntegrationError::InvalidLayout);
    }
    let mut report = IntegrationDiagnosis {
        active: active.clone(),
        active_layout,
        source: name.map(str::to_owned),
        source_layout: None,
        prepared_name: None,
        prepared: PreparedIntegration::Unverified,
        configured: ConfiguredIntegration::Unavailable,
        unsupported: None,
        conflicts: Vec::new(),
        next_action: NextAction::ChooseSource,
        rendering_verified: false,
    };
    let Some(name) = name else {
        return Ok(report);
    };
    report.source_layout = layout_integration(app_home, name).ok();
    report.prepared_name = Some(format!("{name}-jira-peek"));
    let active_personal = report
        .active_layout
        .as_ref()
        .is_some_and(|layout| layout.panel_id.is_some())
        && active.name.as_deref() == report.prepared_name.as_deref();
    let active_toolbar_present = report.active_layout.as_ref().is_some_and(|layout| {
        app_home
            .join("mods")
            .join(&layout.toolbar)
            .join("main.js")
            .is_file()
    });
    let inspect = || -> Result<(AttachmentPlan, usize, Vec<PathBuf>)> {
        let plan = plan_attachment(app_home, name, false)?;
        let mut existing = 0;
        for path in plan.files.keys() {
            if optional_snapshot(path)?.is_some() {
                existing += 1;
            }
        }
        let conflicts = planned_conflicts(&plan, app_home)?;
        validate_attachment(&plan)?;
        Ok((plan, existing, conflicts))
    };
    match inspect() {
        Err(error) => {
            report.unsupported = Some(error);
            report.configured = if active.name.is_none() {
                ConfiguredIntegration::Unavailable
            } else if active.errors {
                ConfiguredIntegration::HostErrors
            } else if active_personal && active_toolbar_present {
                ConfiguredIntegration::Personal
            } else {
                ConfiguredIntegration::Unverified
            };
            let target = app_home
                .join("layouts")
                .join(format!("{name}-jira-peek.json"));
            report.prepared = if fs::symlink_metadata(target).is_ok() {
                PreparedIntegration::ExistsUnverified
            } else {
                PreparedIntegration::None
            };
            report.next_action = NextAction::ManualIntegration;
        }
        Ok((plan, existing, conflicts)) => {
            let prepared = existing == plan.files.len() && conflicts.is_empty();
            report.prepared = if prepared {
                PreparedIntegration::Matching
            } else if existing > 0 {
                PreparedIntegration::PartialOrConflicting
            } else {
                PreparedIntegration::None
            };
            report.configured = if active.name.is_none() {
                ConfiguredIntegration::Unavailable
            } else if active.errors {
                ConfiguredIntegration::HostErrors
            } else if active.name.as_deref() == Some(plan.name.as_str()) && prepared {
                ConfiguredIntegration::Yes
            } else if active_personal && !conflicts.is_empty() {
                ConfiguredIntegration::Personal
            } else {
                ConfiguredIntegration::No
            };
            report.next_action = match bundle {
                BundleState::Missing => NextAction::InstallBundle,
                BundleState::Invalid => NextAction::PreserveBundle,
                BundleState::Valid if active.errors => NextAction::InspectHostErrors,
                BundleState::Valid if report.configured == ConfiguredIntegration::Yes => {
                    NextAction::VerifyButton
                }
                BundleState::Valid
                    if prepared && active.name.as_deref() != Some(plan.name.as_str()) =>
                {
                    NextAction::SelectLayout
                }
                BundleState::Valid if report.configured == ConfiguredIntegration::Personal => {
                    NextAction::PersonalIntegration
                }
                BundleState::Valid if !conflicts.is_empty() => NextAction::PreserveConflicts,
                BundleState::Valid if prepared => NextAction::SelectLayout,
                BundleState::Valid => NextAction::Repair,
            };
            report.conflicts = conflicts;
        }
    }
    Ok(report)
}
/// Targeted guidance for unsupported or conflicting copies. The CLI owns the
/// executable path and command formatting for repair/selection actions.
pub fn manual_integration_guidance(app_home: &Path, source: &str) -> String {
    let reference = format!(
        "manual integration guide mods/jira-peek/docs/PANEL-INTEGRATION.md (online: {MANUAL_INTEGRATION_URL})"
    );
    match layout_integration(app_home, source) {
        Ok(layout) => {
            let target = layout.panel_id.map(|id| format!("use {} in both find calls", quoted(&id))).unwrap_or_else(|| "choose one Peek block with a unique ID and use its actual ID in both find calls".into());
            format!("In a separately named copy of mods/{}/main.js, add or retarget one toggle immediately after Changes; {target}. Point a copy of {source} at that toolbar and keep one Peek panel. See the {reference}.", layout.toolbar)
        }
        Err(_) => {
            format!("Review the source layout and follow the {reference}.")
        }
    }
}

/// Confirmed repair output; preserved orphan candidates need review, not deletion.
#[derive(Debug)]
pub struct RepairResult {
    pub plan: AttachmentPlan,
    pub cleanup: CleanupReport,
}
/// Runs within a lifecycle lock supplied by the caller. `with_lock` must hold
/// the core's existing installation lock throughout the callback; no second lock
/// is created. `managed_state` validates and fingerprints the complete managed
/// bundle, before locking, inside the lock, and after the optional native check.
/// Keep callback errors sanitized. Successful repair prepares files only.
pub fn repair_integration<L, S, C, T>(
    app_home: &Path,
    source: &str,
    check: bool,
    with_lock: L,
    mut managed_state: S,
    checker: C,
) -> Result<RepairResult>
where
    T: Eq,
    L: FnOnce(&mut dyn FnMut() -> Result<RepairResult>) -> Result<RepairResult>,
    S: FnMut() -> Result<T>,
    C: FnOnce(&Path) -> Result<()>,
{
    safe_path(app_home)?;
    let expected = managed_state()?;
    let mut checker = Some(checker);
    let mut called = false;
    with_lock(&mut || {
        if called {
            return Err(IntegrationError::Changed);
        }
        called = true;
        if managed_state()? != expected {
            return Err(IntegrationError::BundleChanged);
        }
        let plan = plan_attachment(app_home, source, true)?;
        if check {
            check_attachment(
                &plan,
                &plan.toolbar_directory()?,
                checker.take().ok_or(IntegrationError::NativeCheck)?,
            )?;
        }
        if managed_state()? != expected {
            return Err(IntegrationError::BundleChanged);
        }
        let cleanup = apply_attachment_report(&plan, app_home)?;
        Ok(RepairResult { plan, cleanup })
    })
}

#[cfg(test)]
mod failure_tests {
    use super::*;
    fn fixture() -> (tempfile::TempDir, AttachmentPlan, PathBuf) {
        let home = tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap();
        let input = home.path().join("source");
        fs::write(&input, b"fictional source").unwrap();
        let files = BTreeMap::from([
            (
                home.path().join("mods/tabs-jira-peek/main.js"),
                b"fictional main".to_vec(),
            ),
            (
                home.path().join("mods/tabs-jira-peek/mod.json"),
                b"{}".to_vec(),
            ),
            (
                home.path().join("layouts/main-jira-peek.json"),
                b"fictional layout".to_vec(),
            ),
        ]);
        let plan = AttachmentPlan::from_parts(
            "main-jira-peek".into(),
            home.path().into(),
            files,
            BTreeMap::from([(input.clone(), Some(integration_snapshot(&input).unwrap()))]),
            BTreeMap::new(),
            true,
        )
        .unwrap();
        (home, plan, input)
    }
    #[test]
    fn partial_publication_retains_complete_files_and_retry_finishes() {
        for fail_at in 1..=3 {
            let (home, plan, _) = fixture();
            let mut count = 0;
            assert_eq!(
                apply_with(&plan, home.path(), |path, bytes| {
                    count += 1;
                    if count == fail_at {
                        return Err(IntegrationError::Io);
                    }
                    publish(path, bytes)
                }),
                Err(IntegrationError::Io)
            );
            for (path, bytes) in plan.files() {
                if path.exists() {
                    assert_eq!(fs::read(path).unwrap(), *bytes);
                }
            }
            assert!(!home.path().join("layouts/main-jira-peek.json").exists());
            apply_attachment(&plan, home.path()).unwrap();
            apply_attachment(&plan, home.path()).unwrap();
        }
    }
    #[test]
    fn drift_after_first_publish_stops_before_layout_and_retains_main() {
        let (home, plan, input) = fixture();
        assert_eq!(
            apply_with(&plan, home.path(), |path, bytes| {
                publish(path, bytes)?;
                fs::write(&input, b"changed")?;
                Ok(())
            }),
            Err(IntegrationError::Changed)
        );
        assert_eq!(
            fs::read(home.path().join("mods/tabs-jira-peek/main.js")).unwrap(),
            b"fictional main"
        );
        assert!(!home.path().join("layouts/main-jira-peek.json").exists());
    }
    #[test]
    fn final_readback_detects_personal_edit_without_rollback() {
        let (home, plan, _) = fixture();
        let main = home.path().join("mods/tabs-jira-peek/main.js");
        assert_eq!(
            apply_with(&plan, home.path(), |path, bytes| {
                publish(path, bytes)?;
                if path.starts_with(home.path().join("layouts")) {
                    fs::write(&main, b"personal edit")?;
                }
                Ok(())
            }),
            Err(IntegrationError::Changed)
        );
        assert_eq!(fs::read(main).unwrap(), b"personal edit");
    }
    #[test]
    fn racing_creation_wins_over_staged_exclusive_link_and_failure_cleans_up() {
        for competing in [false, true] {
            let (home, _, _) = fixture();
            let target = home.path().join("mods/tabs-jira-peek/main.js");
            let result = publish_with(&target, b"generated", |staged, path| {
                assert_eq!(fs::read(staged)?, b"generated");
                if competing {
                    fs::write(path, b"personal creation")?;
                    fs::hard_link(staged, path)
                } else {
                    Err(std::io::Error::other("fictional publication failure"))
                }
            });
            assert_eq!(
                result,
                Err(if competing {
                    IntegrationError::Conflict
                } else {
                    IntegrationError::Io
                })
            );
            assert_eq!(target.exists(), competing);
            if competing {
                assert_eq!(fs::read(&target).unwrap(), b"personal creation");
            }
            assert!(fs::read_dir(target.parent().unwrap()).unwrap().all(|e| !e
                .unwrap()
                .file_name()
                .to_string_lossy()
                .starts_with(".jira-peek-attach-")));
        }
    }
    #[test]
    fn orphan_cleanup_only_unlinks_verified_dead_aliases() {
        use std::os::unix::fs::PermissionsExt;
        let (home, plan, _) = fixture();
        apply_attachment(&plan, home.path()).unwrap();
        let main = home.path().join("mods/tabs-jira-peek/main.js");
        let directory = main.parent().unwrap();
        let orphan = directory.join(".jira-peek-attach-2147483647-fixture.tmp");
        let unknown = directory.join(".jira-peek-attach-2147483647-unknown.tmp");
        let live = directory.join(format!(".jira-peek-attach-{}-live.tmp", std::process::id()));
        fs::hard_link(&main, &orphan).unwrap();
        fs::hard_link(&main, &live).unwrap();
        fs::write(&unknown, b"partial").unwrap();
        fs::set_permissions(&unknown, fs::Permissions::from_mode(0o600)).unwrap();
        let report = apply_attachment_report(&plan, home.path()).unwrap();
        assert_eq!(
            report,
            CleanupReport {
                removed: 1,
                preserved: 1
            }
        );
        assert!(!orphan.exists());
        assert!(unknown.exists());
        assert!(live.exists());
        assert_eq!(fs::read(main).unwrap(), b"fictional main");
    }
}
