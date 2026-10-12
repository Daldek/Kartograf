"""
Update plan ``kartograf-plan/1`` shared by every download track (spec 4.4).

A plan lists the files of a request with their local version and the source
freshness signal, WITHOUT downloading anything. Every position belongs to a
track (``pl_sheet``, ``laz_tile``, ``cz_sheet``, ``pl_cutout``,
``cz_cutout``, ``landcover``, ``hsg``); ``unit`` is the task unit of the
track (sheet code, LAZ tile sheet, CZ sheet, bbox coordinates, TERYT).
Executing a plan (``--upgrade --plan``) re-checks the signal:
``select_planned`` keeps only the planned positions
whose fresh check is identical, the rest are ``stale``; positions removed
from the plan file are never executed.
"""

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast, get_args

from kartograf._version import build_version
from kartograf.exceptions import ValidationError

PLAN_SCHEMA = "kartograf-plan/1"
ItemStatus = Literal["current", "newer", "missing", "unverifiable", "check_failed"]
Track = Literal[
    "pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout", "landcover", "hsg"
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
    """

    track: Track
    segment: str
    hierarchy: str
    name: str
    unit: str
    local_label: str | None
    local_sha256: str | None
    available_label: str | None
    available_signal: dict | None
    status: ItemStatus
    error: str | None = None


@dataclass(frozen=True)
class UpdatePlan:
    """Plan of one store; ``store`` = resolved output directory."""

    store: str
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    schema: str = PLAN_SCHEMA

    def to_json(self) -> str:
        """The plan as JSON (``kartograf-plan/1``)."""
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "UpdatePlan":
        """Read a plan; an unknown schema or a malformed plan = ``ValidationError``."""
        try:
            payload = json.loads(text)
        except ValueError as e:
            raise ValidationError(f"Plan aktualizacji nie jest JSON: {e}") from e
        if not isinstance(payload, dict) or payload.get("schema") != PLAN_SCHEMA:
            schema = payload.get("schema") if isinstance(payload, dict) else None
            raise ValidationError(
                f"Nieznany schemat planu aktualizacji {schema!r} "
                f"(oczekiwano {PLAN_SCHEMA!r})"
            )
        try:
            items = tuple(_item(raw) for raw in payload["items"])
            return cls(
                store=str(payload["store"]),
                checked_at=str(payload["checked_at"]),
                kartograf_version=str(payload["kartograf_version"]),
                items=items,
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise ValidationError(f"Niekompletny plan aktualizacji: {e}") from e

    def merge(self, other: "UpdatePlan") -> "UpdatePlan":
        """One plan of both (``--country auto``); the earlier ``checked_at`` wins.

        Raises
        ------
        ValidationError
            The plans describe different stores.
        """
        if other.store != self.store:
            raise ValidationError(
                f"Nie mozna polaczyc planow roznych magazynow ({self.store}, "
                f"{other.store})"
            )
        return replace(
            self,
            checked_at=min(self.checked_at, other.checked_at),
            items=self.items + other.items,
        )

    def items_for(self, track: Track) -> tuple[PlanItem, ...]:
        """Positions of one track, in plan order."""
        return tuple(item for item in self.items if item.track == track)


def _item(raw: dict) -> PlanItem:
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
    )


def store_id(output_dir: str | Path) -> str:
    """Identity of a store in a plan: the resolved output directory."""
    return str(Path(output_dir).resolve())


def new_plan(output_dir: str | Path, items: Iterable[PlanItem]) -> UpdatePlan:
    """A plan of the store ``output_dir`` checked now."""
    return UpdatePlan(
        store=store_id(output_dir),
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=tuple(items),
    )


def require_store(plan: UpdatePlan, store: str) -> None:
    """Reject a plan of an unknown schema or of another store.

    Raises
    ------
    ValidationError
        Before any request to the source.
    """
    if plan.schema != PLAN_SCHEMA:
        raise ValidationError(
            f"Nieznany schemat planu aktualizacji {plan.schema!r} "
            f"(oczekiwano {PLAN_SCHEMA!r})"
        )
    if plan.store != store:
        raise ValidationError(
            f"Plan dotyczy innego magazynu ({plan.store}), nie {store}"
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
