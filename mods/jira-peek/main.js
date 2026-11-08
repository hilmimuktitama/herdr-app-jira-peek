import { View, div, svg } from "gpui-kit";
import { h_flex, v_flex, Button, Toggle, Scrollbar, v_virtual_list, Input, InputState, VirtualListScrollHandle } from "gpui-base";
import * as herdr from "herdr";
import { appHome, exec, hc, focused, terminals, panes, theme, settings, props, layout, readTextFile, writeTextFile, watchFolder, pickFolder, nextCommand, run } from "herdr";
import { PeekModel, MAX_KEYS, focusedSource, extractKeys, issueLink, parseIssueKey, statusColor, uiPreferences, readerPreferences, displayDate, FIELD_NAMES, FIELD_SECTIONS, MAX_LAYOUT_FIELDS, validFieldId, defaultFieldLayout, readFieldLayout, parseFieldFile, connectionFieldLayout, updateFieldFile, requestedReaderFields, placedFields } from "./model.js";
import { seedDemo } from "./demo.js";

const ROOT = "mods/jira-peek";
const ISSUE_ACTIONS = new Set(["quick-copy-key", "quick-copy-link", "quick-refresh", "quick-pin", "open", "retry-refresh",
  "copy-key", "copy-link", "refresh", "comments-toggle", "comments-retry", "details-toggle"]);
const MESSAGES = {
  configuration_missing: "Set up Jira or choose an existing configuration folder.",
  connection_changed: "Your connection changed. Reconnect to load its current issues.",
  connection_failed: "Check your private configuration and Jira authentication, then reconnect.",
  dependencies_missing: "Install jq and your configured Jira backend, then reconnect.",
  request_failed: "Could not load Jira data. Refresh to retry.",
  invalid_request: "This request is outside the configured project allowlist.",
  permission_denied: "Jira denied this request. Check issue access and token permissions.",
};

class SelectedIssueRow extends View {
  init(p) { this.renderRow = p.renderRow; this.currentKey = p.currentKey; }
  render() {
    const key = this.currentKey();
    if (key !== this.renderedKey) { this.renderedKey = key; this.hovered = false; }
    return this.renderRow(this.hovered === true).on_hover((hovered, cx) => {
      if (this.hovered === hovered) return;
      this.hovered = hovered; cx.notify();
    });
  }
}

class ResultRowActions extends View {
  init(p) { this.renderActions = p.renderActions; }
  render() { return this.renderActions(); }
}

export default class JiraPeek extends View {
  init(_props, cx) {
    this.model = new PeekModel(); this.epoch = 0; this.revision = 0;
    this.width = 400; this.height = 800; this.watchers = []; this.note = "";
    this.handle = cx.focus_handle(); this.readerHandle = cx.focus_handle(); this.rootFocus = cx.focus_handle();
    this.helpHandle = cx.focus_handle();
    this.nativeInput = !!herdr.commands?.().some(command => command.name === "layout.focus");
    this.listScroll = VirtualListScrollHandle.new();
    this.copyNote = ""; this.copyNoteRevision = 0; this.moreOpen = false; this.helpTopic = null;
    this.connectionParent = "options";
    this.fieldFileText = null; this.fieldFileDocument = parseFieldFile(null); this.fieldReadRevision = 0; this.fieldFileError = "";
    this.preferencesSaving = false; this.preferenceError = "";
    this.issuesExpanded = false; this.disclosureIdentity = null; this.commentsOpen = false; this.detailsOpen = false;
    this.actionFocus = Object.fromEntries([
      "highlight-source", "pin", "follow", "unseen", "reader-focus", "more", "scan", "history", "live-refresh",
      "quick-pin", "pinned-return",
      "connection", "clear-cache", "clear-list", "choose-config", "reconnect", "refresh", "retry-refresh", "open",
      "copy-key", "copy-link", "quick-copy-key", "quick-copy-link", "quick-refresh", "clear-filter", "results-clear-filter", "comments-toggle", "comments-retry", "details-toggle", "dismiss-note", "dismiss-lookup", "setup-open", "setup-back", "setup-save",
      "setup-token-link", "setup-scoped", "setup-retry", "settings-back", "settings-choose", "settings-reconnect",
      "help", "shortcuts", "help-back", "help-token-link", "options-back", "hide", "fields", "fields-back", "fields-apply", "fields-reset", "fields-empty", "fields-add", "fields-path",
    ].map(id => [id, cx.focus_handle()]));
    for (const topic of ["peek", "options", "fields", "connection", "setup"]) {
      for (const [title] of this.helpSections(topic)) {
        this.actionFocus[this.helpSectionId(title)] ||= cx.focus_handle();
      }
    }
    // Live restores only a prior explicit opt-in; absent/malformed state stays off.
    const preferences = this.legacyPreferences = uiPreferences(localStorage.getItem("preferences"));
    this.live = preferences.live;
    this.autoRefreshPreference = preferences.live; this.idlePaused = false;
    this.highlightSource = preferences.highlightSource;
    this.lastInteraction = this.now(); this.lastLiveAttempt = 0;
    this.input = InputState.new({ placeholder: "Filter issues or enter a Jira key…" });
    this.input.on("change", (_e, cx) => {
      this.inputChanged(cx);
    });
    this.input.on("submit", (_e, cx) => { this.interact(); this.submit(cx); });
    this.input.on("focus", (_e, cx) => {
      const passive = !!this.previewFocus && this.previewFocus === this.model.current;
      const preserveFollow = passive || this.clearFocus === this.model.current;
      this.clearFocus = null; this.previewFocus = null;
      if (!passive) this.interact();
      this.typing = true; this.issuesExpanded = true;
      this.model.leaveReader();
      if (!preserveFollow) this.model.browse();
      const previous = this.selectQueryOnFocus;
      this.selectQueryOnFocus = null;
      if (previous && this.input.value() === previous) this.input.set_selected_range({ start: 0, end: previous.length });
      cx.notify();
    });
    this.input.on("blur", (_e, cx) => { this.typing = false; this.clearFocus = null; this.previewFocus = null; cx.notify(); });
    this.demo = props()?.demo === true;
    if (this.demo) { seedDemo(this.model); this.loadFieldLayout(); }
    else this.connect(cx);
    this.rowActions = []; this.rowRefreshPending = false; this.rowRenderRevision = 0;
    // Keep the reader behind a closure: set_props rollback must not traverse
    // the controller's entire state graph when rebuilding this small view.
    // Keep separate retained entities for the fixed row and the virtual list
    // so pin transitions do not move a retained entity between native parents.
    this.selectedRow = this.newSelectedRow(cx);
    this.pinnedSelectedRow = this.newSelectedRow(cx);
    // Native virtual rows cannot register handlers. Keep bounded retained
    // action views so only the header's actual buttons receive action clicks.
    this.resultActionRows = Array.from({ length: MAX_KEYS }, (_, index) => this.newResultActions(cx, index));
    this.pinnedResultActions = this.newResultActions(cx, -1);
    this.rowTask = cx.spawn(async cx => {
      for (;;) {
        if (!this.rowActions.length && !this.rowRefreshPending) await new Promise(resolve => { this.rowWake = resolve; });
        this.rowWake = null;
        if (this.highlightClosed) return;
        this.drainRowActions(cx);
        if (this.rowRefreshPending) {
          this.updateSelectedRows(cx);
        }
      }
    });
    cx.spawn(async (cx) => {
      for (;;) {
        const command = await nextCommand();
        this.handleCommand(command, cx);
      }
    });
    if (this.live) this.scheduleLive(cx);
  }

  rememberOrigin() {
    if (typeof focused !== "function" || typeof panes !== "function") return;
    if (this.isPeekFocused()) return;
    const context = focused();
    if (!context?.terminal) return;
    const address = context.shown || context.terminal;
    if (!terminals().some(t => t.address === address)) return;
    this.origin = { space: context.space, tab: context.tab, terminal: address, backingTerminal: context.terminal, pane: context.pane || null };
  }

  // layout.focus invokes this inside the native shortcut dispatch. Keep it
  // synchronous: the next key/paste must already belong to the native input.
  focus(cx) {
    this.browse(cx);
  }

  handleCommand(command, cx) {
    if (command === "browse") { this.browse(cx); return; }
    if (command === "back") {
      if (this.helpTopic) this.closeHelp(cx);
      else if (this.setup) this.cancelSetup(cx);
      else if (this.fieldEditor) this.closeFields(cx);
      else if (this.connectionSettings) this.closeSettings(cx);
      else if (this.moreOpen) this.closeOptions(cx);
      cx.notify(); return;
    }
    if (command === "hide") { this.hide(cx); return; }
    if (command === "help") { this.openHelp(cx); return; }
    if (command === "options") { this.openOptions(cx); return; }
    if (command === "reconnect" && this.connectionSettings && !this.helpTopic && !this.setup) { this.reconnect(cx); return; }
    if (command === "setup" && this.connectionSettings && !this.helpTopic && !this.demo) { this.openSetup(cx); return; }
    if (this.helpTopic || this.setup || this.connectionSettings || this.fieldEditor || this.moreOpen) { cx.notify(); return; }
    if (command === "peek") this.peek(cx);
    else if (command === "search") this.search(cx);
    else if (command === "follow") this.follow(cx);
    else if (command === "unseen") this.readNew(cx);
    else if (command === "refresh") this.refresh(cx);
    else if (command === "scan") this.scan(cx, { bypass: true });
    else if (command === "history") this.history(cx);
    else if (command === "reconnect") this.connect(cx);
    else if (command === "clear-cache") this.clearCache(cx);
    else if (command === "clear-list") this.clearList(cx);
    else if (command === "pause") { this.interact(); this.model.browse(); }
    else if (command === "resume" && !this.model.current?.follow) this.follow(cx);
    else if (command === "pin" || command === "unpin") {
      if (this.model.source) { this.model.pinned = command === "pin"; this.adoptSource(cx); }
    }
    else if (command === "reader" || command === "issues") {
      if ((!this.issuesExpanded) !== (command === "reader")) this.toggleIssues(cx);
    }
    else if (command === "fields") this.openFields(cx);
    else if (command === "connection" && !this.demo) this.openConnection(cx);
    else if (command === "setup" && !this.demo) this.openSetup(cx);
    else if (command === "comments" && this.currentFieldLayout().fields.some(f => f.id === "comments" && f.section !== "hidden")) this.toggleComments(cx);
    else if (command === "comments-retry") this.loadComments(cx, true);
    else if (command === "details") this.toggleDetails(cx);
    else if (command === "copy-key" || command === "copy-link") this.copyIssue(command === "copy-link", cx);
    else if (command === "open") this.openIssue(cx);
    cx.notify();
  }

  isPeekFocused() {
    return !!(this.typing || this.formInputFocus || this.rootFocus?.is_focused() || this.handle?.is_focused() || this.readerHandle?.is_focused() || this.helpHandle?.is_focused() ||
      Object.values(this.actionFocus || {}).some(handle => handle?.is_focused()));
  }

  hasKeyModifiers(e) {
    const chord = String(e?.keystroke || "").toLowerCase();
    const chordModified = /(^|-)(ctrl|control|alt|shift|cmd|platform|super|win)(-|$)/.test(chord);
    const mods = e?.modifiers || {};
    return chordModified || !!(mods.shift || mods.control || mods.alt || mods.platform);
  }

  peek(cx) {
    this.rememberOrigin();
    if (this.helpTopic || this.setup || this.connectionSettings || this.fieldEditor) { cx?.notify(); return; }
    if (this.isPeekFocused()) this.returnToTerminal(cx);
    else if (this.issueActionKey()) { this.model.browse(); this.model.enterReader(); this.issuesExpanded = false; this.typing = false; this.moreOpen = false; this.readerHandle.focus(); }
    else { this.search(cx); }
    cx?.notify();
  }

  attachedPanel(node = layout()) {
    if (node?.content?.mod === "jira-peek") return node;
    for (const child of node?.children || []) {
      const panel = this.attachedPanel(child);
      if (panel) return panel;
    }
    return null;
  }

  hide(cx) {
    const overlay = props()?.overlay;
    const panel = overlay ? null : this.attachedPanel();
    if (!overlay && !panel) return;
    this.rememberOrigin();
    this.returnToTerminal(cx);
    // Native hiding retains the mod instance and panel width.
    if (overlay) herdr.closeOverlay(overlay);
    else run("layout.hide", { id: panel.id });
  }

  search(cx) {
    if (this.helpTopic || this.setup || this.connectionSettings || this.fieldEditor) { cx?.notify(); return; }
    this.rememberOrigin();
    // The native focus notification may arrive after the first render on a
    // cold opening. Keep source adoption from clearing that first query.
    this.interact(); this.model.browse(); this.model.leaveReader(); this.typing = true; this.issuesExpanded = true; this.input.focus(); cx?.notify();
    this.reconcilePreview(cx, "open");
  }

  browse(cx) {
    if (this.isPeekFocused()) { this.returnToTerminal(cx); return; }
    this.rememberOrigin();
    // Return to an open form without discarding its draft.
    const back = this.helpTopic ? "help-back" : this.setup ? "setup-back"
      : this.fieldEditor ? "fields-back" : this.connectionSettings ? "settings-back"
      : !this.model.config && !this.loading ? "setup-open" : null;
    if (back) { this.actionFocus[back].focus(); cx.notify(); return; }
    this.moreOpen = false;
    this.selectQueryOnFocus = this.input.value();
    this.search(cx);
  }

  consumeBrowseRequest(cx) {
    // A visible toolbar can reveal a hidden copy. Consume its request on the
    // first visible render, including cold starts, without a timing-based retry.
    const request = herdr.shared("jira-peek.browse"), panel = this.attachedPanel();
    if (!request || !panel || request.id !== panel.id || panel.hidden) return;
    herdr.setShared("jira-peek.browse", null);
    const context = focused();
    if (Math.abs(this.now() - request.at) > 1000 || !Number.isFinite(request.at) ||
        (request.space ?? null) !== (context?.space ?? null) || (request.tab ?? null) !== (context?.tab ?? null)) return;
    this.browse(cx);
  }

  returnToTerminal(cx) {
    if (!this.isPeekFocused()) return false;
    const origin = this.origin;
    const context = focused();
    const liveTerminal = origin && terminals().some(t => t.address === origin.terminal);
    const livePane = origin?.pane && panes().some(p => p.pane === origin.pane && p.tab === origin.tab && p.terminal === origin.backingTerminal);
    const sameContext = context && context.space === origin?.space && context.tab === origin?.tab;
    if (!origin || !sameContext || !liveTerminal || (origin.pane && !livePane)) return false;
    if (origin.pane) run("pane.focus", { pane: origin.pane });
    else run("pane.focus", { terminal: origin.terminal });
    this.typing = false; this.interact(); cx?.notify();
    // Host commands finish after this event; redraw once their focus has landed.
    cx?.timer.after(0, cx => cx.notify());
    return true;
  }

  openIssue(cx) {
    const key = this.issueActionKey();
    const config = this.model.config;
    const link = config && key && issueLink(config.base, key, config.projects);
    if (!link || this.demo) return false;
    cx.open_url(link); this.interact(); return true;
  }

  issueActionKey() {
    const selected = this.model.current?.selected;
    const config = this.model.config;
    if (!config || !selected || !this.model.current.keys.includes(selected) || parseIssueKey(config.base, selected, config.projects) !== selected) return null;
    return (this.issuesExpanded ? this.model.rows().includes(selected) : this.model.readerKey() === selected) ? selected : null;
  }

  issueContext() {
    const state = this.model.current, presentation = state?.presentation;
    return { epoch: this.epoch, source: this.model.sourceRevision, state, key: state?.selected, selection: state?.selectionRevision,
      presentation, projection: presentation?.projection, actions: presentation?.actionsRevision,
      reader: state?.readerGrant, expanded: this.issuesExpanded,
      surface: this.helpTopic || this.setup || this.fieldEditor || this.connectionSettings || this.moreOpen };
  }

  issueContextCurrent(context) {
    const current = this.issueContext();
    return Object.keys(context).every(key => context[key] === current[key]);
  }

  focusResults() {
    const rows = this.model.rows();
    if (rows.length === 1 && this.issueActionKey()) this.readerHandle.focus();
    else if (rows.length) this.handle.focus();
    else { this.previewFocus = this.model.current; this.input.focus(); }
  }

  revealSelection() {
    const slots = this.model.compactSlots(), pin = this.model.current?.pinnedIssueKey;
    const sticky = slots[0]?.key === pin ? slots[0] : null;
    if (sticky?.key === this.model.current?.selected) return;
    const scrollable = sticky ? slots.slice(1) : slots;
    const index = scrollable.findIndex(slot => slot.key === this.model.current?.selected);
    if (index < 0) return;
    const page = Math.max(1, this.issuePageSize(slots.length) - (sticky ? 1 : 0)), viewport = this.resultsViewport;
    if (scrollable.length <= page) return;
    const current = viewport && viewport.state === this.model.current && viewport.projection === this.model.current?.presentation?.projection;
    if (current && index >= viewport.range.start && index < viewport.range.end) return;
    this.listScroll.scroll_to_item(index, "top");
  }

  queueRowAction(action, context) {
    this.rowActions.push({ action, context }); this.rowWake?.();
  }

  drainRowActions(cx) {
    for (const { action, context, rowKey } of this.rowActions.splice(0)) {
      if (this.highlightClosed || !this.issueContextCurrent(context) || (!rowKey && !this.issueActionKey())) continue;
      try {
        if (rowKey) this.performResultAction(rowKey, action, context, cx);
        else this.performIssueAction(action, cx);
      }
      catch { this.note = "Could not complete the issue action. Try again."; }
      cx.notify();
    }
  }

  performIssueAction(action, cx) {
    if (action === "open") this.openIssue(cx);
    else if (action === "copy-key") this.copyIssue(false, cx);
    else if (action === "copy-link") this.copyIssue(true, cx);
    else if (action === "pin") this.toggleIssuePin(cx);
    else if (action === "refresh") this.refresh(cx);
  }

  refreshSelectedRow() {
    if (!this.selectedRow) return;
    this.rowRefreshPending = true; this.rowWake?.();
  }

  newSelectedRow(cx) {
    return cx.new(SelectedIssueRow, { currentKey: () => this.model.current?.selected,
      renderRow: hovered => this.renderSelectedIssueRow(this.issueContext(), hovered) });
  }

  newResultActions(cx, index) {
    return cx.new(ResultRowActions, { renderActions: () => {
      const key = index < 0 ? this.fixedActionKey : this.resultActionKeys?.[index];
      const context = this.resultActionContext;
      if (!key || !context || key === context.key || !this.issueContextCurrent(context)) return div();
      return this.renderRowHoverActions(key, theme(), !!this.model.source && this.model.source !== "manual", context);
    } });
  }

  updateSelectedRows(cx) {
    if (!this.selectedRow || this.highlightClosed) return;
    this.rowRefreshPending = false;
    // Refresh text and action leases before the navigation event returns, so
    // the parent cannot mount the previous ticket's cached row for one frame.
    const revision = ++this.rowRenderRevision;
    for (const name of ["selectedRow", "pinnedSelectedRow"]) {
      try { this[name].set_props({ revision }); }
      catch (error) {
        // Native unmounting may release a row while the panel survives.
        if (!String(error?.message || error).includes("Entity has been released")) throw error;
        this[name] = this.newSelectedRow(cx);
        cx.notify();
      }
    }
    for (let index = -1; index < this.resultActionRows.length; index++) {
      const row = index < 0 ? this.pinnedResultActions : this.resultActionRows[index];
      try { row.set_props({ revision }); }
      catch (error) {
        if (!String(error?.message || error).includes("Entity has been released")) throw error;
        const replacement = this.newResultActions(cx, index);
        if (index < 0) this.pinnedResultActions = replacement;
        else this.resultActionRows[index] = replacement;
        cx.notify();
      }
    }
  }

  navigateResults(key, cx) {
    this.model.browse();
    const rows = this.model.rows(), direction = ["up", "arrowup", "pageup", "home"].includes(key) ? -1 : 1;
    const target = key === "home" ? rows[0] : key === "end" ? rows[rows.length - 1]
      : this.model.navigationTarget(direction, key.startsWith("page") ? this.issuePageSize(this.model.compactSlots().length) : 1);
    if (target) {
      this.select(target, cx, false, false);
      this.updateSelectedRows(cx);
      this.revealSelection();
    }
  }

  copyIssue(link, cx) {
    const key = this.issueActionKey(), config = this.model.config;
    if (!key) return;
    const value = link ? config && issueLink(config.base, key, config.projects) : key;
    if (value) this.copy(value, cx, link ? "Issue link copied" : "Issue key copied");
  }

