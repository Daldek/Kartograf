# Plan C na zywo (Task 8): archiwum BDOT10k, modele 3D, PRG, EGiB

Data: 2026-10-15, 22:53-23:15 CEST. Galaz `feat/plan-c-collections`.
Pobrania (sekcje 1-7) na kodzie `fffe71a` (sidecary: `kartograf_version`
`0.8.0-dev+fffe71a`); sprawdzenie poprawki podpowiedzi (sekcja 8), projekt
i API (sekcja 9) na `92b0005` (poprawka z testem regresji). CLI: ta sama
`kartograf.cli.commands.main(argv)` uruchamiana z korzenia worktree przez
opakowanie `requests.Session.send`, ktore wypisuje metode, URL, status,
`Content-Length` i czas kazdego zapytania ("HTTP" nizej; caly ruch HTTP
Kartografa idzie przez `requests`). Cache metadanych: domyslny
`.kartograf_cache.db` w korzeniu worktree. Dane wylacznie w
`<katalog-danych>` (udzial SMB 3.1.1, cifs), kazde polecenie z jawnym
`-o <katalog-danych>`; polecenia sekwencyjnie. CLMS bez credentials -
nie dotyczy planu C.

## Wynik

| # | Polecenie (`-o <katalog-danych>`) | Oczekiwane (plan Task 8) | Wynik |
|---|---|---|---|
| 1 | `landcover download --source bdot10k --teryt 1261 --year 2024 --format SHP` | 47 404 309 B | PASS: `nowa wersja 2024_5dbd678a`, 47 404 309 B, 29,8 s, 1 GET |
| 2 | `... --year 2022 --format SHP` | sha `6c64b1d33782...` | PASS: `nowa wersja 2022_6c64b1d3`, 46 762 581 B, 19,7 s |
| 3 | `... --year 2023 --format SHP` | `relabeled` wzgledem 2022, ten sam i-wezel | PASS: `nowa etykieta 2023 (plik identyczny z 2022)`; ten sam plik na serwerze (sekcja 6) |
| 4 | `models3d download --product buildings --lod 1 --year 2024 --teryt 1261` | 28 790 760 B, sha `dff392bbb6e8...` | PASS: `nowa wersja 2024_dff392bb`, 28 790 760 B, `vertical_crs` EPSG:9651, 11,4 s |
| 5 | `models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500` | paczka powiatu z PRG | PASS: `Info: buildings: powiaty obszaru wg PRG (1): 1261`, `nowa wersja 2017_de14ed18`, 59 961 467 B, EPSG:9650, `extra.parent_request` |
| 6 | `boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000` | 39 obiektow `A03_Granice_gmin` | PASS: 39 obiektow (GPKG i sidecar), `hits` z dnia 39, 1 strona, 6,6 s |
| 7 | `boundaries download --product admin --teryt 12` | 22 070 839 B | PASS: `nowa wersja 2026-10-15_919fce9d`, 22 070 839 B, 8,5 s |
| 8 | `cadastre download --product map --teryt 1261` | eksport powiatu GPKG | PASS: ZIP 87 175 594 B -> `1261.gpkg` 284 045 312 B (`dzialki` 215 626, `budynki` 116 673, `transakcje` 233 604), 36,0 s |
| 9 | `cadastre download --product map --country pl --bbox 565000,243000,567000,245000` | 3306 dzialek (porownaj z `hits` z dnia) | PASS: `dzialki` 3306, `budynki` 2947 = `hits` z dnia (3306, 2947), 4 + 3 strony, 29,0 s |
| R | powtorzenie 1-9 | `local`, zero transferu danych | PASS: 9 x `lokalna wersja ... (bez sprawdzania; --check-updates)`, kod 0, 0 zapytan HTTP |
| C | `--check-updates` dla 1-9 | `unverifiable` | PASS: 9 x `nie da sie sprawdzic bez pobrania (<etykieta>)`, 0 zapytan |
| F | `--force` dla 1 (BDOT10k 2024) | `unchanged` | PASS: 1 GET, `bez zmian 2024`; dodatkowo `--force` dla 6: `bez zmian` (te same bajty GPKG) |
| S | sidecary, dowiazania | `request`, `extra.*`, hardlinki | PASS: sekcje 5 i 6 |
| + | PRG `--whole-country`, obszar 2 powiatow `--workers 2`, luki LoD2, bledy wyboru, projekt, API | - | PASS (sekcje 7-9); 1 blad tekstu podpowiedzi naprawiony z testem regresji (sekcja 8) |

