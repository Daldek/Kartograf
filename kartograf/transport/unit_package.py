"""
Engine ``unit_package`` (ADR-042 D1-D2, ADR-043): one file per unit.

A collection channel with ``UnitPackageParams`` publishes one package per
unit - administrative unit (powiat, voivodeship), national file (one per
theme), map sheet, index tile or CZ cadastral area; each ``PackageVariant``
is one published choice (year, format, LoD, scale, sheet system, network)
with its URL template, or with ``url_template=None`` the URL of the unit's
index record (``index_url``). ``select_variant`` picks the variant of a
user's choice without any network (a missing or unknown value is a
``ValidationError`` naming the allowed values), ``package_url`` fills the
template, ``fetch_package`` downloads the file atomically
(``transport.http.download_to``) and checks its bytes against
``Content-Length``. A ZIP (``file_kind="zip"``): the central directory is
read, the variant's member suffixes are required and - with ``unpack`` -
exactly one member is streamed to the result (``zipfile`` checks its CRC).
A channel with ``class_pattern`` (BDOO: files ``__OT_<KOD>_<typ>.``) needs at
least one class member, and a choice of classes stores a new ZIP of the
members of those classes only - in the order of the source, each streamed
byte for byte with its name and date; none of them in the package =
``NoCoverageError`` (the unit has no objects of those classes).
A GeoPackage member with ``unpack_layers`` is unpacked in a local working
directory first and its ``gpkg_contents`` must name every required layer:
SQLite opens only that local copy (a store on a network volume has no
working byte-range locks, ADR-042 D5), the checked file then moves to the
staging path. Another kind is stored as published and checked by its
content: TIFF magic (``tiff``), ``%PDF-`` (``pdf``) or a text head
(``txt``: no NUL bytes, the first non-empty line is not markup). HTTP 404
is ``NoCoverageError`` (the source publishes no file of the unit), every
other failure ``DownloadError``; the file never sits in memory and a failure
leaves no result file.
"""

import os
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
import zlib
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.sources.descriptor import FileKind, PackageVariant, UnitPackageParams
from kartograf.transport.http import download_to, response_signal

_COPY_CHUNK = 1_048_576
_TOKEN = re.compile(r"{(\w+)}")
# Bytes read to check a file that is not a ZIP by its content.
_HEAD_BYTES = 4096
# Classic and BigTIFF byte-order marks with the version number.
_TIFF_MAGIC = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
# Suffix of the stored file of each kind (a ZIP without ``unpack`` included).
FILE_SUFFIX: dict[FileKind, str] = {
    "zip": ".zip",
    "tiff": ".tif",
    "pdf": ".pdf",
    "txt": ".txt",
}
# Kind of the expected file in messages ("zamiast <...>", "oczekiwano <...>").
_KIND_TEXT: dict[FileKind, str] = {
    "zip": "paczki ZIP",
    "tiff": "pliku TIFF",
    "pdf": "pliku PDF",
    "txt": "pliku tekstowego",
}


@dataclass(frozen=True)
class PackageFile:
    """A downloaded package: ``path`` = the stored file (the ZIP itself, the
    unpacked member or the ZIP of the chosen classes), ``http`` =
    ``response_signal`` of the download, ``size`` = bytes of the downloaded
    ZIP, ``member`` = the unpacked member name, ``classes`` = the chosen
    classes found in the package (``()``: no class choice)."""

    path: Path
    http: dict
    size: int
    member: str | None = None
    classes: tuple[str, ...] = ()


def choice_keys(params: UnitPackageParams) -> tuple[str, ...]:
    """Option names that select a variant of the channel (``()``: one variant)."""
    return tuple(key for key, _ in params.variants[0].choice)


def _values(variants: list[PackageVariant], key: str) -> list[str]:
    """Distinct values of ``key`` in registry order."""
    seen: list[str] = []
    for variant in variants:
        value = dict(variant.choice)[key]
        if value not in seen:
            seen.append(value)
    return seen


