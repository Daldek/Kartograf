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
    "give_group_command": Text(
        "{group}: give a command of the group (data commands: {data_commands_text})",
        "{group}: podaj komende grupy (komendy danych: {data_commands_text})",
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
    "task_run_flag": Text(
        "option {name!r} of the line is a flag of a run and no option of a task: a "
        "task keeps only the options of its data command",
        "opcja {name!r} zapisu jest flaga uruchomienia, nie opcja zadania: zadanie "
        "ma tylko opcje swojej komendy danych",
    ),
}
