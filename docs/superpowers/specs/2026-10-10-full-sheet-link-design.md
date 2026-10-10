# Spec: Drugie dowiazanie do najnowszego PELNEGO lotu (`full_coverage/`)

**Data:** 2026-10-10
**Status:** decyzje uzytkownika z 2026-10-10 (sekcja 0) wiazace; spec do
akceptacji calosci, potem plan i implementacja
**Wersja docelowa:** 0.7.2 (galaz `feat/full-sheet-link` z `develop`)
**Dokumenty zrodlowe:**
- ADR-028 (wybor rekordu: najnowsza `(aktualnosc, dt_pzgik, url)`, bez
  preferencji pelnego arkusza), decyzja D4/D9 z 2026-09-29
- ADR-030 (d) (dowiazanie do najnowszej LOKALNEJ kampanii, nigdy wstecz)
  + errata 3 (CZ bez kampanii), errata 4 (wylacznie hardlink -> kopia),
  errata 5 (I-1)
- ADR-032 / spec `2026-10-09-year-range-selection-design.md` sekcja 0
  (model A: flagi roku = filtr, `--campaigns` = liczba lotow; U15
  `Info:` o dowiazaniu spoza przedzialu), Q2a (opcja `--full-sheet`)
- E13 (`docs/research/2026-10-06-e2e-brzegowe-i-review/cykl-e2e.md`),
  `raport-koncowy.md` sekcja 4 (kierunki (a)-(c)),
  `pokrycie-kampanii.md` (pomiar 8 par)
- backlog `docs/PROGRESS.md` "Do 0.7.2" pozycja (c)

---

## 0. Decyzje uzytkownika (2026-10-10)

| # | Decyzja | Sekcja |
|---|---|---|
| F-U1 | **Dociaganie tylko z flaga `--full-sheet`** (wariant C). Bez flagi: drugie dowiazanie powstaje wylacznie z lotow, ktore zadanie i tak ma lokalnie (model A doslowny: `--campaigns` = liczba lotow). Z flaga: gdy najnowszy lot w przedziale nie jest pelny, zadanie pobiera DODATKOWO najnowszy pelny lot w przedziale. | 5.1, 5.2 |
| F-U2 | **Arkusz bez zadnego pelnego lotu:** brak pliku w `full_coverage/` + komunikat laczony z E13 (jeden `Warning:`). Bez dowiazania "najlepszego" niepelnego. | 5.3 |
| F-U3 | **Przedzial lat:** dowiazanie pelne nigdy wstecz; gdy zostaje przy nowszym pelnym locie spoza przedzialu — `Info:` jak U15. | 5.4 |
| F-U4 | **Wycinki `--target-crs`:** mozaika ze sciezek standardowych, bez zmian. | 6.3 |
| F-U5 | **Nazwa katalogu po angielsku: `full_coverage/`** ("i tak przechodzimy na anglojezyczne nazwy"). `kampanie/` zostaje (zmiana nazwy to osobna, lamiaca decyzja — kandydat do 0.8.0). | 3 |

## 1. Kontekst i cel

### 1.1 Problem

Sciezka standardowa `<segment>/<hierarchia>/<godlo>.<ext>` wskazuje
najnowszy lokalny lot, takze niepelny (`calyArkuszWypelnionyTrescia = NIE`).
Uzytkownik dostaje `Warning:` E13, ale plik zostaje niepelny. Pomiar
2026-10-07 (577 grup godlo x produkt): 14 arkuszy z niepelnym najnowszym
rekordem, w 8 istnieje starszy pelny lot; pokrycie niepelnego od 0,9 %
(NMT N-34-139-C-a-3-1, okno 255 x 422 px) do 98,9 %. Pozostale 6 to
glownie NMT 0,5 m bez zadnego pelnego lotu.

Regula ADR-028 zostaje: drugie dowiazanie OBOK standardowego, nie zmiana
klucza standardowego.

### 1.2 Cel

1. Dla kazdego arkusza z co najmniej jednym lokalnym lotem pelnym
   (`full_sheet is True`) wsrod lotow zadania powstaje drugie dowiazanie
   `<segment>/full_coverage/<hierarchia>/<godlo>.<ext>` do najnowszego
   takiego lotu (klucz ADR-028), z sidecarem jak sciezka standardowa.
