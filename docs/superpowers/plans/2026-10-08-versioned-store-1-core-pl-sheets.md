# Magazyn wersjonowany — plan 1/3: fundament i arkusze PL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-11 (przepisany od nowa; wersja z 2026-10-08 nieaktualna — historia w gicie)

**Goal:** Wersje identyfikowane trescia w ukladzie `<segment>/versions/<hierarchia>/<etykieta>_<sha8>/<nazwa>` z niezmiennym sidecarem, wylacznym zapisem (`os.link`), wymaganymi hardlinkami i trybami `update` (domyslny / `check` / `upgrade` / `force`) oraz planem aktualizacji `kartograf-plan/1` — dla arkuszy PL NMT/NMPT/orto pobieranych przez `DownloadManager`, w bibliotece i w CLI `kartograf download` (godlo, hierarchia, lista, `--bbox`/`--geometry` bez `--target-crs`).

**Architecture:** Nowy modul `kartograf/download/versions.py` (tozsamosc, zapis, lista wersji, sprzatanie). `download/links.py` zostaje mechanizmem dowiazan (standardowe i `full_sheet/`), wylacznie hardlink, klucz wersji zamiast klucza kampanii. `DownloadManager` zastepuje `skip_existing` parametrem `update`; kampania GUGiK = wersja z etykieta `<aktualnosc>_<id>`. Nowy modul `kartograf/download/updates.py` (plan aktualizacji). CLI: `--check-updates` / `--upgrade` / `--force` (grupa wykluczajaca) i `--plan`.

**Spec:** `docs/superpowers/specs/2026-10-08-versioned-store-design.md` — ZAAKCEPTOWANY 2026-10-11 (D1-D24), uzupelniony 2026-10-12 o D25 (samoopisowe nazwy plikow). Numeracja decyzji (Dn) w tym planie odnosi sie do specu.

**Poza planem 1/3 (osobne plany po wykonaniu tego):**
- plan 2/3: inwentaryzacja sygnalow (spec sekcja 8) dla zrodel spoza arkuszy PL, LAZ, CZ (godlo i `bbox/`), wycinki PL z WCS `bbox/` (D15; nazwa samoopisowa wg D25, np. `nmt_<wsp>.tif`), nadpisanie starych plikow LAZ/CZ (D24), `DownloadManager.download_bbox`, `extra.http` i sygnal `http`;
- plan 3/3: land cover (BDOT10k, CORINE, SoilGrids) i HSG w ukladzie `data/` (D11) z samoopisowymi nazwami plikow (D25, np. `bdot10k_teryt_1206.gpkg`, nie `1206.gpkg`), `keep_raw`, pelna dokumentacja i E2E calosci.
Galaz `feat/versioned-store` trafia do `develop` dopiero po planie 3/3.

---

## Global Constraints

- Python wylacznie z `.venv`: `.venv/bin/python -m pytest ...`, `.venv/bin/python -m ruff ...`, `.venv/bin/python -m mypy ...`, `.venv/bin/kartograf ...`.
- Testy offline: `-m "not live"` (`tests/conftest.py` przewraca kazde polaczenie poza loopback). Brama przed KAZDYM commitem:
  `.venv/bin/python -m pytest tests/ -m "not live" -q` zielone, `.venv/bin/python -m ruff check .` i `.venv/bin/python -m ruff format --check .` czyste, `.venv/bin/python -m mypy kartograf/ tests/` bez bledow.
- Commity: Conventional Commits z opisem po polsku; docstringi i komentarze po angielsku; dokumentacja po polsku. Autor `Daldek <git@debever.pl>`. **Bez stopki `Co-Authored-By`.**
- Kazdy commit wylacznie przez straznik wzorcow:
  `! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "..."` — trafienie przerywa commit. Brak pliku wzorcow = zatrzymaj sie i zapytaj. Tresci wzorcow nie wpisuj do repo ani komunikatu.
- Nowe identyfikatory (kod, API, sidecar, plan aktualizacji) wylacznie po angielsku (ADR-031). Komunikaty CLI po polsku bez znakow diakrytycznych w kodzie.
- `docs/DECISIONS.md` ma konce linii CRLF — po edycji sprawdz, ze kazda linia konczy sie `\r\n`.
- Dane testow na zywo tylko poza repo i poza `/tmp`, z jawnym `--output`; katalog wskazuje uzytkownik; sciezki nie zapisuj w repo.
- Stale: `VERSIONS_DIR = "versions"`, `INCOMING_DIR = ".incoming"`, `STALE_AFTER_S = 24 * 3600`, `PLAN_SCHEMA = "kartograf-plan/1"`.
- Tryby: `UpdateMode = Literal["check", "upgrade", "force"]`; brak trybu = `None` (domyslny).
- Testy: zachowanie, granice, niezmienniki, przejscia; nie okablowanie ani tekst zrodla. Testy stare, ktore pinuja usuwane zachowanie (`kampanie/`, kopia zamiast hardlinku, `parent_requests`, `skip_existing`), usuwaj albo przepisuj na nowe zachowanie — nie zostawiaj podwojnych sciezek.
- Nazwy plikow (D25): nazwa pliku w sciezce standardowej i w katalogu wersji jest ta sama i opisuje dane bez kontekstu katalogu. W planie 1/3 arkusze PL zachowuja `<godlo>.<ext>` (wyjatek D25); kazda nowa nazwa pliku wprowadzana przez ten plan (np. pliki testowe, plan aktualizacji) tez ma byc samoopisowa.

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Sygnal przy D23 w planie 1/3 = etykieta.** Dla kampanii etykieta `<aktualnosc>_<id>` wynika z rekordu skorowidza, wiec "inny sygnal" = inna etykieta przy `label_source` `campaign`/`edition`. Etykieta `downloaded` nie jest sygnalem (zawsze `unchanged`). `extra.http` jako sygnal dochodzi w planie 2/3.
2. **D20 (jeden odczyt):** ASC — sha256 i pokrycie liczone w jednym strumieniu (parser liczb w tym samym przebiegu po 1 MiB). GeoTIFF (orto) — sha256 w strumieniu, pokrycie przez `rasterio` zaraz potem (dane w cache stron systemu). `build_metadata(digest=)` nigdy nie czyta pliku drugi raz. Zapisane w docstringu `read_content`.
3. **Granulacja pozycji:** `newest` — jedna pozycja na arkusz; `all` — jedna pozycja na (arkusz, kampania); `--full-sheet` — dodatkowa pozycja "najnowszy pelny lot w zakresie".
4. **Tozsamosc magazynu w planie aktualizacji:** `str(Path(output_dir).resolve())`; porownanie dokladne.
5. **Host w katalogu roboczym:** `socket.gethostname()` oczyszczony do `[A-Za-z0-9-]` (reszta -> `-`), token `secrets.token_hex(4)`.
6. **Klucz "najnowszej wersji":** kampania — `(extra.campaign.date, extra.campaign.pzgik_date or "", extra.source.url)` (jak dzis `campaign_key_from_sidecar`); pozostale — `(data z etykiety albo "", downloaded_at, sha256)`. Wersja bez czytelnego sidecara nie jest wazna, wiec fallbacku z nazwy katalogu nie ma.
7. **Tor bez kampanii (`_fetch_sheet_plain`)** dostaje wersje z etykieta `downloaded` (providery bez kampanii: atrapy testowe, obce providery).
8. **Tymczasowe odrzucenie w CLI:** `--check-updates`/`--upgrade` dla torow z planow 2/3 i 3/3 (LAZ, CZ, `--target-crs`, `landcover`, `soilgrids`) konczy sie `Error:` (kod 1) przed siecia; `--force` dziala tam jak dzis. Galaz nie trafia do `develop` przed planem 3/3, ktory usuwa to odrzucenie.

