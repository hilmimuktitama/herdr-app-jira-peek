# Native Jira Peek security policy

Jira Peek is an unofficial community mod for Jira Cloud, distributed under the
MIT License. Jira and Atlassian are Atlassian trademarks. The TWG backend uses
OAuth managed by TWG; REST uses a private netrc. Native setup can create its
own private credential file only when the user submits Test & save.

This mod was developed with AI assistance and is experimental software provided
as-is, without warranty. Bugs and security issues may remain. Review the code
and [known limitations](README.md#known-limitations), test in an isolated app home,
back up your settings, and grant only the Jira access you need before connecting
an account.

## Trust and security maintenance

Herdr mods are trusted local code with access to programs and files under your
user account. Install only source you trust. The native checker executes the
mod to validate it; it is not a security sandbox or a security audit.

The updater downloads code from this project's GitHub repository and runs its
installer. It checks that the selected tag stays unchanged during download,
that versions agree, and that managed local files have not been edited. Those
checks do not verify a signed release or protect against a compromised
maintainer account, repository, host or local toolchain. No release-signature
verification is implemented. Review the source and release notes before updating.

No release has a guaranteed security-support window, response time or backport
commitment. Private vulnerability reports may cover any version; include the
exact mod, herdr-app and herdr-core versions and whether the host is patched.
A fix, if provided, may require upgrading to a newer release.

## Native Herdr app edition

Experimental 0.3.2 runs as a native mod with local program access. Automatic discovery uses
passive, explicitly addressed `hc read --lines 0` calls. **History** explicitly
reads up to 200 available host history lines without scrolling or sending
input. This exposes more local terminal content to the mod; alternate-screen
history may be absent. Only validated allowlisted issue keys go to Jira.
Remote terminal addresses do not move credentials or Jira requests off the
local machine.

Unchanged default screen scans do not refresh Jira data. Optional **Auto-refresh issue** is
off for new users and refreshes the selected issue at most once every 60 seconds
when enabled, skipping busy requests.
It pauses that panel after five minutes without actual panel input; automatic
work and preference reloads do not renew the lease. This pause does not write the
shared opt-in or stop another active panel. Hidden panels stay alive and may
continue traffic within the lease; hide/reopen and reconnect retain a local
pause. A newly created panel can start with the saved opt-in. Options resumes a
paused panel locally; turning active refresh Off changes the shared preference.
Fetch time uses the payload file modification time, including cached payloads;
it does not establish current Jira state or continued account access.

Issue bodies are native plain text, with no fetched images or active embedded
links. Manual URL lookup checks that the normalized path is `/browse/KEY`,
on the configured HTTPS origin with an allowlisted key. Browser actions
construct links from that origin. Descriptions are capped at 100,000 characters, comments at 100 with
20,000 characters per body and 1,000,000 body characters total, and metadata
values at 4,096 characters.

Configuration is created through inline setup or chosen by folder. Its selected
path is remembered in the mod's localStorage. Native field layouts and the
Auto-refresh/source-highlighting preferences live in the shared private
`data/jira-peek/fields.json`; older UI preferences migrate there. The installer never copies
private configuration or credentials. Issue lists, filters, and source
snapshots remain in memory, with up to 200 keys per source, 12 source sessions,
and 40 loaded details. Closing a panel discards its memory; hiding it does not.
An issue pin stores only a key within those limits, without retaining an extra
body. Reconnect, Clear cache, source eviction and panel destruction discard it.
The separate private disk cache lives under
`HERDR_APP_HOME/data/jira-peek/state/connections/<folder-hash>` and follows
connection, epoch, and TTL rules. The hash identifies the directory by its
filesystem device and inode. Aliases of one directory share state, including
case aliases on case-insensitive volumes; distinct directories on case-sensitive
volumes keep separate caches and epochs. State starts fresh when that filesystem
identity changes. Zero TTL disables durable issue caching and keeps at most the
current source's logically selected body in memory. Filtering it out, covering
it with Help/Fields or hiding does not end that logical selection; changing to
another key retires the old full body while retaining searchable metadata.
Connection reset discards every body. This is not a secure-erasure guarantee.

Optional source highlighting requires the local desktop renderer extension.
The selected key and exact terminal address are held in memory for that mod
copy, not persisted by the highlight API. It decorates rendered cells without
terminal input or additional Jira requests. Disabling it or retiring the copy
clears its mark; hidden copies do not paint. Only the on/off preference is saved.
This extension is separate from the stock host.

**Test & save** sends the entered email and API token only to the validated
Jira Cloud site or Atlassian API gateway for a read-only account check. Setup
rejects redirects and unsupported destinations. Tokens travel from the native
form through a private temporary file, never process arguments, environment
variables, localStorage, or diagnostic messages. The helper stores a mode-600
netrc in a mode-700 managed connection directory, and switches config only
after successful verification and a stale-state check. These files are not
encrypted against other processes running as the same user, administrators,
or filesystem backups. Setup does not access an OS credential store.

The token field is masked and never loads the saved token. Its input state is
discarded on submission or cancellation. Normal save/failure cleanup removes
the temporary submission. Forced termination can leave private temporary
files until cleanup; filesystem deletion does not guarantee secure erasure.
Existing external configurations and credential files are not overwritten by
the setup form. Account verification does not establish every project or
field permission, and no Jira records are modified.

**Clear cache** clears issue memory in the invoking panel and issue disk cache
for its configuration folder, invalidates that connection's in-flight responses,
and reconnects. It leaves private configuration, credentials, and saved UI
choices intact. Other open
copies using the same configuration can rediscover or fetch data again. Other
configuration folders retain their caches. Close all copies before removing
`data/jira-peek` for broader cleanup. External configuration and credential
files, Herdr terminal history, clipboard contents, and backups are separate.

Version 0.3.1 does not reuse or delete the former shared cache at
`data/jira-peek/state/cache`. It can contain issue data from an earlier release
until you remove it. Close Peek before removing that old cache; deleting files
does not erase copies in filesystem snapshots or backups.

Config and epoch watchers clear the UI on drift; pending responses are checked
again before display. Credential/account changes and remote revocation are
detected on subsequent backend requests, not by a continuous authentication
poll. Request errors never forward raw transport output to Herdr.

Installer `--doctor [--json]` checks executable presence and the native app
version offline; it does not validate authentication. `--check` checks
capabilities and validates a staged mod before replacement. Updates reject
symlinks, unmanaged files, and edits to managed files. Only the regular
Herdr-generated `gpui-kit.d.ts` and `jsconfig.json` files are accepted as extras.
Updates preserve the full previous mod in a hidden backup under `mods` and
omit those generated files from the new bundle so Herdr regenerates paths.
The installer does not modify shipped layouts or existing keyboard bindings.

## Reporting a vulnerability

General issue reports, feature requests, collaboration and support requests are
closed for now; see the [project policy](CONTRIBUTING.md). Private vulnerability
reports are the only reporting exception. This channel is for security concerns
only; no response time or fix is guaranteed.

When available, use [GitHub's private vulnerability reporting](https://github.com/hilmimuktitama/herdr-app-jira-peek/security/advisories/new)
to send a security report to the maintainers. Otherwise, email
[hilmimukti@gmail.com](mailto:hilmimukti@gmail.com) with the subject
"Peek for Jira security report". The maintainer has chosen to publish this
contact address. Do not disclose vulnerabilities in a public issue.

Include the affected version, a concise description of the impact, reproduction
steps, and any suggested mitigation. Redact Jira URLs, issue content,
credentials, tokens, and other sensitive data from the report.

## Runtime files and cleanup limits

The project allowlist limits issue keys sent to the backend; it does not narrow
account permissions or redact terminal content read locally. Protect the chosen
private configuration and `HERDR_APP_HOME/data/jira-peek` state. Raw backend
responses and stderr can exist in private temporary files during requests.
Normal completion cleans request files; forced termination can leave files.
Cache TTL is not a complete retention or secure-erasure policy.

`config.sh` is parsed as allowlisted assignments, never executed as shell code.
The runtime rejects symlinks at the final component of its principal config,
state, cache and diagnostic paths. Saved credentials are protected by file
permissions, not against other processes running as the same user or backups.

For removal, close all copies, remove only this mod's personal layout block
and optional shortcuts, and remove its installed folder. Review update backups
separately. Remove `data/jira-peek` only if also deleting locally saved setup
credentials, configuration, preferences and cache is intended. External config
and credentials, TWG-managed state, terminal history, clipboard contents and
backups require separate handling. Uninstallation is not proof of complete
data erasure. See [removal instructions](README.md#update-remove-and-inspect).

Do not include configuration, credentials, raw transport output, terminal
captures or cached issues in public reports. Use entirely fictional reproduction
fixtures. Current offline native evidence uses stock herdr-app 0.1.12 and the
separate herdr-core 0.1.17 on macOS arm64. Historical optional-patch testing is
separate. Stock 0.1.12 retains the documented input gaps; Linux GUI, full
accessibility and optional renderer release-mode builds remain unverified.
See [known limitations](README.md#known-limitations).
