import test from "node:test";
import assert from "node:assert/strict";
import { issueAsMarkdown, MARKDOWN_LIMIT } from "../mods/jira-peek/model.js";

const field = (id, section, label) => ({ id, section, label: label || id });
const layout = (fields, showEmpty = false) => ({ version: 1, showEmpty, fields });

const baseLayout = layout([
  field("summary", "body", "Summary"),
  field("status", "header", "Status"),
  field("assignee", "header", "Assignee"),
  field("updated", "header", "Updated"),
  field("description", "body", "Description"),
  field("comments", "body", "Comments"),
  field("priority", "details", "Priority"),
]);

const issue = {
  key: "ABC-123",
  summary: "Checkout retry loop after token refresh",
  status: "In Progress",
  description: "When the session token expires, checkout retries forever.\n\n- GIVEN a signed-in shopper\n- WHEN the token expires during submit\n- THEN checkout shows one retry prompt",
  metadata: [
    { id: "assignee", label: "Assignee", value: "Rin Vale" },
    { id: "updated", label: "Updated", value: "2026-11-09T09:30:00Z" },
    { id: "priority", label: "Priority", value: "High" },
  ],
  comments: [{ author: "Rin Vale", created: "2026-11-09T09:30:00Z", body: "The cause is `src/checkout/retry.js:42`." }],
  commentsTotal: 1,
  commentsDeferred: false,
  fetchedAt: Date.UTC(2026, 10, 9, 14, 32),
};

test("issueAsMarkdown follows the configured sections and produces stable Markdown", () => {
  assert.equal(issueAsMarkdown(issue, baseLayout, "https://jira.example.test/browse/ABC-123"), `# ABC-123 — Checkout retry loop after token refresh

https://jira.example.test/browse/ABC-123

Fetched 09 Nov 2026 · 14:32 UTC

- **Status:** In Progress
- **Assignee:** Rin Vale
- **Updated:** 09 Nov 2026

## Description

When the session token expires, checkout retries forever.

- GIVEN a signed-in shopper
- WHEN the token expires during submit
- THEN checkout shows one retry prompt

## Comments (1)

**Rin Vale** — 09 Nov 2026

The cause is \`src/checkout/retry.js:42\`.

## Details

### Priority

High`);
});

test("hidden fields are never copied, including a hidden summary and status", () => {
  const hidden = layout([
    field("summary", "hidden", "Summary"),
    field("status", "hidden", "Status"),
    field("description", "body", "Description"),
    field("comments", "hidden", "Comments"),
    field("priority", "hidden", "Priority"),
  ]);
  const text = issueAsMarkdown(issue, hidden, "https://jira.example.test/browse/ABC-123");
  assert.ok(text.startsWith("# ABC-123\n\n"));
  assert.doesNotMatch(text, /Checkout retry loop/);
  assert.doesNotMatch(text, /In Progress/);
  assert.doesNotMatch(text, /Comments/);
  assert.doesNotMatch(text, /Priority/);
});

