// The page's words in Polish and English (DEV-15.2): its own texts by key and the words it
// gives the kit's elements in English. Polish is the default; the person's choice is kept in
// the browser under `kartograf-lang` (theme-init.js reads it before the first paint). The
// app menu and the sources strip of the kit have Polish words only.

import { BASEMAP_TEXTS } from "../nogat/nogat-basemaps.js";
import { COMMAND_FORM_TEXTS } from "../nogat/nogat-command-form.js";

/** The languages of the page, the default first. */
export const LANGS = ["pl", "en"];
const STORAGE = "kartograf-lang";

const PL = {
  title: "Kartograf: plan i skrypt pobrania danych",
  context: "Plan i skrypt pobrania danych przestrzennych",
  language: "Język strony",
  theme: "Przełącz motyw jasny i ciemny",
  rail: "Nawigacja",
  railData: "Dane",
  railAbout: "O stronie",
  terms: "Regulamin",
  dataHeading: "Dane",
  dataChoice: "Rodzaj danych",
  elevation: "Model wysokościowy",
  elevationNote: "NMT, NMPT, chmury punktów LAZ",
  imagery: "Ortofotomapa",
  imageryNote: "ortofotomapa GUGiK i ČÚZK",
  formLoading: "Wczytuję formularz polecenia…",
  check: "Sprawdź plan",
  checking: "Sprawdzam plan…",
  basemapsHeading: "Podkłady kartograficzne",
  mapLabel: "Mapa: obszar i zarysy plików planu",
  draw: "Zaznacz prostokąt",
  drawHint: "Przeciągnij po mapie, aby zaznaczyć prostokąt; Esc przerywa.",
  areaHint: "Zaznacz prostokąt na mapie, wybierz arkusz albo wpisz obszar w formularzu.",
  sheets: "Arkusze widoku",
  sheetsHint: "Kliknij arkusz, aby go wybrać.",
  sheetsZoom: "Przybliż mapę, aby pokazać arkusze 1:10 000.",
  sheetsMany: "W widoku jest {count} arkuszy: przybliż mapę.",
  sheetsFailed: "Nie udało się pokazać arkuszy: {message}",
  clearArea: "Wyczyść obszar",
  planHeading: "Plan",
  planEmpty:
    "Wypełnij formularz i kliknij „Sprawdź plan”. Zanim cokolwiek powstanie, zobaczysz " +
    "pliki, ich rozmiary, źródła i licencje.",
  planStale: "Formularz się zmienił: sprawdź plan ponownie.",
  planSummary: "Plików: {count}. Sprawdzono {checked}.",
  planIncomplete: "Plan niepełny",
  planFailedItems: "nie udało się sprawdzić plików: {count}",
  planCredentials:
    "dane CLMS wymagają Twojego klucza w CLMS_CREDENTIALS; uruchom polecenie albo skrypt " +
    "Kartografa na swoim komputerze",
  planNotOk: "serwer nie zakończył planu",
  planFailed: "Nie udało się sprawdzić planu: {message}",
  noticesHeading: "Komunikaty",
  colUnit: "Jednostka",
  colFile: "Plik",
  colSize: "Rozmiar",
  colSource: "Źródło",
  colLicence: "Licencja",
  colStatus: "Stan",
  statusWrite: "do pobrania",
  statusReplace: "zastąpi plik",
  statusConflict: "konflikt",
  statusCurrent: "aktualny",
  statusFailed: "nie sprawdzono",
  statusOther: "do pobrania",
  reasonCredentials: "wymaga klucza: tylko polecenie i skrypt Kartografa",
  reasonBuilt: "budowany przez Kartografa: tylko polecenie i skrypt Kartografa",
  reasonFeed: "adres nieznany serwerowi: tylko polecenie i skrypt Kartografa",
  footprints: "Zarysy na mapie: {shown} z {total} jednostek.",
  footprintsNone: "Ten plan nie ma zarysów jednostek na mapie.",
  outputsHeading: "Wynik",
  outputsEmpty: "Polecenie i skrypty pojawią się po sprawdzeniu planu.",
  outputs: "Rodzaj wyniku",
  tabLine: "Polecenie",
  tabKartograf: "Skrypt Kartografa",
  tabDirect: "Skrypt bezpośredni",
  shell: "Powłoka",
  copy: "Kopiuj",
  save: "Zapisz",
  copied: "Skopiowano do schowka.",
  copyFailed: "Nie udało się skopiować: zaznacz tekst i skopiuj go ręcznie.",
  saved: "Zapisano plik {name}.",
  lineNote:
    "Uruchom w terminalu, w którym jest Kartograf: pobierze pliki, sprawdzi je i zapisze " +
    "z metadanymi.",
  kartografNote:
    "Skrypt sprawdza uv, instaluje Kartografa, gdy go brak (uv tool install), i uruchamia " +
    "polecenie; działa wtedy wszystko, co daje Kartograf: ponawianie, kontrole, metadane " +
    "i magazyn.",
  directNote:
    "Skrypt pobiera pliki planu wprost ze źródeł (curl albo Invoke-WebRequest) i zapisuje " +
    "ATTRIBUTION.txt. Nie ponawia pobrań, nie sprawdza formatu, nie zapisuje metadanych " +
    "ani magazynu Kartografa.",
  generating: "Przygotowuję skrypt…",
  scriptFailed: "Nie udało się przygotować skryptu: {message}",
  leftOut: "Pominięte w skrypcie bezpośrednim:",
  leftOutReason: "{name}: {reason}",
  reasons: {
    credentials: "wymaga klucza dostawcy",
    built: "Kartograf go buduje, żaden adres go nie podaje",
    feed_not_cached: "serwer nie zna jeszcze jego adresu",
    no_url: "plan nie podaje jego adresu",
    check_failed: "nie udało się go sprawdzić",
  },
  files: "Plików do pobrania: {count}.",
  keys:
    "Strona nie pyta o klucze API i żadnego nie wysyła: skrypty czytają je ze zmiennych " +
    "środowiskowych na Twoim komputerze.",
  serverMissing:
    "Serwer Kartografa nie odpowiada, więc formularz, plan i skrypty są niedostępne. " +
    "Uruchom „kartograf gui serve” albo sprawdź plan na swoim komputerze: kartograf … --check.",
  serverError: "Serwer odpowiedział błędem: {message}",
  aboutHeading: "O stronie",
  about1:
    "Strona przygotowuje pobranie danych przestrzennych Polski i Czech (GUGiK, ČÚZK) na " +
    "Twoim komputerze. Wybierz dane i obszar, sprawdź plan, a potem skopiuj albo zapisz " +
    "polecenie Kartografa lub skrypt.",
  about2:
    "Dane płyną wprost między Twoim komputerem a źródłem: serwer tylko planuje, niczego nie " +
    "pobiera ani nie przechowuje.",
  aboutVersion: "Kartograf {version}",
  close: "Zamknij",
};

