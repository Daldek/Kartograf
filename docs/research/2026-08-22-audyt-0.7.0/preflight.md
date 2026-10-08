# Pre-flight scan planu 2026-08-22-release-0.7.0-audit

Recenzent: agent opus (read-only). Zakres: caly plan (1243 linie, 26 zadan), ledger
`progress.md` (rulingi), raporty `audit/*-verify.md`. Zaden plik planu ani kodu nie zostal
zmieniony. Weryfikacja odwolan `plik:linia` prowadzona grepem na `fix/release-0.7.0-audit`
(HEAD 951356d). Srodowisko sprawdzone: rasterio 1.5.0, pyproj 3.7.2, pyshp 3.0.3,
pytest 9.0.2, `ruff check` czysty, `mypy kartograf/` = **Found 33 errors in 10 files**
(baseline z Global Constraint (c) potwierdzony), `setuptools` NIEobecne w `.venv`.

---

## 1. Pary zadan dzielace plik albo interfejs

| A | B | Co A produkuje / B konsumuje (wspolny plik) | Kolejnosc OK? | Konflikt (linie planu) | Rozstrzygniecie |
|---|---|---|---|---|---|
| 5 | 16 | `DownloadManager.last_result` (`DownloadResult`) -> CLI czyta `last_result.failed` (`manager.py` / `download_cmd.py`) | TAK (5 < 16) | brak; plan sam ostrzega, ze `Mock().last_result.failed` jest truthy (l. 869) | zostawic; wymog "nadac `last_result = None` mockom" musi zostac w kroku 4 zad. 16 |
| 2 | 12 | `core/sheet_parser.py`: 2 -> `_get_parent_from_200k`/`_get_children_from_500k` (l. 375, 441); 12 -> `_bboxes_intersect` (831), `find_sheets_for_bbox` (885), docstring klasy (37) | TAK | rozlaczne funkcje; wspolny `tests/test_sheet_parser.py` (2: l. ~409-502, 12: `test_touching_edge` l. 916) | bez zmian; zad. 12 ma pracowac na pliku juz poprawionym przez 2 |
| 11 | 12 | 11 produkuje bbox zdegenerowany `(x,y,x,y)`; 12 zmienia semantyke przeciecia i rozszerza zdegenerowany bbox | TAK (11 < 12) | brak - sprawdzone na zywo: dzis `find_sheets_for_bbox(BBox(420500,230500,420500,230500,'EPSG:2180'))` = 1 arkusz, wiec test z zad. 11 jest zielony przed zad. 12; punkt na linii siatki daje dzis `[]` (czerwien zad. 12) | bez zmian |
| 6 | 7 | `hydrology/hsg.py`: 6 -> `_USDA_RULES`, `classify_usda_texture_array`; 7 -> maska nodata liczona z wartosci ZRODLOWYCH + statystyki | TAK (6 < 7) | zad. 7 zaklada `hsg[0,0] == 3` dla (300,300,400) g/kg = `clay_loam` -> C; poprawne DOPIERO po regulach z zad. 6 | bez zmian; w zad. 7 dopisac, ze wartosc kontrolna wynika z regul zad. 6 |
| 6 | 20 | `TEXTURE_NAMES` (`hsg.py:46`) - martwy wg V5, ozywiony przez zad. 6 | TAK | plan ma jawny WYJATEK (l. 1010) + kontrole grepem | bez zmian |
| 9 | 10 | `auth/client.py`: 9 usuwa `get_access_token` (l. 176-200) i `/token`; 10 przepisuje `_start_proxy`/`_ensure_proxy`/`is_available`/`download_file` | TAK (9 < 10) | wspolny plik i wspolny `tests/test_auth_client.py`; 9 kasuje `TestGetAccessToken` (l. 205-242) | bez zmian |
| 9 | 20 | `providers/corine.py`: 9 zmienia log l. 559-561; 20 kasuje blok l. 60-227 (`KEYCHAIN_SERVICE`, 3 funkcje) + `DLR_YEARS` (387) + docstring | TAK (9 < 20) | po zad. 20 numeracja linii corine przesuwa sie o ~-167; odwolania zad. 20 liczone sprzed usuniecia | zad. 20 ma pracowac po nazwach symboli, nie po liniach (juz tak jest) |
| 20 | 9 | zad. 20 usuwa `get_clms_credentials` - JEDYNEGO dzisiejszego czytelnika `CLMS_CREDENTIALS`; zad. 9 dodaje `CLMSCredentials.load_from_env` w proxy | TAK (9 < 20) | brak: zad. 9 nie uzywa zadnego symbolu z corine; `KEYCHAIN_SERVICE` w `auth/proxy.py:41` to inna, zywa kopia (plan to odnotowuje) | bez zmian |
| 16 | 17 | `cli/download_cmd.py`: 16 -> `_create_provider_and_storage` (60), `_resolve_pl_sentinels` (106), galaz godla (~550), `_download_pl_bbox` (757), `_download_pl_geometry` (1381); 17 -> `_dispatch_area` (372-422) | TAK (16 < 17) | rozlaczne funkcje; wspolny `tests/test_cli.py` | bez zmian |
| 16 | 20 | poz. 16-17 inwentarza martwego kodu (galaz `laz`, 3x `getattr(..., "KRON86")`) robi zad. 16 | TAK | zad. 20 ma zweryfikowac, ze poz. 16-17 juz nie istnieja | bez zmian |
| 14 | 18 | `cli/_parser.py`: 14 -> l. 252 (`choices`), 18 -> l. 24/201/375 (opisy) | TAK | rozne linie | bez zmian |
| 18 | 20 | `cli/commands.py`: 18 wynosi dispatch do `_dispatch()` i owija w bariere (l. 67-105); 20 kasuje 9 re-eksportow (l. 13-63) | TAK (18 < 20) | brak; zweryfikowano, ze testy importuja z fasady tylko nazwy z listy "ZOSTAJA" | bez zmian |
| 13 | 19 | `tests/test_gugik_provider.py` + `tests/test_gugik_orto.py`; 19 dodatkowo usuwa lokalny autouse z test_gugik_orto (l. 19-35) i patchuje `_validated_layers` w `test_get_opendata_url_tries_all_layers` (481-497) | TAK (13 < 19) | zad. 13 juz uzywa tej samej sztuczki `provider._validated_layers[(res, vcrs)] = [...]`; klucz slownika potwierdzony (`gugik.py:342`) | bez zmian |
| 8 | 19 | 8 usuwa `test_get_bbox_for_teryt_returns_bbox` (21. test z siecia) -> 19 oczekuje **20** FAILED | TAK (8 < 19) | brak | bez zmian |
| 19 | 21 | `pyproject.toml`: 19 dodaje marker `real_wms_layers`, 21 zmienia `[project]`/`[tool.setuptools]` | TAK | rozne sekcje | bez zmian |
| 20 | 22-24 | 20 kasuje `get_clms_credentials`/`save_credentials_to_keychain`; docs nie moga ich wymieniac | TAK (20 < 22-24) | zad. 23 krok 1 ma jawny nakaz usuniecia odwolan | bez zmian |
| 6 / 17 / 25 | - | `docs/DECISIONS.md`: 6 dodaje ADR-025 (przed szablonem ADR-XXX, l. 762); 17 dopisuje addendum ADR-023 pkt 5 + zdanie do pkt 4; 25 podmienia ilustracje w pkt 4 (l. 575) | TAK (6 < 17 < 25) | 17 i 25 edytuja TEN SAM akapit (pkt 4); plan jawnie rozdziela zakresy (l. 964) | zostawic, ale w zad. 25 dopisac "nie ruszac zdania dodanego w zad. 17" |
| 22 | 1-21 | CHANGELOG konsumuje komunikaty commitow 1-21 (`git log ff145a9..HEAD`) | TAK | brak | bez zmian |
| 22 / 23 / 26 | - | liczba testow i pokrycie wpisywane niezaleznie w trzech zadaniach | TAK, ale | 22 (krok 1), 23 (l. 287 README), 26 (krok 2) moga wpisac trzy rozne liczby | wskazac JEDEN przebieg zrodlowy (po zad. 21) i przepisywac go doslownie |
| 19 | 1-18 | blokada sieci w conftest powstaje dopiero w 19, a testy dodaja zadania 1-18 | ryzyko | Global Constraint (g) mowi "mockowac jak dotychczas"; blad wyjdzie dopiero w kroku 1 zad. 19 | rozwazyc przesuniecie samej fixtury `_block_network` przed zad. 2 (patrz P-13) |
| 8 | 20 | po zad. 8 `LandCoverProvider.validate_teryt` traci jedynego produkcyjnego konsumenta (`soilgrids.py:414`), na ktorym V5 oparl korekte "nie usuwac" | TAK | zad. 20 nie ma `validate_teryt` na liscie - brak realnego konfliktu | odnotowac w raporcie zad. 20, ze inwentarz V5 sie zdezaktualizowal |

