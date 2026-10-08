# Magazyn wersjonowany — plan 1/3: fundament i arkusze PL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wersje identyfikowane trescia (`versions/<etykieta>_<sha8>/`) z niezmiennym sidecarem i trybami `update` (domyslny / `check` / `upgrade` / `force`) oraz planem aktualizacji `kartograf-plan/1` dla arkuszy PL (NMT, NMPT, orto) pobieranych przez `DownloadManager` — w bibliotece i w CLI `kartograf download`.

**Architecture:** Nowy modul `kartograf/download/versions.py` (tozsamosc wersji, zapis przez katalog `.incoming` + `os.replace`, lista waznych wersji). `download/links.py` zostaje mechanizmem dowiazania standardowego (hardlink/kopia, nigdy wstecz), z kluczem wersji zamiast klucza kampanii. `DownloadManager` zastepuje `skip_existing` parametrem `update`; kampania GUGiK = wersja z etykieta `<data>_<id>`. Nowy modul `kartograf/download/updates.py` (plan aktualizacji: `check_updates`, `upgrade`). CLI dostaje `--check-updates` / `--upgrade` / `--force` (grupa wykluczajaca) i `--plan`.

**Tech Stack:** Python 3.12, `hashlib`, `dataclasses`, `pytest` (offline, `conftest` blokuje gniazda), `argparse`.

**Spec:** `docs/superpowers/specs/2026-10-08-versioned-store-design.md` (zaakceptowany 2026-10-08).

**Kolejne plany (osobne dokumenty, pisane po wykonaniu tego):**
- plan 2/3: LAZ, CZ (DMR 5G/4G), wycinki `bbox/` (PL `--target-crs`, CZ) — wersje, tryby `update`, sha256 wejsc;
- plan 3/3: land cover (BDOT10k, CORINE, SoilGrids) i HSG w ukladzie `data/` + pelna aktualizacja dokumentacji i E2E calosci.
Galaz `feat/versioned-store` jest mergowana do `develop` dopiero po planie 3/3.

## Global Constraints

- Python wylacznie z `.venv`: `.venv/bin/python -m pytest ...`, `.venv/bin/python -m ruff ...`, `.venv/bin/python -m mypy ...`.
- Testy offline: `-m "not live"`. Brama przed kazdym commitem: `.venv/bin/python -m pytest tests/ -m "not live" -q` zielone, `.venv/bin/python -m ruff check .` i `.venv/bin/python -m ruff format --check .` czyste, `.venv/bin/python -m mypy kartograf/ tests/` bez bledow.
- Commity: Conventional Commits z opisem po polsku; docstringi i komentarze po angielsku; dokumentacja po polsku. Stopka commita: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Przed kazdym commitem kontrola nazw zakazanych w repo (wzorce poza repo, w `$HOME/.config/kartograf/forbidden-patterns.txt`): commit wykonuj WYLACZNIE w postaci `! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit ...` — trafienie przerywa commit. Brak pliku wzorcow = zatrzymaj sie i zapytaj koordynatora. Tresci wzorcow nie wolno wpisywac do zadnego pliku repo ani komunikatu commita.
- Nowe identyfikatory w kodzie, API, sidecarze i planie aktualizacji wylacznie po angielsku (ADR-031). Komunikaty CLI jak dzis (polskie bez znakow diakrytycznych w kodzie).
- Katalog wersji: `versions` (stala `VERSIONS_DIR`); katalog roboczy: `versions/.incoming/<pid>_<tid>/`.
- Nazwa katalogu wersji: `<etykieta>_<sha8>`, `sha8` = pierwsze 8 znakow szesnastkowych sha256 pliku danych.
- Etykieta kampanii GUGiK: `CampaignRef.dirname` (`<aktualnosc>_<id>`), `label_source="campaign"`; bez kampanii: data pobrania UTC `RRRR-MM-DD`, `label_source="downloaded"`.
- Sidecar wersji jest pisany raz: pola `sha256` (gorny poziom) i `extra.version = {"label", "label_source"}`; `extra.parent_requests` nie istnieje.
- Schemat planu aktualizacji: `"kartograf-plan/1"`.
- Tryby: `UpdateMode = Literal["check", "upgrade", "force"]`, brak trybu = `None`.
- Bez migracji `kampanie/` (D10); CLI drukuje raz `Info:` o starym katalogu.
- Dane testow na zywo tylko poza repo i poza `/tmp`, z jawnym `--output`; CLI z korzenia repo.

## Review Focus

1. **Ponowne pobranie tej samej tresci innego dnia (tor bez kampanii)** — etykieta `downloaded` zmienia sie z data, a wersja ma byc ta sama (dedupe po sha256 wsrod WSZYSTKICH wersji pliku, nie tylko w katalogu o tej samej etykiecie). Test: Task 2 `test_commit_same_content_other_label_is_unchanged`.
2. **Przerwany zapis: dane bez sidecara w katalogu wersji** — wersja niewazna (pomijana z `Warning:`), a nastepne pobranie tej samej tresci ja naprawia, zamiast zglaszac kolizje. Test: Task 2 `test_commit_repairs_version_without_sidecar`.
3. **Pozostalosci `.incoming/` po przerwaniu** — nie moga byc brane za wersje ani psuc `list_versions`. Test: Task 2 `test_list_versions_ignores_incoming`.
4. **Domyslne uruchomienie przy awarii skorowidza dla `--campaigns all` i `--min-year`** — lokalna wersja + `unverified` (dzis I-1 dzialalo tylko dla `newest` bez `min_year`). Test: Task 4 `test_default_transport_failure_any_strategy_uses_local`.
5. **Plan wykonany na innym magazynie / plan z nieznanym schematem** — `ValidationError` przed jakimkolwiek pobraniem. Test: Task 6 `test_upgrade_rejects_foreign_store` i `test_plan_from_json_rejects_unknown_schema`.

---

## Mapa plikow

| Plik | Odpowiedzialnosc |
|---|---|
| `kartograf/download/versions.py` (NOWY) | `VersionRef`, `LocalVersion`, `VersionCommit`, `sha256_file`, `downloaded_label`, `incoming_path`, `commit_version`, `list_versions`, `newest_version` |
| `kartograf/download/links.py` | dowiazanie standardowe; `version_key_of` (z sidecara: kampania albo `(data etykiety, downloaded_at, sha256)`; fallback z nazwy katalogu `versions/`) |
| `kartograf/download/campaigns.py` | `CampaignRef` i weryfikacja formatu; bez `CAMPAIGNS_DIR` |
| `kartograf/download/storage.py` | `version_parts`; `list_files(versions=...)`; bez `get_campaign_path` |
| `kartograf/sources/sidecar.py` | `ResultMetadata.sha256`; `emit_sidecar(sha256=, version=)` |
| `kartograf/download/manager.py` | `UpdateMode`, `update=` zamiast `skip_existing`, tor kampanii i tor bez kampanii na wersjach, `check_sheet`, bez `_note_reuse` |
| `kartograf/download/updates.py` (NOWY) | `PlanItem`, `UpdatePlan` (JSON `kartograf-plan/1`), `check_updates`, `upgrade`, `UpgradeReport` |
| `kartograf/download/cutout.py` | wywolanie `download_sheets(update=...)` (pelne wersjonowanie wycinka: plan 2/3) |
| `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py` | flagi, mapowanie na `update`, linie statusu, raport `check`, `--plan`, `Info:` o `kampanie/`, odrzucenie `check`/`upgrade` dla torow z planu 2/3 |
| `kartograf/__init__.py` | eksporty `VersionRef`, `UpdatePlan`, `PlanItem`, `UpgradeReport`, `check_updates`, `upgrade` |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, spec | ADR-032, wpisy BREAKING, errata specu |

---

### Task 1: Errata specu (decyzje implementacyjne)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-08-versioned-store-design.md` (sekcje 3.1, 5)

**Interfaces:**
- Consumes: —
- Produces: spec zgodny z planem (kolejnosc zapisu, liczenie sha256, moduly)

- [ ] **Step 1: Popraw sekcje 3.1 (kroki zapisu)**

Zastap liste "1.-5." w sekcji 3.1 tym tekstem:

```markdown
1. Provider pobiera plik do katalogu roboczego w tym samym segmencie:
   `<segment>/versions/.incoming/<pid>_<tid>/<nazwa>` (ten sam system
   plikow, wiec `os.replace` jest atomowe).
2. sha256 liczone z pliku po pobraniu (`versions.sha256_file`) — jedna
   sciezka dla plikow pobranych (takze rozpakowanych przez `save=`)
   i dla produktow pochodnych, ktore nie przechodza przez HTTP.
3. Jesli jakakolwiek WAZNA wersja tego pliku (dowolna etykieta) ma to samo
   sha256: plik roboczy usuwany, wynik "bez zmian" (`unchanged`).
4. Jesli katalog `<etykieta>_<sha8>` istnieje, a jego sidecar ma INNE pelne
   sha256 (kolizja prefiksu): `DownloadError`, bez zapisu.
5. W przeciwnym razie: `os.replace` pliku roboczego do katalogu wersji,
   potem obowiazkowy sidecar wersji (zapis atomowy). Porazka sidecara =
   plik danych usuwany, `DownloadError`. Kolejnosc dane -> sidecar, bo
   sidecar czyta plik (nodata z naglowka ASC, uklad arkusza PL-2000).
6. Przestawienie dowiazania standardowego (sekcja 3.2).
```

oraz zdanie "Waznosc wersji" uzupelnij o: "Wersja z danymi bez sidecara
(przerwanie miedzy krokami 5) jest naprawiana przy nastepnym zapisie tej
samej tresci (sidecar dopisywany, bez kolizji)."

- [ ] **Step 2: Popraw tabele sekcji 5**

W wierszu `download/versions.py` zamien opis na: "`VersionRef`, etykiety, `commit_version`, `list_versions`, `newest_version`, `incoming_path`"; dodaj wiersz `download/links.py` — "zostaje: dowiazanie hardlink/kopia, nigdy wstecz; `version_key_of` zamiast `campaign_key_of`"; w wierszu `transport/http.py` zamien opis na: "bez zmian w planie 1/3 (sha256 z pliku po pobraniu); zwrot naglowkow `ETag`/`Last-Modified` dla sygnalu `http` — plan 2/3".

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-10-08-versioned-store-design.md
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "docs(spec): errata magazynu wersjonowanego — kolejnosc zapisu i sha256 z pliku

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Modul `versions.py` (tozsamosc, zapis, lista wersji)

**Files:**
- Create: `kartograf/download/versions.py`
- Test: `tests/test_versions.py`

**Interfaces:**
- Consumes: `kartograf.exceptions.DownloadError`
- Produces:
  - `VERSIONS_DIR: str = "versions"`, `INCOMING_DIR: str = ".incoming"`
  - `LabelSource = Literal["campaign", "edition", "downloaded"]`
  - `sha256_file(path: Path) -> str`
  - `downloaded_label(now: datetime | None = None) -> str`
  - `@dataclass(frozen=True) VersionRef(label: str, label_source: LabelSource, sha256: str)` z `sha8`, `dirname`, `to_extra() -> dict`
  - `@dataclass(frozen=True) LocalVersion(path: Path, version: VersionRef, downloaded_at: str, key: tuple[str, str, str])`
  - `@dataclass(frozen=True) VersionCommit(path: Path, version: VersionRef, status: Literal["new", "unchanged"])`
  - `incoming_path(segment_root: Path, name: str) -> Path`
  - `list_versions(segment_root: Path, rel: PurePath) -> list[LocalVersion]`
  - `newest_version(versions: list[LocalVersion]) -> LocalVersion | None`
  - `commit_version(staged: Path, segment_root: Path, rel: PurePath, *, label: str, label_source: LabelSource, write_sidecar: Callable[[Path, VersionRef], None]) -> VersionCommit`

- [ ] **Step 1: Napisz testy**

