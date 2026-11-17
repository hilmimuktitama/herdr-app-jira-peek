use super::fs::{digest, read_regular, safe_path};
use crate::{fail, Result};
use serde::{
    de::{Error as _, MapAccess, SeqAccess, Visitor},
    Deserialize, Deserializer,
};
use serde_json::Value;
use std::{collections::BTreeSet, fmt, os::unix::fs::PermissionsExt, path::Path};

struct Unique(Value);
impl<'de> Deserialize<'de> for Unique {
    fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = Unique;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("JSON without duplicate keys")
            }
            fn visit_map<M: MapAccess<'de>>(
                self,
                mut m: M,
            ) -> std::result::Result<Unique, M::Error> {
                let mut out = serde_json::Map::new();
                while let Some((k, v)) = m.next_entry::<String, Unique>()? {
                    if out.insert(k, v.0).is_some() {
                        return Err(M::Error::custom("duplicate key"));
                    }
                }
                Ok(Unique(Value::Object(out)))
            }
            fn visit_seq<S: SeqAccess<'de>>(
                self,
                mut s: S,
            ) -> std::result::Result<Unique, S::Error> {
                let mut v = Vec::new();
                while let Some(x) = s.next_element::<Unique>()? {
                    v.push(x.0);
                }
                Ok(Unique(Value::Array(v)))
            }
            fn visit_bool<E: serde::de::Error>(self, v: bool) -> std::result::Result<Unique, E> {
                Ok(Unique(v.into()))
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> std::result::Result<Unique, E> {
                Ok(Unique(v.into()))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> std::result::Result<Unique, E> {
                Ok(Unique(v.into()))
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> std::result::Result<Unique, E> {
                Ok(Unique(v.into()))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> std::result::Result<Unique, E> {
                Ok(Unique(serde_json::json!(v)))
            }
            fn visit_unit<E: serde::de::Error>(self) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Null))
            }
        }
        d.deserialize_any(V)
    }
}
pub fn parse(bytes: &[u8]) -> Result<Value> {
    Ok(serde_json::from_slice::<Unique>(bytes)
        .map_err(|_| fail("invalid_manifest"))?
        .0)
}
pub fn json(path: &Path) -> Result<Value> {
    parse(&read_regular(path, 1024 * 1024)?)
}
pub fn version(s: &str) -> bool {
    regex::Regex::new(r"^[0-9]+\.[0-9]+\.[0-9]+$")
        .unwrap()
        .is_match(s)
}
pub fn hash(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
pub fn relative(s: &str) -> bool {
    !s.contains('\\')
        && !s.split('/').any(|s| s.is_empty() || s == "." || s == "..")
        && s != "install.json"
}
pub const RUNTIME: &[&str] = &[
    "app-bridge.sh",
    "app-setup.py",
    "app-issue.jq",
    "app-metadata.jq",
    "common.sh",
    "connection.sh",
    "preferences.sh",
    "field-plan.sh",
    "fields.jq",
    "jira-rest.sh",
    "clear-cache.sh",
    "install-app.py",
    "update-app.py",
    "runtime-bundle.py",
];
pub const MOD: &[&str] = &[
    "main.js",
    "model.js",
    "demo.js",
    "mod.json",
    "fields.schema.json",
];
pub const ICONS: &[&str] = &[
    "options",
    "help",
    "close",
    "external-link",
    "link",
    "refresh",
    "copy",
    "check",
    "chevron-right",
    "chevron-down",
    "more",
    "pin",
    "play",
    "pause",
    "terminal",
    "user-check",
    "search",
];
pub fn inventory() -> BTreeSet<String> {
    MOD.iter()
        .map(|s| s.to_string())
        .chain(ICONS.iter().map(|s| format!("icons/{s}.svg")))
        .chain(RUNTIME.iter().map(|s| format!("runtime/{s}")))
        .chain(
            [
                "LICENSE",
                "AGENTS.md",
                "docs/PANEL-INTEGRATION.md",
                "runtime/jira-peek-bridge",
                "runtime/runtime.json",
                "runtime/THIRD-PARTY-NOTICES.txt",
            ]
            .map(str::to_string),
        )
        .collect()
}
// Frozen historical inventories, deliberately independent of inventory().
fn historical(files: &BTreeSet<String>, v: &str) -> bool {
    let base: BTreeSet<String> = include_str!("historical-inventory.txt")
        .lines()
        .map(str::to_string)
        .collect();
    let icons: BTreeSet<String> = base
        .iter()
        .filter(|s| s.starts_with("icons/"))
        .cloned()
        .collect();
    for projection in [false, true] {
        for workspace in [false, true] {
            let mut required = base.clone();
            if projection {
                required.remove("runtime/app-metadata.jq");
            }
            if workspace {
                for n in ["terminal", "user-check", "search"] {
                    required.remove(&format!("icons/{n}.svg"));
                }
            }
            let no_icons: BTreeSet<_> = required.difference(&icons).cloned().collect();
            let mut former = no_icons.clone();
            for n in ["runtime/install-app.py", "runtime/update-app.py"] {
                former.remove(n);
            }
            let mut previous = former.clone();
            for n in ["AGENTS.md", "fields.schema.json"] {
                previous.remove(n);
            }
            let mut legacy = previous.clone();
            legacy.remove("runtime/app-setup.py");
            let mut document = previous.clone();
            document.insert("runtime/app-document.py".into());
            if files == &required
                || files == &no_icons
                || files == &former
                || files == &previous
                || (["0.1.0", "0.2.0", "0.3.0"].contains(&v) && files == &legacy)
                || (v == "0.5.0" && files == &document)
            {
                return true;
            }
        }
    }
    false
}
pub fn walk(root: &Path) -> Result<Vec<String>> {
    fn visit(root: &Path, p: &Path, out: &mut Vec<String>) -> Result<()> {
        safe_path(p)?;
        for entry in std::fs::read_dir(p)? {
            let p = entry?.path();
            safe_path(&p)?;
            let m = std::fs::symlink_metadata(&p)?;
            if m.is_dir() {
                out.push(format!(
                    "{}/",
                    p.strip_prefix(root)
                        .unwrap()
                        .to_str()
                        .ok_or_else(|| fail("invalid_path"))?
                ));
                visit(root, &p, out)?;
            } else if m.is_file() {
                out.push(
                    p.strip_prefix(root)
                        .unwrap()
                        .to_str()
                        .ok_or_else(|| fail("invalid_path"))?
                        .into(),
                );
            } else {
                return Err(fail("unsafe_management_file"));
            }
        }
        Ok(())
    }
    let mut out = Vec::new();
    visit(root, root, &mut out)?;
    out.sort();
    Ok(out)
}
pub fn managed(root: &Path) -> Result<Value> {
    safe_path(root)?;
    let m = json(&root.join("install.json"))?;
    let v = m["version"]
        .as_str()
        .filter(|s| version(s))
        .ok_or_else(|| fail("invalid_install_version"))?;
    let files = m["files"]
        .as_object()
        .ok_or_else(|| fail("invalid_install_manifest"))?;
    let names: BTreeSet<_> = files.keys().cloned().collect();
    if m["owner"] != "herdr-jira-peek"
        || !(m["configDir"].is_null() || m["configDir"].is_string())
        || if m.get("format").is_some() {
            m["format"].as_u64() != Some(1)
                || !["main.js", "mod.json", "LICENSE", "runtime/app-bridge.sh"]
                    .iter()
                    .all(|s| names.contains(*s))
        } else {
            !historical(&names, v)
        }
    {
        return Err(fail("invalid_install_manifest"));
    }
    for (name, expected) in files {
        if !relative(name)
            || !expected.as_str().is_some_and(hash)
            || digest(&root.join(name))? != expected.as_str().unwrap()
        {
            return Err(fail("installed_files_changed"));
        }
        if name == "runtime/jira-peek-bridge"
            && std::fs::metadata(root.join(name))?.permissions().mode() & 0o111 == 0
        {
            return Err(fail("runtime_not_executable"));
        }
    }
    for name in walk(root)? {
        if let Some(dir) = name.strip_suffix('/') {
            if !names.iter().any(|s| s.starts_with(&format!("{dir}/"))) {
                return Err(fail("unmanaged_install_directory"));
            }
        } else if !names.contains(&name)
            && name != "install.json"
            && name != "gpui-kit.d.ts"
            && name != "jsconfig.json"
        {
            return Err(fail("unmanaged_install_file"));
        } else {
            read_regular(&root.join(name), 32 * 1024 * 1024)?;
        }
    }
    Ok(m)
}
