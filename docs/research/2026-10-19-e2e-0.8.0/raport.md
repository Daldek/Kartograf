# Test E2E przed tagiem v0.8.0 (2026-10-19): wszystkie dane, MCP, audyt dokumentacji, poprawki

Cel: pewnosc, ze Kartograf 0.8.0 dziala poprawnie na zywych uslugach (GUGiK, CUZK,
Copernicus/EEA, ISRIC) przed otagowaniem wersji deweloperskiej v0.8.0 i testami z
Archiwista i Retmanem. Dane wylacznie pod `<katalog-danych>` (udzial SMB/cifs bez
`serverino`, jawne `--output`), male wycinki; cache metadanych lokalnie w katalogu
roboczym kazdego przebiegu.

## Metoda

- **Czysta instalacja:** wheel i sdist zbudowane `python -m build` z `git archive` (runda 1:
  `develop` `e019126a`; runda 2: `integrate/e2e-fixes` `cf39177a`; smoke koncowy: `42ec581b`),
  zainstalowane z `[mcp]` w nowym venv Pythona 3.13 (pyproj 3.8.0, PROJ 9.8.1, bez siatek PROJ
  uzytkownika). CLI = skrypt `kartograf` z wheel, nie kod z drzewa.
- **Runda 1 (samodzielnie, bez MCP):** 5 rownoleglych wycinkow (A elevation; B imagery, maps,
  geodesy; C landcover, soil/HSG; D boundaries, cadastre, models3d, hydro, names; E projekt,
  API odczytu magazynu, parse/catalog/cache, warstwa komend, tryby aktualizacji, offline
  `unshare -rn`). Przypadki typowe (pierwsze pobranie, powtorka lokalna, `--check-updates`,
  `--upgrade`, `--json`) i brzegowe (granica PL-CZ `auto`, morze, brak danych, bledne wejscie,
  zakresy lat, PL-1992/PL-2000, EPSG:4326, mikro-bbox, offline, Ctrl-C, procesy rownolegle).
- **MCP z malym agentem (runda 1 i 2):** Claude Code `-p --model haiku`, `--strict-mcp-config`,
  tylko narzedzia `mcp__kartograf` (`kartograf-mcp --allow-dir <katalog-danych>`), bez
  wbudowanych narzedzi.
- **Audyt dokumentacji** (bez README) rownolegle z runda 1.
- **Poprawki** na 7 galeziach `fix/e2e-*` (kazda z testami regresji failing-before i dowodem
  na zywo przed/po), integracja na `integrate/e2e-fixes`, runda 2 (regresja wszystkich P2
  i poprawionych P3 + powtorka 1 307 polecen rundy 1 + smoke 13 grup), runda 3 poprawek
  i smoke koncowy na wheel z `42ec581b`.

Szczegolowe raporty (tabele przypadkow, polecenia, dowody) leza obok tego pliku:
`e2e-A.md` ... `e2e-E.md` (runda 1), `audyt-dokumentacji.md`, `fix-*.md` (poprawki),
`r2-reg.md`, `r2-mcp.md` (runda 2), `fix-round3.md` (runda 3).

## Podsumowanie

| Etap | Zakres | P1 | P2 | P3 |
|---|---|---|---|---|
| Runda 1, A elevation | 464 wywolania, 52 scenariusze | 0 | 3 | 19 |
| Runda 1, B imagery/maps/geodesy | 397 wywolan, 70 scenariuszy | 0 | 1 | 15 |
| Runda 1, C landcover/soil | ok. 450 wywolan, 98 przypadkow | 0 | 8 | 26 |
| Runda 1, D kolekcje | 310 przypadkow CLI | 0 | 2 | 12 |
| Runda 1, E projekt/magazyn | 718 wywolan, 133 przypadki | 0 | 2 | 25 |
| Runda 2, regresja | 32 pozycje, 1 307 powtorzonych polecen, smoke 13 grup | 0 | 1 (nowe, nie regresja) | 7 |
| Runda 2, MCP haiku | 6 zadan | 0 | 0 | 5 |
| Smoke koncowy (`42ec581b`) | 22 polecenia, 13 grup | 0 | 0 | 0 |