const EN = {
  title: "Kartograf: the plan and script of a download",
  context: "The plan and script of a download of spatial data",
  language: "Language of the page",
  theme: "Switch between the light and the dark theme",
  rail: "Navigation",
  railData: "Data",
  railAbout: "About",
  terms: "Regulamin",
  dataHeading: "Data",
  dataChoice: "Kind of data",
  elevation: "Elevation model",
  elevationNote: "NMT, NMPT, LAZ point clouds",
  imagery: "Orthophoto",
  imageryNote: "orthophoto of GUGiK and ČÚZK",
  formLoading: "Loading the form of the command…",
  check: "Check the plan",
  checking: "Checking the plan…",
  basemapsHeading: "Base maps",
  mapLabel: "Map: the area and the footprints of the planned files",
  draw: "Draw a rectangle",
  drawHint: "Drag over the map to draw a rectangle; Esc cancels.",
  areaHint: "Draw a rectangle on the map, pick a sheet or type the area in the form.",
  sheets: "Sheets of the view",
  sheetsHint: "Click a sheet to choose it.",
  sheetsZoom: "Zoom in to show the 1:10,000 sheets.",
  sheetsMany: "The view has {count} sheets: zoom in.",
  sheetsFailed: "The sheets could not be shown: {message}",
  clearArea: "Clear the area",
  planHeading: "Plan",
  planEmpty:
    "Fill in the form and click “Check the plan”. Before anything is generated you see the " +
    "files, their sizes, sources and licences.",
  planStale: "The form has changed: check the plan again.",
  planSummary: "Files: {count}. Checked {checked}.",
  planIncomplete: "Incomplete plan",
  planFailedItems: "files that could not be checked: {count}",
  planCredentials:
    "the CLMS data need your key in CLMS_CREDENTIALS; run the command or the Kartograf " +
    "script on your own machine",
  planNotOk: "the server did not finish the plan",
  planFailed: "The plan could not be checked: {message}",
  noticesHeading: "Notices",
  colUnit: "Unit",
  colFile: "File",
  colSize: "Size",
  colSource: "Source",
  colLicence: "Licence",
  colStatus: "State",
  statusWrite: "to download",
  statusReplace: "replaces a file",
  statusConflict: "conflict",
  statusCurrent: "current",
  statusFailed: "not checked",
  statusOther: "to download",
  reasonCredentials: "needs a key: the command and the Kartograf script only",
  reasonBuilt: "built by Kartograf: the command and the Kartograf script only",
  reasonFeed: "address unknown to the server: the command and the Kartograf script only",
  footprints: "Footprints on the map: {shown} of {total} units.",
  footprintsNone: "This plan has no footprints of units on the map.",
  outputsHeading: "Result",
  outputsEmpty: "The command and the scripts appear once the plan is checked.",
  outputs: "Kind of result",
  tabLine: "Command",
  tabKartograf: "Kartograf script",
  tabDirect: "Direct script",
  shell: "Shell",
  copy: "Copy",
  save: "Save",
  copied: "Copied to the clipboard.",
  copyFailed: "Copying failed: select the text and copy it yourself.",
  saved: "Saved the file {name}.",
  lineNote:
    "Run it in a terminal with Kartograf: it downloads the files, checks them and writes " +
    "them with their metadata.",
  kartografNote:
    "The script checks for uv, installs Kartograf when it is missing (uv tool install) and " +
    "runs the command, with everything Kartograf does: retries, checks, metadata and the store.",
  directNote:
    "The script downloads the files of the plan straight from their sources (curl or " +
    "Invoke-WebRequest) and writes ATTRIBUTION.txt. It has no retries, no format checks, no " +
    "metadata and no store of Kartograf.",
  generating: "Preparing the script…",
  scriptFailed: "The script could not be prepared: {message}",
  leftOut: "Left out of the direct script:",
  leftOutReason: "{name}: {reason}",
  reasons: {
    credentials: "needs the provider's key",
    built: "Kartograf builds it, no address serves it",
    feed_not_cached: "the server does not know its address yet",
    no_url: "the plan names no address of it",
    check_failed: "it could not be checked",
  },
  files: "Files to download: {count}.",
  keys:
    "The page never asks for an API key and sends none: the scripts read keys from the " +
    "environment variables of your machine.",
  serverMissing:
    "Kartograf's server does not answer, so the form, the plan and the scripts are " +
    "unavailable. Start “kartograf gui serve” or check the plan on your own machine: " +
    "kartograf … --check.",
  serverError: "The server answered with an error: {message}",
  aboutHeading: "About this page",
  about1:
    "The page prepares a download of spatial data of Poland and Czechia (GUGiK, ČÚZK) on " +
    "your own machine. Choose the data and the area, check the plan, then copy or save the " +
    "Kartograf command or a script.",
  about2:
    "The data go straight between your machine and the source: the server only plans, it " +
    "downloads and keeps nothing.",
  aboutVersion: "Kartograf {version}",
  close: "Close",
};

