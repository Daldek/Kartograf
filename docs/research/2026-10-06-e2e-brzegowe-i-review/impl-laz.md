# Naprawa LAZ — implementacja (2026-10-07)

Galaz `refactor/laz` (worktree `Kartograf-laz`), baza `a7bf7a8`. Zrodla:
`e2e-b-orto-laz-wycinek.md` (C13, UWAGI LAZ 1 i 3), `review-1-duplikacje.md`
(D17), `review-2-deklaracje.md` (N6, N15), `raport-koncowy.md` (backlog: LAZ
dubluje obszar, LAZ bez `parent_request`). Decyzja: nowy **ADR-029**.

## Wynik koncowy

- `pytest tests/ -m "not live"`: **2259 passed** (baza 2216; +43), 16
  deselected (`-m live --collect-only`: 16/2275).
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`:
  96 files already formatted.
- `mypy kartograf/`: 32 bledy; lista bez numerow linii **identyczna** z baza
  `a7bf7a8` (zaden z nich nie lezy w zmienianych plikach).
- `docs/DECISIONS.md`: CRLF zachowane (1453 linii = 1453 `\r`); pozostale
  pliki bez zmian koncowek.
- Nietkniete (zgodnie z zadaniem): `_download_with_retry`, `_make_request`,
  `_save_response` w `gugik_laz.py`, sekcje CLI spoza LAZ.

## Problem

1. **Zdublowany obszar.** Dedup po godle: kafle PL-1992 i PL-2000 tego samego
   miejsca maja rozne godla, wiec obszar w2 (`--bbox 637400,487000,637450,487050
   --bbox-crs EPSG:2180`) dostawal 2022/PL-2000:S7 (250 MB) **i** 2025/PL-1992
   (50 MB).
2. **D17.** Pula watkow, sidecar kafla i porazki kafli zyly w
   `_cmd_download_laz`; biblioteka nie miala API pobierania LAZ.
3. **N15.** Sidecar LAZ bez `extra.parent_request` (errata ADR-023 pkt 8).

## Decyzje projektowe

### Regula wyboru: zachlannie od najnowszego, wg ramy kafla

`select_newest_cover(tiles, area, tolerance_m)` (w `gugik_laz.py`), wolana
z `GugikLazProvider.select_tiles` po filtrze `--min-density`:

- kolejnosc: `akt_rok` malejaco, potem `akt_data` malejaco, gestosc
  malejaco, godlo, URL (deterministyczna; `akt_data` rozstrzyga dwie dostawy
  tego samego roku — Wroclaw 2025 ma dostawy 03-19 i 08-12);
- kafel jest pomijany, gdy `(rama ∩ obszar) \ ⋃(ramy wybranych + 1 m)` jest
  puste (pole <= 1e-6 m²); kafel wnoszacy niepokryty kawalek zostaje (caly);
- `--year`: odpytywany jeden rocznik, ta sama regula w jego obrebie.

**Dlaczego rama `msGeometry`, a nie obwiednia.** WFS zwraca prawdziwy
wielokat kafla (w osiach N,E — tak samo jak envelope). Ramy sa obrocone
wzgledem EPSG:2180 — nie tylko PL-2000 (w2: rama 2022 odchyla sie o ~14 m na
800 m), ale i PL-1992 (arkusze 1:2500 to trapezy z bokami-lukami).
Obwiednia "pokrywalaby" naroza, ktorych kafel nie ma — falszywe pominiecie
starszego kafla. Przeglad wszystkich 299 kafli z surowych odpowiedzi C13
(9 obszarow): 285 ram po 5 punktow, 14 po 9 (srodki bokow), wszystkie
pojedyncze `gml:Polygon`, zadna bez geometrii.

**Geometria bez nowych zaleznosci.** Ramy sa wypuklymi czworokatami, wiec
wystarcza arytmetyka wielokatow wypuklych (`kartograf/core/coverage.py`):
przeciecie Sutherlanda-Hodgmana, roznica `P \ Q` jako rozlaczne kawalki
`P ∩ H1..H(i-1) ∩ ¬Hi`, bufor = przesuniecie krawedzi. Wspolrzedne sa
przesuwane do rogu obszaru (pola przy 10^5-10^6 m tracilyby precyzje).
Normalizacja usuwa wierzcholki wspolliniowe do **10 cm**: boki
rownoleznikowe ramy 1:2500 sa w EPSG:2180 lukami, srodek boku odchyla sie
od cieciwy o ~3 cm (Krakow M-34-76-A-a-1-1-3) raz na zewnatrz, raz do
srodka — przy progu 2 cm rama wychodzila "wklesla" (mutacja M14).

**Tolerancja 1 m (`COVERAGE_TOLERANCE_M`).** Ramy roznych ukladow i kampanii
nie leza krawedz w krawedz (wspolrzedne zaokraglone do 1 cm, rozne ciecia
arkuszy); pas wezszy niz 1 m to 2-4 rzedy punktow przy 4-20 p/m² przy bledzie
polozenia 0,10-0,30 m (`blad_sr_syt`) — nie uzasadnia pobrania kafla
50-250 MB. Jednoczesnie 1 m jest o 2-3 rzedy wielkosci mniejszy od kafla
(~500-1100 m), wiec nie ukryje realnej luki w nowszej kampanii. Parametr
`tolerance_m` (`0` = dokladnie) jest w API.

**Zasady ostroznosci (watpliwosc = pobierz):**

- pokrywa tylko kafel `czy_ark_wypelniony` != `NIE` — rama arkusza
  niepelnego nie jest zasiegiem danych; w danych C13 (Wroclaw 2025) sa po
  dwie dostawy NIE tego samego arkusza: obie zostaja (dawny dedup po godle
  bral jedna dowolna);
- pokrywa sie rama albo tym samym godlem (ta sama rama arkusza — tak
  dziala tez kafel bez geometrii, co zachowuje dawny dedup po godle),
  **nigdy obwiednia**;
- rama niewypukla / multi / z otworem -> `footprint=None`: zasiegiem staje
  sie obwiednia (nadmiar = kafel latwiej zostaje), a kafel nie pokrywa innych;
- kafel bez geometrii (NaN) zostaje;
- kafel, ktorego rama nie przecina obszaru (przecina go tylko obwiednia,
  np. naroze obroconej ramy PL-2000), jest pomijany jako `outside` — nie
  wnosi danych. Guard osi (`returned and not kept`) dziala jak dotad na
  obwiedniach.

Pominiete kafle: `LazTileSelection.superseded` (`SupersededLazTile(tile,
covered_by)`, `reason` = `covered`/`outside`); CLI: jeden naglowek `Info:`
+ linia per kafel z kaflami pokrywajacymi, na stderr (takze z `-q`).

### API biblioteki (D17) — wzor `download_pl_cutout`

`kartograf/download/laz.py`:

- `GugikLazProvider.select_tiles(...)` -> `LazTileSelection` (krok discovery;
  `discover_tiles` = `select_tiles(...).tiles`, sygnatura bez zmian);
- `run_laz_download(selection, *, provider, bbox, output_dir, year,
  min_density, max_workers, force, on_progress, parent_request)` — pula
  watkow, `FileStorage(product="laz", vertical_crs=provider.vertical_crs)`,
  skip istniejacych, sidecar (`write_laz_sidecar`, dawny `_write_laz_sidecar`
  z CLI), porazki `DownloadError` zbierane w `failed` (posortowane po godle);
- `download_laz_area(bbox, ...)` — oba kroki; brak kafli = `NoCoverageError`
  (komunikat jak dotad `No LAZ tiles found ...`); jawny `vertical_crs`
  niezgodny z podanym providerem = `ValueError`;
- `LazDownloadResult(tiles, downloaded, skipped, failed, superseded)`,
  `.ok`; `LazTileFailure(tile, error)`.

Porazka kafla NIE jest wyjatkiem biblioteki (inaczej niz arkusz wycinka):
kafle LAZ sa niezalezne, czesciowy wynik ma wartosc, a wolajacy dostaje
pelna liste do ponowienia. CLI zachowuje fale A: `Error: N z M kafli LAZ
nie pobrano ...` + pelna lista, kod 1. Eksport w `kartograf/__init__.py`.
CLI dwuetapowe (select -> `Info:`/`Found N` -> run), bo drukuje miedzy krokami.

### `parent_request` (N15)

`_laz_parent_request(args, bbox)` w CLI: tylko `--bbox`/`--geometry`
(ADR-023 (f).1, godlo -> brak klucza); `--bbox` w ukladzie PODANYM (jak
tory NMT), `--geometry` jako obwiednia EPSG:2180, `countries: ["PL"]`.
Errata ADR-023 pkt 8 usunieta, ARCHITECTURE 3.4 / README poprawione.

### Zachowane

`Error:` + pelna lista + kod 1 (fala A), `request.year`/`request.min_density`
(fala B, E16), `parse_pl_uklad` (fala B, D3), osie (N,E) — dla envelope
i (nowe) ramy przez ten sam `_corner_xy`.

## Testy (+43)

| Plik | Co |
|---|---|
| `tests/test_laz_coverage.py` (nowy, 27) | geometria (`normalize_convex` na realnej ramie 9-punktowej, CW->CCW, odrzucenie wkleslej; roznica, bufor, suma pokryc); parsowanie ramy z surowego XML (osie E,N, `date`, `full_sheet`); `select_tiles` na surowym WFS w2: domyslnie tylko 2025, 2022/PL-2000 i 2023 pokryte przez 2025; obszar wychodzacy poza 2025 -> 2022 zostaje; `--year 2022`; rama poza obszarem = `outside`; KRON86 2018 pokrywa 2012; regula na kaflach syntetycznych: kolejnosc wejscia, suma pokryc, pas 0,5 m (tolerancja) vs 2 m, `tolerance_m=0`, NIE nie pokrywa, `akt_data` w roku, kafel bez geometrii, to samo godlo, obwiednia nie pokrywa, dwie dostawy NIE |
| `tests/test_laz_download.py` (nowy, 16) | `run_laz_download`: segment + sidecar (`request.year/min_density`, brak `parent_request` bez argumentu), `parent_request` w kazdym sidecarze, porazki zebrane (pelna lista, bez sidecara), skip/`force`, `superseded` przekazane, 3 watki + `on_progress`, KRON86; `download_laz_area` na surowym WFS w2 (pobrany tylko URL 2025, brak `pl_2000_*`), `--year 2022`, rocznik pusty -> `NoCoverageError` bez pobran, niezgodny pion; CLI na surowym WFS: tylko kafel 2025 + `Info:` z oboma pominietymi, `parent_request` w bbox (2180 i 4326 w ukladzie podanym), brak w trybie godla, `--year 2022` bez `Info:` |
| `tests/test_real_gugik_responses.py` | C13: test "dwa kafle w dwoch ukladach" zastapiony "2025/PL-1992 pokrywa oba uklady" (+ `superseded`) |
| `tests/test_cli.py` | mocki `discover_tiles` -> `select_tiles` (`_selection(...)`), `vertical_crs` providera |

Test C13 w nowej postaci pada na bazie `a7bf7a8` (sprawdzone `git stash`
kodu: `1 failed` w `-k c13`); pozostale nowe testy nie importuja sie na bazie
(brak `select_tiles`/`download.laz`).

## Mutacje (cala suita offline po kazdej; skrypt w scratchpadzie)

| # | Mutacja | Wynik |
|---|---|---|
| M1 | dedup pokryciowy wylaczony (`if False`) | 11 failed (m.in. w2 real, suma pokryc, tolerancja) |
| M2 | sortowanie od najstarszego roku | 18 failed |
| M3 | brak `parent_request` w sidecarze (biblioteka) | 4 failed (biblioteka + CLI) |
| M4 | tolerancja ignorowana (bufor 0) | 1 failed (`test_gap_within_tolerance_is_covered`) |
| M5 | kafel NIE pokrywa | 2 failed |
| M6 | osie ramy (N,E) niezamienione | 18 failed |
| M7 | obwiednia pokrywa | 1 failed (`test_envelope_alone_never_covers`) |
| M8 | `akt_data` ignorowana | **przezyla** -> test wzmocniony (godla odwrotnie do dat, commit `a184194`) -> 1 failed |
| M9 | CLI bez `Info:` | 1 failed |
| M10 | `parent_request` takze w trybie godla | 1 failed |
| M11 | `parent_request` w EPSG:2180 zamiast ukladu podanego | 1 failed |
| M12 | `failed` obciete do 1 kafla | 2 failed (CLI fala A + biblioteka) |
| M13 | kafel z rama poza obszarem zachowany | 1 failed |
| M14 | prog wspolliniowosci 2 cm | 1 failed (rama Krakowa "wklesla") |

Kazda mutacja przywracana z kopii zrodla; `git status` czysty po przebiegu.

## Commity

| Commit | Zakres |
|---|---|
| `dfe1372` | feat(laz): wybor kafli wg pokrycia obszaru od najnowszego rocznika |
| `a14febe` | feat(laz): API biblioteki download_laz_area, parent_request w sidecarze |
| `a184194` | test(laz): kolejnosc w roku po akt_data (mutacja M8) |
| `bd07710` | docs(laz): ADR-029, ARCHITECTURE 3.4/4.7, CLAUDE.md, README/PRD/SCOPE, CHANGELOG; errata N15 usunieta |
| (ten) | docs(research): raport impl-laz |

## Weryfikacja na zywo (jedno uruchomienie, 2026-10-07)

Kod worktree (`python -c "from kartograf.cli.commands import main; ..."`,
cwd = worktree), wynik w katalogu danych:

```
download --bbox 637400,487000,637450,487050 --bbox-crs EPSG:2180 --country pl \
  --product laz -o <katalog-danych>/kartograf/e2e/2026-10-07-laz/
