//! Lifecycle wiring for personal layout preparation; never switches a layout.
use super::{doctor, fs, install, integration as panel, manifest, process};
use crate::{fail, Result};
use serde_json::Value;
use std::{
    path::{Path, PathBuf},
    process::Command,
};

fn quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}
fn helper(home: &Path) -> String {
    quote(
        &home
            .join("mods/jira-peek/runtime/jira-peek-bridge")
            .to_string_lossy(),
    )
}
fn repair_guidance(home: &Path, source: &str) {
    println!(
        "Repair integration: {} manage integration repair --app-home {} --layout {}",
        helper(home),
        quote(&home.to_string_lossy()),
        quote(source)
    );
}
fn prepared(home: &Path, result: &panel::AttachmentPlan, cleanup: &panel::CleanupReport) {
    println!(
        "Prepared personal layout {}. Existing source layout and keys were preserved.",
        result.name
    );
    if cleanup.removed > 0 {
        println!(
            "Removed {} verified abandoned staging files.",
            cleanup.removed
        );
    }
    if cleanup.preserved > 0 {
        println!(
            "Preserved {} unverified staging files for review.",
            cleanup.preserved
        );
    }
    select_guidance(home, &result.name);
}
fn select_guidance(home: &Path, name: &str) {
    println!(
        "Select when ready: HERDR_APP_HOME={} herdr-app do layout.switch {}",
        quote(&home.to_string_lossy()),
        quote(&serde_json::json!({"name":name}).to_string())
    );
    println!("Button rendering is unverified; check hide and reopen in Herdr.");
}
fn integration_failure(error: panel::IntegrationError) -> crate::Error {
    eprintln!("{error}");
    fail("integration_incomplete_files_preserved")
}
fn check_toolbar(staged: &Path) -> std::result::Result<(), panel::IntegrationError> {
    let check = || -> Result<()> {
        if doctor::report()["ok"] != true {
            return Err(fail("missing_host_capabilities"));
        }
        let temporary = tempfile::tempdir()?;
        let base = temporary.path().canonicalize()?;
        install::mkdir(&base.join("run"))?;
        let mut command = Command::new("herdr-app");
        command.arg("check").arg(staged);
        process::isolated(&mut command, &base);
        process::run(&mut command, 60)?;
        Ok(())
    };
    check().map_err(|_| panel::IntegrationError::NativeCheck)
}

/// Holds one existing lifecycle lock across plan/check, bundle and personal files.
pub fn install_attached(
    request: install::Request<'_>,
    expected: Option<&Value>,
    attach: Option<&str>,
) -> Result<PathBuf> {
    fs::safe_path(request.source_root)?;
    fs::safe_path(request.app_home)?;
    let home = request.app_home;
    let mods = home.join("mods");
    install::mkdir(&mods)?;
    let _lock = fs::InstallLock::acquire(&mods)?;
    install::recover(&mods)?;
    let automatic = request.update && attach.is_none();
    let source = attach.or(if automatic { Some("main") } else { None });
    let mut plan = match source.map(|s| panel::plan_attachment(home, s, true)) {
        Some(Ok(plan)) => Some(plan),
        Some(Err(error)) if automatic => {
            println!("Automatic toolbar preparation skipped; personal files preserved. {error}");
            None
        }
        Some(Err(error)) => return Err(integration_failure(error)),
        None => None,
    };
    if request.check {
        if let Some(candidate) = plan.as_ref() {
            let checked = candidate.toolbar_directory().and_then(|directory| {
                panel::check_attachment(candidate, &directory, check_toolbar)
            });
            if let Err(error) = checked {
                if !automatic {
                    return Err(integration_failure(error));
                }
                println!(
                    "Automatic toolbar validation failed; integration files preserved. {error}"
                );
                plan = None;
            }
        }
    }
    let destination = install::install_locked(request, expected)?;
    if let Some(plan) = plan {
        match panel::apply_attachment_report(&plan, home) {
            Ok(cleanup) => prepared(home, &plan, &cleanup),
            Err(error) => {
                println!("Bundle installed successfully; toolbar integration is incomplete and may be partial. {error}");
                repair_guidance(home, source.unwrap_or("main"));
            }
        }
    } else if automatic {
        repair_guidance(home, "main");
    }
    Ok(destination)
}

pub fn repair(home: &Path, source: &str) -> Result<()> {
    let mods = home.join("mods");
    let destination = mods.join("jira-peek");
    let result = panel::repair_integration(
        home,
        source,
        true,
        |work| {
            let _lock = fs::InstallLock::acquire(&mods).map_err(|_| panel::IntegrationError::Io)?;
            install::recover(&mods).map_err(|_| panel::IntegrationError::Io)?;
            work()
        },
        || manifest::managed(&destination).map_err(|_| panel::IntegrationError::BundleChanged),
        check_toolbar,
    )
    .map_err(integration_failure)?;
    prepared(home, &result.plan, &result.cleanup);
    Ok(())
}

