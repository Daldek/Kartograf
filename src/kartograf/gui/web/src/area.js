// The area of the request on the map (ADR-063 decision 9, plan D1): a rectangle drawn on the
// map is `--bbox … --bbox-crs EPSG:4326`; a sheet of the view picked on the map is `--sheet`
// (the 1:10 000 PL-1992 sheets of `sheet find`, which every product of the page takes); and
// the area the form holds, drawn or typed, is outlined on the map.

import { t } from "./i18n.js";
import { boxOutline, localOutline, ringFeature, sheetOutline } from "./sheets.js";

/** The sheets of the view: their scale and system, from this zoom, at most this many. */
const SHEETS = { scale: "1:10000", system: "1992", zoom: 11, max: 600 };

/** The map bar's tools of the area: draw, pick a sheet, clear; and the area's outline. */
export class AreaTools {
  /**
   * @param {{view: import("./map.js").MapView, api: import("./api.js").Api,
   *   form: import("./form.js").DataForm}} parts the map, the server and the form
   */
  constructor({ view, api, form }) {
    this.view = view;
    this.api = api;
    this.form = form;
    this.outline = null;
    this.turn = 0;
    this.sheetTurn = 0;
    this.drawButton = document.getElementById("draw");
    this.sheetsButton = document.getElementById("sheets");
    this.clearButton = document.getElementById("clear-area");
    this.hint = document.getElementById("map-hint");
    this.say("areaHint");
    this.drawButton.addEventListener("click", () => this.draw());
    this.sheetsButton.addEventListener("click", () => this.toggleSheets());
    this.clearButton.addEventListener("click", () => {
      view.stopDrawing(null);
      form.set({ sheet: undefined, bbox: undefined, bbox_crs: undefined });
    });
    view.onClick("sheets", (unit) => {
      // A sheet's code implies its system: a system given must agree with it.
      const given = form.options.sheet_system !== undefined;
      form.set(given ? { sheet: unit, sheet_system: SHEETS.system } : { sheet: unit });
    });
    view.onMoveEnd(() => this.refreshSheets());
    for (const button of [this.drawButton, this.sheetsButton, this.clearButton]) {
      button.disabled = false;
    }
  }

  /** Draw a rectangle on the map: the form's `bbox` in EPSG:4326. */
  draw() {
    if (this.view.drawing) {
      this.view.stopDrawing(null);
      return;
    }
    this.drawButton.setAttribute("aria-pressed", "true");
    this.say("drawHint");
    this.view.draw((bbox) => {
      this.drawButton.setAttribute("aria-pressed", "false");
      this.say(this.sheetsOn() ? "sheetsHint" : "areaHint");
      if (bbox) this.form.set({ bbox, bbox_crs: "EPSG:4326" });
    });
  }

  /** @returns {boolean} whether the sheets of the view are shown */
  sheetsOn() {
    return this.sheetsButton.getAttribute("aria-pressed") === "true";
  }

  /** Show or hide the sheets of the view, to pick one. */
  toggleSheets() {
    this.sheetsButton.setAttribute("aria-pressed", String(!this.sheetsOn()));
    this.refreshSheets();
  }

  /** The sheets of the view again, after a move or a toggle. */
  async refreshSheets() {
    const turn = ++this.sheetTurn;
    if (!this.sheetsOn()) {
      this.view.setSheets([]);
      if (!this.view.drawing) this.say("areaHint");
      return;
    }
    if (this.view.zoom() < SHEETS.zoom) {
      this.view.setSheets([]);
      this.say("sheetsZoom");
      return;
    }
    let found;
    try {
      found = await this.api.sheets(this.view.view(), SHEETS.scale, SHEETS.system);
    } catch (error) {
      if (turn !== this.sheetTurn) return;
      this.view.setSheets([]);
      this.say("sheetsFailed", { message: error.message });
      return;
    }
    if (turn !== this.sheetTurn) return;
    const codes = found?.sheets ?? [];
    if (codes.length > SHEETS.max) {
      this.view.setSheets([]);
      this.say("sheetsMany", { count: codes.length });
      return;
    }
    this.view.setSheets(
      codes.flatMap((code) => {
        const ring = localOutline(code);
        return ring ? [ringFeature(ring, { unit: code })] : [];
      }),
    );
    if (!this.view.drawing) this.say("sheetsHint");
  }

  /**
   * The map bar's hint.
   *
   * @param {string} key the text's key
   * @param {object} [values] its placeholders
   */
  say(key, values = {}) {
    this.hintKey = { key, values };
    this.hint.textContent = t(key, values);
    this.hint.title = this.hint.textContent;
  }

  /** The hint again in the page's language. */
  relabel() {
    this.say(this.hintKey.key, this.hintKey.values);
  }

  /**
   * Outline the area the form holds: its rectangle, or its sheet (its frame, else the bounds
   * `sheet parse` gives).
   *
   * @param {object} options the form's call
   * @returns {Promise<number[][]|null>} the outline, null for none the page can draw
   */
  async sync(options) {
    const turn = ++this.turn;
    let outline = null;
    if (options.bbox !== undefined) outline = boxOutline(options.bbox, options.bbox_crs);
    else if (typeof options.sheet === "string" && options.sheet) {
      outline = await sheetOutline(options.sheet, (code) => this.api.sheet(code));
    }
    if (turn !== this.turn) return this.outline;
    this.outline = outline;
    this.view.setArea(outline);
    return outline;
  }
}