test("summary is promoted only for the reader's default first-body title", () => {
  const renamed = layout([
    field("summary", "body", "Title"),
    field("description", "body", "Description"),
  ]);
  assert.match(issueAsMarkdown(issue, renamed, "https://jira.example.test/browse/ABC-123"),
    /^# ABC-123\n\nhttps:\/\/jira\.example\.test\/browse\/ABC-123\n\nFetched[^\n]*\n\n## Title\n\nCheckout retry loop/);

  const moved = layout([
    field("summary", "header", "Summary"),
    field("status", "header", "Status"),
  ]);
  assert.match(issueAsMarkdown(issue, moved, "https://jira.example.test/browse/ABC-123"),
    /^- \*\*Summary:\*\* Checkout retry loop after token refresh$/m);

  const empty = { ...issue, summary: "" };
  assert.match(issueAsMarkdown(empty, baseLayout, "https://jira.example.test/browse/ABC-123"), /^# ABC-123\n/);
});

test("details preserve block structure and multi-line values", () => {
  const details = layout([
    field("summary", "body", "Summary"),
    field("priority", "details", "Priority"),
    field("customfield_10017", "details", "Release notes"),
  ]);
  const text = issueAsMarkdown({ ...issue, metadata: [
    { id: "priority", value: "High" },
    { id: "customfield_10017", value: "First paragraph\n\nSecond paragraph" },
  ] }, details, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /## Details\n\n### Priority\n\nHigh\n\n### Release notes\n\nFirst paragraph\n\nSecond paragraph$/);
});

test("comments are copied only from loaded data with honest state notes", () => {
  const base = "https://jira.example.test/browse/ABC-123";
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 0 }, baseLayout, base), /## Comments\n\n_No comments\._/);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 4, commentsDeferred: true }, baseLayout, base),
    /## Comments\n\n_Comments not loaded; open them in Peek or Jira\._/);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 4, commentsLoading: true }, baseLayout, base),
    /_Comments are loading\._/);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 4, commentsError: "permission_denied" }, baseLayout, base),
    /_Comments not included; Jira denied access\._/);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 4, commentsError: "request_failed" }, baseLayout, base),
    /_Comments not included; could not load them\._/);
  assert.match(issueAsMarkdown({ ...issue, commentsTotal: 5 }, baseLayout, base), /## Comments \(1 of 5\)[\s\S]*_Showing 1 of 5 comments\._/);
  assert.match(issueAsMarkdown({ ...issue, commentsDeferred: true }, baseLayout, base), /More comments may still load\./);
  assert.match(issueAsMarkdown({ ...issue, commentsError: "request_failed" }, baseLayout, base),
    /Some comments could not load\./);
  assert.match(issueAsMarkdown({ ...issue, commentsLoading: true }, baseLayout, base),
    /Comments are still loading\./);
  assert.match(issueAsMarkdown({ ...issue, comments: [{ ...issue.comments[0], body: "C".repeat(20000) }] },
    baseLayout, base), /Some comment text may be shortened\./);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 1 }, baseLayout, base),
    /Open in Jira to view 1 comment\._/);
  assert.match(issueAsMarkdown({ ...issue, comments: [], commentsTotal: 0, commentsDeferred: false,
    commentsError: null }, baseLayout, base), /_No comments\._/);
  assert.doesNotMatch(issueAsMarkdown({ ...issue, comments: [] }, layout([
    field("comments", "hidden", "Comments"),
  ]), base), /Comments/);
});

