# Etap 0 — refaktor przygotowawczy pod zrodla wielokrajowe: plan implementacji

**Status: WYKONANY** — zmergowany do develop 2026-08-11. Errata (2026-08-18): nota KNOWN_PATHS "preferowac reprojekcje serwerowa CUZK" odwrocona przez ADR-024; `vertical_crs_code("EVRF2007")` zmienione z 9651 na 5621 w etapie 1 (ADR-023d).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md` (zaakceptowany 2026-08-10)

**Goal:** Refaktor zachowujacy zachowanie: deskryptory zrodel (`sources/`), sidecar `.meta.json` (jedyna zmiana obserwowalna), twarda polityka transformacji (`transform/`), wspolne narzedzia transportowe (`transport/`), rejestr systemow godel, unifikacja ABC providerow, przenosiny `providers/pl/` **bez shimow**, podzial CLI na moduly z fasada.

**Architecture:** Nowe moduly sa czystymi danymi/narzedziami bez konsumentow produkcyjnych (poza sidecarem, wpietym w managery/CLI). Istniejaca logika providerow NIE jest przepinana. Granice: `sources/` opisuje, `transport/` nie zna krajow, `transform/` nie zna HTTP, sidecary pisza managery/CLI (nie providery).

**Tech Stack:** Python 3.12, pytest, pyproj 3.7 (`TransformerGroup`), rasterio 1.5 (`merge`), requests; ruff + mypy.

## Global Constraints

- **Galaz:** cala praca na NOWEJ galezi `feature/etap0-zrodla-wielokrajowe` utworzonej z `develop` (Zadanie 0). Commity: Conventional Commits.
- **Inwariant testowy:** wszystkie dotychczasowe 1060 testow przechodzi **bez zmiany asercji**. Dozwolone wylacznie: (a) mechaniczna aktualizacja patch-targetow i importow po przenosinach modulow (dokladne listy w Zadaniach 9 i 13), (b) addytywne asercje sidecara. Zakazane: zmiany asercji zachowania, usuwanie testow, oslabianie mockow.
- **Wersja pakietu zostaje `0.6.1`** — testy ja asertuja (`tests/test_integration.py:56`, `tests/test_cli.py:259`); podbicie do 0.7.0 nastapi przy wydaniu na main, poza tym planem. CHANGELOG: wpisy pod `## [Unreleased]`.
- Jakosc po kazdym zadaniu: `.venv/bin/python -m pytest tests/ -q` zielone; na koncu takze `ruff check`, `ruff format --check`, mypy (patrz Zadanie 0 — baseline), pokrycie >= 80%.
- Przenosiny kodu **1:1** — tresc funkcji bez zmian poza importami; sidecar/`descriptor_key` dokladane w OSOBNYCH zadaniach (nie w commitach przenosin).
- Zero IO przy imporcie `kartograf.sources.*` (deskryptory to stale w kodzie).
- Blad zapisu sidecara NIGDY nie przerywa pobrania (log warning).
- Komunikaty bledow istniejacych sciezek **co do bajta** bez zmian (np. ValidationError konfliktu ukladow: `f"Godło '{cleaned}' ma format PL-2000, ale podano uklad='{uklad}'"`).
- Uzywaj `.venv/bin/python` (oraz `.venv/bin/pip`). `python -m kartograf` nie dziala (brak `__main__.py`) — CLI to `.venv/bin/kartograf`.

### Decyzje planu doprecyzowujace spec (uzasadnione pomiarami z rekonesansu)

1. **Filtr dokladnosci w `transform/crs.py`:** spec mowi "odrzuc accuracy <= 0 (nieznana)", ale zmierzono w pyproj 3.7.2: operacje DOKLADNE (czysta matematyka) raportuja `accuracy == 0.0` (np. jedyna operacja 25833→2180, ktora wg specu i testu (f) MUSI przejsc), a nieznana dokladnosc to `-1`. Implementujemy: **odrzuc `accuracy < 0` (nieznana), akceptuj `0.0` (dokladna)** — inaczej test (f) ze specu jest niespelnialny. Odnotowac w ADR.
2. **Patch-targety CLI:** testy patchuja `kartograf.cli.commands.DownloadManager` itd. Po podziale CLI kod zyje w submodulach, wiec patche na fasadzie przestana dzialac. Rozszerzamy liste dozwolonych zmian mechanicznych z sekcji 9 specu o aktualizacje patch-targetow CLI (ta sama kategoria: "aktualizacja stalych patch-targetow po przeniesieniu modulow"); dokladna lista w Zadaniu 13. Asercje bez zmian.
3. **mypy nie jest zainstalowany** w `.venv` i nie ma konfiguracji `[tool.mypy]` — baseline nieznany. Zadanie 0 instaluje mypy i zapisuje baseline; kryterium: **nowe moduly czyste, zero NOWYCH bledow wzgledem baseline** (pelne "mypy czyste" na starym kodzie to osobna praca poza zakresem etapu 0).
4. **Reguly 5m⇒EVRF2007 nie usuwamy z `DownloadManager.__init__`** — manager wymusza ja takze przy przekazanym wlasnym providerze (asertowane w test_download_manager), wiec zostaje verbatim; fabryka `create_nmt_provider` dostaje te sama regule dla sciezki konstrukcji domyslnego providera (CLI + manager). Podwojnego warninga nie ma (manager przekazuje juz skorygowana wartosc).
5. **`LandCoverManager` dalej wola `provider.download_by_teryt`** (nie nowy alias) — testy asertuja `mock_provider.download_by_teryt.assert_called_once()`; API managera bez zmian (zgodnie ze spec sekcja 4 "nie wchodzi").

### Mapa plikow (co powstaje / co sie zmienia)

```
NOWE:  kartograf/sources/{__init__,descriptor,registry,sidecar}.py
       kartograf/transport/{__init__,http,mosaic}.py
       kartograf/transform/{__init__,crs}.py
       kartograf/core/parser_registry.py
       kartograf/providers/pl/__init__.py           (+ fabryka create_nmt_provider)
       kartograf/cli/{_parser,parse_cmd,download_cmd,landcover_cmd,soilgrids_cmd,cache_cmd}.py
       tests/test_{sources_registry,sidecar,transform_crs,transport_http,transport_mosaic,parser_registry}.py
PRZENIESIONE (git mv, 1:1): providers/{gugik,gugik_nmpt,gugik_orto,gugik_laz,bdot10k}.py -> providers/pl/
USUNIETE bez shimow: providers/landcover_base.py (LandCoverProvider -> providers/base.py)
ZMIENIONE: providers/base.py, providers/__init__.py, kartograf/__init__.py, exceptions (nie — bledy transform
       zyja w transform/crs.py), download/{manager,storage}.py, landcover/manager.py, core/sheet_parser.py,
       cli/commands.py (fasada), corine.py, soilgrids.py, docs/*
```

---

### Zadanie 0: Galaz robocza i baseline srodowiska

**Files:** brak zmian w repo (tylko git + venv).

- [ ] **Krok 0.1: Utworz galaz z develop**

```bash
cd /home/claude-agent/workspace/Kartograf
git checkout develop && git pull origin develop
git checkout -b feature/etap0-zrodla-wielokrajowe
```

- [ ] **Krok 0.2: Doinstaluj narzedzia dev (mypy brak w venv; ruff 0.15.0 juz jest)**

```bash
.venv/bin/pip install "mypy>=1.13" "pytest-cov>=5.0"
```

- [ ] **Krok 0.3: Baseline testow i lintera**

```bash
.venv/bin/python -m pytest tests/ -q          # oczekiwane: 1060 passed
.venv/bin/python -m ruff check kartograf/ tests/       # oczekiwane: czysto
.venv/bin/python -m ruff format --check kartograf/ tests/
```

- [ ] **Krok 0.4: Baseline mypy — zapisz do pliku, policz bledy**

```bash
.venv/bin/python -m mypy kartograf/ > /tmp/mypy-baseline.txt; tail -1 /tmp/mypy-baseline.txt
```

Zanotuj liczbe bledow baseline (uzyjesz jej w Zadaniu 15: zero NOWYCH bledow; nowe moduly czyste).

---

### Zadanie 1: `sources/descriptor.py` — deskryptory jako zamrozone dane

**Files:**
- Create: `kartograf/sources/__init__.py`, `kartograf/sources/descriptor.py`
- Test: `tests/test_sources_registry.py` (sekcja deskryptorow; rejestr dojdzie w Zadaniu 2)

**Interfaces (Produces):** `TransportKind` (StrEnum), `LicenseInfo`, `AccessChannel`, `TileScheme`, `SourceDescriptor`, `CountryProfile` — dokladnie jak nizej; konsumowane przez `registry.py` (Zadanie 2) i `sidecar.py` (Zadanie 3).

- [ ] **Krok 1.1: Napisz failing test**

```python
# tests/test_sources_registry.py
"""Testy deskryptorow i rejestru zrodel (kartograf.sources)."""

import dataclasses

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    LicenseInfo,
    SourceDescriptor,
    TileScheme,
    TransportKind,
)


class TestDescriptorDataclasses:
    def _channel(self) -> AccessChannel:
        return AccessChannel(
            transport=TransportKind.WCS,
            horizontal_crs="EPSG:2180",
            vertical_crs_options=("EPSG:9650", "EPSG:9651"),
            capabilities=frozenset({"bbox_raster"}),
        )

    def test_transport_kind_values(self):
        assert TransportKind.WCS == "wcs"
        assert TransportKind.WMS_SHEET_INDEX == "wms_sheet_index"
        assert TransportKind.WFS == "wfs"
        assert TransportKind.DIRECT_FILES == "direct_files"
        assert TransportKind.CLMS_API == "clms_api"
        assert TransportKind.ARCGIS_IMAGE == "arcgis_image"
        assert TransportKind.ARCGIS_QUERY == "arcgis_query"
        assert TransportKind.OGC_API_FEATURES == "ogc_api_features"

    def test_access_channel_defaults(self):
        ch = self._channel()
        assert ch.vertical_source == "native"
        assert ch.server_reprojection is False
        assert ch.notes == ""

    def test_descriptor_frozen(self):
        desc = SourceDescriptor(
            key="pl.gugik.nmt_1m",
            country="PL",
            product="nmt",
            name="NMT 1m",
            provider_name="GUGiK",
            channels=(self._channel(),),
            tile_scheme=None,
            storage_subdir="nmt_1m",
            default_extension=".asc",
            license=LicenseInfo(id="PL-PGiK-40a", attribution="GUGiK"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            desc.key = "x"  # type: ignore[misc]
        assert desc.resolution is None
        assert desc.auth == "none"

    def test_tile_scheme_and_country_profile(self):
        ts = TileScheme(
            kind="computable", crs="EPSG:2180", width_m=2000.0, height_m=2000.0,
            description="test",
        )
        assert ts.kind == "computable"
        cp = CountryProfile(
            code="PL", name="Polska",
            extent_wgs84=BBox(14.07, 49.00, 24.20, 54.90, "EPSG:4326"),
            dataset_keys=("pl.gugik.nmt_1m",),
        )
        assert cp.extent_wgs84.crs == "EPSG:4326"
```

- [ ] **Krok 1.2: Uruchom test — ma pasc**

```bash
.venv/bin/python -m pytest tests/test_sources_registry.py -q
```

Oczekiwane: FAIL/ERROR `ModuleNotFoundError: No module named 'kartograf.sources'`.

- [ ] **Krok 1.3: Implementacja**

```python
# kartograf/sources/__init__.py
"""Zrodla danych opisane deklaratywnie (deskryptory + rejestr + sidecar)."""
```

```python
# kartograf/sources/descriptor.py
"""
Deskryptory zrodel danych — czyste dane, zero IO, zero zachowan.

Deskryptor opisuje JEDEN zbior danych (np. NMT 1m z GUGiK): kanaly dostepu,
uklady, licencje, schemat kafli. Zrodlem prawdy dla logiki wykonawczej
pozostaja providery (etap 0); egzekwowanie capabilities zaczyna sie w etapie 1.
"""

from dataclasses import dataclass
from enum import StrEnum

from kartograf.core.sheet_parser import BBox


class TransportKind(StrEnum):
    """Rodzaj transportu danych (mechanizm pobierania)."""

    WCS = "wcs"                              # PL nmt_1m bbox, SoilGrids; pozniej DE/SK
    WMS_SHEET_INDEX = "wms_sheet_index"      # PL: skorowidz WMS -> URL pliku
    WFS = "wfs"                              # PL LAZ
    DIRECT_FILES = "direct_files"            # PL BDOT10k; pozniej CZ openzu
    CLMS_API = "clms_api"                    # CORINE
    ARCGIS_IMAGE = "arcgis_image"            # etap 1 (CZ exportImage)
    ARCGIS_QUERY = "arcgis_query"            # etap 3 (ZABAGED), SK
    OGC_API_FEATURES = "ogc_api_features"    # DE basemap.de


@dataclass(frozen=True)
class LicenseInfo:
    """Licencja i gotowy tekst atrybucji dla zrodla."""

    id: str            # np. "CC-BY-4.0", "PL-PGiK-40a", "dl-de/by-2-0"
    attribution: str   # gotowy tekst atrybucji
    url: str = ""


@dataclass(frozen=True)
class AccessChannel:
    """Jeden kanal dostepu do zrodla (transport + uklady + zdolnosci)."""

    transport: TransportKind
    horizontal_crs: str                      # "EPSG:2180", "EPSG:5514", ...
    vertical_crs_options: tuple[str, ...] = ()   # () gdy nie dotyczy (orto, landcover)
    vertical_source: str = "native"          # "native" | "ellipsoidal" | "server"
    server_reprojection: bool = False
    capabilities: frozenset[str] = frozenset()
    # {"bbox_raster","bbox_vector","sheet_files","area_files","admin_unit_files"}
    notes: str = ""
    # endpointow celowo brak w etapie 0 — zrodlem prawdy pozostaja providery;
    # pole endpoint dojdzie w etapie 1, gdy pierwszy silnik zacznie je konsumowac


@dataclass(frozen=True)
class TileScheme:
    """Schemat kafli zrodla (obliczalny lub wymagajacy indeksu)."""

    kind: str                 # "computable" | "index"
    crs: str
    width_m: float | None
    height_m: float | None
    description: str          # np. "SM5: nazwa miasta + cyfry, wymaga indeksu"


@dataclass(frozen=True)
class SourceDescriptor:
    """Pelny opis jednego zbioru danych."""

    key: str                  # "pl.gugik.nmt_1m"
    country: str              # "PL" | "EU" | "GLOBAL" (pozniej "CZ","DE","SK")
    product: str              # "nmt" | "nmpt" | "orto" | "laz" | "landcover" | "soil"
    name: str                 # czytelna nazwa zbioru
    provider_name: str        # "GUGiK", "CUZK", ...
    channels: tuple[AccessChannel, ...]
    tile_scheme: TileScheme | None
    storage_subdir: str | None    # None dla zrodel LandCoverManagera
    default_extension: str
    license: LicenseInfo
    resolution: str | None = None
    auth: str = "none"            # "none" | "clms_oauth"


@dataclass(frozen=True)
class CountryProfile:
    """Profil kraju: przyblizony zasieg (dla --country auto w etapie 1) + zbiory."""

    code: str                 # "PL"
    name: str
    extent_wgs84: BBox
    dataset_keys: tuple[str, ...]
```

- [ ] **Krok 1.4: Testy przechodza**

```bash
.venv/bin/python -m pytest tests/test_sources_registry.py -q
```

- [ ] **Krok 1.5: Commit**

```bash
git add kartograf/sources/ tests/test_sources_registry.py
git commit -m "feat(sources): deskryptory zrodel jako zamrozone dane (etap 0)"
```

---

### Zadanie 2: `sources/registry.py` — rejestr zrodel i krajow + test spojnosci

**Files:**
- Create: `kartograf/sources/registry.py`
- Test: `tests/test_sources_registry.py` (rozszerzenie)

