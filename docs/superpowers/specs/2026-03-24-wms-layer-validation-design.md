# WMS Layer Validation via GetCapabilities

## Problem

GugikProvider uses hardcoded WMS layer names (`WMS_LAYERS`) to discover OpenData URLs via GetFeatureInfo. When GUGiK renames, adds, or removes layers, the hardcoded list becomes stale. This caused a bug where 5m resolution downloads failed for all sheets because:
- `SkorowidzeNMT2022` was hardcoded instead of `SkorowidzeNMT2022iStarsze`
- `SkorowidzeNMT2021iStarsze` was listed but doesn't exist
- `SkorowidzeNMT2025` was missing

Note: the hardcoded 5m values have already been corrected in the current code. This feature prevents the same class of bug from recurring.

## Solution

Validate hardcoded layer names against WMS GetCapabilities at runtime. When a mismatch is detected, log a warning and use the layers from GetCapabilities instead of the hardcoded list.

## Scope

- **In scope:** `GugikProvider` (NMT) and `GugikNmptProvider` (NMPT, inherits from GugikProvider)
- **Out of scope:** `GugikOrtoProvider` — inherits from `BaseProvider` (not `GugikProvider`), has a flat `WMS_LAYERS` list (not nested dict), a single `WMS_SKOROWIDZE_ENDPOINT` string (not dict), and its own `_get_opendata_url()` implementation. Adapting it requires a separate design.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| When to validate | Lazy, on first `_get_opendata_url()` call | No wasted request if provider only used for WCS bbox downloads |
| On mismatch | Warning + auto-update | Developer sees the drift in logs; users get working downloads |
| On GetCapabilities failure | Warning + hardcoded fallback | Doesn't block downloads when WMS metadata endpoint is down |
| Caching | In-memory per provider instance | GetCapabilities is small (~1KB). One request per session is negligible cost. No schema changes to MetadataCache. |
| Thread-safety | No lock; tolerate duplicate fetch | Two threads seeing a cache miss both fetch GetCapabilities and store the same result. Benign duplicate — same endpoint, same response. Consistent with the simplicity goal. |
| GetCapabilities timeout | 10 seconds (separate from download timeout) | Metadata request is lightweight. Shorter timeout means faster fallback when endpoint is slow. |

## Architecture

### New methods in GugikProvider

**`_fetch_wms_layers(wms_endpoint: str, timeout: int = 10) -> list[str]`**

Sends WMS GetCapabilities request, parses XML response, returns sorted layer names.

