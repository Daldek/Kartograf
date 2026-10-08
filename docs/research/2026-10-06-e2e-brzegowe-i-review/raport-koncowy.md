# Raport końcowy: runda E2E przypadków brzegowych GUGiK + code review (2026-10-06)

**Stan wyjściowy:** `develop` `6d9a6d0`, 2105 testów offline.
**Stan końcowy:** `develop` po merge `9c47988` + dokumentacja rundy, **2216 testów
offline** (+111) + 16 `live`, ruff czysty, mypy 32 (lista błędów = baseline).
Kontrakt rundy i jego historia: `cykl-e2e.md` (wymagania E1–E18).

## 1. Co zrobiono

| Etap | Wykonawca | Wynik | Raport |
|------|-----------|-------|--------|
| E2E-A: NMT/NMPT (C1–C11, C16) | Sonnet | 211 arkuszy w skorowidzu, 38 uruchomień CLI: 0 FAIL, 4 UWAGI | `e2e-a-nmt.md` |
| E2E-B: orto, LAZ, wycinek, cache (C12–C15, C17) | Sonnet | 13 PASS, 6 UWAG, 1 FAIL | `e2e-b-orto-laz-wycinek.md` |
| Review-1: duplikacje, overengineering | Fable | 19 duplikacji (3 WYSOKIE), 12 przypadków overengineeringu | `review-1-duplikacje.md` |
| Review-2: deklaracje vs działanie | Fable | 17 niespójności (1 WYSOKA), ponad 40 deklaracji zgodnych | `review-2-deklaracje.md` |
| Fala A (6 napraw) | Opus | TDD + 9 mutacji | `impl-fala-a.md` |
| Fala B (8 napraw, E12–E17) | Opus | TDD + 15 mutacji | `impl-fala-b.md` |
| Testy na surowych body GUGiK (E18) | Sonnet | 28 testów, 85 fixtur (840 KB), 22 mutacje | `impl-fixtury.md` |
| Fala C (E17 `Warning:`, errata dokumentacji) | Opus | 4 poprawki kodu, errata 10 znalezisk | `impl-fala-c.md` |
| F9: ponowny przebieg na żywo | Sonnet | **9/9 PASS** | `live-f9.md` |

Koordynator sam sprawdził wszystkie znaleziska WYSOKIE i jedyny FAIL, uruchamiając
ponownie skrypty dowodowe, czytając surowe nagłówki i kod. Powtórzył też niezależnie
6 mutacji (A1, A4, M3, B1, B3 oraz retry z ca4d004); każdą testy wykryły.

## 2. Błędy naprawione (wszystkie z testem, który bez naprawy pada)

