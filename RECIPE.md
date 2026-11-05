# Jira Peek

A native Jira reader beside the terminal you are working in. Issue keys arrive
automatically; deliberate reading stays put. Colors and typography follow Herdr.

![Jira Peek with entirely fictional issue and terminal content](preview.png)

**Experimental 0.2.0. AI-assisted — use with caution.** Developed with AI
assistance and provided as-is under the [MIT License](LICENSE), without warranty.
Collaboration, pull requests, issue reports, feature requests and support are
closed for now. See the [project policy](CONTRIBUTING.md) and [security policy](SECURITY.md).

## What you see

A right panel with Issues, Following/Paused, Options and a close control. The
current issue's key, status, title, fetch time and actions lead the reader.
Descriptions are directly readable; Details and Comments reveal more content.
Open in Jira, copy and refresh remain accessible above the scrolling body.
The heading, actions and reading text share an aligned gutter. Compact spacing
groups issue identity and metadata; straight separators organize disclosures.
Reading surfaces keep a full accent outline while focused and a quiet boundary
otherwise. Help uses its empty footer space while preserving the hidden reader's
viewport and reading position; focused icon captions still have their own strip.

Issues opens a focused filter and stable list. New unread activity sits beside
navigation without moving the issue actions. Options and Help use an explicit
return to Issues; form Help preserves drafts. Empty fields stay hidden by default.
Small panels scroll long titles with the body while retaining key/actions.
Below 500px high, browsing uses a dedicated list; Enter returns to the reader.
The footer shows the current reading/search keys and keeps **? Keys** within
reach. The guide leads with the daily Find → Read → Back loop; other actions
live under More shortcuts. Enter reads inside Peek; Cmd+Enter or Ctrl+Enter
explicitly opens Jira from nonediting issue contexts. Native buttons retain
Enter/Space activation. Comments and Details
show their keys; C/D focus those disclosures, F toggles Follow, and N reads
one unread issue. Keyboard reading pauses Follow without losing the query.
P or the inline pin keeps one issue for this terminal; P again unpins it.
Pinning a different issue moves the pin immediately. During a detour, the existing
footer offers Return to KEY; K returns without clearing the filter. There is no
management screen or added row. Copy, Open and Refresh target the viewed issue.

## How it behaves

- Read explicitly addressed terminal screens with `hc read --lines 0`.
  Read history only when requested, up to 200 available lines. Do not send
  terminal input, scroll the terminal, or move focus during discovery.
- Follow the latest visible allowlisted key. User reading/filtering/selection
  pauses Follow. Keep selection, filter and reading position during incoming
  discovery; acknowledge one issue when reading the unread badge.
- Keep this terminal retains one exact source. Keep machine-qualified addresses distinct;
  Jira authentication and requests remain local even for remote terminals.
- Issue pins retain one key per source within the existing 200-key/12-source
  bounds, without retaining an extra body. They are session-only and reset with
  connection/cache state. Pinning is a direct, reversible action on the currently
  viewed issue. Never pin an issue for a manual source or infer a task.
- Search loaded metadata or look up an allowed key/same-origin Jira browse URL.
  Reject foreign origins and disallowed projects. Hidden filtered selections
  must not expose reader actions until the user returns to them explicitly.
- Request issue details on selection, reuse valid caches, and keep at most two
  issue/metadata reads in flight. Prioritize the latest selection and preserve
  loaded content on refresh failure. With REST, load comments separately.
- Default auto-refresh off. When enabled, refresh at most once per minute,
  stop after five minutes without panel input, and show actual fetch time.
- Share field layouts and reader preferences through the versioned
  `data/jira-peek/fields.json`. Validate edits, preserve last valid state, reject
  stale UI writes, and keep this file outside managed source. Use the
  [installed agent contract](docs/AGENT-GUIDE.md) and
  [schema](mods/jira-peek/fields.schema.json).
- Hide/reopen through a persistent personal toolbar toggle. Keyboard entry
  requires the optional host patch for synchronous `layout.focus`; stock hosts
  use Issues or Tab before typing. Retain native text editing and focus behavior.

## Built from

**herdr-app >= 0.1.10** is the desktop UI/mod host. **herdr-core** is the separate
terminal backend exposed as `hc`; the installer requires it on PATH without a
numeric core minimum. Check `herdr-app --version` and `hc --version` separately.
Keep **0.1.10** exact; never substitute **1.10.0** or a core/TUI version.

Use the complete source ZIP or checkout, including `scripts/`. Copying only
`mods/jira-peek` omits its runtime. From the source root:

```sh
python3 scripts/install-app.py --doctor
python3 scripts/install-app.py --check --attach
herdr-app do layout.switch '{"name":"main-jira-peek"}'
```

`--attach` creates a personal layout and Jira Peek toolbar toggle, preserves
originals and shortcuts, and refuses conflicts. Use `--attach YOUR_LAYOUT` for
a different stock-toolbar layout. Later installs use `--update --check`; the
[update guide](README.md#update-remove-and-inspect) explains private-preview
0.1.0 migration, numbered releases and rollback. Updates protect edited files
and retain the complete prior bundle. No personal layouts ship in this repository.

Use native GPUI controls, theme colors, argument-array execution and bounded
state. `demo.js` supplies wholly fictional content only when `props.demo` is
true; live operation must never silently fall back to the demo. Installed
`AGENTS.md` documents settings and native commands.

Do not rebuild the host during ordinary installation. The optional
[input patch](native/APP-INPUT.md) targets herdr-app 0.1.12; the separate
[highlighting extension](native/APP-HIGHLIGHT.md) targets 0.1.10. Do not stack
patches for different versions. Merge [keys.json](keys.json) only after verifying
`layout.focus`, using the attached block ID and preserving unrelated bindings.
See [toolbar integration](docs/PANEL-INTEGRATION.md) for custom layouts.

## Watch out

Review the code and [known limitations](README.md#known-limitations), test in an
isolated app home, back up settings and grant only necessary Jira access.
No support, fixes or release schedule are promised.

This mod runs local programs and reads terminal content. It makes read-only
Jira requests but an account/token may have broader permissions. Credentials
and issue caches use private local files, not an encrypted keychain. Read
[SECURITY.md](SECURITY.md) for permissions, retention and cleanup limits.

Never render issue bodies as active HTML/Markdown or send their text through a
shell. Mark unsupported/shortened content. Preserve connection/source boundaries
and reject stale responses. Hiding a panel does not close its in-memory state.
Stock-host input gaps, Linux GUI and accessibility limits remain documented.

## Done when

- The assembled mod passes Herdr's native checker and renders in an isolated app.
- Following, Browse, filtering, pinning and unread navigation preserve their
  documented state through asynchronous discovery and failures.
- Setup, fields and Help retain drafts and give errors without exposing secrets.
- Reader actions remain visible and named at narrow widths; text remains readable.
- The installer preserves private configuration, layouts, shortcuts and local edits.
- Optional host behavior is checked separately on its pinned build.
- Shared captures use only the [fictional fixtures](docs/screenshots/README.md).
