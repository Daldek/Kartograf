"""
Dowiazanie sciezki standardowej do najnowszej lokalnej kampanii (ADR-030 d).

Prawdziwe pliki NMT/NMPT/orto leza w ``<segment>/kampanie/<data>_<id>/...``;
sciezka standardowa ``<segment>/<hierarchia>/<godlo>.<ext>`` wskazuje
najnowsza LOKALNA kampanie. Metoda: 1) symlink WZGLEDNY, 2) hardlink,
3) kopia (``logger.warning``); podmiana zawsze atomowa (tymczasowe
dowiazanie w katalogu linku + ``os.replace``). Sidecar sciezki standardowej
to ZWYKLY plik (kopia sidecara celu + ``extra.link``/``extra.link_target``),
nigdy zapis "przez" dowiazanie.

Dowiazanie nigdy nie cofa sie na kampanie starsza od biezacego celu: klucz
celu z jego sidecara, a gdy nieczytelny — z nazwy katalogu ``<data>_<id>``
(errata ADR-030 (d), D-1).
"""

import contextlib
import json
import logging
import os
import re
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Literal

logger = logging.getLogger(__name__)

LinkMethod = Literal["symlink", "hardlink", "copy"]

# Lokalna stala (bez importu z download/campaigns.py — zadanie rownolegle).
_CAMPAIGNS_DIR = "kampanie"
_CAMPAIGN_DIR = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d+|u[0-9a-f]{8})")


@dataclass(frozen=True)
class LinkOutcome:
    """Wynik ``ensure_standard_link``."""

    method: LinkMethod
    target: Path  # plik kampanii wskazywany przez sciezke standardowa
    changed: bool  # dowiazanie utworzone/przestawione w tym wywolaniu


