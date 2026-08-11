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
