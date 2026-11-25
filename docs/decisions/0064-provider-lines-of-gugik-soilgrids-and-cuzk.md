# ADR-064: The provider lines G, SG and Z of GUGiK, ISRIC SoilGrids and ČÚZK in sidecars, documents and `ATTRIBUTION.txt`

**Date:** 2026-11-25
**Status:** Accepted (closes the deviation DEV-20 of `CLAUDE.md`, the open question „Nogat DEV-20 provider lines” of
`docs/PROGRESS.md` and the release finding E2-04; on `feat/provider-lines`, the author reviews it at the merge,
DEV-3.3); amends ADR-054 (decisions 3, 6 and 10: `ATTRIBUTION.txt` in every plain write, its plan position and its
entry in `files[]`), ADR-062 (decisions 8 and 9 and erratum 1: the result documents carry the lines, and the
`ATTRIBUTION.txt` of CAMELS-PL goes through the generic plain write) and ADR-063 (decision 5 (c) and erratum 1: the
direct script writes the plan's lines; decision 9: the strip `<nogat-sources>` reads the plan's `attribution` and
`terms_notice`)
**Standard:** Nogat 1.3: DEV §20 (DEV-20.4 to DEV-20.7, DEV-20.9 to DEV-20.11), DEV-19.1, DEV-19.16, DEV-19.19;
ECO-068

**Context:** Nogat DEV §20 is a table of the lines a provider requires with its data. Standard 1.3 adds the rows W
and WP of PIG-PIB (order 8) and the terms line RW, so G is order 9, SG 10 and Z 11:

```text
G   Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, <products> (wytworzono <period>, pozyskano <date>); dane przetworzone
SG  Źródło: ISRIC – World Soil Information, SoilGrids, licencja CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); dane przetworzone
Z   Źródło: Český úřad zeměměřický a katastrální (ČÚZK), <products> (pozyskano <date>), licencja CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); dane przetworzone
```

In G and Z `<products>` names the products used, joined by „, ”; `<period>` the year the data were created, or the
first and the last joined by an en dash („2020–2025”); `<date>` the day they were downloaded, `YYYY-MM-DD`, or the
first and the last joined by a spaced en dash („2026-03-24 – 2026-10-29”); both from the Kartograf metadata of the
files. DEV-20.9 asks for G on a product with GUGiK data, DEV-20.10 for SG with ISRIC SoilGrids data and DEV-20.11 for
Z with ČÚZK data; the standard's reason is ECO-068 (GUGiK's conditions of reuse ask for its full name, the time the
data were created and acquired and a note that they were processed; SoilGrids and ČÚZK are under CC BY 4.0). DEV-20.5
puts the lines on every surface: `ATTRIBUTION.txt` in the root of a directory of plain files (DEV-19.1), listed in
`files[]`; the fields `attribution` and `terms_notice` of a JSON document, an API or MCP answer; the strip of a GUI
view with the short forms GK, SK and ZK. DEV-20.6 keeps a field a project already has for them, the sidecar's
`license.attribution` (DEV-19.16). DEV-20.7 gives GUGiK, ISRIC and ČÚZK no terms line.

Kartograf carried the lines for CAMELS-PL only: S, P, L and the terms line RD in the sidecar and in `ATTRIBUTION.txt`
of a plain write (ADR-062, erratum 1). The GUGiK, ISRIC and ČÚZK files carried Kartograf's own ASCII text of the
source in `license.attribution` (`sources/registry.py`, `messages/legal.py`: „Dane: Glowny Urzad Geodezji i
Kartografii (www.geoportal.gov.pl), art. 40a …”), a plain directory of them had no `ATTRIBUTION.txt`, and no result
document carried `attribution` or `terms_notice`. `CLAUDE.md` recorded this as the deviation DEV-20 and
`docs/PROGRESS.md` as an open question. The Nogat integration run of `candidate-5` found it again (E2-04, PROGRESS
Next 32): Archiwista indexes the `license.attribution` of a version, so its export and its version card carried
Kartograf's ASCII text, not G, SG and Z. The direct script of ADR-063 (c) merged the registry's texts into its
`ATTRIBUTION.txt` for the same reason.

**Options:**
- A) Where the lines go.
  - A1) Keep the deviation: Archiwista's export and version card, a plain directory and the documents stay without
    the lines DEV-20.9 to DEV-20.11 ask for.
  - A2) The lines in new sidecar fields (`extra.attribution`) beside the old text in `license.attribution`: a file
    with two texts, and Archiwista, which reads `license.attribution`, would still show the old one.
  - A3) `license.attribution` of the sidecar is the filled line, the field DEV-20.6 names; `license.id` and `url`
    stay (chosen).
