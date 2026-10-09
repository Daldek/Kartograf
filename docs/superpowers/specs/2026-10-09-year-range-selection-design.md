# Spec: Wybor roku danych — `--year`, `--min-year`, `--max-year` (NMT, NMPT, orto, LAZ)

**Data:** 2026-10-09
**Status:** projekt do review uzytkownika; decyzje uzytkownika z 2026-10-09
(sekcja 2) sa wiazace, pozostale rozstrzygniecia (sekcja 3) i pytania
otwarte (sekcja 12) czekaja na akceptacje
**Wersja docelowa:** 0.7.1 (galaz `feat/hydrograf-0.7.1`, przed tagiem)
**Dokumenty zrodlowe:**
- ADR-028 (wybor rekordu skorowidza: twardy filtr + najnowsza
  `(aktualnosc, dt_pzgik, url)`, bez preferencji pelnego arkusza)
- ADR-029 (LAZ: zachlanny wybor kafli wg pokrycia obszaru od najnowszego
  `akt_rok`) + errata 1
- ADR-030 (strategie `newest`/`all`, `--min-year`, `kampanie/`, cache
  `campaigns_cache`) + erraty 1-6; w szczegolnosci (f), (g), (h), (i), (j),
  errata 1 [Q2], [Q5], [Q9], errata 2 [N-3], errata 3 (CZ bez kampanii),
  errata 5 (I-1: skorowidz niedostepny)
- `docs/ARCHITECTURE.md` 3.2 (sidecar), 4.1 (godlo PL), 4.3 (wycinek PL),
  4.6 (`--country auto`), 4.7 (LAZ)
- surowe odpowiedzi GUGiK: `tests/fixtures/gugik_skorowidz/real_2026_10_06/`,
  `tests/fixtures/gugik_laz/real_2026_10_06/`

---

## 1. Kontekst i cel

### 1.1 Blad: `--year` jest po cichu ignorowany poza LAZ

`kartograf download --year RRRR` jest dzis zdefiniowany jako opcja "LAZ only"
(`kartograf/cli/_parser.py:263-269`) i czytany w jednym miejscu —
`_cmd_download_laz` (`kartograf/cli/download_cmd.py:1801`,
`getattr(args, "year", None)`). Dla `--product nmt|nmpt|orto` flaga
przechodzi parser bez bledu, nie trafia do `_campaign_opts`
(`download_cmd.py:230-232` czyta tylko `campaigns` i `min_year`), nie trafia
do `DownloadManager` ani do sidecara. Uzytkownik, ktory pisze
`kartograf download N-34-139-C-a-3-1 --year 2023`, dostaje najnowsza
kampanie (2025) bez slowa ostrzezenia — cicha degradacja, ktorej ADR-028
zabrania w kazdej innej postaci.

### 1.2 Dzisiejsza semantyka roku (pomiar w kodzie)

| Element | Dzis | Gdzie |
|---|---|---|
| Rok rekordu NMT/NMPT/orto | `aktualnoscRok`, a bez niego `aktualnosc[:4]`; nieustalony = `None` | `providers/pl/skorowidz.py:381-385` (`_record_year`) |
| Rok kafla LAZ | `akt_rok` z WFS | `providers/pl/gugik_laz.py:764-765` |
| `--min-year` NMT/NMPT/orto, `newest` | rekord ADR-028 (`record_cache`); gdy jego rok < granicy: `NoCoverageError` "Najnowsza kampania ... starsza niz min_year" — w trybie listy arkusz POMINIETY z `Warning:` (R5), kod 0, gdy inne arkusze sie pobraly | `skorowidz.py:686-694`, `cli/download_cmd.py:1162-1249` |
| `--min-year` NMT/NMPT/orto, `all` | warstwy o gornym roku z nazwy < granicy nie sa odpytywane (skan czesciowy, `scanned_from` w `campaigns_cache`); rekordy filtrowane po `aktualnosc`; brak = `NoCoverageError` "Brak kampanii ... od roku" | `skorowidz.py:564-706` |
| `--year` LAZ | tylko rocznik Y (warstwa WFS `...LIDAR<Y>`); rocznik nieobecny w usludze = `DownloadError`; brak kafli = `NoCoverageError` / `Error: No LAZ tiles found`; obszar pokryty rocznikiem Y tylko czesciowo = cicho pobrane to, co jest | `gugik_laz.py:652-674`, `download/laz.py:47-50,320` |
| `--min-year` LAZ | roczniki < granicy nie sa odpytywane; wyklucza sie z `--year` | `gugik_laz.py:637-660` |
| Sidecar | `request.min_year` gdy podany; LAZ `request.year` gdy podany | `download/manager.py:1213-1240`, `download/laz.py:115-122` |
| CZ | opcje kampanii (`all`, `--min-year`): bez PL = `Error:`, PL+CZ pod `auto` = `Info:` (CZ biezaca wersja) | `download_cmd.py:235-266`, ADR-030 (j), errata 2 [N-3], errata 3 |
| Wycinek `--target-crs` | `--campaigns all` i `--min-year` = `Error:` przed siecia (nazwa wycinka nie niesie roku) | `download_cmd.py:269-297`, ADR-030 errata 1 [Q2] |

### 1.3 Cel

1. `--year RRRR` dziala tak samo dla NMT, NMPT, orto i LAZ: pobiera WYLACZNIE
   rok RRRR, a gdy ktorys arkusz/kafel ma dane tylko z innych lat —
   zatrzymuje zadanie przed jakimkolwiek pobraniem i mowi, jakie lata sa.
2. Nowa flaga `--max-year RRRR`, symetryczna do `--min-year`; `--year Y`
   jest skrotem `--min-year Y --max-year Y`, a para min+max to przedzial.
3. Ta sama semantyka w bibliotece (`DownloadManager`, `download_pl_cutout`,
   `download_laz_area`, `GugikLazProvider.select_tiles`,
   `resolve_campaigns`): nowy parametr `max_year=`, wyjatek z listy
   dostepnych lat per arkusz.
4. Wybrany rok i kampania (lot) trafiaja do sidecara.

Poza zakresem: skladanie kampanii w jedna powierzchnie (SCOPE 3.1), kampanie
dla CZ (ADR-030 errata 3), land cover (`--year` CORINE to inna flaga innej
komendy — `_parser.py:356-359`, bez zmian).

## 2. Decyzje uzytkownika (2026-10-09, wiazace)

| # | Decyzja |
|---|---|
| U1 | `--year RRRR` jest honorowany dla NMT, NMPT, orto i LAZ — JEDNO zachowanie dla czterech produktow. |
| U2 | `--year Y` pobiera wylacznie rok Y. Warunek: kazdy arkusz/kafel zadania ma dane z roku Y. |
| U3 | Arkusz/kafel bez ZADNYCH danych (zaden rok; np. poza granica kraju) = pominiety z czytelnym `Warning:`. |
| U4 | Arkusz/kafel z danymi tylko z INNYCH lat = zatrzymanie przed pobraniem czegokolwiek; lista dostepnych lat per arkusz; podpowiedz `--min-year Y`, gdy sa lata nowsze (Y i nowsze), oraz `--max-year Y`, gdy sa tylko starsze (Y i starsze = najnowszy nie pozniejszy niz Y). |
| U5 | Nowa flaga `--max-year`, symetryczna do `--min-year`; `--year Y` == `--min-year Y --max-year Y`; min+max = przedzial lat. |
| U6 | Najpierw sprawdzenie wszystkich arkuszy, potem pobieranie (zadnego wyniku czesciowego po zatrzymaniu). Wybrany rok trafia do sidecara. |
| U7 | (uzupelnienie 2026-10-09) Spec ma jawnie opisac przypadek DWOCH LUB WIECEJ kampanii (lotow) tego samego arkusza/kafla w JEDNYM roku: co jest dzis, co wybiera `--year`/`--min-year`/`--max-year`, jak dziala `--campaigns all`, co mowi sidecar, czy uzytkownik jest informowany. |

