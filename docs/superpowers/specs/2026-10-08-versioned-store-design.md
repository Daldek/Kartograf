# Spec: Magazyn wersjonowany (podprojekt 1 roadmapy v1.0.0)

**Data:** 2026-10-08; rewizja 2026-10-11 (po 0.7.1 i 0.7.2 oraz review
zapisu i skladowania, decyzje D13-D24); rewizja 2026-10-12 (weryfikacja
przed planem 2/3, decyzje D26-D28; D25 odrzucone)
**Status:** ZAAKCEPTOWANY przez uzytkownika 2026-10-11 (rewizja D13-D24);
D26-D28 decyzje uzytkownika 2026-10-12
**Galaz:** `feat/versioned-store` (z `develop`; rebase na 0.7.2 2026-10-11)
**Wersja docelowa:** 0.8.0 (zmiany lamiace ukladu `data/`, `--force`,
sidecara, nazw wycinkow `bbox/` i CLI land cover)
**Warunek wstepny:** usuniety przestarzaly tor arkuszowy wycinkow PL
(backlog "Do 0.8.0", ADR-035) — osobna galaz z `develop` przed planem 1/3
(D16)
**Dokumenty zrodlowe:**
- `docs/SCOPE.md` 3.3 (roadmapa do v1.0.0, zasady magazynu i manifestu)
- ADR-026 (uklad `data/` per produkt), ADR-030 + errata 1-8 (kampanie
  i dowiazania), ADR-031 (angielskie identyfikatory)
- ADR-032 (wybor roku), ADR-033 (`full_sheet/`), ADR-035 (wycinki PL z WCS)
- `docs/ARCHITECTURE.md` 3.2 (sidecar), 3.3 (uklad `data/`), 4.8 (land cover)

---

## 1. Kontekst i cel

Dzis tylko kampanie NMT/NMPT/orto PL (ADR-030) maja niezmienne wersje
(`<segment>/kampanie/<data>_<id>/...` + dowiazanie standardowe, od 0.7.2
takze dowiazanie `full_sheet/` do najnowszego pelnego lotu, ADR-033).
Pozostale produkty (BDOT10k, CORINE, SoilGrids, HSG, LAZ, CZ) maja jedna
sciezke na plik: istniejacy plik jest pomijany bez kontaktu ze zrodlem albo
nadpisywany (`--force`; land cover nadpisuje przy KAZDYM pobraniu), a
poprzednia tresc przepada. Wycinki PL z WCS (ADR-035) maja w nazwie date
pobrania i sa pobierane przy kazdym uruchomieniu (ten sam dzien =
nadpisanie). Sidecar ma od 0.7.1 `sha256` i `size_bytes` pliku danych, ale
nie jest niezmienny: `extra.parent_requests` jest dopisywany przy ponownym
uzyciu, a `extra.coverage` (0.7.2) po pomiarze pokrycia.

Cel: magazyn, ktory **nigdy po cichu nie nadpisuje danych**. Kazdy produkt
ma niezmienne wersje identyfikowane trescia, kazda wersja ma niezmienny
sidecar z `sha256`, a aktualizacja do nowszych danych jest swiadoma. To
fundament manifestu projektu (podprojekt 2), ktory przypina konkretne
wersje, oraz GUI managera danych (podprojekt 5).

Poza zakresem (podprojekt 2): manifest projektu, `prune` (usuwanie wersji),
weryfikacja integralnosci lokalnych plikow (`verify`), indeks "ktore
projekty uzywaja pliku".

## 2. Decyzje (rozmowy 2026-10-08, 2026-10-11 i 2026-10-12)