---

## 2. Spojnosc wewnetrzna zadan

Legenda: "linie" = czy odwolania `plik:linia` istnieja (sprawdzone grepem);
"czerwien" = czy krok "test czerwony" faktycznie bedzie czerwony na obecnym kodzie.

| Zad. | Testy zgodne z kodem (nazwy/sygnatury/`match=`) | Linie/symbole | Global Constraints + rulingi | Scope commita | Czerwien (dowod) |
|---|---|---|---|---|---|
| 1 | tak, poza jednym wyrazeniem asercji (P-6); `match="mozaik"` zgodne z proponowanym komunikatem ("kafli mozaiki") | OK: `_tile_grid` 248, `export_image` 117-185, `mosaic.py` 19-64; `test_tiling_above_limits_mosaics` l. 404 (bbox 0,0,16,16 = 8x8 px - jak w planie), brak asercji o kolejnosci `requested` | (d) ADR-024 nietkniety; rasterio 1.5.0 ma `dst_path`+`dst_kwds`, przy `dst_path` profil z 1. zrodla i `out_profile["nodata"]=nodata` - "bit-w-bit" wiarygodne | `fix(cuzk)`, `perf(transport)` - `perf` jest typem z 2.2, `transport` scope OK | TAK: dzis `_tile_grid` kotwiczy w SW (`bbox.min_y + row_off*px`), a `merge(bounds=)` w NW; krok 9 czerwony, bo `merge()` wolane bez `dst_path` (mosaic.py:44-48) |
| 2 | tak; 3 wskazane asercje potwierdzone: `test_get_parent_from_200k_section_b` (N-34-37 -> dzis "N-34-B"), `children[35]=="N-34-36"` (A), `children[0]=="N-34-109"` (D) | OK: 375, 441; `_apply_200k_subdivision` (740) potwierdza, ze wiersz 0 = polnoc | OK | `fix(parser)` OK | TAK: zweryfikowane numerycznie - nowa formula daje 144/144 dzieci wewnatrz bboxa rodzica i zmienia rodzica dla **72** arkuszy (dokladnie jak w planie) |
| 3 | tak; `match="geotransformacj"` uzgodnione z polskim komunikatem; wzor `_mock_transformer/_mock_group` jest w `tests/test_transform_crs.py`, nie w `test_cuzk_dmr.py` (trzeba go przeniesc/zaimportowac) | OK: `_pinned` 344, `horizontal_transform` 183, `_bbox_to_crs` 353, `_shift_in_place` 391, `bbox_to_crs` 516/530, polityki 64-80; `probe_point` jest polem `TransformPolicy` (crs.py:49), probe implementowany (crs.py:187-201) | OK; `_VERTICAL_POLICY` bez probe zgodnie z decyzja 3; docstring `crs.py` jest po POLSKU, a plan podaje zdanie po angielsku ("jezyk pliku - sprawdzic") | `fix(cuzk)` OK | TAK: `grep probe_point kartograf/` = tylko definicja w `crs.py`; przy dwoch mockach 0,051 vs 0,5 i `_HORIZONTAL_POLICY.min_accuracy_m=1.0` dzis wygrywa 0,051 |
| 4 | tak; `MetadataCache(db_path=...)`, `set_url/get_url(godlo, resolution, vertical_crs, product)`, `set_sheet(system, godlo, payload)` zgodne z kodem | OK: `get_url` 125 (cialo 151-175), `get_teryt` 220, `get_sheet` 287, `stats` 341; zagniezdzony `with self._write_lock` w `get_url` na l. 166 (ostrzezenie o nierekurencyjnym Locku trafne) | OK | `fix(cache)` OK | prawdopodobnie TAK (V2: 8 watkow x 2000 -> 9339 zlych); plan ma zapasowy wariant "zwiekszyc iteracje" |
| 5 | test `manager._storage._subdir` dziala (`_subdir` to property, `subdir=` to arg konstruktora) | OK: `__init__` 139-192 (plan pisze ~175-193 - to sam korpus), `DownloadResult` 60 z property `total` 79, `storage.py` 17/313 | **NARUSZENIE (f)**: implementacja wywroci ~25 istniejacych testow spoza listy plikow (P-1) | `fix(download)`, `feat(download)` OK | TAK: `GugikNmptProvider.descriptor_key = "pl.gugik.nmpt"` (l. 125), a dzis storage bierze podkatalog z `resolution` -> `nmt_1m` |
| 6 | 12 regul zweryfikowanych numerycznie: pokrywaja caly symplex (0 punktow bez klasy), 50 punktow lapie 2 reguly (rozstrzyga kolejnosc); 4 punkty kontrolne V4 potwierdzone | OK: `hsg.py` 46/82/189, `TEXTURE_CLASSES` 30, `TEXTURE_TO_HSG` 66 (clay_loam->C) | (b) OK; ruling A4-4 respektowany; ALE uzasadnienie `default=loam` jest bledne (P-3) i liczby skutku dotycza innej sciezki (P-4) | `fix(hsg)`, `docs(adr)` - scope `adr` spoza listy z (j) (P-7) | TAK: dzis `(0,70,30)`->loamy_sand, `(20,45,35)`->sandy_clay_loam, `(35,45,20)`->sandy_clay |
| 7 | tak; helper `_create_test_raster` istnieje i wymaga rozszerzenia o `crs`/`nodata` (plan to mowi) | OK: `calculate_hsg_by_bbox` 394 (odczyt rastrow 475-498), `get_hsg_statistics` 535 (`pixel_area` z `transform[0]*transform[4]`) | OK | `fix(hsg)` OK | TAK: dzis jedyna maska to `(clay==0)&(sand==0)&(silt==0)` (hsg.py:498), a pole liczone jest z transformu bez uwzglednienia CRS geograficznego |
| 8 | tak; `corine.py:873` = `download_by_teryt` z `NotImplementedError` (wzor), `landcover_cmd.py:197` lapie `NotImplementedError` (plan pisze 196 - roznica 1 linii), `download_by_admin_unit` w `base.py:278` juz rzuca | OK: `soilgrids.py` 251/378/424/449, `corine.py` 536/994/1014 | ruling zad. 8 (NotImplementedError) respektowany; BREAKING trafia do zad. 22 | `fix(landcover)`, `fix(soilgrids)` OK | TAK: dzis `_transform_bbox_to_*` przelicza 2 naroza; `test_download_via_wms_dimensions` (l. 685-699) pinuje `WIDTH=100`/`HEIGHT=100` |
| 9 | tak; `_make_handler` istnieje (`tests/test_auth_proxy.py:203`), `/token` w `do_GET` na l. 184, `TestGetAccessToken` na l. 205 | OK: proxy 41/44/52/91/148/173/193; client 176-200 (+ przyklad w docstringu l. 40); corine 559-561 | OK; jedyny inny czytelnik `get_access_token` to `CLMSAuth` (corine.py:735) - nietkniety | `fix(auth)` OK | TAK: `load_from_env` nie istnieje; `/token` dzis zwraca 200/500 |
| 10 | tak; `reset_singleton` (test_auth_client.py:18) zeruje `_instance/_proxy_process/_proxy_port` | OK: 77/115/133/151/252-295, `PROXY_STARTUP_TIMEOUT` 21, atrybuty klasy 49-50 | OK | `fix(auth)` OK | TAK: `download_file` (252-295) pisze wprost do `output_path`, nie sprawdza `Content-Length`, `is_available` zawsze wola `_ensure_proxy` |
| 11 | tak; `_make_gpkg_blob` (test_geometry.py:164-189) dopisuje WKB POINT `struct.pack(f"{endian}Bi2d", ...)` = 21 bajtow bez wyrownania - zgodne z offsetami planu | OK: geometry 29/118/269 | OK; brak obslugi EWKB z flaga SRID (0x20000000) przesuwajaca wspolrzedne o 4 B - edge, GPKG jej nie uzywa | `fix(geometry)` OK | TAK: pyshp 3.0.3 - `Point` nie ma `bbox` (potwierdzone: `AttributeError: 'Point' object has no attribute 'bbox'`) |
| 12 | tak; komunikat zawiera slowo "system" (`match="system"` OK) | OK: 37/831/885 oraz `parser_2000.py:629`; `_bboxes_intersect` uzywa dzis `<` (styk = przeciecie) | ruling A1-7 respektowany; wewnetrzna sprzecznosc co do wspoldzielenia stalej `_DEGENERATE_EPS` (P-12) | `fix(parser)` x2 OK | TAK: `find_sheets_for_bbox(BBox(21.0,52.0,21.0,52.0,'EPSG:4326'))` = `[]`; bbox arkusza daje dzis nadmiarowe arkusze |
| 13 | tak, ale `is_wcs_available` nie ma konsumentow produkcyjnych (tylko 2 testy) - zakres zmiany mniejszy niz sugeruje opis | OK: registry 80-85/240/281 (`notes` istnieje w `AccessChannel`), gugik 81/422/568, gugik_orto `_get_opendata_url` **293** (plan pisze 340-386 - to wnetrze funkcji), test_sources_registry 186-241 (`test_nmt_1m` 227-241, `server_reprojection is True` na 190 i 216) | OK; ale model `sonnet` przy tym zakresie jest ryzykowny (P-5) | `fix(sources)`, `fix(download)` OK | TAK: kanal WCS ma dzis `_PL_VERTICAL_BOTH`; `download_bbox` nie waliduje EVRF2007; `_get_opendata_url` nie zlicza bledow transportowych |
| 14 | tak; `test_supported_formats` (l. 79-85) nie asertuje GML, wiec nie trzeba go ruszac | OK: bdot10k 105/108/191-193/463/554(+`output_gpkg` ~609)/843-845, docstring "GPKG, SHP, or GML" na l. 219; base 364/385; `_parser.py:252`; `landcover_cmd.py:53` | OK | `fix(landcover)`, `fix(cli)` OK | TAK: `_extract_gpkg_from_zip` nic nie zwraca, `get_supported_formats` zwraca `["GPKG","SHP","GML"]`, argparse przyjmuje GML |
| 15 | tak; `test_download_by_bbox_auto_path`/`_godlo_auto_path` sprawdzaja tylko podlancuchy "bbox"/"N-34-130-D" - przezyja zmiane (plan sluszny) | OK: manager 241/274/311, `_generate_output_path` 398, test l. 873 (`assert "TestProv" in ...`) | BREAKING -> zad. 22 OK | `fix(landcover)` OK | TAK: dzis `f"{self._provider.name}_{godlo}.gpkg"` (ze spacjami) |
| 16 | tak; komunikaty i asercje spojne; ostrzezenie o `Mock().last_result` trafne | OK: 60/106/119-120/550-551/757-758/1381-1382; `_resolve_pl_sentinels` wolany na kazdej sciezce PRZED tymi liniami, zaden test nie wola `_download_pl_*` bezposrednio (zamiana `getattr` na atrybut bezpieczna) | OK | `fix(cli)` x2, `refactor(cli)` OK | TAK: dzis `--product nmpt --resolution 5m` konczy sie 0; hierarchia z porazkami konczy sie 0 |
| 17 | tak; nowa semantyka wymaga przepisania istniejacych testow `TestAutoSplit*` (plan tego wymaga i kaze je wylistowac) | OK: 372-422, 319, 322-369, 425; `_country_bbox(auto=False)` daje bbox bez przyciecia (zgodne z asercja) | ruling N6-2 respektowany (i jawnie nadpisuje rekomendacje V6 "NIE w tym wydaniu" - poprawnie, ruling jest wiazacy); ruling A3-2 respektowany | `feat(cli)`, `fix(cli)`, `docs(adr)` - `adr` spoza listy (j) | TAK: dzis `--country auto` + `--system 2000` na bboxie przygranicznym = exit 1 |
| 18 | tak; `test_help_flag` istnieje; teksty `--help` nie sa asertowane | OK: commands.py 67-105; `_parser.py` 24/201/375 (cytaty doslownie zgodne); `landcover_cmd.py:51` | OK | `fix(cli)`, `docs(cli)` OK | TAK: `main()` nie ma zadnego `try` |
| 19 | fixture `_offline_wms_layers` NIE zadziala jak opisano (P-2); reszta OK; `real_wms_layers` dopisywane do `markers` (dzis tylko `live`) | OK: test_gugik_provider 481-497, test_gugik_orto 19-35 (autouse uzywa `return_value`, nie `side_effect`), `TestFetchWmsLayers` 139, `gugik.py:271` wlasna `Session`; "8 testow live" potwierdzone (1 klasa x 8 parametrow, `test_pl2000_verification.py:425`) | (g) OK; wybor `RuntimeError` zamiast `OSError` jest sluszny - `_get_validated_layers` lapie tylko `RequestException/ValueError/ParseError` | `test:`, `test(cli)` OK | TAK (mechanicznie): 21 testow wola `_fetch_wms_layers` z wlasna `Session` |
| 20 | test przypinajacy A5-1 jest ZIELONY z definicji (plan to przyznaje); `CorineProvider.__init__` nie startuje proxy, wiec test jest bezpieczny takze po zad. 10 | OK: corine 67/70/132/196/229/387; commands.py 13-63 (9 re-eksportow); `providers/__init__.py`; `landcover/manager.py:442-443`; `auth/proxy.py:41` | OK; lista "ZOSTAJA" zgodna z `grep "from kartograf.cli.commands import" tests/` | `refactor:` (bez scope) - dopuszczalne, ale niespojne z (j) | n/d (zadanie usuwajace) |
| 21 | test parsuje TOML, nie wymaga setuptools | OK: pyproject 7-8/15/43-44 - ale `version = "0.6.1"` (P-8) | ruling (wersja/authors) respektowany | `chore(build)` - scope `build` spoza listy (j) | TAK: `dynamic` nie istnieje, `include` nie istnieje |
| 22 | n/d | OK i BARDZO dokladne: `[0.7.0]` 8-264, duplikaty `### Added` 188/232, `### Fixed` 209, `### Tests` 240/252, `gugik_laz.py` na 190, `nmt_2000_1m` na 342, `requirements.txt` na 579, link porownania na 833 | (e) ASCII OK | `docs(changelog)` - scope spoza (j) | n/d |
| 23 | n/d | OK: README 49 (`--bbox 419000,...`), 89-91, 186-190, 287; CLAUDE.md ma sekcje "Ograniczenia" | (e) README z diakrytykami - plan to respektuje | `docs(readme)` OK | n/d |
| 24 | n/d | OK: PRD 91/117/123/154/183, SCOPE 55 i 118 ("9 warstw WMS"), `kartograf.__all__` = **31** (zgodnie z planem); `TransformError`/`TransformUnavailableError` NIE sa w `__all__` (plan przewiduje sprawdzenie) | OK | `docs(scope)` - scope spoza (j) | n/d |
| 25 | n/d | OK: wszystkie 7 plikow istnieje; ADR-023 pkt 4 z fraza "okolic Krakowa/Rzeszowa" na l. 575; `bugfix-report.md` l. 4 = "Zgloszenie: `seam-report.md`..." | OK | `docs(research)` - scope spoza (j) | n/d |
| 26 | n/d | OK: DEVELOPMENT_STANDARDS 10.1 (~472-482), 13.4 (~654-664); backlog zgodny z rulingiem "odlozone" | OK | `docs(progress)` - scope spoza (j) | n/d |

