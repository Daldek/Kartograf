"""Offline store reader contracts (ADR-045): metadata, segments, the scan of
the versioned store, scoped units, skipped versions and verified links."""

import hashlib
import itertools
import json
import os
import random
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kartograf.download.fetch import fetch_version
from kartograf.download.links import ensure_link
from kartograf.download.storage import content_segment, token_segment, unit_slot
from kartograf.download.versions import VersionRef
from kartograf.exceptions import InvalidSidecarError, KartografError, ValidationError
from kartograf.landcover.store import hsg_segment
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.gugik_orto import (
    GugikOrtoProvider,
    cutout_resolution_labels,
    wcs_cutout_channels,
)
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.descriptor import (
    AtomFilesParams,
    FeatureBBoxParams,
    SheetIndexParams,
    UnitPackageParams,
    WcsCutoutParams,
)
from kartograf.sources.registry import all_sources
from kartograf.sources.sidecar import emit_sidecar
from kartograf.store import (
    describe_segment,
    iter_store,
    link_target,
    list_partitions,
    list_segments,
    read_sidecar,
)
from kartograf.transport.atom import atom_segment_tokens

SHEET = "N-34-130-D-d-2-4"
HIERARCHY = "N-34/130/D/d/2/4"
SEGMENT = "nmt/pl_1992_1m_evrf2007"
BODY = b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n42\n"
SHA = hashlib.sha256(BODY).hexdigest()


def _meta(
    path: Path, *, extra=None, request=None, dataset="pl.gugik.nmt_1m", body=BODY
) -> Path:
    meta = path.with_name(path.name + ".meta.json")
    meta.write_text(
        json.dumps(
            {
                "schema": "kartograf-meta/1",
                "dataset": dataset,
                "country": "PL",
                "product": "nmt",
                "horizontal_crs": "EPSG:2180",
                "request": {"sheet": SHEET} if request is None else request,
                "downloaded_at": "2026-10-18T10:20:30+00:00",
                "sha256": hashlib.sha256(body).hexdigest(),
                "size_bytes": len(body),
                "extra": {} if extra is None else extra,
            }
        ),
        encoding="utf-8",
    )
    return meta


def _data(
    path: Path, *, extra=None, request=None, dataset="pl.gugik.nmt_1m", body=BODY
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    _meta(path, extra=extra, request=request, dataset=dataset, body=body)
    return path


def _version(
    root: Path,
    segment: str,
    hierarchy: str,
    label: str,
    name: str,
    body=BODY,
    request=None,
) -> Path:
    """A version as the store keeps it: ``<label>_<sha8>/<name>`` + sidecar."""
    sha8 = hashlib.sha256(body).hexdigest()[:8]
    path = root / segment / "versions" / hierarchy / f"{label}_{sha8}" / name
    version = {"label": label, "label_source": "edition"}
    return _data(path, body=body, extra={"version": version}, request=request)


def _linked(link: Path, version: Path) -> Path:
    """Kartograf's own link: hardlink + link sidecar with ``link_target``."""
    assert ensure_link(link, version, ("", "", "")).changed
    return link


def _rows(entries) -> set[tuple]:
    return {
        (e.kind, e.path, e.version_path, e.label, e.sha8, e.problem, e.skipped)
        for e in entries
    }


# --- read_sidecar ---------------------------------------------------------------


def test_sidecar_normalizes_data_year_not_download_year_and_preserves_raw(tmp_path):
    data = _data(
        tmp_path / "old.asc",
        extra={
            "source": {
                "aktualnosc": "2022-05-10",
                "aktualnosc_rok": "2022",
                "numer_zgloszenia": "P.123",
            },
            "campaign": {
                "date": "2022-05-10",
                "zgloszenie": "P.123",
                "full_sheet": False,
            },
            "coverage": 0.75,
            "godlo_kafla": SHEET,
        },
        request={"godlo": SHEET, "year": 2022},
        dataset="pl.gugik.orto_true",  # renamed during 0.8.0 development
    )
    sidecar = read_sidecar(data)
    assert sidecar == read_sidecar(data.with_name(data.name + ".meta.json"))
    assert sidecar.dataset == "pl.gugik.orto_true"
    assert sidecar.dataset_key == "pl.gugik.true_orto"
    assert sidecar.data_year == 2022
    assert sidecar.data_date == "2022-05-10"
    assert sidecar.campaign is not None and sidecar.campaign["date"] == "2022-05-10"
    assert sidecar.survey_work_id == "P.123"
    assert sidecar.full_sheet is False and sidecar.coverage == 0.75
    assert sidecar.unit == SHEET
    assert sidecar.request == {"sheet": SHEET, "year": 2022}
    assert sidecar.extra is not None
    assert sidecar.extra["source"]["acquisition_date"] == "2022-05-10"
    assert sidecar.extra["source"]["survey_work_id"] == "P.123"
    assert sidecar.extra["tile_sheet"] == SHEET
    assert sidecar.campaign["survey_work_id"] == "P.123"
    assert sidecar.raw["request"] == {"godlo": SHEET, "year": 2022}
    assert sidecar.raw["extra"]["source"]["aktualnosc"] == "2022-05-10"


@pytest.mark.parametrize(
    ("historical", "current"),
    [
        ("pl.gugik.buildings_3d", "pl.gugik.buildings"),
        ("pl.gugik.orto_oblique", "pl.gugik.oblique_orto"),
        ("cz.cuzk.hy_net", "cz.cuzk.hynet"),
        ("cz.cuzk.qgzu", "cz.cuzk.qgzu2013"),
    ],
)
def test_development_dataset_keys_are_explicitly_mapped(tmp_path, historical, current):
    data = _data(tmp_path / f"{historical}.zip", dataset=historical)
    meta = read_sidecar(data)
    assert (meta.dataset, meta.dataset_key) == (historical, current)


def test_sparse_old_sidecar_does_not_infer_year_from_download(tmp_path):
    data = tmp_path / "old.tif"
    data.with_name(data.name + ".meta.json").write_text(
        json.dumps(
            {
                "schema": "kartograf-meta/1",
                "dataset": "old.unknown.source",
                "downloaded_at": "2019-03-10T12:00:00Z",
                "request": {"sheet": SHEET},
                "extra": {
                    "version": {"label": "2019-03-10", "label_source": "downloaded"}
                },
            }
        ),
        encoding="utf-8",
    )
    sidecar = read_sidecar(data)
    assert sidecar.data_year is None and sidecar.data_date is None
    assert sidecar.dataset_key is None and sidecar.dataset == "old.unknown.source"
    assert sidecar.sha256 is None and sidecar.campaign is None
    assert sidecar.full_sheet is None and sidecar.resolution is None


def test_source_acquisition_beats_requested_year_but_edition_is_available(tmp_path):
    data = _data(
        tmp_path / "area.zip",
        request={"teryt": "1465", "year": 2024},
        extra={
            "source": {"acquisition_date": "2021-08-17", "edition": "V2020_20u1"},
            "version": {"label": "V2020_20u1", "label_source": "edition"},
        },
    )
    meta = read_sidecar(data)
    assert (meta.data_year, meta.data_date, meta.edition, meta.unit) == (
        2021,
        "2021-08-17",
        "V2020_20u1",
        "1465",
    )


def test_cz_orthophoto_data_year_is_not_the_feed_publication_date(tmp_path):
    """The ATOM ``updated`` of an orthophoto edition is when it was
    published, not when the data were taken (``year``)."""
    data = _data(
        tmp_path / "CTES96.jpg",
        request={"sheet": "CTES96"},
        extra={
            "source": {
                "edition": "2025_2026-02-24",
                "year": 2025,
                "updated": "2026-02-24",
            },
            "version": {"label": "2025_2026-02-24", "label_source": "edition"},
        },
    )
    meta = read_sidecar(data)
    assert (meta.data_year, meta.data_date, meta.edition) == (
        2025,
        None,
        "2025_2026-02-24",
    )


def test_unexpected_field_types_are_missing_values_not_errors(tmp_path):
    raw = {
        "schema": "kartograf-meta/1",
        "dataset": 7,
        "resolution": 5,
        "nodata": "-9999",
        "size_bytes": -1,
        "sha256": "NOT-A-DIGEST",
        "request": ["N-34"],
        "extra": "broken",
    }
    path = tmp_path / "odd.tif.meta.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    meta = read_sidecar(path)
    assert (meta.dataset, meta.resolution, meta.nodata, meta.size_bytes) == (
        None,
        None,
        None,
        None,
    )
    assert (meta.sha256, meta.request, meta.extra, meta.unit) == (
        None,
        None,
        None,
        None,
    )
    assert meta.raw == raw


@pytest.mark.parametrize("text", ["{", "[]", "{}", '{"schema":"kartograf-meta/2"}'])
def test_invalid_schema_or_json_raises_with_sidecar_path(tmp_path, text):
    path = tmp_path / "bad.tif.meta.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(KartografError, match="bad.tif.meta.json"):
        read_sidecar(path)
    with pytest.raises(InvalidSidecarError) as raised:
        read_sidecar(tmp_path / "bad.tif")
    assert raised.value.path == path


def test_missing_sidecar_raises_specific_kartograf_error(tmp_path):
    with pytest.raises(InvalidSidecarError, match="missing.asc.meta.json"):
        read_sidecar(tmp_path / "missing.asc")


# --- describe_segment ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("segment", "dataset", "product", "variant"),
    [
        ("nmt/pl_1992_1m_evrf2007", "pl.gugik.nmt_1m", "nmt", "PL-1992 · EVRF2007"),
        ("nmt/pl_1992_tbd_25m_kron86", "pl.gugik.nmt_tbd_25m", "nmt", "KRON86"),
        ("nmpt/cz_dmpok_bpv", "cz.cuzk.dmpok", "nmpt", "Bpv"),
        ("orto/pl_1992_cir", "pl.gugik.orto", "orto", "CIR"),
        ("orto/pl_1992_standard_0.25m", "pl.gugik.orto", "orto", "standard · 0.25m"),
        ("true-orto/pl_1992_0.05m", "pl.gugik.true_orto", "true-orto", "0.05m"),
        ("landcover/pl_bdot10k_shp_2024", "pl.gugik.bdot10k", "bdot10k", "2024"),
        ("landcover/pl_bdot10k_gpkg_ptwp-swrs", "pl.gugik.bdot10k", "bdot10k", "PTWP"),
        ("landcover/eu_corine_1990_preview", "eu.clms.corine", "corine", "1990"),
        ("boundaries/pl_prg_gmina", "pl.gugik.prg", "admin", "gmina"),
        (
            "soil/global_soilgrids_clay_0-5cm_mean",
            "global.isric.soilgrids",
            "soil",
            "clay",
        ),
        ("hsg/global_soilgrids_0-5cm_mean", "global.isric.soilgrids", "hsg", "0-5cm"),
        ("maps/cz_ztm_10000_sjtsk_tiff", "cz.cuzk.ztm", "topographic", "10000"),
        ("cadastre/cz_cadastral-map_shp", "cz.cuzk.cadastral_map", "map", "shp"),
    ],
)
def test_segment_inverse_names_the_registered_variant(
    segment, dataset, product, variant
):
    info = describe_segment(segment)
    assert (info.dataset_key, info.product, info.known) == (dataset, product, True)
    assert variant.lower() in info.name.lower()


