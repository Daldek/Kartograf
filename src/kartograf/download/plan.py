"""
Update plan ``kartograf-plan/1`` shared by every download track (spec 4.4).

A plan lists the files of a request with their local version and the source
freshness signal, WITHOUT downloading anything. Every position belongs to a
track (``pl_sheet``, ``laz_tile``, ``cz_sheet``, ``cz_laz``, ``pl_cutout``,
``cz_cutout``, ``landcover``, ``hsg``, ``collection``, ``cz_orto``); ``unit``
is the task unit of the track (sheet code, LAZ tile sheet, CZ sheet, CZ LAZ
sheet, bbox coordinates, TERYT, country code of a national file, SM5 sheet of
the CZ orthophoto - four positions: the JPEG and its three world files).
Executing a plan (``--upgrade --plan``) re-checks the signal:
``select_planned`` keeps only the planned positions
whose fresh check is identical, the rest are ``stale``; positions removed
from the plan file are never executed.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast, get_args

from kartograf import _clock
from kartograf._version import build_version
from kartograf.exceptions import ValidationError
from kartograf.messages import message
from kartograf.notices import Notice
from kartograf.output import Action, Mode
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
    three are ``None`` in the store.
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
            raise ValidationError(f"Plan aktualizacji nie jest JSON: {e}") from e
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
                f"Nieznany schemat planu aktualizacji {schema!r} "
                f"(oczekiwano {PLAN_SCHEMA!r})"
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
            raise ValidationError(f"Niekompletny plan aktualizacji: {e}") from e

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
                f"Nie mozna polaczyc planow roznych magazynow ({self.target}, "
                f"{other.target})"
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
        raise ValidationError(f"Nieznany status pozycji planu {status!r}")
    track = raw["track"]
    if track not in TRACKS:
        raise ValidationError(f"Nieznany tor pozycji planu {track!r}")
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
        raise ValidationError(f"Nieznany poziom komunikatu planu {level!r}")
    return Notice(level, str(raw["code"]), str(raw["message"]))


def store_id(root: str | Path) -> str:
    """Identity of a store in a plan: the resolved output directory."""
    return str(Path(root).resolve())


def new_plan(
    root: str | Path | None,
    items: Iterable[PlanItem],
    *,
    output_dir: str | Path | None = None,
) -> UpdatePlan:
    """Return the plan checked now: of the store ``root``, or of ``output_dir``."""
    return UpdatePlan(
        root=None if root is None else store_id(root),
        output_dir=None if output_dir is None else store_id(output_dir),
        checked_at=_clock.now().isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=tuple(items),
    )


def require_store(plan: UpdatePlan, store: str) -> None:
    """Reject a plan of another store.

    Raises
    ------
    ValidationError
        Before any request to the source.
    """
    if plan.root != store:
        raise ValidationError(
            f"Plan dotyczy innego magazynu ({plan.target}), nie {store}",
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
