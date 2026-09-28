"""Testy wycinka PL --target-crs (ADR-027): API biblioteki, tresc, walidacje,
sidecar, przeplyw CLI."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rasterio

from kartograf.cli.commands import main
from kartograf.cli.download_cmd import _download_pl_bbox
from kartograf.core.sheet_parser import BBox
from kartograf.download.cutout import build_pl_cutout, prepare_pl_cutout
from kartograf.transform.crs import (
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_NODATA = -9999.0
_APEX = (530050.0, 382050.0)  # EPSG:2180, okolice Piotrkowa Trybunalskiego


def _write_sheet_asc(path, west, south, size=100, pixel=1.0, apex=None):
    """Syntetyczny 'arkusz' AAIGrid: stozek wokol apex albo plaski 100.0."""
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = (south + size * pixel) - (rows + 0.5) * pixel
    if apex is None:
        data = np.full((size, size), 100.0, dtype="float32")
    else:
        data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    header = (
        f"ncols {size}\nnrows {size}\nxllcorner {west}\nyllcorner {south}\n"
        f"cellsize {pixel}\nNODATA_value {_NODATA}\n"
    )
    body = "\n".join(" ".join(f"{v:.3f}" for v in row) for row in data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body + "\n", encoding="ascii")
    return path


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX, allow_network_grids=False
        ),
    )


class TestBuildPlCutout:
    """Spec 8a-c: regresja tresci, mozaika z nodata, crop bez warpa."""

    def test_target_5514_content_lt_1px(self, tmp_path):
        """Mozaika 2 arkuszy + warp: wierzcholek tam, gdzie mowi pyproj."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        west = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "b.asc", 530100, 382000, apex=_APEX)
        bbox_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX))
        bbox_target = bbox_to_crs(bbox_2180, "EPSG:5514")
        target = tmp_path / "out" / "cut.tif"

        build_pl_cutout([west, east], bbox_2180, bbox_target, 1.0, pinned, target)

        with rasterio.open(target) as ds:
            assert ds.crs.to_epsg() == 5514
            data = ds.read(1, masked=True)
            row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
            gx, gy = ds.xy(int(row), int(col))
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"
        assert list(target.parent.glob("*.mosaic.tif")) == []  # sprzatanie tmp

    def test_target_5514_full_coverage_from_source_bbox(self, tmp_path):
        """R-01: arkusze z ``bbox_source_2180`` pokrywaja CALA siatke wyniku.

        Obraz prostokata 2180 w Krovaku jest czworokatem obroconym, wiec
        obwiednia celu wystaje poza zadanie — bez zapasu po stronie zrodla
        rogi wyniku byly by nodata.
        """
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:5514",
            output_dir=str(tmp_path),
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        sheets = [
            _write_sheet_asc(tmp_path / "a.asc", 529900, 381950, size=200),
            _write_sheet_asc(tmp_path / "b.asc", 530100, 381950, size=200),
        ]

        build_pl_cutout(
            sheets,
            cut.bbox_source_2180,
            cut.bbox_target,
            1.0,
            cut.pinned,
            cut.target_path,
        )

        with rasterio.open(cut.target_path) as ds:
            data = ds.read(1)
        assert not (data == _NODATA).any()

    def test_nodata_seam_between_sheets(self, tmp_path):
        """Mozaika arkuszy z przerwa: pas nodata w wyniku, nigdy zero."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        b = _write_sheet_asc(tmp_path / "b.asc", 530120, 382000)  # 20 m przerwy
        bbox = BBox(530010, 382010, 530210, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        build_pl_cutout([a, b], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.nodata == _NODATA
            data = ds.read(1)
        # przerwa 530100..530120 = kolumny 90..109 (min_x 530010, piksel 1 m)
        assert (data[:, 90:110] == _NODATA).all()
        assert not (data == 0.0).any()

    def test_target_2180_crop_only(self, tmp_path):
        """EPSG:2180: sam crop — GeoTIFF z wpisanym CRS, zasieg = bbox."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        build_pl_cutout([a], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.crs is not None and ds.crs.to_epsg() == 2180
            assert ds.bounds == (530010.0, 382010.0, 530090.0, 382090.0)

    def test_failed_build_keeps_previous_result(self, tmp_path):
        """Przerwana budowa NIE niszczy poprzedniego wyniku ani nie zostawia tmp.

        Obie sciezki zapisu sa atomowe (``os.replace`` przy samym cropie,
        wewnetrzny ``os.replace`` w ``warp_to_grid``), wiec pod finalna sciezka
        nie da sie zostawic polzapisanego pliku — a skoro tak, to kasowanie
        starego wyniku bylo czysta utrata danych (kod 0 calego zadania na
        pograniczu pod ``--country auto``).
        """
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        target = tmp_path / "out" / "cut.tif"
        target.parent.mkdir()
        target.write_bytes(b"II*\x00poprzedni wynik")

        with (
            patch(
                "kartograf.transform.raster.warp_to_grid",
                side_effect=RuntimeError("warp przerwany"),
            ),
            pytest.raises(RuntimeError, match="warp przerwany"),
        ):
            build_pl_cutout(
                [a], bbox, bbox_to_crs(bbox, "EPSG:5514"), 1.0, pinned, target
            )

        assert target.read_bytes() == b"II*\x00poprzedni wynik"
        assert list(target.parent.glob("*.mosaic.tif")) == []


