# Test na zywo przed wydaniem 0.7.0

Data: 2026-10-08. Galaz `develop`, start na `b34067d`. W trakcie przebiegu
`develop` przesunal sie (inne sesje) do `4ca3600` przez `11f76f7` (potem
amend do `0ce24d7`) i `8c74748`; zmiany dotyczyly tylko `pyproject.toml`
i `docs/` — kod `kartograf/` identyczny z `b34067d`
(`git diff --stat b34067d..4ca3600 -- kartograf/` puste). Dlatego sidecary
maja rozne `kartograf_version` (`0.7.0-dev+b34067d`, `+11f76f7`, `+0ce24d7`,
`+8c74748`, `+4ca3600`) — format `0.7.0-dev+<sha>` poprawny wszedzie, bez
`dirty`.

CLI `.venv/bin/kartograf`, cwd = korzen repo (cache metadanych lokalny),
wszystkie dane jawnym `-o` do `<katalog-danych>` (przebieg
`e2e/2026-10-08-przed-0.7.0/`). CORINE pominiety (brak credentials CLMS).
Rastry sprawdzone `gdalinfo`, LAZ sygnatura `LASF`, GPKG `ogrinfo`.

## Wyniki

| # | Polecenie | Oczekiwane | Faktyczne | Wynik |
|---|-----------|------------|-----------|-------|
| 1a | `download N-34-130-D-d-2-4 -o <katalog-danych>/data` | pobranie, sidecar z nowymi kluczami, hardlink | kod 0, `Downloading ... (resolution: 1m)`, plik w `kampanie/2025-04-26_82710/`, sciezka standardowa = ten sam inode (nlink 2), `extra.link: hardlink`, `link_target` wzgledny; `request.sheet`, `extra.source.{acquisition_date, declared_crs, index_url, pzgik_date, survey_work_id}`, `extra.campaign.{id,date,survey_work_id,source,full_sheet,pzgik_date}`; 2252x2432, 1 m, NoData -9999 | PASS |
| 1b | to samo ponownie | `Skipped` | kod 0, `Skipped N-34-130-D-d-2-4 - already exists at ...` | PASS |
| 2 | `download N-34-130-D-d-2 -o ...` | rozwiniecie do 1:10000 | kod 0, 4 arkusze `-2-1..-2-4`, `Downloaded 3 files ... (1 already existed)` | PASS |
| 3a | `download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 --scale 1:2000 -o ...` | arkusz(e) 1:2000 | kod 0, `7.171.21.23`, `horizontal_crs: EPSG:2178`, `declared_crs: PL-2000:S7`, segment `nmt/pl_2000_1m_evrf2007/`, hardlink do `kampanie/2026-04-05_83997/`, 1600x1000 | PASS |
| 3b | to samo bez `--scale` | brak danych 1:10000 + `Info: ... --scale 1:2000` | kod 1, `∅ 7.171.21`, `Error: GUGiK nie ma danych dla zadnego z 1 arkuszy obszaru`, `Info: Dostepny potomek 7.171.21.13 — uzyj --scale 1:2000`, `Info: Skorowidz ma ten obszar w PL-1992: N-34-139-C-a-1-4 ...` | UWAGA (U2) |
| 3c | `download 7.171.21 -o ...` | `Error:` z podpowiedzia | kod 1, jedno `Error:` z obiema podpowiedziami | PASS |
| 4a | `parse 6` | nowy komunikat o numerze strefy | kod 1, `Error: Nieprawidłowe godło: '6'. To numer strefy PL-2000, a nie godło arkusza. Najgrubsze godło PL-2000 ma format strefa.pas.slup (1:10000), np. 6.179.12.` | PASS |
| 4b | `parse XYZ` | nowy komunikat | kod 1, `Error: Nieprawidłowe godło: 'XYZ'. Oczekiwano godła PL-1992 (np. N-34-130-D-d-2-4) albo PL-2000 (np. 6.179.12).` | PASS |
| 4c | `--version` | `kartograf 0.7.0-dev+<sha>` | `kartograf 0.7.0-dev+0ce24d7` (HEAD w chwili wywolania) | PASS |
| 4d | `parse N-34-130-D-d-2-4`, `parse 6.179.12.20`, `parse 7.171.21` | poprawny opis godla | kod 0; dla PL-2000 skladowe po polsku i zdublowana strefa | UWAGA (U1) |
| 4e | `parse 302_5550`, `parse CTES96` | (dodatkowo) | kod 1, `Oczekiwano godła PL-1992 ... albo PL-2000` — `download` te godla przyjmuje | UWAGA (U1) |
| 5a | `download N-34-130-D-d-2-4 --campaigns all -o ...` | kilka kampanii w `kampanie/` | kod 0, `Downloaded 2 campaign files for 1 sheets to ... (1 already existed)`; kampanie `2022-07-21_76748`, `2024-05-27_81449`, `2025-04-26_82710`; sciezka standardowa zostaje na najnowszej (inode bez zmian); sidecar `request.campaigns: all` | PASS |
| 5b | to samo ponownie | bez pobran | kod 0, `Downloaded 0 campaign files ... (3 already existed)` | PASS |
| 5c | `... --min-year 2026` (newest) | `Error:` z data najnowszej kampanii | kod 1, `Error: Najnowsza kampania N-34-130-D-d-2-4 ma date 2025-04-26 — starsza niz min_year=2026 (--min-year)` | PASS |
| 5d | `... --min-year 2024 --campaigns all` | tylko 2024 i 2025 | kod 0, `Downloaded 0 campaign files ... (2 already existed)` | PASS |
| 5e | `... --min-year 1800` | `Error:` bez sieci | kod 1, `Error: --min-year musi byc liczba calkowita 1900..2100, otrzymano 1800` | PASS |
| 6a | `download --bbox 770000,509000,771000,510000 --target-crs EPSG:2180 -o ...` | jeden GeoTIFF, `extra.sheet_sources[]` | kod 0, `bbox/770000_509000_771000_510000.tif`, EPSG:2180, 1001x1001 (siatka arkuszy 1:1, faza .5), NoData -9999; `sheet_sources[].{sheet,url,layer,acquisition_date,full_sheet}` | PASS |
| 6b | to samo ponownie | skip | kod 0, `Skipped - already exists at ...` | PASS |
| 7 | `download --bbox 770000,509000,770300,509300 --product laz -o ...` | kafle LAZ, sidecar | kod 0, 2 kafle `82707_*` w `laz/pl_1992_evrf2007/`, naglowek `LASF`; `extra.{tile_sheet, year: 2025, nominal_density: 4, url, parent_request}`; brak `Info:` (brak starszych kafli — `select_tiles(...).superseded == ()`) | PASS |
| 8a | `download CTES96 -o ...` | 5 m bez `--resolution` | kod 0, `Downloading CTES96 (CZ, resolution: 5m)...`, `nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif` (+ `.tfw` z paczki CUZK), EPSG:5514, 500x400, 5 m, NoData -9999; `extra.{mapname, cz_share: 0.99}` | PASS |
| 8b | `download CTES96 --resolution 2m -o ...` | `Error:` bez `Downloading` | kod 1, tylko `Error: Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) — pomin --resolution albo podaj 5m; dla 2m uzyj godla TM33 albo --bbox [godlo: CTES96]` | PASS |
| 8c | `download ABCD12 --country cz -o ...` | sam `Error:` | kod 1, tylko `Error: Arkusz SM5 'ABCD12' nie istnieje w indeksie KladyMapovychListu (warstwa 24)` | PASS |
| 8d | `download 302_5550 --country cz -o ...` | 2 m | kod 0, `Downloading 302_5550 (CZ, resolution: 2m)...`, EPSG:3045, 1000x1000, 2 m; `transform.horizontal` = `pinned: ... S-JTSK to ETRS89 (1) ... (1.0 m)`; `extra` puste (`cz_share` tylko dla SM5 — zgodnie z ARCHITECTURE) | PASS |
| 9a | `landcover list-layers --source bdot10k` (cwd = pusty katalog tymczasowy) | lista, nic na dysku | kod 0, 15 warstw, katalog pusty po wywolaniu | PASS |
| 9b | `landcover download --source bdot10k --teryt 1465 -o <katalog-danych>/landcover` | GPKG + sidecar | kod 0, `bdot10k_teryt_1465.gpkg` (warstwy `OT_*`), sidecar `request.teryt: "1465"` | PASS |
| 9c | `landcover download --source soilgrids --bbox 770000,509000,772000,511000 --property clay -o ...` | GeoTIFF + sidecar | kod 0, EPSG:4326, 14x8; nazwa i sidecar bez `property`/`depth`/`stat`; `--property sand` nadpisuje ten sam plik | UWAGA (U3) |
| 9d | `soilgrids hsg --godlo N-34-130-D --stats -o <katalog-danych>/hsg` | raster HSG + sidecar | kod 0, statystyki A/B/C/D, `hsg_N-34-130-D.tif` 123x77 EPSG:4326 NoData 0; sidecar `extra.{derived, source_layers, depth, stat, classes}`; `request` ma tylko bbox (bez godla) | UWAGA (U4) |
| 9e | `soilgrids hsg --geometry nieistniejacy.shp -o <katalog-danych>/hsg-geom` | `Error:`, bez pustego katalogu | kod 1, `Error: File not found: nieistniejacy.shp`, katalog nie powstal | PASS |
| 10a | `cache stats`, `cache path` | statystyki/sciezka | kod 0; `TERYT entries: 0` mimo pobrania BDOT10k | UWAGA (U5) |
| 10b | cwd = katalog tymczasowy z `.kartograf_cache.db` ze smieci; `download N-34-130-D-d-4-1 -o <katalog-danych>/data-cache` | jedno `Warning:`, pobranie | kod 0, jedno `Warning: cache metadanych nieczytelny (...): file is not a database — praca bez cache; uzyj \`kartograf cache clear\` albo usun plik`, potem `Downloading`/`Downloaded`; plik cache nietkniety | PASS |
| 10c | tamze `cache stats`, `cache clear`, `cache stats` | blad, usuniecie, czysto | `stats` kod 1 `Error: cache nieczytelny: ... — uzyj \`kartograf cache clear\``; `clear` kod 0 `Usunieto nieczytelny plik cache: ...`, plik usuniety; `stats` kod 0, zera, `(file not created yet)`; cache w repo nietkniety (md5 bez zmian) | PASS |
| 11a | `download N-34-130-D-d-2-4 --product nmpt -o ...` | arkusz NMPT | kod 0, `nmpt/pl_1992_1m_evrf2007/`, hardlink do `kampanie/2025-04-26_82709/`, 2252x2432 Float32 NoData -9999; `extra.source.data_source: null` | PASS |
| 11b | `download N-34-130-D-d-2-4 --product orto -o ...` | arkusz orto, `extra.source.color` | kod 0, `orto/pl_1992/`, hardlink, 3 pasma Byte RGB, EPSG:2180, 22528x24326, piksel 0,1 m; `extra.source.color: "RGB"`, `resolution_m: 0.1` | UWAGA (U6) |

