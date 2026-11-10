import test from "node:test";
import assert from "node:assert/strict";
import { PeekModel, extractKeys, focusedSource, issueLink, parseIssueKey, uiPreferences, MAX_KEYS, MAX_SOURCES } from "../mods/jira-peek/model.js";

const config = { projects: ["ABC", "DEF"], base: "https://jira.example.test", ttl: 10, limit: 20, context: "one" };
function model() { const m = new PeekModel(); m.reset(config); m.useSource("t1"); m.follow(); return m; }

test("new sources start Paused with stable unread arrivals; activation and Follow restore independently", () => {
  const m = new PeekModel(); m.reset(config); m.useSource("t1");
  assert.equal(m.current.follow, false); assert.equal(m.current.activated, false);
  m.merge(["ABC-2", "ABC-1"]);
  const before = m.resultSlots().map(slot => slot.id);
  m.merge(["ABC-3"]);
  assert.equal(m.current.selected, null);
  assert.deepEqual(m.rows(), ["ABC-1", "ABC-2", "ABC-3"]);
  assert.deepEqual(m.resultSlots().slice(0, 2).map(slot => slot.id), before);
  assert.equal(m.current.unseen.size, 3);
  m.select("ABC-2"); assert.equal(m.current.activated, true);
  m.useSource("remote/t1"); assert.equal(m.current.activated, false);
  m.follow(); m.useSource("t1");
  assert.equal(m.current.follow, false); assert.equal(m.current.selected, "ABC-2");
  m.clearList(); assert.equal(m.current.activated, true); assert.equal(m.current.follow, false);
  m.useSource("remote/t1"); assert.equal(m.current.follow, true); assert.equal(m.current.activated, true);
  m.reset(config); m.useSource("t1"); assert.equal(m.current.activated, false);
});

test("Paused browsing appends arrivals while canonical recency and retention stay bounded", () => {
  const m = model();
  m.merge(Array.from({ length: MAX_KEYS }, (_, i) => `ABC-${i + 1}`));
  m.select("ABC-40"); m.toggleIssuePin("ABC-80");
  const selectedId = m.resultSlots().find(slot => slot.key === "ABC-40").id;
  for (let i = 201; i <= 600; i++) m.merge([`ABC-${i}`]);
  assert.equal(m.current.keys.length, MAX_KEYS);
  assert.equal(m.current.selected, "ABC-40"); assert.equal(m.current.pinnedIssueKey, "ABC-80");
  assert.equal(m.current.latestObserved, "ABC-600");
  assert.equal(m.resultSlots().find(slot => slot.key === "ABC-40").id, selectedId);
  assert.equal(m.compactSlots().length, MAX_KEYS);
  assert.equal(m.resultSlots().length, MAX_KEYS);
  assert.ok(m.resultSlots().every(slot => m.current.keys.includes(slot.key)));
  assert.ok([...m.current.presentation.eligible].every(key => m.current.keys.includes(key)));
  assert.ok(m.current.unseen.has("ABC-600")); assert.equal(m.rows().at(-1), "ABC-600");
  assert.equal(m.current.keys[0], "ABC-600");
});

test("metadata matches join the end automatically without replacing the selected issue", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2", "ABC-3"]);
  m.accept({ key: "ABC-1", summary: "Orchard paths" });
  m.accept({ key: "ABC-2", summary: "Orchard exports" });
  m.accept({ key: "ABC-3", summary: "Harbor" });
  m.filter("orchard");
  const slots = m.resultSlots().map(slot => ({ ...slot })), projection = m.current.presentation.projection;
  const before = m.current.presentation.actionsRevision;
  m.accept({ key: "ABC-1", summary: "Harbor paths" });
  m.accept({ key: "ABC-3", summary: "Orchard navigation" });
  assert.deepEqual(m.resultSlots().slice(0, slots.length), slots); assert.deepEqual(m.rows(), ["ABC-2", "ABC-3"]);
  assert.equal(m.current.selected, "ABC-1");
  assert.equal(m.current.presentation.projection, projection);
  const invalidated = m.current.presentation.actionsRevision; assert.ok(invalidated > before);
  m.accept({ key: "ABC-1", summary: "Orchard paths restored" });
  assert.ok(m.current.presentation.actionsRevision > invalidated);
  assert.deepEqual(m.rows(), ["ABC-1", "ABC-2", "ABC-3"]);
  assert.equal(m.current.selected, "ABC-1");
  m.accept({ key: "ABC-2", summary: "Harbor exports" });
  assert.deepEqual(m.rows(), ["ABC-1", "ABC-3"]);
  assert.ok(m.current.presentation.projection > projection);
});

