"""Messages of the availability report (``kartograf.download.availability``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.availability``.
    "country_auto": Text(
        "auto (PL and CZ parts by the rectangular country envelopes in one report)",
        "auto (czesci PL i CZ wg prostokatnych obwiedni krajow w jednym raporcie)",
    ),
    "cz_no_years": Text(
        "CZ (CUZK) does not publish survey years - --year/--min-year/--max-year apply "
        "only to PL (the CZ report gives the file publication date)",
        "CZ (CUZK) nie publikuje lat nalotu - --year/--min-year/--max-year dotycza "
        "tylko PL (raport CZ podaje date publikacji plikow)",
    ),
    "no_land": Text(
        "the area has no PL land (territorial sea or area outside the state boundary) "
        "- there is no land to cover, so every combination is complete (complete: "
        "yes) with no promise of data to download",
        "obszar nie ma ladu PL (morze terytorialne albo obszar poza granica panstwa) "
        "- nie ma ladu do pokrycia, wiec kazda kombinacja jest kompletna (komplet: "
        "tak) bez obietnicy danych do pobrania",
    ),
    "reason_sheet": Text(
        "sheet codes outside the PL-1992/PL-2000 sheet systems",
        "godla spoza ukladow arkuszy PL-1992/PL-2000",
    ),
    "reason_url": Text("no https URL of the file", "bez adresu https pliku"),
    "reason_crs": Text("no CRS", "bez ukladu wspolrzednych"),
    "reason_file": Text(
        "record format inconsistent with the file",
        "format rekordu niezgodny z plikiem",
    ),
    "reason_format": Text(
        "format not in the variant registry",
        "format spoza rejestru wariantow",
    ),
    "reason_registry": Text(
        "variant not in the registry (resolution or vertical CRS)",
        "wariant spoza rejestru (rozdzielczosc albo uklad wysokosci)",
    ),
    "auto_part_failed": Text(
        "--country auto: could not check the {code} part ({failure}) - the report "
        "covers only {countries}",
        "--country auto: nie udalo sie sprawdzic czesci {code} ({failure}) - raport "
        "obejmuje tylko {countries}",
    ),
    "product_required": Text(
        "--product required: {choices}",
        "--product wymagane: {choices}",
    ),
    "product_unknown": Text(
        "--product {product!r}: unknown value - available: {choices}",
        "--product {product!r}: nieznana wartosc - dostepne: {choices}",
    ),
    "country_required_area": Text(
        "--country required with --bbox/--geometry: {country_choices}",
        "--country wymagane z --bbox/--geometry: {country_choices}",
    ),
    "country_unsupported": Text(
        "--country {country!r}: the availability report covers: {country_choices}",
        "--country {country!r}: raport dostepnosci obejmuje: {country_choices}",
    ),
    "sheet_country_mismatch": Text(
        "Sheet code '{sheet}' belongs to system {name} (country {country}), but "
        "--country {country_2} was given",
        "Godlo '{sheet}' nalezy do systemu {name} (kraj {country}), a podano "
        "--country {country_2}",
    ),
    "availability_report": Text("availability report", "raport dostepnosci"),
    "area_no_country": Text(
        "the area does not intersect the extent of any known country (PL, CZ)",
        "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
    ),
    "auto_narrowed_to_pl": Text(
        "--country auto -> pl ({years} applies only to PL)",
        "--country auto -> pl ({years} dotyczy tylko PL)",
    ),
    "layer_no_features": Text(
        "{name}: layer has no features",
        "{name}: warstwa bez obiektow",
    ),
    "index_no_vintage": Text(
        "{flags}: GUGiK sheet index {name} has no vintage {year_range_label} - "
        "available vintages: {available}",
        "{flags}: skorowidz GUGiK {name} nie ma rocznika {year_range_label} - "
        "dostepne roczniki: {available}",
    ),
    "name_file_suffix": Text("{name}, .{suffix} file", "{name}, plik .{suffix}"),
    "unsupported_slot_summary": Text(
        "{shown} {vertical_crs} ({years}; sheets: {slot_sheets_count}) - {reason_text}",
        "{shown} {vertical_crs} ({years}; arkusze: {slot_sheets_count}) - "
        "{reason_text}",
    ),
    "unsupported_records_notice": Text(
        "The GUGiK sheet index also has records for the area that Kartograf does not "
        "download: {parts:join(; )}",
        "Skorowidz GUGiK ma dla obszaru tez rekordy, ktorych Kartograf nie pobiera: "
        "{parts:join(; )}",
    ),
    "cz_have_singular": Text("does not have", "nie ma"),
    "cz_are_singular": Text("is", "jest"),
    "cz_have_plural": Text("do not have", "nie maja"),
    "cz_are_plural": Text("are", "sa"),
    "cz_models_list": Text("{models:join( and )}", "{models:join( i )}"),
    "cz_service_only": Text(
        "{names} {have} CUZK sheet files (the report does not cover them) - {are} "
        "available for the whole of CZ as a cutout (--cutout), as a TM33 tile from "
        "the ImageServer service (--sheet, e.g. 302_5550) and as LAZ (--product laz "
        "--model {models})",
        "{names} {have} plikow arkuszy CUZK (raport ich nie obejmuje) - {are} dla "
        "calego CZ jako wycinek (--cutout), kafel TM33 z uslugi ImageServer (--sheet, "
        "np. 302_5550) i LAZ (--product laz --model {models})",
    ),
}
