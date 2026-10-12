# Spojnosc CLI, biblioteki i API (2026-10-12)

**Pozycja backlogu:** "Do 0.8.0" -> "Spojnosc CLI, biblioteki i API".
**Kod:** galaz `chore/cli-api-consistency` od `develop` `d5215e8` (0.8.0-dev),
bez zmian kodu. **Metoda:** `kartograf <komenda> --help` kazdej komendy,
`inspect.signature` wszystkich wywolywalnych z `__all__`, lektura torow CLI
(`cli/download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`,
`parse_cmd.py`, `cache_cmd.py`, `commands.py`), parsowanie 67 przykladow CLI
z `README.md`/`docs/USAGE.md`/`docs/ARCHITECTURE.md` przez
`create_parser().parse_args` i sprawdzenie wymaganych flag (bez sieci), smoke
bibliotek z bbox spoza EPSG:2180 (walidacja przed siecia).

## Wynik w skrocie

- Regula 0.8.0 "bez domyslnych wplywajacych na dane" trzyma sie w CLI
  i API (brak `--product`, `--output`, `--vertical-crs`, `--resolution`,
  `--system`, `--scale`, `--source`, `--year` CORINE, `--property`/`--depth`/
  `--stat` = `Error:` z lista wartosci). Wyjatek do decyzji: `stat` HSG (R3).
- Tryby aktualizacji (`--check-updates`/`--upgrade`/`--force`/`--plan`) maja
  odpowiedniki biblioteczne w kazdym torze, ale w czterech roznych ksztaltach
  (R2).
- Logika, ktora istnieje TYLKO w CLI: `--country auto`, rozwiniecie obszaru
  PL na arkusze z walidacja `--system`/`--scale`, `parent_request`,
  `--geometry` dla wycinkow/LAZ/land cover/HSG, przeliczenie `--bbox-crs`
  dla LAZ, arkusze CZ (R1, R4, R5).
- Przyklady CLI w dokumentacji: 67/67 parsuja sie i maja wymagane flagi.
  Przyklady Pythona: jeden zepsuty (`README.md:83`).

## 1. Tabela: mozliwosc -> CLI / biblioteka / `__all__`

Legenda: ✅ zgodne, ⚠️ roznica, ❌ brak.

### 1.1 `kartograf download`

| Mozliwosc | CLI | Biblioteka | `__all__` | Uwagi |
|---|---|---|---|---|
| Arkusz PL (godlo) | `--sheet` | `DownloadManager(...).download_sheet(sheet)` | ✅ | ⚠️ zwraca `Path \| list[Path]`, status w `manager.last_sheet`/`last_result` (R2) |
| Obszar PL -> arkusze | `--bbox/--geometry --country pl --system [--scale]` | `find_sheets_for_bbox(bbox, target_scale, system)` / `find_sheets_for_geometry(...)` + `download_sheets` | ✅ | ⚠️ skala 1:10000 dla PL-1992 i walidacja `--system`/`--scale` tylko w CLI (`download_cmd.py:424-452`, `636`); `parent_request` tylko przez `sidecar_extra` (R5) |
| Kampanie, lata | `--all-campaigns --year --min-year --max-year --full-sheet` | `DownloadManager(all_campaigns=, min_year=, max_year=, full_sheet=)` | ✅ | ⚠️ `year` jest w LAZ (`download_laz_area(year=)`), nie ma go w `DownloadManager` |
| Wycinek PL `--target-crs` | `--bbox --target-crs` | `download_pl_cutout(bbox, target_crs, *, ...)`; kroki `prepare_pl_cutout`/`check_pl_cutout`/`run_pl_wcs_cutout` | ✅ | ⚠️ `target_crs` pozycyjny, w CZ keyword-only; `download_pl_cutout` bez `plan=` (R2) |
| Wycinek CZ | `--country cz --bbox` | `download_cz_cutout(bbox, *, output_dir, target_crs, vertical_crs, resolution)`; `check_cz_cutout(provider, bbox, *, output_dir, image_crs)`, `run_cz_cutout(...)` | ✅ | ⚠️ `target_crs` vs `image_crs`; `check_*` wymaga providera, `download_*` nie; brak `plan=` w `download_cz_cutout` |
| Arkusz CZ SM5/TM33 | `--sheet CTES96` / `302_5550` | `download/cz_sheets.py` `check_cz_sheet`/`run_cz_sheet` | ❌ | tylko CLI (decyzja 9 planu 2/3) (R4) |
| `--country auto` | `--country auto` | `countries_for_bbox`, `split_bbox_by_country` (prymitywy) | ⚠️ | orkiestracja tylko w CLI: `_dispatch_area` (`download_cmd.py:895-1016`), `_pl_only_flags`, `_validate_cross_country`, wartosci `pl=..,cz=..`, kod 0 przy czesciowym sukcesie (R1) |
| LAZ | `--product laz` | `download_laz_area(bbox, *, output_dir, vertical_crs, year, min_density, all_campaigns, min_year, max_year, ...)` | ✅ | ⚠️ biblioteka przyjmuje tylko bbox EPSG:2180 i rzuca `ValueError` (R6); `--sheet`/`--geometry`/`--bbox-crs` przelicza tylko CLI (`_resolve_laz_bbox`) |
| `--geometry`/`--layer` | wszystkie tory | `find_sheets_for_geometry` (tylko arkusze PL) | ⚠️ | obwiednia geometrii `core.geometry.get_overall_bbox` poza `__all__` (R5) |
| `--bbox-crs` | `download` | `BBox(..., crs)` | ⚠️ | przeliczenie `core.bbox.transform_bbox` poza `__all__` (R5) |
| Tryby aktualizacji | `--check-updates/--upgrade/--force/--plan` | `update=` w kazdym torze; plan: patrz R2 | ✅ | ⚠️ `--force` w CLI odswieza tez `MetadataCache` (`_cli_metadata_cache`), `update="force"` w bibliotece nie |
| `--workers` | domyslnie 4 | `max_workers=1` (`DownloadManager`, `download_laz_area`) | ✅ | rozna wartosc domyslna (techniczna, dozwolona) |
| `--quiet` | tak | `on_progress=None` | ✅ | — |

