"""
CuzkClient — silnik zrodel CUZK: ArcGIS REST (exportImage, query) + pliki openzu.

Pierwszy silnik sterowany deskryptorem (ADR-022/ADR-023): metody sa generyczne,
parametryzowane endpointem; klient nie zna godel, produktow ani sidecarow.
Retry/backoff i atomic write pochodza z transport/http.py.
"""

import os
import threading
import zipfile
from pathlib import Path

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.transport.http import download_to

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
        (+ towarzyszacy .tfw), zapisz atomowo, usun ZIP."""
        output_path = Path(output_path)
        if unzip_single is None:
            return download_to(self._session, url, output_path, timeout=self._timeout)

        zip_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.zip"
        )
        download_to(self._session, url, zip_path, timeout=self._timeout)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                suffix = unzip_single.lower()
                names = [n for n in zf.namelist() if n.lower().endswith(suffix)]
                if len(names) != 1:
                    raise DownloadError(
                        f"ZIP {url}: oczekiwano dokladnie 1 pliku "
                        f"'{unzip_single}', znaleziono {len(names)}"
                    )
                _extract_member(zf, names[0], output_path)
                stem = names[0].rsplit(".", 1)[0].lower()
                tfw = next(
                    (n for n in zf.namelist() if n.lower() == f"{stem}.tfw"), None
                )
                if tfw is not None:
                    _extract_member(zf, tfw, output_path.with_suffix(".tfw"))
        except zipfile.BadZipFile as e:
            raise DownloadError(f"Uszkodzony ZIP z {url}: {e}") from e
        finally:
            zip_path.unlink(missing_ok=True)
        return output_path


def _extract_member(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    """Wypakuj element ZIP do target atomowo (tmp + os.replace)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    try:
        with zf.open(member) as src, open(tmp, "wb") as dst:
            while chunk := src.read(1_048_576):
                dst.write(chunk)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
