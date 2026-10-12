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
target key comes from its version sidecar (``version_key``).
"""

import contextlib
import errno
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path, PurePath

from kartograf.download.versions import read_version, version_key
from kartograf.exceptions import DownloadError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkOutcome:
    """Result of ``ensure_link``."""

    target: Path  # version file the link path points to
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


def link_atomic(target: Path, link: Path) -> None:
    """Set ``link`` -> ``target`` as a hardlink (D22).

    Always via a temporary file in the ``link`` directory
    (``<name>.<pid>_<tid>.link.tmp``) + ``os.replace`` (in place of an
    existing symlink it replaces the symlink ITSELF, it does not write
    through it). No hardlink support (exFAT/FAT, sshfs/FUSE) =
    ``DownloadError`` with a description; any other ``OSError`` propagates.
    The existing link is left untouched on failure and tmp is cleaned up.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
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
    """``version_key`` of a version file from its version sidecar; ``None``
    when the file is not a valid version."""
    version = read_version(path.parent, path.name)
    return version_key(version) if version is not None else None


def linked_version(link: Path) -> Path | None:
    """Version file the link path points to.

    The target comes ONLY from the link sidecar (``extra.link == "hardlink"``
    + ``extra.link_target``), verified with ``samefile``. ``None`` = no file,
    a sidecar without ``extra.link``, a ``copy`` from 0.7.x (D22: never
    trusted), a nonexistent ``link_target`` (version directory removed) or a
    hardlink that is no longer the same file.
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
        if target.is_file() and os.path.samefile(link, target):
            return target
    except OSError:
        pass
    return None


def _link_target_text(link: Path, target: Path) -> str:
    try:
        return PurePath(os.path.relpath(target, link.parent)).as_posix()
    except ValueError:  # different drive (Windows) — absolute path
        return PurePath(_norm(target)).as_posix()


def write_link_sidecar(link: Path, target: Path) -> None:
    """``<link>.meta.json`` = version sidecar + ``extra.link`` + ``extra.link_target``.

    A REGULAR file: tmp + ``os.replace`` (also replaces a sidecar symlink
    left by the user — never a write "through" it into the version
    sidecar). ``extra.link_target`` = path relative to the link file
    (absolute when a relative one is impossible) — the only source of the
    target. Unreadable version sidecar -> the old link sidecar is removed
    + ``logger.warning``. Never raises (the link sidecar is best-effort).
    """
    sidecar = _sidecar_of(link)
    tmp = _tmp_name(sidecar, "tmp")
    try:
        meta = _read_json(_sidecar_of(target))
        if meta is None:
            sidecar.unlink(missing_ok=True)
            logger.warning(
                f"Sidecar wersji {target} nieczytelny — brak sidecara {sidecar}"
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
        logger.warning(f"Nie udalo sie zapisac sidecara {sidecar}: {e}")


def update_sidecar_extra(data_path: Path, updates: dict) -> None:
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

    The current target ``cur = linked_version(link)`` stays
    (``changed=False``) when it is ``target`` itself and ``refresh`` is not
    set, or when its key (``version_key_of``) is newer than ``key`` — or
    equal without ``refresh`` (a new version under the same key, e.g. new
    content of the same campaign, moves the link only when committed in
    this call). Otherwise ``link_atomic`` + ``write_link_sidecar`` + removal
    of ``<link>.aux.xml`` (stale GDAL PAM statistics). A link sidecar that
    is a symlink is rewritten as a regular file even when the link stays.
    A missing ``<link>.meta.json`` = unknown path, the link is created anew.
    A swap failure propagates (``DownloadError`` without hardlinks, else
    ``OSError``); the existing link stays.

    Residual risk (race, no locks — a deliberate decision): parallel calls
    on the same ``link`` path may briefly leave the link on an older
    version; versions are never touched and the next call repairs the link.
    ``DownloadManager`` links each sheet once per call.
    """
    cur = linked_version(link)
    if cur is not None:
        same = _norm(cur) == _norm(target)
        cur_key = None if same else version_key_of(cur)
        keep = (
            (same and not refresh)
            or (cur_key is not None and cur_key > key)
            or (cur_key is not None and cur_key == key and not refresh)
        )
        if keep:
            if _sidecar_of(link).is_symlink():
                write_link_sidecar(link, cur)
            return LinkOutcome(cur, False)
    link_atomic(target, link)
    write_link_sidecar(link, target)
    (link.parent / f"{link.name}.aux.xml").unlink(missing_ok=True)
    return LinkOutcome(target, True)