**Interfaces:**
- Consumes: dataclassy z Zadania 1.
- Produces: `get_source(key) -> SourceDescriptor` (KeyError z lista kluczy), `sources_for(country=None, product=None) -> list[SourceDescriptor]`, `get_country(code) -> CountryProfile` (KeyError z lista), `vertical_crs_code(name) -> str` ("KRON86"->"EPSG:9650", "EVRF2007"->"EPSG:9651"; kody EPSG przechodza bez zmian; nieznana nazwa -> KeyError). Konsumenci: sidecar (Zadanie 3, 12), testy spojnosci.

- [ ] **Krok 2.1: Failing testy — dopisz do `tests/test_sources_registry.py`**

```python
from kartograf.sources.registry import (
    get_country,
    get_source,
    sources_for,
    vertical_crs_code,
)

EXPECTED_KEYS = {
    "pl.gugik.nmt_1m", "pl.gugik.nmt_5m", "pl.gugik.nmpt", "pl.gugik.orto",
    "pl.gugik.laz", "pl.gugik.bdot10k", "eu.clms.corine", "global.isric.soilgrids",
}


class TestRegistry:
    def test_all_keys_present(self):
        assert {d.key for d in sources_for()} == EXPECTED_KEYS

    def test_get_source_unknown_key_lists_available(self):
        with pytest.raises(KeyError) as exc:
            get_source("cz.cuzk.dmr5g")
        assert "pl.gugik.nmt_1m" in str(exc.value)

    def test_sources_for_filters(self):
        pl = sources_for(country="PL")
        assert len(pl) == 6
        nmt = sources_for(country="PL", product="nmt")
        assert {d.key for d in nmt} == {"pl.gugik.nmt_1m", "pl.gugik.nmt_5m"}

    def test_country_pl(self):
        pl = get_country("PL")
        assert pl.code == "PL"
        assert pl.extent_wgs84.crs == "EPSG:4326"
        assert set(pl.dataset_keys) == {k for k in EXPECTED_KEYS if k.startswith("pl.")}
        with pytest.raises(KeyError):
            get_country("CZ")

    def test_vertical_crs_code(self):
        assert vertical_crs_code("KRON86") == "EPSG:9650"
        assert vertical_crs_code("EVRF2007") == "EPSG:9651"
        assert vertical_crs_code("EPSG:9651") == "EPSG:9651"
        with pytest.raises(KeyError):
            vertical_crs_code("Kronsztad")

    def test_nmt_1m_entry_values(self):
        d = get_source("pl.gugik.nmt_1m")
        assert d.storage_subdir == "nmt_1m"
        assert d.default_extension == ".asc"
        assert d.resolution == "1m"
        transports = {ch.transport for ch in d.channels}
        assert transports == {TransportKind.WMS_SHEET_INDEX, TransportKind.WCS}

    def test_no_vertical_for_orto_and_landcover(self):
        for key in ("pl.gugik.orto", "pl.gugik.bdot10k", "eu.clms.corine",
                    "global.isric.soilgrids"):
            for ch in get_source(key).channels:
                assert ch.vertical_crs_options == ()
```

- [ ] **Krok 2.2: Uruchom — FAIL (`ImportError`)**

```bash
.venv/bin/python -m pytest tests/test_sources_registry.py -q
```

- [ ] **Krok 2.3: Implementacja `kartograf/sources/registry.py`**

```python
"""
Rejestr zrodel danych i krajow.

Etap 0: deskryptory sa zrodlem prawdy dla storage_subdir, default_extension,
licencji, opcji pionowych i capabilities (konsumpcja: sidecar + testy
spojnosci). Egzekwowanie capabilities w managerach zaczyna sie w etapie 1.
"""

from kartograf.core.sheet_parser import BBox
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    LicenseInfo,
    SourceDescriptor,
    TransportKind,
)

# Mapowanie nazw ukladow pionowych uzywanych w CLI na kody EPSG.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",     # PL-KRON86-NH
    "EVRF2007": "EPSG:9651",   # PL-EVRF2007-NH (realizacja PL)
}

_GUGIK_LICENSE = LicenseInfo(
    id="PL-PGiK-40a",
    attribution=(
        "Dane: Glowny Urzad Geodezji i Kartografii (www.geoportal.gov.pl), "
        "art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne"
    ),
    url="https://www.geoportal.gov.pl",
)

_CLMS_LICENSE = LicenseInfo(
    id="COPERNICUS-CLMS",
    attribution=(
        "(c) European Union, Copernicus Land Monitoring Service, "
        "European Environment Agency (EEA)"
    ),
    url="https://land.copernicus.eu/en/products/corine-land-cover",
)

_SOILGRIDS_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="SoilGrids — ISRIC World Soil Information, CC BY 4.0",
    url="https://www.isric.org/explore/soilgrids",
)

_PL_VERTICAL_BOTH = ("EPSG:9650", "EPSG:9651")

_SOURCES: dict[str, SourceDescriptor] = {
    d.key: d
    for d in (
        SourceDescriptor(
            key="pl.gugik.nmt_1m",
            country="PL",
            product="nmt",
            name="Numeryczny Model Terenu 1 m (GRID1)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"sheet_files"}),
                ),
                AccessChannel(
                    transport=TransportKind.WCS,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"bbox_raster"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmt_1m",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="1m",
        ),
        SourceDescriptor(
            key="pl.gugik.nmt_5m",
            country="PL",
            product="nmt",
            name="Numeryczny Model Terenu 5 m",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=("EPSG:9651",),
                    capabilities=frozenset({"sheet_files"}),
                    notes="WCS niedostepne dla 5m — tylko arkusze OpenData",
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmt_5m",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="5m",
        ),
        SourceDescriptor(
            key="pl.gugik.nmpt",
            country="PL",
            product="nmpt",
            name="Numeryczny Model Pokrycia Terenu 1 m (DSM)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"sheet_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmpt",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="1m",
        ),
        SourceDescriptor(
            key="pl.gugik.orto",
            country="PL",
            product="orto",
            name="Ortofotomapa Standard Resolution (25 cm)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"sheet_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="orto",
            default_extension=".tif",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.laz",
            country="PL",
            product="laz",
            name="Chmury punktow LIDAR (dane pomiarowe ALS)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WFS,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"area_files"}),
                    notes="WMS skorowidzy LAZ zwraca 401 — WFS jedyna droga",
                ),
            ),
            tile_scheme=None,
            storage_subdir="laz",
            default_extension=".laz",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.bdot10k",
            country="PL",
            product="landcover",
            name="BDOT10k — baza danych obiektow topograficznych",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"admin_unit_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".gpkg",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="eu.clms.corine",
            country="EU",
            product="landcover",
            name="CORINE Land Cover",
            provider_name="Copernicus CLMS",
            channels=(
                AccessChannel(
                    transport=TransportKind.CLMS_API,
                    horizontal_crs="EPSG:3035",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="bez credentials CLMS fallback: podglad PNG z WMS",
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".tif",
            license=_CLMS_LICENSE,
            auth="clms_oauth",
        ),
        SourceDescriptor(
            key="global.isric.soilgrids",
            country="GLOBAL",
            product="soil",
            name="SoilGrids — globalne dane glebowe",
            provider_name="ISRIC",
            channels=(
                AccessChannel(
                    transport=TransportKind.WCS,
                    horizontal_crs="EPSG:4326",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="tylko WGS84 bbox; transformacja z EPSG:2180 automatyczna",
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".tif",
            license=_SOILGRIDS_LICENSE,
        ),
    )
}

_COUNTRIES: dict[str, CountryProfile] = {
    "PL": CountryProfile(
        code="PL",
        name="Polska",
        extent_wgs84=BBox(14.07, 49.00, 24.20, 54.90, "EPSG:4326"),
        dataset_keys=tuple(sorted(k for k in _SOURCES if k.startswith("pl."))),
    ),
}


def get_source(key: str) -> SourceDescriptor:
    """Zwroc deskryptor zrodla; KeyError z lista dostepnych kluczy."""
    try:
        return _SOURCES[key]
    except KeyError:
        raise KeyError(
            f"Nieznane zrodlo: '{key}'. Dostepne: {sorted(_SOURCES)}"
        ) from None


def sources_for(
    country: str | None = None, product: str | None = None
) -> list[SourceDescriptor]:
    """Zwroc deskryptory pasujace do kraju i/lub produktu."""
    return [
        d
        for d in _SOURCES.values()
        if (country is None or d.country == country)
        and (product is None or d.product == product)
    ]


def get_country(code: str) -> CountryProfile:
    """Zwroc profil kraju; KeyError z lista dostepnych kodow."""
    try:
        return _COUNTRIES[code]
    except KeyError:
        raise KeyError(
            f"Nieznany kraj: '{code}'. Dostepne: {sorted(_COUNTRIES)}"
        ) from None


def vertical_crs_code(name: str) -> str:
    """Mapuj nazwe CLI ukladu pionowego na kod EPSG (kody przechodza bez zmian)."""
    if name in _VERTICAL_CRS_CODES:
        return _VERTICAL_CRS_CODES[name]
    if name in _VERTICAL_CRS_CODES.values():
        return name
    raise KeyError(
        f"Nieznany uklad pionowy: '{name}'. "
        f"Dostepne: {sorted(_VERTICAL_CRS_CODES)}"
    )
```

- [ ] **Krok 2.4: Testy przechodza**

```bash
.venv/bin/python -m pytest tests/test_sources_registry.py -q
```

- [ ] **Krok 2.5: Test spojnosci deskryptor↔provider — dopisz do `tests/test_sources_registry.py`**

Importy WYLACZNIE z publicznego API `kartograf` (stabilne przez przenosiny w Zadaniu 9).

```python
class TestDescriptorProviderConsistency:
    """Spec 6.12: deskryptor musi zgadzac sie ze stanem faktycznym providera."""

    def test_nmt_1m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_1m")
        provider = GugikProvider(resolution="1m")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="1m")
        assert d.storage_subdir == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("1m")
        codes = {vertical_crs_code(n) for n in supported}
        for ch in d.channels:
            assert set(ch.vertical_crs_options) == codes

    def test_nmt_5m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_5m")
        provider = GugikProvider(resolution="5m")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="5m")
        assert d.storage_subdir == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("5m")
        assert {vertical_crs_code(n) for n in supported} == set(
            d.channels[0].vertical_crs_options
        )

    def test_nmpt(self, tmp_path):
        from kartograf import FileStorage, GugikNmptProvider

        d = get_source("pl.gugik.nmpt")
        provider = GugikNmptProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="nmpt")._subdir
        codes = {vertical_crs_code(n) for n in provider.SUPPORTED_VERTICAL_CRS}
        assert set(d.channels[0].vertical_crs_options) == codes

    def test_orto(self, tmp_path):
        from kartograf import FileStorage, GugikOrtoProvider

        d = get_source("pl.gugik.orto")
        provider = GugikOrtoProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="orto")._subdir
        assert d.channels[0].vertical_crs_options == ()

    def test_laz(self, tmp_path):
        from kartograf import FileStorage, GugikLazProvider

        d = get_source("pl.gugik.laz")
        provider = GugikLazProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="laz")._subdir
        codes = {vertical_crs_code(n) for n in provider.SUPPORTED_VERTICAL_CRS}
        assert set(d.channels[0].vertical_crs_options) == codes

    def test_landcover_and_soil(self):
        from kartograf import Bdot10kProvider, CorineProvider, SoilGridsProvider

        cases = [
            ("pl.gugik.bdot10k", Bdot10kProvider(), "GPKG"),
            ("eu.clms.corine", CorineProvider(use_proxy=False), "GTiff"),
            ("global.isric.soilgrids", SoilGridsProvider(), "GTiff"),
        ]
        for key, provider, fmt in cases:
            d = get_source(key)
            assert d.storage_subdir is None
            assert d.default_extension == provider.get_file_extension(fmt)
            assert d.provider_name != ""
            assert d.license.attribution != ""
```

- [ ] **Krok 2.6: Testy przechodza; pelny pytest bez regresji**

```bash
.venv/bin/python -m pytest tests/test_sources_registry.py -q && .venv/bin/python -m pytest tests/ -q
```

Uwaga: `CorineProvider(use_proxy=False)` nie robi IO w konstruktorze (rekonesans: `__init__` tylko ustawia pola). Gdyby ktorys konstruktor jednak dotykal sieci — zmockuj sesje, NIE oslabiaj asercji.

- [ ] **Krok 2.7: Commit**

```bash
git add kartograf/sources/registry.py tests/test_sources_registry.py
git commit -m "feat(sources): rejestr zrodel PL/EU/GLOBAL + test spojnosci deskryptor-provider"
```

---

### Zadanie 3: `sources/sidecar.py` — metadane wyniku + zapis `.meta.json`

**Files:**
- Create: `kartograf/sources/sidecar.py`
- Test: `tests/test_sidecar.py`

**Interfaces:**
- Consumes: `SourceDescriptor`, `registry.vertical_crs_code`.
- Produces (dla Zadania 12): `ResultMetadata` (dataclass, kw_only), `build_metadata(descriptor, *, request, vertical_crs=None, data_path=None, transform=None, extra=None) -> ResultMetadata`, `write_sidecar(data_path: Path, meta: ResultMetadata) -> Path` (sciezka: `<pelna nazwa pliku>.meta.json`), `read_asc_nodata(path: Path) -> float | None`.

- [ ] **Krok 3.1: Failing testy — `tests/test_sidecar.py`**

```python
"""Testy sidecara metadanych (kartograf.sources.sidecar)."""

import json
import logging

from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import (
    ResultMetadata,
    build_metadata,
    read_asc_nodata,
    write_sidecar,
)


class TestBuildMetadata:
    def test_godlo_request_nmt(self, tmp_path):
        asc = tmp_path / "N-34-130-D-d-2-4.asc"
        asc.write_text(
            "ncols 10\nnrows 10\nxllcorner 0\nyllcorner 0\n"
            "cellsize 1\nNODATA_value -9999\n"
        )
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"godlo": "N-34-130-D-d-2-4"},
            vertical_crs="EVRF2007",
            data_path=asc,
        )
        assert meta.schema == "kartograf-meta/1"
        assert meta.dataset == "pl.gugik.nmt_1m"
        assert meta.country == "PL"
        assert meta.product == "nmt"
        assert meta.provider == "GUGiK"
        assert meta.horizontal_crs == "EPSG:2180"
        assert meta.vertical_crs == "EPSG:9651"
        assert meta.vertical_source == "native"
        assert meta.resolution == "1m"
        assert meta.nodata == -9999.0
        assert meta.request == {"godlo": "N-34-130-D-d-2-4"}
        assert meta.license["id"] == "PL-PGiK-40a"
        assert meta.transform is None
        assert meta.downloaded_at.endswith("+00:00")
        assert meta.kartograf_version

    def test_bbox_request_selects_bbox_channel(self):
        meta = build_metadata(
            get_source("pl.gugik.nmt_1m"),
            request={"bbox": [530000.0, 382000.0, 533000.0, 386000.0],
                     "bbox_crs": "EPSG:2180"},
            vertical_crs="EVRF2007",
        )
        assert meta.horizontal_crs == "EPSG:2180"
        assert meta.nodata is None
        assert meta.request["bbox_crs"] == "EPSG:2180"

    def test_no_vertical_for_orto(self):
        meta = build_metadata(
            get_source("pl.gugik.orto"), request={"godlo": "N-34-130-D-d-2-4"}
        )
        assert meta.vertical_crs is None
        assert meta.resolution is None

    def test_extra_fields(self):
        meta = build_metadata(
            get_source("pl.gugik.laz"),
            request={"bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:2180"},
            vertical_crs="KRON86",
            extra={"godlo_kafla": "N-33-131-B-a-1-1-4", "rok": 2024},
        )
        assert meta.vertical_crs == "EPSG:9650"
        assert meta.extra["rok"] == 2024


class TestWriteSidecar:
    def _meta(self) -> ResultMetadata:
        return build_metadata(
            get_source("pl.gugik.orto"), request={"godlo": "N-34-130-D-d-2-4"}
        )

    def test_writes_full_filename_meta_json(self, tmp_path):
        data = tmp_path / "N-34-130-D-d-2-4.tif"
        data.write_bytes(b"x")
        out = write_sidecar(data, self._meta())
        assert out == tmp_path / "N-34-130-D-d-2-4.tif.meta.json"
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["schema"] == "kartograf-meta/1"
        assert payload["dataset"] == "pl.gugik.orto"
        assert payload["license"]["id"] == "PL-PGiK-40a"

    def test_write_failure_warns_and_does_not_raise(self, tmp_path, caplog):
        # Spec sekcja 8: wyjatki IO w write_sidecar lapane i logowane jako
        # warning — pobranie (wolajacy) dostaje wynik normalnie.
        data = tmp_path / "missing-dir" / "x.tif"
        with caplog.at_level(logging.WARNING):
            out = write_sidecar(data, self._meta())
        assert not out.exists()
        assert "sidecar" in caplog.text.lower()


class TestReadAscNodata:
    def test_reads_nodata(self, tmp_path):
        p = tmp_path / "a.asc"
        p.write_text("ncols 2\nnrows 2\nNODATA_value -9999\n1 2\n3 4\n")
        assert read_asc_nodata(p) == -9999.0

    def test_missing_header_or_file(self, tmp_path):
        p = tmp_path / "b.asc"
        p.write_text("ncols 2\nnrows 2\n1 2\n3 4\n")
        assert read_asc_nodata(p) is None
        assert read_asc_nodata(tmp_path / "nie-ma.asc") is None
```

