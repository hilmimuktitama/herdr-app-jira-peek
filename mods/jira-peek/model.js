// Pure state: no terminal control, credentials, disk storage, or network access.
export const MAX_KEYS = 200;
export const MAX_SOURCES = 12;
export const SCREEN_LIMIT = 200000;
export const KEY_SETTLE_MS = 250;

export function descriptionPreview(value, options = {}) {
  const bound = (value, fallback) => Number.isSafeInteger(value) && value > 0 ? value : fallback;
  const maxChars = bound(options?.maxChars, 560);
  const maxLines = bound(options?.maxLines, 7);
  const original = value == null ? "" : String(value);
  const text = original.replace(/\r\n?/g, "\n").trim();
  const lines = text.split("\n");
  const limited = lines.slice(0, maxLines).join("\n");
  const chars = Array.from(limited);
  if (lines.length <= maxLines && chars.length <= maxChars) return { text, truncated: false };

  const prefix = chars.slice(0, Math.max(0, maxChars - 1)).join("");
  let preview = prefix.trimEnd();
  if (chars.length >= maxChars && preview && prefix === preview && !/\s/u.test(chars[maxChars - 1])) {
    const boundary = preview.search(/\s+\S*$/u);
    if (boundary >= 0 && Array.from(preview.slice(0, boundary)).length >= Array.from(preview).length / 2) {
      preview = preview.slice(0, boundary).trimEnd();
    }
  }
  return { text: `${preview.replace(/…+$/u, "")}…`, truncated: true };
}

