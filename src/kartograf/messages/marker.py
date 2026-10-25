"""Messages of the store marker (``kartograf.marker``): nesting, layout and marker."""

from kartograf.messages import Text

MESSAGES = {
    # ``marker``: a store does not nest in another store (any tool).
    "inside_a_store": Text(
        "{path} lies inside the store {ancestor} ({marker}): a store does not nest "
        "in another store",
        "{path} lezy w magazynie {ancestor} ({marker}): magazyn nie zagniezdza sie "
        "w innym magazynie",
    ),
    "holds_another_store": Text(
        "{path} holds {marker}, the marker of another store: a store does not nest "
        "in another store",
        "{path} zawiera {marker}, znacznik innego magazynu: magazyn nie zagniezdza "
        "sie w innym magazynie",
    ),
    "store_below": Text(
        "the store {folder} ({marker}) lies below {path}: a store does not nest in "
        "another store",
        "magazyn {folder} ({marker}) lezy pod {path}: magazyn nie zagniezdza sie w "
        "innym magazynie",
    ),
    # ``marker``: the document and the layout of a root.
    "not_a_marker": Text(
        "{path} is not a {schema} document",
        "{path} nie jest dokumentem {schema}",
    ),
    "layout_without_marker": Text(
        "{path} has the layout of a store but no {marker}",
        "{path} ma uklad magazynu, ale nie ma {marker}",
    ),
    "init_hint": Text(
        "kartograf store init --root {path} verifies the layout and writes the marker",
        "kartograf store init --root {path} sprawdza uklad i zapisuje znacznik",
    ),
    "not_empty": Text(
        "{path} is not empty and has no {marker}: a store root is a new or empty "
        "directory",
        "{path} nie jest pusty i nie ma {marker}: korzen magazynu to nowy albo pusty "
        "katalog",
    ),
    "not_empty_hint": Text(
        "Give a new or empty directory as the store root",
        "Podaj nowy albo pusty katalog jako korzen magazynu",
    ),
    "naive_time": Text(
        "created_at needs a time zone",
        "created_at wymaga strefy czasowej",
    ),
    "unexpected_entry": Text(
        "unexpected entry '{name}' at the top level",
        "nieoczekiwany wpis '{name}' na najwyzszym poziomie",
    ),
    "tree_not_directory": Text(
        "'{name}' is not a directory",
        "'{name}' nie jest katalogiem",
    ),
    "not_a_store": Text(
        "{path} is not the layout of a Kartograf store ({count} found)",
        "{path} nie ma ukladu magazynu Kartografa (znaleziono: {count})",
    ),
    "layout_hint": Text(
        "Move what does not belong out of the root or give another root; "
        "details.problems lists it",
        "Przenies to, co nie nalezy do magazynu, poza korzen albo podaj inny korzen; "
        "details.problems to wymienia",
    ),
    "foreign_sidecar": Text(
        "{path} is not a kartograf-meta/1 sidecar",
        "{path} nie jest sidecarem kartograf-meta/1",
    ),
}
