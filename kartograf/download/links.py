"""
Linking the standard path to the newest local campaign (ADR-030 d).

The real NMT/NMPT/orto files live in ``<segment>/kampanie/<date>_<id>/...``;
the standard path ``<segment>/<hierarchy>/<godlo>.<ext>`` points to the
newest LOCAL campaign. Method (errata 4 ADR-030): 1) hardlink, 2) copy
(``logger.warning``); we do not create symlinks (unreadable for Windows
clients over SMB, target length limit on the share). The swap is always
atomic (temporary file in the link directory + ``os.replace``). The standard
path sidecar is a REGULAR file (a copy of the target sidecar +
``extra.link``/``extra.link_target``) and the ONLY source of the link target
(a hardlink carries no pointer). An existing symlink (data from before the
release) = unknown path, replaced with a hardlink.

The link never moves back to a campaign older than the current target: the
target key comes from its sidecar and, when unreadable, from the directory
name ``<date>_<id>`` (errata ADR-030 (d), D-1).
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

LinkMethod = Literal["hardlink", "copy"]

# Local constant (no import from download/campaigns.py — parallel task).
_CAMPAIGNS_DIR = "kampanie"
_CAMPAIGN_DIR = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d+|u[0-9a-f]{8})")


@dataclass(frozen=True)
class LinkOutcome:
    """Result of ``ensure_standard_link``."""

    method: LinkMethod
    target: Path  # campaign file the standard path points to
    changed: bool  # link created/moved in this call


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
    """Set ``link`` -> ``target``: a hardlink, or a copy when unavailable.

    Always via a temporary file in the ``link`` directory
    (``<name>.<pid>_<tid>.link.tmp``) + ``os.replace`` (in place of an
    existing symlink it replaces the symlink ITSELF, it does not write
    through it). A hardlink exception (OSError, NotImplementedError — e.g.
    exFAT/FAT, sshfs/FUSE) = copy + ``logger.warning``; tmp cleaned up. A
    copy failure (OSError) propagates and the existing link is left
    untouched.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_name(link, "link.tmp")
    tmp.unlink(missing_ok=True)  # leftover from an interrupted run (same pid_tid)
    attempts: list[tuple[LinkMethod, Callable[[], object]]] = [
        ("hardlink", lambda: os.link(target, tmp)),
        ("copy", lambda: shutil.copyfile(target, tmp)),
    ]
    for method, make in attempts:
        try:
            make()
            os.replace(tmp, link)
        except (OSError, NotImplementedError):
            # a cleanup failure must not lose the copy attempt or the copy error
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            if method == "copy":
                raise
            continue
        # rename(2) onto the same inode (link is already a hardlink of the
        # target) does nothing and leaves tmp behind
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        if method == "copy":
            logger.warning(f"Hardlink {link} niedostepny — kopia {target}")
        return method
    raise AssertionError("unreachable")


def campaign_key_from_sidecar(data_path: Path) -> tuple[str, str, str] | None:
    """``(extra.campaign.date, extra.campaign.pzgik_date or "", extra.source.url)``
    from ``<data_path>.meta.json``; ``None`` when missing/unreadable/incomplete.

    A sidecar without the ``extra.campaign.pzgik_date`` key (written before
    ADR-031 with Polish key names) is incomplete: ``None``, so
    ``campaign_key_of`` falls back to the lower bound from the directory name.
    """
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
    if "pzgik_date" not in campaign:
        return None
    date = campaign.get("date")
    dt_pzgik = campaign.get("pzgik_date") or ""
    url = source.get("url")
    if (
        not isinstance(date, str)
        or not isinstance(url, str)
        or not isinstance(dt_pzgik, str)
    ):
        return None
    return (date, dt_pzgik, url)


def campaign_key_of(data_path: Path) -> tuple[str, str, str] | None:
    """Campaign key of a file (errata ADR-030 (d), D-1).

    First ``campaign_key_from_sidecar``; when ``None`` (no campaign sidecar
    = only user interference, errata 2 N-1) — from the directory name: the
    path element after the LAST ``kampanie`` segment that is followed by a
    name fully matching ``<date>_<id>`` (searched from the end — the output
    root may contain ``kampanie``) -> ``(date, "", "")``. The fallback is a
    LOWER BOUND of the key (empty ``dt_pzgik`` and URL), so with the same
    date the new target wins, while a target with a later date stays.
    ``None`` only when neither the sidecar nor the directory name yields a
    key.
    """
    key = campaign_key_from_sidecar(data_path)
    if key is not None:
        return key
    parts = PurePath(_norm(data_path)).parts
    # from the end: the user output directory may itself contain "kampanie"
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx] != _CAMPAIGNS_DIR:
            continue
        m = _CAMPAIGN_DIR.fullmatch(parts[idx + 1])
        if m is not None:
            return (m.group(1), "", "")
    return None