  keyDown(e, cx, context = null) {
    if (this.pointerRowAction) {
      this.pointerRowAction = false; this.refreshSelectedRow(); cx.notify();
    }
    const shortcut = String(e.keystroke || "").toLowerCase(), pressed = String(e.key || "").toLowerCase();
    const issueShortcut = ["cmd-enter", "ctrl-enter", "shift-y"].includes(shortcut) ||
      (!this.hasKeyModifiers(e) && ["y", "r", "p", "c", "d"].includes(pressed));
    // Editing and navigation read current state. Only issue-specific actions
    // carry the rendered target lease, so fast filter edits cannot drop arrows.
    if (context && issueShortcut && !this.typing && !this.setup && !this.fieldEditor && !this.connectionSettings && !this.issueContextCurrent(context)) {
      cx.stop_propagation(); return true;
    }
    if (this.helpTopic) {
      const key = String(e.key || "").toLowerCase();
      if ((!this.hasKeyModifiers(e) && ["escape", "?"].includes(key)) || String(e.keystroke || "").toLowerCase() === "shift-/") {
        this.closeHelp(cx); cx.stop_propagation(); return true;
      }
      if (key === "tab" && (!this.hasKeyModifiers(e) || String(e.keystroke || "").toLowerCase() === "shift-tab")) {
        if (String(e.keystroke || "").toLowerCase() === "shift-tab") window.focus_prev(); else window.focus_next();
        cx.stop_propagation(); cx.notify(); return true;
      }
      if (this.hasKeyModifiers(e)) return false;
      if (["arrowup", "up", "arrowdown", "down", "home", "end"].includes(key) && !this.helpHandle.is_focused()) {
        const order = ["help-back", ...this.helpSections().map(([title]) => this.helpSectionId(title))];
        const current = order.findIndex(id => this.actionFocus[id]?.is_focused());
        const up = key === "arrowup" || key === "up";
        const index = key === "home" ? 0 : key === "end" ? order.length - 1
          : (Math.max(0, current) + (up ? -1 : 1) + order.length) % order.length;
        this.actionFocus[order[index]].focus(); cx.stop_propagation(); cx.notify(); return true;
      }
      if (!this.hasKeyModifiers(e) && (key === "enter" || key === " " || key === "space")) return false;
      if (["arrowup", "up", "arrowdown", "down", "/", "y"].includes(key)) {
        cx.stop_propagation(); return true;
      }
      return false;
    }
    if (this.setupKeyDown(e, cx)) return true;
    const key = String(e.key || "").toLowerCase();
    const chord = String(e.keystroke || "").toLowerCase();
    const modified = this.hasKeyModifiers(e);
    if (key === "tab" && (!modified || chord === "shift-tab")) {
      if (!this.setup && !this.connectionSettings && !this.fieldEditor && !this.moreOpen) {
        this.interact(); this.model.browse();
      }
      if (chord === "shift-tab") window.focus_prev(); else window.focus_next();
      cx.stop_propagation(); cx.notify(); return true;
    }
    if (this.fieldEditor) {
      if (!modified && key === "escape") { this.closeFields(cx); cx.stop_propagation(); return true; }
      return false;
    }
    if (this.setup || this.connectionSettings) return false;
    const helpKey = e.key_char === "?" || key === "?" || chord === "shift-/";
    if (helpKey && !this.typing && (!modified || chord === "shift-/" || chord === "shift-?")) {
      this.openHelp(cx, true); cx.stop_propagation(); return true;
    }
    if (this.moreOpen) {
      const action = chord === "shift-y" ? "copy-link" : !modified ? ({ r: "refresh", y: "copy-key" })[key] : null;
      if (action) {
        if (!e.is_held && this.optionAvailability()[action]) this.runOption(c => this.handleCommand(action, c), cx);
        cx.stop_propagation(); return true;
      }
      if (modified) return false;
      if (key === "arrowup" || key === "up" || key === "arrowdown" || key === "down") {
        const availability = this.optionAvailability(), order = Object.keys(availability);
        const current = order.findIndex(id => this.actionFocus[id]?.is_focused());
        const direction = key === "arrowup" || key === "up" ? -1 : 1;
        const start = current < 0 ? (direction > 0 ? -1 : 0) : current;
        for (let step = 1; step <= order.length; step++) {
          const index = (start + direction * step + order.length) % order.length;
          if (availability[order[index]]) { this.actionFocus[order[index]].focus(); break; }
        }
        cx.stop_propagation(); cx.notify(); return true;
      }
      if (key === "escape") { this.closeOptions(cx); return true; }
      // Let native controls handle activation and leave unrelated host chords alone.
      if (key === "enter" || key === " " || key === "space") return false;
      cx.stop_propagation(); return true;
    }
    // Host chords (including optional Follow/Refresh bindings) belong to keys.json.
    if (!modified && key === "escape") {
      this.interact(); this.clearFocus = null;
      if (this.lookupError) this.lookupError = "";
      else if (this.commentsOpen || this.detailsOpen) {
        this.commentsOpen = false; this.detailsOpen = false;
        if (this.issueActionKey()) this.readerHandle.focus();
      } else if (this.issuesExpanded && this.issueActionKey()) this.select(this.issueActionKey(), cx);
      else if (this.issuesExpanded && this.input.value()) this.clearFilter(cx);
      else this.returnToTerminal(cx);
      cx.stop_propagation(); cx.notify(); return true;
    }
    if (chord === "cmd-f") { this.search(cx); cx.stop_propagation(); return true; }
    if ((key === "/" || e.key_char === "/") && !modified) {
      if (this.typing) return false;
      this.search(cx); cx.stop_propagation(); return true;
    }
    if (this.typing) {
      if (!modified && ["arrowup", "up", "arrowdown", "down", "pageup", "pagedown"].includes(key)) {
        this.navigateResults(key, cx);
        cx.stop_propagation(); cx.notify(); return true;
      }
      return false;
    }
    const readerFocused = this.readerHandle.is_focused();
    const issueControlFocused = ["quick-copy-key", "quick-copy-link", "quick-refresh", "open", "retry-refresh",
      "comments-toggle", "comments-retry", "details-toggle", "quick-pin", "pinned-return"]
      .some(id => this.actionFocus[id]?.is_focused());
    if (!readerFocused && !issueControlFocused && !this.handle.is_focused()) return false;
    if (chord === "cmd-enter" || chord === "ctrl-enter") {
      if (!e.is_held) this.openIssue(cx);
      cx.stop_propagation(); return true;
    }
    if (chord === "shift-y") {
      this.handleCommand("copy-link", cx); cx.stop_propagation(); return true;
    }
    if (modified) return false;
    if (["f", "n", "c", "d", "p", "k"].includes(key)) {
      if (!e.is_held) {
        if (key === "f" && !this.demo && this.model.source && this.model.source !== "manual") this.follow(cx);
        else if (key === "n") this.readNew(cx);
        else if (key === "c") this.toggleComments(cx, true);
        else if (key === "d") this.toggleDetails(cx, true);
        else if (key === "p") this.toggleIssuePin(cx);
        else if (key === "k") this.returnToPin(cx);
      }
      cx.stop_propagation(); return true;
    }
    if (key === "o" || key === "r") {
      if (!e.is_held) this.handleCommand(key === "o" ? "options" : "refresh", cx);
      cx.stop_propagation(); return true;
    }
    if (!readerFocused && key !== "y") return false;
    if (key === "enter") {
      // Reading stays inside Peek, including a second Enter after choosing a result.
      if (this.issuesExpanded && this.issueActionKey()) this.select(this.issueActionKey(), cx);
      else { this.interact(); this.model.browse(); }
      cx.stop_propagation(); cx.notify(); return true;
    }
    if (key === "y") {
      this.copyIssue(false, cx);
      cx.stop_propagation(); return true;
    }
    if (key === "arrowup" || key === "up" || key === "arrowdown" || key === "down") {
      this.navigateResults(key, cx);
      cx.stop_propagation(); return true;
    }
    return false;
  }

  syncInput() {
    const value = this.model.current?.query || "";
    if (this.input.value() === value) return;
    this.syncing = true; this.input.set_value(value); this.syncing = false;
  }

  inputChanged(cx) {
    this.filterPreview = null;
    this.clearFocus = null;
    if (this.syncing) return;
    const query = this.input.value();
    const hadLookupError = !!this.lookupError;
    if (hadLookupError) this.lookupError = "";
    if (query === this.model.current?.query) { if (hadLookupError) cx.notify(); return; }
    this.interact(); this.issuesExpanded = true;
    this.model.filter(query);
    this.reconcilePreview(cx, "query");
    cx.notify();
  }

  clearFilter(cx) {
    this.interact(); this.lookupError = ""; this.filterPreview = null;
    // Native set_value changes the field without guaranteeing a change event.
    this.model.filter(""); this.syncInput(); this.issuesExpanded = true;
    this.input.focus();
    this.reconcilePreview(cx, "query");
    cx.notify();
  }

  now() { return Date.now(); }

  cancelPreview() {
    this.previewTimer?.cancel(); this.previewTimer = null; this.previewWait = null;
  }

  previewOwnsFocus() {
    return this.readerHandle.is_focused() || ["quick-copy-key", "quick-copy-link", "quick-refresh", "quick-pin",
      "open", "retry-refresh", "comments-toggle", "comments-retry", "details-toggle"]
      .some(id => this.actionFocus?.[id]?.is_focused());
  }

  reconcilePreview(cx, intent = "passive") {
    this.model.syncPresentations();
    if (!this.issuesExpanded) return;
    this.model.leaveReader();
    if (this.moreOpen) {
      if (!this.issueActionKey() && ["refresh", "copy-key", "copy-link"].some(id => this.actionFocus?.[id]?.is_focused())) this.focusOptionsStart(this.optionAvailability());
      return;
    }
    if (this.helpTopic || this.setup || this.fieldEditor || this.connectionSettings) return;
    const s = this.model.current;
    if (!s) return;
    const deliberate = intent === "query";
    const rows = this.model.rows();
    if (!deliberate) {
      if (!rows.includes(s.selected)) {
        this.cancelPreview();
        if (this.previewOwnsFocus()) {
          if (rows.length) this.handle.focus();
          else { this.previewFocus = s; this.input.focus(); }
        }
      }
      // Restore automatic previews when delayed metadata supplies a match.
      // This is not a read: preserve unread state, cooldown and viewport.
      if (intent === "passive" && s.query.trim() && rows.length && !rows.includes(s.selected)) this.select(rows[0], cx, false, false, { deferred: true, passive: true });
      this.syncHighlight(); return;
    }
    if (!rows.length) {
      this.cancelPreview();
      if (this.previewOwnsFocus()) { this.previewFocus = s; this.input.focus(); }
      this.syncHighlight();
      return;
    }
    const exact = intent === "query" ? this.lookupKey() : null;
    const key = exact && rows.includes(exact) ? exact : rows.includes(s.selected) ? s.selected : rows[0];
    if (s.selected !== key) {
      if (this.previewOwnsFocus()) { this.previewFocus = s; this.input.focus(); }
      this.select(key, cx, false, true, { deferred: true });
    } else if (deliberate) {
      this.model.select(key);
      if (!this.model.detail(key) && !this.model.failures.has(key)) {
        this.deferPreview(cx, key); this.pump(cx);
      }
    }
  }

  deferPreview(cx, key) {
    if (this.previewWait?.key === key && this.previewWait.state === this.model.current) return;
    this.cancelPreview();
    const wait = { key, state: this.model.current, epoch: this.epoch };
    this.previewWait = wait;
    this.previewTimer = cx.timer.after(150, cx => {
      if (this.previewWait !== wait || wait.epoch !== this.epoch || this.model.current !== wait.state) return;
      this.cancelPreview(); this.pump(cx); cx.notify();
    });
  }
  savePreferences(cx) {
    if (this.demo) {
      localStorage.setItem("preferences", JSON.stringify({ live: this.autoRefreshPreference === true, highlightSource: this.highlightSource !== false }));
      return;
    }
    if (this.preferencesSaving || this.fieldFileError || this.fieldFileText === null) {
      this.usePreferences(readerPreferences(this.fieldFileDocument), cx);
      this.preferenceError = "Could not save preferences. Check the shared config file, then try again."; cx.notify(); return;
    }
    const token = { epoch: this.epoch }, expected = this.fieldFileText;
    const current = () => this.preferenceSave === token && token.epoch === this.epoch && !this.highlightClosed;
    const file = { ...this.fieldFileDocument, preferences: { autoRefresh: this.autoRefreshPreference === true, highlightSource: this.highlightSource !== false } };
    this.preferenceSave = token;
    this.preferencesSaving = true; this.preferenceError = "";
    cx.spawn(async cx => {
      try {
        await writeTextFile(this.fieldFilePath(), JSON.stringify(file, null, 2) + "\n", expected);
        if (current()) await this.loadFieldLayout(cx);
      } catch {
        if (current()) {
          await this.loadFieldLayout(cx);
          if (!current()) return;
          this.usePreferences(readerPreferences(this.fieldFileDocument), cx);
          this.preferenceError = "Preferences were not saved. The file may have changed; review Options and try again.";
        }
      } finally {
        if (this.preferenceSave === token) { this.preferenceSave = null; this.preferencesSaving = false; }
        cx.notify();
      }
    });
  }

  usePreferences(preferences, cx) {
    this.autoRefreshPreference = preferences.live;
    // Reloads and write callbacks never grant a new interaction lease. Check
    // elapsed time even if optimistic Off cancelled its timer during a save.
    if (this.now() - this.lastInteraction >= 5 * 60000) this.idlePaused = true;
    const live = preferences.live && !this.idlePaused && !this.highlightClosed, changed = this.live !== live;
    this.live = live; this.highlightSource = preferences.highlightSource;
    if (changed) {
      if (this.live) this.scheduleLive(cx);
      else { this.liveTimer?.cancel(); this.liveTimer = null; this.liveWait = null; }
    }
    this.syncHighlight();
  }

  currentFieldLayout() { return this.fieldLayout || defaultFieldLayout(this.model.config); }

  fieldFilePath() { return `${appHome()}/data/jira-peek/fields.json`; }

  async loadFieldLayout(cx, initialize = false) {
    this.fieldLayoutKey = `field-layout:${this.configDir || "demo"}:${this.model.config?.base || ""}`;
    if (this.demo) { this.fieldLayout = readFieldLayout(localStorage.getItem(this.fieldLayoutKey), this.model.config); return; }
    const config = this.model.config, directory = this.configDir, epoch = this.epoch;
    if (!config) return;
    const revision = ++this.fieldReadRevision;
    const current = () => epoch === this.epoch && revision === this.fieldReadRevision;
    try {
      let text = await readTextFile(this.fieldFilePath());
      if (!current()) return;
      let file = parseFieldFile(text);
      const stored = connectionFieldLayout(file, directory, config.base);
      let next = stored || (initialize ? readFieldLayout(localStorage.getItem(this.fieldLayoutKey), config) : defaultFieldLayout(config));
      const migratePreferences = initialize && !file.preferences;
      if (migratePreferences) file = { ...file, preferences: {
        autoRefresh: this.legacyPreferences?.live === true, highlightSource: this.legacyPreferences?.highlightSource !== false,
      } };
      if (initialize && (!stored || migratePreferences)) {
        // Preserve the previous UI layout even if migration cannot be saved.
        this.useFieldLayout(next, cx);
        const updated = updateFieldFile(file, directory, config.base, next);
        const serialized = JSON.stringify(updated, null, 2) + "\n";
        try { await writeTextFile(this.fieldFilePath(), serialized, text); text = serialized; file = updated; }
        catch {
          // Another panel may have initialized the same connection first.
          text = await readTextFile(this.fieldFilePath()); file = parseFieldFile(text);
          const concurrent = connectionFieldLayout(file, directory, config.base);
          if (!concurrent) throw new Error("Could not initialize field configuration");
          next = concurrent;
        }
        if (!current()) return;
      }
      this.fieldFileText = text; this.fieldFileDocument = file; this.fieldFileError = "";
      this.preferenceError = ""; this.usePreferences(readerPreferences(file), cx);
      this.useFieldLayout(next, cx);
      // Only the offline demo keeps using localStorage. Native preferences
      // migrate once into the file that both the UI and the user's agent edit.
      if (stored || initialize) { try {
        localStorage.removeItem(this.fieldLayoutKey);
        if (file.preferences) localStorage.removeItem("preferences");
      } catch { /* the file remains authoritative */ } }
    } catch {
      if (current()) this.fieldFileError = "Could not load fields.json. Check its JSON and settings; the last valid layout and preferences are still used.";
    }
    if (current()) cx.notify();
  }

  useFieldLayout(next, cx) {
    const changedRequest = requestedReaderFields(next) !== requestedReaderFields(this.currentFieldLayout());
    this.fieldLayout = next;
    if (!next.fields.some(field => field.id === "comments" && field.section !== "hidden")) this.commentsOpen = false;
    if (changedRequest && !this.demo) {
      this.revision++;
      this.model.details.clear(); this.model.failures.clear(); this.model.denied.clear();
      this.model.retryAfter = 0; this.forceKey = null;
    }
    this.pump(cx);
  }

  openFields(cx, initial = this.currentFieldLayout()) {
    if (!this.model.config) return;
    const draft = readFieldLayout(initial, this.model.config);
    this.fieldEditor = { ...draft, context: this.model.config.context, epoch: this.epoch, fileText: this.fieldFileText, file: this.fieldFileDocument, error: "", busy: false,
      labels: new Map(draft.fields.map(field => [field.id, this.newSetupInput(field.label)])),
      add: this.newSetupInput("", false, "priority or customfield_10016") };
    this.moreOpen = false; this.typing = false; this.model.browse();
    this.actionFocus["fields-back"].focus(); cx.notify();
  }

  releaseFields() {
    if (this.fieldEditor.add === this.formInputFocus || [...this.fieldEditor.labels.values()].includes(this.formInputFocus)) this.formInputFocus = null;
    for (const input of this.fieldEditor.labels.values()) input.release();
    this.fieldEditor.add.release(); this.fieldEditor = null;
  }

  closeFields(cx, applied = false) {
    if (this.fieldEditor.busy && !applied) return;
    this.releaseFields();
    this.moreOpen = !applied && !!this.model.config;
    if (this.moreOpen) this.actionFocus.fields.focus();
    else if (this.model.config) this.readerHandle.focus();
    else this.actionFocus["setup-open"].focus();
    cx.notify();
  }

  resetFields(cx) {
    this.releaseFields();
    this.openFields(cx, defaultFieldLayout(this.model.config));
  }

  addField(cx) {
    const editor = this.fieldEditor, id = editor.add.value().trim();
    if (!validFieldId(id)) editor.error = "Use a supported Jira field ID, such as priority or customfield_10016.";
    else if (editor.fields.some(field => field.id === id)) editor.error = "That field is already listed.";
    else if (editor.fields.length >= MAX_LAYOUT_FIELDS) editor.error = `Use up to ${MAX_LAYOUT_FIELDS} fields. Remove a field before adding another.`;
    else {
      const label = FIELD_NAMES[id] || id;
      editor.fields.push({ id, label, section: "body" });
      editor.labels.set(id, this.newSetupInput(label));
      editor.add.set_value(""); editor.error = ""; editor.labels.get(id).focus();
    }
    cx.notify();
  }

  moveField(id, direction, cx) {
    const fields = this.fieldEditor.fields, from = fields.findIndex(field => field.id === id);
    const group = fields.map((field, i) => field.section === fields[from].section ? i : -1).filter(i => i >= 0);
    const to = group[group.indexOf(from) + direction];
    if (to !== undefined) [fields[from], fields[to]] = [fields[to], fields[from]];
    cx.notify();
  }

  applyFields(cx) {
    const editor = this.fieldEditor;
    if (editor.busy) return;
    if (!this.model.config || editor.context !== this.model.config.context || editor.epoch !== this.epoch) {
      editor.error = "The connection changed. Close and reopen Fields before applying."; cx.notify(); return;
    }
    const next = readFieldLayout({ ...editor, fields: editor.fields.map(field => ({ ...field, label: editor.labels.get(field.id).value() })) }, this.model.config);
    if (this.demo) {
      try { localStorage.setItem(this.fieldLayoutKey, JSON.stringify(next)); }
      catch { editor.error = "Could not save the layout. Your previous layout is unchanged."; cx.notify(); return; }
      this.useFieldLayout(next, cx); this.closeFields(cx, true); return;
    }
    if (this.fieldFileError || editor.fileText !== this.fieldFileText) {
      editor.error = this.fieldFileError || "Fields changed elsewhere. Go Back and reopen Fields before applying."; cx.notify(); return;
    }
    const file = updateFieldFile(editor.file, this.configDir, this.model.config.base, next);
    editor.busy = true; editor.error = ""; cx.notify();
    cx.spawn(async cx => {
      try {
        await writeTextFile(this.fieldFilePath(), JSON.stringify(file, null, 2) + "\n", editor.fileText);
        if (editor.epoch !== this.epoch) return;
        await this.loadFieldLayout(cx);
        if (this.fieldEditor === editor && editor.epoch === this.epoch && !this.fieldFileError) this.closeFields(cx, true);
      } catch {
        if (this.fieldEditor === editor) editor.error = "Could not save. The file may have changed; go Back and reopen Fields before retrying.";
        if (editor.epoch === this.epoch) await this.loadFieldLayout(cx);
      } finally { editor.busy = false; cx.notify(); }
    });
  }
  get highlightSupported() { return typeof herdr !== "undefined" && typeof herdr.setTerminalHighlight === "function"; }

