"""
Update plan ``kartograf-plan/1`` shared by every download track (spec 4.4).

A plan lists the files of a request with their local version and the source
freshness signal, WITHOUT downloading anything. Every position belongs to a
track (``pl_sheet``, ``laz_tile``, ``cz_sheet``, ``cz_laz``, ``pl_cutout``,
``cz_cutout``, ``landcover``, ``hsg``, ``collection``, ``cz_orto``); ``unit``
is the task unit of the track (sheet code, LAZ tile sheet, CZ sheet, CZ LAZ
sheet, bbox coordinates, TERYT, country code of a national file, SM5 sheet of
the CZ orthophoto - four positions: the JPEG and its three world files). The
store root that a write would refuse as a conflict has one position of its own,
of the track ``store``, and the plan lists nothing else (`refusal_plan`).
Executing a plan (``--upgrade --plan``) re-checks the signal:
``select_planned`` keeps only the planned positions
whose fresh check is identical, the rest are ``stale``; positions removed
from the plan file are never executed.

Every position also says where its file comes from (ADR-063 decision 3), from what
the check reads and no request more: ``source``, the registry key of its source;
``fetch``, the URL whose bytes the file is unchanged, with the size and the SHA-256
the check knows (`Fetch`), or ``fetch_reason`` when no URL serves the file
(`fetch_fields`); and the plan lists its sources once (``sources``, `PlanSource`).
A detached plan (`detached_plan`) is the plan of a plain write into a directory
that does not exist, answered as the write into ``.``.
"""

import json
import secrets
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast, get_args

from kartograf import _clock
from kartograf._version import build_version
from kartograf.exceptions import ConflictError, KartografError, ValidationError
from kartograf.marker import store_refusal
from kartograf.messages import message, reason
from kartograf.notices import Notice
from kartograf.output import Action, Mode, Staging, plain_of, wrapping
from kartograf.serialization import Document, EncodeContext
from kartograf.sources.descriptor import LicenseInfo
from kartograf.sources.registry import get_source

PLAN_SCHEMA = "kartograf-plan/1"
ItemStatus = Literal["current", "newer", "missing", "unverifiable", "check_failed"]
Track = Literal[
    "pl_sheet",
    "laz_tile",
    "cz_sheet",
    "cz_laz",
    "pl_cutout",
    "cz_cutout",
    "landcover",
    "hsg",
    "collection",
    "cz_orto",
    "store",
]
TRACKS: tuple[Track, ...] = get_args(Track)
# Statuses a plan executes.
TODO_STATUSES: tuple[ItemStatus, ...] = ("newer", "missing")
# Why a planned file has no URL that serves it (ADR-063 decision 3).
FetchReason = Literal["credentials", "built"]
FETCH_REASONS: tuple[FetchReason, ...] = get_args(FetchReason)
# The ``output_dir`` of a detached plan: its paths are relative to it.
DETACHED = "."
_DETACHED_PREFIX = "kartograf-detached-"


@dataclass(frozen=True)
class Fetch:
    """The URL whose bytes a planned file is, unchanged (ADR-063 decision 3).

    ``size_bytes`` is the size the check read (an index record, the ``Content-Length``
    of a probe, an ATOM feed) and ``sha256`` the SHA-256 the registry pins; each is
    ``None`` when the check does not know it, ``url`` too: the file of an ATOM feed in
    a plain plan, whose feed only the run reads, or the file of a sheet whose index
    could not be checked.
    """

    url: str | None
    size_bytes: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class PlanSource:
    """A source of the files of a plan, as ``<group> list-sources`` writes it.

    ``key`` is the registry key (``pl.gugik.nmt_1m``), ``provider`` the data provider,
    ``license`` its ``{id, attribution, url}`` and ``auth`` ``none`` or the key
    exchange its URLs need (``clms_oauth``).
    """

    key: str
    provider: str
    license: LicenseInfo
    auth: str