test("comments in Details stay below the Details heading", () => {
  const details = layout([field("summary", "body", "Summary"), field("comments", "details", "Comments")]);
  const text = issueAsMarkdown(issue, details, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /## Details\n\n### Comments \(1\)\n\n\*\*Rin Vale\*\* — 09 Nov 2026\n\nThe cause is/);
});

test("the unescaped Jira projection stays verbatim and is not rendered by the formatter", () => {
  const text = issueAsMarkdown({
    ...issue,
    description: "# Heading\n\n<script>alert('x')</script>\n\n[link](https://evil.example)\n\n| a | b |",
  }, baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.ok(text.includes("# Heading"));
  assert.ok(text.includes("<script>alert('x')</script>"));
  assert.ok(text.includes("[link](https://evil.example)"));
  assert.ok(text.includes("| a | b |"));
});

test("body text keeps Markdown hard-break spaces and normalizes only line endings", () => {
  const text = issueAsMarkdown({
    ...issue,
    description: "line one  \r\nline two\t\r\nline three",
  }, baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.ok(text.includes("line one  \nline two\t\nline three"));
  assert.doesNotMatch(text, /\r/);
});

test("hidden description and hidden custom fields never appear", () => {
  const hidden = layout([
    field("summary", "body", "Summary"),
    field("description", "hidden", "Description"),
    field("customfield_10017", "hidden", "Secret"),
    field("comments", "body", "Comments"),
  ]);
  const text = issueAsMarkdown({ ...issue, metadata: [{ id: "customfield_10017", value: "Hidden value" }] },
    hidden, "https://jira.example.test/browse/ABC-123");
  assert.ok(text.includes("Checkout retry loop after token refresh"));
  assert.doesNotMatch(text, /When the session token expires/);
  assert.doesNotMatch(text, /Hidden value/);
});

test("summary appears once and is promoted only when it is the first body field", () => {
  const moved = layout([
    field("description", "body", "Description"),
    field("summary", "body", "Summary"),
  ]);
  const text = issueAsMarkdown(issue, moved, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /^# ABC-123\n/);
  assert.equal((text.match(/Checkout retry loop after token refresh/g) || []).length, 1);
  assert.match(text, /## Summary\n\nCheckout retry loop after token refresh/);
});

test("empty placeholders are omitted while zero and false values survive", () => {
  const custom = layout([
    field("summary", "body", "Summary"),
    field("duedate", "body", "Due date"),
    field("customfield_1", "body", "Flag"),
    field("customfield_2", "body", "Count"),
  ], true);
  const text = issueAsMarkdown({ ...issue, metadata: [
    { id: "duedate", value: " \n\t" },
    { id: "customfield_1", value: false },
    { id: "customfield_2", value: 0 },
  ] }, custom, "https://jira.example.test/browse/ABC-123");
  assert.doesNotMatch(text, /Due date/);
  assert.doesNotMatch(text, /^—$/m);
  assert.match(text, /## Flag\n\nfalse/);
  assert.match(text, /## Count\n\n0/);
});

test("field and issue content notices survive in the copied document", () => {
  const notices = layout([
    field("summary", "body", "Summary"),
    field("priority", "header", "Priority"),
    field("customfield_1", "body", "Body field"),
    field("customfield_2", "details", "Detail field"),
  ]);
  const text = issueAsMarkdown({
    ...issue, truncated: true, unsupportedContent: true,
    metadata: [
      { id: "priority", value: "High", truncated: true },
      { id: "customfield_1", value: "Body", truncated: true },
      { id: "customfield_2", value: "Detail", unsupportedContent: true },
    ],
  }, notices, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /Some issue content is shortened or unsupported by Peek\./);
  assert.match(text, /Some header values are shortened or unsupported by Peek\./);
  assert.match(text, /This field is shortened\. Open in Jira for the full field\./);
  assert.match(text, /Some content is unsupported here\. Open in Jira for the full field\./);
  const bodyHeading = text.indexOf("## Body field"), bodyNote = text.indexOf("This field is shortened");
  const detailHeading = text.indexOf("### Detail field"), detailNote = text.indexOf("Some content is unsupported");
  assert.ok(text.indexOf("Some header values") < text.indexOf("- **Priority:** High"));
  assert.ok(bodyNote > bodyHeading && bodyNote < text.indexOf("\n\nBody", bodyHeading));
  assert.ok(detailNote > detailHeading && detailNote < text.indexOf("\n\nDetail", detailHeading));
});

test("comment state notes survive before bodies when the cap truncates the page", () => {
  const comments = Array.from({ length: 20 }, (_, index) => ({
    author: `Author ${index}`, created: "2026-11-09T09:30:00Z", body: "C".repeat(20000),
  }));
  const text = issueAsMarkdown({ ...issue, comments, commentsTotal: 100 },
    baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /_Showing 20 of 100 comments\._/);
  assert.match(text, /Copy truncated at 262,144 characters/);
  assert.ok(text.indexOf("Showing 20 of 100") < text.indexOf("Author 0"));
});

test("the copy bound is a hard whole-output cap with one marker", () => {
  const comments = Array.from({ length: 20 }, (_, index) => ({
    author: `Author ${index}`, created: "2026-11-09T09:30:00Z", body: "B".repeat(20000),
  }));
  const text = issueAsMarkdown({
    ...issue,
    description: "A".repeat(100000),
    comments,
    commentsTotal: comments.length,
  }, baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.ok(Array.from(text).length <= MARKDOWN_LIMIT);
  assert.equal((text.match(/… Copy truncated at 262,144 characters/g) || []).length, 1);
  assert.match(text, /… Copy truncated at 262,144 characters\. Open in Jira for the full issue\.$/);
});

test("an exactly-limit document is not truncated, while one extra code point is", () => {
  const base = "https://jira.example.test/browse/ABC-123";
  const withOne = issueAsMarkdown({ ...issue, description: "x", comments: [] }, baseLayout, base);
  const exact = issueAsMarkdown({ ...issue, description: "x".repeat(MARKDOWN_LIMIT - (withOne.length - 1)), comments: [] },
    baseLayout, base);
  assert.equal(Array.from(exact).length, MARKDOWN_LIMIT);
  assert.doesNotMatch(exact, /Copy truncated/);

  const over = issueAsMarkdown({ ...issue, description: "x".repeat(MARKDOWN_LIMIT - (withOne.length - 1) + 1), comments: [] },
    baseLayout, base);
  assert.ok(Array.from(over).length <= MARKDOWN_LIMIT);
  assert.match(over, /Copy truncated at 262,144 characters/);
});

test("the cap counts code points and never splits an astral character", () => {
  const text = issueAsMarkdown({ ...issue, description: "🙂".repeat(300000), comments: [] },
    baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.equal(Array.from(text).length, MARKDOWN_LIMIT);
  assert.match(text, /Copy truncated at 262,144 characters/);
  assert.doesNotMatch(text, /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(^|[^\uD800-\uDBFF])[\uDC00-\uDFFF]/);

  const under = issueAsMarkdown({ ...issue, description: "🙂".repeat(200000), comments: [] },
    baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.doesNotMatch(under, /Copy truncated/);
  assert.ok(under.includes("🙂".repeat(200000)));
});

test("invalid or mismatched inputs return null instead of inventing an issue", () => {
  const base = "https://jira.example.test/browse/ABC-123";
  assert.ok(issueAsMarkdown(issue, baseLayout, base, "https://jira.example.test"));
  assert.equal(issueAsMarkdown(issue, baseLayout, "http://jira.example.test/browse/ABC-123"), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, "https://user:pass@jira.example.test/browse/ABC-123"), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, `${base}?x=1`), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, `${base}#fragment`), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, "https://jira.example.test/browse/ABC-124"), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, base, "https://other.example.test"), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, base, "http://jira.example.test"), null);
  assert.equal(issueAsMarkdown(issue, baseLayout, base, "https://jira.example.test/path"), null);
  assert.equal(issueAsMarkdown({ ...issue, key: "not a key" }, baseLayout, base), null);
  assert.equal(issueAsMarkdown(issue, null, base), null);
  assert.equal(issueAsMarkdown(issue, { version: 1 }, base), null);
  assert.equal(issueAsMarkdown(issue, layout([null]), base), null);
  assert.equal(issueAsMarkdown(issue, layout([{ id: "summary", section: "weird", label: "Summary" }]), base), null);
  assert.equal(issueAsMarkdown(issue, layout([field("not_a_field", "body", "Nope")]), base), null);
  assert.equal(issueAsMarkdown(issue, layout([field("summary", "body"), field("summary", "body")]), base), null);
  assert.equal(issueAsMarkdown(issue, layout([field("comments", "header", "Comments")]), base), null);
  assert.equal(issueAsMarkdown(issue, layout(Array.from({ length: 33 }, (_, i) => field(`customfield_${i}`, "body"))), base), null);
  assert.doesNotThrow(() => issueAsMarkdown({ ...issue, metadata: [null] }, baseLayout, base));
});

test("missing timestamps, metadata and optional issue fields do not throw", () => {
  const text = issueAsMarkdown({
    key: "ABC-123", summary: "Harbor", status: "", description: "",
    metadata: undefined, comments: undefined, commentsTotal: undefined, fetchedAt: undefined,
  }, baseLayout, "https://jira.example.test/browse/ABC-123");
  assert.match(text, /^# ABC-123 — Harbor/);
  assert.doesNotMatch(text, /Fetched/);
  assert.doesNotMatch(text, /## Details/);
  assert.match(text, /_Comment data unavailable\._$/);
});