- [ ] **Krok 3.2: Uruchom — FAIL (ImportError)**

```bash
.venv/bin/python -m pytest tests/test_sidecar.py -q
```

- [ ] **Krok 3.3: Implementacja `kartograf/sources/sidecar.py`**

```python
"""
Sidecar metadanych wyniku pobrania: `<pelna_nazwa_pliku>.meta.json`.

Kontrakt dla Hydrografa (scalanie danych transgranicznych poza Kartografem):
CRS-y, nodata, zrodlo, licencja. Format wersjonowany polem `schema`;
pola dokladane addytywnie.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from kartograf.sources.descriptor import AccessChannel, SourceDescriptor
from kartograf.sources.registry import vertical_crs_code

logger = logging.getLogger(__name__)

_BBOX_CAPS = {"bbox_raster", "bbox_vector"}


@dataclass(kw_only=True)
class ResultMetadata:
    """Metadane jednego pliku wynikowego."""

    dataset: str            # klucz deskryptora
    country: str
    product: str
    provider: str
    horizontal_crs: str
    vertical_crs: str | None
    vertical_source: str    # "native" | "ellipsoidal" | "server"
    resolution: str | None
    nodata: float | None
    request: dict           # {"godlo": ...} | {"bbox": [...], "bbox_crs": ...} | {"teryt": ...}
    license: dict           # {"id","attribution","url"}
    downloaded_at: str      # ISO 8601 UTC
    kartograf_version: str
    transform: dict | None = None   # etap 0: None
    extra: dict = field(default_factory=dict)
    schema: str = "kartograf-meta/1"


def read_asc_nodata(path: Path) -> float | None:
    """Odczytaj NODATA_value z naglowka Arc/Info ASCII Grid (None gdy brak)."""
    try:
        with open(path, encoding="ascii", errors="replace") as f:
            for _ in range(6):
                parts = f.readline().split()
                if len(parts) == 2 and parts[0].lower() == "nodata_value":
                    return float(parts[1])
    except (OSError, ValueError):
        return None
    return None


def _select_channel(descriptor: SourceDescriptor, request: dict) -> AccessChannel:
    """Dobierz kanal do rodzaju zadania (bbox -> kanal bbox_*, inaczej pierwszy pasujacy)."""
    want_bbox = "bbox" in request
    for ch in descriptor.channels:
        has_bbox = bool(ch.capabilities & _BBOX_CAPS)
        if want_bbox == has_bbox:
            return ch
    return descriptor.channels[0]


def build_metadata(
    descriptor: SourceDescriptor,
    *,
    request: dict,
    vertical_crs: str | None = None,
    data_path: Path | None = None,
    transform: dict | None = None,
    extra: dict | None = None,
) -> ResultMetadata:
    """Zbuduj metadane z deskryptora + kontekstu wywolania."""
    from kartograf import __version__  # lazy: unika cyklu importow

    channel = _select_channel(descriptor, request)

    vertical: str | None = None
    if channel.vertical_crs_options and vertical_crs is not None:
        vertical = vertical_crs_code(vertical_crs)

    nodata: float | None = None
    if data_path is not None and data_path.suffix.lower() == ".asc":
        nodata = read_asc_nodata(data_path)

    return ResultMetadata(
        dataset=descriptor.key,
        country=descriptor.country,
        product=descriptor.product,
        provider=descriptor.provider_name,
        horizontal_crs=channel.horizontal_crs,
        vertical_crs=vertical,
        vertical_source=channel.vertical_source,
        resolution=descriptor.resolution,
        nodata=nodata,
        request=request,
        license={
            "id": descriptor.license.id,
            "attribution": descriptor.license.attribution,
            "url": descriptor.license.url,
        },
        transform=transform,
        extra=extra or {},
        downloaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        kartograf_version=__version__,
    )


def write_sidecar(data_path: Path, meta: ResultMetadata) -> Path:
    """Zapisz `<data_path>.meta.json` obok pliku danych; zwroc sciezke sidecara.

    Wyjatki IO sa lapane i logowane jako warning (spec sekcja 8) — brak
    sidecara nigdy nie przerywa pobrania; przy bledzie zwracana sciezka
    wskazuje plik, ktory NIE powstal.
    """
    sidecar_path = data_path.parent / f"{data_path.name}.meta.json"
    try:
        payload = json.dumps(asdict(meta), ensure_ascii=False, indent=2)
        sidecar_path.write_text(payload + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar_path}: {e}")
    return sidecar_path
```

- [ ] **Krok 3.4: Testy przechodza + ruff**

```bash
.venv/bin/python -m pytest tests/test_sidecar.py tests/test_sources_registry.py -q
.venv/bin/python -m ruff check kartograf/sources/ tests/test_sidecar.py
```

- [ ] **Krok 3.5: Commit**

```bash
git add kartograf/sources/sidecar.py tests/test_sidecar.py
git commit -m "feat(sources): ResultMetadata + write_sidecar (.meta.json) + read_asc_nodata"
```

---

### Zadanie 4: `transform/crs.py` — twarda polityka transformacji

**Files:**
- Create: `kartograf/transform/__init__.py`, `kartograf/transform/crs.py`
- Test: `tests/test_transform_crs.py`

**Interfaces (Produces):** `TransformPolicy`, `PinnedTransform`, `build_pinned_transform(src_crs, dst_crs, policy) -> PinnedTransform`, `TransformError(KartografError)`, `TransformUnavailableError(TransformError)` (atrybuty: `rejected: list[tuple[str, str]]`, `remedy: str | None`), stale `KNOWN_PATHS`, `REMEDIES`. Zadnych zmian w `kartograf/exceptions.py` — bledy zyja tu (nowa galaz pod KartografError). Konsument produkcyjny: etap 1.

Fakty z pomiaru (pyproj 3.7.2): `TransformerGroup(crs_from, crs_to, always_xy=..., allow_ballpark=...)`; transformer ma `.accuracy` (float; **-1 = nieznana, 0.0 = dokladna**) i `.description`; grupa ma `.unavailable_operations`. Patrz "Decyzje planu" pkt 1 — filtr odrzuca `accuracy < 0`, NIE `== 0`.

- [ ] **Krok 4.1: Failing testy — `tests/test_transform_crs.py`**

```python
"""Testy twardej polityki transformacji (kartograf.transform.crs)."""

import math
from unittest.mock import MagicMock, patch

import pytest

from kartograf.exceptions import KartografError
from kartograf.transform.crs import (
    KNOWN_PATHS,
    REMEDIES,
    TransformError,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_GROUP_PATCH = "kartograf.transform.crs.TransformerGroup"


def _mock_transformer(accuracy, description, result=(100.0, 200.0)):
    t = MagicMock()
    t.accuracy = accuracy
    t.description = description
    t.transform.return_value = result
    return t


def _mock_group(transformers):
    g = MagicMock()
    g.transformers = transformers
    g.unavailable_operations = []
    return g


class TestErrorHierarchy:
    def test_transform_errors_under_kartograf_error(self):
        assert issubclass(TransformError, KartografError)
        assert issubclass(TransformUnavailableError, TransformError)


class TestBuildPinnedTransform:
    def test_ballpark_disabled_in_group_construction(self):
        """(a) Grupa budowana wylacznie z allow_ballpark=False, always_xy=True."""
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group(
                [_mock_transformer(0.5, "op dokladna")]
            )
            build_pinned_transform("EPSG:5514", "EPSG:2180", TransformPolicy())
        _, kwargs = mock_cls.call_args
        assert kwargs["allow_ballpark"] is False
        assert kwargs["always_xy"] is True

    def test_empty_group_raises_with_remedy(self):
        """(b) Pusta lista operacji => TransformUnavailableError z remedium."""
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([])
            with pytest.raises(TransformUnavailableError) as exc:
                build_pinned_transform(
                    "EPSG:8357", "EPSG:9651", TransformPolicy()
                )
        assert exc.value.remedy is not None
        assert "pl07_2019" in exc.value.remedy

    def test_accuracy_filter(self):
        """(c) Odrzuc accuracy < 0 (nieznana) i > min_accuracy_m; 0.0 akceptowane."""
        good = _mock_transformer(0.0, "dokladna konwersja")
        unknown = _mock_transformer(-1.0, "nieznana dokladnosc")
        coarse = _mock_transformer(7.0, "za gruba")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([coarse, unknown, good])
            pinned = build_pinned_transform(
                "EPSG:25833", "EPSG:2180", TransformPolicy(min_accuracy_m=1.0)
            )
        assert pinned.accuracy_m == 0.0
        assert pinned.description == "dokladna konwersja"

    def test_probe_rejects_inf(self):
        """(d) Probe: operacja zwracajaca inf na punkcie kontrolnym odpada."""
        bad_grid = _mock_transformer(0.03, "siatka obcego kraju",
                                     result=(math.inf, math.inf))
        ok_op = _mock_transformer(0.5, "operacja bez siatek")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([bad_grid, ok_op])
            pinned = build_pinned_transform(
                "EPSG:5514", "EPSG:2180",
                TransformPolicy(probe_point=(-598000.0, -1160000.0)),
            )
        assert pinned.description == "operacja bez siatek"

    def test_all_rejected_lists_reasons(self):
        unknown = _mock_transformer(-1.0, "op A")
        coarse = _mock_transformer(9.9, "op B")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([unknown, coarse])
            with pytest.raises(TransformUnavailableError) as exc:
                build_pinned_transform(
                    "EPSG:4258", "EPSG:2180", TransformPolicy(min_accuracy_m=1.0)
                )
        reasons = dict(exc.value.rejected)
        assert "op A" in reasons and "op B" in reasons

    def test_result_isfinite_guard(self):
        """(e) Wynik nieskonczony => TransformError, nie dane."""
        flaky = _mock_transformer(0.5, "psuje sie po zbudowaniu")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([flaky])
            pinned = build_pinned_transform(
                "EPSG:5514", "EPSG:2180", TransformPolicy()
            )
        flaky.transform.return_value = (math.inf, 5.0)
        with pytest.raises(TransformError):
            pinned.transform(1.0, 2.0)

    def test_25833_to_2180_end_to_end_offline(self):
        """(f) Realna para DE->PL: bez siatek, dziala offline, acc 0.0."""
        policy = TransformPolicy(probe_point=(400000.0, 5800000.0))
        pinned = build_pinned_transform("EPSG:25833", "EPSG:2180", policy)
        assert pinned.accuracy_m == 0.0
        x, y = pinned.transform(400000.0, 5800000.0)
        assert x == pytest.approx(127742.88, abs=0.1)
        assert y == pytest.approx(511326.23, abs=0.1)


class TestKnownPaths:
    def test_documented_pairs_present(self):
        pairs = {(p.src, p.dst) for p in KNOWN_PATHS}
        assert ("EPSG:5514", "EPSG:2180") in pairs
        assert ("EPSG:8353", "EPSG:2180") in pairs
        assert ("EPSG:25833", "EPSG:2180") in pairs
        assert ("EPSG:8357", "EPSG:5621") in pairs
        assert ("EPSG:7837", "EPSG:5621") in pairs
        assert ("EPSG:4937", "EPSG:8357") in pairs

    def test_remedies_for_polish_vertical(self):
        assert "EPSG:9650" in REMEDIES and "EPSG:9651" in REMEDIES
```

- [ ] **Krok 4.2: Uruchom — FAIL (ImportError)**

```bash
.venv/bin/python -m pytest tests/test_transform_crs.py -q
```

- [ ] **Krok 4.3: Implementacja `kartograf/transform/__init__.py` + `crs.py`**

```python
# kartograf/transform/__init__.py
"""Twarda polityka transformacji ukladow (etap 0: infrastruktura + testy)."""
```