| # | Decyzja | Odrzucone |
|---|---|---|
| D1 | Wersja = TRESC: tozsamosc to sha256 pliku danych; identyczne ponowne pobranie = ta sama wersja, bez duplikatu | wersja wg daty zrodla (nie kazde zrodlo ja podaje); wersja per pobranie (duplikaty) |
| D2 | Data/edycja zrodla tylko jako etykieta wersji | — |
| D3 | Uklad: uogolnione kampanie ADR-030 — katalog wersji w segmencie + dowiazanie standardowe | magazyn adresowany trescia (`.store/sha256/...`): nieczytelny dla czlowieka i konsumentow |
| D4 | Jeden katalog `versions/` (angielski, ADR-031) dla WSZYSTKICH produktow; `kampanie/` znika, kampania = wersja z etykieta ze skorowidza | dwa mechanizmy (`versions/` + `kampanie/`); polskie `wersje/` |
| D5 | Domyslnie: lokalna wersja, a przy tanim sygnale tylko informacja o nowszej; jedna regula dla wszystkich produktow (takze kampanii) — powtarzalne wyniki | automatyczna aktualizacja przy tanim sygnale (dzisiejsze `newest`) |
| D6 | `--check-updates` = wylacznie raport; `--upgrade` = pobiera tylko to, co sprawdzenie potwierdzilo; `--force` = ponowne pobranie calosci | jedna flaga laczaca sprawdzanie i pobieranie |
| D7 | Plan aktualizacji `kartograf-plan/1` jako mechanizm (`check_updates` -> plan -> `upgrade(plan)`); `--upgrade` bez planu = skrot "sprawdz i wykonaj" | ukryty stan sprawdzen w cache SQLite |
| D8 | Produkty pochodne (wycinki, HSG) wersjonowane; sidecar z sha256 wejsc | odtwarzanie pochodnych z wejsc (nie bit w bit przy innej wersji GDAL/PROJ) |
| D9 | Bez automatycznego usuwania wersji (prune dopiero z manifestem) | `prune --keep N` bez wiedzy o projektach |
| D10 | Bez migracji starego ukladu: stare pliki przestaja byc widziane, dane pobiera sie ponownie | `store migrate`; migracja w locie (zapisy wspolbiezne na udziale bez blokad) |
| D11 | Land cover (BDOT10k, CORINE, SoilGrids) i HSG wchodza do kanonicznego ukladu `data/` (segmenty, wersje, domyslne uzycie lokalnej wersji) | osobna konwencja nazw z wersjami obok |
| D12 | Sidecar wersji pisany RAZ; `extra.parent_requests` usuniete (Hydrograf z niego nie korzysta), `extra.parent_request` zostaje | dopiski w sidecarze standardowym scalane przy przestawieniu |
| D13 | Pokrycie lotu (`extra.coverage`) mierzone PRZED zapisem sidecara wersji dla kazdego lotu bez `full_sheet = true` (takze pojedynczego); sidecar wersji niezmienny bez wyjatkow (2026-10-11) | dopisywanie po pobraniu (0.7.2); pokrycie tylko w sidecarze dowiazania (pomiar w kazdym zadaniu); wyjatek dla pol wynikajacych z tresci |
| D14 | Zakres lat i niedostepny skorowidz: gdy KAZDY arkusz zadania ma lokalna wersje z rocznikiem w zakresie — lokalne wersje + `Warning:` (D5); w przeciwnym razie blad calego zadania bez pobran (ADR-032 pkt 2) (2026-10-11) | zawsze blad zadania; decyzja per arkusz (lamie "zero plikow" ADR-032) |
| D15 | Wycinek PL z WCS (ADR-035) jak kazdy produkt: `bbox/<wsp>.tif` = dowiazanie do najnowszej wersji, data pobrania tylko w etykiecie wersji, domyslnie lokalna wersja (zmienia W-U3/W-U8) (2026-10-11) | pobieranie przy kazdym uruchomieniu; nazwy z data |
| D16 | Przestarzaly tor arkuszowy wycinkow PL usuwany PRZED planem 1/3; magazyn go nie wersjonuje (2026-10-11) | magazyn najpierw z tymczasowa obsluga toru arkuszowego |
| D17 | Uklad per plik: `<segment>/versions/<hierarchia>/<etykieta>_<sha8>/<nazwa>`; sprawdzenie "ta sama tresc" przeglada tylko wersje jednego pliku (review 2026-10-11, K1) | katalog wersji nad hierarchia: kazdy zapis przeglada wszystkie wersje segmentu (20 000 wersji: ok. 0,9 s lokalnie, szacunkowo 20-40 s na SMB na kazdy plik) |
| D18 | Zapis wersji wylaczny: `os.link` pliku roboczego (nigdy nie nadpisuje); istniejacy cel sprawdzany sha256 (K2) | `os.replace` (drugi proces podmienia plik pod dowiazaniem pierwszego) |
| D19 | Katalog roboczy `.incoming/<host>_<pid>_<token>/`; pozostalosci usuwane tylko wg wieku (mtime > 24 h) (I2) | `<pid>_<tid>` (niejednoznaczne miedzy hostami); sprzatanie przez nastepny zapis (moze usunac plik zywego procesu) |
| D20 | Jeden odczyt pliku przy zapisie: sha256 i pokrycie w jednym przebiegu, wynik przekazany do `build_metadata(digest=)` (I3) | trzy pelne odczyty (sha przy zapisie, sha w `build_metadata`, pokrycie) |
| D21 | `fsync` pliku roboczego przed `os.link` i tmp sidecara przed `os.replace` (I5) | brak gwarancji trwalosci przy utracie zasilania |
| D22 | Hardlinki wymagane: brak hardlinku = `DownloadError` pliku, bez kopii (I4; zmienia ADR-030 errata 4) | kopia + `Warning:` (2-3x miejsca, pelna kopia przy kazdym przestawieniu dowiazania) |
| D23 | Ta sama tresc pod nowym sygnalem (nowy rekord skorowidza, nowy `ETag`, nowa edycja): nowy katalog wersji `<nowa_etykieta>_<sha8>` z hardlinkiem do tych samych danych i wlasnym sidecarem; status `relabeled` (review 2026-10-11, I1) | `unchanged` bez sladu nowego sygnalu (petla "dostepna nowsza" -> `--upgrade` -> bez zmian); jeden katalog na tresc z etykieta poza niezmiennym sidecarem |
| D24 | Stary zwykly plik 0.7.x w sciezce, ktora w 0.8.0 staje sie dowiazaniem (LAZ `laz/pl_<uklad>_<vcrs>/...`, CZ godlo i `bbox/` w `nmt/cz_*`), jest NADPISYWANY przy pierwszym dowiazaniu, bez kopii i bez komunikatu; tylko wpis BREAKING w CHANGELOG (review 2026-10-11, D5; uzytkownik: brak innych uzytkownikow 0.7.x) | odlozenie jako `<nazwa>.pre-0.8`; przyjecie starego pliku jako wersji (migracja, wbrew D10) |
| D26 | LAZ wersjonowany per plik: nazwa kafla niesie id rekordu (`<zgloszenie>_<rekord>_<godlo>.laz`), wiec nowszy nalot to INNE pliki, nie nowa wersja tego samego. Selekcja kafli zawsze wg ADR-029/ADR-030 (najnowsza w zakresie lat); kafel z lokalna wersja nie jest pobierany ponownie (domyslnie i `--upgrade`), nowy kafel z nowszego nalotu pobiera sie takze domyslnie — wyjatek od D5 dla LAZ. WFS niedostepny = blad zadania jak dzis (bez lokalnej mapy pokrycia obszaru) (2026-10-12) | pokrycie obszaru najpierw z lokalnych kafli + `Info:` o nowszym nalocie (nowa sciezka selekcji) |
| D27 | `DownloadManager.download_bbox` USUNIETE (BREAKING): plik o nazwie wywolujacego w korzeniu `--output`, zawsze nadpisywany, dubluje `download_pl_cutout(target_crs="EPSG:2180")` bez maski PRG; Hydrograf go nie wola. NMT/NMPT bbox -> `download_pl_cutout` (wersjonowany, D15); orto i surowy WCS -> `provider.download_bbox(bbox, path)` poza magazynem, bez wersji i sidecara (2026-10-12) | wymagana `path` poza magazynem z odmowa nadpisania (dwa API do zblizonego wyniku); osobny segment `bbox_raw/` (trzecia regula sciezek) |
| D28 | `Content-Length` z `HEAD` NIE jest sygnalem uzupelniajacym zrodel `index`; cicha poprawke u zrodla wykrywa tylko `--force` (ograniczenie 4.1) (2026-10-12) | `HEAD` na plik w `--check-updates`/`--upgrade` (1 zapytanie na plik) |

