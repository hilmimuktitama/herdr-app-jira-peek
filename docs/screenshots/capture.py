#!/usr/bin/env python3
"""Capture native Herdr app frames using isolated, entirely fictional fixtures.

Requires herdr-app and hc; no Jira account or live session is used.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", action="store_true", help="Capture native app frames (the default; retained for compatibility)")
    parser.add_argument("--app-review", action="store_true", help="Keep the isolated window open until Enter for interaction review")
    parser.add_argument("--app-highlight", action="store_true", help="Capture real terminal highlights with isolated fictional data")
    parser.add_argument("--app-binary", type=Path, help="Desktop executable (normally the optional local build for highlights)")
    args = parser.parse_args()
    if args.app_highlight:
        capture_highlight_app(args.app_binary, review=args.app_review)
    else:
        capture_app(args.app_binary, review=args.app_review)


def capture_app(binary=None, review=False):
    """Native app frames only; never use the person's app home or core socket."""
    app, core = binary or shutil.which("herdr-app"), shutil.which("hc")
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
        for directory in (home / "layouts", home / "mods/capture-context", base / "run", base / "config/herdr-core"):
            directory.mkdir(parents=True, mode=0o700)
        (base / "config/herdr-core/config.toml").write_text("notes = false\n")
        subprocess.run([sys.executable, str(ROOT / "scripts/install-app.py"), "--app-home", str(home)], env=env, check=True, stdout=subprocess.DEVNULL)
        (home / "settings.json").write_text(json.dumps({"core": core, "telemetry": False, "sounds": {"enabled": False}, "appearance": "dark"}))
        (home / "shared.json").write_text(json.dumps({"frame.welcomed": "skipped"}))
        app_version = subprocess.check_output([app, "--version"], env=env, text=True).strip().split()[-1]
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
if response.get("metadataDelay") and fields and "description" not in fields and "--comments" not in sys.argv:
    (control.parent/"fixture-metadata-started").write_text("started")
    time.sleep(response["metadataDelay"])
if response.get("slowIssue") in keys:
    (control.parent/"fixture-issue-started").write_text("started")
    time.sleep(2)