## 3. Rozstrzygniecia projektowe (do akceptacji)

| # | Rozstrzygniecie | Uzasadnienie |
|---|---|---|
| P1 | **Jeden mechanizm = przedzial `[min_year, max_year]`.** Regula "sprawdz wszystko, potem pobierz; konflikt = stop" (U4, U6) obowiazuje dla KAZDEGO przedzialu: `--year`, samo `--min-year`, samo `--max-year`, para. | U5 mowi, ze `--year Y` to `--min-year Y --max-year Y`; gdyby `--min-year` zachowal dzisiejsze "pomin arkusz z `Warning:`", to `--year Y` i `--min-year Y --max-year Y` roznilyby sie zachowaniem — sprzecznosc z U5. Zmiana zachowania `--min-year` opisana w CHANGELOG (sekcja 11). Pytanie otwarte Q1. |
| P2 | **Rok rekordu bez zmian:** NMT/NMPT/orto = `aktualnoscRok`, inaczej `aktualnosc[:4]` (`_record_year`); LAZ = `akt_rok`. Rekord bez ustalonego roku nie spelnia zadnego przedzialu (jak dzis dla `min_year`). | ADR-030 (f): 1381 rekordow — `aktualnoscRok` zawsze zgodny z `aktualnosc`; pomiar 2026-10-09 na fixtures `real_2026_10_06` (NMT, NMPT, orto; 44 pary arkusz/wariant): zero rozbieznosci. `dt_pzgik` (data przyjecia do PZGiK) NIE jest rokiem danych — roznica siega roku (2025-10-21 -> 2026-07-10). |
| P3 | **Wybor w przedziale = ADR-028 zawezone do przedzialu.** `newest`: najnowsza kampania (klucz `(aktualnosc, dt_pzgik, url)`) sposrod rekordow z rokiem w przedziale; `all`: wszystkie rekordy twardego filtru z rokiem w przedziale. Bez preferencji pelnego arkusza. | Regula wyboru ADR-028 pozostaje jedyna; przedzial jest tylko dodatkowym twardym filtrem. Pytanie otwarte Q2 (preferencja pelnego arkusza w roku). |
| P4 | **Dwa loty w jednym roku (U7):** `newest` wybiera najnowszy `aktualnosc` w tym roku (P3); `all` pobiera wszystkie loty z przedzialu; sidecar identyfikuje lot (`extra.campaign`, istniejace) i wymienia pozostale loty z przedzialu (`extra.alternatives`, nowe) oraz wszystkie lata arkusza (`extra.available_years`, nowe); CLI drukuje `Info:` o arkuszach z wieloma lotami w wybranym roku (sekcja 6.3). | Pomiar (sekcja 4.3): dwa-trzy loty w jednym roku to w realnych danych norma, nie wyjatek; uzytkownik proszacy o "rok 2025" musi wiedziec, ktory lot dostal i ze byl inny. |
| P5 | **Sprawdzenie wymaga PELNEJ listy kampanii arkusza** (wszystkie warstwy skorowidza), nie najnowszego rekordu z `record_cache`. Przy jakimkolwiek przedziale `newest` korzysta z `campaigns_cache` (lista), a nie z `record_cache`. Skan czesciowy (`scanned_from`, pomijanie warstw o gornym roku z nazwy < `min_year`) jest USUWANY: lista jest zawsze pelna. | Komunikat U4 ma wymienic WSZYSTKIE dostepne lata arkusza — po skanie czesciowym lata starsze od granicy sa nieznane. Gorny rok z nazwy warstwy nie pozwala pominac warstwy dla `max_year` (`2023iStarsze` zawiera wszystko starsze). Koszt: dla NMT EVRF2007 4 warstwy zamiast 1-3 zapytan GetFeatureInfo per arkusz, raz na 7 dni (TTL). Pytanie otwarte Q6. |
| P6 | **Wycinek `--target-crs` (ADR-027) przyjmuje przedzial lat.** Wynik dostaje sufiks `_y<min>-<max>` (albo `_y<rok>` gdy min == max, `_y<min>-` / `_y-<max>` dla polotwartego) w nazwie pliku `bbox/<coords>_y2024.tif`; sidecar wycinka niesie `request.min_year`/`max_year`(/`year`) i `extra.sheet_sources` jak dotad. `--campaigns all` z wycinkiem = `Error:` bez zmian. | Powod odrzucenia `--min-year` w errata 1 [Q2] (nazwa wycinka nie niesie roku, wiec drugi rok bylby pominiety jako istniejacy) znika z sufiksem. Wycinek i tak sklada arkusze przez `DownloadManager.download_sheets` (`download/cutout.py:760-779`), wiec mechanika P1 przychodzi za darmo. Pytanie otwarte Q3. |
| P7 | **CZ / `--country auto`:** `--year`, `--min-year`, `--max-year` to opcje kampanii PL — ta sama straz co dzis dla `--campaigns all`/`--min-year` (`_reject_campaign_opts_without_pl`): zadanie bez PL = `Error:`, kod 1; obszar PL+CZ pod `auto` = `Info:` raz, CZ pobierany w biezacej wersji; flagi roku NIE wchodza do `_pl_only_flags` (nie zawezaja `auto` do PL). | CUZK nie ma archiwum (ADR-030 errata 3) — roku nie da sie uszanowac; ciche zignorowanie dla CZ powtorzyloby blad z 1.1; odrzucenie calego zadania granicznego zlamaloby ADR-023 pkt 5 (zadanie PL+CZ ma dzialac). Spojne z (j), [Q9], [N-3]. |
| P8 | **LAZ: "kafel zadania" = kafel wyboru referencyjnego.** Wybor referencyjny R = `select_newest_cover` po WSZYSTKICH rocznikach uslugi (z `--min-density`, `--vertical-crs`), czyli to, co uzytkownik dostalby bez flag roku. Kafel R o roku spoza przedzialu musi miec swoja czesc wspolna z obszarem pokryta kaflami z przedzialu (ta sama regula pokrycia co ADR-029, tolerancja 1 m); inaczej konflikt (U4) z latami kafli, ktorych rama przecina niepokryty kawalek. Czesc obszaru bez kafli w zadnym roku = jak dzis (bez ostrzezenia: obszar LAZ nie jest lista arkuszy). | Kafle roznych rocznikow maja rozne godla (PL-1992 vs PL-2000, inne ciecie), wiec "ten sam kafel w innym roku" da sie zdefiniowac tylko przez pokrycie; maszyneria (`select_newest_cover`, `uncovered_pieces`) juz istnieje. |
| P9 | **Awaria skorowidza/WFS w fazie sprawdzania = przerwanie calego zadania** (`DownloadError`, kod 1, lista arkuszy, ktorych nie dalo sie sprawdzic), bez pobierania. Fallback I-1 (lokalna kampania bez sprawdzenia) dziala wylacznie bez flag roku — jak dzis bez `--min-year` (ADR-030 errata 5). | U6: warunek "kazdy arkusz ma rok Y" nie jest sprawdzalny bez odpowiedzi skorowidza; pobranie reszty byloby wynikiem czesciowym. Pytanie otwarte Q5. |
| P10 | **Kombinacje flag:** `--year` z `--min-year` albo `--max-year` = `Error:` (CLI) / `ValidationError` (biblioteka: `year=` tylko w LAZ, patrz 8.3); `--min-year > --max-year` = blad; zakres 1900..2100 jak dzis. | `--year` jest skrotem; laczenie skrotu z granica jest albo redundantne, albo sprzeczne — jawny blad zamiast zgadywania. |

## 4. Definicje i fakty zmierzone

### 4.1 Rok danych