## 3. Model wersji i uklad na dysku

```
<segment>/versions/<hierarchia>/<etykieta>_<sha8>/<nazwa>.<ext>   (+ .meta.json)
<segment>/<hierarchia>/<nazwa>.<ext>                               <- dowiazanie do najnowszej
```

- Wszystkie wersje pliku leza w `<segment>/versions/<hierarchia>/` (D17);
  sprawdzenie "ta sama tresc" czyta tylko katalogi tego miejsca i tylko
  pliki `<nazwa>`. Kampania nie ma wspolnego katalogu (i tak rozbija ja
  `sha8` per plik).
- `<segment>` i `<hierarchia>` bez zmian wzgledem ADR-026 (dla land cover
  i HSG nowe segmenty — sekcja 3.4).
- `sha8` = pierwsze 8 znakow szesnastkowych sha256 pliku danych; pelne
  sha256 w sidecarze.
- **Etykieta** (tylko dla czlowieka; w kolejnosci):
  1. kampania ze skorowidza: `<aktualnosc RRRR-MM-DD>_<id>` jak dzis w ADR-030;
  2. edycja zrodla: CORINE `<rok>`, rok aktualizacji CUZK, wersja SoilGrids
     (dokladna postac per zrodlo — inwentaryzacja, sekcja 8);
  3. data pobrania `RRRR-MM-DD` (UTC).
  Rodzaj etykiety zapisuje `extra.version.label_source`
  (`campaign`/`edition`/`downloaded`).

### 3.1 Zapis wersji

1. Provider pobiera plik do katalogu roboczego w tym samym segmencie:
   `<segment>/versions/.incoming/<host>_<pid>_<token>/<nazwa>` (`token`
   losowy — unikalny takze miedzy hostami na wspolnym udziale; ten sam
   system plikow, wiec dowiazanie i `os.replace` sa atomowe) (D19).
2. Jeden odczyt gotowego pliku liczy sha256 (`sources/sidecar.file_digest`)
   i — dla lotu bez `full_sheet = true` — pokrycie waznymi pikselami
   (`extra.coverage`, D13); wynik trafia do `build_metadata(digest=)`, ktory
   nie czyta pliku drugi raz (D20). Jedna sciezka dla plikow pobranych
   (takze rozpakowanych) i produktow pochodnych; bez liczenia w strumieniu
   `download_to` (decyzja uzytkownika 2026-10-08).
3. Jesli jakakolwiek WAZNA wersja tego pliku (dowolna etykieta) ma to samo
   sha256:
   - sygnal tego pobrania (etykieta kampanii/edycji, rekord skorowidza,
     `extra.http`) jest taki sam jak w ktorejs z tych wersji — plik
     roboczy usuwany, wynik "bez zmian" (`unchanged`);
   - sygnal jest inny (D23) — nowy katalog `<nowa_etykieta>_<sha8>`:
     `os.link` z ISTNIEJACEJ wersji (bez dodatkowego miejsca), wlasny
     sidecar wersji z nowym sygnalem, plik roboczy usuwany, wynik
     `relabeled`; dalej kroki 6-7. Etykieta `downloaded` sama w sobie nie
     jest sygnalem: zrodlo bez sygnalu (`none`) z ta sama trescia zawsze
     daje `unchanged`.
   Nowa etykieta przestawia dowiazanie wg zwyklej reguly "najnowsza
   wersja"; dzieki temu powrot zrodla do starszej tresci pod nowym
   sygnalem tez przestawia dowiazanie, mimo zasady "nigdy wstecz".
4. `fsync` pliku roboczego (D21), `mkdir` katalogu `<etykieta>_<sha8>`,
   `os.link(roboczy, docelowy)` — tworzenie wylaczne, nigdy nie nadpisuje
   (D18) — i usuniecie pliku roboczego. Brak obslugi hardlinkow =
   `DownloadError` (D22).
5. Cel juz istnieje (`FileExistsError`: rownolegly zapis albo wczesniej
   przerwany): sha256 istniejacego pliku. Rowne — plik roboczy usuwany;
   z sidecarem wersji `unchanged`, bez sidecara naprawa (sidecar pisany dla
   SPRAWDZONEJ tresci). Rozne (kolizja prefiksu albo uszkodzony plik) —
   `DownloadError`, bez zapisu.
6. Sidecar wersji: tmp + `fsync` + `os.replace` (D21). Porazka sidecara =
   plik danych usuwany, `DownloadError`. Kolejnosc dane -> sidecar, bo
   sidecar czyta plik (nodata z naglowka ASC, uklad arkusza PL-2000).
7. Przestawienie dowiazan (sekcja 3.2).

Dwa procesy (takze z roznych hostow na udziale) pobierajace te sama tresc
koncza w jednym katalogu wersji bez blokad: pierwszy `os.link` wygrywa,
drugi przechodzi krok 5 i konczy `unchanged`.

**Waznosc wersji:** wersja jest wazna tylko, gdy ma plik danych i sidecar
wersji. Katalog wersji bez jednego z nich (przerwany zapis) jest pomijany
z `Warning:`; wersje z danymi bez sidecara naprawia nastepny zapis tej
samej tresci (krok 5, po sprawdzeniu sha256). Pusty katalog wersji (awaria
miedzy `mkdir` a `os.link`) nie jest wersja.

**Sprzatanie (D19):** pozostalosci `versions/.incoming/` nigdy nie sa
wersjami. Zapis pliku usuwa w `.incoming/` i w `versions/<hierarchia>/`
tylko wpisy starsze niz 24 h (mtime: pliki robocze, puste katalogi
wersji) — nigdy mlodsze, bo moga nalezec do zywego procesu na innym
hoscie. Dotyczy tez pozostalosci po braku miejsca na dysku.

### 3.2 Dowiazanie standardowe

