"""
CLI module for Kartograf.

This module provides command-line interface for interacting with
the Kartograf library, including parsing map sheet identifiers
and downloading NMT data.

``main`` is imported on first access: ``python -m kartograf.cli.commands``
runs that module as ``__main__``, and importing it here first would make
``runpy`` warn about a module already in ``sys.modules``.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kartograf.cli.commands import main

__all__ = ["main"]


def __getattr__(name: str) -> Any:
    if name == "main":
        from kartograf.cli.commands import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
