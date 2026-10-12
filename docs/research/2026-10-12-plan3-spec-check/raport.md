# Weryfikacja specu magazynu wersjonowanego przed planem 3/3 (2026-10-12)

**Zakres:** sekcje 3.3, 3.4, 4.1-4.5, 5 i 8 specu
`docs/superpowers/specs/2026-10-08-versioned-store-design.md` wobec kodu
galezi `feat/versioned-store` (`369e7cf`) dla land cover (BDOT10k, CORINE,
SoilGrids) i HSG, plus zapytania na zywo o metadane wydan (bez pobierania
danych, bez `CLMS_CREDENTIALS`). Uzupelnia inwentaryzacje
`docs/research/2026-10-12-signal-inventory/raport.md`.

## 1. CORINE — metadane wydania w publicznym katalogu CLMS

`GET https://land.copernicus.eu/api/@search?UID=<uid>&fullobjects=1`
(naglowek `Accept: application/json`, bez uwierzytelnienia) zwraca rekord
zbioru z polem `characteristics_release_major_version`. Odpowiedz dla CLC 2018
zapisana w `tests/fixtures/signals/real_2026_10_12/clms_corine_2018_search.json`.

| Pole (CLC 2018, UID `0407d497d3c44bcd93ce8fd5bf78596a`) | Wartosc |
|---|---|
| `characteristics_release_major_version` | `V2020_20u1` |
| `dataset_download_information.items[RASTER]` | `@id` `7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb`, `full_path` `...U2018_CLC2018_V2020_20u1_raster100m_tiled` |
| `downloadable_files.items[0].version` | `v2020_20u1` |
| `modified` | `2026-09-23T08:42:00+00:00` (rekord strony, nie dane) |
| Naglowki odpowiedzi | `ETag` strony Plone (`"\|\|1939050\|en\|..."`), `Cache-Control: max-age=10` — opisuja dokument, nie zbior |

Wydanie (`V2020_20u1`) jest tozsamoscia tresci zbioru: ta sama wartosc w
sciezce danych zrodla (`full_path`) i w liscie plikow. Zmiana wydania =
nowe dane CLC tego rocznika. Sygnal `metadata` = to pole; etykieta `edition`
= jego wartosc. Rocznik CORINE (`year`) jest parametrem zadania, nie
wersja — nalezy do segmentu.

**UID-y w kodzie:** `CorineProvider.CLMS_DATASET_UIDS` i
`CLMS_RASTER_DOWNLOAD_IDS` (`kartograf/providers/corine.py:207-220`) sa
poprawne tylko dla 2018. Wyszukanie
`@search?portal_type=DataSet&SearchableText=CORINE%20Land%20Cover` (2026-10-12):

| Rocznik | UID zbioru (katalog) | `@id` RASTER (katalog) | W kodzie |
|---|---|---|---|
| 2018 | `0407d497d3c44bcd93ce8fd5bf78596a` | `7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb` | zgodne |
| 2012 | `a5ee71470be04d66bcff498f94ceb5dc` | `b1027c88-6256-435b-98a3-62f019cbb381` | `f0a04d46-...`, `b0a2b7bb-...` — UID nie istnieje (`items_total: 0`) |
| 2006 | `d443c86fec2f49e08ff12c7decdbf2af` | `4841f8cb-6e7c-4227-bb35-cd787609c546` | `e6f25e4e-...`, `a99e5c2f-...` — UID nie istnieje |
| 2000 | `6704f90ca82e4f228a46111519f8978e` | `19d7fbd8-53ee-4d09-89b6-fe5231247763` | `a3f977ae-...`, `c8f3c1d2-2e7a-4b5c-8e0d-1a2b3c4d5e6f` — UID nie istnieje |
| 1990 | `8b393c8e474642d5acb4ed70fc2dc024` | `fecff4c7-a5e5-428d-817d-a8ee5f23d99d` | brak (1990 tylko podglad WMS) |

Kazdy rocznik ma dzis `V2020_20u1`. Pobrania CLMS (`@datarequest_post`) nie
sprawdzono — wymaga `CLMS_CREDENTIALS` (odlozone). Niesprawdzone
pozostaje tez, czy plik z `DownloadURL` jest GeoTIFF-em (kod zapisuje go
jako `.tif`, `corine.py:644-652`) czy archiwum.

**Kanal bez credentials:** `CorineProvider` bez tokenu CLMS pobiera stylizowany
PNG z WMS EEA (1990: DLR) — `extra.fallback = "wms_png"`, "podglad WMS, nie
dane" (`kartograf/landcover/manager.py:676-687`). Deskryptor `eu.clms.corine`
ma jeden kanal (`CLMS_API`, `metadata`); podglad jest tylko w `notes`.

## 2. SoilGrids — wydanie per wlasciwosc