---

## 3. Wiernosc wobec ustalen

Kontrola: kazde ustalenie z werdyktem "Naprawa przed wydaniem 0.7.0: TAK / DOCS-ONLY"
oraz kazde "Nowe ustalenie" z 7 raportow verify zestawione z tabela "Ustalenie -> Zadanie".

| Grupa | Ustalenia z werdyktem TAK/DOCS-ONLY | Przypisane w planie | Pominiete |
|---|---|---|---|
| A1 + N1 | A1-1..A1-9, N1 | 2, 3, 11, 13, 11, 13, 12, 12+24, 5+22, 18 | **brak** |
| A2 + V2-N1 | A2-1,2,3,5,6,8,9 + V2-N1 (A2-4/7 odlozone) | 4, 5, 5+16, 5, 14, 23+24, 13, 16 (+26) | **brak** |
| A3 + N3 | A3-1..A3-5, N3-1, N3-2 | 1, 17, 1, 1, 3, 1, 1+checklista | **brak** |
| A4 + N4-1 | A4-1..A4-11, A4-13, A4-14, N4-1 (A4-12 odlozone) | 9, 9+10, 8, 6, 7, 7, 8, 6, 6+23, 9(+26), 10, 10, 10, 10 (+26) | **brak** |
| A5 + N5-1 | A5-1,2,3,6,8 + martwy kod 17 poz. + N5-1 (A5-4/5/7 odlozone) | 23+20, 15, 26, 3+26, 24, 20 (+16), 16 (+26) | **brak** |
| A6 + N6 | A6-1..A6-15 + N6-1, N6-2, N6-3 | 23/24, 14, 22, 21, 21, 21, 24, 23/24/26, 22, 22, 24, 24, 18, 25+23/24, 23, 23+24, 17, 14 | **brak** |
| A9 | A9-1..A9-5 | 12, 20, 13, 4, 5 | **brak** |
| A7 | A7-1..A7-6 (+A7-7, A7-10 przy okazji) | 25 | **brak** |
| A8 + N7 | A8-1,2,5,6,7 + N7-1, N7-2 (A8-3/4 odlozone) | 19, 19, 19, 19, 26, checklista, 26 | **brak** |

