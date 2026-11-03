"""One real ``kartograf`` command in this process, with the PL sheets of a fake index.

Used by ``tests/integration/test_cli_plain_subprocess.py``; it is not a test. Usage::

    python -m tests.support.plain_driver KARTOGRAF_ARGUMENT...

The command is the real one (``kartograf.cli.commands.main``: its argument parsing,
output target, staging directory, documents on stdout and stderr and exit code, in a
process of its own); only the index and the transfer of the PL sheets are replaced by
``FakeCampaignProvider`` (``tests.support.data_fixtures.pl_sheets``), which asks no
service. No source of Kartograf can be replaced from the command line: every data
command downloads, and ``--check`` always asks the source.
"""

import sys

from kartograf.cli.commands import main
from tests.support.data_fixtures import pl_sheets


def run(arguments: list[str]) -> int:
    """Run ``kartograf`` with the arguments; the PL sheets come from the fake index."""
    with pl_sheets():
        return main(arguments)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
