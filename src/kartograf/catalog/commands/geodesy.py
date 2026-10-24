"""Declare ``kartograf geodesy``.

Survey control networks - PRPOG (GUGiK, PL) and Bodove pole (CUZK, CZ) - and the
quasi-geoid models PL-geoid2021 and QGZU-2013 (plan E, E5).
"""

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
            (
                "Control network (required with `product=control`). One value "
                'applies to every country of the task, or give {"pl": '
                '"horizontal", "cz": "gnss"}.'
            ),
            metavar="SIEC",
            allowed=lambda: choice_values(products(), "network"),
            task=True,
            description_pl=network_help,
        ),
    )


COMMANDS = collection_commands(
    "geodesy",
    summary=(
        "Download control points, county packages, sheet archives or a quasi-geoid",
        (
            "Pobierz punkty osnowy obszaru, paczke powiatu, archiwum "
            "arkusza albo model quasi-geoidy"
        ),
    ),
    description=(
        "`control`: network points that cross an area (GeoPackage; PL "
        "EPSG:2180, CZ EPSG:5514), a county package of the horizontal "
        "or vertical network (`teryt`), or the archive catalogues of "
        "1:100000 sheets (`network` archive-*). `geoid`: the national "
        "quasi-geoid model, with `whole_country`. Files are stored as "
        "published; no model is applied.",
        (
            "Pobierz do magazynu wersji. --product control: punkty sieci "
            "--network przecinajace obszar (--bbox/--sheet/--geometry; "
            "GeoPackage w ukladzie uslugi: PL EPSG:2180, CZ EPSG:5514; siec"
            " CZ = suma jej warstw), paczka powiatu sieci horizontal albo "
            "vertical (--teryt 4 cyfry; wykazy wspolrzednych XLS i opisy "
            "topograficzne JPG) albo archiwalne katalogi punktow arkuszy "
            "1:100 000 obszaru (--network "
            "archive-1942|archive-kronsztadt60; skany PDF i TIFF). "
            "--product geoid: model quasi-geoidy, jeden plik krajowy "
            "(--whole-country --country pl: PL-geoid2021, TXT; --country "
            "cz: QGZU-2013, ZIP siatek TXT). Pliki zapisywane 1:1; "
            "Kartograf nie stosuje modeli do innych danych."
        ),
    ),
    teryt=(
        "TERYT code of a county (4 digits, `1201`): the package of the "
        "horizontal or vertical network (`network` horizontal or "
        "vertical).",
        (
            "Kod TERYT powiatu (4 cyfry, np. 1201): paczka sieci poziomej "
            "albo wysokosciowej (--network horizontal|vertical)"
        ),
    ),
    examples=(
        Example(
            {"product": "control", "network": "horizontal", "teryt": "1201"},
            title="PL horizontal control: a county package",
            title_pl="Osnowa pozioma PL: paczka powiatu",
        ),
        Example(
            {
                "product": "control",
                "country": "pl",
                "network": "vertical",
                "bbox": [560000, 240000, 575000, 250000],
                "bbox_crs": "EPSG:2180",
            },
            title="PL vertical control for a rectangle",
            title_pl="Osnowa wysokosciowa PL dla prostokata",
        ),
        Example(
            {"product": "geoid", "country": "cz", "whole_country": True},
            title="CZ quasi-geoid QGZU-2013: the national file",
            title_pl="Quasi-geoida QGZU-2013 (CZ): plik krajowy",
        ),
    ),
    area_result=(
        "Downloads the network points of the area (GeoPackage) or the "
        "archives of the 1:100000 sheets of the area.",
        ("punkty sieci obszaru (GeoPackage) albo archiwa arkuszy 1:100 000 obszaru"),
    ),
    whole_country=(
        "The national quasi-geoid model (`product=geoid`; needs "
        "`country` pl or cz). The size is in a notice before the "
        "download.",
        (
            "Model quasi-geoidy kraju (--product geoid; wymaga --country pl"
            " albo cz); rozmiar z serwera w Warning przed pobraniem"
        ),
    ),
    check=(
        "Signal: the release date of QGZU (CZ) in the ATOM feed; "
        "control points, packages, archives and PL-geoid2021 have none.",
        (
            "Porownaj lokalne wersje ze zrodlem bez pobierania: QGZU (CZ) -"
            " data wydania w feedzie ATOM; punkty osnow, paczki, archiwa i "
            "PL-geoid2021 nie maja taniego sygnalu (nie da sie sprawdzic "
            "bez pobrania), brakujace pliki = do pobrania"
        ),
    ),
    content=_content,
)

GROUPS = (
    collection_group(
        "geodesy",
        (
            "Geodetic control and quasi-geoids: PRPOG, PL-geoid2021 (PL), "
            "Bodove pole, QGZU (CZ)",
            (
                "Osnowy geodezyjne i quasi-geoidy: PRPOG, PL-geoid2021 (PL), "
                "Bodove pole, QGZU (CZ)"
            ),
        ),
        (
            "Points of geodetic control networks (GUGiK, CUZK) and the "
            "quasi-geoid models PL-geoid2021 and QGZU-2013 in the versioned"
            " store.",
            (
                "Punkty osnow geodezyjnych (GUGiK, CUZK) i modele quasi-geoidy "
                "PL-geoid2021 i QGZU-2013 w magazynie wersji."
            ),
        ),
    ),
)
