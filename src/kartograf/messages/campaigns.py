"""Messages of the PL sheet campaigns (``download.campaigns``, ``manager``)."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.campaigns``.
    "format_zip": Text("ZIP archive", "archiwum ZIP"),
    "year_not_integer": Text(
        "{name} must be an integer 1900..2100, got {year!r}",
        "{name} musi byc liczba calkowita 1900..2100, otrzymano {year!r}",
    ),
    "min_year_exceeds_max": Text(
        "min_year ({min_year}) must not be greater than max_year ({max_year})",
        "min_year ({min_year}) nie moze byc wiekszy niz max_year ({max_year})",
    ),
    "year_label_single": Text("from year {min_year}", "z roku {min_year}"),
    "year_label_range": Text(
        "from years {min_year}-{max_year}", "z lat {min_year}-{max_year}"
    ),
    "year_label_from": Text("from {min_year} onwards", "od roku {min_year}"),
    "year_label_until": Text("up to {max_year}", "do roku {max_year}"),
    "hint_max_year_older": Text(
        "--max-year {upper} (year {upper} and older)",
        "--max-year {upper} (rok {upper} i starsze)",
    ),
    "hint_min_year_newer": Text(
        "--min-year {min_year} (year {min_year} and newer)",
        "--min-year {min_year} (rok {min_year} i nowsze)",
    ),
    "max_year_hint": Text(
        "--max-year {upper} ({year_range})",
        "--max-year {upper} ({year_range})",
    ),
    "hint_min_year_lower": Text(
        "--min-year {lower} (year {lower} and newer)",
        "--min-year {lower} (rok {lower} i nowsze)",
    ),
    "hint_max_year_single": Text(
        "--max-year {max_year} (year {max_year} and older)",
        "--max-year {max_year} (rok {max_year} i starsze)",
    ),
    "min_year_hint": Text(
        "--min-year {lower} ({year_range})",
        "--min-year {lower} ({year_range})",
    ),
    "default_subject": Text("data", "danych"),
    "year_range_no_data": Text(
        "no {subject} {year_range_label} for {sheets_count} of {total} {unit} - "
        "nothing downloaded:",
        "brak {subject} {year_range_label} dla {sheets_count} z {total} {unit} - nic "
        "nie pobrano:",
    ),
    "year_partial_sheets": Text(
        "{year} (incomplete sheets only)",
        "{year} (tylko arkusze niepelne)",
    ),
    "sheet_available_vintages": Text(
        "  {sheet}{label_suffix}: available vintages {year_texts:join}",
        "  {sheet}{label_suffix}: dostepne roczniki {year_texts:join}",
    ),
    "sheets_more_count": Text(
        "  ... and {remaining} more",
        "  ... i {remaining} innych",
    ),
    "year_range_hint": Text(
        "Hint: {hints:join( or )}",
        "Podpowiedz: {hints:join( albo )}",
    ),
    "record_invalid_freshness": Text(
        "Sheet index record has an invalid freshness {date!r} (expected YYYY-MM-DD)",
        "Rekord skorowidza ma niepoprawna aktualnosc {date!r} (oczekiwano RRRR-MM-DD)",
    ),
    "record_vertical_crs_mismatch": Text(
        "{sheet}: sheet index record declares vertical CRS {declared}, but "
        "{vertical_crs} was requested (expected {expected}) - file was not "
        "downloaded: {url}",
        "{sheet}: rekord skorowidza deklaruje uklad wysokosci {declared}, a zadano "
        "{vertical_crs} (oczekiwano {expected}) - plik nie zostal pobrany: {url}",
    ),
    "campaign_format_unsupported": Text(
        "Campaign {dirname}: format {fmt!r} is unsupported (product: {default_ext})",
        "Kampania {dirname}: format {fmt!r} nieobslugiwany (produkt: {default_ext})",
    ),
    "no_format_verification": Text(
        "{name}: no format verification for {ext!r}",
        "{name}: brak weryfikacji formatu dla {ext!r}",
    ),
    "format_verify_read_failed": Text(
        "{name}: read for format verification: {error}",
        "{name}: odczyt do weryfikacji formatu: {error}",
    ),
    "file_format_mismatch": Text(
        "{name}: content is not {format_name} (header: {head_bytes!r})",
        "{name}: tresc nie jest {format_name} (naglowek: {head_bytes!r})",
    ),
    "coverage_measure_failed": Text(
        "{name}: failed to measure coverage: {error}",
        "{name}: nie udalo sie zmierzyc pokrycia: {error}",
    ),
    "asc_cell_count_mismatch": Text(
        "{name}: ASC has {count} cells, expected {expected}",
        "{name}: ASC ma {count} komorek, oczekiwano {expected}",
    ),
    "no_coverage_measurement": Text(
        "{name}: no coverage measurement for {ext!r}",
        "{name}: brak pomiaru pokrycia dla {ext!r}",
    ),
    "url_suffix_mismatch": Text(
        "Sheet index record URL does not end with sheet code {sheet} and suffix "
        "{suffix}: {url}",
        "URL rekordu skorowidza nie konczy sie godlem {sheet} z przyrostkiem "
        "{suffix}: {url}",
    ),
    "url_missing_sheet_code": Text(
        "Sheet index record URL does not contain sheet code {sheet}: {url}",
        "URL rekordu skorowidza nie zawiera godla {sheet}: {url}",
    ),
    "asc_header_incomplete": Text(
        "{name}: incomplete ASC header (missing {error}) - cannot check extent of "
        "sheet {sheet}",
        "{name}: niepelny naglowek ASC (brak {error}) - nie mozna sprawdzic zasiegu "
        "arkusza {sheet}",
    ),
    "sheet_extent_mismatch": Text(
        "{name}: file extent ({x0:.0f}, {y0:.0f}, {x1:.0f}, {y1:.0f}) does not match "
        "the frame of sheet {sheet} ({min_x:.0f}, {min_y:.0f}, {max_x:.0f}, "
        "{max_y:.0f}, {crs})",
        "{name}: zasieg pliku ({x0:.0f}, {y0:.0f}, {x1:.0f}, {y1:.0f}) nie pokrywa "
        "sie z rama godla {sheet} ({min_x:.0f}, {min_y:.0f}, {max_x:.0f}, "
        "{max_y:.0f}, {crs})",
    ),
    # ``download.manager``.
    "year_excludes_bounds": Text(
        "--year excludes --min-year/--max-year (--year Y is shorthand for --min-year "
        "Y --max-year Y)",
        "--year wyklucza sie z --min-year/--max-year (--year Y to skrot --min-year Y "
        "--max-year Y)",
    ),
    "error_item": Text("{name}: {error}", "{name}: {error}"),
    "sheet_problems": Text(
        "{sheet}: {problems:join(; )}", "{sheet}: {problems:join(; )}"
    ),
    "campaign_local": Text("{label} local", "{label} lokalna"),
    "campaign_to_download": Text("{dirname} to download", "{dirname} do pobrania"),
    "no_coverage_text": Text(
        "GUGiK has no data for any of the {total} {total:plural(sheet|sheets)} of the "
        "area",
        "GUGiK nie ma danych dla zadnego z {total} "
        "{total:plural(arkusza|arkuszy|arkuszy)} obszaru",
    ),
    "provider_no_campaigns": Text(
        "Provider {name} does not support campaigns "
        "(--all-campaigns/--min-year/--max-year/--year/--full-sheet)",
        "Provider {name} nie obsluguje kampanii "
        "(--all-campaigns/--min-year/--max-year/--year/--full-sheet)",
    ),
    "range_check_requirements": Text(
        "Range check requires PL campaigns and a year boundary",
        "Sprawdzenie przedzialu wymaga kampanii PL i granicy roku",
    ),
    "year_check_failed": Text(
        "could not check the data year for {failed_count} of {sheets_count} "
        "{sheets_count:plural(sheet|sheets)} (sheet index error, not missing data): "
        "{names} - retry the download",
        "nie udalo sie sprawdzic roku danych dla {failed_count} z {sheets_count} "
        "{sheets_count:plural(arkusza|arkuszy|arkuszy)} (blad skorowidza, nie brak "
        "danych): {names} - ponow pobranie",
    ),
    "link_error": Text("link {link}: {error}", "dowiazanie {link}: {error}"),
    "large_file_notice": Text(
        "{what} PL {sheet}: large file {url} - {size_text}",
        "{what} PL {sheet}: duzy plik {url} - {size_text}",
    ),
    "campaigns_not_downloaded": Text(
        "{errors_count} of {chosen_count} campaigns not downloaded ({listing:join})",
        "nie pobrano {errors_count} z {chosen_count} kampanii ({listing:join})",
    ),
    "index_unavailable_unverified": Text(
        "{sheet}: GUGiK sheet index not available - used local version without "
        "checking for a newer one ({unverified_reason})",
        "{sheet}: skorowidz GUGiK niedostepny - uzyto lokalnej wersji bez sprawdzenia "
        "nowszej ({unverified_reason})",
    ),
    "index_unavailable_many_sheets": Text(
        "GUGiK sheet index not available - used local versions without checking for a "
        "newer one for {sheets_count} {sheets_count:plural(sheet|sheets)} ({shown}) "
        "({unverified_reason})",
        "skorowidz GUGiK niedostepny - dla {sheets_count} "
        "{sheets_count:plural(arkusza|arkuszy|arkuszy)} uzyto lokalnych wersji bez "
        "sprawdzenia nowszej ({shown}) ({unverified_reason})",
    ),
    "newer_campaign_available": Text(
        "newer campaign available for {sheets_count} "
        "{sheets_count:plural(sheet|sheets)} ({shown}) - used local versions; "
        "download with: --upgrade",
        "dostepna nowsza kampania dla {sheets_count} "
        "{sheets_count:plural(arkusza|arkuszy|arkuszy)} ({shown}) - uzyto lokalnych "
        "wersji; pobierz: --upgrade",
    ),
    "campaign_sidecar_failed": Text(
        "Failed to write the mandatory sidecar of campaign {dirname}: {error}",
        "Nie udalo sie zapisac obowiazkowego sidecara kampanii {dirname}: {error}",
    ),
}
