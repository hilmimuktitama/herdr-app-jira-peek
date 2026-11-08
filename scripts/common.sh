# Native data runtime: declarative configuration, connection identity and cached reads.
# Sourcing initializes private data state; terminal/viewer lifecycle belongs to the host.
# shellcheck disable=SC2329,SC2034 # Cleanup is trap-indirect; sourced functions expose caller variables.
umask 077

TWG="${TWG_BIN_PATH:-twg}"
DIR=${DIR:-$(CDPATH='' cd "$(dirname "${0:-scripts/common.sh}")" 2>/dev/null && pwd)}
STATE="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}/herdr-jira-peek}"
CONFIG_DIR="${HERDR_PLUGIN_CONFIG_DIR:-$STATE}"
CACHE="$STATE/cache"
# shellcheck source=scripts/preferences.sh
. "$DIR/preferences.sh"

die() {
  printf 'jira-peek: %s\n' "$*" >&2
  exit 1
}

require_backend() {
  if [ "$JIRA_BACKEND" = rest ]; then
    command -v "${CURL_BIN_PATH:-curl}" >/dev/null 2>&1 || die 'curl is required for the REST backend; install curl and rerun the doctor action.'
    return 0
  fi
  command -v "$TWG" >/dev/null 2>&1 || die 'TWG CLI is required; run the setup action for dependency installation instructions, then complete twg setup yourself in a terminal.'
}

# Public defaults. Credentials live outside this plugin config.
JIRA_BASE=
JIRA_SITE=
JIRA_BACKEND=twg
JIRA_CLOUD_ID=
JIRA_NETRC_FILE=
JIRA_PROJECTS=
CACHE_TTL_MIN=10
MAX_CANDIDATES=20
PICKER_LAYOUT=bottom
AUTO_REFRESH_SEC=2
KEY_RE=
SOURCE_HIGHLIGHT=off
# Config is authoritative; inherited display preferences must not override it.
unset PICKER_FIELDS PREVIEW_FIELDS READER_FIELDS FIELD_LABELS TEXT_STYLE
preferences_defaults

# Config is a deliberately small declarative assignment file. Parse the
# public settings as data instead of executing config.sh as shell code.
decode_config_value() {
  # Keep parsing literal, without launching a process for every assignment.
  config_raw=${1:-}
  config_raw=${config_raw#"${config_raw%%[![:space:]]*}"}
  config_raw=${config_raw%"${config_raw##*[![:space:]]}"}
  case "$config_raw" in
    \'*\')
      config_value=${config_raw#\'}
      config_value=${config_value%\'}
      ;;
    \"*\")
      config_value=${config_raw#\"}
      config_value=${config_value%\"}
      ;;
    *\'*|*\"*) return 1 ;;
    *) config_value=$config_raw ;;
  esac
}

load_config() {
  config_file=$CONFIG_DIR/config.sh
  case "$CONFIG_DIR" in
    ''|/|.) die 'refusing unsafe plugin config directory path' ;;
  esac
  [ ! -L "$CONFIG_DIR" ] || die 'plugin config directory must not be a symlink'
  [ ! -L "$config_file" ] || die 'config.sh must not be a symlink'
  [ -f "$config_file" ] || return 0

  while IFS= read -r config_line || [ -n "$config_line" ]; do
    config_line=${config_line#"${config_line%%[![:space:]]*}"}
    case "$config_line" in
      ''|\#*) continue ;;
      JIRA_BASE=*)
        decode_config_value "${config_line#JIRA_BASE=}" || die 'invalid JIRA_BASE assignment in config.sh'
        JIRA_BASE=$config_value
        ;;
      JIRA_SITE=*)
        decode_config_value "${config_line#JIRA_SITE=}" || die 'invalid JIRA_SITE assignment in config.sh'
        JIRA_SITE=$config_value
        ;;
      JIRA_BACKEND=*)
        decode_config_value "${config_line#JIRA_BACKEND=}" || die 'invalid JIRA_BACKEND assignment in config.sh'
        JIRA_BACKEND=$config_value
        ;;
      JIRA_CLOUD_ID=*)
        decode_config_value "${config_line#JIRA_CLOUD_ID=}" || die 'invalid JIRA_CLOUD_ID assignment in config.sh'
        JIRA_CLOUD_ID=$config_value
        ;;
      JIRA_NETRC_FILE=*)
        decode_config_value "${config_line#JIRA_NETRC_FILE=}" || die 'invalid JIRA_NETRC_FILE assignment in config.sh'
        JIRA_NETRC_FILE=$config_value
        ;;
      JIRA_PROJECTS=*)
        decode_config_value "${config_line#JIRA_PROJECTS=}" || die 'invalid JIRA_PROJECTS assignment in config.sh'
        JIRA_PROJECTS=$config_value
        ;;
      CACHE_TTL_MIN=*)
        decode_config_value "${config_line#CACHE_TTL_MIN=}" || die 'invalid CACHE_TTL_MIN assignment in config.sh'
        CACHE_TTL_MIN=$config_value
        ;;
      MAX_CANDIDATES=*)
        decode_config_value "${config_line#MAX_CANDIDATES=}" || die 'invalid MAX_CANDIDATES assignment in config.sh'
        MAX_CANDIDATES=$config_value
        ;;
      PICKER_LAYOUT=*)
        decode_config_value "${config_line#PICKER_LAYOUT=}" || die 'invalid PICKER_LAYOUT assignment in config.sh'
        PICKER_LAYOUT=$config_value
        ;;
      AUTO_REFRESH_SEC=*)
        decode_config_value "${config_line#AUTO_REFRESH_SEC=}" || die 'invalid AUTO_REFRESH_SEC assignment in config.sh'
        AUTO_REFRESH_SEC=$config_value
        ;;
      SOURCE_HIGHLIGHT=*)
        decode_config_value "${config_line#SOURCE_HIGHLIGHT=}" || die 'invalid SOURCE_HIGHLIGHT assignment in config.sh'
        SOURCE_HIGHLIGHT=$config_value
        ;;
      KEY_RE=*)
        decode_config_value "${config_line#KEY_RE=}" || die 'invalid KEY_RE assignment in config.sh'
        KEY_RE=$config_value
        ;;
      PICKER_FIELDS=*)
        decode_config_value "${config_line#PICKER_FIELDS=}" || die 'invalid PICKER_FIELDS assignment in config.sh'
        PICKER_FIELDS=$config_value
        ;;
      PREVIEW_FIELDS=*)
        decode_config_value "${config_line#PREVIEW_FIELDS=}" || die 'invalid PREVIEW_FIELDS assignment in config.sh'
        PREVIEW_FIELDS=$config_value
        ;;
      READER_FIELDS=*)
        decode_config_value "${config_line#READER_FIELDS=}" || die 'invalid READER_FIELDS assignment in config.sh'
        READER_FIELDS=$config_value
        ;;
      FIELD_LABELS=*)
        decode_config_value "${config_line#FIELD_LABELS=}" || die 'invalid FIELD_LABELS assignment in config.sh'
        FIELD_LABELS=$config_value
        ;;
      COLOR_THEME=*)
        decode_config_value "${config_line#COLOR_THEME=}" || die 'invalid COLOR_THEME assignment in config.sh'
        case "$config_value" in
          terminal|ocean|warm|mono) : ;;
          *) die 'COLOR_THEME is no longer supported; remove it from config.sh' ;;
        esac
        ;;
      TEXT_STYLE=*)
        decode_config_value "${config_line#TEXT_STYLE=}" || die 'invalid TEXT_STYLE assignment in config.sh'
        TEXT_STYLE=$config_value
        ;;
      *) die 'config.sh may contain only Peek for Jira setting assignments' ;;
    esac
  done < "$config_file"
}

