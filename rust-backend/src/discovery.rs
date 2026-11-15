//! Explicit, scoped read discovery. Never accepts raw JQL or terminal text.
use crate::{
    config::{matches, Config},
    fail, projection, transport, Result,
};
use serde_json::{json, Value};

fn quoted(s: &str) -> String {
    serde_json::to_string(s).unwrap()
}
fn query(c: &Config, mode: &str, text: &str) -> Result<String> {
    if text.len() > 512 || text.chars().any(char::is_control) {
        return Err(fail("invalid_request"));
    }
    let predicate = match mode {
        "mine" if text.is_empty() => "assignee = currentUser() AND resolution = Unresolved".into(),
        "text" if !text.trim().is_empty() => {
            let text = text.trim();
            if matches(r"^[A-Za-z][A-Za-z0-9_]*-[0-9]+$", text) {
                if !c.key(text) {
                    return Err(fail("invalid_request"));
                }
                format!("key = {}", quoted(text))
            } else {
                // Literal phrase: escape Lucene syntax, then the enclosing JQL string.
                let mut literal = String::new();
                for ch in text.chars() {
                    if "+-&|!(){}[]^\"~*?:\\/".contains(ch) {
                        literal.push('\\');
                    }
                    literal.push(ch);
                }
                format!("text ~ {}", quoted(&format!("\"{literal}\"")))
            }
        }
        _ => return Err(fail("invalid_request")),
    };
    let projects = c
        .get("JIRA_PROJECTS")
        .split('|')
        .map(quoted)
        .collect::<Vec<_>>()
        .join(",");
    Ok(format!(
        "project in ({projects}) AND ({predicate}) ORDER BY updated DESC, key ASC"
    ))
}

pub fn fetch(c: &Config, args: &[String]) -> Result<Value> {
    if args.len() != 3 || args[2].len() > 4096 || args[2].chars().any(char::is_control) {
        return Err(fail("invalid_request"));
    }
    let jql = query(c, &args[0], &args[1])?;
    if c.get("JIRA_BACKEND") != "rest" {
        return Err(fail("discovery_unsupported"));
    }
    let mut body = json!({"jql":jql,"maxResults":50,"fields":c.metadata()});
    if !args[2].is_empty() {
        body["nextPageToken"] = json!(args[2]);
    }
    let response = transport::http(
        c,
        format!("{}/rest/api/3/search/jql", transport::origin(c)),
        Some(body),
        true,
    )?;
    page(c, &response)
}

fn page(c: &Config, response: &Value) -> Result<Value> {
    let issues = response["issues"]
        .as_array()
        .ok_or(fail("request_failed"))?;
    let last = response["isLast"].as_bool().ok_or(fail("request_failed"))?;
    let token = response["nextPageToken"].as_str().unwrap_or("");
    if issues.len() > 50
        || token.len() > 4096
        || token.chars().any(char::is_control)
        || (!last && token.is_empty())
    {
        return Err(fail("request_failed"));
    }
    let mut rows = Vec::new();
    for issue in issues {
        if !issue["key"].as_str().is_some_and(|k| c.key(k)) || !issue["fields"].is_object() {
            return Err(fail("invalid_request"));
        }
        rows.push(projection::row(issue, c.get("PICKER_FIELDS")));
    }
    Ok(json!({"rows":rows,"nextPageToken":if last { "" } else { token },"isLast":last}))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn config() -> Config {
        Config::load(
            b"JIRA_BASE=https://jira.example.test\nJIRA_PROJECTS=ABC\nJIRA_SITE=fictional\n",
        )
        .unwrap()
    }
    #[test]
    fn scope_and_literals() {
        let c = config();
        assert!(query(&c, "mine", "")
            .unwrap()
            .contains("project in (\"ABC\") AND (assignee = currentUser()"));
        assert!(query(&c, "text", "XYZ-1").is_err());
        assert!(query(&c, "text", "a\nb").is_err());
        assert!(query(&c, "text", "ABC-1")
            .unwrap()
            .contains("key = \"ABC-1\""));
        let q = query(&c, "text", "a\" OR project = XYZ").unwrap();
        assert!(q.contains("text ~ \"\\\"a\\\\\\\" OR project = XYZ\\\"\""));
    }
    #[test]
    fn hyphenated_words_are_literal_text_not_issue_keys() {
        let c = config();
        for text in ["front-end", "ABC-no"] {
            let q = query(&c, "text", text).unwrap();
            let literal = format!("\"{}\"", text.replace('-', "\\-"));
            assert_eq!(
                q,
                format!(
                    "project in (\"ABC\") AND (text ~ {}) ORDER BY updated DESC, key ASC",
                    quoted(&literal)
                )
            );
        }
        for key in ["XYZ-1", "abc-1"] {
            assert!(query(&c, "text", key).is_err());
        }
    }
    #[test]
    fn validate_pages() {
        let c = config();
        assert!(page(&c, &json!({"issues":[],"isLast":false})).is_err());
        assert!(page(
            &c,
            &json!({"issues":[{"key":"XYZ-1","fields":{}}],"isLast":true})
        )
        .is_err());
        assert_eq!(
            page(&c, &json!({"issues":[],"isLast":true})).unwrap()["nextPageToken"],
            ""
        );
    }
}
