"""A5: transport and mosaic helpers are part of the stable public API."""

import kartograf


def test_transport_and_mosaic_exported():
    from kartograf.transport.http import get_with_retry, make_gugik_session
    from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

    assert kartograf.get_with_retry is get_with_retry
    assert kartograf.make_gugik_session is make_gugik_session
    assert kartograf.mosaic_and_crop is mosaic_and_crop
    assert kartograf.check_source_grid is check_source_grid
    for name in (
        "get_with_retry",
        "make_gugik_session",
        "mosaic_and_crop",
        "check_source_grid",
        "CacheError",
    ):
        assert name in kartograf.__all__


def test_get_with_retry_any_ogc_url_with_params():
    """Any service URL; params sent unchanged on every attempt."""
    from unittest.mock import Mock

    response = Mock(status_code=200)
    response.raise_for_status = Mock()
    session = Mock()
    session.get.return_value = response
    out = kartograf.get_with_retry(
        session,
        "https://example.org/wfs",
        timeout=5,
        params={"SERVICE": "WFS", "REQUEST": "GetCapabilities"},
    )
    assert out is response
    session.get.assert_called_once_with(
        "https://example.org/wfs",
        timeout=5,
        params={"SERVICE": "WFS", "REQUEST": "GetCapabilities"},
    )
