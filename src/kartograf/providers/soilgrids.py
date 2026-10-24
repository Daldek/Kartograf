"""
ISRIC SoilGrids provider for downloading soil property data.

This module provides the SoilGridsProvider class for downloading
soil property data from ISRIC SoilGrids via Web Coverage Service (WCS).

SoilGrids provides global soil information at 250m resolution:
- Soil texture (clay, sand, silt content)
- Soil organic carbon (SOC)
- pH, nitrogen, bulk density
- And more soil properties

Data source: https://soilgrids.org
WCS endpoint: https://maps.isric.org/mapserv

Available properties and the unit of their VALUES in the files. A SoilGrids
raster holds integers ("mapped units" of ISRIC, stored this way to save
space); the familiar unit is ``value / divisor`` (``SoilUnits``; the ISRIC
table https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html,
checked 2026-10-19 against the ISRIC REST ``unit_measure``):

- bdod: bulk density, cg/cm3 (kg/dm3 = value / 100)
- cec: cation exchange capacity, mmol(c)/kg (cmol(c)/kg = value / 10)
- cfvo: coarse fragments, cm3/dm3 (cm3/100cm3 = value / 10)
- clay: clay content, g/kg (% = value / 10)
- nitrogen: total nitrogen, cg/kg (g/kg = value / 100)
- ocd: organic carbon density, hg/m3 (kg/m3 = value / 10)
- ocs: organic carbon stock, t/ha (kg/m2 = value / 10); ONLY depth 0-30cm
- phh2o: pH in H2O, pH x 10 (pH = value / 10)
- sand: sand content, g/kg (% = value / 10)
- silt: silt content, g/kg (% = value / 10)
- soc: soil organic carbon, dg/kg (g/kg = value / 10)

The ``uncertainty`` statistic of every property is the ratio
``(Q0.95 - Q0.05) / Q0.5`` times 10 (no unit).

Depth intervals: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
(every property but ocs). Statistics: mean, Q0.05, Q0.5, Q0.95, uncertainty
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, ValidationError
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

_OWS = "{http://www.opengis.net/ows/2.0}"
_OWS_TITLE = f"{_OWS}ServiceIdentification/{_OWS}Title"
# "SoilGrids250m 2.0 - Clay content" -> "2.0" (D29)
_EDITION_RE = re.compile(r"^SoilGrids250m (\S+) - ")
# The maps whose own GetCapabilities title names no edition (``ocd``:
# "Soilgrids property: Organic carbon density", measured 2026-10-19; the ISRIC
# documentation lists it in the release 2.0): their edition is the one the map
# of ``_EDITION_REFERENCE`` announces, the version of the whole service.
_EDITIONLESS_MAPS = frozenset({"ocd"})
_EDITION_REFERENCE = "clay"
# One pixel of the SoilGrids WCS in EPSG:4326 (250 m). A window narrower than
# half a pixel is answered with HTTP 400 (measured 2026-10-19: 0.001 deg fails,
# 0.0012 deg gives one pixel), so a smaller window is widened to one pixel.
PIXEL_DEGREES = 0.00225


@dataclass(frozen=True)
class SoilUnits:
    """Hold the unit of the integer values of a SoilGrids file and its conversion.

    The ISRIC "mapped units"; ``conventional = value / divisor``.
    """

    mapped: str
    conventional: str
    divisor: int

    def to_extra(self) -> dict[str, Any]:
        """``extra.units`` of the version sidecar."""
        return {
            "mapped": self.mapped,
            "conventional": self.conventional,
            "divisor": self.divisor,
        }


# ISRIC mapped units per property (docstring of the module).
PROPERTY_UNITS = {
    "bdod": SoilUnits("cg/cm3", "kg/dm3", 100),
    "cec": SoilUnits("mmol(c)/kg", "cmol(c)/kg", 10),
    "cfvo": SoilUnits("cm3/dm3", "cm3/100cm3", 10),
    "clay": SoilUnits("g/kg", "%", 10),
    "nitrogen": SoilUnits("cg/kg", "g/kg", 100),
    "ocd": SoilUnits("hg/m3", "kg/m3", 10),
    "ocs": SoilUnits("t/ha", "kg/m2", 10),
    "phh2o": SoilUnits("pH x 10", "pH", 10),
    "sand": SoilUnits("g/kg", "%", 10),
    "silt": SoilUnits("g/kg", "%", 10),
    "soc": SoilUnits("dg/kg", "g/kg", 10),
}
# ``uncertainty`` of any property: 10 x (Q0.95 - Q0.05) / Q0.5, rounded
# (checked on clay: the layer equals the ratio of the quantile layers, |diff| <= 0.5).
UNCERTAINTY_UNITS = SoilUnits(
    "10 * (Q0.95 - Q0.05) / Q0.5", "(Q0.95 - Q0.05) / Q0.5", 10
)


def units_for(property: str, stat: str) -> SoilUnits:
    """Return the unit of the values of the layer ``property``/``stat``.

    The ``uncertainty`` of every property is the same ratio.
    """
    return UNCERTAINTY_UNITS if stat == "uncertainty" else PROPERTY_UNITS[property]


def _at_least_one_pixel(
    bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Widen ``bounds`` (min_lon, min_lat, max_lon, max_lat) to a minimum side length.

    Each side is at least ``PIXEL_DEGREES`` long: a shorter side is widened
    symmetrically around its centre (the WCS answers a window under half a pixel
    with HTTP 400).
    """

    def side(low: float, high: float) -> tuple[float, float]:
        if high - low >= PIXEL_DEGREES:
            return low, high
        centre = (low + high) / 2
        return centre - PIXEL_DEGREES / 2, centre + PIXEL_DEGREES / 2

    min_lon, max_lon = side(bounds[0], bounds[2])
    min_lat, max_lat = side(bounds[1], bounds[3])
    return min_lon, min_lat, max_lon, max_lat


