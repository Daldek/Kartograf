# Spec: Uklad katalogow data/ per produkt + --target-crs dla PL (tryb bbox)

**Data:** 2026-08-28
**Status:** projekt zatwierdzony w rozmowie 2026-08-28 (wariant A + pionowy
zawsze jawnie + target-crs PL jako wycinek); spec do review uzytkownika
**Wersja docelowa:** 0.7.0 (develop, przed tagiem)
**Dokumenty zrodlowe:**
- ADR-017 (PL-2000; odroczony uklad `nmt_2000_<res>` — domykany tutaj)
- ADR-022 (architektura zrodel wielokrajowych, deskryptory)
- ADR-023 (dyspozycja per kraj, `--country auto`, `extra.parent_request`)
- ADR-024 (reprojekcje wylacznie lokalnie, przypieta operacja)
- `docs/research/2026-08-10-niemcy-dgm-atkis.md` (federacja 17 modeli DE —
  glowny argument skalowania ukladu katalogow)

---

## 1. Kontekst i cel

Dzisiejszy uklad `data/` jest plaski i niespojny: podkatalogi polskie nie
niosa kraju ani ukladu (`nmt_1m/`, `nmpt/`), czeskie niosa kraj w prefiksie
(`cz_dmr5g/`), PL-2000 dzieli katalog z PL-1992 (odroczenie z ADR-017),
a uklad pionowy nie jest kodowany wcale — ten sam arkusz w KRON86
i EVRF2007 to JEDNA sciezka (drugie pobranie: skip albo nadpisanie).
Dodanie zrodel niemieckich (federacja per-land, kilkanascie zrodel dla
samego DEM) rozsadziloby korzen katalogu.

Rownolegle: `--target-crs` istnieje tylko dla CZ. Scenariusz "obszar
zainteresowania w jednym kraju + dociagniecie danych z drugiego" wymaga
dzis warpa PL po stronie konsumenta — asymetria bez powodu innego niz
historia implementacji.

Cel:
1. **Nowy uklad `data/`**: `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]/...`
   — kazdy segment zrodlowy jawnie koduje kraj, uklad wspolrzednych
   (poziomy system godel/CRS i pionowy), wariant produktu.
2. **`--target-crs` dla PL w trybie bbox/geometry**: jeden scalony wycinek
   (mozaika arkuszy + crop + lokalny warp przypieta operacja), symetrycznie
   do CZ; na obszarze transgranicznym `--country auto --target-crs` daje
   dwa wycinki gotowe do nalozenia.
3. **Dokumentacja**: nowy `docs/ARCHITECTURE.md` (kanoniczny opis warstw,
   kontraktow i ukladu danych) + aktualizacja calego `docs/`.

## 2. Decyzje zatwierdzone przez uzytkownika (2026-08-28)

| # | Decyzja | Rozstrzygniecie |
|---|---------|-----------------|
| D1 | Struktura | Wariant A: `data/<produkt>/<segment>/...`; `landcover/` bez zmian |
| D2 | Uklad poziomy w segmencie | ZAWSZE jawnie dla PL (`pl_1992_*`, `pl_2000_*`) — dotyczy wszystkich produktow, nie tylko NMT |
| D3 | Uklad pionowy w segmencie | ZAWSZE jawnie (`_kron86`/`_evrf2007`/`_bpv`); jedynym produktem bez pionowego jest orto (zdjecia) |
| D4 | CZ bez dopisku ukladu poziomego | `cz_dmr5g`/`cz_dmr4g` — nazwa datasetu wyznacza uklad 1:1 (natywnie zawsze 5514); dopisek bylby redundancja |
| D5 | Rozdzielczosc w segmencie | tylko tam, gdzie jest parametrem API (NMT/NMPT `--resolution`); nie dla CZ (dmr5g=>2m z definicji) ani orto/laz (brak parametru) |
| D6 | `--target-crs` dla PL | TAK, wchodzi w zakres; semantyka "jeden wycinek" (sekcja 6) |
| D7 | Timing | wszystko w 0.7.0, przed tagiem (uklad cz_* i plaski bbox nigdy nie wyjda w starej formie) |
| D8 | PL-2000 | osobne segmenty `pl_2000_*` — domyka odroczony ADR-017 (strefy 2176-2179 vs 2180) |

