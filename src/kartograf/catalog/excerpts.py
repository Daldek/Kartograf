"""
Excerpts of the result documents for the examples of the catalog (AGI-2.2).

Every example of a command has a ``result``: an excerpt of the document the call
returns. The excerpt is the same shape for every call of a schema, so it is kept
here by the schema id of the document; an example whose result differs gives its own
(``Example.result``). An excerpt holds the keys that show the shape of the document
(a contract test checks them against the keys of the real document) and few values,
shortened where they are long.
"""

from collections.abc import Mapping
from typing import Final

_STORE = "/data"
_PATH = f"{_STORE}/nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc"
_SHA = "10be475e6b5c43d5..."
_SIDECAR: Mapping[str, object] = {
    "schema": "kartograf-meta/1",
    "dataset": "pl.gugik.nmt_1m",
    "country": "PL",
    "product": "nmt",
    "resolution": "1m",
    "sha256": _SHA,
}

EXCERPTS: Final[Mapping[str, Mapping[str, object]]] = {
    "kartograf-download/1": {
        "schema": "kartograf-download/1",
        "files": [
            {
                "unit": "N-34-130-D-d-2-4",
                "country": "PL",
                "file": {
                    "path": _PATH,
                    "status": "new",
                    "label": "2022-05-10_83233",
                    "sha256": _SHA,
                },
            }
        ],
        "failed": [],
        "ok": True,
    },
    "kartograf-plan/1": {
        "schema": "kartograf-plan/1",
        "store": _STORE,
        "items": [
            {
                "unit": "N-34-130-D-d-2-4",
                "local_label": "2022-05-10_83233",
                "available_label": "2025-04-02_99887",
                "status": "newer",
            }
        ],
        "ok": True,
    },
    "kartograf-availability/1": {
        "schema": "kartograf-availability/1",
        "request": {"product": "nmt", "country": "pl", "sheet": "N-34-130-D-d-2-4"},
        "combinations": [
            {
                "country": "PL",
                "year": 2022,
                "resolution": "1m",
                "vertical_crs": "EVRF2007",
                "format": "ASC",
                "complete": True,
            }
        ],
        "ok": True,
    },
    "kartograf-sheet/1": {
        "schema": "kartograf-sheet/1",
        "sheet": "N-34-130-D-d-2-4",
        "system": "pl1992",
        "country": "PL",
        "scale": "1:10000",
        "crs": "EPSG:2180",
        "commands": ["elevation download", "elevation availability"],
    },
    "kartograf-sheets/1": {
        "schema": "kartograf-sheets/1",
        "request": {"scale": "1:10000", "sheet_system": "1992"},
        "sheets": ["M-34-64-D-d-1-4", "M-34-64-D-d-3-2"],
        "count": 2,
    },
    "kartograf-sources/1": {
        "schema": "kartograf-sources/1",
        "group": "elevation",
        "products": ["nmt", "nmpt", "laz", "contours"],
        "sources": [
            {
                "key": "pl.gugik.nmt_1m",
                "country": "PL",
                "provider": "GUGiK",
                "product": "nmt",
                "directory": "nmt/<uklad>_1m_<uklad-wys>",
            }
        ],
    },
    "kartograf-layers/1": {
        "schema": "kartograf-layers/1",
        "group": "landcover",
        "product": "corine",
        "years": [{"year": 2018, "data": "clms"}],
    },
    "kartograf-project-state/1": {
        "schema": "kartograf-project-state/1",
        "directory": "/work/project",
        "output_dir": _STORE,
        "tasks": [
            {
                "name": "teren",
                "command": "elevation download",
                "options": {"product": "nmt", "sheet": "N-34-130-D-d-2-4"},
            }
        ],
    },
    "kartograf-project-report/1": {
        "schema": "kartograf-project-report/1",
        "project": {"directory": "/work/project", "output_dir": _STORE},
        "tasks": [{"name": "teren", "ok": True}],
        "ok": True,
    },
    "kartograf-project-check/1": {
        "schema": "kartograf-project-check/1",
        "project": {"directory": "/work/project", "output_dir": _STORE},
        "files": [{"path": _PATH, "status": "ok"}],
        "not_downloaded": [],
        "ok": True,
    },
    "kartograf-cache/1": {
        "schema": "kartograf-cache/1",
        "action": "stats",
        "path": "/home/user/.cache/nogat/kartograf/metadata.db",
        "exists": True,
        "size_bytes": 4096,
        "entries": {"records": 1, "campaigns": 2, "teryt": 3, "sheets": 4},
    },
    "kartograf-config/1": {
        "schema": "kartograf-config/1",
        "tool": "kartograf",
        "version": "0.8.0",
        "keys": {"lang": {"value": "pl", "source": "default"}},
        "credentials": {"CLMS_CREDENTIALS": "missing"},
    },
    "kartograf-store-overview/1": {
        "schema": "kartograf-store-overview/1",
        "output_dir": _STORE,
        "segments": [
            {
                "segment": "nmt/pl_1992_1m_evrf2007",
                "product": "nmt",
                "country": "PL",
                "dataset_key": "pl.gugik.nmt_1m",
                "known": True,
            }
        ],
    },
    "kartograf-store-entries/1": {
        "schema": "kartograf-store-entries/1",
        "output_dir": _STORE,
        "segment": "nmt/pl_1992_1m_evrf2007",
        "limit": 20,
        "truncated": False,
        "entries": [{"kind": "link", "name": "N-34-130-D-d-2-4.asc", "path": _PATH}],
    },
    "kartograf-store-sidecar/1": {
        "schema": "kartograf-store-sidecar/1",
        "path": _PATH,
        "sidecar": _SIDECAR,
    },
    "kartograf-catalog/1": {
        "schema": "kartograf-catalog/1",
        "view": "overview",
        "commands": [{"id": "elevation download", "summary": "Download NMT"}],
    },
}