/** The command form's words in English, the placeholders of COMMAND_FORM_TEXTS kept. */
export const FORM_TEXTS_EN = {
  required: "required",
  defaultIs: "default {value}",
  excludedBy: "not with {name}",
  more: "More options",
  choice: "Given as",
  exactlyOne: "one of {count}",
  atMostOne: "at most one of {count}",
  none: "—",
  noneTitle: "no value: the command's default behaviour",
  yes: "yes",
  no: "no",
  example: "e.g. {value}",
  rules: "Rules",
  pathInput: "path to read",
  pathOutput: "path to write",
  pathRoot: "store directory",
  numbersHint: "Separate the values with a space or a semicolon.",
  textsHint: "Separate the values with a comma.",
  aboveForm: "Correct the command",
  missing: "Give a value: the option is required",
  notNumber: "Give a number",
  notInteger: "Give a whole number",
  notNumberItem: "Value {index} (“{text}”) is not a number",
  minimum: "At least {limit} (given {value})",
  maximum: "At most {limit} (given {value})",
  exclusiveMinimum: "Must be more than {limit} (given {value})",
  exclusiveMaximum: "Must be less than {limit} (given {value})",
  notAllowed: "Allowed values: {allowed}",
  pattern: "Does not match the pattern {pattern}",
  date: "Give a date as YYYY-MM-DD",
  dateTime: "Give a date and a time as YYYY-MM-DDThh:mm",
  json: "Invalid JSON: {message}",
  jsonObject: "Give a JSON object: {…}",
  jsonList: "Give a JSON list: [ … ]",
  requires: "Give also: {names}",
  excludes: "Do not combine with: {names}",
  line: "Command",
  incomplete: "Complete or correct: {names}",
  lineFailed: "The command could not be written: {message}",
  copy: "Copy",
  copied: "Copied to the clipboard",
  copyFailed: "Copying failed: select the command and copy it yourself",
  paste: "Paste a command",
  read: "Read",
  pasteFailed: "The command could not be read: {message}",
  otherCommand: "This is the command {command}, not {current}",
};