```python
# kartograf/transform/crs.py
"""
Twarda polityka transformacji CRS.

Cztery reguly bezpieczenstwa (kazda wynika ze zmierzonej pulapki, patrz spec
sekcja 6.4 i docs/research/2026-08-10-*):
1. Transformer budowany WYLACZNIE przez TransformerGroup(..., allow_ballpark=False,
   always_xy=True) — Transformer.from_crs potrafi cicho zwrocic identycznosc.
2. Pusta lista operacji = TransformUnavailableError, nigdy fallback.
3. Filtr: odrzuc accuracy < 0 (nieznana; pyproj koduje jako -1 — 0.0 oznacza
   operacje DOKLADNA i jest akceptowane) oraz accuracy > policy.min_accuracy_m;
   nastepnie probe na punkcie kontrolnym (inf/NaN => odrzut operacji — przypadek
   siatki obcego kraju). Z pozostalych wybierz najlepsza dokladnosc.
4. Kazdy wynik transformacji przechodzi kontrole isfinite; inaczej TransformError.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from pyproj import network
from pyproj.transformer import TransformerGroup

from kartograf.exceptions import KartografError


class TransformError(KartografError):
    """Blad transformacji wspolrzednych (np. wynik nieskonczony)."""


class TransformUnavailableError(TransformError):
    """Brak bezpiecznej operacji transformacji dla pary ukladow."""

    def __init__(
        self,
        message: str,
        rejected: list[tuple[str, str]] | None = None,
        remedy: str | None = None,
    ):
        super().__init__(message)
        self.rejected = rejected or []
        self.remedy = remedy


@dataclass(frozen=True)
class TransformPolicy:
    """Polityka doboru operacji transformacji."""

    min_accuracy_m: float = 1.0
    probe_point: tuple[float, float] | None = None   # w ukladzie zrodlowym
    allow_network_grids: bool = True                 # PROJ CDN


@dataclass(frozen=True)
class PinnedTransform:
    """Przypieta (wybrana raz, deterministyczna) operacja transformacji."""

    accuracy_m: float
    description: str        # opis operacji (trafia do sidecara w etapie 1+)
    _transformer: Any = field(repr=False)

    def transform(self, x: float, y: float, z: float | None = None) -> tuple:
        """Transformuj punkt; wynik nieskonczony/NaN => TransformError."""
        if z is None:
            result = self._transformer.transform(x, y)
        else:
            result = self._transformer.transform(x, y, z)
        if not all(math.isfinite(v) for v in result):
            raise TransformError(
                f"Transformacja zwrocila wartosc nieskonczona dla ({x}, {y})"
                f" [{self.description}]"
            )
        return result


@dataclass(frozen=True)
class KnownPath:
    """Wpis dokumentacyjny: zweryfikowana sciezka transformacji."""

    src: str
    dst: str
    expected_accuracy_m: float
    note: str


# Tabela referencyjna (spec 6.4); w etapie 0 konsumowana w testach.
KNOWN_PATHS: tuple[KnownPath, ...] = (
    KnownPath("EPSG:5514", "EPSG:2180", 0.5,
              "probe odrzuca sk_gku (inf w CZ); preferowac reprojekcje serwerowa CUZK"),
    KnownPath("EPSG:8353", "EPSG:2180", 0.001, "SK, bez siatek"),
    KnownPath("EPSG:25833", "EPSG:2180", 0.0, "DE, jedyna operacja, bez siatek"),
    KnownPath("EPSG:8357", "EPSG:5621", 0.1, "Bpv->EVRF2007; +0,12..+0,14 m"),
    KnownPath("EPSG:7837", "EPSG:5621", 0.1, "DHHN2016; realnie 1-14 mm"),
    KnownPath("EPSG:4937", "EPSG:8357", 0.03,
              "siatka sk_gku_Slovakia_ETRS89h_to_Baltic1957; probe konieczny "
              "(pierwsza operacja PROJ to siatka CZ)"),
)

_KRON86_EVRF_REMEDY = (
    "Siatki pl86_2019/pl07_2019 nie sa publiczne — zainstaluj je recznie do "
    "PROJ_DATA albo uzyj EVRF2007 (EPSG:5621)."
)

# Remedium per DOCELOWY uklad, dolaczane do TransformUnavailableError.
REMEDIES: dict[str, str] = {
    "EPSG:9650": _KRON86_EVRF_REMEDY,
    "EPSG:9651": _KRON86_EVRF_REMEDY,
}


def build_pinned_transform(
    src_crs: str, dst_crs: str, policy: TransformPolicy
) -> PinnedTransform:
    """Zbuduj przypieta transformacje wg polityki albo rzuc TransformUnavailableError."""
    network.set_network_enabled(policy.allow_network_grids)

    group = TransformerGroup(
        src_crs, dst_crs, always_xy=True, allow_ballpark=False
    )

    rejected: list[tuple[str, str]] = []
    candidates = []
    for transformer in group.transformers:
        accuracy = transformer.accuracy
        description = str(transformer.description)
        if accuracy < 0:
            rejected.append((description, "nieznana dokladnosc (accuracy < 0)"))
            continue
        if accuracy > policy.min_accuracy_m:
            rejected.append(
                (description,
                 f"dokladnosc {accuracy} m > limit {policy.min_accuracy_m} m")
            )
            continue
        if policy.probe_point is not None:
            px, py = policy.probe_point
            try:
                probe = transformer.transform(px, py)
            except Exception as e:  # noqa: BLE001 — kazdy blad probe = odrzut
                rejected.append((description, f"probe rzucil wyjatek: {e}"))
                continue
            if not all(math.isfinite(v) for v in probe):
                rejected.append(
                    (description,
                     "probe zwrocil inf/NaN (siatka nie pokrywa obszaru danych)")
                )
                continue
        candidates.append((accuracy, transformer, description))

    if not candidates:
        raise TransformUnavailableError(
            f"Brak bezpiecznej operacji transformacji {src_crs} -> {dst_crs} "
            f"(kandydatow: {len(group.transformers)}, odrzuconych: {len(rejected)})",
            rejected=rejected,
            remedy=REMEDIES.get(dst_crs),
        )

    accuracy, transformer, description = min(candidates, key=lambda c: c[0])
    return PinnedTransform(
        accuracy_m=accuracy, description=description, _transformer=transformer
    )
```

Uwaga implementacyjna: `PinnedTransform` z polem `_transformer` bez defaultu po polach bez defaultow — kolejnosc pol jest poprawna. Gdyby mypy protestowal o `Any` w frozen dataclass — zostaw `Any` (transformer pyproj nie ma stabilnego typu publicznego w tym uzyciu).

- [ ] **Krok 4.4: Testy przechodza (offline; para 25833→2180 nie wymaga siatek)**

```bash
.venv/bin/python -m pytest tests/test_transform_crs.py -q
```

- [ ] **Krok 4.5: Commit**

```bash
git add kartograf/transform/ tests/test_transform_crs.py
git commit -m "feat(transform): twarda polityka transformacji (ballpark ban, probe, isfinite)"
```

---

### Zadanie 5: `transport/http.py` — kanoniczny downloader

**Files:**
- Create: `kartograf/transport/__init__.py`, `kartograf/transport/http.py`
- Test: `tests/test_transport_http.py`

**Interfaces (Produces):** `download_to(session, url, output_path, *, timeout, retries=3, chunk_size=1_048_576) -> Path`. Konsument: etap 1 (CuzkClient). Istniejace providery NIE sa przepinane.

- [ ] **Krok 5.1: Failing testy — `tests/test_transport_http.py`**

```python
"""Testy kanonicznego downloadera (kartograf.transport.http)."""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.transport.http import download_to


def _mock_response(chunks=(b"abc", b"def")):
    resp = MagicMock()
    resp.iter_content.return_value = iter(chunks)
    resp.raise_for_status.return_value = None
    return resp


class TestDownloadTo:
    def test_atomic_write_and_content(self, tmp_path):
        session = MagicMock()
        session.get.return_value = _mock_response()
        out = tmp_path / "sub" / "plik.tif"
        result = download_to(session, "https://example.test/plik", out, timeout=5)
        assert result == out
        assert out.read_bytes() == b"abcdef"
        leftovers = [p for p in out.parent.iterdir() if p.name != "plik.tif"]
        assert leftovers == []  # tmp sprzatniety po os.replace

    def test_temp_name_uses_pid_and_thread(self, tmp_path):
        seen = {}
        real_replace = os.replace

        def spy_replace(src, dst):
            seen["src"] = str(src)
            return real_replace(src, dst)

        session = MagicMock()
        session.get.return_value = _mock_response()
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.os.replace", side_effect=spy_replace):
            download_to(session, "https://example.test/p", out, timeout=5)
        assert f".{os.getpid()}_{threading.get_ident()}.tmp" in seen["src"]

    def test_retry_then_success(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = [
            requests.ConnectionError("boom"),
            _mock_response(),
        ]
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.time.sleep") as mock_sleep:
            result = download_to(
                session, "https://example.test/p", out, timeout=5, retries=3
            )
        assert result.read_bytes() == b"abcdef"
        assert mock_sleep.call_count == 1

    def test_exhausted_retries_raise_download_error_and_cleanup(self, tmp_path):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("boom")
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.time.sleep"):
            with pytest.raises(DownloadError):
                download_to(
                    session, "https://example.test/p", out, timeout=5, retries=3
                )
        assert session.get.call_count == 3
        assert list(tmp_path.iterdir()) == []  # zadnych tmp ani czesciowych plikow

    def test_error_mid_stream_cleans_tmp(self, tmp_path):
        def broken_iter(chunk_size):
            yield b"abc"
            raise requests.ChunkedEncodingError("przerwane")

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.iter_content.side_effect = broken_iter
        session = MagicMock()
        session.get.return_value = resp
        out = tmp_path / "plik.tif"
        with patch("kartograf.transport.http.time.sleep"):
            with pytest.raises(DownloadError):
                download_to(
                    session, "https://example.test/p", out, timeout=5, retries=1
                )
        assert list(tmp_path.iterdir()) == []
```

- [ ] **Krok 5.2: Uruchom — FAIL**

```bash
.venv/bin/python -m pytest tests/test_transport_http.py -q
```

- [ ] **Krok 5.3: Implementacja**

```python
# kartograf/transport/__init__.py
"""Wspolne narzedzia transportowe (downloader HTTP, mozaikowanie rastrow)."""
```

```python
# kartograf/transport/http.py
"""
Kanoniczny downloader HTTP dla NOWEGO kodu (etap 1+).

Wzorzec: zapis do pliku tymczasowego `pid_tid.tmp` + os.replace (atomowo),
retry z backoffem wykladniczym, DownloadError po wyczerpaniu prob.
Istniejace providery maja wlasne, przetestowane implementacje tego wzorca
i NIE sa przepinane w etapie 0.
"""

import logging
import os
import threading
import time
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE = 2


def download_to(
    session: requests.Session,
    url: str,
    output_path: Path,
    *,
    timeout: int,
    retries: int = 3,
    chunk_size: int = 1_048_576,
) -> Path:
    """Pobierz URL do output_path (atomowo, z retry); zwroc output_path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(
        f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        f.write(chunk)
            os.replace(temp_path, output_path)
            return output_path
        except requests.RequestException as e:
            last_error = e
            if temp_path.exists():
                temp_path.unlink()
            if attempt < retries - 1:
                wait = RETRY_BACKOFF_BASE**attempt
                logger.warning(
                    f"Pobranie {url} nieudane (proba {attempt + 1}/{retries}): "
                    f"{e}; ponowienie za {wait}s"
                )
                time.sleep(wait)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    raise DownloadError(
        f"Nie udalo sie pobrac {url} po {retries} probach: {last_error}"
    )
```

- [ ] **Krok 5.4: Testy przechodza**

```bash
.venv/bin/python -m pytest tests/test_transport_http.py -q
```

- [ ] **Krok 5.5: Commit**

```bash
git add kartograf/transport/ tests/test_transport_http.py
git commit -m "feat(transport): download_to — atomic write, retry z backoffem"
```

---

### Zadanie 6: `transport/mosaic.py` — zszywanie i przycinanie kafli

**Files:**
- Create: `kartograf/transport/mosaic.py`
- Test: `tests/test_transport_mosaic.py`

**Interfaces (Produces):** `mosaic_and_crop(inputs: list[Path], bbox: BBox, output_path: Path, *, nodata: float | None = None) -> Path`. Walidacje -> `ValidationError` (z `kartograf.exceptions`). Pierwszy konsument: etap 1 (kafelkowanie exportImage > 15000x4100 px).

Fakt z pomiaru (rasterio 1.5.0): `rasterio.merge.merge(sources, bounds=None, res=None, nodata=None, ...)` — przyjmuje `bounds` i `nodata`, zwraca `(array, transform)`.

- [ ] **Krok 6.1: Failing testy — `tests/test_transport_mosaic.py`**

```python
"""Testy mozaikowania (kartograf.transport.mosaic) na syntetycznych rastrach."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.transport.mosaic import mosaic_and_crop


def _write_tile(
    path: Path,
    origin_x: float,
    origin_y: float,
    value: float,
    size: int = 10,
    res: float = 1.0,
    crs: str = "EPSG:2180",
    nodata: float | None = None,
) -> Path:
    data = np.full((size, size), value, dtype="float32")
    profile = {
        "driver": "GTiff", "height": size, "width": size, "count": 1,
        "dtype": "float32", "crs": crs,
        "transform": from_origin(origin_x, origin_y, res, res),
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


@pytest.fixture
def four_tiles(tmp_path):
    # Kafle 2x2 (kazdy 10x10 m, res 1 m): wspolny naroznik w (10, 10).
    return [
        _write_tile(tmp_path / "a.tif", 0, 20, 1.0),    # NW
        _write_tile(tmp_path / "b.tif", 10, 20, 2.0),   # NE
        _write_tile(tmp_path / "c.tif", 0, 10, 3.0),    # SW
        _write_tile(tmp_path / "d.tif", 10, 10, 4.0),   # SE
    ]


class TestMosaicAndCrop:
    def test_merge_and_crop_to_bbox(self, four_tiles, tmp_path):
        out = mosaic_and_crop(
            four_tiles, BBox(5.0, 5.0, 15.0, 15.0, "EPSG:2180"),
            tmp_path / "out.tif",
        )
        with rasterio.open(out) as src:
            assert src.width == 10 and src.height == 10
            assert src.bounds == pytest.approx((5.0, 5.0, 15.0, 15.0))
            data = src.read(1)
        # Cwiartki wyniku pochodza z 4 roznych kafli.
        assert data[0, 0] == 1.0 and data[0, -1] == 2.0
        assert data[-1, 0] == 3.0 and data[-1, -1] == 4.0

    def test_nodata_propagated_never_zeroed(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, nodata=-9999.0),
        ]
        out = mosaic_and_crop(
            tiles, BBox(0.0, 0.0, 20.0, 10.0, "EPSG:2180"),
            tmp_path / "out.tif", nodata=-9999.0,
        )
        with rasterio.open(out) as src:
            assert src.nodata == -9999.0
            data = src.read(1)
        # Obszar bez pokrycia (x 10..20) = nodata, NIE 0.
        assert data[0, -1] == -9999.0

    def test_empty_inputs_raise(self, tmp_path):
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                [], BBox(0, 0, 1, 1, "EPSG:2180"), tmp_path / "out.tif"
            )

    def test_crs_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, crs="EPSG:2180"),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, crs="EPSG:2177"),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )

    def test_resolution_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, res=1.0),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, res=2.0),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )
```

- [ ] **Krok 6.2: Uruchom — FAIL**

```bash
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q
```

- [ ] **Krok 6.3: Implementacja `kartograf/transport/mosaic.py`**

```python
"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px); kolejni: Saksonia (brak WCS). Nodata jest propagowane do
wyniku — NIGDY nie zamieniane na 0.
"""

import contextlib
from pathlib import Path

import rasterio
from rasterio.merge import merge

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError


def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
) -> Path:
    """Zszyj rastry wejsciowe i przytnij do bbox; zwroc output_path."""
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    with contextlib.ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(p)) for p in inputs]

        crs_set = {str(src.crs) for src in sources}
        if len(crs_set) > 1:
            raise ValidationError(
                f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
            )
        res_set = {src.res for src in sources}
        if len(res_set) > 1:
            raise ValidationError(
                f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
            )

        data, transform = merge(
            sources,
            bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
            nodata=nodata,
        )

        profile = sources[0].profile.copy()
        profile.update(
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            transform=transform,
        )
        if nodata is not None:
            profile["nodata"] = nodata

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data)
    return output_path
```

- [ ] **Krok 6.4: Testy przechodza + pelny pytest**

```bash
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q && .venv/bin/python -m pytest tests/ -q
```

- [ ] **Krok 6.5: Commit**

```bash
git add kartograf/transport/mosaic.py tests/test_transport_mosaic.py
git commit -m "feat(transport): mosaic_and_crop — merge kafli + przyciecie, propagacja nodata"
```

---

### Zadanie 7: `core/parser_registry.py` + delegacja z `SheetParser` i `FileStorage`

**Files:**
- Create: `kartograf/core/parser_registry.py`
- Modify: `kartograf/core/sheet_parser.py:20-22` (`_is_pl2000_format`), `kartograf/download/storage.py:190-218` (`_get_directory_parts`)
- Test: `tests/test_parser_registry.py`

**Interfaces:**
- Produces: `SheetSystem` (frozen dataclass: `id, country, detect, parser_factory, path_parts`), `register_system(system)`, `detect_system(godlo) -> SheetSystem | None`, `path_parts(godlo) -> list[str]`. Wpisy `pl2000` (regex `^[5-8]\.\d`) i `pl1992` (fallback) rejestrowane przy imporcie modulu.
- Publiczne API `SheetParser`/`FileStorage` BEZ zmian; wyniki identyczne (pilnuja istniejace testy `test_sheet_parser.py`, `test_storage.py`, `test_parser_2000.py`).

Kluczowy trik zgodnosci: `SheetParser.__init__` (sheet_parser.py:131) NADAL wola `_is_pl2000_format(cleaned)` — zmieniamy tylko CIALO tej funkcji na delegacje do rejestru. Zero zmian w `__init__`, komunikaty ValidationError nietkniete.

- [ ] **Krok 7.1: Failing testy — `tests/test_parser_registry.py`**