## Pytania do uzytkownika (przed Task 1)

- **Kolejnosc wzgledem pozostalych zmian lamiacych 0.8.0** (`godlo` -> `sheet` w CLI i API, `--product` wymagane, `--campaigns` -> `--all-campaigns`, parametry wymagane w API). Wszystkie dotykaja `cli/_parser.py`, `cli/download_cmd.py` i sygnatur `DownloadManager`, ktore ten plan przebudowuje. Rekomendacja: wykonac je NAJPIERW na `develop` (osobne galezie, jak w backlogu), potem `git rebase develop` tej galezi i dopiero Task 1 — kod magazynu powstaje od razu z nowymi nazwami, bez konfliktow na dlugo zyjacej galezi. Jesli uzytkownik wybierze kolejnosc odwrotna, Task 6-7 uzywaja dzisiejszych nazw, a zmiany nazw ida po merge planu 3/3.

## Review Focus

1. **Wylaczny zapis (D18):** dwa zapisy tej samej tresci (takze rownolegle) koncza w jednym katalogu wersji, drugi `unchanged`; plik pod nazwa wersji o innej tresci = `DownloadError`, pierwsza tresc nietknieta. Testy: Task 1 `test_commit_concurrent_same_content_one_version`, `test_commit_existing_target_other_content_is_error`.
2. **Naprawa wersji bez sidecara tylko po sprawdzeniu sha256 (D18):** Task 1 `test_commit_repairs_orphan_only_when_sha_matches`.
3. **Sprzatanie tylko wpisow starszych niz 24 h (D19):** mlodszy katalog roboczy innego procesu nie jest usuwany. Task 1 `test_cleanup_keeps_young_incoming`.
4. **D23 `relabeled`:** ta sama tresc z nowa etykieta kampanii = nowy katalog z hardlinkiem i nowym sidecarem, dowiazanie przechodzi na nowa etykiete. Task 1 `test_commit_same_content_new_campaign_label_is_relabeled`, Task 4 `test_relabeled_campaign_moves_link`.
5. **Brak hardlinku = blad, nigdy kopia (D22):** Task 3 `test_link_without_hardlink_support_is_error`.
6. **D14 (zakres lat, skorowidz niedostepny):** wszystkie arkusze z lokalna wersja w zakresie = lokalne + ostrzezenie; brak jednego = blad zadania bez pobran. Task 5 `test_range_index_down_all_local_uses_local`, `test_range_index_down_one_missing_fails_task`.
7. **Sidecar wersji niezmienny (D12/D13):** pokrycie zapisane przy zapisie; zadne pozniejsze zadanie nie zmienia bajtow sidecara wersji. Task 4 `test_version_sidecar_bytes_never_change`.
8. **Plan nieaktualny / obcy magazyn:** Task 6 `test_upgrade_stale_item_fails_others_run`, `test_upgrade_rejects_foreign_store`.

---

## Mapa plikow

| Plik | Odpowiedzialnosc |
|---|---|
| `kartograf/download/versions.py` (NOWY) | `VersionRef`, `ContentDigest`, `LocalVersion`, `VersionCommit`, `read_content`, `new_incoming_dir`, `commit_version`, `list_versions`, `newest_version`, `version_key`, `cleanup_stale` |
| `kartograf/sources/sidecar.py` | `build_metadata(digest=)`, `emit_sidecar(digest=, version=)`, `extra.version`, `fsync` w `write_sidecar(atomic=True)` |
| `kartograf/download/links.py` | wylacznie hardlink (`link_atomic`), `linked_version`, `version_key_of`; `update_sidecar_extra` tylko dla sidecarow dowiazan |
| `kartograf/download/campaigns.py` | bez `CAMPAIGNS_DIR`; `measure_coverage` przyjmuje gotowy odczyt (D20) |
| `kartograf/download/storage.py` | `get_versions_root`, `list_files` pomija `versions/` i `full_sheet/`, `has_legacy_campaigns`; bez `get_campaign_path` |
| `kartograf/download/manager.py` | `UpdateMode`, `update=` zamiast `skip_existing`, kampanie i tor bez kampanii na wersjach, D13, D14, `relabeled`, `SheetFetch.status/version/newer`, bez `_note_reuse` |
| `kartograf/download/updates.py` (NOWY) | `PlanItem`, `UpdatePlan` (`kartograf-plan/1`), `check_updates`, `upgrade`, `UpgradeReport` |
| `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py` | flagi, mapowanie na `update`, linie statusu, liczniki, raport `check`, `--plan`, `Info:` o `kampanie/`, tymczasowe odrzucenie torow 2/3 i 3/3 |
| `kartograf/__init__.py` | eksporty `VersionRef`, `UpdatePlan`, `PlanItem`, `UpgradeReport`, `check_updates`, `upgrade` |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`, `docs/PROGRESS.md` | ADR-036, BREAKING, opis ukladu i trybow dla arkuszy PL |

Fakty o obecnym kodzie (zweryfikowane 2026-10-11 na `feat/versioned-store` po rebase na `develop`):
- `DownloadManager.download_sheet/download_hierarchy/download_sheets(..., skip_existing: bool = True, ...)` — `kartograf/download/manager.py:620-626`, `703-710`, `813-819`; wewnetrznie `_fetch_sheet` (853), `_fetch_sheet_plain` (875), `_fetch_campaigns` (901-1229), `_download_many` (1375), I-1 `_local_newest` (1236), pomiar pokrycia `_add_range_flights` (1175-1226, `update_sidecar_extra` w 1210 i 1225), `_write_sidecar` (1559), `_write_campaign_sidecar` (1600), `_note_reuse` (1644).
- Plik kampanii: `FileStorage.get_campaign_path` (`kartograf/download/storage.py:255-263`), dowiazanie pelne `get_full_sheet_path` (265-272), `list_files` (470-498), `delete` (444-468).
- `link_atomic` z kopia zapasowa — `kartograf/download/links.py:73-109`; `ensure_link(link, target, key, *, refresh)` — 294-331; `linked_campaign` 171-214; `campaign_key_from_sidecar` 112-141; `update_sidecar_extra` 252-283.
- `build_metadata` liczy `file_digest` z gotowego pliku — `kartograf/sources/sidecar.py:214-217`; `write_sidecar(atomic=True)` bez `fsync` — 258-270; `emit_sidecar` 284-358.
- `measure_coverage(path, ext)` — `kartograf/download/campaigns.py:367-435`; `CampaignRef.dirname/sort_key/to_extra` — 215-283.
- CLI: `--force` `kartograf/cli/_parser.py:206-215`, `--campaigns` 179-190, `--full-sheet` 259-269; `skip_existing = not args.force` w `kartograf/cli/download_cmd.py:1103` i `1835` (arkusze PL), `2339` (CZ godlo, plan 2/3), `run_laz_download(force=args.force)` 2059 (plan 2/3); `_pl_metadata_cache` 219; podsumowania 1150-1170, 1296-1298, 1378-1379; kody wyjscia `_finish_pl_sheets` 1313-1408.
- Testy: `tests/test_manager_campaigns.py` (helpery `FakeCampaignProvider` 107, `c14_fake` 701, `std_path` 176, `campaign_path` 181, `meta` 199, `deny_links` 219), `tests/test_links.py`, `tests/test_campaigns.py`, `tests/test_campaigns_flow.py`, `tests/test_storage.py`, `tests/test_sidecar*.py`, `tests/test_cli.py`.

---

### Task 1: Modul `versions.py` — tozsamosc, zapis wylaczny, lista, sprzatanie

**Files:**
- Create: `kartograf/download/versions.py`, `tests/test_versions.py`

**Interfaces:**
- Consumes: `kartograf.sources.sidecar.file_digest` (wzorzec odczytu 1 MiB), `kartograf.exceptions.DownloadError`
- Produces:
  ```python
  VERSIONS_DIR = "versions"; INCOMING_DIR = ".incoming"; STALE_AFTER_S = 86400
  LabelSource = Literal["campaign", "edition", "downloaded"]
  CommitStatus = Literal["new", "unchanged", "relabeled"]

  @dataclass(frozen=True)
  class VersionRef:
      label: str
      label_source: LabelSource
      def to_extra(self) -> dict: ...  # {"label": ..., "label_source": ...}
      @staticmethod
      def downloaded(now: datetime | None = None) -> "VersionRef": ...  # UTC RRRR-MM-DD

  @dataclass(frozen=True)
  class ContentDigest:
      sha256: str
      size_bytes: int
      coverage: float | None = None

  @dataclass(frozen=True)
  class LocalVersion:
      path: Path          # data file inside versions/<hier>/<label>_<sha8>/
      label: str
      label_source: str
      sha256: str
      meta: dict          # parsed version sidecar

  @dataclass(frozen=True)
  class VersionCommit:
      status: CommitStatus
      path: Path
      sha256: str
      label: str

  def read_content(path: Path, *, ext: str, coverage: bool) -> ContentDigest
  def new_incoming_dir(versions_root: Path) -> Path
  def commit_version(staged: Path, versions_root: Path, name: str, version: VersionRef,
                     digest: ContentDigest, write_sidecar: Callable[[Path, VersionRef, ContentDigest], None]
                     ) -> VersionCommit
  def list_versions(versions_root: Path, name: str) -> list[LocalVersion]
  def version_key(v: LocalVersion) -> tuple[str, str, str]
  def newest_version(versions: Iterable[LocalVersion]) -> LocalVersion | None
  def cleanup_stale(versions_root: Path, *, now: float | None = None) -> None
  ```

- [ ] **Step 1: Testy (`tests/test_versions.py`)**

```python
"""Versioned store core (spec 3, 3.1; D17-D23)."""

