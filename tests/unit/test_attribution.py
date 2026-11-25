"""The provider lines of the Nogat standard (``kartograf.attribution``, DEV §20).

The lines are those of the table of the standard that ``_data/provider_lines.json``
copies; ``L`` filled for CAMELS-PL 2.1.0 and 2.0.0 (ADR-062). ``ATTRIBUTION.txt`` is
written into the output directory of a plain ``Staging``.
"""

import hashlib

import pytest

from kartograf.attribution import (
    ATTRIBUTION_FILE,
    merge_lines,
    plan_attribution,
    provider_lines,
    split_terms,
    write_attribution,
)
from kartograf.exceptions import ConflictError
from kartograf.output import PlanEntry, Staging

S = (
    "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – "
    "Państwowy Instytut Badawczy"
)
P = (
    "Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu "
    "Badawczego zostały przetworzone"
)
L_21 = (
    "Źródło danych: CAMELS-PL 2.1.0 (Brzezińska i in., 2026), "
    "https://doi.org/10.5281/zenodo.23275336, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/)"
)
L_20 = (
    "Źródło danych: CAMELS-PL 2.0.0 (Brzezińska i in., 2026), "
    "https://doi.org/10.5281/zenodo.23102156, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/)"
)
LP = "Dane CAMELS-PL zostały przetworzone"
RD = "Regulamin danych IMGW-PIB: https://danepubliczne.imgw.pl/regulations"
RE = "Regulamin danych E-OBS: https://www.ecad.eu/documents/ECAD_datapolicy.pdf"
RELEASE_21 = {"version": "2.1.0", "year": "2026", "doi": "10.5281/zenodo.23275336"}


# --- provider_lines -------------------------------------------------------------


@pytest.mark.parametrize(
    "codes",
    [("S", "P", "L"), ("L", "P", "S"), ("P", "L", "S", "L", "S")],
    ids=["standard-order", "reversed", "repeated"],
)
def test_provider_lines_come_in_the_order_of_the_standard_each_once(codes):
    assert provider_lines(codes, **RELEASE_21) == (S, P, L_21)


def test_provider_lines_put_a_processed_text_after_its_text_and_terms_last():
    lines = provider_lines(["RE", "LP", "RD", "P", "L", "S"], **RELEASE_21)

    assert lines == (S, P, L_21, LP, RD, RE)


def test_split_terms_parts_the_terms_lines_from_the_attribution_lines():
    own = "Źródło: sieć operatora"  # a line the table does not hold (DEV-20.4)

    parts = split_terms([S, P, L_21, own, RD, RE])

    assert parts == ((S, P, L_21, own), (RD, RE))


def test_provider_lines_fill_l_with_the_version_year_and_doi_of_a_release():
    lines = provider_lines(
        ["L"], version="2.0.0", year="2026", doi="10.5281/zenodo.23102156"
    )

    assert lines == (L_20,)


def test_provider_lines_without_a_placeholder_need_no_values():
    assert provider_lines(["P", "S"]) == (S, P)


def test_provider_lines_of_a_code_the_standard_lacks_is_key_error():
    with pytest.raises(KeyError):
        provider_lines(["S", "X"], **RELEASE_21)


def test_provider_lines_without_a_value_of_a_placeholder_is_key_error():
    with pytest.raises(KeyError, match="doi"):
        provider_lines(["S", "L"], version="2.1.0", year="2026")


# --- merge_lines -----------------------------------------------------------------


def test_merge_lines_keeps_the_l_lines_of_two_releases_in_their_order():
    assert merge_lines([S, P, L_21], [S, P, L_20]) == (S, P, L_21, L_20)
    assert merge_lines([S, P, L_20], [S, P, L_21]) == (S, P, L_20, L_21)


def test_merge_lines_puts_lines_the_table_lacks_after_its_lines_and_terms_last():
    """A line of a provider the table does not hold keeps its place among such
    lines, after the lines of the table; the terms lines come last."""
    first, second = "Data: a provider of its own, CC0", "Data: another one"

    merged = merge_lines([RD, first, L_21], [S, second, P, first])

    assert merged == (S, P, L_21, first, second, RD)


