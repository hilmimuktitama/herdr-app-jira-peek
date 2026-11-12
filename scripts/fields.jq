# Shared Jira field lookup and presentation helpers.
#
# Resolve configured fields from canonical nested issues and older flattened
# cache entries. Keep native projection helpers in this module: nesting them
# through another module triggers a compiler abort in jq 1.8.2.
module {
  "name": "jira_peek_fields"
};

def field_names:
  {
    key: "Key",
    summary: "Summary",
    status: "Status",
    assignee: "Assignee",
    reporter: "Reporter",
    priority: "Priority",
    issuetype: "Type",
    project: "Project",
    created: "Created",
    updated: "Updated",
    duedate: "Due date",
    resolution: "Resolution",
    labels: "Labels",
    components: "Components",
    fixVersions: "Fix versions",
    versions: "Affects versions",
    parent: "Parent",
    issuelinks: "Linked Issues",
    description: "Description",
    comments: "Comments",
    link: "Link"
  };

def text_value:
  if . == null then ""
  elif type == "string" then .
  elif type == "number" or type == "boolean" then tostring
  else ""
  end;

def field_clean:
  tostring
  | gsub("\r\n|\r"; "\n")
  | gsub("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]"; " ")
  | gsub("[\r\n\t]+"; " ");

# Turn common Jira objects into one safe display string. Unknown objects are
# intentionally reduced to a useful name/id/value instead of being dumped as
# arbitrary JSON metadata.
def display_value:
  if . == null then ""
  elif type == "string" or type == "number" or type == "boolean" then tostring
  elif type == "array" then map(display_value | select(length > 0)) | join(", ")
  elif type == "object" then
    (if .displayName != null then .displayName
     elif .name != null then .name
     elif .value != null then .value
     elif .key != null then .key
     elif .id != null then .id
     else "" end) | text_value
  else ""
  end;

# Project Atlassian Document Format to a safe one-line picker value. This is
# deliberately smaller than the reader's full renderer: recognized text nodes
# survive, while attributes, links, mentions, and unknown metadata do not.
def rich_inline:
  if . == null then ""
  elif type == "string" or type == "number" or type == "boolean" then tostring
  elif type == "array" then map(rich_inline) | join(" ")
  elif type == "object" and .type == "text" then (.text // "") | text_value
  elif type == "object" and .type == "hardBreak" then " "
  elif type == "object" and (.content|type) == "array" then (.content | map(rich_inline) | join(" "))
  else ""
  end;
def rich_value:
  if type == "object" and .type == "doc" and (.content|type) == "array"
  then (.content | map(rich_inline) | join(" "))
  else ""
  end;

# Return the requested field from the canonical {fields:{...}} shape, while
# accepting the flattened aliases used by older cached responses.
def field_raw($id):
  if $id == "key" then .key
  elif $id == "link" then
    (if .link != null then .link
     elif .url != null then .url
     elif (.fields|type) == "object" and (.fields|has("link")) then .fields.link
     elif (.fields|type) == "object" and (.fields|has("url")) then .fields.url
     else null end)
  elif ($id == "comments" or $id == "description") then
    (if (.fields|type) == "object" and (.fields|has($id)) then .fields[$id] else .[$id] end)
  elif (.fields|type) == "object" and (.fields|has($id)) then .fields[$id]
  else .[$id]
  end;

# Safe scalar form for transport/picker extraction. Description and comments
# remain intentionally empty here because they are rendered as structured
# bodies by render.jq; callers should use field_raw for those fields.
def field_value($id):
  field_raw($id)
  | if . == null then ""
    elif $id == "description" or $id == "comments" then ""
    elif type == "object" and .type == "doc" then rich_value | field_clean
    else display_value | field_clean
    end;

def parse_labels:
  if type == "object" then .
  elif type == "string" then
    split(",")
    | map(select(length > 0) | split(":")
        | select(length >= 2 and .[0] != "" and (.[1:] | join(":")) != "")
        | {key: .[0], value: (.[1:] | join(":"))})
    | from_entries
  else {}
  end;

def field_label($id; $labels):
  ($labels | parse_labels) as $custom
  | ($custom[$id] // field_names[$id] // $id);

# Shared native-only text and picker projection.
def clean:
  if type == "string" then
    gsub("\r\n|\r"; "\n") | gsub("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"; "")
  else "" end;
def visible_value:
  if type == "array" then map(visible_value | select(length > 0)) | join(", ")
  elif type == "object" then (.displayName // .name // .value // .key // "") | text_value
  else text_value end;
# Bound structured relationships once; the UI never follows supplied URLs.
def link_line:
  .label + ": " + .key + (if .summary == "" then "" else " — " + .summary end)
  + (if .status == "" then "" else " [" + .status + "]" end);
def link_string: text_value | field_clean | clean;
def linked_projection:
  . as $raw
  | (if type == "array" then . else [] end) as $input
  | [$input[] | . as $link | if type != "object" then null else
      (if (.type|type) == "object" then .type else {} end) as $kind
      | if (has("inwardIssue") or has("outwardIssue")) then
        ("inward", "outward") as $direction
        | select($link | has($direction + "Issue"))
        | $link[$direction + "Issue"]
        | if type != "object" then null
          elif (.key|type) != "string" then null
          elif (.key|test("^[A-Z][A-Z0-9_]*-[0-9]+$")|not) or (.key|length)>512 then null
          else . as $target
          | (if (.fields|type) == "object" then .fields else {} end) as $fields
          | {id:($link.id|link_string|.[0:128]),
             type: ((if $kind.id != null then "id:" + ($kind.id|link_string) elif $kind.name != null then "name:" + ($kind.name|link_string) else "unknown" end)|.[0:256]),
             direction:$direction, label:($kind[$direction]|link_string|if .=="" then "Linked issue" else . end),
             key:$target.key, summary:($fields.summary|link_string), status:($fields.status|visible_value|field_clean|clean)}
          end
        else null end end] as $entries
  | reduce $entries[] as $entry
      ({state:(if ($raw|type)=="array" then "available" else "unavailable" end), records:[], malformed:false, truncated:false, remaining:20000};
       if $entry == null then .malformed=true
       else ($entry + {label:$entry.label[0:256],summary:$entry.summary[0:4096],status:$entry.status[0:256]}) as $bounded
       | .truncated = (.truncated or $bounded != $entry)
       | ($bounded|link_line|length) as $size
       | if (.records|length)>=100 or $size > .remaining then .truncated=true
         else .records += [$bounded] | .remaining -= ($size + 1) end end)
  | del(.remaining);
def linked_text:
  (if .state == "unavailable" then "Linked issue data unavailable"
   elif (.records|length)==0 and (.malformed|not) then "No linked issues returned"
   else .records | map(link_line) | join("\n") end)
  + (if .malformed then "\nSome returned link data could not be displayed." else "" end)
  + (if .truncated then "\nLinked issues are shortened. Open in Jira for the full relationships." else "" end);
def linked_issues: linked_projection | linked_text;

def app_value($id):
  field_raw($id)
  | (if $id == "issuelinks" then linked_issues
     elif type == "object" and .type == "doc" then rich_value else visible_value end)
  | field_clean | clean;

# One bounded, privacy-filtered representation for every native search row.
def picker_value($id): app_value($id) | .[0:4096];
