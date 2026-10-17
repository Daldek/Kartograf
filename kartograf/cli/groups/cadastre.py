"""``kartograf cadastre``: cadastral map - EGiB (GUGiK) and the CZ cadastral map
(CUZK) - and transaction prices RCN (GUGiK) (ADR-042 D9; plan E, E3)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_choice_values


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    formats = "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, "format").items()
    )
    content.add_argument(
        "--format",
        metavar="FORMAT",
        default=None,
        help=f"Format paczki katastralniho uzemi (wymagany): {formats}",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``cadastre download`` and ``cadastre list-sources``."""
    commands = add_group(
        subparsers,
        "cadastre",
        help="Kataster i ceny: EGiB, RCN (PL), mapa katastralna (CZ)",
        description="Mapa ewidencyjna EGiB i rejestr cen nieruchomosci RCN "
        "(GUGiK, PL) oraz mapa katastralna (CUZK, CZ) w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "cadastre",
        help="Pobierz eksport jednostki albo dane obszaru",
        description="Pobierz do magazynu wersji. --product map: EGiB (PL) - "
        "eksport powiatu (--teryt 4 cyfry; GeoPackage z warstwami dzialki, "
        "budynki i transakcje, odswiezany co dobe) albo dzialki i budynki "
        "przecinajace obszar z uslugi zbiorczej WFS (--bbox/--sheet/--geometry; "
        "jeden GeoPackage w EPSG:2180, powiaty bez integracji z usluga = luki, "
        "atrybuty zastrzezone = brak_uprawnien); mapa katastralna CZ - paczka "
        "katastralniho uzemi (--ku 6 cyfr) albo kazdego uzemi obszaru (--bbox/"
        "--geometry z --country cz; uzemi wg RUIAN) w formacie --format "
        "(SHP, DXF, DGN albo VFK; ZIP 1:1). --product prices (PL): eksport RCN "
        "powiatu (--teryt 4 cyfry) albo wojewodztwa (--teryt 2 cyfry) albo "
        "kazdego powiatu obszaru - GeoPackage z warstwami transakcje_dzialki, "
        "transakcje_budynki, transakcje_lokale (EPSG:2180, odswiezany co dobe).",
        teryt_help="Kod TERYT: powiat (4 cyfry, np. 1261) - eksport EGiB (map) "
        "albo RCN (prices); wojewodztwo (2 cyfry, np. 12) - eksport RCN",
        ku_help="Kod katastralniho uzemi CZ (6 cyfr, np. 623164): paczka mapy "
        "katastralnej (--product map; wymaga --format)",
        examples_of=(
            "kartograf cadastre download --product map --teryt 1261 -o ./data",
            "kartograf cadastre download --product map --ku 623164 --format SHP "
            "-o ./data",
            "kartograf cadastre download --product prices --teryt 1201 -o ./data",
        ),
        area_result="dzialki i budynki EGiB (GeoPackage), paczki uzemi CZ albo "
        "eksporty RCN powiatow obszaru",
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: paczka "
        "mapy katastralnej CZ - naglowki HTTP (ETag/Last-Modified); eksporty "
        "GUGiK (EGiB, RCN) i obiekty obszaru nie maja taniego sygnalu (nie da sie "
        "sprawdzic bez pobrania), brakujace pliki = do pobrania",
        content=_content,
    )
