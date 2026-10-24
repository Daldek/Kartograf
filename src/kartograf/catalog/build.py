"""
The catalog document built from the declarations (spec 8.5).

``build_catalog`` resolves the providers of the declarations, checks them and
builds the ``Catalog``; ``get_catalog`` and ``data_commands`` do it for the
declarations of ``kartograf/catalog/commands/``. The full catalog is built once
per process and is read-only; the filters (a group, a command, with or without
parameters) are views of it.
"""

import functools
from collections.abc import Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType

from kartograf.catalog.commands import declared
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.model import (
    FULL,
    OVERVIEW,
    Catalog,
    CommandInfo,
    ConstraintInfo,
    ErrorCodeInfo,
    ExampleInfo,
    ExitCodeInfo,
    GroupInfo,
    ParamInfo,
    ProductInfo,
    SchemaInfo,
)
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Group,
    Param,
    check_declarations,
    resolve,
    sorted_groups,
)
from kartograf.error_report import ERROR_CODES, EXIT_CODES
from kartograf.exceptions import ValidationError
from kartograf.serialization import SCHEMAS
from kartograf.sources.registry import sources_for

LANGUAGE = "pl"

# The description of every document schema of the library; a registered schema
# without one is not listed in the catalog (a test requires one for each).
SCHEMA_DESCRIPTIONS = {
    "kartograf-download/1": "Wynik komendy danych: pliki, pliki surowe, wejscia, "
    "bledy, nieaktualne pozycje, podsumowanie i komunikaty; ok: false = czesc "
    "jednostek sie nie powiodla",
    "kartograf-plan/1": "Plan aktualizacji (sprawdzenie bez pobierania): pozycje "
    "z porownaniem lokalnej wersji ze zrodlem i komunikaty; ok: false = czesci "
    "pozycji nie dalo sie sprawdzic",
    "kartograf-availability/1": "Raport dostepnosci produktu dla obszaru: lata, "
    "uklady, rozdzielczosci, formaty i polecenia pobrania kompletnych kombinacji",
    "kartograf-sheet/1": "Opis godla arkusza: system, skala, czlony, uklad, "
    "obwiednia i komendy, ktore przyjmuja to godlo",
    "kartograf-sheets/1": "Godla arkuszy obszaru w wybranej skali i ukladzie godel",
    "kartograf-sources/1": "Zrodla danych grupy z rejestru: dostawca, katalog "
    "w magazynie, wybor flag i sygnaly aktualnosci",
    "kartograf-layers/1": "Warstwy produktu: BDOT10k, ZABAGED, Data50, Data250, "
    "klasy BDOO, lata CORINE albo wlasciwosci SoilGrids",
    "kartograf-project-state/1": "Stan projektu po init, add albo remove: "
    "magazyn i zadania",
    "kartograf-project-report/1": "Wynik pobrania zadan projektu: wyniki zadan "
    "i przypiete pliki",
    "kartograf-project-check/1": "Sprawdzenie projektu (status, verify, "
    "sprawdzenie aktualnosci): pliki zadan z wynikiem",
    "kartograf-cache/1": "Cache metadanych: sciezka, rozmiar i liczby wpisow "
    "wg rodzaju",
    "kartograf-store-overview/1": "Przeglad magazynu: segmenty i liczby wpisow",
    "kartograf-store-entries/1": "Wpisy magazynu: pliki z sidecarami",
    "kartograf-store-sidecar/1": "Sidecar jednego pliku magazynu (kartograf-meta/1)",
    "kartograf-error/1": "Blad komendy: kod, komunikat, podpowiedz, wyjatek, "
    "kod wyjscia i szczegoly",
    "kartograf-catalog/1": "Katalog komend: grupy, komendy, parametry, "
    "ograniczenia, przyklady, tabele kodow wyjscia i bledow oraz schematy",
}


def _frozen(value: object) -> object:
    """Freeze mappings read-only and lists as tuples.

    The encoder writes them back as objects and arrays.
    """
    if isinstance(value, Mapping):
        return _frozen_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_frozen(item) for item in value)
    return value


def _frozen_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _frozen(item) for key, item in mapping.items()})


def _param_info(param: Param) -> ParamInfo:
    allowed = resolve(param.allowed)
    return ParamInfo(
        name=param.name,
        argument=param.api_argument,
        flag=param.cli_flag,
        short=param.short,
        positional=param.positional,
        kind=param.kind,
        required=param.required,
        task=param.task,
        allowed=None if allowed is None else tuple(allowed),
        default=param.default,
        cli_default=param.cli_default,
        accepts=param.accepts,
        section=param.section,
        description=resolve(param.description),
    )


