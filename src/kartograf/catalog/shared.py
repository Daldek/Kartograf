"""
Parameters shared by the commands of the catalog (spec 8.2, 8.3 item 4).

A parameter that means the same in many commands is declared once here: the
area choice (``sheet``, ``bbox`` + ``bbox_crs``, ``geometry`` + ``layer``), the
product and country choice, the store directory, the update modes and the
display flags. A command includes it and may override ``description``,
``allowed``, ``required`` or ``section`` with ``dataclasses.replace``; the
helpers below do that for the usual cases. The texts and the section titles are
the ones of the ``--help`` of the CLI (the sheet, bbox and layer descriptions
are common to every area command). Every text is a catalog message of the area
``catalog`` (``kartograf.messages.catalog``): English for the catalog document and
the MCP tools, Polish for ``--help`` with ``--lang pl``.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import get_args

from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Param,
    Text,
    Values,
    resolve,
)
from kartograf.download.fetch import UpdateMode
from kartograf.download.options import BBOX_CRS_CHOICES
from kartograf.messages import message

BBOX_HELP = message("catalog.bbox_description")
# Area groups (land cover, soil): a sheet code is an area like --bbox (ADR-039).
SHEET_AREA_HELP = message("catalog.sheet_area_description")
GEOMETRY_HELP = message("catalog.geometry_description")
LAYER_HELP = message("catalog.layer_description")
CHECK_HELP = message("catalog.check_description")
UPDATE_HELP = message("catalog.update_description")
PLAN_HELP = message("catalog.plan_description")
# One sentence for the description of every data command (DEV-19.18): both targets.
PLAIN_NOTE = message("catalog.plain_note")
# The selection rule of the PL sheets in plain mode (ADR-054 decision 5, DEV-19.4).
PLAIN_SHEETS_HELP = message("catalog.plain_sheets_description")
# Titles of the --help sections of every data command (UX-27).
SELECTION_TITLE = message("catalog.section_selection")
PRODUCT_TITLE = message("catalog.section_product")
OUTPUT_TITLE = message("catalog.section_output")
# The sheet systems of the PL codes (``SheetParser`` reads both).
PL_SHEETS = ("pl1992", "pl2000")

PRODUCT = Param(
    "product",
    "str",
    message("catalog.product_description"),
    required=True,
    task=True,
    section=SELECTION_TITLE,
)
COUNTRY = Param(
    "country",
    "str",
    message("catalog.country_description"),
    task=True,
    normalize="lower",
    section=SELECTION_TITLE,
)
SHEET = Param(
    "sheet",
    "str",
    message("catalog.sheet_description"),
    metavar=message("catalog.metavar_sheet"),
    # argparse does not strip whitespace; a sheet code with padding would
    # reach the system registry and the file name (parser review 2026-10-07, K5)
    normalize="strip",
    task=True,
    section=SELECTION_TITLE,
)
BBOX = Param(
    "bbox",
    "bbox",
    BBOX_HELP,
    metavar="BBOX",
    examples=([565000, 242000, 566000, 243000],),
    task=True,
    section=SELECTION_TITLE,
)
BBOX_CRS = Param(
    "bbox_crs",
    "bbox_crs",
    message("catalog.bbox_crs_description"),
    allowed=lambda: BBOX_CRS_CHOICES,
    choices=True,
    normalize="upper",
    cli_default="EPSG:2180",
    task=True,
    section=SELECTION_TITLE,
)
GEOMETRY = Param(
    "geometry",
    "path",
    GEOMETRY_HELP,
    path_role="input",
    metavar=message("catalog.metavar_file"),
    task=True,
    section=SELECTION_TITLE,
)
LAYER = Param(
    "layer",
    "str",
    LAYER_HELP,
    metavar=message("catalog.metavar_name"),
    task=True,
    section=SELECTION_TITLE,
)
OUTPUT_DIR = Param(
    "output_dir",
    "path",
    message("catalog.output_dir_description"),
    short="-o",
    path_role="output",
    metavar=message("catalog.metavar_directory"),
    section=OUTPUT_TITLE,
)
ROOT = Param(
    "root",
    "path",
    message("catalog.root_description"),
    path_role="root",
    metavar=message("catalog.metavar_directory"),
    section=OUTPUT_TITLE,
)
WORKERS = Param(
    "workers",
    "int",
    message("catalog.workers_description"),
    minimum=1,
    short="-w",
    metavar="N",
    section=OUTPUT_TITLE,
)
QUIET = Param(
    "quiet",
    "flag",
    message("catalog.quiet_description"),
    argument=None,
    short="-q",
    section=OUTPUT_TITLE,
)
JSON = Param(
    "json",
    "flag",
    message("catalog.json_description"),
    argument=None,
)
LANG = Param(
    "lang",
    "str",
    message("catalog.lang_description"),
    argument=None,
    allowed=("pl", "en"),
    choices=True,
    normalize="lower",
    metavar=message("catalog.metavar_lang"),
)
CHECK = Param(
    "check",
    "flag",
    CHECK_HELP,
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPGRADE = Param(
    "upgrade",
    "flag",
    message("catalog.upgrade_description"),
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
FORCE = Param(
    "force",
    "flag",
    message("catalog.force_description"),
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPDATE = Param(
    "update",
    "str",
    UPDATE_HELP,
    flag=None,
    # ``check`` is the ``check_*`` twin of a command, not a mode of its function
    allowed=lambda: [mode for mode in get_args(UpdateMode) if mode != "check"],
    section=OUTPUT_TITLE,
)
PLAN = Param(
    "plan",
    "plan",
    PLAN_HELP,
    metavar=message("catalog.metavar_file"),
    section=OUTPUT_TITLE,
)


def product(
    products: Values,
    choices_text: Callable[[Sequence[str]], str],
    *,
    section: str = SELECTION_TITLE,
) -> Param:
    """``--product`` of a group.

    ``products`` are the allowed values and the parser choices,
    ``choices_text(products)`` names them in the Polish description (``Produkt
    (wymagany): nmt (...), nmpt (...)``); the meanings of the English ones are in
    ``kartograf.catalog.meanings``.
    """

    def description() -> str:
        return message(
            "catalog.product_choices_description",
            choices=choices_text(tuple(resolve(products))),
        )

    return replace(
        PRODUCT,
        description=description,
        allowed=lambda: tuple(resolve(products)),
        choices=True,
        section=section,
    )


def country(
    countries: Values, description: Text, *, section: str = SELECTION_TITLE
) -> Param:
    """``--country`` of a command.

    ``countries`` are the allowed values and the parser choices; ``description`` is the
    text of the command.
    """
    return replace(
        COUNTRY,
        description=description,
        allowed=lambda: tuple(resolve(countries)),
        choices=True,
        section=section,
    )


def area(
    *,
    sheet: Text | None,
    accepts: tuple[str, ...] | None = None,
    bbox: Text = BBOX_HELP,
    geometry: Text = GEOMETRY_HELP,
    section: str = SELECTION_TITLE,
) -> tuple[Param, ...]:
    """One area choice of a request.

    ``sheet`` (when ``sheet`` is the text of its description; ``accepts`` are the
    sheet systems it takes), ``bbox`` with ``bbox_crs``, ``geometry`` with ``layer``.
    Exactly one is checked by the library (a ``one_of`` constraint of the command).
    """
    params: list[Param] = []
    if sheet is not None:
        if accepts is None:
            raise ValueError("area: a sheet parameter declares the systems it accepts")
        params.append(replace(SHEET, description=sheet, accepts=accepts))
    params += [
        replace(BBOX, description=bbox),
        BBOX_CRS,
        replace(GEOMETRY, description=geometry),
        LAYER,
    ]
    return tuple(replace(param, section=section) for param in params)


def target(files: Text, *, sheets: bool = False) -> tuple[Param, Param]:
    """``--output-dir`` and ``--root``: where a data command writes (DEV-19.1).

    ``files`` says where the files of the store go (``pliki w <KATALOG>/nmt/...``,
    in the Polish text); ``sheets``: the command has PL sheets, whose plain mode takes
    the newest FULL flight (``PLAIN_SHEETS_HELP``).
    """

    def description() -> str:
        return message(
            "catalog.root_files_description",
            root=ROOT.description,
            files=resolve(files),
        )

    output = OUTPUT_DIR
    if sheets:
        output = replace(
            OUTPUT_DIR,
            description=message(
                "catalog.output_dir_sheets_description",
                output_dir=OUTPUT_DIR.description,
                sheets=PLAIN_SHEETS_HELP,
            ),
        )
    return output, replace(ROOT, description=description)


def target_constraints(*, campaigns: bool = False) -> tuple[Constraint, ...]:
    """Return the rules of ``--output-dir`` and ``--root`` of a data command.

    One mutual exclusion group, ``target`` (neither: the default store), and the
    options that act on versions, which need the store.
    """
    names = ("upgrade", "plan", *(("all_campaigns",) if campaigns else ()))
    flags = ", ".join("--" + name.replace("_", "-") for name in names)
    return (
        Constraint(
            "one_of",
            ("output_dir", "root"),
            message("catalog.rule_target"),
            group="target",
            optional=True,
        ),
        Constraint(
            "excludes",
            names,
            message("catalog.rule_output_dir_excludes", flags=flags),
            "output_dir",
        ),
    )


def workers(description: Text, default: int | None) -> Param:
    """``--workers``/``-w``.

    Parallel transfers (``description``: the text of the command); ``default`` is the
    number the library function uses (and the flag).
    """
    return replace(WORKERS, description=description, default=default)


def _force_plain(text: Text) -> Text:
    """Return the text of ``--force`` and what it does with ``--output-dir``.

    A lazy text stays lazy.
    """
    if callable(text):
        return lambda: message("catalog.force_plain_description", force=text())
    return message("catalog.force_plain_description", force=text)


def update_params(
    *,
    check: Text,
    upgrade: Text,
    force: Text,
    plan: Text | None = None,
    plain: bool = True,
) -> tuple[Param, ...]:
    """Update modes of a command that writes.

    The flags ``--check``, ``--upgrade`` and ``--force``, the API argument ``update``
    and, when ``plan`` is the text of its description, ``--plan``. ``check`` says what
    the source signals for this command: the English sentence is added to the common
    text of the option, the Polish one is the whole help; ``upgrade`` and ``force``
    are the help of the flags, which only spell ``update``.

    ``--check`` and ``--upgrade`` exclude each other. ``--force`` too, unless the
    command writes plain files (``plain``): ``--check --force`` is the plan that says
    ``replace``, ``--upgrade --force`` is refused by the command, and the text of
    ``--force`` says what it does with ``--output-dir``.
    """
    params = [
        replace(
            CHECK,
            description=message(
                "catalog.check_source_description", common=CHECK_HELP, source=check
            ),
        ),
        replace(UPGRADE, description=upgrade),
        replace(
            FORCE,
            description=_force_plain(force) if plain else force,
            exclusive=None if plain else "update",
        ),
        UPDATE,
    ]
    if plan is not None:
        params.append(replace(PLAN, description=plan))
    return tuple(params)


def product_summaries(
    products: Sequence[str], choices_text: Callable[[Sequence[str]], str]
) -> list[tuple[str, str]]:
    """Return the ``(product, summary)`` pairs of a group.

    The text in the parentheses of ``choices_text`` of one product (``nmt (Numeryczny
    Model Terenu; PL i CZ)`` gives ``Numeryczny Model Terenu; PL i CZ``).
    """
    pairs = []
    for name in products:
        text = choices_text([name])
        prefix = f"{name} ("
        if not (text.startswith(prefix) and text.endswith(")")):
            raise ValueError(f"{text!r} is not '{name} (<summary>)'")
        pairs.append((name, text[len(prefix) : -1]))
    return pairs


# What a command that only reads can raise: a wrong argument and, in the MCP server, a
# path outside the allowed directories (ERR-1).
READ_ERRORS = ("validation_error", "io_error", "forbidden")
# What a command that downloads can raise.
DATA_ERRORS = (
    "validation_error",
    "source_unavailable",
    "no_data",
    "unsupported",
    "calculation_error",
    "store_unavailable",
    "io_error",
    "forbidden",
)


def list_sources_command(group: str, products: Values) -> Command:
    """``<group> list-sources``.

    The registered sources of the group's ``products`` (the registry, no network). The
    API function ``list_sources`` serves every group, so ``group`` is a fixed argument
    with the one value of this command and ``product`` narrows the list.
    """
    return Command(
        f"{group} list-sources",
        message("catalog.list_sources_summary", group=group),
        "query",
        "list_sources",
        "kartograf-sources/1",
        (
            Param(
                "group",
                "str",
                message("catalog.list_sources_group_description", group=group),
                flag=None,
                required=True,
                fixed=group,
            ),
            Param(
                "product",
                "str",
                message("catalog.list_sources_product_description"),
                metavar=message("catalog.metavar_product"),
                allowed=lambda: tuple(resolve(products)),
                choices=True,
            ),
            JSON,
        ),
        description=message("catalog.list_sources_description", group=group),
        rules=(message("catalog.list_sources_rule"),),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {},
                title=message("catalog.list_sources_example", group=group),
            ),
        ),
    )
