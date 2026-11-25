// The page of `kartograf gui serve` (ADR-063 decision 9): Nogat's shell with Kartograf's
// mark, the language and the theme, the app menu of the deployment's GUIs, the regulamin of
// a public GUI, and the map over the ecosystem's shared base maps. The deployment's settings
// come from `site.json` beside the page; the API is found by GET /api/v1/server (api.js).

import { findApi } from "./api.js";
import { applyTexts, basemapTexts, lang, setLang, t } from "./i18n.js";
import { createMap } from "./map.js";

const THEME = "nogat-theme";
const PANEL = { min: 260, max: 560, step: 16, bigStep: 64 };

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

/** The left panel's resizer: a drag, the arrow keys, a double click for the default. */
function setupResizers() {
  const layout = document.querySelector(".view-layout");
  for (const resizer of document.querySelectorAll(".resizer")) {
    const side = resizer.dataset.side;
    const variable = `--${side}-w`;
    const initial = parseFloat(getComputedStyle(layout).getPropertyValue(variable)) || 380;
    const width = () => parseFloat(getComputedStyle(layout).getPropertyValue(variable)) || initial;
    const set = (value) => {
      const kept = Math.min(PANEL.max, Math.max(PANEL.min, Math.round(value)));
      layout.style.setProperty(variable, `${kept}px`);
      resizer.setAttribute("aria-valuenow", String(kept));
    };
    resizer.setAttribute("role", "separator");
    resizer.setAttribute("aria-valuemin", String(PANEL.min));
    resizer.setAttribute("aria-valuemax", String(PANEL.max));
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
      const step = event.shiftKey ? PANEL.bigStep : PANEL.step;
      if (event.key === "ArrowLeft") set(width() - sign * step);
      else if (event.key === "ArrowRight") set(width() + sign * step);
      else return;
      event.preventDefault();
    });
    resizer.addEventListener("dblclick", () => set(initial));
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

async function main() {
  applyTexts();
  setupLanguage();
  setupResizers();
  const site = await loadSite().catch(() => ({ basemaps: [], apps: {}, terms: null }));
  setupTerms(site);
  const api = await findApi().catch(() => null);
  document.getElementById("server-missing").hidden = api !== null;
  setupAbout(api);
  await customElements.whenDefined("nogat-basemaps");
  const view = await createMap(document.getElementById("map"), {
    credit: basemapTexts().credit,
    label: t("mapLabel"),
  });
  setupBasemaps(view, site.basemaps ?? []);
  setupTheme(() => view.repaint());
  window.kartograf = { api, view, site };
}

main();
