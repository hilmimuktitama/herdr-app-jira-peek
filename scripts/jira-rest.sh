#!/bin/sh
# Direct Jira Cloud REST transport, shared by runtime and doctor.
# shellcheck disable=SC2034,SC2329 # Sourced functions expose caller variables.

REST_CURL=${CURL_BIN_PATH:-curl}
rest_origin() {
  if [ -n "${JIRA_CLOUD_ID:-}" ]; then
    printf 'https://api.atlassian.com/ex/jira/%s' "$JIRA_CLOUD_ID"
  else
    printf '%s' "$JIRA_BASE"
  fi
}

rest_validate_netrc() {
  case "${JIRA_NETRC_FILE:-}" in /*) ;; *) return 2 ;; esac
  [ -f "$JIRA_NETRC_FILE" ] && [ -r "$JIRA_NETRC_FILE" ] && [ ! -L "$JIRA_NETRC_FILE" ] || return 2
  # Discard failed GNU/BSD stat output instead of concatenating it with the
  # fallback result (GNU stat -f can emit filesystem information on failure).
  if rest_mode=$(stat -c '%a' "$JIRA_NETRC_FILE" 2>/dev/null); then :
  else rest_mode=$(stat -f '%Lp' "$JIRA_NETRC_FILE" 2>/dev/null) || return 2
  fi
  case "$rest_mode" in 400|600) ;; *) return 2 ;; esac
}
rest_validate_auth() {
  command -v "$REST_CURL" >/dev/null 2>&1 || return 127
  rest_validate_netrc
}

# REST request: $1 URL, $2 output body, $3 output status, $4 output stderr.
rest_get() {
  rest_url=$1; rest_out_body=$2; rest_out_status=$3; rest_out_stderr=$4
  "$REST_CURL" -q -sS --connect-timeout 5 --max-time 30 --proto '=https' --proto-redir '=https' --max-redirs 0 \
    --netrc-file "$JIRA_NETRC_FILE" -H 'Accept: application/json' \
    -o "$rest_out_body" -w '%{http_code}' "$rest_url" >"$rest_out_status" 2>"$rest_out_stderr"
}
rest_post() {
  rest_url=$1; rest_payload=$2; rest_out_body=$3; rest_out_status=$4; rest_out_stderr=$5
  "$REST_CURL" -q -sS --connect-timeout 5 --max-time 30 --proto '=https' --proto-redir '=https' --max-redirs 0 \
    --netrc-file "$JIRA_NETRC_FILE" -H 'Accept: application/json' -H 'Content-Type: application/json' \
    --data-binary "@$rest_payload" -o "$rest_out_body" -w '%{http_code}' "$rest_url" >"$rest_out_status" 2>"$rest_out_stderr"
}
rest_http_failure() {
  rest_code=$(sed -n '1p' "$1" 2>/dev/null || true)
  case "$rest_code" in 401) return 10;; 403) return 13;; 404) return 11;; 429) return 12;; 400|4*|5*) return 1;; *) return 1;; esac
}

rest_fetch_issue() {
  rest_key=$1; rest_dir=$2
  rest_validate_auth || return $?
  mkdir -p "$rest_dir" || return 1
  rest_body="$rest_dir/body"; rest_status="$rest_dir/status"; rest_stderr="$rest_dir/stderr"
  rest_get "$(rest_origin)/rest/api/3/issue/$rest_key?fields=$DETAIL_FIELDS" "$rest_body" "$rest_status" "$rest_stderr" || return 1
  rest_code=$(sed -n '1p' "$rest_status")
  [ "$rest_code" = 200 ] || { rest_http_failure "$rest_status"; return $?; }
  jq -s -e --arg key "$rest_key" 'length == 1 and (.[0] | type) == "object" and .[0].key == $key and (.[0].fields | type) == "object"' "$rest_body" >/dev/null 2>&1 || return 20
  # The native reader returns core context immediately. Comments use the
  # separate bounded request in rest_fetch_comments, so they cannot delay or
  # discard this body.
  jq -c --argjson comments "$FETCH_COMMENTS" '.fields + {key:.key,fields:.fields,comments:[],_peek_comments_deferred:($comments == 1)}' "$rest_body"
}

# Native comments are optional and cost at most one request. Newest first gives
# a useful recent discussion even when a long-running issue has many pages.
rest_fetch_comments() {
  rest_key=$1; rest_dir=$2
  rest_validate_auth || return $?
  mkdir -p "$rest_dir" || return 1
  rest_body="$rest_dir/body"; rest_status="$rest_dir/status"; rest_stderr="$rest_dir/stderr"
  rest_get "$(rest_origin)/rest/api/3/issue/$rest_key/comment?startAt=0&maxResults=100&orderBy=-created" "$rest_body" "$rest_status" "$rest_stderr" || return 1
  rest_code=$(sed -n '1p' "$rest_status")
  [ "$rest_code" = 200 ] || { rest_http_failure "$rest_status"; return $?; }
  jq -s -e 'length == 1 and (.[0] | type) == "object" and
    (.[0] | (.comments | type) == "array" and (.comments | length) <= 100 and
      all(.comments[]; type == "object") and .startAt == 0 and
      (.total | type) == "number" and .total >= (.comments | length) and .total == (.total | floor) and
      ((.comments | length) > 0 or .total == 0))' "$rest_body" >/dev/null 2>&1 || return 20
  jq -c --arg key "$rest_key" '{key:$key,comments:{total:.total,comments:.comments}}' "$rest_body"
}
