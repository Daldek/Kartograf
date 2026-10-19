"""The project file ``kartograf-project.json``: format, strict reading, atomic
write under the project lock and per-task merging (``manifest.py``, ADR-040).

``tests/fixtures/project/kartograf-project.json`` is the example of the spec
(3.3): task ``teren`` pinned, task ``pokrycie`` not downloaded.
"""

import copy
import json
import os
import shutil
from pathlib import Path

import pytest

from kartograf.exceptions import ValidationError
from kartograf.project import manifest
from kartograf.project.manifest import (
    LOCK_NAME,
    MANIFEST_NAME,
    commit_tasks,
    create_manifest,
    read_manifest,
)

GOLDEN = Path(__file__).parent / "fixtures" / "project" / MANIFEST_NAME


@pytest.fixture
def project(tmp_path) -> Path:
    directory = tmp_path / "projekt"
    directory.mkdir()
    shutil.copy2(GOLDEN, directory / MANIFEST_NAME)
    return directory


def _doc(project: Path) -> dict:
    return json.loads((project / MANIFEST_NAME).read_text(encoding="utf-8"))


def _write_doc(project: Path, doc: dict) -> None:
    (project / MANIFEST_NAME).write_text(json.dumps(doc), encoding="utf-8")


def test_read_golden_manifest(project):
    read, state = read_manifest(project)
    assert read.directory == project and read.output_dir == Path("/srv/dane/kartograf")
    teren, pokrycie = read.tasks
    assert (teren.name, teren.command) == ("teren", "elevation download")
    assert dict(teren.options) == {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
    }
    (pin,) = teren.files
    assert (pin.role, pin.label, pin.size_bytes) == (
        "output",
        "2022-05-10_83233",
        41029733,
    )
    assert pin.version.endswith("/2022-05-10_83233_10be475e/N-34-130-D-d-2-4.asc")
    assert pokrycie.pinned_at is None and pokrycie.files == ()
    assert state == {t["name"]: t for t in _doc(project)["tasks"]}


def test_manifest_bytes_stable(project):
    """Written form = the spec example: key order, indentation, final newline."""
    golden = GOLDEN.read_bytes()
    _, state = read_manifest(project)
    assert commit_tasks(project, {"pokrycie": (state["pokrycie"], None)}) == ()
    assert "pokrycie" not in (project / MANIFEST_NAME).read_text(encoding="utf-8")
    assert commit_tasks(project, {"pokrycie": (None, state["pokrycie"])}) == ()
    assert (project / MANIFEST_NAME).read_bytes() == golden


def test_written_form_normalizes_key_order(project):
    doc = _doc(project)
    teren = doc["tasks"][0]
    teren["options"] = dict(reversed(list(teren["options"].items())))
    doc["tasks"][0] = dict(reversed(list(teren.items())))
    _write_doc(project, doc)
    _, state = read_manifest(project)
    commit_tasks(project, {"pokrycie": (state["pokrycie"], None)})
    commit_tasks(project, {"pokrycie": (None, state["pokrycie"])})
    assert (project / MANIFEST_NAME).read_bytes() == GOLDEN.read_bytes()


def _teren(doc: dict) -> dict:
    return doc["tasks"][0]


def _pin(doc: dict) -> dict:
    return doc["tasks"][0]["files"][0]


def _set(path, value):
    def change(doc: dict) -> None:
        *keys, last = path
        target = doc
        for key in keys:
            target = target[key]
        target[last] = value

    return change


def _delete(path):
    def change(doc: dict) -> None:
        *keys, last = path
        target = doc
        for key in keys:
            target = target[key]
        del target[last]

    return change


