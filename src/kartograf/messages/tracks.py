"""Messages of the file tracks (PL and CZ LAZ, CZ sheets, orthophoto and contours)."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.cz_contours``.
    "cz_contours_sheets": Text(
        "CZ contours are SM5 sheets (e.g. CTES96, AS91); TM33 tiles exist only for "
        "NMT and NMPT",
        "warstwice CZ to arkusze SM5 (np. CTES96, AS91); kafle TM33 sa tylko dla NMT "
        "i NMPT",
    ),
    "unknown_contours_format": Text(
        "--format {fmt!r}: unknown value for --product {product} - available: "
        "{contours_formats}",
        "--format {fmt!r}: nieznana wartosc dla --product {product} - dostepne: "
        "{contours_formats}",
    ),
    "tm33_not_for_contours": Text(
        "{cz_contours_sheets} (got {code})",
        "{cz_contours_sheets} (podano {code})",
    ),
    "not_sm5_contours_sheet": Text(
        "Sheet code '{code}' is not a CZ contours SM5 sheet (2 or 4 capital letters + "
        "2 digits, e.g. CTES96, AS91)",
        "Godlo '{code}' nie jest arkuszem SM5 warstwic CZ (2 albo 4 wielkie litery + "
        "2 cyfry, np. CTES96, AS91)",
    ),
    "bad_zip_package": Text(
        "{url}: corrupt or non-ZIP package: {error}",
        "{url}: uszkodzona albo nie-ZIP paczka: {error}",
    ),
    "corrupt_zip_member": Text(
        "{url}: corrupt file {broken} in ZIP package",
        "{url}: uszkodzony plik {broken} w paczce ZIP",
    ),
    "zip_missing_suffix_file": Text(
        "{url}: package without a {suffix} file ({names_count} "
        "{names_count:plural(file|files)}) - this is not the expected data",
        "{url}: paczka bez pliku {suffix} ({names_count} "
        "{names_count:plural(plik|pliki|plikow)}) - to nie sa oczekiwane dane",
    ),
    "sidecar_missing_extra": Text(
        "Sidecar {sheet} without extra.mapname/cz_share (index error): {error}",
        "Sidecar {sheet} bez extra.mapname/cz_share (blad indeksu): {error}",
    ),
    "cuzk_no_contours_file": Text(
        "{error} - CUZK has no contours file for sheet {sheet} (verify the sheet code "
        "in the KladyMapovychListu index)",
        "{error} - CUZK nie ma pliku warstwic arkusza {sheet} (zweryfikuj godlo w "
        "indeksie KladyMapovychListu)",
    ),
    "contours_check_failed": Text(
        "Could not check CZ contours sheet {sheet}: {error}",
        "Nie udalo sie sprawdzic arkusza warstwic CZ {sheet}: {error}",
    ),
    # ``download.cz_laz``.
    "no_laz_sheets": Text(
        "No CZ LAZ sheets for the area (KladyMapovychListu index: SM5 sheets for Bpv, "
        "TM33 tiles for EVRF2007) - check the area and --vertical-crs",
        "Brak arkuszy LAZ CZ dla obszaru (indeks KladyMapovychListu: arkusze SM5 dla "
        "Bpv, kafle TM33 dla EVRF2007) - sprawdz obszar i --vertical-crs",
    ),
    "sheet_or_bbox_required": Text(
        "CZ LAZ: give exactly one of sheet (sheet code) or bbox (area)",
        "LAZ CZ: podaj dokladnie jedno z sheet (godlo) albo bbox (obszar)",
    ),
    "sidecar_no_cz_share": Text(
        "Sidecar {sheet} without extra.cz_share (PODIL; index error): {error}",
        "Sidecar {sheet} bez extra.cz_share (PODIL; blad indeksu): {error}",
    ),
    # ``download.cz_orto``.
    "cz_orto_sheets_hint": Text(
        "CZ orthophoto has SM5 sheets (e.g. CTES96, AS91); TM33 tiles exist only for "
        "NMT",
        "ortofoto CZ ma arkusze SM5 (np. CTES96, AS91); kafle TM33 sa tylko dla NMT",
    ),
    "cz_orto_tm33_given": Text(
        "{cz_orto_sheets} (given: {code})",
        "{cz_orto_sheets} (podano {code})",
    ),
    "cz_orto_bad_sheet_code": Text(
        "Sheet code '{code}' is not an SM5 sheet of CZ orthophoto (2 or 4 capital "
        "letters + 2 digits, e.g. CTES96, AS91)",
        "Godlo '{code}' nie jest arkuszem SM5 ortofoto CZ (2 albo 4 wielkie litery + "
        "2 cyfry, np. CTES96, AS91)",
    ),
    "cz_orto_check_failed": Text(
        "Could not check CZ orthophoto sheet {sheet}: {error}",
        "Nie udalo sie sprawdzic arkusza ortofoto CZ {sheet}: {error}",
    ),
    # ``download.cz_sheets``.
    "cz_sheet_check_failed": Text(
        "Could not check CZ sheet {sheet}: {error}",
        "Nie udalo sie sprawdzic arkusza CZ {sheet}: {error}",
    ),
    "unverified_local_version": Text(
        "{sheet}: local version {label} has no HTTP signal from the CUZK file (e.g. a "
        "tile cut from ImageServer by an earlier Kartograf version) - unverified; "
        "CUZK file: --force",
        "{sheet}: lokalna wersja {label} bez sygnalu HTTP pliku CUZK (np. kafel "
        "wyciety z ImageServer przez wczesniejsza wersje Kartografa) - niesprawdzona; "
        "plik CUZK: --force",
    ),
    # ``download.laz``.
    "no_laz_tiles": Text(
        "No LAZ tiles for the given area (check the area, --year, --min-year, "
        "--max-year and --vertical-crs; all WFS vintages responded)",
        "Brak kafli LAZ dla podanego obszaru (sprawdz obszar, --year, --min-year, "
        "--max-year i --vertical-crs; wszystkie roczniki WFS odpowiedzialy)",
    ),
    "best_density": Text(
        "highest nominal density {max_densities} pts/m2",
        "najwyzsza gestosc nominalna {max_densities} pkt/m2",
    ),
    "no_nominal_density": Text(
        "tiles do not give a nominal density",
        "kafle nie podaja gestosci nominalnej",
    ),
    "no_tiles_min_density": Text(
        "No LAZ tiles for the given area: --min-density {min_density} rejected "
        "{below_density_count} {below_density_count:plural(tile|tiles)} of the area "
        "({best}) - lower or omit --min-density",
        "Brak kafli LAZ dla podanego obszaru: --min-density {min_density} odrzucilo "
        "{below_density_count} {below_density_count:plural(kafel|kafle|kafli)} "
        "obszaru ({best}) - obniz albo pomin --min-density",
    ),
    "laz_area_exactly_one": Text(
        "LAZ PL: give exactly one of sheet (sheet code) or bbox (area)",
        "LAZ PL: podaj dokladnie jedno z sheet (godlo) albo bbox (obszar)",
    ),
    "vertical_crs_mismatch": Text(
        "vertical_crs={vertical_crs} does not match the provider "
        "({provider_vertical_crs})",
        "vertical_crs={vertical_crs} niezgodny z providerem ({provider_vertical_crs})",
    ),
    "laz_tiles_superseded": Text(
        "skipped {covered_count} LAZ {covered_count:plural(tile|tiles)} - the area is "
        "covered by newer tiles (by default the newest vintage per area; another "
        "vintage: --year/--min-year/--max-year)",
        "pominieto {covered_count} {covered_count:plural(kafel|kafle|kafli)} LAZ - "
        "obszar pokrywaja nowsze kafle (domyslnie najnowszy rocznik per obszar; inny "
        "rocznik: --year/--min-year/--max-year)",
    ),
    "tile_covered_by": Text(
        "  {tile_label}: covered by {covering}",
        "  {tile_label}: pokryty przez {covering}",
    ),
}