## 1. Pierwsze pobranie

Zapytania HTTP kazdego polecenia (pelne URL-e w logu przebiegu; adresy
uslug sa publiczne):

| # | Zapytania | Linia statusu |
|---|---|---|
| 1 | `GET .../Archiwum/bdot10k/2024/SHP/12/1261_SHP_2024.zip` 200, 47 404 309 B | `landcover/pl_bdot10k_shp_2024/teryt/1261.zip: nowa wersja 2024_5dbd678a` |
| 2 | `GET .../2022/SHP/12/1261_SHP_2022.zip` 200, 46 762 581 B | `landcover/pl_bdot10k_shp_2022/teryt/1261.zip: nowa wersja 2022_6c64b1d3` |
| 3 | `GET .../2023/SHP/12/1261_SHP_2023.zip` 200, 46 762 581 B | `landcover/pl_bdot10k_shp_2023/teryt/1261.zip: nowa etykieta 2023 (plik identyczny z 2022)` |
| 4 | `GET .../InneDane/Budynki3D/LOD1/2024/12/1261.zip` 200, 28 790 760 B | `models3d/pl_buildings_lod1_2024/teryt/1261.zip: nowa wersja 2024_dff392bb` |
| 5 | WFS PRG `A02_Granice_powiatow` (`BBOX=243000,566000,243500,566500,urn:...:2180`, N,E) 808 B; `GET .../LOD2/1261_gml.zip` 200, 59 961 467 B | `models3d/pl_buildings_lod2_2017/teryt/1261.zip: nowa wersja 2017_de14ed18` |
| 6 | PRG `GetCapabilities`; `GetFeature RESULTTYPE=hits` (`A03_Granice_gmin`, `BBOX=220000,550000,270000,590000,...`); `DescribeFeatureType`; 1 strona `COUNT=1000&STARTINDEX=0` (2,8 s) | `boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg: nowa wersja 2026-10-15_d8fd43e6` |
| 7 | `GET .../prg/granice/12_GraniceAdministracyjne.zip` 200, 22 070 839 B | `boundaries/pl_prg_gml/teryt/12.zip: nowa wersja 2026-10-15_919fce9d` |
| 8 | `GET .../latest_exports/eziudp_wfs/GPKG/1261.gpkg.zip` 200, 87 175 594 B | `cadastre/pl_egib_gpkg/teryt/1261.gpkg: nowa wersja 2026-10-15_fd23bd6e` |
| 9 | EGiB `GetCapabilities`; `hits` `ms:dzialki` i `ms:budynki`; `DescribeFeatureType` x 2; strony `dzialki` `STARTINDEX` 0/1000/2000/3000 i `budynki` 0/1000/2000 (1,9-4,4 s na strone) | `cadastre/pl_egib/bbox/565000_243000_567000_245000.gpkg: nowa wersja 2026-10-15_14c95c95` |

Kazde polecenie: kod 0, jedna linia statusu na stdout. BBOX zapytan WFS
GUGiK ma kolejnosc N,E (`axis_order="yx"`), zgodnie z ADR-042 D4.

Zawartosc GPKG (odczyt `pyogrio.read_info`, GDAL 3.12.4, pyogrio 0.13.0):

| Plik | Warstwa | Typ | Obiekty | Uklad |
|---|---|---|---|---|
| `boundaries/pl_prg_gmina/bbox/550000_220000_590000_270000.gpkg` (2 146 304 B) | `A03_Granice_gmin` (pola PRG, m.in. `JPT_KOD_JE`, `IIP_IDENTY`) | MultiPolygon | 39 | EPSG:2180 |
| `cadastre/pl_egib/bbox/565000_243000_567000_245000.gpkg` (3 461 120 B) | `dzialki` (`gml_id`, `ID_DZIALKI`, ...; bez `DATA`) | MultiPolygon | 3306 | EPSG:2180 |
| jw. | `budynki` (`gml_id`, `ID_BUDYNKU`, ...) | MultiPolygon | 2947 | EPSG:2180 |
| `cadastre/pl_egib_gpkg/teryt/1261.gpkg` (eksport GUGiK 1:1) | `dzialki` / `budynki` / `transakcje` | - | 215 626 / 116 673 / 233 604 | EPSG:2180 |

