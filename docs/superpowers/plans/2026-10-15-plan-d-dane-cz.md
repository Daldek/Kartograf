# Plan D - dane CZ (ZABAGED, RUIAN, HY-NET, ortofoto) i wycinek ortofotomapy PL w magazynie - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-15

**Wersja docelowa:** 0.8.0 (razem z manifestem i planami A, B, C, E).

**Goal:** Na silnikach planu C: ZABAGED jako zrodlo `landcover`
(obszar -> GPKG, caly kraj -> plik krajowy z feedu ATOM), granice RUIAN
w `boundaries --country cz`, siec HY-NET w nowej grupie `hydro`,
ortofoto CZ w `imagery --country cz` (arkusze SM5, JPEG + JGW bez
konwersji) oraz wycinek ortofotomapy PL z WCS w magazynie wersji
(`imagery download --product orto --cutout`, Standard/High). Nowy silnik
`atom_files` (feed ATOM CUZK -> plik) i poprawka wzorca godla SM5.

**Architecture:** Plan C dostarcza `AccessChannel.params`,
`transport/unit_package.py`, `transport/feature_bbox.py`,
`transform/gpkg.py`, `download/collections.py`
(`download_collection`/`check_collection`/`validate_collection_request`),
`FileSlot.related_roots`, `download/storage.py::unit_slot/content_segment`
i ADR-042 (decyzje D12-D17 dotycza tego planu). Plan D dodaje:
`AtomFilesParams` + `kartograf/transport/atom.py` (indeks feedu uslugi
w `MetadataCache`), `WcsCutoutParams` (kanaly WCS wycinka orto),
deskryptory `cz.cuzk.zabaged`, `cz.cuzk.ruian`, `cz.cuzk.hy_net`,
`cz.cuzk.ortofoto` i kanaly WCS `pl.gugik.orto`;
zrodla `landcover` oparte na kolekcji (`LandCoverManager` deleguje do
`download/collections.py`); tor arkuszy ortofoto CZ
`kartograf/download/cz_orto.py` (w `download_data`, tor planu
`cz_orto`); wycinek orto PL w `kartograf/download/orto_cutout.py` (tor
`pl_cutout`); grupe CLI `cli/groups/hydro.py`.

**Spec:** `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`
(K5-K8, sekcje 5, 6 plan D, 7, 8, 9.4, 9.7); rekonesans
`docs/research/2026-10-15-plan-c-d/raport.md` (liczby, URL-e, pulapki:
czytaj przed kazdym Taskiem); `docs/research/2026-08-10-czechy-dmr-zabaged.md`
(ZABAGED, 5); plan C (`2026-10-15-plan-c-silniki-i-dane-pl.md`: kontrakt,
ADR-042); manifest (spec sekcja 5).

**Galaz:** `feat/plan-d` z `develop` PO wdrozeniu planu C (twarda
zaleznosc: silniki i API kolekcji). Kod planu A (ADR-041,
`kartograf/sources/variants.py`) jest wdrazany wczesniej (kolejnosc
A-B-C-D, spec 9.1): etykiety `--resolution` wycinka orto ida przez
`resolution_label`/`parse_resolution` (Task 5). Integracja - koordynator.

---

## Global Constraints

Jak w planie C (sekcja "Global Constraints" - obowiazuja bez zmian:
`.venv`, brama, straznik wzorcow przy commicie, Conventional Commits po
polsku bez `Co-Authored-By`, ASCII w tekstach dla uzytkownika,
`ValidationError`/`DownloadError`/`NoCoverageError`, CLI tylko tlumaczy,
zero domyslnych wartosci zmieniajacych dane, magazyn przez `FileSlot`
i `store_file`, testy offline z przycietych prawdziwych odpowiedzi, dane
live tylko w `<katalog-danych>`, CRLF w `docs/DECISIONS.md`). Dodatkowo:

- Pliki krajowe CUZK (ZABAGED 5,8/6,7 GB, HY-NET 194 MB, RUIAN 253 MB)
  pobierane wylacznie po jawnym `--whole-country`; testy offline nigdy
  nie symuluja ich pelnej tresci (male ZIP-y z prawdziwymi nazwami
  czlonow).
- Feed uslugi ATOM ortofoto ma 23,7 MB - nigdy nie wchodzi do
  `tests/fixtures` w calosci (przyciety do kilku wpisow z prawdziwymi
  id, `updated`, linkami i kategoriami).

## Zweryfikowane punkty zaczepienia (develop `bcdf37d` + plan C)

