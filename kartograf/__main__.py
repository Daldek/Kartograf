"""``python -m kartograf``: the same command line as the ``kartograf`` script."""

import sys

from kartograf.cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
