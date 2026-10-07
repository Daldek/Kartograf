"""
CuzkDmrProvider — DMR 5G (2 m, exportImage) i DMR 4G (5 m, pliki openzu + exportImage).

Zasada natywnosci: wynik exportImage to pochodna serwera (GeoTIFF); pliki
openzu to bajty CUZK 1:1 — modyfikowany jest wylacznie tag CRS w GeoTIFF
bez CRS (naprawa metadanych). Transformacja pionowa wylacznie na jawne
zadanie (vertical_crs="EVRF2007").

Endpointy pochodza WYLACZNIE z deskryptorow (`get_source(...).channels[..].endpoint`)
— provider nie zna zadnego URL-a. Sidecary pisze warstwa CLI/managera.
"""

import dataclasses
import logging
import os
import shutil
import threading
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.transform import xy as _pixel_xy
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, transform_bbox
from kartograf.core.parser_registry import detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, wkid
from kartograf.providers.cuzk.sheets import SheetIndex
from kartograf.sources.descriptor import AccessChannel, TransportKind
from kartograf.sources.registry import get_source
from kartograf.transform.crs import (
    CONTENT_POLICY,
    REMEDIES,
    WARP_MARGIN_PX,
    PinnedTransform,
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)
from kartograf.transform.raster import warp_to_grid

logger = logging.getLogger(__name__)

CUZK_NODATA = -9999.0

# Uklad, w ktorym CUZK TRZYMA dane rastrowe. Serwer dostaje zadania wylacznie
# w nim: imageSR=2180 gubi transformacje datum (blad 135 m, ADR-024).
# Dawne 1,25 m dla 3045 wynikalo z roznicy operacji czeskiej EPSG:1622
# i slowackiej EPSG:4829 w lokalnej referencji, nie bledu serwera (errata).
NATIVE_CRS = "EPSG:5514"

_RESOLUTION_KEYS = {"2m": "cz.cuzk.dmr5g", "5m": "cz.cuzk.dmr4g"}
_PIXEL_SIZES = {"2m": 2.0, "5m": 5.0}
_SUPPORTED_VERTICAL = ("Bpv", "EVRF2007")
_DEFAULT_TIMEOUT = 60

# Punkt kontrolny dla operacji POZIOMYCH, ktorych zrodlem jest uklad natywny
# — mniej wiecej srodek Czech (15,5E / 49,8N) w Krovaku. Siatka, ktora go nie
# pokrywa (np. sk_gku, Slowacja), zwraca tam inf i zostaje odrzucona, zanim
# zdazy popsuc pobranie (audyt 0.7.0, A1-2).
CZ_PROBE_NATIVE: tuple[float, float] = (-670165.0, -1084718.0)

# Operacja pionowa Bpv->EVRF2007 ma dokladnosc 0,1 m (rekonesans Zad. 1, krok 7).
# Bez probe: para jest czysto pionowa, wiec transformer.transform(x, y) nie ma
# tu sensu jako test pokrycia.
_VERTICAL_POLICY = TransformPolicy(min_accuracy_m=0.2)
# Pomocnicze przeliczenia poziome NIE dotykaja wartosci danych, wiec limit
# jest luzniejszy niz dla operacji reprojektujacej tresc:
#  - lon/lat dla operacji pionowej: offset zmienia sie o 0,014 m na stopien
#    szerokosci, wiec blad 2 m to ~3e-7 m wysokosci;
#  - obwiednia zadania natywnego: ma tylko POKRYC obszar celu, a ewentualny
#    rozjazd z operacja przypieta (<= 2 m) miesci sie w zapasie
#    WARP_MARGIN_PX (4 px = 8 m przy 2 m) — zmniejszajac ten zapas trzeba
#    zaostrzyc te polityke albo policzyc obwiednie ta sama operacja co warp.
# Siatki z CDN nie sa tu potrzebne (kosztuja ~2 s na pare ukladow), dlatego
# allow_network_grids=False.
_LONLAT_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
_ENVELOPE_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
# Operacja reprojektujaca TRESC rastra: CONTENT_POLICY, zapas obwiedni:
# WARP_MARGIN_PX — oba z transform/crs.py, wspolne z wycinkiem PL (D9).