P1 (zle dane, cicho bledny wynik, utrata danych) nie znaleziono w zadnej rundzie. Dane
zweryfikowane niezaleznie: wycinki WCS PL bit w bit z oknem arkusza, reprojekcje S-JTSK/TM33
zgodne z przypieta operacja (srednio 0,025 m), GPKG kolekcji zgodne z liczbami obiektow
uslug i sidecarami, raster SoilGrids == bezposrednie WCS, LAS/ZIP/sidecary poprawne.
Parytet biblioteka == CLI `--json` (ok. 70 porownan) i MCP == CLI (16 porownan) bez roznic.

## Znaleziska P2 i ich stan

| Id | Opis | Stan |
|---|---|---|
| A P2-1, E P2-1 | Na SMB bez `serverino` dowiazanie sciezki standardowej cofalo sie na starszy lot, `link_target()` zwracal `None`, zbedne przepisanie sidecara dowiazania | naprawione (`fix-links.md`; potwierdzenie trescia bez liczby dowiazan); runda 2: 210/210 |
| A P2-2 (+B/D/E P3) | Surowe `UserWarning` pyproj i nieprefiksowane linie loggera na stderr, takze w `--json` | naprawione (`fix-stderr.md`); stderr 0 B |
| A P2-3 | `--check-updates`/plan: arkusze bez danych jako `check_failed`, kod 1 | naprawione (`fix-pl-sheets.md`) |
| B P2-1, C P2-5, D P2-2 | Ctrl-C przy `--workers >= 2` nie zatrzymywal kolejki, zatwierdzal jednostki; SIGTERM bez obslugi | naprawione (`fix-cancel.md`; `kartograf.interrupt.run_parallel`, kod 143); runda 2: wyjscie 0,2-2,4 s, 0 wersji po sygnale |
| C P2-1, P2-2 | CORINE: podglad 2012/2006/2000 nie dzialal; pusty PNG zapisywany jako wersja | naprawione (`fix-landcover-soil.md`) |
| C P2-3, P2-4 | SoilGrids `ocd`/`ocs` nie dzialaly; jednostki w opisach niezgodne z plikami | naprawione; `extra.units` w sidecarze |
| C P2-6, P2-7 | BDOT10k z obszaru bez limitu 100 plikow/10 GB; `--layers` z klasa nieobecna w powiecie = blad | naprawione |
| C P2-8 | Zly CRS bbox (metry z EPSG:4326) = wyjatki wewnetrzne / zapytania z `inf` | naprawione (walidacja centralna, kod 2) |
| D P2-1 | `cadastre map --country auto`: obszar tylko w PL w prostokacie CZ przerywal cale zadanie | naprawione (`fix-collections.md`) |
| E P2-2 | Kafel LAZ: `Sidecar.unit` i `file_footprint` z bbox zadania zamiast kafla | naprawione (`fix-store-project.md`) |
| R2 N-P2-1 | `file_footprint()` rzucal `TransformUnavailableError` dla wpisow `OGC:CRS84` (names, granice specjalne) na PROJ 9.8 | naprawione (`fix-round3.md`); smoke: 25/25 wpisow bez bledu |

Najwazniejsze P3 naprawione: rodzaje porazek `no_coverage`/`year_out_of_range`, `--workers
>= 1` we wszystkich torach, bbox zerowej powierzchni i punkt w `--geometry` (blad z
`option=geometry` tam, gdzie potrzebny obszar), availability (obwiednia kraju, obszar bez ladu,
`--min-density`), podpowiedzi `Przyklad:` wg produktu i trybu, podpowiedz zakresu lat,
czesciowy sukces `auto` w kolekcjach = kod 0, krotka lista jednostek, cache wyszukania KU
RUIAN (offline), `project download --force` naprawia uszkodzona wersje, przyklady USAGE 1.1
sprawdzone na zywo. Pelna lista: `docs/CHANGELOG.md` [0.8.0] (wpisy "test E2E 2026-10-19")
i erraty ADR (DECISIONS, "test E2E 0.8.0").