```python
"""Versioned store core (ADR-032): identity, commit, listing."""

import json
from datetime import UTC, datetime
from pathlib import Path, PurePath

import pytest

from kartograf.download.versions import (
    INCOMING_DIR,
    VERSIONS_DIR,
    VersionRef,
    commit_version,
    downloaded_label,
    incoming_path,
    list_versions,
    newest_version,
    sha256_file,
)
from kartograf.exceptions import DownloadError

REL = PurePath("N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc")


def _sidecar_writer(extra: dict | None = None, downloaded_at: str = "2026-10-08T10:00:00+00:00"):
    def write(path: Path, ref: VersionRef) -> None:
        meta = {
            "sha256": ref.sha256,
            "downloaded_at": downloaded_at,
            "extra": {"version": ref.to_extra(), **(extra or {})},
        }
        sidecar = path.parent / f"{path.name}.meta.json"
        sidecar.write_text(json.dumps(meta), encoding="utf-8")

    return write


def _stage(root: Path, content: bytes) -> Path:
    staged = incoming_path(root, REL.name)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(content)
    return staged


def test_sha256_file(tmp_path):
    f = tmp_path / "a"
    f.write_bytes(b"abc")
    assert sha256_file(f) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_downloaded_label_is_utc_date():
    assert downloaded_label(datetime(2026, 10, 8, 23, 59, tzinfo=UTC)) == "2026-10-08"


def test_version_ref_dirname_and_extra():
    ref = VersionRef("2022-05-10_83233", "campaign", "ab" * 32)
    assert ref.sha8 == "abababab"
    assert ref.dirname == "2022-05-10_83233_abababab"
    assert ref.to_extra() == {"label": "2022-05-10_83233", "label_source": "campaign"}


def test_incoming_path_is_inside_versions(tmp_path):
    p = incoming_path(tmp_path, "x.asc")
    assert p.parts[-4:-2] == (VERSIONS_DIR, INCOMING_DIR)
    assert p.name == "x.asc"


def test_commit_new_version(tmp_path):
    staged = _stage(tmp_path, b"v1")
    c = commit_version(staged, tmp_path, REL, label="2026-10-08",
                       label_source="downloaded", write_sidecar=_sidecar_writer())
    assert c.status == "new"
    assert c.path == tmp_path / VERSIONS_DIR / c.version.dirname / REL
    assert c.path.read_bytes() == b"v1"
    assert not staged.exists()
    assert not (tmp_path / VERSIONS_DIR / INCOMING_DIR).exists()


def test_commit_same_content_same_label_is_unchanged(tmp_path):
    w = _sidecar_writer()
    first = commit_version(_stage(tmp_path, b"v1"), tmp_path, REL, label="L",
                           label_source="downloaded", write_sidecar=w)
    staged = _stage(tmp_path, b"v1")
    again = commit_version(staged, tmp_path, REL, label="L",
                           label_source="downloaded", write_sidecar=w)
    assert again.status == "unchanged"
    assert again.path == first.path
    assert not staged.exists()


def test_commit_same_content_other_label_is_unchanged(tmp_path):
    w = _sidecar_writer()
    first = commit_version(_stage(tmp_path, b"v1"), tmp_path, REL,
                           label="2026-10-08", label_source="downloaded", write_sidecar=w)
    again = commit_version(_stage(tmp_path, b"v1"), tmp_path, REL,
                           label="2026-10-09", label_source="downloaded", write_sidecar=w)
    assert again.status == "unchanged"
    assert again.path == first.path
    assert len(list_versions(tmp_path, REL)) == 1


def test_commit_other_content_is_new_version(tmp_path):
    w = _sidecar_writer()
    commit_version(_stage(tmp_path, b"v1"), tmp_path, REL, label="L",
                   label_source="downloaded", write_sidecar=w)
    second = commit_version(_stage(tmp_path, b"v2"), tmp_path, REL, label="L",
                            label_source="downloaded", write_sidecar=w)
    assert second.status == "new"
    assert len(list_versions(tmp_path, REL)) == 2


def test_commit_sha8_collision_raises(tmp_path):
    staged = _stage(tmp_path, b"v1")
    sha = sha256_file(staged)
    clash = tmp_path / VERSIONS_DIR / f"L_{sha[:8]}" / REL
    clash.parent.mkdir(parents=True)
    clash.write_bytes(b"other")
    (clash.parent / f"{clash.name}.meta.json").write_text(
        json.dumps({"sha256": sha[:8] + "0" * 56}), encoding="utf-8"
    )
    with pytest.raises(DownloadError, match="kolizja"):
        commit_version(staged, tmp_path, REL, label="L",
                       label_source="downloaded", write_sidecar=_sidecar_writer())
    assert clash.read_bytes() == b"other"


def test_commit_repairs_version_without_sidecar(tmp_path):
    staged = _stage(tmp_path, b"v1")
    sha = sha256_file(staged)
    broken = tmp_path / VERSIONS_DIR / f"L_{sha[:8]}" / REL
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"v1")  # data written, sidecar never written
    c = commit_version(staged, tmp_path, REL, label="L",
                       label_source="downloaded", write_sidecar=_sidecar_writer())
    assert c.status == "new"
    assert (broken.parent / f"{broken.name}.meta.json").is_file()
    assert len(list_versions(tmp_path, REL)) == 1


def test_commit_sidecar_failure_removes_data(tmp_path):
    def failing(path: Path, ref: VersionRef) -> None:
        raise DownloadError("sidecar")

    staged = _stage(tmp_path, b"v1")
    with pytest.raises(DownloadError, match="sidecar"):
        commit_version(staged, tmp_path, REL, label="L",
                       label_source="downloaded", write_sidecar=failing)
    assert list_versions(tmp_path, REL) == []
    assert not any((tmp_path / VERSIONS_DIR).rglob("*.asc"))


def test_list_versions_skips_incomplete_with_warning(tmp_path, caplog):
    d = tmp_path / VERSIONS_DIR / "L_0123abcd" / REL
    d.parent.mkdir(parents=True)
    d.write_bytes(b"x")
    assert list_versions(tmp_path, REL) == []
    assert "niekompletna" in caplog.text


def test_list_versions_ignores_incoming(tmp_path):
    staged = _stage(tmp_path, b"left over")
    (staged.parent / f"{staged.name}.meta.json").write_text("{}", encoding="utf-8")
    assert list_versions(tmp_path, REL) == []


def test_list_versions_reads_ref_and_key(tmp_path):
    w = _sidecar_writer(downloaded_at="2026-10-08T10:00:00+00:00")
    c = commit_version(_stage(tmp_path, b"v1"), tmp_path, REL, label="2026-10-08",
                       label_source="downloaded", write_sidecar=w)
    [v] = list_versions(tmp_path, REL)
    assert v.path == c.path
    assert v.version == c.version
    assert v.key == ("2026-10-08", "2026-10-08T10:00:00+00:00", c.version.sha256)


def test_campaign_key_from_sidecar(tmp_path):
    w = _sidecar_writer(extra={
        "campaign": {"date": "2022-05-10", "pzgik_date": "2022-06-01"},
        "source": {"url": "https://x/83233_1_N.asc"},
    })
    commit_version(_stage(tmp_path, b"v1"), tmp_path, REL, label="2022-05-10_83233",
                   label_source="campaign", write_sidecar=w)
    [v] = list_versions(tmp_path, REL)
    assert v.key == ("2022-05-10", "2022-06-01", "https://x/83233_1_N.asc")


def test_newest_version_by_key(tmp_path):
    commit_version(_stage(tmp_path, b"old"), tmp_path, REL, label="2026-01-01",
                   label_source="downloaded",
                   write_sidecar=_sidecar_writer(downloaded_at="2026-01-01T00:00:00+00:00"))
    commit_version(_stage(tmp_path, b"new"), tmp_path, REL, label="2026-10-08",
                   label_source="downloaded",
                   write_sidecar=_sidecar_writer(downloaded_at="2026-10-08T00:00:00+00:00"))
    newest = newest_version(list_versions(tmp_path, REL))
    assert newest is not None and newest.path.read_bytes() == b"new"
    assert newest_version([]) is None
```

- [ ] **Step 2: Uruchom testy — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_versions.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kartograf.download.versions'`

- [ ] **Step 3: Implementacja**

```python
"""
Versioned store (ADR-032): immutable versions identified by content.

A version of the logical file ``<segment>/<hierarchy>/<name>`` lives in
``<segment>/versions/<label>_<sha8>/<hierarchy>/<name>`` next to its
mandatory sidecar; the standard path is a hardlink (or a copy) of the
newest version (``download/links.py``). A version is VALID only when both
the data file and its sidecar exist. Providers download into
``versions/.incoming/<pid>_<tid>/`` (same filesystem as the versions, so
``os.replace`` is atomic) and ``commit_version`` moves the file into place.
No locks: two processes committing the same content end in the same
directory (same sha256).
"""

import contextlib
import hashlib
import json
import logging
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Literal

from kartograf.exceptions import DownloadError

logger = logging.getLogger(__name__)

VERSIONS_DIR = "versions"
INCOMING_DIR = ".incoming"
LabelSource = Literal["campaign", "edition", "downloaded"]

_VERSION_DIR = re.compile(r"(?P<label>.+)_(?P<sha8>[0-9a-f]{8})")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CHUNK = 1_048_576


def sha256_file(path: Path) -> str:
    """Hex sha256 of a file (streamed in 1 MiB chunks)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def downloaded_label(now: datetime | None = None) -> str:
    """Label of a version without a source date: the UTC download date."""
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class VersionRef:
    """Identity (sha256) and human label of one version."""

    label: str
    label_source: LabelSource
    sha256: str

    @property
    def sha8(self) -> str:
        return self.sha256[:8]

    @property
    def dirname(self) -> str:
        return f"{self.label}_{self.sha8}"

    def to_extra(self) -> dict:
        """``extra.version`` of the version sidecar."""
        return {"label": self.label, "label_source": self.label_source}


@dataclass(frozen=True)
class LocalVersion:
    """A valid version on disk with its ordering key."""

    path: Path
    version: VersionRef
    downloaded_at: str
    key: tuple[str, str, str]


@dataclass(frozen=True)
class VersionCommit:
    """Result of ``commit_version``."""

    path: Path
    version: VersionRef
    status: Literal["new", "unchanged"]


def _sidecar_of(path: Path) -> Path:
    return path.parent / f"{path.name}.meta.json"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sidecar_key(meta: dict) -> tuple[str, str, str] | None:
    """Ordering key of a version from its sidecar.

    Campaign (``extra.campaign`` with ``pzgik_date`` + ``extra.source.url``):
    ``(date, pzgik_date or "", url)`` — the ADR-028 order. Otherwise
    ``(label date or "", downloaded_at, sha256)``. ``None`` = sidecar without
    the needed fields.
    """
    extra = meta.get("extra")
    extra = extra if isinstance(extra, dict) else {}
    campaign = extra.get("campaign")
    source = extra.get("source")
    if isinstance(campaign, dict) and "pzgik_date" in campaign:
        date = campaign.get("date")
        url = source.get("url") if isinstance(source, dict) else None
        pzgik = campaign.get("pzgik_date") or ""
        if isinstance(date, str) and isinstance(url, str) and isinstance(pzgik, str):
            return (date, pzgik, url)
        return None
    sha = meta.get("sha256")
    downloaded_at = meta.get("downloaded_at")
    if not isinstance(sha, str) or not isinstance(downloaded_at, str):
        return None
    version = extra.get("version")
    label = version.get("label") if isinstance(version, dict) else None
    label_date = label[:10] if isinstance(label, str) and _DATE.match(label) else ""
    return (label_date, downloaded_at, sha)


def incoming_path(segment_root: Path, name: str) -> Path:
    """Working path for a download: ``versions/.incoming/<pid>_<tid>/<name>``."""
    return (
        Path(segment_root)
        / VERSIONS_DIR
        / INCOMING_DIR
        / f"{os.getpid()}_{threading.get_ident()}"
        / name
    )


def _prune_incoming(staged: Path, segment_root: Path) -> None:
    """Remove the empty ``<pid>_<tid>`` and ``.incoming`` directories."""
    incoming = Path(segment_root) / VERSIONS_DIR / INCOMING_DIR
    for directory in (staged.parent, incoming):
        with contextlib.suppress(OSError):
            directory.rmdir()  # only when empty


def list_versions(segment_root: Path, rel: PurePath) -> list[LocalVersion]:
    """Valid versions of ``rel`` (data + readable sidecar with sha256 and a key).

    A version directory with only one of the two files (interrupted write)
    is skipped with a warning; ``.incoming`` is never a version.
    """
    root = Path(segment_root) / VERSIONS_DIR
    if not root.is_dir():
        return []
    found: list[LocalVersion] = []
    for entry in sorted(root.iterdir()):
        if entry.name == INCOMING_DIR or not entry.is_dir():
            continue
        m = _VERSION_DIR.fullmatch(entry.name)
        if m is None:
            continue
        data = entry / rel
        sidecar = _sidecar_of(data)
        has_data, has_sidecar = data.is_file(), sidecar.is_file()
        if not has_data and not has_sidecar:
            continue
        meta = _read_json(sidecar) if has_sidecar else None
        key = sidecar_key(meta) if meta is not None else None
        sha = meta.get("sha256") if meta is not None else None
        if not has_data or key is None or not isinstance(sha, str):
            logger.warning(f"Wersja {entry / rel} niekompletna — pominieta")
            continue
        extra = meta.get("extra") if isinstance(meta.get("extra"), dict) else {}
        version = extra.get("version") if isinstance(extra, dict) else None
        label_source = (
            version.get("label_source") if isinstance(version, dict) else None
        )
        if label_source not in ("campaign", "edition", "downloaded"):
            label_source = "downloaded"
        found.append(
            LocalVersion(
                path=data,
                version=VersionRef(m.group("label"), label_source, sha),
                downloaded_at=str(meta.get("downloaded_at", "")),
                key=key,
            )
        )
    return found


def newest_version(versions: list[LocalVersion]) -> LocalVersion | None:
    """The version with the highest key (``None`` for an empty list)."""
    return max(versions, key=lambda v: v.key) if versions else None


def commit_version(
    staged: Path,
    segment_root: Path,
    rel: PurePath,
    *,
    label: str,
    label_source: LabelSource,
    write_sidecar: Callable[[Path, VersionRef], None],
) -> VersionCommit:
    """Move a downloaded file into its version directory (spec 3.1).

    The same sha256 as ANY valid version of ``rel`` = ``unchanged`` (the
    working file is removed). A ``<label>_<sha8>`` directory whose sidecar
    carries another full sha256 = ``DownloadError`` (prefix collision).
    Otherwise ``os.replace`` + ``write_sidecar(target, ref)``; a sidecar
    failure removes the data file and raises ``DownloadError``.
    """
    staged = Path(staged)
    try:
        sha = sha256_file(staged)
        ref = VersionRef(label, label_source, sha)
        for existing in list_versions(segment_root, rel):
            if existing.version.sha256 == sha:
                staged.unlink(missing_ok=True)
                return VersionCommit(existing.path, existing.version, "unchanged")
        target = Path(segment_root) / VERSIONS_DIR / ref.dirname / rel
        meta = _read_json(_sidecar_of(target))
        other = meta.get("sha256") if meta is not None else None
        if isinstance(other, str) and other != sha:
            staged.unlink(missing_ok=True)
            raise DownloadError(
                f"{target}: kolizja prefiksu sha256 ({ref.sha8}) z inna trescia"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)
        try:
            write_sidecar(target, ref)
        except Exception as e:
            target.unlink(missing_ok=True)
            if isinstance(e, DownloadError):
                raise
            raise DownloadError(f"Sidecar wersji {target}: {e}") from e
        return VersionCommit(target, ref, "new")
    finally:
        _prune_incoming(staged, segment_root)
```