/** The base map switcher's words in English. */
export const BASEMAP_TEXTS_EN = {
  group: "Base maps",
  name: "Base map",
  none: "no base map",
  failed: "Base map not responding",
  credit: "Show or hide the base map's credit",
  labels: {
    openfreemap: "OpenFreeMap grey",
    "gugik-osm": "OSM GUGiK grey (Poland only)",
    "gugik-ortho": "GUGiK orthophoto",
  },
};

const WORDS = { pl: PL, en: EN };

function stored() {
  try {
    const value = localStorage.getItem(STORAGE);
    return LANGS.includes(value) ? value : null;
  } catch {
    return null;
  }
}

let current = stored() ?? "pl";

/** @returns {"pl"|"en"} the language of the page */
export function lang() {
  return current;
}

/**
 * Switch the page's language: kept in the browser, set on <html>, then `kartograf-lang`
 * fired on the document so the views draw their words again.
 *
 * @param {"pl"|"en"} value the language
 */
export function setLang(value) {
  if (!LANGS.includes(value) || value === current) return;
  current = value;
  try {
    localStorage.setItem(STORAGE, value);
  } catch {
    // A private window: the choice lasts while the page is open.
  }
  document.documentElement.lang = value;
  document.dispatchEvent(new CustomEvent("kartograf-lang", { detail: { lang: value } }));
}

/**
 * A text of the page in its language, `{name}` placeholders filled.
 *
 * @param {string} key the key of the text
 * @param {Object<string, unknown>} [values] the values of its placeholders
 * @returns {string} the text
 */
export function t(key, values = {}) {
  const text = WORDS[current][key] ?? WORDS.pl[key] ?? key;
  return String(text).replace(/\{(\w+)\}/g, (whole, name) =>
    Object.hasOwn(values, name) ? String(values[name]) : whole,
  );
}

/**
 * A reason a direct script leaves a file out, in the page's language.
 *
 * @param {string} reason the reason of `left_out` (credentials, built, …)
 * @returns {string} its words, the reason itself when the page has none
 */
export function reasonText(reason) {
  return WORDS[current].reasons[reason] ?? reason;
}

/** @returns {object} the words of <nogat-command-form> in the page's language */
export function formTexts() {
  return current === "en" ? FORM_TEXTS_EN : COMMAND_FORM_TEXTS;
}

/** @returns {object} the words of <nogat-basemaps> in the page's language */
export function basemapTexts() {
  return current === "en" ? BASEMAP_TEXTS_EN : BASEMAP_TEXTS;
}

/**
 * Write the page's words into the elements that name them: `data-text` (the text),
 * `data-title` (the tooltip), `data-label` (the accessible name).
 *
 * @param {ParentNode} [root] where to look, the whole document by default
 */
export function applyTexts(root = document) {
  for (const element of root.querySelectorAll("[data-text]")) {
    element.textContent = t(element.dataset.text);
  }
  for (const element of root.querySelectorAll("[data-title]")) {
    element.title = t(element.dataset.title);
  }
  for (const element of root.querySelectorAll("[data-label]")) {
    element.setAttribute("aria-label", t(element.dataset.label));
  }
  document.title = t("title");
}