def _writer_segments() -> Iterator[tuple[str, str]]:
    """``(descriptor key, segment)`` of every segment the writers produce,
    built with the writers' own helpers (``resolve_subdir``,
    ``content_segment``, ``token_segment``, orthophoto variants and
    cutouts, land cover tokens, ``hsg_segment``)."""
    land: dict[str, list[tuple[str, ...]]] = {
        "pl.gugik.bdot10k": [
            ("gpkg",),
            ("gpkg", "zip"),
            ("shp",),
            ("gpkg", "PTWP-SWRS"),
        ],
        "eu.clms.corine": [(str(y),) for y in CorineProvider.CLMS_YEARS]
        + [(str(y), "preview") for y in CorineProvider.AVAILABLE_YEARS],
        "global.isric.soilgrids": list(
            itertools.product(
                SoilGridsProvider.PROPERTIES,
                SoilGridsProvider.DEPTHS,
                SoilGridsProvider.STATS,
            )
        ),
    }
    for d in all_sources():
        template = d.storage_subdir
        if "{vcrs}" in template:
            for v in d.variants:
                systems = v.systems if "{system}" in template else (None,)
                for system in systems if v.vertical_crs else ():
                    yield (
                        d.key,
                        d.resolve_subdir(system=system, vertical_crs=v.vertical_crs),
                    )
            continue
        if "{system}" in template:
            for system in {
                s
                for c in d.channels
                if isinstance(c.params, SheetIndexParams)
                for s in c.params.systems
            }:
                yield d.key, d.resolve_subdir(system=system)
                if d.key == "pl.gugik.orto":
                    for color in ("CIR", "B/W"):
                        variant = GugikOrtoProvider(color=color).storage_variant
                        yield d.key, f"{d.resolve_subdir(system=system)}_{variant}"
            cutouts = wcs_cutout_channels(d.key)
            for channel in cutouts:
                assert isinstance(channel.params, WcsCutoutParams)
                coverage = channel.params.variant if len(cutouts) > 1 else None
                for label in cutout_resolution_labels(d.key, coverage):
                    pixel: tuple[str, ...] = (label,)
                    if coverage is not None:
                        pixel = (coverage, label)
                    yield d.key, token_segment(d.resolve_subdir(system="1992"), pixel)
            continue
        for content in land.get(d.key, []):
            yield d.key, content_segment(d.key, content)
        collection = False
        for channel in d.channels:
            params = channel.params
            if isinstance(params, UnitPackageParams):
                collection = True
                for package in params.variants:
                    yield d.key, content_segment(d.key, package.segment_tokens)
                    if package.classes:
                        classes = "-".join(sorted(package.classes)[:2])
                        with_classes = (*package.segment_tokens, classes)
                        yield d.key, content_segment(d.key, with_classes)
            elif isinstance(params, AtomFilesParams):
                collection = True
                for crs in params.crs if len(params.crs) > 1 else (None,):
                    yield (
                        d.key,
                        content_segment(d.key, atom_segment_tokens(params, crs)),
                    )
            elif isinstance(params, FeatureBBoxParams):
                collection = True
                chosen = tuple(value for _, value in params.choice)
                if params.selection == "level":
                    for layer in params.layers:
                        yield d.key, content_segment(d.key, (*chosen, layer.code))
                else:
                    yield d.key, content_segment(d.key, chosen)
        if not collection and d.key not in land:
            yield d.key, template
    for depth in SoilGridsProvider.DEPTHS:
        yield "global.isric.soilgrids", hsg_segment(depth, "mean")