import json
import os
import threading
import time
from pathlib import Path

import pytest

from kartograf.download import versions as v
from kartograf.exceptions import DownloadError

NAME = "N-34-139-C-a-3-1.asc"
ASC = "ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n1 2\n-9999 4\n"


def stage(root: Path, body: str = ASC) -> Path:
    d = v.new_incoming_dir(root)
    p = d / NAME
    p.write_text(body)
    return p


def sidecar_writer(data: Path, ref: v.VersionRef, digest: v.ContentDigest) -> None:
    payload = {"sha256": digest.sha256, "extra": {"version": ref.to_extra()}}
    (data.parent / f"{data.name}.meta.json").write_text(json.dumps(payload))


def commit(root: Path, label="2025-06-02_91234", source="campaign", body=ASC):
    staged = stage(root, body)
    digest = v.read_content(staged, ext=".asc", coverage=True)
    return v.commit_version(
        staged, root, NAME, v.VersionRef(label, source), digest, sidecar_writer
    )


def test_layout_is_per_file_under_hierarchy(tmp_path):
    c = commit(tmp_path)
    assert c.status == "new"
    assert c.path.parent.name == f"2025-06-02_91234_{c.sha256[:8]}"
    assert c.path.parent.parent == tmp_path
    assert c.path.name == NAME
    assert not any((tmp_path / v.INCOMING_DIR).rglob(NAME))  # staged removed


def test_read_content_hashes_and_measures_in_one_pass(tmp_path):
    p = tmp_path / NAME
    p.write_text(ASC)
    d = v.read_content(p, ext=".asc", coverage=True)
    import hashlib

    assert d.sha256 == hashlib.sha256(ASC.encode()).hexdigest()
    assert d.size_bytes == len(ASC.encode())
    assert d.coverage == pytest.approx(0.75)


def test_commit_same_content_same_label_is_unchanged(tmp_path):
    first = commit(tmp_path)
    again = commit(tmp_path)
    assert again.status == "unchanged" and again.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_same_content_new_campaign_label_is_relabeled(tmp_path):
    first = commit(tmp_path, label="2024-05-10_80000")
    second = commit(tmp_path, label="2025-02-01_90000")
    assert second.status == "relabeled"
    assert second.path != first.path
    assert os.path.samefile(first.path, second.path)  # no extra space
    labels = {x.label for x in v.list_versions(tmp_path, NAME)}
    assert labels == {"2024-05-10_80000", "2025-02-01_90000"}


def test_commit_same_content_downloaded_label_is_unchanged(tmp_path):
    commit(tmp_path, label="2026-10-10", source="downloaded")
    again = commit(tmp_path, label="2026-10-11", source="downloaded")
    assert again.status == "unchanged"


def test_commit_other_content_is_new_version(tmp_path):
    commit(tmp_path)
    other = commit(tmp_path, label="2025-06-02_91235", body=ASC.replace("4\n", "5\n"))
    assert other.status == "new"
    assert len(v.list_versions(tmp_path, NAME)) == 2


def test_commit_existing_target_other_content_is_error(tmp_path):
    first = commit(tmp_path)
    first.path.write_text("uszkodzony")  # same name, different bytes
    (first.path.parent / f"{NAME}.meta.json").unlink()
    with pytest.raises(DownloadError, match="sha256"):
        commit(tmp_path)
    assert first.path.read_text() == "uszkodzony"  # never overwritten


def test_commit_repairs_orphan_only_when_sha_matches(tmp_path):
    first = commit(tmp_path)
    (first.path.parent / f"{NAME}.meta.json").unlink()  # interrupted before sidecar
    assert v.list_versions(tmp_path, NAME) == []  # invalid version skipped
    repaired = commit(tmp_path)
    assert repaired.status == "new" and repaired.path == first.path
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_concurrent_same_content_one_version(tmp_path):
    results = []
    barrier = threading.Barrier(2)

    def run():
        staged = stage(tmp_path)
        digest = v.read_content(staged, ext=".asc", coverage=False)
        barrier.wait()
        results.append(
            v.commit_version(
                staged, tmp_path, NAME, v.VersionRef("2025-06-02_91234", "campaign"),
                digest, sidecar_writer,
            ).status
        )

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["new", "unchanged"]
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_commit_without_hardlink_support_is_error(tmp_path, monkeypatch):
    def no_link(*a, **k):
        raise OSError(95, "Operation not supported")

    monkeypatch.setattr(v.os, "link", no_link)
    with pytest.raises(DownloadError, match="hardlink"):
        commit(tmp_path)


