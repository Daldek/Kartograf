"""
The user environment of Kartograf: ``nogat.toml``, variables and user directories.

A setting comes from the first of: the command-line option, the environment
variable ``KARTOGRAF_<KEY>``, the shared variable ``NOGAT_<KEY>`` (only the
shared keys ``data_dir``, ``cache_dir`` and ``lang``), the section
``[kartograf]`` of ``nogat.toml``, the section ``[nogat]`` of it (shared keys
only) and the built-in default (DEV-18.1, ECO-028). An empty variable counts as
unset. The file is ``nogat.toml`` in ``platformdirs.user_config_path("nogat")``
or the path in ``NOGAT_CONFIG``; it is read with ``tomllib`` and its absence is
no error. The credential ``CLMS_CREDENTIALS`` comes from the environment only,
never from the file (DEV-18.4).

The settings are:

- ``root`` (``KARTOGRAF_ROOT``): the store, default ``<data_dir>/kartograf`` (DEV-19.2);
- ``data_dir`` (``KARTOGRAF_DATA_DIR``, ``NOGAT_DATA_DIR``): the parent of the
  stores, default the user data directory of ``nogat``;
- ``cache_dir`` (``KARTOGRAF_CACHE_DIR``, ``NOGAT_CACHE_DIR``): the parent of
  the caches, default the user cache directory of ``nogat``;
- ``lang`` (``KARTOGRAF_LANG``, ``NOGAT_LANG``): ``pl`` or ``en``, default ``pl``;
- ``debug`` (``KARTOGRAF_DEBUG``): print tracebacks and every library log record.

The command-line options of a call (there are none for these keys yet) go
before every layer here; ``get_config`` reports what the environment and the
file give. The library never writes into the current directory: the metadata
cache is ``<cache_dir>/kartograf/metadata.db`` (DEV-18.2).

Examples
--------
>>> from kartograf.config import get_config
>>> get_config().keys["lang"].value
'pl'
"""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Final, Literal

import platformdirs

from kartograf.exceptions import ConfigError, ValidationError
from kartograf.marker import MARKER
from kartograf.messages import Lang, Message, message
from kartograf.serialization import Document

__all__ = [
    "Config",
    "ConfigFile",
    "Setting",
    "StoreInfo",
    "StoreRoot",
    "cache_dir",
    "check_config",
    "config_file",
    "data_dir",
    "debug",
    "get_config",
    "human_language",
    "resolve",
    "resolve_root",
    "store_root",
]

APP: Final = "nogat"
TOOL: Final = "kartograf"
PREFIX: Final = "KARTOGRAF_"
SHARED_PREFIX: Final = "NOGAT_"
CONFIG_ENV: Final = "NOGAT_CONFIG"
CONFIG_FILENAME: Final = "nogat.toml"
SHARED_KEYS: Final[tuple[str, ...]] = ("data_dir", "cache_dir", "lang")
"""Keys of ``[nogat]`` and ``NOGAT_<KEY>``: the same for every tool of the ecosystem."""
KEYS: Final[tuple[str, ...]] = ("root", "data_dir", "cache_dir", "lang", "debug")
"""Every setting of Kartograf, in the order of ``config show``."""
PATH_KEYS: Final[tuple[str, ...]] = ("root", "data_dir", "cache_dir")
CREDENTIALS: Final[tuple[str, ...]] = ("CLMS_CREDENTIALS",)
"""Variables that only the environment may give (DEV-18.4); never printed."""
LANGUAGES: Final[tuple[str, ...]] = ("pl", "en")
DEFAULT_LANG: Final = "pl"
_FALSE_WORDS: Final = frozenset({"", "0", "false", "no", "off"})

SettingSource = Literal["default", "env", "file"]


