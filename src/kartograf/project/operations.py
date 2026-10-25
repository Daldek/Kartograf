"""Project operations of the public API (ADR-040; spec 4.3-4.12).

Every operation reads ``kartograf-project.json`` (strict validation) and
writes it only through ``manifest.commit_tasks`` (atomic, per-task merge
under a short lock), after each task. All operations except
``init_project`` and ``open_project`` require the store directory to exist:
an unmounted share must not receive gigabytes in an empty mount point
(spec 3.1). The data logic stays in the library functions of the commands
(``commands.COMMANDS``); here only the pins: what a full success pins, what
``download`` without a mode restores (identical SHA-256 only) and what
``upgrade``/``force`` re-pin (the whole task).
"""

import contextlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

from kartograf import _clock
from kartograf._version import build_version
from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.kinds import options_from_json, options_to_json
from kartograf.download.arguments import require_workers
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadProgress
from kartograf.download.plan import PlanItem
from kartograf.download.versions import read_version
from kartograf.exceptions import KartografError, ValidationError
from kartograf.notices import PROJECT_GEOMETRY_CHANGED, Notice, NoticeSink
from kartograf.project.commands import TaskFiles, project_command, task_command
from kartograf.project.manifest import (
    MANIFEST_NAME,
    TASK_NAME,
    TASK_NAME_RULE,
    absolute,
    commit_tasks,
    create_manifest,
    pin_problem,
    read_manifest,
    resolve_path,
    task_to_json,
)
from kartograf.project.model import (
    FileCheck,
    PinnedFile,
    PinRole,
    PinStatus,
    Project,
    ProjectCheck,
    ProjectReport,
    ProjectTask,
    TaskResult,
)
from kartograf.sources.sidecar import file_digest, write_sidecar

_UPDATE_MODES = (None, "upgrade", "force")
_GEOMETRY_PARTS = (".shp", ".shx", ".dbf", ".prj")


def _saved_path(path: str | Path, project_dir: Path) -> str:
    """Return a path as written in the manifest (spec 3.2).

    Given relatively - relative to the project directory; given absolutely - absolute;
    always ``/``.
    """
    given = Path(path)
    if given.is_absolute():
        return given.as_posix()
    try:
        return Path(os.path.relpath(absolute(given), project_dir)).as_posix()
    except ValueError:  # another drive (Windows): only an absolute path works
        return absolute(given).as_posix()


def _require_store(project: Project) -> None:
    if not project.root.is_dir():
        raise ValidationError(
            f"magazyn projektu nie istnieje: {project.root}; podlacz udzial "
            f"albo popraw root w {MANIFEST_NAME}"
        )


def _concurrent(name: str) -> str:
    return (
        f"{name}: zadanie zmienione w tym czasie przez inny proces; nic nie "
        "zapisano - ponow polecenie"
    )


def _select(
    project: Project, names: Sequence[str] | None, option: str = "tasks"
) -> tuple[ProjectTask, ...]:
    """Tasks by name in the given order (``None`` = all, in manifest order).

    Raises
    ------
    ValidationError
        An unknown task name (before any network access).
    """
    if names is None:
        return project.tasks
    if isinstance(names, str):
        names = (names,)
    by_name = {task.name: task for task in project.tasks}
    selected: list[ProjectTask] = []
    for name in names:
        task = by_name.get(name)
        if task is None:
            known = ", ".join(by_name) or (
                f"brak ({project_command(project.directory, 'add', 'NAZWA ...')})"
            )
            raise ValidationError(
                f"nieznane zadanie {name!r}; zadania projektu: {known}", option=option
            )
        if task not in selected:
            selected.append(task)
    return tuple(selected)


def init_project(project_dir: str | Path, *, root: str | Path | None) -> Project:
    """Create a project: ``kartograf-project.json`` with the store ``root``.

    The project directory and the store directory are created when missing.
    ``root`` given relatively (to the current directory) is written
    relative to the project directory, an absolute one as it is (spec 3.2).

    Raises
    ------
    ValidationError
        The manifest exists already (nothing is changed), no or an empty
        ``root`` or a store that cannot be created.
    """
    directory = absolute(project_dir)
    target = directory / MANIFEST_NAME
    if target.exists():
        raise ValidationError(f"projekt juz istnieje: {target}")
    if root is None or not str(root):
        raise ValidationError(
            "--root wymagane: katalog magazynu projektu (np. data albo wspolny "
            "magazyn zespolu)"
        )
    saved = _saved_path(root, directory)
    store = resolve_path(saved, directory)
    try:
        store.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValidationError(f"nie mozna utworzyc magazynu {store}: {e}") from e
    create_manifest(directory, saved)
    return open_project(directory)


