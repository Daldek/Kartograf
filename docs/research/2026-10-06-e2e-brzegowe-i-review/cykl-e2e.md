# Cykl testu E2E: przypadki brzegowe danych GUGiK

**Dokument żywy.** Koordynator aktualizuje go w trakcie rundy: dopisuje nowe
wymagania, zmienia stare i notuje każdą zmianę w sekcji „Historia zmian”.
Agenci wykonawczy czytają go jako kontrakt, ale go nie edytują: swoje wyniki
zapisują we własnych raportach.

- **Runda:** 2026-10-06, przed wydaniem 0.7.0, `develop` od `fef7bf0`
- **Dane:** `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/`
  (rastry, LAZ, surowe odpowiedzi serwera). Raporty `.md` trafiają do
  tego katalogu w repo.
- **Równolegle:** code review (Fable) — duplikacje, overengineering,
  niespójności deklaracji z działaniem (`review-*.md`).

## 1. Cel

Sprawdzić w praktyce, na prawdziwych danych GUGiK, trzy rzeczy:

1. **Wybór pliku arkusza** (ADR-028): czy dla nietypowych arkuszy program
   bierze plik, który według reguły powinien wygrać: zgodne godło, układ
   i rozdzielczość, potem najnowsza `aktualnosc`, potem `dt_pzgik`, potem URL.
2. **Sidecary `<plik>.meta.json`:** czy każde pole opisuje FAKTYCZNY plik,
   a nie to, o co poproszono (rozdzielczość, układ poziomy i pionowy,
   nodata, źródło, kampania, licencja, braki).
3. **Różnice wersji danych:** roczniki, kampanie, warstwy zbiorcze
   („iStarsze”, „Starsze”), KRON86 vs EVRF2007, PL-1992 vs PL-2000, 1 m
   vs 5 m vs 0,5 m, RGB vs CIR, lata i gęstości LAZ.

Test nie ma powtarzać rundy 2026-09-30 (11 PASS). Szuka przypadków,
których tamta runda nie dotknęła.

## 2. Pełny cykl (fazy)

| Faza | Co | Wynik |
|------|----|-------|
| F0 | **Przygotowanie.** `df -h <katalog-danych>`, `git rev-parse HEAD`, CLI z korzenia repo (cache SQLite lokalnie), `--output` zawsze na katalog danych. Przy rozpoznaniu wyboru pliku `--force`, żeby cache rekordów nie maskował zmian. | Nagłówek raportu |
| F1 | **Rozpoznanie danych.** Surowe zapytania do skorowidza GUGiK (WMS GetCapabilities, GetFeatureInfo `text/html`), WFS LAZ, nagłówki plików (HEAD). Szukamy arkuszy z katalogu C (sekcja 3). Surowe body zapisujemy na katalog danych (`raw/<przypadek>/...`). | Lista kandydatów z uzasadnieniem |
| F2 | **Wyrocznia przed uruchomieniem.** Z surowych rekordów, ręcznie i NIEZALEŻNIE od kodu, wyprowadzamy oczekiwany wynik: który URL wygra, jaka `aktualnosc`, rozdzielczość, układ, pion, kod wyjścia, komunikat. Zapisujemy to PRZED uruchomieniem CLI. | Kolumna „oczekiwane” |
| F3 | **Wykonanie.** CLI (albo API biblioteki, gdy CLI nie daje dostępu). Zapisujemy pełną komendę, kod wyjścia, stderr (`Info:`/`Warning:`/`Error:`) i czas. | Kolumna „faktyczne” |
| F4 | **Weryfikacja trójstronna:** rekord źródłowy ↔ plik na dysku ↔ sidecar. Lista kontrolna W1–W12 (sekcja 4). | Tabela zgodności |
| F5 | **Klasyfikacja:** PASS / FAIL / UWAGA / BLOKADA (sekcja 5). | Werdykt per przypadek |
| F6 | **Sprzężenie zwrotne.** Każdy FAIL i UWAGA → nowe albo zmienione wymaganie w sekcji 6 (koordynator). | Rejestr wymagań |
| F7 | **Regresja offline.** Każdy FAIL i każdy nowy wzorzec danych → fixtura z SUROWEJ odpowiedzi (`tests/fixtures/gugik_skorowidz/`) + test offline. Dowód: test pada na kodzie bez naprawy (mutacja albo stan sprzed poprawki). | Testy + dowody mutacyjne |
| F8 | **Naprawa** potwierdzonych błędów (TDD: test z F7 najpierw czerwony). | Commity |
| F9 | **Ponowny przebieg na żywo** tylko dla przypadków FAIL po naprawie. | Werdykt końcowy |