```python
"""Testy rejestru systemow godel (kartograf.core.parser_registry)."""

import pytest

from kartograf.core import parser_registry
from kartograf.core.parser_registry import SheetSystem, detect_system, path_parts


class TestDetection:
    def test_pl2000_detected(self):
        system = detect_system("6.179.12.20")
        assert system is not None and system.id == "pl2000"
        assert system.country == "PL"

    def test_pl1992_fallback(self):
        assert detect_system("N-34-130-D-d-2-4").id == "pl1992"
        assert detect_system("N-34").id == "pl1992"
        # Opaque godlo kafla LAZ (drobniejsze niz 1:10000) tez trafia do pl1992
        assert detect_system("N-33-131-B-a-1-1-4").id == "pl1992"

    def test_registration_order_and_duplicate_guard(self):
        with pytest.raises(ValueError):
            parser_registry.register_system(
                SheetSystem(
                    id="pl2000", country="PL", detect=lambda g: False,
                    parser_factory=lambda g: None, path_parts=lambda g: [],
                )
            )


class TestPathParts:
    """Zlote wartosci — identyczne z dotychczasowym FileStorage._get_directory_parts."""

    @pytest.mark.parametrize(
        ("godlo", "expected"),
        [
            ("N-34-130-D-d-2-4", ["N-34", "130", "D", "d", "2", "4"]),
            ("N-34-130-D", ["N-34", "130", "D"]),
            ("N-34", ["N-34"]),
            ("M-34-27-B-b-2-1-1", ["M-34", "27", "B", "b", "2", "1", "1"]),
            ("6.179.12.20", ["6", "179", "12", "20"]),
            ("6.179.12", ["6", "179", "12"]),
            ("6.162.34.02.3", ["6", "162", "34", "02", "3"]),
        ],
    )
    def test_golden_values(self, godlo, expected):
        assert path_parts(godlo) == expected


class TestParserFactories:
    def test_pl2000_factory(self):
        parser = detect_system("6.179.12.20").parser_factory("6.179.12.20")
        assert parser.godlo == "6.179.12.20"

    def test_pl1992_factory(self):
        parser = detect_system("N-34-130-D").parser_factory("N-34-130-D")
        assert parser.scale == "1:100000"


class TestSheetParserIntegration:
    def test_is_pl2000_format_delegates_to_registry(self):
        from kartograf.core.sheet_parser import _is_pl2000_format

        assert _is_pl2000_format("6.179.12.20") is True
        assert _is_pl2000_format("N-34-130-D") is False
        assert _is_pl2000_format("4.179.12") is False  # strefa spoza 5-8
```

- [ ] **Krok 7.2: Uruchom — FAIL (ModuleNotFoundError)**

```bash
.venv/bin/python -m pytest tests/test_parser_registry.py -q
```

- [ ] **Krok 7.3: Implementacja `kartograf/core/parser_registry.py`**

```python
"""
Rejestr systemow godel (etap 0: pl1992 + pl2000; etap 1: cz_tm33, cz_sm5).

Logika detekcji PL-2000 (regex) i dzielenia sciezek przeniesiona 1:1
z sheet_parser._is_pl2000_format i FileStorage._get_directory_parts.
Fabryki parserow uzywaja importow lazy (unikamy cyklu importow z sheet_parser).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SheetSystem:
    """Opis jednego systemu godlowania arkuszy."""

    id: str                                  # "pl1992", "pl2000"
    country: str
    detect: Callable[[str], bool]
    parser_factory: Callable[[str], Any]     # obiekt z .godlo, .get_bbox(), ...
    path_parts: Callable[[str], list[str]]   # czesci sciezki dla FileStorage


_REGISTRY: list[SheetSystem] = []


def register_system(system: SheetSystem) -> None:
    """Zarejestruj system godel; ValueError przy duplikacie id."""
    if any(s.id == system.id for s in _REGISTRY):
        raise ValueError(f"System godel '{system.id}' jest juz zarejestrowany")
    _REGISTRY.append(system)


def detect_system(godlo: str) -> SheetSystem | None:
    """Zwroc pierwszy system (w kolejnosci rejestracji), ktorego detect pasuje."""
    for system in _REGISTRY:
        if system.detect(godlo):
            return system
    return None


def path_parts(godlo: str) -> list[str]:
    """Czesci sciezki katalogowej dla godla wg wykrytego systemu."""
    system = detect_system(godlo)
    if system is None:
        raise ValueError(f"Brak systemu godel pasujacego do: '{godlo}'")
    return system.path_parts(godlo)


_PL2000_PATTERN = re.compile(r"^[5-8]\.\d")


def _detect_pl2000(godlo: str) -> bool:
    return bool(_PL2000_PATTERN.match(godlo))


def _pl2000_path_parts(godlo: str) -> list[str]:
    # PL-2000: split on dots, use all parts as directory hierarchy
    return godlo.split(".")


def _pl1992_path_parts(godlo: str) -> list[str]:
    # PL-1992: split on dashes, first two parts form the base (e.g. N-34)
    parts = godlo.split("-")
    dir_parts = [f"{parts[0]}-{parts[1]}"]
    for part in parts[2:]:
        dir_parts.append(part)
    return dir_parts


def _make_parser_pl2000(godlo: str) -> Any:
    from kartograf.core.parser_2000 import Parser2000

    return Parser2000(godlo)


def _make_parser_pl1992(godlo: str) -> Any:
    from kartograf.core.sheet_parser import SheetParser

    return SheetParser(godlo)


register_system(
    SheetSystem(
        id="pl2000",
        country="PL",
        detect=_detect_pl2000,
        parser_factory=_make_parser_pl2000,
        path_parts=_pl2000_path_parts,
    )
)
register_system(
    SheetSystem(
        id="pl1992",
        country="PL",
        detect=lambda godlo: True,   # fallback — zawsze ostatni
        parser_factory=_make_parser_pl1992,
        path_parts=_pl1992_path_parts,
    )
)
```

- [ ] **Krok 7.4: Delegacja w `sheet_parser.py` — zmien TYLKO cialo `_is_pl2000_format`**

Stan obecny (sheet_parser.py:20-22):

```python
def _is_pl2000_format(godlo: str) -> bool:
    """Check if godlo uses PL-2000 dot-separated numeric format."""
    return bool(re.match(r"^[5-8]\.\d", godlo))
```

Nowa wersja (dodaj u gory pliku `from kartograf.core import parser_registry` — parser_registry NIE importuje sheet_parser na poziomie modulu, wiec cyklu nie ma):

```python
def _is_pl2000_format(godlo: str) -> bool:
    """Check if godlo uses PL-2000 dot-separated numeric format (via registry)."""
    system = parser_registry.detect_system(godlo)
    return system is not None and system.id == "pl2000"
```

Jesli `re` przestanie byc uzywane gdzie indziej w sheet_parser.py — NIE usuwaj importu bez sprawdzenia (`grep -n "re\." kartograf/core/sheet_parser.py` — modul uzywa re takze w PATTERNS/parsowaniu; zostanie).

- [ ] **Krok 7.5: Delegacja w `storage.py` — zmien TYLKO cialo `_get_directory_parts`**

Dodaj u gory `from kartograf.core import parser_registry`; cialo metody (storage.py:209-218) zamien na:

```python
        return parser_registry.path_parts(godlo)
```

(docstring metody zostaje bez zmian).

- [ ] **Krok 7.6: Nowe + istniejace testy przechodza (pelny pytest — inwariant!)**

```bash
.venv/bin/python -m pytest tests/test_parser_registry.py tests/test_storage.py tests/test_sheet_parser.py tests/test_parser_2000.py -q
.venv/bin/python -m pytest tests/ -q
```

Oczekiwane: komplet zielony, zero zmian w istniejacych testach.

- [ ] **Krok 7.7: Commit**

```bash
git add kartograf/core/parser_registry.py kartograf/core/sheet_parser.py kartograf/download/storage.py tests/test_parser_registry.py
git commit -m "feat(core): rejestr systemow godel; SheetParser i FileStorage deleguja do rejestru"
```

---

### Zadanie 8: `FileStorage` — opcjonalny `subdir` z deskryptora

**Files:**
- Modify: `kartograf/download/storage.py:56-112` (`__init__`, `_subdir`, `__repr__`)
- Test: `tests/test_storage.py` (WYLACZNIE dopisanie nowej klasy testowej — istniejace bez zmian)

**Interfaces:** `FileStorage(output_dir, resolution="1m", product=None, subdir=None)` — `subdir` ma pierwszenstwo przed `product` i `resolution`; `None` ⇒ logika dotychczasowa bez zmian. `SUPPORTED_RESOLUTIONS` zostaje (walidacja legacy `resolution`).

- [ ] **Krok 8.1: Failing testy — dopisz na koncu `tests/test_storage.py`**

```python
class TestSubdirOverride:
    """Etap 0: subdir sterowany deskryptorem (etap 1: np. cz_dmr5g)."""

    def test_subdir_takes_precedence(self, tmp_path):
        storage = FileStorage(tmp_path, subdir="cz_dmr5g")
        path = storage.get_raw_path("302_5550", "302_5550.tif")
        assert path == tmp_path / "cz_dmr5g" / "302_5550" / "302_5550.tif"

    def test_subdir_wins_over_product_and_resolution(self, tmp_path):
        storage = FileStorage(tmp_path, resolution="5m", product="orto",
                              subdir="wlasny")
        assert storage.get_path("N-34", ".asc") == (
            tmp_path / "wlasny" / "N-34" / "N-34.asc"
        )

    def test_none_keeps_legacy_behavior(self, tmp_path):
        assert FileStorage(tmp_path, resolution="1m").get_path("N-34", ".asc") == (
            tmp_path / "nmt_1m" / "N-34" / "N-34.asc"
        )
        assert FileStorage(tmp_path, product="nmpt").get_path("N-34", ".asc") == (
            tmp_path / "nmpt" / "N-34" / "N-34.asc"
        )

    def test_repr_with_subdir(self, tmp_path):
        assert "subdir='cz_dmr5g'" in repr(FileStorage(tmp_path, subdir="cz_dmr5g"))
```

Uwaga: `FileStorage(tmp_path, resolution="5m", product="orto", subdir=...)` przechodzi dzis walidacje, bo `product` wylacza walidacje resolution — zachowujemy te kolejnosc galezi.

- [ ] **Krok 8.2: Uruchom — FAIL (`TypeError: unexpected keyword argument 'subdir'`)**

```bash
.venv/bin/python -m pytest tests/test_storage.py -q -k Subdir
```

- [ ] **Krok 8.3: Implementacja — zmiany w `storage.py`**

`__init__` — nowa sygnatura i jedna dodatkowa linia (reszta ciala bez zmian):

```python
    def __init__(
        self,
        output_dir: str | Path = "./data",
        resolution: str = "1m",
        product: str | None = None,
        subdir: str | None = None,
    ):
        # ... istniejacy docstring rozszerzony o subdir ...
        self._subdir_override = subdir
        if product:
            self._product = product
            self._resolution = ""
        else:
            ...  # istniejace cialo bez zmian
```

Property `_subdir` (storage.py:107-112) — dolozyc pierwszenstwo:

```python
    @property
    def _subdir(self) -> str:
        """Return subdirectory name (override, product or nmt_<resolution>)."""
        if self._subdir_override:
            return self._subdir_override
        if self._product:
            return self._product
        return self._RESOLUTION_SUBDIRS.get(self._resolution, self._resolution)
```

`__repr__` — dolozyc galaz PRZED istniejacymi (tylko dla nowego przypadku):

```python
        if self._subdir_override:
            return (
                f"FileStorage(output_dir='{self._output_dir}', "
                f"subdir='{self._subdir_override}')"
            )
```

- [ ] **Krok 8.4: Testy przechodza (cale test_storage + pelny pytest)**

```bash
.venv/bin/python -m pytest tests/test_storage.py -q && .venv/bin/python -m pytest tests/ -q
```

- [ ] **Krok 8.5: Commit**

```bash
git add kartograf/download/storage.py tests/test_storage.py
git commit -m "feat(storage): opcjonalny subdir sterowany deskryptorem (logika PL bez zmian)"
```

---

### Zadanie 9: Unifikacja ABC — `DataSourceProvider`, `LandCoverProvider` w `base.py`, aliasy teryt

**Files:**
- Modify: `kartograf/providers/base.py` (dodanie `DataSourceProvider` + wchloniecie `LandCoverProvider`)
- Delete: `kartograf/providers/landcover_base.py` (bez shima)
- Modify (importy): `kartograf/__init__.py:47`, `kartograf/providers/__init__.py:20`, `kartograf/providers/bdot10k.py:43`, `kartograf/providers/corine.py:48`, `kartograf/providers/soilgrids.py:44`, `kartograf/landcover/manager.py:18`
- Modify (source_url -> base_url): `bdot10k.py:141-144`, `corine.py:465-468`, `soilgrids.py:155-158`
- Modify (admin_unit): `bdot10k.py:150-205` (+ wywolania wewnetrzne :289, :454, :187)
- Test: `tests/test_landcover.py:25` (import — jedyna dozwolona zmiana istniejacego testu) + nowe testy aliasow dopisane na koncu pliku

**Interfaces (Produces):**
- `DataSourceProvider(ABC)`: abstrakcyjne property `name`, `base_url`; atrybut klasowy `descriptor_key: str | None = None` (wartosci per provider dopiero w Zadaniu 12).
- `BaseProvider(DataSourceProvider)`: bez zmian kontraktu (default_extension, download, download_bbox, get_supported_formats, get_file_extension, validate_godlo, __repr__, __str__ — identyczne jak dzis).
- `LandCoverProvider(DataSourceProvider)`: `source_url` = konkretna property-alias `base_url` (deprecated w docstringu); NOWE `download_by_admin_unit(code, output_path, timeout=120, **kwargs)` i `validate_admin_unit(code)`; `download_by_teryt`/`validate_teryt` = trzyliniowe wrappery wolajace NOWE nazwy (nigdy odwrotnie!). Reszta (download_by_bbox abstract, download_by_godlo, get_available_layers, get_supported_formats, get_file_extension, __repr__, __str__) — przeniesiona verbatim z landcover_base.py.

- [ ] **Krok 9.1: Failing testy aliasow — dopisz na koncu `tests/test_landcover.py`**

```python
class TestAdminUnitAliases:
    """Etap 0 (spec 6.7): kanoniczne download_by_admin_unit + aliasy teryt."""

    def test_validate_admin_unit_same_as_teryt(self):
        provider = Bdot10kProvider()
        assert provider.validate_admin_unit("1465") is True
        assert provider.validate_admin_unit("123") is False
        assert provider.validate_teryt("1465") is provider.validate_admin_unit("1465")

    def test_download_by_teryt_delegates_to_admin_unit(self, tmp_path):
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"
        with patch.object(
            provider, "download_by_admin_unit", return_value=output
        ) as mock_new:
            result = provider.download_by_teryt("1465", output, timeout=99)
        mock_new.assert_called_once_with("1465", output, timeout=99)
        assert result == output

    def test_source_url_aliases_base_url(self):
        provider = Bdot10kProvider()
        assert provider.source_url == provider.base_url

    def test_data_source_provider_hierarchy(self):
        from kartograf.providers.base import BaseProvider, DataSourceProvider

        assert issubclass(LandCoverProvider, DataSourceProvider)
        assert issubclass(BaseProvider, DataSourceProvider)
        assert DataSourceProvider.descriptor_key is None
```

(`patch` jest juz importowany w test_landcover.py; jesli nie w tym zakresie — uzyj istniejacego stylu importow z tego pliku.)

- [ ] **Krok 9.2: Uruchom — FAIL (brak metod/klas)**

```bash
.venv/bin/python -m pytest tests/test_landcover.py -q -k AdminUnitAliases
```

- [ ] **Krok 9.3: Przebuduj `kartograf/providers/base.py`**

Struktura docelowa pliku (kod istniejacych metod KOPIUJ verbatim z obecnego base.py i landcover_base.py — nie przepisuj z pamieci):