@dataclass(frozen=True)
class PlanItem:
    """One file of the request: local version vs. the source signal.

    ``available_signal`` depends on the channel: an index record
    (``url``, ``date``, ...), HTTP headers (``etag``, ``last_modified``,
    ``content_length``) or ``None`` (no cheap signal). ``status``:
    ``current`` (the local version is the newest), ``newer`` (the source
    has newer content, not local), ``missing`` (no local version),
    ``unverifiable`` (no cheap signal), ``check_failed`` (the signal could
    not be read; ``error``).

    A position of a plain write (``output_dir``, DEV-19.10) has no segment, hierarchy
    or local version: ``name`` is the file name, ``action`` says what the write
    would do (``write`` a new file, ``replace`` an existing one with ``--force``,
    ``conflict``), ``path`` is the target and ``reason`` names a conflict
    (``duplicate_output_name``, ``output_in_store``, ``output_exists``). The
    ``status`` is ``missing`` for ``write`` and ``unverifiable`` for the others. A
    position whose source could not be checked stays ``check_failed`` and has none of
    the three, as in the store, where all three are ``None``. The position of the
    track ``store`` is the root of a store that a write would refuse
    (``nested_store``, ``not_empty``; DEV-19.14): ``action`` is ``conflict``,
    ``path`` the root, ``reason`` why, ``error`` the text of the refusal, and
    ``name`` and ``unit`` are the root too.

    ``source`` is the registry key of the source of the file (``None`` for the
    position of the track ``store``); ``fetch`` the URL whose bytes the file is,
    unchanged, or ``None`` with ``fetch_reason`` saying why no URL serves it:
    ``credentials`` (a source whose ``auth`` is not ``none``) or ``built`` (a file
    Kartograf builds; `fetch_fields`).
    """

    track: Track
    segment: str
    hierarchy: str
    name: str
    unit: str
    local_label: str | None
    local_sha256: str | None
    available_label: str | None
    available_signal: dict[str, Any] | None
    status: ItemStatus
    error: str | None = None
    action: Action | None = None
    path: Path | None = None
    reason: str | None = None
    source: str | None = None
    fetch: Fetch | None = None
    fetch_reason: FetchReason | None = None

    @property
    def store_path(self) -> str:
        """The path of the position below the store (``nmt/pl_1992/N-34.asc``).

        It is the subject of the status lines of the CLI and the ``id`` of the
        position in the ``items`` of the result envelope.
        """
        return "/".join(
            part for part in (self.segment, self.hierarchy, self.name) if part
        )


@dataclass(frozen=True)
class UpdatePlan(Document):
    """Describe the plan of one write target (``kartograf-plan/1``).

    The plan of the store at ``root`` (the resolved store directory; ``mode``
    ``store``) or of the plain write into ``output_dir`` (the resolved directory;
    ``mode`` ``plain``, ``root`` ``None``): one of them is set. A detached plan
    (`detached_plan`) has ``output_dir`` ``"."`` and the ``path`` of each position
    relative to it.

    ``notices``: the messages emitted while the plan was built (what the
    checking command passed to ``on_notice``); ``ok``: no position failed to
    be checked (a computed property, never read from a plan file); ``sources``: the
    sources of the positions, each once, in the order of their first position.
    """

    SCHEMA = PLAN_SCHEMA
    JSON_KEYS = (
        "mode",
        "root",
        "output_dir",
        "checked_at",
        "kartograf_version",
        "items",
        "notices",
        "ok",
        "sources",
    )

    root: str | None
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    notices: tuple[Notice, ...] = ()
    output_dir: str | None = None
    sources: tuple[PlanSource, ...] = ()

    @property
    def mode(self) -> Mode:
        """Return ``plain`` for the plan of a write into a directory, else ``store``."""
        return "plain" if self.output_dir is not None else "store"

    @property
    def target(self) -> str:
        """Return the resolved store directory or output directory of the plan."""
        target = self.output_dir if self.output_dir is not None else self.root
        assert target is not None  # a plan names its store or its directory
        return target

    @property
    def ok(self) -> bool:
        """No position has the status ``check_failed``."""
        return all(item.status != "check_failed" for item in self.items)

    def prepare_context(self, ctx: EncodeContext) -> None:
        """Keep the paths of a detached plan relative to its ``output_dir`` ``"."``."""
        if self.output_dir == DETACHED:
            ctx.relative_paths = True

    @classmethod
    def from_json(cls, text: str) -> "UpdatePlan":
        """Read a plan; an unknown schema or a malformed plan = ``ValidationError``."""
        try:
            payload = json.loads(text)
        except ValueError as e:
            raise ValidationError(
                message("download.plan_not_json", error=reason(e))
            ) from e
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: object) -> "UpdatePlan":
        """Read a plan document (``to_dict`` or a plan file of 0.8.0-dev).

        A plan without ``notices`` and ``ok`` loads; ``ok`` is ignored (it is
        computed). A plan without ``sources`` and without the ``source``, ``fetch``
        and ``fetch_reason`` of its positions (0.9.0) loads with none of them. An
        unknown schema or a malformed plan = ``ValidationError``.
        """
        if not isinstance(payload, Mapping) or payload.get("schema") != PLAN_SCHEMA:
            schema = payload.get("schema") if isinstance(payload, Mapping) else None
            raise ValidationError(
                message(
                    "download.plan_unknown_schema",
                    schema=schema,
                    plan_schema=PLAN_SCHEMA,
                )
            )
        if "store" in payload and "root" not in payload:
            raise ValidationError(message("download.old_plan_store_key"), option="plan")
        try:
            items = tuple(_item(raw) for raw in payload["items"])
            notices = tuple(_notice(raw) for raw in payload.get("notices", ()))
            sources = tuple(_source(raw) for raw in payload.get("sources", ()))
            root, output_dir = payload["root"], payload.get("output_dir")
            if (root is None) == (output_dir is None):
                raise ValueError("exactly one of root and output_dir is set")
            return cls(
                root=None if root is None else str(root),
                output_dir=None if output_dir is None else str(output_dir),
                checked_at=str(payload["checked_at"]),
                kartograf_version=str(payload["kartograf_version"]),
                items=items,
                notices=notices,
                sources=sources,
            )
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            raise ValidationError(
                message("download.plan_incomplete", error=reason(e))
            ) from e

    def merge(self, other: "UpdatePlan") -> "UpdatePlan":
        """One plan of both (``--country auto``); the earlier ``checked_at`` wins.

        The notices of both plans are joined, in order, without repeats, and so are
        their sources (one per key, the first one).

        Raises
        ------
        ValidationError
            The plans describe different stores.
        """
        if (other.root, other.output_dir) != (self.root, self.output_dir):
            raise ValidationError(
                message(
                    "download.plan_merge_stores_differ",
                    target=self.target,
                    other_target=other.target,
                )
            )
        sources: dict[str, PlanSource] = {}
        for source in self.sources + other.sources:
            sources.setdefault(source.key, source)
        return replace(
            self,
            checked_at=min(self.checked_at, other.checked_at),
            items=self.items + other.items,
            notices=tuple(dict.fromkeys(self.notices + other.notices)),
            sources=tuple(sources.values()),
        )

    def items_for(self, track: Track) -> tuple[PlanItem, ...]:
        """Positions of one track, in plan order."""
        return tuple(item for item in self.items if item.track == track)


