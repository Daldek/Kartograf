"""``kartograf project``: manage tasks and pinned store versions (ADR-040)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import Command, Example, Group, Param

# The help of the project commands has no sections (a flat list of flags).
_PROJECT_DIR = Param(
    "project_dir",
    "path",
    (
        "Project directory (the one with `kartograf-project.json`); in "
        "the CLI the current directory by default."
    ),
    flag="--project",
    dest="project",
    metavar="KATALOG",
    cli_default=".",
    required=True,
    description_pl="Katalog projektu (domyslnie biezacy katalog)",
    path_role="input",
)
# The commands that write the manifest write into the project directory.
_PROJECT_DIR_WRITTEN = replace(_PROJECT_DIR, path_role="output")
_QUIET = replace(shared.QUIET, section=None)
_NAME = Param(
    "name",
    "str",
    "Name of the task.",
    positional=True,
    required=True,
    metavar="NAZWA",
    description_pl="Nazwa zadania",
)
_TASKS = Param(
    "tasks",
    "str_list",
    "Only these tasks; default all.",
    positional=True,
    nargs="*",
    metavar="NAZWA",
    description_pl="Wybrane zadania (domyslnie wszystkie)",
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
    _PROJECT_DIR_WRITTEN,
    replace(
        shared.OUTPUT_DIR,
        description="Store directory of the project (required): there is no default.",
        description_pl="Katalog magazynu projektu (wymagany; bez domyslnej sciezki)",
        section=None,
    ),
    shared.JSON,
)

_ADD_PARAMS = (
    _PROJECT_DIR_WRITTEN,
    replace(
        _NAME,
        description="Unique name of the task.",
        description_pl="Unikalna nazwa zadania",
    ),
    Param(
        "arguments",
        "str_list",
        positional=True,
        nargs="REMAINDER",
        argument=None,
        metavar="<grupa> <komenda> [opcje]",
        description_pl=(
            "Komenda danych i jej opcje, np. elevation download --product nmt ..."
        ),
    ),
    Param(
        "command",
        "str",
        (
            "Data command of the task (required): one of the commands a "
            "project task may run."
        ),
        flag=None,
        required=True,
        allowed=_data_commands,
        description_pl=(
            "Komenda danych zadania (wymagana): jedna z komend z "
            "project_task w katalogu; w CLI to pierwsze slowa po NAZWA"
        ),
    ),
    Param(
        "options",
        "options",
        (
            "Options of the task (required): an object with the options of "
            'the data command without `output_dir`, for example {"product":'
            ' "nmt", "sheet": "N-34-130-D-d-2-4"}; `commands schema` lists '
            "them."
        ),
        flag=None,
        required=True,
        description_pl=(
            "Opcje zadania (wymagane): obiekt z opcjami komendy danych bez "
            'output_dir, np. {"product": "nmt", "sheet": '
            '"N-34-130-D-d-2-4"}; opcje komendy podaje commands schema; '
            "w CLI to opcje po komendzie"
        ),
    ),
    shared.JSON,
)

_REMOVE_PARAMS = (_PROJECT_DIR_WRITTEN, _NAME, shared.JSON)

_UPDATE = tuple(
    replace(
        param,
        description="Update mode. Omitted: a task that is not fetched is fetched "
        "and pinned, a fetched one stays as it is. upgrade or force re-pins the "
        "whole task. CLI: --upgrade, --force.",
        description_pl="Tryb aktualizacji (pominiety: zadanie niepobrane jest "
        "pobierane i przypinane, pobrane zostaje bez zmian): upgrade albo "
        "force przepina cale zadanie",
    )
    if param.name == "update"
    else param
    for param in _flat(
        shared.update_params(
            check=(
                "The pins stay unchanged.",
                "Sprawdz zrodla bez pobierania i bez zmiany przypiec",
            ),
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
            (
                "Parallel transfers inside each task (default as in the data "
                "command: 4 for elevation and imagery, 1 for the rest; none for"
                " `soil hsg`).",
                (
                    "Rownolegle pobieranie plikow w kazdym zadaniu (domyslnie jak w"
                    " komendzie danych: elevation i imagery 4, pozostale 1; soil "
                    "hsg bez rownoleglosci)"
                ),
            ),
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
        "Create a project manifest and its store",
        "manage",
        "init_project",
        _STATE,
        _INIT_PARAMS,
        description=(
            "Creates `kartograf-project.json` in `project_dir` and points "
            "it at the store `output_dir`; missing directories are created."
            " One project has one store; several projects may share it. Add"
            " tasks with `project add`."
        ),
        effects=("store_write", "project_write"),
        tool="project_init",
        examples=(
            Example(
                {},
                title="A new project with the store in ./data",
                title_pl="Nowy projekt z magazynem w ./data",
            ),
        ),
        summary_pl="Utworz manifest projektu i magazyn",
        description_pl=(
            "Utworz manifest projektu (kartograf-project.json w katalogu "
            "--project) wskazujacy magazyn --output; tworzy katalogi, "
            "ktorych nie ma. Jeden projekt = jeden magazyn; wiele projektow"
            " moze dzielic magazyn."
        ),
        rules=("Give `output_dir`: a project has no default store.",),
        rules_pl=("Podaj `output_dir`: projekt nie ma domyslnego magazynu.",),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project add",
        ("Add a task for a data command to the project without downloading"),
        "manage",
        "add_project_task",
        _STATE,
        _ADD_PARAMS,
        description=(
            "Adds a named task: a data command with its options (without "
            "`output_dir` and the update options). The choices are checked "
            "offline and nothing is downloaded. Fetch the tasks with "
            "`project download`."
        ),
        effects=("project_write",),
        idempotent=False,
        tool="project_add",
        examples=(
            Example(
                {"name": "teren"},
                title="An NMT task for a PL sheet",
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
                title_pl="Zadanie NMT dla arkusza PL",
            ),
            Example(
                {"name": "gleby"},
                title="An HSG task for a PL sheet",
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
                title_pl="Zadanie HSG dla arkusza PL",
            ),
        ),
        summary_pl="Dodaj zadanie z komendy danych (bez pobierania)",
        description_pl=(
            "Dodaj zadanie: NAZWA <grupa> <komenda> [opcje komendy]. "
            "--project podaj przed NAZWA; opcje po NAZWA naleza do komendy "
            "danych (bez --output i trybow aktualizacji). Wybory sprawdzane"
            " bez sieci, nic nie jest pobierane."
        ),
        rules=(
            ("`options` are the options of the data command; see `commands schema`."),
        ),
        rules_pl=("`options` to opcje komendy danych; zobacz `commands schema`.",),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project remove",
        ("Remove a task and its pins from the manifest, keeping the files"),
        "manage",
        "remove_project_task",
        _STATE,
        _REMOVE_PARAMS,
        description=(
            "Removes the task and its pinned files from the manifest; the "
            "files in the store stay. Destructive for the manifest only."
        ),
        effects=("project_write",),
        idempotent=False,
        destructive=True,
        tool="project_remove",
        summary_pl="Usun zadanie (nie pliki magazynu)",
        description_pl=(
            "Usun zadanie i jego przypiecia z manifestu; pliki w magazynie zostaja."
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {"name": "teren"},
                title="Remove the task teren",
                title_pl="Usun zadanie teren",
            ),
        ),
    ),
    Command(
        "project download",
        ("Fetch, restore or update the tasks of a project and pin their files"),
        "data",
        "download_project",
        "kartograf-project-report/1",
        _DOWNLOAD_PARAMS,
        description=(
            "Fetches the tasks into the store and pins their files "
            "(SHA-256). A task whose pinned files exist is kept without "
            "asking the source; missing files are restored only when the "
            "SHA-256 matches. `update` upgrade or force re-pins whole "
            "tasks. With `check_updates` it only checks the sources."
        ),
        effects=("network", "store_write", "project_write"),
        check_function="check_project",
        check_result_schema=_CHECK,
        tool="project_download",
        examples=(
            Example(
                {},
                title="Fetch the tasks that are not there yet",
                title_pl="Pobierz zadania, ktorych jeszcze nie ma",
            ),
            Example(
                {},
                title="Check the sources without fetching",
                run={"check_updates": True},
                title_pl="Sprawdz aktualnosc zrodel bez pobierania",
            ),
            Example(
                {"tasks": ["teren"]},
                title="Re-pin a task to newer versions",
                run={"upgrade": True},
                title_pl="Przepnij zadanie na nowsze wersje",
            ),
        ),
        summary_pl="Pobierz, odtworz lub zaktualizuj zadania projektu",
        description_pl=(
            "Pobierz zadania projektu do magazynu i przypnij ich pliki "
            "(SHA-256). Zadanie z obecnymi przypietymi plikami zostaje bez "
            "zmian i bez zapytan do zrodla; brakujace pliki sa odtwarzane "
            "tylko przy zgodnej SHA-256. Zmiana przypiec: --upgrade albo "
            "--force."
        ),
        rules=("Check first with `check_updates`: it changes no pin.",),
        rules_pl=("Najpierw `check_updates`: nie zmienia przypiec.",),
        errors=(
            "validation_error",
            "source_unavailable",
            "no_data",
            "unsupported",
            "calculation_error",
            "store_unavailable",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project status",
        ("Check offline that the pinned files of the tasks exist with the pinned size"),
        "query",
        "get_project_status",
        _CHECK,
        _INSPECT_PARAMS,
        description=(
            "Offline and fast (no content is read): reports tasks not yet "
            "fetched and pinned files that are missing or have another "
            "size. The manifest is unchanged. Use `project verify` to check"
            " the content."
        ),
        tool="project_status",
        summary_pl="Sprawdz obecnosc i rozmiar przypietych plikow",
        description_pl=(
            "Sprawdz bez sieci, czy przypiete pliki zadan sa w magazynie i "
            "maja przypiety rozmiar (szybko, bez czytania tresci); manifest"
            " bez zmian. Kod 1, gdy ktores zadanie nie jest pobrane albo "
            "brakuje przypietego pliku."
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {},
                title="Check the pinned files of every task",
                title_pl="Sprawdz przypiete pliki kazdego zadania",
            ),
        ),
    ),
    Command(
        "project verify",
        ("Verify the SHA-256 and the sidecars of the pinned files of the tasks"),
        "query",
        "verify_project",
        _CHECK,
        _INSPECT_PARAMS,
        description=(
            "Offline: reads whole files and compares their SHA-256 and the "
            "sidecars of their versions. The manifest is unchanged. Slower "
            "than `project status`, which checks existence and size only."
        ),
        tool="project_verify",
        summary_pl="Sprawdz SHA-256 i sidecary przypietych plikow",
        description_pl=(
            "Sprawdz bez sieci tresc przypietych plikow: czyta cale pliki i"
            " porownuje SHA-256 oraz sidecary wersji; manifest bez zmian. "
            "Kod 1 przy niezgodnosci."
        ),
        rules=(),
        rules_pl=(),
        errors=(
            "validation_error",
            "data_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {},
                title="Verify the pinned files of every task",
                title_pl="Zweryfikuj przypiete pliki kazdego zadania",
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "project",
        "Project: tasks and pinned file versions in a store",
        (
            "The project manifest: download tasks and the pinned versions "
            "of their data in one store."
        ),
        summary_pl="Projekt: zadania i przypiete wersje plikow w magazynie",
        description_pl=(
            "Manifest projektu: zadania pobrania i przypiete wersje danych "
            "w jednym magazynie."
        ),
    ),
)