- **NMT, NMPT, orto:** `rok(rekord)` = `int(aktualnoscRok)`, a gdy pola brak —
  `int(aktualnosc[:4])`; niecyfrowe = `None` (`skorowidz.py:381-385`).
  Orto ma te same pola (`aktualnosc`, `aktualnoscRok`, `dt_pzgik`; brak
  `format` i pionu) i te sama semantyke; warianty CIR/B-W sa osobnym
  twardym filtrem (`kolor`, `gugik_orto.py:197-205`) — rok jest liczony w
  obrebie wariantu.
- **LAZ:** `rok(kafel)` = `akt_rok` (`gugik_laz.py:764-765`); `akt_data`
  (`LazTile.date`) rozstrzyga kolejnosc w roku (ADR-029).
- **Przedzial:** `[min_year, max_year]`, obie granice domkniete, kazda
  opcjonalna; `year=Y` == `[Y, Y]`. Rekord/kafel "w przedziale" =
  `rok` nie `None` i `min_year <= rok <= max_year`.

### 4.2 Lata arkusza i klasyfikacja

Dla arkusza (NMT/NMPT/orto) albo kafla referencyjnego (LAZ):

- `lata(arkusz)` = posortowany zbior `rok(rekord)` po rekordach twardego
  filtru ADR-028 ze WSZYSTKICH warstw skorowidza (lista jak
  `select_campaign_records`, `skorowidz.py:282-305`).
- Klasy:
  - **OK** — co najmniej jeden rekord w przedziale;
  - **BRAK** — `lata(arkusz)` puste (dzis `NoCoverageError` z podpowiedziami
    `coverage_hints`, `skorowidz.py:813-844`) — U3: pominiety z `Warning:`;
  - **KONFLIKT** — `lata(arkusz)` niepuste, zaden rok w przedziale — U4: stop.

### 4.3 Wiele kampanii (lotow) w jednym roku — pomiar 2026-10-09

Skrypt pomiaru przeszedl wszystkie surowe odpowiedzi z
`tests/fixtures/gugik_skorowidz/real_2026_10_06/` przez
`parse_skorowidz_records` i pogrupowal rekordy po (arkusz, wariant, uklad,
rozdzielczosc, rok). Wynik — ten sam arkusz, ta sama rozdzielczosc i pion,
rozne `aktualnosc` w jednym roku:

| Produkt | Arkusz | Rok | Loty (`aktualnosc` / id kampanii / pelny arkusz) |
|---|---|---|---|
| NMT 1 m EVRF2007 | N-34-139-C-a-3-1 | 2025 | 2025-04-27 / 83233 / TAK; 2025-10-21 / 84183 / NIE |
| NMT 1 m EVRF2007 | N-34-139-C-a-3-2 | 2025 | 2025-04-04 / 81468 / TAK; 2025-04-27 / 83233 / TAK; 2025-10-21 / 84183 / NIE |
| NMT 1 m EVRF2007 | N-34-139-C-a-3-3 | 2025 | 2025-04-27 / 83233 / TAK; 2025-10-21 / 84183 / NIE |
| NMT 1 m EVRF2007 | N-34-139-C-a-3-4 | 2025 | 2025-04-04 / 81468 / TAK; 2025-04-27 / 83233 / TAK; 2025-10-21 / 84183 / TAK |
| NMT 1 m EVRF2007 | N-33-69-A-d-3-2 | 2024 | 2024-07-21 / 81616 / TAK; 2024-09-23 / 81025 / TAK |
| NMT 1 m EVRF2007 | M-33-57-C-b-4-2 | 2021 | 2021-09-09 / 75115 / TAK; 2021-10-09 / 75079 / TAK |
| NMT 1 m EVRF2007 | M-34-63-A-c-2-1 | 2021 | 2021-04-10 / 74189 / TAK; 2021-05-12 / 74949 / TAK |
| NMPT EVRF2007 | N-33-77-A-d-2-2 | 2024 | 2024-08-29 / 84005 / NIE; 2024-09-21 / 80195 / TAK |

Orto: w fixtures rekordy tego samego arkusza i roku roznia sie wylacznie
wielkoscia piksela (np. N-34-139-A-c-1-1 RGB 2024: 0,25 m; 7.173.21.01 RGB
2020 i 2021: 0,05 m obok 0,25 m z 2017) — to warianty rozdzielczosci, nie
loty; orto nie filtruje rozdzielczosci (ADR-028), wiec dla `--year` sa jedna
pula i wygrywa najnowszy `aktualnosc`. Prawdziwych dwoch lotow orto w jednym
roku o tej samej wielkosci piksela fixtures nie zawieraja (do nagrania,
sekcja 10.3).

LAZ: obszar w2 (`tests/fixtures/gugik_laz/real_2026_10_06/`) ma po JEDNYM
kaflu na rocznik (EVRF2007: 2022 PL-2000:S7, 2023 i 2025 PL-1992 to samo
godlo; KRON86: 2012, 2018). ADR-029 odnotowuje realny przypadek dwoch
dostaw NIE (arkusz niepelny) tego samego arkusza w 2025 (Wroclaw) —
fixture do nagrania (sekcja 10.3).

**Jak to dziala dzis:**

- ADR-028 (`newest`): wygrywa maksimum `(aktualnosc, dt_pzgik, url)` — dla
  N-34-139-C-a-3-1 jest to lot 2025-10-21 / 84183, NIEPELNY
  (`tests/test_real_gugik_responses.py:380-401` to przypina); CLI drukuje
  `Warning:` E13 o niepelnym arkuszu (`_warn_sheet_sidecars`).
- ADR-030 (c): tozsamosc kampanii `<aktualnosc>_<id>` — dwa loty w roku to
  dwa katalogi `kampanie/2025-04-27_83233/` i `kampanie/2025-10-21_84183/`;
  `test_same_date_different_id_distinct_dirs_and_order`
  (`tests/test_campaigns.py:185`) pokrywa nawet te sama date z innym id.
- `--campaigns all`: oba loty pobrane; dowiazanie na najnowszy
  (`manager.py:826-838`).
- LAZ (ADR-029): w roku kolejnosc `akt_data` malejaco, potem gestosc; kafel
  niepelny (`czy_ark_wypelniony = NIE`) nie pokrywa, wiec dwie dostawy NIE
  tego samego arkusza zostaja obie (`gugik_laz.py:187-196, 283-327`).

**Decyzja dla przedzialu (P3, P4):** w roku wybiera ten sam klucz co ADR-028
(najnowszy `aktualnosc`), `all` bierze wszystkie loty z przedzialu, LAZ bez
zmian w regule ADR-029. Uzytkownik dowiaduje sie o pozostalych lotach z
`Info:` (6.3) i z sidecara (sekcja 7).

## 5. Tabela decyzyjna

Przyklady na realnych arkuszach z fixtures (sekcja 4.3; N-34-139-C-a-3-1 ma
lata 2019, 2023, 2025; -2: 2019, 2022, 2023, 2024, 2025, 2026; -3: 2019,
2025; -4: 2019, 2022, 2023, 2024, 2025, 2026). "Lista" = 4 arkusze
N-34-139-C-a-3-{1..4} z `--bbox`/`--geometry`/hierarchii.

