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
import textwrap
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


def _directory(source: SourceDescriptor) -> str:
    """KATALOG of ``list-sources``: the storage segment of a source below
    ``--output`` with its placeholders named (``nmt/pl_<uklad>_1m_<uklad-wys>``)."""
    return source.storage_subdir.replace("{system}", "<uklad>").replace(
        "{vcrs}", "<uklad-wys>"
    )


def add_list_sources(
    commands: argparse._SubParsersAction,
    group: str,
    products: Sequence[str],
    choice: Callable[[SourceDescriptor], str],
) -> None:
    """``<group> list-sources``: the registered sources of ``products``.

    The table comes from the descriptor registry (``kartograf.sources``) -
    no network, no second catalogue. ``choice`` gives the flags of every
    required choice of a source in ``<group> download`` (WYBOR, e.g.
    ``--product nmt --country pl --resolution 1m --vertical-crs
    EVRF2007|KRON86``). KATALOG is the storage segment below ``--output``,
    KLUCZ the ``dataset`` field of the sidecar.
    """
    parser = commands.add_parser(
        "list-sources",
        help="Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        description=f"Wypisz zrodla danych grupy {group} z rejestru zrodel "
        "(bez sieci): WYBOR = wymagane flagi wyboru zrodla w download (a|b - "
        "jedna z wartosci), KATALOG = katalog plikow pod --output, KLUCZ = "
        "pole dataset w sidecarze pliku",
    )

    def list_sources(_args: argparse.Namespace) -> int:
        sources = [d for product in products for d in sources_for(product=product)]
        header = ("WYBOR", "KRAJ", "DOSTAWCA", "KATALOG", "KLUCZ", "NAZWA")
        rows = [
            (choice(d), d.country, d.provider_name, _directory(d), d.key, d.name)
            for d in sources
        ]
        widths = [
            max(len(row[i]) for row in (header, *rows)) for i in range(len(header))
        ]
        print(f"Zrodla grupy {group}:")
        for row in (header, *rows):
            cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
            print("  " + "  ".join(cells).rstrip())
        print()
        print(
            textwrap.fill(
                "WYBOR: a|b = jedna z wartosci. KATALOG: pod --output; <uklad> "
                "i <uklad-wys> wynikaja z wyboru, wybory wariantu (skala, "
                "format, rocznik) dopisuja czlony _<wartosc>.",
                width=78,
            )
        )
        print(f"Opcje pobrania: kartograf {group} download --help")
        return 0

    parser.set_defaults(_handler=list_sources)