def open_project(project_dir: str | Path) -> Project:
    """Read and validate ``kartograf-project.json`` (no network, no store check).

    Raises
    ------
    ValidationError
        No manifest or an invalid one (the message names the place).
    """
    return read_manifest(project_dir)[0]


def add_project_task(
    project_dir: str | Path,
    *,
    name: str,
    command: str,
    options: Mapping[str, object],
) -> Project:
    """Add a task: a data command with its ``options``.

    The command is e.g. ``"elevation download"``; ``options`` are the library arguments
    of that command without ``root`` (``BBox``, ``Path``, per-country mappings,
    sequences).

    The choice is checked without network by the checks the command's
    download function runs before its first request (the same error as the
    command); the options are written in their JSON form, a relative
    ``geometry`` path relative to the project directory (spec 3.2). Nothing
    is downloaded.

    Raises
    ------
    ValidationError
        Invalid or taken name, not a data command, an option of another
        command, an invalid choice, a missing store directory.
    """
    project, state = read_manifest(project_dir)
    _require_store(project)
    if not isinstance(name, str) or TASK_NAME.fullmatch(name) is None:
        raise ValidationError(
            f"nieprawidlowa nazwa zadania {name!r} ({TASK_NAME_RULE})", option="name"
        )
    taken = (
        f"zadanie {name} juz istnieje; usun je "
        f"({project_command(project.directory, 'remove', name)}) albo wybierz "
        "inna nazwe"
    )
    if name in state:
        raise ValidationError(taken, option="name")
    entry = task_command(command)
    data = options_to_json(entry.options, options, command=entry.name)
    if "geometry" in data:
        data["geometry"] = _saved_path(str(data["geometry"]), project.directory)
    entry.validate(
        project.root,
        options_from_json(entry.options, data, base_dir=project.directory),
    )
    task = ProjectTask(name, command, data, None, None, None, ())
    if commit_tasks(project.directory, {name: (None, task_to_json(task))}):
        raise ValidationError(taken, option="name")
    return open_project(project.directory)


def remove_project_task(project_dir: str | Path, *, name: str) -> Project:
    """Remove a task with its pins.

    The store files stay (other projects may pin them; Kartograf never deletes store
    versions).

    Raises
    ------
    ValidationError
        Unknown task, a missing store directory or the task changed by
        another process meanwhile.
    """
    project, state = read_manifest(project_dir)
    _require_store(project)
    _select(project, (name,), option="name")
    if commit_tasks(project.directory, {name: (state[name], None)}):
        raise ValidationError(_concurrent(name))
    return open_project(project.directory)


# =============================================================================
# download_project
# =============================================================================


class _NotPinnable(Exception):
    """A result file that cannot be pinned (no readable version sidecar)."""


def _error_text(error: Exception) -> str:
    """Return the text of a library error with the remedy of a ``TransformError``."""
    remedy = getattr(error, "remedy", None)
    return f"{error}" + (f" Remedium: {remedy}" if remedy else "")


def _prefixed(sink: NoticeSink, task: str) -> Callable[[Notice], None]:
    """Notices of the library call of a task: same code, ``<task>: `` text."""

    def forward(notice: Notice) -> None:
        sink.add(Notice(notice.level, notice.code, f"{task}: {notice.message}"))

    return forward


def pin_state(store: Path, pin: PinnedFile) -> PinStatus:
    """Classify a pinned version as ``ok``, ``missing`` or ``corrupt``.

    ``missing`` = no version file or sidecar, ``corrupt`` = another size; ``stat`` only,
    no data read (spec 4.9).
    """
    data = store / pin.version
    try:
        size = data.stat().st_size
    except OSError:
        return "missing"
    if not data.with_name(f"{data.name}.meta.json").is_file():
        return "missing"
    return "ok" if size == pin.size_bytes else "corrupt"


def _geometry_files(path: Path) -> list[Path]:
    """Return the files of a geometry: a GPKG, or the present parts of a shapefile."""
    if path.suffix.lower() == ".shp":
        return sorted(
            part
            for part in path.parent.glob(f"{path.stem}.*")
            if part.stem == path.stem
            and part.suffix.lower() in _GEOMETRY_PARTS
            and part.is_file()
        )
    return [path] if path.is_file() else []


