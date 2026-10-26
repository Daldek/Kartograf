# ADR-056: One cached index answer for the report and the plans; the TTL of refresh mode

**Date:** 2026-10-26
**Status:** Accepted (the author's problem of 2026-10-26: the plan of a download asks the source again
for what the availability report has just learned); amends ADR-036 (a refreshing cache reads the
answers younger than its `refresh_ttl_seconds`) and ADR-041 (the index answers of the report serve the
sheet download, the archive sheets and the LAZ tiles)
**Standard:** Nogat 2.1: DEV-10.1 (offline tests), AGI-1.3 (a plan without effects)

**Context:** Archiwista plans a download right after `check_availability` of the same area, with the
same `MetadataCache`: "Sprawdź u źródła", then "Pobierz…" of a row runs `check_command` of each line of
the row's `download_hint` (Archiwista ADR-035 D6, ADR-036). The plan asked the index again for all of it:

- `--check` opens the cache in refresh mode (`data.py::_Run.refresh`, live test 0.8.0 P2-2): every
  read is a miss, so nothing the report cached could serve the plan;
- even a reading cache had nothing for it: the report kept its parsed entries under
  `wfs|<endpoint>|<types>|<envelope>` and the GetCapabilities answer under `wfs-types|<endpoint>`,
  while the sheet download asks GetCapabilities again (`WfsSkorowidzLayersMixin._layers`, memoized
  per provider only) and one GetFeature of a 20 m square around the centre of every sheet
  (`_query_layer`), cached per sheet in `campaigns_cache`/`record_cache`; the archive sheets ask an
  area GetFeature of their own (`GugikProvider.index_sheets`) and the LAZ tiles one GetFeature per
  yearly type (`GugikLazProvider._query_layer`).

Measured on the recorded GUGiK answers (`tests/fixtures/gugik_wfs/real_2026_10_15`, Kraków 4 x 4 km,
socket-guarded): the report asks 7 requests (2 GetCapabilities, 2 GetFeature, 3 PRG); the check of its
hint `--year 2025` PL-1992 1 m asks 7 more (GetCapabilities + 6 sheets), PL-2000 2023 1 m 16 (15
sheets), an archive 4 to 8, a LAZ line 10 or 11; the 34 hints of the NMT, NMPT and LAZ reports ask 288
requests. In Archiwista's live trial of 2026-10-26 the 32 per-sheet lines of one row took 31.5 s
before the plan window showed, each check job 1.7-2.1 s, of which the requests were at most about
0.5 s (the job's 0.95 s of work less about 0.4 s of importing Kartograf, an estimate).

**Options considered:**
- (a) A check reads the cache like a download. Reverses P2-2 for every caller: a flight published
  within the TTL would stay unseen by `--check` - rejected.
- (b) A keyword of `check_command` that turns refresh off. Only `check_data` would honour it, while
  every track already opens the cache it is given - rejected for (c).
- (c) A TTL of refresh mode on the cache instance (chosen): an answer younger than it stands for
  asking again; every track and every table read it alike, the caller decides per call, `0` keeps
  P2-2.
- (d) The report writes the per-sheet entries of the sheet download. It would need the providers'
  variant queries, and its entries would outlive the answer they come from - rejected.
- (e) The report keeps its parsed entries with the raw fields of each record. A second record
  format beside the parsers - rejected for (f).
- (f) The answer is kept as the index gave it (chosen): the XML of its features, so each reader runs
  its own parser on the same bytes.

**Decision:**
1. **TTL of refresh mode.** `MetadataCache(..., refresh_ttl_seconds=0)`: in refresh mode
   (`refresh=True`, and the connection `open_cache` opens for a check, `--upgrade` or `--force`,
   which keeps the value of the instance it is given) an entry younger than `refresh_ttl_seconds` is
   read in every table; an older one is a miss and stays for normal reads. Default `0`: refresh mode
   reads nothing, so the CLI and every caller that does not set it ask the source as before (P2-2).
   `MetadataCache.index_area_keys(prefix)` lists the readable keys of a prefix, newest first.
2. **One answer, one entry** (`providers/pl/skorowidz_wfs.py`). `cached_feature_types` keeps the
   yearly types under `wfs-types|<endpoint>`; `area_features` keeps the answer of a GetFeature as the
   XML of its features under `wfs|<endpoint>|<types as asked>|<EPSG:2180 envelope in mm>`. The
   report reads and writes both; a cache of an earlier version (parsed entries) is a miss there, so
   the first report asks again once.
3. **Readers.**
   - The sheet download (`WfsSkorowidzLayersMixin`): the types from the shared entry; the records of a
     sheet from the newest cached answer of all the types of the service for an envelope that the
     sheet's frame overlaps by more than the edge sliver (`overlaps_area`). The index gives every
     record its sheet frame (276 of 319 recorded features match the frame within 0.01 %, the other 43
     are the same frames densified, within 7 cm), so that answer holds every record of the sheet; a
     query around the centre selects from the same records. A sheet without a matching record there
     asks the index, which also gives the no-coverage hints.
   - The archive sheets (`index_sheets`): a cached answer of the types (or more) for an envelope that
     contains the area's envelope; its other features never overlap the area.
   - The LAZ tiles: a cached answer for the same envelope stands for the query of each of its types (an
     answer of several types holds per type what the type alone gives, recorded 2026-10-15).
4. **No entry of its own.** A record read from a cached answer writes no `record_cache` or
   `campaigns_cache` entry: the answer keeps its age, so nothing is served after its TTL.

**Consequences:**
- With a cache of `refresh_ttl_seconds` covering the time since the report, the check of every PL
  hint of the report asks the index nothing: 0 of the 288 requests above, and on all 80 hints of the
  recorded Kraków and Pomorze reports (sheets inside the area and at its edge, PL-2000 scales,
  `--full-sheet`, archives, LAZ) the plan equals the plan asking the index gives
  (`tests/integration/test_availability.py`).
- The default download mode reads the shared answers within the TTL as it reads `record_cache`: a
  download right after a report asks the index nothing either; the LAZ tiles of a reported area are
  read from the report's answer (they were asked every time before).
- An answer is kept larger than the parsed entries were (Kraków NMT EVRF2007, 80 features: 188 KB
  instead of 39 KB); a cached report parses it again.
- Not covered: the CZ part (one `HEAD` per file and the CUZK sheet index have their own entries) and
  the run of a plan, which refreshes (`--upgrade`) unless its caller sets the TTL too.
