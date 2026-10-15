# Plan C - silniki `unit_package` i `feature_bbox`, dane PL - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-15

**Wersja docelowa:** 0.8.0 (razem z manifestem projektu i planami A, B, D,
E; bez wydania posredniego).

**Goal:** Generyczne silniki kanalow sterowane deskryptorem -
`unit_package` (paczka ZIP per jednostka TERYT albo kraj z szablonu URL)
i `feature_bbox` (WFS / ArcGIS REST -> jeden GPKG w ukladzie natywnym) -
z jednym orkiestratorem kolekcji na magazynie wersji (ADR-036), oraz
produkty PL: archiwum BDOT10k (`landcover download --source bdot10k
--year R`), modele 3D budynkow (`models3d`), granice PRG (`boundaries`)
i EGiB (`cadastre`). Plan D dodaje na tych samych silnikach dane CZ
i `atom_files`.

**Architecture:** `AccessChannel.params` (nowe pole, dane bez IO) niesie
typowana konfiguracje kanalu: `UnitPackageParams` / `FeatureBBoxParams`
(plan D dopisze `AtomFilesParams` i `WcsCutoutParams`). Silniki: `kartograf/transport/unit_package.py`
(URL, pobranie, walidacja ZIP, rozpakowanie jednego czlonu),
`kartograf/transport/feature_bbox.py` (liczba obiektow, strony, dedupe,
kontrola kompletnosci, bledy uslug), `kartograf/transform/gpkg.py`
(deterministyczny GPKG z odpowiedzi przez `pyogrio`). Orkiestrator
`kartograf/download/collections.py`: walidacja bez sieci, wybor kanalu
z rodzaju wyboru, jednostki (TERYT z PRG dla obszaru), sloty, wersje,
sidecar, plan `kartograf-plan/1` (tor `collection`), raport
`CollectionReport`. CLI: nowe moduly grup `cli/groups/{boundaries,cadastre,models3d}.py`
(ADR-039 D2) i wspolny handler `cli/collection_cmd.py`; `landcover`
dostaje `--year` dla BDOT10k. Decyzje: ADR-042 (tekst w tym planie,
sekcja "ADR-042").

**Spec:** `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`
(K5-K8, sekcje 5, 6 plan C, 7, 8, 9.3); rekonesans
`docs/research/2026-10-15-plan-c-d/raport.md` (fakty uslug, liczby,
pulapki - czytaj przed Task 3 i 4); inwentaryzacja
`docs/research/2026-10-13-katalog-produktow/{raport,probki,bdot10k-archiwum}.md`;
manifest `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`
sekcja 5 i plan manifestu (Task 2, "Integracja"). Kontrakty: ADR-036
(magazyn), ADR-037 (CLI = API), ADR-039 (grupy), ADR-040 (manifest),
ADR-041 (rejestr wariantow, plan A - jesli scalony).

**Galaz:** `feat/plan-c` z aktualnego `develop`. Kolejnosc wdrozen A-B-C-D
(spec 9.1): kod planow A/B (ADR-041) jest zwykle juz scalony; plan C nie
korzysta z rejestru wariantow, ale dzieli pliki `sources/registry.py`,
`sources/descriptor.py` i `tests/test_sources_registry.py` - konflikty
rozwiaz na korzysc stanu po A/B. Integracja do `develop` - koordynator.

---

## Global Constraints

- Python z `.venv` uruchamiany z korzenia worktree; brama przed kazdym
  commitem: `python -m pytest tests/ -m "not live" -q`, `python -m ruff
  check .`, `python -m ruff format --check .`, `python -m mypy kartograf/
  tests/`. Conventional Commits po polsku, autor `Daldek
  <git@debever.pl>` bez `Co-Authored-By`; commit wylacznie przez straznik
  wzorcow `! git diff --cached -U0 | grep '^+' | grep -qiEf
  "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit ...`
  (brak pliku wzorcow = zatrzymaj sie i zapytaj).
- Angielskie identyfikatory i docstringi; teksty `Notice` i wyjatkow po
  polsku ASCII (Z5); `ValidationError` przed siecia dla wejscia,
  `DownloadError` dla zrodla, `NoCoverageError` gdy zrodlo poprawnie
  odpowiada, ale nie ma danych jednostki/obszaru (STANDARDS 11). Zadnego
  `print` w bibliotece - komunikaty przez `Notice`/`NoticeSink`.
- CLI tylko tlumaczy (ADR-037): moduly `kartograf/cli/` nie importuja
  `kartograf.providers` ani logiki wyboru
  (`tests/test_cli_translation.py::test_cli_imports_no_data_logic`).
- Zero wartosci domyslnych wplywajacych na dane (K8): wariant (rok,
  format, LoD, poziom) wymagany, gdy zrodlo publikuje wiecej niz jeden;
  plik krajowy tylko przez jawne `--whole-country` (K7).
- Kazdy plik wyniku przez `FileSlot` + `use_local`/`store_file`/
  `fetch_version`/`inspect_version` (`kartograf/download/fetch.py`),
  sidecar wersji wylaczny (`emit_sidecar(..., exclusive=True, digest=,
  version=)`), dowiazanie twarde; bez drugiej polityki skip/retry/wersji.
- Testy offline z fixtur prawdziwych odpowiedzi (`tests/fixtures/pl/...`,
  male, przyciete do kilku obiektow); `tests/conftest.py::_block_network`
  (autouse) dowodzi braku sieci; testy `live` oznaczone `@pytest.mark.live`.
  Asercje na statusach, `Notice.code`, bajtach plikow, sidecarach
  i typach wyjatkow - nie na tekstach (wyjatek: zgodnosc CLI = API).
- Dane live wylacznie poza repo i `/tmp`, jawne `--output
  <katalog-danych>`; rzeczywista sciezka nie trafia do repo, testow,
  dokumentow ani commitow. Cache metadanych CLI w korzeniu worktree.
- `docs/DECISIONS.md` ma CRLF - zachowaj przy edycji (STANDARDS 5.5).

## Zweryfikowane punkty zaczepienia (develop `bcdf37d`, numery linii orientacyjne)

