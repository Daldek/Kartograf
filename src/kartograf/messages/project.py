"""Messages of the projects (``kartograf.project``): the manifest and its operations."""

from kartograf.messages import Text

MESSAGES = {
    # ``project.commands``.
    "data_commands_allowed": Text(
        "commands that write data can be added to the project: {data_commands_text}",
        "do projektu mozna dodac komendy zapisujace dane: {data_commands_text}",
    ),
    # ``project.manifest``.
    "place_problem": Text("{where}: {problem}", "{where}: {problem}"),
    "within": Text("{where}{path}", "{where}{path}"),
    "manifest_problem": Text(
        "{manifest_name}: {problem}", "{manifest_name}: {problem}"
    ),
    "lock_owner": Text(
        "{lock_name}: host {host}, pid {pid}, since {since}",
        "{lock_name}: host {host}, pid {pid}, od {since}",
    ),
    "task_name_rule": Text(
        "lowercase letters, digits, '-' and '_', starting with a letter or digit, up "
        "to 64 characters",
        "male litery, cyfry, '-' i '_', na poczatku litera albo cyfra, do 64 znakow",
    ),
    "duplicate_json_key": Text(
        "duplicate key {key_value!r}",
        "powtorzony klucz {key_value!r}",
    ),
    "disallowed_json_constant": Text(
        "disallowed value {name}",
        "niedozwolona wartosc {name}",
    ),
    "project_is_file": Text(
        "{directory} is a file, but --project requires a project directory "
        "(containing {manifest_name}), e.g. --project {parent}",
        "{directory} to plik, a --project wymaga katalogu projektu (z "
        "{manifest_name}), np. --project {parent}",
    ),
    "project_not_found": Text(
        "no project in {directory} ({manifest_name}); create one: kartograf project "
        "init --root DIR or specify --project DIR",
        "brak projektu w {directory} ({manifest_name}); utworz: kartograf project "
        "init --root KATALOG albo wskaz --project KATALOG",
    ),
    "manifest_read_failed": Text(
        "{manifest_name}: cannot read {path}: {error}",
        "{manifest_name}: nie mozna odczytac {path}: {error}",
    ),
    "manifest_invalid_json": Text(
        "{manifest_name}: invalid JSON: {error}",
        "{manifest_name}: nieprawidlowy JSON: {error}",
    ),
    "unknown_key": Text("unknown key {key_value!r}", "nieznany klucz {key_value!r}"),
    "missing_key": Text("missing key {key_value!r}", "brak klucza {key_value!r}"),
    "expected_json_object": Text("expected a JSON object", "oczekiwano obiektu JSON"),
    "missing_schema_key": Text("missing key 'schema'", "brak klucza 'schema'"),
    "unknown_schema": Text(
        "unknown schema {doc_schema!r} (this Kartograf knows {project_schema}); "
        "update Kartograf",
        "nieznany schemat {doc_schema!r} (ten Kartograf zna {project_schema}); "
        "zaktualizuj Kartografa",
    ),
    "expected_store_path": Text(
        "expected a non-empty store path",
        "oczekiwano niepustej sciezki magazynu",
    ),
    "expected_task_list": Text("expected a list of tasks", "oczekiwano listy zadan"),
    "expected_task_object": Text(
        "expected a task object",
        "oczekiwano obiektu zadania",
    ),
    "task_location": Text("task {name}", "zadanie {name}"),
    "invalid_task_name": Text(
        "invalid task name {name!r} ({task_name_rule})",
        "nieprawidlowa nazwa zadania {name!r} ({task_name_rule})",
    ),
    "duplicate_task_name": Text("duplicate task name", "nazwa zadania powtorzona"),
    "unknown_command": Text(
        "unknown command {raw_command!r} (data commands: {data_commands_text})",
        "nieznana komenda {raw_command!r} (komendy danych: {data_commands_text})",
    ),
    "pinned_at_not_iso": Text(
        "pinned_at: expected an ISO 8601 instant, got {pinned_at!r}",
        "pinned_at: oczekiwano chwili ISO 8601, podano {pinned_at!r}",
    ),
    "pin_fields_mismatch": Text(
        "pinned_at and kartograf_version: both null (task not downloaded) or both "
        "strings (task pinned)",
        "pinned_at i kartograf_version: oba null (zadanie niepobrane) albo oba napisy "
        "(zadanie przypiete)",
    ),
    "files_not_list": Text(
        "files: expected a list of pinned files",
        "files: oczekiwano listy przypietych plikow",
    ),
    "files_pin_mismatch": Text(
        "files: a pinned task has at least one file, and a task not downloaded "
        "(pinned_at null) has an empty list",
        "files: zadanie przypiete ma co najmniej jeden plik, a niepobrane (pinned_at "
        "null) - pusta liste",
    ),
    "geometry_sha256_scope": Text(
        "geometry_sha256: exactly in a pinned task with options.geometry",
        "geometry_sha256: dokladnie w zadaniu przypietym z options.geometry",
    ),
    "geometry_sha256_not_object": Text(
        "geometry_sha256: expected an object {{file name: sha256}}",
        "geometry_sha256: oczekiwano obiektu {{nazwa pliku: sha256}}",
    ),
    "version_pinned_twice": Text("version pinned twice", "wersja przypieta dwa razy"),
    "path_not_relative_nonempty": Text(
        "expected a non-empty path relative to the store",
        "oczekiwano niepustej sciezki wzglednej do magazynu",
    ),
    "path_must_be_relative": Text(
        "path must be relative to the store, with the / separator",
        "sciezka musi byc wzgledna do magazynu, z separatorem /",
    ),
    "path_bad_segments": Text(
        "path must not have '.', '..' or empty segments",
        "sciezka nie moze miec segmentow '.', '..' ani pustych",
    ),
    "file_not_object": Text(
        "expected a pinned file object",
        "oczekiwano obiektu przypietego pliku",
    ),
    "role_not_allowed": Text(
        "expected one of: {roles}",
        "oczekiwano jednej z: {roles}",
    ),
    "expected_string": Text("expected a string", "oczekiwano napisu"),
    "standard_path_in_versions": Text(
        "standard path must not lie in versions/",
        "sciezka standardowa nie moze lezec w versions/",
    ),
    "version_path_outside_versions": Text(
        "version path must lie in versions/ of the store (without .incoming)",
        "sciezka wersji musi lezec w versions/ magazynu (bez .incoming)",
    ),
    "version_label_empty": Text(
        "expected a non-empty version label",
        "oczekiwano niepustej etykiety wersji",
    ),
    "sha256_not_hex": Text(
        "expected 64 lowercase hex characters",
        "oczekiwano 64 malych znakow hex",
    ),
    "expected_non_negative_int": Text(
        "expected an integer >= 0",
        "oczekiwano liczby calkowitej >= 0",
    ),
    "lock_owner_unknown": Text(
        "{lock_name}: owner unknown",
        "{lock_name}: wlasciciel nieznany",
    ),
    "project_locked": Text(
        "project locked by another process ({owner_text}); if no kartograf is working "
        "on this project, remove the directory {lock}",
        "projekt zablokowany przez inny proces ({owner_text}); jesli zaden kartograf "
        "nie pracuje na tym projekcie, usun katalog {lock}",
    ),
    "project_lock_failed": Text(
        "cannot lock the project ({lock}): {error}",
        "nie mozna zablokowac projektu ({lock}): {error}",
    ),
    "manifest_dir_sync_failed": Text(
        "{manifest_name}: writing {directory}: {error}",
        "{manifest_name}: zapis {directory}: {error}",
    ),
    "manifest_write_failed": Text(
        "{manifest_name}: cannot write {target}: {error}",
        "{manifest_name}: nie mozna zapisac {target}: {error}",
    ),
    "project_already_exists": Text(
        "project already exists: {target}",
        "projekt juz istnieje: {target}",
    ),
    # ``project.operations``.
    "unit_problem": Text("{unit}: {problem}", "{unit}: {problem}"),
    "task_notice": Text("{task}: {text}", "{task}: {text}"),
    "corrupt_detail": Text("{error}; {repair_advice}", "{error}; {repair_advice}"),
    "project_store_missing": Text(
        "project store does not exist: {root}; attach the share or fix root in "
        "{manifest_name}",
        "magazyn projektu nie istnieje: {root}; podlacz udzial albo popraw root w "
        "{manifest_name}",
    ),
    "task_changed_concurrently": Text(
        "{name}: task changed in the meantime by another process; nothing was saved - "
        "repeat the command",
        "{name}: zadanie zmienione w tym czasie przez inny proces; nic nie zapisano - "
        "ponow polecenie",
    ),
    "no_tasks_known": Text(
        "none ({add_command} NAME ...)", "brak ({add_command} NAZWA ...)"
    ),
    "unknown_task": Text(
        "unknown task {name!r}; project tasks: {known}",
        "nieznane zadanie {name!r}; zadania projektu: {known}",
    ),
    "store_create_failed": Text(
        "cannot create store {store}: {error}",
        "nie mozna utworzyc magazynu {store}: {error}",
    ),
    "task_already_exists": Text(
        "task {name} already exists; remove it ({project_command}) or choose another "
        "name",
        "zadanie {name} juz istnieje; usun je ({project_command}) albo wybierz inna "
        "nazwe",
    ),
    "file_outside_store": Text(
        "{unit}: file outside store {store}: {version_path}",
        "{unit}: plik poza magazynem {store}: {version_path}",
    ),
    "version_not_pinnable": Text(
        "{unit}: version {version} without a readable sidecar (sha256, size_bytes) - "
        "cannot be pinned",
        "{unit}: wersja {version} bez czytelnego sidecara (sha256, size_bytes) - nie "
        "moze byc przypieta",
    ),
    "unknown_update_mode": Text(
        "Unknown update mode update={update!r} (allowed: None, 'upgrade', 'force'); "
        "check without downloading: check_project",
        "Nieznany tryb update={update!r} (dozwolone: None, 'upgrade', 'force'); "
        "sprawdzenie bez pobierania: check_project",
    ),
    "geometry_file_changed": Text(
        "geometry file {options_geometry} has changed since pinning; restore it or "
        "accept the new area: {upgrade_hint}",
        "plik geometrii {options_geometry} zmienil sie od przypiecia; przywroc go "
        "albo przyjmij nowy obszar: {upgrade_hint}",
    ),
    "task_incomplete_no_pin": Text(
        "task did not give a full result - nothing pinned",
        "zadanie nie dalo pelnego wyniku - nic nie przypieto",
    ),
    "repair_advice": Text(
        "restore the version directory from a store backup or run {project_command} "
        "(sets the damaged version aside and downloads it again)",
        "przywroc katalog wersji z kopii magazynu albo uruchom {project_command} "
        "(odklada uszkodzona wersje i pobiera ja ponownie)",
    ),
    "pinned_size_mismatch": Text(
        "{unit}: pinned version {version} has a different size than the pinned one - "
        "{repair_advice}",
        "{unit}: przypieta wersja {version} ma inny rozmiar niz przypiety - "
        "{repair_advice}",
    ),
    "pin_path_outside_store": Text(
        "{unit}: path of pinned version {version} goes outside the store (symbolic "
        "link) - not setting it aside",
        "{unit}: sciezka przypietej wersji {version} wykracza poza magazyn "
        "(dowiazanie symboliczne) - nie odkladam jej",
    ),
    "no_free_aside_name": Text(
        "{directory}: no free directory name for the damaged version",
        "{directory}: brak wolnej nazwy katalogu na uszkodzona wersje",
    ),
    "repin_failed": Text(
        "{unit}: could not restore pinned version {version}: {error}",
        "{unit}: nie udalo sie odtworzyc przypietej wersji {version}: {error}",
    ),
    "restore_source_conflict": Text(
        "{unit}: source content differs from the pinned one (pinned {label}, "
        "downloaded {candidates_label}); pin left unchanged - restore the store from "
        "a backup or accept the new version: {upgrade_hint}",
        "{unit}: zrodlo ma inna tresc niz przypieta (przypieta {label}, pobrana "
        "{candidates_label}); przypiecie bez zmian - przywroc magazyn z kopii albo "
        "przyjmij nowa wersje: {upgrade_hint}",
    ),
    "restore_pinned_file_missing": Text(
        "{unit}: pinned file {path} is not in the task result; pin left unchanged - "
        "restore the store from a backup or accept the new result: {upgrade_hint}",
        "{unit}: przypietego pliku {path} nie ma w wyniku zadania; przypiecie bez "
        "zmian - przywroc magazyn z kopii albo przyjmij nowy wynik: {upgrade_hint}",
    ),
    "sidecar_sha256_mismatch": Text(
        "sidecar {version} has a different sha256 than the pinned one",
        "sidecar {version} ma inne sha256 niz przypiete",
    ),
    "version_bytes_mismatch": Text(
        "{version} has different bytes than the pinned ones",
        "{version} ma inne bajty niz przypiete",
    ),
    "pinned_version_missing": Text(
        "pinned version missing; restore a store backup or run {project_command}",
        "brak przypietej wersji; przywroc kopie magazynu albo uruchom "
        "{project_command}",
    ),
    "pinned_path_escapes": Text(
        "pinned version path escapes the store",
        "sciezka przypietej wersji wykracza poza magazyn",
    ),
    "standard_path_escapes": Text(
        "standard path escapes the store",
        "sciezka standardowa wykracza poza magazyn",
    ),
    "sidecar_unreadable": Text(
        "version sidecar is unreadable or inconsistent with the version name",
        "sidecar wersji jest nieczytelny lub niezgodny z nazwa wersji",
    ),
    "sidecar_pin_mismatch": Text(
        "version sidecar does not match the pin",
        "sidecar wersji nie zgadza sie z przypieciem",
    ),
    "data_sha256_mismatch": Text(
        "SHA-256 checksum of the data differs from the pinned one",
        "suma SHA-256 danych jest inna niz przypieta",
    ),
    "pinned_file_missing": Text(
        "pinned file missing from the store; restore a backup or run {project_command}",
        "brak przypietego pliku w magazynie; przywroc kopie albo uruchom "
        "{project_command}",
    ),
    "newer_version_available": Text(
        "newer version in the store or at the source; run {upgrade_hint}",
        "nowsza wersja w magazynie albo u zrodla; uruchom {upgrade_hint}",
    ),
    "geometry_changed_since_pin": Text(
        "{name}: geometry file has changed since pinning; the update plan applies to "
        "the current geometry",
        "{name}: plik geometrii zmienil sie od przypiecia; plan aktualizacji dotyczy "
        "obecnej geometrii",
    ),
    "file_not_in_result": Text(
        "file not in the task result",
        "plik poza wynikiem zadania",
    ),
}
