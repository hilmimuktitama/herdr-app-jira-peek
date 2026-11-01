// Pure state: no terminal control, credentials, disk storage, or network access.
export const MAX_KEYS = 200;
export const MAX_SOURCES = 12;

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
    this.source = null;
    this.sourceRevision = 0;
    this.pinned = false;
    this.retryAfter = 0;
  }

  get current() { return this.sources.get(this.source); }

  useSource(address) {
    if (address === this.source) return false;
    this.source = address;
    this.sourceRevision++;
    if (address && !this.sources.has(address)) {
      this.sources.set(address, {
        keys: [], selected: null, query: "", follow: true,
        unseen: new Set(), snapshot: "", latestObserved: null, error: null,
      });
    }
    if (address) {
      const state = this.current;
      this.sources.delete(address); this.sources.set(address, state);
    }
    while (this.sources.size > MAX_SOURCES) this.sources.delete(this.sources.keys().next().value);
    this.prune();
    return true;
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
    // Keep both the latest observation and a deliberate Browse selection in
    // the bounded list, replacing tail entries only when retention requires it.
    const retained = new Set([s.latestObserved, !s.follow ? s.selected : null].filter(Boolean));
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
    if (!s.selected) s.selected = s.keys[0];
    this.prune();
    return !!(fresh.length || (s.follow && keys.length));
  }

  browse() { if (this.current) this.current.follow = false; }
  follow() {
    const s = this.current;
    if (!s) return;
    s.follow = true; s.query = ""; s.unseen.clear();
    s.selected = s.latestObserved && s.keys.includes(s.latestObserved) ? s.latestObserved : s.keys[0] || null;
  }
  filter(query) { if (this.current) { this.browse(); this.current.query = query; } }
  select(key) {
    if (!this.current?.keys.includes(key)) return;
    this.browse(); this.current.selected = key; this.current.unseen.delete(key);
  }
  rows() {
    const s = this.current;
    if (!s) return [];
    const words = s.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
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
    this.failures.delete(issue.key);
    this.denied.delete(issue.key);
    this.prune();
  }
  prune() {
    const retained = new Set([...this.sources.values()].flatMap(s => s.keys));
    for (const map of [this.details, this.metadata]) {
      for (const key of map.keys()) if (!retained.has(key)) map.delete(key);
    }
    for (const set of [this.failures, this.denied, this.metadataAttempts]) {
      for (const key of set) if (!retained.has(key)) set.delete(key);
    }
    while (this.details.size > 40) this.details.delete(this.details.keys().next().value);
  }
}
