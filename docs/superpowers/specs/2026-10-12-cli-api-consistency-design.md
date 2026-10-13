# Spec: Spojnosc CLI, biblioteki i API (0.8.0)

**Data:** 2026-10-12
**Status:** ZAAKCEPTOWANY przez uzytkownika 2026-10-12 (z decyzjami S1-S6
wg propozycji w sekcji 7; kryterium sekcji 1 poprawione o pola czasowe)
**Galaz:** `chore/cli-api-consistency` (z `develop` `d5215e8`)
**Wersja docelowa:** 0.8.0 (zmiany lamiace API i CLI w tym samym wydaniu
co magazyn wersjonowany)
**Dokumenty zrodlowe:**
- `docs/research/2026-10-12-cli-api-consistency/raport.md` (R1-R13, dowody)
- decyzje uzytkownika 2026-10-12: R1-R5, R7, R11-R13 zatwierdzone; R3
  usunac `stat` z HSG; R6 wariant B; R9 jezyk polski, wymuszone ASCII;
  R12 biblioteka domyslnie z cache jak CLI
- ADR-023 (kraje, `--country auto`), ADR-031 (angielskie identyfikatory),
  ADR-036 (magazyn wersjonowany, plan `kartograf-plan/1`)
- `docs/DEVELOPMENT_STANDARDS.md` 9.4 (jezyk), 11 (wyjatki)

---

## 1. Cel i kryterium akceptacji

To samo zadanie podane przez CLI albo przez publiczne API (te same
wartosci, ta sama tresc zrodla, ten sam moment wykonania) daje:

- te same pliki, katalogi wersji i sidecary — bajtowo, w tym
  `extra.parent_request`;
- te same statusy wersji (`new`, `relabeled`, `unchanged`, `local`,
  `reused`) i ten sam plan `kartograf-plan/1`;
- ten sam typ bledu i ten sam tekst bledu;
- te same komunikaty o danych (CLI je wypisuje, API zwraca w wyniku).

Pola zalezne od chwili wykonania nie sa roznica CLI/API, tylko faktem
przebiegu: `downloaded_at` sidecara, etykieta wersji `downloaded` (data
UTC, takze w nazwie katalogu wersji zrodel bez kampanii i wydania) oraz
`checked_at` planu. Dwa przebiegi w roznych chwilach roznia sie nimi
niezaleznie od sposobu uruchomienia. Testy zgodnosci zamrazaja zegar
(jedno zrodlo czasu wstrzykiwane w `sources/sidecar.py`,
`download/versions.py` i `download/updates.py`) i porownuja wszystko
bajtowo, bez wyjatkow.

CLI rozni sie od API tylko forma wyjscia: stdout/stderr, pasek postepu,
kod wyjscia wyliczony z wyniku. Kryterium pilnuja testy zgodnosci (Z7).

## 2. Stan wyjsciowy (skrot raportu)

- Logika danych tylko w CLI: `--country auto` (`cli/download_cmd.py`
  `_dispatch_area` 895-1016), walidacja `--system`/`--scale`
  (`_pl_option_error` 346-452), `parent_request` (806-823), `--geometry`
  i `--bbox-crs` poza arkuszami PL, arkusz CZ (`download/cz_sheets.py` poza
  `__all__`), BDOT10k z wielu powiatow dla bbox/godla
  (`cli/landcover_cmd.py` 283-303; `LandCoverManager.download(bbox=)` w
  bibliotece daje jeden powiat albo `ValidationError`).
- Cztery ksztalty wyniku i planu (arkusze PL: `Path | list[Path]` +
  `last_result`/`last_sheet`; wycinki/LAZ: `plan=` tylko w `run_*`; land
  cover/HSG: `plan=` w wywolaniu; `check_*` z roznymi argumentami).
- Cache: CLI `MetadataCache(cwd/.kartograf_cache.db)`, biblioteka
  `cache=None`; `--force` odswieza cache, `update="force"` nie.
