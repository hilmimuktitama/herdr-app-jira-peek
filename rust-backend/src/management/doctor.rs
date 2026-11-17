use super::process;
use serde_json::{json, Value};
use std::process::Command;
fn found(name: &str) -> bool {
    std::env::var_os("PATH").is_some_and(|p| {
        std::env::split_paths(&p).any(|p| {
            use std::os::unix::fs::PermissionsExt;
            std::fs::metadata(p.join(name))
                .is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
        })
    })
}
fn version(name: &str) -> Option<(String, Vec<u64>)> {
    let temp = tempfile::tempdir().ok()?;
    let mut c = Command::new(name);
    c.arg("--version");
    process::isolated(&mut c, temp.path());
    let bytes = process::run(&mut c, 10).ok()?;
    let s = std::str::from_utf8(&bytes).ok()?.trim();
    let re = regex::Regex::new(if name == "hc" {
        r"^(?:(?:hc|herdr-core)\s+)?([0-9]+\.[0-9]+\.[0-9]+)$"
    } else {
        r"^(?:herdr-app\s+)?([0-9]+\.[0-9]+\.[0-9]+)$"
    })
    .ok()?;
    let v = re.captures(s)?.get(1)?.as_str();
    Some((
        v.into(),
        v.split('.')
            .map(str::parse)
            .collect::<std::result::Result<_, _>>()
            .ok()?,
    ))
}
pub fn app_version() -> Option<String> {
    version("herdr-app").map(|v| v.0)
}
pub fn report() -> Value {
    let app = version("herdr-app");
    let core = version("hc");
    let required = json!({"posix":cfg!(unix),"herdr-app >= 0.1.10":app.as_ref().is_some_and(|(_,v)|v.as_slice()>=[0,1,10].as_slice()),"hc":found("hc")});
    json!({"ok":required.as_object().unwrap().values().all(|v|v==true),"required":required,"herdr_app_version":app.map(|v|v.0),"herdr_core_version":core.map(|v|v.0),"backend":"rest","token_setup":{"ok":true,"required":{}},"optional":{"git":found("git"),"twg":found("twg")}})
}