test("an empty Paused search admits later matches automatically and keeps them unread until reading", () => {
  const m = model(); m.merge(["ABC-1"]); m.accept({ key: "ABC-1", summary: "Harbor" });
  m.filter("orchard"); m.merge(["ABC-2"]); m.accept({ key: "ABC-2", summary: "Orchard" });
  assert.deepEqual(m.rows(), ["ABC-2"]); assert.equal(m.current.selected, "ABC-1");
  assert.ok(m.current.unseen.has("ABC-2"));
  m.rebuildResults(); assert.deepEqual(m.rows(), ["ABC-2"]);
  assert.ok(m.current.unseen.has("ABC-2"));
  m.select("ABC-2", { read: true }); assert.equal(m.current.unseen.size, 0); assert.equal(m.readerKey(), "ABC-2");
});

test("eviction removes a browsing row and rediscovery appends a fresh identity", () => {
  const m = model(); m.merge(Array.from({ length: MAX_KEYS }, (_, i) => `ABC-${i + 1}`));
  m.select("ABC-1");
  const slot = m.resultSlots().find(slot => slot.key === "ABC-3"), id = slot.id;
  m.merge(Array.from({ length: MAX_KEYS }, (_, i) => `ABC-${i + 201}`));
  assert.ok(!m.resultSlots().some(slot => slot.id === id));
  m.merge(["ABC-3"]);
  assert.equal(m.rows().at(-1), "ABC-3");
  assert.notEqual(m.resultSlots().find(slot => slot.key === "ABC-3").id, id);
});

test("a Paused arrival batch appends in observation order without changing existing row IDs", () => {
  const m = model(); m.merge(["ABC-3", "ABC-2", "ABC-1"]); m.select("ABC-2");
  const ids = m.resultSlots().map(slot => slot.id), projection = m.current.presentation.projection;
  m.merge(["ABC-5", "ABC-4"]);
  assert.deepEqual(m.rows(), ["ABC-3", "ABC-2", "ABC-1", "ABC-4", "ABC-5"]);
  assert.deepEqual(m.resultSlots().slice(0, ids.length).map(slot => slot.id), ids);
  assert.equal(m.current.presentation.projection, projection);
  assert.deepEqual(m.current.keys, ["ABC-5", "ABC-4", "ABC-3", "ABC-2", "ABC-1"]);
  m.follow(); assert.deepEqual(m.rows(), m.current.keys); assert.equal(m.current.selected, "ABC-5");
});

test("selection leases expire across A to B to A while row identities stay stable", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2"]); m.browse();
  m.select("ABC-1", { read: true });
  const grant = m.current.readerGrant, version = m.current.presentation.projection, selection = m.current.selectionRevision;
  m.select("ABC-2", { read: true }); m.select("ABC-1");
  assert.equal(m.readerKey(), null); assert.equal(m.current.presentation.projection, version); assert.ok(m.current.selectionRevision > selection);
  assert.notEqual(m.current.readerGrant, grant);
  m.select("ABC-2", { read: true }); m.filter("ABC-1");
  assert.equal(m.readerKey(), null); assert.deepEqual(m.rows(), ["ABC-1"]);
  m.select("ABC-2", { read: true }); assert.equal(m.readerKey(), "ABC-2", "explicit outside-filter reading is allowed");
  m.leaveReader(); m.browse(); assert.equal(m.readerKey(), null, "collapsing does not revive a grant");
});

test("navigation skips unavailable slots around the selected logical position", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2", "ABC-3", "ABC-4"]);
  for (const key of m.current.keys) m.accept({ key, summary: "Orchard" });
  m.filter("orchard"); m.select("ABC-2"); m.accept({ key: "ABC-2", summary: "Harbor" });
  assert.equal(m.navigationTarget(-1), "ABC-1"); assert.equal(m.navigationTarget(1), "ABC-3");
  assert.equal(m.navigationTarget(1, 2), "ABC-4");
  m.accept({ key: "ABC-2", summary: "Orchard again" });
  assert.equal(m.current.selected, "ABC-2"); assert.equal(m.current.unseen.size, 0);
});

