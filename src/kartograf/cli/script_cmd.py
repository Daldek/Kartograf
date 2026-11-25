"""
``kartograf script generate``: the script of a request for the user's own machine.

The handler translates the flags to ``generate_script`` (ADR-063 decision 5): it reads
the plan file of ``--plan`` (the library takes the plan) and prints the text of the
script on stdout, so ``> kartograf.sh`` saves it; with ``--json`` it prints the
envelope of ``kartograf-script/1``. The notices of the plan of a line go to stderr as
it is made.
"""

import argparse
import sys

from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli.download_cmd import notice_printer, read_plan_file
from kartograf.script import generate_script


def cmd_script_generate(args: argparse.Namespace) -> int:
    """Print the script of a line or of a saved plan (``--json``: its document)."""
    result = generate_script(
        shell=args.shell,
        command=args.command_line,
        plan=None if args.plan is None else read_plan_file(args.plan),
        direct=args.direct,
        target=args.target,
        on_notice=notice_printer(args),
    )
    if wants_json(args):
        return emit_result(command_id(args), result)
    sys.stdout.write(result.text)
    return 0
