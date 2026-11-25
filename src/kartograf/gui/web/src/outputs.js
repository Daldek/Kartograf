// The three outputs of a checked plan (ADR-063 decision 9, plan D3), each to copy or to save:
// (a) by default the command line `commands format` wrote for it, with the target as typed;
// (b) the Kartograf script of that line (`script generate {shell, command}`), which installs
// or finds Kartograf and runs it; (c) the direct script of the plan itself (`script generate
// {shell, plan, direct, target}`, so the server does not plan again), plain curl or
// Invoke-WebRequest, with the files it leaves out and why. The scripts come in bash or
// PowerShell; each is asked for once per plan and shell, when its tab is first shown.

import { reasonText, t } from "./i18n.js";

/** The file names of the outputs. */
const FILES = { line: "kartograf.txt", bash: "kartograf.sh", powershell: "kartograf.ps1" };
const KINDS = ["line", "kartograf", "direct"];
const NOTES = { line: "lineNote", kartograf: "kartografNote", direct: "directNote" };

function make(tag, className = null, text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null) node.textContent = text;
  return node;
}

/** The output section: the tabs, the shell, the text, „Kopiuj” and „Zapisz”. */
export class OutputsView {
  /**
   * @param {HTMLElement} root the section
   * @param {import("./api.js").Api} api the server
   */
  constructor(root, api) {
    this.api = api;
    this.checked = null;
    this.kind = "line";
    this.shell = /Windows/i.test(navigator.userAgent) ? "powershell" : "bash";
    this.scripts = new Map();
    this.turn = 0;
    this.parts = {
      empty: root.querySelector("#outputs-empty"),
      body: root.querySelector("#outputs-body"),
      panel: root.querySelector("#output"),
      tabs: [...root.querySelectorAll("[role=tab]")],
      shell: root.querySelector("#output-shell"),
      shells: [...root.querySelectorAll("[data-shell]")],
      note: root.querySelector("#output-note"),
      leftOut: root.querySelector("#output-left-out"),
      text: root.querySelector("#output-text"),
      copy: root.querySelector("#output-copy"),
      save: root.querySelector("#output-save"),
      status: root.querySelector("#output-status"),
    };
    const { tabs, shells, copy, save } = this.parts;
    for (const tab of tabs) {
      tab.addEventListener("click", () => this.choose(tab.dataset.kind));
      tab.addEventListener("keydown", (event) => {
        const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
        if (!step) return;
        event.preventDefault();
        const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
        next.focus();
        this.choose(next.dataset.kind);
      });
    }
    for (const button of shells) {
      button.addEventListener("click", () => {
        this.shell = button.dataset.shell;
        this._draw();
      });
    }
    copy.addEventListener("click", () => this.copy());
    save.addEventListener("click", () => this.save());
  }

  /**
   * The outputs of a checked plan: the command line first.
   *
   * @param {{line: object, envelope: object}} checked the line of the call and its plan
   */
  show(checked) {
    this.turn += 1;
    this.checked = checked;
    this.scripts = new Map();
    this.kind = "line";
    this.stale(false);
  }

  /** No plan: nothing to give. */
  reset() {
    this.turn += 1;
    this.checked = null;
    this.scripts = new Map();
    this.stale(true);
  }

  /** @param {boolean} value whether the form has changed since the plan: no outputs then */
  stale(value) {
    const shown = this.checked !== null && !value;
    this.parts.body.hidden = !shown;
    this.parts.empty.hidden = shown;
    if (shown) this._draw();
  }

  /** @param {"line"|"kartograf"|"direct"} kind the output shown */
  choose(kind) {
    if (!KINDS.includes(kind)) return;
    this.kind = kind;
    this._draw();
  }

  /** Draw the output chosen again, in the page's language. */
  relabel() {
    if (this.checked !== null && !this.parts.body.hidden) this._draw();
  }