def _constraint_info(constraint: Constraint) -> ConstraintInfo:
    when = constraint.when
    return ConstraintInfo(
        type=constraint.type,
        param=constraint.param,
        params=constraint.params,
        when=None if when is None else _frozen_mapping(when),
        message=constraint.message,
    )


def _example_info(command: Command, example: Example) -> ExampleInfo:
    return ExampleInfo(
        title=example.title,
        options=_frozen_mapping(example.options),
        command_line=example_command_line(command, example),
    )


def _check_references(command: Command) -> None:
    """Constraints and examples name only the parameters of their command."""
    names = {param.name for param in command.params}
    for constraint in command.constraints:
        refs = [constraint.param, *constraint.params, *(constraint.when or {})]
        for ref in refs:
            if ref is not None and ref not in names:
                raise ValueError(
                    f"{command.id}: constraint {constraint.type} names {ref!r}, "
                    "which is not a parameter"
                )
    for example in command.examples:
        for key in (*example.options, *example.run):
            if key not in names:
                raise ValueError(
                    f"{command.id}: an example names {key!r}, which is not a parameter"
                )


def _command_info(command: Command) -> CommandInfo:
    """Return the command with its parameters, constraints and examples."""
    _check_references(command)
    return CommandInfo(
        id=command.id,
        group=command.group,
        name=command.name,
        summary=command.summary,
        description=resolve(command.description) or command.summary,
        kind=command.kind,
        effects=command.effects,
        idempotent=command.idempotent,
        destructive=command.destructive,
        project_task=command.project_task,
        function=command.function,
        check_function=command.check_function,
        result_schema=command.result_schema,
        check_result_schema=command.check_result_schema,
        supports_check=command.supports_check,
        check_tool=command.check_tool,
        cli=command.cli_words,
        tool=command.tool,
        params=tuple(_param_info(param) for param in command.params),
        constraints=tuple(_constraint_info(c) for c in command.constraints),
        examples=tuple(_example_info(command, e) for e in command.examples),
    )


def _product_infos(group: Group) -> tuple[ProductInfo, ...]:
    infos = []
    for name, summary in resolve(group.products):
        sources = sources_for(product=name)
        countries = tuple(dict.fromkeys(source.country.lower() for source in sources))
        infos.append(
            ProductInfo(
                name, summary, countries, tuple(source.key for source in sources)
            )
        )
    return tuple(infos)


def _group_info(group: Group, commands: Sequence[Command]) -> GroupInfo:
    ids = tuple(c.id for c in commands if c.cli is not None and c.group == group.name)
    return GroupInfo(
        name=group.name,
        summary=group.summary,
        description=group.description,
        products=_product_infos(group),
        commands=ids,
    )


def _schema_infos(commands: Sequence[Command]) -> tuple[SchemaInfo, ...]:
    infos = []
    for schema in SCHEMAS:
        description = SCHEMA_DESCRIPTIONS.get(schema)
        if description is None:
            continue
        producers = tuple(
            c.id for c in commands if schema in (c.result_schema, c.check_result_schema)
        )
        infos.append(SchemaInfo(schema, description, producers))
    return tuple(infos)


def _build_full(commands: Sequence[Command], groups: Sequence[Group]) -> Catalog:
    """Return the catalog of every command: the source of every view.

    It has the parameters, constraints, examples and the tables.
    """
    from kartograf import __version__  # the package imports the catalog

    check_declarations(commands, groups)
    return Catalog(
        view=FULL,
        kartograf_version=__version__,
        language=LANGUAGE,
        groups=tuple(_group_info(g, commands) for g in sorted_groups(groups)),
        commands=tuple(_command_info(command) for command in commands),
        exit_codes=tuple(
            ExitCodeInfo(row.code, row.name, row.meaning) for row in EXIT_CODES
        ),
        errors=tuple(
            ErrorCodeInfo(row.code, row.exception, row.exit_code, row.meaning)
            for row in ERROR_CODES
        ),
        schemas=_schema_infos(commands),
    )


