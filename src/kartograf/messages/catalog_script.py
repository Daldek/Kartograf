"""Messages of the command catalog: the declarations of ``script``."""

from kartograf.messages import Text

MESSAGES = {
    "generate_summary": Text(
        "Write a bash or PowerShell script that runs a data command or downloads its "
        "files",
        "Napisz skrypt bash albo PowerShell, który uruchamia komendę danych albo "
        "pobiera jej pliki",
    ),
    "generate_description": Text(
        "Nothing is written; the network only plans a direct script of `command`. "
        "Default: the Kartograf script, which installs the pinned release with uv when "
        "needed, checks the keys of its sources and runs the line. `direct`: curl or "
        "Invoke-WebRequest of the files of the plan of `command` or of a saved `plan`, "
        "with size and SHA-256 checks and an ATTRIBUTION.txt; a file no URL serves is "
        "left out with its reason. `text` is the script.",
        "Skrypt dla twojego komputera (bez zapisu): domyślnie skrypt Kartografa, który "
        "w razie potrzeby instaluje przypięte wydanie przez uv, sprawdza klucze źródeł "
        "i uruchamia linię komendy; z --direct skrypt curl albo Invoke-WebRequest "
        "plików planu linii (--command) albo zapisanego planu (--plan), ze "
        "sprawdzeniem rozmiaru i SHA-256 oraz plikiem ATTRIBUTION.txt; plik bez URL "
        "jest pominięty z powodem. Sieć tylko do planu skryptu bezpośredniego z "
        "--command. --json: dokument kartograf-script/1.",
    ),
    "generate_rule": Text(
        "Paths in `command` and `target` are text of the script: nothing is resolved.",
        "Ścieżki w --command i --target są tekstem skryptu: nic nie jest rozwiązywane.",
    ),
    "shell_description": Text(
        "The shell the script is written for (required).",
        "Powłoka, dla której jest skrypt (wymagana)",
    ),
    "command_description": Text(
        "The line of a data command, with or without the leading `kartograf`: the "
        "Kartograf script runs it, a direct script downloads the files of its plan "
        "into its `-o` or `--root`, as typed.",
        "Linia komendy danych (z kartograf na początku albo bez): skrypt Kartografa ją "
        "uruchamia, skrypt bezpośredni pobiera pliki jej planu do jej -o albo --root, "
        "tak jak wpisano",
    ),
    "plan_description": Text(
        "A saved plan (`kartograf-plan/1`, the result of `check`) whose files a direct "
        "script downloads, instead of `command`: a file on the CLI, the document in "
        "the API.",
        "Zapisany plan (kartograf-plan/1 z --check), którego pliki pobiera skrypt "
        "bezpośredni, zamiast --command: plik w CLI, dokument w API",
    ),
    "direct_description": Text(
        "Write the direct script (curl or Invoke-WebRequest of the URLs of the plan) "
        "instead of the Kartograf script.",
        "Napisz skrypt bezpośredni (curl albo Invoke-WebRequest adresów URL planu) "
        "zamiast skryptu Kartografa",
    ),
    "target_description": Text(
        "The directory a direct script downloads into, as typed: by default the `-o` "
        "or `--root` of `command`, else `.`.",
        "Katalog, do którego pobiera skrypt bezpośredni, tak jak wpisano: domyślnie -o "
        "albo --root linii komendy, inaczej katalog bieżący",
    ),
    "rule_command_or_plan": Text(
        "Give exactly one of --command and --plan",
        "Podaj dokładnie jedno z: --command albo --plan",
    ),
    "metavar_shell": Text("SHELL", "POWŁOKA"),
    "metavar_line": Text("LINE", "LINIA"),
    "example_kartograf_bash": Text(
        "The Kartograf script of a line, for bash",
        "Skrypt Kartografa dla linii komendy, w bash",
    ),
    "example_direct_powershell": Text(
        "A direct PowerShell script of the files of the plan of a line, into another "
        "directory",
        "Skrypt bezpośredni PowerShell plików planu linii komendy, do innego katalogu",
    ),
    "group_summary": Text(
        "Scripts that run a request on your own machine",
        "Skrypty, które wykonują żądanie na twoim komputerze",
    ),
    "group_description": Text(
        "Bash and PowerShell scripts of a data command for your own machine "
        "(ADR-063): the Kartograf script that runs its line with a pinned release, or "
        "the direct script of the URLs of its plan.",
        "Skrypty bash i PowerShell komendy danych dla twojego komputera (ADR-063): "
        "skrypt Kartografa, który uruchamia jej linię przypiętym wydaniem, albo skrypt "
        "bezpośredni adresów URL jej planu.",
    ),
}