class TestPreparePlCutout:
    def test_target_2180_no_pinned_and_native_name(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.pinned is None
        assert cut.bbox_target is cut.bbox_2180
        # bez warpa siatka wyniku rowna sie zadaniu — zapas zbedny (R-01)
        assert cut.bbox_source_2180 is cut.bbox_2180
        assert cut.target_path == (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )

    def test_target_5514_builds_pinned_and_names_in_target(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.pinned is not None and cut.pinned.accuracy_m <= 1.0
        assert cut.bbox_target.crs == "EPSG:5514"
        # zrodlo szersze z KAZDEJ strony niz zadanie (R-01: pokrycie siatki)
        source = cut.bbox_source_2180
        assert source.crs == "EPSG:2180"
        assert source.min_x < cut.bbox_2180.min_x
        assert source.min_y < cut.bbox_2180.min_y
        assert source.max_x > cut.bbox_2180.max_x
        assert source.max_y > cut.bbox_2180.max_y
        # nazwa niesie wspolrzedne w ukladzie WYNIKU (Krovak: ujemne)
        assert cut.target_path.name.startswith("-")
        assert cut.target_path.parent == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        )

    def test_probe_point_is_center_of_request(self, tmp_path):
        """Operacje wybiera polityka Z PROBE w srodku zadania, nie sama polityka.

        Bez probe przeszlaby operacja, ktorej siatka nie pokrywa obszaru
        (inf/NaN dla zadania) — regula 3 polityki, lustro toru CZ.
        """
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        real = _pinned_2180_to("EPSG:5514")

        with patch(
            "kartograf.transform.crs.build_pinned_transform", return_value=real
        ) as build:
            prepare_pl_cutout(
                bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
            )

        policy = build.call_args.args[2]
        assert policy.probe_point == (530100.0, 382050.0)
        assert policy.min_accuracy_m == 1.0
        assert policy.allow_network_grids is False

    def test_vertical_kron86_lands_in_kron86_segment(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="KRON86"
        )
        assert "pl_1992_1m_kron86" in cut.target_path.parts

    def test_wgs84_bbox_normalized_to_2180(self, tmp_path):
        bbox = BBox(18.60, 49.75, 18.65, 49.77, "EPSG:4326")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.bbox_2180.crs == "EPSG:2180"
        assert 400000 < cut.bbox_2180.min_x < 700000  # rzad wielkosci 2180

    def test_unavailable_operation_raises_transform_error(self, tmp_path):
        """Fail-fast: brak operacji -> TransformError PRZED siecia (spec 6.3)."""
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.transform.crs.build_pinned_transform",
                side_effect=TransformUnavailableError("brak operacji", remedy="R"),
            ),
            pytest.raises(TransformUnavailableError),
        ):
            prepare_pl_cutout(
                bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
            )


_DL = "kartograf.cli.download_cmd"
# warstwa biblioteczna wycinka (R3) — tu zyja selekcja arkuszy i manager
_CUT = "kartograf.download.cutout"


