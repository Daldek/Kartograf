"""``kartograf geodesy``: survey control networks - PRPOG (GUGiK, PL) and
Bodove pole (CUZK, CZ) - and the quasi-geoid models PL-geoid2021 and
QGZU-2013 (plan E, E5)."""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param


def _content(products: Products) -> tuple[Param, ...]:
    def network_help() -> str:
        return (
            f"Siec osnowy (--product control; wymagana): "
            f"{choice_text(products(), 'network')}. Jedna "
            "wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ (--country auto) "
            "z roznymi: pl=SIEC,cz=SIEC (np. pl=horizontal,cz=gnss)"
        )

    return (
        Param(
            "network",
            "per_country",
            network_help,
            metavar="SIEC",
            allowed=lambda: choice_values(products(), "network"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "geodesy",
    summary="Pobierz punkty osnowy obszaru, paczke powiatu, archiwum arkusza "
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
    teryt="Kod TERYT powiatu (4 cyfry, np. 1201): paczka sieci "
    "poziomej albo wysokosciowej (--network horizontal|vertical)",
    examples=(
        Example(
            {"product": "control", "network": "horizontal", "teryt": "1201"},
            title="Osnowa pozioma PL: paczka powiatu",
        ),
        Example(
            {
                "product": "control",
                "country": "pl",
                "network": "vertical",
                "bbox": [560000, 240000, 575000, 250000],
                "bbox_crs": "EPSG:2180",
            },
            title="Osnowa wysokosciowa PL dla prostokata",
        ),
        Example(
            {"product": "geoid", "country": "cz", "whole_country": True},
            title="Quasi-geoida QGZU-2013 (CZ): plik krajowy",
        ),
    ),
    area_result="punkty sieci obszaru (GeoPackage) albo archiwa arkuszy "
    "1:100 000 obszaru",
    whole_country="Model quasi-geoidy kraju (--product geoid; wymaga "
    "--country pl albo cz); rozmiar z serwera w Warning przed pobraniem",
    check="Porownaj lokalne wersje ze zrodlem bez pobierania: QGZU "
    "(CZ) - data wydania w feedzie ATOM; punkty osnow, paczki, archiwa "
    "i PL-geoid2021 nie maja taniego sygnalu (nie da sie sprawdzic bez "
    "pobrania), brakujace pliki = do pobrania",
    content=_content,
)

GROUPS = (
    collection_group(
        "geodesy",
        "Osnowy geodezyjne i quasi-geoidy: PRPOG, PL-geoid2021 (PL), "
        "Bodove pole, QGZU (CZ)",
        "Punkty osnow geodezyjnych (GUGiK, CUZK) i modele "
        "quasi-geoidy PL-geoid2021 i QGZU-2013 w magazynie wersji.",
    ),
)