# Transformacja idzie pasami o stalej liczbie PIKSELI (nie wierszy): przy szerokim
# rastrze pas wierszowy wygenerowalby wielkie tablice indeksow i lon/lat.
_CHUNK_PIXELS = 4_000_000


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
        # Fail-fast jak przy KRON86: brak bezpiecznej operacji 8357->5621 ma
        # przerwac PRZED jakimkolwiek pobieraniem, zeby uzytkownik nie zaplacil
        # za transfer i nie dostal pliku w Bpv pod nazwa zamowiona jako EVRF2007.
        self._vertical_transform: PinnedTransform | None = (
            self._pinned("EPSG:8357", "EPSG:5621", _VERTICAL_POLICY)
            if vertical_crs == "EVRF2007"
            else None
        )
        # Ta sama zasada dla poziomu: gdy uzytkownik zazadal ukladu innego niz
        # natywny, brak bezpiecznej operacji ma przerwac przed transferem.
        if target_crs is not None:
            self.horizontal_transform(target_crs)

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

    def horizontal_transform(self, target_crs: str) -> PinnedTransform | None:
        """Przypieta operacja ``EPSG:5514 -> target_crs`` uzyta do reprojekcji
        TRESCI rastra; ``None``, gdy wynik zostaje w ukladzie natywnym.

        Ta sama instancja co uzyta przy pobieraniu (cache ``_transforms``), wiec
        opis i dokladnosc w sidecarze opisuja faktycznie wykonana operacje.
        """
        if wkid(target_crs) == wkid(NATIVE_CRS):
            return None
        return self._pinned(
            NATIVE_CRS, target_crs, CONTENT_POLICY, probe=CZ_PROBE_NATIVE
        )

    @property
    def vertical_transform(self) -> PinnedTransform | None:
        """Przypieta operacja 8357->5621 (None, gdy pobieranie natywne Bpv).

        Budowana w konstruktorze — patrz uwaga o fail-fast tamze.
        """
        return self._vertical_transform

    def download(
        self, godlo: str, output_path: Path, timeout: int = _DEFAULT_TIMEOUT
    ) -> Path:
        """Pobierz kafel TM33 (siatka w 3045) lub arkusz SM5 (openzu, 5514).

        `target_crs` dotyczy wylacznie trybu bbox — godlo definiuje zasieg
        w konkretnym ukladzie, wiec reprojekcja rozjechalaby go z siatka.
        Kafel TM33 lezy w EPSG:3045, a dane CUZK w EPSG:5514: `exportImage`
        dostaje zadanie natywne, a na siatke kafla przenosi je lokalny warp
        (ADR-024). Arkusz SM5 przychodzi plikiem juz w 5514 — bez warpu.
        """
        output_path = Path(output_path)
        system = detect_system(godlo)
        if system.country != "CZ":
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
            self._export_raster(bbox, output_path, timeout)
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
        """Jeden wycinek dla dowolnego bboxa (`--target-crs` => warp lokalny)."""
        if format != "GTiff":
            raise ValidationError(
                f"CuzkDmrProvider.download_bbox obsluguje tylko GTiff "
                f"(zadano: {format})"
            )
        output_path = Path(output_path)
        image_sr = self._target_crs or NATIVE_CRS
        if wkid(bbox.crs) != wkid(image_sr):
            bbox = self._bbox_to_crs(bbox, image_sr)
        self._export_raster(bbox, output_path, timeout)
        if self.vertical_transform is not None:
            self._apply_vertical_shift(output_path)
        return output_path

    def _export_raster(self, bbox: BBox, output_path: Path, timeout: int) -> None:
        """Raster pokrywajacy ``bbox`` w ukladzie ``bbox.crs``.

        Serwer dostaje zadanie WYLACZNIE w ukladzie natywnym (``NATIVE_CRS``);
        gdy cel jest inny, tresc jest reprojektowana lokalnie przypieta
        operacja z czeskim krokiem datum EPSG:1622 (1,0 m).
        ``exportImage&imageSR=2180`` gubi transformacje datum S-JTSK->ETRS89
        (tresc przesunieta o 135 m; ADR-024). Dawne 1,25 m dla 3045 to roznica
        EPSG:1622/4829 w referencji lokalnej, nie blad serwera (errata ADR-024).
        Lokalny warp pozwala wymusic i zapisac operacje niezaleznie od serwera.

        Kafelkowanie (limity ``exportImage``) i mozaikowanie dzieja sie po
        stronie ukladu natywnego, czyli PRZED warpem — szew kafli nie moze
        wiec zostac utrwalony przez interpolacje.

        Warp to wspolny ``transform/raster.warp_to_grid`` (ten sam co w torze
        PL): zapis przez plik tymczasowy i ``os.replace``, wiec nieudana
        przebudowa (``--force``) zostawia poprzedni plik wyniku nietkniety.
        """
        client = self._client_for(timeout)
        # None == cel jest ukladem natywnym: serwer wydaje dane wprost
        pinned = self.horizontal_transform(bbox.crs)
        if pinned is None:
            client.export_image(
                self._image_endpoint,
                bbox,
                pixel_size=self._pixel_size,
                image_sr=NATIVE_CRS,
                no_data=CUZK_NODATA,
                output_path=output_path,
            )
            return

        native_bbox = self._native_request_bbox(bbox)
        native_path = output_path.with_name(
            f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.native.tif"
        )
        try:
            client.export_image(
                self._image_endpoint,
                native_bbox,
                pixel_size=self._pixel_size,
                image_sr=NATIVE_CRS,
                no_data=CUZK_NODATA,
                output_path=native_path,
            )
            # Wspolny warp torow PL i CZ (D8): zapis przez plik tymczasowy
            # i os.replace — awaria NIE kasuje poprzedniego wyniku (N7).
            warp_to_grid(
                native_path,
                output_path,
                bbox,
                self._pixel_size,
                pinned,
                src_crs=NATIVE_CRS,
                nodata=CUZK_NODATA,
            )
        finally:
            native_path.unlink(missing_ok=True)

    def _native_request_bbox(self, bbox: BBox) -> BBox:
        """Obwiednia zadania natywnego: cel przeliczony do 5514 plus zapas."""
        native = self._bbox_to_crs(bbox, NATIVE_CRS)
        margin = WARP_MARGIN_PX * self._pixel_size
        return BBox(
            native.min_x - margin,
            native.min_y - margin,
            native.max_x + margin,
            native.max_y + margin,
            NATIVE_CRS,
        )

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
        self,
        src_crs: str,
        dst_crs: str,
        policy: TransformPolicy,
        *,
        probe: tuple[float, float] | None = None,
    ) -> PinnedTransform:
        """Przypieta transformacja (jedna na pare ukladow w cyklu zycia providera).

        `probe` (w ukladzie ZRODLOWYM) doklada do polityki punkt kontrolny:
        kandydat, ktory zwraca tam inf/NaN, odpada — tak wypada siatka obcego
        kraju, formalnie dokladniejsza, ale nieobejmujaca naszych danych.
        Klucz cache pozostaje sama para ukladow: probe wylacznie ODRZUCA
        kandydatow (nie zmienia rankingu), wiec pierwsze zapytanie o pare
        ustala operacje dla calego cyklu zycia providera.
        """
        key = (src_crs, dst_crs)
        if key not in self._transforms:
            if probe is not None:
                policy = dataclasses.replace(policy, probe_point=probe)
            self._transforms[key] = build_pinned_transform(src_crs, dst_crs, policy)
        return self._transforms[key]

    def _bbox_to_crs(self, bbox: BBox, target_crs: str) -> BBox:
        """Obwiednia bboxa w ukladzie docelowym, z transformacja z cache providera."""
        return bbox_to_crs(
            bbox,
            target_crs,
            self._pinned(
                bbox.crs,
                target_crs,
                _ENVELOPE_POLICY,
                probe=_center_of(bbox),
            ),
        )

    def _apply_vertical_shift(self, path: Path) -> None:
        """Przelicz wartosci rastra przypieta operacja 8357->5621 (per piksel).

        Operacja pionowa wymaga wspolrzednych poziomych w kolejnosci
        (lon, lat, h) — always_xy=True, potwierdzone w rekonesansie (Zad. 1
        krok 7a; zamiana argumentow daje cichy blad ~0,44 m). Piksele nodata
        (oraz ewentualne NaN/inf) NIE sa transformowane — inaczej wartosc
        -9999 zostalaby przesunieta o offset i przestala byc rozpoznawana.

        Przeliczenie idzie pasami, wiec pracuje na KOPII tymczasowej i dopiero
        po pelnym sukcesie podmienia plik (`os.replace`) — inaczej awaria na
        pasie k zostawilaby pod docelowa nazwa raster o wymieszanych ukladach
        pionowych (pasy 0..k-1 w EVRF2007, reszta w Bpv), a `skip_existing`
        w DownloadManagerze utrwalilby taka korupcje. Przy bledzie znikaja
        zarowno kopia, jak i plik zrodlowy (wraz z towarzyszacym `.tfw`).
        """
        pinned = self._vertical_transform
        if pinned is None:  # pragma: no cover — wolane tylko dla EVRF2007
            return
        temp_path = path.with_name(
            f"{path.name}.{os.getpid()}_{threading.get_ident()}.vshift.tif"
        )
        try:
            shutil.copy2(path, temp_path)
            self._shift_in_place(temp_path, pinned, path.name)
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            path.with_suffix(".tfw").unlink(missing_ok=True)
            raise

    def _shift_in_place(self, path: Path, pinned: PinnedTransform, label: str) -> None:
        """Przelicz wysokosci pasami w podanym pliku (patrz _apply_vertical_shift).

        `label` to nazwa pliku DOCELOWEGO — komunikaty nie moga wskazywac na
        nazwe kopii tymczasowej, ktorej uzytkownik nigdy nie zobaczy.
        """
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                raise ValidationError(
                    f"Raster {label} nie ma CRS — nie da sie wyznaczyc "
                    f"(lon, lat) wymaganych przez operacje pionowa"
                )
            if ds.transform.is_identity or not ds.transform.is_rectilinear:
                raise ValidationError(
                    f"Raster {label} nie ma uzytecznej geotransformacji "
                    f"(jednostkowa/nieprostokatna) — nie da sie wyznaczyc "
                    f"(lon, lat) dla operacji pionowej"
                )
            bounds = ds.bounds
            horizontal = self._pinned(
                str(ds.crs),
                "EPSG:4326",
                _LONLAT_POLICY,
                probe=(
                    (bounds.left + bounds.right) / 2,
                    (bounds.bottom + bounds.top) / 2,
                ),
            )
            nodata = ds.nodata if ds.nodata is not None else CUZK_NODATA
            logger.debug(
                f"Transformacja pionowa {label}: {pinned.description} "
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


def bbox_to_crs(
    bbox: BBox, target_crs: str, pinned: PinnedTransform | None = None
) -> BBox:
    """Obwiednia bboxa w ukladzie docelowym przez operacje PRZYPIETA (ADR-024).

    Jedyne wejscie dla zadan opuszczajacych uklad czeski (i normalizacji
    zadan exportImage): wybiera operacje obwiedniowa (``_ENVELOPE_POLICY``
    z punktem kontrolnym w srodku bboxa), gdy wolajacy jej nie poda.
    Obwiednie z zageszczonych krawedzi liczy ``core.bbox.transform_bbox``
    (21 probek na krawedz) — obraz prostokata w innym ukladzie jest
    czworokatem o krzywych bokach.

    Funkcja modulowa (nie tylko metoda), bo warstwa CLI normalizuje bbox PRZED
    zbudowaniem nazwy pliku — nazwa musi niesc wspolrzedne faktycznie zadanego
    wycinka. Powtorna normalizacja w `download_bbox` jest wtedy strzezonym no-opem.
    """
    if pinned is None:
        pinned = build_pinned_transform(
            bbox.crs,
            target_crs,
            dataclasses.replace(_ENVELOPE_POLICY, probe_point=_center_of(bbox)),
        )
    return transform_bbox(bbox, target_crs, transformer=pinned)


def _center_of(bbox: BBox) -> tuple[float, float]:
    """Srodek bboxa — punkt kontrolny operacji obwiedniowej (uklad zrodlowy)."""
    return ((bbox.min_x + bbox.max_x) / 2, (bbox.min_y + bbox.max_y) / 2)


def _endpoint_for(
    channels: tuple[AccessChannel, ...], transport: TransportKind
) -> str | None:
    """Endpoint pierwszego kanalu danego transportu (None, gdy kanalu brak)."""
    return next(
        (ch.endpoint for ch in channels if ch.transport == transport and ch.endpoint),
        None,
    )


def _assign_crs(path: Path, crs: str) -> None:
    """Naprawa metadanych DMR4G-TIFF: wpisz CRS (georeferencja jest w .tfw).

    Lustro `_overwrite_crs` w client.py: cale cialo w try/except, bo
    uszkodzony TIFF z poprawnie rozpakowanego ZIP-a moze sprawic, ze
    rasterio zglosi niemapowany wyjatek (np. TypeError) zamiast
    (DownloadError, ValidationError) — bez przechwycenia taki wyjatek
    uciekalby poza `_cz_download_godlo`/`_run_cz` traceback'iem. Przy
    bledzie usuwany jest zarowno plik docelowy, jak i towarzyszacy .tfw,
    zeby `skip_existing` w kolejnym uruchomieniu nie utrwalil korupcji.
    """
    try:
        with rasterio.open(path, "r+") as ds:
            if ds.crs is None:
                logger.debug(f"{path.name}: brak CRS w GeoTIFF — wpisuje {crs}")
                ds.crs = CRS.from_string(crs)
    except Exception as e:
        path.unlink(missing_ok=True)
        path.with_suffix(".tfw").unlink(missing_ok=True)
        raise DownloadError(f"nie udalo sie wpisac CRS {crs} w {path}: {e}") from e
