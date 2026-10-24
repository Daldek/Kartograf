"""
Linking a path to the newest local version (spec 3.2; ADR-030 d, ADR-033).

The real NMT/NMPT/orto files live as versions in
``<segment>/versions/<hierarchy>/<label>_<sha8>/...``. Two link paths point
into them: the standard path ``<segment>/<hierarchy>/<sheet>.<ext>`` (newest
LOCAL version) and the second link
``<segment>/full_sheet/<hierarchy>/<sheet>.<ext>`` (newest LOCAL version of a
campaign declared full in the index). The mechanics below do not depend on
which link path is used. Method: hardlink only (D22) — a file system without
hardlinks is a ``DownloadError``; never a copy, never a symlink (unreadable
for Windows clients over SMB). The swap is always atomic (temporary file in
the link directory + ``os.replace``). The link path sidecar is a REGULAR
file (a copy of the version sidecar + ``extra.link``/``extra.link_target``)
and the ONLY source of the link target (a hardlink carries no pointer). A
link sidecar from an older release (``extra.link == "copy"``, a symlink,
no ``extra.link``) = unknown path, replaced with a hardlink.

The link never moves back to a version older than the current target: the
target key comes from its version sidecar (``version_key``). The current
target is what the path HOLDS: the version named by its sidecar, confirmed
by inode identity (``samefile``) or - where the file system gives none -
by content (size + sha256), never by the link count: an SMB client without
``serverino`` reports ``st_nlink == 1`` for a path it has just opened (also
for the read that confirms the content), so the count is no evidence.
"""

import contextlib
import errno
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from kartograf.download.versions import ensure_dir, read_version, version_key
from kartograf.exceptions import DownloadError
from kartograf.sources.sidecar import file_digest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkOutcome:
    """Result of ``ensure_link``."""

    target: Path  # version file the link path points to
    changed: bool  # link created/moved/restored in this call


