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
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE = 2


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

    last_error: Exception | None = None
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
            if attempt < retries - 1:
                wait = RETRY_BACKOFF_BASE**attempt
                logger.warning(
                    f"Pobranie {url} nieudane (proba {attempt + 1}/{retries}): "
                    f"{e}; ponowienie za {wait}s"
                )
                time.sleep(wait)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    raise DownloadError(
        f"Nie udalo sie pobrac {url} po {retries} probach: {last_error}"
    )
