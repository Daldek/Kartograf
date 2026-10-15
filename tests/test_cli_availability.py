"""``kartograf elevation availability`` (ADR-041): the CLI only translates the
flags into ``check_availability`` and prints its report.

Answers: the recorded GUGiK index and PRG answers (``RecordedIndex``, see
``tests/test_availability.py``); no network, no data file.
"""

import re
from unittest.mock import patch

import pytest
import requests

from kartograf.cli import main
from tests.conftest import RecordedIndex, wfs_endpoint

SESSION = "kartograf.transport.http.make_gugik_session"
KRAKOW = ["--bbox", "565000,242000,569000,246000"]
POMORZE = ["--bbox", "339000,744800,343000,747000"]


def _areas(product: str, place: str) -> dict[str, list[str]]:
    return {
        f"{product}_{vcrs}": [f"area_{product}_{vcrs}_{place}.xml.gz"]
        for vcrs in ("evrf2007", "kron86")
    }


def _run(capsys, argv: list[str], session) -> tuple[int, str, str]:
    with patch(SESSION, return_value=session):
        code = main(["elevation", "availability", "--product", "nmt", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _table(out: str) -> list[list[str]]:
    """Rows of the table (cells split on runs of two or more spaces)."""
    lines = out.split("\n\n")[1].splitlines()
    return [re.split(r" {2,}", line.strip()) for line in lines]


def test_table_sorted_and_footer(capsys):
    code, out, err = _run(
        capsys,
        ["--country", "pl", *KRAKOW],
        RecordedIndex(_areas("nmt", "krakow")),
    )

    assert code == 0 and err == ""
    assert out.startswith(
        "Dostepnosc NMT PL wg skorowidza GUGiK: obszar 16,00 km2, w tym lad 16,00 km2\n"
    )
    header, *rows = _table(out)
    assert header == [
        "ROK",
        "NALOT",
        "UKLAD",
        "ROZDZ.",
        "WYSOKOSCI",
        "FORMAT",
        "ARKUSZE TAK/NIE",
        "KOMPLET",
    ]
    years = [int(row[0]) for row in rows]
    assert years == sorted(years, reverse=True) and years[0] == 2025
    assert rows[0][2:] == ["PL-1992", "1m", "EVRF2007", "ASC", "6/0", "tak"]
    hint = (
        "elevation download --product nmt --country pl --bbox "
        "565000,242000,569000,246000 --sheet-system 1992 --resolution 1m "
        "--vertical-crs EVRF2007 --year 2025"
    )
    assert out.endswith(
        "Najnowsza kompletna kombinacja: 2025 PL-1992 1m EVRF2007 ASC\n"
        f"  Pobranie (dodaj --output KATALOG): kartograf {hint}\n"
        f"  W projekcie: kartograf project add NAZWA {hint}\n"
    )


def test_incomplete_cells_name_partial_sheets_and_uncovered_land(capsys):
    code, out, _ = _run(
        capsys,
        ["--country", "pl", *POMORZE],
        RecordedIndex(_areas("nmt", "pomorze"), coast=True),
    )

    assert code == 0
    rows = {(row[0], row[3], row[5]): row for row in _table(out)[1:]}
    assert rows[("2025", "0.5m", "ASC")][-1] == "nie: 4 niepelne"
    assert rows[("2022", "1m", "ASC")][-1] == "nie: brak arkuszy dla 0,88 ha"
    assert rows[("2022", "0.5m", "ASC")][-2:] == ["1/3", "nie: 3 niepelne"]
    # the newest complete combination of Pomorze is an archive
    assert "Najnowsza kompletna kombinacja: 2010 PL-1992 25m KRON86 TBD" in out
    assert "--format TBD --resolution 25m --vertical-crs KRON86 --year 2010" in out


def test_details_lists_partial_and_uncovered(capsys):
    _, out, _ = _run(
        capsys,
        ["--country", "pl", *POMORZE, "--year", "2022", "--details"],
        RecordedIndex(_areas("nmt", "pomorze"), coast=True),
    )

    details = out.split("Szczegoly kombinacji:\n")[1]
    assert (
        "  2022 PL-1992 0.5m EVRF2007 ASC: nie: 3 niepelne\n    arkusze niepelne (3): "
    ) in details
    assert (
        "  2022 PL-1992 1m EVRF2007 ASC: nie: brak arkuszy dla 0,88 ha\n"
        "    lad bez zadnego arkusza kombinacji: 0,88 ha\n"
        "    kartograf elevation download --product nmt --country pl --bbox "
        "339000,744800,343000,747000 --sheet-system 1992 --resolution 1m "
        "--vertical-crs EVRF2007 --year 2022\n"
    ) in details
    assert "Zadna kombinacja nie pokrywa calego ladu" in out


def test_exit_codes(capsys):
    code, out, err = _run(capsys, ["--country", "pl", *KRAKOW], RecordedIndex())
    assert code == 0 and err == ""
    assert out.endswith("\nBrak arkuszy NMT dla obszaru w skorowidzu GUGiK\n")

    failing = RecordedIndex(
        _areas("nmt", "krakow"),
        fail={wfs_endpoint("nmt_evrf2007"): requests.ConnectionError("reset")},
    )
    with patch("time.sleep"):
        # --force: the empty answer of the run above is in the cache
        code, out, err = _run(capsys, ["--country", "pl", *KRAKOW, "--force"], failing)
    assert code == 1 and out == ""
    assert err.startswith("Error: ") and "wynik bylby niepelny" in err

    code, _, err = _run(capsys, KRAKOW, RecordedIndex())
    assert code == 1
    assert err == "Error: --country wymagane z --bbox/--geometry: pl (GUGiK)\n"

    with pytest.raises(SystemExit) as error:
        _run(capsys, ["--country", "cz", *KRAKOW], RecordedIndex())
    assert error.value.code == 2


def test_notices_on_stderr(capsys):
    session = RecordedIndex(
        {"nmt_evrf2007": ["sheet_nmt_evrf2007_N-33-142-B-b-4-1.xml"]}
    )
    code, out, err = _run(capsys, ["--sheet", "N-33-142-B-b-4-1"], session)

    assert code == 0
    assert err.startswith(
        "Info: Skorowidz GUGiK ma dla obszaru tez rekordy, ktorych Kartograf nie "
        "pobiera: ARC/INFO ASCII GRID 1m EVRF2007 (2019; arkusze: 4)"
    )
    assert "Info:" not in out


def test_force_skips_the_cache(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    argv = ["--country", "pl", *KRAKOW, "--year", "2025"]
    first = RecordedIndex(_areas("nmt", "krakow"))
    _run(capsys, argv, first)
    cached = RecordedIndex(fail={"https://": AssertionError("network")})
    _, out_cached, _ = _run(capsys, argv, cached)
    forced = RecordedIndex(_areas("nmt", "krakow"))
    _, out_forced, _ = _run(capsys, [*argv, "--force"], forced)

    assert first.urls and cached.urls == [] and forced.urls
    assert out_cached == out_forced
