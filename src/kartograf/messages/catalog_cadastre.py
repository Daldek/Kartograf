"""Messages of the command catalog: the declarations of ``cadastre``."""

from kartograf.messages import Text

MESSAGES = {
    "format_description": Text(
        "Format of a CZ cadastral-area package (required for `product=map` CZ): SHP, "
        "DXF, DGN or VFK.{choice_text:skip}",
        "Format paczki katastralniho uzemi (wymagany): {choice_text}",
    ),
    "download_summary": Text(
        "Download cadastral data: an EGiB or RCN export, or the data of an area",
        "Pobierz eksport jednostki albo dane obszaru",
    ),
    "download_description": Text(
        "`map`: EGiB (PL) county export or the parcels and buildings of an area "
        "(GeoPackage); the CZ cadastral map as a cadastral-area package (`ku`) or the "
        "areas of an area. `prices`: RCN (PL) county or voivodeship export, or the "
        "counties of an area (transaction layers). Never overwrites.",
        "Pobierz do magazynu wersji. --product map: EGiB (PL) - eksport powiatu "
        "(--teryt 4 cyfry; GeoPackage z warstwami dzialki, budynki i transakcje, "
        "odswiezany co dobe) albo dzialki i budynki przecinajace obszar z uslugi "
        "zbiorczej WFS (--bbox/--sheet/--geometry; jeden GeoPackage w EPSG:2180, "
        "powiaty bez integracji z usluga = luki, atrybuty zastrzezone = "
        "brak_uprawnien); mapa katastralna CZ - paczka katastralniho uzemi (--ku 6 "
        "cyfr) albo kazdego uzemi obszaru (--bbox/--geometry z --country cz; uzemi wg "
        "RUIAN) w formacie --format (SHP, DXF, DGN albo VFK; ZIP 1:1). --product "
        "prices (PL): eksport RCN powiatu (--teryt 4 cyfry) albo wojewodztwa (--teryt "
        "2 cyfry) albo kazdego powiatu obszaru - GeoPackage z warstwami "
        "transakcje_dzialki, transakcje_budynki, transakcje_lokale (EPSG:2180, "
        "odswiezany co dobe).",
    ),
    "teryt_description": Text(
        "TERYT code: county (4 digits, `1261`): the EGiB (`map`) or RCN (`prices`) "
        "export; voivodeship (2 digits, `12`): the RCN export.",
        "Kod TERYT: powiat (4 cyfry, np. 1261) - eksport EGiB (map) albo RCN "
        "(prices); wojewodztwo (2 cyfry, np. 12) - eksport RCN",
    ),
    "ku_description": Text(
        "CZ cadastral area code (6 digits, `623164`): the cadastral-map package "
        "(`product=map`; needs `format`).",
        "Kod katastralniho uzemi CZ (6 cyfr, np. 623164): paczka mapy katastralnej "
        "(--product map; wymaga --format)",
    ),
    "area_result_description": Text(
        "Downloads the EGiB parcels and buildings (GeoPackage), the CZ area packages "
        "or the RCN county exports of the area.",
        "dzialki i budynki EGiB (GeoPackage), paczki uzemi CZ albo eksporty RCN "
        "powiatow obszaru",
    ),
    "check_description": Text(
        "Cheap signal: the HTTP headers of the CZ cadastral-map package; GUGiK "
        "exports (EGiB, RCN) and area objects have none.",
        "Porownaj lokalne wersje ze zrodlem bez pobierania: paczka mapy katastralnej "
        "CZ - naglowki HTTP (ETag/Last-Modified); eksporty GUGiK (EGiB, RCN) i "
        "obiekty obszaru nie maja taniego sygnalu (nie da sie sprawdzic bez "
        "pobrania), brakujace pliki = do pobrania",
    ),
    "commands_rule": Text(
        "Use `teryt` for a PL export and `ku` for a CZ cadastral area.",
        "Uzyj `teryt` dla eksportu PL i `ku` dla uzemi katastralnego CZ.",
    ),
    "example_egib_cadastral_map_county_export": Text(
        "EGiB cadastral map: a county export",
        "Mapa ewidencyjna EGiB: eksport powiatu",
    ),
    "example_cz_cadastral_map_cadastral_area_package": Text(
        "CZ cadastral map: a cadastral-area package",
        "Mapa katastralna CZ: paczka katastralniho uzemi",
    ),
    "example_rcn_transaction_prices_county_export": Text(
        "RCN transaction prices: a county export",
        "Ceny transakcyjne RCN: eksport powiatu",
    ),
    "group_summary": Text(
        "Cadastre and prices: EGiB, RCN (PL), cadastral map (CZ)",
        "Kataster i ceny: EGiB, RCN (PL), mapa katastralna (CZ)",
    ),
    "group_description": Text(
        "The EGiB cadastral map and the RCN real-estate price register (GUGiK, PL) "
        "and the cadastral map (CUZK, CZ) in the versioned store.",
        "Mapa ewidencyjna EGiB i rejestr cen nieruchomosci RCN (GUGiK, PL) oraz mapa "
        "katastralna (CUZK, CZ) w magazynie wersji.",
    ),
}
