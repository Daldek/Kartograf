"""Messages of the command catalog: the declarations of ``gui``."""

from kartograf.messages import Text

MESSAGES = {
    "serve_summary": Text(
        "Serve the page of plans and scripts with the read-only API on this computer",
        "Udostepnij strone planow i skryptow z API tylko do odczytu na tym komputerze",
    ),
    "serve_description": Text(
        "Serves the page and the read-only /api/v1 of `kartograf server` on "
        "127.0.0.1:8065 until Ctrl+C or SIGTERM, and opens the page in a browser "
        "unless `no_browser`. The page builds a data command, shows its plan and gives "
        "its line and scripts; it plans with the network and never writes data. Needs "
        "the extra `gui`. The record `start` on stderr names the address; the result "
        "comes after the stop.",
        "Udostepnia strone i API tylko do odczytu /api/v1 serwera kartograf server na "
        "127.0.0.1:8065 do Ctrl+C albo SIGTERM i otwiera strone w przegladarce, chyba "
        "ze podano --no-browser. Strona sklada komende danych, pokazuje jej plan i "
        "daje jej linie oraz skrypty; planuje przez siec i nigdy nie zapisuje danych. "
        "Wymaga dodatku gui (pip install 'kartograf[gui]'). Rekord start na stderr "
        "podaje adres; --json: dokument kartograf-gui/1 po zatrzymaniu.",
    ),
    "serve_rule": Text(
        "On an address beyond this computer, anyone who reaches it can use the page "
        "and its API.",
        "Na adresie poza tym komputerem ze strony i jej API moze korzystac kazdy, kto "
        "do niego dotrze.",
    ),
    "host_description": Text(
        "The address to listen on: 127.0.0.1, this computer only.",
        "Adres, na ktorym serwer nasluchuje: domyslnie 127.0.0.1, tylko ten komputer",
    ),
    "port_description": Text(
        "The TCP port; 0 takes a free one.",
        "Port TCP; 0 wybiera wolny",
    ),
    "no_browser_description": Text(
        "Do not open the page in a web browser.",
        "Nie otwieraj strony w przegladarce",
    ),
    "metavar_host": Text("HOST", "ADRES"),
    "example_serve_without_browser": Text(
        "Serve the page on another port without opening a browser",
        "Udostepnij strone na innym porcie bez otwierania przegladarki",
    ),
    "group_summary": Text(
        "The web page of plans and scripts on this computer",
        "Strona WWW planow i skryptow na tym komputerze",
    ),
    "group_description": Text(
        "The web page (ADR-063) that builds a data command, shows its plan as a table "
        "and its footprints on a map, and gives its command line, the Kartograf script "
        "and the direct script; served with the read-only API of kartograf server "
        "(extra gui).",
        "Strona WWW (ADR-063), ktora sklada komende danych, pokazuje jej plan jako "
        "tabele i jego zasiegi na mapie oraz daje jej linie komendy, skrypt Kartografa "
        "i skrypt bezposredni; udostepniana z API tylko do odczytu serwera kartograf "
        "server (dodatek gui).",
    ),
}
