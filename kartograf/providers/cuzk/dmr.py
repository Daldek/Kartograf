"""
CuzkDmrProvider — DMR 5G (2 m, exportImage) i DMR 4G (5 m, pliki openzu + exportImage).

Zasada natywnosci: wynik exportImage to pochodna serwera (GeoTIFF); pliki
openzu to bajty CUZK 1:1 — modyfikowany jest wylacznie tag CRS w GeoTIFF
bez CRS (naprawa metadanych). Transformacja pionowa wylacznie na jawne
zadanie (vertical_crs="EVRF2007").

Endpointy pochodza WYLACZNIE z deskryptorow (`get_source(...).channels[..].endpoint`)
— provider nie zna zadnego URL-a. Sidecary pisze warstwa CLI/managera.
"""

import logging
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.transform import xy as _pixel_xy
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, _wkid
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.sources.descriptor import AccessChannel, TransportKind
from kartograf.sources.registry import get_source
from kartograf.transform.crs import (
    REMEDIES,
    PinnedTransform,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

logger = logging.getLogger(__name__)

CUZK_NODATA = -9999.0

_RESOLUTION_KEYS = {"2m": "cz.cuzk.dmr5g", "5m": "cz.cuzk.dmr4g"}
_PIXEL_SIZES = {"2m": 2.0, "5m": 5.0}
_SUPPORTED_VERTICAL = ("Bpv", "EVRF2007")
_DEFAULT_TIMEOUT = 60

# Operacja pionowa Bpv->EVRF2007 ma dokladnosc 0,1 m (rekonesans Zad. 1, krok 7).
_VERTICAL_POLICY = TransformPolicy(min_accuracy_m=0.2)
# Pomocnicze przeliczenia poziome (lon/lat dla operacji pionowej, obwiednia
# zadania exportImage) NIE dotykaja wartosci danych: offset pionowy zmienia sie
# o 0,014 m na stopien szerokosci, wiec blad 2 m to ~3e-7 m wysokosci, a bbox
# zadania i tak reprojektuje serwer. Siatki z CDN nie sa tu potrzebne (kosztuja
# ~2 s na pare ukladow), dlatego allow_network_grids=False.
_LONLAT_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
_ENVELOPE_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)

# Transformacja idzie pasami o stalej liczbie PIKSELI (nie wierszy): przy szerokim
# rastrze pas wierszowy wygenerowalby wielkie tablice indeksow i lon/lat.
_CHUNK_PIXELS = 4_000_000
# Probki na krawedz przy przeliczaniu obwiedni: Krovak wzgledem UTM/PL-1992 jest
# obrocony, wiec obraz krawedzi jest krzywa — same naroza moglyby obwiednie zanizyc.
_EDGE_SAMPLES = 9


