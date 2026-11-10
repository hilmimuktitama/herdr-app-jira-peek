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
    const metadata = issue?.metadata?.find(item => item?.id === field.id);
    const value = ["summary", "status", "description"].includes(field.id) ? issue?.[field.id] : metadata?.value;
    const empty = value === null || value === undefined || (typeof value === "string" && value.trim() === "");
    if (field.id !== "comments" && empty && !layout.showEmpty) continue;
    regions[field.section].push({ ...field, value: empty ? "—" : String(value).trimEnd(),
      unsupportedContent: metadata?.unsupportedContent === true, truncated: metadata?.truncated === true });
  }
  return regions;
}

// Whole-issue clipboard output. The bound applies after the document is built,
// so every configured field and loaded comment gets a chance to be represented.
export const MARKDOWN_LIMIT = 262144;
const MARKDOWN_KEY = /^[A-Z][A-Z0-9_]*-[0-9]+$/;

function markdownText(value) {
  // Preserve meaningful internal whitespace, including Markdown hard-break
  // spaces. Only normalize line endings and trailing whitespace at the ends.
  return String(value ?? "").replace(/\r\n?/g, "\n").trimEnd();
}

function markdownLine(value) {
  return markdownText(value).replace(/\s+/g, " ").trim();
}

function markdownLabel(value) {
  return markdownLine(value) || "Field";
}

function markdownLink(link, key, base = null) {
  if (typeof link !== "string") return null;
  try {
    const url = new URL(link), expected = `/browse/${key}`;
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash ||
        url.pathname !== expected) return null;
    if (base !== null) {
      const configured = new URL(base);
      if (configured.protocol !== "https:" || configured.username || configured.password ||
          configured.search || configured.hash || configured.pathname !== "/" ||
          configured.origin !== url.origin) return null;
    }
    return `${url.origin}${expected}`;
  } catch { return null; }
}

function markdownFetchedAt(issue) {
  const at = Number.isFinite(issue?.fetchedAt) && issue.fetchedAt > 0 ? issue.fetchedAt : issue?.loadedAt;
  if (!Number.isFinite(at) || at <= 0) return "";
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return "";
  const iso = date.toISOString();
  return `Fetched ${displayDate(iso)} · ${iso.slice(11, 16)} UTC`;
}

function markdownField(field, level) {
  const value = ["description", "comments"].includes(field.id)
    ? markdownText(field.value) : displayDate(markdownText(field.value));
  const parts = [`${"#".repeat(level)} ${markdownLabel(field.label)}`, ""];
  // Put the notice before the value so a hard cap cannot remove the only
  // statement that this field is incomplete.
  if (field.unsupportedContent) parts.push("_Some content is unsupported here. Open in Jira for the full field._", "");
  else if (field.truncated) parts.push("_This field is shortened. Open in Jira for the full field._", "");
  parts.push(value);
  return parts.join("\n");
}

function markdownComments(issue, label, level) {
  const hasData = Array.isArray(issue?.comments);
  const comments = hasData ? issue.comments : [];
  const total = Number.isFinite(issue?.commentsTotal) ? Math.max(0, Math.trunc(issue.commentsTotal)) : comments.length;
  const deferred = issue?.commentsDeferred === true;
  const loading = issue?.commentsLoading === true;
  const error = issue?.commentsError;
  const count = comments.length ? ` (${comments.length}${total > comments.length ? ` of ${total}` : ""})` : "";
  const lines = [`${"#".repeat(level)} ${markdownLabel(label)}${count}`];
  if (comments.length) {
    // Keep the state notes ahead of the bodies so even a truncated comment
    // page still explains whether it is partial, loading or failed.
    const notes = [];
    if (total > comments.length) notes.push(`_Showing ${comments.length} of ${total} comments._`);
    if (comments.some(comment => typeof comment?.body === "string" && comment.body.length >= 20000))
      notes.push("_Some comment text may be shortened. Open in Jira for the full discussion._");
    if (loading) notes.push("_Comments are still loading._");
    if (deferred) notes.push("_More comments may still load. Open in Jira for the full discussion._");
    if (error) notes.push(error === "permission_denied"
      ? "_Some comments are unavailable; Jira denied access._" : "_Some comments could not load._");
    if (notes.length) lines.push("", notes.join("\n\n"));
    for (const comment of comments) {
      const author = markdownLine(comment?.author) || "Unknown author";
      const date = displayDate(comment?.created);
      lines.push("", `**${author}**${date ? ` — ${date}` : ""}`, "", markdownText(comment?.body));
    }
  } else if (error === "permission_denied") {
    lines.push("", "_Comments not included; Jira denied access._");
  } else if (error) {
    lines.push("", "_Comments not included; could not load them._");
  } else if (loading) {
    lines.push("", "_Comments are loading._");
  } else if (deferred) {
    lines.push("", "_Comments not loaded; open them in Peek or Jira._");
  } else if (!hasData) {
    lines.push("", "_Comment data unavailable._");
  } else if (total > 0) {
    lines.push("", `_No comments loaded. Open in Jira to view ${total} comment${total === 1 ? "" : "s"}._`);
  } else {
    lines.push("", "_No comments._");
  }
  return lines.join("\n");
}

