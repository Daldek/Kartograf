"""
``kartograf config show`` (DEV-18.6): the settings in force and where each comes from.

The command is the library function ``get_config``: the text is rendered from its
document (``kartograf-config/1``) and with ``--json`` the CLI prints that document.
A ``nogat.toml`` that cannot be used does not stop the command (every other command
refuses it, ``check_config``): the report says what is wrong with the file.
"""

import argparse

from kartograf.cli._json import emit_document, wants_json
from kartograf.config import Config, Setting, get_config

_SOURCE_TEXT = {"default": "domyslnie", "env": "zmienna", "file": "plik"}


def _origin(source: str, name: str | None) -> str:
    if source == "default":
        return _SOURCE_TEXT["default"]
    return f"{_SOURCE_TEXT[source]} {name}"


def _shown(setting: Setting) -> str:
    if isinstance(setting.value, bool):
        return "tak" if setting.value else "nie"
    return str(setting.value)


def _state(report: Config) -> str:
    file = report.config_file
    if file.error is not None:
        return f"blad: {file.error}"
    return "istnieje" if file.exists else "brak"


def render(report: Config) -> str:
    """Return the text of a report: file, settings, credentials and store."""
    file = report.config_file
    lines = [
        f"Plik ustawien: {file.path} ({_state(report)})",
        "Ustawienia:",
    ]
    for key, setting in report.keys.items():
        line = f"  {key} = {_shown(setting)}  [{_origin(setting.source, setting.name)}]"
        if setting.error is not None:
            line += f"  (pominieto wartosc: {setting.error})"
        lines.append(line)
    for ignored in file.ignored:
        lines.append(f"  pominieto klucz [kartograf] {ignored.key}: {ignored.reason}")
    lines.append("Dane uwierzytelniajace (tylko zmienne srodowiskowe):")
    for name, state in report.credentials.items():
        lines.append(f"  {name}: {'ustawione' if state == 'present' else 'brak'}")
    store = report.store
    size = "brak katalogu" if store.size_bytes is None else f"{store.size_bytes} B"
    lines.append(
        f"Magazyn: {store.root}  [{_origin(store.source, store.name)}]  {size}"
    )
    return "\n".join(lines) + "\n"


def cmd_config_show(args: argparse.Namespace) -> int:
    """Print the settings in force (``--json``: the document ``kartograf-config/1``)."""
    report = get_config()
    if wants_json(args):
        return emit_document(report)
    print(render(report), end="")
    return 0
