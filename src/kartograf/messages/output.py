"""Messages of the data output (``kartograf.output``): targets and plain files."""

from kartograf.messages import Text

MESSAGES = {
    # ``output``: the two write targets.
    "exclusive_options": Text(
        "output_dir and root exclude each other: write plain files (--output-dir) or "
        "the store (--root), not both",
        "output_dir i root wykluczają się: zapisz zwykłe pliki (--output-dir) albo "
        "magazyn (--root), nie oba naraz",
    ),
    "exclusive_options_hint": Text(
        "Give --output-dir for plain files or --root for the store, not both",
        "Podaj --output-dir dla zwykłych plików albo --root dla magazynu, nie oba "
        "naraz",
    ),
    "empty_output_dir": Text(
        "output_dir is empty: give the directory of the plain files or leave it out "
        "for the default store",
        "output_dir jest pusty: podaj katalog zwykłych plików albo pomiń go, aby "
        "użyć domyślnego magazynu",
    ),
    # ``download.manager``: a manager writes plain files or a storage layout.
    "output_dir_excludes_storage": Text(
        "output_dir and storage exclude each other: the files of a plain write have "
        "no storage layout",
        "output_dir i storage wykluczają się: pliki zwykłego zapisu nie mają układu "
        "magazynu",
    ),
    # ``output``: the preflight of a plain write (every offending path in the details).
    "duplicate_output_name": Text(
        "{count} output paths of this request share a name (the first: {first})",
        "{count} ścieżek wyjściowych tego żądania ma tę samą nazwę (pierwsza: {first})",
    ),
    "duplicate_output_name_hint": Text(
        "Narrow the request so that its files have distinct names; details.paths "
        "lists them",
        "Zawęź żądanie tak, aby jego pliki miały różne nazwy; details.paths je "
        "wymienia",
    ),
    "output_in_store": Text(
        "{count} output paths are, or lie in, a store (the first: {first})",
        "{count} ścieżek wyjściowych jest magazynem albo leży w magazynie (pierwsza: "
        "{first})",
    ),
    "directory_in_store": Text(
        "the output directory {path} is, or lies in, the store {store}",
        "katalog wyjściowy {path} jest magazynem albo leży w magazynie {store}",
    ),
    "output_in_store_hint": Text(
        "Use --root to write the store, or choose a directory outside every store",
        "Użyj --root, aby zapisać magazyn, albo wybierz katalog poza każdym magazynem",
    ),
    "output_exists": Text(
        "{count} output files exist (the first: {first})",
        "{count} plików wyjściowych już istnieje (pierwszy: {first})",
    ),
    "output_exists_hint": Text(
        "Use --force to replace them; details.paths lists them",
        "Użyj --force, aby je zastąpić; details.paths je wymienia",
    ),
    "target_appeared": Text(
        "{path} appeared while the files were fetched; --force replaces it",
        "{path} pojawił się w trakcie pobierania plików; --force go zastępuje",
    ),
    # ``output``: an option that acts on the versions of a store, given with output_dir.
    "store_only_option": Text(
        "{option} acts on the versions of a store and does not apply to plain files "
        "(--output-dir)",
        "{option} działa na wersjach magazynu i nie dotyczy zwykłych plików "
        "(--output-dir)",
    ),
    "store_only_option_hint": Text(
        "Use --root to write the store, or leave out {option} for plain files",
        "Użyj --root, aby zapisać magazyn, albo pomiń {option} dla zwykłych plików",
    ),
    # ``output``: PL sheets of a plain write that have no full flight (the newest FULL
    # flight is the only one a plain write takes).
    "skipped_incomplete": Text(
        "{sheet}: no full flight within the year range (the newest flight, {flight}, "
        "is partial)",
        "{sheet}: brak pełnego przelotu w zakresie lat (najnowszy przelot, {flight}, "
        "jest częściowy)",
    ),
    "skipped_incomplete_hint": Text(
        "Use --root to write the store, which takes the newest flight, partial or not",
        "Użyj --root, aby zapisać magazyn, który bierze najnowszy przelot, częściowy "
        "lub nie",
    ),
    "skipped_incomplete_all": Text(
        "none of the {count} {count:plural(sheet|sheets)} has a full flight within "
        "the year range: nothing to write",
        "żaden z {count} {count:plural(arkusza|arkuszy|arkuszy)} nie ma pełnego "
        "przelotu w zakresie lat: nie ma czego zapisać",
    ),
    "skipped_incomplete_some": Text(
        "{count} {count:plural(sheet|sheets)} not written, no full flight within the "
        "year range ({sheets}); --root writes the store, which takes the newest "
        "flight, partial or not",
        "Nie zapisano {count} {count:plural(arkusza|arkuszy|arkuszy)}, brak pełnego "
        "przelotu w zakresie lat ({sheets}); --root zapisuje magazyn, który bierze "
        "najnowszy przelot, częściowy lub nie",
    ),
    "full_sheet_redundant": Text(
        "--full-sheet has no effect with --output-dir: a plain write takes the newest "
        "full flight anyway",
        "--full-sheet nie działa z --output-dir: zwykły zapis i tak bierze najnowszy "
        "pełny przelot",
    ),
}
