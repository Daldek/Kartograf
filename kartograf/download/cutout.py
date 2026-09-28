"""
Scalony wycinek NMT PL w zadanym ukladzie (ADR-027) — warstwa biblioteczna.

Arkusze GUGiK pobierane sa normalnie do swoich segmentow (dzialaja jako
cache), mozaika jest przycinana do obszaru zadania rozszerzonego na zewnatrz
do siatki pikseli arkuszy (< 1 px; przy reprojekcji — z zapasem), a dla
ukladu innego niz EPSG:2180 tresc trafia na siatke wyniku lokalnym warpem
z WYMUSZONA operacja przypieta (ADR-024/027). Wynik to JEDEN GeoTIFF
``<output_dir>/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`` + sidecar.

CLI (``kartograf download --bbox/--geometry --target-crs``) jest nakladka na
ten modul: wypisuje komunikaty i tlumaczy wyjatki na kody wyjscia. Tu nie ma
``print`` ani argparse.

Przyklad::

    from kartograf import BBox, download_pl_cutout

    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        "EPSG:5514",
        output_dir="./data",
        max_workers=4,
    )
    print(result.path)
"""

import logging
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.core.sheet_parser import BBox, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, ProgressCallback
from kartograf.download.storage import FileStorage, prune_empty_dirs
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.transform.crs import PinnedTransform, TransformPolicy

logger = logging.getLogger(__name__)

# nodata arkuszy ASC GUGiK
PL_NODATA = -9999.0
# piksel siatki wyniku per rozdzielczosc NMT PL
PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}
# uklady docelowe z przypieta operacja EPSG:2180 -> cel (KNOWN_PATHS, ADR-027)
SUPPORTED_TARGET_CRS = ("EPSG:2180", "EPSG:5514", "EPSG:3045")
# Zapas obwiedni zrodla w pikselach — lustro _WARP_MARGIN_PX toru CZ
# (providers/cuzk/dmr.py): pokrywa niepewnosc operacji obwiedniowej i halo
# interpolatora bilinear (1 px) na krawedziach siatki wyniku.
WARP_MARGIN_PX = 4
# Polityka operacji reprojektujacej TRESC wycinka — lustro _HORIZONTAL_POLICY
# toru CZ; probe_point dokladany per zadanie (srodek bboxa).
_HORIZONTAL_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)
# uklady czeskie opuszczamy wylacznie przypieta operacja (ADR-024)
_CZ_CRS = frozenset({"EPSG:5514", "EPSG:3045"})
_VERTICAL_CRS = ("EVRF2007", "KRON86")
# Dolne oszacowanie rozmiaru arkusza ASC na dysku: 5,74-7,95 B na wartosc
# w realnych plikach GUGiK 5 m (fakt 9 planu 2026-09-28) — bierzemy mniej,
# zeby kontrola nie odrzucala zadan, ktore sie zmieszcza.
_ASC_BYTES_PER_VALUE = 5.5


@dataclass(frozen=True)
class PlCutout:
    """Przygotowany (fail-fast, bez sieci) wycinek NMT PL."""

    target_crs: str
    resolution: str
    vertical_crs: str  # FAKTYCZNY pion (po regule 5m => EVRF2007)
    output_dir: Path
    bbox_2180: BBox  # dokladne zadanie w EPSG:2180
    bbox_source_2180: BBox  # zadanie + zapas na warp: selekcja arkuszy i crop mozaiki
    bbox_target: BBox  # siatka wyniku (uklad docelowy)
    pinned: PinnedTransform | None  # None dla EPSG:2180 (sam crop)
    target_path: Path

    @property
    def pixel_size(self) -> float:
        """Piksel siatki wyniku (m)."""
        return PIXEL_SIZES[self.resolution]

    @property
    def grid_shape(self) -> tuple[int, int]:
        """(wysokosc, szerokosc) siatki wyniku w pikselach — jak w ``warp_to_grid``."""
        b, px = self.bbox_target, self.pixel_size
        return (
            max(1, round((b.max_y - b.min_y) / px)),
            max(1, round((b.max_x - b.min_x) / px)),
        )

    @property
    def estimated_bytes(self) -> int:
        """Rozmiar wyniku float32 bez kompresji (bajty)."""
        height, width = self.grid_shape
        return height * width * 4