| Znalezisko | Problem | Naprawa |
|------------|---------|---------|
| E2E-B C12-f (FAIL) | Orto CIR i RGB dzieliły ścieżkę: żądanie CIR po cichu zwracało istniejący RGB | CIR → `orto/pl_<uklad>_cir/`, B/W → `_bw/`; RGB bez zmian (bez migracji) |
| Review-2 N1 | BDOT10k `--format SHP` zapisywał ZIP pod nazwą `.gpkg` | plik `.zip`, sidecar obok (F9-8 PASS) |
| Review-1 D8 / N7 | Nieudana przebudowa wyniku CZ (`--force`) kasowała poprzedni poprawny plik | tor CZ używa wspólnego `warp_to_grid` (kopia ~90 linii usunięta); wynik bit w bit |
| Review-1 D1 / N9 | CORINE/SoilGrids ponawiały 404 trzy razy i gubiły `status_code` | ta sama polityka co GUGiK (sieć/429/5xx, `Retry-After`) |
| Review-2 N5 | Indeks arkuszy CUZK i TERYT BDOT10k bez żadnych ponowień | `get_with_retry` |
| Review-2 N3 | GetCapabilities skorowidza: 10 s na sztywno zamiast 30/60 s | timeout providera |
| Review-1 D3 | Trzy parsery `uklad_xy` z różnymi wynikami (utajone: w danych tylko ścisłe wartości) | jeden `parse_pl_uklad`; nierozpoznana wartość odrzucana, bez zgadywania (**BREAKING** dla `LazTile.uklad`) |
| E2E-B C15 | `--force` omijał cache, ale go nie odświeżał | `MetadataCache(refresh=True)`: PL i CZ (D16) |
| E2E-B C12-a, C14-b; E2E-A C5 | Niepełny najnowszy arkusz (orto w 97 % czarne, wycinek pusty) bez ostrzeżenia | `Warning:` w każdym torze, także przy skip; `full_sheet` w `sheet_sources`, `all_nodata` w sidecarze |
| E2E-B C17 | Skip godła drukował `Downloaded to`; skip pustego wycinka milczał | `Skipped ...`; ostrzeżenie powtarzane |
| E2E-B C13-f | Sidecar LAZ bez `--year`/`--min-density` | `request.year`, `request.min_density` |
| E2E-A C6b/C6h | PL-2000 strefa 7 publikowana przez GUGiK w EPSG:2180: tylko komunikat loggera | `Warning:` w CLI; sidecar opisuje układ pliku (było już poprawne) |
| Review-2 N6 | LAZ: porażka kafli jako `Warning:` + kod 1 i tylko 5 kafli | `Error:` + pełna lista |
| Review-2 N8 | Błędne `--property`/`--year` w landcover wyglądały jak awaria programu | `Error: <treść>` bez podpowiedzi DEBUG |
| Review-2 N11, N17 | Martwa stała timeoutu BDOT10k; `KARTOGRAF_DEBUG=1` bez tracebacku dla `KartografError` | naprawione |

Dokumentacja (errata, bez przepisywania historii ADR): N2, N4 („3 próby” po nowej polityce),
N10, N12–N16, D16; ADR-023, ADR-027 i ADR-028 dostały erraty; CLAUDE.md, ARCHITECTURE,
SCOPE, README i CHANGELOG (podsekcja „Runda review/E2E 2026-10-06”) są zaktualizowane.

## 3. Jak zmieniły się testy (wymóg: łapią FAKTYCZNE problemy)

- **28 testów na surowych odpowiedziach GUGiK z tej rundy**
  (`tests/test_real_gugik_responses.py`, fixtury `tests/fixtures/gugik_skorowidz/real_2026_10_06/`,
  `tests/fixtures/gugik_laz/real_2026_10_06/`). Pokrywają wzorce, które naprawdę są w danych:
  kilka kampanii w jednej warstwie, 0,5 m nowsze niż 1 m, godło małymi literami, `.ASC`/`.xyz`,
  podpowiedzi PL-2000 `--scale`, CIR tylko w starszej warstwie, rekordy potomne/nadrzędne,
  dwa układy LAZ w jednym obszarze, `format=LAS` przy pliku `.laz`.
  Każdy test pada pod co najmniej jedną mutacją kodu (22 mutacje). Jeden test, którego żadna
  mutacja nie przewracała, usunięto, a jeden przepisano.
- **Testy kontraktowe na wartościach z danych**: parser układu sparametryzowany wartościami
  występującymi w 1131 rekordach skorowidza i 294 kaflach LAZ oraz wartościami nietypowymi.
- **Nagłówek ASC strefy 7 w EPSG:2180** (przycięty, 19,7 KB) jako fixtura sidecara i ostrzeżenia.
- Przy każdej naprawie najpierw powstał test, który był czerwony na starym kodzie; łącznie
  ok. 40 dowodów mutacyjnych w raportach `impl-*.md`.

## 4. Decyzja dla Ciebie (wstrzymana świadomie)

**Reguła wyboru niepełnego arkusza (ADR-028, Twoja decyzja D4/D9 z 2026-09-29).**
Dziś wygrywa najnowsza kampania, nawet niepełna. Realne skutki z tej rundy:
- orto M-34-90-C-b-4-4: kampania 2026 jest w 96,9 % czarna, a pełna kampania 2024 istnieje;
- NMT N-34-139-C-a-3-1: kampania 2025-10-21 to okno 255×422 px, a pełna kampania 2025-04-27 istnieje;
  wycinek w tym arkuszu wychodzi pusty.