- 36 x `raise ValueError` obok 122 x `raise ValidationError`; CLI ma na to
  obejscia `except ValueError`.
- Jezyk `--help` i komunikatow mieszany PL/EN; jeden komunikat z polskimi
  znakami.

## 3. Zasady (staja sie regulami w STANDARDS)

**Z1. CLI tylko tlumaczy.** Komenda CLI = zamiana flag na argumenty
funkcji biblioteki poziomu komendy (sekcja 4) + wypisanie jej wyniku.
W `kartograf/cli/` NIE wolno: walidowac wartosci danych, wybierac krajow,
arkuszy, skali, kampanii ani powiatow, budowac `parent_request`, czytac
sidecarow w celu decyzji. Wolno: parsowac tekst flag (`--bbox`,
`pl=..,cz=..`, `--layers`), czytac i zapisywac plik planu, formatowac
wynik, wyliczac kod wyjscia z pol wyniku, rysowac postep z `on_progress`.

**Z2. Para `download`/`check`.** Kazda publiczna funkcja pobierajaca ma
blizniaka `check_*` z tymi samymi argumentami bez `update`, `plan`,
`workers`, `on_progress`. Kazda funkcja pobierajaca przyjmuje `update=`
i `plan=`.

**Z3. Komunikaty o danych powstaja w bibliotece.** Wynik ma pole
`notices: tuple[Notice, ...]` (`Notice(level: "info" | "warning", code:
str, text: str)`). CLI wypisuje `Info: <text>` / `Warning: <text>` na
stderr (takze z `-q`). Biblioteka NIE loguje dodatkowo tych samych
komunikatow (jedno zrodlo tekstu; usuwa tez podwojna linie ostrzezenia I-1
z "Otwarte drobne" ADR-030).

**Z4. Wyjatki (R6, wariant B).** Bledne wejscie = `ValidationError`
(`ParseError` dla godel), problem zrodla = `DownloadError`
(`NoCoverageError`, `YearRangeError`), cache = `CacheError`. Bledy
wewnetrznych niezmiennikow (bledy programu) zostaja wbudowane
(`ValueError`, `RuntimeError`); nieznany argument = `TypeError`
(konwencja Pythona). `ValidationError` NIE dziedziczy z `ValueError`
(wariant A zmienilby po cichu ~25 wewnetrznych `except ValueError`).

**Z5. Jezyk (R9).** `--help`, komunikaty CLI i teksty wyjatkow biblioteki
(trafiaja do CLI 1:1 jako `Error:`) — po polsku, wylacznie ASCII (bez
znakow diakrytycznych). Nazwy flag, parametrow i wartosci — po angielsku
(ADR-031). Docstringi i komentarze — po angielsku (bez zmian). `metavar`
jednolicie po polsku: `PLIK`, `KATALOG`, `GODLO`, `BBOX`, `ROK`.

**Z6. Cache metadanych (R12).** Domyslnie CLI i biblioteka uzywaja tego
samego `MetadataCache` w `<cwd>/.kartograf_cache.db` (TTL 7 dni).
Parametr `cache` funkcji publicznych: `MetadataCache` (ten), `True`
(domyslny, w cwd), `False` (bez cache). `update="force"` = bez odczytow
z cache w tym wywolaniu (zapisy odswiezaja wpisy) — tak samo w CLI
i bibliotece. Ryzyko: proces biblioteki z cwd tylko do odczytu dostaje
cache wylaczony z `Notice` (zachowanie `on_disabled` jak dzis w CLI);
Hydrograf podaje wlasny `MetadataCache` i nie jest dotkniety.

**Z7. Testy zgodnosci (R13).** Scenariusze offline na fixturach
uruchamiane przez `kartograf.cli.main([...])` i przez API; porownanie
plikow, sidecarow, statusow, planu, `notices` i typu/tekstu bledu.
Lista scenariuszy: sekcja 6.

## 4. API poziomu komend

Jedna funkcja na komende CLI; nazwy parametrow = nazwy flag w
`snake_case`, te same wartosci dopuszczalne.