- B) `<period>`.
  - B1) The year of the download or of the request: it says when Kartograf asked, not when the provider created the
    data, which is what G names.
  - B2) The year the data were created, from the metadata Kartograf has, and `b.d.` when it has none (chosen; the
    abbreviation Hydrograf writes in its own G, its ADR-085).
- C) The names of `<products>`.
  - C1) In the code, beside the descriptors: names with Polish and Czech letters („RÚIAN”, „Modele 3D budynków”) are
    literals outside `kartograf.messages` and `_data`, which `CLAUDE.md` forbids.
  - C2) A data file of the package, one name per registry key, as the provider names the product (chosen).
- D) Several files of one row in one product.
  - D1) One G per file: a directory of 200 sheets would hold a G per flight year and download day.
  - D2) One line per row that names every product once and the years and days first to last, the forms of DEV §20
    (chosen).
- E) The `ATTRIBUTION.txt` of the direct script.
  - E1) Merge in the shell: parse the G or Z line already there and join its years and days, `merge_lines` written
    again in bash and in PowerShell.
  - E2) Append each line the file lacks, as the script did, with `<date>` filled when it runs (chosen).

**Decision:** A3, B2, C2, D2 and E2.

1. **The table and the products.** `_data/provider_lines.json` is the table of Nogat 1.3, byte for byte (W, WP and RW
   added; G, SG and Z orders 9 to 11). `_data/line_products.json` names `<products>` per registry key: the 74
   descriptors of GUGiK and ČÚZK (NMT, NMPT, BDOT10k, PRG, EGiB, PRNG, RCN, BDOO, Ortofotomapa, …, DMR 5G, ZABAGED,
   RÚIAN, …); a test (`tests/unit/test_attribution.py`) checks that it names the product of every GUGiK and ČÚZK
   descriptor and nothing else, and `source_line`
   raises `KeyError` for one it does not name. `LicenseInfo.line` is the code of the line the data of a source carry:
   `G` on the licence of GUGiK, `SG` on SoilGrids, `Z` on ČÚZK, `None` elsewhere (CLMS, PGW, CAMELS-PL). It is not
   written into a document (`metadata={"json": False}`): `license` stays `{id, attribution, url}` and the field is
   not compared. The registry's texts are unchanged: `list-sources` and the `sources[].license.attribution` of a plan
   keep the ASCII text of each source.
2. **The values** (`kartograf.attribution`). `source_line(source, years=, days=)` fills the line of a source;
   `<products>` comes from `_data/line_products.json`. `<period>` is `created_years(sidecar)`: the store's
   `Sidecar.data_year` (the flight, the date of the index record, the edition, the year of the request), else the
   UTC year of `extra.http.last_modified`, else none, which `period_text` writes as `b.d.` (`UNKNOWN`): an answer a
   service builds at the request (a WCS, WFS or OGC API area, an ImageServer cutout) names no year of creation.
   `<date>` is the UTC day of `downloaded_at` (`YYYY-MM-DD`, `date_text`). SG has no value.
3. **Merging** (`merge_lines`, DEV-20.4). The lines of one row whose values are products, years and days (G, Z, W)
   become one line in the place of the first of them: the products each once in the order they came, joined by
   `, `; the years first–last (`2020–2025`, an en dash); the days first – last (`2026-03-24 – 2026-10-29`, a spaced
   en dash); `b.d.` adds nothing and stays only when no line names a value. Two lines of another row (L of two
   releases) stay two. `split_terms` parts the attribution lines from the terms lines; `date_parts(line)` gives the
   text of a G, Z or W line before and after its `<date>` value (`None` for another line).
4. **The sidecar.** `build_metadata` writes the filled line as `license.attribution` of a GUGiK, SoilGrids or ČÚZK
   file (one line); the HSG raster, whose descriptor is SoilGrids, carries SG. CAMELS-PL is unchanged (S, P, L and RD
   in `license.attribution`, `extra.attribution` and `extra.terms_notice`, ADR-062). CORINE (CLMS) and PGW keep the
   registry's text: the table holds no row for them. `file_lines(meta)` gives the lines of a file from its sidecar:
   the line of its source filled from its metadata, else the lines of its `license.attribution`.
5. **Reports.** The five reports of `kartograf-download/1` (`DataReport`, `CollectionReport`, `LandCoverReport`,
   `SoilReport`, `HsgReport`) gain `attribution` and `terms_notice`, arrays of strings, as their last keys: the lines
   of their `files`, `raw` and `inputs`, merged in the order of DEV-20.4. Each file carries its lines
   (`VersionedFile.lines`): those of its version sidecar, or those of the sidecar a plain file would have had (the
   track's sidecar writer runs in `sources.sidecar.built_sidecars`, which keeps the sidecar and writes none;
   `download.fetch.built_lines`).
