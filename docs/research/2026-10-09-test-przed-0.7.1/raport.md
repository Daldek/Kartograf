# Test na zywo przed wydaniem 0.7.1 (2026-10-09)

Galaz `feat/hydrograf-0.7.1` (HEAD `858ad96`, `kartograf 0.7.1-dev+858ad96`),
bez zmian w kodzie. CLI uruchamiane z korzenia repo (cache metadanych
lokalnie), dane w `<katalog-danych>/kartograf/e2e/2026-10-09-test-przed-0.7.1/`
z jawnym `--output`. Skrypty biblioteczne jednorazowe, poza repo.

## Brama offline

| Komenda | Wynik |
|---|---|
| `pytest tests/ -m "not live"` | 3076 passed, 16 deselected |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 121 files already formatted |
| `mypy kartograf/ tests/` | no issues found in 119 source files |

## Wyniki

| # | Scenariusz | Wynik | Ocena |
|---|---|---|---|
| 1 | `download M-33-036-A-a-1-1` | kod 0; plik `nmt/pl_1992_1m_evrf2007/M-33/36/A/a/1/1/M-33-36-A-a-1-1.asc` (godlo bez zer wiodacych w sciezce i `request.sheet`), dowiazanie do `kampanie/2021-09-07_74959/` (ten sam inode); `sha256` i `size_bytes` zgodne z plikiem (36 567 732 B); `extra.source`: `height_rmse_m: 0.15`, `position_rmse_m: 0.3`, `archive_module: "1:5000"`, `declared_vertical_crs: "PL-EVRF2007-NH"` | PASS |
| 2 | `parse`/`download N-34-999-D`, `parse N-36-10-A`, `parse X-34-130-D` | kod 1, `Error: Nieprawidlowe godlo: ... poza zakresem nomenklatury PL-1992: arkusz 999 (dozwolone: 1-144)` (odpowiednio slup 36, pas X); `download` bez zapytan sieciowych | PASS |
| 3a | `download N-34-130-D-d-2-4 --campaigns all` (dwa razy) | kod 0, `Downloaded 3 campaign files ... (0 already existed)`, potem `(3 already existed)`; kampanie `2022-07-21_76748`, `2024-05-27_81449`, `2025-04-26_82710`, kazda z `sha256` zgodnym z plikiem i `declared_vertical_crs` | PASS |
| 3b | `... --min-year 2026` | kod 1, `Error: Najnowsza kampania N-34-130-D-d-2-4 ma date 2025-04-26 — starsza niz min_year=2026 (--min-year)` | PASS |
| 3c | `... --min-year 2024 --campaigns all` | kod 0, `(2 already existed)` — tylko 2024 i 2025 | PASS |
| 3d | `--bbox ... --campaigns all --target-crs EPSG:2180`, `--bbox ... --min-year 2024 --target-crs EPSG:2180` | kod 1, `Error: --campaigns all nie dziala z --target-crs — wycinek sklada jedna kampanie na arkusz` (bez odeslania do wydania), `Error: --min-year nie dziala z --target-crs ...` | PASS |
| 4 | `download --bbox 770000,509000,771000,510000 --target-crs EPSG:2180` | kod 0, `bbox/770000_509000_771000_510000.tif`, EPSG:2180, 1001x1001, NoData -9999; `extra.sheet_sources[]` (2 arkusze, kampania 82710); `sha256` zgodne | PASS |
| 5 | `download --bbox 16.19,50.42,16.25,50.45 --bbox-crs EPSG:4326 --country auto` (Kudowa) | kod 0; CZ: jeden wycinek `nmt/cz_dmr5g_bpv/bbox/...tif` (EPSG:5514, `vertical_crs` EPSG:8357), `extra.all_nodata: false`, `extra.parent_request.countries: ["CZ","PL"]`; PL: 4 arkusze `M-33-57-C-b-4-1..4` z tym samym `parent_request` | PASS |
| 6 | Biblioteka: `LandCoverManager(provider="bdot10k", cache=MetadataCache()).download_all_counties(bbox=340000,290000,350000,300000 EPSG:2180, keep_raw=True)` | 2 powiaty: `bdot10k_teryt_0208.gpkg`, `bdot10k_teryt_0224.gpkg` + surowe `bdot10k_teryt_<T>_GPKG.zip` z wlasnymi sidecarami (`sha256` ZIP zgodne z plikiem); sidecar GPKG: `request.teryt`, `extra.parent_request`, `extra.http.content_length` (= rozmiar ZIP; `etag`/`last_modified` null — serwer ich nie podaje), `extra.source.{url,teryt,format,raw_file}`; `download_by_bbox` na tym obszarze: `ValidationError ... przecina 2 powiaty (0208, 0224); uzyj LandCoverManager.download_all_counties ...` | PASS |
| 7 | CLI `landcover download --source bdot10k --bbox 340000,290000,350000,300000` | kod 0, dwie linie `Downloaded to:` (0208, 0224), pliki tej samej wielkosci co z biblioteki | PASS |
| 8 | Biblioteka: `hsg_from_rasters(clay, sand, silt, bbox=..., crs="EPSG:2180", pixel_m=250, output_path=...)` na rastrach z `landcover download --source soilgrids --property clay/sand/silt` | raster EPSG:2180 40x40, piksel 250 m, NoData 0, klasy {B: 1589, luka: 11} (luki = komorki zrodla z trojka zer); `sha256` wyniku zgodne; `extra.source_files[]` z `sha256` wejsc zgodnymi z plikami, `extra.source_layers: [clay, sand, silt]`; `pixel_m=0` -> `ValidationError` | PASS |
| 9 | Biblioteka: `build_cutout_from_sheets([N-34-130-D-d-2-3, N-34-130-D-d-2-4], bbox jak w 4, "EPSG:2180", output_path, resolution="1m", vertical_crs="EVRF2007")` | wynik identyczny piksel w piksel z wycinkiem CLI z pkt 4 (ta sama siatka 1001x1001, poczatek 769999.5/510000.5); sidecar z `sha256`, `size_bytes`, 2 `sheet_sources`; brakujacy arkusz i `output_path` = arkusz wejsciowy -> `ValidationError`, nic nie zapisane | PASS |
| 10a | `download N-34-130-D-d-2-4 --resolution 5m --vertical-crs KRON86`; to samo w trybie `--bbox ... --target-crs EPSG:2180` | kod 1, `Error: NMT 5m (PL) jest dostepny tylko w EVRF2007 — podano --vertical-crs KRON86; ...`, katalog wyjscia nie powstal | PASS |
| 10b | `download N-34-130-D-d-2-4 --year 2024` (z `--product nmt` i bez) | kod 1, `Error: --year dziala tylko z --product laz (podano nmt); wybor roku dla NMT/NMPT/orto bedzie w 0.7.2. Teraz uzyj --min-year RRRR ...` | PASS |
| 10c | `... --min-density 4` | kod 1, `Error: --min-density dziala tylko z --product laz (podano nmt); pomin --min-density` | PASS |
| 10d | `download CTES96 --year 2024`; `--bbox` Kudowa `--country cz --year 2024` | kod 1, `Error: --year nie dziala dla CZ (CUZK nie ma wyboru roku; podano nmt); pomin --year` | PASS |
| 11 | `download --bbox 770000,509000,770300,509300 --product laz --year 2025`; to samo z `--year 1999` | kod 0, 2 kafle `82707_*` z `request.year: 2025`, `extra.{tile_sheet, year, nominal_density: 4, url, parent_request}`, `sha256` zgodne; `--year 1999`: kod 1, `Error: rocznik 1999 nie istnieje w usludze EVRF2007 (dostepne: 2026, ..., 2018)` | PASS |
| 12 | `download N-34-130-D-d --resolution 5m` (5 m bez `--vertical-crs`) | kod 0, 10 z 16 arkuszy, `Warning: GUGiK nie ma danych dla 6 z 16 arkuszy ...` | UWAGA (U1) |
| 13 | `cache stats` | kod 0, `TERYT entries: 1` po pobraniu BDOT10k przez biblioteke (wpis obszaru PRG), bez wzrostu po tym samym bboxie z CLI (trafienie w cache) | PASS |