  /** The text shown, null while there is none. */
  _text() {
    if (this.kind === "line") return this.checked.line.line;
    const script = this.scripts.get(`${this.kind} ${this.shell}`);
    return script?.result?.text ?? null;
  }

  /** The name „Zapisz” gives the file. */
  _fileName() {
    return this.kind === "line" ? FILES.line : FILES[this.shell];
  }

  _draw() {
    const { tabs, shell, shells, note, leftOut, text, copy, save } = this.parts;
    for (const tab of tabs) {
      const chosen = tab.dataset.kind === this.kind;
      tab.setAttribute("aria-selected", String(chosen));
      tab.tabIndex = chosen ? 0 : -1;
      if (chosen) {
        this.parts.panel.setAttribute("aria-labelledby", tab.id);
        text.setAttribute("aria-labelledby", tab.id);
      }
    }
    for (const button of shells) {
      button.setAttribute("aria-pressed", String(button.dataset.shell === this.shell));
    }
    shell.hidden = this.kind === "line";
    note.textContent = t(NOTES[this.kind]);
    leftOut.replaceChildren();
    leftOut.hidden = true;
    text.classList.toggle("line", this.kind === "line");
    const key = `${this.kind} ${this.shell}`;
    if (this.kind !== "line" && !this.scripts.has(key)) this._ask(key);
    const script = this.scripts.get(key);
    if (script?.result) this._script(script.result);
    const shown = this._text();
    text.textContent = shown ?? "";
    text.hidden = shown === null;
    copy.disabled = shown === null;
    save.disabled = shown === null;
    if (script?.error) {
      const { message, doc } = script.error;
      this._say("scriptFailed", { message: [message, doc?.hint].filter(Boolean).join(" ") });
    } else if (script && !script.result) this._say("generating");
    else this._say(null);
  }

  /** The files of a direct script and those it leaves out, with the reasons. */
  _script(result) {
    const { note, leftOut } = this.parts;
    if (result.kind !== "direct") return;
    note.textContent = `${t("directNote")} ${t("files", { count: result.files?.length ?? 0 })}`;
    const left = result.left_out ?? [];
    if (!left.length) return;
    leftOut.append(make("li", "heading", t("leftOut")));
    for (const file of left) {
      const words = { name: file.name, reason: reasonText(file.reason) };
      leftOut.append(make("li", null, t("leftOutReason", words)));
    }
    leftOut.hidden = false;
  }

  /** Ask the server for a script of the plan shown, once per kind and shell. */
  async _ask(key) {
    const [kind, shell] = key.split(" ");
    const { line, envelope } = this.checked;
    const turn = this.turn;
    let body = { shell, command: line.line };
    if (kind === "direct") {
      body = { shell, plan: envelope.result, direct: true };
      const target = line.run?.output_dir ?? line.run?.root;
      if (typeof target === "string" && target) body.target = target;
    }
    const entry = { result: null, error: null };
    this.scripts.set(key, entry);
    try {
      entry.result = await this.api.script(body);
    } catch (error) {
      entry.error = error;
    }
    if (turn === this.turn && this.scripts.get(key) === entry) this._draw();
  }

  /**
   * The status beside the buttons, in the page's language.
   *
   * @param {string|null} key the text's key, null for none
   * @param {object} [values] its placeholders
   */
  _say(key, values = {}) {
    this.parts.status.textContent = key ? t(key, values) : "";
  }

  /** Copy the text shown, or select it for the person to copy where the browser refuses. */
  async copy() {
    const shown = this._text();
    if (shown === null) return;
    try {
      await navigator.clipboard.writeText(shown);
      this._say("copied");
    } catch {
      const range = document.createRange();
      range.selectNodeContents(this.parts.text);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      this._say("copyFailed");
    }
  }

  /** Save the text shown as a file of the person's machine. */
  save() {
    const shown = this._text();
    if (shown === null) return;
    const name = this._fileName();
    const content = shown.endsWith("\n") ? shown : `${shown}\n`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = make("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    this._say("saved", { name });
  }
}