def test_sidecar_failure_removes_data(tmp_path):
    staged = stage(tmp_path)
    digest = v.read_content(staged, ext=".asc", coverage=False)

    def broken(*a):
        raise OSError("dysk pelny")

    with pytest.raises(DownloadError):
        v.commit_version(
            staged, tmp_path, NAME, v.VersionRef("x_1", "campaign"), digest, broken
        )
    assert not list(tmp_path.glob(f"x_1_*/{NAME}"))


def test_list_versions_ignores_incoming_and_empty_dirs(tmp_path):
    commit(tmp_path)
    stage(tmp_path)  # leftover staging
    (tmp_path / "2020-01-01_1_deadbeef").mkdir()  # empty version dir
    assert len(v.list_versions(tmp_path, NAME)) == 1


def test_cleanup_keeps_young_incoming(tmp_path):
    young = stage(tmp_path).parent
    old = stage(tmp_path).parent
    past = time.time() - v.STALE_AFTER_S - 10
    os.utime(old / NAME, (past, past))
    os.utime(old, (past, past))
    v.cleanup_stale(tmp_path)
    assert young.exists() and not old.exists()


def test_incoming_dirs_are_unique_per_call(tmp_path):
    assert v.new_incoming_dir(tmp_path) != v.new_incoming_dir(tmp_path)
