# Native text projection. No remote images, executable markup, link targets,
# account IDs, or unknown ADF attributes are handed to the panel.
include "fields";
def clean:
  if type == "string" then
    gsub("\r\n|\r"; "\n") | gsub("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"; "")
  else "" end;
def visible_value:
  if type == "array" then map(visible_value | select(length > 0)) | join(", ")
  elif type == "object" then (.displayName // .name // .value // .key // "") | text_value
  else text_value end;
def app_value($id):
  field_raw($id)
  | (if type == "object" and .type == "doc" then rich_value else visible_value end)
  | field_clean | clean;
def known_body_type:
  . as $type | ["text", "hardBreak", "mention", "emoji", "media", "mediaInline",
    "inlineCard", "blockCard", "embedCard", "rule", "orderedList", "doc", "paragraph",
    "heading", "codeBlock", "blockquote", "bulletList", "listItem", "table", "tableRow",
    "tableCell", "tableHeader", "mediaSingle", "mediaGroup", "panel", "expand", "nestedExpand",
    "taskList", "taskItem", "decisionList", "decisionItem", "status"] | index($type) != null;
def unsupported_body:
  if type == "array" then any(.[]; unsupported_body)
  elif type != "object" then false
  elif (.type | known_body_type | not) then true
  else (if (.content | type) == "array" then any(.content[]; unsupported_body) else false end) end;
def contents: if type == "object" and (.content | type) == "array" then .content else [] end;
def body:
  if type == "string" then clean
  elif type == "array" then map(body) | join("")
  elif type != "object" then ""
  elif .type == "text" then .text | clean
  elif .type == "hardBreak" then "\n"
  elif .type == "mention" then (.attrs.text // "@mention") | clean
  elif .type == "emoji" then (.attrs.text // .attrs.shortName // "") | clean
  elif .type == "status" then (.attrs.text // "") | clean
  elif .type == "media" or .type == "mediaInline" then "[Attachment]"
  elif .type == "inlineCard" or .type == "blockCard" or .type == "embedCard" then "[Linked content]"
  elif .type == "rule" then "────────\n\n"
  elif .type == "orderedList" then
    # Ignore arbitrary attributes, including misleading list start values.
    (if (.content | type) == "array" then .content else [] end)
    | to_entries | map(((.key + 1) | tostring) + ". " +
        (.value | body | sub("^• "; "") | sub("\n+$"; "")) + "\n") | join("") + "\n"
  elif .type == "panel" or .type == "expand" or .type == "nestedExpand" then
    (if .type == "panel" then
      ({info:"Info", note:"Note", warning:"Warning", success:"Success", error:"Error"}[.attrs.panelType // "note"] // "Note")
     else (.attrs.title // "") | clean end) as $title
    | (if (.content | type) == "array" then .content | map(body) | join("") else "" end) as $text
    | (if $title != "" then $title + "\n" else "" end) + $text + "\n\n"
  elif .type == "table" then
    contents as $rows
    | ($rows | map(contents)) as $cells
    | ($cells | any(.[][]; (.attrs.colspan // 1) != 1 or (.attrs.rowspan // 1) != 1)) as $merged
    | if ($cells | length) > 1 and ($cells[0] | length) > 0 and ($cells[0] | all(.[]; .type == "tableHeader")) and ($merged | not) then
        # Repeat the column name beside each value so wrapping or scrolling a
        # narrow reader cannot separate a value from its meaning.
        ($cells[0] | map(contents | map(body) | join("") | gsub("\n+"; " ") | sub(" +$"; ""))) as $labels
        | $cells[1:] | map(. as $row
            | ([($labels | length), ($row | length)] | max) as $width
            | [range(0; $width) | . as $i
                | (if ($labels[$i] // "") != "" then $labels[$i] else "Column " + (($i + 1) | tostring) end)
                  + ": " + (if $row[$i] then
                    ($row[$i] | contents | map(body) | join("") | gsub("\n+"; " ") | sub(" +$"; "") | if . == "" then "—" else . end)
                    else "—" end)] | join("\n")) | join("\n\n") + "\n\n"
      else
        (if $merged then "[Table has merged cells. Open in Jira for column relationships.]\n" else "" end)
        + ($rows | map(body) | join("")) + "\n\n"
      end
  elif .type == "doc" or .type == "paragraph" or .type == "heading" or
       .type == "codeBlock" or .type == "blockquote" or .type == "bulletList" or
       .type == "listItem" or .type == "tableRow" or
       .type == "tableCell" or .type == "tableHeader" or .type == "mediaSingle" or .type == "mediaGroup" or
       .type == "taskList" or .type == "taskItem" or .type == "decisionList" or .type == "decisionItem" then
    (if (.content | type) == "array" then .content else [] end | map(body) | join("")) as $text
    | if .type == "listItem" then "• " + ($text | sub("\n+$"; "")) + "\n"
      elif .type == "taskItem" then (if .attrs.state == "DONE" then "[x] " else "[ ] " end) + ($text | sub("\n+$"; "")) + "\n"
      elif .type == "decisionItem" then "Decision: " + ($text | sub("\n+$"; "")) + "\n"
      elif .type == "heading" then ($text | sub("\n+$"; "")) + "\n────────\n\n"
      elif .type == "codeBlock" then ($text | sub("\n+$"; "") | split("\n") | map("    " + .) | join("\n")) + "\n\n"
      elif .type == "blockquote" then ($text | sub("\n+$"; "") | split("\n") | map("│ " + .) | join("\n")) + "\n\n"
      elif .type == "tableRow" then ($text | sub("  │  $"; "")) + "\n"
      elif .type == "tableCell" or .type == "tableHeader" then ($text | gsub("\n+"; " ") | sub(" +$"; "")) + "  │  "
      elif .type == "paragraph" or .type == "bulletList" then $text + "\n\n"
      else $text end
  else "[Unsupported content]\n\n"
  end;
def reader_value($id):
  field_raw($id) | if type == "object" and .type == "doc" then body else visible_value | clean end;
. as $issue
| ($fields | split(",")) as $selected
| (if $selected | index("description") then field_raw("description") | body else "" end) as $description
| (if $selected | index("description") then field_raw("description") | unsupported_body else false end) as $unsupportedDescription
| (if $selected | index("comments") then
    field_raw("comments") | if type == "array" then . elif type == "object" and (.comments | type) == "array" then .comments else [] end
    else [] end | map(select(type == "object"))) as $comments
| (if $selected | index("comments") then
    field_raw("comments") | if type == "object" and (.total | type) == "number" then .total else 0 end
    else 0 end) as $reportedTotal
| ($comments[0:100] | map({
    author: (.author | (if type == "object" then .displayName else . end) // "Unknown author" | clean | .[0:256]),
    created: (.created // "" | clean | .[0:128]), body: (.body | body)
  })) as $projectedComments
| (reduce $projectedComments[] as $comment ({remaining:1000000, items:[], shortened:false};
    ([($comment.body | length), 20000, .remaining] | min) as $size
    | .shortened = (.shortened or ($comment.body | length) > $size)
    | .remaining -= $size
    | .items += [$comment + {body:$comment.body[0:$size]}])) as $boundedComments
| {
    key: .key,
    summary: (app_value("summary") | .[0:4096]),
    status: (app_value("status") | .[0:4096]),
    values: [($picker_fields | split(","))[] | . as $id | $issue | app_value($id) | .[0:4096]],
    metadata: [$selected[] | select(. != "key" and . != "summary" and . != "description" and . != "comments" and . != "link") | . as $id
      | ($issue | reader_value($id)) as $value
      | {id:$id, label: (field_label($id; $labels) | clean | .[0:256]), value: $value[0:20000],
         truncated: (($value | length) > 20000),
         unsupportedContent: ($issue | field_raw($id) | if type == "object" and .type == "doc" then unsupported_body else false end)}],
    description: $description[0:100000],
    commentsDeferred: (($selected | index("comments")) != null and ._peek_comments_deferred == true),
    commentsTotal: ([($comments | length), $reportedTotal] | max),
    unsupportedContent: ($unsupportedDescription or any($comments[0:100][]; .body | unsupported_body)),
    truncated: (($description | length) > 100000 or ($comments | length) > 100 or
      $reportedTotal > ($comments | length) or $boundedComments.shortened or
      any(("summary", "status", ($picker_fields | split(",")[]))
        | select(. != "description" and . != "comments" and . != "link");
        . as $id | $issue | app_value($id) | length > 4096) or
      any($selected[] | select(. != "description" and . != "comments" and . != "link");
        . as $id | $issue | reader_value($id) | length > 20000)),
    comments: $boundedComments.items
  }