Mechanizm ADR-030 (errata 4) i ADR-033 bez zmian w zasadzie, z kluczem
wersji zamiast klucza kampanii:

- metoda: wylacznie hardlink (D22, zmienia ADR-030 errata 4 — bez kopii
  zapasowej); magazyn wymaga systemu plikow z hardlinkami (ext4, NTFS,
  SMB — sprawdzone w ADR-030 errata 4), brak hardlinku = `DownloadError`
  pliku z opisem; bez symlinkow; `extra.link = "hardlink"`;
- dwa dowiazania: sciezka standardowa `<segment>/<hierarchia>/<nazwa>` do
  najnowszej wersji oraz — tylko kampanie NMT/NMPT/orto —
  `<segment>/full_sheet/<hierarchia>/<nazwa>` do najnowszej wersji
  z `extra.campaign.full_sheet = true` (ADR-033; brak takiej wersji = brak
  pliku w `full_sheet/`);
- sidecar dowiazania = kopia sidecara wersji docelowej + `extra.link`
  i `extra.link_target` (jedyne zrodlo celu) + pola zestawu lotow zadania,
  ktore nie opisuja jednej wersji (`extra.flights`, `extra.better_coverage`,
  ADR-032 pkt 4 i 7); sidecar dowiazania jest przepisywany, sidecar wersji
  nigdy;
- **najnowsza wersja**: kampanie — klucz ADR-028/030 (`extra.campaign.date`,
  `extra.campaign.pzgik_date`, `extra.source.url`); pozostale produkty —
  data etykiety, przy remisie albo braku daty `downloaded_at`;
- dowiazanie nigdy nie cofa sie na wersje starsza od biezacego celu; gdy przy
  zakresie lat wskazuje wersje spoza zakresu — informacja jak w 0.7.2
  (`link_outside_range`, `full_link_outside_range`, `Info:` w CLI);
- recznie usuniety katalog wersji = brak wersji; dowiazanie przestawia sie
  na najnowsza zachowana, a gdy nie ma zadnej — plik uznaje sie za
  niepobrany.
- Windows: plik standardowy otwarty przez inny program (np. QGIS) blokuje
  przestawienie dowiazania — blad tego pliku; wersja zostaje zapisana,
  dowiazanie przestawi nastepne uruchomienie;
- dowiazanie i jego sidecar sa zapisywane osobno: przez chwile sidecar moze
  opisywac poprzednia wersje (znane ograniczenie; naprawia nastepne
  przestawienie, wykrywa manifest w podprojekcie 2).

### 3.3 Sidecar (`kartograf-meta/1`, klucze tylko dodawane/usuwane)

Sidecar wersji jest pisany raz i nigdy nie zmieniany.

| Pole | Zmiana |
|---|---|
| `sha256`, `size_bytes` (gorny poziom) | istnieja od 0.7.1 (`build_metadata`, odczyt gotowego pliku); w sidecarze wersji = tozsamosc wersji |
| `extra.version` | NOWE: `{label, label_source}` |
| `extra.http` | istnieje od 0.7.1 dla BDOT10k (`{etag, last_modified, content_length}`; serwer paczek GUGiK podaje tylko `Content-Length`); NOWE dla pozostalych zrodel, gdy daja naglowki — sygnal `http` (sekcja 4.1) |
| `extra.source` / `extra.campaign` | bez zmian (kampanie PL; `extra.campaign.full_sheet` wyznacza cel `full_sheet/`) |
| `extra.coverage` | w sidecarze wersji liczone przy zapisie (D13), nigdy dopisywane; `extra.flights`, `extra.better_coverage` tylko w sidecarze dowiazania |
| `request.*`, `extra.available_years` (ADR-032 pkt 7) | bez zmian; `request` opisuje pobranie, ktore UTWORZYLO wersje (ponowne pobranie tej samej tresci go nie zmienia) |
| etykieta zrodla dla BDOT10k, SoilGrids, CZ | NOWE pola wg inwentaryzacji (sekcja 8); dzis brak |
| `extra.source_files[]` (HSG) | istnieje w `hsg_from_rasters` (`name`, `file`, `sha256`); NOWE w `calculate_hsg_by_bbox` |
| inne pochodne z lokalnych plikow | lista wejsc z `sha256` w postaci `extra.source_files[]` |
| `extra.parent_requests` | USUNIETE (BREAKING); `extra.parent_request` zostaje |

Schemat pozostaje `kartograf-meta/1`: stare sidecary czytane jak dzis
(brak klucza = brak informacji).

### 3.4 Land cover i HSG w ukladzie `data/`

`LandCoverManager` i `HSGCalculator` przechodza na `storage_for_provider`
i segmenty ADR-026. Segmenty niosa parametry tresci, ktore dzis sa w nazwie
pliku (od 0.7.1 `bdot10k_teryt_<TERYT>.gpkg`, z filtrem warstw
`bdot10k_PTWP-SWRS_teryt_<TERYT>.gpkg`), np. (dokladne nazwy w planie
implementacji, zgodnie z regulami segmentow ADR-026):

```
landcover/pl_bdot10k_gpkg/teryt/1206.gpkg
landcover/pl_bdot10k_gpkg_PTWP-SWRS/teryt/1206.gpkg
landcover/pl_bdot10k_raw_zip/teryt/1206.zip     (keep_raw)
landcover/eu_corine_2018/...
soil/global_soilgrids_clay_0-5cm_mean/...
hsg/...
```

Filtr warstw BDOT10k zmienia tresc, wiec jest parametrem segmentu, nie
wersja. Oryginalny ZIP (`keep_raw=True`) jest osobnym plikiem z wlasnymi
wersjami i sidecarem (jak w 0.7.1); sidecar GPKG ma wtedy
`extra.source_files[]` z sha256 ZIP-a. Zapisy ZIP i GPKG nie sa atomowe
wzgledem siebie (awaria miedzy nimi = ZIP bez GPKG; naprawia nastepne
uruchomienie). `hsg_from_rasters` pisze pod
sciezke podana przez wywolujacego — poza magazynem, bez wersji.

