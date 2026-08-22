"""
Pytest configuration and shared fixtures.

This module contains pytest fixtures and configuration that are shared
across all test modules.
"""

import ipaddress
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# Network isolation
# =============================================================================


def _is_local_address(address: object) -> bool:
    """
    Tell whether a socket address points at the local machine.

    Non-tuple addresses (AF_UNIX paths, bytes) never leave the machine,
    so they are treated as local.

    Parameters
    ----------
    address : object
        Address passed to ``socket.socket.connect``.

    Returns
    -------
    bool
        True if the address is loopback/unspecified or a non-IP socket.
    """
    if not isinstance(address, tuple) or not address:
        return True

    host = address[0]
    if isinstance(host, bytes | bytearray):
        host = bytes(host).decode("ascii", errors="ignore")
    if not isinstance(host, str):
        return False
    if host in ("localhost", "localhost.localdomain", ""):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_unspecified


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """
    Fail any test that opens a non-loopback socket.

    Unit tests must run offline: a test that reaches a production server
    (GUGiK, CUZK, ISRIC, ...) is slow, flaky and its result depends on the
    state of that server. Tests marked ``live`` are exempt.

    Loopback connections are allowed on purpose — some tests spin up a real
    ``HTTPServer`` on 127.0.0.1 (see ``tests/test_auth_proxy.py``).

    The guard raises ``RuntimeError``, not ``OSError``: ``requests`` wraps
    ``OSError`` into ``ConnectionError``, which production fallbacks catch,
    so the offending call would stay invisible.
    """
    if request.node.get_closest_marker("live"):
        yield
        return

    real_connect = socket.socket.connect
    nodeid = request.node.nodeid

    def guarded_connect(self, address):
        if _is_local_address(address):
            return real_connect(self, address)
        raise RuntimeError(
            f"Network access blocked in unit tests ({nodeid}): connect to {address!r}"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield


# =============================================================================
# Offline WMS GetCapabilities
# =============================================================================


def _nmt_endpoint_layers() -> dict[str, list[str]]:
    """
    Map every NMT/NMPT skorowidze endpoint to its hardcoded layer list.

    Returns
    -------
    dict[str, list[str]]
        WMS endpoint URL -> layers declared in ``WMS_LAYERS`` for the
        (resolution, vertical CRS) pair that endpoint serves.
    """
    from kartograf.providers.pl.gugik import GugikProvider
    from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

    mapping: dict[str, list[str]] = {}
    for provider_cls in (GugikProvider, GugikNmptProvider):
        for (
            resolution,
            per_vertical_crs,
        ) in provider_cls.WMS_SKOROWIDZE_ENDPOINTS.items():
            for vertical_crs, endpoint in per_vertical_crs.items():
                layers = provider_cls.WMS_LAYERS.get(resolution, {}).get(
                    vertical_crs, []
                )
                if layers:
                    mapping[endpoint] = list(layers)
    return mapping


@pytest.fixture(autouse=True)
def _offline_wms_layers(request):
    """
    Serve WMS GetCapabilities from the hardcoded layer lists, offline.

    ``_get_validated_layers`` calls ``_fetch_wms_layers``, which opens its own
    ``requests.Session`` — a session injected into the provider does not
    intercept it, so unit tests used to query the live GUGiK service. The stub
    returns exactly the hardcoded layers, so validation reports a clean match
    (no warning) and no test result depends on what GUGiK publishes today.

    Two policies, because the signatures differ: ``GugikProvider`` takes the
    endpoint (``side_effect``, dispatching on it), ``GugikOrtoProvider`` has a
    single flat endpoint (``return_value``). ``patch.object`` without
    ``autospec`` installs a ``MagicMock``, which is not a descriptor, so
    ``self`` never reaches the ``side_effect`` — hence the endpoint-only
    lambda signature.

    Opt out with ``@pytest.mark.real_wms_layers`` in tests that exercise
    ``_fetch_wms_layers`` itself.
    """
    if request.node.get_closest_marker("real_wms_layers"):
        yield
        return

    from kartograf.providers.pl.gugik import GugikProvider
    from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

    endpoint_layers = _nmt_endpoint_layers()

    def fake_fetch(endpoint, timeout=10):
        layers = endpoint_layers.get(endpoint)
        if layers is None:
            # AssertionError on purpose: _get_validated_layers swallows
            # ValueError/RequestException, so those would hide the gap.
            raise AssertionError(
                f"No offline GetCapabilities stub for WMS endpoint {endpoint!r}. "
                f"Add it to tests/conftest.py::_nmt_endpoint_layers."
            )
        return list(layers)

    with (
        patch.object(GugikProvider, "_fetch_wms_layers", side_effect=fake_fetch),
        patch.object(
            GugikOrtoProvider,
            "_fetch_wms_layers",
            return_value=list(GugikOrtoProvider.WMS_LAYERS),
        ),
    ):
        yield


# =============================================================================
# Shared data fixtures
# =============================================================================


@pytest.fixture
def sample_godlos() -> dict:
    """
    Provide sample godlo identifiers for each scale.

    Returns
    -------
    dict
        Dictionary mapping scale names to sample godlo identifiers
    """
    return {
        "1:1000000": "N-34",
        "1:500000": "N-34-A",
        "1:200000": "N-34-130",
        "1:100000": "N-34-130-D",
        "1:50000": "N-34-130-D-d",
        "1:25000": "N-34-130-D-d-2",
        "1:10000": "N-34-130-D-d-2-4",
    }


@pytest.fixture
def test_data_dir(tmp_path) -> Path:
    """
    Create a temporary test data directory.

    Returns
    -------
    Path
        Path to the temporary test data directory
    """
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_tif_data() -> bytes:
    """
    Provide mock TIFF data for testing downloads.

    Returns
    -------
    bytes
        Mock TIFF file content (minimal valid header)
    """
    # Minimal TIFF header (little-endian, 42 magic number)
    return b"II*\x00\x08\x00\x00\x00" + b"\x00" * 100
