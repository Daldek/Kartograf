// The map (ADR-063 decision 9): MapLibre GL JS 6.14.0 from vendor/ (its module worker is a
// file beside it, so the CSP keeps `worker-src 'self'`), the shared base maps drawn by the
// kit's `maplibreBasemap` under the page's own layers (DEV-15.15), and those layers: the
// area of the request, the footprints of the plan's units, the sheets of the view to pick
// one from and the rectangle being drawn. The base map's credit is the map's attribution.

import {
  maplibreBasemap,
  removeMaplibreBasemap,
  repaintMaplibreBasemap,
} from "../nogat/nogat-basemaps.js";

/** The vendored glyphs, as the kit's base maps and the labels of this page read them. */
export const GLYPHS = new URL("vendor/glyphs/{fontstack}/{range}.pbf", document.baseURI).href
  .replace(/%7B/gi, "{")
  .replace(/%7D/gi, "}");
const FONT = ["noto-sans-regular"];
/** Poland and Czechia, the area of the sources of the first version. */
const HOME = [
  [12.0, 48.5],
  [24.2, 55.0],
];
const FIT_PADDING = 40;
/** The page's lowest layer: the base map goes under it. */
const LOWEST = "sheets-fill";
const EMPTY = { type: "FeatureCollection", features: [] };
/** Decimals of a drawn rectangle's degrees: about a metre. */
const DECIMALS = 5;

/** The colours of the page's layers, read from the tokens of the theme shown. */
function palette(element) {
  const style = getComputedStyle(element);
  const token = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
  return {
    background: token("--surface-2", "#f4f1f1"),
    area: token("--accent", "#284b63"),
    unit: token("--tool-kartograf", "#8a5a1c"),
    failed: token("--bad", "#dc2626"),
    sheet: token("--text-2", "#4b4545"),
    halo: token("--surface", "#ffffff"),
  };
}

function rounded(value) {
  const scale = 10 ** DECIMALS;
  return Math.round(value * scale) / scale;
}

/** A rectangle of two corners as `[west, south, east, north]`, in degrees. */
function boxOf(first, second) {
  return [
    rounded(Math.min(first.lng, second.lng)),
    rounded(Math.min(first.lat, second.lat)),
    rounded(Math.max(first.lng, second.lng)),
    rounded(Math.max(first.lat, second.lat)),
  ];
}

/** A GeoJSON polygon of `[west, south, east, north]`. */
export function boxPolygon(bbox, properties = {}) {
  const [west, south, east, north] = bbox;
  return {
    type: "Feature",
    properties,
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
  };
}

function collection(features) {
  return { type: "FeatureCollection", features };
}

