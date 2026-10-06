"""
CuzkClient — silnik zrodel CUZK: ArcGIS REST (exportImage, query) + pliki openzu.

Pierwszy silnik sterowany deskryptorem (ADR-022/ADR-023): metody sa generyczne,
parametryzowane endpointem; klient nie zna godel, produktow ani sidecarow.
Retry/backoff i atomic write pochodza z transport/http.py.
"""

import math
import os
import threading
import zipfile
from pathlib import Path
from urllib.parse import urlencode

import rasterio
import requests
from rasterio.crs import CRS

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.transport.http import download_to, get_with_retry
from kartograf.transport.mosaic import mosaic_and_crop

_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def wkid(crs: str) -> str:
    """'EPSG:5514' -> '5514' (ArcGIS przyjmuje goly wkid)."""
    return crs.split(":", 1)[1] if ":" in crs else crs


class CuzkClient:
    """Transport CUZK: zapytania ArcGIS REST i pobieranie plikow openzu."""

    MAX_EXPORT_WIDTH = 15000
    MAX_EXPORT_HEIGHT = 4100
    # Sondy 2026-09-29: 7,5 Mpx OK, 8,38 Mpx HTTP 500 niezaleznie od
    # ksztaltu. Budzet z zapasem wobec tego limitu i timeoutu 60 s.
    MAX_EXPORT_PIXELS = 4_000_000
    QUERY_PAGE_SIZE = 2000  # maxRecordCount uslug CUZK (potwierdzone w Zad. 1)

    def __init__(self, session: requests.Session | None = None, timeout: int = 60):
        self._session = session or requests.Session()
        self._timeout = timeout

    def query(
        self,
        endpoint: str,
        layer: int,
        *,
        bbox: BBox | None = None,
        where: str | None = None,
        out_fields: str = "*",
        out_sr: str | None = None,
    ) -> list[dict]:
        """GET {endpoint}/{layer}/query (f=json) z paginacja resultOffset."""
        url = f"{endpoint}/{layer}/query"
        features: list[dict] = []
        offset = 0
        while True:
            params: dict[str, str] = {
                "f": "json",
                "outFields": out_fields,
                "returnGeometry": "true",
                "resultOffset": str(offset),
                "resultRecordCount": str(self.QUERY_PAGE_SIZE),
            }
            if where is not None:
                params["where"] = where
            if bbox is not None:
                params["geometry"] = (
                    f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y}"
                )
                params["geometryType"] = "esriGeometryEnvelope"
                params["inSR"] = wkid(bbox.crs)
                params["spatialRel"] = "esriSpatialRelIntersects"
            if out_sr is not None:
                params["outSR"] = wkid(out_sr)
            # Siec/429/5xx ponawiane (3 proby, Retry-After), 4xx od razu —
            # wspolna polityka transport/http.py (review N5). Blad tresci
            # (JSON) nie jest ponawiany.
            response = get_with_retry(
                self._session,
                url,
                timeout=self._timeout,
                params=params,
                description=f"Zapytanie {url}",
            )
            try:
                data = response.json()
            except ValueError as e:
                raise DownloadError(f"Zapytanie {url} nieudane: {e}") from e
            if "error" in data:
                raise DownloadError(f"Blad ArcGIS dla {url}: {data['error']}")
            page = data.get("features", [])
            features.extend(page)
            if data.get("exceededTransferLimit") and page:
                offset += len(page)
                continue
            return features

    def fetch_file(
        self,
        url: str,
        output_path: Path,
        *,
        unzip_single: str | None = None,
    ) -> Path:
        """Pobierz plik; przy unzip_single wyciagnij jedyny plik o rozszerzeniu
        (+ towarzyszacy .tfw), zapisz atomowo (oba pliki razem albo zaden),
        usun ZIP. Kazdy blad ekstrakcji => DownloadError, bez pozostawiania
        czesciowych wynikow na dysku."""
        output_path = Path(output_path)
        if unzip_single is None:
            return download_to(self._session, url, output_path, timeout=self._timeout)

        zip_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.zip"
        )
        download_to(self._session, url, zip_path, timeout=self._timeout)
        try:
            _extract_zip_pair(zip_path, output_path, unzip_single, url)
        finally:
            zip_path.unlink(missing_ok=True)
        return output_path

    def export_image(
        self,
        endpoint: str,
        bbox: BBox,
        *,
        pixel_size: float,
        image_sr: str,
        no_data: float = -9999.0,
        output_path: Path,
    ) -> Path:
        """GeoTIFF float32 z {endpoint}/exportImage; kafelkowanie nad limitem.

        no_data NIGDY nie jest pomijane (obszar poza CZ bylby wypelniony
        zerami bez oznaczenia — research 2026-08-10/11, Zad. 1 krok 4).

        CRS zwracany przez exportImage jest bezuzyteczny do reprojekcji
        (`to_epsg()` daje None zarowno dla 5514 — LOCAL_CS, jak i 3045 —
        niedopasowany PROJCS z osiami "(N-E)" vs deklaracja E-N; rekonesans
        Zad. 1, kroki 4-5), wiec po kazdym eksporcie (pojedynczym lub
        mozaice) CRS jest nadpisywany bezwarunkowo na deklarowany image_sr.
        """
        output_path = Path(output_path)
        width_px = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
        height_px = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
        # Kotwica NW i calkowita liczba pikseli, wspolne dla pojedynczego
        # eksportu, kafli i mozaiki. Niezrownany bbox zmienial rozmiar piksela.
        bbox = BBox(
            bbox.min_x,
            bbox.max_y - height_px * pixel_size,
            bbox.min_x + width_px * pixel_size,
            bbox.max_y,
            bbox.crs,
        )

        if (
            width_px <= self.MAX_EXPORT_WIDTH
            and height_px <= self.MAX_EXPORT_HEIGHT
            and width_px * height_px <= self.MAX_EXPORT_PIXELS
        ):
            self._export_single(
                endpoint, bbox, width_px, height_px, image_sr, no_data, output_path
            )
            _overwrite_crs(output_path, image_sr)
            return output_path

        if wkid(bbox.crs) != wkid(image_sr):
            raise ValidationError(
                f"Kafelkowanie exportImage wymaga bbox.crs == image_sr "
                f"(bbox: {bbox.crs}, image_sr: {image_sr}) — znormalizuj bbox "
                f"do ukladu wyjsciowego przed eksportem"
            )

        tiles = _tile_grid(
            bbox,
            pixel_size,
            width_px,
            height_px,
            self.MAX_EXPORT_WIDTH,
            self.MAX_EXPORT_HEIGHT,
            self.MAX_EXPORT_PIXELS,
        )
        tile_paths: list[Path] = []
        try:
            for i, (tile_bbox, tile_w, tile_h) in enumerate(tiles):
                tile_path = output_path.with_name(
                    f"{output_path.name}"
                    f".{os.getpid()}_{threading.get_ident()}.part{i}.tif"
                )
                self._export_single(
                    endpoint,
                    tile_bbox,
                    tile_w,
                    tile_h,
                    image_sr,
                    no_data,
                    tile_path,
                )
                tile_paths.append(tile_path)
            try:
                mosaic_and_crop(tile_paths, bbox, output_path, nodata=no_data)
            except ValidationError:
                raise
            except Exception as e:  # noqa: BLE001 - rasterio/GDAL nie maja wspolnej bazy
                output_path.unlink(missing_ok=True)
                raise DownloadError(
                    f"exportImage: nie udalo sie zszyc {len(tile_paths)} kafli "
                    f"mozaiki w {output_path}: {e}"
                ) from e
            _overwrite_crs(output_path, image_sr)
        finally:
            for p in tile_paths:
                p.unlink(missing_ok=True)
        return output_path

    def _export_single(
        self,
        endpoint: str,
        bbox: BBox,
        width_px: int,
        height_px: int,
        image_sr: str,
        no_data: float,
        output_path: Path,
    ) -> None:
        params = {
            "f": "image",
            "format": "tiff",
            "pixelType": "F32",
            "bbox": ",".join(
                format(v, ".10g")
                for v in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
            ),
            "bboxSR": wkid(bbox.crs),
            "imageSR": wkid(image_sr),
            "size": f"{width_px},{height_px}",
            "noData": f"{no_data:g}",
            "noDataInterpretation": "esriNoDataMatchAny",
        }
        url = f"{endpoint}/exportImage?{urlencode(params)}"
        download_to(self._session, url, output_path, timeout=self._timeout)
        with open(output_path, "rb") as f:
            head = f.read(4)
        if head not in _TIFF_MAGIC:
            with open(output_path, "rb") as f:
                snippet = f.read(500)
            output_path.unlink(missing_ok=True)
            raise DownloadError(
                f"exportImage nie zwrocil TIFF "
                f"(poczatek odpowiedzi: {snippet[:200]!r}) [{url}]"
            )