Zmiana zachowania (BREAKING): ponowne uruchomienie NIE pobiera ponownie
istniejacego wyniku; reguly sekcji 4.

## 4. Zachowanie przy pobieraniu

### 4.1 Sygnal swiezosci

Kanal dostepu deskryptora (`AccessChannel` w `sources/`) deklaruje
`update_signal` — per kanal, bo jeden deskryptor moze miec kanaly o roznych
sygnalach (np. `cz.cuzk.dmr4g`: pliki SM5 z `openzu` i `exportImage`;
`pl.gugik.nmt_1m`: arkusze ze skorowidza i WCS) (rewizja 2026-10-12):

| Wartosc | Znaczenie | Przyklad |
|---|---|---|
| `index` | skorowidz GUGiK (rekord, kampanie) | NMT, NMPT, orto, LAZ |
| `metadata` | data/rok w metadanych uslugi | CUZK, CORINE `year` |
| `http` | `ETag`/`Last-Modified` z sidecara wersji porownywane zapytaniem `HEAD` | wg inwentaryzacji |
| `none` | brak taniego sygnalu | wg inwentaryzacji |

Przyporzadkowanie zrodel — inwentaryzacja (sekcja 8).

**Sprawdzanie porownuje sygnal, nie sha256.** Tozsamosc wersji (sha256)
sluzy zapisowi w magazynie i manifestowi; poznaje sie ja dopiero po
pobraniu. Sprawdzanie swiezosci (domyslne `Info:`, `--check-updates`,
`--upgrade`) porownuje wylacznie sygnal i **nigdy nie pobiera danych**:

| Sygnal | Strona lokalna (sidecar wersji) | Strona zrodla |
|---|---|---|
| `index` | `extra.campaign` / `extra.source` (data aktualnosci, id kampanii z URL, numer zgloszenia); LAZ: URL kafla w sidecarze wersji (D26: plik = rekord) | najnowszy rekord skorowidza w zakresie strategii kampanii; LAZ: selekcja kafli WFS (ADR-029/030) |
| `metadata` | etykieta edycji (`extra.version.label`) | data/rok/edycja z metadanych uslugi |
| `http` | `extra.http` (`etag`, `last_modified`, `content_length`) | naglowki odpowiedzi na `HEAD` |
| `none` | — | brak; wynik "nie da sie sprawdzic bez pobrania" |

Ograniczenie: zmiana tresci pliku przy niezmienionym sygnale (cicha poprawka
u zrodla pod tym samym rekordem i URL) jest niewykrywalna bez pobrania;
wykrywa ja `--force` (inne sha256 = nowa wersja). `Content-Length` z `HEAD`
nie jest sygnalem uzupelniajacym (D28).

### 4.2 Tryby

Biblioteka: jeden parametr `update: None | "check" | "upgrade" | "force"`.
CLI (`download`, `landcover`, `soilgrids`): `--check-updates`, `--upgrade`,
`--force` — wzajemnie wykluczajace sie.

Lokalna wersja istnieje:

| Sytuacja | Domyslnie | `--check-updates` | `--upgrade` | `--force` |
|---|---|---|---|---|
| Sygnal tani, bez zmian | lokalna wersja | raport "aktualne" | lokalna wersja | pobiera ponownie |
| Sygnal tani, jest nowsza | lokalna wersja + `Info: dostepna nowsza ... (--upgrade)` | raport "nowsza: <etykieta>" | pobiera -> nowa wersja | pobiera ponownie |
| Sygnal `none` | lokalna wersja | raport "nie da sie sprawdzic bez pobrania" | lokalna wersja (niesprawdzone) + `Info:` o `--force` | pobiera ponownie |
| Sygnal niedostepny (siec, skorowidz) | lokalna wersja + `Warning:` | raport "nie udalo sie sprawdzic" | blad tego pliku | blad pobrania |

Brak lokalnej wersji: domyslnie, `--upgrade` i `--force` pobieraja
najnowsza; `--check-updates` raportuje "do pobrania".

- `--check-updates` niczego nie pobiera (takze brakujacych plikow).
- Ponowne pobranie nigdy nie nadpisuje: to samo sha256 = "bez zmian".
- `--force` (BREAKING, nowe znaczenie): pobiera bajty ponownie i odswieza
  cache metadanych (`MetadataCache(refresh=True)`), niezaleznie od sygnalu.
- Bledy sa per plik; reszta zadania sie wykonuje; kod wyjscia wg dzisiejszej
  reguly czesciowego sukcesu (ARCHITECTURE 4.2). `--check-updates` z choc
  jedna pozycja "nie udalo sie sprawdzic" konczy sie tym samym kodem.
- Strategie kampanii (`--campaigns newest|all`; w 0.8.0 przelacznik bez
  wartosci, backlog) i zakres lat (`--year`/`--min-year`/`--max-year`,
  ADR-032) okreslaja, KTORE wersje sa w zakresie zadania; tryby `update` —
  czy siegac po nie do zrodla. Dzisiejsze automatyczne pobranie nowszej
  kampanii przy `newest` znika (BREAKING, D5).
- Zakres lat, domyslnie: lokalna wersja liczy sie, gdy jej rocznik
  (`aktualnoscRok`, ADR-032 pkt 1) jest w zakresie. Faza sprawdzenia
  ADR-032 (pelna lista rocznikow przed pobraniem, `YearRangeError`) dziala
  bez zmian, gdy skorowidz odpowiada. Skorowidz niedostepny: D14 — KAZDY
  arkusz ma lokalna wersje w zakresie = lokalne + `Warning:`; w przeciwnym
  razie blad calego zadania, zero pobran. Bez zakresu lat: tabela wyzej
  (dzisiejsze I-1 dla wszystkich strategii).
- `--full-sheet` (ADR-033): brakujacy lokalnie najnowszy pelny lot
  z zakresu to pozycja "brak lokalnej wersji" (domyslnie, `--upgrade`
  i `--force` pobieraja; `--check-updates` raportuje "do pobrania").
  `full_sheet/` powstaje tez bez flagi z wersji lokalnych.