Po tej rundzie użytkownik dostaje `Warning:` i flagi w sidecarze, ale plik nadal jest niepełny.
Możliwe kierunki:
(a) zostawić tak jak jest;
(b) dla niepełnej najnowszej kampanii dobrać pełną starszą jako drugie źródło (mozaika dwóch kampanii);
(c) preferować najnowszą PEŁNĄ kampanię i dawać `Info:`, gdy istnieje nowsza niepełna.
Rekomendacja koordynatora: **(c) dla orto i arkuszy pobieranych pojedynczo**, bo plik
w 97 % pusty jest dla użytkownika gorszy niż plik o rok starszy. To zmienia regułę z ADR-028,
dlatego nie zostało zrobione bez Ciebie.

## 5. Backlog (nie blokuje wydania)

- **Duplikacje (review-1):** D4 (5 parserów `--bbox`), D5 (5 przeliczeń obwiedni), D7 (5 opakowań
  sidecara), D10 (pobranie arkusza ×3 w `DownloadManager`), D11 (reguła 5 m ⇒ EVRF2007 w 4 miejscach,
  3 różne skutki), D17 (3 pule wątków; pula i sidecar LAZ tylko w CLI). Do tego wykładnik backoffu:
  2/4 s w providerach, 1/2 s w transporcie (udokumentowane).
- **Overengineering:** O1 (6 publicznych metod `FileStorage` bez wywołań), O3 (rejestr wtyczek
  parserów czytany tylko w testach), O4 (aliasy „deprecated” wbrew zasadzie bez shimów),
  O5 (pola deskryptorów bez konsumenta). Usuwanie publicznego API wymaga sprawdzenia
  Hydrografu i Hydrologu oraz wpisu BREAKING.
- **Z F9 i fali C:**
  - landcover nie pomija istniejących plików (każde wywołanie pobiera ponownie; dotyczy też GPKG);
  - sidecar BDOT10k nie zapisuje formatu;
  - `MetadataCache.__del__` drukuje `ImportError` przy zamykaniu interpretera;
  - podwójne komunikaty (logger + `Warning:`) przy E17 i `all_nodata`;
  - LAZ bez `parent_request` w sidecarze;
  - SoilGrids/CORINE rzucają `ValueError` zamiast `ValidationError`;
  - LAZ dubluje kafle tego samego obszaru z dwóch układów (2022/PL-2000 i 2025/PL-1992);
  - `gestosc` LAZ jest nominalna (faktycznie ~8× wyższa; udokumentowane).
- **Dane GUGiK (do wiedzy, nie błąd kodu):** NMPT bywa o kilka lat starsze niż NMT
  tego samego arkusza; KRON86 i EVRF2007 nie mają wspólnej kampanii (różnicy datum nie da się
  zmierzyć na danych); w danych nie znaleziono remisu `aktualnosc` rozstrzygającego wybór.

## 6. Uwagi o procesie

- Naprawy szły w osobnych worktree, żeby nie zmieniać kodu pod biegnącymi testami na żywo.
  Obie gałęzie są scalone i usunięte.
- Agent fali A przepisał `docs/DECISIONS.md` z CRLF na LF (2740 linii diffu przy 5 liniach
  zmiany). Koordynator to przywrócił, a kolejne zlecenia zawierały ostrzeżenie.
- Kontrakt F9 zalecał cache SQLite w katalogu na udziale sieciowym CIFS, a WAL na CIFS daje
  `database is locked`, co CLAUDE.md już opisuje. Agent przeszedł na lokalny katalog.
- Dane rundy: 3,2 GB w `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/`.
- Nic nie zostało wypchnięte: `develop` ma 275+ commitów przed origin. Wydanie 0.7.0
  czeka na Twoje polecenie i na decyzję z sekcji 4 (jeśli wybierzesz (b) lub (c)).