- [ ] **Step 4: Uruchom testy — maja przejsc**

Run: `.venv/bin/python -m pytest tests/test_versions.py -q`
Expected: PASS (wszystkie)

- [ ] **Step 5: Brama i commit**

```bash
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m mypy kartograf/ tests/
git add kartograf/download/versions.py tests/test_versions.py
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "feat(store): modul wersji — tozsamosc sha256, zapis przez .incoming, lista wersji

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Sidecar wersji (`sha256`, `extra.version`)

**Files:**
- Modify: `kartograf/sources/sidecar.py` (`ResultMetadata`, `build_metadata`, `emit_sidecar`)
- Test: `tests/test_sidecar.py`

**Interfaces:**
- Consumes: `VersionRef.to_extra()` (Task 2) — przez parametr `version: dict | None`
- Produces: `emit_sidecar(..., sha256: str | None = None, version: dict | None = None)`; `ResultMetadata.sha256: str | None`

- [ ] **Step 1: Napisz testy (dopisz na koncu `tests/test_sidecar.py`)**

```python
def test_emit_sidecar_writes_sha256_and_version(tmp_path):
    import json

    from kartograf.sources.sidecar import emit_sidecar

    data = tmp_path / "N-34-139-C-a-3-1.asc"
    data.write_text("ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n1\n")
    path = emit_sidecar(
        "pl.gugik.nmt_1m",
        data,
        request={"sheet": "N-34-139-C-a-3-1"},
        vertical_crs="EVRF2007",
        sha256="ab" * 32,
        version={"label": "2026-10-08", "label_source": "downloaded"},
        required=True,
    )
    meta = json.loads(path.read_text(encoding="utf-8"))
    assert meta["sha256"] == "ab" * 32
    assert meta["extra"]["version"] == {
        "label": "2026-10-08",
        "label_source": "downloaded",
    }


def test_emit_sidecar_without_sha256_writes_null(tmp_path):
    import json

    from kartograf.sources.sidecar import emit_sidecar

    data = tmp_path / "N-34-139-C-a-3-1.asc"
    data.write_text("ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n1\n")
    path = emit_sidecar("pl.gugik.nmt_1m", data, request={"sheet": "N-34-139-C-a-3-1"})
    meta = json.loads(path.read_text(encoding="utf-8"))
    assert meta["sha256"] is None
    assert "version" not in meta["extra"]
```

- [ ] **Step 2: Uruchom — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_sidecar.py -q -k "sha256"`
Expected: FAIL — `TypeError: emit_sidecar() got an unexpected keyword argument 'sha256'`

- [ ] **Step 3: Implementacja**

W `ResultMetadata` dodaj pole po `kartograf_version`:

```python
    downloaded_at: str  # ISO 8601 UTC
    kartograf_version: str
    sha256: str | None = None  # data file content identity (ADR-032)
    transform: dict | None = None  # stage 0: None
```

W `build_metadata` dodaj parametry `sha256: str | None = None, version: dict | None = None` (po `horizontal_crs`) i zmien budowe `extra` oraz wywolanie konstruktora:

```python
    merged_extra = dict(extra or {})
    if version is not None:
        merged_extra["version"] = dict(version)
    return ResultMetadata(
        ...
        transform=transform,
        extra=merged_extra,
        downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        sha256=sha256,
    )
```

(pozostale argumenty konstruktora bez zmian). W `emit_sidecar` dodaj parametry `sha256: str | None = None, version: dict | None = None` (przed `required`) i przekaz je do `build_metadata(..., sha256=sha256, version=version)`. Uzupelnij docstring `emit_sidecar`: "``sha256``/``version`` — identity and label of a store version (ADR-032); a version sidecar is written once and never modified."

- [ ] **Step 4: Uruchom — maja przejsc; caly plik sidecara bez regresji**

Run: `.venv/bin/python -m pytest tests/test_sidecar.py tests/test_sidecar_required.py -q`
Expected: PASS

- [ ] **Step 5: Brama i commit**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m mypy kartograf/ tests/
git add kartograf/sources/sidecar.py tests/test_sidecar.py
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "feat(sidecar): pola sha256 i extra.version dla wersji magazynu

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Dowiazanie i `FileStorage` na katalogu `versions/`

**Files:**
- Modify: `kartograf/download/links.py`, `kartograf/download/campaigns.py`, `kartograf/download/storage.py`
- Test: `tests/test_links.py`, `tests/test_storage.py`, `tests/test_campaigns.py`

**Interfaces:**
- Consumes: `VERSIONS_DIR`, `sidecar_key` (Task 2)
- Produces:
  - `links.version_key_of(data_path: Path) -> tuple[str, str, str] | None` (zastepuje `campaign_key_of`; `campaign_key_from_sidecar` usuniete)
  - `links.linked_version(link: Path) -> Path | None` (zmiana nazwy `linked_campaign`)
  - `links.ensure_standard_link(link, target, key, *, refresh=False) -> LinkOutcome` (sygnatura bez zmian)
  - `FileStorage.version_parts(godlo: str, ext: str = ".asc") -> tuple[Path, PurePath]` — `(segment_root, rel)`
  - `FileStorage.list_files(pattern="**/*.asc", *, versions: bool = False)`
  - usuniete: `FileStorage.get_campaign_path`, `campaigns.CAMPAIGNS_DIR`

- [ ] **Step 1: Napisz/zmien testy**

Dopisz do `tests/test_storage.py`:

```python
def test_version_parts_splits_segment_and_hierarchy(tmp_path):
    from pathlib import PurePath

    from kartograf.download.storage import FileStorage

    st = FileStorage(tmp_path, resolution="1m")
    root, rel = st.version_parts("N-34-139-C-a-3-1", ".asc")
    assert root == tmp_path / "nmt" / "pl_1992_1m_evrf2007"
    assert rel == PurePath("N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc")
    assert root / rel == st.get_path("N-34-139-C-a-3-1", ".asc")


def test_list_files_separates_versions(tmp_path):
    from kartograf.download.storage import FileStorage

    st = FileStorage(tmp_path, resolution="1m")
    std = st.get_path("N-34-139-C-a-3-1", ".asc")
    root, rel = st.version_parts("N-34-139-C-a-3-1", ".asc")
    ver = root / "versions" / "2026-10-08_0123abcd" / rel
    for p in (std, ver):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    assert st.list_files() == [std]
    assert st.list_files(versions=True) == [ver]
```

Dopisz do `tests/test_links.py`:

```python
def test_version_key_from_generic_sidecar(tmp_path):
    import json

    from kartograf.download.links import version_key_of

    data = tmp_path / "versions" / "2026-10-08_0123abcd" / "a.gpkg"
    data.parent.mkdir(parents=True)
    data.write_text("x")
    (data.parent / "a.gpkg.meta.json").write_text(json.dumps({
        "sha256": "0123abcd" + "0" * 56,
        "downloaded_at": "2026-10-08T10:00:00+00:00",
        "extra": {"version": {"label": "2026-10-08", "label_source": "downloaded"}},
    }))
    assert version_key_of(data) == (
        "2026-10-08", "2026-10-08T10:00:00+00:00", "0123abcd" + "0" * 56
    )


def test_version_key_falls_back_to_versions_dirname(tmp_path):
    from kartograf.download.links import version_key_of

    data = tmp_path / "versions" / "2022-05-10_83233_0123abcd" / "N.asc"
    data.parent.mkdir(parents=True)
    data.write_text("x")
    assert version_key_of(data) == ("2022-05-10", "", "")


def test_version_key_none_outside_versions(tmp_path):
    from kartograf.download.links import version_key_of

    data = tmp_path / "kampanie" / "2022-05-10_83233" / "N.asc"
    data.parent.mkdir(parents=True)
    data.write_text("x")
    assert version_key_of(data) is None
```

W istniejacych testach `tests/test_links.py`, `tests/test_storage.py`, `tests/test_campaigns.py`:
- import `campaign_key_of` -> `version_key_of`, `linked_campaign` -> `linked_version`;
- sciezki `.../kampanie/<data>_<id>/...` -> `.../versions/<data>_<id>_0123abcd/...` (fallback z nazwy katalogu wymaga sufiksu `_<sha8>`);
- testy `get_campaign_path` usun (metoda znika); `list_files(campaigns=True)` -> `list_files(versions=True)`;
- testy `CAMPAIGNS_DIR` usun.

- [ ] **Step 2: Uruchom — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_links.py tests/test_storage.py tests/test_campaigns.py -q`
Expected: FAIL (`ImportError: cannot import name 'version_key_of'`, `AttributeError: ... version_parts`)

- [ ] **Step 3: Implementacja — `links.py`**

Zastap stale i funkcje klucza:

```python
from kartograf.download.versions import VERSIONS_DIR, sidecar_key

# "<label>_<sha8>" whose label starts with a date: lower bound of the key
_VERSION_DIR = re.compile(r"(\d{4}-\d{2}-\d{2})(?:_.*)?_[0-9a-f]{8}")


