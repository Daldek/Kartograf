"""Project manifest ``kartograf-project.json`` (ADR-040).

A project records which data its analysis ordered (tasks: data commands of
the CLI groups with their options) and exactly which store versions it used
(pinned files with SHA-256), so the data can be verified, checked for newer
source content and restored in another store. CLI: ``kartograf project``.
"""

from kartograf.project.model import (
    FileCheck,
    PinnedFile,
    Project,
    ProjectCheck,
    ProjectReport,
    ProjectTask,
    TaskResult,
)
from kartograf.project.operations import (
    add_project_task,
    init_project,
    open_project,
    remove_project_task,
)

__all__ = [
    "FileCheck",
    "PinnedFile",
    "Project",
    "ProjectCheck",
    "ProjectReport",
    "ProjectTask",
    "TaskResult",
    "add_project_task",
    "init_project",
    "open_project",
    "remove_project_task",
]