@dataclass(frozen=True)
class PlCutoutSheets:
    """Arkusze do pobrania dla wycinka (godla w skali selekcji)."""

    godla: tuple[str, ...]


@dataclass(frozen=True)
class PlCutoutResult:
    """Wynik ``run_pl_cutout`` / ``download_pl_cutout``."""

    path: Path
    skipped: bool = False  # plik juz istnial (force=False) — bez sieci
    sheet_paths: tuple[Path, ...] = ()  # arkusze uzyte do mozaiki
    missing_sheets: tuple[str, ...] = ()  # arkusze bez danych GUGiK (R5) -> nodata


def _bbox_to_2180(bbox: BBox) -> BBox:
    """Zadanie w EPSG:2180: uklady czeskie przypieta operacja, reszta jak dotad.

    Uklady PL/WGS84 — swiadomie domyslny transformer, jak w calym przeplywie PL.
    CLI podaje tu bbox juz po ``_country_bbox``, ktory opuszcza uklady czeskie
    przypieta operacja; galaz czeska dotyczy wiec wywolan bibliotecznych.
    Etykieta ukladu jest porownywana bez wielkosci liter i spacji: doslowne
    porownanie puszczalo ``"epsg:5514"`` domyslnym transformerem (obok
    ADR-024, finalny review fali, m-2).
    """
    crs = bbox.crs.strip().upper()
    if crs == "EPSG:2180":
        # etykieta kanoniczna, jak dotad z transformacji tozsamosciowej
        return bbox._replace(crs=crs)
    if crs in _CZ_CRS:
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        return bbox_to_crs(bbox, "EPSG:2180")
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox

    return _transform_bbox(
        bbox.min_x,
        bbox.min_y,
        bbox.max_x,
        bbox.max_y,
        CRS.from_user_input(bbox.crs),
        "EPSG:2180",
    )


def prepare_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
) -> PlCutout:
    """Fail-fast przygotowanie wycinka: operacja, bboxy i sciezka wyniku.

    Zero sieci. ``TransformError``, gdy dla pary EPSG:2180 -> ``target_crs``
    nie ma przypietej operacji (ADR-024/027); ``ValidationError`` na zle
    parametry. ``vertical_crs`` to pion FAKTYCZNY: przy 5m tylko EVRF2007
    (``download_pl_cutout`` stosuje regule fabryki providera sam).

    Wycinek jest zawsze GeoTIFF (``.tif``) — ``default_extension``
    deskryptora (``.asc``) dotyczy arkuszy, nie wycinka.
    """
    if target_crs not in SUPPORTED_TARGET_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka PL: {target_crs} "
            f"(dostepne: {', '.join(SUPPORTED_TARGET_CRS)})"
        )
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    if resolution == "5m" and vertical_crs != "EVRF2007":
        raise ValidationError("NMT 5m jest dostepny wylacznie w EVRF2007")

    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_source

    # import lokalny: testy podmieniaja operacje w module transform.crs
    from kartograf.transform.crs import build_pinned_transform

    bbox_2180 = _bbox_to_2180(bbox)
    pinned = None
    bbox_target = bbox_2180
    bbox_source_2180 = bbox_2180
    if target_crs != "EPSG:2180":
        center = (
            (bbox_2180.min_x + bbox_2180.max_x) / 2,
            (bbox_2180.min_y + bbox_2180.max_y) / 2,
        )
        # polityka jak _HORIZONTAL_POLICY toru CZ + probe w srodku zadania
        pinned = build_pinned_transform(
            "EPSG:2180", target_crs, replace(_HORIZONTAL_POLICY, probe_point=center)
        )
        bbox_target = bbox_to_crs(bbox_2180, target_crs, pinned)
        # Zrodlo musi pokryc CALA siatke wyniku: obwiednia celu wraca do 2180
        # wieksza niz zadanie (obrot ukladu), a interpolator potrzebuje halo.
        # Lustro _native_request_bbox toru CZ. Bez `pinned` — operacja
        # przypieta jest KIERUNKOWA (2180 -> target), tak samo robi CZ.
        back = bbox_to_crs(bbox_target, "EPSG:2180")
        margin = WARP_MARGIN_PX * PIXEL_SIZES[resolution]
        bbox_source_2180 = BBox(
            back.min_x - margin,
            back.min_y - margin,
            back.max_x + margin,
            back.max_y + margin,
            "EPSG:2180",
        )

    key = "pl.gugik.nmt_5m" if resolution == "5m" else "pl.gugik.nmt_1m"
    subdir = get_source(key).resolve_subdir(uklad="1992", vertical_crs=vertical_crs)
    coords = "_".join(
        format(v, ".10g")
        for v in (
            bbox_target.min_x,
            bbox_target.min_y,
            bbox_target.max_x,
            bbox_target.max_y,
        )
    )
    return PlCutout(
        target_crs=target_crs,
        resolution=resolution,
        vertical_crs=vertical_crs,
        output_dir=Path(output_dir),
        bbox_2180=bbox_2180,
        bbox_source_2180=bbox_source_2180,
        bbox_target=bbox_target,
        pinned=pinned,
        target_path=Path(output_dir) / subdir / "bbox" / f"{coords}.tif",
    )