GetCapabilities WCS 2.0.1 kazdej mapy wlasciwosci
(`https://maps.isric.org/mapserv?map=/map/<property>.map&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCapabilities`)
ma `ows:Title` w postaci `SoilGrids250m <wydanie> - <opis>`; 2026-10-12:
`SoilGrids250m 2.0 - Clay content`, `... Sand content`, `... Silt content`
(fixtura `isric_soilgrids_capabilities_get.xml` z inwentaryzacji). Brak daty
i rewizji per coverage.

Serwer plikow ISRIC (`files.isric.org/soilgrids/`): `README.md` opisuje
`former` (wydanie z 2017-03-10) i `latest` (biezace wydanie) — wersjonowanie
na poziomie wydan. VRT `latest/data/clay/clay_0-5cm_mean.vrt` ma `ETag` i
`Last-Modified: Tue, 02 Jun 2020 15:55:55 GMT`, ale to inny kanal niz WCS
(kafle pod VRT moga sie zmieniac bez zmiany VRT; brak dowodu, ze WCS czyta te
pliki) — nie jest sygnalem tresci zwracanej przez GetCoverage.

Wniosek: sygnal `metadata` = wydanie z tytulu GetCapabilities danej
wlasciwosci, etykieta `edition` = `2.0`. Poprawka w obrebie wydania jest
niewykrywalna bez `--force` (ograniczenie spec 4.1, jak przy `index`).

## 3. Kod land cover i HSG (stan `369e7cf`)

- `LandCoverManager` (`kartograf/landcover/manager.py`): jedna sciezka na plik
  w korzeniu `output_dir`, nazwa `<zrodlo>[_<param>...]_<tryb>_<id>.<ext>`
  (`_generate_output_path` 610-651; bbox jako `:.0f`), nadpisanie przy kazdym
  pobraniu, opcjonalne `output_path` wywolujacego (Hydrograf go uzywa:
  `Hydrograf/backend/scripts/download_landcover.py:134,154,189`).
- BDOT10k: `Bdot10kProvider.download_package` (`providers/pl/bdot10k.py:174-292`)
  sklada GPKG w lokalnym katalogu tymczasowym i kopiuje wynik
  (`_merge_gpkg_files` 626-677; blad SQLite na CIFS z 2026-10-07 nie dotyczy
  juz katalogu wyniku); `keep_raw` zapisuje ZIP przez `os.replace`;
  `extra.http` niesie tylko `content_length` (sygnal `none`).
- SoilGrids: `download_by_bbox` (`providers/soilgrids.py:165-251`) — WCS do
  `output_path.with_suffix(".tif")`; TERYT = `NotImplementedError`; CORINE
  TERYT tez (`providers/corine.py:752-770`).
- HSG: `HSGCalculator.calculate_hsg_by_bbox(bbox, output_path, ...)`
  (`hydrology/hsg.py:458-579`) pobiera clay/sand/silt do katalogu
  tymczasowego (`keep_intermediate` kopiuje je obok wyniku jako
  `clay.tif`/`sand.tif`/`silt.tif`); sidecar bez `source_files[]`.
  `hsg_from_rasters` (672-742) pisze pod sciezke wywolujacego, sidecar z
  `source_files[]` (`name`, `file`, `sha256`).
- CLI `soilgrids hsg` z `--bbox`/`--geometry` i katalogiem w `--output`
  zapisuje `hsg_bbox_<depth>.tif` (`cli/soilgrids_cmd.py:102-109`) — dwa
  rozne obszary dziela jedna nazwe (drugie uruchomienie nadpisuje pierwsze).
- Deskryptory `pl.gugik.bdot10k`, `eu.clms.corine`, `global.isric.soilgrids`
  maja `storage_subdir=None` (`sources/registry.py:205-264`); sygnaly:
  `none`, `metadata`, `none`.
- Maszyneria planow 1/3 i 2/3: `fetch_version`/`inspect_version`
  (`download/fetch.py:184-310`) traktuja `metadata` jak `index` — lokalna
  wersja zawsze "aktualna", bez porownania z wydaniem zrodla (zaden tor planu
  2/3 nie mial sygnalu `metadata`). `commit_version` z `signal` zawierajacym
  tylko `content_length` daje `relabeled` zamiast `unchanged`
  (`same_http_signal` = `None`, `versions.py:405-420`) — tory `none` musza
  przekazywac `signal=None`.
- Segmenty ADR-026: wartosci lowercase (`docs/ARCHITECTURE.md` 3.3, regula 1);
  przyklad specu 3.4 `pl_bdot10k_gpkg_PTWP-SWRS` ja lamie.

## 4. Wplyw na spec

Rozstrzygniecia (D29-D33) i poprawki sekcji 3.3, 3.4, 4.1, 4.3, 4.5, 5 i 8
zapisane w specu w rewizji 2026-10-12 (plan 3/3).