def test_every_segment_the_writers_produce_is_known_with_its_source():
    produced = list(_writer_segments())
    assert len(produced) > 500
    wrong = [
        (key, segment, describe_segment(segment).dataset_key)
        for key, segment in produced
        if not describe_segment(segment).known
        or describe_segment(segment).dataset_key != key
    ]
    assert wrong == []


@pytest.mark.parametrize(
    "segment",
    [
        "nmt/pl_1992_73m_evrf2007",
        "nmt/pl_1992_5m_kron86",  # 5 m is EVRF2007 only
        "orto/pl_1992_lilac",
        "orto/pl_2000_standard_0.25m",  # cutouts are PL-1992 only
        "soil/global_soilgrids",  # prefix requires content tokens
        "landcover/eu_corine_1990",  # only a WMS preview exists for 1990
        "landcover/cz_zabaged_gpkg",  # national file requires its CRS
        "hsg/global_soilgrids_0-5cm_q0.5",  # HSG uses the mean only
        "orto/pl_1992_true",  # 0.8.0 development directory (ADR-044 D7)
        "cadastre/cz_km_shp",  # 0.8.0 development directory (ADR-044 D7)
        "foo/bar",
    ],
)
def test_unknown_segment_does_not_guess_descriptor(segment):
    info = describe_segment(segment)
    assert (info.known, info.dataset_key, info.product) == (False, None, None)
    assert info.name == segment


# --- list_segments and the full scan --------------------------------------------


def test_list_segments_lists_real_segment_directories_including_unknown(tmp_path):
    root = tmp_path / "data"
    for segment in (SEGMENT, "landcover/pl_bdot10k_gpkg", "newproduct/pl_x"):
        (root / segment).mkdir(parents=True)
    (root / "nmt" / ".snapshot").mkdir()
    (root / ".Trash-1000" / "files").mkdir(parents=True)
    (root / "nmt" / "readme.txt").write_text("not a segment")
    (root / "nmt" / "linked").symlink_to(root / SEGMENT, target_is_directory=True)
    assert list_segments(root) == [
        "landcover/pl_bdot10k_gpkg",
        "newproduct/pl_x",
        SEGMENT,
    ]


def test_missing_store_is_an_error_not_an_empty_store(tmp_path):
    missing = tmp_path / "unmounted"
    with pytest.raises(FileNotFoundError):
        list_segments(missing)
    with pytest.raises(FileNotFoundError):
        iter_store(missing)
    with pytest.raises(FileNotFoundError):
        iter_store(missing, segment=SEGMENT)
    with pytest.raises(FileNotFoundError):
        list_partitions(missing, SEGMENT)
    (tmp_path / "data").mkdir()
    assert list(iter_store(tmp_path / "data", segment=SEGMENT)) == []
    assert list_partitions(tmp_path / "data", SEGMENT) == []


def test_iter_store_all_kinds_sidecar_failures_and_leftovers(tmp_path):
    root = tmp_path / "data"
    slot = root / SEGMENT / HIERARCHY
    versions_root = root / SEGMENT / "versions" / HIERARCHY
    label = "2022-05-10_83233"
    version = _data(
        versions_root / f"{label}_{SHA[:8]}" / f"{SHEET}.asc",
        extra={
            "version": {"label": label, "label_source": "campaign"},
            "campaign": {"date": "2022-05-10"},
        },
    )
    unpaired_version = _version(
        root, SEGMENT, HIERARCHY, "2023-05-10_83234", f"{SHEET}.asc"
    )
    unpaired_version.with_name(unpaired_version.name + ".meta.json").unlink()
    wrong_hash = _data(
        versions_root / "2024-05-10_83235_00000000" / f"{SHEET}.asc",
        extra={"version": {"label": "2024-05-10_83235", "label_source": "campaign"}},
    )
    unlabelled = _data(versions_root / f"2025-05-10_83236_{SHA[:8]}" / f"{SHEET}.asc")
    standard = _linked(slot / f"{SHEET}.asc", version)
    full = _linked(root / SEGMENT / "full_sheet" / HIERARCHY / standard.name, version)
    outside = slot / "outside.asc"
    _data(
        outside,
        extra={"link": "hardlink", "link_target": "../../../../../../../elsewhere.asc"},
    )
    # Same file name, but the version of another sheet: not this slot's.
    neighbour = root / SEGMENT / "N-34/130/D/d/2/3" / standard.name
    _data(
        neighbour,
        extra={
            "link": "hardlink",
            "link_target": os.path.relpath(version, neighbour.parent),
        },
    )
    bad = _data(slot / "damaged.asc")
    bad.with_name(bad.name + ".meta.json").write_text("{bad", encoding="utf-8")
    (slot / "unpaired.asc").write_bytes(b"unpaired")
    (slot / ".DS_Store").write_bytes(b"hidden")
    (root / SEGMENT / "kampanie" / "old").mkdir(parents=True)
    incoming = root / SEGMENT / "versions" / ".incoming"
    stale = incoming / "host_10_old"
    fresh = incoming / "host_11_fresh"
    active = incoming / "host_12_active"
    for staging in (stale, fresh, active):
        staging.mkdir(parents=True)
    (active / "new.asc").write_bytes(BODY)
    day_ago = time.time() - 90000
    os.utime(stale, (day_ago, day_ago))
    os.utime(active, (day_ago, day_ago))
    unknown = _data(root / "newproduct" / "pl_experimental" / "teryt" / "12.zip")

    entries = list(iter_store(root))

    assert [
        (e.path, e.label, e.sha8, e.hierarchy, e.version_path)
        for e in entries
        if e.kind == "version"
    ] == [(version, label, SHA[:8], HIERARCHY, version)]
    links = {
        (e.kind, e.path, e.version_path, e.hierarchy, e.label, e.sha8)
        for e in entries
        if e.kind in ("link", "full_sheet")
    }
    assert links == {
        ("link", standard, version, HIERARCHY, label, SHA[:8]),
        ("full_sheet", full, version, HIERARCHY, label, SHA[:8]),
        ("link", outside, None, HIERARCHY, None, SHA[:8]),
        ("link", neighbour, None, "N-34/130/D/d/2/3", None, SHA[:8]),
        ("link", unknown, None, "teryt", None, SHA[:8]),
    }
    assert {(e.problem, e.path) for e in entries if e.kind == "problem"} == {
        ("invalid_sidecar", bad),
        ("invalid_sidecar", wrong_hash),
        ("invalid_sidecar", unlabelled),
        ("missing_sidecar", slot / "unpaired.asc"),
        ("missing_sidecar", unpaired_version),
        ("legacy_campaigns", root / SEGMENT / "kampanie"),
        ("stale_incoming", stale),
        ("unknown_segment", root / "newproduct" / "pl_experimental"),
    }
    assert {e.segment for e in entries} == {SEGMENT, "newproduct/pl_experimental"}