def select_pl_cutout_sheets(
    cutout: PlCutout,
    *,
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
) -> PlCutoutSheets:
    """Arkusze wycinka (zero sieci).

    Tryb bbox: arkusze obwiedni zrodla (zadanie + zapas) powiekszonej o 1
    piksel — crop mozaiki jest przyciagany NA ZEWNATRZ do siatki arkuszy
    (< 1 px, ``build_pl_cutout``). Tryb geometrii: arkusze per obiekt, a przy
    warpie SUMA z arkuszami tej samej powiekszonej obwiedni zrodla (R-01:
    wynik obejmuje CALA obwiednie, bez maskowania do obiektow — bez sumy na
    krawedziach zostawalaby ramka nodata; ARCHITECTURE 4.3). Koszt jest
    swiadomy: dla rzadkiej geometrii wieloobiektowej suma obejmuje arkusze
    calej obwiedni, takze tam, gdzie nie ma zadnego obiektu.
    """
    px = cutout.pixel_size
    src = cutout.bbox_source_2180
    # Crop przyciagany jest NA ZEWNATRZ do siatki arkuszy (< 1 px): selekcja
    # z zapasem 1 px, zeby brzegowy piksel nie wpadl w arkusz spoza listy.
    selection = BBox(
        src.min_x - px, src.min_y - px, src.max_x + px, src.max_y + px, "EPSG:2180"
    )
    if geometry is None:
        godla = find_sheets_for_bbox(selection, scale, system="1992")
        what = "bbox"
    else:
        from kartograf.core.geometry import find_sheets_for_geometry

        godla = find_sheets_for_geometry(
            Path(geometry), target_scale=scale, layer=layer, system="1992"
        )
        if cutout.pinned is not None:
            godla = sorted(
                set(godla) | set(find_sheets_for_bbox(selection, scale, system="1992"))
            )
        what = "geometry"
    if not godla:
        raise ValidationError(f"No sheets found for the given {what}")
    return PlCutoutSheets(godla=tuple(godla))


# x >= 1 000 000 m to wspolrzedne strefowe PL-2000 (strefa = cyfra milionow,
# EPSG:2176-2179 dla stref 5-8); PUWG 1992 miesci sie ponizej.
_PL2000_MIN_X = 1_000_000.0


