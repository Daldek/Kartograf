"""Messages of the command layer (``kartograf.commands``): command line errors."""

from kartograf.messages import Text

MESSAGES = {
    # ``commands``.
    "invalid_command_line": Text(
        "invalid command line: {error}",
        "nieprawidlowy zapis komendy: {error}",
    ),
    "give_data_command": Text(
        "give a data command (a group and a command, e.g. elevation download): "
        "{data_commands_text}",
        "podaj komende danych (grupa i komenda, np. elevation download): "
        "{data_commands_text}",
    ),
    "help_version_not_data": Text(
        "--help and --version are not part of a data command; the description of a "
        'command: kartograf commands schema --command "<group> <command>"',
        "--help i --version nie sa czescia komendy danych; opis komendy: kartograf "
        'commands schema --command "<grupa> <komenda>"',
    ),
    "give_group_command": Text(
        "{group}: give a command of the group (data commands: {data_commands_text})",
        "{group}: podaj komende grupy (komendy danych: {data_commands_text})",
    ),
    "option_not_of_command": Text(
        "option {name!r} does not belong to the command {command}",
        "opcja {name!r} nie nalezy do komendy {command}",
    ),
    "option_given_twice": Text(
        "option {name!r} is given as a task option and as a run flag",
        "opcja {name!r} podana jako opcja zadania i jako flaga uruchomienia",
    ),
    "output_dir_required": Text(
        "output_dir is required (the store directory)",
        "output_dir wymagane (katalog magazynu)",
    ),
    "summary_only_for_hsg": Text(
        "summary applies only to the command {summary_command} (HSG statistics)",
        "summary dotyczy tylko komendy {summary_command} (statystyki HSG)",
    ),
}
