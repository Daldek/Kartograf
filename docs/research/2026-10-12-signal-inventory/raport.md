# Inwentaryzacja sygnalow swiezosci zrodel (2026-10-12)

**Zakres:** Task 1 planu 2/3 magazynu wersjonowanego; pomiary na zywo, bez zmian kodu ani specu. Dane i jednorazowe skrypty: `<katalog-danych>/kartograf/e2e/2026-10-12-signal-inventory/`. Pobrane dane nie sa fixturami w repo. Naglowki i male surowe dokumenty: `tests/fixtures/signals/real_2026_10_12/`; dla kazdego probowanego obiektu sa osobne JSON dla HEAD i GET (GET strumieniowany i zamkniety bez czytania danych; wyjatkiem GetCapabilities i metadanych jest zapis ciala ponizej 200 KB). Daty pomiaru w JSON: `2026-10-12`. Zapytania i pobrania wykonywano sekwencyjnie.

## 1. Naglowki, sygnal i etykieta

Skruty naglowkow: `T` = Content-Type, `L` = Content-Length, `C` = Cache-Control, `E` = ETag, `M` = Last-Modified. `-` oznacza brak tych szesciu naglowkow; `Digest` nie wystapil w zadnej z odpowiedzi. `HEAD/GET` podaje stan kazdej metody osobno; wszystkie zapisane odpowiedzi mialy status HTTP 200. Etykieta `downloaded` = data pobrania UTC, a nie data publikacji serwera.

| Zrodlo / kanal i probka | HEAD / GET | Sygnal | Etykieta | Uzasadnienie |
|---|---|---|---|---|
| `pl.gugik.nmt_1m` arkusz ASC, `82060_1692108` | T,L,C / T,L,C | `index` | `campaign` (`<data_aktualnosci>_<id>`) | Skorowidz podaje lot; sam plik bez E/M/Digest. |
| `pl.gugik.nmpt` arkusz ASC, `80195_1533958` | T,L,C / T,L,C | `index` | `campaign` | Jw. |
| `pl.gugik.orto` arkusz TIFF, `83832_1514596` | T,L,C / T,L,C | `index` | `campaign` | Jw. |
| `pl.gugik.laz` kafel `83230_1743180_...laz` | T,L,C / T,L,C | `index` | `campaign` (`<akt_data>_<zgloszenie>`) | WFS identyfikuje rekord; nowszy nalot tworzy inna nazwe pliku (D26). |
| `pl.gugik.bdot10k` powiat 1465, ZIP GPKG | T,L,C / T,L,C | `none` | `downloaded` | `schemat2021` w URL opisuje schemat, nie edycje paczki; L nie jest sygnalem (D28). |
| `pl.gugik.nmt_1m` WCS GetCoverage, EVRF2007 | T / T | `none` | `downloaded` | HEAD zwraca ogolny `text/html`, GET `multipart/related; boundary=wcs`, oba bez E/M. |
| GUGiK WCS GetCapabilities, NMT KRON86 TIFF | T / T,L | `none` | nie dotyczy | Dokument uslugi bez daty aktualizacji coverage. |
| `global.isric.soilgrids` GetCoverage `clay_0-5cm_mean` | T,L,C / T,C | `metadata` (tylko edycja zbioru) | `edition`: `SoilGrids250m 2.0` | HEAD to `text/html` (nie dane coverage), GET to `image/tiff`; zadne nie daje E/M. Tytul GetCapabilities deklaruje edycje 2.0, ale brak daty i sygnalu zmian w obrebie tej edycji. |
| ISRIC GetCapabilities dla `clay.map` | T,L,C / T,L,C | `metadata` (tylko edycja) | `edition`: `SoilGrids250m 2.0` | Tytul `SoilGrids250m 2.0 - Clay content`; brak daty ostatniej zmiany i wersji poszczegolnych coverage. |
| `cz.cuzk.dmr4g` SM5 `CTES96.zip` z `openzu` | T,L,M,E / T,L,M,E | `http` (E, potem M) | `downloaded` | `ETag: "d19f2c604d89dc1:0"`, `Last-Modified: Mon, 19 Jan 2026 14:10:33 GMT` to data publikacji pliku, nie rok skanowania. |
| `cz.cuzk.dmr5g` `exportImage`, maly TM33 i bbox | T,L,C,E / T,L,C,E | **`none`** | `downloaded` | ETag istnieje, lecz jest zaleznym od parametrow zadania znacznikiem odpowiedzi, nie potwierdzono, ze zmienia sie przy edycji danych rastra; dla kafelkowania brak pojedynczego ETag calego pliku. |
| `cz.cuzk.dmr5g` rzeczywisty kafel TM33 `302_5550`, pojedyncze zadanie eksportu 1128x1128 | T,L,C,E / T,L,C,E | **`none`** | `downloaded` | ETag `"b5007506"`; obecnosci ETag jednego zapytania nie mozna przeniesc na wszystkie mozaiki. |
| CUZK `dmr5g/ImageServer?f=json` | T,L,C,E / T,C,E | `none` dla rastra | `downloaded` | ETag dotyczy dokumentu JSON; brak pola edycji/daty danych rastrowych. |
| CUZK `Metadata/MapServer/20?f=json` i zapytanie punktowe | T,C,E / T,C,E; T,L,C,E / T,L,C,E | `none` dla eksportu rastra | `downloaded` | Warstwa ma pole `rok` (`Rok aktualizace`); punkt `-670050,-1084750` zwrocil `2010`. To rok obszaru, a nie tozsamosc wersji mozaiki ImageServer lub eksportu TM33. |
| `eu.clms.corine` | nie sprawdzono (brak `CLMS_CREDENTIALS`) | `metadata` (`year`) **oczekiwane, niezmierzone** | `edition`: `<rok>` (np. `2018`), **oczekiwane** | Brak prob autoryzowanego pliku i porownania bajtow; nie mozna potwierdzic zmian w obrebie rocznika. |