def select_variant(params: UnitPackageParams, **choice: str | None) -> PackageVariant:
    """The published variant of a choice (``None`` values = not chosen).

    Every key must belong to the channel; a chosen value must be published
    (together with the other chosen values); when several variants remain,
    the first key that still distinguishes them is required (K8: no data
    default). A channel with one variant needs no choice, and a chosen value
    must then equal the published one.

    Raises
    ------
    ValidationError
        An option the channel does not have, a value that is not published,
        or a missing required option; the text names the flag (``--year``)
        and the allowed values.
    """
    keys = choice_keys(params)
    given = {key: value for key, value in choice.items() if value is not None}
    foreign = sorted(set(given) - set(keys))
    if foreign:
        raise ValidationError(
            f"--{foreign[0]} nie dotyczy tego produktu"
            + (f" (wybory: {', '.join(f'--{k}' for k in keys)})" if keys else "")
        )
    candidates = list(params.variants)
    context: list[str] = []
    for key in keys:
        if key not in given:
            continue
        allowed = _values(candidates, key)
        if given[key] not in allowed:
            where = f" dla {', '.join(context)}" if context else ""
            raise ValidationError(
                f"--{key} {given[key]}: niedostepne{where}; dostepne: "
                f"{', '.join(allowed)}"
            )
        candidates = [v for v in candidates if dict(v.choice)[key] == given[key]]
        context.append(f"--{key} {given[key]}")
    if len(candidates) == 1:
        return candidates[0]
    for key in keys:
        allowed = _values(candidates, key)
        if len(allowed) > 1:
            where = f" dla {', '.join(context)}" if context else ""
            raise ValidationError(f"--{key} wymagane{where}: {', '.join(allowed)}")
    raise AssertionError(f"Warianty kanalu nie sa rozroznialne: {candidates}")


def package_url(
    variant: PackageVariant,
    *,
    teryt: str | None = None,
    sheet: str | None = None,
    ku: str | None = None,
    theme: str | None = None,
) -> str:
    """URL of the variant's file for a unit: the template tokens ``{teryt}``,
    ``{woj}`` (its first two digits), ``{sheet}``, ``{ku}`` and ``{theme}``.

    Raises
    ------
    ValueError
        A variant without a template (its URL comes from an index record,
        ``index_url``) or a template token without a value (programmer
        error).
    """
    template = variant.url_template
    if template is None:
        raise ValueError("Wariant bez szablonu URL - adres daje rekord indeksu")
    values = {
        "teryt": teryt,
        "woj": teryt[:2] if teryt else None,
        "sheet": sheet,
        "ku": ku,
        "theme": theme,
    }
    missing = sorted(
        {token for token in _TOKEN.findall(template) if values.get(token) is None}
    )
    if missing:
        raise ValueError(f"Szablon {template} wymaga {', '.join(missing)}")
    return template.format(**{key: value or "" for key, value in values.items()})


def index_url(variant: PackageVariant, urls: Mapping[str, str], *, unit: str) -> str:
    """URL of the variant in the index record of ``unit`` (``url_template``
    ``None``): the only link of a record with one URL (key ``""``), else the
    link of the variant's ``format`` choice.

    Raises
    ------
    DownloadError
        The record has no link of that format (the index changed shape: the
        file cannot be addressed).
    """
    if set(urls) == {""}:
        return urls[""]
    file_format = dict(variant.choice).get("format")
    if file_format is None or file_format not in urls:
        raise DownloadError(
            f"{unit}: rekord indeksu bez pliku {file_format or '?'} "
            f"(sa: {', '.join(sorted(urls)) or 'brak'})"
        )
    return urls[file_format]


def reject_documents(url: str, kind: FileKind = "zip"):
    """``download_to`` validator: an HTML/XML document instead of the file."""

    def validate(response: requests.Response) -> None:
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "html" in content_type or "xml" in content_type:
            raise DownloadError(
                f"{url}: zrodlo zwrocilo dokument ({content_type}) zamiast "
                f"{_KIND_TEXT[kind]}"
            )

    return validate


