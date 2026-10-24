# Kartograf

Kartograf pobiera dane przestrzenne z publicznych usług GUGiK (Polska), CUZK
(Czechy), Copernicus i ISRIC i zapisuje je w uporządkowanym katalogu `data/`
razem z metadanymi każdego pliku. Obszar wybierasz godłem arkusza, bboxem,
plikiem geometrii, kodem jednostki (TERYT) albo całym krajem. Działa jako
narzędzie wiersza poleceń (`kartograf`), biblioteka Python i serwer MCP
(`kartograf-mcp`, dla agentów AI).

Jest częścią toolchainu hydrologicznego: **Hydrograf** używa go jako źródła
danych GIS (NMT, pokrycie terenu), **Hydrolog** opcjonalnie (grupy
hydrologiczne gleb, SoilGrids), a dane obserwacyjne dostarcza **IMGWTools**.
Kartograf nie wykonuje obliczeń hydrologicznych (poza klasyfikacją HSG).

## Obsługiwane dane

Komendy są pogrupowane wg typu danych (`kartograf <grupa> download`); dane
wybiera `--product` w każdej grupie (w `soil` — `--property`, `--depth`,
`--stat`). Źródła grupy i wartości wyboru wypisuje
`kartograf <grupa> list-sources`.

| Grupa | Dane (wartość `--product`) |
|---|---|
| `elevation` | NMT (`nmt`): PL — siatki GUGiK 0,15–10 m, archiwa GUGiK jako pliki źródłowe, NMT 100 m (pliki XYZ województw); CZ — DMR 5G/4G (2 m / 5 m). NMPT (`nmpt`): PL — 0,5 / 0,6 / 1 m; CZ — DMP OK 0,5 m, DMP 1G 2 m. Chmury punktów LIDAR (`laz`): PL (GUGiK) i CZ (`--model` `dmr5g`, `dmr4g`, `dmp1g`, `dmpok`). Warstwice ZABAGED (`contours`, CZ): arkusze SM5, SHP albo DGN. Raport dostępności bez pobierania: `elevation availability` |
| `imagery` | Ortofotomapa (`orto`): PL — arkusze GUGiK wg kampanii (np. 25 cm, 10 cm) albo wycinek WCS Standard/High; CZ — arkusze SM5 CUZK (JPEG z plikami JGW). PL: obrazy intensywności LIDAR (`intensity`), prawdziwa ortofotomapa wybranych miast (`true-orto`, arkusze i wycinek WCS), ortofotomapa ukośna (`oblique-orto`, cztery kierunki widoku) |
| `landcover` | BDOT10k (`bdot10k`; także archiwum roczników 2014–2025, GML/SHP), BDOO 1:250 000 (`bdoo`, PL), CORINE Land Cover (`corine`, Copernicus), ZABAGED (`zabaged`), Data50 i Data250 (`data50`, `data250`) — CZ |
| `soil` | SoilGrids (ISRIC; `soil download --property`), grupy hydrologiczne gleb HSG dla metody SCS-CN, liczone z SoilGrids (`soil hsg`) |
| `boundaries` | Granice jednostek (`admin`): PRG (PL), RUIAN (CZ). PL: punkty adresowe i ulice (`addresses`), 44 rodzaje granic specjalnych (`special`). CZ: jednostki geomorfologiczne (`geomorphology`) |
| `cadastre` | Mapa ewidencyjna (`map`): EGiB — działki i budynki (PL), mapa katastralna — SHP, DXF, DGN, VFK (CZ). Ceny nieruchomości RCN (`prices`, PL) |
| `models3d` | PL: budynki CityGML LoD1/LoD2 (`buildings`), drzewa CityGML LoD1 (`trees`), mesh miast OBJ z teksturami (`mesh`) |
| `hydro` | Sieć hydrograficzna HY-NET (`network`, CZ) |
| `names` | Nazwy geograficzne (`geographic`): PRNG (PL), Geonames (CZ); polskie nazwy geograficzne świata (`world`) |
| `maps` | Mapy topograficzne (`topographic`): wizualizacje BDOT10k (PL), ZTM (CZ); TIFF, PDF i formaty ZTM |
| `geodesy` | Osnowy geodezyjne (`control`): pozioma, wysokościowa, grawimetryczna i magnetyczna GUGiK (także archiwa), Bodove pole CUZK. Quasi-geoidy (`geoid`): PL-geoid2021, QGZU-2013 |

