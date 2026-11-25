"""Messages of ``kartograf server`` (``kartograf.server``): refusals, limits, start."""

from kartograf.messages import Text

MESSAGES = {
    # ``server.calls``: what the server refuses (ADR-063 decision 7).
    "writes_disabled": Text(
        "{command} only plans on this server: add ?check=true to get its plan; the "
        "server runs nothing and writes no data",
        "{command} na tym serwerze tylko planuje: dodaj ?check=true, aby dostac plan; "
        "serwer niczego nie uruchamia i nie zapisuje danych",
    ),
    "writes_disabled_hint": Text(
        "Run the command on your own machine, or generate its script with POST "
        "/api/v1/script/generate.",
        "Uruchom komende na swoim komputerze albo wygeneruj jej skrypt: POST "
        "/api/v1/script/generate.",
    ),
    "run_option": Text(
        "{option} belongs to a run of {command}, which this server refuses: it only "
        "plans",
        "{option} nalezy do uruchomienia {command}, ktorego ten serwer odmawia: on "
        "tylko planuje",
    ),
    "check_not_switch": Text(
        "check must be true or false, not {value}",
        "check musi byc true albo false, nie {value}",
    ),
    "path_option": Text(
        "{option} is a path ({role}): kartograf server takes no path from a client",
        "{option} to sciezka ({role}): kartograf server nie przyjmuje sciezek od "
        "klienta",
    ),
    "path_option_hint": Text(
        "Leave out {option}: the server plans a plain write into a new directory, and "
        "an area file is read only on your own machine (give the area with bbox or "
        "sheet).",
        "Pomin {option}: serwer planuje zapis zwyklych plikow do nowego katalogu, a "
        "plik obszaru jest czytany tylko na twoim komputerze (podaj obszar przez bbox "
        "albo sheet).",
    ),
    "path_in_line": Text(
        "the line of {command} names {option}, a file the server would read to plan "
        "it: kartograf server takes no path from a client",
        "linia {command} podaje {option}, plik, ktory serwer musialby przeczytac, aby "
        "ja zaplanowac: kartograf server nie przyjmuje sciezek od klienta",
    ),
    "too_many_units": Text(
        "the plan has {count} units, more than the {limit} this server plans at once",
        "plan ma {count} jednostek, wiecej niz {limit}, ktore ten serwer planuje naraz",
    ),
    "too_many_units_hint": Text(
        "Split the area, or plan on your own machine: kartograf <group> download ... "
        "--check.",
        "Podziel obszar albo zaplanuj na swoim komputerze: kartograf <grupa> download "
        "... --check.",
    ),
    "query_repeated": Text(
        "{name} is given {count} times in the query: give it once (an array as its "
        "values joined by ',')",
        "{name} podano {count} razy w zapytaniu: podaj raz (tablice jako wartosci "
        "rozdzielone ',')",
    ),
    # ``server.calls``: the limits per client (ADR-063 decision 8, DEV-15.9).
    "request_limit": Text(
        "Too many requests: {limit} in {window} s from one client. Try again in "
        "{seconds} s.",
        "Zbyt wiele zadan: {limit} w {window} s od jednego klienta. Sprobuj ponownie "
        "za {seconds} s.",
    ),
    "plan_limit": Text(
        "Too many plans: {limit} in {window} s from one client. Try again in "
        "{seconds} s.",
        "Zbyt wiele planow: {limit} w {window} s od jednego klienta. Sprobuj ponownie "
        "za {seconds} s.",
    ),
    "plan_limit_hint": Text(
        "Plan on your own machine, as often as you like: kartograf <group> download "
        "... --check.",
        "Planuj na swoim komputerze, bez limitu: kartograf <grupa> download ... "
        "--check.",
    ),
    # ``server.app``: the routes and the bodies.
    "not_served": Text(
        "{command} works on the store, cache or settings of its own machine: kartograf "
        "server does not serve it",
        "{command} dziala na magazynie, cache albo ustawieniach swojego komputera: "
        "kartograf server jej nie udostepnia",
    ),
    "not_served_hint": Text(
        "Run kartograf {command} on your own machine.",
        "Uruchom kartograf {command} na swoim komputerze.",
    ),
    "unknown_route": Text(
        "kartograf server has no route {route}",
        "kartograf server nie ma sciezki {route}",
    ),
    "unknown_route_hint": Text(
        "GET /api/v1/commands/list names the route of every command (rest); GET "
        "/api/v1/openapi.json describes them.",
        "GET /api/v1/commands/list podaje sciezke kazdej komendy (rest); GET "
        "/api/v1/openapi.json je opisuje.",
    ),
    "method_not_allowed": Text(
        "{route} answers {allowed}, not {method}",
        "{route} odpowiada na {allowed}, nie na {method}",
    ),
    "query_in_post": Text(
        "{name} is given in the query: POST {route} takes its options in a JSON body "
        "(only check=true of a plan goes in the query)",
        "{name} podano w zapytaniu: POST {route} przyjmuje opcje w tresci JSON (w "
        "zapytaniu jest tylko check=true planu)",
    ),
    "body_not_json": Text(
        "the body of the request is not JSON: {error}",
        "tresc zadania nie jest JSON: {error}",
    ),
    "body_not_object": Text(
        "the body of POST {route} must be a JSON object of the options of {command}",
        "tresc POST {route} musi byc obiektem JSON z opcjami {command}",
    ),
    "body_too_large": Text(
        "the body of the request is larger than {limit} bytes",
        "tresc zadania jest wieksza niz {limit} bajtow",
    ),
    "internal_error": Text(
        "kartograf server could not answer the request: its log has the cause",
        "kartograf server nie mogl odpowiedziec na zadanie: przyczyna jest w jego "
        "dzienniku",
    ),
    # ``server.stats``: the daily totals (DEV-15.11).
    "stats_not_written": Text(
        "the daily totals of kartograf server could not be written",
        "nie mozna zapisac dziennych sum kartograf server",
    ),
    # ``kartograf server`` on the command line (``kartograf.cli.server_cmd``).
    "cli_description": Text(
        "Serve the command catalog, the plans and the scripts over HTTP, read only "
        "(ADR-063): GET /api/v1/server, /api/v1/openapi.json and the route of every "
        "command (rest of kartograf commands list). It runs no download, writes no "
        "data and takes no path from a client; its plans are plans of a plain write "
        "into a new directory. Needs the extra server. Settings (limits, trusted "
        "proxies): kartograf config show.",
        "Udostepnij katalog komend, plany i skrypty przez HTTP, tylko do odczytu "
        "(ADR-063): GET /api/v1/server, /api/v1/openapi.json i sciezka kazdej komendy "
        "(rest z kartograf commands list). Niczego nie pobiera, nie zapisuje danych i "
        "nie przyjmuje sciezek od klienta; jego plany to plany zapisu zwyklych plikow "
        "do nowego katalogu. Wymaga dodatku server. Ustawienia (limity, zaufane "
        "proxy): kartograf config show.",
    ),
    "cli_host": Text(
        "address to listen on (default 127.0.0.1: this computer only; behind a proxy "
        "keep it and set trusted_proxies)",
        "adres nasluchu (domyslnie 127.0.0.1: tylko ten komputer; za proxy zostaw go "
        "i ustaw trusted_proxies)",
    ),
    "cli_port": Text(
        "TCP port (default 8065; 0 takes a free one, named in the record start)",
        "port TCP (domyslnie 8065; 0 bierze wolny, podany w rekordzie start)",
    ),
    "cli_port_invalid": Text(
        "{value} is no TCP port: a whole number from 0 to 65535",
        "{value} to nie port TCP: liczba calkowita od 0 do 65535",
    ),
    "cli_epilog": Text(
        "Examples:\n"
        "  kartograf server\n"
        "  kartograf server --port 8070\n"
        "  curl -s http://127.0.0.1:8065/api/v1/server",
        "Przyklady:\n"
        "  kartograf server\n"
        "  kartograf server --port 8070\n"
        "  curl -s http://127.0.0.1:8065/api/v1/server",
    ),
    "port_in_use": Text(
        "port {port} of {host} is in use",
        "port {port} na {host} jest zajety",
    ),
    "port_in_use_hint": Text(
        "Stop the program that uses it or choose another port with --port.",
        "Zatrzymaj program, ktory go uzywa, albo wybierz inny port przez --port.",
    ),
    "invalid_host": Text(
        "cannot listen on {host}: {error}",
        "nie mozna nasluchiwac na {host}: {error}",
    ),
    "missing_extra": Text(
        "{program} needs the extra {extra} (Starlette and uvicorn): {error}",
        "{program} wymaga dodatku {extra} (Starlette i uvicorn): {error}",
    ),
}
