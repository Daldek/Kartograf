"""
CORINE Land Cover provider for downloading land cover data.

This module provides the CorineProvider class for downloading
CORINE Land Cover data from multiple sources:

1. CLMS API (primary) - Raw GeoTIFF with class codes (requires OAuth2 credentials)
2. EEA Discomap WMS (fallback) - Styled images for preview
3. DLR WMS (fallback for 1990) - Styled images

CORINE Land Cover is a pan-European land cover inventory with 44
thematic classes, available for years: 2018, 2012, 2006, 2000, 1990.

Data sources:
- CLMS API: https://land.copernicus.eu (requires registration)
- EEA WMS: https://image.discomap.eea.europa.eu
- DLR WMS: https://geoservice.dlr.de/eoc/land/wms

Authentication modes:
1. Auth Proxy (default, secure) - credentials isolated in subprocess
2. Direct mode - credentials passed explicitly (for testing)

To configure credentials:
1. Register at https://land.copernicus.eu
2. Generate API credentials (JSON with client_id, private_key, token_uri,
   optionally user_id)
3. Either set CLMS_CREDENTIALS as a JSON string in the environment
   (read by the kartograf.auth.proxy subprocess), or pass
   ``CorineProvider(clms_credentials={...})`` explicitly from library code.

The auth proxy isolates credentials in a separate subprocess, keeping
them out of the main application process.
"""

import json
import logging
import os
import time
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.base import LandCoverProvider
from kartograf.sources.edition import Edition, edition_label
from kartograf.transform.bbox import envelope_from_2180
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
    get_with_retry,
    reject_error_document,
)

logger = logging.getLogger(__name__)

_WMS = "{http://www.opengis.net/wms}"