  syncHighlight(reassert = false) {
    if (this.highlightClosed || !this.highlightSupported) return;
    const source = this.model.source, key = this.issueActionKey();
    const valid = this.highlightSource !== false && !this.demo && !this.setup && !this.connectionSettings &&
      this.model.config && typeof key === "string" && key.length <= 128 &&
      /^[A-Z][A-Z0-9_]*-[0-9]+$/.test(key) &&
      this.model.config.projects.includes(key.slice(0, key.lastIndexOf("-"))) &&
      source !== "manual" && focusedSource({ terminal: source }, terminals().filter(t => t.state === "live")) === source && !!source;
    const target = valid ? source : null, query = valid ? key : null;
    const unchanged = (this.highlightTarget || null) === target && (this.highlightKey || null) === query;
    if (unchanged && !(reassert && target && this.highlightApplied)) return;
    // Remember rejected requests too: an unavailable target must not cause a
    // render/retry loop. A source/key change or disable/re-enable retries it.
    this.highlightTarget = target; this.highlightKey = query;
    this.highlightError = false; this.highlightApplied = false;
    try {
      const applied = herdr.setTerminalHighlight(target, query);
      this.highlightApplied = !!target && applied === true;
      if (target && applied === false) herdr.setTerminalHighlight(null, null);
    } catch {
      this.highlightError = true;
      // A failed update may leave the previous mark. Clear once, best effort;
      // native ownership remains responsible if the extension also rejects it.
      if (target) { try { herdr.setTerminalHighlight(null, null); } catch {} }
    }
  }

  async close(_cx) {
    this.cancelConfirmation(); this.cancelPreview(); this.clearFocus = null;
    if (this.highlightClosed) return;
    this.highlightClosed = true; this.highlightApplied = false;
    this.rowTask?.cancel(); this.rowWake?.(); this.rowWake = null;
    this.selectedRow?.release(); this.selectedRow = null;
    this.pinnedSelectedRow?.release(); this.pinnedSelectedRow = null;
    for (const row of this.resultActionRows || []) row.release();
    this.resultActionRows = [];
    this.pinnedResultActions?.release(); this.pinnedResultActions = null;
    this.listScroll?.release?.();
    this.liveTimer?.cancel(); this.liveTimer = null; this.liveWait = null; this.live = false;
    this.highlightTarget = null; this.highlightKey = null;
    if (this.highlightSupported) {
      try { herdr.setTerminalHighlight(null, null); } catch { /* Native unload cleanup is the final safeguard. */ }
    }
  }

  get highlightHelp() {
    if (!this.highlightSupported) return "Highlighting unavailable on this host";
    if (this.highlightError) return "Highlight failed; toggle off/on to retry";
    return "Highlight selected key in terminal";
  }

  toggleHighlight(cx) {
    if (this.highlightClosed || !this.highlightSupported || this.demo) return;
    this.interact(); this.highlightSource = this.highlightSource === false;
    this.savePreferences(cx); this.syncHighlight(); cx.notify();
  }

  interact() { this.clearFocus = null; this.previewFocus = null; this.lastInteraction = this.now(); }
  scheduleLive(cx) {
    this.liveTimer?.cancel();
    this.liveTimer = null; this.liveWait = null;
    if (!this.live || this.demo || this.highlightClosed) return;
    const wait = this.liveWait = {};
    this.liveTimer = cx.timer.after(60000, cx => {
      if (this.liveWait !== wait || !this.live || this.highlightClosed) return;
      this.liveTimer = null; this.liveWait = null;
      if (this.now() - this.lastInteraction >= 5 * 60000) {
        this.idlePaused = true; this.live = false;
        this.note = "Auto-refresh paused in this panel after 5 idle minutes. Resume in Options."; cx.notify(); return;
      }
      const key = this.model.current?.selected;
      if (key && this.now() - this.lastLiveAttempt >= 60000 && this.now() >= this.model.retryAfter) {
        this.lastLiveAttempt = this.now(); this.refresh(cx, true);
      }
      this.scheduleLive(cx);
    });
  }

  toggleLive(cx) {
    if (this.preferencesSaving) return;
    const resume = this.autoRefreshPreference && this.idlePaused;
    this.interact(); this.idlePaused = false;
    if (!resume) this.autoRefreshPreference = !this.autoRefreshPreference;
    this.live = this.autoRefreshPreference;
    if (!resume) this.savePreferences(cx);
    if (this.live) this.scheduleLive(cx);
    else { this.liveTimer?.cancel(); this.liveTimer = null; this.liveWait = null; }
    cx.notify();
  }

  toggleIssues(cx) {
    this.interact(); this.clearFocus = null;
    if (!this.issuesExpanded) {
      this.selectQueryOnFocus = this.input.value(); this.search(cx);
    } else {
      const key = this.issueActionKey() || this.model.rows()[0];
      if (key) this.select(key, cx);
      else this.input.focus();
    }
    cx.notify();
  }

  clearList(cx) {
    if (this.demo || !this.model.config || !this.model.current || this.model.source === "manual") return;
    const state = this.model.clearList();
    this.pruneMetadataFailures();
    this.cancelConfirmation(); this.cancelPreview(); this.cancelRetry();
    this.interact(); this.lookupError = ""; this.filterPreview = null; this.note = "";
    this.copyNoteTimer?.cancel(); this.copyNoteRevision++; this.copyNote = ""; this.copyValue = null;
    this.commentsOpen = false; this.detailsOpen = false; this.forceKey = null;
    this.historyPending = null; this.scanPending = null;
    this.moreOpen = false; this.issuesExpanded = true;
    this.syncInput(); this.listScroll.scroll_to_item(0, "top"); this.syncHighlight();
    this.clearFocus = this.typing ? null : state;
    this.input.focus();
    // Retire old work by source identity, but keep its occupied slots until it
    // settles. The dedicated baseline must be a read begun after this clear.
    this.queueScreen(cx, this.terminalRead()); cx.notify();
  }

  clearCache(cx) {
    this.cancelConfirmation(); this.cancelPreview(); this.clearFocus = null;
    const config = this.model.config;
    if (!config || this.demo || this.clearing) return;
    this.cancelRetry(); this.commentsRequest = null;
    this.interact(); this.clearing = true; this.loading = true; this.error = null; this.lookupError = "";
    this.note = "Clearing local issue cache…";
    const directory = this.configDir;
    // Retire every outstanding result before the bridge changes its cache epoch.
    const token = { epoch: ++this.epoch, directory, context: config.context };
    this.clearToken = token; this.revision++; this.failedMetadata = null; this.model.reset(); this.syncHighlight(); this.request = null; this.backgroundRequest = null; this.scanning = null;
    this.historyRead = null; this.historyPending = null; this.scanPending = null;
    this.forceKey = null; this.timer?.cancel(); this.syncInput(); cx.notify();
    cx.spawn(async taskCx => {
      try {
        const result = await this.bridge("clear", token.context);
        if (this.clearToken !== token || token.epoch !== this.epoch) return;
        if (!result.ok) throw new Error(result.error || "request_failed");
        this.note = "Local issue cache cleared.";
        this.clearToken = null; this.clearing = false;
        this.connect(taskCx, directory);
      } catch {
        if (this.clearToken === token && token.epoch === this.epoch) {
          this.loading = false; this.error = "connection_failed"; this.note = "Could not clear the local issue cache. Reconnect and try again.";
        }
      } finally {
        if (this.clearToken === token) { this.clearToken = null; this.clearing = false; taskCx.notify(); }
      }
    });
  }

  setupRoot() { return `${appHome()}/data/jira-peek/connection`; }

  async setupHelper(operation, ...args) {
    const result = await exec("python3", [`${appHome()}/${ROOT}/runtime/app-setup.py`, operation, this.setupRoot(), ...args]);
    if (result.code !== 0) throw new Error("setup_failed");
    let reply;
    try { reply = JSON.parse(result.stdout); } catch { throw new Error("setup_failed"); }
    if (!reply || reply.ok !== true) {
      const codes = ["invalid_site", "invalid_email", "invalid_projects", "invalid_token", "invalid_cloud_id",
        "authentication_failed", "permission_denied", "rate_limited", "connection_failed", "config_changed",
        "unsafe_path", "dependencies_missing", "setup_failed"];
      throw new Error(codes.includes(reply?.error) ? reply.error : "setup_failed");
    }
    return reply;
  }

  newSetupInput(value = "", masked = false, placeholder = "") {
    const input = InputState.new({ value, placeholder });
    input.on("focus", (_e, cx) => { this.formInputFocus = input; cx.notify(); });
    input.on("blur", (_e, cx) => { if (this.formInputFocus === input) this.formInputFocus = null; cx.notify(); });
    if (masked) input.set_masked(true);
    return input;
  }

  resetSetupToken(form) {
    const old = form.token;
    if (this.formInputFocus === old) this.formInputFocus = null;
    form.token = this.newSetupInput("", true);
    if (old) { old.set_value(""); old.release(); }
  }

  releaseSetup(form) {
    for (const key of ["base", "email", "token", "projects", "cloudId"]) {
      if (this.formInputFocus === form[key]) this.formInputFocus = null;
      if (key === "token") form[key].set_value("");
      form[key].release();
    }
  }

  closeSettings(cx) {
    this.folderSelection = null;
    this.connectionSettings = false;
    if (this.connectionParent === "options" && this.model.config) { this.moreOpen = true; this.actionFocus.connection?.focus(); }
    else {
      this.moreOpen = false;
      if (this.loading) this.rootFocus?.focus();
      else this.actionFocus["setup-open"]?.focus();
    }
    cx.notify();
  }

  openOptions(cx) {
    if (!this.model.config || this.setup || this.connectionSettings || this.fieldEditor) return;
    if (!this.helpTopic && !this.moreOpen) this.rememberMainFocus();
    this.helpTopic = null; this.moreOpen = true;
    this.focusOptionsStart(this.optionAvailability()); cx.notify();
  }

  closeOptions(cx) {
    this.moreOpen = false; this.restoreMainFocus(); cx.stop_propagation(); cx.notify();
  }

  toggleIssuePin(cx) {
    if (!this.model.toggleIssuePin(this.issueActionKey())) return;
    if (this.issuesExpanded) this.revealSelection();
    this.interact(); cx.notify();
  }

  returnToPin(cx) {
    const key = this.model.current?.pinnedIssueKey;
    if (!key || !this.model.current.keys.includes(key)) return;
    this.lookupError = ""; this.filterPreview = null;
    this.select(key, cx);
  }

  rememberMainFocus() {
    this.mainFocus = this.handle.is_focused() ? "list" : (!this.issuesExpanded) && this.model.current?.selected ? "reader" : "filter";
  }

  restoreMainFocus() {
    if (!this.model.config) { (this.loading ? this.rootFocus : this.actionFocus["setup-open"]).focus(); return; }
    if ((!this.issuesExpanded) && this.issueActionKey()) this.readerHandle.focus();
    else if (this.mainFocus === "list") this.focusResults();
    else this.input.focus();
  }

  openHelp(cx, shortcuts = false) {
    if (this.setup?.busy || this.fieldEditor?.busy) return;
    if (this.helpTopic) { this.closeHelp(cx); return; }
    if (!this.moreOpen && !this.setup && !this.fieldEditor && !this.connectionSettings) this.rememberMainFocus();
    this.helpTopic = this.setup ? "setup" : this.fieldEditor ? "fields" : this.connectionSettings ? "connection" : this.moreOpen ? "options" : !this.model.config ? "connection" : "peek";
    // Options and general Help are sibling pages. Returning from Help should
    // reveal the retained issue/filter view, not another covered page.
    if (this.helpTopic === "options") this.moreOpen = false;
    this.helpExpanded = shortcuts && ["peek", "options"].includes(this.helpTopic) ? "Keyboard" : null;
    this.typing = false;
    this.actionFocus["help-back"]?.focus(); cx.notify();
  }

  closeHelp(cx) {
    if (!this.helpTopic) return;
    this.helpTopic = null;
    if (this.setup || this.fieldEditor || this.connectionSettings) this.actionFocus.help?.focus();
    else this.restoreMainFocus();
    cx.stop_propagation(); cx.notify();
  }

  optionAvailability() {
    const selected = this.issueActionKey();
    const config = this.model.config;
    const link = config && selected && issueLink(config.base, selected, config.projects);
    const issueBusy = this.request?.phase === "issue" && this.request.key === selected;
    const issueFailed = !!selected && this.model.failures.has(selected);
    const refreshQueued = !!selected && !!this.model.details.get(selected) && this.forceKey === selected && !issueBusy;
    return {
      refresh: !this.demo && !!selected && !issueBusy && !issueFailed && !refreshQueued,
      "copy-key": !!selected,
      "copy-link": !!link,
      pin: !!this.model.source,
      "highlight-source": this.highlightSupported && !this.demo && !this.preferencesSaving && !this.fieldFileError,
      scan: !!this.model.source && this.model.source !== "manual" && !this.demo && !this.scanning,
      history: !!this.model.source && this.model.source !== "manual" && !this.demo && !this.historyRead && !this.historyPending,
      "clear-list": !this.demo && !!config && !!this.model.current && this.model.source !== "manual" &&
        !!(this.model.current.keys.length || this.model.current.candidates.size || this.model.current.baselinePending),
      "live-refresh": !this.demo && !this.preferencesSaving && !this.fieldFileError && !!config,
      fields: !!config,
      connection: !this.demo,
      "clear-cache": !!this.model.config && !this.demo && !this.clearing,
      help: true,
    };
  }

  optionsEnabled(availability) {
    return Object.keys(availability).filter(id => availability[id]);
  }

  focusOptionsStart(availability) {
    const first = this.optionsEnabled(availability)[0];
    (first ? this.actionFocus[first] : this.actionFocus["options-back"])?.focus();
  }

  openConnection(cx) {
    this.connectionParent = "options";
    if (!this.loading) this.connectionMessage = "";
    this.moreOpen = false; this.connectionSettings = true; this.syncHighlight();
    this.actionFocus["setup-open"]?.focus(); cx.notify();
  }

  runOption(action, cx) {
    this.moreOpen = false;
    action(cx);
    this.restoreMainFocus();
    cx.notify();
  }

  setupKeyDown(e, cx) {
    if (!this.setup && !this.connectionSettings) return false;
    if (String(e.key).toLowerCase() === "escape" && !this.hasKeyModifiers(e)) {
      if (this.setup) this.cancelSetup(cx); else this.closeSettings(cx);
      cx.stop_propagation();
      return true;
    }
    return false;
  }

  openSetup(cx) {
    if (this.setup?.busy) return;
    const parent = this.setup?.parent || (this.connectionSettings ? "connection" : "connect");
    if (this.setup) this.releaseSetup(this.setup);
    this.folderSelection = null;
    if (this.loading) { this.epoch++; this.loading = false; }
    const form = { parent, loading: true, busy: false, error: "", scoped: false,
      base: this.newSetupInput("", false, "https://your-site.atlassian.net"), email: this.newSetupInput(), token: this.newSetupInput("", true),
      projects: this.newSetupInput("", false, "ABC, DEF"), cloudId: this.newSetupInput() };
    this.setup = form; this.syncHighlight(); this.connectionSettings = false; this.moreOpen = false;
    // Keep input inside the already-mounted panel while the form loads.
    this.rootFocus?.focus(); cx.notify();
    cx.spawn(async taskCx => {
      try {
        const result = await this.setupHelper("inspect");
        if (this.setup !== form) return;
        if (typeof result.revision !== "string" || !result.settings || typeof result.settings !== "object") throw new Error("setup_failed");
        form.revision = result.revision;
        for (const key of ["base", "email", "projects", "cloudId"]) form[key].set_value(typeof result.settings[key] === "string" ? result.settings[key] : "");
        form.scoped = !!result.settings.cloudId;
        if (!this.helpTopic) this.requestSetupFocus(form, "base");
      } catch { if (this.setup === form) form.error = "Could not load connection settings. Go back and try again."; }
      finally { if (this.setup === form) { form.loading = false; taskCx.notify(); } }
    });
  }

  cancelSetup(cx) {
    const form = this.setup;
    if (!form || form.busy) return;
    this.releaseSetup(form); this.setup = null;
    if (form.parent === "connection") { this.connectionSettings = true; this.moreOpen = false; this.actionFocus?.["setup-open"]?.focus(); }
    else { this.connectionSettings = false; (this.model.config ? this.actionFocus?.more : this.actionFocus?.["setup-open"])?.focus(); }
    cx.notify();
  }

  saveSetup(cx) {
    const form = this.setup;
    if (!form || form.busy || form.loading || !form.revision) return;
    const payload = { base: form.base.value(), email: form.email.value(), token: form.token.value(),
      projects: form.projects.value(), cloudId: form.scoped ? form.cloudId.value() : "" };
    this.rootFocus?.focus();
    this.resetSetupToken(form);
    let validation = "";
    if (!payload.base || !payload.email || !payload.token || !payload.projects || (form.scoped && !payload.cloudId))
      validation = "Complete all required fields and re-enter your API token.";
    else if (!/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.atlassian\.net\/?$/i.test(payload.base))
      validation = "Enter a Jira Cloud site URL ending in atlassian.net.";
    else if (payload.cloudId && !/^[A-Za-z0-9-]+$/.test(payload.cloudId))
      validation = "Enter a valid Cloud ID.";
    if (validation) {
      payload.token = ""; form.error = validation; this.requestSetupFocus(form, "token"); cx.notify(); return;
    }
    form.busy = true; form.error = ""; cx.notify();
    cx.spawn(async taskCx => {
      let ticket;
      try {
        const prepared = await this.setupHelper("prepare", form.revision);
        ticket = prepared.ticket;
        if (typeof ticket !== "string" || !/^[0-9a-f]{48}$/.test(ticket) ||
            prepared.path !== `${this.setupRoot()}/.setup-pending/${ticket}/request.json`) throw new Error("setup_failed");
        try { await writeTextFile(prepared.path, JSON.stringify(payload), ""); }
        finally { payload.token = ""; }
        await this.setupHelper("save", ticket);
        if (this.setup !== form) return;
        this.releaseSetup(form); this.setup = null; this.connectionSettings = false;
        let remembered = true;
        try { localStorage.setItem("configDir", this.setupRoot()); } catch { remembered = false; }
        this.connect(taskCx, this.setupRoot());
        this.rootFocus?.focus();
        this.note = remembered ? "Account verified. Connection saved." : "Connection saved. Could not remember the selected folder for next time.";
      } catch (error) {
        const messages = {
          invalid_site: "Enter a valid HTTPS Jira Cloud site URL.", invalid_email: "Enter a valid email address.",
          invalid_projects: "Enter uppercase project keys.", invalid_token: "Enter a valid API token.",
          invalid_cloud_id: "Enter a valid Cloud ID.", authentication_failed: "Jira could not verify these credentials.",
          permission_denied: "Verification needs account read permission; reading issues needs issue read permissions.", rate_limited: "Jira is rate limiting requests. Try again later.",
          connection_failed: "Could not reach Jira. Check your connection.", config_changed: "Connection settings changed. Go back and reopen setup.",
          unsafe_path: "The managed connection location is not safe to use.", dependencies_missing: "Token setup requires Python 3 and curl. Install the missing tool and retry.",
        };
        if (this.setup === form) {
          this.resetSetupToken(form);
          const message = Object.hasOwn(messages, error?.message) ? messages[error.message] : "Could not save the connection.";
          form.error = `${message} Re-enter your API token to try again.`;
        }
      } finally {
        payload.token = "";
        // The helper's save also cleans up; cancel is deliberately idempotent.
        if (typeof ticket === "string" && /^[0-9a-f]{48}$/.test(ticket)) { try { await this.setupHelper("cancel", ticket); } catch { /* best effort */ } }
        if (this.setup === form) { form.busy = false; if (form.error) this.requestSetupFocus(form, "token"); taskCx.notify(); }
      }
    });
  }

  requestSetupFocus(form, key) {
    // The input may not be mounted yet (inspection or a replaced token).
    // A new mount identity lets the native size callback hand it focus once.
    form.focusRevision = (form.focusRevision || 0) + 1;
    form.pendingFocus = form[key];
  }

  mountSetupField(form, input, size, cx) {
    if (this.setup !== form || this.helpTopic || form.loading || form.busy ||
        form.pendingFocus !== input || size.width <= 0 || size.height <= 0) return;
    form.pendingFocus = null;
    input.focus(); cx.notify();
  }

  setupField(label, key, t) {
    const form = this.setup, input = form[key], secret = key === "token";
    // Put padding, border and focus styling on the native input itself: every
    // painted pixel belongs to its synchronous native mouse-down focus handler.
    const field = form.busy
      ? div().h(34).px(8).flex().items_center().text_color(t.muted).child(secret ? "Token submitted" : (input.value() || "—"))
      : Input.new(input).accessibility_label(label).when(secret, el => el.role("password_input"))
        .w_full().min_w(0).h(34).px(8).rounded(6).border_1()
        .border_color(this.formInputFocus === input ? t.accent : t.border).text_color(t.foreground);
    return v_flex().id(`setup-field-${key}-${form.focusRevision || 0}`).w_full().min_w(0).flex_none().gap(4)
      .on_size_change((size, cx) => this.mountSetupField(form, input, size, cx))
      .child(div().font_semibold().child(label))
      .child(field);
  }

