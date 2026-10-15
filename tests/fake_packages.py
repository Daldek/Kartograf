"""Offline stand-ins for GUGiK unit packages (``tests/fixtures/pl/unit_package``).

``packages.json`` holds real URLs, response headers and ZIP member names; the
ZIP bodies are built here from those names (tiny artificial member content),
so the engines and the collection orchestrator see real package shapes
without the real bytes.
"""

import io
import json
import zipfile
from pathlib import Path

import requests

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "unit_package"
PACKAGES: dict = json.loads((FIXTURES / "packages.json").read_text(encoding="utf-8"))

Route = tuple[int, dict, bytes]


def zip_bytes(members: list[str], *, content: bytes = b"kartograf") -> bytes:
    """A ZIP with ``members`` (names ending in ``/`` are directories).

    Fixed member timestamps: the same members and content give the same
    bytes (identical yearly releases of a package).
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in members:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 15, 12, 0, 0))
            if name.endswith("/"):
                archive.writestr(info, b"")
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content + name.encode())
    return buffer.getvalue()


class FakeResponse:
    """A streamed ``requests.Response`` stand-in."""

    def __init__(self, status: int, headers: dict, body: bytes) -> None:
        self.status_code = status
        self.headers = dict(headers)
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)  # type: ignore[arg-type]

    def iter_content(self, chunk_size: int = 1):
        size = max(int(chunk_size), 1)
        for start in range(0, len(self.content), size):
            yield self.content[start : start + size]


class FakePackageSession:
    """``requests.Session`` stand-in: URL -> (status, headers, body).

    ``heads`` overrides the ``HEAD`` headers of a URL (the recorded size of a
    national file whose GET body is a tiny ZIP). ``calls`` records
    ``("GET"|"HEAD", url)`` in order; an unknown URL fails the test.
    """

    def __init__(
        self, routes: dict[str, Route], heads: dict[str, dict] | None = None
    ) -> None:
        self.routes = dict(routes)
        self.heads = dict(heads or {})
        self.calls: list[tuple[str, str]] = []

    def _route(self, method: str, url: str) -> Route:
        self.calls.append((method, url))
        if url not in self.routes:
            raise AssertionError(f"Nieoczekiwany URL w tescie: {url}")
        return self.routes[url]

    def get(self, url: str, **_kwargs) -> FakeResponse:
        return FakeResponse(*self._route("GET", url))

    def head(self, url: str, **_kwargs) -> FakeResponse:
        status, headers, _ = self._route("HEAD", url)
        return FakeResponse(status, self.heads.get(url, headers), b"")

    def gets(self, url: str | None = None) -> int:
        """Number of GET requests (of ``url``, or all)."""
        return sum(1 for m, u in self.calls if m == "GET" and (url is None or u == url))


def package_route(
    name: str,
    *,
    members: list[str] | None = None,
    content: bytes = b"kartograf",
    length: int | None = None,
) -> tuple[str, Route]:
    """Route of a fixture package: its URL and a response with a built ZIP.

    ``Content-Length`` = the body length (``length`` overrides it: a
    truncated transfer). A recorded error response (``status``) is replayed.
    """
    entry = PACKAGES[name]
    headers = dict(entry["headers"])
    if "status" in entry:
        return entry["url"], (entry["status"], headers, entry["body"].encode())
    body = zip_bytes(
        members if members is not None else entry["members"], content=content
    )
    headers["Content-Length"] = str(length if length is not None else len(body))
    return entry["url"], (200, headers, body)


def recorded_head(name: str) -> tuple[str, dict]:
    """``HEAD`` headers recorded for a fixture package (real size)."""
    entry = PACKAGES[name]
    return entry["url"], dict(entry["headers"])
