"""``kartograf project``: manage tasks and pinned store versions (ADR-040)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import Command, Example, Group, Param
from kartograf.messages import message

# The help of the project commands has no sections (a flat list of flags).
_PROJECT_DIR = Param(
    "project_dir",
    "path",
    message("catalog_project.project_dir_description"),
    flag="--project",
    dest="project",
    metavar=message("catalog.metavar_directory"),
    cli_default=".",
    required=True,
    path_role="input",
)
# The commands that write the manifest write into the project directory.
_PROJECT_DIR_WRITTEN = replace(_PROJECT_DIR, path_role="output")
_QUIET = replace(shared.QUIET, section=None)
_NAME = Param(
    "name",
    "str",
    message("catalog_project.name_description"),
    positional=True,
    required=True,
    metavar=message("catalog.metavar_name"),
)
_TASKS = Param(
    "tasks",
    "str_list",
    message("catalog_project.tasks_description"),
    positional=True,
    nargs="*",
    metavar=message("catalog.metavar_name"),
)
_STATE = "kartograf-project-state/1"
_CHECK = "kartograf-project-check/1"
# A project is bound to a store: no `output_dir` (DEV-19.18).
_STORE_ONLY = message("catalog_project.store_only_rule")


def _data_commands() -> list[str]:
    """Return the ids of the data commands a task can run.

    In the order of ``COMMANDS``.
    """
    return [command.id for command in declared().commands if command.project_task]


def _flat(params: tuple[Param, ...]) -> tuple[Param, ...]:
    return tuple(replace(param, section=None) for param in params)


_INIT_PARAMS = (
    _PROJECT_DIR_WRITTEN,
    replace(
        shared.ROOT,
        description=message("catalog_project.root_description"),
        section=None,
    ),
    shared.JSON,
)

_ADD_PARAMS = (
    _PROJECT_DIR_WRITTEN,
    replace(
        _NAME,
        description=message("catalog_project.add_name_description"),
    ),
    Param(
        "arguments",
        "str_list",
        positional=True,
        nargs="REMAINDER",
        argument=None,
        metavar=message("catalog.metavar_group_command"),
        description=message("catalog_project.arguments_description"),
    ),
    Param(
        "command",
        "str",
        message("catalog_project.command_description"),
        flag=None,
        required=True,
        allowed=_data_commands,
    ),
    Param(
        "options",
        "options",
        message("catalog_project.options_description"),
        flag=None,
        required=True,
    ),
    shared.JSON,
)

_REMOVE_PARAMS = (_PROJECT_DIR_WRITTEN, _NAME, shared.JSON)

_UPDATE = tuple(
    replace(
        param,
        description=message("catalog_project.param_description"),
    )
    if param.name == "update"
    else param
    for param in _flat(
        shared.update_params(
            check=message("catalog_project.check_description"),
            upgrade=message("catalog_project.download_upgrade_description"),
            force=message("catalog_project.download_force_description"),
            plain=False,
        )
    )
)

_DOWNLOAD_PARAMS = (
    _PROJECT_DIR,
    *_UPDATE,
    _QUIET,
    replace(
        shared.workers(
            message("catalog_project.workers_description"),
            None,
        ),
        section=None,
    ),
    _TASKS,
    shared.JSON,
)

_INSPECT_PARAMS = (_PROJECT_DIR, _QUIET, _TASKS, shared.JSON)

COMMANDS = (
    Command(
        "project init",
        message("catalog_project.project_init_summary"),
        "manage",
        "init_project",
        _STATE,
        _INIT_PARAMS,
        description=message("catalog_project.project_init_description"),
        effects=("store_write", "project_write"),
        examples=(
            Example(
                {},
                title=message("catalog_project.example_new_project_store_data"),
            ),
        ),
        rules=(message("catalog_project.project_init_rule_1"), _STORE_ONLY),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project add",
        message("catalog_project.project_add_summary"),
        "manage",
        "add_project_task",
        _STATE,
        _ADD_PARAMS,
        description=message("catalog_project.project_add_description"),
        effects=("project_write",),
        idempotent=False,
        examples=(
            Example(
                {"name": "teren"},
                title=message("catalog_project.example_nmt_task_pl_sheet"),
                run={
                    "arguments": [
                        "elevation",
                        "download",
                        "--product",
                        "nmt",
                        "--sheet",
                        "N-34-130-D-d-2-4",
                        "--resolution",
                        "1m",
                        "--vertical-crs",
                        "EVRF2007",
                    ]
                },
            ),
            Example(
                {"name": "gleby"},
                title=message("catalog_project.example_hsg_task_pl_sheet"),
                run={
                    "arguments": [
                        "soil",
                        "hsg",
                        "--sheet",
                        "N-34-130-D",
                        "--depth",
                        "0-5cm",
                    ]
                },
            ),
        ),
        rules=(
            message("catalog_project.project_add_rule_1"),
            _STORE_ONLY,
        ),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project remove",
        message("catalog_project.project_remove_summary"),
        "manage",
        "remove_project_task",
        _STATE,
        _REMOVE_PARAMS,
        description=message("catalog_project.project_remove_description"),
        effects=("project_write",),
        idempotent=False,
        destructive=True,
        rules=(_STORE_ONLY,),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {"name": "teren"},
                title=message("catalog_project.example_remove_task_teren"),
            ),
        ),
    ),
    Command(
        "project download",
        message("catalog_project.project_download_summary"),
        "data",
        "download_project",
        "kartograf-project-report/1",
        _DOWNLOAD_PARAMS,
        description=message("catalog_project.project_download_description"),
        effects=("network", "store_write", "project_write"),
        check_function="check_project",
        check_result_schema=_CHECK,
        examples=(
            Example(
                {},
                title=message("catalog_project.example_fetch_tasks_not_there_yet"),
            ),
            Example(
                {},
                title=message("catalog_project.example_check_sources_without_fetching"),
                run={"check": True},
            ),
            Example(
                {"tasks": ["teren"]},
                title=message("catalog_project.example_re_pin_task_newer_versions"),
                run={"upgrade": True},
            ),
        ),
        rules=(message("catalog_project.project_download_rule_1"), _STORE_ONLY),
        errors=(
            "validation_error",
            "source_unavailable",
            "no_data",
            "unsupported",
            "calculation_error",
            "store_unavailable",
            "io_error",
            "forbidden",
        ),
        family="project",
    ),
    Command(
        "project status",
        message("catalog_project.project_status_summary"),
        "query",
        "get_project_status",
        _CHECK,
        _INSPECT_PARAMS,
        description=message("catalog_project.project_status_description"),
        rules=(_STORE_ONLY,),
        errors=(
            "validation_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {},
                title=message("catalog_project.example_check_pinned_files_every_task"),
            ),
        ),
    ),
    Command(
        "project verify",
        message("catalog_project.project_verify_summary"),
        "query",
        "verify_project",
        _CHECK,
        _INSPECT_PARAMS,
        description=message("catalog_project.project_verify_description"),
        rules=(_STORE_ONLY,),
        errors=(
            "validation_error",
            "data_error",
            "io_error",
            "forbidden",
        ),
        family="project",
        examples=(
            Example(
                {},
                title=message("catalog_project.example_verify_pinned_files_every_task"),
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "project",
        message("catalog_project.project_group_summary"),
        message("catalog_project.project_group_description"),
    ),
)
