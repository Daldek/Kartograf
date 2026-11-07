# ADR-059: PGW water management plan data: `hydro download --product pgw`, the national archive and the GeoPackage of an area

**Date:** 2026-11-06
**Status:** Accepted (approved by delegation: on 2026-11-06 the author delegated the architecture of the Nogat
plan `docs/plans/2026-11-06-hydroni-instance.md`, whose decision D1 this ADR carries out; the author reviews it at
the merge); amends ADR-042 (D2: an area of a product published as one national archive is answered from the
stored archive; D6: a version label from the edition of a product's only file; D9: a collection product with
`--layers`)
**Standard:** Nogat 2.1: DEV-17.4, DEV-19 (ADR-054), DEV-10.5, DEV-10.6, DEV-13.2, ERR-4; plan
[`docs/plans/2026-11-06-pgw-water-management-plan-data.md`](../plans/2026-11-06-pgw-water-management-plan-data.md);
Nogat plan `docs/plans/2026-11-06-hydroni-instance.md` (branch `plan/hydroni-instance`, `1fd0317`), step 1

**Context:** Hydrograf's instance for the Hydroni area processes its area by the catchments of PGW Wody Polskie
(Nogat plan D3), and the instance takes its inputs from Kartograf's store (D6). Kartograf therefore downloads the
spatial data of the second update of the river basin management plans (IIaPGW, cycle 2022-2027; PROGRESS item 27).
Measured on 2026-11-06:

- **Publication.** The page <https://apgw.gov.pl/pl/III-cykl-materialy-do-pobrania> links one spatial file,
  "Geobaza IIaPGW":
  `https://wody.isok.gov.pl/api/repo-mdd/publ/download/file/bccfebcf31ac47799fe1de6294b73c29/geobaza-2apgw-ver-20230915-gdb-zip`.
  `HEAD` answers 200 without authentication with `content-type: application/zip`, `content-length: 142048450`,
  `content-disposition: attachment; filename=Geobaza_2aPGW_ver_20230915.gdb.zip`, and neither `ETag` nor
  `Last-Modified`. The file id and the name in the URL name the edition, so a new edition is a new URL. The page
  names no feature service and no licence; for each of its materials it says that PGW Wody Polskie KZGW reserves
  that they are auxiliary and that the legally binding documents are the updated plans published as regulations
  of the Minister of Infrastructure in Dziennik Ustaw (the CC BY-SA 4.0 of the page footer concerns the
  accessibility materials the site was built with).
- **Archive.** One File Geodatabase, `Geobaza_2aPGW_ver_20230915.gdb/` (304 ZIP members, 307.5 MB unpacked, with
  the `gdb` marker file of the format): 25 spatial layers in three feature datasets, `PGW_WP` (16: surface water
  bodies and their catchments, river basin districts, water regions, ecoregions, the regional water management
  authorities, main rivers), `JCWPd` (1: groundwater bodies) and `SIG` (8: protected areas), and 34 attribute
  tables (characteristics, status assessments, environmental objectives, pressures and exemptions, measures,
  relations and threshold values), without field domains. The layers declared as measured (`Rzeki_glowne` and
  six `SIG` layers) hold no M values: GDAL 3.10 reads every feature of them in 2D.
- **CRS.** Every spatial layer carries the same ESRI definition `PUWG_1992`: Transverse Mercator, 19°E,
  k = 0.9993, 500 000 m / -5 300 000 m, GRS 1980, datum ETRS89 (ESRI:102173). pyproj 3.8 (PROJ 9.8.1) finds no
  EPSG code for it and does not take it as equal to EPSG:2180, whose datum the current EPSG dataset names
  ETRF2000-PL; the projection and its five parameters are those of EPSG:2180.
- **Reading.** GDAL reads the geodatabase inside the ZIP (`/vsizip/`). Reading the 25 layers within the
  envelope of the Hydroni area (70 x 78 km) from the archive on the NAS took 11.2 s; a GeoPackage of the 14
  non-empty layers of that envelope is 14.7 MB, written in 4.7 s. Within the envelope `Zlewnie_JCWP_rzecznych`
  has 53 features, `Zlewnie_bezpośrednie_JCWP_jeziornych` 53 and `Pozostale_obszary_JCWP` 4; 36, 45 and 2 of
  them meet the area polygon itself.

