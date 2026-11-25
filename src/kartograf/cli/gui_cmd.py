"""
``kartograf gui serve``: the page of plans and scripts with the server (ADR-063).

The handler translates the flags to ``serve_gui`` (ADR-063 decision 9), which serves
until Ctrl+C or ``SIGTERM``. The address is in the lifecycle record ``start`` on
stderr, so the text mode prints nothing on stdout; ``--json`` prints the envelope of
``kartograf-gui/1`` after the stop.
"""

import argparse

from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.gui import serve_gui


def cmd_gui_serve(args: argparse.Namespace) -> int:
    """Serve the GUI until it is stopped (``--json``: its document after the stop)."""
    result = serve_gui(host=args.host, port=args.port, no_browser=args.no_browser)
    if wants_json(args):
        return emit_result(command_id(args), result)
    return 0