## MCP z malym agentem (haiku)

Runda 1 (wheel `e019126a`, 7 zadan): serwer `connected`, 29 narzedzi; wszystkie odpowiedzi
poprawne (NMT 5 m: rok 2019, sha `23d160d0...` = pobranie CLI; granice gmin; glina
SoilGrids; arkusz na morzu - agent wyjasnil brak ladu i nic nie pobral; Cieszyn PL+CZ;
projekt init/add/download/status; przeglad magazynu). Koszt 0,005-0,01 USD i 10-34 s na
zadanie. Luka: narzedzia MCP nie daja obrysu w WGS84 (`file_footprint` jest tylko w
bibliotece) - agent odmowil zgadywania.

Runda 2 (wheel `cf39177a`, 6 zadan, `r2-mcp.md`): 6/6 poprawnych, 17 wywolan narzedzi
(2 oczekiwane `is_error`), 0,037 USD lacznie; mapa katastralna `auto` dla obszaru PL dziala
(plik PL + `auto_partial_success`), zly CRS bbox daje `invalid_input` z `option=bbox`, agent
dostaje pola KD (`full_m2`, `campaign_coverage`) jednym wywolaniem; stderr serwera czysty.
Uwaga metodyczna: w rundzie 1 skrypt uruchamial `claude -p` w petli `while read` bez
`</dev/null`; wyniki rundy 1 zgadzaja sie z poleceniami, runda 2 powtorzona poprawnie.

## Audyt dokumentacji

`audyt-dokumentacji.md`: 17 poprawek w 8 plikach (CLAUDE.md, USAGE, ARCHITECTURE, CHANGELOG,
DECISIONS, PRD, SCOPE, STANDARDS), 400 przykladow CLI przez prawdziwy parser, 54 bloki
Pythona zgodne z API, 274 linki. README poza zakresem (nastepny krok).

## Smoke koncowy (wheel `42ec581b`)

22 polecenia w 13 grupach (`--json`): NMT arkusz + powtorka + `--check-updates` pierwszego
przykladu USAGE 1.1 (kod 0), availability PL i CZ, wycinek orto, BDOO, SoilGrids, HSG,
granice gmin i specjalne, nazwy, mapa katastralna `auto` (obszar PL), sieci wodne CZ,
osnowy, ZTM CZ, bledne wejscia (zly CRS bbox, `--workers 0`), `parse`, `catalog`: wszystkie
kody zgodne z oczekiwaniem, stderr pusty poza dozwolonymi liniami ponowien HTTP.
`file_footprint` na calym magazynie smoke: 25 wpisow, 0 bledow. Jedna awaria uslugi
(WFS osnow GUGiK: zerwane polaczenia, 3 proby) - powtorzenie po chwili: kod 0.

## Otwarte (do decyzji, bez wplywu na poprawnosc danych)

- SIGTERM w serwerze MCP: zostaje domyslne zakonczenie procesu (opcje w `fix-cancel.md`).
- `project download` zadania `--country auto` z czesciowym sukcesem: zadanie atomowe nie
  przypina czesci PL (kod 1), a ostrzezenie biblioteki mowi o kodzie 0 (`r2-reg.md` N-P3-5).
- Obrys w WGS84 przez MCP (narzedzie albo pole w `store_entries`) - funkcja na pozniej.
- Dowiazanie bez czytelnego sidecara moze sie nadal cofnac na SMB bez `serverino`
  (`fix-links.md`); niezalezna kopia z ta sama trescia jest teraz rozpoznawana jako wersja.
- Komunikaty argparse po angielsku (znane od 2026-10-17), pasek postepu na stdout bez TTY.
- Data wydania 2026-10-17 w CHANGELOG/SCOPE/PRD przy braku tagu.
- Nie sprawdzone: pobranie CORINE z CLMS (brak `CLMS_CREDENTIALS`, decyzja uzytkownika),
  magazyn na SMB z `serverino`, skala 50 tys. slotow, pelne arkusze orto 0,3-1,3 GB.
