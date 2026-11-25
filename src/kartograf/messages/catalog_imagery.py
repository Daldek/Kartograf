"""Messages of the command catalog: the declarations of ``imagery``."""

from kartograf.messages import Text

MESSAGES = {
    "sheet_description": Text(
        "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 (`6.129.30.25.3`) or CZ "
        "SM5 (`CTES96`, `AS91`: a JPEG with three JGW files). A coarser PL code "
        "expands to the source sheets.",
        "Godło arkusza - pliki tego arkusza ze źródła (grubsze godło PL rozwija się "
        "na arkusze źródła): PL-1992 (np. N-34-130-D-d-2-4), PL-2000 (np. "
        "6.129.30.25.3) albo CZ SM5 (np. CTES96, AS91; JPEG i trzy pliki JGW)",
    ),
    "geometry_description": Text(
        "Vector file (SHP, GPKG or GeoJSON): the sheets that intersect its features; "
        "for a cutout, its extent.",
        "Plik geometrii obszaru (SHP, GPKG albo GeoJSON): arkusze przecinające "
        "obiekty; wycinek (--cutout) - obwiednia geometrii",
    ),
    "direction_description": Text(
        "Oblique orthophotos only: view directions `n`, `e`, `s`, `w`; default all "
        "four. A sheet is one file per direction (`<code>_<direction>.tif`).",
        "Tylko --product oblique-orto: kierunki widoku po przecinku (n, e, s, w; np. "
        "n,e); arkusz orto ukośnej to plik na kierunek (<godlo>_<kierunek>.tif); bez "
        "flagi wszystkie cztery",
    ),
    "sheet_system_description": Text(
        "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` (zones "
        "EPSG:2176-2179, needs `scale`). Required with `bbox` or `geometry` for PL "
        "(not with `cutout`); may be omitted for a product with one system (true "
        "orthophoto 1992, oblique 2000); implied by a sheet code. Not for "
        "CZ.{sheet_system_choices:skip}",
        "Układ godeł arkuszy PL - wymagany z --bbox/--geometry dla PL (bez --cutout): "
        "{sheet_system_choices}. Produkt z jednym układem (true orto: 1992, orto "
        "ukośna: 2000) i wycinek --cutout (tylko 1992): można pominąć. Z --sheet "
        "układ wynika z godła (podana wartość musi się z nim zgadzać). Nie dotyczy CZ "
        "(arkusze SM5; z --country auto dotyczy części PL)",
    ),
    "scale_description": Text(
        "Scale of PL-2000 sheets: required with `bbox` or `geometry` and "
        "`sheet_system=2000`, and with a PL-2000 1:10000 code; optional with a finer "
        "code. Oblique orthophotos have 1:2000 and 1:1000 sheets. Not for PL-1992 "
        "(one scale per product), CZ and `cutout`.{scale_2000_choices:skip}",
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godłem PL-2000 1:10000 (np. 7.171.21): "
        "{scale_2000_choices}; z drobniejszym godłem PL-2000 opcjonalna (rozwija "
        "godło do potomków w tej skali); orto ukośna ma arkusze 1:2000 i 1:1000. "
        "PL-1992: niedozwolona - GUGiK publikuje arkusze PL-1992 w jednej skali "
        "(1:10000, godło 7-członowe; true orto: 1:5000, godło 8-członowe), a grubsze "
        "godło rozwija się do niej samo. Nie dotyczy CZ (arkusze SM5 1:5000; z "
        "--country auto dotyczy części PL) i --cutout. Szczegóły: docs/USAGE.md 1.6",
    ),
    "cutout_description": Text(
        "Fetch one WCS cutout instead of sheets (with `bbox` or `geometry`; PL only; "
        "orthophoto and true orthophoto; needs `horizontal_crs` and `resolution`, "
        "orthophoto also `coverage`): an RGB GeoTIFF on the service grid, not "
        "resampled and not masked, as the server composes its flights.",
        "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry, tylko PL, "
        "ortofotomapa i true orto; wymaga --horizontal-crs i --resolution, "
        "ortofotomapa także --coverage): GeoTIFF RGB z WCS GUGiK na siatce usługi "
        "(obraz bez przepróbkowania, bez maski lądu), plik <wsp>.tif (wersje w "
        "versions/, ponowne uruchomienie używa lokalnej wersji; --force pobiera); "
        "kompozycja lotów serwera (bez wyboru roku); w trybie --geometry obejmuje "
        "CAŁĄ obwiednię geometrii",
    ),
    "horizontal_crs_description": Text(
        "CRS of the cutout; required with `cutout`, refused without it. Only the CRS "
        "of the service grid (the image is not resampled).",
        "Układ poziomy wycinka - wymagany z --cutout (bez --cutout błąd): tylko układ "
        "siatki usługi (obraz bez przepróbkowania)",
    ),
    "coverage_description": Text(
        "WCS variant of an orthophoto cutout; required with `cutout` and "
        "`product=orto` (true orthophoto has one: omit it). `standard`: the newest "
        "available orthophotos; `high`: pixel 10 cm or "
        "finer.{orto_coverage_choices:skip}",
        "Wariant WCS wycinka ortofotomapy - wymagany z --cutout --product orto (bez "
        "--cutout błąd; true orto ma jeden wariant - pomiń): {orto_coverage_choices}",
    ),
    "resolution_description": Text(
        "Pixel size of a cutout; required with `cutout` (sheets keep the source "
        "pixel). The choices depend on `product` and "
        "`coverage`.{cutout_resolution_choices:skip}",
        "Piksel wycinka - wymagany z --cutout (arkusze mają piksel źródła: bez "
        "--cutout błąd): {cutout_resolution_choices}",
    ),
    "year_description": Text(
        "Only this data year (acquisition year of the images): the newest flight of "
        "that year. A sheet without it stops the run before any download. Excludes "
        "`min_year` and `max_year`; not with `cutout`.",
        "Tylko ten rok danych (rok pozyskania zdjęć: aktualność ortofotomapy); skrót "
        "--min-year ROK --max-year ROK; najnowszy lot z tego roku (wszystkie: "
        "--all-campaigns); brak roku na którymś arkuszu = błąd przed pobraniem; nie "
        "działa z --cutout",
    ),
    "min_year_description": Text(
        "Lower bound of the data year (inclusive): the newest flight in the range, or "
        "all of them with `all_campaigns`. Not with `cutout`.",
        "Dolna granica roku danych (włącznie); najnowszy lot z lat >= ROK (wszystkie: "
        "--all-campaigns); nie działa z --cutout",
    ),
    "max_year_description": Text(
        "Upper bound of the data year (inclusive): the newest flight in the range, or "
        "all of them with `all_campaigns`; the standard path never moves to an older "
        "flight. Not with `cutout`.",
        "Górna granica roku danych (włącznie); najnowszy lot z lat <= ROK (wszystkie: "
        "--all-campaigns); ścieżka standardowa nigdy nie cofa się na starszy lot; nie "
        "działa z --cutout",
    ),
    "all_campaigns_description": Text(
        "Fetch every flight of the year range into `versions/` instead of the newest "
        "one per sheet. Not with `cutout`.",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); z flagą "
        "wszystkie loty z zakresu lat do <segment>/versions/; flagi roku ograniczają "
        "tylko dopuszczalne lata; nie działa z --cutout",
    ),
    "full_sheet_description": Text(
        "Orthophoto and oblique orthophoto only (intensity and true orthophoto "
        "records declare no full sheets: an error): when the newest flight of a sheet "
        "is not full, also fetch the newest full flight of the range and link it "
        "under `full_sheet/`. Not with `cutout`.",
        "Ortofotomapa i orto ukośna (rekordy intensywności i true orto nie deklarują "
        "pełnego arkusza: błąd): gdy najnowszy lot arkusza nie jest pełny "
        "(calyArkuszWypelnionyTrescia), pobierz też najnowszy pełny lot z zakresu lat "
        "(najwyżej jeden dodatkowy lot na arkusz) i dowiąż go w "
        "<segment>/full_sheet/; pełny = w granicach Polski; nie działa z --cutout",
    ),
    "check_description": Text(
        "Signal: the GUGiK index for PL sheets, the release in the CUZK ATOM feed for "
        "CZ sheets; a cutout has none.",
        "Porównaj lokalne wersje ze źródłem i wypisz raport (aktualne / nowsza / do "
        "pobrania / nie da się sprawdzić bez pobrania); niczego nie pobiera. Arkusze "
        "PL: skorowidz GUGiK, arkusze CZ: wydanie w feedzie ATOM CUZK, wycinek: bez "
        "taniego sygnału",
    ),
    "workers_description": Text(
        "Parallel transfers (default 4; 1 = one by one).",
        "Liczba równoległych pobrań (domyślnie 4; 1 = po kolei)",
    ),
    "rule_give_exactly_one_area_sheet_bbox_geometry": Text(
        "Give exactly one area: --sheet, --bbox or --geometry",
        "Podaj dokładnie jeden obszar: --sheet, --bbox albo --geometry",
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
        "--horizontal-crs, --coverage i --resolution działają tylko z --cutout",
    ),
    "rule_cutout_works_only_bbox_geometry": Text(
        "--cutout works only with --bbox/--geometry",
        "--cutout działa tylko z --bbox/--geometry",
    ),
    "rule_direction_applies_only_product_oblique_orto": Text(
        "--direction applies only to --product oblique-orto",
        "--direction dotyczy tylko --product oblique-orto",
    ),
    "rule_year_excludes_min_year_max_year": Text(
        "--year excludes --min-year/--max-year",
        "--year wyklucza się z --min-year/--max-year",
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
        "Ortofotomapa PL: arkusze dla prostokąta (układ 1992)",
    ),
    "example_pl_oblique_orthophoto_north_direction": Text(
        "PL oblique orthophoto: the north direction",
        "Orto ukośna PL: kierunek północny",
    ),
    "example_cz_orthophoto_sm5_sheet": Text(
        "CZ orthophoto: an SM5 sheet",
        "Ortofotomapa CZ: arkusz SM5",
    ),
    "example_cz_orthophoto_sm5_sheets_rectangle": Text(
        "CZ orthophoto: SM5 sheets for a rectangle",
        "Ortofotomapa CZ: arkusze SM5 dla prostokąta",
    ),
    "imagery_download_summary": Text(
        "Download orthophotos and other images as sheets or one WCS cutout",
        "Pobierz arkusze obrazów (PL, CZ) albo wycinek (PL)",
    ),
    "imagery_download_rule": Text(
        "Use `cutout` for one image of an area, sheets for the source files.",
        "Użyj `cutout` dla jednego obrazu obszaru, arkuszy dla plików źródłowych.",
    ),
    "imagery_group_summary": Text(
        "Imagery: orthophotos (PL, CZ), intensity images, true and oblique "
        "orthophotos (PL)",
        "Obrazy lotnicze: ortofotomapa PL i CZ, obrazy intensywności, true orto i "
        "orto ukośna (PL)",
    ),
    "imagery_group_description": Text(
        "Aerial images in the versioned store: the GUGiK orthophoto (PL: sheets and "
        "WCS cutout) and the CUZK one (CZ: SM5 sheets), LIDAR intensity images, the "
        "true orthophoto (sheets and WCS cutout) and the oblique orthophoto of GUGiK "
        "(PL).",
        "Obrazy lotnicze w magazynie wersji: ortofotomapa GUGiK (PL: arkusze i "
        "wycinek WCS) i CUZK (CZ: arkusze SM5), obrazy intensywności LIDAR, prawdziwa "
        "ortofotomapa (true orto: arkusze i wycinek WCS) i ortofotomapa ukośna GUGiK "
        "(PL).",
    ),
    "country_description": Text(
        "Country of the source; required with `bbox` or `geometry`, implied by a "
        "sheet code (a given value must agree). `auto` splits the area between PL and "
        "CZ; a cutout is PL only (with `auto` it covers the PL "
        "part).{country_choices:skip}",
        "Kraj źródła danych - wymagany z --bbox/--geometry: {country_choices}. Z "
        "--sheet kraj wynika z godła (podana wartość musi się z nim zgadzać). Wycinek "
        "(--cutout) tylko PL: z auto obejmuje część PL",
    ),
    "download_upgrade_description": Text(
        "Fetch newer content when the source signals it (default: information only); "
        "a cutout without a cheap signal stays local (fetch it with --force); with "
        "--plan run the saved plan",
        "Pobierz nowszą treść, gdy sygnał źródła ją wskazuje (domyślnie tylko "
        "informacja); wycinek bez taniego sygnału zostaje lokalny (pobranie: "
        "--force); z --plan wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file of the task again (sheets, cutout) and refresh the list of "
        "campaigns from GUGiK; the same content = unchanged, other content = a new "
        "version; nothing is overwritten",
        "Pobierz ponownie każdy plik zadania (arkusze, wycinek) i odśwież listę "
        "kampanii z GUGiK; ta sama treść = bez zmian, inna = nowa wersja; nic nie "
        "jest nadpisywane",
    ),
    "download_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (JSON kartograf-plan/1, "
        "przy --country auto jeden plan PL i CZ); z --upgrade: wykonaj plan (pozycje "
        "zmienione od planu = błąd, bez pobrania)",
    ),
    "imagery_download_description": Text(
        "Fetches orthophoto, LIDAR intensity, true and oblique orthophoto of GUGiK "
        "(PL) and the SM5 orthophoto sheets of CUZK (CZ) into the versioned store. "
        "Sheets are the source files 1:1; `cutout` (PL orthophoto and true "
        "orthophoto) gives one WCS GeoTIFF. Never overwrites: new content is a new "
        "version. {note} Not for terrain (`elevation download`).",
        "Pobierz obrazy do magazynu wersji. PL (GUGiK): arkusze wg kampanii "
        "(--bbox/--geometry rozwija się na arkusze źródłowe, godła PL-1992 albo "
        "PL-2000) albo jeden wycinek GeoTIFF z WCS (--cutout: ortofotomapa i true "
        "orto); orto ukośna: arkusz = 4 pliki kierunków (--direction). CZ (CUZK, "
        "tylko ortofotomapa): arkusze SM5 aktualnego rocznika (archiwalne ortofoto "
        "CUZK są płatne), JPEG z plikami JGW w S-JTSK, TM33N i TM34N "
        "(--bbox/--geometry rozwija się na arkusze SM5). Arkusze: pliki źródłowe 1:1, "
        "piksel źródła. {note}",
    ),
}