## 3. Nowy uklad data/ — mapa kanoniczna

```
data/
├── nmt/
│   ├── pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
│   ├── pl_1992_1m_kron86/...
│   ├── pl_1992_5m_evrf2007/...             # 5m tylko EVRF2007 (regula istniejaca)
│   ├── pl_1992_1m_evrf2007/bbox/<coords>.tif   # NOWE: wycinek --target-crs (sekcja 6)
│   ├── pl_2000_1m_evrf2007/6/179/12/20/6.179.12.20.asc
│   ├── cz_dmr5g_bpv/302/5550/302_5550.tif
│   ├── cz_dmr5g_bpv/bbox/<coords>.tif      # wycinki bbox CZ (po fixie ed939a0)
│   ├── cz_dmr5g_evrf2007/...
│   └── cz_dmr4g_bpv/CTES/96/CTES96.tif
├── nmpt/pl_1992_1m_evrf2007/...            # (+ _kron86, + pl_2000_...)
├── orto/pl_1992/...                        # bez pionowego
├── laz/pl_2000_evrf2007/...                # poziomy per kafel (LazTile.crs), pionowy z flagi
└── landcover/...                           # bez zmian (wlasny default --output)
```

Reguly:
- Segment: `<kraj>_<uklad>[_<wariant>][_<vcrs>]`, wartosci lowercase.
  Uklad PL: `1992`/`2000`. Pionowy: `kron86`/`evrf2007`/`bpv`.
- Hierarchia wewnatrz segmentu: bez zmian (`parser_registry.path_parts`).
- Podkatalog `bbox/` wewnatrz segmentu: wycinki z trybu `--bbox`
  (`<coords><ext>`, wspolrzedne w ukladzie WYNIKU — konwencja z fixu
  ed939a0, teraz wspolna dla PL i CZ).
- Przyszle zrodla (DE): nowy wpis deskryptora wystarcza, np.
  `nmt/de_bb_dgm1_dhhn2016/` — zero zmian w kodzie sciezek.

**Tabela migracji (BREAKING, do CHANGELOG):**