pub fn diagnose(home: &Path, source: Option<&str>) -> Result<()> {
    fs::safe_path(home)?;
    let destination = home.join("mods/jira-peek");
    let validated = manifest::managed(&destination).ok();
    let bundle = if validated.is_some() {
        panel::BundleState::Valid
    } else if std::fs::symlink_metadata(&destination).is_ok() {
        panel::BundleState::Invalid
    } else {
        panel::BundleState::Missing
    };
    println!(
        "Bundle installed: {}",
        match &bundle {
            panel::BundleState::Valid => format!(
                "Jira Peek {} (validated)",
                validated.as_ref().unwrap()["version"].as_str().unwrap()
            ),
            panel::BundleState::Invalid => "present; managed bundle validation failed".into(),
            panel::BundleState::Missing => "not installed".into(),
        }
    );
    let mut command = Command::new("herdr-app");
    command.arg("status").env("HERDR_APP_HOME", home);
    let active = process::run(&mut command, 5)
        .ok()
        .map(|bytes| panel::parse_active_layout(&bytes))
        .unwrap_or_default();
    let report =
        panel::diagnose_integration(home, source, active, bundle).map_err(integration_failure)?;
    println!(
        "Active layout: {}",
        report.active.name.as_deref().unwrap_or("unavailable")
    );
    for (label, layout) in [
        ("Active", &report.active_layout),
        ("Source", &report.source_layout),
    ] {
        if let Some(layout) = layout {
            println!("{label} toolbar mod: {}", layout.toolbar);
            println!(
                "{label} Jira Peek panel ID: {}",
                layout
                    .panel_id
                    .as_ref()
                    .map(|s| serde_json::json!(s).to_string())
                    .unwrap_or_else(|| "none or ambiguous".into())
            );
        }
    }
    if let Some(source) = &report.source {
        println!("Source layout: {source}");
    }
    println!(
        "Automatic integration support: {}",
        report
            .unsupported
            .as_ref()
            .map(ToString::to_string)
            .unwrap_or_else(|| if report.source.is_some() {
                "supported stock toolbar structure".into()
            } else {
                "unavailable without a source layout".into()
            })
    );
    let state = match report.prepared {
        panel::PreparedIntegration::None => "none",
        panel::PreparedIntegration::Matching => "matching files",
        panel::PreparedIntegration::PartialOrConflicting => {
            "partial or conflicting files; preserved"
        }
        panel::PreparedIntegration::ExistsUnverified => "exists; unverified",
        panel::PreparedIntegration::Unverified => "unverified",
    };
    println!(
        "Prepared integration layout: {} ({state})",
        report.prepared_name.as_deref().unwrap_or("unavailable")
    );
    println!(
        "Active integration configured: {}",
        match report.configured {
            panel::ConfiguredIntegration::Yes => "yes (selected layout and files match)",
            panel::ConfiguredIntegration::No => "no",
            panel::ConfiguredIntegration::Unavailable => "unavailable",
            panel::ConfiguredIntegration::HostErrors => "unverified (Herdr reports errors)",
            panel::ConfiguredIntegration::Unverified => "unverified",
        }
    );
    let source = report.source.as_deref().unwrap_or("main");
    match report.next_action {
        panel::NextAction::InstallBundle => println!(
            "Next action: install from a complete source package with manage install --check."
        ),
        panel::NextAction::PreserveBundle => println!(
            "Next action: preserve the existing bundle and local edits before reinstalling."
        ),
        panel::NextAction::Repair | panel::NextAction::ChooseSource => {
            repair_guidance(home, source)
        }
        panel::NextAction::SelectLayout => {
            select_guidance(home, report.prepared_name.as_deref().unwrap())
        }
        panel::NextAction::PreserveConflicts => {
            println!(
                "Preserve conflicting files: {}",
                report
                    .conflicts
                    .iter()
                    .map(|p| quote(&p.to_string_lossy()))
                    .collect::<Vec<_>>()
                    .join(", ")
            );
            println!("{}", panel::manual_integration_guidance(home, source));
        }
        panel::NextAction::InspectHostErrors => {
            println!("Next action: inspect herdr-app status and resolve its errors.")
        }
        panel::NextAction::VerifyButton => {
            println!("Next action: verify the Jira Peek toggle; hide and reopen the panel.")
        }
        panel::NextAction::ManualIntegration => {
            println!("{}", panel::manual_integration_guidance(home, source))
        }
    }
    debug_assert!(!report.rendering_verified);
    println!("Button rendering is unverified; status and files do not establish visible UI.");
    Ok(())
}