def geometry_digest(options: Mapping[str, object]) -> dict[str, str] | None:
    """Return ``{file name: sha256}`` of the task's geometry files.

    ``None`` without ``geometry`` in the (library) options or when the file is missing.
    """
    geometry = options.get("geometry")
    if not isinstance(geometry, Path):
        return None
    files = _geometry_files(geometry)
    return {part.name: file_digest(part)[0] for part in files} or None


def _pin(store: Path, role: PinRole, unit: str, file: VersionedFile) -> PinnedFile:
    """Return the pin of one result file (decision 6 of the plan)."""
    try:
        path = file.path.relative_to(store).as_posix()
        version = file.version_path.relative_to(store).as_posix()
    except ValueError:
        raise _NotPinnable(
            f"{unit}: plik poza magazynem {store}: {file.version_path}"
        ) from None
    local = read_version(file.version_path.parent, file.version_path.name)
    size = local.meta.get("size_bytes") if local is not None else None
    if (
        local is None
        or local.sha256 != file.sha256
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size < 0
    ):
        raise _NotPinnable(
            f"{unit}: wersja {version} bez czytelnego sidecara (sha256, "
            "size_bytes) - nie moze byc przypieta"
        )
    pin = PinnedFile(role, unit, path, version, file.label, file.sha256, size)
    problem = pin_problem(pin)
    if problem is not None:
        raise _NotPinnable(f"{unit}: {problem}")
    return pin


def _pins(store: Path, files: TaskFiles) -> tuple[list[PinnedFile], list[str]]:
    """Return the pins of a result in result order without repeated versions.

    The files that cannot be pinned are returned too.
    """
    pins: list[PinnedFile] = []
    errors: list[str] = []
    seen: set[str] = set()
    for role, unit, file in files.files:
        try:
            pin = _pin(store, role, unit, file)
        except _NotPinnable as e:
            errors.append(str(e))
            continue
        if pin.version not in seen:
            seen.add(pin.version)
            pins.append(pin)
    return pins, errors


class _Problem(NamedTuple):
    """What went wrong in a task: the text and the registry code (and reason) of it."""

    text: str
    code: str
    reason: str | None = None


def _failed(task: ProjectTask, problems: Sequence[_Problem]) -> TaskResult:
    """Return the failed result of a task: every text, the code of the first problem."""
    first = problems[0]
    return TaskResult(
        task.name,
        "failed",
        (),
        (),
        tuple(problem.text for problem in problems),
        first.code,
        first.reason,
    )


def _commit(
    project: Project, before: dict[str, Any], task: ProjectTask
) -> _Problem | None:
    """Write one task; the problem when it could not be written."""
    try:
        conflicts = commit_tasks(
            project.directory, {task.name: (before, task_to_json(task))}
        )
    except ValidationError as e:
        return _Problem(str(e), e.code, e.reason)
    if conflicts:
        return _Problem(_concurrent(task.name), "conflict", "concurrent_change")
    return None


def download_project(
    project_dir: str | Path,
    *,
    tasks: Sequence[str] | None = None,
    update: UpdateMode | None = None,
    workers: int | None = None,
    cache: MetadataCache | bool = False,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_notice: Callable[[Notice], None] | None = None,
) -> ProjectReport:
    """Download, pin and restore the tasks (``tasks``: names; ``None`` = all).

    Without ``update`` (spec 4.6): a task not downloaded yet is downloaded
    with its command's library function and pinned as a whole after a full
    success (``pinned``); a pinned task whose pinned versions are in the
    store is left without network (``unchanged``); missing pinned versions
    are restored only with the same SHA-256 (``restored``: the bytes back
    under the pinned ``version`` path - the manifest keeps ``version`` and
    ``label`` also when the download labels them anew, e.g. another
    download date). ``update="upgrade"``/
    ``"force"`` (spec 4.7): the library function in that mode; after a full
    success the pins of the task are replaced by the result as a whole
    (``updated``, or ``unchanged`` when identical). ``"force"`` also repairs:
    a pinned version that ``verify_project`` calls corrupt (bytes, size or
    sidecar other than pinned) is set aside - its files move to the hidden
    ``.<label>_<sha8>.corrupt-<time>`` next to it, nothing is deleted - and
    the download makes it again; pins that return with the same bytes stay
    as they were (``restored``). A failure of a task
    (``failed``, library errors in ``TaskResult.errors``) leaves its pins
    as they were and the other tasks run. The manifest is written after
    each task. ``workers``: parallel file transfers within a task, for every
    task (``None`` = the default of each command's library function:
    ``elevation``/``imagery`` 4, the others 1; ``soil hsg`` has none - it is
    not a task option). ``cache=False`` by default: no SQLite in the project
    directory (``True`` = the default cache in the current directory).

    Raises
    ------
    ValidationError
        Invalid manifest, unknown task name, unknown mode, ``workers`` not an
        integer >= 1 or a missing store directory (before any network access).
    """
    if update not in _UPDATE_MODES:
        raise ValidationError(
            f"Nieznany tryb update={update!r} (dozwolone: None, 'upgrade', "
            "'force'); sprawdzenie bez pobierania: check_project",
            option="update",
            allowed=("upgrade", "force"),
        )
    if workers is not None:
        require_workers(workers, "--workers")
    project, state = read_manifest(project_dir)
    _require_store(project)
    selected = _select(project, tasks)
    sink = NoticeSink(on_notice)
    results = tuple(
        _download_task(
            project, task, state[task.name], update, workers, cache, on_progress, sink
        )
        for task in selected
    )
    return ProjectReport(
        project=open_project(project.directory),
        tasks=results,
        notices=sink.notices,
        ok=all(result.outcome != "failed" for result in results),
    )