  renderSetup(root, t) {
    const form = this.setup;
    root.child(h_flex().flex_none().px(this.contentInset).py(8).gap(8).items_center()
      .child(this.button("setup-back", "Cancel", cx => this.cancelSetup(cx), t, { disabled: form.busy }))
      .child(this.button("setup-save", form.busy ? "Testing…" : "Test & save", cx => this.saveSetup(cx), t,
        { active: true, disabled: form.busy || form.loading || !form.revision }))
      .when(!form.loading && !form.revision, el => el.child(this.button("setup-retry", "Retry", cx => this.openSetup(cx), t))));
    if (form.busy || form.error) root.child(div().flex_none().px(this.contentInset).py(4)
      .text_color(form.error ? t.blocked : t.muted).child(form.error || "Testing your Jira connection…"));
    const body = v_flex().id("jira-setup-form").flex_1().min_h(0).w_full().min_w(0).overflow_y_scrollbar().px(this.contentInset).py(16).gap(12)
      .child(div().font_semibold().child("Set up Jira"))
      .child(div().text_color(t.muted).child("Your token is saved in a private local file. Verification needs account read permission; reading issues needs issue read permissions."));
    if (form.loading) body.child(div().child("Loading connection settings…"));
    else {
      body.child(this.setupField("Site URL", "base", t)).child(this.setupField("Email", "email", t))
        .child(this.setupField("API token", "token", t))
        .child(this.button("setup-token-link", "Create API token ↗", cx => cx.open_url("https://id.atlassian.com/manage-profile/security/api-tokens"), t,
          { disabled: form.busy, help: "Create an Atlassian API token" }))
        .child(this.setupField("Project keys", "projects", t))
        .child(div().text_color(t.muted).child("Separate uppercase project keys with a pipe, comma, or space."))
        .child(this.toggle("setup-scoped", "Scoped token", form.scoped, (value, cx) => { form.scoped = value; cx.notify(); }, t,
          "Use a scoped API token", "Requires a Cloud ID", form.busy))
        .child(div().text_color(t.muted).child("Scoped tokens require your Cloud ID."));
      if (form.scoped) body.child(this.setupField("Cloud ID", "cloudId", t));
    }
    return root.child(body);
  }

  async bridge(operation, ...args) {
    if (this.fieldLayout && operation === "issue") args = [args[0], args[1], args[2] || "", requestedReaderFields(this.fieldLayout)];
    if (this.fieldLayout && operation === "comments") args = [args[0], args[1], requestedReaderFields(this.fieldLayout)];
    const result = await exec("sh", [`${appHome()}/${ROOT}/runtime/app-bridge.sh`, operation,
      this.configDir, `${appHome()}/data/jira-peek/state`, ...args]);
    if (result.code !== 0) throw new Error("connection_failed");
    try { return JSON.parse(result.stdout); } catch { throw new Error("connection_failed"); }
  }

  connect(cx, directory, connectionAttempt = null) {
    if (this.demo || this.setup) return;
    this.cancelConfirmation(); this.cancelPreview(); this.clearFocus = null;
    this.cancelRetry(); this.commentsRequest = null;
    this.clearToken = null; this.clearing = false;
    const epoch = ++this.epoch;
    this.lookupError = ""; this.failedMetadata = null; this.model.reset(); this.syncHighlight(); this.syncInput(); this.error = null; this.loading = true;
    this.timer?.cancel(); this.watchers.forEach(task => task.cancel()); this.watchers = [];
    this.request = null; this.backgroundRequest = null; this.scanning = null; this.historyRead = null;
    this.historyPending = null; this.scanPending = null; this.forceKey = null;
    cx.spawn(async (cx) => {
      try {
        if (directory) this.configDir = directory;
        if (!this.configDir) {
          let install = {};
          try { install = JSON.parse(await readTextFile(`${appHome()}/${ROOT}/install.json`) || "{}"); } catch { /* use defaults */ }
          if (epoch !== this.epoch) return;
          this.configDir = props()?.configDir || localStorage.getItem("configDir") || install.configDir || `${appHome()}/data/jira-peek/config`;
        }
        const config = await this.bridge("config");
        if (epoch !== this.epoch) return;
        if (!config.ok) {
          this.error = config.error;
          if (connectionAttempt === this.connectionAttempt) this.connectionMessage = `Could not reconnect. ${MESSAGES[config.error] || MESSAGES.connection_failed}`;
          return;
        }
        this.model.reset(config);
        this.fieldLayout = defaultFieldLayout(config); this.fieldFileError = "";
        this.watch(this.configDir, epoch, cx);
        this.watch(`${appHome()}/data/jira-peek`, epoch, cx);
        await this.loadFieldLayout(cx, true);
        if (epoch !== this.epoch) return;
        if (connectionAttempt === this.connectionAttempt) this.connectionMessage = "Configuration loaded.";
        if (directory) localStorage.setItem("configDir", directory);
        if (config.interval > 0) this.timer = cx.timer.every(config.interval * 1000, cx => this.scan(cx));
        this.adoptSource(cx);
      } catch {
        if (epoch === this.epoch) {
          this.error = "connection_failed";
          if (connectionAttempt === this.connectionAttempt) this.connectionMessage = `Could not reconnect. ${MESSAGES.connection_failed}`;
        }
      }
      finally {
        if (epoch === this.epoch) { this.loading = false; cx.notify(); }
      }
    });
  }

  watch(folder, epoch, cx) {
    this.watchers.push(cx.spawn(async (cx) => {
      try {
        while (epoch === this.epoch) {
          const paths = await watchFolder(folder);
          if (epoch !== this.epoch) return;
          if (paths.some(path => path === `${this.configDir}/config.sh` || path.endsWith("/connection-context"))) {
            const stamp = await this.bridge("stamp");
            if (epoch !== this.epoch) return;
            if (!stamp.ok || stamp.context !== this.model.config?.context) { this.invalidate(cx); return; }
          }
          if (paths.includes(this.fieldFilePath())) await this.loadFieldLayout(cx);
        }
      } catch {
        if (epoch === this.epoch) {
          // A missing watcher must not silently allow stale connection data.
          this.invalidate(cx);
        }
      }
    }));
  }

  invalidate(cx) {
    this.cancelConfirmation(); this.cancelPreview(); this.clearFocus = null;
    this.cancelRetry(); this.commentsRequest = null;
    const restoreFocus = !this.setup && !this.connectionSettings && this.isPeekFocused();
    this.epoch++; this.failedMetadata = null; this.model.reset(); this.syncHighlight(); this.timer?.cancel();
    this.error = "connection_changed"; this.lookupError = ""; this.request = null; this.backgroundRequest = null; this.scanning = null;
    this.clearToken = null; this.clearing = false; this.historyRead = null;
    this.historyPending = null; this.scanPending = null; this.loading = false; this.moreOpen = false;
    if (restoreFocus) this.focusVisibleSurface();
    if (this.connectionSettings) this.connectionMessage = MESSAGES.connection_changed;
    this.forceKey = null; this.syncInput(); cx.notify();
  }

  focusVisibleSurface() {
    if (this.helpTopic) return;
    if (this.fieldEditor?.busy) this.rootFocus?.focus();
    else if (!this.formInputFocus) this.actionFocus[this.fieldEditor ? "fields-back" : "setup-open"]?.focus();
  }

  chooseConfig(cx) {
    if (this.setup) return;
    const inConnection = this.connectionSettings;
    const selection = {}; this.folderSelection = selection;
    cx.spawn(async (cx) => {
      try {
        const folder = await pickFolder({ prompt: "Use Jira Peek configuration" });
        if (this.folderSelection !== selection || this.setup || (inConnection && !this.connectionSettings)) return;
        this.folderSelection = null;
        if (folder) {
          if (inConnection) this.reconnect(cx, folder);
          else this.connect(cx, folder);
        } else if (inConnection && this.connectionSettings) { if (!this.helpTopic) this.actionFocus["settings-choose"]?.focus(); cx.notify(); }
      } catch {
        if (this.folderSelection === selection && !this.setup && (!inConnection || this.connectionSettings)) {
          this.folderSelection = null;
          if (inConnection) this.connectionMessage = "Could not open the folder picker.";
          else this.note = "Could not open the folder picker.";
          if (inConnection && !this.helpTopic) this.actionFocus["settings-choose"]?.focus();
          cx.notify();
        }
      }
    });
  }

  reconnect(cx, directory) {
    this.connectionMessage = "";
    const attempt = this.connectionAttempt = (this.connectionAttempt || 0) + 1;
    this.connect(cx, directory, attempt);
    if (!this.helpTopic) this.actionFocus["settings-back"]?.focus();
  }

  adoptSource(cx, scan = true) {
    this.rememberOrigin();
    this.syncHighlight();
    if (this.demo || !this.model.config || this.model.pinned) return;
    const address = focusedSource(focused(), terminals());
    const query = this.typing ? this.input.value() : null;
    // Clicking this panel leaves terminal focus null. Keep that source so
    // filtering and reading never switch underneath the pointer.
    if (address && this.model.useSource(address)) {
      this.cancelConfirmation(); this.cancelPreview(); this.clearFocus = null;
      this.pruneMetadataFailures();
      this.syncHighlight();
      if (query !== null) { this.model.filter(query); this.model.browse(); }
      this.lookupError = ""; this.syncInput(); this.note = "";
      this.revealSelection();
      if (scan) this.scan(cx);
      this.reconcilePreview(cx);
      this.pump(cx);
    }
  }

  terminalRead(options = {}) {
    return { epoch: this.epoch, sourceRevision: this.model.sourceRevision,
      address: this.model.source, state: this.model.current, ...options };
  }

  terminalReadCurrent(token) {
    return !this.highlightClosed && token.epoch === this.epoch && token.sourceRevision === this.model.sourceRevision &&
      token.address === this.model.source && token.state === this.model.current;
  }

  requestSourceCurrent(token) {
    return !this.highlightClosed && token.epoch === this.epoch && this.model.sources.get(token.address) === token.state;
  }

  cancelConfirmation() {
    this.confirmTimer?.cancel(); this.confirmTimer = null; this.confirmRead = null;
  }

  scan(cx, options = {}) {
    if (this.demo || !this.model.config || this.highlightClosed) return;
    this.adoptSource(cx, false);
    this.queueScreen(cx, this.terminalRead(options));
  }

  queueScreen(cx, token) {
    if (!this.terminalReadCurrent(token) || !token.address || token.address === "manual") return;
    if (this.scanning || this.historyRead) {
      if (this.sameRead(this.scanPending, token)) {
        this.scanPending.bypass ||= token.bypass;
        this.scanPending.confirmation &&= token.confirmation;
      } else this.scanPending = token;
      return;
    }
    this.startScreen(cx, token);
  }

  startScreen(cx, token) {
    const { address, state } = token;
    if (!this.terminalReadCurrent(token)) return;
    if (!terminals().some(t => t.address === address)) {
      state.error = "Source terminal is no longer available."; cx.notify(); return;
    }
    this.scanning = token;
    cx.spawn(async cx => {
      try {
        // Passive reads never scroll, send input, or change terminal focus.
        const result = await hc(["read", address, "--lines", "0"]);
        if (!this.terminalReadCurrent(token)) return;
        if (result.code !== 0) throw new Error("unavailable");
        state.error = null;
        const previous = state.selected;
        const observed = this.model.observeScreen(result.stdout, this.now(), {
          bypass: token.bypass, truncated: result.truncated === true,
        });
        if (state.selected !== previous) {
          this.revealSelection();
        }
        if (observed.confirm && !token.confirmation) {
          this.cancelConfirmation();
          const confirmation = { ...token, confirmation: true };
          this.confirmRead = confirmation;
          this.confirmTimer = cx.timer.after(250, cx => {
            if (this.confirmRead !== confirmation) return;
            this.cancelConfirmation(); this.queueScreen(cx, confirmation);
          });
        } else if (!observed.confirm) this.cancelConfirmation();
        this.reconcilePreview(cx); this.syncHighlight(); this.pump(cx); cx.notify();
      } catch {
        if (this.terminalReadCurrent(token)) {
          state.error = state.baselinePending ? "Could not establish a fresh screen baseline. Scan again to retry."
            : "Source unavailable. Retrying passive reads…";
          cx.notify();
        }
      } finally {
        if (this.scanning === token) {
          this.scanning = null;
          if (token.epoch === this.epoch) {
            this.drainTerminalRead(cx);
            if (!this.scanning && !this.historyRead && !this.terminalReadCurrent(token)) this.scan(cx);
          }
        }
      }
    });
  }

  history(cx) {
    if (this.demo) return;
    const token = this.terminalRead();
    if (!token.address || token.address === "manual" || !token.state || !terminals().some(t => t.address === token.address)) return;
    this.interact();
    if (this.sameRead(this.historyRead, token) || this.sameRead(this.historyPending, token)) return;
    if (this.scanning || this.historyRead) {
      this.historyPending = token;
      this.note = "History queued after the screen read…"; cx.notify(); return;
    }
    this.startHistory(cx, token);
  }

  sameRead(a, b) { return !!a && !!b && a.epoch === b.epoch && a.sourceRevision === b.sourceRevision && a.address === b.address && a.state === b.state; }

  startHistory(cx, token) {
    if (!this.terminalReadCurrent(token) || !terminals().some(t => t.address === token.address)) return;
    this.historyRead = token; this.note = "Reading available terminal history…"; cx.notify();
    cx.spawn(async cx => {
      try {
        const result = await hc(["read", token.address, "--lines", "200"]);
        if (!this.terminalReadCurrent(token)) return;
        if (result.code !== 0) throw new Error("unavailable");
        const previous = token.state.selected;
        this.model.merge(extractKeys(result.stdout.slice(-200000), this.model.config.projects));
        if (token.state.selected !== previous) {
          this.revealSelection();
        }
        this.note = "History read · alternate-screen history may be unavailable.";
        this.reconcilePreview(cx); this.syncHighlight(); this.pump(cx);
      } catch {
        if (this.terminalReadCurrent(token)) this.note = "Terminal history is unavailable; the current screen remains available.";
      } finally {
        if (this.historyRead === token) this.historyRead = null;
        if (token.epoch === this.epoch) { this.drainTerminalRead(cx); cx.notify(); }
      }
    });
  }

  drainTerminalRead(cx) {
    if (this.scanning || this.historyRead) return;
    if (this.historyPending) {
      const pending = this.historyPending; this.historyPending = null;
      if (this.terminalReadCurrent(pending)) { this.startHistory(cx, pending); return; }
    }
    if (this.scanPending) {
      const pending = this.scanPending; this.scanPending = null;
      if (this.terminalReadCurrent(pending)) this.startScreen(cx, pending);
    }
  }

  cancelRetry() {
    this.retryTimer?.cancel(); this.retryTimer = null; this.retryWait = null;
  }

  deferPump(cx) {
    const at = this.model.retryAfter;
    if (this.retryWait?.epoch === this.epoch && this.retryWait.at === at) return;
    this.cancelRetry();
    const wait = { epoch: this.epoch, at };
    this.retryWait = wait;
    this.retryTimer = cx.timer.after(Math.max(1, at - this.now()), cx => {
      if (this.retryWait !== wait || wait.epoch !== this.epoch) return;
      this.retryTimer = null; this.retryWait = null;
      this.pump(cx); cx.notify();
    });
  }

  toggleDetails(cx, keyboard = false) {
    if (!this.issueActionKey() || !this.model.details.has(this.issueActionKey())) return;
    this.interact(); this.model.browse(); this.detailsOpen = !this.detailsOpen;
    if (keyboard) { this.model.enterReader(); this.issuesExpanded = false; this.typing = false; this.actionFocus["details-toggle"].focus(); }
    cx.notify();
  }

  toggleComments(cx, keyboard = false) {
    if (!this.issueActionKey() || !this.model.details.has(this.issueActionKey())) return;
    const field = this.currentFieldLayout().fields.find(field => field.id === "comments" && field.section !== "hidden");
    if (!field) return;
    this.interact();
    if (field.section === "details") this.detailsOpen = true;
    this.commentsOpen = !this.commentsOpen;
    if (this.commentsOpen) { this.model.browse(); this.loadComments(cx); }
    if (keyboard) { this.model.enterReader(); this.issuesExpanded = false; this.typing = false; this.actionFocus["comments-toggle"].focus(); }
    cx.notify();
  }

  loadComments(cx, retry = false) {
    const key = this.model.current?.selected, config = this.model.config;
    const issue = this.model.details.get(key);
    if (this.highlightClosed || !this.issueActionKey() || !config || !issue?.commentsDeferred || this.demo ||
        !this.currentFieldLayout().fields.some(field => field.id === "comments" && field.section !== "hidden")) return;
    if (retry) issue.commentsError = "";
    if (this.commentsRequest || issue.commentsError) return;
    const token = { epoch: this.epoch, key, issue, address: this.model.source, state: this.model.current };
    this.commentsRequest = token; issue.commentsLoading = true;
    cx.spawn(async cx => {
      try {
        const result = await this.bridge("comments", config.context, key);
        if (token.epoch !== this.epoch) return;
        if (["connection_changed", "connection_failed", "configuration_missing"].includes(result.error) ||
            (result.ok && result.context !== config.context)) { this.invalidate(cx); return; }
        if (!this.requestSourceCurrent(token) || this.model.details.get(key) !== issue) return;
        if (!result.ok) throw new Error(result.error === "permission_denied" ? "permission_denied" : "request_failed");
        const comments = result.comments;
        if (comments?.key !== key || !Array.isArray(comments.comments)) throw new Error("request_failed");
        issue.comments = comments.comments; issue.commentsTotal = comments.commentsTotal;
        issue.commentsDeferred = false; issue.commentsLoaded = true; issue.commentsError = "";
        issue.truncated ||= comments.truncated === true;
        issue.unsupportedContent ||= comments.unsupportedContent === true;
      } catch (error) {
        if (this.requestSourceCurrent(token) && this.model.details.get(key) === issue)
          issue.commentsError = error.message === "permission_denied" ? "permission_denied" : "request_failed";
      } finally {
        if (this.commentsRequest === token) issue.commentsLoading = false;
        if (this.commentsRequest === token) {
          this.commentsRequest = null;
          if (token.epoch === this.epoch && this.commentsOpen) this.loadComments(cx);
        }
        cx.notify();
      }
    });
  }

  pruneMetadataFailures() {
    if (this.failedMetadata?.epoch !== this.epoch) return;
    for (const key of this.failedMetadata.keys) {
      if (!["failed", "denied"].includes(this.model.rowStates.get(key)?.status)) this.failedMetadata.keys.delete(key);
    }
  }

  metadataFailure(token, status = "failed") {
    const keys = this.model.settleMetadata(token, [], status);
    if (keys.length) {
      if (this.failedMetadata?.epoch !== token.epoch) this.failedMetadata = { epoch: token.epoch, keys: new Set() };
      for (const key of this.failedMetadata.keys) if (!this.model.metadataAttempts.has(key)) this.failedMetadata.keys.delete(key);
      keys.forEach(key => this.failedMetadata.keys.add(key));
    }
    return keys;
  }

