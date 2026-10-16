"""``kartograf elevation availability`` (ADR-041): the CLI only translates the
flags into ``check_availability`` and prints its report.

Answers: the recorded GUGiK index and PRG answers (``RecordedIndex``) and
the recorded CUZK index and ``HEAD`` answers (``CuzkSession``), see
``tests/test_availability.py``; no network, no data file.
"""

import re
from dataclasses import replace
from unittest.mock import patch

import pytest
import requests

from kartograf.cli import main
from kartograf.download.availability import COUNTRY_CHOICES
from tests.conftest import RecordedIndex, wfs_endpoint
from tests.test_availability import CTES86_DMPOK, TILE_DMPOK, _Border, _FailingHead
from tests.test_cuzk_laz import CuzkSession

SESSION = "kartograf.transport.http.make_gugik_session"
KRAKOW = ["--bbox", "565000,242000,569000,246000"]
POMORZE = ["--bbox", "339000,744800,343000,747000"]
CIESZYN = ["--bbox=-447000,-1114000,-446000,-1113000", "--bbox-crs", "EPSG:5514"]


def _areas(product: str, place: str) -> dict[str, list[str]]:
    return {
        f"{product}_{vcrs}": [f"area_{product}_{vcrs}_{place}.xml.gz"]
        for vcrs in ("evrf2007", "kron86")
    }


def _run(capsys, argv: list[str], session, product="nmt") -> tuple[int, str, str]:
    with patch(SESSION, return_value=session):
        code = main(["elevation", "availability", "--product", product, *argv])
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
    assert err == f"Error: --country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}\n"

    with pytest.raises(SystemExit) as error:
        _run(capsys, ["--country", "de", *KRAKOW], RecordedIndex())
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


# =============================================================================
# CZ and ``auto`` (plan B, decisions 9-10)
# =============================================================================

CZ_HEADER = [
    "MODEL",
    "UKLAD",
    "ROZDZ.",
    "WYSOKOSCI",
    "FORMAT",
    "ARKUSZE SA/BRAK",
    "PUBLIKACJA",
    "ROZMIAR",
    "KOMPLET",
]


def test_cz_table_without_years(capsys):
    code, out, err = _run(capsys, ["--country", "cz", *CIESZYN], CuzkSession(), "nmpt")

    assert code == 0
    assert out.startswith(
        "Dostepnosc NMPT CZ wg indeksu arkuszy i plikow CUZK: obszar 1,00 km2\n"
        "CUZK nie publikuje lat nalotu; daty = publikacja pliku\n\n"
    )
    header, *rows = _table(out)
    assert header == CZ_HEADER
    assert rows == [
        ["DMP OK", "S-JTSK", "0.5m", "Bpv", "TIFF", "1/0", "2025-10-10", "16,7 MB"]
        + ["tak"],
        ["DMP OK", "ETRS89-TM33", "0.5m", "EVRF2007", "TIFF", "1/0", "2026-08-20"]
        + ["29,6 MB", "tak"],
    ]
    assert out.endswith(
        "  DMP OK S-JTSK 0.5m Bpv TIFF\n"
        "    kartograf elevation download --product nmpt --sheet CTES86 "
        "--resolution 0.5m --vertical-crs Bpv\n"
        "  DMP OK ETRS89-TM33 0.5m EVRF2007 TIFF\n"
        "    kartograf elevation download --product nmpt --sheet 760_5516 "
        "--resolution 0.5m --vertical-crs EVRF2007\n"
    )
    assert err.startswith("Info: DMP 1G (2m) nie ma plikow arkuszy CUZK")


