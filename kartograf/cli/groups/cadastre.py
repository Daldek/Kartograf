"""``kartograf cadastre``: cadastral map - EGiB (GUGiK) (ADR-042 D9)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands


def register(subparsers: argparse._SubParsersAction) -> None:
    """``cadastre download`` and ``cadastre list-sources``."""
    commands = add_group(
        subparsers,
        "cadastre",
        help="Ewidencja gruntow i budynkow: EGiB",
        description="Mapa ewidencyjna EGiB (GUGiK, PL) w magazynie wersji: "
        "dzialki i budynki.",
    )
    add_collection_commands(
        commands,
        "cadastre",
        help="Pobierz eksport powiatu albo dzialki i budynki obszaru",
        description="Pobierz EGiB do magazynu wersji: eksport powiatu (--teryt "
        "4 cyfry; GeoPackage z warstwami dzialki, budynki i transakcje, "
        "odswiezany co dobe) albo dzialki i budynki przecinajace obszar "
        "z uslugi zbiorczej WFS (--bbox/--sheet/--geometry; jeden GeoPackage "
        "w EPSG:2180, powiaty bez integracji z usluga = luki, atrybuty "
        "zastrzezone = brak_uprawnien).",
        teryt_help="Kod TERYT powiatu (4 cyfry, np. 1261): eksport EGiB powiatu",
        area_result="dzialki i budynki przecinajace obszar (GeoPackage)",
    )
