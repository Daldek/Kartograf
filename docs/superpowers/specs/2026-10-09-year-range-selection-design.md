# Spec: Wybor roku danych — `--year`, `--min-year`, `--max-year` (NMT, NMPT, orto, LAZ)

**Data:** 2026-10-09, aktualizacja 2026-10-10
**Status:** projekt do review uzytkownika; decyzje uzytkownika z 2026-10-09
i 2026-10-10 (sekcja 2) sa wiazace; pytania Q1, Q3-Q8 rozstrzygniete
(sekcja 12), otwarta zostaje tylko opcja Q2a
**Wersja docelowa:** 0.7.2 (galaz `feat/year-range` z `develop`)
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

## 0. Errata 2026-10-10 — model A (NADRZEDNA wobec sekcji 2-11)

**Status:** zaakceptowany przez uzytkownika 2026-10-10 (model A po audycie
logiki flag CLI, `agent://CliFlagLogicAudit`). Gdzie nizsze sekcje mowia
inaczej, obowiazuje ta sekcja; wiersze tabeli 5 i testy 10.1 wymienione
nizej sa zastapione.

**Powod:** audyt wykazal, ze flagi roku mieszaly dwa pytania — KTORE lata
(filtr) i ILE lotow na arkusz (strategia): samo `--min-year` dawalo 1 lot,
a `--max-year`/`--year` wszystkie loty z przedzialu (`--min-year 1900` = 4
pliki, `--max-year 2100` = 23 pliki na C14); jawne `--campaigns newest`
z gorna granica bylo bledem, choc ma naturalne znaczenie; te same flagi
znaczyly co innego dla LAZ niz dla NMT/NMPT/orto.

| # | Decyzja (2026-10-10) | Zastepuje |
|---|---|---|
| U14 | **Flagi roku = filtr dopuszczalnych lat; `--campaigns` = ile lotow.** `--year`, `--min-year`, `--max-year` i para wyznaczaja przedzial lat (twardy filtr, sprawdzenie wszystkich arkuszy, konflikt = stop — U2-U6, P1 bez zmian). `--campaigns` decyduje o liczbie lotow na arkusz: `newest` (domyslnie) = jeden, najnowszy lot w przedziale (klucz ADR-028); `all` = wszystkie loty w przedziale. Kazda kombinacja jest dozwolona; jawne `--campaigns newest` znaczy to samo co brak flagi. Ta sama regula dla NMT, NMPT, orto i LAZ (dla LAZ to dzisiejsza semantyka ADR-029, bez zmian). | U9, U13 (staje sie regula, nie wyjatkiem), P3, P3a, czesc U12 ("z `--max-year` albo `--year` = blad") |
| U15 | **Sciezka standardowa przy przedziale (opcja (i)):** regula dowiazania BEZ ZMIAN (ADR-030 (d): najnowszy lokalny lot, nigdy wstecz — U8). Gdy przy jakimkolwiek przedziale dowiazanie arkusza wskazuje lot SPOZA przedzialu (bo lokalnie jest nowszy), CLI wypisuje `Info:` (stderr, takze z `-q`) z godlem, lotem dowiazania i katalogiem pobranego lotu; biblioteka zwraca te informacje w wyniku (`SheetFetch`/`DownloadResult`). Kod wyjscia bez zmian. | zdanie P3 "sciezka standardowa = dowiazanie do najnowszego lotu w przedziale" |
| U16 | **0.8.0:** `--campaigns {newest,all}` zostaje w 0.7.2; w 0.8.0 (zmiany lamiace CLI w jednym wydaniu) zastapione przelacznikiem bez wartosci (np. `--all-campaigns`), bo `newest` jest zawsze domyslne. Pozycja w backlogu "Do 0.8.0". | — |

**Skutki (zastepuja wskazane miejsca):**

- **Biblioteka:** brak sentinela strategii — `DownloadManager(campaigns=
  "newest")`, `resolve_campaigns(campaigns="newest")` domyslnie;
  `resolve_campaign_strategy` usuniety; `campaigns="newest"` z `max_year`
  dozwolone (najnowszy lot w przedziale). 8.2, 8.3, 8.6 odpowiednio.
- **Pomiar pokrycia i `Info:` 6.3** (U10, P4) — tylko przy `all` (jawnym)
  z > 1 lotem w przedziale i niepelnym najnowszym; przy `newest` jeden lot,
  bez pomiaru.
- **Podpowiedzi 6.2** bez zmian w tekscie; obie (`--min-year Y`,
  `--max-year Y`) daja teraz po jednym locie na arkusz.
- **Tabela 5 (C14):**
  - T1 `--year 2025` (lista) = 4 pliki kampanii (po jednym na arkusz,
    wszystkie 84183, 2025-10-21), dowiazania na nie, `Warning:` E13 dla
    -1, -2, -3, bez pomiaru i bez `Info:` 6.3; dzisiejszy wynik T1
    (10 plikow, pomiar, `Info:`) = `--campaigns all --year 2025`.
  - T8 `--max-year 2022` = 4 pliki: -1 i -3 73021 (2019), -2 i -4 75162
    (2022); sidecar `request.campaigns: "newest"`, `request.max_year: 2022`.
    Dzisiejszy wynik T8 (6 plikow) = `--campaigns all --max-year 2022`.
  - T14 -1 `--year 2025` = jeden lot 84183; T15 (`--campaigns all`) = oba
    loty (84183, 83233) z pomiarem — to dzisiejsze T14.
  - T16, T16a bez zmian; T26 `--campaigns newest --year 2025` (albo
    `--max-year 2025`) = jak bez `--campaigns` (jeden lot), kod 0 — bez
    bledu; T26a bez zmian.
  - T27, T28 — dotycza `--campaigns all`.
  - T21-T25 (LAZ) bez zmian.
- **Testy 10.1:** testy T1/T8/T14/T26 managera i CLI przepisane wg
  powyzszego; testy `all` dostaja jawne `campaigns="all"`.
- **CHANGELOG 11:** `--year`/`--max-year` pobieraja domyslnie jeden lot
  w przedziale; wszystkie loty = `--campaigns all`; brak bledu
  `--campaigns newest` z gorna granica; `Info:` o dowiazaniu spoza
  przedzialu.


## 1. Kontekst i cel

### 1.1 Stan: `--year` poza LAZ jest odrzucany (0.7.1, Task 14)

W 0.7.0 `kartograf download --year RRRR` dla `--product nmt|nmpt|orto` byl
po cichu ignorowany (pobierana byla najnowsza kampania). W 0.7.1 (Task 14)
cicha degradacje zastapil blad: `_reject_laz_only_opts`
(`kartograf/cli/download_cmd.py`) konczy takie zadanie `Error:` i kodem 1
z podpowiedzia `--min-year`. Ten spec zastepuje to odrzucenie dzialajacym
wyborem roku; komunikat i docstring `_reject_laz_only_opts` oraz zdania
"wybor roku ... w 0.7.2" w `docs/USAGE.md` 1.1 i `docs/ARCHITECTURE.md`
przechodza do aktualizacji w ramach wdrozenia.

### 1.2 Dzisiejsza semantyka roku (pomiar w kodzie)

Odwolania do linii w tabeli i dalej w specu pochodza z pomiaru 2026-10-09
(przed poprawkami 0.7.1 i review 0.7.1); plan wdrozenia weryfikuje je na
`develop` przed kazdym zadaniem.

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
3. Ta sama semantyka w bibliotece (`DownloadManager`,
   `download_laz_area`, `GugikLazProvider.select_tiles`,
   `resolve_campaigns`): nowy parametr `max_year=`, wyjatek z listy
   dostepnych lat per arkusz.
4. Wybrany rok i kampania (lot) trafiaja do sidecara.

Poza zakresem: skladanie kampanii w jedna powierzchnie (SCOPE 3.1), kampanie
dla CZ (ADR-030 errata 3), land cover (`--year` CORINE to inna flaga innej
komendy — `_parser.py:356-359`, bez zmian).

## 2. Decyzje uzytkownika (2026-10-09 i 2026-10-10, wiazace)