Wniosek: **zadne ustalenie z kwalifikacja "TAK" ani "DOCS-ONLY" nie zostalo pominiete.**
Odlozone (A2-4, A2-7, A4-12, A5-4, A5-5, A5-7, A8-3, A8-4 + A5-3, A5-6, A1-8, A1-9,
A4-10 reszta) maja pozycje w backlogu zad. 26 - zgodnie z rulingiem.

Scope creep (zmiany, ktorych zaden raport nie uzasadnia):

| Element planu | Zrodlo | Ocena |
|---|---|---|
| zad. 17: `--resolution 1m` na liscie flag "tylko-PL" | ruling N6-2 wymienia `--system`, `--vertical-crs KRON86`, `--product != nmt`; `--resolution 1m` dodaje plan (Decyzja 14) | uzasadnione i jawnie odnotowane; skutek scisle lepszy niz dzisiejszy exit 1 - **akceptowalne** |
| zad. 1 krok 9-11: `merge(dst_path=)` | A3-4 (TAK) - dokladnie ten zakres | OK |
| zad. 6: `float64` + `_normalize_pct` | A4-8 + A4-15 (RuntimeWarning) | OK, A4-15 to "przy okazji" tej samej linii |
| zad. 13: `is_wcs_available()` zawezone do KRON86 | nie wynika wprost z A1-4 (raport mowi o deskryptorze i `download_bbox`) | drobne rozszerzenie, ale logicznie spojne; zmienia 1 istniejacy test - **akceptowalne**, warto dopisac do CHANGELOG |
| zad. 21: usuniecie `requirements*.txt` | ruling zad. 21 | OK |
| zad. 22: wpis A6-16 (`--bbox-crs` +5514/+3045) | Minor "przy okazji" | OK |