  pump(cx) {
    this.syncHighlight(); this.syncDisclosures();
    const config = this.model.config, s = this.model.current;
    if (this.demo || !config || !s || this.highlightClosed) return;
    const key = this.issueActionKey(), force = !!key && this.forceKey === key;
    const deferred = this.previewWait?.state === s && this.previewWait.key === key;
    const detail = key && (force || (!deferred && !this.model.detail(key) && !this.model.failures.has(key)));
    const keys = s.keys.slice(0, config.limit).filter(k => !this.model.metadata.has(k) && !this.model.metadataAttempts.has(k));
    // Count retired work until it actually settles. Only a still-valid request
    // can satisfy the latest selection, including after clearing/re-admitting it.
    const usable = token => token && this.requestSourceCurrent(token) && token.revision === this.revision;
    if (detail && [this.request, this.backgroundRequest].some(token => token?.phase === "issue" && token.key === key && !usable(token))) return;
    if (detail && this.backgroundRequest?.phase === "issue" && this.backgroundRequest.key === key && usable(this.backgroundRequest)) {
      [this.request, this.backgroundRequest] = [this.backgroundRequest, this.request];
    }
    if (this.request) {
      if (!detail || (this.request.phase === "issue" && this.request.key === key && usable(this.request)) || this.backgroundRequest) return;
      this.backgroundRequest = this.request; this.request = null;
    }
    if (!detail && this.backgroundRequest?.phase === "metadata") return;
    if (!detail && !keys.length) { this.cancelRetry(); return; }
    if (this.now() < this.model.retryAfter) { this.deferPump(cx); return; }
    this.cancelRetry();
    const token = { epoch: this.epoch, revision: this.revision, address: this.model.source, state: s,
      key: detail ? key : null, phase: detail ? "issue" : "metadata" };
    this.request = token;
    if (detail) this.forceKey = null;
    else this.model.beginMetadata(token, keys);
    const current = () => this.requestSourceCurrent(token) && token.revision === this.revision;
    const failure = (denied = false) => {
      if (detail) {
        this.model.failures.add(key);
        if (denied) {
          this.model.details.delete(key); this.model.metadata.delete(key); this.model.denied.add(key);
          this.model.rowStates.set(key, { revision: ++this.model.projectionRevision, status: "denied" });
        }
      } else return this.metadataFailure(token, denied ? "denied" : "failed");
      return [key];
    };
    cx.spawn(async cx => {
      try {
        const result = detail ? await this.bridge("issue", config.context, key, ...(force ? ["refresh"] : []))
          : await this.bridge("metadata", config.context, ...keys);
        if (token.epoch !== this.epoch) return;
        // Revocation is authoritative even for a cleared or superseded source.
        if (["connection_changed", "connection_failed", "configuration_missing"].includes(result.error) ||
            (result.ok && result.context !== config.context)) { this.invalidate(cx); return; }
        if (!current()) return;
        if (["dependencies_missing", "invalid_request", "permission_denied"].includes(result.error)) {
          const affected = failure(result.error === "permission_denied");
          if (affected.length && token.state === this.model.current)
            this.note = detail && result.error === "permission_denied" ? "" : MESSAGES[result.error];
          return;
        }
        if (!result.ok) throw new Error("request_failed");
        if (detail) {
          if (result.issue?.key !== key) throw new Error("request_failed");
          this.model.accept(result.issue);
          if (this.commentsOpen && this.model.current?.selected === key) this.loadComments(cx);
        } else {
          if (!Array.isArray(result.rows)) throw new Error("request_failed");
          const settled = this.model.settleMetadata(token, result.rows);
          if (this.failedMetadata?.epoch === token.epoch) settled.forEach(k => this.failedMetadata.keys.delete(k));
        }
      } catch {
        if (current()) {
          const affected = failure();
          if (detail && this.issueActionKey() === key) this.model.retryAfter = this.now() + 30000;
          if (affected.length && token.state === this.model.current) {
            if (!detail) this.note = "Some issue titles did not load. Preview an issue to load it, or Refresh to retry.";
            else if (this.issueActionKey() === key) this.note = "Could not load Jira data. Refresh to retry.";
          }
        }
      } finally {
        if (token.epoch === this.epoch && !detail) this.model.releaseMetadata(token);
        if (this.request === token || this.backgroundRequest === token) {
          if (this.request === token) this.request = null;
          else this.backgroundRequest = null;
          this.model.prune(); this.pruneMetadataFailures(); this.reconcilePreview(cx); this.pump(cx); cx.notify();
        }
      }
    });
  }

  select(key, cx, read = true, reveal = true, { deferred = false, passive = false } = {}) {
    if (!this.model.current?.keys.includes(key)) return;
    if (!passive) this.interact();
    if (!deferred) this.cancelPreview();
    const previous = this.model.current?.selected;
    this.model.select(key, { passive, read: read || (!this.issuesExpanded && !passive) });
    // A deliberate choice may try another issue immediately; passive scans
    // and automatic refresh still respect the connection's retry cooldown.
    if (!passive && previous !== this.model.current?.selected) this.model.retryAfter = 0;
    if (read) { this.issuesExpanded = false; this.typing = false; }
    this.syncHighlight();
    if (previous !== key) { this.commentsOpen = false; }
    if (this.forceKey && this.forceKey !== key) this.forceKey = null;
    if (reveal && (!read || previous !== key)) this.revealSelection();
    if (read) this.readerHandle.focus();
    if (!read && !deferred) this.filterPreview = { query: this.input.value(), key };
    if (deferred && !this.model.detail(key)) this.deferPreview(cx, key);
    if (!passive) this.note = "";
    this.pump(cx); cx.notify();
  }

  rowPlaceholder(key) {
    const loading = [this.request, this.backgroundRequest].some(token => token?.phase === "issue" && token.key === key &&
      this.requestSourceCurrent(token) && token.revision === this.revision);
    return this.model.rowPlaceholder(key, loading);
  }
  lookupKey() {
    const raw = this.input.value().trim(), config = this.model.config;
    const keyInput = /^[A-Za-z][A-Za-z0-9_]*-[0-9]+$/.test(raw) ? raw.toUpperCase() : raw;
    return config ? parseIssueKey(config.base, keyInput, config.projects) : null;
  }

  submit(cx) {
    const raw = this.input.value().trim();
    const config = this.model.config;
    if (!config) return;
    // An explicit keyboard preview wins over interpreting the unchanged
    // filter as a direct key. Editing the input starts a fresh lookup.
    const preview = this.filterPreview;
    if (preview?.query === this.input.value() && preview.key === this.model.current?.selected && this.model.rows().includes(preview.key)) {
      this.lookupError = ""; this.select(preview.key, cx); return;
    }
    const key = this.lookupKey();
    if (key) {
      this.lookupError = "";
      if (!this.model.current) this.model.useSource("manual");
      this.model.browse(); this.model.merge([key]);
      this.select(key, cx); return;
    }
    const rows = this.model.rows();
    const urlInput = /^[A-Za-z][A-Za-z0-9+.-]*:\/\//.test(raw);
    // Hyphenated story labels are ordinary filters when they match a row.
    // URLs always go through origin validation, even if their text matches.
    if (urlInput || (!rows.length && /^[A-Za-z][A-Za-z0-9_]*-.*$/.test(raw))) {
      const projects = config?.projects?.join(", ") || "configured projects";
      let origin = "your configured Jira site";
      try { origin = new URL(config.base).origin; } catch { /* config error is shown separately */ }
      this.lookupError = `Use an issue key from ${projects}, or a Jira URL from ${origin}.`;
      cx.notify(); return;
    }
    this.lookupError = "";
    const selected = this.model.current?.selected;
    const target = rows.includes(selected) ? selected : rows[0];
    if (target) this.select(target, cx);
  }

  readNew(cx) {
    const s = this.model.current;
    const key = s?.keys.find(key => s.unseen.has(key));
    if (!key) return;
    this.lookupError = ""; this.filterPreview = null;
    // select acknowledges only this arrival and leaves the retained query and
    // Paused state intact. Reprinting an old key must not consume new work.
    this.select(key, cx);
  }
  follow(cx) {
    this.interact(); this.lookupError = "";
    const pausing = this.model.current?.follow;
    if (pausing) this.model.browse();
    else {
      // A newly followed issue can remove its predecessor's disclosures, now
      // or after the next scan. Move their focus to the persistent reader first.
      if (["comments-toggle", "comments-retry", "details-toggle", "retry-refresh"]
        .some(id => this.actionFocus?.[id]?.is_focused())) {
        this.issuesExpanded = false; this.readerHandle.focus();
      }
      this.model.follow(); this.syncInput();
    }
    if (!pausing) this.revealSelection();
    this.scan(cx); this.pump(cx); cx.notify();
  }
  refresh(cx, automatic = false) {
    const key = this.issueActionKey();
    if (this.demo || !key) return;
    // Automatic work never queues behind another request or invalidates it.
    // This also prevents a queued tick from running after Live is paused.
    if (automatic && (!this.live || this.request || this.backgroundRequest || this.now() < this.model.retryAfter ||
        this.now() - this.lastInteraction >= 5 * 60000)) return;
    this.interactIfManual(automatic);
    if (!automatic) this.cancelPreview();
    this.revision++; this.model.failures.delete(key); this.model.denied.delete(key); this.model.metadataAttempts.delete(key);
    if (!automatic) {
      this.model.retryAfter = 0;
      if (this.failedMetadata?.epoch === this.epoch) {
        for (const rowKey of this.model.current.keys) {
          if (this.failedMetadata.keys.delete(rowKey)) this.model.metadataAttempts.delete(rowKey);
        }
      }
    }
    this.forceKey = key; this.note = "";
    this.pump(cx); cx.notify();
  }
  interactIfManual(automatic) { if (!automatic) this.interact(); }
  copy(value, cx, label = "Copied") {
    const revision = ++this.copyNoteRevision;
    this.copyNoteTimer?.cancel();
    try {
      cx.write_to_clipboard(value); this.copyNote = label; this.copyValue = value;
    } catch {
      this.copyNote = "Could not copy to the clipboard."; this.copyValue = null;
    }
    cx.notify();
    this.copyNoteTimer = cx.timer.after(2200, cx => {
      if (revision !== this.copyNoteRevision) return;
      this.copyNote = ""; cx.notify();
    });
  }
  button(id, title, action, t, options = {}) {
    const { active = false, disabled = false, label = title, help = label, row = false, trailing = "", trailingIcon = "", icon = "", iconOnly = false, quiet = false, focusLabel = label, iconButtonSize = 32, iconSize = 16 } = options;
    const focus = this.actionFocus[id];
    const context = ISSUE_ACTIONS.has(id) ? this.issueContext() : null;
    if (iconOnly && focus.is_focused()) this.focusCaption = focusLabel;
    const button = Button.new(id).track_focus(focus).tab_index(0).tab_stop(!disabled)
      .accessibility_label(label).tooltip(help).disabled(disabled)
      .when(!disabled, el => el.cursor_pointer())
      .when(row, el => el.w_full().h(this.controlRowHeight).min_h(this.controlRowHeight).flex_none().px(8).rounded(5))
      .when(!row && !iconOnly, el => el.px(quiet ? 4 : 9).py(6).min_h(32).rounded(6).border_1()
        .border_color(focus.is_focused() ? t.accent : quiet ? "#00000000" : t.border))
      .when(iconOnly, el => el.size(iconButtonSize).min_w(iconButtonSize).min_h(iconButtonSize).p(0).flex_none().rounded(6)
        .border_1().border_color(focus.is_focused() ? t.accent : "#00000000"))
      .text_color(disabled ? t.dim : (active ? t.accent : iconOnly ? t.muted : t.foreground))
      .when(active && !row && !disabled, el => el.bg(t.selected))
      .when(focus.is_focused(), el => el.bg(t.selected))
      .hover(el => el.when(!disabled, item => item.bg(t.hover).text_color(t.foreground)))
      .active(el => el.when(!disabled, item => item.bg(t.selected)))
      .on_click((_e, cx) => { cx.stop_propagation(); if (disabled || (context && (!this.issueContextCurrent(context) || !this.issueActionKey()))) return; this.interact(); action(cx); });
    const glyph = icon ? svg(`${ROOT}/icons/${icon}.svg`).size(iconSize).flex_none() : null;
    button.child(iconOnly ? glyph : row ? h_flex().w_full().h_full().min_w(0).gap(6).items_center()
      .when(!!glyph, el => el.child(glyph))
      .child(div().min_w(0).flex_1().truncate().child(title))
      .when(!!trailing, el => el.child(div().flex_none().text_color(t.muted).child(trailing)))
      .when(!!trailingIcon, el => el.child(svg(`${ROOT}/icons/${trailingIcon}.svg`).size(16).flex_none().text_color(t.muted)))
      : glyph ? h_flex().min_w(0).gap(6).items_center()
        .child(glyph).child(div().min_w(0).truncate().child(title)) : title);
    // Native Button drops its focus handle while disabled. Keep existing focus
    // through an in-flight action without making the disabled button a tab stop.
    return disabled && focus.is_focused() ? div().flex().items_stretch().track_focus(focus).tab_stop(false).child(button) : button;
  }
  toggle(id, title, pressed, onChange, t, label, help, disabled = false, options = {}) {
    const { row = false, trailing = "", trailingIcon = "", rowHeight = this.controlRowHeight, quiet = false, icon = "", iconOnly = false, focusLabel = label } = options;
    const focus = this.actionFocus[id];
    const context = ISSUE_ACTIONS.has(id) ? this.issueContext() : null;
    if (iconOnly && focus.is_focused()) this.focusCaption = focusLabel;
    const toggle = Toggle.new(id).track_focus(focus).tab_index(0).tab_stop(!disabled).accessibility_label(label)
      .when(!!help, el => el.tooltip(help)).pressed(!!pressed).disabled(disabled)
      .when(!disabled, el => el.cursor_pointer())
      .when(row, el => el.w_full().h(rowHeight).min_h(rowHeight).flex_none().px(8).rounded(5))
      .when(!row && !iconOnly, el => el.px(quiet ? 4 : 9).py(6).min_h(32).rounded(6).border_1()
        .border_color(focus.is_focused() ? t.accent : quiet ? "#00000000" : t.border))
      .when(iconOnly, el => el.size(32).min_w(32).min_h(32).p(0).rounded(6).border_1()
        .border_color(focus.is_focused() ? t.accent : "#00000000"))
      .text_color(disabled ? t.dim : (!row && pressed && !quiet ? t.accent : iconOnly ? t.muted : t.foreground))
      .when((!row && pressed && !quiet) || focus.is_focused(), el => el.bg(t.selected))
      .hover(el => el.when(!disabled, item => item.bg(t.hover).text_color(t.foreground)))
      .on_change((value, cx) => { cx.stop_propagation(); if (disabled || (context && (!this.issueContextCurrent(context) || !this.issueActionKey()))) return; this.interact(); onChange(value, cx); })
      .child(iconOnly ? svg(`${ROOT}/icons/${icon}.svg`).size(16).flex_none() : row ? h_flex().w_full().h_full().min_w(0).gap(6).items_center()
        .when(!!icon, el => el.child(svg(`${ROOT}/icons/${icon}.svg`).size(16).flex_none()))
        .child(div().min_w(0).flex_1().truncate().child(title))
        .when(!!trailing, el => el.child(div().flex_none().text_color(pressed && !disabled ? t.accent : t.muted).child(trailing)))
        .when(!!trailingIcon, el => el.child(svg(`${ROOT}/icons/${trailingIcon}.svg`).size(16).flex_none().text_color(t.muted))) : title);
    // herdr-app 0.1.10 doesn't forward Toggle tooltips; a supported div owns the help text.
    return div().flex_none().when(row, el => el.w_full().h(rowHeight))
      .when(!disabled, el => el.cursor_pointer())
      .when(!!help, el => el.tooltip(help)).child(toggle);
  }
  text(text, t) { return div().min_w(0).text_color(t.foreground).child(text); }
  get contentInset() { return this.width < 340 ? 12 : 16; }
  get secondaryTextSize() { return Math.max(11, settings().ui_font_size - 1); }
  get monoFont() { return settings().font_family || "Geist Mono"; }
  get controlRowHeight() { return Math.max(32, Math.ceil((settings().ui_font_size * 1.5 + 8) / 4) * 4); }
  get chromeHeight() { return Math.max(40, Math.ceil((settings().ui_font_size * 1.5 + 14) / 4) * 4); }
  get filterHeight() { return Math.max(36, this.controlRowHeight); }
  get resultHeaderHeight() { return Math.max(32, Math.ceil((this.secondaryTextSize * 1.4 + 6) / 4) * 4); }
  get issueRowHeight() {
    return Math.ceil((this.resultHeaderHeight + Math.ceil(settings().ui_font_size * 1.4) + 4 + 8 + 1) / 4) * 4;
  }

  resultRow(element, t) {
    return element.relative().v_flex().items_start().w_full().h(this.issueRowHeight).min_w(0)
      .px(this.contentInset - 1).pt(4).pb(8).gap(0).border_b(1).border_color(t.border);
  }

  resultSummary(key, row, available, t) {
    return div().id(`issue-summary-${key}`).w_full().min_w(0).truncate().line_height(1.4)
      .text_color(available && row?.summary ? t.foreground : t.muted)
      .when(available && !!row?.summary, el => el.tooltip(row.summary.slice(0, 512)))
      .child(!available ? "No longer matches" : row?.summary || this.rowPlaceholder(key));
  }

  freshnessLabel(issue) {
    const at = issue?.fetchedAt || issue?.loadedAt;
    if (!Number.isFinite(at)) return "Freshness unavailable";
    const timestamp = new Date(at).toISOString();
    const time = `${timestamp.slice(11, 16)} UTC`;
    return `Fetched ${displayDate(timestamp)} · ${time}`;
  }
  message(title, detail, t) {
    return v_flex().px(this.contentInset).py(16).gap(8).child(div().font_semibold().child(title))
      .when(!!detail, el => el.child(div().text_color(t.muted).line_height(1.5).child(detail)));
  }

  optionDivider(t) { return div().h(1).flex_none().my(4).mx(8).bg(t.border); }

  keycap(key, t) {
    return div().flex_none().px(5).py(1).min_w(20).rounded(4).border_1().border_color(t.border)
      .bg(t.chrome).text_color(t.muted).font_family(this.monoFont).text_size(this.secondaryTextSize).child(key);
  }

  renderShortcuts(t, more = false) {
    const rows = more ? [
      ["⌘/Ctrl+Enter", "Open in Jira"], ["Y / ⇧Y", "Copy key / link"], ["C / D", "Comments / details"],
      ["R", "Refresh"], ["F / N", "Follow / next unread"], ["Tab / ⇧Tab", "Next / previous control"],
      ["O / ?", "Options / keys"], ["PgUp / PgDn", this.nativeInput ? "Page text or results" : "Page results"],
      ["Home / End", this.nativeInput ? "Top / bottom" : "First / last result"],
    ] : [
      ["/", "Find an issue"], ["↑ ↓", "Choose an issue"], ["Enter", "Read in Peek"],
      ...(this.nativeInput ? [["Space / ⇧Space", "Page the reader"]] : []),
      ["Esc", "Back one step"], ["P / K", "Pin / return"],
    ];
    return v_flex().id(more ? "jira-more-shortcuts" : "jira-shortcuts").min_w(0).gap(8)
      .children(rows.map(([key, label]) => h_flex().min_w(0).gap(8).items_start()
        .child(div().flex_1().min_w(0).child(label)).child(this.keycap(key, t))))
      .when(!more, el => el.child(div().pt(4).text_size(this.secondaryTextSize).text_color(t.muted).child("Letter keys stay text in search.")));
  }

  helpSectionId(title) { return `help-section-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`; }

  helpSections(topic = this.helpTopic) {
    const issueHelp = [
      ["Keyboard", "Find, read, then return. Enter stays inside Peek. Escape goes back one step, then to the terminal. P pins or unpins; K returns to the pin."],
      ["More shortcuts", "Issue actions and navigation. Letter keys work while reading or browsing, not while typing."],
      ["Issues", "Expand Issues to filter detected tickets. Editing the filter previews a match; the selected ticket stays highlighted in its original row. Pin and Copy link belong to the selected result; Refresh sits beside the fetch time, and the issue key opens Jira. There is no duplicate key row below the results. Its complete title scrolls with the reader. Click rows or use arrows to preview; Enter reads. While Paused, new matches appear automatically at the bottom without selecting them or scrolling the list. Loaded fields remain searchable; results that stop matching or leave the 200-issue history disappear. Enter a Jira key or URL for direct lookup; this does not search all of Jira. The × clears the filter."],
      ["Open in Jira", "Cmd+Enter or Ctrl+Enter opens the viewed issue in your browser while reading or browsing. Clicking the issue key does the same. Enter alone keeps you in Peek; Enter on a focused button activates that button."],
      ["Following / Paused", "The icon shows the next action: pause while Following, play while Paused. Click the icon or press F to switch. Hover for the action and shortcut. Following selects new issue keys as they appear in the terminal. Paused keeps your selection while new matches appear at the bottom. The list keeps its browsing height as arrivals continue. The +new badge explicitly reads one unread issue, including outside your filter, and keeps Paused. Reopening Issues restores your filter and browsing order. Clear filter shows all retained keys; resume Follow to select the latest issue, clear the filter and restore latest-first order."],
      ["Keyboard browsing", "While filtering, arrows preview issues and Page Up/Down move by a visible group. Enter reads the selection and stays inside Peek. Click Issues to enter Peek before typing. Once Peek has keyboard focus, use Cmd+F or Tab to reach the filter. Stock installation does not provide a terminal-to-panel entry shortcut."],
      ["Keyboard scrolling", this.nativeInput
        ? "Page Up/Down moves through the reader or Help. Home/End reaches the top or bottom. Space/Shift+Space pages a focused text pane; Space on a button still activates it. Tab reveals each control. Hiding and reopening keeps your place."
        : "Keyboard scrolling and reading-position restoration after hiding are unavailable on this host. Use the wheel or trackpad for long text, or Cmd+Enter / Ctrl+Enter to open Jira. Issue-list paging works independently."],
    ];
    const optionHelp = [
      ["Refresh", "Load the latest details for the selected issue from Jira. The last successful fetch time stays above the reader; Refresh sits beside the fetch time above the reader. The current details and that time stay visible if a refresh fails."],
      ["Copy key", "Copy the selected issue key, such as ABC-42, to the clipboard. Copy key is grouped with Copy link and Pin on the right. Y also copies the key while reading or browsing; a check mark confirms the copy."],
      ["Copy link", "Copy the selected issue's Jira URL to the clipboard. The chain icon beside the issue key does the same; a check mark confirms the copy. Shift+Y also copies the link while reading."],
      ["Pin issue", "Press P or the pin beside the issue actions. Press it again on the pinned issue to unpin; pinning another issue moves the pin immediately. A matching pin stays visible at the top of Issues while the list scrolls; a nonmatching pin stays available with Return. Each terminal has one temporary pin. It disappears on reconnect, Clear cache, source eviction or panel close; hiding preserves the session."],
      ["Return to pin", "Press K or Return in the footer to read the pinned issue. Your filter stays, Follow pauses, and other unread issues stay unread. P and K remain text while typing. Copy, Open and Refresh target the viewed issue. Details may reload; scroll restoration depends on your host."],
      ["Keep this terminal", "Keep reading issue keys from the same terminal when you switch terminals, tabs, or panes. Turn this off to read from the terminal you are working in. Following/Paused controls automatic issue selection. This is separate from pinning an issue."],
      ["Highlight source", this.highlightSupported && !this.highlightError
        ? "Mark the selected issue key inside the terminal text. Turn it off to remove the mark. Paused keeps the same issue marked."
        : !this.highlightSupported
          ? "Mark the selected issue key inside the terminal text. Unsupported means your Herdr app cannot display these marks."
          : "The terminal mark could not be shown. Turn Highlight source off and on to retry."],
      ["Scan screen", "Look for Jira issue keys in the visible terminal text now. While Paused, new matches appear at the bottom automatically."],
      ["Read history", "Look for Jira issue keys in up to 200 recent terminal lines, including text that has scrolled out of view."],
      ["Clear list", "Forget collected issues, the filter and issue pin for this terminal only. A fresh screen read sets the cutoff: keys visible then stay ignored until a complete read observes them absent and they reappear. Output arriving before that read belongs to the baseline. Following or Paused is preserved; Paused collects new keys unread until you choose one. Scan screen, Read history or direct lookup deliberately restores older issues. A screen over 200 keys or the read-size limit waits for a complete baseline. This does not clear caches or change the connection."],
      ["Auto-refresh issue", "Update the selected issue at most once per minute. Five idle minutes pause only this panel, keeping your saved choice. Paused → On resumes here without saving; On → Off turns refresh off for every panel. To turn it off while Paused, resume then turn it off. Another panel turning it on does not resume a panel paused for inactivity. Finding terminal keys runs separately."],
      ["Fields", "Choose which issue fields to show, change their labels, and arrange them in the reader."],
      ["Connection", "Set up Jira, choose an existing configuration folder, or reconnect to your current Jira connection."],
      ["Clear cache", "Remove locally saved issue data so it can be fetched again. Keeps your Jira connection and field settings."],
    ];
    return ({
      peek: [...issueHelp, ...optionHelp],
      options: [...issueHelp.slice(0, 2), ...optionHelp, ...issueHelp.slice(2)],
      fields: [
        ["Place fields", "Header pins compact values above the reader. Body shows full text in order. Details groups secondary fields behind a disclosure. Hidden removes a field from the reader."],
        ["Choose and label", "Add a standard field ID such as priority, issuetype or duedate, or a customfield_ ID from Jira. Edit its display label and use the arrows to reorder it within its section. Comments can appear in Body or Details."],
        ["Apply or cancel", "Apply saves this connection's layout and rebuilds the reader. Back or Escape discards edits. Empty values stay out of the layout unless Show empty fields is enabled. The issue key and Open in Jira remain available."],
        ["Ask your agent", "Copy config path gives your agent the shared JSON file. Its edits reload automatically. If it changes while you are editing here, go Back and reopen Fields."],
      ],
      connection: [
        ["Choose a connection", "Set up Jira saves your connection locally. Choose existing folder loads a folder containing your private config.sh."],
        ["Reconnect", "Reloads the selected configuration. Jira access is limited to its allowed project keys."],
        ["Find issues", "Jira keys must be in an allowed project and appear in terminal text, or enter a Jira key for direct lookup."]
      ],
      setup: [
        ["Connection details", "Enter your Jira Cloud site, account email, API token, and allowed project keys. A scoped token also needs its Cloud ID."],
        ["Test & save", "Verifies the account, then saves the connection in private local files. Reading issues also requires issue read permission."],
        ["Cancel", "Discards this setup form. Visiting Help keeps your entered values in memory."]
      ]
    })[topic] || [];
  }