# shellcheck source=scripts/connection.sh
. "$DIR/connection.sh"
CONNECTION_CONFIG_DIGEST=$(connection_config_hash) || die 'could not fingerprint config; SHA-256 tooling is required'
[ -z "${VIEWER_CONFIG_DIGEST:-}" ] || [ "$VIEWER_CONFIG_DIGEST" = "$CONNECTION_CONFIG_DIGEST" ] \
  || die 'Configuration changed; close and reopen Peek.'
load_config
[ "$(connection_config_hash)" = "$CONNECTION_CONFIG_DIGEST" ] || die 'configuration changed while loading; retry'

JIRA_BASE=${JIRA_BASE:-}
while [ "${JIRA_BASE%/}" != "$JIRA_BASE" ]; do
  JIRA_BASE=${JIRA_BASE%/}
done

[ -n "${JIRA_BASE:-}" ] || die 'JIRA_BASE is required in config.sh'
case "$JIRA_BASE" in
  *[[:space:]]*) die 'JIRA_BASE must not contain whitespace' ;;
esac
printf '%s\n' "$JIRA_BASE" | grep -Eq '^https://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]+)?$' \
  || die 'JIRA_BASE must be a bare HTTPS origin without credentials, path, query, or fragment'

case "$JIRA_BACKEND" in twg|rest) ;; *) die 'JIRA_BACKEND must be twg or rest' ;; esac
if [ "$JIRA_BACKEND" = twg ]; then
  [ -n "${JIRA_SITE:-}" ] || die 'JIRA_SITE is required in config.sh for the TWG backend'
  case "$JIRA_SITE" in *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-]*) die 'JIRA_SITE must be an Atlassian site prefix or bare cloud ID' ;; esac
else
  [ -n "${JIRA_NETRC_FILE:-}" ] || die 'JIRA_NETRC_FILE is required in config.sh for the REST backend'
  case "$JIRA_NETRC_FILE" in /*) ;; *) die 'JIRA_NETRC_FILE must be an absolute path' ;; esac
  [ ! -L "$JIRA_NETRC_FILE" ] || die 'JIRA_NETRC_FILE must not be a symlink'
  [ -f "$JIRA_NETRC_FILE" ] || die 'JIRA_NETRC_FILE must be a regular file'
  # shellcheck source=scripts/jira-rest.sh
  . "$DIR/jira-rest.sh"
  rest_validate_netrc || die 'JIRA_NETRC_FILE must be owner-readable and inaccessible to group/world (mode 400 or 600)'
  case "$JIRA_CLOUD_ID" in *[!A-Za-z0-9_-]*) die 'JIRA_CLOUD_ID contains unsafe characters' ;; esac
fi

[ -n "${JIRA_PROJECTS:-}" ] || die 'JIRA_PROJECTS must not be empty'
printf '%s\n' "$JIRA_PROJECTS" \
  | grep -Eq '^[A-Z][A-Z0-9_]*(\|[A-Z][A-Z0-9_]*)*$' \
  || die 'JIRA_PROJECTS must be an explicit allowlist such as ABC|DEF'
case "${CACHE_TTL_MIN:-}" in
  ''|*[!0-9]*) die 'CACHE_TTL_MIN must be a non-negative integer' ;;
esac
case "${MAX_CANDIDATES:-}" in
  ''|*[!0-9]*) die 'MAX_CANDIDATES must be a positive integer' ;;
esac
[ "$MAX_CANDIDATES" -gt 0 ] || die 'MAX_CANDIDATES must be greater than zero'
[ "$MAX_CANDIDATES" -le 100 ] || die 'MAX_CANDIDATES must not exceed 100'
case "$PICKER_LAYOUT" in
  top|bottom) ;;
  *) die 'PICKER_LAYOUT must be top or bottom' ;;
esac
case "$SOURCE_HIGHLIGHT" in
  off|auto) ;;
  *) die 'SOURCE_HIGHLIGHT must be off or auto' ;;
esac
printf '%s\n' "$AUTO_REFRESH_SEC" | grep -Eq '^(0|[1-9]|[1-5][0-9]|60)$' \
  || die 'AUTO_REFRESH_SEC must be a whole number from 0 to 60'
preferences_validate_all || die "$PREFERENCES_ERROR"
# shellcheck source=scripts/field-plan.sh
. "$DIR/field-plan.sh"
# Check configured regular expressions without making a non-match an error.
regex_status=0
printf '\n' | grep -Eq "^(${JIRA_PROJECTS})-[0-9]+$" >/dev/null 2>&1 \
  || regex_status=$?
[ "$regex_status" -ne 2 ] || die 'JIRA_PROJECTS is not a valid regular expression'

if [ -z "${KEY_RE:-}" ]; then
  KEY_RE="(${JIRA_PROJECTS})-[0-9]+"
fi
regex_status=0
printf '\n' | grep -oE "$KEY_RE" >/dev/null 2>&1 || regex_status=$?
[ "$regex_status" -ne 2 ] || die 'KEY_RE is not a valid regular expression'

ensure_private_dir() {
  private_dir=${1:-}
  private_label=${2:-directory}
  case "$private_dir" in
    ''|/|.) die "refusing unsafe $private_label path" ;;
  esac
  [ ! -L "$private_dir" ] || die "$private_label must not be a symlink"
  if [ -e "$private_dir" ] && [ ! -d "$private_dir" ]; then
    die "$private_label must be a directory"
  fi
  mkdir -p "$private_dir" || die "could not create $private_label"
  chmod 700 "$private_dir" || die "could not protect $private_label"
}

ensure_private_dir "$STATE" 'plugin state directory'
ensure_private_dir "$CACHE" 'issue cache directory'

# Fetch temporaries include their creating process ID. A later invocation may
# safely remove a direct regular file only when that owner process is gone;
# active concurrent fetches are left untouched. This also recovers from SIGKILL,
# where no shell trap can run.
cleanup_abandoned_temps() {
  for stale_temp in "$@"; do
    [ -f "$stale_temp" ] && [ ! -L "$stale_temp" ] || continue
    stale_name=${stale_temp##*/}
    stale_stem=${stale_name%.*}
    stale_owner=${stale_stem##*.}
    case "$stale_owner" in
      ''|0|*[!0-9]*) continue ;;
    esac
    if ! kill -0 "$stale_owner" 2>/dev/null; then
      rm -f "$stale_temp" || die 'could not remove an abandoned temporary file'
    fi
  done
}
cleanup_abandoned_temps \
  "$STATE"/.identity.*.* \
  "$STATE"/.twg-json.*.* \
  "$STATE"/.twg-stderr.*.* \
  "$STATE"/.twg-normalized.*.* \
  "$STATE"/.twg-error.*.* \
  "$STATE"/.issue-*.*.*

