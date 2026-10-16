"""
Engine ``atom_files`` (ADR-042 D12): files listed by a CUZK ATOM feed.

A CUZK ATOM download service has two levels. The service feed has one entry
per dataset (ORTOFOTO: one per SM5 sheet, 16 301 entries, 23.7 MB; ZABAGED:
one dataset), each linking its dataset feed; the entries of a dataset feed
link the files (``rel="alternate"`` with ``length``) and name their CRS
(``category`` ``http://www.opengis.net/def/crs/EPSG/0/<code>``). The file
names carry the release (``WRTO24.<rok>.<arkusz>.zip``,
``ZABAGED-5514-gpkg-<data>.zip``), so the URL of a file exists only in the
feeds - a URL template would have to guess the year.

``atom_index`` reads the service feed into ``key -> AtomEntry``:
``AtomFilesParams.entry_pattern`` is searched in the dataset feed id of each
entry (entries it does not match are not data of the channel); its named
group ``sheet`` is the key, without it the feed has exactly one dataset (key
``""``). The feed is parsed as a stream (``iterparse``, every parsed entry
dropped from the tree) and the index is kept in the metadata cache with the
feed ``ETag``: within the cache TTL no request is made; an older index or
``refresh=True`` sends a conditional GET (``If-None-Match``) and ``304``
keeps the stored index. ``resolve_atom_file`` reads the dataset feed of one
key - always fresh: it is small and its entry carries the edition - and picks
the file by its CRS category. A key missing from a cached index, or a
dataset feed answering 404, refreshes the index once (a stale index must not
hide a new release). The edition label is the date of the file entry's
``updated``, prefixed by the ``year`` group when the pattern has one
(``2024_2025-02-06``, ``2026-10-04``): the ``metadata`` freshness signal of
the versioned store (D29).

``fetch_atom_file`` downloads a file atomically and checks its size against
the feed ``length`` and ``Content-Length``; ``unpack_members`` stores the
members of ``AtomFilesParams.members`` under ``<stem><stored suffix>``.
Failures: an unknown key = ``NoCoverageError``; HTML or an error page instead
of a feed, an entry without exactly one file link, an ambiguous file or a
cut transfer = ``DownloadError``; a CRS choice the channel does not publish
= ``ValidationError`` (no network).
"""

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.sources.descriptor import AtomFilesParams
from kartograf.sources.edition import edition_label
from kartograf.transport.http import download_to, get_with_retry, response_signal
from kartograf.transport.unit_package import reject_documents, unpack_member

logger = logging.getLogger(__name__)

# Read timeouts (s): the service feed (ORTOFOTO 23.7 MB answered in 3.2 s on
# 2026-10-15, but GUGiK ATOM feeds had 120 s timeouts - STANDARDS 13.4) and
# one dataset feed (about 1.4 KB).
SERVICE_FEED_TIMEOUT = 120
DATASET_FEED_TIMEOUT = 60

_ATOM = "{http://www.w3.org/2005/Atom}"
_FEED = f"{_ATOM}feed"
_ENTRY = f"{_ATOM}entry"
_CRS_TERM = re.compile(r"https?://www\.opengis\.net/def/crs/EPSG/[^/]+/([0-9]+)")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DIGITS = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class AtomEntry:
    """One dataset of a service feed: ``key`` (the ``sheet`` group or
    ``""``), the dataset feed URL, its ``updated``, the named groups of
    ``entry_pattern`` and the CRSs of its files (``EPSG:<code>``)."""

    key: str
    dataset_feed: str
    updated: str
    groups: Mapping[str, str]
    crs: tuple[str, ...]


@dataclass(frozen=True)
class AtomFile:
    """One file of a dataset feed.

    ``length`` in bytes from the feed (``None`` when absent), ``updated`` of
    its entry, ``edition`` = the version label of its release, ``crs`` =
    its CRS category (``EPSG:<code>``), ``dataset_feed`` = the feed it was
    read from, ``groups`` = the named groups of ``entry_pattern`` in the id
    of that feed (``year``, ``sheet``).
    """

    url: str
    length: int | None
    updated: str
    edition: str
    crs: str | None
    dataset_feed: str
    groups: Mapping[str, str]


@dataclass(frozen=True)
class UnpackedMember:
    """A ZIP member stored as ``path``; ``member`` = its name in the ZIP."""

    path: Path
    member: str


def atom_segment_tokens(params: AtomFilesParams, crs: str | None) -> tuple[str, ...]:
    """Content tokens of the storage segment: ``segment_tokens`` plus the
    EPSG number of the chosen file when the dataset has several CRSs."""
    if len(params.crs) > 1:
        assert crs is not None  # check_atom_crs
        return (*params.segment_tokens, crs.split(":", 1)[1])
    return params.segment_tokens