---

## 4. Ryzyka wykonawcze (zadania zbyt ogolne / zly model)

| Zad. | Model w planie | Brakujaca wartosc / decyzja | Rekomendacja |
|---|---|---|---|
| 13 | sonnet | 3 pliki produkcyjne + przepiecie calej klasy `TestGugikProviderDownloadBbox` (7 testow, w tym `test_download_bbox_invalid_format` i `_wrong_crs`, ktorych komunikaty zmieni nowy guard, bo pojdzie on PRZED walidacja formatu/CRS); dobor `COVERAGE_IDS`; przepisanie testu deskryptora "per kanal" | **opus** (albo dopisac w planie kolejnosc guardow i liste 7 testow do przepiecia) |
| 19 | opus | ambiwalencja: "najprosciej `return_value` nie wystarczy... albo zwracajacej sume wszystkich list... wiec zwracac DOKLADNIE hardcoded" - dwie sprzeczne instrukcje; brak decyzji, co ze stubem dla klasy `live` | zostawic opus, ale rozstrzygnac tresc fixtury (P-2) |
| 20 | sonnet | decyzja "czy import `CorineProvider` w `landcover/manager.py` tworzy cykl" zostawiona implementerowi; przepisanie docstringu modulu `corine.py` (sekcja credentials) to zadanie redakcyjne zalezne od zad. 9 | sonnet OK, jesli plan przesadzi wariant: "zostawic `year == 1990`, poprawic tylko komentarz" (import CorineProvider w managerze jest zbedny) |
| 21 | sonnet | `setuptools` NIE ma w `.venv` -> krok 3 (`pip install -e .`) i kontrola A6-5 sa niewykonalne offline; plan nie mowi, co wtedy z `--fail`/raportem | sonnet OK po dopisaniu: "brak setuptools = pominac krok 3, odnotowac w raporcie, przeniesc do Checklisty release pkt 4" |
| 2 | sonnet | krok 4 "jesli pada cos wiecej - sprawdzic, czy asercja byla przypadkowo zgodna" wymaga osadu, ale zweryfikowalem, ze pada dokladnie 3 asercje wymienione w planie | sonnet OK |
| 4, 14, 15, 18, 25, 26 | sonnet | brak brakow | sonnet OK |
| 22 | opus | "liczba testow z ostatniego przebiegu" - nie wskazano, ktory przebieg jest kanoniczny dla 22/23/26 | dopisac: przebieg po zad. 21 |
| 12 | opus | `_DEGENERATE_EPS` deklarowany jako wspolna stala modulu, a wartosci sa w roznych jednostkach (1e-7 stopnia vs 1e-3 m) | patrz P-12 |

