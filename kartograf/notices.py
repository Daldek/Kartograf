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
# Collections (ADR-042, ADR-043): units of an area, size of a national file
# before its transfer, size of a unit file over 100 MiB before its transfer
# (``HEAD``, K9), ``--country auto`` narrowed to the countries with the product,
# source layers an area result leaves out on purpose (in the national file),
# chosen classes (``--layers``) a unit package has no file of (BDOO).
UNIT_LIST = "unit_list"
WHOLE_COUNTRY_SIZE = "whole_country_size"
DOWNLOAD_SIZE = "download_size"
AUTO_NARROWED_TO_CZ = "auto_narrowed_to_cz"
AREA_OMITTED = "area_omitted"
CLASSES_ABSENT = "classes_absent"
# Availability report: index records Kartograf does not download (outside the
# variant registry, format inconsistent with the file, sheet code outside
# SheetParser).
INDEX_UNSUPPORTED = "index_unsupported"
# Availability report CZ: models without sheet files (DMR 5G, DMP 1G) - only
# a cutout or a TM33 tile of the ImageServer, and their LAZ.
CZ_SERVICE_ONLY = "cz_service_only"

# A file above this size is announced (``DOWNLOAD_SIZE``) before its transfer
# (K9): collection units and the image sheets of ``download_data``.
LARGE_FILE_BYTES = 100 * 1024 * 1024


def size_text(length: int | None) -> str:
    """Size of a file in notices (``Content-Length`` of ``HEAD`` or a feed)."""
    if length is None:
        return "rozmiar nieznany (serwer nie podal Content-Length)"
    return f"{length} B (ok. {length / 1e6:.0f} MB)"


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
