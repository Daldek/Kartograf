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
"""

import json
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
from kartograf.serialization import Document

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
    ``status`` is ``missing`` for ``write`` and ``unverifiable`` for the others. All
    three are ``None`` in the store. The position of the track ``store`` is the root
    of a store that a write would refuse (``nested_store``, ``not_empty``; DEV-19.14):
    ``action`` is ``conflict``, ``path`` the root, ``reason`` why, ``error`` the text
    of the refusal, and ``name`` and ``unit`` are the root too.
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
    ``mode`` ``plain``, ``root`` ``None``): one of them is set.

    ``notices``: the messages emitted while the plan was built (what the
    checking command passed to ``on_notice``); ``ok``: no position failed to
    be checked (a computed property, never read from a plan file).
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
    )

    root: str | None
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    notices: tuple[Notice, ...] = ()
    output_dir: str | None = None

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
        computed). An unknown schema or a malformed plan = ``ValidationError``.
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
            )
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            raise ValidationError(
                message("download.plan_incomplete", error=reason(e))
            ) from e

    def merge(self, other: "UpdatePlan") -> "UpdatePlan":
        """One plan of both (``--country auto``); the earlier ``checked_at`` wins.

        The notices of both plans are joined, in order, without repeats.

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
        return replace(
            self,
            checked_at=min(self.checked_at, other.checked_at),
            items=self.items + other.items,
            notices=tuple(dict.fromkeys(self.notices + other.notices)),
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
    )


def _notice(raw: Mapping[str, object]) -> Notice:
    level = raw["level"]
    if level not in ("info", "warning"):
        raise ValidationError(
            message("download.plan_unknown_notice_level", level=level)
        )
    return Notice(level, str(raw["code"]), str(raw["message"]))


def store_id(root: str | Path) -> str:
    """Identity of a store in a plan: the resolved output directory."""
    return str(Path(root).resolve())


def plain_items(write: Staging, items: Iterable[PlanItem]) -> tuple[PlanItem, ...]:
    """Judge the positions of a plain write as a whole (DEV-19.10).

    One `plan_plain` over the names of every position: each gets its ``action``
    (``write``, ``replace`` with ``--force``, ``conflict``), its ``path`` and, for a
    conflict, its ``reason``; the ``status`` is ``missing`` for ``write`` and
    ``unverifiable`` for the others. Called again on positions already judged, it
    judges them again (a plan merged from several tracks sees their duplicates).
    """
    listed = tuple(items)
    entries = write.plan([item.name for item in listed])
    return tuple(
        replace(
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
    directory is the ``output_dir`` of the plan.
    """
    write = plain_of(root)
    if write is not None:
        items, root, output_dir = plain_items(write, items), None, write.directory
    return UpdatePlan(
        root=None if root is None else store_id(root),
        output_dir=None if output_dir is None else store_id(output_dir),
        checked_at=_clock.now().isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=tuple(items),
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
    path = Path(store_id(root))
    item = PlanItem(
        track="store",
        segment="",
        hierarchy="",
        name=str(path),
        unit=str(path),
        local_label=None,
        local_sha256=None,
        available_label=None,
        available_signal=None,
        status="unverifiable",
        error=str(refusal),
        action="conflict",
        path=path,
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
