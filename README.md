# Kartograf

Kartograf pobiera dane przestrzenne z publicznych usług GUGiK (Polska), CUZK
(Czechy), Copernicus i ISRIC: wybierasz obszar (godło arkusza, bbox albo plik
geometrii), a Kartograf pobiera arkusze albo wycinek WCS NMT/NMPT
i ortofotomapy PL (`--cutout --horizontal-crs`) — także granice, ewidencję
i modele 3D budynków GUGiK oraz dane wektorowe CUZK (ZABAGED, RUIAN, HY-NET)
— i zapisuje je w uporządkowanym katalogu `data/`
razem z metadanymi każdego pliku. Działa
jako narzędzie wiersza poleceń (`kartograf`) i jako biblioteka Python.

Jest częścią toolchainu hydrologicznego: **Hydrograf** używa go jako źródła
danych GIS (NMT, pokrycie terenu), **Hydrolog** opcjonalnie (grupy
hydrologiczne gleb, SoilGrids), a dane obserwacyjne dostarcza **IMGWTools**.
Kartograf nie wykonuje obliczeń hydrologicznych (poza klasyfikacją HSG).

## Obsługiwane dane

- **NMT (PL)** — Numeryczny Model Terenu z GUGiK: siatki 0,15–10 m (np. 0,5 m, 1 m, 5 m) i archiwa GUGiK jako pliki źródłowe
- **NMT (CZ)** — DMR 5G/4G z CUZK (2 m / 5 m)
- **NMPT** — Numeryczny Model Pokrycia Terenu (DSM) z GUGiK (0,5 m, 0,6 m, 1 m)
- **Ortofotomapa (PL)** — zdjęcia lotnicze GUGiK (rozdzielczość wg kampanii, np. 25 cm, 10 cm): arkusze albo wycinek WCS Standard/High z wyborem piksela
- **Ortofoto (CZ)** — arkusze SM5 CUZK (JPEG z plikami georeferencji JGW, aktualny rocznik)
- **LAZ** — chmury punktów LIDAR (ALS) z GUGiK
- **BDOT10k** — wektorowa baza obiektów topograficznych (pokrycie terenu, hydrografia)
- **Archiwum BDOT10k** — roczniki 2014-2025 (GML/SHP), oryginalna paczka powiatu
- **Granice administracyjne (PRG)** — granice jednostek administracyjnych i ewidencyjnych z GUGiK
- **EGiB** — mapa ewidencyjna z GUGiK (działki i budynki)
- **Modele 3D budynków** — CityGML LoD1/LoD2 z GUGiK
- **ZABAGED (CZ)** — 22 warstwy pokrycia terenu i wód CUZK (obszar) albo plik krajowy GPKG
- **Granice RUIAN (CZ)** — kraje, okresy, obce i katastralni uzemi z CUZK
- **HY-NET (CZ)** — sieć hydrograficzna CUZK (odcinki cieków i węzły; plik krajowy)
- **Nazwy geograficzne** — PRNG (Polska i polskie nazwy świata), Geonames CUZK: obiekty obszaru albo archiwum krajowe
- **Mapy topograficzne** — gotowe arkusze wizualizacji BDOT10k (PL) i ZTM (CZ), TIFF/PDF oraz formaty ZTM
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
kartograf elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data
kartograf elevation download --sheet M-34-64-D-d-2-1 --product nmpt --resolution 0.5m --vertical-crs EVRF2007 -o ./data
kartograf imagery download --sheet N-34-130-D-d-2-4 --product orto -o ./data
kartograf imagery download --sheet CTES96 --product orto -o ./data   # ortofoto CZ (SM5)

# Jakie lata, rozdzielczości i formaty mają komplet arkuszy dla obszaru (bez pobierania)
kartograf elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000

# NMT dla obszaru: bbox (domyślnie EPSG:2180) albo plik SHP/GPKG
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --geometry zlewnia.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data

# Jeden wycinek obszaru zamiast arkuszy (PL: WCS GUGiK 1 m, CZ: CUZK)
kartograf elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --vertical-crs EVRF2007 --cutout --horizontal-crs EPSG:2180 -o ./data
kartograf imagery download --bbox 566000,243000,566500,243500 --country pl --product orto --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m -o ./data

# Dane CZ (CUZK): ZABAGED, granice RUIAN, sieć wód HY-NET (współrzędne EPSG:5514 jako --bbox=...)
kartograf landcover download --source zabaged "--bbox=-460000,-1120000,-450000,-1110000" --bbox-crs EPSG:5514 -o ./data
kartograf boundaries download --product admin --country cz --level obec "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 -o ./data
kartograf hydro download --product network --country cz --whole-country -o ./data

# NMT Czech
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data

# Pokrycie terenu i grupy hydrologiczne gleb
kartograf landcover download --source bdot10k --teryt 1465 -o ./data
kartograf soil hsg --sheet N-34-130-D --stats -o ./data --depth 0-5cm

# Granice, ewidencja, modele 3D budynków i archiwum BDOT10k (GUGiK)
kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 -o ./data
kartograf cadastre download --product map --teryt 1261 -o ./data
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 -o ./data
kartograf landcover download --source bdot10k --teryt 1261 --year 2024 --format SHP -o ./data

# Nazwy i gotowe arkusze map: jawny katalog danych poza repozytorium
kartograf names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326 -o <katalog-danych>
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 -o <katalog-danych>
kartograf maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF -o <katalog-danych>
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF -o <katalog-danych>
```

Pełna lista opcji: `kartograf <grupa> <komenda> --help`. Więcej przykładów, wybór
kraju (`--country`), jeden wycinek (`--cutout --horizontal-crs`) i kampanie GUGiK:
[docs/USAGE.md](docs/USAGE.md).

### Projekt i przypięte wersje

```bash
mkdir -p ~/projekty/wisla
cd ~/projekty/wisla
kartograf project init --output ~/dane/kartograf
kartograf project add teren elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --year 2022
kartograf project download
kartograf project verify
```

Projekt zapisuje w `kartograf-project.json` zadania i sumy SHA-256
przypiętych wersji ze wspólnego magazynu; zwykłe `project download`
odtwarza brakujące wersje tylko przy identycznej treści. Więcej przykładów,
aktualizacje i przenoszenie magazynu:
[docs/USAGE.md — Projekt](docs/USAGE.md#8-projekt).

### Biblioteka Python

```python
from kartograf import BBox, DownloadManager, GugikProvider, download_data

# To samo co `kartograf elevation download ...` — te same pliki, sidecary, komunikaty
# i błędy (każdy wybór danych jawny; od 0.8.0 bez wartości domyślnych)
report = download_data(
    product="nmt",
    output_dir="./data",
    bbox=BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
    country="pl",
    cutout=True,                  # jeden wycinek WCS 1 m z maską lądu
    horizontal_crs="EPSG:2180",
    resolution="1m",
    vertical_crs="EVRF2007",
)
print([item.file.path for item in report.files], report.ok, report.notices)

# Niższy poziom: arkusz NMT po godle przez DownloadManager
provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager("./data", provider)
result = manager.download_sheet("N-34-130-D-d-2-4")
path = result.files["N-34-130-D-d-2-4"][0].version_path
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
