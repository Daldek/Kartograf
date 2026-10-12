"""
Pytest configuration and shared fixtures.

This module contains pytest fixtures and configuration that are shared
across all test modules.
"""

import ipaddress
import json
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


_STUB_LAYERS = {
    "NMT/WMS/SkorowidzeUkladKRON86": [
        "SkorowidzeNMT2019",
        "SkorowidzeNMT2018",
        "SkorowidzeNMT2017iStarsze",
    ],
    "NMT/WMS/SkorowidzeUkladEVRF2007": [
        "SkorowidzeNMT2026",
        "SkorowidzeNMT2025",
        "SkorowidzeNMT2024",
        "SkorowidzeNMT2023iStarsze",
    ],
    "NMT/WMS/SheetsGrid5mEVRF2007": [
        "SkorowidzeNMT2025",
        "SkorowidzeNMT2024",
        "SkorowidzeNMT2023",
        "SkorowidzeNMT2022iStarsze",
    ],
    "NMPT/WMS/SkorowidzeUkladKRON86": [
        "SkorowidzeNMPT2019",
        "SkorowidzeNMPT2018",
        "SkorowidzeNMPT2017iStarsze",
    ],
    "NMPT/WMS/SkorowidzeUkladEVRF2007": [
        "SkorowidzeNMPT2026",
        "SkorowidzeNMPT2025",
        "SkorowidzeNMPT2024",
        "SkorowidzeNMPT2023iStarsze",
    ],
}


@pytest.fixture(autouse=True)
def _offline_wms_layers(request):
    """A GetCapabilities stub without network, independent of production configuration.

    Layer discovery tests use the ``real_wms_layers`` marker.
    """
    if request.node.get_closest_marker("real_wms_layers"):
        yield
        return

    from kartograf.providers.pl.gugik import GugikProvider
    from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

    endpoint_layers = {
        f"https://mapy.geoportal.gov.pl/wss/service/PZGIK/{path}": layers
        for path, layers in _STUB_LAYERS.items()
    }

    def fake_fetch(endpoint, timeout=None):
        layers = endpoint_layers.get(endpoint)
        if layers is None:
            # Do not turn a missing stub into a service error.
            raise AssertionError(
                f"No offline GetCapabilities stub for WMS endpoint {endpoint!r}. "
                f"Add it to tests/conftest.py::_STUB_LAYERS."
            )
        return list(layers)

    with (
        patch.object(GugikProvider, "_fetch_wms_layers", side_effect=fake_fetch),
        patch.object(
            GugikOrtoProvider,
            "_fetch_wms_layers",
            return_value=[
                "SkorowidzeOrtofotomapy2026",
                "SkorowidzeOrtofotomapy2025",
                "SkorowidzeOrtofotomapy2024",
                "SkorowidzeOrtofotomapyStarsze",
            ],
        ),
    ):
        yield


# =============================================================================
# Shared data fixtures
# =============================================================================


def render_gfi_body(records: list[dict], var: str = "skor_NMT_wg_akt") -> str:
    """Render a MapServer template like GUGiK: an empty response has only the header
    with ``createTable`` (gfi/01), the array declaration appears with records."""
    header = "<script>function createTable (rows) { return rows; }</script>\n"
    if not records:
        return header
    pushes = [
        f"{var}.push({{"
        + ",".join(
            f"{key}:{json.dumps(value, ensure_ascii=False)}"
            for key, value in record.items()
        )
        + "});"
        for record in records
    ]
    return header + f"<script>var {var} = [];\n" + "\n".join(pushes) + "</script>"


def gfi_record(
    sheet: str,
    *,
    resolution: str = "1.00 m",
    system: str = "PL-1992",
    aktualnosc: str = "2024-09-03",
    url: str | None = None,
    **fields: str,
) -> dict:
    """NMT/NMPT index record with fields as in the GUGiK response (2026-09-29)."""
    record = {
        "url": url
        or f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{sheet}.asc",
        "godlo": sheet,
        "aktualnosc": aktualnosc,
        "format": "ARC/INFO ASCII GRID",
        "charakterystykaPrzestrzenna": resolution,
        "ukladWspolrzednychPoziomych": system,
        "ukladWspolrzednychPionowych": "PL-EVRF2007-NH",
        "calyArkuszWypelnionyTrescia": "TAK",
        "aktualnoscRok": aktualnosc[:4],
        "dt_pzgik": aktualnosc,
    }
    record.update(fields)
    return record


def write_gpkg_layers(path: Path, layers: list[str]) -> Path:
    """GeoPackage catalogue with the given feature tables and no features.

    Enough for ``core.geometry.resolve_layer`` (the CLI resolves the layer before
    the readers) in CLI tests that mock the geometry readers themselves.
    """
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
        conn.executemany(
            "INSERT INTO gpkg_contents VALUES (?, 'features')",
            [(name,) for name in layers],
        )
        conn.commit()
    finally:
        conn.close()
    return path


WCS_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_wcs" / "real_2026_10_11"


def recorded_response(path: Path, body: bytes | None = None):
    """Mock ``requests.Response`` replaying a recorded body and its headers.

    ``<file>.headers.json`` next to the body holds the HTTP status and
    ``Content-Type`` (fixture README); ``body`` overrides the recorded bytes.
    ``iter_content`` yields small blocks, so streaming readers see several.
    """
    from unittest.mock import Mock

    import requests

    meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
    content = path.read_bytes() if body is None else body
    response = Mock()
    response.status_code = meta["status"]
    response.headers = {"Content-Type": meta["Content-Type"]}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    response.iter_content = lambda chunk_size=1: (
        content[i : i + 1000] for i in range(0, len(content), 1000)
    )
    if meta["status"] >= 400:
        error = requests.HTTPError(f"{meta['status']} Error", response=response)
        response.raise_for_status.side_effect = error
    return response


def multipart_asc_body(values, xll: float, yll: float, cellsize: float = 1.0) -> bytes:
    """A GUGiK-shaped ``multipart/related; boundary=wcs`` body with one ASC grid.

    Same framing as the recorded responses (fixture README): CRLF part headers,
    LF ASC lines, an ``.prj`` part after the grid.
    """
    rows, cols = values.shape
    header = (
        f"ncols        {cols}\nnrows        {rows}\n"
        f"xllcorner    {xll:.12f}\nyllcorner    {yll:.12f}\n"
        f"cellsize     {cellsize:.12f}\n"
    )
    grid = "\n".join(" " + " ".join(repr(float(v)) for v in row) for row in values)
    part = b"\r\n--wcs\r\nContent-Type: %s\r\nContent-ID: coverage/%s\r\n\r\n"
    return (
        part % (b"image/x-aaigrid", b"result.asc")
        + (header + grid + "\n").encode()
        + part % (b"application/octet-stream", b"result.prj")
        + b'PROJCS["ETRS89_Poland_CS92"]'
        + b"\r\n--wcs--\r\n"
    )


@pytest.fixture
def sample_sheets() -> dict:
    """
    Provide sample sheet identifiers for each scale.

    Returns
    -------
    dict
        Dictionary mapping scale names to sample sheet identifiers
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