---

## 5. Kolejnosc

| Zaleznosc | Wymuszona kolejnosc | Stan w planie | Uwaga |
|---|---|---|---|
| `last_result` (5) -> CLI (16) | 5 < 16 | OK | - |
| `_USDA_RULES`/`TEXTURE_NAMES` (6) -> nodata (7), martwy kod (20) | 6 < 7 < 20 | OK | - |
| usuniety test TERYT (8) -> liczba 20 FAILED (19) | 8 < 19 | OK | - |
| proxy env/`/token` (9) -> klient (10) i martwy blok corine (20) | 9 < 10 < 20 | OK | - |
| punkty (11) -> semantyka krawedzi (12) | 11 < 12 | OK; sprawdzone, ze test zad. 11 jest zielony takze przed zad. 12 | - |
| ten sam plik `download_cmd.py` (16, 17) | 16 < 17 | OK | - |
| kod (1-21) -> docs (22-26) | OK | OK | 22 wymaga `git log ff145a9..HEAD` - wykonalne dopiero po 21 |
| martwy kod (20) -> docs (22-24) | 20 < 22 | OK | docs nie moga wymieniac `get_clms_credentials`/`save_credentials_to_keychain`/`DLR_YEARS` |
| blokada sieci (19) vs testy dodane w 1-18 | **plan: 19 po 18** | ryzyko | testy z zadan 1-18 nie sa weryfikowane pod katem sieci az do zad. 19; krok 1 zad. 19 ("dokladnie 20 FAILED") moze pokazac wiecej pozycji - plan ma na to procedure, ale koszt to powrot do zadania zamknietego. Alternatywa: wydzielic sama fixture `_block_network` do mini-zadania przed zad. 2 (P-13) |
| ADR-023 (17) vs ilustracja ADR-023 (25) | 17 < 25 | OK | ten sam akapit pkt 4 - zad. 25 nie moze skasowac zdania z zad. 17 |
| markery pytest (19) vs `[project]` (21) | 19 < 21 | OK | rozne sekcje `pyproject.toml` |

---

## Defekty do rozstrzygniecia

