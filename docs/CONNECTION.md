# Connecting Jira

The [README quickstart](../README.md#connect-jira) covers the usual setup. This
page gives token scopes, credential storage, and existing-configuration details.

## New connection

Choose **Set up Jira** in the panel, or **Options → Connection → Set up Jira**.
Before starting, have your Jira Cloud site URL, account email, project keys, and an
API token ready. If you use a scoped token, also have your Cloud ID. If you
already have a TWG/REST configuration, skip to Existing configuration.

1. Enter your Jira Cloud site root, such as `https://your-site.atlassian.net`,
   plus account email and project keys (`ABC, DEF`). Use the site root only; no
   `/jira` or `/browse` suffix.
2. Choose **Create API token ↗** to open Atlassian's token page. Prefer a scoped
   token with only read scopes; classic tokens are broader. Even scoped tokens can
   carry write scopes, so use a read-only token or a dedicated account. Paste the
   token into the masked field.
3. For a scoped token, enable **Scoped token** here and enter your **Cloud ID**;
   see [Atlassian's Cloud ID instructions](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/).
   Classic tokens skip this step.
4. Choose **Test & save**. A failed check preserves the previous connection;
   re-enter the token to retry. Cancel discards an unsaved form.

Scoped tokens use the Atlassian API gateway. The account check uses
`/rest/api/3/myself`, requiring account-read permission (`read:jira-user` for
classic scopes); issue reads usually require `read:jira-work` for classic scopes.
See the
[current-user reference](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-myself/#api-rest-api-3-myself-get)
for granular scopes. Setup does not prove access to every issue; the allowlist
limits keys sent, not your permissions.

Scoped setup verifies the site and Cloud-ID association before saving; see
[SECURITY.md](../SECURITY.md) for the lookup and reuse checks.

Credentials created by **Test & save** are saved under
`HERDR_APP_HOME/data/jira-peek/connection`, normally outside this checkout, in a
mode-600 file within a private directory. They are protected by file permissions,
**not an encrypted keychain**, and are not protected from other processes running
as your user, administrators, or filesystem backups. The token is never prefilled,
passed in arguments, or kept in localStorage. **Test & save** contacts only the
validated site or gateway and rejects redirects. See [SECURITY.md](../SECURITY.md).

## Existing configuration

Select **Choose configuration folder…** on the initial screen, or **Options →
Connection → Choose existing folder…**, then choose the folder containing your
private `config.sh` (not the file). You can also pass `--config-dir
/absolute/path` during install. No private configuration is copied. For manual
setup, copy [config.example.sh](../config.example.sh) to a private folder outside the
checkout as `config.sh`. For TWG, set `JIRA_BACKEND='twg'` and `JIRA_SITE`, then
run `twg setup`. For REST, set `JIRA_BACKEND='rest'` and an absolute private
`JIRA_NETRC_FILE` (mode 400/600). Both need `JIRA_BASE` and `JIRA_PROJECTS`;
scoped REST gateways also need `JIRA_CLOUD_ID`. See the
[agent guide](AGENT-GUIDE.md#connection-and-data-settings) for all variables and
[SECURITY.md](../SECURITY.md) for external-origin checks. Keep credentials outside
the checkout. **Reconnect** reloads the chosen configuration.
