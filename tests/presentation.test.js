import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_UNIT, displayDate, presentationMode, readerMaxWidth, splitRailWidth, stackTitleVisible, statusColor,
} from "../mods/jira-peek/model.js";

const approx = (actual, expected) =>
  assert.ok(Math.abs(actual - expected) < 0.01, `${actual} is not within 0.01 of ${expected}`);

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

test("presentationMode switches modes at the u=13 boundaries", () => {
  // Guard: w < 18u (234) or h < 15u (195).
  assert.equal(presentationMode(233, 600), "guard");
  assert.equal(presentationMode(234, 600), "stack");
  assert.equal(presentationMode(500, 194), "guard");
  assert.equal(presentationMode(500, 195), "stack");
  // Card: w < 28u (364) and h < 24u (312).
  assert.equal(presentationMode(363, 300), "card");
  assert.equal(presentationMode(364, 300), "stack");
  assert.equal(presentationMode(363, 311), "card");
  assert.equal(presentationMode(363, 312), "stack");
  // Split: w >= 58u (754) or (w >= 46u (598) and h <= 40u (520)).
  assert.equal(presentationMode(597, 300), "stack");
  assert.equal(presentationMode(598, 300), "split");
  assert.equal(presentationMode(753, 600), "stack");
  assert.equal(presentationMode(754, 600), "split");
  assert.equal(presentationMode(598, 519), "split");
  assert.equal(presentationMode(598, 520), "split");
  assert.equal(presentationMode(598, 521), "stack");
  assert.equal(presentationMode(753, 520), "split");
  assert.equal(presentationMode(753, 521), "stack");
});

test("presentationMode switches modes at the u=20 boundaries", () => {
  // 18u=360, 15u=300, 28u=560, 24u=480, 58u=1160, 46u=920, 40u=800.
  assert.equal(presentationMode(359, 900, 20), "guard");
  assert.equal(presentationMode(360, 900, 20), "stack");
  assert.equal(presentationMode(1200, 299, 20), "guard");
  assert.equal(presentationMode(1200, 300, 20), "split");
  assert.equal(presentationMode(559, 400, 20), "card");
  assert.equal(presentationMode(560, 400, 20), "stack");
  assert.equal(presentationMode(559, 479, 20), "card");
  assert.equal(presentationMode(559, 480, 20), "stack");
  assert.equal(presentationMode(919, 400, 20), "stack");
  assert.equal(presentationMode(920, 400, 20), "split");
  assert.equal(presentationMode(1159, 900, 20), "stack");
  assert.equal(presentationMode(1160, 900, 20), "split");
  assert.equal(presentationMode(920, 799, 20), "split");
  assert.equal(presentationMode(920, 800, 20), "split");
  assert.equal(presentationMode(920, 801, 20), "stack");
});

test("presentation precedence checks guard, card, split, then stack", () => {
  assert.equal(presentationMode(233, 194), "guard");
  assert.equal(presentationMode(350, 300), "card");
  assert.equal(presentationMode(600, 300), "split");
  assert.equal(presentationMode(500, 400), "stack");
});

test("splitRailWidth clamps 32% of the panel between 240 and 360", () => {
  assert.equal(splitRailWidth(598), 240);
  approx(splitRailWidth(754), 241.28);
  assert.equal(splitRailWidth(1200), 360);
});

test("readerMaxWidth and stackTitleVisible follow the unit", () => {
  assert.equal(DEFAULT_UNIT, 13);
  assert.equal(readerMaxWidth(13), 520);
  assert.equal(readerMaxWidth(20), 800);
  assert.equal(readerMaxWidth(), 520);
  assert.equal(stackTitleVisible(337), false);
  assert.equal(stackTitleVisible(338), true);
  assert.equal(stackTitleVisible(519, 20), false);
  assert.equal(stackTitleVisible(520, 20), true);
});

test("statusColor separates progress, review and done roles with legacy fallbacks", () => {
  const theme = { info: "#7aa2f7", success: "#9ece6a", working: "#fabd2f", done: "#c0caf5",
    accent: "#82aaff", blocked: "#f7768e", muted: "#999999" };
  assert.equal(statusColor("In progress", theme), theme.info);
  assert.equal(statusColor("In review", theme), theme.working);
  assert.equal(statusColor("Testing", theme), theme.working);
  assert.equal(statusColor("Done", theme), theme.success);
  assert.equal(statusColor("Closed", theme), theme.success);
  assert.equal(statusColor("Blocked", theme), theme.blocked);
  assert.equal(statusColor("To do", theme), theme.muted);
  // Stock 0.1.16 exposes no info/success: progress follows the blue accent,
  // review keeps the working amber and done keeps its existing role.
  const stock = { accent: "#3b82f6", working: "#fabd2f", done: "#7aa2f7",
    blocked: "#f7768e", muted: "#999999" };
  assert.equal(statusColor("In progress", stock), stock.accent);
  assert.equal(statusColor("In review", stock), stock.working);
  assert.equal(statusColor("Done", stock), stock.done);
  const legacy = { working: "#fabd2f", done: "#c0caf5", blocked: "#f7768e", muted: "#999999" };
  assert.equal(statusColor("In progress", legacy), legacy.working);
  assert.equal(statusColor("Done", legacy), legacy.done);
});

test("invalid geometry degrades without throwing", () => {
  assert.equal(presentationMode(NaN, 600), "stack");
  assert.equal(presentationMode(600, Infinity), "stack");
  assert.equal(presentationMode(0, 0), "stack");
  assert.equal(presentationMode(600, 600, 0), "stack");
  assert.equal(splitRailWidth(NaN), 0);
  assert.equal(splitRailWidth(0), 0);
  assert.equal(readerMaxWidth(Infinity), 0);
  assert.equal(readerMaxWidth(0), 0);
  assert.equal(stackTitleVisible(NaN), false);
  assert.equal(stackTitleVisible(338, 0), false);
});