| Symbol | Miejsce | Fakt istotny dla planu |
|---|---|---|
| `CZ_SM5_PATTERN`, system `cz_sm5`, `detect_system` | `kartograf/core/parser_registry.py:24, 70-74` | `^[A-Z]{4}[0-9]{2}$`, `path_parts=[sheet[:4], sheet[4:]]` - 99 godel `AS..` (2 litery; indeks SM5 ma 16 299 arkuszy) nierozpoznanych: `detect_system("AS91")` = `pl1992` (fallback). |
| `SheetIndex`, `SheetInfo`, `KLADY_ENDPOINT`, `SM5_LAYER=24` | `kartograf/providers/cuzk/sheets.py:46-176` | `sm5_sheet(mapnom)`, `sm5_sheets_for_bbox(bbox)`; `SheetInfo(sheet, name, bbox 5514, podil, in_cz)`; cache `sheet_cache` (TTL 30 dni). |
| `CuzkClient.query`, `fetch_file` | `kartograf/providers/cuzk/client.py:65-158` | `query` zbiera wszystkie strony w liste (nie do duzych wynikow - kolekcje uzywaja `feature_bbox`). |
| `download_cz_sheet`, `check_cz_sheet`, `CzSheetResult` | `kartograf/download/cz_sheets.py:58-298` | Wzorzec arkusza CZ w magazynie (sygnal `http`, `mapname`, `cz_share`). |
| `download_data`, `check_data`, `_execute`, `_dispatch_area`, `_download_cz` | `kartograf/download/data.py:245-436, 449, 1170` | Routing produktow; `--country auto` dzieli obszar `split_bbox_by_country`. |
| `validate_request`, `CUTOUT_CRS` | `kartograf/download/options.py:299-397` | `--cutout` z `orto` odrzucany (l. 382-386); `--horizontal-crs` tylko z `--cutout`. |
| `GugikOrtoProvider`, `WCS_ENDPOINT`, `COVERAGE_ID`, `download_bbox`, `DEFAULT_TIMEOUT=60` | `kartograf/providers/pl/gugik_orto.py:43-226` | Tylko StandardResolution, siatka natywna 0,1 m (bez `SCALEFACTOR`). |
| `GugikWcsMixin`, `WCS_GRID`, `WCS_NATIVE_STEP`, `WCS_CHUNK_LIMITS`, `_construct_wcs_url`, `plan_wcs_chunks`, `_download_wcs` | `kartograf/providers/pl/wcs.py:45-333` | WCS 2.0.1 `SUBSET` + opcjonalny `SCALEFACTOR`; kawalki ze zszyciem 1:1; `reject_error_document`. |
| `bbox_slot`, `_pl_cutout_slot`, `_check_prepared` | `kartograf/download/storage.py:688`, `kartograf/download/cutout.py:358-380` | Wycinek PL: `bbox/<coords>`, tor `pl_cutout`, sygnal `channel_signal(key, WCS)` (dla `pl.gugik.orto` dzis brak kanalu WCS -> `ValidationError`). |
| `pl.gugik.orto`, `_COUNTRIES["CZ"]` | `kartograf/sources/registry.py:166-183, 368-376` | Orto ma tylko kanal `WMS_SHEET_INDEX`; `dataset_keys` CZ zaszyte (`cz.cuzk.dmr4g`, `cz.cuzk.dmr5g`). |
| `MetadataCache` (`get_sheet`/`set_sheet`, TTL) | `kartograf/cache/metadata.py:52-56, 626-679` | Typowane tabele cache; nowa tabela feedow ATOM wg tego wzorca. |
| `imagery` (`PRODUCTS=("orto",)`, `--country pl|auto`) | `kartograf/cli/groups/imagery.py:20, 57-66` | ADR-039 D3: `cz` dochodzi w planie D. |
| `PROVIDERS`, `_SOURCE_OPTIONS`, `_kind`, `_check_options` | `kartograf/landcover/manager.py:85-100, 602-668` | Menedzer oparty na klasach providerow - zrodla kolekcji dochodza jako osobna galaz. |

## Matryca produktow planu D

| Wybor CLI | API | Deskryptor, kanal | Plik pod `--output` | Sygnal / etykieta |
|---|---|---|---|---|
| `landcover download --source zabaged --bbox -460000,-1120000,-450000,-1110000 --bbox-crs EPSG:5514` | `LandCoverManager(o, "zabaged").download(bbox=BBox(..., "EPSG:5514"))` | `cz.cuzk.zabaged` (`product="landcover"`, CZ), `ARCGIS_QUERY` `.../ZABAGED_POLOHOPIS/MapServer`: 22 warstwy (tabela nizej), `xy`, EPSG:5514, strona 2000, `order_field="OBJECTID"`, id `fid_zbg`, `selection="all"` | `landcover/cz_zabaged/bbox/<coords 5514>.gpkg` | `none` / pobranie |
| `landcover download --source zabaged --whole-country --horizontal-crs EPSG:5514` | `... .download(whole_country=True, horizontal_crs="EPSG:5514")` | `cz.cuzk.zabaged`, `DIRECT_FILES` + `AtomFilesParams` (feed `https://atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml`, jedyny zbior, kategorie CRS 5514/3045) | `landcover/cz_zabaged_gpkg_5514/country/cz.zip` | `metadata` / `updated` (np. `2026-10-04`) |
| `boundaries download --product admin --country cz --level obec --bbox ...` | `download_collection(product="admin", country="cz", level="obec", bbox=...)` | `cz.cuzk.ruian` (`product="admin"`), `ARCGIS_QUERY` `.../RUIAN/MapServer`: `kraj`=17, `okres`=15, `obec`=12, `katastralni-uzemi`=7, `xy`, strona 1000, `order_field="objectid"`, id `kod` | `boundaries/cz_ruian_obec/bbox/<coords 5514>.gpkg` | `none` / pobranie |
| `boundaries download --product admin --country cz --whole-country` | `download_collection(product="admin", country="cz", whole_country=True)` | `cz.cuzk.ruian`, `DIRECT_FILES` `unit_package` country: `https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip`, `members` `.shp` | `boundaries/cz_ruian_shp/country/cz.zip` | `http` / pobranie |
| `boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox ...` | `download_collection(product="admin", country="auto", level={"pl": "gmina", "cz": "obec"}, bbox=...)` | PRG + RUIAN (obszar dzielony `split_bbox_by_country`) | dwa pliki (PL i CZ) | jw. |
| `hydro download --product network --country cz --bbox ...` | `download_collection(product="network", country="cz", bbox=...)` | `cz.cuzk.hy_net` (`product="network"`), `WFS` `https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs`: `hy-n:WatercourseLink`, `hy-n:HydroNode`, `hy-n:WatercourseSeparatedCrossing`, `xy`, EPSG:5514, strona 1000, id `gml_id`, `selection="all"` | `hydro/cz_hynet/bbox/<coords 5514>.gpkg` | `none` / pobranie |
| `hydro download --product network --country cz --whole-country` | `download_collection(product="network", country="cz", whole_country=True)` | `cz.cuzk.hy_net`, `DIRECT_FILES` `unit_package` country: `https://openzu.cuzk.gov.cz/opendata/HY-NET/HY-NET.zip` (jeden uklad EPSG:3045), `members` `.gpkg` | `hydro/cz_hynet_gpkg/country/cz.zip` | `http` / pobranie |
| `imagery download --product orto --country cz --sheet CTES96` | `download_data(product="orto", country="cz", sheet="CTES96", output_dir=o)` | `cz.cuzk.ortofoto` (`product="orto"`, CZ), `DIRECT_FILES` + `AtomFilesParams` (feed `https://atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml`, wpis po godle SM5) | `orto/cz_sjtsk/CTES/96/CTES96.jpg` + `CTES96.jgw`, `CTES96.TM33N.jgw`, `CTES96.TM34N.jgw` | `metadata` / `<rok>_<updated>` (np. `2024_2025-02-06`) |
| `imagery download --product orto --country cz --bbox ... --bbox-crs EPSG:5514` | `download_data(product="orto", country="cz", bbox=...)` | jw.; arkusze z `SheetIndex.sm5_sheets_for_bbox` | jw. per arkusz | jw. |
| `imagery download --product orto --country pl --bbox 566000,243000,566500,243500 --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m` | `download_data(product="orto", country="pl", bbox=..., cutout=True, horizontal_crs="EPSG:2180", coverage="standard", resolution="0.25m")` | `pl.gugik.orto`, nowe kanaly `WCS` (`StandardResolution`/`Orthoimagery_StandardResolution`, `HighResolution`/`Orthoimagery_High_Resolution`), `none` | `orto/pl_1992_standard_0.25m/bbox/<coords>.tif` | `none` / pobranie |

