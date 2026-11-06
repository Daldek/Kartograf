"""Offline fixtures of the formats Kartograf writes and other projects read.

Projects that read a Kartograf store (``iter_store``, ``read_sidecar``, the
``kartograf-meta/1`` sidecars) test their readers against instances built here
instead of hand-written copies of the formats. Everything is produced by the REAL
writers of the library (``fetch_version`` / ``commit_version`` for the versions,
``ensure_link`` for the standard and ``full_sheet/`` paths, ``emit_sidecar`` for the
sidecars), so a fixture cannot drift from the format: a change of a format changes
the fixture, and the consumer's contract test sees it when it moves to the new
Kartograf version.

Nothing here touches the network and the output is deterministic: every
timestamp comes from the library clock seam (``kartograf._clock``), driven
by a fixed instant for the duration of a build, so two builds with the same
arguments give byte-identical files (the ``kartograf_version`` recorded in
the sidecars is that of the installed Kartograf).

The fixture store (variant ``complete``)::

    nmt/pl_1992_1m_evrf2007/                 PL NMT 1 m, ASC sheet N-34-130-D-d-2-4
        N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc        standard path (hard link)
        full_sheet/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
        versions/N-34/130/D/d/2/4/
            2022-05-10_83233_<sha8>/                 campaign 1, new content
            2025-01-30_84020_<sha8>/                 campaign 2, new content
            2025-06-02_84500_<sha8>/                 campaign 3, same bytes as 2
    nmt/cz_dmr4g_bpv/                        CZ DMR 4G, GeoTIFF sheet CTES96
        CTES/96/CTES96.tif, versions/CTES/96/<date>_<sha8>/CTES96.tif

Every data file has a ``<name>.meta.json`` sidecar next to it. The standard
path and ``full_sheet/`` path link (hard link) to the newest version, the
third PL version is a ``relabeled`` hard link of the second one (same
content, new label).

The PGW store (``build_pgw_store``, ADR-059)::

    hydro/pl_pgw_gdb/                        the national IIaPGW geodatabase archive
        country/pl.zip                               standard path (hard link)
        versions/country/2023-09-15_<sha8>/pl.zip    the edition 2023-09-15

Its archive (``build_pgw_archive``) is a tiny File Geodatabase in a ZIP with the
published structure of the real one: the geodatabase name of the edition, the
feature datasets ``PGW_WP``, ``JCWPd`` and ``SIG`` with their 25 spatial layers
(identifier and geometry columns, fields, the ESRI definition of the CS92 grid)
and the attribute table ``Charakterystyka_JCWP``, recorded from the archive of
2023-09-15 in ``_data/pgw_geodatabase.json`` (``scripts/build_pgw_geodatabase.py``).
Its features are fictional and lie around ``PGW_AREA``; the archive is stored by
the job of ``hydro download --whole-country`` itself, served from memory.
"""

import contextlib
import functools
import hashlib
import io
import itertools
import json
import tempfile
import threading
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, Literal, get_args

import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

from kartograf import _clock
from kartograf.core.bbox import BBox
from kartograf.core.parser_registry import path_parts
from kartograf.download.campaigns import FULL_SHEET_DIR, CampaignRef
from kartograf.download.collections import (
    package_job,
    run_job,
    validate_collection_request,
)
from kartograf.download.fetch import FileSlot, FileStatus, fetch_version, local_version
from kartograf.download.links import ensure_link
from kartograf.download.storage import unit_slot
from kartograf.download.versions import (
    INCOMING_DIR,
    VERSIONS_DIR,
    CommitStatus,
    ContentDigest,
    LabelSource,
    VersionRef,
    version_key,
)
from kartograf.exceptions import ValidationError
from kartograf.marker import prepare_store
from kartograf.messages import message
from kartograf.notices import NoticeSink
from kartograf.providers.pl.skorowidz import SkorowidzRecord
from kartograf.sources.sidecar import emit_sidecar

__all__ = [
    "PL_SEGMENT",
    "CZ_SEGMENT",
    "PL_SHEET",
    "CZ_SHEET",
    "PGW_DATASET",
    "PGW_ARCHIVE_SEGMENT",
    "PGW_AREA",
    "VARIANTS",
    "Variant",
    "FixtureFile",
    "FixtureStore",
    "FixtureVersion",
    "PgwFixture",
    "build_fixture_store",
    "build_pgw_archive",
    "build_pgw_store",
    "make_sidecar",
]

Variant = Literal[
    "complete",
    "unreadable_sidecar",
    "unknown_schema",
    "missing_sidecar",
    "unknown_segment",
]
VARIANTS: tuple[str, ...] = get_args(Variant)

