"""
``kartograf config show`` (DEV-18.6): the settings in force and where each comes from.

The command is the library function ``get_config``: the text is rendered from its
document (``kartograf-config/1``) and with ``--json`` the CLI prints that document.
A ``nogat.toml`` that cannot be used does not stop the command (every other command
refuses it, ``check_config``): the report says what is wrong with the file.
"""

import argparse

from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import localized, yes_no
from kartograf.config import Config, Setting, get_config
from kartograf.messages import message

_SOURCE_TEXT = {
    "default": message("cli.source_default"),
    "env": message("cli.source_env"),
    "file": message("cli.source_file"),
}


def _origin(source: str, name: str | None) -> str:
    if source == "default":
        return localized(_SOURCE_TEXT["default"])
    return f"{localized(_SOURCE_TEXT[source])} {name}"


def _shown(setting: Setting) -> str:
    if isinstance(setting.value, bool):
        return yes_no(setting.value)
    if isinstance(setting.value, tuple):
        return ", ".join(setting.value)
    return str(setting.value)


def _state(report: Config) -> str:
    file = report.config_file
    if file.error is not None:
        return localized(message("cli.state_error", error=file.error))
    return (
        localized(message("cli.state_exists"))
        if file.exists
        else localized(message("cli.missing"))
    )


def render(report: Config) -> str:
    """Return the text of a report: file, settings, credentials and store."""
    file = report.config_file
    lines: list[str] = [
        localized(
            message(
                "cli.settings_file_line",
                path=file.path,
                state=_state(report),
            )
        ),
        localized(message("cli.settings_header")),
    ]
    for key, setting in report.keys.items():
        line = f"  {key} = {_shown(setting)}  [{_origin(setting.source, setting.name)}]"
        if setting.error is not None:
            line += localized(message("cli.value_skipped", error=setting.error))
        lines.append(line)
    for ignored in file.ignored:
        lines.append(
            localized(
                message(
                    "cli.ignored_config_key",
                    setting_key=ignored.key,
                    reason=ignored.reason,
                )
            )
        )
    lines.append(localized(message("cli.credentials_header")))
    for name, state in report.credentials.items():
        state_text = (
            localized(message("cli.credential_set"))
            if state == "present"
            else localized(message("cli.missing"))
        )
        lines.append(f"  {name}: {state_text}")
    store = report.store
    size = (
        localized(message("cli.store_no_directory"))
        if store.size_bytes is None
        else f"{store.size_bytes} B"
    )
    lines.append(
        localized(
            message(
                "cli.store_line",
                root=store.root,
                origin=_origin(store.source, store.name),
                size=size,
            )
        )
    )
    return "\n".join(lines) + "\n"


def cmd_config_show(args: argparse.Namespace) -> int:
    """Print the settings in force (``--json``: the document ``kartograf-config/1``)."""
    report = get_config()
    if wants_json(args):
        return emit_result(command_id(args), report)
    print(render(report), end="")
    return 0
