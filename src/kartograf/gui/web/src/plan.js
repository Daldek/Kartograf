// The plan of the request (ADR-063 decision 9, plan D2): the detached plan the server checks
// (`POST <group>/<verb>?check=true`, `kartograf-plan/1`) shown before anything is generated.
// Its notices stand above a table of its files: the unit, the file, its size where the plan
// knows it, the source with its provider, the licence and the state, with the reason a file
// has no address of its own (`fetch_reason`). A plan that is not `ok`, or that holds a source
// whose files need a key (`auth` other than `none`), is marked incomplete and says why. The
// map draws the footprints of its units (sheets.js) and the sources' lines stand in the
// kit's <nogat-sources> strip. A row and a footprint select each other.

import { lang, t } from "./i18n.js";
import { extentOf, localOutline, pooled, ringFeature, sheetOutline } from "./sheets.js";

/** The tracks whose units are sheets or tiles: their footprints are the sheets' outlines. */
const SHEET_TRACKS = new Set(["pl_sheet", "laz_tile", "cz_sheet", "cz_laz", "cz_orto"]);
/** The tracks of a cutout: its footprint is the area of the request. */
const CUTOUT_TRACKS = new Set(["pl_cutout", "cz_cutout"]);
/** At most this many units are read with `sheet parse`, this many at a time. */
const PARSED_MAX = 100;
const PARSED_AT_ONCE = 4;
const SIZE_UNITS = ["B", "kB", "MB", "GB", "TB"];
const REASONS = {
  credentials: "reasonCredentials",
  built: "reasonBuilt",
  feed_not_cached: "reasonFeed",
};

function make(tag, className = null, text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null) node.textContent = text;
  return node;
}

/**
 * A size in bytes as a person reads it, in the page's language.
 *
 * @param {number|null|undefined} bytes the size
 * @returns {string} e.g. `12,3 MB`, `—` when unknown
 */
export function sizeText(bytes) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < SIZE_UNITS.length - 1) {
    value /= 1000;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  const number = new Intl.NumberFormat(lang(), { maximumFractionDigits: digits }).format(value);
  return `${number} ${SIZE_UNITS[unit]}`;
}

/**
 * A notice of the plan: its first line, the rest folded under it.
 *
 * @param {{level: string, message: string}} notice a notice of the plan
 * @returns {HTMLLIElement} the item
 */
function noticeItem(notice) {
  const item = make("li", notice.level === "info" ? null : notice.level);
  const [first, ...rest] = String(notice.message ?? "").split("\n");
  if (!rest.length) {
    item.textContent = first;
    return item;
  }
  const details = make("details");
  details.append(make("summary", null, first), rest.join("\n"));
  item.append(details);
  return item;
}

/** The time a plan was checked, in the page's language. */
function timeText(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso ?? "");
  return date.toLocaleString(lang(), { dateStyle: "medium", timeStyle: "short" });
}

/**
 * The state of a file: its badge and the reason under it.
 *
 * @param {object} item a position of the plan
 * @returns {{tone: string, text: string, reason: string|null}} the badge's tone and words
 */
function stateOf(item) {
  const reason = item.fetch_reason ? t(REASONS[item.fetch_reason] ?? "reasonFeed") : null;
  if (item.status === "check_failed") {
    return { tone: "bad", text: t("statusFailed"), reason: item.error ?? reason };
  }
  if (item.action === "conflict") {
    return { tone: "bad", text: t("statusConflict"), reason: item.error ?? item.reason };
  }
  if (item.action === "replace") return { tone: "warn", text: t("statusReplace"), reason };
  if (item.status === "current") return { tone: "ok", text: t("statusCurrent"), reason };
  const text = item.action === "write" ? t("statusWrite") : t("statusOther");
  return { tone: reason ? "warn" : "ok", text, reason };
}

/**
 * Why a plan is incomplete: positions that could not be checked, a source that needs a key,
 * a result that is not `ok`.
 *
 * @param {object} plan `kartograf-plan/1`
 * @param {string} status the `status` of the result
 * @returns {string[]} the reasons, none for a complete plan
 */
export function incompleteReasons(plan, status) {
  const reasons = [];
  const failed = (plan.items ?? []).filter((item) => item.status === "check_failed").length;
  if (failed) reasons.push(t("planFailedItems", { count: failed }));
  if ((plan.sources ?? []).some((source) => source.auth && source.auth !== "none")) {
    reasons.push(t("planCredentials"));
  }
  if ((plan.ok === false || status !== "ok") && !failed) reasons.push(t("planNotOk"));
  return reasons;
}

