"""Messages of the land cover orchestration: BDOT10k, CORINE and SoilGrids."""

from kartograf.messages import Text

MESSAGES = {
    # ``landcover.manager``.
    "teryt_products": Text(
        "--product bdot10k (county, 4 digits) or bdoo (voivodeship, 2 digits)",
        "--product bdot10k (powiat, 4 cyfry) albo bdoo (wojewodztwo, 2 cyfry)",
    ),
    "area_choices": Text(
        "--sheet, --bbox or --geometry",
        "--sheet, --bbox albo --geometry",
    ),
    "year_required": Text(
        "--year required for corine: 2018, 2012, 2006, 2000 (CLMS/WMS land cover "
        "editions), 1990 (WMS preview only)",
        "--year wymagane dla corine: 2018, 2012, 2006, 2000 (edycje pokrycia terenu "
        "CLMS/WMS), 1990 (tylko podglad WMS)",
    ),
    "property_required": Text(
        "--property required: bdod (bulk density), cec (cation exchange capacity), "
        "cfvo (coarse fragments), clay (clay), nitrogen (nitrogen), ocd (organic "
        "carbon density), ocs (organic carbon stock), phh2o (pH), sand (sand), silt "
        "(silt), soc (soil organic carbon)",
        "--property wymagane: bdod (gestosc objetosciowa), cec (pojemnosc sorpcyjna), "
        "cfvo (frakcja szkieletowa), clay (il), nitrogen (azot), ocd (gestosc wegla "
        "organicznego), ocs (zasob wegla organicznego), phh2o (pH), sand (piasek), "
        "silt (pyl), soc (wegiel organiczny)",
    ),
    "depth_required": Text(
        "--depth required: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm "
        "(depth interval below the surface); ocs only 0-30cm",
        "--depth wymagane: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm "
        "(przedzial glebokosci ponizej powierzchni); ocs tylko 0-30cm",
    ),
    "stat_required": Text(
        "--stat required: mean (average), Q0.05 (5th percentile), Q0.5 (median), "
        "Q0.95 (95th percentile), uncertainty (prediction uncertainty)",
        "--stat wymagane: mean (srednia), Q0.05 (5. percentyl), Q0.5 (mediana), Q0.95 "
        "(95. percentyl), uncertainty (niepewnosc predykcji)",
    ),
    "preview_note": Text("WMS preview, not data", "podglad WMS, nie dane"),
    "product_required": Text(
        "--product required: {landcover_product_choices}",
        "--product wymagane: {landcover_product_choices}",
    ),
    "product_unknown": Text(
        "--product {product!r}: unknown value - available: {landcover_product_choices}",
        "--product {product!r}: nieznana wartosc - dostepne: "
        "{landcover_product_choices}",
    ),
    "unknown_source": Text(
        "Unknown source: {name}. Available: {available}",
        "Nieznane zrodlo: {name}. Dostepne: {available}",
    ),
    "source_no_provider": Text(
        "{provider_name}: source without a provider (collection engines) - download: "
        "download(), layers: get_available_layers()",
        "{provider_name}: zrodlo bez providera (silniki kolekcji) - pobranie: "
        "download(), warstwy: get_available_layers()",
    ),
    "option_needs_product_owner": Text(
        "--{option_flag} only works with --product {owners:join( or )}",
        "--{option_flag} dziala tylko z --product {owners:join( albo )}",
    ),
    "horizontal_crs_type": Text(
        "--horizontal-crs: expected a string (e.g. 'EPSG:5514'), got "
        "{horizontal_crs!r}",
        "--horizontal-crs: oczekiwano napisu (np. 'EPSG:5514'), podano "
        "{horizontal_crs!r}",
    ),
    "teryt_unsupported_product": Text(
        "--teryt works only with {teryt_products}; --product {source}: give --bbox, "
        "--geometry or --whole-country",
        "--teryt dziala tylko z {teryt_products}; --product {source}: podaj --bbox, "
        "--geometry albo --whole-country",
    ),
    "bdot10k_one_selection": Text(
        "Give exactly one selection for --product bdot10k: {selection_choices}",
        "Podaj dokladnie jeden wybor dla --product bdot10k: {selection_choices}",
    ),
    "where_corine": Text(" for --product corine", " dla --product corine"),
    "one_area_selection": Text(
        "Give exactly one selection{where}: {area_choices}",
        "Podaj dokladnie jeden wybor{where}: {area_choices}",
    ),
    "teryt_wrong_product": Text(
        "--teryt works only with {teryt_products}; {name}: give {area_choices}",
        "--teryt dziala tylko z {teryt_products}; {name}: podaj {area_choices}",
    ),
    "teryt_needs_county": Text(
        "--teryt {teryt}: BDOT10k is published per county - give --teryt <4 digits> "
        "(e.g. 1465); available: {selection_choices}",
        "--teryt {teryt}: BDOT10k jest publikowany per powiat - podaj --teryt <4 "
        "cyfry> (np. 1465); dostepne: {selection_choices}",
    ),
    "invalid_teryt_code": Text(
        "Invalid TERYT code {teryt!r}: BDOT10k county (4 digits, e.g. 1465)",
        "Nieprawidlowy kod TERYT {teryt!r}: powiat BDOT10k (4 cyfry, np. 1465)",
    ),
    "corine_preview_problem": Text(
        "CORINE {year}: {problem} - WMS preview (styled PNG, not data)",
        "CORINE {year}: {problem} - podglad WMS (stylizowany PNG, nie dane)",
    ),
    "corine_preview_notice": Text(
        "CORINE {year}: WMS preview (styled PNG, not data; CLMS data requires "
        "CLMS_CREDENTIALS)",
        "CORINE {year}: podglad WMS (stylizowany PNG, nie dane; dane CLMS wymagaja "
        "CLMS_CREDENTIALS)",
    ),
    "unsupported_provider_kind": Text(
        "LandCoverManager supports BDOT10k, CORINE and SoilGrids, not {name!r} (file "
        "outside the store: provider.download_by_*)",
        "LandCoverManager obsluguje BDOT10k, CORINE i SoilGrids, nie {name!r} (plik "
        "poza magazynem: provider.download_by_*)",
    ),
    "option_needs_product": Text(
        "--{option_flag} only works with --product {products:join( or )}",
        "--{option_flag} dziala tylko z --product {products:join( albo )}",
    ),
    "bdot10k_archive_option": Text(
        "--{replace} does not apply to the BDOT10k archive (--year: county GML or SHP "
        "package saved 1:1)",
        "--{replace} nie dotyczy archiwum BDOT10k (--year: paczka powiatu GML albo "
        "SHP zapisywana 1:1)",
    ),
    "bdot10k_format_invalid": Text(
        "--format {fmt}: current BDOT10k packages are GPKG or SHP; GML only with "
        "--year (vintage archive)",
        "--format {fmt}: biezace paczki BDOT10k to GPKG albo SHP; GML tylko z --year "
        "(archiwum rocznikow)",
    ),
    "layers_gpkg_only": Text(
        "--layers applies only to --format GPKG (SHP is the original package ZIP)",
        "--layers dotyczy tylko --format GPKG (SHP to oryginalny ZIP paczki)",
    ),
    "keep_raw_gpkg_only": Text(
        "--keep-raw applies only to --format GPKG (SHP is already the original ZIP)",
        "--keep-raw dotyczy tylko --format GPKG (SHP to juz oryginalny ZIP)",
    ),
    "bdot10k_no_county": Text(
        "BDOT10k: area does not intersect any county (PRG)",
        "BDOT10k: obszar nie przecina zadnego powiatu (PRG)",
    ),
    "area_counties_prg": Text(
        "{product}: counties of the area per PRG ({county_count}): {county_names}",
        "{product}: powiaty obszaru wg PRG ({county_count}): {county_names}",
    ),
    "plan_requires_upgrade": Text(
        "The update plan requires update='upgrade'",
        "Plan aktualizacji wymaga update='upgrade'",
    ),
    "raster_all_nodata": Text(
        "{raster_path}: raster is entirely zero - SoilGrids gives 0 in areas without "
        "data (sea, water, built-up areas, rocks, ice); check --bbox",
        "{raster_path}: raster w calosci zerowy - SoilGrids daje 0 w obszarach bez "
        "danych (morze, woda, zabudowa, skaly, lod); sprawdz --bbox",
    ),
    "classes_absent_in_package": Text(
        "{product} PL {teryt}: package has no files for classes {absent} (no such "
        "objects); saved classes {classes}",
        "{product} PL {teryt}: paczka nie ma plikow klas {absent} (brak takich "
        "obiektow); zapisano klasy {classes}",
    ),
    "bdot10k_archive_choices": Text(
        "{years} (--format {formats:join( or )})",
        "{years} (--format {formats:join( albo )})",
    ),
    # ``landcover.store``.
    "exactly_one_selection": Text(
        "Give exactly one selection: teryt, bbox or sheet",
        "Podaj dokladnie jeden wybor: teryt, bbox albo sheet",
    ),
}