def _select(
    full: Catalog,
    *,
    group: str | None,
    command: str | None,
    params: bool | None,
    tables: bool | None,
) -> Catalog:
    """Return a view of the full catalog (spec 8.5).

    The overview when nothing is selected and no parameters are asked for, else the full
    view.
    """
    groups, commands = full.groups, full.commands
    if group is not None:
        names = tuple(g.name for g in groups)
        if group not in names:
            raise ValidationError(
                f"Nieznana grupa {group!r} - dostepne: {', '.join(names)}",
                option="group",
                allowed=names,
            )
        groups = tuple(g for g in groups if g.name == group)
        commands = tuple(c for c in commands if c.group == group and c.cli is not None)
    if command is not None:
        ids = tuple(c.id for c in commands)
        if command not in ids:
            scope = f"grupy {group}" if group is not None else "katalogu"
            raise ValidationError(
                f"Nieznana komenda {command!r} {scope} - dostepne: {', '.join(ids)}",
                option="command",
                allowed=ids,
            )
        commands = tuple(c for c in commands if c.id == command)
        owners = {c.group for c in commands}
        groups = tuple(g for g in groups if g.name in owners)
    selected = group is not None or command is not None
    with_params = params if params is not None else command is not None
    if not with_params:
        commands = tuple(
            replace(c, params=None, constraints=None, examples=None) for c in commands
        )
    if tables is None:
        tables = with_params and not selected  # the whole catalog: everything
    return Catalog(
        view=FULL if selected or with_params else OVERVIEW,
        kartograf_version=full.kartograf_version,
        language=full.language,
        groups=groups,
        commands=commands,
        exit_codes=full.exit_codes if tables else None,
        errors=full.errors if tables else None,
        schemas=full.schemas if tables else None,
    )


def build_catalog(
    commands: Sequence[Command],
    groups: Sequence[Group],
    *,
    params: bool | None = None,
    group: str | None = None,
    command: str | None = None,
    tables: bool | None = None,
) -> Catalog:
    """Return the catalog of the given declarations.

    The view arguments are those of ``get_catalog``; nothing is cached.

    Raises
    ------
    ValueError
        The declarations are inconsistent (a group without commands, a constraint
        or an example naming a parameter the command does not have).
    ValidationError
        An unknown ``group`` or ``command`` (``option`` names the argument,
        ``allowed`` the known values).
    """
    full = _build_full(commands, groups)
    return _select(full, group=group, command=command, params=params, tables=tables)


@functools.cache
def _full_catalog() -> Catalog:
    declarations = declared()
    return _build_full(declarations.commands, declarations.groups)


@functools.cache
def _view(
    group: str | None, command: str | None, params: bool | None, tables: bool | None
) -> Catalog:
    return _select(
        _full_catalog(), group=group, command=command, params=params, tables=tables
    )


def clear_caches() -> None:
    """Forget the catalogs built so far (for tests that swap the declarations)."""
    _full_catalog.cache_clear()
    _view.cache_clear()


def get_catalog(
    *,
    group: str | None = None,
    command: str | None = None,
    params: bool | None = None,
    tables: bool | None = None,
) -> Catalog:
    """Return the catalog of the commands: ``kartograf catalog --json``.

    Without arguments the *overview*: every group (summary, product names) and
    every command (id, summary, MCP tool, whether it can check for updates) -
    a short document an agent reads first. Everything else is asked for.

    Parameters
    ----------
    group : str, optional
        Only this group and its commands, with the products and their sources.
    command : str, optional
        Only this command (its id: ``elevation download``, ``parse``,
        ``find_sheets``); the view has its parameters, constraints and examples.
    params : bool, optional
        ``True``: parameters, constraints and examples of every selected command
        (without ``group`` and ``command``: of all of them, the whole catalog,
        about 200 thousand characters); ``False``: never; ``None``: only when
        ``command`` is given.
    tables : bool, optional
        ``True``: the exit code and error code tables and the document schemas;
        ``False``: never; ``None``: only for the whole catalog (``params=True``
        without ``group`` and ``command``).

    Returns
    -------
    Catalog
        ``view`` is ``overview`` when nothing is selected and no parameters are
        asked for, else ``full``. The same object for the same arguments.

    Raises
    ------
    ValidationError
        An unknown ``group`` or ``command``.
    """
    return _view(group, command, params, tables)


def data_commands() -> tuple[CommandInfo, ...]:
    """Return the data commands a project task may run, with their parameters.

    The twelve commands of ``COMMANDS`` in its order (``project_task`` is true).
    """
    return tuple(c for c in _full_catalog().commands if c.project_task)