def _sidecar_of(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def _norm(path: Path | str) -> str:
    return os.path.normpath(os.path.abspath(path))


def _tmp_name(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}_{threading.get_ident()}.{suffix}")


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def link_atomic(target: Path, link: Path) -> LinkMethod:
    """Ustaw ``link`` -> ``target``: symlink WZGLEDNY, potem hardlink, potem kopia.

    Zawsze przez plik tymczasowy w katalogu ``link``
    (``<name>.<pid>_<tid>.link.tmp``) + ``os.replace``. Wyjatki proby
    (OSError, NotImplementedError, ValueError z ``relpath`` na Windows)
    = nastepna metoda; tmp sprzatany. Porazka kopii (OSError) wylatuje,
    a dotychczasowe dowiazanie zostaje nietkniete.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_name(link, "link.tmp")
    tmp.unlink(missing_ok=True)  # pozostalosc po przerwanym przebiegu (ten sam pid_tid)
    attempts: list[tuple[LinkMethod, Callable[[], object]]] = [
        ("symlink", lambda: os.symlink(os.path.relpath(target, link.parent), tmp)),
        ("hardlink", lambda: os.link(target, tmp)),
        ("copy", lambda: shutil.copyfile(target, tmp)),
    ]
    for method, make in attempts:
        try:
            make()
            os.replace(tmp, link)
        except (OSError, NotImplementedError, ValueError):
            tmp.unlink(missing_ok=True)
            if method == "copy":
                raise
            continue
        if method == "copy":
            logger.warning(f"Dowiazanie {link} niedostepne — kopia {target}")
        return method
    raise AssertionError("unreachable")


def campaign_key_from_sidecar(data_path: Path) -> tuple[str, str, str] | None:
    """``(extra.campaign.date, extra.campaign.dt_pzgik or "", extra.source.url)``
    z ``<data_path>.meta.json``; ``None`` gdy brak/nieczytelny/niepelny."""
    meta = _read_json(_sidecar_of(data_path))
    if meta is None:
        return None
    extra = meta.get("extra")
    if not isinstance(extra, dict):
        return None
    campaign = extra.get("campaign")
    source = extra.get("source")
    if not isinstance(campaign, dict) or not isinstance(source, dict):
        return None
    date = campaign.get("date")
    dt_pzgik = campaign.get("dt_pzgik") or ""
    url = source.get("url")
    if (
        not isinstance(date, str)
        or not isinstance(url, str)
        or not isinstance(dt_pzgik, str)
    ):
        return None
    return (date, dt_pzgik, url)


def campaign_key_of(data_path: Path) -> tuple[str, str, str] | None:
    """Klucz kampanii pliku (errata ADR-030 (d), D-1).

    Najpierw ``campaign_key_from_sidecar``; gdy ``None`` (brak sidecara
    kampanii = tylko ingerencja uzytkownika, errata 2 N-1) — z nazwy
    katalogu: element sciezki po OSTATNIM segmencie ``kampanie``, po ktorym
    nastepuje nazwa pasujaca w calosci do ``<data>_<id>`` (szukanie od
    konca — korzen wyjscia moze zawierac ``kampanie``) -> ``(data, "", "")``.
    Fallback jest DOLNYM oszacowaniem klucza (puste ``dt_pzgik`` i URL),
    wiec przy tej samej dacie nowy cel wygrywa, a cel o pozniejszej dacie
    zostaje. ``None`` tylko gdy ani
    sidecar, ani nazwa katalogu nie daja klucza.
    """
    key = campaign_key_from_sidecar(data_path)
    if key is not None:
        return key
    parts = PurePath(_norm(data_path)).parts
    # od konca: katalog wyjsciowy uzytkownika moze sam zawierac "kampanie"
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx] != _CAMPAIGNS_DIR:
            continue
        m = _CAMPAIGN_DIR.fullmatch(parts[idx + 1])
        if m is not None:
            return (m.group(1), "", "")
    return None


def linked_campaign(link: Path) -> Path | None:
    """Plik kampanii, na ktory wskazuje sciezka standardowa.

    ``None`` = brak pliku, wiszace dowiazanie, zwykly plik bez ``extra.link``
    (stary plik — errata (e)), hardlink, ktory nie jest juz tym samym plikiem
    (``samefile``), kopia o innym rozmiarze niz cel ALBO starsza od celu
    (D-5: ``target.st_mtime > link.st_mtime`` — cel pobrany ponownie po
    skopiowaniu; ``shutil.copyfile`` nie przenosi mtime, wiec swieza kopia
    ma mtime >= cel).
    """
    if link.is_symlink():
        target = Path(_norm(link.parent / os.readlink(link)))
        return target if target.exists() else None
    if not link.is_file():
        return None
    meta = _read_json(_sidecar_of(link))
    extra = meta.get("extra") if meta is not None else None
    if not isinstance(extra, dict):
        return None
    method = extra.get("link")
    rel = extra.get("link_target")
    if method not in ("hardlink", "copy") or not isinstance(rel, str):
        return None
    target = Path(_norm(link.parent / rel))
    try:
        if not target.is_file():
            return None
        if method == "hardlink":
            return target if os.path.samefile(link, target) else None
        t_stat, l_stat = target.stat(), link.stat()
    except OSError:
        return None
    if t_stat.st_size != l_stat.st_size or t_stat.st_mtime > l_stat.st_mtime:
        return None
    return target


def _link_target_text(link: Path, target: Path) -> str:
    try:
        return PurePath(os.path.relpath(target, link.parent)).as_posix()
    except ValueError:  # inny dysk (Windows) — sciezka absolutna
        return PurePath(_norm(target)).as_posix()


def write_standard_sidecar(link: Path, target: Path, method: LinkMethod) -> None:
    """``<link>.meta.json`` = sidecar celu + ``extra.link`` + ``extra.link_target``.

    ZWYKLY plik: tmp + ``os.replace`` (zastepuje takze symlink — nigdy zapis
    "przez" dowiazanie do sidecara kampanii). Sidecar celu nieczytelny ->
    stary sidecar standardowy usuniety + ``logger.warning``. Nigdy nie
    rzuca wyjatku (sidecar standardowy jest best-effort).
    """
    sidecar = _sidecar_of(link)
    tmp = _tmp_name(sidecar, "tmp")
    try:
        meta = _read_json(_sidecar_of(target))
        if meta is None:
            sidecar.unlink(missing_ok=True)
            logger.warning(
                f"Sidecar kampanii {target} nieczytelny — brak sidecara {sidecar}"
            )
            return
        extra = meta.get("extra")
        if not isinstance(extra, dict):
            extra = {}
            meta["extra"] = extra
        extra["link"] = method
        extra["link_target"] = _link_target_text(link, target)
        tmp.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, sidecar)
    except Exception as e:  # noqa: BLE001 — sidecar standardowy best-effort
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar}: {e}")


def _current_method(link: Path) -> LinkMethod:
    if link.is_symlink():
        return "symlink"
    meta = _read_json(_sidecar_of(link)) or {}
    extra = meta.get("extra")
    method = extra.get("link") if isinstance(extra, dict) else None
    # linked_campaign zwraca cel zwyklego pliku tylko dla hardlink/copy
    return "copy" if method == "copy" else "hardlink"


def ensure_standard_link(
    link: Path, target: Path, key: tuple[str, str, str], *, refresh: bool = False
) -> LinkOutcome:
    """Dowiazanie standardowe do najnowszej LOKALNEJ kampanii.

    Biezacy cel ``cur = linked_campaign(link)`` zostaje (``changed=False``),
    gdy istnieje i nie jest to odswiezenie tego samego celu (``refresh``
    i ``cur == target``), oraz ``cur == target`` ALBO klucz biezacego celu
    (``campaign_key_of`` — sidecar, a gdy nieczytelny nazwa katalogu) jest
    ``>= key``. Inaczej ``link_atomic`` + ``write_standard_sidecar`` +
    usuniecie ``<link>.aux.xml`` (stale statystyki GDAL PAM). Gdy dowiazanie
    zostaje, a ``<link>.meta.json`` brak — jest odtwarzany. Porownanie
    ``cur == target`` na sciezkach znormalizowanych, nie ``samefile``
    (kopia nie jest tym samym plikiem). Porazka podmiany (takze kopii)
    wylatuje jako ``OSError``; dotychczasowe dowiazanie zostaje.
    """
    cur = linked_campaign(link)
    if cur is not None:
        same = _norm(cur) == _norm(target)
        if not (refresh and same):
            cur_key = campaign_key_of(cur)
            if same or (cur_key is not None and cur_key >= key):
                method = _current_method(link)
                if not _sidecar_of(link).exists():
                    write_standard_sidecar(link, cur, method)
                return LinkOutcome(method, cur, False)
    method = link_atomic(target, link)
    write_standard_sidecar(link, target, method)
    (link.parent / f"{link.name}.aux.xml").unlink(missing_ok=True)
    return LinkOutcome(method, target, True)
