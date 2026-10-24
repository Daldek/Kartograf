"""Read-only view of the versioned ``data/`` store (ADR-045, ARCHITECTURE 3.3.1).

The scan works from directory listings: every link, ``full_sheet`` link and
version opens only its own sidecar, once; a data file is never opened, hashed
or statted, and a sidecar missing from a listing is reported without an
``open``. A version directory named in ``skip_versions`` is only listed, or -
named with its file names - not even listed. ``list_partitions`` splits one
segment into disjoint parts for parallel scans. Confirming a hardlink by
content is the separate, on-demand ``link_target``. Nothing here writes to
the store, so every function works on a store mounted read-only and may run
in several threads at once.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import re
import stat
import time
from collections.abc import Collection, Generator, Iterable, Iterator, Mapping, Set
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Any, Literal

from kartograf.core import parser_registry
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.campaigns import FULL_SHEET_DIR
from kartograf.download.links import linked_version
from kartograf.download.versions import INCOMING_DIR, STALE_AFTER_S, VERSIONS_DIR
from kartograf.exceptions import InvalidSidecarError, ValidationError
from kartograf.sources.descriptor import (
    AtomFilesParams,
    FeatureBBoxParams,
    SheetIndexParams,
    SourceDescriptor,
    UnitPackageParams,
    WcsCutoutParams,
)
from kartograf.sources.registry import all_sources, get_source
from kartograf.sources.variants import parse_resolution

EntryKind = Literal["version", "link", "full_sheet", "problem"]
ProblemCode = Literal[
    "missing_sidecar",
    "invalid_sidecar",
    "unknown_segment",
    "legacy_campaigns",
    "stale_incoming",
]


@dataclass(frozen=True)
class Sidecar:
    """Typed ``kartograf-meta/1`` metadata of one file (ARCHITECTURE 3.2).

    Fields of the schema keep their meaning; a missing value or a value of an
    unexpected type is ``None`` (``raw`` keeps the unchanged JSON). Keys of
    sidecars written before ADR-031 (Polish names) are read under their
    current names in ``request``/``extra``; ``dataset`` stays raw and
    ``dataset_key`` is the registered descriptor key (development keys of
    0.8.0 mapped explicitly), ``None`` when the registry does not know it.

    Derived fields: ``data_year``/``data_date`` (when the DATA were acquired
    or published: campaign, index record, LAZ tile, edition - never the
    download timestamp), ``campaign`` (``extra.campaign``),
    ``survey_work_id``, ``edition``, ``full_sheet`` (declared full sheet),
    ``coverage`` (valid-cell share 0..1) and ``unit`` (the unit of the
    request: TERYT, KU, sheet, tile, ``<coords>`` or the country code; for
    a national file of a theme the file stem ``<code>_<theme>``, e.g.
    ``pl_miejscowosci``; for a LAZ tile - also one selected for an area or
    a sheet request, whose ``request.bbox`` is that area - its tile code
    ``extra.tile_sheet``). ``unit`` can be passed to ``iter_store(units=...)``
    of the file's segment.

    Not hashable (``request``/``extra``/``raw`` are dicts); compare with
    ``==`` or key by ``StoreEntry.path``.
    """

    schema: str
    dataset: str | None
    dataset_key: str | None
    country: str | None
    product: str | None
    provider: str | None
    horizontal_crs: str | None
    vertical_crs: str | None
    vertical_source: str | None
    resolution: str | None
    nodata: float | None
    request: dict[str, Any] | None
    license: dict[str, Any] | None
    downloaded_at: str | None
    kartograf_version: str | None
    transform: dict[str, Any] | None
    extra: dict[str, Any] | None
    sha256: str | None
    size_bytes: int | None
    data_year: int | None
    data_date: str | None
    campaign: dict[str, Any] | None
    survey_work_id: str | None
    edition: str | None
    full_sheet: bool | None
    coverage: float | None
    unit: str | None
    raw: dict[str, Any]

    __hash__ = None  # type: ignore[assignment]  # dict fields: explicit, not generated


@dataclass(frozen=True)
class StoreEntry:
    """One file of the store, or one problem found in it (``iter_store``).

    Attributes
    ----------
    kind : str
        ``version`` (an immutable file in ``versions/``), ``link`` (standard
        path), ``full_sheet`` (link in ``full_sheet/``) or ``problem``.
    segment : str
        ``<product>/<variant>`` directory, e.g. ``nmt/pl_1992_1m_evrf2007``.
    hierarchy : str
        Slot directory below the segment (below ``versions/`` or
        ``full_sheet/`` for those kinds), e.g. ``N-34/130/D/d/2/4``,
        ``teryt``; ``""`` for a segment-level problem.
    name, path : str, Path
        File (or problem directory) name and path, built from ``output_dir``
        as given.
    version_path : Path or None
        The version a link points to according to its sidecar (lexically
        checked to lie in the link's own slot, not verified by content - see
        ``link_target``); a version's own path; ``None`` when unknown.
    label, sha8 : str or None
        Version label and the first 8 hex digits of its sha256 (from the
        version directory name ``<label>_<sha8>``; for a link without a
        known version, from its sidecar).
    sidecar : Sidecar or None
        Parsed sidecar; ``None`` for a skipped version (``skipped``) and for
        problems without a readable sidecar.
    problem : str or None
        ``missing_sidecar``, ``invalid_sidecar`` (unreadable, another schema,
        or a version sidecar not matching its directory), ``unknown_segment``
        (a segment the registry cannot produce), ``legacy_campaigns`` (0.7.x
        ``kampanie/``) or ``stale_incoming`` (staging older than 24 h).
    skipped : bool
        ``True`` for a version whose directory was listed in
        ``skip_versions``: its sidecar was not read.

    Not hashable (the sidecar holds dicts); key by ``path`` (or ``(kind,
    path)``).
    """

    kind: EntryKind
    segment: str
    hierarchy: str
    name: str
    path: Path
    version_path: Path | None
    label: str | None
    sha8: str | None
    sidecar: Sidecar | None
    problem: ProblemCode | None
    skipped: bool = False

    __hash__ = None  # type: ignore[assignment]  # dict fields: explicit, not generated


@dataclass(frozen=True)
class SegmentInfo:
    """Registered source and human-readable variant of a store segment.

    ``known=False``: no registered descriptor produces this segment (another
    release, a development directory, a user's directory); ``product``,
    ``country`` and ``dataset_key`` are then ``None`` and ``name`` is the
    segment itself - never a guessed descriptor.
    """

    segment: str
    product: str | None
    country: str | None
    dataset_key: str | None
    name: str
    known: bool


_SCHEMA = "kartograf-meta/1"
_META_SUFFIX = ".meta.json"
# 0.7.x campaign directory (download/storage.py, ``has_legacy_campaigns``).
_LEGACY_DIR = "kampanie"
_RESERVED = frozenset({VERSIONS_DIR, FULL_SHEET_DIR, _LEGACY_DIR})
# Longest file name component accepted in a unit (NAME_MAX of common file systems).
_NAME_MAX = 255
# Link trees of a slot: the standard path and the second link (ADR-033).
_LINK_DIRS: tuple[tuple[tuple[str, ...], EntryKind], ...] = (
    ((), "link"),
    ((FULL_SHEET_DIR,), "full_sheet"),
)
_READ_CHUNK = 65536
# Characters that make a name more than one directory entry (partition keys,
# ``skip_versions`` file names).
_SEPARATORS = ("/", "\x00", os.sep, os.altsep or "/")
# ``skip_versions`` as the scan uses it: known version directories, listed
# only (a set) or not even listed (a mapping to their data file names).
_Skip = Set[str] | Mapping[str, Collection[str]] | None

# Dataset keys renamed in the unpublished 0.8.0 development tree (ADR-044 D7).
# Keep the raw value in Sidecar.dataset; only dataset_key is normalized.
_DEV_DATASETS = {
    "pl.gugik.orto_true": "pl.gugik.true_orto",
    "pl.gugik.orto_oblique": "pl.gugik.oblique_orto",
    "pl.gugik.buildings_3d": "pl.gugik.buildings",
    "pl.gugik.mesh_3d": "pl.gugik.mesh",
    "pl.gugik.trees_3d": "pl.gugik.trees",
    "pl.gugik.prpog": "pl.gugik.control",
    "pl.gugik.quasigeoid": "pl.gugik.geoid2021",
    "cz.cuzk.hy_net": "cz.cuzk.hynet",
    "cz.cuzk.ortofoto": "cz.cuzk.orto",
    "cz.cuzk.survey_control": "cz.cuzk.control",
    "cz.cuzk.qgzu": "cz.cuzk.qgzu2013",
}
# Keys of sidecars written before ADR-031 (Polish names) -> current names.
_REQUEST_KEYS = {"godlo": "sheet"}
_SOURCE_KEYS = {
    "godlo": "sheet",
    "aktualnosc": "acquisition_date",
    "aktualnosc_rok": "acquisition_year",
    "uklad": "declared_crs",
    "zrodlo_danych": "data_source",
    "numer_zgloszenia": "survey_work_id",
    "skorowidz": "index_url",
    "dt_pzgik": "pzgik_date",
    "kolor": "color",
}
_CAMPAIGN_KEYS = {"zgloszenie": "survey_work_id", "dt_pzgik": "pzgik_date"}
_EXTRA_KEYS = {
    "godlo_kafla": "tile_sheet",
    "rok": "year",
    "gestosc": "nominal_density",
    "uwaga": "note",
    "podil": "cz_share",
}
_SHEET_SOURCE_KEYS = {"godlo": "sheet", "aktualnosc": "acquisition_date"}

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_YEAR = re.compile(r"[0-9]{4}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# Version directory ``<label>_<sha8>`` (download/versions.py).
_VERSION_DIR = re.compile(r"(.+)_([0-9a-f]{8})")
# Unit codes of ``download.storage.unit_slot``: ``<coords>`` of a bbox slot
# (``%.10g`` joined by ``_``), TERYT, a country (optionally ``_<theme>``).
_COORD = r"-?[0-9.]+(?:e[-+]?[0-9]+)?"
_BBOX_UNIT = re.compile(rf"{_COORD}(?:_{_COORD}){{3}}")
_TERYT = re.compile(r"[0-9]{2,7}")
_KU = re.compile(r"[0-9]{6}")
_COUNTRY = re.compile(r"[a-z]{2}(?:_[a-z0-9]+(?:-[a-z0-9]+)*)?")
# Unit kinds of package channels that are sheet or tile codes, not TERYT/KU.
_CODE_KINDS = frozenset({"sheet", "tile"})
# Orthophoto colour variants of GugikOrtoProvider.storage_variant (E12).
_ORTO_COLORS = {"cir": "CIR", "bw": "B/W"}


def _renamed(
    value: dict[str, Any] | None, names: dict[str, str]
) -> dict[str, Any] | None:
    """Historical keys under current names; never changes the raw JSON."""
    if value is None or names.keys().isdisjoint(value):
        return value
    result = value.copy()
    for old, current in names.items():
        if old in result:
            previous = result.pop(old)
            result.setdefault(current, previous)
    return result


def _normalized_extra(extra: dict[str, Any] | None) -> dict[str, Any] | None:
    if extra is None:
        return None
    result = _renamed(extra, _EXTRA_KEYS)
    assert result is not None
    for key, names in (("source", _SOURCE_KEYS), ("campaign", _CAMPAIGN_KEYS)):
        old = _dict(extra.get(key))
        new = _renamed(old, names)
        if new is not old:
            result = result.copy() if result is extra else result
            result[key] = new
    sheets = extra.get("sheet_sources")
    if isinstance(sheets, list) and any(
        isinstance(sheet, dict) and not _SHEET_SOURCE_KEYS.keys().isdisjoint(sheet)
        for sheet in sheets
    ):
        result = result.copy() if result is extra else result
        result["sheet_sources"] = [
            _renamed(sheet, _SHEET_SOURCE_KEYS) if isinstance(sheet, dict) else sheet
            for sheet in sheets
        ]
    return result


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _pick(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _date(value: Any) -> str | None:
    return value if isinstance(value, str) and _DATE.fullmatch(value) else None


def _year(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1000 <= value <= 9999 else None
    if isinstance(value, str) and _YEAR.fullmatch(value):
        return int(value)
    return None


def _unit(
    request: dict[str, Any] | None,
    source: dict[str, Any],
    tile_sheet: Any,
    country: str | None,
    stem: str | None,
) -> str | None:
    if request is None:
        return None
    unit = _pick(
        request.get("teryt"),
        request.get("ku"),
        request.get("sheet"),
        request.get("tile"),
        source.get("sheet"),
        # A LAZ tile selected for an area keeps that area in ``request.bbox``
        # (0.7.x-0.8.0 sidecars): its own unit is the tile, never the area.
        tile_sheet,
    )
    if unit:
        return unit
    bbox = request.get("bbox")
    if (
        isinstance(bbox, list)
        and len(bbox) == 4
        and all(_number(v) is not None for v in bbox)
    ):
        # The same %.10g naming as the bbox slot (download/storage.py).
        return "_".join(format(v, ".10g") for v in bbox)
    if request.get("whole_country") is True:
        # The slot of a national file is named ``<code>[_<theme>]`` by
        # ``unit_slot``; the theme is not in the request.
        if stem is not None and _COUNTRY.fullmatch(stem):
            return stem
        return _pick(request.get("country"), country.lower() if country else None)
    return None


@lru_cache(maxsize=256)
def _dataset_key(dataset: str) -> str | None:
    """Return the registered key of a sidecar ``dataset`` (0.8.0-dev keys mapped)."""
    try:
        return get_source(_DEV_DATASETS.get(dataset, dataset)).key
    except KeyError:
        return None


def _typed(raw: dict[str, Any], stem: str | None) -> Sidecar:
    """Return the typed view of a ``kartograf-meta/1`` object; raw stays untouched.

    ``stem`` is the stem of the data file the sidecar belongs to.
    """
    extra = _normalized_extra(_dict(raw.get("extra")))
    request = _renamed(_dict(raw.get("request")), _REQUEST_KEYS)
    extra_data = extra or {}
    request_data = request or {}
    source = _dict(extra_data.get("source")) or {}
    campaign = _dict(extra_data.get("campaign"))
    campaign_data = campaign or {}
    version = _dict(extra_data.get("version")) or {}
    label = _text(version.get("label"))
    label_source = version.get("label_source")
    edition = _pick(source.get("edition"), extra_data.get("edition"))
    if edition is None and label_source == "edition":
        edition = label
    # When the data were acquired or published - never ``downloaded_at``
    # (a "downloaded" label is the download date as well).
    date: str | None = None
    for value in (
        campaign_data.get("date"),
        source.get("acquisition_date"),
        extra_data.get("acquisition_date"),
    ):
        if (date := _date(value)) is not None:
            break
    if date is None and label is not None and label_source == "campaign":
        date = _date(label[:10])
    if date is None and edition is not None:
        date = _date(edition)
    year = int(date[:4]) if date is not None else None
    if year is None:
        for value in (
            campaign_data.get("year"),
            extra_data.get("year"),
            source.get("acquisition_year"),
            source.get("year"),
            request_data.get("year"),
            edition,
        ):
            if (year := _year(value)) is not None:
                break
    dataset = _text(raw.get("dataset"))
    sha256 = _text(raw.get("sha256"))
    size = raw.get("size_bytes")
    country = _text(raw.get("country"))
    full_sheet: bool | None = None
    for value in (
        campaign_data.get("full_sheet"),
        extra_data.get("full_sheet"),
        source.get("full_sheet"),
    ):
        if isinstance(value, bool):
            full_sheet = value
            break
    return Sidecar(
        schema=_SCHEMA,
        dataset=dataset,
        dataset_key=_dataset_key(dataset) if dataset else None,
        country=country,
        product=_text(raw.get("product")),
        provider=_text(raw.get("provider")),
        horizontal_crs=_text(raw.get("horizontal_crs")),
        vertical_crs=_text(raw.get("vertical_crs")),
        vertical_source=_text(raw.get("vertical_source")),
        resolution=_text(raw.get("resolution")),
        nodata=_number(raw.get("nodata")),
        request=request,
        license=_dict(raw.get("license")),
        downloaded_at=_text(raw.get("downloaded_at")),
        kartograf_version=_text(raw.get("kartograf_version")),
        transform=_dict(raw.get("transform")),
        extra=extra,
        sha256=sha256 if sha256 is not None and _SHA256.fullmatch(sha256) else None,
        size_bytes=(
            size
            if isinstance(size, int) and not isinstance(size, bool) and size >= 0
            else None
        ),
        data_year=year,
        data_date=date,
        campaign=campaign,
        survey_work_id=_pick(
            campaign_data.get("survey_work_id"), source.get("survey_work_id")
        ),
        edition=edition,
        full_sheet=full_sheet,
        coverage=_number(extra_data.get("coverage")),
        unit=_unit(request, source, extra_data.get("tile_sheet"), country, stem),
        raw=raw,
    )


def _read_bytes(path: str) -> bytes:
    """Read a small file with open/read/close only (no ``fstat``, no ``isatty``)."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        chunks = []
        while chunk := os.read(fd, _READ_CHUNK):
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _is_meta(raw: dict[str, Any]) -> bool:
    """Check whether ``raw`` is a ``kartograf-meta/1`` object.

    A missing ``schema`` is accepted only for the bare version sidecar of a provider
    without a descriptor (``emit_sidecar``): the same object with ``sha256`` and
    ``extra``, accepted by ``read_version``.
    """
    schema = raw.get("schema")
    if schema is None:
        return isinstance(raw.get("sha256"), str) and isinstance(raw.get("extra"), dict)
    return bool(schema == _SCHEMA)


def _load(side: str | Path) -> Sidecar:
    try:
        raw = json.loads(_read_bytes(os.fspath(side)))
    except (OSError, ValueError) as exc:
        raise InvalidSidecarError(
            f"Nie mozna odczytac sidecara {side}: {exc}", path=Path(side)
        ) from exc
    if not isinstance(raw, dict) or not _is_meta(raw):
        schema = raw.get("schema") if isinstance(raw, dict) else None
        raise InvalidSidecarError(
            f"Nieznany schemat sidecara {schema!r} (oczekiwano {_SCHEMA}): {side}",
            path=Path(side),
        )
    name = os.path.basename(side)
    return _typed(raw, name.removesuffix(_META_SUFFIX).split(".", 1)[0])


def read_sidecar(path: str | Path) -> Sidecar:
    """Read the sidecar of a store file, tolerating older releases.

    Parameters
    ----------
    path : str or Path
        A data file (its ``<name>.meta.json`` is read) or the sidecar itself.
        The data file is never opened.

    Returns
    -------
    Sidecar
        Typed fields of ``kartograf-meta/1``, the raw JSON and the derived
        data year/date, campaign, edition, full sheet, coverage and unit.
        Missing information of an old sidecar stays ``None``; the year of
        the data is never taken from ``downloaded_at``.

    Raises
    ------
    InvalidSidecarError
        The sidecar is missing, unreadable, not a JSON object or of another
        schema (``path`` attribute = the sidecar path).
    """
    given = Path(path)
    side = (
        given
        if given.name.endswith(_META_SUFFIX)
        else given.with_name(given.name + _META_SUFFIX)
    )
    return _load(side)


def _descriptor_bases(descriptor: SourceDescriptor) -> Iterator[tuple[str, str]]:
    """Segments of a template resolved as the writers do, with their labels."""
    template = descriptor.storage_subdir
    if "{vcrs}" in template:
        for variant in descriptor.variants:
            if variant.vertical_crs is None:
                continue
            systems: tuple[str | None, ...] = (
                variant.systems if "{system}" in template else (None,)
            )
            for system in systems:
                resolved = descriptor.resolve_subdir(
                    system=system, vertical_crs=variant.vertical_crs
                )
                if "{" in resolved:
                    continue
                label = variant.vertical_crs
                if system is not None:
                    label = f"{_system_label(system)} · {label}"
                yield resolved, label
    elif "{system}" in template:
        indexed = {
            system
            for channel in descriptor.channels
            if isinstance(channel.params, SheetIndexParams)
            for system in channel.params.systems
        }
        for name in sorted(indexed):
            yield descriptor.resolve_subdir(system=name), _system_label(name)
    else:
        yield template, ""


def _system_label(system: str) -> str:
    return f"PL-{system}" if system in ("1992", "2000") else system.upper()


def _content_variant(descriptor: SourceDescriptor, suffix: str) -> str | None:
    """Return the label of the content tokens ``suffix``, or ``None``.

    The label is given when the descriptor's writer produces them
    (``content_segment``, rules 8-9).
    """
    parts = suffix.split("_") if suffix else []
    key = descriptor.key
    if key == "pl.gugik.bdot10k":
        # landcover/manager.py: gpkg, gpkg_zip (keep_raw), shp, gpkg_<layers>.
        if parts in (["gpkg"], ["gpkg", "zip"], ["shp"]):
            return " · " + " ".join(parts).upper()
        if len(parts) == 2 and parts[0] == "gpkg":
            classes = parts[1].split("-")
            if all(re.fullmatch(r"[a-z]{4}", c) for c in classes) and classes == sorted(
                set(classes)
            ):
                return f" · GPKG · {', '.join(c.upper() for c in classes)}"
    if key == "eu.clms.corine":
        from kartograf.providers.corine import CorineProvider

        year = _year(parts[0]) if parts else None
        if parts[1:] == ["preview"] and year in CorineProvider.AVAILABLE_YEARS:
            return f" · {parts[0]} · podglad"
        if len(parts) == 1 and year in CorineProvider.CLMS_YEARS:
            return f" · {parts[0]}"
    if key == "global.isric.soilgrids":
        from kartograf.providers.soilgrids import SoilGridsProvider

        if (
            len(parts) == 3
            and parts[0] in SoilGridsProvider.PROPERTIES
            and parts[1] in SoilGridsProvider.depths_for(parts[0])
            and parts[2] in (s.lower() for s in SoilGridsProvider.STATS)
        ):
            return " · " + " · ".join(parts)
    if not parts:
        # The prefix itself is a segment when a channel needs no tokens.
        for channel in descriptor.channels:
            params = channel.params
            if isinstance(params, UnitPackageParams) and any(
                not v.segment_tokens for v in params.variants
            ):
                return ""
            if isinstance(params, AtomFilesParams) and not params.segment_tokens:
                return ""
            if (
                isinstance(params, FeatureBBoxParams)
                and params.selection == "all"
                and not params.choice
            ):
                return ""
        return None
    for channel in descriptor.channels:
        params = channel.params
        if isinstance(params, UnitPackageParams):
            for variant in params.variants:
                base = tuple(variant.segment_tokens)
                if tuple(parts) == base:
                    return " · " + " · ".join(parts)
                if (
                    len(parts) == len(base) + 1
                    and tuple(parts[: len(base)]) == base
                    and variant.classes
                ):
                    classes = parts[-1].upper().split("-")
                    if classes == sorted(set(classes)) and all(
                        c in variant.classes for c in classes
                    ):
                        return " · " + " · ".join((*base, ", ".join(classes)))
        elif isinstance(params, AtomFilesParams):
            base = tuple(params.segment_tokens)
            if tuple(parts) == base and base and len(params.crs) <= 1:
                return " · " + " · ".join(parts)
            if (
                len(params.crs) > 1
                and len(parts) == len(base) + 1
                and tuple(parts[: len(base)]) == base
                and parts[-1] in (crs.removeprefix("EPSG:") for crs in params.crs)
            ):
                return " · " + " · ".join(parts)
        elif isinstance(params, FeatureBBoxParams):
            base = tuple(value.lower() for _, value in params.choice)
            if params.selection == "all" and tuple(parts) == base:
                return " · " + " · ".join(parts)
            if (
                params.selection == "level"
                and tuple(parts[:-1]) == base
                and parts[-1] in (layer.code.lower() for layer in params.layers)
            ):
                return " · " + " · ".join(parts)
    return None


# Sources whose ``storage_subdir`` is only a prefix: the land cover manager
# always completes it with content tokens (rule 8).
_PREFIX_ONLY = frozenset(
    {"pl.gugik.bdot10k", "eu.clms.corine", "global.isric.soilgrids"}
)
_COLLECTION_PARAMS = (UnitPackageParams, AtomFilesParams, FeatureBBoxParams)


def _bare_template(descriptor: SourceDescriptor) -> bool:
    """Check whether a fixed template is itself a segment (no content tokens)."""
    if descriptor.key in _PREFIX_ONLY:
        return False
    collection = any(
        isinstance(channel.params, _COLLECTION_PARAMS)
        for channel in descriptor.channels
    )
    return not collection or _content_variant(descriptor, "") is not None


@lru_cache(maxsize=1)
def _registered_segments() -> dict[str, tuple[SourceDescriptor, str]]:
    return {
        segment: (descriptor, label)
        for descriptor in all_sources()
        if "{" in descriptor.storage_subdir or _bare_template(descriptor)
        for segment, label in _descriptor_bases(descriptor)
    }


def _orto_variant(segment: str) -> tuple[SourceDescriptor, str] | None:
    """Orthophoto colour variants (E12) and WCS cutouts (ADR-042 D14)."""
    for key in ("pl.gugik.orto", "pl.gugik.true_orto"):
        descriptor = get_source(key)
        for base, base_label in _descriptor_bases(descriptor):
            if not segment.startswith(base + "_"):
                continue
            suffix = segment[len(base) + 1 :]
            if key == "pl.gugik.orto" and suffix in _ORTO_COLORS:
                return descriptor, f"{base_label} · {_ORTO_COLORS[suffix]}"
            wcs = [
                c.params
                for c in descriptor.channels
                if isinstance(c.params, WcsCutoutParams)
            ]
            # Cutouts are PL-1992 only (download/orto_cutout.py): with several
            # WCS variants ``<coverage>_<res>``, otherwise ``<res>``.
            if base != descriptor.resolve_subdir(system="1992"):
                continue
            tokens = suffix.split("_")
            if len(wcs) > 1 and len(tokens) == 2:
                coverage, resolution = tokens
                choices = [c for c in wcs if c.variant == coverage]
            elif len(wcs) == 1 and len(tokens) == 1:
                resolution = tokens[0]
                choices = wcs
            else:
                continue
            value = parse_resolution(resolution)
            if value is not None and any(value in c.resolutions for c in choices):
                return descriptor, f"{base_label} · {' · '.join(tokens)}"
    return None


@lru_cache(maxsize=1024)
def describe_segment(segment: str) -> SegmentInfo:
    """Which registered source and variant a store segment holds.

    The inverse of the writers' segment rules (``resolve_subdir``,
    ``content_segment``, orthophoto variants and cutouts, HSG): a segment no
    registered descriptor produces is ``known=False``, never a guess.

    Parameters
    ----------
    segment : str
        ``<product>/<variant>``, e.g. ``"nmt/pl_1992_1m_evrf2007"``.

    Returns
    -------
    SegmentInfo
        Product, country, descriptor key and a human name: the descriptor
        name and the variant (system, height system, resolution, format,
        year, level...), e.g. ``"Numeryczny Model Terenu 1 m (siatka ASC) ·
        PL-1992 · EVRF2007"``.
    """
    found = _registered_segments().get(segment)
    if found is None and segment.startswith("hsg/global_soilgrids_"):
        from kartograf.providers.soilgrids import SoilGridsProvider

        # HSG (no descriptor, landcover/store.py): always the mean texture.
        tokens = segment.removeprefix("hsg/global_soilgrids_").split("_")
        if tokens[1:] == ["mean"] and tokens[0] in SoilGridsProvider.DEPTHS:
            soil = get_source("global.isric.soilgrids")
            return SegmentInfo(
                segment,
                "hsg",
                soil.country,
                soil.key,
                "Grupy hydrologiczne gleb HSG (z SoilGrids) · " + " · ".join(tokens),
                True,
            )
    if found is None:
        for descriptor in all_sources():
            prefix = descriptor.storage_subdir
            if "{" not in prefix and segment.startswith(prefix + "_"):
                variant = _content_variant(descriptor, segment[len(prefix) + 1 :])
                if variant is not None:
                    found = (descriptor, variant)
                    break
    if found is None:
        found = _orto_variant(segment)
    if found is None:
        return SegmentInfo(segment, None, None, None, segment, False)
    descriptor, label = found
    if label and not label.startswith(" · "):
        label = " · " + label
    return SegmentInfo(
        segment,
        descriptor.product,
        descriptor.country,
        descriptor.key,
        descriptor.name + label,
        True,
    )


def list_segments(output_dir: str | Path) -> list[str]:
    """Segments of the store: every ``<product>/<variant>`` directory.

    Includes segments the registry does not know (``iter_store`` reports them
    as ``unknown_segment``); skips symlinks and names starting with ``.``.
    Cost: one listing of ``output_dir`` and one of each product directory.

    Parameters
    ----------
    output_dir : str or Path
        The ``data/`` directory (not its parent).

    Returns
    -------
    list of str
        Sorted ``"<product>/<variant>"`` names, ready for ``iter_store(...,
        segment=...)`` (e.g. one call per segment in a thread pool).

    Raises
    ------
    OSError
        ``output_dir`` cannot be listed (missing, a disconnected share).
    """
    root = os.path.normpath(os.fspath(output_dir))
    found: list[str] = []
    for product in _directories(root, required=True):
        found.extend(
            f"{product}/{variant}"
            for variant in _directories(os.path.join(root, product))
        )
    return sorted(found)


def _directories(path: str, *, required: bool = False) -> list[str]:
    """Real (non-symlink) subdirectories not starting with ``.``."""
    try:
        with os.scandir(path) as entries:
            return sorted(
                entry.name
                for entry in entries
                if not entry.name.startswith(".")
                and entry.is_dir(follow_symlinks=False)
            )
    except (FileNotFoundError, NotADirectoryError):
        if required:
            raise
        return []  # removed during the scan


def _listing(path: str) -> list[tuple[str, bool]] | None:
    """Sorted ``(name, is_real_directory)`` of a directory; ``None`` if absent.

    ``DirEntry.is_dir(follow_symlinks=False)`` uses the entry type of the
    listing (ext4, XFS, NTFS, SMB/CIFS): no ``stat`` per entry.
    """
    try:
        with os.scandir(path) as entries:
            found = [
                (entry.name, entry.is_dir(follow_symlinks=False)) for entry in entries
            ]
    except (FileNotFoundError, NotADirectoryError):
        return None
    found.sort()
    return found


def _data_names(listing: list[tuple[str, bool]]) -> list[str]:
    """Files that are not sidecars, hidden files or directories."""
    return [
        name
        for name, is_dir in listing
        if not is_dir and not name.startswith(".") and not name.endswith(_META_SUFFIX)
    ]


def _matches(name: str, stems: Set[str]) -> bool:
    """``name`` is ``<stem>.<extension...>`` of a wanted unit code."""
    index = name.find(".")
    while index > 0:
        if name[:index] in stems:
            return True
        index = name.find(".", index + 1)
    return False


def _problem(
    problem: ProblemCode,
    segment: str,
    hierarchy: str,
    path: Path,
    *,
    label: str | None = None,
    sha8: str | None = None,
    sidecar: Sidecar | None = None,
) -> StoreEntry:
    return StoreEntry(
        "problem",
        segment,
        hierarchy,
        path.name,
        path,
        None,
        label,
        sha8,
        sidecar,
        problem,
    )


def _read_problem(exc: InvalidSidecarError) -> ProblemCode:
    vanished = isinstance(exc.__cause__, FileNotFoundError)
    return "missing_sidecar" if vanished else "invalid_sidecar"


def _version_of_link(link: Path, rel: str) -> Path | None:
    """Return the version a link sidecar names, if it lies in the link's own slot.

    Lexical, without I/O: ``<base>/[full_sheet/]<hierarchy>/<name>`` may only
    point at ``<base>/versions/<hierarchy>/<label>_<sha8>/<name>``. The
    result is built from the link path itself, so it has the same form
    (relative or absolute) as the paths ``iter_store`` yields.
    """
    if not rel:
        return None
    link_dir = os.path.normpath(link.parent)
    target = PurePath(os.path.normpath(os.path.join(link_dir, rel)))
    if target.name != link.name or not _VERSION_DIR.fullmatch(target.parent.name):
        return None
    own = PurePath(link_dir).parts
    anchor = own
    if target.is_absolute() and not PurePath(link_dir).is_absolute():
        anchor = PurePath(os.path.abspath(link_dir)).parts
    offset = len(anchor) - len(own)
    slot = target.parent.parent.parts
    for k, part in enumerate(slot):
        if part != VERSIONS_DIR or slot[:k] != anchor[:k]:
            continue
        hierarchy = slot[k + 1 :]
        if not hierarchy or k < offset:
            continue
        rest = anchor[k:]
        if rest in (hierarchy, (FULL_SHEET_DIR, *hierarchy)):
            return Path(*own[: k - offset], VERSIONS_DIR, *hierarchy).joinpath(
                target.parent.name, target.name
            )
    return None


def _slot_version(
    directory: str, name: str, rel: str, slot: str
) -> re.Match[str] | None:
    """Return the version match of the link ``<directory>/<name>``, or ``None``.

    Used for ``_version_of_link`` when the scan knows its versions ``slot``: the
    ``<label>_<sha8>`` match of the version directory of ``slot`` that ``rel``
    names.

    The same lexical rule on normalized strings, without ``pathlib``: an
    absolute ``rel`` of a relative store is compared absolutely.
    """
    if not rel:
        return None
    head, file = os.path.split(os.path.normpath(os.path.join(directory, rel)))
    if file != name:
        return None
    parent, version = os.path.split(head)
    if parent != slot and not (
        os.path.isabs(parent)
        and not os.path.isabs(slot)
        and parent == os.path.abspath(slot)
    ):
        return None
    return _VERSION_DIR.fullmatch(version)


def _link_entry(
    kind: EntryKind, segment: str, level: str, directory: str, name: str, slot: str
) -> StoreEntry:
    file = os.path.join(directory, name)
    path = Path(file)
    try:
        meta = _load(file + _META_SUFFIX)
    except InvalidSidecarError as exc:
        return _problem(_read_problem(exc), segment, level, path)
    extra = meta.extra or {}
    rel = extra.get("link_target")
    match = None
    if level and extra.get("link") == "hardlink" and isinstance(rel, str):
        match = _slot_version(directory, name, rel, slot)
    if match is not None:
        target: Path | None = Path(slot, match[0], name)
        label, sha8 = match[1], match[2]
    else:
        target = None
        version = _dict(extra.get("version")) or {}
        label = _text(version.get("label"))
        sha8 = meta.sha256[:8] if meta.sha256 is not None else None
    return StoreEntry(kind, segment, level, name, path, target, label, sha8, meta, None)


def _link_files(
    directory: str,
    segment: str,
    level: str,
    slot: str,
    kind: EntryKind,
    listing: list[tuple[str, bool]],
    wanted: Set[str] | None = None,
) -> Iterator[StoreEntry]:
    """Yield the links of one directory of hierarchy ``level``.

    The ``slot`` is its ``versions/`` directory, the only place its links may
    point at.
    """
    names = {name for name, _ in listing}
    for name in _data_names(listing):
        if wanted is not None and not _matches(name, wanted):
            continue
        if name + _META_SUFFIX in names:
            yield _link_entry(kind, segment, level, directory, name, slot)
        else:
            yield _problem("missing_sidecar", segment, level, Path(directory, name))


def _valid_version(raw: dict[str, Any], sha8: str) -> bool:
    """Return the validity rule of ``download.versions.read_version``.

    ``sha256`` starting with the directory's ``sha8`` and ``extra.version`` with
    ``label`` and ``label_source``.
    """
    extra = raw.get("extra")
    version = extra.get("version") if isinstance(extra, dict) else None
    sha256 = raw.get("sha256")
    return (
        isinstance(version, dict)
        and "label" in version
        and "label_source" in version
        and isinstance(sha256, str)
        and sha256.startswith(sha8)
    )


def _skipped(
    segment: str, level: str, name: str, path: Path, label: str, sha8: str
) -> StoreEntry:
    return StoreEntry(
        "version", segment, level, name, path, path, label, sha8, None, None, True
    )


def _version_files(
    directory: str,
    segment: str,
    level: str,
    match: re.Match[str],
    skip: _Skip,
    wanted: Set[str] | None = None,
) -> Iterator[StoreEntry]:
    """Files of the version directory ``<level>/<label>_<sha8>`` (``match``)."""
    label, sha8 = match[1], match[2]
    skipped = False
    if skip is not None:
        key = f"{segment}/{VERSIONS_DIR}/{level}/{match[0]}"
        if isinstance(skip, Set):
            skipped = key in skip
        elif key in skip:  # a mapping: the caller's names, without a listing
            for name in _known_names(key, skip[key]):
                if wanted is None or _matches(name, wanted):
                    path = Path(directory, name)
                    yield _skipped(segment, level, name, path, label, sha8)
            return
    listing = _listing(directory)
    if listing is None:
        return
    names = {name for name, _ in listing}
    for name in _data_names(listing):
        if wanted is not None and not _matches(name, wanted):
            continue
        file = os.path.join(directory, name)
        path = Path(file)
        if name + _META_SUFFIX not in names:
            yield _problem(
                "missing_sidecar", segment, level, path, label=label, sha8=sha8
            )
            continue
        if skipped:
            yield _skipped(segment, level, name, path, label, sha8)
            continue
        try:
            meta = _load(file + _META_SUFFIX)
        except InvalidSidecarError as exc:
            yield _problem(
                _read_problem(exc), segment, level, path, label=label, sha8=sha8
            )
            continue
        if not _valid_version(meta.raw, sha8):
            yield _problem(
                "invalid_sidecar",
                segment,
                level,
                path,
                label=label,
                sha8=sha8,
                sidecar=meta,
            )
            continue
        yield StoreEntry(
            "version", segment, level, name, path, path, label, sha8, meta, None
        )


def _version_match(name: str) -> re.Match[str] | None:
    """``<label>_<sha8>`` of a version directory name.

    Most hierarchy names (``130``, ``D``, ``teryt``) are rejected without the regex.
    """
    if len(name) < 10 or name[-9] != "_":
        return None
    return _VERSION_DIR.fullmatch(name)


def _version_dirs(
    listing: list[tuple[str, bool]],
) -> Iterator[tuple[str, re.Match[str]]]:
    """Version directories of a hierarchy directory below ``versions/``."""
    for name, is_dir in listing:
        if is_dir and not name.startswith("."):
            match = _version_match(name)
            if match is not None:
                yield name, match


def _child(level: str, name: str) -> str:
    return f"{level}/{name}" if level else name


def _walk_links(
    directory: str, segment: str, level: str, slot: str, kind: EntryKind
) -> Iterator[StoreEntry]:
    """Yield the entries of a directory depth first.

    Files of a directory come before its subdirectories (``slot``: the
    ``versions/`` directory of ``level``).
    """
    listing = _listing(directory)
    if listing is None:
        return
    yield from _link_files(directory, segment, level, slot, kind, listing)
    for name, is_dir in listing:
        if is_dir and not name.startswith("."):
            yield from _walk_links(
                os.path.join(directory, name),
                segment,
                _child(level, name),
                os.path.join(slot, name),
                kind,
            )


def _walk_versions(
    directory: str, segment: str, level: str, skip: _Skip
) -> Generator[StoreEntry, None, bool]:
    """Version directories below ``versions/``.

    Returns whether the staging directory ``.incoming`` exists (seen in the listing of
    the root).
    """
    listing = _listing(directory)
    if listing is None:
        return False
    incoming = False
    for name, is_dir in listing:
        if not is_dir:
            continue  # files outside version directories are not versions
        if name.startswith("."):
            incoming = incoming or (not level and name == INCOMING_DIR)
            continue
        path = os.path.join(directory, name)
        match = _version_match(name) if level else None
        if match is not None:
            yield from _version_files(path, segment, level, match, skip)
        else:
            yield from _walk_versions(path, segment, _child(level, name), skip)
    return incoming


def _newest_mtime(path: str) -> float:
    """Freshness of a staging entry as the writer judges it (lstat only)."""
    info = os.lstat(path)
    newest = info.st_mtime
    if stat.S_ISDIR(info.st_mode):
        with os.scandir(path) as entries:
            for entry in entries:
                newest = max(newest, _newest_mtime(entry.path))
    return newest


def _stale_incoming(base: str, segment: str) -> Iterator[StoreEntry]:
    """Staging entries the next writer would remove (older than 24 h)."""
    incoming = os.path.join(base, VERSIONS_DIR, INCOMING_DIR)
    limit = time.time() - STALE_AFTER_S
    listing = _listing(incoming) or []
    for name, _ in listing:
        try:
            stale = _newest_mtime(os.path.join(incoming, name)) < limit
        except OSError:
            continue  # a writer may remove its staging directory meanwhile
        if stale:
            yield _problem("stale_incoming", segment, "", Path(incoming, name))


def _segment_entries(base: str, segment: str, skip: _Skip) -> Iterator[StoreEntry]:
    """Every entry of one segment: links, ``full_sheet``, versions, leftovers."""
    listing = _listing(base)
    if listing is None:
        return
    if not describe_segment(segment).known:
        yield _problem("unknown_segment", segment, "", Path(base))
    versions = os.path.join(base, VERSIONS_DIR)
    yield from _link_files(base, segment, "", versions, "link", listing)
    directories = [name for name, is_dir in listing if is_dir]
    for name in directories:
        if name not in _RESERVED and not name.startswith("."):
            yield from _walk_links(
                os.path.join(base, name),
                segment,
                name,
                os.path.join(versions, name),
                "link",
            )
    if FULL_SHEET_DIR in directories:
        yield from _walk_links(
            os.path.join(base, FULL_SHEET_DIR), segment, "", versions, "full_sheet"
        )
    incoming = False
    if VERSIONS_DIR in directories:
        incoming = yield from _walk_versions(versions, segment, "", skip)
    if _LEGACY_DIR in directories:
        yield _problem("legacy_campaigns", segment, "", Path(base, _LEGACY_DIR))
    if incoming:
        yield from _stale_incoming(base, segment)


def _segment_level(base: str, segment: str) -> Iterator[StoreEntry]:
    """Yield the entries of the partition ``"."`` of a segment.

    The segment's own problems and the files directly in the segment directory and in
    ``full_sheet/`` (hierarchy ``""``).
    """
    listing = _listing(base)
    if listing is None:
        return
    if not describe_segment(segment).known:
        yield _problem("unknown_segment", segment, "", Path(base))
    versions = os.path.join(base, VERSIONS_DIR)
    yield from _link_files(base, segment, "", versions, "link", listing)
    directories = {name for name, is_dir in listing if is_dir}
    if FULL_SHEET_DIR in directories:
        full = os.path.join(base, FULL_SHEET_DIR)
        found = _listing(full)
        if found is not None:
            yield from _link_files(full, segment, "", versions, "full_sheet", found)
    if _LEGACY_DIR in directories:
        yield _problem("legacy_campaigns", segment, "", Path(base, _LEGACY_DIR))
    if VERSIONS_DIR in directories and (INCOMING_DIR, True) in (
        _listing(versions) or ()
    ):
        yield from _stale_incoming(base, segment)


def _partition_entries(
    base: str, segment: str, parts: tuple[str, ...], exact: bool, skip: _Skip
) -> Iterator[StoreEntry]:
    """Entries of one partition of ``list_partitions``.

    The slot ``parts`` (``exact``) or the slot and every slot below it, in the three
    trees.
    """
    if not parts:
        yield from _segment_level(base, segment)
        return
    level = "/".join(parts)
    slot = os.path.join(base, VERSIONS_DIR, *parts)
    known: dict[str, bool] = {}
    for prefix, kind in _LINK_DIRS:
        if not prefix and parts[0] in _RESERVED:
            continue  # versions/, full_sheet/, kampanie/: not a hierarchy
        directory = _real_directory(base, (*prefix, *parts), known)
        if directory is None:
            continue
        if not exact:
            yield from _walk_links(directory, segment, level, slot, kind)
            continue
        listing = _listing(directory)
        if listing is not None:
            yield from _link_files(directory, segment, level, slot, kind, listing)
    if any(_version_match(part) is not None for part in parts[1:]):
        return  # below the first level such a name is a version directory
    versions = _real_directory(base, (VERSIONS_DIR, *parts), known)
    if versions is None:
        return
    if not exact:
        yield from _walk_versions(versions, segment, level, skip)
        return
    for name, match in _version_dirs(_listing(versions) or []):
        yield from _version_files(
            os.path.join(versions, name), segment, level, match, skip
        )


# A directory of the hierarchy while ``list_partitions`` splits: its names
# below the segment and its directories in the link, ``full_sheet/`` and
# ``versions/`` trees (``None`` where absent).
_Node = tuple[tuple[str, ...], list[str | None]]


def _split(dirs: list[str | None]) -> tuple[dict[str, list[str | None]], bool]:
    """Split the subdirectories of one hierarchy directory by name.

    The three trees are link, ``full_sheet/`` and ``versions/``; the flag tells
    whether its own slot has entries.
    """
    children: dict[str, list[str | None]] = {}
    own = False
    for tree, directory in enumerate(dirs):
        if directory is None:
            continue
        for name, is_dir in _listing(directory) or []:
            if name.startswith("."):
                continue
            if not is_dir:
                own = own or (tree < 2 and not name.endswith(_META_SUFFIX))
            elif tree == 2 and _version_match(name) is not None:
                own = True
            else:
                children.setdefault(name, [None, None, None])[tree] = os.path.join(
                    directory, name
                )
    return children, own


def _sheet_parts(code: str) -> tuple[str, ...]:
    """Return the hierarchy of a sheet code as the writers build it.

    The writers are ``unit_slot`` and ``FileStorage``: ZTM map sheets by
    ``cuzk_map_path_parts``, PL codes in their canonical form (``SheetParser``),
    CZ sheets and tiles and raw tile identifiers by ``path_parts``.
    """
    if parser_registry.ztm_sheet_system(code):
        return tuple(parser_registry.cuzk_map_path_parts(code))
    with contextlib.suppress(ValidationError):  # incl. ParseError: not PL
        code = SheetParser(code).sheet
    return tuple(parser_registry.path_parts(code))


def _unit_kinds(segment: str) -> frozenset[str]:
    """Return the unit kinds of the segment's package channels (``powiat``...)."""
    key = describe_segment(segment).dataset_key
    if key is None:
        return frozenset()
    return frozenset(
        channel.params.unit
        for channel in get_source(key).channels
        if isinstance(channel.params, UnitPackageParams)
    )


def _unit_slot(
    segment: str, unit: str, kinds: frozenset[str]
) -> tuple[tuple[str, ...], str | None]:
    """``(slot directory below the segment, file stem)`` of one unit.

    A stem ``None`` = every file of the directory (the slot of one sheet).
    """
    if not isinstance(unit, str) or any(c in unit for c in ("\\", "\x00", ":")):
        raise ValidationError(
            f"Nieprawidlowa jednostka magazynu: {unit!r}", option="units"
        )
    *directory, code = unit.split("/")
    if (
        any(
            not part or part.startswith(".") or len(part.encode()) > _NAME_MAX
            for part in (*directory, code)
        )
        or (directory and directory[0] in _RESERVED)
        or code in _RESERVED
    ):
        raise ValidationError(
            f"Nieprawidlowa jednostka magazynu: {unit!r}", option="units"
        )
    if directory:
        if tuple(directory) == _sheet_parts(code):
            return tuple(directory), None
        return tuple(directory), code
    if _BBOX_UNIT.fullmatch(code):
        return ("bbox",), code
    # A segment of sheets or tiles only has no TERYT: a bare number there is a
    # sheet code (the ZTM 1:100000 sheet ``0510``).
    if _TERYT.fullmatch(code) and not (kinds and kinds <= _CODE_KINDS):
        return ("ku",) if _KU.fullmatch(code) and "ku" in kinds else ("teryt",), code
    if _COUNTRY.fullmatch(code):
        return ("country",), code
    parts = _sheet_parts(code)
    if any(
        not part
        or part.startswith(".")
        or "/" in part
        or len(part.encode()) > _NAME_MAX
        for part in parts
    ):
        raise ValidationError(
            f"Nieprawidlowa jednostka magazynu: {unit!r}", option="units"
        )
    return parts, None


def _unit_groups(
    segment: str, units: Iterable[str]
) -> dict[tuple[str, ...], frozenset[str] | None]:
    """Return the slot directories of the units with the wanted file stems.

    ``None`` stands for the whole directory; the order is that of the units.
    """
    if isinstance(units, str):
        raise ValidationError(
            f"units: podaj kolekcje nazw jednostek, nie napis ({units!r})",
            option="units",
        )
    kinds = _unit_kinds(segment)
    groups: dict[tuple[str, ...], set[str] | None] = {}
    for unit in units:
        directory, stem = _unit_slot(segment, unit, kinds)
        if stem is None:
            groups[directory] = None
        elif directory not in groups:
            groups[directory] = {stem}
        else:
            stems = groups[directory]
            if stems is not None:
                stems.add(stem)
    return {
        directory: None if stems is None else frozenset(stems)
        for directory, stems in groups.items()
    }


def _real_directory(
    base: str, parts: tuple[str, ...], known: dict[str, bool]
) -> str | None:
    """Return ``base/parts`` when every component is a real directory.

    No symlink leads out of the store; ``lstat`` results are shared between
    units.
    """
    path = base
    for part in parts:
        path = os.path.join(path, part)
        real = known.get(path)
        if real is None:
            try:
                real = stat.S_ISDIR(os.lstat(path).st_mode)
            except (FileNotFoundError, NotADirectoryError):
                real = False
            except OSError as exc:
                if exc.errno == errno.ENAMETOOLONG:
                    raise ValidationError(
                        f"Jednostka magazynu daje zbyt dluga sciezke: {path}",
                        option="units",
                    ) from exc
                raise
            known[path] = real
        if not real:
            return None
    return path


def _unit_entries(
    base: str,
    segment: str,
    groups: dict[tuple[str, ...], frozenset[str] | None],
    skip: _Skip,
) -> Iterator[StoreEntry]:
    """Entries of the units' slots only; no other directory is listed."""
    known: dict[str, bool] = {}
    for hierarchy, wanted in groups.items():
        level = "/".join(hierarchy)
        slot = os.path.join(base, VERSIONS_DIR, *hierarchy)
        for prefix, kind in _LINK_DIRS:
            directory = _real_directory(base, (*prefix, *hierarchy), known)
            listing = _listing(directory) if directory is not None else None
            if directory is not None and listing is not None:
                yield from _link_files(
                    directory, segment, level, slot, kind, listing, wanted
                )
        versions = _real_directory(base, (VERSIONS_DIR, *hierarchy), known)
        listing = _listing(versions) if versions is not None else None
        if versions is None or listing is None:
            continue
        for name, match in _version_dirs(listing):
            yield from _version_files(
                os.path.join(versions, name), segment, level, match, skip, wanted
            )


def _validated_segment(segment: str) -> tuple[str, str]:
    parts = segment.split("/") if isinstance(segment, str) else []
    if (
        len(parts) != 2
        or any(c in segment for c in ("\\", "\x00", ":"))
        or any(not part or part.startswith(".") for part in parts)
    ):
        raise ValidationError(
            f"Nieprawidlowy segment magazynu: {segment!r} (oczekiwano "
            "<produkt>/<wariant>, np. nmt/pl_1992_1m_evrf2007)",
            option="segment",
        )
    return parts[0], parts[1]


def _single_name(name: object) -> bool:
    """One non-hidden directory entry name.

    Never a path, a drive or longer than file systems accept (``NAME_MAX``).
    """
    return (
        isinstance(name, str)
        and name != ""
        and not name.startswith(".")
        and not any(separator in name for separator in _SEPARATORS)
        and not os.path.splitdrive(name)[0]
        and len(name.encode()) <= _NAME_MAX
    )


def _partition_scope(partition: str) -> tuple[tuple[str, ...], bool]:
    """``(hierarchy directories, exact)`` of a ``list_partitions`` key.

    ``((), True)`` for the segment level ``"."``.
    """
    if partition == ".":
        return (), True
    exact = isinstance(partition, str) and partition.endswith("/.")
    parts = (
        tuple((partition[:-2] if exact else partition).split("/"))
        if isinstance(partition, str)
        else ()
    )
    if not parts or not all(_single_name(part) for part in parts):
        raise ValidationError(
            f"Nieprawidlowa czesc segmentu: {partition!r} (oczekiwano klucza "
            'z list_partitions: ".", "<katalog>[/<katalog>...]" albo '
            '"<katalog>[/<katalog>...]/.")',
            option="partition",
        )
    return parts, exact


def _known_versions(
    skip_versions: Collection[str] | Mapping[str, Collection[str]] | None,
) -> _Skip:
    if skip_versions is None:
        return None
    if isinstance(skip_versions, str):
        raise ValidationError(
            "skip_versions: podaj kolekcje sciezek katalogow wersji, nie napis",
            option="skip_versions",
        )
    if isinstance(skip_versions, (Set, Mapping)):
        return skip_versions
    return frozenset(skip_versions)


def _known_names(key: str, names: Collection[str]) -> list[str]:
    """Return the file names a ``skip_versions`` mapping gives for a version.

    The names are of one version directory, in listing order; only plain names of
    data files.
    """
    if (
        isinstance(names, str)
        or not isinstance(names, Collection)
        or not all(
            _single_name(name) and not name.endswith(_META_SUFFIX) for name in names
        )
    ):
        raise ValidationError(
            f"skip_versions[{key!r}]: podaj nazwy plikow danych wersji (bez "
            f"sidecarow, sciezek i nazw ukrytych), nie {names!r}",
            option="skip_versions",
        )
    return sorted(set(names))  # a listing never repeats a name


def _segment_dir(root: str, segment: str) -> str | None:
    """Return the segment directory, ``None`` when absent.

    A missing ``root`` is ``OSError``, a symlinked product or segment
    ``ValidationError``.
    """
    os.stat(root)  # a missing store is an error, a missing segment is not
    path = root
    for part in segment.split("/"):
        path = os.path.join(path, part)
        try:
            mode = os.lstat(path).st_mode
        except (FileNotFoundError, NotADirectoryError):
            return None
        if stat.S_ISLNK(mode):
            raise ValidationError(
                f"Segment magazynu jest dowiazaniem: {path}", option="segment"
            )
        if not stat.S_ISDIR(mode):
            return None
    return os.path.normpath(path)


def _scan_store(root: str, segments: list[str], skip: _Skip) -> Iterator[StoreEntry]:
    for segment in segments:
        base = os.path.normpath(os.path.join(root, *segment.split("/")))
        yield from _segment_entries(base, segment, skip)


def list_partitions(
    output_dir: str | Path, segment: str, *, target: int = 32
) -> list[str]:
    """Disjoint parts of one segment for parallel ``iter_store`` calls.

    The union of ``iter_store(output_dir, segment=segment, partition=key)``
    over the returned keys is exactly ``iter_store(output_dir,
    segment=segment)``: the same entries, none twice. A part covers the same
    hierarchy under the standard path, ``full_sheet/`` and ``versions/``.
    The first-level hierarchy directories are split level by level into
    their subdirectories while there are fewer than ``target`` parts and a
    directory to split. Cost: one listing of the segment, ``full_sheet/``
    and ``versions/`` plus at most three listings per directory examined
    for a split (its own directory in each of the three trees).

    Parameters
    ----------
    output_dir : str or Path
        The ``data/`` directory (not its parent).
    segment : str
        A ``<product>/<variant>`` segment (``list_segments``).
    target : int, default 32
        Number of parts to aim at (e.g. a few times the threads); a segment
        with fewer hierarchy directories gives fewer parts.

    Returns
    -------
    list of str
        ``"."`` first - the segment level: ``unknown_segment``,
        ``legacy_campaigns``, ``stale_incoming`` and the files directly in
        the segment directory and ``full_sheet/``; then, sorted by
        hierarchy, ``"<dir>[/<dir>...]"`` - that slot and every slot below
        it - and ``"<dir>[/<dir>...]/."`` - only that slot's own files and
        versions, when its subdirectories are parts of their own. Empty for
        a missing segment.

    Raises
    ------
    ValidationError
        A malformed segment or ``target``, a segment directory that is a
        symlink.
    OSError
        ``output_dir`` cannot be read (missing, a disconnected share).
    """
    root = os.path.normpath(os.fspath(output_dir))
    _validated_segment(segment)
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValidationError(
            f"target: podaj dodatnia liczbe czesci, nie {target!r}", option="target"
        )
    base = _segment_dir(root, segment)
    listing = _listing(base) if base is not None else None
    if base is None or listing is None:
        return []
    real = {name for name, is_dir in listing if is_dir and not name.startswith(".")}
    nodes: dict[str, list[str | None]] = {
        name: [os.path.join(base, name), None, None] for name in real - _RESERVED
    }
    for tree, top in ((1, FULL_SHEET_DIR), (2, VERSIONS_DIR)):
        if top not in real:
            continue
        directory = os.path.join(base, top)
        for name, is_dir in _listing(directory) or []:
            if is_dir and not name.startswith("."):
                path = os.path.join(directory, name)
                nodes.setdefault(name, [None, None, None])[tree] = path
    keys = ["."]
    frontier: list[_Node] = [((name,), dirs) for name, dirs in sorted(nodes.items())]
    while frontier and len(keys) + len(frontier) < target:
        deeper: list[_Node] = []
        for parts, dirs in frontier:
            children, own = _split(dirs)
            key = "/".join(parts)
            if not children:
                keys.append(key)  # nothing to split: the whole subtree
                continue
            if own:
                keys.append(f"{key}/.")
            deeper.extend(
                ((*parts, name), found) for name, found in sorted(children.items())
            )
        frontier = deeper
    keys.extend("/".join(parts) for parts, _ in frontier)
    return [".", *sorted(keys[1:], key=lambda key: key.split("/"))]


def iter_store(
    output_dir: str | Path,
    *,
    segment: str | None = None,
    units: Iterable[str] | None = None,
    skip_versions: Collection[str] | Mapping[str, Collection[str]] | None = None,
    partition: str | None = None,
) -> Iterator[StoreEntry]:
    """Stream the files of the store and the problems found in it.

    Versions (``versions/<hierarchy>/<label>_<sha8>/``), links of the
    standard path and of ``full_sheet/`` and problems: unknown segments,
    missing or unreadable sidecars, 0.7.x ``kampanie/`` and staging
    directories older than 24 h. A link's ``version_path`` comes from its
    sidecar (``extra.link_target``) without reading the data; confirm it
    on demand with ``link_target``. Cost (ARCHITECTURE 3.3.1): one listing
    per directory and one read per sidecar of a link or version; data files
    are never opened or statted, known versions are not read.

    Parameters
    ----------
    output_dir : str or Path
        The ``data/`` directory (not its parent).
    segment : str, optional
        Only this ``<product>/<variant>`` segment (``list_segments``). Calls
        for different segments, for units or for partitions of one segment
        may run in parallel threads; each iterator belongs to one thread.
    units : iterable of str, optional
        Only the slots of these units of ``segment`` (required), without
        listing the rest of the segment: a sheet code (PL-1992/2000, TM33,
        SM5, ZTM map sheet, LAZ tile), ``teryt/<code>``, ``bbox/<coords>``,
        ``country/<code>``, ``ku/<code>`` or ``<directory>/<file stem>``
        (``2000/7/<tile>`` of a mesh). A bare TERYT, ``<coords>`` or
        country code works too. Exact names, not prefixes; segment-level
        problems are not reported.
    skip_versions : collection of str or mapping of str to names, optional
        Version directories already known to the caller, relative to
        ``output_dir`` with ``/`` (``<segment>/versions/<hierarchy>/<label>_
        <sha8>``). Their files are yielded with ``skipped=True`` and
        ``sidecar=None`` without reading their sidecars: from the directory
        listing for a collection (pass a set for large ones), or - for a
        mapping to the directory's data file names - from those names,
        without even listing the directory (the caller vouches for its
        content: a file removed from or added to it is not seen).
    partition : str, optional
        Only this part of ``segment`` (required; not with ``units``), a key
        of ``list_partitions``. Parts of one call are disjoint and together
        give the whole segment; they may run in parallel threads.

    Returns
    -------
    Iterator[StoreEntry]
        A lazy iterator: an entry is yielded before later directories are
        listed. Order: links, ``full_sheet``, versions, leftovers.

    Raises
    ------
    ValidationError
        ``units`` or ``partition`` without ``segment`` or together, a
        malformed segment, unit or partition (never a path out of the
        store), a segment directory that is a symlink, a ``skip_versions``
        name that is not a plain data file name (when its directory is
        reached).
    OSError
        ``output_dir`` cannot be listed, or the store becomes unreadable
        during the scan (e.g. a disconnected share) - a vanished file or
        directory is not an error.
    """
    root = os.path.normpath(os.fspath(output_dir))
    skip = _known_versions(skip_versions)
    if segment is None:
        if units is not None:
            raise ValidationError(
                "units wymaga segment (jednostki jednego segmentu)", option="units"
            )
        if partition is not None:
            raise ValidationError(
                "partition wymaga segment (czesc jednego segmentu)", option="partition"
            )
        return _scan_store(root, list_segments(root), skip)
    _validated_segment(segment)
    if units is not None and partition is not None:
        raise ValidationError(
            "units albo partition, nie oba naraz", options=("units", "partition")
        )
    groups = _unit_groups(segment, units) if units is not None else None
    scope = _partition_scope(partition) if partition is not None else None
    base = _segment_dir(root, segment)
    if base is None:
        return iter(())
    if groups is not None:
        return _unit_entries(base, segment, groups, skip)
    if scope is not None:
        return _partition_entries(base, segment, *scope, skip)
    return _segment_entries(base, segment, skip)


def link_target(path: str | Path) -> Path | None:
    """Return the version a link path holds, confirmed on disk.

    Reads the link sidecar (``extra.link == "hardlink"``,
    ``extra.link_target``), requires the target to be a version of the
    link's own slot and confirms it with ``download.links.linked_version``:
    the same file by inode, or - on a share without stable inode numbers
    (SMB without ``serverino``) - by content: the same size and the link's
    sha256 equal to the version sidecar's (one full read of the file on
    every call). The link count is not consulted (an SMB client reports 1
    for a path it has just opened, the confirming read included), so a path
    that holds the version's bytes counts as holding it, a hardlink or an
    independent copy alike (a download turns an evident copy back into a
    hardlink). Call it for the links of interest, not for every slot of a
    full scan.

    Parameters
    ----------
    path : str or Path
        A standard path or a ``full_sheet/`` path of the store.

    Returns
    -------
    Path or None
        The version file, in the same form as ``StoreEntry.version_path``;
        ``None`` for a missing file or sidecar, a 0.7.x copy, a target
        outside the slot, a removed version or a path whose content is no
        longer the version's.
    """
    link = Path(path)
    try:
        meta = _load(link.with_name(link.name + _META_SUFFIX))
    except InvalidSidecarError:
        return None
    extra = meta.extra or {}
    rel = extra.get("link_target")
    if extra.get("link") != "hardlink" or not isinstance(rel, str):
        return None
    expected = _version_of_link(link, rel)
    if expected is None:
        return None
    verified = linked_version(link)
    if verified is None or os.path.normcase(
        os.path.abspath(expected)
    ) != os.path.normcase(os.fspath(verified)):
        return None
    return expected