| # | Decyzja |
|---|---|
| U1 | `--year RRRR` jest honorowany dla NMT, NMPT, orto i LAZ — JEDNO zachowanie dla czterech produktow. |
| U2 | `--year Y` pobiera wylacznie rok Y. Warunek: kazdy arkusz/kafel zadania ma dane z roku Y. |
| U3 | Arkusz/kafel bez ZADNYCH danych (zaden rok; np. poza granica kraju) = pominiety z czytelnym `Warning:`. |
| U4 | Arkusz/kafel z danymi tylko z INNYCH lat = zatrzymanie przed pobraniem czegokolwiek; lista dostepnych lat per arkusz; podpowiedz `--min-year Y`, gdy sa lata nowsze (Y i nowsze), oraz `--max-year Y`, gdy sa tylko starsze (Y i starsze = najnowszy nie pozniejszy niz Y). |
| U5 | Nowa flaga `--max-year`, symetryczna do `--min-year`; `--year Y` == `--min-year Y --max-year Y`; min+max = przedzial lat. |
| U6 | Najpierw sprawdzenie wszystkich arkuszy, potem pobieranie (zadnego wyniku czesciowego po zatrzymaniu). Wybrany rok trafia do sidecara. |
| U7 | (uzupelnienie 2026-10-09) Spec ma jawnie opisac przypadek DWOCH LUB WIECEJ kampanii (lotow) tego samego arkusza/kafla w JEDNYM roku: co jest dzis, co wybiera `--year`/`--min-year`/`--max-year`, jak dziala `--campaigns all`, co mowi sidecar, czy uzytkownik jest informowany. |
| U8 | (decyzja Q2, 2026-10-09) Regula sciezki standardowej BEZ ZMIAN: zawsze najnowszy lot (klucz ADR-028 `(aktualnosc, dt_pzgik, url)`, ADR-030 (d) "dowiazanie nigdy wstecz"); bez preferencji pelnego arkusza i bez wyboru wg pokrycia — niepelne dane w sciezce standardowej sa akceptowane, bo liczy sie stabilna i prosta regula. |
| U9 | (decyzja Q2) Z `--year` albo przedzialem (`--min-year`/`--max-year`) pobierane sa WSZYSTKIE loty z przedzialu do `kampanie/` — w praktyce `--campaigns all` zawezone do przedzialu. |
| U10 | (decyzja Q2) Uzytkownik dostaje `Info:` (CLI) i pole w sidecarze, gdy arkusz mial w przedziale kilka lotow I inny pobrany lot ma WIEKSZE pokrycie niz najnowszy. Pokrycie = zmierzony po pobraniu udzial waznych pikseli (skorowidz ma tylko TAK/NIE w `calyArkuszWypelnionyTrescia`). Wyjatek: gdy najnowszy lot jest pelny (TAK) — bez komunikatu. |
| U11 | (decyzja Q2) Pomysl alternatywny — dodatkowa flaga zmieniajaca regule domyslna (wymuszenie pelnego arkusza albo prog pokrycia, np. `--min-coverage 90`) — ma byc opisany jako OPCJA/pytanie otwarte, nie rozstrzygniety (sekcja 12, Q2a). |
| U12 | (decyzje 2026-10-09 do pytan sekcji 12) Q1: zatrzymanie przy konflikcie obowiazkowe dla kazdego przedzialu; Q3: wycinki `--target-crs` NIE przyjmuja flag roku (`--year`, `--min-year`, `--max-year` = `Error:` przed siecia; spojne z planowanymi wycinkami z WCS, ktore nie maja roku); Q4-Q8: przyjete propozycje specu. Jawne `--campaigns newest` z `--min-year` zostaje dozwolone, z `--max-year` albo `--year` = blad. |
| U13 | (decyzja 2026-10-10) Samo `--min-year` bez `--campaigns` pobiera JEDNA, najnowsza kampanie arkusza (jak dzis) — granica dziala jak kontrola "najnowsze dane nie starsze niz L"; najnowsza starsza niz L = konflikt (U4, stop). Strategia `all` z przedzialu (U9) dotyczy przedzialow z gorna granica (`--max-year`, `--year`, para) oraz jawnego `--campaigns all`. Przyklad: arkusz z lotami 2019-2026 i `--min-year 2024` = 1 plik (lot 2026), a nie 5. |

## 3. Rozstrzygniecia projektowe (do akceptacji)

