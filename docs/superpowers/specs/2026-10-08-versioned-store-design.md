# Spec: Magazyn wersjonowany (podprojekt 1 roadmapy v1.0.0)

**Data:** 2026-10-08
**Status:** projekt zatwierdzony w rozmowie 2026-10-08 (sekcje 1-4); spec do
review uzytkownika
**Galaz:** `feat/versioned-store` (z `develop`)
**Wersja docelowa:** 0.8.0 (zmiany lamiace ukladu `data/`, `--force`,
sidecara i CLI land cover)
**Dokumenty zrodlowe:**
- `docs/SCOPE.md` 3.3 (roadmapa do v1.0.0, zasady magazynu i manifestu)
- ADR-026 (uklad `data/` per produkt), ADR-030 + errata 1-5 (kampanie
  i dowiazania), ADR-031 (angielskie identyfikatory)
- `docs/ARCHITECTURE.md` 3.2 (sidecar), 3.3 (uklad `data/`), 4.8 (land cover)

---

## 1. Kontekst i cel

Dzis tylko kampanie NMT/NMPT/orto PL (ADR-030) maja niezmienne wersje
(`<segment>/kampanie/<data>_<id>/...` + dowiazanie standardowe). Pozostale
produkty (BDOT10k, CORINE, SoilGrids, HSG, LAZ, CZ, wycinki `bbox/`) maja
jedna sciezke na plik: istniejacy plik jest pomijany bez kontaktu ze zrodlem
albo nadpisywany (`--force`; land cover nadpisuje przy KAZDYM pobraniu),
a poprzednia tresc przepada. Sidecar nie ma sumy kontrolnej (SCOPE 3.2),
a `extra.parent_requests` jest dopisywany do istniejacego sidecara.

Cel: magazyn, ktory **nigdy po cichu nie nadpisuje danych**. Kazdy produkt
ma niezmienne wersje identyfikowane trescia, kazda wersja ma niezmienny
sidecar z `sha256`, a aktualizacja do nowszych danych jest swiadoma. To
fundament manifestu projektu (podprojekt 2), ktory przypina konkretne
wersje, oraz GUI managera danych (podprojekt 5).

Poza zakresem (podprojekt 2): manifest projektu, `prune` (usuwanie wersji),
weryfikacja integralnosci lokalnych plikow (`verify`), indeks "ktore
projekty uzywaja pliku".

## 2. Decyzje (rozmowa 2026-10-08)

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

## 3. Model wersji i uklad na dysku

```
<segment>/versions/<etykieta>_<sha8>/<hierarchia>/<nazwa>.<ext>   (+ .meta.json)
<segment>/<hierarchia>/<nazwa>.<ext>                               <- dowiazanie do najnowszej
```

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

1. Pobranie do pliku tymczasowego w tym samym segmencie (ten sam system
   plikow), nazwa z PID i identyfikatorem watku; sha256 liczone w strumieniu
   (`transport/http.download_to`).
2. Jesli katalog wersji o tym sha8 istnieje i jego sidecar ma TO SAMO pelne
   sha256: plik tymczasowy usuwany, wynik "bez zmian" (`unchanged`).
3. Jesli istnieje z INNYM pelnym sha256 (kolizja prefiksu): `DownloadError`
   z opisem, bez zapisu.
4. W przeciwnym razie: utworzenie katalogu wersji, zapis sidecara wersji
   (plik tymczasowy + `os.replace`), potem `os.replace` danych.
5. Przestawienie dowiazania standardowego (sekcja 3.2).

Dwa procesy pobierajace te sama tresc koncza w tym samym katalogu wersji —
bez blokad (udzialy SMB bez blokad zakresow bajtow).

**Waznosc wersji:** wersja jest wazna tylko, gdy ma plik danych i sidecar
wersji. Katalog wersji bez jednego z nich (przerwany zapis) jest pomijany
z `Warning:`; pozostale pliki tymczasowe (`*.tmp` z PID) sprzata nastepny
zapis tego pliku.

### 3.2 Dowiazanie standardowe

Mechanizm ADR-030 (errata 4) bez zmian w zasadzie, z kluczem wersji zamiast
klucza kampanii:

- metoda: hardlink, inaczej kopia + `Warning:` (`extra.link` = `hardlink`/`copy`);
  bez symlinkow;
- sidecar sciezki standardowej = kopia sidecara wersji docelowej
  + `extra.link` i `extra.link_target` (jedyne zrodlo celu);
- **najnowsza wersja** = najpozniejsza data etykiety; remis albo brak daty
  w etykiecie -> `downloaded_at`;
- dowiazanie nigdy nie cofa sie na wersje starsza od biezacego celu;
- recznie usuniety katalog wersji = brak wersji; dowiazanie przestawia sie
  na najnowsza zachowana, a gdy nie ma zadnej — plik uznaje sie za
  niepobrany.