Kontrola niezalezna (`curl`, 22:59): `RESULTTYPE=hits` dla tych samych
BBOX - `ms:dzialki` 3306, `ms:budynki` 2947, `ms:A03_Granice_gmin` 39.

## 2. Powtorzenie (polecenia 1-9)

9 x `lokalna wersja <etykieta> (bez sprawdzania; --check-updates)`, kod 0,
0 zapytan HTTP (takze polecenie 5: lista powiatow obszaru z cache
metadanych, `Info:` jak przy pierwszym pobraniu). Czas 0,5-1,0 s, polecenie
8 - 2,9 s: na tym udziale cifs i-wezly nie sa stabilne, wiec dowiazanie
potwierdza tresc (sha256 dowiazania = sha256 sidecara wersji,
`links._same_content_hardlink`; 284 MB odczytu).

## 3. `--check-updates` i plan

- 9 x `<jednostka>: nie da sie sprawdzic bez pobrania (<etykieta>)` (np.
  `1261: nie da sie sprawdzic bez pobrania (2024)`,
  `550000_220000_590000_270000: ... (2026-10-15)`), kod 0, 0 zapytan
  (polecenie 5: cache metadanych PRG).
- `models3d download ... --lod 1 --year 2024 --teryt 1261 --check-updates
  --plan <katalog-danych>/plans/models3d.json`: plik planu
  `kartograf-plan/1` z jedna pozycja `{"track": "collection", "segment":
  "models3d/pl_buildings_lod1_2024", "hierarchy": "teryt", "name":
  "1261.zip", "unit": "1261", "local_label": "2024", "status":
  "unverifiable"}`; `--upgrade --plan` tym plikiem - `lokalna wersja 2024`,
  kod 0, 0 zapytan.
- `boundaries download --product admin --teryt 12 --upgrade`: `Info: ...
  lokalna wersja 2026-10-15 niesprawdzona - zrodlo bez taniego sygnalu;
  pobierz ponownie: --force` i linia statusu, kod 0, 0 zapytan.

## 4. `--force`

- Polecenie 1 z `--force`: 1 GET paczki (47 404 309 B), `bez zmian 2024`
  (16,9 s); magazyn bez nowej wersji.
- Polecenie 6 z `--force`: `GetCapabilities`, `hits`, `DescribeFeatureType`,
  1 strona; `bez zmian 2026-10-15` - GPKG zlozony ponownie ze swiezej
  odpowiedzi ma te same bajty (sha256 `d8fd43e62742...`; ADR-042 D5,
  ta sama wersja GDAL).

## 5. Sidecary wersji

| Plik (wersja) | `request` | `extra` (poza `version`) | `vertical_crs` |
|---|---|---|---|
| `landcover/pl_bdot10k_shp_2024/.../2024_5dbd678a/1261.zip` | `{teryt: "1261", format: "SHP", year: 2024}` | `source {url, edition: "2024"}`, `http {etag: null, last_modified: null, content_length: 47404309}` | `null` |
| `landcover/pl_bdot10k_shp_2023/.../2023_6c64b1d3/1261.zip` | `{teryt: "1261", format: "SHP", year: 2023}` | `source {url .../2023/SHP/..., edition: "2023"}`, `http` | `null` |
| `models3d/pl_buildings_lod1_2024/.../2024_dff392bb/1261.zip` | `{teryt: "1261", lod: 1, year: 2024}` | `source {url, edition: "2024"}`, `http` | `EPSG:9651` |
| `models3d/pl_buildings_lod2_2017/.../2017_de14ed18/1261.zip` | `{teryt: "1261", lod: 2}` (`year` nie podany - jedyne wydanie) | `source {url, edition: "2017"}`, `http`, `parent_request {bbox: [566000, 243000, 566500, 243500], bbox_crs: "EPSG:2180", countries: ["PL"]}` | `EPSG:9650` |
| `boundaries/pl_prg_gmina/.../550000_220000_590000_270000.gpkg` | `{bbox: [...], bbox_crs: "EPSG:2180", level: "gmina"}` | `source {service .../PRG/WFS/AdministrativeBoundaries, protocol: "wfs", layers: [{code: "gmina", source: "ms:A03_Granice_gmin", name: "A03_Granice_gmin", features: 39}]}` | `null` |
| `boundaries/pl_prg_gml/.../12.zip` | `{teryt: "12"}` | `source {url}`, `http` | `null` |
| `boundaries/pl_prg_shp/.../country/.../pl.zip` | `{whole_country: true}` | `source {url}`, `http {content_length: 377419459}` | `null` |
| `cadastre/pl_egib_gpkg/.../1261.gpkg` | `{teryt: "1261"}` | `source {url, member: "1261.gpkg"}`, `http {content_length: 87175594}` | `null` |
| `cadastre/pl_egib/.../565000_243000_567000_245000.gpkg` | `{bbox: [...], bbox_crs: "EPSG:2180"}` | `source {service .../EGIB/WFS/UslugaZbiorcza, protocol: "wfs", layers: dzialki 3306, budynki 2947, dropped_fields: {DATA: ["2026-10-15"]}}` | `null` |