```

- [ ] **Step 2: Uruchom — FAIL** (`ModuleNotFoundError: kartograf.download.versions`)

Run: `.venv/bin/python -m pytest tests/test_versions.py -q`

- [ ] **Step 3: Implementacja `kartograf/download/versions.py`**

Wymagania (kazde pokryte testem wyzej):
- `new_incoming_dir(root)`: `root / INCOMING_DIR / f"{host}_{os.getpid()}_{secrets.token_hex(4)}"`, `mkdir(parents=True)`; host z decyzji 5.
- `read_content`: jeden przebieg po 1 MiB; `hashlib.sha256().update(chunk)`; dla `.asc` z `coverage=True` inkrementalny parser: naglowek (do pierwszej linii zaczynajacej sie od liczby) daje `NODATA_value` (domyslnie brak), dalej liczy tokeny i tokeny != nodata (token przeciety granica bloku przenoszony do nastepnego); `coverage = valid / total` (0 tokenow = `None`). Dla innych rozszerzen z `coverage=True` — po hashu `measure_coverage(path, ext)` z `campaigns.py` (decyzja 2). Wyniki ASC musza byc rowne `measure_coverage` dla tego samego pliku (asercja w Task 4 na prawdziwych fixturach C14).
- `commit_version`:
  1. `cleanup_stale(root)`.
  2. Kandydaci: `list_versions(root, name)` z `sha256 == digest.sha256`. Jest kandydat z ta sama etykieta albo `version.label_source == "downloaded"` -> usun `staged` (i pusty katalog roboczy), `VersionCommit("unchanged", kandydat.path, ...)`. Jest kandydat z inna etykieta (`campaign`/`edition`) -> zrodlem `os.link` staje sie `kandydat.path` (D23), status docelowy `relabeled`.
  3. `fd = os.open(staged, os.O_RDONLY); os.fsync(fd)` (D21).
  4. `vdir = root / f"{version.label}_{digest.sha256[:8]}"`; `vdir.mkdir(parents=True, exist_ok=True)`; `target = vdir / name`.
  5. `os.link(source, target)`; `OSError` z `errno` w `{EPERM, EOPNOTSUPP, ENOTSUP, EXDEV, EMLINK}` albo `NotImplementedError` -> `DownloadError("... wymaga systemu plikow z hardlinkami (D22): ...")`.
  6. `FileExistsError`: `existing = file_digest(target)[0]`; rozne -> `DownloadError(f"{target}: plik wersji ma inne sha256 ({existing[:8]}) niz pobrany ({digest.sha256[:8]}) — kolizja albo uszkodzony plik")`; rowne i jest sidecar -> `unchanged`; rowne i brak sidecara -> naprawa: przejdz do 7 z `target`.
  7. Usun `staged` (jesli nie byl zrodlem `relabeled`, to tez — staged nie jest juz potrzebny) i pusty katalog roboczy.
  8. `write_sidecar(target, version, digest)`; wyjatek -> `target.unlink(missing_ok=True)` (tylko gdy ten zapis go utworzyl, nie przy naprawie istniejacego), `DownloadError`.
  9. Zwroc `VersionCommit(status, target, digest.sha256, version.label)`.
- `list_versions(root, name)`: tylko katalogi `root/*` z nazwa nie zaczynajaca sie od `.`; wazna wersja = istnieje `d/name` i czytelny `d/name.meta.json` z `sha256` i `extra.version.label`; niewazna = `logger.warning` (raz na katalog) i pominieta; puste katalogi pomijane bez ostrzezenia.
- `version_key(v)`: decyzja 6.
- `cleanup_stale(root, now)`: w `root/.incoming/*` i w pustych katalogach `root/*` usuwa wpisy, ktorych `mtime` (najnowszy z katalogu i plikow w nim) jest starszy niz `now - STALE_AFTER_S`; bledy `OSError` ignorowane (inny proces moze sprzatac rownolegle).

- [ ] **Step 4: PASS** — `.venv/bin/python -m pytest tests/test_versions.py -q`
- [ ] **Step 5: Brama i commit** — `feat(versions): magazyn wersji — zapis wylaczny, etykiety, sprzatanie`

---

### Task 2: Sidecar wersji — `extra.version`, `digest=`, `fsync`

**Files:**
- Modify: `kartograf/sources/sidecar.py` (`build_metadata` 182-242, `write_sidecar` 245-276, `emit_sidecar` 284-358)
- Test: `tests/test_sidecar.py`

**Interfaces:**
- Produces: `build_metadata(..., digest: tuple[str, int] | None = None, version: dict | None = None)`, `emit_sidecar(..., digest=None, version=None)`; `extra.version` w sidecarze; `write_sidecar(atomic=True)` robi `fsync` pliku tymczasowego przed `os.replace`.

- [ ] **Step 1: Testy**

```python
def test_build_metadata_with_digest_does_not_read_file(tmp_path, monkeypatch):
    from kartograf.sources import sidecar as s

    data = tmp_path / "N-34-139-C-a-3-1.asc"
    data.write_text("ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n1\n")
    monkeypatch.setattr(s, "file_digest", lambda p: pytest.fail("second read"))
    meta = s.build_metadata(
        s.get_source("pl.gugik.nmt_1m"),
        request={"sheet": "N-34-139-C-a-3-1"},
        data_path=data,
        digest=("ab" * 32, 7),
        version={"label": "2025-06-02_91234", "label_source": "campaign"},
    )
    assert (meta.sha256, meta.size_bytes) == ("ab" * 32, 7)
    assert meta.extra["version"] == {"label": "2025-06-02_91234", "label_source": "campaign"}


def test_atomic_sidecar_is_fsynced_before_replace(tmp_path, monkeypatch):
    from kartograf.sources import sidecar as s

    calls = []
    monkeypatch.setattr(s.os, "fsync", lambda fd: calls.append("fsync"))
    real_replace = s.os.replace
    monkeypatch.setattr(
        s.os, "replace", lambda a, b: (calls.append("replace"), real_replace(a, b))
    )
    data = tmp_path / "x.asc"
    data.write_text("ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\n1\n")
    s.emit_sidecar("pl.gugik.nmt_1m", data, request={"sheet": "N-34-139-C-a-3-1"},
                   required=True)
    assert calls[:2] == ["fsync", "replace"]
```

(`get_source` importowany w `sidecar.py` z `sources.registry`; jesli nie — uzyj tej samej sciezki importu, co istniejace testy `tests/test_sidecar.py`.)

- [ ] **Step 2: FAIL** (`unexpected keyword argument 'digest'`)
- [ ] **Step 3: Implementacja** — w `build_metadata` (214-217): `if digest is not None: sha256, size_bytes = digest` zamiast `file_digest`; `extra = {**(extra or {}), "version": dict(version)}` gdy `version`. W `write_sidecar(atomic=True)`: zapis przez `open(tmp, "w")` + `f.flush()` + `os.fsync(f.fileno())`, potem `os.replace`. `emit_sidecar` przekazuje `digest`/`version`. Docstring: "``digest`` — (sha256, size) computed by the store commit from the same read (D20); a version sidecar is written once (D12)."
- [ ] **Step 4: PASS** — `tests/test_sidecar*.py`
- [ ] **Step 5: Brama i commit** — `feat(sidecar): extra.version, digest z zapisu wersji i fsync`

---

### Task 3: Dowiazania tylko hardlink, klucz wersji, `FileStorage` na `versions/`

**Files:**
- Modify: `kartograf/download/links.py` (73-109, 112-214, 294-331), `kartograf/download/storage.py` (16, 255-263, 444-498), `kartograf/download/campaigns.py` (stala `CAMPAIGNS_DIR` 28)
- Test: `tests/test_links.py`, `tests/test_storage.py`

**Interfaces:**
- Produces:
  - `link_atomic(target, link) -> Literal["hardlink"]` — wylacznie `os.link` + `os.replace`; brak hardlinku -> `DownloadError` z opisem D22 (nie `OSError`, zeby manager mial jedna sciezke bledu arkusza).
  - `linked_version(link) -> Path | None` — cel tylko z `extra.link == "hardlink"` + `extra.link_target` + `os.path.samefile` (sidecar z `copy` = sciezka nieznana, odtworzona).
  - `version_key_of(path) -> tuple[str, str, str] | None` — z sidecara wersji (decyzja 6).
  - `ensure_link(link, target, key, *, refresh=False)` — logika bez zmian, `campaign_key_of` -> `version_key_of`.
  - `FileStorage.get_versions_root(godlo) -> Path` = `<segment>/versions/<hierarchia>/`; `FileStorage.has_legacy_campaigns() -> bool` (czy w segmencie istnieje `kampanie/`); `list_files` pomija pierwszy czlon `versions` i `full_sheet`; `delete` usuwa oba dowiazania (wersje zostaja, D9); `get_campaign_path` usuniete.
- Usun: galaz kopii w `link_atomic`, kontrole D-5 (rozmiar/mtime kopii) w `linked_campaign`, `campaign_key_of` z fallbackiem z nazwy katalogu `kampanie/`, `CAMPAIGNS_DIR`.

- [ ] **Step 1: Testy** — przepisz w `tests/test_links.py` testy kopii (`test_no_hardlink_falls_back_to_copy_with_warning`, `test_copy_detected_via_sidecar_on_next_run`, `test_refresh_recopies_when_target_redownloaded` i pochodne) na:

```python
def test_link_without_hardlink_support_is_error(tmp_path, monkeypatch):
    from kartograf.download import links
    from kartograf.exceptions import DownloadError

    target = tmp_path / "versions" / "a" / "v_1" / "x.asc"
    target.parent.mkdir(parents=True)
    target.write_text("1")
    monkeypatch.setattr(links.os, "link", lambda *a: (_ for _ in ()).throw(OSError(95, "x")))
    with pytest.raises(DownloadError, match="hardlink"):
        links.link_atomic(target, tmp_path / "a" / "x.asc")
    assert not (tmp_path / "a" / "x.asc").exists()


def test_copy_sidecar_from_older_release_is_unknown(tmp_path):
    """A 0.7.x link sidecar with ``extra.link == "copy"`` is not trusted (D22)."""
    import json

    from kartograf.download import links

    target = tmp_path / "versions" / "a" / "v_1" / "x.asc"
    target.parent.mkdir(parents=True)
    target.write_text("1")
    link = tmp_path / "a" / "x.asc"
    link.parent.mkdir(parents=True)
    link.write_text("1")  # a copy, not a hardlink
    (link.parent / "x.asc.meta.json").write_text(
        json.dumps({"extra": {"link": "copy", "link_target": "../versions/a/v_1/x.asc"}})
    )
    assert links.linked_version(link) is None
```

oraz w `tests/test_storage.py`:

```python
def test_versions_root_mirrors_hierarchy(tmp_path):
    s = FileStorage(tmp_path)
    root = s.get_versions_root("N-34-130-D-d-2-4")
    assert root == tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "versions" / "N-34" / "130" / "D" / "d" / "2" / "4"


def test_list_files_skips_versions_and_full_sheet(tmp_path):
    s = FileStorage(tmp_path)
    g = "N-34-130-D-d-2-4"
    standard = s.get_path(g)
    full = s.get_full_sheet_path(g)
    version = s.get_versions_root(g) / "2025-06-02_91234_3fa91c2e" / f"{g}.asc"
    for p in (standard, full, version):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("1")
    assert s.list_files() == [standard]
```

- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implementacja** wg Interfaces; `has_legacy_campaigns` sprawdza `(<output>/<segment>/kampanie).is_dir()` dla obu wartosci `{uklad}` jak `list_files` (storage.py:504-508).
- [ ] **Step 4: Bez osobnego commitu** — Task 3 zmienia kontrakt, na ktorym stoi `DownloadManager`, wiec testy managera sa czerwone do konca Task 4; brama i commit sa wspolne z Task 4 (bez `xfail`). Tu tylko: `.venv/bin/python -m pytest tests/test_links.py tests/test_storage.py tests/test_campaigns.py -q` -> PASS.

---

### Task 4: `DownloadManager` — arkusze na wersjach (zapis, D13, D23, `full_sheet/`)

**Files:**
- Modify: `kartograf/download/manager.py` (`_fetch_campaigns` 901-1229, `_fetch_sheet_plain` 875-899, `_add_range_flights` 1175-1226, `_local_newest` 1236-1258, `_write_sidecar` 1559, `_write_campaign_sidecar` 1600-1642; usun `_note_reuse` 1644-1688 i `_note_link_reuse`)
- Test: `tests/test_manager_campaigns.py`, `tests/test_campaigns_flow.py`

**Interfaces:**
- Consumes: Task 1-3.
- Produces (tryb domyslny jak dzisiejsze `skip_existing=True`; tryby w Task 5):
  - Pobranie kampanii: `staged = new_incoming_dir(root) / f"{godlo}{ext}"` -> `provider.download_record(record, staged)` -> `verify_file_format(staged, ext)` -> `verify_sheet_extent(staged, godlo, ext)` -> `digest = read_content(staged, ext=ext, coverage=ref.full_sheet is not True)` (D13) -> `commit_version(staged, root, name, VersionRef(ref.dirname, "campaign"), digest, writer)`; `writer` wola `_write_campaign_sidecar(..., digest=, version=, coverage=)` (`extra.coverage` gdy niepuste; blad pomiaru = brak pola + `logger.warning`, spec 6).
  - Istniejaca lokalna wersja kampanii = wersja z etykieta `ref.dirname` w `list_versions` -> bez pobrania (`local`).
  - R22 znika: wersja bez sidecara jest niewazna; naprawia ja nastepny zapis tej samej tresci (D18).
  - Dowiazania: standardowe -> `newest_version` lokalnych wersji zadania (klucz decyzji 6); `full_sheet/` -> najnowsza wersja z `meta["extra"]["campaign"]["full_sheet"] is True`; `ensure_link(..., refresh=commit.status in ("new", "relabeled"))`.
  - `_add_range_flights`: pokrycie czytane z `extra.coverage` sidecarow wersji; `update_sidecar_extra` wolany wylacznie na sidecarze dowiazania (`flights`, `better_coverage`).
  - `SheetFetch` dostaje `status: Literal["new", "unchanged", "relabeled", "local"]` i `version: str | None` (etykieta celu dowiazania); `DownloadResult` liczniki `new`, `relabeled`, `unchanged`, `local` (listy godel).
  - Usuniete: `extra.parent_requests` (`_note_reuse`), `DownloadResult.copied`, `SheetFetch.link` (`"copy"` nie istnieje — pole usuwane, nie stale `"hardlink"`).

- [ ] **Step 1: Testy** — przepisz testy z `kampanie/` na `versions/` (helper `campaign_path` -> `version_path(tmp_path, record, godlo)` szukajacy `versions/<hier>/<dirname>_*/<godlo>.asc`); usun testy kopii, `_note_reuse` i R22; dodaj:

```python
def test_version_sidecar_bytes_never_change(tmp_path):
    fake = c14_fake(contents={REC["84183"].url: asc_pixels(G, (1, -9999, -9999, -9999)),
                              REC["83233"].url: asc_pixels(G, (1, 2, 3, 4))})
    DownloadManager(tmp_path, provider=fake, campaigns="all", min_year=2025,
                    max_year=2025).download_sheets([G])
    sidecars = {p: p.read_bytes() for p in (tmp_path / SEGMENT / "versions").rglob("*.meta.json")}
    for kwargs in ({}, {"campaigns": "all", "min_year": 2019}, {"full_sheet": True}):
        DownloadManager(tmp_path, provider=fake, **kwargs).download_sheets([G])
    for p, body in sidecars.items():
        assert p.read_bytes() == body