- Weryfikacja rekordu (B4, uklad wysokosci, 0.7.1) dziala przed kazdym
  pobraniem we wszystkich trybach; `--force` jej nie wylacza.

### 4.3 Produkty pochodne

Produkty pochodne = wyniki liczone z LOKALNYCH plikow (dzis HSG z warstw
SoilGrids). Najpierw wersje wejsc wg tabeli 4.2. Istniejaca wersja
pochodnej o tym samym zestawie sha256 wejsc i tych samych parametrach jest
uzywana ponownie (`reused`); w przeciwnym razie powstaje nowa wersja.

Wycinki PL z WCS (ADR-035) i wycinki CZ nie sa pochodnymi: ich zrodlem jest
usluga, nie lokalne pliki — wersjonowane jak produkty zrodlowe (sekcja 4.6).

### 4.4 Plan aktualizacji (`kartograf-plan/1`)

- Biblioteka: `check_updates(...) -> UpdatePlan`; `upgrade(plan)` wykonuje
  plan. `UpdatePlan` serializuje sie do JSON (angielskie klucze).
- Pozycja planu: identyfikacja pliku (segment + hierarchia + nazwa),
  wersja lokalna (etykieta, sha256), wersja dostepna (etykieta i wartosc
  sygnalu: rekord skorowidza / data / `ETag`), status (`current`, `newer`,
  `missing`, `unverifiable`, `check_failed`).
- Naglowek planu: `schema: "kartograf-plan/1"`, katalog magazynu (`--output`),
  czas sprawdzenia, wersja Kartografa.
