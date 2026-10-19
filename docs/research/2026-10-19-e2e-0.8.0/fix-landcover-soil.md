# fix-landcover-soil - raport (galaz `fix/e2e-landcover-soil`, od develop @ bef87501)

Brama: `scripts/gate.sh` **zielona** (ruff check, ruff format --check, mypy, pytest offline: 7186 passed, 18 deselected; po ostatniej zmianie testow).
Commity: `1acf3585` (cherry-pick `names_text` z `fix/e2e-collections` a6188d00, patrz uwagi), `66474b6f` (kod + testy), `fe0c7de9` (docs + llms.txt).
Dane zywe: `<katalog-danych>/fix-landcover-soil/{before,after}` (SMB, < 10 MB).

Incydent procesowy: pierwsza edycja `kartograf/providers/soilgrids.py` poszla sciezka WZGLEDNA i trafila w glowny checkout; cofnieta w ciagu sekund
(`git checkout -- kartograf/providers/soilgrids.py` w glownym checkoucie, `git status` czysty, md5 = plik z worktree). Dalej wylacznie sciezki bezwzgledne.

## Znaleziska

| ID | Status | Przyczyna | Zmiana | Testy regresji (`tests/test_landcover_soil_fixes.py`) |
|---|---|---|---|---|
| P2-1 CORINE WMS 2012/2006/2000 | naprawione | `EEA_RASTER_LAYER="12"` tylko w CLC2018; reszta ma `Corine_Land_Cover_<rok>_raster<numer>` | `corine.py`: `_raster_layer_name` (warstwa po tytule `Corine Land Cover <rok> raster` z GetCapabilities uslugi roku), `CorineProvider._eea_raster_layer` (pamiec per provider, nie cache na dysku: numery sie zmieniaja), czytelny blad PL gdy brak warstwy; `_construct_*_wms_url(layer)` | `test_eea_raster_layer_is_read_from_the_capabilities_of_the_year` (4 lata), `..._without_the_raster_layer_...`, `test_getmap_asks_the_layer_of_the_year` |
| P2-2 pusty podglad CORINE | naprawione | brak kontroli tresci PNG | `_is_blank` (rasterio `dataset_mask`, RGBA/GA/paleta, bez `NotGeoreferencedWarning`); `_download_via_wms` -> `NoCoverageError` po pobraniu, PRZED wersja, plik usuniety (wzor true orto; `kind: no_coverage`, kod 1) | `test_fully_transparent_preview_is_no_coverage_and_leaves_no_file` (EEA i DLR) |
| P2-3 SoilGrids ocd/ocs | naprawione | `ocd.map` bez wydania w tytule; `ocs` tylko `ocs_0-30cm_*` | `soilgrids.py`: wydanie `ocd` z mapy `clay` (`_EDITIONLESS_MAPS`, `extra.edition.url/title` wskazuja `clay`); `PROPERTY_DEPTHS={"ocs":["0-30cm"]}`, `depths_for/all_depths/layers/check_layer` (jedno miejsce walidacji: provider i `LandCoverManager._check_options`); `store.py` rozpoznaje segment `ocs_0-30cm_*` | `test_ocs_is_published_at_0_30cm_only`, `test_ocd_edition_comes_from_the_clay_map_its_title_has_none` |
| P2-4 jednostki SoilGrids | naprawione | opisy podawaly jednostki konwencjonalne, plik ma "mapped units" ISRIC | tabela `PROPERTY_UNITS` (ISRIC FAQ <https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html>, sprawdzona z REST `unit_measure` dla cec/cfvo/ocs; uncertainty zweryfikowane liczbowo: = round(10*(Q0.95-Q0.05)/Q0.5), |diff|<=0.5); opisy `--help`/`list-layers` generowane z tej tabeli; sidecar `extra.units={mapped, conventional, divisor}`; `list-layers --json`: `properties[]` = `PropertyInfo` (+`unit, conventional_unit, divisor, depths`), `depths` ma `0-30cm` | `test_values_of_a_file_are_converted_with_the_isric_units`, `test_soil_sidecar_has_the_units_...` |
| P2-6 BDOT10k obszar bez limitu | naprawione | sciezka BDOT10k poza `download/collections.py` | `collections.py`: `within_volume` i `unit_choices` publiczne (rozmiary `HEAD` przez sesje providera), ten sam komunikat limitu; `LandCoverManager._bdot_volume` (biezace paczki; powiat liczony raz mimo `--keep-raw`) i ten sam limit dla archiwum `--year`; `Info` `unit_list` (`names_text`) w `_area_teryts` (takze `--check-updates`) | `test_bdot10k_area_over_the_volume_limit_is_refused_before_any_download`, `..._within_the_limit_downloads_every_powiat` |
| P2-7 BDOT10k `--layers` | naprawione | brakujaca klasa = `DownloadError` powiatu; nieznany kod dopiero po pobraniu | `bdot10k.py`: `BDOT10K_CLASSES` (58 klas rozporzadzenia Dz.U. 2021 poz. 1412 zal. 1; zgodne z paczkami 2463/2472/2476, jedyny wyjatek to literowka GUGiK `OT_BIUB_L`), `normalize_layers` odrzuca nieznany kod PRZED siecia (exit 2, `option=layers`, `allowed`); klasa nieobecna = `Info` `classes_absent` + `extra.source.classes`, brak wszystkich = `NoCoverageError` powiatu (jak BDOO); `Bdot10kPackage.classes/absent` | `test_layers_name_only_classes_...`, `test_class_absent_from_a_powiat_package_...`, `test_absent_class_of_a_powiat_is_an_info_...` |
| P3-06 okno < piksel | naprawione (rozszerzenie) | WCS: HTTP 400 gdy okno < ok. 0,5 piksela (0,001 st. nie, 0,0012 st. tak) | `_at_least_one_pixel` (0,00225 st.) w `download_by_bbox` | `test_window_under_a_pixel_is_widened_not_refused` |
| P3-07 wynik bez danych | naprawione | brak kontroli | SoilGrids: raster samych zer (poza `cfvo`, gdzie 0 to wartosc: zmierzone, Q0.05 cfvo = 0 na 11170 z 11172 pikseli) = `Warning` `all_nodata` + `extra.all_nodata`; HSG bez klasy tak samo | `test_all_zero_raster_is_empty_except_for_cfvo`, `test_soil_sidecar_has_the_units_and_an_empty_raster_is_reported[0/87]` |
| P3-08 zly `CLMS_CREDENTIALS` | naprawione (czesc) | proxy logowal blad tylko do debug, `Info` mowil "wymagaja CLMS_CREDENTIALS" | proxy `/health` zwraca `credentials_error` (tekst bez wartosci), `AuthProxyClient.credentials_problem()`, `CorineProvider.clms_credentials_problem`; manager: `Warning` `corine_preview` z powodem (tylko lata z CLMS). "Proxy request failed" na stderr/`last_error` = FixStderr (nie ruszane) | `test_unusable_clms_credentials_...`, `test_proxy_names_why_the_variable_is_unusable` |
| P3-10 HSG float32 | naprawione | odczyt float32, `/10`, normalizacja przez dzielenie | `_USDA_RULES(c,s,si,u)` porownuja 100 x ilosci z sumami (bez dzielenia), float64; `classify_usda_texture_array` i `_classify_hsg` jeden kod; usuniete martwe `HSGCalculator.CONVERSION_FACTOR` | `test_values_on_a_triangle_boundary_are_classified_by_the_rule[float64/float32]` (wyrocznia na `Fraction`) |
| P3-24 pusty kod | naprawione | `bad=[""]` w komunikacie | `normalize_layers`: "pusty kod warstwy (nadmiarowy przecinek?)" | j.w. |
| P3-04 rok CORINE | naprawione | repr listy | `CorineProvider.check_year`: `--year 2019: niedostepne dla --product corine; dostepne: 2018, 2012, ...` (`option=year`) | `test_corine_year_error_lists_the_years_with_the_flag` |
| P3-16 list-layers BDOT10k | naprawione | lista 15 vs 58-70 tabel | `list-layers --product bdot10k` = wszystkie 58 klas (= wartosci `--layers`) + notka; poprawiony tez opis `PTWZ` ("Wyrobiska i zwalowiska", bylo "Tereny zabagnione") | `test_list_layers_bdot10k`, `test_available_layers` |
| P3-01 llms.txt | naprawione | brak `--product` | `llms.txt`: `list-layers --product bdoo --json` i `soil list-layers --json` | `test_offline_query_commands_of_llms_txt_run` (uruchamia offline polecenia `list-*` z llms.txt) |

