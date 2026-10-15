# E2E manifestu projektu na zywo (plan manifestu, Task 10)

Data: 2026-10-15. Galaz `feat/project-manifest`, commit `6fb962a` (czyste
drzewo; `kartograf --version` = `kartograf 0.8.0-dev+6fb962a`). CLI: entry
point `.venv/bin/kartograf` z `PYTHONPATH=<korzen worktree>` (import kodu
worktree sprawdzony wersja), uruchamiany z korzenia worktree (STANDARDS 6.4);
projekty i magazyny wylacznie w `<katalog-danych>` (udzial SMB 3.1.1, cifs
z `serverino`; dowiazania twarde i atomowe `mkdir` dzialaja), kazde polecenie
z jawnym `--project` i `--output` (`init`). Polecenia sekwencyjnie. CLMS bez
credentials - pominiety (CORINE nie wchodzi do scenariuszy specu 7). Kodu nie
zmieniano.

"Z licznikiem HTTP" oznacza to samo `kartograf.cli.commands.main(argv)`
uruchomione przez `python -c` z opakowaniem `requests.adapters.HTTPAdapter.send`,
ktore wypisuje metode, status, `Content-Length` i URL kazdego zapytania
(caly ruch HTTP Kartografa idzie przez `requests`: `transport/http.py`,
`download_to`, `session.get`/`head`).

Przebieg wstepny na `4bd9fff` + niezacommitowanych zmianach Task 7-8 (pozniej
`4fc080b`, `4a586cf`) dal te same wyniki; raport opisuje przebieg koncowy na
`6fb962a`, a z przebiegu wstepnego podaje tylko roznice (rsync, sekcja 4).

## Wynik

| # | Scenariusz (spec 7) | Wynik |
|---|---|---|
| 1 | Projekt A: NMT PL arkusz 1 m, BDOT10k powiat, SoilGrids + HSG maly arkusz, SM5 CZ; `download`, `status`, `verify` | PASS: 5 zadan przypietych (8 przypiec, 7 roznych wersji), 21,5 s; `status` i `verify` 8 x `ok`, kod 0 |
| 2 | Projekt B na tym samym magazynie, to samo zadanie NMT | PASS: przypiete bez pobierania (3 zapytania o skorowidz, 0 pobran danych), magazyn bez zmian, przypiecia identyczne z A; ponowne `download` = `bez zmian`, 0 zapytan |
| 3 | `download --check-updates` w A | PASS: NMT `aktualne` (sygnal `index`), SM5 `aktualne` (`http`: ETag), SoilGrids i wejscia HSG `aktualne` (`metadata`: wydanie 2.0), HSG `aktualne`, BDOT10k `nie da sie sprawdzic bez pobrania (--force)`; 8 zapytan o metadane, 0 pobran, magazyn i manifest bez zmian |
| 4a | Kopia magazynu `rsync -aH`, nowy `output_dir`, `verify` | PASS: 8 x `ok`; OGRANICZENIE: na tym udziale `rsync -aH` nie zawsze odtwarza dowiazania twarde (kopia poprawna, ale wieksza) - sekcja 4 |
| 4b | Projekt z pustym magazynem: `download` -> `restored` | PASS: `odtworzone 5`, 6 pobran danych, magazyn identyczny z oryginalem (30 sciezek, 22 pliki, 49 582 135 B), manifest bez zmian, `verify` 8 x `ok` |
| + | Dodatkowo: `add` (4 komendy danych) i `remove`, `--upgrade` bez nowszych danych, `--force` dla toru bez sygnalu, brak katalogu magazynu, uszkodzony bajt w kopii | PASS: `add` 0 zapytan, blad wyboru SM5 przed siecia, `add`+`remove` = manifest bajt w bajt; 5 x `bez zmian` + `Info:` BDOT10k; `--force` ta sama tresc = `bez zmian`; `Error:` bez sieci; `verify` wykrywa zmiane 1 bitu, `status` nie (zgodnie ze specem 4.9) |
| smoke | Smoke offline prawdziwego CLI (plan Task 10) | PASS: `init`, `add` (+ bledy), `download`, `status`, `verify`, `--check-updates`, drugi projekt z nowsza wersja, `--upgrade`, odtwarzanie, konflikt tresci - sekcja 6 |

## Wybor obszarow (najmniejsze realne pobrania)

