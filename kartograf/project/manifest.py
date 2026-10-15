"""The project file ``kartograf-project.json`` (``kartograf-project/1``, ADR-040).

Reading validates the whole structure and names the place of an error
(``ValidationError``: ``kartograf-project.json: zadanie teren: files[2].version:
...``). Writing is atomic - a temporary file in the project directory,
``fsync``, ``os.replace``, ``fsync`` of the directory - under a short
directory lock ``.kartograf-project.lock`` (``mkdir``, owner file with host,
pid and time) held only for read-merge-write and never taken over.
``commit_tasks`` merges per task: a task changed by another process since
the operation read it is a conflict and is left as it is. No SQLite and no
byte-range locks: the project may live on a network share (SCOPE 3.3).

The file is always written in one form (spec 3.3): keys in the order of the
format, options in the order of the command's options, 2-space indentation,
UTF-8 and a newline at the end.
"""

import errno
import json
import os
import re
import socket
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import NoReturn

from kartograf import _clock
from kartograf.exceptions import ValidationError
from kartograf.project.commands import COMMANDS, check_options_json, data_commands_text
from kartograf.project.model import PinnedFile, Project, ProjectTask

MANIFEST_NAME = "kartograf-project.json"
PROJECT_SCHEMA = "kartograf-project/1"
LOCK_NAME = ".kartograf-project.lock"
# A busy lock is retried every LOCK_RETRY_S seconds for LOCK_TIMEOUT_S.
LOCK_TIMEOUT_S = 5.0
LOCK_RETRY_S = 0.1

TASK_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
TASK_NAME_RULE = (
    "male litery, cyfry, '-' i '_', na poczatku litera albo cyfra, do 64 znakow"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_TOP_KEYS = ("schema", "output_dir", "tasks")
_TASK_KEYS = ("name", "command", "options", "pinned_at", "kartograf_version", "files")
_FILE_KEYS = ("role", "unit", "path", "version", "label", "sha256", "size_bytes")
_ROLES = ("output", "raw", "input")
_VERSIONS = "versions"
_INCOMING = ".incoming"


class _Invalid(Exception):
    """A manifest error at ``where`` (raised as ``ValidationError``)."""

    def __init__(self, where: str, problem: str) -> None:
        super().__init__(f"{where}: {problem}" if where else problem)


def _fail(where: str, problem: str) -> NoReturn:
    raise _Invalid(where, problem)


def manifest_path(project_dir: str | Path) -> Path:
    """``<project_dir>/kartograf-project.json`` (absolute)."""
    return absolute(project_dir) / MANIFEST_NAME


def absolute(path: str | Path) -> Path:
    """An absolute path without ``.``/``..`` (symlinks kept)."""
    return Path(os.path.abspath(path))


def resolve_path(text: str, project_dir: Path) -> Path:
    """A path of the manifest: relative to the project directory, or absolute."""
    path = Path(text)
    return path if path.is_absolute() else absolute(project_dir / path)


# =============================================================================
# Reading
# =============================================================================


def read_manifest(project_dir: str | Path) -> tuple[Project, dict[str, dict]]:
    """The project and the JSON state of each task at reading (for merging).

    Raises
    ------
    ValidationError
        No manifest in ``project_dir``, unreadable file or invalid content
        (the message names the place).
    """
    directory = absolute(project_dir)
    doc = _load(directory)
    return _project(directory, doc), {task["name"]: task for task in doc["tasks"]}


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    data: dict = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"powtorzony klucz {key!r}")
        data[key] = value
    return data


def _no_constant(name: str) -> NoReturn:
    raise ValueError(f"niedozwolona wartosc {name}")


def _load(directory: Path) -> dict:
    """Read and validate the manifest of ``directory``."""
    path = directory / MANIFEST_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValidationError(
            f"brak projektu w {directory} ({MANIFEST_NAME}); utworz: kartograf "
            "project init --output KATALOG albo wskaz --project KATALOG"
        ) from None
    except (OSError, UnicodeDecodeError) as e:
        raise ValidationError(f"{MANIFEST_NAME}: nie mozna odczytac {path}: {e}") from e
    try:
        doc = json.loads(
            text, object_pairs_hook=_unique_keys, parse_constant=_no_constant
        )
    except ValueError as e:
        raise ValidationError(f"{MANIFEST_NAME}: nieprawidlowy JSON: {e}") from e
    validate_manifest(doc)
    return doc


