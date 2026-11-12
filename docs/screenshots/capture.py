#!/usr/bin/env python3
"""Capture native Herdr app frames using isolated, entirely fictional fixtures.

Requires herdr-app and hc; no Jira account or live session is used.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import plistlib
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def desktop_binaries():
    return [p / "Contents/MacOS/Herdr" for p in
            (Path("/Applications/Herdr.app"), Path.home() / "Applications/Herdr.app")]


def select_app_binary(binary=None):
    """Prefer the installed desktop on macOS over a potentially stale CLI link."""
    if binary is None and sys.platform == "darwin":
        available = [p for p in desktop_binaries() if p.is_file()]
        if len(available) > 1:
            raise RuntimeError("Multiple desktop bundles found; select one with --app-binary")
        binary = next(iter(available), None)
    binary = binary or shutil.which("herdr-app")
    if not binary:
        raise RuntimeError("herdr-app is required for native screenshots")
    path = Path(binary).expanduser().resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("Selected desktop binary is not executable")
    return str(path)


def host_identity(app, env):
    """Capture the executable itself, not just a version label or bundle plist."""
    path = Path(app)
    version = subprocess.check_output([app, "--version"], env=env, text=True, timeout=10).strip()
    if not version.startswith("herdr-app "):
        raise RuntimeError("Selected executable did not identify itself as herdr-app")
    identity = {"executable": str(path), "version": version,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if path.parent.name == "MacOS" and path.parent.parent.name == "Contents":
        bundle = path.parent.parent.parent
        with (bundle / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        identity["bundle_version"] = info.get("CFBundleShortVersionString")
        if identity["bundle_version"] != version.removeprefix("herdr-app "):
            raise RuntimeError("Desktop bundle metadata and executable versions differ; finish the host update before QA")
        if any(bundle.with_name(bundle.name + suffix).exists() for suffix in (".new", ".new.noindex")):
            raise RuntimeError("Desktop update is staged; finish it before QA to avoid testing a different host")
    return identity


def verify_host_identity(app, env, expected):
    if host_identity(app, env) != expected:
        raise RuntimeError("Desktop executable changed during native QA; results cannot be attributed to the selected host")


def capture_targets(output_dir=None):
    """Keep the public gallery small; explicit QA output retains every view."""
    captures = [
        ("peek-demo", ROOT / "preview.png"),
        ("peek-light", OUT / "app-light.png"),
        ("peek-help", OUT / "app-help.png"),
        ("peek-short", OUT / "app-short.png"),
    ]
    if output_dir is not None:
        captures += [("peek-" + name, OUT / filename) for name, filename in (
            ("narrow", "app-narrow.png"), ("reader", "app-reader.png"),
            ("refreshing", "app-refreshing.png"), ("loading", "app-loading.png"),
            ("paused", "app-paused.png"), ("refreshing-large", "app-refreshing-large.png"),
            ("options", "app-options.png"), ("browse", "app-browse.png"),
            ("excluded", "filtered-result.png"), ("lookup", "direct-lookup.png"),
            ("title-300", "title-300.png"), ("title-360", "title-360.png"),
            ("title-420", "title-420.png"),
            ("title-379", "title-379.png"), ("title-380", "title-380.png"),
            ("title-499", "title-499.png"), ("title-500", "title-500.png"),
            ("title-headers", "title-headers.png"),
        )]
        captures.extend([("peek-alignment", OUT / "alignment-300.png"),
                         ("peek-alignment-wide", OUT / "alignment-420.png"),
                         ("peek-alignment-large", OUT / "alignment-large.png")])
        captures.append(("peek-sticky", OUT / "sticky-scrolled.png"))
        captures.extend(("peek-key-" + name, OUT / ("keys-" + name + ".png"))
                        for name in ("300", "360", "420", "font16", "font20"))
        captures.append(("main-jira-peek", OUT / "app-toolbar.png"))
        captures.append(("workbench-jira-peek", OUT / "app-custom-toolbar.png"))
        captures = [(name, Path(output_dir) / target.name) for name, target in captures]
    return captures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", action="store_true", help="Capture native app frames (the default; retained for compatibility)")
    parser.add_argument("--app-review", action="store_true", help="Keep the isolated window open until Enter for interaction review")
    parser.add_argument("--row-stress", action="store_true", help="Exercise more than 10,000 native row allocations and retirements")
    parser.add_argument("--app-binary", type=Path, help="Desktop executable; defaults to the installed macOS bundle, otherwise herdr-app on PATH")
    parser.add_argument("--output-dir", type=Path, help="Write the full QA capture set here instead of the four documentation images")
    args = parser.parse_args()
    capture_app(args.app_binary, review=args.app_review, output_dir=args.output_dir, row_stress=args.row_stress)


def capture_app(binary=None, review=False, output_dir=None, row_stress=False):
    """Native app frames only; never use the person's app home or core socket."""
    if review and output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="jira-peek-frames-")
    output_dir = Path(output_dir).resolve() if output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        print("Fictional QA frames: " + str(output_dir), flush=True)
    app, core = select_app_binary(binary), shutil.which("hc")
    # A direct bundle executable lets macOS identify a separately named test
    # copy correctly; launching through a symlink can lose that bundle identity.
    app = str(Path(app).resolve()) if app else app
    if not app or not core:
        raise SystemExit("herdr-app and hc are required for native screenshots")
    with tempfile.TemporaryDirectory(prefix="peek-app-") as temporary:
        base = Path(temporary).resolve()
        home = base / "app"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "HC_", "TWG_", "CURL_"))}
        env.update(HERDR_APP_HOME=str(home), HERDR_TELEMETRY="0", HC_SESSION="jp",
                   HERDR_RELEASES_URL="http://127.0.0.1:9",
                   HC_SOCKET=str(base / "hc.sock"), XDG_STATE_HOME=str(base / "state"),
                   XDG_CONFIG_HOME=str(base / "config"), XDG_CACHE_HOME=str(base / "cache"),
                   XDG_RUNTIME_DIR=str(base / "run"))
        identity = host_identity(app, env)
        print("Native host: " + identity["version"] + " · " + app, flush=True)
        for directory in (home / "layouts", home / "mods/capture-context", base / "run", base / "config/herdr-core"):
            directory.mkdir(parents=True, mode=0o700)
        (base / "config/herdr-core/config.toml").write_text("notes = false\n")
        subprocess.run([sys.executable, str(ROOT / "scripts/install-app.py"), "--app-home", str(home)], env=env, check=True, stdout=subprocess.DEVNULL)
        (home / "settings.json").write_text(json.dumps({"core": core, "telemetry": False, "sounds": {"enabled": False}, "appearance": "dark"}))
        (home / "shared.json").write_text(json.dumps({"frame.welcomed": "skipped"}))
        app_version = identity["version"].split()[-1]
        (home / "update-notes.json").write_text(json.dumps({"last_run": app_version, "presented": []}))
        # Exercise the real async native exec/file-watch boundary as well as
        # the static demo. This transport has no network implementation.
        fixture_config = home / "data/jira-peek/config"
        (fixture_config / "config.sh").write_text("JIRA_BASE='https://jira.example.test'\nJIRA_SITE='jira-example'\nJIRA_PROJECTS='ABC'\n")
        fake_twg = base / "twg"
        fake_twg.write_text("#!" + sys.executable + '''
import json,os,re,sys,time
from pathlib import Path
if "whoami" in sys.argv:
    print('{"accountId":"fictional-native-reader"}'); sys.exit(0)
control=Path(os.environ["HERDR_APP_HOME"])/"fixture-response.json"
response=json.loads(control.read_text()) if control.exists() else {}
if response.get("mode") == "slow": time.sleep(6)
if response.get("mode") == "failure":
    print('{"error":"Fictional request failure"}'); sys.exit(1)
keys=[arg for arg in sys.argv if re.fullmatch(r"ABC-[0-9]+",arg)]
fields=sys.argv[sys.argv.index("--fields")+1] if "--fields" in sys.argv else ""
if response.get("delayIssue") and ("description" in fields or "--comments" in sys.argv): time.sleep(response["delayIssue"])
if response.get("metadataDelay") and fields and "description" not in fields and "--comments" not in sys.argv:
    (control.parent/"fixture-metadata-started").write_text("started")
    time.sleep(response["metadataDelay"])
if response.get("slowIssue") in keys:
    (control.parent/"fixture-issue-started").write_text("started")
    time.sleep(2)
def issue_links():
    return [{"id":str(i), "type":{"id":"1" if i < 2 else "2", "inward":"is blocked by", "outward":"relates to"},
        ("inwardIssue" if i < 2 else "outwardIssue"):{"key":"ABC-"+str(i+2),
            "fields":{"summary":"Fictional linked catalog item "+str(i+2), "status":{"name":"Open"}}}}
        for i in range(7)]
def issue(key):
    if response.get("rich"):
        summary="Keep catalog filters when returning from an item"
        description="Returning to the fictional catalog should restore filters and reading position.\\n\\n" + "\\n\\n".join("Acceptance step %d: keep the chosen category and price range visible. Keyboard and pointer navigation must preserve the reader's place." % i for i in range(1,13))
        if response.get("unreadReview"):
            summary="Viewport restoration" if key in ["ABC-201","ABC-202","ABC-203","ABC-204"] else "Catalog exports"
        if response.get("readerReview"):
            summary="Catalog exports" if int(key.split("-")[1]) % 2 else "Keep catalog filters when returning from a saved item"
            def paragraph(text): return {"type":"paragraph","content":[{"type":"text","text":text}]}
            def cell(kind,text): return {"type":kind,"content":[paragraph(text)]}
            table={"type":"table","content":[
                {"type":"tableRow","content":[cell("tableHeader",text) for text in ["Capability","Basic plan","Team plan"]]},
                {"type":"tableRow","content":[cell("tableCell",text) for text in ["Saved exports",
                    "Up to 7 days from the time a fictional catalog export finishes",
                    "Up to 42 days, including archived catalog versions kept for review, with the original category and selection preserved so reviewers can compare every saved version"]]}]}
            description={"type":"doc","content":[paragraph("This fictional catalog supports two export plans. Each retention limit belongs to its named plan."),table]
                + [paragraph("Reading checkpoint %d. Preserve the chosen category and price range when returning to the catalog. This passage must remain readable while the pointer rests over it." % i) for i in range(1,21)]}
        return {"key":key,"summary":summary, "status":{"name":"Awaiting cross-team review"},
            "assignee":{"displayName":"Alex Example"},"priority":{"name":"High"},
            "customfield_10016":0,"customfield_10017":{"type":"doc","content":[
                {"type":"paragraph","content":[{"type":"text","text":"Keep the catalog category when returning."}]},
                {"type":"paragraph","content":[{"type":"text","text":"Check keyboard and pointer navigation."}]}]},
            "labels":["catalog","navigation"],"duedate":None,
            "issuelinks":issue_links(),
            "description":description,
            "comments":[{"author":{"displayName":"Sam Sample"},"created":"2026-10-31T08:00:00Z","body":"Verified with entirely fictional catalog records."}]}
    return {"key":key,"summary":"Fictional native integration","status":{"name":"Open"},"issuelinks":issue_links(),"description":"Offline integration body","comments":[]}
if "--comments" in sys.argv: print(json.dumps({"data":issue(keys[0])}))
else: print(json.dumps({"data":{"items":[{"input":key,"ok":True,"data":issue(key)} for key in keys]}}))
''')
        fake_twg.chmod(0o700)
        env["TWG_BIN_PATH"] = str(fake_twg)
        # Exercise the real token-save helper without making any network call.
        fake_curl = base / "curl"
        fake_curl.write_text("#!" + sys.executable + "\n" + (OUT / "app-setup-curl.py").read_text())
        fake_curl.chmod(0o700)
        env["CURL_BIN_PATH"] = str(fake_curl)
        mod = home / "mods/jira-peek"
        (mod / "main.js").rename(mod / "panel.js")
        # Controlled host-setting input for real native font/layout checks.
        # This shim exists only in the disposable fictional fixture copy.
        panel_source = (mod / "panel.js").read_text()
        settings_import = "theme, settings, props,"
        if settings_import not in panel_source:
            raise RuntimeError("The font fixture must be updated for the current panel imports")
        panel_source = panel_source.replace(settings_import, "theme, settings as fixtureSettings, props,", 1)
        # props() is scoped to the currently rendering entity. Forward the
        # controlled font to retained rows on creation and invalidation too.
        for constructor in ("SelectedIssueRow", "ResultRowActions"):
            token = f"return cx.new({constructor}, {{"
            if token not in panel_source:
                raise RuntimeError("The retained-row font fixture must be updated")
            panel_source = panel_source.replace(token, token + " fixtureUiFontSize: props()?.fixtureUiFontSize,", 1)
        panel_source = panel_source.replace(".set_props({ revision });",
            ".set_props({ revision, fixtureUiFontSize: props()?.fixtureUiFontSize });")
        panel_source += "\nfunction settings() { const value=fixtureSettings(); return props()?.fixtureUiFontSize ? {...value,ui_font_size:props().fixtureUiFontSize} : value; }\n"
        (mod / "panel.js").write_text(panel_source)
        (mod / "main.js").write_text('''
import Panel from "./panel.js";
import {props,terminals,appHome,readTextFile,writeTextFile,run,setShared,shared} from "herdr";
export default class NativeCheck extends Panel {
  renderIssueActions(...args) {
    if (!this.keyWidthFixture) return super.renderIssueActions(...args);
    // Exercise an enabled Open target with fictional cached data only.
    const demo = this.demo; this.demo = false;
    try { return super.renderIssueActions(...args); } finally { this.demo = demo; }
  }
  handleCommand(command, cx) {
    if (this.keyWidthFixture && ["fixture-key-short", "fixture-key-long"].includes(command)) {
      this.select(command === "fixture-key-short" ? "DEMO-2" : "ORBITALCATALOG-123456", cx, false, false);
      this.updateSelectedRows(cx); cx.notify(); return;
    }
    return super.handleCommand(command, cx);
  }
  async bridge(...args) {
    if (["issue", "metadata"].includes(args[0])) this.fixtureJiraReads=(this.fixtureJiraReads || 0)+1;
    return super.bridge(...args);
  }
  newResultActions(cx,index) {
    this.rowStressCreated=(this.rowStressCreated || 0)+1;
    return super.newResultActions(cx,index);
  }
  openIssue(cx) {
    if (!this.keyWidthFixture && !props()?.review) return super.openIssue(cx);
    // Record the real action's URL boundary without opening an external site.
    const demo=this.demo;
    if(this.keyWidthFixture) this.demo=false;
    try {
      return super.openIssue({open_url:url => {
        const requests=shared("fixture.open-urls") || [];
        setShared("fixture.open-urls",[...requests,url]); cx.notify();
      }});
    } finally { this.demo=demo; }
  }
  keyDown(event,cx,context) {
    if(props()?.review && String(event.key).toLowerCase() === "tab") this.reviewFocusEvent=Date.now();
    return super.keyDown(event,cx,context);
  }
  render(cx) {
    const activity=props()?.review && this.reviewReady && shared("fixture.activity");
    if(activity && this.model.config && activity.number !== this.reviewActivity) {
      this.reviewActivity=activity.number;
      cx.spawn(async cx => {
        await cx.sleep(500);
        const template=this.model.details.get(this.model.current?.selected);
        if(!template) return;
        const matches=["ABC-201","ABC-202","ABC-203","ABC-204"];
        const keys=[...matches,"ABC-1","ABC-2",...Array.from({length:6},(_,i)=>`ABC-${211+i}`)];
        const state=this.model.current;
        state.keys=keys; state.unseen.clear(); state.snapshot="ABC-2";
        for(const key of keys) this.model.accept({...template,key,summary:matches.includes(key)?"Viewport restoration":"Catalog exports",values:[]});
        this.model.filter(""); this.syncInput(); this.select(matches[0],cx); cx.notify();
      });
    }
    const trial=props()?.review && this.reviewReady && shared("fixture.open");
    if(trial && this.model.config && trial.key !== this.reviewTrialKey) {
      this.reviewTrialKey=trial.key;
      cx.spawn(async cx => {
        await cx.sleep(1);
        this.model.merge([trial.key]);
        this.model.metadata.set(trial.key,{key:trial.key,summary:trial.summary,status:"Awaiting cross-team review"});
        this.select(trial.key,cx); cx.notify();
      });
    }
    const root = super.render(cx);
    if (props()?.review) {
      const state = {query:this.input.value(), modelQuery:this.model.current?.query,
        rows:this.model.rows(), total:this.model.current?.keys.length, unread:[...(this.model.current?.unseen || [])],
        compact:this.model.compactSlots?.().map(slot=>({id:slot.id,key:slot.key})),
        uiFont:props()?.fixtureUiFontSize || 13,
        actionKey:this.issueActionKey(), typing:!!this.typing, reader:(!this.issuesExpanded),
        selected:this.model.current?.selected, follow:this.model.current?.follow,
        pinnedIssue:this.model.current?.pinnedIssueKey,
        loaded:this.model.details.has(this.model.current?.selected), caption:this.focusCaption,
        copyValue:this.copyValue, copyNote:this.copyNote,
        width:this.width,height:this.height,focusEvent:this.reviewFocusEvent,
        loading:!!this.loading, origin:this.origin, focused:this.isPeekFocused(),
        readerFocused:this.readerHandle.is_focused(), helpFocused:this.helpHandle.is_focused(),
        helpTopic:this.helpTopic, helpExpanded:this.helpExpanded,
        control:Object.keys(this.actionFocus).find(id=>this.actionFocus[id].is_focused())};
      const text = JSON.stringify(state);
      if (text !== this.keyboardSnapshot) { this.keyboardSnapshot=text; setShared("fixture.keyboard",state); }
    }
    return root;
  }
  init(p,cx) {
    this.keyWidthFixture = props()?.captureScreen === "key-widths";
    super.init(p,cx);
    if (["refreshing", "refreshing-large", "loading"].includes(props()?.captureScreen)) {
      const key=this.model.current.selected;
      if (props().captureScreen === "loading") this.model.details.delete(key);
      this.request={phase:"issue",key};
    }
    if (props()?.captureScreen === "paused") {
      const config=this.model.config; this.model.reset(config); this.model.useSource("t-fictional-paused");
      this.model.merge(["DEMO-1042", "DEMO-1038"]);
    }
    if (props()?.demo) {
      this.live=false;
      for(const issue of this.model.details.values()) issue.fetchedAt=Date.parse("2026-11-01T08:45:00Z");
      if (props().captureScreen === "options") this.moreOpen=true;
      if (props().captureScreen === "help") { this.helpTopic="options"; this.helpExpanded="Keyboard"; }
      if (props().captureScreen === "browse") this.issuesExpanded = true;
      if (props().captureScreen === "alignment") {
        for (const issue of [...this.model.details.values()]) this.model.accept({...issue, status:"In Progress"});
        this.issuesExpanded=true; this.model.select("DEMO-1042");
      }
      if (props().captureScreen === "key-widths") {
        this.model.config.projects.push("ORBITALCATALOG");
        const keys=["DEMO-2", "ORBITALCATALOG-123456"];
        this.model.merge(keys);
        for(const key of keys) this.model.accept({key,summary:"Fictional key layout",status:"In Progress",
          fetchedAt:Date.parse("2026-11-01T08:45:00Z"),description:"Entirely fictional key and hover review."});
        this.issuesExpanded=true; this.model.filter("Fictional key layout"); this.syncInput();
        this.model.select(keys[0]);
      }
      if (props().captureScreen === "sticky") {
        this.issuesExpanded=true;
        const keys=Array.from({length:12},(_,i)=>`DEMO-${2000+i}`);
        this.model.merge(keys);
        for(const key of keys) this.model.accept({key,summary:`Fictional catalog task ${key}`,status:"In Review"});
        this.model.select("DEMO-1042"); this.model.toggleIssuePin("DEMO-1042");
        this.model.select("DEMO-2005");
        cx.spawn(async cx => { await cx.sleep(500); this.listScroll.scroll_to_item(5,"top"); cx.notify(); });
      }
      if (props().captureScreen === "long-title") {
        const key="DEMO-1042", issue=this.model.details.get(key);
        if(props().fixtureHeaders) {
          this.fieldLayout={...this.currentFieldLayout(),fields:[...this.currentFieldLayout().fields,
            {id:"customfield_10016",label:"Acceptance",section:"header"},
            {id:"customfield_10017",label:"Context",section:"header"}]};
          issue.metadata.push({id:"customfield_10016",value:"Keep fictional category and price filters"},
            {id:"customfield_10017",value:"Fictional header content ".repeat(12)});
        }
        this.model.accept({...issue,summary:"Preserve catalog category and price filters when returning from a saved item after changing the sorting order"});
        this.issuesExpanded=true; this.model.filter(key); this.syncInput(); this.reconcilePreview(cx,"query");
      }
      if (["excluded","lookup"].includes(props().captureScreen)) {
        this.issuesExpanded = true;
        this.model.filter(props().captureScreen === "excluded" ? "empty-results" : "DEMO-2500"); this.syncInput();
        this.reconcilePreview(cx,"query");
      }
    }
    if (props()?.review) {
      this.issuesExpanded = false; this.live=false;
      cx.spawn(async cx => {
        for(let i=0;i<200 && !this.model.config;i++) await cx.sleep(100);
        if(!this.model.config || !props().source) return;
        this.model.useSource(props().source); this.model.pinned=true;
        if(props().many) this.model.merge(Array.from({length:30},(_,i)=>`ABC-${i+1}`));
        this.scan(cx); this.pump(cx); this.reviewReady=true; cx.notify();
      });
    }
    if (props()?.rowStress) {
      this.issuesExpanded=true;
      const keys=Array.from({length:200},(_,i)=>`DEMO-${6000+i}`);
      this.model.merge(keys); this.model.select(keys[0]);
      cx.spawn(async cx => {
        let peak=0,cycles=0;
        try {
          await cx.sleep(100);
          for(;cycles<3000 && (this.rowStressCreated || 0)<12000;cycles++) {
            for(const row of this.resultActionRows.values()) row.release();
            this.updateSelectedRows(cx);
            this.listScroll.scroll_to_item((cycles*7)%190,"top");
            cx.notify(); await cx.sleep(20);
            peak=Math.max(peak,this.resultActionRows.size);
            if(peak>7) throw new Error("Native action viewport exceeded its bound");
          }
          if(this.rowStressCreated<10000) throw new Error("Native stress did not cross the retained-object limit cumulatively");
          this.issuesExpanded=false; cx.notify(); await cx.sleep(100);
          if(this.resultActionRows.size) throw new Error("Collapsed native list retained actions");
          await writeTextFile(appHome()+"/row-stress.json",JSON.stringify({ok:true,cycles,created:this.rowStressCreated,peakActions:peak,collapsedActions:this.resultActionRows.size}),null);
        } catch(error) {
          await writeTextFile(appHome()+"/row-stress.json",JSON.stringify({ok:false,error:String(error),cycles,created:this.rowStressCreated}),null);
        }
      });
    }
    if (!props()?.integration) return;
    cx.spawn(async cx => {
      let waitStep = 0;
      const wait = async predicate => {
        waitStep++;
        for(let i=0;i<200;i++) { if(predicate()) return; await cx.sleep(100); }
        throw new Error("Timed out waiting for native state at step "+waitStep);
      };
      try {
        await wait(()=>this.model.config);
        this.openSetup(cx);
        await wait(()=>this.setup && !this.setup.loading && this.formInputFocus === this.setup.base);
        const setupForm=this.setup;
        this.saveSetup(cx); // Empty fictional token: validate locally, never contact Jira.
        await wait(()=>setupForm.error && this.formInputFocus === setupForm.token);
        this.cancelSetup(cx);
        const source=props().source;
        await wait(()=>terminals().some(t=>t.address === source));
        this.model.useSource(source); this.model.pinned=true; this.scan(cx);
        await wait(()=>this.model.current.keys.includes("ABC-2"));
        if(this.model.current.follow || this.model.current.activated || this.model.current.selected || this.fixtureJiraReads)
          throw new Error("Paused startup performed Jira reads or selected an issue");
        if(!this.model.current.unseen.has("ABC-2")) throw new Error("Paused startup lost unread discovery");
        this.model.follow(); this.pump(cx);
        await wait(()=>this.model.details.get("ABC-2"));
        if(this.model.current.keys.includes("ABC-1")) throw new Error("Automatic scan unexpectedly read history");
        this.history(cx);
        await wait(()=>this.model.current.keys.includes("ABC-1"));
        this.input.set_value("https://jira.example.test/browse/ABC-1?source=fictional"); this.submit(cx);
        await wait(()=>this.model.details.get("ABC-1"));
        if(this.model.details.get("ABC-1").summary !== "Fictional native integration") throw new Error("Wrong native issue");
        if(!(this.model.details.get("ABC-1").fetchedAt > 0)) throw new Error("Missing payload freshness timestamp");
        this.model.filter("catalog"); this.syncInput(); this.follow(cx);
        await cx.sleep(200);
        if(!this.model.current.follow || this.model.current.query) throw new Error("Follow was interrupted by native input synchronization");
        this.toggleIssues(cx);
        if((!this.issuesExpanded)) throw new Error("Issue browsing did not open");
        this.toggleIssues(cx);
        if(this.issuesExpanded) throw new Error("Compact reader did not reopen");
        this.search(cx); this.input.set_value("catalog");
        const selectedBeforeHelp=this.model.current.selected;
        run("jira-peek.options"); await wait(()=>this.moreOpen);
        run("jira-peek.help"); await wait(()=>this.helpTopic === "options" && !this.moreOpen);
        run("jira-peek.back"); await wait(()=>!this.helpTopic);
        if(this.moreOpen || (!this.issuesExpanded) || this.input.value()!=="catalog" || this.model.current.selected!==selectedBeforeHelp)
          throw new Error("Options help did not return to the retained filter and issue");
        run("jira-peek.help"); await wait(()=>this.helpTopic === "peek");
        run("jira-peek.options"); await wait(()=>!this.helpTopic && this.moreOpen);
        run("jira-peek.back"); await wait(()=>!this.moreOpen);
        // Programmatic InputState changes need not emit change. Clear must
        // update the model itself, including after a zero-result query.
        for(const query of ["ABC-1","no fictional match"]) {
          this.input.set_value(query); this.inputChanged(cx); this.issuesExpanded = true;
          await cx.sleep(100);
          if(query === "ABC-1" && this.model.current.selected !== "ABC-1")
            throw new Error("Native filtering did not preview the matching issue");
          // Filtering can deliberately replace an excluded selection. Clearing
          // preserves that preview, not the issue from before the query edit.
          const clearSelection=this.model.current.selected;
          this.clearFilter(cx); await cx.sleep(100);
          if(this.input.value() || this.model.current.query || this.model.rows().length!==this.model.current.keys.length ||
              this.model.current.selected!==clearSelection || this.model.current.follow)
            throw new Error("Native clear did not restore the complete result set: "+JSON.stringify({
              input:this.input.value(),query:this.model.current.query,rows:this.model.rows().length,
              keys:this.model.current.keys.length,selected:this.model.current.selected,expected:clearSelection,
              follow:this.model.current.follow,reader:(!this.issuesExpanded)}));
        }
        // Focus/typing is reviewed through real pointer and keyboard events,
        // not an InputState focus event in this background integration task.
        this.model.metadata.get("ABC-1").summary="NAV-S03: Preserve fictional catalog navigation";
        this.model.filter("NAV-S03"); this.syncInput(); await cx.sleep(100);
        this.submit(cx);
        if(this.model.current.selected!=="ABC-1" || this.lookupError) throw new Error("Native title lookup failed");
        this.model.filter("retained query"); this.syncInput();
        this.model.merge(["ABC-71"]); this.model.merge(["ABC-72"]); this.model.merge(["ABC-1"]);
        this.readNew(cx);
        if(this.model.current.selected!=="ABC-72" || this.model.current.follow || this.model.current.query!=="retained query" ||
            !this.model.current.unseen.has("ABC-71") || this.model.current.unseen.has("ABC-72"))
          throw new Error("Native unread navigation lost an arrival or browsing state");
        await wait(()=>!this.request && !this.backgroundRequest);
        this.model.filter(""); this.syncInput(); this.select("ABC-1",cx);
        await wait(()=>this.fieldFileText && !this.fieldFileError);
        const fieldPath=this.fieldFilePath(), originalFields=await readTextFile(fieldPath);
        const fieldFile=JSON.parse(originalFields), entry=fieldFile.connections[0];
        entry.fields.find(f=>f.id==="summary").label="Agent task brief";
        fieldFile.connections.push({configDir:"/fictional/other-connection",base:"https://other.example.test",fields:[]});
        let fieldText=JSON.stringify(fieldFile);
        await writeTextFile(fieldPath,fieldText,originalFields);
        await wait(()=>this.fieldLayout.fields.some(f=>f.label==="Agent task brief"));
        this.openFields(cx);
        this.fieldEditor.labels.get("summary").set_value("Stale draft");
        entry.fields.find(f=>f.id==="summary").label="New agent edit";
        const agentText=JSON.stringify(fieldFile);
        await writeTextFile(fieldPath,agentText,fieldText);
        await wait(()=>this.fieldLayout.fields.some(f=>f.label==="New agent edit"));
        this.applyFields(cx);
        if(!this.fieldEditor?.error) throw new Error("Stale field draft was not blocked");
        this.closeFields(cx); this.openFields(cx);
        this.fieldEditor.labels.get("summary").set_value("Saved in UI");
        this.addLinkedField(cx);
        if(!this.fieldEditor.fields.some(f=>f.id==="issuelinks" && f.label==="Linked Issues")) throw new Error("Linked Issues missing in Fields");
        this.applyFields(cx); await wait(()=>!this.fieldEditor);
        await wait(()=>this.model.details.get("ABC-1")?.metadata.some(f=>f.id==="issuelinks" && f.value.includes("is blocked by: ABC-2")));
        // Real focus handles must recover when a same-issue replacement
        // removes Show all/fewer. This does not simulate pointer/key input.
        const linkedData=this.model.details.get("ABC-1").metadata.find(f=>f.id==="issuelinks").links;
        const returnedLinks=linkedData.records;
        for(const all of [false,true]) for(const focused of [false,true]) {
          linkedData.records=returnedLinks; this.linkedAll=all; cx.notify(); await cx.sleep(100);
          (focused ? this.actionFocus["linked-more"] : this.readerHandle).focus();
          cx.notify(); await cx.sleep(100);
          if(!(focused ? this.actionFocus["linked-more"] : this.readerHandle).is_focused())
            throw new Error("Linked Issues fixture did not establish initial focus: "+JSON.stringify({all,focused}));
          linkedData.records=returnedLinks.slice(0,4); cx.notify();
          for(let i=0;i<10;i++) {
            await cx.sleep(100);
            if((focused ? this.actionFocus["linked-toggle"] : this.readerHandle).is_focused()) break;
          }
          if(!(focused ? this.actionFocus["linked-toggle"] : this.readerHandle).is_focused())
            throw new Error("Linked Issues count replacement lost or stole native focus: "+JSON.stringify({all,focused,
              pending:!!this.linkedFocusRecovery,more:this.actionFocus["linked-more"].is_focused(),
              toggle:this.actionFocus["linked-toggle"].is_focused(),reader:this.readerHandle.is_focused()}));
          if(this.linkedAll!==all) throw new Error("Count replacement reset the user's preview choice");
        }
        linkedData.records=returnedLinks; this.linkedAll=false; cx.notify();
        fieldText=await readTextFile(fieldPath);
        if(!JSON.parse(fieldText).connections.some(c=>c.configDir==="/fictional/other-connection")) throw new Error("Other connection lost");
        await writeTextFile(fieldPath,"{",fieldText);
        await wait(()=>this.fieldFileError);
        if(!this.fieldLayout.fields.some(f=>f.label==="Saved in UI")) throw new Error("Invalid edit replaced the working layout");
        await writeTextFile(fieldPath,originalFields,"{");
        await wait(()=>!this.fieldFileError && this.fieldFileText===originalFields);
        const preferenceFile=JSON.parse(originalFields);
        preferenceFile.preferences={autoRefresh:true,highlightSource:false};
        await writeTextFile(fieldPath,JSON.stringify(preferenceFile),originalFields);
        await wait(()=>this.live);
        if("highlightSource" in this && this.highlightSource!==undefined) throw new Error("Retired highlight preference still drives the panel");
        this.toggleLive(cx); await wait(()=>!this.preferencesSaving);
        const preferenceSaved=JSON.parse(await readTextFile(fieldPath));
        if(preferenceSaved.preferences.autoRefresh!==false) throw new Error("Options did not save reader preferences");
        if("highlightSource" in preferenceSaved.preferences) throw new Error("Retired highlight preference was written back");
        if(JSON.stringify(preferenceSaved.connections)!==JSON.stringify(preferenceFile.connections)) throw new Error("Preference save changed layouts");
        run("jira-peek.pause"); await wait(()=>!this.model.current.follow);
        run("jira-peek.resume"); await wait(()=>this.model.current.follow);
        run("jira-peek.unpin"); await wait(()=>!this.model.pinned);
        run("jira-peek.pin"); await wait(()=>this.model.pinned);
        run("jira-peek.fields"); await wait(()=>this.fieldEditor);
        this.fieldEditor.labels.get("summary").set_value("Unapplied native draft");
        run("jira-peek.reconnect"); await cx.sleep(100);
        if(!this.fieldEditor || this.fieldEditor.labels.get("summary").value()!=="Unapplied native draft") throw new Error("Command interrupted a field draft");
        run("jira-peek.back"); await wait(()=>!this.fieldEditor);
        run("jira-peek.back"); await wait(()=>!this.moreOpen);
        await writeTextFile(fieldPath,originalFields,await readTextFile(fieldPath));
        await wait(()=>this.fieldFileText===originalFields);
        await wait(()=>!this.request && !this.backgroundRequest);
        const control=appHome()+"/fixture-response.json";
        const writeControl=async value=>writeTextFile(control,JSON.stringify(value),await readTextFile(control));
        const waitFile=async path=>{
          for(let i=0;i<200;i++) { if(await readTextFile(path)) return; await cx.sleep(20); }
          throw new Error("Delayed backend did not start");
        };
        this.model.browse();
        this.model.merge(["ABC-81","ABC-82"]);
        if(this.model.rebuildResults) this.model.rebuildResults();
        await writeControl({metadataDelay:2}); this.pump(cx);
        await waitFile(appHome()+"/fixture-metadata-started");
        const metadataStart=Date.now(); this.select("ABC-81",cx,false);
        await wait(()=>this.model.details.has("ABC-81"));
        const metadataSelectionMs=Date.now()-metadataStart;
        if(this.backgroundRequest?.phase!=="metadata" && this.request?.phase!=="metadata")
          throw new Error("Selected issue waited for background metadata");
        await wait(()=>!this.request && !this.backgroundRequest);
        await writeControl({slowIssue:"ABC-83"});
        this.model.merge(["ABC-83","ABC-84"]);
        if(this.model.rebuildResults) this.model.rebuildResults();
        this.select("ABC-83",cx,false);
        await waitFile(appHome()+"/fixture-issue-started");
        const issueStart=Date.now(); this.select("ABC-84",cx,false);
        await wait(()=>this.model.details.has("ABC-84"));
        const supersededSelectionMs=Date.now()-issueStart;
        if(this.backgroundRequest?.key!=="ABC-83" && this.request?.key!=="ABC-83")
          throw new Error("Selected issue waited for the previous issue");
        await wait(()=>!this.request && !this.backgroundRequest);
        await writeControl({});
        const cachedStart=Date.now(); this.select("ABC-81",cx,false);
        const cachedSelectionMs=Date.now()-cachedStart;
        if(this.request || this.backgroundRequest || !this.model.detail("ABC-81"))
          throw new Error("Revisiting a cached issue started unnecessary work");
        const performance={metadataSelectionMs,supersededSelectionMs,cachedSelectionMs};
        // Clear is source-local and a real asynchronous screen read defines
        // its baseline. Newly printed fixture output must not revive old keys.
        for(const follow of [true,false]) {
          this.model.current.follow=follow; this.clearList(cx);
          await wait(()=>!this.model.current.baselinePending && !this.scanning);
          await cx.sleep(300);
          if(this.model.current.keys.length || this.model.current.follow!==follow || !this.typing)
            throw new Error("Native Clear did not preserve focus/Follow and suppress the baseline");
          const key=follow ? "ABC-90" : "ABC-91", discovery=appHome()+"/fixture-discovery";
          await writeTextFile(discovery,key,await readTextFile(discovery));
          await wait(()=>this.model.current.keys.includes(key));
          if(this.model.current.keys.length!==1 || this.model.current.selected!==(follow ? key : null))
            throw new Error("Native Clear selected an old or Paused issue");
          if(!follow && !this.model.current.unseen.has(key)) throw new Error("Paused Clear lost unread arrival");
          this.input.set_value(key); this.inputChanged(cx);
          await wait(()=>this.model.details.has(key));
        }
        const oldContext=this.model.config.context;
        run("jira-peek.clear-cache");
        await wait(()=>this.model.config && this.model.config.context !== oldContext);
        if(this.model.details.size) throw new Error("Clear retained stale issue details");
        const file=appHome()+"/data/jira-peek/config/config.sh";
        const before=await readTextFile(file);
        await writeTextFile(file,before+"# fictional drift check\\n",before);
        await wait(()=>this.error === "connection_changed");
        if(this.model.details.size) throw new Error("Native watch retained stale detail");
        run("jira-peek.reconnect");
        await wait(()=>this.model.config && this.error===null);
        // Native focus handles and InputState events, with retained drafts.
        for(const target of ["control","input","help","busy-input"]) {
          await wait(()=>!this.loading);
          this.openFields(cx); await cx.sleep(100);
          const draft=this.fieldEditor, input=draft.labels.get("summary");
          input.set_value("Fictional invalidated draft");
          if(target==="input" || target==="busy-input") input.focus();
          else if(target==="help") this.openHelp(cx);
          else this.actionFocus["fields-apply"].focus();
          await cx.sleep(100);
          if(target==="busy-input") draft.busy=true;
          this.invalidate(cx); await cx.sleep(100);
          if(this.fieldEditor!==draft || input.value()!=="Fictional invalidated draft") throw new Error("Invalidation lost Fields draft");
          if(target==="control" && !this.actionFocus["fields-back"].is_focused()) throw new Error("Invalidation focused an absent Fields control");
          if(target==="input" && this.formInputFocus!==input) throw new Error("Invalidation stole Fields input focus");
          if(target==="busy-input") {
            if(!this.rootFocus.is_focused()) throw new Error("Busy Fields retained disabled input focus");
            draft.busy=false;
          }
          if(target==="help") {
            if(!this.actionFocus["help-back"].is_focused()) throw new Error("Invalidation stole Help focus");
            this.closeHelp(cx);
          }
          this.applyFields(cx);
          if(!draft.error) throw new Error("Invalidated Fields draft was applied");
          this.closeFields(cx); this.connect(cx);
          await wait(()=>this.model.config && !this.loading);
        }
        const leasePath=this.fieldFilePath(), leaseOriginal=await readTextFile(leasePath);
        const leaseFile=JSON.parse(leaseOriginal); leaseFile.preferences.autoRefresh=true;
        await writeTextFile(leasePath,JSON.stringify(leaseFile),leaseOriginal);
        await wait(()=>this.live && this.autoRefreshPreference);
        const leaseSaved=await readTextFile(leasePath);
        this.lastInteraction=this.now()-5*60000;
        // Accelerate only this timer registration; its callback gets native cx.
        this.scheduleLive({timer:{after:(_ms,callback)=>cx.timer.after(1,callback)}});
        await wait(()=>this.idlePaused && !this.live);
        if(await readTextFile(leasePath)!==leaseSaved) throw new Error("Idle pause changed shared preferences");
        await this.loadFieldLayout(cx);
        if(this.live || !this.idlePaused) throw new Error("Preference reload renewed an expired lease");
        this.toggleLive(cx);
        if(!this.live || this.idlePaused || await readTextFile(leasePath)!==leaseSaved) throw new Error("Local resume wrote shared settings");
        this.toggleLive(cx); await wait(()=>!this.preferencesSaving);
        if(JSON.parse(await readTextFile(leasePath)).preferences.autoRefresh!==false) throw new Error("Explicit Off was not shared");
        this.timer?.cancel();
        await wait(()=>!this.request && !this.backgroundRequest && !this.scanning && !this.historyRead);
        this.model.config={...this.model.config,ttl:0};
        this.model.useSource(source); this.model.pinned=true;
        this.model.follow();
        this.model.merge(["ABC-501"]); this.pump(cx); await wait(()=>this.model.details.has("ABC-501"));
        this.model.merge(["ABC-502"]); this.pump(cx);
        if(this.model.details.has("ABC-501")) throw new Error("TTL-zero Follow retained its previous body");
        await wait(()=>this.model.details.has("ABC-502"));
        this.model.filter("no fictional match"); this.issuesExpanded=true; this.syncInput();
        const retainedBody=this.model.details.get("ABC-502");
        this.openHelp(cx); await cx.sleep(100); this.closeHelp(cx);
        if(this.model.details.get("ABC-502")!==retainedBody || this.issueActionKey()) throw new Error("TTL-zero visibility changed logical retention or action eligibility");
        // Fault injection: leave native timers running with no Promise row
        // worker. Queued actions must still settle exactly once.
        this.model.filter(""); this.syncInput(); this.select("ABC-502",cx,false,false);
        this.rowTask?.cancel(); this.rowWake=null;
        for(let cycle=0;cycle<3;cycle++) {
          this.queueRowAction("pin",this.issueContext());
          await wait(()=>this.model.current.pinnedIssueKey==="ABC-502");
          this.queueRowAction("pin",this.issueContext());
          await wait(()=>this.model.current.pinnedIssueKey===null);
        }
        this.queueRowAction("copy-key",this.issueContext());
        await wait(()=>this.rowActions.length===0 && this.copyValue==="ABC-502");
        await writeTextFile(appHome()+"/native-check.json",JSON.stringify({ok:true,performance,nativeActionFallback:true}),null);
      } catch(error) {
        await writeTextFile(appHome()+"/native-check.json",JSON.stringify({ok:false,error:String(error),waitStep,
          setup:this.setup ? {loading:this.setup.loading,busy:this.setup.busy,error:this.setup.error,
            pendingFocus:!!this.setup.pendingFocus,baseFocused:this.formInputFocus===this.setup.base} : null}),null);
      }
    });
  }
}
''')
        (home / "mods/capture-context/mod.json").write_text('{"place":"none"}')
        (home / "mods/capture-context/main.js").write_text('''
import {View,div} from "gpui-kit";
import {v_flex,h_flex} from "gpui-base";
import {theme} from "herdr";
export default class Context extends View {
  render() {
    const t=theme();
    const lines=["$ git log --oneline -4", "", "f1a2b3c  DEMO-1042 Preserve catalog filters", "a2b3c4d  DEMO-1038 Add an empty-results state", "b3c4d5e  DEMO-1026 Cache catalog thumbnails", "c4d5e6f  DEMO-1019 Keyboard navigation", "", "$ "];
    return v_flex().size_full().min_w(0).bg(t.canvas).p(28).gap(24)
      .child(h_flex().gap(10).items_center().child(div().w(8).h(8).rounded(4).bg(t.working)).child(div().font_semibold().child("Catalog / feature/preserve-filters")))
      .child(v_flex().rounded(12).border_1().border_color(t.border).bg(t.background).p(20).gap(8)
        .child(div().text_size(10).text_color(t.dim).child("FICTIONAL TERMINAL TRANSCRIPT"))
        .children(lines.map(line=>div().font_family("Geist Mono").text_size(12).text_color(t.foreground).child(line || " "))))
      .child(v_flex().gap(12).child(div().text_size(26).font_semibold().child("Keep the issue beside the work."))
        .child(div().text_size(14).text_color(t.muted).child("A native companion for Herdr. Follow new issue keys, then pause to read at your own pace.")))
      .child(div().flex_1())
      .child(div().text_size(11).text_color(t.dim).child("OFFLINE DEMO · No Jira account or live terminal is connected."));
  }
}
''')
        for name, appearance, width in (("peek-demo", "graphite", 420), ("peek-light", "paper", 420), ("peek-narrow", "graphite", 300), ("peek-refreshing", "graphite", 300), ("peek-loading", "graphite", 300), ("peek-paused", "graphite", 300), ("peek-refreshing-large", "graphite", 300), ("peek-reader", "graphite", 300), ("peek-options", "graphite", 300), ("peek-help", "graphite", 420), ("peek-browse", "graphite", 300), ("peek-alignment", "graphite", 300), ("peek-alignment-wide", "graphite", 420), ("peek-alignment-large", "graphite", 300), ("peek-sticky", "graphite", 420), ("peek-short", "graphite", 300), ("peek-excluded", "graphite", 300), ("peek-lookup", "graphite", 300), ("peek-title-300", "graphite", 300), ("peek-title-360", "graphite", 360), ("peek-title-420", "graphite", 420)):
            panel_props = {"demo": True}
            if name in ("peek-options", "peek-help", "peek-excluded", "peek-lookup", "peek-sticky", "peek-refreshing", "peek-loading", "peek-paused", "peek-refreshing-large"):
                panel_props["captureScreen"] = name.removeprefix("peek-")
            if name == "peek-refreshing-large": panel_props["fixtureUiFontSize"] = 20
            if name in ("peek-browse", "peek-short"):
                panel_props["captureScreen"] = "browse"
            if name.startswith("peek-alignment"):
                panel_props["captureScreen"] = "alignment"
                if name.endswith("large"): panel_props["fixtureUiFontSize"] = 20
            if name.startswith("peek-title-"):
                panel_props["captureScreen"] = "long-title"
            panel = {"id":"jira", "type":"block", "size":{"px":width}, "content":{"mod":"jira-peek","props":panel_props}}
            if name == "peek-short":
                panel["size"] = {"px":400}
                panel = {"id":"short-column", "type":"column", "size":{"px":width}, "children":[panel]}
            layout = {"id":"demo-root", "type":"row", "theme":appearance, "divider":{"width":1,"color":"border"}, "children":[
                {"id":"context", "type":"block", "content":{"mod":"capture-context"}},
                panel,
            ]}
            (home / f"layouts/{name}.json").write_text(json.dumps(layout))
        for suffix, height, font, headers in (("379",379,16,False),("380",380,16,False),
                                               ("499",499,20,False),("500",500,20,False),
                                               ("headers",500,20,True)):
            panel={"id":"jira","type":"block","size":{"px":height},"content":{"mod":"jira-peek",
                "props":{"demo":True,"captureScreen":"long-title","fixtureUiFontSize":font,"fixtureHeaders":headers}}}
            (home / f"layouts/peek-title-{suffix}.json").write_text(json.dumps({"id":"font-root","type":"row","theme":"graphite","children":[
                {"id":"context","type":"block","content":{"mod":"capture-context"}},
                {"id":"font-column","type":"column","size":{"px":300},"children":[panel]}]}))
        for suffix, width, font in (("300",300,13),("360",360,13),("420",420,13),
                                    ("font16",300,16),("font20",300,20)):
            name = "peek-key-" + suffix
            panel = {"id":name,"type":"block","size":{"px":width},"content":{"mod":"jira-peek",
                     "props":{"demo":True,"captureScreen":"key-widths","fixtureUiFontSize":font}}}
            (home / f"layouts/{name}.json").write_text(json.dumps({"id":name+"-root","type":"row","theme":"graphite",
                "children":[{"id":"context","type":"block","content":{"mod":"capture-context"}},panel]}))
        log = (base / "app.log").open("w")
        process = subprocess.Popen([app], env=env, stdout=log, stderr=log)
        try:
            ready = False
            for _ in range(75):
                result = subprocess.run([app, "status"], env=env, capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    ready = True; break
                if process.poll() is not None: break
                time.sleep(.2)
            if not ready:
                if output_dir:
                    log.flush()
                    (output_dir / "native-startup.log").write_bytes((base / "app.log").read_bytes())
                    (output_dir / "native-status-error.txt").write_text(result.stderr)
                raise RuntimeError("Isolated Herdr window did not become ready")
            verify_host_identity(app, env, identity)
            # Use the actual shipped tabs/layout contract and the selected
            # native checker, without replacing the fixture's instrumented mod.
            spec = importlib.util.spec_from_file_location("toolbar_installer", ROOT / "scripts/install-app.py")
            toolbar_installer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(toolbar_installer)
            toolbar_plan = toolbar_installer.attachment_plan(home, "main")
            toolbar_check = base / "toolbar-check"
            toolbar_check.mkdir()
            toolbar_installer.stage_attachment(toolbar_plan, toolbar_check)
            subprocess.run([app, "check", str(toolbar_check)], env=env, capture_output=True, timeout=60, check=True)
            toolbar_installer.attach(toolbar_plan, home)
            # Exercise a real host-created tabs clone, a supporting import and
            # an existing nondefault Peek ID without changing the public gallery.
            subprocess.run([app, "do", "mod.clone", '{"name":"tabs","as":"worktree-tabs"}'],
                           env=env, capture_output=True, timeout=5, check=True)
            personal = home / "mods/worktree-tabs"
            source = (personal / "main.js").read_text()
            source = 'import { customAction } from "./controls.js";\n' + source
            source = source.replace('      .when(w?.buttons,',
                                    '      .child(button("fixture-custom", "Q", customAction))\n      .when(w?.buttons,')
            (personal / "main.js").write_text(source)
            (personal / "controls.js").write_text('import { run } from "herdr";\nexport const customAction = () => run("layout.toggle", { id: "sidebar" });\n')
            custom_layout = json.loads((home / "layouts/main.json").read_text())
            entries = list(toolbar_installer.layout_entries(custom_layout))
            next(node for node, _ in entries if node.get("id") == "tabs")["content"]["mod"] = "worktree-tabs"
            next(node for node, _ in entries if node.get("id") == "work-body")["children"].append({
                "id": "peek-sidebar", "type": "block", "size": {"px": 360},
                "content": {"mod": "jira-peek", "props": {"demo": True}}})
            (home / "layouts/workbench.json").write_text(json.dumps(custom_layout))
            custom_plan = toolbar_installer.attachment_plan(home, "workbench")
            custom_check = base / "custom-toolbar-check"
            toolbar_installer.stage_attachment(custom_plan, custom_check)
            subprocess.run([app, "check", str(custom_check)], env=env, capture_output=True, timeout=60, check=True)
            toolbar_installer.attach(custom_plan, home)
            toolbar_installer.attachment_plan(home, "workbench")  # Identical preparation remains repeatable.
            transcript = base / "fictional-terminal.sh"
            transcript_text = "#!/bin/sh\nprintf 'ABC-1 fictional history\\n'\ni=0\nwhile [ \"$i\" -lt 120 ]; do printf 'fictional filler line\\n'; i=$((i+1)); done\nprintf 'ABC-2 fictional visible issue\\n'\n"
            # A raw receiver can print controlled fictional arrivals in every
            # fixture mode. Any received keys are recorded, never executed.
            transcript_text += f"exec {shlex.quote(sys.executable)} {shlex.quote(str(OUT / 'input-receiver.py'))}\n"
            transcript.write_text(transcript_text)
            created = subprocess.run([core, "run", "--bg", "--no-parent", "--no-notify", "--name", "fictional-source", "--cwd", str(base), "/bin/sh", str(transcript)], env=env, capture_output=True, text=True, timeout=10, check=True)
            address = json.loads(created.stdout)["address"]
            for _ in range(50):
                screen = subprocess.run([core, "read", address, "--lines", "0"], env=env, capture_output=True, text=True, timeout=5, check=True).stdout
                if "ABC-2" in screen: break
                time.sleep(.1)
            history = subprocess.run([core, "read", address, "--lines", "200"], env=env, capture_output=True, text=True, timeout=5, check=True).stdout
            if "ABC-1" in screen or "ABC-2" not in screen or "ABC-1" not in history:
                raise RuntimeError("Fictional source did not establish separate screen/history fixtures")
            (home / "layouts/peek-integration.json").write_text(json.dumps({"id":"native-check", "type":"block", "content":{"mod":"jira-peek", "props":{"integration":True,"source":address}}}))
            subprocess.run([app, "do", "overlay.close", '{"id":"frame-welcome"}'], env=env, capture_output=True, timeout=5)
            subprocess.run([app, "do", "layout.switch", '{"name":"peek-integration"}'], env=env, capture_output=True, timeout=5, check=True)
            native_result = home / "native-check.json"
            for _ in range(750):
                if native_result.exists(): break
                time.sleep(.1)
            if not native_result.exists():
                if output_dir:
                    status = subprocess.run([app, "status"], env=env, capture_output=True, text=True, timeout=5)
                    (output_dir / "native-timeout-status.json").write_text(status.stdout)
                    (output_dir / "native-startup.log").write_bytes((base / "app.log").read_bytes())
                    subprocess.run([app, "shot", str(output_dir / "native-timeout.png")], env=env,
                                   capture_output=True, timeout=5)
                raise RuntimeError("Native async integration check did not complete")
            result = json.loads(native_result.read_text())
            if not result.get("ok"):
                if output_dir:
                    (output_dir / "native-failure.json").write_text(json.dumps(result, indent=2))
                    subprocess.run([app, "shot", str(output_dir / "native-failure.png")], env=env,
                                   capture_output=True, timeout=5)
                raise RuntimeError("Native async integration check failed: " + result.get("error", "unknown error"))
            print("Passed native setup mount/retry focus, discovery/history, preview/unread, settings/conflicts, cache clear/reconnect, Fields invalidation focus, local idle lease/resume, and TTL-zero logical retention")
            print("Offline native latency (ms; network cases sampled every 100ms): " + json.dumps(result.get("performance", {})))
            if row_stress:
                (home / "layouts/peek-row-stress.json").write_text(json.dumps({"id":"stress", "type":"block",
                    "content":{"mod":"jira-peek", "props":{"demo":True,"rowStress":True}}}))
                subprocess.run([app, "do", "layout.switch", '{"name":"peek-row-stress"}'], env=env,
                               capture_output=True, timeout=5, check=True)
                stress_path = home / "row-stress.json"
                for _ in range(1000):
                    if stress_path.exists() or process.poll() is not None: break
                    time.sleep(.1)
                stress = json.loads(stress_path.read_text()) if stress_path.exists() else {"ok":False,"error":"Native row stress did not complete"}
                if output_dir:
                    (output_dir / "row-stress.json").write_text(json.dumps(stress, indent=2) + "\n")
                if not stress.get("ok"):
                    raise RuntimeError("Native row stress failed: " + stress.get("error", "unknown error"))
                result["rowStress"] = stress
                print("Passed native row allocation stress: " + json.dumps(stress), flush=True)
            for name, target in capture_targets(output_dir):
                subprocess.run([app, "do", "layout.switch", json.dumps({"name":name})], env=env, capture_output=True, timeout=5, check=True)
                time.sleep(1)
                status = subprocess.run([app, "status"], env=env, capture_output=True, text=True, timeout=5, check=True)
                info = json.loads(status.stdout)
                if info.get("errors"):
                    raise RuntimeError("Native demo reported errors: " + json.dumps(info["errors"]))
                if info.get("overlays"):
                    raise RuntimeError("An overlay obscures the native demo; refusing to publish the frame")
                # Size callbacks can invalidate a second native frame after a
                # layout switch. Publish only a settled fictional frame.
                frame = base / "capture-frame.png"
                previous = None
                for _ in range(8):
                    subprocess.run([app, "shot", str(frame)], env=env, check=True, stdout=subprocess.DEVNULL, timeout=5)
                    current = frame.read_bytes()
                    if current == previous:
                        target.write_bytes(current)
                        break
                    previous = current
                    time.sleep(.15)
                else:
                    raise RuntimeError("Native demo frame did not settle; refusing to publish it")
                print("Captured native fictional demo: " + target.name)
            verify_host_identity(app, env, identity)
            if output_dir:
                verification = {**result, "herdr_app": app_version,
                                "herdr_core": subprocess.check_output([core, "--version"], env=env, text=True).strip(),
                                "host": identity}
                (output_dir / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
            if review:
                (home / "fixture-response.json").write_text(json.dumps({"mode":"success", "rich":True}))
                review_mod = home / "mods/capture-review"
                review_mod.mkdir()
                (review_mod / "mod.json").write_text('{"place":"none"}')
                shutil.copy2(OUT / "app-review.js", review_mod / "main.js")
                short_heights = {"peek-review-short": 400, "peek-review-tiny": 300,
                                 "peek-review-499": 499, "peek-review-500": 500,
                                 "peek-review-font16":380,"peek-review-font20":500}
                for name in ("peek-review", "peek-review-light", *short_heights, "peek-review-many", "peek-review-empty", "peek-review-setup", "peek-review-demo"):
                    panel_props = {"review":True, "source":address, "many":name=="peek-review-many"}
                    if name in ("peek-review-font16","peek-review-font20"):
                        panel_props["fixtureUiFontSize"] = 16 if name.endswith("16") else 20
                    if name in ("peek-review-empty", "peek-review-setup"):
                        panel_props["source"] = None
                    if name == "peek-review-setup":
                        panel_props["configDir"] = str(base / "missing-fictional-config")
                    if name == "peek-review-demo":
                        panel_props.update(demo=True, source=None)
                    panel = {"id":"review-panel", "type":"block", "content":{"mod":"jira-peek", "props":panel_props}}
                    if name in short_heights:
                        panel["size"] = {"px":short_heights[name]}
                        right = {"id":"review-column", "type":"column", "size":{"px":300}, "children":[panel, {"id":"space", "type":"block", "content":{"mod":"capture-review", "props":{"spacer":True}}}]}
                    else:
                        right = panel
                        right["size"] = {"px":420 if name == "peek-review-light" else 300}
                    layout = {"id":"review-root", "type":"row", "theme":"paper" if name=="peek-review-light" else "graphite",
                              "children":[{"id":"controls", "type":"block", "content":{"mod":"capture-review", "props":{"resizeId":"review-column" if name in short_heights else "review-panel"}}}, right]}
                    (home / f"layouts/{name}.json").write_text(json.dumps(layout))
                # Exercise the installer's real panel + toolbar attachment.
                # A host-owned layout.focus can route a custom shortcut to Peek.
                spec = importlib.util.spec_from_file_location("peek_installer", ROOT / "scripts/install-app.py")
                installer = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(installer)
                installer.attach(installer.attachment_plan(home, "main"), home)
                toolbar_layout = json.loads((home / "layouts/main-jira-peek.json").read_text())
                work = next(node for node in toolbar_layout["children"] if node["id"] == "work")
                body = next(node for node in work["children"] if node["id"] == "work-body")
                next(node for node in body["children"] if node["id"] == "main")["content"] = {"terminal":address}
                panel = next(node for node in body["children"] if node["id"] == "jira-peek")
                panel.update(hidden=True, content={"mod":"jira-peek", "props":{"review":True,"many":True,"source":address}})
                (home / "layouts/peek-review-toolbar.json").write_text(json.dumps(toolbar_layout))
                # Preserve host actions such as terminal paste while adding
                # Peek's optional bindings, just as a normal install does.
                keys = json.loads((home / "keys.json").read_text())
                for scope, bindings in json.loads((ROOT / "keys.json").read_text()).items():
                    keys.setdefault(scope, {}).update(bindings)
                commands = json.loads(subprocess.run([app, "commands"], env=env,
                                      capture_output=True, text=True, timeout=5, check=True).stdout)
                if not any(command["name"] == "layout.focus" for command in commands):
                    keys["global"].pop("ctrl-shift-j", None)
                    print("Stock host: keyboard-entry trials need a host-owned layout.focus; pointer review remains available.")
                (home / "keys.json").write_text(json.dumps(keys))
                # A real app space/tab lets focus-return checks exercise the
                # normal context even though the displayed terminal is standalone.
                # Both terminals must only record input, including after return.
                subprocess.run([app, "do", "space.new", json.dumps({"name":"Fictional keyboard review",
                                "folder":str(base), "argv":[sys.executable, str(OUT / "input-receiver.py")]})],
                               env=env, capture_output=True, timeout=5, check=True)
                subprocess.run([app, "do", "layout.switch", '{"name":"peek-review"}'], env=env, capture_output=True, timeout=5, check=True)
                print("Isolated review app home: " + str(home), flush=True)
                input("Isolated fictional app ready for interaction review. Press Enter to close it: ")
        finally:
            subprocess.run([app, "do", "app.quit"], env=env, capture_output=True, timeout=5)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
            subprocess.run([core, "server", "stop"], env=env, capture_output=True, timeout=10)
            log.close()


if __name__ == "__main__":
    main()