| # | Rozstrzygniecie | Uzasadnienie |
|---|---|---|
| P1 | **Jeden mechanizm = przedzial `[min_year, max_year]`.** Regula "sprawdz wszystko, potem pobierz; konflikt = stop" (U4, U6) obowiazuje dla KAZDEGO przedzialu: `--year`, samo `--min-year`, samo `--max-year`, para. | U5 mowi, ze `--year Y` to `--min-year Y --max-year Y`; gdyby `--min-year` zachowal dzisiejsze "pomin arkusz z `Warning:`", to `--year Y` i `--min-year Y --max-year Y` roznilyby sie zachowaniem — sprzecznosc z U5. Zmiana zachowania `--min-year` opisana w CHANGELOG (sekcja 11). Q1 rozstrzygniete (U12). |
| P2 | **Rok rekordu bez zmian:** NMT/NMPT/orto = `aktualnoscRok`, inaczej `aktualnosc[:4]` (`_record_year`); LAZ = `akt_rok`. Rekord bez ustalonego roku nie spelnia zadnego przedzialu (jak dzis dla `min_year`). | ADR-030 (f): 1381 rekordow — `aktualnoscRok` zawsze zgodny z `aktualnosc`; pomiar 2026-10-09 na fixtures `real_2026_10_06` (NMT, NMPT, orto; 44 pary arkusz/wariant): zero rozbieznosci. `dt_pzgik` (data przyjecia do PZGiK) NIE jest rokiem danych — roznica siega roku (2025-10-21 -> 2026-07-10). |
| P3 | **Strategia wg przedzialu (U9, U13).** Przedzial z gorna granica (`max_year` podane: `--max-year`, `--year`, para) albo jawne `--campaigns all` = `all` zawezone do przedzialu: pobierane sa WSZYSTKIE rekordy twardego filtru ADR-028 z rokiem w przedziale (kazdy do `kampanie/<data>_<id>/`). Samo `--min-year` bez `--campaigns` = `newest`: jeden, najnowszy rekord (klucz ADR-028), o ile jego rok >= `min_year`. Sciezka standardowa w obu przypadkach = dowiazanie do najnowszego lotu w przedziale (klucz ADR-028, ADR-030 (d) bez zmian — U8). | Jedna regula wyboru (ADR-028) i jedna regula dowiazania (ADR-030 (d)); przedzial jest tylko dodatkowym twardym filtrem na liscie kampanii. Dla `[L, inf)` najnowszy lot w przedziale jest najnowszym lotem w ogole, wiec `newest` + `min_year` niczego nie cofa i nie wymaga pobrania pozostalych lotow; dla gornej granicy najnowszy lot w przedziale nie jest najnowszym lotem arkusza, a wszystkie loty lokalnie = uzytkownik sam sklada/wybiera w QGIS (ADR-030 kontekst). |
| P3a | **`--campaigns` z flaga roku.** Parser: `--campaigns` dostaje domyslnie sentinel (brak flagi), jak `--resolution`/`--vertical-crs` (`_resolve_pl_sentinels`). Rozwiazanie sentinela: bez `max_year` (bez flag roku albo samo `--min-year`) = `newest`; z `max_year` (`--max-year`, `--year`) = `all`. JAWNE `--campaigns newest` z `--year`/`--max-year` = `Error:` przed siecia; jawne `--campaigns newest --min-year` = dozwolone (to samo co bez `--campaigns`); jawne `--campaigns all` z dowolna flaga roku = `all` w przedziale. Biblioteka tak samo: `campaigns=None` domyslnie (rozwiazywany jak w CLI), jawne `campaigns="newest"` z `max_year` = `ValidationError`, z samym `min_year` dozwolone. LAZ: bez zmian (ADR-029 w obrebie przedzialu; `all` = bez deduplikacji; jawne `newest` z kazda flaga roku dozwolone) — Q8. | Jawne `newest` ("jeden, najnowszy lot") i gorna granica ("wszystkie loty do roku U", U9) sa sprzeczne: najnowszy lot do roku U nie jest najnowszym lotem arkusza, a dowiazanie na niego cofaloby sciezke standardowa (ADR-030 (d) "nigdy wstecz"); ciche nadpisanie jawnej flagi powtorzyloby wzorzec bledu z 1.1. Z sama dolna granica sprzecznosci nie ma (U12, U13). LAZ nie ma `kampanie/`, a regula ADR-029 juz dzis zachowuje kazdy lot niepelny (NIE nigdy nie wypiera i nie jest wypierany), deduplikuje tylko pelne powtorzenia tej samej ramy — cel U9 (nie gubic lotow) jest spelniony bez zmiany; `newest`+`--year` dla LAZ to dzis udokumentowane zachowanie (ADR-029 "z `--year` regula dziala w obrebie roku"). |
| P4 | **Kilka lotow w przedziale (U7, U10), strategia `all`:** wszystkie pobrane (P3); dowiazanie na najnowszy; po pobraniu Kartograf MIERZY pokrycie kazdego lotu arkusza (udzial waznych pikseli, sekcja 4.4) tylko wtedy, gdy arkusz ma w przedziale > 1 lot i najnowszy lot NIE jest pelny (TAK); gdy inny lot ma wieksze pokrycie niz najnowszy — `Info:` w CLI (6.3) i pola w sidecarze sciezki standardowej (`extra.flights`, `extra.better_coverage`, sekcja 7); kazdy sidecar kampanii dostaje `extra.coverage`, gdy zmierzono. Najnowszy pelny (TAK) = bez pomiaru i bez komunikatu. `newest` (samo `--min-year`) pobiera jeden lot — bez pomiaru. | Pomiar (sekcja 4.3): dwa-trzy loty w jednym roku to w realnych danych norma; skorowidz nie mierzy skali braku (ADR-030 kontekst: niepelny lot moze miec 0,9 % danych pelnego), wiec jedyna uczciwa informacja jest pomiar po pobraniu — a pobranie i tak nastepuje (P3). Dowiazanie sie NIE zmienia (U8). |
| P5 | **Sprawdzenie wymaga PELNEJ listy kampanii arkusza** (wszystkie warstwy skorowidza), nie najnowszego rekordu z `record_cache`. Przy jakimkolwiek przedziale `newest` korzysta z `campaigns_cache` (lista), a nie z `record_cache`. Skan czesciowy (`scanned_from`, pomijanie warstw o gornym roku z nazwy < `min_year`) jest USUWANY: lista jest zawsze pelna. | Komunikat U4 ma wymienic WSZYSTKIE dostepne lata arkusza — po skanie czesciowym lata starsze od granicy sa nieznane. Gorny rok z nazwy warstwy nie pozwala pominac warstwy dla `max_year` (`2023iStarsze` zawiera wszystko starsze). Koszt: dla NMT EVRF2007 4 warstwy zamiast 1-3 zapytan GetFeatureInfo per arkusz, raz na 7 dni (TTL). Q6 rozstrzygniete (U12). |
| P6 | **Wycinek `--target-crs` (ADR-027) NIE przyjmuje flag roku (U12, Q3).** `--year`, `--min-year`, `--max-year` z `--target-crs` = `Error:` przed siecia, kod 1 (dzis: `--min-year` i — przez `_reject_laz_only_opts` — `--year`); `--campaigns all` = `Error:` bez zmian. Biblioteka bez zmian: `prepare_pl_cutout`/`download_pl_cutout`/`run_pl_cutout` nie maja parametrow roku i skladaja najnowsze kampanie. | Nazwa wycinka nie niesie roku (ADR-030 errata 1 [Q2]); wycinki PL maja przejsc na WCS (backlog 0.7.2, pozycja (a)), ktory nie ma rocznikow — sufiks roku i obsluga przedzialu w wycinku z arkuszy bylyby kodem do usuniecia w tym samym cyklu. |
| P7 | **CZ / `--country auto`:** `--year`, `--min-year`, `--max-year` to opcje kampanii PL — ta sama straz co dzis dla `--campaigns all`/`--min-year` (`_reject_campaign_opts_without_pl`): zadanie bez PL = `Error:`, kod 1; obszar PL+CZ pod `auto` = `Info:` raz, CZ pobierany w biezacej wersji; flagi roku NIE wchodza do `_pl_only_flags` (nie zawezaja `auto` do PL). | CUZK nie ma archiwum (ADR-030 errata 3) — roku nie da sie uszanowac; ciche zignorowanie dla CZ powtorzyloby blad z 1.1; odrzucenie calego zadania granicznego zlamaloby ADR-023 pkt 5 (zadanie PL+CZ ma dzialac). Spojne z (j), [Q9], [N-3]. |
| P8 | **LAZ: "kafel zadania" = kafel wyboru referencyjnego.** Wybor referencyjny R = `select_newest_cover` po WSZYSTKICH rocznikach uslugi (z `--min-density`, `--vertical-crs`), czyli to, co uzytkownik dostalby bez flag roku. Kafel R o roku spoza przedzialu musi miec swoja czesc wspolna z obszarem pokryta kaflami z przedzialu (ta sama regula pokrycia co ADR-029, tolerancja 1 m); inaczej konflikt (U4) z latami kafli, ktorych rama przecina niepokryty kawalek. Czesc obszaru bez kafli w zadnym roku = jak dzis (bez ostrzezenia: obszar LAZ nie jest lista arkuszy). | Kafle roznych rocznikow maja rozne godla (PL-1992 vs PL-2000, inne ciecie), wiec "ten sam kafel w innym roku" da sie zdefiniowac tylko przez pokrycie; maszyneria (`select_newest_cover`, `uncovered_pieces`) juz istnieje. |
| P9 | **Awaria skorowidza/WFS w fazie sprawdzania = przerwanie calego zadania** (`DownloadError`, kod 1, lista arkuszy, ktorych nie dalo sie sprawdzic), bez pobierania. Fallback I-1 (lokalna kampania bez sprawdzenia) dziala wylacznie bez flag roku — jak dzis bez `--min-year` (ADR-030 errata 5). | U6: warunek "kazdy arkusz ma rok Y" nie jest sprawdzalny bez odpowiedzi skorowidza; pobranie reszty byloby wynikiem czesciowym. Q5 rozstrzygniete (U12). |
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

**Decyzja dla przedzialu (U8-U10, U13, P3, P4):** przy strategii `all`
wszystkie loty z przedzialu sa pobierane do `kampanie/` (samo `--min-year`
pobiera jeden, najnowszy lot); dowiazanie wskazuje najnowszy lot (klucz
ADR-028, bez preferencji pelnego arkusza, bez wyboru wg pokrycia); LAZ bez
zmian w regule ADR-029 (loty niepelne i tak zostaja). Pokrycie lotow jest
mierzone po pobraniu (4.4), a uzytkownik dowiaduje sie z `Info:` (6.3) i z
sidecara (sekcja 7), gdy inny lot ma wieksze pokrycie niz najnowszy.

### 4.4 Pokrycie lotu (pomiar po pobraniu)

- **NMT/NMPT (`.asc`):** `pokrycie` = udzial komorek o wartosci roznej od
  `NODATA_value` z naglowka AAIGrid (brak klucza = `-9999`, jak GDAL) w
  calym pliku; wynik 0..1, zapis w sidecarze z 4 miejscami po przecinku.
  Pomiar strumieniowy po pobraniu (plik jest juz lokalny; `verify_file_format`
  i `verify_sheet_extent` czytaja tylko naglowek, pomiar czyta calosc —
  ~100-300 MB tekstu dla 1 m, raz na kampanie).
- **Orto (`.tif`):** udzial pikseli roznych od nodata (znacznik nodata
  GeoTIFF albo kanal alfa; bez obu = pokrycie NIEUSTALONE, bez porownania i
  bez komunikatu).
- Mierzone TYLKO w przeplywie z przedzialem i strategia `all`, tylko dla arkuszy z > 1 lotem
  w przedziale i tylko, gdy najnowszy lot nie ma `calyArkuszWypelnionyTrescia
  = TAK` (U10). Wynik mierzony raz, zapisywany w sidecarze kampanii
  (`extra.coverage`); ponowne uruchomienie czyta z sidecara.