def check_atom_crs(params: AtomFilesParams, crs: str | None) -> None:
    """The CRS choice of a file (no network).

    Raises
    ------
    ValidationError
        A dataset with several CRSs without ``crs``, a ``crs`` it does not
        publish, or a ``crs`` given for a dataset with one file.
    """
    if not params.crs:
        if crs is not None:
            raise ValidationError(
                f"--horizontal-crs {crs}: zbior ma jeden plik (uklad wynika ze zrodla)"
            )
        return
    if crs is None:
        raise ValidationError(
            f"--horizontal-crs wymagane (plik publikowany w kilku ukladach): "
            f"{', '.join(params.crs)}"
        )
    if crs not in params.crs:
        raise ValidationError(
            f"--horizontal-crs {crs}: zbior nie jest publikowany w tym ukladzie; "
            f"dostepne: {', '.join(params.crs)}"
        )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _crs_of(element: ET.Element) -> tuple[str, ...]:
    """EPSG codes of the CRS categories of an entry (other categories skipped)."""
    codes = []
    for category in element.findall(f"{_ATOM}category"):
        match = _CRS_TERM.fullmatch((category.get("term") or "").strip())
        if match:
            codes.append(f"EPSG:{int(match[1])}")
    return tuple(codes)


def _alternate(element: ET.Element, context: str) -> ET.Element:
    """The one ``rel="alternate"`` link of an entry."""
    links = [
        link
        for link in element.findall(f"{_ATOM}link")
        if link.get("rel") == "alternate" and (link.get("href") or "").strip()
    ]
    if len(links) != 1:
        raise DownloadError(
            f"{context}: wpis {element.findtext(f'{_ATOM}id')!r} ma {len(links)} "
            "linkow rel=alternate, oczekiwano jednego"
        )
    return links[0]


def _updated(element: ET.Element, context: str) -> str:
    updated = (element.findtext(f"{_ATOM}updated") or "").strip()
    if not _DATE.match(updated):
        raise DownloadError(
            f"{context}: wpis {element.findtext(f'{_ATOM}id')!r} bez daty "
            f"<updated> ({updated!r})"
        )
    return updated


def _not_a_feed(context: str, content_type: str, detail: str) -> DownloadError:
    return DownloadError(
        f"{context}: odpowiedz nie jest feedem ATOM ({content_type or 'brak typu'}): "
        f"{detail}"
    )


def _parse_service(
    content: bytes, params: AtomFilesParams, context: str, content_type: str
) -> dict[str, AtomEntry]:
    """Index of a service feed, parsed as a stream (entries dropped)."""
    pattern = re.compile(params.entry_pattern)
    entries: dict[str, AtomEntry] = {}
    try:
        events = ET.iterparse(io.BytesIO(content), events=("start", "end"))
        _, root = next(events)
        if root.tag != _FEED:
            raise _not_a_feed(context, content_type, f"element {_local(root.tag)}")
        for event, element in events:
            if event != "end" or element.tag != _ENTRY:
                continue
            ident = (element.findtext(f"{_ATOM}id") or "").strip()
            match = pattern.search(ident)
            if match is not None:
                groups = {k: v for k, v in match.groupdict().items() if v is not None}
                key = groups.get("sheet", "")
                if key in entries:
                    raise DownloadError(
                        f"{context}: dwa zbiory dla {key or 'jedynego zbioru'} "
                        f"({entries[key].dataset_feed}, {ident})"
                    )
                entries[key] = AtomEntry(
                    key=key,
                    dataset_feed=str(_alternate(element, context).get("href")).strip(),
                    updated=_updated(element, context),
                    groups=groups,
                    crs=_crs_of(element),
                )
            root.remove(element)  # bounded memory: drop parsed entries
    except (ET.ParseError, StopIteration) as e:
        raise _not_a_feed(context, content_type, str(e)) from e
    if not entries:
        raise DownloadError(
            f"{context}: feed nie ma zbiorow pasujacych do {params.entry_pattern!r}"
        )
    if "sheet" not in pattern.groupindex and len(entries) != 1:
        raise DownloadError(
            f"{context}: oczekiwano jednego zbioru, jest {len(entries)}"
        )
    return entries


def _payload(index: dict[str, AtomEntry]) -> dict:
    return {
        key: {
            "dataset_feed": entry.dataset_feed,
            "updated": entry.updated,
            "groups": dict(entry.groups),
            "crs": list(entry.crs),
        }
        for key, entry in index.items()
    }


def _from_payload(payload: dict) -> dict[str, AtomEntry]:
    return {
        key: AtomEntry(
            key=key,
            dataset_feed=value["dataset_feed"],
            updated=value["updated"],
            groups=dict(value["groups"]),
            crs=tuple(value["crs"]),
        )
        for key, value in payload.items()
    }