  renderHelp(root, t) {
    const groups = this.helpSections();
    const nested = !!(this.setup || this.fieldEditor || this.connectionSettings);
    const title = ({ fields: "Fields help", connection: "Connection help", setup: "Setup help" })[this.helpTopic];
    const backTitle = this.setup ? "Back to setup" : this.fieldEditor ? "Back to Fields" : this.connectionSettings ? "Back to Connection"
      : "Back to Issues";
    const content = v_flex().id(`jira-peek-help-content-${this.helpTopic}`).flex_1().min_h(0).min_w(0).overflow_y_scrollbar().px(this.contentInset - 9).py(8)
      .track_focus(this.helpHandle).tab_index(0).role("pane").accessibility_label("Help topics")
      .border_1().border_color(this.helpHandle.is_focused() ? t.accent : "#00000000");
    const groupLabels = { Issues: "Reading", Refresh: "Issue actions", "Keep this terminal": "Terminal", "Auto-refresh issue": "Settings" };
    for (const [title, description] of groups) {
      const expanded = this.helpExpanded === title;
      const tokenGuide = (this.helpTopic === "setup" && title === "Connection details") ||
        (this.helpTopic === "connection" && title === "Choose a connection");
      if (!nested && groupLabels[title]) content.child(div().px(8).pt(16).pb(4)
        .text_size(this.secondaryTextSize).font_semibold().text_color(t.muted).child(groupLabels[title]));
      content.child(v_flex().id(`${this.helpSectionId(title)}-group`).flex_none().min_w(0)
        .child(this.toggle(this.helpSectionId(title), title, expanded, (open, cx) => {
          this.helpExpanded = open ? title : null; cx.notify();
        }, t, `${expanded ? "Hide" : "Show"} ${title} help`,
        `${expanded ? "Collapse" : "Expand"} help`, false,
        { row: true, icon: expanded ? "chevron-down" : "chevron-right" }))
        .when(expanded, el => el.child(v_flex().id(`${this.helpSectionId(title)}-body`).min_w(0).px(8).pt(8).pb(12).gap(8)
          .child(title === "Keyboard" || title === "More shortcuts" ? this.renderShortcuts(t, title === "More shortcuts") : div().text_color(t.muted).line_height(1.5).child(description))
          .when(tokenGuide, body => body.child(this.button("help-token-link", "API token guide ↗",
            cx => cx.open_url("https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/"), t,
            { help: "API token guide" })))))
        .when(expanded, el => el.child(this.optionDivider(t))));
    }
    return root.child(v_flex().id("jira-peek-help").flex_1().min_h(0).min_w(0)
      .when(nested, el => el.child(h_flex().flex_none().px(10).py(6).gap(8).items_center().border_b(1).border_color(t.border)
        .child(this.button("help-back", backTitle, cx => this.closeHelp(cx), t, { label: `${backTitle}; close help` }))
        .child(div().font_semibold().child(title))))
      .child(content));
  }

  renderOptions(root, t, sourceLabel, selected, link, availability) {
    return root.child(v_flex().id("jira-peek-options").flex_1().min_h(0).overflow_y_scrollbar().px(this.contentInset - 8).py(8)
      .when(!!(this.fieldFileError || this.preferenceError), el => el.child(div().py(6).text_color(t.blocked).child(this.fieldFileError || this.preferenceError)))
      .child(this.button("refresh", "Refresh", cx => this.runOption(c => this.refresh(c), cx), t, {
        row: true, trailing: "R", disabled: !availability.refresh, label: selected ? `Refresh ${selected}` : "Refresh selected issue",
        help: "Refresh issue (R)",
      }))
      .child(this.button("copy-key", "Copy key", cx => this.runOption(c => this.copyIssue(false, c), cx), t,
        { row: true, trailing: "Y", disabled: !availability["copy-key"], label: "Copy issue key", help: "Copy key (Y)" }))
      .child(this.button("copy-link", "Copy link", cx => this.runOption(c => this.copyIssue(true, c), cx), t,
        { row: true, trailing: "⇧Y", disabled: !availability["copy-link"], label: "Copy issue link", help: "Copy link (Shift+Y)" }))
      .child(this.optionDivider(t))
      .child(this.toggle("pin", "Keep this terminal", this.model.pinned, (pinned, cx) => {
        if (!this.model.source) return;
        this.model.pinned = pinned; this.adoptSource(cx); cx.notify();
      }, t, "Keep reading issue keys from this terminal", `Keep terminal: ${sourceLabel}`, !availability.pin, { row: true, trailing: this.model.pinned ? "On" : "Off" }))
      .child(this.toggle("highlight-source", "Highlight source", this.highlightSupported && !this.demo && this.highlightSource !== false,
        (_value, cx) => this.toggleHighlight(cx), t, "Highlight selected key in source terminal",
        this.highlightHelp,
        !availability["highlight-source"], { row: true, trailing: !this.highlightSupported ? "Unsupported" : this.demo ? "Unavailable" : this.highlightError ? "Failed" : this.highlightSource !== false ? "On" : "Off" }))
      .child(this.button("scan", "Scan screen", cx => this.runOption(c => this.scan(c, { bypass: true }), cx), t, {
        row: true, disabled: !availability.scan, label: "Scan current terminal screen for issue keys",
        help: "Find keys on screen",
      }))
      .child(this.button("history", this.historyRead ? "Reading history…" : "Read history", cx => this.runOption(c => this.history(c), cx), t, {
        row: true, disabled: !availability.history, label: "Read available terminal history",
        help: "Find keys in history (up to 200 lines)",
      }))
      .child(this.button("clear-list", "Clear list", cx => this.clearList(cx), t, {
        row: true, disabled: !availability["clear-list"], label: "Clear discovered issues for this terminal",
        help: "Clear this terminal’s list and pin",
      }))
      .child(this.optionDivider(t))
      .child(this.toggle("live-refresh", "Auto-refresh issue", this.live, (_value, cx) => this.toggleLive(cx), t,
        this.autoRefreshPreference && this.idlePaused ? "Resume auto-refresh in this panel" : "Automatically refresh selected issue",
        this.autoRefreshPreference && this.idlePaused ? "Resume auto-refresh here" : this.live ? "Turn off auto-refresh for all panels" : "Refresh issue every minute",
        !availability["live-refresh"], { row: true, trailing: this.live ? "On" : this.autoRefreshPreference && this.idlePaused ? "Paused" : "Off" }))
      .child(this.button("fields", "Fields", cx => this.openFields(cx), t, {
        row: true, disabled: !availability.fields, trailingIcon: "chevron-right", label: "Configure field placement and visibility",
        help: "Arrange reader fields",
      }))
      .child(this.button("connection", "Connection", cx => this.openConnection(cx), t, {
        row: true, disabled: !availability.connection, trailingIcon: "chevron-right", label: "Jira connection settings",
        help: "Manage Jira connection",
      }))
      .child(this.button("clear-cache", this.clearing ? "Clearing cache…" : "Clear cache", cx => this.runOption(c => this.clearCache(c), cx), t, {
        row: true, disabled: !availability["clear-cache"], label: "Clear local Jira issue cache",
        help: "Clear issue cache and reconnect",
      }))
      .child(this.optionDivider(t))
      .child(this.button("help", "Help", cx => this.openHelp(cx), t, {
        row: true, icon: "help", trailing: "?", help: "Help (?)",
      })));
  }

  syncDisclosures() {
    const disclosureIdentity = `${this.model.source || "none"}:${this.model.current?.selected || "none"}`;
    if (this.disclosureIdentity !== disclosureIdentity) {
      this.disclosureIdentity = disclosureIdentity; this.commentsOpen = false; this.detailsOpen = false;
    }
  }

  renderHeader(t) {
    const nested = !!(this.setup || this.connectionSettings || this.fieldEditor);
    const secondary = !nested && !!(this.helpTopic || (this.moreOpen && this.model.config));
    const header = h_flex().id("jira-peek-title").w_full().min_w(0).h(this.chromeHeight).flex_none().px(this.contentInset).gap(8)
      .items_center().bg(t.chrome).border_b(1).border_color(t.border);
    if (secondary) {
      const back = this.model.config ? "← Issues" : "← Jira Peek";
      header.child(this.button(this.helpTopic ? "help-back" : "options-back", back,
        cx => this.helpTopic ? this.closeHelp(cx) : this.closeOptions(cx), t,
        { quiet: true, label: this.model.config ? "Back to Issues" : "Back to Jira Peek", help: "Back (Esc)" }).ml(-5))
        .child(div().min_w(0).flex_1().font_semibold().child(this.helpTopic ? "Help" : "Options"));
      if (this.helpTopic) return header.when(!!this.model.config, el => el.child(this.button("more", "Options", cx => this.openOptions(cx), t,
        { icon: "more", iconOnly: true, focusLabel: "Options · O", help: "Options (O)" })));
      return header;
    }
    return header.child(h_flex().min_w(0).flex_1().gap(8).items_center()
      .child(div().min_w(0).truncate().font_semibold().child("Jira Peek")))
      .child(h_flex().flex_none().gap(0).mr(-6).items_center()
        .child(this.button("more", "Options", cx => this.openOptions(cx), t, {
          icon: "more", iconOnly: true,
          focusLabel: "Options · O",
          help: "Options (O)", disabled: nested || !this.model.config,
        }))
        .when(nested || !this.model.config, el => el.child(this.button("help", "Help", cx => this.openHelp(cx), t, {
          icon: "help", iconOnly: true,
          focusLabel: "Help · ?",
          label: this.helpTopic ? "Close Jira Peek help" : "Open Jira Peek help",
          help: "Help (?)", disabled: !!this.setup?.busy || !!this.fieldEditor?.busy,
        })))
        .when(!nested && !this.helpTopic, el => el.child(this.button("hide", "×", cx => this.hide(cx), t, {
          icon: "close", iconOnly: true,
          label: "Hide Jira Peek", help: "Hide Jira Peek",
          disabled: !props()?.overlay && !this.attachedPanel(),
        }))));
  }

  render(cx) {
    this.focusCaption = "";
    if (!this.setup && !this.connectionSettings) this.adoptSource(cx);
    this.consumeBrowseRequest(cx);
    this.syncHighlight(true);
    this.syncDisclosures();
    const t = theme(), s = this.model.current, config = this.model.config;
    const selected = s?.selected;
    const pinnedReturn = !!s?.pinnedIssueKey && (this.issuesExpanded || s.pinnedIssueKey !== selected);
    if (!this.moreOpen && !this.helpTopic && this.actionFocus["pinned-return"].is_focused() && !pinnedReturn) this.restoreMainFocus();
    const source = this.demo ? { title: "Catalog · feature/preserve-filters", status: "working" }
      : panes().find(p => p.terminal === this.model.source) || terminals().find(t => t.address === this.model.source);
    const sourceLabel = this.demo ? source.title : this.model.source === "manual" ? "Manual Jira lookup"
      : source?.title || this.model.source || "No terminal selected";
    const link = config && selected && issueLink(config.base, selected, config.projects);
    const optionAvailability = this.optionAvailability();
    // Inherit Herdr's UI size throughout; the host applies zoom itself.
    const context = this.issueContext();
    const root = v_flex().id("jira-peek").size_full().min_h(0).min_w(0).overflow_hidden()
      .bg(t.background).text_color(t.foreground).text_size(settings().ui_font_size)
      .track_focus(this.rootFocus)
      .on_size_change((size, cx) => {
        // Layout dimensions include Herdr's zoom; builder lengths do not.
        // Keep responsive breakpoints and list budgets in the same units.
        const zoom = Number(settings().zoom), scale = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
        const width = Math.round(size.width / scale * 100) / 100;
        const height = Math.round(size.height / scale * 100) / 100;
        if (width !== this.width || height !== this.height) {
          this.width = width; this.height = height;
          cx.notify();
        }
      })
      .on_key_down((e, cx) => {
        this.keyDown(e, cx, context);
      })
      .on_mouse_down_out((_e, cx) => cx.notify())
      .child(this.renderHeader(t));

    const auxiliary = !!(this.helpTopic || this.setup || this.connectionSettings || this.fieldEditor || (this.moreOpen && config));
    const content = v_flex().id("jira-peek-content").relative().flex_1().min_h(0).min_w(0);
    // Retain native scroll state while auxiliary screens cover the reader.
    // Visibility hides descendants from hit testing and focus traversal without
    // collapsing the scroll viewport; display:none or unmounting resets it.
    const peek = v_flex().id("jira-peek-body").size_full().min_h(0).min_w(0)
      .when(auxiliary, el => el.invisible());
    // Disconnected entry has no reading position; omit its duplicate setup action.
    content.child(auxiliary && !config ? peek : this.renderPeek(peek, t, sourceLabel));
    if (auxiliary) {
      const surface = v_flex().id("jira-peek-surface").absolute().inset_0().min_h(0).min_w(0).bg(t.background)
        // Help can use the quiet footer without resizing the retained reader.
        // Restore the caption strip when its header icon owns focus.
        .when(!!this.helpTopic && !this.focusCaption, el => el.bottom(-this.chromeHeight));
      if (this.helpTopic) content.child(this.renderHelp(surface, t));
      else if (this.setup) content.child(this.renderSetup(surface, t));
      else if (this.fieldEditor) content.child(this.renderFields(surface, t));
      else if (this.connectionSettings) content.child(this.renderConnection(surface, t));
      else content.child(this.renderOptions(surface, t, sourceLabel, selected, link, optionAvailability));
    }
    const rows = this.model.rows();
    const reading = !auxiliary && !this.typing && this.issueActionKey() && this.readerHandle.is_focused();
    const hint = this.nativeInput ? "Space Scroll · / Find · Esc Back" : "/ Find · Esc Back";
    const caption = this.focusCaption || (!auxiliary && (this.typing || this.handle.is_focused())
      ? (rows.length ? `${this.height < 500 ? "↑↓ Select" : "↑↓ Preview"} · ↵ Read` : "Enter a key to look up") : "");
    // The invisible reading hint reserves the same wrapped height on focus and
    // blur. A short icon label must not resize the reader or move its passage.
    return root.child(content).child(h_flex().id("jira-control-hint").flex_none().h(this.chromeHeight).min_w(0).px(this.contentInset).gap(8).items_center().bg(t.chrome).border_t(1).border_color(t.border).text_size(this.secondaryTextSize).text_color(t.muted)
      .when(!!this.helpTopic && !this.focusCaption, el => el.invisible())
      .child(!auxiliary && pinnedReturn ? this.button("pinned-return",
        h_flex().min_w(0).gap(6).items_center()
          .child(div().flex_1().min_w(0).truncate().child(`Return to ${s.pinnedIssueKey}`)).child(this.keycap("K", t)),
        cx => this.returnToPin(cx), t, { quiet: true, label: `Return to pinned issue ${s.pinnedIssueKey}`,
          help: `Return to ${s.pinnedIssueKey} (K)` }).flex_1().min_w(0)
        : div().relative().flex_1().min_w(0)
        .child(div().id("jira-reader-hint").when(!reading || !!caption, el => el.invisible()).child(config && selected ? hint : " "))
        .when(!!caption, el => el.child(div().id("jira-focus-caption").absolute().inset_0().child(caption)))
        .when(!reading && !caption && !auxiliary, el => el.child(div().absolute().inset_0().child(config ? "/ Find an issue" : "Jira beside your work"))))
      .when(!auxiliary, el => el.child(this.button("shortcuts", config ? "? Keys" : "? Help", cx => this.openHelp(cx, true), t, {
        quiet: true, label: config ? "Keyboard shortcuts" : "Connection help",
        help: config ? "Keyboard shortcuts (?)" : "Connection help",
      }).flex_none())));
  }

  fieldButton(id, title, action, t, disabled = false, active = false, label = title) {
    disabled ||= !!this.fieldEditor?.busy;
    return Button.new(id).tab_index(0).tab_stop(!disabled).disabled(disabled)
      .accessibility_label(label).tooltip(label).h(26).px(6).rounded(5)
      .bg(active ? t.selected : t.background).text_color(disabled ? t.dim : active ? t.accent : t.foreground)
      .hover(el => el.bg(t.hover)).focus(el => el.border_1().border_color(t.accent))
      .on_click((_e, cx) => { cx.stop_propagation(); if (!disabled) { this.interact(); action(cx); } }).child(title);
  }

