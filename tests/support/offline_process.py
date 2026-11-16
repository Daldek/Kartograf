"""The environment of a ``kartograf`` process a test starts, kept off the network.

The guard of ``tests/conftest.py`` (``_block_network``) patches the socket of the
test process only; a child process gets these variables instead: every user
directory and the settings file lie under the test directory, and every proxy is a
dead loopback port, so a request the command should not make fails instead of
reaching a service.
"""

import os
from pathlib import Path

DEAD_PROXY = "http://127.0.0.1:9"


def offline_env(tmp_path: Path) -> dict[str, str]:
    """Return the environment of an offline ``kartograf`` process under ``tmp_path``.

    The ``KARTOGRAF_*`` and ``NOGAT_*`` variables of the caller are dropped; the data
    and cache directories and an empty ``nogat.toml`` lie in ``tmp_path``. Python
    reads and writes UTF-8 (``PYTHONUTF8``) on every platform.
    """
    config = tmp_path / "nogat.toml"
    config.write_text("", encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("KARTOGRAF_", "NOGAT_"))
    }
    return env | {
        "KARTOGRAF_DATA_DIR": str(tmp_path / "data"),
        "KARTOGRAF_CACHE_DIR": str(tmp_path / "cache"),
        "NOGAT_CONFIG": str(config),
        "HTTP_PROXY": DEAD_PROXY,
        "HTTPS_PROXY": DEAD_PROXY,
        "ALL_PROXY": DEAD_PROXY,
        "NO_PROXY": "",
        "PYTHONUTF8": "1",
    }