| # | Przypadek | Przyklad | Wynik |
|---|---|---|---|
| T1 | Wszystkie arkusze maja rok Y | lista, `--year 2025` | pobranie 4 arkuszy, kazdy najnowszy lot z 2025 (-1: 84183 niepelny, -2: 84183 niepelny, -3: 84183 niepelny, -4: 84183 pelny); `Info:` o wielu lotach (6.3); `Warning:` E13 o niepelnych; kod 0 |
| T2 | Czesc arkuszy bez ZADNYCH danych | lista + arkusz morski, `--year 2025` | arkusz morski pominiety: `Warning: GUGiK nie ma danych dla 1 z 5 arkuszy (...) — pominiete (morze, obszar za granica)` (istniejacy R5), reszta jak T1, kod 0 |
| T3 | Arkusz ma dane tylko z lat NOWSZYCH | pojedynczy -2 z `--year 2018` (lata 2019..2026) | `Error:` (6.2) z `dostepne roczniki 2019, 2022, 2023, 2024, 2025, 2026`; podpowiedz `--min-year 2018` (rok 2018 i nowsze); kod 1; nic nie pobrano |
| T4 | Arkusz ma dane tylko z lat STARSZYCH | -1 z `--year 2026` (lata 2019, 2023, 2025) | `Error:` z lista lat; podpowiedz `--max-year 2026`; kod 1 |
| T5 | Jeden arkusz ma lata starsze I nowsze, zadnego w Y | lista, `--year 2024`: -2 i -4 OK (2024), -1 (2019, 2023, 2025) i -3 (2019, 2025) KONFLIKT | `Error:` wymienia -1 i -3 z ich latami; podpowiedz OBIE: `--min-year 2024` (2024 i nowsze) i `--max-year 2024` (2024 i starsze); kod 1; nic nie pobrano (takze -2 i -4) |
| T6 | Mieszanka: jeden arkusz tylko nowsze, inny tylko starsze | lista {-1, -3, -4} z `--year 2026`: -4 OK; -1 i -3 tylko starsze | podpowiedz `--max-year 2026`; kod 1 |
| T7 | Samo `--min-year Y` | lista, `--min-year 2026`: -2 i -4 OK (2026); -1, -3 KONFLIKT (tylko starsze) | `Error:` (P1 — dzis bylyby pominiete z `Warning:`); podpowiedz `--min-year 2025` (najnowszy rok wspolny konfliktowych arkuszy — 6.2); kod 1 |
| T8 | Samo `--max-year Y` | lista, `--max-year 2022`: -1 -> 2019, -2 -> 2022, -3 -> 2019, -4 -> 2022 | pobranie 4 arkuszy, kazdy "najnowszy nie pozniejszy niz 2022"; kod 0; sidecar `request.max_year: 2022` |
| T9 | Przedzial | lista, `--min-year 2023 --max-year 2024`: -1 -> 2023, -2 -> 2024, -3 KONFLIKT (2019, 2025), -4 -> 2024 | `Error:` dla -3: `dostepne roczniki 2019, 2025`; podpowiedz `--min-year 2023` (zdjecie gornej granicy) i `--max-year 2024` (zdjecie dolnej); kod 1 |
| T10 | `--year` + `--min-year` | `--year 2024 --min-year 2022` | `Error: --year wyklucza sie z --min-year/--max-year (--year Y to skrot --min-year Y --max-year Y)`; kod 1; przed siecia |
| T11 | `--year` + `--max-year` | `--year 2024 --max-year 2025` | jak T10 |
| T12 | `--min-year` > `--max-year` | `--min-year 2025 --max-year 2023` | `Error: --min-year (2025) nie moze byc wiekszy niz --max-year (2023)`; kod 1 |
| T13 | Rok poza 1900..2100 | `--max-year 2200` | `Error: --max-year musi byc liczba calkowita 1900..2100, otrzymano 2200` (jak dzis `--min-year`); kod 1 |
| T14 | Dwa loty w roku, `newest` | -1 z `--year 2025` | pobrany lot 2025-10-21_84183 (najnowszy `aktualnosc`, ADR-028 — niepelny); `Info: 1 arkusz ma w wybranym przedziale wiecej niz jedna kampanie (N-34-139-C-a-3-1: 2025-04-27_83233, 2025-10-21_84183) — pobrano najnowsza; wszystkie: --campaigns all`; `Warning:` E13 (niepelny); sidecar `extra.alternatives: [{id: "83233", date: "2025-04-27", full_sheet: true}]`; kod 0 |
| T15 | Dwa loty w roku, `all` | -1 z `--year 2025 --campaigns all` | oba loty do `kampanie/`, dowiazanie na 2025-10-21_84183; podsumowanie "2 campaign files for 1 sheets"; bez `Info:` o lotach (wszystkie pobrane); kod 0 |
| T16 | `all` + przedzial | lista, `--campaigns all --min-year 2024` | -2: 2024, 2025 x3, 2026; -4: 2024, 2025 x3, 2026; -1, -3 KONFLIKT -> `Error:` jak T7 (stop dotyczy obu strategii) |
| T17 | Wariant orto | N-34-139-A-c-1-1, `--product orto`, CIR, `--year 2025` | CIR ma lata 2011, 2014, 2017, 2022, 2024 -> KONFLIKT (RGB ma 2025, ale wariant jest osobnym filtrem); `dostepne roczniki` z puli CIR; kod 1 |
| T18 | Godlo CZ / obszar bez PL | `kartograf download CTES96 --year 2023` | `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year/--max-year/--year dotycza tylko PL`; kod 1; przed siecia |
| T19 | Obszar PL+CZ pod `auto` | `--bbox ... --country auto --year 2023` | `Info: --campaigns/--min-year/--max-year/--year dotycza tylko czesci PL (CZ: biezaca wersja danych CUZK)`; czesc PL wg tej tabeli; CZ biezaca |
| T20 | Wycinek `--target-crs` | `--bbox ... --target-crs EPSG:5514 --year 2024` | P6: arkusze wg T1-T9; wynik `bbox/<coords>_y2024.tif`; przy konflikcie `Error:` i brak pliku; `--campaigns all` nadal `Error:` |
| T21 | LAZ, rocznik w przedziale pokrywa to, co referencja | w2, `--product laz --year 2022` (referencja: kafel 2025 N-34-139-A-c-1-1-3-4; kafel 2022 7.173.21.06.2 pokrywa obszar) | pobranie kafla 2022; `Info:` o kaflach pominietych jak dzis; kod 0 |
| T22 | LAZ, rocznik w usludze, brak kafli w czesci obszaru | w2, `--year 2024` (warstwa 2024 istnieje, w w2 pusta) | `Error: brak kafli LAZ z roku 2024 dla 1 z 1 kafli obszaru — nic nie pobrano:` / `  N-34-139-A-c-1-1-3-4 (2025, PL-1992): dostepne roczniki 2022, 2023, 2025` / podpowiedz `--min-year 2024` i `--max-year 2024`; kod 1 |
| T23 | LAZ, rocznik nieobecny w usludze | `--year 2017` na EVRF2007 (warstwy 2018..2026) | `Error: rocznik 2017 nie istnieje w usludze EVRF2007 (dostepne: 2026, ..., 2018)` — jak dzis, bez GetFeature; dla przedzialu bez wspolnego rocznika z usluga: `Error: przedzial 2010-2017 nie ma rocznika w usludze EVRF2007 (dostepne: ...)` |
| T24 | LAZ, obszar bez kafli w zadnym roku | bbox na morzu, `--year 2023` | jak dzis: `Error: No LAZ tiles found ...`, kod 1 (referencja pusta — nie ma z czym porownac) |
| T25 | LAZ, dwie dostawy NIE tego samego arkusza w jednym roku | Wroclaw 2025 (ADR-029), `--year 2025` | obie zostaja (NIE nie pokrywa) — ADR-029 bez zmian; sidecary roznia sie `extra.url` i nowym `extra.acquisition_date` |

## 6. CLI: flagi, komunikaty, kody wyjscia

### 6.1 Flagi (`kartograf/cli/_parser.py`)

- `--year RRRR` — opis: "Tylko ten rok danych (PL: rok pozyskania
  `aktualnosc` NMT/NMPT/orto, `akt_rok` LAZ); skrot `--min-year RRRR
  --max-year RRRR`; brak roku na ktoryms arkuszu/kaflu = blad przed
  pobraniem".
