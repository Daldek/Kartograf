# Fala naprawcza C — implementacja (2026-10-06)

Galaz `fix/review-2026-10-06` (worktree `Kartograf-fix`), baza `b42ceaa`
(fale A i B + fixtury). Zrodla: `cykl-e2e.md` (E17), `impl-fala-b.md`
(odstepstwo B8), `review-2-deklaracje.md` (N2, N4, N10-N17),
`review-1-duplikacje.md` (D16). Zmiany kodu TDD: test czerwony na bazie ->
minimalna zmiana -> zielony -> mutacja -> czerwony -> przywrocenie.

## Wynik koncowy

- `pytest tests/ -m "not live"`: **2216 passed** (baza 2210 po C1 / 2206
  przed C1; +10 przypadkow w fali C), 16 deselected (`live`; `-m live
  --collect-only`: 16/2232).
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`:
  92 files already formatted.
- `mypy kartograf/`: 32 bledy; lista bez numerow linii (`sed -E
  's/:[0-9]+: /: /' | sort`) **identyczna** z baza `b42ceaa` (`diff` pusty).
- `docs/DECISIONS.md`: CRLF zachowane (`file`: "with CRLF line
  terminators"; 1394 `\n` = 1394 `\r\n`). Pozostale pliki bez `\r`.

## Commity

| Commit | Zakres |
|---|---|
| `87b92f9` | C1 fix(cli): Warning o arkuszu PL w innym ukladzie niz godlo (E17) |
| `ee36306` | C2 fix(cli): KARTOGRAF_DEBUG=1 takze dla KartografError (N17) |
| `b7471e6` | C2 fix(bdot10k): DEFAULT_TIMEOUT = 120 s (N11) |
| `43cc922` | C2 fix(cli): --force w torze CZ odswieza cache indeksu (D16) |
| `f05c49e` | C2 docs: errata N2, N4, N10, N12-N17, D16 |
| `f5dcb40` | C3 docs(changelog): runda review/E2E — fala C |

## C1 (E17) — `Warning:` o arkuszu w innym ukladzie niz godlo

- **Zmiana:** `cli/download_cmd.py`: `_read_sheet_sidecar`,
  `_sheet_crs_mismatch(path)` (sidecar `country == "PL"`,
  `request.godlo`, `horizontal_crs` != `horizontal_crs_for_godlo(godlo)`),
  `_warn_crs_mismatch_sheets(paths)` i wspolne `_warn_sheet_sidecars`
  (E13 niepelny arkusz + E17) wolane w torze godla (pojedynczy arkusz) i w
  `_finish_pl_sheets` (lista `--bbox`/`--geometry`, hierarchia). Fakt czytany
  z sidecara pliku wyniku, wiec dziala przy skip (wzor B2). Komunikat:
  `Warning: 1 arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje
  godlo: 7.125.11.19 (godlo: EPSG:2178, plik: EPSG:2180) — sidecar opisuje
  uklad pliku (horizontal_crs); deklaracja rekordu w extra.source.uklad`.
  stderr, takze przy `-q`; kod 0 bez zmian.
- **Wycinek `--target-crs`:** nie dotyczy — bierze wylacznie arkusze
  PL-1992 (`_reject_pl2000_sheets`), a obserwowany przypadek to godlo
  PL-2000. Zapisane w CLAUDE.md.
- **Logger zostaje:** `pl_sheet_horizontal_crs` dalej loguje WARNING
  (sygnal dla biblioteki, test B8). W CLI bez handlerow trafia on rowniez
  na stderr — uzytkownik widzi dwie linie (logger + `Warning:`). Backlog
  ponizej.
- **Test:** `tests/test_cli.py::TestSheetCrsMismatchWarning` (prawdziwy
  `GugikProvider` + `DownloadManager`, atrapa sesji skorowidza, plik =
  fixtura `tests/fixtures/gugik_asc/77912_1384976_7.125.11.19.head.asc`):
  godlo, skip (drugi przebieg), lista `--bbox --system 2000`, kontrola:
  ta sama fixtura z `xllcenter 7567975.95` (strefa 7) -> brak ostrzezenia.
- **Przed:** 3 failed (brak linii `Warning:` z EPSG:2180), kontrola passed.
- **Mutacje:**

  | Mutacja | Wynik |
  |---|---|
  | `_warn_crs_mismatch_sheets(paths)` -> `pass` | 3 failed (godlo, skip, lista) |
  | `if True or expected == actual` (nigdy nie ostrzega) | 3 failed |
  | komunikat bez prefiksu `Warning:` | 3 failed |
  | `if False and expected == actual` (zawsze ostrzega) | 1 failed (`test_file_in_zone_crs_is_silent`) — pierwsza wersja kontroli filtrowala linie po "EPSG:2180" i mutacja przezyla; asercja wzmocniona na brak "innym ukladzie" |

  Wszystkie przywrocone.
- **Docs:** CLAUDE.md (zdanie z B8 "BEZ prefiksu `Warning:`" zastapione
  opisem `Warning:`), errata ADR-028, CHANGELOG.

## C2 — tabela statusow

| Zn. | Status po falach A/B | Dzialanie | Pliki | Commit |
|---|---|---|---|---|
| N2 | aktualne | naprawione w dok.: arkusz za granica w trybie listy = `Warning:` + kod 0 (przy >= 1 pliku) | README.md | `f05c49e` |
| N4 | aktualne (ca4d004 poprawil tylko jedno miejsce ARCHITECTURE) | naprawione w dok.: "do 3 prob (siec, 429, 5xx; inne 4xx bez ponowien)"; errata ADR-028 obejmuje tez zdanie z errata ADR-020 | CLAUDE.md, SCOPE.md (2 miejsca), ARCHITECTURE.md 4.1/4.3, `download/cutout.py` docstring, DECISIONS.md | `f05c49e` |
| N10 | aktualne | naprawione w dok.: usuniete "CORINE przez TERYT"; dopisane: TERYT BDOT10k 30 s, GetCapabilities = timeout providera (po B6) | CLAUDE.md, SCOPE.md | `f05c49e` |
| N11 | aktualne | naprawione w kodzie: `DEFAULT_TIMEOUT = 120` i domyslna wartosc trzech sygnatur; test `TestBdot10kDefaultTimeout` (3 failed przed, mutacja `= 60` -> 3 failed) | `providers/pl/bdot10k.py`, `tests/test_landcover.py` | `b7471e6` |
| N12 | aktualne (2057/2058) | naprawione w dok.: 2216 offline + 16 live (pomiar koncowy) | README.md (3 miejsca) | `f05c49e` |
| N13 | aktualne (`_warn_cz_all_nodata` importuje `transport.mosaic`) | naprawione w dok.: krawedz `cli -> transport (leniwie)` w grafie + opis; przeniesienie kontroli do providera CZ = backlog | ARCHITECTURE.md 2 | `f05c49e` |
| N14 | aktualne (A4 naprawil tylko BDOT10k SHP) | naprawione w dok.: "baza nazwy", rozszerzenie nadaje provider (`.gpkg`/`.tif`/`.png`/`.zip`) | ARCHITECTURE.md 4.8, CHANGELOG.md (wpis A5-2) | `f05c49e` |
| N15 | aktualne | naprawione w dok.: errata ADR-023 pkt 8; dopisanie `parent_request` do LAZ = backlog | DECISIONS.md | `f05c49e` |
| N16 | czesciowo nieaktualne (docstring klasy `LandCoverManager` mial juz `soilgrids`) | naprawione w dok.: dwa docstringi metod `LandCoverManager`, docstring `MetadataCache` (`sheet_cache` 30 d, `refresh`) | `landcover/manager.py`, `cache/metadata.py` | `f05c49e` |
| N17 | aktualne | naprawione w kodzie: bariera `main` przepuszcza `KartografError` przy `KARTOGRAF_DEBUG`; test `test_debug_env_reraises_kartograf_error` (czerwony bez zmiany = mutacja); CLAUDE.md doprecyzowane | `cli/commands.py`, `tests/test_cli.py`, CLAUDE.md | `ee36306`, `f05c49e` |
| D16 | aktualne (B3 zmienil tylko PL) | naprawione w kodzie: tor CZ `MetadataCache(refresh=bool(args.force))`; test `test_force_refreshes_sheet_index_cache[False/True]` (True czerwony bez zmiany); zdanie w CLAUDE.md, SCOPE, ARCHITECTURE 4.1 | `cli/download_cmd.py`, `tests/test_cli.py`, CLAUDE.md, SCOPE.md, ARCHITECTURE.md | `43cc922`, `f05c49e` |

Faktyczne zachowanie CZ przed D16: `_cmd_download_cz` otwieral
`MetadataCache()` zawsze, wiec `--force` pobieral plik na nowo, ale indeks
arkuszy SM5 (`SheetIndex.sm5_sheet`) czytal z `sheet_cache` (TTL 30 d).
Zmiana byla jedna linia, wiec zrobiona w kodzie zamiast samego zdania.

Przy okazji errata ADR-028 opisuje tez dwie rozbieznosci po fali B,
ktorych review nie wymienil: "`--force` omija cache" (od E14 refresh) oraz
"sidecar PL-2000 deklaruje strefe" (E17: sidecar opisuje uklad pliku).

## Backlog

1. **N13 (kod):** kontrola "wynik CZ w calosci nodata" do providera/biblioteki
   (jak `PlCutoutResult.all_nodata`), co usunie krawedz `cli -> transport`.
2. **N15 (kod):** `extra.parent_request` w sidecarze LAZ
   (`_build_parent_request` gotowe) — klucz grupowania dla Hydrografu;
   zmiana kontraktu sidecara, wiec poza "trywialna".
3. **E17 (kosmetyka):** w CLI ten sam fakt pojawia sie dwa razy na stderr
   (logger `kartograf.sources.sidecar` przez `lastResort` + `Warning:`).
   Opcje: CLI wycisza logger sidecara albo logger schodzi do INFO (wtedy
   test B8 do zmiany).
4. **A5 (z fali A):** providery SoilGrids/CORINE nadal rzucaja `ValueError`
   zamiast `ValidationError`.
5. **O3/D16 resztka:** `Sm5Sheet.get_bbox` z wlasnym cyklem cache, osiagalny
   tylko z testow (`parser_factory`).
6. **N17 skutek uboczny:** z `KARTOGRAF_DEBUG=1` takze bledy uzytkownika
   docierajace do bariery koncza sie tracebackiem — zgodnie z deklaracja;
   wiekszosc torow tlumaczy je wczesniej na `Error:`.
7. `docs/PROGRESS.md` nie byl aktualizowany w tej fali (zadanie koordynatora).