## Dowody na zywo (przed -> po)
- CORINE 2012 arkusz N-34-130-D-d-2-4: przed exit 1 (`LayerNotDefined`), po exit 0, PNG zapisany.
- CORINE 2018 Kijow (poza CLC): przed exit 0 + pusta wersja `d0f7eebe`, po exit 1 `no_coverage`, brak wersji.
- SoilGrids `ocd` 0-5cm (bbox 19.50,52.00,19.52,52.02): przed exit 1 (brak wydania), po exit 0, wydanie 2.0, `extra.units={hg/m3,kg/m3,10}`; `ocs` 0-5cm exit 2 (czytelny, `Dostepne dla ocs: 0-30cm`), `ocs` 0-30cm exit 0.
- SoilGrids okno 10 m: exit 0 (+`Warning all_nodata`; poprzednio HTTP 400); Baltyk: `Warning all_nodata`.
- BDOT10k Sopot `--teryt 2264 --layers SWKN,PTWP`: przed exit 1, po exit 0 + `Info: bdot10k PL 2264: paczka nie ma plikow klas SWKN ...; zapisano klasy PTWP`; `--layers XXXX` exit 2 bez sieci; `--layers "SWRS,"` exit 2 "pusty kod warstwy".
- NIE zweryfikowane na zywo: (a) CLC1990 dla PL (DLR WMS odpowiada HTTP 502 przez caly czas sesji; sciezka DLR pokryta testem offline), (b) limit BDOT10k na prawdziwym obszarze calej Polski - PRG WFS odpowiada teraz HTTP 400 na duze BBOX (takze `--check-updates`), wiec limit sprawdzony tylko offline (101 powiatow, `HEAD` 48 MB, brak pobrania); (c) CLMS GeoTIFF (brak poswiadczen) - kontrola pustego obrazu dotyczy tylko podgladu WMS.

