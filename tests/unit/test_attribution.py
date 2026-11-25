"""The provider lines of the Nogat standard (``kartograf.attribution``, DEV §20).

The lines are those of the table of the standard that ``_data/provider_lines.json``
copies; ``L`` filled for CAMELS-PL 2.1.0 and 2.0.0 (ADR-062); G, SG and Z of the
sources of GUGiK, ISRIC SoilGrids and ČÚZK, filled from the metadata of a file
(ADR-064). ``ATTRIBUTION.txt`` is written into the output directory of a plain
``Staging``.
"""

import hashlib
import json
from importlib import resources

import pytest

from kartograf.attribution import (
    ATTRIBUTION_FILE,
    UNKNOWN,
    add_lines,
    date_parts,
    file_lines,
    merge_lines,
    plan_attribution,
    provider_lines,
    source_line,
    split_terms,
    write_attribution,
)
from kartograf.exceptions import ConflictError
from kartograf.output import PlanEntry, Staging
from kartograf.sources.registry import all_sources, get_source
from kartograf.sources.sidecar import build_metadata

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


# --- the lines of GUGiK, ISRIC SoilGrids and ČÚZK (ADR-064) -----------------------

G_TEXT = (
    "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, {products} "
    "(wytworzono {period}, pozyskano {date}); dane przetworzone"
)
Z_TEXT = (
    "Źródło: Český úřad zeměměřický a katastrální (ČÚZK), {products} "
    "(pozyskano {date}), licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/); dane przetworzone"
)
SG = (
    "Źródło: ISRIC – World Soil Information, SoilGrids, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/); dane przetworzone"
)
NMT = "pl.gugik.nmt_1m"
PRG = "pl.gugik.prg"
RUIAN = "cz.cuzk.ruian"
SOILGRIDS = "global.isric.soilgrids"
CORINE = "eu.clms.corine"
CAMELS = "pl.camels.camels"


def _g(products: str, period: str, date: str) -> str:
    return G_TEXT.format(products=products, period=period, date=date)


def _z(products: str, date: str) -> str:
    return Z_TEXT.format(products=products, date=date)


@pytest.mark.parametrize(
    ("key", "line"),
    [
        (NMT, _g("NMT", "2022", "2026-10-12")),
        (RUIAN, _z("RÚIAN", "2026-10-12")),
        (SOILGRIDS, SG),
    ],
    ids=["G", "Z", "SG"],
)
def test_source_line_names_the_product_the_year_and_the_day_its_line_asks_for(
    key, line
):
    assert source_line(get_source(key), years=[2022], days=["2026-10-12"]) == line


def test_source_line_without_a_year_or_a_day_says_b_d():
    assert source_line(get_source(PRG)) == _g("PRG", UNKNOWN, UNKNOWN)


def test_source_line_of_a_provider_the_table_lacks_is_none():
    assert source_line(get_source(CORINE)) is None


def test_merge_lines_joins_the_g_of_several_files_into_one_line():
    """The products each once in the order they came, the years and the days from
    the first to the last (DEV §20)."""
    merged = merge_lines(
        [_g("NMT", "2022", "2026-10-12")],
        [_g("BDOT10k", "2025", "2026-03-24"), _g("NMT", "2020", "2026-10-29")],
    )

    assert merged == (
        "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, NMT, BDOT10k "
        "(wytworzono 2020–2025, pozyskano 2026-03-24 – 2026-10-29); "
        "dane przetworzone",
    )


def test_merge_lines_keeps_b_d_only_while_no_line_names_a_value():
    merged = merge_lines([_g("PRG", UNKNOWN, UNKNOWN)], [_g("NMT", "2021", UNKNOWN)])

    assert merged == (_g("PRG, NMT", "2021", UNKNOWN),)


def test_merge_lines_joins_the_z_lines_and_puts_g_sg_z_in_the_order_of_the_table():
    merged = merge_lines(
        [_z("RÚIAN", "2026-10-13"), SG],
        [L_21, RD],
        [_g("NMT", "2022", "2026-10-12"), _z("DMR 5G", "2026-10-12")],
    )

    assert merged == (
        L_21,
        _g("NMT", "2022", "2026-10-12"),
        SG,
        _z("RÚIAN, DMR 5G", "2026-10-12 – 2026-10-13"),
        RD,
    )