Zasada nadrzędna: **żaden wniosek o błędzie bez sprawdzenia danych
u źródła** (pokrycie 1 m i 5 m się nie pokrywa, warstwy mają opóźnienia).
Każdy FAIL musi mieć surowy rekord skorowidza albo nagłówek pliku jako dowód.

## 3. Katalog przypadków brzegowych (C)

Agent szuka realnych arkuszy dla każdego punktu. Jeśli w danych GUGiK
przypadek nie występuje, zapisuje to jako wynik („nie znaleziono w N
sprawdzonych arkuszach”), a nie pomija go po cichu.

**Wybór pliku arkusza (NMT / NMPT):**
- **C1** Kilka kampanii jednego arkusza w tej samej warstwie (różne
  `aktualnosc`): wygrywa najnowsza.
- **C2** Remis `aktualnosc`: rozstrzyga `dt_pzgik`, potem URL. Szukamy
  arkusza z dwoma rekordami tego samego dnia.
- **C3** Pliki 0,5 m i 1 m (albo 1 m i 5 m) dla tego samego godła:
  filtr rozdzielczości.
- **C4** Arkusz obecny tylko w warstwie zbiorczej („2023iStarsze”,
  „2022iStarsze”): przejście przez warstwy bez błędu.
- **C5** Nowsza kampania z niepełnym arkuszem, starsza z pełnym
  (deklaracja: wygrywa najnowsza niezależnie od flagi pełnego arkusza):
  zmierzyć odsetek nodata i ocenić konsekwencje.
- **C6** Godła PL-2000: arkusze przy granicy stref 5/6/7/8, skale 1:5000,
  1:2000, 1:1000, 1:500; 1:10000 bez własnego pliku (podpowiedź `--scale`).
- **C7** KRON86 vs EVRF2007 dla tego samego arkusza: pion w sidecarze,
  różnica wysokości (oczekiwane kilkanaście cm, stała w arkuszu).
- **C8** NMT 5 m: arkusz w najstarszej warstwie, arkusz z 5 m bez 1 m
  i odwrotnie.
- **C9** Nietypowe pliki: rozszerzenie wielkimi literami (`.ASC`), `.zip`,
  `.tif` zamiast `.asc`, inna nazwa pliku niż godło.
- **C10** Arkusz przy morzu lub granicy państwa: częściowe pokrycie,
  `∅`, nodata.
- **C11** Nagłówek ASC: `xllcorner` vs `xllcenter`, `cellsize` niecałkowite,
  różne `NODATA_value`. Sidecar `nodata` ma odpowiadać plikowi.
- **C16** NMPT: opóźnienie warstw (2025 vs 2026), KRON86/EVRF2007.

**Ortofotomapa:**
- **C12** Arkusz z RGB i CIR w tej samej kampanii; różne rozdzielczości
  (0,05 / 0,10 / 0,25 m) dla jednego godła; rocznik 2026 vs „Starsze”.

**LAZ:**
- **C13** Kafle z kilku lat i o różnej gęstości dla jednego obszaru
  (`--year`, `--min-density`); `uklad_xy` 1992 i 2000 w jednym obszarze;
  KRON86 vs EVRF2007.

