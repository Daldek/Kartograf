"""
The scripts of a request for the user's own machine (``kartograf script generate``).

``generate_script`` writes, as text, a bash or PowerShell script of one data command
(ADR-063 decision 5). Nothing is resolved, read or written on the disk of the process:
a path of the line or the target is text of the script, which the shell of the user's
machine reads (a leading ``~`` is the home directory there).

- The *Kartograf script* (``kind`` ``kartograf``) of a command line runs the line with
  the released Kartograf it pins (``kartograf @ git+<repository>@v<version>``): it
  stops with the address of uv's installation guide when ``uv`` is missing, installs
  the pinned tag with ``uv tool install`` when ``kartograf`` is missing, runs the line
  with ``uvx --from`` when another version is installed (which it leaves as it is) and
  otherwise with ``kartograf``. Before that it stops, naming them, when the variables
  of a keyed source of the command's product are not set and, on macOS, the Keychain
  has no key either (the Auth Proxy of Kartograf reads both). A development version
  pins no tag: ``unsupported``, ``development_version``.
- The *direct script* (``kind`` ``direct``) downloads every file of a plan that is the
  bytes of a URL (``fetch``) with ``curl`` or ``Invoke-WebRequest`` into the target
  under its plain name, checks the size the plan knows and the SHA-256 the registry
  pins, and appends to ``ATTRIBUTION.txt`` each provider line of DEV §20 of its files
  the file lacks (DEV-20.5, ADR-064): G, SG and Z with the products and the years the
  plan names and the day the script runs as the day of the download, the registry
  text of a source the table holds no row for (a rerun on another day adds its own G
  or Z line instead of joining it with the earlier one). The plan is the detached
  plan of the line (``check_command(..., detached=True)``: the only use of the
  network) or a saved plan, whose names, URLs and SHA-256 are checked first. A file
  no URL serves (``fetch_reason``, ``no_url``), one whose source could not be checked
  (``check_failed``) and one whose target is a conflict (its ``reason``; two files of
  one name in a store plan are ``duplicate_output_name``) are left out with their
  reason, in the header of the script and in ``left_out``; a plan whose every file is
  left out has no direct script (``unsupported``, ``no_direct_files``).

The texts of a script are English, as the rest of its document (AGI-9.2). A PowerShell
script is ASCII: Windows PowerShell 5.1 reads a file without a byte order mark in the
code page of the system, so every other character of a value is written as its code.
"""

import re
import shlex
import textwrap
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol, get_args
from urllib.parse import urlsplit

from kartograf._version import build_version
from kartograf.attribution import ATTRIBUTION_FILE, date_parts
from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared_commands
from kartograf.commands import CommandCall, check_command, format_command, parse_command
from kartograf.download.arguments import require_bool, require_str
from kartograf.download.plan import PlanItem, UpdatePlan, plan_lines
from kartograf.exceptions import UnsupportedError, ValidationError
from kartograf.messages import message
from kartograf.notices import Notice
from kartograf.serialization import Document
from kartograf.source_info import SOURCE_GROUPS, list_sources

__all__ = [
    "SHELLS",
    "LeftOutFile",
    "ScriptFile",
    "ScriptResult",
    "generate_script",
]

Shell = Literal["bash", "powershell"]
SHELLS: Final[tuple[Shell, ...]] = get_args(Shell)
"""The shells a script is written for (``--shell``)."""
ScriptKind = Literal["kartograf", "direct"]

REPOSITORY: Final = "https://github.com/Daldek/Kartograf.git"
"""The repository whose released tag a Kartograf script installs."""
UV_GUIDE: Final = "https://docs.astral.sh/uv/getting-started/installation/"
"""The installation guide of uv, which a Kartograf script names when uv is missing."""
PLANNED_LINES: Final[Mapping[str, tuple[str, str]]] = {
    "script generate": ("command", "direct")
}
"""The commands whose call plans a command line it is given: the option of the line
and the switch that makes the call plan it (a direct script reads the input files of
the line, ``geometry``). An interface that confines paths (the MCP server's
``--allow-dir``, ``kartograf server``) checks them as the call's own options."""


@dataclass(frozen=True)
class _Key:
    """Where Kartograf takes the key of a source from: a variable, on macOS a Keychain.

    ``keychain`` is the service of the macOS Keychain the Auth Proxy reads when the
    variable is not set (``kartograf.auth.proxy.KEYCHAIN_SERVICE``), or ``None``.
    """

    variable: str
    keychain: str | None = None


