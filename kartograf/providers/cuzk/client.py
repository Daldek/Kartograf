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
from kartograf.transport.http import download_to
from kartograf.transport.mosaic import mosaic_and_crop

_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def _wkid(crs: str) -> str:
    """'EPSG:5514' -> '5514' (ArcGIS przyjmuje goly wkid)."""
    return crs.split(":", 1)[1] if ":" in crs else crs


class CuzkClient:
    """Transport CUZK: zapytania ArcGIS REST i pobieranie plikow openzu."""

    MAX_EXPORT_WIDTH = 15000
    MAX_EXPORT_HEIGHT = 4100
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
                params["inSR"] = _wkid(bbox.crs)
                params["spatialRel"] = "esriSpatialRelIntersects"
            if out_sr is not None:
                params["outSR"] = _wkid(out_sr)
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as e:
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

        if width_px <= self.MAX_EXPORT_WIDTH and height_px <= self.MAX_EXPORT_HEIGHT:
            self._export_single(
                endpoint, bbox, width_px, height_px, image_sr, no_data, output_path
            )
            _overwrite_crs(output_path, image_sr)
            return output_path

        if _wkid(bbox.crs) != _wkid(image_sr):
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
            mosaic_and_crop(tile_paths, bbox, output_path, nodata=no_data)
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
            "bboxSR": _wkid(bbox.crs),
            "imageSR": _wkid(image_sr),
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
            ds.crs = CRS.from_epsg(int(_wkid(image_sr)))
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
) -> list[tuple[BBox, int, int]]:
    """Deterministyczna siatka kafli cieta po pelnych pikselach (S->N, W->E)."""

    def _splits(total_px: int, max_px: int) -> list[tuple[int, int]]:
        n = math.ceil(total_px / max_px)
        base, extra = divmod(total_px, n)
        sizes = [base + (1 if i < extra else 0) for i in range(n)]
        offsets = [sum(sizes[:i]) for i in range(n)]
        return list(zip(offsets, sizes, strict=True))

    tiles: list[tuple[BBox, int, int]] = []
    for row_off, row_px in _splits(height_px, max_h):
        for col_off, col_px in _splits(width_px, max_w):
            tiles.append(
                (
                    BBox(
                        bbox.min_x + col_off * pixel_size,
                        bbox.min_y + row_off * pixel_size,
                        bbox.min_x + (col_off + col_px) * pixel_size,
                        bbox.min_y + (row_off + row_px) * pixel_size,
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
            if has_tfw:
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