**CUZK ETag, sprawdzenie znaczenia:** dwukrotny GET identycznego eksportu TIFF 50x50 dal ten sam ETag `"5e254ee7"` i SHA-256 `2e38bd438435126797d847aa16d95f613bd0d9262226ca14c0f62e8acdf291b0`. Bbox sasiedni: ETag `"59cd482"`, SHA-256 `46213d106e150d6f6fc59d961322df07ba5ec386692c139899112ce34a915aec`; ten sam bbox w PNG: ETag `"8c0653bf"`, SHA-256 `dcf21344c0d219efcf1ad12d9c8b84d2acbb0afcf6db90186687bcc0229f85b0`. ETag nie jest prefiksem SHA ani CRC32/Adler32 bajtow TIFF (`c87c012c`/`0f08da05`) i PNG (`33216a47`/`360d21c9`). Czas HEAD TIFF (pierwszy) 0,516 s, GET 0,987 s i powtorny GET 0,478 s; dla sasiedniego HEAD 0,232 s, GET 0,877 s. To za malo, by potwierdzic, ze HEAD nie renderuje calej odpowiedzi. `Cache-Control: must-revalidate,max-age=43200,public` (12 h) moze maskowac zmiany. **Rekomendacja:** `none` do czasu udokumentowania zaleznosci ETag od edycji samego datasetu. Sam ETag od obrazu i mozliwosc HEAD nie stanowia sygnalu swiezosci po stronie serwera dla calego lokalnego pliku.

**WCS i metadane:** GUGiK GetCapabilities zawiera `CoverageId` i opis uslugi, nie date aktualizacji danych. ISRIC GetCapabilities podaje tytul edycji `SoilGrids250m 2.0 - Clay content` (plik XML w fixturach), bez rewizji warstwy `clay_0-5cm_mean`. Przy stabilnym 2.0 aktualizacja bajtow pozostanie niewykryta az do `--force`; jezeli wymog sygnalu oznacza wykrywanie kazdej poprawki w obrebie wydania, SoilGrids trzeba traktowac jako `none`, zachowujac etykiete edycji `SoilGrids250m 2.0` w sidecarze. CUZK `Metadata/20` nie jest obrazem ani indeksem historycznych kampanii; pokazuje rok regionalnej ostatniej aktualizacji, nie stan aktualnie pobieranego eksportu.

## 2. Powtarzalnosc bajtowa (dwa niezalezne pobrania)

`A` i `B` to osobne katalogi wynikowe pod `<katalog-danych>/kartograf/e2e/2026-10-12-signal-inventory/<przypadek>/`; hashe ponizej sa SHA-256 plikow danych, nie sidecarow. W kazdym uruchomieniu CLI jawne `--output` i `--workers 1`. Sukces oznacza rownosc dwoch kompletnych plikow dla podanych parametrow, nie gwarancje niezmiennosci serwera w przyszlosci.