# The key of each key exchange of the registry (``auth`` of a source, ``list-sources``).
_KEYS: Final[Mapping[str, _Key]] = {
    "clms_oauth": _Key("CLMS_CREDENTIALS", "clms-token"),
}
# A released version: the tag ``v<version>`` exists (a development one has no tag).
_RELEASE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
# Not in a plain file name on any system the scripts run on.
_NOT_IN_NAMES = frozenset('/\\:*?"<>|')
# A word a shell reads as it is (``shlex.quote`` leaves these bare).
_BARE = re.compile(r"[A-Za-z0-9_@%+=:,./-]+")
# The width of the comments of the header.
_WIDTH = 88
# The reasons of ``left_out`` with a text of their own; any other is a conflict.
_WHY: Final[Mapping[str, str]] = {
    "credentials": "script.why_credentials",
    "built": "script.why_built",
    "feed_not_cached": "script.why_feed_not_cached",
    "check_failed": "script.why_check_failed",
    "no_url": "script.why_no_url",
}


@dataclass(frozen=True)
class ScriptFile:
    """A file a direct script downloads.

    ``name`` is its plain name in the target, ``unit`` the unit of the plan,
    ``url`` where its bytes are, ``size_bytes`` and ``sha256`` what the script checks
    (``None`` when the plan does not know them) and ``source`` the registry key of its
    source.
    """

    name: str
    unit: str
    url: str
    size_bytes: int | None
    sha256: str | None
    source: str | None


@dataclass(frozen=True)
class LeftOutFile:
    """A file of the plan a direct script leaves out, and why.

    ``reason`` is the ``fetch_reason`` of the position (``credentials``, ``built``,
    ``feed_not_cached``), ``no_url`` (the plan names no URL of it), ``check_failed``
    or the ``reason`` of a conflict of its target (``duplicate_output_name``, ...).
    """

    name: str
    unit: str
    reason: str


@dataclass(frozen=True)
class ScriptResult(Document):
    """The script of a request (``kartograf-script/1``, ADR-063 decision 5).

    ``shell`` is ``bash`` or ``powershell``; ``kind`` ``kartograf`` for the script
    that runs the line with Kartograf or ``direct`` for the downloads of its plan;
    ``text`` the script (LF, a final newline; the CLI prints it). A direct script
    lists its downloads in ``files`` and the files it leaves out in ``left_out``;
    ``notices`` are those of its plan.
    """

    SCHEMA = "kartograf-script/1"

    shell: Shell
    kind: ScriptKind
    text: str
    files: tuple[ScriptFile, ...] = ()
    left_out: tuple[LeftOutFile, ...] = ()
    notices: tuple[Notice, ...] = ()


