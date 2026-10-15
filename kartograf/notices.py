"""Structured data notices shared by command-level results and CLI output."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

SHEET_LIST = "sheet_list"
GEOMETRY_LAYER_DEFAULT = "geometry_layer_default"
AUTO_NARROWED_TO_PL = "auto_narrowed_to_pl"
AUTO_CLIPPED = "auto_clipped"
AUTO_AREA_OUTSIDE = "auto_area_outside"
AUTO_PARTIAL_SUCCESS = "auto_partial_success"
LEGACY_CAMPAIGNS_DIR = "legacy_campaigns_dir"
NEWER_AVAILABLE = "newer_available"
NO_COVERAGE_HINT = "no_coverage_hint"
NO_COVERAGE_SOME = "no_coverage_some"
UNVERIFIED_LOCAL = "unverified_local"
CHECK_FAILED = "check_failed"
BETTER_COVERAGE = "better_coverage"
LINK_OUTSIDE_RANGE = "link_outside_range"
SHEET_CRS_MISMATCH = "sheet_crs_mismatch"
INCOMPLETE_CAMPAIGN = "incomplete_campaign"
CUTOUT_SIZE = "cutout_size"
ALL_NODATA = "all_nodata"
LAZ_SUPERSEDED = "laz_superseded"
CORINE_PREVIEW = "corine_preview"
CACHE_DISABLED = "cache_disabled"
PROJECT_GEOMETRY_CHANGED = "project_geometry_changed"


@dataclass(frozen=True)
class Notice:
    """An ASCII message about data, identified independently of its wording."""

    level: Literal["info", "warning"]
    code: str
    text: str

    def __post_init__(self) -> None:
        if not self.text.isascii():
            raise ValueError("Tekst komunikatu musi byc zapisany w ASCII")


class NoticeSink:
    """Collect notices and forward each once when it is emitted."""

    def __init__(self, on_notice: Callable[[Notice], None] | None) -> None:
        self._on_notice = on_notice
        self._notices: list[Notice] = []

    def emit(self, level: Literal["info", "warning"], code: str, text: str) -> None:
        """Record a notice before forwarding it to the optional callback."""
        self.add(Notice(level, code, text))

    def add(self, notice: Notice) -> None:
        """Record an already built notice (e.g. from a nested call) and forward it."""
        self._notices.append(notice)
        if self._on_notice is not None:
            self._on_notice(notice)

    @property
    def notices(self) -> tuple[Notice, ...]:
        """Immutable snapshot of notices emitted so far."""
        return tuple(self._notices)