Poza grupami danych: `kartograf project` (projekt z przypiętymi wersjami,
niżej), `kartograf sheet parse` (godło arkusza), `kartograf cache`, `kartograf config`
(ustawienia, niżej) i `kartograf commands list` (katalog komend dla agentów AI, niżej).

## Instalacja

```bash
git clone https://github.com/Daldek/Kartograf.git
cd Kartograf
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Serwer MCP dla agentów AI to opcjonalny dodatek: `pip install -e ".[mcp]"`.

## Szybki start

### CLI

```bash
# Informacje o godle arkusza
kartograf sheet parse N-34-130-D-d-2-4

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
kartograf landcover download --product zabaged "--bbox=-460000,-1120000,-450000,-1110000" --bbox-crs EPSG:5514 -o ./data
kartograf boundaries download --product admin --country cz --level obec "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514 -o ./data
kartograf hydro download --product network --country cz --whole-country -o ./data

# NMT Czech
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data

# Pokrycie terenu i grupy hydrologiczne gleb
kartograf landcover download --product bdot10k --teryt 1465 -o ./data
kartograf soil hsg --sheet N-34-130-D --summary -o ./data --depth 0-5cm

# Granice, ewidencja, modele 3D budynków i archiwum BDOT10k (GUGiK)
kartograf boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000 -o ./data
kartograf cadastre download --product map --teryt 1261 -o ./data
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 -o ./data
kartograf landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP -o ./data

# Nazwy geograficzne i gotowe arkusze map (katalog danych poza repozytorium)
kartograf names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326 -o ~/kartograf-data
kartograf names download --product geographic --country cz --whole-country --format GPKG --horizontal-crs EPSG:5514 -o ~/kartograf-data
kartograf maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF -o ~/kartograf-data
kartograf maps download --product topographic --country cz --sheet NM-34-07-1-D-15 --scale 1:10000 --format PDF -o ~/kartograf-data

# Osnowy geodezyjne (punkty sieci obszaru) i model quasi-geoidy
kartograf geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000 -o ./data
kartograf geodesy download --product geoid --country pl --whole-country -o ./data
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
from kartograf import (
    BBox, DownloadManager, GugikProvider, calculate_hsg,
    download_data, download_landcover,
)

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

# Ten sam kontrakt dla landcover i HSG: files, failed, notices, ok
powiat = download_landcover(product="bdot10k", output_dir="./data", teryt="1465")
print([item.file.path for item in powiat.files], powiat.failed)
hsg = calculate_hsg(output_dir="./data", sheet="N-34-130-D", depth="0-5cm")
print([item.file.path for item in hsg.files], hsg.inputs, hsg.failed)