@dataclass(frozen=True)
class ConfigFile:
    """
    The user's ``nogat.toml``, read once.

    Attributes
    ----------
    path : pathlib.Path
        Location of the file.
    source : {"default", "NOGAT_CONFIG"}
        Whether ``path`` is the platform default or comes from ``NOGAT_CONFIG``.
    exists : bool
        Whether the file exists.
    sections : Mapping of str to Mapping of str to object
        The tables ``nogat`` and ``kartograf`` (empty when the file is missing
        or unusable); the tables of other tools are not read.
    error : str or None
        Why the file cannot be used (unreadable, not UTF-8 text, invalid TOML,
        a section that is not a table, or a missing file named by
        ``NOGAT_CONFIG``); ``None`` when it is usable or simply absent.
    """

    path: Path
    source: Literal["default", "NOGAT_CONFIG"]
    exists: bool
    sections: Mapping[str, Mapping[str, Any]]
    error: str | None


@dataclass(frozen=True)
class Found:
    """
    A setting found outside the built-in default.

    Attributes
    ----------
    value : object
        The raw value (the text of a variable, the TOML value of a file).
    source : {"env", "file"}
        Where it was found.
    name : str
        The variable (``KARTOGRAF_ROOT``) or the table (``[kartograf]``).
    """

    value: Any
    source: Literal["env", "file"]
    name: str


@dataclass(frozen=True)
class Setting:
    """
    One setting with the layer that gave its value.

    Attributes
    ----------
    value : pathlib.Path, str or bool
        The value in force: a directory (``root``, ``data_dir``, ``cache_dir``;
        ``~`` expanded), ``pl`` or ``en`` (``lang``) or a flag (``debug``).
    source : {"default", "env", "file"}
        The layer: the built-in default, a variable or ``nogat.toml``.
    name : str or None
        The variable or the table that gave the value; ``None`` for the default.
    error : str or None
        Why the value cannot be used (``check_config`` raises it); ``None``
        when it is valid.
    """

    value: Path | str | bool
    source: SettingSource
    name: str | None
    error: str | None = None


@dataclass(frozen=True)
class IgnoredKey:
    """A key of ``[kartograf]`` that no setting uses (``config_file.ignored``)."""

    key: str
    reason: Literal["credential", "unknown"]


@dataclass(frozen=True)
class ConfigFileInfo:
    """
    The settings file as ``config show`` reports it.

    ``ignored`` lists the keys of ``[kartograf]`` that no setting uses: a
    credential (those come from the environment only) or an unknown key.
    """

    path: Path
    source: Literal["default", "NOGAT_CONFIG"]
    exists: bool
    error: str | None
    ignored: tuple[IgnoredKey, ...]


@dataclass(frozen=True)
class StoreInfo:
    """
    The store root with its source and size (DEV-18.6).

    Attributes
    ----------
    root : pathlib.Path
        The store root of DEV-19.2: ``root`` of the settings, else
        ``<data_dir>/kartograf``.
    source, name : str
        The layer of ``root`` and its variable or table (``None`` for the default).
    exists : bool
        Whether the root is a directory.
    size_bytes : int or None
        Bytes of the files below the root, a hard-linked file counted once;
        ``None`` while the directory does not exist.
    """

    root: Path
    source: SettingSource
    name: str | None
    exists: bool
    size_bytes: int | None


@dataclass(frozen=True)
class StoreRoot:
    """
    The default store root, resolved without reading the store (DEV-19.2).

    Attributes
    ----------
    root : pathlib.Path
        The store root: ``--root`` aside, ``KARTOGRAF_ROOT``, ``[kartograf] root``
        of ``nogat.toml``, else ``<data_dir>/kartograf``; ``~`` expanded.
    source : {"default", "env", "file"}
        The layer that gave the root.
    name : str or None
        The variable or the table that gave it; ``None`` for the default.
    marker_exists : bool
        Whether ``kartograf-store.json`` is a file in the root. The directory may
        be missing; then the marker does not exist either.
    """

    root: Path
    source: SettingSource
    name: str | None
    marker_exists: bool