- `--min-year RRRR` — "Tylko PL: dolna granica roku danych (wlacznie)";
  usunac "nie dziala z --target-crs" (P6).
- `--max-year RRRR` (NOWA) — "Tylko PL: gorna granica roku danych
  (wlacznie) — najnowsze dane nie pozniejsze niz RRRR".
- `--campaigns` bez zmian; opis LAZ bez zmian.
- Walidacja przed siecia, w `cmd_download` tam, gdzie dzis
  `validate_campaign_args` (`download_cmd.py:883-889`): T10-T13.

### 6.2 Komunikat zatrzymania (U4)

Jeden `Error:` na stderr (takze z `-q`), kod 1, nic nie pobrane:

```
Error: brak danych z roku 2024 dla 2 z 4 arkuszy — nic nie pobrano:
  N-34-139-C-a-3-1: dostepne roczniki 2019, 2023, 2025
  N-34-139-C-a-3-3: dostepne roczniki 2019, 2025
Podpowiedz: --min-year 2024 (rok 2024 i nowsze) albo --max-year 2024 (rok 2024 i starsze)
```

Naglowek wg przedzialu: `z roku 2024` (min == max), `od roku 2026`
(samo min), `do roku 2020` (samo max), `z lat 2023-2024` (para). Lista
arkuszy pelna do 20 pozycji, dalej `... i N innych` (lista pelna w
`DownloadError`/wyjatku, sekcja 8). Arkusze BRAK (U3) nie wchodza do tego
komunikatu — dostaja `Warning:` R5 tylko wtedy, gdy zadanie doszlo do
pobierania; przy zatrzymaniu nie sa raportowane (nic nie pobrano).

Podpowiedz (liczona z arkuszy konfliktowych; L = `min_year`, U = `max_year`):

- `nowsze_s` = lata arkusza > U; `starsze_s` = lata < L.
- Wszystkie konfliktowe arkusze maja `nowsze_s`: gdy L podane —
  `--min-year L (rok L i nowsze)` [dla `--year Y`: U4 doslownie]; gdy L
  brak (samo `--max-year`) — `--max-year U'`, gdzie `U'` = max po arkuszach
  z min(`nowsze_s`) (najmniejsze podniesienie granicy, ktore obejmie kazdy
  arkusz).
- Wszystkie maja `starsze_s`: gdy U podane — `--max-year U (rok U i
  starsze)`; gdy U brak (samo `--min-year`) — `--min-year L'`, gdzie `L'` =
  min po arkuszach z max(`starsze_s`) (T7: 2025).
- Obie grupy niepuste (T5, T6, T9) — obie linie, rozdzielone `albo`.
- Zadna z podpowiedzi nie obejmuje wszystkich konfliktowych arkuszy
  (np. jeden tylko nowsze bez L, drugi tylko starsze bez U — niemozliwe przy
  jednej parze granic; zostawione dla kompletnosci) — tylko lista lat.

### 6.3 `Info:` o wielu lotach w przedziale (P4)

Tylko `newest`, tylko gdy dla arkusza w przedziale jest > 1 rekordu;
stderr, raz na zadanie, przed pobieraniem:

```
Info: 3 arkusze maja w wybranym przedziale wiecej niz jedna kampanie — pobrano najnowsza; wszystkie: --campaigns all
  N-34-139-C-a-3-1: 2025-04-27_83233 (pelny), 2025-10-21_84183 (niepelny, wybrany)
  N-34-139-C-a-3-2: 2025-04-04_81468 (pelny), 2025-04-27_83233 (pelny), 2025-10-21_84183 (niepelny, wybrany)
  ...
```

Lista do 10 arkuszy, dalej `... i N innych`. Bez przedzialu (dzisiejszy
`newest`) komunikatu NIE ma — `newest` nadal uzywa `record_cache` i nie zna
listy (P5); pytanie otwarte Q4.

### 6.4 Pozostale komunikaty

- T10: `Error: --year wyklucza sie z --min-year/--max-year (--year Y to
  skrot --min-year Y --max-year Y)`.
- T12: `Error: --min-year (2025) nie moze byc wiekszy niz --max-year (2023)`.
- T13: tekst `validate_campaign_args` z nazwa parametru zamieniona na flage
  (jak dzis `min_year` -> `--min-year`, `download_cmd.py:888`).
- T18/T19: rozszerzone teksty `_reject_campaign_opts_without_pl`
  (`download_cmd.py:252-264`) — wyliczenie flag jak w tabeli.
- LAZ T22: `Error: brak kafli LAZ z roku 2024 dla 1 z 1 kafli obszaru — nic
  nie pobrano:` + linie `  <godlo> (<rok>, <uklad>): dostepne roczniki ...`
  + podpowiedz jak 6.2. Dzisiejszy `Info:` o kaflach pominietych
  (`_print_laz_superseded`) zmienia dopisek "starszy rocznik: --year" na
  "inny rocznik: --year/--min-year/--max-year".
- P9: `Error: nie udalo sie sprawdzic roku danych dla 2 z 4 arkuszy (blad
  skorowidza, nie brak danych): N-34-..., N-34-... — ponow pobranie`;
  kod 1; LAZ analogicznie (dzisiejszy `DownloadError` z `select_tiles`).
- Kody: 0 = pobrano (takze z `Warning:` R5/E13/`Info:`); 1 = walidacja,
  konflikt (6.2), awaria sprawdzania (P9), brak danych dla WSZYSTKICH
  arkuszy (jak dzis), porazka pobrania (jak dzis).

## 7. Sidecar (`kartograf-meta/1`, pola addytywne)

| Plik | Pole | Wartosc |
|---|---|---|
| kampania NMT/NMPT/orto (`kampanie/...`) i sciezka standardowa (kopia sidecara) | `request.min_year`, `request.max_year` | gdy podane; `request.year` dodatkowo, gdy min == max (czytelnosc; LAZ ma `request.year` dzis) |
| j.w. | `extra.campaign` | bez zmian — identyfikuje lot (`id`, `date`, `full_sheet`, ...) |
| j.w. | `extra.available_years` (NOWE) | wszystkie lata arkusza w skorowidzu w chwili pobrania (lista int, rosnaco); tylko w przeplywie z przedzialem (tam lista jest znana) |
| j.w. | `extra.alternatives` (NOWE) | `newest` z przedzialem: pozostale rekordy w przedziale, NIE pobrane: `[{"id", "date", "full_sheet"}]`; pomijane, gdy puste; `all`: pomijane |
| wycinek PL (`bbox/<coords>_y....tif`) | `request.min_year`/`max_year`/`year` | jak wyzej; `extra.sheet_sources` bez zmian (kazdy wpis niesie `acquisition_date`/`acquisition_year` rekordu) |
| kafel LAZ | `request.min_year`, `request.max_year`, `request.year` | gdy podane (`year` dzis jest; `max_year` nowe) |
| kafel LAZ | `extra.acquisition_date` (NOWE), `extra.full_sheet` (NOWE) | `akt_data`, `czy_ark_wypelniony` kafla — dwie dostawy tego samego arkusza w roku (T25) roznia sie dzis tylko `url` |
| sidecar standardowy po `_note_reuse` (N4) | `extra.parent_requests[].min_year/max_year/year` | zadania ponownie uzywajace pliku (jak dzis `min_year`) |

`request` opisuje POBRANIE (ARCHITECTURE 3.2) — przy ponownym uruchomieniu z
innym przedzialem, ktory wybiera te sama kampanie, plik jest pomijany, a
nowy przedzial trafia do `extra.parent_requests` (istniejace N4).

## 8. Biblioteka

### 8.1 Nowy wyjatek