Podsumowanie: brak FAIL; 6 uwag (U1-U6), zadna nie blokuje 0.7.0
w sensie poprawnosci pobranych danych NMT/NMPT/orto/LAZ/CZ.

## Uwagi (szczegoly)

### U1 — `parse`: wyjscie PL-2000 miesza jezyki i dubluje strefe; godla CZ nieobslugiwane

```
$ kartograf parse 6.179.12.20
Sheet:     6.179.12.20
Scale:     1:2000
Layout:    2000
Components:
  strefa: 6
  pas: 179
  slup: 12
  ark_2k: 20
  Strefa: 6
  Natywny CRS: EPSG:2177
```

- Etykiety naglowka po angielsku (`Sheet`, `Scale`, `Layout`, `Components`),
  skladowe i dopiski po polsku; `strefa: 6` i `Strefa: 6` to ta sama
  informacja dwa razy; `Natywny CRS` wyglada na dopisek, ktory powinien byc
  poza `Components` (np. `Native CRS:` w naglowku).
- Komunikaty `parse` maja polskie znaki (`Nieprawidłowe godło`, `godła`),
  reszta CLI pisze bez diakrytykow (`Brak danych`, `uklad`, `musi byc`);
  podobnie `soilgrids hsg` drukuje `Godło: N-34-130-D`. Kosmetyka.