def _download_task(
    project: Project,
    task: ProjectTask,
    before: dict[str, Any],
    update: UpdateMode | None,
    workers: int | None,
    cache: MetadataCache | bool,
    on_progress: Callable[[DownloadProgress], None] | None,
    sink: NoticeSink,
) -> TaskResult:
    """One task of ``download_project``."""
    command = task_command(task.command)
    store = project.root
    options = options_from_json(
        command.options, task.options, base_dir=project.directory
    )
    restore: tuple[PinnedFile, ...] = ()
    if task.files and update is None:
        states = {pin.version: pin_state(store, pin) for pin in task.files}
        corrupt = [pin for pin in task.files if states[pin.version] == "corrupt"]
        if corrupt:
            return _failed(
                task,
                [
                    _Problem(
                        _corrupt_text(project, task.name, pin),
                        "data_error",
                        "corrupt_pin",
                    )
                    for pin in corrupt
                ],
            )
        restore = tuple(pin for pin in task.files if states[pin.version] == "missing")
        if not restore:
            return TaskResult(task.name, "unchanged", (), (), ())
    geometry = geometry_digest(options)
    pinned_geometry = (
        dict(task.geometry_sha256) if task.geometry_sha256 is not None else None
    )
    if (
        restore
        and None not in (pinned_geometry, geometry)
        and geometry != pinned_geometry
    ):
        return _failed(
            task,
            [
                _Problem(
                    f"plik geometrii {task.options['geometry']} zmienil sie od "
                    "przypiecia; przywroc go albo przyjmij nowy obszar: "
                    f"{_upgrade_hint(project, task.name)}",
                    "conflict",
                    "geometry_changed",
                )
            ],
        )
    repaired: tuple[PinnedFile, ...] = ()
    if update == "force":
        try:
            repaired = _set_aside_corrupt(project, task)
        except (OSError, ValueError) as e:
            return _failed(task, [_Problem(str(e), "io_error")])
    try:
        result = command.download(
            store,
            options,
            update=update,
            plan=None,
            workers=workers,
            summary=False,
            cache=cache,
            on_progress=on_progress,
            on_notice=_prefixed(sink, task.name),
        )
    except KartografError as e:
        return _failed(task, [_Problem(_error_text(e), e.code, e.reason)])
    files = command.files(result)
    pins, pin_errors = _pins(store, files)
    if restore:
        return _restore(project, task, restore, files, pins, pin_errors)
    problems = [
        *(
            _Problem(text, files.code or "internal_error", files.reason)
            for text in files.errors
        ),
        *(_Problem(text, "data_error", "not_pinnable") for text in pin_errors),
        *(
            _Problem(text, "io_error", "repin_failed")
            for text in _repin_repaired(project.root, repaired, pins)
        ),
    ]
    if not files.complete or problems or not pins:
        return _failed(
            task,
            problems
            or [
                _Problem(
                    "zadanie nie dalo pelnego wyniku - nic nie przypieto",
                    "internal_error",
                    "incomplete_result",
                )
            ],
        )
    if task.files:
        # The same bytes keep their pin (a relabeled version of identical
        # content, e.g. --force of a source without a signal, changes nothing).
        present = {
            (pin.path, pin.sha256): pin
            for pin in task.files
            if pin_state(store, pin) == "ok"
        }
        pins = [present.get((pin.path, pin.sha256), pin) for pin in pins]
    if task.files and set(pins) == set(task.files) and geometry == pinned_geometry:
        # repaired: the same pins, the bytes of some of them made again
        return TaskResult(
            task.name, "restored" if repaired else "unchanged", repaired, (), ()
        )
    pinned = replace(
        task,
        pinned_at=_clock.now().isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        geometry_sha256=geometry,
        files=tuple(pins),
    )
    problem = _commit(project, before, pinned)
    if problem is not None:
        return _failed(task, [problem])
    old, new = set(task.files), set(pins)
    return TaskResult(
        task.name,
        "updated" if task.files else "pinned",
        tuple(pin for pin in pins if pin not in old),
        tuple(pin for pin in task.files if pin not in new),
        (),
    )


