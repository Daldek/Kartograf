"""``kartograf geodesy``: survey control networks - PRPOG (GUGiK, PL) and
Bodove pole (CUZK, CZ) - and the quasi-geoid models PL-geoid2021 and
QGZU-2013 (plan E, E5)."""

import argparse

from kartograf.cli.groups import add_group
from kartograf.cli.groups._collection import add_collection_commands
from kartograf.download.collections import collection_choice_values


def _content(content: argparse._ArgumentGroup, products: tuple[str, ...]) -> None:
    networks = "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, "network").items()
    )
    content.add_argument(
        "--network",
        metavar="SIEC",
        default=None,
        help=f"Siec osnowy (--product control; wymagana): {networks}. Jedna "
        "wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ (--country auto) "
        "z roznymi: pl=SIEC,cz=SIEC (np. pl=horizontal,cz=gnss)",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """``geodesy download`` and ``geodesy list-sources``."""
    commands = add_group(
        subparsers,
        "geodesy",
        help="Osnowy geodezyjne i quasi-geoidy: PRPOG, PL-geoid2021 (PL), "
        "Bodove pole, QGZU (CZ)",
        description="Punkty osnow geodezyjnych (GUGiK, CUZK) i modele "
        "quasi-geoidy PL-geoid2021 i QGZU-2013 w magazynie wersji.",
    )
    add_collection_commands(
        commands,
        "geodesy",
        help="Pobierz punkty osnowy obszaru, paczke powiatu, archiwum arkusza "
        "albo model quasi-geoidy",
        description="Pobierz do magazynu wersji. --product control: punkty sieci "
        "--network przecinajace obszar (--bbox/--sheet/--geometry; GeoPackage "
        "w ukladzie uslugi: PL EPSG:2180, CZ EPSG:5514; siec CZ = suma jej "
        "warstw), paczka powiatu sieci horizontal albo vertical (--teryt 4 "
        "cyfry; wykazy wspolrzednych XLS i opisy topograficzne JPG) albo "
        "archiwalne katalogi punktow arkuszy 1:100 000 obszaru (--network "
        "archive-1942|archive-kronsztadt60; skany PDF i TIFF). --product geoid: "
        "model quasi-geoidy, jeden plik krajowy (--whole-country --country pl: "
        "PL-geoid2021, TXT; --country cz: QGZU-2013, ZIP siatek TXT). Pliki "
        "zapisywane 1:1; Kartograf nie stosuje modeli do innych danych.",
        teryt_help="Kod TERYT powiatu (4 cyfry, np. 1201): paczka sieci "
        "poziomej albo wysokosciowej (--network horizontal|vertical)",
        examples_of=(
            "kartograf geodesy download --product control --network horizontal "
            "--teryt 1201 -o ./data",
            "kartograf geodesy download --product control --country pl --network "
            "vertical --bbox 560000,240000,575000,250000 -o ./data",
            "kartograf geodesy download --product geoid --country cz "
            "--whole-country -o ./data",
        ),
        area_result="punkty sieci obszaru (GeoPackage) albo archiwa arkuszy "
        "1:100 000 obszaru",
        whole_country_help="Model quasi-geoidy kraju (--product geoid; wymaga "
        "--country pl albo cz); rozmiar z serwera w Warning przed pobraniem",
        check_help="Porownaj lokalne wersje ze zrodlem bez pobierania: QGZU "
        "(CZ) - data wydania w feedzie ATOM; punkty osnow, paczki, archiwa "
        "i PL-geoid2021 nie maja taniego sygnalu (nie da sie sprawdzic bez "
        "pobrania), brakujace pliki = do pobrania",
        content=_content,
    )