@dataclass(frozen=True)
class Config(Document):
    """
    The settings in force and where each comes from (``kartograf-config/1``, DEV-18.6).

    Attributes
    ----------
    version : str
        The version of Kartograf.
    config_file : ConfigFileInfo
        The path of ``nogat.toml``, whether it exists, why it cannot be used
        and the keys of ``[kartograf]`` that nothing reads.
    keys : Mapping of str to Setting
        Every setting (``root``, ``data_dir``, ``cache_dir``, ``lang``,
        ``debug``) with its value, ``source`` and ``name``.
    credentials : Mapping of str to str
        Each credential variable as ``present`` or ``missing``; the value is
        never given.
    store : StoreInfo
        The store root with its source and size.
    """

    SCHEMA = "kartograf-config/1"
    JSON_KEYS = ("tool", "version", "config_file", "keys", "credentials", "store")
    JSON_FILL: ClassVar[Mapping[str, object]] = {"tool": TOOL}

    version: str
    config_file: ConfigFileInfo
    keys: Mapping[str, Setting]
    credentials: Mapping[str, Literal["present", "missing"]]
    store: StoreInfo


def default_data_dir() -> Path:
    """Return the default ``data_dir``: the user data directory of ``nogat``."""
    return Path(platformdirs.user_data_path(APP))


def default_cache_dir() -> Path:
    """Return the default ``cache_dir``: the user cache directory of ``nogat``."""
    return Path(platformdirs.user_cache_path(APP))


def config_file() -> ConfigFile:
    """
    Read ``nogat.toml`` (the file named by ``NOGAT_CONFIG`` or the default).

    Returns
    -------
    ConfigFile
        The file and its tables; ``error`` says why a file cannot be used (the
        tables are then empty), a missing default file is no error.
    """
    explicit = os.environ.get(CONFIG_ENV)
    source: Literal["default", "NOGAT_CONFIG"] = (
        "NOGAT_CONFIG" if explicit else "default"
    )
    path = (
        Path(explicit).expanduser()
        if explicit
        else Path(platformdirs.user_config_path(APP)) / CONFIG_FILENAME
    )

    def unusable(error: str | None, *, exists: bool) -> ConfigFile:
        return ConfigFile(path, source, exists, {}, error)

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # A missing default file is the normal case; a named one is a mistake.
        missing = message("config.file_missing") if explicit else None
        return unusable(missing, exists=False)
    except UnicodeDecodeError:
        return unusable(message("config.file_not_utf8"), exists=True)
    except OSError as error:
        return unusable(
            message("config.file_unreadable", error=error.strerror or str(error)),
            exists=True,
        )
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return unusable(
            message("config.file_invalid_toml", error=str(error)), exists=True
        )
    sections: dict[str, Mapping[str, Any]] = {}
    for name in (APP, TOOL):
        table = document.get(name, {})
        if not isinstance(table, dict):
            return unusable(message("config.section_not_table", name=name), exists=True)
        sections[name] = table
    return ConfigFile(path, source, True, sections, None)


def lookup(key: str) -> Found | None:
    """
    Find ``key`` in the environment and in ``nogat.toml``, in the order of DEV-18.1.

    Command-line options are not consulted here; they belong to the layer above.

    Parameters
    ----------
    key : str
        A setting name (``cache_dir``); the variables are ``KARTOGRAF_<KEY>``
        and, for a shared key, ``NOGAT_<KEY>``.

    Returns
    -------
    Found or None
        The first layer that holds a non-empty value, or ``None`` for the
        built-in default.
    """
    variables = [f"{PREFIX}{key.upper()}"]
    if key in SHARED_KEYS:
        variables.append(f"{SHARED_PREFIX}{key.upper()}")
    for variable in variables:
        if value := os.environ.get(variable):
            return Found(value, "env", variable)
    sections = config_file().sections
    for section, allowed in ((TOOL, True), (APP, key in SHARED_KEYS)):
        table = sections.get(section, {})
        if allowed and key in table and table[key] not in ("", None):
            return Found(table[key], "file", f"[{section}]")
    return None