**22 warstwy ZABAGED (`landcover --source zabaged`, kody = nazwy
warstw GPKG; zrodlo: `ZABAGED_POLOHOPIS/MapServer?f=pjson` 2026-10-15):**
93 `vodni_tok` (linie), 99 `budova_jednotliva_nebo_blok_budov_plocha`,
112 `brehova_cara` (linie), 114 `areal_ucelove_zastavby`,
115 `ostatni_plocha_v_sidlech`, 116 `hrbitov`, 117 `skladka`,
118 `povrchova_tezba_lom`, 129 `sesuv_pudy_sut`, 130 `skalni_utvary`,
131 `bazina_mocal`, 132 `vodni_plocha`, 134 `udrzovana_zelen`,
135 `ovocny_sad_zahrada`, 136 `vinice`, 137 `chmelnice`,
138 `orna_puda_a_ostatni_dale_nespecifikovane_plochy`,
139 `trvaly_travni_porost`, 140 `lesni_puda_s_krovinatym_porostem`,
141 `lesni_puda_s_kosodrevinou`, 142 `lesni_puda_se_stromy`,
144 `lesni_puda_se_stromy_kategorizovana_plocha` (pozostale - poligony).
Kod = nazwa warstwy REST bez diakrytykow, male litery, ciagi znakow
spoza `[a-z0-9]` zastapione `_`; nazwa zrodla z identyfikatorem warstwy
w `gpkg_contents.description` (opcja warstwy GDAL `DESCRIPTION`). Zestaw
odpowiada tabeli research 2026-08-10 sekcja 5.1 (odpowiedniki PT*
BDOT10k + cieki, linia brzegowa, budynki) bez dzialu wodnego (113)
i bez drog/kolei (linie); **Kartograf nie przelicza klas ZABAGED na kody
BDOT10k** (ADR-042 D15; tabela 5.1 ma bledne odpowiedniki - pytanie do
uzytkownika w raporcie rekonesansu).

Uwagi: (1) RUIAN `teryt` nie dotyczy (CZ) - `ValidationError`; obszar
z `--country cz` w EPSG:5514 (inne `--bbox-crs` przeliczane jak
w `country_bbox`). (2) Plik krajowy ZABAGED: dwa uklady (5514, 3045)
-> `--horizontal-crs` wymagany; HY-NET kraj: jeden uklad (EPSG:3045 wg
kategorii feedu) - flaga niepotrzebna, inna wartosc = blad; wynik
obszaru zawsze w EPSG:5514 (DefaultCRS uslug). (3) Ortofoto CZ: tylko
aktualny rocznik arkusza (archiwalne orto CUZK sa platne - poza
zakresem), wiec `--year`/`--min-year`/`--max-year`/`--all-campaigns`/
`--full-sheet`/`--sheet-system`/`--scale` z `--country cz` = blad;
z `--country auto` dzialaja tylko dla czesci PL (jak dzis w
`elevation`: `_reject_campaign_opts_without_pl`); TM33 jako `--sheet`
= blad z podpowiedzia SM5. (4) Wycinek orto: tylko
EPSG:2180 (bez przeprobkowania obrazu w 0.8.0), bez maski ladu PRG,
`--coverage` i `--resolution` wymagane; `--cutout` z `--country cz`
albo z `--sheet` = blad.

---

### Task 1: Wzorzec godla SM5 i rejestr krajow CZ

**Files:**
- Modify: `kartograf/core/parser_registry.py`, `kartograf/sources/registry.py`
- Test: `tests/test_parser_registry.py` (albo istniejacy plik testow
  `parser_registry`; `grep -rln CZ_SM5_PATTERN tests`), `tests/test_sources_registry.py`

- [ ] **Step 1: Testy (RED)** - `test_sm5_two_letter_codes`
  (`detect_system("AS91").id == "cz_sm5"` - dzis `pl1992` przez fallback,
  wiec arkusz DMR/orto `AS91` konczy sie bledem godla PL;
  `path_parts("AS91") == ["AS", "91"]`; `CTES96` -> `["CTES", "96"]` bez
  zmian; `A91`, `ABCDE91`, `CTES9` nie sa SM5).
