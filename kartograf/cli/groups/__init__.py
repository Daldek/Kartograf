"""
Command groups of the CLI by data type (ADR-039).

Every public module of this package is one group (``kartograf <grupa>
<komenda>``) and defines ``register(subparsers)``; ``register_groups`` finds
the modules by name, so a new group is one new module - no shared file to
edit. Modules starting with ``_`` are helpers, not groups.

A group parser built with ``add_group`` prints its help when called without
a command; each command sets ``_handler`` (``set_defaults``), the function
``commands._dispatch`` calls with the parsed arguments.
"""

import argparse
from collections.abc import Callable, Sequence
from importlib import import_module
from pkgutil import iter_modules

from kartograf.sources.descriptor import SourceDescriptor
from kartograf.sources.registry import sources_for


def register_groups(subparsers: argparse._SubParsersAction) -> None:
    """Register every group module, in the order of module names."""
    for module in sorted(iter_modules(__path__), key=lambda m: m.name):
        if not module.name.startswith("_"):
            import_module(f"{__name__}.{module.name}").register(subparsers)


def add_group(
    subparsers: argparse._SubParsersAction, name: str, *, help: str, description: str
) -> argparse._SubParsersAction:
    """The ``kartograf <name>`` parser; returns the subparsers of its commands."""
    group = subparsers.add_parser(name, help=help, description=description)
    group.set_defaults(_group_parser=group)
    return group.add_subparsers(
        dest=f"{name}_command", title="komendy", metavar="KOMENDA"
    )


def add_list_sources(
    commands: argparse._SubParsersAction,
    group: str,
    products: Sequence[str],
    choice: Callable[[SourceDescriptor], str] | None = None,
) -> None:
    """``<group> list-sources``: the registered sources of ``products``.

    The table comes from the descriptor registry (``kartograf.sources``) -
    no network, no second catalogue. ``choice`` gives the flag selecting a
    source in ``<group> download`` (e.g. ``--product nmt``); ``None`` for a
    group with one source. KLUCZ is the ``dataset`` field of the sidecar.
    """
    parser = commands.add_parser(
        "list-sources",
        help="Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        description=f"Wypisz zrodla danych grupy {group} z rejestru zrodel "
        "(bez sieci); KLUCZ = pole dataset w sidecarze pliku",
    )

    def list_sources(_args: argparse.Namespace) -> int:
        sources = [d for product in products for d in sources_for(product=product)]
        header: tuple[str, ...] = ("KRAJ", "DOSTAWCA", "KLUCZ", "NAZWA")
        rows: list[tuple[str, ...]] = [
            (d.country, d.provider_name, d.key, d.name) for d in sources
        ]
        if choice is not None:
            header = ("WYBOR", *header)
            rows = [(choice(d), *row) for d, row in zip(sources, rows, strict=True)]
        widths = [
            max(len(row[i]) for row in (header, *rows)) for i in range(len(header))
        ]
        print(f"Zrodla grupy {group}:")
        for row in (header, *rows):
            cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
            print("  " + "  ".join(cells).rstrip())
        print()
        print(f"Opcje pobrania: kartograf {group} download --help")
        return 0

    parser.set_defaults(_handler=list_sources)