2. `--full-sheet` dociaga najnowszy pelny lot, gdy najnowszy nie jest
   pelny — uzytkownik dostaje uzywalny plik bez `--campaigns all`.
3. Drzewo standardowe nie zmienia znaczenia; biblioteka zwraca sciezke
   dowiazania pelnego w wyniku.

### 1.3 Poza zakresem

- Zmiana klucza sciezki standardowej (ADR-028/ADR-030 (d) bez zmian).
- Mozaika lotow (nowy + uzupelnienie ze starszego) — SCOPE 3.1.
- Wybor wg zmierzonego pokrycia (`--min-coverage`, Q2a). Flaga GUGiK
  myli sie w obie strony (Slubice N-33-126-C-c-3-4: TAK przy 75 %
  nodata) — `full_coverage/` ufa deklaracji skorowidza, co dokumentacja
  mowi wprost.
- Zmiana nazwy `kampanie/` na angielska.
- CZ (6.4), LAZ (6.2), wycinki `--target-crs` (6.3), land cover.

## 2. Stan kodu (pomiar 2026-10-10, `develop` `fc4c176`)

| Element | Dzis | Gdzie |
|---|---|---|
| Flaga pelnego arkusza | `SkorowidzRecord.full_sheet` z `calyArkuszWypelnionyTrescia` (TAK/NIE/brak = True/False/None); `CampaignRef.full_sheet`; sidecar kampanii `extra.campaign.full_sheet`, `extra.source.full_sheet` | `providers/pl/skorowidz.py:192-204`, `download/campaigns.py:213-269` |
| Przeplyw kampanii | `_fetch_campaigns`: rekordy z `resolve_campaigns` -> pliki w `kampanie/` -> `local` (lista `(CampaignRef, Path)` lotow TEGO zadania) -> `max(local, key=sort_key)` -> `ensure_standard_link(std, path, key, refresh=)` | `download/manager.py:863-1058` |
| Dowiazanie | `ensure_standard_link(link, target, key, refresh)` — ogolne wzgledem sciezki `link`: cel z sidecara `link` (`linked_campaign`), nigdy wstecz (`campaign_key_of(cur) >= key`), `link_atomic` (hardlink -> kopia), `write_standard_sidecar` (kopia sidecara kampanii + `extra.link`, `extra.link_target`) | `download/links.py:168-328` |
| Rekordy `newest` bez przedzialu | jeden rekord: `_resolve_record` (cache `record_cache`) | `skorowidz.py:485-540, 646-647` |
| Pelna lista lotow | `_resolve_all`: WSZYSTKIE warstwy skorowidza produktu, cache `campaigns_cache`; uzywana przy `all` i przy przedziale lat | `skorowidz.py:542-614` |
| Sciezki | `FileStorage.get_path` (standard), `get_campaign_path` (`<segment>/kampanie/<data>_<id>/<hierarchia>/`) | `download/storage.py:213-273` |
| Listowanie | `FileStorage.list_files(campaigns=False)` = wszystko w segmencie POZA `kampanie/` — nowy katalog trafilby do listy plikow standardowych (duplikaty) | `storage.py:480-517` |
| Usuwanie | `FileStorage.delete(godlo)` usuwa sciezke standardowa + sidecar, kampanie zostaja | `storage.py:452-478` |
| E13 | `_warn_partial_sheets`: `Warning:` z sidecarow wyniku (`extra.source.full_sheet is False`), takze przy skip | `cli/download_cmd.py:1446-1522` |
| I-1 | awaria transportu skorowidza przy `newest` bez przedzialu i ze skip: wynik z lokalnej kampanii, dowiazanie bez zmian | `manager.py:905-942` |
| Straze opcji kampanii | CZ bez PL = `Error:`, PL+CZ pod `auto` = `Info:`; wycinek `--target-crs` z `--campaigns all`/flagami roku = `Error:` przed siecia | `cli/download_cmd.py` (ADR-030 errata 1 [Q2], errata 3; ADR-032) |
| Wycinek PL | mozaika ze sciezek standardowych arkuszy; `partial_sheets` z `sheet_sources[].full_sheet` | `download/cutout.py` |

Numery linii z pomiaru; plan weryfikuje je przed kazdym zadaniem.

