#!/bin/sh
# JSON-only adapter for the native Herdr app. No Herdr TUI control commands.
# shellcheck disable=SC2329 # Cleanup is invoked by traps.
set -eu
umask 077
DIR=$(CDPATH='' cd "$(dirname "$0")" && pwd)
export DIR

bridge() (
  operation=${1:-}; CONFIG_DIR=${2:-}; STATE=${3:-}
  case "$operation" in config|stamp|issue|comments|metadata|clear) ;; *) exit 14 ;; esac
  case "$CONFIG_DIR:$STATE" in /*:/*) ;; *) exit 14 ;; esac
  [ "$CONFIG_DIR" != / ] && [ "$STATE" != / ] || exit 14
  [ ! -L "$CONFIG_DIR" ] && [ ! -L "$STATE" ] || exit 14
  [ -f "$CONFIG_DIR/config.sh" ] && [ ! -L "$CONFIG_DIR/config.sh" ] || exit 10
  HERDR_PLUGIN_CONFIG_DIR=$CONFIG_DIR; HERDR_PLUGIN_STATE_DIR=$STATE
  LC_ALL=C
  export HERDR_PLUGIN_CONFIG_DIR HERDR_PLUGIN_STATE_DIR LC_ALL
  unset VIEWER_CONFIG_DIGEST VIEWER_CONNECTION_ID VIEWER_CONNECTION_EPOCH HERDR_VIEWER_SOURCE_TERMINAL
  unset HERDR_SOCKET_PATH HERDR_PLUGIN_CONTEXT_JSON
  for dependency in jq awk sed mktemp stat; do
    command -v "$dependency" >/dev/null 2>&1 || exit 11
  done
  if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then exit 11; fi
  # Copies using different configuration folders must not replace each other's
  # connection epoch or issue cache. Filesystem identity also joins case aliases
  # on case-insensitive volumes without merging distinct case-sensitive folders.
  # Keep the former shared state untouched; never attribute its cache to a new
  # connection without knowing which configuration created it.
  CONFIG_DIR=$(CDPATH='' cd -P "$CONFIG_DIR" && printf '%s/' "$PWD") || exit 10
  CONFIG_DIR=${CONFIG_DIR%/}
  # shellcheck source=scripts/connection.sh
  . "$DIR/connection.sh"
  if directory_identity=$(stat -Lc '%d:%i' "$CONFIG_DIR" 2>/dev/null); then :
  else directory_identity=$(stat -Lf '%d:%i' "$CONFIG_DIR" 2>/dev/null) || exit 10
  fi
  case "$directory_identity" in ''|*[!0-9:]*|:*|*:|*:*:*) exit 10 ;; esac
  case "$directory_identity" in *:*) ;; *) exit 10 ;; esac
  namespace=$(printf '%s' "directory-v1:$directory_identity" | connection_hash) || exit 12
  state_root=$STATE
  [ ! -L "$STATE/connections" ] || exit 14
  STATE=$STATE/connections/$namespace
  [ ! -L "$STATE" ] || exit 14
  HERDR_PLUGIN_CONFIG_DIR=$CONFIG_DIR; HERDR_PLUGIN_STATE_DIR=$STATE
  export HERDR_PLUGIN_CONFIG_DIR HERDR_PLUGIN_STATE_DIR
  if [ "$operation" = stamp ]; then
    # This path is local-only: no authentication initialization or Jira request.
    digest=$(connection_config_hash) || exit 12
    connection_read_marker || exit 12
    jq -n --arg context "$digest:$connection_saved_epoch" '{ok:true,context:$context}'
    exit
  fi
  if [ "$operation" = clear ]; then
    [ -n "${4:-}" ] && [ "$#" -eq 4 ] || exit 14
    # Do not initialize common.sh here: initialization can purge cache or
    # replace an epoch before a stale caller has been rejected.
    CACHE=$STATE/cache
    [ -d "$STATE" ] && [ ! -L "$CACHE" ] || exit 13
    [ ! -e "$CACHE" ] || [ -d "$CACHE" ] || exit 13
    connection_lock || exit 13
    trap 'connection_unlock' 0
    trap 'exit 1' 1 2 15
    digest=$(connection_config_hash) || exit 12
    connection_read_marker || exit 12
    [ -n "$connection_saved_id" ] && [ -n "$connection_saved_epoch" ] || exit 12
    [ "$4" = "$digest:$connection_saved_epoch" ] || exit 12
    CONNECTION_ID=$connection_saved_id
    CONNECTION_CONFIG_DIGEST=$digest
    connection_new_epoch || exit 13
    connection_remove_cache || exit 13
    connection_marker_current && [ "$(connection_config_hash)" = "$digest" ] || exit 12
    printf '%s\n' '{"ok":true}'
    exit
  fi
  # Read only the declarative backend selector, never source configuration.
  # common.sh still validates the complete file before using any setting.
  backend=$(awk '
    BEGIN { backend="twg" }
    { line=$0; sub(/^[[:space:]]*/, "", line) }
    line ~ /^JIRA_BACKEND=/ {
      sub(/^JIRA_BACKEND=/, "", line); gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      gsub(/^[\047\042]|[\047\042]$/, "", line); backend=line
    }
    END { print backend }
  ' "$CONFIG_DIR/config.sh")
  case "$backend" in
    twg) command -v "${TWG_BIN_PATH:-twg}" >/dev/null 2>&1 || exit 11 ;;
    rest) command -v "${CURL_BIN_PATH:-curl}" >/dev/null 2>&1 || exit 11 ;;
  esac
  # Preserve common.sh's private-state guarantee for both new parent levels.
  # Stamp and stale Clear remain read-only and never create these directories.
  for parent in "$state_root" "$state_root/connections"; do
    [ ! -L "$parent" ] || exit 14
    [ ! -e "$parent" ] || [ -d "$parent" ] || exit 13
    mkdir -p "$parent" && chmod 700 "$parent" || exit 13
  done
  # shellcheck source=scripts/common.sh
  . "$DIR/common.sh"
  # The optional reader selection changes only this read, never private config.
  # Reuse the existing field validator and request signature for cache isolation.
  if { [ "$operation" = issue ] && [ "$#" -eq 7 ]; } || { [ "$operation" = comments ] && [ "$#" -eq 6 ]; }; then
    if [ "$operation" = issue ]; then READER_FIELDS=$7; else READER_FIELDS=$6; fi
    [ "${#READER_FIELDS}" -le 2048 ] && preferences_validate_field_list reader "$READER_FIELDS" || exit 14
    # shellcheck source=scripts/field-plan.sh
    . "$DIR/field-plan.sh"
  fi
  PEEK_NATIVE_READER=1
  if [ "$JIRA_BACKEND" = rest ]; then
    # Never reuse a legacy all-comments cache as a deferred native response.
    FIELD_REQUEST_SIGNATURE="$FIELD_REQUEST_SIGNATURE:native-v2"
    LEGACY_FIELD_REQUEST=0
  fi
  context="$CONNECTION_CONFIG_DIGEST:$CONNECTION_EPOCH"
  if [ "$operation" = config ]; then
    jq -n --arg context "$context" --arg base "$JIRA_BASE" --arg projects "$JIRA_PROJECTS" \
      --arg backend "$JIRA_BACKEND" --argjson interval "$AUTO_REFRESH_SEC" \
      --argjson limit "$MAX_CANDIDATES" --argjson ttl "$CACHE_TTL_MIN" \
      --arg fields "summary,$READER_FIELDS" --arg labels "$FIELD_LABELS" -L "$DIR" \
      'include "fields"; {ok:true,context:$context,base:$base,projects:($projects|split("|")),backend:$backend,interval:$interval,limit:$limit,ttl:$ttl,
        fields:[$fields|split(",")[]|select(. != "" and . != "link")|{id:.,label:field_label(.;$labels)}]}'
    exit
  fi
  [ "${4:-}" = "$context" ] || exit 12
  shift 4
  f=; keys=; raw=; stderr=; projection=
  cleanup() {
    [ -z "$f" ] || fetch_cleanup "$f"
    [ -z "$keys" ] || rm -f "$keys"
    [ -z "$projection" ] || rm -f "$projection"
    fetch_work_cleanup
  }
  trap cleanup 0
  trap 'exit 1' 1 2 15
  if [ "$operation" = comments ]; then
    { [ "$#" -eq 1 ] || [ "$#" -eq 2 ]; } && [ "$JIRA_BACKEND" = rest ] || exit 14
    requested=$1
    validate_key "$requested" || exit 14
    case ",$READER_FIELDS," in *,comments,*) ;; *) exit 14 ;; esac
    rest_dir=$(mktemp -d "$STATE/.rest-fetch.$$.XXXXXX") || exit 13
    raw=$(mktemp "$STATE/.twg-json.$$.XXXXXX") || exit 13
    comment_result=0
    rest_fetch_comments "$requested" "$rest_dir" > "$raw" || comment_result=$?
    connection_assert_current --identity || exit 12
    case "$comment_result" in
      0) ;;
      10) connection_revoke || true; exit 12 ;;
      13) exit 15 ;;
      *) exit 13 ;;
    esac
    projection=$(mktemp "$STATE/.issue-app-projection.$$.XXXXXX") || exit 13
    jq -c -L "$DIR" --arg fields comments --arg picker_fields '' --arg labels '' \
      -f "$DIR/app-issue.jq" "$raw" > "$projection" || exit 13
    [ "$(wc -c < "$projection")" -le 7340032 ] || exit 13
    connection_assert_current || exit 12
    jq -c --arg context "$context" '{ok:true,context:$context,comments:{key,comments,commentsTotal,truncated,unsupportedContent}}' "$projection"
    exit
  fi
  if [ "$operation" = issue ]; then
    [ "$#" -ge 1 ] && [ "$#" -le 3 ] || exit 14
    requested=${1:-}
    validate_key "$requested" || exit 14
    case "${2:-}" in refresh) clear_cache "$requested" || exit 13 ;; '') ;; *) exit 14 ;; esac
    if ! fetch "$requested" >/dev/null; then
      connection_assert_current || exit 12
      [ "$(fetch_error_detail "$requested")" != "$FETCH_ERROR_REST_PERMISSION" ] || exit 15
      exit 13
    fi
    f=$FETCHED_FILE
    # The same lock guards canonical renames and clear. Timestamp and content
    # must describe the same file, including the transient TTL=0 payload.
    connection_lock || exit 13
    connection_assert_current || exit 12
    [ -f "$f" ] && [ ! -L "$f" ] || exit 13
    if modified=$(stat -c '%Y %y' "$f" 2>/dev/null); then
      fetched_at=$(printf '%s\n' "$modified" | awk '{ split($3, a, "."); printf "%.0f", $1 * 1000 + substr(a[2] "000", 1, 3) }')
    else
      modified=$(stat -f '%.9Fm' "$f" 2>/dev/null) || exit 13
      fetched_at=$(printf '%s\n' "$modified" | awk '{ split($0, a, "."); printf "%.0f", a[1] * 1000 + substr(a[2] "000", 1, 3) }')
    fi
    case "$fetched_at" in ''|*[!0-9]*) exit 13 ;; esac
    projection=$(mktemp "$STATE/.issue-app-projection.$$.XXXXXX") || exit 13
    jq -c -L "$DIR" --arg fields "$READER_FIELDS" --arg picker_fields "$PICKER_FIELDS" \
      --arg labels "$FIELD_LABELS" -f "$DIR/app-issue.jq" "$f" > "$projection" || exit 13
    # Leave room for the envelope under Herdr exec's 8 MiB output limit.
    [ "$(wc -c < "$projection")" -le 7340032 ] || exit 13
    connection_assert_current || exit 12
    jq -c --arg context "$context" --argjson fetchedAt "$fetched_at" \
      '{ok:true,context:$context,issue:(. + {fetchedAt:$fetchedAt})}' "$projection"
  else
    [ "$#" -gt 0 ] && [ "$#" -le "$MAX_CANDIDATES" ] || exit 14
    keys=$(mktemp "$STATE/.issue-app-keys.$$.XXXXXX")
    for requested in "$@"; do validate_key "$requested" || exit 14; printf '%s\n' "$requested" >> "$keys"; done
    raw=$(mktemp "$STATE/.twg-json.$$.XXXXXX")
    stderr=$(mktemp "$STATE/.twg-stderr.$$.XXXXXX")
    metadata_result=0
    run_metadata_batch "$keys" "$raw" "$stderr" || metadata_result=$?
    if [ "$metadata_result" -ne 0 ]; then
      connection_assert_current || exit 12
      [ "$JIRA_BACKEND:$metadata_result" != rest:13 ] || exit 15
      exit 13
    fi
    projection=$(mktemp "$STATE/.issue-app-projection.$$.XXXXXX") || exit 13
    jq -cs -L "$DIR" --arg backend "$JIRA_BACKEND" --arg fields "$PICKER_FIELDS" \
      --rawfile keys "$keys" -f "$DIR/app-metadata.jq" "$raw" > "$projection" || exit 13
    # File-based output avoids argv limits even for valid large batches.
    [ "$(wc -c < "$projection")" -le 7340032 ] || exit 13
    connection_assert_current || exit 12
    jq -c --arg context "$context" '{ok:true,context:$context,rows:.}' "$projection"
  fi
)

# Never expose transport stdout/stderr, tenant settings, or authentication data
# in errors. Success contains only the intentionally projected panel fields.
if payload=$(bridge "$@" 2>/dev/null); then
  printf '%s\n' "$payload"
else
  status=$?
  case "$status" in
    10) printf '%s\n' '{"ok":false,"error":"configuration_missing"}' ;;
    11) printf '%s\n' '{"ok":false,"error":"dependencies_missing"}' ;;
    12) printf '%s\n' '{"ok":false,"error":"connection_changed"}' ;;
    13) printf '%s\n' '{"ok":false,"error":"request_failed"}' ;;
    14) printf '%s\n' '{"ok":false,"error":"invalid_request"}' ;;
    15) printf '%s\n' '{"ok":false,"error":"permission_denied"}' ;;
    *) printf '%s\n' '{"ok":false,"error":"connection_failed"}' ;;
  esac
fi