def test_date_parts_split_a_line_around_its_day():
    before, after = _g("NMT", "2022", "<>").split("<>")

    assert date_parts(_g("NMT", "2022", "2026-10-12")) == (before, after)
    assert date_parts(SG) is None
    assert date_parts("Data: a provider of its own") is None


def test_file_lines_fill_the_line_of_a_sidecar_from_its_metadata():
    """The year of the flight and the UTC day of the download, whatever
    ``license.attribution`` a sidecar written before the lines holds."""
    meta = {
        "dataset": NMT,
        "downloaded_at": "2026-10-12T23:59:59.000001+00:00",
        "extra": {"campaign": {"date": "2022-05-10"}},
        "license": {"id": "PL-PGiK-40a", "attribution": "Dane: Glowny Urzad"},
    }

    assert file_lines(meta) == (_g("NMT", "2022", "2026-10-12"),)


@pytest.mark.parametrize(
    ("extra", "period"),
    [
        ({"http": {"last_modified": "Tue, 03 Mar 2026 10:00:00 GMT"}}, "2026"),
        ({"http": {"last_modified": "no date"}}, UNKNOWN),
        ({}, UNKNOWN),
    ],
    ids=["last-modified", "unreadable", "none"],
)
def test_file_lines_without_a_data_year_take_the_year_the_file_was_served(
    extra, period
):
    meta = {
        "dataset": PRG,
        "downloaded_at": "2026-10-12T08:00:00+00:00",
        "extra": extra,
    }

    assert file_lines(meta) == (_g("PRG", period, "2026-10-12"),)


def test_file_lines_of_a_source_without_a_line_are_its_license_attribution():
    """A CAMELS-PL file carries the lines of its release (ADR-062); a dataset this
    Kartograf does not know, the text its sidecar holds."""
    camels = {
        "dataset": CAMELS,
        "license": {"attribution": "\n".join([S, P, L_21, RD]) + "\n"},
    }
    unknown = {"dataset": "xx.other", "license": {"attribution": "Data: other"}}

    assert file_lines(camels) == (S, P, L_21, RD)
    assert file_lines(unknown) == ("Data: other",)
    assert file_lines({"dataset": "xx.other"}) == ()


def test_build_metadata_writes_the_filled_line_into_license_attribution(
    frozen_clock,
):
    nmt = get_source(NMT)

    meta = build_metadata(
        nmt,
        request={"sheet": "N-34-130-D-d-2-4"},
        extra={"campaign": {"date": "2022-05-10"}},
    )

    assert meta.license == {
        "id": nmt.license.id,
        "attribution": _g("NMT", "2022", "2026-10-12"),
        "url": nmt.license.url,
    }


def test_line_products_name_the_product_of_every_source_of_g_and_z_and_no_other():
    """Every source whose licence names G or Z has its ``<products>`` (a new GUGiK
    or ČÚZK source needs its name); a name holds no ``, `` (the join of the
    products) and no parenthesis (the fixed text after the products)."""
    products = json.loads(
        resources.files("kartograf")
        .joinpath("_data", "line_products.json")
        .read_text(encoding="utf-8")
    )["products"]
    lined = {s.key for s in all_sources() if s.license.line in ("G", "Z")}

    assert set(products) == lined
    for name in products.values():
        assert name.strip() == name and name and ", " not in name, name
        assert not set(name) & set("()"), name


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


def test_add_lines_merges_the_lines_of_each_file_placed_into_one_file(tmp_path):
    """The second file's G joins the first's; the file stays ``written`` for the
    write that made it, and a write whose files are not kept adds nothing."""
    out = tmp_path / "out"

    with Staging(out) as write:
        add_lines(write, [_g("NMT", "2022", "2026-10-12")])
        add_lines(write, [_g("PRG", UNKNOWN, "2026-10-12"), SG])
        with write.scratch() as inputs:
            add_lines(inputs, [_z("RÚIAN", "2026-10-12")])
            scratch = inputs.attribution
        written = write.attribution

    assert (out / ATTRIBUTION_FILE).read_text("utf-8") == (
        f"{_g('NMT, PRG', '2022', '2026-10-12')}\n{SG}\n"
    )
    assert written is not None and written.status == "written"
    assert scratch is None