## 3. Uklad danych

```
<segment>/
  <hierarchia>/<godlo>.<ext>                   # standard: najnowszy lokalny lot (bez zmian)
  <hierarchia>/<godlo>.<ext>.meta.json
  full_coverage/<hierarchia>/<godlo>.<ext>     # NOWE: najnowszy lokalny lot pelny
  full_coverage/<hierarchia>/<godlo>.<ext>.meta.json
  kampanie/<data>_<id>/<hierarchia>/<godlo>.<ext>   # pliki (bez zmian)
```

- Stala `FULL_COVERAGE_DIR = "full_coverage"` obok `CAMPAIGNS_DIR`;
  `FileStorage.get_full_coverage_path(godlo, ext)`.
- Dowiazanie: ta sama mechanika co standardowe — hardlink -> kopia,
  atomowa podmiana, nigdy wstecz (wsrod lotow pelnych), sidecar = kopia
  sidecara kampanii + `extra.link`, `extra.link_target`.
  `ensure_standard_link` dostaje nazwe ogolna `ensure_link` (wszyscy
  wolajacy zmigrowani, bez aliasu); `write_standard_sidecar` analogicznie
  `write_link_sidecar`.
- Gdy najnowszy lot jest pelny, `full_coverage/` i standard wskazuja ten
  sam plik (dwa hardlinki jednego inode — bez kosztu miejsca; przy kopii
  — dwie kopie, istniejacy `Warning:` o kopii).
- Kolizja nazw: brak — `full_coverage` nie jest czlonem hierarchii
  (pierwszy czlon to arkusz 1:1M albo strefa, np. `N-34`, `7`).

## 4. Regula dowiazania pelnego

- Kandydaci: loty z `local` TEGO zadania z `ref.full_sheet is True`
  (NIE i brak flagi = nie pelny — tylko to, co skorowidz jawnie deklaruje).
- Cel: `max(kandydaci, key=sort_key)`; `ensure_link(full, path, key,
  refresh=path in downloaded)` — nigdy wstecz, wiec po wczesniejszym
  `--campaigns all` dowiazanie zostaje przy nowszym pelnym locie.
- Dzialanie bez flagi (F-U1): domyslne `newest` z pelnym najnowszym
  daje `full_coverage/` = ten sam plik co standard; `--campaigns all`
  daje najnowszy pelny z przedzialu. Pierwsze uruchomienie po
  aktualizacji tworzy `full_coverage/` dla istniejacych danych
  (przeplyw kampanii przechodzi przez kazdy arkusz, takze przy skip).
- Brak kandydatow: dowiazanie pelne nietkniete (istniejace zostaje,
  nowego nie ma); komunikat — 5.3.
- Porazka dowiazania pelnego (`OSError`) = porazka arkusza (jak
  standardowego), komunikat `dowiazanie <sciezka>: <blad>`.
- I-1 (skorowidz niedostepny): dowiazanie pelne nietkniete.
- `--force`: odswieza jak standardowe (`refresh`).

## 5. Pobieranie i komunikaty

### 5.1 Flaga `--full-sheet` (F-U1)

- CLI `kartograf download ... --full-sheet` (bez wartosci); biblioteka
  `DownloadManager(full_sheet=True)` (domyslnie `False`).
- Znaczenie: gdy wybrany najnowszy lot (w przedziale lat) ma
  `full_sheet is not True`, pobierz dodatkowo najnowszy lot z
  `full_sheet is True` w tym samym przedziale; dowiaz go w
  `full_coverage/`. Gdy najnowszy jest pelny — flaga nic nie zmienia.
- Z `--campaigns all`: dozwolona, bez skutku (wszystkie loty i tak sa
  pobierane) — jak jawne `--campaigns newest` w modelu A, bez bledu.
- Dozwolona z flagami roku (przedzial filtruje tez lot pelny).
- `--help` i USAGE: "pobiera najwyzej jeden dodatkowy lot na arkusz,
  tylko gdy najnowszy jest niepelny"; `--campaigns` w `--help` bez zmian.

### 5.2 Dociaganie — szczegoly