connection_cleanup_abandoned

for stale_rest_dir in "$STATE"/.rest-fetch.*.* "$STATE"/.rest-metadata.*.*; do
  [ -d "$stale_rest_dir" ] && [ ! -L "$stale_rest_dir" ] || continue
  stale_rest_owner=${stale_rest_dir%.*}; stale_rest_owner=${stale_rest_owner##*.}
  case "$stale_rest_owner" in ''|0|*[!0-9]*) continue ;; esac
  if ! kill -0 "$stale_rest_owner" 2>/dev/null; then
    rm -rf "$stale_rest_dir" || die 'could not remove abandoned REST request data'
  fi
done

# Purge on every invocation, not only when a particular key is requested. This
# also removes interrupted fetches and makes TTL=0 a true no-durable-cache mode.
purge_cache() {
  # Visit direct entries (including dotfiles), pruning every child directory.
  # One find replaces a process per cached ticket on every invocation. The
  # default no-follow behavior preserves symlinks and their targets.
  if [ "$CACHE_TTL_MIN" -eq 0 ]; then
    find "$CACHE/." ! -name . -prune -type f -exec rm -f {} +
  else
    find "$CACHE/." ! -name . -prune -type f ! -mmin -"$CACHE_TTL_MIN" -exec rm -f {} +
  fi || die 'could not purge issue cache files'
}
purge_cache

# Cache ordering is global to STATE, not to a Herdr session.  Network work never
# holds this lock; it protects only generation reads and the final rename.
CACHE_GENERATION_DIR="$STATE/cache-generations"
ensure_private_dir "$CACHE_GENERATION_DIR" 'cache generation directory'
cache_generation_path() { printf '%s/%s' "$CACHE_GENERATION_DIR" "$1"; }
cache_generation_read() {
  cache_generation_file=$(cache_generation_path "$1")
  [ ! -L "$cache_generation_file" ] || return 1
  if [ ! -e "$cache_generation_file" ]; then printf '0'; return 0; fi
  [ -f "$cache_generation_file" ] || return 1
  cache_generation_value=$(sed -n '1p' "$cache_generation_file" 2>/dev/null || true)
  case "$cache_generation_value" in ''|*[!0-9]*) return 1;; esac
  [ "$(printf '%s\n' "$cache_generation_value" | wc -c | tr -d ' ')" = "$(wc -c < "$cache_generation_file" | tr -d ' ')" ] || return 1
  printf '%s' "$cache_generation_value"
}
cache_generation_increment_locked() {
  cache_generation_key=$1
  cache_generation_file=$(cache_generation_path "$cache_generation_key")
  cache_generation_value=$(cache_generation_read "$cache_generation_key") || return 1
  cache_generation_value=$((cache_generation_value + 1))
  cache_generation_tmp=$(mktemp "$CACHE_GENERATION_DIR/.$cache_generation_key.XXXXXX") || {
    return 1
  }
  printf '%s\n' "$cache_generation_value" > "$cache_generation_tmp" \
    && mv "$cache_generation_tmp" "$cache_generation_file"
  cache_generation_status=$?
  rm -f "$cache_generation_tmp"
  return "$cache_generation_status"
}
cache_publish_lock() {
  cache_publish_key=$1
  cache_publish_lock_dir="$CACHE_GENERATION_DIR/.$cache_publish_key.lock"
  [ ! -L "$cache_publish_lock_dir" ] || return 1
  cache_publish_owner=$(mktemp "$CACHE_GENERATION_DIR/.owner.$$.XXXXXX") || return 1
  printf '%s\n' "$$" > "$cache_publish_owner" || { rm -f "$cache_publish_owner"; return 1; }
  cache_lock_wait=0
  while ! mkdir "$cache_publish_lock_dir" 2>/dev/null; do
    cache_lock_tokens="$cache_publish_lock_dir/.owner.*"
    cache_lock_token_count=0; cache_lock_token=
    for cache_lock_candidate in $cache_lock_tokens; do
      [ -f "$cache_lock_candidate" ] && [ ! -L "$cache_lock_candidate" ] || continue
      cache_lock_token_count=$((cache_lock_token_count + 1)); cache_lock_token=$cache_lock_candidate
    done
    if [ "$cache_lock_token_count" -eq 1 ]; then
      cache_lock_owner=${cache_lock_token##*/}; cache_lock_owner=${cache_lock_owner#.owner.}; cache_lock_owner=${cache_lock_owner%%.*}
      case "$cache_lock_owner" in ''|*[!0-9]*) ;; *)
        if ! kill -0 "$cache_lock_owner" 2>/dev/null; then
          rm "$cache_lock_token" && rmdir "$cache_publish_lock_dir" 2>/dev/null || true
        fi ;;
      esac
    fi
    # Recover a process killed between mkdir and owner publication. Only an
    # old, empty directory is removable; never steal a fresh or occupied lock.
    if [ -n "$(find "$cache_publish_lock_dir" -prune -type d -mmin +1 -print 2>/dev/null)" ]; then
      rmdir "$cache_publish_lock_dir" 2>/dev/null || true
    fi
    cache_lock_wait=$((cache_lock_wait + 1))
    [ "$cache_lock_wait" -lt 1000 ] || { rm -f "$cache_publish_owner"; return 1; }
    sleep 0.01
  done
  mv "$cache_publish_owner" "$cache_publish_lock_dir/" || { rm -f "$cache_publish_owner"; rmdir "$cache_publish_lock_dir"; return 1; }
  cache_publish_owner="$cache_publish_lock_dir/${cache_publish_owner##*/}"
  CACHE_PUBLISH_LOCK_HELD=1
}
cache_publish_unlock() {
  [ "${CACHE_PUBLISH_LOCK_HELD:-0}" -eq 1 ] || return 0
  [ -f "$cache_publish_owner" ] && [ ! -L "$cache_publish_owner" ] || return 1
  rm "$cache_publish_owner" && rmdir "$cache_publish_lock_dir" || return 1
  CACHE_PUBLISH_LOCK_HELD=0
}
cache_invalidate() {
  cache_invalidate_key=$1
  cache_publish_lock "$cache_invalidate_key" || return 1
  cache_generation_increment_locked "$cache_invalidate_key" || { cache_publish_unlock; return 1; }
  rm -f "$CACHE/$cache_invalidate_key.json" || { cache_publish_unlock; return 1; }
  cache_publish_unlock
}