def test_coverage_written_at_commit_for_partial_flight(tmp_path):
    fake = c14_fake(contents={REC["84183"].url: asc_pixels(G, (1, -9999, -9999, -9999))})
    DownloadManager(tmp_path, provider=fake).download_sheet(G)
    assert meta(version_path(tmp_path, REC["84183"]))["extra"]["coverage"] == pytest.approx(0.25)


@pytest.mark.parametrize("record", C14_ALL, ids=tag)
def test_read_content_matches_measure_coverage_on_real_c14(tmp_path, record):
    from kartograf.download.campaigns import measure_coverage
    from kartograf.download.versions import read_content

    body = FakeCampaignProvider(C14).body_for(record)  # same bytes download_record writes
    p = tmp_path / f"{G}.asc"
    p.write_bytes(body)
    assert read_content(p, ext=".asc", coverage=True).coverage == pytest.approx(
        measure_coverage(p, ".asc")
    )


def test_relabeled_campaign_moves_link(tmp_path):
    body = asc_pixels(G, (1, 2, 3, 4))
    old = REC["83233"]
    new = dataclasses.replace(old, url=old.url.replace("83233", "99999"), aktualnosc="2026-01-01")
    fake = FakeCampaignProvider({"newest": [old]}, contents={old.url: body, new.url: body})
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.records = {"newest": [new]}
    m.download_sheet(G)  # Task 5 changes the default to "local + newer": use update="upgrade" there
    assert m.last_sheet.status == "relabeled"
    assert meta(std_path(tmp_path))["extra"]["version"]["label"].startswith("2026-01-01_99999")