- `upgrade(plan)`: przed pobraniem kazdej pozycji ponownie odczytuje sygnal;
  jesli rozni sie od zapisanego w planie — blad tej pozycji ("zrodlo zmienilo
  sie od planu"), bez pobrania. Pozycje usuniete z pliku planu nie sa
  wykonywane.
- Nieznany schemat albo inny katalog magazynu: `ValidationError` przed
  jakimkolwiek pobraniem.
- CLI: `--check-updates [--plan PLIK]` zapisuje plan; `--upgrade --plan PLIK`
  wykonuje go; `--upgrade` bez planu = sprawdzenie i wykonanie w jednym
  przebiegu (model bez stanu).
- Plan lezy tam, gdzie wskaze uzytkownik — nie w magazynie.

### 4.5 Wynik i CLI

- `SheetFetch`/`DownloadResult`, wyniki land cover, LAZ, wycinka i HSG
  dostaja informacje o wersji: etykieta, `sha256`, status
  (`new`/`unchanged`/`relabeled`/`reused`/`local`), sciezka wersji.
- CLI: jedna linia statusu na plik, np.
  `N-34-130-D-d-2-4: nowa wersja 2025-06-02_91234_3fa91c2e`,
  `1206: lokalna wersja 2026-10-08_ab12cd34 (bez sprawdzania; --check-updates)`;
  podsumowanie z licznikami (nowe / nowa etykieta / bez zmian / uzyte
  ponownie / bledy).
- Stary katalog `kampanie/` w segmencie: jednorazowe
  `Info: katalog kampanie/ z wersji 0.7.0 nie jest uzywany; dane zostana
  pobrane ponownie do versions/` (bez migracji, D10).

### 4.6 Wycinki `bbox/` (D15)

- Nazwa bez daty: `<segment>/bbox/<wsp>.tif` = dowiazanie do najnowszej
  wersji; wersje w `<segment>/versions/bbox/<etykieta>_<sha8>/<wsp>.tif`
  (D17, hierarchia = `bbox`) z etykieta `downloaded` (data pobrania UTC).
  Dotychczasowe `<wsp>_<RRRRMMDD>.tif` przestaja byc rozpoznawane (D10,
  bez migracji).
- Domyslnie lokalna wersja (zmiana W-U8 ADR-035: koniec pobierania przy
  kazdym uruchomieniu); `--force` pobiera ponownie — ta sama tresc =
  "bez zmian", inna = nowa wersja. Sygnal wg inwentaryzacji (sekcja 8);
  bez taniego sygnalu `none`.
- Wejscia spoza tresci (maska PRG `extra.mask`, `composition: "server"`)
  zostaja w sidecarze wersji; zmiana maski u zrodla jest niewykrywalna bez
  `--force` (jak cicha poprawka, sekcja 4.1).
- Powtarzalnosc bajtowa (inwentaryzacja 2026-10-12, sekcja 8): wycinek PL
  WCS (EPSG:2180 i 3045), wycinek CZ (natywny i EPSG:2180), arkusz SM5,
  kafel TM33 i surowy kafel LAZ — dwa pobrania o identycznym sha256. Przy
  niezmienionej tresci zrodla `--force` daje "bez zmian", nie nowa wersje.
  Zmiana GDAL/PROJ albo naglowkow serwera moze to zmienic (wtedy nowa
  wersja, bez usuwania do podprojektu 2).
- Wycinek CZ: ta sama regula nazw i trybow.

## 5. Zmiany w kodzie

| Modul | Zmiana |
|---|---|
| `download/versions.py` (NOWY) | `VersionRef`, etykiety, `commit_version` (`.incoming/<host>_<pid>_<token>`, `fsync`, wylaczny `os.link`, sprawdzenie istniejacego celu, sprzatanie > 24 h), `list_versions` (tylko `versions/<hierarchia>/`), `newest_version`; wchlania sciezki `download/campaigns.py` (`CampaignRef` i weryfikacja rekordu zostaja) |
| `download/links.py` | zostaje: wylacznie hardlink (bez kopii, D22), nigdy wstecz, oba dowiazania (standardowe i `full_sheet/`); `version_key_of` zamiast `campaign_key_of`; bez `update_sidecar_extra` dla sidecarow wersji (D13) |
| `download/updates.py` (NOWY) | `UpdatePlan`, pozycje, serializacja `kartograf-plan/1`, `check_updates`, `upgrade` |
| `transport/http.py` | bez liczenia sha256 (sekcja 3.1 pkt 2); zwrot `ETag`/`Last-Modified`/rozmiaru i `HEAD` dla sygnalu `http` |
| `sources/` (deskryptory) | pole `update_signal` |
| `sources/sidecar.py` | `extra.version`; `build_metadata(digest=)` (sha256 i rozmiar z zapisu, bez drugiego odczytu, D20); `fsync` tmp sidecara (D21); usuniecie `parent_requests` |
| `download/storage.py` | `get_version_path` zamiast `get_campaign_path`; `list_files` pomija `versions/` i `full_sheet/` |
| `download/manager.py` | `update=` zamiast `skip_existing`; usuniety `_note_reuse`; kampanie przez `versions.py`; faza zakresu lat (ADR-032) z regula D14; pomiar pokrycia przy zapisie wersji (D13); `full_sheet` jako pozycje "brak lokalnej wersji"; usuniete `download_bbox` (D27) |
| `download/cutout.py` (tor WCS), `download/cz_cutout.py`, `download/laz.py` | zapis wersji; wycinki bez daty w nazwie (D15) |
| `landcover/manager.py`, `hydrology/hsg.py` | `storage_for_provider`, segmenty, wersje, tryby `update`; `source_files[]` w `calculate_hsg_by_bbox` |
| `cli/*` | flagi z 4.2/4.4, linie statusu, liczniki, kody wyjscia, `Info:` o `kampanie/` |
| `cache/metadata.py` | bez zmian strukturalnych (`campaigns_cache` zostaje) |
| `kartograf/__init__.py` | eksporty `UpdatePlan`, `check_updates`, `upgrade`, `VersionRef` (nazwy angielskie) |

## 6. Przypadki brzegowe

| Sytuacja | Zachowanie |
|---|---|
| Przerwany zapis | wersja bez danych albo sidecara pomijana z `Warning:`; pozostalosci starsze niz 24 h sprzata zapis tego pliku (D19) |
| Kolizja `sha8` / uszkodzony plik pod nazwa wersji | `DownloadError`, bez zapisu |
| Rownolegly zapis tej samej tresci (takze inny host) | pierwszy `os.link` wygrywa, drugi `unchanged` (D18) |
| Hardlink niemozliwy | `DownloadError` pliku (D22) |
| Brak miejsca na dysku | `DownloadError`; plik roboczy usuwany, a jesli nie — sprzatanie > 24 h |
| Utrata zasilania | `fsync` przed dowiazaniem i przed sidecarem (D21) |
| Windows: plik standardowy otwarty | blad pliku, wersja zapisana, dowiazanie przy nastepnym uruchomieniu |
| Stary zwykly plik 0.7.x w sciezce dowiazania (LAZ, CZ) | nadpisany dowiazaniem przy pierwszym zapisie (D24) |
| Plan nieaktualny | blad pozycji, reszta wykonana, kod czesciowego sukcesu |
| Plan: nieznany schemat / inny magazyn | `ValidationError` przed pobraniem |
| Recznie usuniety katalog wersji | dowiazanie na najnowsza zachowana albo "niepobrany" |
| Sygnal niedostepny | tabela 4.2 |
| Zakres lat, skorowidz niedostepny | D14: wszystkie arkusze z lokalna wersja w zakresie = lokalne + `Warning:`, inaczej blad zadania bez pobran |
| Lot niepelny bez pomiaru pokrycia (blad odczytu rastra) | wersja zapisana bez `extra.coverage` + `Warning:`; brak dopisywania pozniej |

## 7. Testy

Offline (`-m "not live"`), fixtury z surowych odpowiedzi:

- `versions.py`: etykiety (3 zrodla), dedupe tej samej tresci, nowa wersja
  przy innej tresci, nigdy wstecz, rownolegly zapis tego samego sha
  (`os.link` + `FileExistsError`), naprawa wersji bez sidecara po
  sprawdzeniu sha256, wersja niekompletna pomijana, kolizja sha8, brak
  hardlinku = blad, sprzatanie tylko wpisow > 24 h, jeden odczyt pliku
  przy zapisie; ta sama tresc z nowym sygnalem = `relabeled` (hardlink,
  bez nowego miejsca, dowiazanie na nowa etykiete), ta sama tresc bez
  sygnalu = `unchanged`;
- tabela 4.2: kazda komorka osobnym testem (sygnal podstawiony);
- plan: round-trip JSON, nieaktualna pozycja, pozycja usunieta z planu,
  zly schemat/magazyn;
- sidecar: nowe pola, brak `parent_requests`, niezmiennosc sidecara wersji
  po ponownym uzyciu;
- land cover i HSG: nowe sciezki, domyslne uzycie lokalnej wersji, filtr
  warstw BDOT10k w segmencie, `keep_raw` jako osobny plik;
- wycinki `bbox/`: nazwa bez daty, domyslnie lokalna wersja, `--force`
  z ta sama trescia = "bez zmian";
- HSG: ponowne uzycie wg sha wejsc; nowa wersja po zmianie jednej warstwy;
- kampanie: `full_sheet/` z wersji, `--full-sheet` jako "brak lokalnej
  wersji", `extra.coverage` w sidecarze wersji przy zapisie (bez
  pozniejszych zmian sidecara), D14 (wszystkie arkusze lokalnie vs brak
  jednego);
- CLI: wykluczanie flag, linie statusu, liczniki, kody wyjscia, `Info:`
  o `kampanie/`;
- sygnal `http`: fixtury z odpowiedzi nagranych na zywo w inwentaryzacji;
- weryfikacja mutacja kluczowych regul (dedupe, nigdy wstecz, waznosc
  wersji, plan nieaktualny).

Na zywo (`-m live`, swiadomie): jeden test na typ sygnalu; E2E w katalogu
danych poza repo: puste `versions/` -> pelne pobranie -> ponowne
uruchomienie (bez sieciowych zmian) -> `--check-updates` -> `--upgrade`
-> `--force`.

## 8. Inwentaryzacja sygnalow (pierwsze zadanie planu)

Przed implementacja sekcji 4: dla kazdego zrodla sprawdzic na zywo i zapisac
surowe odpowiedzi jako fixtury:

- BDOT10k (paczki powiatowe): `HEAD` — `ETag`/`Last-Modified`/rozmiar?
  data paczki w metadanych uslugi?