- `kartograf parse 302_5550` i `parse CTES96` -> `Error: ... Oczekiwano godła
  PL-1992 ... albo PL-2000`, choc `download` przyjmuje oba godla (rejestr
  zna `cz_tm33`/`cz_sm5`). Albo `parse` obsluguje CZ, albo komunikat/
  dokumentacja mowi wprost, ze `parse` jest tylko PL.

### U2 — lista `--bbox` PL-2000 bez `--scale`: podpowiedzi drukowane dwa razy

```
$ kartograf download --bbox 7503200,5775000,7504800,5776000 --bbox-crs EPSG:2178 --system 2000 -o <katalog-danych>/data
Found 1 sheets at 1:10000 for bbox (resolution: 1m)
  Sheets: 7.171.21
[==============================] 1/1 ∅ 7.171.21
(stderr)
No data for 7.171.21: Brak danych NMT 1m dla 7.171.21 (uklad PL-2000, EVRF2007). Dostepny potomek 7.171.21.13 — uzyj --scale 1:2000; Skorowidz ma ten obszar w PL-1992: N-34-139-C-a-1-4 (1:10000) — uzyj tego godla lub --system 1992 --scale 1:10000
Error: GUGiK nie ma danych dla zadnego z 1 arkuszy obszaru
Info: Dostepny potomek 7.171.21.13 — uzyj --scale 1:2000
Info: Skorowidz ma ten obszar w PL-1992: N-34-139-C-a-1-4 (1:10000) — uzyj tego godla lub --system 1992 --scale 1:10000
```