What exists: the collection engines of ADR-042 and ADR-043 (`download/collections.py`; `transport/unit_package.py`
stores a national file 1:1 after its HTML, size and ZIP-member checks; `transform/gpkg.py` writes deterministic
GeoPackages of full geometries), the derived versions of `soil hsg` (`hydrology/hsg.py`: the inputs are versions,
a result is reused when a version of the same input `sha256` exists, `extra.source_files` names them), plain mode
and the store (ADR-054) and `extra.parent_request` (ARCHITECTURE 3.4). The group `hydro` has one product, `network`
(HY-NET, CZ; ADR-042 D16).

**Options:**
- A) The area result.
  - A1) Download the archive for every area request and drop it: 142 MB per request, while the Nogat plan wants it
    fetched once.
  - A2) A provider class `providers/pl/pgw.py`: ADR-042 chose engines driven by descriptors over providers for
    collection products.
  - A3) The national archive is a version of the store, and the area GeoPackage is derived from its local version
    by a second channel of the same descriptor that reads layers from it (chosen).
- B) The area of `--geometry`.
  - B1) The features of the geometry: the slot `bbox/<coords>` (ADR-042 D8) would hold different contents for
    geometries with one envelope (rule 9 of ARCHITECTURE 3.3: different contents never share a slot), so the
    slot would need a new form.
  - B2) Its envelope, as for every collection area (ADR-058 decision 4) (chosen). Hydrograf takes the units of its
    own polygon from the GeoPackage (Nogat plan D3).
- C) `--layers` not given.
  - C1) `PGW_WP` alone, the wording of the Nogat plan: a default that chooses data, which the rules for code forbid
    (`CLAUDE.md`).
  - C2) Required: a second meaning of `--layers`, which means "all" when `landcover download` omits it.
  - C3) Every spatial layer (chosen).
- D) The freshness signal of the archive.
  - D1) `http`: the server sends neither `ETag` nor `Last-Modified` and `content_length` never counts (ADR-036
    D28), so every check would be `unverifiable` after a `HEAD`.
  - D2) `metadata` read from the materials page: a CMS page is not a feed, its HTML changes without notice and
    the page belongs to one planning cycle.
  - D3) `metadata` from the edition the registry pins: `--check` would answer `current` without asking the
    source.
  - D4) `none`, with the edition as the version label (chosen; as the BDOT10k archive, ADR-042 D11: label = year,
    `none`).
- E) The CRS of the GeoPackage: a reprojection has nothing to do (the grid is the same), so EPSG:2180 is written
  with the coordinates unchanged after a check of the projection (chosen; `providers/cuzk/client.py` likewise
  replaces the useless CRS of an exportImage answer by the declared one).
- F) The GeoPackage layer names: the source names with Polish letters, or lowercase ASCII names (chosen, as the
  ZABAGED layers, ADR-042 D15).

**Decision:** A3, B2, C3, D4, E and F.

1. **Product.** `hydro download --product pgw --country pl`: the descriptor `pl.pgw.pgw` (`country` PL, `product`
   `pgw`, `provider_name` `PGW Wody Polskie`, a name naming the IIaPGW geodatabase and its cycle, `storage_subdir`
   `hydro/pl_pgw`, `default_extension` `.gpkg`). The group gets its first PL product: `--country pl|cz|auto`, and
   `--country auto` narrows a `pgw` area to PL (`auto_narrowed_to_pl`) as it narrows `network` to CZ. `hydro`
   keeps no `--sheet` and no `--teryt` (`sheet=False` in `catalog/commands/hydro.py`): PGW catchments are taken
   for a study area, not for a map sheet or a county.
2. **Edition and signal.** The only variant is the file published on 2023-09-15 for the IIaPGW cycle (the
   "edition `2apgw-20230915`" of the Nogat plan is this file, `geobaza-2apgw-ver-20230915-gdb-zip`): its URL,
   `PackageVariant.edition` `2023-09-15` (the version label, `label_source="edition"`; a date first, so
   `version_key` orders editions by date) and `members` `("_ver_20230915.gdb/gdb",)`, the marker file of a
   geodatabase whose name carries the edition date. A file of another edition behind the URL is a
   `DownloadError` and never a version under this label. Both channels have the signal `none`: a local version
   is used without a request, `--check` gives `unverifiable` for the archive (`missing` without one), `--force`
   downloads it again (the same bytes: `unchanged`), and a new edition comes with a registry change (its URL and
   label) and `--force`.
