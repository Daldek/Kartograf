"""Offline fixtures shared by the project manifest tests (ADR-040).

Stores are real (``tmp_path``) and written by the real library functions;
only the sources are fakes of the download tests: PL sheets
(``FakeCampaignProvider``), LAZ tiles (``FakeProvider`` of the LAZ tests),
CZ (``_cz_provider_mock``), BDOT10k packages (``FakePackages``), SoilGrids
(``RasterSoilGrids``, ``FakeSoilGrids``) and CORINE (``FakeCorine``).
"""

import os
import shutil
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf import init_project
from kartograf.core.bbox import BBox
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from tests.fake_packages import FakePackageSession, package_route
from tests.test_cli import _cz_provider_mock
from tests.test_collections_products import serve_prg_obreby
from tests.test_feature_bbox import PRG_BBOX
from tests.test_landcover_output_params import FakePackages
from tests.test_laz_download import FakeProvider, _selection, _tile
from tests.test_manager_campaigns import C14, FakeCampaignProvider
from tests.test_wcs_cutout import ALL_LAND, MASK, _synthetic_session

# Collections (ADR-042): PRG obreby of a recorded area, 3D models and the
# BDOT10k archive of powiat 1261 from fixture packages.
PRG_AREA = {"product": "admin", "country": "pl", "level": "obreb", "bbox": PRG_BBOX}
BUILDINGS = {"product": "buildings", "teryt": "1261", "lod": 1, "year": 2024}
BDOT_ARCHIVE = {"source": "bdot10k", "teryt": "1261", "year": 2024, "format": "SHP"}


@contextmanager
def collection_sources() -> Iterator[FakePackageSession]:
    """PRG WFS (A06 answers), the LoD1 2024 and BDOT10k 2024 SHP packages of
    1261 for ``download_collection`` and the BDOT10k archive."""
    session = FakePackageSession(
        dict(
            package_route(name)
            for name in ("buildings_lod1_2024_1261", "bdot10k_2024_shp_1261")
        )
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        service = serve_prg_obreby(monkeypatch)
        wfs_get = service.get

        def route(url, params=None, **kwargs):
            if url in session.routes:
                return session.get(url, **kwargs)
            return wfs_get(url, params=params, **kwargs)

        monkeypatch.setattr(service, "get", route)
        monkeypatch.setattr(
            LandCoverManager,
            "_get_provider_by_name",
            staticmethod(lambda name, cache=None: Bdot10kProvider(session=session)),
        )
        yield session


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
# A tiny area inside the rectangular envelopes of PL and CZ (Cieszyn):
# ``country="auto"`` gives one cutout per country.
AUTO_CUTOUT = {
    "product": "nmt",
    "bbox": BBox(18.6300, 49.7450, 18.6303, 49.7452, "EPSG:4326"),
    "country": "auto",
    "resolution": {"pl": "1m", "cz": "2m"},
    "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
    "cutout": True,
    "horizontal_crs": "EPSG:5514",
}


def new_project(root: Path, name: str = "projekt", store: str = "data") -> Path:
    """A project ``root/name`` with the store ``<store>`` relative to it (the
    manifest copied elsewhere points at the store next to the copy)."""
    directory = root / name
    init_project(directory, output_dir=os.path.relpath(directory / store))
    return directory


@contextmanager
def auto_pl_cz(cz=None) -> Iterator[None]:
    """PL cutout from a synthetic WCS (all land) and CZ from a provider mock."""

    def pl_provider(*_args, **_kwargs):
        return GugikProvider(
            session=_synthetic_session(lambda xs, ys: xs + ys),
            vertical_crs="EVRF2007",
            resolution="1m",
        )

    with (
        patch(MASK, return_value=ALL_LAND),
        patch("kartograf.providers.pl.create_nmt_provider", side_effect=pl_provider),
        patch(CZ_FACTORY, return_value=cz if cz is not None else _cz_provider_mock()),
    ):
        yield


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
    ``download_tile`` writes ``content`` (``b"LASF"`` by default)."""

    def __init__(self, *sheets: str, failing=()) -> None:
        super().__init__(failing=failing)
        self.sheets = list(sheets)
        self.content = b"LASF"

    def select_tiles(self, bbox, **kwargs):
        return _selection(*(_tile(sheet) for sheet in self.sheets))

    def download_tile(self, url, target, **kwargs):
        path = super().download_tile(url, target, **kwargs)
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