def fetch_package(
    session: requests.Session,
    url: str,
    staged: Path,
    *,
    params: UnitPackageParams,
    variant: PackageVariant,
    timeout: float,
    classes: Sequence[str] = (),
) -> PackageFile:
    """Download the file ``url`` into ``staged`` (the ZIP, its member, the
    ZIP of the members of ``classes`` or the file of another
    ``variant.file_kind``).

    ``classes``: class codes of ``variant.classes`` (``layers``) - the
    stored file holds only their members (module docstring).

    Raises
    ------
    NoCoverageError
        HTTP 404: no file of this unit at the source; a package without a
        member of any of ``classes``.
    DownloadError
        Any other HTTP/network failure (after the retry policy), a document
        instead of the file, fewer bytes than ``Content-Length``, an
        unreadable ZIP, missing required members or class members, not
        exactly one member to unpack, a member failing its CRC or a file
        whose content is not of its kind. No result file is left behind.
    """
    staged = Path(staged)
    kind = variant.file_kind
    unpack = params.unpack if kind == "zip" else None
    rewrite = unpack is not None or bool(classes)
    archive_path = staged.with_name(f"{staged.name}.zip") if rewrite else staged
    signal: dict = {}
    try:
        download_to(
            session,
            url,
            archive_path,
            timeout=timeout,
            description=url,
            validate=reject_documents(url, kind),
            on_response=lambda response: signal.update(response_signal(response)),
        )
    except DownloadError as e:
        if e.status_code == 404:
            what = "paczki" if kind == "zip" else "pliku"
            raise NoCoverageError(
                f"Zrodlo nie publikuje {what} {url} (HTTP 404)", status_code=404
            ) from e
        raise
    kept: tuple[str, ...] = ()
    try:
        size = archive_path.stat().st_size
        expected = signal.get("content_length")
        if expected is not None and expected != size:
            raise DownloadError(
                f"{url}: pobrano {size} z {expected} bajtow (przerwany transfer)"
            )
        if kind == "zip":
            member, kept = _check_archive(
                url, archive_path, staged, params, variant, tuple(classes)
            )
        else:
            _check_content(url, archive_path, kind)
            member = None
    except BaseException:
        staged.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        raise
    if rewrite:
        archive_path.unlink(missing_ok=True)
    return PackageFile(staged, signal, size, member, kept)


def _check_content(url: str, path: Path, kind: FileKind) -> None:
    """A file that is not a ZIP checked by its first bytes (module docstring)."""
    try:
        with open(path, "rb") as stream:
            head = stream.read(_HEAD_BYTES)
    except OSError as e:
        raise DownloadError(f"{url}: nie udalo sie odczytac pliku: {e}") from e
    if kind == "tiff":
        valid = head[:4] in _TIFF_MAGIC
    elif kind == "pdf":
        valid = head.startswith(b"%PDF-")
    else:
        valid = _is_text(head)
    if not valid:
        raise DownloadError(
            f"{url}: oczekiwano {_KIND_TEXT[kind]}, a plik zaczyna sie od "
            f"{head[:16]!r} - to nie sa oczekiwane dane"
        )


def _is_text(head: bytes) -> bool:
    """Text without NUL bytes (any 8-bit encoding) whose first non-empty line
    is not markup: an HTML or XML document is never the published text file,
    and binary files (ZIP, TIFF, PDF streams) carry NUL bytes in their head."""
    if not head or b"\x00" in head:
        return False
    text = head.decode("latin-1").lstrip("\ufeff\xef\xbb\xbf")
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return bool(first) and not first.startswith("<")


def _check_archive(
    url: str,
    archive_path: Path,
    staged: Path,
    params: UnitPackageParams,
    variant: PackageVariant,
    classes: tuple[str, ...],
) -> tuple[str | None, tuple[str, ...]]:
    """Central directory, required members, class members and the optional
    unpacked member or ZIP of ``classes``: the unpacked member name and the
    classes kept."""
    try:
        with zipfile.ZipFile(archive_path) as archive:
            files = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename.lower() for info in files]
            missing = [
                suffix
                for suffix in variant.members
                if not any(name.endswith(suffix.lower()) for name in names)
            ]
            if missing:
                raise DownloadError(
                    f"{url}: paczka bez plikow {', '.join(missing)} "
                    f"({len(files)} plikow) - to nie sa oczekiwane dane"
                )
            if params.class_pattern is not None:
                kept = _class_members(
                    url, archive, files, params.class_pattern, classes, staged
                )
                return None, kept
            if classes:
                raise ValueError(f"{url}: wybor klas bez class_pattern kanalu")
            if params.unpack is None:
                return None, ()
            suffix = params.unpack.lower()
            chosen = [info for info in files if info.filename.lower().endswith(suffix)]
            if len(chosen) != 1:
                raise DownloadError(
                    f"{url}: oczekiwano dokladnie jednego pliku {params.unpack} "
                    f"w paczce, jest {len(chosen)}"
                )
            if params.unpack_layers:
                _unpack_checked_layers(url, archive, chosen[0], staged, params)
            else:
                unpack_member(archive, chosen[0], staged)
            return chosen[0].filename, ()
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as e:
        # BadZipFile: directory or CRC; zlib.error/EOFError: corrupt or cut
        # compressed data; NotImplementedError: unsupported compression
        raise DownloadError(f"{url}: uszkodzona paczka ZIP: {e}") from e
    except OSError as e:
        raise DownloadError(f"{url}: nie udalo sie odczytac paczki: {e}") from e