- Pokrycie NIE wplywa na dowiazanie (U8) — sluzy wylacznie informacji.

## 5. Tabela decyzyjna

Przyklady na realnych arkuszach z fixtures (sekcja 4.3; N-34-139-C-a-3-1 ma
lata 2019, 2023, 2025; -2: 2019, 2022, 2023, 2024, 2025, 2026; -3: 2019,
2025; -4: 2019, 2022, 2023, 2024, 2025, 2026). "Lista" = 4 arkusze
N-34-139-C-a-3-{1..4} z `--bbox`/`--geometry`/hierarchii.

| # | Przypadek | Przyklad | Wynik |
|---|---|---|---|
| T1 | Wszystkie arkusze maja rok Y | lista, `--year 2025` | pobranie WSZYSTKICH lotow z 2025 (-1: 2, -2: 3, -3: 2, -4: 3 = 10 plikow kampanii) do `kampanie/`; dowiazania na najnowszy lot 84183 (-1, -2, -3 niepelny; -4 pelny); pomiar pokrycia dla -1, -2, -3 (najnowszy NIE); `Info:` 6.3 dla arkuszy, gdzie starszy lot ma wieksze pokrycie; `Warning:` E13 o niepelnych; podsumowanie "Downloaded 10 campaign files for 4 sheets"; kod 0 |
| T2 | Czesc arkuszy bez ZADNYCH danych | lista + arkusz morski, `--year 2025` | arkusz morski pominiety: `Warning: GUGiK nie ma danych dla 1 z 5 arkuszy (...) — pominiete (morze, obszar za granica)` (istniejacy R5), reszta jak T1, kod 0 |
| T3 | Arkusz ma dane tylko z lat NOWSZYCH | pojedynczy -2 z `--year 2018` (lata 2019..2026) | `Error:` (6.2) z `dostepne roczniki 2019, 2022, 2023, 2024, 2025, 2026`; podpowiedz `--min-year 2018` (rok 2018 i nowsze); kod 1; nic nie pobrano |
| T4 | Arkusz ma dane tylko z lat STARSZYCH | -1 z `--year 2026` (lata 2019, 2023, 2025) | `Error:` z lista lat; podpowiedz `--max-year 2026`; kod 1 |
| T5 | Jeden arkusz ma lata starsze I nowsze, zadnego w Y | lista, `--year 2024`: -2 i -4 OK (2024), -1 (2019, 2023, 2025) i -3 (2019, 2025) KONFLIKT | `Error:` wymienia -1 i -3 z ich latami; podpowiedz OBIE: `--min-year 2024` (2024 i nowsze) i `--max-year 2024` (2024 i starsze); kod 1; nic nie pobrano (takze -2 i -4) |
| T6 | Mieszanka: jeden arkusz tylko nowsze, inny tylko starsze | lista {-1, -3, -4} z `--year 2026`: -4 OK; -1 i -3 tylko starsze | podpowiedz `--max-year 2026`; kod 1 |
| T7 | Samo `--min-year Y` | lista, `--min-year 2026`: -2 i -4 OK (2026); -1, -3 KONFLIKT (tylko starsze) | `Error:` (P1 — dzis bylyby pominiete z `Warning:`); podpowiedz `--min-year 2025` (najnowszy rok wspolny konfliktowych arkuszy — 6.2); kod 1 |
| T8 | Samo `--max-year Y` | lista, `--max-year 2022` | strategia `all` (P3): wszystkie loty <= 2022 do `kampanie/` — -1: 2019; -2: 2022, 2019; -3: 2019; -4: 2022, 2019 = 6 plikow; dowiazania: -1 i -3 na 73021 (2019), -2 i -4 na 75162 (2022); kod 0; sidecar `request.max_year: 2022`, `request.campaigns: "all"` |
| T9 | Przedzial | lista, `--min-year 2023 --max-year 2024`: -1 -> 2023, -2 -> 2024, -3 KONFLIKT (2019, 2025), -4 -> 2024 | `Error:` dla -3: `dostepne roczniki 2019, 2025`; podpowiedz `--min-year 2023` (zdjecie gornej granicy) i `--max-year 2024` (zdjecie dolnej); kod 1 |
| T10 | `--year` + `--min-year` | `--year 2024 --min-year 2022` | `Error: --year wyklucza sie z --min-year/--max-year (--year Y to skrot --min-year Y --max-year Y)`; kod 1; przed siecia |
| T11 | `--year` + `--max-year` | `--year 2024 --max-year 2025` | jak T10 |
| T12 | `--min-year` > `--max-year` | `--min-year 2025 --max-year 2023` | `Error: --min-year (2025) nie moze byc wiekszy niz --max-year (2023)`; kod 1 |
| T13 | Rok poza 1900..2100 | `--max-year 2200` | `Error: --max-year musi byc liczba calkowita 1900..2100, otrzymano 2200` (jak dzis `--min-year`); kod 1 |
| T14 | Dwa loty w roku (bez `--campaigns`) | -1 z `--year 2025` | OBA loty do `kampanie/` (2025-04-27_83233 pelny, 2025-10-21_84183 niepelny); dowiazanie na 84183 (najnowszy, U8); pomiar pokrycia obu (najnowszy NIE); gdy 83233 ma wieksze pokrycie: `Info:` 6.3 i sidecar standardowy `extra.better_coverage: "83233"`, `extra.flights` z pokryciem obu; `Warning:` E13 (niepelny); "Downloaded 2 campaign files for 1 sheets"; kod 0 |
| T15 | Dwa loty w roku, jawne `--campaigns all` | -1 z `--year 2025 --campaigns all` | identycznie jak T14 (flaga redundantna, P3a) |
| T16 | Samo `--min-year` (U13) | lista, `--min-year 2024` | strategia `newest`: po jednym pliku — -1 i -3: 84183 (2025-10-21, niepelny), -2 i -4: 83998 (2026-04-05); `Warning:` E13 dla -1 i -3; kod 0; sidecar `request.min_year: 2024`, `request.campaigns: "newest"`, `extra.available_years` |
| T16a | `--campaigns all --min-year` | lista, `--campaigns all --min-year 2024` | -1: 2 loty (84183, 83233); -2: 5 (83998, 84183, 83233, 81468, 79091); -3: 2; -4: 5 = 14 plikow; dowiazania na najnowszy; pomiar pokrycia dla -1 i -3 (najnowszy NIE, > 1 lot); kod 0 |
| T26 | Jawne `--campaigns newest` + gorna granica | -1 z `--year 2025 --campaigns newest` (albo `--max-year 2025`) | `Error: --campaigns newest wyklucza sie z --year/--max-year — gorna granica roku pobiera wszystkie kampanie z przedzialu (pomin --campaigns)`; kod 1; przed siecia |
| T26a | Jawne `--campaigns newest` + `--min-year` | -1 z `--campaigns newest --min-year 2024` | jak T16 dla -1 (jeden lot 84183); kod 0 |
| T27 | Najnowszy lot w przedziale pelny (TAK) | -4 z `--year 2025` (84183 TAK) | 3 loty pobrane, dowiazanie na 84183, BEZ pomiaru pokrycia i bez `Info:` (U10 wyjatek); sidecary kampanii bez `extra.coverage` |
| T28 | Jeden lot w przedziale | -1 z `--year 2023` (jeden lot: 78047) | jeden plik kampanii, bez pomiaru, bez `Info:`; podsumowanie "1 campaign files for 1 sheets" |
| T17 | Wariant orto | N-34-139-A-c-1-1, `--product orto`, CIR, `--year 2025` | CIR ma lata 2011, 2014, 2017, 2022, 2024 -> KONFLIKT (RGB ma 2025, ale wariant jest osobnym filtrem); `dostepne roczniki` z puli CIR; kod 1 |
| T18 | Godlo CZ / obszar bez PL | `kartograf download CTES96 --year 2023` | `Error: CZ (CUZK) nie ma kampanii — --campaigns all/--min-year/--max-year/--year dotycza tylko PL`; kod 1; przed siecia |
| T19 | Obszar PL+CZ pod `auto` | `--bbox ... --country auto --year 2023` | `Info: --campaigns/--min-year/--max-year/--year dotycza tylko czesci PL (CZ: biezaca wersja danych CUZK)`; czesc PL wg tej tabeli; CZ biezaca |
| T20 | Wycinek `--target-crs` z flaga roku (P6) | `--bbox ... --target-crs EPSG:5514 --year 2024` (takze `--min-year`, `--max-year`) | `Error: --year nie dziala z --target-crs — wycinek sklada najnowsze kampanie, nazwa wycinka nie niesie roku` (nazwa flagi wg podanej); kod 1; przed siecia; nic nie pobrano |
| T21 | LAZ, rocznik w przedziale pokrywa to, co referencja | w2, `--product laz --year 2023` (referencja: kafel 2025 N-34-139-A-c-1-1-3-4; kafel 2023 ma ten sam godlo, czyli te sama rame) | pobranie kafla 2023; `Info:` o kaflach pominietych jak dzis; kod 0 |
| T21a | LAZ, rocznik pokrywa referencje dopiero kilkoma kaflami | w2, `--year 2022` (korekta 2026-10-10 po nagraniu dla `W2_BBOX`: rok 2022 ma tu DWA kafle PL-2000 `7.173.21.06.1` i `.06.2`; zaden sam nie pokrywa obszaru, razem tak; wczesniejszy pomiar "53 %" wynikal z fixtures nagranych dla mniejszego okna C13) | pobranie obu kafli 2022; kod 0. Konflikt P8 na czesci kafli referencji: obszar w3 (T22 na dwoch kaflach, 10.3) |
| T22 | LAZ, rocznik w usludze, brak kafli w czesci obszaru | w2, `--year 2024` (warstwa 2024 istnieje, w w2 pusta) | `Error: brak kafli LAZ z roku 2024 dla 1 z 1 kafli obszaru — nic nie pobrano:` / `  N-34-139-A-c-1-1-3-4 (2025, PL-1992): dostepne roczniki 2022, 2023, 2025` / podpowiedz `--min-year 2024` i `--max-year 2024`; kod 1 |
| T23 | LAZ, rocznik nieobecny w usludze | `--year 2017` na EVRF2007 (warstwy 2018..2026) | `Error: rocznik 2017 nie istnieje w usludze EVRF2007 (dostepne: 2026, ..., 2018)` — jak dzis, bez GetFeature; dla przedzialu bez wspolnego rocznika z usluga: `Error: przedzial 2010-2017 nie ma rocznika w usludze EVRF2007 (dostepne: ...)` |
| T24 | LAZ, obszar bez kafli w zadnym roku | bbox na morzu, `--year 2023` | jak dzis: `Error: No LAZ tiles found ...`, kod 1 (referencja pusta — nie ma z czym porownac) |
| T25 | LAZ, dwie dostawy NIE tego samego arkusza w jednym roku | Wroclaw `6.150.13.16.4` (ADR-029), domyslnie i `--max-year 2025` | obie zostaja (NIE nie pokrywa) — ADR-029 bez zmian; zostaje tez kafel 2024 PL-1992 `M-33-35-A-c-4-4-3-2`, ktorego nie pokrywa zaden kafel TAK. `--year 2025` = konflikt P8 (pomiar 2026-10-10): rok 2025 ma tu tylko dostawy NIE, referencja 2024 zostaje niepokryta; `Error:` wymienia ja z latami `2019, 2022, 2024, 2025 (tylko arkusze niepelne)` (dopisek: decyzja uzytkownika 2026-10-10) |