test("source-local browsing order survives source return and resets on clear, Follow, and source eviction", () => {
  const m = model(); m.merge(["ABC-1"]); m.filter("ABC");
  const original = m.current.presentation;
  m.useSource("t2"); m.merge(["ABC-2"]); m.filter("ABC");
  m.useSource("t1"); assert.equal(m.current.presentation, original);
  m.clearList(); assert.notEqual(m.current.presentation, original); assert.deepEqual(m.resultSlots(), []);
  m.follow(); assert.equal(m.current.presentation, null);
  for (let i = 3; i <= MAX_SOURCES + 3; i++) { m.useSource(`t${i}`); m.merge([`ABC-${i}`]); m.browse(); }
  assert.equal(m.sources.size, MAX_SOURCES); assert.equal(m.sources.has("t1"), false);
});

test("screen discovery settles complete exact keys without retaining a streamed prefix", () => {
  const m = model();
  assert.equal(m.observeScreen("Working on ABC-24", 0).confirm, true);
  assert.equal(m.observeScreen("Working on ABC-2456", 100).confirm, true);
  m.observeScreen("Working on ABC-2456", 349);
  assert.deepEqual(m.current.keys, []);
  m.observeScreen("Working on ABC-2456", 350);
  assert.deepEqual(m.current.keys, ["ABC-2456"]);
  m.observeScreen("ABC-24 ABC-2456", 400);
  m.observeScreen("ABC-24 ABC-2456", 650);
  assert.deepEqual(m.current.keys, ["ABC-24", "ABC-2456"]);
  m.observeScreen("ABC-24", 651);
  assert.equal(m.current.selected, "ABC-24", "known keys are immediately usable");
});

test("clear waits for a fresh baseline and preserves Follow or Paused on fresh arrivals", () => {
  for (const follow of [true, false]) {
    const m = model(); m.merge(["ABC-1"]); m.current.follow = follow;
    const old = m.current; m.current.pinnedIssueKey = "ABC-1";
    m.clearList();
    assert.notEqual(m.current, old); assert.equal(m.current.follow, follow);
    assert.equal(m.current.pinnedIssueKey, null);
    m.observeScreen("ABC-1", 0); m.observeScreen("ABC-1", 250);
    assert.deepEqual(m.current.keys, []);
    m.observeScreen("ABC-1 ABC-2", 500); m.observeScreen("ABC-1 ABC-2", 750);
    assert.deepEqual(m.current.keys, ["ABC-2"]);
    assert.equal(m.current.selected, follow ? "ABC-2" : null);
    assert.deepEqual([...m.current.unseen], follow ? [] : ["ABC-2"]);
    m.observeScreen("ABC-2", 1000);
    m.observeScreen("ABC-1 ABC-2", 1250); m.observeScreen("ABC-1 ABC-2", 1500);
    assert.ok(m.current.keys.includes("ABC-1"), "an absent key can be rediscovered");
  }
});

test("suppression uses full presence evidence despite candidate-window churn and oversized reads", () => {
  const m = model(); m.merge(["ABC-1"]); m.clearList(); m.observeScreen("ABC-1", 0);
  const many = Array.from({ length: 201 }, (_, i) => `ABC-${i + 2}`).join(" ");
  m.observeScreen(`ABC-1 ${many}`, 250); m.observeScreen(`ABC-1 ${many}`, 500);
  assert.ok(m.current.suppressed.has("ABC-1"));
  m.observeScreen("x".repeat(200001), 750);
  assert.ok(m.current.suppressed.has("ABC-1"), "truncation cannot establish absence");
  m.observeScreen("ABC-1", 1000); m.observeScreen("ABC-1", 1250);
  assert.ok(!m.current.keys.includes("ABC-1"));
  m.clearList(); m.observeScreen(many, 1500);
  assert.equal(m.current.baselinePending, true); assert.equal(m.current.screenLimited, true);
  assert.deepEqual(m.current.keys, []);
  m.observeScreen("ABC-1", 1750);
  assert.equal(m.current.baselinePending, false);
});