**Wycinek i cache:**
- **C14** Wycinek `--target-crs` z arkuszy różnych kampanii i lat:
  `extra.sheet_sources`, `missing_sheets`, `off_grid_sheets`.
- **C15** Cache rekordów: drugie uruchomienie bez `--force` (oczekiwane:
  bez zapytań do skorowidza, ten sam plik); `--force` po zmianie kampanii.
- **C17** Ponowne uruchomienie (skip): plik i sidecar nienaruszone,
  `parent_requests` dopisane tam, gdzie deklarowane.

## 4. Lista kontrolna weryfikacji (W)

Dla każdego pobranego pliku:

- **W1** URL w `extra.source` = URL rekordu wskazanego przez wyrocznię (F2).
- **W2** `aktualnosc` (i inne pola źródła) w sidecarze = rekord źródłowy.
- **W3** Rozdzielczość pliku (nagłówek ASC / GeoTIFF) = żądana = opis
  w sidecarze.
- **W4** Układ poziomy w sidecarze zgodny z FAKTYCZNYMI współrzędnymi
  pliku (EPSG:2180 vs 2176–2179 — zakres X/Y strefy).
- **W5** Pion w sidecarze = pion warstwy, z której pochodzi rekord
  (KRON86 = EPSG:9650; EVRF2007 dla PL wg deskryptora).
- **W6** `nodata` w sidecarze = `NODATA_value` / nodata pliku.
- **W7** Ścieżka zgodna z ADR-026 (`<produkt>/<kraj>_<uklad>_..._<vcrs>`),
  `<uklad>` z godła pliku (LAZ: z `uklad_xy` kafla).
- **W8** Zasięg pliku pokrywa godło (bbox arkusza z `kartograf parse`).
- **W9** `request` w sidecarze opisuje faktyczne żądanie (godło/bbox,
  rozdzielczość, pion).
- **W10** Licencja i atrybucja obecne; `kartograf_version` zgodna.
- **W11** Kod wyjścia i komunikaty zgodne z deklaracją w CLAUDE.md
  (sekcje „Skorowidz GUGiK”, „Lista arkuszy PL”, „Wycinek PL”).
- **W12** Ponowne uruchomienie: skip bez zmiany pliku; `--force` pobiera
  ponownie i aktualizuje sidecar.

## 5. Klasyfikacja wyników

- **PASS** — wynik = wyrocznia i W1–W12 spełnione.
- **FAIL** — kod działa niezgodnie z deklaracją (CLAUDE.md, ADR, docstring)
  albo sidecar opisuje coś innego niż plik. Wymaga dowodu z danych źródłowych.
- **UWAGA** — kod działa zgodnie z deklaracją, ale dane GUGiK pokazują
  sytuację, której deklaracja nie przewiduje albo która szkodzi
  użytkownikowi (np. „najnowsza” kampania jest w 40 % pusta).
- **BLOKADA** — serwer niedostępny lub dane nieosiągalne; nie jest to
  wniosek o kodzie.

## 6. Rejestr wymagań (E)

Statusy: **aktywne** · **zmienione** (z datą i powodem) · **nowe** (dodane
w trakcie rundy) · **wycofane**.

