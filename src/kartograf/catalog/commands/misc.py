"""Declare the commands outside the data groups.

``sheet parse`` and ``sheet find``, ``commands list``, ``commands schema`` and
``commands guide``, the ``cache`` group and the read access to the store
(``store overview``, ``store entries``, ``store sidecar``).
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
)
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000
from kartograf.core.sheet_parser import PL_BBOX_CRS, SheetParser


def _command_ids() -> list[str]:
    return [command.id for command in declared().commands]


def _guide_formats() -> tuple[str, ...]:
    from kartograf.guide import GUIDE_FORMATS  # it imports the catalog

    return GUIDE_FORMATS


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
        (
            "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 "
            "(`6.179.12.20`), SM5 (`CTES96`), TM33 tile (`302_5550`) or ZTM"
            " (`0510-D-11`, `NM-34-07-1-D-15`)."
        ),
        positional=True,
        required=True,
        metavar="GODLO",
        normalize="strip",
        description_pl=(
            "Godlo arkusza: PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. "
            "6.179.12.20), SM5 (np. CTES96), kafel TM33 (np. 302_5550) albo"
            " ZTM (np. 0510-D-11, NM-34-07-1-D-15)"
        ),
        examples=("N-34-130-D-d-2-4",),
    ),
    Param(
        "hierarchy",
        "flag",
        ("Add the hierarchy from the sheet up to the scale 1:1000000 (PL codes only)."),
        default=False,
        description_pl=(
            "Pokaz hierarchie od arkusza do skali 1:1000000 (tylko godla PL)"
        ),
    ),
    Param(
        "children",
        "flag",
        "Add the direct child sheets (PL codes only).",
        default=False,
        description_pl="Pokaz bezposrednie arkusze potomne (tylko godla PL)",
    ),
    Param(
        "descendants",
        "str",
        (
            "Add every descendant sheet down to this scale, for example "
            "`1:10000` (PL codes only)."
        ),
        metavar="SKALA",
        description_pl=(
            "Pokaz wszystkie arkusze potomne do skali docelowej (np. "
            "1:10000; tylko godla PL)"
        ),
    ),
    shared.JSON,
)

_SCHEMA_PARAMS = (
    Param(
        "command",
        "str",
        (
            "Command to describe (required): its name, such as `elevation "
            "download`, or its `operation_id`, such as "
            "`kartograf_elevation_download`."
        ),
        required=True,
        metavar="KOMENDA",
        allowed=_command_ids,
        description_pl=(
            "Komenda do opisania (wymagana): nazwa z katalogu (np. elevation "
            "download) albo jej operation_id (np. kartograf_elevation_download); "
            "lista: kartograf commands list"
        ),
        examples=("elevation download",),
    ),
    shared.JSON,
)

_GUIDE_PARAMS = (
    Param(
        "format",
        "str",
        (
            "Guide to render: `agents` is AGENTS.md, `llms` is llms.txt and "
            "`agents-md-block` is the compact block for the AGENTS.md of a "
            "repository that uses Kartograf."
        ),
        default="agents",
        allowed=_guide_formats,
        choices=True,
        metavar="RODZAJ",
        description_pl=(
            "Rodzaj przewodnika: agents (AGENTS.md), llms (llms.txt) albo "
            "agents-md-block (blok dla AGENTS.md projektu, ktory uzywa "
            "Kartografa); domyslnie agents"
        ),
    ),
    Param(
        "inject",
        "path",
        "File to put the block in (CLI only).",
        argument=None,
        path_role="output",
        metavar="PLIK",
        description_pl=(
            "Wstaw blok agents-md-block do pliku AGENTS.md projektu (zastepuje "
            "blok miedzy <!-- BEGIN kartograf --> a <!-- END kartograf -->, a "
            "bez bloku dopisuje go na koncu; wymaga --format agents-md-block)"
        ),
    ),
    shared.JSON,
)

_FIND_SHEETS_PARAMS = (
    Param(
        "bbox",
        "bbox",
        (
            "Area rectangle [min_x, min_y, max_x, max_y] in the CRS of "
            "`bbox_crs`; exactly one of `bbox` and `geometry`."
        ),
        metavar="BBOX",
        description_pl=(
            "Prostokat obszaru: min_x,min_y,max_x,max_y w ukladzie "
            "--bbox-crs (domyslnie EPSG:2180); dokladnie jeden z --bbox i "
            "--geometry"
        ),
    ),
    Param(
        "bbox_crs",
        "bbox_crs",
        ("CRS of `bbox`, required with it (the CLI defaults to EPSG:2180)."),
        allowed=lambda: PL_BBOX_CRS,
        choices=True,
        normalize="upper",
        cli_default="EPSG:2180",
        description_pl=_bbox_crs_help,
    ),
    Param(
        "geometry",
        "path",
        (
            "Vector file (SHP or GPKG): the sheets that intersect its "
            "features; exactly one of `bbox` and `geometry`."
        ),
        metavar="PLIK",
        description_pl=(
            "Plik geometrii (SHP albo GPKG): godla przecinajace obiekty "
            "pliku; dokladnie jeden z --bbox i --geometry"
        ),
        path_role="input",
    ),
    Param(
        "layer",
        "str",
        "GPKG layer of `geometry` (default: the first one).",
        metavar="NAZWA",
        description_pl="Warstwa GPKG pliku --geometry (domyslnie pierwsza)",
    ),
    Param(
        "scale",
        "str",
        (
            "Scale of the sheets (required): PL-1992 1:1000000 to 1:5000, "
            "PL-2000 1:10000 to 1:500."
        ),
        required=True,
        allowed=_scales,
        metavar="SKALA",
        description_pl=_scale_help,
    ),
    Param(
        "sheet_system",
        "str",
        "Sheet system (required): `1992` or `2000`.",
        required=True,
        allowed=lambda: SheetParser.VALID_SYSTEMS,
        choices=True,
        description_pl="Uklad godel (wymagany): 1992 (PL-1992) albo 2000 (PL-2000)",
    ),
    shared.JSON,
)

_OUTPUT_DIR = replace(
    shared.OUTPUT_DIR,
    description="Store directory (required): the one that holds the product segments.",
    description_pl="Katalog magazynu (wymagany): katalog z segmentami produktow",
    section=None,
)

_STORE_ENTRIES_PARAMS = (
    _OUTPUT_DIR,
    Param(
        "segment",
        "str",
        (
            "Segment of the store (required): the product directory, for "
            "example `nmt/pl_1992_1m_evrf2007`; `store overview` lists "
            "them."
        ),
        required=True,
        metavar="SEGMENT",
        description_pl=(
            "Segment magazynu (wymagany): katalog produktu, np. "
            "nmt/pl_1992_1m_evrf2007; lista: kartograf store overview"
        ),
    ),
    Param(
        "units",
        "str_list",
        (
            "Only these units of the segment: names as in `sidecar.unit` of"
            " an entry (not prefixes); the reserved names (`versions`, "
            "`full_sheet`, `kampanie`) are errors; default all."
        ),
        metavar="JEDNOSTKI",
        description_pl=(
            "Tylko te jednostki segmentu po przecinku: nazwy jak w "
            "sidecar.unit wpisu (nie prefiksy); nazwy zarezerwowane "
            "(versions, full_sheet, kampanie) to blad; domyslnie wszystkie"
        ),
    ),
    Param(
        "limit",
        "int",
        (
            "Most entries to return (at least 1, required); `truncated` in "
            "the result says whether more followed."
        ),
        required=True,
        metavar="N",
        description_pl=(
            "Najwyzej tyle wpisow (liczba >= 1, wymagana); truncated w "
            "wyniku mowi, czy byly dalsze"
        ),
        minimum=1,
    ),
    shared.JSON,
)

_STORE_SIDECAR_PARAMS = (
    Param(
        "path",
        "path",
        ("Data file of the store or its sidecar `<file>.meta.json` (required)."),
        required=True,
        metavar="PLIK",
        description_pl=(
            "Plik danych magazynu albo jego sidecar <plik>.meta.json (wymagany)"
        ),
        path_role="input",
    ),
    shared.JSON,
)

COMMANDS = (
    Command(
        "sheet parse",
        "Recognise a PL or CZ sheet code and show its properties",
        "query",
        "describe_sheet",
        "kartograf-sheet/1",
        _PARSE_PARAMS,
        description=(
            "Offline. PL-1992 and PL-2000 codes: scale, parts, CRS and "
            "hierarchy; CZ codes (SM5, TM33, ZTM): system, CRS and the "
            "commands that accept the code. To go from an area to sheet "
            "codes use `sheet find`."
        ),
        examples=(
            Example(
                {"sheet": "N-34-130-D-d-2-4"},
                title="A PL-1992 sheet code",
                title_pl="Godlo PL-1992",
            ),
            Example(
                {"sheet": "N-34-130-D", "descendants": "1:10000"},
                title="Descendant sheets down to 1:10000",
                title_pl="Arkusze potomne do skali 1:10000",
            ),
            Example(
                {"sheet": "6.179.12.20"},
                title="A PL-2000 sheet code",
                title_pl="Godlo PL-2000",
            ),
            Example(
                {"sheet": "CTES96"},
                title="A CZ code (SM5 sheet)",
                title_pl="Godlo CZ (arkusz SM5)",
            ),
        ),
        summary_pl="Rozpoznaj godlo arkusza (PL albo CZ) i pokaz jego wlasciwosci",
        description_pl=(
            "Rozpoznaj godlo arkusza i pokaz jego wlasciwosci (bez sieci): "
            "PL-1992 i PL-2000 - skala, czlony, uklad i hierarchia arkuszy;"
            " CZ - system (SM5, kafel TM33, ZTM), uklad wspolrzednych i "
            "komendy, ktore przyjmuja godlo w --sheet."
        ),
        rules=(),
        rules_pl=(),
        errors=("validation_error",),
        family="discovery",
    ),
    Command(
        "commands list",
        "List the commands with their groups, products and MCP families",
        "query",
        "list_commands",
        "kartograf-command-list/1",
        (shared.JSON,),
        description=(
            "Offline, read only: every group with its products and every "
            "command with its `operation_id`, summary, MCP families, whether "
            "it only reads and whether `check_updates` plans it. Start here; "
            "for the options of one command use `commands schema`."
        ),
        examples=(
            Example(
                {},
                title="The groups, products and commands",
                title_pl="Grupy, produkty i komendy",
            ),
            Example(
                {},
                title="The same as a JSON document",
                run={"json": True},
                title_pl="To samo jako dokument JSON",
            ),
        ),
        summary_pl="Wypisz komendy z grupami, produktami i rodzinami narzedzi MCP",
        description_pl=(
            "Przeglad katalogu komend (bez sieci i bez zapisu): grupy z "
            "produktami i komendy (nazwa, operation_id, podsumowanie, rodziny "
            "narzedzi MCP, czy tylko czyta i czy ma plan). --json: dokument "
            "kartograf-command-list/1. Opcje jednej komendy: kartograf commands "
            'schema --command "<grupa> <komenda>".'
        ),
        rules=(),
        rules_pl=(),
        errors=(),
        family="discovery",
        core=True,
        cardinality="bounded",
    ),
    Command(
        "commands schema",
        "Describe one command: its options, result, effects, rules and examples",
        "query",
        "command_schema",
        "kartograf-commands/1",
        _SCHEMA_PARAMS,
        description=(
            "Offline, read only: the schema of one command (`kartograf-"
            "commands/1`): each option with its type, bounds, allowed values "
            "and meanings and path role, the result document, effects, rules, "
            "examples with a result excerpt, error codes and the Polish texts. "
            "One command per call; the names are in `commands list`."
        ),
        examples=(
            Example(
                {"command": "elevation download"},
                title="The schema of a data command",
                title_pl="Schemat komendy danych",
            ),
            Example(
                {"command": "kartograf_soil_hsg"},
                title="The schema of a command by its operation id, as JSON",
                run={"json": True},
                title_pl="Schemat komendy wg operation_id, jako JSON",
            ),
        ),
        summary_pl="Opisz jedna komende: opcje, wynik, skutki, zasady i przyklady",
        description_pl=(
            "Schemat jednej komendy z katalogu (bez sieci i bez zapisu): opcje "
            "(rodzaj, zakresy, dozwolone wartosci ze znaczeniami, rola "
            "sciezki), dokument wyniku, skutki, zasady, przyklady z fragmentem "
            "wyniku i kody bledow. --json: dokument kartograf-commands/1 "
            "(opisy po angielsku, polskie teksty komendy w i18n.pl)."
        ),
        rules=(),
        rules_pl=(),
        errors=("validation_error",),
        family="discovery",
        core=True,
        cardinality="single",
    ),
    Command(
        "commands guide",
        "Render the guide for AI agents (AGENTS.md, llms.txt or its block)",
        "query",
        "agent_guide",
        "kartograf-guide/1",
        _GUIDE_PARAMS,
        description=(
            "Offline, read only: the English guide for AI agents generated from "
            "the catalog: `agents` is AGENTS.md, `llms` is llms.txt and "
            "`agents-md-block` is the compact block that `--inject FILE` puts "
            "into the AGENTS.md of a repository that uses Kartograf (CLI only). "
            "A large text: fetch it once per session."
        ),
        examples=(
            Example(
                {"format": "llms"},
                title="The llms.txt of Kartograf",
                title_pl="Plik llms.txt Kartografa",
            ),
            Example(
                {"format": "agents-md-block"},
                title="The compact block, as JSON",
                run={"json": True},
                title_pl="Zwarty blok, jako JSON",
            ),
        ),
        summary_pl="Wygeneruj przewodnik dla agentow AI (AGENTS.md, llms.txt, blok)",
        description_pl=(
            "Przewodnik dla agentow AI wygenerowany z katalogu (bez sieci i bez "
            "zapisu, po angielsku): agents to AGENTS.md, llms to llms.txt, "
            "agents-md-block to zwiezly blok, ktory --inject PLIK wstawia do "
            "AGENTS.md projektu korzystajacego z Kartografa. --json: dokument "
            "kartograf-guide/1."
        ),
        rules=("Fetch the guide once per session; `agents` is large.",),
        rules_pl=("Pobierz przewodnik raz na sesje; agents jest duzy.",),
        errors=("validation_error",),
        cardinality="single",
    ),
    Command(
        "cache stats",
        "Show the statistics of the metadata cache",
        "query",
        "get_cache_info",
        "kartograf-cache/1",
        (shared.JSON,),
        description=(
            "Offline, read only: the number of entries of the metadata "
            "cache by kind (records, campaigns, TERYT, sheets, ATOM feeds),"
            " the size and the path of the database."
        ),
        summary_pl="Pokaz statystyki cache (liczby wpisow, rozmiar bazy)",
        description_pl=(
            "Wypisz liczby wpisow cache metadanych wg rodzaju (rekordy, "
            "kampanie, TERYT, arkusze, feedy ATOM), rozmiar i sciezke bazy"
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "store_unavailable",
            "io_error",
        ),
        examples=(
            Example(
                {},
                title="The statistics of the metadata cache",
                title_pl="Statystyki cache metadanych",
            ),
        ),
    ),
    Command(
        "cache clear",
        "Delete every entry of the metadata cache",
        "manage",
        "clear_cache",
        "kartograf-cache/1",
        (shared.JSON,),
        description=(
            "Deletes every entry of the metadata cache (the next commands "
            "query the sources again); an unreadable database file is "
            "removed. The data files of the store stay."
        ),
        effects=("cache_delete",),
        destructive=True,
        summary_pl="Usun wszystkie wpisy cache",
        description_pl=(
            "Usun wszystkie wpisy cache metadanych (nastepne komendy "
            "odpytaja zrodla ponownie); nieczytelny plik bazy jest usuwany."
            " Pliki magazynu danych zostaja"
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "store_unavailable",
            "io_error",
        ),
        examples=(
            Example(
                {},
                title="Delete every cache entry",
                title_pl="Usun wszystkie wpisy cache",
            ),
        ),
    ),
    Command(
        "cache path",
        "Show the path of the metadata cache file",
        "query",
        "get_cache_path",
        "kartograf-cache/1",
        (shared.JSON,),
        description=(
            "Offline, read only: the path of the metadata cache file, "
            "without opening the database, so it works when the database is"
            " unreadable."
        ),
        summary_pl="Pokaz sciezke pliku bazy cache",
        description_pl=(
            "Wypisz sciezke pliku bazy cache metadanych (w biezacym "
            "katalogu) bez otwierania bazy: dziala tez, gdy baza jest "
            "nieczytelna"
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "io_error",
        ),
        examples=(
            Example(
                {}, title="The path of the cache file", title_pl="Sciezka pliku cache"
            ),
        ),
    ),
    Command(
        "sheet find",
        "List the PL sheet codes that cover an area",
        "query",
        "find_sheets",
        "kartograf-sheets/1",
        _FIND_SHEETS_PARAMS,
        description=(
            "Offline: the PL-1992 or PL-2000 sheet codes of the chosen "
            "scale that cover a `bbox` or intersect the features of a "
            "`geometry` file; the list is not truncated. To describe one "
            "code use `sheet parse`."
        ),
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
                title="PL-1992 1:10000 sheets for a rectangle",
                title_pl="Arkusze PL-1992 1:10000 dla prostokata",
            ),
            Example(
                {
                    "geometry": "zlewnia.gpkg",
                    "scale": "1:2000",
                    "sheet_system": "2000",
                },
                title="PL-2000 1:2000 sheets for a geometry",
                title_pl="Arkusze PL-2000 1:2000 dla geometrii",
            ),
        ),
        summary_pl="Wypisz godla arkuszy pokrywajace obszar (bbox albo geometria)",
        description_pl=(
            "Godla arkuszy PL-1992 albo PL-2000 w wybranej skali, ktore "
            "pokrywaja obszar: bbox (z bbox_crs) albo plik geometrii "
            "(arkusze przecinajace obiekty); skala i uklad godel sa "
            "wymagane. Bez sieci; wynik: lista godel w kolejnosci "
            "biblioteki, bez ucinania."
        ),
        rules=("`scale` and `sheet_system` are required: nothing is guessed.",),
        rules_pl=("`scale` i `sheet_system` sa wymagane: nic nie jest zgadywane.",),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="discovery",
        core=True,
        cardinality="unbounded",
    ),
    Command(
        "store overview",
        "List the segments of a store",
        "query",
        "describe_store",
        "kartograf-store-overview/1",
        (_OUTPUT_DIR, shared.JSON),
        description=(
            "Read only, offline: the segments (product directories) of the "
            "store with product, country, `dataset` key, name and whether a"
            " registered source produces them. For the files of one segment"
            " use `store entries`."
        ),
        examples=(
            Example(
                {},
                title="The segments of the store in ./data",
                title_pl="Segmenty magazynu w ./data",
            ),
        ),
        summary_pl="Wypisz segmenty magazynu danych (przeglad)",
        description_pl=(
            "Przeglad magazynu (tylko odczyt, bez sieci): segmenty "
            "(katalogi produktow) z produktem, krajem, kluczem zbioru, "
            "nazwa i znacznikiem, czy segment jest w rejestrze zrodel."
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="store",
        core=True,
        cardinality="bounded",
    ),
    Command(
        "store entries",
        ("List the entries of one store segment: version files with their sidecars"),
        "query",
        "list_store_entries",
        "kartograf-store-entries/1",
        _STORE_ENTRIES_PARAMS,
        description=(
            "Read only, offline: the first `limit` entries of a segment "
            "(version files and links, their sidecars without `raw`). "
            "`segment` and `limit` are required: a full scan is not an "
            "answer for a model. `truncated` says whether more entries "
            "followed."
        ),
        examples=(
            Example(
                {"segment": "nmt/pl_1992_1m_evrf2007", "limit": 20},
                title="The first 20 entries of a segment",
                title_pl="Pierwsze 20 wpisow segmentu",
            ),
            Example(
                {
                    "segment": "nmt/pl_1992_1m_evrf2007",
                    "limit": 5,
                    "units": ["N-34-130-D-d-2-4"],
                },
                title="The entries of one sheet",
                title_pl="Wpisy jednego arkusza",
            ),
        ),
        summary_pl="Wypisz wpisy segmentu magazynu: pliki wersji z sidecarami",
        description_pl=(
            "Pierwsze limit wpisow segmentu magazynu (tylko odczyt, bez "
            "sieci): pliki wersji z sidecarami bez pola raw; segment i "
            "limit sa wymagane, bo pelny skan magazynu nie jest "
            "odpowiedzia. truncated: byly dalsze wpisy; sidecar.unit wpisu "
            "jest wartoscia units tego samego segmentu."
        ),
        rules=(
            ("Take `segment` from `store overview` and `units` from `sidecar.unit`."),
        ),
        rules_pl=("Wez `segment` z `store overview`, a `units` z `sidecar.unit`.",),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="store",
        cardinality="bounded",
    ),
    Command(
        "store sidecar",
        "Read the sidecar of one store file (kartograf-meta/1)",
        "query",
        "read_store_sidecar",
        "kartograf-store-sidecar/1",
        _STORE_SIDECAR_PARAMS,
        description=(
            "Read only, offline: the sidecar of a store data file or of a "
            "`<file>.meta.json`, with the `raw` field. A missing or "
            "unreadable sidecar is the error `data_error` (reason "
            "`invalid_sidecar`)."
        ),
        examples=(
            Example(
                {"path": "./data/nmt/pl_1992_1m_evrf2007/N-34-130-D-d-2-4.asc"},
                title="The sidecar of a store file",
                title_pl="Sidecar pliku z magazynu",
            ),
        ),
        summary_pl="Odczytaj sidecar jednego pliku magazynu (kartograf-meta/1)",
        description_pl=(
            "Sidecar pliku danych magazynu albo pliku <plik>.meta.json "
            "(tylko odczyt, bez sieci), wraz z polem raw; brak albo "
            "nieczytelny sidecar to blad invalid_sidecar."
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "data_error",
            "io_error",
            "forbidden",
        ),
        family="store",
    ),
)

GROUPS = (
    Group(
        "cache",
        "Manage the metadata cache",
        (
            "The local SQLite cache of metadata (WMS answers, TERYT, the "
            "index of CUZK sheets); the data of the store are not part of "
            "it."
        ),
        position=2,
        summary_pl="Zarzadzaj cache metadanych",
        description_pl=(
            "Lokalny cache metadanych SQLite (odpowiedzi WMS, TERYT, indeks"
            " arkuszy CUZK) w pliku w biezacym katalogu; dane w magazynie "
            "(--output) nie sa czescia cache"
        ),
    ),
    Group(
        "commands",
        "Catalog of commands",
        (
            "The description of the commands of Kartograf for agents and "
            "scripts (offline, read only): the list of commands and the "
            "schema of one command."
        ),
        position=2,
        summary_pl="Katalog komend",
        description_pl=(
            "Opis komend Kartografa dla agentow i skryptow (bez sieci i bez"
            " zapisu): lista komend i schemat jednej komendy z opcjami, "
            "wynikiem, zasadami i przykladami."
        ),
    ),
    Group(
        "sheet",
        "Sheet codes",
        (
            "A PL-1992, PL-2000 or CZ (SM5, TM33, ZTM) sheet code and its "
            "properties, and the sheets that cover an area (offline)."
        ),
        summary_pl="Godla arkuszy",
        description_pl=(
            "Godlo arkusza PL-1992, PL-2000 albo CZ (SM5, TM33, ZTM) i jego"
            " wlasciwosci, bez sieci."
        ),
    ),
    Group(
        "store",
        "Read the store",
        (
            "Read access to the versioned store (read only, offline): its "
            "segments, the entries with their sidecars and the sidecar of "
            "one file."
        ),
        summary_pl="Odczyt magazynu",
        description_pl=(
            "Odczyt magazynu wersji (tylko odczyt, bez sieci): segmenty, "
            "wpisy z sidecarami i sidecar jednego pliku."
        ),
    ),
)
