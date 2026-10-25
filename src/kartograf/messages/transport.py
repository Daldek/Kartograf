"""Messages of the transport engines: HTTP, ATOM, features, packages, mosaics."""

from kartograf.messages import Text

MESSAGES = {
    # ``transport.aaigrid``.
    "not_multipart": Text(
        "WCS: response is not multipart (Content-Type: {content_type!r})",
        "WCS: odpowiedz nie jest multipart (Content-Type: {content_type!r})",
    ),
    "multipart_truncated": Text(
        "WCS: multipart response truncated in part {asc_media_type} ({name})",
        "WCS: odpowiedz multipart urwana w czesci {asc_media_type} ({name})",
    ),
    "asc_part_missing": Text(
        "WCS: no {asc_media_type} part in multipart response; start of body: {head!r}",
        "WCS: brak czesci {asc_media_type} w odpowiedzi multipart; poczatek tresci: "
        "{head!r}",
    ),
    "asc_size_mismatch": Text(
        "WCS: ASC has ncols x nrows {width} x {height}, expected {expect_width} x "
        "{expect_height}",
        "WCS: ASC ma ncols x nrows {width} x {height}, oczekiwano {expect_width} x "
        "{expect_height}",
    ),
    "asc_cellsize_mismatch": Text(
        "WCS: ASC has cellsize {cell_width} x {cell_height}, expected {step_x} x "
        "{step_y}",
        "WCS: ASC ma cellsize {cell_width} x {cell_height}, oczekiwano {step_x} x "
        "{step_y}",
    ),
    "asc_corner_mismatch": Text(
        "WCS: ASC has xllcorner/yllcorner {xll}/{yll}, expected {min_x}/{min_y}",
        "WCS: ASC ma xllcorner/yllcorner {xll}/{yll}, oczekiwano {min_x}/{min_y}",
    ),
    "asc_unreadable": Text(
        "WCS: unreadable ASC file {name}: {error}",
        "WCS: nieczytelny plik ASC {name}: {error}",
    ),
    # ``transport.atom``.
    "crs_single_file": Text(
        "--horizontal-crs {crs}: the dataset has a single file (CRS is determined by "
        "the source)",
        "--horizontal-crs {crs}: zbior ma jeden plik (uklad wynika ze zrodla)",
    ),
    "crs_required_multi": Text(
        "--horizontal-crs required (file published in several CRSs): {crs}",
        "--horizontal-crs wymagane (plik publikowany w kilku ukladach): {crs}",
    ),
    "crs_not_published": Text(
        "--horizontal-crs {crs}: the dataset is not published in this CRS; available: "
        "{available_crs}",
        "--horizontal-crs {crs}: zbior nie jest publikowany w tym ukladzie; dostepne: "
        "{available_crs}",
    ),
    "atom_alternate_links": Text(
        "{context}: entry {entry_id!r} has {links_count} rel=alternate links, "
        "expected one",
        "{context}: wpis {entry_id!r} ma {links_count} linkow rel=alternate, "
        "oczekiwano jednego",
    ),
    "atom_entry_no_updated": Text(
        "{context}: entry {entry_id!r} has no <updated> date ({updated!r})",
        "{context}: wpis {entry_id!r} bez daty <updated> ({updated!r})",
    ),
    "response_not_atom_feed": Text(
        "{context}: response is not an ATOM feed ({content_type}): {detail}",
        "{context}: odpowiedz nie jest feedem ATOM ({content_type}): {detail}",
    ),
    "no_content_type": Text("no content type", "brak typu"),
    "atom_duplicate_dataset": Text(
        "{context}: two datasets for {key_value} ({dataset_feed}, {ident})",
        "{context}: dwa zbiory dla {key_value} ({dataset_feed}, {ident})",
    ),
    "atom_only_dataset": Text("the only dataset", "jedynego zbioru"),
    "atom_no_matching_dataset": Text(
        "{context}: feed has no datasets matching {entry_pattern!r}",
        "{context}: feed nie ma zbiorow pasujacych do {entry_pattern!r}",
    ),
    "atom_expected_one_dataset": Text(
        "{context}: expected one dataset, found {entries_count}",
        "{context}: oczekiwano jednego zbioru, jest {entries_count}",
    ),
    "atom_unexpected_304": Text(
        "{context}: HTTP 304 without a conditional request",
        "{context}: HTTP 304 bez zapytania warunkowego",
    ),
    "atom_no_file_in_crs": Text(
        "{context}: no file in CRS {crs} (feed: {published})",
        "{context}: brak pliku w ukladzie {crs} (feed: {published})",
    ),
    "atom_no_crs_category": Text("no CRS category", "bez kategorii ukladu"),
    "atom_ambiguous_dataset": Text(
        "{context}: {chosen_count} {chosen_count:plural(file|files)} of the dataset "
        "left unresolved (expected one)",
        "{context}: {chosen_count} {chosen_count:plural(plik|pliki|plikow)} zbioru "
        "bez rozstrzygniecia (oczekiwano jednego)",
    ),
    "atom_dataset_not_in_feed": Text(
        "ATOM {service_feed}: dataset {dataset_key!r} not found in the service feed",
        "ATOM {service_feed}: brak zbioru {dataset_key!r} w feedzie uslugi",
    ),
    "atom_truncated_download": Text(
        "{url}: downloaded {size} of {expected} bytes according to {source} "
        "(interrupted transfer)",
        "{url}: pobrano {size} z {expected} bajtow wg {source} (przerwany transfer)",
    ),
    "atom_package_ambiguous_files": Text(
        "{url}: package without unambiguous files {mismatches} - members: {filenames}",
        "{url}: paczka bez jednoznacznych plikow {mismatches} - czlony: {filenames}",
    ),
    "atom_zip_corrupt": Text(
        "{url}: corrupt ZIP package: {error}",
        "{url}: uszkodzona paczka ZIP: {error}",
    ),
    # ``transport.chunks``.
    "pixel_grid_step_mismatch": Text(
        "align_bbox: pixel {pixel_size} differs from source grid step {grid_step} "
        "(service-side resampling is not supported)",
        "align_bbox: piksel {pixel_size} rozny od kroku siatki zrodla {grid_step} "
        "(przeprobkowanie po stronie uslugi nie jest obslugiwane)",
    ),
    "chunk_size_not_multiple": Text(
        "plan_chunks: {width} x {height} px is not a multiple of {multiple}",
        "plan_chunks: {width} x {height} px nie jest wielokrotnoscia {multiple}",
    ),
    "mosaic_stitch_failed": Text(
        "failed to stitch {parts_count} mosaic parts into {output_path}: {error}",
        "nie udalo sie zszyc {parts_count} kawalkow mozaiki w {output_path}: {error}",
    ),
    # ``transport.feature_bbox``.
    "pages_count_mismatch": Text(
        "{context}: pages yield {seen_count} distinct features, but the count query "
        "returned {total} (data changed during the download)",
        "{context}: strony daja {seen_count} roznych obiektow, a zapytanie o liczbe "
        "{total} (dane zmienily sie w trakcie)",
    ),
    "incomplete_response": Text(
        "{context}: incomplete response - {seen_count} of {total} features (pages "
        "ended at position {end_position})",
        "{context}: niepelna odpowiedz - {seen_count} z {total} obiektow (koniec "
        "stron na pozycji {end_position})",
    ),
    "no_features_in_area": Text(
        "{service}: no features in the area (layers: {sources})",
        "{service}: brak obiektow w obszarze (warstwy: {sources})",
    ),
    "response_not_xml": Text(
        "{context}: response is not an XML document ({content_type}): {error}",
        "{context}: odpowiedz nie jest dokumentem XML ({content_type}): {error}",
    ),
    "service_error_tag": Text(
        "{context}: service error ({tag}): {message}",
        "{context}: blad uslugi ({tag}): {message}",
    ),
    "feature_type_not_published": Text(
        "{context}: the service does not publish feature type {source}",
        "{context}: usluga nie publikuje typu obiektow {source}",
    ),
    "default_crs_mismatch": Text(
        "{context}: default CRS of {source} is {declared!r}, expected {native_crs}",
        "{context}: uklad domyslny {source} to {declared!r}, oczekiwano {native_crs}",
    ),
    "page_size_over_limit": Text(
        "{context}: the service returns at most {min_limits} features per page, but "
        "the channel requests {page_size}",
        "{context}: usluga zwraca najwyzej {min_limits} obiektow na strone, a kanal "
        "zada {page_size}",
    ),
    "wfs_hits_missing": Text(
        "{context}: the service did not provide the feature count "
        "(numberMatched={matched!r})",
        "{context}: usluga nie podala liczby obiektow (numberMatched={matched!r})",
    ),
    "incomplete_page": Text(
        "{context}: incomplete page (numberReturned={returned!r}, features {members})",
        "{context}: niepelna strona (numberReturned={returned!r}, obiektow {members})",
    ),
    "member_without_feature": Text(
        "{context}: wfs:member element without a feature",
        "{context}: element wfs:member bez obiektu",
    ),
    "feature_without_id": Text(
        "{context}: feature {local} without identifier {id_field}",
        "{context}: obiekt {local} bez identyfikatora {id_field}",
    ),
    "response_not_json": Text(
        "{context}: response is not JSON ({content_type}): {error}",
        "{context}: odpowiedz nie jest JSON ({content_type}): {error}",
    ),
    "response_not_json_object": Text(
        "{context}: response is not a JSON object",
        "{context}: odpowiedz nie jest obiektem JSON",
    ),
    "service_error": Text(
        "{context}: {service} service error: {message} {details}",
        "{context}: blad uslugi {service}: {message} {details}",
    ),
    "layer_no_fields": Text(
        "{context}: layer description has no field list (fields)",
        "{context}: opis warstwy bez listy pol (fields)",
    ),
    "layer_missing_field": Text(
        "{context}: layer has no field {required}",
        "{context}: warstwa nie ma pola {required}",
    ),
    "layer_crs_mismatch": Text(
        "{context}: layer CRS is EPSG:{wkid}, expected {native_crs}",
        "{context}: uklad warstwy EPSG:{wkid}, oczekiwano {native_crs}",
    ),
    "arcgis_page_over_limit": Text(
        "{context}: the service returns at most {limit} features per page, but the "
        "channel requests {page_size}",
        "{context}: usluga zwraca najwyzej {limit} obiektow na strone, a kanal zada "
        "{page_size}",
    ),
    "arcgis_count_missing": Text(
        "{context}: the service did not provide the feature count ({count!r})",
        "{context}: usluga nie podala liczby obiektow ({count!r})",
    ),
    "response_not_geojson": Text(
        "{context}: response is not a GeoJSON collection",
        "{context}: odpowiedz nie jest kolekcja GeoJSON",
    ),
    "feature_no_identifier": Text(
        "{context}: feature without identifier {id_field} ({value!r})",
        "{context}: obiekt bez identyfikatora {id_field} ({value!r})",
    ),
    "no_collections_list": Text(
        "{context}: response without a list of collections (collections)",
        "{context}: odpowiedz bez listy kolekcji (collections)",
    ),
    "collections_not_published": Text(
        "{context}: service does not publish collections {missing}",
        "{context}: usluga nie publikuje kolekcji {missing}",
    ),
    "ogcapi_page_description": Text(
        "{context} (page {pages_count})",
        "{context} (strona {pages_count})",
    ),
    "ogcapi_count_mismatch": Text(
        "{context}: pages give {seen_count} distinct features, but numberMatched is "
        "{total} (data changed in the meantime)",
        "{context}: strony daja {seen_count} roznych obiektow, a numberMatched "
        "{total} (dane zmienily sie w trakcie)",
    ),
    "reason_no_new_features": Text("no new features", "brak nowych obiektow"),
    "no_next_link": Text("no next link", "brak next"),
    "ogcapi_incomplete_response": Text(
        "{context}: incomplete response - {seen_count} of {total} features (page "
        "{page_index}: {reason})",
        "{context}: niepelna odpowiedz - {seen_count} z {total} obiektow (strona "
        "{page_index}: {reason})",
    ),
    "ogcapi_matched_changed": Text(
        "{context}: numberMatched of page {page_index} is {matched}, but of the first "
        "page {total} (data changed in the meantime)",
        "{context}: numberMatched strony {page_index} to {matched}, a pierwszej "
        "{total} (dane zmienily sie w trakcie)",
    ),
    "ogcapi_incomplete_page": Text(
        "{context}: incomplete page (numberReturned={returned!r}, features "
        "{features_count})",
        "{context}: niepelna strona (numberReturned={returned!r}, obiektow "
        "{features_count})",
    ),
    "links_not_list": Text(
        "{context}: links field is not a list",
        "{context}: pole links nie jest lista",
    ),
    "multiple_next_links": Text(
        "{context}: multiple next links: {hrefs}",
        "{context}: kilka linkow next: {hrefs}",
    ),
    "next_link_foreign_origin": Text(
        "{context}: next link outside service {endpoint}: {url}",
        "{context}: link next spoza uslugi {endpoint}: {url}",
    ),
    # ``transport.http``.
    "no_attempt": Text("no attempt made", "bez proby"),
    "response_timeout": Text("response timed out", "przekroczony czas odpowiedzi"),
    "dns_failure": Text(
        "network down or DNS failure (unknown host name)",
        "brak sieci albo DNS (nieznana nazwa serwera)",
    ),
    "connection_broken": Text(
        "connection broken or refused",
        "zerwane albo odrzucone polaczenie",
    ),
    "http_error_no_retry": Text(
        "{context}: HTTP {http_status} (no retries): {error}",
        "{context}: HTTP {http_status} (bez ponowien): {error}",
    ),
    "attempt_failed_retrying": Text(
        "{context}: attempt {attempt}/{retries} failed ({failure_reason}); retrying "
        "in {delay}s",
        "{context}: proba {attempt}/{retries} nieudana ({failure_reason}); ponowienie "
        "za {delay}s",
    ),
    "download_failed_retries": Text(
        "{context}: download failed after {retries} attempts ({failure_reason})",
        "{context}: pobranie nieudane po {retries} probach ({failure_reason})",
    ),
    "check_failed_retries": Text(
        "{context}: check failed after {retries} attempts ({failure_reason})",
        "{context}: sprawdzenie nieudane po {retries} probach ({failure_reason})",
    ),
    "download_http_no_retry": Text(
        "Failed to download {context}: HTTP {http_status} (no retries): {error}",
        "Nie udalo sie pobrac {context}: HTTP {http_status} (bez ponowien): {error}",
    ),
    "download_failed_retrying": Text(
        "Download of {context} failed (attempt {attempt}/{retries}: "
        "{failure_reason}); retrying in {wait}s",
        "Pobranie {context} nieudane (proba {attempt}/{retries}: {failure_reason}); "
        "ponowienie za {wait}s",
    ),
    "download_gave_up": Text(
        "Failed to download {context} after {retries} attempts ({failure_reason})",
        "Nie udalo sie pobrac {context} po {retries} probach ({failure_reason})",
    ),
    # ``transport.index_records``.
    "gfi_context": Text("{sheet}: layer {layer}", "{sheet}: warstwa {layer}"),
    "gfi_not_utf8": Text(
        "{context}: GFI response is not UTF-8 ({error})",
        "{context}: odpowiedz GFI nie jest UTF-8 ({error})",
    ),
    "gfi_ogc_exception": Text(
        "{context}: OGC exception report: {excerpt}",
        "{context}: raport wyjatku OGC: {excerpt}",
    ),
    "gfi_no_sheet_table": Text(
        "{context}: response has no sheet table for layer {layer}",
        "{context}: odpowiedz bez tabeli arkusza warstwy {layer}",
    ),
    "index_feature_skipped": Text(
        "Index {endpoint}: feature {fid} skipped ({error})",
        "Indeks {endpoint}: obiekt {fid} pominiety ({error})",
    ),
    "no_https_url_field": Text(
        "no HTTPS URL in field {url_field}",
        "brak adresu HTTPS w polu {url_field}",
    ),
    "url_no_filename": Text(
        "URL {url} has no file name",
        "adres {url} bez nazwy pliku",
    ),
    "missing_unit_field": Text("missing field {unit_field}", "brak pola {unit_field}"),
    "no_label_values": Text(
        "no values in label fields {label_fields}",
        "brak wartosci pol etykiety {label_fields}",
    ),
    "tile_unit_label": Text("tile {unit}", "kafel {unit}"),
    "year_not_number": Text(
        "year {text!r} in field {year_field} is not a number",
        "rok {text!r} w polu {year_field} nie jest liczba",
    ),
    "unknown_crs_in_field": Text(
        "unknown CRS {value!r} in field {zone_field}",
        "nieznany uklad {value!r} w polu {zone_field}",
    ),
    "invalid_sheet_code": Text(
        "{context}: invalid sheet code {published!r}",
        "{context}: nieprawidlowe godlo {published!r}",
    ),
    "sheet_no_state_date": Text(
        "{context}: sheet {published} has no database state date",
        "{context}: arkusz {published} bez daty stanu bazy",
    ),
    "link_not_https": Text(
        "{context}: link {href!r} is not HTTPS",
        "{context}: link {href!r} bez HTTPS",
    ),
    "sheet_two_links": Text(
        "{context}: sheet {published} has two {kind} links",
        "{context}: arkusz {published} ma dwa linki {kind}",
    ),
    "sheet_no_link": Text(
        "{context}: sheet {published} has no PDF/GeoTIFF link",
        "{context}: arkusz {published} bez linku PDF/GeoTIFF",
    ),
    "gfi_source_invalid": Text(
        "index {endpoint}: GFI read requires kind='wms_gfi' and parser='map_links' "
        "(got {kind!r}, {parser!r})",
        "indeks {endpoint}: odczyt GFI wymaga kind='wms_gfi' i parser='map_links' "
        "(podano {kind!r}, {parser!r})",
    ),
    "wfs_source_invalid": Text(
        "index {endpoint}: WFS read requires kind='wfs' and url_field (got {kind!r}, "
        "{url_field!r})",
        "indeks {endpoint}: odczyt WFS wymaga kind='wfs' i url_field (podano "
        "{kind!r}, {url_field!r})",
    ),
    # ``transport.mosaic``.
    "off_grid_sources": Text(
        "{off_grid_count} of {total} {total:plural(source|sources)} lie on a different "
        "pixel grid than the rest (max. offset {worst:.3f} px): {names}{more}",
        "{off_grid_count} z {total} {total:plural(zrodla|zrodel|zrodel)} lezy na innej "
        "siatce pikseli niz pozostale (maks. przesuniecie {worst:.3f} px): "
        "{names}{more}",
    ),
    "rotated_source_grid": Text(
        "rotated source grid {name}",
        "obrocona siatka zrodla {name}",
    ),
    "source_resolution_mismatch": Text(
        "inconsistent source resolutions: {res_set}",
        "niezgodne rozdzielczosci zrodel: {res_set}",
    ),
    "check_grid_no_inputs": Text(
        "check_source_grid: no input rasters",
        "check_source_grid: brak rastrow wejsciowych",
    ),
    "mosaic_no_inputs": Text(
        "mosaic_and_crop: no input rasters",
        "mosaic_and_crop: brak rastrow wejsciowych",
    ),
    "mosaic_crs_mismatch": Text(
        "mosaic_and_crop: inconsistent input CRS: {crs_set}",
        "mosaic_and_crop: niezgodne CRS wejsc: {crs_set}",
    ),
    "mosaic_resolution_mismatch": Text(
        "mosaic_and_crop: inconsistent input resolutions: {res_set}",
        "mosaic_and_crop: niezgodne rozdzielczosci wejsc: {res_set}",
    ),
    "mosaic_band_type_mismatch": Text(
        "mosaic_and_crop: sources have different band types ({dtype_set}) - pass "
        "dtype=",
        "mosaic_and_crop: zrodla maja rozne typy pasm ({dtype_set}) - podaj dtype=",
    ),
    "vrt_single_band_only": Text(
        "mosaic_and_crop: source {name} has {band_count} bands - VRT wrapping (dtype) "
        "supports only single-band rasters",
        "mosaic_and_crop: zrodlo {name} ma {band_count} pasm - owijanie w VRT (dtype) "
        "obsluguje tylko rastry jednopasmowe",
    ),
    "mosaic_band_type_unsupported": Text(
        "mosaic_and_crop: band type {band_type!r} (source {name}) is not among the "
        "supported types: {vrt_types}",
        "mosaic_and_crop: typ pasma {band_type!r} (zrodlo {name}) spoza "
        "obslugiwanych: {vrt_types}",
    ),
    # ``transport.unit_package``.
    "kind_zip": Text("a ZIP package", "paczki ZIP"),
    "kind_tiff": Text("a TIFF file", "pliku TIFF"),
    "kind_pdf": Text("a PDF file", "pliku PDF"),
    "kind_txt": Text("a text file", "pliku tekstowego"),
    "default_subject": Text("this product", "tego produktu"),
    "flag_not_applicable": Text(
        "{cli_flag} does not apply to {subject}{choices_note}",
        "{cli_flag} nie dotyczy {subject}{choices_note}",
    ),
    "choices_note": Text(" (choices: {cli_flags})", " (wybory: {cli_flags})"),
    "where_context": Text(" for {context}", " dla {context}"),
    "variant_not_available": Text(
        "{cli_flag} {given_value}: not available{where}; available: {allowed}",
        "{cli_flag} {given_value}: niedostepne{where}; dostepne: {allowed}",
    ),
    "choice_required": Text(
        "{cli_flag} required{where}: {allowed}",
        "{cli_flag} wymagane{where}: {allowed}",
    ),
    "index_record_no_file": Text(
        "{unit}: index record has no {file_format} file (found: {urls})",
        "{unit}: rekord indeksu bez pliku {file_format} (sa: {urls})",
    ),
    "none_found": Text("none", "brak"),
    "unexpected_document_type": Text(
        "{url}: source returned a document ({content_type}) instead of {expected_kind}",
        "{url}: zrodlo zwrocilo dokument ({content_type}) zamiast {expected_kind}",
    ),
    "what_package": Text("package", "paczki"),
    "what_file": Text("file", "pliku"),
    "source_not_published": Text(
        "The source does not publish the {what} {url} (HTTP 404)",
        "Zrodlo nie publikuje {what} {url} (HTTP 404)",
    ),
    "transfer_interrupted": Text(
        "{url}: downloaded {size} of {expected} bytes (interrupted transfer)",
        "{url}: pobrano {size} z {expected} bajtow (przerwany transfer)",
    ),
    "file_read_failed": Text(
        "{url}: could not read the file: {error}",
        "{url}: nie udalo sie odczytac pliku: {error}",
    ),
    "unexpected_file_head": Text(
        "{url}: expected {kind_text}, but the file starts with {head!r} - this is not "
        "the expected data",
        "{url}: oczekiwano {kind_text}, a plik zaczyna sie od {head!r} - to nie sa "
        "oczekiwane dane",
    ),
    "package_missing_files": Text(
        "{url}: package lacks files {missing} ({files_count} "
        "{files_count:plural(file|files)}) - this is not the expected data",
        "{url}: paczka bez plikow {missing} ({files_count} "
        "{files_count:plural(plik|pliki|plikow)}) - to nie sa oczekiwane dane",
    ),
    "unpack_count_mismatch": Text(
        "{url}: expected exactly one {unpack} file in the package, found "
        "{chosen_count}",
        "{url}: oczekiwano dokladnie jednego pliku {unpack} w paczce, jest "
        "{chosen_count}",
    ),
    "package_read_failed": Text(
        "{url}: could not read the package: {error}",
        "{url}: nie udalo sie odczytac paczki: {error}",
    ),
    "package_no_class_files": Text(
        "{url}: package has no feature class files ({files_count} "
        "{files_count:plural(file|files)}) - this is not the expected data",
        "{url}: paczka bez plikow klas obiektow ({files_count} "
        "{files_count:plural(plik|pliki|plikow)}) - to nie sa oczekiwane dane",
    ),
    "package_classes_absent": Text(
        "{url}: package has no files for classes {classes} (no features of these "
        "classes in the unit)",
        "{url}: paczka nie ma plikow klas {classes} (brak obiektow tych klas w "
        "jednostce)",
    ),
    "gpkg_missing_layers": Text(
        "{url}: GeoPackage lacks layers {missing} (found: {found}) - this is not the "
        "expected data",
        "{url}: GeoPackage bez warstw {missing} (sa: {found}) - to nie sa oczekiwane "
        "dane",
    ),
    "not_geopackage": Text(
        "{url}: file in the package is not a GeoPackage: {error}",
        "{url}: plik w paczce nie jest GeoPackage: {error}",
    ),
}