test("history does not confirm screen candidates or change a clear baseline", () => {
  const m = model(); m.observeScreen("ABC-24", 0);
  m.merge(["ABC-3"]); // Explicit history remains immediately usable.
  m.observeScreen("ABC-2456", 300);
  assert.deepEqual(m.current.keys, ["ABC-3"]);
  m.observeScreen("ABC-2456", 550);
  assert.deepEqual(m.current.keys, ["ABC-2456", "ABC-3"]);
  m.clearList(); m.observeScreen("ABC-3", 750);
  m.merge(["ABC-4"]);
  assert.ok(m.current.suppressed.has("ABC-3"));
  m.observeScreen("ABC-3", 1000, { bypass: true });
  m.observeScreen("ABC-3", 1250, { bypass: true });
  assert.ok(m.current.keys.includes("ABC-3"), "deliberate screen scans may restore a cleared key");
});

test("effective URL matches share strict origin validation with direct lookup", () => {
  const m = model(); m.merge(["ABC-1", "ABC-12"]);
  m.metadata.set("ABC-12", { summary: "https://foreign.example.test/browse/ABC-1" });
  m.filter("https://jira.example.test/browse/ABC-1?view=reader#body");
  assert.deepEqual(m.rows(), ["ABC-1"]);
  m.filter("https://foreign.example.test/browse/ABC-1"); assert.deepEqual(m.rows(), []);
  m.filter("https://jira.example.test/browse/ABC-99"); assert.deepEqual(m.rows(), []);
  m.filter(" abc-1 "); assert.deepEqual(m.rows(), ["ABC-1", "ABC-12"]);
});

test("metadata projections remain newer after body eviction, and stale ownership cannot downgrade them", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2"]);
  const old = {}; m.beginMetadata(old, ["ABC-1", "ABC-2"]);
  m.accept({ key: "ABC-1", summary: "Orchard paths", status: "Ready" }); m.details.delete("ABC-1");
  assert.deepEqual(m.settleMetadata(old, [{ key: "ABC-1", summary: "Old title" }]), ["ABC-2"]);
  m.releaseMetadata(old);
  assert.equal(m.metadata.get("ABC-1").summary, "Orchard paths");
  assert.equal(m.rowStates.get("ABC-1").status, "ready");
  assert.equal(m.rowPlaceholder("ABC-2"), "Title unavailable");
  m.filter("orchard"); assert.deepEqual(m.rows(), ["ABC-1"]);
  const revision = m.rowStates.get("ABC-1").revision;
  m.clearList(); m.merge(["ABC-1"]);
  assert.ok(m.rowStates.get("ABC-1").revision > revision);
  const newer = {}; m.beginMetadata(newer, ["ABC-1"]); m.releaseMetadata(old);
  assert.equal(m.rowStates.get("ABC-1").owner, newer);
  m.releaseMetadata(newer);
  assert.equal(m.metadataAttempts.has("ABC-1"), false);
});

test("passive extraction uses allowlists, complete tokens, and last occurrence", () => {
  assert.deepEqual(extractKeys("ABC-1 DEF-2 ABC-1 NOPE-3 _ABC-4 ABC-5x ABC-6_", config.projects), ["ABC-1", "DEF-2"]);
  assert.deepEqual(extractKeys("界 ABC-12\nhttps://jira.example.test/browse/DEF-9?x=1", config.projects), ["DEF-9", "ABC-12"]);
});

test("source identity includes the machine and shown terminal", () => {
  const live = [{ address: "t1" }, { address: "remote/t1" }];
  assert.equal(focusedSource({ terminal: "t1", shown: "remote/t1" }, live), "remote/t1");
  assert.equal(focusedSource({ terminal: "t1" }, live), "t1");
  assert.equal(focusedSource({ terminal: "other/t1" }, live), null);
  assert.equal(focusedSource({ terminal: "--all" }, [{ address: "--all" }]), null);
  assert.equal(focusedSource(null, live), null);
});

test("Follow selects new keys; Browse keeps selection, query, and unseen count", () => {
  const m = model(); m.merge(["ABC-1"]); m.merge(["ABC-2", "ABC-1"]);
  assert.equal(m.current.selected, "ABC-2");
  m.select("ABC-1"); m.filter("a summary"); m.merge(["ABC-3"]);
  assert.equal(m.current.selected, "ABC-1"); assert.equal(m.current.query, "a summary");
  assert.deepEqual([...m.current.unseen], ["ABC-3"]);
  assert.equal(m.merge(["ABC-3"]), false);
  m.follow(); assert.equal(m.current.selected, "ABC-3"); assert.equal(m.current.query, "");
  assert.equal(m.current.unseen.size, 0);
});

