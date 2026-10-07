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

import functools
import json
import logging
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.core.sheet_parser import BBox, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, ProgressCallback
from kartograf.download.storage import (
    FileStorage,
    bbox_cutout_path,
    prune_empty_dirs,
    storage_for_provider,
)
from kartograf.exceptions import DownloadError, GridMismatchError, ValidationError
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
    """Wynik ``run_pl_cutout`` / ``download_pl_cutout``.

    Przy ``skipped=True`` (plik istnial, ``force=False``) ``missing_sheets``,
    ``off_grid_sheets``, ``partial_sheets`` i ``all_nodata`` pochodza
    z sidecara istniejacego wycinka (``skipped_pl_cutout``; raster nie jest
    czytany ponownie), a ``sheet_paths`` jest puste — arkuszy nikt nie
    dotykal.
    """

    path: Path
    skipped: bool = False  # plik juz istnial (force=False) — bez sieci
    sheet_paths: tuple[Path, ...] = ()  # arkusze uzyte do mozaiki
    missing_sheets: tuple[str, ...] = ()  # arkusze bez danych GUGiK (R5) -> nodata
    # arkusze o innej fazie siatki niz reszta, reprojektowane osobno (W1, S5)
    off_grid_sheets: tuple[str, ...] = ()
    # wycinek bez ani jednego waznego piksela (N2): pobrane arkusze leza w
    # marginesie selekcji albo same sa nodata — plik powstal, kod 0 w CLI
    all_nodata: bool = False
    # arkusze z niepelnej najnowszej kampanii (rekord skorowidza
    # ``full_sheet=False``, E13) — wybrane wg ADR-028, ale moga wnosic nodata
    partial_sheets: tuple[str, ...] = ()


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
    from kartograf.providers.pl import nmt_vertical_crs

    if nmt_vertical_crs(resolution, vertical_crs, log=False) != vertical_crs:
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
    return PlCutout(
        target_crs=target_crs,
        resolution=resolution,
        vertical_crs=vertical_crs,
        output_dir=Path(output_dir),
        bbox_2180=bbox_2180,
        bbox_source_2180=bbox_source_2180,
        bbox_target=bbox_target,
        pinned=pinned,
        target_path=bbox_cutout_path(output_dir, subdir, bbox_target, ".tif"),
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

    Do 0.7.0 skorowidz GUGiK potrafil wydac dla godla PL-1992 arkusz nowszej
    kampanii w ukladzie PL-2000 (cichy fallback URL bez godla, usuniety razem
    z K4 — ``select_sheet_record`` odrzuca rekord innego ukladu). Straz zostaje
    dla arkuszy z cache pobranych wczesniejsza wersja: mozaika wymusza
    EPSG:2180, wiec taki arkusz wyladowalby poza obszarem i ``merge``
    pominalby go bez slowa. Reprojekcja takich arkuszy to etap 2.
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
        paths = ", ".join(str(p) for p, _ in foreign)
        raise ValidationError(
            f"{len(foreign)} arkusz(y) ma wspolrzedne PL-2000 zamiast PL-1992: "
            f"{listing}{' ...' if len(foreign) > 5 else ''} — plik pochodzi "
            "z wczesniejszej wersji Kartografa (cichy fallback skorowidza, "
            "usuniety w 0.7.0) i wycinek pominalby go po cichu (dziura nodata). "
            f"Usun go i ponow pobranie: {paths}"
        )


def build_pl_cutout(
    sheet_paths: list[Path],
    crop_bbox_2180: BBox,
    bbox_target: BBox,
    pixel_size: float,
    pinned: PinnedTransform | None,
    target_path: Path,
) -> tuple[str, ...]:
    """Zszyj arkusze, przytnij do ``crop_bbox_2180``; opcjonalny lokalny warp.

    ``crop_bbox_2180`` to obwiednia ZRODLA (przy warpie: zadanie + zapas),
    nie dokladne zadanie. ``pinned is None`` = cel EPSG:2180: sam crop
    (atomowy ``os.replace``). Obie sciezki zapisu sa atomowe (druga domyka
    wewnetrzny ``os.replace`` w ``warp_to_grid``), wiec przerwana budowa NIE
    zostawia polzapisanego pliku pod ``target_path`` — i nie kasuje
    poprzedniego wyniku. Zwraca godla arkuszy reprojektowanych osobno (W1,
    nizej) — pusta krotke na sciezce mozaiki.

    Siatka arkuszy (R1): crop jest rozszerzany NA ZEWNATRZ do pelnych pikseli
    siatki arkuszy (wiekszosci; < 1 px na strone), wiec przy celu EPSG:2180
    wartosci przechodza 1:1, bez przeprobkowania, a warp dostaje tresc bez
    przesuniecia o ulamek piksela. Fazy siatki sprawdza ``check_source_grid``
    PRZED mozaika (S5: arkusze 5 m kampanii 2022 pod Krakowem maja kazdy inna
    faze; 1 m — jedna faza), bo ``merge`` przepisuje arkusz spoza siatki
    "przez okno" — nie zawsze z najblizszego piksela i z kolumna/wierszem
    nodata na szwie:

    - cel EPSG:2180 (``pinned is None``) i arkusz spoza siatki ->
      ``GridMismatchError`` (D3): wartosci 1:1 sa niemozliwe, a wycinek
      z warpem albo same arkusze sa dostepne bez sieci (arkusze zostaja
      w cache);
    - warp (``pinned``) i arkusz spoza siatki -> **W1** (D8):
      ``warp_to_grid`` dostaje LISTE arkuszy i reprojektuje kazdy RAZ, z jego
      wlasnej siatki na siatke wyniku (bez mozaiki posredniej); szwy to
      niezalezne warpy (interpolator nie widzi sasiada zza szwu), w zakladce
      wygrywa pierwszy w sortowaniu — jak w ``merge``;
    - jedna faza -> mozaika 1:1 (+ warp) jak dotad (zweryfikowana na zywo
      bit w bit; ARCHITECTURE 4.3).

    Na sciezce mozaiki kazdy arkusz jest owijany w VRT z jawnym EPSG:2180
    i pasmem Float32: arkusz z ``.prj`` (np. dopisanym przez Hydrograf) scala
    sie z arkuszem bez niego (dotad blad ``niezgodne CRS wejsc``), a arkusz
    z samymi liczbami calkowitymi (GDAL czyta go jako Int32) nie obcina
    wysokosci pozostalych. Wejscia sa sortowane: ``merge`` bierze profil
    wyniku z pierwszego zrodla, a pierwsze zrodlo wygrywa w zakladce, wiec
    wynik nie zalezy od kolejnosci listy (pobieranie rownolegle zwraca
    arkusze w kolejnosci ukonczenia). Wynik mozaiki to GTiff z EPSG:2180.

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
    from kartograf.transport.mosaic import check_source_grid, mosaic_and_crop

    paths = sorted(Path(p) for p in sheet_paths)
    grid = check_source_grid(paths)
    if grid.off_grid:
        if pinned is None:
            raise GridMismatchError(
                grid.describe_off_grid(len(paths), "arkuszy")
                + " — wycinek EPSG:2180 wymaga wspolnej siatki (wartosci 1:1). "
                "Zadaj wycinek w ukladzie z pelnym warpem (--target-crs "
                "EPSG:5514 albo EPSG:3045) albo pobierz obszar jako arkusze "
                "(bez --target-crs). Arkusze zostaja w cache.",
                grid.off_grid,
            )
        from kartograf.transform.raster import warp_to_grid

        # W1: kazdy arkusz ze swojej siatki prosto na siatke wyniku.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        warp_to_grid(
            paths,
            target_path,
            bbox_target,
            pixel_size,
            pinned,
            src_crs="EPSG:2180",
            nodata=PL_NODATA,
        )
        return tuple(sorted(s.path.stem for s in grid.off_grid))

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
            paths,
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
    return ()


def _sheet_source(sheet_path: Path) -> dict:
    """Pochodzenie arkusza z jego sidecara (``extra.source``), best-effort."""
    entry: dict = {
        "godlo": sheet_path.stem,
        "url": None,
        "layer": None,
        "aktualnosc": None,
        "full_sheet": None,
    }
    sidecar = sheet_path.parent / f"{sheet_path.name}.meta.json"
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        source = meta["extra"]["source"]
    except (OSError, ValueError, KeyError, TypeError):
        return entry  # arkusz bez sidecara (cache sprzed 0.7.0) albo bez source
    request_godlo = meta.get("request", {}).get("godlo")
    if isinstance(request_godlo, str):
        entry["godlo"] = request_godlo
    for key in ("url", "layer", "aktualnosc", "full_sheet"):
        entry[key] = source.get(key)
    return entry


def _partial_sheets(sources: list) -> tuple[str, ...]:
    """Godla wpisow ``sheet_sources`` z ``full_sheet is False`` (E13).

    ``None`` (arkusz bez sidecara albo rekord bez flagi) nie jest niepelny —
    ostrzegamy tylko o tym, co skorowidz jawnie deklaruje.
    """
    return tuple(
        sorted(
            str(entry.get("godlo"))
            for entry in sources
            if isinstance(entry, dict) and entry.get("full_sheet") is False
        )
    )


def write_pl_cutout_sidecar(
    cutout: PlCutout,
    *,
    parent_request: dict | None = None,
    missing_sheets: tuple[str, ...] = (),
    sheet_paths: tuple[Path, ...] = (),
    off_grid_sheets: tuple[str, ...] = (),
    all_nodata: bool = False,
) -> None:
    """Best-effort sidecar wycinka (blad nie przerywa pobrania).

    ``capability="sheet_files"``: dane pochodza z arkuszy OpenData — kanal
    ``bbox_raster`` nie istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86
    (ADR-027, odstepstwo od litery spec 6.1 pkt 5). ``missing_sheets``
    (niepuste) -> ``extra.missing_sheets``: arkusze bez danych GUGiK (R5).
    ``sheet_paths`` (niepuste) -> ``extra.sheet_sources``: pochodzenie
    kazdego arkusza mozaiki ``{godlo, url, layer, aktualnosc, full_sheet}``
    (``full_sheet`` = flaga pelnego arkusza z rekordu skorowidza, E13) czytane
    z sidecarow arkuszy (``extra.source``, D5); arkusz bez sidecara albo bez
    ``source`` (cache sprzed 0.7.0) ma ``null`` w polach poza ``godlo``.
    ``off_grid_sheets`` (niepuste) -> ``extra.off_grid_sheets``: arkusze
    o innej fazie siatki niz reszta, reprojektowane osobno (W1, S5) —
    konsument widzi, ze szwy wycinka powstaly z niezaleznych warpow.
    ``all_nodata=True`` -> ``extra.all_nodata: true`` (E15): wycinek bez
    ani jednego waznego piksela; pominiecie istniejacego wycinka odtwarza
    flage z sidecara zamiast czytac raster.
    """
    from kartograf.sources.sidecar import emit_sidecar

    b = cutout.bbox_target
    extra: dict = {}
    if parent_request:
        extra["parent_request"] = parent_request
    if missing_sheets:
        # R5: arkusze, dla ktorych GUGiK nie ma danych — tam wycinek ma nodata
        extra["missing_sheets"] = list(missing_sheets)
    if sheet_paths:
        extra["sheet_sources"] = [_sheet_source(Path(p)) for p in sheet_paths]
    if off_grid_sheets:
        extra["off_grid_sheets"] = list(off_grid_sheets)
    if all_nodata:
        extra["all_nodata"] = True
    emit_sidecar(
        "pl.gugik.nmt_5m" if cutout.resolution == "5m" else "pl.gugik.nmt_1m",
        cutout.target_path,
        request={
            "bbox": [b.min_x, b.min_y, b.max_x, b.max_y],
            "bbox_crs": cutout.target_crs,
        },
        vertical_crs=cutout.vertical_crs,
        horizontal_crs=cutout.target_crs,
        pinned_transforms={"horizontal": cutout.pinned},
        capability="sheet_files",
        nodata=PL_NODATA,
        extra=extra or None,
    )


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


@functools.cache
def _sheet_frame_transformer():
    """Jeden transformer WGS84 -> EPSG:2180 na proces (N9).

    ``SheetParser.get_bbox("EPSG:2180")`` buduje ``Transformer.from_crs`` przy
    KAZDYM wywolaniu (~7 ms; pyproj nie cache'uje ``from_crs``), a estymacja
    liczy obwiednie kazdego arkusza spoza cache — 1221 arkuszy to ~9 s, i tyle
    samo drugi raz, gdy wolajacy sam sprawdza miejsce przed ``run_pl_cutout``.
    Z jednym transformerem (bezpieczny miedzy watkami od pyproj 3.1) ta sama
    petla schodzi ponizej 0,2 s.
    """
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def _sheet_frame_2180(godlo: str) -> BBox:
    """Obwiednia arkusza w EPSG:2180 — jak ``SheetParser.get_bbox("EPSG:2180")``
    (obwiednia 4 przetransformowanych naroznikow), ze wspolnym transformerem."""
    from kartograf.core.sheet_parser import SheetParser

    wgs = SheetParser(godlo).get_bbox("EPSG:4326")
    transformer = _sheet_frame_transformer()
    xs, ys = zip(
        *(
            transformer.transform(lon, lat)
            for lon, lat in (
                (wgs.min_x, wgs.min_y),
                (wgs.min_x, wgs.max_y),
                (wgs.max_x, wgs.min_y),
                (wgs.max_x, wgs.max_y),
            )
        ),
        strict=True,
    )
    return BBox(min(xs), min(ys), max(xs), max(ys), "EPSG:2180")


def estimate_pl_cutout_bytes(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> tuple[int, int]:
    """(bajty, liczba arkuszy do pobrania) — DOLNE oszacowanie potrzeb dysku.

    Wynik float32 bez kompresji + arkusze jeszcze nie pobrane po 5,5 B na
    wartosc. Plik posredni mozaiki (skompresowany) i narzut systemu plikow NIE
    sa liczone: to kontrola "na pewno nie wystarczy", nie gwarancja. Tania
    (jeden transformer na proces, ``_sheet_frame_transformer``), wiec
    wolajacy, ktory liczy ja sam przed ``run_pl_cutout``, nie placi podwojnie.
    """
    storage = storage or storage_for_provider(
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
        frame = _sheet_frame_2180(leaf)
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


def _sidecar_sheet_list(extra: dict, key: str) -> tuple[str, ...]:
    """Lista godel z ``extra[key]`` sidecara — pusta, gdy pola nie ma albo
    ma inny ksztalt (sidecar z reki albo sprzed pola)."""
    value = extra.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str))


def skipped_pl_cutout(cutout: PlCutout) -> PlCutoutResult:
    """Wynik dla wycinka, ktory JUZ istnieje (``force=False``): zero sieci.

    Dziury nodata sa takie, jakie zapisala budowa pliku, wiec
    ``missing_sheets`` (arkusze bez danych GUGiK, R5) i ``off_grid_sheets``
    (W1) wracaja z sidecara istniejacego wycinka (``extra.missing_sheets``,
    ``extra.off_grid_sheets``), a nie jako puste krotki — konsument widzi to
    samo, co przy budowie. Bez sidecara, z sidecarem nieczytelnym albo bez
    tych pol (wycinek sprzed 0.7.0, bez dziur): puste. ``sheet_paths`` jest
    puste — arkuszy nikt tu nie dotyka. ``partial_sheets`` (E13) wraca
    z ``extra.sheet_sources`` (wpisy z ``full_sheet: false``), a
    ``all_nodata`` (E15) z ``extra.all_nodata`` — raster nie jest czytany.
    """
    sidecar = cutout.target_path.with_name(f"{cutout.target_path.name}.meta.json")
    try:
        extra = json.loads(sidecar.read_text(encoding="utf-8")).get("extra") or {}
    except (OSError, ValueError, AttributeError):
        extra = {}
    if not isinstance(extra, dict):
        extra = {}
    sources = extra.get("sheet_sources")
    return PlCutoutResult(
        path=cutout.target_path,
        skipped=True,
        missing_sheets=_sidecar_sheet_list(extra, "missing_sheets"),
        off_grid_sheets=_sidecar_sheet_list(extra, "off_grid_sheets"),
        all_nodata=extra.get("all_nodata") is True,
        partial_sheets=_partial_sheets(sources if isinstance(sources, list) else []),
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

    ``force=False`` + istniejacy plik wyniku -> ``skipped=True`` bez sieci
    (``missing_sheets``/``off_grid_sheets`` z sidecara istniejacego wycinka,
    ``skipped_pl_cutout``). Arkusze z cache sa uzywane ponownie
    (``skip_existing = not force``).
    Brak danych u zrodla (``NoCoverageError``) -> nodata + ``missing_sheets``;
    kazda inna porazka pobrania arkusza (``DownloadError``) -> ``DownloadError``;
    gdy ZADEN arkusz nie ma danych -> ``ValidationError``. Oba bledy padaja,
    zanim cokolwiek zostanie zbudowane. Wycinek z arkuszy, ktore nie wnosza
    ani jednego waznego piksela (N2: margines selekcji, arkusz w calosci
    nodata), POWSTAJE i ma ``all_nodata=True`` (+ ``logger.warning``) — to
    poprawny wynik "brak danych", nie blad.
    Inny wyjatek arkusza (np. ``OSError``
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
        return skipped_pl_cutout(cutout)
    if provider is None:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=cutout.vertical_crs, resolution=cutout.resolution
        )
    if storage is None:
        storage = storage_for_provider(
            cutout.output_dir,
            provider,
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
        off_grid = build_pl_cutout(
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
    # N2: arkusze z marginesu selekcji (1 px / zapas warpu) potrafia nie
    # wniesc zadnego piksela do obszaru zadania, a arkusz przygraniczny bywa
    # w calosci nodata — plik jest wtedy poprawnym wynikiem "brak danych",
    # ale konsument ma o tym wiedziec (CLI: Warning, kod 0).
    from kartograf.transport.mosaic import has_valid_pixels

    all_nodata = not has_valid_pixels(cutout.target_path, PL_NODATA)
    if all_nodata:
        logger.warning(
            f"Wycinek {cutout.target_path} jest w calosci nodata — pobrane "
            f"arkusze ({len(sheet_paths)}) nie wnosza zadnego piksela w obszarze "
            "zadania (brak danych GUGiK / obszar poza pokryciem)"
        )
    write_pl_cutout_sidecar(
        cutout,
        parent_request=parent_request,
        missing_sheets=missing,
        sheet_paths=tuple(sheet_paths),
        off_grid_sheets=off_grid,
        all_nodata=all_nodata,
    )
    return PlCutoutResult(
        path=cutout.target_path,
        sheet_paths=tuple(sheet_paths),
        missing_sheets=missing,
        off_grid_sheets=off_grid,
        all_nodata=all_nodata,
        partial_sheets=_partial_sheets([_sheet_source(Path(p)) for p in sheet_paths]),
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
    cache=None,
) -> PlCutoutResult:
    """Jeden scalony GeoTIFF NMT PL w ``target_crs`` dla bboxa albo geometrii.

    Tryb geometrii: ``bbox`` to obwiednia geometrii (np.
    ``get_overall_bbox(path, target_crs="EPSG:2180")``), ``geometry`` — plik
    Regula fabryki NMT: 5m => EVRF2007 (z ostrzezeniem w logu). Provider
    i sesja pochodza z fabryki; ``cache`` (``MetadataCache`` albo ``None``)
    trafia do providera — rekordy skorowidza sa czytane i zapisywane tylko
    z cache. ``force=True`` NIE omija cache rekordow sam z siebie: zeby
    odswiezyc rekordy (pominac odczyt, zapisac nowy wybor), podaj
    ``MetadataCache(refresh=True)`` — tak robi CLI przy ``--force`` (E14).
    Wlasny provider/sesja: kroki
    ``prepare_pl_cutout`` -> ``select_pl_cutout_sheets`` ->
    ``run_pl_cutout(provider=...)``.

    Returns
    -------
    PlCutoutResult
        ``path`` — plik wyniku; ``skipped=True`` (bez sieci), gdy plik juz
        istnial i ``force=False`` (``missing_sheets``/``off_grid_sheets``
        wtedy z sidecara istniejacego wycinka); ``missing_sheets`` — arkusze
        bez danych GUGiK (w ich miejscu nodata); ``off_grid_sheets`` — arkusze
        o innej fazie siatki, reprojektowane osobno (W1; tylko przy warpie);
        ``sheet_paths`` — arkusze uzyte do mozaiki (kolejnosc ukonczenia
        pobran).

    Raises
    ------
    ValidationError
        Zle parametry, brak arkuszy dla obszaru, zaden arkusz nie ma danych
        GUGiK, za malo miejsca na dysku albo arkusz we wspolrzednych PL-2000.
    GridMismatchError
        (podklasa ``ValidationError``) ``target_crs="EPSG:2180"``, a arkusze
        leza na roznych siatkach pikseli (S5): wartosci 1:1 sa niemozliwe —
        ``.off_grid`` wymienia arkusze z przesunieciem; arkusze zostaja
        w cache, wycinek z warpem (5514/3045) z nich powstanie.
    TransformError
        Brak bezpiecznej przypietej operacji EPSG:2180 -> ``target_crs``
        (przed jakakolwiek siecia).
    DownloadError
        Awaria pobrania arkusza (siec, serwer; zerwane zapytanie warstwy
        skorowidza — do 3 prob przy bledzie sieci, 429 i 5xx, inne 4xx bez
        ponowien — nie brak danych); wycinek nie powstaje.
    OSError
        Blad zapisu arkusza przy ``max_workers=1`` (w puli watkow liczy sie
        jak awaria pobrania).

    ``parent_request`` trafia do sidecara wycinka i sidecarow arkuszy
    pobranych w tym wywolaniu tylko wtedy, gdy zostal podany.
    """
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(
            f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})"
        )
    from kartograf.providers.pl import create_nmt_provider

    provider = create_nmt_provider(
        vertical_crs=vertical_crs, resolution=resolution, cache=cache
    )
    cutout = prepare_pl_cutout(
        bbox,
        target_crs,
        output_dir=output_dir,
        resolution=resolution,
        vertical_crs=provider.vertical_crs,
    )
    if not force and cutout.target_path.exists():
        return skipped_pl_cutout(cutout)
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