def validate_manifest(doc: object) -> None:
    """Validate a parsed manifest (the whole structure, spec 3.3).

    Raises
    ------
    ValidationError
        ``kartograf-project.json: <place>: <problem>``.
    """
    try:
        _validate(doc)
    except _Invalid as e:
        raise ValidationError(f"{MANIFEST_NAME}: {e}") from None


def _keys(obj: dict, required: tuple[str, ...], optional: tuple[str, ...], where: str):
    for key in obj:
        if key not in required and key not in optional:
            _fail(where, f"nieznany klucz {key!r}")
    for key in required:
        if key not in obj:
            _fail(where, f"brak klucza {key!r}")


def _validate(doc: object) -> None:
    if not isinstance(doc, dict):
        _fail("", "oczekiwano obiektu JSON")
    if "schema" not in doc:
        _fail("", "brak klucza 'schema'")
    if doc["schema"] != PROJECT_SCHEMA:
        _fail(
            "",
            f"nieznany schemat {doc['schema']!r} (ten Kartograf zna "
            f"{PROJECT_SCHEMA}); zaktualizuj Kartografa",
        )
    _keys(doc, _TOP_KEYS, (), "")
    if not isinstance(doc["output_dir"], str) or not doc["output_dir"]:
        _fail("output_dir", "oczekiwano niepustej sciezki magazynu")
    tasks = doc["tasks"]
    if not isinstance(tasks, list):
        _fail("tasks", "oczekiwano listy zadan")
    names: set[str] = set()
    for index, task in enumerate(tasks):
        _validate_task(task, index, names)


def _validate_task(task: object, index: int, names: set[str]) -> None:
    if not isinstance(task, dict):
        _fail(f"tasks[{index}]", "oczekiwano obiektu zadania")
    name = task.get("name")
    valid_name = isinstance(name, str) and TASK_NAME.fullmatch(name) is not None
    where = f"zadanie {name}" if valid_name else f"tasks[{index}]"
    _keys(task, _TASK_KEYS, ("geometry_sha256",), where)
    if not valid_name:
        _fail(where, f"nieprawidlowa nazwa zadania {name!r} ({TASK_NAME_RULE})")
    assert isinstance(name, str)
    if name in names:
        _fail(where, "nazwa zadania powtorzona")
    names.add(name)
    raw_command = task["command"]
    command = COMMANDS.get(raw_command) if isinstance(raw_command, str) else None
    if command is None:
        _fail(
            where,
            f"nieznana komenda {raw_command!r} (komendy danych: "
            f"{data_commands_text()})",
        )
    error = check_options_json(command, task["options"])
    if error is not None:
        _fail(where, error)
    pinned_at, version = task["pinned_at"], task["kartograf_version"]
    if pinned_at is None and version is None:
        pinned = False
    elif isinstance(pinned_at, str) and isinstance(version, str) and version:
        pinned = True
        try:
            datetime.fromisoformat(pinned_at)
        except ValueError:
            _fail(where, f"pinned_at: oczekiwano chwili ISO 8601, podano {pinned_at!r}")
    else:
        _fail(
            where,
            "pinned_at i kartograf_version: oba null (zadanie niepobrane) albo "
            "oba napisy (zadanie przypiete)",
        )
    files = task["files"]
    if not isinstance(files, list):
        _fail(where, "files: oczekiwano listy przypietych plikow")
    if pinned != bool(files):
        _fail(
            where,
            "files: zadanie przypiete ma co najmniej jeden plik, a niepobrane "
            "(pinned_at null) - pusta liste",
        )
    geometry = "geometry" in task["options"] and pinned
    if ("geometry_sha256" in task) != geometry:
        _fail(
            where,
            "geometry_sha256: dokladnie w zadaniu przypietym z options.geometry",
        )
    if geometry:
        digests = task["geometry_sha256"]
        if (
            not isinstance(digests, dict)
            or not digests
            or not all(
                isinstance(v, str) and _SHA256.fullmatch(v) for v in digests.values()
            )
        ):
            _fail(where, "geometry_sha256: oczekiwano obiektu {nazwa pliku: sha256}")
    versions: set[str] = set()
    for position, entry in enumerate(files):
        _validate_file(entry, f"{where}: files[{position}]")
        if entry["version"] in versions:
            _fail(f"{where}: files[{position}].version", "wersja przypieta dwa razy")
        versions.add(entry["version"])