def test_merge_lines_takes_each_line_once():
    assert merge_lines([S, S, P], [P, S], []) == (S, P)


# --- ATTRIBUTION.txt of a plain write ---------------------------------------------


def test_write_attribution_writes_a_new_file_and_leaves_no_staging(tmp_path):
    out = tmp_path / "out"
    lines = provider_lines(["S", "P", "L"], **RELEASE_21)

    with Staging(out) as write:
        planned = plan_attribution(write, lines)
        written = write_attribution(write, lines)

    target = out / ATTRIBUTION_FILE
    content = f"{S}\n{P}\n{L_21}\n".encode()
    assert planned == PlanEntry(target, "write")
    assert written is not None
    assert (written.path, written.status) == (target, "written")
    assert (written.size_bytes, written.sha256) == (
        len(content),
        hashlib.sha256(content).hexdigest(),
    )
    assert target.read_bytes() == content
    assert [path.name for path in out.iterdir()] == [ATTRIBUTION_FILE]


def test_write_attribution_merges_new_lines_into_a_file_and_removes_none(tmp_path):
    """The lines of another release and of another tool stay; the new ``L`` line
    comes after the ``L`` line before it."""
    target = tmp_path / ATTRIBUTION_FILE
    target.write_text(f"{S}\n{P}\n{L_20}\nData: a provider of its own\n", "utf-8")

    with Staging(tmp_path, force=False) as write:
        planned = plan_attribution(write, [S, P, L_21])
        written = write_attribution(write, [S, P, L_21])

    assert planned == PlanEntry(target, "replace")
    assert written is not None and written.status == "replaced"
    assert target.read_text("utf-8") == (
        f"{S}\n{P}\n{L_20}\n{L_21}\nData: a provider of its own\n"
    )


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_attribution_that_holds_every_line_is_left_as_it_is(tmp_path, newline):
    """A file written with ``CRLF`` (``write_text`` on Windows) holds its lines too."""
    target = tmp_path / ATTRIBUTION_FILE
    content = f"{S}{newline}{P}{newline}{L_21}{newline}".encode()
    target.write_bytes(content)
    before = target.stat().st_mtime_ns

    with Staging(tmp_path) as write:
        planned = plan_attribution(write, [L_21, S])
        written = write_attribution(write, [L_21, S])

    assert (planned, written) == (None, None)
    assert target.stat().st_mtime_ns == before
    assert target.read_bytes() == content


def test_attribution_without_lines_is_not_written(tmp_path):
    with Staging(tmp_path) as write:
        assert plan_attribution(write, []) is None
        assert write_attribution(write, []) is None

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["not-utf-8", "directory"])
def test_attribution_that_is_no_readable_utf8_file_is_a_conflict(tmp_path, kind):
    """Without ``force`` nothing is written over it: the conflict ``output_exists``
    of a plain write."""
    target = tmp_path / ATTRIBUTION_FILE
    if kind == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"\xff\xfe" + S.encode("utf-16-le"))

    with Staging(tmp_path) as write:
        planned = plan_attribution(write, [S, P])
        with pytest.raises(ConflictError) as raised:
            write_attribution(write, [S, P])

    assert planned == PlanEntry(target, "conflict", "output_exists")
    assert raised.value.reason == "output_exists"
    assert raised.value.paths == (str(target),)
    if kind == "directory":
        assert list(target.iterdir()) == []
    else:
        assert target.read_bytes() == b"\xff\xfe" + S.encode("utf-16-le")


def test_attribution_that_is_no_utf8_text_is_replaced_by_the_lines_when_forced(
    tmp_path,
):
    """``force`` replaces it as any existing target: the provider lines alone."""
    target = tmp_path / ATTRIBUTION_FILE
    target.write_bytes(b"\xff\xfe" + S.encode("utf-16-le"))

    with Staging(tmp_path, force=True) as write:
        planned = plan_attribution(write, [P, S])
        written = write_attribution(write, [P, S])

    assert planned == PlanEntry(target, "replace")
    assert written is not None and written.status == "replaced"
    assert target.read_text("utf-8") == f"{S}\n{P}\n"
