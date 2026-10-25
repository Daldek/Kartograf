"""Declare ``kartograf landcover``.

BDOT10k and BDOO (GUGiK), CORINE Land Cover, ZABAGED, Data50 and Data250 (CUZK)
(ADR-039, ADR-042 D15, ADR-043).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    OUTPUT_TITLE,
    PL_SHEETS,
    PRODUCT_TITLE,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.options import store_files
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_PRODUCT_CHOICES,
    LANDCOVER_PRODUCTS,
    bdoo_year_choices,
    bdot10k_archive_choices,
)
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.sources.descriptor import AtomFilesParams, UnitPackageParams
from kartograf.sources.registry import get_source, sources_for

_BDOT10K = "pl.gugik.bdot10k"


def _products() -> list[tuple[str, str]]:
    """Each product with the name and country of its source, as the help names it."""
    summaries = []
    for name in LANDCOVER_PRODUCTS:
        source = next(
            d
            for d in sources_for(product=name)
            if d.storage_subdir.split("/", 1)[0] == "landcover"
        )
        summaries.append((name, f"{source.name}, {source.country}"))
    return summaries


def _formats() -> list[str]:
    """Return the BDOT10k formats: the current packages and the yearly archive."""
    archive = (
        dict(variant.choice)["format"]
        for channel in get_source(_BDOT10K).channels
        if isinstance(channel.params, UnitPackageParams)
        for variant in channel.params.variants
    )
    return list(dict.fromkeys((*Bdot10kProvider.OPENDATA_PATTERNS, *archive)))


def _national_file_crs() -> list[str]:
    """Return the ``--horizontal-crs`` values.

    The CRSs in which the national files of the land cover sources on the collection
    engines are published (the ATOM channels of the registry).
    """
    return list(
        dict.fromkeys(
            crs
            for key in COLLECTION_SOURCES.values()
            for channel in get_source(key).channels
            if isinstance(channel.params, AtomFilesParams)
            for crs in channel.params.crs
        )
    )


def _year_help() -> str:
    return (
        "Rok danych. CORINE (wymagany): wydanie (rok referencyjny) 2018, "
        "2012, 2006, 2000 (edycje pokrycia terenu CLMS/WMS), 1990 (tylko "
        "podglad WMS). BDOT10k: rocznik archiwum (stan z poczatku roku) "
        f"{bdot10k_archive_choices()} - oryginalna paczka powiatu ZIP; bez "
        f"--year biezace paczki. BDOO (wymagany): rocznik {bdoo_year_choices()} "
        "- oryginalna paczka wojewodztwa ZIP"
    )


def _product_help() -> str:
    return f"Produkt (wymagany): {LANDCOVER_PRODUCT_CHOICES}"


_PRODUCT = replace(
    shared.PRODUCT,
    description_pl=_product_help,
    allowed=lambda: LANDCOVER_PRODUCTS,
    choices=True,
)

_DOWNLOAD_PARAMS = (
    _PRODUCT,
    Param(
        "teryt",
        "str",
        (
            "TERYT code: a BDOT10k county (4 digits, `1465`) or a BDOO "
            "voivodeship (2 digits, `12`)."
        ),
        metavar="KOD",
        task=True,
        section=SELECTION_TITLE,
        description_pl=(
            "Kod TERYT: powiat BDOT10k (4 cyfry, np. 1465) albo wojewodztwo"
            " BDOO (2 cyfry, np. 12)"
        ),
    ),
    *shared.area(
        sheet=(
            "Sheet code (for example N-34-130-D): the area is the extent of"
            " that sheet, as bbox with its corners. BDOT10k: the counties "
            "that intersect the sheet; BDOO: the voivodeships.",
            f"{SHEET_AREA_HELP}; BDOT10k: powiaty przecinajace arkusz, "
            "BDOO: wojewodztwa",
        ),
        accepts=PL_SHEETS,
    ),
    Param(
        "whole_country",
        "flag",
        (
            "ZABAGED, Data50 and Data250 only: the national file instead of"
            " an area (a ZIP as published: ZABAGED GeoPackage of the whole "
            "base, several GB; Data50 and Data250 Shapefile, 230-760 MB; "
            "needs `horizontal_crs`). The size is in a notice before the "
            "download."
        ),
        default=False,
        task=True,
        section=SELECTION_TITLE,
        description_pl=(
            "Tylko ZABAGED, Data50 i Data250: plik krajowy zamiast obszaru "
            "(ZIP 1:1 - ZABAGED: GeoPackage pelnej bazy, kilka GB; "
            "Data50/Data250: Shapefile, 230-760 MB; wymaga "
            "--horizontal-crs); rozmiar z feedu w Warning przed pobraniem"
        ),
    ),
    Param(
        "year",
        "int",
        (
            "Data year. CORINE (required): edition 2018, 2012, 2006 or 2000"
            " (CLMS/WMS land cover), 1990 (WMS preview only). BDOT10k: "
            "archive year 2014-2025 (needs `format` GML or SHP; the "
            "original county ZIP), without it the current packages. BDOO "
            "(required): 2015 or 2021-2026 (the original voivodeship ZIP)."
        ),
        metavar="ROK",
        task=True,
        section=PRODUCT_TITLE,
        description_pl=_year_help,
    ),
    Param(
        "format",
        "str",
        (
            "BDOT10k only: the current packages as GPKG (default) or SHP; "
            "with `year` (the yearly archive) GML or SHP is required."
        ),
        short="-f",
        allowed=_formats,
        choices=True,
        normalize="upper",
        task=True,
        section=PRODUCT_TITLE,
        description_pl=(
            "Tylko BDOT10k: biezace paczki GPKG (GeoPackage, domyslnie) lub"
            " SHP (archiwum ZIP z plikami Shapefile); z --year (archiwum "
            "rocznikow) wymagany GML albo SHP"
        ),
    ),
    Param(
        "layers",
        "str_list",
        (
            "Layer or class codes, for example `SWRS` and `PTWP`; default "
            "all. Current BDOT10k GPKG: keeps the chosen layers. BDOO: a "
            "ZIP of the chosen classes of each package (no complex objects,"
            " XSD or metadata). Codes: `landcover list-layers`."
        ),
        metavar="KODY",
        task=True,
        section=PRODUCT_TITLE,
        description_pl=(
            "Kody po przecinku (np. SWRS,PTWP); domyslnie wszystkie. "
            "Biezace BDOT10k GPKG: zostaw wybrane warstwy. BDOO: ZIP plikow"
            " wybranych klas z kazdej paczki (bez obiektow zlozonych, XSD i"
            " metadanych). Lista: landcover list-layers"
        ),
    ),
    Param(
        "keep_raw",
        "flag",
        (
            "Current BDOT10k GPKG only: also keep the original GUGiK ZIP "
            "next to the file (a raw version in the store)."
        ),
        default=False,
        task=True,
        section=PRODUCT_TITLE,
        description_pl=(
            "Tylko biezace BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok"
            " pliku (wersja surowa w magazynie)"
        ),
    ),
    Param(
        "horizontal_crs",
        "str",
        (
            "CRS of the national file; required with `whole_country` "
            "(ZABAGED, Data50, Data250). Area results are always in the "
            "service CRS EPSG:5514."
        ),
        allowed=_national_file_crs,
        choices=True,
        normalize="upper",
        task=True,
        section=PRODUCT_TITLE,
        description_pl=(
            "Tylko --whole-country (ZABAGED, Data50, Data250; wymagany): "
            "uklad pliku krajowego; wynik obszaru zawsze w ukladzie uslugi "
            "EPSG:5514"
        ),
    ),
    shared.root(lambda: store_files(["landcover"])),
    *shared.update_params(
        check=(
            "Signal: the release of CORINE (CLMS) and of the national "
            "ZABAGED, Data50 and Data250 files; BDOT10k, BDOO, the CORINE "
            "preview and CUZK areas have none.",
            (
                "Porownaj lokalne wersje ze zrodlem bez pobierania: CORINE "
                "(CLMS) i pliki krajowe ZABAGED, Data50, Data250 - wydanie "
                "zrodla; BDOT10k, BDOO, podglad CORINE i obszary CUZK - brak "
                "taniego sygnalu (nie da sie sprawdzic bez pobrania)"
            ),
        ),
        upgrade="Pobierz nowsze wydanie CORINE albo pliku krajowego CUZK "
        "(domyslnie tylko informacja); BDOT10k, BDOO, podglad CORINE i obszary "
        "CUZK zostaja lokalne (pobranie: --force); z --plan wykonaj zapisany "
        "plan",
        force="Pobierz ponownie kazdy plik (BDOT10k i BDOO: takze odswiez "
        "jednostki obszaru z PRG); ta sama tresc = bez zmian, inna = nowa wersja",
        plan="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    ),
    shared.workers(
        (
            "BDOT10k or BDOO area only (several counties or voivodeships): "
            "parallel transfers, default 1.",
            (
                "Tylko obszar BDOT10k albo BDOO (wiele powiatow albo "
                "wojewodztw): liczba rownoleglych pobran (domyslnie 1)"
            ),
        ),
        1,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("teryt", "sheet", "bbox", "geometry", "whole_country"),
        "Podaj dokladnie jeden obszar: --teryt, --sheet, --bbox, --geometry "
        "albo --whole-country",
    ),
    Constraint(
        "requires",
        ("horizontal_crs",),
        "--whole-country wymaga --horizontal-crs",
        "whole_country",
    ),
    Constraint(
        "applies_to",
        (),
        "--keep-raw dotyczy tylko biezacych paczek BDOT10k",
        "keep_raw",
        {"product": ["bdot10k"]},
    ),
    Constraint(
        "applies_to",
        (),
        "--whole-country dotyczy tylko ZABAGED, Data50 i Data250",
        "whole_country",
        {"product": ["zabaged", "data50", "data250"]},
    ),
)

COMMANDS = (
    Command(
        "landcover download",
        ("Download land cover: BDOT10k, BDOO, CORINE, ZABAGED, Data50 or Data250"),
        "data",
        "download_landcover",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Fetches one land-cover product for one area (`teryt`, `sheet`,"
            " `bbox` or `geometry`): BDOT10k county packages or archive, "
            "BDOO voivodeship packages, CORINE, or the ZABAGED, Data50 and "
            "Data250 GeoPackage of the area or the national file (CZ). "
            "Never overwrites: new content is a new version. Not for soil "
            "(`soil download`)."
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_landcover",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=(
            Example(
                {"product": "bdot10k", "teryt": "1465"},
                title="BDOT10k: a county package",
                title_pl="BDOT10k: paczka powiatu",
            ),
            Example(
                {"product": "bdoo", "teryt": "12", "year": 2023},
                title="BDOO: a voivodeship package of the 2023 archive",
                title_pl="BDOO: paczka wojewodztwa z rocznika 2023",
            ),
            Example(
                {"product": "corine", "year": 2018, "sheet": "N-34-130-D"},
                title="CORINE 2018 for a sheet",
                title_pl="CORINE 2018 dla arkusza",
            ),
            Example(
                {
                    "product": "zabaged",
                    "bbox": [-460000, -1120000, -450000, -1110000],
                    "bbox_crs": "EPSG:5514",
                },
                title="CZ ZABAGED for a rectangle in S-JTSK",
                title_pl="ZABAGED (CZ) dla prostokata w S-JTSK",
            ),
        ),
        summary_pl="Pobierz dane wybranego produktu pokrycia terenu",
        description_pl=(
            "Pobierz dane wybranego produktu (--product) dla jednego "
            "obszaru: --teryt, --sheet, --bbox albo --geometry. BDOT10k "
            "obszaru = paczki kazdego powiatu, ktory obszar przecina (PRG);"
            " z --year paczki z archiwum rocznikow BDOT10k (GML albo SHP, "
            "zapis 1:1). BDOO (--year wymagany): oryginalna paczka GML "
            "wojewodztwa (--teryt 2 cyfry; obszar = paczki wojewodztw, "
            "ktore przecina, wg PRG); --layers zostawia pliki wybranych "
            "klas. ZABAGED, Data50 i Data250 (CZ): obszar "
            "(--bbox/--geometry) = jeden GeoPackage warstw uslugi w "
            "EPSG:5514 (ZABAGED: pokrycie terenu i wody, Data50/Data250: "
            "wszystkie warstwy obiektowe; nazwy CUZK, bez przeliczenia na "
            "kody BDOT10k; lista: landcover list-layers), --whole-country ="
            " plik krajowy z feedu ATOM CUZK (ZABAGED: GPKG, "
            "Data50/Data250: SHP; zapis 1:1)."
        ),
        rules=("`year` is required for CORINE and BDOO.",),
        rules_pl=("`year` jest wymagany dla CORINE i BDOO.",),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("landcover", lambda: LANDCOVER_PRODUCTS),
    Command(
        "landcover list-layers",
        ("List the layers, classes or years of a land-cover product (offline)"),
        "query",
        "list_layers",
        "kartograf-layers/1",
        (
            Param(
                "group",
                "str",
                flag=None,
                required=True,
                description_pl=(
                    "Grupa komend (tu: landcover); list_layers obsluguje landcover "
                    "i soil"
                ),
                fixed="landcover",
            ),
            replace(
                _PRODUCT,
                task=False,
                section=None,
            ),
            shared.JSON,
        ),
        description=(
            "Lists the layers of BDOT10k, ZABAGED, Data50 and Data250, the "
            "BDOO classes per archive year or the CORINE years. Use it to "
            "choose `layers` and `year` for `landcover download`."
        ),
        summary_pl="Wypisz warstwy wybranego produktu",
        description_pl=(
            "Wypisz warstwy BDOT10k, ZABAGED, Data50 i Data250, klasy BDOO "
            "wg rocznikow albo lata CORINE (bez sieci)"
        ),
        rules=(),
        rules_pl=(),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {"product": "bdoo"},
                title="The classes of BDOO per archive year",
                title_pl="Klasy BDOO wg rocznikow",
            ),
            Example(
                {"product": "corine"},
                title="The years of CORINE",
                title_pl="Roczniki CORINE",
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "landcover",
        "Land cover: BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250",
        (
            "Land cover and general geographic databases in the versioned "
            "store: the vector databases BDOT10k and BDOO (GUGiK, PL), "
            "CORINE Land Cover (Copernicus, EU), ZABAGED, Data50 and "
            "Data250 (CUZK, CZ)."
        ),
        products=_products,
        summary_pl=("Pokrycie terenu: BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250"),
        description_pl=(
            "Pokrycie terenu i bazy ogolnogeograficzne: wektorowe bazy "
            "BDOT10k i BDOO (GUGiK, PL), CORINE Land Cover (Copernicus, "
            "UE), ZABAGED, Data50 i Data250 (CUZK, CZ) w magazynie wersji."
        ),
    ),
)