PL_SEGMENT = "nmt/pl_1992_1m_evrf2007"
CZ_SEGMENT = "nmt/cz_dmr4g_bpv"
PL_SHEET = "N-34-130-D-d-2-4"
CZ_SHEET = "CTES96"
PGW_DATASET = "pl.pgw.pgw"
PGW_ARCHIVE_SEGMENT = "hydro/pl_pgw_gdb"
# The 10 x 10 km square of EPSG:2180 around which the features of the PGW
# archive lie (``build_pgw_archive``).
PGW_AREA = BBox(380000.0, 540000.0, 390000.0, 550000.0, "EPSG:2180")

_PL_DATASET = "pl.gugik.nmt_1m"
_CZ_DATASET = "cz.cuzk.dmr4g"
# Second PL sheet of the defect variants: same segment, own slot.
_DEFECT_SHEET = "N-34-130-D-d-2-3"
_UNKNOWN_SEGMENT = "newproduct/pl_experimental"
_INDEX_URL = "https://example.invalid/wfs/nmt_1m"
_SOURCE_URL = "https://example.invalid/nmt/{id}_1744736_{sheet}.asc"
_CLOCK_START = datetime(2026, 10, 12, 8, 30, 45, 123456, tzinfo=UTC)
_CLOCK_STEP = timedelta(minutes=1)
# An empty ZIP archive (the end-of-central-directory record only).
_EMPTY_ZIP = b"PK\x05\x06" + bytes(18)

_clock_lock = threading.Lock()


@contextlib.contextmanager
def _fixed_clock(start: datetime = _CLOCK_START) -> Iterator[None]:
    """Run with the library clock (``kartograf._clock.now``) ticking from ``start``.

    Every call advances the instant by one minute, so the versions of one
    build are ordered by their ``downloaded_at``. The patch is process-wide
    and restored on exit; builds serialise on a lock.
    """
    ticks = itertools.count()
    original = _clock.now

    def now() -> datetime:
        return start + _CLOCK_STEP * next(ticks)

    with _clock_lock:
        _clock.now = now
        try:
            yield
        finally:
            _clock.now = original


# --- data ----------------------------------------------------------------------


def _asc(offset: float) -> bytes:
    """Build a 4x4 Arc/Info ASCII Grid inside PL-1992 sheet ``PL_SHEET``."""
    rows = [
        " ".join(
            "-9999" if (row, col) == (0, 0) else f"{200 + offset + row + col / 2:.2f}"
            for col in range(4)
        )
        for row in range(4)
    ]
    header = (
        "ncols 4\nnrows 4\nxllcorner 770000\nyllcorner 509000\ncellsize 1\n"
        "NODATA_value -9999\n"
    )
    return (header + "\n".join(rows) + "\n").encode("ascii")


def _geotiff() -> bytes:
    """Build a 4x4 float32 GeoTIFF in S-JTSK / Krovak (EPSG:5514), 5 m cells."""
    import numpy as np  # lazy: heavy, and only the CZ sheet needs a raster
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    values = (300 + np.arange(16, dtype="float32")).reshape(4, 4)
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=4,
            height=4,
            count=1,
            dtype="float32",
            crs="EPSG:5514",
            transform=from_origin(-740000.0, -1040000.0, 5.0, 5.0),
            nodata=-9999.0,
        ) as dataset:
            dataset.write(values, 1)
        return bytes(memory.read())


# --- PGW data (ADR-059) --------------------------------------------------------

# The recorded structure of the published geodatabase (package data).
_PGW_STRUCTURE = "pgw_geodatabase.json"
# The date of every member of the archive: that of the published directory entry.
_PGW_MEMBER_DATE = (2023, 9, 15, 16, 37, 0)
# The headers of the published file besides its length (HEAD of 2026-11-06).
_PGW_HEADERS = {
    "Content-Type": "application/zip",
    "Content-Disposition": "attachment; filename=Geobaza_2aPGW_ver_20230915.gdb.zip",
}