- NMT PL 1 m: arkusz 1:5000 `M-34-64-D-d-1-2` (Krakow), lot `83137`
  (2025-04-28), plik ASC 37 004 903 B. Ta sama suma `e041a794...` co probka
  z 2026-10-13 (`docs/research/2026-10-13-katalog-produktow/probki.md`).
- BDOT10k: powiat `2476` (Swietochlowice) - najmniejsza paczka GPKG sposrod
  sprawdzonych miast na prawach powiatu (`HEAD` paczek `schemat2021/GPKG`:
  2476 - 3 421 022 B, 2474 - 4 705 002 B, 2264 - 5 101 215 B, 2463 -
  5 847 173 B, 2471 - 6 529 121 B; bez `ETag` i `Last-Modified`). Plik GPKG
  w magazynie: 11 771 904 B.
- SoilGrids + HSG: arkusz 1:10000 `M-34-64-D-d-1` (zawiera arkusz NMT),
  glebokosc `0-5cm`; rastry 883-1158 B. Zadanie `gleby-il` (`clay 0-5cm
  mean`) i wejscie `clay` zadania `gleby-hsg` to ta sama wersja w magazynie.
- CZ: arkusz SM5 `CTES96` (DMR 4G 5 m, `Bpv`), ZIP z openzu 752 795 B, plik
  TIFF 780 401 B. Ta sama suma `a1e327bb...` co w E2E magazynu z 2026-10-12
  (`docs/research/2026-10-12-store-e2e/raport.md`, etykieta wtedy
  `2026-10-12`).

## 1. Projekt A: `init`, `add`, `download`, `status`, `verify`

```bash
kartograf project init --project <katalog-danych>/projekty/a --output <katalog-danych>/magazyn
kartograf project add --project <katalog-danych>/projekty/a teren elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution 1m --vertical-crs EVRF2007
kartograf project add --project <katalog-danych>/projekty/a pokrycie landcover download --source bdot10k --teryt 2476
kartograf project add --project <katalog-danych>/projekty/a gleby-il soil download --sheet M-34-64-D-d-1 --property clay --depth 0-5cm --stat mean
kartograf project add --project <katalog-danych>/projekty/a gleby-hsg soil hsg --sheet M-34-64-D-d-1 --depth 0-5cm
kartograf project add --project <katalog-danych>/projekty/a teren-cz elevation download --sheet CTES96 --product nmt --vertical-crs Bpv
kartograf project status --project <katalog-danych>/projekty/a
kartograf project download --project <katalog-danych>/projekty/a
kartograf project status --project <katalog-danych>/projekty/a
kartograf project verify --project <katalog-danych>/projekty/a
```

- `init`: `Utworzono projekt: <katalog-danych>/projekty/a/kartograf-project.json`,
  `Magazyn: <katalog-danych>/magazyn`, podpowiedz `project add`; kod 0.
- Kazde `add`: `Dodano zadanie <nazwa> (<komenda>); pobierz: kartograf
  project download <nazwa>`, kod 0, 0,5-0,6 s, bez sieci (sekcja 2b). W `options`
  zapisane tylko podane flagi (np. `teren-cz`: `product`, `sheet`,
  `vertical_crs` - bez `resolution`, ktorej uzytkownik nie podal; `pokrycie`:
  `source`, `teryt` - bez domyslnego `format`).
- `status` przed pobraniem: 5 x `Error: <zadanie>: zadanie nie pobrane`, kod 1.
- `download` (kod 0, 21,5 s; w przebiegu wstepnym 43,3 s):

```text
Pobieranie M-34-64-D-d-1-2 (resolution: 1m)...
Pobieranie CTES96 (CZ, resolution: 5m)...
teren: przypieto (1 plik)
teren: M-34-64-D-d-1-2: przypieto 2025-04-28_83137
pokrycie: przypieto (1 plik)
pokrycie: 2476: przypieto 2026-10-15
gleby-il: przypieto (1 plik)
gleby-il: M-34-64-D-d-1: przypieto 2.0
gleby-hsg: przypieto (4 pliki)
gleby-hsg: M-34-64-D-d-1: przypieto 2.0
gleby-hsg: clay M-34-64-D-d-1: przypieto 2.0
gleby-hsg: sand M-34-64-D-d-1: przypieto 2.0
gleby-hsg: silt M-34-64-D-d-1: przypieto 2.0
teren-cz: przypieto (1 plik)
teren-cz: CTES96: przypieto 2026-10-15
Projekt: przypiete 5, odtworzone 0, zaktualizowane 0, bez zmian 0, bledy 0
```