- Sends `GET ?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
- Parses XML with `xml.etree.ElementTree`
- Handles WMS 1.3.0 namespace: searches for `{http://www.opengis.net/wms}Name` elements. Falls back to namespace-less `Name` search if no namespace matches found (defensive against server variations).
- Filters to names starting with `Skorowidze` prefix (each WMS endpoint only serves layers for its own product — NMT endpoint serves `SkorowidzeNMT*`, NMPT endpoint serves `SkorowidzeNMPT*`, so a generic `Skorowidze` prefix is safe)
- Sorts: descending by year (regex `(\d{4})`), `iStarsze` layers last
- Raises `requests.RequestException` on network errors
- Raises `ValueError` on unparseable XML or no matching layers

**`_get_validated_layers(resolution: str, vertical_crs: str, timeout: int = 10) -> list[str]`**

Returns validated layer list, using in-memory cache.

1. Check `self._validated_layers.get((resolution, vertical_crs))` — return on hit
2. Look up WMS endpoint from `self.WMS_SKOROWIDZE_ENDPOINTS[resolution][vertical_crs]`
   - If endpoint not found: fall back to `self.WMS_LAYERS[resolution][vertical_crs]` (no warning — this is a config issue, not a server issue)
3. Call `self._fetch_wms_layers(wms_endpoint, timeout)`
4. Compare result with `self.WMS_LAYERS[resolution][vertical_crs]` — **set-based comparison** (order doesn't matter, only presence/absence of layers)
5. If sets differ: log warning with details (see Logging section)
6. Store result in `self._validated_layers[(resolution, vertical_crs)]`
7. On any exception from `_fetch_wms_layers()`: log warning, fall back to hardcoded `WMS_LAYERS`, cache that fallback

### Modified method

**`_get_opendata_url()`**

One change — replace:
```python
resolution_layers = self.WMS_LAYERS.get(self._resolution, {})
wms_layers = resolution_layers.get(self._vertical_crs, [])
```

With:
```python
wms_layers = self._get_validated_layers(self._resolution, self._vertical_crs)
```

Rest of the method unchanged.

### New instance attribute

```python
self._validated_layers: dict[tuple[str, str], list[str]] = {}
```

Initialized in `__init__()`.

### Layer sorting logic

GetCapabilities may return layers in any order. Sorting rules:
1. Extract year from name via regex `(\d{4})`
2. Sort descending by year (newest first)
3. Names containing `iStarsze` sort last regardless of year

Example: `[NMT2023, NMT2025, NMT2022iStarsze, NMT2024]` becomes `[NMT2025, NMT2024, NMT2023, NMT2022iStarsze]`.

## Logging

**On mismatch (WARNING):**
```
WMS GetCapabilities returned different layers than hardcoded for
resolution={resolution}, vertical_crs={vertical_crs}.
Hardcoded: {hardcoded_layers}. Discovered: {discovered_layers}.
Using discovered layers. Consider updating WMS_LAYERS in code.
```

**On GetCapabilities failure (WARNING):**
```
Failed to fetch WMS GetCapabilities from {endpoint}: {error}.
Using hardcoded WMS_LAYERS as fallback.
```

## Error handling

| Scenario | Log level | Action |
|---|---|---|
| GetCapabilities returns layers different from hardcoded | WARNING | Use GetCapabilities layers |
| GetCapabilities layers match hardcoded | (none) | Use hardcoded layers (identical) |
| GetCapabilities timeout / HTTP error / no network | WARNING | Use hardcoded `WMS_LAYERS` |
| GetCapabilities returns empty layer list | WARNING | Use hardcoded `WMS_LAYERS` |
| XML parse failure / no `Skorowidze*` layers found | WARNING | Use hardcoded `WMS_LAYERS` |
| WMS endpoint not found in `WMS_SKOROWIDZE_ENDPOINTS` | (none) | Use hardcoded `WMS_LAYERS` |

## Impact on existing code

- `WMS_LAYERS` class attribute stays as fallback — no removal
- `__init__()` gains `self._validated_layers = {}`
- `_get_opendata_url()` — one line change to call `_get_validated_layers()`
- `GugikNmptProvider` — inherits from `GugikProvider`, has its own `WMS_LAYERS` (with `SkorowidzeNMPT*` prefix) and `WMS_SKOROWIDZE_ENDPOINTS`. Validation works automatically via inheritance since `_get_validated_layers` reads `self.WMS_LAYERS` and `self.WMS_SKOROWIDZE_ENDPOINTS`.
- `GugikOrtoProvider` — **not affected** (separate inheritance tree, separate `_get_opendata_url()`)

## Testing

- Mock GetCapabilities XML responses (with WMS namespace)
- Test: GetCapabilities returns same layers as hardcoded — no warning, uses hardcoded
- Test: GetCapabilities returns different layers — warning logged, uses discovered layers
- Test: GetCapabilities fails (timeout, 500) — warning logged, uses hardcoded fallback
- Test: GetCapabilities returns empty / no Skorowidze layers — warning logged, uses hardcoded
- Test: layer sorting (year descending, iStarsze last)
- Test: in-memory caching (second call doesn't make HTTP request)
- Test: integration with `_get_opendata_url()` — validated layers used for iteration
- Test: GugikNmptProvider inherits validation (NMPT-specific layer names)
- Test: WMS endpoint not found — silent fallback to hardcoded