def test_store_written_by_kartograf_is_read_back_exactly(tmp_path):
    """The reader agrees with Kartograf's writers: versions (also a
    relabelled one sharing the data), the link to the newest, the sidecars."""
    root = tmp_path / "data"
    segment = "landcover/pl_bdot10k_gpkg"
    slot = unit_slot(root, segment, ".gpkg", teryt="1465")

    def write_sidecar(data, ref, digest, http):
        emit_sidecar(
            "pl.gugik.bdot10k",
            data,
            request={"teryt": "1465"},
            digest=(digest.sha256, digest.size_bytes),
            version=ref.to_extra(),
            exclusive=True,
        )

    files = [
        fetch_version(
            slot,
            "force",
            signal="none",
            fetch=lambda staged, body=body: staged.write_bytes(body) and None,
            write_sidecar=write_sidecar,
            version=VersionRef(label, "edition"),
        )
        for label, body in (
            ("2024", b"first"),
            ("2025", b"second"),
            ("2026", b"second"),
        )
    ]
    assert [f.status for f in files] == ["new", "new", "relabeled"]

    entries = list(iter_store(root))

    versions = {e.path: e for e in entries if e.kind == "version"}
    assert set(versions) == {f.version_path for f in files}
    for file in files:
        entry = versions[file.version_path]
        assert (entry.label, entry.sha8) == (file.label, file.sha256[:8])
        assert entry.sidecar is not None and entry.sidecar.sha256 == file.sha256
        assert entry.sidecar.data_year == int(file.label)
        assert (entry.segment, entry.hierarchy, entry.problem) == (
            segment,
            "teryt",
            None,
        )
    [link] = [e for e in entries if e.kind == "link"]
    assert (link.path, link.version_path, link.label) == (
        slot.std,
        files[-1].version_path,
        "2026",
    )
    assert link_target(link.path) == link.version_path
    assert [e for e in entries if e.kind == "problem"] == []


def test_relative_output_dir_gives_link_version_path_equal_to_version_path(
    tmp_path, monkeypatch
):
    root = tmp_path / "data"
    version = _version(root, SEGMENT, HIERARCHY, "2025", f"{SHEET}.asc")
    _linked(root / SEGMENT / HIERARCHY / f"{SHEET}.asc", version)
    monkeypatch.chdir(tmp_path)
    entries = {e.kind: e for e in iter_store("./data")}
    assert entries["version"].path == Path(
        "data", SEGMENT, "versions", HIERARCHY, version.parent.name, version.name
    )
    assert entries["link"].version_path == entries["version"].path
    assert link_target(entries["link"].path) == entries["version"].path


# --- skip_versions -------------------------------------------------------------------