/**
 * The lines of the sources for the kit's strip: each source's `license.attribution` once,
 * declared for the strip with the words of its address linked to the licence's page.
 *
 * @param {object[]} sources the plan's `sources`
 * @returns {{attribution: string[], screenLines: object[]}} the lines and their declarations
 */
export function sourceLines(sources) {
  const attribution = [];
  const screenLines = [];
  for (const source of sources ?? []) {
    const text = source?.license?.attribution;
    if (typeof text !== "string" || !text || attribution.includes(text)) continue;
    attribution.push(text);
    let links = [];
    try {
      const host = new URL(source.license.url).host;
      if (host && text.includes(host)) links = [[host, source.license.url]];
    } catch {
      // A licence without an address: the line's own addresses are linked.
    }
    screenLines.push({ text, short: null, links });
  }
  return { attribution, screenLines };
}

/** The plan's section of the page: its notices, its table and the footprints on the map. */
export class PlanView {
  /**
   * @param {HTMLElement} root the section
   * @param {{view: import("./map.js").MapView, api: import("./api.js").Api, terms: string|null}}
   *   parts the map, the server and the address of the regulamin
   */
  constructor(root, { view, api, terms }) {
    this.root = root;
    this.view = view;
    this.api = api;
    this.shown = null;
    this.turn = 0;
    this.footprintCount = null;
    this.parts = {
      empty: root.querySelector("#plan-empty"),
      stale: root.querySelector("#plan-stale"),
      error: root.querySelector("#plan-error"),
      body: root.querySelector("#plan-body"),
      summary: root.querySelector("#plan-summary"),
      incomplete: root.querySelector("#plan-incomplete"),
      notices: root.querySelector("#plan-notices"),
      table: root.querySelector("#plan-table"),
      rows: root.querySelector("#plan-table tbody"),
      footprints: root.querySelector("#plan-footprints"),
      sources: root.querySelector("#plan-sources"),
    };
    if (terms) this.parts.sources.setAttribute("terms", terms);
    this.parts.rows.addEventListener("click", (event) => {
      const row = event.target.closest("tr[data-unit]");
      if (row && !event.target.closest("a")) this.choose(row.dataset.unit);
    });
    this.parts.rows.addEventListener("keydown", (event) => {
      const row = event.target.closest("tr[data-unit]");
      if (!row || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      this.choose(row.dataset.unit);
    });
    view.onClick("footprints", (unit) => this.choose(unit, { fit: false }));
  }

  /** No plan: the hint of how to get one. */
  reset() {
    this.turn += 1;
    this.shown = null;
    const { empty, stale, error, body } = this.parts;
    empty.hidden = false;
    stale.hidden = true;
    error.hidden = true;
    body.hidden = true;
    this.view.setFootprints([]);
  }

  /** @param {boolean} value whether the form has changed since the plan shown */
  stale(value) {
    this.parts.stale.hidden = !value || this.shown === null;
  }

  /**
   * A plan the server refused or could not make: its message and hint, the plan before gone.
   *
   * @param {import("./api.js").ApiError|Error} error the error
   */
  failed(error) {
    this.reset();
    const doc = error?.doc ?? {};
    const box = this.parts.error;
    box.replaceChildren(make("p", null, t("planFailed", { message: error.message })));
    if (typeof doc.hint === "string" && doc.hint) box.append(make("p", null, doc.hint));
    box.hidden = false;
    this.parts.empty.hidden = true;
  }

  /**
   * Show a checked plan and draw its footprints.
   *
   * @param {object} envelope the `kartograf-result/1` of the plan
   * @param {number[][]|null} area the outline of the request's area, for a cutout's footprint
   * @returns {Promise<void>} once the footprints are drawn
   */
  async show(envelope, area) {
    const turn = ++this.turn;
    this.shown = { envelope, area };
    this._draw();
    await this._footprints(turn);
  }

  /** Draw the plan shown again in the page's language. */
  relabel() {
    if (this.shown === null) return;
    this._draw();
    this._footprintNote();
  }

  _draw() {
    const { envelope } = this.shown;
    const plan = envelope.result;
    const items = plan.items ?? [];
    const { empty, stale, error, body, summary, incomplete, notices, rows, sources } = this.parts;
    empty.hidden = true;
    stale.hidden = true;
    error.hidden = true;
    body.hidden = false;
    const sizes = items
      .map((item) => item.fetch?.size_bytes)
      .filter((size) => typeof size === "number");
    const said = [t("planSummary", { count: items.length, checked: timeText(plan.checked_at) })];
    if (sizes.length) {
      const size = sizeText(sizes.reduce((sum, bytes) => sum + bytes, 0));
      said.push(t("planSize", { known: sizes.length, count: items.length, size }));
    }
    summary.textContent = said.join(" ");
    this.parts.table.classList.toggle("no-size", sizes.length === 0);
    const reasons = incompleteReasons(plan, envelope.status);
    incomplete.replaceChildren();
    if (reasons.length) {
      incomplete.append(make("strong", null, `${t("planIncomplete")}: `), reasons.join("; "));
    }
    incomplete.hidden = reasons.length === 0;
    notices.replaceChildren(...(plan.notices ?? []).map(noticeItem));
    notices.hidden = notices.children.length === 0;
    const bySource = new Map((plan.sources ?? []).map((source) => [source.key, source]));
    rows.replaceChildren(...items.map((item) => this._row(item, bySource.get(item.source))));
    const lines = sourceLines(plan.sources);
    sources.screenLines = lines.screenLines;
    sources.attribution = lines.attribution;
  }

  _row(item, source) {
    const row = make("tr");
    row.dataset.unit = item.unit;
    row.tabIndex = 0;
    const what = make("td", "what");
    what.append(make("span", "unit", item.unit), make("span", "file", item.name));
    const from = make("td", "source");
    const terms = source?.license;
    const named = make("span", "provider");
    if (source?.provider) named.append(source.provider);
    if (terms?.url) {
      const link = make("a", null, terms.id ?? terms.url);
      link.href = terms.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      named.append(source?.provider ? ", " : "", link);
    } else if (terms?.id) {
      named.append(source?.provider ? ", " : "", terms.id);
    }
    from.append(named);
    if (item.source) from.append(make("code", null, item.source));
    const state = stateOf(item);
    const status = make("td", "status");
    status.append(make("span", `badge ${state.tone}`, state.text));
    if (state.reason) status.append(make("span", "reason", state.reason));
    row.append(what, make("td", "size", sizeText(item.fetch?.size_bytes)), from, status);
    return row;
  }

  /** The footprints of the plan's units on the map, the view fitted to them and the area. */
  async _footprints(turn) {
    const { envelope, area } = this.shown;
    const items = envelope.result.items ?? [];
    const units = new Map();
    for (const item of items) {
      const known = units.get(item.unit);
      const failed = item.status === "check_failed";
      if (known) known.failed ||= failed;
      else units.set(item.unit, { unit: item.unit, track: item.track, failed, ring: null });
    }
    const asked = [];
    for (const unit of units.values()) {
      if (CUTOUT_TRACKS.has(unit.track)) unit.ring = area;
      else if (SHEET_TRACKS.has(unit.track)) {
        unit.ring = localOutline(unit.unit);
        if (!unit.ring && asked.length < PARSED_MAX) asked.push(unit);
      }
    }
    this.footprintCount = { shown: 0, total: units.size };
    this._footprintNote();
    this.view.setFootprints([]);
    await pooled(asked, PARSED_AT_ONCE, async (unit) => {
      if (turn !== this.turn) return;
      unit.ring = await sheetOutline(unit.unit, (code) => this.api.sheet(code));
    });
    if (turn !== this.turn) return;
    const drawn = [...units.values()].filter((unit) => unit.ring);
    this.view.setFootprints(
      drawn.map((unit) => ringFeature(unit.ring, { unit: unit.unit, failed: unit.failed })),
    );
    this.footprintCount = { shown: drawn.length, total: units.size };
    this._footprintNote();
    const extent = extentOf([...drawn.map((unit) => unit.ring), ...(area ? [area] : [])]);
    if (extent) this.view.fit(extent);
  }

  _footprintNote() {
    const count = this.footprintCount;
    const note = this.parts.footprints;
    if (!count) {
      note.textContent = "";
      return;
    }
    note.textContent = count.shown
      ? t("footprints", { shown: count.shown, total: count.total })
      : t("footprintsNone");
  }

  /**
   * Choose a unit: its rows marked and shown, its footprint marked (and the view on it).
   *
   * @param {string} unit the unit
   * @param {{fit?: boolean}} [how] whether the map moves to the footprint
   */
  choose(unit, { fit = true } = {}) {
    let first = null;
    for (const row of this.parts.rows.querySelectorAll("tr[data-unit]")) {
      const chosen = row.dataset.unit === unit;
      row.classList.toggle("selected", chosen);
      if (chosen) row.setAttribute("aria-current", "true");
      else row.removeAttribute("aria-current");
      if (chosen && !first) first = row;
    }
    first?.scrollIntoView({ block: "nearest" });
    this.view.select(unit);
    if (!fit) return;
    const feature = this.view.footprints.find((item) => item.properties.unit === unit);
    const extent = feature ? extentOf(feature.geometry.coordinates) : null;
    if (extent) this.view.fit(extent);
  }
}
