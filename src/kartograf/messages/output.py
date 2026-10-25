"""Messages of the data output (``kartograf.output``): targets and plain files."""

from kartograf.messages import Text

MESSAGES = {
    # ``output``: the two write targets.
    "exclusive_options": Text(
        "output_dir and root exclude each other: write plain files (--output-dir) or "
        "the store (--root), not both",
        "output_dir i root wykluczaja sie: zapisz zwykle pliki (--output-dir) albo "
        "magazyn (--root), nie oba naraz",
    ),
    "exclusive_options_hint": Text(
        "Give --output-dir for plain files or --root for the store, not both",
        "Podaj --output-dir dla zwyklych plikow albo --root dla magazynu, nie oba "
        "naraz",
    ),
    "empty_output_dir": Text(
        "output_dir is empty: give the directory of the plain files or leave it out "
        "for the default store",
        "output_dir jest pusty: podaj katalog zwyklych plikow albo pomin go, aby "
        "uzyc domyslnego magazynu",
    ),
    # ``download.manager``: a manager writes plain files or a storage layout.
    "output_dir_excludes_storage": Text(
        "output_dir and storage exclude each other: the files of a plain write have "
        "no storage layout",
        "output_dir i storage wykluczaja sie: pliki zwyklego zapisu nie maja ukladu "
        "magazynu",
    ),
    # ``output``: the preflight of a plain write (every offending path in the details).
    "duplicate_output_name": Text(
        "{count} output paths of this request share a name (the first: {first})",
        "{count} sciezek wyjsciowych tego zadania ma te sama nazwe (pierwsza: {first})",
    ),
    "duplicate_output_name_hint": Text(
        "Narrow the request so that its files have distinct names; details.paths "
        "lists them",
        "Zawez zadanie tak, aby jego pliki mialy rozne nazwy; details.paths je "
        "wymienia",
    ),
    "output_in_store": Text(
        "{count} output paths are, or lie in, a store (the first: {first})",
        "{count} sciezek wyjsciowych jest magazynem albo lezy w magazynie (pierwsza: "
        "{first})",
    ),
    "directory_in_store": Text(
        "the output directory {path} is, or lies in, the store {store}",
        "katalog wyjsciowy {path} jest magazynem albo lezy w magazynie {store}",
    ),
    "output_in_store_hint": Text(
        "Use --root to write the store, or choose a directory outside every store",
        "Uzyj --root, aby zapisac magazyn, albo wybierz katalog poza kazdym magazynem",
    ),
    "output_exists": Text(
        "{count} output files exist (the first: {first})",
        "{count} plikow wyjsciowych juz istnieje (pierwszy: {first})",
    ),
    "output_exists_hint": Text(
        "Use --force to replace them; details.paths lists them",
        "Uzyj --force, aby je zastapic; details.paths je wymienia",
    ),
    "target_appeared": Text(
        "{path} appeared while the files were fetched; --force replaces it",
        "{path} pojawil sie w trakcie pobierania plikow; --force go zastepuje",
    ),
    # ``output``: an option that acts on the versions of a store, given with output_dir.
    "store_only_option": Text(
        "{option} acts on the versions of a store and does not apply to plain files "
        "(--output-dir)",
        "{option} dziala na wersjach magazynu i nie dotyczy zwyklych plikow "
        "(--output-dir)",
    ),
    "store_only_option_hint": Text(
        "Use --root to write the store, or leave out {option} for plain files",
        "Uzyj --root, aby zapisac magazyn, albo pomin {option} dla zwyklych plikow",
    ),
    # ``output``: PL sheets of a plain write that have no full flight (the newest FULL
    # flight is the only one a plain write takes).
    "skipped_incomplete": Text(
        "{sheet}: no full flight within the year range (the newest flight, {flight}, "
        "is partial)",
        "{sheet}: brak pelnego przelotu w zakresie lat (najnowszy przelot, {flight}, "
        "jest czesciowy)",
    ),
    "skipped_incomplete_hint": Text(
        "Use --root to write the store, which takes the newest flight, partial or not",
        "Uzyj --root, aby zapisac magazyn, ktory bierze najnowszy przelot, czesciowy "
        "lub nie",
    ),
    "skipped_incomplete_all": Text(
        "none of the {count} {count:plural(sheet|sheets)} has a full flight within "
        "the year range: nothing to write",
        "zaden z {count} {count:plural(arkusza|arkuszy|arkuszy)} nie ma pelnego "
        "przelotu w zakresie lat: nie ma czego zapisac",
    ),
    "skipped_incomplete_some": Text(
        "{count} {count:plural(sheet|sheets)} not written, no full flight within the "
        "year range ({sheets}); --root writes the store, which takes the newest "
        "flight, partial or not",
        "Nie zapisano {count} {count:plural(arkusza|arkuszy|arkuszy)}, brak pelnego "
        "przelotu w zakresie lat ({sheets}); --root zapisuje magazyn, ktory bierze "
        "najnowszy przelot, czesciowy lub nie",
    ),
    "full_sheet_redundant": Text(
        "--full-sheet has no effect with --output-dir: a plain write takes the newest "
        "full flight anyway",
        "--full-sheet nie dziala z --output-dir: zwykly zapis i tak bierze najnowszy "
        "pelny przelot",
    ),
}