| Przypadek, obiekt | A (SHA-256) | B (SHA-256) | Bajty powtarzalne |
|---|---|---|---|
| `pl_wcs_2180`, NMT WCS 200x200 m, EPSG:2180 | `31f74cd761c86971781cef6bec29683c69561f65a39896387dd5c74931a65986` | `31f74cd761c86971781cef6bec29683c69561f65a39896387dd5c74931a65986` | tak |
| `pl_wcs_3045`, ten sam obszar, EPSG:3045 | `076bd5022e3730e729d2b3c850eaa4df63f2ac16e65ce5f6d04261453d44ed7b` | `076bd5022e3730e729d2b3c850eaa4df63f2ac16e65ce5f6d04261453d44ed7b` | tak |
| `cz_native`, bbox 200x200 m w EPSG:5514 | `1991d4bfed2d0b4177cd4a5ed6625592c99546a5825d0885d1497185225ac1ae` | `1991d4bfed2d0b4177cd4a5ed6625592c99546a5825d0885d1497185225ac1ae` | tak |
| `cz_2180`, ten sam bbox, lokalna reprojekcja EPSG:2180 | `300843fbb0b8383e5404109c40c77836c74ec125cbceab2a42f38f54cc24cef1` | `300843fbb0b8383e5404109c40c77836c74ec125cbceab2a42f38f54cc24cef1` | tak |
| `cz_sm5`, CTES96, rozpakowany TIFF + uzupelniony tag CRS | `a1e327bb5678c957a1e07684f20ce505b826f1b9b1cf6cace30f06864ca18d0d` | `a1e327bb5678c957a1e07684f20ce505b826f1b9b1cf6cace30f06864ca18d0d` | tak |
| `cz_tm33`, 302_5550, lokalny warp na EPSG:3045 | `23116e9f8a5d594e6a5978ecadedb01d0c468e803b0c7741dbddc9cafa120d1d` | `23116e9f8a5d594e6a5978ecadedb01d0c468e803b0c7741dbddc9cafa120d1d` | tak (64691 pikseli danych) |
| `pl_laz_direct`, caly kafel 136606526 B `83230_1743180_...laz` | `78a7131d8aee1d8a33c4bf2624f6396eedb7c735c65de526866d7395776da027` | `78a7131d8aee1d8a33c4bf2624f6396eedb7c735c65de526866d7395776da027` | tak (surowe bajty HTTP) |
| `bdot10k_gpkg`, powiat 1465, warstwa PTWP | `1ed467c48163aaa3fb404e7f2435198beed3c1975fa041638917e44d00b26ebd` | `1ed467c48163aaa3fb404e7f2435198beed3c1975fa041638917e44d00b26ebd` | tak |
| `soilgrids_clay`, `clay_0-5cm_mean`, 3x2 piksele TIFF | `06d680486d0a7b81efc1e483f6b658b9b90fcd83154561f9bf49bb67d212b4b2` | `06d680486d0a7b81efc1e483f6b658b9b90fcd83154561f9bf49bb67d212b4b2` | tak |
| CORINE | nie sprawdzono | nie sprawdzono | nie ustalono |

PL WCS przy czesci prob przerywal polaczenie `RemoteDisconnected`; przebieg B EPSG:2180 i przebiegi EPSG:3045 udaly sie po ponowieniu. Nie zaliczono pobrania niekompletnego do porownania. LAZ w CLI: godlo pliku `N-34-139-A-c-1-1-1-1` nie jest akceptowanym godlem arkusza, a probny wybior pliku `7.173.21.06.2` przez WFS przekroczyl 240 s; dodatkowo niestabilny w trakcie pracy tree roboczy mial chwilowy blad importu, dlatego pomiar **bajtow zrodla** wykonano dwoma pelnymi, sekwencyjnymi GET bez selekcji WFS/CLI. Nie dowodzi on powtarzalnosci dowolnych pochodnych LAZ; zwykly tor LAZ zapisuje odebrane bajty bez reprojekcji. Weryfikacja CLI pozostaje niepotwierdzona w tym pomiarze.

## 3. Komendy i parametry do odtworzenia

`D='<katalog-danych>/kartograf/e2e/2026-10-12-signal-inventory'`; ponizsze komendy wykonano raz dla `run=A` i raz dla `run=B`, kazda z osobnym `--output "$D/<przypadek>/$run"`, z korzenia repo i z `.venv`. Podane `--output` sa jawnymi sciezkami w katalogu danych poza repo. Udane pomiary CLI wykonano, zanim rownolegle zmiany kodu naruszyly importy; pozniejsze probowanie naglowkow korzystalo z tymczasowej kopii ustalonego commita w `D/src-snapshot`.

```sh
.venv/bin/kartograf download --bbox 530100,382100,530300,382300 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --target-crs EPSG:2180 --workers 1 --output "$D/pl_wcs_2180/$run"
.venv/bin/kartograf download --bbox 530100,382100,530300,382300 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --target-crs EPSG:3045 --workers 1 --output "$D/pl_wcs_3045/$run"
.venv/bin/kartograf download --bbox=-670100,-1084800,-669900,-1084600 --bbox-crs EPSG:5514 --country cz --product nmt --resolution 2m --vertical-crs Bpv --workers 1 --output "$D/cz_native/$run"
.venv/bin/kartograf download --bbox=-670100,-1084800,-669900,-1084600 --bbox-crs EPSG:5514 --country cz --product nmt --resolution 2m --vertical-crs Bpv --target-crs EPSG:2180 --workers 1 --output "$D/cz_2180/$run"
.venv/bin/kartograf download --sheet CTES96 --country cz --product nmt --resolution 5m --vertical-crs Bpv --workers 1 --output "$D/cz_sm5/$run"
.venv/bin/kartograf download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv --workers 1 --output "$D/cz_tm33/$run"
```