def _opened(monkeypatch) -> list[str]:
    opened: list[str] = []
    original = os.open

    def recording(path, *args, **kwargs):
        opened.append(os.fspath(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", recording)
    return opened


def test_skip_versions_lists_known_versions_without_reading_their_sidecars(
    tmp_path, monkeypatch
):
    root = tmp_path / "data"
    old = _version(root, SEGMENT, HIERARCHY, "2024", f"{SHEET}.asc", b"old")
    new = _version(root, SEGMENT, HIERARCHY, "2025", f"{SHEET}.asc", b"new")
    gone = _version(root, SEGMENT, HIERARCHY, "2023", f"{SHEET}.asc", b"gone")
    gone.with_name(gone.name + ".meta.json").unlink()
    link = _linked(root / SEGMENT / HIERARCHY / f"{SHEET}.asc", new)
    known = {path.parent.relative_to(root).as_posix() for path in (old, gone)}
    opened = _opened(monkeypatch)

    entries = {
        e.path: e for e in iter_store(root, segment=SEGMENT, skip_versions=known)
    }

    assert (entries[old].kind, entries[old].sidecar, entries[old].skipped) == (
        "version",
        None,
        True,
    )
    assert (entries[old].label, entries[old].version_path) == ("2024", old)
    assert entries[gone].problem == "missing_sidecar"
    assert entries[new].sidecar is not None and not entries[new].skipped
    assert entries[link].version_path == new and entries[link].sidecar is not None
    assert sorted(opened) == sorted(
        os.fspath(p.with_name(p.name + ".meta.json")) for p in (new, link)
    )
    scoped = list(iter_store(root, segment=SEGMENT, units=[SHEET], skip_versions=known))
    assert _rows(scoped) == _rows(entries.values())


def _listed(monkeypatch) -> list[Path]:
    listed: list[Path] = []
    original = os.scandir

    def recording(path):
        listed.append(Path(path))
        return original(path)

    monkeypatch.setattr(os, "scandir", recording)
    return listed


def test_skip_versions_mapping_gives_known_files_without_listing_their_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "data"
    old = _version(root, SEGMENT, HIERARCHY, "2024", f"{SHEET}.asc", b"old")
    new = _version(root, SEGMENT, HIERARCHY, "2025", f"{SHEET}.asc", b"new")
    _linked(root / SEGMENT / HIERARCHY / f"{SHEET}.asc", new)
    key = old.parent.relative_to(root).as_posix()
    listed_known = _rows(iter_store(root, segment=SEGMENT, skip_versions={key}))
    listed = _listed(monkeypatch)
    opened = _opened(monkeypatch)

    entries = list(iter_store(root, segment=SEGMENT, skip_versions={key: [old.name]}))

    assert _rows(entries) == listed_known  # the same entries as from the listing
    assert old.parent not in listed and new.parent in listed
    assert old.with_name(old.name + ".meta.json") not in map(Path, opened)


def test_skip_versions_mapping_serves_units_of_a_flat_slot_without_listings(
    tmp_path, monkeypatch
):
    """A flat slot shares ``versions/teryt`` between its units: known version
    directories are not listed for every unit of a refresh."""
    root = tmp_path / "data"
    segment = "landcover/pl_bdot10k_gpkg"
    versions = {
        unit: _version(root, segment, "teryt", "2024", f"{unit}.gpkg", unit.encode())
        for unit in ("1465", "1261", "0201")
    }
    known = {
        path.parent.relative_to(root).as_posix(): (path.name,)
        for path in versions.values()
    }
    listed = _listed(monkeypatch)

    result = list(
        iter_store(root, segment=segment, units=["1465"], skip_versions=known)
    )

    assert [(e.path, e.skipped, e.label) for e in result] == [
        (versions["1465"], True, "2024")
    ]
    assert not {path.parent for path in versions.values()} & set(listed)


@pytest.mark.parametrize(
    "names",
    [
        "M-34.asc",  # a string, not a collection of names
        None,
        ["../escape.asc"],
        ["sub/name.asc"],
        [".hidden"],
        [f"{SHEET}.asc.meta.json"],
        [""],
        [7],
    ],
)
def test_skip_versions_mapping_rejects_names_of_no_data_file(tmp_path, names):
    root = tmp_path / "data"
    old = _version(root, SEGMENT, HIERARCHY, "2024", f"{SHEET}.asc")
    known = {old.parent.relative_to(root).as_posix(): names}
    with pytest.raises(ValidationError, match="skip_versions"):
        list(iter_store(root, segment=SEGMENT, skip_versions=known))


def test_skip_versions_mapping_with_a_repeated_name_yields_the_file_once(tmp_path):
    """A listing never repeats a name; neither does the mapping form."""
    root = tmp_path / "data"
    old = _version(root, SEGMENT, HIERARCHY, "2024", f"{SHEET}.asc")
    known = {old.parent.relative_to(root).as_posix(): [old.name, old.name]}

    found = list(iter_store(root, segment=SEGMENT, skip_versions=known))

    assert [(e.path, e.skipped) for e in found if e.kind == "version"] == [(old, True)]


# --- units --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("segment", "unit", "hierarchy", "code"),
    [
        (SEGMENT, SHEET, HIERARCHY, SHEET),
        (SEGMENT, "n-34-130-d-d-2-4", HIERARCHY, SHEET),  # canonical code
        (SEGMENT, f"{HIERARCHY}/{SHEET}", HIERARCHY, SHEET),
        ("nmt/pl_2000_1m_evrf2007", "6.179.12.20", "6/179/12/20", "6.179.12.20"),
        ("nmt/cz_dmr5g_bpv", "AS91", "AS/91", "AS91"),
        ("nmt/cz_dmr5g_evrf2007", "302_5550", "302/5550", "302_5550"),
        ("landcover/pl_bdot10k_gpkg", "1465", "teryt", "1465"),
        ("landcover/pl_bdot10k_gpkg", "teryt/1465", "teryt", "1465"),
        ("cadastre/cz_cadastral-map_shp", "623164", "ku", "623164"),
        ("names/pl_prng_shp", "pl_miejscowosci", "country", "pl_miejscowosci"),
        ("maps/cz_ztm_10000_sjtsk_tiff", "0510-D-11", "0510/D/11", "0510-D-11"),
        (
            "models3d/pl_mesh",
            "2000/7/78944_6777_74230_55482",
            "2000/7",
            "78944_6777_74230_55482",
        ),
        (
            "soil/global_soilgrids_clay_0-5cm_mean",
            "450000.5_550000_460000_560000",
            "bbox",
            "450000.5_550000_460000_560000",
        ),
    ],
)
def test_scoped_units_build_exact_hierarchy_without_scanning_siblings(
    tmp_path, monkeypatch, segment, unit, hierarchy, code
):
    root = tmp_path / "data"
    slot = root / segment / hierarchy
    chosen = _data(slot / f"{code}.tif", request={"sheet": unit})
    sibling = slot.parent / "neighbor" / "other.tif"
    _data(sibling)
    calls: list[Path] = []
    scans = os.scandir

    def checked_scandir(path):
        path = Path(path)
        calls.append(path)
        if path == sibling.parent:
            raise AssertionError("scanned unrelated hierarchy")
        return scans(path)

    monkeypatch.setattr(os, "scandir", checked_scandir)
    result = list(iter_store(root, segment=segment, units=[unit]))
    assert [(entry.kind, entry.path, entry.hierarchy) for entry in result] == [
        ("link", chosen, hierarchy)
    ]
    assert root / segment not in calls
    assert sibling.parent not in calls


def test_scoped_unit_matches_exact_name_not_prefix(tmp_path):
    root = tmp_path / "data"
    slot = root / "landcover/pl_bdot10k_gpkg/teryt"
    selected = _data(slot / "1465.gpkg", request={"teryt": "1465"})
    _data(slot / "14650.gpkg", request={"teryt": "14650"})
    _data(slot / "1465_other.gpkg", request={"teryt": "1465_other"})
    result = list(
        iter_store(root, segment="landcover/pl_bdot10k_gpkg", units=["teryt/1465"])
    )
    assert len(result) == 1 and result[0].path == selected
    assert result[0].sidecar is not None and result[0].sidecar.unit == "1465"


def test_scoped_sheet_unit_takes_every_file_of_the_sheet_and_its_versions(tmp_path):
    """A LAZ tile keeps the source file name and an oblique orthophoto has
    one file per direction: the sheet's slot directory is the unit."""
    root = tmp_path / "data"
    segment = "laz/pl_1992_evrf2007"
    tile = "N-33-131-B-a-1-1-4"
    hierarchy = "N-33/131/B/a/1/1/4"
    name = f"81121_1744736_{tile}.laz"
    version = _version(root, segment, hierarchy, "2021-06-01_81121", name)
    link = _linked(root / segment / hierarchy / name, version)
    _data(root / segment / hierarchy / "1" / "finer.laz")  # another (finer) sheet
    result = list(iter_store(root, segment=segment, units=[tile]))
    assert {(e.kind, e.path, e.version_path) for e in result} == {
        ("link", link, version),
        ("version", version, version),
    }


def test_scoped_units_skip_hidden_version_directories_like_the_full_scan(tmp_path):
    root = tmp_path / "data"
    segment = "landcover/pl_bdot10k_gpkg"
    version = _version(root, segment, "teryt", "2024", "1465.gpkg")
    hidden = version.parent.with_name("." + version.parent.name)
    hidden.mkdir()
    for file in version.parent.iterdir():
        (hidden / file.name).write_bytes(file.read_bytes())
    whole = _rows(iter_store(root, segment=segment))
    assert {row[1] for row in whole} == {version}
    assert _rows(iter_store(root, segment=segment, units=["1465"])) == whole


def test_units_of_one_flat_slot_are_listed_once(tmp_path, monkeypatch):
    root = tmp_path / "data"
    segment = "landcover/pl_bdot10k_gpkg"
    wanted = [
        _version(root, segment, "teryt", "2024", f"{t}.gpkg", t.encode())
        for t in ("1465", "1261")
    ]
    _version(root, segment, "teryt", "2024", "0201.gpkg", b"other unit")
    calls: list[str] = []
    scans = os.scandir

    def counted(path):
        calls.append(os.fspath(path))
        return scans(path)

    monkeypatch.setattr(os, "scandir", counted)
    result = list(
        iter_store(root, segment=segment, units=["1465", "teryt/1261", "1465"])
    )
    assert sorted(e.path for e in result) == sorted(wanted)
    versions_slot = os.fspath(root / segment / "versions" / "teryt")
    assert calls.count(versions_slot) == 1


@pytest.mark.parametrize(
    ("segment", "units", "skip"),
    [
        ("../escape", None, None),
        ("nmt/../../escape", None, None),
        ("/absolute", None, None),
        ("nmt/.hidden", None, None),
        (SEGMENT, ["../escape"], None),
        (SEGMENT, ["teryt/../../escape"], None),
        (SEGMENT, ["/absolute"], None),
        (SEGMENT, [r"teryt\..\escape"], None),
        (SEGMENT, ["versions/N-34/130"], None),
        (SEGMENT, ["full_sheet/x"], None),
        (SEGMENT, ["N-34-.."], None),
        (SEGMENT, SHEET, None),  # a string is not a collection of units
        (SEGMENT, None, "nmt/pl_1992_1m_evrf2007/versions/x"),
        (None, [SHEET], None),  # units require a segment
    ],
)
def test_untrusted_arguments_never_traverse_store(tmp_path, segment, units, skip):
    (tmp_path / "data").mkdir()
    with pytest.raises(ValidationError):
        iter_store(tmp_path / "data", segment=segment, units=units, skip_versions=skip)


def test_scoped_unit_does_not_follow_hierarchy_symlink(tmp_path, monkeypatch):
    root = tmp_path / "data"
    outside = tmp_path / "outside"
    _data(outside / "1465.gpkg", request={"teryt": "1465"})
    base = root / "landcover/pl_bdot10k_gpkg"
    base.mkdir(parents=True)
    (base / "teryt").symlink_to(outside, target_is_directory=True)
    original = os.scandir

    def confined(path):
        if Path(path) == outside:
            raise AssertionError("scanned outside output_dir")
        return original(path)

    monkeypatch.setattr(os, "scandir", confined)
    assert (
        list(iter_store(root, segment="landcover/pl_bdot10k_gpkg", units=["1465"]))
        == []
    )


@pytest.mark.parametrize(
    ("segment", "stem", "req"),
    [
        ("names/pl_prng_shp", "pl_miejscowosci", {"whole_country": True}),
        (
            "names/pl_prng_shp",
            "pl_miejscowosci",
            {"whole_country": True, "country": "pl"},
        ),
        ("boundaries/pl_prg_gml", "pl", {"whole_country": True, "country": "pl"}),
    ],
)
def test_unit_of_a_national_file_round_trips_into_scoped_scan(
    tmp_path, segment, stem, req
):
    """The unit read from a sidecar finds the file again (a themed national
    file is named ``<code>_<theme>``; the theme is not in the request)."""
    root = tmp_path / "data"
    version = _version(root, segment, "country", "2026", f"{stem}.zip", request=req)
    link = root / segment / "country" / f"{stem}.zip"
    _linked(link, version)
    other = _version(root, segment, "country", "2026", "pl_other.zip", b"other")
    _meta(link, request=req)

    unit = read_sidecar(link).unit
    assert unit == stem
    found = list(iter_store(root, segment=segment, units=[unit]))
    assert {(e.kind, e.path) for e in found} == {("link", link), ("version", version)}
    assert other not in {e.path for e in found}


@pytest.mark.parametrize("unit", ["versions", "full_sheet", "kampanie", "x" * 300])
def test_reserved_and_overlong_units_are_rejected_at_call_time(tmp_path, unit):
    (tmp_path / "data").mkdir()
    with pytest.raises(ValidationError):
        iter_store(tmp_path / "data", segment=SEGMENT, units=[unit])


def test_entries_and_sidecars_are_explicitly_unhashable(tmp_path):
    root = tmp_path / "data"
    _data(root / SEGMENT / HIERARCHY / f"{SHEET}.asc")
    entry = next(e for e in iter_store(root) if e.kind == "link")
    for record in (entry, entry.sidecar):
        with pytest.raises(TypeError, match="unhashable"):
            hash(record)


def test_bare_version_sidecar_of_a_provider_without_descriptor_is_readable(tmp_path):
    """``emit_sidecar`` writes no ``schema`` for such a provider; the version
    is valid for ``read_version``, so it is for the reader too."""
    root = tmp_path / "data"
    segment = "custom/xx_provider"
    data = root / segment / "versions" / "teryt" / f"2025_{SHA[:8]}" / "1465.bin"
    data.parent.mkdir(parents=True)
    data.write_bytes(BODY)
    emit_sidecar(
        None,
        data,
        request={"teryt": "1465"},
        digest=(SHA, len(BODY)),
        version={"label": "2025", "label_source": "edition"},
        exclusive=True,
    )
    assert "schema" not in json.loads(
        data.with_name("1465.bin.meta.json").read_text(encoding="utf-8")
    )
    link = _linked(root / segment / "teryt" / "1465.bin", data)

    sidecar = read_sidecar(data)
    assert (sidecar.schema, sidecar.sha256, sidecar.unit) == (
        "kartograf-meta/1",
        SHA,
        "1465",
    )
    entries = list(iter_store(root, segment=segment))
    # The custom segment itself is unknown to the registry; its files are fine.
    assert {(e.kind, e.path, e.problem) for e in entries} == {
        ("link", link, None),
        ("version", data, None),
        ("problem", root / segment, "unknown_segment"),
    }


@pytest.mark.parametrize(
    "body",
    [
        {"sha256": SHA},  # no extra: not a meta object
        {"schema": "kartograf-meta/2", "sha256": SHA, "extra": {}},
        {"schema": 1, "sha256": SHA, "extra": {}},
    ],
)
def test_sidecar_without_valid_schema_or_meta_shape_is_rejected(tmp_path, body):
    data = tmp_path / "x.bin"
    data.with_name("x.bin.meta.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(InvalidSidecarError):
        read_sidecar(data)


# --- partitions -----------------------------------------------------------------

# Directory names the generator below combines: nested sheets, a flat slot, a
# name that is a version directory below the first level, reserved and hidden.
_NAMES = ("A", "B", "7", "bbox", "x_0123abcd", "versions", "kampanie", ".h")


def _random_segment(tmp_path: Path, rng: random.Random) -> str:
    """A segment with every shape the scan tells apart, at random places:
    slots at several levels (so split directories have files of their own),
    links resolved, of another slot or unpaired, damaged sidecars, versions
    with a wrong sha8 or without a sidecar, files outside version
    directories, hidden entries, symlinks out of the store and the
    segment-level leftovers."""
    root = tmp_path / "data"
    segment = rng.choice((SEGMENT, "newproduct/pl_x"))
    base = root / segment
    base.mkdir(parents=True)
    outside = tmp_path / "outside"
    _data(outside / "deep" / "escaped.asc")
    slots = {
        tuple(rng.choice(_NAMES) for _ in range(rng.randint(1, 4)))
        for _ in range(rng.randint(3, 10))
    }
    for n, parts in enumerate(sorted(slots)):
        hierarchy = "/".join(parts)
        directory = base.joinpath(*parts)
        name = f"f{n}.asc"
        versions = [
            _version(root, segment, hierarchy, label, name, f"{n}{label}".encode())
            for label in rng.sample(("2023", "2024", "2025"), rng.randint(0, 2))
        ]
        foreign = base / "versions" / "A" / "2020_0123abcd" / name
        for tree in rng.sample(((), ("full_sheet",)), rng.randint(0, 2)):
            link = base.joinpath(*tree, *parts, name)
            target = rng.choice([*versions, foreign, None])
            rel = None if target is None else os.path.relpath(target, link.parent)
            _data(link, extra={"link": "hardlink", "link_target": rel} if rel else {})
        shape = rng.randrange(6)
        if shape == 0 and versions:
            versions[0].with_name(versions[0].name + ".meta.json").unlink()
        elif shape == 1:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "unpaired.asc").write_bytes(b"no sidecar")
        elif shape == 2:
            _data(base / "versions" / hierarchy / "2022_00000000" / name)  # wrong sha8
        elif shape == 3:
            _data(base / "versions" / hierarchy / "outside_any_version.asc")
        elif shape == 4:
            _data(directory / "damaged.asc")
            (directory / "damaged.asc.meta.json").write_text("{", encoding="utf-8")
        elif not (directory / "s").exists():
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "s").symlink_to(outside / "deep", target_is_directory=True)
    if rng.random() < 0.5:
        _data(base / "root.asc")
        _data(base / "full_sheet" / "root.asc")
    if rng.random() < 0.5:
        (base / "kampanie" / "old").mkdir(parents=True, exist_ok=True)
        stale = base / "versions" / ".incoming" / "host_1_old"
        stale.mkdir(parents=True)
        day_ago = time.time() - 90000
        os.utime(stale, (day_ago, day_ago))
    (base / "S").symlink_to(outside, target_is_directory=True)
    return segment