def version_key_of(data_path: Path) -> tuple[str, str, str] | None:
    """Ordering key of a version file (ADR-032; campaigns: ADR-030 (d), D-1).

    First the key from the version sidecar (``versions.sidecar_key``); when
    unreadable — from the directory name: the element after the LAST
    ``versions`` segment that matches ``<date>[_...]_<sha8>`` -> ``(date,
    "", "")``, a LOWER BOUND (with the same date the new target wins, a
    target with a later date stays). ``None`` when neither yields a key.
    """
    meta = _read_json(_sidecar_of(data_path))
    if meta is not None:
        key = sidecar_key(meta)
        if key is not None:
            return key
    parts = PurePath(_norm(data_path)).parts
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx] != VERSIONS_DIR:
            continue
        m = _VERSION_DIR.fullmatch(parts[idx + 1])
        if m is not None:
            return (m.group(1), "", "")
    return None
```

Usun `_CAMPAIGNS_DIR`, `_CAMPAIGN_DIR`, `campaign_key_from_sidecar`, `campaign_key_of`. Zmien nazwe `linked_campaign` -> `linked_version` (tresc bez zmian, w docstringu "campaign" -> "version"). W `ensure_standard_link` zamien `campaign_key_of(cur)` na `version_key_of(cur)`. Zaktualizuj docstring modulu: pliki leza w `<segment>/versions/<label>_<sha8>/...` (ADR-032), dowiazanie do najnowszej LOKALNEJ wersji. `download/versions.py` nie importuje `links.py` (brak cyklu).

- [ ] **Step 4: Implementacja — `campaigns.py` i `storage.py`**

`campaigns.py`: usun `CAMPAIGNS_DIR = "kampanie"`. `storage.py`: usun import `CAMPAIGNS_DIR, CampaignRef` i metode `get_campaign_path`; dodaj import `from pathlib import Path, PurePath` i `from kartograf.download.versions import VERSIONS_DIR`; dodaj metode:

```python
    def version_parts(self, godlo: str, ext: str = ".asc") -> tuple[Path, PurePath]:
        """``(segment_root, rel)`` of a sheet: ``get_path == segment_root / rel``.

        Versions of the sheet live in
        ``segment_root / "versions" / <label>_<sha8> / rel`` (ADR-032).
        """
        normalized = SheetParser(godlo).godlo
        root = self._output_dir / self._resolved_subdir(normalized)
        rel = PurePath(*self._get_directory_parts(normalized), f"{normalized}{ext}")
        return root, rel
```

W `list_files` zmien parametr `campaigns` na `versions` (docstring: "False (default): standard paths — without ``versions/``. True: only files in ``versions/`` (ADR-032).") i warunek na `in_versions = p.relative_to(root).parts[:1] == (VERSIONS_DIR,)`. W `delete` i `write_atomic` zamien w komentarzach `kampanie/` na `versions/`.

- [ ] **Step 5: Uruchom — maja przejsc**

Run: `.venv/bin/python -m pytest tests/test_links.py tests/test_storage.py tests/test_campaigns.py tests/test_versions.py -q`
Expected: PASS. Pozostale moduly (`manager.py`) jeszcze importuja stare nazwy — naprawia je Task 5; dlatego w tym kroku NIE uruchamiaj calego zestawu.

- [ ] **Step 6: Commit (bez bramy calego zestawu — manager w Task 5)**

```bash
.venv/bin/python -m ruff check kartograf/download tests/test_links.py tests/test_storage.py tests/test_campaigns.py
git add kartograf/download/links.py kartograf/download/campaigns.py kartograf/download/storage.py tests/test_links.py tests/test_storage.py tests/test_campaigns.py
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "refactor(store): dowiazanie i FileStorage na katalogu versions/

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `DownloadManager` — tryby `update` i wersje arkuszy

**Files:**
- Modify: `kartograf/download/manager.py`
- Modify: `kartograf/download/cutout.py:766` (wywolanie `download_sheets`)
- Create: `tests/test_manager_versions.py`
- Modify: `tests/test_manager_campaigns.py`, `tests/test_download_manager.py`, `tests/test_parallel_download.py`, `tests/test_campaigns_flow.py`, `tests/test_integration.py`, `tests/test_pl_cutout.py`

**Interfaces:**
- Consumes: `commit_version`, `list_versions`, `newest_version`, `incoming_path`, `downloaded_label`, `VersionRef`, `LocalVersion` (Task 2); `version_key_of`, `linked_version`, `ensure_standard_link` (Task 4); `FileStorage.version_parts` (Task 4); `emit_sidecar(sha256=, version=)` (Task 3)
- Produces:
  - `UpdateMode = Literal["check", "upgrade", "force"]` (w `manager.py`)
  - `download_sheet(godlo, update: UpdateMode | None = None, on_progress=None, on_download=None)`, `download_hierarchy(godlo, target_scale, update=None, on_progress=None, max_workers=None)`, `download_sheets(godla, update=None, on_progress=None, max_workers=None)` — parametr `skip_existing` usuniety; `update="check"` -> `ValidationError` (sprawdzanie: `check_sheet`)
  - `SheetFetch` + pola `status: Literal["new", "unchanged", "local"] = "new"`, `version: VersionRef | None = None`, `newer: tuple[str, ...] = ()`, `unverifiable: bool = False`
  - `DownloadResult` + pola `unchanged: list[str]`, `newer: dict[str, tuple[str, ...]]`, `unverifiable: list[str]`
  - `DownloadManager.check_sheet(godlo: str) -> PlanItem` — definicja `PlanItem` w Task 6; w tym tasku zwracany jest `dict` o kluczach z Task 6 i Task 6 podmienia go na `PlanItem` (patrz Step 3c)

- [ ] **Step 1: Napisz testy nowych zachowan (`tests/test_manager_versions.py`)**

```python
"""DownloadManager on the versioned store (ADR-032): update modes per sheet."""

import json
from pathlib import Path

import pytest
import requests

from kartograf.download.manager import DownloadManager
from kartograf.download.versions import list_versions
from kartograf.exceptions import DownloadError, ValidationError
from tests.test_manager_campaigns import C14, C14_ALL, REC, G, FakeCampaignProvider

OLD = REC["83233"]  # 2025-04-27
NEW = REC["84183"]  # 2025-10-21 (newest)


def _manager(tmp_path, records, **kw):
    provider = FakeCampaignProvider(records)
    return DownloadManager(output_dir=tmp_path, provider=provider, **kw), provider


def _versions(m):
    root, rel = m.storage.version_parts(G, ".asc")
    return list_versions(root, rel)


def test_first_run_downloads_newest_as_version(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    path = m.download_sheet(G)
    fetch = m.last_sheet
    assert fetch.status == "new"
    assert fetch.version is not None and fetch.version.label_source == "campaign"
    assert "/versions/" in fetch.downloaded[0].as_posix()
    assert path == m.storage.get_path(G, ".asc")
    meta = json.loads(Path(f"{fetch.downloaded[0]}.meta.json").read_text())
    assert meta["sha256"] == fetch.version.sha256
    assert meta["extra"]["version"]["label"] == fetch.version.label


def test_default_with_local_does_not_download_newer_but_reports_it(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    p.records = {"newest": [NEW], "all": [NEW, OLD]}
    p.downloads.clear()
    m.download_sheet(G)
    assert p.downloads == []
    assert m.last_sheet.status == "local"
    assert m.last_sheet.newer and m.last_sheet.newer[0].startswith(NEW.aktualnosc)


def test_upgrade_downloads_newer_and_relinks(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    p.records = {"newest": [NEW], "all": [NEW, OLD]}
    m.download_sheet(G, update="upgrade")
    assert m.last_sheet.status == "new"
    assert len(_versions(m)) == 2
    std = m.storage.get_path(G, ".asc")
    assert NEW.url.rsplit("/", 1)[-1] in std.read_text()


def test_upgrade_when_current_downloads_nothing(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    p.downloads.clear()
    m.download_sheet(G, update="upgrade")
    assert p.downloads == []
    assert m.last_sheet.status == "local"


def test_force_same_content_is_unchanged_without_new_version(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    m.download_sheet(G, update="force")
    assert m.last_sheet.status == "unchanged"
    assert len(_versions(m)) == 1


def test_force_changed_content_same_campaign_is_new_version(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    p.version = "v2"  # silent fix at the source: same record, other bytes
    m.download_sheet(G, update="force")
    assert m.last_sheet.status == "new"
    assert len(_versions(m)) == 2


def test_check_mode_rejected_by_download(tmp_path):
    m, _ = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    with pytest.raises(ValidationError, match="check_sheet"):
        m.download_sheet(G, update="check")


@pytest.mark.parametrize("kw", [{"campaigns": "all"}, {"min_year": 2000}, {}])
def test_default_transport_failure_any_strategy_uses_local(tmp_path, kw):
    records = {"newest": [OLD], "all": [OLD]}
    m, p = _manager(tmp_path, records, **kw)
    m.download_sheet(G)
    err = DownloadError("x")
    err.__cause__ = requests.ConnectionError("down")
    p.resolve_error = err
    m.download_sheet(G)
    assert m.last_sheet.status == "local"
    assert m.last_sheet.unverified is not None


def test_upgrade_transport_failure_raises(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheet(G)
    err = DownloadError("x")
    err.__cause__ = requests.ConnectionError("down")
    p.resolve_error = err
    with pytest.raises(DownloadError):
        m.download_sheet(G, update="upgrade")


def test_all_default_with_local_reports_missing_campaigns(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]}, campaigns="all")
    m.download_sheet(G)
    p.records = {"newest": [NEW], "all": C14_ALL}
    p.downloads.clear()
    m.download_sheet(G)
    assert p.downloads == []
    assert len(m.last_sheet.newer) == len(C14_ALL) - 1


def test_version_sidecar_not_modified_by_reuse(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]},
                    sidecar_extra={"parent_request": {"bbox": [0, 0, 1, 1]}})
    m.download_sheet(G)
    [v] = _versions(m)
    before = Path(f"{v.path}.meta.json").read_bytes()
    m2 = DownloadManager(output_dir=tmp_path, provider=p,
                         sidecar_extra={"parent_request": {"bbox": [2, 2, 3, 3]}})
    m2.download_sheet(G)
    assert Path(f"{v.path}.meta.json").read_bytes() == before
    assert "parent_requests" not in before.decode()


def test_list_result_counts_unchanged_and_newer(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    m.download_sheets([G])
    p.records = {"newest": [NEW], "all": [NEW, OLD]}
    m.download_sheets([G])
    assert m.last_result.skipped == [G]
    assert G in m.last_result.newer
    m.download_sheets([G], update="force")
    assert m.last_result.unchanged == []  # force downloads NEW: other content
```

- [ ] **Step 2: Uruchom — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_manager_versions.py -q`
Expected: FAIL (`ImportError`/`TypeError: unexpected keyword argument 'update'`)

- [ ] **Step 3a: Implementacja — typy wyniku i sygnatury**

W `manager.py`:
- importy: zamien import z `links` na `from kartograf.download.links import LinkOutcome, ensure_standard_link, linked_version, write_standard_sidecar` i dodaj `from typing import Literal` oraz
  `from kartograf.download.versions import LocalVersion, VersionRef, commit_version, downloaded_label, incoming_path, list_versions, newest_version`;
- po importach: `UpdateMode = Literal["check", "upgrade", "force"]`;
- `SheetFetch`: dodaj pola na koncu:

```python
    status: Literal["new", "unchanged", "local"] = "new"
    version: VersionRef | None = None
    newer: tuple[str, ...] = ()
    unverifiable: bool = False