test("Follow selects the latest visible key when a changed snapshot contains only known keys", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  assert.equal(m.current.selected, "ABC-2");
  assert.equal(m.merge(["ABC-1", "ABC-2"]), true);
  assert.equal(m.current.selected, "ABC-1");
  assert.deepEqual(m.current.keys, ["ABC-2", "ABC-1"]);
  assert.equal(m.current.unseen.size, 0);
  assert.equal(m.merge(["ABC-1", "ABC-2"]), false);
});

test("resuming Follow selects the latest observation after browsing without losing its reading target", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  m.select("ABC-2"); m.filter("keep");
  m.merge(["ABC-1", "ABC-2"]);
  assert.equal(m.current.selected, "ABC-2");
  assert.equal(m.current.query, "keep");
  assert.deepEqual(m.current.keys, ["ABC-2", "ABC-1"]);
  m.follow();
  assert.equal(m.current.selected, "ABC-1");
  assert.equal(m.current.query, "");
});

test("empty and unchanged snapshots preserve the latest Follow target", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  assert.equal(m.merge([]), false);
  assert.equal(m.current.selected, "ABC-2");
  assert.equal(m.current.latestObserved, "ABC-2");
  assert.equal(m.merge(["ABC-1", "ABC-2"]), true);
  assert.equal(m.current.selected, "ABC-1");
  assert.equal(m.merge(["ABC-1", "ABC-2"]), false);
  assert.equal(m.current.selected, "ABC-1");
});

test("latest observed key is isolated by source", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  m.useSource("remote/t1"); m.follow(); m.merge(["DEF-9"]);
  m.useSource("t1");
  m.follow();
  assert.equal(m.current.selected, "ABC-2");
  m.merge(["ABC-1", "ABC-2"]);
  m.useSource("remote/t1");
  assert.equal(m.current.selected, "DEF-9");
});

test("Follow retains a known latest key at the MAX_KEYS boundary", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  m.merge(["ABC-1", "ABC-2"]);
  const fresh = Array.from({ length: MAX_KEYS - 1 }, (_, i) => `ABC-${1000 + i}`);
  m.merge(["ABC-1", ...fresh]);
  assert.equal(m.current.keys.length, MAX_KEYS);
  assert.ok(m.current.keys.includes("ABC-1"));
  assert.equal(m.current.selected, "ABC-1");
});

test("Browse retention preserves both its reading selection and latest key for resume", () => {
  const m = model(); m.merge(["ABC-2", "ABC-1"]);
  m.merge(["ABC-1", "ABC-2"]);
  m.select("ABC-2");
  const fresh = Array.from({ length: MAX_KEYS - 1 }, (_, i) => `ABC-${1000 + i}`);
  m.merge(["ABC-1", ...fresh]);
  assert.equal(m.current.keys.length, MAX_KEYS);
  assert.ok(m.current.keys.includes("ABC-1"));
  assert.ok(m.current.keys.includes("ABC-2"));
  assert.equal(m.current.selected, "ABC-2");
  m.follow();
  assert.equal(m.current.selected, "ABC-1");
});

test("switching terminals retains each reading session and never mixes keys", () => {
  const m = model(); m.merge(["ABC-1"]); m.filter("one");
  m.useSource("remote/t1"); m.follow(); m.merge(["DEF-9"]);
  assert.deepEqual(m.current.keys, ["DEF-9"]);
  m.useSource("t1"); assert.deepEqual(m.current.keys, ["ABC-1"]); assert.equal(m.current.query, "one");
});

test("a bounded list keeps the reading selection and avoids repeating identical scans", () => {
  const m = model(); m.merge(["ABC-1"]); m.select("ABC-1");
  const keys = Array.from({ length: MAX_KEYS }, (_, i) => `ABC-${i + 2}`);
  m.merge(keys); assert.equal(m.current.keys.length, MAX_KEYS); assert.ok(m.current.keys.includes("ABC-1"));
  assert.equal(m.merge(keys), false);
  for (let i = 0; i < MAX_SOURCES + 4; i++) m.useSource(`t${i + 2}`);
  assert.equal(m.sources.size, MAX_SOURCES);
});

test("metadata filtering uses every search word and loaded custom values", () => {
  const m = model(); m.merge(["ABC-1", "DEF-2"]);
  m.metadata.set("ABC-1", { summary: "Keep filters", status: "In Progress", values: ["Alex Example"] });
  m.filter("filters alex"); assert.deepEqual(m.rows(), ["ABC-1"]);
  m.filter("filters done"); assert.deepEqual(m.rows(), []);
});

