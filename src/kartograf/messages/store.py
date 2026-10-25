"""Messages of the store read API and its documents (``kartograf.store*``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``store``.
    "sidecar_unreadable": Text(
        "Cannot read the sidecar {side}: {error}",
        "Nie mozna odczytac sidecara {side}: {error}",
    ),
    "sidecar_unknown_schema": Text(
        "Unknown sidecar schema {schema!r} (expected {expected}): {side}",
        "Nieznany schemat sidecara {schema!r} (oczekiwano {expected}): {side}",
    ),
    "invalid_unit": Text(
        "Invalid store unit: {unit!r}",
        "Nieprawidlowa jednostka magazynu: {unit!r}",
    ),
    "units_not_string": Text(
        "units: give a collection of unit names, not a string ({units!r})",
        "units: podaj kolekcje nazw jednostek, nie napis ({units!r})",
    ),
    "unit_path_too_long": Text(
        "The store unit gives a path that is too long: {path}",
        "Jednostka magazynu daje zbyt dluga sciezke: {path}",
    ),
    "invalid_segment": Text(
        "Invalid store segment: {segment!r} (expected <product>/<variant>, e.g. "
        "nmt/pl_1992_1m_evrf2007)",
        "Nieprawidlowy segment magazynu: {segment!r} (oczekiwano <produkt>/<wariant>, "
        "np. nmt/pl_1992_1m_evrf2007)",
    ),
    "invalid_partition": Text(
        "Invalid part of a segment: {partition!r} (expected a key of list_partitions: "
        '".", "<directory>[/<directory>...]" or "<directory>[/<directory>...]/.")',
        "Nieprawidlowa czesc segmentu: {partition!r} (oczekiwano klucza z "
        'list_partitions: ".", "<katalog>[/<katalog>...]" albo '
        '"<katalog>[/<katalog>...]/.")',
    ),
    "skip_versions_not_string": Text(
        "skip_versions: give a collection of version directory paths, not a string",
        "skip_versions: podaj kolekcje sciezek katalogow wersji, nie napis",
    ),
    "skip_versions_names": Text(
        "skip_versions[{version!r}]: give the names of the data files of the version "
        "(no sidecars, paths or hidden names), not {names!r}",
        "skip_versions[{version!r}]: podaj nazwy plikow danych wersji (bez sidecarow, "
        "sciezek i nazw ukrytych), nie {names!r}",
    ),
    "segment_is_link": Text(
        "The store segment is a link: {path}",
        "Segment magazynu jest dowiazaniem: {path}",
    ),
    "target_positive": Text(
        "target: give a positive number of parts, not {target!r}",
        "target: podaj dodatnia liczbe czesci, nie {target!r}",
    ),
    "units_need_segment": Text(
        "units needs segment (the units of one segment)",
        "units wymaga segment (jednostki jednego segmentu)",
    ),
    "partition_needs_segment": Text(
        "partition needs segment (a part of one segment)",
        "partition wymaga segment (czesc jednego segmentu)",
    ),
    "units_or_partition": Text(
        "units or partition, not both at once",
        "units albo partition, nie oba naraz",
    ),
    # The name of a segment: the descriptor name and the variant; ``{separator}`` is the
    # middle dot that joins the parts (the texts of the catalog are ASCII).
    "segment_name": Text("{name}{label}", "{name}{label}"),
    "preview_label": Text(
        "{separator}{year}{separator}preview",
        "{separator}{year}{separator}podglad",
    ),
    "hsg_segment_name": Text(
        "Hydrologic soil groups HSG (from SoilGrids){separator}{tokens}",
        "Grupy hydrologiczne gleb HSG (z SoilGrids){separator}{tokens}",
    ),
    # ``store_documents``.
    "limit_at_least_one": Text(
        "limit must be >= 1, got {limit}",
        "limit musi byc >= 1, podano {limit}",
    ),
    "segment_required": Text(
        "segment is required: <product>/<variant> (got {segment!r}); the segments of "
        "the store: describe_store",
        "segment jest wymagany: <produkt>/<wariant> (otrzymano {segment!r}); segmenty "
        "magazynu: describe_store",
    ),
}
