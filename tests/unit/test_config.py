"""User environment (DEV-18): ``nogat.toml``, variables and ``config show``."""

import json
import os
from pathlib import Path

import pytest

import kartograf
from kartograf import ConfigError, error_report, get_config
from kartograf import config as environment
from kartograf.cache.defaults import default_cache_path
from kartograf.cli import main
from kartograf.envelope import wrap
from tests.support.errors import error_document


def write_config(tmp_path: Path, monkeypatch, text: str) -> Path:
    path = tmp_path / "custom" / "nogat.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("NOGAT_CONFIG", str(path))
    return path


def source_of(key: str) -> tuple[str, str, str | None]:
    setting = get_config().keys[key]
    return str(setting.value), setting.source, setting.name


def test_a_shared_key_comes_from_the_first_layer_of_dev_18_1(tmp_path, monkeypatch):
    path = write_config(
        tmp_path,
        monkeypatch,
        '[nogat]\ndata_dir = "/nogat-file"\n\n[kartograf]\ndata_dir = "/own-file"\n',
    )
    monkeypatch.setenv("NOGAT_DATA_DIR", "/nogat-env")
    monkeypatch.setenv("KARTOGRAF_DATA_DIR", "/own-env")

    expected = [
        ("/own-env", "env", "KARTOGRAF_DATA_DIR"),
        ("/nogat-env", "env", "NOGAT_DATA_DIR"),
        ("/own-file", "file", "[kartograf]"),
        ("/nogat-file", "file", "[nogat]"),
    ]
    for value, source, name in expected:
        assert source_of("data_dir") == (value, source, name)
        assert environment.data_dir() == Path(value)
        # Drop the layer that won, so the next one shows.
        if source == "env":
            monkeypatch.delenv(name)
        else:
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace(f'data_dir = "{value}"', "x = 1"), encoding="utf-8"
            )
    assert source_of("data_dir")[1:] == ("default", None)
    assert environment.data_dir() == environment.default_data_dir()


def test_an_empty_variable_counts_as_unset(monkeypatch):
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", "")
    monkeypatch.setenv("NOGAT_CACHE_DIR", "/shared")

    assert source_of("cache_dir") == ("/shared", "env", "NOGAT_CACHE_DIR")


def test_the_store_root_is_a_key_of_kartograf_only(
    tmp_path, monkeypatch, user_environment
):
    assert environment.store_root().root == user_environment / "data" / "kartograf"
    write_config(
        tmp_path,
        monkeypatch,
        '[nogat]\nroot = "/ignored"\ndata_dir = "/shared"\n',
    )
    monkeypatch.setenv("NOGAT_ROOT", "/ignored-too")

    # <data_dir>/kartograf: the shared data_dir moves it, a shared root does not exist
    assert source_of("root") == ("/shared/kartograf", "default", None)

    write_config(tmp_path, monkeypatch, '[kartograf]\nroot = "/from-file"\n')
    assert source_of("root") == ("/from-file", "file", "[kartograf]")
    monkeypatch.setenv("KARTOGRAF_ROOT", "/from-env")
    assert source_of("root") == ("/from-env", "env", "KARTOGRAF_ROOT")
    store = get_config().store
    assert (store.root, store.source, store.name) == (
        Path("/from-env"),
        "env",
        "KARTOGRAF_ROOT",
    )


def test_the_public_store_root_names_the_root_its_source_and_the_marker(
    tmp_path, monkeypatch, user_environment
):
    default = kartograf.store_root()
    assert default == kartograf.StoreRoot(
        user_environment / "data" / "kartograf", "default", None, False
    )

    write_config(tmp_path, monkeypatch, '[kartograf]\nroot = "' + str(tmp_path) + '"\n')
    (tmp_path / "kartograf-store.json").write_text("{}", encoding="utf-8")
    assert kartograf.store_root() == kartograf.StoreRoot(
        tmp_path, "file", "[kartograf]", True
    )

    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("KARTOGRAF_ROOT", str(elsewhere))
    assert kartograf.store_root() == kartograf.StoreRoot(
        elsewhere, "env", "KARTOGRAF_ROOT", False
    )
    # the same root, source and name as the report of config show
    store = get_config().store
    assert (store.root, store.source, store.name) == (
        elsewhere,
        "env",
        "KARTOGRAF_ROOT",
    )


def test_the_marker_of_another_tool_is_not_the_marker_of_kartograf(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path))
    (tmp_path / "imgw-store.json").write_text("{}", encoding="utf-8")

    assert kartograf.store_root().marker_exists is False


def test_the_public_store_root_does_not_walk_the_tree(
    tmp_path, monkeypatch, user_environment
):
    (tmp_path / "versions").mkdir()
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path))

    def walked(*args, **kwargs):
        raise AssertionError("store_root() must not read the store")

    monkeypatch.setattr(environment, "_tree_size", walked)
    monkeypatch.setattr(os, "walk", walked)
    monkeypatch.setattr(os, "scandir", walked)
    monkeypatch.setattr(Path, "iterdir", walked)

    assert kartograf.store_root().root == tmp_path