def linked_campaign(link: Path) -> Path | None:
    """Campaign file the standard path points to.

    The target comes ONLY from the standard sidecar (``extra.link`` in
    {hardlink, copy} + ``extra.link_target``), verified against the file.
    ``None`` = no file, a file without ``extra.link`` or with another
    ``extra.link`` (old file — errata (e); symlink from before errata 4), a
    nonexistent ``link_target`` (campaign directory removed), a hardlink
    that is no longer the same file (``samefile``), a copy of a different
    size than the target OR older than the target (D-5:
    ``target.st_mtime > link.st_mtime`` — target downloaded again after
    copying; ``shutil.copyfile`` does not carry over mtime, so a fresh copy
    has mtime >= target).
    """
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
    except ValueError:  # different drive (Windows) — absolute path
        return PurePath(_norm(target)).as_posix()


def write_standard_sidecar(link: Path, target: Path, method: LinkMethod) -> None:
    """``<link>.meta.json`` = target sidecar + ``extra.link`` + ``extra.link_target``.

    A REGULAR file: tmp + ``os.replace`` (also replaces a sidecar symlink
    left by the user — never a write "through" it into the campaign
    sidecar). ``extra.link_target`` = path relative to the campaign file
    (absolute when a relative one is impossible) — the only source of the
    target. Unreadable target sidecar -> the old standard sidecar is removed
    + ``logger.warning``. Never raises (the standard sidecar is best-effort).
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
    except Exception as e:  # noqa: BLE001 — standard sidecar is best-effort
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar}: {e}")


def _current_method(link: Path) -> LinkMethod:
    meta = _read_json(_sidecar_of(link)) or {}
    extra = meta.get("extra")
    method = extra.get("link") if isinstance(extra, dict) else None
    # linked_campaign returns the target of a regular file only for hardlink/copy
    return "copy" if method == "copy" else "hardlink"


def ensure_standard_link(
    link: Path, target: Path, key: tuple[str, str, str], *, refresh: bool = False
) -> LinkOutcome:
    """Standard link to the newest LOCAL campaign.

    The current target ``cur = linked_campaign(link)`` stays
    (``changed=False``) when it exists, this is not a refresh of the same
    target (``refresh`` and ``cur == target``), and either ``cur == target``
    OR the key of the current target (``campaign_key_of`` — sidecar, and
    when unreadable the directory name) is ``>= key``. Otherwise
    ``link_atomic`` + ``write_standard_sidecar`` + removal of
    ``<link>.aux.xml`` (stale GDAL PAM statistics). A missing
    ``<link>.meta.json`` = unknown path (the sidecar is the only source of
    the target), so the link is created anew. The ``cur == target``
    comparison uses normalized paths, not ``samefile`` (a copy is not the
    same file). A swap failure (a copy too) propagates as ``OSError``; the
    existing link stays.

    Residual risk (race, no locks — a deliberate decision): parallel calls
    on the same ``link`` path (within one process or across processes) may
    briefly leave the link on an older campaign (reading the current target
    and the swap are not one atomic operation). Files in ``kampanie/``
    remain untouched, and the next ``newest``/``all`` call repairs the link
    itself. ``DownloadManager`` does not call this function in parallel for
    one sheet (a link once per sheet, godlo deduplication in
    ``expand_sheets``).
    """
    cur = linked_campaign(link)
    if cur is not None:
        same = _norm(cur) == _norm(target)
        if not (refresh and same):
            cur_key = campaign_key_of(cur)
            if same or (cur_key is not None and cur_key >= key):
                return LinkOutcome(_current_method(link), cur, False)
    method = link_atomic(target, link)
    write_standard_sidecar(link, target, method)
    (link.parent / f"{link.name}.aux.xml").unlink(missing_ok=True)
    return LinkOutcome(method, target, True)