/** The page's layers, from the lowest: the sheets, the footprints, the area, the drawing. */
function addLayers(map, colors) {
  for (const name of ["sheets", "footprints", "area", "draw"]) {
    map.addSource(name, { type: "geojson", data: EMPTY });
  }
  map.addLayer({
    id: "sheets-fill",
    type: "fill",
    source: "sheets",
    paint: { "fill-color": colors.sheet, "fill-opacity": 0.04 },
  });
  map.addLayer({
    id: "sheets-line",
    type: "line",
    source: "sheets",
    paint: { "line-color": colors.sheet, "line-width": 1, "line-dasharray": [3, 2] },
  });
  map.addLayer({
    id: "footprints-fill",
    type: "fill",
    source: "footprints",
    paint: {
      "fill-color": ["case", ["get", "failed"], colors.failed, colors.unit],
      "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.35, 0.14],
    },
  });
  map.addLayer({
    id: "footprints-line",
    type: "line",
    source: "footprints",
    paint: {
      "line-color": ["case", ["get", "failed"], colors.failed, colors.unit],
      "line-width": 1.5,
    },
  });
  map.addLayer({
    id: "area-fill",
    type: "fill",
    source: "area",
    paint: { "fill-color": colors.area, "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: "area-line",
    type: "line",
    source: "area",
    paint: { "line-color": colors.area, "line-width": 2 },
  });
  map.addLayer({
    id: "draw-line",
    type: "line",
    source: "draw",
    paint: { "line-color": colors.area, "line-width": 2, "line-dasharray": [2, 1] },
  });
  for (const [source, color] of [
    ["sheets", colors.sheet],
    ["footprints", colors.unit],
  ]) {
    map.addLayer({
      id: `${source}-label`,
      type: "symbol",
      source,
      minzoom: 10,
      layout: {
        "text-field": ["get", "unit"],
        "text-font": FONT,
        "text-size": 11,
        "text-allow-overlap": false,
      },
      paint: { "text-color": color, "text-halo-color": colors.halo, "text-halo-width": 1.2 },
    });
  }
}

function repaintLayers(map, colors) {
  const set = (layer, property, value) => {
    if (map.getLayer(layer)) map.setPaintProperty(layer, property, value);
  };
  set("sheets-fill", "fill-color", colors.sheet);
  set("sheets-line", "line-color", colors.sheet);
  set("sheets-label", "text-color", colors.sheet);
  set("sheets-label", "text-halo-color", colors.halo);
  set("footprints-fill", "fill-color", ["case", ["get", "failed"], colors.failed, colors.unit]);
  set("footprints-line", "line-color", ["case", ["get", "failed"], colors.failed, colors.unit]);
  set("footprints-label", "text-color", colors.unit);
  set("footprints-label", "text-halo-color", colors.halo);
  set("area-fill", "fill-color", colors.area);
  set("area-line", "line-color", colors.area);
  set("draw-line", "line-color", colors.area);
  set("background", "background-color", colors.background);
}

/** The map of the page and what the page draws on it. */
export class MapView {
  /**
   * @param {object} map a MapLibre map with the page's layers
   */
  constructor(map) {
    this.map = map;
    this.drawing = null;
    this.selected = null;
    this.footprints = [];
  }

  /**
   * Draw a base map of the kit's shape, or none (`null`).
   *
   * @param {object|null} entry an entry of the base maps the page offers
   * @param {{locale: string, onFailure: Function}} options its language and its failure
   */
  showBasemap(entry, { locale, onFailure }) {
    if (!entry) {
      removeMaplibreBasemap(this.map);
      return;
    }
    maplibreBasemap(entry, {
      map: this.map,
      glyphs: GLYPHS,
      locale,
      before: LOWEST,
      onFailure,
    }).catch(() => {
      // A failure calls onFailure; a call overtaken by a later one draws nothing.
    });
  }

  /** Repaint the base map and the page's layers in the colours of the theme shown. */
  repaint() {
    repaintMaplibreBasemap(this.map);
    repaintLayers(this.map, palette(this.map.getContainer()));
  }

  /** @param {number[][]|null} ring the area: a closed ring in degrees, `null` for none */
  setArea(ring) {
    const polygon = { type: "Polygon", coordinates: [ring] };
    const area = ring ? collection([{ type: "Feature", properties: {}, geometry: polygon }]) : EMPTY;
    this.map.getSource("area").setData(area);
  }

  /** @param {object[]} features the footprints: polygons with `unit` and `failed` */
  setFootprints(features) {
    this.selected = null;
    this.footprints = features.map((feature, index) => ({ ...feature, id: index }));
    this.map.getSource("footprints").setData(collection(this.footprints));
  }

  /** @param {object[]} features the sheets of the view: polygons with `unit` */
  setSheets(features) {
    this.map.getSource("sheets").setData(collection(features));
  }

  /**
   * Mark one footprint, by its unit, as the one the table shows.
   *
   * @param {string|null} unit the unit, `null` for none
   */
  select(unit) {
    const features = this.footprints;
    if (this.selected !== null) {
      this.map.setFeatureState({ source: "footprints", id: this.selected }, { selected: false });
    }
    const found = features.find((feature) => feature.properties.unit === unit);
    this.selected = found ? found.id : null;
    if (found) {
      this.map.setFeatureState({ source: "footprints", id: found.id }, { selected: true });
    }
  }

  /**
   * Fit the view to features or to a box.
   *
   * @param {number[]} bbox `[west, south, east, north]`
   */
  fit(bbox) {
    this.map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: FIT_PADDING, maxZoom: 14, duration: 0 },
    );
  }

  /** @returns {number[]} the view as `[west, south, east, north]` */
  view() {
    const bounds = this.map.getBounds();
    return [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].map(
      rounded,
    );
  }

  /** @returns {number} the zoom of the view */
  zoom() {
    return this.map.getZoom();
  }

  /** @param {() => void} callback what to do once the view has moved */
  onMoveEnd(callback) {
    this.map.on("moveend", callback);
  }

  /**
   * Draw a rectangle with the pointer: a drag over the map, Esc to stop.
   *
   * @param {(bbox: number[]|null) => void} done called with the rectangle, `null` when the
   *   drawing stopped without one
   */
  draw(done) {
    this.stopDrawing(null);
    const map = this.map;
    const canvas = map.getCanvasContainer();
    let start = null;
    const show = (bbox) => {
      map.getSource("draw").setData(bbox ? collection([boxPolygon(bbox)]) : EMPTY);
    };
    const down = (event) => {
      if (event.originalEvent?.button > 0) return;
      event.preventDefault();
      start = event.lngLat;
    };
    const move = (event) => {
      if (start) show(boxOf(start, event.lngLat));
    };
    const up = (event) => {
      if (!start) return;
      const bbox = boxOf(start, event.lngLat);
      start = null;
      const flat = bbox[0] === bbox[2] || bbox[1] === bbox[3];
      this.stopDrawing(flat ? null : bbox);
    };
    const key = (event) => {
      if (event.key === "Escape") this.stopDrawing(null);
    };
    map.dragPan.disable();
    map.boxZoom.disable();
    canvas.classList.add("drawing");
    map.on("mousedown", down);
    map.on("mousemove", move);
    map.on("mouseup", up);
    map.on("touchstart", down);
    map.on("touchmove", move);
    map.on("touchend", up);
    document.addEventListener("keydown", key);
    this.drawing = {
      done,
      off: () => {
        map.off("mousedown", down);
        map.off("mousemove", move);
        map.off("mouseup", up);
        map.off("touchstart", down);
        map.off("touchmove", move);
        map.off("touchend", up);
        document.removeEventListener("keydown", key);
        canvas.classList.remove("drawing");
        map.dragPan.enable();
        map.boxZoom.enable();
        show(null);
      },
    };
  }

  /**
   * Stop drawing a rectangle.
   *
   * @param {number[]|null} bbox the rectangle drawn, `null` for none
   */
  stopDrawing(bbox) {
    const drawing = this.drawing;
    if (!drawing) return;
    this.drawing = null;
    drawing.off();
    drawing.done(bbox);
  }

  /**
   * Call back with the unit of a sheet or a footprint clicked. While the sheets of the view
   * are shown, a click picks a sheet, never the footprint under it.
   *
   * @param {"sheets"|"footprints"} source the layer's source
   * @param {(unit: string) => void} callback what to do with the unit
   */
  onClick(source, callback) {
    const layer = `${source}-fill`;
    this.map.on("click", layer, (event) => {
      if (this.drawing) return;
      if (source === "footprints") {
        const sheets = this.map.queryRenderedFeatures(event.point, { layers: ["sheets-fill"] });
        if (sheets.length) return;
      }
      const unit = event.features?.[0]?.properties?.unit;
      if (unit) callback(unit);
    });
    this.map.on("mouseenter", layer, () => {
      if (!this.drawing) this.map.getCanvas().classList.add("pointing");
    });
    this.map.on("mouseleave", layer, () => this.map.getCanvas().classList.remove("pointing"));
  }
}