def _sidecar_of(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def _norm(path: Path | str) -> str:
    return os.path.normpath(os.path.abspath(path))


def _tmp_name(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}_{threading.get_ident()}.{suffix}")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def link_atomic(target: Path, link: Path) -> None:
    """Set ``link`` -> ``target`` as a hardlink (D22).

    Always via a temporary file in the ``link`` directory
    (``<name>.<pid>_<tid>.link.tmp``) + ``os.replace`` (in place of an
    existing symlink it replaces the symlink ITSELF, it does not write
    through it). No hardlink support (exFAT/FAT, sshfs/FUSE) =
    ``DownloadError`` with a description; any other ``OSError`` propagates.
    The existing link is left untouched on failure and tmp is cleaned up.
    """
    ensure_dir(link.parent)
    tmp = _tmp_name(link, "link.tmp")
    tmp.unlink(missing_ok=True)  # leftover from an interrupted run (same pid_tid)
    try:
        os.link(target, tmp)
        os.replace(tmp, link)
    except (OSError, NotImplementedError) as e:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        if isinstance(e, NotImplementedError) or e.errno in (
            errno.EPERM,
            errno.EOPNOTSUPP,
            getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
            errno.EXDEV,
            errno.EMLINK,
        ):
            raise DownloadError(
                f"{link}: magazyn wersji wymaga systemu plikow z hardlinkami (D22): {e}"
            ) from e
        raise
    # rename(2) onto the same inode (link is already a hardlink of the
    # target) does nothing and leaves tmp behind
    with contextlib.suppress(OSError):
        tmp.unlink(missing_ok=True)


def version_key_of(path: Path) -> tuple[str, str, str] | None:
    """Return the ``version_key`` of a version file.

    ``version_key`` of a version file from its version sidecar; ``None``
    when the file is not a valid version.
    """
    version = read_version(path.parent, path.name)
    return version_key(version) if version is not None else None


@dataclass(frozen=True)
class _Held:
    """What a link path holds (``_hold``)."""

    version: Path  # version file named by the link sidecar
    lone: bool  # confirmed by content only and no path reports a second name


def _hold(link: Path) -> _Held | None:
    """Return the version that ``link`` holds, from its sidecar and the file itself.

    The target comes ONLY from the link sidecar (``extra.link == "hardlink"``
    + ``extra.link_target``), verified with ``samefile``. Where the file
    system reports no stable inode numbers (e.g. SMB mounted without
    ``serverino``) ``samefile`` is false even for a hardlink; the path is
    then confirmed by content (``_same_content``). ``None`` = no file, a
    sidecar without ``extra.link``, a ``copy`` from 0.7.x (D22: never
    trusted), a nonexistent ``link_target`` (version directory removed) or
    a path that no longer holds the version content.
    """
    if not link.is_file():
        return None
    meta = _read_json(_sidecar_of(link))
    extra = meta.get("extra") if meta is not None else None
    if not isinstance(extra, dict):
        return None
    rel = extra.get("link_target")
    if extra.get("link") != "hardlink" or not isinstance(rel, str):
        return None
    target = Path(_norm(link.parent / rel))
    try:
        if not target.is_file():
            return None
        if os.path.samefile(link, target):
            return _Held(target, False)
        return _same_content(link, target)
    except OSError:
        return None


def _same_content(link: Path, target: Path) -> _Held | None:
    """Confirm a link without inode identity by size and sha256.

    Confirmation without inode identity: the same size and the link's
    sha256 equal to the version sidecar's (one full read of ``link``).

    The link counts are read BEFORE that read (the read itself makes an SMB
    client report ``st_nlink == 1`` for ``link`` for a few seconds). They do
    not confirm anything; they only mark a probable independent copy
    (``_Held.lone``: neither path reports a second name) for ``ensure_link``
    to restore as a hardlink. A transient 1 on one path leaves the other
    one at its real count.
    """
    l_stat, t_stat = link.stat(), target.stat()
    if l_stat.st_size != t_stat.st_size:
        return None
    version = read_version(target.parent, target.name)
    if version is None or file_digest(link)[0] != version.sha256:
        return None
    return _Held(target, l_stat.st_nlink < 2 and t_stat.st_nlink < 2)


def linked_version(link: Path) -> Path | None:
    """Version file the link path holds (``None`` = none).

    The version named by the link sidecar when the path is that file by
    inode identity (``samefile``) or - where the file system gives no
    stable inode numbers (e.g. SMB mounted without ``serverino``) - holds
    its content: the same size and the sha256 of the sidecar of that
    version (one full read, only on such mounts). The link count plays no
    part, so the answer does not change with the client's attribute cache.
    Nonexistent file, sidecar without ``extra.link``, a ``copy`` from 0.7.x,
    a removed version directory or changed content give ``None``.
    """
    held = _hold(link)
    return held.version if held is not None else None


def _link_target_text(link: Path, target: Path) -> str:
    try:
        return PurePath(os.path.relpath(target, link.parent)).as_posix()
    except ValueError:  # different drive (Windows) — absolute path
        return PurePath(_norm(target)).as_posix()


def write_link_sidecar(link: Path, target: Path) -> None:
    """``<link>.meta.json`` = version sidecar + ``extra.link`` + ``extra.link_target``.

    A REGULAR file: tmp + ``os.replace`` (also replaces a sidecar symlink
    left by the user — never a write "through" it into the version
    (absolute when a relative one is impossible) — the only source of the
    target. Unreadable version sidecar or a failed write -> the old link
    sidecar is removed + ``logger.warning``: it would describe another
    version (ADR-030 errata 10, M-8); without it the link is an unknown
    path and the next ``ensure_link`` relinks it and writes the sidecar.
    Never raises (the link sidecar is best-effort).
    """
    sidecar = _sidecar_of(link)
    tmp = _tmp_name(sidecar, "tmp")
    try:
        meta = _read_json(_sidecar_of(target))
        if meta is None:
            sidecar.unlink(missing_ok=True)
            logger.warning(
                f"Sidecar wersji {target} nieczytelny - brak sidecara {sidecar}"
            )
            return
        extra = meta.get("extra")
        if not isinstance(extra, dict):
            extra = {}
            meta["extra"] = extra
        extra["link"] = "hardlink"
        extra["link_target"] = _link_target_text(link, target)
        tmp.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, sidecar)
    except Exception as e:  # noqa: BLE001 — link sidecar is best-effort
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            sidecar.unlink(missing_ok=True)
        logger.warning(
            f"Nie udalo sie zapisac sidecara {sidecar}: {e} - stary sidecar "
            "usuniety (nastepne uruchomienie odtworzy dowiazanie)"
        )