# Fetch diagnostics are private, connection-scoped state. Each key has its own
# file, and writers use a same-directory temp file plus rename so concurrent
# fetches cannot expose a partial diagnostic.
FETCH_ERROR_DIR="$STATE/fetch-errors"
ensure_private_dir "$FETCH_ERROR_DIR" 'fetch diagnostic state directory'
cleanup_abandoned_temps "$FETCH_ERROR_DIR"/.fetch-error-*.*.*
FETCH_ERROR_GENERIC='TWG request failed'
FETCH_ERROR_TWG='TWG is not authenticated or configured; run twg setup, then retry'
FETCH_ERROR_JIRA='Jira request failed'
FETCH_ERROR_MISSING='TWG CLI unavailable; install the official Atlassian TWG CLI, ensure it is on PATH, then run twg setup'
if [ "$JIRA_BACKEND" = rest ]; then
  FETCH_ERROR_GENERIC='Jira request failed'
  FETCH_ERROR_MISSING='curl is unavailable; install curl and retry'
fi
FETCH_ERROR_REST_AUTH='Jira authentication failed (HTTP 401)'
FETCH_ERROR_REST_PERMISSION='Access to this Jira operation was denied (HTTP 403)'
FETCH_ERROR_REST_NOT_FOUND='Jira issue or endpoint was not found (HTTP 404)'
FETCH_ERROR_REST_RATE='Jira rate limit reached (HTTP 429)'
FETCH_ERROR_REST_INVALID='Jira response was not valid issue JSON'
for fetch_error_parent in "$STATE" "$STATE"/session-*; do
  [ -e "$fetch_error_parent" ] || continue
  [ -d "$fetch_error_parent" ] && [ ! -L "$fetch_error_parent" ] \
    || die 'refusing symlinked or invalid session state directory'
  fetch_error_dir="$fetch_error_parent/fetch-errors"
  [ -e "$fetch_error_dir" ] || continue
  [ -d "$fetch_error_dir" ] && [ ! -L "$fetch_error_dir" ] \
    || die 'refusing symlinked or invalid fetch diagnostic directory'
  for fetch_error_file in "$fetch_error_dir"/fetch-error-*; do
    [ -f "$fetch_error_file" ] && [ ! -L "$fetch_error_file" ] || continue
    fetch_error_value=$(sed -n '1p' "$fetch_error_file" 2>/dev/null || true)
    fetch_error_bytes=$(wc -c < "$fetch_error_file" | tr -d ' ')
    fetch_error_valid=1
    case "$fetch_error_value" in
      "$FETCH_ERROR_GENERIC") fetch_error_expected=$(printf '%s\n' "$FETCH_ERROR_GENERIC" | wc -c | tr -d ' ') ;;
      "$FETCH_ERROR_TWG") fetch_error_expected=$(printf '%s\n' "$FETCH_ERROR_TWG" | wc -c | tr -d ' ') ;;
      "$FETCH_ERROR_JIRA") fetch_error_expected=$(printf '%s\n' "$FETCH_ERROR_JIRA" | wc -c | tr -d ' ') ;;
      "$FETCH_ERROR_MISSING") fetch_error_expected=$(printf '%s\n' "$FETCH_ERROR_MISSING" | wc -c | tr -d ' ') ;;
      "$FETCH_ERROR_REST_AUTH"|"$FETCH_ERROR_REST_PERMISSION"|"$FETCH_ERROR_REST_NOT_FOUND"|"$FETCH_ERROR_REST_RATE"|"$FETCH_ERROR_REST_INVALID") fetch_error_expected=$(printf '%s\n' "$fetch_error_value" | wc -c | tr -d ' ') ;;
      *) fetch_error_valid=0 ;;
    esac
    [ "$fetch_error_bytes" = "${fetch_error_expected:-}" ] || fetch_error_valid=0
    if [ "$fetch_error_valid" -eq 1 ] \
      && ! LC_ALL=C printf '%s\n' "$fetch_error_value" | cmp -s - "$fetch_error_file"; then
      fetch_error_valid=0
    fi
    [ "$fetch_error_valid" -eq 1 ] || rm -f "$fetch_error_file" \
      || die 'could not remove obsolete fetch diagnostic'
  done
done
FETCHED_FILE=

fetch_error_path() {
  fetch_error_key=${1:-}
  validate_key "$fetch_error_key" || return 1
  printf '%s/fetch-error-%s' "$FETCH_ERROR_DIR" "$fetch_error_key"
}

clear_fetch_error() {
  fetch_error_file=$(fetch_error_path "${1:-}") || return 1
  rm -f "$fetch_error_file"
}