```python
class YearRangeError(DownloadError):
    """Dane istnieja, ale nie w zadanym przedziale lat (U4) — przed pobraniem.

    sheets: dict[str, tuple[int, ...]]  # godlo / godlo kafla -> dostepne lata
    min_year: int | None
    max_year: int | None
    hints: tuple[str, ...]               # teksty podpowiedzi z 6.2 (jak NoCoverageError.hints)
    """
```

Dziedziczy po `DownloadError`, NIE po `NoCoverageError`: brak pokrycia jest
w trybie listy tolerowany (R5: pominiecie), a konflikt roku ma zatrzymac
zadanie — rozroznienie klasami, nie trescia. Eksport z `kartograf`
(`__all__`), obok `NoCoverageError`.

### 8.2 `DownloadManager` (`kartograf/download/manager.py`)

- `DownloadManager(..., campaigns="newest", min_year=None, max_year=None)`;
  wlasciwosc `max_year`; `validate_campaign_args(campaigns, min_year,
  max_year)` (zmiana sygnatury — funkcja nie jest w `__all__`
  `kartograf/__init__.py`, uzywana wewnetrznie i w `select_tiles`).
- Przeplyw z jakimkolwiek przedzialem (`min_year` lub `max_year` podane),
  tylko provider z `supports_campaigns is True`:
  1. **Faza sprawdzania** (`check_year_range(godla) -> YearRangeCheck`,
     publiczna, rownolegla jak `_download_many`): dla kazdego arkusza
     `resolve_campaigns(godlo, campaigns="all", ...)` bez granic (pelna
     lista, `campaigns_cache`); klasyfikacja 4.2; wynik
     `YearRangeCheck(selected: dict[godlo, list[SkorowidzRecord]],
     no_data: dict[godlo, NoCoverageError], conflicts: dict[godlo,
     tuple[int, ...]], failed: dict[godlo, DownloadError])`.
     `selected` = rekordy w przedziale: `newest` -> jeden (max po kluczu
     ADR-028), `all` -> wszystkie, malejaco.
  2. `conflicts` niepuste -> `YearRangeError` (wszystkie arkusze, z
     podpowiedziami); `failed` niepuste -> `DownloadError` (P9); nic nie
     pobrane. Kolejnosc: najpierw `failed` (nie wiadomo, czy konflikt jest
     pelny), potem `conflicts`.
  3. **Faza pobierania**: jak dzisiejszy `_fetch_campaigns`
     (`manager.py:700-863`), ale z rekordami z fazy 1 (bez drugiego
     `resolve_campaigns`); `no_data` -> `no_coverage` wyniku (R5, jak dzis);
     sidecar kampanii z polami z sekcji 7.
- `download_sheet`, `download_sheets`, `download_hierarchy`: z przedzialem
  moga rzucic `YearRangeError` i `DownloadError` fazy 1 PRZED pierwszym
  pobraniem (dokumentacja: dotad lista nie rzucala `DownloadError`).
  `last_result` po fazie 1 z bledem = `None`.
- Bez przedzialu: przeplyw bez zmian (w tym `record_cache` i fallback I-1).
- `_write_campaign_sidecar`: `request.max_year`/`year`, `extra.available_years`,
  `extra.alternatives` (sekcja 7).

### 8.3 Provider skorowidza (`providers/pl/skorowidz.py`)

- `resolve_campaigns(godlo, *, campaigns="newest", min_year=None,
  max_year=None, timeout=None)`: z jakimkolwiek przedzialem — pelna lista
  (`_resolve_all` bez pomijania warstw), filtr `min_year <= rok <= max_year`,
  `newest` -> `[max]`; brak rekordu w przedziale przy niepustej liscie ->
  `YearRangeError({godlo: lata})`; pusta lista -> `NoCoverageError` jak
  dzis. `_meets_min_year` -> `_in_year_range(record, min_year, max_year)`.
- `_resolve_all`: parametr `min_year` i pomijanie warstw usuniete (P5);
  `scanned_from`, `_covers`, `_partial_scan_no_coverage` usuniete; wpis
  `campaigns_cache` z `scanned_from` innym niz `None` = chybienie (jak wpisy
  sprzed ADR-031, `skorowidz.py:594-599`).
- `available_years(godlo) -> tuple[int, ...]` (publiczna, z listy
  `_resolve_all`) — dla Hydrografu/QGIS: "jakie lata ma ten arkusz".

### 8.4 Wycinek PL (`download/cutout.py`)

- `prepare_pl_cutout(..., min_year=None, max_year=None)`: sufiks nazwy
  (P6) w `PlCutout.target_path`; `download_pl_cutout(..., min_year=None,
  max_year=None)` i `run_pl_cutout` przekazuja do `DownloadManager`;
  `YearRangeError`/`DownloadError` fazy 1 przechodza (wycinek nie powstaje);
  sidecar wycinka z sekcji 7. `campaigns="all"` nadal `ValidationError`.
- CLI: `_reject_campaign_opts_with_target_crs` odrzuca juz tylko
  `--campaigns all`.

### 8.5 LAZ (`providers/pl/gugik_laz.py`, `download/laz.py`)

- `select_tiles(bbox, year=None, min_density=None, ..., campaigns="newest",
  min_year=None, max_year=None)`; `year=Y` == `min_year=max_year=Y`;
  `year` z `min_year`/`max_year` = `ValidationError` (dzis tylko z
  `min_year`); `min_year > max_year` = `ValidationError`.
- Roczniki uslugi: przedzial bez wspolnego rocznika = `DownloadError`
  (T23, tekst jak dzis dla `year`).
- Z przedzialem: zapytania do WSZYSTKICH rocznikow uslugi (nie tylko z
  przedzialu — potrzebna referencja i lata do komunikatu), filtr
  `min_density` jak dzis; `R = select_newest_cover(wszystkie)`;
  `C = select_newest_cover(w przedziale)` albo `select_all_intersecting`
  przy `all`; dla kazdego `r` w `R.tiles` o roku spoza przedzialu:
  czesc wspolna `r` z obszarem musi byc pokryta suma pelnych kafli `C`
  (powiekszonych o `tolerance_m`, regula ADR-029); niepokryty kawalek ->
  konflikt: lata = `akt_rok` wszystkich kafli (dowolny rok), ktorych rama
  przecina ten kawalek. Konflikty -> `YearRangeError({godlo_kafla: lata})`;
  bez konfliktow -> zwrot `C` (z `superseded` jak dzis).
- Koszt: `--year Y` odpytuje dzis 1 rocznik, po zmianie wszystkie (NMT
  EVRF2007: 9 warstw) — tyle samo, co `newest` bez flag; GetFeature per
  rocznik to zapytania bbox, tanie wobec kafli 50-250 MB.
- `download_laz_area(..., max_year=None)`; `write_laz_sidecar` z polami z
  sekcji 7; `LazDownloadResult` bez zmian.
- `discover_tiles` (alias `select_tiles(...).tiles`) bez zmian sygnatury
  poza `max_year`.

### 8.6 CLI (`cli/download_cmd.py`)

- `_campaign_opts` -> `(campaigns, min_year, max_year)`; `--year Y` mapowany
  w jednym miejscu (`cmd_download`, po T10-T13) na `min_year = max_year = Y`
  i tak przekazywany do WSZYSTKICH torow (godlo, hierarchia, lista
  `--bbox`/`--geometry`, wycinek, LAZ). `_cmd_download_laz` przestaje
  czytac `args.year` osobno (`download_cmd.py:1771-1773, 1801`).
- `_reject_campaign_opts_without_pl` / `_reject_campaign_opts_with_target_crs`
  wg P6/P7.
- `YearRangeError` -> komunikat 6.2 (CLI formatuje z `sheets`/`hints`),
  kod 1; wszystkie tory.

## 9. Cache (`cache/metadata.py`)

