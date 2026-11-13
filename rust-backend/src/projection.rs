use crate::config::{csv, matches, Config};
use serde_json::{json, Value};
pub fn cut(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}
fn len(s: &str) -> usize {
    s.chars().count()
}
fn text(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Bool(_) | Value::Number(_) => v.to_string(),
        _ => String::new(),
    }
}
pub fn clean(s: &str) -> String {
    s.replace("\r\n","\n").replace('\r',"\n").chars().filter(|c|!matches!(*c,'\u{0}'..='\u{8}'|'\u{b}'|'\u{c}'|'\u{e}'..='\u{1f}'|'\u{7f}'..='\u{9f}'|'\u{200b}'..='\u{200f}'|'\u{202a}'..='\u{202e}'|'\u{2060}'..='\u{206f}'|'\u{feff}')).collect()
}
fn string(v: &Value) -> String {
    clean(v.as_str().unwrap_or(""))
}
fn line(s: &str) -> String {
    let mut result = String::new();
    let mut space = false;
    for c in s.replace("\r\n", "\n").replace('\r', "\n").chars() {
        if matches!(c, '\n' | '\t') {
            if !space {
                result.push(' ')
            }
            space = true;
        } else {
            result.push(if matches!(c,'\u{0}'..='\u{8}'|'\u{b}'|'\u{c}'|'\u{e}'..='\u{1f}'|'\u{7f}'..='\u{9f}'){' '}else{c});
            space = false
        }
    }
    clean(&result)
}
fn visible(v: &Value) -> String {
    match v {
        Value::Array(a) => a
            .iter()
            .map(visible)
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>()
            .join(", "),
        Value::Object(_) => ["displayName", "name", "value", "key"]
            .iter()
            .find_map(|k| (!v[k].is_null() && v[k] != false).then(|| text(&v[k])))
            .unwrap_or_default(),
        _ => text(v),
    }
}
fn children(v: &Value) -> &[Value] {
    v["content"].as_array().map(Vec::as_slice).unwrap_or(&[])
}
fn inline(v: &Value) -> String {
    if let Some(a) = v.as_array() {
        return a.iter().map(inline).collect::<Vec<_>>().join(" ");
    }
    if !v.is_object() {
        return text(v);
    }
    match v["type"].as_str().unwrap_or("") {
        "text" => text(&v["text"]),
        "hardBreak" => " ".into(),
        _ => children(v).iter().map(inline).collect::<Vec<_>>().join(" "),
    }
}
pub fn raw<'a>(v: &'a Value, id: &str) -> &'a Value {
    if id == "key" {
        return &v["key"];
    }
    if v["fields"].as_object().is_some_and(|o| o.contains_key(id)) {
        &v["fields"][id]
    } else {
        &v[id]
    }
}
pub fn label(id: &str, labels: &str) -> String {
    for p in labels.split(',') {
        if let Some((k, l)) = p.split_once(':') {
            if k == id {
                return l.into();
            }
        }
    }
    match id {
        "key" => "Key",
        "summary" => "Summary",
        "status" => "Status",
        "assignee" => "Assignee",
        "reporter" => "Reporter",
        "priority" => "Priority",
        "issuetype" => "Type",
        "project" => "Project",
        "created" => "Created",
        "updated" => "Updated",
        "duedate" => "Due date",
        "resolution" => "Resolution",
        "labels" => "Labels",
        "components" => "Components",
        "fixVersions" => "Fix versions",
        "versions" => "Affects versions",
        "parent" => "Parent",
        "issuelinks" => "Linked Issues",
        "description" => "Description",
        "comments" => "Comments",
        "link" => "Link",
        _ => id,
    }
    .into()
}
fn known(t: &str) -> bool {
    matches!(
        t,
        "text"
            | "hardBreak"
            | "mention"
            | "emoji"
            | "media"
            | "mediaInline"
            | "inlineCard"
            | "blockCard"
            | "embedCard"
            | "rule"
            | "orderedList"
            | "doc"
            | "paragraph"
            | "heading"
            | "codeBlock"
            | "blockquote"
            | "bulletList"
            | "listItem"
            | "table"
            | "tableRow"
            | "tableCell"
            | "tableHeader"
            | "mediaSingle"
            | "mediaGroup"
            | "panel"
            | "expand"
            | "nestedExpand"
            | "taskList"
            | "taskItem"
            | "decisionList"
            | "decisionItem"
            | "status"
    )
}
fn unsupported(v: &Value) -> bool {
    if let Some(a) = v.as_array() {
        a.iter().any(unsupported)
    } else if v.is_object() {
        !known(v["type"].as_str().unwrap_or("")) || children(v).iter().any(unsupported)
    } else {
        false
    }
}
fn child_body(v: &Value) -> String {
    children(v).iter().map(body).collect()
}
fn cell(v: &Value) -> String {
    let s = child_body(v);
    let mut out = String::new();
    let mut newline = false;
    for c in s.chars() {
        if c == '\n' {
            if !newline {
                out.push(' ')
            }
            newline = true;
        } else {
            out.push(c);
            newline = false;
        }
    }
    out.trim_end_matches(' ').into()
}
pub fn body(v: &Value) -> String {
    if let Some(s) = v.as_str() {
        return clean(s);
    }
    if let Some(a) = v.as_array() {
        return a.iter().map(body).collect();
    }
    if !v.is_object() {
        return String::new();
    }
    let t = v["type"].as_str().unwrap_or("");
    let attrs = &v["attrs"];
    match t {
        "text" => string(&v["text"]),
        "hardBreak" => "\n".into(),
        "mention" => attrs["text"]
            .as_str()
            .map(clean)
            .unwrap_or("@mention".into()),
        "emoji" => string(if attrs["text"].is_null() || attrs["text"] == false {
            &attrs["shortName"]
        } else {
            &attrs["text"]
        }),
        "status" => string(&attrs["text"]),
        "media" | "mediaInline" => "[Attachment]".into(),
        "inlineCard" | "blockCard" | "embedCard" => "[Linked content]".into(),
        "rule" => "────────\n\n".into(),
        "orderedList" => {
            children(v)
                .iter()
                .enumerate()
                .map(|(i, x)| {
                    let item = body(x);
                    format!(
                        "{}. {}\n",
                        i + 1,
                        item.strip_prefix("• ")
                            .unwrap_or(&item)
                            .trim_end_matches('\n')
                    )
                })
                .collect::<String>()
                + "\n"
        }
        "panel" | "expand" | "nestedExpand" => {
            let title = if t == "panel" {
                match attrs["panelType"].as_str().unwrap_or("") {
                    "info" => "Info",
                    "warning" => "Warning",
                    "success" => "Success",
                    "error" => "Error",
                    _ => "Note",
                }
                .into()
            } else {
                string(&attrs["title"])
            };
            format!(
                "{}{}\n\n",
                if title.is_empty() {
                    title
                } else {
                    title + "\n"
                },
                child_body(v)
            )
        }
        "table" => {
            let rows = children(v);
            let merged = rows.iter().flat_map(children).any(|x| {
                ["colspan", "rowspan"]
                    .iter()
                    .any(|k| !x["attrs"][k].is_null() && x["attrs"][k] != 1)
            });
            if rows.len() > 1
                && !children(&rows[0]).is_empty()
                && children(&rows[0])
                    .iter()
                    .all(|x| x["type"] == "tableHeader")
                && !merged
            {
                let labels: Vec<_> = children(&rows[0]).iter().map(cell).collect();
                rows[1..]
                    .iter()
                    .map(|r| {
                        let cells = children(r);
                        (0..labels.len().max(cells.len()))
                            .map(|i| {
                                let label = labels
                                    .get(i)
                                    .filter(|s| !s.is_empty())
                                    .cloned()
                                    .unwrap_or(format!("Column {}", i + 1));
                                let value = cells
                                    .get(i)
                                    .map(cell)
                                    .filter(|s| !s.is_empty())
                                    .unwrap_or("—".into());
                                format!("{label}: {value}")
                            })
                            .collect::<Vec<_>>()
                            .join("\n")
                    })
                    .collect::<Vec<_>>()
                    .join("\n\n")
                    + "\n\n"
            } else {
                format!(
                    "{}{}\n\n",
                    if merged {
                        "[Table has merged cells. Open in Jira for column relationships.]\n"
                    } else {
                        ""
                    },
                    child_body(v)
                )
            }
        }
        _ if known(t) => {
            let s = child_body(v);
            let trim = s.trim_end_matches('\n');
            match t {
                "listItem" => format!("• {trim}\n"),
                "taskItem" => format!(
                    "[{}] {trim}\n",
                    if attrs["state"] == "DONE" { "x" } else { " " }
                ),
                "decisionItem" => format!("Decision: {trim}\n"),
                "heading" => format!("{trim}\n────────\n\n"),
                "codeBlock" | "blockquote" => {
                    trim.split('\n')
                        .map(|l| format!("{}{l}", if t == "codeBlock" { "    " } else { "│ " }))
                        .collect::<Vec<_>>()
                        .join("\n")
                        + "\n\n"
                }
                "tableRow" => s.strip_suffix("  │  ").unwrap_or(&s).to_owned() + "\n",
                "tableCell" | "tableHeader" => cell(v) + "  │  ",
                "paragraph" | "bulletList" => s + "\n\n",
                _ => s,
            }
        }
        _ => "[Unsupported content]\n\n".into(),
    }
}
fn link_line(v: &Value) -> String {
    format!(
        "{}: {}{}{}",
        v["label"].as_str().unwrap_or(""),
        v["key"].as_str().unwrap_or(""),
        if v["summary"] == "" {
            String::new()
        } else {
            format!(" — {}", v["summary"].as_str().unwrap_or(""))
        },
        if v["status"] == "" {
            String::new()
        } else {
            format!(" [{}]", v["status"].as_str().unwrap_or(""))
        }
    )
}
fn links(v: &Value) -> Value {
    let mut out = json!({"state":if v.is_array(){"available"}else{"unavailable"},"records":[],"malformed":false,"truncated":false});
    let mut records = vec![];
    let mut remaining = 20000i64;
    for l in v.as_array().map(Vec::as_slice).unwrap_or(&[]) {
        if !l.is_object() || (!l.get("inwardIssue").is_some() && !l.get("outwardIssue").is_some()) {
            out["malformed"] = json!(true);
            continue;
        }
        for direction in ["inward", "outward"] {
            let Some(target) = l.get(format!("{direction}Issue")) else {
                continue;
            };
            let key = target["key"].as_str().unwrap_or("");
            if !matches(r"^[A-Z][A-Z0-9_]*-[0-9]+$", key) || len(key) > 512 {
                out["malformed"] = json!(true);
                continue;
            }
            let kind = &l["type"];
            let typ = if !kind["id"].is_null() {
                format!("id:{}", line(&text(&kind["id"])))
            } else if !kind["name"].is_null() {
                format!("name:{}", line(&text(&kind["name"])))
            } else {
                "unknown".into()
            };
            let label = line(&text(&kind[direction]));
            let label = if label.is_empty() {
                "Linked issue".into()
            } else {
                label
            };
            let summary = line(&text(&target["fields"]["summary"]));
            let status = line(&visible(&target["fields"]["status"]));
            if len(&label) > 256 || len(&summary) > 4096 || len(&status) > 256 {
                out["truncated"] = json!(true)
            }
            let r = json!({"id":cut(&line(&text(&l["id"])),128),"type":cut(&typ,256),"direction":direction,"label":cut(&label,256),"key":key,"summary":cut(&summary,4096),"status":cut(&status,256)});
            let size = len(&link_line(&r)) as i64;
            if records.len() >= 100 || size > remaining {
                out["truncated"] = json!(true)
            } else {
                records.push(r);
                remaining -= size + 1;
            }
        }
    }
    out["records"] = json!(records);
    out
}
fn links_text(v: &Value) -> String {
    let mut s = if v["state"] == "unavailable" {
        "Linked issue data unavailable".into()
    } else if v["records"].as_array().unwrap().is_empty() && v["malformed"] == false {
        "No linked issues returned".into()
    } else {
        v["records"]
            .as_array()
            .unwrap()
            .iter()
            .map(link_line)
            .collect::<Vec<_>>()
            .join("\n")
    };
    if v["malformed"] == true {
        s += "\nSome returned link data could not be displayed."
    }
    if v["truncated"] == true {
        s += "\nLinked issues are shortened. Open in Jira for the full relationships."
    }
    s
}
fn app(v: &Value, id: &str) -> String {
    let r = raw(v, id);
    line(&if id == "issuelinks" {
        links_text(&links(r))
    } else if r["type"] == "doc" {
        inline(r)
    } else {
        visible(r)
    })
}
fn reader(v: &Value, id: &str) -> String {
    let r = raw(v, id);
    if id == "issuelinks" {
        links_text(&links(r))
    } else if r["type"] == "doc" {
        body(r)
    } else {
        clean(&visible(r))
    }
}
pub fn row(v: &Value, picker: &str) -> Value {
    json!({"key":v["key"],"summary":cut(&app(v,"summary"),4096),"status":cut(&app(v,"status"),4096),"values":csv(picker).iter().map(|id|cut(&app(v,id),4096)).collect::<Vec<_>>()})
}
pub fn issue(v: &Value, c: &Config) -> Value {
    let selected = csv(c.get("READER_FIELDS"));
    let has = |s: &str| selected.iter().any(|v| v == s);
    let description = if has("description") {
        body(raw(v, "description"))
    } else {
        String::new()
    };
    let cv = raw(v, "comments");
    let comments: Vec<_> = if has("comments") {
        cv.as_array()
            .or_else(|| cv["comments"].as_array())
            .map(|a| a.iter().filter(|x| x.is_object()).collect())
            .unwrap_or_default()
    } else {
        vec![]
    };
    let reported = if has("comments") {
        cv["total"].as_f64().unwrap_or(0.)
    } else {
        0.
    };
    let mut truncated =
        len(&description) > 100000 || comments.len() > 100 || reported > comments.len() as f64;
    let mut unsupported_content = has("description") && unsupported(raw(v, "description"));
    let mut remaining = 1000000;
    let projected:Vec<_>=comments.iter().take(100).map(|x|{let s=body(&x["body"]);let size=len(&s).min(20000).min(remaining);remaining-=size;truncated|=len(&s)>size;unsupported_content|=unsupported(&x["body"]);let author=if x["author"].is_object(){&x["author"]["displayName"]}else{&x["author"]};json!({"author":cut(&if author.is_null()||*author==false{"Unknown author".into()}else{string(author)},256),"created":cut(&string(&x["created"]),128),"body":cut(&s,size)})}).collect();
    let metadata:Vec<_>=selected.iter().filter(|id|!matches!(id.as_str(),"key"|"summary"|"description"|"comments"|"link")).map(|id|{let value=reader(v,id);let linked=if id=="issuelinks"{links(raw(v,id))}else{Value::Null};let short=len(&value)>20000||linked["truncated"]==true;truncated|=short;let mut m=json!({"id":id,"label":cut(&clean(&label(id,c.get("FIELD_LABELS"))),256),"value":cut(&value,20000),"truncated":short,"unsupportedContent":raw(v,id)["type"]=="doc"&&unsupported(raw(v,id))});if id=="issuelinks"{m["links"]=linked}m}).collect();
    for id in csv(&format!("summary,status,{}", c.get("PICKER_FIELDS"))) {
        truncated |= len(&app(v, &id)) > 4096;
    }
    let mut out = row(v, c.get("PICKER_FIELDS"));
    out["metadata"] = json!(metadata);
    out["description"] = json!(cut(&description, 100000));
    out["commentsDeferred"] = json!(has("comments") && v["_peek_comments_deferred"] == true);
    out["commentsTotal"] = if reported > comments.len() as f64 {
        cv["total"].clone()
    } else {
        json!(comments.len())
    };
    out["unsupportedContent"] = json!(unsupported_content);
    out["truncated"] = json!(truncated);
    out["comments"] = json!(projected);
    out
}