# Keep only the first line, remove terminal controls, redact credential-like
# values, and hide paths/URLs before returning a diagnostic for display.
sanitize_fetch_error_file() {
  fetch_error_source=${1:-}
  [ -r "$fetch_error_source" ] || return 1
  fetch_error_safe=$(LC_ALL=C awk '
    NR == 1 {
      original = $0
      if (tolower(original) ~ /(token|password|passwd|secret|credential|cookie|authorization|bearer|basic|api[ _-]*key)/)
        exit 1
      gsub(/\t/, " ")
      gsub(/[[:cntrl:]]/, "")
      gsub(/https?:\/\/[^[:space:]]*/, "[url]")
      gsub(/[Aa]uthorization[[:space:]]*:[[:space:]]*[^[:space:]]*([[:space:]]+[^[:space:]]*)?/, "[redacted]")
      gsub(/[Bb]earer[[:space:]]+[^[:space:]]*/, "[redacted]")
      gsub(/[Bb]asic[[:space:]]+[^[:space:]]*/, "[redacted]")
       gsub(/[[:alnum:]_-]*(token|Token|TOKEN|password|Password|PASSWORD|secret|Secret|credential|Credential|CREDENTIAL|api[_-]key|API[_-]KEY)[[:alnum:]_-]*[[:space:]]*[:=][[:space:]]*\"[^\"]*\"/, "[redacted]")
       gsub(/[[:alnum:]_-]*(token|Token|TOKEN|password|Password|PASSWORD|secret|Secret|SECRET|credential|Credential|CREDENTIAL|api[_-]key|API[_-]KEY)[[:alnum:]_-]*[[:space:]]*[:=][[:space:]]*[^[:space:]]*/, "[redacted]")
      gsub(/[^[:space:]]*\/[^[:space:]]*/, "[path]")
      gsub(/[[:alpha:]]:\\[^[:space:]]*/, "[path]")
      if (tolower($0) ~ /(token|password|passwd|secret|credential|cookie|authorization|bearer|basic|api[ _-]*key)/)
        exit 1
      sub(/^[[:space:]]+/, "")
      sub(/[[:space:]]+$/, "")
      print substr($0, 1, 200)
      exit
    }
  ' "$fetch_error_source" 2>/dev/null || true)

  [ -n "$fetch_error_safe" ] || return 1
  printf '%s\n' "$fetch_error_safe" \
    | LC_ALL=C awk 'NR == 1 && $0 ~ /[^[:print:]]/ { exit 1 }
                   NR == 1 && $0 ~ /[^[:space:]]/ { exit 0 }
                   { exit 1 }' >/dev/null 2>&1 || return 1
  case "$fetch_error_safe" in
    */*|*\\*) return 1 ;;
  esac
  printf '%s' "$fetch_error_safe"
}

extract_fetch_json_error() {
  fetch_error_source=${1:-}
  [ -r "$fetch_error_source" ] || return 1
  jq -er -s '
    def message:
      if type == "string" then .
      elif type == "object" and (.message | type) == "string" then .message
      else empty
      end;
    if length != 1 or (.[0] | type) != "object" then empty
    else
      .[0]
      | [(.error | message),
         (.message | message),
         (.errors |
         if type == "array" then .[] | message
         elif type == "object" then message
         else empty
         end)]
        | map(select(type == "string" and length > 0))
        | .[0] // empty
    end
  ' "$fetch_error_source" 2>/dev/null
}

# Classify only clear client/auth setup failures. A Jira 401/403 or a project
# permission error remains a Jira request failure unless TWG explicitly says
# its own credentials/site configuration is missing.
is_twg_auth_error() {
  auth_source=$1
  auth_extra=${2:-}
  if [ -n "$auth_source" ] && grep -Eiq \
    '(twg[^[:cntrl:]]*(not[[:space:]]+authenticated|authentication[[:space:]]+(required|failed|not[[:space:]]+configured)|credentials?[[:space:]].*(missing|not[[:space:]]+configured)|setup|login)|run[^[:alnum:]]+twg[[:space:]]+(setup|login)|auth\.conf|no[[:space:]]+(default[[:space:]]+)?site|configure[[:space:]]+twg)' \
    "$auth_source" 2>/dev/null; then
    return 0
  fi
  [ -n "$auth_extra" ] && grep -Eiq \
    '(twg[^[:cntrl:]]*(not[[:space:]]+authenticated|authentication[[:space:]]+(required|failed|not[[:space:]]+configured)|credentials?[[:space:]].*(missing|not[[:space:]]+configured)|setup|login)|run[^[:alnum:]]+twg[[:space:]]+(setup|login)|auth\.conf|no[[:space:]]+(default[[:space:]]+)?site|configure[[:space:]]+twg)' \
    "$auth_extra" 2>/dev/null
}

# Classify explicit transport status/code fields, never words in issue content.
# TWG may return a failed single-item v2 envelope with a zero process status.
is_twg_permission_error() {
  jq -se '
    def denied:
      type == "object" and
      ([.status, .statusCode, .httpStatus, .code] |
        any(. == 403 or . == "403" or . == "FORBIDDEN" or . == "PERMISSION_DENIED"));
    length == 1 and (.[0] | type) == "object" and (.[0] |
      (if (.data | type) == "object" then .data else {} end) as $data |
      if (.key | type) == "string" or ($data.key | type) == "string" then false
      else denied or (.error | denied) or
      (if ($data.items | type) == "array" and ($data.items | length) == 1 then
        $data.items[0] | type == "object" and .ok == false and (denied or (.error | denied))
       else false end) end)
  ' "$1" >/dev/null 2>&1 && return 0
  [ "${twg_status:-0}" -ne 0 ] && grep -Eq \
    '(^|[^A-Za-z0-9_])(HTTP([ /][0-9.]+)?[ :]+403|PERMISSION_DENIED|FORBIDDEN)([^A-Za-z0-9_]|$)' \
    "$2" 2>/dev/null
}

save_fetch_error() {
  fetch_error_key=${1:-}
  fetch_error_message=${2:-}
  fetch_error_file=$(fetch_error_path "$fetch_error_key") || return 1
  fetch_error_tmp=$(mktemp "$FETCH_ERROR_DIR/.fetch-error-$fetch_error_key.$$.XXXXXX") || return 1
  if printf '%s\n' "$fetch_error_message" > "$fetch_error_tmp" \
    && mv "$fetch_error_tmp" "$fetch_error_file"; then
    return 0
  fi
  rm -f "$fetch_error_tmp"
  return 1
}

record_fetch_error() {
  fetch_error_key=${1:-}
  fetch_error_prefix=${2:-$FETCH_ERROR_GENERIC}
  fetch_error_source=${3:-}
  fetch_error_fallback_source=${4:-}
  fetch_error_message=$FETCH_ERROR_GENERIC
  case "$fetch_error_prefix" in
    "$FETCH_ERROR_GENERIC"|"$FETCH_ERROR_TWG"|"$FETCH_ERROR_JIRA"|"$FETCH_ERROR_MISSING"|"$FETCH_ERROR_REST_AUTH"|"$FETCH_ERROR_REST_PERMISSION"|"$FETCH_ERROR_REST_NOT_FOUND"|"$FETCH_ERROR_REST_RATE"|"$FETCH_ERROR_REST_INVALID") fetch_error_message=$fetch_error_prefix ;;
  esac
  save_fetch_error "$fetch_error_key" "$fetch_error_message"
}

fetch_error_detail() {
  fetch_error_file=$(fetch_error_path "${1:-}") || return 1
  [ -s "$fetch_error_file" ] || return 1
  fetch_error_detail=$(sed -n '1p' "$fetch_error_file" 2>/dev/null || true)
  case "$fetch_error_detail" in
    "$FETCH_ERROR_GENERIC"|"$FETCH_ERROR_TWG"|"$FETCH_ERROR_JIRA"|"$FETCH_ERROR_MISSING"|"$FETCH_ERROR_REST_AUTH"|"$FETCH_ERROR_REST_PERMISSION"|"$FETCH_ERROR_REST_NOT_FOUND"|"$FETCH_ERROR_REST_RATE"|"$FETCH_ERROR_REST_INVALID") printf '%s' "$fetch_error_detail" ;;
    *) printf '%s' "$FETCH_ERROR_GENERIC" ;;
  esac
}

# Validate the complete issue key before it is used in a path or command.
validate_key() {
  key=${1:-}
  [ -n "$key" ] || return 1
  case "$key" in
    *[!ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-]*) return 1 ;;
  esac
  printf '%s\n' "$key" | grep -Eq "^(${JIRA_PROJECTS})-[0-9]+$"
}

cache_entry_valid() {
  cache_key=${1:-}
  validate_key "$cache_key" || return 1
  cache_file="$CACHE/$cache_key.json"
  [ -s "$cache_file" ] && [ ! -L "$cache_file" ] \
    && [ "$CACHE_TTL_MIN" -gt 0 ] \
    && [ -n "$(find "$cache_file" -mmin -"$CACHE_TTL_MIN" -print 2>/dev/null)" ] \
    && issue_payload_valid "$cache_file" "$cache_key"
}

# Also checked under the connection lock immediately before native projection:
# a validated canonical pathname can have been replaced since fetch returned.
issue_payload_valid() {
  jq -s -e --arg requested_key "$2" \
      --arg request "$FIELD_REQUEST_SIGNATURE" --argjson legacy "$LEGACY_FIELD_REQUEST" \
      'length == 1 and ((.[0] | type) == "object") and .[0].key == $requested_key
       and (.[0]._peek_request == $request or ($legacy == 1 and (.[0] | has("_peek_request") | not)))' \
      "$1" >/dev/null 2>&1
}

clear_cache() {
  clear_cache_key=${1:-}
  if [ -n "$clear_cache_key" ]; then
    validate_key "$clear_cache_key" || die 'invalid Jira issue key'
    cache_invalidate "$clear_cache_key" || return 1
    clear_fetch_error "$clear_cache_key" || true
    return 0
  fi
  # Remove only direct, regular cache files. Never traverse a nested directory
  # that may have been created by another version or by user error.
  for clear_cache_file in "$CACHE"/* "$CACHE"/.[!.]* "$CACHE"/..?*; do
    [ -f "$clear_cache_file" ] && [ ! -L "$clear_cache_file" ] || continue
    rm -f "$clear_cache_file" || return 1
  done
  for clear_error_file in "$FETCH_ERROR_DIR"/* "$FETCH_ERROR_DIR"/.[!.]* "$FETCH_ERROR_DIR"/..?*; do
    [ -f "$clear_error_file" ] && [ ! -L "$clear_error_file" ] || continue
    rm -f "$clear_error_file" || return 1
  done
}

fetch_cleanup() {
  fetch_cleanup_file=${1:-}
  [ "$CACHE_TTL_MIN" -eq 0 ] || return 0
  case "$fetch_cleanup_file" in
    "$STATE"/.issue-*) rm -f "$fetch_cleanup_file" ;;
  esac
}

# fetch() uses private same-filesystem temporaries before publishing a cache
# entry. POSIX shell functions do not have local variables, so top-level
# callers can use this helper from their signal/exit traps as well.
fetch_work_cleanup() {
  for fetch_work_file in "${raw:-}" "${stderr:-}" "${normalized:-}" "${json_error:-}"; do
    case "$fetch_work_file" in
      "$STATE"/.twg-json.*|"$STATE"/.twg-stderr.*|\
      "$STATE"/.twg-normalized.*|"$STATE"/.twg-error.*)
        rm -f "$fetch_work_file"
        ;;
    esac
  done
  case "${rest_dir:-}" in "$STATE"/.rest-fetch.*) [ -d "$rest_dir" ] && rm -rf "$rest_dir" ;; esac
  case "${rest_metadata_dir:-}" in "$STATE"/.rest-metadata.*) [ -d "$rest_metadata_dir" ] && rm -rf "$rest_metadata_dir" ;; esac
  connection_unlock || true
  cache_publish_unlock || true
}

fetch_failure() {
  fetch_failure_key=${1:-}
  fetch_failure_prefix=${2:-$FETCH_ERROR_GENERIC}
  fetch_failure_source=${3:-}
  fetch_failure_fallback_source=${4:-}
  # The ordering decision and every failure-side mutation are one transaction.
  # Keep the same key-lock -> connection-lock order as successful publication.
  cache_publish_lock "$fetch_failure_key" || return 1
  if ! connection_lock; then cache_publish_unlock; return 1; fi
  if ! connection_assert_current || { [ -n "${fetch_generation:-}" ] &&
      [ "$(cache_generation_read "$fetch_failure_key")" != "$fetch_generation" ]; }; then
    connection_unlock; cache_publish_unlock; return 1
  fi
  fetch_failure_result=1
  if [ "$fetch_failure_prefix" = "$FETCH_ERROR_REST_PERMISSION" ]; then
    if cache_generation_increment_locked "$fetch_failure_key" && rm -f "$CACHE/$fetch_failure_key.json"; then
      FETCH_PERMISSION_DENIED=1
      record_fetch_error "$fetch_failure_key" "$fetch_failure_prefix" || true
    fi
  else
    record_fetch_error "$fetch_failure_key" "$fetch_failure_prefix" \
      "$fetch_failure_source" "$fetch_failure_fallback_source" || true
  fi
  if [ "$fetch_failure_prefix" != "$FETCH_ERROR_REST_PERMISSION" ] && cache_entry_valid "$fetch_failure_key"; then
    if clear_fetch_error "$fetch_failure_key"; then
      FETCHED_FILE=$CACHE/$fetch_failure_key.json
      fetch_failure_result=0
    fi
  fi
  connection_unlock || { cache_publish_unlock; return 1; }
  cache_publish_unlock || return 1
  [ "$fetch_failure_result" -ne 0 ] || printf '%s' "$FETCHED_FILE"
  return "$fetch_failure_result"
}

# Run one metadata-only request for the keys listed in a file. The key file is
# generated from validated issue keys, so expanding the function's positional
# arguments cannot introduce options or shell syntax.
run_twg_metadata_batch() {
  metadata_keys_file=${1:-}
  metadata_raw=${2:-}
  metadata_stderr=${3:-}
  [ -r "$metadata_keys_file" ] || return 1
  [ -n "$metadata_raw" ] && [ -n "$metadata_stderr" ] || return 1
  command -v "$TWG" >/dev/null 2>&1 || return 127

  set --
  while IFS= read -r metadata_key || [ -n "$metadata_key" ]; do
    validate_key "$metadata_key" || continue
    set -- "$@" "$metadata_key"
  done < "$metadata_keys_file"
  [ "$#" -gt 0 ] || return 1

  metadata_status=0
  "$TWG" --mode user --api-version v2 --site "$JIRA_SITE" --output json \
    jira workitem get "$@" --fields "$METADATA_FIELDS" \
    > "$metadata_raw" 2> "$metadata_stderr" || metadata_status=$?
  return "$metadata_status"
}

run_rest_metadata_batch() (
  metadata_keys_file=$1; metadata_raw=$2; metadata_stderr=$3
  rest_dir=$(mktemp -d "$STATE/.rest-metadata.$$.XXXXXX") || return 1
  trap 'rm -rf "$rest_dir"' 0
  trap 'exit 1' 1 2 15
  rest_metadata_dir=$rest_dir
  rest_payload="$rest_dir/payload"; rest_status="$rest_dir/status"
  jq -Rn --arg fields "$METADATA_FIELDS" '[inputs | select(length > 0)] | {issueIdsOrKeys: ., fields:($fields | split(","))}' "$metadata_keys_file" > "$rest_payload" || { rm -rf "$rest_dir"; return 1; }
  # shellcheck source=scripts/jira-rest.sh
  . "$DIR/jira-rest.sh"
  rest_validate_auth || { rest_status_code=$?; rm -rf "$rest_dir"; return "$rest_status_code"; }
  rest_post "$(rest_origin)/rest/api/3/issue/bulkfetch" "$rest_payload" "$metadata_raw" "$rest_status" "$metadata_stderr" || { rm -rf "$rest_dir"; return 1; }
  rest_code=$(sed -n '1p' "$rest_status" 2>/dev/null || true)
  [ "$rest_code" = 200 ] || { rest_http_failure "$rest_status"; rest_rc=$?; rm -rf "$rest_dir"; return "$rest_rc"; }
  jq -s -e 'length == 1 and (.[0] | type) == "object" and (.[0].issues | type) == "array"' "$metadata_raw" >/dev/null 2>&1 || return 20
  rm -rf "$rest_dir"
)
run_metadata_batch() {
  connection_assert_current || return 1
  batch_connection_status=0
  if [ "$JIRA_BACKEND" = rest ]; then run_rest_metadata_batch "$@" || batch_connection_status=$?; else run_twg_metadata_batch "$@" || batch_connection_status=$?; fi
  connection_assert_current --identity || return 1
  if { [ "$JIRA_BACKEND" = rest ] && [ "$batch_connection_status" -eq 10 ]; } \
    || { [ "$JIRA_BACKEND" = twg ] && [ "$batch_connection_status" -ne 0 ] && is_twg_auth_error "$3" "$2"; }; then
    connection_revoke || true
  fi
  return "$batch_connection_status"
}

# fetch KEY -> prints path of canonical issue JSON, using the cache when fresh.
# TWG is deliberately invoked with direct JSON output so the plugin never has
# to trust an indirect path to a second response file.
fetch() {
  fetch_generation=
  FETCH_PERMISSION_DENIED=0
  connection_assert_current || return 1
  key=${1:-}
  validate_key "$key" || return 1
  if [ "$CACHE_TTL_MIN" -gt 0 ]; then
    out="$CACHE/$key.json"
  else
    # Created only after a successful request. Callers consume this file
    # immediately and remove it after use; keeping it outside CACHE means
    # TTL=0 never creates a durable issue cache entry.
    out=
  fi

  if [ "$CACHE_TTL_MIN" -gt 0 ] && cache_entry_valid "$key"; then
    if ! clear_fetch_error "$key"; then
      if fetch_failure "$key" "$FETCH_ERROR_GENERIC"; then
        return 0
      fi
      return 1
    fi
    FETCHED_FILE=$out
    printf '%s' "$out"
    return 0
  fi

  # Reserve an ordered attempt before transport. A later miss supersedes this
  # attempt even if the earlier response arrives last (or the later read fails).
  cache_publish_lock "$key" || return 1
  if ! cache_generation_increment_locked "$key"; then cache_publish_unlock; return 1; fi
  fetch_generation=$(cache_generation_read "$key") || { cache_publish_unlock; return 1; }
  cache_publish_unlock || return 1

  if [ "$JIRA_BACKEND" = twg ] && ! command -v "$TWG" >/dev/null 2>&1; then
    if fetch_failure "$key" 'TWG CLI unavailable; install the official Atlassian TWG CLI, ensure it is on PATH, then run twg setup'; then
      return 0
    fi
    return 1
  fi

  raw=$(mktemp "$STATE/.twg-json.$$.XXXXXX") || {
    if fetch_failure "$key" "$FETCH_ERROR_GENERIC"; then
      return 0
    fi
    return 1
  }
  stderr=$(mktemp "$STATE/.twg-stderr.$$.XXXXXX") || {
    rm -f "$raw"
    if fetch_failure "$key" "$FETCH_ERROR_GENERIC"; then
      return 0
    fi
    return 1
  }
  normalized=$(mktemp "$STATE/.twg-normalized.$$.XXXXXX") || {
    rm -f "$raw" "$stderr"
    if fetch_failure "$key" "$FETCH_ERROR_GENERIC"; then
      return 0
    fi
    return 1
  }
  twg_status=0
  if [ "$JIRA_BACKEND" = rest ]; then
    # The REST transport writes the same canonical issue shape consumed below.
    # shellcheck source=scripts/jira-rest.sh
    . "$DIR/jira-rest.sh"
    rest_dir="$STATE/.rest-fetch.$$.XXXXXX"
    rest_dir=$(mktemp -d "$rest_dir") || twg_status=1
    if [ "$twg_status" -eq 0 ]; then
      rest_fetch_issue "$key" "$rest_dir" > "$raw" 2> "$stderr" || twg_status=$?
      rm -rf "$rest_dir"
    fi
  else
    set --
    if [ "$LEGACY_FIELD_REQUEST" -eq 0 ]; then set -- --fields "$DETAIL_FIELDS"; fi
    if [ "$FETCH_COMMENTS" -eq 1 ]; then set -- "$@" --comments; fi
    "$TWG" --mode user --api-version v2 --site "$JIRA_SITE" --output json \
      jira workitem get "$key" "$@" > "$raw" 2> "$stderr" \
      || twg_status=$?
  fi
  connection_assert_current --identity || { rm -f "$raw" "$stderr" "$normalized"; return 1; }
  if { [ "$JIRA_BACKEND" = rest ] && [ "$twg_status" -eq 10 ]; } \
    || { [ "$JIRA_BACKEND" = twg ] && [ "$twg_status" -ne 0 ] && is_twg_auth_error "$stderr" "$raw"; }; then
    if [ "$JIRA_BACKEND" = rest ]; then record_fetch_error "$key" "$FETCH_ERROR_REST_AUTH"; else record_fetch_error "$key" "$FETCH_ERROR_TWG"; fi
    connection_revoke || true
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  fi
  # Superseded failures must not invalidate a newer attempt's cache either.
  [ "$(cache_generation_read "$key")" = "$fetch_generation" ] || {
    rm -f "$raw" "$stderr" "$normalized"; return 1
  }
  if [ "$JIRA_BACKEND" = twg ] && is_twg_permission_error "$raw" "$stderr"; then
    fetch_failure "$key" "$FETCH_ERROR_REST_PERMISSION" || true
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  fi
  if [ "$twg_status" -ne 0 ]; then
    json_error=$(mktemp "$STATE/.twg-error.$$.XXXXXX") || {
      if fetch_failure "$key" 'Jira request failed' '' "$stderr"; then
        rm -f "$raw" "$stderr" "$normalized"
        return 0
      fi
      rm -f "$raw" "$stderr" "$normalized"
      return 1
    }
    fetch_failure_result=1
    if [ "$JIRA_BACKEND" = rest ]; then
      case "$twg_status" in
        10) fetch_failure "$key" "$FETCH_ERROR_REST_AUTH" && fetch_failure_result=0 ;;
        11) fetch_failure "$key" "$FETCH_ERROR_REST_NOT_FOUND" && fetch_failure_result=0 ;;
        12) fetch_failure "$key" "$FETCH_ERROR_REST_RATE" && fetch_failure_result=0 ;;
        13) fetch_failure "$key" "$FETCH_ERROR_REST_PERMISSION" || true ;;
        20) fetch_failure "$key" "$FETCH_ERROR_REST_INVALID" && fetch_failure_result=0 ;;
        127) fetch_failure "$key" "$FETCH_ERROR_MISSING" && fetch_failure_result=0 ;;
        *) fetch_failure "$key" "$FETCH_ERROR_JIRA" && fetch_failure_result=0 ;;
      esac
      rm -f "$raw" "$stderr" "$normalized" "$json_error"
      return "$fetch_failure_result"
    fi
    if extract_fetch_json_error "$raw" > "$json_error"; then
      if is_twg_auth_error "$stderr" "$json_error"; then
        fetch_failure "$key" 'TWG is not authenticated or configured; run twg setup, then retry' "$json_error" "$stderr" \
          && fetch_failure_result=0
      elif fetch_failure "$key" 'Jira request failed' "$json_error" "$stderr"; then
        fetch_failure_result=0
      fi
    else
      if is_twg_auth_error "$stderr"; then
        fetch_failure "$key" 'TWG is not authenticated or configured; run twg setup, then retry' '' "$stderr" \
          && fetch_failure_result=0
      elif fetch_failure "$key" 'Jira request failed' '' "$stderr"; then
        fetch_failure_result=0
      fi
    fi
    rm -f "$raw" "$stderr" "$normalized" "$json_error"
    return "$fetch_failure_result"
  fi

  # Direct JSON may be an issue object. Accept a single data wrapper, including
  # TWG's single-item data array, but never accept multiple documents/issues or
  # an output-files envelope.
  if ! jq -s -e --arg requested_key "$key" --arg request "$FIELD_REQUEST_SIGNATURE" '
    if length != 1 or (.[0] | type) != "object" then
      error("unexpected JSON response")
    else
      .[0] as $doc
       | (if ($doc.data | type) == "array" then
            if ($doc.data | length) == 1 then $doc.data[0] else error("multiple issues") end
          elif ($doc.data | type) == "object" then $doc.data
          else $doc
          end) as $issue
      | if ($issue | type) == "object" and $issue.key == $requested_key
        then (if ($issue.fields | type) == "object" then $issue.fields + $issue else $issue end)
          | ._peek_request = $request
        else error("unexpected issue JSON")
        end
    end
  ' "$raw" > "$normalized" 2>/dev/null; then
    if fetch_failure "$key" 'Jira response was not valid issue JSON' '' "$stderr"; then
      rm -f "$raw" "$stderr" "$normalized"
      return 0
    fi
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  fi

  connection_assert_current || { rm -f "$raw" "$stderr" "$normalized"; return 1; }
  cache_publish_lock "$key" || {
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  }
  published_generation=$(cache_generation_read "$key") || {
    cache_publish_unlock || true
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  }
  if [ "$published_generation" != "$fetch_generation" ]; then
    cache_publish_unlock || true
    rm -f "$raw" "$stderr" "$normalized"
    return 1
  fi
  if [ "$CACHE_TTL_MIN" -eq 0 ]; then
    out=$(mktemp "$STATE/.issue-$key.$$.XXXXXX") || {
      cache_publish_unlock
      rm -f "$raw" "$stderr" "$normalized"
      return 1
    }
  fi
  if ! connection_lock; then
    cache_publish_unlock; rm -f "$raw" "$stderr" "$normalized"; return 1
  fi
  if ! connection_assert_current; then
    connection_unlock; cache_publish_unlock; rm -f "$raw" "$stderr" "$normalized"; return 1
  fi
  if ! mv "$normalized" "$out"; then
    connection_unlock
    cache_publish_unlock
    rm -f "$raw" "$stderr" "$normalized"
    if fetch_failure "$key" "$FETCH_ERROR_GENERIC"; then
      return 0
    fi
    return 1
  fi
  clear_fetch_error "$key" || { connection_unlock; cache_publish_unlock; return 1; }
  connection_unlock || return 1
  if ! cache_publish_unlock; then
    rm -f "$raw" "$stderr"
    return 1
  fi
  rm -f "$raw" "$stderr"
  FETCHED_FILE=$out
  printf '%s' "$out"
  return 0
}

require_backend
connection_initialize || die 'Connection changed or identity is unavailable; verify authentication and reconnect.'
