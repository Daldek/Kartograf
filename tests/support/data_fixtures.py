"""Offline fixtures of the data commands shared by the command, CLI and MCP tests.

Stores are real (``tmp_path``) and written by the real library functions;
only the sources are fakes of the download tests: PL sheets
(``FakeCampaignProvider``) and the land cover providers by name (SoilGrids,
CORINE, BDOT10k fakes of the land cover tests).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from kartograf.landcover.manager import LandCoverManager
from tests.integration.test_manager_campaigns import C14, FakeCampaignProvider

G = "N-34-139-C-a-3-1"
PL_SHEET = {
    "product": "nmt",
    "sheet": G,
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
HSG_SHEET = "N-34-130-D"


@contextmanager
def pl_sheets(
    fake: FakeCampaignProvider | None = None,
) -> Iterator[FakeCampaignProvider]:
    """PL sheets of ``download_data`` from a fake index (newest: 84183)."""
    provider = fake if fake is not None else FakeCampaignProvider(C14)
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(provider, None),
    ):
        yield provider


@contextmanager
def landcover_sources(**by_name) -> Iterator[None]:
    """``LandCoverManager`` by name -> a fresh no-network provider."""
    with patch.object(
        LandCoverManager,
        "_get_provider_by_name",
        staticmethod(lambda name, cache=None: by_name[name]()),
    ):
        yield