- [ ] **Step 2: Implementacja** - `CZ_SM5_PATTERN =
  re.compile(r"^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$")`, `path_parts=lambda
  sheet: [sheet[:-2], sheet[-2:]]`; docstring z liczba 99 godel `AS`;
  `dataset_keys` CZ liczone z `_SOURCES`.
- [ ] **Step 3: Brama i commit** - `fix(core): godla SM5 z dwiema
  literami (As) i lista zrodel CZ z rejestru`

### Task 2: Silnik `atom_files`

**Files:**
- Modify: `kartograf/sources/descriptor.py` (`AtomFilesParams`, unia
  `params`), `kartograf/cache/metadata.py` (tabela `atom_cache`)
- Create: `kartograf/transport/atom.py`, `tests/test_atom.py`,
  `tests/fixtures/cz/atom/` (przyciete prawdziwe feedy: uslugi ORTOFOTO
  z wpisami `WRTO24.2024.CTES96`, `WRTO24.2025.AS91`, `WRTO24.2025.BENE09`;
  zbioru `CZ-00025712-CUZK_ORTOFOTO_WRTO24.2024.CTES96.xml`; ZABAGED-GPKG
  uslugi i zbioru (2 wpisy 5514/3045); naglowki `ETag`/`Last-Modified`)

```python
@dataclass(frozen=True)
class AtomFilesParams:
    service_feed: str                 # ATOM service feed URL
    entry_pattern: str                # regex on the dataset feed id; named groups
                                      # (?P<sheet>...) / (?P<year>...) when present
    crs: tuple[str, ...] = ()         # EPSG codes of feed CRS categories
                                      # ("EPSG:5514", "EPSG:3045"); () = one file
    members: tuple[tuple[str, str], ...] = ()  # (ZIP member suffix, stored suffix);
                                      # () = keep the ZIP; longest suffix matches first
    segment_tokens: tuple[str, ...] = ()  # ("gpkg",); EPSG number appended if len(crs) > 1
```

- [ ] **Step 1: Testy (RED)** - `test_index_maps_sheet_to_dataset_feed`
  (wpisy z `entry_pattern` `...ORTOFOTO_WRTO24\.(?P<year>\d{4})\.(?P<sheet>[A-Z]{2,4}\d{2})\.xml$`:
  `CTES96` -> rok 2024, `AS91` -> 2025, `updated` z wpisu);
  `test_dataset_feed_link_and_length` (link `rel="alternate"`,
  `length` -> rozmiar; brak linku albo kilka bez rozstrzygniecia =
  `DownloadError`); `test_crs_category_selects_file` (ZABAGED: 5514 vs
  3045; brak kategorii = `ValidationError` z lista);
  `test_edition_label` (`2024_2025-02-06` dla orto, `2026-10-04` dla
  ZABAGED, tylko `[A-Za-z0-9._+-]`); `test_index_cached_and_revalidated`
  (drugie wywolanie bez sieci w TTL; z `refresh=True` warunkowy GET:
  304 = indeks bez zmian, 200 = nowy indeks; sesja-atrapa liczy
  `If-None-Match`); `test_unknown_sheet_is_no_coverage`;
  `test_html_feed_is_download_error`.
- [ ] **Step 2: Implementacja** - `kartograf/transport/atom.py`:
  `AtomEntry(key: str, dataset_feed: str, updated: str, groups:
  Mapping[str, str], crs: tuple[str, ...])` (wszystkie kategorie ukladu
  wpisu; ZABAGED ma dwie), `AtomFile(url, length, updated, edition: str,
  crs: str | None, dataset_feed)`;
  `atom_index(session, params, *, cache, refresh) -> dict[str,
  AtomEntry]` (strumieniowy `xml.etree.ElementTree.iterparse` po
  `{http://www.w3.org/2005/Atom}entry`, czyszczenie elementow -
  23,7 MB bez trzymania drzewa; zapis wpisow do `atom_cache` z ETag
  feedu); `resolve_atom_file(session, params, *, key, crs, cache,
  refresh) -> AtomFile` (feed zbioru pobierany zawsze swiezo - maly;
  klucz brakujacy w indeksie z cache albo 404 feedu zbioru = jedno
  odswiezenie indeksu, zeby nieaktualny cache nie ukryl nowego
  rocznika); `check_atom_crs` (wybor ukladu bez sieci),
  `atom_segment_tokens`, `fetch_atom_file` (rozmiar = `length` feedu
  i `Content-Length`), `unpack_members` (najdluzszy sufiks najpierw).
  Timeout feedu uslugi 120 s (rekonesans: 3,2 s, ale GUGiK ATOM mial
  timeouty 120 s - STANDARDS 13.4), ponowienia `get_with_retry`.
  Dlaczego feed, skoro plan B dla DMR go nie uzywa (szablon `openzu`
  + `HEAD`): nazwa pliku ortofoto i ZABAGED kraj zawiera rok/date
  wydania (`WRTO24.<rok>.<godlo>`, `ZABAGED-5514-gpkg-<data>`), wiec
  URL istnieje tylko w feedzie - szablon zgadywalby rok.
  `MetadataCache`: `get_atom_entries(feed) -> (etag, entries, fresh)` /
  `set_atom_entries(feed, etag, entries)` (klucz: feed + wzorzec; TTL
  domyslny 7 dni; starszy indeks zwracany z `fresh=False` do
  warunkowego GET, tryb `refresh` cache = brak odczytu).
- [ ] **Step 3: Brama i commit** - `feat(transport): silnik atom_files
  (feed ATOM CUZK -> plik, wydanie z updated)`

### Task 3: ZABAGED, RUIAN i HY-NET na silnikach kolekcji

