import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { FIELD_NAMES, validFieldId } from "../mods/jira-peek/model.js";
import { defaultFieldLayout, readFieldLayout, requestedReaderFields, placedFields, parseFieldFile, connectionFieldLayout, updateFieldFile, readerPreferences } from "../mods/jira-peek/model.js";

const field = (id, section, label = id) => ({ id, section, label });
const saved = fields => ({ version: 1, showEmpty: false, fields });

const connection = { configDir: "/fictional/connection", base: "https://jira.example.test", fields: [{ id: "summary", section: "body" }] };

test("shell, native model and schema agree on field IDs and intentional reader aliases", () => {
  const schema = JSON.parse(readFileSync(new URL("../mods/jira-peek/fields.schema.json", import.meta.url), "utf8"));
  const [standard, custom] = schema.$defs.field.properties.id.anyOf;
  assert.deepEqual([...standard.enum].sort(), Object.keys(FIELD_NAMES).sort());
  for (const id of [...standard.enum, "link", "customfield_0", "customfield_123456789012",
    "customfield_1234567890123", "customfield_", "customfield_1x", "customfield_1;echo", "constructor", "unknown"]) {
    const expected = standard.enum.includes(id) || new RegExp(custom.pattern).test(id);
    assert.equal(validFieldId(id), expected, id);
    const result = spawnSync("sh", ["-c", '. "$1"; preferences_is_detail_field "$2"', "field-contract",
      new URL("../scripts/preferences.sh", import.meta.url).pathname, id]);
    assert.equal(result.status === 0, (expected && id !== "summary") || id === "link", id);
  }
});

test("reader preferences accept legacy keys, return only auto-refresh and survive field updates", () => {
  const file = parseFieldFile('{"version":1,"preferences":{"autoRefresh":true,"highlightSource":false},"connections":[]}');
  assert.deepEqual(readerPreferences(file), { live: true });
  assert.deepEqual(readerPreferences(parseFieldFile(null)), { live: false });
  const other = { configDir: "/fictional/other", base: "https://other.example.test", fields: [field("priority", "header")] };
  const shared = parseFieldFile(JSON.stringify({ version: 1, preferences: file.preferences, connections: [connection, other] }));
  const updated = updateFieldFile(shared, connection.configDir, connection.base, saved([]));
  assert.deepEqual(updated.preferences, file.preferences);
  assert.deepEqual(updated.connections.find(entry => entry.configDir === "/fictional/other"), other);
  for (const preferences of [null, [], false, { autoRefresh: "yes" }, { highlightSource: 0 }, { unknown: true }]) {
    assert.throws(() => parseFieldFile(JSON.stringify({ version: 1, connections: [], preferences })));
  }
});

test("shared files select the exact connection, preserve other entries, and allow an empty layout", () => {
  const file = parseFieldFile(JSON.stringify({ version: 1, connections: [connection, { ...connection, base: "https://another.example.test", fields: [] }] }));
  assert.equal(connectionFieldLayout(file, connection.configDir, connection.base).fields[0].label, "Summary");
  assert.equal(connectionFieldLayout(file, "/elsewhere", connection.base), null);
  assert.deepEqual(connectionFieldLayout(file, connection.configDir, "https://another.example.test").fields, []);
  const updated = updateFieldFile(file, connection.configDir, connection.base, saved([field("priority", "header")]));
  assert.equal(updated.connections.length, 2);
  assert.deepEqual(updated.connections[0], file.connections[1]);
  assert.deepEqual(file.connections[0], connection, "updating a draft cannot mutate the original document");
  assert.deepEqual(parseFieldFile(JSON.stringify(updated)), updated);
});

test("invalid shared files reject the entire edit instead of silently changing working layouts", () => {
  const doc = entry => JSON.stringify({ version: 1, connections: [entry] });
  for (const invalid of ["", "null", "[]", "{", JSON.stringify({ version: 2, connections: [] }),
    JSON.stringify({ version: 1, connections: [], typo: true }),
    JSON.stringify({ version: 1, connections: [connection, connection] }),
    ...[null, { ...connection, configDir: "relative" }, { ...connection, base: "https://user:secret@jira.example.test" },
      { ...connection, showEmpty: "false" }, { ...connection, unknown: true },
      { ...connection, fields: [{ id: "summarry", section: "body" }] },
      { ...connection, fields: [{ id: "comments", section: "header" }] },
      { ...connection, fields: [field("summary", "body", " trailing ")] },
      { ...connection, fields: [field("summary", "body", "\u202eTitle")] },
      { ...connection, fields: [field("summary", "body", "x".repeat(81))] },
      { ...connection, fields: [...connection.fields, ...connection.fields] },
      { ...connection, fields: Array.from({ length: 33 }, (_, i) => field(`customfield_${i}`, "body")) }
    ].map(doc)]) assert.throws(() => parseFieldFile(invalid));
  assert.deepEqual(parseFieldFile(null), { version: 1, connections: [] });
});