def _item(raw: dict[str, Any]) -> PlanItem:
    status = raw["status"]
    if status not in get_args(ItemStatus):
        raise ValidationError(
            message("download.plan_unknown_item_status", status=status)
        )
    track = raw["track"]
    if track not in TRACKS:
        raise ValidationError(message("download.plan_unknown_item_track", track=track))
    fetch_reason = raw.get("fetch_reason")
    if fetch_reason is not None and fetch_reason not in FETCH_REASONS:
        raise ValidationError(
            message("download.plan_unknown_fetch_reason", fetch_reason=fetch_reason)
        )
    fetch = raw.get("fetch")
    return PlanItem(
        track=cast(Track, track),
        segment=str(raw["segment"]),
        hierarchy=str(raw["hierarchy"]),
        name=str(raw["name"]),
        unit=str(raw["unit"]),
        local_label=raw.get("local_label"),
        local_sha256=raw.get("local_sha256"),
        available_label=raw.get("available_label"),
        available_signal=raw.get("available_signal"),
        status=cast(ItemStatus, status),
        error=raw.get("error"),
        action=cast(Action | None, raw.get("action")),
        path=Path(raw["path"]) if raw.get("path") is not None else None,
        reason=raw.get("reason"),
        source=raw.get("source"),
        fetch=None if fetch is None else _fetch(fetch),
        fetch_reason=cast(FetchReason | None, fetch_reason),
    )


def _fetch(raw: Mapping[str, object]) -> Fetch:
    url, size, sha256 = raw["url"], raw["size_bytes"], raw["sha256"]
    if size is not None and (not isinstance(size, int) or isinstance(size, bool)):
        raise ValueError(f"size_bytes {size!r} is not a whole number")
    return Fetch(
        url=None if url is None else str(url),
        size_bytes=size,
        sha256=None if sha256 is None else str(sha256),
    )


def _source(raw: Mapping[str, Any]) -> PlanSource:
    license = raw["license"]
    return PlanSource(
        key=str(raw["key"]),
        provider=str(raw["provider"]),
        license=LicenseInfo(
            str(license["id"]), str(license["attribution"]), str(license["url"])
        ),
        auth=str(raw["auth"]),
    )


