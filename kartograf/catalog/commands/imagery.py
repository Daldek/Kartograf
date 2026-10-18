"""``kartograf imagery``: GUGiK images - orthophotomap (sheets and WCS cutout),
intensity images, true orthophotomap (sheets and WCS cutout), oblique
orthophotomap (PL) - and CUZK SM5 orthophoto sheets (CZ) (ADR-039, ADR-042
D13, D14, plan E1)."""

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
    """The view directions of the image products (the oblique orthophotomap)."""
    found = (d for product in IMAGERY_PRODUCTS for d in image_directions(product))
    return list(dict.fromkeys(found))


def _coverages() -> list[str]:
    """The WCS variants of the orthophotomap cutout (``standard``, ``high``)."""
    return [
        channel.params.variant
        for channel in wcs_cutout_channels(ORTO_KEY)
        if isinstance(channel.params, WcsCutoutParams)
    ]


def _cutout_resolutions() -> list[str]:
    """The pixels of every WCS cutout channel of the image products."""
    labels: list[str] = []
    for product in IMAGERY_PRODUCTS:
        source = image_source(product)
        channels = wcs_cutout_channels(source.key) if source is not None else ()
        for channel in channels:
            if isinstance(channel.params, WcsCutoutParams):
                labels += [resolution_label(v) for v in channel.params.resolutions]
    return list(dict.fromkeys(labels))


def _sheet_systems() -> list[str]:
    """The PL sheet systems the registry has variants for (``--sheet-system``)."""
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
        "Kraj zrodla danych - wymagany z --bbox/--geometry: "
        f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
        "musi sie z nim zgadzac). Wycinek (--cutout) tylko PL: z auto obejmuje "
        "czesc PL",
    ),
    *shared.area(
        sheet="Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
        "PL rozwija sie na arkusze zrodla): PL-1992 (np. N-34-130-D-d-2-4), "
        "PL-2000 (np. 6.129.30.25.3) albo CZ SM5 (np. CTES96, AS91; JPEG i trzy "
        "pliki JGW)",
        accepts=_ACCEPTS,
        geometry="Plik geometrii obszaru (SHP albo GPKG): arkusze "
        "przecinajace obiekty; wycinek (--cutout) - obwiednia geometrii",
    ),
    Param(
        "direction",
        "str_list",
        "Tylko --product oblique-orto: kierunki widoku po przecinku (n, e, "
        "s, w; np. n,e); arkusz orto ukosnej to plik na kierunek "
        "(<godlo>_<kierunek>.tif); bez flagi wszystkie cztery",
        metavar="KIERUNKI",
        allowed=_directions,
        task=True,
        section=SELECTION_TITLE,
    ),
    Param(
        "sheet_system",
        "str",
        _sheet_system_help,
        allowed=_sheet_systems,
        choices=True,
        task=True,
        section="Arkusze obszaru",
    ),
    Param(
        "scale",
        "str",
        _scale_help,
        metavar="SKALA",
        allowed=lambda: SCALES_2000,
        task=True,
        section="Arkusze obszaru",
    ),
    Param(
        "cutout",
        "flag",
        "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry, "
        "tylko PL, ortofotomapa i true orto; wymaga --horizontal-crs i "
        "--resolution, ortofotomapa takze --coverage): GeoTIFF RGB z WCS GUGiK "
        "na siatce uslugi (obraz bez przeprobkowania, bez maski ladu), plik "
        "<wsp>.tif (wersje w versions/, ponowne uruchomienie uzywa lokalnej "
        "wersji; --force pobiera); kompozycja lotow serwera (bez wyboru roku); "
        "w trybie --geometry obejmuje CALA obwiednie geometrii",
        default=False,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
    ),
    Param(
        "horizontal_crs",
        "str",
        "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad): "
        "tylko uklad siatki uslugi (obraz bez przeprobkowania)",
        allowed=lambda: [ORTO_CUTOUT_CRS],
        choices=True,
        normalize="upper",
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
    ),
    Param(
        "coverage",
        "str",
        _coverage_help,
        metavar="WARIANT",
        allowed=_coverages,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
    ),
    Param(
        "resolution",
        "per_country",
        _resolution_help,
        short="-r",
        metavar="ROZDZIELCZOSC",
        allowed=_cutout_resolutions,
        task=True,
        section="Wycinek zamiast arkuszy (tylko PL)",
    ),
    Param(
        "year",
        "int",
        "Tylko ten rok danych (rok pozyskania zdjec: aktualnosc "
        "ortofotomapy); skrot --min-year ROK --max-year ROK; najnowszy lot "
        "z tego roku (wszystkie: --all-campaigns); brak roku na ktoryms "
        "arkuszu = blad przed pobraniem; nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "min_year",
        "int",
        "Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK "
        "(wszystkie: --all-campaigns); nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "max_year",
        "int",
        "Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK "
        "(wszystkie: --all-campaigns); sciezka standardowa nigdy nie cofa sie "
        "na starszy lot; nie dziala z --cutout",
        metavar="ROK",
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "all_campaigns",
        "flag",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
        "z flaga wszystkie loty z zakresu lat do <segment>/versions/; flagi "
        "roku ograniczaja tylko dopuszczalne lata; nie dziala z --cutout",
        default=False,
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "full_sheet",
        "flag",
        "Ortofotomapa i orto ukosna (rekordy intensywnosci i true orto nie "
        "deklaruja pelnego arkusza: blad): gdy najnowszy lot arkusza nie jest "
        "pelny (calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot "
        "z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i dowiaz go "
        "w <segment>/full_sheet/; pelny = w granicach Polski; nie dziala "
        "z --cutout",
        default=False,
        task=True,
        section=_CAMPAIGNS,
    ),
    shared.output_dir(_output_files),
    *shared.update_params(
        check="Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne "
        "/ nowsza / do pobrania / nie da sie sprawdzic bez pobrania); niczego "
        "nie pobiera. Arkusze PL: skorowidz GUGiK, arkusze CZ: wydanie w feedzie "
        "ATOM CUZK, wycinek: bez taniego sygnalu",
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
    shared.workers("Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)", 4),
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
        title="Ortofotomapa PL: arkusz",
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
        title="Ortofotomapa PL: wycinek WCS",
    ),
    Example(
        {"product": "oblique-orto", "sheet": "7.125.11.08", "direction": ["n"]},
        title="Orto ukosna PL: kierunek polnocny",
    ),
    Example(
        {"product": "orto", "sheet": "CTES96"},
        title="Ortofotomapa CZ: arkusz SM5",
    ),
)