test("the installed schema accepts documented origins and custom IDs", () => {
  const schema = JSON.parse(readFileSync(new URL("../mods/jira-peek/fields.schema.json", import.meta.url), "utf8"));
  const origin = new RegExp(schema.$defs.connection.properties.base.pattern);
  for (const base of ["https://jira.example.test", "https://jira.example.test:8443", "https://[::1]:443"]) {
    assert.equal(origin.test(base), true);
    assert.doesNotThrow(() => parseFieldFile(JSON.stringify({ version: 1, connections: [{ ...connection, base }] })));
  }
  for (const base of ["http://jira.example.test", "https://jira.example.test/path", "https://user:secret@jira.example.test"]) assert.equal(origin.test(base), false);
  assert.equal(new RegExp(schema.$defs.field.properties.id.anyOf[1].pattern).test("customfield_10016"), true);
});

test("default layout uses configured IDs and labels, with a fixed summary and grouped secondary fields", () => {
  const config = { fields: [{ id: "summary", label: "Title" }, { id: "status", label: "Workflow" }, { id: "customfield_10016", label: "Points" }, { id: "comments" }, { id: "link" }] };
  const layout = defaultFieldLayout(config);
  assert.deepEqual(layout.fields, [field("summary", "body", "Title"), field("status", "header", "Workflow"),
    field("customfield_10016", "details", "Points"), field("comments", "body", "Comments")]);
  assert.equal(layout.showEmpty, false);
});

test("corrupt, duplicate, oversized and unsupported saved layouts fall back to the configured layout", () => {
  const config = { fields: [{ id: "priority" }] };
  for (const invalid of ["not json", null, { version: 2, fields: [] }, saved([null]),
    saved([field("summary", "footer")]), saved([field("comments", "header")]),
    saved([field("constructor", "body")]), saved([field("customfield_1;echo", "body")]),
    saved([field("summary", "body"), field("summary", "hidden")]),
    saved(Array.from({ length: 33 }, (_, i) => field(`customfield_${i}`, "body")))]) {
    assert.deepEqual(readFieldLayout(invalid, config), defaultFieldLayout(config));
  }
  assert.deepEqual(readFieldLayout(saved([]), config).fields, []);
});

test("placement follows IDs and saved order even when labels repeat or change", () => {
  const layout = readFieldLayout(saved([field("customfield_10017", "body", "Notes"), field("summary", "hidden"),
    field("customfield_10016", "header", "Notes"), field("status", "details", "Workflow")]));
  const regions = placedFields({ summary: "Hidden title", status: "Review", metadata: [
    { id: "customfield_10016", label: "An old name", value: 0 },
    { id: "customfield_10017", label: "An old name", value: "First paragraph\n\nSecond paragraph\n\n" },
  ] }, layout);
  assert.equal(regions.header[0].value, "0");
  assert.equal(regions.body[0].value, "First paragraph\n\nSecond paragraph");
  assert.equal(regions.details[0].label, "Workflow");
  assert.equal(regions.body.length, 1);
  assert.equal(requestedReaderFields(layout), "customfield_10016,customfield_10017,status");
  assert.equal(requestedReaderFields({ fields: [...layout.fields].reverse() }), requestedReaderFields(layout));
});

test("empty fields are optional while zero, false, comments and content notices survive", () => {
  const layout = saved([field("duedate", "body"), field("customfield_1", "body"), field("comments", "details")]);
  const issue = { metadata: [{ id: "duedate", value: " \n\t" }, { id: "customfield_1", value: false, truncated: true, unsupportedContent: true }] };
  const compact = placedFields(issue, layout);
  assert.deepEqual(compact.body.map(f => f.value), ["false"]);
  assert.equal(compact.body[0].truncated, true);
  assert.equal(compact.body[0].unsupportedContent, true);
  assert.equal(compact.details[0].id, "comments");
  assert.deepEqual(placedFields(issue, { ...layout, showEmpty: true }).body.map(f => f.value), ["—", "false"]);
});

test("saved labels are bounded, cleaned, and default when blank", () => {
  const layout = readFieldLayout(saved([field("summary", "body", "\u202e\u0000Title"),
    field("status", "header", "  "), field("customfield_1", "details", "x".repeat(100))]));
  assert.deepEqual(layout.fields.map(f => f.label), ["Title", "Status", "x".repeat(80)]);
});


test("Linked Issues has shared placement validation and honest empty/unavailable states", () => {
  const layout = saved([field("issuelinks", "body", "Dependencies")]);
  for (const state of ["available", "unavailable"]) {
    const issue = { metadata: [{ id: "issuelinks", links: { state, records: [], malformed: false, truncated: false } }] };
    assert.deepEqual(placedFields(issue, layout).body, []);
    const visible = placedFields(issue, { ...layout, showEmpty: true }).body[0];
    assert.equal(visible.label, "Dependencies");
    assert.match(visible.value, state === "available" ? /No linked issues returned/ : /data unavailable/);
  }
  const malformed = { metadata: [{ id: "issuelinks", links: { state: "available", records: [], malformed: true } }] };
  assert.match(placedFields(malformed, layout).body[0].value, /could not be displayed/);
  assert.throws(() => parseFieldFile(JSON.stringify({ version: 1, connections: [{ ...connection,
    fields: [field("issuelinks", "header")] }] })), /cannot be placed in Header/);
  const valid = parseFieldFile(JSON.stringify({ version: 1, connections: [{ ...connection, fields: layout.fields }] }));
  assert.equal(connectionFieldLayout(valid, connection.configDir, connection.base).fields[0].label, "Dependencies");
});
