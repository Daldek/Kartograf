# Przeglad dokumentacji vs stan kodu — 2026-10-08

Stan: develop @ 4f065b6 (`0.7.0-dev`, 2684 testy offline + 16 live). Przeglad tylko do odczytu,
6 subagentow (A–F), kazde twierdzenie weryfikowane grepem w `kartograf/` lub `--help`.
Koordynator powtorzyl weryfikacje znalezisk kluczowych: C-02, E-04, E-13/E-15/E-26, F-01, F-02,
F-08, F-10, F-11 — wszystkie potwierdzone.

## Podsumowanie

| Plik | BLAD | NIEAKT. | BRAK | NIESPOJNE | DROBNE | Razem |
|---|---|---|---|---|---|---|
| A `CLAUDE.md` | 0 | 1 | 8 | 0 | 3 | 12 |
| B `README.md` | 0 | 3 | 0 | 1 | 0 | 4 |
| C `docs/ARCHITECTURE.md` | 2 | 2 | 7 | 2 | 4 | 17 |
| D `docs/PRD.md` + `docs/SCOPE.md` | 0 | 7 | 3 | 3 | 3 | 16 |
| E `PROGRESS` + `DEVELOPMENT_STANDARDS` + `IMPLEMENTATION_PROMPT` | 4 | 12 | 3 | 2 | 4 | 25 |
| F `docs/CHANGELOG.md` + `docs/DECISIONS.md` | 1 | 3 | 4 | 6 | 3 | 17 |
| **Razem** | **7** | **28** | **25** | **14** | **17** | **91** |

Ogolny obraz: opisy zachowania (komunikaty CLI, timeouty, retry, kampanie, wycinek, LAZ, CZ) sa
zgodne z kodem we wszystkich plikach. Niezgodnosci to glownie: (1) liczby i daty sprzed ADR-030,
(2) listy modulow/eksportow/pol bez elementow z 2026-10-07/08, (3) w CHANGELOG 0.7.0 wpisy z
wczesnej fazy cyklu niepoprawione po pozniejszych zmianach w tym samym wydaniu, (4) dwa dokumenty
pomocnicze (STANDARDS, PROMPT) z bledami o CORINE/TERYT i Auth Proxy.

## Priorytet 1 — wplywaja na wydanie 0.7.0 lub wprowadzaja w blad

| ID | Gdzie | Problem | Poprawka |
|---|---|---|---|
| F-01 | CHANGELOG:543-556 | Instrukcja przejscia z 0.6.1 kaze przenosic `nmt_*`/`nmpt`/`orto`, by uniknac ponownego pobrania — od ADR-030 zwykly plik w sciezce standardowej i tak jest pobierany do `kampanie/` (`links.py` `linked_campaign` -> None). Przeczy wpisowi BREAKING l.25-37 tej samej sekcji. | Przenoszenie ma sens tylko dla `laz/`; NMT/NMPT/orto zostana pobrane ponownie. |
| F-08 | CHANGELOG Breaking | Nieoznaczone BREAKING: usuniete `MetadataCache.get_url/set_url`, atrybuty klas `WMS_LAYERS` (GUGiK NMT/NMPT/orto), `GugikProvider.FORMAT_EXTENSIONS`, `RETRY_BACKOFF_BASE` (providery; zostal tylko w `transport/http.py`). | Dopisac punkt w `### Breaking Changes`. |
| F-02 | CHANGELOG:878-884, 1088-1110 | Wpisy o `WMS_LAYERS` z fallbackiem i `_get_validated_layers()` — symboli nie ma, ta sama sekcja (l.467) mowi o ich usunieciu. | Usunac / zastapic jednym zdaniem. |
| F-03/04/05/06 | CHANGELOG 0.7.0 | Wpisy wczesne sprzeczne z pozniejszymi w tym samym wydaniu: LAZ „najnowszy rok per kafel” + fallback lat (jest ADR-029, bez fallbacku); LAZ `uklad` fallback na `2000` (jest `ValidationError`/pominiecie); sidecar LAZ „(backlog)” (jest `parent_request`); `Sm5Sheet` w Added (usuniety). | Skorygowac wpisy. |
| F-07 | CHANGELOG Tests | „1861 testow offline … 8 live”, nieistniejace klasy `TestHardcodedLayerNames`, `TestOrtoLayerValidation`. | 2684 + 16; usunac punkty o klasach. |
| F-10 | CHANGELOG:1879-1884 | Odnosniki compare do tagow `v0.6.0` i `v0.3.2`, ktorych nie ma lokalnie (`git tag`). | Dotagowac (0.6.0 = `f9a0a0f`) lub zmienic linki — decyzja uzytkownika (tag = operacja zewnetrzna po push). |
| F-11 | DECISIONS:1610-1612 (ADR-030 errata 1 (d)) | Mowi o porownaniu klucza `<data>_<id>`; kod: `(aktualnosc, dt_pzgik, url)`, fallback z katalogu `(data, "", "")` (`links.py`). | Poprawic tekst erraty. |
| F-12 | DECISIONS | Brak erraty I-1 (fallback offline, `unverified`); ADR-028 Konsekwencje nadal mowia, ze awaria skorowidza = blad. | Errata 5 ADR-030 + odsylacz w ADR-028. |
| E-13/E-26 | STANDARDS:755, PROMPT:128 | „CORINE — TERYT 120 s” — to `NotImplementedError` (`corine.py:752`). | Usunac wiersz / „60 s”. |
| E-15 (+D-07) | STANDARDS 14.2-14.3:785, PRD:337,642 | Auth Proxy: „Keychain” i `os.getenv("CLMS_CLIENT_ID")` — kod: `CLMS_CREDENTIALS` (JSON) w podprocesie proxy, Keychain tylko macOS jako fallback. | Poprawic opis i przyklad. |
| C-02 | ARCHITECTURE:98-115 | Graf zaleznosci oznaczony „ZMIERZONY” pomija krawedzie: `transport→transform` (import, `mosaic.py:26`), `providers→download` (leniwe, `skorowidz.py:620`, `gugik_laz.py:633`), `hydrology→sources` (leniwe, `hsg.py:558`). | Dopisac krawedzie. |
| E-27 | PROMPT 8.1 | Instrukcja nowego providera LandCover: abstrakcyjne sa tylko `download_by_bbox` (+ `download`/`name`/`base_url`); `download_by_godlo` dziedziczone. | Poprawic liste wymaganych metod. |