### 4.1 `kartograf download` <-> `download_data` / `check_data`

```python
def download_data(
    *,
    product: str,                        # nmt | nmpt | orto | laz
    output_dir: str | Path,
    sheet: str | None = None,            # PL-1992, PL-2000, CZ SM5, CZ TM33
    bbox: BBox | None = None,            # dowolny obslugiwany CRS (BBox.crs)
    geometry: Path | None = None,
    layer: str | None = None,
    country: str | None = None,          # pl | cz | auto; wymagane z bbox/geometry
    vertical_crs: str | Mapping[str, str] | None = None,  # {"pl": .., "cz": ..}
    resolution: str | Mapping[str, str] | None = None,
    system: str | None = None,           # 1992 | 2000
    scale: str | None = None,
    target_crs: str | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 4,
    cache: MetadataCache | bool = True,
    on_progress: Callable[[DownloadProgress], None] | None = None,
) -> DataReport: ...

def check_data(...) -> UpdatePlan: ...   # te same argumenty bez update/plan/workers/on_progress
```

Cala dzisiejsza walidacja i orkiestracja `download_cmd.py` przechodzi do
biblioteki (`kartograf/download/data.py`): rozpoznanie godla i kraju,
`--country auto` z zawezeniem do PL (`_pl_only_flags`), walidacja opcji
dla kazdego kraju przed pobraniem, wartosci per kraj, rozwiniecie obszaru
PL na arkusze (PL-1992 zawsze 1:10000, PL-2000 `scale`), `parent_request`,
czesciowy sukces `auto` (ADR-023 pkt 4-5).

`DataReport`:

| Pole | Znaczenie |
|---|---|
| `files: tuple[UnitFile, ...]` | `UnitFile(unit, country, file: VersionedFile)`; `unit` = godlo / kafel / sciezka wycinka wzgledem `output_dir` |
| `failed: tuple[UnitFailure, ...]` | `UnitFailure(unit, country, error: str, kind)`; `kind` = `no_coverage` / `download` / `country` |
| `stale: tuple[PlanItem, ...]` | pozycje planu zmienione od planu |
| `superseded: tuple[SupersededLazTile, ...]` | LAZ |
| `notices: tuple[Notice, ...]` | Z3 (podpowiedzi pokrycia, I-1, lepsze pokrycie, dowiazania poza zakresem, all-nodata, rozmiar wycinka, zawezenie `auto`, przyciecie do krajow, CORINE podglad itd.) |
| `ok: bool` | regula kodu wyjscia liczona w bibliotece (dzisiejsze `_finish_pl_sheets`, `_dispatch_area`) |

CLI: `kod = 0 if report.ok else 1`.

### 4.2 `kartograf landcover download` <-> `LandCoverManager.download` / `.check`

- `download(*, teryt=None, sheet=None, bbox=None, geometry=None,
  layer=None, update=None, plan=None, workers=..., **options)` zawsze
  zwraca `LandCoverAreaResult` (`files`, `failed`, `stale`, `notices`,
  `ok`). BDOT10k z `bbox`/`sheet`/`geometry` = kazdy powiat obszaru (jak
  dzis CLI). `download_all_counties`/`check_all_counties` znikaja
  (wchlonione).
- `bbox` w dowolnym obslugiwanym CRS (przeliczenie w bibliotece);
  `geometry` = obwiednia geometrii.
- Opcje BDOT10k `layers`, `keep_raw` dostaja flagi CLI `--layers`
  (lista kodow po przecinku), `--keep-raw`; CLI dostaje tez `--bbox-crs`,
  `--workers`, `--quiet` (R7).

### 4.3 `kartograf soilgrids hsg` <-> `HSGCalculator.calculate_hsg` / `.check_hsg`

- `calculate_hsg(*, sheet=None, bbox=None, geometry=None, layer=None,
  depth, update=None, plan=None, timeout=120) -> HsgResult` i `check_hsg`
  (te same argumenty bez `update`/`plan`). Zastepuja
  `calculate_hsg_by_bbox/sheet` i `check_hsg_by_bbox/sheet`.