test("detail eviction drops full bodies while keeping searchable rows, then source eviction drops rows", () => {
  const m = model();
  const keys = Array.from({ length: 41 }, (_, i) => `ABC-${i + 1}`);
  m.merge(keys);
  for (const key of keys) m.accept({ key, summary: "Fictional issue", status: "Open",
    values: ["Alex Example"], description: "Private body fixture", comments: [{ body: "Private comment fixture" }] });
  assert.equal(m.details.size, 40); assert.equal(m.details.has("ABC-1"), false);
  assert.deepEqual(Object.keys(m.metadata.get("ABC-1")).sort(), ["key", "status", "summary", "values"]);
  m.filter("alex"); assert.equal(m.rows().length, 41);
  for (let i = 0; i < MAX_SOURCES; i++) m.useSource(`new-${i}`);
  assert.equal(m.details.size, 0); assert.equal(m.metadata.size, 0);
});

test("expired detail is refetched on selection; zero TTL has no timed refetch loop", () => {
  const m = model(); m.merge(["ABC-1"]); m.accept({ key: "ABC-1" }, 100);
  assert.ok(m.detail("ABC-1", 1000)); assert.equal(m.detail("ABC-1", 600101), null);
  m.config = { ...config, ttl: 0 }; assert.ok(m.detail("ABC-1", 600101));
});

test("disk cache loading does not restart the original freshness window", () => {
  const m = model(); m.merge(["ABC-1"]);
  m.accept({ key: "ABC-1", fetchedAt: 1000 }, 541000);
  assert.ok(m.detail("ABC-1", 550000));
  assert.equal(m.detail("ABC-1", 901000), null);
  assert.ok(m.details.get("ABC-1"), "stale content remains visible during refresh");
  m.accept({ key: "ABC-1", fetchedAt: null }, 901000);
  assert.ok(m.detail("ABC-1", 902000));
});

test("TTL zero retires bodies on every logical selection path while retaining rows, pins and unread state", () => {
  const m = model(); m.config = { ...m.config, ttl: 0 };
  m.merge(["ABC-1"]); m.accept({ key: "ABC-1", summary: "Fictional first" });
  m.merge(["ABC-2"]);
  assert.equal(m.current.selected, "ABC-2"); assert.equal(m.details.has("ABC-1"), false);
  assert.equal(m.metadata.get("ABC-1").summary, "Fictional first");
  m.accept({ key: "ABC-2" }); m.select("ABC-1");
  assert.equal(m.details.has("ABC-2"), false);
  m.accept({ key: "ABC-1", summary: "Fictional reloaded" }); m.toggleIssuePin("ABC-1");
  m.merge(["ABC-3"]);
  assert.ok(m.details.has("ABC-1")); assert.ok(m.current.unseen.has("ABC-3"));
  m.follow();
  assert.equal(m.current.selected, "ABC-3"); assert.equal(m.details.has("ABC-1"), false);
  assert.equal(m.current.pinnedIssueKey, "ABC-1");
  m.accept({ key: "ABC-1", description: "Fictional late body" });
  assert.equal(m.details.has("ABC-1"), false); assert.ok(m.metadata.has("ABC-1"));
});

test("TTL zero preserves logical selection through filtering and same-key source adoption, but clears other identities", () => {
  const m = model(); m.config = { ...m.config, ttl: 0 };
  m.merge(["ABC-1"]); m.useSource("other"); m.merge(["ABC-1"]);
  m.accept({ key: "ABC-1", summary: "Fictional shared issue" }); const body = m.details.get("ABC-1");
  m.useSource("t1"); assert.equal(m.details.get("ABC-1"), body);
  m.filter("no matching text"); assert.deepEqual(m.rows(), []); assert.equal(m.details.get("ABC-1"), body);
  m.filter(""); assert.equal(m.details.get("ABC-1"), body);
  m.useSource("new-source"); assert.equal(m.details.size, 0);
  m.merge(["ABC-1"]); m.accept({ key: "ABC-1" }); m.clearList();
  assert.equal(m.details.size, 0); m.merge(["ABC-1"]); assert.equal(m.details.size, 0);
  m.accept({ key: "ABC-1" }); m.reset({ ...m.config, context: "new-context" });
  m.useSource("t1"); m.merge(["ABC-1"]); assert.equal(m.details.size, 0);
});