# Properties whose value 0 is a real value, so a raster of zeros may be data: a
# soil without coarse fragments (the 5th percentile of ``cfvo`` is 0 over most
# of Poland, measured 2026-10-19).
_ZERO_IS_DATA = frozenset({"cfvo"})


def is_empty(path: Path, property: str) -> bool:
    """Check whether the SoilGrids raster at ``path`` holds no data.

    Every pixel is 0,
    the value SoilGrids gives the areas it masks (sea, water, built-up land,
    bare rock, ice; the GeoTIFF has no NoData tag).

    ``cfvo`` is never empty: 0 is one of its values, so a raster of zeros
    cannot be told from a masked area. An unreadable file is not empty.
    """
    if property in _ZERO_IS_DATA:
        return False
    import rasterio
    from rasterio.errors import RasterioError

    try:
        with rasterio.open(path) as raster:
            for _, window in raster.block_windows(1):
                if raster.read(1, window=window).any():
                    return False
    except (OSError, ValueError, RasterioError) as e:
        logger.debug("SoilGrids raster %s unreadable: %s", path, e)
        return False
    return True


# Names of the soil properties for the user (Polish, ASCII; one text for --help
# and `soil list-layers`, UX-23); the description adds the unit of the values
# in the file and its conversion (``PROPERTY_UNITS``).
_PROPERTY_NAMES = {
    "bdod": "gestosc objetosciowa",
    "cec": "pojemnosc sorpcyjna",
    "cfvo": "frakcja szkieletowa",
    "clay": "il",
    "nitrogen": "azot calkowity",
    "ocd": "gestosc wegla organicznego",
    "ocs": "zasob wegla organicznego, tylko glebokosc 0-30cm",
    "phh2o": "pH w wodzie (H2O)",
    "sand": "piasek",
    "silt": "pyl",
    "soc": "wegiel organiczny",
}


def _unit_text(units: SoilUnits) -> str:
    return f"w pliku {units.mapped}; {units.conventional} = wartosc / {units.divisor}"


PROPERTY_DESCRIPTIONS = {
    code: f"{name} ({_unit_text(PROPERTY_UNITS[code])})"
    for code, name in _PROPERTY_NAMES.items()
}
STAT_DESCRIPTIONS = {
    "mean": "srednia",
    "Q0.05": "5. percentyl",
    "Q0.5": "mediana",
    "Q0.95": "95. percentyl",
    "uncertainty": f"niepewnosc predykcji ({_unit_text(UNCERTAINTY_UNITS)}; bez "
    "jednostki)",
}
DEPTH_DESCRIPTION = "przedzial glebokosci ponizej powierzchni"