def _entries(entries) -> list[str]:
    """Every field of the entries (sidecars included), duplicates kept."""
    return sorted(repr(entry) for entry in entries)


@pytest.mark.parametrize("seed", range(16))
def test_partitions_union_is_exactly_the_segment_scan(tmp_path, seed):
    root = tmp_path / "data"
    segment = _random_segment(tmp_path, random.Random(seed))
    found = list(iter_store(root, segment=segment))
    bad = {e.path.parent for e in found if e.kind == "problem"}
    mapping: dict[str, list[str]] = {}
    for e in found:
        if e.kind == "version" and e.path.parent not in bad:
            key = e.path.parent.relative_to(root).as_posix()
            mapping.setdefault(key, []).append(e.name)
    assert _entries(iter_store(root, segment=segment, skip_versions=mapping)) == (
        _entries(iter_store(root, segment=segment, skip_versions=set(mapping)))
    )
    for target, skip in itertools.product((1, 2, 3, 1000), (None, mapping)):
        whole = _entries(iter_store(root, segment=segment, skip_versions=skip))
        keys = list_partitions(root, segment, target=target)
        assert keys[0] == "." and len(set(keys)) == len(keys)
        with ThreadPoolExecutor(max_workers=4) as pool:
            parts = pool.map(
                lambda key, skip=skip: list(
                    iter_store(root, segment=segment, partition=key, skip_versions=skip)
                ),
                keys,
            )
            union = _entries(itertools.chain.from_iterable(parts))
        assert union == whole, (target, keys)


