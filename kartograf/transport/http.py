"""
Shared HTTP transport of all providers (review 2026-10-06 D1/D2).

The one place of the download policy: writing to a temporary file
``<file>.<pid>_<tid>.tmp`` + ``os.replace`` (atomically), up to ``MAX_RETRIES``
attempts with exponential backoff (``backoff_delay``: 2 s, 4 s), only
network errors, 429 and 5xx are retried (``is_retryable``), ``Retry-After`` extends
the pause (``retry_wait``), ``DownloadError.status_code`` carries the HTTP code
of the last attempt (``http_failure``). Files are downloaded by ``download_to``,
in-memory responses by ``get_with_retry``; per-thread sessions by ``SessionPerThread``.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError

logger = logging.getLogger(__name__)

# Number of attempts (first + retries) - one for the whole package.
MAX_RETRIES = 3
# Backoff before retry n (n = 1, 2, ...): RETRY_BACKOFF_BASE ** n,
# i.e. 2 s and 4 s. One value for files and queries (D1, 2026-10-07):
# previously providers waited 2 s/4 s, and the shared transport 1 s/2 s.
RETRY_BACKOFF_BASE = 2
# Upper bound of the wait from the Retry-After header (s): we would not outlast a longer
# server outage within three attempts anyway, and the CLI must not "hang".
MAX_RETRY_AFTER = 60


def backoff_delay(attempt: int) -> float:
    """Pause after failed attempt ``attempt`` (from 0): 2 s, 4 s, ..."""
    return RETRY_BACKOFF_BASE ** (attempt + 1)


def http_status(exc: requests.RequestException) -> int | None:
    response = getattr(exc, "response", None)
    return response.status_code if response is not None else None


def is_retryable(exc: requests.RequestException) -> bool:
    """Retry network errors, 429 and 5xx; other 4xx would just repeat."""
    status = http_status(exc) if isinstance(exc, requests.HTTPError) else None
    if status is None:
        return True
    return status == 429 or status >= 500


def retry_wait(exc: requests.RequestException, backoff: float) -> float:
    """Time before the next attempt: Retry-After (<= MAX_RETRY_AFTER) or backoff."""
    response = getattr(exc, "response", None)
    value = response.headers.get("Retry-After") if response is not None else None
    if not value:
        return backoff
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return backoff
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    if seconds < 0:
        return backoff
    return max(backoff, min(seconds, MAX_RETRY_AFTER))


def http_failure(
    message: str, exc: requests.RequestException | None, **kwargs
) -> DownloadError:
    """DownloadError with the HTTP code of the last attempt (if any)."""
    status = http_status(exc) if exc is not None else None
    return DownloadError(message, status_code=status, **kwargs)


def make_gugik_session() -> requests.Session:
    """Create a GUGiK keep-alive session; the application handles retries."""
    from kartograf import __version__

    session = requests.Session()
    session.headers["User-Agent"] = f"kartograf/{__version__}"
    for scheme in ("http://", "https://"):
        session.mount(
            scheme, requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8)
        )
    return session


class SessionPerThread:
    """One session per thread, or a session entrusted by the caller.

    ``requests.Session`` has no thread-safety guarantee, so a
    provider shared by a thread pool keeps a separate session for each
    thread. An injected session (``injected``) always wins - its use
    from many threads is the caller's concern. ``factory`` (default
    ``make_gugik_session``) is resolved on the first ``get()``
    in a given thread.
    """

    def __init__(
        self,
        injected: requests.Session | None = None,
        factory: Callable[[], requests.Session] | None = None,
    ) -> None:
        self.injected = injected
        self._factory = factory
        self._local = threading.local()

    def get(self) -> requests.Session:
        if self.injected is not None:
            return self.injected
        session = getattr(self._local, "session", None)
        if session is None:
            factory = self._factory or make_gugik_session
            session = self._local.session = factory()
        return session


def reject_error_document(service: str) -> Callable[[requests.Response], None]:
    """``download_to`` validator: an XML/HTML error report instead of data.

    OGC services (WMS/WCS) can answer HTTP 200 with a
    ``ServiceException`` document - such a file must not land on disk as a raster.
    A content error is not retried (the same URL gives the same report).
    """

    def validate(response: requests.Response) -> None:
        content_type = response.headers.get("Content-Type", "").lower()
        if "xml" in content_type or "html" in content_type:
            raise DownloadError(
                f"{service} returned error response: {response.text[:500]}"
            )

    return validate


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    retries: int = MAX_RETRIES,
    description: str = "",
    params: dict[str, str] | None = None,
) -> requests.Response:
    """Fetch an HTTP response; every failed attempt keeps the same URL.

    ``params`` (optional) go to ``session.get`` unchanged - every
    attempt sends the same set of query parameters.
    """
    extra = {"params": params} if params is not None else {}
    context = description or url
    last_error: requests.RequestException | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout, **extra)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if not is_retryable(exc):
                raise http_failure(
                    f"{context}: HTTP {http_status(exc)} (bez ponowien): {exc}", exc
                ) from exc
            if attempt < retries - 1:
                delay = retry_wait(exc, backoff_delay(attempt))
                logger.warning(
                    "%s: proba %s/%s nieudana: %s; ponowienie za %ss",
                    context,
                    attempt + 1,
                    retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
    raise http_failure(
        f"{context}: pobranie nieudane po {retries} probach: {last_error}",
        last_error,
    ) from last_error


def _write_atomic(
    response: requests.Response, output_path: Path, chunk_size: int
) -> Path:
    """Write the response stream to output_path via a temporary file."""
    temp_path = output_path.with_name(
        f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )
    try:
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
        os.replace(temp_path, output_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return output_path


def download_to(
    session: requests.Session,
    url: str,
    output_path: Path,
    *,
    timeout: float,
    retries: int = MAX_RETRIES,
    description: str = "",
    validate: Callable[[requests.Response], None] | None = None,
    save: Callable[[requests.Response, Path], Path] | None = None,
    chunk_size: int = 1_048_576,
) -> Path:
    """Download a URL to a file (atomically, with a retry policy); return the path.

    Parameters
    ----------
    description : str, optional
        Description for messages and logs (default: the URL).
    validate : callable, optional
        Called with the response after ``raise_for_status``, before writing; an
        exception other than ``requests.RequestException`` ends the download without
        retries (e.g. ``reject_error_document``).
    save : callable, optional
        Write the response instead of the default atomic stream write;
        returns the path of the file actually written (e.g. an unpacked ZIP).
        An interrupted stream (``RequestException``) is retried.

    The target directory is created only after a successful response - an HTTP error
    leaves no empty directories.
    """
    output_path = Path(output_path)
    context = description or url

    last_error: requests.RequestException | None = None
    for attempt in range(retries):
        try:
            logger.debug("Pobieranie %s (proba %s/%s)", context, attempt + 1, retries)
            response = session.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            if validate is not None:
                validate(response)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if save is not None:
                saved = save(response, output_path)
            else:
                saved = _write_atomic(response, output_path, chunk_size)
            logger.info("Pobrano %s -> %s", context, saved)
            return saved
        except requests.RequestException as e:
            last_error = e
            if not is_retryable(e):
                raise http_failure(
                    f"Nie udalo sie pobrac {context}: "
                    f"HTTP {http_status(e)} (bez ponowien): {e}",
                    e,
                ) from e
            if attempt < retries - 1:
                wait = retry_wait(e, backoff_delay(attempt))
                logger.warning(
                    "Pobranie %s nieudane (proba %s/%s): %s; ponowienie za %ss",
                    context,
                    attempt + 1,
                    retries,
                    e,
                    wait,
                )
                time.sleep(wait)

    raise http_failure(
        f"Nie udalo sie pobrac {context} po {retries} probach: {last_error}",
        last_error,
    ) from last_error