class CuzkDmrProvider(BaseProvider):
    """Provider NMT dla Czech (CUZK): DMR 5G / DMR 4G."""

    def __init__(
        self,
        resolution: str = "2m",
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
        target_crs: str | None = None,
        vertical_crs: str = "Bpv",
    ):
        if resolution not in _RESOLUTION_KEYS:
            raise ValidationError(
                f"Nieobslugiwana rozdzielczosc CZ: '{resolution}' (dostepne: 2m, 5m)"
            )
        if vertical_crs == "KRON86":
            raise TransformUnavailableError(
                "Brak transformacji Bpv (EPSG:8357) -> KRON86 (EPSG:9650) "
                "— siatki GUGiK nie sa publiczne",
                remedy=REMEDIES["EPSG:9650"],
            )
        if vertical_crs not in _SUPPORTED_VERTICAL:
            raise ValidationError(
                f"Nieobslugiwany uklad pionowy dla CZ: '{vertical_crs}' "
                f"(dostepne: {', '.join(_SUPPORTED_VERTICAL)})"
            )
        self.descriptor_key = _RESOLUTION_KEYS[resolution]
        self._resolution = resolution
        self._pixel_size = _PIXEL_SIZES[resolution]
        self._target_crs = target_crs
        self._vertical_crs = vertical_crs
        self._session = session or requests.Session()
        self._client = CuzkClient(session=self._session, timeout=_DEFAULT_TIMEOUT)
        self._client_timeout = _DEFAULT_TIMEOUT
        self._sheet_index = SheetIndex(session=self._session, cache=cache)
        self._transforms: dict[tuple[str, str], PinnedTransform] = {}

        descriptor = get_source(self.descriptor_key)
        image_endpoint = _endpoint_for(descriptor.channels, TransportKind.ARCGIS_IMAGE)
        if image_endpoint is None:
            raise ValidationError(
                f"Deskryptor '{self.descriptor_key}' nie ma kanalu "
                f"{TransportKind.ARCGIS_IMAGE.name} z endpointem — "
                f"pobieranie rastrow CUZK niemozliwe"
            )
        self._image_endpoint: str = image_endpoint
        # Kanal plikowy istnieje tylko dla DMR 4G (arkusze SM5 z openzu);
        # None jest tu poprawnym stanem, a nie bledem konfiguracji.
        self._files_endpoint: str | None = _endpoint_for(
            descriptor.channels, TransportKind.DIRECT_FILES
        )

    @property
    def name(self) -> str:
        return f"CUZK DMR ({self._resolution})"

    @property
    def base_url(self) -> str:
        return self._image_endpoint

    @property
    def default_extension(self) -> str:
        return ".tif"

    @property
    def resolution(self) -> str:
        return self._resolution

    @property
    def vertical_crs(self) -> str:
        """Nazwa CLI ukladu pionowego wyniku ("Bpv" albo "EVRF2007")."""
        return self._vertical_crs

    @property
    def sheet_index(self) -> SheetIndex:
        """Wspoldzielony indeks arkuszy (walidacja SM5, PODIL do sidecara)."""
        return self._sheet_index

    @property
    def vertical_transform(self) -> PinnedTransform | None:
        """Przypieta operacja 8357->5621 (None, gdy pobieranie natywne Bpv)."""
        if self._vertical_crs != "EVRF2007":
            return None
        return self._pinned("EPSG:8357", "EPSG:5621", _VERTICAL_POLICY)

    def download(
        self, godlo: str, output_path: Path, timeout: int = _DEFAULT_TIMEOUT
    ) -> Path:
        """Pobierz kafel TM33 (exportImage w 3045) lub arkusz SM5 (openzu).

        `target_crs` dotyczy wylacznie trybu bbox — arkusze i kafle sa zawsze
        pobierane w ukladzie natywnym swojej siatki (godlo definiuje zasieg
        w konkretnym ukladzie, wiec reprojekcja rozjechalaby go z siatka).
        """
        output_path = Path(output_path)
        system = detect_system(godlo)
        if system is None or system.country != "CZ":
            raise ValidationError(
                f"Godlo '{godlo}' nie nalezy do zadnego systemu CZ "
                f"(TM33: 302_5550, SM5: CTES96)"
            )
        if system.id == "cz_sm5":
            self._download_sm5(godlo, output_path, timeout)
        else:  # cz_tm33
            # Parsowanie przez ParserTM33 (pelna walidacja: kilometry parzyste),
            # nie przez sam regex rejestru systemow.
            bbox = ParserTM33(godlo).get_bbox()
            self._client_for(timeout).export_image(
                self._image_endpoint,
                bbox,
                pixel_size=self._pixel_size,
                image_sr=bbox.crs,
                no_data=CUZK_NODATA,
                output_path=output_path,
            )
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
        return output_path

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> Path:
        """Jeden wycinek serwerowy (exportImage) dla dowolnego bboxa."""
        if format != "GTiff":
            raise ValidationError(
                f"CuzkDmrProvider.download_bbox obsluguje tylko GTiff "
                f"(zadano: {format})"
            )
        output_path = Path(output_path)
        image_sr = self._target_crs or "EPSG:5514"
        if _wkid(bbox.crs) != _wkid(image_sr):
            bbox = self._bbox_to_crs(bbox, image_sr)
        self._client_for(timeout).export_image(
            self._image_endpoint,
            bbox,
            pixel_size=self._pixel_size,
            image_sr=image_sr,
            no_data=CUZK_NODATA,
            output_path=output_path,
        )
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
        return output_path

    def _download_sm5(self, godlo: str, output_path: Path, timeout: int) -> None:
        """Arkusz SM5 (DMR 4G) z openzu + naprawa metadanych CRS."""
        if self._resolution != "5m":
            raise ValidationError(
                f"Arkusze SM5 sa dostepne tylko dla --resolution 5m "
                f"(DMR 4G); dla 2m uzyj godla TM33 albo --bbox "
                f"[godlo: {godlo}]"
            )
        if self._files_endpoint is None:
            raise ValidationError(
                f"Deskryptor '{self.descriptor_key}' nie ma kanalu "
                f"{TransportKind.DIRECT_FILES.name} z endpointem — "
                f"pobieranie arkuszy SM5 niemozliwe"
            )
        self._sheet_index.sm5_sheet(godlo)  # walidacja przed pobraniem
        url = self._files_endpoint.format(sheet=godlo)
        try:
            self._client_for(timeout).fetch_file(url, output_path, unzip_single=".tif")
        except DownloadError as e:
            # spec sekcja 7: 404 z openzu -> podpowiedz weryfikacji godla
            raise DownloadError(
                f"{e} — zweryfikuj godlo w indeksie KladyMapovychListu "
                f"(arkusz moze byc znany indeksowi, ale plik openzu "
                f"niedostepny)"
            ) from e
        _assign_crs(output_path, "EPSG:5514")

    def _client_for(self, timeout: int) -> CuzkClient:
        """Klient dla zadanego timeoutu (sesja HTTP zawsze wspoldzielona)."""
        if timeout == self._client_timeout:
            return self._client
        return CuzkClient(session=self._session, timeout=timeout)

    def _pinned(
        self, src_crs: str, dst_crs: str, policy: TransformPolicy
    ) -> PinnedTransform:
        """Przypieta transformacja (jedna na pare ukladow w cyklu zycia providera)."""
        key = (src_crs, dst_crs)
        if key not in self._transforms:
            self._transforms[key] = build_pinned_transform(src_crs, dst_crs, policy)
        return self._transforms[key]

    def _bbox_to_crs(self, bbox: BBox, target_crs: str) -> BBox:
        """Obwiednia bboxa w ukladzie docelowym (normalizacja zadan exportImage).

        Krawedzie sa probkowane (nie tylko naroza), bo obraz prostokata w innym
        ukladzie jest czworokatem o krzywych bokach — obwiednia z samych naroznikow
        potrafi uciac skrawek zadanego obszaru.
        """
        pinned = self._pinned(bbox.crs, target_crs, _ENVELOPE_POLICY)
        xs = np.linspace(bbox.min_x, bbox.max_x, _EDGE_SAMPLES)
        ys = np.linspace(bbox.min_y, bbox.max_y, _EDGE_SAMPLES)
        west = np.full(_EDGE_SAMPLES, bbox.min_x)
        east = np.full(_EDGE_SAMPLES, bbox.max_x)
        south = np.full(_EDGE_SAMPLES, bbox.min_y)
        north = np.full(_EDGE_SAMPLES, bbox.max_y)
        edge_x = np.concatenate([xs, xs, west, east])
        edge_y = np.concatenate([south, north, ys, ys])
        out_x, out_y = pinned.transform(edge_x, edge_y)
        return BBox(
            float(np.min(out_x)),
            float(np.min(out_y)),
            float(np.max(out_x)),
            float(np.max(out_y)),
            target_crs,
        )

    def _apply_vertical_shift(self, path: Path) -> None:
        """Przelicz wartosci rastra przypieta operacja 8357->5621 (per piksel).

        Operacja pionowa wymaga wspolrzednych poziomych w kolejnosci
        (lon, lat, h) — always_xy=True, potwierdzone w rekonesansie (Zad. 1
        krok 7a; zamiana argumentow daje cichy blad ~0,44 m). Piksele nodata
        (oraz ewentualne NaN/inf) NIE sa transformowane — inaczej wartosc
        -9999 zostalaby przesunieta o offset i przestala byc rozpoznawana.
        """
        pinned = self.vertical_transform
        if pinned is None:  # pragma: no cover — wolane tylko dla EVRF2007
            return
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                raise ValidationError(
                    f"Raster {path.name} nie ma CRS — nie da sie wyznaczyc "
                    f"(lon, lat) wymaganych przez operacje pionowa"
                )
            horizontal = self._pinned(str(ds.crs), "EPSG:4326", _LONLAT_POLICY)
            nodata = ds.nodata if ds.nodata is not None else CUZK_NODATA
            logger.debug(
                f"Transformacja pionowa {path.name}: {pinned.description} "
                f"(dokladnosc {pinned.accuracy_m} m), nodata {nodata}"
            )
            chunk_rows = max(1, _CHUNK_PIXELS // ds.width)
            for row_start in range(0, ds.height, chunk_rows):
                rows = min(chunk_rows, ds.height - row_start)
                window = Window(0, row_start, ds.width, rows)
                data = ds.read(1, window=window)
                mask = np.isfinite(data) & (data != nodata)
                if not mask.any():
                    continue
                row_idx, col_idx = np.nonzero(mask)
                xs, ys = _pixel_xy(
                    ds.window_transform(window), row_idx, col_idx, offset="center"
                )
                lon, lat = horizontal.transform(
                    np.asarray(xs, dtype="float64"),
                    np.asarray(ys, dtype="float64"),
                )
                _, _, shifted = pinned.transform(lon, lat, data[mask].astype("float64"))
                data[mask] = np.asarray(shifted, dtype=data.dtype)
                ds.write(data, 1, window=window)


def _endpoint_for(
    channels: tuple[AccessChannel, ...], transport: TransportKind
) -> str | None:
    """Endpoint pierwszego kanalu danego transportu (None, gdy kanalu brak)."""
    return next(
        (ch.endpoint for ch in channels if ch.transport == transport and ch.endpoint),
        None,
    )


def _assign_crs(path: Path, crs: str) -> None:
    """Naprawa metadanych DMR4G-TIFF: wpisz CRS (georeferencja jest w .tfw)."""
    with rasterio.open(path, "r+") as ds:
        if ds.crs is None:
            logger.debug(f"{path.name}: brak CRS w GeoTIFF — wpisuje {crs}")
            ds.crs = CRS.from_string(crs)