def issue(key):
    if response.get("rich"):
        return {"key":key,"summary":"Keep catalog filters when returning from an item", "status":{"name":"Awaiting cross-team review"},
            "assignee":{"displayName":"Alex Example"},"priority":{"name":"High"},
            "customfield_10016":0,"customfield_10017":{"type":"doc","content":[
                {"type":"paragraph","content":[{"type":"text","text":"Keep the catalog category when returning."}]},
                {"type":"paragraph","content":[{"type":"text","text":"Check keyboard and pointer navigation."}]}]},
            "labels":["catalog","navigation"],"duedate":None,
            "description":"Returning to the fictional catalog should restore filters and reading position.\\n\\n" + "\\n\\n".join("Acceptance step %d: keep the chosen category and price range visible. Keyboard and pointer navigation must preserve the reader's place." % i for i in range(1,13)),
            "comments":[{"author":{"displayName":"Sam Sample"},"created":"2026-10-31T08:00:00Z","body":"Verified with entirely fictional catalog records."}]}
    return {"key":key,"summary":"Fictional native integration","status":{"name":"Open"},"description":"Offline integration body","comments":[]}
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
        (mod / "main.js").write_text('''
import Panel from "./panel.js";
import {props,terminals,appHome,readTextFile,writeTextFile,run,setShared} from "herdr";
export default class NativeCheck extends Panel {
  render(cx) {
    const root = super.render(cx);
    if (props()?.review) {
      const state = {query:this.input.value(), modelQuery:this.model.current?.query,
        rows:this.model.rows(), unread:[...(this.model.current?.unseen || [])],
        actionKey:this.issueActionKey(), typing:!!this.typing, reader:this.readerFocus,
        selected:this.model.current?.selected, follow:this.model.current?.follow,
        loading:!!this.loading, origin:this.origin, focused:this.isPeekFocused()};
      const text = JSON.stringify(state);
      if (text !== this.keyboardSnapshot) { this.keyboardSnapshot=text; setShared("fixture.keyboard",state); }
    }
    return root;
  }
  init(p,cx) {
    super.init(p,cx);
    if (props()?.demo) {
      this.live=false;
      for(const issue of this.model.details.values()) issue.fetchedAt=Date.parse("2026-11-01T08:45:00Z");
      if (props().captureScreen === "options") this.moreOpen=true;
      if (props().captureScreen === "help") this.helpTopic="options";
      if (props().captureScreen === "browse") this.readerFocus=false;
      if (["excluded","lookup"].includes(props().captureScreen)) {
        this.readerFocus=false;
        this.model.filter(props().captureScreen === "excluded" ? "empty-results" : "DEMO-2500"); this.syncInput();
      }
    }
    if (props()?.review) {
      this.readerFocus=true; this.live=false;
      cx.spawn(async cx => {
        for(let i=0;i<200 && !this.model.config;i++) await cx.sleep(100);
        if(!this.model.config || !props().source) return;
        this.model.useSource(props().source); this.model.pinned=true;
        if(props().many) this.model.merge(Array.from({length:30},(_,i)=>`ABC-${i+1}`));
        this.scan(cx); this.pump(cx); cx.notify();
      });
    }
    if (!props()?.integration) return;
    cx.spawn(async cx => {
      const wait = async predicate => {
        for(let i=0;i<200;i++) { if(predicate()) return; await cx.sleep(100); }
        throw new Error("Timed out waiting for native state");
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
        this.toggleReaderFocus(cx);
        if(this.readerFocus) throw new Error("Issue browsing did not open");
        this.toggleReaderFocus(cx);
        if(!this.readerFocus) throw new Error("Compact reader did not reopen");
        this.search(cx); this.input.set_value("catalog");
        const selectedBeforeHelp=this.model.current.selected;
        run("jira-peek.options"); await wait(()=>this.moreOpen);
        run("jira-peek.help"); await wait(()=>this.helpTopic === "options" && !this.moreOpen);
        run("jira-peek.back"); await wait(()=>!this.helpTopic);
        if(this.moreOpen || this.readerFocus || this.input.value()!=="catalog" || this.model.current.selected!==selectedBeforeHelp)
          throw new Error("Options help did not return to the retained filter and issue");
        run("jira-peek.help"); await wait(()=>this.helpTopic === "peek");
        run("jira-peek.options"); await wait(()=>!this.helpTopic && this.moreOpen);
        run("jira-peek.back"); await wait(()=>!this.moreOpen);
        // Programmatic InputState changes need not emit change. Clear must
        // update the model itself, including after a zero-result query.
        const clearSelection=this.model.current.selected;
        for(const query of ["ABC-1","no fictional match"]) {
          this.model.filter(query); this.syncInput(); this.readerFocus=false;
          await cx.sleep(100);
          this.clearFilter(cx); await cx.sleep(100);
          if(this.input.value() || this.model.current.query || this.model.rows().length!==this.model.current.keys.length ||
              this.model.current.selected!==clearSelection || this.model.current.follow)
            throw new Error("Native clear did not restore the complete result set: "+JSON.stringify({
              input:this.input.value(),query:this.model.current.query,rows:this.model.rows().length,
              keys:this.model.current.keys.length,selected:this.model.current.selected,expected:clearSelection,
              follow:this.model.current.follow,reader:this.readerFocus}));
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
        this.applyFields(cx); await wait(()=>!this.fieldEditor);
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
        await wait(()=>this.live && this.highlightSource===false);
        this.toggleLive(cx); await wait(()=>!this.preferencesSaving);
        const preferenceSaved=JSON.parse(await readTextFile(fieldPath));
        if(preferenceSaved.preferences.autoRefresh!==false || preferenceSaved.preferences.highlightSource!==false) throw new Error("Options did not save reader preferences");
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
        await writeControl({metadataDelay:2}); this.pump(cx);
        await waitFile(appHome()+"/fixture-metadata-started");
        const metadataStart=Date.now(); this.select("ABC-81",cx,false);
        await wait(()=>this.model.details.has("ABC-81"));
        const metadataSelectionMs=Date.now()-metadataStart;
        if(this.backgroundRequest?.phase!=="metadata" && this.request?.phase!=="metadata")
          throw new Error("Selected issue waited for background metadata");
        await wait(()=>!this.request && !this.backgroundRequest);
        await writeControl({slowIssue:"ABC-83"});
        this.model.merge(["ABC-83","ABC-84"]); this.select("ABC-83",cx,false);
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
        await writeTextFile(appHome()+"/native-check.json",JSON.stringify({ok:true,performance}),null);
      } catch(error) {
        await writeTextFile(appHome()+"/native-check.json",JSON.stringify({ok:false,error:String(error)}),null);
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
        .child(div().text_size(14).text_color(t.muted).child("A native companion for Herdr. Follow new issue keys as they appear, or pin your source and settle in to read.")))
      .child(div().flex_1())
      .child(div().text_size(11).text_color(t.dim).child("OFFLINE DEMO · No Jira account or live terminal is connected."));
  }
}
''')
        for name, appearance, width in (("peek-demo", "graphite", 420), ("peek-light", "paper", 420), ("peek-narrow", "graphite", 300), ("peek-reader", "graphite", 300), ("peek-options", "graphite", 300), ("peek-help", "graphite", 420), ("peek-browse", "graphite", 300), ("peek-short", "graphite", 300), ("peek-excluded", "graphite", 300), ("peek-lookup", "graphite", 300)):
            panel_props = {"demo": True}
            if name in ("peek-options", "peek-help", "peek-excluded", "peek-lookup"):
                panel_props["captureScreen"] = name.removeprefix("peek-")
            if name in ("peek-browse", "peek-short"):
                panel_props["captureScreen"] = "browse"
            panel = {"id":"jira", "type":"block", "size":{"px":width}, "content":{"mod":"jira-peek","props":panel_props}}
            if name == "peek-short":
                panel["size"] = {"px":400}
                panel = {"id":"short-column", "type":"column", "size":{"px":width}, "children":[panel]}
            layout = {"id":"demo-root", "type":"row", "theme":appearance, "divider":{"width":1,"color":"border"}, "children":[
                {"id":"context", "type":"block", "content":{"mod":"capture-context"}},
                panel,
            ]}
            (home / f"layouts/{name}.json").write_text(json.dumps(layout))
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
                raise RuntimeError("Isolated Herdr window did not become ready")
            transcript = base / "fictional-terminal.sh"
            transcript_text = "#!/bin/sh\nprintf 'ABC-1 fictional history\\n'\ni=0\nwhile [ \"$i\" -lt 120 ]; do printf 'fictional filler line\\n'; i=$((i+1)); done\nprintf 'ABC-2 fictional visible issue\\n'\n"
            if review:
                transcript_text += '''last=; i=0
while [ "$i" -lt 3600 ]; do
  if [ -r "$HERDR_APP_HOME/fixture-discovery" ]; then
    next=$(cat "$HERDR_APP_HOME/fixture-discovery")
    if [ "$next" != "$last" ]; then printf '%s fictional discovered issue\\n' "$next"; last=$next; fi
  fi
  sleep 1; i=$((i+1))
done
'''
            else:
                transcript_text += "sleep 180\n"
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
            for _ in range(250):
                if native_result.exists(): break
                time.sleep(.1)
            if not native_result.exists():
                raise RuntimeError("Native async integration check did not complete")
            result = json.loads(native_result.read_text())
            if not result.get("ok"):
                raise RuntimeError("Native async integration check failed: " + result.get("error", "unknown error"))
            print("Passed native setup mount/retry focus, terminal/history reads, URL/title lookup, Clear, unread selection, freshness, Options/Help/filter return, reader settings/conflicts/recovery, agent commands, cache clear, and reconnect after invalidation")
            print("Offline native latency (ms; network cases sampled every 100ms): " + json.dumps(result.get("performance", {})))
            for name, target in (("peek-demo", ROOT / "preview.png"), ("peek-light", OUT / "app-light.png"), ("peek-narrow", OUT / "app-narrow.png"), ("peek-reader", OUT / "app-reader.png"), ("peek-options", OUT / "app-options.png"), ("peek-help", OUT / "app-help.png"), ("peek-browse", OUT / "app-browse.png"), ("peek-short", OUT / "app-short.png"), ("peek-excluded", base / "filtered-result.png"), ("peek-lookup", base / "direct-lookup.png")):
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
            if review:
                (home / "fixture-response.json").write_text(json.dumps({"mode":"success", "rich":True}))
                review_mod = home / "mods/capture-review"
                review_mod.mkdir()
                (review_mod / "mod.json").write_text('{"place":"none"}')
                shutil.copy2(OUT / "app-review.js", review_mod / "main.js")
                for name in ("peek-review", "peek-review-light", "peek-review-short", "peek-review-many", "peek-review-empty", "peek-review-setup", "peek-review-demo"):
                    panel_props = {"review":True, "source":address, "many":name=="peek-review-many"}
                    if name in ("peek-review-empty", "peek-review-setup"):
                        panel_props["source"] = None
                    if name == "peek-review-setup":
                        panel_props["configDir"] = str(base / "missing-fictional-config")
                    if name == "peek-review-demo":
                        panel_props.update(demo=True, source=None)
                    panel = {"id":"review-panel", "type":"block", "content":{"mod":"jira-peek", "props":panel_props}}
                    if name == "peek-review-short":
                        panel["size"] = {"px":400}
                        right = {"id":"review-column", "type":"column", "size":{"px":300}, "children":[panel, {"id":"space", "type":"block", "content":{"mod":"capture-review", "props":{"spacer":True}}}]}
                    else:
                        right = panel
                        right["size"] = {"px":420 if name == "peek-review-light" else 300}
                    layout = {"id":"review-root", "type":"row", "theme":"paper" if name=="peek-review-light" else "graphite",
                              "children":[{"id":"controls", "type":"block", "content":{"mod":"capture-review", "props":{"resizeId":"review-column" if name=="peek-review-short" else "review-panel"}}}, right]}
                    (home / f"layouts/{name}.json").write_text(json.dumps(layout))
                # Exercise the installer's real panel + toolbar attachment, then
                # add the separately opted-in keyboard handler for its review.
                spec = importlib.util.spec_from_file_location("peek_installer", ROOT / "scripts/install-app.py")
                installer = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(installer)
                installer.attach(installer.attachment_plan(home, "main"), home)
                tabs_file = home / "mods/tabs-jira-peek/main.js"
                tabs_code = tabs_file.read_text()
                integration = (ROOT / "docs/PANEL-INTEGRATION.md").read_text().split("```js\n")
                browse_init = integration[2].split("```", 1)[0].rstrip()
                stock_init = '  init() {\n    this.pressed = null;\n    this.panels = JSON.parse(localStorage.getItem("panels") ?? "{}");\n  }'
                if stock_init not in tabs_code:
                    raise RuntimeError("Stock tabs changed; review the documented toolbar integration")
                tabs_file.write_text(tabs_code.replace('settings } from "herdr";', 'settings, nextCommand, focused, setShared } from "herdr";')
                                     .replace(stock_init, browse_init))
                toolbar_layout = json.loads((home / "layouts/main-jira-peek.json").read_text())
                work = next(node for node in toolbar_layout["children"] if node["id"] == "work")
                body = next(node for node in work["children"] if node["id"] == "work-body")
                next(node for node in body["children"] if node["id"] == "main")["content"] = {"terminal":address}
                panel = next(node for node in body["children"] if node["id"] == "jira-peek")
                panel.update(hidden=True, content={"mod":"jira-peek", "props":{"review":True,"many":True,"source":address}})
                (home / "layouts/peek-review-toolbar.json").write_text(json.dumps(toolbar_layout))
                (home / "keys.json").write_text((ROOT / "keys.json").read_text())
                # A real app space/tab lets focus-return checks exercise the
                # normal context even though the displayed terminal is standalone.
                subprocess.run([app, "do", "space.new", json.dumps({"name":"Fictional keyboard review",
                                "folder":str(base), "argv":["/bin/sh"]})],
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


def capture_highlight_app(binary=None, review=False):
    """Exercise actual terminal cells without connecting to any Jira service."""
    app = str(Path(binary or shutil.which("herdr-app") or "").resolve())
    core = shutil.which("hc")
    if not Path(app).is_file() or not core:
        raise RuntimeError("A Herdr desktop executable and hc are required")
    # macOS's default per-user temp directory can exceed the core's socket limit.
    with tempfile.TemporaryDirectory(prefix="peek-highlight-", dir="/tmp") as temporary:
        base = Path(temporary).resolve()
        home = base / "app"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "HC_", "TWG_", "CURL_", "XDG_"))}
        env.update(HERDR_APP_HOME=str(home), HERDR_TELEMETRY="0", HC_SESSION="jph",
                   HC_SOCKET=str(base / "hc.sock"), XDG_STATE_HOME=str(base / "state"),
                   XDG_CONFIG_HOME=str(base / "config"), XDG_CACHE_HOME=str(base / "cache"),
                   XDG_RUNTIME_DIR=str(base / "run"))
        for directory in (home / "layouts", base / "run", base / "config/herdr-core"):
            directory.mkdir(parents=True, mode=0o700)
        (base / "config/herdr-core/config.toml").write_text("notes = false\n")
        subprocess.run([sys.executable, str(ROOT / "scripts/install-app.py"), "--app-home", str(home)],
                       env=env, check=True, stdout=subprocess.DEVNULL)
        (home / "settings.json").write_text(json.dumps({"core": core, "telemetry": False,
                                                        "sounds": {"enabled": False}, "appearance": "dark"}))
        (home / "shared.json").write_text(json.dumps({"frame.welcomed": "skipped"}))
        version = subprocess.check_output([app, "--version"], env=env, text=True).strip().split()[-1]
        (home / "update-notes.json").write_text(json.dumps({"last_run": version, "presented": []}))
        mod = home / "mods/jira-peek"
        (mod / "main.js").rename(mod / "panel.js")
        (mod / "main.js").write_text('''
import Panel from "./panel.js";
import * as herdr from "herdr";
export default class HighlightFixture extends Panel {
  init(p,cx) {
    super.init(p,cx); // demo props seed entirely fictional, in-memory issues.
    if(typeof herdr.setTerminalHighlight !== "function") throw new Error("The local renderer extension is required");
    this.demo=false; this.live=false; this.model.pinned=true;
    this.model.useSource(herdr.props().source);
    this.model.merge(["DEMO-1042","DEMO-1038"]);
    this.select("DEMO-1042",cx,false);
  }
  connect() {} // This fixture never opens configuration or a network connection.
  scan() {}
  pump() { this.syncHighlight(); }
  openIssue() { return false; }
  handleCommand(command,cx) {
    if(command === "qa-primary") this.select("DEMO-1042",cx,false);
    else if(command === "qa-secondary") this.select("DEMO-1038",cx,false);
    else if(command === "qa-toggle") this.toggleHighlight(cx);
    else super.handleCommand(command,cx);
    cx.notify();
  }
}
''')
        transcript = base / "fictional-terminal.sh"
        transcript.write_text("""#!/bin/sh
printf '\\033[2J\\033[HFICTIONAL WORKING AREA — Jira Peek highlight check\\n\\n'
printf 'DEMO-1042  Preserve catalog filters\\n'
printf 'DEMO-1038  Add an empty-results state\\n\\n'
printf 'Selected key repeated: (DEMO-1042), /browse/DEMO-1042\\n'
printf 'Different tokens: DEMO-10420 XDEMO-1042 DEMO-1042_extra\\n'
printf 'Unicode before key: 中 文  DEMO-1042\\n\\n'
printf 'This terminal is idle. Selection changes must redraw it.\\n'
sleep 3600
""")
        process = None
        log = (base / "app.log").open("w")
        def call(*args):
            return subprocess.run([app, *args], env=env, capture_output=True, text=True, timeout=10, check=True)
        def capture(name):
            time.sleep(.4)
            info = json.loads(call("status").stdout)
            if info.get("errors") or info.get("overlays"):
                raise RuntimeError("Fictional highlight fixture has runtime errors or an obscuring overlay")
            target = OUT / name
            call("shot", str(target))
            print("Captured fictional terminal: " + target.name, flush=True)
        try:
            created = subprocess.run([core, "run", "--bg", "--no-parent", "--no-notify", "--name", "fictional-highlight",
                                      "--cwd", str(base), "/bin/sh", str(transcript)], env=env,
                                     capture_output=True, text=True, timeout=10)
            if created.returncode:
                raise RuntimeError("Isolated fixture terminal failed: " + created.stderr.strip())
            address = json.loads(created.stdout)["address"]
            for name, theme in (("highlight-dark", "graphite"), ("highlight-light", "paper")):
                layout = {"id": "highlight-lab", "type": "row", "theme": theme, "children": [
                    {"id": "working-area", "type": "block", "content": {"terminal": address}},
                    {"id": "jira", "type": "block", "size": {"px": 400},
                     "content": {"mod": "jira-peek", "props": {"demo": True, "source": address}}}]}
                (home / f"layouts/{name}.json").write_text(json.dumps(layout))
            process = subprocess.Popen([app], env=env, stdout=log, stderr=log)
            for _ in range(75):
                status = subprocess.run([app, "status"], env=env, capture_output=True, timeout=3)
                if status.returncode == 0: break
                if process.poll() is not None: raise RuntimeError("Isolated highlight app exited")
                time.sleep(.2)
            else:
                raise RuntimeError("Isolated highlight app did not become ready")
            call("do", "overlay.close", '{"id":"frame-welcome"}')
            call("do", "layout.switch", '{"name":"highlight-dark"}')
            time.sleep(1)
            def read_source():
                return subprocess.check_output([core, "read", address, "--lines", "0"], env=env, text=True, timeout=5)
            before = read_source()
            if "DEMO-1042" not in before: raise RuntimeError("Fictional source has not rendered")
            capture("app-highlight-dark.png")
            call("do", "jira-peek.qa-secondary")
            capture("app-highlight-changed.png")
            call("do", "jira-peek.qa-toggle")
            capture("app-highlight-off.png")
            if read_source() != before: raise RuntimeError("Highlighting altered the source terminal text")
            call("do", "jira-peek.qa-toggle")
            call("do", "jira-peek.qa-primary")
            call("do", "layout.switch", '{"name":"highlight-light"}')
            capture("app-highlight-light.png")
            call("do", "layout.hide", '{"id":"jira"}')
            capture("app-highlight-hidden.png")
            call("do", "layout.show", '{"id":"jira"}')
            capture("app-highlight-restored.png")
            print("Passed fictional fixture execution and unchanged terminal text; visually inspect the captured marks.", flush=True)
            if review:
                print(f"Isolated highlight review app home: {home}", flush=True)
                input("Use the fictional panel for interaction review. Press Enter here to close it: ")
        finally:
            if process is not None and process.poll() is None:
                subprocess.run([app, "do", "app.quit"], env=env, capture_output=True, timeout=5)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
            subprocess.run([core, "server", "stop"], env=env, capture_output=True, timeout=10)
            log.close()


if __name__ == "__main__":
    main()