/**
 * Make the map: MapLibre on the page's background, its zoom and scale, and the page's layers.
 *
 * @param {HTMLElement} container the map's element
 * @param {{credit: string, label: string}} texts the name of the credit's button and of the map
 * @returns {Promise<MapView>} the map once loaded
 */
export async function createMap(container, texts) {
  const maplibregl = await import("../vendor/maplibre-gl/maplibre-gl.mjs");
  const colors = palette(container);
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      glyphs: GLYPHS,
      sources: {},
      layers: [
        { id: "background", type: "background", paint: { "background-color": colors.background } },
      ],
    },
    bounds: HOME,
    fitBoundsOptions: { padding: FIT_PADDING },
    attributionControl: { compact: matchMedia("(max-width: 860px)").matches },
    locale: { "AttributionControl.ToggleAttribution": texts.credit, "Map.Title": texts.label },
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
    maxPitch: 0,
    renderWorldCopies: false,
  });
  map.touchZoomRotate.disableRotation();
  map.keyboard.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  // With a listener MapLibre logs nothing itself: a tile or a glyph range that does not load
  // leaves the map as it is (the kit takes a failing base map off); anything else is a
  // fault of this page.
  map.on("error", (event) => {
    if (!event.sourceId) console.warn(event.error);
  });
  await new Promise((resolve) => map.once("load", resolve));
  addLayers(map, colors);
  return new MapView(map);
}