T = ("tasks", 0)
F = ("tasks", 0, "files", 0)
INVALID = {
    "schema-2": _set(("schema",), "kartograf-project/2"),
    "unknown-top-key": _set(("comment",), "x"),
    "unknown-task-key": _set((*T, "optons"), {}),
    "missing-task-key": _delete((*T, "files")),
    "duplicate-name": lambda doc: doc["tasks"][1].update(name="teren"),
    "bad-name": _set((*T, "name"), "Teren 1"),
    "unknown-command": _set((*T, "command"), "elevation list-sources"),
    "option-of-another-command": _set((*T, "options", "keep_raw"), True),
    "option-null": _set((*T, "options", "year"), None),
    "option-wrong-type": _set((*T, "options", "year"), "2022"),
    "version-dotdot": _set((*F, "version"), "nmt/../versions/x/a.asc"),
    "version-absolute": _set((*F, "version"), "/srv/versions/a.asc"),
    "version-incoming": _set((*F, "version"), "nmt/versions/.incoming/h_1/a.asc"),
    "version-outside-versions": _set((*F, "version"), "nmt/pl/N-34/a.asc"),
    "path-in-versions": _set((*F, "path"), "nmt/versions/a.asc"),
    "sha256-not-hex": _set((*F, "sha256"), "Z" * 64),
    "sha256-upper": _set((*F, "sha256"), "A" * 64),
    "size-negative": _set((*F, "size_bytes"), -1),
    "role-unknown": _set((*F, "role"), "extra"),
    "pinned-at-without-version": _set((*T, "kartograf_version"), None),
    "pinned-without-files": _set((*T, "files"), []),
    "not-pinned-with-files": lambda doc: doc["tasks"][1].update(
        files=copy.deepcopy(doc["tasks"][0]["files"])
    ),
    "geometry-sha256-without-geometry": _set(
        (*T, "geometry_sha256"), {"a.gpkg": "0" * 64}
    ),
    "geometry-without-sha256": _set((*T, "options", "geometry"), "a.gpkg"),
    "same-version-twice": lambda doc: doc["tasks"][0]["files"].append(
        copy.deepcopy(doc["tasks"][0]["files"][0])
    ),
}


@pytest.mark.parametrize("change", INVALID.values(), ids=INVALID.keys())
def test_read_rejects_invalid(project, change):
    doc = _doc(project)
    change(doc)
    _write_doc(project, doc)
    before = (project / MANIFEST_NAME).read_bytes()
    with pytest.raises(ValidationError) as caught:
        read_manifest(project)
    assert str(caught.value).startswith(f"{MANIFEST_NAME}: ")
    with pytest.raises(ValidationError):
        commit_tasks(project, {})
    assert (project / MANIFEST_NAME).read_bytes() == before
    assert sorted(os.listdir(project)) == [MANIFEST_NAME]


@pytest.mark.parametrize(
    "text", ["{", '{"schema": "kartograf-project/1", "schema": 1}', "[NaN]"]
)
def test_read_rejects_bad_json(project, text):
    (project / MANIFEST_NAME).write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError):
        read_manifest(project)


def test_read_error_names_the_place(project):
    doc = _doc(project)
    _teren(doc)["optons"] = {}
    _write_doc(project, doc)
    with pytest.raises(ValidationError) as caught:
        read_manifest(project)
    assert str(caught.value) == (
        "kartograf-project.json: zadanie teren: nieznany klucz 'optons'"
    )


def test_missing_manifest_names_the_directory(tmp_path):
    with pytest.raises(ValidationError) as caught:
        read_manifest(tmp_path)
    assert str(caught.value).startswith(f"brak projektu w {tmp_path} ")


def test_bom_of_an_editor_is_accepted_and_not_written_back(project):
    """E2E 0.8.0 P3-15: Notepad & co. save JSON with a BOM."""
    path = project / MANIFEST_NAME
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    read, state = read_manifest(project)
    assert [task.name for task in read.tasks] == ["teren", "pokrycie"]
    assert commit_tasks(project, {"pokrycie": (state["pokrycie"], None)}) == ()
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_project_given_as_the_manifest_file_names_the_directory_to_give(project):
    with pytest.raises(ValidationError) as caught:
        read_manifest(project / MANIFEST_NAME)
    assert f"--project {project}" in str(caught.value)
    assert f"{MANIFEST_NAME}/{MANIFEST_NAME}" not in str(caught.value)


def _pinned(task: dict, label: str) -> dict:
    changed = copy.deepcopy(task)
    changed["files"][0]["label"] = label
    return changed