| ID | Wymaganie | Status | Źródło |
|----|-----------|--------|--------|
| E1 | Każdy przypadek C ma wyrocznię zapisaną PRZED uruchomieniem CLI. | aktywne | cykl F2 |
| E2 | Każdy FAIL ma surowy dowód (body skorowidza, nagłówek pliku, sidecar) zapisany na katalog danych i zacytowany w raporcie. | aktywne | cykl F1/F5 |
| E3 | Sidecar opisuje faktyczny plik (W3–W6), nie żądanie. | aktywne | ADR-026/028 |
| E4 | Wybór pliku arkusza zgodny z ADR-028 dla C1–C4, C8, C9, C12. | aktywne | ADR-028 |
| E5 | Kod wyjścia i komunikaty zgodne z CLAUDE.md (W11). | aktywne | CLAUDE.md |
| E6 | Każdy FAIL i każdy nowy wzorzec danych kończy się testem offline na surowej fixturze, z dowodem mutacyjnym. | aktywne | cykl F7 |
| E7 | Dane tylko na katalog danych, `--output` jawny, cache SQLite w repo. | aktywne | CLAUDE.md |
| E8 | Nieudane ponowne budowanie wyniku (`--force`) nie usuwa poprzedniego poprawnego pliku — w KAZDYM torze (PL i CZ). | nowe (2026-10-06) | review-1 D8, review-2 N7 |
| E9 | Nazwa i rozszerzenie pliku odpowiadaja jego faktycznemu formatowi (np. ZIP z SHP nie jest `.gpkg`); sidecar lezy obok faktycznego pliku. | nowe (2026-10-06) | review-2 N1 |
| E10 | Kazde zapytanie sieciowe, ktore konczy tor bledem (indeks arkuszy CUZK, TERYT BDOT10k, GetCapabilities skorowidza), ma te sama polityke ponowien co pobieranie pliku i timeout zgodny z CLAUDE.md. | nowe (2026-10-06) | review-2 N3, N5 |
| E11 | Wartosci `uklad_xy`/ukladu w rekordach GUGiK (skorowidz i WFS LAZ) sa zapisywane w raportach E2E dokladnie (z bialymi znakami i wielkoscia liter) — rozstrzygaja, czy rozjazd trzech parserow (review-1 D3) dotyczy realnych danych. | nowe (2026-10-06) | review-1 D3 |
| E12 | Wariant orto (RGB/CIR/B-W) jest czescia tozsamosci pliku: rozne warianty nie dziela sciezki, skip nie zwraca innego wariantu niz zadany. | nowe (2026-10-06) | E2E-B C12-f (FAIL) |
| E13 | Wybor rekordu `full_sheet=false` (niepelny arkusz) jest widoczny: `Warning:` w CLI i `extra.source.full_sheet` w sidecarze arkusza oraz w `extra.sheet_sources` wycinka. Regula wyboru ADR-028 (najnowsza kampania) bez zmian — zmiana reguly wymaga decyzji uzytkownika. | nowe (2026-10-06) | E2E-B C12-a, C14-b; E2E-A C5, C10d |
| E14 | `--force` omija ODCZYT cache rekordow, ale ZAPISUJE swiezo wybrany rekord (kolejne uruchomienie bez `--force` dostaje nowy rekord). | nowe (2026-10-06) | E2E-B C15 |
| E15 | Komunikat przy skip mowi o skip (nie `Downloaded to`); pusty wycinek (`all_nodata`) jest zapisany w sidecarze i ostrzezenie powtarza sie przy skip. | nowe (2026-10-06) | E2E-B C17 |
| E16 | Sidecar LAZ `request` zapisuje `year` i `min_density`; dokumentacja mowi, ze `gestosc`/`--min-density` to wartosc NOMINALNA GUGiK (faktyczna bywa kilkukrotnie wyzsza). | nowe (2026-10-06) | E2E-B C13-f |
| E17 | Plik PL-2000 opublikowany przez GUGiK we wspolrzednych EPSG:2180 (strefa 7, niecalkowity `cellsize`): sidecar `horizontal_crs` = uklad pliku (EPSG:2180), `extra.source.uklad` = deklaracja rekordu, `Warning:`; segment sciezki wg godla (ADR-026) — zachowanie udokumentowane w CLAUDE.md. | nowe (2026-10-06) | E2E-A C6b/C6h (UWAGA, kod poprawny) |
| E18 | Testy offline wyboru rekordu korzystaja z SUROWYCH body z tej rundy (C1b, C3, C6, C9, C10g, C12, C13, C14) — kazdy z dowodem mutacyjnym. | nowe (2026-10-06) | E6 + raporty E2E |

