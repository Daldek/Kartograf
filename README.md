# Kartograf

Kartograf pobiera dane przestrzenne z publicznych usług GUGiK (Polska), CUZK
(Czechy), Copernicus i ISRIC: wybierasz obszar (godło arkusza, bbox albo plik
geometrii), a Kartograf znajduje właściwe arkusze, pobiera je i zapisuje
w uporządkowanym katalogu `data/` razem z metadanymi każdego pliku. Działa
jako narzędzie wiersza poleceń (`kartograf`) i jako biblioteka Python.

Jest częścią toolchainu hydrologicznego: **Hydrograf** używa go jako źródła
danych GIS (NMT, pokrycie terenu), **Hydrolog** opcjonalnie (grupy
hydrologiczne gleb, SoilGrids), a dane obserwacyjne dostarcza **IMGWTools**.
Kartograf nie wykonuje obliczeń hydrologicznych (poza klasyfikacją HSG).

## Obsługiwane dane

- **NMT (PL)** — Numeryczny Model Terenu z GUGiK (1 m / 5 m)
- **NMT (CZ)** — DMR 5G/4G z CUZK (2 m / 5 m)
- **NMPT** — Numeryczny Model Pokrycia Terenu (DSM) z GUGiK
- **Ortofotomapa** — zdjęcia lotnicze GUGiK (25 cm)
- **LAZ** — chmury punktów LIDAR (ALS) z GUGiK
- **BDOT10k** — wektorowa baza obiektów topograficznych (pokrycie terenu, hydrografia)
- **CORINE Land Cover** — europejska klasyfikacja pokrycia terenu (Copernicus)
- **SoilGrids** — globalne dane glebowe (ISRIC)
- **HSG** — grupy hydrologiczne gleb dla metody SCS-CN, liczone z SoilGrids

## Instalacja

```bash
git clone https://github.com/Daldek/Kartograf.git
cd Kartograf
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Szybki start

### CLI

```bash
# Informacje o godle arkusza
kartograf parse N-34-130-D-d-2-4

# NMT dla arkusza, inne produkty GUGiK
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D-d-2-4 --product orto

# NMT dla obszaru: bbox (domyślnie EPSG:2180) albo plik SHP/GPKG
kartograf download --bbox 530000,382000,533000,386000 --country pl
kartograf download --geometry zlewnia.gpkg --layer catchments

# NMT Czech
kartograf download 302_5550 --country cz

# Pokrycie terenu i grupy hydrologiczne gleb
kartograf landcover download --source bdot10k --teryt 1465
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

Pełna lista opcji: `kartograf <komenda> --help`. Więcej przykładów, wybór
kraju (`--country`), scalony wycinek (`--target-crs`) i kampanie GUGiK:
[docs/USAGE.md](docs/USAGE.md).

### Biblioteka Python

```python
from kartograf import BBox, DownloadManager, download_pl_cutout

# Arkusz NMT po godle
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Obszar jako jeden GeoTIFF w zadanym układzie
result = download_pl_cutout(
    BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
    "EPSG:2180",
    output_dir="./data",
)
print(result.path)
```

## Gdzie trafiają dane

Pliki lądują w `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...`
(np. `data/nmt/pl_1992_1m_evrf2007/`), a każdy ma obok sidecar
`<plik>.meta.json` z układem, licencją i pochodzeniem danych — opis
w [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (sekcja 3).

## Dokumentacja

| Plik | Zawartość |
|---|---|
| [USAGE.md](docs/USAGE.md) | Przewodnik użytkownika: CLI i biblioteka, wynik pobrania, kampanie, CLMS, znane problemy |
| [SCOPE.md](docs/SCOPE.md) | Zakres projektu: co jest, czego nie ma, ograniczenia techniczne |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architektura, moduły, kontrakty danych, układ `data/`, przepływy per produkt |
| [PRD.md](docs/PRD.md) | Wymagania produktowe, publiczne API |
| [DECISIONS.md](docs/DECISIONS.md) | Rejestr decyzji architektonicznych (ADR) |
| [CHANGELOG.md](docs/CHANGELOG.md) | Historia zmian per wydanie |
| [PROGRESS.md](docs/PROGRESS.md) | Bieżący stan prac |
| [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) | Dla deweloperów: środowisko, testy, konwencje, workflow |

## Wymagania

Python 3.12+; zależności wymienia `pyproject.toml` (`dependencies`,
narzędzia deweloperskie w `[dev]`). CORINE jako GeoTIFF wymaga konta
Copernicus CLMS ([docs/USAGE.md](docs/USAGE.md), sekcja 6) — bez niego
pobierany jest podgląd PNG.

## Licencja

MIT — szczegóły w pliku `LICENSE`.

## Autor

[Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/)

## Status

Projekt w aktywnym rozwoju; wersję pakietu podaje `kartograf --version`.
Zmiany, także niewydane jeszcze zmiany kontraktów, opisuje
[docs/CHANGELOG.md](docs/CHANGELOG.md).
