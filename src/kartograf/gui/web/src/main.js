// The page of `kartograf gui serve` (ADR-063 decision 9): Nogat's shell with Kartograf's
// mark, the language and the theme, the app menu of the deployment's GUIs, the regulamin of
// a public GUI, and the map over the ecosystem's shared base maps. Beside the map: the form of
// a data command (form.js), its area drawn or picked on the map (area.js) and its plan,
// checked by the server before anything is generated (plan.js). The deployment's settings
// come from `site.json` beside the page; the API is found by GET /api/v1/server (api.js).

import { findApi } from "./api.js";
import { AreaTools } from "./area.js";
import { DataForm, callKey } from "./form.js";
import { applyTexts, basemapTexts, lang, setLang, t } from "./i18n.js";
import { createMap } from "./map.js";
import { PlanView } from "./plan.js";
import { extentOf } from "./sheets.js";

/** The panels' least and most widths, as Nogat's layout gives them; the default is the CSS's. */
const PANELS = {
  left: { min: 260, max: 560 },
  right: { min: 340, max: 720 },
};
const STEP = { small: 16, big: 64 };
/** Milliseconds between the last edit of the form and the area drawn again. */
const AREA_DELAY = 250;

/** The deployment's settings of the page: base maps, the other GUIs, the regulamin. */
async function loadSite() {
  const response = await fetch(new URL("site.json", document.baseURI), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`site.json: HTTP ${response.status}`);
  return response.json();
}

/** The theme shown: the stored one, else the system's. */
function theme() {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === "light" || chosen === "dark") return chosen;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setupTheme(onChange) {
  document.getElementById("theme").addEventListener("click", () => {
    const next = theme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME, next);
    } catch {
      // A private window: the theme lasts while the page is open.
    }
    onChange();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onChange);
}

function setupLanguage() {
  const buttons = document.querySelectorAll("[data-lang]");
  const mark = () => {
    for (const button of buttons) {
      button.setAttribute("aria-pressed", String(button.dataset.lang === lang()));
    }
  };
  for (const button of buttons) {
    button.addEventListener("click", () => setLang(button.dataset.lang));
  }
  mark();
  document.addEventListener("kartograf-lang", () => {
    mark();
    applyTexts();
  });
}

/** The regulamin of a public GUI: the rail's foot and the app menu (DEV-15.7). */
function setupTerms(site) {
  const link = document.getElementById("rail-terms");
  const menu = document.querySelector("nogat-app-menu");
  if (typeof site.terms === "string" && site.terms) {
    link.href = site.terms;
    link.hidden = false;
    menu.setAttribute("terms", site.terms);
  }
  menu.apps = site.apps ?? {};
}

/** The panels' resizers: a drag, the arrow keys, a double click for the default. */
function setupResizers() {
  const layout = document.querySelector(".view-layout");
  for (const resizer of document.querySelectorAll(".resizer")) {
    const side = resizer.dataset.side;
    const bounds = PANELS[side];
    const variable = `--${side}-w`;
    const width = () => parseFloat(getComputedStyle(layout).getPropertyValue(variable));
    const initial = width();
    const set = (value) => {
      const kept = Math.min(bounds.max, Math.max(bounds.min, Math.round(value)));
      layout.style.setProperty(variable, `${kept}px`);
      resizer.setAttribute("aria-valuenow", String(kept));
    };
    resizer.setAttribute("role", "separator");
    resizer.setAttribute("aria-valuemin", String(bounds.min));
    resizer.setAttribute("aria-valuemax", String(bounds.max));
    resizer.setAttribute("aria-valuenow", String(initial));
    const sign = side === "left" ? 1 : -1;
    resizer.addEventListener("pointerdown", (event) => {
      const startX = event.clientX;
      const startWidth = width();
      resizer.setPointerCapture(event.pointerId);
      resizer.classList.add("dragging");
      const move = (moved) => set(startWidth + sign * (moved.clientX - startX));
      const up = () => {
        resizer.classList.remove("dragging");
        resizer.removeEventListener("pointermove", move);
        resizer.removeEventListener("pointerup", up);
      };
      resizer.addEventListener("pointermove", move);
      resizer.addEventListener("pointerup", up);
    });
    resizer.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? STEP.big : STEP.small;
      if (event.key === "ArrowLeft") set(width() - sign * step);
      else if (event.key === "ArrowRight") set(width() + sign * step);
      else return;
      event.preventDefault();
    });
    resizer.addEventListener("dblclick", () => {
      layout.style.removeProperty(variable);
      resizer.setAttribute("aria-valuenow", String(width()));
    });
  }
}