**Files:**
- Modify: `kartograf/sources/registry.py` (deskryptory
  `cz.cuzk.zabaged`, `cz.cuzk.ruian`, `cz.cuzk.hy_net`, licencja
  `_CUZK_LICENSE`), `kartograf/landcover/manager.py` (zrodla kolekcji),
  `kartograf/download/collections.py` (kanal `atom_files` dla
  `whole_country`; `level` per kraj), `tests/test_sources_registry.py`
  (`CHANNEL_SIGNALS`)
- Create: `tests/test_collections_cz.py`, `tests/fixtures/cz/feature_bbox/`
  (nagraj raz i przytnij: ZABAGED `?f=pjson` (lista warstw),
  `/93?f=json` i `/132?f=json` (pola), `returnCountOnly` i dwie strony
  `resultRecordCount=2` z `exceededTransferLimit`; RUIAN `/12/query`
  count + strona; HY-NET `GetCapabilities` (fragment 3 typow),
  `DescribeFeatureType` WatercourseLink, `hits` + 2 strony `COUNT=2`
  (ostatnia z mylacym `next`))

- [ ] **Step 1: Testy (RED)** - `test_zabaged_layers_config_matches_service`
  (22 pary id -> kod z fixtury `?f=pjson`, typy geometrii zgodne);
  `test_zabaged_bbox_gpkg` (GPKG EPSG:5514, warstwy o kodach z tabeli,
  pusta warstwa = schemat bez obiektow, `description` z nazwa zrodla,
  liczby = `returnCountOnly`); `test_zabaged_whole_country_requires_crs`
  (bez `horizontal_crs` - `ValidationError` z `EPSG:5514, EPSG:3045`;
  z 5514: `WHOLE_COUNTRY_SIZE` z `length` feedu przed `GET`, plik
  `landcover/cz_zabaged_gpkg_5514/country/cz.zip`, etykieta `2026-10-04`);
  `test_zabaged_teryt_rejected`; `test_ruian_levels` (`obec` -> warstwa
  12, klucz `kod`, sort po `kod`); `test_ruian_whole_country_http_signal`
  (drugi `--check-updates` z tym samym `ETag` = `current`, innym =
  `newer`); `test_hynet_three_layers_and_misleading_next` (komplet z
  `hits`, `next` ostatniej strony ignorowany, schemat `http` w `next`
  nie jest sledzony); `test_hynet_whole_country_crs_3045`
  (`horizontal_crs="EPSG:5514"` -> blad; sidecar `horizontal_crs`
  EPSG:3045); `test_auto_level_per_country` (`country="auto"`, bbox na
  granicy: `level` str -> blad z podpowiedzia `pl=...,cz=...`; mapa ->
  dwa pliki PL i CZ, `AUTO_CLIPPED` jak w `download_data`).
- [ ] **Step 2: Implementacja** - deskryptory z matrycy (dane);
  `LandCoverManager`: `COLLECTION_SOURCES = {"zabaged":
  "cz.cuzk.zabaged"}` w `landcover/manager.py`; konstruktor przyjmuje
  te nazwe (bez klasy providera), `_kind`/`_check_options` dla zrodla
  kolekcji (opcje: `whole_country`, `horizontal_crs`; `teryt`,
  `format`, `layers`, `keep_raw`, `year` - bledy z nazwa zrodla; reguly
  bez sieci, wiec obejmuje je tez `LandCoverManager.validate_request`
  manifestu),
  `download`/`check` deleguja do funkcji plikow z
  `download/collections.py` (ten sam kod co `download_collection`,
  wynik jako `LandCoverAreaResult`, tor planu `landcover`). W
  `download/collections.py`: `whole_country` przez `atom_files`
  (gdy kanal ma `AtomFilesParams`) albo `unit_package` country;
  `level: str | Mapping[str, str]` jak `PerCountry` w `download/options.py`
  (`check_per_country`, `country_value`).
- [ ] **Step 3: Brama i commit** - `feat(download): ZABAGED, RUIAN
  i HY-NET (feature_bbox, pliki krajowe, atom_files)`

### Task 4: Ortofoto CZ w `imagery`

**Files:**
- Modify: `kartograf/sources/registry.py` (`cz.cuzk.ortofoto`),
  `kartograf/download/data.py` (routing `orto` + CZ),
  `kartograf/download/options.py` (reguly orto CZ),
  `kartograf/download/plan.py` (`Track` += `"cz_orto"`)
- Create: `kartograf/download/cz_orto.py`, `tests/test_cz_orto.py`,
  `tests/fixtures/cz/ortofoto/` (maly ZIP z prawdziwymi nazwami
  czlonow `WRTO24.2024.CTES96.jpg/.jgw/.TM33N.jgw/.TM34N.jgw`: JPEG
  przyciety do kilku pikseli zapisany przez `rasterio`, JGW prawdziwe
  z probki)

- [ ] **Step 1: Testy (RED)** - `test_cz_orto_sheet_files_and_sidecars`
  (cztery pliki w `orto/cz_sjtsk/CTES/96/` przemianowane na `CTES96.*`,
  bajty JPEG = bajty czlonu ZIP (bez konwersji), sidecar JPEG:
  `horizontal_crs` EPSG:5514, `extra.world_files` = `{".jgw":
  "EPSG:5514", ".TM33N.jgw": "EPSG:3045", ".TM34N.jgw": "EPSG:3046"}`,
  `extra.source` z URL, `updated`, rokiem, `mapname`, `cz_share`);
  `test_cz_orto_world_files_committed_before_jpeg` (blad zapisu JPEG
  -> arkusz w `failed`, kolejne uruchomienie naprawia);
  `test_cz_orto_metadata_signal` (`check_data` bez pobrania: ten sam
  `updated` = `current`, nowy rok w feedzie = `newer`; `--upgrade`
  pobiera, stara wersja zostaje w `versions/`);
  `test_cz_orto_area_uses_sm5_index` (bbox -> arkusze z indeksu,
  `SHEET_LIST`); `test_cz_orto_pl_only_flags_rejected` (rok, kampanie,
  `--full-sheet`, `--sheet-system`, `--scale`, `--cutout` z `cz`;
  TM33 jako arkusz); `test_auto_orto_both_countries` (bbox na granicy
  -> arkusze PL i CZ, zamiast dzisiejszego `AUTO_NARROWED_TO_PL`);
  `test_two_letter_sm5_sheet` (`AS91`).
