"""Declare ``kartograf imagery``.

GUGiK images - orthophotomap (sheets and WCS cutout), intensity images, true
orthophotomap (sheets and WCS cutout), oblique orthophotomap (PL) - and CUZK SM5
orthophoto sheets (CZ) (ADR-039, ADR-042 D13, D14, plan E1).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    OUTPUT_TITLE,
    PL_SHEETS,
    SELECTION_TITLE,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    IMAGERY_PRODUCTS,
    SCALE_2000_CHOICES,
    SCALES_2000,
    SHEET_SYSTEM_CHOICES,
    product_choices,
    product_directory,
    store_files,
)
from kartograf.download.orto_cutout import (
    ORTO_CUTOUT_CRS,
    cutout_resolution_choices,
    orto_coverage_choices,
)
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    image_directions,
    image_source,
    wcs_cutout_channels,
)
from kartograf.sources.descriptor import WcsCutoutParams
from kartograf.sources.variants import resolution_label, variants

# The sheet systems of the imagery commands: the PL ones and the CZ SM5 sheets
# of the orthophotomap.
_ACCEPTS = (*PL_SHEETS, "cz_sm5")
_CAMPAIGNS = (
    "Rok danych i loty (tylko PL: z --country cz blad, z auto dotyczy czesci PL)"
)


def _products() -> list[tuple[str, str]]:
    return shared.product_summaries(IMAGERY_PRODUCTS, product_choices)


def _directions() -> list[str]:
    """Return the view directions of the image products (the oblique orthophotomap)."""
    found = (d for product in IMAGERY_PRODUCTS for d in image_directions(product))
    return list(dict.fromkeys(found))


def _coverages() -> list[str]:
    """Return the WCS variants of the orthophotomap cutout (``standard``, ``high``)."""
    return [
        channel.params.variant
        for channel in wcs_cutout_channels(ORTO_KEY)
        if isinstance(channel.params, WcsCutoutParams)
    ]


def _cutout_resolutions() -> list[str]:
    """Return the pixels of every WCS cutout channel of the image products."""
    labels: list[str] = []
    for product in IMAGERY_PRODUCTS:
        source = image_source(product)
        channels = wcs_cutout_channels(source.key) if source is not None else ()
        for channel in channels:
            if isinstance(channel.params, WcsCutoutParams):
                labels += [resolution_label(v) for v in channel.params.resolutions]
    return list(dict.fromkeys(labels))


def _sheet_systems() -> list[str]:
    """Return the PL sheet systems the registry has variants for.

    They are the values of ``--sheet-system``.
    """
    found = variants(country="PL")
    return sorted({system for v in found for system in v.systems})


def _output_files() -> str:
    return store_files(product_directory(p) for p in IMAGERY_PRODUCTS)


def _sheet_system_help() -> str:
    return (
        "Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL (bez "
        f"--cutout): {SHEET_SYSTEM_CHOICES}. Produkt z jednym ukladem (true "
        "orto: 1992, orto ukosna: 2000) i wycinek --cutout (tylko 1992): mozna "
        "pominac. Z --sheet uklad wynika z godla (podana wartosc musi sie z nim "
        "zgadzac). Nie dotyczy CZ (arkusze SM5; z --country auto dotyczy "
        "czesci PL)"
    )


def _scale_help() -> str:
    return (
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali); orto ukosna ma arkusze "
        "1:2000 i 1:1000. PL-1992: niedozwolona - GUGiK publikuje arkusze "
        "PL-1992 w jednej skali (1:10000, godlo 7-czlonowe; true orto: 1:5000, "
        "godlo 8-czlonowe), a grubsze godlo rozwija sie do niej samo. Nie "
        "dotyczy CZ (arkusze SM5 1:5000; z --country auto dotyczy czesci PL) "
        "i --cutout. Szczegoly: docs/USAGE.md 1.6"
    )


def _coverage_help() -> str:
    return (
        "Wariant WCS wycinka ortofotomapy - wymagany z --cutout --product "
        "orto (bez --cutout blad; true orto ma jeden wariant - pomin): "
        f"{orto_coverage_choices()}"
    )


def _resolution_help() -> str:
    return (
        "Piksel wycinka - wymagany z --cutout (arkusze maja piksel zrodla: "
        f"bez --cutout blad): {cutout_resolution_choices(IMAGERY_PRODUCTS)}"
    )


_DOWNLOAD_PARAMS = (
    shared.product(lambda: IMAGERY_PRODUCTS, product_choices),
    shared.country(
        lambda: COUNTRIES,
        (
            "Country of the source; required with `bbox` or `geometry`, "
            "implied by a sheet code (a given value must agree). `auto` "
            "splits the area between PL and CZ; a cutout is PL only (with "
            "`auto` it covers the PL part).",
            "Kraj zrodla danych - wymagany z --bbox/--geometry: "
            f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
            "musi sie z nim zgadzac). Wycinek (--cutout) tylko PL: z auto obejmuje "
            "czesc PL",
        ),
    ),
    *shared.area(
        sheet=(
            "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 "
            "(`6.129.30.25.3`) or CZ SM5 (`CTES96`, `AS91`: a JPEG with "
            "three JGW files). A coarser PL code expands to the source "
            "sheets.",
            (
                "Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo PL"
                " rozwija sie na arkusze zrodla): PL-1992 (np. "
                "N-34-130-D-d-2-4), PL-2000 (np. 6.129.30.25.3) albo CZ SM5 "
                "(np. CTES96, AS91; JPEG i trzy pliki JGW)"
            ),
        ),
        accepts=_ACCEPTS,
        geometry=(
            "Vector file (SHP or GPKG): the sheets that intersect its "
            "features; for a cutout, its extent.",
            (
                "Plik geometrii obszaru (SHP albo GPKG): arkusze przecinajace "
                "obiekty; wycinek (--cutout) - obwiednia geometrii"
            ),
        ),
    ),
    Param(
        "direction",
        "str_list",
        (
            "Oblique orthophotos only: view directions `n`, `e`, `s`, `w`; "
            "default all four. A sheet is one file per direction "
            "(`<code>_<direction>.tif`)."
        ),
        metavar="KIERUNKI",
        allowed=_directions,
        task=True,
        section=SELECTION_TITLE,
        description_pl=(
            "Tylko --product oblique-orto: kierunki widoku po przecinku (n,"
            " e, s, w; np. n,e); arkusz orto ukosnej to plik na kierunek "
            "(<godlo>_<kierunek>.tif); bez flagi wszystkie cztery"
        ),
    ),
    Param(
        "sheet_system",
        "str",
        (
            "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` "
            "(zones EPSG:2176-2179, needs `scale`). Required with `bbox` or"
            " `geometry` for PL (not with `cutout`); may be omitted for a "
            "product with one system (true orthophoto 1992, oblique 2000); "
            "implied by a sheet code. Not for CZ."
        ),
        allowed=_sheet_systems,
        choices=True,
        task=True,
        section="Arkusze obszaru",
        description_pl=_sheet_system_help,
    ),
    Param(
        "scale",
        "str",
        (
            "Scale of PL-2000 sheets: required with `bbox` or `geometry` "
            "and `sheet_system=2000`, and with a PL-2000 1:10000 code; "
            "optional with a finer code. Oblique orthophotos have 1:2000 "
            "and 1:1000 sheets. Not for PL-1992 (one scale per product), CZ"
            " and `cutout`."
        ),
        metavar="SKALA",
        allowed=lambda: SCALES_2000,
        task=True,
        section="Arkusze obszaru",
        description_pl=_scale_help,
    ),
    Param(
        "cutout",
        "flag",
        (
            "Fetch one WCS cutout instead of sheets (with `bbox` or "
            "`geometry`; PL only; orthophoto and true orthophoto; needs "
            "`horizontal_crs` and `resolution`, orthophoto also "
            "`coverage`): an RGB GeoTIFF on the service grid, not resampled"
            " and not masked, as the server composes its flights."
        ),
        default=False,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
        description_pl=(
            "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry,"
            " tylko PL, ortofotomapa i true orto; wymaga --horizontal-crs i"
            " --resolution, ortofotomapa takze --coverage): GeoTIFF RGB z "
            "WCS GUGiK na siatce uslugi (obraz bez przeprobkowania, bez "
            "maski ladu), plik <wsp>.tif (wersje w versions/, ponowne "
            "uruchomienie uzywa lokalnej wersji; --force pobiera); "
            "kompozycja lotow serwera (bez wyboru roku); w trybie "
            "--geometry obejmuje CALA obwiednie geometrii"
        ),
    ),
    Param(
        "horizontal_crs",
        "str",
        (
            "CRS of the cutout; required with `cutout`, refused without it."
            " Only the CRS of the service grid (the image is not "
            "resampled)."
        ),
        allowed=lambda: [ORTO_CUTOUT_CRS],
        choices=True,
        normalize="upper",
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
        description_pl=(
            "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout "
            "blad): tylko uklad siatki uslugi (obraz bez przeprobkowania)"
        ),
    ),
    Param(
        "coverage",
        "str",
        (
            "WCS variant of an orthophoto cutout; required with `cutout` "
            "and `product=orto` (true orthophoto has one: omit it). "
            "`standard`: the newest available orthophotos; `high`: pixel 10"
            " cm or finer."
        ),
        metavar="WARIANT",
        allowed=_coverages,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
        description_pl=_coverage_help,
    ),
    Param(
        "resolution",
        "per_country",
        (
            "Pixel size of a cutout; required with `cutout` (sheets keep "
            "the source pixel). The choices depend on `product` and "
            "`coverage`."
        ),
        short="-r",
        metavar="ROZDZIELCZOSC",
        allowed=_cutout_resolutions,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
        description_pl=_resolution_help,
    ),
    Param(
        "year",
        "int",
        (
            "Only this data year (acquisition year of the images): the "
            "newest flight of that year. A sheet without it stops the run "
            "before any download. Excludes `min_year` and `max_year`; not "
            "with `cutout`."
        ),
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
        description_pl=(
            "Tylko ten rok danych (rok pozyskania zdjec: aktualnosc "
            "ortofotomapy); skrot --min-year ROK --max-year ROK; najnowszy "
            "lot z tego roku (wszystkie: --all-campaigns); brak roku na "
            "ktoryms arkuszu = blad przed pobraniem; nie dziala z --cutout"
        ),
    ),
    Param(
        "min_year",
        "int",
        (
            "Lower bound of the data year (inclusive): the newest flight in"
            " the range, or all of them with `all_campaigns`. Not with "
            "`cutout`."
        ),
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
        description_pl=(
            "Dolna granica roku danych (wlacznie); najnowszy lot z lat >= "
            "ROK (wszystkie: --all-campaigns); nie dziala z --cutout"
        ),
    ),
    Param(
        "max_year",
        "int",
        (
            "Upper bound of the data year (inclusive): the newest flight in"
            " the range, or all of them with `all_campaigns`; the standard "
            "path never moves to an older flight. Not with `cutout`."
        ),
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
        description_pl=(
            "Gorna granica roku danych (wlacznie); najnowszy lot z lat <= "
            "ROK (wszystkie: --all-campaigns); sciezka standardowa nigdy "
            "nie cofa sie na starszy lot; nie dziala z --cutout"
        ),
    ),
    Param(
        "all_campaigns",
        "flag",
        (
            "Fetch every flight of the year range into `versions/` instead "
            "of the newest one per sheet. Not with `cutout`."
        ),
        default=False,
        task=True,
        section=_CAMPAIGNS,
        description_pl=(
            "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
            "z flaga wszystkie loty z zakresu lat do <segment>/versions/; "
            "flagi roku ograniczaja tylko dopuszczalne lata; nie dziala z "
            "--cutout"
        ),
    ),
    Param(
        "full_sheet",
        "flag",
        (
            "Orthophoto and oblique orthophoto only (intensity and true "
            "orthophoto records declare no full sheets: an error): when the"
            " newest flight of a sheet is not full, also fetch the newest "
            "full flight of the range and link it under `full_sheet/`. Not "
            "with `cutout`."
        ),
        default=False,
        task=True,
        section=_CAMPAIGNS,
        description_pl=(
            "Ortofotomapa i orto ukosna (rekordy intensywnosci i true orto "
            "nie deklaruja pelnego arkusza: blad): gdy najnowszy lot "
            "arkusza nie jest pelny (calyArkuszWypelnionyTrescia), pobierz "
            "tez najnowszy pelny lot z zakresu lat (najwyzej jeden "
            "dodatkowy lot na arkusz) i dowiaz go w <segment>/full_sheet/; "
            "pelny = w granicach Polski; nie dziala z --cutout"
        ),
    ),
    shared.root(_output_files),
    *shared.update_params(
        check=(
            "Signal: the GUGiK index for PL sheets, the release in the CUZK"
            " ATOM feed for CZ sheets; a cutout has none.",
            (
                "Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne /"
                " nowsza / do pobrania / nie da sie sprawdzic bez pobrania); "
                "niczego nie pobiera. Arkusze PL: skorowidz GUGiK, arkusze CZ: "
                "wydanie w feedzie ATOM CUZK, wycinek: bez taniego sygnalu"
            ),
        ),
        upgrade="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje "
        "(domyslnie tylko informacja); wycinek bez taniego sygnalu zostaje "
        "lokalny (pobranie: --force); z --plan wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik zadania (arkusze, wycinek) "
        "i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, inna = "
        "nowa wersja; nic nie jest nadpisywane",
        plan="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1, przy --country auto jeden plan PL i CZ); z --upgrade: "
        "wykonaj plan (pozycje zmienione od planu = blad, bez pobrania)",
    ),
    shared.workers(
        (
            "Parallel transfers (default 4; 1 = one by one).",
            "Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
        ),
        4,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("sheet", "bbox", "geometry"),
        "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    Constraint(
        "requires",
        ("horizontal_crs", "resolution"),
        "--cutout wymaga --horizontal-crs i --resolution",
        "cutout",
    ),
    Constraint(
        "required_when",
        (),
        "--product orto z --cutout wymaga --coverage",
        "coverage",
        {"cutout": True, "product": ["orto"]},
    ),
    Constraint(
        "applies_to",
        (),
        "--horizontal-crs, --coverage i --resolution dzialaja tylko z --cutout",
        "horizontal_crs",
        {"cutout": True},
    ),
    Constraint(
        "excludes",
        ("sheet",),
        "--cutout dziala tylko z --bbox/--geometry",
        "cutout",
    ),
    Constraint(
        "applies_to",
        (),
        "--direction dotyczy tylko --product oblique-orto",
        "direction",
        {"product": ["oblique-orto"]},
    ),
    Constraint(
        "excludes",
        ("min_year", "max_year"),
        "--year wyklucza sie z --min-year/--max-year",
        "year",
    ),
)

_DOWNLOAD_EXAMPLES = (
    Example(
        {"product": "orto", "sheet": "N-34-130-D-d-2-4"},
        title="PL orthophoto: a sheet",
        title_pl="Ortofotomapa PL: arkusz",
    ),
    Example(
        {
            "product": "orto",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "coverage": "standard",
            "resolution": "0.25m",
        },
        title="PL orthophoto: a WCS cutout",
        title_pl="Ortofotomapa PL: wycinek WCS",
    ),
    Example(
        {
            "product": "orto",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "sheet_system": "1992",
        },
        title="PL orthophoto: sheets for a rectangle (1992 system)",
        title_pl="Ortofotomapa PL: arkusze dla prostokata (uklad 1992)",
    ),
    Example(
        {"product": "oblique-orto", "sheet": "7.125.11.08", "direction": ["n"]},
        title="PL oblique orthophoto: the north direction",
        title_pl="Orto ukosna PL: kierunek polnocny",
    ),
    Example(
        {"product": "orto", "sheet": "CTES96"},
        title="CZ orthophoto: an SM5 sheet",
        title_pl="Ortofotomapa CZ: arkusz SM5",
    ),
    Example(
        {
            "product": "orto",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
        },
        title="CZ orthophoto: SM5 sheets for a rectangle",
        title_pl="Ortofotomapa CZ: arkusze SM5 dla prostokata",
    ),
)

COMMANDS = (
    Command(
        "imagery download",
        ("Download orthophotos and other images as sheets or one WCS cutout"),
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Fetches orthophoto, LIDAR intensity, true and oblique "
            "orthophoto of GUGiK (PL) and the SM5 orthophoto sheets of CUZK"
            " (CZ) into the versioned store. Sheets are the source files "
            "1:1; `cutout` (PL orthophoto and true orthophoto) gives one "
            "WCS GeoTIFF. Never overwrites: new content is a new version. "
            "Not for terrain (`elevation download`)."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
        summary_pl="Pobierz arkusze obrazow (PL, CZ) albo wycinek (PL)",
        description_pl=(
            "Pobierz obrazy do magazynu wersji. PL (GUGiK): arkusze wg "
            "kampanii (--bbox/--geometry rozwija sie na arkusze zrodlowe, "
            "godla PL-1992 albo PL-2000) albo jeden wycinek GeoTIFF z WCS "
            "(--cutout: ortofotomapa i true orto); orto ukosna: arkusz = 4 "
            "pliki kierunkow (--direction). CZ (CUZK, tylko ortofotomapa): "
            "arkusze SM5 aktualnego rocznika (archiwalne ortofoto CUZK sa "
            "platne), JPEG z plikami JGW w S-JTSK, TM33N i TM34N "
            "(--bbox/--geometry rozwija sie na arkusze SM5). Arkusze: pliki"
            " zrodlowe 1:1, piksel zrodla."
        ),
        rules=(
            ("Use `cutout` for one image of an area, sheets for the source files."),
        ),
        rules_pl=(
            (
                "Uzyj `cutout` dla jednego obrazu obszaru, arkuszy dla plikow "
                "zrodlowych."
            ),
        ),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("imagery", lambda: IMAGERY_PRODUCTS),
)

GROUPS = (
    Group(
        "imagery",
        (
            "Imagery: orthophotos (PL, CZ), intensity images, true and "
            "oblique orthophotos (PL)"
        ),
        (
            "Aerial images in the versioned store: the GUGiK orthophoto "
            "(PL: sheets and WCS cutout) and the CUZK one (CZ: SM5 sheets),"
            " LIDAR intensity images, the true orthophoto (sheets and WCS "
            "cutout) and the oblique orthophoto of GUGiK (PL)."
        ),
        products=_products,
        summary_pl=(
            "Obrazy lotnicze: ortofotomapa PL i CZ, obrazy intensywnosci, "
            "true orto i orto ukosna (PL)"
        ),
        description_pl=(
            "Obrazy lotnicze w magazynie wersji: ortofotomapa GUGiK (PL: "
            "arkusze i wycinek WCS) i CUZK (CZ: arkusze SM5), obrazy "
            "intensywnosci LIDAR, prawdziwa ortofotomapa (true orto: "
            "arkusze i wycinek WCS) i ortofotomapa ukosna GUGiK (PL)."
        ),
    ),
)