1. **P-1 - Zadanie 5 - BLOKUJACY.** Implementacja `subdir` z deskryptora wywroci ~25
   istniejacych testow. Dowod: `BaseProvider` deklaruje `descriptor_key: str | None = None`
   jako atrybut KLASY (`providers/base.py:21`), wiec `Mock(spec=GugikProvider).descriptor_key`
   zwraca `Mock`, a nie `None` (sprawdzone: `get_source(<Mock>)` -> `KeyError "Nieznane
   zrodlo: '<Mock name=...>'"`). Plan naklada wprost: "`get_source` rzuca `KeyError` dla
   nieznanego klucza - NIE lapac" (l. 372), a fixtury `mock_provider` w
   `tests/test_download_manager.py:134, 243, 358` uzywaja `Mock(spec=GugikProvider)`;
   dotkniete sa takze `tests/test_parallel_download.py:160, 259` i
   `tests/test_integration.py:234` (plik SPOZA listy "Files" zadania, wiec Global Constraint
   (f) kaze przerwac zadanie). **Korekta:** w kroku 3 zamienic warunek na
   `key = getattr(self._provider, "descriptor_key", None); if isinstance(key, str): subdir = get_source(key).storage_subdir`
   i dopisac w "Interfaces", ze mocki providerow maja `descriptor_key` typu `Mock`, wiec
   nie-`str` traktujemy jak brak deskryptora.

2. **P-2 - Zadanie 19 - ISTOTNY.** Fixture `_offline_wms_layers` nie zadziala w opisanej
   postaci z dwoch powodow. (a) Plan proponuje
   `patch.object(GugikProvider, "_fetch_wms_layers", side_effect=lambda self, endpoint, timeout=10: ...)`
   (l. 979) - `patch.object` bez `autospec=True` podstawia `MagicMock`, ktory nie jest
   deskryptorem, wiec wywolanie `self._fetch_wms_layers(endpoint, timeout)` NIE przekazuje
   `self`; istniejacy autouse w `tests/test_gugik_orto.py:31-33` omija ten problem uzywajac
   `return_value`. (b) Plan twierdzi "`GugikOrtoProvider._fetch_wms_layers` (ta sama
   sygnatura)" (l. 976), a w kodzie jest `def _fetch_wms_layers(self, timeout: int = 10)`
   (`gugik_orto.py:134`) wobec `def _fetch_wms_layers(self, wms_endpoint, timeout=10)`
   (`gugik.py:245`). **Korekta:** w "Interfaces" poprawic sygnature orto i zapisac fixture
   jako `side_effect=lambda endpoint, timeout=10: _LAYERS_BY_ENDPOINT[endpoint]` dla
   `GugikProvider` oraz `return_value=list(GugikOrtoProvider.WMS_LAYERS)` dla orto; usunac
   sprzeczne zdanie o "sumie wszystkich list".

3. **P-3 - Zadanie 6 - ISTOTNY.** Uzasadnienie "`default=loam` zostaje dla punktow o sumie 0"
   (l. 498) jest nieprawdziwe: po `_normalize_pct` punkt o sumie 0 ma `(0,0,0)`, a regula 1
   (`silt + 1.5*clay < 15`) jest wtedy PRAWDZIWA, wiec `np.select` zwroci `sand` (HSG A), a
   nie `loam`. Dzis `classify_usda_texture(0,0,0) == "loam"` i `classify_usda_texture_array`
   zwraca `4` (sprawdzone na zywo). W potoku rastrowym maska z zad. 7 to zeruje, ale publiczna
   funkcja skalarna zmienia wynik po cichu. **Korekta:** w kroku 3 dodac jawny guard
   `codes = np.where(total > 0, np.select(...), TEXTURE_CLASSES["loam"])` (albo zwrocic
   `TEXTURE_CLASSES["loam"]` dla `~valid`) i skasowac blednie uzasadniajace zdanie.

4. **P-4 - Zadania 6, 22 (ADR-025, CHANGELOG) - ISTOTNY.** Liczby skutku korekty USDA
   ("~3,4% symplexu ... 136 pkt B->A, 35 pkt B->C, 5 pkt C->D", l. 466 i l. 1050) pochodza z
   `A4-verify.md:136-140` i opisuja porownanie z funkcja SKALARNA. Produkt
   (`calculate_hsg_by_bbox`) uzywa funkcji TABLICOWEJ, dla ktorej przeliczylem symplex co 1%:
   **226 punktow (4,39%) zmienia grupe: 136 A->B, 85 C->B, 5 D->C** (roznice tekstur: 427 z
   5151). Dodatkowo zapis "B->A" czytany wprost sugeruje kierunek odwrotny do faktycznego
   (dzis A, po naprawie B). **Korekta:** w ADR-025 i CHANGELOG podac liczby dla wersji
   tablicowej i kierunek "bylo -> jest" (np. "136 pkt A->B, 85 C->B, 5 D->C; ok. 4,4%
   symplexu"), a liczby skalarne V4 zostawic co najwyzej jako przypis.

5. **P-5 - Zadanie 13 - ISTOTNY.** Zadanie oznaczone `sonnet` wymaga osadu: nowy guard
   `if self._vertical_crs == "EVRF2007": raise ValidationError(...)` w `download_bbox` trafia
   przed dotychczasowe walidacje formatu i CRS, wiec zmienia komunikaty w
   `test_download_bbox_invalid_format` (`tests/test_gugik_provider.py:314`) i
   `test_download_bbox_wrong_crs` (:322); plan mowi ogolnie "istniejace testy
   `TestGugikProviderDownloadBbox` przepiac" bez listy i bez wskazania miejsca guardu.
   Do tego dochodzi przepisanie `test_nmt_1m` "per kanal" i zawezenie `is_wcs_available()`
   (nieuzasadnione zadnym raportem, ale spojne). **Korekta:** zmienic model na `opus` oraz
   dopisac, ze guard EVRF2007 ma stac PO walidacji formatu/CRS, a przepiecia dotycza 7 testow
   klasy `TestGugikProviderDownloadBbox` + `test_is_wcs_available_1m` (l. 113).

6. **P-6 - Zadanie 1, krok 1 - DROBNY.** Asercja jest bledna skladniowo:
   `np.allclose(data[r, :], src.transform * (0.5, r + 0.5))[1]` (l. 115) - indeksuje wynik
   `np.allclose` (skalar `numpy.bool_`), a nie krotke wspolrzednych. **Korekta:** zapisac
   `assert np.allclose(data[r, :], (src.transform * (0.5, r + 0.5))[1])`.

7. **P-7 - Global Constraint (j) - DROBNY.** Lista scope'ow "wg DEVELOPMENT_STANDARDS 2.3"
   (l. 89) jest wymyslona przez plan (sekcja 2.3 podaje PRZYKLADY, nie enumeracje) i przeczy
   komunikatom commitow samego planu: `docs(adr)`, `docs(changelog)`, `docs(readme)`,
   `docs(scope)`, `docs(progress)`, `docs(research)`, `chore(build)`, `test(cli)`,
   `perf(transport)`. **Korekta:** zamienic zdanie na "typ wg 2.2 (feat/fix/docs/test/
   refactor/perf/style/chore); scope = modul albo dokument, ktorego dotyczy zmiana" i usunac
   zamknieta liste.