- [ ] **Step 2: Implementacja** - `cz_orto.py`: `download_cz_orto_sheet(
  sheet, *, output_dir, cache, update, plan, on_notice) ->
  CzOrtoResult(files: tuple[VersionedFile, ...], stale, notices)`,
  `check_cz_orto_sheet(...) -> UpdatePlan`; sloty czlonow:
  `FileStorage(output_dir, resolution=None, vertical_crs=None, subdir="orto/cz_sjtsk")` z
  `get_raw_path(sheet, f"{sheet}{suffix}")` / `get_raw_versions_root(sheet)`
  jak arkusze CZ w `download/cz_sheets.py` (hierarchia `path_parts`,
  Task 1), wspolna `EditionLookup` arkusza (jedno `resolve_atom_file`
  na arkusz); lokalne wszystkie czlony = `local` bez pobrania; inaczej
  jeden ZIP do stagingu, czlony rozpakowane i `store_file` w kolejnosci
  `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`, `.jpg`. `download_data`: produkt
  `orto` z krajem `cz` (arkusz SM5, obszar przez indeks, `auto` dzieli
  obszar) - `UnitFile` dla kazdego z czterech plikow arkusza (unit =
  godlo, country `cz`).
- [ ] **Step 3: Brama i commit** - `feat(download): ortofoto CZ z ATOM
  (arkusze SM5, JPEG + JGW bez konwersji)`

### Task 5: Wycinek ortofotomapy PL z WCS w magazynie

**Files:**
- Modify: `kartograf/sources/descriptor.py` (`WcsCutoutParams`, unia
  `params`), `kartograf/sources/registry.py` (`pl.gugik.orto`: kanaly
  `WCS` Standard i High z `endpoint`, `update_signal="none"`,
  `capabilities={"bbox_raster"}`, `params=WcsCutoutParams(...)`),
  `kartograf/providers/pl/gugik_orto.py` (`coverage=`, `resolution=`,
  limity kawalkow, timeout), `kartograf/providers/pl/wcs.py` (budzet
  kawalka GeoTIFF liczony w pikselach coverage jak ASC; NMT bez zmian),
  `kartograf/download/options.py` (reguly wycinka orto),
  `kartograf/download/area.py` (`pl_only_flags`: `coverage` i piksel
  wycinka orto), `kartograf/download/data.py` (routing); `notices.py`
  bez zmian (istniejace `CUTOUT_SIZE`, `ALL_NODATA`)
- Create: `kartograf/download/orto_cutout.py`, `tests/test_orto_cutout.py`,
  `tests/fixtures/pl/orto_wcs/` (KOREKTA po nagraniu 2026-10-16:
  `DescribeCoverage` obu coverage; GeoTIFF 4 x 4 px 0,25 m i jego
  cwiartki 2 x 2 px; High 4 x 4 px 0,1 m i High bez danych 0,0,0;
  odpowiedz na 3 x 3 px 0,25 m = zla siatka serwera, bo 7,5 piksela
  coverage; `ExceptionReport` `ExtentError` HTTP 400)

```python
@dataclass(frozen=True)
class WcsCutoutParams:
    """WCS channel offered as a cutout in the store (ADR-042 D14)."""
    variant: str                       # "standard" | "high" (--coverage)
    coverage_id: str                   # "Orthoimagery_StandardResolution"
    native_step: Decimal               # Decimal("0.1") (DescribeCoverage)
    resolutions: tuple[Decimal, ...]   # 0.1, 0.25, 0.5, 1 -> labels K2
    max_native_pixels: int             # 4_000_000 per GetCoverage request
```

Etykiety `--resolution` z `kartograf/sources/variants.py::resolution_label/
parse_resolution` (plan A, jedna funkcja etykiet K2); `ProductVariant`
planu A (model wysokosci: `vertical_crs`, skorowidz) NIE jest
rozszerzany o orto.

- [ ] **Step 1: Testy (RED)** - `test_orto_cutout_requires_variant`
  (bez `coverage`/`resolution`/`horizontal_crs` - `ValidationError`
  z listami; `EPSG:5514` - blad "tylko EPSG:2180"; `--sheet`, `cz`,
  `vertical_crs` - blad); `test_orto_cutout_slot_and_sidecar`
  (`orto/pl_1992_standard_0.25m/bbox/<coords>.tif`, `request` z
  `coverage` i `resolution`, `extra.source` z endpointem, coverage id
  i `SCALEFACTOR`); `test_orto_cutout_grid_and_chunks` (siatka
  wyrownana do wielokrotnosci rozdzielczosci; kawalek <= 4 Mpx
  natywnych 0,1 m, czyli 200 x 200 m; kawalki kopiowane 1:1 - KOREKTA:
  wynik z kawalkow NIE jest bit w bit z jednym zapytaniem, serwer
  przeprobkowuje kazde zapytanie we wlasnym zasiegu; 3 pasma uint8,
  EPSG:2180); `test_orto_cutout_exception_report_is_download_error`
  (bez wersji; takze GeoTIFF na innej siatce niz zapytanie);
  `test_orto_cutout_local_reuse_and_force_unchanged`;
  `test_check_orto_cutout_unverifiable` (tor `pl_cutout`, bez pobrania);
  `test_orto_cutout_all_black_is_kept_with_warning` (High poza
  obszarami 10 cm: HTTP 200 z 0,0,0 -> wersja, `extra.all_nodata`,
  `ALL_NODATA`);
  istniejace testy `GugikOrtoProvider.download_bbox` (plik poza
  magazynem - API surowe, D27 dla niego bez zmian) przechodza bez zmian.