def _raster_layer_name(content: bytes, year: int, *, what: str) -> str:
    """The name of the raster layer of the CLC ``year`` in a WMS 1.3.0
    GetCapabilities of the EEA service of that year.

    The layer is found by its title ``Corine Land Cover <year> raster``: its
    NAME differs per year (``12`` in CLC2018, ``Corine_Land_Cover_2012_raster59601``
    in CLC2012 - a number that changes when EEA republishes the service).

    Raises
    ------
    DownloadError
        Not XML, or no named layer with that title (the message lists the
        named layers).
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise DownloadError(f"{what}: GetCapabilities nie jest XML: {e}") from e
    wanted = f"Corine Land Cover {year} raster".lower()
    named: list[str] = []
    for layer in root.iter(f"{_WMS}Layer"):
        name = (layer.findtext(f"{_WMS}Name") or "").strip()
        if not name:
            continue
        named.append(name)
        if (layer.findtext(f"{_WMS}Title") or "").strip().lower() == wanted:
            return name
    raise DownloadError(
        f"{what}: usluga WMS EEA nie ma warstwy rastrowej 'Corine Land Cover "
        f"{year} raster' (warstwy: {', '.join(named) or 'brak'}); podglad "
        "tego roku jest niedostepny - zmien --year albo ustaw CLMS_CREDENTIALS"
    )


def _is_blank(path: Path) -> bool:
    """Whether the preview image at ``path`` has no visible pixel: every pixel
    transparent (alpha 0, or the transparent colour of a palette) - the WMS
    answered an area without data. An unreadable file is not blank (it is the
    answer as it came, never rejected on a guess)."""
    import rasterio
    from rasterio.errors import NotGeoreferencedWarning, RasterioError

    try:
        with warnings.catch_warnings():
            # a PNG has no georeference: not a problem of a preview
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(path) as image:
                for _, window in image.block_windows(1):
                    if image.dataset_mask(window=window).any():
                        return False
                return True
    except (OSError, ValueError, RasterioError) as e:
        logger.debug("CORINE preview %s unreadable: %s", path, e)
        return False


# Lazy import to avoid circular dependency
_auth_proxy_client = None


def _get_auth_proxy():
    """Get singleton AuthProxyClient instance."""
    global _auth_proxy_client
    if _auth_proxy_client is None:
        from kartograf.auth import AuthProxyClient

        _auth_proxy_client = AuthProxyClient()
    return _auth_proxy_client


class CLMSAuth:
    """
    CLMS OAuth2 authentication handler.

    Uses RSA private key to generate JWT and exchange for access token.
    """

    def __init__(self, credentials: dict):
        """
        Initialize CLMS auth handler.

        Parameters
        ----------
        credentials : dict
            OAuth2 credentials with client_id, private_key, token_uri
        """
        self.client_id = credentials.get("client_id")
        self.private_key = credentials.get("private_key")
        self.token_uri = credentials.get("token_uri")
        self.key_id = credentials.get("key_id")
        self.user_id = credentials.get("user_id")

        self._access_token: str | None = None
        self._token_expires: float = 0

    def get_access_token(self, session: requests.Session | None = None) -> str:
        """
        Get valid access token, refreshing if necessary.

        Returns
        -------
        str
            Valid access token for API calls.

        Raises
        ------
        DownloadError
            If token exchange fails.
        """
        # Return cached token if still valid (with 60s buffer)
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        # Generate new token
        self._access_token = self._exchange_token(session)
        # Tokens typically valid for 1 hour
        self._token_expires = time.time() + 3600

        return self._access_token

    def _exchange_token(self, session: requests.Session | None = None) -> str:
        """Exchange JWT assertion for access token."""
        import jwt

        # Create JWT assertion
        now = int(time.time())
        payload = {
            "iss": self.client_id,
            "sub": self.user_id or self.client_id,
            "aud": self.token_uri,
            "iat": now,
            "exp": now + 300,  # 5 min validity for assertion
        }

        headers = {}
        if self.key_id:
            headers["kid"] = self.key_id

        if not self.private_key:
            raise DownloadError("Nie udalo sie utworzyc asercji JWT: brak private_key")

        try:
            assertion = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers=headers if headers else None,
            )
        except Exception as e:
            raise DownloadError(f"Nie udalo sie utworzyc asercji JWT: {e}") from e

        # Exchange for access token
        sess = session or requests.Session()
        try:
            response = sess.post(
                self.token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            access_token = result.get("access_token")
            if not access_token:
                raise DownloadError(f"Brak access_token w odpowiedzi: {result}")

            logger.info("CLMS access token obtained successfully")
            return access_token

        except requests.RequestException as e:
            raise DownloadError(f"Wymiana tokenu nie powiodla sie: {e}") from e


class CorineProvider(LandCoverProvider):
    """
    Provider for downloading CORINE Land Cover data.

    CORINE (Coordination of Information on the Environment) Land Cover
    is a standardized European land cover classification system with
    44 classes. Data is available at 100m resolution.

    Supports multiple download modes:
    - CLMS API: GeoTIFF with raw class codes (requires token)
    - WMS: Styled images for preview (no token needed)

    Available years: 2018, 2012, 2006, 2000, 1990

    Examples
    --------
    >>> # Preview mode (WMS - styled images)
    >>> provider = CorineProvider()
    >>> provider.download_by_sheet("N-34-130-D", Path("./preview.png"), year=2018)
    >>>
    >>> # Data mode (CLMS API - raw class codes, with CLMS_CREDENTIALS configured)
    >>> provider = CorineProvider()
    >>> provider.download_by_bbox(bbox, Path("./data.tif"), year=2018)
    """

    # =========================================================================
    # CLMS API Configuration (primary - raw data with class codes)
    # =========================================================================
    CLMS_API_BASE = "https://land.copernicus.eu/api"

    # Dataset UIDs and RASTER download ids of the CLMS catalogue (checked
    # 2026-10-12, docs/research/2026-10-12-plan3-spec-check/raport.md)
    CLMS_DATASET_UIDS = {
        2018: "0407d497d3c44bcd93ce8fd5bf78596a",
        2012: "a5ee71470be04d66bcff498f94ceb5dc",
        2006: "d443c86fec2f49e08ff12c7decdbf2af",
        2000: "6704f90ca82e4f228a46111519f8978e",
    }

    # Download information IDs for raster data
    CLMS_RASTER_DOWNLOAD_IDS = {
        2018: "7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb",
        2012: "b1027c88-6256-435b-98a3-62f019cbb381",
        2006: "4841f8cb-6e7c-4227-bb35-cd787609c546",
        2000: "19d7fbd8-53ee-4d09-89b6-fe5231247763",
    }

    # =========================================================================
    # WMS Configuration (fallback - styled preview images)
    # =========================================================================
    EEA_WMS_BASE = "https://image.discomap.eea.europa.eu/arcgis/services/Corine"
    DLR_WMS_ENDPOINT = "https://geoservice.dlr.de/eoc/land/wms"

    # Available years
    AVAILABLE_YEARS = [2018, 2012, 2006, 2000, 1990]
    EEA_YEARS = [2018, 2012, 2006, 2000]
    CLMS_YEARS = [2018, 2012, 2006, 2000]  # Years with CLMS API support

    # DLR layer of the 1990 preview (the EEA raster layer of a year is read from
    # the GetCapabilities of its service: ``_eea_raster_layer``)
    DLR_WMS_LAYERS = {
        1990: "CORINE_LAND_COVER_1990_100x100_ETRS89",
    }

    # Default settings
    DEFAULT_TIMEOUT = 60
    CLMS_POLL_INTERVAL = 10  # seconds between status checks
    CLMS_MAX_WAIT = 600  # max seconds to wait for CLMS download
    MAX_RETRIES = MAX_RETRIES

    # Output format settings
    WMS_FORMAT = "image/png"
    WMS_RESOLUTION = 100  # meters per pixel

    def __init__(
        self,
        session: requests.Session | None = None,
        clms_credentials: dict[str, Any] | None = None,
        use_proxy: bool = True,
    ):
        """
        Initialize CORINE provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        clms_credentials : dict, optional
            CLMS OAuth2 credentials dict with client_id, private_key, token_uri.
            If provided, disables proxy mode and uses direct authentication.
            For security, prefer using the auth proxy (credentials in Keychain).
        use_proxy : bool, optional
            Use auth proxy for CLMS authentication (default: True).
            The proxy isolates credentials in a separate subprocess.
            Set to False to use direct mode (requires clms_credentials).
        """
        self._sessions = SessionPerThread(session, factory=requests.Session)
        self._use_proxy = use_proxy and clms_credentials is None
        self._clms_auth: CLMSAuth | None = None
        # EEA raster layer name per year (GetCapabilities read once per provider)
        self._wms_layers: dict[int, str] = {}

        # Direct mode: use provided credentials
        if (
            clms_credentials
            and clms_credentials.get("client_id")
            and clms_credentials.get("private_key")
        ):
            self._use_proxy = False
            try:
                self._clms_auth = CLMSAuth(clms_credentials)
                logger.info("CLMS OAuth2 authentication configured (direct mode)")
            except Exception as e:
                logger.debug("Failed to initialize CLMS auth: %s", e)

        self.descriptor_key = "eu.clms.corine"

    @property
    def has_clms_token(self) -> bool:
        """Return True if CLMS OAuth2 authentication is available."""
        if self._clms_auth is not None:
            return True
        if self._use_proxy:
            try:
                proxy = _get_auth_proxy()
                return proxy.is_available()
            except Exception:
                return False
        return False

    @property
    def name(self) -> str:
        """Return provider name."""
        return "CORINE Land Cover"

    @property
    def base_url(self) -> str:
        """Return source URL."""
        return "https://land.copernicus.eu/en/products/corine-land-cover"

    def uses_clms(self, year: int) -> bool:
        """True when ``year`` is downloaded as CLMS data (else a WMS preview)."""
        return year in self.CLMS_YEARS and self.has_clms_token

    @property
    def clms_credentials_problem(self) -> str | None:
        """Why ``CLMS_CREDENTIALS`` of the environment cannot be used (a text
        of the auth proxy - the one process that reads it), else ``None``:
        the variable is not set, credentials were given to the provider or
        the proxy is not used."""
        if (
            self._clms_auth is not None
            or not self._use_proxy
            or not os.environ.get("CLMS_CREDENTIALS")
        ):
            return None
        try:
            return _get_auth_proxy().credentials_problem()
        except Exception as e:  # the proxy is best effort here
            logger.debug("CLMS credentials check failed: %s", e)
            return None

    @classmethod
    def check_year(cls, year: int) -> None:
        """``ValidationError`` unless ``year`` is a CORINE edition (``--year``)."""
        if year not in cls.AVAILABLE_YEARS:
            raise ValidationError(
                f"--year {year}: niedostepne dla --product corine; dostepne: "
                f"{', '.join(str(y) for y in cls.AVAILABLE_YEARS)}",
                option="year",
                allowed=tuple(str(y) for y in cls.AVAILABLE_YEARS),
            )

    def edition(self, year: int, timeout: int = DEFAULT_TIMEOUT) -> Edition:
        """CORINE edition of ``year`` from the public CLMS catalogue (D29).

        ``GET {CLMS_API_BASE}/@search?UID=<uid>&fullobjects=1`` without a
        token; the single dataset record's
        ``characteristics_release_major_version`` (e.g. ``V2020_20u1``) is
        the version label.

        Raises
        ------
        ValidationError
            ``year`` has no CLMS dataset (preview-only years).
        DownloadError
            HTTP failure, not exactly one record or no release field.
        """
        uid = self.CLMS_DATASET_UIDS.get(year)
        if uid is None:
            raise ValidationError(
                f"CORINE {year}: brak zbioru CLMS (lata: {sorted(self.CLMS_YEARS)})"
            )
        url = f"{self.CLMS_API_BASE}/@search?UID={uid}&fullobjects=1"
        what = f"CORINE {year} katalog CLMS"
        response = get_with_retry(
            self._sessions.get(),
            url,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=what,
            headers={"Accept": "application/json"},
        )
        try:
            items = response.json().get("items")
        except (ValueError, AttributeError) as e:
            raise DownloadError(f"{what}: odpowiedz nie jest JSON: {e}") from e
        if not isinstance(items, list) or len(items) != 1:
            count = len(items) if isinstance(items, list) else None
            raise DownloadError(
                f"{what}: oczekiwano 1 rekordu zbioru {uid}, jest {count}"
            )
        raw = items[0].get("characteristics_release_major_version")
        if not isinstance(raw, str) or not raw:
            raise DownloadError(
                f"{what}: rekord bez characteristics_release_major_version"
            )
        return Edition(id=edition_label(raw, what=what), url=url, dataset_uid=uid)

    # =========================================================================
    # Download by bbox
    # =========================================================================

    # The generic provider interface permits source-specific **kwargs;
    # CORINE requires its edition even when called through that interface.
    def download_by_bbox(  # type: ignore[override]
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        year: int,
        **kwargs: Any,
    ) -> Path:
        """
        Download CORINE Land Cover data for a bounding box.

        If CLMS token is configured, downloads GeoTIFF with raw class codes.
        Otherwise, downloads styled PNG preview via WMS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        year : int
            CORINE edition: 2018 (newest), 2012, 2006, 2000, or 1990
            (historical land cover; 1990 is WMS preview only).
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file (.tif if CLMS, .png if WMS)

        Raises
        ------
        ValidationError
            If bbox CRS is not EPSG:2180 or year is invalid
        DownloadError
            If the download fails
        """
        if bbox.crs != "EPSG:2180":
            raise ValidationError(
                f"bbox musi byc w EPSG:2180, podano {bbox.crs}. "
                "Przelicz: SheetParser.get_bbox(crs='EPSG:2180')."
            )

        self.check_year(year)

        output_path = Path(output_path)

        # Use CLMS API if token available and year is supported
        if self.uses_clms(year):
            return self._download_via_clms(bbox, output_path, year, timeout)

        # Fallback to WMS (styled preview)
        return self._download_via_wms(bbox, output_path, year, timeout)

    def _eea_endpoint(self, year: int) -> str:
        """The WMS service of the EEA for the CLC ``year``."""
        return f"{self.EEA_WMS_BASE}/CLC{year}_WM/MapServer/WMSServer"

    def _eea_raster_layer(self, year: int, timeout: int) -> str:
        """The name of the raster layer of the EEA WMS of ``year``, read from the
        GetCapabilities of that service (once per provider: the names carry
        numbers that change when EEA republishes a service).

        Raises
        ------
        DownloadError
            GetCapabilities failed or the service has no such layer.
        """
        layer = self._wms_layers.get(year)
        if layer is None:
            what = f"CORINE {year}"
            params = {
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetCapabilities",
            }
            response = get_with_retry(
                self._sessions.get(),
                f"{self._eea_endpoint(year)}?{urlencode(params)}",
                timeout=timeout,
                retries=self.MAX_RETRIES,
                description=f"{what} GetCapabilities WMS EEA",
            )
            layer = self._wms_layers.setdefault(
                year, _raster_layer_name(response.content, year, what=what)
            )
        return layer

    def _download_via_wms(
        self,
        bbox: BBox,
        output_path: Path,
        year: int,
        timeout: int,
    ) -> Path:
        """Download styled preview via WMS.

        Raises
        ------
        NoCoverageError
            The image is fully transparent: the service has no CLC data of
            that year for the area. The file is not kept.
        DownloadError
            The download fails, or the EEA service has no raster layer.
        """
        # Aspect ratio always comes from the metric (EPSG:3857) envelope, so
        # the ground resolution along Y matches the one along X. Degrees would
        # not do: plate carree is not conformal, a pixel square in degrees is
        # 1/cos(lat) taller on the ground (~1.6x in Poland).
        aspect_bounds = envelope_from_2180(bbox, "EPSG:3857")

        # Envelope actually sent as BBOX, in the CRS of the WMS request:
        # EPSG:3857 for the EEA endpoint, EPSG:4326 for the DLR fallback
        # (same branch as in _construct_wms_url).
        if year in self.EEA_YEARS:
            target_bounds = aspect_bounds
        else:
            target_bounds = envelope_from_2180(bbox, "EPSG:4326")

        # Width follows the ground resolution along X, height follows the
        # aspect ratio of the requested area on the ground.
        width_px = max(1, int((bbox.max_x - bbox.min_x) / self.WMS_RESOLUTION))
        height_px = max(
            1,
            round(
                width_px
                * (aspect_bounds[3] - aspect_bounds[1])
                / (aspect_bounds[2] - aspect_bounds[0])
            ),
        )

        # Limit max size to prevent huge requests
        max_size = 4096
        if width_px > max_size:
            width_px = max_size
        if height_px > max_size:
            height_px = max_size

        layer = (
            self._eea_raster_layer(year, timeout) if year in self.EEA_YEARS else None
        )
        url = self._construct_wms_url(target_bounds, year, width_px, height_px, layer)

        logger.debug(
            "Downloading CLC %s preview via WMS "
            "(no CLMS credentials - styled PNG, not class codes)",
            year,
        )

        path = download_to(
            self._sessions.get(),
            url,
            output_path.with_suffix(".png"),
            timeout=timeout,
            retries=self.MAX_RETRIES,
            validate=reject_error_document("WMS"),
            description=(
                f"CLC {year} for bbox "
                f"({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )
        if _is_blank(path):
            path.unlink(missing_ok=True)
            service = "EEA" if year in self.EEA_YEARS else "DLR"
            raise NoCoverageError(
                f"podglad CORINE {year}: obraz WMS {service} jest w calosci "
                f"przezroczysty - usluga nie ma danych CLC {year} dla tego obszaru "
                "(poza zasiegiem CORINE albo kraj bez tego rocznika); wersja nie "
                "powstala, zmien --bbox albo --year"
            )
        return path

    # =========================================================================
    # CLMS API Download (GeoTIFF with class codes)
    # =========================================================================

    def _download_via_clms(
        self,
        bbox: BBox,
        output_path: Path,
        year: int,
        timeout: int,
    ) -> Path:
        """
        Download raw GeoTIFF with class codes via CLMS API.

        This is an async process:
        1. Authenticate via OAuth2 (via proxy or direct)
        2. Request download with bbox
        3. Poll for task completion
        4. Download the result file
        """
        # Transform bbox to WGS84 for CLMS API
        bbox_wgs84 = envelope_from_2180(bbox, "EPSG:4326")

        # Request download
        dataset_id = self.CLMS_DATASET_UIDS[year]
        download_info_id = self.CLMS_RASTER_DOWNLOAD_IDS[year]

        request_data = {
            "Datasets": [
                {
                    "DatasetID": dataset_id,
                    "DatasetDownloadInformationID": download_info_id,
                    "BoundingBox": [
                        bbox_wgs84[1],  # min_lat
                        bbox_wgs84[0],  # min_lon
                        bbox_wgs84[3],  # max_lat
                        bbox_wgs84[2],  # max_lon
                    ],
                    "OutputFormat": "Geotiff",
                    "OutputGCS": "EPSG:3035",
                }
            ]
        }

        logger.info(f"Requesting CLC {year} GeoTIFF via CLMS API...")

        # Use proxy or direct mode
        if self._use_proxy:
            return self._download_via_clms_proxy(
                request_data, output_path, year, timeout
            )
        else:
            return self._download_via_clms_direct(
                request_data, output_path, year, timeout
            )

    def _download_via_clms_proxy(
        self,
        request_data: dict,
        output_path: Path,
        year: int,
        timeout: int,
    ) -> Path:
        """Download via CLMS API using auth proxy (secure mode)."""
        proxy = _get_auth_proxy()

        # Request download
        response = proxy.proxy_request(
            url=f"{self.CLMS_API_BASE}/@datarequest_post",
            method="POST",
            payload=request_data,
        )

        if not response:
            reason = f": {proxy.last_error}" if proxy.last_error else ""
            raise DownloadError(f"Zadanie przez proxy nie powiodlo sie{reason}")

        if response.get("status_code") != 200:
            raise DownloadError(
                f"CLMS API error: {response.get('status_code')} - "
                f"{response.get('body')}"
            )

        result = json.loads(response.get("body", "{}"))

        # Parse TaskID
        task_id = result.get("TaskID")
        if not task_id:
            task_ids = result.get("TaskIds", [])
            if task_ids and isinstance(task_ids, list) and len(task_ids) > 0:
                task_id = task_ids[0].get("TaskID")

        if not task_id:
            raise DownloadError(f"API CLMS nie zwrocilo TaskID: {result}")

        logger.info(f"CLMS download requested, TaskID: {task_id}")

        # Poll for completion via proxy
        download_url = self._poll_clms_task_proxy(proxy, task_id, timeout)

        # Download the file via proxy
        logger.info("Downloading GeoTIFF from CLMS...")
        output_file = output_path.with_suffix(".tif")
        if proxy.download_file(download_url, output_file):
            logger.info(f"Successfully downloaded to {output_file}")
            return output_file
        else:
            raise DownloadError("Nie udalo sie pobrac pliku przez proxy")

    def _poll_clms_task_proxy(
        self,
        proxy,
        task_id: str,
        timeout: int,
    ) -> str:
        """Poll CLMS API for task completion via proxy."""
        start_time = time.time()

        while time.time() - start_time < self.CLMS_MAX_WAIT:
            response = proxy.proxy_request(
                url=f"{self.CLMS_API_BASE}/@datarequest_search?TaskID={task_id}",
                method="GET",
            )

            if not response or response.get("status_code") != 200:
                logger.debug("CLMS status check failed via proxy")
                time.sleep(self.CLMS_POLL_INTERVAL)
                continue

            result = json.loads(response.get("body", "{}"))
            task_info = result.get(task_id, result)

            status = task_info.get("Status", "")
            if status == "Finished":
                download_url = task_info.get("DownloadURL")
                if download_url:
                    return download_url
                raise DownloadError("Zadanie CLMS zakonczone bez DownloadURL")

            if status in ("Failed", "Cancelled", "Rejected"):
                raise DownloadError(
                    f"CLMS task {status}: {task_info.get('Message', 'nieznany blad')}"
                )

            logger.info(f"CLMS task status: {status}, waiting...")
            time.sleep(self.CLMS_POLL_INTERVAL)

        raise DownloadError(
            f"CLMS download timed out after {self.CLMS_MAX_WAIT} seconds"
        )

    def _download_via_clms_direct(
        self,
        request_data: dict,
        output_path: Path,
        year: int,
        timeout: int,
    ) -> Path:
        """Download via CLMS API using direct authentication."""
        session = self._sessions.get()

        # Get access token via OAuth2
        # Reachable only via has_clms_token with the proxy off, i.e. with
        # _clms_auth set; the check narrows the Optional for the type checker.
        if self._clms_auth is None:
            raise DownloadError("Tryb bezposredni CLMS wymaga clms_credentials")
        access_token = self._clms_auth.get_access_token(session)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = session.post(
                f"{self.CLMS_API_BASE}/@datarequest_post",
                headers=headers,
                json=request_data,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()

            # Parse TaskID from response (can be in different formats)
            task_id = result.get("TaskID")
            if not task_id:
                # Try alternate format: {"TaskIds": [{"TaskID": "..."}]}
                task_ids = result.get("TaskIds", [])
                if task_ids and isinstance(task_ids, list) and len(task_ids) > 0:
                    task_id = task_ids[0].get("TaskID")

            if not task_id:
                raise DownloadError(f"API CLMS nie zwrocilo TaskID: {result}")

            logger.info(f"CLMS download requested, TaskID: {task_id}")

            # Poll for completion
            download_url = self._poll_clms_task(session, headers, task_id, timeout)

            # Download the file
            logger.info("Downloading GeoTIFF from CLMS...")
            return download_to(
                session,
                download_url,
                output_path.with_suffix(".tif"),
                timeout=timeout,
                retries=self.MAX_RETRIES,
                validate=reject_error_document("WMS"),
                description=f"CLC {year} GeoTIFF",
            )

        except requests.RequestException as e:
            raise DownloadError(f"Zapytanie API CLMS nie powiodlo sie: {e}") from e

    def _poll_clms_task(
        self,
        session: requests.Session,
        headers: dict,
        task_id: str,
        timeout: int,
    ) -> str:
        """
        Poll CLMS API for task completion.

        Returns download URL when ready.
        """
        start_time = time.time()

        while time.time() - start_time < self.CLMS_MAX_WAIT:
            try:
                response = session.get(
                    f"{self.CLMS_API_BASE}/@datarequest_search",
                    headers=headers,
                    params={"TaskID": task_id},
                    timeout=timeout,
                )
                response.raise_for_status()
                result = response.json()

                # Response format: {task_id: {..., "Status": "...", ...}}
                task_info = result.get(task_id, result)

                status = task_info.get("Status", "")
                if status == "Finished":
                    download_url = task_info.get("DownloadURL")
                    if download_url:
                        return download_url
                    raise DownloadError("Zadanie CLMS zakonczone bez DownloadURL")

                if status in ("Failed", "Cancelled", "Rejected"):
                    msg = task_info.get("Message", "Unknown error")
                    raise DownloadError(f"CLMS task {status}: {msg}")

                logger.info(f"CLMS task status: {status}, waiting...")
                time.sleep(self.CLMS_POLL_INTERVAL)

            except requests.RequestException as e:
                logger.debug("CLMS status check failed: %s", e)
                time.sleep(self.CLMS_POLL_INTERVAL)

        raise DownloadError(
            f"CLMS download timed out after {self.CLMS_MAX_WAIT} seconds"
        )

    # See download_by_bbox: the edition is mandatory for sheet downloads too.
    def download_by_sheet(  # type: ignore[override]
        self,
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        year: int,
        **kwargs: Any,
    ) -> Path:
        """
        Download CORINE Land Cover data for a map sheet.

        Parameters
        ----------
        sheet : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        year : int
            CORINE edition: 2018 (newest), 2012, 2006, 2000, or 1990
            (historical land cover; 1990 is WMS preview only).
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(sheet)
        bbox = parser.get_bbox(crs="EPSG:2180")

        return self.download_by_bbox(
            bbox=bbox,
            output_path=output_path,
            timeout=timeout,
            year=year,
            **kwargs,
        )

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs: Any,
    ) -> Path:
        """
        CORINE does not support TERYT downloads.

        Raises
        ------
        NotImplementedError
            Always raised - use download_by_bbox or download_by_sheet instead
        """
        raise NotImplementedError(
            "CORINE Land Cover does not support TERYT downloads. "
            "Use download_by_bbox() or download_by_sheet() instead."
        )

    def _construct_wms_url(
        self,
        bounds: tuple[float, float, float, float],
        year: int,
        width: int,
        height: int,
        layer: str | None = None,
    ) -> str:
        """
        Construct WMS GetMap URL.

        Uses EEA Discomap for years 2018, 2012, 2006, 2000.
        Falls back to DLR WMS for year 1990.

        Parameters
        ----------
        bounds : tuple
            Envelope of the requested area in the CRS of the request:
            EPSG:3857 for EEA years, EPSG:4326 for the DLR fallback
            (see transform.bbox.envelope_from_2180)
        year : int
            Reference year
        width : int
            Image width in pixels
        height : int
            Image height in pixels
        layer : str, optional
            The raster layer of the EEA service of ``year``
            (``_eea_raster_layer``); required for the EEA years, unused for 1990

        Returns
        -------
        str
            Full WMS URL
        """
        if year in self.EEA_YEARS:
            if layer is None:
                raise ValueError(f"CLC {year}: GetMap of the EEA needs a layer name")
            return self._construct_eea_wms_url(bounds, year, width, height, layer)
        return self._construct_dlr_wms_url(bounds, year, width, height)

    def _construct_eea_wms_url(
        self,
        bbox_3857: tuple[float, float, float, float],
        year: int,
        width: int,
        height: int,
        layer: str,
    ) -> str:
        """
        Construct EEA Discomap WMS GetMap URL.

        EEA WMS uses WMS 1.3.0 with EPSG:3857 (Web Mercator).
        """
        endpoint = self._eea_endpoint(year)

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": layer,
            "STYLES": "",
            "CRS": "EPSG:3857",
            "BBOX": f"{bbox_3857[0]},{bbox_3857[1]},{bbox_3857[2]},{bbox_3857[3]}",
            "WIDTH": width,
            "HEIGHT": height,
            "FORMAT": self.WMS_FORMAT,
            "TRANSPARENT": "TRUE",
        }

        return f"{endpoint}?{urlencode(params)}"

    def _construct_dlr_wms_url(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        year: int,
        width: int,
        height: int,
    ) -> str:
        """
        Construct DLR WMS GetMap URL (fallback for 1990).

        DLR WMS uses WMS 1.1.1 with EPSG:4326.
        """
        layer = self.DLR_WMS_LAYERS[year]

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "LAYERS": layer,
            "STYLES": "",
            "SRS": "EPSG:4326",
            "BBOX": f"{bbox_wgs84[0]},{bbox_wgs84[1]},{bbox_wgs84[2]},{bbox_wgs84[3]}",
            "WIDTH": width,
            "HEIGHT": height,
            "FORMAT": self.WMS_FORMAT,
            "TRANSPARENT": "TRUE",
        }

        return f"{self.DLR_WMS_ENDPOINT}?{urlencode(params)}"

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_available_layers(self) -> list[str]:
        """
        Return list of available CORINE classes.

        Returns list of year strings as "layers" since CORINE
        provides different datasets per year.
        """
        return [f"CLC_{year}" for year in self.AVAILABLE_YEARS]

    def get_available_years(self) -> list[int]:
        """Return list of available reference years."""
        return self.AVAILABLE_YEARS.copy()

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["PNG", "GTiff"]

    def get_clc_classes(self) -> dict[str, str]:
        """
        Return CORINE Land Cover classification.

        Returns
        -------
        dict[str, str]
            Dictionary mapping class codes to descriptions
        """
        return {
            # Level 1: Artificial surfaces
            "111": "Continuous urban fabric",
            "112": "Discontinuous urban fabric",
            "121": "Industrial or commercial units",
            "122": "Road and rail networks",
            "123": "Port areas",
            "124": "Airports",
            "131": "Mineral extraction sites",
            "132": "Dump sites",
            "133": "Construction sites",
            "141": "Green urban areas",
            "142": "Sport and leisure facilities",
            # Level 1: Agricultural areas
            "211": "Non-irrigated arable land",
            "212": "Permanently irrigated land",
            "213": "Rice fields",
            "221": "Vineyards",
            "222": "Fruit trees and berry plantations",
            "223": "Olive groves",
            "231": "Pastures",
            "241": "Annual crops associated with permanent crops",
            "242": "Complex cultivation patterns",
            "243": "Agriculture with natural vegetation",
            "244": "Agro-forestry areas",
            # Level 1: Forest and semi-natural areas
            "311": "Broad-leaved forest",
            "312": "Coniferous forest",
            "313": "Mixed forest",
            "321": "Natural grasslands",
            "322": "Moors and heathland",
            "323": "Sclerophyllous vegetation",
            "324": "Transitional woodland-shrub",
            "331": "Beaches, dunes, sands",
            "332": "Bare rocks",
            "333": "Sparsely vegetated areas",
            "334": "Burnt areas",
            "335": "Glaciers and perpetual snow",
            # Level 1: Wetlands
            "411": "Inland marshes",
            "412": "Peat bogs",
            "421": "Salt marshes",
            "422": "Salines",
            "423": "Intertidal flats",
            # Level 1: Water bodies
            "511": "Water courses",
            "512": "Water bodies",
            "521": "Coastal lagoons",
            "522": "Estuaries",
            "523": "Sea and ocean",
        }
