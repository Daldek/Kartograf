# Plan E — pozostale produkty GUGiK/CUZK (24 pozycje) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Najpierw Task E0. Potem pakiety E1-E5 moga isc rownolegle, kazdy u innego wykonawcy. Pakiet nie edytuje plikow innego pakietu; wyjatkiem sa bloki w plikach wspolnych (sekcja "Mapa plikow"). Task EZ wykonuje integrator po scaleniu E1-E5.

**Data:** 2026-10-15

**Goal:** Wszystkie 24 pozycje planu E (spec 6) sa w 0.8.0 pobieralne z CLI
i API. Kazda trafia do magazynu wersjonowanego (ADR-036) z sidecarem
`kartograf-meta/1` i sygnalem swiezosci kanalu (K6). Kazda ma wpis
w `list-sources` i test zgodnosci CLI = API (ADR-037). Plan E nie tworzy
nowych silnikow pobierania. Rozszerza silniki planow C i D tam, gdzie
produkt tego wymaga (Task E0, E1).

**Architecture:** Produkty dodane do istniejacych komend uzywaja ich funkcji
biblioteki: `elevation download` i `imagery download` -> `download_data`/
`check_data`, `landcover download` -> `LandCoverManager`. Pozostale grupy
uzywaja `download_collection`/`check_collection` z planu C: grupy C/D
(`boundaries`, `cadastre`, `models3d`) i nowe grupy planu E (`names`, `maps`,
`geodesy`). Rozszerzenia planu E:
(1) jednostki `sheet`, `tile` i `ku` w `unit_package` oraz adres pliku
z rekordu indeksu (E0); (2) sygnal `index` w torze `collection` (E0);
(3) parametry wyboru `format`, `scale`, `sheet_system`, `network` i `ku`
w API kolekcji (E0); (4) protokol OGC API Features w `feature_bbox` (E0);
(5) selektor `woj` i `https` w `AtomFilesParams` planu D (E1);
(6) 8-czlonowe godla PL-1992 w `SheetParser` (E1).

**Spec:** `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`
(K1-K10, sekcje 5, 6, 6.1, 7, 8). Pomiary: `docs/research/2026-10-15-plan-e/raport.md`
(stan zrodel 2026-10-15; dalej "raport E"),
`docs/research/2026-10-13-katalog-produktow/{raport,probki}.md`.

**Wersja docelowa:** 0.8.0. **ADR:** ADR-043 "Plan E: produkty jednostkowe,
arkuszowe i krajowe na silnikach C/D" (`docs/DECISIONS.md`). Tekst powstal
w Task E0 (D1-D10); wyniki E2E i ostateczne nazwy symboli E1-E5 dochodza
w Task EZ jako errata.

**Kod wyjsciowy:** `develop` `1b8e358`. Sa na nim grupy CLI (ADR-039),
spec i plan manifestu (ADR-040) oraz plany A i B. Plany C i D (ADR-042)
sa w commicie `7e3f31e` na galezi `docs/plans-cd`:
`docs/superpowers/plans/2026-10-15-plan-c-silniki-i-dane-pl.md`, sekcja
"Kontrakt silnikow i orkiestratora", oraz `...-plan-d-dane-cz.md`, Task 2
i 5. Plan E korzysta z tych symboli:
- parametry kanalow w `kartograf/sources/descriptor.py`:
  - `UnitPackageParams(unit: "powiat"|"woj"|"country", variants: tuple[PackageVariant, ...], members, unpack)`;
  - `PackageVariant(choice, url_template, edition, segment_tokens, vertical_crs)`; tokeny szablonu w C to tylko `{teryt}` i `{woj}`;
  - `FeatureBBoxParams(protocol: "wfs"|"arcgis", native_crs, axis_order, page_size, layers: tuple[FeatureLayer, ...], selection: "level"|"all", order_field, drop_fields)`;
  - `FeatureLayer(code, source, name, id_field)`;
  - z planu D: `AtomFilesParams(service_feed, entry_pattern, crs, members, segment_tokens)` i `WcsCutoutParams(variant, coverage_id, native_step, resolutions, max_native_pixels)`;
- silniki:
  - `kartograf/transport/unit_package.py` (`select_variant`, `package_url`, `fetch_package`; 404 = `NoCoverageError`);
  - `kartograf/transport/feature_bbox.py` (`count_features`, `fetch_features`);
  - `kartograf/transform/gpkg.py::write_gpkg`;
  - `kartograf/transport/atom.py` (`atom_index`, `resolve_atom_file` -> `AtomFile(url, length, updated, edition, crs)`);
- orkiestrator `kartograf/download/collections.py`:
  - `download_collection(*, product, output_dir, country=None, teryt=None, sheet=None, bbox=None, geometry=None, layer=None, whole_country=False, level=None, lod=None, year=None, horizontal_crs=None, update=None, plan=None, workers=1, cache=True, on_notice=None) -> CollectionReport(files: tuple[UnitFile, ...], failed, stale, notices, ok)`;
  - `check_collection(...) -> UpdatePlan`, `validate_collection_request(...) -> CollectionRequest`;
  - tor planu `collection`; `Notice` `UNIT_LIST` i `WHOLE_COUNTRY_SIZE`;
- magazyn: `kartograf/download/storage.py::unit_slot(output_dir, segment, ext, *, teryt=None, bbox=None, sheet=None, country=None, related_roots=())` i `content_segment(key, tokens)`;
- CLI: grupy `boundaries`, `cadastre`, `models3d`, `hydro`, handler `kartograf/cli/collection_cmd.py`;
  nowe grupy z `--product` i `--country pl|cz|auto`; `--source` zostaje tylko w `landcover`;
  wybor ukladu pliku krajowego przez `--horizontal-crs` (`horizontal_crs=`);
- `sheet=` w `download_collection` znaczy obszar arkusza (ADR-039 D4) i dla
  produktow C/D tak zostaje.

Przed Task E0 porownaj ten kontrakt z kodem C/D na `develop`.
Inna nazwa w kodzie: zmien wywolania w planie E, bez drugiego silnika.
Inny ksztalt interfejsu: zatrzymaj sie i opisz roznice koordynatorowi.

**Korekta 2026-10-16 (po Task E0).** Interfejsy E0 w tym planie (sekcja
"Decyzje" pkt 3-4 i 6, Task E0 "Interfaces", deskryptory E2-E5) opisuja
kod E0, nie projekt z 2026-10-15. Roznice wobec pierwszej wersji:
- `SheetGrid(system="1992"|"cuzk", parts, layer, crs)`: bez siatki PL-2000
  i bez `scale` (zaden produkt kolekcji jej nie potrzebuje); warstwa CUZK
  ma jawny uklad natywny `crs`.
- `IndexSource` bez `layers`: warstwa WMS albo typ WFS indeksu jest
  w wariancie (`PackageVariant.index_layer`, skala mapy = warstwa).
  `parser` tylko `map_links` - parser `skorowidz` (GFI `skor.push`) jest
  zbedny, bo intensywnosc, true orto i orto ukosna ida torem providera
  orto (E1), nie kolekcja; `url_field=None` dla `map_links` (link na
  format); dochodzi `zone_field` (uklad kafla -> katalog slotu i uklad
  sidecara).
- `AtomFilesParams.choice` (jeden feed na format, np. Geonames GPKG/FGDB)
  i `FeatureBBoxParams.timeout` (wolna usluga; jawny `timeout` wywolania
  ma pierwszenstwo, potem kanal, potem `SERVICE_TIMEOUT` 60 s).
- `UnitPackageParams.ku_layer` to pelny adres warstwy RUIAN
  (`.../RUIAN/MapServer/7`), nie numer.
- Capability kanalu kolekcji nie musi byc unikalna: kanaly jednego rodzaju
  (usluga WFS na siec) dziela ja i deklaruja te same uklady (ADR-043 D6,
  test rejestru).
- Sygnal `index`: etykieta rekordu = wydanie wersji (ADR-043 D4); kanal
  ma `index` wtedy i tylko wtedy, gdy ma `IndexSource` (test rejestru).
- `DOWNLOAD_SIZE`: `HEAD` przed kazdym plikiem jednostki (takze C/D),
  `Notice` dla pliku ponad 100 MiB w chwili jego pobrania, bez sumy przed
  pierwszym `GET` (pkt 6).
- Pomiary 2026-10-16: OGC API PRNG 78-95 s na kazde `items` niezaleznie
  od `limit`, OGC API PRG 3,5 s; PRG ma 51 kolekcji = 6 `Granica*` + 45
  innych (nie 46); WFS osnowy grawimetrycznej odpowiada pod
  `.../OsnowaGrawimetryczna/WFS` (bez `/WFS` nie), obiekty bez `gml:id`
  (identyfikator `nr_punktu`); RCN 1261 ma 301 623 607 B (2026-10-15:
  236 404 584 B - plik `latest_exports` jest podmieniany); mesh 3D: jeden
  rekord na kafel, Krakow 3884 kafle po ok. 37 MB.
- Wnioskowanie `--sheet-system` ZTM z godla nie jest w E0: robi je E2.

---

## Statusy produktow

`do implementacji` znaczy: kanal danych potwierdzony 2026-10-15 (raport E),
plan kompletny. `pytanie Pn` znaczy: jedna decyzja uzytkownika (sekcja
"Pytania"); plan opisuje obie odpowiedzi, a reszta produktu nie czeka.

| # | Produkt (klucz deskryptora) | Komenda i wybor | Pakiet | Status |
|---|---|---|---|---|
| 1 | NMT 100 m (`pl.gugik.nmt_100m`) | `elevation download --product nmt --resolution 100m` | E1 | do implementacji (P1: uklad wysokosci nieznany) |
| 2 | Obrazy intensywnosci (`pl.gugik.intensity`) | `imagery download --product intensity` | E1 | do implementacji |
| 3 | True orto (`pl.gugik.orto_true`) | `imagery download --product true-orto` (arkusze; `--cutout`) | E1 | do implementacji |
| 4 | Orto ukosna (`pl.gugik.orto_oblique`) | `imagery download --product oblique-orto [--direction]` | E1 | do implementacji |
| 5 | Mesh 3D (`pl.gugik.mesh_3d`) | `models3d download --product mesh` | E5 | do implementacji |
| 6 | Modele drzew 3D (`pl.gugik.trees_3d`) | `models3d download --product trees` | E5 | do implementacji |
| 7 | Wizualizacje BDOT10k (`pl.gugik.bdot10k_maps`) | `maps download --product topographic --country pl` | E2 | do implementacji |
| 8 | BDOO (`pl.gugik.bdoo`) | `landcover download --source bdoo --year R` | E4 | do implementacji |
| 9 | PRG punkty adresowe (`pl.gugik.prg_addresses`) | `boundaries download --product addresses` | E3 | do implementacji |
| 10 | PRG granice specjalne (`pl.gugik.prg_special`) | `boundaries download --product special` | E3 | do implementacji |
| 11 | PRNG nazwy RP (`pl.gugik.prng`) | `names download --product geographic --country pl` | E2 | do implementacji |
| 12 | PRNG nazwy swiata (`pl.gugik.prng_world`) | `names download --product world` | E2 | do implementacji |
| 13 | Osnowy podstawowe (`pl.gugik.prpog`) | `geodesy download --product control --country pl --network ...` | E5 | do implementacji |
| 14 | RCN (`pl.gugik.rcn`) | `cadastre download --product prices` | E3 | do implementacji |
| 15 | Quasi-geoida PL-geoid2021 (`pl.gugik.quasigeoid`) | `geodesy download --product geoid --country pl --whole-country` | E5 | do implementacji |
| 16 | CZ warstwice (`cz.cuzk.zabaged_contours`) | `elevation download --product contours --country cz` | E1 | do implementacji |
| 17 | CZ Data50 (`cz.cuzk.data50`) | `landcover download --source data50` | E4 | do implementacji |
| 18 | CZ Data250 (`cz.cuzk.data250`) | `landcover download --source data250` | E4 | do implementacji |
| 19 | CZ mapa katastralna (`cz.cuzk.cadastral_map`) | `cadastre download --product map --country cz --ku ...` | E3 | do implementacji (SHP, DXF, DGN, VFK); VKM poza 0.8.0 (P2) |
| 20 | CZ Geonames (`cz.cuzk.geonames`) | `names download --product geographic --country cz` | E2 | do implementacji |
| 21 | CZ ZTM (`cz.cuzk.ztm`) | `maps download --product topographic --country cz` | E2 | do implementacji |
| 22 | CZ QGZU (`cz.cuzk.qgzu`) | `geodesy download --product geoid --country cz --whole-country` | E5 | do implementacji |
| 23 | CZ Bodove pole (`cz.cuzk.survey_control`) | `geodesy download --product control --country cz --network ...` | E5 | do implementacji |
| 24 | CZ jednostki geomorfologiczne (`cz.cuzk.geomorphology`) | `boundaries download --product geomorphology --country cz --level ...` | E3 | do implementacji |

Inwentaryzacja mowila o jednym kluczu `cz.cuzk.data50_250`. Data50
i Data250 to dwa zbiory (osobne feedy, uslugi i rozmiary), wiec dostaja dwa
deskryptory i dwa wybory `--source`.

## Pytania do uzytkownika

Obie rozstrzygniete przez uzytkownika 2026-10-15 (ADR-043 D10).