- [ ] **Step 2: Implementacja** - `GugikOrtoProvider(..., coverage:
  Literal["standard", "high"] | None = None, resolution: str | None =
  None)` (KOREKTA: siatka wyniku zalezy od piksela) wybiera endpoint
  i coverage id z kanalu deskryptora; `WCS_NATIVE_STEP = 0.1`
  (DescribeCoverage obu uslug), `WCS_GRID` = siatka wyniku z wybranej
  rozdzielczosci, limity kawalka liczone w pikselach natywnych (4 Mpx),
  parzyste kawalki miksera zostaja (0,25 m: nieparzysta liczba pikseli =
  ulamek piksela coverage -> zla siatka albo HTTP 400), timeout odczytu
  kawalka 300 s (pomiar: 4 Mpx = 64 s, 2000 x 2000 px przy
  `SCALEFACTOR=0.4` = 176 s). `orto_cutout.py`:
  `download_orto_cutout(bbox, *, horizontal_crs, output_dir, coverage,
  resolution, update, plan, parent_request, cache, on_notice) ->
  OrtoCutoutResult(file, stale, notices)` i `check_orto_cutout(...)` na
  `bbox_slot` + `fetch_version(signal="none")` (wzorzec
  `download/cutout.py`, bez maski i warpa); `CUTOUT_SIZE` z MiB i liczba
  zapytan WCS; wynik na innej siatce niz zapytanie = `DownloadError`.
  `validate_request`: usun `orto` z odrzucenia `--cutout`, dodaj reguly
  z uwagi (4) matrycy. `download_data(..., coverage: str | None = None)`
  - nowy parametr tylko dla orto.
- [ ] **Step 3: Brama i commit** - `feat(download): wycinek
  ortofotomapy PL z WCS w magazynie (--cutout, standard/high)`

### Task 6: CLI - `hydro`, `imagery` CZ i wycinek, `landcover zabaged`, `boundaries` CZ, `_task`, projekt

**Files:**
- Create: `kartograf/cli/groups/hydro.py`
- Modify: `kartograf/cli/groups/imagery.py` (`--country pl|cz|auto`,
  `--cutout`, `--horizontal-crs`, `--coverage`, `--resolution`;
  opisy flag PL-only), `kartograf/cli/download_cmd.py` (tlumaczenie
  `coverage`), `kartograf/cli/groups/landcover.py` (`--source zabaged`,
  `--whole-country`, `--horizontal-crs`), `kartograf/cli/landcover_cmd.py`,
  `kartograf/cli/groups/boundaries.py` (`--country cz|auto`, poziomy CZ,
  `--level` w skladni per kraj), testy: `tests/test_cli_translation.py`,
  `tests/test_parity.py`, `tests/test_cli.py` (albo plik testow grup)
- Warunkowo (manifest scalony): `kartograf/project/commands.py`,
  `tests/test_project_commands.py`

- [ ] **Step 1: Testy (RED)** - `test_hydro_group_registered`
  (`hydro download|list-sources`, tylko flagi grupy);
  `test_imagery_new_flags_translation` (`--cutout --horizontal-crs
  EPSG:2180 --coverage high --resolution 0.5m` -> argumenty
  `download_data`; `--country cz`); `test_landcover_zabaged_translation`;
  `test_level_per_country_syntax` (`--level pl=gmina,cz=obec` -> mapa);
  parytet (`run_both` + `assert_same_store`): ZABAGED bbox, RUIAN bbox,
  HY-NET kraj (atrapa HEAD/GET), ortofoto CZ arkusz, wycinek orto,
  `--check-updates --plan`/`--upgrade --plan` dla `cz_orto`.
  `_handler` i `_task` kazdej zmienionej komendy korzystaja z jednej
  funkcji tlumaczenia (bez osobnego testu okablowania).
- [ ] **Step 2: Implementacja** - modul `hydro` wg ADR-039
  (`add_group("hydro", help="Hydrografia: siec wod (HY-NET CZ)")`,
  `download` z `--product`, `--country`, obszar, `--whole-country`,
  wspolne flagi wyniku; `list-sources`;
  `set_defaults(_handler=cmd_collection_download, _task=collection_task)`);
  `imagery`: wybory `--coverage`/`--resolution` z rejestru (bez
  literalow), `--horizontal-crs` tylko `EPSG:2180` dla orto (lista
  z biblioteki); `_task` imagery/landcover rozszerzone o nowe
  argumenty (to samo tlumaczenie co `_handler`). `--level pl=..,cz=..`
  parsuje istniejacy `cli/download_cmd.py::_per_country` - przenies go
  do `cli/_args.py` (jedna definicja dla `elevation` i `boundaries`,
  bez kopii).
- [ ] **Step 3: Projekt (ADR-040, warunkowo)** - jesli
  `kartograf/project/commands.py` istnieje: pozycja `hydro download`
  (jak grupy planu C: `download_collection`/`check_collection`/
  `validate_collection_request`/adapter `CollectionReport`), rozszerzone
  `options` dla `imagery download` (`cutout`, `horizontal_crs`,
  `coverage`, `resolution`), `landcover download` (`whole_country`,
  `horizontal_crs`) i `boundaries download` (mapa `level`), test
  zadania projektu z ortofoto CZ (cztery przypiete pliki jednego
  arkusza) i z ZABAGED bbox. Bez manifestu: `_task` ustawione, lista
  pozycji w `docs/PROGRESS.md` dla galezi manifestu.