- Bez nowego API providera: manager, po rekordzie `newest` z
  `full_sheet is not True`, wola `resolve_campaigns(godlo, campaigns=
  "all", min_year, max_year)` i bierze pierwszy rekord z `full_sheet is
  True` (lista jest od najnowszego). Pelna lista warstw skorowidza tylko
  dla arkuszy z niepelnym najnowszym (cache `campaigns_cache`).
- Dociagniety lot trafia do `kampanie/`, liczy sie w
  `DownloadResult.campaign_files`/`reused_campaign_files` i w
  podsumowaniu ("Downloaded N campaign files for M sheets").
- Sidecar dociagnietego lotu: `request.full_sheet: true` (obok
  `request.campaigns`); bez flagi pole nieobecne.
- Awaria pobrania lotu pelnego = porazka arkusza (jak kazda kampania,
  Q10 ADR-030); sciezka standardowa i tak powstaje z najnowszego.
- Awaria skorowidza przy pelnej liscie: jak dzis przy `all` (wyjatek,
  porazka arkusza).

### 5.3 Arkusze bez pelnego lotu (F-U2)

- Brak pliku w `full_coverage/` (drzewo ma jedno znaczenie).
- Jeden `Warning:` zamiast dzisiejszego E13 (stderr, takze z `-q`), dla
  arkuszy z niepelnym najnowszym lotem, z podzialem:
  - "pelny lot w `full_coverage/`: <godla>" — gdy dowiazanie pelne
    istnieje (z flaga albo z lokalnych lotow);
  - "brak pelnego lotu w skorowidzu: <godla>" — z `--full-sheet`, gdy
    pelna lista nie ma lotu TAK w przedziale;
  - "pelny lot nie pobrany: <godla> — uzyj --full-sheet" — bez flagi,
    gdy lokalnie brak lotu pelnego (nie wiadomo, czy w skorowidzu jest).
  Tresc dokladna w planie; fakt czytany z sidecarow (dziala przy skip):
  standardowy (`extra.source.full_sheet`) + istnienie `full_coverage/`.
- Biblioteka: `SheetFetch.full_link: Path | None`,
  `DownloadResult.full_links: dict[str, Path]` (godlo -> sciezka
  `full_coverage/`), `DownloadResult.without_full: tuple[str, ...]`
  (godla, dla ktorych z `full_sheet=True` skorowidz nie ma lotu pelnego
  w przedziale).

### 5.4 Przedzial lat (F-U3)

Kandydaci pochodza z lotow zadania (w przedziale), ale "nigdy wstecz"
moze zostawic `full_coverage/` przy nowszym pelnym locie spoza
przedzialu. Wtedy: dowiazanie bez zmian, `SheetFetch.full_link_outside_range:
Path | None`, `DownloadResult.full_link_outside_range: dict[str, Path]`,
`Info:` w CLI wspolny z istniejacym `Info:` U15 (jedna linia na arkusz,
wskazuje ktore drzewo). Kod wyjscia bez zmian.

## 6. Relacje z innymi torami

### 6.1 `--campaigns all`

Wszystkie loty z przedzialu lokalnie -> `full_coverage/` = najnowszy
pelny wsrod nich. Pomiar pokrycia i `Info:` 6.3 ADR-032 bez zmian.

### 6.2 LAZ

Bez `full_coverage/`: LAZ nie ma sciezki standardowej ani `kampanie/`;
ADR-029 juz traktuje kafle NIE jako niepokrywajace. `--full-sheet`
z `--product laz` = `Error:` przed siecia (wspolny punkt jak
`_reject_laz_only_opts`, odwrotny kierunek), kod 1.

### 6.3 Wycinki `--target-crs` (F-U4)

Mozaika ze sciezek standardowych, bez zmian. `--full-sheet`
z `--target-crs` = `Error:` przed siecia (jak `--campaigns all`,
ADR-030 errata 1 [Q2]), kod 1. Biblioteka `download_pl_cutout` bez
nowego parametru.

### 6.4 CZ, `--country auto`

Jak pozostale opcje kampanii (ADR-030 errata 3): `--full-sheet` dla CZ
bez PL = `Error:`; PL+CZ pod `auto` = `Info:` (CZ biezaca wersja),
flaga dziala dla arkuszy PL.

### 6.5 `FileStorage`

- `list_files(campaigns=False)` pomija tez `full_coverage/` (inaczej
  duplikaty w liscie plikow standardowych — zmiana konieczna).
