"""
CuzkLazProvider - CUZK point clouds (DMR 5G/4G, DMP 1G/OK) from openzu.

CUZK publishes one ZIP with one ``.laz`` per sheet, in two pairs only:
SM5 sheets in S-JTSK (EPSG:5514) with Bpv heights, and TM33 2x2 km tiles in
ETRS89/TM33N (EPSG:3045) with EVRF2007 heights. A point cloud is never
transformed, so the height system chooses the sheet system (plan B, decision
2) and the stored file is the ZIP member byte for byte. Sheets of an area
come from the ``KladyMapovychListu`` index (layer 24 SM5, layer 26 TM33).
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, wkid
from kartograf.providers.cuzk.raster import bbox_to_crs
from kartograf.providers.cuzk.sheets import SheetIndex, SheetInfo
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import CZ_SYSTEM_CRS, channel_for, get_source
from kartograf.sources.variants import (
    cz_laz_error,
    cz_sheet_system,
    find_cz_laz_variant,
)
from kartograf.transport.http import SessionPerThread, head_signal


class CuzkLazProvider(BaseProvider):
    """CUZK LAZ files of one model: SM5 sheets (Bpv) or TM33 tiles (EVRF2007).

    Parameters
    ----------
    model : str
        ``dmr5g``, ``dmr4g``, ``dmp1g`` or ``dmpok``.
    session : requests.Session, optional
        Injected HTTP session (its use from many threads is the caller's
        concern); by default one new session per thread.
    cache : MetadataCache, optional
        Cache of the sheet index (``None`` = no caching).
    vertical_crs : str
        ``"Bpv"`` (SM5 sheets, EPSG:5514) or ``"EVRF2007"`` (TM33 tiles,
        EPSG:3045).

    Raises
    ------
    ValidationError
        Missing or unknown model, or a height system without LAZ files
        (before any request).
    """

    DEFAULT_TIMEOUT = 60

    def __init__(
        self,
        model: str,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
        *,
        vertical_crs: str,
    ):
        variant = find_cz_laz_variant(model=model, vertical_crs=vertical_crs)
        self.descriptor_key = variant.source
        self._source_name = get_source(variant.source).name
        self._model = model
        self._vertical_crs = vertical_crs
        self._system = variant.systems[0]
        self._channel = channel_for(
            self.descriptor_key,
            TransportKind.DIRECT_FILES,
            CZ_SYSTEM_CRS[self._system],
        )
        if self._channel.endpoint is None:
            raise ValidationError(
                f"Deskryptor '{self.descriptor_key}' nie ma endpointu plikow "
                f"{self._channel.horizontal_crs}"
            )
        self._endpoint: str = self._channel.endpoint
        self._cache = cache
        self._sessions = SessionPerThread(session, factory=requests.Session)

    @property
    def name(self) -> str:
        return f"CUZK LAZ ({self._source_name})"

    @property
    def base_url(self) -> str:
        return self._endpoint

    @property
    def default_extension(self) -> str:
        return ".laz"

    @property
    def model(self) -> str:
        """CUZK model: ``dmr5g``, ``dmr4g``, ``dmp1g`` or ``dmpok``."""
        return self._model

    @property
    def vertical_crs(self) -> str:
        """CLI name of the files' native height system ("Bpv" or "EVRF2007")."""
        return self._vertical_crs

    @property
    def system(self) -> str:
        """Sheet system of the files: ``"sm5"`` or ``"tm33"``."""
        return self._system

    @property
    def horizontal_crs(self) -> str:
        """Native CRS of the files: EPSG:5514 (SM5) or EPSG:3045 (TM33)."""
        return self._channel.horizontal_crs

    @property
    def sheet_index(self) -> SheetIndex:
        """Sheet index on the calling thread's session (zero IO to build)."""
        return SheetIndex(session=self._sessions.get(), cache=self._cache)

    def sheets(self, area: BBox) -> list[SheetInfo]:
        """Index sheets of the files intersecting ``area`` (any supported CRS).

        The area is carried to the index CRS of the system through the pinned
        operation (``bbox_to_crs``); the sheets are ``SheetIndex.file_sheets``
        (SM5 with a part in CZ, TM33 tiles not marked outside CZ), sorted by
        sheet code.
        """
        crs = self.horizontal_crs
        if wkid(area.crs) != wkid(crs):
            area = bbox_to_crs(area, crs)
        return self.sheet_index.file_sheets(self._system, area)

    def file_url(self, sheet: str) -> str:
        """openzu ZIP of a sheet code of this provider's system.

        Raises
        ------
        ValidationError
            Not a CZ code, or a code of the other sheet system.
        """
        sheet = sheet.strip()
        system = cz_sheet_system(sheet)
        if system != self._system:
            raise cz_laz_error(
                model=self._model, vertical_crs=self._vertical_crs, system=system
            ) or ValidationError(
                f"Godlo '{sheet}' spoza systemu {self._system}", option="sheet"
            )
        return self._endpoint.format(sheet=sheet)

    def file_signal(self, sheet: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """HTTP signal of the sheet's ZIP (one ``HEAD``, nothing downloaded)."""
        return head_signal(self._sessions.get(), self.file_url(sheet), timeout=timeout)

    def download(
        self,
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        *,
        on_download: Callable[[], None] | None = None,
        on_response: Callable[[requests.Response], None] | None = None,
    ) -> Path:
        """Store the sheet's ``.laz`` exactly as the ZIP member (no transform).

        The code is validated before any transfer: the system/height pair,
        an SM5 sheet against the index, a TM33 tile by its grid.
        ``on_download`` is called right before the transfer; ``on_response``
        receives the ZIP response (``response_signal``).

        Raises
        ------
        ValidationError
            Wrong pair, unknown SM5 sheet or malformed TM33 code.
        DownloadError
            openzu failure; a 404 keeps ``status_code`` and points to the
            sheet index.
        """
        sheet = sheet.strip()
        url = self.file_url(sheet)
        if self._system == "sm5":
            self.sheet_index.sm5_sheet(sheet)
        else:
            ParserTM33(sheet)  # full grid validation (even kilometres)
        if on_download is not None:
            on_download()
        client = CuzkClient(session=self._sessions.get(), timeout=timeout)
        try:
            client.fetch_file(
                url, Path(output_path), unzip_single=".laz", on_response=on_response
            )
        except DownloadError as e:
            if e.status_code != 404:
                raise
            raise DownloadError(
                f"{e} - zweryfikuj godlo w indeksie KladyMapovychListu "
                f"(arkusz moze byc znany indeksowi, ale plik openzu niedostepny)",
                sheet=sheet,
                status_code=e.status_code,
            ) from e
        return Path(output_path)
