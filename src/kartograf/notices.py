"""Provide structured data notices and the text helpers of user messages.

The notices are shared by command-level results and CLI output; the helpers
cover sizes, lists of names and flag names.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from kartograf.messages import Lang, localize, message

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
SKIPPED_INCOMPLETE = "skipped_incomplete"
FULL_SHEET_REDUNDANT = "full_sheet_redundant"
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
# A slow source announced with its measured answer time right before the
# request (GUGiK PRNG OGC API Features; the WCS series of a PL cutout tells
# its time in ``CUTOUT_SIZE``).
SLOW_SOURCE = "slow_source"
# Availability report: index records Kartograf does not download (outside the
# variant registry, format inconsistent with the file, sheet code outside
# SheetParser).
INDEX_UNSUPPORTED = "index_unsupported"
# Availability report CZ: models without sheet files (DMR 5G, DMP 1G) - only
# a cutout or a TM33 tile of the ImageServer, and their LAZ.
CZ_SERVICE_ONLY = "cz_service_only"
# Availability report PL: the area has no land (the sea within the territorial
# waters, an area beyond the state border) - every combination is "complete"
# for lack of land to cover.
NO_LAND = "no_land"

# A file above this size is announced (``DOWNLOAD_SIZE``) before its transfer
# (K9): collection units and the image sheets of ``download_data``.
LARGE_FILE_BYTES = 100 * 1024 * 1024


def size_text(length: int | None) -> str:
    """Size of a file in notices (``Content-Length`` of ``HEAD`` or a feed)."""
    if length is None:
        return message("notices.size_unknown")
    return message("notices.size_known", length=length, megabytes=length / 1e6)


# The units a ``UNIT_LIST`` notice names; the rest is only counted (an area of
# thousands of index tiles must not print one line of 100 KB before the volume
# limit refuses it).
LISTED_UNITS = 10


def names_text(names: Sequence[str]) -> str:
    """Return the names of the units of a notice.

    ``a, b, c``; over ``LISTED_UNITS`` of them the first ones and the rest counted:
    ``a, b, ..., j and 3 others``.
    """
    if len(names) <= LISTED_UNITS:
        return ", ".join(names)
    return message(
        "notices.names_more",
        listed=", ".join(names[:LISTED_UNITS]),
        rest=len(names) - LISTED_UNITS,
    )


def ascii_text(text: str, errors: str = "replace") -> str:
    """Return ``text`` for a `Notice`, whose message must be ASCII.

    An ASCII text is returned as it is, so a catalog message stays translatable; any
    other text gets its non-ASCII characters replaced (``errors`` is a codec error
    handler: ``"replace"``, ``"backslashreplace"``).
    """
    return text if text.isascii() else text.encode("ascii", errors).decode("ascii")


def cli_flag(name: str) -> str:
    """Return the CLI flag of a library parameter in messages.

    ``sheet_system`` -> ``--sheet-system`` (keys of the source registry are parameter
    names).
    """
    return "--" + name.replace("_", "-")


@dataclass(frozen=True)
class Notice:
    """An ASCII message about data, identified independently of its wording.

    ``message`` is English; a catalog `kartograf.messages.Message` there can be
    rendered in another language (`localized`).
    """

    level: Literal["info", "warning"]
    code: str
    message: str

    def __post_init__(self) -> None:
        """Check that the message of the notice is ASCII."""
        if not self.message.isascii():
            raise ValueError("The message of a notice must be ASCII")

    def localized(self, lang: Lang) -> "Notice":
        """Return the notice with its message rendered in ``lang``."""
        return replace(self, message=localize(self.message, lang))


class NoticeSink:
    """Collect notices and forward each once when it is emitted."""

    def __init__(self, on_notice: Callable[[Notice], None] | None) -> None:
        self._on_notice = on_notice
        self._notices: list[Notice] = []

    def emit(self, level: Literal["info", "warning"], code: str, message: str) -> None:
        """Record a notice before forwarding it to the optional callback."""
        self.add(Notice(level, code, message))

    def add(self, notice: Notice) -> None:
        """Record an already built notice (e.g. from a nested call) and forward it."""
        self._notices.append(notice)
        if self._on_notice is not None:
            self._on_notice(notice)

    @property
    def notices(self) -> tuple[Notice, ...]:
        """Immutable snapshot of notices emitted so far."""
        return tuple(self._notices)