def test_commit_merges_other_tasks(project):
    _, first = read_manifest(project)
    _, second = read_manifest(project)
    new_task = {**copy.deepcopy(first["pokrycie"]), "name": "gleby"}
    assert (
        commit_tasks(project, {"teren": (first["teren"], _pinned(first["teren"], "A"))})
        == ()
    )
    assert commit_tasks(project, {"gleby": (None, new_task)}) == ()
    assert second  # read before both commits
    read, _ = read_manifest(project)
    assert [t.name for t in read.tasks] == ["teren", "pokrycie", "gleby"]
    assert read.tasks[0].files[0].label == "A"


def test_commit_conflict_same_task(project):
    _, first = read_manifest(project)
    _, second = read_manifest(project)
    assert (
        commit_tasks(project, {"teren": (first["teren"], _pinned(first["teren"], "A"))})
        == ()
    )
    after_first = (project / MANIFEST_NAME).read_bytes()
    conflicts = commit_tasks(
        project,
        {
            "teren": (second["teren"], _pinned(second["teren"], "B")),
            "pokrycie": (second["pokrycie"], None),
        },
    )
    assert conflicts == ("teren",)
    read, _ = read_manifest(project)
    assert [t.name for t in read.tasks] == ["teren"]  # the other change written
    assert read.tasks[0].files[0].label == "A"
    assert after_first != (project / MANIFEST_NAME).read_bytes()


def test_commit_add_conflicts_with_concurrent_add(project):
    _, state = read_manifest(project)
    new_task = {**copy.deepcopy(state["pokrycie"]), "name": "gleby"}
    assert commit_tasks(project, {"gleby": (None, new_task)}) == ()
    assert commit_tasks(project, {"gleby": (None, new_task)}) == ("gleby",)


def test_lock_busy_times_out_without_takeover(project, monkeypatch):
    monkeypatch.setattr(manifest, "LOCK_TIMEOUT_S", 0.2)
    lock = project / LOCK_NAME
    lock.mkdir()
    (lock / "owner").write_text("lab-3 4121 2026-10-20T08:15:02+00:00\n")
    before = (project / MANIFEST_NAME).read_bytes()
    _, state = read_manifest(project)
    with pytest.raises(ValidationError) as caught:
        commit_tasks(project, {"pokrycie": (state["pokrycie"], None)})
    assert "host lab-3, pid 4121" in str(caught.value)
    assert (lock / "owner").read_text() == "lab-3 4121 2026-10-20T08:15:02+00:00\n"
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_interrupted_replace_keeps_old_manifest(project, monkeypatch):
    before = (project / MANIFEST_NAME).read_bytes()
    _, state = read_manifest(project)

    def interrupted(source, target):
        raise OSError("dysk odlaczony")

    monkeypatch.setattr(os, "replace", interrupted)
    with pytest.raises(ValidationError):
        commit_tasks(project, {"pokrycie": (state["pokrycie"], None)})
    monkeypatch.undo()
    assert (project / MANIFEST_NAME).read_bytes() == before
    assert sorted(os.listdir(project)) == [MANIFEST_NAME]


def test_create_refuses_existing_and_project_dir_has_no_extra_files(tmp_path):
    directory = tmp_path / "nowy"
    create_manifest(directory, "data")
    created = (directory / MANIFEST_NAME).read_bytes()
    assert json.loads(created) == {
        "schema": "kartograf-project/1",
        "output_dir": "data",
        "tasks": [],
    }
    with pytest.raises(ValidationError):
        create_manifest(directory, "inny")
    assert (directory / MANIFEST_NAME).read_bytes() == created
    task = {
        "name": "teren",
        "command": "soil hsg",
        "options": {"sheet": "N-34-130-D", "depth": "0-5cm"},
        "pinned_at": None,
        "kartograf_version": None,
        "files": [],
    }
    commit_tasks(directory, {"teren": (None, task)})
    commit_tasks(directory, {"teren": (task, None)})
    assert os.listdir(directory) == [MANIFEST_NAME]
    assert (directory / MANIFEST_NAME).read_bytes() == created