def test_cz_sheets_without_file(capsys):
    session = CuzkSession(missing=(CTES86_DMPOK, TILE_DMPOK))
    code, out, _ = _run(
        capsys, ["--country", "cz", *CIESZYN, "--details"], session, "nmpt"
    )

    assert code == 0
    s_jtsk, tm33 = _table(out)[1:]
    assert s_jtsk[5:] == ["0/1", "-", "-", "nie: 1 bez pliku (1,00 km2)"]
    # the tile is measured against the S-JTSK area (not its larger envelope in
    # EPSG:3045); the NE corner of the area lies east of it
    assert tm33[5:] == ["0/1", "-", "-", "nie: 1 bez pliku (99,26 ha)"]
    details = out.split("Szczegoly kombinacji:\n")[1]
    assert details.startswith(
        "  DMP OK S-JTSK 0.5m Bpv TIFF: nie: 1 bez pliku (1,00 km2)\n"
        "    arkusze bez pliku (1): CTES86\n"
    )
    assert "    arkusze bez pliku (1): 760_5516\n" in details
    assert "kartograf elevation download" not in out
    assert out.endswith(
        "Zadna kombinacja CZ nie ma plikow wszystkich arkuszy obszaru "
        "(arkusze bez pliku: --details)\n"
    )


def test_cz_footer_shows_five_commands(capsys):
    """Many sheets of a raster combination: the footer shows five commands
    and the number of the others; ``--details`` shows all of them."""
    from kartograf.download.availability import check_availability
    from tests.test_cuzk_laz import CIESZYN as CIESZYN_BBOX

    with patch(SESSION, return_value=CuzkSession()):
        report = check_availability(
            product="nmpt", country="cz", bbox=CIESZYN_BBOX, cache=False
        )
    hints = tuple(
        f"elevation download --product nmpt --sheet CTES8{n} --resolution 0.5m "
        "--vertical-crs Bpv"
        for n in range(7)
    )
    many = replace(
        report, combinations=(replace(report.combinations[0], download_hint=hints),)
    )
    argv = ["elevation", "availability", "--product", "nmpt", "--country", "cz"]

    with patch("kartograf.cli.availability_cmd.check_availability", return_value=many):
        main([*argv, *CIESZYN])
        footer = capsys.readouterr().out.split("Kompletne kombinacje CZ")[1]
        main([*argv, *CIESZYN, "--details"])
        details = capsys.readouterr().out.split("Kompletne kombinacje CZ")[0]

    shown = [line for line in footer.splitlines() if "kartograf elevation" in line]
    assert shown == [f"    kartograf {hint}" for hint in hints[:5]]
    assert footer.endswith(
        "    ... pozostale polecenia: 2 (wszystkie: --details albo --json)\n"
    )
    assert all(f"    kartograf {hint}\n" in details for hint in hints)


def test_auto_tables_per_country(capsys):
    code, out, _ = _run(
        capsys, ["--country", "auto", *CIESZYN], _Border("nmpt"), "nmpt"
    )

    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("Dostepnosc NMPT PL wg skorowidza GUGiK: obszar ")
    dates = lines.index("CUZK nie publikuje lat nalotu; daty = publikacja pliku")
    assert lines[dates - 1].startswith("Dostepnosc NMPT CZ wg indeksu arkuszy")
    assert re.split(r" {2,}", lines[dates + 2].strip()) == CZ_HEADER
    assert "Najnowsza kompletna kombinacja: 2024 PL-1992 0.5m EVRF2007 ASC" in out
    assert "  DMP OK S-JTSK 0.5m Bpv TIFF\n" in out


def test_auto_part_failed_exit_code(capsys):
    """A country that could not be checked: the report of the other one, a
    warning and exit code 1 (the answer is incomplete)."""
    session = _Border("nmpt", _FailingHead(TILE_DMPOK))
    with patch("time.sleep"):
        code, out, err = _run(capsys, ["--country", "auto", *CIESZYN], session, "nmpt")

    assert code == 1
    assert out.startswith("Dostepnosc NMPT PL wg skorowidza GUGiK")
    assert "Dostepnosc NMPT CZ" not in out
    assert "Warning: --country auto: nie udalo sie sprawdzic czesci CZ" in err
