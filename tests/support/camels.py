"""Offline Zenodo and registry entry for the CAMELS-PL tests (ADR-062).

``ZenodoServer`` answers the requests of a ``requests`` session from memory as Zenodo
answered them on 2026-11-23 (``tests/fixtures/pl/camels``, its README): a ``Range`` of
one span with 206 and its ``Content-Range``, and fixed answers such as the recorded
``302`` of the concept DOI to the newest record. It records every request and counts
the bytes read from every body. ``zenodo`` serves the fixture ZIP of every supported
release and the recorded concept answers; ``use_params`` puts the registry entry of
CAMELS-PL with the releases of ``fixture_params`` (re-pinned to the bytes of the
fixture archives of ``kartograf.testing``) in place for one test.
"""

import io
import json
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from kartograf.download.releases import release_params
from kartograf.sources import registry
from kartograf.sources.descriptor import ReleaseFilesParams
from kartograf.testing import (
    CAMELS_DATASET,
    _camels_archive_bytes,
    _camels_release,
    _ServedFiles,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl" / "camels"
ANSWERS: dict[str, Any] = json.loads(
    (FIXTURES / "answers.json").read_text(encoding="utf-8")
)
CONCEPT_URL: str = ANSWERS["concept"]["url"]
RECORD_URL: str = ANSWERS["record"]["url"]
# The headers of the recorded range answer that describe the file, not the range.
ZIP_HEADERS: dict[str, str] = {
    name: ANSWERS["range"]["headers"][name]
    for name in ("content-type", "accept-ranges")
}
_LOCAL_HEADER = struct.Struct("<4s5H3I2H")

Answer = tuple[int, Mapping[str, str], bytes]


@dataclass(frozen=True)
class Asked:
    """One request the server got: its method, URL and ``Range`` header."""

    method: str
    url: str
    range: str | None


class Body(io.BytesIO):
    """The body of an answer: counts the bytes read from it."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.taken = 0

    def read(self, size: int | None = -1, /) -> bytes:
        chunk = super().read(size)
        self.taken += len(chunk)
        return chunk


class ZenodoServer(_ServedFiles):
    """Answer the requests of a session from memory and record them.

    ``files`` and ``ranges`` as ``kartograf.testing._served`` (without ``ranges`` a
    ``Range`` is ignored: 200 and the whole file). ``answers`` maps a URL to a fixed
    answer ``(status, headers, body)``: a redirect (the session follows its
    ``location``) or an error. ``short`` cuts the next ``short`` answers of a range
    by their last byte. ``asked``: every request in order, ``headers`` its headers;
    ``bodies``: the body of every answer in order.
    """

    def __init__(
        self,
        files: Mapping[str, tuple[bytes, Mapping[str, str]]],
        *,
        ranges: bool = True,
        answers: Mapping[str, Answer] | None = None,
        short: int = 0,
    ) -> None:
        super().__init__(files, ranges=ranges)
        self.answers = dict(answers or {})
        self.short = short
        self.asked: list[Asked] = []
        self.headers: list[CaseInsensitiveDict[str]] = []
        self.bodies: list[Body] = []

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: Any = True,
        cert: Any = None,
        proxies: Any = None,
    ) -> requests.Response:
        """Return the answer to ``request`` and record both."""
        url = request.url or ""
        headers = CaseInsensitiveDict(
            {
                name: value.decode("latin-1") if isinstance(value, bytes) else value
                for name, value in request.headers.items()
            }
        )
        self.asked.append(Asked(request.method or "", url, headers.get("Range")))
        self.headers.append(headers)
        fixed = self.answers.get(url)
        if fixed is not None:
            response = answer(request, *fixed)
        else:
            response = super().send(
                request,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies=proxies,
            )
        data = response.raw.read()
        if self.short and response.status_code == 206:
            self.short -= 1
            data = data[:-1]
        body = Body(data)
        response.raw = body
        self.bodies.append(body)
        return response

    def session(self) -> requests.Session:
        """Return a new session that only this server answers."""
        session = requests.Session()
        session.mount("https://", self)
        session.mount("http://", self)
        return session


def answer(
    request: requests.PreparedRequest,
    status: int,
    headers: Mapping[str, str],
    body: bytes,
) -> requests.Response:
    """Return the fixed answer ``status``, ``headers``, ``body`` to ``request``."""
    response = requests.Response()
    response.request = request
    response.url = request.url or ""
    response.status_code = status
    response.reason = HTTPStatus(status).phrase
    response.headers = CaseInsensitiveDict(dict(headers))
    response.raw = io.BytesIO(body)
    return response


def recorded_record() -> dict[str, Any]:
    """Return the recorded JSON of the newest record (2.1.0), a copy to edit."""
    data: dict[str, Any] = json.loads(
        (FIXTURES / ANSWERS["record"]["body"]).read_text(encoding="utf-8")
    )
    return data


def concept_answers(record: Mapping[str, Any] | None = None) -> dict[str, Answer]:
    """Return the recorded answers of the concept DOI: its 302, then the record.

    ``record`` replaces the recorded JSON of the newest record; the 302 then points to
    the record of its ``id`` (an id of eight digits keeps the recorded length).
    """
    concept = ANSWERS["concept"]
    redirect = (FIXTURES / concept["body"]).read_bytes()
    if record is None:
        return {
            CONCEPT_URL: (concept["status"], concept["headers"], redirect),
            RECORD_URL: (
                ANSWERS["record"]["status"],
                {},
                (FIXTURES / ANSWERS["record"]["body"]).read_bytes(),
            ),
        }
    recorded = str(recorded_record()["id"])
    newest = str(record["id"])
    location = concept["headers"]["location"].replace(recorded, newest)
    return {
        CONCEPT_URL: (
            concept["status"],
            {**concept["headers"], "location": location},
            redirect.replace(recorded.encode(), newest.encode()),
        ),
        RECORD_URL.replace(recorded, newest): (
            ANSWERS["record"]["status"],
            {},
            json.dumps(record).encode("utf-8"),
        ),
    }


def zenodo(
    params: ReleaseFilesParams,
    *,
    ranges: bool = True,
    concept: Mapping[str, Answer] | None = None,
    short: int = 0,
) -> ZenodoServer:
    """Return Zenodo with the fixture ZIP of every supported release of ``params``.

    ``concept``: the answers of the concept DOI (the recorded ones without it, see
    ``concept_answers``; ``{}`` answers it 404).
    """
    files = {
        release.url: (_camels_archive_bytes(release.version), ZIP_HEADERS)
        for release in params.releases
        if release.refusal is None
    }
    return ZenodoServer(
        files,
        ranges=ranges,
        answers=concept_answers() if concept is None else concept,
        short=short,
    )


def fixture_params() -> ReleaseFilesParams:
    """Return the releases of CAMELS-PL, the supported ones re-pinned to the fixtures.

    The length of the fixture ZIP and the size, CRC and SHA-256 of the fixture
    GeoPackages (``kartograf.testing._camels_release``); the rest as registered.
    """
    params = release_params(registry.get_source(CAMELS_DATASET).channels[0])
    return replace(params, releases=tuple(_camels_release(r) for r in params.releases))


def use_params(monkeypatch: pytest.MonkeyPatch, params: ReleaseFilesParams) -> None:
    """Put the registry entry of CAMELS-PL with ``params`` in place for one test."""
    descriptor = registry.get_source(CAMELS_DATASET)
    (channel,) = descriptor.channels
    monkeypatch.setitem(
        registry._SOURCES,
        CAMELS_DATASET,
        replace(descriptor, channels=(replace(channel, params=params),)),
    )


def member_ranges(archive: bytes, name: str) -> tuple[str, str]:
    """Return the ``Range`` of the local header and of the stored bytes of ``name``.

    Read from ``archive`` with ``zipfile`` and its local header: what a range reader
    of the member asks.
    """
    info = zipfile.ZipFile(io.BytesIO(archive)).getinfo(name)
    offset = info.header_offset
    *_, name_length, extra_length = _LOCAL_HEADER.unpack_from(archive, offset)
    start = offset + _LOCAL_HEADER.size + name_length + extra_length
    return (
        f"bytes={offset}-{offset + _LOCAL_HEADER.size - 1}",
        f"bytes={start}-{start + info.compress_size - 1}",
    )
