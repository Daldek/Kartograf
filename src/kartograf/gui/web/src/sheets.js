// The outlines of sheets on the map (ADR-063 decision 9, plan D2). A PL-1992 sheet is a
// rectangle of the geographic grid of the International Map of the World, so its outline
// comes from its code alone, as Kartograf's parser computes it (core/sheet_parser.py), down
// to the nine members of a GUGiK LAZ tile, one level below the parser's eight. Any other
// sheet (PL-2000, a ČÚZK TM33 tile) has the bounds `sheet parse` gives in its native CRS,
// drawn by projection.js; an SM5 or ZTM sheet has none (its frame is in ČÚZK's index), nor
// has a code that is no sheet. Only the map reads them: no file, plan or script depends on
// them.

import { knownCrs, ringOf } from "./projection.js";

/** The quarters below the 1:200 000 sheets: their marks, NW, NE, SW and SE in this order. */
const QUARTERS = ["ABCD", "abcd", "1234", "1234", "1234", "1234"];
/** The 1:200 000 sheets of a 1:1 000 000 sheet: 12 rows of 12, numbered from the north-west. */
const GRID = 12;

/** One quarter of `[west, south, east, north]`: `index` 0 to 3 is NW, NE, SW, SE. */
function quarter([west, south, east, north], index) {
  const height = (north - south) / 2;
  const width = (east - west) / 2;
  const top = north - (index >> 1) * height;
  const left = west + (index & 1) * width;
  return [left, top - height, left + width, top];
}

/**
 * The frame of a PL-1992 sheet in longitude and latitude: the 1:1 000 000 sheet of its
 * band and zone, then the 1:500 000 quarter (A to D) or the 1:200 000 sheet (1 to 144), then
 * its quarters (A to D, a to d, then 1 to 4 four times at most).
 *
 * @param {string} code e.g. `N-34-139-A-c-1-3` or the LAZ tile `N-34-139-A-c-1-3-3-3`
 * @returns {number[]|null} `[west, south, east, north]` in degrees, null for another code
 */
export function pl1992Bounds(code) {
  const parts = String(code ?? "").split("-");
  const [band, zone] = parts;
  if (parts.length < 2 || !/^[A-V]$/.test(band) || !/^\d{1,2}$/.test(zone)) return null;
  const column = Number(zone);
  if (column < 1 || column > 60) return null;
  const south = (band.charCodeAt(0) - 65) * 4;
  const west = (column - 31) * 6;
  let bounds = [west, south, west + 6, south + 4];
  if (parts.length === 2) return bounds;
  const third = parts[2];
  if (/^[A-D]$/.test(third)) {
    return parts.length === 3 ? quarter(bounds, "ABCD".indexOf(third)) : null;
  }
  if (!/^\d{1,3}$/.test(third)) return null;
  const number = Number(third);
  if (number < 1 || number > GRID * GRID) return null;
  const height = 4 / GRID;
  const width = 6 / GRID;
  const north = bounds[3] - Math.floor((number - 1) / GRID) * height;
  const left = west + ((number - 1) % GRID) * width;
  bounds = [left, north - height, left + width, north];
  const rest = parts.slice(3);
  if (rest.length > QUARTERS.length) return null;
  for (const [level, mark] of rest.entries()) {
    const index = mark.length === 1 ? QUARTERS[level].indexOf(mark) : -1;
    if (index < 0) return null;
    bounds = quarter(bounds, index);
  }
  return bounds;
}

/** The ring of a rectangle in degrees, closed. */
function boxRing([west, south, east, north]) {
  return [
    [west, south],
    [east, south],
    [east, north],
    [west, north],
    [west, south],
  ];
}

/**
 * A polygon feature of a ring.
 *
 * @param {number[][]} ring the closed ring in degrees
 * @param {object} properties its properties (`unit`, …)
 * @returns {object} the GeoJSON feature
 */
export function ringFeature(ring, properties = {}) {
  return { type: "Feature", properties, geometry: { type: "Polygon", coordinates: [ring] } };
}

/**
 * The outline of a sheet the page can draw without the server: a PL-1992 sheet.
 *
 * @param {string} code the sheet code
 * @returns {number[][]|null} the closed ring in degrees, null for another code
 */
export function localOutline(code) {
  const bounds = pl1992Bounds(code);
  return bounds ? boxRing(bounds) : null;
}

/**
 * The outline of a sheet: its PL-1992 frame, else the bounds `sheet parse` gives.
 *
 * @param {string} code the sheet code
 * @param {(code: string) => Promise<object>} parse the server's `sheet parse`
 * @returns {Promise<number[][]|null>} the closed ring in degrees, null when the sheet has no
 *   bounds the page reads (an SM5 or ZTM sheet, a code that is no sheet, an error)
 */
export async function sheetOutline(code, parse) {
  const local = localOutline(code);
  if (local) return local;
  let sheet;
  try {
    sheet = await parse(code);
  } catch {
    return null;
  }
  const bounds = sheet?.bounds;
  if (!bounds || !Array.isArray(bounds.bbox) || !knownCrs(bounds.crs)) return null;
  return ringOf(bounds.crs, bounds.bbox);
}

/**
 * The outline of a rectangle of a request, as `--bbox` and `--bbox-crs` give it.
 *
 * @param {unknown} bbox `[min_x, min_y, max_x, max_y]`
 * @param {unknown} crs its CRS
 * @returns {number[][]|null} the closed ring in degrees, null when the page cannot draw it
 */
export function boxOutline(bbox, crs) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  if (!bbox.every((value) => typeof value === "number" && Number.isFinite(value))) return null;
  const [xmin, ymin, xmax, ymax] = bbox;
  if (!(xmin < xmax && ymin < ymax) || !knownCrs(String(crs ?? ""))) return null;
  return ringOf(String(crs), bbox);
}

/**
 * Run `work` over `items` with at most `limit` calls at a time.
 *
 * @template T, R
 * @param {T[]} items the items
 * @param {number} limit the calls at a time
 * @param {(item: T) => Promise<R>} work the call of one item
 * @returns {Promise<R[]>} the results in the order of the items
 */
export async function pooled(items, limit, work) {
  const results = new Array(items.length);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const at = next;
      next += 1;
      results[at] = await work(items[at]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}

/**
 * The extent of rings: `[west, south, east, north]`, null for none.
 *
 * @param {number[][][]} rings closed rings in degrees
 * @returns {number[]|null} the extent
 */
export function extentOf(rings) {
  const points = rings.flat();
  if (!points.length) return null;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
