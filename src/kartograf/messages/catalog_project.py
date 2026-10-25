"""Messages of the command catalog: the declarations of ``project``."""

from kartograf.messages import Text

MESSAGES = {
    "project_dir_description": Text(
        "Project directory (the one with `kartograf-project.json`); in the CLI the "
        "current directory by default.",
        "Katalog projektu (domyslnie biezacy katalog)",
    ),
    "name_description": Text("Name of the task.", "Nazwa zadania"),
    "tasks_description": Text(
        "Only these tasks; default all.",
        "Wybrane zadania (domyslnie wszystkie)",
    ),
    "root_description": Text(
        "Store directory of the project, written into the manifest. Default: the "
        "store of the user data directory (`KARTOGRAF_ROOT`, `[kartograf] root` of "
        "`nogat.toml`, else `<data_dir>/kartograf`), as an absolute path.",
        "Katalog magazynu projektu, zapisany w manifescie (domyslnie magazyn w "
        "katalogu danych uzytkownika, jako sciezka bezwzgledna)",
    ),
    "add_name_description": Text("Unique name of the task.", "Unikalna nazwa zadania"),
    "arguments_description": Text(
        "The data command and its options, for example elevation download --product "
        "nmt ...",
        "Komenda danych i jej opcje, np. elevation download --product nmt ...",
    ),
    "command_description": Text(
        "Data command of the task (required): one of the commands a project task may "
        "run.",
        "Komenda danych zadania (wymagana): jedna z komend z project_task w katalogu; "
        "w CLI to pierwsze slowa po NAZWA",
    ),
    "options_description": Text(
        "Options of the task (required): an object with the options of the data "
        'command without `root`, for example {{"product": "nmt", "sheet": '
        '"N-34-130-D-d-2-4"}}; `commands schema` lists them.',
        "Opcje zadania (wymagane): obiekt z opcjami komendy danych bez root, np. "
        '{{"product": "nmt", "sheet": "N-34-130-D-d-2-4"}}; opcje komendy podaje '
        "commands schema; w CLI to opcje po komendzie",
    ),
    "param_description": Text(
        "Update mode. Omitted: a task that is not fetched is fetched and pinned, a "
        "fetched one stays as it is. upgrade or force re-pins the whole task. CLI: "
        "--upgrade, --force.",
        "Tryb aktualizacji (pominiety: zadanie niepobrane jest pobierane i "
        "przypinane, pobrane zostaje bez zmian): upgrade albo force przepina cale "
        "zadanie",
    ),
    "check_description": Text(
        "The pins stay unchanged.",
        "Sprawdz zrodla bez pobierania i bez zmiany przypiec",
    ),
    "workers_description": Text(
        "Parallel transfers inside each task (default as in the data command: 4 for "
        "elevation and imagery, 1 for the rest; none for `soil hsg`).",
        "Rownolegle pobieranie plikow w kazdym zadaniu (domyslnie jak w komendzie "
        "danych: elevation i imagery 4, pozostale 1; soil hsg bez rownoleglosci)",
    ),
    "project_init_summary": Text(
        "Create a project manifest and its store",
        "Utworz manifest projektu i magazyn",
    ),
    "project_init_description": Text(
        "Creates `kartograf-project.json` in `project_dir` and points it at the store "
        "`root`; missing directories are created. One project has one store; several "
        "projects may share it. Add tasks with `project add`.",
        "Utworz manifest projektu (kartograf-project.json w katalogu --project) "
        "wskazujacy magazyn --root; tworzy katalogi, ktorych nie ma. Jeden projekt = "
        "jeden magazyn; wiele projektow moze dzielic magazyn.",
    ),
    "project_init_rule_1": Text(
        "Without `root` the manifest points at the default store.",
        "Bez `root` manifest wskazuje domyslny magazyn.",
    ),
    "example_new_project_store_data": Text(
        "A new project with the store in ./data",
        "Nowy projekt z magazynem w ./data",
    ),
    "project_add_summary": Text(
        "Add a task for a data command to the project without downloading",
        "Dodaj zadanie z komendy danych (bez pobierania)",
    ),
    "project_add_description": Text(
        "Adds a named task: a data command with its options (without `root`, "
        "`output_dir` and the update options). The choices are checked offline and "
        "nothing is downloaded. Fetch the tasks with `project download`.",
        "Dodaj zadanie: NAZWA <grupa> <komenda> [opcje komendy]. --project podaj "
        "przed NAZWA; opcje po NAZWA naleza do komendy danych (bez --root, "
        "--output-dir i trybow aktualizacji). Wybory sprawdzane bez sieci, nic nie "
        "jest pobierane.",
    ),
    "project_add_rule_1": Text(
        "`options` are the options of the data command; see `commands schema`.",
        "`options` to opcje komendy danych; zobacz `commands schema`.",
    ),
    "example_nmt_task_pl_sheet": Text(
        "An NMT task for a PL sheet",
        "Zadanie NMT dla arkusza PL",
    ),
    "example_hsg_task_pl_sheet": Text(
        "An HSG task for a PL sheet",
        "Zadanie HSG dla arkusza PL",
    ),
    "project_remove_summary": Text(
        "Remove a task and its pins from the manifest, keeping the files",
        "Usun zadanie (nie pliki magazynu)",
    ),
    "project_remove_description": Text(
        "Removes the task and its pinned files from the manifest; the files in the "
        "store stay. Destructive for the manifest only.",
        "Usun zadanie i jego przypiecia z manifestu; pliki w magazynie zostaja.",
    ),
    "example_remove_task_teren": Text("Remove the task teren", "Usun zadanie teren"),
    "project_download_summary": Text(
        "Fetch, restore or update the tasks of a project and pin their files",
        "Pobierz, odtworz lub zaktualizuj zadania projektu",
    ),
    "project_download_description": Text(
        "Fetches the tasks into the store and pins their files (SHA-256). A task "
        "whose pinned files exist is kept without asking the source; missing files "
        "are restored only when the SHA-256 matches. `update` upgrade or force "
        "re-pins whole tasks. With `check` it only checks the sources.",
        "Pobierz zadania projektu do magazynu i przypnij ich pliki (SHA-256). Zadanie "
        "z obecnymi przypietymi plikami zostaje bez zmian i bez zapytan do zrodla; "
        "brakujace pliki sa odtwarzane tylko przy zgodnej SHA-256. Zmiana przypiec: "
        "--upgrade albo --force.",
    ),
    "project_download_rule_1": Text(
        "Check first with `check`: it changes no pin.",
        "Najpierw `check`: nie zmienia przypiec.",
    ),
    "example_fetch_tasks_not_there_yet": Text(
        "Fetch the tasks that are not there yet",
        "Pobierz zadania, ktorych jeszcze nie ma",
    ),
    "example_check_sources_without_fetching": Text(
        "Check the sources without fetching",
        "Sprawdz aktualnosc zrodel bez pobierania",
    ),
    "example_re_pin_task_newer_versions": Text(
        "Re-pin a task to newer versions",
        "Przepnij zadanie na nowsze wersje",
    ),
    "project_status_summary": Text(
        "Check offline that the pinned files of the tasks exist with the pinned size",
        "Sprawdz obecnosc i rozmiar przypietych plikow",
    ),
    "project_status_description": Text(
        "Offline and fast (no content is read): reports tasks not yet fetched and "
        "pinned files that are missing or have another size. The manifest is "
        "unchanged. Use `project verify` to check the content.",
        "Sprawdz bez sieci, czy przypiete pliki zadan sa w magazynie i maja przypiety "
        "rozmiar (szybko, bez czytania tresci); manifest bez zmian. Kod 1, gdy ktores "
        "zadanie nie jest pobrane albo brakuje przypietego pliku.",
    ),
    "example_check_pinned_files_every_task": Text(
        "Check the pinned files of every task",
        "Sprawdz przypiete pliki kazdego zadania",
    ),
    "project_verify_summary": Text(
        "Verify the SHA-256 and the sidecars of the pinned files of the tasks",
        "Sprawdz SHA-256 i sidecary przypietych plikow",
    ),
    "project_verify_description": Text(
        "Offline: reads whole files and compares their SHA-256 and the sidecars of "
        "their versions. The manifest is unchanged. Slower than `project status`, "
        "which checks existence and size only.",
        "Sprawdz bez sieci tresc przypietych plikow: czyta cale pliki i porownuje "
        "SHA-256 oraz sidecary wersji; manifest bez zmian. Kod 1 przy niezgodnosci.",
    ),
    "example_verify_pinned_files_every_task": Text(
        "Verify the pinned files of every task",
        "Zweryfikuj przypiete pliki kazdego zadania",
    ),
    "project_group_summary": Text(
        "Project: tasks and pinned file versions in a store",
        "Projekt: zadania i przypiete wersje plikow w magazynie",
    ),
    "project_group_description": Text(
        "The project manifest: download tasks and the pinned versions of their data "
        "in one store.",
        "Manifest projektu: zadania pobrania i przypiete wersje danych w jednym "
        "magazynie.",
    ),
    "store_only_rule": Text(
        "Store only: a project is bound to a store, so there is no `output_dir`.",
        "Tylko magazyn: projekt jest zwiazany z magazynem, wiec bez --output-dir.",
    ),
    "download_upgrade_description": Text(
        "Fetch newer versions and re-pin the whole tasks",
        "Pobierz nowsze wersje i przepnij cale zadania",
    ),
    "download_force_description": Text(
        "Fetch again and re-pin the whole tasks",
        "Pobierz ponownie i przepnij cale zadania",
    ),
}
