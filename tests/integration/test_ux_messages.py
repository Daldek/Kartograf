"""Input errors and input rules of the 0.8.0 UX review: the same text and
result from the CLI and the library, before any network."""

import json

import pytest

from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.download.collections import validate_collection_request
from kartograf.download.data import download_data, validate_data_request
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager

SHEET = "N-34-130-D-d-2-4"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Every check below happens before a request: a request is a failure."""

    def refuse(*args, **kwargs):
        raise AssertionError("request before validation")

    monkeypatch.setattr("requests.Session.request", refuse)


def _cli_error(capsys, *argv: str) -> str:
    assert main(list(argv)) == 2
    return capsys.readouterr().err


def test_layer_without_geometry_is_an_error_in_cli_and_api(tmp_path, capsys):
    # UX-01: --layer names a layer of the --geometry file; without it the
    # value was dropped silently
    text = "--layer applies only to --geometry"
    polish = "--layer dotyczy tylko --geometry"  # the terminal speaks Polish
    err = _cli_error(
        capsys,
        "boundaries", "download", "--product", "admin", "--teryt", "14",
        "--layer", "x", "--root", str(tmp_path),
    )  # fmt: skip
    assert polish in err
    with pytest.raises(ValidationError, match=text):
        validate_collection_request(
            product="admin", root=tmp_path, teryt="14", layer="x"
        )
    with pytest.raises(ValidationError, match=f"{text}.*are selected with --layers"):
        LandCoverManager("bdot10k", root=tmp_path).validate_request(
            teryt="1465", layer="PTWP"
        )
    with pytest.raises(ValidationError, match=text):
        validate_data_request(
            product="nmt", root=tmp_path, sheet=SHEET, layer="x",
            resolution="1m", vertical_crs="EVRF2007",
        )  # fmt: skip


@pytest.mark.parametrize(
    ("flags", "text"),
    [
        (["--resolution", "1m"], "--resolution nie dotyczy LAZ"),
        (["--sheet-system", "2000"], "--sheet-system nie dotyczy LAZ PL"),
        (
            ["--sheet-system", "2000", "--scale", "1:500"],
            "--sheet-system i --scale nie dotycza LAZ PL",
        ),
    ],
)
def test_pl_laz_rejects_grid_and_sheet_flags(tmp_path, capsys, flags, text):
    # UX-02: LAZ CZ rejected them, LAZ PL dropped them silently
    err = _cli_error(
        capsys,
        "elevation", "download", "--product", "laz", "--sheet", SHEET,
        "--vertical-crs", "EVRF2007", "--root", str(tmp_path), *flags,
    )  # fmt: skip
    assert text in err


def test_registry_keys_are_named_as_flags(tmp_path):
    # UX-03: messages named --sheet_system (a registry key, not a flag)
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="topographic", root=tmp_path, country="pl",
            bbox=BBox(565000, 242000, 566000, 243000, "EPSG:2180"),
            scale="1:10000", format="TIFF", sheet_system="1992",
        )  # fmt: skip
    assert "--sheet-system" in str(error.value)
    assert "--sheet_system" not in str(error.value)


def test_missing_selection_names_only_the_selections_of_the_product(tmp_path):
    # UX-04: the text listed --teryt, --ku and --sheet for HY-NET (CZ)
    with pytest.raises(ValidationError) as error:
        validate_collection_request(product="network", root=tmp_path, country="cz")
    assert str(error.value) == (
        "Give exactly one choice for --product network (CZ): --bbox/--geometry (area "
        "features), --whole-country (country file)"
    )


def test_survey_control_hint_names_the_network_of_each_selection(tmp_path):
    # UX-14: the hint listed --bbox/--sheet/--geometry twice, without --network
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="control", root=tmp_path, country="pl",
            whole_country=True, network="horizontal",
        )  # fmt: skip
    text = str(error.value)
    assert "with --network horizontal|vertical (county package)" in text
    assert (
        "with --network archive-1942|archive-kronsztadt60 (sheets of the area)"
    ) in text


def test_cz_source_with_a_pl_sheet_code_names_the_source(tmp_path):
    # UX-05: the error pointed to --country cz, a flag landcover does not have
    with pytest.raises(ValidationError) as error:
        LandCoverManager("zabaged", root=tmp_path).validate_request(sheet="N-34-130-D")
    assert str(error.value) == (
        "--product zabaged (CZ): sheet code N-34-130-D does not define a CZ area - "
        "give --bbox (e.g. in EPSG:5514) or --geometry"
    )


def test_area_outside_the_explicit_country_fails_before_network(tmp_path):
    # UX-06: S-JTSK numbers read as EPSG:2180 failed as "no objects" after the
    # network; swapped EPSG:4326 axes as "no sheets"
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="network", root=tmp_path, country="cz",
            bbox=BBox(-600000, -1100000, -590000, -1090000, "EPSG:2180"),
        )  # fmt: skip
    assert str(error.value).startswith("--bbox (EPSG:2180) lies outside CZ")
    assert "--bbox-crs EPSG:5514" in str(error.value)
    with pytest.raises(ValidationError) as error:
        validate_data_request(
            product="nmt", root=tmp_path, country="pl", sheet_system="1992",
            resolution="1m", vertical_crs="EVRF2007",
            bbox=BBox(50.05, 19.93, 50.06, 19.94, "EPSG:4326"),
        )  # fmt: skip
    assert str(error.value).endswith(
        "the axes look swapped: --bbox 19.93,50.05,19.94,50.06"
    )


def test_unknown_flag_is_reported_by_the_command_with_its_owners(capsys):
    # UX-07: argparse of the root named neither the command nor a hint
    with pytest.raises(SystemExit) as exit_:
        main(["elevation", "download", "--product", "nmt", "--teryt", "1465"])
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("usage: kartograf elevation download")
    assert (
        "kartograf elevation download: error: nieznana opcja --teryt (maja ja: "
        "boundaries, cadastre, geodesy, landcover, models3d download). Opcje: "
        "kartograf elevation download --help"
    ) in err
    # UX-08: landcover chose its data with --source until 0.8.0
    for flag in ("--source", "-s"):
        with pytest.raises(SystemExit):
            main(["landcover", "download", flag, "bdot10k"])
        assert (
            f"nieznana opcja {flag} (od 0.8.0 produkt wybiera --product, np. "
            "--product bdot10k; lista: kartograf landcover list-sources)"
        ) in capsys.readouterr().err


def test_flag_prefixes_are_not_abbreviations(capsys):
    # UX-09: --stat of soil hsg was read as its --stats (now --summary)
    with pytest.raises(SystemExit):
        main(["soil", "hsg", "--depth", "0-5cm", "--stat", "mean", "--sheet", "X"])
    assert "nieznana opcja --stat (maja ja: soil download)" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["soil", "hsg", "--depth", "0-5cm", "--stats", "--sheet", "X"])
    assert (
        "nieznana opcja --stats (od 0.8.0 statystyki HSG wypisuje --summary)"
        in capsys.readouterr().err
    )


def test_negative_bbox_after_a_space_is_the_bbox_value(tmp_path, capsys):
    # UX-10: "--bbox -600000,..." ended with "expected one argument"
    err = _cli_error(
        capsys,
        "hydro", "download", "--product", "network", "--country", "cz",
        "--bbox", "-600000,-1100000,-590000,-1090000", "--root", str(tmp_path),
    )  # fmt: skip
    assert "lezy poza CZ" in err  # parsed as a bbox, checked by the library


def test_bdot10k_voivodeship_teryt_names_the_powiat_choice(tmp_path):
    # UX-12: "Nieprawidlowy kod TERYT: 14" without a hint
    with pytest.raises(ValidationError) as error:
        LandCoverManager("bdot10k", root=tmp_path).validate_request(teryt="14")
    assert str(error.value).startswith(
        "--teryt 14: BDOT10k is published per county - give --teryt <4 digits>"
    )


# Cieszyn: an area crossing the PL-CZ border
BORDER = BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326")


def test_enumerated_values_are_taken_in_any_case(tmp_path, capsys):
    # UX-11: --country PL, --vertical-crs evrf2007, --format shp and
    # epsg:2180 were errors; each flag had its own spelling
    def addresses(**case):
        return validate_collection_request(
            product="addresses", root=tmp_path, whole_country=True, **case
        )

    canonical = addresses(country="pl", format="SHP")
    assert addresses(country="PL", format="shp") == canonical
    gminy = BBox(565000, 242000, 566000, 243000, "EPSG:2180")
    assert validate_collection_request(
        product="admin", root=tmp_path, country="Pl", level="gmina",
        bbox=gminy._replace(crs="epsg:2180"),
    ) == validate_collection_request(
        product="admin", root=tmp_path, country="pl", level="gmina", bbox=gminy
    )  # fmt: skip

    from tests.integration.test_download_data import G, _pl_sheets
    from tests.integration.test_manager_campaigns import C14, FakeCampaignProvider

    def nmt_sheet(out, **case):
        with _pl_sheets(FakeCampaignProvider(C14)):
            report = download_data(
                product="nmt", root=out, sheet=G, resolution="1m", cache=False,
                **case,
            )  # fmt: skip
        file = report.files[0].file
        sidecar = file.version_path.with_name(f"{file.version_path.name}.meta.json")
        return file.path.relative_to(out), json.loads(sidecar.read_text())["request"]

    assert nmt_sheet(
        tmp_path / "a", vertical_crs="evrf2007", country="PL"
    ) == nmt_sheet(tmp_path / "b", vertical_crs="EVRF2007")

    out = tmp_path / "store"
    assert main([
        "landcover", "download", "--product", "bdot10k", "--teryt", "1465",
        "--format", "shp", "--root", str(out), "--check",
    ]) == 0  # fmt: skip
    assert capsys.readouterr().out == (
        "landcover/pl_bdot10k_shp/teryt/1465.zip: do pobrania\n"
    )


def test_pl_sheet_code_with_another_sheet_system_fails_before_network(tmp_path, capsys):
    # the sheet system of a PL sheet code comes from the code; another
    # --sheet-system was dropped silently
    text = (
        f"--sheet-system 2000 nie zgadza sie z godlem {SHEET} (PL-1992): uklad "
        "arkuszy wynika z godla - pomin --sheet-system"
    )
    err = _cli_error(
        capsys,
        "elevation", "download", "--product", "nmt", "--sheet", SHEET,
        "--sheet-system", "2000", "--resolution", "1m", "--vertical-crs",
        "EVRF2007", "--root", str(tmp_path),
    )  # fmt: skip
    assert f"Error: {text}" in err
    with pytest.raises(
        ValidationError, match=("does not match sheet code 6.129.30.25.3")
    ):
        validate_data_request(
            product="orto", root=tmp_path, sheet="6.129.30.25.3",
            sheet_system="1992",
        )  # fmt: skip
    # the system of the code itself stays a valid (redundant) choice
    assert (
        validate_data_request(
            product="nmt",
            root=tmp_path,
            sheet=SHEET,
            sheet_system="1992",
            resolution="1m",
            vertical_crs="EVRF2007",
        )  # fmt: skip
        is None
    )


def test_option_of_the_other_country_source(tmp_path):
    # UX-15: --sheet-system selects the ZTM sheets (CZ); for the BDOT10k maps
    # (PL) it was "nie dotyczy", and an auto area could never take it
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="topographic", root=tmp_path, country="pl",
            bbox=BBox(565000, 242000, 566000, 243000, "EPSG:2180"),
            scale="1:10000", format="TIFF", sheet_system="1992",
        )  # fmt: skip
    assert str(error.value) == (
        "--sheet-system applies only to --product topographic (CZ: sjtsk, etrs89) - "
        "for PL omit --sheet-system"
    )
    request = validate_collection_request(
        product="topographic", root=tmp_path, country="auto", bbox=BORDER,
        scale="1:10000", format="TIFF", sheet_system="sjtsk",
    )  # fmt: skip
    choices = {part.country: part.choice for part in request.parts}
    assert choices["CZ"]["sheet_system"] == "sjtsk"
    assert "sheet_system" not in choices["PL"]


def test_survey_network_per_country(tmp_path):
    # UX-48: --level, --resolution and --vertical-crs took pl=...,cz=...;
    # --network had one value for both countries (different networks)
    request = validate_collection_request(
        product="control", root=tmp_path, country="auto", bbox=BORDER,
        network={"pl": "horizontal", "cz": "gnss"},
    )  # fmt: skip
    assert {part.country: part.choice["network"] for part in request.parts} == {
        "PL": "horizontal",
        "CZ": "gnss",
    }
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="control", root=tmp_path, country="auto", bbox=BORDER,
            network="gnss",
        )  # fmt: skip
    assert "common: horizontal, vertical, gravity)" in str(error.value)


@pytest.mark.parametrize("teryt", ["99", "9999", "33"])
def test_teryt_of_a_missing_voivodeship_says_so_and_lists_the_existing_ones(
    tmp_path, teryt
):
    # E2E 0.8.0 D P3-6: a well-formed code of no voivodeship read as a format error
    with pytest.raises(ValidationError) as error:
        validate_collection_request(product="admin", root=tmp_path, teryt=teryt)
    text = str(error.value)
    assert f"no voivodeship with code {teryt[:2]}" in text
    assert "12 (malopolskie)" in text and "Invalid" not in text
    assert error.value.option == "teryt"


def test_teryt_of_a_wrong_format_is_still_a_format_error(tmp_path):
    with pytest.raises(ValidationError, match="2 digits, e.g. 12") as error:
        validate_collection_request(product="admin", root=tmp_path, teryt="126")
    assert error.value.option == "teryt"


def test_whole_country_names_only_the_countries_of_the_product(tmp_path):
    # E2E 0.8.0 D P3-4: hydro (CZ only) asked for --country pl, which it rejects
    with pytest.raises(ValidationError) as hydro:
        validate_collection_request(
            product="network", root=tmp_path, whole_country=True
        )
    assert "--country cz" in str(hydro.value)
    assert "--country pl" not in str(hydro.value)
    assert hydro.value.allowed == ("cz",)
    with pytest.raises(ValidationError) as admin:
        validate_collection_request(
            product="admin", root=tmp_path, whole_country=True, country="auto"
        )
    assert "--country pl or --country cz" in str(admin.value)
    assert admin.value.allowed == ("pl", "cz")