def _repair_advice(project: Project, task: str) -> str:
    """Return the ways back from a corrupt pinned version.

    They are the copy of the store or ``--force`` (``_set_aside_corrupt``).
    """
    return (
        "przywroc katalog wersji z kopii magazynu albo uruchom "
        f"{project_command(project.directory, 'download', '--force', task)} "
        "(odklada uszkodzona wersje i pobiera ja ponownie)"
    )


def _corrupt_text(project: Project, task: str, pin: PinnedFile) -> str:
    return (
        f"{pin.unit}: przypieta wersja {pin.version} ma inny rozmiar niz "
        f"przypiety - {_repair_advice(project, task)}"
    )


def _set_aside_corrupt(project: Project, task: ProjectTask) -> tuple[PinnedFile, ...]:
    """Run the repair of ``--force``.

    The pinned versions that ``verify`` calls corrupt are set aside (``_set_aside``)
    before the download, so it makes them again; the pins that return with the same
    bytes keep their version path and label (``_repin_repaired``).

    Raises
    ------
    OSError, ValueError
        A corrupt version that cannot be set aside (it lies outside the store
        or cannot be moved); the ones before it stay set aside.
    """
    corrupt = tuple(
        pin
        for pin in task.files
        if _store_check(project, task, pin, verify=True).status == "corrupt"
    )
    for pin in corrupt:
        _set_aside(project.root, pin)
    return corrupt


def _set_aside(store: Path, pin: PinnedFile) -> None:
    """Move the data file and the sidecar of a pinned version aside.

    They go into the hidden directory ``.<label>_<sha8>.corrupt-<time>`` next to it:
    Kartograf never deletes a version, and a hidden directory is none for
    ``list_versions`` and ``iter_store``. The standard path (a hardlink of the same
    bytes) is linked anew by the download.

    Raises
    ------
    ValueError
        The version lies outside the store (a symlink in its path).
    OSError
        The files cannot be moved (nothing is moved then).
    """
    data = store / pin.version
    directory = data.parent
    expected = store.resolve(strict=True) / PurePosixPath(pin.version).parent
    if directory.resolve(strict=True) != expected:
        raise ValueError(
            f"{pin.unit}: sciezka przypietej wersji {pin.version} wykracza poza "
            "magazyn (dowiazanie symboliczne) - nie odkladam jej"
        )
    stamp = _clock.now().strftime("%Y%m%dT%H%M%S")
    for attempt in range(1000):
        suffix = f"-{attempt}" if attempt else ""
        aside = directory.with_name(f".{directory.name}.corrupt-{stamp}{suffix}")
        try:
            aside.mkdir()
        except FileExistsError:
            continue
        break
    else:
        raise OSError(f"{directory}: brak wolnej nazwy katalogu na uszkodzona wersje")
    moved: list[tuple[Path, Path]] = []
    try:
        for source in (data, data.with_name(f"{data.name}.meta.json")):
            os.replace(source, aside / source.name)
            moved.append((source, aside / source.name))
    except OSError:
        for source, target in reversed(moved):
            with contextlib.suppress(OSError):
                os.replace(target, source)
        with contextlib.suppress(OSError):
            aside.rmdir()
        raise


def _repin_repaired(
    store: Path, repaired: tuple[PinnedFile, ...], pins: list[PinnedFile]
) -> list[str]:
    """Put the pinned version directory of a repaired pin back and return the errors.

    This applies when the download gave its bytes under another version
    (``_repin_version``). Other bytes (the source changed) are no repair: ``--force``
    re-pins them.
    """
    problems = []
    for pin in repaired:
        same = next(
            (new for new in pins if new.path == pin.path and new.sha256 == pin.sha256),
            None,
        )
        if same is None:
            continue
        try:
            _repin_version(store, pin, same)
        except (OSError, ValueError, KeyError, TypeError) as e:
            problems.append(
                f"{pin.unit}: nie udalo sie odtworzyc przypietej wersji "
                f"{pin.version}: {e}"
            )
    return problems


