"""The scripts of ``script generate`` (ADR-063 decision 5).

A bash script is read by ``bash -n`` and the direct one run against a stub ``curl``
that serves local files; a PowerShell script is checked for ASCII and read back by a
small reader of its strings, sums and brackets (``pwsh`` parses it where installed).
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import kartograf
from kartograf import UnsupportedError, generate_script
from kartograf.auth.proxy import KEYCHAIN_SERVICE
from kartograf.download.plan import Fetch, PlanItem, UpdatePlan
from kartograf.error_report import error_report
from kartograf.exceptions import ValidationError
from kartograf.messages.script import MESSAGES
from kartograf.notices import Notice
from kartograf.script import _KEYS, LeftOutFile, ScriptFile
from kartograf.source_info import SOURCE_GROUPS, list_sources

LINE = (
    "elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m"
    " --vertical-crs EVRF2007 -o ~/dem"
)
# In the order ``format_command`` writes the options of the line.
CORINE = (
    "landcover download --product corine --bbox 500000,500000,510000,510000"
    " --year 2018 --root ~/kartograf"
)
NMT = "pl.gugik.nmt_1m"
DMR5G = "cz.cuzk.dmr5g"
ASC = b"ncols 2\nnrows 2\n1 2\n3 4\n"
ZIP = b"PK\x05\x06" + bytes(18)
CHECKED_AT = "2026-11-25T09:00:00+00:00"
DAY = "2026-11-25"  # the day a direct script runs, as the stub ``date`` says
# The provider lines of DEV §20 of the NMT and DMR 5G files downloaded on ``DAY``.
G_NMT = (
    "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, NMT"
    f" (wytworzono b.d., pozyskano {DAY}); dane przetworzone"
)
Z_DMR5G = (
    "Źródło: Český úřad zeměměřický a katastrální (ČÚZK), DMR 5G"
    f" (pozyskano {DAY}), licencja CC BY 4.0"
    " (https://creativecommons.org/licenses/by/4.0/); dane przetworzone"
)
# Texts a script prints between double quotes, where the shells expand ``${name}``.
RUNTIME = (
    "uv_missing",
    "key_missing",
    "curl_missing",
    "downloading",
    "size_differs",
    "sha256_differs",
    "downloaded",
)

needs_pwsh = pytest.mark.skipif(shutil.which("pwsh") is None, reason="no pwsh")


@pytest.fixture
def released(monkeypatch):
    """A released Kartograf, whose tag a Kartograf script pins."""
    monkeypatch.setattr(kartograf, "__version__", "0.9.0")


def _item(
    name: str,
    *,
    url: str | None = None,
    size: int | None = None,
    sha256: str | None = None,
    source: str | None = NMT,
    fetch: bool = True,
    fetch_reason: str | None = None,
    status: str = "missing",
    action: str | None = "write",
    reason: str | None = None,
    track: str = "pl_sheet",
    signal: dict | None = None,
) -> PlanItem:
    return PlanItem(
        track=track,  # type: ignore[arg-type]
        segment="",
        hierarchy="",
        name=name,
        unit=name.split(".")[0],
        local_label=None,
        local_sha256=None,
        available_label=None,
        available_signal=signal,
        status=status,  # type: ignore[arg-type]
        action=action,  # type: ignore[arg-type]
        reason=reason,
        source=source,
        fetch=Fetch(url, size, sha256) if fetch else None,
        fetch_reason=fetch_reason,  # type: ignore[arg-type]
    )


def _plan(*items: PlanItem, notices=(), output_dir=".") -> UpdatePlan:
    return UpdatePlan(
        root=None if output_dir else "/srv/store",
        checked_at=CHECKED_AT,
        kartograf_version="0.9.1",
        items=items,
        notices=notices,
        output_dir=output_dir,
    )


def _direct(plan: UpdatePlan, shell: str = "bash", target: str | None = None):
    return generate_script(shell=shell, plan=plan, direct=True, target=target)


def _bash_syntax(text: str, tmp_path: Path) -> None:
    script = tmp_path / "check.sh"
    script.write_text(text, encoding="utf-8")
    done = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


# --- a reader of the PowerShell the scripts are written in ------------------------


def _ps_value(text: str, start: int) -> tuple[str, int]:
    """Read the string expression at ``start``: ``'...'`` or ``(a + b + ...)`` of such
    strings and ``[char]`` codes; return its value and the index after it."""
    if text.startswith("'", start):
        end, value = start + 1, ""
        while True:
            quote = text.index("'", end)
            value += text[end:quote]
            if text.startswith("''", quote):
                value, end = value + "'", quote + 2
                continue
            return value, quote + 1
    if text.startswith("[char]::ConvertFromUtf32(0x", start):
        close = text.index(")", start)
        code = text[start + len("[char]::ConvertFromUtf32(0x") : close]
        return chr(int(code, 16)), close + 1
    if text.startswith("[char]0x", start):
        end = start + len("[char]0x") + 4
        return chr(int(text[start + len("[char]0x") : end], 16)), end
    assert text.startswith("(", start), text[start:]
    value, index = "", start + 1
    while True:
        part, index = _ps_value(text, index)
        value += part
        if text.startswith(")", index):
            return value, index + 1
        assert text.startswith(" + ", index), text[index:]
        index += 3


def _ps_values(text: str) -> list[str]:
    """The values of a line of string expressions separated by spaces or commas."""
    values, index = [], 0
    while index < len(text):
        value, index = _ps_value(text, index)
        values.append(value)
        while index < len(text) and text[index] in " ,":
            index += 1
    return values


def _ps_balanced(text: str) -> bool:
    """Say whether the brackets of the code (not of comments or strings) pair up."""
    pairs, stack = {")": "(", "}": "{", "]": "["}, []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        quote = None
        for char in line:
            if quote is not None:
                quote = None if char == quote else quote
            elif char in "'\"":
                quote = char
            elif char in "({[":
                stack.append(char)
            elif char in pairs and (not stack or stack.pop() != pairs[char]):
                return False
        if quote is not None:
            return False
    return not stack


def _ps_line(text: str, prefix: str) -> str:
    """The rest of the first line of ``text`` that starts with ``prefix``."""
    line = next(row for row in text.splitlines() if row.startswith(prefix))
    return line[len(prefix) :]


# --- the arguments ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "option", "options"),
    [
        ({"shell": None, "command": LINE}, "shell", ()),
        ({"shell": "zsh", "command": LINE}, "shell", ()),
        ({"shell": "bash"}, None, ("command", "plan")),
        (
            {"shell": "bash", "command": LINE, "plan": _plan()},
            None,
            ("command", "plan"),
        ),
        ({"shell": "bash", "plan": _plan()}, None, ("plan", "direct")),
        ({"shell": "bash", "command": LINE, "target": "x"}, None, ("target", "direct")),
        (
            {"shell": "bash", "command": LINE, "direct": True, "target": ""},
            "target",
            (),
        ),
        (
            {"shell": "bash", "command": LINE, "direct": True, "target": "a\nb"},
            "target",
            (),
        ),
        ({"shell": "bash", "command": "sheet parse N-34-130-D"}, "command", ()),
        ({"shell": "bash", "command": "elevation nope"}, "command", ()),
        ({"shell": "bash", "plan": {"items": []}, "direct": True}, "plan", ()),
    ],
    ids=[
        "no_shell",
        "unknown_shell",
        "neither",
        "both",
        "plan_without_direct",
        "target_without_direct",
        "empty_target",
        "control_in_target",
        "no_data_command",
        "unknown_command",
        "plan_of_no_plan",
    ],
)
def test_generate_script_refuses_a_bad_request_before_any_work(kwargs, option, options):
    with pytest.raises(ValidationError) as caught:
        generate_script(**kwargs)

    assert caught.value.option == option
    assert tuple(caught.value.options or ()) == options


def test_generate_script_names_the_shells_and_the_data_commands_it_takes():
    with pytest.raises(ValidationError) as shell:
        generate_script(shell="cmd", command=LINE)
    with pytest.raises(ValidationError) as command:
        generate_script(shell="bash", command="sheet parse N-34-130-D")

    assert tuple(shell.value.allowed) == ("bash", "powershell")
    assert "elevation download" in command.value.allowed
    assert "sheet parse" not in command.value.allowed


# --- the Kartograf script ----------------------------------------------------------


@pytest.mark.usefixtures("released")
def test_the_kartograf_script_of_bash_pins_the_release_and_runs_the_line(tmp_path):
    script = generate_script(shell="bash", command=f"kartograf {LINE}")

    assert (script.shell, script.kind, script.files, script.left_out) == (
        "bash",
        "kartograf",
        (),
        (),
    )
    lines = script.text.splitlines()
    assert lines[0] == "#!/usr/bin/env bash"
    assert (
        "pin='kartograf @ git+https://github.com/Daldek/Kartograf.git@v0.9.0'" in lines
    )
    # the path is left for the shell, whose ``~`` is the home directory of the machine
    assert lines[lines.index("version=0.9.0") + 2] == (
        "arguments=(elevation download --product nmt --sheet N-34-130-D-d-2-4"
        " --resolution 1m --vertical-crs EVRF2007 -o ~/dem)"
    )
    assert "CLMS_CREDENTIALS" not in script.text  # no keyed source
    assert script.text.endswith('exec uvx --from "$pin" kartograf "${arguments[@]}"\n')
    _bash_syntax(script.text, tmp_path)


@pytest.mark.usefixtures("released")
def test_the_kartograf_script_of_bash_stops_without_the_key_of_a_keyed_source(
    tmp_path,
):
    script = generate_script(shell="bash", command=CORINE)

    assert (
        'if [ -z "${CLMS_CREDENTIALS:-}" ] && ! { [ "$(uname -s)" = Darwin ] && '
        "security find-generic-password -s clms-token >/dev/null 2>&1; }; then"
    ) in script.text.splitlines()
    _bash_syntax(script.text, tmp_path)
    # the check runs: without the variable, on Linux, the script stops before kartograf
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "uv").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (tmp_path / "bin" / "uv").chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    done = subprocess.run(
        ["bash", "-c", script.text],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert (done.returncode, done.stdout) == (1, "")
    assert done.stderr.startswith("CLMS_CREDENTIALS is not set")


@pytest.mark.usefixtures("released")
def test_the_kartograf_script_of_powershell_is_ascii_with_the_words_of_the_line():
    script = generate_script(shell="powershell", command=CORINE)

    assert script.text.isascii() and _ps_balanced(script.text)
    assert _ps_line(script.text, "$pin = ") == (
        "'kartograf @ git+https://github.com/Daldek/Kartograf.git@v0.9.0'"
    )
    words = _ps_line(script.text, "$arguments = @(")[:-1]
    assert words.endswith(", '--root', (Join-Path $HOME 'kartograf')")
    assert _ps_values(words.removesuffix(", (Join-Path $HOME 'kartograf')")) == [
        *CORINE.split()[:-1]
    ]
    assert (
        "if (-not $env:CLMS_CREDENTIALS -and -not (Test-Keychain 'clms-token')) {"
        in script.text.splitlines()
    )


def test_every_key_exchange_of_the_registry_has_its_variable_and_keychain():
    auths = {
        source.auth
        for group in SOURCE_GROUPS
        for source in list_sources(group=group).sources
        if source.auth != "none"
    }

    assert auths and auths <= set(_KEYS)
    assert _KEYS["clms_oauth"].variable == "CLMS_CREDENTIALS"
    assert _KEYS["clms_oauth"].keychain == KEYCHAIN_SERVICE


@pytest.mark.parametrize("version", ["0.10.0.dev0", "0.9.0rc1", "0.9.0+abc"])
def test_a_development_version_has_no_kartograf_script(monkeypatch, version):
    monkeypatch.setattr(kartograf, "__version__", version)

    with pytest.raises(UnsupportedError) as caught:
        generate_script(shell="bash", command=LINE)

    report = error_report(caught.value)
    assert (report.code, report.exit_code) == ("unsupported", 15)
    assert report.details["reason"] == "development_version"
    assert report.details["version"] == version
    assert "--direct" in (report.hint or "")


# --- the direct script: what it downloads ------------------------------------------


def test_the_direct_script_classifies_every_position_of_a_plan():
    url = "https://example.test/"
    plan = _plan(
        _item("a.asc", url=url + "a.asc", size=24, sha256="AB" * 32),
        _item(
            "b.tif", fetch=False, source="eu.clms.corine", fetch_reason="credentials"
        ),
        _item("c.tif", fetch=False, fetch_reason="built"),
        _item("d.zip", fetch_reason="feed_not_cached"),
        _item("e.asc", status="check_failed", action=None),
        _item("f.asc"),  # a fetch without a URL and no reason: a sheet not indexed
        _item("g.asc", url=url + "g.asc", action="conflict", reason="output_exists"),
        _item("ATTRIBUTION.txt", fetch=False, fetch_reason="built"),
    )

    script = _direct(plan)

    assert script.kind == "direct"
    assert script.files == (
        ScriptFile("a.asc", "a", url + "a.asc", 24, "ab" * 32, NMT),
    )
    assert script.left_out == (
        LeftOutFile("b.tif", "b", "credentials"),
        LeftOutFile("c.tif", "c", "built"),
        LeftOutFile("d.zip", "d", "feed_not_cached"),
        LeftOutFile("e.asc", "e", "check_failed"),
        LeftOutFile("f.asc", "f", "no_url"),
        LeftOutFile("g.asc", "g", "output_exists"),
    )
    header = " ".join(
        row[2:] for row in script.text.splitlines() if row.startswith("# ")
    )
    assert "Left out, 6 files:" in header
    assert "c.tif (c): Kartograf builds it" in header
    assert "f.asc (f): the plan names no URL of it" in header
    assert "g.asc (g): a conflict of its target (output_exists)" in header


def test_two_files_of_one_name_in_a_store_plan_are_both_left_out():
    url = "https://example.test/"
    plan = _plan(
        _item("x.zip", url=url + "1/x.zip", action=None, track="collection"),
        _item("x.zip", url=url + "2/x.zip", action=None, track="collection"),
        _item("y.zip", url=url + "y.zip", action=None, track="collection"),
        output_dir=None,
    )

    script = _direct(plan)

    assert [file.name for file in script.files] == ["y.zip"]
    assert [file.reason for file in script.left_out] == [
        "duplicate_output_name",
        "duplicate_output_name",
    ]


def test_a_plan_with_nothing_to_download_has_no_direct_script():
    plan = _plan(
        _item("c.tif", fetch=False, fetch_reason="built"),
        _item("d.zip", fetch_reason="feed_not_cached"),
    )

    with pytest.raises(UnsupportedError) as caught:
        _direct(plan)

    report = error_report(caught.value).to_dict()
    assert (report["code"], report["exit_code"]) == ("unsupported", 15)
    assert report["details"]["reason"] == "no_direct_files"
    assert report["details"]["option"] == "direct"
    assert report["details"]["files"] == [
        {"name": "c.tif", "unit": "c", "reason": "built"},
        {"name": "d.zip", "unit": "d", "reason": "feed_not_cached"},
    ]


@pytest.mark.parametrize(
    ("item", "said"),
    [
        (_item("a.asc", fetch=False, source=None), "does not say where a.asc"),
        (_item("a/b.asc", url="https://example.test/b.asc"), "no plain file name"),
        (_item("..", url="https://example.test/b.asc"), "no plain file name"),
        (_item("b.asc", url="file:///etc/passwd"), "no http or https URL"),
        (_item("b.asc", url="https://example.test/a b"), "no http or https URL"),
        (_item("b.asc", url="https://x.test/b", sha256="12" * 31), "64 hexadecimal"),
    ],
    ids=["plan_0_9_0", "directory", "dot_dot", "file_url", "space", "short_sha256"],
)
def test_a_saved_plan_is_checked_before_a_script_is_written(item, said):
    with pytest.raises(ValidationError, match=said) as caught:
        _direct(_plan(item))

    assert caught.value.option == "plan"


def test_the_direct_script_of_a_line_plans_it_detached_into_its_target(monkeypatch):
    """The line's ``-o`` is the default target, as typed; the plan's notices stay."""
    notice = Notice("info", "sheet_list", "1 sheet")
    plan = _plan(_item("a.asc", url="https://example.test/a.asc"), notices=(notice,))
    calls = []

    def check(command, options, **kwargs):
        calls.append((command, kwargs["detached"]))
        return SimpleNamespace(result=plan)

    monkeypatch.setattr("kartograf.script.check_command", check)

    script = generate_script(shell="bash", command=LINE, direct=True, cache=False)
    other = generate_script(
        shell="bash", command=LINE, direct=True, target="/srv/x", cache=False
    )

    assert calls == [("elevation download", True)] * 2
    assert "target=~/dem" in script.text.splitlines()
    assert "target=/srv/x" in other.text.splitlines()
    assert script.notices == (notice,)
    assert f"#   kartograf {LINE.replace('~/dem', chr(39) + '~/dem' + chr(39))}" in (
        script.text.splitlines()
    )


# --- the direct script of bash, run --------------------------------------------------


def _stub_curl(tmp_path: Path, served: dict[str, bytes]) -> dict[str, str]:
    """A ``curl`` that writes the bytes of a URL from ``served`` (by its last part)
    to ``--output`` and logs the URL; the environment of a run with it."""
    files = tmp_path / "served"
    files.mkdir()
    for name, data in served.items():
        (files / name).write_bytes(data)
    stub = tmp_path / "bin" / "curl"
    stub.parent.mkdir()
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "out= url=\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    --output) out=$2; shift 2 ;;\n"
        "    --proto|--proto-redir) shift 2 ;;\n"
        "    -*) shift ;;\n"
        "    *) url=$1; shift ;;\n"
        "  esac\n"
        "done\n"
        'printf \'%s\\n\' "$url" >> "$STUB_LOG"\n'
        'src="$STUB_FILES/${url##*/}"\n'
        '[ -f "$src" ] || exit 22\n'
        'cp -- "$src" "$out"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return {
        "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "STUB_FILES": str(files),
        "STUB_LOG": str(tmp_path / "curl.log"),
    }


def _stub_date(env: dict[str, str]) -> dict[str, str]:
    """A ``date`` next to the stub ``curl`` that logs its arguments and says ``DAY``;
    the environment of a run with both."""
    stub = Path(env["PATH"].split(os.pathsep)[0]) / "date"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$DATE_LOG"\n'
        f"printf '%s\\n' {DAY}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return {**env, "DATE_LOG": str(Path(env["STUB_LOG"]).with_name("date.log"))}


def _run(text: str, env: dict[str, str], tmp_path: Path):
    script = tmp_path / "direct.sh"
    script.write_text(text, encoding="utf-8")
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=tmp_path,
    )


def _saved_plan(tmp_path: Path, *items: PlanItem) -> UpdatePlan:
    """The plan as ``--check --json`` saves it and ``--plan`` reads it back."""
    path = tmp_path / "plan.json"
    path.write_text(_plan(*items).to_json(), encoding="utf-8")
    return UpdatePlan.from_json(path.read_text(encoding="utf-8"))


def test_the_bash_direct_script_downloads_checks_and_attributes_once(tmp_path):
    odd = "Łąka 'a' $x.asc"  # quotes, a dollar and Polish letters of a name
    plan = _saved_plan(
        tmp_path,
        _item(
            "N-34.asc",
            url="https://example.test/pl/N-34.asc",
            size=len(ASC),
            sha256=hashlib.sha256(ASC).hexdigest().upper(),
        ),
        _item(odd, url="https://example.test/pl/odd.asc", size=len(ASC)),
        _item("CTES96.zip", url="https://example.test/cz/CTES96.zip", source=DMR5G),
        _item("c.tif", fetch=False, fetch_reason="built"),
        _item("ATTRIBUTION.txt", fetch=False, fetch_reason="built"),
    )
    env = _stub_date(
        _stub_curl(tmp_path, {"N-34.asc": ASC, "odd.asc": ASC, "CTES96.zip": ZIP})
    )
    target = Path(env["HOME"]) / "data dir"
    target.mkdir(parents=True)
    (target / "ATTRIBUTION.txt").write_text(f"own line\n{Z_DMR5G}\n", encoding="utf-8")
    script = _direct(plan, target="~/data dir")
    _bash_syntax(script.text, tmp_path)

    first = _run(script.text, env, tmp_path)
    attribution = (target / "ATTRIBUTION.txt").read_text(encoding="utf-8")
    second = _run(script.text, env, tmp_path)

    assert first.returncode == 0, first.stderr
    assert "target=~/'data dir'" in script.text.splitlines()
    assert (target / "N-34.asc").read_bytes() == ASC
    assert (target / odd).read_bytes() == ASC
    assert (target / "CTES96.zip").read_bytes() == ZIP
    assert attribution == f"own line\n{Z_DMR5G}\n{G_NMT}\n"
    assert first.stdout.splitlines()[-1] == f"3 files downloaded into {target}"
    assert second.returncode == 0, second.stderr
    assert (target / "ATTRIBUTION.txt").read_text(encoding="utf-8") == attribution
    assert sorted(p.name for p in target.iterdir()) == sorted(
        ["N-34.asc", odd, "CTES96.zip", "ATTRIBUTION.txt"]
    )
    log = Path(env["STUB_LOG"]).read_text(encoding="utf-8").splitlines()
    assert log == 2 * [
        "https://example.test/pl/N-34.asc",
        "https://example.test/pl/odd.asc",
        "https://example.test/cz/CTES96.zip",
    ]
    dates = Path(env["DATE_LOG"]).read_text(encoding="utf-8").splitlines()
    assert dates == 2 * ["-u +%F"]


def test_the_direct_script_names_the_year_the_plan_knows_in_the_g_line():
    plan = _plan(
        _item("a.asc", url="https://example.test/a.asc", signal={"date": "2022-05-01"})
    )

    script = _direct(plan)

    assert (
        "for line in 'Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, NMT"
        " (wytworzono 2022, pozyskano '\"$day\"'); dane przetworzone'; do"
    ) in script.text.splitlines()


@pytest.mark.parametrize(
    ("size", "sha256", "said"),
    [
        (len(ASC) + 1, None, f"a.asc: {len(ASC)} bytes downloaded, the plan says"),
        (None, "0" * 64, "a.asc: its SHA-256 is not the one the registry pins"),
    ],
    ids=["size", "sha256"],
)
def test_the_bash_direct_script_stops_on_a_file_that_differs(
    tmp_path, size, sha256, said
):
    plan = _plan(
        _item("a.asc", url="https://example.test/a.asc", size=size, sha256=sha256),
        _item("b.asc", url="https://example.test/b.asc"),
    )
    env = _stub_curl(tmp_path, {"a.asc": ASC, "b.asc": ASC})

    done = _run(_direct(plan, target="out").text, env, tmp_path)

    assert done.returncode == 1
    assert done.stderr.startswith(said)
    assert list((tmp_path / "out").iterdir()) == []  # neither the file nor its .part


def test_the_bash_direct_script_stops_when_a_download_fails(tmp_path):
    plan = _plan(_item("a.asc", url="https://example.test/missing.asc"))
    env = _stub_curl(tmp_path, {})

    done = _run(_direct(plan, target="out").text, env, tmp_path)

    assert done.returncode == 1
    assert list((tmp_path / "out").iterdir()) == []


# --- the direct script of PowerShell -------------------------------------------------


def test_the_powershell_direct_script_is_ascii_and_keeps_every_value():
    name = "Łąka 'a' $x `y 😀.asc"
    url = "https://example.test/pl/a.asc?x='1'"
    sha256 = "ab" * 32
    plan = _plan(
        _item(name, url=url, size=24, sha256=sha256),
        _item("b.zip", url="https://example.test/b.zip", source=DMR5G),
    )

    script = _direct(plan, shell="powershell", target="~/dane/żółw")

    assert script.text.isascii() and _ps_balanced(script.text)
    assert "#!" not in script.text and "2>$null" not in script.text
    assert _ps_line(script.text, "$target = ") == (
        "(Join-Path $HOME ('dane/' + [char]0x017C + [char]0x00F3 + [char]0x0142 + 'w'))"
    )
    calls = [row for row in script.text.splitlines() if row.startswith("Get-PlanFile ")]
    first, second = (row.removeprefix("Get-PlanFile ") for row in calls)
    assert first.endswith(f" 24 '{sha256}'")
    assert _ps_values(first.replace(" 24 ", " ")) == [name, url, sha256]
    assert second == "'b.zip' 'https://example.test/b.zip' $null ''"
    lines = _ps_line(script.text, "foreach ($line in @(").removesuffix(")) {")
    assert _ps_line(script.text, "$day = ") == (
        "[DateTime]::UtcNow.ToString('yyyy-MM-dd', "
        "[Globalization.CultureInfo]::InvariantCulture)"
    )
    assert _ps_values(lines.replace(" + $day + ", f" + '{DAY}' + ")) == [
        G_NMT,
        Z_DMR5G,
    ]


@pytest.mark.usefixtures("released")
def test_a_header_value_that_is_not_ascii_is_an_escape_in_a_powershell_comment():
    script = _direct(
        _plan(_item("Łąka.asc", url="https://example.test/a.asc")),
        shell="powershell",
    )

    assert script.text.isascii()
    assert "# Generated by kartograf script generate" in script.text


@needs_pwsh
@pytest.mark.usefixtures("released")
def test_pwsh_parses_every_powershell_script(tmp_path):
    texts = [
        generate_script(shell="powershell", command=CORINE).text,
        _direct(
            _plan(_item("Łąka 'a'.asc", url="https://example.test/a.asc", size=1)),
            shell="powershell",
            target="~/x",
        ).text,
    ]
    for number, text in enumerate(texts):
        path = tmp_path / f"s{number}.ps1"
        path.write_text(text, encoding="ascii")
        parse = (
            "$errors = $null; [void][System.Management.Automation.Language.Parser]"
            f"::ParseFile('{path}', [ref]$null, [ref]$errors); "
            "if ($errors) { $errors; exit 1 }"
        )
        done = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", parse],
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stdout + done.stderr


# --- the texts of a script -----------------------------------------------------------


@pytest.mark.parametrize("key", RUNTIME)
def test_a_text_a_script_prints_holds_nothing_a_shell_expands(key):
    for text in MESSAGES[key]:
        assert not set(text) & set('"$`\\'), (key, text)
    assert MESSAGES[key].en.isascii()  # a script prints the English text