# Niższy poziom: arkusz NMT po godle przez DownloadManager
provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
manager = DownloadManager("./data", provider)
result = manager.download_sheet("N-34-130-D-d-2-4")
path = result.files["N-34-130-D-d-2-4"][0].version_path
```

## Dla agentów AI

To samo zadanie daje ten sam wynik w CLI, bibliotece i serwerze MCP:

- `--json` w każdej komendzie CLI: na stdout jeden dokument
  `kartograf-<rodzaj>/1`, błąd jako `kartograf-error/1` z `code`, `hint`
  i kodem wyjścia (0, 1, 2, 130, 143);
- `kartograf commands list --json` (`get_catalog()`): komendy, parametry, dozwolone
  wartości i przykłady;
- serwer MCP `kartograf-mcp` (`pip install "kartograf[mcp]"`, stdio; w Claude
  Code `claude mcp add kartograf -- kartograf-mcp`) z 29 narzędziami;
- [llms.txt](llms.txt): krótki spis dla agentów (zadania, polecenia, kody
  błędów).

Szczegóły: [docs/USAGE.md — Interfejs dla agentów](docs/USAGE.md#9-interfejs-dla-agentow).
Agenci z innych repozytoriów pracują nad kodem Kartografa według reguł z
[CLAUDE.md](CLAUDE.md).

## Gdzie trafiają dane

Pliki lądują w katalogu `--output` (niżej `data/`):
`data/<produkt>/<kraj>_<układ albo źródło>[_<wariant>]/...` (np.
`data/nmt/pl_1992_1m_evrf2007/`, `data/boundaries/pl_prg_gmina/bbox/`).
Każdy plik ma obok sidecar `<plik>.meta.json` z układem, licencją
i pochodzeniem danych; pobrana treść trafia jako wersja do `versions/`,
a ścieżka standardowa jest dowiązaniem do najnowszej lokalnej wersji — opis
w [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (sekcja 3).

## Settings, directories and backup

Settings come from the first of: the command-line option, the variable `KARTOGRAF_<KEY>`,
the shared variable `NOGAT_<KEY>` (only `data_dir`, `cache_dir` and `lang`), the table
`[kartograf]` and then `[nogat]` of `nogat.toml`, and the default (Nogat DEV-18).
`nogat.toml` is in the user configuration directory (`~/.config/nogat/nogat.toml` on
Linux) or at the path in `NOGAT_CONFIG`; Kartograf works without it, and refuses to run
with a file it cannot read (`validation_error`, reason `invalid_config`).
`kartograf config show [--json]` lists every setting with its value and source.
[.env.example](.env.example) has every variable; Kartograf does not read a `.env` file.

| Variable | Key in `nogat.toml` | Meaning | Default |
|---|---|---|---|
| `KARTOGRAF_ROOT` | `[kartograf] root` | root of the store (reported by `config show`; the commands still take the store from `--output`) | `<data_dir>/kartograf` |
| `KARTOGRAF_DATA_DIR`, `NOGAT_DATA_DIR` | `data_dir` | parent of the stores | user data directory of `nogat` (`~/.local/share/nogat`) |
| `KARTOGRAF_CACHE_DIR`, `NOGAT_CACHE_DIR` | `cache_dir` | parent of the caches; the metadata cache is `<cache_dir>/kartograf/metadata.db` | user cache directory of `nogat` (`~/.cache/nogat`) |
| `KARTOGRAF_LANG`, `NOGAT_LANG` | `lang` | language of human-readable output, `pl` or `en` (output is Polish until the message catalogue lands) | `pl` |
| `KARTOGRAF_DEBUG` | `[kartograf] debug` | print tracebacks and every library log record | off |
| `NOGAT_CONFIG` | - | path of `nogat.toml` | user configuration directory |
| `CLMS_CREDENTIALS` | never in the file | CLMS API credentials for CORINE as GeoTIFF ([docs/USAGE.md](docs/USAGE.md), section 6); `config show` says present or missing | - |

Kartograf never writes a cache or state into the current directory.

**Backup.** A store keeps hard links: the standard path and `full_sheet/` are hard links to
a file in `versions/`. Back it up with a copy that preserves them (`rsync -aH SOURCE/
TARGET/`); on Windows use a tool that keeps hard links, not Explorer or `robocopy`, or the
copy is two to three times larger. A source serves its current state, so a version that
the source has since replaced or withdrawn (a campaign GUGiK no longer lists, a national
file replaced in place) cannot be downloaded again: the store holds the only copy, and
that part is the one to protect first. The metadata cache is not data and needs no backup.

## Dokumentacja

| Plik | Zawartość |
|---|---|
| [USAGE.md](docs/USAGE.md) | Przewodnik użytkownika: CLI i biblioteka, wynik pobrania, kampanie, CLMS, znane problemy |
| [llms.txt](llms.txt) | Spis dla agentów AI (llmstxt.org): zadania, polecenia, kody błędów |
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
