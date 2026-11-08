# Native batch projection shares the issue reader's privacy and picker bounds.
# Only requested keys survive; successful omissions remain omitted.
include "fields";
def docs:
  if length != 1 then []
  elif $backend == "rest" then
    if (.[0] | type) == "object" and (.[0].issues | type) == "array" then
      [.[0].issues[] | select(type == "object" and (.fields | type) == "object")]
    else [] end
  elif (.[0] | type) == "array" then .[0]
  elif (.[0] | type) != "object" then []
  elif (.[0].data | type) == "array" then .[0].data
  elif (.[0].data | type) == "object" and (.[0].data.items | type) == "array" then
    [.[0].data.items[] | select(type == "object" and .ok == true and (.data | type) == "object") | .data]
  elif (.[0].data | type) == "object" then [.[0].data]
  else [.[0]] end;
docs as $issues
| [$keys | split("\n")[] | select(length > 0) | . as $key
   | first($issues[] | select(type == "object" and .key == $key)) as $issue
   | $issue | {key, summary: picker_value("summary"), status: picker_value("status"),
       values: [($fields | split(","))[] | select(length > 0) | . as $id | $issue | picker_value($id)]}]