- Magazyn po pobraniu: 30 sciezek (15 plikow danych + 15 sidecarow),
  22 unikalne pliki (i-wezly), 49 582 135 B; dowiazania twarde sciezka
  standardowa - wersja (NMT takze `full_sheet/`).
- `status` (0,5 s) i `verify` (0,9 s, pelne SHA-256 49,6 MB na udziale SMB):
  naglowki zadan (`teren  elevation download  1 plik  przypiete
  2026-10-15T19:29:38+00:00`, `gleby-hsg  soil hsg  4 pliki  ...`) i 8 linii
  `<zadanie>: <jednostka>: ok`, kod 0. Manifest bez zmian (bajt w bajt).
- Przypiecia (identyczne `sha256`, `size_bytes`, `label` i `version`
  w przebiegu wstepnym i koncowym):

| Zadanie | Rola | Jednostka (`unit`) | Segment magazynu | Etykieta | sha256 (8) | Rozmiar [B] |
|---|---|---|---|---|---|---|
| `teren` | output | `M-34-64-D-d-1-2` | `nmt/pl_1992_1m_evrf2007` | `2025-04-28_83137` | `e041a794` | 37 004 903 |
| `pokrycie` | output | `2476` | `landcover/pl_bdot10k_gpkg` | `2026-10-15` | `ebfdf70e` | 11 771 904 |
| `gleby-il` | output | `M-34-64-D-d-1` | `soil/global_soilgrids_clay_0-5cm_mean` | `2.0` | `58790ca2` | 883 |
| `gleby-hsg` | output | `M-34-64-D-d-1` | `hsg/global_soilgrids_0-5cm_mean` | `2.0` | `e9660dcc` | 1158 |
| `gleby-hsg` | input | `clay M-34-64-D-d-1` | `soil/global_soilgrids_clay_0-5cm_mean` | `2.0` | `58790ca2` | 883 |
| `gleby-hsg` | input | `sand M-34-64-D-d-1` | `soil/global_soilgrids_sand_0-5cm_mean` | `2.0` | `ba3e5839` | 911 |
| `gleby-hsg` | input | `silt M-34-64-D-d-1` | `soil/global_soilgrids_silt_0-5cm_mean` | `2.0` | `d5eb7332` | 923 |
| `teren-cz` | output | `CTES96` | `nmt/cz_dmr4g_bpv` | `2026-10-15` | `a1e327bb` | 780 401 |

Zadanie `teren` w pliku (sciezki przypiec wzgledne do magazynu):

```json
{
  "name": "teren",
  "command": "elevation download",
  "options": {
    "product": "nmt",
    "sheet": "M-34-64-D-d-1-2",
    "resolution": "1m",
    "vertical_crs": "EVRF2007"
  },
  "pinned_at": "2026-10-15T19:29:38+00:00",
  "kartograf_version": "0.8.0-dev+6fb962a",
  "files": [
    {
      "role": "output",
      "unit": "M-34-64-D-d-1-2",
      "path": "nmt/pl_1992_1m_evrf2007/M-34/64/D/d/1/2/M-34-64-D-d-1-2.asc",
      "version": "nmt/pl_1992_1m_evrf2007/versions/M-34/64/D/d/1/2/2025-04-28_83137_e041a794/M-34-64-D-d-1-2.asc",
      "label": "2025-04-28_83137",
      "sha256": "e041a79460a15571b5345884c22d82840f9c2dcfcfd666ba5c3f06a4a2e4a630",
      "size_bytes": 37004903
    }
  ]
}
```

## 2. Projekt B na tym samym magazynie

```bash
kartograf project init --project <katalog-danych>/projekty/b --output <katalog-danych>/magazyn
kartograf project add --project <katalog-danych>/projekty/b teren elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution 1m --vertical-crs EVRF2007
kartograf project download --project <katalog-danych>/projekty/b     # z licznikiem HTTP
kartograf project download --project <katalog-danych>/projekty/b     # z licznikiem HTTP
kartograf project verify --project <katalog-danych>/projekty/b
```

- Pierwsze `download` (kod 0, 1,2 s): `teren: przypieto (1 plik)`,
  `teren: M-34-64-D-d-1-2: przypieto 2025-04-28_83137`. Zapytania (3, same
  metadane): `GET SkorowidzeUkladEVRF2007 GetCapabilities`, `GetFeatureInfo`
  warstw `SkorowidzeNMT2026` i `SkorowidzeNMT2025` (2532, 2456, 2988 B).
  Zero pobran danych; magazyn przed i po: 30 sciezek, 22 pliki,
  49 582 135 B.
