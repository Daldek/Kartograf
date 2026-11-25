"""Messages of ``kartograf gui serve`` (``kartograf.gui``): settings, page, start."""

from kartograf.messages import Text

MESSAGES = {
    # ``kartograf.gui``: the start.
    "empty_host": Text("the address is empty", "adres jest pusty"),
    "browser_failed": Text(
        "the page {url} could not be opened in a web browser ({error}); open it "
        "yourself",
        "nie udało się otworzyć strony {url} w przeglądarce ({error}); otwórz ją "
        "samodzielnie",
    ),
    # ``kartograf.gui.basemaps``: the base maps of the page (Nogat DEV-15.15, DEV-18.1).
    "catalogue_unreadable": Text(
        "the catalogue of base maps {path} cannot be read: {error}",
        "nie można odczytać katalogu podkładów {path}: {error}",
    ),
    "basemaps_invalid": Text(
        "{name} is not a list of the ids of base maps: {value}",
        "{name} to nie lista identyfikatorów podkładów: {value}",
    ),
    "basemap_unknown": Text(
        "{name} names the base map {value}, which the catalogue does not have "
        "(known: {known})",
        "{name} podaje podkład {value}, którego nie ma w katalogu (znane: {known})",
    ),
    "basemap_mirrors_invalid": Text(
        "{name} is not a table of an id of the catalogue and the http or https "
        "address of its copy: {value}",
        "{name} to nie tabela identyfikatora z katalogu i adresu http albo https jego "
        "kopii: {value}",
    ),
    "basemap_extra_invalid": Text(
        "{name}: the field {field} of an own base map is not valid: {value}",
        "{name}: pole {field} własnego podkładu jest nieprawidłowe: {value}",
    ),
    "basemap_extra_missing": Text(
        "{name}: the own base map {value} has no field {field}",
        "{name}: własny podkład {value} nie ma pola {field}",
    ),
    "basemap_hint": Text(
        "Allowed ids: {known}. Own base maps: a list of tables with id, name, kind "
        "(xyz, wms or vector), url, attribution and grayscale.",
        "Dozwolone identyfikatory: {known}. Własne podkłady: lista tabel z polami id, "
        "name, kind (xyz, wms albo vector), url, attribution i grayscale.",
    ),
    # ``kartograf.gui.site``: the other GUIs (Nogat DEV-15.4) and the regulamin.
    "gui_table_invalid": Text(
        "[nogat] gui of nogat.toml is not a table of names and addresses: the app "
        "menu lists no other GUI",
        "[nogat] gui w nogat.toml to nie tabela nazw i adresów: menu aplikacji nie "
        "pokazuje innych GUI",
    ),
    "terms_none": Text(
        "no [nogat.operator] in nogat.toml: the GUI is not public and serves no "
        "regulamin",
        "brak [nogat.operator] w nogat.toml: GUI nie jest publiczne i nie podaje "
        "regulaminu",
    ),
    "terms_failed": Text(
        "the regulamin cannot be filled, the GUI serves none: {error}",
        "nie można wypełnić regulaminu, GUI go nie podaje: {error}",
    ),
    "terms_no_address": Text(
        "[nogat.gui] of nogat.toml has no address of kartograf",
        "[nogat.gui] w nogat.toml nie ma adresu kartograf",
    ),
    "terms_not_table": Text(
        "[nogat.operator] of nogat.toml is not a table",
        "[nogat.operator] w nogat.toml to nie tabela",
    ),
    "terms_no_version": Text(
        "the template names no version of the regulamin",
        "szablon nie podaje wersji regulaminu",
    ),
    "terms_value_missing": Text(
        "no value of {names}",
        "brak wartości {names}",
    ),
    "terms_not_text": Text(
        "{key} of [nogat.operator] is not text",
        "{key} w [nogat.operator] to nie tekst",
    ),
    "terms_not_date": Text(
        "terms_effective of [nogat.operator] is not a date such as 2026-11-20",
        "terms_effective w [nogat.operator] to nie data, np. 2026-11-20",
    ),
    "terms_left": Text(
        "a placeholder {{{{...}}}} is left in the page",
        "w stronie został symbol zastępczy {{{{...}}}}",
    ),
    # ``kartograf.gui.app``: the request limit of a page (Nogat DEV-15.9).
    "rate_limited_title": Text("Too many requests", "Zbyt wiele żądań"),
    "rate_limited_page": Text(
        "Too many requests. Try again in {seconds} s.",
        "Zbyt wiele żądań. Spróbuj ponownie za {seconds} s.",
    ),
}