Biblioteka: `.venv/bin/python` z korzenia repo, dla obu przebiegow oddzielny katalog `D/<przypadek>/<run>/`:

```python
from pathlib import Path
from kartograf import BBox
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider

Bdot10kProvider().download_package("1465", Path("<output>/1465.gpkg"), layers=["PTWP"])
SoilGridsProvider().download_by_bbox(
    BBox(530100, 382100, 530600, 382600, "EPSG:2180"),
    Path("<output>/clay.tif"), property="clay", depth="0-5cm", stat="mean",
)
```

LAZ: dla A i B `requests.get(url, stream=True, timeout=(15,120))`, strumien 1 MiB do oddzielnego `<output>/83230_1743180_N-34-139-A-c-1-1-1-1.laz`, obliczenie SHA-256; URL dokladnie w `gugik_laz_tile_get.json` (katalog fixtur). Wynik 136606526 B w kazdym przebiegu. HEAD i GET naglowkow: `.venv/bin/python "$D/probe.py"`, dodatkowy rzeczywisty TM33 i WCS: `PYTHONPATH="$D/src-snapshot" .venv/bin/python "$D/probe_extra.py"`; sprawdzenie ETag: `.venv/bin/python "$D/export_etag.py"`. Katalog `src-snapshot` byl jedynie tymczasowa kopia commita do stabilnej proby.

## 4. Porownanie z oczekiwanym przyporzadkowaniem planu 2/3

| Deskryptor / kanal | Plan: sygnal / etykieta | Pomiar: sygnal / etykieta | Roznica |
|---|---|---|---|
| PL NMT 1 m, NMT 5 m, NMPT, orto - arkusze | `index` / `campaign` | `index` / `campaign` (probki NMT 1m, NMPT, orto; NMT 5m bez osobnego HEAD) | brak udokumentowanej zmiany |
| PL NMT/NMPT - WCS | `none` / `downloaded` | `none` / `downloaded` (probka NMT; NMPT z tego samego typu uslugi, bez osobnej proby) | **brak roznicy dla planu 2/3** |
| PL LAZ - pliki | `index` / `campaign` | `index` / `campaign` | **brak roznicy dla planu 2/3**; CLI wyboru kafla niepotwierdzone |
| CZ SM5 - openzu | `http` (E/M) / `downloaded` | `http` (E/M) / `downloaded` | **brak roznicy dla planu 2/3** |
| CZ TM33 i bbox - exportImage | `none` / `downloaded` | `none` / `downloaded`, mimo zaobserwowanego ETag | **rozbieznosc w naglowkach, NIE w rekomendowanym sygnale**; nie zmieniac na `http` bez dowodu zgodnosci ETag z edycja rastera i agregacji przy kafelkowaniu |
| BDOT10k | do ustalenia (`none` wg 0.7.1) / do ustalenia | `none` / `downloaded` | uzupelnienie planu 3/3: schema 2021 nie jest edycja |
| CORINE | `metadata` (`year`) / `edition` `<rok>` | nie sprawdzono / nie sprawdzono | brak potwierdzenia wobec braku credentials |
| SoilGrids | do ustalenia / do ustalenia | `metadata` na poziomie tytulu wydania / `edition` `SoilGrids250m 2.0` | uzupelnienie planu 3/3: brak wykrywania korekt w obrebie 2.0 i brak HTTP E/M |

**Roznice wzgledem tekstu specu 8 (nie zmieniano specu ani planu):** spec sugeruje, ze CUZK rok aktualizacji `Metadata` jest etykieta i sygnalem ImageServer. Rok dotyczy poligonu aktualizacji, nie wersji eksportowanego pliku; nie stanowi poprawnego taniego sygnalu porownania konkretnego TIFF. Spec pozostawia powtarzalnosc `bbox/` jako niesprawdzona; w dziewieciu parach powyzej jest powtarzalna (dla LAZ porownano surowy kafel). Spec 8 nie rozroznia HTTP ETag dokumentu `ImageServer?f=json` od sygnalu zawartosci rastrowej i nie przewiduje ETag dla exportImage; pomiar wykazuje ETag, ale bez gwarancji jego semantyki. Edycja SoilGrids jest tylko w tytule uslugi; brak wersji per coverage i daty aktualizacji.
