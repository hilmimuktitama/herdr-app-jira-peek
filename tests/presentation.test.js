import test from "node:test";
import assert from "node:assert/strict";
import { descriptionPreview, displayDate } from "../mods/jira-peek/model.js";

test("description preview preserves short paragraphs and normalizes line endings", () => {
  assert.deepEqual(descriptionPreview(null), { text: "", truncated: false });
  assert.deepEqual(descriptionPreview("  \r\n  "), { text: "", truncated: false });
  assert.deepEqual(descriptionPreview("  First paragraph.\r\n\r\n- One\r\n- Two  "),
    { text: "First paragraph.\n\n- One\n- Two", truncated: false });
  assert.deepEqual(descriptionPreview(42), { text: "42", truncated: false });
});

test("description preview limits long paragraphs at a natural boundary", () => {
  const text = "A small fictional garden grows beside the river. ".repeat(20);
  const result = descriptionPreview(text);
  assert.equal(result.truncated, true);
  assert.ok(Array.from(result.text).length <= 560);
  assert.match(result.text, /\S…$/u);
  assert.ok(text.startsWith(result.text.slice(0, -1)));
  assert.equal(text[result.text.length - 1], " ");
});

test("description preview enforces both line and character limits", () => {
  assert.deepEqual(descriptionPreview("one\ntwo\nthree\nfour", { maxLines: 2, maxChars: 50 }),
    { text: "one\ntwo…", truncated: true });
  assert.deepEqual(descriptionPreview("alpha beta gamma\nsecond", { maxLines: 2, maxChars: 12 }),
    { text: "alpha beta…", truncated: true });
  assert.deepEqual(descriptionPreview("abcdefghijk", { maxChars: 5 }),
    { text: "abcd…", truncated: true });
  assert.deepEqual(descriptionPreview("abc", { maxChars: 1 }), { text: "…", truncated: true });
});

test("description preview keeps unbroken Unicode intact and handles invalid bounds", () => {
  const result = descriptionPreview("🌱".repeat(20), { maxChars: 5 });
  assert.deepEqual(result, { text: "🌱🌱🌱🌱…", truncated: true });
  assert.deepEqual(descriptionPreview("short", { maxChars: 0, maxLines: NaN }),
    { text: "short", truncated: false });
  assert.deepEqual(descriptionPreview("short", null), { text: "short", truncated: false });
  assert.deepEqual(descriptionPreview("abc…def", { maxChars: 5 }), { text: "abc…", truncated: true });
});

test("displayDate formats valid dates and timestamps in UTC", () => {
  assert.equal(displayDate("2026-10-31"), "31 Oct 2026");
  assert.equal(displayDate("2026-11-01T00:30:00+02:00"), "31 Oct 2026");
  assert.equal(displayDate("2026-10-30T23:45:00-02:00"), "31 Oct 2026");
  assert.equal(displayDate("2024-02-29T12:00:00.123Z"), "29 Feb 2024");
});

test("displayDate preserves invalid dates and custom labels", () => {
  for (const value of ["2025-02-29", "2026-04-31", "2026-13-01", "2026-10-31T24:00:00Z",
    "2026-10-31T12:00:00+25:00", "2026-10-31T12:00:00", "31 Oct 2026", "Next milestone"]) {
    assert.equal(displayDate(value), value);
  }
  assert.equal(displayDate(null), "");
  assert.equal(displayDate(""), "");
});