Oczekiwana podpowiedz `Info: ... --scale 1:2000` jest, ale ta sama tresc
pojawia sie w linii `No data for ...` (bez prefiksu `Warning:`/`Info:`)
i ponownie jako dwa `Info:`. Linia `No data for` nie ma prefiksu
z konwencji (`Info:`/`Warning:`/`Error:`). Drobna niescislosc: podpowiedz
wymienia jednego potomka (`7.171.21.13`, rekord z punktu GetFeatureInfo),
choc obszar zawiera tez `7.171.21.23` (pobrany w 3a) — liczba pojedyncza
moze sugerowac, ze to jedyny potomek.

### U3 — SoilGrids przez `landcover download`: nazwa pliku i sidecar bez parametru, nadpisanie

```
$ kartograf landcover download --source soilgrids --bbox 770000,509000,772000,511000 --property clay -o <katalog-danych>/landcover
Downloaded to: <katalog-danych>/landcover/soilgrids_bbox_770000_509000_772000_511000.tif
md5 f045a465...
$ kartograf landcover download --source soilgrids --bbox 770000,509000,772000,511000 --property sand -o <katalog-danych>/landcover
Downloaded to: <katalog-danych>/landcover/soilgrids_bbox_770000_509000_772000_511000.tif
md5 619292eb...   (ten sam plik, nadpisany)
```

Sidecar: `"request": {"bbox": [770000.0, 509000.0, 772000.0, 511000.0], "bbox_crs": "EPSG:2180"}`,
`"extra": {}`, `"nodata": null` — brak `property`, `depth`, `stat`; raster
bez wartosci NoData. Z pliku i sidecara nie da sie ustalic, jaki parametr
glebowy zawiera; drugi parametr dla tego samego obszaru po cichu nadpisuje
pierwszy. Przyczyna: `LandCoverManager._generate_output_path`
(`kartograf/landcover/manager.py`) buduje nazwe tylko z prefiksu providera
i obszaru. Z lektury kodu ten sam problem dotyczy CORINE (`--year` nie
trafia do nazwy) — nie sprawdzane na zywo. Zachowanie sprzed 0.7.0 (nie
regresja), ale dotyczy poprawnosci danych uzytkownika (Hydrolog/Hydrograf).

### U4 — sidecar HSG z `--godlo` nie zapisuje godla

`soilgrids hsg --godlo N-34-130-D`: `"request": {"bbox": [754438.13, 502993.54, 772420.11, 522427.43], "bbox_crs": "EPSG:2180"}`
— brak `request.sheet`, choc nazwa pliku to `hsg_N-34-130-D.tif`. Arkusze
NMT zapisuja `request.sheet`; tu zadanie uzytkownika gubi sie na rzecz
pochodnego bboxa. Drobne.

### U5 — `cache stats`: `TERYT entries` zawsze 0 z CLI

Po `landcover download --source bdot10k --teryt 1465`: `TERYT entries: 0`.
Z kodu: `teryt_cache` wypelnia tylko `Bdot10kProvider._get_teryt_for_point`
(tryb bbox/godlo), a `landcover_cmd.py` i `LandCoverManager` tworza
`Bdot10kProvider()` bez `cache=` — z CLI tabela nigdy sie nie zapelni.
Tryb `--teryt` i tak nie wymaga zapytania punktowego, wiec 0 jest tu
oczekiwane, ale statystyka w CLI jest martwa. Drobne.

### U6 — orto: dokumentacja mowi 25 cm, GUGiK daje 10 cm

