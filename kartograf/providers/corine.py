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
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.base import LandCoverProvider
from kartograf.transform.bbox import envelope_from_2180
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
    reject_error_document,
)

logger = logging.getLogger(__name__)

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
            raise DownloadError("Failed to create JWT assertion: missing private_key")

        try:
            assertion = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers=headers if headers else None,
            )
        except Exception as e:
            raise DownloadError(f"Failed to create JWT assertion: {e}") from e

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
                raise DownloadError(f"No access_token in response: {result}")

            logger.info("CLMS access token obtained successfully")
            return access_token

        except requests.RequestException as e:
            raise DownloadError(f"Token exchange failed: {e}") from e


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
    >>> provider.download_by_godlo("N-34-130-D", Path("./preview.png"), year=2018)
    >>>
    >>> # Data mode (CLMS API - raw class codes)
    >>> provider = CorineProvider(clms_token="your-token-here")
    >>> provider.download_by_bbox(bbox, Path("./data.tif"), year=2018)
    """

    # =========================================================================
    # CLMS API Configuration (primary - raw data with class codes)
    # =========================================================================
    CLMS_API_BASE = "https://land.copernicus.eu/api"

    # Dataset UIDs for CORINE Land Cover (from CLMS API)
    CLMS_DATASET_UIDS = {
        2018: "0407d497d3c44bcd93ce8fd5bf78596a",
        2012: "f0a04d46-7506-4d13-8a5e-0c7f22506a8c",
        2006: "e6f25e4e-d847-4c31-95f2-15bf11c93f66",
        2000: "a3f977ae-e863-4b0e-85e7-0accb8a44359",
    }

    # Download information IDs for raster data
    CLMS_RASTER_DOWNLOAD_IDS = {
        2018: "7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb",
        2012: "b0a2b7bb-a1f8-4d99-b987-83ae7f687cf5",
        2006: "a99e5c2f-6c52-4d22-b8b4-6e0c38282ec1",
        2000: "c8f3c1d2-2e7a-4b5c-8e0d-1a2b3c4d5e6f",
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

    # WMS layer names
    EEA_RASTER_LAYER = "12"
    DLR_WMS_LAYERS = {
        1990: "CORINE_LAND_COVER_1990_100x100_ETRS89",
    }

    # Default settings
    DEFAULT_TIMEOUT = 60
    CLMS_POLL_INTERVAL = 10  # seconds between status checks
    CLMS_MAX_WAIT = 600  # max seconds to wait for CLMS download
    MAX_RETRIES = MAX_RETRIES
    DEFAULT_YEAR = 2018

    # Output format settings
    WMS_FORMAT = "image/png"
    WMS_RESOLUTION = 100  # meters per pixel

    def __init__(
        self,
        session: requests.Session | None = None,
        clms_credentials: dict | None = None,
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
                logger.warning(f"Failed to initialize CLMS auth: {e}")

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

    # =========================================================================
    # Download by bbox
    # =========================================================================

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        year: int = DEFAULT_YEAR,
        **kwargs,
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
        year : int, optional
            Reference year: 2018, 2012, 2006, 2000, or 1990 (default: 2018)
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file (.tif if CLMS, .png if WMS)

        Raises
        ------
        ValueError
            If bbox CRS is not EPSG:2180 or year is invalid
        DownloadError
            If the download fails
        """
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        if year not in self.AVAILABLE_YEARS:
            raise ValueError(
                f"Invalid year: {year}. Available years: {self.AVAILABLE_YEARS}"
            )

        output_path = Path(output_path)

        # Use CLMS API if token available and year is supported
        if self.has_clms_token and year in self.CLMS_YEARS:
            return self._download_via_clms(bbox, output_path, year, timeout)

        # Fallback to WMS (styled preview)
        return self._download_via_wms(bbox, output_path, year, timeout)

    def _download_via_wms(
        self,
        bbox: BBox,
        output_path: Path,
        year: int,
        timeout: int,
    ) -> Path:
        """Download styled preview via WMS."""
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

        url = self._construct_wms_url(target_bounds, year, width_px, height_px)

        logger.warning(
            "Downloading CLC %s preview via WMS "
            "(no CLMS credentials - styled PNG, not class codes)",
            year,
        )

        return download_to(
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
            raise DownloadError("Proxy request failed")

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
            raise DownloadError(f"CLMS API did not return TaskID: {result}")

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
            raise DownloadError("Failed to download file via proxy")

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
                logger.warning("CLMS status check failed via proxy")
                time.sleep(self.CLMS_POLL_INTERVAL)
                continue

            result = json.loads(response.get("body", "{}"))
            task_info = result.get(task_id, result)

            status = task_info.get("Status", "")
            if status == "Finished":
                download_url = task_info.get("DownloadURL")
                if download_url:
                    return download_url
                raise DownloadError("CLMS task finished but no DownloadURL")

            if status in ("Failed", "Cancelled", "Rejected"):
                raise DownloadError(
                    f"CLMS task {status}: {task_info.get('Message', 'Unknown error')}"
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
            raise DownloadError("CLMS direct mode requires clms_credentials")
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
                raise DownloadError(f"CLMS API did not return TaskID: {result}")

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
            raise DownloadError(f"CLMS API request failed: {e}") from e

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
                    raise DownloadError("CLMS task finished but no DownloadURL")

                if status in ("Failed", "Cancelled", "Rejected"):
                    msg = task_info.get("Message", "Unknown error")
                    raise DownloadError(f"CLMS task {status}: {msg}")

                logger.info(f"CLMS task status: {status}, waiting...")
                time.sleep(self.CLMS_POLL_INTERVAL)

            except requests.RequestException as e:
                logger.warning(f"CLMS status check failed: {e}")
                time.sleep(self.CLMS_POLL_INTERVAL)

        raise DownloadError(
            f"CLMS download timed out after {self.CLMS_MAX_WAIT} seconds"
        )

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        year: int = DEFAULT_YEAR,
        **kwargs,
    ) -> Path:
        """
        Download CORINE Land Cover data for a map sheet (godło).

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        year : int, optional
            Reference year: 2018, 2012, 2006, 2000, or 1990 (default: 2018)
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
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
        **kwargs,
    ) -> Path:
        """
        CORINE does not support TERYT downloads.

        Raises
        ------
        NotImplementedError
            Always raised - use download_by_bbox or download_by_godlo instead
        """
        raise NotImplementedError(
            "CORINE Land Cover does not support TERYT downloads. "
            "Use download_by_bbox() or download_by_godlo() instead."
        )

    def _construct_wms_url(
        self,
        bounds: tuple[float, float, float, float],
        year: int,
        width: int,
        height: int,
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

        Returns
        -------
        str
            Full WMS URL
        """
        if year in self.EEA_YEARS:
            return self._construct_eea_wms_url(bounds, year, width, height)
        else:
            return self._construct_dlr_wms_url(bounds, year, width, height)

    def _construct_eea_wms_url(
        self,
        bbox_3857: tuple[float, float, float, float],
        year: int,
        width: int,
        height: int,
    ) -> str:
        """
        Construct EEA Discomap WMS GetMap URL.

        EEA WMS uses WMS 1.3.0 with EPSG:3857 (Web Mercator).
        """
        # EEA endpoint for this year
        endpoint = f"{self.EEA_WMS_BASE}/CLC{year}_WM/MapServer/WMSServer"

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": self.EEA_RASTER_LAYER,
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