def generate_script(
    *,
    shell: str | None,
    command: str | None = None,
    plan: UpdatePlan | None = None,
    direct: bool = False,
    target: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> ScriptResult:
    """Write the script of a request for the user's own machine (``script generate``).

    Parameters
    ----------
    shell : {"bash", "powershell"}
        The shell of the script (required).
    command : str, optional
        The line of a data command (``parse_command`` reads it; with or without the
        leading ``kartograf``). Without ``direct`` the script runs it; its ``-o`` or
        ``--root`` is the default target of a direct script, as typed.
    plan : UpdatePlan, optional
        A saved plan (``kartograf-plan/1``) to make the direct script of, instead of
        ``command``.
    direct : bool
        Write the direct script (``curl`` or ``Invoke-WebRequest`` of the URLs of the
        plan) instead of the Kartograf script.
    target : str, optional
        The directory the direct script downloads into, as typed: by default the
        target of ``command``, else ``.``.
    cache : MetadataCache or bool
        As in the library functions: the plan of ``command`` reuses the index answers
        the cache holds (``check_command``).
    on_notice : callable, optional
        Called with each notice of the plan of ``command`` as it is made.

    Returns
    -------
    ScriptResult
        The document ``kartograf-script/1``. Only the plan of a direct script of
        ``command`` uses the network; nothing is written.

    Raises
    ------
    ValidationError
        No or an unknown ``shell`` (``allowed`` the shells); neither or both of
        ``command`` and ``plan``; ``plan`` or ``target`` without ``direct``; an empty
        ``target`` or one with a control character; a line ``parse_command`` refuses
        (``UsageError``) or one of no data command (``option`` ``command``); a plan
        of 0.9.0 without the fields that say where its files come from, or with a
        name that is no plain file name, a URL that is not ``http`` or ``https`` or a
        SHA-256 that is not 64 hexadecimal digits (``option`` ``plan``); and the
        errors of ``check_command`` of the line.
    UnsupportedError
        A Kartograf script of a development version, which no released tag pins
        (``development_version``), or a direct script of a plan none of whose files a
        URL serves (``no_direct_files``, ``files`` the files with their reason).

    Examples
    --------
    >>> from kartograf import generate_script
    >>> script = generate_script(
    ...     shell="bash",
    ...     command="elevation download --product nmt --sheet N-34-130-D-d-2-4"
    ...     " --resolution 1m --vertical-crs EVRF2007 -o ./dem",
    ... )
    >>> script.kind, script.text.startswith("#!/usr/bin/env bash")
    ('kartograf', True)
    """
    writer = _writer(shell)
    require_bool(direct, "--direct")
    if command is not None:
        require_str(command, "--command")
    if plan is not None and not isinstance(plan, UpdatePlan):
        raise ValidationError(
            message("script.not_a_plan", got=type(plan).__name__), option="plan"
        )
    if command is not None and plan is not None:
        raise ValidationError(
            message("script.command_and_plan"), options=("command", "plan")
        )
    if command is None and plan is None:
        raise ValidationError(
            message("script.give_command_or_plan"), options=("command", "plan")
        )
    if plan is not None and not direct:
        raise ValidationError(
            message("script.plan_needs_direct"), options=("plan", "direct")
        )
    if target is not None:
        require_str(target, "--target")
        if not direct:
            raise ValidationError(
                message("script.target_needs_direct"), options=("target", "direct")
            )
        if not target or any(_control(char) for char in target):
            raise ValidationError(
                message("script.bad_target", target=target), option="target"
            )
    call = None if command is None else _data_call(command)
    if not direct:
        assert call is not None  # a Kartograf script needs the line (checked above)
        return _kartograf_script(writer, call)
    if call is not None:
        planned = check_command(
            call.command,
            call.options,
            detached=True,
            cache=cache,
            on_notice=on_notice,
        ).result
        assert planned is not None  # a data command answers with its plan
        default = call.run.get("output_dir") or call.run.get("root") or "."
        line: str | None = format_command(call.command, call.options, run=call.run)
        plan = planned
    else:
        assert plan is not None
        _check_plan(plan)
        default, line = ".", None
    return _direct_script(
        writer, plan, line, target if target is not None else str(default)
    )


# --- the arguments --------------------------------------------------------------------


def _control(char: str) -> bool:
    """Say whether a character is a control character (no shell shows it as text)."""
    return ord(char) < 0x20 or ord(char) == 0x7F


def _writer(shell: object) -> "_Writer":
    """Return the writer of a shell.

    Raises
    ------
    ValidationError
        No shell, or one that is not ``bash`` or ``powershell``.
    """
    if shell is None:
        raise ValidationError(
            message("script.give_shell"), option="shell", allowed=SHELLS
        )
    if shell not in SHELLS:
        raise ValidationError(
            message("script.unknown_shell", shell=shell), option="shell", allowed=SHELLS
        )
    return _Bash() if shell == "bash" else _PowerShell()


def _data_call(command: str) -> CommandCall:
    """Return the call of a line of a data command.

    The line is only read: a path in it stays text (``validate_command`` would read a
    geometry file).

    Raises
    ------
    ValidationError
        A line ``parse_command`` refuses (its error, ``option`` ``command`` unless it
        names an option of the line), or the line of a command that is no data command.
    """
    try:
        call = parse_command(command)
    except ValidationError as error:
        if error.option is None and not error.options:
            error.option = "command"
        raise
    if declared_commands()[call.command].kind != "data":
        data = [c.id for c in declared_commands().values() if c.kind == "data"]
        raise ValidationError(
            message(
                "script.not_a_data_command",
                command=call.command,
                data_commands=", ".join(data),
            ),
            option="command",
            allowed=data,
        )
    return call


def _plain_name(name: str) -> bool:
    """Say whether ``name`` is a file name of its own on every system (no directory)."""
    return (
        bool(name)
        and name not in (".", "..")
        and not any(char in _NOT_IN_NAMES or _control(char) for char in name)
    )


def _web_url(url: str) -> bool:
    """Say whether ``url`` is an ``http`` or ``https`` URL without spaces."""
    if any(char.isspace() or _control(char) for char in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _check_plan(plan: UpdatePlan) -> None:
    """Check a saved plan before a script is written of it.

    Raises
    ------
    ValidationError
        A position of a plan of 0.9.0 (without ``source``, ``fetch`` and
        ``fetch_reason``), or a file to download whose name is no plain file name,
        whose URL is not ``http`` or ``https`` or whose SHA-256 is not 64 hexadecimal
        digits (``option`` ``plan``).
    """
    for item in plan.items:
        if (
            item.track != "store"
            and item.source is None
            and item.fetch is None
            and item.fetch_reason is None
        ):
            raise ValidationError(
                message(
                    "script.plan_without_fetch",
                    name=item.name,
                    version=plan.kartograf_version,
                ),
                option="plan",
            )
        fetch = item.fetch
        if fetch is None or fetch.url is None:
            continue
        if not _plain_name(item.name):
            raise ValidationError(
                message("script.plan_file_name", name=item.name), option="plan"
            )
        if not _web_url(fetch.url):
            raise ValidationError(
                message("script.plan_url", url=fetch.url, name=item.name),
                option="plan",
            )
        if fetch.sha256 is not None and not _SHA256.fullmatch(fetch.sha256):
            raise ValidationError(
                message("script.plan_sha256", sha256=fetch.sha256, name=item.name),
                option="plan",
            )


# --- the Kartograf script -------------------------------------------------------------


def _release() -> str:
    """Return the version of the running Kartograf, a release whose tag a script pins.

    Raises
    ------
    UnsupportedError
        A development version (``development_version``).
    """
    import kartograf  # the package imports this module

    version = kartograf.__version__
    if not _RELEASE.fullmatch(version):
        raise UnsupportedError(
            message("script.development_version", version=version),
            reason="development_version",
            version=version,
            hint=message("script.development_version_hint"),
        )
    return version


def _keys(call: CommandCall) -> tuple[_Key, ...]:
    """Return the keys of the keyed sources of the product of a call, each once.

    From ``auth`` of the sources ``list_sources`` gives the group and the product of
    the call; a call without the product its command takes has none (Kartograf
    refuses the line).
    """
    declaration = declared_commands()[call.command]
    if declaration.group not in SOURCE_GROUPS:
        return ()
    product = call.options.get("product")
    if product is None and any(p.name == "product" for p in declaration.call_options):
        return ()
    sources = list_sources(
        group=declaration.group, product=None if product is None else str(product)
    ).sources
    return tuple(
        dict.fromkeys(_KEYS[source.auth] for source in sources if source.auth != "none")
    )


def _kartograf_script(writer: "_Writer", call: CommandCall) -> ScriptResult:
    """Return the Kartograf script of a call (decision 5 (b))."""
    version = _release()
    line = format_command(call.command, call.options, run=call.run)
    keys = _keys(call)
    header = [
        *_wrapped(message("script.generated", version=build_version())),
        *_wrapped(message("script.kartograf_runs", version=version)),
        f"  {line}",
        *_wrapped(message("script.kartograf_steps", version=version)),
    ]
    if keys:
        variables = [key.variable for key in keys]
        header += _wrapped(message("script.kartograf_keys", variables=variables))
    text = writer.kartograf(
        header,
        version=version,
        pin=f"kartograf @ git+{REPOSITORY}@v{version}",
        keys=keys,
        arguments=_arguments(call, line),
    )
    return ScriptResult(writer.shell, "kartograf", text)


def _arguments(call: CommandCall, line: str) -> list[tuple[str, bool]]:
    """Return the words of a line after ``kartograf``, each with whether it is a path.

    A path is the value of a flag of a ``path`` or ``plan`` parameter (the line has
    them as ``--flag value``): the shell reads a leading ``~`` of it.
    """
    declaration = declared_commands()[call.command]
    flags = {
        flag
        for param in declaration.params
        if param.kind in ("path", "plan")
        for flag in (param.cli_flag, param.short)
        if flag is not None
    }
    words = shlex.split(line)[1:]
    return [
        (word, index > 0 and words[index - 1] in flags)
        for index, word in enumerate(words)
    ]


# --- the direct script ----------------------------------------------------------------


def _left_out(item: PlanItem) -> str | None:
    """Return why a direct script leaves a position out (``None``: it downloads it)."""
    if item.status == "check_failed":
        return "check_failed"
    if item.action == "conflict":
        return item.reason or "conflict"
    if item.fetch is None or item.fetch.url is None:
        return item.fetch_reason or "no_url"
    return None


def _direct_items(
    plan: UpdatePlan,
) -> tuple[tuple[PlanItem, ...], tuple[LeftOutFile, ...]]:
    """Return the positions a direct script downloads and the files it leaves out.

    In the order of the plan. The plan's own ``ATTRIBUTION.txt`` is neither: the script
    writes its own. Two files to download of one name are ``duplicate_output_name`` (a
    store plan has them in other directories; a plain plan judged them already).
    """
    items = [item for item in plan.items if item.name != ATTRIBUTION_FILE]
    reasons = [_left_out(item) for item in items]
    names = Counter(
        item.name for item, why in zip(items, reasons, strict=True) if why is None
    )
    downloaded: list[PlanItem] = []
    left_out: list[LeftOutFile] = []
    for item, why in zip(items, reasons, strict=True):
        if why is None and names[item.name] > 1:
            why = "duplicate_output_name"
        if why is not None:
            left_out.append(LeftOutFile(item.name, item.unit, why))
            continue
        downloaded.append(item)
    return tuple(downloaded), tuple(left_out)


def _script_file(item: PlanItem) -> ScriptFile:
    """Return the file a direct script downloads for a position with a URL."""
    assert item.fetch is not None and item.fetch.url is not None
    sha256 = item.fetch.sha256
    return ScriptFile(
        name=item.name,
        unit=item.unit,
        url=item.fetch.url,
        size_bytes=item.fetch.size_bytes,
        sha256=None if sha256 is None else sha256.lower(),
        source=item.source,
    )


def _attribution(items: Iterable[PlanItem]) -> tuple[str, ...]:
    """Return the lines of ``ATTRIBUTION.txt`` of the files of ``items``, each once.

    The provider lines of DEV §20 of the positions (``kartograf.download.plan``,
    ``plan_lines``): G, SG and Z with the products and the years the plan names, the
    registry text of a source the table holds no row for, the attribution lines before
    the terms lines. The day of the download of G and Z is ``b.d.`` here: the writer
    of a shell puts the day the script runs in its place (``date_parts``), and the
    script appends each line the file lacks, so a rerun on another day adds its own
    G or Z line instead of joining it with the earlier one (ADR-064). The files of
    CAMELS-PL, whose provider lines Kartograf has, are never downloaded directly
    (``built``, ADR-063 erratum 1).
    """
    return plan_lines(items)


def _why(file: LeftOutFile) -> str:
    """Return the text of why a file is left out."""
    key = _WHY.get(file.reason)
    if key is None:
        return message("script.why_conflict", reason=file.reason)
    return message(key)


def _direct_script(
    writer: "_Writer", plan: UpdatePlan, line: str | None, target: str
) -> ScriptResult:
    """Return the direct script of a plan (decision 5 (c)).

    Raises
    ------
    UnsupportedError
        No file of the plan is the bytes of a URL (``no_direct_files``).
    """
    downloaded, left_out = _direct_items(plan)
    files = tuple(_script_file(item) for item in downloaded)
    if not files:
        reasons = ", ".join(dict.fromkeys(file.reason for file in left_out))
        raise UnsupportedError(
            message("script.no_direct_files", count=len(left_out), reasons=reasons),
            reason="no_direct_files",
            option="direct",
            files=left_out,
        )
    header = _wrapped(message("script.generated", version=build_version()))
    if line is not None:
        header += _wrapped(message("script.direct_command", checked_at=plan.checked_at))
        header.append(f"  {line}")
    else:
        header += _wrapped(
            message(
                "script.direct_plan",
                checked_at=plan.checked_at,
                version=plan.kartograf_version,
            )
        )
    header += _wrapped(message("script.direct_does", tool=writer.tool))
    header += _wrapped(message("script.direct_does_not"))
    if left_out:
        header += _wrapped(message("script.direct_left_out", count=len(left_out)))
        for file in left_out:
            header += _wrapped(
                message(
                    "script.left_out_file",
                    name=file.name,
                    unit=file.unit,
                    why=_why(file),
                ),
                indent="  ",
            )
    text = writer.direct(
        header,
        target=target,
        files=files,
        lines=_attribution(downloaded),
    )
    return ScriptResult(writer.shell, "direct", text, files, left_out, plan.notices)


def _wrapped(text: str, indent: str = "") -> list[str]:
    """Return a text of the header as lines of a comment (without ``# ``)."""
    return textwrap.wrap(
        text,
        width=_WIDTH - 2,
        initial_indent=indent,
        subsequent_indent=indent * 2,
        break_long_words=False,
        break_on_hyphens=False,
    )


# --- the shells -----------------------------------------------------------------------


def _said(text: str) -> str:
    """Return a text a script prints when it runs, between double quotes.

    The text is an English message; a value is the ``${name}`` of a variable of the
    script, which both shells expand between double quotes. The texts hold no ``"``,
    ``$``, backtick or backslash of their own.
    """
    return f'"{text}"'


class _Writer(Protocol):
    """The writer of the scripts of one shell."""

    shell: Shell
    tool: str

    def kartograf(
        self,
        header: Sequence[str],
        *,
        version: str,
        pin: str,
        keys: Sequence[_Key],
        arguments: Sequence[tuple[str, bool]],
    ) -> str:
        """Return the text of the Kartograf script."""
        ...

    def direct(
        self,
        header: Sequence[str],
        *,
        target: str,
        files: Sequence[ScriptFile],
        lines: Sequence[str],
    ) -> str:
        """Return the text of the direct script."""
        ...


def _comment(text: str) -> str:
    """Return a header line as a comment: a control character is written as its code."""
    shown = "".join(f"\\x{ord(char):02x}" if _control(char) else char for char in text)
    return f"# {shown}".rstrip()


def _bash_quoted(text: str) -> str:
    """Return a word of bash that is ``text``: bare, single-quoted or ``$'...'``."""
    if _BARE.fullmatch(text):
        return text
    if not any(_control(char) for char in text):
        return "'" + text.replace("'", "'\\''") + "'"
    escaped = "".join(
        f"\\x{ord(char):02x}"
        if _control(char)
        else "\\" + char
        if char in "\\'"
        else char
        for char in text
    )
    return f"$'{escaped}'"


def _bash_path(text: str) -> str:
    """Return a path for bash: a leading ``~`` is left for the shell to expand."""
    if text == "~":
        return "~"
    if text.startswith("~/"):
        rest = text[2:]
        return "~/" + _bash_quoted(rest) if rest else "~/"
    return _bash_quoted(text)


def _bash_line(line: str) -> str:
    """Return a provider line for bash: ``$day`` is the day of its download.

    A line whose row names the day of the download (``date_parts``: G, Z) is its text
    before that value, the ``$day`` the script sets when it runs and its text after
    it, in one word; another line is its text.
    """
    parts = date_parts(line)
    if parts is None:
        return _bash_quoted(line)
    before, after = parts
    return f'{_bash_quoted(before)}"$day"{_bash_quoted(after)}'


class _Bash:
    """The scripts of bash (``curl`` downloads)."""

    shell: Shell = "bash"
    tool = "curl"

    def kartograf(
        self,
        header: Sequence[str],
        *,
        version: str,
        pin: str,
        keys: Sequence[_Key],
        arguments: Sequence[tuple[str, bool]],
    ) -> str:
        words = " ".join(
            _bash_path(word) if path else _bash_quoted(word) for word, path in arguments
        )
        lines = [
            "#!/usr/bin/env bash",
            *(_comment(row) for row in header),
            "set -euo pipefail",
            "",
            f"version={_bash_quoted(version)}",
            f"pin={_bash_quoted(pin)}",
            f"arguments=({words})",
            "",
            "if ! command -v uv >/dev/null 2>&1; then",
            f"  echo {_said(message('script.uv_missing', guide=UV_GUIDE))} >&2",
            "  exit 1",
            "fi",
        ]
        for key in keys:
            unset = f'[ -z "${{{key.variable}:-}}" ]'
            if key.keychain is not None:
                found = (
                    '{ [ "$(uname -s)" = Darwin ] && security find-generic-password '
                    f"-s {_bash_quoted(key.keychain)} >/dev/null 2>&1; }}"
                )
                unset = f"{unset} && ! {found}"
            lines += [
                f"if {unset}; then",
                "  echo "
                + _said(message("script.key_missing", variable=key.variable))
                + " >&2",
                "  exit 1",
                "fi",
            ]
        lines += [
            "if ! command -v kartograf >/dev/null 2>&1; then",
            '  uv tool install "$pin"',
            "fi",
            "installed=$(kartograf --version 2>/dev/null || true)",
            'if [ "$installed" = "kartograf $version" ]; then',
            '  exec kartograf "${arguments[@]}"',
            "fi",
            'exec uvx --from "$pin" kartograf "${arguments[@]}"',
        ]
        return "\n".join(lines) + "\n"

    def direct(
        self,
        header: Sequence[str],
        *,
        target: str,
        files: Sequence[ScriptFile],
        lines: Sequence[str],
    ) -> str:
        script = [
            "#!/usr/bin/env bash",
            *(_comment(row) for row in header),
            "set -euo pipefail",
            "",
            f"target={_bash_path(target)}",
            "",
            "if ! command -v curl >/dev/null 2>&1; then",
            f"  echo {_said(message('script.curl_missing'))} >&2",
            "  exit 1",
            "fi",
            'mkdir -p -- "$target"',
            "",
            "fetch() {",
            "  local name=$1 url=$2 size=$3 sha256=$4",
            '  local part="$target/$name.part"',
            f"  echo {_said(message('script.downloading', name='${name}'))}",
            "  if ! curl --fail --location --silent --show-error \\",
            "      --proto '=http,https' --proto-redir '=http,https' \\",
            '      --output "$part" "$url"; then',
            '    rm -f -- "$part"',
            "    exit 1",
            "  fi",
            '  if [ -n "$size" ]; then',
            "    local actual",
            '    actual=$(wc -c < "$part")',
            "    actual=$((actual))",
            '    if [ "$actual" -ne "$size" ]; then',
            '      rm -f -- "$part"',
            "      echo "
            + _said(
                message(
                    "script.size_differs",
                    name="${name}",
                    actual="${actual}",
                    size="${size}",
                )
            )
            + " >&2",
            "      exit 1",
            "    fi",
            "  fi",
            '  if [ -n "$sha256" ]; then',
            "    local sum",
            "    if command -v sha256sum >/dev/null 2>&1; then",
            '      sum=$(sha256sum < "$part")',
            "    else",
            '      sum=$(shasum -a 256 < "$part")',
            "    fi",
            '    if [ "${sum%% *}" != "$sha256" ]; then',
            '      rm -f -- "$part"',
            "      echo "
            + _said(
                message("script.sha256_differs", name="${name}", sha256="${sha256}")
            )
            + " >&2",
            "      exit 1",
            "    fi",
            "  fi",
            '  mv -f -- "$part" "$target/$name"',
            "}",
            "",
        ]
        script += [
            "fetch "
            + " ".join(
                _bash_quoted(value)
                for value in (
                    file.name,
                    file.url,
                    "" if file.size_bytes is None else str(file.size_bytes),
                    file.sha256 or "",
                )
            )
            for file in files
        ]
        if lines:
            script += [
                "",
                f'attribution="$target/{ATTRIBUTION_FILE}"',
                'touch -- "$attribution"',
            ]
            if any(date_parts(row) is not None for row in lines):
                script.append("day=$(date -u +%F)")
            script += [
                "for line in " + " ".join(_bash_line(row) for row in lines) + "; do",
                (
                    '  grep -qxF -- "$line" "$attribution" '
                    '|| printf \'%s\\n\' "$line" >> "$attribution"'
                ),
                "done",
            ]
        script.append(
            "echo "
            + _said(message("script.downloaded", count=len(files), target="${target}"))
        )
        return "\n".join(script) + "\n"


def _ps_quoted(text: str) -> str:
    """Return a PowerShell expression of ``text`` in ASCII.

    A single-quoted string; any character that is not printable ASCII is its code
    (``[char]0x0142``) in a sum of strings, which Windows PowerShell 5.1 reads whatever
    the code page of the system.
    """
    parts: list[str] = []
    run = ""
    for char in text:
        if " " <= char <= "~":
            run += char
            continue
        if run:
            parts.append("'" + run.replace("'", "''") + "'")
            run = ""
        code = ord(char)
        parts.append(
            f"[char]0x{code:04X}"
            if code <= 0xFFFF
            else f"[char]::ConvertFromUtf32(0x{code:X})"
        )
    if run or not parts:
        parts.append("'" + run.replace("'", "''") + "'")
    if len(parts) == 1 and parts[0].startswith("'"):
        return parts[0]
    if not parts[0].startswith("'"):
        parts.insert(0, "''")  # a sum that starts with a string is a string
    return "(" + " + ".join(parts) + ")"


def _ps_path(text: str) -> str:
    """Return a path for PowerShell: a leading ``~`` is the home directory."""
    if text == "~":
        return "$HOME"
    if text.startswith("~/"):
        return f"(Join-Path $HOME {_ps_quoted(text[2:])})"
    return _ps_quoted(text)


def _ps_line(line: str) -> str:
    """Return a provider line for PowerShell: ``$day`` is the day of its download.

    A line whose row names the day of the download (``date_parts``: G, Z) is the sum
    of its text before that value, the ``$day`` the script sets when it runs and its
    text after it; another line is its text.
    """
    parts = date_parts(line)
    if parts is None:
        return _ps_quoted(line)
    before, after = parts
    return f"({_ps_quoted(before)} + $day + {_ps_quoted(after)})"


def _ps_comment(text: str) -> str:
    """Return a header line as an ASCII comment (another character is its escape)."""
    return _comment(text.encode("ascii", "backslashreplace").decode("ascii"))


class _PowerShell:
    """The scripts of PowerShell (``Invoke-WebRequest`` downloads)."""

    shell: Shell = "powershell"
    tool = "Invoke-WebRequest"

    def kartograf(
        self,
        header: Sequence[str],
        *,
        version: str,
        pin: str,
        keys: Sequence[_Key],
        arguments: Sequence[tuple[str, bool]],
    ) -> str:
        words = ", ".join(
            _ps_path(word) if path else _ps_quoted(word) for word, path in arguments
        )
        lines = [
            *(_ps_comment(row) for row in header),
            "$ErrorActionPreference = 'Stop'",
            "",
            f"$version = {_ps_quoted(version)}",
            f"$pin = {_ps_quoted(pin)}",
            f"$arguments = @({words})",
            "",
            "if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {",
            "    [Console]::Error.WriteLine("
            + _said(message("script.uv_missing", guide=UV_GUIDE))
            + ")",
            "    exit 1",
            "}",
        ]
        if any(key.keychain is not None for key in keys):
            lines += [
                "function Test-Keychain([string]$service) {",
                "    if (-not $IsMacOS) { return $false }",
                "    try {",
                "        $null = & security find-generic-password -s $service *>&1",
                "        return $LASTEXITCODE -eq 0",
                "    } catch {",
                "        return $false",
                "    }",
                "}",
            ]
        for key in keys:
            unset = f"-not $env:{key.variable}"
            if key.keychain is not None:
                unset += f" -and -not (Test-Keychain {_ps_quoted(key.keychain)})"
            lines += [
                f"if ({unset}) {{",
                "    [Console]::Error.WriteLine("
                + _said(message("script.key_missing", variable=key.variable))
                + ")",
                "    exit 1",
                "}",
            ]
        lines += [
            "if (-not (Get-Command kartograf -ErrorAction SilentlyContinue)) {",
            "    & uv tool install $pin",
            "    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            "}",
            "$installed = ''",
            "if (Get-Command kartograf -ErrorAction SilentlyContinue) {",
            "    $installed = (& kartograf --version | Out-String).Trim()",
            "}",
            'if ($installed -eq "kartograf ${version}") {',
            "    & kartograf @arguments",
            "} else {",
            "    & uvx --from $pin kartograf @arguments",
            "}",
            "exit $LASTEXITCODE",
        ]
        return "\n".join(lines) + "\n"

    def direct(
        self,
        header: Sequence[str],
        *,
        target: str,
        files: Sequence[ScriptFile],
        lines: Sequence[str],
    ) -> str:
        script = [
            *(_ps_comment(row) for row in header),
            "$ErrorActionPreference = 'Stop'",
            "$ProgressPreference = 'SilentlyContinue'",
            "",
            f"$target = {_ps_path(target)}",
            "$null = New-Item -ItemType Directory -Force -Path $target",
            "$target = (Resolve-Path -LiteralPath $target).ProviderPath",
            "",
            (
                "function Get-PlanFile([string]$name, [string]$url, $size, "
                "[string]$sha256) {"
            ),
            "    $part = Join-Path $target ($name + '.part')",
            f"    Write-Host {_said(message('script.downloading', name='${name}'))}",
            "    try {",
            "        Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing",
            "    } catch {",
            (
                "        Remove-Item -LiteralPath $part -Force "
                "-ErrorAction SilentlyContinue"
            ),
            "        throw",
            "    }",
            "    if ($null -ne $size) {",
            "        $actual = (Get-Item -LiteralPath $part).Length",
            "        if ($actual -ne $size) {",
            "            Remove-Item -LiteralPath $part -Force",
            "            [Console]::Error.WriteLine("
            + _said(
                message(
                    "script.size_differs",
                    name="${name}",
                    actual="${actual}",
                    size="${size}",
                )
            )
            + ")",
            "            exit 1",
            "        }",
            "    }",
            "    if ($sha256) {",
            (
                "        $actual = (Get-FileHash -LiteralPath $part -Algorithm SHA256)"
                ".Hash.ToLowerInvariant()"
            ),
            "        if ($actual -ne $sha256) {",
            "            Remove-Item -LiteralPath $part -Force",
            "            [Console]::Error.WriteLine("
            + _said(
                message("script.sha256_differs", name="${name}", sha256="${sha256}")
            )
            + ")",
            "            exit 1",
            "        }",
            "    }",
            (
                "    Move-Item -LiteralPath $part "
                "-Destination (Join-Path $target $name) -Force"
            ),
            "}",
            "",
        ]
        script += [
            "Get-PlanFile "
            + " ".join(
                (
                    _ps_quoted(file.name),
                    _ps_quoted(file.url),
                    "$null" if file.size_bytes is None else str(file.size_bytes),
                    _ps_quoted(file.sha256 or ""),
                )
            )
            for file in files
        ]
        if lines:
            script += [
                "",
                f"$attribution = Join-Path $target {_ps_quoted(ATTRIBUTION_FILE)}",
                "$utf8 = New-Object System.Text.UTF8Encoding $false",
                "$present = @()",
                "if (Test-Path -LiteralPath $attribution) {",
                "    $present = [IO.File]::ReadAllLines($attribution, $utf8)",
                "}",
            ]
            if any(date_parts(row) is not None for row in lines):
                script.append(
                    "$day = [DateTime]::UtcNow.ToString('yyyy-MM-dd', "
                    "[Globalization.CultureInfo]::InvariantCulture)"
                )
            script += [
                "foreach ($line in @("
                + ", ".join(_ps_line(row) for row in lines)
                + ")) {",
                "    if ($present -cnotcontains $line) {",
                '        [IO.File]::AppendAllText($attribution, $line + "`n", $utf8)',
                "        $present += $line",
                "    }",
                "}",
            ]
        script.append(
            "Write-Host "
            + _said(message("script.downloaded", count=len(files), target="${target}"))
        )
        return "\n".join(script) + "\n"
