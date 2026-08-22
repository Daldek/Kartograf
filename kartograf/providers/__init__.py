"""
Providers module for Kartograf.

This module re-exports a historical subset of the provider classes
(dating from before the ``providers.pl``/``providers.cuzk`` package split).
It does NOT re-export every provider that ships in this release (e.g.
``GugikNmptProvider``, ``GugikOrtoProvider``, or the ``providers.cuzk``
package with ``CuzkDmrProvider``/``create_dmr_provider`` are missing here).

For the complete, currently maintained provider list, use the top-level
package API: ``from kartograf import ...`` (see ``kartograf/__init__.py``).

Polish providers (Gugik*, Bdot10kProvider) live in ``kartograf.providers.pl``;
CUZK (Czech) providers live in ``kartograf.providers.cuzk``.
"""

from kartograf.providers.base import BaseProvider, LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.soilgrids import SoilGridsProvider

__all__ = [
    "BaseProvider",
    "GugikProvider",
    "GugikLazProvider",
    "LandCoverProvider",
    "Bdot10kProvider",
    "CorineProvider",
    "SoilGridsProvider",
]