def _notice(raw: Mapping[str, object]) -> Notice:
    level = raw["level"]
    if level not in ("info", "warning"):
        raise ValidationError(
            message("download.plan_unknown_notice_level", level=level)
        )
    return Notice(level, str(raw["code"]), str(raw["message"]))


def source_of(provider: object) -> str | None:
    """Return the registry key of the files of ``provider`` (``None``: it names none).

    The ``descriptor_key`` of a provider of the registry; a provider without one (a
    foreign provider, a stub) gives positions without a source.
    """
    key = getattr(provider, "descriptor_key", None)
    return key if isinstance(key, str) else None


def fetch_fields(
    source: str | None, fetch: Fetch | None
) -> tuple[Fetch | None, FetchReason | None]:
    """Return the ``fetch`` and ``fetch_reason`` of a planned file of ``source``.

    ``fetch`` is what the track knows of the URL whose bytes the file is unchanged,
    ``None`` for a file Kartograf builds rather than fetches (``built``: a WCS or
    ImageServer cutout, a merged or reprojected raster, HSG, a file written from
    features, a member read out of a ZIP, any file converted). A file of a source
    whose ``auth`` is not ``none`` is ``credentials`` whatever the track says: its
    URLs need a key exchange (CLMS OAuth, ``CLMS_CREDENTIALS``). A position without
    a source (the root of a store) has neither.
    """
    if source is None:
        return None, None
    if get_source(source).auth != "none":
        return None, "credentials"
    if fetch is None:
        return None, "built"
    return fetch, None


def plan_sources(items: Iterable[PlanItem]) -> tuple[PlanSource, ...]:
    """Return the sources of ``items`` from the registry, once each, in item order."""
    keys = dict.fromkeys(item.source for item in items if item.source is not None)
    return tuple(_plan_source(key) for key in keys)


def _plan_source(key: str) -> PlanSource:
    descriptor = get_source(key)
    return PlanSource(
        key, descriptor.provider_name, descriptor.license, descriptor.auth
    )


def store_id(root: str | Path) -> str:
    """Identity of a store in a plan: the resolved output directory.

    Written as every document writes a path (``Path.as_posix()``), so a plan names
    its store as the documents of the run do, on Windows too.
    """
    return Path(root).resolve().as_posix()


def plain_items(write: Staging, items: Iterable[PlanItem]) -> tuple[PlanItem, ...]:
    """Judge the positions of a plain write as a whole (DEV-19.10).

    One `plan_plain` over the names of every position: each gets its ``action``
    (``write``, ``replace`` with ``--force``, ``conflict``), its ``path`` and, for a
    conflict, its ``reason``; the ``status`` is ``missing`` for ``write`` and
    ``unverifiable`` for the others. A position whose source could not be checked
    stays as it is, as in the store: ``check_failed`` with its ``error`` and no
    action, path or reason, so the plan is not ``ok`` (the run fails that unit); its
    name still counts for the others, as in the preflight of the run. Called again on
    positions already judged, it judges them again (a plan merged from several tracks
    sees their duplicates).
    """
    listed = tuple(items)
    entries = write.plan([item.name for item in listed])
    return tuple(
        item
        if item.status == "check_failed"
        else replace(
            item,
            status="missing" if entry.action == "write" else "unverifiable",
            action=entry.action,
            path=entry.path,
            reason=entry.reason,
        )
        for item, entry in zip(listed, entries, strict=True)
    )


def new_plan(
    root: str | Path | None,
    items: Iterable[PlanItem],
    *,
    output_dir: str | Path | None = None,
) -> UpdatePlan:
    """Return the plan checked now: of the store ``root``, or of ``output_dir``.

    A ``root`` that is the handle root of a plain write (``kartograf.output.plain_of``)
    gives the plan of that write: its positions are judged by `plain_items` and its
    directory is the ``output_dir`` of the plan. ``sources`` are those of the
    positions (`plan_sources`).
    """
    write = plain_of(root)
    if write is not None:
        items, root, output_dir = plain_items(write, items), None, write.directory
    listed = tuple(items)
    return UpdatePlan(
        root=None if root is None else store_id(root),
        output_dir=None if output_dir is None else store_id(output_dir),
        checked_at=_clock.now().isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=listed,
        sources=plan_sources(listed),
    )


def detached_directory() -> Path:
    """Return a directory that does not exist, for a detached plan (ADR-063 dec. 4).

    A fresh name in the temporary directory of the system; nothing creates it (a check
    writes nothing), so the plan shows nothing of the disk of the process.
    """
    while True:
        directory = Path(tempfile.gettempdir()) / (
            _DETACHED_PREFIX + secrets.token_hex(8)
        )
        if not directory.exists():
            return directory


