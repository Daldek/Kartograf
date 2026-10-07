"""
Kanoniczny downloader HTTP dla NOWEGO kodu (etap 1+).

Wzorzec: zapis do pliku tymczasowego `pid_tid.tmp` + os.replace (atomowo),
retry z backoffem wykladniczym, DownloadError po wyczerpaniu prob.
Istniejace providery maja wlasne, przetestowane implementacje tego wzorca
i NIE sa przepinane w etapie 0.
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

RETRY_BACKOFF_BASE = 2
# Gorna granica oczekiwania z naglowka Retry-After (s): dluzszego postoju
# serwera i tak nie przeczekamy w trzech probach, a CLI nie moze "wisiec".
MAX_RETRY_AFTER = 60


def http_status(exc: requests.RequestException) -> int | None:
    response = getattr(exc, "response", None)
    return response.status_code if response is not None else None


def is_retryable(exc: requests.RequestException) -> bool:
    """Ponawiaj bledy sieci, 429 i 5xx; inne 4xx powtorzone daja to samo."""
    status = http_status(exc) if isinstance(exc, requests.HTTPError) else None
    if status is None:
        return True
    return status == 429 or status >= 500


def retry_wait(exc: requests.RequestException, backoff: float) -> float:
    """Czas przed kolejna proba: Retry-After (<= MAX_RETRY_AFTER) albo backoff."""
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
    """DownloadError z kodem HTTP ostatniej proby (o ile byl)."""
    status = http_status(exc) if exc is not None else None
    return DownloadError(message, status_code=status, **kwargs)


def make_gugik_session() -> requests.Session:
    """Utworz sesje keep-alive GUGiK; ponowienia obsluguje aplikacja."""
    from kartograf import __version__

    session = requests.Session()
    session.headers["User-Agent"] = f"kartograf/{__version__}"
    for scheme in ("http://", "https://"):
        session.mount(
            scheme, requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8)
        )
    return session


class SessionPerThread:
    """Jedna sesja na watek albo sesja powierzona przez wolajacego.

    ``requests.Session`` nie ma gwarancji bezpieczenstwa watkowego, wiec
    provider wspoldzielony przez pule watkow trzyma osobna sesje dla kazdego
    watku. Sesja wstrzyknieta (``injected``) wygrywa zawsze — o jej uzycie
    z wielu watkow dba wolajacy. ``factory`` (domyslnie
    ``make_gugik_session``) jest rozwiazywana przy pierwszym ``get()``
    w danym watku.
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


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    retries: int = 3,
    description: str = "",
    params: dict[str, str] | None = None,
) -> requests.Response:
    """Pobierz odpowiedz HTTP; kazda nieudana proba zachowuje ten sam URL.

    ``params`` (opcjonalne) trafiaja do ``session.get`` bez zmian — kazda
    proba wysyla ten sam zestaw parametrow zapytania.
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
                delay = retry_wait(exc, RETRY_BACKOFF_BASE**attempt)
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


def download_to(
    session: requests.Session,
    url: str,
    output_path: Path,
    *,
    timeout: int,
    retries: int = 3,
    chunk_size: int = 1_048_576,
) -> Path:
    """Pobierz URL do output_path (atomowo, z retry); zwroc output_path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(
        f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.tmp"
    )

    last_error: requests.RequestException | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        f.write(chunk)
            os.replace(temp_path, output_path)
            return output_path
        except requests.RequestException as e:
            last_error = e
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if not is_retryable(e):
                raise http_failure(
                    f"Nie udalo sie pobrac {url}: "
                    f"HTTP {http_status(e)} (bez ponowien): {e}",
                    e,
                ) from e
            if attempt < retries - 1:
                wait = retry_wait(e, RETRY_BACKOFF_BASE**attempt)
                logger.warning(
                    f"Pobranie {url} nieudane (proba {attempt + 1}/{retries}): "
                    f"{e}; ponowienie za {wait}s"
                )
                time.sleep(wait)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    raise http_failure(
        f"Nie udalo sie pobrac {url} po {retries} probach: {last_error}",
        last_error,
    )