def _store_path_problem(text: object) -> str | None:
    """Problem of a store-relative path of a pin (``None`` = valid)."""
    if not isinstance(text, str) or not text:
        return "oczekiwano niepustej sciezki wzglednej do magazynu"
    if "\\" in text or text.startswith("/") or re.match(r"[A-Za-z]:", text):
        return "sciezka musi byc wzgledna do magazynu, z separatorem /"
    if any(part in ("", ".", "..") for part in text.split("/")):
        return "sciezka nie moze miec segmentow '.', '..' ani pustych"
    return None


def _validate_file(entry: object, where: str) -> None:
    if not isinstance(entry, dict):
        _fail(where, "oczekiwano obiektu przypietego pliku")
    _keys(entry, _FILE_KEYS, (), where)
    if entry["role"] not in _ROLES:
        _fail(f"{where}.role", f"oczekiwano jednej z: {', '.join(_ROLES)}")
    if not isinstance(entry["unit"], str):
        _fail(f"{where}.unit", "oczekiwano napisu")
    for key in ("path", "version"):
        problem = _store_path_problem(entry[key])
        if problem is not None:
            _fail(f"{where}.{key}", problem)
    if _VERSIONS in entry["path"].split("/"):
        _fail(f"{where}.path", "sciezka standardowa nie moze lezec w versions/")
    parts = entry["version"].split("/")
    if _VERSIONS not in parts or _INCOMING in parts:
        _fail(
            f"{where}.version",
            "sciezka wersji musi lezec w versions/ magazynu (bez .incoming)",
        )
    if not isinstance(entry["label"], str) or not entry["label"]:
        _fail(f"{where}.label", "oczekiwano niepustej etykiety wersji")
    if not isinstance(entry["sha256"], str) or not _SHA256.fullmatch(entry["sha256"]):
        _fail(f"{where}.sha256", "oczekiwano 64 malych znakow hex")
    size = entry["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _fail(f"{where}.size_bytes", "oczekiwano liczby calkowitej >= 0")


def _project(directory: Path, doc: dict) -> Project:
    return Project(
        directory=directory,
        output_dir=resolve_path(doc["output_dir"], directory),
        tasks=tuple(task_from_json(task) for task in doc["tasks"]),
    )


def task_from_json(data: dict) -> ProjectTask:
    """A validated ``tasks[]`` entry as ``ProjectTask``."""
    digests = data.get("geometry_sha256")
    return ProjectTask(
        name=data["name"],
        command=data["command"],
        options=MappingProxyType(dict(data["options"])),
        pinned_at=data["pinned_at"],
        kartograf_version=data["kartograf_version"],
        geometry_sha256=MappingProxyType(dict(digests)) if digests else None,
        files=tuple(PinnedFile(**entry) for entry in data["files"]),
    )


def task_to_json(task: ProjectTask) -> dict:
    """``tasks[]`` entry of a task in the written form (key order of spec 3.3)."""
    order = COMMANDS[task.command].options
    data: dict = {
        "name": task.name,
        "command": task.command,
        "options": {key: task.options[key] for key in order if key in task.options},
        "pinned_at": task.pinned_at,
        "kartograf_version": task.kartograf_version,
    }
    if task.geometry_sha256 is not None:
        data["geometry_sha256"] = dict(task.geometry_sha256)
    data["files"] = [
        {key: getattr(pin, key) for key in _FILE_KEYS} for pin in task.files
    ]
    return data


# =============================================================================
# Writing
# =============================================================================


def _host() -> str:
    return re.sub(r"[^A-Za-z0-9-]", "-", socket.gethostname()) or "host"


def _owner_text(lock: Path) -> str:
    try:
        host, pid, since = (lock / "owner").read_text(encoding="utf-8").split()
    except (OSError, ValueError):
        return f"{LOCK_NAME}: wlasciciel nieznany"
    return f"{LOCK_NAME}: host {host}, pid {pid}, od {since}"


@contextmanager
def _locked(directory: Path) -> Iterator[None]:
    """The project lock for one read-merge-write (never taken over)."""
    lock = directory / LOCK_NAME
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValidationError(
                    f"projekt zablokowany przez inny proces ({_owner_text(lock)}); "
                    "jesli zaden kartograf nie pracuje na tym projekcie, usun "
                    f"katalog {lock}"
                ) from None
            time.sleep(LOCK_RETRY_S)
        except OSError as e:
            raise ValidationError(f"nie mozna zablokowac projektu ({lock}): {e}") from e
    try:
        since = _clock.now().isoformat(timespec="seconds")
        try:
            (lock / "owner").write_text(
                f"{_host()} {os.getpid()} {since}\n", encoding="utf-8"
            )
        except OSError as e:
            raise ValidationError(f"nie mozna zablokowac projektu ({lock}): {e}") from e
        yield
    finally:
        with suppress(OSError):
            (lock / "owner").unlink()
        with suppress(OSError):
            lock.rmdir()


def _sync_directory(directory: Path) -> None:
    """``fsync`` of the directory entry after ``os.replace`` (where supported)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError as e:
        if e.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EBADF):
            raise ValidationError(f"{MANIFEST_NAME}: zapis {directory}: {e}") from e
    finally:
        os.close(fd)


def _write(directory: Path, doc: dict) -> None:
    """Replace the manifest atomically with ``doc`` in the written form."""
    text = json.dumps(_written(doc), indent=2, ensure_ascii=False) + "\n"
    target = directory / MANIFEST_NAME
    temporary = directory / f"{MANIFEST_NAME}.{_host()}_{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as e:
        with suppress(OSError):
            temporary.unlink()
        raise ValidationError(
            f"{MANIFEST_NAME}: nie mozna zapisac {target}: {e}"
        ) from e
    except BaseException:
        with suppress(OSError):
            temporary.unlink()
        raise
    _sync_directory(directory)


def _written(doc: dict) -> dict:
    """The written form: every task through ``task_to_json``."""
    return {
        "schema": PROJECT_SCHEMA,
        "output_dir": doc["output_dir"],
        "tasks": [task_to_json(task_from_json(task)) for task in doc["tasks"]],
    }


def create_manifest(project_dir: str | Path, output_dir: str) -> None:
    """Write a new manifest with ``output_dir`` and no tasks (``init``).

    Raises
    ------
    ValidationError
        The manifest exists already (it is not touched).
    """
    directory = absolute(project_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with _locked(directory):
        target = directory / MANIFEST_NAME
        if target.exists():
            raise ValidationError(f"projekt juz istnieje: {target}")
        _write(
            directory, {"schema": PROJECT_SCHEMA, "output_dir": output_dir, "tasks": []}
        )


def commit_tasks(
    project_dir: str | Path, changes: Mapping[str, tuple[dict | None, dict | None]]
) -> tuple[str, ...]:
    """Write task changes merged into the current manifest; the conflicts.

    ``changes``: per task name ``(state at reading, new state)``, ``None`` =
    no such task (add: ``(None, new)``, remove: ``(old, None)``). Under the
    lock the manifest is read again: a task whose current state differs from
    the state at reading was changed by another process - it is returned and
    nothing is written for it; the other changes are written with one
    ``os.replace``. Existing tasks keep their places, new ones go last.
    """
    directory = absolute(project_dir)
    with _locked(directory):
        doc = _load(directory)
        tasks: list[dict] = list(doc["tasks"])
        conflicts: list[str] = []
        changed = False
        for name, (before, after) in changes.items():
            current = next((task for task in tasks if task["name"] == name), None)
            if current != before:
                conflicts.append(name)
                continue
            if after == current:
                continue
            changed = True
            if after is None:
                tasks = [task for task in tasks if task["name"] != name]
            elif current is None:
                tasks.append(after)
            else:
                tasks = [after if task["name"] == name else task for task in tasks]
        if changed:
            new = {**doc, "tasks": tasks}
            validate_manifest(new)
            _write(directory, new)
    return tuple(conflicts)
