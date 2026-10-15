"""Project operations of the public API (ADR-040; spec 4.3-4.12).

Every operation reads ``kartograf-project.json`` (strict validation) and
writes it only through ``manifest.commit_tasks`` (atomic, per-task merge
under a short lock). All operations except ``init_project`` and
``open_project`` require the store directory to exist: an unmounted share
must not receive gigabytes in an empty mount point (spec 3.1).
"""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from kartograf.exceptions import ValidationError
from kartograf.project.commands import options_from_json, options_to_json, task_command
from kartograf.project.manifest import (
    MANIFEST_NAME,
    TASK_NAME,
    TASK_NAME_RULE,
    absolute,
    commit_tasks,
    create_manifest,
    read_manifest,
    resolve_path,
    task_to_json,
)
from kartograf.project.model import Project, ProjectTask


def _saved_path(path: str | Path, project_dir: Path) -> str:
    """A path as written in the manifest (spec 3.2): given relatively - relative
    to the project directory; given absolutely - absolute; always ``/``."""
    given = Path(path)
    if given.is_absolute():
        return given.as_posix()
    try:
        return Path(os.path.relpath(absolute(given), project_dir)).as_posix()
    except ValueError:  # another drive (Windows): only an absolute path works
        return absolute(given).as_posix()


def _require_store(project: Project) -> None:
    if not project.output_dir.is_dir():
        raise ValidationError(
            f"magazyn projektu nie istnieje: {project.output_dir}; podlacz udzial "
            f"albo popraw output_dir w {MANIFEST_NAME}"
        )


def _concurrent(name: str) -> str:
    return (
        f"{name}: zadanie zmienione w tym czasie przez inny proces; nic nie "
        "zapisano - ponow polecenie"
    )


def _select(project: Project, names: Sequence[str] | None) -> tuple[ProjectTask, ...]:
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
            known = ", ".join(by_name) or "brak (kartograf project add NAZWA ...)"
            raise ValidationError(
                f"nieznane zadanie {name!r}; zadania projektu: {known}"
            )
        if task not in selected:
            selected.append(task)
    return tuple(selected)


def init_project(project_dir: str | Path, *, output_dir: str | Path) -> Project:
    """Create a project: ``kartograf-project.json`` with the store ``output_dir``.

    The project directory and the store directory are created when missing.
    ``output_dir`` given relatively (to the current directory) is written
    relative to the project directory, an absolute one as it is (spec 3.2).

    Raises
    ------
    ValidationError
        The manifest exists already (nothing is changed), an empty
        ``output_dir`` or a store that cannot be created.
    """
    directory = absolute(project_dir)
    target = directory / MANIFEST_NAME
    if target.exists():
        raise ValidationError(f"projekt juz istnieje: {target}")
    if not str(output_dir):
        raise ValidationError(
            "--output wymagane: katalog magazynu projektu (np. data albo wspolny "
            "magazyn zespolu)"
        )
    saved = _saved_path(output_dir, directory)
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
    """Add a task: a data command (``"elevation download"``, ...) with its
    ``options`` - the library arguments of that command without
    ``output_dir`` (``BBox``, ``Path``, per-country mappings, sequences).

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
            f"nieprawidlowa nazwa zadania {name!r} ({TASK_NAME_RULE})"
        )
    taken = (
        f"zadanie {name} juz istnieje; usun je (kartograf project remove {name}) "
        "albo wybierz inna nazwe"
    )
    if name in state:
        raise ValidationError(taken)
    entry = task_command(command)
    data = options_to_json(entry, options)
    if "geometry" in data:
        data["geometry"] = _saved_path(str(data["geometry"]), project.directory)
    entry.validate(
        project.output_dir,
        options_from_json(entry, data, project_dir=project.directory),
    )
    task = ProjectTask(name, command, data, None, None, None, ())
    if commit_tasks(project.directory, {name: (None, task_to_json(task))}):
        raise ValidationError(taken)
    return open_project(project.directory)


def remove_project_task(project_dir: str | Path, *, name: str) -> Project:
    """Remove a task with its pins; the store files stay (other projects may
    pin them; Kartograf never deletes store versions).

    Raises
    ------
    ValidationError
        Unknown task, a missing store directory or the task changed by
        another process meanwhile.
    """
    project, state = read_manifest(project_dir)
    _require_store(project)
    _select(project, (name,))
    if commit_tasks(project.directory, {name: (state[name], None)}):
        raise ValidationError(_concurrent(name))
    return open_project(project.directory)