- `files[]` zadania `teren` w B rowne `files[]` w A (ta sama wersja,
  etykieta, suma i rozmiar); manifest A bez zmian.
- Drugie `download`: `teren: bez zmian`, `Projekt: ... bez zmian 1, bledy 0`,
  0 zapytan (zadanie przypiete z kompletem wersji nie siega do sieci).
- `verify`: `teren: M-34-64-D-d-1-2: ok`, kod 0.

### 2b. `add` i `remove` bez sieci (na projekcie B)

```bash
kartograf project add --project <katalog-danych>/projekty/b pokrycie landcover download --source bdot10k --teryt 2476                                    # z licznikiem HTTP
kartograf project add --project <katalog-danych>/projekty/b gleby-il soil download --sheet M-34-64-D-d-1 --property clay --depth 0-5cm --stat mean     # z licznikiem HTTP
kartograf project add --project <katalog-danych>/projekty/b gleby-hsg soil hsg --sheet M-34-64-D-d-1 --depth 0-5cm                                      # z licznikiem HTTP
kartograf project add --project <katalog-danych>/projekty/b teren-cz elevation download --sheet CTES96 --product nmt --vertical-crs Bpv                  # z licznikiem HTTP
kartograf project add --project <katalog-danych>/projekty/b zly-cz elevation download --sheet CTES96 --product nmt --vertical-crs Bpv --resolution 2m   # z licznikiem HTTP
kartograf project remove --project <katalog-danych>/projekty/b pokrycie      # i tak samo gleby-il, gleby-hsg, teren-cz
kartograf project download --check-updates --project <katalog-danych>/projekty/b nieznane
```

- Cztery `add` komend `landcover download`, `soil download`, `soil hsg`
  i `elevation download` (CZ): `Dodano zadanie ...`, kod 0, 0 zapytan HTTP.
- `add zly-cz ... --resolution 2m`: `Error: Arkusze SM5 sa dostepne tylko
  w 5m (DMR 4G) - pomin --resolution albo podaj 5m; dla 2m uzyj godla TM33
  albo --bbox [arkusz: CTES96]`, kod 1, 0 zapytan, zadanie nie dodane.
- Kazde `remove`: `Usunieto zadanie <nazwa>; pliki zostaly w magazynie`,
  kod 0. Manifest B po czterech `add` i czterech `remove` jest bajt w bajt
  taki jak przed nimi (postac kanoniczna); magazyn bez zmian.
- Nieznane zadanie: `Error: nieznane zadanie 'nieznane'; zadania projektu:
  teren`, kod 1.

## 3. `download --check-updates` w A

```bash
kartograf project download --check-updates --project <katalog-danych>/projekty/a
kartograf project download --check-updates --project <katalog-danych>/projekty/a     # z licznikiem HTTP
kartograf project download --check-updates --project <katalog-danych>/projekty/a pokrycie teren-cz
kartograf project download --check-updates --project <katalog-danych>/projekty/a -q
```

```text
teren: M-34-64-D-d-1-2: aktualne
pokrycie: 2476: nie da sie sprawdzic bez pobrania (--force)
gleby-il: M-34-64-D-d-1: aktualne
gleby-hsg: clay M-34-64-D-d-1: aktualne
gleby-hsg: sand M-34-64-D-d-1: aktualne
gleby-hsg: silt M-34-64-D-d-1: aktualne
gleby-hsg: M-34-64-D-d-1: aktualne
teren-cz: CTES96: aktualne
```

Kod 0 (4,2 s i 1,8 s); wybor zadan `pokrycie teren-cz` daje tylko ich dwie
linie; `-q` - pusty wydruk, kod 0. Magazyn przed i po obu sprawdzeniach:
30 sciezek, 22 pliki, 49 582 135 B; manifest A bez zmian (bajt w bajt).

Sygnaly torow. Kolumny "tor" i "sygnal" pochodza z diagnostycznego wywolania
tej samej funkcji `check` pozycji `kartograf/project/commands.py`, ktorej
uzywa `check_project` (wypisane `PlanItem.track`, `status`,
`available_signal`); kolumna "zapytania" - z przebiegu CLI z licznikiem HTTP.