## 6. CLI: flagi, komunikaty, kody wyjscia

### 6.1 Flagi (`kartograf/cli/_parser.py`)

- `--year RRRR` — opis: "Tylko ten rok danych (PL: rok pozyskania
  `aktualnosc` NMT/NMPT/orto, `akt_rok` LAZ); skrot `--min-year RRRR
  --max-year RRRR`; wszystkie kampanie z roku; brak roku na ktoryms
  arkuszu/kaflu = blad przed pobraniem; nie dziala z --target-crs".
- `--min-year RRRR` — "Tylko PL: dolna granica roku danych (wlacznie);
  bez --campaigns all pobiera najnowsza kampanie i konczy sie bledem, gdy
  jest starsza; nie dziala z --target-crs".
- `--max-year RRRR` (NOWA) — "Tylko PL: gorna granica roku danych
  (wlacznie) — wszystkie kampanie nie pozniejsze niz RRRR, dowiazanie na
  najnowsza z nich; nie dziala z --target-crs".
- `--campaigns {newest,all}` — domyslnie sentinel (brak flagi; `default=None`
  jak `--resolution`): bez `--max-year`/`--year` = `newest`, z nimi = `all`
  (P3a); opis: "Kampanie GUGiK (tylko PL): newest = najnowsza kampania
  arkusza (default bez --max-year/--year), all = wszystkie kampanie do
  <segment>/kampanie/ (default i jedyna strategia z --year/--max-year);
  LAZ: all = bez deduplikacji pokrycia". Jawne `newest` z `--year`/
  `--max-year` = T26.
- Walidacja przed siecia, w `cmd_download` tam, gdzie dzis
  `validate_campaign_args`: T10-T13, T20, T26.

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

### 6.3 `Info:` o locie o wiekszym pokryciu (P4, U10)

Tylko w przeplywie z przedzialem i strategia `all`; tylko dla arkuszy, ktore maja w przedziale
> 1 lot, ktorych najnowszy lot NIE jest pelny (TAK) i dla ktorych inny
pobrany lot ma zmierzone pokrycie WIEKSZE niz najnowszy; stderr (takze z
`-q`), raz na zadanie, po pobraniu (pomiar wymaga plikow):

```
Info: dla 2 arkuszy starszy lot z przedzialu ma wieksze pokrycie niz najnowszy (dowiazanie wskazuje najnowszy):
  N-34-139-C-a-3-1: dowiazanie 2025-10-21_84183 (niepelny, pokrycie 0,9 %); wieksze pokrycie: 2025-04-27_83233 (pelny, 99,8 %)
  N-34-139-C-a-3-3: dowiazanie 2025-10-21_84183 (niepelny, 12,4 %); wieksze pokrycie: 2025-04-27_83233 (pelny, 100 %)
```

Lista do 10 arkuszy, dalej `... i N innych`. Wartosci procentowe z
`extra.coverage` (4.4). Bez strategii `all` (`newest`, takze z samym
`--min-year`) komunikatu NIE ma — pobierany jest jeden lot i nie ma czego
porownac. Q4 rozstrzygniete (U12): stderr.

### 6.4 Pozostale komunikaty

- T10: `Error: --year wyklucza sie z --min-year/--max-year (--year Y to
  skrot --min-year Y --max-year Y)`.
- T12: `Error: --min-year (2025) nie moze byc wiekszy niz --max-year (2023)`.
- T13: tekst `validate_campaign_args` z nazwa parametru zamieniona na flage
  (jak dzis `min_year` -> `--min-year`, `download_cmd.py:888`).
- T18/T19: rozszerzone teksty `_reject_campaign_opts_without_pl`
  (`download_cmd.py:252-264`) — wyliczenie flag jak w tabeli.
- T20 (P6): `Error: <flaga> nie dziala z --target-crs — wycinek sklada
  najnowsze kampanie, nazwa wycinka nie niesie roku`; dla `--year`
  zastepuje dzisiejszy komunikat `_reject_laz_only_opts`.
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
| kampania NMT/NMPT/orto | `extra.coverage` (NOWE) | zmierzony udzial waznych pikseli lotu, 0..1 (4.4); tylko gdy mierzono (arkusz z > 1 lotem w przedziale, najnowszy nie TAK); orto bez nodata/alfa: brak pola |
| j.w. | `request.campaigns` | strategia ROZWIAZANA z sentinela (P3a): `"all"` albo `"newest"` (samo `--min-year`) — sidecar opisuje, co zrobiono, nie jak wpisano flage |
| sciezka standardowa (kopia sidecara kampanii + `link`) | `extra.flights` (NOWE) | wszystkie loty arkusza z przedzialu, malejaco wg klucza ADR-028: `[{"id", "date", "full_sheet", "coverage"}]` (`coverage` tylko gdy mierzono); tylko w przeplywie z przedzialem i strategia `all` |
| j.w. | `extra.better_coverage` (NOWE) | `id` lotu o NAJWIEKSZYM pokryciu, gdy jest ono wieksze niz pokrycie lotu dowiazania (U10); brak pola = brak lepszego lotu albo najnowszy pelny (TAK) |
| kafel LAZ | `request.min_year`, `request.max_year`, `request.year` | gdy podane (`year` dzis jest; `max_year` nowe) |
| kafel LAZ | `extra.acquisition_date` (NOWE), `extra.full_sheet` (NOWE) | `akt_data`, `czy_ark_wypelniony` kafla — dwie dostawy tego samego arkusza w roku (T25) roznia sie dzis tylko `url` |