# Fictional features of the archive around ``PGW_AREA`` (380000-390000 E,
# 540000-550000 N in EPSG:2180): per layer, the field values given and the
# geometry - ("box", min x, min y, max x, max y), ("line", (x, y), ...) or
# ("point", x, y). The other fields are null, ``Shape_Length`` and ``Shape_Area``
# are measured as the geodatabase does; a layer not named has no features.
_Feature = tuple[dict[str, Any], tuple[Any, ...]]
_PGW_FEATURES: dict[str, tuple[_Feature, ...]] = {
    # river catchments: inside, across the east edge, on the north edge, outside
    "Zlewnie_JCWP_rzecznych": (
        ({"MS_KOD": "RW600019000001"}, ("box", 381000, 541000, 386000, 549000)),
        ({"MS_KOD": "RW600019000002"}, ("box", 386000, 541000, 393000, 549000)),
        ({"MS_KOD": "RW600019000003"}, ("box", 381000, 550000, 393000, 556000)),
        ({"MS_KOD": "RW600019000004"}, ("box", 395000, 541000, 399000, 549000)),
    ),
    "Jednolite_Części_Wód_Powierzchniowych_Rzecznych": (
        (
            {"MS_KOD": "RW600019000001", "Nazwa_JCWP": "Stream 1"},
            ("line", (382000, 542000), (385000, 548000)),
        ),
        (
            {"MS_KOD": "RW600019000002", "Nazwa_JCWP": "Stream 2"},
            ("line", (387000, 542000), (392000, 548000)),
        ),
        (
            {"MS_KOD": "RW600019000004", "Nazwa_JCWP": "Stream 4"},
            ("line", (396000, 542000), (398000, 548000)),
        ),
    ),
    # a lake with its direct catchment inside, another catchment outside
    "Zlewnie_bezpośrednie_JCWP_jeziornych": (
        ({"MS_KOD": "LW10001"}, ("box", 382000, 545000, 384000, 547000)),
        ({"MS_KOD": "LW10002"}, ("box", 395500, 545000, 397000, 547000)),
    ),
    "Jednolite_Części_Wód_Powierzchniowych_Jeziornych": (
        (
            {"MS_KOD": "LW10001", "Nazwa_JCWP": "Lake 1"},
            ("box", 382500, 545500, 383500, 546500),
        ),
    ),
    # a remaining area across the south edge
    "Pozostale_obszary_JCWP": (
        ({"MS_KOD": "RW600019000005"}, ("box", 381000, 536000, 393000, 541000)),
    ),
    "Rzeki_glowne": (
        (
            {"NAZ_RZEKI": "River 1", "RZAD": 1},
            ("line", (379000, 545000), (391000, 546000)),
        ),
    ),
    # the units that cover the square (the authorities: FID ``OBJECTID_1``)
    "Regiony_wodne": (
        ({"RB_NAME": "Water region 1"}, ("box", 370000, 530000, 400000, 560000)),
    ),
    "Obszary_dorzeczy": (
        ({"RBD_NAME": "District 1"}, ("box", 360000, 520000, 410000, 570000)),
    ),
    "Ekoregiony": (
        ({"ECO_NAME": "Ecoregion 1"}, ("box", 360000, 520000, 410000, 570000)),
    ),
    "Regionalne_Zarządy_Gospodarki_Wodnej": (
        ({"RZGW_NAME": "Authority 1"}, ("box", 360000, 520000, 410000, 570000)),
    ),
    "Jednolite_części_wód_podziemnych": (
        (
            {"NR_JCWPD": 1, "kod_jcwpd": "GW600001"},
            ("box", 350000, 510000, 420000, 580000),
        ),
    ),
    # a protected area across the north-east corner, a monument inside and outside
    "Obszary_chronione_wodozależne": (
        (
            {"kodinspire": "PL.ZIPOP.1393.N2K.PLH990001.H"},
            ("box", 388000, 547000, 392000, 552000),
        ),
    ),
    "Obszary_chronione_wodozależne_pominiki_przyrody": (
        ({"kodinspire": "PL.ZIPOP.1393.PP.0000001"}, ("point", 383000, 546000)),
        ({"kodinspire": "PL.ZIPOP.1393.PP.0000002"}, ("point", 399000, 559000)),
    ),
}
# Rows of the attribute table, one per river water body of the archive.
_PGW_TABLE_ROWS: tuple[dict[str, Any], ...] = tuple(
    {"kod_jcwp": f"RW60001900000{n}", "nazwa_jcwp": f"Stream {n}"} for n in range(1, 6)
)


def _pgw_structure() -> dict[str, Any]:
    """Return the recorded structure of the published geodatabase."""
    data = resources.files("kartograf").joinpath("_data", _PGW_STRUCTURE)
    document: dict[str, Any] = json.loads(data.read_text(encoding="utf-8"))
    return document


def _pgw_geometry(spec: tuple[Any, ...]) -> Any:
    """Return the shapely geometry of a feature of ``_PGW_FEATURES``."""
    import shapely  # lazy, as the other data builders

    kind, *values = spec
    if kind == "box":
        return shapely.MultiPolygon([shapely.box(*values)])
    if kind == "line":
        return shapely.MultiLineString([values])
    return shapely.MultiPoint([values])


def _pgw_columns(
    fields: Mapping[str, str], rows: Sequence[Mapping[str, Any]], shapes: Sequence[Any]
) -> tuple[list[Any], list[Any]]:
    """Return the field arrays and null masks of ``rows`` for the GDAL writer.

    A field a row does not name is null; ``Shape_Length`` and ``Shape_Area`` of a
    feature are its length and area, as the geodatabase computes them.
    """
    import numpy as np
    import shapely

    data: list[Any] = []
    masks: list[Any] = []
    for name, dtype in fields.items():
        values: list[Any] = []
        for row, shape in zip(rows, shapes, strict=True):
            if name in row:
                values.append(row[name])
            elif shape is not None and name.lower() == "shape_length":
                values.append(float(shapely.length(shape)))
            elif shape is not None and name.lower() == "shape_area":
                values.append(float(shapely.area(shape)))
            else:
                values.append(None)
        if dtype == "object":
            data.append(np.array(values, dtype=object))
            masks.append(None)
        else:
            filled = [0 if value is None else value for value in values]
            data.append(np.array(filled, dtype=dtype))
            masks.append(np.array([value is None for value in values], dtype=bool))
    return data, masks