- [ ] **Step 4: Smoke offline** - `--help` grup `hydro`, `imagery`,
  `landcover`, `boundaries` z korzenia worktree.
- [ ] **Step 5: Brama i commit** - `feat(cli): grupa hydro, ortofoto CZ
  i wycinek orto w imagery, ZABAGED w landcover, RUIAN w boundaries`

### Task 7: Dokumentacja, live E2E i brama koncowa

**Files:**
- Modify: `docs/DECISIONS.md` (ADR-042: weryfikacja D12-D17 z kodem,
  errata przy odstepstwie; ADR-036 status - D27 czesciowo zastapione),
  `docs/ARCHITECTURE.md` (2: `transport/atom.py`, `download/cz_orto.py`,
  `download/orto_cutout.py`; 3.3: segmenty CZ i `orto/pl_1992_<coverage>_<res>`,
  regula 2 - SM5 dwuliterowe; 4.x: `atom_files`, ortofoto CZ, wycinek orto;
  4.4-4.6: CZ i `auto` dla orto i granic), `docs/USAGE.md` (przyklady
  CLI i API z matrycy; ZABAGED: 22 warstwy, brak mapowania na BDOT10k,
  nazwy warstw pliku krajowego inne niz wynik obszaru; ortofoto CZ:
  przypisanie ukladu w GIS (JGW nie niesie ukladu), aktualny rocznik;
  wycinek orto: czasy WCS, `standard` vs `high`; HY-NET kraj w EPSG:3045),
  `docs/SCOPE.md`, `docs/PRD.md`, `README.md`, `docs/CHANGELOG.md`
  `[0.8.0] - Unreleased` (Added; Changed: `imagery --country cz`,
  `--cutout` dla orto; Fixed: godla SM5 `AS..`), `docs/PROGRESS.md`,
  NOWY `docs/research/2026-10-15-plan-d-live/raport.md`.

- [ ] **Step 1: Dokumentacja** wg listy.
- [ ] **Step 2: Live E2E** (`<katalog-danych>`, bez sciezki w repo):
  ```text
  kartograf landcover download --source zabaged --bbox -460000,-1120000,-450000,-1110000 --bbox-crs EPSG:5514 -o <katalog-danych>
  kartograf boundaries download --product admin --country cz --level obec --bbox -470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514 -o <katalog-danych>
  kartograf boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox 18.5,49.6,18.8,49.9 --bbox-crs EPSG:4326 -o <katalog-danych>
  kartograf hydro download --product network --country cz --bbox -470000,-1130000,-440000,-1100000 --bbox-crs EPSG:5514 -o <katalog-danych>
  kartograf hydro download --product network --country cz --whole-country -o <katalog-danych>
  kartograf imagery download --product orto --country cz --sheet CTES96 -o <katalog-danych>
  kartograf imagery download --product orto --country cz --sheet AS91 -o <katalog-danych>
  kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m -o <katalog-danych>
  kartograf imagery download --product orto --country pl --bbox 566000,243000,566200,243200 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m -o <katalog-danych>
  ```
  Oczekiwane (rekonesans): HY-NET kraj 194 208 037 B z `WHOLE_COUNTRY_SIZE`
  przed transferem; RUIAN obce w bboxie = 68; ortofoto CTES96: ZIP
  63 870 664 B, cztery pliki, etykieta `2024_2025-02-06` (o ile feed
  sie nie zmienil); wycinek 0,25 m = 800 x 800 px, 0,1 m = 2000 x 2000 px,
  3 pasma, EPSG:2180 (`gdalinfo`). Powtorka kazdego polecenia = `local`
  bez transferu; `--check-updates` HY-NET = `current` (ten sam `ETag`),
  ortofoto = `current`; `--force` wycinka = `unchanged` albo nowa
  wersja z inna trescia (zrodlo moze sie zmienic). ZABAGED
  `--whole-country` (5,8 GB) tylko swiadomie, osobno, po sprawdzeniu
  miejsca. GPKG sprawdz `ogrinfo -so` (warstwy, liczby = `hits`/
  `returnCountOnly` z dnia, EPSG:5514). Wyniki do raportu live (bez
  sciezki).
- [ ] **Step 3: Brama koncowa** - jak plan C; smoke rzeczywistego CLI
  i API.
- [ ] **Step 4: Commit** - `docs: plan D - dane CZ, ortofoto CZ i wycinek
  orto PL (ARCHITECTURE, USAGE, ADR-042)`

## Kryteria akceptacji

1. Kazdy wiersz matrycy dziala z CLI i z API (parytet na wspolnym
   magazynie), wybory i `--help` z rejestru, bez domyslnych wariantow.
2. Wynik obszaru CZ jest kompletny wzgledem `hits`/`returnCountOnly`,
   w EPSG:5514, z pelnymi geometriami; plik krajowy tylko po
   `--whole-country`, z rozmiarem przed transferem i faktycznym ukladem
   w sidecarze.
3. Ortofoto CZ: JPEG bajtowo rowny czlonowi ZIP, trzy pliki JGW obok,
   sygnal `metadata` wykrywa nowy rocznik bez pobierania danych; godla
   `AS..` dzialaja (takze dla DMR).
4. Wycinek orto PL w magazynie: jawne `coverage`/`resolution`, siatka
   wyrownana, kawalki w limicie, blad uslugi nigdy nie daje pustego
   pliku; surowe `download_bbox` bez zmian.
5. Brak nowej implementacji `unit_package`/`feature_bbox` - wylacznie
   deskryptory, `atom_files` i tory `cz_orto`/wycinka; brama zielona,
   dokumentacja i raport live zgodne z wynikiem.