## 7. Podział pracy

| Rola | Model | Zakres | Raport |
|------|-------|--------|--------|
| E2E-A | Sonnet | NMT i NMPT: C1–C11, C16 (PL-1992/2000, KRON86/EVRF2007, 1 m/5 m, sidecary ASC) | `e2e-a-nmt.md` |
| E2E-B | Sonnet | Orto, LAZ, wycinek, cache: C12–C15, C17 | `e2e-b-orto-laz-wycinek.md` |
| Review-1 | Fable | Zduplikowana logika, overengineering | `review-1-duplikacje.md` |
| Review-2 | Fable | Deklaracje (CLAUDE.md, ARCHITECTURE, ADR, docstringi, `--help`) vs faktyczny kod | `review-2-deklaracje.md` |
| Koordynator | Opus | Ten dokument, weryfikacja znalezisk, F6–F9, raport końcowy | `raport-koncowy.md` |

## 7a. Ponowny przebieg na żywo (F9) — zakres

Po scaleniu `fix/review-2026-10-06` do `develop` (Sonnet, dane na katalog danych
`.../2026-10-06-brzegowe/f9/`), tylko przypadki, ktorych dotyczyly naprawy:

| ID | Przypadek | Oczekiwane po naprawie | Wymaganie |
|----|-----------|------------------------|-----------|
| F9-1 | M-34-90-C-b-4-4: RGB, potem CIR przez API (`GugikOrtoProvider(color="CIR")`) | CIR w `orto/pl_1992_cir/`, sidecar `kolor: CIR`, RGB nietkniety | E12 |
| F9-2 | M-34-90-C-b-4-4 orto RGB (rekord 2026 niepelny) | `Warning:` o niepelnej kampanii, kod 0, `extra.source.full_sheet: false` | E13 |
| F9-3 | Wycinek `--bbox 637000,473000,637100,473100 --target-crs EPSG:2180` (N-34-139-C-a-3-1, ucieta kampania 2025-10-21) | `Warning:` wskazuje niepelna najnowsza kampanie; sidecar `all_nodata: true`, `sheet_sources[].full_sheet`; rerun (skip) powtarza ostrzezenie | E13, E15 |
| F9-4 | Godlo z cache: `--force` po wymianie rekordu, potem bez `--force` | drugi przebieg bierze rekord z `--force` | E14 |
| F9-5 | Ponowne uruchomienie pojedynczego godla | komunikat o skip, nie `Downloaded to` | E15 |
| F9-6 | LAZ `--year 2023` na obszarze w2 | sidecar `request.year == 2023` | E16 |
| F9-7 | 7.125.11.19 (PL-2000:S7 w EPSG:2180) | `Warning:` o ukladzie pliku, sidecar EPSG:2180, `extra.source.uklad` = `PL-2000:S7` | E17 |
| F9-8 | BDOT10k `--format SHP` (maly powiat) | plik `.zip` (naglowek `PK`), sidecar obok | E9 |
| F9-9 | NMT godlo + wycinek PL (regresja ogolna rundy 2026-09-30) | jak w `live-2026-09-30.md` | E3–E5 |

## 8. Historia zmian

- **2026-10-06, zamkniecie rundy** — fala C (E17 `Warning:` w CLI, D16
  `--force` CZ = refresh, N11, N17, errata dokumentacji). Merge
  `b394570` do `develop`: 2216 testow offline. **F9: 9/9 PASS**
  (`live-f9.md`) — E9, E12–E17 potwierdzone na zywo. Zmiana kontraktu
  F9 po fakcie: cache SQLite dla testow cache NIE na katalog danych CIFS (WAL
  -> `database is locked`), tylko lokalny katalog (zgodnie z CLAUDE.md;
  blad w zleceniu koordynatora). Otwarte: decyzja uzytkownika o regule
  niepelnego arkusza (E13 daje tylko widocznosc) i backlog —
  `raport-koncowy.md` sekcje 4–5. Status wszystkich E: spelnione,
  poza E13 w czesci "czy niepelny arkusz powinien wygrywac" (decyzja).