### 3.3 Sidecar (`kartograf-meta/1`, klucze tylko dodawane/usuwane)

Sidecar wersji jest pisany raz i nigdy nie zmieniany.

| Pole | Zmiana |
|---|---|
| `sha256` (gorny poziom) | NOWE, wszystkie sidecary wersji |
| `extra.version` | NOWE: `{label, label_source}` |
| `extra.http` | NOWE (gdy zrodlo daje): `{etag, last_modified, content_length}` z odpowiedzi, z ktorej pochodzi plik — sygnal `http` (sekcja 4.1) |
| `extra.source` / `extra.campaign` | bez zmian (kampanie PL) |
| etykieta zrodla dla BDOT10k, SoilGrids, CZ | NOWE pola wg inwentaryzacji (sekcja 8); dzis brak |
| `extra.sheet_sources[]` (wycinek PL) | NOWE `sha256` kazdego arkusza wejsciowego |
| `source_layers[]` (HSG) | NOWE `sha256` kazdej warstwy wejsciowej |
| wycinki CZ, inne pochodne | lista wejsc z `sha256` (postac w planie implementacji, wspolna z PL) |
| `extra.parent_requests` | USUNIETE (BREAKING); `extra.parent_request` zostaje |

Schemat pozostaje `kartograf-meta/1`: stare sidecary czytane jak dzis
(brak klucza = brak informacji).

### 3.4 Land cover i HSG w ukladzie `data/`

`LandCoverManager` i `HSGCalculator` przechodza na `storage_for_provider`
i segmenty ADR-026. Segmenty niosa parametry tresci, ktore dzis sa w nazwie
pliku (`bdot10k_gpkg_teryt_1206.gpkg`), np. (dokladne nazwy w planie
implementacji, zgodnie z regulami segmentow ADR-026):

```
landcover/pl_bdot10k_gpkg/teryt/1206.gpkg
landcover/eu_corine_2018/...
soil/global_soilgrids_clay_0-5cm_mean/...
hsg/...
```

Zmiana zachowania (BREAKING): ponowne uruchomienie NIE pobiera ponownie
istniejacego wyniku; reguly sekcji 4.

## 4. Zachowanie przy pobieraniu

### 4.1 Sygnal swiezosci

Deskryptor zrodla (`sources/`) deklaruje `update_signal`:

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
| `index` | `extra.campaign` / `extra.source` (data aktualnosci, id kampanii z URL, numer zgloszenia); LAZ: `extra.year` i URL kafla | najnowszy rekord skorowidza w zakresie strategii kampanii |
| `metadata` | etykieta edycji (`extra.version.label`) | data/rok/edycja z metadanych uslugi |
| `http` | `extra.http` (`etag`, `last_modified`, `content_length`) | naglowki odpowiedzi na `HEAD` |
| `none` | — | brak; wynik "nie da sie sprawdzic bez pobrania" |

Ograniczenie: zmiana tresci pliku przy niezmienionym sygnale (cicha poprawka
u zrodla pod tym samym rekordem i URL) jest niewykrywalna bez pobrania;
wykrywa ja `--force` (inne sha256 = nowa wersja). Zrodlo moze miec sygnal
uzupelniajacy (np. `index` + `Content-Length` z `HEAD`): rozny rozmiar =
na pewno inna tresc, ten sam rozmiar niczego nie dowodzi.

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
- Strategie kampanii (`--campaigns newest|all`, `--min-year`) okreslaja,
  KTORE wersje sa w zakresie zadania; tryby `update` — czy siegac po nie do
  zrodla. Dzisiejsze automatyczne pobranie nowszej kampanii przy `newest`
  znika (BREAKING, D5).

### 4.3 Produkty pochodne

Najpierw wersje wejsc (arkuszy, warstw) wg tabeli 4.2. Istniejaca wersja
pochodnej o tym samym zestawie sha256 wejsc i tych samych parametrach jest
uzywana ponownie (`reused`); w przeciwnym razie powstaje nowa wersja.

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
  (`new`/`unchanged`/`reused`/`local`), sciezka wersji.
- CLI: jedna linia statusu na plik, np.
  `N-34-130-D-d-2-4: nowa wersja 2025-06-02_91234_3fa91c2e`,
  `1206: lokalna wersja 2026-10-08_ab12cd34 (bez sprawdzania; --check-updates)`;
  podsumowanie z licznikami (nowe / bez zmian / uzyte ponownie / bledy).
- Stary katalog `kampanie/` w segmencie: jednorazowe
  `Info: katalog kampanie/ z wersji 0.7.0 nie jest uzywany; dane zostana
  pobrane ponownie do versions/` (bez migracji, D10).

