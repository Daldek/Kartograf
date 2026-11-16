"""The registry code of a failed unit (``UnitFailure.code``, ERR §4)."""

import re
from typing import get_args

import pytest

from kartograf._errors import BY_CODE
from kartograf.download.data import (
    FAILURE_CODES,
    FailureKind,
    UnitFailure,
    failure_kind,
)
from kartograf.exceptions import DownloadError, NoCoverageError, YearRangeError


def test_every_kind_has_a_registry_code_and_a_snake_case_reason():
    assert set(FAILURE_CODES) == set(get_args(FailureKind))
    for code, reason in FAILURE_CODES.values():
        assert code in BY_CODE
        assert reason is None or re.fullmatch(r"[a-z][a-z0-9_]*", reason)


@pytest.mark.parametrize(
    ("kind", "code", "reason"),
    [
        ("no_coverage", "no_data", "no_coverage"),
        ("year_out_of_range", "no_data", "year_out_of_range"),
        ("download", "source_unavailable", None),
        ("country", "source_unavailable", None),
    ],
)
def test_a_failed_unit_reports_the_code_of_its_kind(kind, code, reason):
    failure = UnitFailure("N-34-130-D", "PL", "text", kind)

    assert (failure.code, failure.reason) == (code, reason)


def test_the_kind_of_an_error_follows_its_class():
    year_range = YearRangeError(
        "m", sheets={"N-34": (2020,)}, min_year=2000, max_year=2010
    )

    assert failure_kind(NoCoverageError("m", "N-34")) == "no_coverage"
    assert failure_kind(year_range) == "year_out_of_range"
    assert failure_kind(DownloadError("m")) == "download"
    assert failure_kind(DownloadError("m"), "country") == "country"
    # a state of the data keeps its name whatever the default of the caller
    assert failure_kind(NoCoverageError("m", "N-34"), "country") == "no_coverage"