- SoilGrids (WCS ISRIC): wersja zbioru w GetCapabilities/metadanych?
  naglowki HTTP?
- CORINE: `year` jako edycja (juz w `request.year`); czy w obrebie edycji
  zmienia sie tresc?
- CUZK (DMR 5G/4G): rok aktualizacji (`Metadata`) jako etykieta i sygnal;
- LAZ: rekord WFS jako sygnal `index` (rok, gestosc);
- NMT/NMPT/orto: skorowidz — bez zmian (`index`). Ustalone na zywo
  2026-10-08 (`HEAD` arkusza NMT na `opendata.geoportal.gov.pl`): serwer NIE
  podaje sum kontrolnych (brak naglowka `Digest`, pliki `<plik>.md5`/
  `.sha256`/`.sha1` = 404, rekord skorowidza bez pola sumy), NIE podaje
  `ETag` ani `Last-Modified`, katalogi kampanii bez listingu (404); jest
  tylko `Content-Length`. `Content-Length` nie jest sygnalem uzupelniajacym
  (D28).
- Pozostale hosty (paczki BDOT10k, LAZ, ISRIC, CUZK): te same pytania —
  sumy kontrolne, `ETag`/`Last-Modified`, `Content-Length`.
- WCS GUGiK (wycinki `bbox/`, ADR-035): naglowki odpowiedzi
  (`ETag`/`Last-Modified`) i data aktualizacji w GetCapabilities; brak =
  `none`.
- Powtarzalnosc bajtowa: dla kazdego zrodla pobrac ten sam obiekt dwa razy
  i porownac sha256 (szczegolnie wycinki WCS, GPKG BDOT10k skladany
  lokalnie, wycinki CZ); wynik zapisac w 4.6 i USAGE.

Wynik ustala `update_signal` i etykiete zrodla per deskryptor; zrodlo bez
taniego sygnalu dostaje `none`.

**Wynik (2026-10-12,** raport
`docs/research/2026-10-12-signal-inventory/raport.md`, naglowki
`tests/fixtures/signals/real_2026_10_12/`**):**

| Deskryptor / kanal | Sygnal | Etykieta | Powtarzalnosc bajtowa |
|---|---|---|---|
| `pl.gugik.nmt_1m`/`nmt_5m`/`nmpt`/`orto` — arkusze | `index` | `campaign` | — |
| `pl.gugik.nmt_1m`/`nmpt` — WCS (`bbox/`) | `none` (bez `ETag`/`Last-Modified`, GetCapabilities bez daty) | `downloaded` | tak |
| `pl.gugik.laz` — pliki | `index` (rekord WFS; `HEAD` tylko `Content-Length`) | `campaign` (D26) | tak (surowy kafel) |
| `cz.cuzk.dmr4g` — pliki SM5 (`openzu`) | `http` (`ETag`, `Last-Modified`) | `downloaded` | tak |
| `cz.cuzk.dmr4g`/`dmr5g` — `exportImage` (TM33, wycinki) | `none` | `downloaded` | tak |
| `pl.gugik.bdot10k` | `none` (tylko `Content-Length`) | `downloaded` | tak (GPKG skladany lokalnie) |
| `global.isric.soilgrids` | do decyzji w planie 3/3: `metadata` tylko na poziomie wydania (tytul GetCapabilities `SoilGrids250m 2.0`) albo `none` | `edition` `SoilGrids250m 2.0` albo `downloaded` | tak |
| `eu.clms.corine` | `metadata` (`year`) — niesprawdzone (brak `CLMS_CREDENTIALS`) | `edition` `<rok>` | nie sprawdzono |

Ustalenia poza oczekiwaniami: `exportImage` CUZK zwraca `ETag`, ale zalezny
od parametrow zadania (bbox, rozmiar, format), bez dowodu, ze sledzi edycje
rastra, a wycinek i kafel TM33 ponad budzet pikseli sa mozaika wielu zadan —
zostaje `none`. Warstwa CUZK `Metadata` (`rok`) to rok aktualizacji
obszaru, nie tozsamosc wersji pobieranego pliku — nie jest sygnalem ani
etykieta. `ETag` dokumentu `ImageServer?f=json` dotyczy dokumentu JSON.

## 9. Dokumentacja

- Nowy ADR-036 "Magazyn wersjonowany" (CRLF w `docs/DECISIONS.md`):
  czesciowo zastepuje ADR-030 (uklad `kampanie/`, automatyczne `newest`,
  errata 4: kopia zamiast hardlinku — D22),
  ADR-033 (F-U5: "`kampanie/` zostaje"), ADR-035 (W-U3/W-U8: nazwa z data,
  pobieranie przy kazdym uruchomieniu), ADR-032 (pkt 2: awaria skorowidza
  przy zakresie — D14; pkt 4: pomiar pokrycia — D13), ADR-026 (land cover
  poza ukladem) i ADR-004 (`DownloadManager.download_bbox` usuniete — D27);
  ADR-036 zapisuje wyjatek LAZ od D5 (D26); errata/odsylacze w indeksie.
- `ARCHITECTURE` 3.2, 3.3, 4.1-4.8; `SCOPE` 2.11, 2.12 (sumy kontrolne
  w sidecarze sa od 0.7.1); `PRD` 3.12; `USAGE` (wymaganie systemu plikow
  z hardlinkami, kopiowanie magazynu `rsync -aH`, zalecana kompresja
  systemu plikow — tresc w magazynie jest nieskompresowana, bo sha256
  liczone z bajtow); `CHANGELOG` (BREAKING:
  `kampanie/` -> `versions/`, `--force`, brak automatycznej aktualizacji,
  `parent_requests`, sciezki land cover/HSG, wycinki `bbox/` bez daty
  w nazwie i bez pobierania przy kazdym uruchomieniu, koniec kopii zamiast
  hardlinku, stare pliki LAZ i CZ nadpisywane przy pierwszym pobraniu —
  D24; usuniete `DownloadManager.download_bbox` — D27; Przejscie z 0.7.x:
  ponowne pobranie danych).