def _upgrade_hint(project: Project, task: str) -> str:
    """Return the command that re-pins a task to a new version (``--upgrade``)."""
    return project_command(project.directory, "download", "--upgrade", task)


def _restore(
    project: Project,
    task: ProjectTask,
    missing: tuple[PinnedFile, ...],
    files: TaskFiles,
    pins: list[PinnedFile],
    pin_errors: list[str],
) -> TaskResult:
    """Restore the missing pinned versions from the result.

    Identical SHA-256 only (spec 4.6 point 3), also when other pins of the task fail.
    The bytes go back under the pinned ``version`` path (``_repin_version``): the pins
    and the manifest never change.
    """
    restored: list[PinnedFile] = []
    problems: list[_Problem] = []
    for pin in missing:
        candidates = [new for new in pins if new.path == pin.path]
        same = next((new for new in candidates if new.sha256 == pin.sha256), None)
        if same is not None:
            try:
                _repin_version(project.root, pin, same)
            except (OSError, ValueError, KeyError, TypeError) as e:
                problems.append(
                    _Problem(
                        f"{pin.unit}: nie udalo sie odtworzyc przypietej wersji "
                        f"{pin.version}: {e}",
                        "io_error",
                        "repin_failed",
                    )
                )
                continue
            restored.append(pin)
        elif candidates:
            problems.append(
                _Problem(
                    f"{pin.unit}: zrodlo ma inna tresc niz przypieta (przypieta "
                    f"{pin.label}, pobrana {candidates[0].label}); przypiecie bez "
                    "zmian - przywroc magazyn z kopii albo przyjmij nowa wersje: "
                    f"{_upgrade_hint(project, task.name)}",
                    "conflict",
                    "pin_mismatch",
                )
            )
        else:
            problems.append(
                _Problem(
                    f"{pin.unit}: przypietego pliku {pin.path} nie ma w wyniku "
                    "zadania; przypiecie bez zmian - przywroc magazyn z kopii albo "
                    "przyjmij nowy wynik: "
                    f"{_upgrade_hint(project, task.name)}",
                    "conflict",
                    "pin_mismatch",
                )
            )
    if problems:
        errors = [
            *(problem.text for problem in problems),
            *files.errors,
            *pin_errors,
        ]
        return TaskResult(
            task.name,
            "failed",
            tuple(restored),
            (),
            tuple(errors),
            problems[0].code,
            problems[0].reason,
        )
    return TaskResult(task.name, "restored", tuple(restored), (), ())


def _repin_version(store: Path, pin: PinnedFile, found: PinnedFile) -> None:
    """Restore the pinned version directory for the same bytes.

    The download stored them under another version (``found``; e.g. another download
    date): a hardlink of its data and its sidecar with the pinned label, written once
    (D18). Nothing to do when the download used the pinned version itself.

    Raises
    ------
    OSError, ValueError, KeyError, TypeError
        The found version or its sidecar cannot be read, the target holds
        other bytes or the link fails.
    """
    if found.version == pin.version:
        return
    source = store / found.version
    target = store / pin.version
    meta = json.loads(
        source.with_name(f"{source.name}.meta.json").read_text(encoding="utf-8")
    )
    if meta["sha256"] != pin.sha256:
        raise ValueError(f"sidecar {found.version} ma inne sha256 niz przypiete")
    meta["extra"]["version"]["label"] = pin.label
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except FileExistsError:
        if file_digest(target) != (pin.sha256, pin.size_bytes):
            raise ValueError(f"{pin.version} ma inne bajty niz przypiete") from None
    # FileExistsError: another restore of the same pin published it first
    with contextlib.suppress(FileExistsError):
        write_sidecar(target, meta, exclusive=True)


def _file_check(
    task: ProjectTask,
    pin: PinnedFile,
    status: PinStatus,
    *,
    detail: str | None = None,
    available: str | None = None,
) -> FileCheck:
    return FileCheck(
        task.name, pin.unit, pin.path, status, pin.label, available, detail
    )