- **2026-10-06, po falach A i B** — fala A (`fix/review-2026-10-06`, 6
  zadan: D8/N7, D1/N9, N5, N1, N8, N6) i fala B (8 zadan: E12–E17, N3, D3)
  zaimplementowane TDD z dowodami mutacyjnymi (`impl-fala-a.md`,
  `impl-fala-b.md`); 28 testow regresyjnych na surowych body z tej rundy
  (`impl-fixtury.md`, E18). Koordynator powtorzyl niezaleznie 5 mutacji
  (A1, A4, M3, B1, B3) — wszystkie wykryte. Suita: 2105 -> 2206 offline.
  Status wymagan: E8, E9, E10 (czesciowo: GetCapabilities N3, CUZK query,
  TERYT), E12, E14, E15, E16, E18 — spelnione offline; E13 i E17 —
  spelnione offline, E17 `Warning:` w fali C; wszystkie czekaja na F9
  (sekcja 7a). E11 rozstrzygniete (D3 naprawione mimo braku w danych —
  kafel/rekord z nierozpoznanym ukladem jest odrzucany).
- Zauwazony problem procesu: agent fali A przepisal `docs/DECISIONS.md`
  z CRLF na LF (2740 linii diffu przy 5 liniach zmiany) — przywrocone,
  kolejne zlecenia zawieraja ostrzezenie o CRLF.

- **2026-10-06, po E2E** — E2E-A (NMT/NMPT, 211 arkuszy w skorowidzu,
  38 uruchomien CLI): 0 FAIL, 4 UWAGI (PL-2000 strefa 7 z plikiem
  EPSG:2180 — potwierdzone przez koordynatora na surowym naglowku;
  KRON86/EVRF2007 bez wspolnej kampanii; NMPT o 6 lat starsze od NMT).
  E2E-B (orto, LAZ, wycinek, cache): 13 PASS, 6 UWAG, 1 FAIL (C12-f:
  CIR i RGB dziela sciezke — potwierdzone na kodzie: segment
  `orto/pl_{uklad}` bez wariantu). E11 rozstrzygniete: w 1131 rekordach
  skorowidza i 294 kaflach LAZ wystepuja tylko scisle wartosci
  `PL-1992`/`PL-2000:S5..S8` — rozjazd parserow D3 jest utajony
  (backlog, test kontraktowy). Dodane E12–E18. Decyzja koordynatora:
  niepelne arkusze (C5/C12-a/C14-b) — widocznosc (E13), bez zmiany
  reguly wyboru (decyzja uzytkownika D4/D9 z 2026-09-29; pytanie
  w raporcie koncowym).

- **2026-10-06, po review** — dodane E8–E11. Review-1: 19 duplikacji
  (3 WYSOKIE: D1 petle retry rozjechane, D3 trzy parsery `uklad_xy`, D8
  kopia warpu CZ kasuje poprzedni wynik) i 12 przypadkow overengineeringu.
  Review-2: 17 niespojnosci (WYSOKA N1: BDOT10k SHP jako `.gpkg`).
  Koordynator powtorzyl dowody D1, D3, D8 i N1 — potwierdzone. Fala
  naprawcza A (D1/N9, D8/N7, N1, N5, N6, N8) w worktree
  `fix/review-2026-10-06`, zeby nie zmieniac kodu pod biegnacymi testami
  na zywo. D3 czeka na realne wartosci `uklad_xy` z E2E (E11).

- **2026-10-06** — wersja pierwsza: fazy F0–F9, katalog C1–C17,
  lista W1–W12, wymagania E1–E7.
