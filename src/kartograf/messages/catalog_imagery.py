"""Messages of the command catalog: the declarations of ``imagery``."""

from kartograf.messages import Text

MESSAGES = {
    "sheet_description": Text(
        "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 (`6.129.30.25.3`) or CZ "
        "SM5 (`CTES96`, `AS91`: a JPEG with three JGW files). A coarser PL code "
        "expands to the source sheets.",
        "Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo PL rozwija sie "
        "na arkusze zrodla): PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. "
        "6.129.30.25.3) albo CZ SM5 (np. CTES96, AS91; JPEG i trzy pliki JGW)",
    ),
    "geometry_description": Text(
        "Vector file (SHP or GPKG): the sheets that intersect its features; for a "
        "cutout, its extent.",
        "Plik geometrii obszaru (SHP albo GPKG): arkusze przecinajace obiekty; "
        "wycinek (--cutout) - obwiednia geometrii",
    ),
    "direction_description": Text(
        "Oblique orthophotos only: view directions `n`, `e`, `s`, `w`; default all "
        "four. A sheet is one file per direction (`<code>_<direction>.tif`).",
        "Tylko --product oblique-orto: kierunki widoku po przecinku (n, e, s, w; np. "
        "n,e); arkusz orto ukosnej to plik na kierunek (<godlo>_<kierunek>.tif); bez "
        "flagi wszystkie cztery",
    ),
    "sheet_system_description": Text(
        "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` (zones "
        "EPSG:2176-2179, needs `scale`). Required with `bbox` or `geometry` for PL "
        "(not with `cutout`); may be omitted for a product with one system (true "
        "orthophoto 1992, oblique 2000); implied by a sheet code. Not for "
        "CZ.{sheet_system_choices:skip}",
        "Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL (bez --cutout): "
        "{sheet_system_choices}. Produkt z jednym ukladem (true orto: 1992, orto "
        "ukosna: 2000) i wycinek --cutout (tylko 1992): mozna pominac. Z --sheet "
        "uklad wynika z godla (podana wartosc musi sie z nim zgadzac). Nie dotyczy CZ "
        "(arkusze SM5; z --country auto dotyczy czesci PL)",
    ),
    "scale_description": Text(
        "Scale of PL-2000 sheets: required with `bbox` or `geometry` and "
        "`sheet_system=2000`, and with a PL-2000 1:10000 code; optional with a finer "
        "code. Oblique orthophotos have 1:2000 and 1:1000 sheets. Not for PL-1992 "
        "(one scale per product), CZ and `cutout`.{scale_2000_choices:skip}",
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        "{scale_2000_choices}; z drobniejszym godlem PL-2000 opcjonalna (rozwija "
        "godlo do potomkow w tej skali); orto ukosna ma arkusze 1:2000 i 1:1000. "
        "PL-1992: niedozwolona - GUGiK publikuje arkusze PL-1992 w jednej skali "
        "(1:10000, godlo 7-czlonowe; true orto: 1:5000, godlo 8-czlonowe), a grubsze "
        "godlo rozwija sie do niej samo. Nie dotyczy CZ (arkusze SM5 1:5000; z "
        "--country auto dotyczy czesci PL) i --cutout. Szczegoly: docs/USAGE.md 1.6",
    ),
    "cutout_description": Text(
        "Fetch one WCS cutout instead of sheets (with `bbox` or `geometry`; PL only; "
        "orthophoto and true orthophoto; needs `horizontal_crs` and `resolution`, "
        "orthophoto also `coverage`): an RGB GeoTIFF on the service grid, not "
        "resampled and not masked, as the server composes its flights.",
        "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry, tylko PL, "
        "ortofotomapa i true orto; wymaga --horizontal-crs i --resolution, "
        "ortofotomapa takze --coverage): GeoTIFF RGB z WCS GUGiK na siatce uslugi "
        "(obraz bez przeprobkowania, bez maski ladu), plik <wsp>.tif (wersje w "
        "versions/, ponowne uruchomienie uzywa lokalnej wersji; --force pobiera); "
        "kompozycja lotow serwera (bez wyboru roku); w trybie --geometry obejmuje "
        "CALA obwiednie geometrii",
    ),
    "horizontal_crs_description": Text(
        "CRS of the cutout; required with `cutout`, refused without it. Only the CRS "
        "of the service grid (the image is not resampled).",
        "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad): tylko uklad "
        "siatki uslugi (obraz bez przeprobkowania)",
    ),
    "coverage_description": Text(
        "WCS variant of an orthophoto cutout; required with `cutout` and "
        "`product=orto` (true orthophoto has one: omit it). `standard`: the newest "
        "available orthophotos; `high`: pixel 10 cm or "
        "finer.{orto_coverage_choices:skip}",
        "Wariant WCS wycinka ortofotomapy - wymagany z --cutout --product orto (bez "
        "--cutout blad; true orto ma jeden wariant - pomin): {orto_coverage_choices}",
    ),
    "resolution_description": Text(
        "Pixel size of a cutout; required with `cutout` (sheets keep the source "
        "pixel). The choices depend on `product` and "
        "`coverage`.{cutout_resolution_choices:skip}",
        "Piksel wycinka - wymagany z --cutout (arkusze maja piksel zrodla: bez "
        "--cutout blad): {cutout_resolution_choices}",
    ),
    "year_description": Text(
        "Only this data year (acquisition year of the images): the newest flight of "
        "that year. A sheet without it stops the run before any download. Excludes "
        "`min_year` and `max_year`; not with `cutout`.",
        "Tylko ten rok danych (rok pozyskania zdjec: aktualnosc ortofotomapy); skrot "
        "--min-year ROK --max-year ROK; najnowszy lot z tego roku (wszystkie: "
        "--all-campaigns); brak roku na ktoryms arkuszu = blad przed pobraniem; nie "
        "dziala z --cutout",
    ),
    "min_year_description": Text(
        "Lower bound of the data year (inclusive): the newest flight in the range, or "
        "all of them with `all_campaigns`. Not with `cutout`.",
        "Dolna granica roku danych (wlacznie); najnowszy lot z lat >= ROK (wszystkie: "
        "--all-campaigns); nie dziala z --cutout",
    ),
    "max_year_description": Text(
        "Upper bound of the data year (inclusive): the newest flight in the range, or "
        "all of them with `all_campaigns`; the standard path never moves to an older "
        "flight. Not with `cutout`.",
        "Gorna granica roku danych (wlacznie); najnowszy lot z lat <= ROK (wszystkie: "
        "--all-campaigns); sciezka standardowa nigdy nie cofa sie na starszy lot; nie "
        "dziala z --cutout",
    ),
    "all_campaigns_description": Text(
        "Fetch every flight of the year range into `versions/` instead of the newest "
        "one per sheet. Not with `cutout`.",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); z flaga "
        "wszystkie loty z zakresu lat do <segment>/versions/; flagi roku ograniczaja "
        "tylko dopuszczalne lata; nie dziala z --cutout",
    ),
    "full_sheet_description": Text(
        "Orthophoto and oblique orthophoto only (intensity and true orthophoto "
        "records declare no full sheets: an error): when the newest flight of a sheet "
        "is not full, also fetch the newest full flight of the range and link it "
        "under `full_sheet/`. Not with `cutout`.",
        "Ortofotomapa i orto ukosna (rekordy intensywnosci i true orto nie deklaruja "
        "pelnego arkusza: blad): gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot z zakresu lat "
        "(najwyzej jeden dodatkowy lot na arkusz) i dowiaz go w "
        "<segment>/full_sheet/; pelny = w granicach Polski; nie dziala z --cutout",
    ),
    "check_description": Text(
        "Signal: the GUGiK index for PL sheets, the release in the CUZK ATOM feed for "
        "CZ sheets; a cutout has none.",
        "Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne / nowsza / do "
        "pobrania / nie da sie sprawdzic bez pobrania); niczego nie pobiera. Arkusze "
        "PL: skorowidz GUGiK, arkusze CZ: wydanie w feedzie ATOM CUZK, wycinek: bez "
        "taniego sygnalu",
    ),
    "workers_description": Text(
        "Parallel transfers (default 4; 1 = one by one).",
        "Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    ),
    "rule_give_exactly_one_area_sheet_bbox_geometry": Text(
        "Give exactly one area: --sheet, --bbox or --geometry",
        "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    "rule_cutout_needs_horizontal_crs_resolution": Text(
        "--cutout needs --horizontal-crs and --resolution",
        "--cutout wymaga --horizontal-crs i --resolution",
    ),
    "rule_product_orto_cutout_needs_coverage": Text(
        "--product orto with --cutout needs --coverage",
        "--product orto z --cutout wymaga --coverage",
    ),
    "rule_horizontal_crs_coverage_resolution_work_only": Text(
        "--horizontal-crs, --coverage and --resolution work only with --cutout",
        "--horizontal-crs, --coverage i --resolution dzialaja tylko z --cutout",
    ),
    "rule_cutout_works_only_bbox_geometry": Text(
        "--cutout works only with --bbox/--geometry",
        "--cutout dziala tylko z --bbox/--geometry",
    ),
    "rule_direction_applies_only_product_oblique_orto": Text(
        "--direction applies only to --product oblique-orto",
        "--direction dotyczy tylko --product oblique-orto",
    ),
    "rule_year_excludes_min_year_max_year": Text(
        "--year excludes --min-year/--max-year",
        "--year wyklucza sie z --min-year/--max-year",
    ),
    "example_pl_orthophoto_sheet": Text(
        "PL orthophoto: a sheet",
        "Ortofotomapa PL: arkusz",
    ),
    "example_pl_orthophoto_wcs_cutout": Text(
        "PL orthophoto: a WCS cutout",
        "Ortofotomapa PL: wycinek WCS",
    ),
    "example_pl_orthophoto_sheets_rectangle_1992_system": Text(
        "PL orthophoto: sheets for a rectangle (1992 system)",
        "Ortofotomapa PL: arkusze dla prostokata (uklad 1992)",
    ),
    "example_pl_oblique_orthophoto_north_direction": Text(
        "PL oblique orthophoto: the north direction",
        "Orto ukosna PL: kierunek polnocny",
    ),
    "example_cz_orthophoto_sm5_sheet": Text(
        "CZ orthophoto: an SM5 sheet",
        "Ortofotomapa CZ: arkusz SM5",
    ),
    "example_cz_orthophoto_sm5_sheets_rectangle": Text(
        "CZ orthophoto: SM5 sheets for a rectangle",
        "Ortofotomapa CZ: arkusze SM5 dla prostokata",
    ),
    "imagery_download_summary": Text(
        "Download orthophotos and other images as sheets or one WCS cutout",
        "Pobierz arkusze obrazow (PL, CZ) albo wycinek (PL)",
    ),
    "imagery_download_rule": Text(
        "Use `cutout` for one image of an area, sheets for the source files.",
        "Uzyj `cutout` dla jednego obrazu obszaru, arkuszy dla plikow zrodlowych.",
    ),
    "imagery_group_summary": Text(
        "Imagery: orthophotos (PL, CZ), intensity images, true and oblique "
        "orthophotos (PL)",
        "Obrazy lotnicze: ortofotomapa PL i CZ, obrazy intensywnosci, true orto i "
        "orto ukosna (PL)",
    ),
    "imagery_group_description": Text(
        "Aerial images in the versioned store: the GUGiK orthophoto (PL: sheets and "
        "WCS cutout) and the CUZK one (CZ: SM5 sheets), LIDAR intensity images, the "
        "true orthophoto (sheets and WCS cutout) and the oblique orthophoto of GUGiK "
        "(PL).",
        "Obrazy lotnicze w magazynie wersji: ortofotomapa GUGiK (PL: arkusze i "
        "wycinek WCS) i CUZK (CZ: arkusze SM5), obrazy intensywnosci LIDAR, prawdziwa "
        "ortofotomapa (true orto: arkusze i wycinek WCS) i ortofotomapa ukosna GUGiK "
        "(PL).",
    ),
    "country_description": Text(
        "Country of the source; required with `bbox` or `geometry`, implied by a "
        "sheet code (a given value must agree). `auto` splits the area between PL and "
        "CZ; a cutout is PL only (with `auto` it covers the PL "
        "part).{country_choices:skip}",
        "Kraj zrodla danych - wymagany z --bbox/--geometry: {country_choices}. Z "
        "--sheet kraj wynika z godla (podana wartosc musi sie z nim zgadzac). Wycinek "
        "(--cutout) tylko PL: z auto obejmuje czesc PL",
    ),
    "download_upgrade_description": Text(
        "Fetch newer content when the source signals it (default: information only); "
        "a cutout without a cheap signal stays local (fetch it with --force); with "
        "--plan run the saved plan",
        "Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie tylko "
        "informacja); wycinek bez taniego sygnalu zostaje lokalny (pobranie: "
        "--force); z --plan wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file of the task again (sheets, cutout) and refresh the list of "
        "campaigns from GUGiK; the same content = unchanged, other content = a new "
        "version; nothing is overwritten",
        "Pobierz ponownie kazdy plik zadania (arkusze, wycinek) i odswiez liste "
        "kampanii z GUGiK; ta sama tresc = bez zmian, inna = nowa wersja; nic nie "
        "jest nadpisywane",
    ),
    "download_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (JSON kartograf-plan/1, "
        "przy --country auto jeden plan PL i CZ); z --upgrade: wykonaj plan (pozycje "
        "zmienione od planu = blad, bez pobrania)",
    ),
    "imagery_download_description": Text(
        "Fetches orthophoto, LIDAR intensity, true and oblique orthophoto of GUGiK "
        "(PL) and the SM5 orthophoto sheets of CUZK (CZ) into the versioned store. "
        "Sheets are the source files 1:1; `cutout` (PL orthophoto and true "
        "orthophoto) gives one WCS GeoTIFF. Never overwrites: new content is a new "
        "version. {note} Not for terrain (`elevation download`).",
        "Pobierz obrazy do magazynu wersji. PL (GUGiK): arkusze wg kampanii "
        "(--bbox/--geometry rozwija sie na arkusze zrodlowe, godla PL-1992 albo "
        "PL-2000) albo jeden wycinek GeoTIFF z WCS (--cutout: ortofotomapa i true "
        "orto); orto ukosna: arkusz = 4 pliki kierunkow (--direction). CZ (CUZK, "
        "tylko ortofotomapa): arkusze SM5 aktualnego rocznika (archiwalne ortofoto "
        "CUZK sa platne), JPEG z plikami JGW w S-JTSK, TM33N i TM34N "
        "(--bbox/--geometry rozwija sie na arkusze SM5). Arkusze: pliki zrodlowe 1:1, "
        "piksel zrodla. {note}",
    ),
}