  renderFields(root, t) {
    const editor = this.fieldEditor;
    root.child(h_flex().flex_none().px(this.contentInset).py(8).gap(8).items_center().border_b(1).border_color(t.border)
      .child(this.button("fields-back", "Back", cx => this.closeFields(cx), t, { disabled: editor.busy, label: "Back to Options; discard field changes" }))
      .child(div().flex_1().font_semibold().child("Fields"))
      .child(this.button("fields-apply", editor.busy ? "Saving…" : "Apply", cx => this.applyFields(cx), t, { active: true,
        disabled: editor.busy || !!this.fieldFileError || editor.fileText !== this.fieldFileText || editor.context !== this.model.config?.context, label: "Apply field layout" })));
    const body = v_flex().id("jira-field-editor").flex_1().min_h(0).min_w(0).overflow_y_scrollbar().px(this.contentInset).py(16).gap(12)
      .child(div().text_color(t.muted).child("Arrange this connection's reader. The issue key stays visible."))
      .child(this.toggle("fields-empty", "Show empty fields", editor.showEmpty, (value, cx) => { editor.showEmpty = value; cx.notify(); }, t,
        "Show empty fields", "Show empty fields as a dash", editor.busy, { row: true, trailing: editor.showEmpty ? "On" : "Off" }));
    if (!this.demo) body.child(this.button("fields-path", "Copy config path", cx => {
      cx.write_to_clipboard(this.fieldFilePath()); editor.notice = "Config path copied."; cx.notify();
    }, t, { row: true, help: "Copy field config path" }));
    if (editor.notice) body.child(div().text_color(t.muted).child(editor.notice));
    if (editor.error) body.child(div().text_color(t.blocked).child(editor.error));
    else if (this.fieldFileError) body.child(div().text_color(t.blocked).child(this.fieldFileError));
    else if (editor.fileText !== this.fieldFileText) body.child(div().text_color(t.blocked).child("Fields changed elsewhere. Go Back and reopen Fields before applying."));
    else if (editor.context !== this.model.config?.context) body.child(div().text_color(t.blocked).child("The connection changed. Go back and reconnect before editing fields."));
    for (const section of FIELD_SECTIONS) {
      const fields = editor.fields.filter(field => field.section === section);
      if (!fields.length) continue;
      body.child(div().font_semibold().child(section[0].toUpperCase() + section.slice(1)));
      for (const [index, field] of fields.entries()) {
        body.child(v_flex().id(`edit-field-${field.id}`).min_w(0).gap(5).pb(8).border_b(1).border_color(t.border)
          .child(h_flex().gap(3).items_center()
            .child(div().flex_1().min_w(0).h(30).px(6).border_1().border_color(t.border).rounded(5)
              .child(Input.new(editor.labels.get(field.id)).disabled(editor.busy).h_full().accessibility_label(`Display label for ${field.id}`)))
            .child(this.fieldButton(`field-up-${field.id}`, "↑", cx => this.moveField(field.id, -1, cx), t, index === 0, false, `Move ${field.label} up in ${section}`))
            .child(this.fieldButton(`field-down-${field.id}`, "↓", cx => this.moveField(field.id, 1, cx), t, index === fields.length - 1, false, `Move ${field.label} down in ${section}`))
            .child(this.fieldButton(`field-remove-${field.id}`, "×", cx => {
              editor.fields = editor.fields.filter(item => item.id !== field.id);
              editor.labels.get(field.id).release(); editor.labels.delete(field.id); editor.add.focus(); cx.notify();
            }, t, false, false, `Remove ${field.label} from the layout`)))
          .child(div().text_color(t.muted).child(field.id))
          .child(h_flex().gap(3).flex_wrap().children(FIELD_SECTIONS.map(destination =>
            this.fieldButton(`field-place-${field.id}-${destination}`, destination[0].toUpperCase() + destination.slice(1), cx => {
              field.section = destination; cx.notify();
            }, t, field.id === "comments" && destination === "header", section === destination, `Place ${field.label} in ${destination}`)))));
      }
    }
    return root.child(body
      .child(div().font_semibold().child("Add a field"))
      .child(h_flex().gap(6).items_center()
        .child(div().flex_1().min_w(0).h(32).px(6).border_1().border_color(t.border).rounded(5)
          .child(Input.new(editor.add).disabled(editor.busy).h_full().accessibility_label("Jira field ID")))
        .child(this.button("fields-add", "Add", cx => this.addField(cx), t, { disabled: editor.busy })))
      .child(div().text_color(t.muted).child("Use a standard ID such as priority or duedate, or a customfield_ ID from Jira."))
      .child(this.button("fields-reset", "Reset to configured fields", cx => this.resetFields(cx), t,
        { disabled: editor.busy || editor.context !== this.model.config?.context })));
  }

  renderConnection(root, t) {
    const config = this.model.config;
    return root.child(v_flex().flex_1().min_h(0).overflow_y_scrollbar().px(this.contentInset - 8).py(8).gap(4)
      .child(div().px(8).py(8).flex_none().font_semibold().child("Connection"))
      .child(this.button("settings-back", this.connectionParent === "options" && config ? "Back to Options" : "Back to Connect Jira", cx => this.closeSettings(cx), t, { row: true }))
      .child(this.button("setup-open", "Set up Jira", cx => this.openSetup(cx), t, { active: true, row: true }))
      .child(this.button("settings-choose", "Choose existing folder…", cx => this.chooseConfig(cx), t, { row: true }))
      .child(this.button("settings-reconnect", this.loading ? "Connecting…" : "Reconnect", cx => this.reconnect(cx), t,
        { row: true, disabled: !!this.loading, help: "Reload connection" }))
      .when(!this.loading && !!this.connectionMessage, el => el.child(div().flex_none().px(8).py(4)
        .text_color(this.loading ? t.muted : this.error ? t.blocked : t.foreground).child(this.connectionMessage))));
  }

  renderHeaderField(field, t, stacked = false) {
    return h_flex().id(`header-field-${field.id}`).min_w(0).gap(4).items_center().text_size(this.secondaryTextSize)
      .when(stacked, el => el.w_full()).when(!stacked, el => el.max_w(240))
      .tooltip(`${field.label}: ${field.value.slice(0, 512)}`)
      .when(field.id !== "status" || field.label !== "Status", el => el.child(div().flex_none().max_w(100).truncate().text_color(t.muted).child(`${field.label}:`)))
      .child(div().flex_1().min_w(0).truncate().text_color(field.id === "status" ? statusColor(field.value, t) : t.foreground).child(displayDate(field.value).replace(/\s+/g, " ")));
  }

  renderField(field, issue, t, hideLabel = false) {
    if (field.id === "comments") return this.renderComments(issue, t, field.label);
    return v_flex().id(`reader-field-${field.id}`).min_w(0).gap(4)
      .when(!hideLabel, el => el.child(div().text_size(this.secondaryTextSize).text_color(t.muted).child(field.label)))
      .child(div().min_w(0).line_height(1.55).text_color(field.id === "status" ? statusColor(field.value, t) : t.foreground)
        .when(field.id === "summary", el => el.font_semibold())
        .child(displayDate(field.value)))
      .when(field.unsupportedContent || field.truncated, el => el.child(div().text_color(t.muted)
        .child(field.unsupportedContent ? "Some content is unsupported here. Open in Jira for the full field." : "This field is shortened. Open in Jira for the full field.")));
  }

  renderComments(issue, t, label) {
    const count = issue.commentsTotal ?? issue.comments?.length ?? 0;
    return v_flex().id("reader-field-comments").min_w(0).gap(8).pt(8).border_t(1).border_color(t.border)
      .child(this.button("comments-toggle", issue.commentsDeferred ? label : `${label} (${count})`, cx => this.toggleComments(cx), t, {
        row: true, trailing: "C", icon: this.commentsOpen ? "chevron-down" : "chevron-right",
        active: this.commentsOpen, label: `${this.commentsOpen ? "Hide" : "Show"} ${issue.commentsDeferred ? "issue" : count} comments`,
        help: `${this.commentsOpen ? "Hide" : "Show"} comments (C)`,
      }))
      .when(this.commentsOpen, el => el.child(v_flex().gap(8)
        .when(issue.commentsDeferred && !issue.commentsError, section => section.child(div().text_color(t.muted).child("Loading comments…")))
        .when(!!issue.commentsError, section => section.child(h_flex().gap(8).items_center()
          .child(this.button("comments-retry", "Retry", cx => {
            this.loadComments(cx, true); this.actionFocus["comments-toggle"].focus(); cx.notify();
          }, t, { label: "Retry loading comments", help: "Retry loading comments" }))
          .child(div().flex_1().min_w(0).text_color(t.muted)
            .child(issue.commentsError === "permission_denied" ? "Jira denied access to comments." : "Could not load comments."))))
        .when(!issue.commentsDeferred && !count, section => section.child(div().text_color(t.muted).child("No comments.")))
        .when(issue.commentsTotal > (issue.comments?.length || 0), section => section.child(div().text_color(t.muted)
          .child(issue.comments?.length ? `Showing ${issue.comments.length} of ${issue.commentsTotal} comments. Open in Jira for the rest.`
            : `No comments loaded. Open in Jira to view ${issue.commentsTotal} comments.`)))
        .children((issue.comments || []).map((comment, i) => v_flex().id(`comment-${i}`).min_w(0).gap(8).pb(8)
          .child(h_flex().min_w(0).gap(8).items_center()
            .child(div().flex_1().min_w(0).font_semibold().child(comment.author))
            .child(div().flex_none().text_size(this.secondaryTextSize).text_color(t.muted).child(displayDate(comment.created))))
          .child(this.text(comment.body, t).line_height(1.55))))));
  }

  issueKeyWidth(key) {
    const length = this.issuesExpanded ? Math.max(key.length, ...this.model.rows().map(value => value.length)) : key.length;
    return Math.min(Math.ceil(length * this.secondaryTextSize * 0.63) + 8,
      Math.max(64, this.width - this.contentInset * 2 - (this.model.source === "manual" ? 64 : 96) - 6 - 36));
  }

  performResultAction(key, action, context, cx) {
    if (key === context.key || !this.issueContextCurrent(context) ||
        !this.issuesExpanded || context.surface || !this.model.rows().includes(key)) return;
    this.interact();
    if (action === "pin") this.model.toggleIssuePin(key);
    else {
      const value = action === "copy-link" ? issueLink(this.model.config.base, key, this.model.config.projects) : key;
      if (!value) return;
      this.model.browse(); this.copy(value, cx, action === "copy-link" ? "Issue link copied" : "Issue key copied");
    }
    this.updateSelectedRows(cx); this.handle.focus(); cx.notify();
  }

  renderRowHoverActions(key, t, canPin, context) {
    const pinned = this.model.current?.pinnedIssueKey === key;
    const link = issueLink(this.model.config.base, key, this.model.config.projects);
    const glyph = (name, icon, label, copied = false) => Button.new(`row-${name}-${key}`)
      .size(32).min_w(32).min_h(32).p(0).flex_none().justify_center().items_center().rounded(6).tab_stop(false)
      .accessibility_label(label).tooltip(label).cursor_pointer().text_color(copied ? t.accent : t.muted)
      .on_mouse_down("left", (_event, cx) => {
        this.pointerRowAction = true; this.rowPress = key; cx.stop_propagation();
      })
      .on_click((_event, cx) => {
        cx.stop_propagation();
        this.rowActions.push({ action: name, context, rowKey: key }); this.rowWake?.();
      })
      .when(!!icon, el => el.hover(item => item.bg(t.hover).text_color(t.foreground))
        .child(svg(`${ROOT}/icons/${copied ? "check" : icon}.svg`).size(16).flex_none()));
    return h_flex().id(`row-hover-${key}`).absolute().inset_0().px(this.contentInset - 1)
      .pt(4 + (this.resultHeaderHeight - 32) / 2)
      .justify_end().items_start().opacity(0).hover(el => el.opacity(1))
      .child(glyph("copy-key", "copy", `Copy issue key ${key}`, this.copyNote === "Issue key copied" && this.copyValue === key))
      .child(glyph("copy-link", "link", `Copy link to ${key}`, this.copyNote === "Issue link copied" && this.copyValue === link))
      .when(canPin, el => el.child(glyph("pin", pinned ? "" : "pin", `${pinned ? "Unpin" : "Pin"} issue ${key}`)));
  }

  renderIssueActions(t, queued = false, context = this.issueContext(), hovered = false) {
    const s = this.model.current, selected = s?.selected, issue = this.model.details.get(selected), config = this.model.config;
    const link = config && selected && issueLink(config.base, selected, config.projects);
    const selectionExcluded = !this.issueActionKey();
    const keyCopied = this.copyNote === "Issue key copied" && this.copyValue === selected;
    const linkCopied = this.copyNote === "Issue link copied" && this.copyValue === link;
    const fieldLayout = this.currentFieldLayout(), regions = placedFields(issue || this.model.metadata.get(selected), fieldLayout);
    const inlineStatus = regions.header.find(field => field.id === "status" && field.label === "Status");
    const inlineStatusConfigured = fieldLayout.fields.some(field => field.id === "status" && field.label === "Status" && field.section === "header");
    const keyWidth = this.issueKeyWidth(selected);
    const act = (action, cx) => queued ? this.queueRowAction(action, context) : this.performIssueAction(action, cx);
    const show = !queued || hovered || (this.rowActionOwnsFocus() && !this.pointerRowAction);
    const actions = h_flex().id("jira-issue-action-buttons").flex_none().h(32).items_center()
      .child(this.button("quick-copy-key", "Copy key", cx => act("copy-key", cx), t, {
        icon: keyCopied ? "check" : "copy", iconOnly: true, focusLabel: "Copy key · Y",
        disabled: selectionExcluded, active: keyCopied,
        label: keyCopied ? `${selected} copied` : `Copy issue key ${selected}`,
        help: keyCopied ? "Key copied" : `Copy ${selected} (Y)`,
      }).when(!show, el => el.invisible()))
      .child(this.button("quick-copy-link", "Copy link", cx => act("copy-link", cx), t, {
        icon: linkCopied ? "check" : "link", iconOnly: true, focusLabel: "Copy link · Shift+Y",
        active: linkCopied, disabled: selectionExcluded || !link, label: linkCopied ? `Link to ${selected} copied` : `Copy link to ${selected}`,
        help: linkCopied ? "Link copied" : "Copy link (Shift+Y)",
      }).when(!show, el => el.invisible()))
      .when(this.model.source !== "manual", el => el.child(this.toggle("quick-pin", "", s?.pinnedIssueKey === selected,
        (_value, cx) => act("pin", cx), t, `${s?.pinnedIssueKey === selected ? "Unpin" : "Pin"} issue ${selected}`,
        s?.pinnedIssueKey === selected ? "Unpin issue (P)" : `Pin issue (P)${s?.pinnedIssueKey ? ` · replaces ${s.pinnedIssueKey}` : ""}`,
        selectionExcluded || !this.model.source, { icon: "pin", iconOnly: true, focusLabel: `${s?.pinnedIssueKey === selected ? "Unpin" : "Pin issue"} · P` })
        .when(!show && s?.pinnedIssueKey !== selected, item => item.invisible())));
    return h_flex().id("jira-issue-actions").w_full().min_w(0).h(this.resultHeaderHeight).items_center().line_height(1.4)
      .child(h_flex().id("jira-issue-identity").flex_1().min_w(0).items_center()
        .child(this.button("open", div().w_full().min_w(0).truncate().child(selected), cx => act("open", cx), t, {
          quiet: true, disabled: selectionExcluded || !link || this.demo, label: `Open ${selected} in Jira`,
          help: "Open in Jira (⌘/Ctrl+Enter)",
        }).flex_1().min_w(0).when(inlineStatusConfigured, el => el.flex_none().w(keyWidth + 5))
          .min_h(this.resultHeaderHeight).h(this.resultHeaderHeight).ml(-5).px(4).py(3).text_size(this.secondaryTextSize).font_family(this.monoFont).text_color(t.accent))
        .when(inlineStatusConfigured, el => el.child(inlineStatus
          ? this.renderHeaderField(inlineStatus, t).flex_1().ml(6)
          : div().flex_1().min_w(0))))
      .child(actions);
  }

  rowActionOwnsFocus() {
    return ["open", "quick-copy-key", "quick-copy-link", "quick-pin"]
      .some(id => this.actionFocus[id].is_focused());
  }

  renderSelectedIssueRow(context, hovered = false) {
    const key = context.key, row = this.model.metadata.get(key), t = theme();
    if (!this.issueContextCurrent(context) || !this.issuesExpanded || !this.issueActionKey()) return div().h(this.issueRowHeight);
    return this.resultRow(v_flex().id("jira-selected-result"), t).bg(t.selected)
      .on_mouse_down("left", () => { this.pointerRowAction = true; })
      .child(h_flex().id(`issue-title-${key}`).w_full().h(this.resultHeaderHeight).min_w(0).items_center()
        .child(this.renderIssueActions(t, true, context, hovered)))
      .child(this.resultSummary(key, row, true, t));
  }

  renderSearch(t) {
    return h_flex().id("search").w_full().min_w(0).h(this.filterHeight).min_h(this.filterHeight).pl(11).gap(4).items_center().bg(t.surface).rounded(6).border_1().overflow_hidden()
      .border_color(this.typing ? t.accent : t.border).cursor_text()
      .tooltip("Filter loaded issues; Enter looks up a Jira key/URL")
      .child(Input.new(this.input).accessibility_label("Filter detected or loaded Jira issues, or look up a Jira key or URL directly").flex_1().min_w(0).h(this.filterHeight - 2).text_color(t.foreground))
      .when(!!this.input.value(), el => el.child(this.button("clear-filter", "×", cx => this.clearFilter(cx),
        t, { icon: "close", iconOnly: true, label: "Clear issue filter", focusLabel: "Clear filter", help: "Clear filter" })));
  }

  readerHeaderFields(fields) {
    // The default status belongs beside the key. Custom labels and placement
    // keep their configured header/body/details behavior.
    return fields.filter(field => !(field.id === "status" && field.label === "Status"));
  }

  headerFieldHeight() {
    const count = this.model.config ? this.readerHeaderFields(this.currentFieldLayout().fields.filter(field => field.section === "header")).length : 0;
    return count ? Math.min(140, count * (Math.ceil(this.secondaryTextSize * 1.5) + 5)) : 0;
  }

  freshnessHeight() {
    const lines = this.width - this.contentInset * 2 - 28 < this.secondaryTextSize * 21.5 ? 2 : 1;
    return Math.max(24, Math.ceil(this.secondaryTextSize * 1.5) * lines);
  }

  peekFixedHeight() {
    const listVisible = this.issuesExpanded || !this.model.current?.selected;
    return this.chromeHeight * 2 + this.controlRowHeight + 16
      + (listVisible ? this.filterHeight + 16 : 0)
      + (this.model.pinned ? Math.ceil(settings().ui_font_size * 1.5) : 0)
      + (this.model.current?.selected ? (listVisible && this.model.rows().includes(this.model.current.selected) ? 16 : this.resultHeaderHeight + 16)
        + this.freshnessHeight() + this.headerFieldHeight() : 0);
  }

  issueListHeight(count) {
    if (!count) return 0;
    const rowHeight = this.issueRowHeight;
    const visibleCount = count ? this.model.current?.presentation?.viewportCount || count : 0;
    const minimum = count > 1 && this.model.rows().includes(this.model.current?.pinnedIssueKey) ? 2 : 1;
    const available = this.height - this.peekFixedHeight() - Math.max(96, Math.ceil(settings().ui_font_size * 4.65)) - 2;
    const page = Math.max(minimum, Math.min(visibleCount, this.height < 500 ? 2 : 4, Math.floor(available / rowHeight)));
    return page * rowHeight + 2;
  }

  issuePageSize(count) { return Math.max(1, Math.floor(this.issueListHeight(count) / this.issueRowHeight)); }