`version`: `{label: <rok>, label_source: "edition"}` dla archiwum BDOT10k
i modeli 3D, `{label: "2026-10-15", label_source: "downloaded"}` dla PRG
i EGiB. Wszystkie: `horizontal_crs` EPSG:2180, `license` PL-PGiK-40a.
Sidecar sciezki standardowej = kopia sidecara wersji z `extra.link =
"hardlink"` i `extra.link_target` (np. `../versions/teryt/2022_6c64b1d3/1261.zip`).

## 6. Dowiazania twarde i D7

`stat -c %h` na tym udziale cifs nie jest wiarygodny: kolejne odczyty
tego samego pliku dawaly `1`, `1`, `2` w odstepach 2 s, a `stat -c %i`
daje rozne numery dla dowiazan tego samego pliku (i-wezly klienta, nie
serwera; patrz tez `docs/research/2026-10-15-project-e2e/raport.md`
sekcja 4). Dowod z serwera: `smbinfo fileallinfo <plik>` (`Index Number`
= identyfikator pliku na serwerze, `Number of Links`):

| Sciezki | Index Number | Number of Links |
|---|---|---|
| `landcover/pl_bdot10k_shp_2022/teryt/1261.zip`, `.../pl_bdot10k_shp_2022/versions/teryt/2022_6c64b1d3/1261.zip`, `.../pl_bdot10k_shp_2023/teryt/1261.zip`, `.../pl_bdot10k_shp_2023/versions/teryt/2023_6c64b1d3/1261.zip` | ten sam (jeden plik) | 4 |
| sciezka standardowa i wersja: BDOT10k SHP 2024, LoD1 2024, LoD2 2017, PRG gmin, PRG 12, EGiB 1261, EGiB obszaru | ta sama para (po jednym pliku na produkt) | 2 |

Rocznik 2023 powiatu 1261 (SHP) jest bajt w bajt rocznikiem 2022 (sha256
`6c64b1d33782...`, 46 762 581 B): zapis 2023 trafil do slotu pokrewnego
2022 (`FileSlot.related_roots`), wiec 2023 to hardlink do danych 2022 -
46,8 MB zajete raz (ADR-042 D7, kryterium akceptacji 3).

## 7. Dodatkowo

- **Obszar dwoch powiatow, archiwum GML, `--workers 2`:** `landcover
  download --source bdot10k --year 2018 --format GML --bbox
  557000,244000,559000,246000 --workers 2` (wiersz 2 matrycy planu): WFS PRG
  (N,E) -> 1206, 1261; rownolegle `1261_GML_2018.zip` (40 030 676 B)
  i `1206_GML_2018.zip` (72 324 406 B); linie w kolejnosci kodow
  (`.../teryt/1206.zip: nowa wersja 2018_b8b23714`, `.../teryt/1261.zip:
  nowa wersja 2018_f8f5ead1`) i `Nowe: 2, nowa etykieta: 0, bez zmian: 0,
  lokalne: 0, bledy: 0`, 30,2 s. Sidecar: `request {teryt, format: "GML",
  year: 2018}`, `extra.parent_request {bbox, bbox_crs, countries: ["PL"]}`.
  Powtorzenie: `lokalne: 2`, 0 zapytan.