## Priorytet 2 — nieaktualne liczby, daty, statusy

- **Liczba testow 2684** (zamiast 2216/2057/2058/2622/1716): README:15,448,497 (B-01..04), SCOPE:584 (D-01), PROGRESS:27 (E-01), STANDARDS 7.1 (E-16), 10.1 (E-18 — data pomiaru pokrycia), 6.3 „8 live” -> 16 (E-14).
- **README Status** (B-03): opis 0.7.0-dev bez ADR-030.
- **PROGRESS** (E-02..E-11): data zakresu do 2026-10-08; dwa sprzeczne bloki „START NASTEPNEJ SESJI” (stary z 2058 testami/236 commitami — usunac lub zarchiwizowac); `e2e-data/` „czeka na decyzje” — **katalog juz nie istnieje** (potwierdzone `ls`); pkt 13 „wydanie czeka na fale naprawcza” (zamknieta); 223 -> 386 commitow przed origin; martwy odnosnik „Znany problem uslugowy”; wzmianka o usunietym `Sm5Sheet`; Backlog `[ ]` juz zrobione: A5-3 (retry -> `download_to`), walidacja NaN w `--bbox`, tolerancja `NoCoverageError` w listach, kontrola tresci ASC (`verify_file_format`); A2-7 do sprawdzenia (`_get_opendata_url` nadal istnieje w `gugik.py:274`, `gugik_orto.py:193`); tabela statusu bez wiersza ADR-029/ADR-030 i z niepelnym wierszem CLI.
- **SCOPE** (D-06, D-11): status „ponowna weryfikacja przed wydaniem” (zrobiona); naglowek 3.12/2026-09-30 vs stopka 3.13/2026-10-07.
- **PRD** (D-12, D-13): snapshot v0.6.1 bez wzmianki o ADR-029/030; pokrycie ~89 % vs 93 % w SCOPE.
- **ARCHITECTURE** (C-01, C-14): data 2026-09-30 i odnosnik tylko do raportu live z 09-29; „land cover bez zmian wzgl. 0.6.x” (sa: sidecary, `.zip` SHP, GPKG skladany lokalnie, sidecar HSG).
- **DECISIONS** (F-13..F-17): brak odsylaczy ADR-026/028 -> ADR-030; status ADR-021 (zastapiony czesciowo przez ADR-029) i ADR-023 (czesci zastapione przez ADR-024/027); ADR-020 „timeout 10 s GetCapabilities” (jest timeout providera 30/60 s); ADR-029 „starsze tylko `--year`” (jest tez `--campaigns all`); ADR-030 Konsekwencje opisuja ryzyka symlinkow (errata 4 ich nie zastepuje wprost).
- **CHANGELOG** F-09 (niepewne): BDOT10k SHP zwraca `.zip` — dopisac do „Zmian zachowania widocznych dla skryptow”.

## Priorytet 3 — luki w listach modulow / API / pol