COMMANDS = (
    Command(
        "imagery download",
        "Pobierz arkusze obrazow (PL, CZ) albo wycinek (PL)",
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Pobierz obrazy do magazynu wersji. PL (GUGiK): arkusze wg kampanii "
            "(--bbox/--geometry rozwija sie na arkusze zrodlowe, godla PL-1992 "
            "albo PL-2000) albo jeden wycinek GeoTIFF z WCS (--cutout: "
            "ortofotomapa i true orto); orto ukosna: arkusz = 4 pliki kierunkow "
            "(--direction). CZ (CUZK, tylko ortofotomapa): arkusze SM5 "
            "aktualnego rocznika (archiwalne ortofoto CUZK sa platne), JPEG "
            "z plikami JGW w S-JTSK, TM33N i TM34N (--bbox/--geometry rozwija sie "
            "na arkusze SM5). Arkusze: pliki zrodlowe 1:1, piksel zrodla."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        tool="imagery_download",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
    ),
    shared.list_sources_command("imagery", lambda: IMAGERY_PRODUCTS),
)

GROUPS = (
    Group(
        "imagery",
        "Obrazy lotnicze: ortofotomapa PL i CZ, obrazy intensywnosci, true "
        "orto i orto ukosna (PL)",
        "Obrazy lotnicze w magazynie wersji: ortofotomapa GUGiK (PL: "
        "arkusze i wycinek WCS) i CUZK (CZ: arkusze SM5), obrazy intensywnosci "
        "LIDAR, prawdziwa ortofotomapa (true orto: arkusze i wycinek WCS) i "
        "ortofotomapa ukosna GUGiK (PL).",
        products=_products,
    ),
)
