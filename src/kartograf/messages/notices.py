"""Messages of the helpers of the data notices (``kartograf.notices``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``notices``.
    "size_unknown": Text(
        "size unknown (the server did not send Content-Length)",
        "rozmiar nieznany (serwer nie podal Content-Length)",
    ),
    "size_known": Text(
        "{length} B (approx. {megabytes:.0f} MB)",
        "{length} B (ok. {megabytes:.0f} MB)",
    ),
    "names_more": Text(
        "{listed} and {rest} {rest:plural(other|others)}",
        "{listed} i {rest} {rest:plural(inny|inne|innych)}",
    ),
    "approx_gigabytes": Text(
        "approx. {gigabytes:.1f} GB", "ok. {gigabytes:comma(.1f)} GB"
    ),
    "approx_megabytes": Text("approx. {megabytes:.0f} MB", "ok. {megabytes:.0f} MB"),
    "lines": Text("{lines:join(\n)}", "{lines:join(\n)}"),
    "list": Text("{items:join}", "{items:join}"),
    "joined": Text("{items:join(; )}", "{items:join(; )}"),
}
