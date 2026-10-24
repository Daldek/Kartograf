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
from kartograf.notices import Notice
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
    """Describe the plan of one store (``kartograf-plan/1``).

    Plan of one store (``kartograf-plan/1``); ``store`` = resolved output
    directory.

    ``notices``: the messages emitted while the plan was built (what the
    checking command passed to ``on_notice``); ``ok``: no position failed to
    be checked (a computed property, never read from a plan file).
    """

    SCHEMA = PLAN_SCHEMA
    JSON_KEYS = ("store", "checked_at", "kartograf_version", "items", "notices", "ok")

    store: str
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    notices: tuple[Notice, ...] = ()

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
        try:
            items = tuple(_item(raw) for raw in payload["items"])
            notices = tuple(_notice(raw) for raw in payload.get("notices", ()))
            return cls(
                store=str(payload["store"]),
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
        if other.store != self.store:
            raise ValidationError(
                f"Nie mozna polaczyc planow roznych magazynow ({self.store}, "
                f"{other.store})"
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
    )


def _notice(raw: Mapping[str, object]) -> Notice:
    level = raw["level"]
    if level not in ("info", "warning"):
        raise ValidationError(f"Nieznany poziom komunikatu planu {level!r}")
    return Notice(level, str(raw["code"]), str(raw["message"]))


def store_id(output_dir: str | Path) -> str:
    """Identity of a store in a plan: the resolved output directory."""
    return str(Path(output_dir).resolve())


def new_plan(output_dir: str | Path, items: Iterable[PlanItem]) -> UpdatePlan:
    """Return the plan of the store ``output_dir`` checked now."""
    return UpdatePlan(
        store=store_id(output_dir),
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
    if plan.store != store:
        raise ValidationError(
            f"Plan dotyczy innego magazynu ({plan.store}), nie {store}",
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
