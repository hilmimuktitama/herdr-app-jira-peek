//! User-facing lifecycle operations. Compatibility bridge commands stay separate.
pub mod bundle;
pub mod doctor;
pub mod fs;
pub mod install;
pub mod manifest;
mod process;
pub mod update;
use crate::{fail, Result};
use std::path::PathBuf;
fn default_home() -> Result<PathBuf> {
    let exe = std::env::current_exe()?;
    if let Some(runtime) = exe.parent() {
        if runtime.file_name().is_some_and(|n| n == "runtime") {
            if let Some(mod_dir) = runtime.parent() {
                if mod_dir.file_name().is_some_and(|n| n == "jira-peek") {
                    if let Some(mods) = mod_dir.parent() {
                        if mods.file_name().is_some_and(|n| n == "mods") {
                            return Ok(mods
                                .parent()
                                .ok_or_else(|| fail("invalid_app_home"))?
                                .to_path_buf());
                        }
                    }
                }
            }
        }
    }
    Ok(std::env::var_os("HERDR_APP_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".config/herdr-app")
        }))
}
pub fn run(args: &[String]) -> Result<()> {
    let command = args
        .first()
        .map(String::as_str)
        .ok_or_else(|| fail("management_command_required"))?;
    if command == "doctor" {
        if args.len() > 2 || (args.len() == 2 && args[1] != "--json") {
            return Err(fail("invalid_doctor_arguments"));
        }
        let report = doctor::report();
        if args.len() == 2 {
            println!("{report}");
        } else {
            println!("Jira Peek REST installation requirements (offline):");
            for (name, ok) in report["required"].as_object().unwrap() {
                println!(
                    "{}: {}",
                    name,
                    if *ok == true {
                        "available"
                    } else {
                        "missing or unsupported"
                    }
                );
            }
            println!(
                "herdr-app: {}; herdr-core: {} (independent versions)",
                report["herdr_app_version"]
                    .as_str()
                    .unwrap_or("unavailable"),
                report["herdr_core_version"]
                    .as_str()
                    .unwrap_or("unavailable")
            );
            println!("Git is required for release updates; TWG is optional for existing TWG connections.");
        }
        return if report["ok"] == true {
            Ok(())
        } else {
            Err(fail("missing_host_capabilities"))
        };
    }
    if command == "update" {
        let mut home = default_home()?;
        let mut selected = None;
        let mut check = false;
        let mut downgrade = false;
        let mut seen = std::collections::BTreeSet::new();
        let mut i = 1;
        while i < args.len() {
            let arg = args[i].as_str();
            if !seen.insert(arg) {
                return Err(fail("duplicate_management_argument"));
            }
            match arg {
                "--app-home" | "--version" => {
                    i += 1;
                    let v = args
                        .get(i)
                        .filter(|v| !v.starts_with("--"))
                        .ok_or_else(|| fail("missing_management_argument"))?;
                    if arg == "--app-home" {
                        home = PathBuf::from(v);
                        fs::safe_path(&home)?;
                    } else {
                        selected = Some(v.as_str());
                    }
                }
                "--check" => check = true,
                "--allow-downgrade" => downgrade = true,
                _ => return Err(fail("unsupported_management_argument")),
            }
            i += 1;
        }
        let result = update::run(&home, selected, check, downgrade);
        if result.is_err() && !check {
            report_state(&home);
        }
        return result;
    }
    let mut home = default_home()?;
    let mut source = None;
    let mut config = None;
    let mut check = false;
    let mut update = false;
    let mut backup = None;
    let mut i = 1;
    let mut seen = std::collections::BTreeSet::new();
    while i < args.len() {
        let arg = args[i].as_str();
        if !seen.insert(arg) {
            return Err(fail("duplicate_management_argument"));
        }
        match arg {
            "--app-home" | "--source-root" | "--config-dir" => {
                i += 1;
                let value = args
                    .get(i)
                    .filter(|s| !s.starts_with("--"))
                    .ok_or_else(|| fail("missing_management_argument"))?;
                let p = PathBuf::from(value);
                fs::safe_path(&p)?;
                match arg {
                    "--app-home" => home = p,
                    "--source-root" => source = Some(p),
                    _ => config = Some(p),
                }
            }
            "--check" => check = true,
            "--update" => update = true,
            "--attach" => return Err(fail("attachment_requires_coordinator_integration")),
            s if command == "rollback" && !s.starts_with('-') && backup.is_none() => {
                backup = Some(s)
            }
            _ => return Err(fail("unsupported_management_argument")),
        }
        i += 1;
    }
    match command {
        "install" => {
            let result = install::install(install::Request {
                source_root: source
                    .as_deref()
                    .ok_or_else(|| fail("source_root_required"))?,
                app_home: &home,
                config_dir: config.as_deref(),
                check,
                update,
            });
            if result.is_err() {
                report_state(&home);
            }
            result.map(|_| ())
        }
        "rollback" if source.is_none() && config.is_none() && !update => {
            let result = install::rollback(
                &home,
                backup.ok_or_else(|| fail("backup_name_required"))?,
                check,
            );
            if result.is_err() {
                report_state(&home);
            }
            result.map(|_| ())
        }
        _ => Err(fail("unsupported_management_command")),
    }
}

#[cfg(test)]
mod tests;

/// A failed acknowledgement is not proof of rollback. Report only validated state.
pub fn report_state(home: &std::path::Path) {
    if fs::safe_path(home).is_err() {
        return;
    }
    match manifest::managed(&home.join("mods/jira-peek")) {
        Ok(m) => eprintln!("Installed Jira Peek {} is confirmed; toolbar/layout integration is unverified.", m["version"].as_str().unwrap()),
        Err(_) => eprintln!("Installed state is unconfirmed. Inspect the installation and replacement journal before retrying; no integration success is claimed."),
    }
}
