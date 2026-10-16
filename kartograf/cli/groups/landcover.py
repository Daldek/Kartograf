"""``kartograf landcover``: BDOT10k and BDOO (GUGiK), CORINE Land Cover,
ZABAGED, Data50 and Data250 (CUZK) (ADR-039, ADR-042 D15, ADR-043)."""

import argparse

from kartograf.cli._args import (
    OUTPUT_TITLE,
    SHEET_AREA_HELP,
    add_area_flags,
    add_quiet,
    add_update_flags,
    layer_codes,
)
from kartograf.cli.groups import add_group, add_list_sources
from kartograf.cli.landcover_cmd import (
    cmd_landcover_download,
    cmd_landcover_list_layers,
    landcover_task_arguments,
)
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_PRODUCT_CHOICES,
    LANDCOVER_PRODUCTS,
    bdoo_year_choices,
    bdot10k_archive_choices,
)
from kartograf.sources.descriptor import AtomFilesParams, SourceDescriptor
from kartograf.sources.registry import get_source


def _product_flag(source: SourceDescriptor) -> str:
    """``--product`` of a descriptor: the last part of its key (``bdot10k``)."""
    return f"--product {source.key.rsplit('.', 1)[-1]}"


def _national_file_crs() -> list[str]:
    """``--horizontal-crs`` values: the CRSs in which the national files of the
    land cover sources on the collection engines are published (the ATOM
    channels of the registry)."""
    return list(
        dict.fromkeys(
            crs
            for key in COLLECTION_SOURCES.values()
            for channel in get_source(key).channels
            if isinstance(channel.params, AtomFilesParams)
            for crs in channel.params.crs
        )
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``landcover download``, ``list-sources`` and ``list-layers``."""
    commands = add_group(
        subparsers,
        "landcover",
        help="Pokrycie terenu: BDOT10k, BDOO, CORINE, ZABAGED, Data50, Data250",
        description="Pokrycie terenu i bazy ogolnogeograficzne: wektorowe bazy "
        "BDOT10k i BDOO (GUGiK, PL), CORINE Land Cover (Copernicus, UE), "
        "ZABAGED, Data50 i Data250 (CUZK, CZ) w magazynie wersji.",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz dane wybranego produktu (--product)",
        description="Pobierz dane wybranego produktu (--product) dla jednego "
        "obszaru: --teryt, --sheet, --bbox albo --geometry. BDOT10k obszaru "
        "= paczki kazdego powiatu, ktory obszar przecina (PRG); z --year "
        "paczki z archiwum rocznikow BDOT10k (GML albo SHP, zapis 1:1). "
        "BDOO (--year wymagany): oryginalna paczka GML wojewodztwa (--teryt "
        "2 cyfry; obszar = paczki wojewodztw, ktore przecina, wg PRG); "
        "--layers zostawia pliki wybranych klas. ZABAGED, Data50 i Data250 "
        "(CZ): obszar (--bbox/--geometry) = jeden GeoPackage warstw uslugi w "
        "EPSG:5514 (ZABAGED: pokrycie terenu i wody, Data50/Data250: "
        "wszystkie warstwy obiektowe; nazwy CUZK, bez przeliczenia na kody "
        "BDOT10k; lista: landcover list-layers), --whole-country = plik "
        "krajowy z feedu ATOM CUZK (ZABAGED: GPKG, Data50/Data250: SHP; zapis "
        "1:1).",
    )

    selection = download.add_argument_group("Produkt i obszar")
    selection.add_argument(
        "--product",
        choices=LANDCOVER_PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {LANDCOVER_PRODUCT_CHOICES}",
    )
    selection.add_argument(
        "--teryt",
        metavar="KOD",
        help="Kod TERYT: powiat BDOT10k (4 cyfry, np. 1465) albo wojewodztwo "
        "BDOO (2 cyfry, np. 12)",
    )
    add_area_flags(
        selection,
        sheet_help=f"{SHEET_AREA_HELP}; BDOT10k: powiaty przecinajace arkusz, "
        "BDOO: wojewodztwa",
    )
    selection.add_argument(
        "--whole-country",
        action="store_true",
        help="Tylko ZABAGED, Data50 i Data250: plik krajowy zamiast obszaru "
        "(ZIP 1:1 - ZABAGED: GeoPackage pelnej bazy, kilka GB; Data50/Data250: "
        "Shapefile, 230-760 MB; wymaga --horizontal-crs); rozmiar z feedu w "
        "Warning przed pobraniem",
    )

    options = download.add_argument_group("Parametry produktu")
    options.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        default=None,
        help="Rok danych. CORINE (wymagany): wydanie (rok referencyjny) 2018, "
        "2012, 2006, 2000 (edycje pokrycia terenu CLMS/WMS), 1990 (tylko "
        "podglad WMS). BDOT10k: rocznik archiwum (stan z poczatku roku) "
        f"{bdot10k_archive_choices()} - oryginalna paczka powiatu ZIP; bez "
        f"--year biezace paczki. BDOO (wymagany): rocznik {bdoo_year_choices()} "
        "- oryginalna paczka wojewodztwa ZIP",
    )
    options.add_argument(
        "--format",
        "-f",
        type=str.upper,
        choices=["GPKG", "SHP", "GML"],
        default=None,
        help="Tylko BDOT10k: biezace paczki GPKG (GeoPackage, domyslnie) lub SHP "
        "(archiwum ZIP z plikami Shapefile); z --year (archiwum rocznikow) "
        "wymagany GML albo SHP",
    )
    options.add_argument(
        "--layers",
        metavar="KODY",
        type=layer_codes,
        default=None,
        help="Kody po przecinku (np. SWRS,PTWP); domyslnie wszystkie. Biezace "
        "BDOT10k GPKG: zostaw wybrane warstwy. BDOO: ZIP plikow wybranych "
        "klas z kazdej paczki (bez obiektow zlozonych, XSD i metadanych). "
        "Lista: landcover list-layers",
    )
    options.add_argument(
        "--keep-raw",
        action="store_true",
        help="Tylko biezace BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok "
        "pliku (wersja surowa w magazynie)",
    )
    options.add_argument(
        "--horizontal-crs",
        type=str.upper,
        choices=_national_file_crs(),
        default=None,
        help="Tylko --whole-country (ZABAGED, Data50, Data250; wymagany): "
        "uklad pliku krajowego; wynik obszaru zawsze w ukladzie uslugi "
        "EPSG:5514",
    )

    output = download.add_argument_group(OUTPUT_TITLE)
    output.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help="Wymagane: katalog magazynu; pliki trafiaja do "
        "<KATALOG>/landcover/... (wersje w versions/)",
    )
    add_update_flags(
        output,
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: CORINE "
        "(CLMS) i pliki krajowe ZABAGED, Data50, Data250 - wydanie zrodla; "
        "BDOT10k, BDOO, podglad CORINE i obszary CUZK - brak taniego sygnalu "
        "(nie da sie sprawdzic bez pobrania)",
        upgrade_help="Pobierz nowsze wydanie CORINE albo pliku krajowego CUZK "
        "(domyslnie tylko informacja); BDOT10k, BDOO, podglad CORINE i obszary "
        "CUZK zostaja lokalne (pobranie: --force); z --plan wykonaj zapisany "
        "plan",
        force_help="Pobierz ponownie kazdy plik (BDOT10k i BDOO: takze odswiez "
        "jednostki obszaru z PRG); ta sama tresc = bez zmian, inna = nowa wersja",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=1,
        help="Tylko obszar BDOT10k albo BDOO (wiele powiatow albo wojewodztw): "
        "liczba rownoleglych pobran (domyslnie 1)",
    )
    add_quiet(output)
    download.set_defaults(
        _handler=cmd_landcover_download, _task=landcover_task_arguments
    )

    add_list_sources(commands, "landcover", ("landcover",), _product_flag)

    layers = commands.add_parser(
        "list-layers",
        help="Wypisz warstwy wybranego produktu",
        description="Wypisz warstwy BDOT10k, ZABAGED, Data50 i Data250, klasy "
        "BDOO wg rocznikow albo lata CORINE (bez sieci)",
    )
    layers.add_argument(
        "--product",
        choices=LANDCOVER_PRODUCTS,
        default=None,
        help=f"Produkt (wymagany): {LANDCOVER_PRODUCT_CHOICES}",
    )
    layers.set_defaults(_handler=cmd_landcover_list_layers)