- Bez `stat` (R3): HSG zawsze ze statystyki `mean`; `HsgResult.notices`.
- CLI: `--bbox-crs`, `--quiet` (R7).

### 4.4 Funkcje torow (nizszy poziom, publiczne)

Zostaja publiczne, wspolna regula Z2; `download_data` je wola.

| Tor | Pobranie | Sprawdzenie | Zmiana |
|---|---|---|---|
| Arkusze PL | `DownloadManager.download_sheets(sheets, *, update, plan, on_progress) -> DownloadResult` | `DownloadManager.check_sheets(sheets) -> UpdatePlan` | `download_sheet`/`download_hierarchy` zwracaja `DownloadResult`; `last_result`, `last_sheet`, `check_updates()`, `upgrade()`, `UpgradeReport` usuniete; `DownloadResult.stale`, `.notices`; `DownloadManager(year=)` |
| Wycinek PL | `download_pl_cutout(bbox, *, target_crs, output_dir, vertical_crs, product, update, plan, parent_request, cache)` | `check_pl_cutout(bbox, *, target_crs, output_dir, vertical_crs, product)` | `target_crs` keyword-only; `plan=` |
| Wycinek CZ | `download_cz_cutout(bbox, *, output_dir, target_crs, vertical_crs, resolution, update, plan, parent_request, cache)` | `check_cz_cutout(` te same `)` | `plan=`; `check_cz_cutout` bez providera i `image_crs` |
| Arkusz CZ | `download_cz_sheet(sheet, *, output_dir, vertical_crs, resolution, update, plan, cache)` | `check_cz_sheet(` te same `)` | NOWE publiczne (R4; errata decyzji 9 planu 2/3) |
| LAZ | `download_laz_area(bbox, *, output_dir, vertical_crs, year, min_year, max_year, all_campaigns, min_density, update, plan, workers, parent_request, cache)` | `check_laz_area(` te same bez `update/plan/workers` `)` | `bbox` w dowolnym CRS; `plan=`; `max_workers` -> `workers` |

Z `__all__` znikaja kroki wewnetrzne: `prepare_pl_cutout`,
`run_pl_wcs_cutout`, `PlCutout`, `run_cz_cutout`, `run_laz_download`,
`check_laz_updates`, `check_updates`, `upgrade`, `UpgradeReport`.
Dochodza: `download_data`, `check_data`, `DataReport`, `UnitFile`,
`UnitFailure`, `Notice`, `download_cz_sheet`, `check_cz_sheet`,
`check_laz_area`, `get_overall_bbox`, `transform_bbox`.

`find_sheets_for_bbox`/`find_sheets_for_geometry` zostaja narzedziami
geometrii bez ograniczenia skali (Hydrograf uzywa ich do list godel);
regula "PL-1992 tylko 1:10000" nalezy do `download_data` (korekta R5
raportu).

### 4.5 `parse`, `cache`

Bez zmian w 0.8.0 (R8 pozniej); `cache` korzysta ze sciezki Z6.

## 5. Kolejnosc prac (zadania planu)

| # | Zadanie | Punkty raportu |
|---|---|---|
| T0 | `README.md:83` `result.file.path` | R10 |
| T1 | Wyjatki wg Z4: `ValueError` -> `ValidationError` w sciezkach wejscia, usuniecie obejsc CLI, STANDARDS 11 | R6 |
| T2 | Cache wg Z6: `cache: MetadataCache | bool`, `force` bez odczytow cache | R12 |
| T3 | Funkcje torow wg 4.4 (wynik, `plan=`, blizniaki `check_*`, arkusz CZ, LAZ w dowolnym CRS, `year`) | R2, R4 |
| T4 | Land cover i HSG wg 4.2-4.3 (bez `stat`, `geometry`, wszystkie powiaty, `notices`) | R3, R7 (biblioteka) |
| T5 | `Notice` i `DataReport`; `download_data`/`check_data` z logika przeniesiona z CLI | R1, R5, R11 |
| T6 | CLI jako tlumacz (Z1) dla `download`, `landcover`, `soilgrids`; flagi R7 | R7, R11 |
| T7 | Jezyk wg Z5: `--help`, komunikaty, teksty wyjatkow; test ASCII; STANDARDS 9.4 | R9 |
| T8 | Testy zgodnosci wg Z7 (rosna od T3; komplet po T6) | R13 |
| T9 | Dokumentacja: ADR-037 (CRLF), errata decyzji 9 planu 2/3, ARCHITECTURE, USAGE, README, CHANGELOG [0.8.0] BREAKING z "Co zrobic", STANDARDS | — |
| T10 | Weryfikacja na zywo (katalog danych od uzytkownika) | — |