def test_partitions_split_levels_and_keep_own_files_of_split_directories(tmp_path):
    root = tmp_path / "data"
    base = root / SEGMENT
    own = _data(base / "M-34" / "own.asc")
    in_22 = _version(root, SEGMENT, "M-34/22", "2025", "a.asc")
    _version(root, SEGMENT, "M-34/7", "2025", "b.asc")
    full = _data(base / "full_sheet" / "M-34" / "7" / "b.asc")
    _version(root, SEGMENT, "bbox", "2025", "1_2_3_4.tif")

    assert list_partitions(root, SEGMENT, target=1) == [".", "M-34", "bbox"]
    keys = list_partitions(root, SEGMENT)
    assert keys == [".", "M-34/.", "M-34/22", "M-34/7", "bbox"]

    def paths(key):
        return {e.path for e in iter_store(root, segment=SEGMENT, partition=key)}

    assert paths("M-34/.") == {own}
    assert paths("M-34/22") == {in_22}
    assert full in paths("M-34/7")
    assert paths(".") == set()


def test_segment_level_problems_and_files_belong_to_dot_partition_only(tmp_path):
    root = tmp_path / "data"
    segment = "newproduct/pl_experimental"
    base = root / segment
    on_root = _data(base / "root.zip")
    full_root = _data(base / "full_sheet" / "root.zip")
    unit = _data(base / "teryt" / "12.zip")
    (base / "kampanie" / "old").mkdir(parents=True)
    stale = base / "versions" / ".incoming" / "host_1_old"
    stale.mkdir(parents=True)
    day_ago = time.time() - 90000
    os.utime(stale, (day_ago, day_ago))

    keys = list_partitions(root, segment)

    assert keys == [".", "teryt"]
    rows = {
        key: {
            (e.kind, e.problem, e.path)
            for e in iter_store(root, segment=segment, partition=key)
        }
        for key in keys
    }
    assert rows["."] == {
        ("problem", "unknown_segment", base),
        ("link", None, on_root),
        ("full_sheet", None, full_root),
        ("problem", "legacy_campaigns", base / "kampanie"),
        ("problem", "stale_incoming", stale),
    }
    assert rows["teryt"] == {("link", None, unit)}


def test_partition_lists_only_its_own_subtree(tmp_path, monkeypatch):
    root = tmp_path / "data"
    base = root / SEGMENT
    mine = _version(root, SEGMENT, "M-34/22/A", "2025", "a.asc")
    link = _linked(base / "M-34/22/A/a.asc", mine)
    other = _version(root, SEGMENT, "M-34/23/A", "2025", "b.asc")
    _linked(base / "M-34/23/A/b.asc", other)
    listed = _listed(monkeypatch)

    entries = list(iter_store(root, segment=SEGMENT, partition="M-34/22"))

    assert {(e.kind, e.path, e.version_path) for e in entries} == {
        ("link", link, mine),
        ("version", mine, mine),
    }
    own = (base / "M-34/22", base / "versions/M-34/22")
    assert listed
    assert all(any(path.is_relative_to(tree) for tree in own) for path in listed)


