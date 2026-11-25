// The form of the data command (ADR-063 decisions 1, 6 and 9): Nogat's <nogat-command-form>
// generated from `commands schema --form`, its line written by the server's `commands format`
// and a pasted line read by `commands parse`. The first version offers `elevation download`
// (NMT, NMPT, LAZ) and `imagery download` (the orthophoto), the plan's question 3: the page
// narrows their `product` to those, hides the options a person cannot give here (`check` and
// `plan`, which the page drives, and the input file `geometry` with its `layer`, which the
// server refuses) and fills each product's usual choices (Poland, the 1992 sheets, 1 m,
// EVRF2007), which the person may change. Every other option comes from the catalog.

import { formTexts, lang, t } from "./i18n.js";

/** The commands of the page, their products and the choices each product starts with. */
export const COMMANDS = {
  "elevation download": {
    products: ["nmt", "nmpt", "laz"],
    presets: {
      nmt: { country: "pl", sheet_system: "1992", resolution: "1m", vertical_crs: "EVRF2007" },
      nmpt: { country: "pl", sheet_system: "1992", resolution: "1m", vertical_crs: "EVRF2007" },
      laz: { country: "pl", vertical_crs: "EVRF2007" },
    },
  },
  "imagery download": {
    products: ["orto"],
    presets: { orto: { country: "pl", sheet_system: "1992" } },
  },
};
/** The options the form does not show. */
const HIDDEN = ["check", "plan", "geometry", "layer"];
/** The options a call keeps when the person picks the other command: the area, the target. */
const KEPT = ["country", "sheet", "bbox", "bbox_crs", "output_dir", "root"];

/**
 * The key of a call: the same call, the same key.
 *
 * @param {string} command the command
 * @param {object} options its options
 * @returns {string} the key
 */
export function callKey(command, options) {
  const sorted = Object.keys(options)
    .sort()
    .map((name) => [name, options[name]]);
  return JSON.stringify([command, sorted]);
}

/**
 * The entry the form shows: `product` narrowed to the page's products and, on an English page,
 * the catalog's English texts. The kit reads a person's texts from `i18n.pl`, so an English
 * page drops them and gives it the command's English rules there.
 *
 * @param {object} entry the commands-1 entry of `commands schema --form`
 * @param {string[]} products the products offered
 * @param {string} language the page's language
 * @returns {object} the entry
 */
function shownEntry(entry, products, language) {
  const options = entry.options.map((option) => {
    let shown = option;
    if (option.name === "product" && Array.isArray(option.enum)) {
      shown = { ...option, enum: option.enum.filter((item) => products.includes(item.value)) };
    }
    if (language !== "pl") {
      const { i18n: _, ...english } = shown;
      shown = english;
    }
    return shown;
  });
  if (language === "pl") return { ...entry, options };
  const rules = Array.isArray(entry.rules) ? entry.rules : [];
  return { ...entry, options, i18n: { pl: { rules } } };
}

/** The data command's form: its entry, its bindings and the choices of its products. */
export class DataForm {
  /**
   * @param {HTMLElement} element the <nogat-command-form>
   * @param {import("./api.js").Api} api the server
   * @param {{onEdit: () => void, onCommand: (command: string) => void}} callbacks a change of
   *   the call (by the person or the page), and a pasted line of the other command
   */
  constructor(element, api, { onEdit, onCommand }) {
    this.element = element;
    this.api = api;
    this.onEdit = onEdit;
    this.onCommand = onCommand;
    this.command = null;
    this.entries = new Map();
    this.product = null;
    this.pasted = false;
    this.written = null;
    element.hide = HIDDEN;
    element.format = async (command, options) => {
      const line = await api.format(command, options);
      this.written = { key: callKey(command, options), line };
      return line.line;
    };
    element.parse = async (text) => {
      const line = await api.parse(text);
      return { command: line.command, options: { ...line.options, ...line.run } };
    };
    element.addEventListener("change", () => this._edited());
    element.addEventListener("nogat-command-paste", (event) => {
      const { command, options } = event.detail;
      if (command === this.command) {
        this.pasted = true;
        return;
      }
      if (!Object.hasOwn(COMMANDS, command)) return;
      event.preventDefault();
      this.onCommand(command);
      this.load(command, options).then(() => this.onEdit());
    });
  }

  /** @returns {object} the call: the options in the catalog's types */
  get options() {
    return this.element.options;
  }

  /**
   * Show the form of a command: its entry from the server once, then the options given, else
   * the area and target of the form before with the presets of the first product.
   *
   * @param {string} command one of COMMANDS
   * @param {object} [options] the options to show, as a pasted line gives them
   * @returns {Promise<void>} once shown
   */
  async load(command, options) {
    const kept = {};
    for (const name of KEPT) {
      const value = this.element.options[name];
      if (value !== undefined) kept[name] = value;
    }
    if (!this.entries.has(command)) {
      this.entries.set(command, await this.api.schema(command));
    }
    const { products, presets } = COMMANDS[command];
    this.command = command;
    this._show();
    const product = options?.product ?? products[0];
    this.element.options = options ?? { ...presets[product], ...kept, product };
    this.product = this.element.options.product ?? null;
  }

  /** Draw the form again in the page's language, its values kept. */
  relabel() {
    if (!this.command) return;
    const options = this.element.options;
    this._show();
    this.element.options = options;
  }

  /** The entry and the words of the form in the page's language. */
  _show() {
    const doc = this.entries.get(this.command);
    const entry = doc.commands.find((item) => item.name === this.command) ?? doc.commands[0];
    this.element.texts = formTexts();
    this.element.labels = { "#one_of": t("areaGroup"), "#target": t("targetGroup") };
    this.element.command = shownEntry(entry, COMMANDS[this.command].products, lang());
  }

  /** A person's edit: another product takes its own presets, then the page hears of it. */
  _edited() {
    const product = this.element.options.product ?? null;
    if (product !== this.product && !this.pasted) this._presets(this.product, product);
    this.product = product;
    this.pasted = false;
    this.onEdit();
  }

  /**
   * Swap the presets of one product for another's, where the person kept the old values.
   *
   * @param {string|null} from the product before
   * @param {string|null} to the product now
   */
  _presets(from, to) {
    const presets = COMMANDS[this.command].presets;
    const old = presets[from] ?? {};
    const next = presets[to] ?? {};
    const current = this.element.options;
    for (const [name, value] of Object.entries(old)) {
      if (!Object.hasOwn(next, name) && current[name] === value) {
        this.element.setOption(name, undefined);
      }
    }
    for (const [name, value] of Object.entries(next)) {
      if (current[name] === undefined) this.element.setOption(name, value);
    }
  }

  /**
   * Show the values the map gives (a rectangle, a sheet); the page hears of the change.
   *
   * @param {object} values option → value, undefined to empty one
   */
  set(values) {
    for (const [name, value] of Object.entries(values)) this.element.setOption(name, value);
    this.onEdit();
  }

  /** @returns {boolean} whether the form passes the checks of the catalog, its messages shown */
  check() {
    return this.element.check();
  }

  /** @param {object} doc a problem document: its message under the option it names */
  showError(doc) {
    this.element.showError(doc);
  }

  /**
   * The line of a call: the one the form wrote last when it is of this call, else asked anew.
   *
   * @param {object} options the call's options
   * @returns {Promise<object>} `kartograf-command-line/1`: `options`, `run`, `line`
   */
  async line(options) {
    const key = callKey(this.command, options);
    if (this.written?.key === key) return this.written.line;
    return this.api.format(this.command, options);
  }
}