`request` opisuje POBRANIE (ARCHITECTURE 3.2) — przy ponownym uruchomieniu z
innym przedzialem, ktory wybiera te sama kampanie, plik jest pomijany,
a `request` zostaje z pierwszego pobrania. `extra.parent_request(s)` (N4)
nie niesie flag roku — `_build_parent_request` opisuje obszar zadania
(bbox, uklad, kraje) i tak zostaje (korekta przy planie 2026-10-10:
wczesniejsza wersja specu zakladala, ze niesie `min_year`).

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

- `DownloadManager(..., campaigns=None, min_year=None, max_year=None)`:
  `campaigns=None` (nowy domyslny sentinel) = `"newest"` bez `max_year`,
  `"all"` z `max_year`; jawne `"newest"` z `max_year` = `ValidationError`,
  z samym `min_year` dozwolone (P3a); wlasciwosc `campaigns` zwraca
  strategie ROZWIAZANA; wlasciwosc `max_year`;
  `validate_campaign_args(campaigns, min_year, max_year)` przyjmuje `None`
  i sprawdza wartosci i `min_year <= max_year`; regula P3a jest w osobnej
  `resolve_campaign_strategy(campaigns, max_year)` (korekta przy planie:
  `validate_campaign_args` sluzy tez LAZ, gdzie jawne `newest` z gorna
  granica jest dozwolone, Q8). Obie poza `__all__` `kartograf/__init__.py`.
- Przeplyw z jakimkolwiek przedzialem (`min_year` lub `max_year` podane),
  tylko provider z `supports_campaigns is True`:
  1. **Faza sprawdzania** (`check_year_range(godla) -> YearRangeCheck`,
     publiczna, rownolegla jak `_download_many`): dla kazdego arkusza
     `resolve_campaigns(godlo, campaigns="all", ...)` bez granic (pelna
     lista, `campaigns_cache`); klasyfikacja 4.2; wynik
     `YearRangeCheck(selected: dict[godlo, list[SkorowidzRecord]],
     no_data: dict[godlo, NoCoverageError], conflicts: dict[godlo,
     tuple[int, ...]], failed: dict[godlo, DownloadError])`.
     `selected` = przy `all` WSZYSTKIE rekordy w przedziale, malejaco po
     kluczu ADR-028; przy `newest` (samo `min_year`) jeden, najnowszy
     rekord (P3).
  2. `conflicts` niepuste -> `YearRangeError` (wszystkie arkusze, z
     podpowiedziami); `failed` niepuste -> `DownloadError` (P9); nic nie
     pobrane. Kolejnosc: najpierw `failed` (nie wiadomo, czy konflikt jest
     pelny), potem `conflicts`.
  3. **Faza pobierania**: jak dzisiejszy `_fetch_campaigns` dla `all`
     (`manager.py:700-863`), ale z rekordami z fazy 1 (bez drugiego
     `resolve_campaigns`); `no_data` -> `no_coverage` wyniku (R5, jak dzis);
     dowiazanie na najnowszy lokalny lot (`max` po `sort_key`,
     `ensure_standard_link` — bez zmian, U8); sidecar kampanii z polami z
     sekcji 7.
  4. **Faza pomiaru pokrycia** (tylko `all`, per arkusz, po skompletowaniu jego lotow):
     warunek U10 (> 1 lot w przedziale, najnowszy nie TAK) -> pomiar 4.4
     kazdego lotu bez `extra.coverage` w sidecarze, dopisanie `extra.coverage`
     do sidecara kampanii i `extra.flights`/`extra.better_coverage` do
     sidecara standardowego; wynik `SheetFetch.better_coverage: str | None`
     i `DownloadResult.better_coverage: dict[godlo, str]` (id lotu) dla CLI
     (6.3). Blad pomiaru (np. nieczytelny ASC) = `logger.warning`, bez
     porazki arkusza (plik juz zweryfikowany formatowo).
- `download_sheet`, `download_sheets`, `download_hierarchy`: z przedzialem
  moga rzucic `YearRangeError` i `DownloadError` fazy 1 PRZED pierwszym
  pobraniem (dokumentacja: dotad lista nie rzucala `DownloadError`).
  `last_result` po fazie 1 z bledem = `None`.
- Bez przedzialu: przeplyw bez zmian (w tym `record_cache` i fallback I-1).
- `_write_campaign_sidecar`: `request.campaigns` (rozwiazana),
  `request.max_year`/`year`, `extra.available_years`; po pomiarze
  `extra.coverage` (kampania) oraz `extra.flights`/`extra.better_coverage`
  (sciezka standardowa) — sekcja 7.

### 8.3 Provider skorowidza (`providers/pl/skorowidz.py`)

- `resolve_campaigns(godlo, *, campaigns=None, min_year=None,
  max_year=None, timeout=None)`: sentinel jak w `DownloadManager` (P3a;
  jawne `"newest"` z `max_year` = `ValidationError`); z przedzialem —
  pelna lista (`_resolve_all` bez pomijania warstw), filtr
  `min_year <= rok <= max_year`, zwrot WSZYSTKICH rekordow z przedzialu
  (malejaco) przy `all` albo `[najnowszy]` przy `newest`; brak rekordu
  w przedziale przy niepustej liscie -> `YearRangeError({godlo: lata})`;
  pusta lista -> `NoCoverageError` jak dzis. `_meets_min_year` ->
  `_in_year_range(record, min_year, max_year)`.
- `_resolve_all`: parametr `min_year` i pomijanie warstw usuniete (P5);
  `scanned_from`, `_covers`, `_partial_scan_no_coverage` usuniete; wpis
  `campaigns_cache` z `scanned_from` innym niz `None` = chybienie (jak wpisy
  sprzed ADR-031, `skorowidz.py:594-599`).
- `available_years(godlo) -> tuple[int, ...]` (publiczna, z listy
  `_resolve_all`) — dla Hydrografu/QGIS: "jakie lata ma ten arkusz".

### 8.4 Wycinek PL (`download/cutout.py`, CLI)

- Biblioteka bez zmian: `prepare_pl_cutout`, `download_pl_cutout`,
  `run_pl_cutout` nie maja parametrow roku i skladaja najnowsze kampanie
  (P6). `DownloadManager` tworzony przez wycinek dostaje `campaigns=None`
  bez granic, czyli `newest`.
- CLI: `_reject_campaign_opts_with_target_crs` odrzuca `--campaigns all`,
  `--min-year`, `--max-year` i `--year` (T20, 6.4) przed siecia; dla
  `--year` zastepuje odrzucenie z `_reject_laz_only_opts`.

### 8.5 LAZ (`providers/pl/gugik_laz.py`, `download/laz.py`)

- `select_tiles(bbox, year=None, min_density=None, ..., campaigns="newest",
  min_year=None, max_year=None)`: domyslnie `newest` ZAWSZE (bez sentinela; takze
  z przedzialem — LAZ nie ma `kampanie/`, a ADR-029 zachowuje loty
  niepelne, P3a); jawne `newest` z przedzialem dozwolone (dzisiejsze
  zachowanie); `all` = bez deduplikacji w przedziale; Q8 rozstrzygniete (U12).
  `year=Y` == `min_year=max_year=Y`;
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
- `discover_tiles` (alias `select_tiles(...).tiles`) dostaje `min_year`
  i `max_year` (keyword-only; `min_year` — decyzja uzytkownika 2026-10-10).