function setupAbout(api) {
  const dialog = document.getElementById("about");
  document.getElementById("about-open").addEventListener("click", () => dialog.showModal());
  const version = document.getElementById("about-version");
  const show = () => {
    version.textContent = api ? t("aboutVersion", { version: api.version }) : "";
  };
  show();
  document.addEventListener("kartograf-lang", show);
}

/** The base map switcher and the map's base map (DEV-15.15). */
function setupBasemaps(view, entries) {
  const switcher = document.querySelector("nogat-basemaps");
  switcher.texts = basemapTexts();
  switcher.entries = entries;
  const show = (id) => {
    const entry = switcher.entries.find((candidate) => candidate.id === id) ?? null;
    view.showBasemap(entry, { locale: lang(), onFailure: (failed) => switcher.fail(failed) });
  };
  switcher.addEventListener("change", (event) => show(event.detail.id));
  document.addEventListener("kartograf-lang", () => {
    switcher.texts = basemapTexts();
    show(switcher.value);
  });
  show(switcher.value);
}

/** A status line whose words follow the page's language: `say(key, values)`, `say(null)`. */
function statusLine(element) {
  let shown = null;
  const draw = () => {
    element.textContent = shown ? t(shown.key, shown.values) : "";
  };
  document.addEventListener("kartograf-lang", draw);
  return (key, values = {}) => {
    shown = key ? { key, values } : null;
    draw();
  };
}

/**
 * The data command: its choice, its form, its area on the map and its plan.
 *
 * @param {import("./api.js").Api} api the server
 * @param {import("./map.js").MapView} view the map
 * @param {object} site the page's settings
 * @returns {Promise<object>} the parts, for the console and the tests
 */
async function setupData(api, view, site) {
  const formStatus = statusLine(document.getElementById("form-status"));
  const checkStatus = statusLine(document.getElementById("check-status"));
  const button = document.getElementById("check");
  const radios = [...document.querySelectorAll('input[name="command"]')];
  const plan = new PlanView(document.getElementById("plan"), { view, api, terms: site.terms });
  let checked = null;
  let areaTimer = null;
  const form = new DataForm(document.getElementById("form"), api, {
    onEdit: () => edited(),
    onCommand: (command) => mark(command),
  });
  const tools = new AreaTools({ view, api, form });

  function mark(command) {
    for (const radio of radios) radio.checked = radio.value === command;
  }

  function edited() {
    plan.stale(checked !== null && checked.key !== callKey(form.command, form.options));
    clearTimeout(areaTimer);
    areaTimer = setTimeout(() => tools.sync(form.options), AREA_DELAY);
  }

  async function load(command) {
    formStatus("formLoading");
    button.disabled = true;
    try {
      await form.load(command);
    } catch (error) {
      formStatus("formFailed", { message: error.message });
      return;
    }
    formStatus(null);
    button.disabled = false;
    edited();
  }

  async function check() {
    if (!form.check()) {
      checkStatus("formInvalid");
      return;
    }
    const command = form.command;
    const options = form.options;
    button.disabled = true;
    checkStatus("checking");
    const area = await tools.sync(options);
    try {
      const line = await form.line(options);
      const envelope = await api.plan(command, line.options);
      checked = { key: callKey(command, options), command, line, envelope };
      checkStatus(null);
      plan.show(envelope, area).catch((error) => console.warn(error));
    } catch (error) {
      checked = null;
      checkStatus(null);
      if (typeof error?.doc?.details?.option === "string") form.showError(error.doc);
      plan.failed(error);
      const extent = area ? extentOf([area]) : null;
      if (extent) view.fit(extent);
    } finally {
      button.disabled = false;
    }
  }

  for (const radio of radios) {
    radio.addEventListener("change", () => {
      if (radio.checked) load(radio.value);
    });
  }
  button.addEventListener("click", () => check());
  document.addEventListener("kartograf-lang", () => {
    form.relabel();
    plan.relabel();
    tools.relabel();
  });
  await load(radios.find((radio) => radio.checked)?.value ?? radios[0].value);
  return { form, plan, tools, checked: () => checked };
}

async function main() {
  applyTexts();
  setupLanguage();
  setupResizers();
  const site = await loadSite().catch(() => ({ basemaps: [], apps: {}, terms: null }));
  setupTerms(site);
  const api = await findApi().catch(() => null);
  document.getElementById("server-missing").hidden = api !== null;
  document.getElementById("data-form").hidden = api === null;
  setupAbout(api);
  await customElements.whenDefined("nogat-basemaps");
  const view = await createMap(document.getElementById("map"), {
    credit: basemapTexts().credit,
    label: t("mapLabel"),
  });
  setupBasemaps(view, site.basemaps ?? []);
  setupTheme(() => view.repaint());
  const data = api ? await setupData(api, view, site) : null;
  window.kartograf = { api, view, site, data };
}

main();
