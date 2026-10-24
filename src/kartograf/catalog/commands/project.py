"""``kartograf project``: manage tasks and pinned store versions (ADR-040)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import Command, Example, Group, Param

# The help of the project commands has no sections (a flat list of flags).
_PROJECT_DIR = Param(
    "project_dir",
    "path",
    "Katalog projektu (domyslnie biezacy katalog)",
    flag="--project",
    dest="project",
    metavar="KATALOG",
    cli_default=".",
    required=True,
)
_QUIET = replace(shared.QUIET, section=None)
_NAME = Param(
    "name",
    "str",
    "Nazwa zadania",
    positional=True,
    required=True,
    metavar="NAZWA",
)
_TASKS = Param(
    "tasks",
    "str_list",
    "Wybrane zadania (domyslnie wszystkie)",
    positional=True,
    nargs="*",
    metavar="NAZWA",
)
_STATE = "kartograf-project-state/1"
_CHECK = "kartograf-project-check/1"


def _data_commands() -> list[str]:
    """Return the ids of the data commands a task can run.

    In the order of ``COMMANDS``.
    """
    return [command.id for command in declared().commands if command.project_task]


def _flat(params: tuple[Param, ...]) -> tuple[Param, ...]:
    return tuple(replace(param, section=None) for param in params)


_INIT_PARAMS = (
    _PROJECT_DIR,
    replace(
        shared.OUTPUT_DIR,
        description="Katalog magazynu projektu (wymagany; bez domyslnej sciezki)",
        section=None,
    ),
    shared.JSON,
)

_ADD_PARAMS = (
    _PROJECT_DIR,
    replace(_NAME, description="Unikalna nazwa zadania"),
    Param(
        "arguments",
        "str_list",
        "Komenda danych i jej opcje, np. elevation download --product nmt ...",
        positional=True,
        nargs="REMAINDER",
        argument=None,
        metavar="<grupa> <komenda> [opcje]",
    ),
    Param(
        "command",
        "str",
        "Komenda danych zadania (wymagana): jedna z komend z project_task w "
        "katalogu; w CLI to pierwsze slowa po NAZWA",
        flag=None,
        required=True,
        allowed=_data_commands,
    ),
    Param(
        "options",
        "options",
        "Opcje zadania (wymagane): obiekt z opcjami komendy danych bez "
        'output_dir, np. {"product": "nmt", "sheet": "N-34-130-D-d-2-4"}; '
        "parametry z task=true podaje get_catalog z command=; w CLI to "
        "opcje po komendzie",
        flag=None,
        required=True,
    ),
    shared.JSON,
)

_REMOVE_PARAMS = (_PROJECT_DIR, _NAME, shared.JSON)

_UPDATE = tuple(
    replace(
        param,
        description="Tryb aktualizacji (pominiety: zadanie niepobrane jest "
        "pobierane i przypinane, pobrane zostaje bez zmian): upgrade albo "
        "force przepina cale zadanie",
    )
    if param.name == "update"
    else param
    for param in _flat(
        shared.update_params(
            check="Sprawdz zrodla bez pobierania i bez zmiany przypiec",
            upgrade="Pobierz nowsze wersje i przepnij cale zadania",
            force="Pobierz ponownie i przepnij cale zadania",
        )
    )
)

_DOWNLOAD_PARAMS = (
    _PROJECT_DIR,
    *_UPDATE,
    _QUIET,
    replace(
        shared.workers(
            "Rownolegle pobieranie plikow w kazdym zadaniu (domyslnie jak "
            "w komendzie danych: elevation i imagery 4, pozostale 1; soil hsg "
            "bez rownoleglosci)",
            None,
        ),
        section=None,
    ),
    _TASKS,
    shared.JSON,
)

_INSPECT_PARAMS = (_PROJECT_DIR, _QUIET, _TASKS, shared.JSON)

COMMANDS = (
    Command(
        "project init",
        "Utworz manifest projektu i magazyn",
        "manage",
        "init_project",
        _STATE,
        _INIT_PARAMS,
        description="Utworz manifest projektu (kartograf-project.json "
        "w katalogu --project) wskazujacy magazyn --output; tworzy katalogi, "
        "ktorych nie ma. Jeden projekt = jeden magazyn; wiele projektow moze "
        "dzielic magazyn.",
        effects=("store_write", "project_write"),
        tool="project_init",
        examples=(Example({}, title="Nowy projekt z magazynem w ./data"),),
    ),
    Command(
        "project add",
        "Dodaj zadanie z komendy danych (bez pobierania)",
        "manage",
        "add_project_task",
        _STATE,
        _ADD_PARAMS,
        description="Dodaj zadanie: NAZWA <grupa> <komenda> [opcje komendy]. "
        "--project podaj przed NAZWA; opcje po NAZWA naleza do komendy danych "
        "(bez --output i trybow aktualizacji). Wybory sprawdzane bez sieci, "
        "nic nie jest pobierane.",
        effects=("project_write",),
        idempotent=False,
        tool="project_add",
        examples=(
            Example(
                {"name": "teren"},
                title="Zadanie NMT dla arkusza PL",
                run={
                    "arguments": [
                        "elevation",
                        "download",
                        "--product",
                        "nmt",
                        "--sheet",
                        "N-34-130-D-d-2-4",
                        "--resolution",
                        "1m",
                        "--vertical-crs",
                        "EVRF2007",
                    ]
                },
            ),
            Example(
                {"name": "gleby"},
                title="Zadanie HSG dla arkusza PL",
                run={
                    "arguments": [
                        "soil",
                        "hsg",
                        "--sheet",
                        "N-34-130-D",
                        "--depth",
                        "0-5cm",
                    ]
                },
            ),
        ),
    ),
    Command(
        "project remove",
        "Usun zadanie (nie pliki magazynu)",
        "manage",
        "remove_project_task",
        _STATE,
        _REMOVE_PARAMS,
        description="Usun zadanie i jego przypiecia z manifestu; pliki "
        "w magazynie zostaja.",
        effects=("project_write",),
        idempotent=False,
        destructive=True,
        tool="project_remove",
    ),
    Command(
        "project download",
        "Pobierz, odtworz lub zaktualizuj zadania projektu",
        "data",
        "download_project",
        "kartograf-project-report/1",
        _DOWNLOAD_PARAMS,
        description="Pobierz zadania projektu do magazynu i przypnij ich pliki "
        "(SHA-256). Zadanie z obecnymi przypietymi plikami zostaje bez zmian i "
        "bez zapytan do zrodla; brakujace pliki sa odtwarzane tylko przy "
        "zgodnej SHA-256. Zmiana przypiec: --upgrade albo --force.",
        effects=("network", "store_write", "project_write"),
        check_function="check_project",
        check_result_schema=_CHECK,
        tool="project_download",
        examples=(
            Example({}, title="Pobierz zadania, ktorych jeszcze nie ma"),
            Example(
                {},
                title="Sprawdz aktualnosc zrodel bez pobierania",
                run={"check_updates": True},
            ),
            Example(
                {"tasks": ["teren"]},
                title="Przepnij zadanie na nowsze wersje",
                run={"upgrade": True},
            ),
        ),
    ),
    Command(
        "project status",
        "Sprawdz obecnosc i rozmiar przypietych plikow",
        "query",
        "get_project_status",
        _CHECK,
        _INSPECT_PARAMS,
        description="Sprawdz bez sieci, czy przypiete pliki zadan sa w magazynie "
        "i maja przypiety rozmiar (szybko, bez czytania tresci); manifest bez "
        "zmian. Kod 1, gdy ktores zadanie nie jest pobrane albo brakuje "
        "przypietego pliku.",
        tool="project_status",
    ),
    Command(
        "project verify",
        "Sprawdz SHA-256 i sidecary przypietych plikow",
        "query",
        "verify_project",
        _CHECK,
        _INSPECT_PARAMS,
        description="Sprawdz bez sieci tresc przypietych plikow: czyta cale pliki "
        "i porownuje SHA-256 oraz sidecary wersji; manifest bez "
        "zmian. Kod 1 przy niezgodnosci.",
        tool="project_verify",
    ),
)

GROUPS = (
    Group(
        "project",
        "Projekt: zadania i przypiete wersje plikow w magazynie",
        "Manifest projektu: zadania pobrania i przypiete wersje danych "
        "w jednym magazynie.",
    ),
)
