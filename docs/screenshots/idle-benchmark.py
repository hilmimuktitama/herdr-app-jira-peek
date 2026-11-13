#!/usr/bin/env python3
"""Offline stock-host CPU and panel-render benchmark; no personal app/core access.

Compare --revision REF with the working tree using the same duration and host.
Panel renders and host window-render counters are measured, not physical display
presentations. Keep output outside Git.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from capture import ROOT, host_identity, select_app_binary, verify_host_identity


def cpu_seconds(pid):
    value = subprocess.check_output(["ps", "-p", str(pid), "-o", "time="], text=True).strip()
    parts = value.split(":")
    return sum(float(n) * 60 ** i for i, n in enumerate(reversed(parts)))


def frame_records(path):
    if not path.exists():
        return []
    # The host appends one JSON line per interval. An incomplete final line is
    # not a sample; leave it for the next read instead of inventing zero draws.
    text = path.read_text()
    return [json.loads(line) for line in text[:text.rfind("\n") + 1].splitlines() if line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Read this local Git revision's panel instead of working tree")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app-binary")
    parser.add_argument("--await-activation", action="store_true", help="Pause to raise the isolated window before measuring")
    parser.add_argument("--stop-polling", action="store_true", help="Diagnostic only; retain the recovery timer")
    args = parser.parse_args()
    if not 5 <= args.seconds <= 300:
        parser.error("Use 5–300 seconds")
    args.output = args.output.resolve()
    if args.output.is_relative_to(ROOT):
        parser.error("Keep machine-specific evidence outside the repository")
    app, core = select_app_binary(args.app_binary), shutil.which("hc")
    if not core:
        parser.error("hc is required")
    with tempfile.TemporaryDirectory(prefix="jp-idle-") as directory:
        base = Path(directory).resolve()
        home = base / "app"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "HC_", "TWG_", "CURL_"))}
        env.update(HERDR_APP_HOME=str(home), HERDR_TELEMETRY="0", HC_SESSION="jp-idle",
                   HERDR_APP_BENCH=str(base / "frames.jsonl"),
                   HERDR_RELEASES_URL="http://127.0.0.1:9", HC_SOCKET=str(base / "hc.sock"),
                   XDG_STATE_HOME=str(base / "state"), XDG_CONFIG_HOME=str(base / "config"),
                   XDG_CACHE_HOME=str(base / "cache"), XDG_RUNTIME_DIR=str(base / "run"))
        identity = host_identity(app, env)
        for p in (home / "layouts", base / "run", base / "config/herdr-core"):
            p.mkdir(parents=True, mode=0o700)
        (base / "config/herdr-core/config.toml").write_text("notes = false\n")
        subprocess.run([sys.executable, str(ROOT / "scripts/install-app.py"), "--app-home", str(home)],
                       env=env, check=True, stdout=subprocess.DEVNULL)
        (home / "settings.json").write_text(json.dumps({"core": core, "telemetry": False, "sounds": {"enabled": False}}))
        (home / "shared.json").write_text('{"frame.welcomed":"skipped"}')
        (home / "update-notes.json").write_text(json.dumps({"last_run": identity["version"].split()[-1], "presented": []}))
        config = home / "data/jira-peek/config/config.sh"
        config.write_text("JIRA_BASE='https://jira.example.test'\nJIRA_SITE='fictional'\nJIRA_PROJECTS='ABC'\nAUTO_REFRESH_SEC='1'\n")
        transport = base / "twg"
        transport.write_text('#!/bin/sh\nprintf \'{"accountId":"fictional-idle-reader"}\\n\'\n')
        transport.chmod(0o700)
        env["TWG_BIN_PATH"] = str(transport)
        mod = home / "mods/jira-peek"
        if args.revision:
            for name in ("main.js", "model.js"):
                (mod / name).write_bytes(subprocess.check_output(["git", "show", f"{args.revision}:mods/jira-peek/{name}"], cwd=ROOT))
        (mod / "main.js").rename(mod / "panel.js")
        (mod / "main.js").write_text('''
import Panel from "./panel.js";
import {props,appHome,writeTextFile} from "herdr";
export default class IdleBenchmark extends Panel {
  render(cx) { this.renders=(this.renders || 0)+1; return super.render(cx); }
  startScreen(cx,token) { this.reads=(this.reads || 0)+1; return super.startScreen(cx,token); }
  init(p,cx) {
    super.init(p,cx);
    cx.spawn(async cx => {
      for(let i=0;i<300 && !this.model.config;i++) await cx.sleep(100);
      if(!this.model.config) return;
      this.model.useSource(props().source); this.model.pinned=true; this.scan(cx); cx.notify();
      await cx.sleep(3000);
      if(props().stopPolling) this.timer?.cancel();
      const renders=this.renders, reads=this.reads, start=Date.now();
      await writeTextFile(appHome()+"/idle-ready.json",JSON.stringify({start}),null);
      await cx.sleep(props().seconds*1000);
      await writeTextFile(appHome()+"/idle-result.json",JSON.stringify({elapsedMs:Date.now()-start,
        panelRenders:this.renders-renders,screenReads:this.reads-reads,
        recoveryTimerRetained:!!this.rowWakeTimer,error:this.error || this.model.current.error || null}),null);
    });
  }
}
''')
        process = None
        try:
            source = subprocess.run([core, "run", "--bg", "--no-parent", "--no-notify", "--name", "fictional-idle",
                                     "--cwd", str(base), "/bin/sh", "-c", "printf 'Entirely fictional idle terminal\\n'; sleep 600"],
                                    env=env, capture_output=True, text=True, timeout=15, check=True)
            address = json.loads(source.stdout)["address"]
            (home / "layouts/idle.json").write_text(json.dumps({"id":"idle", "type":"block",
                "content":{"mod":"jira-peek","props":{"source":address,"seconds":args.seconds,"stopPolling":args.stop_polling}}}))
            with (base / "app.log").open("w") as log:
                process = subprocess.Popen([app], env=env, stdout=log, stderr=log)
                for _ in range(100):
                    ready = subprocess.run([app, "status"], env=env, capture_output=True, timeout=3)
                    if ready.returncode == 0: break
                    if process.poll() is not None: raise RuntimeError("Isolated app exited")
                    time.sleep(.1)
                if args.await_activation:
                    print("Isolated idle app home: " + str(home), flush=True)
                    input("Raise the isolated window, then press Enter to measure: ")
                subprocess.run([app, "do", "overlay.close", '{"id":"frame-welcome"}'], env=env, capture_output=True, timeout=5)
                subprocess.run([app, "do", "layout.switch", '{"name":"idle"}'], env=env, capture_output=True, timeout=5, check=True)
                for _ in range(400):
                    if (home / "idle-ready.json").exists(): break
                    time.sleep(.1)
                else: raise RuntimeError("Idle fixture failed to initialize")
                start_cpu, start = cpu_seconds(process.pid), time.monotonic()
                frame_offset = len(frame_records(base / "frames.jsonl"))
                for _ in range((args.seconds+10)*10):
                    if (home / "idle-result.json").exists(): break
                    time.sleep(.1)
                else: raise RuntimeError("Idle fixture failed to finish")
                elapsed, consumed = time.monotonic()-start, cpu_seconds(process.pid)-start_cpu
                result = json.loads((home / "idle-result.json").read_text())
                frames = frame_records(base / "frames.jsonl")[frame_offset:]
                result["hostFrames"] = {"samples": len(frames), "records": frames,
                    "windowRenderCalls": sum(row.get("window", 0) for row in frames)} if frames else None
                if result["error"]: raise RuntimeError("Isolated panel error: " + result["error"])
                verify_host_identity(app, env, identity)
                result.update(appCpuPercent=100*consumed/elapsed, cpuSeconds=consumed, cpuWallSeconds=elapsed,
                              revision=args.revision or "working-tree", stopPolling=args.stop_polling, host=identity,
                              activationPause=args.await_activation,
                              core=subprocess.check_output([core,"--version"],env=env,text=True).strip())
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(result,indent=2)+"\n")
                print(json.dumps(result,indent=2))
        finally:
            if process:
                subprocess.run([app,"do","app.quit"],env=env,capture_output=True,timeout=5)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
            subprocess.run([core,"server","stop"],env=env,capture_output=True,timeout=10)


if __name__ == "__main__":
    main()
