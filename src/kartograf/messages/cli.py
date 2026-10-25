"""Messages of the CLI: the texts it prints for a person (``kartograf.cli``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``cli.commands``: the entry point.
    "no_command": Text("no command given", "nie podano komendy"),
    "plan_needs_mode": Text(
        "--plan needs --check-updates or --upgrade",
        "--plan wymaga --check-updates albo --upgrade",
    ),
    "remedy": Text("Remedy: {remedy}", "Remedium: {remedy}"),
    "debug_hint": Text(
        "Set KARTOGRAF_DEBUG=1 to see the full traceback.",
        "Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback.",
    ),
}
