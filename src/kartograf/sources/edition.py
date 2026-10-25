"""
Source edition — the ``metadata`` freshness signal (versioned store D29, D30).

An edition is the release of a dataset announced by the source's own metadata
(SoilGrids: the WCS GetCapabilities title, CORINE: the CLMS catalogue record).
Its id is the version label of every file downloaded from that release, so
two versions are comparable without downloading the data.
"""

import re
from dataclasses import dataclass
from typing import Any

from kartograf.exceptions import DownloadError
from kartograf.messages import message

_LABEL_RE = re.compile(r"[A-Za-z0-9._+-]+")


@dataclass(frozen=True)
class Edition:
    """Edition of a source read from its metadata.

    ``id`` is the version label (D29), ``url`` the metadata request,
    ``title`` the raw SoilGrids ``ows:Title``, ``dataset_uid`` the CLMS
    dataset UID of CORINE. ``source_property`` names the SoilGrids property
    whose map announced the edition when it is not the property of the file
    (``ocd``: its own map names no edition, so ``url`` and ``title`` are the
    ``clay`` map's); ``None`` = the file's own map.
    """

    id: str
    url: str
    title: str | None = None
    dataset_uid: str | None = None
    source_property: str | None = None

    def to_extra(self) -> dict[str, Any]:
        """``extra.edition`` of the version sidecar (``None`` fields skipped)."""
        fields = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "dataset_uid": self.dataset_uid,
            "source_property": self.source_property,
        }
        return {k: v for k, v in fields.items() if v is not None}


def edition_label(raw: str, *, what: str) -> str:
    """``raw`` as a version label; ``DownloadError`` when not ``[A-Za-z0-9._+-]+``.

    ``what`` names the source in the error message.
    """
    if not _LABEL_RE.fullmatch(raw):
        raise DownloadError(
            message("sources.edition_invalid_label", what=what, raw=raw)
        )
    return raw