```

  z docstringiem: "``status``: ``new`` = a new version written, ``unchanged`` = downloaded but identical to a local version, ``local`` = nothing downloaded. ``version`` = the version the standard path points to. ``newer`` = labels of source versions not present locally (default mode only reports them). ``unverifiable`` = ``upgrade`` without a cheap signal (flow without campaigns)."
- `DownloadResult`: dodaj pola `unchanged: list[str]`, `newer: dict[str, tuple[str, ...]]`, `unverifiable: list[str]` (wszystkie `field(default_factory=...)`), z opisem w docstringu;
- `download_sheet`, `download_hierarchy`, `download_sheets`, `_fetch_sheet`, `_download_single_sheet_task`, `_download_many`: zamien parametr `skip_existing: bool = True` na `update: UpdateMode | None = None` i przekazuj dalej; na poczatku `download_sheet`/`download_hierarchy`/`download_sheets` (po resecie `last_result`/`last_sheet`):

```python
        if update == "check":
            raise ValidationError(
                "update='check' nie pobiera danych — uzyj DownloadManager.check_sheet "
                "albo kartograf.check_updates"
            )
```

- `_record`: po `if fetch.unverified is not None:` dodaj

```python
            if fetch.status == "unchanged":
                result.unchanged.append(godlo)
            if fetch.newer:
                result.newer[godlo] = fetch.newer
            if fetch.unverifiable:
                result.unverifiable.append(godlo)
```

- `_download_single_sheet_task`: `if fetch.status == "local": return (godlo, fetch, "skipped", "Lokalna wersja", ())`.
- Usun `_note_reuse` i `_note_standard_reuse` (oraz ich wywolania); usun `_local_newest` (zastepuje go `_use_local`).

- [ ] **Step 3b: Implementacja — wspolne pomocnicze**

```python
    def _use_local(
        self,
        godlo: str,
        std: Path,
        local: list[LocalVersion],
        *,
        newer: tuple[str, ...] = (),
        unverified: str | None = None,
        unverifiable: bool = False,
    ) -> SheetFetch:
        """Nothing downloaded: the standard path -> newest local version.

        ``ensure_standard_link`` never moves the link back, so this also
        repairs a missing/stale link without regressing it.
        """
        newest = newest_version(local)
        assert newest is not None  # callers pass a non-empty list
        outcome = ensure_standard_link(std, newest.path, newest.key)
        if unverified is not None:
            logger.warning(
                f"{godlo}: zrodlo niedostepne ({unverified}) — uzyto lokalnej "
                f"wersji {newest.version.dirname} bez sprawdzenia nowszej"
            )
        return SheetFetch(
            godlo,
            std,
            skipped=True,
            reused=(newest.path,),
            link=outcome.method,
            unverified=unverified,
            status="local",
            version=newest.version,
            newer=newer,
            unverifiable=unverifiable,
        )

    def _relink_newest(
        self, std: Path, segment_root: Path, rel, fresh: set[Path]
    ) -> tuple[LinkOutcome, LocalVersion]:
        """Point the standard path at the newest valid version (after commits)."""
        newest = newest_version(list_versions(segment_root, rel))
        if newest is None:
            raise DownloadError(f"{std}: brak waznej wersji po zapisie")
        outcome = ensure_standard_link(
            std, newest.path, newest.key, refresh=newest.path in fresh
        )
        return outcome, newest
```

- [ ] **Step 3c: Implementacja — tor kampanii (`_fetch_campaigns`)**

Zastap cialo `_fetch_campaigns` (sygnatura: `(self, godlo: str, update: UpdateMode | None, on_download=None) -> SheetFetch`):

```python
        std = self._storage.get_path(godlo, self._default_ext)
        segment_root, rel = self._storage.version_parts(godlo, self._default_ext)
        local = list_versions(segment_root, rel)
        try:
            records = self._campaign_provider.resolve_campaigns(
                godlo, campaigns=self._campaigns, min_year=self._min_year
            )
        except DownloadError as e:
            if update is None and local and _is_transport_failure(e):
                return self._use_local(godlo, std, local, unverified=str(e))
            raise
        logger.info("%s: %d kampanii (%s)", godlo, len(records), self._campaigns)
        local_keys = {v.key for v in local}
        errors: list[tuple[str, DownloadError]] = []
        wanted: list[tuple[SkorowidzRecord, CampaignRef]] = []
        for record in records:
            try:  # R16: a bad date = this campaign fails
                wanted.append((record, CampaignRef.from_record(record)))
            except DownloadError as e:
                errors.append((record.url, e))
        missing = [(r, ref) for r, ref in wanted if ref.sort_key not in local_keys]
        if local and update is None:
            labels = tuple(ref.dirname for _, ref in sorted(
                missing, key=lambda rr: rr[1].sort_key, reverse=True))
            return self._use_local(godlo, std, local, newer=labels)
        to_fetch = wanted if update == "force" else missing
        if local and not to_fetch and not errors:
            return self._use_local(godlo, std, local)
        new: list[Path] = []
        unchanged: list[Path] = []
        started = False
        for record, ref in to_fetch:
            try:
                ext = campaign_extension(ref, self._default_ext)  # before the network
            except DownloadError as e:
                errors.append((ref.dirname, e))
                continue
            if on_download is not None and not started:
                on_download()
                started = True
            staged = incoming_path(segment_root, rel.name)
            logger.info(f"Downloading {godlo} {ref.dirname}...")
            try:
                self._campaign_provider.download_record(record, staged)
                verify_file_format(staged, ext)
                commit = commit_version(
                    staged,
                    segment_root,
                    rel,
                    label=ref.dirname,
                    label_source="campaign",
                    write_sidecar=lambda path, ver, record=record, ref=ref: (
                        self._write_campaign_sidecar(path, godlo, record, ref, ver)
                    ),
                )
            except DownloadError as e:
                staged.unlink(missing_ok=True)
                errors.append((ref.dirname, e))
                continue
            (new if commit.status == "new" else unchanged).append(commit.path)
        method: str | None = None
        link_error: OSError | DownloadError | None = None
        version: VersionRef | None = None
        try:
            outcome, newest = self._relink_newest(std, segment_root, rel, set(new))
        except (OSError, DownloadError) as e:  # R5: sheet failure, not list abort
            link_error = e
        else:
            method, version = outcome.method, newest.version
        if errors or link_error is not None:  # Q10: full failure list
            problems = []
            if errors:
                listing = ", ".join(f"{name}: {e}" for name, e in errors)
                problems.append(
                    f"nie pobrano {len(errors)} z {len(records)} kampanii ({listing})"
                )
            if link_error is not None:
                problems.append(f"dowiazanie {std}: {link_error}")
            raise DownloadError(f"{godlo}: " + "; ".join(problems), godlo=godlo)
        status = "new" if new else ("unchanged" if unchanged else "local")
        return SheetFetch(
            godlo,
            std,
            skipped=status == "local",
            downloaded=tuple(new + unchanged),
            reused=tuple(v.path for v in local),
            link=method,
            status=status,
            version=version,
        )
```

`_write_campaign_sidecar` dostaje parametr `version: VersionRef` i przekazuje `sha256=version.sha256, version=version.to_extra()` do `_write_sidecar`; `_write_sidecar` dostaje parametry `sha256: str | None = None, version: dict | None = None` i przekazuje je do `emit_sidecar`.

- [ ] **Step 3d: Implementacja — tor bez kampanii (`_fetch_sheet_plain`)**

```python
    def _fetch_sheet_plain(
        self,
        godlo: str,
        update: UpdateMode | None,
        on_download: Callable[[], None] | None = None,
    ) -> SheetFetch:
        """Flow without campaigns: no cheap freshness signal (``none``).

        A local version is used for the default mode and for ``upgrade``
        (``unverifiable=True`` — nothing to compare without downloading);
        ``force`` or no local version downloads and commits a version
        labelled with the download date.
        """
        std = self._storage.get_path(godlo, self._default_ext)
        segment_root, rel = self._storage.version_parts(godlo, self._default_ext)
        local = list_versions(segment_root, rel)
        if local and update != "force":
            return self._use_local(
                godlo, std, local, unverifiable=update == "upgrade"
            )
        if on_download is not None:
            on_download()
        staged = incoming_path(segment_root, rel.name)
        logger.info(f"Downloading {godlo}...")
        try:
            downloaded = self._provider.download(godlo, staged)
            commit = commit_version(
                Path(downloaded),
                segment_root,
                rel,
                label=downloaded_label(),
                label_source="downloaded",
                write_sidecar=lambda path, ver: self._write_sidecar(
                    path,
                    {"sheet": godlo},
                    sha256=ver.sha256,
                    version=ver.to_extra(),
                    required=True,
                ),
            )
        finally:
            staged.unlink(missing_ok=True)
        fresh = {commit.path} if commit.status == "new" else set()
        outcome, newest = self._relink_newest(std, segment_root, rel, fresh)
        return SheetFetch(
            godlo,
            std,
            skipped=False,
            downloaded=(commit.path,),
            link=outcome.method,
            status=commit.status,
            version=newest.version,
        )
```

- [ ] **Step 3e: Implementacja — `check_sheet` (tymczasowo `dict`)**

```python
    def check_sheet(self, godlo: str) -> dict:
        """Compare the local versions of one 1:10000/PL-2000 sheet with the source.

        Never downloads data. Status: ``current``, ``newer``, ``missing``,
        ``unverifiable`` (no cheap signal), ``check_failed`` (signal
        unavailable), ``no_coverage``. Replaced by ``PlanItem`` in
        ``download/updates.py``.
        """
        segment_root, rel = self._storage.version_parts(godlo, self._default_ext)
        local = list_versions(segment_root, rel)
        newest = newest_version(local)
        local_info = (
            {"label": newest.version.label, "sha256": newest.version.sha256}
            if newest is not None
            else None
        )
        item = {"sheet": godlo, "local": local_info, "available": (), "error": None}
        if not self._campaign_aware:
            item["status"] = "unverifiable" if local else "missing"
            return item
        try:
            records = self._campaign_provider.resolve_campaigns(
                godlo, campaigns=self._campaigns, min_year=self._min_year
            )
        except NoCoverageError as e:
            return {**item, "status": "no_coverage", "error": str(e)}
        except DownloadError as e:
            return {**item, "status": "check_failed", "error": str(e)}
        local_keys = {v.key for v in local}
        refs = []
        for record in records:
            try:
                refs.append(CampaignRef.from_record(record))
            except DownloadError as e:
                return {**item, "status": "check_failed", "error": str(e)}
        missing = sorted(
            (r for r in refs if r.sort_key not in local_keys),
            key=lambda r: r.sort_key,
            reverse=True,
        )
        item["available"] = tuple(
            {
                "label": r.dirname,
                "signal": {"url": r.url, "date": r.date, "pzgik_date": r.dt_pzgik},
            }
            for r in missing
        )
        if not local:
            item["status"] = "missing"
        else:
            item["status"] = "newer" if missing else "current"
        return item