def _cache_key(params: AtomFilesParams) -> str:
    """The cache entry of an index: the feed and the pattern that keyed it."""
    return f"{params.service_feed}|{params.entry_pattern}"


def _index(
    session: requests.Session,
    params: AtomFilesParams,
    *,
    cache: MetadataCache | None,
    refresh: bool,
    timeout: float,
) -> tuple[dict[str, AtomEntry], bool]:
    """The index and whether it was confirmed by the service in this call."""
    key = _cache_key(params)
    stored = cache.get_atom_entries(key) if cache is not None else None
    if stored is not None and stored[2] and not refresh:
        return _from_payload(stored[1]), False
    etag = stored[0] if stored is not None else None
    context = f"ATOM {params.service_feed}"
    response = get_with_retry(
        session,
        params.service_feed,
        timeout=timeout,
        description=context,
        headers={"If-None-Match": etag} if etag else None,
    )
    if response.status_code == 304:
        if stored is None or not etag:
            raise DownloadError(f"{context}: HTTP 304 bez zapytania warunkowego")
        logger.debug("%s: 304, indeks bez zmian", context)
        if cache is not None:
            cache.set_atom_entries(key, etag, stored[1])
        return _from_payload(stored[1]), True
    content_type = str(response.headers.get("Content-Type", ""))
    index = _parse_service(response.content, params, context, content_type)
    new_etag = response.headers.get("ETag")
    if cache is not None:
        cache.set_atom_entries(
            key, new_etag if isinstance(new_etag, str) else None, _payload(index)
        )
    logger.info("%s: %s zbiorow", context, len(index))
    return index, True


def atom_index(
    session: requests.Session,
    params: AtomFilesParams,
    *,
    cache: MetadataCache | None,
    refresh: bool = False,
    timeout: float = SERVICE_FEED_TIMEOUT,
) -> dict[str, AtomEntry]:
    """Datasets of the service feed by key (module docstring).

    ``cache``: the index store (``None``: the feed is read on every call);
    ``refresh``: revalidate a stored index even within its TTL.

    Raises
    ------
    DownloadError
        HTTP/network failure, a document that is not an ATOM feed, no
        matching dataset, two datasets of one key, an entry without exactly
        one dataset feed link or without ``updated``.
    """
    return _index(session, params, cache=cache, refresh=refresh, timeout=timeout)[0]


def _dataset_entries(
    session: requests.Session, url: str, timeout: float
) -> list[ET.Element]:
    """Entries of a dataset feed (``DownloadError`` with ``status_code``)."""
    context = f"ATOM {url}"
    response = get_with_retry(session, url, timeout=timeout, description=context)
    content_type = str(response.headers.get("Content-Type", ""))
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        raise _not_a_feed(context, content_type, str(e)) from e
    if root.tag != _FEED:
        raise _not_a_feed(context, content_type, f"element {_local(root.tag)}")
    return root.findall(_ENTRY)


def _edition(entry: AtomEntry, updated: str, context: str) -> str:
    date = updated[:10]
    year = entry.groups.get("year")
    return edition_label(f"{year}_{date}" if year else date, what=context)


def _select(
    entries: list[ET.Element], entry: AtomEntry, crs: str | None, context: str
) -> AtomFile:
    """The file of a dataset: the entry of the CRS category (or the only one)."""
    found = [(element, _crs_of(element)) for element in entries]
    if crs is not None:
        chosen = [element for element, codes in found if crs in codes]
        if not chosen:
            published = sorted({code for _, codes in found for code in codes})
            raise DownloadError(
                f"{context}: brak pliku w ukladzie {crs} (feed: "
                f"{', '.join(published) or 'bez kategorii ukladu'})"
            )
    else:
        chosen = [element for element, _ in found]
    if len(chosen) != 1:
        raise DownloadError(
            f"{context}: {len(chosen)} plikow zbioru bez rozstrzygniecia "
            "(oczekiwano jednego)"
        )
    (element,) = chosen
    link = _alternate(element, context)
    length = (link.get("length") or "").strip()
    updated = _updated(element, context)
    codes = _crs_of(element)
    return AtomFile(
        url=str(link.get("href")).strip(),
        length=int(length) if _DIGITS.fullmatch(length) else None,
        updated=updated,
        edition=_edition(entry, updated, context),
        crs=crs if crs is not None else (codes[0] if len(codes) == 1 else None),
        dataset_feed=entry.dataset_feed,
        groups=entry.groups,
    )


