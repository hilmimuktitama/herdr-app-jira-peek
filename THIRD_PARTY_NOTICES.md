# Third-party notices

Peek for Jira is an unofficial, unaffiliated community native mod. Jira and
Atlassian are trademarks owned by Atlassian.

## Herdr

The native app edition uses [Herdr app](https://github.com/herdrdev/herdr-app)
and [herdr-core](https://github.com/herdrdev/herdr-core), distributed separately
under their own Apache 2.0 licenses and bundled dependency notices. Its UI calls
the app's GPUI mod API; no Herdr binary or vendored UI library is included here.

The optional [desktop highlighting patch](native/herdr-app-0.1.10-highlight.patch)
contains modified Herdr app source and context from v0.1.10, revision
`36725d47c89cd19345994363d6d9cdee5c42c80b`. It is distributed under the
[Apache License 2.0](native/LICENSE-HERDR); patch hunks identify the changes.
The patch also modifies the bundled gpui-kit shell's generation cleanup hook,
under that project's Apache 2.0 license. The build helper downloads the pinned
upstream source and its dependencies. No desktop binary or complete dependency
library is committed to this repository.

## Teamwork Graph CLI (TWG)

The mod calls the official Atlassian Teamwork Graph CLI for read-only Jira
Cloud work-item retrieval. TWG authenticates with Atlassian OAuth and is a
separately distributed tool and service with its own terms, privacy policy,
availability, and permission model. Peek for Jira does not manage TWG
credentials. Raw responses and stderr may exist transiently in private request
state while a request is running; see [local retention and cleanup](SECURITY.md).

- [Official setup guide](https://developer.atlassian.com/cloud/twg-cli/getting-started/installation/)
- [Organization permissions and IP restrictions](https://developer.atlassian.com/cloud/twg-cli/getting-started/configure-permissions/)
- [Atlassian Privacy Policy](https://www.atlassian.com/legal/privacy-policy)
- [Atlassian Developer Terms](https://developer.atlassian.com/platform/marketplace/atlassian-developer-terms/),
  linked from the TWG documentation. Follow the terms and consent presented by
  your installed TWG version and Atlassian account for the applicable agreement.

Peek's read-only operations do not imply that the TWG OAuth connection is
limited to read permissions. Organization settings control what TWG may
request; the configured Jira user must also have access to the relevant data.

## Jira Cloud REST API

The optional `rest` backend calls Atlassian's Jira Cloud REST API with `curl`.
For an existing configuration, it reads an email/API-token pair from the user's
external mode-600 netrc file without copying it into the mod. Native **Test & save**
instead creates or replaces a private mode-600 credential file in the app's
managed connection directory. Credentials are not printed or committed; local
file permissions do not provide keychain encryption. See
[native credential storage](SECURITY.md#native-herdr-app-edition). Use the scopes required
by the Atlassian app and the account's Jira permissions. See the [Jira Cloud
REST API documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
and [API token guidance](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

## Other runtime tools

These tools are installed separately, rather than bundled with the mod:

| Tool | Purpose | Upstream reference |
| --- | --- | --- |
| jq | JSON parsing and rendering | [Copyright and license notices](https://github.com/jqlang/jq/blob/master/COPYING) |
| curl | REST transport and account verification | [Copyright and license](https://curl.se/docs/copyright.html) |

Python, Git and shell utilities come from the user's system or package manager.
Their installed distributions provide relevant notices. Browser and clipboard
actions use the native Herdr API. The optional host build also requires the
pinned Rust/Zig toolchains and upstream dependency notices.

The mod source itself is available under the [MIT License](LICENSE).
