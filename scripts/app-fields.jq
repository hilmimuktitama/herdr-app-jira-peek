# Shared native-only text and picker projection.
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

# One bounded, privacy-filtered representation for every native search row.
def picker_value($id): app_value($id) | .[0:4096];