### 1.2 `kartograf landcover download` i `soilgrids hsg`

| Mozliwosc | CLI | Biblioteka | `__all__` | Uwagi |
|---|---|---|---|---|
| Zrodlo | `--source` | `LandCoverManager(output_dir, provider)` | ✅ | — |
| TERYT/bbox/godlo | `--teryt/--bbox/--sheet` | `.download(teryt=, bbox=, sheet=)` | ✅ | ⚠️ CLI `--bbox` tylko EPSG:2180, brak `--bbox-crs` (`landcover_cmd.py:209`, `soilgrids_cmd.py:140`) |
| BDOT10k wiele powiatow | automatycznie dla bbox/godla | `.download_all_counties(...)` / `.check_all_counties(...)` | ✅ (metody klasy) | — |
| BDOT10k warstwy, surowy ZIP | ❌ | `layers=`, `keep_raw=` (`landcover/manager.py:71`) | ✅ | tylko biblioteka (R7) |
| CORINE rok, SoilGrids property/depth/stat | `--year`, `--property/--depth/--stat` | kwargs `.download(...)` walidowane `_check_options` | ✅ | — |
| HSG glebokosc | `--depth` | `calculate_hsg_by_*(depth=)` | ✅ | — |
| HSG statystyka | ❌ zaszyte `mean` (`soilgrids_cmd.py:186`) | `stat=` wymagane | ✅ | ⚠️ R3 |
| HSG z geometrii | `--geometry` | ❌ tylko bbox/godlo | — | R5 |
| Sprawdzenie aktualizacji | `--check-updates` | `.check(...)`, `.check_hsg_by_bbox/sheet(...)` | ✅ | — |
| `--workers`, `--quiet` | ❌ | `download_batch(max_workers=4)` | ✅ | roznica tylko w CLI; do decyzji (R7) |

### 1.3 `parse`, `cache`, inne sposoby uzycia

| Mozliwosc | CLI | Biblioteka | Uwagi |
|---|---|---|---|
| Godlo PL-1992/PL-2000 | `kartograf parse` | `SheetParser`, `Parser2000` | ✅ |
| Godlo CZ (SM5, TM33) | ❌ `parse CTES96` -> `Error: Nieprawidlowe godlo` | `ParserTM33` w `__all__` | ⚠️ `download --sheet` przyjmuje CZ, `parse` nie (R8) |
| Cache | `cache stats/clear/path` | `MetadataCache(db_path, ...)`, `prune_expired()` | ✅ (prune tylko biblioteka; drobne) |
| `python -m kartograf` | ❌ (`No module named kartograf.__main__`) | — | R8 |
| `KARTOGRAF_DEBUG` | traceback w CLI | nie dotyczy | ✅ zgodnie z przeznaczeniem |
| Wyjatki -> kod wyjscia | `KartografError` = `Error:`; inne = `Error: <Typ>: ...` + podpowiedz `KARTOGRAF_DEBUG` (`commands.py:96-108`) | 36 x `raise ValueError`, 122 x `raise ValidationError` | ⚠️ R6 |