def update_sidecar_extra(data_path: Path, updates: dict[str, Any]) -> None:
    """Atomically update existing LINK sidecar extra fields, never create one.

    Only for link sidecars (``extra.flights``, ``extra.better_coverage``); a
    version sidecar is never changed (D12/D13). ``None`` clears a stale
    optional field. A missing or unreadable sidecar is best-effort: warn on
    errors, but do not fail an already downloaded sheet. A sidecar symlink
    is replaced by a regular file (never written through).
    """
    sidecar = _sidecar_of(data_path)
    if not sidecar.exists():
        return
    tmp = _tmp_name(sidecar, "tmp")
    try:
        payload = _read_json(sidecar)
        if payload is None:
            raise ValueError("nieczytelny JSON sidecara")
        extra = payload.get("extra")
        if not isinstance(extra, dict):
            extra = {}
            payload["extra"] = extra
        for key, value in updates.items():
            if value is None:
                extra.pop(key, None)
            else:
                extra[key] = value
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, sidecar)
    except Exception as e:  # noqa: BLE001 — metadata must not abort a download
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        logger.warning(f"Nie udalo sie dopisac danych do sidecara {sidecar}: {e}")


def ensure_link(
    link: Path, target: Path, key: tuple[str, str, str], *, refresh: bool = False
) -> LinkOutcome:
    """Link ``link`` (standard or ``full_sheet/`` path) to the newest LOCAL version.

    The version the path holds now (``cur``, see ``linked_version``) stays
    (``changed=False``) when it is ``target`` itself and ``refresh`` is not
    set, or when its key (``version_key_of``) is newer than ``key`` — or
    equal without ``refresh`` (a new version under the same key, e.g. new
    content of the same campaign, moves the link only when committed in
    this call). Then nothing is written, except: a path that holds the
    content of ``cur`` but is evidently an independent copy (no path
    reports a second name, e.g. after ``rsync -a`` without ``-H``) is
    replaced by a hardlink of ``cur`` (``changed=True``, never of another
    version), and a link sidecar that is a symlink is rewritten as a
    regular file. Otherwise ``link_atomic`` + ``write_link_sidecar`` +
    removal of ``<link>.aux.xml`` (stale GDAL PAM statistics). A missing
    ``<link>.meta.json`` = unknown path, the link is created anew.
    A swap failure propagates (``DownloadError`` without hardlinks, else
    ``OSError``); the existing link stays.

    Residual risk (race, no locks — a deliberate decision): parallel calls
    on the same ``link`` path may briefly leave the link on an older
    version; versions are never touched and the next call repairs the link.
    ``DownloadManager`` links each sheet once per call.
    """
    held = _hold(link)
    if held is not None:
        cur = held.version
        same = _norm(cur) == _norm(target)
        cur_key = None if same else version_key_of(cur)
        keep = (
            (same and not refresh)
            or (cur_key is not None and cur_key > key)
            or (cur_key is not None and cur_key == key and not refresh)
        )
        if keep:
            if held.lone:
                link_atomic(cur, link)
            if _sidecar_of(link).is_symlink():
                write_link_sidecar(link, cur)
            return LinkOutcome(cur, held.lone)
    link_atomic(target, link)
    write_link_sidecar(link, target)
    (link.parent / f"{link.name}.aux.xml").unlink(missing_ok=True)
    return LinkOutcome(target, True)