### 8.6 CLI (`cli/download_cmd.py`)

- `_campaign_opts` -> `(campaigns, min_year, max_year)`; `--year Y` mapowany
  w jednym miejscu (`cmd_download`, po T10-T13) na `min_year = max_year = Y`
  i tak przekazywany do torow godla, hierarchii, listy
  `--bbox`/`--geometry` i LAZ (wycinek odrzuca flagi roku wczesniej, P6).
  `_cmd_download_laz` przestaje czytac `args.year` osobno.
  `_reject_laz_only_opts` traci `--year` (zostaje `--min-density`).
- `--campaigns` sentinel rozwiazywany w tym samym miejscu (P3a): `None` ->
  `all` z `--max-year`/`--year`, inaczej `newest`; jawne `newest` +
  `--max-year`/`--year` = T26 (produkty arkuszowe; LAZ: `newest` dozwolone
  — ADR-029 w obrebie przedzialu). Straze CZ
  (`_reject_campaign_opts_without_pl`) dzialaja na strategii ROZWIAZANEJ
  i na kazdej fladze roku (obszar PL+CZ z `--year` daje `Info:` jak dotad
  z `all`).
- Podsumowanie i `Info:` 6.3 w `_finish_pl_sheets` i w torze pojedynczego
  godla (jak `_print_campaign_summary` dla `all` dzis;
  `DownloadResult.better_coverage`).
- `_reject_campaign_opts_without_pl` / `_reject_campaign_opts_with_target_crs`
  wg P7/P6.
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
| `test_resolve_campaigns_year_2025_c14_returns_both_flights` | provider | T14: -1 -> [84183, 83233] (malejaco, klucz ADR-028); -2 -> 3 loty |
| `test_resolve_campaigns_explicit_newest_with_max_year_is_validation_error` | provider | T26/P3a: `campaigns="newest", max_year=2025` -> `ValidationError`; `campaigns="newest", min_year=2024` -> `[84183]`; `campaigns=None, max_year=2025` -> lista |
| `test_resolve_campaigns_year_2024_c14_conflict_lists_years` | provider | T5: -1 -> `YearRangeError` z (2019, 2023, 2025) |
| `test_resolve_campaigns_max_year_2022_c14` | provider | T8: -1 -> 2019 (73021), -2 -> 2022 |
| `test_resolve_campaigns_range_queries_all_layers_no_partial_scan` | provider | P5: `queried_layers` = 4 warstwy takze z `min_year=2026`; wpis cache bez `scanned_from`; stary wpis `scanned_from=2024` = chybienie |
| `test_available_years_c14` | provider | 8.3: -2 -> (2019, 2022, 2023, 2024, 2025, 2026) |
| `test_orto_cir_year_2025_conflict_rgb_has_it` | provider | T17 |
| `test_manager_year_2024_list_stops_before_any_download` | manager | T5: `download_sheets` 4 arkusze -> `YearRangeError` z 2 arkuszami; `download_record` nie wywolany; brak plikow w `kampanie/` |
| `test_manager_year_2025_list_downloads_every_flight_links_newest` | manager | T1: 10 plikow kampanii, `last_result.campaign_files`, dowiazania na 84183, sidecar `request.campaigns: "all"`, `request.year/min_year/max_year`, `extra.available_years`, `extra.flights` |
| `test_manager_coverage_measured_only_when_newest_partial` | manager | T14 vs T27: stub `download_record` zapisuje ASC z roznym udzialem NODATA; -1: oba loty dostaja `extra.coverage`, sidecar standardowy `extra.better_coverage: "83233"`, `last_result.better_coverage`; -4 (najnowszy TAK): brak pomiaru i pol |
| `test_manager_coverage_newest_has_more_data_no_info` | manager | U10: najnowszy niepelny, ale z wiekszym pokryciem niz starszy -> `extra.flights` z pokryciem, bez `better_coverage` |
| `test_manager_single_flight_in_range_no_measurement` | manager | T28 |
| `test_manager_explicit_newest_with_max_year_rejected` | manager | T26: `DownloadManager(campaigns="newest", max_year=2024)` -> `ValidationError`; `campaigns=None, max_year=2024` -> `manager.campaigns == "all"`; `campaigns=None, min_year=2024` -> `"newest"` |
| `test_manager_min_year_alone_downloads_newest_only` | manager | T16 (U13): 4 pliki, po jednym na arkusz, bez `kampanie/` innych lotow, bez pomiaru; `request.campaigns: "newest"`, `extra.available_years` |
| `test_coverage_of_asc_counts_nodata` | campaigns | 4.4: ASC z `NODATA_value` i bez (domyslne -9999), wynik 0..1 |
| `test_manager_year_with_no_data_sheet_is_skipped` | manager | T2: `empty.body` dla 5. arkusza -> `no_coverage`, reszta pobrana |
| `test_manager_min_year_alone_conflict_is_error_not_skip` | manager | T7 (P1): zmiana wobec `test_min_year_newest_no_coverage_in_list_is_no_coverage_status` (`tests/test_manager_campaigns.py:678`) — ten test do przepisania |
| `test_manager_check_failure_aborts_whole_task` | manager | P9: jedna warstwa 5xx dla jednego arkusza -> `DownloadError`, zero pobran |
| `test_manager_explicit_all_with_range_same_as_default` | manager | T15: `campaigns="all"` z `--year` = ten sam wynik co `campaigns=None`; T16a: `campaigns="all", min_year=2024` = 14 plikow |
| `test_manager_without_range_unchanged_uses_record_cache` | manager | regresja: `newest` bez flag nie dotyka `campaigns_cache`, fallback I-1 dziala |
| `test_cli_year_nmt_list_error_message_and_hints` | CLI | T5: dokladny tekst 6.2, kod 1, `MetadataCache` zamkniety |
| `test_cli_year_conflicts_with_min_max` | CLI | T10-T12, przed siecia (`GugikProvider` nie tworzony) |
| `test_cli_year_cz_godlo_rejected` / `test_cli_year_pl_cz_info` | CLI | T18/T19 (wzor: istniejace testy `--min-year` dla CZ w `tests/test_cli.py`) |
| `test_cli_year_info_better_coverage` | CLI | T14: tekst 6.3 (stderr, takze z `-q`), kod 0 |
| `test_cli_explicit_newest_with_year_rejected` | CLI | T26: tekst, kod 1, przed siecia, dla `--year` i `--max-year`; `--campaigns newest --min-year` przechodzi (T26a); `--campaigns all --year` = jak bez `--campaigns` |
| `test_cli_year_flags_rejected_with_target_crs` | CLI | T20: `--year`, `--min-year`, `--max-year` z `--target-crs` -> tekst 6.4, kod 1, `GugikProvider` nie tworzony |
| `test_laz_year_2023_w2_covers_reference` | LAZ | T21: kafel 2023 wybrany; `test_c13_year_2023_returns_the_single_older_tile` (`tests/test_real_gugik_responses.py:614`) — wynik kafli bez zmian, odpytane wszystkie roczniki |
| `test_laz_year_2022_two_tiles_together_cover_w2_reference` | LAZ | T21a (korekta 2026-10-10): dwa kafle 2022 wybrane, bez bledu |
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

Stan nagran (2026-10-10, `tests/fixtures/gugik_laz/real_2026_10_10/`,
`tests/fixtures/gugik_skorowidz/real_2026_10_10/orto/`): orto —
N-33-130-D-d-1-4 (Poznan, 2025: dwa loty RGB 0,25 m); LAZ w3 —
`627706,479258,628006,479558` (`--year 2019`: kafel tylko z nowszymi
latami; `--year 2025`: kafel tylko ze starszym); LAZ Wroclaw —
`6.150.13.16.4`; NMT PL-2000 z dwoma lotami w roku — NIE znaleziony
(112 arkuszy 1:2000 w 6 miastach, okolice c14 i `6.129.30`: zaden rok
z > 1 lotem), test nie powstal.

Nagrywanie wg `tests/fixtures/gugik_skorowidz/real_2026_10_06/README.md`
(pliki bez edycji; dane poza repo, tylko wybrany podzbior do fixtures;
zadnych sciezek prywatnych w README).