function markdownTruncate(text, limit) {
  // The documented cap is the whole clipboard payload, including the marker.
  // Count and slice by code point so an astral character is never split.
  const formattedLimit = String(limit).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const marker = `\n\n… Copy truncated at ${formattedLimit} characters. Open in Jira for the full issue.`;
  const budget = Math.max(0, limit - marker.length);
  let count = 0, end = 0;
  for (const character of text) {
    if (count === limit) break;
    count++; end += character.length;
  }
  if (end === text.length) return text;

  count = 0; end = 0;
  for (const character of text) {
    if (count === budget) break;
    count++; end += character.length;
  }
  let cut = text.slice(0, end);
  const newline = cut.lastIndexOf("\n");
  if (newline >= Math.floor(cut.length / 2)) cut = cut.slice(0, newline);
  return `${cut.trimEnd()}${marker}`;
}

export function issueAsMarkdown(issue, layout, link, base = null) {
  const key = issue?.key, sections = new Set(FIELD_SECTIONS), seen = new Set();
  if (typeof key !== "string" || !MARKDOWN_KEY.test(key) || !layout || !Array.isArray(layout.fields) ||
      layout.fields.length > MAX_LAYOUT_FIELDS) return null;
  for (const field of layout.fields) {
    if (!field || typeof field.id !== "string" || !validFieldId(field.id) || !sections.has(field.section) ||
        seen.has(field.id) || (field.id === "comments" && field.section === "header")) return null;
    seen.add(field.id);
  }
  const url = markdownLink(link, key, base);
  if (!url) return null;
  // The projection can omit metadata on a partial issue; never let that make
  // the formatter throw or silently fall back to unfiltered issue values.
  const regions = placedFields({ ...issue, metadata: Array.isArray(issue.metadata) ? issue.metadata : [] },
    { ...layout, showEmpty: false });
  const firstBody = layout.fields.find(field => field?.section === "body");
  const promoted = firstBody?.id === "summary" && firstBody.label === "Summary";
  const title = promoted ? regions.body.find(field => field.id === "summary") : null;
  const blocks = [`# ${key}${title ? ` — ${markdownLine(title.value)}` : ""}`, url];

  const fetched = markdownFetchedAt(issue);
  if (fetched) blocks.push(fetched);
  // Keep the provenance warning before long bodies so truncation cannot remove
  // the only statement that the copied text is incomplete or unsupported.
  if (issue.truncated || issue.unsupportedContent)
    blocks.push("_Some issue content is shortened or unsupported by Peek. Open in Jira for the full issue._");

  if (regions.header.some(field => field.truncated || field.unsupportedContent))
    blocks.push("_Some header values are shortened or unsupported by Peek. Open in Jira for the full values._");
  const header = regions.header.map(field =>
    `- **${markdownLabel(field.label)}:** ${displayDate(markdownLine(field.value))}`);
  if (header.length) blocks.push(header.join("\n"));

  for (const field of regions.body) {
    if (title && field === title) continue;
    blocks.push(field.id === "comments" ? markdownComments(issue, field.label, 2) : markdownField(field, 2));
  }

  if (regions.details.length) {
    const details = regions.details.map(field => field.id === "comments"
      ? markdownComments(issue, field.label, 3) : markdownField(field, 3));
    blocks.push(`## Details\n\n${details.join("\n\n")}`);
  }

  return markdownTruncate(blocks.join("\n\n"), MARKDOWN_LIMIT);
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
    this.displayRevision = 0;
    this.source = null;
    this.sourceRevision = 0;
    this.pinned = false;
    this.retryAfter = 0;
  }

  get current() { return this.sources.get(this.source); }

  newSource(follow = true) {
    return {
      keys: [], selected: null, selectionRevision: 0, readerGrant: null, presentation: null,
      query: "", follow, pinnedIssueKey: null,
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
    if (!state.follow) this.rebuildResults();
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
    if (s.follow && keys.length) { this.setSelected(s.keys.includes(s.latestObserved) ? s.latestObserved : s.keys[0]); this.enterReader(); s.unseen.clear(); }
    else fresh.forEach(k => s.unseen.add(k));
    for (const key of s.unseen) if (!s.keys.includes(key)) s.unseen.delete(key);
    if (!s.selected && s.follow) { this.setSelected(s.keys[0] || null); this.enterReader(); }
    for (const key of s.keys) this.rowState(key);
    this.prune();
    return !!(fresh.length || (s.follow && keys.length));
  }

  browse() {
    const s = this.current;
    if (!s) return;
    const reader = s.readerGrant;
    s.follow = false;
    if (!s.presentation) { this.rebuildResults(); s.readerGrant = reader; }
  }

  setSelected(key) {
    const s = this.current;
    if (!s || s.selected === key) return;
    s.selected = key; s.selectionRevision++; s.readerGrant = null;
  }

  enterReader() {
    const s = this.current;
    if (s?.selected && s.keys.includes(s.selected)) s.readerGrant = { key: s.selected, revision: s.selectionRevision };
  }

  leaveReader() { if (this.current) this.current.readerGrant = null; }

  readerKey() {
    const s = this.current, grant = s?.readerGrant;
    return grant && grant.key === s.selected && grant.revision === s.selectionRevision && s.keys.includes(grant.key) ? grant.key : null;
  }

  rebuildResults() {
    const s = this.current;
    if (!s) return;
    s.follow = false; s.readerGrant = null;
    const revision = ++this.displayRevision, keys = this.matchingKeys();
    s.presentation = { revision, projection: revision, actionsRevision: revision,
      eligible: new Set(keys), pinnedVisible: keys.includes(s.pinnedIssueKey),
      nextSlot: keys.length, viewportCount: Math.max(1, keys.length),
      slots: keys.map((key, index) => ({ id: `${revision}:${index}`, key })) };
  }

  // Keep browsing order separate from canonical recency. New matches join the
  // end automatically; existing matches keep their order and stable row IDs.
  syncPresentations() {
    for (const s of this.sources.values()) {
      const p = s.presentation;
      if (!p) continue;
      const retained = new Set(s.keys), keys = this.matchingKeys(s), matching = new Set(keys), previous = p.slots;
      // A nonmatching selection keeps only its navigation anchor until the
      // user chooses another issue. It never owns browsing actions.
      p.slots = previous.filter(slot => retained.has(slot.key) && (matching.has(slot.key) || slot.key === s.selected));
      const displayed = new Set(p.slots.map(slot => slot.key));
      for (const key of keys.filter(key => !displayed.has(key)).reverse())
        p.slots.push({ id: `${p.revision}:${p.nextSlot++}`, key });
      if (previous.some((slot, index) => p.slots[index] !== slot)) p.projection = ++this.displayRevision;
      const pinnedVisible = matching.has(s.pinnedIssueKey);
      if (pinnedVisible !== p.pinnedVisible) p.projection = ++this.displayRevision;
      p.pinnedVisible = pinnedVisible;
      const eligible = matching;
      if (eligible.has(s.selected) !== p.eligible.has(s.selected)) {
        p.actionsRevision = ++this.displayRevision;
      }
      p.eligible = eligible;
    }
  }

  resultSlots() {
    const s = this.current;
    const slots = s?.presentation?.slots || this.matchingKeys().map(key => ({ id: key, key }));
    const pin = s?.pinnedIssueKey;
    if (!pin || !this.matchingKeys(s).includes(pin)) return slots;
    const index = slots.findIndex(slot => slot.key === pin);
    return index > 0 ? [slots[index], ...slots.slice(0, index), ...slots.slice(index + 1)] : slots;
  }

  compactSlots() {
    const matching = new Set(this.rows());
    return this.resultSlots().filter(slot => matching.has(slot.key));
  }

  navigationTarget(direction, step = 1) {
    const slots = this.resultSlots(), active = new Set(this.rows());
    const anchor = slots.findIndex(slot => slot.key === this.current?.selected);
    if (anchor < 0) return slots.find(slot => active.has(slot.key))?.key;
    const candidates = slots.filter((slot, index) => active.has(slot.key) && (direction < 0 ? index < anchor : index > anchor));
    if (direction < 0) candidates.reverse();
    return candidates[Math.min(step, candidates.length) - 1]?.key || (active.has(this.current.selected) ? this.current.selected : undefined);
  }
  toggleIssuePin(key) {
    if (!this.config || !this.source || this.source === "manual" || !this.current?.keys.includes(key) ||
        parseIssueKey(this.config.base, key, this.config.projects) !== key) return false;
    this.browse();
    const before = this.resultSlots().map(slot => slot.id);
    this.current.pinnedIssueKey = this.current.pinnedIssueKey === key ? null : key;
    if (this.current.presentation) {
      this.current.presentation.pinnedVisible = this.matchingKeys().includes(this.current.pinnedIssueKey);
      if (this.resultSlots().some((slot, index) => slot.id !== before[index]))
        this.current.presentation.projection = ++this.displayRevision;
    }
    return true;
  }
  follow() {
    const s = this.current;
    if (!s) return;
    s.follow = true; s.query = ""; s.unseen.clear();
    s.presentation = null;
    this.setSelected(s.latestObserved && s.keys.includes(s.latestObserved) ? s.latestObserved : s.keys[0] || null);
    this.enterReader();
    this.prune();
  }
  filter(query) { if (this.current) { this.current.query = query; this.rebuildResults(); } }
  select(key, { passive = false, read = false } = {}) {
    if (!this.current?.keys.includes(key)) return;
    if (!passive) this.browse();
    this.setSelected(key);
    if (!passive) { this.current.unseen.delete(key); this.leaveReader(); }
    if (read) this.enterReader();
    this.prune();
  }
  matchingKeys(s = this.current) {
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

  rows() {
    const live = this.matchingKeys();
    const matching = new Set(live);
    return this.resultSlots().filter(slot => slot.key && matching.has(slot.key)).map(slot => slot.key);
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

  invalidateDetails() {
    this.details.clear(); this.failures.clear(); this.denied.clear();
    this.retryAfter = 0;
  }

  failIssue(key, denied = false) {
    this.failures.add(key);
    if (denied) {
      this.details.delete(key); this.metadata.delete(key); this.denied.add(key);
      this.rowStates.set(key, { revision: ++this.projectionRevision, status: "denied" });
    }
  }

  retryIssue(key, { manual = false, failedMetadata = null } = {}) {
    this.failures.delete(key); this.denied.delete(key); this.metadataAttempts.delete(key);
    if (manual) {
      this.retryAfter = 0;
      for (const rowKey of this.current.keys) {
        if (failedMetadata?.delete(rowKey)) this.metadataAttempts.delete(rowKey);
      }
    }
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
    this.syncPresentations();
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
    this.syncPresentations();
    // Retention follows logical selection, independently of reader visibility.
    // This covers Follow/history/source changes as well as explicit selection.
    if (this.config?.ttl === 0) {
      for (const key of this.details.keys()) if (key !== this.current?.selected) this.details.delete(key);
    }
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