def detached_plan(plan: UpdatePlan, directory: Path) -> UpdatePlan:
    """Return the plan of a plain write into ``directory`` as the write into ``.``.

    ``directory`` is the `detached_directory` the plan was made for: ``output_dir``
    becomes ``"."`` and the ``path`` of each position is relative to it (a JSON
    document writes it as relative POSIX text, `UpdatePlan.prepare_context`).
    """
    bases = (directory, directory.resolve())

    def relative(path: Path) -> Path:
        for base in bases:
            if path.is_relative_to(base):
                return path.relative_to(base)
        return path

    return replace(
        plan,
        output_dir=DETACHED,
        items=tuple(
            item if item.path is None else replace(item, path=relative(item.path))
            for item in plan.items
        ),
    )


def conflict_plan(root: str | Path, refusal: KartografError) -> UpdatePlan:
    """Return the plan that lists the refusal of a store root as its one conflict.

    A write into a store root that is inside another store, holds one or is not
    empty is refused with ``conflict`` (``nested_store``, ``not_empty``; DEV-19.14).
    The plan of that write lists the refusal instead of raising it (DEV-19.10): one
    position of the track ``store`` with the action ``conflict``, the root as
    ``path`` and the ``reason``, status ``unverifiable``. The plan is ``ok``: only
    the run fails with ``conflict``. Nothing else is looked at, so no request is made.

    Raises
    ------
    KartografError
        ``refusal`` itself when it is no ``conflict``: a root without its marker is
        ``store_unavailable`` (``no_marker``) and an unreadable marker ``data_error``,
        and the plan fails as the run does, before any request.
    """
    if not isinstance(refusal, ConflictError):
        raise refusal
    root_id = store_id(root)
    item = PlanItem(
        track="store",
        segment="",
        hierarchy="",
        name=root_id,
        unit=root_id,
        local_label=None,
        local_sha256=None,
        available_label=None,
        available_signal=None,
        status="unverifiable",
        error=str(refusal),
        action="conflict",
        path=Path(root_id),
        reason=refusal.reason,
    )
    return new_plan(root, [item])


def refusal_plan(root: str | Path) -> UpdatePlan | None:
    """Plan the refusal of the store at ``root``, or return None when a write may go on.

    The first step of every check of a store write (``check_*``, ``--check``): the
    plan of a root that a write would refuse as a conflict is `conflict_plan`, a
    refusal of another code is raised (the run raises every one of them, `guard_store`).
    The handle root of a plain write is no store: None.
    """
    if plain_of(root) is not None:
        return None
    refusal = store_refusal(root)
    return None if refusal is None else conflict_plan(root, refusal)


def plans[F: Callable[..., UpdatePlan]](method: F) -> F:
    """Wrap a check method of an object that writes plain files or a store.

    Like `kartograf.output.writes`, and a store root that a write would refuse as a
    conflict is the plan of that conflict (`refusal_plan`), not the error.
    """
    return wrapping(method, refusal=refusal_plan)


def require_store(plan: UpdatePlan, store: str) -> None:
    """Reject a plan of another store.

    Raises
    ------
    ValidationError
        Before any request to the source.
    """
    if plan.root != store:
        raise ValidationError(
            message("download.plan_other_store", target=plan.target, store=store),
            option="plan",
        )


def _key(item: PlanItem) -> tuple[str, str, str, str | None, str]:
    signal = json.dumps(item.available_signal, sort_keys=True)
    return (item.segment, item.hierarchy, item.name, item.available_label, signal)


def select_planned(
    plan: UpdatePlan, fresh: list[PlanItem], track: Track
) -> tuple[list[PlanItem], list[PlanItem]]:
    """Positions of ``track`` to execute now: ``(todo, stale)``.

    ``todo``: fresh items matching a planned ``newer``/``missing`` position
    (same segment, hierarchy, name, available label and signal) and still
    ``newer``/``missing``. ``stale``: planned positions without such a
    fresh item (the source changed since the plan, or the file left the
    selection). A planned position now ``current`` is neither (already
    done); fresh items absent from the plan are skipped.
    """
    by_key = {_key(item): item for item in fresh if item.track == track}
    todo: list[PlanItem] = []
    stale: list[PlanItem] = []
    for planned in plan.items_for(track):
        if planned.status not in TODO_STATUSES:
            continue
        match = by_key.get(_key(planned))
        if match is None:
            stale.append(planned)
        elif match.status in TODO_STATUSES:
            todo.append(match)
    return todo, stale
