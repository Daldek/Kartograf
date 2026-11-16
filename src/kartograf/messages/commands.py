"""Messages of the command layer (``kartograf.commands``): command line errors."""

from kartograf.messages import Text

MESSAGES = {
    # ``commands``.
    "invalid_command_line": Text(
        "invalid command line: {error}",
        "nieprawidlowy zapis komendy: {error}",
    ),
    "give_command": Text(
        "give a command (a group and a command, e.g. elevation download); the list: "
        "kartograf commands list",
        "podaj komende (grupa i komenda, np. elevation download); lista: kartograf "
        "commands list",
    ),
    "help_version_not_a_call": Text(
        "--help and --version are not part of a command that can be called; the "
        'description of a command: kartograf commands schema --command "<group> '
        '<command>"',
        "--help i --version nie sa czescia komendy, ktora mozna wywolac; opis "
        'komendy: kartograf commands schema --command "<grupa> <komenda>"',
    ),
    "give_group_commands": Text(
        "{group}: give a command of the group ({group_commands})",
        "{group}: podaj komende grupy ({group_commands})",
    ),
    "option_not_of_command": Text(
        "option {name!r} does not belong to the command {command}",
        "opcja {name!r} nie nalezy do komendy {command}",
    ),
    "option_given_twice": Text(
        "option {name!r} is given as an option and as a run flag",
        "opcja {name!r} podana jako opcja i jako flaga uruchomienia",
    ),
    "summary_only_for_hsg": Text(
        "summary applies only to the command {summary_command} (HSG statistics)",
        "summary dotyczy tylko komendy {summary_command} (statystyki HSG)",
    ),
    "options_not_mapping": Text(
        "the options of a command are a mapping of names to values, got {got}",
        "opcje komendy to slownik nazw i wartosci, otrzymano {got}",
    ),
    "option_required": Text(
        "option {name!r} is required by the command {command}",
        "opcja {name!r} jest wymagana przez komende {command}",
    ),
    "value_not_allowed": Text(
        "option {name!r}: {value!r} is not one of the allowed values ({allowed})",
        "opcja {name!r}: {value!r} nie jest dozwolona wartoscia ({allowed})",
    ),
    "value_at_least": Text(
        "option {name!r} must be at least {limit}",
        "opcja {name!r} musi byc co najmniej {limit}",
    ),
    "value_at_most": Text(
        "option {name!r} must be at most {limit}",
        "opcja {name!r} musi byc co najwyzej {limit}",
    ),
    "store_only_command": Text(
        "the command {command} works on a store only: it has no plain mode "
        "(output_dir)",
        "komenda {command} dziala tylko na magazynie: nie ma trybu zwyklych plikow "
        "(output_dir)",
    ),
    "no_check": Text(
        "the command {command} has no plan: it has no option check",
        "komenda {command} nie ma planu: nie ma opcji check",
    ),
    "no_check_hint": Text(
        "Run it: only a command with the option check can be planned without effects "
        "(kartograf commands list: check)",
        "Uruchom ja: bez skutkow planuje sie tylko komende z opcja check "
        "(kartograf commands list: check)",
    ),
    # ``command_for_file`` (KB-6, ADR-057).
    "file_sidecar_type": Text(
        "command_for_file takes the Sidecar that read_sidecar returns, not {kind}",
        "command_for_file przyjmuje Sidecar zwracany przez read_sidecar, nie {kind}",
    ),
    "file_field_malformed": Text(
        "{dataset}: the sidecar field {field} has a value of a wrong form: {value}",
        "{dataset}: pole sidecara {field} ma wartosc zlej postaci: {value}",
    ),
    "file_field_malformed_hint": Text(
        "A writer of Kartograf never writes this value: download the file again "
        "into the store",
        "Zaden zapis Kartografa nie tworzy takiej wartosci: pobierz plik ponownie "
        "do magazynu",
    ),
    "file_unknown_dataset": Text(
        "the sidecar names no registered dataset ({dataset}): no command of this "
        "Kartograf downloads it",
        "sidecar nie wskazuje zarejestrowanego zbioru ({dataset}): zadna komenda tej "
        "wersji Kartografa go nie pobiera",
    ),
    "file_missing_field": Text(
        "{dataset}: the sidecar has no {field}, which the command of the file needs",
        "{dataset}: sidecar nie ma pola {field}, ktorego potrzebuje komenda pliku",
    ),
    "file_hsg": Text(
        "{dataset}: soil hsg is derived from SoilGrids inputs that its sidecar does "
        "not record as a command (decision D5 of ADR-057)",
        "{dataset}: soil hsg powstaje z wejsc SoilGrids, ktorych sidecar nie zapisuje "
        "jako komendy (decyzja D5 ADR-057)",
    ),
    "file_area": Text(
        "{dataset}: the file was chosen by an area (a box, a geometry or an index tile "
        "of an area) and its sidecar records no selection the command can repeat",
        "{dataset}: plik wybrano obszarem (prostokat, geometria albo kafel skorowidza "
        "obszaru), a jego sidecar nie zapisuje wyboru, ktory komenda moze powtorzyc",
    ),
    "file_reprojected_cutout": Text(
        "{dataset}: the cutout was reprojected to {crs}; its recorded grid does not "
        "give back the area it was requested for",
        "{dataset}: wycinek przeliczono do {crs}; zapisana siatka nie odtwarza "
        "obszaru, o ktory go poproszono",
    ),
    "file_no_selection": Text(
        "{dataset}: the request ({keys}) names no selection of the command {command}",
        "{dataset}: zadanie ({keys}) nie wskazuje wyboru komendy {command}",
    ),
    "file_not_an_option": Text(
        "{dataset}: the request field {field} is not an option of the command "
        "{command}",
        "{dataset}: pole zadania {field} nie jest opcja komendy {command}",
    ),
}
