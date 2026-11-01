import test from "node:test";
import assert from "node:assert/strict";
import { PeekModel, extractKeys, focusedSource, issueLink, parseIssueKey, uiPreferences, MAX_KEYS, MAX_SOURCES } from "../mods/jira-peek/model.js";

const config = { projects: ["ABC", "DEF"], base: "https://jira.example.test", ttl: 10, limit: 20, context: "one" };
function model() { const m = new PeekModel(); m.reset(config); m.useSource("t1"); return m; }

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
  m.useSource("remote/t1"); m.merge(["DEF-9"]);
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
  m.useSource("remote/t1"); m.merge(["DEF-9"]);
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