def _overwrite_crs(output_path: Path, image_sr: str) -> None:
    """Nadpisz CRS pliku na deklarowany image_sr zadania (rasterio "r+").

    exportImage CUZK zwraca GeoTIFF, ktorego CRS jest bezuzyteczny do
    reprojekcji przez GDAL/rasterio: `to_epsg()` daje None zarowno dla
    5514 (zapisywany jako LOCAL_CS, nie PROJCS) jak i dla 3045
    (PROJCS z AUTHORITY poprawnym, ale osiami "(N-E)" niezgodnymi z
    deklaracja Easting/Northing — GDAL nie dopasowuje kodu EPSG).
    Krok wykonywany bezwarunkowo, bo tag `nodata` serwer JUZ ustawia
    poprawnie (rekonesans Zad. 1, krok 4) — nie ma potrzeby go dopisywac.
    """
    try:
        with rasterio.open(output_path, "r+") as ds:
            ds.crs = CRS.from_epsg(int(wkid(image_sr)))
    except Exception as e:
        output_path.unlink(missing_ok=True)
        raise DownloadError(
            f"exportImage: nie udalo sie nadpisac CRS na {image_sr} "
            f"w {output_path}: {e}"
        ) from e


def _tile_grid(
    bbox: BBox,
    pixel_size: float,
    width_px: int,
    height_px: int,
    max_w: int,
    max_h: int,
    max_px: int,
) -> list[tuple[BBox, int, int]]:
    """Deterministyczna siatka kafli cieta po pelnych pikselach (N->S, W->E);
    kotwica w narozniku NW — spojnie z rasterio.merge(bounds=...) i
    transform/raster.warp_to_grid (from_origin(min_x, max_y)).

    Why NW: siatka wyniku mozaiki zawsze startuje w max_y i ma wysokosc
    round((max_y-min_y)/res), wiec przy bboxie o ulamkowej wysokosci
    kotwica SW rozjezdza sie z nia o 0<delta<res: dolny wiersz wyniku
    wypada pod zasiegiem kafli (caly pas nodata), a tresc — przenoszona
    przez merge blokami, bez resamplingu — jest przesunieta do 1 px.
    To ten sam rzad bledu geolokalizacji, dla ktorego ADR-024 zakazal
    reprojekcji serwerowej, i tak samo niewidoczny w metadanych (A3-1).
    """

    def _splits(total_px: int, parts: int) -> list[tuple[int, int]]:
        base, extra = divmod(total_px, parts)
        return [
            (i * base + min(i, extra), base + (1 if i < extra else 0))
            for i in range(parts)
        ]

    # Kwadratowawe kafle zamiast waskich pasow 15000 x 260 px:
    # sondy serwera potwierdzily te klase ksztaltow, nie dlugie pasy.
    col_cap = max(1, min(max_w, math.isqrt(max_px)))
    cols = _splits(width_px, math.ceil(width_px / col_cap))
    tile_w = max(size for _, size in cols)
    row_cap = max(1, min(max_h, max_px // tile_w))
    rows = _splits(height_px, math.ceil(height_px / row_cap))

    tiles: list[tuple[BBox, int, int]] = []
    for row_off, row_px in rows:
        for col_off, col_px in cols:
            tiles.append(
                (
                    BBox(
                        bbox.min_x + col_off * pixel_size,
                        bbox.max_y - (row_off + row_px) * pixel_size,
                        bbox.min_x + (col_off + col_px) * pixel_size,
                        bbox.max_y - row_off * pixel_size,
                        bbox.crs,
                    ),
                    col_px,
                    row_px,
                )
            )
    return tiles


def _extract_zip_pair(
    zip_path: Path, output_path: Path, unzip_single: str, url: str
) -> None:
    """Wyciagnij dokladnie 1 plik o rozszerzeniu unzip_single (+ opcjonalny
    towarzyszacy .tfw) z zip_path do output_path.

    Oba pliki sa najpierw rozpakowywane do lokalizacji tymczasowych; dopiero
    gdy WSZYSTKIE ekstrakcje sie powioda, sa commitowane (os.replace) razem.
    Kazdy blad na dowolnym etapie (uszkodzony ZIP, zla liczba dopasowan, IO,
    nieobslugiwana kompresja, zaszyfrowany element, blad commitu) mapuje sie
    na DownloadError, a wszelkie juz zapisane pliki tymczasowe/wynikowe sa
    sprzatane — na dysku nie zostaje ani czesciowy .tif, ani osierocony .tfw.
    """
    tfw_path = output_path.with_suffix(".tfw")
    tmp_main = output_path.with_name(
        f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )
    tmp_tfw = tfw_path.with_name(
        f"{tfw_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )
    has_tfw = False
    try:
        with zipfile.ZipFile(zip_path) as zf:
            suffix = unzip_single.lower()
            names = [n for n in zf.namelist() if n.lower().endswith(suffix)]
            if len(names) != 1:
                raise DownloadError(
                    f"ZIP {url}: oczekiwano dokladnie 1 pliku "
                    f"'{unzip_single}', znaleziono {len(names)}"
                )
            _extract_to(zf, names[0], tmp_main)
            stem = names[0].rsplit(".", 1)[0].lower()
            tfw_member = next(
                (n for n in zf.namelist() if n.lower() == f"{stem}.tfw"), None
            )
            has_tfw = tfw_member is not None
            if tfw_member is not None:
                _extract_to(zf, tfw_member, tmp_tfw)

        # Obie ekstrakcje gotowe w tmp -> commit atomowy razem.
        os.replace(tmp_main, output_path)
        try:
            if has_tfw:
                os.replace(tmp_tfw, tfw_path)
        except OSError:
            output_path.unlink(missing_ok=True)
            raise
    except DownloadError:
        raise
    except zipfile.BadZipFile as e:
        raise DownloadError(f"Uszkodzony ZIP z {url}: {e}") from e
    except Exception as e:
        raise DownloadError(f"Rozpakowanie ZIP {url} nieudane: {e}") from e
    finally:
        tmp_main.unlink(missing_ok=True)
        tmp_tfw.unlink(missing_ok=True)


def _extract_to(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    """Wypakuj element ZIP do target (bez commitu/rename — robi to wolajacy)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, open(target, "wb") as dst:
        while chunk := src.read(1_048_576):
            dst.write(chunk)