| Stara sciezka | Nowa sciezka |
|---|---|
| `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
| `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
| `nmt_5m/` | `nmt/pl_1992_5m_evrf2007/` |
| `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
| `orto/` | `orto/pl_1992/` |
| `laz/` | `laz/pl_<uklad>_<vcrs>/` |
| `cz_dmr5g/` (0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
| `cz_dmr4g/` (0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

`<vcrs>` przy migracji recznej: odczytac z sidecara (`vertical_crs`);
pliki sprzed etapu 0 nie maja sidecarow — wtedy re-download albo wiedza
wlasna uzytkownika (odnotowac w CHANGELOG).

## 4. Szablony w deskryptorach (mechanika)

`SourceDescriptor.storage_subdir` staje sie **szablonem** z placeholderami
`{uklad}` i `{vcrs}`:

| Klucz deskryptora | Nowa wartosc `storage_subdir` |
|---|---|
| `pl.gugik.nmt_1m` | `"nmt/pl_{uklad}_1m_{vcrs}"` |
| `pl.gugik.nmt_5m` | `"nmt/pl_{uklad}_5m_{vcrs}"` |
| `pl.gugik.nmpt` | `"nmpt/pl_{uklad}_1m_{vcrs}"` |
| `pl.gugik.orto` | `"orto/pl_{uklad}"` |
| `pl.gugik.laz` | `"laz/pl_{uklad}_{vcrs}"` |
| `cz.cuzk.dmr5g` | `"nmt/cz_dmr5g_{vcrs}"` |
| `cz.cuzk.dmr4g` | `"nmt/cz_dmr4g_{vcrs}"` |
| bdot10k/corine/soilgrids | `None` (bez zmian) |

Nowa metoda `SourceDescriptor.resolve_subdir(*, uklad=None, vertical_crs=None) -> str`:
- wypelnianie przez `str.replace` (NIE `str.format` — czesciowe wypelnienie
  ma byc legalne: `{uklad}` moze zostac do rozwiazania pozniej);
- `vertical_crs` normalizowane `.lower()` (`"Bpv"` -> `"bpv"`);
- podanie wymiaru, ktorego szablon nie ma — no-op (orto ignoruje vcrs);
- wolajacy koncowy (FileStorage przy budowie sciezki) waliduje, ze w
  segmencie nie zostala zadna klamra `{` — inaczej `ValidationError`
  z nazwa brakujacego wymiaru.

## 5. Zmiany w komponentach (uklad katalogow)

### 5.1 `download/storage.py` — FileStorage
- Nowy parametr konstruktora `vertical_crs: str | None = "EVRF2007"`
  (addytywny; normalizowany lower do wypelnienia `{vcrs}`).
- `_RESOLUTION_SUBDIRS` -> szablony: `{"1m": "nmt/pl_{uklad}_1m_{vcrs}",
  "5m": "nmt/pl_{uklad}_5m_{vcrs}"}`. Nowa mapa `_PRODUCT_SUBDIRS`:
  `{"nmpt": "nmpt/pl_{uklad}_1m_{vcrs}", "orto": "orto/pl_{uklad}",
  "laz": "laz/pl_{uklad}_{vcrs}"}`; nieznany `product` — passthrough
  jak dzis (jawny `subdir=` tez, bez zmian).
- `{vcrs}` wypelniane w konstruktorze; `{uklad}` w `get_path`/
  `get_raw_path`/`ensure_directory`/`exists`/`delete` z identyfikatora:
  kropki -> `2000`, myslniki -> `1992` (ta sama regula co `path_parts`).
  Jesli po wypelnieniu zostaje `{` -> `ValidationError`.
- Docstringi struktury zaktualizowane (przyklad PL-2000 przestaje byc
  "shared", ADR-017 domkniety).

### 5.2 `download/manager.py` — DownloadManager
- Domyslny storage (gdy `storage=None`): subdir z
  `get_source(key).resolve_subdir(vertical_crs=self._vertical_crs)`
  (`{uklad}` zostaje do rozwiazania przez FileStorage per godlo);
  przekazuje tez `vertical_crs` do konstruktora FileStorage.

### 5.3 CLI PL — `_create_provider_and_storage`
- Przekazuje `vertical_crs` do FileStorage (nmt/nmpt); orto bez pionowego
  (szablon go nie ma). `{uklad}` rozwiazywany per godlo przez FileStorage —
  fabryka NIE musi znac systemu.

### 5.4 CLI CZ — `_cz_download_godlo` / `_cz_download_bbox`
- `descriptor.storage_subdir` -> `descriptor.resolve_subdir(
  vertical_crs=provider.vertical_crs)`; reszta przeplywu bez zmian
  (wycinki bbox laduja w `.../bbox/` — fix ed939a0 sklada sie
  automatycznie).

### 5.5 CLI LAZ — `_cmd_download_laz`
- Uklad poziomy per kafel, kaskada: (1) `LazTile.crs` (`"PL-2000:*"` ->
  `2000`, `"PL-1992*"` -> `1992`); (2) gdy `crs=None` — format godla
  kafla (kropki -> `2000`, myslniki -> `1992`); (3) gdy oba zawodza —
  `2000` z ostrzezeniem w logu (wspolczesne kafle GUGiK ciete sa
  w ukladzie 2000). `vertical_crs` z flagi CLI.
  Storage per rozwiazany segment (cache slownikowy na wypadek kafli
  z roznych ukladow w jednym zadaniu).

## 6. NOWE: `--target-crs` dla PL (tryb bbox/geometry, produkt nmt)

### 6.1 Semantyka
`kartograf download --bbox ... [--bbox-crs ...] --country pl --target-crs EPSG:XXXX`
zwraca **jeden plik**: `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`.

Przeplyw:
1. Walidacje (6.3). Bbox -> EPSG:2180 (istniejaca normalizacja) ->
   `find_sheets_for_bbox` -> pobranie arkuszy przez DownloadManager
   **normalnie do ich segmentow** (dzialaja jako cache; skip-existing
   standardowo). Kazdy failed arkusz = blad calosci (kod 1) — wycinek
   wymaga kompletu pokrycia.
2. `mosaic_and_crop(sheet_paths, bbox_2180, tmp)` — mechanizm istnieje
   (skleja dzis kafle CZ; domyka to zalegly punkt backlogu "Mozaikowanie
   arkuszy NMT PL" dla trybu bbox). Nodata: -9999 (ASC GUGiK).
3. Warp `rasterio.warp.reproject` z wymuszonym
   `PinnedTransform("EPSG:2180", target).gdal_operation()` —
   maszyneria i pulapki ADR-024 (axisswap dla celow northing-first!);
   fail-fast operacji w momencie startu przeplywu (przed siecia).
   `--target-crs EPSG:2180` => warp pomijany (sam crop, zapis GeoTIFF).
4. Nazwa pliku: `<coords>` w ukladzie WYNIKU (normalizacja bboxa do
   target przed nazwaniem — konwencja identyczna z CZ).
5. Sidecar CLI (nie manager): `horizontal_crs=target`,
   `transform.horizontal="pinned: ..."` (dla 2180: `transform: null`),
   `capability="bbox_raster"`, `nodata=-9999.0`, `request={bbox, bbox_crs
   (target)}`, `extra.parent_request` (zawsze w trybie bbox — ADR-023).

Bez `--target-crs` zachowanie PL bbox bez zmian (lista arkuszy natywnie).

### 6.2 Tryb auto (pogranicze)
Usuniecie blokady "PL + --target-crs" z walidacji dyspozycji
(`_resolve_pl_sentinels` i checklista `_dispatch_area`). Na obszarze
transgranicznym `--country auto --target-crs EPSG:2180 --vertical-crs
EVRF2007` daje DWA wycinki (PL i CZ) w tym samym ukladzie poziomym
i pionowym, wspolny `extra.parent_request` — scenariusz pogranicza
w jednej komendzie. Errata do ADR-023 (target-crs przestaje byc
flaga wylacznie czeska).

### 6.3 Walidacje (ValidationError / komunikat + kod 1)
- `--target-crs` + godlo (PL i CZ, bez zmian dla CZ): "dziala tylko
  z --bbox/--geometry".
- `--target-crs` + `--product nmpt|orto|laz`: "w 0.7.0 tylko nmt;
  nmpt/orto — etap 2" (laz to chmura punktow, warp rastrowy nie dotyczy).
- `--target-crs` + `--system 2000`: blad z remedium "uzyj domyslnego
  1992" — bbox wielostrefowy dalby arkusze w roznych CRS
  (2176-2179), mozaika miedzystrefowa = etap 2.
- Walidacja wartosci target (nieznany CRS / brak przypietej operacji):
  komunikat z `TransformError.remedy` — jak CZ.

## 7. Obsluga bledow — pozostale
Bez zmian wzgledem stanu obecnego; nowe komunikaty wylacznie z sekcji 6.3.
Blad zapisu sidecara pozostaje warningiem (kontrakt etapu 0).

## 8. Strategia testowa (TDD)
- **Szablony/deskryptory:** `resolve_subdir` (wypelnianie czesciowe,
  normalizacja lower, no-op dla nieznanego wymiaru); rejestr — nowe
  wartosci `storage_subdir` (aktualizacja asercji w
  `test_sources_registry.py`).
- **FileStorage:** nowe sciezki 1992/2000 x kron86/evrf2007; walidacja
  nierozwiazanej klamry; passthrough nieznanego productu; `delete()`
  z sidecar em w nowym ukladzie (`test_storage.py`).
- **CLI/manager:** aktualizacja asercji sciezek (`test_cli.py`,
  `test_download_manager.py`, `test_parallel_download.py`,
  `test_integration.py`); LAZ: mapowanie `uklad_xy` -> segment +
  fallbacki (`test_gugik_laz.py`/`test_cli.py`).
- **PL wycinek:** (a) regresja TRESCI wzorem ADR-024 — syntetyczne
  arkusze, asercja polozenia wierzcholka po warpie < 1 px od wzorca
  pyproj; (b) mozaika 2 arkuszy z nodata na styku; (c) target 2180 =
  crop bez warpa, `transform: null`; (d) walidacje 6.3; (e) auto-split
  z target-crs: dwa wycinki + wspolny parent_request; (f) failed arkusz
  => kod 1, bez pliku wycinka.
- **Brama jakosci:** pelna suita offline, `ruff check`, `ruff format
  --check`, `mypy` vs baseline 32 — zero nowego dlugu.

## 9. Zgodnosc wsteczna
- **BREAKING (uklad na dysku):** tabela migracji w sekcji 3 -> CHANGELOG
  0.7.0 Breaking Changes. Hydrograf odporny (konsumuje `Path`-y z API
  + `rglob`), Hydrolog nie zalezy od sciezek.
- **API:** sygnatury publiczne bez zmian poza addytywnymi
  (`FileStorage(vertical_crs=)`, `SourceDescriptor.resolve_subdir`).
  Zwracane typy bez zmian; PL bbox z `--target-crs` to NOWA sciezka
  wynikowa (jeden plik), stara semantyka (lista arkuszy) nietknieta
  bez flagi.
- **Sidecar:** schema `kartograf-meta/1` bez zmian pol; nowy wariant
  wartosci (`transform.horizontal="pinned: ..."` dla wycinka PL).
- **Deskryptory:** `storage_subdir` zmienia semantyke (szablon) —
  odnotowac w ADR-026; konsument zewnetrzny czytajacy to pole wprost
  dostanie szablon (swiadomy trade-off, pole bylo dotad de facto
  wewnetrzne).

## 10. Dokumentacja (zakres obowiazkowy)
1. **`docs/ARCHITECTURE.md` — NOWY.** Kanoniczny opis architektury;
   konspekt:
   - 1. Przeglad i zasady projektowe (deskryptory-jako-dane; sidecar
     obowiazkowy przy kazdym pobraniu; polityka transformacji ADR-024:
     ballpark ban, przypiete operacje, pulapka osi; brak scalania
     miedzykrajowego — kontrakt z Hydrografem);
   - 2. Warstwy i zaleznosci modulow (diagram tekstowy: core / sources /
     transform / transport / providers / cache / download / landcover /
     hydrology / auth / cli);
   - 3. Kontrakty danych: SourceDescriptor (w tym szablony subdir),
     schema sidecara, **kanoniczna tabela ukladu `data/`** (README
     i CLAUDE.md odsylaja tutaj zamiast duplikowac), `parent_request`
     jako klucz grupowania/wyszukiwania;
   - 4. Przeplywy per produkt (godlo PL, bbox PL z/bez target-crs,
     CZ godlo/bbox, LAZ, landcover) — po jednym akapicie + sciezka
     wynikowa;
   - 5. Jak dodac nowe zrodlo/kraj (checklist na przykladzie DE:
     deskryptor + profil kraju + parser godel + provider + testy);
   - 6. Indeks ADR z jednozdaniowymi streszczeniami.
2. **CLAUDE.md:** kolejnosc czytania dokumentacji + ARCHITECTURE.md;
   sekcja struktury data/ (odeslanie do ARCHITECTURE + skrot);
   przyklady CLI (`--target-crs` dla PL i pogranicze jedna komenda);
   ograniczenia (usunac "target-crs tylko CZ", dodac wylaczenia 6.3);
   korekta nieaktualnej wzmianki o podkatalogu `nmt_2000_1m`.
3. **README.md:** drzewo data/ (skrot + odeslanie), przyklady CLI,
   tabela sidecara (wiersz dla wycinka PL).
4. **docs/SCOPE.md:** uklad storage (2.x), target-crs PL in-scope,
   known limitations (2000+target-crs, nmpt/orto etap 2).
5. **docs/CHANGELOG.md:** Breaking (uklad data/ + tabela migracji +
   nota o plikach bez sidecarow), Added (`--target-crs` PL,
   `ARCHITECTURE.md`, `resolve_subdir`, `FileStorage(vertical_crs=)`),
   Changed (szablony subdir); korekta przykladu sciezki we wpisie
   o `bbox/` z ed939a0 (nowy segment).
6. **docs/DECISIONS.md:** ADR-026 (uklad data/: motywacja DE, reguly
   segmentow, szablony w deskryptorach, decyzje D1-D8); ADR-027
   (`--target-crs` PL: semantyka wycinka, mozaika+pinned warp,
   wylaczenia); errata ADR-017 (domkniety — pkt D8); errata ADR-023
   (target-crs uniwersalny w trybie bbox).
7. **docs/PROGRESS.md:** sesja + backlog (sekcja 11).
8. **docs/PRD.md / DEVELOPMENT_STANDARDS.md:** bez zmian merytorycznych
   (PRD to snapshot 0.6.1 z nota o CZ przy wydaniu 0.7.0 — uklad data/
   opisze ARCHITECTURE.md; w DS ewentualnie liczby plikow testowych).

## 11. Backlog etapu 2 (dopisywany przy tej zmianie, poza zakresem 0.7.0)
- `find_downloaded(product=, bbox=, vertical_crs=)` — inwentarz pobran
  po sidecarach (klucz: `parent_request` / przeciecie bbox).
- `--target-crs` dla `nmpt`/`orto` (razem z odpowiednikami CZ etapu 2).
- Wycinek PL dla `--system 2000` (mozaika miedzystrefowa: warp per
  strefa przed sklejeniem).
- Ujednolicenie `parent_request.bbox_crs` miedzy trybami jawny/auto
  (pozycja istniejaca — powiazac z `find_downloaded`).
- Nota dla Hydrografa: funkcja `harmonize_dem(files, target_crs,
  resolution)` na bazie `kartograf.transform.crs.PinnedTransform`
  (NIE golego pyproj — lekcja ADR-024); wejscie z sidecarow.

## 12. Ryzyka i mitygacje
- **Churn testow sciezkowych** (najwiekszy koszt): zmiany mechaniczne;
  plan wyliczy pliki i wzorce zamian per zadanie.
- **Pominiety konsument `storage_subdir` liczacy na literal:** grep
  calego repo w planie (`storage_subdir` uzywany dzis w manager.py,
  download_cmd.py x3, testach) — kazde uzycie przechodzi na
  `resolve_subdir`.
- **Operacja 2180->target bez siatek** na maszynie uzytkownika:
  fail-fast z `TransformError.remedy` (wzor CZ), test na znanym celu
  5514.
- **Wydanie tuz po audycie:** pelna brama jakosci + syntetyczne testy
  tresci; zmiana nie dotyka torow zweryfikowanych live poza sciezkami
  zapisu (E2E live sciezek nowego ukladu — pozycja w checklist release,
  pkt 12 PROGRESS).

## 13. Kryteria akceptacji
1. Pelna suita offline zielona; ruff/format czyste; mypy <= 32.
2. `kartograf download N-34-130-D-d-2-4` -> `data/nmt/pl_1992_1m_evrf2007/...`;
   `--vertical-crs KRON86` -> `..._kron86/...`; godlo `6.179.12.20` ->
   `data/nmt/pl_2000_1m_evrf2007/...`.
3. `--product nmpt/orto/laz` -> odpowiednio `nmpt/pl_1992_1m_evrf2007/`,
   `orto/pl_1992/`, `laz/pl_2000_evrf2007/` (LAZ wg `uklad_xy` kafla).
4. CZ: godlo TM33 -> `nmt/cz_dmr5g_bpv/...`; `--vertical-crs EVRF2007`
   -> `nmt/cz_dmr5g_evrf2007/...`; bbox CZ -> `.../bbox/<coords>.tif`.
5. PL bbox + `--target-crs EPSG:5514` -> jeden GeoTIFF
   `nmt/pl_1992_1m_evrf2007/bbox/<coords>.tif`, tresc w miejscu wg
   wzorca pyproj (< 1 px, test syntetyczny); `EPSG:2180` -> crop bez
   warpa, `transform: null`.
6. Pogranicze: `--country auto --target-crs EPSG:2180 --vertical-crs
   EVRF2007` -> dwa wycinki (PL+CZ) w 2180/EVRF2007, wspolny
   `parent_request`, kod 0.
7. Walidacje 6.3 daja czytelne bledy (godlo, nmpt/orto/laz, system 2000).
8. `docs/ARCHITECTURE.md` istnieje wg konspektu 10.1; pozostale
   dokumenty zaktualizowane wg sekcji 10; CHANGELOG z tabela migracji.
