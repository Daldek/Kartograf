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

## 7. Podział pracy

| Rola | Model | Zakres | Raport |
|------|-------|--------|--------|
| E2E-A | Sonnet | NMT i NMPT: C1–C11, C16 (PL-1992/2000, KRON86/EVRF2007, 1 m/5 m, sidecary ASC) | `e2e-a-nmt.md` |
| E2E-B | Sonnet | Orto, LAZ, wycinek, cache: C12–C15, C17 | `e2e-b-orto-laz-wycinek.md` |
| Review-1 | Fable | Zduplikowana logika, overengineering | `review-1-duplikacje.md` |
| Review-2 | Fable | Deklaracje (CLAUDE.md, ARCHITECTURE, ADR, docstringi, `--help`) vs faktyczny kod | `review-2-deklaracje.md` |
| Koordynator | Opus | Ten dokument, weryfikacja znalezisk, F6–F9, raport końcowy | `raport-koncowy.md` |

## 8. Historia zmian

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