- **Luki LoD2 (izolacja bledow jednostek):** `models3d download --product
  buildings --lod 2 --country pl --bbox 205000,633000,206000,635000`
  (Szczecin i sasiedni powiat): `Info: buildings: powiaty obszaru wg PRG
  (2): 3211, 3262`, `GET .../LOD2/3211_gml.zip` i `.../3262_gml.zip` -> 404,
  `Nowe: 0, ..., bledy: 2`, `Error: 3211: Zrodlo nie publikuje paczki ...
  (HTTP 404)`, `Error: 3262: ...`, kod 1, brak plikow i katalogow wersji.
- **PRG `--whole-country` (377 MB, swiadomie):** `HEAD
  .../prg/granice/00_jednostki_administracyjne.zip` (377 419 459 B), potem
  `Warning: admin PL: plik krajowy ... - 377419459 B (ok. 377 MB)` i GET;
  `boundaries/pl_prg_shp/country/pl.zip: nowa wersja 2026-10-15_40b93870`,
  149,1 s. Powtorzenie: `lokalna wersja`, 0 zapytan, 3,9 s (potwierdzenie
  dowiazania trescia na cifs).
- **Bledy wyboru (CLI, bez sieci, kod 1 albo 2):**

| Polecenie | Wynik |
|---|---|
| `boundaries download --product admin --teryt 1261` | `Error: --teryt 1261: admin nie ma paczek powiatow; dostepne: --bbox/--sheet/--geometry (obiekty obszaru), --teryt <2 cyfry> (paczka wojewodztwa), --whole-country (plik krajowy)` |
| `cadastre download --product map --teryt 12` | przed poprawka - sekcja 8; po: `Error: --teryt 12: map nie ma paczek wojewodztw; dostepne: --teryt <4 cyfry> (paczka powiatu), --bbox/--sheet/--geometry (obiekty obszaru)` |
| `models3d download --product buildings --lod 1 --year 2024 --country pl --whole-country` | blad parsera `unrecognized arguments: --whole-country`, kod 2 (grupa nie ma tej flagi - flagi tylko swoje) |
| `landcover download --source bdot10k --teryt 1261 --year 2024` | `Error: --format wymagane dla --year 2024: GML, SHP` |
| `landcover download --source bdot10k --teryt 1261 --format GML` | `Error: --format GML: biezace paczki BDOT10k to GPKG albo SHP; GML tylko z --year (archiwum rocznikow)` |
| `models3d download --product buildings --teryt 1261` | `Error: --lod wymagane: 1, 2` |
| `models3d download --product buildings --lod 2 --year 2018 --teryt 1261` | `Error: --year 2018: niedostepne dla --lod 2; dostepne: 2017` |
| `boundaries download --product admin --country pl --bbox ...` | `Error: --level wymagane dla obszaru admin (PL): wojewodztwo, powiat, gmina, jednostka-ewidencyjna, obreb` |
| `boundaries download --product admin --teryt 12 --level gmina` | `Error: --level dotyczy obiektow obszaru (--bbox/--sheet/--geometry), nie paczek admin` |

## 8. Znaleziony blad i poprawka

`cadastre download --product map --teryt 12` (przed poprawka) konczyl sie
`Error: --teryt 12: map nie ma paczek wojewodztw; dostepne: --teryt <4
cyfry> (paczka powiatu), --bbox/--sheet/--geometry (paczki powiatow
obszaru), --bbox/--sheet/--geometry (obiekty obszaru)` - ta sama flaga
z dwoma znaczeniami, a pierwsze nieprawdziwe: obszar EGiB zawsze idzie do
uslugi WFS (kanal `feature_bbox` ma pierwszenstwo, ADR-042 D2). Poprawka
`download/collections.py::_available` (podpowiedz wymienia kanal, ktory
`_channel_for` wybiera dla obszaru) z testem regresji
`tests/test_collections.py::test_selection_hint_names_what_an_area_downloads`
(czerwony przed poprawka, zielony po); prawdziwe CLI po poprawce - tabela
w sekcji 7. Brama po poprawce: 3987 passed, 18 deselected; ruff, ruff
format i mypy bez bledow.