def _write_pgw_geodatabase(directory: Path) -> Path:
    """Write the fixture geodatabase into ``directory`` and return its path."""
    import numpy as np
    import pyogrio.raw
    import shapely

    from kartograf.transform.gpkg import gdal_config

    structure = _pgw_structure()
    path = directory / str(structure["geodatabase"])
    created = False
    # GDAL draws the UUIDs of the system tables at random unless told otherwise
    with gdal_config({"OPENFILEGDB_REPRODUCIBLE_UUID": "YES"}):
        for layer in structure["layers"]:
            features = _PGW_FEATURES.get(layer["name"], ())
            shapes = [_pgw_geometry(spec) for _, spec in features]
            data, masks = _pgw_columns(
                layer["fields"], [row for row, _ in features], shapes
            )
            pyogrio.raw.write(
                path,
                np.array([shapely.to_wkb(shape) for shape in shapes], dtype=object),
                data,
                fields=list(layer["fields"]),
                field_mask=masks,
                layer=layer["name"],
                driver="OpenFileGDB",
                geometry_type=layer["geometry"],
                crs=structure["crs"],
                append=created,
                layer_options={
                    "FEATURE_DATASET": layer["dataset"],
                    "FID": layer["fid"],
                    "GEOMETRY_NAME": layer["geometry_column"],
                },
            )
            created = True
        table = structure["table"]
        data, masks = _pgw_columns(
            table["fields"], _PGW_TABLE_ROWS, [None] * len(_PGW_TABLE_ROWS)
        )
        pyogrio.raw.write(
            path,
            None,
            data,
            fields=list(table["fields"]),
            field_mask=masks,
            layer=table["name"],
            driver="OpenFileGDB",
            append=True,
            layer_options={"FID": table["fid"]},
        )
    return path


@functools.cache
def _pgw_archive_bytes() -> bytes:
    """Return the ZIP of the fixture geodatabase, built once per process.

    The bytes do not change within a process (reproducible UUIDs, fixed member
    dates), so every later fixture copies the first build.
    """
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="kartograf-testing-") as tmp:
        gdb = _write_pgw_geodatabase(Path(tmp))
        with zipfile.ZipFile(buffer, "w") as archive:
            directory = zipfile.ZipInfo(f"{gdb.name}/", date_time=_PGW_MEMBER_DATE)
            archive.writestr(directory, b"")
            for file in sorted(gdb.iterdir()):
                member = zipfile.ZipInfo(
                    f"{gdb.name}/{file.name}", date_time=_PGW_MEMBER_DATE
                )
                member.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(member, file.read_bytes())
    return buffer.getvalue()


class _ServedFiles(BaseAdapter):
    """Answer the requests of a session from files in memory: no network.

    ``files``: URL -> (body, headers); any other URL answers 404.
    """

    def __init__(self, files: Mapping[str, tuple[bytes, Mapping[str, str]]]) -> None:
        super().__init__()
        self._files = dict(files)

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: Any = True,
        cert: Any = None,
        proxies: Any = None,
    ) -> requests.Response:
        """Return the answer to ``request`` from memory."""
        found = self._files.get(request.url or "")
        body, headers = found if found is not None else (b"", {})
        response = requests.Response()
        response.request = request
        response.url = request.url or ""
        response.status_code = 200 if found is not None else 404
        response.reason = "OK" if found is not None else "Not Found"
        response.headers = CaseInsensitiveDict(
            {**headers, "Content-Length": str(len(body))}
        )
        response.raw = io.BytesIO(body if request.method == "GET" else b"")
        return response

    def close(self) -> None:
        """Release nothing: the files are in memory."""


def _served(files: Mapping[str, tuple[bytes, Mapping[str, str]]]) -> requests.Session:
    """Return a session that answers from ``files`` and opens no socket."""
    session = requests.Session()
    adapter = _ServedFiles(files)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# --- results -------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureVersion:
    """One version of a fixture file as the store holds it.

    Attributes
    ----------
    label : str
        Version label (the directory name without ``_<sha8>``).
    sha256 : str
        SHA-256 of the data.
    size_bytes : int
        Size of the data.
    path : Path
        The version data file; ``<path>.meta.json`` is its sidecar.
    status : str
        What the writer did: ``new`` (new content) or ``relabeled`` (the
        content of an earlier version under a new label, hard linked).
    """

    label: str
    sha256: str
    size_bytes: int
    path: Path
    status: CommitStatus


