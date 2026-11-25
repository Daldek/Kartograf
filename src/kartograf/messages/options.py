"""Messages of the area ``options``."""

from kartograf.messages import Text

MESSAGES = {
    # ``download.options``.
    "expected_min_x_min_y_max": Text(
        "Expected: min_x,min_y,max_x,max_y (e.g. 450000,550000,460000,560000)",
        "Oczekiwano: min_x,min_y,max_x,max_y (np. 450000,550000,460000,560000)",
    ),
    "invalid_bbox_unsupported_crs": Text(
        "Invalid bbox: unsupported CRS {crs!r} - available: {bbox_crs_choices}",
        "Nieprawidłowy bbox: nieobsługiwany układ {crs!r} - dostępne: "
        "{bbox_crs_choices}",
    ),
    "invalid_bbox_bbox_zero_area": Text(
        "Invalid bbox: a bbox with zero area (min == max): {coords}; expected min_x < "
        "max_x and min_y < max_y. {bbox_expected}",
        "Nieprawidłowy bbox: bbox o zerowej powierzchni (min == max): {coords}; "
        "oczekiwano min_x < max_x i min_y < max_y. {bbox_expected}",
    ),
    "invalid_bbox_coordinates_lie_outside": Text(
        "Invalid bbox: coordinates {coords} lie outside the range of EPSG:4326 "
        "(longitude -180..180, latitude -90..90). {bbox_crs_remedy}. {bbox_expected}",
        "Nieprawidłowy bbox: współrzędne {coords} leżą poza zakresem EPSG:4326 "
        "(długość -180..180, szerokość -90..90). {bbox_crs_remedy}. {bbox_expected}",
    ),
    "bbox_crs_remedy_hint": Text("{bbox_crs_remedy}.", "{bbox_crs_remedy}."),
    # ``download.options``.
    "product_nmt": Text(
        "Digital Terrain Model; PL and CZ",
        "Numeryczny Model Terenu; PL i CZ",
    ),
    "product_nmpt": Text(
        "Digital Surface Model; PL and CZ",
        "Numeryczny Model Pokrycia Terenu; PL i CZ",
    ),
    "product_orto": Text("RGB orthophoto; PL and CZ", "ortofotomapa RGB; PL i CZ"),
    "product_laz": Text(
        "LIDAR point cloud; PL and CZ",
        "chmura punktów LIDAR; PL i CZ",
    ),
    "product_contours": Text(
        "ZABAGED contours - 2D vector, SM5 sheets, SHP or DGN; CZ",
        "warstwice ZABAGED - wektor 2D, arkusze SM5, SHP albo DGN; CZ",
    ),
    "product_intensity": Text(
        "LIDAR intensity images, 1 band 0.25 m; PL",
        "obrazy intensywności LIDAR, 1 pasmo 0,25 m; PL",
    ),
    "product_true_orto": Text(
        "true orthophoto (true orto) of selected cities, 0.05 m; PL",
        "prawdziwa ortofotomapa (true orto) wybranych miast, 0,05 m; PL",
    ),
    "product_oblique_orto": Text(
        "oblique orthophoto of selected cities, sheet = 4 files for directions n, e, "
        "s, w; PL",
        "ortofotomapa ukośna wybranych miast, arkusz = 4 pliki kierunków n, e, s, w; "
        "PL",
    ),
    "product_required": Text(
        "--product required: {product_choices}",
        "--product wymagane: {product_choices}",
    ),
    "product_unknown": Text(
        "--product {product!r}: unknown value - available: {product_choices}",
        "--product {product!r}: nieznana wartość - dostępne: {product_choices}",
    ),
    "country_auto": Text(
        "auto (countries by rectangular PL and CZ envelopes; an area in both "
        "countries gives separate files per country)",
        "auto (kraje wg prostokątnych obwiedni PL i CZ; obszar w obu krajach daje "
        "osobne pliki per kraj)",
    ),
    "vertical_crs_evrf2007": Text(
        "PL-EVRF2007-NH, current system",
        "PL-EVRF2007-NH, układ obowiązujący",
    ),
    "vertical_crs_kron86": Text(
        "PL-KRON86-NH, historical system",
        "PL-KRON86-NH, układ historyczny",
    ),
    "or_list": Text(
        "{leading_values} or {last_value}",
        "{leading_values} albo {last_value}",
    ),
    "cz_resolution_help": Text(
        "{parts:join(; )}; SM5 sheet only {sm5:join} (can be omitted)",
        "{parts:join(; )}; arkusz SM5 tylko {sm5:join} (można pominąć)",
    ),
    "choices": Text("{items:join}", "{items:join}"),
    "choice_item": Text("{name} ({summary})", "{name} ({summary})"),
    "product_labels": Text("{product}: {labels}", "{product}: {labels}"),
    "sheet_system_choices": Text(
        "1992 (PL-1992 sheet codes, 1:10000 sheets), 2000 (PL-2000 sheet codes, "
        "EPSG:2176-2179 zones; requires --scale)",
        "1992 (godła PL-1992, arkusze 1:10000), 2000 (godła PL-2000, strefy "
        "EPSG:2176-2179; wymaga --scale)",
    ),
    "scale_2000_choices": Text(
        "1:5000, 1:2000, 1:1000, 1:500 (GUGiK publishes PL-2000 sheets most often at "
        "1:2000, also at 1:1000 and 1:5000)",
        "1:5000, 1:2000, 1:1000, 1:500 (GUGiK publikuje arkusze PL-2000 najczęściej w "
        "1:2000, także w 1:1000 i 1:5000)",
    ),
    "invalid_per_country_value": Text(
        "{flag}: invalid value {shown!r} - give one value for each country of the "
        "task or comma-separated country=value pairs (countries: pl, cz), e.g. {flag} "
        "pl=...,cz=...",
        "{flag}: nieprawidłowa wartość {shown!r} - podaj jedną wartość dla każdego "
        "kraju zadania albo pary kraj=wartość rozdzielone przecinkami (kraje: pl, "
        "cz), np. {flag} pl=...,cz=...",
    ),
    "per_country_hint": Text(
        " (PL+CZ task: per-country values, e.g. {flag} pl=...,cz=...)",
        " (zadanie PL+CZ: wartości per kraj, np. {flag} pl=...,cz=...)",
    ),
    "error_with_suffix": Text("{error}{suffix}", "{error}{suffix}"),
    "file_variant_reason": Text(
        "{shown} consists of voivodeship files from ATOM - no sheets, flights or "
        "cutout",
        "{shown} to pliki województw z ATOM - bez arkuszy, lotów i wycinka",
    ),
    "flag_not_for_resolution": Text(
        "{flag} does not apply to --resolution {label}: {reason}",
        "{flag} nie dotyczy --resolution {label}: {reason}",
    ),
    "country_cz_not_for_resolution": Text(
        "--country cz does not apply to --resolution {label} (PL only): {reason}",
        "--country cz nie dotyczy --resolution {label} (tylko PL): {reason}",
    ),
    "vcrs_not_for_resolution": Text(
        "--vertical-crs does not apply to --resolution {label}: {unknown_vertical} - "
        "GUGiK does not declare a vertical CRS for {shown}; omit --vertical-crs",
        "--vertical-crs nie dotyczy --resolution {label}: {unknown_vertical} - GUGiK "
        "nie deklaruje układu wysokości {shown}; pomiń --vertical-crs",
    ),
    "resolution_not_for_laz": Text(
        "--resolution does not apply to LAZ - a point cloud has no grid; omit "
        "--resolution",
        "--resolution nie dotyczy LAZ - chmura punktów nie ma siatki; pomiń "
        "--resolution",
    ),
    "cutout_needs_asc_grid": Text(
        "--cutout works only with the ASC 1m grid (a cutout from GUGiK WCS); --format "
        "{fmt} means source sheet files - omit --cutout",
        "--cutout działa tylko z siatką ASC 1m (wycinek z WCS GUGiK); --format {fmt} "
        "to pliki źródłowe arkuszy - pomiń --cutout",
    ),
    "cutout_only_1m": Text(
        "PL cutouts (--cutout) are 1 m only (GUGiK WCS); {resolution} sheets: omit "
        "--cutout (sheets without --cutout); cutout: --resolution 1m or omit "
        "--resolution",
        "wycinki PL (--cutout) są tylko 1 m (WCS GUGiK); arkusze {resolution}: pomiń "
        "--cutout (arkusze bez --cutout); wycinek: --resolution 1m albo pomiń "
        "--resolution",
    ),
    "format_product_mismatch": Text(
        "--format applies only to --product nmt and nmpt (PL) and {contours} (CZ), "
        "got --product {product} - omit --format",
        "--format dotyczy tylko --product nmt i nmpt (PL) oraz {contours} (CZ), "
        "podano --product {product} - pomiń --format",
    ),
    "noun_orthophoto": Text("an orthophoto", "ortofotomapa"),
    "noun_image": Text("an image", "obraz"),
    "vcrs_not_for_product": Text(
        "--vertical-crs does not apply to --product {product} ({noun} has no vertical "
        "CRS)",
        "--vertical-crs nie dotyczy --product {product} ({noun} nie ma układu "
        "pionowego)",
    ),
    "vcrs_required_pl": Text(
        "--vertical-crs required for --product {product} (PL): "
        "{vertical_crs_text}{vcrs_hint}",
        "--vertical-crs wymagane dla --product {product} (PL): "
        "{vertical_crs_text}{vcrs_hint}",
    ),
    "vcrs_not_pl": Text(
        "{vertical_crs} is not a PL vertical CRS - available: "
        "{vertical_crs_text}{vcrs_hint}",
        "{vertical_crs} nie jest układem wysokości PL - dostępne: "
        "{vertical_crs_text}{vcrs_hint}",
    ),
    "verb_plural": Text("do not apply", "nie dotyczą"),
    "verb_singular": Text("does not apply", "nie dotyczy"),
    "laz_crs_flags": Text(
        "{flags:join( and )} {verb} to LAZ PL - the CRS of each tile comes from GUGiK "
        "WFS; omit {flags:join( and )}",
        "{flags:join( i )} {verb} LAZ PL - układ każdego kafla pochodzi z WFS GUGiK; "
        "pomiń {flags:join( i )}",
    ),
    "cutout_sheet_system_2000": Text(
        "--cutout does not work with --sheet-system 2000 - a multi-zone bbox would "
        "give sheets in different CRS (2176-2179); cutout: --sheet-system 1992 or "
        "omit --sheet-system",
        "--cutout nie działa z --sheet-system 2000 - bbox wielostrefowy dałby arkusze "
        "w różnych CRS (2176-2179); wycinek: --sheet-system 1992 albo pomiń "
        "--sheet-system",
    ),
    "scale_not_for_format": Text(
        "--scale does not apply to --format {fmt}: archive sheets (various scales) "
        "come from the GUGiK sheet index - omit --scale",
        "--scale nie dotyczy --format {fmt}: arkusze archiwum (różne skale) wynikają "
        "ze skorowidza GUGiK - pomiń --scale",
    ),
    "cutout_hint": Text(
        "; one cutout instead of sheets: --cutout",
        "; jeden wycinek zamiast arkuszy: --cutout",
    ),
    "sheet_system_required_pl": Text(
        "--sheet-system is required for --bbox/--geometry in PL: "
        "{sheet_system_choices}{cutout_hint}",
        "--sheet-system wymagane dla --bbox/--geometry w PL: "
        "{sheet_system_choices}{cutout_hint}",
    ),
    "sheet_system_not_for_product": Text(
        "--sheet-system {sheet_system} does not apply to --product {product}: GUGiK "
        "publishes sheets only {only} - omit --sheet-system",
        "--sheet-system {sheet_system} nie dotyczy --product {product}: GUGiK "
        "publikuje arkusze tylko {only} - pomiń --sheet-system",
    ),
    "product_sheet_system_mismatch": Text(
        "--product {product}: GUGiK publishes sheets only {only} - sheet code {sheet} "
        "is PL-{code_system}",
        "--product {product}: GUGiK publikuje arkusze tylko {only} - godło {sheet} to "
        "PL-{code_system}",
    ),
    "sheet_system_code_mismatch": Text(
        "--sheet-system {sheet_system} does not match sheet code {sheet} "
        "(PL-{code_system}): the sheet system follows from the sheet code - omit "
        "--sheet-system",
        "--sheet-system {sheet_system} nie zgadza się z godłem {sheet} "
        "(PL-{code_system}): układ arkuszy wynika z godła - pomiń --sheet-system",
    ),
    "scale_not_for_pl1992": Text(
        "--scale does not apply to PL-1992: GUGiK publishes PL-1992 sheets only at "
        "{label} ({parts}-part sheet code), and a coarser sheet code expands to "
        "{label} by itself - omit --scale",
        "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 tylko w {label} "
        "(godło {parts}-członowe), a grubsze godło rozwija się do {label} samo - "
        "pomiń --scale",
    ),
    "scale_required_pl2000": Text(
        "--scale is required for PL-2000 sheets: {scale_2000_choices}",
        "--scale wymagane dla arkuszy PL-2000: {scale_2000_choices}",
    ),
    "unknown_pl2000_scale": Text(
        "Unknown PL-2000 scale {scale} - available: {scale_2000_choices}",
        "Nieznana skala PL-2000 {scale} - dostępne: {scale_2000_choices}",
    ),
    "format_only_cz_contours": Text(
        "--format applies in CZ only to --product {contours} (contours); {product} CZ "
        "comes as CUZK files with no format choice - omit --format",
        "--format dotyczy w CZ tylko --product {contours} (warstwice); {product} CZ "
        "to pliki CUZK bez wyboru formatu - pomiń --format",
    ),
    "resolution_not_for_cz_laz": Text(
        "--resolution does not apply to LAZ CZ - omit --resolution",
        "--resolution nie dotyczy LAZ CZ - pomiń --resolution",
    ),
    "min_density_only_pl_laz": Text(
        "--min-density applies only to LAZ PL - omit --min-density",
        "--min-density dotyczy tylko LAZ PL - pomiń --min-density",
    ),
    "sheet_system_only_pl": Text(
        "--sheet-system applies only to PL (CZ sheet codes are detected by pattern)",
        "--sheet-system dotyczy tylko PL (godła CZ wykrywane wzorcem)",
    ),
    "vcrs_required_cz_laz": Text(
        "--vertical-crs is required for LAZ CZ: {cz_laz_vertical_text}{vcrs_hint}",
        "--vertical-crs wymagane dla LAZ CZ: {cz_laz_vertical_text}{vcrs_hint}",
    ),
    "vcrs_required_cz": Text(
        "--vertical-crs is required for {product} CZ: {cz_vertical_text}{vcrs_hint}",
        "--vertical-crs wymagane dla {product} CZ: {cz_vertical_text}{vcrs_hint}",
    ),
    "contours_reason": Text(
        "contours are SM5 sheets (vector) - no resolution, flights or cutout",
        "warstwice to arkusze SM5 (wektor) - bez rozdzielczości, lotów i wycinka",
    ),
    "flag_not_for_contours": Text(
        "{flag} does not apply to --product {contours}: {reason}",
        "{flag} nie dotyczy --product {contours}: {reason}",
    ),
    "contours_format_required": Text(
        "--format required for --product {contours}: {formats}",
        "--format wymagane dla --product {contours}: {formats}",
    ),
    "contours_format_unknown": Text(
        "--format {fmt!r}: unknown value for --product {contours} - available: "
        "{formats}",
        "--format {fmt!r}: nieznana wartość dla --product {contours} - dostępne: "
        "{formats}",
    ),
    "contours_vertical_crs": Text(
        "--vertical-crs {vertical_crs} does not apply to --product {contours}: "
        "ZABAGED contours have heights {heights} (--vertical-crs can be omitted)",
        "--vertical-crs {vertical_crs} nie dotyczy --product {contours}: warstwice "
        "ZABAGED mają wysokości {heights} (można pominąć --vertical-crs)",
    ),
    "cz_orto_flag_pl_only": Text(
        "{flag} applies to PL only - CUZK publishes only the current vintage of a CZ "
        "orthophoto sheet (archive CUZK orthophotos are paid, out of scope)",
        "{flag} dotyczy tylko PL - CUZK publikuje tylko aktualny rocznik arkusza "
        "ortofoto CZ (archiwalne ortofoto CUZK są płatne, poza zakresem)",
    ),
    "cz_orto_sheet_system": Text(
        "--sheet-system applies to PL only - CZ orthophoto consists of SM5 sheets "
        "(sheet code recognised by pattern, sheets of the area from the SM5 index)",
        "--sheet-system dotyczy tylko PL - ortofoto CZ to arkusze SM5 (godło "
        "rozpoznawane wzorcem, arkusze obszaru z indeksu SM5)",
    ),
    "cz_orto_scale": Text(
        "--scale applies to PL only - CZ orthophoto consists of SM5 sheets at a "
        "single scale (1:5000)",
        "--scale dotyczy tylko PL - ortofoto CZ to arkusze SM5 w jednej skali (1:5000)",
    ),
    "orto_vertical_crs": Text(
        "--vertical-crs does not apply to --product orto (orthophoto has no vertical "
        "CRS)",
        "--vertical-crs nie dotyczy --product orto (ortofotomapa nie ma układu "
        "pionowego)",
    ),
    "cz_orto_format": Text(
        "--format does not apply to CZ orthophoto (CUZK files: JPEG and JGW without "
        "conversion) - omit --format",
        "--format nie dotyczy ortofoto CZ (pliki CUZK: JPEG i JGW bez konwersji) - "
        "pomiń --format",
    ),
    "cz_cutout_required_mixed": Text(
        "the area extends into CZ, and CUZK provides only a single cutout for an area "
        "- add --cutout --horizontal-crs <crs> (the PL part will also be a cutout "
        "from the GUGiK WCS) or use --country pl (PL sheets only)",
        "obszar sięga CZ, a CUZK daje dla obszaru tylko jeden wycinek - dodaj "
        "--cutout --horizontal-crs <układ> (część PL też będzie wycinkiem z WCS "
        "GUGiK) albo użyj --country pl (tylko arkusze PL)",
    ),
    "cz_cutout_required": Text(
        "a CZ (CUZK) area is downloaded only as a single cutout - add --cutout "
        "--horizontal-crs <crs> (e.g. EPSG:5514, the native CUZK CRS)",
        "obszar CZ (CUZK) jest pobierany tylko jako jeden wycinek - dodaj --cutout "
        "--horizontal-crs <układ> (np. EPSG:5514, układ natywny CUZK)",
    ),
    "geometry_zero_area": Text(
        "--geometry: the envelope of the features has zero area (a point or a line "
        "parallel to an axis), {coords} in {crs}; {what} requires an area - provide a "
        "polygon or a --bbox with positive area",
        "--geometry: obwiednia obiektów ma zerową powierzchnię (punkt albo linia "
        "równoległa do osi), {coords} w {crs}; {what} wymaga obszaru - podaj wielobok "
        "albo --bbox o dodatniej powierzchni",
    ),
    "area_choice_exactly_one": Text(
        "Provide exactly one area choice: --sheet, --bbox or --geometry",
        "Podaj dokładnie jeden wybór obszaru: --sheet, --bbox albo --geometry",
    ),
    "area_choice_missing": Text(
        "Provide an area choice: --sheet, --bbox or --geometry",
        "Podaj wybór obszaru: --sheet, --bbox albo --geometry",
    ),
    "layer_hint_layers": Text(
        "; BDOT10k and BDOO data layers are selected with --layers",
        "; warstwy danych BDOT10k i BDOO wybiera --layers",
    ),
    "layer_requires_geometry": Text(
        "--layer applies only to --geometry (a layer of the GPKG area file){hint}",
        "--layer dotyczy tylko --geometry (warstwa pliku GPKG z obszarem){hint}",
    ),
    "store_files_location": Text(
        "files in <DIR>/{tops}/...",
        "pliki w <KATALOG>/{tops}/...",
    ),
    "country_required_area": Text(
        "--country required with --bbox/--geometry: {country_choices}",
        "--country wymagane z --bbox/--geometry: {country_choices}",
    ),
    "country_unknown": Text(
        "--country {country!r}: unknown value - available: {country_choices}",
        "--country {country!r}: nieznana wartość - dostępne: {country_choices}",
    ),
    "sheet_system_unknown": Text(
        "--sheet-system {sheet_system!r}: unknown value - available: "
        "{sheet_system_choices}",
        "--sheet-system {sheet_system!r}: nieznana wartość - dostępne: "
        "{sheet_system_choices}",
    ),
    "horizontal_crs_unknown": Text(
        "--horizontal-crs {horizontal_crs!r}: unknown value - available: {cutout_crs}",
        "--horizontal-crs {horizontal_crs!r}: nieznana wartość - dostępne: "
        "{cutout_crs}",
    ),
    "model_only_laz_cz": Text(
        "--model applies only to --product laz in CZ",
        "--model dotyczy tylko --product laz w CZ",
    ),
    "model_only_laz_cz_pl": Text(
        "--model applies only to --product laz in CZ - omit --model for PL",
        "--model dotyczy tylko --product laz w CZ - pomiń --model dla PL",
    ),
    "min_density_only_laz": Text(
        "--min-density works only with --product laz (got {product}); omit "
        "--min-density",
        "--min-density działa tylko z --product laz (podano {product}); pomiń "
        "--min-density",
    ),
    "full_sheet_not_laz": Text(
        "--full-sheet works only with NMT/NMPT and images (got laz) - LAZ has no "
        "standard path or full_sheet/ link; omit --full-sheet",
        "--full-sheet działa tylko z NMT/NMPT i obrazami (podano laz) - LAZ nie ma "
        "ścieżki standardowej ani dowiązania full_sheet/; pomiń --full-sheet",
    ),
    "full_sheet_not_declared": Text(
        "--full-sheet does not apply to --product {product}: GUGiK sheet index "
        "records do not declare a full sheet (no calyArkuszWypelnionyTrescia) - omit "
        "--full-sheet",
        "--full-sheet nie dotyczy --product {product}: rekordy skorowidza GUGiK nie "
        "deklarują pełnego arkusza (bez calyArkuszWypelnionyTrescia) - pomiń "
        "--full-sheet",
    ),
    "cutout_needs_bbox": Text(
        "--cutout works only with --bbox/--geometry; --sheet determines the extent "
        "and CRS of the product (PL 1:1 sheet in the sheet CRS, SM5 1:1 sheet in "
        "EPSG:5514, TM33 tile on the EPSG:3045 grid)",
        "--cutout działa tylko z --bbox/--geometry; --sheet wyznacza zasięg i układ "
        "produktu (arkusz PL 1:1 w układzie arkusza, arkusz SM5 1:1 w EPSG:5514, "
        "kafel TM33 na siatce EPSG:3045)",
    ),
    "cutout_product_unsupported": Text(
        "--cutout works only with --product {or_list} (cutout from GUGiK WCS); "
        "{product} - download without --cutout",
        "--cutout działa tylko z --product {or_list} (wycinek z WCS GUGiK); {product} "
        "- pobierz bez --cutout",
    ),
    "horizontal_crs_required": Text(
        "--horizontal-crs is required with --cutout (cutout CRS): {cutout_crs}",
        "--horizontal-crs wymagane z --cutout (układ wycinka): {cutout_crs}",
    ),
    "horizontal_crs_needs_cutout": Text(
        "--horizontal-crs works only with --cutout (CRS of a single cutout); sheets "
        "take their CRS from the sheet code - add --cutout or omit --horizontal-crs",
        "--horizontal-crs działa tylko z --cutout (układ jednego wycinka); arkusze "
        "mają układ z godła - dodaj --cutout albo pomiń --horizontal-crs",
    ),
    "coverage_only_orto_cutout": Text(
        "--coverage works only with --cutout --product orto (WCS variant of an "
        "orthophoto cutout: {coverage_choices}) - omit --coverage",
        "--coverage działa tylko z --cutout --product orto (wariant WCS wycinka "
        "ortofotomapy: {coverage_choices}) - pomiń --coverage",
    ),
    "resolution_orto_cutout_only": Text(
        "--resolution with --product orto applies only to a cutout (--cutout); "
        "orthophoto sheets have the source pixel size (PL: of the campaign, CZ: of "
        "the SM5 sheet in the JGW file) - omit --resolution",
        "--resolution z --product orto dotyczy tylko wycinka (--cutout); arkusze "
        "ortofotomapy mają piksel źródła (PL: kampanii, CZ: arkusza SM5 w pliku JGW) "
        "- pomiń --resolution",
    ),
    "where_cutout_only": Text(
        "applies only to a cutout (--cutout)",
        "dotyczy tylko wycinka (--cutout)",
    ),
    "resolution_not_applicable": Text(
        "--resolution with --product {product} {where}; sheets have the source pixel "
        "size (of the GUGiK sheet index record) - omit --resolution",
        "--resolution z --product {product} {where}; arkusze mają piksel źródła "
        "(rekordu skorowidza GUGiK) - pomiń --resolution",
    ),
    "direction_product_unsupported": Text(
        "--direction applies only to --product {or_list} (oblique orthophoto view "
        "directions) - omit --direction",
        "--direction dotyczy tylko --product {or_list} (kierunki widoku orto ukośnej) "
        "- pomiń --direction",
    ),
    "direction_give_list": Text(
        "--direction {direction!r}: give a direction or a list of directions: {codes}",
        "--direction {direction!r}: podaj kierunek albo listę kierunków: {codes}",
    ),
    "direction_unknown_value": Text(
        "--direction {value!r}: unknown value - available: {codes} (north, east, "
        "south, west)",
        "--direction {value!r}: nieznana wartość - dostępne: {codes} (północ, wschód, "
        "południe, zachód)",
    ),
    "campaign_opt_with_cutout": Text(
        "{flag} does not work with --cutout - a cutout from GUGiK WCS uses the "
        "server's flight composition (no year selection); for the data year, download "
        "sheets without --cutout",
        "{flag} nie działa z --cutout - wycinek z WCS GUGiK ma kompozycję lotów "
        "serwera (bez wyboru roku); rok danych: pobierz arkusze bez --cutout",
    ),
    "all_campaigns_with_cutout": Text(
        "--all-campaigns does not work with --cutout - a cutout from GUGiK WCS uses a "
        "single server flight composition; for all campaigns, download sheets without "
        "--cutout",
        "--all-campaigns nie działa z --cutout - wycinek z WCS GUGiK ma jedną "
        "kompozycję lotów serwera; wszystkie kampanie: pobierz arkusze bez --cutout",
    ),
    "full_sheet_with_cutout": Text(
        "--full-sheet does not work with --cutout - the cutout comes from the GUGiK "
        "WCS, not from sheets",
        "--full-sheet nie działa z --cutout - wycinek pochodzi z WCS GUGiK, nie z "
        "arkuszy",
    ),
}
