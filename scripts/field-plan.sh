# Derive API requests from validated presentation preferences. Sourced only.
# shellcheck disable=SC2034 # Callers consume the derived request values.
# `PREVIEW_FIELDS` is accepted for imported configurations but no longer adds
# requested fields: the native reader projects only PICKER_FIELDS and
# READER_FIELDS. A stable sorted union lets ordering and labels reuse raw data.
DETAIL_FIELDS=$(printf '%s\n' "summary,$PICKER_FIELDS,$READER_FIELDS" \
  | tr ',' '\n' | LC_ALL=C sort -u | awk 'NF && $0 != "link" && $0 != "comments" { if (n++) printf ","; printf "%s", $0 }')
FETCH_COMMENTS=0
case ",$READER_FIELDS," in *,comments,*) FETCH_COMMENTS=1 ;; esac
FIELD_REQUEST_SIGNATURE="v1:$DETAIL_FIELDS:comments=$FETCH_COMMENTS"
# The batch projection keeps summary, status and PICKER_FIELDS values. Do not
# request assignee/updated unless the picker actually configures them.
METADATA_FIELDS=$(printf '%s\n' "summary,$PICKER_FIELDS" | tr ',' '\n' \
  | awk 'NF && !seen[$0]++ { if (n++) printf ","; printf "%s", $0 }')
