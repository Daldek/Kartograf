"""Record the structure of the IIaPGW geodatabase for the Kartograf fixtures (ADR-059).

``kartograf.testing`` builds a tiny archive with the published structure of the
geodatabase of PGW Wody Polskie (the spatial layers of the feature datasets
``PGW_WP``, ``JCWPd`` and ``SIG``, their identifier and geometry columns, fields and
CRS definition, and one attribute table) without the 142 MB of the real one. This
script reads that structure from the downloaded archive - no network - and writes
``src/kartograf/_data/pgw_geodatabase.json``:

1. the one ``*.gdb`` directory of the ZIP (or a ``*.gdb`` directory given itself),
   read through GDAL (``pyogrio``);
2. the feature dataset of every layer: the first part of the path of its item in the
   system table ``GDB_Items``, which GDAL lists with ``LIST_ALL_TABLES``;
3. for every spatial layer of the three datasets: its geometry type as GDAL reads
   it, identifier (FID) and geometry columns, feature count and fields with their
   ``numpy`` types; the one CRS definition they share; the same for the attribute
   table ``Charakterystyka_JCWP``.

The tests never run it.

Usage::

    kartograf hydro download --product pgw --country pl --whole-country -o DIR
    uv run scripts/build_pgw_geodatabase.py --source DIR/pl.zip
"""

import argparse
import json
import sys
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyogrio
import pyogrio.raw

from kartograf.sources.descriptor import UnitPackageParams
from kartograf.sources.registry import get_source

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src" / "kartograf" / "_data" / "pgw_geodatabase.json"
DATASETS = ("PGW_WP", "JCWPd", "SIG")
TABLE = "Charakterystyka_JCWP"
SCHEMA = "kartograf-pgw-geodatabase/1"


def geodatabase(source: Path) -> tuple[str, str]:
    """Return the GDAL path of the geodatabase and its directory name.

    Parameters
    ----------
    source : Path
        The archive (``.zip``) or the unpacked ``*.gdb`` directory.

    Returns
    -------
    tuple of str
        The path GDAL opens and the name of the ``*.gdb`` directory.
    """
    if source.is_dir():
        return str(source), source.name
    with zipfile.ZipFile(source) as archive:
        tops = {name.split("/", 1)[0] for name in archive.namelist()}
    found = sorted(top for top in tops if top.lower().endswith(".gdb"))
    if len(found) != 1:
        sys.exit(f"{source}: {len(found)} geodatabases in the archive, expected one")
    return f"/vsizip/{source}/{found[0]}", found[0]


def datasets(path: str) -> dict[str, str]:
    """Return the feature dataset of every item of the geodatabase (``GDB_Items``)."""
    _, _, _, (names, paths) = pyogrio.raw.read(
        path,
        layer="GDB_Items",
        columns=["Name", "Path"],
        read_geometry=False,
        LIST_ALL_TABLES="YES",
    )
    found: dict[str, str] = {}
    for name, item in zip(names, paths, strict=True):
        parts = str(item).strip("\\").split("\\")
        if len(parts) == 2:
            found[str(name)] = parts[0]
    return found


def describe(path: str, layer: str) -> dict[str, Any]:
    """Return the columns, fields and count of one layer or table."""
    info = pyogrio.read_info(path, layer=layer)
    return {
        "fid": info["fid_column"],
        "geometry_column": info["geometry_name"] or None,
        "count": int(info["features"]),
        "fields": {
            str(name): str(dtype)
            for name, dtype in zip(info["fields"], info["dtypes"], strict=True)
        },
        "crs": info["crs"],
    }


def main() -> None:
    """Read the structure of the archive given by ``--source`` and write the JSON."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    warnings.simplefilter("ignore")  # GDAL reports measured types and old .spx files
    path, name = geodatabase(args.source)
    owner = datasets(path)
    layers: list[dict[str, Any]] = []
    crs: set[str] = set()
    for layer, kind in pyogrio.list_layers(path):
        if kind is None or owner.get(str(layer)) not in DATASETS:
            continue
        found = describe(path, str(layer))
        crs.add(found.pop("crs"))
        layers.append(
            {
                "dataset": owner[str(layer)],
                "name": str(layer),
                "geometry": str(kind),
                "fid": found["fid"],
                "geometry_column": found["geometry_column"],
                "features": found["count"],
                "fields": found["fields"],
            }
        )
    if len(crs) != 1:
        sys.exit(f"{args.source}: {len(crs)} CRS definitions, expected one")
    layers.sort(key=lambda item: (DATASETS.index(item["dataset"]), item["name"]))
    table = describe(path, TABLE)
    source = get_source("pl.pgw.pgw")
    channel = next(c for c in source.channels if c.capabilities == {"country_files"})
    assert isinstance(channel.params, UnitPackageParams)
    (variant,) = channel.params.variants
    document = {
        "schema": SCHEMA,
        "source": {
            "url": variant.url_template,
            "edition": variant.edition,
            "file": args.source.name,
            "read": datetime.now(UTC).date().isoformat(),
            "reader": f"pyogrio {pyogrio.__version__}, GDAL "
            f"{pyogrio.__gdal_version_string__}",
        },
        "geodatabase": name,
        "crs": crs.pop(),
        "layers": layers,
        "table": {
            "name": TABLE,
            "fid": table["fid"],
            "rows": table["count"],
            "fields": table["fields"],
        },
    }
    text = json.dumps(document, ensure_ascii=False, indent=1) + "\n"
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    fields = sum(len(item["fields"]) for item in layers)
    print(f"{TARGET}: {len(layers)} layers, {fields} fields")


if __name__ == "__main__":
    main()
