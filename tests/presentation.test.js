import test from "node:test";
import assert from "node:assert/strict";
import { displayDate } from "../mods/jira-peek/model.js";

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