test("connection changes drop every issue, source, failure, and pending metadata key", () => {
  const m = model(); m.merge(["ABC-1"]); m.accept({ key: "ABC-1" });
  m.failures.add("ABC-1"); m.metadataAttempts.add("ABC-1"); m.pinned = true;
  const generation = m.generation; m.reset({ ...config, context: "two" });
  assert.ok(m.generation > generation); assert.equal(m.source, null); assert.equal(m.details.size, 0);
  assert.equal(m.metadata.size, 0); assert.equal(m.sources.size, 0); assert.equal(m.pinned, false);
  assert.equal(m.failures.size, 0); assert.equal(m.metadataAttempts.size, 0);
});

test("browser links are built only from the configured HTTPS origin and a valid key", () => {
  assert.equal(issueLink(config.base, "ABC-1", config.projects), `${config.base}/browse/ABC-1`);
  assert.equal(issueLink(config.base, "https://jira.example.test/browse/ABC-1?filter=mine#top", config.projects), `${config.base}/browse/ABC-1`);
  assert.equal(parseIssueKey(config.base, "https://jira.example.test/browse/ABC-1?filter=mine#top", config.projects), "ABC-1");
  for (const key of ["NOPE-1", "ABC-1/other", "ABC-1?x=1", "$(ABC-1)"]) assert.equal(issueLink(config.base, key, config.projects), null);
  for (const origin of ["javascript:alert(1)", "http://jira.example.test", "https://user@jira.example.test/browse/ABC-1", "https://other.example.test/browse/ABC-1", "https://jira.example.test/other/ABC-1", "https://jira.example.test/browse/ABC-1/extra"]) {
    assert.equal(issueLink(origin, "ABC-1", config.projects), null);
  }
  assert.equal(issueLink(config.base, "https://jira.example.test/browse/NOPE-1", config.projects), null);
  assert.equal(parseIssueKey(config.base, "https://user@jira.example.test/browse/ABC-1", config.projects), null);
});

test("detail freshness keeps the fetched payload time and falls back only when absent", () => {
  const m = model(); m.merge(["ABC-1"]);
  m.accept({ key: "ABC-1", fetchedAt: 1234 }, 9000);
  assert.equal(m.detail("ABC-1", 9000).fetchedAt, 1234);
  assert.equal(m.detail("ABC-1", 9000).loadedAt, 9000);
  m.accept({ key: "ABC-1" }, 12000);
  assert.equal(m.detail("ABC-1", 12000).fetchedAt, 12000);
});

test("only explicit UI preferences restore, with Live off by default", () => {
  assert.deepEqual(uiPreferences(null), { live: false, readerFocus: false, highlightSource: true });
  assert.deepEqual(uiPreferences("not json"), { live: false, readerFocus: false, highlightSource: true });
  assert.deepEqual(uiPreferences('{"live":true,"readerFocus":true,"issue":"ABC-1","query":"secret fixture"}'),
    { live: true, readerFocus: true, highlightSource: true });
});

test("source highlighting defaults on and restores only an explicit boolean false", () => {
  for (const value of [null, {}, [], "false", 0, true]) {
    assert.equal(uiPreferences(JSON.stringify({highlightSource: value})).highlightSource, true);
  }
  assert.equal(uiPreferences('{"highlightSource":false}').highlightSource, false);
});


test("issue pins survive detours and arrivals without changing the viewed action target", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2"]);
  assert.equal(m.toggleIssuePin("ABC-1"), true);
  m.select("ABC-2"); m.filter("retained filter"); m.merge(["ABC-3"]);
  assert.equal(m.current.pinnedIssueKey, "ABC-1");
  assert.equal(m.current.selected, "ABC-2");
  assert.equal(m.current.query, "retained filter");
  assert.deepEqual([...m.current.unseen], ["ABC-3"]);
  m.follow(); assert.equal(m.current.selected, "ABC-3");
  assert.equal(m.current.pinnedIssueKey, "ABC-1");
  m.toggleIssuePin("ABC-1"); assert.equal(m.current.pinnedIssueKey, null);
  assert.equal(m.current.selected, "ABC-3");
});