def _class_members(
    url: str,
    archive: zipfile.ZipFile,
    files: list[zipfile.ZipInfo],
    pattern: str,
    classes: tuple[str, ...],
    staged: Path,
) -> tuple[str, ...]:
    """The class members of a package (``class_pattern``); with ``classes``
    the ZIP of their members written to ``staged`` and the classes found."""
    regex = re.compile(pattern)
    found: list[tuple[zipfile.ZipInfo, str]] = []
    for info in files:
        match = regex.search(info.filename.rsplit("/", 1)[-1])
        if match is not None:
            found.append((info, match.group("code")))
    if not found:
        raise DownloadError(
            f"{url}: paczka bez plikow klas obiektow ({len(files)} plikow) - to "
            "nie sa oczekiwane dane"
        )
    if not classes:
        return ()
    present = {code for _, code in found}
    kept = tuple(code for code in classes if code in present)
    if not kept:
        raise NoCoverageError(
            f"{url}: paczka nie ma plikow klas {', '.join(classes)} (brak "
            "obiektow tych klas w jednostce)"
        )
    _write_members(archive, [info for info, code in found if code in kept], staged)
    return kept


def _write_members(
    archive: zipfile.ZipFile, members: list[zipfile.ZipInfo], target: Path
) -> None:
    """A new ZIP of ``members`` at ``target`` (atomically): each streamed
    byte for byte (``zipfile`` checks its CRC) with its name, date, attributes
    and compression method, in the given order - the same members give the
    same bytes."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as result:
            for info in members:
                copy = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                copy.compress_type = info.compress_type
                copy.external_attr = info.external_attr
                copy.create_system = info.create_system
                copy.file_size = info.file_size  # ZIP64 decided before writing
                with archive.open(info) as source, result.open(copy, "w") as sink:
                    shutil.copyfileobj(source, sink, _COPY_CHUNK)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def unpack_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path
) -> None:
    """Stream one member to ``target`` atomically (``zipfile`` checks the CRC)."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    try:
        with archive.open(info) as source, open(tmp, "wb") as sink:
            shutil.copyfileobj(source, sink, _COPY_CHUNK)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _unpack_checked_layers(
    url: str,
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    staged: Path,
    params: UnitPackageParams,
) -> None:
    """The GeoPackage member unpacked and checked in a local working directory
    (module docstring), then moved to ``staged``."""
    work = Path(tempfile.mkdtemp(prefix="kartograf-unpack-"))
    try:
        local = work / staged.name
        unpack_member(archive, info, local)
        found = _gpkg_layers(url, local)
        missing = [layer for layer in params.unpack_layers if layer not in found]
        if missing:
            raise DownloadError(
                f"{url}: GeoPackage bez warstw {', '.join(missing)} (sa: "
                f"{', '.join(sorted(found)) or 'brak'}) - to nie sa oczekiwane dane"
            )
        shutil.move(str(local), staged)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _gpkg_layers(url: str, path: Path) -> set[str]:
    """Table names of ``gpkg_contents`` (read-only connection)."""
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT table_name FROM gpkg_contents").fetchall()
    except sqlite3.DatabaseError as e:
        raise DownloadError(f"{url}: plik w paczce nie jest GeoPackage: {e}") from e
    return {str(name) for (name,) in rows}
