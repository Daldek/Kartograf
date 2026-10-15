"""
Engine ``unit_package`` (ADR-042 D1-D2): one ZIP per unit from a URL template.

A collection channel with ``UnitPackageParams`` publishes one package per
administrative unit (powiat, voivodeship) or one national file; each
``PackageVariant`` is one published choice (year, format, LoD) with its URL
template. ``select_variant`` picks the variant of a user's choice without
any network (a missing or unknown value is a ``ValidationError`` naming
the allowed values), ``package_url`` fills the template, ``fetch_package``
downloads the package atomically (``transport.http.download_to``), checks
its bytes against ``Content-Length``, reads the ZIP central directory,
requires the variant's member suffixes and - with ``unpack`` - streams
exactly one member to the result (``zipfile`` checks its CRC). HTTP 404 is
``NoCoverageError`` (the source publishes no package of the unit), every
other failure ``DownloadError``; the package never sits in memory and a
failure leaves no result file.
"""

import os
import shutil
import threading
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

import requests

from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.sources.descriptor import PackageVariant, UnitPackageParams
from kartograf.transport.http import download_to, response_signal

_COPY_CHUNK = 1_048_576


@dataclass(frozen=True)
class PackageFile:
    """A downloaded package: ``path`` = the stored file (the ZIP itself or the
    unpacked member), ``http`` = ``response_signal`` of the download, ``size``
    = bytes of the downloaded ZIP, ``member`` = the unpacked member name."""

    path: Path
    http: dict
    size: int
    member: str | None = None


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


def package_url(variant: PackageVariant, *, teryt: str | None) -> str:
    """URL of the variant's package for a unit: ``{teryt}`` and ``{woj}`` (its
    first two digits); ``teryt=None`` only for a template without tokens."""
    code = teryt or ""
    if not code and "{" in variant.url_template:
        raise ValueError(f"Szablon {variant.url_template} wymaga kodu TERYT")
    return variant.url_template.format(teryt=code, woj=code[:2])


def _reject_documents(url: str):
    """``download_to`` validator: an HTML/XML document instead of a package."""

    def validate(response: requests.Response) -> None:
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "html" in content_type or "xml" in content_type:
            raise DownloadError(
                f"{url}: zrodlo zwrocilo dokument ({content_type}) zamiast paczki ZIP"
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
) -> PackageFile:
    """Download the package ``url`` into ``staged`` (the ZIP or its member).

    Raises
    ------
    NoCoverageError
        HTTP 404: no package of this unit at the source.
    DownloadError
        Any other HTTP/network failure (after the retry policy), a document
        instead of a ZIP, fewer bytes than ``Content-Length``, an unreadable
        ZIP, missing required members, not exactly one member to unpack or a
        member failing its CRC. No result file is left behind.
    """
    staged = Path(staged)
    archive_path = (
        staged if params.unpack is None else staged.with_name(f"{staged.name}.zip")
    )
    signal: dict = {}
    try:
        download_to(
            session,
            url,
            archive_path,
            timeout=timeout,
            description=url,
            validate=_reject_documents(url),
            on_response=lambda response: signal.update(response_signal(response)),
        )
    except DownloadError as e:
        if e.status_code == 404:
            raise NoCoverageError(
                f"Zrodlo nie publikuje paczki {url} (HTTP 404)", status_code=404
            ) from e
        raise
    try:
        size = archive_path.stat().st_size
        expected = signal.get("content_length")
        if expected is not None and expected != size:
            raise DownloadError(
                f"{url}: pobrano {size} z {expected} bajtow (przerwany transfer)"
            )
        member = _check_archive(url, archive_path, staged, params, variant)
    except BaseException:
        staged.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        raise
    if params.unpack is not None:
        archive_path.unlink(missing_ok=True)
    return PackageFile(staged, signal, size, member)


def _check_archive(
    url: str,
    archive_path: Path,
    staged: Path,
    params: UnitPackageParams,
    variant: PackageVariant,
) -> str | None:
    """Central directory, required members and the optional unpacked member."""
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
            if params.unpack is None:
                return None
            suffix = params.unpack.lower()
            chosen = [info for info in files if info.filename.lower().endswith(suffix)]
            if len(chosen) != 1:
                raise DownloadError(
                    f"{url}: oczekiwano dokladnie jednego pliku {params.unpack} "
                    f"w paczce, jest {len(chosen)}"
                )
            _unpack(archive, chosen[0], staged)
            return chosen[0].filename
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as e:
        # BadZipFile: directory or CRC; zlib.error/EOFError: corrupt or cut
        # compressed data; NotImplementedError: unsupported compression
        raise DownloadError(f"{url}: uszkodzona paczka ZIP: {e}") from e
    except OSError as e:
        raise DownloadError(f"{url}: nie udalo sie odczytac paczki: {e}") from e


def _unpack(archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path) -> None:
    """Stream one member to ``target`` atomically (``zipfile`` checks the CRC)."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}_{threading.get_ident()}.tmp")
    try:
        with archive.open(info) as source, open(tmp, "wb") as sink:
            shutil.copyfileobj(source, sink, _COPY_CHUNK)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