T7 po T6, bo T6 przepisuje wiekszosc komunikatow; wczesniej nowy tekst
od razu po polsku ASCII.

## 6. Scenariusze zgodnosci (Z7)

Arkusz PL-1992 1:10000; godlo grubsze (rozwiniecie); PL-2000 ze `scale`;
obszar PL `system=1992`; obszar PL `system=2000`; `geometry` PL;
kampanie (`all_campaigns`, `min_year`, `full_sheet`); wycinek PL
`target_crs`; arkusz CZ SM5 i TM33; wycinek CZ; `country="auto"`
(PL+CZ, zawezenie do PL, czesciowy sukces); LAZ (`bbox` w EPSG:4326,
`min_density`); `check_*` + plan + `upgrade` z planem (tez nieaktualny
plan); BDOT10k `teryt` i obszar wielu powiatow; CORINE (CLMS i podglad);
SoilGrids; HSG (`bbox`, `geometry`); bledy wejscia (brak wymaganej
wartosci, zla wartosc, bbox poza krajami) — ten sam typ i tekst.

## 7. Decyzje do akceptacji

| # | Decyzja | Propozycja | Alternatywa |
|---|---|---|---|
| S1 | Nazwy funkcji poziomu komendy `download` | `download_data` / `check_data` | `download` koliduje z podpakietem `kartograf.download` |
| S2 | Kroki wewnetrzne (`prepare_pl_cutout`, `run_*`, `check_laz_updates`, `check_updates`, `upgrade`) | usunac z `__all__` (BREAKING) | zostawic jako drugi poziom API (wiecej do utrzymania i do testow zgodnosci) |
| S3 | `LandCoverManager.download` | zawsze `LandCoverAreaResult`; `download_all_counties` wchlonione | dwie metody i decyzja w wywolujacym (lamie Z1) |
| S4 | HSG | `calculate_hsg`/`check_hsg` z `sheet`/`bbox`/`geometry` | zostawic `*_by_bbox/sheet` i dodac `*_by_geometry` |
| S5 | Parametr `cache` | `MetadataCache | bool`, domyslnie `True` (cwd) | `MetadataCache | None` + osobny `no_cache: bool` |
| S6 | Teksty wyjatkow biblioteki | po polsku ASCII (Z5), bo trafiaja do CLI 1:1 | po angielsku, CLI tlumaczy (CLI znowu ma wlasna logike) |

## 8. Wplyw na Hydrograf i Hydrolog

Hydrograf (stan repo `../Hydrograf`, 2026-10-12): `scripts/download_dem.py`
(`DownloadManager.download_sheets` + `last_result`, wlasny
`MetadataCache` — dostosowanie do `DownloadResult` z wartosci zwracanej),
`core/cn_calculator.py` i `scripts/bootstrap.py` (`HSGCalculator` —
`calculate_hsg`, bez `stat`), `scripts/download_landcover.py`
(`LandCoverManager` — `LandCoverAreaResult`), lapanie `ValueError`
z providerow (Z4). `find_sheets_for_bbox/geometry` i `SheetParser` bez
zmian. Hydrolog: do sprawdzenia przed wydaniem (bez importow
`kartograf` w `../Hydrolog` wg wyszukiwania 2026-10-12).