```python
"""
Base provider classes for data download services.

DataSourceProvider — wspolny korzen wszystkich providerow (nazwa, URL,
wiazanie z rejestrem zrodel przez descriptor_key).
BaseProvider — rastry/arkusze (NMT/NMPT/Orto/LAZ), jak dotychczas.
LandCoverProvider — pokrycie terenu (BDOT10k/CORINE/SoilGrids); przeniesiony
z landcover_base.py (usuniety bez shima, etap 0 spec 6.7).
"""

from abc import ABC, abstractmethod
from pathlib import Path

from kartograf.core.sheet_parser import BBox


class DataSourceProvider(ABC):
    """Wspolny korzen providerow zrodel danych."""

    #: Klucz deskryptora w kartograf.sources.registry (None = niezwiazany).
    descriptor_key: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable name of the provider."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return base URL for the provider's service."""


class BaseProvider(DataSourceProvider):
    # DOKLADNIE dzisiejsza tresc klasy BaseProvider (base.py:15-207),
    # bez powtarzania name/base_url (dziedziczone abstrakty pozostaja
    # niespelnione, wiec klasa dalej jest abstrakcyjna dla podklas bez nich).
    # Zostaja: default_extension, download (abstract), download_bbox,
    # get_supported_formats, get_file_extension, validate_godlo,
    # __repr__, __str__ — verbatim.
    ...


class LandCoverProvider(DataSourceProvider):
    # Tresc z landcover_base.py:15-266 verbatim, ze zmianami:
    # 1. USUN abstrakcyjne source_url; w zamian:
    @property
    def source_url(self) -> str:
        """Deprecated alias for base_url (kept for backward compatibility)."""
        return self.base_url

    # 2. NOWE kanoniczne metody + stare nazwy jako wrappery:
    def download_by_admin_unit(
        self,
        code: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """Download data for an administrative unit (canonical name).

        Dla PL kodem jednostki jest TERYT. Domyslnie nieobslugiwane.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support TERYT downloads"
        )

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """Deprecated alias for download_by_admin_unit."""
        return self.download_by_admin_unit(teryt, output_path, timeout=timeout, **kwargs)

    def validate_admin_unit(self, code: str) -> bool:
        """Validate administrative-unit code (canonical name).

        PL: TERYT — 4 cyfry (powiat) lub 7 cyfr (gmina).
        """
        if not code or not code.isdigit():
            return False
        # Powiat: 4 digits, Gmina: 7 digits
        return len(code) in (4, 7)

    def validate_teryt(self, teryt: str) -> bool:
        """Deprecated alias for validate_admin_unit."""
        return self.validate_admin_unit(teryt)

    # 3. Reszta verbatim: download_by_bbox (abstract), download_by_godlo,
    #    get_available_layers, get_supported_formats, get_file_extension,
    #    __repr__, __str__. W docstringu przykladu klasy zamien source_url
    #    na base_url.
```

WAZNE zgodnosci:
- Komunikat NotImplementedError w `download_by_admin_unit` = DOSLOWNIE dzisiejszy komunikat `download_by_teryt` ("does not support TERYT downloads") — testy moga go dotykac.
- `CorineProvider.download_by_teryt` (corine.py:871-889, zawsze raise NotImplementedError) ZOSTAJE bez zmian — nadpisuje wrapper, test `test_download_by_teryt_not_supported` dalej trafia w ten sam wyjatek.
- Cialo `validate_admin_unit` = przeniesione cialo `validate_teryt` (landcover_base.py:241-258).

- [ ] **Krok 9.4: `Bdot10kProvider` — przenosiny na nazwy kanoniczne**

W `bdot10k.py`:
1. Zmien nazwe metody `download_by_teryt` -> `download_by_admin_unit`, parametr `teryt` -> `code`; W CIELE: `self.validate_teryt(teryt)` -> `self.validate_admin_unit(code)`; komunikaty interpoluja wartosc, wiec tekst wyjatkow pozostaje identyczny (`f"Invalid TERYT code: {code}"`, `description=f"BDOT10k TERYT {code}"`).
2. Wywolania wewnetrzne `self.download_by_teryt(` (bdot10k.py:289 w `download_by_godlo`, :454 w `download_by_bbox`) -> `self.download_by_admin_unit(`.
3. Property `source_url` (bdot10k.py:141-144) -> `base_url` (tresc bez zmian, zwraca "https://www.geoportal.gov.pl/dane/bdot10k").
4. Import: `from kartograf.providers.landcover_base import LandCoverProvider` -> `from kartograf.providers.base import LandCoverProvider`.

- [ ] **Krok 9.5: `corine.py` i `soilgrids.py`**

- Import landcover_base -> base (jak wyzej).
- `source_url` -> `base_url` (corine.py:465-468, soilgrids.py:155-158; tresc bez zmian).
- soilgrids.py:413 `self.validate_teryt(teryt)` moze zostac (wrapper dziala); NIE zmieniaj — minimalizacja diffu.
- corine.py: `download_by_teryt` override zostaje jak jest.

- [ ] **Krok 9.6: Pozostale importy + usuniecie landcover_base**

```bash
# landcover/manager.py:18 i providers/__init__.py:20 i kartograf/__init__.py:47:
#   from kartograf.providers.landcover_base import LandCoverProvider
#   -> from kartograf.providers.base import LandCoverProvider
# tests/test_landcover.py:25 — ta sama zamiana (dozwolona: import po usunietym module)
git rm kartograf/providers/landcover_base.py
grep -rn "landcover_base" kartograf/ tests/   # oczekiwane: 0 trafien
```

- [ ] **Krok 9.7: Pelny pytest + ruff — inwariant**

```bash
.venv/bin/python -m pytest tests/ -q && .venv/bin/python -m ruff check kartograf/ tests/
```

- [ ] **Krok 9.8: Commit**

```bash
git add -A
git commit -m "refactor(providers)!: DataSourceProvider + LandCoverProvider w base.py; download_by_admin_unit z aliasami teryt

BREAKING CHANGE: kartograf.providers.landcover_base usuniety bez shima —
importowac LandCoverProvider z kartograf.providers.base (albo z kartograf)."
```

---

### Zadanie 10: Przenosiny `providers/pl/` (git mv, 1:1, bez shimow)

**Files:**
- Move (git mv): `kartograf/providers/{gugik,gugik_nmpt,gugik_orto,gugik_laz,bdot10k}.py` -> `kartograf/providers/pl/`
- Create: `kartograf/providers/pl/__init__.py` (na razie same eksporty; fabryka w Zadaniu 11)
- Modify (importy w kodzie): `kartograf/providers/pl/gugik_nmpt.py:17`, `kartograf/__init__.py:41-46`, `kartograf/providers/__init__.py`, `kartograf/landcover/manager.py:16`, `kartograf/download/manager.py:21`, `kartograf/cli/commands.py:609,612,617,622,980,1212,1219,1229`
- Modify (testy — WYLACZNIE mechaniczna zamiana sciezek/patch-targetow): lista ponizej

Osobny commit przenosin, weryfikowany pelnym pytest (mitygacja z sekcji 11 specu).

- [ ] **Krok 10.1: Przenies pliki**

```bash
mkdir -p kartograf/providers/pl
git mv kartograf/providers/gugik.py kartograf/providers/pl/gugik.py
git mv kartograf/providers/gugik_nmpt.py kartograf/providers/pl/gugik_nmpt.py
git mv kartograf/providers/gugik_orto.py kartograf/providers/pl/gugik_orto.py
git mv kartograf/providers/gugik_laz.py kartograf/providers/pl/gugik_laz.py
git mv kartograf/providers/bdot10k.py kartograf/providers/pl/bdot10k.py
```

- [ ] **Krok 10.2: `kartograf/providers/pl/__init__.py`**

```python
"""Providery polskich zrodel danych (GUGiK)."""

from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

__all__ = [
    "Bdot10kProvider",
    "GugikProvider",
    "GugikLazProvider",
    "GugikNmptProvider",
    "GugikOrtoProvider",
    "LazTile",
]
```

- [ ] **Krok 10.3: Mechaniczna zamiana sciezek w kodzie i testach**

Prefiksy `kartograf.providers.gugik*` i `kartograf.providers.bdot10k` sa jednoznaczne (nie koliduja z `providers.base`), wiec globalna zamiana jest bezpieczna:

```bash
grep -rln "kartograf\.providers\.\(gugik\|bdot10k\)" kartograf/ tests/ | xargs sed -i \
  -e 's/kartograf\.providers\.gugik/kartograf.providers.pl.gugik/g' \
  -e 's/kartograf\.providers\.bdot10k/kartograf.providers.pl.bdot10k/g'
grep -rn "kartograf\.providers\.\(gugik\|bdot10k\)\b" kartograf/ tests/ | grep -v "providers\.pl"  # oczekiwane: 0
```

Ta zamiana zalatwia (pelna lista z grepa — zweryfikuj, ze wszystkie pliki sa w diffie):
- kod: `pl/gugik_nmpt.py:17` (import gugik), `kartograf/__init__.py:41-46`, `providers/__init__.py:16-19`, `landcover/manager.py:16`, `download/manager.py:21`, `cli/commands.py` (8 importow lokalnych)
- testy (importy): `test_gugik_orto.py:16`, `test_parallel_download.py:25`, `test_gugik_laz.py:16`, `test_metadata_cache.py:29-32`, `test_gugik_nmpt.py:19-20`, `test_gugik_provider.py:16`, `test_wms_layer_validation.py:20-22`, `test_cli.py:724,736,747,1798`, `test_download_manager.py:18`, `test_landcover.py:20`
- testy (patch-targety, sekcja 9 specu): `test_gugik_laz.py:19` (`_LAZ_SESSION_PATCH`), `test_gugik_laz.py:406` (`time.sleep`), `test_wms_layer_validation.py:118` (`_SESSION_PATCH`), `:321,338,356,374,405` (`gugik.logger`), `:492` (`_ORTO_SESSION_PATCH`), `:562,576,594` (`gugik_orto.logger`), `test_cli.py:1848,1876,1898,1924` (`GugikLazProvider`), `test_landcover.py:484` (`bdot10k.time.sleep`)

- [ ] **Krok 10.4: Uporzadkuj `kartograf/providers/__init__.py` (docstring + eksporty przez pl)**

Po sedzie importy wskazuja `providers.pl.*` — zostaw eksportowane nazwy IDENTYCZNE jak dzis (`BaseProvider`, `GugikProvider`, `GugikLazProvider`, `LandCoverProvider`, `Bdot10kProvider`, `CorineProvider`, `SoilGridsProvider`); w docstringu dopisz, ze providery polskie zyja w `providers/pl/`.

- [ ] **Krok 10.5: Pelny pytest + ruff (inwariant — commit przenosin musi byc zielony)**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m ruff check kartograf/ tests/ && .venv/bin/python -m ruff format --check kartograf/ tests/
```

- [ ] **Krok 10.6: Commit**

```bash
git add -A
git commit -m "refactor(providers)!: przenosiny gugik*/bdot10k do providers/pl bez shimow

BREAKING CHANGE: glebokie importy kartograf.providers.gugik* i
kartograf.providers.bdot10k przestaja dzialac — uzyj kartograf.providers.pl.*
albo stabilnego 'from kartograf import ...'. Tabela migracji w CHANGELOG."
```

---

### Zadanie 11: Fabryka `create_nmt_provider` + przepiecie DownloadManager i CLI

**Files:**
- Modify: `kartograf/providers/pl/__init__.py` (fabryka), `kartograf/download/manager.py:21,179-181`, `kartograf/cli/commands.py:606-630` (`_create_provider_and_storage`)
- Test: `tests/test_sources_registry.py` LUB nowy blok w `tests/test_download_manager.py` — fabryka (ponizej dodajemy do test_download_manager.py)

**Interfaces (Produces):** `create_nmt_provider(vertical_crs="EVRF2007", resolution="1m", session=None, cache=None) -> GugikProvider` — jedno miejsce polskich domyslow NMT, w tym regula "5m ⇒ EVRF2007" (warning + korekta, identyczny komunikat jak w managerze). Regula w `DownloadManager.__init__` ZOSTAJE (patrz "Decyzje planu" pkt 4).

- [ ] **Krok 11.1: Failing test — dopisz do `tests/test_download_manager.py`**

```python
class TestCreateNmtProviderFactory:
    def test_defaults(self):
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider()
        assert provider.resolution == "1m"
        assert provider.vertical_crs == "EVRF2007"

    def test_5m_forces_evrf2007_with_warning(self, caplog):
        import logging

        from kartograf.providers.pl import create_nmt_provider

        with caplog.at_level(logging.WARNING):
            provider = create_nmt_provider(vertical_crs="KRON86", resolution="5m")
        assert provider.vertical_crs == "EVRF2007"
        assert "5m only supports EVRF2007" in caplog.text

    def test_passes_session_and_cache(self):
        from unittest.mock import MagicMock

        from kartograf.providers.pl import create_nmt_provider

        session, cache = MagicMock(), MagicMock()
        provider = create_nmt_provider(session=session, cache=cache)
        assert provider._session is session and provider._cache is cache
```

- [ ] **Krok 11.2: Uruchom — FAIL (ImportError)**

```bash
.venv/bin/python -m pytest tests/test_download_manager.py -q -k Factory
```

- [ ] **Krok 11.3: Fabryka — dopisz do `kartograf/providers/pl/__init__.py`**

```python
import logging

import requests

logger = logging.getLogger(__name__)


def create_nmt_provider(
    vertical_crs: str = "EVRF2007",
    resolution: str = "1m",
    session: requests.Session | None = None,
    cache=None,
) -> GugikProvider:
    """Fabryka domyslnego providera NMT — jedno miejsce polskich domyslow.

    Egzekwuje regule "5m => EVRF2007" (identycznie jak DownloadManager).
    """
    if resolution == "5m" and vertical_crs != "EVRF2007":
        logger.warning(
            f"Resolution 5m only supports EVRF2007, changing "
            f"vertical_crs from '{vertical_crs}' to 'EVRF2007'"
        )
        vertical_crs = "EVRF2007"
    return GugikProvider(
        session=session,
        vertical_crs=vertical_crs,
        resolution=resolution,
        cache=cache,
    )
```

(dopisz `create_nmt_provider` do `__all__`).

- [ ] **Krok 11.4: Przepnij `DownloadManager.__init__`**

manager.py:21: `from kartograf.providers.pl.gugik import GugikProvider` -> `from kartograf.providers.pl import create_nmt_provider` (sprawdz grepem, ze `GugikProvider` nie jest uzywany nigdzie indziej w tym module; adnotacje typow zostaja na `BaseProvider`). manager.py:179-181:

```python
        self._provider = provider or create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution
        )
```

Linie 171-177 (wymuszenie 5m⇒EVRF2007) ZOSTAJA verbatim.

- [ ] **Krok 11.5: Przepnij CLI `_create_provider_and_storage` (galaz else/nmt)**

```python
    else:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution
        )
        storage = FileStorage(output_dir, resolution=resolution)
```

(usun z naglowka funkcji nieuzywany juz import `from kartograf.providers.pl.gugik import GugikProvider`).

- [ ] **Krok 11.6: Pelny pytest**

```bash
.venv/bin/python -m pytest tests/ -q
```

Testy `test_cli.py:723-756` (isinstance po typach providerow) przechodza — fabryka zwraca te same klasy.

- [ ] **Krok 11.7: Commit**

```bash
git add -A
git commit -m "feat(providers): fabryka create_nmt_provider; DownloadManager i CLI korzystaja z niej"
```

---

### Zadanie 12: Sidecar w managerach i CLI LAZ + `descriptor_key` w providerach

**Files:**
- Modify: `kartograf/providers/pl/{gugik,gugik_nmpt,gugik_orto,gugik_laz,bdot10k}.py` (jedna linia w `__init__` kazdego), `kartograf/providers/{corine,soilgrids}.py` (jw.), `kartograf/download/manager.py` (helper + 4 punkty), `kartograf/landcover/manager.py` (helper + 6 punktow), `kartograf/cli/commands.py` (`_write_laz_sidecar` + wpiecie w `_cmd_download_laz`)
- Test: addytywne bloki w `tests/test_download_manager.py`, `tests/test_landcover.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `get_source`, `build_metadata`, `write_sidecar` (Zadania 2-3); `descriptor_key` z `DataSourceProvider` (Zadanie 9).
- Produces: po kazdym UDANYM pobraniu plik `<nazwa>.meta.json` obok wyniku. Skip-existing NIE tworzy sidecara. Blad sidecara -> `logger.warning`, pobranie zwraca wynik normalnie. Mocki bez `descriptor_key: str` sa cicho pomijane (guard `isinstance(key, str)`) — dotychczasowe testy nie widza zadnej roznicy.