@dataclass(frozen=True)
class FixtureFile:
    """One file of a fixture store with its versions.

    Attributes
    ----------
    segment : str
        ``<product>/<variant>`` directory below the store root.
    unit : str
        Unit of the file: its sheet code, or the country code of a national file.
    dataset : str
        Descriptor key recorded in the sidecars.
    path : Path
        The standard path (hard link to the newest version).
    full_sheet_path : Path or None
        The ``full_sheet/`` link, when the file has one.
    versions : tuple of FixtureVersion
        Oldest first; the last one is the one ``path`` links to. Empty for a
        file outside the version layout (variant ``unknown_segment``).
    """

    segment: str
    unit: str
    dataset: str
    path: Path
    full_sheet_path: Path | None
    versions: tuple[FixtureVersion, ...]


@dataclass(frozen=True)
class FixtureStore:
    """A fixture store built by ``build_fixture_store``.

    Attributes
    ----------
    root : Path
        The store root (``root`` of the read API).
    variant : str
        The variant that was built.
    files : tuple of FixtureFile
        The intact files, the same in every variant.
    defective : FixtureFile or None
        The file the variant damaged, ``None`` for ``complete``.
    """

    root: Path
    variant: str
    files: tuple[FixtureFile, ...]
    defective: FixtureFile | None = None

    def file(self, segment: str) -> FixtureFile:
        """Return the intact file of ``segment``.

        Raises
        ------
        KeyError
            The store has no intact file in that segment.
        """
        for item in self.files:
            if item.segment == segment:
                return item
        raise KeyError(segment)


@dataclass(frozen=True)
class PgwFixture:
    """The PGW store built by ``build_pgw_store``.

    Attributes
    ----------
    root : Path
        The store root (``root`` of the read API and of ``download_collection``).
    archive : FixtureFile
        The national archive: segment ``PGW_ARCHIVE_SEGMENT``, unit ``pl``, one
        version labelled by the edition ``2023-09-15``.
    """

    root: Path
    archive: FixtureFile


# --- writers -------------------------------------------------------------------


