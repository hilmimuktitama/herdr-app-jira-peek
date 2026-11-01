# Agent workflows worth supporting

Research checked **2026-11-01**. These are source-backed product ideas, not a
claim that Jira Peek already provides delegation, field discovery or session
management. Only the shared field configuration below is implemented.

## Implemented: agents arrange the reader

Herdr's [official guide](https://herdr.dev/guide/) directs users to ask agents
to read the installed host guide and customize the app. Its
[mod catalog instructions](https://herdr.dev/mods/) treat a recipe as the brief
another agent reads before installation.

Jira Peek now installs its own agent guide and schema. UI edits and agent edits
use the same user-owned JSON file, with one layout per connection, automatic
reload, validation and protection against stale UI saves. No extra daemon,
command wrapper or dependency is required.

Concrete requests:

- Implementation: put acceptance criteria before the description, with status
  and priority in the header.
- QA: put reproduction notes and expected behavior first; keep owner and
  updated date in Details.
- Triage: put priority, assignee and labels near the top; hide comments until
  needed.

These requests edit the current connection's layout; they are not additional
saved profiles. Custom field IDs must be supplied or confirmed using approved
Jira metadata tools. See [the installed agent contract](AGENT-GUIDE.md).

## Best next step: resolve field names to IDs

Use case: “Show Acceptance Criteria first” currently requires a custom field
ID. Names can repeat, and visibility depends on the connection's access.
Atlassian's [Get fields API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-fields/#api-rest-api-3-field-get)
documents system/custom field metadata, IDs, names and schema, with visibility
rules based on configuration and permissions.

Proposal: use the user's approved read-only Jira tool to find matching IDs and
types, resolve ambiguous matches, then edit the existing layout file. Start
with an agent workflow; add a native picker only if repeated use justifies it.
Do not guess IDs, create Jira fields, or interpret an incomplete catalog as
proof that a field does not exist.

## Next: an explicit task brief

Use case: a developer has an issue open and wants to give an agent the relevant
requirements without copying an entire discussion.
The community [a2u/herdr-jira](https://github.com/a2u/herdr-jira/blob/main/README.md)
already documents issue-to-agent prompt templates and explicit target selection.
It targets the older TUI; its commands and delivery behavior are not native
Herdr app APIs and have not been adopted here.

Proposal: begin with **Copy task brief**, using the selected issue key, origin,
chosen visible fields, fetch time and any truncation warnings. Let the user
review and paste it. This keeps the field configuration useful for both reading
and handoff. Issue text remains quoted task data, never instructions to the
integration. Automatic submission, agent spawning and Jira transitions are
separate decisions, not side effects of opening an issue.

## Later: return to the agent working on an issue

Use case: after several tasks or a restart, a user wants to resume the session
that investigated an issue rather than start over.
Herdr's [official guide](https://herdr.dev/guide/) describes a worktree per issue.
[herdr-core](https://github.com/herdrdev/herdr-core/blob/master/README.md)
documents persistent terminals, agent roles and the installed `hc --skill`
contract. [Atuin Threads](https://github.com/atuinsh/herdr-atuin-threads/blob/main/README.md)
demonstrates a native mod that resumes captured coding sessions in a new tab.

Proposal: store an explicit local issue-to-session association, show its
availability, and offer an Open session action. Confirm the current native API
before building it; a similar mod is evidence of a useful interaction, not API
compatibility or a dependency recommendation. An agent's done state should not
automatically mark a Jira issue complete.

Field discovery removes the largest current configuration friction. A copied
brief is the smallest subsequent handoff feature. Session linking should wait
until those workflows show a real need.