Weryfikacja ryzyka "sidecar psuje test asertujacy zawartosc katalogu" (spec sekcja 11): grep `iterdir|listdir|glob` w tests/ dal 3 trafienia, wszystkie w `test_storage.py:354,359,542` — zadne nie liczy plikow w katalogu-lisciu danych (liczba podkatalogow poziom wyzej / filtr `*.asc`), a testy storage nie przechodza przez managera, wiec sidecar tam w ogole nie powstaje. Zero korekt oczekiwan.

- [ ] **Krok 12.1: `descriptor_key` w providerach (na koncu kazdego `__init__`)**

```python
# pl/gugik.py (__init__, po ustawieniu self._resolution):
        self.descriptor_key = f"pl.gugik.nmt_{resolution}"
# pl/gugik_nmpt.py (__init__, PO super().__init__(...)):
        self.descriptor_key = "pl.gugik.nmpt"
# pl/gugik_orto.py:  self.descriptor_key = "pl.gugik.orto"
# pl/gugik_laz.py:   self.descriptor_key = "pl.gugik.laz"
# pl/bdot10k.py:     self.descriptor_key = "pl.gugik.bdot10k"
# corine.py:         self.descriptor_key = "eu.clms.corine"
# soilgrids.py:      self.descriptor_key = "global.isric.soilgrids"
```

Dopisz test spojnosci do `tests/test_sources_registry.py` (klasa `TestDescriptorProviderConsistency`):

```python
    def test_descriptor_keys_bound(self):
        from kartograf import (
            Bdot10kProvider, CorineProvider, GugikLazProvider,
            GugikNmptProvider, GugikOrtoProvider, GugikProvider,
            SoilGridsProvider,
        )

        expected = {
            GugikProvider(resolution="1m"): "pl.gugik.nmt_1m",
            GugikProvider(resolution="5m"): "pl.gugik.nmt_5m",
            GugikNmptProvider(): "pl.gugik.nmpt",
            GugikOrtoProvider(): "pl.gugik.orto",
            GugikLazProvider(): "pl.gugik.laz",
            Bdot10kProvider(): "pl.gugik.bdot10k",
            CorineProvider(use_proxy=False): "eu.clms.corine",
            SoilGridsProvider(): "global.isric.soilgrids",
        }
        for provider, key in expected.items():
            assert provider.descriptor_key == key
            get_source(key)  # klucz istnieje w rejestrze
```

- [ ] **Krok 12.2: Helper + wpiecia w `DownloadManager`**

Na koncu klasy DownloadManager:

```python
    def _write_sidecar(self, data_path: Path, request: dict) -> None:
        """Best-effort zapis sidecara .meta.json (blad nie przerywa pobrania)."""
        try:
            from kartograf.sources.registry import get_source
            from kartograf.sources.sidecar import build_metadata, write_sidecar

            key = getattr(self._provider, "descriptor_key", None)
            if not isinstance(key, str):
                return
            meta = build_metadata(
                get_source(key),
                request=request,
                vertical_crs=getattr(self._provider, "vertical_crs", None),
                data_path=data_path,
            )
            write_sidecar(data_path, meta)
        except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
            logger.warning(f"Nie udalo sie zapisac sidecara dla {data_path}: {e}")
```

Wpiecia (4 punkty sukcesu wg rekonesansu):
1. `download_sheet` — po `self._provider.download(godlo, target_path)` (manager.py:266), przed `return target_path`: `self._write_sidecar(target_path, {"godlo": godlo})`
2. `_download_single_sheet_task` — po `path = self._provider.download(...)` (manager.py:366), przed `return (..., "completed", "")`: `self._write_sidecar(path, {"godlo": descendant_godlo})`
3. `_download_hierarchy_sequential` — po `path = self._provider.download(...)` (manager.py:416): `self._write_sidecar(path, {"godlo": current_godlo})`
4. `download_bbox` (manager.py:596) — przechwycic wynik:

```python
        result = self._provider.download_bbox(bbox, output_path, format=format)
        self._write_sidecar(
            result,
            {"bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
             "bbox_crs": bbox.crs},
        )
        return result
```

Sciezki skip-existing (manager.py:260-262, :363-364, :390-402) — BEZ wpiec.

- [ ] **Krok 12.3: Helper + wpiecia w `LandCoverManager`**

Ten sam helper `_write_sidecar` (identyczna tresc, `vertical_crs` bedzie None dla wszystkich zrodel landcover — descriptor nie ma opcji pionowych). Wpiecia — 6 punktow (rekonesans: `download_by_*` NIE deleguja do `download()`):

```python
# download() — dispatch (manager.py:197-202): kazda galaz przechwytuje wynik, np.:
        if teryt is not None:
            path = self._provider.download_by_teryt(teryt, output_path, **kwargs)
            self._write_sidecar(path, {"teryt": teryt})
            return path
        elif bbox is not None:
            path = self._provider.download_by_bbox(bbox, output_path, **kwargs)
            self._write_sidecar(
                path,
                {"bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                 "bbox_crs": bbox.crs},
            )
            return path
        else:
            path = self._provider.download_by_godlo(godlo, output_path, **kwargs)
            self._write_sidecar(path, {"godlo": godlo})
            return path
# download_by_teryt (:229), download_by_bbox (:261), download_by_godlo (:288):
# analogiczne przechwycenie zamiast bezposredniego return.
```

WAZNE: manager NADAL wola `provider.download_by_teryt` (nie `download_by_admin_unit`) — asertuja to mocki w test_landcover.py:857,937.

- [ ] **Krok 12.4: Sidecar w przeplywie LAZ (`cli/commands.py`)**

Przed `_cmd_download_laz` dodaj:

```python
def _write_laz_sidecar(provider, tile, target: Path, bbox: BBox) -> None:
    """Best-effort sidecar dla kafla LAZ (blad nie przerywa pobrania)."""
    import logging

    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        meta = build_metadata(
            get_source("pl.gugik.laz"),
            request={
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
            vertical_crs=provider.vertical_crs,
            extra={
                "godlo_kafla": tile.godlo,
                "rok": tile.year,
                "gestosc": tile.density,
                "url": tile.url,
            },
        )
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logging.getLogger(__name__).warning(
            f"Nie udalo sie zapisac sidecara dla {target}: {e}"
        )
```

W `_cmd_download_laz._fetch` po `provider.download(tile.url, target)`:

```python
            provider.download(tile.url, target)
            _write_laz_sidecar(provider, tile, target, bbox)
            return "ok", target, None
```

(w istniejacych testach CLI LAZ provider jest Mockiem — `provider.vertical_crs` to Mock, `vertical_crs_code` rzuci KeyError, helper zlapie i zaloguje warning; asercje testow bez zmian).

- [ ] **Krok 12.5: Addytywne testy sidecara**

Do `tests/test_download_manager.py`:

```python
class TestSidecarWritten:
    def _mock_provider(self):
        from unittest.mock import MagicMock

        provider = MagicMock()
        provider.default_extension = ".asc"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.vertical_crs = "EVRF2007"

        def fake_download(godlo, target, timeout=30):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\n"
                "cellsize 1\nNODATA_value -9999\n1 2\n3 4\n"
            )
            return target

        provider.download.side_effect = fake_download
        return provider

    def test_download_sheet_writes_sidecar(self, tmp_path):
        import json

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        result = manager.download_sheet("N-34-130-D-d-2-4")
        sidecar = result.parent / f"{result.name}.meta.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.nmt_1m"
        assert payload["vertical_crs"] == "EPSG:9651"
        assert payload["nodata"] == -9999.0
        assert payload["request"] == {"godlo": "N-34-130-D-d-2-4"}

    def test_skip_existing_writes_no_sidecar(self, tmp_path):
        provider = self._mock_provider()
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        sidecar = result.parent / f"{result.name}.meta.json"
        sidecar.unlink()
        manager.download_sheet("N-34-130-D-d-2-4")  # skip_existing=True
        assert not sidecar.exists()

    def test_sidecar_failure_does_not_break_download(self, tmp_path):
        from unittest.mock import patch

        manager = DownloadManager(output_dir=tmp_path, provider=self._mock_provider())
        with patch(
            "kartograf.sources.sidecar.write_sidecar",
            side_effect=OSError("dysk pelny"),
        ):
            result = manager.download_sheet("N-34-130-D-d-2-4")
        assert result.exists()

    def test_mock_provider_without_key_is_skipped(self, tmp_path):
        provider = self._mock_provider()
        del provider.descriptor_key  # atrybut Mock zamiast str -> guard pomija
        provider.descriptor_key = object()
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        result = manager.download_sheet("N-34-130-D-d-2-4")
        assert not (result.parent / f"{result.name}.meta.json").exists()
```

Do `tests/test_landcover.py`:

```python
class TestSidecarLandCover:
    def test_download_by_teryt_writes_sidecar(self, tmp_path):
        mock_provider = Mock()
        mock_provider.name = "BDOT10k"
        mock_provider.descriptor_key = "pl.gugik.bdot10k"
        out = tmp_path / "out.gpkg"

        def fake(teryt, output_path, **kwargs):
            out.write_bytes(b"GPKG")
            return out

        mock_provider.download_by_teryt.side_effect = fake
        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        result = manager.download_by_teryt("1465", output_path=out)
        sidecar = result.parent / f"{result.name}.meta.json"
        assert sidecar.exists()
        import json

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.bdot10k"
        assert payload["request"] == {"teryt": "1465"}
        assert payload["vertical_crs"] is None
```

Do `tests/test_cli.py` (obok istniejacych testow LAZ, w ich stylu — patch klasy `kartograf.providers.pl.gugik_laz.GugikLazProvider`, skonfiguruj instancje: `vertical_crs="EVRF2007"`, `discover_tiles` zwraca 1 `LazTile`, `download` side_effect tworzy plik) — asercja: obok pliku kafla powstaje `<nazwa>.laz.meta.json` z `extra.godlo_kafla`.

- [ ] **Krok 12.6: Pelny pytest + ruff**

```bash
.venv/bin/python -m pytest tests/ -q && .venv/bin/python -m ruff check kartograf/ tests/
```

- [ ] **Krok 12.7: Commit**

```bash
git add -A
git commit -m "feat(sidecar): .meta.json po kazdym udanym pobraniu (managery + CLI LAZ); descriptor_key w providerach"
```

---

### Zadanie 13: Podzial `cli/commands.py` (1600 linii) na moduly + fasada

**Files:**
- Create: `kartograf/cli/_parser.py`, `parse_cmd.py`, `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`, `cache_cmd.py`
- Modify: `kartograf/cli/commands.py` (zostaje fasada + `main`), `kartograf/cli/__init__.py` bez zmian, `pyproject.toml` bez zmian (entry point `kartograf.cli.commands:main` dalej dziala)
- Modify (testy — mechaniczne patch-targety, patrz "Decyzje planu" pkt 2): `tests/test_cli.py`, `tests/test_parallel_download.py`

Funkcje przenosza sie **bez zmian tresci** (wraz z sidecarowym `_write_laz_sidecar` z Zadania 12). Mapa podzialu (zakresy linii wg stanu sprzed Zadania 12 — po Zadaniu 12 przeniesc razem z dopisanym kodem):

| Modul | Funkcje (kolejnosc jak w commands.py) |
|---|---|
| `_parser.py` | `create_parser` (18-381) |
| `parse_cmd.py` | `format_sheet_info`, `format_hierarchy`, `format_children`, `format_descendants`, `cmd_parse` (384-557) |
| `download_cmd.py` | `create_progress_callback`, `_create_provider_and_storage`, `cmd_download`, `_download_godlo_list`, `_cmd_download_bbox`, `_resolve_laz_bbox`, `_write_laz_sidecar`, `_cmd_download_laz`, `_cmd_download_geometry` (560-1146) |
| `landcover_cmd.py` | `cmd_landcover`, `cmd_landcover_list_sources`, `cmd_landcover_list_layers`, `cmd_landcover_download` (1149-1340) |
| `soilgrids_cmd.py` | `cmd_soilgrids`, `cmd_soilgrids_hsg` (1343-1501) |
| `cache_cmd.py` | `cmd_cache` (1504-1555) |
| `commands.py` (fasada) | `main` (1558-1596) + re-eksporty |

- [ ] **Krok 13.1: Zbierz kotwice testowe (przed podzialem — mitygacja z sekcji 11 specu)**

```bash
grep -rn "from kartograf.cli.commands import" tests/
grep -rn "kartograf\.cli\.commands\." tests/
```

Oczekiwane (stan z rekonesansu): importy nazw `create_parser, create_progress_callback, format_children, format_descendants, format_hierarchy, format_sheet_info, main, _create_provider_and_storage, _resolve_laz_bbox` oraz patche `DownloadManager, LandCoverManager, _create_provider_and_storage, find_sheets_for_bbox`. Kazda importowana nazwa MUSI byc re-eksportowana w fasadzie; kazdy patch-target MUSI zostac przepisany na modul docelowy (krok 13.5).

- [ ] **Krok 13.2: Utworz submoduly**

Kazdy submodul: naglowek docstring + WLASNE importy modulowe (skopiuj z dzisiejszego naglowka commands.py:8-15 tylko to, czego dany modul uzywa; importy lokalne wewnatrz funkcji zostaja jak sa). Konkretnie:

```python
# _parser.py — importy: argparse
# parse_cmd.py — importy: argparse, sys; from kartograf.core.sheet_parser import SheetParser;
#   from kartograf.exceptions import ParseError, ValidationError
# download_cmd.py — importy: argparse, sys; from pathlib import Path;
#   from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox;
#   from kartograf.download.manager import DownloadManager, DownloadProgress;
#   from kartograf.exceptions import DownloadError, ParseError, ValidationError
# landcover_cmd.py — importy: argparse, sys; from pathlib import Path;
#   from kartograf.core.sheet_parser import BBox, SheetParser;
#   from kartograf.exceptions import DownloadError, ParseError, ValidationError;
#   from kartograf.landcover.manager import LandCoverManager
# soilgrids_cmd.py — importy: argparse, sys; from pathlib import Path;
#   from kartograf.core.sheet_parser import BBox, SheetParser;
#   from kartograf.exceptions import DownloadError, ParseError, ValidationError
# cache_cmd.py — importy: argparse, sys
```

Po przeniesieniu uruchom `ruff check kartograf/cli/` — F821 (undefined name) wskaze brakujacy import, F401 zbedny; dopasuj do faktycznych potrzeb funkcji (to jest weryfikowalna metoda, nie zgadywanie).

- [ ] **Krok 13.3: Fasada `commands.py`**

```python
"""
CLI commands for Kartograf — fasada zgodnosci.

Implementacje zyja w modulach _parser/parse_cmd/download_cmd/landcover_cmd/
soilgrids_cmd/cache_cmd; ten modul re-eksportuje publiczne nazwy i helpery
uzywane przez testy oraz utrzymuje entry point `main`
(pyproject: kartograf = "kartograf.cli.commands:main").
"""

import sys

from kartograf.cli._parser import create_parser
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.download_cmd import (
    _cmd_download_bbox,
    _cmd_download_geometry,
    _cmd_download_laz,
    _create_provider_and_storage,
    _download_godlo_list,
    _resolve_laz_bbox,
    _write_laz_sidecar,
    cmd_download,
    create_progress_callback,
)
from kartograf.cli.landcover_cmd import (
    cmd_landcover,
    cmd_landcover_download,
    cmd_landcover_list_layers,
    cmd_landcover_list_sources,
)
from kartograf.cli.parse_cmd import (
    cmd_parse,
    format_children,
    format_descendants,
    format_hierarchy,
    format_sheet_info,
)
from kartograf.cli.soilgrids_cmd import cmd_soilgrids, cmd_soilgrids_hsg

__all__ = [
    "create_parser",
    "main",
    "cmd_parse",
    "cmd_download",
    "cmd_landcover",
    "cmd_landcover_download",
    "cmd_landcover_list_layers",
    "cmd_landcover_list_sources",
    "cmd_soilgrids",
    "cmd_soilgrids_hsg",
    "cmd_cache",
    "create_progress_callback",
    "format_sheet_info",
    "format_hierarchy",
    "format_children",
    "format_descendants",
    "_create_provider_and_storage",
    "_download_godlo_list",
    "_cmd_download_bbox",
    "_cmd_download_laz",
    "_cmd_download_geometry",
    "_resolve_laz_bbox",
    "_write_laz_sidecar",
]


def main(args: list[str] | None = None) -> int:
    # DOKLADNIE dzisiejsza tresc main() (commands.py:1558-1596) — bez zmian.
    ...


if __name__ == "__main__":
    sys.exit(main())
```

