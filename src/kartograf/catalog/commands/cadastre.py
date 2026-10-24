"""``kartograf cadastre``: cadastral map - EGiB (GUGiK) and the CZ cadastral map
(CUZK) - and transaction prices RCN (GUGiK) (ADR-042 D9; plan E, E3)."""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param


def _content(products: Products) -> tuple[Param, ...]:
    def format_help() -> str:
        return (
            "Format paczki katastralniho uzemi (wymagany): "
            f"{choice_text(products(), 'format')}"
        )

    return (
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "cadastre",
    summary="Pobierz eksport jednostki albo dane obszaru",
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
    teryt="Kod TERYT: powiat (4 cyfry, np. 1261) - eksport EGiB (map) "
    "albo RCN (prices); wojewodztwo (2 cyfry, np. 12) - eksport RCN",
    ku="Kod katastralniho uzemi CZ (6 cyfr, np. 623164): paczka mapy "
    "katastralnej (--product map; wymaga --format)",
    examples=(
        Example(
            {"product": "map", "teryt": "1261"},
            title="Mapa ewidencyjna EGiB: eksport powiatu",
        ),
        Example(
            {"product": "map", "ku": "623164", "format": "SHP"},
            title="Mapa katastralna CZ: paczka katastralniho uzemi",
        ),
        Example(
            {"product": "prices", "teryt": "1201"},
            title="Ceny transakcyjne RCN: eksport powiatu",
        ),
    ),
    area_result="dzialki i budynki EGiB (GeoPackage), paczki uzemi CZ albo "
    "eksporty RCN powiatow obszaru",
    check="Porownaj lokalne wersje ze zrodlem bez pobierania: paczka "
    "mapy katastralnej CZ - naglowki HTTP (ETag/Last-Modified); eksporty "
    "GUGiK (EGiB, RCN) i obiekty obszaru nie maja taniego sygnalu (nie da sie "
    "sprawdzic bez pobrania), brakujace pliki = do pobrania",
    content=_content,
)

GROUPS = (
    collection_group(
        "cadastre",
        "Kataster i ceny: EGiB, RCN (PL), mapa katastralna (CZ)",
        "Mapa ewidencyjna EGiB i rejestr cen nieruchomosci RCN "
        "(GUGiK, PL) oraz mapa katastralna (CUZK, CZ) w magazynie wersji.",
    ),
)