3. **National archive (`--whole-country`).** A `unit_package` channel (`UnitPackageParams(unit="country")`,
   `DIRECT_FILES`, capability `country_files`, EPSG:2180) stores the ZIP 1:1 in
   `hydro/pl_pgw_gdb/country/pl.zip`, versions `hydro/pl_pgw_gdb/versions/country/2023-09-15_<sha8>/pl.zip` (the
   format token `gdb`, because the product also has an area result: rule 9). `fetch_package` applies as it is
   (HTML on HTTP 200, the size against `Content-Length`, the ZIP directory, the members), with
   `WHOLE_COUNTRY_SIZE` from the `HEAD` before the transfer and `PACKAGE_TIMEOUT`. `--layers` with
   `--whole-country` is a `ValidationError`: the archive is stored as published.
4. **Area (`--bbox`, `--geometry`).** A second channel of the descriptor (`DIRECT_FILES`, capability
   `bbox_vector`, EPSG:2180, signal `none`) carries new typed parameters, `ArchiveLayersParams`
   (`sources/descriptor.py`, a member of `ChannelParams`): `native_crs`, `layers` (`FeatureLayer`: `code` = the
   feature dataset, the `--layers` value; `source` = the layer in the geodatabase; `name` = the GeoPackage layer;
   `id_field` = the FID column of the layer) and `area_omitted`. The file it reads is the archive of the
   descriptor's national channel (exactly one; a registry test keeps it). An area request runs two jobs:
   1. the archive: the local version of its slot, or one download into the slot (the `run_job` of the national
      file, `DOWNLOAD_SIZE` before the 142 MB transfer); with the archive local, the request sends nothing;
   2. the GeoPackage: the version of the area slot whose `extra.source_files` names the `sha256` of that archive
      version is reused (status `reused`, as HSG); otherwise it is written from the archive and stored with the
      archive's label (`label_source="edition"`).

   The writer is a function of `transform/gpkg.py` beside `write_gpkg`, under the same GDAL lock and fixed
   `OGR_CURRENT_DATE`. It opens the one `*.gdb/` directory of the archive through `/vsizip/` (none or several: a
   `DownloadError`); requires every declared layer (a missing one: `DownloadError`) and, for each layer, the
   projection of `native_crs`: Transverse Mercator, 19°E, 0.9993, 500 000 m / -5 300 000 m on GRS 1980 (another
   CRS: `DownloadError`, nothing is reprojected); reads with the envelope of the area as GDAL's spatial filter and
   keeps a feature whose geometry intersects the area rectangle (shapely `intersects`, the boundary included, as
   the `BBOX` filter of a WFS); writes full geometries (no clipping, `promote_to_multi`, 2D), the features in the
   order of the identifier, which stays a field under its name (`OBJECTID`; `OBJECTID_1` in
   `Regionalne_Zarządy_Gospodarki_Wodnej`), the fields as published; every chosen layer, an empty one with its
   schema, with the `DESCRIPTION` `<dataset>/<source name>`; in a local temporary directory, then the staging
   of the store. No feature in any chosen layer is a `NoCoverageError` (`no_data`, no file), as for
   `feature_bbox`. One archive, area and GDAL version give the same bytes.

   The area is the envelope of the request in EPSG:2180 (`--bbox` through `transform_bbox`; `--geometry` the
   envelope of its features), the slot `hydro/pl_pgw[_<layers>]/bbox/<coords>.gpkg`. The attribute tables are left
   out: every area request emits the `Info` `AREA_OMITTED` saying that they are in the archive of
   `--whole-country`.
5. **`--layers`.** A content option of `hydro download` (catalog `content`, kind `str_list`; the API argument
   `layers` of `download_collection`, `check_collection` and `validate_collection_request`), for `--product pgw`
   with an area only: the codes of the feature datasets `PGW_WP`, `JCWPd` and `SIG`, compared without letter
   case. Not given: every spatial layer, as `landcover download --layers`; an empty list or an unknown code is a
   `ValidationError` with `option="layers"` and `allowed` the three codes. A choice is a segment token as for
   BDOT10k and BDOO (rule 10): the codes sorted, lowercase, `_` written as `-`, joined by `-` (`--layers PGW_WP` ->
   `hydro/pl_pgw_pgw-wp`, `--layers SIG,PGW_WP` -> `hydro/pl_pgw_pgw-wp-sig`), and `request.layers` of the
   sidecar lists them as published.