Sidecar arkusza `N-34-130-D-d-2-4`: `"resolution_m": 0.1`, raster
22528x24326, piksel 0,1 m (`gdalinfo`). `README.md` (`zdjecia lotnicze
GUGiK (25 cm)`), `docs/SCOPE.md` (`Standard Resolution (25cm)`),
`docs/PRD.md` (`w rozdzielczosci 25cm`), docstring
`kartograf/providers/pl/gugik_orto.py` podaja 25 cm.
Provider bierze najnowszy rekord bez filtra rozdzielczosci, wiec
rozdzielczosc zalezy od kampanii (tu 10 cm, raster ~548 Mpx). Do poprawy
w dokumentacji (np. "rozdzielczosc wg kampanii, typowo 10-25 cm");
sidecar ma `resolution: null` — `resolution_m` w `extra.source` jest
jedynym zrodlem.

## Obserwacje bez oceny

- CZ SM5 (`CTES96`) zostawia obok `.tif` plik `.tfw` z paczki CUZK —
  zgodnie z kodem (`providers/cuzk/client.py`), GeoTIFF ma takze CRS.
- `302_5550` bez `Warning:` o nodata (kafel nie jest w calosci pusty).
- Kampanie jednej kampanii GUGiK (`82710`) maja rozne `aktualnosc` per
  arkusz (`2025-04-26` dla `N-34-130-D-d-2-4`, `2025-04-29` dla
  `N-34-130-D-d-4-1`) — katalogi `kampanie/<data>_<id>/` sa wiec rozne dla
  tego samego `id`; zgodne z ADR-030.
- Discovery WFS LAZ dla malego bboxa w bibliotece (`select_tiles`) trwala
  ~2 min (siec), wynik poprawny.
- Gramatyka `1 sheets` w podsumowaniach (`Found 1 sheets`, `for 1 sheets`).

## Klucze sidecarow (zbior ze wszystkich przebiegow, 26 plikow)

Najwyzszy poziom: `schema`, `dataset`, `country`, `product`, `provider`,
`horizontal_crs`, `vertical_crs`, `vertical_source`, `resolution`, `nodata`,
`request`, `license`, `downloaded_at`, `kartograf_version`, `transform`,
`extra`.

- `request`: `sheet`, `bbox`, `bbox_crs`, `campaigns`, `teryt`
- `license`: `id`, `attribution`, `url`
- `transform`: `horizontal`
- `extra.source`: `url`, `index_url`, `layer`, `sheet`, `acquisition_date`,
  `acquisition_year`, `pzgik_date`, `resolution_m`, `declared_crs`,
  `full_sheet`, `survey_work_id`, `data_source`, `format`, `color`
- `extra.campaign`: `id`, `date`, `survey_work_id`, `source`, `full_sheet`,
  `pzgik_date`
- `extra` (pozostale): `link`, `link_target`, `parent_request`
  (`bbox`, `bbox_crs`, `countries`), `parent_requests[]` (`bbox`,
  `bbox_crs`, `countries`), `sheet_sources[]` (`sheet`, `url`, `layer`,
  `acquisition_date`, `full_sheet`), `tile_sheet`, `year`,
  `nominal_density`, `url`, `mapname`, `cz_share`, `derived`,
  `source_layers`, `depth`, `stat`, `classes`

Polskich kluczy brak (jedyny dozwolony `teryt` wystepuje). Wartosci
pochodzace ze zrodel pozostaja w oryginale (`data_source: "Skaning
laserowy"`, `mapname: "Český Těšín 9-6"`) — zgodnie z ADR-031.

## Wnioski

1. Sciezki zmienione od ostatniego testu (ADR-030 kampanie + dowiazania
   twarde, ADR-031 angielskie klucze sidecarow, wersja `+<sha>`,
   rozwijanie godla bez `--scale`, PL-2000 `--scale 1:2000` i podpowiedzi,
   nowe komunikaty `parse`, CZ bez `--resolution`, nieczytelny cache)
   dzialaja na zywo zgodnie z dokumentacja.
2. Brak FAIL. Uwagi U1, U2, U4, U5 to kosmetyka komunikatow/metadanych.
3. Do rozwazenia przed wydaniem: U6 (poprawka dokumentacji — tania)
   i U3 (nazwa pliku/sidecar SoilGrids bez parametru, ciche nadpisanie;
   zachowanie sprzed 0.7.0, ale realne ryzyko pomylki danych) — U3 mozna
   tez swiadomie przesunac do 0.7.1 z wpisem w znanych ograniczeniach.