```

Log (`<katalog-danych>/kartograf/e2e/2026-10-07-laz/run.log`):

```
Info: pominieto 2 kafli LAZ — obszar pokrywaja nowsze kafle (domyslnie najnowszy rocznik per obszar; starszy rocznik: --year)
  7.173.21.06.2 (2022, PL-2000:S7): pokryty przez N-34-139-A-c-1-1-3-4 (2025, PL-1992)
  N-34-139-A-c-1-1-3-4 (2023, PL-1992): pokryty przez N-34-139-A-c-1-1-3-4 (2025, PL-1992)
Querying GUGiK WFS for LAZ tiles (EVRF2007)...
Found 1 LAZ tiles. Downloading with 4 worker(s)...
  1/1 tiles
Downloaded 1 tiles (0 skipped) to .../2026-10-07-laz/laz
rc=0   (18,5 s)
```

(`Info:` stoi w logu przed `Querying...`, bo przy `tee` stdout jest
buforowany, a stderr nie; w terminalu kolejnosc jest naturalna.)

- Pobrany **tylko** `laz/pl_1992_evrf2007/N-34/139/A/c/1/1/3/4/83230_1743191_N-34-139-A-c-1-1-3-4.laz`
  (49 929 359 B, naglowek `LASF`) + sidecar; **brak** `laz/pl_2000_evrf2007/`
  (w rundzie 2026-10-06 ten sam obszar pobral dodatkowo 250 MB kafla 2022).
- Kafel 2025 pokrywa caly obszar (rama E 637068-637618, N 486690-487283
  wobec obszaru E 637400-637450, N 487000-487050) — oczekiwanie spelnione.
- Sidecar: `horizontal_crs` EPSG:2180, `vertical_crs` EPSG:9651,
  `extra.rok` 2025, `extra.parent_request` =
  `{"bbox": [637400.0, 487000.0, 637450.0, 487050.0], "bbox_crs": "EPSG:2180", "countries": ["PL"]}`.
- Cache SQLite nie powstal (LAZ nie uzywa cache rekordow); nic nie trafilo
  do repo.

## Otwarte / poza zakresem

- Duplikacja petli retry (`_download_with_retry` itd.) — inny agent.
- Wybor kafli nie przycina LAZ do obszaru: kafel wnoszacy maly kawalek
  jest pobierany caly (zgodnie z zadaniem).
- `gestosc`/`--min-density` nadal nominalne (bez zmian, udokumentowane).
