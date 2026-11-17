#[path = "../src/management/integration.rs"]
#[allow(dead_code)]
mod integration;
use integration::*;
use serde_json::{json, Value};
use std::{
    cell::Cell,
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};
const TOOLBAR: &str = include_str!("../../tests/fixtures/tabs.js");
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .into()
}
fn temp() -> tempfile::TempDir {
    tempfile::tempdir_in(std::env::temp_dir().canonicalize().unwrap()).unwrap()
}
fn oracle(kind: &str, payload: Value) -> Value {
    let mut child=Command::new("python3").args(["-B","-c",r#"
import importlib.util, json, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('installer','scripts/install-app.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p=json.load(sys.stdin)
try:
    if sys.argv[1]=='toolbar': value=m.integrate_toolbar(p['source'],p['panel'])
    else:
        home=Path(p['home']); plan=m.attachment_plan(home,p['source'],check_conflicts=p.get('conflicts',True))
        value={str(path.relative_to(home)): m.content_bytes(content).hex() for path,content in plan.files.items()}
    print(json.dumps({'ok':True,'value':value}))
except (ValueError,OSError,RecursionError): print(json.dumps({'ok':False}))
"#,kind]).current_dir(root()).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(payload.to_string().as_bytes())
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success(), "oracle failed");
    serde_json::from_slice(&output.stdout).unwrap()
}
fn layout(panel: bool) -> Value {
    let mut body = json!({"id":"work-body","type":"row","children":[{"id":"terminal","type":"block","content":{"tab":"active"}}]});
    if panel {
        body["children"].as_array_mut().unwrap().push(json!({"id":"peek-sidebar","type":"block","size":{"px":420},"hidden":true,"content":{"mod":"jira-peek"}}));
    }
    json!({"id":"root","type":"column","children":[{"id":"tabs","type":"block","content":{"mod":"tabs"}},body]})
}
fn write(home: &Path, relative: &str, bytes: impl AsRef<[u8]>) {
    let path = home.join(relative);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, bytes).unwrap();
}
fn fixture(personal: bool) -> tempfile::TempDir {
    let home = temp();
    let h = home.path();
    let mut source = layout(personal);
    write(h, "mods/tabs/main.js", TOOLBAR);
    write(h, "keys.json", br#"{"global":{"f2":"fictional-action"}}"#);
    if personal {
        source["children"][0]["content"]["mod"] = json!("worktree-tabs");
        source["children"][0]["id"] = json!("personal-toolbar");
        let code=format!("import {{ customAction }} from \"./controls.js\";\n{}",TOOLBAR.replace("import { h_flex }","import { h_flex, Button, Toggle }").replace("      .when(w?.buttons,","      .child(Button.new(\"custom-action\").on_click(customAction).child(\"Q\"))\n      .when(w?.buttons,"));
        write(h, "mods/worktree-tabs/main.js", code);
        write(
            h,
            "mods/worktree-tabs/controls.js",
            "export const customAction = () => \"fictional-action\";\n",
        );
        write(
            h,
            "mods/worktree-tabs/icons/custom.svg",
            b"<svg xmlns=\"http://www.w3.org/2000/svg\"/>",
        );
        write(h,"mods/worktree-tabs/mod.json",br#"{"place":"top","title":"Personal tabs","focusable":true,"cloned_from":{"name":"tabs","version":"0.1.13"}}"#);
        write(h, "layouts/workbench.json", source.to_string());
    } else {
        write(h, "layouts/main.json", source.to_string());
    }
    home
}
fn assert_plan_parity(home: &Path, source: &str) -> AttachmentPlan {
    let expected = oracle("plan", json!({"home":home,"source":source}));
    assert_eq!(expected["ok"], true, "Python refused fixture");
    let plan = plan_attachment(home, source, true).unwrap();
    let mut actual = serde_json::Map::new();
    for (path, bytes) in plan.files() {
        actual.insert(
            path.strip_prefix(home).unwrap().to_str().unwrap().into(),
            json!(bytes.iter().map(|b| format!("{b:02x}")).collect::<String>()),
        );
    }
    assert_eq!(
        Value::Object(actual),
        expected["value"],
        "generated files differ from Python"
    );
    plan
}
fn assert_refused(home: &Path, source: &str) {
    assert_eq!(
        oracle("plan", json!({"home":home,"source":source}))["ok"],
        false
    );
    assert!(plan_attachment(home, source, true).is_err());
}
#[test]
fn toolbar_transform_matches_oracle_and_retains_custom_controls() {
    for source in [TOOLBAR.to_owned(),TOOLBAR.replace("import { h_flex }","import { h_flex, Toggle }"),TOOLBAR.replace("      .when(enabled.includes(\"changes\"),","      .child(div().id(\"custom-before\").on_click(() => run(\"custom.before\", {})).child(\"Before\"))\n      .when(enabled.includes(\"changes\"),").replace("      .when(w?.buttons,","      .child(div().id(\"custom-after\").on_click(() => run(\"custom.after\", {})).child(\"Q\"))\n      .when(w?.buttons,")] {
        for panel in ["peek-sidebar","quoted-\"-peek","fictional-🧭-peek"] {
            let expected=oracle("toolbar",json!({"source":source,"panel":panel})); assert_eq!(expected["ok"],true);
            assert_eq!(integrate_toolbar(&source,panel).unwrap(),expected["value"].as_str().unwrap());
        }
    }
}
#[test]
fn ambiguous_toolbar_and_binding_vectors_match_oracle_rejections() {
    let changes = TOOLBAR
        .lines()
        .find(|line| line.contains("panelButton(\"changes\""))
        .unwrap()
        .to_owned()
        + "\n";
    let mut variants = vec![
        TOOLBAR.replace(&changes, &format!("/*\n{changes}*/\n")),
        TOOLBAR.replace(
            &changes,
            &format!("      .when(true, el => {{\n        return el\n{changes}      }})\n"),
        ),
        TOOLBAR
            .replace("function find(node, id) {", "/*\nfunction find(node, id) {")
            .replace("export default", "*/\nexport default"),
        TOOLBAR.replace(&changes, &format!("{changes}{changes}")),
        TOOLBAR.replace(
            "    return h_flex().size_full()",
            "    return h_flex().size_full();\n    h_flex()",
        ),
        TOOLBAR.replace(
            "return h_flex().size_full()",
            "return h_flex().id(\"panel-jira-peek\").size_full()",
        ),
    ];
    for declaration in [
        "const run = () => null;",
        "const find = () => null;",
        "let run;",
        "let custom, run;",
        "let custom, find;",
        "let custom, Toggle;",
        "let custom, run\n    (0);",
        "let { settings } = {};",
        "let [Toggle] = [];",
        "const custom = 1, run = () => null;",
        "function find() { return null; }",
        r"const \u0072un = () => null;",
    ] {
        variants.push(TOOLBAR.replace(
            "    const t = theme();",
            &format!("    {declaration}\n    const t = theme();"),
        ));
    }
    for extra in [
        "/*".repeat(4000),
        "\"unterminated".into(),
        "{".repeat(129) + &"}".repeat(129),
    ] {
        variants.push(format!("{TOOLBAR}\n{extra}"));
    }
    for source in variants {
        assert_eq!(
            oracle("toolbar", json!({"source":source,"panel":"peek-sidebar"}))["ok"],
            false
        );
        assert!(integrate_toolbar(&source, "peek-sidebar").is_err());
    }
}
#[test]
fn stock_and_personal_plans_match_bytes_and_repair_is_idempotent() {
    for personal in [false, true] {
        let home = fixture(personal);
        let h = home.path();
        let source = if personal { "workbench" } else { "main" };
        write(h, "settings.json", "fictional settings");
        write(h, "data/jira-peek/fields.json", "fictional fields");
        let before = tree(h);
        let plan = assert_plan_parity(h, source);
        let lock = Cell::new(false);
        let checks = Cell::new(0);
        for _ in 0..2 {
            let repaired = repair_integration(
                h,
                source,
                true,
                |operation| {
                    lock.set(true);
                    let result = operation();
                    lock.set(false);
                    result
                },
                || Ok("fictional managed fingerprint"),
                |staged| {
                    assert!(lock.get());
                    assert!(staged.join("main.js").is_file());
                    if personal {
                        assert!(staged.join("controls.js").is_file());
                        assert!(staged.join("icons/custom.svg").is_file());
                    }
                    checks.set(checks.get() + 1);
                    Ok(())
                },
            )
            .unwrap();
            assert_eq!(repaired.plan.files(), plan.files());
            assert_eq!(repaired.cleanup, CleanupReport::default());
        }
        assert_eq!(checks.get(), 2);
        let after = tree(h);
        for (path, bytes) in before {
            assert_eq!(after[&path], bytes);
        }
        assert_plan_parity(h, source);
    }
}
fn tree(root: &Path) -> std::collections::BTreeMap<PathBuf, Vec<u8>> {
    let mut result = std::collections::BTreeMap::new();
    let mut pending = vec![root.to_path_buf()];
    while let Some(dir) = pending.pop() {
        for entry in fs::read_dir(dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                pending.push(path);
            } else {
                result.insert(
                    path.strip_prefix(root).unwrap().into(),
                    fs::read(path).unwrap(),
                );
            }
        }
    }
    result
}
#[test]
fn panel_identity_visibility_and_layout_validation_match_oracle() {
    for case in 0..10 {
        let home = fixture(true);
        let h = home.path();
        let path = h.join("layouts/workbench.json");
        let mut source: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        match case {
            0 => source["children"][1]["hidden"] = json!(true),
            1 => source["children"][1]["type"] = json!("stack"),
            2 => source["children"][1]["children"][1]["id"] = json!("terminal"),
            3 => source["children"][1]["children"][1]["type"] = json!("row"),
            4 => source["children"][1]["children"][1]["id"] = Value::Null,
            5 => {
                let panel = source["children"][1]["children"][1].clone();
                source["children"][1]["children"]
                    .as_array_mut()
                    .unwrap()
                    .push(panel);
            }
            6 => source["children"][1]["content"] = json!([]),
            7 => source["children"][1]["children"] = json!({}),
            8 => source["children"][0]["id"] = json!("unidentified"),
            _ => source["children"][1]["id"] = json!("personal-body"),
        }
        fs::write(&path, source.to_string()).unwrap();
        if case >= 8 {
            assert_plan_parity(h, "workbench");
        } else {
            assert_refused(h, "workbench");
        }
    }
    for case in 0..4 {
        let home = fixture(false);
        let h = home.path();
        let mut source = layout(false);
        match case {
            0 => source["children"][1]["hidden"] = json!(true),
            1 => {
                source["children"][1] =
                    json!({"type":"stack","children":[source["children"][1].clone()]})
            }
            2 => source["children"][1]["children"][0]["id"] = json!("jira-peek"),
            _ => source["children"][1]["id"] = json!("missing-body"),
        }
        write(h, "layouts/main.json", source.to_string());
        assert_refused(h, "main");
    }
}
#[test]
fn shortcut_and_identity_dependencies_match_oracle() {
    let variants = [
        (
            "mods/worktree-tabs/controls.js",
            r#"const action = () => run("worktree-tabs.custom", {});"#,
        ),
        (
            "mods/worktree-tabs/controls.js",
            r#"const prefix = "worktree-tabs";"#,
        ),
        (
            "mods/worktree-tabs/controls.js",
            r#"const custom = () => nextCommand();"#,
        ),
        (
            "mods/worktree-tabs/controls.js",
            r#"import { nextCommand as waitCommand } from "herdr";"#,
        ),
        (
            "mods/worktree-tabs/controls.js",
            r#"const action = () => run("worktree\u002dtabs.custom", {});"#,
        ),
        (
            "mods/worktree-tabs/controls.js",
            r#"const action = () => run("worktree-t\abs.custom", {});"#,
        ),
        ("keys.json", r#"{"global":{"f2":"worktree-tabs.custom"}}"#),
        ("keys.json", r#"{"mod:worktree-tabs":{"f2":"custom"}}"#),
        ("keys.json", "{invalid"),
        ("keys.json", "[]"),
    ];
    for (path, value) in variants {
        let home = fixture(true);
        write(home.path(), path, value);
        let before = tree(home.path());
        assert_refused(home.path(), "workbench");
        assert_eq!(tree(home.path()), before);
    }
    let home = fixture(true);
    write(
        home.path(),
        "keys.json",
        r#"{"mod:worktree-tabs":{},"global":{"f2":"fictional-action"}}"#,
    );
    assert_plan_parity(home.path(), "workbench");
    let home = fixture(false);
    write(home.path(),"mods/tabs/main.js",TOOLBAR.replace("    const t = theme();","    const t = theme();\n    const fictional = { tabs: [] }; fictional.tabs.find(() => null);"));
    assert_plan_parity(home.path(), "main");
}
#[test]
fn bounded_ordered_json_rejects_duplicates_and_matches_python_escaping() {
    let home = fixture(true);
    let h = home.path();
    for payload in [
        r#"{"place":"top","title":"Personal","x":1,"x":2}"#.into(),
        format!("{{\"custom\":{}0{}}}", "[".repeat(128), "]".repeat(128)),
    ] {
        write(h, "mods/worktree-tabs/mod.json", payload);
        assert_refused(h, "workbench");
    }
    // Keep the tabs ID so metadata is parsed as the selected clone's metadata.
    let mut source = layout(true);
    source["children"][0]["content"]["mod"] = json!("worktree-tabs");
    write(h, "layouts/workbench.json", source.to_string());
    write(
        h,
        "mods/worktree-tabs/mod.json",
        format!("{{\"custom\":{}0{}}}", "[".repeat(127), "]".repeat(127)),
    );
    assert_plan_parity(h, "workbench");
    write(h,"mods/worktree-tabs/mod.json","{\"z\":\"🧭é\\u007f\",\"a\":123456789012345678901234567890,\"n\":[1e-7,1e20,1.0,-0.0,1e-4]}");
    assert_plan_parity(h, "workbench");
    write(
        h,
        "layouts/workbench.json",
        r#"{"id":"root","id":"duplicate","children":[]}"#,
    );
    assert_refused(h, "workbench");
}
#[test]
fn expected_state_native_failure_and_bundle_drift_prevent_publication() {
    for case in 0..6 {
        let home = fixture(true);
        let h = home.path();
        if case == 1 {
            fs::remove_file(h.join("keys.json")).unwrap();
        }
        let calls = Cell::new(0);
        let result = repair_integration(
            h,
            "workbench",
            true,
            |op| op(),
            || {
                let n = calls.get();
                calls.set(n + 1);
                Ok(if case == 4 && n >= 1 || case == 5 && n >= 2 {
                    "changed"
                } else {
                    "original"
                })
            },
            |_| {
                match case {
                    0 => write(h, "mods/worktree-tabs/controls.js", "concurrent edit"),
                    1 => write(
                        h,
                        "keys.json",
                        r#"{"global":{"f2":"worktree-tabs.custom"}}"#,
                    ),
                    2 => write(h, "mods/worktree-tabs/new.js", "concurrent addition"),
                    3 => return Err(IntegrationError::NativeCheck),
                    _ => (),
                }
                Ok(())
            },
        );
        assert!(result.is_err());
        assert!(!h.join("layouts/workbench-jira-peek.json").exists());
        assert!(!h.join("mods/workbench-tabs-jira-peek").exists());
    }
}
#[test]
fn diagnosis_is_read_only_and_never_claims_rendering() {
    let home = fixture(true);
    let h = home.path();
    let active = ActiveLayout {
        name: Some("workbench".into()),
        errors: false,
    };
    let before = tree(h);
    let report = diagnose_integration(h, None, active.clone(), BundleState::Valid).unwrap();
    assert_eq!(report.prepared, PreparedIntegration::None);
    assert_eq!(report.configured, ConfiguredIntegration::No);
    assert_eq!(
        toolbar_clone_origin(h, "worktree-tabs"),
        Some(("tabs".into(), "0.1.13".into()))
    );
    assert_eq!(toolbar_clone_origin(h, "tabs"), None);
    assert_eq!(report.next_action, NextAction::Repair);
    assert!(!report.rendering_verified);
    assert_eq!(tree(h), before);
    let plan = plan_attachment(h, "workbench", true).unwrap();
    apply_attachment(&plan, h).unwrap();
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.prepared, PreparedIntegration::Matching);
    assert_eq!(report.next_action, NextAction::SelectLayout);
    let active = ActiveLayout {
        name: Some("workbench-jira-peek".into()),
        errors: false,
    };
    let report = diagnose_integration(h, None, active.clone(), BundleState::Valid).unwrap();
    assert_eq!(report.configured, ConfiguredIntegration::Yes);
    assert_eq!(report.next_action, NextAction::VerifyButton);
    assert!(!report.rendering_verified);
    let errors = ActiveLayout {
        errors: true,
        ..active.clone()
    };
    assert_eq!(
        diagnose_integration(h, None, errors, BundleState::Valid)
            .unwrap()
            .next_action,
        NextAction::InspectHostErrors
    );
    write(
        h,
        "mods/workbench-tabs-jira-peek/controls.js",
        "personal changes",
    );
    let before = tree(h);
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.configured, ConfiguredIntegration::Personal);
    assert_eq!(report.next_action, NextAction::PersonalIntegration);
    assert_eq!(
        report.conflicts,
        vec![PathBuf::from("mods/workbench-tabs-jira-peek/controls.js")]
    );
    assert_eq!(tree(h), before);
    assert_refused(h, "workbench");
    assert_eq!(
        diagnose_integration(h, None, ActiveLayout::default(), BundleState::Valid)
            .unwrap()
            .next_action,
        NextAction::ChooseSource
    );
    assert_eq!(parse_active_layout(br#"{"layout":"workbench","errors":["fictional error"],"private":"must not be returned"}"#),ActiveLayout {name:Some("workbench".into()),errors:true});
    for status in [
        br#"{"layout":"../bad"}"#.as_slice(),
        br#"{"layout":"workbench","layout":"other"}"#,
        b"invalid",
    ] {
        assert_eq!(parse_active_layout(status), ActiveLayout::default());
    }
}

#[test]
fn partially_missing_generated_copy_is_repair_not_personal() {
    let home = fixture(false);
    let h = home.path();
    let plan = plan_attachment(h, "main", true).unwrap();
    apply_attachment(&plan, h).unwrap();
    fs::remove_file(h.join("mods/tabs-jira-peek/mod.json")).unwrap();
    let active = ActiveLayout {
        name: Some("main-jira-peek".into()),
        errors: false,
    };
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.prepared, PreparedIntegration::PartialOrConflicting);
    assert_eq!(report.configured, ConfiguredIntegration::No);
    assert_eq!(report.next_action, NextAction::Repair);
}
#[test]
fn unsupported_source_with_missing_generated_toolbar_is_unverified() {
    let home = fixture(false);
    let h = home.path();
    let plan = plan_attachment(h, "main", true).unwrap();
    apply_attachment(&plan, h).unwrap();
    fs::remove_dir_all(h.join("mods/tabs-jira-peek")).unwrap();
    write(h, "mods/tabs/main.js", "unsupported fictional toolbar");
    let active = ActiveLayout {
        name: Some("main-jira-peek".into()),
        errors: false,
    };
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.configured, ConfiguredIntegration::Unverified);
    assert_eq!(report.next_action, NextAction::ManualIntegration);
}
#[test]
fn explicit_source_diagnosis_is_not_hijacked_by_active_personal_layout() {
    let home = fixture(false);
    let h = home.path();
    let plan = plan_attachment(h, "main", true).unwrap();
    apply_attachment(&plan, h).unwrap();
    write(h, "layouts/other.json", layout(false).to_string());
    let active = ActiveLayout {
        name: Some("main-jira-peek".into()),
        errors: false,
    };
    let report = diagnose_integration(h, Some("other"), active, BundleState::Valid).unwrap();
    assert_eq!(report.source.as_deref(), Some("other"));
    assert_ne!(report.configured, ConfiguredIntegration::Personal);
    assert_eq!(report.next_action, NextAction::Repair);
}
#[test]
fn personal_generated_copy_is_not_reported_as_missing_or_broken() {
    let home = fixture(false);
    let h = home.path();
    let mut personal = layout(true);
    personal["children"][0]["content"]["mod"] = json!("tabs-jira-peek");
    personal["children"][1]["children"][1]["id"] = json!("jira-peek");
    write(h, "layouts/main-jira-peek.json", personal.to_string());
    write(h, "mods/tabs-jira-peek/main.js", "personal toolbar copy");
    write(
        h,
        "mods/tabs-jira-peek/mod.json",
        br#"{"place":"none","title":"Tabs with Jira Peek","cloned_from":{"name":"tabs","version":"0.1.11"}}"#,
    );
    let active = ActiveLayout {
        name: Some("main-jira-peek".into()),
        errors: false,
    };
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.configured, ConfiguredIntegration::Personal);
    assert_eq!(report.next_action, NextAction::PersonalIntegration);
    assert_eq!(
        toolbar_clone_origin(h, "tabs-jira-peek"),
        Some(("tabs".into(), "0.1.11".into()))
    );
    assert!(report
        .conflicts
        .contains(&PathBuf::from("mods/tabs-jira-peek/main.js")));
    assert_eq!(attachment_conflicts(h, "main").unwrap(), report.conflicts);
}
#[test]
fn rust_generated_toggle_behavior_preserves_q_and_actual_panel_target() {
    let source=TOOLBAR.replace("      .when(w?.buttons,","      .child(div().id(\"custom-q\").on_click(() => run(\"custom.q\", {})).child(\"Q\"))\n      .when(w?.buttons,");
    let generated = integrate_toolbar(&source, "peek-sidebar").unwrap();
    let mut child=Command::new("node").args(["--input-type=module","-e",r#"
import assert from 'node:assert/strict';
let generated=''; for await (const part of process.stdin) generated+=part;
function harness(panel) {
  const nodes=new Map(), calls=[];
  const element=id=>{
    const state={nodeId:id,children:[],events:{},properties:{}};
    const node=new Proxy(state,{get(target,key){
      if(key in target)return target[key];
      return (...args)=>{
        if(key==='id'){state.nodeId=args[0];nodes.set(args[0],node);}
        else if(key==='child')state.children.push(args[0]);
        else if(key==='when'){if(args[0])args[1](node);}
        else if(key.startsWith('on_'))state.events[key]=args.at(-1);
        else state.properties[key]=args[0];
        return node;
      };
    }}); if(id)nodes.set(id,node); return node;
  };
  const api={View:class{},div:()=>element(),h_flex:()=>element(),Toggle:{new:element},theme:()=>({}),window:()=>({}),settings:()=>({ui_font_size:13}),shared:()=>['files','changes'],layout:()=>({id:'root',children:panel?[panel]:[]}),run:(command,args)=>{calls.push({command,args});if(command==='layout.toggle'&&args.id===panel?.id)panel.hidden=!panel.hidden;}};
  const Tabs=new Function(...Object.keys(api),generated.replace(/^import .*;\n/gm,'').replace('export default class','return class'))(...Object.values(api));
  return {calls,render(){nodes.clear();return {tree:new Tabs().render(),nodes};}};
}
const panel={id:'peek-sidebar',hidden:true,content:{mod:'jira-peek'}};
const h=harness(panel);let {tree,nodes}=h.render();let button=nodes.get('panel-jira-peek');
assert.deepEqual(tree.children.map(n=>n.nodeId),['panel-files','panel-changes','panel-jira-peek','custom-q']);
assert.equal(button.properties.pressed,false);assert.equal(button.properties.accessibility_label,'Jira Peek');
let stopped=false;button.events.on_mouse_down({}, {stop_propagation(){stopped=true;}});assert.equal(stopped,true);
button.events.on_change();assert.equal(panel.hidden,false);assert.equal(h.render().nodes.get('panel-jira-peek').properties.pressed,true);
h.render().nodes.get('panel-jira-peek').events.on_change();assert.equal(panel.hidden,true);
h.render().nodes.get('custom-q').events.on_click();assert.deepEqual(h.calls,[{command:'layout.toggle',args:{id:'peek-sidebar'}},{command:'layout.toggle',args:{id:'peek-sidebar'}},{command:'custom.q',args:{}}]);
assert.equal(harness(null).render().nodes.has('panel-jira-peek'),false);
"#]).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(generated.as_bytes())
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}
#[test]
fn bounds_symlinks_retargeting_and_source_names_preserve_files() {
    let home = fixture(false);
    let h = home.path();
    for name in ["../main", "/main", "main/other", "main-jira-peek", ""] {
        assert_refused(h, name);
    }
    let plan = plan_attachment(h, "main", true).unwrap();
    apply_attachment(&plan, h).unwrap();
    let mut other = layout(true);
    other["children"][1]["children"][1]["id"] = json!("other-peek");
    write(h, "layouts/other.json", other.to_string());
    let before = tree(h);
    assert_refused(h, "other");
    assert_eq!(tree(h), before);
    let home = fixture(true);
    let h = home.path();
    let target = h.join("mods/worktree-tabs/controls.js");
    fs::remove_file(&target).unwrap();
    std::os::unix::fs::symlink(h.join("missing"), &target).unwrap();
    assert_refused(h, "workbench");
    let home = fixture(false);
    let h = home.path();
    for n in 0..256 {
        write(h, &format!("mods/tabs/{n}.js"), b"fixture");
    }
    assert_refused(h, "main");
    let home = fixture(false);
    let h = home.path();
    write(h, "mods/tabs/gpui-kit.d.ts", b"generated");
    write(h, "mods/tabs/jsconfig.json", b"generated");
    let plan = assert_plan_parity(h, "main");
    assert!(!plan
        .files()
        .keys()
        .any(|p| p.file_name().unwrap() == "gpui-kit.d.ts"));
    for depth in [61, 62, 63, 64, 65, 80] {
        let mut source = layout(false);
        for _ in 0..depth {
            source = json!({"children":[source]});
        }
        write(h, "layouts/main.json", source.to_string());
        let oracle_ok = oracle("plan", json!({"home":h,"source":"main"}))["ok"]
            .as_bool()
            .unwrap();
        assert_eq!(
            plan_attachment(h, "main", true).is_ok(),
            oracle_ok,
            "layout depth {depth}"
        );
    }
}
#[test]
fn diagnosis_bundle_states_unsupported_partial_and_explicit_source() {
    let home = fixture(true);
    let h = home.path();
    let active = ActiveLayout {
        name: Some("workbench".into()),
        errors: false,
    };
    assert_eq!(
        diagnose_integration(h, None, active.clone(), BundleState::Missing)
            .unwrap()
            .next_action,
        NextAction::InstallBundle
    );
    assert_eq!(
        diagnose_integration(h, None, active.clone(), BundleState::Invalid)
            .unwrap()
            .next_action,
        NextAction::PreserveBundle
    );
    let plan = plan_attachment(h, "workbench", true).unwrap();
    let main = plan.toolbar_directory().unwrap().join("main.js");
    fs::create_dir_all(main.parent().unwrap()).unwrap();
    fs::write(&main, &plan.files()[&main]).unwrap();
    let report = diagnose_integration(
        h,
        Some("workbench"),
        ActiveLayout::default(),
        BundleState::Valid,
    )
    .unwrap();
    assert_eq!(report.prepared, PreparedIntegration::PartialOrConflicting);
    assert_eq!(report.configured, ConfiguredIntegration::Unavailable);
    assert_eq!(report.next_action, NextAction::Repair);
    write(
        h,
        "mods/worktree-tabs/main.js",
        "unsupported custom toolbar",
    );
    let before = tree(h);
    let report = diagnose_integration(h, None, active, BundleState::Valid).unwrap();
    assert_eq!(report.next_action, NextAction::ManualIntegration);
    assert!(report.unsupported.is_some());
    assert!(!report.rendering_verified);
    assert_eq!(tree(h), before);
}
