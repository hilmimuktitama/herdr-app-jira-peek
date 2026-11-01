# Peek for Jira configuration template.
# shellcheck disable=SC2034 # These assignments are exported data for the runtime.
# The native installer copies this template beside the private configuration.
# Use Set up Jira in the panel to configure a connection.
# Keep this file declarative: one supported NAME=value assignment per line.
# Quote string values. It is parsed as data and never executed as shell code.

# Backend is `twg` by default. Set `rest` to use Jira Cloud REST directly.
JIRA_BACKEND='twg'

# Jira Cloud browse origin, without a trailing slash. Required for both backends.
JIRA_BASE='https://your-site.atlassian.net'

# TWG's Atlassian site prefix (or bare cloud ID). Required for the TWG backend.
JIRA_SITE='your-site'

# REST credentials live in an external netrc file, never in this config.
# Use an absolute path to a mode-600 file containing the Jira API email/token.
JIRA_NETRC_FILE=''

# Optional Jira Cloud ID for the api.atlassian.com gateway. When empty, REST
# requests use JIRA_BASE as the machine host.
JIRA_CLOUD_ID=''

# Keep this allowlist narrow. Add projects explicitly (for example ABC|DEF).
JIRA_PROJECTS='ABC|DEF'

# Retention for lazily fetched full previews, in minutes. Use 0 for no durable
# issue cache; issue-list metadata is temporary either way.
CACHE_TTL_MIN=10

# Number of recent issues to preload metadata for (1–100).
# All detected keys remain searchable; older issues load when previewed.
MAX_CANDIDATES=20

# Compatibility setting for imported configurations; native layout is
# controlled by the panel.
PICKER_LAYOUT='bottom'

# Passive source discovery interval in whole seconds (1–60); 0 disables it.
# Follow latest is the default; filtering/navigation pauses following, not scans.
# Reconnect Peek after changing this setting (jira-peek.reconnect).
AUTO_REFRESH_SEC=2

# Compatibility setting for imported configurations. Native highlighting uses
# Options → Highlight source and requires the optional renderer extension.
SOURCE_HIGHLIGHT='off'

# Legacy matcher setting for imported configurations. The native panel detects
# standard Jira keys within JIRA_PROJECTS and does not use this expression.
# KEY_RE='(ABC|DEF)-[0-9]+'

# Choose the ordered fields requested for issue lists and issue views. The issue key
# is always retained as the selection identity. Empty values are allowed.
PICKER_FIELDS='status,summary'
PREVIEW_FIELDS='status,assignee,updated,description,comments'
READER_FIELDS='status,assignee,updated,link,description,comments'

# Optional human labels for standard or custom fields. Keep labels concise.
# FIELD_LABELS='customfield_10016:Points,duedate:Due'

# Native field placement, visibility and label overrides live in
# data/jira-peek/fields.json under the Herdr app home. Its root preferences
# object also controls Auto-refresh issue and source highlighting.
# Read mods/jira-peek/AGENTS.md there for all supported agent configuration.

# Optional compatibility setting for imported configurations.
# TEXT_STYLE='plain'
