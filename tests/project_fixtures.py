"""Offline fixtures shared by the project manifest tests (ADR-040).

Stores are real (``tmp_path``) and written by the real library functions;
only the sources are fakes of the download tests: PL sheets
(``FakeCampaignProvider``), LAZ tiles (``FakeProvider`` of the LAZ tests),
CZ (``_cz_provider_mock``), BDOT10k packages (``FakePackages``), SoilGrids
(``RasterSoilGrids``, ``FakeSoilGrids``) and CORINE (``FakeCorine``).
"""

import shutil
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from kartograf.core.bbox import BBox
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from tests.test_landcover_output_params import FakePackages
from tests.test_laz_download import FakeProvider, _selection, _tile
from tests.test_manager_campaigns import C14, FakeCampaignProvider

G = "N-34-139-C-a-3-1"
PL_SHEET = {
    "product": "nmt",
    "sheet": G,
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
LAZ_BBOX = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
LAZ_AREA = {
    "product": "laz",
    "bbox": LAZ_BBOX,
    "country": "pl",
    "vertical_crs": "EVRF2007",
}
BDOT_BBOX = BBox(770000, 509000, 772000, 511000, "EPSG:2180")
HSG_SHEET = "N-34-130-D"
CZ_FACTORY = "kartograf.providers.cuzk.create_dmr_provider"


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


class LazTiles(FakeProvider):
    """LAZ provider selecting ``sheets`` (mutable: a new flight adds a tile);
    ``download`` writes ``content`` (``b"LASF"`` by default)."""

    def __init__(self, *sheets: str, failing=()) -> None:
        super().__init__(failing=failing)
        self.sheets = list(sheets)
        self.content = b"LASF"

    def select_tiles(self, bbox, **kwargs):
        return _selection(*(_tile(sheet) for sheet in self.sheets))

    def download(self, url, target, **kwargs):
        path = super().download(url, target, **kwargs)
        path.write_bytes(self.content)
        return path


@contextmanager
def laz_tiles(provider: LazTiles) -> Iterator[LazTiles]:
    with patch(
        "kartograf.providers.pl.gugik_laz.GugikLazProvider",
        side_effect=lambda **_kw: provider,
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


@contextmanager
def bdot(teryts, packages: FakePackages | None = None) -> Iterator[FakePackages]:
    """BDOT10k packages of ``FakePackages``; PRG answers ``teryts``."""
    fake = packages if packages is not None else FakePackages()
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(Bdot10kProvider, "download_package", side_effect=fake)
        )
        stack.enter_context(
            patch.object(Bdot10kProvider, "teryts_for_area", return_value=list(teryts))
        )
        yield fake


def copy_manifest(project: Path, target: Path) -> Path:
    """A colleague's copy: the manifest only, with an empty store ``data``."""
    target.mkdir(parents=True)
    shutil.copy2(project / "kartograf-project.json", target)
    (target / "data").mkdir()
    return target