## 2. Rozbieznosci (z dowodami)

### R1. `--country auto` istnieje tylko w CLI — niespojnosc, decyzja albo kod

`_dispatch_area` (`cli/download_cmd.py:895-1016`) rozstrzyga kraje
(prostokatne obwiednie), zawęza `auto -> pl` przy flagach tylko PL
(`_pl_only_flags`), waliduje opcje dla kazdego kraju PRZED pobraniem
(`_validate_cross_country`), rozdziela wartosci `pl=..,cz=..`, buduje
`parent_request` i daje kod 0 przy czesciowym sukcesie. Biblioteka ma tylko
`countries_for_bbox` i `split_bbox_by_country`; uzytkownik biblioteki musi
to odtworzyc. Hydrograf korzysta z PL i CZ osobno [INFERENCE: brak wywolan
`auto` w Hydrografie nie sprawdzony w tej sesji].

### R2. Cztery ksztalty wyniku i planu — niespojnosc API (dotyczy 0.8.0)

- Arkusze PL: `download_sheet` zwraca `Path | list[Path]`, statusy wersji
  w atrybutach stanu `manager.last_sheet`/`last_result` (`manager.py:552-553`,
  `819-856`); plan: osobne `check_updates(manager, sheets)` i
  `upgrade(manager, plan)` -> `UpgradeReport`; `download_sheets` nie ma `plan=`.
- Wycinki PL/CZ, LAZ: wynik z `file: VersionedFile`/`files`, `stale`; plan
  tylko w `run_*(plan=)`, NIE w `download_*` (`download_pl_cutout`,
  `download_cz_cutout`, `download_laz_area` bez `plan=`).
- Land cover/HSG: `plan=` bezposrednio w `download(...)`/`calculate_hsg_*`.
- `check_*`: `check_updates(manager, sheets)`, `check_pl_cutout(cutout)`,
  `check_cz_cutout(provider, bbox, *, output_dir, image_crs)`,
  `check_laz_updates(selection, *, provider, output_dir)`,
  `LandCoverManager.check(...)`, `HSGCalculator.check_hsg_by_*(...)`.

Skutek: plik planu z CLI (jeden plan PL+CZ, `run_with_plan_file`
`download_cmd.py:1104-1138`) nie ma jednego wykonawcy w bibliotece; kazdy tor
trzeba wywolac osobno innym API. Arkusze PL to jedyny tor bez wyniku
`VersionedFile` w wartosci zwracanej i ze stanem w obiekcie (nie
watkobezpieczne przy wspoldzielonym menedzerze).

### R3. HSG: `stat` zaszyte w CLI, wymagane w bibliotece — niespojnosc z regula 0.8.0