- **Moduly brakujace w drzewach:**
  - `transform/bbox.py` (`envelope_from_2180`) i `providers/pl/wcs.py` (`GugikWcsMixin`): CLAUDE.md (A-01/02), ARCHITECTURE (C-03, tam brak tez `skorowidz.py`);
  - `download/{campaigns,links,laz}.py`, `core/coverage.py`, `providers/pl/skorowidz.py`: SCOPE 4.1 (D-04), STANDARDS 7.1 (E-17), PROMPT 3 (E-25).
- **Wyjatki:**
  - `ParseError` brak w CLAUDE.md (A-03);
  - `GridMismatchError` brak w ARCHITECTURE (C-04), SCOPE (D-04), STANDARDS 11.1 (E-21), PROMPT (E-25);
  - `NoCoverageError.hints` i `DownloadError.status_code` nieopisane w kilku miejscach.
- **Cache:**
  - `teryt_cache` brak w CLAUDE.md:121 (A-04) i ARCHITECTURE:179 (C-17);
  - SCOPE:512 opisuje nieistniejacy cache „URL” (D-05).
- **`__all__` = 48 nazw**, a PRD §5 i SCOPE 2.10 maja 39 nazw (D-02/03), PROMPT 5 (E-24). Brakuje: `SheetFetch`, `CampaignRef`, `LazDownloadResult`, `LazTileFailure`, `download_laz_area`, `run_laz_download`, `LazTileSelection`, `SupersededLazTile`, `GridMismatchError`.
- **Pola wynikow (ARCHITECTURE C-10, C-12):**
  - `SheetFetch.unverified`;
  - `DownloadResult.unverified` / `no_coverage` / `no_coverage_hints`;
  - `PlCutoutResult.partial_sheets` / `unverified`.
- **Sidecar wycinka (C-08, C-09, C-11; CLAUDE.md A-08, A-09):**
  - opis `extra` jest w 3 miejscach ARCHITECTURE niespojny i niepelny: brak `unverified_sheets`, a skip odtwarza takze `partial_sheets` / `unverified` / `all_nodata`;
  - I-1 w wycinku nieopisany w CLAUDE.md.
- **Sidecar HSG i CORINE:**
  - `HSGCalculator` pisze sidecar, czego brak w liscie warstw piszacych w ARCHITECTURE (C-05);
  - klucze `derived` / `source_layers` / `depth` / `stat` / `classes`, `nodata` 0, CORINE `fallback` / `uwaga` (C-08);
  - SCOPE nie wspomina sidecara HSG ani GPKG BDOT10k skladanego lokalnie (D-10).
- **CLAUDE.md:**
  - `NoCoverageError.hints` -> `Info:` (max 5 linii, `DownloadResult.no_coverage_hints`) nieopisane (A-07);
  - drzewo bez `select_all_intersecting` (A-06);
  - opis `skorowidz.py` bez `resolve_campaigns` (A-05).
- **SCOPE:**
  - przyklady CLI bez `--campaigns` / `--min-year` (D-08);
  - reguly I-1, CZ + kampanie, `--min-year` x `--year` (D-09).
- **ARCHITECTURE:**
  - E17 (plik PL-2000 w EPSG:2180, sidecar z ukladem pliku) nieopisane (C-07);
  - `emit_sidecar` zwraca `None` bez deskryptora, a nie `_write_sidecar` (C-06).

## Drobne

- A-10, A-11, A-12 (`KARTOGRAF_DEBUG`: dowolna niepusta wartosc);
- C-13 (przyklad nazwy wycinka EPSG:5514 rozni sie o ~1 m od obecnego wyniku — przypiecie 1622/1623);
- C-15, C-16;
- D-14 (DLR WMS w tabeli zrodel), D-15, D-16;
- E-12, E-19 („Docker container”), E-22, E-23 (opis markera `live` w pyproject), E-28 (`[Unreleased]` -> `[0.7.0] - Unreleased`), E-30, E-31 (literowka „twrz”), E-32 (wersje dokumentow).

## Decyzje do podjecia przez uzytkownika

1. **Zakres poprawek:** wszystkie 91 vs tylko priorytet 1+2 przed wydaniem.
2. **`DECISIONS.md`:** zgoda na edycje (errata 5 ADR-030 = I-1, poprawka erraty 1 (d), odsylacze statusow ADR-021/023/026/028, korekta ADR-020/029, rozszerzenie erraty 4) — zachowujac CRLF.
3. **`DEVELOPMENT_STANDARDS.md` / `IMPLEMENTATION_PROMPT.md`:** aktualizacja (rekomendacja recenzenta) vs zastapienie list (drzewo, API, timeouty) odsylaczami do CLAUDE.md, zeby nie dublowac stanu w 4 miejscach.
4. **PRD:** podniesc do 0.7.0 vs zostawic snapshot 0.6.1 z nota odsylajaca do SCOPE.
5. **Tagi `v0.6.0` / `v0.3.2`** (F-10): dotagowac historyczne commity vs poprawic odnosniki.
