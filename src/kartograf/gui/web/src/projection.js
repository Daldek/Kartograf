// The map's own reading of the sheet bounds `sheet parse` gives in their native CRS: the
// inverse of the transverse Mercator projections of the sheet systems (GRS 80: PL-1992,
// EPSG:2180; PL-2000, EPSG:2176 to 2179; ETRS89 / UTM 33N of ČÚZK, EPSG:3045), by Krüger's
// series to the fourth power of n (Karney 2011), well under a metre inside a zone. It only
// draws footprints on the map: no file, plan or script depends on it.

const GRS80 = { a: 6378137, f: 1 / 298.257222101 };

/** The transverse Mercator CRSs of the sheet systems: central meridian, scale, offsets. */
const TM = {
  "EPSG:2180": { lon0: 19, k0: 0.9993, fe: 500000, fn: -5300000 },
  "EPSG:2176": { lon0: 15, k0: 0.999923, fe: 5500000, fn: 0 },
  "EPSG:2177": { lon0: 18, k0: 0.999923, fe: 6500000, fn: 0 },
  "EPSG:2178": { lon0: 21, k0: 0.999923, fe: 7500000, fn: 0 },
  "EPSG:2179": { lon0: 24, k0: 0.999923, fe: 8500000, fn: 0 },
  "EPSG:3045": { lon0: 15, k0: 0.9996, fe: 500000, fn: 0 },
};

const n = GRS80.f / (2 - GRS80.f);
const n2 = n * n;
const n3 = n2 * n;
const n4 = n3 * n;
/** The rectifying radius A. */
const A = (GRS80.a / (1 + n)) * (1 + n2 / 4 + n4 / 64);
/** Krüger's β: the series from the projected to the conformal sphere. */
const BETA = [
  n / 2 - (2 / 3) * n2 + (37 / 96) * n3 - n4 / 360,
  n2 / 48 + n3 / 15 - (437 / 1440) * n4,
  (17 / 480) * n3 - (37 / 840) * n4,
  (4397 / 161280) * n4,
];
/** The series from the conformal to the geodetic latitude. */
const DELTA = [
  2 * n - (2 / 3) * n2 - 2 * n3 + (116 / 45) * n4,
  (7 / 3) * n2 - (8 / 5) * n3 - (227 / 45) * n4,
  (56 / 15) * n3 - (136 / 35) * n4,
  (4279 / 630) * n4,
];
const DEG = 180 / Math.PI;

/**
 * Whether the map can draw bounds of a CRS.
 *
 * @param {string} crs e.g. `EPSG:2180`
 * @returns {boolean} whether `toLonLat` reads it
 */
export function knownCrs(crs) {
  return crs === "EPSG:4326" || Object.hasOwn(TM, crs);
}

/**
 * A point of a sheet system in longitude and latitude (EPSG:4326, degrees).
 *
 * @param {string} crs `EPSG:2180`, `EPSG:2176` to `EPSG:2179`, `EPSG:3045` or `EPSG:4326`
 * @param {number} x easting [m]
 * @param {number} y northing [m]
 * @returns {[number, number]} `[longitude, latitude]`
 */
export function toLonLat(crs, x, y) {
  if (crs === "EPSG:4326") return [x, y];
  const p = TM[crs];
  if (!p) throw new RangeError(`no projection of ${crs}`);
  const xi = (y - p.fn) / (p.k0 * A);
  const eta = (x - p.fe) / (p.k0 * A);
  let xi1 = xi;
  let eta1 = eta;
  for (let j = 1; j <= 4; j += 1) {
    const b = BETA[j - 1];
    xi1 -= b * Math.sin(2 * j * xi) * Math.cosh(2 * j * eta);
    eta1 -= b * Math.cos(2 * j * xi) * Math.sinh(2 * j * eta);
  }
  const chi = Math.asin(Math.sin(xi1) / Math.cosh(eta1));
  let phi = chi;
  for (let j = 1; j <= 4; j += 1) phi += DELTA[j - 1] * Math.sin(2 * j * chi);
  const lambda = Math.atan2(Math.sinh(eta1), Math.cos(xi1));
  return [p.lon0 + lambda * DEG, phi * DEG];
}

/**
 * The outline of bounds as a GeoJSON ring in longitude and latitude: the four corners and
 * the first again, each corner projected (a sheet is small, its edges stay straight enough).
 *
 * @param {string} crs the CRS of the bounds
 * @param {number[]} bbox `[xmin, ymin, xmax, ymax]`
 * @returns {number[][]} the ring
 */
export function ringOf(crs, bbox) {
  const [xmin, ymin, xmax, ymax] = bbox;
  const corners = [
    [xmin, ymin],
    [xmax, ymin],
    [xmax, ymax],
    [xmin, ymax],
  ].map(([x, y]) => toLonLat(crs, x, y));
  return [...corners, corners[0]];
}