def resolve_atom_file(
    session: requests.Session,
    params: AtomFilesParams,
    *,
    key: str,
    crs: str | None,
    cache: MetadataCache | None,
    refresh: bool = False,
    timeout: float = DATASET_FEED_TIMEOUT,
) -> AtomFile:
    """The file of dataset ``key`` (``""``: the only dataset) in ``crs``.

    The index comes from ``atom_index`` (cache, ``refresh``); the dataset
    feed is always read. A key missing from a cached index or a dataset
    feed answering 404 refreshes the index once.

    Raises
    ------
    ValidationError
        ``crs`` not allowed for the channel (``check_atom_crs``).
    NoCoverageError
        No dataset ``key`` in the service feed (e.g. a sheet without
        orthophoto).
    DownloadError
        Feed failures (``atom_index``), a dataset feed that is not a feed,
        no file in ``crs``, several files without a choice, an entry without
        exactly one file link.
    """
    check_atom_crs(params, crs)
    index, confirmed = _index(
        session, params, cache=cache, refresh=refresh, timeout=SERVICE_FEED_TIMEOUT
    )
    if key not in index and not confirmed:
        index, confirmed = _index(
            session, params, cache=cache, refresh=True, timeout=SERVICE_FEED_TIMEOUT
        )
    entry = index.get(key)
    if entry is None:
        raise NoCoverageError(
            f"ATOM {params.service_feed}: brak zbioru {key!r} w feedzie uslugi"
        )
    context = f"ATOM {entry.dataset_feed}"
    try:
        entries = _dataset_entries(session, entry.dataset_feed, timeout)
    except DownloadError as e:
        if e.status_code != 404 or confirmed:
            raise
        index, _ = _index(
            session, params, cache=cache, refresh=True, timeout=SERVICE_FEED_TIMEOUT
        )
        renewed = index.get(key)
        if renewed is None:
            raise NoCoverageError(
                f"ATOM {params.service_feed}: brak zbioru {key!r} w feedzie uslugi"
            ) from e
        entry = renewed
        context = f"ATOM {entry.dataset_feed}"
        entries = _dataset_entries(session, entry.dataset_feed, timeout)
    return _select(entries, entry, crs, context)


def fetch_atom_file(
    session: requests.Session, file: AtomFile, staged: Path, *, timeout: float
) -> dict:
    """Download ``file`` into ``staged`` (atomically); its HTTP signal.

    Raises
    ------
    DownloadError
        HTTP/network failure (after the retry policy), a document instead of
        the file, or a size other than the feed ``length`` or
        ``Content-Length`` (no file is left).
    """
    staged = Path(staged)
    signal: dict = {}
    download_to(
        session,
        file.url,
        staged,
        timeout=timeout,
        description=file.url,
        validate=reject_documents(file.url),
        on_response=lambda response: signal.update(response_signal(response)),
    )
    size = staged.stat().st_size
    for source, expected in (
        ("feed ATOM (length)", file.length),
        ("Content-Length", signal.get("content_length")),
    ):
        if expected is not None and expected != size:
            staged.unlink(missing_ok=True)
            raise DownloadError(
                f"{file.url}: pobrano {size} z {expected} bajtow wg {source} "
                "(przerwany transfer)"
            )
    return signal


def unpack_members(
    archive: Path, params: AtomFilesParams, target_dir: Path, stem: str, *, url: str
) -> dict[str, UnpackedMember]:
    """Members of ``params.members`` from a downloaded ZIP as
    ``<target_dir>/<stem><stored suffix>``; stored suffix -> the stored file
    and its member name.

    Every member suffix must match exactly one ZIP member (the longest
    suffix wins: ``.TM33N.jgw`` before ``.jgw``); other members are left in
    the ZIP. Bytes are copied 1:1 (``zipfile`` checks the CRC).

    Raises
    ------
    DownloadError
        An unreadable ZIP, a suffix matching no member or several members.
    """
    ordered = sorted(params.members, key=lambda pair: len(pair[0]), reverse=True)
    found: dict[str, list[zipfile.ZipInfo]] = {stored: [] for _, stored in ordered}
    paths: dict[str, UnpackedMember] = {}
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.lower()
                for member, stored in ordered:
                    if name.endswith(member.lower()):
                        found[stored].append(info)
                        break
            wrong = {s: len(infos) for s, infos in found.items() if len(infos) != 1}
            if wrong:
                raise DownloadError(
                    f"{url}: paczka bez jednoznacznych plikow "
                    + ", ".join(f"{s} ({n})" for s, n in wrong.items())
                    + f" - czlony: {', '.join(i.filename for i in zf.infolist())}"
                )
            for stored, (info,) in found.items():
                target = Path(target_dir) / f"{stem}{stored}"
                unpack_member(zf, info, target)
                paths[stored] = UnpackedMember(target, info.filename)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as e:
        for unpacked in paths.values():
            unpacked.path.unlink(missing_ok=True)
        raise DownloadError(f"{url}: uszkodzona paczka ZIP: {e}") from e
    except BaseException:
        for unpacked in paths.values():
            unpacked.path.unlink(missing_ok=True)
        raise
    return paths