- Klucze `record_cache` i `campaigns_cache` BEZ zmian
  (`(product, resolution, vertical_crs, godlo)`; orto: `color` w polu
  `resolution`, `gugik_orto.py:200`); granice lat poza kluczem (ADR-030
  (h)) — filtr dziala na liscie po odczycie.
- `campaigns_cache` staje sie jedynym zrodlem dla zadan z przedzialem
  (takze `newest`); `record_cache` sluzy wylacznie `newest` bez przedzialu.
  Konsekwencja: `--year` na arkuszu, ktory `newest` odwiedzil wczoraj,
  robi nowe zapytania (inna tabela) — raz na 7 dni.
- Pole `scanned_from` przestaje byc zapisywane; istniejace wpisy z
  `scanned_from != None` sa chybieniem (P5) — bez migracji, jak ADR-031.
- `--force` = `MetadataCache(refresh=True)` bez zmian: faza 1 pyta skorowidz
  i ZAPISUJE liste.
- LAZ: bez cache (jak dzis; lata uslugi w pamieci procesu,
  `gugik_laz.py:424-426`).

## 10. Plan testow (offline, surowe fixtures; `-m "not live"`)

### 10.1 Istniejace fixtures wystarczaja

Zrodlo: `tests/fixtures/gugik_skorowidz/real_2026_10_06/nmt/c14/` (4 arkusze
N-34-139-C-a-3-{1..4}, warstwy 2023iStarsze/2024/2025/2026), helper
`c14_session` (`tests/test_provider_campaigns.py:78`), `empty.body`
(`tests/fixtures/gugik_skorowidz/empty.body`) dla arkusza BRAK; orto:
`N-34-139-A-c-1-1_*` + `orto_session`; LAZ: `w2_EVRF2007_*.xml`,
`laz_session` (`tests/test_real_gugik_responses.py:445`).

| Test (nazwa robocza) | Warstwa | Przypadek |
|---|---|---|
| `test_resolve_campaigns_year_2025_c14_picks_newest_flight` | provider | T1/T14: -1 -> 84183; `alternatives` = 83233 |
| `test_resolve_campaigns_year_2024_c14_conflict_lists_years` | provider | T5: -1 -> `YearRangeError` z (2019, 2023, 2025) |
| `test_resolve_campaigns_max_year_2022_c14` | provider | T8: -1 -> 2019 (73021), -2 -> 2022 |
| `test_resolve_campaigns_range_queries_all_layers_no_partial_scan` | provider | P5: `queried_layers` = 4 warstwy takze z `min_year=2026`; wpis cache bez `scanned_from`; stary wpis `scanned_from=2024` = chybienie |
| `test_available_years_c14` | provider | 8.3: -2 -> (2019, 2022, 2023, 2024, 2025, 2026) |
| `test_orto_cir_year_2025_conflict_rgb_has_it` | provider | T17 |
| `test_manager_year_2024_list_stops_before_any_download` | manager | T5: `download_sheets` 4 arkusze -> `YearRangeError` z 2 arkuszami; `download_record` nie wywolany; brak plikow w `kampanie/` |
| `test_manager_year_2025_list_downloads_all_four_with_info_data` | manager | T1: 4 kampanie, `last_result.campaign_files`, sidecar `request.year/min_year/max_year`, `extra.available_years`, `extra.alternatives` |
| `test_manager_year_with_no_data_sheet_is_skipped` | manager | T2: `empty.body` dla 5. arkusza -> `no_coverage`, reszta pobrana |
| `test_manager_min_year_alone_conflict_is_error_not_skip` | manager | T7 (P1): zmiana wobec `test_min_year_newest_no_coverage_in_list_is_no_coverage_status` (`tests/test_manager_campaigns.py:678`) — ten test do przepisania |
| `test_manager_check_failure_aborts_whole_task` | manager | P9: jedna warstwa 5xx dla jednego arkusza -> `DownloadError`, zero pobran |
| `test_manager_all_with_range_downloads_every_flight_in_range` | manager | T15/T16 |
| `test_manager_without_range_unchanged_uses_record_cache` | manager | regresja: `newest` bez flag nie dotyka `campaigns_cache`, fallback I-1 dziala |
| `test_cli_year_nmt_list_error_message_and_hints` | CLI | T5: dokladny tekst 6.2, kod 1, `MetadataCache` zamkniety |
| `test_cli_year_conflicts_with_min_max` | CLI | T10-T12, przed siecia (`GugikProvider` nie tworzony) |
| `test_cli_year_cz_godlo_rejected` / `test_cli_year_pl_cz_info` | CLI | T18/T19 (wzor: istniejace testy `--min-year` dla CZ w `tests/test_cli.py`) |
| `test_cli_year_info_multiple_flights` | CLI | T14: tekst 6.3 |
| `test_cli_year_target_crs_cutout_suffix` | CLI/cutout | T20: `bbox/<coords>_y2024.tif`, sidecar; `tests/test_pl_cutout.py:2502` (stub `resolve_campaigns`) rozszerzony o `max_year` |
| `test_laz_year_2022_w2_covers_reference` | LAZ | T21: kafel 2022 wybrany; `test_c13_year_2023_returns_the_single_older_tile` (`tests/test_real_gugik_responses.py:475`) nadal przechodzi (ten sam godlo = pokrycie) |
| `test_laz_year_2024_w2_conflict_lists_years` | LAZ | T22: `YearRangeError({"N-34-139-A-c-1-1-3-4": (2022, 2023, 2025)})`; wszystkie roczniki odpytane |
| `test_laz_range_without_service_year` | LAZ | T23 |
| `test_laz_year_and_range_exclusive` | LAZ | 8.5 (rozszerzenie `test_year_and_min_year_are_exclusive`, `tests/test_laz_campaigns.py:105`) |
| `test_laz_sidecar_acquisition_date_and_max_year` | LAZ | sekcja 7 |
| `test_parser_max_year_and_year_for_nmt` | parser | 6.1 |

Testy do zmiany: `test_all_min_year_skips_cumulative_layer_below_bound`,
`test_all_cache_partial_scan_*`, `test_all_cached_partial_no_coverage_*`
(`tests/test_provider_campaigns.py:158, 261, 307, 385, 403`) — opisuja
usuwany skan czesciowy; `test_min_year_skips_older_year_layers`
(`tests/test_laz_campaigns.py:74`) — LAZ odpytuje wszystkie roczniki.

### 10.2 Przypadki testowane na danych syntetycznych (brak surowych)

Tylko tam, gdzie fixture nie moze istniec: rekord bez `aktualnoscRok` i z
niecyfrowym `aktualnosc` (jak dzis `test_all_record_without_year_is_dropped_by_min_year`),
`YearRangeError` z > 20 arkuszami (skrot listy), podpowiedz `--max-year U'`
przy samym `--max-year` (6.2).

### 10.3 Nowe surowe fixtures do nagrania (test `live`, potem kopia)

| Fixture | Po co | Jak nagrac |
|---|---|---|
| orto: dwa loty RGB o tej samej wielkosci piksela w jednym roku | T14 dla orto (w fixtures roznia sie pikselem) | GetFeatureInfo `text/html` na `SkorowidzeOrtofotomapy<rok>` dla arkusza z duzego miasta (np. Warszawa, Krakow — nalot wiosenny i jesienny); zapis `orto/<godlo>_<warstwa>.html` jak w README fixtures |
| LAZ: obszar o dwoch kaflach referencyjnych, z ktorych jeden ma TYLKO nowszy rocznik | T22 na dwoch kaflach (czesciowy konflikt), podpowiedz | GetFeature per rocznik (jak C13) dla bboxa na skraju kampanii 2025 (np. granica nalotu warszawskiego); pliki `w3_EVRF2007_<rok>.xml` |
| LAZ: dwie dostawy NIE tego samego arkusza w jednym roku | T25 | GetFeature 2025 dla Wroclawia (ADR-029) |
| NMT: arkusz PL-2000 z dwoma lotami w roku | regresja strefy w kluczu | C6-podobny (`6.129.30`) — w fixtures 1 lot/rok; wybor arkusza z `SkorowidzeNMT2025` po sprawdzeniu w QGIS |