| Symbol | Miejsce | Fakt istotny dla planu |
|---|---|---|
| `TransportKind`, `SignalKind`, `AccessChannel`, `SourceDescriptor` | `kartograf/sources/descriptor.py:18-113` | `AccessChannel` ma `transport`, `horizontal_crs`, `vertical_crs_options`, `vertical_source`, `server_reprojection`, `capabilities`, `notes`, `endpoint`, `update_signal`; **brak `params`**. `TransportKind.DIRECT_FILES/WFS/ARCGIS_QUERY` juz istnieja. |
| `_SOURCES`, `_COUNTRIES`, `_GUGIK_LICENSE`, `_CUZK_LICENSE` | `kartograf/sources/registry.py` (`pl.gugik.bdot10k` ok. 206-226) | BDOT10k: jeden kanal `DIRECT_FILES`, `admin_unit_files`, `none`, `storage_subdir="landcover/pl_bdot10k"`. `_COUNTRIES["PL"].dataset_keys` liczone z kluczy `pl.*`. |
| `get_source`, `channel_signal`, `sources_for` | `registry.py:406-436` | `channel_signal(key, transport)` zwraca sygnal PIERWSZEGO kanalu danego transportu - nowe deskryptory z dwoma kanalami `DIRECT_FILES` maja ten sam sygnal (`none`). |
| `FileSlot`, `VersionedFile`, `use_local`, `store_file`, `fetch_version`, `inspect_version` | `kartograf/download/fetch.py:68-351` | `FileSlot(output_dir, std, versions_base, versions_root, ext)`; `store_file(slot, staged, *, version, write_sidecar, http, signal, coverage=False)`. |
| `commit_version`, `list_versions`, `VersionRef`, `ContentDigest` | `kartograf/download/versions.py:57-477` | Kandydaci tej samej tresci tylko z `list_versions(root, name)` JEDNEGO slotu (`same = [...]`, ok. l. 412); `relabeled` + `same_as` (etykieta) istnieja. |
| `bbox_cutout_path`, `bbox_slot` | `kartograf/download/storage.py:672-703` | `bbox/<coords .10g>` w ukladzie wyniku, wersje `versions/bbox/`. |
| `landcover_segment`, `selection_slot`, `selection_unit` | `kartograf/landcover/store.py:32-92` | Segment `<storage_subdir>_<tokeny>`; `selection_slot` przyjmuje bbox wylacznie w EPSG:2180. Pakiet `download` nie moze importowac `landcover` (ARCHITECTURE 2). |
| `LandCoverManager.download/check/_check_options`, `_SOURCE_OPTIONS`, `_OPTIONS`, `_REQUIRED` | `kartograf/landcover/manager.py:85-100, 353, 475, 612-668` | `year` dzis tylko CORINE; BDOT10k: `format` domyslnie `GPKG`, `layers`/`keep_raw` tylko GPKG; obszar -> powiaty z PRG, bledy per powiat w `failed`. |
| `discover_teryts_for_bbox` | `kartograf/providers/pl/prg.py:275` | Powiaty przecinajace bbox (WFS PRG, cache WFS). |
| `WOJEWODZTWO_NAMES`, `Bdot10kProvider` | `kartograf/providers/pl/bdot10k.py:94-111, 144` | Biezace paczki BDOT10k zostaja w providerze (scalanie GPKG); archiwum idzie silnikiem. |
| `SessionPerThread`, `get_with_retry`, `head_signal`, `download_to` | `kartograf/transport/http.py:88-230` | `download_to(..., validate=, save=, on_response=)` atomowo; ponowienia sieci/429/5xx (`MAX_RETRIES=3`). |
| `Track`, `PlanItem`, `UpdatePlan`, `select_planned` | `kartograf/download/plan.py:28-143` | `Track` = `Literal["pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout", "landcover", "hsg"]`. |
| `UnitFile`, `UnitFailure`, `DataReport` | `kartograf/download/data.py:109-140` | Elementy raportu do ponownego uzycia w `CollectionReport`. |
| `build_metadata`, `emit_sidecar` | `kartograf/sources/sidecar.py:176, 333` | Kanal wybierany przez `capability`; `exclusive=True` dla sidecara wersji. |
| `register_groups`, `add_group`, `add_list_sources` | `kartograf/cli/groups/__init__.py` | Grupa = modul z `register(subparsers)`; `list-sources` z rejestru. |
| `add_area_flags`, `add_update_flags`, `add_quiet`, `parse_bbox_arg` | `kartograf/cli/_args.py` | `--sheet/--bbox/--bbox-crs/--geometry/--layer` (warstwa pliku geometrii) - wspolne dla grup. |
| `_dispatch` | `kartograf/cli/commands.py:37-58` | Wola `_handler`; `--plan` wymaga trybu. |
| `run_both`, `assert_same_store`, `assert_notices_printed` | `tests/parity.py` (uzywane w `tests/test_parity.py`) | Wzorzec testu CLI = API na wspolnym magazynie. |
| `CHANNEL_SIGNALS` | `tests/test_sources_registry.py:43-67` | Inwentarz (klucz, transport, sygnal) kazdego kanalu - kazdy nowy kanal musi tu trafic. |

## ADR-042 (tekst do `docs/DECISIONS.md`, Task 1)

Wstaw wpis przed "Szablon nowego ADR" (CRLF), dopisz wiersz indeksu
i odsylacze w statusach ADR-015, ADR-036, ADR-039, ADR-040 (np. ADR-036:
"uzupelniona przez ADR-042 (D23 miedzy wydaniami; wycinek orto
w magazynie - czesciowo zastepuje D27)"). Decyzje D12-D17 dotycza planu
D; zapisz je teraz (jedna decyzja dla calego podprojektu), a plan D
tylko weryfikuje zgodnosc i dopisuje errate przy odstepstwie.