def test_rerun_same_campaign_is_local_without_download(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = DownloadManager(tmp_path, provider=fake)
    m.download_sheet(G)
    fake.downloads.clear()
    m.download_sheet(G)
    assert fake.downloads == [] and m.last_sheet.status == "local"
```

Helpery do dopisania w `tests/test_manager_campaigns.py`: `FakeCampaignProvider.downloads: list[str]` (URL-e w `download_record`), `FakeCampaignProvider.body_for(record) -> bytes` (wyciagniete z obecnego `download_record` 161-174 — te same bajty, ktore trafiaja do pliku), `version_path(tmp_path, record, godlo=G) -> Path` (jedyny plik `versions/<hier>/<aktualnosc>_<id>_*/<godlo>.asc`; zastepuje `campaign_path` 181).

- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implementacja** wg Interfaces. `_fetch_sheet_plain`: ten sam zapis przez `commit_version` z `VersionRef.downloaded()` i `coverage=False`, dowiazanie standardowe do najnowszej wersji.
- [ ] **Step 4: PASS** — `tests/test_manager_campaigns.py tests/test_campaigns_flow.py tests/test_download_manager.py tests/test_integration.py`
- [ ] **Step 5: Brama i commit** — `feat(manager)!: arkusze PL w magazynie wersji (versions/, D13, D23)`

---

### Task 5: Tryby `update` (tabela 4.2), zakres lat (D14), I-1 dla wszystkich strategii

**Files:**
- Modify: `kartograf/download/manager.py` (sygnatury 620-626, 703-710, 813-819; `_fetch_sheet`, `_fetch_campaigns`, `_download_many` 1375, faza `check_year_range` 529-614)
- Test: `tests/test_manager_update_modes.py` (NOWY), `tests/test_manager_campaigns.py`

**Interfaces:**
- Produces:
  - `UpdateMode = Literal["check", "upgrade", "force"]`; `download_sheet/download_hierarchy/download_sheets(..., update: UpdateMode | None = None, ...)` — `skip_existing` USUNIETE (BREAKING); `"check"` w tych metodach = `ValidationError` (sprawdzenie robi `check_updates`, Task 6).
  - `SheetFetch.newer: str | None` (etykieta dostepnej nowszej kampanii, tryb domyslny), `SheetFetch.unverified` (jak dzis, tekst bledu skorowidza).
  - `DownloadManager.inspect_sheet(godlo) -> list[PlanItemDraft]` — wspolna logika porownania sygnalu dla Task 6 (bez pobierania).
- Reguly (kazda komorka tabeli 4.2 = test):

| Sytuacja | `None` | `upgrade` | `force` |
|---|---|---|---|
| lokalna wersja kampanii z rekordu = jest | `local` | `local` | pobiera; `unchanged`/`new`/`relabeled` |
| nowszy rekord niz lokalna wersja (`newest`) | `local` + `newer` | pobiera nowsza | pobiera |
| brak lokalnej wersji | pobiera | pobiera | pobiera |
| skorowidz niedostepny (transport), bez zakresu lat | `local` + `unverified` (kazda strategia) | blad arkusza | blad arkusza |
| skorowidz niedostepny, zakres lat | D14: kazdy arkusz zadania ma lokalna wersje z rocznikiem w zakresie -> `local` + `unverified`; inaczej `DownloadError` zadania przed pobraniem | blad zadania | blad zadania |

  - `all`: brakujace lokalnie kampanie z zakresu sa pobierane w trybie domyslnym (decyzja 3); `--full-sheet`: brakujacy najnowszy pelny lot w zakresie = pobranie.
  - `force` = `MetadataCache(refresh=True)` w CLI (Task 7) i pobranie wszystkich wybranych kampanii; weryfikacja rekordu (B4, pion) dziala we wszystkich trybach.
  - Rocznik lokalnej wersji: `extra.campaign.date[:4]` (zgodnie z ADR-032 pkt 1, `aktualnoscRok` jest w `extra.source`, gdy obecny).

- [ ] **Step 1: Testy (`tests/test_manager_update_modes.py`)** — parametryzowane po komorkach tabeli, z `FakeCampaignProvider` i `_transport_error` z `tests/test_manager_campaigns.py`; co najmniej:
  `test_default_existing_local_no_download`, `test_default_newer_record_reports_newer_without_download`, `test_upgrade_downloads_newer_and_relinks`, `test_force_same_content_unchanged`, `test_default_index_down_all_strategy_uses_local`, `test_upgrade_index_down_is_sheet_failure`, `test_range_index_down_all_local_uses_local`, `test_range_index_down_one_missing_fails_task` (zero wywolan `download_record`), `test_check_mode_rejected_in_download_methods`, `test_full_sheet_missing_full_flight_downloaded_by_default`.
  Testy z Task 4 i starsze, ktore zakladaja automatyczne pobranie nowszej kampanii w trybie domyslnym (`test_relabeled_campaign_moves_link`, `test_newer_campaign_appears_relinks` i podobne), przepisz na `update="upgrade"` — domyslny tryb pokazuje juz tylko `newer` (D5).
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implementacja** — jeden punkt decyzji `_decide(item, mode, signal)` zwracajacy `"local" | "download" | "error"`, uzywany przez pobieranie i `inspect_sheet` (jedna regula, D5).
- [ ] **Step 4: PASS** — nowe testy + `tests/test_manager_campaigns.py`
- [ ] **Step 5: Brama i commit** — `feat(manager)!: tryby update zamiast skip_existing (check/upgrade/force, D14)`

---

### Task 6: Plan aktualizacji `updates.py`

**Files:**
- Create: `kartograf/download/updates.py`, `tests/test_updates.py`
- Modify: `kartograf/__init__.py` (grupa "Download" w `__all__`)

**Interfaces:**
- Produces:
  ```python
  PLAN_SCHEMA = "kartograf-plan/1"
  ItemStatus = Literal["current", "newer", "missing", "unverifiable", "check_failed"]

  @dataclass(frozen=True)
  class PlanItem:
      segment: str; hierarchy: str; name: str; sheet: str
      local_label: str | None; local_sha256: str | None
      available_label: str | None; available_signal: dict | None  # record: url, date, pzgik_date
      status: ItemStatus
      error: str | None = None

  @dataclass(frozen=True)
  class UpdatePlan:
      store: str; checked_at: str; kartograf_version: str; items: tuple[PlanItem, ...]
      schema: str = PLAN_SCHEMA
      def to_json(self) -> str: ...
      @classmethod
      def from_json(cls, text: str) -> "UpdatePlan": ...  # unknown schema -> ValidationError

  @dataclass(frozen=True)
  class UpgradeReport:
      done: tuple[SheetFetch, ...]; stale: tuple[PlanItem, ...]; failed: dict[str, str]

  def check_updates(manager: DownloadManager, godla: list[str]) -> UpdatePlan
  def upgrade(manager: DownloadManager, plan: UpdatePlan) -> UpgradeReport
  ```
- Reguly (spec 4.4): `check_updates` niczego nie pobiera; `upgrade(plan)` — inny `store` albo nieznany schemat = `ValidationError` przed jakimkolwiek zapytaniem; przed kazda pozycja `newer`/`missing` ponowne odczytanie sygnalu, rozny od planu = pozycja w `stale`, bez pobrania; pozycje usuniete z pliku planu nie sa wykonywane; `current`/`unverifiable` pomijane.

- [ ] **Step 1: Testy** — `test_plan_json_round_trip`, `test_plan_from_json_rejects_unknown_schema`, `test_upgrade_rejects_foreign_store` (zero wywolan `resolve_campaigns`), `test_check_updates_downloads_nothing` (`fake.downloads == []`, takze dla `missing`), `test_upgrade_stale_item_fails_others_run`, `test_upgrade_skips_items_removed_from_plan`, `test_check_failed_item_on_index_error`.
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implementacja** — `check_updates` buduje pozycje z `manager.inspect_sheet` (Task 5); `upgrade` wola `manager.download_sheets([...], update="upgrade")` per pozycja po sprawdzeniu sygnalu.
- [ ] **Step 4: PASS**
- [ ] **Step 5: Brama i commit** — `feat(updates): plan aktualizacji kartograf-plan/1 (check_updates, upgrade)`

---

### Task 7: CLI `kartograf download` — flagi, statusy, plan, `Info:` o `kampanie/`

**Files:**
- Modify: `kartograf/cli/_parser.py` (`--force` 206-215 do grupy wykluczajacej z `--check-updates`, `--upgrade`; nowe `--plan PLIK`), `kartograf/cli/download_cmd.py` (1085-1192, 1296-1298, 1313-1408, 1835-1870, `_pl_metadata_cache` 219; odrzucenie torow 2/3 i 3/3: LAZ 2059, CZ 2219/2339, `--target-crs`, `landcover`, `soilgrids`)
- Test: `tests/test_cli.py` (klasy z `--force`, kampaniami i `--full-sheet`), `tests/test_cli_update_modes.py` (NOWY)

**Interfaces:**
- Mapowanie: brak flag -> `update=None`; `--upgrade` -> `"upgrade"`; `--force` -> `"force"` (+ `_pl_metadata_cache(refresh=True)`); `--check-updates` -> `check_updates` i raport (bez pobierania), `--plan PLIK` zapisuje JSON; `--upgrade --plan PLIK` -> `upgrade(UpdatePlan.from_json(...))`; `--plan` bez `--check-updates`/`--upgrade` = `Error:` argparse.
- Linie statusu (jedna na plik): `"<godlo>: nowa wersja <label>_<sha8>"`, `"<godlo>: nowa etykieta <label> (ta sama tresc)"`, `"<godlo>: bez zmian <label>"`, `"<godlo>: lokalna wersja <label>"` + przy `newer` dopisek `"; dostepna nowsza <label> (--upgrade)"`; podsumowanie `"Nowe: N, nowa etykieta: N, bez zmian: N, lokalne: N, bledy: N"`; kody wyjscia wg `_finish_pl_sheets` bez zmian; `--check-updates` z pozycja `check_failed` = kod czesciowego sukcesu.
- Raport `--check-updates`: jedna linia na pozycje ze statusem (`aktualne`, `nowsza: <label>`, `do pobrania`, `nie da sie sprawdzic bez pobrania`, `nie udalo sie sprawdzic: <blad>`).
- Jednorazowe `Info: katalog kampanie/ z wersji 0.7.x nie jest uzywany; dane zostana pobrane ponownie do versions/` gdy `storage.has_legacy_campaigns()`.
- Usuniete z CLI: komunikat o kopii zamiast hardlinku (download_cmd.py:1358-1359), `Skipped ... already exists`.

- [ ] **Step 1: Testy** — `test_flags_mutually_exclusive` (kod 2 argparse), `test_plan_requires_check_or_upgrade`, `test_status_lines_and_counters`, `test_check_updates_prints_report_and_downloads_nothing`, `test_check_updates_writes_plan_file`, `test_upgrade_with_plan_executes_items`, `test_legacy_kampanie_info_once`, `test_check_updates_rejected_for_laz_cz_cutout_landcover` (kod 1, przed siecia); przepisz istniejace testy CLI z `Skipped`/`kampanie/`/kopii.
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implementacja**
- [ ] **Step 4: PASS** — `tests/test_cli*.py`
- [ ] **Step 5: Smoke CLI offline** — `.venv/bin/kartograf download --help` (grupa flag widoczna); `.venv/bin/kartograf download N-34-139-C-a-3-1 --check-updates --upgrade` -> kod 2.
- [ ] **Step 6: Brama i commit** — `feat(cli)!: --check-updates, --upgrade, --plan i statusy wersji dla arkuszy PL`

---

### Task 8: Dokumentacja, ADR-036, CHANGELOG

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md` (3.2, 3.3 reguly 6-7, 4.1), `docs/USAGE.md`, `docs/SCOPE.md` (2.11, 2.12), `docs/PROGRESS.md`

- [ ] **Step 1: ADR-036 "Magazyn wersjonowany"** — Kontekst/Opcje/Decyzja = D1-D25 w skrocie z odsylaczem do specu; Konsekwencje: zakres planu 1/3 i plany 2/3, 3/3. Wiersz indeksu; erraty/statusy wg spec sekcja 9 (ADR-030 uklad `kampanie/`, automatyczne `newest`, errata 4 kopia; ADR-033 F-U5; ADR-032 pkt 2 i 4; ADR-035 W-U3/W-U8 — to ostatnie oznacz "realizacja w planie 2/3"; ADR-026 land cover — "realizacja w planie 3/3"). Sprawdz CRLF:
  `.venv/bin/python -c "b=open('docs/DECISIONS.md','rb').read().split(b'\n'); print([i for i,l in enumerate(b[:-1],1) if not l.endswith(b'\r')][:5])"` -> `[]`.
- [ ] **Step 2: CHANGELOG `[0.8.0] - Unreleased` / `Zmiany lamiace (BREAKING)`** (styl wpisow 0.7.2, kazdy z "Co zrobic"): `kampanie/` -> `versions/<hierarchia>/<etykieta>_<sha8>/` (bez migracji, ponowne pobranie); domyslnie lokalna wersja zamiast automatycznego pobrania nowszej kampanii (`--upgrade`); nowe znaczenie `--force`; `skip_existing` -> `update=`; hardlinki wymagane (koniec kopii; FS bez hardlinkow = blad); `extra.parent_requests` usuniete; `SheetFetch.link`, `DownloadResult.copied` usuniete; pola `status`/`version`/`newer`. `Dodane`: `--check-updates`, `--upgrade`, `--plan`, `check_updates`, `upgrade`, `UpdatePlan`, `VersionRef`, `extra.version`, `relabeled`.
- [ ] **Step 3: ARCHITECTURE/USAGE/SCOPE** — uklad `versions/` dla arkuszy PL, tryby, plan aktualizacji, wymaganie hardlinkow, `rsync -aH`, kompresja systemu plikow (spec 9); zasada nazw plikow D25 jako regula ukladu `data/` w ARCHITECTURE 3.3 (z wyjatkiem `<godlo>.<ext>` dla arkuszy PL); usun opisy `kampanie/`, kopii i `parent_requests` dla arkuszy PL.
- [ ] **Step 4: PROGRESS** — sesja, stan planu 1/3, nastepny krok (plan 2/3).
- [ ] **Step 5: Commit** — `docs: magazyn wersjonowany dla arkuszy PL (ADR-036, CHANGELOG, uklad versions/)`

---

### Task 9: Weryfikacja na zywo (arkusz NMT)

**Files:** brak zmian w repo (chyba ze test wykaze blad — wtedy osobny commit z testem odtwarzajacym).

Katalog danych podaje uzytkownik (poza repo i `/tmp`); oznaczony nizej jako `$DATA`. CLI z korzenia repo.

- [ ] **Step 1:** `.venv/bin/kartograf download N-34-139-C-a-3-1 -o "$DATA"` -> kod 0, linia `nowa wersja`, w `$DATA/nmt/pl_1992_1m_evrf2007/versions/N-34/139/C/a/3/1/` jeden katalog `<aktualnosc>_<id>_<sha8>`; `stat -c %h` pliku = 2 (wersja + sciezka standardowa); sidecar wersji z `sha256`, `extra.version`, `extra.campaign`.
- [ ] **Step 2:** ponowne uruchomienie -> `lokalna wersja`, zero pobran (log), bajty sidecara wersji bez zmian (`sha256sum`).
- [ ] **Step 3:** `--check-updates --plan "$DATA/plan.json"` -> `aktualne`; plik planu z `schema: kartograf-plan/1` i `store` = `$DATA`.
- [ ] **Step 4:** `--upgrade` -> `lokalna wersja`; `--force` -> `bez zmian` (ta sama tresc) albo `nowa wersja` przy zmianie u zrodla.
- [ ] **Step 5:** `--campaigns all --min-year 2019` na arkuszu z kilkoma lotami (np. `N-34-139-C-a-3-1`) -> kilka katalogow wersji, `full_sheet/` gdy jest pelny lot, `extra.coverage` w sidecarach lotow niepelnych.
- [ ] **Step 6:** Przekaz uzytkownikowi komendy, kody wyjscia, listing `versions/`, liczby hardlinkow. Kazda niezgodnosc: test odtwarzajacy w `tests/` (failing), poprawka, osobny commit.
