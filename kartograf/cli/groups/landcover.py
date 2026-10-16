"""``kartograf landcover``: BDOT10k (GUGiK), CORINE Land Cover and ZABAGED
(CUZK) (ADR-039, ADR-042 D15)."""

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
    LANDCOVER_SOURCE_CHOICES,
    LANDCOVER_SOURCES,
    bdot10k_archive_choices,
)
from kartograf.sources.descriptor import AtomFilesParams, SourceDescriptor
from kartograf.sources.registry import get_source


def _source_flag(source: SourceDescriptor) -> str:
    """``--source`` of a descriptor: the last part of its key (``pl.gugik.bdot10k``)."""
    return f"--source {source.key.rsplit('.', 1)[-1]}"


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
        help="Pokrycie terenu: BDOT10k, CORINE Land Cover, ZABAGED",
        description="Pokrycie terenu: wektorowa baza BDOT10k (GUGiK, PL), CORINE "
        "Land Cover (Copernicus, UE) i ZABAGED (CUZK, CZ) w magazynie wersji.",
    )
    download = commands.add_parser(
        "download",
        help="Pobierz dane wybranego zrodla (--source)",
        description="Pobierz dane wybranego zrodla (--source) dla jednego "
        "obszaru: --teryt, --sheet, --bbox albo --geometry. BDOT10k obszaru "
        "= paczki kazdego powiatu, ktory obszar przecina (PRG); z --year "
        "paczki z archiwum rocznikow BDOT10k (GML albo SHP, zapis 1:1). "
        "ZABAGED (CZ): obszar (--bbox/--geometry) = jeden GeoPackage warstw "
        "pokrycia terenu i wod w EPSG:5514 (klasy ZABAGED, bez przeliczenia "
        "na kody BDOT10k; lista: landcover list-layers), --whole-country = "
        "plik krajowy GPKG z feedu ATOM CUZK (zapis 1:1).",
    )

    selection = download.add_argument_group("Zrodlo i obszar")
    selection.add_argument(
        "--source",
        "-s",
        choices=LANDCOVER_SOURCES,
        default=None,
        help=f"Zrodlo (wymagane): {LANDCOVER_SOURCE_CHOICES}",
    )
    selection.add_argument(
        "--teryt",
        metavar="KOD",
        help="Kod TERYT powiatu (4 cyfry, np. 1465; tylko BDOT10k)",
    )
    add_area_flags(
        selection,
        sheet_help=f"{SHEET_AREA_HELP}; BDOT10k: powiaty przecinajace arkusz",
    )
    selection.add_argument(
        "--whole-country",
        action="store_true",
        help="Tylko ZABAGED: plik krajowy zamiast obszaru (ZIP z GeoPackage "
        "pelnej bazy pod nazwami warstw CUZK, kilka GB; wymaga "
        "--horizontal-crs); rozmiar z feedu w Warning przed pobraniem",
    )

    options = download.add_argument_group("Parametry zrodla")
    options.add_argument(
        "--year",
        type=int,
        metavar="ROK",
        default=None,
        help="Rok danych. CORINE (wymagany): wydanie (rok referencyjny) 2018, "
        "2012, 2006, 2000 (edycje pokrycia terenu CLMS/WMS), 1990 (tylko "
        "podglad WMS). BDOT10k: rocznik archiwum (stan z poczatku roku) "
        f"{bdot10k_archive_choices()} - oryginalna paczka powiatu ZIP; bez "
        "--year biezace paczki",
    )
    options.add_argument(
        "--format",
        "-f",
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
        help="Tylko biezace BDOT10k GPKG: zostaw wybrane warstwy, kody po "
        "przecinku (np. SWRS,PTWP; lista: landcover list-layers); domyslnie "
        "wszystkie",
    )
    options.add_argument(
        "--keep-raw",
        action="store_true",
        help="Tylko biezace BDOT10k GPKG: zachowaj oryginalny ZIP GUGiK obok "
        "pliku (wersja surowa w magazynie)",
    )
    options.add_argument(
        "--horizontal-crs",
        choices=_national_file_crs(),
        default=None,
        help="Tylko ZABAGED z --whole-country (wymagany): uklad pliku krajowego; "
        "wynik obszaru zawsze w ukladzie uslugi EPSG:5514",
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
        "(CLMS) i plik krajowy ZABAGED - wydanie zrodla; BDOT10k, podglad "
        "CORINE i obszar ZABAGED - brak taniego sygnalu (nie da sie sprawdzic "
        "bez pobrania)",
        upgrade_help="Pobierz nowsze wydanie CORINE albo pliku krajowego ZABAGED "
        "(domyslnie tylko informacja); BDOT10k, podglad CORINE i obszar ZABAGED "
        "zostaja lokalne (pobranie: --force); z --plan wykonaj zapisany plan",
        force_help="Pobierz ponownie kazdy plik (BDOT10k: takze odswiez powiaty "
        "z PRG); ta sama tresc = bez zmian, inna = nowa wersja",
        plan_help="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    )
    output.add_argument(
        "--workers",
        "-w",
        type=int,
        metavar="N",
        default=1,
        help="Tylko BDOT10k obszaru (wiele powiatow): liczba rownoleglych "
        "pobran (domyslnie 1)",
    )
    add_quiet(output)
    download.set_defaults(
        _handler=cmd_landcover_download, _task=landcover_task_arguments
    )

    add_list_sources(commands, "landcover", ("landcover",), _source_flag)

    layers = commands.add_parser(
        "list-layers",
        help="Wypisz warstwy wybranego zrodla",
        description="Wypisz warstwy BDOT10k i ZABAGED albo lata CORINE (bez sieci)",
    )
    layers.add_argument(
        "--source",
        "-s",
        choices=LANDCOVER_SOURCES,
        default=None,
        help=f"Zrodlo (wymagane): {LANDCOVER_SOURCE_CHOICES}",
    )
    layers.set_defaults(_handler=cmd_landcover_list_layers)
