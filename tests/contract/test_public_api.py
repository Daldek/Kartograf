"""A5: transport and mosaic helpers are part of the stable public API;
the download and check functions take their arguments by name."""

import inspect

import pytest

import kartograf

# Modules of the data and project tracks (``check_source_grid`` is a mosaic
# helper, not a check of a download).
_TRACK_MODULES = (
    "kartograf.download.",
    "kartograf.landcover.",
    "kartograf.hydrology.",
    "kartograf.project.",
)


def _download_and_check_functions() -> list[str]:
    return sorted(
        name
        for name in kartograf.__all__
        if name.startswith(("download_", "check_", "calculate_"))
        and getattr(kartograf, name).__module__.startswith(_TRACK_MODULES)
    )


@pytest.mark.parametrize("name", _download_and_check_functions())
def test_download_and_check_functions_are_keyword_only(name):
    """Every download/check function of ``kartograf.__all__`` takes its
    selection by name, as ``download_data`` (``download_pl_cutout(bbox, ...)``
    is a ``TypeError``); a project function keeps only the project directory
    positional - the handle shared by all project functions."""
    params = inspect.signature(getattr(kartograf, name)).parameters.values()
    positional = [p.name for p in params if p.kind is not p.KEYWORD_ONLY]
    expected = ["project_dir"] if name.endswith("_project") else []
    assert positional == expected


# Functions that return a document (spec 5.5): all arguments by name, except the
# one that identifies the object, which is positional like ``read_sidecar(path)``.
_DOCUMENT_FUNCTIONS = {
    "list_sources": [],
    "list_layers": [],
    "get_cache_info": [],
    "get_cache_path": [],
    "clear_cache": [],
    "describe_store": ["output_dir"],
    "list_store_entries": ["output_dir"],
    "read_store_sidecar": ["path"],
    "describe_sheet": ["sheet"],
    "find_sheets": [],
    "get_catalog": [],
}


@pytest.mark.parametrize(("name", "expected"), sorted(_DOCUMENT_FUNCTIONS.items()))
def test_document_functions_are_keyword_only(name, expected):
    """The new document functions take their selection by name; only the
    object that is read is positional."""
    assert name in kartograf.__all__
    params = inspect.signature(getattr(kartograf, name)).parameters.values()
    assert [p.name for p in params if p.kind is not p.KEYWORD_ONLY] == expected


# The command layer (KB-2..KB-5): what names the command - the line, or the command
# and its options - is positional; everything else is by name.
_COMMAND_FUNCTIONS = {
    "parse_command": ["argv"],
    "validate_command": ["command", "options"],
    "format_command": ["command", "options"],
    "run_command": ["command", "options"],
    "check_command": ["command", "options"],
}


@pytest.mark.parametrize(("name", "expected"), sorted(_COMMAND_FUNCTIONS.items()))
def test_command_functions_take_only_the_command_positionally(name, expected):
    assert name in kartograf.__all__
    params = inspect.signature(getattr(kartograf, name)).parameters.values()
    assert [p.name for p in params if p.kind is not p.KEYWORD_ONLY] == expected


def test_command_call_is_exported():
    """``parse_command`` returns it, ``format_command`` and ``run_command`` take its
    parts: a caller needs the type by name."""
    assert "CommandCall" in kartograf.__all__
    assert isinstance(
        kartograf.parse_command("elevation download --product nmt"),
        kartograf.CommandCall,
    )


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


def test_store_read_api_exported():
    """The store reader of ADR-045 (Archiwista) is available from kartograf."""
    from kartograf.exceptions import InvalidSidecarError
    from kartograf.store import (
        SegmentInfo,
        Sidecar,
        StoreEntry,
        describe_segment,
        iter_store,
        link_target,
        list_partitions,
        list_segments,
        read_sidecar,
    )
    from kartograf.store_geometry import Footprint, file_footprint, pinned_transform
    from kartograf.transform.crs import PinnedTransform

    expected = {
        "list_segments": list_segments,
        "list_partitions": list_partitions,
        "iter_store": iter_store,
        "StoreEntry": StoreEntry,
        "read_sidecar": read_sidecar,
        "Sidecar": Sidecar,
        "InvalidSidecarError": InvalidSidecarError,
        "describe_segment": describe_segment,
        "SegmentInfo": SegmentInfo,
        "file_footprint": file_footprint,
        "Footprint": Footprint,
        "link_target": link_target,
        "pinned_transform": pinned_transform,
        "PinnedTransform": PinnedTransform,
    }
    for name, value in expected.items():
        assert name in kartograf.__all__
        assert getattr(kartograf, name) is value


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