`soilgrids_cmd.py:186` `stat = "mean"`; `--help` mowi "uzyj statystyki mean".
Biblioteka (`calculate_hsg_by_*`, `check_hsg_by_*`) wymaga `stat=` i przyjmuje
`Q0.05`/`Q0.5`/`Q0.95`/`uncertainty`. Jedno z dwoch jest niespojne z regula:
albo `stat` wybiera wariant danych (wtedy CLI powinno go wymagac), albo HSG ma
sens tylko dla `mean` (wtedy biblioteka nie powinna pytac; parametr "z jedna
dopuszczalna wartoscia").

### R4. Arkusz CZ bez publicznego API — znana decyzja, do zapisania

`check_cz_sheet`/`run_cz_sheet` (`download/cz_sheets.py`) poza `__all__`;
decyzja 9 planu 2/3 magazynu. Nie ma jej w `docs/DECISIONS.md`
[INFERENCE: nie przeszukiwano wszystkich ADR pod tym katem; backlog wymienia
ja jako "do zapisania"].

### R5. Pomocniki uzywane przez CLI poza `__all__`

- `core.geometry.get_overall_bbox` — CLI uzywa go dla `--geometry` w
  wycinkach PL/CZ, LAZ, `landcover download`, `soilgrids hsg`; biblioteka nie
  ma parametru `geometry` w tych torach.
- `core.bbox.transform_bbox` — LAZ, land cover, SoilGrids, CORINE wymagaja
  bbox EPSG:2180; CLI przelicza `--bbox-crs`, biblioteka kaze uzytkownikowi
  zrobic to samemu (komunikat LAZ podpowiada `SheetParser.get_bbox`).
- `parent_request` (`_build_parent_request`, `download_cmd.py:806-823`) —
  format `{"bbox", "bbox_crs", "countries"}` znany tylko CLI; parametry
  `parent_request=` w bibliotece przyjmuja dowolny `dict`. Sidecary z
  biblioteki nie maja `extra.parent_request`, chyba ze uzytkownik zbuduje go
  sam. Land cover buduje go sam (`landcover/manager.py:827-834`).
- Rozwiniecie obszaru PL: PL-1992 zawsze 1:10000 i warunki `--scale` sa
  w `_pl_option_error`/`_pl_target_scale` (CLI); `find_sheets_for_bbox`
  przyjmuje dowolna `target_scale`.

### R6. Bledy walidacji: `ValueError` obok `ValidationError` — blad spojnosci

`ValidationError` NIE dziedziczy z `ValueError` (MRO: `KartografError`,
`Exception`). Ten sam blad wejscia daje rozne typy:

```
download_laz_area(bbox EPSG:4326)            -> ValueError        (nie KartografError)
LandCoverManager(...).download(bbox 4326)    -> ValidationError
HSGCalculator(...).calculate_hsg_by_bbox(...) -> ValidationError
```

36 miejsc `raise ValueError` (najwiecej: `providers/pl/gugik.py` 6,
`landcover/manager.py` 6, `providers/soilgrids.py` 5,
`providers/pl/gugik_laz.py` 5). Uzytkownik lapiacy `KartografError` ich nie
zlapie; w CLI taki blad konczy sie `Error: ValueError: ...` z podpowiedzia
`KARTOGRAF_DEBUG` zamiast zwyklego `Error:`.

### R7. Opcje tylko w bibliotece albo tylko w `download`

- BDOT10k `layers=`, `keep_raw=` — brak flag w `landcover download`.
- `--bbox-crs`, `--workers`, `--quiet` — sa w `download`, brak w
  `landcover download` i `soilgrids hsg`.
- `year` — jest w LAZ, brak w `DownloadManager` (tylko `min_year`/`max_year`).

### R8. `parse` bez godel CZ; brak `python -m kartograf` — drobne

`kartograf parse CTES96` i `parse 302_5550` -> `Error: Nieprawidlowe godlo`,
choc `download --sheet` je przyjmuje, a `ParserTM33` jest w `__all__`.
`python -m kartograf` -> `No module named kartograf.__main__`.

### R9. Jezyk komunikatow i pomocy CLI — brak reguly

STANDARDS 9.4 nie okresla jezyka komunikatow CLI. Stan: pomoc miesza jezyki
w jednej komendzie (`download --help`: `--sheet`, `--bbox`, `--bbox-crs`,
`--quiet`, `--min-density`, `--geometry`, `--workers` po angielsku, reszta po
polsku; `parse`, `cache`, `landcover list-*` po angielsku), bledy tez
(`Error: No sheets found for the given bbox`, `Error: Must provide one of:
...`, `Error: File not found` obok polskich `Error: --system wymagane ...`).
`metavar` `PLIK` przy `--plan`, `DIR`/`FILE` gdzie indziej.

### R10. Dokumentacja

- `README.md:83` `print(result.path)` — `PlCutoutResult` nie ma `path`
  (pola: `file`, `all_nodata`, `masked_pixels`, `zero_pixels`, `stale`);
  ma byc `result.file.path`. BLAD.
- 67 przykladow CLI (`README.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`):
  wszystkie parsuja sie i maja wymagane flagi danych.

## 3. Rekomendacje

| # | Rekomendacja | Kiedy | Uzasadnienie |
|---|---|---|---|
| R10 | Poprawic `README.md:83` na `result.file.path` | teraz | zepsuty przyklad |
| R6 | Bledy danych wejsciowych w publicznych sciezkach: `ValueError` -> `ValidationError` (wariant B, bez dziedziczenia z `ValueError`); bledy wewnetrznych niezmiennikow (np. `campaigns.py:121`, `links.py:212`, `providers/pl/wcs.py:145`) zostaja wbudowane; nieznane argumenty = `TypeError` (konwencja Pythona); usunac obejscia CLI `except ValueError` (`landcover_cmd.py:248`, `download_cmd.py:1054`, `2411`); regula w STANDARDS 11 | 0.8.0 | DECYZJA uzytkownika 2026-10-12: wariant B; jedna hierarchia `KartografError`; wariant A (`ValidationError(KartografError, ValueError)`) zmienilby po cichu ~25 wewnetrznych `except ValueError` (np. `skorowidz.py:153`, `cuzk/sheets.py:258`) |
| R3 | HSG tylko `mean`: usunac `stat` z `calculate_hsg_by_*`/`check_hsg_by_*` (BREAKING w CHANGELOG [0.8.0]) | 0.8.0 | DECYZJA uzytkownika 2026-10-12; parametr z jedna dopuszczalna wartoscia |
| R2 | Ujednolicic tor arkuszy PL: `download_sheet(s)` zwraca obiekt wyniku z `VersionedFile` (jak pozostale tory) i przyjmuje `plan=`; `download_pl_cutout`/`download_cz_cutout`/`download_laz_area` dostaja `plan=`; `check_cz_cutout` przyjmuje `target_crs` jak `download_cz_cutout` | 0.8.0 | 0.8.0 i tak lamie API toru PL (Hydrograf migruje raz); po wydaniu kazda z tych zmian bylaby kolejnym BREAKING |
| R5 | Do `__all__`: `get_overall_bbox`, `transform_bbox`, funkcja budujaca `parent_request`; `find_sheets_for_bbox` z PL-1992 tylko 1:10000 (walidacja w bibliotece, CLI ja woła) | 0.8.0 | CLI nie powinno miec walidacji danych, ktorej nie ma biblioteka |
| R1 | Przeniesc orkiestracje `--country auto` (`_dispatch_area`, `_pl_only_flags`, `_validate_cross_country`, wartosci per kraj, czesciowy sukces) do publicznej funkcji biblioteki; CLI ja wola (R11) | 0.8.0 | decyzja uzytkownika 2026-10-12: zgodnosc zachowania niezaleznie od sposobu uruchomienia, zamiast zapisu "tylko CLI" |
| R4 | Publiczne API arkusza CZ (np. `download_cz_sheet` + `check_cz_sheet` w `__all__`), CLI je wola; errata decyzji 9 planu 2/3 | 0.8.0 | jw. |
| R7 | `landcover download`: `--layers`, `--keep-raw`, `--bbox-crs`, `--workers`, `--quiet`; `soilgrids hsg`: `--bbox-crs`, `--quiet`; `year` w `DownloadManager` | 0.8.0 | DECYZJA uzytkownika 2026-10-12 |
| R9 | `--help`, komunikaty CLI i teksty wyjatkow po polsku, wymuszone ASCII (test); `metavar` jednolicie | 0.8.0 | DECYZJA uzytkownika 2026-10-12 |
| R8 | `parse` z godlami CZ (SM5, TM33); `kartograf/__main__.py` | pozniej | drobne |
| R11 | **CLI tylko tlumaczy:** kazda komenda CLI = zamiana flag na JEDNO wywolanie publicznej funkcji biblioteki + wypisanie jej wyniku (komunikaty, kod wyjscia). W CLI zadnych walidacji ani decyzji o danych (wybor krajow, arkuszy, skali, kampanii, `parent_request`). Kazdy `Warning:`/`Info:` CLI o danych ma pole w wyniku biblioteki (np. `all_nodata`, `stale`, czesciowy sukces krajow). Obejmuje R1, R4, R5 | 0.8.0 | jedno miejsce logiki = jedno zachowanie; dzis `download_cmd.py` (2790 linii) zawiera walidacje i orkiestracje niedostepne w bibliotece |
| R12 | **Jedna polityka cache metadanych:** biblioteka domyslnie uzywa tego samego `MetadataCache` co CLI (ta sama sciezka, TTL); wylaczenie cache jawne; `update="force"` w bibliotece znaczy to samo co `--force` w CLI (takze odswiezenie cache) | 0.8.0 | DECYZJA uzytkownika 2026-10-12 (wariant: biblioteka jak CLI); dzis CLI uzywa `MetadataCache` w cwd (TTL 7 dni), funkcje biblioteki `cache=None`; [INFERENCE] to samo wywolanie moze wybrac inna kampanie w oknie TTL |
| R13 | **Testy zgodnosci CLI = API:** te same scenariusze (arkusz PL, obszar PL, PL-2000, wycinek PL/CZ, arkusz CZ, `--country auto`, LAZ, land cover, HSG, tryby `update`/`--plan`, bledy wejscia) uruchamiane przez `main([...])` i przez publiczne API, offline na fixturach; porownanie plikow, sidecarow (z `parent_request`), statusow wersji, planu i typu bledu | 0.8.0 | bez testu zgodnosc rozjedzie sie przy nastepnej zmianie |

Do naprawy bez decyzji: R10. Kolejnosc: R2 (wspolny ksztalt wyniku i planu
to warunek R11), potem R11 (z R1, R4, R5) i R12; R13 powstaje rownolegle
jako siatka dla calosci. Wszystkie punkty R1-R13 zdecydowane przez
uzytkownika 2026-10-12 (R8 pozniej). Projekt wdrozenia:
`docs/superpowers/specs/2026-10-12-cli-api-consistency-design.md`.
