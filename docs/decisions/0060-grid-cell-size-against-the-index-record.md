# ADR-060: The cell size of a downloaded grid against its index record: a failed unit `resolution_mismatch`

**Date:** 2026-11-09
**Status:** Accepted (the author's approval of the recommendations of PROGRESS item 28, 2026-11-09)
**Standard:** Nogat 1.0: ERR-1 (one registry code, the refinement in `details.reason`), DEV-10.1 (offline tests)

**Context:** On 2026-11-07 the Hydroni store held 20 sheets of `nmt/pl_1992_5m_evrf2007` (records of the NMT
5 m index, `resolution_m` 5.0, sidecar `resolution` `5m`) whose files are `cellsize 1.00` grids, all of campaign
75114 (PROGRESS item 28). Kartograf stored them without noticing, and Hydrograf's `-resolution highest` mosaic of
the segment became a 1 m grid of 5.83 G cells. The live check of 2026-11-08 (item 28 (b)) found 81 such records
in the whole 5 m index (campaigns 75114, 74964, 75108, 76742, 76597; years 2021 and 2022): each file is, byte
for byte, the 1 m product of an earlier flight carrying the later date of the 5 m campaign, so "the newest
flight" selects it over the genuine 5 m flights of 2020, 2023 or 2025. Nothing in the record tells it; the file
size and the flight date are no sign either (PL-2000 5 m sheets of campaign 73929 are 6.6 to 10.9 MB and
genuine).

**Options considered:**
- (a) A notice and the file stored as it is. The grid stays in the 5 m segment, where `iter_store` consumers
  and Hydrograf read it as 5 m: the defect itself - rejected.
- (b) The file stored as 1 m (another segment). It duplicates, byte for byte, the 1 m flight that
  `--resolution 1m` downloads anyway, and Kartograf does not resample - rejected.
- (c) Per sheet, fall back to the next newest 5 m flight within the year bounds, with a notice
  `resolution_fallback`. It changes which data is chosen without the caller asking: the same call would give a
  2020 flight for one sheet and 2021 for its neighbour, decided by a download, while every choice of data is
  explicit (ADR-044, ADR-032); a check (`--check`) could not plan it either, since the cell size is known only
  after the transfer - rejected.
- (d) A failed unit (chosen): nothing of the flight is written, the unit carries the facts and the hint names
  the flags that choose another flight (`--year`, `--max-year`) and the other years the index lists for the
  sheet.

**Decision:**
1. **The check.** Before a downloaded grid of an elevation sheet (`GugikProvider` and `GugikNmptProvider`,
   provider attribute `checks_cell_size`) becomes a version (`DownloadManager._download_version`) or a plain
   file (`_fetch_plain`), `kartograf.download.campaigns.verify_cell_size` reads its cell size and compares it with
   `resolution_m` of the index record, on both axes, with a tolerance of 1e-3 m (`CELL_SIZE_TOLERANCE_M`):
   - `.asc`: the header, keys of any case (`CELLSIZE`, `cellsize`), the value as a float (`5`, `5.0`, `5.00`),
     or `dx` and `dy` instead of `cellsize` (`verify_sheet_extent` reads `dx`/`dy` too);
   - `.tif`: `abs(a)` and `abs(e)` of the GeoTIFF transform;
   - archives and records without `resolution_m` are not checked; orthophotos are not checked (no defect
     known, and their records declare a pixel size of another kind).
   It runs after `verify_file_format` and `verify_sheet_extent`, in the staging directory.
2. **The failure.** A mismatch is `ResolutionMismatchError`, a `DownloadError` with the registry code
   `data_error` (exit code 7; no new code: the data read by the tool violates what its record declares) and
   the reason `resolution_mismatch`; its attributes (`details`) are `sheet`, `campaign` (`<date>_<id>`), `url`,
   `declared_m` and `found_m`. The hint names `--year` and `--max-year` and the other years of the sheet in the
   index when the request knows them (a year range was given), else `kartograf elevation availability`. A cell
   size that cannot be read is a `DownloadError` (`source_unavailable`), as an incomplete header is.
3. **Nothing written.** The staged file is removed: no version, no standard path, no `full_sheet/` link, no
   sidecar, no plain file. Other flights of the same request (`--all-campaigns`, `--full-sheet`) are written as
   before.
4. **The unit.** A sheet whose only problem is the mismatch fails with that error (not the generic list of
   campaign errors); the download report has a failed unit of the sheet with `kind` `resolution_mismatch` and
   `code` `data_error` (`FAILURE_CODES`), in a single sheet and in a sheet list alike
   (`DownloadResult.resolution_mismatch`; such a sheet is not a `hard_failures` entry, which stays the transport
   failures). A unit carries only a message, so its message ends with the hint (`Remedy: ...`,
   `campaigns.failure_text`). The progress event of the sheet is `failed`.
5. **Stores already filled** keep their grids: removing them is the store owner's step (PROGRESS item 28 (a)).

**Consequences:**
- A request of the 5 m index that meets one of the 81 records fails that sheet with exit code 10 or 11 instead
  of storing a 1 m grid; `--max-year 2020` or `--year 2025` (or 2023 for some sheets) gets the 5 m grid.
- One header read per sheet (`.asc`: six lines; `.tif`: the GeoTIFF header through rasterio).
- A future source that declares one size and serves another fails loudly too, in every elevation variant.
- GUGiK should still be told (PROGRESS item 28 (b), the author's step); Kartograf does not choose another
  flight by itself.