6. **Layers of the area GeoPackage** (feature counts of the whole archive):

   | `--layers` | Source layer | GeoPackage layer | Geometry | Features |
   |---|---|---|---|---|
   | `PGW_WP` | `Jednolite_Części_Wód_Powierzchniowych_Przybrzeżnych` | `jednolite_czesci_wod_powierzchniowych_przybrzeznych` | MultiPolygon | 4 |
   | `PGW_WP` | `Jednolite_Części_Wód_Powierzchniowych_Rzecznych` | `jednolite_czesci_wod_powierzchniowych_rzecznych` | MultiLineString | 3,116 |
   | `PGW_WP` | `Zlewnie_JCWP_rzecznych` | `zlewnie_jcwp_rzecznych` | MultiPolygon | 3,116 |
   | `PGW_WP` | `Zlewnie_bezpośrednie_JCWP_zbiornikowych` | `zlewnie_bezposrednie_jcwp_zbiornikowych` | MultiPolygon | 45 |
   | `PGW_WP` | `Pozostale_obszary_JCWP` | `pozostale_obszary_jcwp` | MultiPolygon | 156 |
   | `PGW_WP` | `Obszary_dorzeczy` | `obszary_dorzeczy` | MultiPolygon | 9 |
   | `PGW_WP` | `Regiony_wodne` | `regiony_wodne` | MultiPolygon | 23 |
   | `PGW_WP` | `Ekoregiony` | `ekoregiony` | MultiPolygon | 5 |
   | `PGW_WP` | `Jednolite_Części_Wód_Powierzchniowych_Jeziornych` | `jednolite_czesci_wod_powierzchniowych_jeziornych` | MultiPolygon | 1,068 |
   | `PGW_WP` | `Jednolite_Części_Wód_Powierzchniowych_Przejściowych` | `jednolite_czesci_wod_powierzchniowych_przejsciowych` | MultiPolygon | 7 |
   | `PGW_WP` | `Jednolite_Części_Wód_Powierzchniowych_Zbiornikowych` | `jednolite_czesci_wod_powierzchniowych_zbiornikowych` | MultiPolygon | 45 |
   | `PGW_WP` | `Zlewnie_bezpośrednie_JCWP_jeziornych` | `zlewnie_bezposrednie_jcwp_jeziornych` | MultiPolygon | 1,068 |
   | `PGW_WP` | `Zlewnie_JCWP_przejściowych` | `zlewnie_jcwp_przejsciowych` | MultiPolygon | 6 |
   | `PGW_WP` | `Zlewnie_JCWP_przybrzeżnych` | `zlewnie_jcwp_przybrzeznych` | MultiPolygon | 3 |
   | `PGW_WP` | `Regionalne_Zarządy_Gospodarki_Wodnej` | `regionalne_zarzady_gospodarki_wodnej` | MultiPolygon | 11 |
   | `PGW_WP` | `Rzeki_glowne` | `rzeki_glowne` | MultiLineString | 121 |
   | `JCWPd` | `Jednolite_części_wód_podziemnych` | `jednolite_czesci_wod_podziemnych` | MultiPolygon | 174 |
   | `SIG` | `Obszary_chronione_wodozależne_pominiki_przyrody` | `obszary_chronione_wodozalezne_pominiki_przyrody` | MultiPoint | 128 |
   | `SIG` | `Obszary_chronione_wodozależne` | `obszary_chronione_wodozalezne` | MultiPolygon | 9,487 |
   | `SIG` | `Obszary_chronione_JCWP_TW_troć` | `obszary_chronione_jcwp_tw_troc` | MultiPolygon | 2 |
   | `SIG` | `Obszary_chronione_cieki_troć` | `obszary_chronione_cieki_troc` | MultiLineString | 289 |
   | `SIG` | `Obszary_chronione_jeziora_zbiorniki_troć` | `obszary_chronione_jeziora_zbiorniki_troc` | MultiPolygon | 183 |
   | `SIG` | `Obszary_chronione_cieki_węgorz` | `obszary_chronione_cieki_wegorz` | MultiLineString | 121 |
   | `SIG` | `Obszary_chronione_jeziora_zbiorniki_węgorz` | `obszary_chronione_jeziora_zbiorniki_wegorz` | MultiPolygon | 216 |
   | `SIG` | `Obszary_chronione_JCWP_TW_węgorz` | `obszary_chronione_jcwp_tw_wegorz` | MultiPolygon | 2 |

   A GeoPackage name is the source name in lowercase with the Polish letters written without diacritics; the
   source spelling (`pominiki`) stays.