## 9. Projekt i API

```bash
kartograf project init --project <katalog-danych>/project-smoke --output <katalog-danych>/store
kartograf project add --project <katalog-danych>/project-smoke granice boundaries download --product admin --teryt 12
kartograf project add --project <katalog-danych>/project-smoke gminy boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000
kartograf project add --project <katalog-danych>/project-smoke egib cadastre download --product map --country pl --bbox 565000,243000,567000,245000
kartograf project add --project <katalog-danych>/project-smoke lod1 models3d download --product buildings --lod 1 --year 2024 --teryt 1261
kartograf project add --project <katalog-danych>/project-smoke lod2 models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500
kartograf project add --project <katalog-danych>/project-smoke bdot landcover download --source bdot10k --teryt 1261 --year 2023 --format SHP
kartograf project add --project <katalog-danych>/project-smoke zly cadastre download --product map --teryt 12
kartograf project download --project <katalog-danych>/project-smoke
kartograf project status --project <katalog-danych>/project-smoke
kartograf project verify --project <katalog-danych>/project-smoke
kartograf project download --project <katalog-danych>/project-smoke --check-updates
```

- 6 x `Dodano zadanie <nazwa> (<komenda>)`, kod 0, bez sieci; `zly`:
  `Error: --teryt 12: map nie ma paczek wojewodztw; ...` (kod 1, zadanie
  nie dodane).
- `download` (kod 0, 3,4 s): `przypieto` 6 zadan (`granice: 12: przypieto
  2026-10-15`, ..., `lod1: 1261: przypieto 2024`, `lod2: 1261: przypieto
  2017`, `bdot: 1261: przypieto 2023`), `Projekt: przypiete 6, odtworzone
  0, ...`; jedyne zapytanie - WFS PRG dla `lod2` (projekt pracuje domyslnie
  bez cache metadanych, `cache=False`), zero pobran danych (wersje z sekcji
  1).
- `status` i `verify`: 6 x `<zadanie>: <jednostka>: ok`, kod 0;
  `--check-updates`: 6 x `nie da sie sprawdzic bez pobrania (--force)`.

API (ten sam magazyn, z korzenia worktree, licznik HTTP):
`download_collection(product="admin", teryt="12")`, `(product="admin",
country="pl", level="gmina", bbox=...)`, `(product="map", country="pl",
bbox=...)`, `(product="map", teryt="1261")`, `(product="buildings",
teryt="1261", lod=1, year=2024)`, `(product="buildings", lod=2,
country="pl", bbox=...)` - te same sciezki co CLI, status `local`,
etykiety jak w sekcji 5, `ok=True`, przy LoD2 `Notice("info", "unit_list",
"buildings: powiaty obszaru wg PRG (1): 1261")`;
`check_collection(product="buildings", teryt="1261", lod=1, year=2024)` ->
`[("collection", "1261", "unverifiable", "2024")]`;
`LandCoverManager(<magazyn>, "bdot10k").download(teryt="1261", year=2023,
format="SHP")` -> `landcover/pl_bdot10k_shp_2023/teryt/1261.zip`, `local`,
`2023`; `validate_collection_request(product="map", teryt="12")` ->
`ValidationError` z tekstem jak CLI. Lacznie 0 zapytan HTTP.

## 10. Uwagi

- Strony WFS GUGiK: 1,9-4,4 s na strone 1000 obiektow (EGiB, PRG),
  zapytania metadanych (`GetCapabilities`, `hits`, `DescribeFeatureType`)
  0,2-2,1 s; limit jednego zapytania to 60 s (`SERVICE_TIMEOUT`).
- Plik krajowy PRG: 149 s na 377 MB (ok. 2,5 MB/s: transfer i zapis).
- Na udziale cifs bez stabilnych i-wezlow uzycie lokalnej wersji czyta
  caly plik dowiazania (potwierdzenie trescia) - 284 MB EGiB = 2,9 s,
  377 MB PRG = 3,9 s; na ext4/NTFS to `samefile` bez odczytu.
- Magazyn po przebiegu: 12 wersji, 11 plikow danych na serwerze (2023 =
  2022), 984 417 233 B danych (bez sidecarow).