```

- [ ] **Step 3f: `cutout.py`**

W `kartograf/download/cutout.py` (wywolanie ok. linii 766) zamien `skip_existing=not force` na `update="force" if force else None` i zaktualizuj zdanie docstringu ok. linii 720 na: "(``update="force"`` with ``force``, otherwise local versions are used — ADR-032)". Pelne wersjonowanie wycinka: plan 2/3.

- [ ] **Step 4: Uruchom nowe testy**

Run: `.venv/bin/python -m pytest tests/test_manager_versions.py -q`
Expected: PASS

- [ ] **Step 5: Dostosuj istniejace testy**

Uruchom `.venv/bin/python -m pytest tests/ -m "not live" -q -x` i popraw kolejne bledy wedlug regul:

| Stary zapis w tescie | Nowy zapis |
|---|---|
| `skip_existing=False` | `update="force"` |
| `skip_existing=True` / brak | brak argumentu (`update=None`) |
| sciezka `.../kampanie/<data>_<id>/...` | szukaj przez `list_versions(*m.storage.version_parts(G, ".asc"))` albo `m.last_sheet.downloaded` |
| `linked_campaign` | `linked_version` |
| `list_files(campaigns=True)` | `list_files(versions=True)` |
| asercja "nowsza kampania pobrana automatycznie" (`test_newer_campaign_appears_relinks`, `test_removed_campaign_dir_redownloads_newest` itp.) | wywolanie z `update="upgrade"`; dodatkowo asercja, ze bez `update` nic nie jest pobierane |
| `test_reused_campaign_notes_parent_request_in_both_sidecars`, `test_note_reuse_*`, testy `parent_requests` | USUN (D12; zastepuje je `test_version_sidecar_not_modified_by_reuse`) |
| `test_reused_campaign_without_sidecar_*` (R22) | zamien na: wersja bez sidecara jest pomijana, a nastepne pobranie (domyslne, bo brak waznej wersji) zapisuje ja poprawnie |
| I-1 `test_resolve_failure_without_fallback_still_fails` z `campaigns="all"`/`min_year` | odwroc oczekiwanie: z lokalna wersja = `status == "local"`, `unverified` ustawione (Review Focus 4) |
| `test_transport_failure_with_force_fails` | bez zmian w oczekiwaniu (force = blad) |
| liczba plikow w `kampanie/` | liczba `list_versions(...)` |

Kazdy usuniety test wymien w opisie commita.

- [ ] **Step 6: Brama i commit**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m mypy kartograf/ tests/
git add kartograf/download/manager.py kartograf/download/cutout.py tests/
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "feat(store)!: DownloadManager na wersjach — tryby update zamiast skip_existing

BREAKING CHANGE: skip_existing usuniete (update=None|upgrade|force);
kampanie w versions/<data>_<id>_<sha8>/; domyslne uruchomienie nie
pobiera nowszej kampanii (tylko SheetFetch.newer); extra.parent_requests
usuniete.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Plan aktualizacji (`updates.py`)

**Files:**
- Create: `kartograf/download/updates.py`
- Modify: `kartograf/download/manager.py` (`check_sheet` zwraca `PlanItem`)
- Modify: `kartograf/__init__.py` (eksporty)
- Test: `tests/test_updates.py`; `tests/test_manager_versions.py` (asercje na `PlanItem`)

**Interfaces:**
- Consumes: `DownloadManager.check_sheet`, `download_sheets(update="upgrade")`, `expand_sheets`, `last_result` (Task 5)
- Produces:
  - `PLAN_SCHEMA = "kartograf-plan/1"`
  - `PlanStatus = Literal["current", "newer", "missing", "unverifiable", "check_failed", "no_coverage"]`
  - `@dataclass(frozen=True) PlanItem(sheet: str, status: PlanStatus, local: dict | None, available: tuple[dict, ...], error: str | None = None)`
  - `@dataclass(frozen=True) UpdatePlan(store: str, request: dict, checked_at: str, kartograf_version: str, items: tuple[PlanItem, ...], schema: str = PLAN_SCHEMA)` z `to_json() -> str`, `@classmethod from_json(text: str) -> UpdatePlan`, `has_failures: bool` (jakikolwiek `check_failed`)
  - `manager_request(manager: DownloadManager) -> dict` — `{"dataset", "resolution", "vertical_crs", "campaigns", "min_year"}`
  - `check_updates(manager: DownloadManager, godla: list[str]) -> UpdatePlan`
  - `@dataclass(frozen=True) UpgradeReport(stale: tuple[str, ...], result: DownloadResult | None)`
  - `upgrade(manager: DownloadManager, plan: UpdatePlan) -> UpgradeReport`

- [ ] **Step 1: Napisz testy (`tests/test_updates.py`)**

```python
"""Update plan kartograf-plan/1 (ADR-032): check -> JSON -> upgrade."""

import dataclasses
import json

import pytest

from kartograf.download.manager import DownloadManager
from kartograf.download.updates import (
    PLAN_SCHEMA,
    PlanItem,
    UpdatePlan,
    check_updates,
    upgrade,
)
from kartograf.exceptions import ValidationError
from tests.test_manager_campaigns import REC, G, FakeCampaignProvider

OLD, NEW = REC["83233"], REC["84183"]


def _setup(tmp_path):
    p = FakeCampaignProvider({"newest": [OLD], "all": [OLD]})
    m = DownloadManager(output_dir=tmp_path, provider=p)
    m.download_sheet(G)
    p.records = {"newest": [NEW], "all": [NEW, OLD]}
    p.downloads.clear()
    return m, p


def test_check_updates_reports_newer_without_download(tmp_path):
    m, p = _setup(tmp_path)
    plan = check_updates(m, [G])
    [item] = plan.items
    assert item.status == "newer"
    assert item.available[0]["signal"]["url"] == NEW.url
    assert p.downloads == []
    assert plan.store == str(tmp_path.resolve())
    assert plan.request["campaigns"] == "newest"


def test_plan_json_round_trip(tmp_path):
    m, _ = _setup(tmp_path)
    plan = check_updates(m, [G])
    data = json.loads(plan.to_json())
    assert data["schema"] == PLAN_SCHEMA
    assert UpdatePlan.from_json(plan.to_json()) == plan


def test_plan_from_json_rejects_unknown_schema():
    with pytest.raises(ValidationError, match="kartograf-plan"):
        UpdatePlan.from_json(json.dumps({"schema": "kartograf-plan/9", "items": []}))


def test_upgrade_executes_plan(tmp_path):
    m, p = _setup(tmp_path)
    report = upgrade(m, check_updates(m, [G]))
    assert report.stale == ()
    assert p.downloads == [NEW.url]
    assert m.last_sheet is None and report.result is not None
    assert report.result.succeeded


def test_upgrade_skips_items_removed_from_plan(tmp_path):
    m, p = _setup(tmp_path)
    plan = check_updates(m, [G])
    trimmed = UpdatePlan(plan.store, plan.request, plan.checked_at,
                         plan.kartograf_version, items=())
    report = upgrade(m, trimmed)
    assert p.downloads == []
    assert report.result is None


def test_upgrade_stale_item_is_error_without_download(tmp_path):
    m, p = _setup(tmp_path)
    plan = check_updates(m, [G])
    newer_still = dataclasses.replace(NEW, url=NEW.url + "?v2")
    p.records = {"newest": [newer_still], "all": [newer_still, OLD]}
    report = upgrade(m, plan)
    assert report.stale == (G,)
    assert p.downloads == []


def test_upgrade_rejects_foreign_store(tmp_path):
    m, _ = _setup(tmp_path)
    plan = check_updates(m, [G])
    other = UpdatePlan("/elsewhere", plan.request, plan.checked_at,
                       plan.kartograf_version, plan.items)
    with pytest.raises(ValidationError, match="magazyn"):
        upgrade(m, other)


def test_upgrade_rejects_other_request(tmp_path):
    m, _ = _setup(tmp_path)
    plan = check_updates(m, [G])
    other = UpdatePlan(plan.store, {**plan.request, "campaigns": "all"},
                       plan.checked_at, plan.kartograf_version, plan.items)
    with pytest.raises(ValidationError, match="zadanie"):
        upgrade(m, other)


def test_has_failures(tmp_path):
    item = PlanItem("X", "check_failed", None, (), "down")
    plan = UpdatePlan("/s", {}, "t", "v", (item,))
    assert plan.has_failures
```

(`SkorowidzRecord` to `@dataclass(frozen=True)`, wiec `dataclasses.replace` dziala.)

- [ ] **Step 2: Uruchom — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_updates.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kartograf.download.updates'`

- [ ] **Step 3: Implementacja `updates.py`**

```python
"""
Update plan ``kartograf-plan/1`` (ADR-032): check, review, upgrade.

``check_updates`` compares local versions with the source WITHOUT
downloading data and returns an ``UpdatePlan`` (JSON with English keys).
``upgrade`` executes exactly that plan: before downloading each item it
checks the source again; an item whose source changed since the plan is
reported as stale and NOT downloaded. Items removed from the plan file are
not executed. The plan lives wherever the user saves it — never in the store.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from kartograf._version import build_version
from kartograf.download.manager import DownloadManager, DownloadResult
from kartograf.exceptions import ValidationError

PLAN_SCHEMA = "kartograf-plan/1"
PlanStatus = Literal[
    "current", "newer", "missing", "unverifiable", "check_failed", "no_coverage"
]
_UPGRADABLE = ("newer", "missing")


@dataclass(frozen=True)
class PlanItem:
    """One sheet of the plan: local version vs. versions available at the source."""

    sheet: str
    status: PlanStatus
    local: dict | None  # {"label", "sha256"} of the newest local version
    available: tuple[dict, ...]  # [{"label", "signal": {...}}], newest first
    error: str | None = None


@dataclass(frozen=True)
class UpdatePlan:
    """Result of ``check_updates``; serialized as ``kartograf-plan/1``."""

    store: str  # absolute output directory
    request: dict  # manager_request(): dataset and strategy
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    schema: str = PLAN_SCHEMA

    @property
    def has_failures(self) -> bool:
        """At least one item could not be checked (``check_failed``)."""
        return any(i.status == "check_failed" for i in self.items)

    def to_json(self) -> str:
        data = asdict(self)
        data["items"] = [
            {**asdict(i), "available": list(i.available)} for i in self.items
        ]
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "UpdatePlan":
        try:
            data = json.loads(text)
        except ValueError as e:
            raise ValidationError(f"Plan aktualizacji nie jest JSON: {e}") from e
        if not isinstance(data, dict) or data.get("schema") != PLAN_SCHEMA:
            raise ValidationError(
                f"Nieznany schemat planu {data.get('schema') if isinstance(data, dict) else None!r} "
                f"(oczekiwano {PLAN_SCHEMA})"
            )
        try:
            items = tuple(
                PlanItem(
                    sheet=i["sheet"],
                    status=i["status"],
                    local=i.get("local"),
                    available=tuple(i.get("available") or ()),
                    error=i.get("error"),
                )
                for i in data["items"]
            )
            return cls(
                store=data["store"],
                request=data["request"],
                checked_at=data["checked_at"],
                kartograf_version=data["kartograf_version"],
                items=items,
            )
        except (KeyError, TypeError) as e:
            raise ValidationError(f"Niepelny plan aktualizacji: {e}") from e


def manager_request(manager: DownloadManager) -> dict:
    """What a plan was computed for — must match the manager executing it."""
    return {
        "dataset": getattr(manager.provider, "descriptor_key", None),
        "resolution": manager.resolution,
        "vertical_crs": manager.vertical_crs,
        "campaigns": manager.campaigns,
        "min_year": manager.min_year,
    }


def _store(manager: DownloadManager) -> str:
    return str(Path(manager.storage.output_dir).resolve())


def check_updates(manager: DownloadManager, godla: list[str]) -> UpdatePlan:
    """Check every leaf sheet of ``godla`` (``expand_sheets``) — no data downloaded."""
    items = tuple(manager.check_sheet(g) for g in manager.expand_sheets(godla))
    return UpdatePlan(
        store=_store(manager),
        request=manager_request(manager),
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=items,
    )


@dataclass(frozen=True)
class UpgradeReport:
    """Result of ``upgrade``: stale items and the download result."""

    stale: tuple[str, ...]
    result: DownloadResult | None  # None = nothing to download


def upgrade(manager: DownloadManager, plan: UpdatePlan) -> UpgradeReport:
    """Execute ``plan`` with ``manager`` (same store and request, else ValidationError)."""
    if plan.schema != PLAN_SCHEMA:
        raise ValidationError(f"Nieznany schemat planu {plan.schema!r}")
    if plan.store != _store(manager):
        raise ValidationError(
            f"Plan dotyczy innego magazynu ({plan.store}), a nie {_store(manager)}"
        )
    if plan.request != manager_request(manager):
        raise ValidationError(
            "Plan dotyczy innego zadania (produkt, rozdzielczosc, uklad, "
            f"strategia kampanii): {plan.request} != {manager_request(manager)}"
        )
    stale: list[str] = []
    todo: list[str] = []
    for item in plan.items:
        if item.status not in _UPGRADABLE:
            continue
        now = manager.check_sheet(item.sheet)
        if now.status != item.status or now.available != item.available:
            stale.append(item.sheet)
            continue
        todo.append(item.sheet)
    if not todo:
        return UpgradeReport(tuple(stale), None)
    manager.download_sheets(todo, update="upgrade")
    return UpgradeReport(tuple(stale), manager.last_result)
```

- [ ] **Step 4: `check_sheet` zwraca `PlanItem`**

W `manager.py` zmien adnotacje i budowe w `check_sheet`: zwracaj `PlanItem(sheet=..., status=..., local=..., available=..., error=...)` (import lokalny w funkcji: `from kartograf.download.updates import PlanItem` — `updates.py` importuje `manager.py`, wiec import na poziomie modulu dalby cykl). Adnotacja zwrotna: `"PlanItem"` z `if TYPE_CHECKING: from kartograf.download.updates import PlanItem`. W `tests/test_manager_versions.py` dopisz:

```python
def test_check_sheet_statuses(tmp_path):
    m, p = _manager(tmp_path, {"newest": [OLD], "all": [OLD]})
    assert m.check_sheet(G).status == "missing"
    m.download_sheet(G)
    assert m.check_sheet(G).status == "current"
    p.records = {"newest": [NEW], "all": [NEW, OLD]}
    item = m.check_sheet(G)
    assert item.status == "newer" and item.local["label"].startswith(OLD.aktualnosc)
    err = DownloadError("x")
    err.__cause__ = requests.ConnectionError("down")
    p.resolve_error = err
    assert m.check_sheet(G).status == "check_failed"
```

- [ ] **Step 5: Eksporty**

W `kartograf/__init__.py` dodaj importy i wpisy `__all__` (sekcja "Download"): `"VersionRef"` (z `kartograf.download.versions`), `"UpdatePlan"`, `"PlanItem"`, `"UpgradeReport"`, `"check_updates"`, `"upgrade"` (z `kartograf.download.updates`). Zaktualizuj liste eksportow w teście sprawdzajacym `__all__` (`tests/test_pl_cutout.py` ok. linii 1842 i ewentualne inne asercje listy `__all__` — `grep -rn "__all__" tests`).

- [ ] **Step 6: Uruchom, brama, commit**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m mypy kartograf/ tests/
git add kartograf/download/updates.py kartograf/download/manager.py kartograf/__init__.py tests/
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "feat(store): plan aktualizacji kartograf-plan/1 (check_updates, upgrade)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: CLI `kartograf download` — flagi, statusy, raport, plan

**Files:**
- Modify: `kartograf/cli/_parser.py` (grupa flag, `--plan`, pomoc `--campaigns`)
- Modify: `kartograf/cli/download_cmd.py`
- Test: `tests/test_cli.py` (nowe testy + dostosowanie starych)

**Interfaces:**
- Consumes: `UpdateMode`, `SheetFetch.status/version/newer/unverifiable`, `DownloadResult.unchanged/newer/unverifiable` (Task 5); `check_updates`, `upgrade`, `UpdatePlan` (Task 6)
- Produces: `args.check_updates: bool`, `args.upgrade: bool`, `args.force: bool`, `args.plan: str | None`; `_update_mode(args) -> UpdateMode | None`

- [ ] **Step 1: Napisz testy CLI (dopisz do `tests/test_cli.py`)**

Testy korzystaja z istniejacego w `tests/test_cli.py` wzorca patchowania `kartograf.cli.download_cmd.DownloadManager` (sprawdz najblizszy test sciezki godla, np. `grep -n "def test_download_.*godlo" tests/test_cli.py`, i uzyj tej samej fikstury/patcha). Wyjscie kieruj do `tmp_path / "out"`.

```python
def test_update_flags_are_mutually_exclusive(capsys):
    from kartograf.cli.commands import main

    with pytest.raises(SystemExit):
        main(["download", "N-34-139-C-a-3-1", "--upgrade", "--force"])
    assert "not allowed with" in capsys.readouterr().err


def test_plan_requires_check_or_upgrade(tmp_path, capsys):
    from kartograf.cli.commands import main

    code = main(["download", "N-34-139-C-a-3-1", "--plan", str(tmp_path / "p.json"),
                 "-o", str(tmp_path / "out")])
    assert code == 1
    assert "--plan" in capsys.readouterr().err


def test_update_mode_mapping():
    import argparse

    from kartograf.cli.download_cmd import _update_mode

    ns = argparse.Namespace(check_updates=False, upgrade=True, force=False)
    assert _update_mode(ns) == "upgrade"
    ns = argparse.Namespace(check_updates=False, upgrade=False, force=False)
    assert _update_mode(ns) is None


def test_check_updates_writes_plan_and_exit_code(tmp_path, capsys, monkeypatch):
    from kartograf.cli import download_cmd
    from kartograf.cli.commands import main
    from kartograf.download.updates import PlanItem, UpdatePlan

    plan = UpdatePlan(str((tmp_path / "out").resolve()), {}, "t", "v", (
        PlanItem("N-34-139-C-a-3-1", "newer", {"label": "2025-04-27_83233",
                 "sha256": "0" * 64}, ({"label": "2025-10-21_84183", "signal": {}},)),
        PlanItem("N-34-139-C-a-3-2", "check_failed", None, (), "down"),
    ))
    monkeypatch.setattr(download_cmd, "check_updates", lambda m, g: plan)
    out = tmp_path / "plan.json"
    code = main(["download", "N-34-139-C-a-3", "--scale", "1:10000",
                 "--check-updates", "--plan", str(out), "-o", str(tmp_path / "out")])
    text = capsys.readouterr()
    assert code == 1  # check_failed
    assert "nowsza 2025-10-21_84183" in text.out
    assert "nie udalo sie sprawdzic" in text.out
    assert UpdatePlan.from_json(out.read_text()) == plan


def test_old_kampanie_dir_info(tmp_path, capsys, monkeypatch):
    from kartograf.cli.download_cmd import _info_old_campaigns_dir

    seg = tmp_path / "out" / "nmt" / "pl_1992_1m_evrf2007"
    (seg / "kampanie").mkdir(parents=True)
    _info_old_campaigns_dir(seg)
    _info_old_campaigns_dir(seg)
    err = capsys.readouterr().err
    assert err.count("kampanie/ z wersji 0.7.0") == 1


def test_check_updates_rejected_for_laz(tmp_path, capsys):
    from kartograf.cli.commands import main

    code = main(["download", "--product", "laz", "--bbox", "1,1,2,2",
                 "--check-updates", "-o", str(tmp_path / "out")])
    assert code == 1
    assert "jeszcze nieobslugiwane" in capsys.readouterr().err
```

(`test_check_updates_writes_plan_and_exit_code` musi tez podstawic `DownloadManager`/provider bez sieci — uzyj tego samego patcha co istniejace testy godla w `tests/test_cli.py`; `check_updates` jest podmienione, wiec manager nie wykonuje zapytan.)

- [ ] **Step 2: Uruchom — maja nie przejsc**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "update or plan or kampanie_dir or rejected_for_laz"`
Expected: FAIL

- [ ] **Step 3: Parser**

W `_parser.py` zastap definicje `--force` grupa:

```python
    update_group = download_parser.add_mutually_exclusive_group()
    update_group.add_argument(
        "--check-updates",
        action="store_true",
        help="Tylko sprawdz u zrodla, czy sa nowsze wersje lokalnych danych "
        "(nic nie pobiera; kod 1, gdy czegos nie udalo sie sprawdzic)",
    )
    update_group.add_argument(
        "--upgrade",
        action="store_true",
        help="Pobierz nowsze wersje potwierdzone przez sprawdzenie u zrodla "
        "(bez taniego sygnalu: lokalna wersja; zrodlo niedostepne: blad)",
    )
    update_group.add_argument(
        "--force",
        action="store_true",
        help="Pobierz ponownie wszystko z zakresu zadania i odswiez cache "
        "metadanych; ta sama tresc = bez nowej wersji (z --target-crs PL: "
        "przebudowuje wycinek)",
    )
    download_parser.add_argument(
        "--plan",
        metavar="FILE",
        help="Z --check-updates: zapisz plan aktualizacji (JSON "
        "kartograf-plan/1); z --upgrade: wykonaj dokladnie ten plan",
    )
```

W pomocy `--campaigns` zamien `do <segment>/kampanie/` na `do <segment>/versions/`.

- [ ] **Step 4: `download_cmd.py` — mapowanie, walidacja, cache**

Dodaj na poziomie modulu:

```python
from kartograf.download.updates import UpdatePlan, check_updates, upgrade
from kartograf.download.versions import VERSIONS_DIR

_old_campaign_dirs_shown: set[Path] = set()


def _update_mode(args: argparse.Namespace):
    """``--check-updates``/``--upgrade``/``--force`` -> ``update`` (ADR-032)."""
    if getattr(args, "check_updates", False):
        return "check"
    if getattr(args, "upgrade", False):
        return "upgrade"
    if getattr(args, "force", False):
        return "force"
    return None


def _reject_update_modes(args: argparse.Namespace, what: str) -> bool:
    """``--check-updates``/``--upgrade`` for flows not yet on versions (plan 2/3)."""
    mode = _update_mode(args)
    if mode in ("check", "upgrade"):
        flag = "--check-updates" if mode == "check" else "--upgrade"
        print(f"Error: {flag} jeszcze nieobslugiwane dla {what}", file=sys.stderr)
        return True
    return False


def _info_old_campaigns_dir(segment_root: Path) -> None:
    """One ``Info:`` per segment with a pre-ADR-032 ``kampanie/`` directory."""
    old = segment_root / "kampanie"
    if old.is_dir() and segment_root not in _old_campaign_dirs_shown:
        _old_campaign_dirs_shown.add(segment_root)
        print(
            f"Info: katalog kampanie/ z wersji 0.7.0 nie jest uzywany ({old}); "
            f"dane zostana pobrane ponownie do {VERSIONS_DIR}/",
            file=sys.stderr,
        )
```

W `cmd_download` (zaraz po `_cache_warnings_shown.clear()`):

```python
    _old_campaign_dirs_shown.clear()
    if getattr(args, "plan", None) and _update_mode(args) not in ("check", "upgrade"):
        print("Error: --plan wymaga --check-updates albo --upgrade", file=sys.stderr)
        return 1
```

Na poczatku `_cmd_download_laz`, `_run_cz`, `_download_pl_cutout` i `_cmd_download_bbox` (tor WCS bez `--target-crs`, jesli nie przechodzi przez liste arkuszy): `if _reject_update_modes(args, "<opis toru>"): return 1` z opisem odpowiednio `"LAZ"`, `"CZ"`, `"wycinka --target-crs"`, `"--bbox WCS"`.

W `_pl_metadata_cache` zmien `_cli_metadata_cache(bool(args.force))` na `_cli_metadata_cache(_update_mode(args) is not None)` — sprawdzanie i aktualizacja czytaja skorowidz na swiezo. Docstring: "``--force``/``--check-updates``/``--upgrade`` = ``MetadataCache(refresh=True)``".

- [ ] **Step 5: `download_cmd.py` — tor godla i listy**

W torze godla (`cmd_download`, sekcja "Sheet code mode"):
- `skip_existing = not args.force` zamien na `update = _update_mode(args)`;
- po utworzeniu `manager`: `_info_old_campaigns_dir(manager.storage.version_parts(...)[0])` — dla godla `args.godlo` (dla godla grubszego niz 1:10000 uzyj pierwszego potomka z `manager.expand_sheets([args.godlo])[0]`);
- jesli `update == "check"`: wykonaj `_run_check(manager, [args.godlo], args)` i zwroc jego kod (ponizej); jesli `update == "upgrade"` i `args.plan`: `_run_plan_upgrade(manager, args)` i zwroc jego kod;
- wywolania `download_hierarchy`/`download_sheet` dostaja `update=update` zamiast `skip_existing=...`;
- komunikaty pojedynczego arkusza zastap funkcja `_print_sheet_status(args.godlo, sheet, result)`:

```python
def _print_sheet_status(godlo: str, sheet: SheetFetch | None, path: Path) -> None:
    """One status line per sheet (spec 4.5) + ``Info:`` about newer versions."""
    if sheet is None or sheet.version is None:
        print(f"Downloaded to {path}")
        return
    label = sheet.version.dirname
    if sheet.status == "new":
        print(f"{godlo}: nowa wersja {label} -> {path}")
    elif sheet.status == "unchanged":
        print(f"{godlo}: bez zmian (wersja {label}) -> {path}")
    else:
        hint = "" if sheet.newer or sheet.unverifiable else " (--check-updates)"
        print(f"{godlo}: lokalna wersja {label}{hint} -> {path}")
    if sheet.newer:
        print(
            f"Info: {godlo}: dostepna nowsza wersja {sheet.newer[0]} (--upgrade)",
            file=sys.stderr,
        )
    if sheet.unverifiable:
        print(
            f"Info: {godlo}: zrodlo bez taniego sygnalu — sprawdzenie wymaga "
            "ponownego pobrania (--force)",
            file=sys.stderr,
        )