def test_a_directory_expands_the_home_of_the_user(monkeypatch):
    monkeypatch.setenv("KARTOGRAF_ROOT", "~/kartograf-store")

    assert environment.store_root().root == Path.home() / "kartograf-store"


def test_a_call_without_a_root_gets_the_default_root(user_environment):
    # no variable and no file: <data_dir>/kartograf of the user directory
    assert environment.resolve_root(None) == user_environment / "data" / "kartograf"


def test_a_root_the_caller_names_is_kept_as_given(monkeypatch):
    monkeypatch.setenv("KARTOGRAF_ROOT", "/default")

    assert environment.resolve_root("data/store") == Path("data/store")
    assert environment.resolve_root(Path("/abs")) == Path("/abs")


def test_an_empty_root_is_a_validation_error_not_the_default(monkeypatch):
    monkeypatch.setenv("KARTOGRAF_ROOT", "/default")

    with pytest.raises(kartograf.ValidationError) as caught:
        environment.resolve_root("")

    assert caught.value.option == "root"


def test_the_nogat_section_holds_only_the_shared_keys(tmp_path, monkeypatch):
    write_config(
        tmp_path,
        monkeypatch,
        '[nogat]\nlang = "en"\ndebug = true\n\n[imgw]\nlang = "pl"\n',
    )

    assert source_of("lang") == ("en", "file", "[nogat]")
    assert environment.debug() is False  # debug is not a shared key


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1", True), ("true", True), ("yes", True), ("0", False), ("OFF", False)],
)
def test_the_debug_flag_reads_the_usual_words(monkeypatch, text, expected):
    monkeypatch.setenv("KARTOGRAF_DEBUG", text)

    assert environment.debug() is expected


def test_the_debug_flag_comes_from_the_file_as_a_boolean(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, "[kartograf]\ndebug = true\n")

    assert source_of("debug") == ("True", "file", "[kartograf]")
    assert environment.debug() is True


def test_credentials_come_from_the_environment_only(tmp_path, monkeypatch):
    write_config(
        tmp_path,
        monkeypatch,
        '[kartograf]\nclms_credentials = "from-file"\nlang = "en"\nfoo = 2\n',
    )

    missing = get_config()
    assert dict(missing.credentials) == {"CLMS_CREDENTIALS": "missing"}
    assert [(item.key, item.reason) for item in missing.config_file.ignored] == [
        ("clms_credentials", "credential"),
        ("foo", "unknown"),
    ]

    monkeypatch.setenv("CLMS_CREDENTIALS", "client:secret-from-env")
    present = get_config()
    assert dict(present.credentials) == {"CLMS_CREDENTIALS": "present"}
    text = present.to_json()
    assert "secret-from-env" not in text and "from-file" not in text


def test_directories_stay_out_of_the_working_directory(
    tmp_path, monkeypatch, user_environment
):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    assert environment.data_dir() == user_environment / "data"
    assert environment.cache_dir() == user_environment / "cache"
    assert default_cache_path() == (
        user_environment / "cache" / "kartograf" / "metadata.db"
    )
    assert main(["cache", "path"]) == 0
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    ("text", "cause"),
    [
        ("[kartograf\nlang = 'pl'\n", "is not valid TOML"),
        ("nogat = 5\n", "[nogat] is not a table"),
        ("[nogat]\nlang = 'pl'\n[kartograf]\n\n[kartograf]\n", "is not valid TOML"),
    ],
    ids=["broken-toml", "section-not-a-table", "duplicate-table"],
)
def test_a_file_that_cannot_be_used_is_reported_and_not_applied(
    text, cause, tmp_path, monkeypatch
):
    assert environment.config_file().error is None  # the default file may be absent
    environment.check_config()

    path = write_config(tmp_path, monkeypatch, text)

    assert cause in str(environment.config_file().error)
    assert environment.resolve("lang").source == "default"
    reported = get_config().config_file
    assert reported.exists and cause in str(reported.error)
    with pytest.raises(ConfigError) as caught:
        environment.check_config()
    assert caught.value.code == "validation_error"
    assert caught.value.exit_code == 2
    assert caught.value.details() == {
        "reason": "invalid_config",
        "option": "NOGAT_CONFIG",
        "path": path.as_posix(),
    }
    assert cause in str(caught.value)


def test_a_file_named_by_nogat_config_must_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("NOGAT_CONFIG", str(tmp_path / "missing.toml"))

    assert environment.config_file().error == "the file does not exist"
    assert get_config().config_file.exists is False
    with pytest.raises(ConfigError, match="does not exist"):
        environment.check_config()