export function displayDate(value) {
  if (value == null) return "";
  if (typeof value !== "string") return String(value);
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2}))?$/.exec(value);
  if (!match) return value;
  const [, year, month, day, hour, minute, second, zone] = match;
  const y = Number(year), m = Number(month), d = Number(day);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (m < 1 || m > 12 || d < 1 || d > days[m - 1] ||
      (hour !== undefined && (+hour > 23 || +minute > 59 || +(second || 0) > 59)) ||
      (zone && zone !== "Z" && (+zone.slice(1, 3) > 23 || +zone.slice(-2) > 59))) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${String(date.getUTCDate()).padStart(2, "0")} ${months[date.getUTCMonth()]} ${String(date.getUTCFullYear()).padStart(4, "0")}`;
}

export function focusedSource(focus, live) {
  const address = focus?.shown || focus?.terminal || focus?.agent;
  return typeof address === "string" && !address.startsWith("-") &&
    !/[\x00-\x20\x7f]/.test(address) && live.some(t => t.address === address)
    ? address : null;
}

export function extractKeys(text, projects) {
  const allowed = new Set(projects);
  const matches = String(text).match(/\b[A-Z][A-Z0-9_]*-[0-9]+\b/g) || [];
  const seen = new Set(), keys = [];
  for (let i = matches.length - 1; i >= 0 && keys.length < MAX_KEYS; i--) {
    const key = matches[i];
    if (allowed.has(key.slice(0, key.lastIndexOf("-"))) && !seen.has(key)) {
      seen.add(key); keys.push(key);
    }
  }
  return keys;
}

export function parseIssueKey(base, input, projects) {
  if (!/^https:\/\/[A-Za-z0-9.[\]:-]+$/.test(base)) return null;
  const allowed = new Set(projects);
  const validKey = value => /^[A-Z][A-Z0-9_]*-[0-9]+$/.test(value) &&
    allowed.has(value.slice(0, value.lastIndexOf("-")));
  if (typeof input !== "string") return null;
  const key = input.trim();
  if (validKey(key)) return key;
  if (!key.startsWith("https://")) return null;
  try {
    const configured = new URL(base), supplied = new URL(key);
    if (configured.origin !== supplied.origin || supplied.username || supplied.password ||
        supplied.pathname.split("/").length !== 3 || !supplied.pathname.startsWith("/browse/")) return null;
    const issueKey = supplied.pathname.slice("/browse/".length);
    return validKey(issueKey) ? issueKey : null;
  } catch { return null; }
}

export function issueLink(base, input, projects) {
  const key = parseIssueKey(base, input, projects);
  return key ? `${base}/browse/${key}` : null;
}

export function statusColor(status, t) {
  if (/done|closed|resolved/i.test(status)) return t.done;
  if (/block|hold/i.test(status)) return t.blocked;
  if (/progress|review|testing/i.test(status)) return t.working;
  return t.muted;
}

export function uiPreferences(serialized) {
  try {
    const saved = JSON.parse(serialized || "{}");
    return { live: saved.live === true, readerFocus: saved.readerFocus === true, highlightSource: saved.highlightSource !== false };
  } catch { return { live: false, readerFocus: false, highlightSource: true }; }
}

export function readerPreferences(file) {
  return { live: file.preferences?.autoRefresh === true, highlightSource: file.preferences?.highlightSource !== false };
}

export const FIELD_NAMES = {
  summary: "Summary", status: "Status", assignee: "Assignee", reporter: "Reporter",
  priority: "Priority", issuetype: "Type", project: "Project", created: "Created",
  updated: "Updated", duedate: "Due date", resolution: "Resolution", labels: "Labels",
  components: "Components", fixVersions: "Fix versions", versions: "Affects versions",
  parent: "Parent", description: "Description", comments: "Comments",
};
export const FIELD_SECTIONS = ["header", "body", "details", "hidden"];
export const MAX_LAYOUT_FIELDS = 32;
export const validFieldId = id => typeof id === "string" &&
  (Object.hasOwn(FIELD_NAMES, id) || /^customfield_[0-9]{1,12}$/.test(id));

export function defaultFieldLayout(config) {
  const configured = config?.fields || ["summary", "status", "assignee", "updated", "description", "comments"].map(id => ({ id }));
  const seen = new Set();
  return { version: 1, showEmpty: false, fields: [{ id: "summary", label: configured.find(field => field.id === "summary")?.label }, ...configured]
    .filter(field => validFieldId(field?.id) && !seen.has(field.id) && seen.add(field.id))
    .slice(0, MAX_LAYOUT_FIELDS).map(({ id, label }) => ({
      id, label: cleanFieldLabel(label) || FIELD_NAMES[id] || id,
      section: id === "status" ? "header" : ["summary", "description", "comments"].includes(id) ? "body" : "details",
    })) };
}

export function cleanFieldLabel(label) {
  return typeof label === "string" ? label.replace(/[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]/g, "").trim().slice(0, 80) : "";
}

export function readFieldLayout(serialized, config) {
  try {
    const saved = typeof serialized === "string" ? JSON.parse(serialized) : serialized;
    if (saved?.version !== 1 || !Array.isArray(saved.fields) || saved.fields.length > MAX_LAYOUT_FIELDS) throw new Error("invalid layout");
    const seen = new Set();
    const fields = saved.fields.map(field => {
      if (!validFieldId(field?.id) || seen.has(field.id) || !FIELD_SECTIONS.includes(field.section) ||
          (field.id === "comments" && field.section === "header")) throw new Error("invalid field");
      seen.add(field.id);
      return { id: field.id, label: cleanFieldLabel(field.label) || FIELD_NAMES[field.id] || field.id, section: field.section };
    });
    return { version: 1, showEmpty: saved.showEmpty === true, fields };
  } catch { return defaultFieldLayout(config); }
}

// The shared file is deliberately stricter than legacy UI preferences: a typo
// must not silently replace a working layout with defaults.
export function parseFieldFile(text) {
  if (text === null) return { version: 1, connections: [] };
  const file = JSON.parse(text);
  const keysOnly = (object, keys) => object && typeof object === "object" && !Array.isArray(object) && Object.keys(object).every(key => keys.includes(key));
  if (!keysOnly(file, ["$schema", "version", "preferences", "connections"]) || file.version !== 1 || !Array.isArray(file.connections) ||
      (file.$schema !== undefined && typeof file.$schema !== "string")) throw new Error("Invalid field configuration");
  if (file.preferences !== undefined && (!keysOnly(file.preferences, ["autoRefresh", "highlightSource"]) ||
      Object.values(file.preferences).some(value => typeof value !== "boolean"))) throw new Error("Invalid reader preferences");
  const seen = new Set();
  for (const connection of file.connections) {
    if (!keysOnly(connection, ["configDir", "base", "showEmpty", "fields"]) ||
        typeof connection.configDir !== "string" || !connection.configDir.startsWith("/") || /[\x00-\x1f]/.test(connection.configDir) ||
        typeof connection.base !== "string" || !/^https:\/\/[A-Za-z0-9.[\]:-]+$/.test(connection.base) ||
        (connection.showEmpty !== undefined && typeof connection.showEmpty !== "boolean") ||
        !Array.isArray(connection.fields) || connection.fields.length > MAX_LAYOUT_FIELDS) throw new Error("Invalid connection layout");
    const identity = JSON.stringify([connection.configDir, connection.base]), ids = new Set();
    if (seen.has(identity)) throw new Error("Duplicate connection layout");
    seen.add(identity);
    for (const field of connection.fields) {
      if (!keysOnly(field, ["id", "label", "section"]) || !validFieldId(field.id) || ids.has(field.id) ||
          !FIELD_SECTIONS.includes(field.section) || (field.id === "comments" && field.section === "header") ||
          (field.label !== undefined && (typeof field.label !== "string" || field.label.length > 80 || cleanFieldLabel(field.label) !== field.label))) throw new Error("Invalid field entry");
      ids.add(field.id);
    }
  }
  return file;
}

export function connectionFieldLayout(file, configDir, base) {
  const entry = file.connections.find(item => item.configDir === configDir && item.base === base);
  return entry ? readFieldLayout({ version: 1, showEmpty: entry.showEmpty, fields: entry.fields }) : null;
}

export function updateFieldFile(file, configDir, base, layout) {
  const entry = { configDir, base, showEmpty: layout.showEmpty, fields: layout.fields };
  const connections = file.connections.filter(item => item.configDir !== configDir || item.base !== base);
  return { $schema: "../../mods/jira-peek/fields.schema.json", ...file, connections: [...connections, entry] };
}

export function requestedReaderFields(layout) {
  return layout.fields.filter(field => field.section !== "hidden" && field.id !== "summary").map(field => field.id).sort().join(",");
}

export function placedFields(issue, layout) {
  const regions = { header: [], body: [], details: [] };
  for (const field of layout.fields) {
    if (field.section === "hidden") continue;
    const metadata = issue?.metadata?.find(item => item.id === field.id);
    const value = ["summary", "status", "description"].includes(field.id) ? issue?.[field.id] : metadata?.value;
    const empty = value === null || value === undefined || (typeof value === "string" && value.trim() === "");
    if (field.id !== "comments" && empty && !layout.showEmpty) continue;
    regions[field.section].push({ ...field, value: empty ? "—" : String(value).trimEnd(),
      unsupportedContent: metadata?.unsupportedContent === true, truncated: metadata?.truncated === true });
  }
  return regions;
}

export class PeekModel {
  constructor() { this.generation = 0; this.reset(); }

  reset(config = null) {
    this.generation++;
    this.config = config;
    this.sources = new Map();
    this.details = new Map();
    this.metadata = new Map();
    this.failures = new Set();
    this.denied = new Set();
    this.metadataAttempts = new Set();
    this.rowStates = new Map();
    this.projectionRevision = 0;
    this.source = null;
    this.sourceRevision = 0;
    this.pinned = false;
    this.retryAfter = 0;
  }

  get current() { return this.sources.get(this.source); }

  newSource(follow = true) {
    return {
      keys: [], selected: null, query: "", follow, pinnedIssueKey: null,
      unseen: new Set(), snapshot: "", latestObserved: null, error: null,
      candidates: new Map(), suppressed: new Set(), baselinePending: false,
      screenLimited: false,
      cleared: false,
    };
  }

  useSource(address) {
    if (address === this.source) return false;
    this.current?.candidates.clear();
    this.source = address;
    this.sourceRevision++;
    if (address && !this.sources.has(address)) {
      this.sources.set(address, this.newSource());
    }
    if (address) {
      const state = this.current;
      this.sources.delete(address); this.sources.set(address, state);
    }
    while (this.sources.size > MAX_SOURCES) this.sources.delete(this.sources.keys().next().value);
    this.prune();
    return true;
  }

  clearList() {
    if (!this.current || this.source === "manual") return null;
    const state = this.newSource(this.current.follow);
    state.baselinePending = true;
    state.cleared = true;
    this.sources.set(this.source, state);
    this.sourceRevision++;
    this.prune();
    return state;
  }

  observeScreen(text, now, { bypass = false, truncated = false } = {}) {
    const s = this.current;
    if (!s) return { changed: false, confirm: false };
    text = String(text);
    s.screenLimited = truncated || text.length > SCREEN_LIMIT;
    if (s.screenLimited) return { changed: false, confirm: false };

    // Presence is checked over the whole bounded screen, independently of the
    // last-200 admission window. Never mistake window eviction for absence.
    const allowed = new Set(this.config.projects), baseline = new Set(), present = new Set();
    for (const [key] of text.matchAll(/\b[A-Z][A-Z0-9_]*-[0-9]+\b/g)) {
      if (!allowed.has(key.slice(0, key.lastIndexOf("-")))) continue;
      if (baseline.size <= MAX_KEYS) baseline.add(key);
      if (s.suppressed.has(key)) present.add(key);
    }
    if (s.baselinePending && !bypass) {
      s.screenLimited = baseline.size > MAX_KEYS;
      if (s.screenLimited) return { changed: false, confirm: false };
      s.suppressed = baseline; s.baselinePending = false; s.candidates.clear();
      return { changed: false, confirm: false };
    }
    if (bypass) s.baselinePending = false;
    s.suppressed = present;
    const admitted = [], candidates = new Map();
    for (const key of extractKeys(text, this.config.projects)) {
      if (!bypass && s.suppressed.has(key)) continue;
      if (s.keys.includes(key)) { admitted.push(key); continue; }
      const first = s.candidates.get(key) ?? now;
      if (now - first >= KEY_SETTLE_MS) admitted.push(key);
      else candidates.set(key, first);
    }
    s.candidates = candidates;
    return { changed: this.merge(admitted), confirm: candidates.size > 0 };
  }

  merge(keys) {
    const s = this.current;
    if (!s) return false;
    const snapshot = keys.join("\n");
    if (s.snapshot === snapshot) return false;
    s.snapshot = snapshot;
    if (keys.length) s.latestObserved = keys[0];
    const fresh = keys.filter(k => !s.keys.includes(k));
    if (fresh.length) s.keys = [...fresh, ...s.keys].slice(0, MAX_KEYS);
    // Keep the latest observation, deliberate Browse selection and pinned issue in
    // the bounded list, replacing tail entries only when retention requires it.
    const retained = new Set([s.latestObserved, !s.follow ? s.selected : null, s.pinnedIssueKey].filter(Boolean));
    for (const key of retained) {
      if (s.keys.includes(key)) continue;
      if (s.keys.length < MAX_KEYS) s.keys.push(key);
      else {
        let index = s.keys.length - 1;
        while (index >= 0 && retained.has(s.keys[index])) index--;
        if (index >= 0) s.keys[index] = key;
      }
    }
    if (s.follow && keys.length) { s.selected = s.keys.includes(s.latestObserved) ? s.latestObserved : s.keys[0]; s.unseen.clear(); }
    else fresh.forEach(k => s.unseen.add(k));
    for (const key of s.unseen) if (!s.keys.includes(key)) s.unseen.delete(key);
    if (!s.selected && s.follow) s.selected = s.keys[0] || null;
    for (const key of s.keys) this.rowState(key);
    this.prune();
    return !!(fresh.length || (s.follow && keys.length));
  }

  browse() { if (this.current) this.current.follow = false; }
  toggleIssuePin(key) {
    if (!this.config || !this.source || this.source === "manual" || !this.current?.keys.includes(key) ||
        parseIssueKey(this.config.base, key, this.config.projects) !== key) return false;
    this.current.pinnedIssueKey = this.current.pinnedIssueKey === key ? null : key;
    this.browse(); return true;
  }
  follow() {
    const s = this.current;
    if (!s) return;
    s.follow = true; s.query = ""; s.unseen.clear();
    s.selected = s.latestObserved && s.keys.includes(s.latestObserved) ? s.latestObserved : s.keys[0] || null;
  }
  filter(query) { if (this.current) { this.browse(); this.current.query = query; } }
  select(key, { passive = false } = {}) {
    if (!this.current?.keys.includes(key)) return;
    this.current.selected = key;
    if (!passive) { this.browse(); this.current.unseen.delete(key); }
  }
  rows() {
    const s = this.current;
    if (!s) return [];
    const raw = s.query.trim();
    if (/^[A-Za-z][A-Za-z0-9+.-]*:\/\//.test(raw) || /^https?:/i.test(raw)) {
      const key = parseIssueKey(this.config.base, raw, this.config.projects);
      return key && s.keys.includes(key) ? [key] : [];
    }
    const words = raw.toLowerCase().split(/\s+/).filter(Boolean);
    return s.keys.filter(key => {
      const row = this.metadata.get(key);
      const text = [key, row?.summary, row?.status, ...(row?.values || [])].join(" ").toLowerCase();
      return words.every(word => text.includes(word));
    });
  }
  detail(key, now = Date.now()) {
    const entry = this.details.get(key);
    // TTL=0 means no durable cache; a displayed issue lives in memory until
    // selection changes or explicit refresh, not a repeating network request.
    const fetchedAt = Number.isFinite(entry?.fetchedAt) && entry.fetchedAt > 0 ? entry.fetchedAt : entry?.loadedAt;
    return entry && (this.config.ttl === 0 || now - fetchedAt < this.config.ttl * 60000)
      ? entry : null;
  }
  accept(issue, now = Date.now()) {
    const fetchedAt = Number.isFinite(issue.fetchedAt) && issue.fetchedAt > 0 ? issue.fetchedAt : now;
    const entry = { ...issue, fetchedAt, loadedAt: now };
    this.details.set(issue.key, entry);
    // Search rows must not retain full bodies after the detail cache evicts them.
    this.metadata.set(issue.key, {
      key: issue.key, summary: issue.summary, status: issue.status,
      values: issue.values || this.metadata.get(issue.key)?.values || [],
    });
    this.rowStates.set(issue.key, { revision: ++this.projectionRevision, status: "ready" });
    this.failures.delete(issue.key);
    this.denied.delete(issue.key);
    this.prune();
  }

  rowState(key) {
    if (!this.rowStates.has(key)) this.rowStates.set(key, {
      revision: ++this.projectionRevision, status: this.metadata.has(key) ? "ready" : "idle",
    });
    return this.rowStates.get(key);
  }

  beginMetadata(token, keys) {
    token.keys = keys;
    token.projections = new Map(keys.map(key => {
      const state = this.rowState(key);
      state.status = "loading"; state.owner = token;
      this.metadataAttempts.add(key);
      return [key, state.revision];
    }));
  }

  metadataEligible(token, key) {
    const state = this.rowStates.get(key);
    return state?.owner === token && state.revision === token.projections.get(key);
  }

  settleMetadata(token, rows = [], status = "ready") {
    const byKey = new Map(rows.map(row => [row.key, row])), settled = [];
    for (const key of token.keys) {
      if (!this.metadataEligible(token, key)) continue;
      const row = byKey.get(key);
      if (row) this.metadata.set(key, row);
      this.rowStates.set(key, { revision: ++this.projectionRevision,
        status: status === "ready" ? row ? "ready" : "omitted" : status });
      settled.push(key);
    }
    return settled;
  }

  releaseMetadata(token) {
    for (const key of token.keys || []) {
      if (!this.metadataEligible(token, key)) continue;
      const state = this.rowStates.get(key);
      delete state.owner; state.status = this.metadata.has(key) ? "ready" : "idle";
      this.metadataAttempts.delete(key);
    }
  }

  rowPlaceholder(key, loading = false) {
    if (this.metadata.has(key)) return "No title returned";
    if (loading) return "Loading title…";
    if (this.denied.has(key)) return "Title unavailable · check access";
    if (this.failures.has(key)) return "Issue failed to load · Refresh to retry";
    return ({ loading: "Loading title…", omitted: "Title unavailable", failed: "Title failed to load · preview to retry",
      denied: "Title unavailable · check access" })[this.rowStates.get(key)?.status] || "Not loaded yet";
  }
  prune() {
    const retained = new Set([...this.sources.values()].flatMap(s => s.keys));
    for (const map of [this.details, this.metadata, this.rowStates]) {
      for (const key of map.keys()) if (!retained.has(key)) map.delete(key);
    }
    for (const set of [this.failures, this.denied, this.metadataAttempts]) {
      for (const key of set) if (!retained.has(key)) set.delete(key);
    }
    while (this.details.size > 40) this.details.delete(this.details.keys().next().value);
  }
}