def _flag(raw: object) -> bool:
    """Return a ``debug`` value as a flag (``0``, ``false``, ``no``, ``off``: off)."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int | float):
        return raw != 0
    return str(raw).strip().lower() not in _FALSE_WORDS


def _invalid(key: str, raw: object) -> Message | None:
    """Return why ``raw`` is not a valid value of ``key`` (``None``: it is valid)."""
    if key in PATH_KEYS:
        return None if isinstance(raw, str) else message("config.directory_not_text")
    if key == "lang":
        value = raw.strip().lower() if isinstance(raw, str) else raw
        if value not in LANGUAGES:
            return message("config.lang_not_allowed", languages=", ".join(LANGUAGES))
    elif key == "debug" and not isinstance(raw, str | bool | int):
        return message("config.debug_not_flag")
    return None


def _default(key: str) -> Path | str | bool:
    match key:
        case "data_dir":
            return default_data_dir()
        case "cache_dir":
            return default_cache_dir()
        case "root":
            return data_dir() / TOOL
        case "lang":
            return DEFAULT_LANG
        case _:
            return False


def resolve(key: str) -> Setting:
    """
    Resolve one setting by the order of DEV-18.1.

    Parameters
    ----------
    key : str
        One of ``KEYS``.

    Returns
    -------
    Setting
        The value in force and its source. A value that is not valid is not
        applied: the setting has the default and ``error`` says why the given
        value was dropped (``check_config`` raises it).

    Raises
    ------
    KeyError
        ``key`` is not a setting of Kartograf.
    """
    if key not in KEYS:
        raise KeyError(key)
    found = lookup(key)
    if found is None:
        return Setting(_default(key), "default", None)
    error = _invalid(key, found.value)
    if error is not None:
        error = message("config.setting_error", name=found.name, key=key, error=error)
        return Setting(_default(key), "default", None, error)
    value: Path | str | bool
    if key in PATH_KEYS:
        value = Path(found.value).expanduser()
    elif key == "lang":
        value = found.value.strip().lower()
    else:
        value = _flag(found.value)
    return Setting(value, found.source, found.name)


def _path(key: str) -> Path:
    return Path(str(resolve(key).value))


def data_dir() -> Path:
    """Return ``data_dir``: the parent of the stores (``<data_dir>/kartograf``)."""
    return _path("data_dir")


def cache_dir() -> Path:
    """Return ``cache_dir``: the parent of the caches (``<cache_dir>/kartograf``)."""
    return _path("cache_dir")


def store_root() -> StoreRoot:
    """
    Return the default store root, its source and whether its marker exists.

    The read-only accessor of the default root that every Nogat producer
    exposes alike (DEV-19.2). It resolves the setting ``root`` by the order of
    DEV-18.1, as ``get_config`` does, and looks for one file, the marker. It
    never creates, lists or measures anything, so the cost does not grow with
    the store (``get_config().store`` measures the size).

    Returns
    -------
    StoreRoot
        ``root``, ``source`` (``default``, ``env`` or ``file``), ``name`` (the
        variable or the table) and ``marker_exists``.

    Examples
    --------
    >>> default = store_root()
    >>> default.marker_exists in (True, False)
    True
    """
    setting = resolve("root")
    root = Path(str(setting.value))
    return StoreRoot(root, setting.source, setting.name, (root / MARKER).is_file())


def resolve_root(root: str | os.PathLike[str] | None) -> Path:
    """
    Return the store root of a call: the one it names, else the default root.

    The default is ``store_root()`` (DEV-19.2): ``KARTOGRAF_ROOT``, ``[kartograf]
    root`` of ``nogat.toml``, else ``<data_dir>/kartograf``. Every entry point
    that writes or reads the store resolves its ``root`` here, so a call without
    one never fails for the lack of it.

    Parameters
    ----------
    root : str or os.PathLike or None
        The store the caller names (``--root``, the argument ``root``); None for
        none.

    Returns
    -------
    pathlib.Path
        ``root`` as given (a relative path stays relative to the working
        directory), or the default root (absolute).

    Raises
    ------
    ValidationError
        ``root`` is an empty string (``details.option`` is ``root``).

    Examples
    --------
    >>> resolve_root("data").as_posix()
    'data'
    """
    if root is None:
        return store_root().root
    if not os.fspath(root):
        raise ValidationError(message("config.empty_root"), option="root")
    return Path(root)


def debug() -> bool:
    """Return whether ``KARTOGRAF_DEBUG`` (or ``debug`` of the file) is on."""
    return bool(resolve("debug").value)


def human_language(explicit: str | None = None) -> Lang:
    """Return the language of the output for people (AGI-9.2, DEV-18.1).

    Parameters
    ----------
    explicit : str, optional
        The language of the command line (``--lang``); the first of the layers.
        A value that is no language is ignored (the parser of the CLI refuses it).

    Returns
    -------
    {"pl", "en"}
        ``explicit``, else the setting ``lang`` (``KARTOGRAF_LANG``,
        ``NOGAT_LANG``, ``nogat.toml``), else ``pl``. A setting that is not valid
        counts as ``pl`` here; ``check_config`` reports it.
    """
    chosen = explicit.strip().lower() if explicit is not None else None
    if chosen in LANGUAGES:
        return "en" if chosen == "en" else "pl"
    return "en" if resolve("lang").value == "en" else "pl"


def check_config() -> None:
    """
    Reject settings that exist but cannot be used.

    Raises
    ------
    ConfigError
        ``nogat.toml`` is unreadable, not UTF-8 text, not valid TOML, has a
        section that is not a table, or ``NOGAT_CONFIG`` names a file that does
        not exist (``details.path``); or a setting has a value that is not
        valid (``details.option``, ``details.value``). Either way
        ``details.reason`` is ``invalid_config``.
    """
    file = config_file()
    if file.error is not None:
        raise ConfigError(
            message("config.file_unusable", path=file.path, error=file.error),
            option=CONFIG_ENV if file.source == CONFIG_ENV else CONFIG_FILENAME,
            path=file.path,
        )
    for key in KEYS:
        setting = resolve(key)
        if setting.error is not None:
            found = lookup(key)
            assert found is not None
            raise ConfigError(
                message("config.setting_invalid", error=setting.error),
                option=found.name if found.source == "env" else f"{found.name} {key}",
                value=str(found.value),
                allowed=LANGUAGES if key == "lang" else None,
                path=file.path if found.source == "file" else None,
            )


def _tree_size(root: Path) -> int:
    """Return the bytes of the files below ``root``; a hard-linked file counts once."""
    total = 0
    seen: set[tuple[int, int]] = set()
    pending = [root]
    while pending:
        try:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        info = entry.stat(follow_symlinks=False)
                        if info.st_nlink > 1:
                            identity = (info.st_dev, info.st_ino)
                            if identity in seen:
                                continue
                            seen.add(identity)
                        total += info.st_size
        except OSError:
            continue  # a directory that vanished or cannot be listed
    return total


def get_config() -> Config:
    """
    Report the settings in force and where each comes from (DEV-18.6).

    The command-line options of a call apply to that call only and are not
    part of the report: it shows what the environment and ``nogat.toml`` give.
    A settings file that cannot be used is reported (``config_file.error``)
    instead of raised, so the report can be used to repair it.

    Returns
    -------
    Config
        The document ``kartograf-config/1``: ``config_file``, ``keys``,
        ``credentials`` (``present`` or ``missing``, never the value) and
        ``store`` (the root with its source, existence and size).

    Examples
    --------
    >>> report = get_config()
    >>> report.store.root == report.keys["root"].value
    True
    """
    from kartograf import __version__  # the package imports this module

    file = config_file()
    keys = {key: resolve(key) for key in KEYS}
    ignored = tuple(
        IgnoredKey(key, "credential" if key.upper() in CREDENTIALS else "unknown")
        for key in file.sections.get(TOOL, {})
        if key not in KEYS or key.upper() in CREDENTIALS
    )
    root = keys["root"]
    path = Path(str(root.value))
    exists = path.is_dir()
    return Config(
        version=__version__,
        config_file=ConfigFileInfo(
            file.path, file.source, file.exists, file.error, ignored
        ),
        keys=keys,
        credentials={
            name: "present" if os.environ.get(name) else "missing"
            for name in CREDENTIALS
        },
        store=StoreInfo(
            root=path,
            source=root.source,
            name=root.name,
            exists=exists,
            size_bytes=_tree_size(path) if exists else None,
        ),
    )
