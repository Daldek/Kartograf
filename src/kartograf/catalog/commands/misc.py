"""Declare the commands outside the data groups.

``sheet parse`` and ``sheet find``, ``commands list``, the ``cache`` group and the
read access to the store (``store overview``, ``store entries``, ``store sidecar``).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Group,
    Param,
    sorted_groups,
)
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000
from kartograf.core.sheet_parser import PL_BBOX_CRS, SheetParser


def _groups() -> list[str]:
    return [group.name for group in sorted_groups(declared().groups)]


def _command_ids() -> list[str]:
    return [command.id for command in declared().commands]


def _scales() -> list[str]:
    """Return the scales of the sheets of either PL sheet system, coarsest first."""
    return list(dict.fromkeys([*SheetParser.SCALE_HIERARCHY, *SCALE_HIERARCHY_2000]))


def _scale_help() -> str:
    return (
        "Skala arkuszy (wymagana): PL-1992 "
        f"{', '.join(SheetParser.SCALE_HIERARCHY)}; PL-2000 "
        f"{', '.join(SCALE_HIERARCHY_2000)}"
    )


def _bbox_crs_help() -> str:
    return f"Uklad wspolrzednych bbox (wymagany z bbox): {', '.join(PL_BBOX_CRS)}"


_PARSE_PARAMS = (
    Param(
        "sheet",
        "str",
        "Godlo arkusza: PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. "
        "6.179.12.20), SM5 (np. CTES96), kafel TM33 (np. 302_5550) albo ZTM "
        "(np. 0510-D-11, NM-34-07-1-D-15)",
        positional=True,
        required=True,
        metavar="GODLO",
        normalize="strip",
    ),
    Param(
        "hierarchy",
        "flag",
        "Pokaz hierarchie od arkusza do skali 1:1000000 (tylko godla PL)",
        default=False,
    ),
    Param(
        "children",
        "flag",
        "Pokaz bezposrednie arkusze potomne (tylko godla PL)",
        default=False,
    ),
    Param(
        "descendants",
        "str",
        "Pokaz wszystkie arkusze potomne do skali docelowej (np. 1:10000; "
        "tylko godla PL)",
        metavar="SKALA",
    ),
    shared.JSON,
)

_CATALOG_PARAMS = (
    Param(
        "group",
        "str",
        "Grupa komend, np. elevation albo project: opisy jej komend i produkty "
        "ze zrodlami (domyslnie przeglad wszystkich grup)",
        positional=True,
        nargs="?",
        metavar="GRUPA",
        allowed=_groups,
    ),
    Param(
        "command",
        "str",
        "Komenda do opisania: identyfikator w katalogu (elevation download, "
        "sheet parse, sheet find); w CLI po GRUPIE wystarczy nazwa komendy grupy "
        "(download)",
        positional=True,
        nargs="?",
        metavar="KOMENDA",
        allowed=_command_ids,
    ),
    Param(
        "params",
        "flag",
        "Dodaj parametry, ograniczenia i przyklady do widoku grupy albo calego "
        "katalogu (opis jednej komendy zawsze je ma; caly katalog z parametrami "
        "to ok. 200 tys. znakow)",
    ),
    Param(
        "tables",
        "flag",
        "Dodaj tabele: kody wyjscia CLI, kody bledow i schematy dokumentow "
        "(caly katalog z parametrami ma je zawsze)",
        flag=None,
    ),
    shared.JSON,
)

_FIND_SHEETS_PARAMS = (
    Param(
        "bbox",
        "bbox",
        "Prostokat obszaru: min_x,min_y,max_x,max_y w ukladzie --bbox-crs "
        "(domyslnie EPSG:2180); dokladnie jeden z --bbox i --geometry",
        metavar="BBOX",
    ),
    Param(
        "bbox_crs",
        "bbox_crs",
        _bbox_crs_help,
        allowed=lambda: PL_BBOX_CRS,
        choices=True,
        normalize="upper",
        cli_default="EPSG:2180",
    ),
    Param(
        "geometry",
        "path",
        "Plik geometrii (SHP albo GPKG): godla przecinajace obiekty pliku; "
        "dokladnie jeden z --bbox i --geometry",
        metavar="PLIK",
    ),
    Param(
        "layer",
        "str",
        "Warstwa GPKG pliku --geometry (domyslnie pierwsza)",
        metavar="NAZWA",
    ),
    Param(
        "scale",
        "str",
        _scale_help,
        required=True,
        allowed=_scales,
        metavar="SKALA",
    ),
    Param(
        "sheet_system",
        "str",
        "Uklad godel (wymagany): 1992 (PL-1992) albo 2000 (PL-2000)",
        required=True,
        allowed=lambda: SheetParser.VALID_SYSTEMS,
        choices=True,
    ),
    shared.JSON,
)

_OUTPUT_DIR = replace(
    shared.OUTPUT_DIR,
    description="Katalog magazynu (wymagany): katalog z segmentami produktow",
    section=None,
)

_STORE_ENTRIES_PARAMS = (
    _OUTPUT_DIR,
    Param(
        "segment",
        "str",
        "Segment magazynu (wymagany): katalog produktu, np. "
        "nmt/pl_1992_1m_evrf2007; lista: kartograf store overview",
        required=True,
        metavar="SEGMENT",
    ),
    Param(
        "units",
        "str_list",
        "Tylko te jednostki segmentu po przecinku: nazwy jak w sidecar.unit wpisu "
        "(nie prefiksy); nazwy zarezerwowane (versions, full_sheet, kampanie) to "
        "blad; domyslnie wszystkie",
        metavar="JEDNOSTKI",
    ),
    Param(
        "limit",
        "int",
        "Najwyzej tyle wpisow (liczba >= 1, wymagana); truncated w wyniku "
        "mowi, czy byly dalsze",
        required=True,
        metavar="N",
    ),
    shared.JSON,
)

_STORE_SIDECAR_PARAMS = (
    Param(
        "path",
        "path",
        "Plik danych magazynu albo jego sidecar <plik>.meta.json (wymagany)",
        required=True,
        metavar="PLIK",
    ),
    shared.JSON,
)

COMMANDS = (
    Command(
        "sheet parse",
        "Rozpoznaj godlo arkusza (PL albo CZ) i pokaz jego wlasciwosci",
        "query",
        "describe_sheet",
        "kartograf-sheet/1",
        _PARSE_PARAMS,
        description="Rozpoznaj godlo arkusza i pokaz jego wlasciwosci (bez "
        "sieci): PL-1992 i PL-2000 - skala, czlony, uklad i hierarchia arkuszy; "
        "CZ - system (SM5, kafel TM33, ZTM), uklad wspolrzednych i komendy, "
        "ktore przyjmuja godlo w --sheet.",
        tool="parse_sheet",
        examples=(
            Example({"sheet": "N-34-130-D-d-2-4"}, title="Godlo PL-1992"),
            Example(
                {"sheet": "N-34-130-D", "descendants": "1:10000"},
                title="Arkusze potomne do skali 1:10000",
            ),
            Example({"sheet": "6.179.12.20"}, title="Godlo PL-2000"),
            Example({"sheet": "CTES96"}, title="Godlo CZ (arkusz SM5)"),
        ),
    ),
    Command(
        "commands list",
        "Katalog komend: grupy, komendy i parametry",
        "query",
        "get_catalog",
        "kartograf-catalog/1",
        _CATALOG_PARAMS,
        description="Wypisz katalog komend (bez sieci i bez zapisu): grupy "
        "z produktami i komendami (jedna linia na komende: identyfikator, "
        "rodzaj, podsumowanie); z GRUPA komendy grupy; z GRUPA KOMENDA opis, "
        "parametry (flaga, argument API, rodzaj, wymagany, dozwolone wartosci, "
        "opis) i przyklady; --params dodaje parametry do widoku grupy i "
        "calosci. --json: dokument kartograf-catalog/1 - wejscie dla agentow "
        "i skryptow; bez GRUPY zwiezly przeglad (grupy, nazwy produktow, "
        "komendy: identyfikator, podsumowanie, narzedzie MCP, sprawdzenie "
        "aktualnosci), reszta z GRUPA, KOMENDA i --params; tabele kodow "
        "wyjscia i bledow oraz schematy dokumentow: tables=True w API albo "
        "caly katalog z parametrami.",
        tool="get_catalog",
        examples=(
            Example({}, title="Przeglad: grupy, produkty i komendy"),
            Example(
                {"group": "elevation"},
                title="Opis komendy: parametry, ograniczenia i przyklady",
                run={"command": "download"},
            ),
            Example(
                {"group": "soil", "params": True},
                title="Komendy grupy z parametrami",
            ),
            Example({}, title="Przeglad jako dokument JSON", run={"json": True}),
        ),
    ),
    Command(
        "cache stats",
        "Pokaz statystyki cache (liczby wpisow, rozmiar bazy)",
        "query",
        "get_cache_info",
        "kartograf-cache/1",
        (shared.JSON,),
        description="Wypisz liczby wpisow cache metadanych wg rodzaju (rekordy, "
        "kampanie, TERYT, arkusze, feedy ATOM), rozmiar i sciezke bazy",
    ),
    Command(
        "cache clear",
        "Usun wszystkie wpisy cache",
        "manage",
        "clear_cache",
        "kartograf-cache/1",
        (shared.JSON,),
        description="Usun wszystkie wpisy cache metadanych (nastepne komendy "
        "odpytaja zrodla ponownie); nieczytelny plik bazy jest usuwany. Pliki "
        "magazynu danych zostaja",
        effects=("cache_delete",),
        destructive=True,
    ),
    Command(
        "cache path",
        "Pokaz sciezke pliku bazy cache",
        "query",
        "get_cache_path",
        "kartograf-cache/1",
        (shared.JSON,),
        description="Wypisz sciezke pliku bazy cache metadanych (w biezacym "
        "katalogu) bez otwierania bazy: dziala tez, gdy baza jest nieczytelna",
    ),
    Command(
        "sheet find",
        "Wypisz godla arkuszy pokrywajace obszar (bbox albo geometria)",
        "query",
        "find_sheets",
        "kartograf-sheets/1",
        _FIND_SHEETS_PARAMS,
        description="Godla arkuszy PL-1992 albo PL-2000 w wybranej skali, "
        "ktore pokrywaja obszar: bbox (z bbox_crs) albo plik geometrii "
        "(arkusze przecinajace obiekty); skala i uklad godel sa wymagane. "
        "Bez sieci; wynik: lista godel w kolejnosci biblioteki, bez ucinania.",
        tool="find_sheets",
        constraints=(
            Constraint(
                "one_of",
                ("bbox", "geometry"),
                "Podaj dokladnie jeden obszar: bbox albo geometry",
            ),
            Constraint(
                "requires",
                ("geometry",),
                "layer dotyczy tylko geometry (warstwa pliku GPKG z obszarem)",
                "layer",
            ),
        ),
        examples=(
            Example(
                {
                    "bbox": [565000, 242000, 566000, 243000],
                    "bbox_crs": "EPSG:2180",
                    "scale": "1:10000",
                    "sheet_system": "1992",
                },
                title="Arkusze PL-1992 1:10000 dla prostokata",
            ),
            Example(
                {
                    "geometry": "zlewnia.gpkg",
                    "scale": "1:2000",
                    "sheet_system": "2000",
                },
                title="Arkusze PL-2000 1:2000 dla geometrii",
            ),
        ),
    ),
    Command(
        "store overview",
        "Wypisz segmenty magazynu danych (przeglad)",
        "query",
        "describe_store",
        "kartograf-store-overview/1",
        (_OUTPUT_DIR, shared.JSON),
        description="Przeglad magazynu (tylko odczyt, bez sieci): segmenty "
        "(katalogi produktow) z produktem, krajem, kluczem zbioru, nazwa i "
        "znacznikiem, czy segment jest w rejestrze zrodel.",
        tool="store_overview",
        examples=(Example({}, title="Segmenty magazynu w ./data"),),
    ),
    Command(
        "store entries",
        "Wypisz wpisy segmentu magazynu: pliki wersji z sidecarami",
        "query",
        "list_store_entries",
        "kartograf-store-entries/1",
        _STORE_ENTRIES_PARAMS,
        description="Pierwsze limit wpisow segmentu magazynu (tylko odczyt, "
        "bez sieci): pliki wersji z sidecarami bez pola raw; segment i limit "
        "sa wymagane, bo pelny skan magazynu nie jest odpowiedzia. "
        "truncated: byly dalsze wpisy; sidecar.unit wpisu jest wartoscia "
        "units tego samego segmentu.",
        tool="store_entries",
        examples=(
            Example(
                {"segment": "nmt/pl_1992_1m_evrf2007", "limit": 20},
                title="Pierwsze 20 wpisow segmentu",
            ),
            Example(
                {
                    "segment": "nmt/pl_1992_1m_evrf2007",
                    "limit": 5,
                    "units": ["N-34-130-D-d-2-4"],
                },
                title="Wpisy jednego arkusza",
            ),
        ),
    ),
    Command(
        "store sidecar",
        "Odczytaj sidecar jednego pliku magazynu (kartograf-meta/1)",
        "query",
        "read_store_sidecar",
        "kartograf-store-sidecar/1",
        _STORE_SIDECAR_PARAMS,
        description="Sidecar pliku danych magazynu albo pliku <plik>.meta.json "
        "(tylko odczyt, bez sieci), wraz z polem raw; brak albo nieczytelny "
        "sidecar to blad invalid_sidecar.",
        tool="store_sidecar",
        examples=(
            Example(
                {"path": "./data/nmt/pl_1992_1m_evrf2007/N-34-130-D-d-2-4.asc"},
                title="Sidecar pliku z magazynu",
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "cache",
        "Zarzadzaj cache metadanych",
        "Lokalny cache metadanych SQLite (odpowiedzi WMS, TERYT, indeks "
        "arkuszy CUZK) w pliku w biezacym katalogu; dane w magazynie "
        "(--output) nie sa czescia cache",
        position=2,
    ),
    Group(
        "commands",
        "Katalog komend",
        "Opis komend Kartografa dla agentow i skryptow (bez sieci i bez zapisu): "
        "przeglad komend, a po nazwie komendy jej parametry, ograniczenia i "
        "przyklady.",
        position=2,
    ),
    Group(
        "sheet",
        "Godla arkuszy",
        "Godlo arkusza PL-1992, PL-2000 albo CZ (SM5, TM33, ZTM) i jego "
        "wlasciwosci, bez sieci.",
    ),
    Group(
        "store",
        "Odczyt magazynu",
        "Odczyt magazynu wersji (tylko odczyt, bez sieci): segmenty, wpisy "
        "z sidecarami i sidecar jednego pliku.",
    ),
)
