"""One real ``kartograf`` command in this process, with a source that stops mid-way.

Used by ``tests/integration/test_cli_interrupt.py``; it is not a test. Usage::

    python -m tests.support.interrupt_driver READY RELEASE KARTOGRAF_ARGUMENT...

The command is the real one (``kartograf.cli.commands.main``: its argument parsing,
signal handlers, staging directory, error document and exit codes); only the index
and the transfer of the PL sheets are replaced by ``FakeCampaignProvider``. The
transfer of the sheet writes the first half of the file where the command asked for
it, then creates the file READY and waits until the file RELEASE exists (at most a
minute), so that the test knows when to send a signal.
"""

import signal
import sys
import time
from pathlib import Path
from unittest.mock import patch

from kartograf.cli.commands import main
from tests.integration.test_manager_campaigns import C14, FakeCampaignProvider, asc_for

LIMIT = 60.0


class StoppingProvider(FakeCampaignProvider):
    """The sheet source whose transfer stops in the middle of the file."""

    def __init__(self, ready: Path, release: Path) -> None:
        super().__init__(C14)
        self.ready, self.release = ready, release

    def download_record(self, r, path, timeout=None):
        body = asc_for(r.sheet, f"v1 {r.url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body[: len(body) // 2])
        self.ready.write_text("blocked", encoding="utf-8")
        deadline = time.monotonic() + LIMIT
        while not self.release.exists():
            if time.monotonic() > deadline:
                raise SystemExit("interrupt_driver: not released within a minute")
            time.sleep(0.02)
        path.write_bytes(body)
        return path


def run(ready: Path, release: Path, arguments: list[str]) -> int:
    """Run ``kartograf`` with the signal handlers of a fresh process."""
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    provider = StoppingProvider(ready, release)
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(provider, None),
    ):
        return main(arguments)


if __name__ == "__main__":
    ready, release, *arguments = sys.argv[1:]
    sys.exit(run(Path(ready), Path(release), arguments))