| Zadanie | Tor | Zapytania (8 lacznie) | Sygnal | Status |
|---|---|---|---|---|
| `teren` | `pl_sheet` | WMS skorowidza: `GetCapabilities` + 2 x `GetFeatureInfo` (2026, 2025) | rekord skorowidza: `.../NMT/83137/83137_1729552_M-34-64-D-d-1-2.asc`, `date` 2025-04-28, `pzgik_date` 2025-11-07 | `aktualne` |
| `pokrycie` | `landcover` (BDOT10k) | 0 | brak taniego sygnalu | `nie da sie sprawdzic bez pobrania (--force)` |
| `gleby-il` | `landcover` (SoilGrids) | WCS `GetCapabilities` `clay.map` | `edition` 2.0 | `aktualne` |
| `gleby-hsg` | 3 x `landcover` + `hsg` | WCS `GetCapabilities` `clay.map`, `sand.map`, `silt.map` | wejscia: `edition` 2.0; HSG: porownanie z wejsciami (`available_signal` puste) | `aktualne` x 4 |
| `teren-cz` | `cz_sheet` | `HEAD` openzu `DMR4G-TIFF/epsg-5514/CTES96.zip` | `etag` `"d19f2c604d89dc1:0"`, `last_modified` Mon, 19 Jan 2026 14:10:33 GMT, `content_length` 752795 | `aktualne` |

Zadne zapytanie nie bylo `GetCoverage` ani pobraniem pliku danych.

### 3b. Dodatkowo: `--upgrade` bez nowszych danych i `--force` toru bez sygnalu

```bash
kartograf project download --upgrade --project <katalog-danych>/projekty/a                  # z licznikiem HTTP
kartograf project download --force --project <katalog-danych>/projekty/a pokrycie teren-cz  # z licznikiem HTTP
kartograf project verify --project <katalog-danych>/projekty/a -q
```

- `--upgrade` (kod 0, 2,2 s): 5 x `<zadanie>: bez zmian`, `Projekt: ...
  bez zmian 5, bledy 0`, na stderr `Info: pokrycie:
  landcover/pl_bdot10k_gpkg/teryt/2476.gpkg: lokalna wersja 2026-10-15
  niesprawdzona - zrodlo bez taniego sygnalu; pobierz ponownie: --force`.
  Te same 8 zapytan o metadane co `--check-updates`, 0 pobran; magazyn
  i manifest bez zmian.
- `--force pokrycie teren-cz` (kod 0, 11,0 s): pobrane ponownie paczka
  `2476_GPKG.zip` (3 421 022 B) i `CTES96.zip` (752 795 B) oraz zapytanie
  o arkusz SM5 (`KladyMapovychListu/MapServer/24/query`, 381 B);
  `pokrycie: bez zmian`, `teren-cz: bez zmian` - ta sama tresc nie tworzy
  nowej wersji ani nowego przypiecia (spec 6 pkt 7). Magazyn: 30 sciezek,
  22 pliki, 49 582 135 B (bez zmian), manifest bez zmian, `verify -q` kod 0.

## 4. Kopia magazynu `rsync -aH`, nowy `output_dir`, `verify`

```bash
rsync -aH <katalog-danych>/magazyn/ <katalog-danych>/magazyn-kopia/
# kopia manifestu A do <katalog-danych>/projekty/a-kopia/ z jedna zmieniona linia:
#   "output_dir": "<katalog-danych>/magazyn-kopia",
kartograf project status --project <katalog-danych>/projekty/a-kopia -q
kartograf project verify --project <katalog-danych>/projekty/a-kopia
```

- `rsync` kod 0 (4,6 s); `status -q` kod 0 bez wydruku; `verify`: 5 naglowkow
  zadan i 8 x `ok`, kod 0 (1,0 s); manifest kopii bez zmian po `verify`.
- Dodatkowo `verify` wykrywa uszkodzenie, a `status` nie (rozmiar ten sam):
  po odwroceniu jednego bitu w srodku pliku wersji `CTES96.tif` w kopii
  (osobny i-wezel, oryginal nietkniety) `kartograf project status --project
  <katalog-danych>/projekty/a-kopia teren-cz` daje `teren-cz: CTES96: ok`
  (kod 0), a `kartograf project verify --project
  <katalog-danych>/projekty/a-kopia teren-cz` - `Error: teren-cz: CTES96:
  uszkodzony przypiety plik: suma SHA-256 danych jest inna niz przypieta;
  przywroc katalog wersji z kopii magazynu` (kod 1). Po przywroceniu bajtu
  `verify -q` kod 0; suma pliku w oryginale nadal `a1e327bb...`.