## Dokumentacja
USAGE 1.5 (CORINE/SoilGrids/BDOT10k), 1.8 (limit obejmuje BDOT10k), 5 (jednostki, ocs, okno), 7 (all_nodata); PRD 3.5 (58 klas), 3.6 (lata WMS), 3.7 (tabela jednostek); ARCHITECTURE 4.8 (sygnal SoilGrids/ocd, podglad, units, BDOT10k limit i klasy); `--help`/`list-layers`/katalog generowane z kodu; `llms.txt`.
Nie edytowane (wg zasad): CHANGELOG, PROGRESS, DECISIONS.

## Propozycja wpisu CHANGELOG (sekcja nadchodzacego wydania, ASCII)
- CORINE: podglad WMS dziala dla 2012, 2006 i 2000 (warstwa rastrowa roku z GetCapabilities uslugi EEA; dotad `LayerNotDefined`); obraz w calosci przezroczysty (np. 1990 dla Polski, obszar poza Europa) to `no_coverage` bez zapisu wersji; blad roku z nazwa flagi; `Warning` gdy `CLMS_CREDENTIALS` jest ustawione, ale nieuzywalne (powod z proxy).
- SoilGrids: `--property ocd` dziala (wydanie z mapy clay), `ocs` tylko `--depth 0-30cm` (czytelny blad dla innych glebokosci); jednostki wartosci w plikach (ISRIC "mapped units": clay g/kg, phh2o pH x 10, bdod cg/cm3, soc dg/kg, nitrogen cg/kg, cec mmol(c)/kg, cfvo cm3/dm3, ocd hg/m3, ocs t/ha) w `--help`, `soil list-layers` i sidecarze `extra.units` (`mapped`, `conventional`, `divisor`; dodatek do `kartograf-meta/1`); okno mniejsze niz piksel rozszerzane do jednego piksela; raster samych zer (poza cfvo) to `Warning` `all_nodata` i `extra.all_nodata`.
- HSG: klasyfikacja trojkata USDA bez zaokraglen (wartosci na granicach g/kg wg regul, nie wg float32); HSG bez zadnej klasy to `Warning` `all_nodata`.
- BDOT10k: obszar wypisuje liste powiatow (`Info` `unit_list`) i podlega limitowi 100 plikow / 10 GB jak kolekcje (takze archiwum `--year`); `--layers`: 58 klas BDOT10k (`landcover list-layers --product bdot10k`), nieznany lub pusty kod = blad przed siecia, klasa bez obiektow w powiecie = `Info` `classes_absent` (jak BDOO), brak wszystkich = blad powiatu; `Bdot10kPackage.classes/absent`, `extra.source.classes`; poprawiony opis klasy PTWZ.
- `llms.txt`: poprawiony przyklad `landcover list-layers` (wymaga `--product`).

## Erraty ADR (propozycja)
- ADR-044/045 (sidecar land cover/soil): `extra.units` i `extra.all_nodata` dla SoilGrids; `extra.source.classes` dla BDOT10k z `--layers`.
- ADR-043 errata 3 (limit obszaru): obejmuje biezace paczki i archiwum BDOT10k (`within_volume` publiczne).

## Decyzje do potwierdzenia
1. Wydanie `ocd` = wydanie mapy `clay` (ISRIC nie podaje wydania w `ocd.map`; dokumentacja ISRIC liczy ocd do 2.0). Alternatywa: sygnal `none` dla `ocd` (etykieta = data).
2. Lista klas BDOT10k z rozporzadzenia 2021 (58) jest zrodlem walidacji; klasy spoza listy w niektorych paczkach (jak literowka `BIUB`) nie sa wybieralne przez `--layers`.
3. Okno < piksel jest rozszerzane (nie bledem); `cfvo` wylaczone z `all_nodata`.

## Uwagi do integracji
- `1acf3585` to cherry-pick `a6188d00` (FixCollections, `notices.names_text`) - identyczna tresc, merge bez konfliktu; uzywam jej w `unit_list` BDOT10k.
- Pliki wspolne: `tests/conftest.py` (autouse `_offline_package_sizes`: HEAD limitu obszaru BDOT10k bez sieci; `FakeCorine` odpowiada na GetCapabilities), `download/collections.py` (tylko pomoc limitu i jedno wywolanie w `run_request`), `auth/client.py` (tylko `is_available`/`credentials_problem`, bez `proxy_request`/`last_error` FixStderr), `providers/pl/bdot10k.py` (tylko blok `layers` w `_extract_gpkg_from_zip`; petle FixCancel nietkniete), `store.py` (rozpoznanie segmentu soil).
- Nie ruszane (poza slice): P2-5 (Ctrl-C), P2-8 (bbox CRS - FixPlSheets), P3-23/P3-25.