(Tresc `main` przenies verbatim — dispatch if-chain po `args.command`; zadnych `set_defaults` w projekcie nie ma.)

- [ ] **Krok 13.4: Skasuj przeniesione funkcje z commands.py**

Po podziale `wc -l kartograf/cli/commands.py` powinno byc ~120 linii (fasada + main).

- [ ] **Krok 13.5: Mechaniczna aktualizacja patch-targetow w testach**

```bash
sed -i \
  -e 's/kartograf\.cli\.commands\.DownloadManager/kartograf.cli.download_cmd.DownloadManager/g' \
  -e 's/kartograf\.cli\.commands\._create_provider_and_storage/kartograf.cli.download_cmd._create_provider_and_storage/g' \
  -e 's/kartograf\.cli\.commands\.find_sheets_for_bbox/kartograf.cli.download_cmd.find_sheets_for_bbox/g' \
  -e 's/kartograf\.cli\.commands\.LandCoverManager/kartograf.cli.landcover_cmd.LandCoverManager/g' \
  tests/test_cli.py tests/test_parallel_download.py
grep -rn "patch(\"kartograf\.cli\.commands\." tests/   # oczekiwane: 0 trafien
```

Pokrycie listy (rekonesans): `DownloadManager` — test_cli.py:416,430,455,471,486,512,566,598,630,652,685,759,781,858,882,1224,1247,1668,1699,1732,1764 + test_parallel_download.py:472; `_create_provider_and_storage` — test_cli.py:565,597,629,651,684 + test_parallel_download.py:471; `LandCoverManager` — test_cli.py:955,969,985,1008,1034,1349; `find_sheets_for_bbox` — test_cli.py:1667,1698. IMPORTY testowe (`from kartograf.cli.commands import ...`) ZOSTAJA bez zmian — obsluguje je fasada. Nowy test sidecara LAZ z Zadania 12.5 patchuje juz `kartograf.providers.pl.gugik_laz.GugikLazProvider` — bez zmian.

- [ ] **Krok 13.6: Pelny pytest + ruff + smoke CLI**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m ruff check kartograf/ tests/ && .venv/bin/python -m ruff format --check kartograf/ tests/
.venv/bin/kartograf --help >/dev/null && .venv/bin/kartograf parse N-34-130-D-d-2-4
```

- [ ] **Krok 13.7: Commit**

```bash
git add -A
git commit -m "refactor(cli): podzial commands.py na moduly per komenda + fasada zgodnosci"
```

---

### Zadanie 14: Dokumentacja — ADR-022, CHANGELOG (BREAKING), CLAUDE.md, PROGRESS, SCOPE

**Files:**
- Modify: `docs/DECISIONS.md`, `docs/CHANGELOG.md`, `CLAUDE.md`, `docs/PROGRESS.md`, `docs/SCOPE.md`, `docs/IMPLEMENTATION_PROMPT.md`

- [ ] **Krok 14.1: ADR-022 w `docs/DECISIONS.md`** (format jak ADR-021; wstaw przed szablonem HTML na koncu)

```markdown
## ADR-022: Architektura zrodel wielokrajowych — deskryptory, rejestry, sidecar, twarda polityka transformacji (etap 0)

**Data:** 2026-08-10
**Status:** Przyjeta

**Kontekst:** Decyzja kierunkowa: rozszerzenie o Czechy (pelna parytetowosc produktowa), potem Niemcy i Slowacje (analizy transgraniczne). Research 3 krajow (docs/research/2026-08-10-*) dal 4 realne przypadki do zaprojektowania granic abstrakcji i wykazal pulapki: DE = federacja 17 modeli; SK WCS zwraca wysokosci elipsoidalne (42,3 m odchylki od Bpv); PROJ przy braku sieci cicho zwraca identycznosc (ballpark); siatki transformacyjne obcych krajow zwracaja inf poza swoim obszarem; CZ wypelnia obszar poza granica zerami (bez metadanych 0 m udaje poziom morza). Spec: docs/superpowers/specs/2026-08-10-etap0-zrodla-wielokrajowe-design.md.

**Opcje:**
- A) Dodawac kraje przez rozbudowe istniejacych klas GUGiK-centrycznych
- B) Etap 0: zrodla opisane deklaratywnie (deskryptory jako dane), sidecar metadanych, twarda polityka transformacji, wspolny transport; providery per kraj w providers/<cc>/
- C) Pelna ekstrakcja silnikow transportu (WMS-skorowidz/WCS) juz teraz

**Decyzja:** Opcja B. `sources/` (SourceDescriptor/AccessChannel/rejestr; zero IO), `sources/sidecar.py` (ResultMetadata + `<plik>.meta.json` po kazdym udanym pobraniu — kontrakt dla Hydrografa, ktory scala dane transgraniczne), `transform/crs.py` (TransformerGroup z allow_ballpark=False; odrzucanie operacji o nieznanej dokladnosci — w pyproj accuracy=-1, 0.0 oznacza operacje dokladna i JEST akceptowane; probe na punkcie kontrolnym odrzuca siatki obcych krajow zwracajace inf; isfinite na kazdym wyniku), `transport/http.py` + `transport/mosaic.py`, `core/parser_registry.py`, unifikacja ABC (DataSourceProvider; download_by_admin_unit z aliasami teryt), przenosiny providers/pl/ BEZ shimow (decyzja uzytkownika: Hydrograf/Hydrolog dostosuja importy; stabilna powierzchnia = `from kartograf import ...`). Opcja C odrzucona: jedynym konsumentem WMS-skorowidzow jest GUGiK, ekstrakcja teraz to ryzyko dla ~1060 testow bez zysku; formalny interfejs silnika powstanie w etapie 1 przy CuzkClient.

**Konsekwencje:** Zachowanie identyczne (inwariant ~1060 testow bez zmiany asercji); jedyna zmiana obserwowalna to sidecary `.meta.json`. BREAKING dla glebokich importow (tabela w CHANGELOG). Etap 1 (CZ DMR) buduje na fabryce providerow pl/, deskryptorach i polityce transformacji.
```

- [ ] **Krok 14.2: CHANGELOG — sekcja `## [Unreleased]`, NA GORZE dodaj (przed wpisami LAZ):**

```markdown
### Added
- **Etap 0 — architektura zrodel wielokrajowych (przygotowanie pod CZ/DE/SK)**
  - `kartograf/sources/` — deskryptory zrodel (SourceDescriptor, AccessChannel,
    TransportKind, LicenseInfo, CountryProfile) + rejestr (`get_source`,
    `sources_for`, `get_country`, `vertical_crs_code`); zero IO przy imporcie
  - **Sidecar metadanych**: po kazdym udanym pobraniu powstaje
    `<plik>.meta.json` (schema `kartograf-meta/1`: dataset, CRS-y, nodata,
    licencja, request, wersja) — kontrakt dla Hydrografa; blad zapisu sidecara
    nie przerywa pobrania
  - `kartograf/transform/crs.py` — twarda polityka transformacji:
    `TransformerGroup(allow_ballpark=False)`, filtr dokladnosci, probe
    odrzucajacy siatki obcych krajow (inf), kontrola isfinite,
    `TransformError`/`TransformUnavailableError` z remedium; `KNOWN_PATHS`
  - `kartograf/transport/` — `download_to()` (atomic write + retry) i
    `mosaic_and_crop()` (rasterio.merge + przyciecie, propagacja nodata)
  - `kartograf/core/parser_registry.py` — rejestr systemow godel (pl1992,
    pl2000); `SheetParser` i `FileStorage` deleguja do rejestru (wyniki
    identyczne)
  - `providers/pl/__init__.py`: fabryka `create_nmt_provider()` — jedno
    miejsce polskich domyslow NMT (w tym regula 5m => EVRF2007)
  - `FileStorage(subdir=...)` — opcjonalny podkatalog sterowany deskryptorem
  - `LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`
    (kanoniczne) + `download_by_teryt`/`validate_teryt`/`source_url` jako
    dzialajace aliasy zgodnosciowe
  - CLI podzielone na moduly (`cli/_parser.py`, `parse_cmd.py`,
    `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`,
    `cache_cmd.py`); `cli/commands.py` zostaje fasada zgodnosci (entry point
    bez zmian)

### Changed
- **BREAKING: glebokie sciezki importu providerow** (bez shimow — decyzja
  z review specu; publiczne API `from kartograf import ...` BEZ zmian):

  | Stary import | Nowy import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.gugik_laz` | `kartograf.providers.pl.gugik_laz` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |
```

- [ ] **Krok 14.3: CLAUDE.md — sekcja "Struktura modulow"**

Zaktualizuj drzewo o: `sources/` (descriptor, registry, sidecar), `transport/` (http, mosaic), `transform/` (crs), `core/parser_registry.py`, `providers/pl/` (5 modulow + fabryka), podzial `cli/` (7 modulow), adnotacje "landcover_base.py USUNIETY". W sekcji "Ograniczenia" dopisz: "Kazde udane pobranie tworzy sidecar `<plik>.meta.json` (metadane CRS/licencja/nodata)".

- [ ] **Krok 14.4: PROGRESS.md**

Tabela statusu: dodaj wiersz "Etap 0 — zrodla wielokrajowe (sources/transform/transport/providers-pl/CLI split/sidecar) | Gotowy | galaz feature/etap0-zrodla-wielokrajowe". Sekcja "Ostatnia sesja": co zrobiono (lista zadan 0-15), stan testow (liczba, pokrycie), nastepny krok: **spec + plan etapu 1 (fundament CZ + DMR)**, decyzja o merge do develop po review.

- [ ] **Krok 14.5: SCOPE.md i IMPLEMENTATION_PROMPT.md**

Zaktualizuj diagramy struktury (linie z `landcover_base.py`: SCOPE.md:251, IMPLEMENTATION_PROMPT.md:66,218) i sciezki providerow na `providers/pl/*`.

- [ ] **Krok 14.6: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: ADR-022, CHANGELOG (BREAKING importy), CLAUDE/PROGRESS/SCOPE po etapie 0"
```

---

### Zadanie 15: Weryfikacja koncowa (kryteria akceptacji ze specu, sekcja 12)

- [ ] **Krok 15.1: Pelny pytest + pokrycie**

```bash
.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=term | tail -20
```

Oczekiwane: wszystkie testy zielone (1060 dotychczasowych + nowe z zadan 1-13, ~1130+); TOTAL coverage >= 80%.

- [ ] **Krok 15.2: Lint + format + mypy**

```bash
.venv/bin/python -m ruff check kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/
.venv/bin/python -m mypy kartograf/ > /tmp/mypy-after.txt; tail -1 /tmp/mypy-after.txt
diff <(grep -o "error:.*" /tmp/mypy-baseline.txt | sort) <(grep -o "error:.*" /tmp/mypy-after.txt | sort) || true
```

Kryterium: ruff czysty; mypy — zero NOWYCH bledow wzgledem baseline z Zadania 0, nowe moduly (`sources/`, `transport/`, `transform/`, `parser_registry`) bez bledow.

- [ ] **Krok 15.3: Smoke E2E CLI (kryterium 3)**

```bash
.venv/bin/kartograf --help >/dev/null
.venv/bin/kartograf parse N-34-130-D-d-2-4
.venv/bin/kartograf cache path
# Przy dostepie do sieci (opcjonalnie, wymaga GUGiK online):
.venv/bin/kartograf download N-34-130-D-d-2-4 --output /tmp/kartograf-e2e
ls /tmp/kartograf-e2e/nmt_1m/N-34/130/D/d/2/4/
# Oczekiwane: N-34-130-D-d-2-4.asc + N-34-130-D-d-2-4.asc.meta.json
cat /tmp/kartograf-e2e/nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc.meta.json
```

Bez sieci: kryterium 3 pokrywaja testy `TestSidecarWritten` (Zadanie 12) — odnotuj to w PROGRESS.

- [ ] **Krok 15.4: Checklist kontraktow (spec sekcja 10)**

```bash
.venv/bin/python - <<'EOF'
# Kontrakty zgodnosci wstecznej po etapie 0
from kartograf import (  # publiczne API — bez zmian
    BaseProvider, Bdot10kProvider, CorineProvider, DownloadManager,
    FileStorage, GugikLazProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikProvider, LandCoverManager, LandCoverProvider, LazTile,
    MetadataCache, SheetParser, SoilGridsProvider,
)
p = Bdot10kProvider()
assert p.source_url == p.base_url            # alias dziala
assert p.validate_teryt("1465")              # alias dziala
try:
    import kartograf.providers.gugik  # noqa: F401
    raise SystemExit("BLAD: stara sciezka nie powinna istniec")
except ModuleNotFoundError:
    pass
try:
    import kartograf.providers.landcover_base  # noqa: F401
    raise SystemExit("BLAD: landcover_base nie powinien istniec")
except ModuleNotFoundError:
    pass
import kartograf.providers.pl.gugik  # nowa sciezka istnieje  # noqa: F401
print("Kontrakty sekcji 10: OK")
EOF
```

- [ ] **Krok 15.5: Aktualizacja PROGRESS.md o wynik weryfikacji + commit koncowy**

```bash
git add docs/PROGRESS.md
git commit -m "docs(progress): etap 0 zweryfikowany — testy/pokrycie/lint/kontrakty"
git log --oneline develop..HEAD   # przeglad calej galezi przed review
```

---

## Self-review (wykonany przy pisaniu planu)

1. **Pokrycie specu:** sekcja 4 pkt 1→Zad.1-2, pkt 2→Zad.3+12, pkt 3→Zad.4, pkt 4→Zad.5-6, pkt 5→Zad.7, pkt 6→Zad.9, pkt 7→Zad.10-11, pkt 8→Zad.8, pkt 9→Zad.13, pkt 10→Zad.14. Testy 6.12: registry→Zad.2, transform→Zad.4, mosaic→Zad.6, http→Zad.5, sidecar→Zad.3, parser_registry→Zad.7, "sidecar powstaje" w managerach→Zad.12. Kryteria sekcji 12→Zad.15.
2. **Odstepstwa od litery specu** (swiadome, uzasadnione w "Decyzjach planu"): filtr `accuracy < 0` zamiast `<= 0`; patch-targety CLI; mypy wzgledem baseline; regula 5m zostaje TAKZE w managerze; wersja pakietu bez podbicia.
3. **Spojnosc typow:** `descriptor_key` ustawiany jako atrybut instancji (str) vs deklaracja klasowa `str | None` — zgodne; `BBox(min_x, min_y, max_x, max_y, crs)` potwierdzone z kodu; `download_sheet -> Path | list[Path]` obsluzone w istniejacym CLI bez zmian; `_write_sidecar` w obu managerach ma identyczna sygnature `(data_path: Path, request: dict) -> None`.
4. **Kolejnosc zadan:** nowe moduly (1-8) przed przenosinami (10) — test spojnosci z Zad.2 importuje przez `kartograf` (stabilne); ABC (9) przed przenosinami (10), zeby diff przenosin byl czysty (`git mv` + sed importow); sidecar (12) po fabryce (11), bo dotyka tych samych plikow managera; CLI split (13) na koncu zmian kodu, zeby przenosic juz ostateczna tresc funkcji.

## Uruchomienie planu

Wykonawca: kazde zadanie = osobna sesja/subagent z pelnym pytest przed commitem. Przy rozjazdach miedzy planem a kodem (np. przesuniete numery linii po wczesniejszych zadaniach) obowiazuje regula: **tresc i kontrakty z planu, kotwice szukaj po nazwach funkcji, nie po numerach linii**. Numery linii w planie odnosza sie do stanu na commit `5b6dd2b` (develop, 2026-08-10).