**Ograniczenie: dowiazania twarde w kopii na udziale SMB.** `rsync -H`
traktuje jako dowiazania tylko pliki z `st_nlink > 1`, a klient cifs tego
udzialu raportuje `st_nlink = 1` dla dowiazanych plikow (i-wezly nadal
wspolne) przez kilka sekund po odczycie pliku. Test na dwoch plikach
w `<katalog-danych>`: plik i dowiazanie bez odczytu - `nlink=2` przez 33 s
(po zmianie nazwy dowiazania: nadal 2 po 3 s); po `cat a` i 2 s - `stat a`
daje `nlink=1`, a `stat b` `nlink=2` (ten sam i-wezel); po kolejnych 10 s oba 2.
Wynik kopii zalezy wiec od tego, co czytalo magazyn tuz przed `rsync`:

| Kopia | Moment | Pliki unikalne | Bajty | `verify` |
|---|---|---|---|---|
| przebieg wstepny | po `verify` projektu B, dwoch `--check-updates` i diagnostyce sygnalow | 22 (dowiazania zachowane) | 49 582 225 | 8 x `ok` |
| `magazyn-kopia` | zaraz po `verify -q` (odczyt wszystkich przypietych plikow) | 30 (zadne dowiazanie) | 136 148 121 | 8 x `ok` |
| `magazyn-kopia-2` | pozniej, po pierwszej kopii (`rsync` czyta kazdy plik); `find` tuz przed nia: `nlink=3` tylko dla trojki NMT | 28 (tylko trojka NMT) | 62 138 315 | 8 x `ok` |

Kopia jest zawsze poprawna dla projektu (przypiecia wskazuja pliki wersji,
sumy zgodne), ale sciezki standardowe przestaja byc dowiazaniami wersji
i kopia zajmuje do 2,75 x wiecej miejsca. Rekomendacja dla dokumentacji
przenoszenia magazynu (spec 3.2, USAGE): uwaga, ze na udzialach SMB/cifs
`rsync -aH` moze nie zachowac dowiazan twardych - kopiowac po stronie
serwera albo z hosta z lokalnym dostepem do systemu plikow i sprawdzic
zajetosc kopii.

## 5. Kolega z pustym magazynem: odtworzenie (`restored`)

```bash
# kopia manifestu A do <katalog-danych>/projekty/c/ z jedna zmieniona linia:
#   "output_dir": "<katalog-danych>/magazyn-pusty",
kartograf project download --project <katalog-danych>/projekty/c      # z licznikiem HTTP; katalogu magazynu jeszcze nie ma
mkdir <katalog-danych>/magazyn-pusty
kartograf project status --project <katalog-danych>/projekty/c
kartograf project download --project <katalog-danych>/projekty/c      # z licznikiem HTTP
kartograf project verify --project <katalog-danych>/projekty/c
kartograf project download --project <katalog-danych>/projekty/c -q
```

- Bez katalogu magazynu: `Error: magazyn projektu nie istnieje:
  <katalog-danych>/magazyn-pusty; podlacz udzial albo popraw output_dir
  w kartograf-project.json`, kod 1, 0 zapytan, katalog nie zostal utworzony.
- `status` na pustym magazynie: naglowki 5 zadan i 8 x `Error: <zadanie>:
  <jednostka>: brak przypietego pliku w magazynie: brak przypietej wersji;
  przywroc kopie magazynu albo uruchom kartograf project download
  <zadanie>`, kod 1.
- `download` (kod 0, 21,5 s):

```text
Pobieranie M-34-64-D-d-1-2 (resolution: 1m)...
Pobieranie CTES96 (CZ, resolution: 5m)...
teren: odtworzono (1 plik)
teren: M-34-64-D-d-1-2: przypieto 2025-04-28_83137
pokrycie: odtworzono (1 plik)
pokrycie: 2476: przypieto 2026-10-15
gleby-il: odtworzono (1 plik)
gleby-il: M-34-64-D-d-1: przypieto 2.0
gleby-hsg: odtworzono (3 pliki)
gleby-hsg: M-34-64-D-d-1: przypieto 2.0
gleby-hsg: sand M-34-64-D-d-1: przypieto 2.0
gleby-hsg: silt M-34-64-D-d-1: przypieto 2.0
teren-cz: odtworzono (1 plik)
teren-cz: CTES96: przypieto 2026-10-15
Projekt: przypiete 0, odtworzone 5, zaktualizowane 0, bez zmian 0, bledy 0
```

  `gleby-hsg` odtworzyl 3 pliki - wejscie `clay` odtworzylo juz zadanie
  `gleby-il` (ta sama wersja). 15 zapytan, w tym 6 pobran danych:
  `83137_1729552_M-34-64-D-d-1-2.asc` (37 004 903 B), `2476_GPKG.zip`
  (3 421 022 B), 3 x WCS `GetCoverage` (`clay`, `sand`, `silt`
  `0-5cm_mean`), `CTES96.zip` (752 795 B); reszta: skorowidz NMT (3),
  `GetCapabilities` SoilGrids (4), arkusz SM5 (2).
