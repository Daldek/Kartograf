# Wybor roku danych — przebieg na zywo i fixtury (Task 8, 2026-10-10)

> **Uwaga (model A, pozniej tego samego dnia):** przebieg T1 nizej (10
> plikow dla `--year 2025`) dotyczy pierwszej wersji semantyki. Po
> przyjeciu modelu A (spec sekcja 0) `--year 2025` daje 4 pliki (jeden lot
> na arkusz, sprawdzone na zywo), a 10 plikow = `--year 2025 --campaigns all`.

Galaz `feat/year-range` (Task 1-7 = `b41197a..7e40c18`). Dane w
`<katalog-danych>/kartograf/2026-10-10-year-range/` (jawne `--output`,
logi `logs/<id>.out|err`). CLI z korzenia repo, `.venv/bin/kartograf`.

## 1. Przebieg CLI (plan Task 8 Step 2)

| Id | Komenda (`kartograf download ...`) | Wynik | Zgodnosc ze specem |
|---|---|---|---|
| T1 | `--bbox 639000,472800,639200,472900 --year 2025` | kod 0, 53 s; "Downloaded 10 campaign files for 4 sheets"; dowiazania na 84183 (-1..-4); `Warning:` E13 (niepelne -1, -2, -3); `Info:` 6.3 dla -1, -2, -3: 84183 pokrycie 41,4 / 61,1 / 78,3 %, 83233 94,6 / 94,5 / 94,6 % | zgodne (T1, T27: -4 bez pomiaru) |
| T1 sidecar | -1: `request.campaigns: "all"`, `year/min_year/max_year: 2025`, `extra.available_years [2019, 2023, 2025]`, `extra.flights` z `coverage`, `extra.better_coverage: "83233"`; -4: `flights` bez `coverage`, bez `better_coverage` | | zgodne (sekcja 7) |
| T5 | jw. `--year 2024` | kod 1; `Error: brak danych z roku 2024 dla 2 z 4 arkuszy — nic nie pobrano:` -1 (2019, 2023, 2025), -3 (2019, 2025); podpowiedz `--min-year 2024 ... albo --max-year 2024 ...`; katalog wyjscia nie powstal | zgodne |
| T16 | jw. `--min-year 2024` | kod 0, 17 s; 4 pliki: -1, -3 = 84183 (2025-10-21), -2, -4 = 83998 (2026-04-05); `Warning:` E13 dla -1, -3; sidecar `request.campaigns: "newest"`, `min_year: 2024`, `available_years` | zgodne (U13) |
| T20 | jw. `--target-crs EPSG:2180` z `--year 2024` / `--min-year 2024` / `--max-year 2024` | kod 1, `Error: <flaga> nie dziala z --target-crs — ...`; nic nie pobrano | zgodne |
| T22 | `--bbox 637200,486900,637500,487100 --product laz --year 2024` | kod 1; `Error: brak kafli LAZ z roku 2024 dla 1 z 1 kafli obszaru — nic nie pobrano:` / `N-34-139-A-c-1-1-3-4 (2025, PL-1992): dostepne roczniki 2022, 2023, 2025`; obie podpowiedzi | zgodne |
| T21a | jw. `--year 2022` | kod 0; pobrane DWA kafle 2022 (`7.173.21.06.1`, `.06.2`, PL-2000:S7) | **rozbieznosc ze specem**, przyczyna w testach — sekcja 3 |
| orto | `N-33-130-D-d-1-4 --product orto --year 2025` | kod 0, 32 s; 2 pliki kampanii (83982 NIE, 83832 TAK), dowiazanie na 83982; `Warning:` E13; bez `Info:` 6.3 | zgodne z 4.4: GeoTIFF orto GUGiK ma 3 kanaly uint8 bez nodata i bez alfy, pokrycie NIEUSTALONE |

## 2. Fixtury (plan Task 8 Step 1, spec 10.3)

Nagrane przez prawdziwe providery (zapytania jak w kodzie), bez edycji:

| Fixture | Wynik | Testy |
|---|---|---|
| orto: dwa loty RGB o tym samym pikselu w roku | N-33-130-D-d-1-4 (Poznan): 2025 = 83982 (0,25 m, NIE) i 83832 (0,25 m, TAK); `tests/fixtures/gugik_skorowidz/real_2026_10_10/orto/` | `test_orto_year_2025_two_rgb_flights_same_pixel_newest_first` |
| LAZ w3: dwa kafle referencji, jeden tylko z nowszymi latami | `627706,479258,628006,479558`: `N-34-138-B-c-4-4-4-4` (2023, 2025), `N-34-138-D-a-2-2-2` (2019); `--year 2019` i `--year 2025` = konflikt na 1 z 2 kafli | `test_w3_year_conflict_on_one_of_two_reference_tiles` (oba kierunki) |
| LAZ Wroclaw: dwie dostawy NIE arkusza w 2025 | `6.150.13.16.4` (84048, 84169), okno 50 x 50 m w srodku arkusza | `test_wroclaw_two_nie_deliveries_of_one_sheet_both_kept`, `test_wroclaw_year_2025_conflict_on_one_of_three_reference_tiles` |
| NMT PL-2000: dwa loty w jednym roku | **nie znaleziono**: 70 losowych arkuszy 1:2000 wokol Warszawy, Krakowa, Wroclawia, Poznania, Gdanska, Lodzi i 42 wokol c14 oraz `6.129.30` (`resolve_campaigns(..., campaigns="all")`); w zadnym roku > 1 lot. Bez testu syntetycznego | — |

## 3. Rozbieznosc T21a: fixtures nagrane dla innego okna

- `tests/fixtures/gugik_laz/real_2026_10_06/w2_*` pochodza z rundy C13
  dla okna `637400,487000,637450,487050` (50 x 50 m), a
  `tests/test_real_gugik_responses.py` i `tests/test_laz_campaigns.py`
  (od `e3d266d`, 2026-10-06) odtwarzaly je dla `W2_BBOX`
  `637200,486900,637500,487100` (300 x 200 m).
- Dla `W2_BBOX` usluga zwraca w 2022 dwa kafle (`7.173.21.06.1` i
  `.06.2`). Sam `.06.2` pokrywa ok. 53 % obszaru, oba razem caly — wedlug
  P8 `--year 2022` to pobranie, nie konflikt. Kod dziala poprawnie, bledny
  byl test T21a i oparte na nim zdania w ADR-032 i ARCHITECTURE 4.7.
- Naprawa: nagranie dla `W2_BBOX` w `tests/fixtures/gugik_laz/real_2026_10_10/`;
  `laz_session` sprawdza parametr `BBOX` zapytania; T21a przepisany na
  "dwa kafle razem pokrywaja referencje"; poprawione oczekiwania dwoch
  testow C13 (`.06.1` w `superseded` i przy `min_density=13`);
  `test_all_still_drops_outside_tiles` jawnie odtwarza odpowiedzi w2 dla
  innego okna (`replay_any_bbox=True`), bo usluga sama odfiltrowuje kafel.
- Ta sama klasa niezgodnosci, poza zakresem: `tests/test_laz_coverage.py`
  (`test_older_tile_adding_uncovered_area_is_kept`,
  `test_tile_whose_footprint_misses_area_is_skipped_as_outside`) i
  5 testow `TestCliOnRealWfs` w `tests/test_laz_download.py` odtwarzaja
  odpowiedzi okna `W2_AREA` dla innych zapytan (godlo, inne okno, inny
  CRS) — wpis w backlogu PROGRESS.

## 4. Uwagi dla uzytkownika

- **Wroclaw `--year 2025`:** `Error:` wymienial kafel referencji 2024 z
  "dostepne roczniki 2019, 2022, 2024, 2025", choc odmawia roku 2025
  (dostawy NIE nie licza sie jako pokrycie). Decyzja uzytkownika
  2026-10-10: dopisek — teraz `2025 (tylko arkusze niepelne)`, sprawdzone
  na zywo (kod 1, nic nie pobrano).
- **Orto i `Info:` 6.3:** pliki orto GUGiK nie maja nodata ani alfy, wiec
  pokrycie orto jest zawsze NIEUSTALONE i komunikat o locie o wiekszym
  pokryciu dla orto sie nie pojawi (czarne wypelnienie = wartosc 0).
