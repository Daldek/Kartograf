"""Testy twardej polityki transformacji (kartograf.transform.crs)."""

import math
from unittest.mock import MagicMock, patch

import pytest

from kartograf.exceptions import KartografError
from kartograf.transform.crs import (
    KNOWN_PATHS,
    REMEDIES,
    TransformError,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_GROUP_PATCH = "kartograf.transform.crs.TransformerGroup"


def _mock_transformer(accuracy, description, result=(100.0, 200.0)):
    t = MagicMock()
    t.accuracy = accuracy
    t.description = description
    t.transform.return_value = result
    return t


def _mock_group(transformers):
    g = MagicMock()
    g.transformers = transformers
    g.unavailable_operations = []
    return g


class TestErrorHierarchy:
    def test_transform_errors_under_kartograf_error(self):
        assert issubclass(TransformError, KartografError)
        assert issubclass(TransformUnavailableError, TransformError)


class TestBuildPinnedTransform:
    def test_ballpark_disabled_in_group_construction(self):
        """(a) Grupa budowana wylacznie z allow_ballpark=False, always_xy=True."""
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([_mock_transformer(0.5, "op dokladna")])
            build_pinned_transform("EPSG:5514", "EPSG:2180", TransformPolicy())
        _, kwargs = mock_cls.call_args
        assert kwargs["allow_ballpark"] is False
        assert kwargs["always_xy"] is True

    def test_empty_group_raises_with_remedy(self):
        """(b) Pusta lista operacji => TransformUnavailableError z remedium."""
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([])
            with pytest.raises(TransformUnavailableError) as exc:
                build_pinned_transform("EPSG:8357", "EPSG:9651", TransformPolicy())
        assert exc.value.remedy is not None
        assert "pl07_2019" in exc.value.remedy

    def test_accuracy_filter(self):
        """(c) Odrzuc accuracy < 0 (nieznana) i > min_accuracy_m; 0.0 akceptowane."""
        good = _mock_transformer(0.0, "dokladna konwersja")
        unknown = _mock_transformer(-1.0, "nieznana dokladnosc")
        coarse = _mock_transformer(7.0, "za gruba")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([coarse, unknown, good])
            pinned = build_pinned_transform(
                "EPSG:25833", "EPSG:2180", TransformPolicy(min_accuracy_m=1.0)
            )
        assert pinned.accuracy_m == 0.0
        assert pinned.description == "dokladna konwersja"

    def test_probe_rejects_inf(self):
        """(d) Probe: operacja zwracajaca inf na punkcie kontrolnym odpada."""
        bad_grid = _mock_transformer(
            0.03, "siatka obcego kraju", result=(math.inf, math.inf)
        )
        ok_op = _mock_transformer(0.5, "operacja bez siatek")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([bad_grid, ok_op])
            pinned = build_pinned_transform(
                "EPSG:5514",
                "EPSG:2180",
                TransformPolicy(probe_point=(-598000.0, -1160000.0)),
            )
        assert pinned.description == "operacja bez siatek"

    def test_all_rejected_lists_reasons(self):
        unknown = _mock_transformer(-1.0, "op A")
        coarse = _mock_transformer(9.9, "op B")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([unknown, coarse])
            with pytest.raises(TransformUnavailableError) as exc:
                build_pinned_transform(
                    "EPSG:4258", "EPSG:2180", TransformPolicy(min_accuracy_m=1.0)
                )
        reasons = dict(exc.value.rejected)
        assert "op A" in reasons and "op B" in reasons

    def test_result_isfinite_guard(self):
        """(e) Wynik nieskonczony => TransformError, nie dane."""
        flaky = _mock_transformer(0.5, "psuje sie po zbudowaniu")
        with patch(_GROUP_PATCH) as mock_cls:
            mock_cls.return_value = _mock_group([flaky])
            pinned = build_pinned_transform("EPSG:5514", "EPSG:2180", TransformPolicy())
        flaky.transform.return_value = (math.inf, 5.0)
        with pytest.raises(TransformError):
            pinned.transform(1.0, 2.0)

    def test_25833_to_2180_end_to_end_offline(self):
        """(f) Realna para DE->PL: bez siatek, dziala offline, acc 0.0."""
        policy = TransformPolicy(probe_point=(400000.0, 5800000.0))
        pinned = build_pinned_transform("EPSG:25833", "EPSG:2180", policy)
        assert pinned.accuracy_m == 0.0
        x, y = pinned.transform(400000.0, 5800000.0)
        assert x == pytest.approx(127742.88, abs=0.1)
        assert y == pytest.approx(511326.23, abs=0.1)


class TestKnownPaths:
    def test_documented_pairs_present(self):
        pairs = {(p.src, p.dst) for p in KNOWN_PATHS}
        assert ("EPSG:5514", "EPSG:2180") in pairs
        assert ("EPSG:8353", "EPSG:2180") in pairs
        assert ("EPSG:25833", "EPSG:2180") in pairs
        assert ("EPSG:8357", "EPSG:5621") in pairs
        assert ("EPSG:7837", "EPSG:5621") in pairs
        assert ("EPSG:4937", "EPSG:8357") in pairs

    def test_remedies_for_polish_vertical(self):
        assert "EPSG:9650" in REMEDIES and "EPSG:9651" in REMEDIES
