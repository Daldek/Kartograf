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
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.transform import xy as _pixel_xy
from rasterio.warp import reproject
from rasterio.windows import Window

from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import detect_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.cuzk.client import CuzkClient, wkid
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

# Uklad, w ktorym CUZK TRZYMA dane rastrowe. Serwer dostaje zadania wylacznie
# w nim: reprojekcja serwerowa (`imageSR` != natywny) jest niewiarygodna —
# 5514->2180 gubi transformacje datum (blad 135 m), a 5514->3045 przesuwa
# tresc o 1,25 m na poludnie (pomiary 2026-08-11, ADR-024).
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
#    _WARP_MARGIN_PX (4 px = 8 m przy 2 m) — zmniejszajac ten zapas trzeba
#    zaostrzyc te polityke albo policzyc obwiednie ta sama operacja co warp.
# Siatki z CDN nie sa tu potrzebne (kosztuja ~2 s na pare ukladow), dlatego
# allow_network_grids=False.
_LONLAT_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
_ENVELOPE_POLICY = TransformPolicy(min_accuracy_m=2.0, allow_network_grids=False)
# Operacja reprojektujaca TRESC rastra — jedyna, ktora przesuwa piksele, wiec
# limit dokladnosci jest ostrzejszy niz dla obwiedni. Znane operacje z Krovaka
# do ukladow docelowych (2180, 3045) maja 0,5 m (KNOWN_PATHS).
_HORIZONTAL_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)
# Zapas obwiedni zadania natywnego w pikselach: pokrywa niepewnosc operacji
# obwiedniowej (<= 2 m) i halo interpolatora bilinear (1 px) na krawedziach.
_WARP_MARGIN_PX = 4

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
            NATIVE_CRS, target_crs, _HORIZONTAL_POLICY, probe=CZ_PROBE_NATIVE
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
        operacja. Powod jest empiryczny (pomiary 2026-08-11, ADR-024):
        ``exportImage&imageSR=2180`` gubi transformacje datum S-JTSK->ETRS89
        (tresc przesunieta o 135 m), a ``imageSR=3045`` przesuwa ja o 1,25 m —
        oba bledy sa niewidoczne w metadanych pliku, wiec jedyna obrona jest
        nieuzywanie tej sciezki.

        Kafelkowanie (limity ``exportImage``) i mozaikowanie dzieja sie po
        stronie ukladu natywnego, czyli PRZED warpem — szew kafli nie moze
        wiec zostac utrwalony przez interpolacje.
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
            _warp_to_grid(native_path, output_path, bbox, self._pixel_size, pinned)
        finally:
            native_path.unlink(missing_ok=True)

    def _native_request_bbox(self, bbox: BBox) -> BBox:
        """Obwiednia zadania natywnego: cel przeliczony do 5514 plus zapas."""
        native = self._bbox_to_crs(bbox, NATIVE_CRS)
        margin = _WARP_MARGIN_PX * self._pixel_size
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


@contextmanager
def _quiet_transformer_only_option():
    """Wycisz jeden komunikat GDAL: ``COORDINATE_OPERATION`` jest opcja
    TRANSFORMERA, a `rasterio.warp.reproject` podaje kwargs takze jako opcje
    warpera, ktory jej nie zna i zglasza `CPLE_NotSupported`. Operacja dziala
    (test `test_bbox_target_crs_puts_content_where_pyproj_says` to sprawdza na
    tresci), a ostrzezenie trafialoby na stderr kazdego pobrania CZ z
    reprojekcja. Filtr jest waski (dopasowanie po nazwie opcji) i zdejmowany
    natychmiast, wiec nie ukrywa innych bledow GDAL.
    """
    gdal_logger = logging.getLogger("rasterio._env")

    def _filter(record: logging.LogRecord) -> bool:
        return "COORDINATE_OPERATION" not in record.getMessage()

    gdal_logger.addFilter(_filter)
    try:
        yield
    finally:
        gdal_logger.removeFilter(_filter)


def _warp_to_grid(
    src_path: Path,
    dst_path: Path,
    bbox: BBox,
    pixel_size: float,
    pinned: PinnedTransform,
) -> None:
    """Zreprojektuj raster natywny na siatke ``bbox``/``pixel_size``.

    Operacja jest WYMUSZONA (`COORDINATE_OPERATION`) — bez tego GDAL wybiera
    ja sam, poza polityka `transform/crs.py` (zakaz ballparku, limit
    dokladnosci, probe). Siatka wyniku liczona jest identycznie jak w
    `CuzkClient.export_image`, wiec zasieg i rozmiar pliku nie zaleza od tego,
    czy po drodze byla reprojekcja.

    `src_nodata`/`dst_nodata` sprawiaja, ze GDAL maskuje piksele puste i nie
    wpuszcza `-9999` do interpolacji (zweryfikowane pomiarem i testem
    `test_nodata_does_not_bleed_into_interpolation`). Zapis jest atomowy:
    plik docelowy powstaje dopiero z gotowej kopii tymczasowej.
    """
    width = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
    height = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
    dst_transform = from_origin(bbox.min_x, bbox.max_y, pixel_size, pixel_size)
    tmp_path = dst_path.with_name(
        f"{dst_path.name}.{os.getpid()}_{threading.get_ident()}.warp.tif"
    )
    logger.debug(
        f"Reprojekcja lokalna {src_path.name} -> {bbox.crs}: "
        f"{pinned.description} (dokladnosc {pinned.accuracy_m} m)"
    )
    try:
        with rasterio.open(src_path) as src:
            profile = {
                "driver": "GTiff",
                "dtype": "float32",
                "count": 1,
                "width": width,
                "height": height,
                "crs": CRS.from_string(bbox.crs),
                "transform": dst_transform,
                "nodata": CUZK_NODATA,
            }
            with (
                rasterio.open(tmp_path, "w", **profile) as dst,
                _quiet_transformer_only_option(),
            ):
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_crs=CRS.from_string(NATIVE_CRS),
                    src_nodata=CUZK_NODATA,
                    dst_crs=CRS.from_string(bbox.crs),
                    dst_nodata=CUZK_NODATA,
                    resampling=Resampling.bilinear,
                    COORDINATE_OPERATION=pinned.gdal_operation(),
                )
        os.replace(tmp_path, dst_path)
    except BaseException:
        dst_path.unlink(missing_ok=True)
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


def bbox_to_crs(
    bbox: BBox, target_crs: str, pinned: PinnedTransform | None = None
) -> BBox:
    """Obwiednia bboxa w ukladzie docelowym (normalizacja zadan exportImage).

    Krawedzie sa probkowane (nie tylko naroza), bo obraz prostokata w innym
    ukladzie jest czworokatem o krzywych bokach — obwiednia z samych naroznikow
    potrafi uciac skrawek zadanego obszaru.

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