- Nowy magazyn: 30 sciezek, 22 pliki, 49 582 135 B - jak oryginal;
  manifest C bez zmian (bajt w bajt): sciezki wersji i etykiety takie same,
  bo odtworzenie bylo tego samego dnia. `verify` 8 x `ok`, kod 0; ponowne
  `download -q` kod 0 (bez zmian).
- W przebiegu wstepnym magazyn A pobral kod `4bd9fff` + zmiany, a odtworzyl
  kod `6fb962a`: te same sumy wszystkich 8 przypiec; sidecary roznily sie
  tylko `downloaded_at` i `kartograf_version`.

## 6. Smoke offline prawdziwego CLI

Skrypt tymczasowy poza repo (w `<katalog-danych>`, usuniety po przebiegu
razem z danymi smoke w `<smoke>` = `<katalog-danych>/smoke/run`):
prawdziwe `kartograf.cli.commands.main` i prawdziwy magazyn; zrodlo arkuszy PL
= `tests/test_manager_campaigns.py::FakeCampaignProvider` przez
`tests/project_fixtures.py::pl_sheets` (patch
`kartograf.download.data._create_provider_and_storage`); kazde
`socket.connect` poza petla zwrotna konczylo sie wyjatkiem (zadne nie
wystapilo). Arkusz `N-34-139-C-a-3-1`, loty `83233` (2025-04-27) i `84183`
(2025-10-21). Przebieg na `6fb962a`, 3,6 s. Pierwszy przebieg (przed
commitem `4a586cf`) wykazal dwie usterki wydruku, poprawione przed commitem:
`1 plikow` w naglowkach i liniach `download` oraz `(0 plikow)` przy
`bez zmian`/`blad`.

| Krok | Wynik |
|---|---|
| `init`, ponowny `init` | manifest + katalog magazynu; `Error: projekt juz istnieje: <smoke>/projekty/a/kartograf-project.json`, kod 1, manifest bez zmian |
| `add teren elevation download ...` | `Dodano zadanie teren (elevation download); pobierz: kartograf project download teren` |
| `add` bez `--vertical-crs` | `Error: --vertical-crs wymagane dla --product nmt (PL): EVRF2007 (...), KRON86 (...)` - tekst identyczny z `ValidationError` z `download_data` (sprawdzone bez sieci), kod 1 |
| `add ... --upgrade` | `Error: --upgrade nie jest czescia zadania; aktualizacja projektu: kartograf project download --upgrade tryb`, kod 1 |
| `add lista elevation availability ...` | `Error: do projektu mozna dodac komendy zapisujace dane: elevation download, imagery download, landcover download, soil download, soil hsg`, kod 1 |
| `status` przed pobraniem | `Error: teren: zadanie nie pobrane`, kod 1 |
| `download` (zrodlo: lot 83233) | `teren: przypieto (1 plik)`, `przypieto 2025-04-27_83233`; 1 pobranie; JSON na dysku: kolejnosc kluczy specu 3.3, `path`/`version` wzgledne, `sha256`, `size_bytes` 147, `pinned_at`, `kartograf_version` |
| `status`, `verify`, ponowne `download`, `--check-updates` | `ok`, `ok`, `teren: bez zmian`, `teren: N-34-139-C-a-3-1: aktualne`; lacznie nadal 1 pobranie; manifest bez zmian |
| projekt B, ten sam magazyn, zrodlo: lot 84183; `download --upgrade` | `przypieto 2025-10-21_84183` (1 pobranie) |
| `verify` A | `ok` - przypiecie A bez zmian, choc sciezka standardowa wskazuje juz 84183; manifest A bez zmian |
| `--check-updates` A | `teren: N-34-139-C-a-3-1: nowsza: 2025-10-21_84183 (przypieta 2025-04-27_83233): nowsza wersja w magazynie albo u zrodla; uruchom kartograf project download --upgrade teren` |
| `--upgrade` A | `teren: zaktualizowano (1 plik)`, `przypieto 2025-10-21_84183`; 0 nowych pobran (wersja z magazynu), 8 plikow magazynu przed i po |
| manifest A + pusty magazyn (projekt C): `status`, `download`, `verify` | `brak przypietego pliku w magazynie`, kod 1; `teren: odtworzono (1 plik)`; `ok` |
| stary manifest (przypiety 83233) + pusty magazyn, zrodlo ma 84183 | `Error: teren: N-34-139-C-a-3-1: zrodlo ma inna tresc niz przypieta (przypieta 2025-04-27_83233, pobrana 2025-10-21_84183); przypiecie bez zmian - przywroc magazyn z kopii albo przyjmij nowa wersje: kartograf project download --upgrade teren`, kod 1, manifest bez zmian |
| katalogi projektow | tylko `kartograf-project.json` (+ magazyn `dane` w C i D) |