## 5. Zmiany w kodzie

| Modul | Zmiana |
|---|---|
| `download/versions.py` (NOWY) | `VersionRef`, etykiety, `write_version`, `list_versions`, `newest`, `ensure_standard_link`; wchlania `download/campaigns.py` i `download/links.py` (logika hardlink/kopia/nigdy wstecz z kluczem wersji) |
| `download/updates.py` (NOWY) | `UpdatePlan`, pozycje, serializacja `kartograf-plan/1`, `check_updates`, `upgrade` |
| `transport/http.py` | sha256 w strumieniu `download_to`; zwrot `ETag`/`Last-Modified`/rozmiaru; `HEAD` dla sygnalu `http` |
| `sources/` (deskryptory) | pole `update_signal` |
| `sources/sidecar.py` | pola z sekcji 3.3; usuniecie `parent_requests` |
| `download/storage.py` | `get_version_path` zamiast `get_campaign_path`; `list_files` pomija `versions/` |
| `download/manager.py` | `update=` zamiast `skip_existing`; usuniety `_note_reuse`; kampanie przez `versions.py` |
| `download/cutout.py`, `download/laz.py` | zapis wersji; ponowne uzycie wycinka wg zestawu sha256 wejsc |
| `landcover/manager.py`, `hydrology/hsg.py` | `storage_for_provider`, segmenty, wersje, tryby `update` |
| `cli/*` | flagi z 4.2/4.4, linie statusu, liczniki, kody wyjscia, `Info:` o `kampanie/` |
| `cache/metadata.py` | bez zmian strukturalnych (`campaigns_cache` zostaje) |
| `kartograf/__init__.py` | eksporty `UpdatePlan`, `check_updates`, `upgrade`, `VersionRef` (nazwy angielskie) |

## 6. Przypadki brzegowe

| Sytuacja | Zachowanie |
|---|---|
| Przerwany zapis | wersja bez danych albo sidecara pomijana z `Warning:`; tmp sprzata nastepny zapis |
| Kolizja `sha8` | `DownloadError`, bez zapisu |
| Hardlink niemozliwy | kopia + `Warning:` |
| Plan nieaktualny | blad pozycji, reszta wykonana, kod czesciowego sukcesu |
| Plan: nieznany schemat / inny magazyn | `ValidationError` przed pobraniem |
| Recznie usuniety katalog wersji | dowiazanie na najnowsza zachowana albo "niepobrany" |
| Sygnal niedostepny | tabela 4.2 |

## 7. Testy

Offline (`-m "not live"`), fixtury z surowych odpowiedzi:

- `versions.py`: etykiety (3 zrodla), dedupe tej samej tresci, nowa wersja
  przy innej tresci, nigdy wstecz, dwa zapisy tego samego sha, wersja
  niekompletna pomijana, kolizja sha8, kopia zamiast hardlinku;
- tabela 4.2: kazda komorka osobnym testem (sygnal podstawiony);
- plan: round-trip JSON, nieaktualna pozycja, pozycja usunieta z planu,
  zly schemat/magazyn;
- sidecar: nowe pola, brak `parent_requests`, niezmiennosc sidecara wersji
  po ponownym uzyciu;
- land cover i HSG: nowe sciezki, domyslne uzycie lokalnej wersji;
- wycinek: ponowne uzycie wg sha wejsc; nowa wersja po zmianie jednego
  arkusza;
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
  tylko `Content-Length`. Do rozstrzygniecia w planie: czy `Content-Length`
  z `HEAD` jako sygnal uzupelniajacy (koszt: jedno zapytanie na plik).
- Pozostale hosty (paczki BDOT10k, LAZ, ISRIC, CUZK): te same pytania —
  sumy kontrolne, `ETag`/`Last-Modified`, `Content-Length`.

Wynik ustala `update_signal` i etykiete zrodla per deskryptor; zrodlo bez
taniego sygnalu dostaje `none`.

## 9. Dokumentacja

- Nowy ADR-032 "Magazyn wersjonowany" (CRLF w `docs/DECISIONS.md`):
  czesciowo zastepuje ADR-030 (uklad `kampanie/`, automatyczne `newest`)
  i ADR-026 (land cover poza ukladem); errata/odsylacze w indeksie.
- `ARCHITECTURE` 3.2, 3.3, 4.1-4.8; `SCOPE` 2.11, 2.12, 3.2 (znika "brak
  sum kontrolnych"); `PRD` 3.12; `USAGE`; `CHANGELOG` (BREAKING:
  `kampanie/` -> `versions/`, `--force`, brak automatycznej aktualizacji,
  `parent_requests`, sciezki land cover/HSG; Przejscie z 0.7.x: ponowne
  pobranie danych).
