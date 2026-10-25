"""``kartograf elevation``: NMT, NMPT, LAZ and contours from GUGiK/CUZK (ADR-039)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import OUTPUT_TITLE, PL_SHEETS, PRODUCT_TITLE
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.availability import (
    AVAILABILITY_COUNTRIES,
    AVAILABILITY_PRODUCTS,
)
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    ELEVATION_PRODUCTS,
    SCALE_2000_CHOICES,
    SCALES_2000,
    SHEET_SYSTEM_CHOICES,
    cz_resolution_help,
    format_text,
    product_choices,
    product_directory,
    resolution_text,
    store_files,
    vertical_crs_text,
)
from kartograf.sources.variants import (
    CZ_VERTICAL_TEXT,
    cz_model_text,
    format_tokens,
    resolution_label,
    variants,
)

_SHEET_PRODUCTS = ("nmt", "nmpt")
# The sheet systems of the elevation commands: the PL ones and the CZ ones of
# the sheet products (SM5 sheets, TM33 tiles).
_ACCEPTS = (*PL_SHEETS, "cz_sm5", "cz_tm33")


def _products() -> list[tuple[str, str]]:
    return shared.product_summaries(ELEVATION_PRODUCTS, product_choices)


def _resolutions() -> list[str]:
    """Every grid label of the sheet products of both countries."""
    found = [v for product in _SHEET_PRODUCTS for v in variants(product=product)]
    values = sorted({v.resolution_m for v in found if v.resolution_m is not None})
    return [resolution_label(value) for value in values]


def _vertical_systems() -> list[str]:
    """Return the height systems of every variant, registry order."""
    return list(dict.fromkeys(v.vertical_crs for v in variants() if v.vertical_crs))


def _formats() -> list[str]:
    """Return the ``--format`` tokens.

    The file formats of the PL sheet products and the CZ contours.
    """
    found = tuple(
        v
        for product in _SHEET_PRODUCTS
        for v in variants(product=product, country="PL")
    )
    return list(dict.fromkeys((*format_tokens(found), *contours_formats())))


def _models() -> list[str]:
    """Return the CUZK models of the CZ point clouds."""
    found = variants(product="laz", country="CZ")
    return list(dict.fromkeys(v.model for v in found if v.model is not None))


def _sheet_systems() -> list[str]:
    """Return the PL sheet systems the registry has variants for.

    They are the values of ``--sheet-system``.
    """
    found = variants(country="PL")
    return sorted({system for v in found for system in v.systems})


def _resolution_help() -> str:
    return (
        "Rozdzielczosc siatki - wymagana tam, gdzie jest wybor. PL "
        f"(siatki ASC; NMT 100m - pliki XYZ wojewodztw): {resolution_text()}; "
        "wycinek --cutout tylko 1m (mozna pominac); archiwa (--format): "
        "rozdzielczosci w kartograf elevation list-sources. CZ: "
        f"{cz_resolution_help()}. LAZ i warstwice bez rozdzielczosci. "
        "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ z roznymi: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=1m,cz=2m)"
    )


def _model_help() -> str:
    return (
        "Model chmury LAZ CZ (wymagany z --product laz gdy zadanie siega CZ): "
        f"{cz_model_text()}. Z --product laz PL i innym produktem: blad"
    )


def _vertical_crs_help() -> str:
    return (
        f"Uklad wysokosci (wymagany). PL: {vertical_crs_text()}; NMT 100 m: "
        "pomin (GUGiK nie deklaruje ukladu). CZ: "
        f"{CZ_VERTICAL_TEXT}. LAZ CZ: Bpv = pliki SM5, EVRF2007 = pliki TM33; "
        "chmury nie sa transformowane. Warstwice CZ: Bpv (mozna pominac). Jedna "
        "wartosc dotyczy kazdego kraju "
        "zadania i musi byc dla niego dostepna; PL+CZ z roznymi ukladami: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=EVRF2007,cz=Bpv)"
    )


def _format_help() -> str:
    return (
        "Format pliku. NMT/NMPT PL: bez flagi siatka ASC (format "
        "produktu); archiwa GUGiK - pliki zrodlowe jak w skorowidzu (bez "
        "konwersji, bez --cutout; arkusze roznych skal wynikaja ze "
        f"skorowidza, bez --scale): {format_text()}. Warstwice CZ (--product "
        f"contours, wymagany): {', '.join(contours_formats())} - ZIP arkusza SM5 "
        "bez konwersji. Warianty: kartograf elevation list-sources"
    )


def _scale_help() -> str:
    return (
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        f"{SCALE_2000_CHOICES}; z drobniejszym godlem PL-2000 opcjonalna "
        "(rozwija godlo do potomkow w tej skali). PL-1992: niedozwolona - "
        "GUGiK publikuje arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), "
        "grubsze godlo rozwija sie do 1:10000 samo. Nie dotyczy CZ, LAZ "
        "i --cutout. Szczegoly: docs/USAGE.md 1.6"
    )


def _sheet_system_help() -> str:
    return (
        "Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL "
        f"(bez --cutout): {SHEET_SYSTEM_CHOICES}. Wycinek --cutout: tylko "
        "1992 (mozna pominac). Z --sheet uklad wynika z godla (podana wartosc "
        "musi sie z nim zgadzac). Nie dotyczy LAZ (uklad kazdego kafla z WFS) "
        "ani CZ"
    )


def _output_files() -> str:
    return store_files(product_directory(p) for p in ELEVATION_PRODUCTS)


_DOWNLOAD_PARAMS = (
    shared.product(lambda: ELEVATION_PRODUCTS, product_choices),
    shared.country(
        lambda: COUNTRIES,
        (
            "Country of the source; required with `bbox` or `geometry`, "
            "implied by a sheet code (a given value must agree). `auto` "
            "splits the area between PL and CZ.",
            "Kraj zrodla danych - wymagany z --bbox/--geometry: "
            f"{COUNTRY_CHOICES}. Z --sheet kraj wynika z godla (podana wartosc "
            "musi sie z nim zgadzac)",
        ),
    ),
    *shared.area(
        sheet=(
            "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 "
            "(`6.129.30.25.3`), CZ SM5 (`CTES96`) or CZ TM33 (`302_5550`). "
            "A coarser PL code expands to the source sheets; contours take "
            "SM5 sheets only.",
            (
                "Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo "
                "rozwija sie na arkusze zrodla; LAZ PL: kafle przecinajace "
                "arkusz, LAZ CZ: plik godla; NMT 100 m: pliki wojewodztw "
                "arkusza): PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. "
                "6.129.30.25.3), CZ SM5 (np. CTES96; warstwice tylko SM5) albo "
                "CZ TM33 (np. 302_5550)"
            ),
        ),
        accepts=_ACCEPTS,
        geometry=(
            "Vector file (SHP or GPKG): PL sheets and LAZ tiles that "
            "intersect its features; CZ LAZ and contours: the sheets that "
            "intersect its extent; cutout: its extent.",
            (
                "Plik geometrii obszaru (SHP albo GPKG): PL - arkusze i kafle "
                "LAZ przecinajace obiekty; CZ LAZ i warstwice - arkusze "
                "przecinajace obwiednie geometrii; wycinek (--cutout) - "
                "obwiednia geometrii"
            ),
        ),
    ),
    Param(
        "resolution",
        "per_country",
        (
            "Grid resolution label such as `1m`; required where the product"
            " offers a choice. One value applies to every country of the "
            'task, or give {"pl": "1m", "cz": "2m"}. Choices per source: '
            "`elevation list-sources`. Not used for LAZ and contours."
        ),
        short="-r",
        metavar="ROZDZIELCZOSC",
        allowed=_resolutions,
        task=True,
        section=PRODUCT_TITLE,
        description_pl=_resolution_help,
    ),
    Param(
        "model",
        "str",
        (
            "CZ LAZ point-cloud model; required with `product=laz` when the"
            " task reaches CZ. Not for other products."
        ),
        metavar="MODEL",
        allowed=_models,
        task=True,
        section=PRODUCT_TITLE,
        description_pl=_model_help,
    ),
    Param(
        "vertical_crs",
        "per_country",
        (
            "Height system; required (omit for NMT 100 m: GUGiK declares "
            "none). One value must exist in every country of the task, or "
            'give {"pl": "EVRF2007", "cz": "Bpv"}. CZ LAZ: Bpv is SM5 '
            "files, EVRF2007 TM33 files (clouds are not transformed); CZ "
            "contours: Bpv, may be omitted."
        ),
        metavar="UKLAD",
        allowed=_vertical_systems,
        task=True,
        section=PRODUCT_TITLE,
        description_pl=_vertical_crs_help,
    ),
    Param(
        "format",
        "str",
        (
            "File format. Without it NMT/NMPT PL are ASC grids. Source "
            "archives (XYZ, TIN, ...) are fetched as published, without "
            "conversion, and not with `cutout`; contours (required): SHP or"
            " DGN, the ZIP of an SM5 sheet. Variants: `elevation "
            "list-sources`."
        ),
        metavar="FORMAT",
        allowed=_formats,
        task=True,
        section=PRODUCT_TITLE,
        description_pl=_format_help,
    ),
    Param(
        "sheet_system",
        "str",
        (
            "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` "
            "(zones EPSG:2176-2179, needs `scale`). Required with `bbox` or"
            " `geometry` for PL (not with `cutout` or LAZ); implied by a "
            "sheet code."
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
            "optional with a finer code (expands it to its descendants). "
            "Not for PL-1992 (always 1:10000), CZ, LAZ and `cutout`."
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
            "`geometry`; needs `horizontal_crs`). PL: 1 m NMT/NMPT on the "
            "sheet grid, masked to the PL land, as the server composes its "
            "flights (for the newest flight fetch sheets). CZ: an "
            "exportImage cutout, required for CZ raster areas. Not for LAZ."
        ),
        default=False,
        task=True,
        section="Wycinek zamiast arkuszy",
        description_pl=(
            "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry;"
            " wymaga --horizontal-crs). PL: wycinek 1 m z WCS GUGiK "
            "(--product nmt albo nmpt, tylko --sheet-system 1992 i "
            "--resolution 1m) na siatce arkuszy, maska ladu PL (poza ladem "
            "nodata), plik <wsp>.tif (wersje w versions/, ponowne "
            "uruchomienie uzywa lokalnej wersji; --force pobiera); "
            "kompozycja lotow serwera (najnowszy lot arkuszy: pobierz "
            "arkusze bez --cutout); w trybie --geometry obejmuje CALA "
            "obwiednie geometrii. CZ: wycinek rastra exportImage - obszar "
            "CZ z NMT/NMPT (takze czesc CZ przy --country auto) wymaga "
            "--cutout; LAZ bez wycinka"
        ),
    ),
    Param(
        "horizontal_crs",
        "str",
        (
            "CRS of the cutout; required with `cutout`, refused without it."
            " Reprojected locally; the CZ native CRS is EPSG:5514."
        ),
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        allowed=lambda: list(CUTOUT_CRS),
        choices=True,
        normalize="upper",
        task=True,
        section="Wycinek zamiast arkuszy",
        description_pl=(
            "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout "
            "blad); reprojekcja lokalna przypieta operacja; natywny CZ: "
            "EPSG:5514"
        ),
    ),
    Param(
        "year",
        "int",
        (
            "Only this data year (acquisition year; `akt_rok` for LAZ): the"
            " newest flight of that year. A sheet or tile without it stops "
            "the run before any download. Excludes `min_year` and "
            "`max_year`; not with `cutout`."
        ),
        metavar="ROK",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
        description_pl=(
            "Tylko ten rok danych (rok pozyskania: aktualnosc NMT/NMPT, "
            "akt_rok LAZ); skrot --min-year ROK --max-year ROK; najnowszy "
            "lot z tego roku (wszystkie: --all-campaigns); brak roku na "
            "ktoryms arkuszu/kaflu = blad przed pobraniem; nie dziala z "
            "--cutout"
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
        section="Rok danych, loty i kafle (tylko PL)",
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
        section="Rok danych, loty i kafle (tylko PL)",
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
            "of the newest one per sheet. LAZ: coverage is not "
            "deduplicated. Not with `cutout`."
        ),
        default=False,
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
        description_pl=(
            "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); "
            "z flaga wszystkie loty z zakresu lat do <segment>/versions/; "
            "flagi roku ograniczaja tylko dopuszczalne lata; LAZ: bez "
            "deduplikacji pokrycia; nie dziala z --cutout"
        ),
    ),
    Param(
        "full_sheet",
        "flag",
        (
            "NMT/NMPT: when the newest flight of a sheet is not full "
            "(`calyArkuszWypelnionyTrescia`), also fetch the newest full "
            "flight of the range (one more per sheet at most) and link it "
            "under `full_sheet/`. Not with `cutout` and LAZ."
        ),
        default=False,
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
        description_pl=(
            "NMT/NMPT: gdy najnowszy lot arkusza nie jest pelny "
            "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot"
            " z zakresu lat (najwyzej jeden dodatkowy lot na arkusz) i "
            "dowiaz go w <segment>/full_sheet/; pelny = w granicach Polski;"
            " nie dziala z --cutout ani z LAZ"
        ),
    ),
    Param(
        "min_density",
        "int",
        (
            "LAZ PL only: keep the tiles with at least this point density "
            "(points per m2)."
        ),
        metavar="N",
        task=True,
        section="Rok danych, loty i kafle (tylko PL)",
        description_pl=(
            "Tylko LAZ PL (--product laz; z innym produktem blad): zostaw "
            "kafle o gestosci punktow >= N pkt/m2"
        ),
        unit="points/m2",
    ),
    shared.root(_output_files),
    *shared.update_params(
        check=(
            "Cheap signal: the ETag of SM5 sheets, TM33 DMR 4G and DMP OK "
            "EVRF2007 tiles and CZ LAZ; cutouts and ImageServer tiles have "
            "none.",
            (
                "Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne /"
                " nowsza / do pobrania / nie da sie sprawdzic bez pobrania); "
                "niczego nie pobiera. Pliki arkuszy SM5, kafle TM33 DMR 4G/DMP "
                "OK EVRF2007 i LAZ CZ: ETag; wycinki i kafle z ImageServer: bez"
                " taniego sygnalu"
            ),
        ),
        upgrade="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie "
        "tylko informacja); pliki bez taniego sygnalu zostaja lokalne "
        "(pobranie: --force); z --plan wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik zadania (arkusze, kafle LAZ, "
        "wycinki) i odswiez liste kampanii z GUGiK; ta sama tresc = bez zmian, "
        "inna = nowa wersja; nic nie jest nadpisywane",
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
        ("horizontal_crs",),
        "--cutout wymaga --horizontal-crs",
        "cutout",
    ),
    Constraint(
        "applies_to",
        (),
        "--horizontal-crs dziala tylko z --cutout",
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
        "excludes",
        ("min_year", "max_year"),
        "--year wyklucza sie z --min-year/--max-year",
        "year",
    ),
    Constraint(
        "applies_to",
        (),
        "--min-density dziala tylko z --product laz",
        "min_density",
        {"product": ["laz"]},
    ),
    Constraint(
        "applies_to",
        (),
        "--model dotyczy tylko --product laz",
        "model",
        {"product": ["laz"]},
    ),
)

_DOWNLOAD_EXAMPLES = (
    Example(
        {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
        },
        title="PL sheet: NMT 1 m in EVRF2007",
        title_pl="Arkusz PL: NMT 1 m w EVRF2007",
    ),
    Example(
        {
            "product": "laz",
            "country": "pl",
            "bbox": [530000, 382000, 533000, 386000],
            "bbox_crs": "EPSG:2180",
            "vertical_crs": "KRON86",
        },
        title="PL LAZ point cloud for a rectangle",
        title_pl="Chmura LAZ PL dla prostokata",
    ),
    Example(
        {
            "product": "nmt",
            "country": "pl",
            "bbox": [565000, 242000, 565500, 242500],
            "bbox_crs": "EPSG:2180",
            "sheet_system": "1992",
            "resolution": "5m",
            "vertical_crs": "EVRF2007",
        },
        title="PL area: NMT 5 m sheets in the 1992 system",
        title_pl="Obszar PL: arkusze NMT 5 m w ukladzie 1992",
    ),
    Example(
        {
            "product": "nmt",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "vertical_crs": "EVRF2007",
        },
        title="PL cutout: NMT 1 m from WCS",
        title_pl="Wycinek PL: NMT 1 m z WCS",
    ),
    Example(
        {
            "product": "nmt",
            "sheet": "CTES96",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title="CZ SM5 sheet: NMT 5 m in Bpv",
        title_pl="Arkusz CZ SM5: NMT 5 m w Bpv",
    ),
    Example(
        {
            "product": "nmt",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
            "cutout": True,
            "horizontal_crs": "EPSG:5514",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title="CZ cutout in S-JTSK",
        title_pl="Wycinek CZ w S-JTSK",
    ),
    Example(
        {
            "product": "laz",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
            "model": "dmr5g",
            "vertical_crs": "Bpv",
        },
        title="CZ LAZ point cloud: DMR 5G model for a rectangle",
        title_pl="Chmura LAZ CZ: model DMR 5G dla prostokata",
    ),
)

_AVAILABILITY_PARAMS = (
    replace(
        shared.product(lambda: AVAILABILITY_PRODUCTS, product_choices),
        task=False,
    ),
    replace(
        shared.country(
            lambda: list(AVAILABILITY_COUNTRIES),
            (
                "Country; required with `bbox` or `geometry`, implied by a "
                "sheet code. `auto` reports the PL and CZ parts together.",
                "Kraj - wymagany z --bbox/--geometry: "
                f"{', '.join(AVAILABILITY_COUNTRIES.values())}. Z --sheet kraj wynika "
                "z godla",
            ),
        ),
        task=False,
    ),
    *(
        replace(param, task=False)
        for param in shared.area(
            sheet=(
                "Sheet code: PL (PL-1992 or PL-2000), CZ SM5 (`CTES96`) or TM33"
                " tile (`760_5518`); the area is the sheet frame.",
                (
                    "Godlo arkusza: PL (PL-1992 albo PL-2000), CZ SM5 (np. CTES96) "
                    "albo kafel TM33 (np. 760_5518); obszar = rama arkusza"
                ),
            ),
            accepts=_ACCEPTS,
            geometry=(
                "Vector file (SHP or GPKG): the area is the extent of its "
                "features (LAZ: of the whole layer; CZ: of the geometry), as in"
                " `elevation download`.",
                (
                    "Plik geometrii obszaru (SHP albo GPKG): obszar = obwiednie "
                    "obiektow (LAZ: obwiednia calej warstwy; CZ: obwiednia "
                    "geometrii) - jak w elevation download"
                ),
            ),
        )
    ),
    Param(
        "year",
        "int",
        (
            "Only this year (the yearly layer of the GUGiK index). Excludes"
            " `min_year` and `max_year`."
        ),
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
        description_pl=(
            "Tylko ten rok (warstwa roczna skorowidza GUGiK); skrot "
            "--min-year ROK --max-year ROK"
        ),
    ),
    Param(
        "min_year",
        "int",
        "Lower bound of the year (inclusive).",
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
        description_pl="Dolna granica roku (wlacznie)",
    ),
    Param(
        "max_year",
        "int",
        "Upper bound of the year (inclusive).",
        metavar="ROK",
        section="Rok danych (tylko PL - CUZK nie publikuje lat nalotu: z "
        "--country cz blad, z --country auto raport tylko czesci PL)",
        description_pl="Gorna granica roku (wlacznie)",
    ),
    Param(
        "details",
        "flag",
        argument=None,
        section="Wynik",
        description_pl=(
            "Dla kazdej kombinacji: godla arkuszy niepelnych (CZ: arkuszy "
            "bez pliku), obszar bez arkuszy i wszystkie polecenia pobrania"
        ),
    ),
    Param(
        "json",
        "flag",
        argument=None,
        section="Wynik",
        description_pl=(
            "Wypisz raport jako JSON (kartograf-availability/1, ten sam "
            "ksztalt co check_availability)"
        ),
    ),
    Param(
        "force",
        "flag",
        (
            "Skip the metadata cache: query the indexes, PRG and CUZK files"
            " again and overwrite the cache entries."
        ),
        default=False,
        section="Wynik",
        description_pl=(
            "Pomin cache metadanych (odpytaj skorowidze, PRG i pliki CUZK "
            "ponownie, nadpisz cache)"
        ),
    ),
)

COMMANDS = (
    Command(
        "elevation download",
        ("Download NMT, NMPT, LAZ or contours as sheets, tiles or one WCS cutout"),
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Fetches the DTM (NMT), DSM (NMPT), LAZ point clouds or CZ "
            "contours of GUGiK (PL) and CUZK (CZ) into the versioned store."
            " Select the area with a sheet code, `bbox` or `geometry`; "
            "`cutout` gives one WCS raster instead of sheets. Never "
            "overwrites: new content is a new version. Not for imagery "
            "(`imagery download`)."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
        summary_pl=(
            "Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)"
        ),
        description_pl=(
            "Pobierz NMT, NMPT i chmury punktow LAZ z GUGiK (PL) albo CUZK "
            "(CZ) do magazynu wersji. PL: --bbox/--geometry wybiera "
            "arkusze/kafle LAZ, --cutout --horizontal-crs daje wycinek 1 m "
            "z WCS GUGiK; NMT 100 m (--resolution 100m) to pliki XYZ "
            "wojewodztw obszaru. CZ: rastry SM5/TM33 z plikow CUZK albo "
            "ImageServer (kafle TM33 DMR 4G i DMP OK z plikow "
            "ETRS89/EVRF2007); dla obszaru rastra --cutout wymagane. LAZ "
            "CZ: --model i arkusz SM5/TM33 albo obszar (arkusze z indeksu),"
            " bez --cutout i bez transformacji chmur. Warstwice CZ "
            "(--product contours --format SHP|DGN): ZIP arkusza SM5 1:1, "
            "obszar = arkusze SM5 z indeksu, bez --cutout."
        ),
        rules=(
            (
                "Run `elevation availability` first if you do not know which "
                "years, grids and CRSs exist."
            ),
            ("Set `vertical_crs` and `resolution` yourself: nothing is guessed."),
        ),
        rules_pl=(
            (
                "Najpierw `elevation availability`, gdy nie wiesz, jakie lata, "
                "siatki i uklady sa dostepne."
            ),
            ("Podaj `vertical_crs` i `resolution` jawnie: nic nie jest zgadywane."),
        ),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("elevation", lambda: ELEVATION_PRODUCTS),
    Command(
        "elevation availability",
        ("Report the years, grids, CRSs and formats of NMT, NMPT or LAZ for an area"),
        "query",
        "check_availability",
        "kartograf-availability/1",
        _AVAILABILITY_PARAMS,
        description=(
            "Read only. PL: the years, grids, CRSs and formats for which "
            "the area has full sheets (LAZ: tiles) in the GUGiK index; CZ: "
            "which SM5 sheets and TM33 tiles have CUZK files, with date and"
            " size. Use it before `elevation download`; it fetches no data."
            " `country=auto` reports both parts together."
        ),
        effects=("network",),
        constraints=(
            Constraint(
                "one_of",
                ("sheet", "bbox", "geometry"),
                "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
            ),
            Constraint(
                "excludes",
                ("min_year", "max_year"),
                "--year wyklucza sie z --min-year/--max-year",
                "year",
            ),
        ),
        examples=(
            Example(
                {
                    "product": "nmt",
                    "country": "pl",
                    "bbox": [565000, 242000, 569000, 246000],
                    "bbox_crs": "EPSG:2180",
                },
                title="NMT availability in PL for a rectangle",
                title_pl="Dostepnosc NMT PL dla prostokata",
            ),
            Example(
                {"product": "nmpt", "sheet": "CTES96"},
                title="NMPT availability for a CZ sheet",
                title_pl="Dostepnosc NMPT dla arkusza CZ",
            ),
            Example(
                {
                    "product": "laz",
                    "country": "pl",
                    "geometry": "zlewnia.gpkg",
                    "min_year": 2020,
                },
                title="LAZ availability in PL since 2020 for a geometry",
                run={"details": True},
                title_pl="Dostepnosc LAZ PL od 2020 dla geometrii",
            ),
        ),
        summary_pl=("Raport dostepnosci NMT, NMPT i LAZ dla obszaru (bez pobierania)"),
        description_pl=(
            "Bez pobierania danych: PL - dla jakich lat, ukladow, "
            "rozdzielczosci, ukladow wysokosci i formatow obszar ma komplet"
            " pelnych arkuszy (LAZ: kafli) wg skorowidza GUGiK (skorowidz "
            "WFS i maska ladu PRG; kompletna kombinacja: caly lad obszaru "
            "lezy w arkuszach pelnych, calyArkuszWypelnionyTrescia); CZ - "
            "ktore arkusze SM5 i kafle TM33 obszaru (indeks "
            "KladyMapovychListu) maja pliki CUZK, z data publikacji i "
            "rozmiarem z naglowkow HEAD (CUZK nie publikuje lat nalotu). "
            "--country auto: czesci PL i CZ obszaru w jednym raporcie. "
            "Stopka podaje polecenia pobrania kompletnych kombinacji (PL: "
            "najnowszej)."
        ),
        rules=(
            (
                "Take `year`, `resolution`, `vertical_crs` and `format` of a "
                "complete combination."
            ),
        ),
        rules_pl=(
            (
                "Wez `year`, `resolution`, `vertical_crs` i `format` kompletnej"
                " kombinacji."
            ),
        ),
        errors=(
            "validation_error",
            "source_unavailable",
            "no_data",
            "store_unavailable",
            "io_error",
            "forbidden",
        ),
        family="availability",
        core=True,
    ),
)

GROUPS = (
    Group(
        "elevation",
        ("Elevation: DTM, DSM and LAZ point clouds (PL and CZ), contours (CZ)"),
        (
            "Elevation data from GUGiK (PL) and CUZK (CZ): DTM (NMT), DSM "
            "(NMPT), LAZ point clouds and ZABAGED contours (CZ)."
        ),
        products=_products,
        summary_pl="Wysokosci: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)",
        description_pl=(
            "Dane wysokosciowe NMT/NMPT i chmury punktow LAZ z GUGiK (PL) i"
            " CUZK (CZ) oraz warstwice ZABAGED (CZ)."
        ),
    ),
)