Linie `Brak pomiaru pokrycia ...: could not convert string to float: b'v1'`
w smoke pochodza z tresci fake'a (ASC z tekstem), nie z produktu.

## Ograniczenia i obserwacje

1. `rsync -aH` na udziale SMB/cifs moze nie zachowac dowiazan twardych
   (sekcja 4): kopia poprawna, `verify` zgodny, wieksza zajetosc.
2. BDOT10k nie ma taniego sygnalu: `--check-updates` = `nie da sie sprawdzic
   bez pobrania (--force)`, `--upgrade` zostaje przy wersji lokalnej
   z `Info:`; porownanie wymaga `--force` (tu 3,4 MB; paczka powiatu 1465 ma
   88 MB wg `docs/research/2026-10-12-store-e2e/raport.md`).
3. Etykiety BDOT10k i SM5 to data pobrania: odtworzenie innego dnia zmieni
   `version` i `label` przy tej samej sumie (dozwolone, spec 4.6). Na zywo
   nie sprawdzone (odtworzenie tego samego dnia); pokrywa to test offline
   `tests/test_project_download.py::test_restore_on_empty_store_same_content`.
   Stabilnosc tresci miedzy dniami potwierdzaja sumy SM5 (2026-10-12)
   i arkusza NMT (2026-10-13) rowne dzisiejszym.
4. Pierwsze przypiecie zadania, ktorego plik jest juz w magazynie
   (projekt B), siega do zrodla po metadane (3 zapytania o skorowidz NMT:
   biblioteka z `update=None` ustala najnowszy lot przed uzyciem wersji
   lokalnej); zadanie juz przypiete z kompletem wersji - 0 zapytan.
5. `--check-updates` bez cache (M12) powtarza `GetCapabilities` `clay` dla
   kazdego zadania, ktore go uzywa (8 zapytan na 5 zadan) - koszt pomijalny.
6. Linie postepu `Pobieranie ...` maja tylko zadania `elevation download`
   (`on_progress` tylko dla `download_data`, decyzja 3 planu); zadania
   `landcover`/`soil` sa ciche do linii wyniku.
7. Zadanie BDOT10k bez `--format` zalezy od domyslnego GPKG biblioteki
   (manifest zapisuje tylko wybor uzytkownika, spec 3.3); zmiana domyslnej
   wartosci wyszlaby przy odtworzeniu jako inna tresc.
8. Poza scenariuszami specu 7 (nie sprawdzane na zywo): CORINE (CLMS bez
   credentials), LAZ, `--country auto`, `imagery download`, rownolegle
   procesy na jednym projekcie.
9. Operacje projektu nie utworzyly `.kartograf_cache.db` (ani w korzeniu
   worktree, ani w `<katalog-danych>`); po przebiegu brak
   `.kartograf-project.lock`, plikow `*.tmp` i niepustych `.incoming`.

## Dane w `<katalog-danych>`

| Katalog | Zawartosc |
|---|---|
| `projekty/a`, `projekty/b`, `projekty/a-kopia`, `projekty/a-kopia-2`, `projekty/c` | tylko `kartograf-project.json` |
| `magazyn` | 30 sciezek, 22 pliki, 49 582 135 B |
| `magazyn-kopia` | 30 sciezek, 30 plikow, 136 148 121 B |
| `magazyn-kopia-2` | 30 sciezek, 28 plikow, 62 138 315 B |
| `magazyn-pusty` (po odtworzeniu) | 30 sciezek, 22 pliki, 49 582 135 B |