- **P1 - uklad wysokosci NMT 100 m.** ATOM i CSW GUGiK go nie podaja.
  Model pochodzi z NMT LPIS, a GUGiK opisuje NMT z lat 2000-2019 jako
  PL-KRON86-NH. Inwentaryzacja z 2026-10-13 podala EVRF2007 bez zrodla.
  **Decyzja:** uklad wysokosci NIEZNANY. Wariant bez ukladu wysokosci,
  segment `nmt/pl_1992_100m` (bez tokenu ukladu), sidecar
  `vertical_crs: null` z adnotacja o zrodle ("GUGiK nie deklaruje ukladu
  wysokosci"), `--vertical-crs` dla 100 m = `ValidationError`. Dotyczy
  tylko kroku "Wariant 100 m" w Task E1.
- **P2 - format VKM mapy katastralnej CZ.** To pilot: feed `KM-KU-VKM` ma
  10 KU, a pliki 2026-10-15 zwracaly 404 (raport E, wiersz 19).
  **Decyzja:** VKM poza 0.8.0 (wpis w backlogu PROGRESS z dowodem 404).
  SHP, DXF, DGN i VFK pokrywaja caly kraj i wchodza.

## Kolejnosc i zaleznosci

```
A (rejestr wariantow ADR-041, WfsIndex) ----+
B (elevation CZ, SheetIndex, sygnal http) --+
C (kolekcje, unit_package, feature_bbox) ---+--> E0 --+--> E1 elevation, imagery     (A, B, D)
D (atom.py, horizontal_crs, wycinek orto) --+         +--> E2 names, maps             (C, D)
                                                      +--> E3 boundaries, cadastre    (C, D)
                                                      +--> E4 landcover               (C, D)
                                                      +--> E5 models3d, geodesy       (A, C, D)
                                                                  E1..E5 --> EZ
```

- **A:** E0 korzysta z `WfsIndex` (kafle mesh). E1 dopisuje 100 m do rejestru
  wariantow (`kartograf/sources/variants.py`, `SourceDescriptor.variants`).
  Plan A NMT 100 m nie obejmuje (spec 3.2: "NMT 100 m z ATOM - plan E"),
  wiec E1 tylko dodaje wpis rejestru; druga lista rozdzielczosci nie
  powstaje.
- **B:** E1 (warstwice) uzywa toru arkuszy CZ (`download/cz_sheets.py`,
  `SheetIndex.sm5_sheets_for_bbox`) i flagi `--country cz` w `elevation`.
- **C:** wszystkie pakiety. `download_collection`, `unit_package`,
  `feature_bbox`, tor `collection`; grupy `boundaries`, `cadastre`,
  `models3d`; BDOT10k archiwalny w `LandCoverManager` (wzorzec dla BDOO);
  rozpakowanie jednego GPKG (EGiB, wzorzec dla RCN).
- **D:** `transport/atom.py` z `AtomFilesParams` (NMT 100 m, Geonames,
  Data50/250, QGZU); `--horizontal-crs` pliku krajowego CZ; ZABAGED
  w `LandCoverManager` (wzorzec dla Data50/250); flagi wycinka obrazu
  (`--cutout`, `--horizontal-crs`, `--resolution <etykieta K2>`,
  `--coverage`) i wycinek orto w magazynie (wzorzec dla true orto).
- **Manifest (ADR-040), warunkowo:** jesli `kartograf/project/commands.py`
  jest na `develop` (`git ls-tree develop kartograf/project/commands.py`),
  pakiet wykonuje krok "Manifest". Inaczej opisuje go w commicie dla
  koordynatora (spec manifestu, sekcja 5: "kto scala sie pozniej, dopisuje
  pozycje").

## Global Constraints

- Python z `.venv`, uruchamiany z korzenia worktree: `.venv/bin/python -m pytest`,
  `-m ruff`, `-m mypy`; CLI `python -m kartograf.cli.commands ...`.
- TDD: kazdy krok "Test RED" to test zachowania. Uruchom go i zobacz porazke
  z wlasciwego powodu; dopiero potem implementacja. Bez testow okablowania,
  kopii stalych i tekstu zrodla (STANDARDS 10).
- Testy offline na fixturach z prawdziwych odpowiedzi, przycietych (kilka
  obiektow, dwie strony, jedna warstwa). Fixtury nagrywa krok "Fixtury"
  pakietu. Siec tylko w swiadomych krokach live. Dane z jawnym
  `--output <katalog-danych>`, nigdy w repo ani w `/tmp`; sciezki katalogu
  danych nie zapisuj w repo.
- Identyfikatory i docstringi po angielsku. Komunikaty dla uzytkownika po
  polsku w ASCII (Z5). `ValidationError` przed siecia, `DownloadError` przy
  awarii zrodla (STANDARDS 11). CLI tylko tlumaczy na API (ADR-037).
- Bez wartosci domyslnych wplywajacych na dane (STANDARDS 11.2). Wymagane sa:
  produkt, wariant (rozdzielczosc, format, skala, uklad arkuszy, siec, uklad
  pliku krajowego, rok tam, gdzie jest wybor), obszar albo jednostka,
  `--output`. Parametr z jedna dopuszczalna wartoscia mozna pominac;
  wartosc spoza listy to `Error:` z lista dopuszczalnych.
- Odpowiedz HTML albo wyjatek OGC przy kodzie 200 to `DownloadError`.
  Niepelne stronicowanie albo przeciete ZIP tez: zadna wersja nie powstaje.
  Usluga WMS nigdy nie jest kanalem danych; jest tylko indeksem (GFI).
- `opendata.geoportal.gov.pl` ignoruje `Range`: pobieranie strumieniowe przez
  `download_to` do stagingu. ZIP sprawdzany na pliku (`zipfile` na dysku),
  nigdy w RAM. Plik powyzej 100 MiB: `HEAD` i `Notice` z rozmiarem przed
  pierwszym `GET`; `check_*` nie pobiera danych.
- Brama przed kazdym commitem: `pytest tests/ -m "not live" -q`,
  `ruff check .`, `ruff format --check .`, `mypy kartograf/ tests/`.
  Commity Conventional po polsku, autor `Daldek <git@debever.pl>`, bez
  `Co-Authored-By`. `docs/DECISIONS.md` - zachowaj CRLF.
- Testy, ktore przypinaja usuwane zachowanie, usuwaj albo przepisuj na nowa
  intencje. Bez aliasow i podwojnych sciezek.

## Decyzje implementacyjne

1. **Grupy i wybory CLI** (ADR-039: grupa = typ danych). Nowe grupy maja
   `download` i `list-sources`; `availability` zostaje tylko w `elevation`
   (spec 4: "Inne grupy - tylko gdy pojawi sie potrzeba"). Nazwy produktow
   sa unikalne w obrebie kolekcji, bo `download_collection(product=...)`
   nie dostaje nazwy grupy.

   | Grupa | Funkcja biblioteki | Wybory planu E | Nowe flagi grupy |
   |---|---|---|---|
   | `elevation` | `download_data` | `--product nmt --resolution 100m` (PL), `--product contours --country cz` | `--format SHP\|DGN` (tylko `contours`) |
   | `imagery` | `download_data` | `--product intensity\|true-orto\|oblique-orto` (PL) | `--direction n,e,s,w` (tylko `oblique-orto`, filtr) |
   | `landcover` | `LandCoverManager` | `--source bdoo\|data50\|data250` | brak (flagi C/D: `--year`, `--layers`, `--whole-country`, `--horizontal-crs`) |
   | `boundaries` | `download_collection` | `--product addresses\|special` (PL), `geomorphology` (CZ) | `--format SHP\|GML` (pliki krajowe) |
   | `cadastre` | `download_collection` | `--product prices` (PL), `--product map --country cz` | `--ku KOD`, `--format SHP\|DXF\|DGN\|VFK` (mapa CZ) |
   | `models3d` | `download_collection` | `--product mesh\|trees` (PL) | brak (`--lod`, `--year` z C) |
   | `names` (nowa) | `download_collection` | `--product geographic --country pl\|cz`, `--product world` | `--format`, `--whole-country`, `--horizontal-crs` |
   | `maps` (nowa) | `download_collection` | `--product topographic --country pl\|cz` | `--scale 1:N`, `--format TIFF\|PDF\|DGN\|SHP`, `--sheet-system sjtsk\|etrs89` (CZ) |
   | `geodesy` (nowa) | `download_collection` | `--product control\|geoid --country pl\|cz` | `--network ...`, `--teryt`, `--whole-country` |

   - `geodesy` obejmuje osnowy PL i CZ oraz modele quasi-geoidy PL i CZ.
     Spec 6.1 zostawia grupe osnow i quasi-geoid na plan, ktory je
     wprowadza. Jedna grupa, bo uzytkownik szuka tych danych razem
     (wysokosci GNSS i punkty osnowy).
   - Wartosci `--format` wielkimi literami, jak w `landcover --format GPKG|SHP`.
     `--scale` w postaci `1:10000`, jak `--scale` w `elevation`.
     Wartosci `--network`: `horizontal`, `vertical`, `gravity` (PL i CZ),
     `magnetic`, `archive-1942`, `archive-kronsztadt60` (PL), `gnss`,
     `densification`, `horizontal-detailed`, `vertical-detailed` (CZ).
     `--level` geomorfologii po czesku w ASCII, jak poziomy RUIAN w planie D:
     `subprovincie`, `oblast`, `celek`, `podcelek`, `okrsek`, `podokrsek`,
     `cast`.
   - `--country auto` jest dozwolone, gdy kazda podana flaga wariantu jest
     poprawna w obu krajach (np. `names --product geographic --bbox ...`,
     `geodesy --product control --network vertical`). Inaczej
     `ValidationError` z wartosciami per kraj, np. `maps` z `--scale 1:5000`
     (tylko CZ). Podzial obszaru na kraje robi mechanizm C/D.
2. **API.**
   - `download_data`/`check_data` dostaja `format: str | None` (warstwice)
     i `direction: str | Sequence[str] | None` (orto ukosna). `None` znaczy
     wszystkie cztery kierunki: arkusz orto ukosnej to cztery pliki, nie
     warianty do wyboru (STANDARDS 11.2: `None` = "nie podano").
   - `download_collection`/`check_collection`/`validate_collection_request`
     dostaja `ku`, `format`, `scale`, `sheet_system` i `network` (wszystkie
     `str | None`; inny typ, takze `teryt`/`sheet`, = `ValidationError`).
     Wartosci sa kluczami `choice` w `PackageVariant` (C), w
     `FeatureBBoxParams` i w `AtomFilesParams` (E0, pkt 3). Bez nowych list
     w kodzie (K1).
   - `LandCoverManager` przyjmuje zrodla `bdoo`, `data50` i `data250`
     z opcjami w `OPTIONS`/`REQUIRED` (`kartograf/landcover/manager.py:77-115`).
   - Nowe eksporty w `kartograf/__init__.py` nie sa potrzebne.
3. **Rozszerzenia silnikow C (E0, ADR-043 D1-D9), w slownictwie planu C.**
   - `UnitPackageParams.unit` dostaje wartosci:
     - `sheet`: arkusze obszaru z serii PL-1992 o `parts` czlonach
       (`find_sheets_for_bbox`) albo z warstwy `layer` indeksu CUZK
       `KladyMapovychListu` w jej ukladzie `crs`
       (`SheetIndex.sheets_for_bbox`, `SheetIndex.sheet`); siatka jest cecha
       wariantu (`PackageVariant.sheet_grid`);
     - `tile`: kafle z rekordow indeksu WFS (`WfsIndex.features` z planu A,
       stronicowanie `next`);
     - `ku`: katastralni uzemi z RUIAN (`ku_layer` =
       `.../RUIAN/MapServer/7`, pole `kod`).
   - Jednostka `sheet` dziala tylko dla kanalu z `unit="sheet"`. Dla
     produktow C/D `sheet=` dalej oznacza obszar arkusza (ADR-039 D4).
   - `UnitPackageParams` dostaje `themes: tuple[str, ...] = ()`: plik
     krajowy z kilku plikow (PRNG: miejscowosci i obiekty
     fizjograficzne); kazdy temat to osobna jednostka `country/pl-<temat>`.
   - `UnitPackageParams` dostaje `index: IndexSource | None`: rekord
     indeksu daje URL pliku i etykiete wersji.
     - Zrodla rekordow: WMS GFI z parserem `map_links` (tabela linkow
       wizualizacji BDOT10k) albo WFS (`URL_do_pobrania` mesh); warstwa
       w `PackageVariant.index_layer`.
     - `PackageVariant.url_template` moze byc `None`, gdy URL daje rekord.
       Wariant wskazuje wtedy link rekordu kluczem `format`.
   - Tokeny `url_template` poza `{teryt}`/`{woj}`: `{sheet}`, `{ku}`,
     `{theme}`. Skala, uklad i format sa literalami szablonu
     w `PackageVariant` danej kombinacji (ZTM: 36 wariantow = 36
     opublikowanych uslug).
   - `PackageVariant.file_kind` (`zip` domyslnie, `tiff`, `pdf`, `txt`):
     pliki bez ZIP (mapy, PDF ZTM, model PL-geoid2021) sprawdzane po
     zawartosci zamiast katalogu ZIP z planu C.
   - `FeatureBBoxParams.protocol` dostaje `"ogcapi"` (OGC API Features):
     - `/collections` raz (brak kolekcji = `DownloadError`); `bbox` w CRS84
       (lon,lat), `limit` = `page_size`, kolejne strony tylko po linku
       `rel="next"` z tego samego hosta;
     - N = `numberMatched` pierwszej strony (bez osobnego zapytania
       o liczbe: kazde `items` PRNG trwa 78-95 s); kontrola
       `numberReturned` i `numberMatched` kazdej strony, GeoJSON;
     - `FeatureLayer.source` = id kolekcji, `id_field` = `id`;
     - `FeatureBBoxParams.timeout`: limit odczytu wolnej uslugi.
   - `FeatureBBoxParams` i `AtomFilesParams` dostaja `choice:
     tuple[tuple[str, str], ...] = ()` (np. `(("network", "gravity"),)`,
     `(("format", "GPKG"),)`): wybor kanalu, gdy siec albo format ma osobna
     usluge lub feed. Kanaly jednego rodzaju dziela capability i maja te
     same uklady.
   - `FeatureBBoxParams` dostaje `selection_key: str = "level"`: nazwa
     flagi wybierajacej warstwy przy `selection="level"`. Ten sam `code`
     w kilku `FeatureLayer` = jeden wybor z kilku warstw (Bodove pole:
     `horizontal` = warstwy 18 i 20).
4. **Sygnal `index` w kolekcjach (E0, ADR-043 D4).** Etykieta wersji
   jednostki to pola rekordu `IndexSource.label_fields` laczone `_` (D29),
   zapisana jako wydanie (`label_source="edition"`).
   - `check_collection` porownuje etykiete biezacego rekordu z lokalna
     wersja przez `inspect_version`, bez pobierania pliku (pyta tylko
     indeks).
   - Kanal kolekcji ma sygnal `index` wtedy i tylko wtedy, gdy ma
     `IndexSource`. `year` produktu bez wariantow rocznych filtruje
     rekordy; bez niego brany jest najnowszy rekord jednostki.
   - Arkusz bez rekordu jest pomijany i wypisany w `UNIT_LIST`; zaden
     z rekordem = `NoCoverageError`.
5. **Segmenty `data/`** (ARCHITECTURE 3.3, regula 8: `content_segment`
   z planu C = prefiks `storage_subdir` + tokeny `[a-z0-9.-]` laczone `_`;
   wariant = inny segment).

   | Produkt | Plik standardowy pod `--output` | Sygnal |
   |---|---|---|
   | NMT 100 m | `nmt/pl_1992_100m/teryt/12.zip` | `metadata` |
   | Warstwice CZ | `contours/cz_zabaged_shp/CTES/96/CTES96.zip` (`_dgn`) | `http` |
   | Intensywnosc | `intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif` (`pl_2000`) | `index` |
   | True orto | arkusz `orto/pl_1992_true/N-34/50/A/c/3/2/3/N-34-50-A-c-3-2-3.tif`; wycinek `orto/pl_1992_true_0.05m/bbox/<wsp>.tif` (wzorzec wycinka orto D: `orto/pl_1992_<wariant>_<etykieta>`) | `index` / `none` |
   | Orto ukosna | `orto/pl_2000_oblique/7/125/11/08/7.125.11.08_n.tif` (`_e`, `_s`, `_w`) | `index` |
   | Mesh 3D | `models3d/pl_mesh/s7/74238_55474.zip` (strefa z `uklad_xy`) | `index` |
   | Drzewa 3D | `models3d/pl_trees_lod1_2023/teryt/1261.zip` | `none` |
   | Wizualizacje BDOT10k | `maps/pl_bdot10k_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif` (`_pdf`, inne skale) | `index` |
   | BDOO | `landcover/pl_bdoo_2023/teryt/12.zip` (`_<klasy>` przy `--layers`, jak C) | `none` |
   | PRG adresy | `boundaries/pl_prg_addresses/bbox/<wsp>.gpkg`; `boundaries/pl_prg_addresses_shp/teryt/1261.zip`; `boundaries/pl_prg_addresses_<shp\|gml>/country/pl.zip` | `none` |
   | PRG specjalne | `boundaries/pl_prg_special/bbox/<wsp>.gpkg`; `boundaries/pl_prg_special_<shp\|gml>/country/pl.zip` | `none` |
   | PRNG RP | `names/pl_prng/bbox/<wsp>.gpkg`; `names/pl_prng_<gml\|shp\|xlsx>/country/pl-miejscowosci.zip`, `.../pl-obiekty-fizjograficzne.zip` | `none` |
   | PRNG swiat | `names/pl_prng_world/bbox/<wsp>.gpkg`; `names/pl_prng_world_<fmt>/country/pl-swiat.zip` | `none` |
   | Osnowy PL | `geodesy/pl_control_<siec>/bbox/<wsp>.gpkg`; `geodesy/pl_control_<horizontal\|vertical>_package/teryt/1261.zip`; `geodesy/pl_control_archive-1942/M-34/64/M-34-64.zip` | `none` |
   | RCN | `cadastre/pl_rcn/teryt/1261.gpkg` (woj.: `teryt/12.gpkg`) | `none` |
   | PL-geoid2021 | `geodesy/pl_geoid2021_evrf2007/country/pl.txt` | `none` |
   | Data50/250 | `landcover/cz_data50/bbox/<wsp>.gpkg`; `landcover/cz_data50_shp_<5514\|3045>/country/cz.zip` | `none` / `metadata` |
   | Mapa katastralna CZ | `cadastre/cz_km_<shp\|dxf\|dgn\|vfk>/ku/623164.zip` | `http` |
   | Geonames | `names/cz_geonames/bbox/<wsp>.gpkg`; `names/cz_geonames_<gpkg\|fgdb>_<5514\|3045>/country/cz.zip` | `none` / `metadata` |
   | ZTM | `maps/cz_ztm_10000_sjtsk_tiff/0301-B-01.zip` (PDF: `.pdf`) | `http` |
   | QGZU | `geodesy/cz_qgzu2013/country/cz.zip` | `metadata` |
   | Bodove pole | `geodesy/cz_control_<siec>/bbox/<wsp>.gpkg` | `none` |
   | Geomorfologia | `boundaries/cz_geomorphology_<poziom>/bbox/<wsp>.gpkg` | `none` |

   Wynik `feature_bbox` to jeden GPKG w ukladzie natywnym uslugi. Dla OGC
   API GUGiK uklad natywny to CRS84: uslugi oferuja na wyjsciu tylko CRS84.
   Paczki wieloplikowe zostaja ZIP-ami (OBJ+MTL+JPG, SHP+SHX+DBF+PRJ,
   TIFF+TFW, GML per klasa). Rozpakowywany jest tylko RCN (jeden GPKG, jak
   EGiB w C). Odstepstwo od specu 7: wycinek true orto ma etykiete
   rozdzielczosci w segmencie (`orto/pl_1992_true_0.05m`, nie
   `orto/pl_1992_true`), bo wycinek ma kilka rozdzielczosci, a regula 8
   rozdziela warianty; tak samo robi wycinek orto w planie D.
6. **Duze pliki i pliki krajowe (K7, K9).** Plik krajowy pobiera sie tylko
   z jawnym `--whole-country` i po `Notice` `WHOLE_COUNTRY_SIZE` (plan C)
   z rozmiarem z `HEAD`: PRG adresy, PRG specjalne, PRNG, Geonames,
   Data50/250, quasi-geoidy. Obszar zawsze idzie kanalem obszarowym
   (`feature_bbox`) albo jednostkami, nigdy plikiem krajowym. Przed `GET`
   kazdego pliku jednostki kolekcji jest `HEAD`; plik ponad 100 MiB (drzewa
   3,4-8,6 GB, archiwum osnow 1942 ok. 1 GB, RCN wojewodztwa) dostaje
   w chwili swojego pobrania `Notice` `DOWNLOAD_SIZE` (E0,
   `kartograf/notices.py`) z URL i rozmiarem; liste jednostek podaje
   wczesniej `UNIT_LIST`. Arkusze obrazow `download_data` (true orto
   i orto ukosna ok. 0,3 GB) emituje ten sam kod w E1 (K9).
7. **Czego plan E swiadomie nie robi** (zapis w ADR-043):
   - Narzedzia transformacji wysokosci z quasi-geoida. Zaden produkt
     Kartografa nie wymaga przejscia z wysokosci elipsoidalnych na normalne:
     dane PL i CZ sa w wysokosciach normalnych, a ETRS89 CZ ma EVRF2007
     natywnie (plan B). PROJ ma juz oficjalna siatke GUGiK
     `pl_gugik_geoid2021-PL-EVRF2007-NH.tif` (raport E, wiersz 15).
     Kartograf pobiera oryginalne modele PL i CZ jako dane i nie stosuje
     ich do zadnych innych danych.
   - Kanalu REST warstwic CZ. Arkusze SM5 daja pliki 1:1 z sygnalem `http`
     i pokrywaja kazdy obszar (D4).
   - GeoParquet RCN (tylko wojewodztwa i kraj). Ten sam zakres co GPKG,
     ktory jest tez powiatowy; tak samo EGiB w planie C.
   - NMT 100 m i warstwic w `elevation availability`. Raport dotyczy
     kompletu arkuszy ze skorowidza (K4); 100 m to 16 plikow
     wojewodzkich jednego wydania.
   - Pliku krajowego BDOO (`bdoo/<rok>/` go nie zawiera; kraj = 16
     wojewodztw z `--bbox` obejmujacym kraj).
   - Formatu VKM (P2).

## Fakty o obecnym kodzie (zweryfikowane 2026-10-15 na `1b8e358`)

- Grupy CLI: `kartograf/cli/groups/__init__.py:23` `register_groups`,
  `:30` `add_group`, `:41` `add_list_sources` (kolumna WYBOR z `choice`).
  `elevation.py:27` `PRODUCTS`, `:30` `_source_choice`. `imagery.py:20`
  `PRODUCTS = ("orto",)`. `landcover.py:26` wybor `--source`; `:75`
  `--format` z `choices=["GPKG", "SHP"]`. Wspolne flagi: `kartograf/cli/_args.py`
  (`add_update_flags`, `add_area_flags` z `--sheet`/`--bbox`/`--geometry`/
  `--layer`, `--bbox-crs`, `add_quiet`).
- API: `kartograf/download/data.py:245` `download_data`, `:321` `check_data`
  (parametry bez `format`/`direction`). Walidacja w `kartograf/download/options.py`:
  `SHEET_SYSTEM_CHOICES` `:50`, `SCALE_2000_CHOICES` `:54` (format `1:2000`),
  `product_choices` `:30`.
- Magazyn: `kartograf/download/fetch.py` `FileSlot` `:85`, `use_local` `:238`,
  `store_file` `:286`, `fetch_version` `:344` (sygnal `metadata` wymaga
  `edition`), `inspect_version` `:399`; `kartograf/sources/edition.py`
  `Edition`, `edition_label`. Tory planu: `kartograf/download/plan.py:27`
  `Track`.
- Deskryptory: `kartograf/sources/descriptor.py:18` `TransportKind`
  (`WCS`, `WMS_SHEET_INDEX`, `WFS`, `DIRECT_FILES`, `ARCGIS_IMAGE`,
  `ARCGIS_QUERY`, `OGC_API_FEATURES` - zadnego nowego), `:35`
  `SignalKind`, `:48` `AccessChannel` (bez `params` do planu C);
  `kartograf/sources/registry.py:44` `_GUGIK_LICENSE`, `:68` `_CUZK_LICENSE`,
  `:76` `_SOURCES`, `:363` `_COUNTRIES`, `:409` `sources_for`.
- Skorowidz WMS: `kartograf/providers/pl/skorowidz.py:169`
  `parse_skorowidz_records` czyta kazde `X.push({...})`, takze
  `skor_orto_ukosne` i `skor_modele_siatkowe_3D` (raport E, wiersze 2-5);
  `:436` `SkorowidzLayersMixin`; `kartograf/providers/pl/gugik_orto.py:43`
  `GugikOrtoProvider` (orto na WMS - wzorzec E1).
- Godla: `kartograf/core/sheet_parser.py` `PATTERNS` (do 7 czlonow PL-1992),
  `:955` `find_sheets_for_bbox(bbox, target_scale, sheet_system)`. Etykiety
  skal Kartografa sa o poziom drobniejsze niz nomenklatura GUGiK. Godlo
  7-czlonowe ma etykiete `1:10000`, a GUGiK nazywa je 1:5000; siatka 1-144
  ma etykiete `1:200000` (docstring klasy, backlog A1-8). 8-czlonowe
  `N-34-50-A-c-3-2-3` daje dzis `ParseError`.
- CZ: `kartograf/providers/cuzk/client.py:53` `CuzkClient.query` (zbiera
  strony do listy - tylko male wyniki: kody KU, numery arkuszy), `:109`
  `fetch_file`; `kartograf/providers/cuzk/sheets.py:72` `SheetIndex`
  (`sm5_sheets_for_bbox` `:114`, `tm33_tiles_for_bbox` `:126`);
  `kartograf/download/cz_sheets.py` (tor arkuszy SM5, `_signal` `:118`).
- PL jednostki: `kartograf/providers/pl/prg.py:294` `discover_teryts_for_bbox`
  (powiaty; wojewodztwo = dwie pierwsze cyfry), `:234` `fetch_land_mask`.
- Pokrycie terenu: `kartograf/landcover/manager.py:77` `PROVIDERS`,
  `:86` opcje per zrodlo, `:216` `LandCoverManager`, `:375` `download`,
  `:480` `check`.
- Notices: `kartograf/notices.py:7-27` kody (bez kodu rozmiaru pobrania).
- Transformacje: `kartograf/transform/crs.py` `KNOWN_PATHS`, `REMEDIES` -
  bez zmian w planie E.
- Zgodnosc CLI = API: `tests/parity.py` (`run_both`, `assert_same_store`),
  `tests/test_parity.py`, `tests/test_cli_translation.py`.

## Mapa plikow

| Plik | Wlasciciel | Zmiana |
|---|---|---|
| `kartograf/sources/descriptor.py` (parametry C/D) | E0 | `SheetGrid`, `IndexSource`; `UnitPackageParams.unit` += `sheet`/`tile`/`ku`, `themes`, `index`, `ku_layer`; `PackageVariant.url_template: str \| None`, `sheet_grid`, `index_layer`, `file_kind`; `FeatureBBoxParams.protocol` += `ogcapi`, `choice`, `selection_key`, `timeout`; `AtomFilesParams.choice` |
| `kartograf/transport/unit_package.py`, `kartograf/transport/feature_bbox.py`, `kartograf/download/collections.py`, `kartograf/download/storage.py` (`unit_slot`) | E0 | odkrywanie jednostek `sheet`/`tile`/`ku`, tematy krajowe, tokeny `{sheet}`/`{ku}`/`{theme}`, OGC API Features, sygnal `index`, parametry `ku`/`format`/`scale`/`sheet_system`/`network`, sloty `<hierarchia godla>/<godlo>`, `<MAPNOM>` (CUZK, plasko), `ku/<kod>`, `<strefa>/<kafel>`, `country/pl-<temat>` |
| `kartograf/providers/cuzk/sheets.py`, `kartograf/providers/cuzk/ruian.py` (NOWY) | E0 | `SheetIndex.sheets_for_bbox(layer, bbox)` i `sheet(layer, mapnom, crs=)` dla dowolnej warstwy `KladyMapovychListu` (SM5 i TM33 bez zmian zachowania); `cadastral_areas_for_bbox` (KU z RUIAN) |
| `kartograf/transport/index_records.py` (NOWY) | E0 | `IndexRecord`, `gfi_records`/`records_from_gfi` (parser `map_links`: tabela linkow wizualizacji BDOT10k), `wfs_records`/`records_from_wfs` (`WfsIndex.features`) |
| `kartograf/notices.py` | E0 | `DOWNLOAD_SIZE` |
| `kartograf/core/sheet_parser.py` | E1 | poziom 8-czlonowy PL-1992 |
| `kartograf/sources/descriptor.py` (`AtomFilesParams`), `kartograf/transport/atom.py` (z D) | E1 | grupa selektora `woj`, pole `force_https` |
| `kartograf/download/{data,options,cz_sheets}.py`, `kartograf/providers/pl/gugik_orto.py` (albo nowy modul obok), `kartograf/cli/groups/{elevation,imagery}.py` | E1 | NMT 100 m, warstwice, intensywnosc, true orto, orto ukosna |
| `kartograf/cli/groups/{names,maps}.py` (NOWE) | E2 | grupy `names`, `maps` |
| `kartograf/cli/groups/{boundaries,cadastre}.py` (z C) | E3 | nowe produkty grup |
| `kartograf/landcover/manager.py` i moduly zrodel C/D w `landcover` | E4 | BDOO, Data50, Data250 |
| `kartograf/cli/groups/models3d.py` (z C), `kartograf/cli/groups/geodesy.py` (NOWY) | E5 | mesh, drzewa, grupa `geodesy` |
| `kartograf/sources/registry.py` | E1-E5 | **plik wspolny**: kazdy pakiet dopisuje jeden ciagly blok deskryptorow z komentarzem `# plan E - Ex`, PL po ostatnim deskryptorze PL, CZ po ostatnim CZ; bez zmian w cudzych blokach; konflikt scalania = oba bloki |
| `kartograf/project/commands.py`, `tests/test_project_*.py` | E1-E5 (warunkowo) | **plik wspolny**: pozycje i opcje wlasnych komend |
| `docs/DECISIONS.md` | E0 (ADR-043), EZ (errata z E2E) | ADR-043 |
| `docs/{USAGE,ARCHITECTURE,SCOPE,PRD,CHANGELOG}.md`, `docs/research/2026-10-xx-plan-e-e2e/raport.md` | EZ | dokumentacja i raport E2E |
| `tests/fixtures/{pl,cz}/<produkt>/real_2026_10_xx/` | pakiet produktu | fixtury z prawdziwych odpowiedzi |

---

### Task E0: Wspolny kontrakt kolekcji planu E

**Stan:** wykonany 2026-10-16 (galaz `feat/plan-e0-engines`, commit
`feat(collections): jednostki arkuszy, kafli i KU oraz sygnal index (plan E,
E0)`; ADR-043). Zaden produkt planu E nie ma jeszcze deskryptora, wiec
CLI = API end-to-end sprawdzaja dopiero E1-E5; silniki sa sprawdzone
testami na prawdziwych fixturach i na zywo (`fetch_features` +
`write_gpkg` na OGC API PRNG: 9 obiektow w CRS84, 190,8 s).

**Zaleznosci:** A, C i D na `develop`; numer ADR od koordynatora (043).

**Files:**
- Modify: `kartograf/sources/descriptor.py` (parametry C/D),
  `kartograf/transport/unit_package.py`, `kartograf/transport/feature_bbox.py`,
  `kartograf/transform/gpkg.py`, `kartograf/download/collections.py`,
  `kartograf/download/storage.py` (`unit_slot`), `kartograf/download/fetch.py`,
  `kartograf/download/arguments.py` (`require_str`),
  `kartograf/providers/cuzk/sheets.py`, `kartograf/providers/cuzk/client.py`,
  `kartograf/providers/pl/skorowidz_wfs.py` (nazwy lokalne), `kartograf/notices.py`,
  `tests/test_unit_package.py`, `tests/test_feature_bbox.py`,
  `tests/test_gpkg_writer.py`, `tests/test_sources_registry.py` (niezmienniki
  rejestru), `docs/DECISIONS.md`
- Create: `kartograf/transport/index_records.py`, `kartograf/providers/cuzk/ruian.py`,
  `tests/test_index_records.py`, `tests/test_collections_units.py`,
  `tests/test_cuzk_units.py`, fixtury `tests/fixtures/pl/e0/real_2026_10_16/`,
  `tests/fixtures/pl/index_records/`, `tests/fixtures/cuzk/real_2026_10_16/`,
  strony OGC API PRNG w `tests/fixtures/pl/feature_bbox/`

**Interfaces** (stan kodu E0; E1-E5 uzywaja tych nazw):
```python
# kartograf/transport/index_records.py
@dataclass(frozen=True)
class IndexRecord:
    unit: str                    # godlo kanoniczne (GFI) / modul kafla (WFS)
    urls: Mapping[str, str]      # format -> URL ("TIFF", "PDF"); {"": url} dla jednego URL
    label: str                   # etykieta wersji (D29) z label_fields laczonych "_"
    year: int | None             # rok danych - filtr year (najnowszy rekord bez niego)
    zone: str | None             # katalog slotu kafla z zone_field ("PL-2000:S7" -> "s7")
    raw: Mapping[str, str]       # pola zrodla do extra.source.record
def gfi_records(session, source: IndexSource, layer: str, sheet: str, *, timeout: float) -> list[IndexRecord]
def records_from_gfi(content: bytes, *, source: IndexSource, layer: str, context: str) -> list[IndexRecord]
def wfs_records(session_factory, source: IndexSource, layer: str, bbox: BBox, *, timeout: float) -> list[IndexRecord]
def records_from_wfs(features: Iterable[ET.Element], *, source: IndexSource) -> list[IndexRecord]

# kartograf/providers/cuzk/ruian.py
def cadastral_areas_for_bbox(client: CuzkClient, layer_url: str, bbox: BBox) -> list[CadastralArea]  # (code, name)

# kartograf/sources/descriptor.py (E0)
FileKind = Literal["zip", "tiff", "pdf", "txt"]
PACKAGE_URL_TOKENS = ("teryt", "woj", "sheet", "ku", "theme")
@dataclass(frozen=True)
class SheetGrid:                 # jednostki "sheet" obszaru (cecha wariantu)
    system: Literal["1992", "cuzk"]
    parts: int | None = None     # PL-1992: liczba czlonow godla serii (seria 1:10000 GUGiK = 6, 1:100000 = 3)
    layer: int | None = None     # CUZK: warstwa KladyMapovychListu (ZTM10 S-JTSK = 2, ETRS89 = 14)
    crs: str | None = None       # CUZK: uklad natywny warstwy (S-JTSK EPSG:5514, ETRS89 EPSG:3045)
@dataclass(frozen=True)
class IndexSource:               # rekordy z URL dla jednostek "sheet"/"tile"
    kind: Literal["wms_gfi", "wfs"]
    endpoint: str
    parser: Literal["map_links"] | None  # tylko wms_gfi
    unit_field: str              # "godlo" | "modul"
    url_field: str | None        # "URL_do_pobrania"; None: map_links (link wg formatu)
    label_fields: tuple[str, ...]  # ("stan_bazy",) | ("Aktualnosc", "Numer_zgloszenia_pracy")
    year_field: str | None = None  # "akt_rok"
    zone_field: str | None = None  # "uklad_xy"
# UnitPackageParams: unit += "sheet" | "tile" | "ku"; index: IndexSource | None = None;
#   themes: tuple[str, ...] = () (jednostki country/<kraj>-<temat malymi literami, "_" -> "-">);
#   ku_layer: str | None = None (pelny adres warstwy RUIAN .../RUIAN/MapServer/7)
# PackageVariant: url_template: str | None (None = URL z rekordu indeksu, link wg choice "format");
#   sheet_grid: SheetGrid | None = None i index_layer: str | None = None (warstwa WMS / typ WFS
#   indeksu wariantu); choice moze miec klucze format/scale/sheet_system/network;
#   file_kind: FileKind = "zip" - plik bez ZIP sprawdzany po zawartosci (magia TIFF, "%PDF-",
#   tekst bez NUL, ktorego pierwsza linia nie jest znacznikiem)
# FeatureBBoxParams: protocol += "ogcapi"; choice: tuple[tuple[str, str], ...] = ();
#   selection_key: str = "level"; timeout: int | None = None
# AtomFilesParams: choice: tuple[tuple[str, str], ...] = ()
# kartograf/notices.py: DOWNLOAD_SIZE = "download_size"
```

- [x] **Step 1: Fixtury (live, swiadomie).** Nagraj przyciete prawdziwe odpowiedzi:
  - RUIAN `ags/RUIAN/MapServer/7/query` (bbox z 2-3 KU, `returnGeometry=false`,
    `outFields=kod,nazev`);
  - `KladyMapovychListu/MapServer/2/query` (ZTM10 S-JTSK, bbox z 2 arkuszami)
    i `.../14/query` (ZTM10 ETRS89);
  - WFS mesh `gugik:SkorowidzModeleSiatkowe3D` z `COUNT=2`: dwie strony
    przez `next` (raport E, wiersz 5);
  - GFI `Mapy10k` w srodku `M-34-064-D-d-1` (tabela z PDF i GeoTIFF oraz
    "Stan bazy") i GFI poza Polska (pusty szablon);
  - (przeniesione do E1: GFI `SkorowidzeOI` nie jest indeksem kolekcji,
    intensywnosc idzie torem providera orto);
  - dwie strony OGC API `NazwaGeograficznaRP` (bbox Krakowa, `limit=5`)
    i `/collections` PRNG;
  - `GetCapabilities` i strona WFS `OsnowaGrawimetryczna` (wybor kanalu
    po `network`).
- [x] **Step 2: Test RED** (`tests/test_unit_package.py`, `tests/test_feature_bbox.py`,
  `tests/test_collections_units.py`, `tests/test_cuzk_units.py`,
  `tests/test_index_records.py`):
  - `test_pl_sheet_series_by_parts`: bbox Krakowa. Seria 1:10000 GUGiK daje
    godla 6-czlonowe, seria 1:100000 godla 3-czlonowe (`M-34-64`). Zbior
    godel rowna sie wynikowi `find_sheets_for_bbox` z etykieta Kartografa
    o poziom drobniejsza. Test pilnuje mapowania serii na liczbe czlonow,
    nie tekstu etykiety.
  - `test_sheet_area_meaning_kept_for_c_products`: `sheet=` dla produktu C
    (np. EGiB) dalej rozwija sie na powiaty zasiegu godla; jednostka
    arkusza powstaje tylko w kanale z `unit="sheet"`.
  - `test_ogcapi_pages_and_crs84`: dwie strony PRNG po `rel="next"` daja
    jeden GPKG bez duplikatu `id`. `bbox` w zapytaniu jest w CRS84
    lon,lat. `next` do obcego hosta albo `numberReturned` niezgodny
    z liczba obiektow = `DownloadError`.
  - `test_feature_channel_by_choice`: `network="gravity"` wybiera kanal
    uslugi grawimetrycznej. `selection_key="network"` z dwiema warstwami
    tego samego `code` pyta obie.
  - `test_cuzk_layer_sheets`: z fixtury powstaje lista `MAPNOM`;
    `exceededTransferLimit` prowadzi do kolejnej strony; pusty, poprawny
    wynik = brak jednostek, bez bledu.
  - `test_ku_units_from_ruian`: kody z fixtury. Kod spoza `^[0-9]{6}$`
    = `ValidationError` przed siecia.
  - `test_tile_units_from_wfs_pages`: dwie strony daja trzy unikalne kafle.
    `numberReturned` niezgodny z liczba obiektow, `next` do obcego hosta
    i HTML przy 200 = `DownloadError` (z dopiskiem "wynik bylby niepelny").
  - `test_map_links_record`: tabela GFI daje rekord z `urls` `{"PDF", "TIFF"}`
    i etykieta `2026-05-27`. Pusty szablon = brak rekordu; HTML bez
    szablonu = `DownloadError`.
  - `test_index_signal_check_downloads_nothing`: atrapa sesji odrzuca kazdy
    URL pliku. `check_collection` daje `current` przy tej samej etykiecie
    rekordu i `newer` przy innej.
  - `test_new_selection_validated_before_network`: `format`, `scale`,
    `sheet_system`, `network` lub `ku` spoza wartosci deskryptora albo
    niedozwolone dla kraju = `ValidationError` z lista; zadnego zapytania.
  - `test_size_notice_before_get`: `HEAD` z `Content-Length` > 100 MiB daje
    `Notice` `DOWNLOAD_SIZE` przed pierwszym `GET`; `check_collection`
    nie robi `GET`.
  - `test_non_zip_files_checked_by_kind`: wariant `file_kind="tiff"`,
    `"pdf"` albo `"txt"` przyjmuje plik z poprawna magia albo naglowkiem.
    HTML przy 200 i plik obcego rodzaju = `DownloadError`, bez wersji.
- [x] **Step 3: Implementacja.**
  - Rozszerz parametry kanalu, odkrywanie jednostek i adresowanie
    w `unit_package` (sekcja "Decyzje" pkt 3-4).
  - Dodaj `protocol="ogcapi"` w `feature_bbox`: zapis stron jak dla WFS
    i ArcGIS w C, GeoJSON przez `write_gpkg`.
  - Rekord indeksu ustala etykiete wersji i `extra.source` (endpoint,
    warstwa/typ, pola rekordu).
  - `SheetIndex` dostaje zapytanie o dowolna warstwe; SM5 i TM33 korzystaja
    z niego bez zmiany wynikow (testy planu B zostaja zielone).
  - Parametry `ku`, `format`, `scale`, `sheet_system` i `network`
    przechodza przez `download_collection`/`check_collection`/
    `validate_collection_request` do `select_variant` i wyboru kanalu
    `feature_bbox`. Dozwolone wartosci czytane z deskryptora, bez list
    w kodzie (K1).
- [x] **Step 4: ADR-043** w `docs/DECISIONS.md` (CRLF, wiersz indeksu
  i sekcja; D1-D9 kod E0, D10 decyzje produktowe E1-E5):
  - kontekst: 24 produkty E na silnikach C/D;
  - decyzja: nowe grupy `names`, `maps`, `geodesy`; nazwy produktow;
    jednostki `sheet`/`tile`/`ku`; adres z rekordu indeksu; sygnal `index`
    w kolekcjach; `--direction` jako filtr; 8-czlonowe godla; P1 i P2 wg
    decyzji uzytkownika;
  - odrzucone: provider per produkt; WMS jako dane; plik krajowy dla
    obszaru; narzedzie transformacji z quasi-geoida (pkt 7).
  Relacje: czesciowo zastepuje ADR-042 (D1: unikalna capability),
  uzupelnia ADR-039, ADR-041 i ADR-042.
- [x] **Step 5: Testy niezmiennikow rejestru**
  (`tests/test_sources_registry.py`, chronia deskryptory E1-E5): wariant
  bez szablonu URL ma `IndexSource`; tokeny szablonu pochodza z jednostki
  kanalu (`{theme}` w kazdym szablonie produktu z tematami); kanal `sheet`
  ma siatke w kazdym wariancie, `tile` indeks WFS, `ku` warstwe RUIAN,
  kanal z indeksem `index_layer` w kazdym wariancie; sygnal `index` wtedy
  i tylko wtedy, gdy kanal ma indeks; kanal z capability wspolna z innym
  ma te same uklady co pierwszy kanal tej capability (sidecar).
- [x] **Step 6: Brama i commit** - `feat(collections): jednostki arkuszy, kafli i KU oraz sygnal index (plan E, E0)`
  oraz `docs(plan-e): ADR-043, korekta planu E po E0 i niezmienniki rejestru`.

### Task E1: `elevation` i `imagery` - NMT 100 m, warstwice CZ, intensywnosc, true orto, orto ukosna

**Zaleznosci:** E0, A, B, D.

**Stan (2026-10-16, galaz `feat/plan-e1`):** kroki 1-3 wykonane (fixtury
w `tests/fixtures/pl/{nmt_100m,intensity,orto_true,orto_oblique}/`
i `tests/fixtures/cz/contours/` z README; godla 8-czlonowe; NMT 100 m,
commit `85b53af`). Kroki 4-9 otwarte. Fakty z kodu dla kroku 4 (rozpoznane
2026-10-16, bez implementacji):
- `DownloadManager._download_planned` filtruje pozycje planu tylko po
  `unit`: przy czterech managerach orto ukosnej musi zawezic je do nazwy
  pliku managera (`updates._where`/`_items`), inaczej pozycje innych
  kierunkow staja sie `stale`;
- `campaigns.verify_record_url` bierze ostatni czlon `_` nazwy z URL:
  `..._7.125.11.08_N.tif` nie przejdzie B4 bez zdjecia przyrostka kierunku;
- `area.pl_only_flags` zaweza `--country auto` do PL tylko dla
  `nmt/nmpt/orto` bez zrodla CZ - nowe produkty obrazow wymagaja
  uogolnienia (kazdy produkt bez deskryptora CZ);
- `options.pl_target_scale` daje dla PL-1992 `1:10000`; true orto potrzebuje
  `series_scale(8)` z deskryptora (tez tekst `--scale` w `pl_option_error`);
- `HEAD` przed `GET` tylko dla providerow obrazow (listy arkuszy NMT
  placilyby ok. 0,5 s na arkusz); manager emituje przez
  `NoticeSink(self._on_notice)`;
- warstwy skorowidzy intensywnosci, true orto i orto ukosnej sa stale -
  lista w deskryptorze omija `GetCapabilities` (bez fixtur tych uslug);
- funkcje wycinka (`gugik_orto.wcs_cutout_channels`, `orto_cutout._prepare`,
  `_write_sidecar`) sa zwiazane z `ORTO_KEY`: uogolnic po kluczu
  deskryptora; jeden kanal WCS (true orto) = bez tokenu `coverage`
  w segmencie (`orto/pl_1992_true_<res>`) i `--coverage` = `Error:`.

Fakty z nagrania i kodu z krokow 1-2 (korekta planu):
- Godla 8-czlonowe zamykaja ograniczenie ADR-041: `DownloadManager`
  rozwija tylko godla grubsze od `BaseProvider.sheet_scale` (NMT/NMPT/orto
  `1:10000`; true orto ustawi `1:5000`), godlo 8-czlonowe jest arkuszem
  (siatki NMT 1 m 2019 per cwiartka, `--sheet`); `ASCII-NMT 10m` EVRF2007
  dopisane do rejestru archiwow (ZIP: punkty co 0,5 m, skorowidz deklaruje
  10 m). `_SERIES_LABEL` z kolekcji zastapione `series_scale(czlony)`
  w `core/sheet_parser.py`.
- NMT 100 m: wpis ATOM ma `<id>` = URL feedu zbioru z
  `spatial_dataset_identifier_code=NMT100_<woj>`; linki feedu uslugi i zbioru
  sa `http://`, odpowiadaja przez `https` (feedy 0,1-0,4 s, plik 7,7 s);
  etykieta `<updated>` wpisu zbioru 2019-05-14. **Rozstrzygniete przez
  koordynatora 2026-10-16:** `--product nmt --resolution 100m` bez
  `--format` (jeden format zrodla = wariant 100 m); `--format XYZ`
  dozwolone jako jedyna wartosc dla 100 m; pozostale archiwa bez zmian
  (`source_file` z indeksem WFS). W kodzie: `ProductVariant.source_file`
  = format archiwum ORAZ `index_ref` (wariant 100 m z `format="XYZ"`,
  `index_ref=None` jest formatem produktu). `ProductVariant.vertical_crs`
  przyjmuje `None` (+ `vertical_note` do `extra.vertical_crs_note`). Tor:
  `collections.atom_area_request` (czesc z kanalem ATOM, grupa `woj`) +
  `run_request`/`plan_request` (tor `collection`); `UnitJob.atom_key`,
  `_fetch_atom`: `WHOLE_COUNTRY_SIZE` tylko dla pliku krajowego,
  `DOWNLOAD_SIZE` powyzej 100 MiB.
- Intensywnosc: jedna warstwa `SkorowidzeOI` z rekordami PL-1992 (modul
  1:5000) i PL-2000 (1:2000) w tym samym punkcie; bez
  `calyArkuszWypelnionyTrescia` i bez `kolor`. True orto: warstwa
  `Skorowidze`, godla 8-czlonowe (cwiartki 1 NW, 2 NE, 3 SW, 4 SE), bez
  `dt_pzgik`. WCS `True_Orthoimagery` (0,05 m) oddaje siatke zapytania
  (jak Standard), poza miastami piksele 0,0,0.
- Orto ukosna: rekordy maja `kierunek` N/E/S/W (jedna warstwa na kierunek),
  URL `..._<godlo>_<N|E|S|W>.tif` (B4 `verify_record_url` musi zdjac
  przyrostek kierunku) i rozne skale PL-2000 (Krakow 1:2000, Gdansk
  `6.224.25.03.1` 1:1000) - `--scale` dla obszaru zostaje wymagane, tylko
  `--sheet-system` ma jedna wartosc (2000). Cztery pliki arkusza = cztery
  managery (provider na kierunek, przyrostek nazwy `_n` w `FileStorage`);
  `_download_planned` musi zawezic pozycje planu do segmentu i nazwy pliku
  managera (inaczej pozycje innych kierunkow staja sie `stale`).
- `HEAD` arkuszy obrazow (0,5-1,6 s): intensywnosc 85 MB, true orto
  297 MB, ukosna 274-302 MB (`DOWNLOAD_SIZE` > 100 MiB).
- Warstwice CZ: SHP 8 plikow, DGN 3 pliki, `ETag` i `Last-Modified`; slot
  hierarchiczny `contours/cz_zabaged_<fmt>/CTES/96/CTES96.zip` (jak arkusze
  SM5 planu B, nie plaski `mapnom` kolekcji E0); produkt elevation nie moze
  stac sie produktem kolekcji (`_is_collection`).

**Files:**
- Modify: `kartograf/sources/registry.py` (blok E1), `kartograf/core/sheet_parser.py`,
  `kartograf/sources/descriptor.py` (`AtomFilesParams`), `kartograf/transport/atom.py` (z D),
  `kartograf/download/{data,options,cz_sheets}.py`, `kartograf/download/orto_cutout.py` (z D),
  `kartograf/providers/pl/gugik_orto.py` (albo nowy modul obok, patrz Step 4),
  `kartograf/cli/groups/{elevation,imagery}.py`, `tests/test_sheet_parser.py`,
  `tests/test_atom.py` (z D), `tests/test_parity.py`
- Create: `tests/test_nmt_100m.py`, `tests/test_cz_contours.py`,
  `tests/test_imagery_products.py`, fixtury `tests/fixtures/pl/{nmt_100m,intensity,orto_true,orto_oblique}/`
  i `tests/fixtures/cz/contours/`

**Interfaces:**
```python
download_data(..., format: str | None = None,                          # contours: "SHP" | "DGN"
              direction: str | Sequence[str] | None = None) -> DataReport  # oblique-orto: subset of n,e,s,w; None = all
# rejestr wariantow (A): ProductVariant(source="pl.gugik.nmt_100m", product="nmt", country="PL",
#   resolution_m=Decimal("100"), vertical_crs=None (P1), format="XYZ", systems=("1992",),
#   channel=TransportKind.DIRECT_FILES, index_ref=None, vertical_note=...)  # source_file=False:
#   format produktu dla --resolution 100m; --format XYZ dozwolone (jedyna wartosc)
# AtomFilesParams (D) + E1: service_feed=".../ATOM/httpauth/atom/GUGIK_NMT100",
#   entry_pattern=r"spatial_dataset_identifier_code=NMT100_(?P<woj>[0-9]{2})" (id wpisu GUGiK to URL),
#   crs=() (jeden plik), members=() (ZIP zostaje), force_https=True (nowe pole: linki GUGiK http -> https)
# WcsCutoutParams (D) dla true orto: variant="true", coverage_id="True_Orthoimagery",
#   native_step=Decimal("0.05"), resolutions=(0.05, 0.1, 0.25, 0.5, 1), max_native_pixels=4_000_000
```

- [x] **Step 1: Fixtury (live).** Zrodla (raport E, wiersze 1-4 i 16):
  - feed uslugi `GUGIK_NMT100` (16 wpisow, id `NMT100_<woj>` w
    `inspire_dls:spatial_dataset_identifier_code`) i feed zbioru `NMT100_12`
    (link `application/zip`, `length` 7619580, kategoria EPSG:2180);
  - `HEAD` pliku warstwic `CTES96` (SHP i DGN, `ETag`);
  - GFI `SkorowidzeOI` (2 loty arkusza PL-1992 i arkusz PL-2000);
  - GFI `TrueOrtho/Skorowidze` w Gdansku i pusty w Krakowie;
  - GFI czterech warstw orto ukosnej w Krakowie;
  - `DescribeCoverage` `True_Orthoimagery` (siatka 0,05 m).
- [x] **Step 2: Godla 8-czlonowe (test RED, potem implementacja).** W `tests/test_sheet_parser.py`:
  - `N-34-50-A-c-3-2-3` parsuje sie; obwiednia to cwiartka arkusza
    7-czlonowego `N-34-50-A-c-3-2` (numeracja 1-4 jak w poziomie
    wyzszym);
  - `find_sheets_for_bbox` zwraca godla 8-czlonowe dla nowego poziomu;
  - `get_parent()` daje arkusz 7-czlonowy.

  Etykieta poziomu w schemacie Kartografa: `1:5000` (GUGiK: 1:2500).
  Docstring klasy dostaje to zdanie; backlog A1-8 bez zmian.
- [x] **Step 3: Wariant 100 m (P1: uklad nieznany) i tor jednostek.** Test RED w `tests/test_nmt_100m.py`:
  - `test_area_selects_voivodeships`: bbox Krakowa daje tylko `12`;
    bbox na granicy wojewodztw daje dwa pliki; `--sheet` daje wojewodztwa
    przecinajace arkusz;
  - `test_edition_label_from_entry`: etykieta wersji `2019-05-14` z
    `<updated>` wpisu zbioru; `check_data` daje `current` bez `GET` pliku;
  - `test_https_for_gugik_atom`: link `http://mapy.geoportal.gov.pl/...`
    z feedu jest pobierany przez `https` tego samego hosta (zmierzone
    2026-10-15: feed i plik 200). Regula w parametrach kanalu, nie w
    kodzie produktu;
  - `test_100m_rejects_sheet_flags`: `--sheet-system`, `--scale`, flagi
    roku i lotow, `--full-sheet`, `--cutout`, `--horizontal-crs`,
    `--min-density` oraz `--country cz` = `Error:` z tekstem "NMT 100 m to
    pliki wojewodztw z ATOM - bez arkuszy, lotow i wycinka";
  - `test_zip_kept_with_txt`: ZIP z jednym TXT zostaje ZIP-em; sidecar
    ma `extra.source` (feed, id zbioru, URL, `length`), `extra.edition`,
    `extra.parent_request`, `vertical_crs: null` i adnotacje, ze GUGiK nie
    deklaruje ukladu wysokosci; segment `nmt/pl_1992_100m`.

  Implementacja:
  - wpis rejestru bez ukladu wysokosci (P1), bez drugiej listy rozdzielczosci;
  - wybor wpisu ATOM przez grupe `woj` w `AtomFilesParams`;
  - wojewodztwa obszaru z `discover_teryts_for_bbox` (dwie pierwsze cyfry);
  - pozycje planu na torze `collection` (bez nowego toru);
  - `--vertical-crs` dla 100 m = `Error:` (uklad nieznany, P1).
- [ ] **Step 4: Intensywnosc, true orto, orto ukosna.** Test RED w `tests/test_imagery_products.py`:
  - `test_intensity_campaigns_like_orto`: arkusz PL-1992 ma loty 2023
    i 2025; bez `--year` pobiera 2025, `--year 2023` pobiera 2023;
    `--all-campaigns` pobiera oba do `versions/`; plik ma 1 pasmo i piksel
    0,25 m; arkusz PL-2000 trafia do segmentu `pl_2000`;
  - `test_true_orto_sheets_and_size_notice`: bbox daje arkusze 8-czlonowe;
    przed `GET` jest `Notice` z rozmiarem (`HEAD` 296 853 152 B); punkt bez
    rekordow daje `NoCoverageError` z podpowiedzia, ze true orto obejmuje
    wybrane miasta;
  - `test_true_orto_cutout_native_grid`: `--cutout --horizontal-crs EPSG:2180
    --resolution 0.05m` pyta coverage `True_Orthoimagery` na siatce
    natywnej, w kawalkach do 4 Mpx natywnych (100 x 100 m; wzorzec
    `orto_cutout.py` z D). Wynik ma 3 pasma, EPSG:2180 i segment
    `orto/pl_1992_true_0.05m`. Etykiety spoza `WcsCutoutParams.resolutions`
    = `Error:` z lista. `--coverage` z `true-orto` = `Error:` "true orto ma
    jedna usluge - bez --coverage";
  - `test_oblique_directions_are_files`: arkusz `7.125.11.08` daje 4 pliki
    `_n`, `_e`, `_s`, `_w`; `--direction n,e` daje 2; `--direction x`
    = `Error:`; `--direction` z innym produktem = `Error:`;
  - `test_full_sheet_only_with_record_flag`: `--full-sheet` dla
    intensywnosci i true orto = `Error:` (rekordy bez
    `calyArkuszWypelnionyTrescia`). Dla orto ukosnej dziala jak dla
    NMT/NMPT.

  Implementacja:
  - Logike arkuszy z `GugikOrtoProvider` sparametryzuj danymi deskryptora:
    endpoint WMS, warstwy, pole rozdzielczosci i filtr kierunku.
  - Orto, intensywnosc, true orto i orto ukosna korzystaja z jednego kodu,
    bez kopii providera (zasada planu C). Testy orto bez zmian.
  - Wycinek true orto to drugi kanal `WCS` z `WcsCutoutParams` na torze
    `orto_cutout.py` planu D.
  - `Notice` `DOWNLOAD_SIZE` (kod z E0) dla arkuszy ponad 100 MiB (K9):
    E0 emituje go tylko w kolekcjach, `download_data` dostaje to w E1
    (`HEAD` przed `GET` arkusza, tekst jak w `collections._announce_size`).
- [ ] **Step 5: Warstwice CZ.** Test RED w `tests/test_cz_contours.py`:
  - `test_contours_sheet_zip_kept`: `--sheet CTES96 --format SHP` daje
    `contours/cz_zabaged_shp/CTES/96/CTES96.zip` (8 plikow, ZIP bez
    rozpakowania); `--format DGN` trafia do osobnego segmentu;
  - `test_contours_area_expands_to_sm5`: bbox w EPSG:5514 daje arkusze
    `sm5_sheets_for_bbox`; `--cutout` i `--resolution` = `Error:` z tekstem
    "warstwice to arkusze SM5 (wektor)";
  - `test_contours_http_signal`: drugi przebieg uzywa wersji lokalnej
    i porownuje `ETag`;
  - brak `--format` = `Error:` z lista `SHP, DGN`; `--vertical-crs` tylko
    `Bpv`, mozna pominac.

  Implementacja na torze arkuszy CZ planu B. Szablon
  `openzu/ZABAGED-vyskopis{,-DGN}/epsg-5514/{sm5}.zip` i lista formatow
  w deskryptorze; feed ATOM (16 301 wpisow) zostaje nieuzywany.
- [ ] **Step 6: CLI.**
  - `elevation`: `contours` w produktach grupy (lista w bibliotece, jak
    `ELEVATION_PRODUCTS` z planu manifestu); `--format`; teksty
    `--resolution` i `--vertical-crs` z rejestru;
  - `imagery`: produkty `intensity`, `true-orto`, `oblique-orto`;
    `--direction`; flagi lotow dla nowych produktow;
  - `list-sources` obu grup pokazuje nowe klucze z wyborami (np.
    `--product nmt --resolution 100m`);
  - parity (`tests/test_parity.py`): NMT 100 m, warstwice, orto ukosna
    `--direction n`.
- [ ] **Step 7: Manifest (warunkowo).**
  - Opcje `elevation download` dostaja `format`, a `imagery download`
    dostaje `direction`;
    `test_task_options_equal_parser_data_flags` zielony;
  - test zadania projektu z NMT 100 m (jednostka wojewodztwa).
- [ ] **Step 8: Live (swiadomie, `-o <katalog-danych>/kartograf/e2e/<data>-plan-e1/`).**
  - NMT 100 m woj. 12 (7,6 MB): drugi przebieg lokalny,
    `--check-updates` = aktualne;
  - warstwice CTES96 SHP i DGN;
  - intensywnosc `M-34-64-D-d-1-4` (85 MB);
  - true orto `N-34-50-A-c-3-2-3` (297 MB) i wycinek 100 x 100 m przy 0.05m;
  - orto ukosna `7.125.11.08 --direction n` (288 MB);
  - bledy przed siecia (pusty katalog wyniku).

  Sprawdz `gdalinfo` (pasma, piksel, EPSG), liste ZIP i sidecary. Wyniki
  do raportu E2E (EZ).
- [ ] **Step 9: Brama i commit** - `feat(elevation,imagery): NMT 100 m, warstwice CZ, intensywnosc, true orto i orto ukosna (plan E, E1)`.

### Task E2: grupy `names` i `maps` - PRNG, nazwy swiata, Geonames, wizualizacje BDOT10k, ZTM

**Zaleznosci:** E0, C, D.

**Files:**
- Create: `kartograf/cli/groups/names.py`, `kartograf/cli/groups/maps.py`,
  `tests/test_names.py`, `tests/test_maps.py`, fixtury
  `tests/fixtures/pl/{prng,prng_world,bdot10k_maps}/`, `tests/fixtures/cz/{geonames,ztm}/`
- Modify: `kartograf/sources/registry.py` (blok E2), `tests/test_parity.py`

**Deskryptory** (endpointy i pola: raport E, wiersze 7, 11, 12, 20, 21):
- `pl.gugik.prng`, product `geographic`, PL.
  - `OGC_API_FEATURES`: `FeatureBBoxParams(protocol="ogcapi",
    native_crs="OGC:CRS84", axis_order="xy", selection="all",
    page_size=10000, timeout=<ponad 95 s, np. 180>)`, jedna `FeatureLayer`
    (kolekcja `NazwaGeograficznaRP`, `id_field="id"`), strony `next`.
    Kazde `items` trwa 78-95 s niezaleznie od `limit` (pomiar 2026-10-16;
    `limit=10000` przyjety), wiec duza strona i limit odczytu kanalu
    (`FeatureBBoxParams.timeout`) sa warunkiem dzialania;
  - `DIRECT_FILES`: `UnitPackageParams(unit="country",
    themes=("MIEJSCOWOSCI", "OBIEKTY_FIZJOGRAFICZNE"))`, trzy
    `PackageVariant` (`format` GML, SHP, XLSX; szablon
    `opendata/prng/PRNG_{theme}_<FORMAT>.zip`, tokeny segmentu `gml`/`shp`/`xlsx`).
- `pl.gugik.prng_world`, product `world`, PL.
  - OGC API: kolekcja `PolskaNazwaGeograficznaSwiata`;
  - pliki: `themes=("SWIAT",)`, te same trzy formaty.
- `cz.cuzk.geonames`, product `geographic`, CZ.
  - `ARCGIS_QUERY`: `FeatureBBoxParams(protocol="arcgis",
    native_crs="EPSG:5514", axis_order="xy", selection="all")`,
    `ags/GEONAMES/Geonames/MapServer`, 25 warstw obiektowych (0-24),
    `order_field="OBJECTID"`;
  - `DIRECT_FILES` + `AtomFilesParams`: dwa kanaly wg `format`
    (`AtomFilesParams.choice=(("format", "GPKG"),)` / `(("format",
    "FGDB"),)`, E0), feedy `atom/GEONAMES-GPKG/GEONAMES-GPKG.xml`
    i `atom/GEONAMES-FGDB/...`, `crs=("EPSG:5514", "EPSG:3045")`,
    `segment_tokens=("gpkg",)` / `("fgdb",)`. URL z data w nazwie pochodzi
    z feedu. Oba kanaly dziela capability i maja te same uklady (ADR-043 D6).
- `pl.gugik.bdot10k_maps`, product `topographic`, PL.
  - `UnitPackageParams(unit="sheet")` i `IndexSource(kind="wms_gfi",
    endpoint=mapy/PZGIK/BDOT/WMS/PobieranieArkuszeMapBDOT10k,
    parser="map_links", unit_field="godlo", url_field=None,
    label_fields=("stan_bazy",))`;
  - osiem `PackageVariant` (`scale` 1:10000/1:25000/1:50000/1:100000
    x `format` TIFF/PDF), `url_template=None`, `file_kind` `tiff`/`pdf`;
  - `sheet_grid=SheetGrid(system="1992", parts=6|5|4|3)` i
    `index_layer="Mapy10k"|"Mapy25k"|"Mapy50k"|"Mapy100k"` wg skali;
  - etykieta = data "Stan bazy" (kazda skala ma swoja date); sygnal
    `index`.
- `cz.cuzk.ztm`, product `topographic`, CZ.
  - `UnitPackageParams(unit="sheet")`, 36 `PackageVariant`, po jednym na
    opublikowana usluge: `choice` (`scale`, `sheet_system`, `format`);
  - `sheet_grid=SheetGrid(system="cuzk", layer=..., crs=...)`: S-JTSK
    0/2/4/6/8/10 (`EPSG:5514`), ETRS89 12/14/16/18/20/22 (`EPSG:3045`,
    zmierzone dla warstwy 14); arkusze plasko `<segment>/<MAPNOM>`;
  - szablon `openzu/ZTM<k>-<SJTSK|ETRS89>-<FORMAT>/{sheet}.zip`; warianty PDF
    maja `.pdf` i `file_kind="pdf"`;
  - sygnal `http`.

- [ ] **Step 1: Fixtury (live):**
  - dwie strony OGC API `NazwaGeograficznaRP` (bbox Krakowa, `limit=5`)
    i jedna strona `PolskaNazwaGeograficznaSwiata`;
  - REST Geonames, warstwa 0 z `exceededTransferLimit`, oraz metadane
    uslugi (25 warstw);
  - feed uslugi i zbioru `GEONAMES-GPKG`;
  - GFI `Mapy10k` i `Mapy100k`;
  - `HEAD` ZTM10 S-JTSK TIFF i ETRS89 PDF.
- [ ] **Step 2: Test RED:**
  - `test_prng_bbox_lonlat_paging`: bbox w EPSG:2180 przechodzi na obwiednie
    CRS84; dwie strony skladaja sie w jeden GPKG bez duplikatu po `id`.
    Sciezka `bbox/<wsp>` jest we wspolrzednych CRS84 `.10g`.
  - `test_prng_whole_country_two_themes`: `--whole-country --format SHP`
    daje dwa pliki z `Notice` rozmiaru. Bez obszaru i bez `--whole-country`
    = `Error:`.
  - `test_world_bbox_crs84_only_pl`: `--bbox-crs EPSG:4326` poza Europa
    jest poprawne i nie jest przycinane do zasiegu PL (`--country pl`
    znaczy tu kraj zrodla, jak w ADR-039); `--country cz` = `Error:`;
    `--whole-country` daje `pl-swiat.zip`.
  - `test_geonames_rest_layers_to_gpkg`: kazda warstwa obiektowa to tabela
    GPKG; warstwy spoza listy deskryptora nie sa pytane (silnik ich nie
    raportuje); brak warstwy z listy = `DownloadError`.
  - `test_geonames_whole_country_crs_and_edition`: feed z dwoma ukladami
    wymaga `--horizontal-crs`; URL z data z feedu; etykieta = `<updated>`
    wpisu.
  - `test_bdot10k_map_sheet_format_slots`: `--scale 1:10000 --format TIFF
    --sheet M-34-064-D-d-1` pobiera link z GFI; slot uzywa godla
    kanonicznego `M-34-64-D-d-1`; `--format PDF` idzie do osobnego slotu;
    `check` porownuje date stanu bazy.
  - `test_ztm_combinations_and_system_from_sheet`: `--sheet 0301-B-01`
    daje S-JTSK, `NM-33-11-4-A-20` daje ETRS89, sprzeczne `--sheet-system`
    = `Error:`; ETRS89 z `DGN` lub `SHP` = `Error:` z lista `TIFF, PDF`;
    `--scale 1:2000` = `Error:` z lista skal CZ; PDF zapisany jako `.pdf`,
    ZIP TIFF+TFW zachowany. Wnioskowanie `sheet_system` z godla dopisuje
    E2 (E0 wybiera wariant tylko po podanych wartosciach; istnienie
    `--sheet` sprawdza w warstwie wariantu).
  - `test_maps_requires_scale_and_format`: brak `--scale` lub `--format`
    = `Error:` z lista dla kraju.
- [ ] **Step 3: Implementacja.**
  - Same deskryptory i parametry, silniki z C/D/E0;
  - grupy `names` i `maps` jako moduly ADR-039 (`add_group`,
    `add_list_sources` z wyborem `--product X --country Y`, flagi z
    `kartograf.cli._args`);
  - handler tylko tlumaczy flagi na `download_collection`/
    `check_collection` i wypisuje `Notice` oraz wynik (wspolny handler
    kolekcji z C);
  - parity: po jednym scenariuszu na produkt.
- [ ] **Step 4: Manifest (warunkowo).**
  - Pozycje `names download` i `maps download` w `kartograf/project/commands.py`
    (`download_collection`/`check_collection`, rodzina `CollectionReport`);
  - `_task` w obu parserach;
  - testy zadania projektu dla obu komend.
- [ ] **Step 5: Live:**
  - PRNG: bbox Krakowa, kraj SHP (ok. 50 MB, dwa pliki);
  - nazwy swiata: bbox;
  - Geonames: bbox CZ i kraj GPKG 5514 (36 MB);
  - wizualizacje BDOT10k: 1:10000 TIFF (63,5 MB) i 1:100000 PDF (29 MB);
  - ZTM10: S-JTSK TIFF `0301-B-01` (37,6 MB) i ETRS89 PDF;
  - drugi przebieg i `--check-updates`.

  Sprawdz `ogrinfo` (warstwy, liczby obiektow, CRS), `gdalinfo` i sidecary.
- [ ] **Step 6: Brama i commit** - `feat(names,maps): nazwy geograficzne PL/CZ i swiata, wizualizacje BDOT10k i ZTM (plan E, E2)`.

### Task E3: `boundaries` i `cadastre` - PRG adresy, granice specjalne, geomorfologia CZ, RCN, mapa katastralna CZ

**Zaleznosci:** E0, C (grupy `boundaries` i `cadastre`, rozpakowanie jednego
GPKG), D (RUIAN w `boundaries`).

**Files:**
- Modify: `kartograf/cli/groups/{boundaries,cadastre}.py`,
  `kartograf/sources/registry.py` (blok E3), `tests/test_parity.py`
- Create: `tests/test_prg_addresses.py`, `tests/test_prg_special.py`,
  `tests/test_cz_geomorphology.py`, `tests/test_rcn.py`,
  `tests/test_cz_cadastral_map.py`, fixtury `tests/fixtures/pl/{prg_addresses,prg_special,rcn}/`
  i `tests/fixtures/cz/{geomorphology,cadastral_map}/`

**Deskryptory** (raport E, wiersze 9, 10, 14, 19, 24):
- `pl.gugik.prg_addresses`, product `addresses`.
  - `WFS`: `FeatureBBoxParams(protocol="wfs", native_crs="EPSG:2180",
    axis_order="yx", selection="all")`,
    `wss/ext/wfs/KrajowaIntegracjaNumeracjiAdresowej`, warstwy
    `adresyUlice:A07_Punkty_adresowe` i `adresyUlice:A08_Ulice`;
  - `DIRECT_FILES` `UnitPackageParams(unit="powiat")`: wariant SHP
    `opendata/prg/adresy/PunktyAdresowe/{woj}/{teryt}.zip`, token `shp`;
  - `DIRECT_FILES` `UnitPackageParams(unit="country")`: wariant SHP
    `opendata/prg/adresy/PunktyAdresowe/POLSKA.zip` i drugi plik
    `opendata/prg/adresy/PRG-punkty_adresowe.zip`. Jego `format` i token
    wpisz dopiero po `unzip -l` w Step 5.
- `pl.gugik.prg_special`, product `special`.
  - `OGC_API_FEATURES`: `FeatureBBoxParams(protocol="ogcapi",
    native_crs="OGC:CRS84", selection="all")`, `ogcapi/PRG/apiFeatures`;
    45 `FeatureLayer` wypisanych jawnie (wszystkie kolekcje poza 6
    `Granica*` planu C; `/collections` 2026-10-16: 51 kolekcji, kazda
    tylko CRS84; strona `items` ok. 3,5 s - domyslny limit odczytu
    wystarcza);
  - `UnitPackageParams(unit="country")`: warianty SHP i GML
    (`opendata/prg/granice/00_granice_specjalne_{shp,xml}.zip`).
- `cz.cuzk.geomorphology`, product `geomorphology`.
  - `ARCGIS_QUERY`: `FeatureBBoxParams(protocol="arcgis",
    native_crs="EPSG:5514", axis_order="xy", selection="level")`,
    `ags/GeomorfologickeJednotky/MapServer`;
  - `FeatureLayer.code` = poziom: `subprovincie` 33, `oblast` 34,
    `celek` 39, `podcelek` 35, `okrsek` 36, `podokrsek` 37, `cast` 38.
- `pl.gugik.rcn`, product `prices`.
  - Dwa kanaly `UnitPackageParams(unit="powiat")` i `(unit="woj")`
    z wariantem
    `opendata/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/{teryt}_transakcje_ceny.gpkg.zip`;
  - `unpack=".gpkg"` (jeden GPKG rozpakowany lokalnie, jak EGiB w C);
  - kontrola warstw `transakcje_dzialki`, `transakcje_budynki`,
    `transakcje_lokale`.
- `cz.cuzk.cadastral_map`, product `map`, CZ.
  - `UnitPackageParams(unit="ku", ku_layer="https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/7")`
    (pelny adres warstwy, jak `RUIAN_7` w `tests/test_collections_units.py`),
    cztery `PackageVariant`
    (`format`) z szablonami:
    - SHP `services.cuzk.gov.cz/shp/ku/epsg-5514/{ku}.zip`;
    - DXF `.../dxf/ku/{ku}.zip`;
    - DGN `.../dgn/ku/{ku}.zip`;
    - VFK `.../vfk/stavy/aktualni/{ku}.zip`;
  - KU obszaru z RUIAN; sygnal `http`;
  - VKM poza 0.8.0 (P2).

- [ ] **Step 1: Fixtury (live):**
  - WFS KIN: dwie strony A07 (bbox Krakowa, `COUNT=2`) i jedna A08;
  - `/collections` OGC API PRG i strona jednej kolekcji (np. `SadRejonowy`);
  - REST geomorfologii: warstwa 39 i metadane uslugi;
  - RCN: przyciety GPKG z prawdziwego pliku 1201 (kilka obiektow z kazdej
    z trzech warstw, ten sam schemat; `ogr2ogr -limit`), spakowany jak
    zrodlo;
  - RUIAN 7 dla bbox z 2 KU; `HEAD` KM 623164 w 4 formatach.
- [ ] **Step 2: Test RED:**
  - `test_addresses_bbox_layers_ne`: zapytanie ma osie N,E (odwrocone daja
    0 obiektow w fixturze); GPKG ma dwie tabele.
  - `test_addresses_units`: `--teryt 1261` daje ZIP SHP 1:1; `--teryt 12`
    = `Error:` "paczki punktow adresowych sa powiatowe"; `--whole-country
    --format SHP` daje `Notice` 563 803 725 B przed `GET`.
  - `test_special_collections_contract`: 45 kolekcji z deskryptora jest
    w `/collections`; brak jednej = `DownloadError` z nazwa; kolekcja spoza
    deskryptora nie jest pytana (silnik E0 jej nie raportuje); kolekcje
    `Granica*` nigdy nie sa pytane.
  - `test_special_needs_area_or_country`: bez obszaru i bez
    `--whole-country` = `Error:`.
  - `test_geomorphology_level_required`: brak `--level` = `Error:` z lista;
    `celek` pyta tylko warstwe 39; adnotacje i mozaika nigdy nie sa pytane.
  - `test_rcn_units_and_layers`: `1261` i `12` wybieraja kanal powiatu albo
    wojewodztwa; inna dlugosc kodu = `Error:`; GPKG bez jednej z trzech
    warstw = `DownloadError` i brak wersji; SQLite tylko w lokalnym
    stagingu.
  - `test_cz_km_ku_and_formats`: `--ku 623164 --format SHP` daje URL
    z szablonu; brak `--format` = `Error:` z lista; `--ku` z `--country pl`
    = `Error:`; 404 jednego KU = blad tej jednostki, pozostale zapisane.
  - `test_cz_km_area_ku_discovery`: bbox daje KU z RUIAN; drugi przebieg
    porownuje `ETag`.
- [ ] **Step 3: Implementacja.** Deskryptory, wybory i walidacja; grupy
  `boundaries` i `cadastre` dostaja produkty, `--format` i `--ku`. Handler
  ten sam co w C; parity po jednym scenariuszu na produkt.
- [ ] **Step 4: Manifest (warunkowo).** Opcje `boundaries download`
  i `cadastre download` (`format`, `ku`); test zadania projektu z RCN.
- [ ] **Step 5: Live:**
  - adresy: bbox Krakowa, `--teryt 1261` (6 MB), kraj SHP (564 MB) i drugi
    plik krajowy (803 MB). Po `unzip -l` drugiego pliku dopisz jego wariant
    (`format` i token) z testem na fixturze listy ZIP, potem powtorz brame;
  - granice specjalne: bbox i kraj SHP (734 MB);
  - geomorfologia: `--level celek`, bbox;
  - RCN: 1201 (9,7 MB) i 1261 (301 623 607 B 2026-10-16, a 236 404 584 B
    2026-10-15: plik `latest_exports` jest podmieniany, wiec bez
    porownania SHA-256 z raportem E; `Notice` `DOWNLOAD_SIZE`);
  - mapa katastralna: 623164 w 4 formatach i bbox z kilkoma KU;
  - VKM: ponowne sprawdzenie odpowiedzi plikow (dowod do wpisu w backlogu
    PROGRESS, P2).
- [ ] **Step 6: Brama i commit** - `feat(boundaries,cadastre): PRG adresy i granice specjalne, geomorfologia CZ, RCN, mapa katastralna CZ (plan E, E3)`.

### Task E4: `landcover` - BDOO, Data50, Data250

**Zaleznosci:** E0, C (BDOT10k archiwalny w `LandCoverManager`
z `unit_package` i filtrem klas), D (ZABAGED w `LandCoverManager`
z `feature_bbox`, `--whole-country` i `--horizontal-crs`).

**Files:**
- Modify: `kartograf/landcover/manager.py` (`PROVIDERS`, opcje, wymagane
  opcje), moduly zrodel `landcover` z C/D (dopisanie zrodel, bez nowego
  providera kopiujacego pobieranie), `kartograf/cli/groups/landcover.py`
  (wybory i teksty), `kartograf/sources/registry.py` (blok E4),
  `tests/test_parity.py`
- Create: `tests/test_bdoo.py`, `tests/test_cz_data50_250.py`, fixtury
  `tests/fixtures/pl/bdoo/`, `tests/fixtures/cz/data50_250/`

**Deskryptory** (raport E, wiersze 8, 17, 18):
- `pl.gugik.bdoo` (`storage_subdir="landcover/pl_bdoo"`).
  - `DIRECT_FILES` `UnitPackageParams(unit="woj")`, siedem `PackageVariant`
    (`year` 2015, 2021, 2022, 2023, 2024, 2025, 2026; szablon
    `opendata/bdoo/<rok>/PL.PZGiK.201.{woj}.zip`, token roku);
  - filtr `--layers` jak BDOT10k w C (klasy `OT_<KOD>` w nazwach plikow GML).
- `cz.cuzk.data50` i `cz.cuzk.data250` (`storage_subdir="landcover/cz_data50"`
  i `.../cz_data250`).
  - `ARCGIS_QUERY`: `FeatureBBoxParams(protocol="arcgis",
    native_crs="EPSG:5514", axis_order="xy", selection="all",
    order_field="OBJECTID")`; warstwy obiektowe `ags/DATA50/MapServer` (69)
    i `ags/DATA250/MapServer` (116);
  - `DIRECT_FILES` + `AtomFilesParams(service_feed=atom/Data50/Data50.xml`
    i `.../Data250/Data250.xml`, `crs=("EPSG:5514", "EPSG:3045")`,
    `segment_tokens=("shp",)`): plik krajowy SHP ZIP.

- [ ] **Step 1: Fixtury (live):**
  - `HEAD` BDOO 12/2023 i 12/2018 (404);
  - przyciety prawdziwy ZIP BDOO (kilka plikow GML z centralnym katalogiem
    jak zrodlo);
  - metadane REST DATA50 i DATA250;
  - dwie warstwy z `exceededTransferLimit`;
  - feedy uslugi i zbioru `Data50`.
- [ ] **Step 2: Test RED:**
  - `test_bdoo_year_required`: brak `--year` = `Error:` z lista lat;
    `--year 2018` = `Error:` z ta sama lista.
  - `test_bdoo_woj_units`: bbox Krakowa daje `12`; bbox na granicy dwoch
    wojewodztw daje dwa pliki; `--teryt 1261` = `Error:` "BDOO jest
    publikowane per wojewodztwo: --teryt 12".
  - `test_bdoo_years_separate_slots`: 2015 i 2023 trafiaja do roznych
    segmentow; te same bajty w jednym slocie = `unchanged`.
  - `test_bdoo_layers_filter`: `--layers ADJA` zostawia tylko pliki
    `OT_ADJA_*` (osobny segment); nieznana klasa = `Error:`.
  - `test_data50_bbox_feature_layers`: tylko warstwy obiektowe; kazda to
    tabela GPKG; bbox w innym ukladzie niz natywny przechodzi na obwiednie
    EPSG:5514.
  - `test_data50_whole_country_crs`: `--whole-country` bez
    `--horizontal-crs` = `Error:` z `EPSG:5514, EPSG:3045`; etykieta
    z `<updated>`; `Notice` 515 542 917 B.
  - Parametryzacja tych samych testow dla Data250.
- [ ] **Step 3: Implementacja.** Zrodla w `LandCoverManager` na sciezkach
  C (BDOO jak archiwum BDOT10k) i D (Data50/250 jak ZABAGED). Teksty
  `--source` i `list-sources` z rejestru.
- [ ] **Step 4: Manifest (warunkowo).** `landcover download` bez nowych
  flag (`test_task_options_equal_parser_data_flags` zielony bez zmian);
  test zadania projektu z BDOO.
- [ ] **Step 5: Live:**
  - BDOO 12/2023 (11,5 MB), 12/2015 (14,6 MB) i `--layers`;
  - Data50: bbox i kraj 5514 (516 MB);
  - Data250: bbox i kraj 5514 (230 MB);
  - drugi przebieg i `--check-updates`.
- [ ] **Step 6: Brama i commit** - `feat(landcover): BDOO oraz Data50 i Data250 CZ (plan E, E4)`.

### Task E5: `models3d` i `geodesy` - mesh 3D, drzewa, osnowy PL i CZ, quasi-geoidy

**Zaleznosci:** E0, A (`WfsIndex`), C (grupa `models3d`, `unit_package`,
`feature_bbox`), D (`AtomFilesParams` dla QGZU).

**Files:**
- Modify: `kartograf/cli/groups/models3d.py`, `kartograf/sources/registry.py`
  (blok E5), `tests/test_parity.py`
- Create: `kartograf/cli/groups/geodesy.py`, `tests/test_mesh_trees.py`,
  `tests/test_geodesy.py`, fixtury `tests/fixtures/pl/{mesh_3d,trees_3d,prpog,quasigeoid}/`
  i `tests/fixtures/cz/{survey_control,qgzu}/`

**Deskryptory** (raport E, wiersze 5, 6, 13, 15, 22, 23):
- `pl.gugik.mesh_3d`, product `mesh`.
  - `UnitPackageParams(unit="tile")` z `IndexSource(kind="wfs",
    endpoint=mapy/PZGIK/NMT/WFS/ModeleSiatkowe3D, parser=None,
    unit_field="modul", url_field="URL_do_pobrania",
    label_fields=("Aktualnosc", "Numer_zgloszenia_pracy"),
    year_field="akt_rok", zone_field="uklad_xy")`; jeden `PackageVariant`
    z `url_template=None`, `index_layer="gugik:SkorowidzModeleSiatkowe3D"`
    i `members=(".obj",)`; strefa slotu i uklad sidecara z `uklad_xy`;
  - obszar duzego miasta to tysiace kafli (Krakow: 3884 po ok. 37 MB,
    ok. 143 GB); E0 wypisuje je w `UNIT_LIST` i nie ogranicza. Limit
    liczby kafli albo wymog potwierdzenia zmienia produkt: E5 zglasza
    pytanie z rekomendacja zamiast zgadywac;
  - najnowszy rekord kafla, `--year` jako filtr (D5, ADR-028).
- `pl.gugik.trees_3d`, product `trees`.
  - `UnitPackageParams(unit="powiat")`, jeden `PackageVariant`
    (`choice` `lod=1`, `year=2023`): szablon
    `opendata/InneDane/Drzewa3D/LOD1/2023/{woj}/{teryt}.zip`, tokeny
    `lod1`, `2023`;
  - obie flagi maja jedna wartosc i mozna je pominac.
- `pl.gugik.prpog`, product `control`, PL. Kazda siec to wartosc `network`:
  - `horizontal`: kanal `WFS` `PodstawowaOsnowaGeodezyjnaPozioma`
    (`choice=(("network", "horizontal"),)`, warstwy `ms:Fundamentalna_pozioma`,
    `ms:Bazowa_pozioma`, `selection="all"`, osie N,E) i kanal paczki
    `UnitPackageParams(unit="powiat")`
    (`opendata/bdpog/Pozioma/{teryt}_PodstawowaOsnowaPozioma.zip`, token
    `package`);
  - `vertical`: to samo dla `...Wysokosciowa`
    (`.../Wysokosciowa/{teryt}_PodstawowaOsnowaWysokosciowa.zip`);
  - `gravity`: kanal WFS `.../OsnowaGrawimetryczna/WFS` (adres bez `/WFS`
    nie odpowiada; `choice=(("network", "gravity"),)`, warstwy
    `ms:Fundamentalna_grawimetryczna` i `ms:Bazowa_grawimetryczna`,
    `id_field="nr_punktu"` - obiekty bez `gml:id`); kanaly WFS sieci dziela
    capability i uklad EPSG:2180 (ADR-043 D6); `magnetic`: kanal WFS
    `OsnowaMagnetyczna` z typami punktow i `ms:izogony`, bez
    `ms:izogony_etykiety`;
  - `archive-1942`, `archive-kronsztadt60`: `UnitPackageParams(unit="sheet")`,
    `PackageVariant.sheet_grid=SheetGrid(system="1992", parts=3)` (arkusz
    1:100000, godlo bez zera wiodacego), szablon
    `opendata/bdpog/MaterialyArchiwalne/Katalogi_<Kartoteki1942|Kronsztadt60>/{sheet}.zip`.
- `cz.cuzk.survey_control`, product `control`, CZ.
  - `ARCGIS_QUERY` `ags/BodovaPole/MapServer`:
    `FeatureBBoxParams(protocol="arcgis", native_crs="EPSG:5514",
    axis_order="xy", selection="level", selection_key="network")`;
  - `FeatureLayer.code` = siec: `gnss` 0; `horizontal` 18 i 20;
    `densification` 38 i 40; `horizontal-detailed` 42; `vertical` 44;
    `vertical-detailed` 46; `gravity` 48;
  - warstwy wariantow wyznaczenia (2-9, 22-29) maja byc podzbiorami 18/20
    i 38/40. Potwierdz to na fixturze po numerach punktow; jesli nie sa,
    dolacz je do sieci;
  - warstwy "zrusene" i "Cisla" sa pomijane.
- `pl.gugik.quasigeoid`, product `geoid`, PL.
  - `UnitPackageParams(unit="country")`, jeden wariant ze stalym URL
    `opendata/InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt`
    i `file_kind="txt"` (E0): plik sprawdzany jako tekst (bez bajtow NUL,
    pierwsza linia nie jest znacznikiem HTML/XML; naglowek pliku 2026-10-16:
    `Szerokosc Dlugosc Zeta`, wiersze CRLF) zamiast katalogu ZIP.
- `cz.cuzk.qgzu`, product `geoid`, CZ.
  - `DIRECT_FILES` + `AtomFilesParams(service_feed=atom/QGZU/QGZU.xml,
    crs=())`: jeden zbior, kategoria EPSG:4258, ZIP zostaje.

- [ ] **Step 1: Fixtury (live):**
  - dwie strony WFS mesh;
  - przyciety prawdziwy ZIP kafla (OBJ, MTL i JPG zmniejszone, te same
    nazwy i katalog);
  - `HEAD` drzew 2261;
  - WFS czterech sieci PL (bbox Krakowa, `COUNT=2`);
  - `HEAD` paczek osnow 1201 i archiwow `M-34-64`;
  - metadane i warstwa 44 `BodovaPole`;
  - feedy `QGZU`;
  - naglowek i dwie ostatnie linie modelu PL-geoid2021.
- [ ] **Step 2: Test RED:**
  - `test_mesh_tiles_from_bbox`: kafle z dwoch stron WFS; zapis
    `models3d/pl_mesh/s7/<modul>.zip`; ZIP z OBJ, MTL i JPG bez
    rozpakowania; `check` porownuje rekord bez `GET`.
  - `test_mesh_newest_and_year`: dwa rekordy kafla; bez `--year`
    pobierany jest nowszy, z `--year` wskazany; brak roku = `NoCoverageError`
    (mechanizm E0; na zywo kilku lat jednego kafla nie zaobserwowano -
    drugi rekord powstaje w tescie z prawdziwej strony WFS).
  - `test_trees_size_notice_and_stream`: `Notice` 3 408 621 873 B przed
    `GET`. Strumien do stagingu (atrapa duzego strumienia bez trzymania
    w pamieci). ZIP sprawdzany na pliku. `--lod 2` i `--year 2024` =
    `Error:` z jedyna wartoscia.
  - `test_trees_unit_failure_isolated`: 404 jednego powiatu nie zatrzymuje
    pozostalych; brak wersji dla bledu.
  - `test_pl_control_bbox_networks`: kazda siec to osobny segment; GPKG ma
    warstwy Fundamentalna i Bazowa (magnetyczna takze `izogony`); osie N,E.
  - `test_pl_control_packages_and_archives`:
    - `--teryt 1201 --network horizontal` daje URL paczki;
    - `--teryt` z `gravity` = `Error:` "siec grawimetryczna jest
      dostepna tylko dla obszaru";
    - `--network archive-1942 --sheet M-34-064-D` daje arkusz `M-34-64`
      (`Notice` 1 069 061 020 B); 404 arkusza = blad jednostki.
  - `test_cz_control_layers`: `vertical` pyta tylko warstwe 44; brak
    `--network` = `Error:` z listami per kraj.
  - `test_geoid_whole_country_only`: `--bbox` = `Error:` "model
    quasi-geoidy to jeden plik krajowy: --whole-country"; PL zapisuje TXT
    1:1; CZ etykieta `2021-02-22` z ATOM; `check` bez `GET`.
- [ ] **Step 3: Implementacja.**
  - Deskryptory i walidacja;
  - grupa `geodesy` jako modul ADR-039 (`download`, `list-sources`; flagi
    obszaru, `--teryt`, `--network`, `--whole-country`, aktualizacji
    i wyniku);
  - `models3d` dostaje produkty `mesh` i `trees`;
  - handler kolekcji z C; parity po jednym scenariuszu na produkt.
- [ ] **Step 4: Manifest (warunkowo).** Pozycja `geodesy download`, `_task`,
  test zadania projektu; `models3d download` bez nowych flag.
- [ ] **Step 5: Live:**
  - mesh: 1 kafel w Krakowie (38 MB);
  - drzewa 2261: 3,4 GB, pelne pobranie i `unzip -t`;
  - osnowy PL: bbox Krakowa w 4 sieciach, paczki 1201 (2,9 MB i 14,2 MB),
    archiwa `M-34-64` Kronsztadt60 (26 MB) i 1942 (1,07 GB);
  - Bodove pole `vertical`: bbox CZ;
  - quasi-geoidy: PL-geoid2021 i QGZU (SHA-256 z raportu E, jesli zrodlo
    nie zmienilo pliku);
  - drugi przebieg.
- [ ] **Step 6: Brama i commit** - `feat(models3d,geodesy): mesh 3D, drzewa, osnowy PL i CZ, quasi-geoidy (plan E, E5)`.

### Task EZ: Integracja, dokumentacja, ADR i E2E calego planu

**Zaleznosci:** E1-E5 scalone.

**Files:** `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md` (`[0.8.0] - Unreleased`),
`docs/USAGE.md`, `docs/ARCHITECTURE.md`, `docs/SCOPE.md`, `docs/PRD.md`,
`docs/research/2026-10-xx-plan-e-e2e/raport.md`, `tests/test_sources_registry.py`.
`docs/PROGRESS.md` wg polecenia koordynatora.

- [ ] **Step 1: Test spojnosci rejestru** (`tests/test_sources_registry.py`).
  Kazdy z 24 deskryptorow statusu (`pl.gugik.nmt_100m` takze jako wariant
  rejestru A) ma: licencje, sygnal kanalu, szablon segmentu bez wielkich
  liter i wpis w `list-sources` swojej grupy. Wartosci `--product` w grupach
  kolekcji sa unikalne. Zaden kanal danych nie jest `WMS`.
- [ ] **Step 2: Dokumentacja:**
  - USAGE: przyklad kazdego produktu (grupy `names`, `maps`, `geodesy`;
    nowe produkty pozostalych grup; `--whole-country` z ostrzezeniem;
    `--direction`; godla 8-czlonowe);
  - ARCHITECTURE: 2 (moduly), 3.3 (segmenty z sekcji "Decyzje" pkt 5),
    4 (jednostki `sheet`/`tile`/`ku`, sygnal `index` w kolekcjach,
    atom `woj`), 5 (nowy produkt = deskryptor + parametry kanalu);
  - SCOPE: 2.x i 3.3 (plan E wykonany);
  - PRD: produkty;
  - CHANGELOG, sekcja Dodane: 24 produkty, grupy `names`, `maps`,
    `geodesy`, `--direction`, `--ku`, `--network`. Zmiana lamiaca tylko
    jesli ktorys pakiet zmienil istniejace zachowanie, z "Co zrobic";
  - ADR-043: errata z wynikami E2E i ostatecznymi nazwami symboli E1-E5.
- [ ] **Step 3: E2E calego planu** (`-o <katalog-danych>/kartograf/e2e/<data>-plan-e/`,
  cache metadanych w korzeniu worktree):
  - powtorz scenariusze live E1-E5 na scalonym kodzie;
  - raport ma 24 wiersze PASS/FAIL: komenda, transfer, liczby
    obiektow/pasm, SHA-256 tam, gdzie zrodlo stale;
  - drugi przebieg, `--check-updates` i `--upgrade` dla sygnalow `http`
    (CZ), `metadata` (ATOM), `index` (mesh, mapy) i `none` (GUGiK);
  - `--help` i `list-sources` kazdej grupy z CLI;
  - bez sciezki katalogu danych;
  - PASS tylko po pelnym przebiegu; produkt zablokowany = pytanie
    z rekomendacja.
- [ ] **Step 4: Brama** (pelne `pytest -m "not live"`, `ruff check .`,
  `ruff format --check .`, `mypy kartograf/ tests/`) i commit
  `docs: ADR-043, CHANGELOG i dokumentacja planu E; raport E2E`.

## Review Focus

1. **Obszar nigdy nie daje pliku krajowego (K7).** Plik krajowy tylko
   z `--whole-country` i `Notice` z `HEAD`. Testy `*_needs_area_or_country`,
   `*_whole_country_*`.
2. **Awaria to nie brak danych.** HTML przy 200, wyjatek OGC, przerwane
   stronicowanie, obcy `next` i przeciety ZIP konczy sie `DownloadError`
   bez wersji. Pusty, kompletny wynik to brak jednostek albo
   `NoCoverageError`.
3. **GB bez RAM i bez `Range`.** Drzewa, archiwum 1942, pliki krajowe:
   strumien do stagingu, `zipfile` na pliku, `Notice` przed `GET`.
4. **Etykiety skal.** Serie map i godla 8-czlonowe mapowane po liczbie
   czlonow, nie po `SheetParser.scale` (backlog A1-8).
5. **Osie bbox.** GUGiK WFS: N,E. OGC API GUGiK: lon,lat (CRS84). ArcGIS
   REST CUZK: X,Y. Kazde z fixtura i odwrotnoscia.
6. **Paczki 1:1.** OBJ+MTL+JPG, SHP komplet, TIFF+TFW, GML per klasa
   zostaja nietkniete. Rozpakowany jest tylko RCN (jeden GPKG).
7. **Sygnaly.** `index` i `metadata` sprawdzaja aktualnosc bez transferu
   danych. `none` = `unverifiable`, nigdy `current`.
8. **Quasi-geoidy to dane.** Zadna sciezka pobierania ani wycinka ich nie
   stosuje.

## Kryteria zamkniecia

- Kazdy z 24 wierszy tabeli statusow dziala z CLI i API. Ma deskryptor
  (NMT 100 m jako wariant rejestru), licencje, `list-sources`, jednoznaczny
  slot `data/`, sidecar wersji, sygnal zgodny z kanalem, test offline na
  prawdziwej fixturze i przebieg live. Decyzje P1 i P2 uzytkownika
  (2026-10-15) sa wykonane.
- Brak drugiego silnika, drugiej listy wariantow i providera kopiujacego
  pobieranie. Nowe mechanizmy ograniczaja sie do E0 i E1 (selektor `woj`,
  godla 8-czlonowe).
- Manifest: kazda komenda danych planu E ma `_task` i pozycje w
  `kartograf/project/commands.py`, jesli manifest jest na `develop`.
- Brama zielona. ADR-043, CHANGELOG, USAGE, ARCHITECTURE, SCOPE i PRD
  zaktualizowane; raport E2E w `docs/research/`.
