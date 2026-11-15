use crate::{fail, Result};
use std::{
    io::{Read, Seek, SeekFrom},
    process::{Command, Stdio},
    time::{Duration, Instant},
};
/// Bounded duration and disk-backed output avoid pipe deadlocks. Never relay stderr.
pub fn run(command: &mut Command, seconds: u64) -> Result<Vec<u8>> {
    let mut output = tempfile::tempfile()?;
    let mut child = command
        .stdin(Stdio::null())
        .stdout(output.try_clone()?)
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| fail("management_command_failed"))?;
    let start = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            if !status.success() {
                return Err(fail("management_command_failed"));
            }
            break;
        }
        if start.elapsed() > Duration::from_secs(seconds) || output.metadata()?.len() > 1024 * 1024
        {
            let _ = child.kill();
            let _ = child.wait();
            return Err(fail("management_command_timeout"));
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    if output.metadata()?.len() > 1024 * 1024 {
        return Err(fail("management_output_too_large"));
    }
    output.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    output.read_to_end(&mut bytes)?;
    Ok(bytes)
}
pub fn isolated(command: &mut Command, base: &std::path::Path) {
    let path = std::env::var_os("PATH").unwrap_or_default();
    command
        .env_clear()
        .env("PATH", path)
        .env("HOME", base)
        .env("LANG", "C")
        .env("HERDR_APP_HOME", base.join("app"))
        .env("HERDR_TELEMETRY", "0")
        .env("HC_SESSION", "jira-peek-check")
        .env("HC_SOCKET", base.join("hc.sock"));
    for (key, dir) in [
        ("XDG_STATE_HOME", "state"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_RUNTIME_DIR", "run"),
    ] {
        command.env(key, base.join(dir));
    }
}