def _reject_pl2000_sheets(sheet_paths: list[Path]) -> None:
    """Glosny blad zamiast cichej dziury (fakt 7 planu 2026-09-28).

    Skorowidz GUGiK potrafi zwrocic dla godla PL-1992 arkusz nowszej kampanii
    w ukladzie PL-2000 (fallback URL w ``GugikProvider._get_opendata_url``).
    Mozaika wymusza EPSG:2180, wiec taki arkusz wyladowalby poza obszarem
    i ``merge`` pominalby go bez slowa. Reprojekcja takich arkuszy to etap 2.
    """
    import rasterio

    foreign: list[tuple[Path, int]] = []
    for path in sheet_paths:
        with rasterio.open(path) as src:
            if src.bounds.left >= _PL2000_MIN_X:
                foreign.append((Path(path), int(src.bounds.left // 1_000_000)))
    if foreign:
        listing = ", ".join(
            f"{p.name} (strefa {zone}, EPSG:{2171 + zone})" for p, zone in foreign[:5]
        )
        raise ValidationError(
            f"{len(foreign)} arkusz(y) ma wspolrzedne PL-2000 zamiast PL-1992: "
            f"{listing}{' ...' if len(foreign) > 5 else ''} — skorowidz GUGiK "
            "wydal dla godla PL-1992 arkusz ukladu 2000 i wycinek pominalby go po "
            "cichu (dziura nodata). Wycinek z takich arkuszy to etap 2; pobierz "
            "obszar jako arkusze (bez --target-crs), np. z --system 2000."
        )


def build_pl_cutout(
    sheet_paths: list[Path],
    crop_bbox_2180: BBox,
    bbox_target: BBox,
    pixel_size: float,
    pinned: PinnedTransform | None,
    target_path: Path,
) -> None:
    """Zszyj arkusze, przytnij do ``crop_bbox_2180``; opcjonalny lokalny warp.

    ``crop_bbox_2180`` to obwiednia ZRODLA (przy warpie: zadanie + zapas),
    nie dokladne zadanie. ``pinned is None`` = cel EPSG:2180: sam crop
    (atomowy ``os.replace``). Obie sciezki zapisu sa atomowe (druga domyka
    wewnetrzny ``os.replace`` w ``warp_to_grid``), wiec przerwana budowa NIE
    zostawia polzapisanego pliku pod ``target_path`` — i nie kasuje
    poprzedniego wyniku.

    Siatka arkuszy (R1): crop jest rozszerzany NA ZEWNATRZ do pelnych pikseli
    siatki arkuszy (wiekszosci; < 1 px na strone), wiec przy celu EPSG:2180
    wartosci przechodza 1:1, bez przeprobkowania, a warp dostaje tresc bez
    przesuniecia o ulamek piksela. Arkusz spoza siatki wiekszosci nie
    przerywa budowy — ostrzezenie w logu, jego tresc idzie najblizszym
    sasiadem (``mosaic_and_crop``). Kazdy arkusz jest owijany w VRT z jawnym
    EPSG:2180 i pasmem Float32: arkusz z ``.prj`` (np. dopisanym przez
    Hydrograf) scala sie z arkuszem bez niego (dotad blad ``niezgodne CRS
    wejsc``), a arkusz z samymi liczbami calkowitymi (GDAL czyta go jako
    Int32) nie obcina wysokosci pozostalych. Wejscia sa sortowane: ``merge``
    bierze profil wyniku z pierwszego zrodla, a pierwsze zrodlo wygrywa
    w zakladce, wiec wynik nie zalezy od kolejnosci listy (pobieranie
    rownolegle zwraca arkusze w kolejnosci ukonczenia). Wynik mozaiki to
    GTiff z EPSG:2180.

    Arkusz we wspolrzednych PL-2000 (``x >= 1 000 000``) konczy sie
    ``ValidationError`` PRZED mozaika (``_reject_pl2000_sheets``) — inaczej
    ``merge`` pominalby go po cichu i w wyniku zostalaby dziura nodata.

    Plik POSREDNI mozaiki (``tmp``) jest kompresowany (deflate, predyktor 3,
    kafle 512 px, BIGTIFF=IF_SAFER) WYLACZNIE gdy ``pinned is not None``: warp
    go potem czyta raz i kasuje, wiec kompresja placi sie miejscem na dysku
    bez kosztu czytelnosci. Przy celu EPSG:2180 ten sam plik JEST wynikiem
    (``os.replace`` na ``target_path``), wiec zostaje bez kompresji — jak
    dotad (zn. 9 fali review max).
    """
    _reject_pl2000_sheets(sheet_paths)
    from kartograf.transport.mosaic import mosaic_and_crop

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(
        f"{target_path.name}.{os.getpid()}_{threading.get_ident()}.mosaic.tif"
    )
    dst_kwds: dict = {"driver": "GTiff", "crs": "EPSG:2180"}
    if pinned is not None:
        # Plik POSREDNI (warp czyta go raz i kasuje): deflate + predyktor
        # zmiennoprzecinkowy daje 2-3x mniej dla NMT. Kafle 512 px — profil
        # AAIGrid ma blockysize=1, a tiled bez rozmiarow konczy sie
        # RasterBlockError; BIGTIFF=IF_SAFER, bo przy kompresji GDAL nie zna
        # rozmiaru z gory (fakt 10 planu 2026-09-28).
        dst_kwds.update(
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=512,
            blockysize=512,
            bigtiff="IF_SAFER",
        )
    try:
        mosaic_and_crop(
            sorted(Path(p) for p in sheet_paths),
            crop_bbox_2180,
            tmp,
            nodata=PL_NODATA,
            dst_kwds=dst_kwds,
            # siatka arkuszy (R1), arkusze w VRT: EPSG:2180 + Float32 — fakty 1-2, 5-6
            snap_to_source_grid=True,
            assign_crs="EPSG:2180",
            dtype="float32",
        )
        if pinned is None:
            os.replace(tmp, target_path)
        else:
            from kartograf.transform.raster import warp_to_grid

            warp_to_grid(
                tmp,
                target_path,
                bbox_target,
                pixel_size,
                pinned,
                src_crs="EPSG:2180",
                nodata=PL_NODATA,
            )
    finally:
        tmp.unlink(missing_ok=True)


def write_pl_cutout_sidecar(
    cutout: PlCutout,
    *,
    parent_request: dict | None = None,
    missing_sheets: tuple[str, ...] = (),
) -> None:
    """Best-effort sidecar wycinka (blad nie przerywa pobrania).

    ``capability="sheet_files"``: dane pochodza z arkuszy OpenData — kanal
    ``bbox_raster`` nie istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86
    (ADR-027, odstepstwo od litery spec 6.1 pkt 5). ``missing_sheets``
    (niepuste) -> ``extra.missing_sheets``: arkusze bez danych GUGiK (R5).
    """
    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        key = "pl.gugik.nmt_5m" if cutout.resolution == "5m" else "pl.gugik.nmt_1m"
        b = cutout.bbox_target
        extra: dict = {}
        if parent_request:
            extra["parent_request"] = parent_request
        if missing_sheets:
            # R5: arkusze, dla ktorych GUGiK nie ma danych — tam wycinek ma nodata
            extra["missing_sheets"] = list(missing_sheets)
        meta = build_metadata(
            get_source(key),
            request={
                "bbox": [b.min_x, b.min_y, b.max_x, b.max_y],
                "bbox_crs": cutout.target_crs,
            },
            vertical_crs=cutout.vertical_crs,
            capability="sheet_files",
            nodata=PL_NODATA,
            extra=extra or None,
        )
        meta.horizontal_crs = cutout.target_crs
        pinned = cutout.pinned
        meta.transform = (
            {"horizontal": f"pinned: {pinned.description} ({pinned.accuracy_m} m)"}
            if pinned is not None
            else None
        )
        write_sidecar(cutout.target_path, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logger.warning(f"Nie udalo sie zapisac sidecara dla {cutout.target_path}: {e}")


def _require_matching_provider(cutout: PlCutout, provider) -> None:
    """Wstrzykniety provider musi dostarczac pion i rozdzielczosc wycinka.

    Segment arkuszy (wspolny cache) i sidecar wycinka biora pion
    i rozdzielczosc z ``cutout``, a dane z providera — rozjazd zapisalby np.
    wysokosci KRON86 do segmentu ``..._evrf2007`` (albo arkusze 5 m do
    segmentu 1 m), a kolejne przebiegi ze ``skip_existing`` uzylyby ich bez
    ostrzezenia. ``isinstance(str)`` jak w ``DownloadManager``: atrybut
    nieobecny albo niebedacy napisem (np. Mock) nie jest porownywany.
    """
    for attr in ("vertical_crs", "resolution"):
        actual = getattr(provider, attr, None)
        expected = getattr(cutout, attr)
        if isinstance(actual, str) and actual != expected:
            raise ValidationError(
                f"Provider niezgodny z wycinkiem: {attr} providera {actual}, "
                f"wycinka {expected} — przygotuj wycinek (prepare_pl_cutout) "
                "z pionem i rozdzielczoscia providera"
            )


def estimate_pl_cutout_bytes(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> tuple[int, int]:
    """(bajty, liczba arkuszy do pobrania) — DOLNE oszacowanie potrzeb dysku.

    Wynik float32 bez kompresji + arkusze jeszcze nie pobrane po 5,5 B na
    wartosc. Plik posredni mozaiki (skompresowany) i narzut systemu plikow NIE
    sa liczone: to kontrola "na pewno nie wystarczy", nie gwarancja.
    """
    from kartograf.core.sheet_parser import SheetParser

    storage = storage or FileStorage(
        cutout.output_dir,
        resolution=cutout.resolution,
        vertical_crs=cutout.vertical_crs,
    )
    px = cutout.pixel_size
    need = cutout.estimated_bytes
    pending = 0
    for leaf in DownloadManager.expand_sheets(list(sheets.godla)):
        if storage.get_path(leaf, ".asc").exists():
            continue
        pending += 1
        frame = SheetParser(leaf).get_bbox("EPSG:2180")
        need += int(
            (frame.max_x - frame.min_x)
            * (frame.max_y - frame.min_y)
            / (px * px)
            * _ASC_BYTES_PER_VALUE
        )
    return need, pending


def check_pl_cutout_disk_space(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> None:
    """``ValidationError``, gdy na dysku NA PEWNO zabraknie miejsca (przed siecia)."""
    import shutil

    need, pending = estimate_pl_cutout_bytes(cutout, sheets, storage=storage)
    probe = cutout.target_path.parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        height, width = cutout.grid_shape
        raise ValidationError(
            f"Za malo miejsca na dysku dla wycinka: potrzeba co najmniej "
            f"~{need / 2**30:.1f} GiB (siatka {width} x {height} px float32 + "
            f"{pending} arkuszy do pobrania), wolne ~{free / 2**30:.1f} GiB w {probe}"
        )


def run_pl_cutout(
    cutout: PlCutout,
    sheets: PlCutoutSheets,
    *,
    provider=None,
    storage: FileStorage | None = None,
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
) -> PlCutoutResult:
    """Pobierz arkusze, zbuduj wycinek, zapisz sidecar.

    ``force=False`` + istniejacy plik wyniku -> ``skipped=True`` bez sieci.
    Arkusze z cache sa uzywane ponownie (``skip_existing = not force``).
    Brak danych u zrodla (``NoCoverageError``) -> nodata + ``missing_sheets``;
    kazda inna porazka pobrania arkusza (``DownloadError``) -> ``DownloadError``;
    gdy ZADEN arkusz nie ma danych -> ``ValidationError``. Oba bledy padaja,
    zanim cokolwiek zostanie zbudowane. Inny wyjatek arkusza (np. ``OSError``
    zapisu) przy ``max_workers=1`` wylatuje stad bez zmian, a w puli watkow
    liczy sie jak porazka pobrania (``DownloadError``). ``provider`` i
    ``storage`` domyslnie z fabryki NMT i ``FileStorage`` segmentu arkuszy
    (CLI wstrzykuje wlasne). Wstrzykniety ``provider`` musi dostarczac pion
    i rozdzielczosc wycinka — inaczej ``ValidationError`` przed jakimkolwiek
    pobraniem. Kontrola miejsca na dysku (``check_pl_cutout_disk_space``)
    biegnie PRZED ``DownloadManager`` — dolne oszacowanie, nie gwarancja
    (zn. 9 fali review max).
    """
    if provider is not None:
        _require_matching_provider(cutout, provider)
    if not force and cutout.target_path.exists():
        return PlCutoutResult(path=cutout.target_path, skipped=True)
    if provider is None:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=cutout.vertical_crs, resolution=cutout.resolution
        )
    if storage is None:
        storage = FileStorage(
            cutout.output_dir,
            resolution=cutout.resolution,
            vertical_crs=cutout.vertical_crs,
        )
    check_pl_cutout_disk_space(cutout, sheets, storage=storage)
    manager = DownloadManager(
        output_dir=cutout.output_dir,
        provider=provider,
        storage=storage,
        vertical_crs=cutout.vertical_crs,
        resolution=cutout.resolution,
        max_workers=max_workers,
        sidecar_extra={"parent_request": parent_request} if parent_request else None,
    )
    sheet_paths = manager.download_sheets(
        list(sheets.godla), skip_existing=not force, on_progress=on_progress
    )
    summary = manager.last_result
    failed = list(summary.failed) if summary is not None else []
    no_data = set(summary.no_coverage) if summary is not None else set()
    fatal = [g for g in failed if g not in no_data]
    missing = tuple(sorted(g for g in failed if g in no_data))
    if fatal:
        # R5: tylko brak danych u zrodla bywa nodata. Kazda inna porazka
        # (siec, serwer, niepelna odpowiedz skorowidza) konczy zadanie — chwilowy
        # blad nie moze zostawic trwalej dziury w pliku, ktory potem jest
        # pomijany jako istniejacy.
        total = summary.total if summary is not None else len(failed)
        raise DownloadError(
            f"{len(fatal)} z {total} arkuszy nie pobrano (blad pobrania, nie brak "
            f"danych): {', '.join(fatal)} — wycinek nie powstal; ponow pobranie"
        )
    if not sheet_paths:
        raise ValidationError(
            f"GUGiK nie ma danych dla zadnego z {len(missing)} arkuszy obszaru "
            "— wycinek nie powstal"
        )
    if missing:
        # info, nie warning: komunikat dla uzytkownika wypisuje CLI, a dane
        # niesie wynik (missing_sheets) i sidecar
        logger.info(
            f"Brak danych GUGiK dla {len(missing)} arkuszy wycinka: "
            f"{', '.join(missing)}"
        )
    try:
        build_pl_cutout(
            list(sheet_paths),
            cutout.bbox_source_2180,
            cutout.bbox_target,
            cutout.pixel_size,
            cutout.pinned,
            cutout.target_path,
        )
    except BaseException:
        # zn. 10: nieudana budowa nie zostawia pustego drzewa <segment>/bbox/
        # (katalog z poprzednim wynikiem nie jest pusty — zostaje)
        prune_empty_dirs(cutout.target_path.parent, cutout.output_dir)
        raise
    write_pl_cutout_sidecar(
        cutout, parent_request=parent_request, missing_sheets=missing
    )
    return PlCutoutResult(
        path=cutout.target_path,
        sheet_paths=tuple(sheet_paths),
        missing_sheets=missing,
    )


def download_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
) -> PlCutoutResult:
    """Jeden scalony GeoTIFF NMT PL w ``target_crs`` dla bboxa albo geometrii.

    Tryb geometrii: ``bbox`` to obwiednia geometrii (np.
    ``get_overall_bbox(path, target_crs="EPSG:2180")``), ``geometry`` — plik
    SHP/GPKG wyznaczajacy arkusze per obiekt (R-01 przy warpie). Regula
    fabryki NMT: 5m => EVRF2007 (z ostrzezeniem w logu).
    """
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    from kartograf.providers.pl import create_nmt_provider

    provider = create_nmt_provider(vertical_crs=vertical_crs, resolution=resolution)
    cutout = prepare_pl_cutout(
        bbox,
        target_crs,
        output_dir=output_dir,
        resolution=resolution,
        vertical_crs=provider.vertical_crs,
    )
    if not force and cutout.target_path.exists():
        return PlCutoutResult(path=cutout.target_path, skipped=True)
    sheets = select_pl_cutout_sheets(
        cutout, geometry=geometry, layer=layer, scale=scale
    )
    return run_pl_cutout(
        cutout,
        sheets,
        provider=provider,
        max_workers=max_workers,
        force=force,
        on_progress=on_progress,
        parent_request=parent_request,
    )