  renderPeek(root, t, sourceLabel) {
    const s = this.model.current, config = this.model.config;
    const rows = this.model.rows(), selected = s?.selected, issue = this.model.details.get(selected);
    const compact = this.model.compactSlots(), context = this.issueContext();
    const link = config && selected && issueLink(config.base, selected, config.projects);
    const issueBusy = this.request?.phase === "issue" && this.request.key === selected;
    const issueDebounced = !!this.previewWait && this.previewWait.state === s && this.previewWait.key === selected;
    const issueQueued = !!selected && !issue && !this.model.failures.has(selected) && !!this.request && !issueBusy;
    const refreshQueued = !!selected && !!issue && this.forceKey === selected && !issueBusy;
    const issueFailed = !!selected && this.model.failures.has(selected);
    const issueWaiting = !!selected && !issue && !issueFailed && !issueBusy && !issueQueued && this.now() < this.model.retryAfter;
    const countDescription = `${rows.length} issues shown of ${s?.keys.length || 0} discovered; search checks keys and fields loaded so far.`;
    const visibleNote = issueFailed && this.note === "Could not load Jira data. Refresh to retry." ? "" : this.note;
    const keyCopied = this.copyNote === "Issue key copied" && this.copyValue === selected;
    const linkCopied = this.copyNote === "Issue link copied" && this.copyValue === link;
    const copyMessage = keyCopied || linkCopied ? "" : this.copyNote;
    const listVisible = this.issuesExpanded || !selected;
    const minimumListRows = compact.length > 1 && compact[0]?.key === s?.pinnedIssueKey ? 2 : 1;
    const singleScroll = this.height < 380 || (!!selected && this.height < this.peekFixedHeight()
      + Math.max(96, Math.ceil(settings().ui_font_size * 4.65)) + (compact.length && listVisible ? this.issueRowHeight * minimumListRows + 2 : 0));
    if (singleScroll) root.overflow_y_scrollbar();
    const selectionExcluded = !!selected && !this.issueActionKey();
    const listHeight = this.issueListHeight(compact.length);
    const rowOwnsActions = listVisible && rows.includes(selected);
    this.refreshSelectedRow();
    if (rowOwnsActions) {
      for (const [id, label] of [["quick-copy-key", "Copy key · Y"], ["quick-copy-link", "Copy link · Shift+Y"],
        ["quick-pin", s?.pinnedIssueKey === selected ? "Unpin · P" : "Pin issue · P"], ["quick-refresh", "Refresh · R"]])
        if (this.actionFocus[id].is_focused()) this.focusCaption = label;
    }
    if (!config) {
      const missing = this.error === "configuration_missing";
      return root
        .when(this.issuesExpanded, el => el.child(div().px(10).py(5).child(this.renderSearch(t))))
        .child(v_flex().flex_1().min_h(0).p(16).gap(12)
        .child(div().font_semibold().child(this.loading ? (this.clearing ? "Clearing cache…" : "Connecting to Jira…") : (this.error && !missing ? "Connection needs attention" : "Connect Jira")))
        .when(!this.loading, el => el.child(div().text_color(t.muted).child(MESSAGES[this.error] || MESSAGES.configuration_missing)))
        .when(!this.loading, el => el.child(this.button("setup-open", "Set up Jira", cx => this.openSetup(cx), t, { active: true })))
        .when(!this.loading, el => el.child(this.button("choose-config", "Choose configuration folder…", cx => this.chooseConfig(cx), t, {
          label: "Choose Jira Peek configuration folder", help: "Choose configuration folder",
        })))
        .when(!this.loading && !!this.error && !missing, el => el.child(this.button("reconnect", "Reconnect", cx => this.connect(cx), t, {
          label: "Reconnect to Jira", help: "Reconnect to Jira",
        })))
        .when(!this.loading && !!this.note, el => el.child(h_flex().gap(8).items_start()
          .child(this.button("dismiss-note", "Dismiss", cx => { this.note = ""; cx.notify(); }, t, {
            label: "Dismiss connection status", help: "Dismiss message",
          }))
          .child(div().flex_1().min_w(0).text_color(t.blocked).child(this.note)))));
    }

    root.child(v_flex().w_full().min_w(0).flex_none().px(this.contentInset).py(8).gap(8)
      .child(h_flex().id("jira-navigation").w_full().min_w(0).gap(8).items_center()
        .child(this.toggle("reader-focus", h_flex().gap(6).items_center()
          .child(svg(`${ROOT}/icons/${listVisible ? "chevron-down" : "chevron-right"}.svg`).size(16).flex_none())
          .child(div().font_semibold().child("Issues"))
          .child(div().text_size(this.secondaryTextSize).text_color(t.muted).child(String(s?.keys.length || 0))), listVisible,
          (_value, cx) => this.toggleIssues(cx), t,
          `Issues (${s?.keys.length || 0}), ${listVisible ? "expanded. Collapse issue list" : "collapsed. Expand issue list"}`,
          null, !selected && !rows.length, { quiet: true }).ml(-5))
        .when(!!s?.unseen.size, el => el.child(this.button("unseen", `+${s.unseen.size} new`, cx => this.readNew(cx), t, {
          quiet: true, label: `Read next new issue; ${s.unseen.size} unread`, help: "Read next unread issue (N)",
        })))
        .child(div().flex_1().min_w(0))
        .child(this.button("follow", "", cx => this.follow(cx), t, {
          icon: s?.follow ? "pause" : "play", iconOnly: true,
          label: s?.follow ? "Pause following new issue keys" : "Resume following new issue keys",
          focusLabel: `${s?.follow ? "Pause following" : "Resume following"} · F`,
          help: this.demo ? "Unavailable in demo" : this.model.source === "manual" ? "Follow unavailable in manual lookup"
            : !s ? "Select a terminal to follow"
            : s.follow ? "Pause following (F)"
              : "Resume following (F) · clears filter",
          disabled: !s || this.demo || this.model.source === "manual",
        })))
      .when(this.model.pinned && !!this.model.source && this.model.source !== "manual", el => el.child(div().id("jira-pinned-source").flex_none().text_color(t.muted)
        .tooltip(`Source: ${sourceLabel}`).child("Keeping this terminal")))
      .when(listVisible, el => el.child(h_flex().id("jira-filter-bar").w_full().min_w(0).h(this.filterHeight).items_center()
        .child(this.renderSearch(t).flex_1())))
      .when(listVisible && !!this.lookupError, el => el.child(h_flex().gap(6).items_start()
        .child(this.button("dismiss-lookup", "Dismiss", cx => { this.lookupError = ""; cx.notify(); }, t, {
          label: "Dismiss issue lookup error", help: "Dismiss error",
        }))
        .child(div().flex_1().min_w(0).text_color(t.blocked).child(this.lookupError)))));

    const results = v_flex().id("issue-list").relative().flex_1().min_h(0).min_w(0)
      .when(singleScroll, el => el.flex_none().h_auto())
      .role("group").accessibility_label(`Filtered issues; ${rows.length} matching results`)
      .track_focus(this.handle).tab_index(0).tab_stop(listVisible)
      .on_scroll_wheel((_e, cx) => {
        this.rowPress = null;
        const following = this.model.current?.follow;
        this.interact(); this.model.browse();
        const actionFocused = this.rowActionOwnsFocus();
        if (actionFocused) this.handle.focus();
        if (following || actionFocused) cx.notify();
      })
      .on_key_down((e, cx) => {
        if (!this.handle.is_focused() || this.hasKeyModifiers(e)) return;
        const key = String(e.key || "").toLowerCase();
        if (key === "enter") {
          const target = this.issueActionKey() || this.model.rows()[0];
          if (target) this.select(target, cx);
        } else if (["up", "arrowup", "down", "arrowdown", "pageup", "pagedown", "home", "end"].includes(key)) this.navigateResults(key, cx);
        else return;
        cx.stop_propagation();
      });
    if (!compact.length && !selected) {
      const emptyTitle = s?.baselinePending ? "Clearing list…" : s?.cleared ? "List cleared · waiting for new issues" : s?.error ? "Terminal unavailable" : s?.query ? "No matches" : this.model.source ? "No Jira issues detected" : "No terminal selected";
      const emptyDetail = s?.screenLimited ? "Too much screen context to establish a complete baseline. Use Read history or enter a key."
        : s?.baselinePending ? s.error || "Establishing a fresh screen baseline…"
        : s?.cleared ? "Newly observed keys will appear here. Scan screen or Read history can restore earlier issues."
        : s?.error
        ? `${s.error} Enter a key to look it up.`
        : s?.query
          ? "Try another filter, or enter a Jira key or URL for a direct lookup."
          : this.model.source
            ? config.interval > 0 ? "Jira keys in this terminal appear here automatically." : "Enter a Jira key, or use Options → Scan screen."
            : "Focus a terminal with Jira activity, or enter a Jira key.";
      results.child(this.message(emptyTitle, emptyDetail, t).flex_1().min_h(0));
    } else if (compact.length && listVisible) {
      const activeKeys = new Set(rows), compactActive = compact.filter(slot => activeKeys.has(slot.key));
      const sticky = compact[0]?.key === s?.pinnedIssueKey ? compact[0] : null;
      const scrollable = sticky ? compact.slice(1) : compact;
      this.fixedActionKey = sticky?.key;
      this.resultActionKeys = scrollable.map(slot => slot.key);
      this.resultActionContext = context;
      const actionIndex = new Map(scrollable.map((slot, index) => [slot, index]));
      const itemKeys = scrollable.map(slot => `${context.projection ?? "following"}/${slot.id}`);
      const slotById = new Map(scrollable.map((slot, index) => [itemKeys[index], slot]));
      const viewport = { state: s, projection: context.projection, range: { start: 0, end: 0 } };
      this.resultsViewport = viewport;
      const renderRow = (slot, fixed = false) => {
        const key = slot.key, available = !!key && activeKeys.has(key);
        const row = this.model.metadata.get(key);
        if (available && key === selected) return div().id(`issue-${key}`).w_full().h(this.issueRowHeight).min_w(0)
          .role("list_box_option").accessibility_label(`${key}${row?.summary ? `, ${row.summary}` : ""}`)
          .set_position(compactActive.indexOf(slot) + 1, compactActive.length).selected(true).aria_selected(true).aria_active_descendant()
          .child(fixed ? this.pinnedSelectedRow : this.selectedRow);
        const canPin = !!this.model.source && this.model.source !== "manual";
        const pinned = key === s?.pinnedIssueKey;
        return this.resultRow(Button.new(`issue-${key || slot.id}`), t).rounded(0).tab_stop(false)
          .role("list_box_option").accessibility_label(key ? `${key}${row?.summary ? `, ${row.summary}` : ""}${available ? "" : ", no longer matches"}` : "Result expired; update results")
          .when(available, el => el.set_position(compactActive.indexOf(slot) + 1, compactActive.length))
          .disabled(!available).selected(available && key === selected)
          .when(available && key === selected, el => el.bg(t.selected).aria_active_descendant())
          .hover(el => el.when(available, item => item.bg(t.hover))).active(el => el.when(available, item => item.bg(t.selected)))
          .when(fixed, el => el.on_click((_event, cx) => {
            if (!this.issueContextCurrent(context) || !this.model.rows().includes(key)) return;
            if (this.rowPress === key) { this.rowPress = null; return; }
            this.handle.focus(); this.select(key, cx, false, false); this.updateSelectedRows(cx);
          }).on_mouse_down("left", () => { this.pointerRowAction = true; this.rowPress = null; }))
          .child(h_flex().id(`issue-title-${key || slot.id}`).w_full().h(this.resultHeaderHeight).min_w(0).items_center().line_height(1.4)
            .child(h_flex().id(`issue-identity-${key || slot.id}`).flex_1().min_w(0).gap(6).items_center()
              .child(div().id(`issue-key-${key || slot.id}`).flex_none().min_w(0).w(this.issueKeyWidth(key || "Result expired")).truncate().text_size(this.secondaryTextSize).font_family(this.monoFont).text_color(key === selected ? t.accent : t.muted).child(key || "Result expired"))
              .child(div().flex_1().min_w(0).truncate().text_size(this.secondaryTextSize).text_color(statusColor(row?.status || "", t))
                .when(!!row?.status, el => el.tooltip(`Status: ${row.status}`)).child(row?.status || "")))
            .child(div().w(canPin ? 96 : 64).flex_none()))
          .child(this.resultSummary(key, row, available, t))
          .when(available && pinned, el => el.child(h_flex().id(`row-pin-indicator-${key}`).absolute().right(this.contentInset - 1)
            .top(4 + (this.resultHeaderHeight - 32) / 2).size(32)
            .items_center().justify_center().text_color(t.accent).child(svg(`${ROOT}/icons/pin.svg`).size(16))))
          .when(available, el => el.child(fixed ? this.pinnedResultActions : this.resultActionRows[actionIndex.get(slot)]));
      };
      // Only the non-pinned rows are virtualized. The fixed row is the same
      // result, not a second copy, and owns actions only when selected.
      const list = v_virtual_list("jira-issue-options", scrollable.length, this.issueRowHeight, index => itemKeys[index], range => {
        const page = Math.max(1, this.issuePageSize(compact.length) - (sticky ? 1 : 0));
        viewport.range = { start: range.start, end: Math.min(range.end, range.start + page) };
        return scrollable.slice(range.start, range.end).map(slot => renderRow(slot));
      }).size_full().min_w(0)
        .track_scroll(this.listScroll)
        .on_item_click((id, cx) => {
          const key = slotById.get(id)?.key;
          if (!this.issueContextCurrent(context) || !this.model.rows().includes(key)) return;
          if (this.rowPress === key) { this.rowPress = null; return; }
          // The native list also reports clicks on controls inside the selected
          // row. Reselecting that row rebuilds it before its action completes.
          if (key === this.model.current?.selected) return;
          this.handle.focus(); this.select(key, cx, false, false); this.updateSelectedRows(cx);
        });
      results.child(v_flex().id("jira-compact-results").relative().w_full().min_w(0).flex_none().h(listHeight).min_h(0)
        .border_1().border_color(this.handle.is_focused() ? t.accent : t.border)
        .role("list_box").accessibility_label("Matching issues")
        .when(!!sticky, el => el.child(renderRow(sticky, true)))
        .child(v_flex().id("jira-issue-scroll-viewport").relative().w_full().flex_1().min_h(0)
        .on_mouse_down("left", (e, cx) => {
          this.pointerRowAction = true; this.rowPress = null;
          if (e.bounds && e.position.x >= e.bounds.x + e.bounds.width - 10 && this.rowActionOwnsFocus()) {
            this.handle.focus(); cx.notify();
          }
        })
          .child(list)
          .child(Scrollbar.vertical("jira-issue-options").absolute().inset_0())));

    }

    let issueStatus = null;
    if (selected && (issueFailed || refreshQueued || (issueBusy && issue))) {
      const statusText = issueFailed
        ? (this.model.denied.has(selected) ? MESSAGES.permission_denied : issue ? "Refresh failed. Showing the last loaded issue." : "Issue unavailable. Check the key and access.")
        : refreshQueued ? "Refresh queued until the current Jira request finishes."
          : "Refreshing this issue…";
      issueStatus = h_flex().id("jira-issue-status").flex_none().px(12).py(5).gap(8).items_start()
        .when(issueFailed, el => el.child(this.button("retry-refresh", "Retry", cx => this.refresh(cx), t, {
          label: `Retry loading ${selected}`, help: "Retry loading issue",
        })))
        .child(div().flex_1().min_w(0).text_color(issueFailed ? t.blocked : t.muted).child(statusText));
    }

    if (selected) {
      // Keep the old reader mounted to preserve its place, but remove it from
      // painting and focus traversal when the filter excludes its selection.
      const preview = v_flex().id("jira-issue-preview").size_full().min_w(0).min_h(0)
        .when(singleScroll, el => el.h_auto())
        .when(selectionExcluded, el => el.invisible());
      // Keep the displayed issue identifiable while its description is scrolled
      // or search results are filtered without changing the selected preview.
      const fieldLayout = this.currentFieldLayout();
      const knownIssue = issue || this.model.metadata.get(selected);
      const regions = placedFields(knownIssue, fieldLayout);
      // Only promote the default first body field. Explicit placement, labels,
      // hidden fields and reordered layouts keep their configured meaning.
      const firstBody = fieldLayout.fields.find(field => field.section === "body");
      const title = firstBody?.id === "summary" && firstBody.label === "Summary"
        ? regions.body.find(field => field.id === "summary") : null;
      const headerFields = this.readerHeaderFields(regions.header);
      const bodyFields = regions.body.filter(field => field !== title);
      // The complete default title always scrolls. It cannot consume the
      // fixed action area or disappear behind a truncated result summary.
      const summaryTitle = title ? v_flex().id("jira-issue-summary").min_w(0).flex_none().pt(4).pb(8)
        .font_semibold().text_size(settings().ui_font_size + 3).line_height(1.3)
        .child(div().min_w(0).child(title.value)) : null;
      const freshness = h_flex().id("jira-freshness-row").w_full().min_w(0).h(this.freshnessHeight()).flex_none().gap(4).items_center().text_size(this.secondaryTextSize)
        .child(div().id("jira-freshness").min_w(0).line_height(1.5).text_size(this.secondaryTextSize).text_color(t.muted)
          .accessibility_label(this.freshnessLabel(issue)).tooltip(this.freshnessLabel(issue))
          .child(issue ? this.freshnessLabel(issue) : ""))
        .child(this.button("quick-refresh", "Refresh", cx => this.refresh(cx), t, {
          icon: "refresh", iconOnly: true, iconButtonSize: 24, iconSize: 13, focusLabel: "Refresh · R",
          disabled: selectionExcluded || this.demo || issueBusy || refreshQueued, label: `Refresh ${selected}`,
          help: "Refresh issue (R)",
        }));
      const headerCount = this.readerHeaderFields(fieldLayout.fields.filter(field => field.section === "header")).length;
      preview.child(v_flex().id("jira-reader-title").w_full().min_w(0).flex_none().px(this.contentInset).pt(4).pb(4)
        .role("group").accessibility_label(`Selected issue ${selected}${listVisible && rows.includes(selected) ? `, ${rows.indexOf(selected) + 1} of ${rows.length} matching results` : ""}`)
        .border_b(1).border_color(this.readerHandle.is_focused() ? "#00000000" : t.border)
        .when(!rowOwnsActions, el => el.child(this.renderIssueActions(t)))
        .child(freshness)
        .when(headerCount > 0, el => el.child(v_flex().id("jira-header-fields").h(this.headerFieldHeight()).min_h(this.headerFieldHeight()).overflow_y_scrollbar().gap(5)
          .children(headerFields.map(field => this.renderHeaderField(field, t, true))))));
      if (issueStatus) preview.child(issueStatus);
      const reader = v_flex().id(`reader-${this.epoch}-${this.model.source}-${selected}`).flex_1().min_h(0)
        .when(!singleScroll, el => el.overflow_y_scrollbar())
        .when(singleScroll, el => el.flex_none().min_h(120))
        .px(this.contentInset - 1).py(16).gap(16)
        .role("pane").accessibility_label(`Issue reader for ${selected}`)
        .track_focus(this.readerHandle).tab_index(0)
        .border_1().border_color(this.readerHandle.is_focused() ? t.accent : "#00000000")
        .on_click((_e, cx) => { this.interact(); this.model.browse(); this.readerHandle.focus(); cx.notify(); })
        .on_key_down((e, cx) => {
          const key = String(e.key || "").toLowerCase(), chord = String(e.keystroke || "").toLowerCase();
          if ((!this.hasKeyModifiers(e) && ["pageup", "pagedown", "home", "end", "space", " "].includes(key)) || chord === "shift-space") {
            this.interact(); this.model.browse(); cx.notify();
          }
          // The native scroll container handles the movement after this callback.
        })
        // Native focus can leave without a Peek action; invalidate its cached hint.
        .on_mouse_down_out((_e, cx) => cx.notify())
        .on_scroll_wheel((_e, cx) => { this.interact(); if (s.follow) { this.model.browse(); cx.notify(); } });
      if (summaryTitle) reader.child(summaryTitle);
      if (issue) {
        if (issue.unsupportedContent) reader.child(div().text_color(t.muted).child("Some content is unsupported here. Open in Jira for the full issue."));
        else if (issue.truncated) reader.child(div().text_color(t.muted).child("Some issue content is shortened."));
        reader.children(bodyFields.map((field, index) => this.renderField(field, issue, t,
          !!title && index === 0 && field.id === "description" && field.label === "Description")));
        reader.child(v_flex().id("jira-reader-details").min_w(0).gap(8).pt(8).border_t(1).border_color(t.border)
          .child(this.button("details-toggle", "Details", cx => this.toggleDetails(cx), t,
        { row: true, trailing: "D", icon: this.detailsOpen ? "chevron-down" : "chevron-right",
          active: this.detailsOpen, label: `${this.detailsOpen ? "Hide" : "Show"} issue details`, help: `${this.detailsOpen ? "Hide" : "Show"} details (D)` }))
          .when(this.detailsOpen, el => el.child(v_flex().id("jira-details-fields").gap(10)
            .child(div().text_color(t.muted).child(this.freshnessLabel(issue)))
            .children(regions.details.map(field => this.renderField(field, issue, t))))));
      } else if (!issueFailed) {
        reader.children(bodyFields.filter(field => field.id === "summary").map(field => this.renderField(field, null, t)));
        reader.child(this.message(issueWaiting ? "Waiting to retry…" : issueDebounced ? "Loading issue…" : issueQueued ? "Waiting for an earlier request…" : issueBusy ? "Loading issue…" : "Issue details unavailable", "", t));
      }
      preview.child(reader);
      results.child(v_flex().relative().flex_1().min_h(0).min_w(0)
        .when(singleScroll, el => el.flex_none().h_auto()).child(preview)
        .when(selectionExcluded, el => el.child(v_flex().id("jira-select-result").absolute().inset_0().bg(t.background).px(this.contentInset).py(16).gap(8)
          .child(div().font_semibold().child(rows.length ? "Select a result to read or copy" : "No matches"))
          .child(div().text_color(t.muted).child("This issue is outside the current filter. Select a matching result or clear the filter."))
          .child(this.button("results-clear-filter", "Clear filter", cx => {
            if (this.issueContextCurrent(context)) this.clearFilter(cx);
          }, t, { label: "Clear filter", help: "Show all loaded issues" })))));
    } else if (rows.length) results.child(this.message("Choose an issue to preview", "New issues stay unread while Paused.", t).flex_1());
    else results.child(div().flex_1());
    root.child(results);
    if (s?.error && (rows.length || selected)) root.child(div().flex_none().px(12).py(5).text_color(t.blocked).child(s.error));
    if (this.fieldFileError || this.preferenceError) root.child(div().flex_none().px(10).py(5).text_color(t.blocked).child(this.fieldFileError || this.preferenceError));
    if (visibleNote || copyMessage) root.child(h_flex().flex_none().px(10).py(5).gap(8).items_start().bg(t.chrome)
      .when(!!visibleNote, el => el.child(this.button("dismiss-note", "Dismiss", cx => { this.note = ""; cx.notify(); }, t, {
        label: "Dismiss operation status", help: "Dismiss message",
      })))
      .when(!!copyMessage && !visibleNote, el => el.child(this.button("dismiss-note", "Dismiss", cx => {
        this.copyNoteRevision++; this.copyNoteTimer?.cancel(); this.copyNote = ""; cx.notify();
      }, t, { label: "Dismiss clipboard confirmation", help: "Dismiss confirmation" })))
      .child(v_flex().flex_1().min_w(0).gap(3)
        .when(!!visibleNote, el => el.child(div().text_color(t.muted).child(visibleNote)))
        .when(!!copyMessage, el => el.child(div().text_color(t.accent).child(copyMessage)))));
    return root;
  }
}