- `delete(godlo)` usuwa takze dowiazanie `full_coverage/` + sidecar (oba
  to dowiazania; pliki w `kampanie/` zostaja).
- Bez nowego trybu listowania `full_coverage/` (brak konsumenta).

## 7. Sidecar

- `full_coverage/...meta.json`: kopia sidecara kampanii + `extra.link`,
  `extra.link_target` (identycznie jak standardowy; pochodzenie i
  `full_sheet: true` z kampanii).
- Sidecar kampanii dociagnietej: `request.full_sheet: true` (5.2).
- Sidecar standardowy: bez nowych pol (sciezka `full_coverage/` wynika
  z ukladu).

## 8. Testy i weryfikacja

Offline na nagraniach `tests/fixtures/gugik_skorowidz/real_2026_10_06/`
i `real_2026_10_10/` (C14: N-34-139-C-a-3-1 = 84183 NIE + 83233 TAK;
-4 = 84183 TAK; NMPT N-33-77-A-d-2-2 = 80195 TAK nowszy niz 84005 NIE):

| # | Scenariusz | Oczekiwane |
|---|---|---|
| F1 | -4, domyslnie (najnowszy TAK) | 1 plik; standard i `full_coverage/` = ten sam plik kampanii 84183 (hardlink, ten sam inode); bez komunikatu |
| F2 | -1, domyslnie | 1 plik (84183); brak `full_coverage/`; `Warning:` "pelny lot nie pobrany ... --full-sheet" |
| F3 | -1, `--full-sheet` | 2 pliki (84183, 83233); standard -> 84183, `full_coverage/` -> 83233; `Warning:` "pelny lot w full_coverage/"; sidecar 83233 `request.full_sheet: true`; "Downloaded 2 campaign files for 1 sheets" |
| F4 | -1, `--campaigns all` (bez flagi) | `full_coverage/` -> 83233 (najnowszy TAK wsrod 4 lotow) |
| F5 | powtorzenie F3 bez `--force` | Skipped, oba dowiazania bez zmian, bez pobrania; ten sam `Warning:` |
| F6 | F2 po F3 (bez flagi, lot pelny lokalnie z poprzedniego zadania) | `full_coverage/` bez zmian (kandydatow brak w tym zadaniu — dowiazanie nietkniete); `Warning:` "pelny lot w full_coverage/" (z istnienia dowiazania) |
| F7 | arkusz bez zadnego lotu TAK z `--full-sheet` | brak `full_coverage/`; "brak pelnego lotu w skorowidzu"; `without_full` |
| F8 | nigdy wstecz: po F4 `--full-sheet --max-year` z wczesniejszym pelnym lotem | `full_coverage/` zostaje; `Info:` (5.4) |
| F9 | hardlink niedostepny | kopia w `full_coverage/`, `Warning:` o kopii; `linked_campaign` rozpoznaje cel |
| F10 | `list_files()`, `delete()` | bez plikow z `full_coverage/` i `kampanie/`; `delete` usuwa oba dowiazania, `kampanie/` zostaje |
| F11 | I-1 | `full_coverage/` nietkniete |
| F12 | `--full-sheet` z `--product laz` / `--target-crs` / CZ | `Error:` kod 1 przed siecia; pod `auto` PL+CZ `Info:` |
| F13 | NMPT N-33-77-A-d-2-2 `--full-sheet` (najnowszy TAK) | 1 plik 80195, flaga bez skutku |

Na zywo (katalog danych wskazuje uzytkownik): F1, F2, F3, F5 na C14
i orto M-34-90-C-b-4-4 (84466 NIE 2026, 81437 TAK 2024); raport w
`docs/research/<data>-full-sheet-link/raport.md`.

Dokumentacja przy wdrozeniu: nowy ADR-033 (drzewo `full_coverage/`,
regula, `--full-sheet`, decyzje F-U1..F-U5), errata ADR-030 (d) (drugie
dowiazanie) i ADR-032 (flaga), ARCHITECTURE 3.3 i 4.1, USAGE 4.x,
SCOPE 2.12, `--help`, CHANGELOG `[0.7.2]`.

## 9. Pytania otwarte

Brak — Q1-Q5 rozstrzygniete 2026-10-10 (sekcja 0).
