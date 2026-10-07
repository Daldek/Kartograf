"""
Wspolny transport HTTP wszystkich providerow (review 2026-10-06 D1/D2).

Jedno miejsce polityki pobierania: zapis do pliku tymczasowego
``<plik>.<pid>_<tid>.tmp`` + ``os.replace`` (atomowo), do ``MAX_RETRIES``
prob z backoffem wykladniczym (``backoff_delay``: 2 s, 4 s), ponawiane
tylko bledy sieci, 429 i 5xx (``is_retryable``), ``Retry-After`` wydluza
przerwe (``retry_wait``), ``DownloadError.status_code`` niesie kod HTTP
ostatniej proby (``http_failure``). Pliki pobieraja ``download_to``,
odpowiedzi w pamieci ``get_with_retry``; sesje na watek ``SessionPerThread``.
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

# Liczba prob (pierwsza + ponowienia) — jedna dla calego pakietu.
MAX_RETRIES = 3
# Backoff przed ponowieniem n (n = 1, 2, ...): RETRY_BACKOFF_BASE ** n,
# czyli 2 s i 4 s. Jedna wartosc dla plikow i zapytan (D1, 2026-10-07):
# wczesniej providery czekaly 2 s/4 s, a transport wspolny 1 s/2 s.
RETRY_BACKOFF_BASE = 2
# Gorna granica oczekiwania z naglowka Retry-After (s): dluzszego postoju
# serwera i tak nie przeczekamy w trzech probach, a CLI nie moze "wisiec".
MAX_RETRY_AFTER = 60


def backoff_delay(attempt: int) -> float:
    """Przerwa po nieudanej probie ``attempt`` (od 0): 2 s, 4 s, ..."""
    return RETRY_BACKOFF_BASE ** (attempt + 1)


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


def reject_error_document(service: str) -> Callable[[requests.Response], None]:
    """Walidator ``download_to``: raport bledu XML/HTML zamiast danych.

    Uslugi OGC (WMS/WCS) potrafia odpowiedziec HTTP 200 z dokumentem
    ``ServiceException`` — taki plik nie moze trafic na dysk jako raster.
    Blad tresci nie jest ponawiany (ten sam URL da ten sam raport).
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
    """Zapisz strumien odpowiedzi do output_path przez plik tymczasowy."""
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
    """Pobierz URL do pliku (atomowo, z polityka ponowien); zwroc sciezke.

    Parameters
    ----------
    description : str, optional
        Opis do komunikatow i logow (domyslnie URL).
    validate : callable, optional
        Wolany z odpowiedzia po ``raise_for_status``, przed zapisem; wyjatek
        spoza ``requests.RequestException`` konczy pobieranie bez ponowien
        (np. ``reject_error_document``).
    save : callable, optional
        Zapis odpowiedzi zamiast domyslnego atomowego zapisu strumienia;
        zwraca sciezke faktycznie zapisanego pliku (np. rozpakowany ZIP).
        Przerwany strumien (``RequestException``) jest ponawiany.

    Katalog docelowy powstaje dopiero po udanej odpowiedzi — blad HTTP nie
    zostawia pustych katalogow.
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
