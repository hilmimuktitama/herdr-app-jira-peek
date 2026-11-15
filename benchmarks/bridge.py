#!/usr/bin/env python3
"""Compare shell/Rust or two Rust builds on identical fictional responses."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
from fixture import Fixture
ROOT=Path(__file__).resolve().parents[1]

def percentile(values,p): return sorted(values)[math.ceil(len(values)*p)-1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples",type=int,default=60)
    parser.add_argument("--warmup",type=int,default=5)
    parser.add_argument("--binary",type=Path,default=ROOT/"rust-backend/target/release/jira-peek-bridge")
    parser.add_argument("--baseline-binary",type=Path,help="Compare an existing Rust reader instead of the shell oracle")
    parser.add_argument("--baseline-revision",help="Declared source revision for the separately built baseline")
    parser.add_argument("--operation-offset",type=int,default=0,help="Rotate operation order across independent runs")
    parser.add_argument("--output",type=Path,default=Path("/tmp/jira-peek-perf-evidence/bridge-benchmark.json"))
    args=parser.parse_args()
    if args.samples<20: parser.error("Use at least 20 samples for p95")
    if args.warmup<0: parser.error("Warmup must be nonnegative")
    if args.output.resolve().is_relative_to(ROOT): parser.error("Keep benchmark evidence outside the repository")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report={"completed":False,"started_at":datetime.now(timezone.utc).isoformat()}
    # Reserve a new report before any preflight can fail. Never reuse old success.
    with args.output.open('x') as stream: json.dump(report,stream,indent=2)
    def persist():
        partial=args.output.with_suffix(args.output.suffix+'.partial')
        partial.write_text(json.dumps(report,indent=2)+'\n'); partial.replace(args.output)
    build_info=json.loads(subprocess.check_output([str(args.binary.resolve()),"--build-info"],text=True))
    if build_info.get("fixtureTransport") is not True: parser.error("Use a fixture-http build for loopback benchmarking")
    baseline="baseline" if args.baseline_binary else "shell"
    baseline_info=None
    if args.baseline_binary:
        baseline_info=json.loads(subprocess.check_output([str(args.baseline_binary.resolve()),"--build-info"],text=True))
        if baseline_info.get("fixtureTransport") is not True: parser.error("Baseline must also be a fixture-http build")
    started=time.monotonic()
    started_at=report['started_at']
    with tempfile.TemporaryDirectory(prefix="fixture-",dir=args.output.parent) as tmp:
        root=Path(tmp); fixture=Fixture(root,tls=True,populated=True)
        try:
            config=root/"config";config.mkdir()
            netrc=root/"fictional.netrc";netrc.write_text("machine jira.example.test login fictional password fictional\n");netrc.chmod(0o600)
            (config/"config.sh").write_text(f"JIRA_BASE='https://jira.example.test'\nJIRA_BACKEND='rest'\nJIRA_NETRC_FILE='{netrc}'\nJIRA_PROJECTS='ABC'\n")
            curl=root/"fixture-curl";curl_binary=fixture.curl_wrapper(curl)
            env={k:v for k,v in os.environ.items() if not k.startswith(("HERDR_","VIEWER_","TWG_","CURL_","SSL_","JIRA_PEEK_"))}
            env.update(JIRA_PEEK_FIXTURE_HTTP=fixture.url,JIRA_PEEK_FIXTURE_CA=str(fixture.certificate),CURL_BIN_PATH=str(curl),TWG_BIN_PATH="/nonexistent/fictional")
            measured=root/'candidate';shutil.copy2(args.binary.resolve(),measured)
            commands={baseline:["sh",str(ROOT/"scripts/app-bridge.sh")],"rust":[str(measured)]}
            if args.baseline_binary:
                prior=root/'baseline';shutil.copy2(args.baseline_binary.resolve(),prior)
                commands[baseline]=[str(prior)]
            states={kind:root/(kind+"-state") for kind in commands}
            def run(kind,op,*params):
                start=time.perf_counter_ns()
                p=subprocess.run([*commands[kind],op,str(config),str(states[kind]),*params],env=env,capture_output=True,text=True,check=True)
                elapsed=(time.perf_counter_ns()-start)/1e6
                value=json.loads(p.stdout)
                if p.stderr or not value.get("ok"): raise RuntimeError(f"{kind}/{op} failed: {value.get('error','stderr')}")
                return elapsed,value
            contexts={k:run(k,"config")[1]["context"] for k in commands}
            for k in commands: run(k,"issue",contexts[k],"ABC-1")
            cases={"stamp":lambda k:run(k,"stamp"),"config":lambda k:run(k,"config"),"issue_cache":lambda k:run(k,"issue",contexts[k],"ABC-1"),"issue_forced":lambda k:run(k,"issue",contexts[k],"ABC-1","refresh"),"metadata":lambda k:run(k,"metadata",contexts[k],"ABC-1","ABC-2"),"comments":lambda k:run(k,"comments",contexts[k],"ABC-1")}
            order=list(cases); offset=args.operation_offset%len(order);order=order[offset:]+order[:offset]
            report={"binary_sha256":hashlib.sha256(measured.read_bytes()).hexdigest(),"rust_build_features":["fixture-http"],"platform":platform.system()+" "+platform.machine(),"samples":args.samples,"warmup":args.warmup,"transport":"identical fictional loopback HTTPS; Rust in-process libcurl"+(" on both sides" if args.baseline_binary else ", shell actual curl via exec wrapper"), "curl_version":subprocess.check_output([curl_binary,"--version"],text=True).splitlines()[0],"metadata_rows":2,"results":{},"operation_order":order}
            if args.baseline_binary:
                report.update(baseline_binary_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),baseline_build_info=baseline_info,baseline_source_revision=args.baseline_revision)
            report.update(binary_build_info=build_info,completed=False,started_at=started_at)
            revision=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True)
            report["source_revision"]=revision.stdout.strip() if revision.returncode==0 else None
            report["shell_source_sha256"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/"scripts").iterdir()) if p.suffix in (".sh",".jq")}
            report["cargo_manifest_sha256"]=hashlib.sha256((ROOT/"rust-backend/Cargo.toml").read_bytes()).hexdigest()
            report["rust_source_sha256"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [ROOT/"rust-backend/Cargo.lock",ROOT/"rust-backend/build.rs",*sorted(p for p in (ROOT/"rust-backend/src").rglob("*") if p.is_file())]}
            report["harness_sha256"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'benchmarks/fixture.py']}
            persist()
            for name in order:
                call=cases[name]
                samples={k:[] for k in commands}
                request_counts={k:[] for k in commands}
                for i in range(args.warmup+args.samples):
                    # Alternate order to reduce drift and first-run bias.
                    order=list(commands) if i%2==0 else list(reversed(commands))
                    outputs=[]
                    for k in order:
                        before=len(fixture.calls);elapsed,value=call(k)
                        count=len(fixture.calls)-before
                        expected=0 if name in ("stamp","config","issue_cache") else 1
                        if count!=expected: raise RuntimeError(f"Unexpected HTTP count {count} for {k}/{name}; expected {expected}")
                        if name=="metadata" and len(value["rows"])!=2: raise RuntimeError("Metadata fixture must return two rows")
                        value.pop("context",None)
                        if "issue" in value:value["issue"].pop("fetchedAt",None)
                        outputs.append(value)
                        if i>=args.warmup:samples[k].append(elapsed);request_counts[k].append(len(fixture.calls)-before)
                    if outputs[0]!=outputs[1]: raise RuntimeError(f"Projection mismatch in {name}")
                metrics={k:{"median_ms":statistics.median(v),"p95_ms":percentile(v,.95),"samples_ms":v,"http_requests":request_counts[k]} for k,v in samples.items()}
                metrics["reduction_percent"]={stat:100*(1-metrics["rust"][stat]/metrics[baseline][stat]) for stat in ("median_ms","p95_ms")}
                if not args.baseline_binary: metrics["target_met"]=all(x>=50 for x in metrics["reduction_percent"].values())
                report["results"][name]=metrics
                persist()
                print(f"{name}: {baseline} {metrics[baseline]['median_ms']:.2f}/{metrics[baseline]['p95_ms']:.2f} ms, Rust {metrics['rust']['median_ms']:.2f}/{metrics['rust']['p95_ms']:.2f} ms (median/p95)",flush=True)
            report.update(completed=True,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
            persist()
        finally: fixture.close()
if __name__=="__main__":main()