test("pinned issue, paused selection and latest observation coexist within key and detail bounds", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2"]); m.toggleIssuePin("ABC-1"); m.select("ABC-2");
  const arrivals = Array.from({length: MAX_KEYS}, (_, i) => `ABC-${i + 1000}`);
  m.merge(arrivals);
  assert.equal(m.current.keys.length, MAX_KEYS);
  for (const key of ["ABC-1", "ABC-2", "ABC-1000"]) assert.ok(m.current.keys.includes(key));
  assert.equal(m.current.selected, "ABC-2");
  m.accept({key: "ABC-1", summary: "Fictional pinned issue"});
  for (const key of arrivals.slice(0, 41)) m.accept({key, summary: "Fictional issue"});
  assert.equal(m.details.size, 40); assert.equal(m.details.has("ABC-1"), false);
  assert.equal(m.current.pinnedIssueKey, "ABC-1", "retain only the key, never pin its body");
  m.follow(); assert.equal(m.current.selected, "ABC-1000");
});

test("issue pins are isolated by exact source and discarded on eviction and connection reset", () => {
  const m = model(); m.merge(["ABC-1"]); m.toggleIssuePin("ABC-1");
  m.useSource("remote/t1"); m.merge(["DEF-2"]); assert.equal(m.current.pinnedIssueKey, null);
  m.toggleIssuePin("DEF-2"); m.useSource("t1"); assert.equal(m.current.pinnedIssueKey, "ABC-1");
  m.useSource("manual"); m.merge(["ABC-3"]); assert.equal(m.toggleIssuePin("ABC-3"), false);
  assert.equal(m.toggleIssuePin("NOPE-99"), false);
  for (let i = 0; i < MAX_SOURCES; i++) m.useSource(`source-${i}`);
  assert.equal(m.sources.size, MAX_SOURCES); assert.equal(m.sources.has("t1"), false);
  m.useSource("t1"); assert.equal(m.current.pinnedIssueKey, null);
  m.merge(["ABC-1"]); m.toggleIssuePin("ABC-1"); m.reset({...config, context:"two"});
  m.useSource("t1"); assert.equal(m.current.pinnedIssueKey, null);
});


test("matching pin leads stable results across filters, arrivals, selection and source switches", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2", "ABC-3"]);
  for (const key of m.current.keys) m.accept({key, summary: "Orchard " + key});
  m.filter("orchard"); const original = m.rows();
  m.select("ABC-3"); m.toggleIssuePin("ABC-3");
  assert.deepEqual(m.rows(), ["ABC-3", "ABC-1", "ABC-2"]);
  m.select("ABC-1"); assert.equal(m.navigationTarget(-1), "ABC-3");
  m.merge(["ABC-4"]); m.accept({key: "ABC-4", summary: "Orchard arrival"});
  assert.deepEqual(m.rows(), ["ABC-3", "ABC-1", "ABC-2", "ABC-4"]);
  assert.equal(m.current.selected, "ABC-1"); assert.ok(m.current.unseen.has("ABC-4"));
  m.filter("ABC-2"); assert.deepEqual(m.rows(), ["ABC-2"]); assert.equal(m.current.pinnedIssueKey, "ABC-3");
  m.filter("orchard"); assert.equal(m.rows()[0], "ABC-3");
  m.useSource("t2"); m.merge(["DEF-1", "DEF-2"]); m.select("DEF-2"); m.toggleIssuePin("DEF-2");
  assert.equal(m.rows()[0], "DEF-2"); m.useSource("t1"); assert.equal(m.rows()[0], "ABC-3");
  m.toggleIssuePin("ABC-3"); assert.deepEqual(m.rows(), ["ABC-4", ...original]);
});

test("a pinned issue moves to the front when metadata starts matching and returns to its anchor when it stops", () => {
  const m = model(); m.merge(["ABC-1", "ABC-2", "ABC-3"]);
  for (const key of m.current.keys) m.accept({key, summary: "Orchard"});
  m.filter("orchard"); m.select("ABC-3"); m.toggleIssuePin("ABC-3"); m.select("ABC-1");
  m.accept({key: "ABC-3", summary: "Harbor"});
  assert.deepEqual(m.rows(), ["ABC-1", "ABC-2"]);
  assert.equal(m.current.pinnedIssueKey, "ABC-3"); assert.equal(m.current.selected, "ABC-1");
  m.accept({key: "ABC-3", summary: "Orchard again"});
  assert.deepEqual(m.rows(), ["ABC-3", "ABC-1", "ABC-2"]);
  m.select("ABC-2"); m.toggleIssuePin("ABC-2");
  assert.deepEqual(m.rows(), ["ABC-2", "ABC-1", "ABC-3"]);
  assert.equal(m.current.selected, "ABC-2");
});