## 11. Dokumentacja i CHANGELOG

### 11.1 `### Dodane`

- `--max-year RRRR` (NMT, NMPT, orto, LAZ): gorna granica roku danych;
  `--year RRRR` dziala teraz takze dla NMT/NMPT/orto (dotad `Error:`) i
  jest skrotem `--min-year RRRR --max-year RRRR`; brak roku na ktoryms
  arkuszu/kaflu zatrzymuje zadanie PRZED pobraniem z lista dostepnych lat i
  podpowiedzia; arkusze bez zadnych danych sa pomijane z `Warning:` jak
  dotad. Z `--year`/`--max-year` pobierane sa WSZYSTKIE kampanie (loty)
  z przedzialu do `kampanie/` (strategia `all`), a sciezka standardowa
  wskazuje najnowsza z nich (regula bez zmian); samo `--min-year` pobiera
  jak dotad jedna, najnowsza kampanie.
- Pokrycie lotu (`extra.coverage`, udzial waznych pikseli) mierzone po
  pobraniu dla arkusza, ktory ma w przedziale kilka lotow, a najnowszy nie
  jest pelny; gdy starszy lot ma wieksze pokrycie — `Info:` w CLI i
  `extra.flights`/`extra.better_coverage` w sidecarze sciezki standardowej.
- Biblioteka: `DownloadManager(max_year=)`, `download_laz_area(max_year=)`,
  `select_tiles(max_year=)`, `resolve_campaigns(max_year=)`,
  `available_years(godlo)`; nowy wyjatek
  `YearRangeError(DownloadError)` z `sheets` (godlo -> lata), `min_year`,
  `max_year`, `hints`.
- Sidecar: `request.max_year`, `request.year` (gdy min == max),
  `extra.available_years`, `extra.coverage` (kampania NMT/NMPT/orto),
  `extra.flights`, `extra.better_coverage` (sciezka standardowa);
  LAZ `extra.acquisition_date`, `extra.full_sheet`.

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
- `--max-year`/`--year` (NMT/NMPT/orto) pobieraja WSZYSTKIE kampanie
  z przedzialu (jak `--campaigns all`), a jawne `--campaigns newest` z nimi
  to `Error:`; samo `--min-year` i `--campaigns newest --min-year` dzialaja
  jak dotad (jedna, najnowsza kampania). Biblioteka:
  `DownloadManager(campaigns="newest", max_year=...)` i
  `resolve_campaigns(campaigns="newest", max_year=...)` rzucaja
  `ValidationError`; domyslna wartosc `campaigns` to `None` (rozwiazywana:
  `all` z `max_year`, inaczej `newest`). Co zrobic: nic dla wywolan bez
  `max_year`; z `max_year` usun `campaigns="newest"` — jeden plik na
  arkusz daje sciezka standardowa (dowiazanie na najnowszy lot
  z przedzialu), pozostale loty leza w `kampanie/`.
- `--year`, `--max-year` z `--target-crs` = `Error:` (jak dotad
  `--min-year`). Co zrobic: nic; wycinek sklada najnowsze kampanie.
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
  przedzialem), (i) (nowe pola), (j)/[Q2] (odrzucenie rozszerzone na
  `--year`/`--max-year`); ADR-029 errata 1 (`--year` == przedzial,
  sprawdzenie pokrycia referencji).
  CRLF zachowac.
- `docs/ARCHITECTURE.md` 3.2 (pola), 4.1, 4.3, 4.6, 4.7; `docs/USAGE.md`
  sekcje 1 (przyklady) i 4 (kampanie); `docs/SCOPE.md` 2 (ograniczenia:
  CZ bez roku); `docs/PROGRESS.md`.

## 12. Pytania otwarte dla uzytkownika

| # | Pytanie | Propozycja w specu |
|---|---|---|
| Q1 | Czy regula "konflikt = stop calego zadania" ma dotyczyc takze SAMEGO `--min-year` i SAMEGO `--max-year` (P1), czy tylko `--year`? Dzis `--min-year` pomija arkusz z `Warning:` (ADR-030 (f)). | ROZSTRZYGNIETE 2026-10-09 (U12): tak, kazdy przedzial. |
| Q2 | ROZSTRZYGNIETE 2026-10-09 (U8-U11), doprecyzowane 2026-10-10 (U13): regula sciezki standardowej bez zmian (najnowszy lot, ADR-028 + ADR-030 (d)); `--year`/`--max-year` pobieraja wszystkie loty z przedzialu (`all` zawezone), samo `--min-year` jeden najnowszy; `Info:` + sidecar, gdy starszy lot ma wieksze zmierzone pokrycie, a najnowszy nie jest TAK; jawne `--campaigns newest` z `--year`/`--max-year` = `Error:` (P3a). | — |
| Q2a | OPCJA (nierozstrzygnieta, U11): dodatkowa flaga zmieniajaca regule domyslna dowiazania — `--full-sheet` (dowiazanie na najnowszy lot z `calyArkuszWypelnionyTrescia = TAK`) albo `--min-coverage N` (dowiazanie na najnowszy lot o zmierzonym pokryciu >= N %). Jak by to weszlo: pomiar 4.4 juz istnieje w przeplywie z przedzialem; flaga przelaczalaby KLUCZ dowiazania z `(aktualnosc, dt_pzgik, url)` na `(spelnia prog, aktualnosc, dt_pzgik, url)` i wymagalaby (a) pobrania wszystkich lotow przed wyborem (z przedzialem — juz tak; bez przedzialu `newest` musialby pobierac loty az do pierwszego spelniajacego prog, od najnowszego), (b) zlamania ADR-030 (d) "dowiazanie nigdy wstecz" przy zmianie progu miedzy uruchomieniami (albo zapisu progu w `extra.link_rule` i przestawiania tylko przy tej samej regule), (c) orto bez nodata/alfa = prog niemierzalny. | Rekomendacja: NIE w tym specu — backlog 0.7.2 (c) proponuje zamiast zmiany reguly DRUGIE dowiazanie do najnowszego pelnego lotu (osobne drzewo), co nie lamie ADR-030 (d); rozstrzygniecie przy specu (c). Tu wystarczy pomiar + `Info:` + `extra.flights`. |
| Q3 | Wycinek `--target-crs` z przedzialem: wspierac z sufiksem `_y<...>` w nazwie, czy utrzymac odrzucenie z errata 1 [Q2] (teraz dla trzech flag)? | ROZSTRZYGNIETE 2026-10-09 (U12): odrzucenie dla trzech flag (P6). |
| Q4 | `Info:` o wielu lotach w przedziale (6.3): zawsze na stderr (takze z `-q`), czy tylko w logu (`logger.info`)? | ROZSTRZYGNIETE (U12): stderr, jak `Info:` o kaflach LAZ. |
| Q5 | Awaria skorowidza dla jednego arkusza w fazie sprawdzania: przerwac cale zadanie (P9), czy sprawdzic reszte, pobrac ja i zglosic ten arkusz jako porazke (kod 1, wynik czesciowy)? | ROZSTRZYGNIETE (U12): przerwac. |
| Q6 | Usunac skan czesciowy `all --min-year` (P5; koszt 1-3 zapytania/arkusz/7 dni), czy zachowac go dla `all --min-year` bez `--max-year` i akceptowac, ze komunikat konfliktu nie wymieni lat starszych od granicy? | ROZSTRZYGNIETE (U12): usunac. |
| Q7 | LAZ: czy czesc obszaru bez kafli w ZADNYM roczniku ma dostac `Warning:` (analog U3 dla arkuszy)? Dzis LAZ milczy (obszar nie jest lista arkuszy). | ROZSTRZYGNIETE (U12): bez zmian (poza zakresem). |
| Q8 | LAZ z flaga roku: zostawic ADR-029 w obrebie przedzialu (pelne powtorzenia tej samej ramy deduplikowane, loty niepelne zawsze zostaja; jawne `newest` dozwolone) czy pobierac WSZYSTKIE kafle z przedzialu bez deduplikacji (`all`)? | ROZSTRZYGNIETE (U12): zostawic ADR-029. |