def test_the_default_file_is_named_in_the_error_without_nogat_config(
    monkeypatch, user_environment
):
    default = user_environment / "config" / "nogat.toml"
    default.parent.mkdir(parents=True)
    default.write_text("[kartograf\n", encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        environment.check_config()

    assert caught.value.details()["option"] == "nogat.toml"
    assert caught.value.details()["path"] == default.as_posix()
    assert get_config().config_file.source == "default"


@pytest.mark.parametrize(
    "content",
    [
        b'[kartograf]\nlang = "za\xbf\xf3\xb3\xe6"\n',
        b"\xff\xfe[\x00k\x00]\x00",
    ],
    ids=["cp1250-text", "utf-16"],
)
def test_a_file_that_is_not_utf_8_is_a_validation_error_with_a_snake_case_reason(
    content, tmp_path, monkeypatch, capsys
):
    """The decoder error is caught: the file is reported like any unusable one."""
    path = write_config(tmp_path, monkeypatch, "")
    path.write_bytes(content)
    reason = "the file is not UTF-8 text"

    assert environment.config_file().error == reason
    assert environment.resolve("lang").source == "default"  # nothing of it is applied
    with pytest.raises(ConfigError) as caught:
        environment.check_config()
    document = error_report(caught.value).to_dict()
    assert document["code"] == "validation_error"
    assert document["exit_code"] == 2
    assert document["details"] == {
        "reason": "invalid_config",  # snake_case (error-1 schema), not the prose
        "option": "NOGAT_CONFIG",
        "path": path.as_posix(),
    }
    assert reason in str(document["message"])

    assert main(["cache", "path", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    printed = error_document(captured.err)
    assert printed["details"]["reason"] == "invalid_config"
    assert main(["config", "show", "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)["result"]
    assert shown["config_file"]["error"] == reason
    assert shown["config_file"]["exists"] is True


def test_every_command_but_config_show_stops_on_an_unusable_file(
    tmp_path, monkeypatch, capsys
):
    write_config(tmp_path, monkeypatch, "not toml")

    assert main(["cache", "path"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: The settings file ")
    assert main(["config", "show"]) == 0
    assert "blad: the file is not valid TOML" in capsys.readouterr().out


def test_a_language_other_than_pl_or_en_is_not_valid(monkeypatch, capsys):
    environment.check_config()
    monkeypatch.setenv("NOGAT_LANG", "de")

    with pytest.raises(ConfigError) as caught:
        environment.check_config()

    assert caught.value.details() == {
        "reason": "invalid_config",
        "option": "NOGAT_LANG",
        "value": "de",
        "allowed": ["pl", "en"],
    }
    lang = get_config().keys["lang"]
    assert (lang.value, lang.source) == ("pl", "default")
    assert lang.error is not None and "NOGAT_LANG" in lang.error
    assert main(["cache", "path"]) == 2
    capsys.readouterr()

    monkeypatch.setenv("NOGAT_LANG", " EN ")
    environment.check_config()
    assert source_of("lang") == ("en", "env", "NOGAT_LANG")


def test_a_directory_must_be_a_text_in_the_file(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, "[kartograf]\ncache_dir = 5\n")

    with pytest.raises(ConfigError) as caught:
        environment.check_config()

    assert caught.value.details()["option"] == "[kartograf] cache_dir"
    assert environment.cache_dir() == environment.default_cache_dir()


def test_config_show_json_gives_every_key_its_source_and_the_store_size(
    tmp_path, monkeypatch, capsys
):
    root = tmp_path / "store"
    (root / "versions").mkdir(parents=True)
    (root / "a.bin").write_bytes(b"x" * 100)
    os.link(root / "a.bin", root / "versions" / "b.bin")  # one file, two names
    (root / "c.txt").write_bytes(b"y" * 7)
    monkeypatch.setenv("KARTOGRAF_ROOT", str(root))
    monkeypatch.setenv("KARTOGRAF_LANG", "en")

    assert main(["config", "show", "--json"]) == 0

    out = capsys.readouterr().out
    envelope = json.loads(out)  # exactly one document
    assert out == wrap("config show", get_config()).to_json()  # byte for byte
    report = envelope["result"]
    assert (report["schema"], report["tool"], report["version"]) == (
        "kartograf-config/1",
        "kartograf",
        kartograf.__version__,
    )
    assert list(report["keys"]) == ["root", "data_dir", "cache_dir", "lang", "debug"]
    assert report["keys"]["lang"] == {
        "value": "en",
        "source": "env",
        "name": "KARTOGRAF_LANG",
        "error": None,
    }
    assert report["keys"]["debug"]["source"] == "default"
    assert report["credentials"] == {"CLMS_CREDENTIALS": "missing"}
    assert report["store"] == {
        "root": root.as_posix(),
        "source": "env",
        "name": "KARTOGRAF_ROOT",
        "exists": True,
        "size_bytes": 107,
    }


def test_config_show_text_and_a_store_that_does_not_exist_yet(capsys, user_environment):
    assert main(["config", "show"]) == 0

    out = capsys.readouterr().out
    root = user_environment / "data" / "kartograf"
    assert f"  root = {root}  [domyslnie]" in out
    assert "  CLMS_CREDENTIALS: brak" in out
    assert f"Magazyn: {root}  [domyslnie]  brak katalogu" in out
    assert get_config().store.size_bytes is None