```markdown
## ADR-042: Silniki kanalow (unit_package, feature_bbox, atom_files) i dane planow C/D

**Data:** 2026-10-15
**Status:** Przyjeta; uzupelnia ADR-015 (zapis GPKG przez pyogrio; odczyt obwiedni bez zmian), ADR-036 (D23 miedzy wydaniami; czesciowo zastepuje D27 - wycinek orto w magazynie), ADR-039 (grupy boundaries, cadastre, models3d, hydro) i ADR-040 (pozycje komend projektu)

**Kontekst:** Spec katalogu (K5-K7) wymaga, by produkt z raportu byl
wpisem deskryptora i konfiguracja kanalu, nie providerem. Plany C i D
wnosza paczki per jednostka administracyjna (archiwum BDOT10k, modele 3D,
PRG, EGiB), obiekty dla obszaru z WFS i ArcGIS REST (PRG, EGiB, RUIAN,
HY-NET, ZABAGED) i pliki wskazywane feedem ATOM CUZK (ortofoto, ZABAGED
kraj). Rekonesans 2026-10-15 wykazal: bledne linki `next` w obu
serwerach WFS, duplikat obiektu na koncu stron MapServer, kolejnosc osi
zgodna z EPSG u obu dostawcow, zmienne w czasie pole EGiB `DATA`, GML
z krzywymi, URL-e z rokiem/data w nazwie (tylko z feedu).

**Opcje:**
- A) Provider per produkt (wzorzec `providers/pl/*.py`).
- B) Generyczne silniki sterowane typowanymi parametrami kanalu
  w deskryptorze + jeden orkiestrator kolekcji na magazynie wersji.
- C) Jeden ogolny "pobierz URL" bez typowanych parametrow.

**Decyzja:** B.
- D1. `AccessChannel.params: UnitPackageParams | FeatureBBoxParams |
  AtomFilesParams | WcsCutoutParams | None` (dane bez IO, niemutowalne;
  dwa ostatnie w planie D). Silniki:
  `transport/unit_package.py`, `transport/feature_bbox.py`,
  `transport/atom.py` (plan D), zapis GPKG `transform/gpkg.py`,
  orkiestracja `download/collections.py`. Nowy produkt = deskryptor
  z parametrami kanalu (+ wybor w CLI).
- D2. Rodzaj wyboru wyznacza kanal: `teryt` (2 cyfry = woj., 4 = powiat)
  -> `unit_package` tej jednostki; obszar (`bbox`/`sheet`/`geometry`) ->
  `feature_bbox`, a gdy produkt go nie ma - powiaty z PRG i paczka na
  powiat; `whole_country` -> plik krajowy (`unit_package` jednostki
  `country` albo `atom_files`) wylacznie jawnie, z rozmiarem z `HEAD`/
  feedu w `Notice` przed transferem (K7). Dokladnie jeden wybor; wariant
  (rok, format, LoD, poziom, uklad pliku krajowego) wymagany, gdy zrodlo
  publikuje wiecej niz jeden (K8), a przy jednym przyjmowany tylko rowny
  opublikowanemu. Uklad pliku wybiera `--horizontal-crs` (ADR-038; API
  `horizontal_crs`): wymagany, gdy kanal ma kilka ukladow (pliki krajowe
  CUZK 5514/3045); wynik obszaru jest zawsze w ukladzie natywnym uslugi.
- D3. Kompletnosc `feature_bbox` z liczby, nie z linkow: WFS
  `RESULTTYPE=hits`, ArcGIS `returnCountOnly` -> N; strony
  `STARTINDEX`/`resultOffset` (ArcGIS z `orderByFields`); `next`
  ignorowany; dedupe po polu identyfikatora kanalu (identyczny duplikat
  pominiety, rozny = `DownloadError`); unikalnych != N albo
  `numberMatched="unknown"` = `DownloadError`; HTML, `ExceptionReport`,
  JSON `error` przy HTTP 200 = `DownloadError`. N = 0 we wszystkich
  warstwach = `NoCoverageError` (bez pliku); pusta warstwa obok
  niepustych = warstwa ze schematem bez obiektow.
- D4. Kolejnosc osi BBOX jest parametrem kanalu z testem na prawdziwej
  odpowiedzi: GUGiK `urn:...:EPSG::2180` = N,E, CUZK EPSG:5514 = X,Y
  (obie zgodne z EPSG); zamiana daje pusty wynik bez bledu.
- D5. Wynik `feature_bbox`: jeden GPKG w ukladzie natywnym uslugi
  (DefaultCRS), pelne geometrie obiektow przecinajacych obszar (bez
  przycinania), warstwa na warstwe zrodla; bajty deterministyczne
  (obiekty po identyfikatorze, schemat z metadanych uslugi, staly
  `OGR_CURRENT_DATE`); pola zalezne od chwili odpowiedzi (`drop_fields`,
  EGiB `DATA`) poza GPKG, w sidecarze `extra.source.response_date`;
  skladanie na dysku lokalnym, potem staging magazynu. Nowa zaleznosc
  `pyogrio` (GDAL wektorowy).
- D6. Magazyn i sygnaly: kazdy plik przez `FileSlot` i
  `use_local`/`store_file`/`fetch_version`/`inspect_version`; sygnal =
  `update_signal` kanalu: paczki GUGiK i wszystkie wyniki WFS/REST
  `none`, pliki CUZK `http`, pliki z feedu ATOM `metadata`. Etykieta:
  produkty z wydaniem w segmencie (rocznik BDOT10k, rok modeli 3D) -
  wydanie (`label_source="edition"`), pozostale `downloaded`.
- D7. D23 miedzy wydaniami: `FileSlot.related_roots` - gdy w slocie nie
  ma wersji o tym sha256, szukana jest w slotach pokrewnych (inne wydania
  tego produktu, formatu i jednostki); trafienie = dowiazanie twarde do
  istniejacych danych, status `relabeled`, `same_as` = etykieta
  znalezionej wersji (spec 9.3: identyczne roczniki bez duplikatu).
- D8. Uklad `data/` (rozszerzenie reguly 8): `<grupa>/<kraj>_<zrodlo>
  [_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>}<ext>`; `coords`
  w ukladzie natywnym (`.10g`), tokeny `[a-z0-9.-]`, plik krajowy
  `country/pl` albo `country/cz`; wersje w `<segment>/versions/<ta sama
  hierarchia>/`. Tokeny = wariant tresci (poziom, LoD, rocznik): wynik
  obszaru (zawsze GPKG w ukladzie natywnym) bez tokenu formatu; paczka
  i plik krajowy z tokenem formatu zrodla, gdy produkt ma kilka formatow
  albo takze wynik obszaru, a gdy zrodlo publikuje plik w kilku
  ukladach - takze z kodem EPSG (doprecyzowanie przykladow specu 7:
  `boundaries/pl_prg_<poziom>/bbox/`, `landcover/cz_zabaged/bbox/`,
  `landcover/cz_zabaged_gpkg_5514/country/cz.zip`,
  `models3d/pl_buildings_lod1_<rok>/teryt/` bez formatu - jeden format,
  brak wyniku obszaru). Rozne tresci nigdy nie dziela slotu.
- D9. CLI (uzupelnienie ADR-039): grupy `boundaries`, `cadastre`,
  `models3d` (plan C) i `hydro` (plan D), modul na grupe z `download`
  i `list-sources`; wybor `--product` + `--country pl|cz|auto` (jak
  `elevation`/`imagery`; `landcover` zostaje z `--source`); `--teryt`,
  `--whole-country`, `--level` (granice dla obszaru; nazwy krajowe:
  PL `wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb`, CZ
  `kraj|okres|obec|katastralni-uzemi`; z `--country auto` w skladni per
  kraj `pl=gmina,cz=obec` jak `--resolution`), `--lod 1|2`, `--year`,
  `--horizontal-crs` (tylko gdzie plik krajowy ma kilka ukladow; plan D:
  `landcover --source zabaged`). Produkty: `admin` (PRG, RUIAN), `map`
  (EGiB - mapa ewidencyjna), `buildings` (modele 3D), `network`
  (HY-NET). Nowe produkty bez `--layers` (stala zawartosc). Parser
  kazdej komendy `download` ustawia `_handler` i `_task` (ADR-040).
- D10. Biblioteka: `download_collection`/`check_collection`
  (`CollectionReport`: `files` z `UnitFile`, `failed` z `UnitFailure`,
  `stale`, `notices`, `ok`), walidacja bez sieci
  `validate_collection_request`, tor planu `collection`. `landcover
  download` zostaje `LandCoverManager` (ADR-039 D8) i deleguje archiwum
  BDOT10k oraz ZABAGED do silnikow kolekcji.
- D11. Archiwum BDOT10k: `--year 2014..2025` z wymaganym `--format
  GML|SHP` (brak GPKG; z `--year` odrzucone `GPKG`, `--layers`,
  `--keep-raw`), ZIP 1:1, `landcover/pl_bdot10k_<format>_<rok>/teryt/<T>.zip`,
  etykieta = rok, `none`, D7 dla identycznych rocznikow; 404 powiatu
  (zmiana TERYT, brak paczki) = `NoCoverageError` tego powiatu.
- D12 (plan D). `atom_files`: feed uslugi ATOM -> feed zbioru -> link
  `alternate` z `length`; wpis wybierany wyrazeniem regularnym na id
  zbioru (grupy nazwane) albo jedyny zbior + kategoria CRS; wydanie
  (`metadata`) z `<updated>` wpisu; indeks feedu uslugi w MetadataCache
  odswiezany warunkowym GET (ETag).
- D13 (plan D). Ortofoto CZ: `imagery download --product orto
  --country cz` (arkusz albo obszar -> arkusze SM5 z indeksu), czlony
  ZIP bez konwersji pikseli jako `<godlo>.jpg`, `<godlo>.jgw` (S-JTSK),
  `<godlo>.TM33N.jgw`, `<godlo>.TM34N.jgw`, kazdy plik wersjonowany
  w `orto/cz_sjtsk/<hierarchia SM5>/`; etykieta `<rok>_<updated>`,
  sygnal `metadata`. Wzorzec godla SM5 przyjmuje 2 litery (As).
- D14 (plan D). Wycinek ortofotomapy PL z WCS w magazynie (czesciowo
  zastepuje ADR-036 D27): `imagery download --product orto --cutout
  --horizontal-crs EPSG:2180 --coverage standard|high --resolution
  0.1m|0.25m|0.5m|1m`, `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif`,
  `none`, bez maski ladu, kawalki do 4 Mpx natywnych, konfiguracja
  w `WcsCutoutParams` kanalu WCS; `GugikOrtoProvider.download_bbox`
  zostaje surowym API poza magazynem.
- D15 (plan D). ZABAGED: `landcover download --source zabaged`; obszar
  -> GPKG EPSG:5514 z 22 warstw pokrycia i hydrografii REST (nazwy =
  kody ASCII nazw warstw), `--whole-country --horizontal-crs
  EPSG:5514|EPSG:3045` -> krajowy `ZABAGED-<kod>-gpkg-<data>.zip`
  z feedu (`metadata`); bez mapowania klas na kody BDOT10k.
- D16 (plan D). Grupa `hydro`, `--product network` (HY-NET): obszar ->
  GPKG EPSG:5514 (3 typy WFS), `--whole-country` -> `HY-NET.zip`
  (EPSG:3045 wg feedu, `http`).
- D17 (plan D). RUIAN: `boundaries --product admin --country cz`; obszar
  -> REST warstwy 17/15/12/7, `--whole-country` -> `shp/stat/epsg-5514/1.zip`
  (`http`).

**Konsekwencje:** Kolejne produkty planu E wchodza jako deskryptory
z parametrami (nowy protokol, np. OGC API Features, rozszerza
`FeatureBBoxParams.protocol` razem z pierwszym produktem). `pyogrio`
dochodzi do zaleznosci (ok. 100 MB kola z GDAL obok GDAL `rasterio`).
Wynik WFS/REST jest migawka bez sygnalu: `--check-updates` raportuje
`unverifiable`, nowa tresc daje dopiero `--force`. Pliki krajowe moga
miec inny uklad niz wynik obszaru (HY-NET 3045 vs 5514) - sidecar podaje
faktyczny. Szczegoly i pomiary: `docs/research/2026-10-15-plan-c-d/raport.md`,
plany `docs/superpowers/plans/2026-10-15-plan-c-*.md`, `...-plan-d-*.md`.
```

## Kontrakt silnikow i orkiestratora

### Parametry kanalow (`kartograf/sources/descriptor.py`)

```python
@dataclass(frozen=True)
class PackageVariant:
    """One published package variant: choice values -> URL template."""
    choice: tuple[tuple[str, str], ...]  # (("format", "SHP"), ("year", "2024"))
    url_template: str                    # tokens: {teryt}, {woj} only
    edition: str | None = None           # version label (label_source "edition")
    segment_tokens: tuple[str, ...] = () # ("shp", "2024") | ("lod1", "2024") | ("gml",)
    members: tuple[str, ...] = ()        # required member suffixes (".shp")
    vertical_crs: str | None = None      # declared in the data (3D CityGML)

@dataclass(frozen=True)
class UnitPackageParams:
    unit: Literal["powiat", "woj", "country"]
    variants: tuple[PackageVariant, ...]
    unpack: str | None = None            # exactly one member with suffix -> file

@dataclass(frozen=True)
class FeatureLayer:
    code: str        # public value (--level) or fixed layer code
    source: str      # WFS typename "ms:A03_Granice_gmin" | ArcGIS layer id "12"
    name: str        # GPKG layer name
    id_field: str    # dedupe key: "IIP_IDENTY" | "gml_id" | "fid_zbg" | "objectid"

@dataclass(frozen=True)
class FeatureBBoxParams:
    protocol: Literal["wfs", "arcgis"]
    native_crs: str                      # "EPSG:2180" | "EPSG:5514"
    axis_order: Literal["xy", "yx"]      # "yx" = northing first in BBOX
    page_size: int                       # WFS CountDefault / ArcGIS <= maxRecordCount
    layers: tuple[FeatureLayer, ...]
    selection: Literal["level", "all"]   # one layer by --level | all layers
    order_field: str | None = None       # ArcGIS orderByFields (OBJECTID)
    drop_fields: tuple[str, ...] = ()    # response-time fields -> sidecar
```

`AccessChannel.params: UnitPackageParams | FeatureBBoxParams | None = None`
(plan D rozszerzy unie o `AtomFilesParams` i `WcsCutoutParams`). Walidacja w testach
rejestru: dozwolone tokeny szablonu wylacznie `{teryt}`, `{woj}`; kazdy
`PackageVariant` w kanale ma te same klucze `choice`; `edition`
i `segment_tokens` pasuja do `[a-z0-9.-]+`; `FeatureBBoxParams.protocol`
zgodny z `transport` (`WFS` -> `wfs`, `ARCGIS_QUERY` -> `arcgis`);
`page_size > 0`.

Korekta przy implementacji (2026-10-15): `members` jest polem
`PackageVariant`, nie `UnitPackageParams` - paczki GML (`.xml`) i SHP
(`.shp`) archiwum BDOT10k leza w jednym kanale, wiec wymagane czlony
zaleza od wariantu. Kazdy kanal kolekcji ma capability unikalna
w deskryptorze (`archive_unit_files`, `country_files`, `bbox_vector`,
`admin_unit_files`) - sidecar wybiera po niej kanal pliku.

### Silniki

- `kartograf/transport/unit_package.py`:
  `select_variant(params, **choice: str) -> PackageVariant` (brak klucza
  albo nieznana wartosc = `ValidationError` z lista dozwolonych
  wartosci, bez sieci); `package_url(variant, *, teryt: str | None) -> str`
  (`{woj}` = 2 pierwsze cyfry TERYT); `fetch_package(session, url,
  staged: Path, *, params, timeout) -> PackageFile(path, http, size)`
  - `download_to` z `validate` odrzucajacym HTML/XML przy 200, kontrola
  `Content-Length` = rozmiar pliku, centralny katalog ZIP czytelny,
  wymagane `members`; `unpack` = dokladnie jeden czlon o sufiksie
  rozpakowany strumieniowo (CRC sprawdza `zipfile`); HTTP 404 =
  `NoCoverageError`, inne bledy = `DownloadError`; nigdy cala paczka
  w RAM.
- `kartograf/transport/feature_bbox.py`:
  `count_features(session, endpoint, params, layer, bbox_native, *,
  timeout) -> int` i `fetch_features(session, endpoint, params,
  layers, bbox_native, pages_dir: Path, *, timeout) -> FeaturePages`
  (algorytm D3; strony zapisywane strumieniowo do `pages_dir/<warstwa>/<start>.gml|.json`).
  BBOX: WFS `BBOX=<a>,<b>,<c>,<d>,urn:ogc:def:crs:EPSG::<kod>` w
  kolejnosci `axis_order`, `SRSNAME` = ten sam URN, `COUNT`,
  `STARTINDEX`, `TYPENAMES`; ArcGIS `geometry=<xmin,ymin,xmax,ymax>`,
  `geometryType=esriGeometryEnvelope`, `inSR`/`outSR` = kod natywny,
  `spatialRel=esriSpatialRelIntersects`, `f=geojson`, `outFields=*`,
  `orderByFields`, `resultOffset`, `resultRecordCount`. Przed
  pierwszym `GetFeature`: `GetCapabilities` (cache metadanych; DefaultCRS
  porownywany po kodzie EPSG - `urn:ogc:def:crs:EPSG::2180` i
  `http://www.opengis.net/def/crs/EPSG/0/5514` to rozne zapisy) - typ
  istnieje i DefaultCRS = `native_crs`, inaczej `DownloadError`
  (bez podmiany); schemat pol: WFS `DescribeFeatureType` (XSD, cache),
  ArcGIS `/<id>?f=json` `fields`.
- `kartograf/transform/gpkg.py`: `write_gpkg(path: Path, layers:
  Sequence[LayerFeatures], *, crs: str) -> dict[str, int]` (liczba
  obiektow na warstwe) - `pyogrio.raw.read` stron (GML z
  `XSD=<plik>`, GeoJSON), dedupe po `id_field`, sort po `id_field`,
  usuniecie `drop_fields` (wartosci zwracane do sidecara),
  `pyogrio.raw.write(..., driver="GPKG", promote_to_multi=True)` przy
  `OGR_CURRENT_DATE="2000-01-01T00:00:00.000Z"` ustawionym przez
  `pyogrio.set_gdal_config_options` na czas zapisu; plik powstaje
  w `tempfile.mkdtemp()` (dysk lokalny), potem przeniesienie do
  stagingu slotu.

### Orkiestrator (`kartograf/download/collections.py`)

```python
def download_collection(
    *,
    product: str | None,
    output_dir: str | Path | None,
    country: str | None = None,          # "pl" | "cz" | "auto"
    teryt: str | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,            # layer of the geometry file
    whole_country: bool = False,
    level: str | Mapping[str, str] | None = None,  # per country with "auto"
    lod: int | None = None,
    year: int | None = None,
    horizontal_crs: str | None = None,  # CRS variant of a national file
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 1,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> CollectionReport

def check_collection(... ten sam wybor, bez update/plan/workers ...) -> UpdatePlan

def validate_collection_request(*, product, output_dir, country=None,
    teryt=None, sheet=None, bbox=None, geometry=None, layer=None,
    whole_country=False, level=None, lod=None, year=None,
    horizontal_crs=None) -> CollectionRequest

@dataclass(frozen=True)
class CollectionReport:
    files: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    notices: tuple[Notice, ...]
    ok: bool                             # no failed and no stale
```

- `validate_collection_request` (wolana jako pierwsza przez obie funkcje
  i przez pozycje projektu; zero sieci): `--bbox` jak dzis
  (`validate_request_bbox`); dokladnie jeden z `teryt`/`sheet`/`bbox`/
  `geometry`/`whole_country`; `product` z rejestru (deskryptory
  z kanalem kolekcji); `country` wymagane z obszarem i z
  `whole_country` (z `sheet` wynika z godla, z `teryt` = `pl`); produkt
  musi miec kanal dla rodzaju wyboru (np. `map` bez `whole_country`);
  wariant przez `select_variant`/poziomy `FeatureBBoxParams`;
  `horizontal_crs` wg D2 (wymagany przy kilku ukladach pliku, przy
  jednym tylko rowny, przy `feature_bbox` tylko natywny); TERYT
  `^[0-9]{2}$` albo `^[0-9]{4}$` zgodny z `unit` kanalu. Zwraca
  `CollectionRequest` (deskryptor, kanal, wariant, warstwy).
- Jednostki: `teryt` -> `[teryt]`; obszar + `feature_bbox` -> jeden
  obszar w ukladzie natywnym (`country_bbox`/`split_bbox_by_country`
  dla `auto`, `transform_bbox` dla innych ukladow; arkusz -> zasieg
  godla; geometria -> obwiednia jak w `landcover`); obszar bez
  `feature_bbox` -> `discover_teryts_for_bbox` (Notice `UNIT_LIST`
  z lista TERYT); `whole_country` -> `pl`/`cz` po `HEAD` (Notice
  `WHOLE_COUNTRY_SIZE` z bajtami; brak `Content-Length` = rozmiar
  "nieznany", nie blad).
- Slot: nowa `kartograf/download/storage.py::unit_slot(output_dir,
  segment, ext, *, teryt=None, bbox=None, sheet=None, country=None,
  related_roots=()) -> FileSlot` (logika przeniesiona z
  `landcover/store.py::selection_slot`, plus `country/<kod>` i bbox
  w dowolnym ukladzie natywnym); `landcover/store.py` wola ja
  (stara funkcja usunieta, wolajacy zmienieni - bez aliasu).
  Segment: `kartograf/download/storage.py::content_segment(key, tokens)`
  (logika `landcover_segment` przeniesiona; `landcover_segment`
  usuniety, wolajacy zmienieni); tokeny: `PackageVariant.segment_tokens`
  dla paczek, `FeatureLayer.code` przy `selection="level"`, brak przy
  `selection="all"` (D8); `storage_subdir` deskryptora = prefiks bez
  tokenow (`boundaries/pl_prg`, `cadastre/pl_egib`, `models3d/pl_buildings`).
- Plik: `fetch_version`/`use_local` + pobranie + `store_file` z
  `VersionRef(edition, "edition")` albo `VersionRef.downloaded()`,
  `signal` = `channel.update_signal`; sidecar `emit_sidecar(key, path,
  request=..., horizontal_crs=..., vertical_crs=..., capability=...,
  extra=..., digest=..., version=..., exclusive=True)` z
  `request` = wybor uzytkownika w jednostce (`teryt`/`bbox`+`bbox_crs`,
  `year`, `format`, `lod`, `level`) i `extra.source` = `url` albo
  `service`, `layers` (kod, zrodlo, liczba obiektow), `edition`,
  `response_date`; `extra.parent_request` dla obszaru rozlozonego na
  jednostki albo przeliczonego z innego ukladu/arkusza/geometrii
  (`parent_request_for`).
- Bledy per jednostka -> `UnitFailure(unit, country, error, kind)`
  (`kind`: `no_coverage` dla `NoCoverageError`, `download` dla
  `DownloadError`); pozostale jednostki dzialaja dalej
  (`ThreadPoolExecutor(workers)` jak BDOT10k). Pozycje planu: tor
  `collection`, `unit` = TERYT / wspolrzedne `_` / `pl`|`cz`.

## Matryca produktow planu C

| Wybor CLI | API | Deskryptor, kanal | Plik pod `--output` | Sygnal / etykieta |
|---|---|---|---|---|
| `landcover download --source bdot10k --year 2024 --format SHP --teryt 1261` | `LandCoverManager(o, "bdot10k").download(teryt="1261", year=2024, format="SHP")` | `pl.gugik.bdot10k`, nowy kanal `DIRECT_FILES` `archive_unit_files`: `UnitPackageParams(unit="powiat")`, 24 warianty `(format, year)` 2014-2025 x GML/SHP, `https://opendata.geoportal.gov.pl/Archiwum/bdot10k/<R>/<F>/{woj}/{teryt}_<F>_<R>.zip`, `members` `.shp` / `.xml` | `landcover/pl_bdot10k_shp_2024/teryt/1261.zip` | `none` / `2024` + D7 |
| `landcover download --source bdot10k --year 2018 --format GML --bbox ...` | `... .download(bbox=..., year=2018, format="GML")` | jw.; powiaty z PRG | `landcover/pl_bdot10k_gml_2018/teryt/<T>.zip` | `none` / `2018` |
| `models3d download --product buildings --lod 1 --year 2024 --teryt 1261` | `download_collection(product="buildings", lod=1, year=2024, teryt="1261", output_dir=o)` | `pl.gugik.buildings_3d` (`product="buildings"`), `DIRECT_FILES`: LoD1 2019 `.../Budynki3D/LOD1/2019/{woj}/{teryt}_gml.zip`, LoD1 2021/2022/2024 `.../LOD1/<R>/{woj}/{teryt}.zip`, LoD2 2017 `.../LOD2/{teryt}_gml.zip`; `members` `.gml`; `vertical_crs` per wariant | `models3d/pl_buildings_lod1_2024/teryt/1261.zip` | `none` / `2024` + D7 |
| `models3d download --product buildings --lod 2 --country pl --bbox ...` | `download_collection(product="buildings", lod=2, country="pl", bbox=...)` | jw. (LoD2 jedyny rocznik 2017 - `--year` zbedny, inny rok = blad) | `models3d/pl_buildings_lod2_2017/teryt/<T>.zip` | `none` / `2017` |
| `boundaries download --product admin --country pl --level gmina --bbox ...` | `download_collection(product="admin", country="pl", level="gmina", bbox=...)` | `pl.gugik.prg` (`product="admin"`), `WFS` `AdministrativeBoundaries`: poziomy `wojewodztwo`=A01, `powiat`=A02, `gmina`=A03, `jednostka-ewidencyjna`=A05, `obreb`=A06, `yx`, strona 1000, id `IIP_IDENTY` | `boundaries/pl_prg_gmina/bbox/<coords 2180>.gpkg` | `none` / pobranie |
| `boundaries download --product admin --teryt 12` | `download_collection(product="admin", teryt="12")` | `pl.gugik.prg`, `DIRECT_FILES` woj.: `https://opendata.geoportal.gov.pl/prg/granice/{woj}_GraniceAdministracyjne.zip`, `members` `.gml` | `boundaries/pl_prg_gml/teryt/12.zip` | `none` / pobranie |
| `boundaries download --product admin --country pl --whole-country` | `download_collection(product="admin", country="pl", whole_country=True)` | `pl.gugik.prg`, `DIRECT_FILES` kraj: `.../prg/granice/00_jednostki_administracyjne.zip` (377 MB), `members` `.shp` | `boundaries/pl_prg_shp/country/pl.zip` | `none` / pobranie |
| `cadastre download --product map --teryt 1261` | `download_collection(product="map", teryt="1261")` | `pl.gugik.egib` (`product="map"`), `DIRECT_FILES`: `https://opendata.geoportal.gov.pl/InneDane/latest_exports/eziudp_wfs/GPKG/{teryt}.gpkg.zip`, `unpack=".gpkg"` | `cadastre/pl_egib_gpkg/teryt/1261.gpkg` | `none` / pobranie |
| `cadastre download --product map --country pl --bbox ...` | `download_collection(product="map", country="pl", bbox=...)` | `pl.gugik.egib`, `WFS` `UslugaZbiorcza`: `ms:dzialki`, `ms:budynki` (`selection="all"`), `yx`, strona 1000, id `gml_id`, `drop_fields=("DATA",)` | `cadastre/pl_egib/bbox/<coords 2180>.gpkg` | `none` / pobranie |

Uwagi do matrycy: (1) PRG `--teryt 1261` = `ValidationError` ("PRG
publikuje paczki wojewodzkie: --teryt <2 cyfry> albo --whole-country;
obszar powiatu: --bbox/--geometry"); EGiB `--teryt 12` (paczka woj.
1,4 GB) poza zakresem - blad z podpowiedzia `--teryt <4 cyfry>`;
`models3d --whole-country` (LoD1 kraj 3,5 GB, LoD2 4,1 GB) poza
zakresem specu - blad z podpowiedzia. (2) LoD2 nie pokrywa kraju
(Szczecin 3262 = 404) - `NoCoverageError` powiatu w `failed`. (3)
Eksport EGiB zawiera tez warstwe `transakcje` (RCN) i jest odswiezany
co dobe - opis w USAGE; WFS EGiB to usluga zbiorcza (luki w powiatach
bez integracji, pola `brak_uprawnien`). (4) Uklad pionowy modeli 3D:
LoD1 2024 = EPSG:9651 (`urn:ogc:def:crs,crs:EPSG::2180,crs:EPSG::9651`),
LoD2 2017 = PL-KRON86-NH (EPSG:9650); lata 2019/2021/2022 zmierz w
Task 6 (pierwszy plik GML paczki z obiektami) i wpisz do wariantu.

---

### Task 1: ADR-042 i typowane parametry kanalow w rejestrze

**Files:**
- Modify: `kartograf/sources/descriptor.py`, `kartograf/sources/registry.py`,
  `tests/test_sources_registry.py`, `docs/DECISIONS.md` (CRLF)

- [ ] **Step 1: Testy (RED)** - `tests/test_sources_registry.py`:
  `test_collection_channels_are_typed` (kazdy kanal z `params`:
  `UnitPackageParams` przy `DIRECT_FILES`, `FeatureBBoxParams` przy
  `WFS`/`ARCGIS_QUERY` z protokolem zgodnym z transportem);
  `test_url_templates_use_known_tokens` (zaden `{...}` poza
  `{teryt}`/`{woj}`; warianty kanalu maja te same klucze `choice`;
  `edition` i `segment_tokens` pasuja do `[a-z0-9.-]+`); `test_feature_layers_unique`
  (kody i nazwy warstw unikalne w kanale, `page_size > 0`);
  `test_new_sources_registered` (`pl.gugik.prg`, `pl.gugik.egib`,
  `pl.gugik.buildings_3d` w `sources_for(country="PL")`, licencja
  `_GUGIK_LICENSE`, `product` = `admin`/`map`/`buildings`);
  `test_bdot10k_archive_is_channel_of_bdot10k` (jeden deskryptor
  `pl.gugik.bdot10k`, dwa kanaly `DIRECT_FILES`, `sources_for(product=
  "landcover")` nie ma klucza archiwum). Rozszerz `CHANNEL_SIGNALS`
  o wszystkie nowe kanaly z ich sygnalem (`none`).
- [ ] **Step 2: Implementacja** - dataclassy z sekcji "Kontrakt";
  `AccessChannel.params` (domyslnie `None`, istniejace kanaly bez
  zmian); wpisy rejestru z matrycy (warianty generowane wyrazeniem
  listowym z jawnych krotek lat/formatow - bez petli z IO);
  `pl.gugik.bdot10k` dostaje drugi kanal `DIRECT_FILES`
  (`capabilities={"archive_unit_files"}`, `endpoint` = katalog
  archiwum). `vertical_crs` wariantow 3D: tylko zmierzone (LoD1 2024,
  LoD2 2017); pozostale lata `None` do Task 6 (Step 0 mierzy i uzupelnia,
  test kompletnosci dochodzi tam - brama kazdego Taska zostaje zielona).
- [ ] **Step 3: ADR-042** - tekst z sekcji "ADR-042" do
  `docs/DECISIONS.md` (CRLF: edytuj narzedziem zachowujacym konce linii
  i sprawdz `file docs/DECISIONS.md` -> "with CRLF line terminators"),
  wiersz indeksu, statusy ADR-015/036/039/040.
- [ ] **Step 4: Brama i commit** - `feat(sources): parametry kanalow
  unit_package i feature_bbox, deskryptory PRG, EGiB, modeli 3D
  i archiwum BDOT10k (ADR-042)`

### Task 2: Magazyn - sloty jednostek i D23 miedzy wydaniami

**Files:**
- Modify: `kartograf/download/fetch.py` (`FileSlot.related_roots`,
  `store_file`), `kartograf/download/versions.py` (`commit_version(...,
  related_roots=())`), `kartograf/download/storage.py` (`unit_slot`,
  `content_segment`), `kartograf/landcover/store.py`,
  `kartograf/landcover/manager.py` (wolajacy), `kartograf/hydrology/hsg.py`
  (jesli wola `landcover_segment`)
- Test: `tests/test_versions.py` (albo istniejacy plik testow
  `commit_version`), `tests/test_landcover_store.py` (istniejacy plik
  testow `selection_slot`; nazwy sprawdz `grep -rn selection_slot tests`)

- [ ] **Step 1: Testy (RED)** -
  `test_commit_identical_in_related_slot_is_relabeled` (wersja `2022`
  w slocie A, ten sam sha256 zapisywany jako `2023` w slocie B z
  `related_roots=(A,)`: status `relabeled`, `same_as == "2022"`,
  `os.stat(...).st_ino` pliku B == pliku A, sidecar B z etykieta
  `2023`); `test_related_slot_ignored_when_own_version_matches`
  (wlasna wersja ma pierwszenstwo: `unchanged`);
  `test_related_slot_different_content_is_new`;
  `test_unit_slot_country_and_native_bbox` (`country/pl.zip`,
  `versions/country/`; bbox EPSG:5514 -> `bbox/<coords .10g>.gpkg`);
  dotychczasowe testy `selection_slot`/`landcover_segment` przeniesione
  na nowe nazwy bez zmiany asercji sciezek.
- [ ] **Step 2: Implementacja** - `FileSlot.related_roots:
  tuple[Path, ...] = ()`; `store_file` przekazuje do `commit_version`;
  w `commit_version` gdy `same` puste: kandydaci z `list_versions(r,
  name)` dla `r in related_roots` o tym samym sha256 -> `source =
  max(..., key=version_key).path`, `status = "relabeled"`, `same_as`
  = etykieta; reszta sciezki bez zmian (D22: brak hardlinku = blad).
  `unit_slot`/`content_segment` w `download/storage.py`; usun
  `selection_slot`/`landcover_segment` i popraw wszystkich wolajacych
  (`grep -rn "selection_slot\|landcover_segment" kartograf tests`).
- [ ] **Step 3: Brama i commit** - `feat(versions): sloty jednostek
  (teryt, bbox, country) i D23 miedzy wydaniami w slotach pokrewnych`

### Task 3: Silnik `unit_package`

**Files:**
- Create: `kartograf/transport/unit_package.py`, `tests/test_unit_package.py`,
  `tests/fixtures/pl/unit_package/` (naglowki `HEAD` z rekonesansu jako
  JSON; male ZIP-y z prawdziwymi nazwami czlonow z probek:
  `PL.PZGiK.283.1261/BDOT10k/PL.PZGiK.283.1261__OT_PTWP_A.xml`,
  `PL.PZGiK.283.1261__OT_PTWP_A.shp/.shx/.dbf/.prj/.cpg`, `1261.gpkg`
  jako najmniejszy poprawny GPKG zapisany przez `transform/gpkg.py`
  albo `tests/conftest.py::write_gpkg_layers`)

- [ ] **Step 1: Testy (RED)** - `test_select_variant_requires_each_key`
  (brak `year` -> `ValidationError` z lista 2014-2025, bez sieci; zly
  format -> lista `GML, SHP`; `GPKG` -> blad);
  `test_package_url_from_template` (2024/SHP/1261 ->
  `.../Archiwum/bdot10k/2024/SHP/12/1261_SHP_2024.zip`; LoD1 2019 ->
  sufiks `_gml`; PRG woj 12 -> `12_GraniceAdministracyjne.zip`);
  `test_fetch_package_rejects_html_200`, `..._rejects_truncated`
  (`Content-Length` > pobranych bajtow), `..._rejects_missing_members`
  (ZIP bez `.shp`), `..._404_is_no_coverage`;
  `test_unpack_single_member` (dokladnie jeden `.gpkg` rozpakowany,
  dwa albo zero = `DownloadError`, uszkodzony CRC = `DownloadError`,
  brak pliku wyniku po bledzie). Sesja-atrapa liczy wywolania.
- [ ] **Step 2: Implementacja** - funkcje z kontraktu na
  `download_to` (`validate=` odrzuca `text/html`/`<?xml` gdy
  oczekiwany ZIP), `zipfile.ZipFile` do kontroli katalogu i
  rozpakowania strumieniowego (`shutil.copyfileobj`), timeout jak
  BDOT10k (`Bdot10kProvider.DEFAULT_TIMEOUT = 120`).
- [ ] **Step 3: Brama i commit** - `feat(transport): silnik unit_package
  (paczki per jednostka z szablonu URL)`

### Task 4: Silnik `feature_bbox` i zapis GPKG

**Files:**
- Modify: `pyproject.toml` (`pyogrio>=0.10` w `dependencies`)
- Create: `kartograf/transport/feature_bbox.py`, `kartograf/transform/gpkg.py`,
  `tests/test_feature_bbox.py`, `tests/test_gpkg_writer.py`,
  `tests/fixtures/pl/feature_bbox/` (nagraj raz na zywo i przytnij:
  PRG `GetCapabilities` (fragment z A01-A06), `DescribeFeatureType`
  A03, `hits` i strony `COUNT=2` dla malego bboxa z 3-4 gminami, w tym
  strona za koncem z duplikatem; EGiB `hits` + 2 strony `COUNT=2`
  z krzywymi; odpowiedz HTML RCN (`UslugaZbiorcza` bez `SERVICE`)
  i `ExceptionReport`)

- [ ] **Step 0: Zaleznosc** - dopisz `pyogrio` do `pyproject.toml`
  i zainstaluj w `.venv` (`.venv/bin/python -m pip install -e .`);
  sprawdz `python -c "import pyogrio, rasterio"` w jednym procesie.
- [ ] **Step 1: Testy (RED)** - `test_wfs_axis_order_in_bbox` (PRG
  `yx`: parametr `BBOX=<N_min>,<E_min>,<N_max>,<E_max>,urn:...:2180`);
  `test_completeness_uses_hits_not_next` (fixtura PRG: strona bez
  `next` w srodku, duplikat na koncu -> komplet N unikalnych);
  `test_missing_features_is_download_error` (strony daja mniej niz
  `hits`); `test_conflicting_duplicate_is_download_error`;
  `test_unknown_hits_is_download_error`; `test_html_and_exception_report_are_download_errors`;
  `test_capabilities_change_is_download_error` (brak typu albo inny
  DefaultCRS); `test_all_layers_empty_is_no_coverage`;
  `test_gpkg_is_deterministic` (dwa zapisy tych samych stron = te
  same bajty; obiekty posortowane po id; `DATA` nieobecne w GPKG
  i zwrocone do sidecara); `test_gpkg_axes_and_crs` (EPSG:2180,
  pierwsza wspolrzedna = wschod; `ogr`-owy odczyt przez `pyogrio.read_info`);
  `test_curves_preserved_or_linearized_consistently` (EGiB
  CurvePolygon: GPKG czytelny, liczba obiektow zgodna).
- [ ] **Step 2: Implementacja** - silnik wg D3/D4 i kontraktu; GML
  czytany przez GDAL z `XSD` z `DescribeFeatureType` (spojne typy pol
  miedzy stronami), `GML_SKIP_RESOLVE_ELEMS=NONE`, bez pobierania
  schematow z sieci przez GDAL (`DOWNLOAD_SCHEMA=NO`); ArcGIS GeoJSON
  z typami z `fields`. Limity czasu jak skorowidze GUGiK (30-60 s na
  strone), ponowienia z `get_with_retry`.
- [ ] **Step 3: Brama i commit** - `feat(transport): silnik feature_bbox
  (WFS/ArcGIS, kompletnosc z liczby obiektow) i deterministyczny zapis GPKG`

### Task 5: Orkiestrator kolekcji

**Files:**
- Create: `kartograf/download/collections.py`, `tests/test_collections.py`
- Modify: `kartograf/download/plan.py` (`Track` += `"collection"`),
  `kartograf/notices.py` (`UNIT_LIST` info, `WHOLE_COUNTRY_SIZE`
  warning), `kartograf/__init__.py` (`download_collection`,
  `check_collection`, `CollectionReport` w `__all__`)

- [ ] **Step 1: Testy (RED)** na deskryptorach testowych
  (`monkeypatch` rejestru) i sesjach-atrapach z fixtur Task 3/4:
  `test_exactly_one_selection` (zero/dwa wybory - `ValidationError`
  przed jakimkolwiek zapytaniem); `test_variant_required_when_many`
  (bez `year` dla LoD1 - lista lat); `test_single_variant_needs_no_flag`
  (LoD2 bez `--year` = 2017; `year=2016` - blad);
  `test_teryt_length_matches_unit`; `test_area_without_feature_channel_uses_powiats`
  (PRG-atrapa zwraca 2 TERYT: 2 pliki, `UNIT_LIST`, `extra.parent_request`);
  `test_unit_failure_isolated` (404 jednego powiatu -> `failed` z
  `kind="no_coverage"`, drugi zapisany, `ok=False`);
  `test_whole_country_requires_flag_and_reports_size` (`HEAD` ->
  `WHOLE_COUNTRY_SIZE` przed `GET`); `test_local_version_reused`
  (drugie wywolanie: zero `GET` danych, status `local`);
  `test_force_same_bytes_unchanged`, `test_force_new_bytes_new_version`
  (sidecar starej wersji nietkniety); `test_check_collection_never_downloads`
  (`missing`/`unverifiable` dla `none`); `test_upgrade_with_plan_stale`
  (pozycja zmieniona od planu = `stale`, bez pobrania);
  `test_editions_relabeled_across_slots` (identyczny ZIP 2022/2023 ->
  `relabeled`, jeden i-wezel).
- [ ] **Step 2: Implementacja** - kontrakt "Orkiestrator";
  `validate_collection_request` jako jedyne miejsce regul wyboru
  (wolane na poczatku `download_collection` i `check_collection`);
  `related_roots` = slot tej samej jednostki w segmentach pozostalych
  wydan tego produktu i formatu (`content_segment` z innym tokenem
  wydania; tylko istniejace katalogi).
- [ ] **Step 3: Brama i commit** - `feat(download): download_collection
  i check_collection (kolekcje na magazynie wersji, tor collection)`

### Task 6: Produkty PL - archiwum BDOT10k, modele 3D, PRG, EGiB

**Files:**
- Modify: `kartograf/landcover/manager.py` (`year` dla BDOT10k ->
  silnik kolekcji), `kartograf/sources/registry.py` (`vertical_crs`
  3D po pomiarze)
- Test: `tests/test_landcover_manager.py` (istniejacy plik testow
  menedzera; sprawdz nazwe), `tests/test_collections_products.py`

- [ ] **Step 0: Pomiar (live, jednorazowo)** - dla LoD1 2019, 2021,
  2022 pobierz paczke jednego malego powiatu (np. 0401) do
  `<katalog-danych>` i odczytaj `srsName` pierwszego GML z obiektami;
  wpisz `vertical_crs` wariantu (2024 = EPSG:9651, 2017 = EPSG:9650
  zmierzone 2026-10-15). Wynik dopisz do raportu rekonesansu.
- [ ] **Step 1: Testy (RED)** - BDOT10k:
  `test_bdot10k_year_requires_archive_format` (`year` bez `format`
  albo z `GPKG` -> `ValidationError` z lista `GML, SHP`; `layers`/
  `keep_raw` z `year` -> blad); `test_bdot10k_year_teryt_slot_and_sidecar`
  (`landcover/pl_bdot10k_shp_2024/teryt/1261.zip`, etykieta `2024`,
  `request.year == 2024`, `request.format == "SHP"`);
  `test_bdot10k_year_area_powiats` (obszar -> powiaty PRG,
  `extra.parent_request`); `test_bdot10k_without_year_unchanged`
  (dotychczasowe testy GPKG/SHP bez zmian asercji). 3D:
  `test_buildings_vertical_crs_in_sidecar` (LoD1 2024 = EPSG:9651, LoD2
  = EPSG:9650) i `test_buildings_variants_declare_vertical_crs` (kazdy
  wariant ma zmierzony uklad pionowy). PRG: `test_prg_level_required_for_area`,
  `test_prg_level_to_layer` (`gmina` -> warstwa `A03_Granice_gmin`
  w GPKG, pola TERYT `JPT_KOD_JE` zachowane), `test_prg_teryt_powiat_rejected`.
  EGiB: `test_egib_export_unpacked_gpkg` (`.gpkg` z trzema warstwami
  fixtury), `test_egib_bbox_two_layers_without_data_field`.
- [ ] **Step 2: Implementacja** - `_SOURCE_OPTIONS["bdot10k"]` +=
  `year`; w `_check_options` reguly D11 (bez sieci; gdy manifest jest
  scalony, `LandCoverManager.validate_request` obejmuje je przez
  `_check_options` - jedno miejsce); `LandCoverManager.download/check`
  dla BDOT10k z `year` buduje jednostki jak dzis (TERYT albo powiaty
  PRG) i dla kazdej wola funkcje pliku z `download/collections.py`
  (wewnetrzna, np. `fetch_unit_file(...)`), wynik jako
  `LandCoverResult(unit, file)`, pozycje planu na torze `landcover`
  (bez zmiany toru). Pozostale produkty - wylacznie wpisy rejestru
  (Task 1) i testy; zero kodu per produkt w orkiestratorze poza
  parametrami.
- [ ] **Step 3: Brama i commit** - `feat(landcover): archiwum BDOT10k
  (--year, GML/SHP) oraz modele 3D, PRG i EGiB na silnikach kolekcji`

### Task 7: CLI - grupy `boundaries`, `cadastre`, `models3d`, `landcover --year`, `_task` i projekt

**Files:**
- Create: `kartograf/cli/groups/boundaries.py`, `kartograf/cli/groups/cadastre.py`,
  `kartograf/cli/groups/models3d.py`, `kartograf/cli/collection_cmd.py`
- Modify: `kartograf/cli/groups/landcover.py` (opis `--year`, `--format`
  z `GML`), `kartograf/cli/landcover_cmd.py` (przekazanie `year` dla
  BDOT10k), testy: `tests/test_cli_translation.py`, `tests/test_parity.py`,
  `tests/test_cli.py` (albo plik testow grup)
- Warunkowo (manifest scalony - istnieje `kartograf/project/commands.py`):
  `kartograf/project/commands.py`, `tests/test_project_commands.py`

- [ ] **Step 1: Testy (RED)** - `test_new_groups_registered`
  (`kartograf boundaries|cadastre|models3d --help` = kod 0, komendy
  `download`, `list-sources`); `test_group_flags_only_own`
  (`cadastre download --level gmina` -> blad argparse, kod 2;
  `boundaries download --lod 1` -> kod 2); `test_list_sources_from_registry`
  (WYBOR `--product admin --country pl`, KLUCZ = `dataset` sidecara);
  `test_collection_translation` (flagi -> dokladnie argumenty
  `download_collection`/`check_collection`, `--bbox-crs` w `BBox.crs`);
  parytet w `tests/test_parity.py` na wspolnym magazynie
  (`run_both` + `assert_same_store`): PRG bbox, EGiB `--teryt`, LoD1
  `--teryt`, BDOT10k `--year`, bledy walidacji (ten sam typ i tekst),
  `--check-updates --plan` + `--upgrade --plan`. `_handler` i `_task`
  korzystaja z jednej funkcji tlumaczenia (bez osobnego testu
  okablowania; zgodnosc komend z tabela projektu sprawdza test
  manifestu, ADR-040).
- [ ] **Step 2: Implementacja** - moduly grup wg ADR-039 (`add_group`,
  `add_area_flags`, `add_update_flags`, `add_quiet`,
  `add_list_sources`); flagi tylko swoje: `boundaries` (`--product`,
  `--country`, obszar, `--teryt`, `--whole-country`, `--level`),
  `cadastre` (`--product`, `--country`, obszar, `--teryt`),
  `models3d` (`--product`, `--country`, obszar, `--teryt`, `--lod`,
  `--year`); wspolne: `--output/-o`, tryby, `--plan`, `--workers/-w`
  (domyslnie 1), `--quiet`. `--help` wymienia wybory z rejestru
  (`product_choices`-podobna funkcja w bibliotece, bez literalow w CLI).
  `cli/collection_cmd.py`: `collection_task(args) -> dict` (to samo
  tlumaczenie dla `_handler` i `_task`), `cmd_collection_download(args)`
  (cykl planu jak `cmd_download`: `--check-updates` -> plik planu,
  `--upgrade --plan` -> wykonanie; wydruk `UnitFile`/`UnitFailure`
  i `Notice`; kod 0 gdy `ok`, 1 inaczej). Parser `download` kazdej
  grupy: `set_defaults(_handler=cmd_collection_download,
  _task=collection_task)`. `landcover download`: `--year` w opisie
  takze dla BDOT10k (archiwum), `--format` choices `GPKG|SHP|GML`
  (walidacja zgodnosci w bibliotece).
- [ ] **Step 3: Projekt (ADR-040, warunkowo)** - jesli
  `kartograf/project/commands.py` istnieje: dodaj `TaskCommand` dla
  `boundaries download`, `cadastre download`, `models3d download`
  (`validate` = `validate_collection_request`, `download` =
  `download_collection`, `check` = `check_collection`, `files` -
  adapter `CollectionReport` -> `TaskFiles(complete=report.ok, files
  =(("output", unit, file) ...), errors=...)`; `options` = klucze
  `_task`), rozszerz `options` `landcover download` (BDOT10k `year`
  dla archiwum - jesli zbior opcji jest jawny) i dodaj test jednego
  zadania projektu dla rodziny `CollectionReport` (spec manifestu,
  kryterium 11). Jesli manifest NIE jest scalony: `_task` i tak
  ustaw (Step 2), a w `docs/PROGRESS.md` (sekcja integracji) dopisz
  liste pozycji do dodania przez galaz manifestu ("kto scala sie
  pozniej, dopisuje pozycje" - spec manifestu sekcja 5).
- [ ] **Step 4: Smoke offline** - `.venv/bin/python -m kartograf.cli.commands
  boundaries download --help`, `cadastre download --help`, `models3d
  download --help`, `landcover download --help` z korzenia worktree;
  porownaj wybory z `list-sources`.
- [ ] **Step 5: Brama i commit** - `feat(cli): grupy boundaries,
  cadastre, models3d i landcover --year dla archiwum BDOT10k`

### Task 8: Dokumentacja, live E2E i brama koncowa

**Files:**
- Modify: `docs/ARCHITECTURE.md` (sekcja 2: nowe moduly i krawedzie
  `download -> transport/transform` dla kolekcji, `transform -> pyogrio`;
  3.3: regula 9 = D8; nowa sekcja 4.x "Kolekcje: unit_package
  i feature_bbox" z algorytmem D3, osiami D4, GPKG D5, D7; sekcja 5:
  nowe zrodlo przez parametry kanalu), `docs/USAGE.md` (przyklady CLI
  i API dla kazdego wiersza matrycy, semantyka rocznika archiwum - stan
  z poczatku roku, zmiany TERYT, LoD2 niepelne, EGiB: usluga zbiorcza,
  `brak_uprawnien`, eksport dobowy z `transakcje`; znane problemy:
  wolne strony WFS), `docs/SCOPE.md` (zakres 0.8.0, 4.2 zaleznosci
  `pyogrio`, tabela zrodel), `docs/PRD.md` (nowe produkty),
  `docs/DEVELOPMENT_STANDARDS.md` 17 (nowe zrodlo = deskryptor
  z parametrami kanalu), `README.md` (lista produktow i grup),
  `docs/CHANGELOG.md` `[0.8.0] - Unreleased` (Added: grupy, archiwum
  BDOT10k, API kolekcji; Changed: nowa zaleznosc `pyogrio`, `landcover
  --format GML` z `--year`; "Co zrobic": `pip install -U kartograf`
  instaluje `pyogrio`), `docs/PROGRESS.md` (koniec sesji),
  spec katalogu sekcja 5 - errata osi 5514 (odsylacz do ADR-042 D4),
  `docs/research/2026-10-15-plan-c-live/raport.md` (NOWY, wyniki E2E).

- [ ] **Step 1: Dokumentacja** wg listy wyzej (teksty po polsku, ASCII
  w nowych dokumentach jak w specu katalogu).
- [ ] **Step 2: Live E2E** (swiadomie, dane do `<katalog-danych>`,
  rzeczywistej sciezki nie zapisuj):
  ```text
  kartograf landcover download --source bdot10k --teryt 1261 --year 2024 --format SHP -o <katalog-danych>
  kartograf landcover download --source bdot10k --teryt 1261 --year 2022 --format SHP -o <katalog-danych>
  kartograf landcover download --source bdot10k --teryt 1261 --year 2023 --format SHP -o <katalog-danych>
  kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 -o <katalog-danych>
  kartograf models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500 -o <katalog-danych>
  kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 -o <katalog-danych>
  kartograf boundaries download --product admin --teryt 12 -o <katalog-danych>
  kartograf cadastre download --product map --teryt 1261 -o <katalog-danych>
  kartograf cadastre download --product map --country pl --bbox 565000,243000,567000,245000 -o <katalog-danych>
  ```
  Oczekiwane (z rekonesansu): SHP 2024 = 47 404 309 B; 2023 =
  `relabeled` wzgledem 2022 (ten sam i-wezel; sha `6c64b1d33782...`
  jesli GUGiK nie zmienil archiwum); LoD1 2024 = 28 790 760 B (sha
  `dff392bbb6e8...`); gminy bbox = 39 obiektow w warstwie
  `A03_Granice_gmin` (`ogrinfo -so`), EGiB bbox = 3306 dzialek (liczba
  moze sie zmienic - porownaj z `RESULTTYPE=hits` z dnia); PRG woj
  = 22 070 839 B. Powtorz kazde polecenie: status `local`, zero
  transferu danych; `--check-updates` = `unverifiable`; `--force` na
  BDOT10k 2024 = `unchanged`. Sprawdz sidecary (`request`,
  `extra.source`, `extra.parent_request`, `extra.version`) i dowiazania
  (`stat -c %h`). PRG `--whole-country` (377 MB) uruchom osobno, swiadomie.
  Wyniki do `docs/research/2026-10-15-plan-c-live/raport.md` (bez sciezki).
- [ ] **Step 3: Brama koncowa** - `python -m pytest tests/ -m "not
  live" -q`, `python -m ruff check .`, `python -m ruff format --check .`,
  `python -m mypy kartograf/ tests/`; smoke rzeczywistego CLI i API
  (nie tylko testy).
- [ ] **Step 4: Commit** - `docs: plan C - silniki kolekcji, archiwum
  BDOT10k, modele 3D, PRG i EGiB (ADR-042, USAGE, ARCHITECTURE)`

## Kryteria akceptacji

1. Kazdy wiersz matrycy dziala z CLI i z API z tymi samymi plikami,
   sidecarami, statusami i `Notice` (test parytetu); `--help` i
   `list-sources` pokazuja wybory z rejestru, bez wartosci domyslnych
   zmieniajacych dane.
2. Zadna niepelna odpowiedz WFS (brak strony, mniej obiektow niz
   `hits`, HTML/wyjatek OGC) ani uszkodzony/obciety ZIP nie staje sie
   wersja; bledy jednostek sa izolowane.
3. Identyczne roczniki archiwum BDOT10k zajmuja miejsce raz
   (`relabeled`, jeden i-wezel); kazda wersja ma niezmienny sidecar.
4. Nowy produkt planu D/E = deskryptor z parametrami kanalu: plan D
   dodaje dane CZ bez nowej implementacji `unit_package`/`feature_bbox`.
5. Brama zielona, dokumentacja (ADR-042, ARCHITECTURE, USAGE, SCOPE,
   CHANGELOG) zgodna z kodem, raport live bez rzeczywistej sciezki.