8. **P-8 - Zadanie 21 - DROBNY.** Ruling i Global Constraint (h) sugeruja, ze
   `pyproject.toml` jest juz zsynchronizowany z `__init__`, a w repozytorium jest
   `version = "0.6.1"` (pyproject.toml:7) wobec `__version__ = "0.7.0-dev"`
   (`kartograf/__init__.py:51`); ponadto `setuptools` NIE jest zainstalowane w `.venv`
   (`ModuleNotFoundError`), wiec krok 3 (instalacja editable + odczyt wersji) i kontrola A6-5
   (`tests` poza wheelem) sa offline niewykonalne. **Korekta:** dopisac w tle zadania
   "dzis pyproject deklaruje 0.6.1 - wersja dynamiczna jednoczesnie naprawia rozjazd (odnotowac
   w CHANGELOG/Changed)" oraz "brak setuptools = krok 3 pominac, przeniesc do Checklisty
   release pkt 4".

9. **P-9 - Zadanie 17 - DROBNY.** Opis `_pl_only_flags` jest wewnetrznie sprzeczny:
   nazywa flagi "`--product <nmpt|orto>`", ale podaje warunek "gdy `product != "nmt"`"
   (l. 918), ktory obejmuje takze `laz`; tymczasem `--product laz` nigdy nie dociera do
   `_dispatch_area`, bo `cmd_download` odsyla go do `_cmd_download_laz`
   (`download_cmd.py:528-529`). **Korekta:** zapisac warunek jako
   `product in ("nmpt", "orto")` i dopisac jedno zdanie, ze LAZ ma wlasny przeplyw.

10. **P-10 - Zadanie 11 - DROBNY.** Fixtura `shp_points_epsg2180` uzywa punktu
    `(420500, 230500)` (l. 683), czyli tego samego obszaru (okolice Opawy w CZ), ktory
    zadania 23/24 usuwaja z README/PRD jako mylacy przyklad "polskiego" bboxa (N6-1);
    sprawdzone: `find_sheets_for_bbox` zwraca dla niego `M-33-84-B-b-3-3`. Test jest
    poprawny (nie pobiera danych), ale utrwala mylacy przyklad. **Korekta:** podmienic
    wspolrzedne fixtury na punkt w Polsce (np. `(530500, 383000)` i `(605000, 495000)`).

11. **P-11 - Zadania 22, 23, 26 - DROBNY.** Trzy zadania niezaleznie wpisuja "liczbe testow
    z ostatniego przebiegu" (l. 1041, 1104, 1160), co da trzy rozne wartosci, jesli kazde
    uruchomi suite osobno. **Korekta:** wskazac jedno zrodlo - "liczba testow i pokrycie z
    przebiegu `pytest --cov` wykonanego na koncu zadania 21; zapisac ja do ledgera i cytowac
    doslownie w 22/23/26".

12. **P-12 - Zadanie 12 - DROBNY.** "Stala eksportowana na poziomie modulu (uzywana tez przez
    `parser_2000`)" (l. 782) nie da sie utrzymac: `_DEGENERATE_EPS` dla PL-1992 jest w
    stopniach (1e-7), a dla PL-2000 w metrach (1e-3), wiec to dwie rozne stale. **Korekta:**
    zapisac dwie nazwane stale (`_DEGENERATE_EPS_DEG` w `sheet_parser.py`,
    `_DEGENERATE_EPS_M` w `parser_2000.py`) i wspoldzielic wylacznie helper `_axis_overlaps`.

13. **P-13 - Kolejnosc (zadanie 19) - DROBNY.** Blokada sieci powstaje dopiero po tym, jak
    zadania 1-18 dopisza kilkadziesiat testow; krok 1 zad. 19 zaklada "dokladnie 20 FAILED",
    a kazdy nowy test siegajacy sieci zmusi do powrotu do zamknietego zadania.
    **Korekta:** przeniesc sama fixture `_block_network` (bez stubu GetCapabilities i bez
    listy 21 testow, ktore do tego czasu beda markowane `real_wms_layers` albo pominiete)
    do osobnego, pierwszego kroku wykonywanego przed zadaniem 2 - albo dopisac do Global
    Constraint (g) wymog "kazdy nowy test uruchomic dodatkowo z `-p no:cacheprovider` i
    odcieta siecia".