6. **Plans.** `kartograf-plan/1` gains `attribution` and `terms_notice` as its last keys, computed from its positions
   as the plan knows them and never read from a plan file (`download.plan.item_lines`, `plan_lines`): G and Z name the
   products of their sources; `<period>` is the year a position names (the date of its index record, the label of a
   flight or an edition, the `Last-Modified` of its signal), else `b.d.`; `<date>` is always `b.d.`, since nothing is
   downloaded yet; a position of CAMELS-PL has the lines of the release it names; any other source its registry text.
7. **`ATTRIBUTION.txt` of every plain write** (DEV-20.5). Each file a plain write (`-o DIR`) places brings its lines
   into `DIR/ATTRIBUTION.txt` as soon as it is in place (`add_lines`, called by `download.fetch.store_plain_file`;
   threads of one write merge one after another under `Staging.attribution_lock`): UTF-8, one line per line, the
   attribution lines and then the terms lines, merged into an existing file, nothing removed. The report lists it
   last in `files[]` when the write changed it, `written` when this write made it and `replaced` otherwise. A write
   whose files are not kept (`Staging.scratch`, the HSG's input rasters) adds nothing. The preflight
   (`output.preflight`, `attribution_refusal`) refuses a path `ATTRIBUTION.txt` that is no readable UTF-8 file
   (`conflict`, `output_exists`, exit 4) without `--force`, before any request; with `--force` the lines alone
   replace it. The plan of a plain write (`new_plan`; the detached plan too) lists `ATTRIBUTION.txt` as one position
   after the files (`write`, `replace` or `conflict`; `fetch_reason` `built`; unit and name `ATTRIBUTION.txt`; the
   track of the first position) when the lines of its positions with the action `write` or `replace` would change
   it (a position that failed its check or is a conflict places nothing, so a plan whose only file failed its check
   has none); an existing file is `replace` whenever a line names years or days (G, Z), as the run fills them. A
   merged plan (`--country auto`) keeps one such position. `ATTRIBUTION.txt` is no unit of the request: the `items`
   of the envelope (`kartograf-result/1`) leave out both its file in a report and its position in a plan. The code
   of `download/releases.py` that wrote and planned the `ATTRIBUTION.txt` of CAMELS-PL alone (ADR-062 decision 9)
   gives way to this path.
8. **The direct script** (`kartograf script generate --direct`, ADR-063 decision 5 (c)). The `ATTRIBUTION.txt` of
   its target gets the plan's lines of the files it downloads, with `<date>` the UTC day the script runs: bash
   `date -u +%F`, PowerShell the UTC date in the invariant culture, put between the two parts of `date_parts`. Each
   line the file lacks is appended, as before.
9. **The GUI** (`kartograf gui serve`, ADR-063 decision 9). The kit's `<nogat-sources>` strip of the plan is fed from
   the plan's `attribution` and `terms_notice`: the kit shows the short forms GK, SK and ZK on the strip and the full
   lines in its dialog. The GUI declares as `screenLines` only the lines equal to a source's registry text (CLMS,
   PGW: providers the table holds no row for). The position of `ATTRIBUTION.txt` has no footprint on the map.

**Consequences:**
- Consumers. Archiwista indexes the `license.attribution` of a version, now one line, so its export and version card
  carry G, SG or Z and its strip shows GK, SK and ZK (E2-04). Hydrolog reads the top-level `attribution` and
  `terms_notice` of a sidecar, which Kartograf never writes, and adds SG itself: nothing changes for it. Hydrograf
  fills its own G from Kartograf's metadata (`data_year`, `downloaded_at`, `extra.http.last_modified`) with the same
  `b.d.` (its ADR-085), so both write the same line for the same files.
- A version sidecar is never rewritten (ADR-036): versions written before keep Kartograf's ASCII text in
  `license.attribution`, and so does what Archiwista indexed of them. The reports recompute the line of a listed
  version from its sidecar's metadata (`file_lines`), so a report over old versions carries G, SG and Z all the same.
- The registry's texts stay: `list-sources` and the plan's `sources[]` show the ASCII text of each source, which the
  GUI uses only for CLMS and PGW.
- `kartograf-plan/1` and `kartograf-download/1` only grow (two keys each); a plan file without them still loads.
- A plain directory of several requests holds one G and one Z line that name every product, year and day, and an
  `ATTRIBUTION.txt` already there is always `replace` in the plan of a GUGiK or ČÚZK write.
- Limitation of the direct script: a rerun on another day adds its own G or Z line instead of joining it with the
  earlier one.
- The deviation DEV-20 leaves `CLAUDE.md`, the open question of PROGRESS is closed and E2-04 is done.