def _store_check(
    project: Project, task: ProjectTask, pin: PinnedFile, *, verify: bool
) -> FileCheck:
    """Inspect a pinned version. Status only stats; verify hashes its data."""
    state = pin_state(project.root, pin)
    if state == "missing":
        return _file_check(
            task,
            pin,
            "missing",
            detail="brak przypietej wersji; przywroc kopie magazynu albo "
            f"uruchom {project_command(project.directory, 'download', task.name)}",
        )
    if state == "corrupt":
        return _file_check(
            task, pin, "corrupt", detail=_corrupt_text(project, task.name, pin)
        )
    if not verify:
        return _file_check(task, pin, "ok")
    data = project.root / pin.version
    sidecar = data.with_name(data.name + ".meta.json")
    try:
        root = project.root.resolve(strict=True)
        # A valid manifest path is lexical; a symlink in any of its parents
        # must still not lead outside the store, even for a correct digest.
        if not data.resolve(strict=True).is_relative_to(root) or not sidecar.resolve(
            strict=True
        ).is_relative_to(root):
            raise ValueError("sciezka przypietej wersji wykracza poza magazyn")
        standard = project.root / pin.path
        if (standard.exists() or standard.is_symlink()) and not standard.resolve(
            strict=False
        ).is_relative_to(root):
            raise ValueError("sciezka standardowa wykracza poza magazyn")
        problem = pin_problem(pin)
        if problem is not None:
            raise ValueError(problem)
        local = read_version(data.parent, data.name)
        if local is None:
            raise ValueError(
                "sidecar wersji jest nieczytelny lub niezgodny z nazwa wersji"
            )
        meta = local.meta
        if (
            meta.get("sha256") != pin.sha256
            or type(meta.get("size_bytes")) is not int
            or meta["size_bytes"] != pin.size_bytes
            or meta.get("extra", {}).get("version", {}).get("label") != pin.label
        ):
            raise ValueError("sidecar wersji nie zgadza sie z przypieciem")
        if file_digest(data) != (pin.sha256, pin.size_bytes):
            raise ValueError("suma SHA-256 danych jest inna niz przypieta")
    except (OSError, ValueError, AttributeError, TypeError) as error:
        return _file_check(
            task,
            pin,
            "corrupt",
            detail=f"{error}; {_repair_advice(project, task.name)}",
        )
    return _file_check(task, pin, "ok")


def _inspect_project(
    project_dir: str | Path,
    tasks: Sequence[str] | None,
    *,
    verify: bool,
) -> ProjectCheck:
    project = open_project(project_dir)
    _require_store(project)
    selected = _select(project, tasks)
    missing_tasks = tuple(task.name for task in selected if not task.files)
    files = tuple(
        _store_check(project, task, pin, verify=verify)
        for task in selected
        for pin in task.files
    )
    return ProjectCheck(
        project,
        files,
        missing_tasks,
        (),
        not missing_tasks and all(item.status == "ok" for item in files),
    )


def get_project_status(
    project_dir: str | Path, *, tasks: Sequence[str] | None = None
) -> ProjectCheck:
    """Check pinned version and sidecar existence and data size.

    No hashing or network access. ``ok`` requires every selected task to have intact
    pins.
    """
    return _inspect_project(project_dir, tasks, verify=False)


def verify_project(
    project_dir: str | Path, *, tasks: Sequence[str] | None = None
) -> ProjectCheck:
    """Verify full SHA-256, size, version sidecars, and symlink containment.

    It covers every pinned file. Neither the store nor the manifest is modified.
    """
    return _inspect_project(project_dir, tasks, verify=True)


def _plan_key(item: PlanItem) -> str:
    """Return the same standard store path as ``PinnedFile.path``."""
    return PurePosixPath(item.segment, item.hierarchy, item.name).as_posix()


def _matched(
    items: tuple[PlanItem, ...], pins: tuple[PinnedFile, ...]
) -> tuple[dict[int, PinnedFile], tuple[PinnedFile, ...]]:
    """Match items and pins within a standard path pair.

    Equal labels go first, then only a unique remaining item and pin (multiple campaigns
    must not be guessed).
    """
    by_path: dict[str, list[int]] = {}
    pins_by_path: dict[str, list[PinnedFile]] = {}
    for index, item in enumerate(items):
        by_path.setdefault(_plan_key(item), []).append(index)
    for pin in pins:
        pins_by_path.setdefault(pin.path, []).append(pin)
    paired: dict[int, PinnedFile] = {}
    unpaired: list[PinnedFile] = []
    for path, local_pins in pins_by_path.items():
        positions = by_path.get(path, [])
        remaining = list(local_pins)
        for label_field in ("available_label", "local_label"):
            for index in positions:
                if index in paired:
                    continue
                label = getattr(items[index], label_field)
                match = next(
                    (
                        pin
                        for pin in remaining
                        if label is not None and pin.label == label
                    ),
                    None,
                )
                if match is not None:
                    paired[index] = match
                    remaining.remove(match)
        unmatched = [index for index in positions if index not in paired]
        if len(unmatched) == len(remaining) == 1:
            paired[unmatched[0]] = remaining.pop()
        unpaired.extend(remaining)
    return paired, tuple(unpaired)


