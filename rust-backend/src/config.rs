use crate::{fail, Result};
use regex::Regex;
use std::collections::{BTreeSet, HashMap};

fn valid_ere(pattern: &str) -> bool {
    let Ok(pattern) = std::ffi::CString::new(pattern) else {
        return false;
    };
    extern "C" {
        fn jira_peek_valid_ere(pattern: *const libc::c_char) -> libc::c_int;
    }
    unsafe { jira_peek_valid_ere(pattern.as_ptr()) != 0 }
}
pub fn matches(pattern: &str, text: &str) -> bool {
    Regex::new(pattern).is_ok_and(|r| r.is_match(text))
}
pub fn field(id: &str) -> bool {
    matches(
        r"^(summary|status|assignee|reporter|priority|issuetype|project|created|updated|duedate|resolution|labels|components|fixVersions|versions|parent|issuelinks|customfield_[0-9]{1,12})$",
        id,
    )
}
pub fn fields(s: &str, picker: bool) -> bool {
    if s.is_empty() {
        return true;
    }
    let mut seen = BTreeSet::new();
    s.split(',').all(|id| {
        seen.insert(id)
            && if picker {
                field(id)
            } else {
                id != "summary" && (field(id) || matches(r"^(description|comments|link)$", id))
            }
    })
}
pub fn csv(s: &str) -> Vec<String> {
    s.split(',')
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .collect()
}
#[derive(Clone)]
pub struct Config {
    pub v: HashMap<String, String>,
}
impl Config {
    pub fn get(&self, k: &str) -> &str {
        self.v.get(k).map(String::as_str).unwrap_or("")
    }
    pub fn number(&self, k: &str) -> u64 {
        self.get(k).parse().unwrap_or(0)
    }
    pub fn load(bytes: &[u8]) -> Result<Self> {
        let mut v: HashMap<String, String> = HashMap::new();
        for (k, val) in [
            ("JIRA_BACKEND", "twg"),
            ("CACHE_TTL_MIN", "10"),
            ("MAX_CANDIDATES", "20"),
            ("AUTO_REFRESH_SEC", "2"),
            ("PICKER_LAYOUT", "bottom"),
            ("SOURCE_HIGHLIGHT", "off"),
            ("PICKER_FIELDS", "status,summary"),
            (
                "PREVIEW_FIELDS",
                "status,assignee,updated,description,comments",
            ),
            (
                "READER_FIELDS",
                "status,assignee,updated,link,description,comments",
            ),
            ("TEXT_STYLE", "bold"),
        ] {
            v.insert(k.into(), val.into());
        }
        let data = String::from_utf8(bytes.to_vec()).map_err(|_| fail("connection_failed"))?;
        for line in data.split('\n') {
            let line = line.trim_start_matches(|c: char| c.is_ascii_whitespace() || c == '\u{b}');
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (k, raw) = line.split_once('=').ok_or(fail("connection_failed"))?;
            if !matches(
                r"^(JIRA_BASE|JIRA_SITE|JIRA_BACKEND|JIRA_CLOUD_ID|JIRA_NETRC_FILE|JIRA_PROJECTS|CACHE_TTL_MIN|MAX_CANDIDATES|AUTO_REFRESH_SEC|PICKER_LAYOUT|SOURCE_HIGHLIGHT|KEY_RE|PICKER_FIELDS|PREVIEW_FIELDS|READER_FIELDS|FIELD_LABELS|COLOR_THEME|TEXT_STYLE)$",
                k,
            ) {
                return Err(fail("connection_failed"));
            }
            let raw = raw.trim_matches(|c: char| c.is_ascii_whitespace() || c == '\u{b}');
            let value = if raw.len() >= 2
                && ((raw.starts_with('\'') && raw.ends_with('\''))
                    || (raw.starts_with('"') && raw.ends_with('"')))
            {
                &raw[1..raw.len() - 1]
            } else {
                if raw.contains(['\'', '"']) {
                    return Err(fail("connection_failed"));
                }
                raw
            };
            v.insert(k.into(), value.into());
        }
        if let Some(b) = v.get_mut("JIRA_BASE") {
            *b = b.trim_end_matches('/').into();
        }
        let c = Self { v };
        let valid = matches(
            r"^https://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]+)?$",
            c.get("JIRA_BASE"),
        ) && matches(
            r"^[A-Z][A-Z0-9_]*(\|[A-Z][A-Z0-9_]*)*$",
            c.get("JIRA_PROJECTS"),
        ) && matches(r"^(twg|rest)$", c.get("JIRA_BACKEND"))
            && matches(r"^[0-9]+$", c.get("CACHE_TTL_MIN"))
            && c.get("CACHE_TTL_MIN").parse::<u64>().is_ok()
            && matches(r"^[0-9]+$", c.get("MAX_CANDIDATES"))
            && (1..=100).contains(&c.number("MAX_CANDIDATES"))
            && matches(r"^(0|[1-9]|[1-5][0-9]|60)$", c.get("AUTO_REFRESH_SEC"))
            && matches(r"^(top|bottom)$", c.get("PICKER_LAYOUT"))
            && matches(r"^(off|auto)$", c.get("SOURCE_HIGHLIGHT"))
            && matches(r"^(plain|bold)$", c.get("TEXT_STYLE"))
            && (!c.v.contains_key("COLOR_THEME")
                || matches(r"^(terminal|ocean|warm|mono)$", c.get("COLOR_THEME")))
            && fields(c.get("PICKER_FIELDS"), true)
            && fields(c.get("READER_FIELDS"), false)
            && fields(c.get("PREVIEW_FIELDS"), false)
            && (c.get("KEY_RE").is_empty() || valid_ere(c.get("KEY_RE")));
        if !valid {
            return Err(fail("connection_failed"));
        }
        if c.get("JIRA_BACKEND") == "twg" {
            if !matches(r"^[A-Za-z0-9._:-]+$", c.get("JIRA_SITE")) {
                return Err(fail("connection_failed"));
            }
        } else if !matches(r"^[A-Za-z0-9_-]*$", c.get("JIRA_CLOUD_ID")) {
            return Err(fail("connection_failed"));
        }
        let mut seen = BTreeSet::new();
        for pair in c
            .get("FIELD_LABELS")
            .split(',')
            .filter(|_| !c.get("FIELD_LABELS").is_empty())
        {
            let (id, label) = pair.split_once(':').ok_or(fail("connection_failed"))?;
            if !(field(id) || matches(r"^(description|comments|link)$", id))
                || !seen.insert(id.to_owned())
                || label.trim().is_empty()
                || !matches(r"^[A-Za-z0-9_. -]+$", label)
            {
                return Err(fail("connection_failed"));
            }
        }
        Ok(c)
    }
    pub fn key(&self, key: &str) -> bool {
        key.rsplit_once('-').is_some_and(|(p, n)| {
            self.get("JIRA_PROJECTS").split('|').any(|x| x == p)
                && !n.is_empty()
                && n.bytes().all(|b| b.is_ascii_digit())
        })
    }
    pub fn detail(&self) -> String {
        csv(&format!(
            "summary,{},{}",
            self.get("PICKER_FIELDS"),
            self.get("READER_FIELDS")
        ))
        .into_iter()
        .filter(|s| s != "link" && s != "comments")
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>()
        .join(",")
    }
    pub fn comments(&self) -> bool {
        csv(self.get("READER_FIELDS"))
            .iter()
            .any(|s| s == "comments")
    }
    pub fn signature(&self) -> String {
        format!(
            "v1:{}:comments={}{}",
            self.detail(),
            u8::from(self.comments()),
            if self.get("JIRA_BACKEND") == "rest" {
                ":native-v2"
            } else {
                ""
            }
        )
    }
    pub fn metadata(&self) -> Vec<String> {
        let mut seen = BTreeSet::new();
        csv(&format!("summary,{}", self.get("PICKER_FIELDS")))
            .into_iter()
            .filter(|s| seen.insert(s.clone()))
            .collect()
    }
}
