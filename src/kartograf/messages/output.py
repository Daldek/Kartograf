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
}
