# CAMELS-PL on Zenodo: the concept DOI and the newest release (ADR-062)

Recorded on 2026-11-23. `answers.json` holds the URL, status and headers of three answers
(header names in lower case):

- `concept`: `GET https://zenodo.org/api/records/20133182`, the API address of the concept
  DOI 10.5281/zenodo.20133182, answers `302` with `location: /api/records/23275336` (the
  record of the newest release; `requests` follows it), `content-type: text/html;
  charset=utf-8` and `content-length: 229`. Its body is `concept_20133182_302.html`.
- `record`: the `200` answer of `https://zenodo.org/api/records/23275336`, the record of
  release 2.1.0, is `record_23275336.json`: id 23275336, doi 10.5281/zenodo.23275336,
  `metadata.version` 2.1.0, `metadata.publication_date` 2026-10-11, conceptdoi
  10.5281/zenodo.20133182, licence `cc-by-4.0`, and two files:
  `CAMELS_PL_Data_Description.pdf` (352,689 B) and `CAMELS_PL_2.1.zip` (1,670,805,350 B).
  Its headers were not recorded.
- `range`: `GET https://zenodo.org/api/records/23275336/files/CAMELS_PL_2.1.zip/content` with
  `range: bytes=-22` and `accept-encoding: identity` answers `206` without a redirect:
  `content-range: bytes 1670805328-1670805349/1670805350`, `content-length: 22`,
  `accept-ranges: bytes`, `content-type: application/octet-stream`,
  `content-disposition: attachment; filename=CAMELS_PL_2.1.zip`. The body (the end record of
  the ZIP) was not kept.

The tests do not hold the ZIPs of 1.6 GB. `tests/support/camels.py` serves the tiny archives
of `kartograf.testing.build_camels_archive` (the published layout of 2.0.0 and 2.1.0) by
range requests, re-pins the registry entry `pl.camels.camels` to their bytes for one test and
answers the concept DOI with the recorded `302` and record (edited in memory to name a newer
release, or left out to fail the lookup). `tests/unit/test_sources_registry.py` compares the
registry entry of 2.1.0 with the record and the range answer.