```

(wywolaj ja zamiast galezi `Skipped ... already exists` / `Downloaded to`, z zachowaniem `-q`: przy `args.quiet` drukuj tylko linie `Info:`). Komunikat I-1 (`sheet.unverified`) zmien na "zrodlo niedostepne — uzyto lokalnej wersji bez sprawdzenia nowszej".

W `_download_godlo_list` i `_download_pl_sheet_list`: parametr `skip_existing` -> `update`, przekazywany do `download_sheets(update=update)`; w `_download_pl_sheet_list` analogiczne rozgalezienie `check`/`upgrade --plan` jak w torze godla (lista godel = `godlo_list`).

W `_finish_pl_sheets` po linii `Downloaded N files...` dodaj:

```python
        if result.unchanged:
            print(f"{len(result.unchanged)} bez zmian (ta sama tresc)")
    if result.newer:
        print(
            f"Info: dla {len(result.newer)} arkuszy dostepne nowsze wersje "
            "(--check-updates pokaze liste, --upgrade pobierze)",
            file=sys.stderr,
        )
    if result.unverifiable:
        print(
            f"Info: {len(result.unverifiable)} arkuszy bez taniego sygnalu "
            "— sprawdzenie wymaga --force",
            file=sys.stderr,
        )
```

(`if result.unchanged` wewnatrz bloku `if not quiet and paths:` w galezi bez `campaigns == "all"`; dwa `Info:` poza nim, bo stderr nie jest wyciszany przez `-q`). Zmien tresc `_warn_unverified` na "zrodlo niedostepne — dla N arkuszy uzyto lokalnej wersji bez sprawdzenia nowszej".

- [ ] **Step 6: `download_cmd.py` — raport sprawdzenia i plan**

```python
_CHECK_LINES = {
    "current": "aktualne ({local})",
    "newer": "nowsza {available} (lokalnie {local})",
    "missing": "do pobrania ({available})",
    "unverifiable": "nie da sie sprawdzic bez pobrania (lokalnie {local})",
    "check_failed": "nie udalo sie sprawdzic ({error})",
    "no_coverage": "brak danych u zrodla",
}


def _run_check(manager: DownloadManager, godla: list[str], args) -> int:
    """``--check-updates``: report per sheet, optional plan file; never downloads."""
    try:
        plan = check_updates(manager, godla)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for item in plan.items:
        local = item.local["label"] if item.local else "-"
        available = ", ".join(a["label"] for a in item.available) or "-"
        line = _CHECK_LINES[item.status].format(
            local=local, available=available, error=item.error
        )
        print(f"{item.sheet}: {line}")
    if args.plan:
        Path(args.plan).write_text(plan.to_json(), encoding="utf-8")
        print(f"Plan aktualizacji zapisany: {args.plan}")
    return 1 if plan.has_failures else 0


def _run_plan_upgrade(manager: DownloadManager, args) -> int:
    """``--upgrade --plan FILE``: execute exactly the saved plan."""
    try:
        plan = UpdatePlan.from_json(Path(args.plan).read_text(encoding="utf-8"))
        report = upgrade(manager, plan)
    except OSError as e:
        print(f"Error: odczyt planu {args.plan}: {e}", file=sys.stderr)
        return 1
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for sheet in report.stale:
        print(
            f"Error: {sheet}: zrodlo zmienilo sie od planu — pominiete "
            "(uruchom ponownie --check-updates)",
            file=sys.stderr,
        )
    if report.result is None:
        if not args.quiet:
            print("Plan nie zawiera nic do pobrania")
        return 1 if report.stale else 0
    code = _finish_pl_sheets(
        report.result,
        list(report.result.succeeded),
        output_dir=Path(args.output),
        quiet=args.quiet,
        campaigns=manager.campaigns,
    )
    return 1 if report.stale else code
```

- [ ] **Step 7: Dostosuj stare testy CLI**

Uruchom `.venv/bin/python -m pytest tests/test_cli.py -q -x` i popraw: oczekiwane `Skipped ... already exists`/`Downloaded to` w torze godla -> nowe linie statusu z `_print_sheet_status`; patche `skip_existing=` -> `update=`; asercje tekstu "skorowidz GUGiK niedostepny" -> "zrodlo niedostepne"; `--force` dalej akceptowane (teraz w grupie). Nie zmieniaj oczekiwan torow LAZ/CZ/wycinka poza `--check-updates`/`--upgrade`.

- [ ] **Step 8: Brama i commit**

```bash
.venv/bin/python -m pytest tests/ -m "not live" -q
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check . && .venv/bin/python -m mypy kartograf/ tests/
git add kartograf/cli/_parser.py kartograf/cli/download_cmd.py tests/test_cli.py
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "feat(cli)!: --check-updates, --upgrade, --plan; statusy wersji arkuszy PL

BREAKING CHANGE: --force pobiera ponownie bez nadpisywania (ta sama
tresc = bez nowej wersji); domyslne uruchomienie nie pobiera nowszej
kampanii.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: ADR-032 i CHANGELOG

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF!), `docs/CHANGELOG.md`, `docs/PROGRESS.md`

**Interfaces:**
- Consumes: decyzje D1-D12 ze specu; wynik Task 2-7
- Produces: ADR-032 w indeksie i tresci; sekcja `[0.7.1] - Unreleased` z wpisami BREAKING (wydanie docelowe 0.8.0 — numer sekcji zmienia sie przy wydaniu)

- [ ] **Step 1: ADR-032 z zachowaniem CRLF**

Edytuj `docs/DECISIONS.md` skryptem Pythona czytajacym i zapisujacym w trybie binarnym (`newline=""`), zeby zachowac `\r\n`. Dodaj wiersz indeksu po ADR-031:

```
| [ADR-032](#adr-032-magazyn-wersjonowany) | Magazyn wersjonowany: wersje identyfikowane trescia, tryby aktualizacji, plan kartograf-plan/1 | 2026-10-08 | Przyjeta — czesciowo zastepuje [ADR-030](#adr-030-strategie-kampanii-newestall---min-year-i-uklad-kampanie-z-dowiazaniem) (uklad `kampanie/`, automatyczne pobieranie nowszej kampanii, `extra.parent_requests`) |
```

i sekcje `## ADR-032: Magazyn wersjonowany` na koncu pliku z podsekcjami **Kontekst** (tekst sekcji 1 specu, 3-4 zdania), **Decyzja** (tabela D1-D12 ze specu sekcja 2, skopiowana), **Konsekwencje** (zmiany lamiace: `kampanie/` -> `versions/`, `--force`, brak automatycznej aktualizacji, `parent_requests`, `skip_existing` -> `update`; plany 2/3 i 3/3 dla pozostalych produktow), **Odsylacze** (spec, plan). W wierszu indeksu ADR-030 dopisz "; czesciowo zastapiona przez [ADR-032](#adr-032-magazyn-wersjonowany)". Weryfikacja CRLF:

```bash
.venv/bin/python - <<'EOF'
data = open("docs/DECISIONS.md", "rb").read()
assert b"\n" not in data.replace(b"\r\n", b""), "LF bez CR w DECISIONS.md"
print("CRLF OK")
EOF
git diff --stat docs/DECISIONS.md   # liczba zmienionych linii = tylko dodane/zmienione, nie caly plik
```

- [ ] **Step 2: CHANGELOG**

W `docs/CHANGELOG.md` w sekcji `## [0.7.1] - Unreleased` dodaj (przed `### Dodane`):

```markdown
### Zmiany lamiace (BREAKING)

- **Magazyn wersjonowany (ADR-032), arkusze PL NMT/NMPT/orto:** pliki
  leza w `<segment>/versions/<etykieta>_<sha8>/` (dotad `kampanie/`);
  katalog `kampanie/` z 0.7.0 nie jest czytany ani migrowany — dane
  pobierane sa ponownie.
- `DownloadManager.download_sheet/download_hierarchy/download_sheets`:
  parametr `skip_existing` zastapiony przez `update` (`None`, `"upgrade"`,
  `"force"`); domyslne uruchomienie NIE pobiera nowszej kampanii
  (informuje: `SheetFetch.newer`, `DownloadResult.newer`).
- `--force` pobiera ponownie bez nadpisywania: ta sama tresc nie tworzy
  nowej wersji, inna tworzy nowa.
- Usuniete `extra.parent_requests` (sidecar wersji jest niezmienny).
```

i w `### Dodane`:

```markdown
- Sidecar wersji: `sha256` i `extra.version` (`label`, `label_source`).
- `kartograf download --check-updates` (raport bez pobierania, kod 1 gdy
  czegos nie udalo sie sprawdzic), `--upgrade` i `--plan FILE`; w bibliotece
  `check_updates`, `upgrade`, `UpdatePlan` (`kartograf-plan/1`), `PlanItem`,
  `UpgradeReport`, `VersionRef`.
```

- [ ] **Step 3: PROGRESS**

W `docs/PROGRESS.md` w tabeli statusu zmien wiersz roadmapy na "🔧 W trakcie" z uwaga "podprojekt 1: plan 1/3 (arkusze PL) wykonany na `feat/versioned-store`; plany 2/3 (LAZ, CZ, wycinki) i 3/3 (land cover, HSG, dokumentacja) do napisania"; w backlogu "Do v1.0.0" przy "1. Magazyn wersjonowany" dopisz "(plan 1/3 wykonany)"; dodaj wpis sesji z lista commitow.

- [ ] **Step 4: Commit**

```bash
git add docs/DECISIONS.md docs/CHANGELOG.md docs/PROGRESS.md
git diff --cached --stat
! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "docs(adr): ADR-032 magazyn wersjonowany; CHANGELOG i PROGRESS (plan 1/3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Weryfikacja na zywo (arkusz NMT)

**Files:** brak zmian w repo (chyba ze test wykaze blad — wtedy osobny commit z testem odtwarzajacym).

**Interfaces:**
- Consumes: CLI z Task 7.
- Produces: raport dla uzytkownika (wyniki komend ponizej).

- [ ] **Step 1: Pelne pobranie do pustego katalogu danych**

Katalog danych poza repo (podaje uzytkownik; ponizej `<katalog-danych>`), CLI z korzenia repo:

```bash
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e
```

Expected: linia `N-34-139-C-a-3-1: nowa wersja <data>_<id>_<sha8> -> ...`; plik w `nmt/pl_1992_1m_evrf2007/versions/<data>_<id>_<sha8>/N-34/139/C/a/3/1/`, sidecar z `sha256` i `extra.version`; sciezka standardowa = hardlink (`stat -c %i` obu plikow rowny).

- [ ] **Step 2: Ponowne uruchomienie bez zmian**

```bash
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e
```

Expected: `lokalna wersja ...`, brak pobierania (czas < kilka s), brak nowego katalogu wersji.

- [ ] **Step 3: `--check-updates` z planem, `--upgrade --plan`, `--force`**

```bash
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e --check-updates --plan <katalog-danych>/vs-e2e-plan.json; echo "exit=$?"
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e --upgrade --plan <katalog-danych>/vs-e2e-plan.json; echo "exit=$?"
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e --force; echo "exit=$?"
ls <katalog-danych>/vs-e2e/nmt/pl_1992_1m_evrf2007/versions/
```

Expected: `aktualne (...)`, exit 0, plan JSON `kartograf-plan/1`; upgrade: "Plan nie zawiera nic do pobrania", exit 0; force: `bez zmian (wersja ...)`, exit 0; w `versions/` jeden katalog wersji.

- [ ] **Step 4: `--campaigns all` dla arkusza z wieloma kampaniami**

```bash
.venv/bin/kartograf download N-34-139-C-a-3-1 -o <katalog-danych>/vs-e2e --campaigns all --upgrade
ls <katalog-danych>/vs-e2e/nmt/pl_1992_1m_evrf2007/versions/
```

Expected: katalog wersji dla kazdej kampanii; sciezka standardowa na najnowsza (`extra.link_target` w sidecarze standardowym).

- [ ] **Step 5: Raport**

Przekaz uzytkownikowi wyniki krokow 1-4 (komendy, kody wyjscia, listing `versions/`). Kazda niezgodnosc: test odtwarzajacy w `tests/` (failing), poprawka, osobny commit.