def _write_version(
    slot: FileSlot,
    body: bytes,
    ref: VersionRef,
    *,
    dataset: str,
    request: dict[str, Any],
    vertical_crs: str,
    extra: dict[str, Any] | None = None,
) -> FixtureVersion:
    """Commit ``body`` as a new version of ``slot`` through ``fetch_version``."""

    def fetch(staged: Path) -> dict[str, Any] | None:
        staged.write_bytes(body)
        return None

    def write_sidecar(
        data: Path, version: VersionRef, digest: ContentDigest, _http: Any
    ) -> None:
        emit_sidecar(
            dataset,
            data,
            request=request,
            vertical_crs=vertical_crs,
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    result = fetch_version(
        slot,
        "force",
        signal="none",
        fetch=fetch,
        write_sidecar=write_sidecar,
        version=ref,
    )
    status = _commit_status(result.status)
    return FixtureVersion(
        result.label, result.sha256, len(body), result.version_path, status
    )


def _commit_status(status: FileStatus) -> CommitStatus:
    if status not in ("new", "unchanged", "relabeled"):
        raise AssertionError(f"unexpected status of a forced download: {status}")
    return status


def _campaign(
    sheet: str, campaign: str, acquired: str, work: str, *, full: bool
) -> tuple[VersionRef, dict[str, Any]]:
    """Build the version label and ``extra`` of a campaign file.

    As the sheet flow writes them: from an index record through
    ``CampaignRef`` and ``to_source``.
    """
    record = SkorowidzRecord(
        url=_SOURCE_URL.format(id=campaign, sheet=sheet),
        sheet=sheet,
        aktualnosc=acquired,
        dt_pzgik=acquired[:4] + "-12-31",
        layer="nmt_1m",
        system="1992",
        zone=None,
        resolution_m=1.0,
        full_sheet=full,
        raw={
            "format": "ARC/INFO ASCII GRID",
            "zrDanych": "lotnicze skanowanie laserowe",
            "numerZgloszeniaPracy": work,
            "ukladWspolrzednychPoziomych": "PL-1992",
            "ukladWspolrzednychPionowych": "PL-EVRF2007-NH",
        },
    )
    ref = CampaignRef.from_record(record)
    extra = {"source": record.to_source(_INDEX_URL), "campaign": ref.to_extra()}
    return VersionRef(ref.dirname, "campaign"), extra


def _pl_file(
    root: Path, sheet: str, campaigns: Sequence[tuple[str, str, str, bytes]]
) -> FixtureFile:
    """Write a PL NMT sheet with one version per campaign.

    Campaigns are ``(campaign id, date, survey work, body)``; the standard
    path and the ``full_sheet/`` link end on the newest version.
    """
    slot = unit_slot(root, PL_SEGMENT, ".asc", sheet=sheet)
    request = {"sheet": sheet, "campaigns": "all", "full_sheet": True}
    versions = []
    for campaign, date, work, body in campaigns:
        ref, extra = _campaign(sheet, campaign, date, work, full=True)
        versions.append(
            _write_version(
                slot,
                body,
                ref,
                dataset=_PL_DATASET,
                request=request,
                vertical_crs="EVRF2007",
                extra=extra,
            )
        )
    newest = local_version(slot)
    assert newest is not None
    full_sheet = root.joinpath(
        PL_SEGMENT, FULL_SHEET_DIR, *path_parts(sheet), slot.name
    )
    ensure_link(full_sheet, newest.path, version_key(newest))
    return FixtureFile(
        PL_SEGMENT, sheet, _PL_DATASET, slot.std, full_sheet, tuple(versions)
    )


def _cz_file(root: Path) -> FixtureFile:
    """Write the CZ sheet: one version labelled by its download date."""
    parts = path_parts(CZ_SHEET)
    base = root / CZ_SEGMENT / VERSIONS_DIR
    slot = FileSlot(
        root=root,
        std=root.joinpath(CZ_SEGMENT, *parts, f"{CZ_SHEET}.tif"),
        versions_base=base,
        versions_root=base.joinpath(*parts),
        ext=".tif",
    )
    version = _write_version(
        slot,
        _geotiff(),
        VersionRef.downloaded(),
        dataset=_CZ_DATASET,
        request={"sheet": CZ_SHEET},
        vertical_crs="Bpv",
        extra={"all_nodata": False},
    )
    return FixtureFile(CZ_SEGMENT, CZ_SHEET, _CZ_DATASET, slot.std, None, (version,))


def _meta_path(data: Path) -> Path:
    return data.with_name(data.name + ".meta.json")


def _defective(root: Path, variant: Variant) -> FixtureFile:
    """Write the file ``variant`` damages.

    A second PL sheet written like the first, then spoiled the way a store
    gets spoiled (never by a Kartograf writer); ``unknown_segment`` is a file
    in a segment no descriptor produces.
    """
    if variant == "unknown_segment":
        data = root / _UNKNOWN_SEGMENT / "teryt" / "12.zip"
        data.parent.mkdir(parents=True)
        data.write_bytes(_EMPTY_ZIP)
        emit_sidecar("pl.gugik.bdot10k", data, request={"teryt": "12"})
        return FixtureFile(_UNKNOWN_SEGMENT, "12", "pl.gugik.bdot10k", data, None, ())
    file = _pl_file(
        root, _DEFECT_SHEET, [("83900", "2023-06-15", "P.83900", _asc(3.0))]
    )
    sidecar = _meta_path(file.versions[-1].path)
    if variant == "unreadable_sidecar":
        sidecar.write_text("{bad", encoding="utf-8")
    elif variant == "unknown_schema":
        text = sidecar.read_text(encoding="utf-8")
        old, new = '"kartograf-meta/1"', '"kartograf-meta/2"'
        assert old in text
        sidecar.write_text(text.replace(old, new), encoding="utf-8")
    else:
        sidecar.unlink()
    return file


def _new_root(root: str | Path) -> Path:
    """Return ``root`` as an empty directory, created when missing.

    Raises
    ------
    ValidationError
        ``root`` exists and is not an empty directory.
    """
    base = Path(root)
    if base.exists() and (not base.is_dir() or any(base.iterdir())):
        raise ValidationError(
            message("testing.empty_directory_needed", base=base),
            option="root",
        )
    base.mkdir(parents=True, exist_ok=True)
    return base


def _remove_staging(base: Path) -> None:
    """Remove the staging directories the writers of the downloads leave empty."""
    for staging in base.glob(f"*/*/{VERSIONS_DIR}/{INCOMING_DIR}"):
        with contextlib.suppress(OSError):
            staging.rmdir()


def _pgw_archive_file(root: Path, body: bytes) -> FixtureFile:
    """Store ``body`` by the job of ``hydro download --product pgw --whole-country``.

    The request is resolved as the command resolves it and the job runs as the
    command runs it; only its requests are answered from memory.
    """
    request = validate_collection_request(
        product="pgw", country="pl", whole_country=True, root=root
    )
    (part,) = request.parts
    assert part.variant is not None
    job = package_job(
        root,
        part.descriptor,
        part.channel,
        part.variant,
        country=part.country,
        teryt=None,
        request={"whole_country": True, **part.choice},
    )
    stored = run_job(
        job,
        "force",
        sink=NoticeSink(None),
        session=_served({job.url or "": (body, _PGW_HEADERS)}),
    )
    assert stored is not None
    version = FixtureVersion(
        stored.label,
        stored.sha256,
        stored.size_bytes,
        stored.version_path,
        _commit_status(stored.status),
    )
    return FixtureFile(
        PGW_ARCHIVE_SEGMENT, job.unit, PGW_DATASET, stored.path, None, (version,)
    )


# --- public API ----------------------------------------------------------------


def build_fixture_store(
    root: str | Path, *, variant: Variant = "complete"
) -> FixtureStore:
    """Build a small versioned store under ``root``, offline.

    The store is written by the real writers of Kartograf and holds two
    products: a PL NMT 1 m ASC sheet with three versions (two contents and a
    ``relabeled`` third one, standard and ``full_sheet/`` link on the newest)
    and one CZ DMR 4G GeoTIFF sheet with one version - see the module
    docstring for the layout. The read API sees 2 segments, 4 versions and
    3 links (the PL standard path, its ``full_sheet/`` link, the CZ path)
    with no problem.

    Parameters
    ----------
    root : str or Path
        Store directory; it must not exist or must be empty.
    variant : str, default "complete"
        One of ``VARIANTS``. ``complete`` is the store above. Every other
        variant adds ONE damaged file to it (``FixtureStore.defective``)
        that exercises an error path of the read API; the intact files read
        as in ``complete``. For the three sidecar variants the sheet is a
        second PL sheet ``N-34-130-D-d-2-3`` (one version, standard and
        ``full_sheet/`` link, whose own sidecars stay readable) and only the
        sidecar of that version is damaged:

        * ``unreadable_sidecar`` - the version sidecar is not JSON:
          ``iter_store`` reports the version as an ``invalid_sidecar``
          problem, ``read_sidecar`` raises ``InvalidSidecarError``.
        * ``unknown_schema`` - the version sidecar has the
          schema ``kartograf-meta/2``: ``invalid_sidecar``,
          ``InvalidSidecarError`` ("Nieznany schemat").
        * ``missing_sidecar`` - the version sidecar is
          deleted: ``missing_sidecar``, ``read_sidecar`` raises
          ``InvalidSidecarError``.
        * ``unknown_segment`` - a file in ``newproduct/pl_experimental`` that
          no descriptor produces: ``unknown_segment`` problem,
          ``describe_segment(...).known`` is false.

    Returns
    -------
    FixtureStore
        ``root``, the intact files with their versions and the damaged file.

    Raises
    ------
    ValidationError
        Unknown ``variant`` or a ``root`` that exists and is not an empty
        directory.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from kartograf import iter_store, list_segments
    >>> from kartograf.testing import build_fixture_store
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     store = build_fixture_store(Path(tmp) / "data")
    ...     print(list_segments(store.root))
    ['nmt/cz_dmr4g_bpv', 'nmt/pl_1992_1m_evrf2007']
    """
    if variant not in VARIANTS:
        raise ValidationError(
            message(
                "testing.unknown_variant", variant=variant, variants=", ".join(VARIANTS)
            ),
            option="variant",
            allowed=VARIANTS,
        )
    base = _new_root(root)
    with _fixed_clock():
        prepare_store(base)  # the marker, as the first write into a root writes it
        pl = _pl_file(
            base,
            PL_SHEET,
            [
                ("83233", "2022-05-10", "P.83233", _asc(0.0)),
                ("84020", "2025-01-30", "P.84020", _asc(1.25)),
                ("84500", "2025-06-02", "P.84500", _asc(1.25)),
            ],
        )
        cz = _cz_file(base)
        damaged = None if variant == "complete" else _defective(base, variant)
    _remove_staging(base)
    return FixtureStore(base, variant, (pl, cz), damaged)


def build_pgw_archive(path: str | Path) -> Path:
    """Write a tiny IIaPGW geodatabase archive to ``path``, offline.

    The ZIP holds one File Geodatabase with the published structure of the archive
    of 2023-09-15 (module docstring): its name, the 25 spatial layers of the
    feature datasets ``PGW_WP``, ``JCWPd`` and ``SIG`` with their identifier and
    geometry columns, fields and ESRI definition of the CS92 grid, and the
    attribute table ``Charakterystyka_JCWP``. Fictional features lie around
    ``PGW_AREA``: four river catchments (inside the square, across its east edge,
    on its north edge, outside), their rivers, two lake catchments and a lake, a
    remaining area across the south edge, the units that cover the square, a
    groundwater body, a protected area and two monuments; the other layers are
    empty. GDAL (``pyogrio``) writes it with reproducible UUIDs and the members
    have fixed dates, so one GDAL version gives the same bytes; they are built once
    per process (about 3 s) and only copied by the next call.

    Parameters
    ----------
    path : str or Path
        The ZIP to write; its directory is created, an existing file replaced.

    Returns
    -------
    Path
        ``path``.

    Examples
    --------
    >>> import tempfile, zipfile
    >>> from pathlib import Path
    >>> from kartograf.testing import build_pgw_archive
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     archive = build_pgw_archive(Path(tmp) / "pl.zip")
    ...     print(zipfile.ZipFile(archive).namelist()[0])
    Geobaza_2aPGW_ver_20230915.gdb/
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_pgw_archive_bytes())
    return target


def build_pgw_store(root: str | Path) -> PgwFixture:
    """Build a store with the national PGW archive under ``root``, offline.

    The archive of ``build_pgw_archive`` is stored by the job of ``hydro download
    --product pgw --country pl --whole-country`` with its requests answered from
    memory: the version ``2023-09-15_<sha8>`` of ``hydro/pl_pgw_gdb/country/pl.zip``
    with the sidecar that command writes (``request`` ``{"whole_country": true}``,
    ``extra.source``, ``extra.http``, ``extra.version``) and the standard path
    linked to it.

    Parameters
    ----------
    root : str or Path
        Store directory; it must not exist or must be empty.

    Returns
    -------
    PgwFixture
        ``root`` and the archive with its version.

    Raises
    ------
    ValidationError
        A ``root`` that exists and is not an empty directory.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from kartograf import list_segments
    >>> from kartograf.testing import build_pgw_store
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     store = build_pgw_store(Path(tmp) / "data")
    ...     print(list_segments(store.root), store.archive.versions[0].label)
    ['hydro/pl_pgw_gdb'] 2023-09-15
    """
    base = _new_root(root)
    with _fixed_clock():
        prepare_store(base)  # the marker, as the first write into a root writes it
        archive = _pgw_archive_file(base, _pgw_archive_bytes())
    _remove_staging(base)
    return PgwFixture(base, archive)


def make_sidecar(
    dataset: str = _PL_DATASET,
    *,
    request: Mapping[str, Any] | None = None,
    name: str | None = None,
    data: bytes | None = None,
    label: str = "2025-01-30",
    label_source: LabelSource = "edition",
    extra: Mapping[str, Any] | None = None,
    vertical_crs: str | None = None,
) -> dict[str, Any]:
    """Build a valid ``kartograf-meta/1`` document with the real emitter.

    For consumers that only need a sidecar dictionary (no store). The
    document is what ``emit_sidecar`` writes for a version of ``data`` of
    the registered source ``dataset``: schema, dataset, CRSs, license,
    ``sha256`` and ``size_bytes`` of ``data``, a fixed ``downloaded_at`` and
    ``extra.version``. The data are written to a temporary directory only
    to be measured.

    Parameters
    ----------
    dataset : str, default "pl.gugik.nmt_1m"
        Key of a registered source (``kartograf.list_sources``).
    request : mapping, optional
        The ``request`` of the sidecar; default: the PL sheet ``N-34-130-D-d-2-4``.
    name : str, optional
        File name of the data (its extension tells the writer how to read
        nodata and the CRS); default ``<sheet>.asc``.
    data : bytes, optional
        Content of the data file; default: a 4x4 ASC grid of that sheet.
    label, label_source : str
        ``extra.version`` of the sidecar.
    extra : mapping, optional
        Added to ``extra`` next to ``version``.
    vertical_crs : str, optional
        The height system the writer records (``EVRF2007``, ``KRON86``, ``Bpv``:
        its EPSG code in the sidecar); default ``EVRF2007`` for
        ``pl.gugik.nmt_1m``, none for any other dataset.

    Returns
    -------
    dict
        The parsed sidecar JSON.

    Raises
    ------
    kartograf.exceptions.DownloadError
        ``dataset`` is not a registered source.

    Examples
    --------
    >>> from kartograf.testing import make_sidecar
    >>> meta = make_sidecar()
    >>> meta["schema"], meta["dataset"], meta["extra"]["version"]["label"]
    ('kartograf-meta/1', 'pl.gugik.nmt_1m', '2025-01-30')
    """
    sheet_request = {"sheet": PL_SHEET} if request is None else dict(request)
    file_name = (
        name if name is not None else f"{sheet_request.get('sheet', PL_SHEET)}.asc"
    )
    body = data if data is not None else _asc(1.25)
    digest = hashlib.sha256(body).hexdigest()
    with tempfile.TemporaryDirectory(prefix="kartograf-testing-") as tmp:
        path = Path(tmp) / file_name
        path.write_bytes(body)
        with _fixed_clock():
            written = emit_sidecar(
                dataset,
                path,
                request=sheet_request,
                vertical_crs=(
                    vertical_crs
                    if vertical_crs is not None
                    else "EVRF2007"
                    if dataset == _PL_DATASET
                    else None
                ),
                extra=None if extra is None else dict(extra),
                digest=(digest, len(body)),
                version=VersionRef(label, label_source).to_extra(),
                exclusive=True,
            )
        assert written is not None
        document: dict[str, Any] = json.loads(written.read_text(encoding="utf-8"))
    return document
