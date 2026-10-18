"""Value kinds and the canonical command line of the command catalog
(spec 8.3, 8.7)."""

import pytest

from kartograf.catalog import kinds
from kartograf.cli import _args
from kartograf.exceptions import ValidationError


def _outcome(function, *args):
    """The result of a parser helper, or the type and text of its error."""
    try:
        return function(*args)
    except ValidationError as error:
        return type(error), str(error)


@pytest.mark.parametrize(
    "args",
    [
        ("530000,382000,533000,386000", "EPSG:2180"),
        (" 19.93 , 50.055,19.945,50.065", "EPSG:4326"),
        ("-447000,-1114000,-446000,-1113000", "EPSG:5514"),
        ("1,2,3", "EPSG:2180"),
        ("1,2,x,4", "EPSG:2180"),
        ("5,2,3,4", "EPSG:2180"),
        ("1,2,3,4", "EPSG:9999"),
        ("nan,2,3,4", "EPSG:2180"),
    ],
)
def test_kinds_parse_bbox_like_the_cli_helper(args):
    assert _outcome(kinds.parse_bbox_arg, *args) == _outcome(
        _args.parse_bbox_arg, *args
    )


@pytest.mark.parametrize(
    "args",
    [
        (None, "--resolution"),
        ("5m", "--resolution"),
        ("pl=1m,cz=2m", "--resolution"),
        (" PL = 1m , cz=2m ", "--vertical-crs"),
        ("pl=1m,pl=2m", "--resolution"),
        ("pl=1m,xx=2m", "--resolution"),
        ("pl=", "--resolution"),
        ("pl=1m,cz", "--resolution"),
    ],
)
def test_kinds_parse_per_country_like_the_cli_helper(args):
    assert _outcome(kinds.parse_per_country, *args) == _outcome(
        _args.parse_per_country, *args
    )


@pytest.mark.parametrize("text", ["SWRS", "SWRS,PTWP", " n , e ", ""])
def test_kinds_split_layer_codes_like_the_cli_helper(text):
    assert kinds.layer_codes(text) == _args.layer_codes(text)