Nagrywanie wg `tests/fixtures/gugik_skorowidz/real_2026_10_06/README.md`
(pliki bez edycji; dane poza repo, tylko wybrany podzbior do fixtures;
zadnych sciezek prywatnych w README).

## 11. Dokumentacja i CHANGELOG

### 11.1 `### Dodane`

- `--max-year RRRR` (NMT, NMPT, orto, LAZ): gorna granica roku danych;
  `--year RRRR` dziala teraz takze dla NMT/NMPT/orto (dotad tylko LAZ) i
  jest skrotem `--min-year RRRR --max-year RRRR`; brak roku na ktoryms
  arkuszu/kaflu zatrzymuje zadanie PRZED pobraniem z lista dostepnych lat i
  podpowiedzia; arkusze bez zadnych danych sa pomijane z `Warning:` jak
  dotad.
- Biblioteka: `DownloadManager(max_year=)`, `download_pl_cutout(min_year=,
  max_year=)`, `download_laz_area(max_year=)`, `select_tiles(max_year=)`,
  `resolve_campaigns(max_year=)`, `available_years(godlo)`; nowy wyjatek
  `YearRangeError(DownloadError)` z `sheets` (godlo -> lata), `min_year`,
  `max_year`, `hints`.
- Sidecar: `request.max_year`, `request.year` (gdy min == max),
  `extra.available_years`, `extra.alternatives` (kampania NMT/NMPT/orto);
  LAZ `extra.acquisition_date`, `extra.full_sheet`.
- Wycinek `--target-crs` z przedzialem lat: nazwa `bbox/<coords>_y<...>.tif`.

### 11.2 `### Zmienione` (z "Co zrobic")

- `--year` dla `--product nmt|nmpt|orto` byl ignorowany (pobierana byla
  najnowsza kampania) — teraz dziala. Co zrobic: skrypty, ktore podawaly
  `--year` "na wszelki wypadek", dostana rok RRRR albo `Error:` z lista lat;
  usun flage albo uzyj `--min-year`/`--max-year`.
- `--min-year` (NMT/NMPT/orto, obie strategie): arkusz z danymi tylko
  starszymi niz granica konczyl sie pominieciem z `Warning:` (lista) albo
  `Error:` braku pokrycia (pojedynczy arkusz); teraz KAZDY taki arkusz
  zatrzymuje cale zadanie przed pobraniem (`Error:` z latami i podpowiedzia,
  kod 1), a arkusz bez zadnych danych nadal jest pomijany. Co zrobic: gdy
  chodzilo o "co najmniej rok RRRR, a reszte pomin", uruchom bez
  `--min-year` i odfiltruj po `extra.campaign.date` w sidecarach, albo
  obniz granice wg podpowiedzi.
- `--min-year` dziala z `--target-crs` (dotad `Error:`); wynik ma sufiks
  `_y<...>` w nazwie. Co zrobic: nic; wczesniejsze wycinki bez sufiksu
  pozostaja wycinkami "najnowsze".
- LAZ `--year`/`--min-year`: obszar, ktorego czesc ma dane tylko z innych
  rocznikow, byl pobierany czesciowo bez komunikatu; teraz `Error:` z
  rocznikami per kafel i podpowiedzia, nic nie pobrane; zapytania WFS ida do
  wszystkich rocznikow uslugi takze z `--year`. Co zrobic: dla swiadomie
  czesciowego pobrania uzyj `--min-year`/`--max-year` wg podpowiedzi albo
  zawez `--bbox`.
- `--campaigns all --min-year` nie pomija juz warstw skorowidza wg roku z
  nazwy (zawsze pelna lista); wpisy `campaigns_cache` ze skanu czesciowego
  sa odpytywane ponownie. Co zrobic: nic (koszt: 1-3 zapytania
  GetFeatureInfo wiecej na arkusz raz na 7 dni).
- `validate_campaign_args(campaigns, min_year, max_year)` — nowy
  obowiazkowy argument (funkcja wewnetrzna, poza `__all__`). Co zrobic: kod
  wolajacy ja bezposrednio dodaje `max_year`.
- `DownloadManager.download_sheets`/`download_hierarchy` z przedzialem lat
  moga rzucic `YearRangeError`/`DownloadError` przed pobraniem (dotad lista
  nie rzucala). Co zrobic: `except YearRangeError` (albo `DownloadError`)
  wokol wywolan z `min_year`/`max_year`.

### 11.3 Dokumenty

- `docs/DECISIONS.md`: nowy ADR-032 (tresc = sekcje 2-3, 5-9 tego specu)
  + erraty: ADR-030 (f) (stop zamiast pominiecia; `--max-year`), (g)/[Q5]
  (skan czesciowy usuniety), (h) (`campaigns_cache` dla `newest` z
  przedzialem), (i) (nowe pola), (j)/[Q2] (wycinek przyjmuje przedzial);
  ADR-029 errata 1 (`--year` == przedzial, sprawdzenie pokrycia referencji).
  CRLF zachowac.
- `docs/ARCHITECTURE.md` 3.2 (pola), 4.1, 4.3, 4.6, 4.7; `docs/USAGE.md`
  sekcje 1 (przyklady) i 4 (kampanie); `docs/SCOPE.md` 2 (ograniczenia:
  CZ bez roku); `docs/PROGRESS.md`.

## 12. Pytania otwarte dla uzytkownika

| # | Pytanie | Propozycja w specu |
|---|---|---|
| Q1 | Czy regula "konflikt = stop calego zadania" ma dotyczyc takze SAMEGO `--min-year` i SAMEGO `--max-year` (P1), czy tylko `--year`? Dzis `--min-year` pomija arkusz z `Warning:` (ADR-030 (f)). | Tak, kazdy przedzial (spojnosc z U5). |
| Q2 | Dwa loty w jednym roku pod `newest`: najnowszy `aktualnosc` (ADR-028; dla N-34-139-C-a-3-1 w 2025 jest to lot NIEPELNY 2025-10-21) czy preferencja pelnego arkusza (`calyArkuszWypelnionyTrescia = TAK`) w obrebie roku? | Najnowszy (jedna regula ADR-028); uzytkownik widzi `Info:` + `Warning:` E13 i moze wziac `--campaigns all`. |
| Q3 | Wycinek `--target-crs` z przedzialem: wspierac z sufiksem `_y<...>` w nazwie (P6), czy utrzymac odrzucenie z errata 1 [Q2] (teraz dla trzech flag)? | Wspierac (P6). |
| Q4 | `Info:` o wielu lotach w przedziale (6.3): zawsze na stderr (takze z `-q`), czy tylko w logu (`logger.info`)? | stderr, jak `Info:` o kaflach LAZ. |
| Q5 | Awaria skorowidza dla jednego arkusza w fazie sprawdzania: przerwac cale zadanie (P9), czy sprawdzic reszte, pobrac ja i zglosic ten arkusz jako porazke (kod 1, wynik czesciowy)? | Przerwac (U6: bez wyniku czesciowego). |
| Q6 | Usunac skan czesciowy `all --min-year` (P5; koszt 1-3 zapytania/arkusz/7 dni), czy zachowac go dla `all --min-year` bez `--max-year` i akceptowac, ze komunikat konfliktu nie wymieni lat starszych od granicy? | Usunac. |
| Q7 | LAZ: czy czesc obszaru bez kafli w ZADNYM roczniku ma dostac `Warning:` (analog U3 dla arkuszy)? Dzis LAZ milczy (obszar nie jest lista arkuszy). | Bez zmian (poza zakresem; osobna sprawa ADR-029). |
