// Kartograf's server API (ADR-063): the page finds its base as the entry of the tool
// `kartograf` in `nogat-server/1` at GET /api/v1/server of its own origin, so the same files
// run under `kartograf gui serve` and behind Latarnik (`/kartograf/v1`). Every call sends the
// page's language (Accept-Language): the server's problem documents come in it. Answers are
// the envelope `kartograf-result/1`; an error is a problem document (RFC 9457) with the
// fields of `kartograf-error/1`, thrown as an `ApiError` whose `doc` the command form places
// under the field `details.option` names.

import { lang } from "./i18n.js";

const TOOL = "kartograf";
const MAJOR = "1";
const SERVER = "/api/v1/server";
const JSON_TYPES = ["application/json", "application/problem+json"];

/** An answer of the server that is no success: `doc` is its problem document. */
export class ApiError extends Error {
  /**
   * @param {object} doc the problem document, or `{message}` for an answer without one
   * @param {number} status the HTTP status, 0 when the server was not reached
   */
  constructor(doc, status) {
    super(String(doc?.detail ?? doc?.message ?? doc?.title ?? status));
    this.name = "ApiError";
    this.doc = doc;
    this.status = status;
    // The fields of the problem document, so the kit's errorMessages(error) reads them.
    Object.assign(this, doc ?? {});
    this.message = String(doc?.detail ?? doc?.message ?? doc?.title ?? status);
  }
}

async function answer(response) {
  const type = (response.headers.get("content-type") ?? "").split(";")[0].trim();
  const body = JSON_TYPES.includes(type) ? await response.json() : null;
  if (!response.ok) {
    throw new ApiError(body ?? { message: `HTTP ${response.status}` }, response.status);
  }
  return body;
}

async function request(url, init = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { Accept: "application/json", "Accept-Language": lang(), ...init.headers },
    });
  } catch (error) {
    throw new ApiError({ message: String(error?.message ?? error) }, 0);
  }
  return answer(response);
}

/** The API of one server: its base and its routes. */
export class Api {
  /**
   * @param {URL} base the base of the API, ending with `/`
   * @param {object} service the tool's entry of `nogat-server/1`
   */
  constructor(base, service) {
    this.base = base;
    this.service = service;
  }

  /** @returns {string} the version of Kartograf on the server */
  get version() {
    return String(this.service?.version ?? "");
  }

  /**
   * The route of a command: its group and verb under the base (`elevation/download`).
   *
   * @param {string} command the command, `<group> <verb>`
   * @param {URLSearchParams|Object<string, string>} [query] the query
   * @returns {URL} the address of the route
   */
  route(command, query) {
    const url = new URL(command.trim().split(/\s+/).join("/"), this.base);
    if (query) url.search = new URLSearchParams(query).toString();
    return url;
  }

  /** GET a route with its options in the query; resolves to the envelope's `result`. */
  async get(command, query) {
    return (await request(this.route(command, query))).result;
  }

  /** POST a JSON object to a route; resolves to the whole envelope. */
  async post(command, body, query) {
    return request(this.route(command, query), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /**
   * The commands-1 entry of a command with its sections and Polish texts (`--form`).
   *
   * @param {string} command the command, e.g. `elevation download`
   * @returns {Promise<object>} `kartograf-commands/1` of the command
   */
  schema(command) {
    return this.get("commands schema", { command, form: "true" });
  }

  /**
   * The line of a call: `commands format` (the tool's format_command).
   *
   * @param {string} command the command
   * @param {object} options the call as `commands schema` lists its options
   * @returns {Promise<object>} `kartograf-command-line/1`: `options`, `run`, `line`
   */
  async format(command, options) {
    return (await this.post("commands format", { command, options })).result;
  }

  /**
   * The call of a pasted line: `commands parse` (the tool's parse_command).
   *
   * @param {string} line the line, with or without the leading `kartograf`
   * @returns {Promise<object>} `kartograf-command-line/1`
   */
  parse(line) {
    return this.get("commands parse", { line });
  }

  /**
   * The detached plan of a data command: `POST <group>/<verb>?check=true`.
   *
   * @param {string} command the data command
   * @param {object} options the options of the call proper (no target, no run option)
   * @returns {Promise<object>} the envelope `kartograf-result/1` of `kartograf-plan/1`
   */
  plan(command, options) {
    return this.post(command, options, { check: "true" });
  }

  /**
   * A script of the request: `script generate`.
   *
   * @param {object} body `{shell, command}` for the Kartograf script, `{shell, plan, direct:
   *   true, target}` for the direct script of a checked plan
   * @returns {Promise<object>} `kartograf-script/1`
   */
  async script(body) {
    return (await this.post("script generate", body)).result;
  }

  /**
   * A sheet's code read: its system, CRS and bounds.
   *
   * @param {string} sheet the sheet code
   * @returns {Promise<object>} `kartograf-sheet/1`
   */
  sheet(sheet) {
    return this.get("sheet parse", { sheet });
  }

  /**
   * The sheets of an area.
   *
   * @param {number[]} bbox `[west, south, east, north]` in EPSG:4326
   * @param {string} scale e.g. `1:10000`
   * @param {string} system `1992` or `2000`
   * @returns {Promise<object>} `kartograf-sheets/1`
   */
  sheets(bbox, scale, system) {
    return this.get("sheet find", {
      bbox: bbox.join(","),
      bbox_crs: "EPSG:4326",
      scale,
      sheet_system: system,
    });
  }
}

/**
 * Find the API of Kartograf on the page's origin: GET /api/v1/server, the entry of the tool
 * and the base of its major 1, resolved against the document's address.
 *
 * @returns {Promise<Api>} the API
 */
export async function findApi() {
  const where = new URL(SERVER, window.location.origin);
  const doc = await request(where);
  const service = (doc?.services ?? []).find((entry) => entry?.tool === TOOL);
  const base = service?.api?.[MAJOR];
  if (typeof base !== "string" || !base) {
    throw new ApiError({ message: `no ${TOOL} API ${MAJOR} in ${SERVER}` }, 0);
  }
  return new Api(new URL(base.endsWith("/") ? base : `${base}/`, where), service);
}