## Uwagi

### U1 — 5 m: arkusze bez danych opisane jako "morze, obszar za granica"

`download N-34-130-D-d --resolution 5m`: 6 arkuszy (`-1-1`, `-1-2`, `-2-1`,
`-2-2`, `-2-3`, `-2-4`) konczy sie `Brak danych NMT 5m`, a podsumowanie
podaje przyczyne `(morze, obszar za granica)` dla obszaru w glebi kraju.
Kod `develop` (0.7.0) z `--force` (bez cache) daje dla `N-34-130-D-d-2-4`
i `N-34-130-D-d-1-1` ten sam wynik — to nie regresja 0.7.1, tylko luka
w skorowidzu 5 m GUGiK; komunikat zgaduje przyczyne zbyt waskim
przykladem. Kosmetyka, poza zakresem 0.7.1.

## Wniosek

Brak FAIL. Wszystkie zmiany 0.7.1 objete testem (godla bez zer wiodacych,
`ParseError` przed siecia, `sha256`/`size_bytes`, pola rekordu skorowidza,
kampanie i `--min-year`, wycinek `--target-crs`, `--country auto` z
`all_nodata`, BDOT10k z wielu powiatow i `keep_raw`, `hsg_from_rasters`,
`build_cutout_from_sheets`, bledy zamiast cichych zamian, LAZ `--year`,
`cache stats`) dzialaja na zywo zgodnie z `docs/CHANGELOG.md` [0.7.1].
Galaz nie wymaga zmian przed wydaniem.