def _missing_detail(project: Project, task: ProjectTask) -> str:
    return (
        "brak przypietego pliku w magazynie; przywroc kopie albo uruchom "
        f"{project_command(project.directory, 'download', task.name)}"
    )


def _checked_item(
    project: Project, task: ProjectTask, item: PlanItem, pin: PinnedFile | None
) -> FileCheck:
    path = _plan_key(item)
    if pin is None:
        if item.status == "check_failed":
            return FileCheck(
                task.name,
                item.unit,
                path,
                "check_failed",
                None,
                item.available_label,
                item.error,
            )
        return FileCheck(
            task.name,
            item.unit,
            path,
            "added",
            None,
            item.available_label,
            "nowy plik w wyniku zadania",
        )
    if pin_state(project.root, pin) != "ok":
        return _file_check(task, pin, "missing", detail=_missing_detail(project, task))
    if item.status == "check_failed":
        return _file_check(
            task,
            pin,
            "check_failed",
            available=item.available_label,
            detail=item.error,
        )
    if item.local_sha256 == pin.sha256 and item.status == "current":
        return _file_check(
            task, pin, "current", available=item.available_label or item.local_label
        )
    if item.local_sha256 == pin.sha256 and item.status == "unverifiable":
        return _file_check(
            task,
            pin,
            "unverifiable",
            available=item.available_label,
            detail="nie da sie sprawdzic bez pobrania (--force)",
        )
    return _file_check(
        task,
        pin,
        "newer",
        available=item.available_label if item.status == "newer" else item.local_label,
        detail="nowsza wersja w magazynie albo u zrodla; uruchom "
        f"{_upgrade_hint(project, task.name)}",
    )


def check_project(
    project_dir: str | Path,
    *,
    tasks: Sequence[str] | None = None,
    cache: MetadataCache | bool = False,
    on_notice: Callable[[Notice], None] | None = None,
) -> ProjectCheck:
    """Check source freshness relative to the task's pins.

    Not the store's latest files. Unpinned tasks are skipped; nothing is downloaded or
    written.
    """
    project = open_project(project_dir)
    _require_store(project)
    selected = _select(project, tasks)
    sink = NoticeSink(on_notice)
    checked: list[FileCheck] = []
    missing_tasks: list[str] = []
    for task in selected:
        if not task.files:
            missing_tasks.append(task.name)
            continue
        command = task_command(task.command)
        options = options_from_json(
            command.options, task.options, base_dir=project.directory
        )
        if task.geometry_sha256 is not None and geometry_digest(options) != dict(
            task.geometry_sha256
        ):
            sink.emit(
                "warning",
                PROJECT_GEOMETRY_CHANGED,
                f"{task.name}: plik geometrii zmienil sie od przypiecia; "
                "plan aktualizacji dotyczy obecnej geometrii",
            )
        try:
            plan = command.check(
                project.root,
                options,
                cache=cache,
                on_notice=_prefixed(sink, task.name),
            )
        except KartografError as error:
            checked.extend(
                _file_check(task, pin, "check_failed", detail=_error_text(error))
                for pin in task.files
            )
            continue
        paired, unpaired = _matched(plan.items, task.files)
        checked.extend(
            _checked_item(project, task, item, paired.get(index))
            for index, item in enumerate(plan.items)
        )
        for pin in unpaired:
            if pin_state(project.root, pin) != "ok":
                checked.append(
                    _file_check(
                        task, pin, "missing", detail=_missing_detail(project, task)
                    )
                )
            else:
                checked.append(
                    _file_check(
                        task, pin, "removed", detail="plik poza wynikiem zadania"
                    )
                )
    files = tuple(checked)
    return ProjectCheck(
        project,
        files,
        tuple(missing_tasks),
        sink.notices,
        all(item.status != "check_failed" for item in files),
    )