class SoilGridsProvider(LandCoverProvider):
    """
    Provider for downloading soil data from ISRIC SoilGrids.

    SoilGrids is a global gridded soil information system providing
    predictions of soil properties at 250m resolution. Data is accessed
    via OGC Web Coverage Service (WCS).

    Supports two download modes:
    - By bbox: downloads data for specified bounding box
    - By sheet code: converts map sheet ID to bbox and downloads

    TERYT (administrative unit) selection is not supported - SoilGrids is a
    global raster service and has no notion of Polish administrative
    boundaries.

    Examples
    --------
    >>> provider = SoilGridsProvider()
    >>>
    >>> # Download soil organic carbon by bbox
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_by_bbox(
    ...     bbox, Path("./soc.tif"), property="soc", depth="0-5cm", stat="mean"
    ... )
    >>>
    >>> # Download clay content by sheet code
    >>> provider.download_by_sheet(
    ...     "N-34-130-D", Path("./clay.tif"), property="clay",
    ...     depth="15-30cm", stat="mean"
    ... )
    """

    # WCS endpoint base URL
    WCS_BASE = "https://maps.isric.org/mapserv"

    # Available soil properties
    PROPERTIES = [
        "bdod",
        "cec",
        "cfvo",
        "clay",
        "nitrogen",
        "ocd",
        "ocs",
        "phh2o",
        "sand",
        "silt",
        "soc",
    ]

    # Standard depth intervals (every property but ocs)
    DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]

    # Properties published at other depths: ocs is the carbon stock of the
    # topsoil 0-30cm only (GetCapabilities of ocs.map, 2026-10-19: the
    # coverages are ocs_0-30cm_<stat>; ocs_0-5cm_mean is HTTP 404)
    PROPERTY_DEPTHS = {"ocs": ["0-30cm"]}

    # Available statistics
    STATS = ["mean", "Q0.05", "Q0.5", "Q0.95", "uncertainty"]

    # Default settings
    DEFAULT_TIMEOUT = 120
    MAX_RETRIES = MAX_RETRIES

    @classmethod
    def depths_for(cls, property: str) -> list[str]:
        """Return the depth intervals SoilGrids publishes for ``property``.

        The six standard ones, ``ocs`` only 0-30cm.
        """
        return list(cls.PROPERTY_DEPTHS.get(property, cls.DEPTHS))

    @classmethod
    def all_depths(cls) -> list[str]:
        """Return the depth intervals of all properties (the standard ones first)."""
        extra = [depth for depths in cls.PROPERTY_DEPTHS.values() for depth in depths]
        return list(dict.fromkeys([*cls.DEPTHS, *extra]))

    @classmethod
    def layers(cls) -> list[tuple[str, str, str]]:
        """Every layer the service publishes: ``(property, depth, stat)``."""
        return [
            (prop, depth, stat)
            for prop in cls.PROPERTIES
            for depth in cls.depths_for(prop)
            for stat in cls.STATS
        ]

    @classmethod
    def check_layer(cls, property: str, depth: str, stat: str) -> None:
        """``ValidationError`` unless SoilGrids publishes the layer.

        The property, its depth (``depths_for``) and the statistic are checked
        in this order; the error names the allowed values of the argument
        (``option`` and ``allowed``).
        """
        for name, label, value, allowed, where in (
            ("property", "wlasciwosc", property, cls.PROPERTIES, ""),
            ("depth", "glebokosc", depth, cls.depths_for(property), f" dla {property}"),
            ("stat", "statystyka", stat, cls.STATS, ""),
        ):
            if value not in allowed:
                raise ValidationError(
                    f"Nieprawidlowa {label}: {value}. Dostepne{where}: "
                    f"{', '.join(allowed)}",
                    option=name,
                    allowed=tuple(allowed),
                )

    def __init__(
        self,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
    ):
        """
        Initialize SoilGrids provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        cache : MetadataCache, optional
            Metadata cache instance. Currently unused for SoilGrids
            (WCS URLs are computed, not looked up), but accepted for
            API consistency with other providers.
        """
        self._sessions = SessionPerThread(session, factory=requests.Session)
        self._cache = cache
        self.descriptor_key = "global.isric.soilgrids"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "SoilGrids"

    @property
    def base_url(self) -> str:
        """Return source URL."""
        return "https://soilgrids.org"

    # =========================================================================
    # Edition (versioned store signal ``metadata``, D29)
    # =========================================================================

    def capabilities_url(self, property: str) -> str:
        """WCS 2.0.1 GetCapabilities URL of the property map."""
        params = {"SERVICE": "WCS", "VERSION": "2.0.1", "REQUEST": "GetCapabilities"}
        return f"{self.WCS_BASE}?map=/map/{property}.map&{urlencode(params)}"

    def _capabilities_title(self, property: str, timeout: int) -> tuple[str, str]:
        """Return ``(url, title)`` of the GetCapabilities of a property map.

        The GetCapabilities request of the property map
        and the first ``ows:Title`` of its ``ServiceIdentification``.
        """
        url = self.capabilities_url(property)
        response = get_with_retry(
            self._sessions.get(),
            url,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=f"SoilGrids GetCapabilities {property}",
        )
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise DownloadError(
                f"SoilGrids GetCapabilities {property}: XML: {e}"
            ) from e
        return url, (root.findtext(_OWS_TITLE) or "").strip()

    def edition(self, property: str, timeout: int = DEFAULT_TIMEOUT) -> Edition:
        """SoilGrids edition announced by the property map's GetCapabilities.

        The first ``ows:Title`` of ``ServiceIdentification`` has the form
        ``SoilGrids250m <edition> - <property name>``; the edition is the
        version label of every file of this property. The map of ``ocd``
        announces no edition (its title is ``Soilgrids property: Organic
        carbon density``): its edition is the one the map of ``clay``
        announces, the ``url``/``title`` of the edition name that map and
        ``source_property`` says so (``"clay"``; ``None`` for an own map).

        Raises
        ------
        DownloadError
            HTTP failure, unreadable XML or a title without an edition.
        """
        if property not in self.PROPERTIES:
            raise ValidationError(
                f"Nieprawidlowa wlasciwosc: {property}. "
                f"Dostepne: {', '.join(self.PROPERTIES)}"
            )
        url, title = self._capabilities_title(property, timeout)
        match = _EDITION_RE.match(title)
        source_property = None  # the edition of the file's own map
        if match is None and property in _EDITIONLESS_MAPS:
            reference_url, reference_title = self._capabilities_title(
                _EDITION_REFERENCE, timeout
            )
            match = _EDITION_RE.match(reference_title)
            if match is not None:
                url, title = reference_url, reference_title
                source_property = _EDITION_REFERENCE
        if match is None:
            raise DownloadError(
                f"SoilGrids GetCapabilities {property}: brak wydania w tytule "
                f"{title!r} (oczekiwano 'SoilGrids250m <wydanie> - ...')"
            )
        label = edition_label(match.group(1), what="SoilGrids")
        return Edition(id=label, url=url, title=title, source_property=source_property)

    # =========================================================================
    # Download by bbox → WCS
    # =========================================================================

    # The generic provider interface permits source-specific **kwargs;
    # SoilGrids requires an explicit property, depth and statistic.
    def download_by_bbox(  # type: ignore[override]
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        property: str,
        depth: str,
        stat: str,
        **kwargs: Any,
    ) -> Path:
        """
        Download soil property data for a bounding box via WCS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the GeoTIFF should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120)
        property : str
            bdod (bulk density), cec (cation exchange capacity), cfvo
            (coarse fragments), clay (clay), nitrogen (total nitrogen),
            ocd (organic carbon density), ocs (organic carbon stock),
            phh2o (soil pH), sand (sand), silt (silt), soc (organic carbon).
        depth : str
            Soil interval: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm,
            or 100-200cm (centimetres below surface); ocs only 0-30cm.
        stat : str
            mean (average), Q0.05 (5th percentile), Q0.5 (median),
            Q0.95 (95th percentile), or uncertainty (prediction uncertainty).
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded GeoTIFF file

        Raises
        ------
        ValidationError
            If bbox CRS is not EPSG:2180 or parameters are invalid
        DownloadError
            If the download fails
        """
        # Validate CRS
        if bbox.crs != "EPSG:2180":
            raise ValidationError(
                f"bbox musi byc w EPSG:2180, podano {bbox.crs}. "
                "Przelicz: SheetParser.get_bbox(crs='EPSG:2180')."
            )

        # Validate property, its depth and the statistic
        self.check_layer(property, depth, stat)

        output_path = Path(output_path)

        # Transform bbox to WGS84 for WCS; a window smaller than a pixel is
        # widened to one pixel (the WCS answers it with HTTP 400)
        bbox_wgs84 = _at_least_one_pixel(envelope_from_2180(bbox, "EPSG:4326"))

        # Download via WCS
        return self._download_via_wcs(
            bbox_wgs84=bbox_wgs84,
            output_path=output_path,
            property=property,
            depth=depth,
            stat=stat,
            timeout=timeout,
        )

    def _download_via_wcs(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        output_path: Path,
        property: str,
        depth: str,
        stat: str,
        timeout: int,
    ) -> Path:
        """
        Download GeoTIFF via WCS GetCoverage request.

        Parameters
        ----------
        bbox_wgs84 : tuple
            (min_lon, min_lat, max_lon, max_lat) in WGS84
        output_path : Path
            Target path for GeoTIFF
        property : str
            Soil property code
        depth : str
            Depth interval
        stat : str
            Statistic type
        timeout : int
            Request timeout

        Returns
        -------
        Path
            Path to downloaded GeoTIFF
        """
        url = self._construct_wcs_url(bbox_wgs84, property, depth, stat)

        description = f"SoilGrids {property} {depth} {stat}"
        logger.info(f"Downloading {description} via WCS...")

        return download_to(
            self._sessions.get(),
            url,
            output_path.with_suffix(".tif"),
            timeout=timeout,
            retries=self.MAX_RETRIES,
            validate=reject_error_document("WCS"),
            description=description,
        )

    def _construct_wcs_url(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        property: str,
        depth: str,
        stat: str,
    ) -> str:
        """
        Construct WCS GetCoverage URL.

        Coverage ID format: {property}_{depth}_{stat}
        Example: soc_0-5cm_mean

        Parameters
        ----------
        bbox_wgs84 : tuple
            (min_lon, min_lat, max_lon, max_lat)
        property : str
            Soil property code
        depth : str
            Depth interval
        stat : str
            Statistic type

        Returns
        -------
        str
            Full WCS URL
        """
        min_lon, min_lat, max_lon, max_lat = bbox_wgs84

        # Coverage ID format for SoilGrids
        coverage_id = f"{property}_{depth}_{stat}"

        # WCS 2.0.1 GetCoverage request
        # Note: SoilGrids uses specific URL format with map parameter
        base_url = f"{self.WCS_BASE}?map=/map/{property}.map"

        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": "image/tiff",
            "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
            "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
        }

        # Build URL with SUBSET parameters (must be separate for X and Y)
        url = f"{base_url}&{urlencode(params)}"
        url += f"&SUBSET=long({min_lon},{max_lon})"
        url += f"&SUBSET=lat({min_lat},{max_lat})"

        logger.debug(f"WCS URL: {url}")
        return url

    # =========================================================================
    # Download by TERYT
    # =========================================================================

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Path:
        """
        SoilGrids does not support TERYT (administrative unit) selection.

        Raises NotImplementedError always. Earlier versions silently returned
        data for a fixed 60x60 km square around a hardcoded wojewodztwo
        centre, which had nothing to do with the requested powiat.

        Raises
        ------
        NotImplementedError
            Always - use download_by_bbox() or download_by_sheet() instead
        """
        raise NotImplementedError(
            "SoilGrids does not support TERYT selection - use --bbox or "
            "--sheet (download_by_bbox / download_by_sheet)"
        )

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_available_layers(self) -> list[str]:
        """
        Return list of available soil properties.

        Returns
        -------
        list[str]
            List of property codes
        """
        return self.PROPERTIES.copy()

    def get_available_properties(self) -> list[str]:
        """
        Return list of available soil properties (alias for get_available_layers).

        Returns
        -------
        list[str]
            List of property codes
        """
        return self.PROPERTIES.copy()

    def get_available_depths(self, property: str | None = None) -> list[str]:
        """
        Return list of available depth intervals.

        Parameters
        ----------
        property : str, optional
            Only the depths of this property (``depths_for``); default: the
            depths of all properties (``all_depths``).

        Returns
        -------
        list[str]
            List of depth intervals
        """
        return self.all_depths() if property is None else self.depths_for(property)

    def get_available_stats(self) -> list[str]:
        """
        Return list of available statistics.

        Returns
        -------
        list[str]
            List of statistic types
        """
        return self.STATS.copy()

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["GTiff"]

    def get_property_description(self, property: str) -> str:
        """
        Get human-readable description for a soil property.

        Parameters
        ----------
        property : str
            Property code (e.g., "soc")

        Returns
        -------
        str
            Property description
        """
        return PROPERTY_DESCRIPTIONS.get(property, property)
