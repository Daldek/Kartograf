"""Offline fixtures of the formats Kartograf writes and other projects read.

Projects that read a Kartograf store (``iter_store``, ``read_sidecar``,
``kartograf-project.json``, the ``kartograf-meta/1`` sidecars) test their
readers against instances built here instead of hand-written copies of the
formats. Everything is produced by the REAL writers of the library
(``fetch_version`` / ``commit_version`` for the versions, ``ensure_link``
for the standard and ``full_sheet/`` paths, ``emit_sidecar`` for the
sidecars, ``commit_tasks`` for the project file), so a fixture cannot drift
from the format: a change of a format changes the fixture, and the consumer's
contract test sees it when it moves to the new Kartograf version.

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
"""

import contextlib
import hashlib
import itertools
import json
import os
import tempfile
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, get_args

from kartograf import _clock
from kartograf._version import build_version
from kartograf.core.parser_registry import path_parts
from kartograf.download.campaigns import FULL_SHEET_DIR, CampaignRef
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
from kartograf.messages import message
from kartograf.project.manifest import (
    MANIFEST_NAME,
    absolute,
    commit_tasks,
    create_manifest,
    pin_problem,
    task_to_json,
)
from kartograf.project.model import PinnedFile, ProjectTask
from kartograf.project.operations import add_project_task, open_project
from kartograf.providers.pl.skorowidz import SkorowidzRecord
from kartograf.sources.sidecar import emit_sidecar

__all__ = [
    "PL_SEGMENT",
    "CZ_SEGMENT",
    "PL_SHEET",
    "CZ_SHEET",
    "VARIANTS",
    "Variant",
    "FixtureFile",
    "FixtureStore",
    "FixtureVersion",
    "build_fixture_store",
    "build_project",
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

_PL_DATASET = "pl.gugik.nmt_1m"
_CZ_DATASET = "cz.cuzk.dmr4g"
# Second PL sheet of the defect variants: same segment, own slot.
_DEFECT_SHEET = "N-34-130-D-d-2-3"
_UNKNOWN_SEGMENT = "newproduct/pl_experimental"
_INDEX_URL = "https://example.invalid/wfs/nmt_1m"
_SOURCE_URL = "https://example.invalid/nmt/{id}_1744736_{sheet}.asc"
_CLOCK_START = datetime(2026, 10, 12, 8, 30, 45, 123456, tzinfo=UTC)
_CLOCK_STEP = timedelta(minutes=1)
_PINNED_AT = datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC)
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
    """One file of the fixture store with its versions.

    Attributes
    ----------
    segment : str
        ``<product>/<variant>`` directory below the store root.
    unit : str
        Sheet code of the file.
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
        The store root (``output_dir`` of the read API).
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
        output_dir=root,
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
    base = Path(root)
    if base.exists() and (not base.is_dir() or any(base.iterdir())):
        raise ValidationError(
            message("testing.empty_directory_needed", base=base),
            option="root",
        )
    base.mkdir(parents=True, exist_ok=True)
    with _fixed_clock():
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
    # the writers leave the staging directories of the downloads empty
    for staging in base.glob(f"*/*/{VERSIONS_DIR}/{INCOMING_DIR}"):
        with contextlib.suppress(OSError):
            staging.rmdir()
    return FixtureStore(base, variant, (pl, cz), damaged)


def build_project(
    project_dir: str | Path,
    store: FixtureStore,
    *,
    pin: Literal["newest", "oldest"] = "newest",
) -> Path:
    """Write ``kartograf-project.json`` with tasks pinning versions of ``store``.

    The project is written by the real project writer: two ``elevation
    download`` tasks (``nmt-pl`` for the PL sheet, ``nmt-cz`` for the CZ
    sheet), each pinning one version of its file by SHA-256, size and label.
    The store is referenced relative to the project directory when it can be.
    ``open_project``, ``get_project_status`` and ``verify_project`` accept the
    result.

    Parameters
    ----------
    project_dir : str or Path
        Directory of the project; it must not contain a manifest yet.
    store : FixtureStore
        A store of ``build_fixture_store``.
    pin : {"newest", "oldest"}, default "newest"
        Which version of the PL sheet to pin. ``oldest`` pins a version that
        a newer one (with the standard path on it) has superseded, as a
        project does after the source published new content.

    Returns
    -------
    Path
        The project directory (``kartograf.open_project`` argument).

    Raises
    ------
    ValidationError
        The project exists already, or ``pin`` is unknown.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from kartograf import open_project
    >>> from kartograf.testing import build_fixture_store, build_project
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     store = build_fixture_store(Path(tmp) / "data")
    ...     project = build_project(Path(tmp) / "projekt", store)
    ...     print([task.name for task in open_project(project).tasks])
    ['nmt-pl', 'nmt-cz']
    """
    if pin not in ("newest", "oldest"):
        raise ValidationError(
            message("testing.unknown_pin", pin=pin),
            option="pin",
            allowed=("newest", "oldest"),
        )
    directory = absolute(project_dir)
    tasks = (
        (
            "nmt-pl",
            {
                "product": "nmt",
                "sheet": PL_SHEET,
                "resolution": "1m",
                "vertical_crs": "EVRF2007",
            },
            store.file(PL_SEGMENT),
            0 if pin == "oldest" else -1,
        ),
        (
            "nmt-cz",
            {
                "product": "nmt",
                "sheet": CZ_SHEET,
                "resolution": "5m",
                "vertical_crs": "Bpv",
            },
            store.file(CZ_SEGMENT),
            -1,
        ),
    )
    if (directory / MANIFEST_NAME).exists():
        raise ValidationError(
            message("testing.project_exists", path=directory / MANIFEST_NAME)
        )
    with _fixed_clock(_PINNED_AT):
        create_manifest(directory, _relative(store.root, directory))
        for name, options, file, index in tasks:
            project = add_project_task(
                directory, name=name, command="elevation download", options=options
            )
            before = task_to_json(next(t for t in project.tasks if t.name == name))
            version = file.versions[index]
            pinned = PinnedFile(
                "output",
                file.unit,
                file.path.relative_to(store.root).as_posix(),
                version.path.relative_to(store.root).as_posix(),
                version.label,
                version.sha256,
                version.size_bytes,
            )
            problem = pin_problem(pinned)
            if problem is not None:
                raise ValidationError(problem)
            task = ProjectTask(
                name,
                "elevation download",
                dict(before["options"]),
                _clock.now().isoformat(timespec="seconds"),
                build_version(),
                None,
                (pinned,),
            )
            if commit_tasks(directory, {name: (before, task_to_json(task))}):
                raise ValidationError(message("testing.task_changed", name=name))
    open_project(directory)
    return directory


def _relative(store: Path, project: Path) -> str:
    """Return the store as a manifest path.

    Relative to the project directory, with ``/``; absolute when there is no
    relative path (another drive).
    """
    try:
        return Path(os.path.relpath(absolute(store), project)).as_posix()
    except ValueError:
        return absolute(store).as_posix()


def make_sidecar(
    dataset: str = _PL_DATASET,
    *,
    request: Mapping[str, Any] | None = None,
    name: str | None = None,
    data: bytes | None = None,
    label: str = "2025-01-30",
    label_source: LabelSource = "edition",
    extra: Mapping[str, Any] | None = None,
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
                vertical_crs="EVRF2007" if dataset == _PL_DATASET else None,
                extra=None if extra is None else dict(extra),
                digest=(digest, len(body)),
                version=VersionRef(label, label_source).to_extra(),
                exclusive=True,
            )
        assert written is not None
        document: dict[str, Any] = json.loads(written.read_text(encoding="utf-8"))
    return document