def _pl_args(tmp_path, **overrides):
    """Namespace jak z argparse dla bezposrednich wywolan _download_pl_bbox."""
    base = dict(
        godlo=None,
        bbox="530010,382010,530190,382090",
        bbox_crs="EPSG:2180",
        geometry=None,
        layer=None,
        scale=None,
        output=str(tmp_path),
        force=False,
        quiet=True,
        vertical_crs=None,
        resolution=None,
        product="nmt",
        system=None,
        country="pl",
        target_crs="EPSG:2180",
        workers=1,
        year=None,
        min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


_PARENT = {
    "bbox": [530010.0, 382010.0, 530190.0, 382090.0],
    "bbox_crs": "EPSG:2180",
    "countries": ["PL"],
}

# Bbox zadania wspolny dla przeplywow ponizej. Stala, a nie obiekt budowany
# w helperze — testy sprawdzaja TOZSAMOSC obiektu podanego do selekcji arkuszy
# (dowod, ze bez --target-crs zapas NIE wchodzi do selekcji).
_BBOX_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")


class TestDownloadPlBboxCutout:
    """Spec 8: przeplyw wycinka na poziomie workera PL (mockowane pobranie)."""

    def _run(self, tmp_path, args, sheets, failed=(), provider=None):
        """Worker PL z mockowanym pobraniem; zwraca ``(rc, manager, find)``.

        Mock KLASY ``DownloadManager`` (kwargs konstruktora, np.
        ``sidecar_extra``) zostaje w ``self.dm`` — zwrot zostaje trojka, bo
        rozpakowuja go kolejne testy.
        """
        from kartograf.download.manager import DownloadResult

        provider = provider or SimpleNamespace(vertical_crs="EVRF2007")
        manager = Mock()
        manager.download_sheets.return_value = list(sheets)
        manager.last_result = DownloadResult(failed=list(failed))
        with (
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1", "N-2"]) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager) as dm,
        ):
            rc = _download_pl_bbox(args, _BBOX_2180, _PARENT)
        self.dm = dm
        return rc, manager, find

    def test_creates_cutout_and_sidecar(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        assert target.exists()
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text("utf-8")
        )
        assert payload["dataset"] == "pl.gugik.nmt_1m"
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["transform"] is None  # 2180 = sam crop (spec 6.1)
        assert payload["nodata"] == _NODATA
        assert payload["vertical_crs"] == "EPSG:9651"  # EVRF2007-PL, kanal arkuszy
        assert payload["request"]["bbox_crs"] == "EPSG:2180"
        assert payload["extra"]["parent_request"] == _PARENT
        # sidecary ARKUSZY (cache) tez niosa rodzica zadania — jak bez wycinka
        assert self.dm.call_args.kwargs["sidecar_extra"] == {"parent_request": _PARENT}

    def test_target_5514_sidecar_has_pinned_transform(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _manager, find = self._run(
            tmp_path, _pl_args(tmp_path, target_crs="EPSG:5514"), sheets
        )

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        payload = json.loads((cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8"))
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["transform"]["horizontal"].startswith("pinned: ")
        assert payload["request"]["bbox_crs"] == "EPSG:5514"
        # R-01: do SELEKCJI arkuszy idzie bbox Z ZAPASEM, nie samo zadanie —
        # inaczej rogi obroconej siatki wyniku wypadaja poza pobrane arkusze
        sent = find.call_args.args[0]
        assert sent.min_x < _BBOX_2180.min_x
        assert sent.max_x > _BBOX_2180.max_x
        assert sent.min_y < _BBOX_2180.min_y
        assert sent.max_y > _BBOX_2180.max_y

    def test_5m_kron86_grid_dataset_vertical_and_segment(self, tmp_path):
        """Caly przeplyw 5m w jednym tescie: siatka, deskryptor, pion, segment.

        ``--resolution 5m`` z ``--vertical-crs KRON86`` jest korygowane do
        EVRF2007 w fabryce providera (5m nie istnieje w KRON86), wiec wycinek
        musi isc za PROVIDEREM, nie za surowa flaga CLI. Dla arkuszy ta klasa
        bledu jest broniona od dawna — tor wycinka byl w niej luka: piksel 1 m
        z danych 5 m (25x rozmiar pliku) albo segment ``pl_1992_5m_kron86``
        z sidecarem EPSG:9650 przechodzily cala suite.
        """
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 529900, 381950, size=40, pixel=5.0),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 381950, size=40, pixel=5.0),
        ]
        args = _pl_args(
            tmp_path, resolution="5m", vertical_crs="KRON86", target_crs="EPSG:5514"
        )
        rc, *_ = self._run(tmp_path, args, sheets)

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        with rasterio.open(tifs[0]) as ds:
            assert ds.res == (5.0, 5.0)
        payload = json.loads((cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8"))
        assert payload["dataset"] == "pl.gugik.nmt_5m"
        assert payload["vertical_crs"] == "EPSG:9651"

    def test_unexpected_raster_error_returns_1(self, tmp_path, capsys):
        """Blad spoza (ValidationError, TransformError) tez konczy sie kodem 1.

        ``mosaic_and_crop``/``warp_to_grid`` moga rzucic ``RasterioIOError``
        (uszkodzony arkusz z cache). Przeciek takiego wyjatku poza petle krajow
        ``_dispatch_area`` lamie kontrakt czesciowego sukcesu ADR-023.
        """
        from rasterio.errors import RasterioIOError

        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        with patch(
            f"{_CUT}.build_pl_cutout",
            side_effect=RasterioIOError("uszkodzony arkusz"),
        ):
            rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 1
        assert "uszkodzony arkusz" in capsys.readouterr().err

    def test_failed_sheet_returns_1_and_no_cutout(self, tmp_path):
        """Spec 6.1: wycinek wymaga kompletu pokrycia."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"])

        assert rc == 1
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()

    def test_error_lists_all_failed_sheets(self, tmp_path, capsys):
        """Komunikat wymienia WSZYSTKIE nieudane arkusze (``download_sheets``).

        Dotad pula watkow konczyla sie pierwszym wyjatkiem — uzytkownik
        poznawal jeden brakujacy arkusz na przebieg.
        """
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), [], failed=["N-1", "N-2"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "N-1" in err and "N-2" in err, err
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()

    def test_skip_existing_short_circuits_before_download(self, tmp_path):
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(b"II*\x00")
        rc, manager, find = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        # skrot dziala PRZED selekcja arkuszy — zero pracy na godlach
        find.assert_not_called()

    def test_without_target_crs_behaviour_unchanged(self, tmp_path):
        """Bez flagi: lista arkuszy jak dotad, zero wycinka (spec 6.1).

        Tor BEZ wycinka zostaje w ``cli.download_cmd`` — dlatego wlasne patche
        ``_DL``, a nie harness ``_run`` (ten patchuje ``download.cutout``).
        """
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        with (
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-1"]) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(f"{_DL}._download_godlo_list", return_value=(sheets, [])),
        ):
            rc = _download_pl_bbox(
                _pl_args(tmp_path, target_crs=None), _BBOX_2180, _PARENT
            )

        assert rc == 0
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()
        # bez wycinka zapas NIE wchodzi do selekcji — arkusze wyznacza
        # dokladnie zadanie uzytkownika (ten sam obiekt, nie kopia z marginesem)
        assert find.call_args.args[0] is _BBOX_2180


class TestGeometryCutout:
    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """MetadataCache laduje w cwd — poza repo i katalogiem wyjsciowym."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

    def test_geometry_mode_builds_cutout(self, tmp_path):
        from kartograf.cli.download_cmd import _download_pl_geometry
        from kartograf.download.manager import DownloadResult

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # sciezka nieuzywana: discovery zamockowane
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        args = _pl_args(tmp_path, bbox=None, geometry=str(geom))
        manager = Mock()
        manager.download_sheets.return_value = sheets
        manager.last_result = DownloadResult()

        with (
            # import lokalny w select_pl_cutout_sheets -> patch u zrodla
            # (ta sama konwencja co testy geometry w test_cli.py)
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1", "N-2"],
            ),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = _download_pl_geometry(args, geom, _PARENT, bbox=bbox)

        assert rc == 0
        assert (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        ).exists()

    def test_geometry_target_5514_covers_whole_envelope(self, tmp_path):
        """R-01 obowiazuje takze w `--geometry`: zapas wchodzi do SELEKCJI.

        Geometria wskazuje sam arkusz zachodni, ale obwiednia celu wraca do
        EPSG:2180 wieksza niz zadanie (obrot Krovaka) i siega juz na arkusz
        wschodni. Bez sumy z ``find_sheets_for_bbox`` wycinek ma na wschodniej
        krawedzi ramke nodata — przy tej samej fladze, ktora w trybie ``--bbox``
        daje komplet.
        """
        from kartograf.cli.download_cmd import _download_pl_geometry
        from kartograf.download.manager import DownloadResult

        sheets = {
            "N-1": _write_sheet_asc(tmp_path / "s1.asc", 529900, 381950, size=200),
            "N-2": _write_sheet_asc(tmp_path / "s2.asc", 530100, 381950, size=200),
        }
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # sciezka nieuzywana: discovery zamockowane
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        args = _pl_args(tmp_path, bbox=None, geometry=str(geom), target_crs="EPSG:5514")
        manager = Mock()
        # godla -> arkusze: do mozaiki trafiaja DOKLADNIE wybrane arkusze
        manager.download_sheets.side_effect = lambda godla, **kw: [
            sheets[g] for g in godla
        ]
        manager.last_result = DownloadResult()

        with (
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1"],
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1", "N-2"]) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = _download_pl_geometry(args, geom, _PARENT, bbox=_BBOX_2180)

        assert rc == 0
        cut = next(
            iter((tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif"))
        )
        with rasterio.open(cut) as ds:
            data = ds.read(1)
        assert not (data == _NODATA).any(), (
            f"ramka nodata: {(data == _NODATA).sum()} z {data.size} pikseli"
        )
        sent = find.call_args.args[0]
        assert sent.min_x < _BBOX_2180.min_x and sent.max_x > _BBOX_2180.max_x

    def test_cli_geometry_target_crs_reaches_worker(self, tmp_path):
        """Cala sciezka przez main(): dyspozycja MUSI podac obwiednie workerowi.

        Broni `bbox=part` w `_dispatch_area` — jedynej linii, dzieki ktorej
        wycinek geometry jest osiagalny z CLI: obwiednia wyznacza siatke
        i crop wycinka, a ``bbox`` jest w ``_download_pl_geometry`` argumentem
        WYMAGANYM. Bez tej linii worker nie dostaje obwiedni i wycinek nie
        powstaje (komenda konczy sie kodem 1).
        """
        from kartograf.download.manager import DownloadResult

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # tresc nieuzywana: discovery zamockowane
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        overall = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        manager = Mock()
        manager.download_sheets.return_value = sheets
        manager.last_result = DownloadResult()

        with (
            # oba importy lokalne (cli.download_cmd, download.cutout) ->
            # patch u zrodla
            patch("kartograf.core.geometry.get_overall_bbox", return_value=overall),
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1", "N-2"],
            ),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                [
                    "download",
                    "--geometry",
                    str(geom),
                    "--country",
                    "pl",
                    "--target-crs",
                    "EPSG:2180",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert rc == 0
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        assert target.exists()
        # parent_request powstaje WYLACZNIE w warstwie dyspozycji — dowod,
        # ze wycinek przyszedl przez `_dispatch_area`, a nie obok niej
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text("utf-8")
        )
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["nodata"] == _NODATA
        assert payload["extra"]["parent_request"]["countries"] == ["PL"]


class TestBorderTwoCutouts:
    """Spec 13.6 / 8(e): jedna komenda -> dwa wycinki w tym samym ukladzie."""

    # maly prostokat przecinajacy PROSTOKATNE obwiednie obu krajow
    # (CZ: 12.09..18.86E / 48.55..51.06N, PL: 14.07..24.20E / 49.00..54.90N)
    _BBOX = "18.80,49.70,18.801,49.7005"

    @pytest.fixture(autouse=True)
    def _isolate_cache(self, tmp_path, monkeypatch):
        """MetadataCache laduje w cwd — poza repo i katalogiem wyjsciowym."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

    def _cz_provider(self):
        """Stub CuzkDmrProvider: zapisuje plik i udaje operacje przypieta."""
        provider = Mock()
        provider.descriptor_key = "cz.cuzk.dmr4g"
        provider.resolution = "5m"
        provider.vertical_crs = "EVRF2007"
        provider.vertical_transform = None

        def fake_horizontal(target_crs):
            pinned = Mock()
            pinned.description = f"S-JTSK to ETRS89 (3) -> {target_crs}"
            pinned.accuracy_m = 0.5
            return pinned

        provider.horizontal_transform.side_effect = fake_horizontal

        def fake_bbox(bbox, target, **kw):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"II*\x00dane")
            return target

        provider.download_bbox.side_effect = fake_bbox
        return provider

    def test_two_cutouts_share_parent_request(self, tmp_path):
        from pyproj import CRS

        from kartograf.core.geometry import _transform_bbox
        from kartograf.download.manager import DownloadResult

        # jeden syntetyczny arkusz pokrywajacy polska czesc zadania
        b = _transform_bbox(
            18.80,
            49.70,
            18.801,
            49.7005,
            CRS.from_user_input("EPSG:4326"),
            "EPSG:2180",
        )
        sheet = _write_sheet_asc(
            tmp_path / "sheet.asc",
            b.min_x - 100,
            b.min_y - 100,
            size=60,
            pixel=5.0,
        )
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        manager = Mock()
        manager.download_sheets.return_value = [sheet]
        manager.last_result = DownloadResult()

        with (
            patch(
                "kartograf.providers.cuzk.create_dmr_provider",
                return_value=self._cz_provider(),
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                [
                    "download",
                    "--bbox",
                    self._BBOX,
                    "--bbox-crs",
                    "EPSG:4326",
                    "--resolution",
                    "5m",
                    "--target-crs",
                    "EPSG:2180",
                    "--vertical-crs",
                    "EVRF2007",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert rc == 0
        pl = list((tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox").glob("*.tif"))
        cz = list((tmp_path / "nmt" / "cz_dmr4g_evrf2007" / "bbox").glob("*.tif"))
        assert len(pl) == 1 and len(cz) == 1
        parents = []
        for f in (*pl, *cz):
            payload = json.loads((f.parent / f"{f.name}.meta.json").read_text("utf-8"))
            assert payload["horizontal_crs"] == "EPSG:2180"
            parents.append(payload["extra"]["parent_request"])
        assert parents[0] == parents[1]
        assert parents[0]["countries"] == ["CZ", "PL"]


class TestTargetCrsValidations:
    """Spec 6.3 przez main() — czytelne bledy, kod 1."""

    _BBOX = ["--bbox", "530010,382010,530190,382090", "--country", "pl"]

    def test_pl_godlo_rejected(self, tmp_path, capsys):
        rc = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    @pytest.mark.parametrize("product", ["nmpt", "orto", "laz"])
    def test_non_nmt_rejected(self, product, tmp_path, capsys):
        rc = main(
            [
                "download",
                *self._BBOX,
                "--product",
                product,
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "--product nmt" in capsys.readouterr().err

    def test_system_2000_rejected_with_remedy(self, tmp_path, capsys):
        rc = main(
            [
                "download",
                *self._BBOX,
                "--system",
                "2000",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "1992" in capsys.readouterr().err


class TestLibraryApi:
    """R3: wycinek PL jako API biblioteki (bez argparse)."""

    _SHEETS = {
        "N-34-130-D-d-2-3": (530000, 382000),
        "N-34-130-D-d-2-4": (530100, 382000),
    }

    def _provider(self):
        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.default_extension = ".asc"
        provider.calls = []

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            west, south = self._SHEETS[godlo]
            return _write_sheet_asc(path, west, south)

        provider.download = download
        return provider

    def test_download_pl_cutout_end_to_end_skip_and_force(self, tmp_path):
        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            first = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            second = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            third = download_pl_cutout(
                bbox, "EPSG:2180", output_dir=tmp_path, force=True
            )

        assert first.path.exists() and not first.skipped
        assert first.path.with_name(first.path.name + ".meta.json").exists()
        assert second.skipped and second.path == first.path
        assert not third.skipped
        assert sorted(provider.calls) == sorted(list(self._SHEETS) * 2)

    def test_rebuild_reuses_cached_sheets(self, tmp_path):
        """Brak wycinka, arkusze w cache: przebudowa BEZ pobierania (force=False).

        Arkusze dzialaja jako cache (``skip_existing = not force``) — skasowany
        albo nigdy niezbudowany wycinek nie moze kosztowac ponownego pobrania
        arkuszy, ktore juz leza w swoim segmencie.
        """
        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            first = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            first.path.unlink()  # wycinek znika, arkusze zostaja w segmencie
            rebuilt = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)

        assert sorted(provider.calls) == sorted(self._SHEETS)  # tylko 1. przebieg
        assert not rebuilt.skipped and rebuilt.path == first.path
        assert rebuilt.path.exists()
        assert len(rebuilt.sheet_paths) == len(self._SHEETS)

    def test_5m_request_follows_factory_vertical_rule(self, tmp_path):
        """Regula fabryki NMT (5m => EVRF2007): wycinek idzie za PROVIDEREM.

        ``download_pl_cutout`` podaje fabryce surowe parametry, a pion wycinka
        bierze z providera — z surowa flaga KRON86 wycinek 5m nie powstalby
        (5m istnieje wylacznie w EVRF2007).
        """
        from kartograf import download_pl_cutout

        provider = self._provider()
        # to, co zwraca prawdziwa fabryka dla 5m + KRON86 (korekta pionu)
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "5m"
        provider.descriptor_key = "pl.gugik.nmt_5m"

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            west, south = self._SHEETS[godlo]
            return _write_sheet_asc(path, west, south, size=40, pixel=5.0)

        provider.download = download
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.providers.pl.create_nmt_provider", return_value=provider
            ) as factory,
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            result = download_pl_cutout(
                bbox,
                "EPSG:2180",
                output_dir=tmp_path,
                resolution="5m",
                vertical_crs="KRON86",
            )

        factory.assert_called_once_with(vertical_crs="KRON86", resolution="5m")
        assert result.path.parent == tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox"
        assert result.path.exists()

    @pytest.mark.parametrize(
        ("attr", "value"), [("vertical_crs", "KRON86"), ("resolution", "5m")]
    )
    def test_run_rejects_provider_not_matching_cutout(self, tmp_path, attr, value):
        """Provider niezgodny z wycinkiem zatrulby wspolny cache arkuszy.

        Segment arkuszy i sidecar wycinka biora pion/rozdzielczosc z wycinka,
        a dane z providera: arkusze KRON86 (albo 5 m) trafilyby do segmentu
        ``pl_1992_1m_evrf2007`` i kolejne przebiegi EVRF2007 1m uzylyby ich
        ponownie bez ostrzezenia. Blad PRZED pobraniem i przed katalogami.
        """
        from kartograf.download.cutout import PlCutoutSheets, run_pl_cutout
        from kartograf.exceptions import ValidationError

        provider = self._provider()
        setattr(provider, attr, value)
        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        sheets = PlCutoutSheets(godla=tuple(self._SHEETS))

        with pytest.raises(ValidationError, match=value):
            run_pl_cutout(cut, sheets, provider=provider)

        assert provider.calls == []
        assert not (tmp_path / "nmt").exists()

    def test_public_exports(self):
        import kartograf

        for name in (
            "PlCutout",
            "PlCutoutResult",
            "PlCutoutSheets",
            "download_pl_cutout",
            "prepare_pl_cutout",
            "run_pl_cutout",
            "select_pl_cutout_sheets",
        ):
            assert name in kartograf.__all__ and hasattr(kartograf, name)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_crs": "EPSG:4326"},
            {"resolution": "2m"},
            {"resolution": "5m", "vertical_crs": "KRON86"},
            {"vertical_crs": "Bpv"},
        ],
    )
    def test_prepare_rejects_bad_params(self, tmp_path, kwargs):
        from kartograf.download.cutout import prepare_pl_cutout
        from kartograf.exceptions import ValidationError

        params = {"target_crs": "EPSG:2180", **kwargs}
        target = params.pop("target_crs")
        with pytest.raises(ValidationError):
            prepare_pl_cutout(_BBOX_2180, target, output_dir=tmp_path, **params)