7. **Sidecars.** Both files: `dataset` `pl.pgw.pgw`, `provider` `PGW Wody Polskie`, `horizontal_crs` EPSG:2180,
   `vertical_crs` null, `license` `{"id": "PL-APGW", "attribution": ..., "url":
   "https://apgw.gov.pl/pl/III-cykl-materialy-do-pobrania"}`. The id names the conditions of that publication
   (no licence named); the attribution, in `messages/legal.py` with one wording in every language (as GUGiK's):
   `Dane: PGW Wody Polskie, KZGW, IIaPGW (apgw.gov.pl); materialy pomocnicze, prawnie obowiazuja plany
   gospodarowania wodami ogloszone w Dzienniku Ustaw`. The archive: `request` `{"whole_country": true}`,
   `extra.source` `{url, edition}`, `extra.http` (the headers of the answer), `extra.version`, and
   `extra.parent_request` when an area request created the version (ARCHITECTURE 3.4: the task that created
   it). The GeoPackage: `request` `{bbox, bbox_crs: "EPSG:2180"}` with `layers` when given; `extra.source` `{url,
   edition, member, layers}`, where `member` is the geodatabase directory and `layers` lists `{code, source,
   name, features}` (the keys of the package and area results of ADR-042); `extra.source_files` `[{name:
   "archive", file, sha256, label}]` (the key of HSG: the archive version it was written from);
   `extra.version`; `extra.parent_request` by the rules of collections.
8. **Report and plan.** `CollectionReport` gets `inputs` (`UnitFile`, as HSG's report; the key is already in
   `kartograf-download/1`, filled with `[]`): an area request lists the archive there and the GeoPackage in
   `files`. `check_collection` gives the archive item (`unverifiable` or `missing`) and the GeoPackage item:
   `current` when a version written from the local archive exists, `missing` otherwise or without a local
   archive, `check_failed` when the archive could not be checked. `--upgrade --plan` follows HSG: the derived
   item is judged before the archive changes.
9. **Plain mode.** `--whole-country -o DIR` writes `DIR/pl.zip`; an area writes `DIR/<coords>.gpkg` and nothing
   else: the archive is fetched into the staging directory and removed with it (ADR-054 decision 12, as the
   SoilGrids inputs of HSG), so each plain area request downloads the archive.
10. **Errors.** Before any request, a `ValidationError` (`validation_error`): a missing product or one of another
    group, `--country cz` with `pgw`, no or a second selection, `--layers` empty, unknown, with `--whole-country`
    or with `network`, `--horizontal-crs` other than EPSG:2180. A file that fails is an item of `failed[]` and
    makes `ok` false, as every collection unit (ARCHITECTURE 4.10): `no_coverage` (`no_data`) for a 404 of the
    archive URL (the `unit_package` rule: the source does not publish the file) and for an area without a feature
    in the chosen layers; `download` (`source_unavailable`) for an HTTP failure after the shared retries of
    `transport/http.py`, HTML or a short transfer, not a ZIP, no marker of this edition, no or several
    geodatabases, a declared layer missing, a layer in another CRS, an unreadable layer or geometry. An area whose
    archive fails has no GeoPackage. No new registry code.
11. **Rebuilt commands.** `command_for_file` (KB-6) rebuilds the archive as `hydro download --product pgw
    --country pl --whole-country` (family `unit`) and refuses the area GeoPackage (family `area`), as every
    collection area result.
12. **Consumers.** `kartograf.testing` gets a fixture of the product for Hydrograf's step 3 (DEV-10.6): a small
    archive with the published feature datasets, layer names, fields and CRS definition, written offline by GDAL
    (`pyogrio` writes a File Geodatabase with feature datasets), and its area GeoPackage written by the real
    writer into a store.

**Consequences:**
- `hydro` holds a PL and a CZ product; the texts of the group, `--help`, `list-sources`, the MCP tool
  `kartograf_hydro_download` (`layers`), `AGENTS.md`, `llms.txt` and the generated tables of `docs/USAGE.md`
  follow the catalog.
- A second kind of collection area result: features read from a stored national file instead of a service. The
  first area request downloads 142 MB once; the later ones read the local archive (seconds) and repeat without
  a network.
- An area GeoPackage records the archive version it comes from; a new archive version (a new edition, or bytes
  changed under `--force`) gives a new GeoPackage version on the next request of that area, and the old
  versions stay.
- `--check` cannot see a newer edition: the source has no validators and the edition sits in the URL. A newer
  edition needs a registry change and `--force`, announced in the CHANGELOG of that release.
- The portal names no licence; the sidecar carries the source and the portal's reservation. Whether the data
  may be redistributed is an open question for the author (Kartograf stores, it does not redistribute).
- Out of scope (Nogat plan D1): the plans in editable formats, the table of contents of the files in Dziennik
  Ustaw, the set of measures and the water-body cards (`karty.apgw.gov.pl`); the 34 attribute tables reach a
  user only through the archive.