def test_partitions_never_follow_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "data"
    outside = tmp_path / "outside"
    _data(outside / "N-34" / "x.asc")
    base = root / SEGMENT
    _data(base / "M-34" / "own.asc")
    (base / "N-34").symlink_to(outside / "N-34", target_is_directory=True)
    (base / "M-34" / "22").symlink_to(outside, target_is_directory=True)
    listed = _listed(monkeypatch)

    assert list_partitions(root, SEGMENT) == [".", "M-34"]
    assert list(iter_store(root, segment=SEGMENT, partition="N-34")) == []
    assert list(iter_store(root, segment=SEGMENT, partition="M-34/22")) == []
    assert not any(path.is_relative_to(outside) for path in listed)


@pytest.mark.parametrize(
    ("segment", "units", "partition"),
    [
        (None, None, "."),  # a partition requires its segment
        (SEGMENT, [SHEET], "."),  # units or a partition, not both
        (SEGMENT, None, ""),
        (SEGMENT, None, "/etc"),
        (SEGMENT, None, "../escape"),
        (SEGMENT, None, "M-34/../../escape"),
        (SEGMENT, None, "M-34//22"),
        (SEGMENT, None, "M-34/./22"),
        (SEGMENT, None, ".hidden"),
        (SEGMENT, None, "M-34/./."),
        (SEGMENT, None, "M-34\x00"),
        (SEGMENT, None, ["M-34"]),
        (SEGMENT, None, "x" * 300),  # longer than NAME_MAX: not OSError
        (SEGMENT, None, "M-34/" + "x" * 300),
    ],
)
def test_untrusted_partitions_never_traverse_store(tmp_path, segment, units, partition):
    (tmp_path / "data" / SEGMENT).mkdir(parents=True)
    with pytest.raises(ValidationError):
        iter_store(tmp_path / "data", segment=segment, units=units, partition=partition)


@pytest.mark.parametrize(
    ("segment", "target"),
    [("../escape", 32), ("nmt", 32), (SEGMENT, 0), (SEGMENT, True), (SEGMENT, 2.5)],
)
def test_list_partitions_rejects_malformed_arguments(tmp_path, segment, target):
    (tmp_path / "data").mkdir()
    with pytest.raises(ValidationError):
        list_partitions(tmp_path / "data", segment, target=target)


# --- streaming, cost and threads -----------------------------------------------------


def test_streaming_yields_first_file_before_touching_later_directory(
    tmp_path, monkeypatch
):
    root = tmp_path / "data"
    first = _data(root / SEGMENT / HIERARCHY / f"{SHEET}.asc")
    later = root / SEGMENT / "versions"
    later.mkdir()
    original = os.scandir

    def guarded(path):
        if Path(path) == later:
            raise AssertionError("later branch visited before first yield")
        return original(path)

    monkeypatch.setattr(os, "scandir", guarded)
    stream = iter_store(root)
    assert next(stream).path == first
    with pytest.raises(AssertionError, match="later branch"):
        list(stream)


def test_scan_opens_each_sidecar_once_and_never_a_data_file(tmp_path, monkeypatch):
    root = tmp_path / "data"
    version = _version(root, SEGMENT, HIERARCHY, "2025", f"{SHEET}.asc")
    link = _linked(root / SEGMENT / HIERARCHY / f"{SHEET}.asc", version)
    (root / SEGMENT / HIERARCHY / "orphan.asc").write_bytes(b"no sidecar")
    data_files = {os.fspath(p) for p in (version, link, link.with_name("orphan.asc"))}
    opened = _opened(monkeypatch)
    statted: list[str] = []
    for name in ("stat", "lstat"):
        original = getattr(os, name)

        def recording(path, *args, _original=original, **kwargs):
            statted.append(os.fspath(path))
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(os, name, recording)

    entries = list(iter_store(root, segment=SEGMENT))

    assert len(entries) == 3
    assert sorted(opened) == sorted(
        os.fspath(p.with_name(p.name + ".meta.json")) for p in (version, link)
    )
    assert data_files.isdisjoint(statted)


def test_concurrent_scans_of_segments_and_unit_chunks_match_one_scan(tmp_path):
    root = tmp_path / "data"
    segments = ("landcover/pl_bdot10k_gpkg", "landcover/pl_bdot10k_shp")
    units = [f"{n:04d}" for n in range(1201, 1241)]
    for segment, unit in itertools.product(segments, units):
        version = _version(
            root, segment, "teryt", "2024", f"{unit}.gpkg", unit.encode()
        )
        _linked(root / segment / "teryt" / f"{unit}.gpkg", version)
    whole = _rows(iter_store(root))
    chunks = [units[i : i + 7] for i in range(0, len(units), 7)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        by_segment = pool.map(
            lambda s: _rows(iter_store(root, segment=s)), list_segments(root)
        )
        by_chunk = pool.map(
            lambda job: _rows(iter_store(root, segment=job[0], units=job[1])),
            itertools.product(segments, chunks),
        )
        segment_rows = set().union(*by_segment)
        chunk_rows = set().union(*by_chunk)
    assert len(whole) == 2 * len(segments) * len(units)
    assert segment_rows == whole == chunk_rows


# --- link_target -----------------------------------------------------------------


def _store_link(root: Path, *, full: bool = False) -> tuple[Path, Path]:
    body = b"actual stored version"
    version = _version(
        root / "data", "nmt/pl_1992", "N-34/130", "2025", "sheet.asc", body
    )
    link = root / "data" / "nmt" / "pl_1992"
    if full:
        link = link / "full_sheet"
    return _linked(link / "N-34" / "130" / "sheet.asc", version), version


@pytest.mark.parametrize("full", [False, True])
def test_verified_link_and_smb_content_fallback(tmp_path, monkeypatch, full):
    link, version = _store_link(tmp_path, full=full)
    assert link_target(link) == version
    # SMB without stable inode numbers: samefile fails, content confirms.
    monkeypatch.setattr(os.path, "samefile", lambda *_: False)
    assert link_target(link) == version
    link.write_bytes(b"corrupted stored version")
    assert link_target(link) is None


def test_link_target_ignores_missing_copy_and_path_traversal(tmp_path):
    link, version = _store_link(tmp_path)
    sidecar = link.with_name(link.name + ".meta.json")
    content = json.loads(sidecar.read_text())
    content["extra"]["link"] = "copy"
    sidecar.write_text(json.dumps(content))
    assert link_target(link) is None
    content["extra"]["link"] = "hardlink"
    content["extra"]["link_target"] = str(version)
    sidecar.write_text(json.dumps(content))
    assert link_target(link) == version  # same-slot absolute target (other drive)
    other = tmp_path / "outsider.asc"
    os.link(version, other)
    content["extra"]["link_target"] = str(other)
    sidecar.write_text(json.dumps(content))
    assert link_target(link) is None  # the same inode cannot authorize an outside file
    sidecar.unlink()
    assert link_target(link) is None
