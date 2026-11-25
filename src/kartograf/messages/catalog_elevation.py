"""Messages of the command catalog: the declarations of ``elevation``."""

from kartograf.messages import Text

MESSAGES = {
    "sheet_description": Text(
        "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 (`6.129.30.25.3`), CZ SM5 "
        "(`CTES96`) or CZ TM33 (`302_5550`). A coarser PL code expands to the source "
        "sheets; contours take SM5 sheets only.",
        "Godło arkusza - pliki tego arkusza ze źródła (grubsze godło rozwija się na "
        "arkusze źródła; LAZ PL: kafle przecinające arkusz, LAZ CZ: plik godła; NMT "
        "100 m: pliki województw arkusza): PL-1992 (np. N-34-130-D-d-2-4), PL-2000 "
        "(np. 6.129.30.25.3), CZ SM5 (np. CTES96; warstwice tylko SM5) albo CZ TM33 "
        "(np. 302_5550)",
    ),
    "geometry_description": Text(
        "Vector file (SHP, GPKG or GeoJSON): PL sheets that intersect its features "
        "(a polygon, not its extent); LAZ tiles, CZ LAZ and contours: those that "
        "intersect its extent; cutout: its extent.",
        "Plik geometrii obszaru (SHP, GPKG albo GeoJSON): PL - arkusze przecinające "
        "obiekty (wielobok, nie jego obwiednię); kafle LAZ, CZ LAZ i warstwice - "
        "przecinające obwiednię geometrii; wycinek (--cutout) - obwiednia geometrii",
    ),
    "resolution_description": Text(
        "Grid resolution label such as `1m`; required where the product offers a "
        'choice. One value applies to every country of the task, or give {{"pl": '
        '"1m", "cz": "2m"}}. Choices per source: `elevation list-sources`. Not used '
        "for LAZ and contours.{resolution_text:skip}{cz_resolution_help:skip}",
        "Rozdzielczość siatki - wymagana tam, gdzie jest wybór. PL (siatki ASC; NMT "
        "100m - pliki XYZ województw): {resolution_text}; wycinek --cutout tylko 1m "
        "(można pominąć); archiwa (--format): rozdzielczości w kartograf elevation "
        "list-sources. CZ: {cz_resolution_help}. LAZ i warstwice bez rozdzielczości. "
        "Jedna wartość dotyczy każdego kraju zadania; zadanie PL+CZ z różnymi: "
        "pl=WARTOŚĆ,cz=WARTOŚĆ (np. pl=1m,cz=2m)",
    ),
    "model_description": Text(
        "CZ LAZ point-cloud model; required with `product=laz` when the task reaches "
        "CZ. Not for other products.{cz_model_text:skip}",
        "Model chmury LAZ CZ (wymagany z --product laz gdy zadanie sięga CZ): "
        "{cz_model_text}. Z --product laz PL i innym produktem: błąd",
    ),
    "vertical_crs_description": Text(
        "Height system; required (omit for NMT 100 m: GUGiK declares none). One value "
        'must exist in every country of the task, or give {{"pl": "EVRF2007", "cz": '
        '"Bpv"}}. CZ LAZ: Bpv is SM5 files, EVRF2007 TM33 files (clouds are not '
        "transformed); CZ contours: Bpv, may be "
        "omitted.{vertical_crs_text:skip}{cz_vertical_text:skip}",
        "Układ wysokości (wymagany). PL: {vertical_crs_text}; NMT 100 m: pomiń (GUGiK "
        "nie deklaruje układu). CZ: {cz_vertical_text}. LAZ CZ: Bpv = pliki SM5, "
        "EVRF2007 = pliki TM33; chmury nie są transformowane. Warstwice CZ: Bpv "
        "(można pominąć). Jedna wartość dotyczy każdego kraju zadania i musi być dla "
        "niego dostępna; PL+CZ z różnymi układami: pl=WARTOŚĆ,cz=WARTOŚĆ (np. "
        "pl=EVRF2007,cz=Bpv)",
    ),
    "format_description": Text(
        "File format. Without it NMT/NMPT PL are ASC grids. Source archives (XYZ, "
        "TIN, ...) are fetched as published, without conversion, and not with "
        "`cutout`; contours (required): SHP or DGN, the ZIP of an SM5 sheet. "
        "Variants: `elevation list-sources`.{format_text:skip}{contours_formats:skip}",
        "Format pliku. NMT/NMPT PL: bez flagi siatka ASC (format produktu); archiwa "
        "GUGiK - pliki źródłowe jak w skorowidzu (bez konwersji, bez --cutout; "
        "arkusze różnych skal wynikają ze skorowidza, bez --scale): {format_text}. "
        "Warstwice CZ (--product contours, wymagany): {contours_formats} - ZIP "
        "arkusza SM5 bez konwersji. Warianty: kartograf elevation list-sources",
    ),
    "sheet_system_description": Text(
        "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` (zones "
        "EPSG:2176-2179, needs `scale`). Required with `bbox` or `geometry` for PL "
        "(not with `cutout` or LAZ); implied by a sheet "
        "code.{sheet_system_choices:skip}",
        "Układ godeł arkuszy PL - wymagany z --bbox/--geometry dla PL (bez --cutout): "
        "{sheet_system_choices}. Wycinek --cutout: tylko 1992 (można pominąć). Z "
        "--sheet układ wynika z godła (podana wartość musi się z nim zgadzać). Nie "
        "dotyczy LAZ (układ każdego kafla z WFS) ani CZ",
    ),
    "scale_description": Text(
        "Scale of PL-2000 sheets: required with `bbox` or `geometry` and "
        "`sheet_system=2000`, and with a PL-2000 1:10000 code; optional with a finer "
        "code (expands it to its descendants). Not for PL-1992 (always 1:10000), CZ, "
        "LAZ and `cutout`.{scale_2000_choices:skip}",
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godłem PL-2000 1:10000 (np. 7.171.21): "
        "{scale_2000_choices}; z drobniejszym godłem PL-2000 opcjonalna (rozwija "
        "godło do potomków w tej skali). PL-1992: niedozwolona - GUGiK publikuje "
        "arkusze PL-1992 tylko w 1:10000 (godło 7-członowe), grubsze godło rozwija "
        "się do 1:10000 samo. Nie dotyczy CZ, LAZ i --cutout. Szczegóły: "
        "docs/USAGE.md 1.6",
    ),
    "cutout_description": Text(
        "Fetch one WCS cutout instead of sheets (with `bbox` or `geometry`; needs "
        "`horizontal_crs`). PL: 1 m NMT/NMPT on the sheet grid, masked to the PL "
        "land, as the server composes its flights (for the newest flight fetch "
        "sheets). CZ: an exportImage cutout, required for CZ raster areas. Not for "
        "LAZ.",
        "Tryb JEDNEGO wycinka zamiast arkuszy (tylko --bbox/--geometry; wymaga "
        "--horizontal-crs). PL: wycinek 1 m z WCS GUGiK (--product nmt albo nmpt, "
        "tylko --sheet-system 1992 i --resolution 1m) na siatce arkuszy, maska lądu "
        "PL (poza lądem nodata), plik <wsp>.tif (wersje w versions/, ponowne "
        "uruchomienie używa lokalnej wersji; --force pobiera); kompozycja lotów "
        "serwera (najnowszy lot arkuszy: pobierz arkusze bez --cutout); w trybie "
        "--geometry obejmuje CAŁĄ obwiednię geometrii. CZ: wycinek rastra exportImage "
        "- obszar CZ z NMT/NMPT (także część CZ przy --country auto) wymaga --cutout; "
        "LAZ bez wycinka",
    ),
    "horizontal_crs_description": Text(
        "CRS of the cutout; required with `cutout`, refused without it. Reprojected "
        "locally; the CZ native CRS is EPSG:5514.",
        "Układ poziomy wycinka - wymagany z --cutout (bez --cutout błąd); reprojekcja "
        "lokalna przypiętą operacją; natywny CZ: EPSG:5514",
    ),
    "year_description": Text(
        "Only this data year (acquisition year; `akt_rok` for LAZ): the newest flight "
        "of that year. A sheet or tile without it stops the run before any download. "
        "Excludes `min_year` and `max_year`; not with `cutout`.",
        "Tylko ten rok danych (rok pozyskania: aktualność NMT/NMPT, akt_rok LAZ); "
        "skrót --min-year ROK --max-year ROK; najnowszy lot z tego roku (wszystkie: "
        "--all-campaigns); brak roku na którymś arkuszu/kaflu = błąd przed pobraniem; "
        "nie działa z --cutout",
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
        "one per sheet. LAZ: coverage is not deduplicated. Not with `cutout`.",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); z flagą "
        "wszystkie loty z zakresu lat do <segment>/versions/; flagi roku ograniczają "
        "tylko dopuszczalne lata; LAZ: bez deduplikacji pokrycia; nie działa z "
        "--cutout",
    ),
    "full_sheet_description": Text(
        "NMT/NMPT: when the newest flight of a sheet is not full "
        "(`calyArkuszWypelnionyTrescia`), also fetch the newest full flight of the "
        "range (one more per sheet at most) and link it under `full_sheet/`. Not with "
        "`cutout` and LAZ.",
        "NMT/NMPT: gdy najnowszy lot arkusza nie jest pełny "
        "(calyArkuszWypelnionyTrescia), pobierz też najnowszy pełny lot z zakresu lat "
        "(najwyżej jeden dodatkowy lot na arkusz) i dowiąż go w "
        "<segment>/full_sheet/; pełny = w granicach Polski; nie działa z --cutout ani "
        "z LAZ",
    ),
    "min_density_description": Text(
        "LAZ PL only: keep the tiles with at least this point density (points per m2).",
        "Tylko LAZ PL (--product laz; z innym produktem błąd): zostaw kafle o "
        "gęstości punktów >= N pkt/m2",
    ),
    "check_description": Text(
        "Cheap signal: the ETag of SM5 sheets, TM33 DMR 4G and DMP OK EVRF2007 tiles "
        "and CZ LAZ; cutouts and ImageServer tiles have none.",
        "Porównaj lokalne wersje ze źródłem i wypisz raport (aktualne / nowsza / do "
        "pobrania / nie da się sprawdzić bez pobrania); niczego nie pobiera. Pliki "
        "arkuszy SM5, kafle TM33 DMR 4G/DMP OK EVRF2007 i LAZ CZ: ETag; wycinki i "
        "kafle z ImageServer: bez taniego sygnału",
    ),
    "workers_description": Text(
        "Parallel transfers (default 4; 1 = one by one).",
        "Liczba równoległych pobrań (domyślnie 4; 1 = po kolei)",
    ),
    "rule_give_exactly_one_area_sheet_bbox_geometry": Text(
        "Give exactly one area: --sheet, --bbox or --geometry",
        "Podaj dokładnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    "rule_cutout_needs_horizontal_crs": Text(
        "--cutout needs --horizontal-crs",
        "--cutout wymaga --horizontal-crs",
    ),
    "rule_horizontal_crs_works_only_cutout": Text(
        "--horizontal-crs works only with --cutout",
        "--horizontal-crs działa tylko z --cutout",
    ),
    "rule_cutout_works_only_bbox_geometry": Text(
        "--cutout works only with --bbox/--geometry",
        "--cutout działa tylko z --bbox/--geometry",
    ),
    "rule_year_excludes_min_year_max_year": Text(
        "--year excludes --min-year/--max-year",
        "--year wyklucza się z --min-year/--max-year",
    ),
    "rule_min_density_works_only_product_laz": Text(
        "--min-density works only with --product laz",
        "--min-density działa tylko z --product laz",
    ),
    "rule_model_applies_only_product_laz": Text(
        "--model applies only to --product laz",
        "--model dotyczy tylko --product laz",
    ),
    "example_pl_sheet_nmt_1_m_evrf2007": Text(
        "PL sheet: NMT 1 m in EVRF2007",
        "Arkusz PL: NMT 1 m w EVRF2007",
    ),
    "example_pl_laz_point_cloud_rectangle": Text(
        "PL LAZ point cloud for a rectangle",
        "Chmura LAZ PL dla prostokąta",
    ),
    "example_pl_area_nmt_5_m_sheets_1992_system": Text(
        "PL area: NMT 5 m sheets in the 1992 system",
        "Obszar PL: arkusze NMT 5 m w układzie 1992",
    ),
    "example_pl_cutout_nmt_1_m_wcs": Text(
        "PL cutout: NMT 1 m from WCS",
        "Wycinek PL: NMT 1 m z WCS",
    ),
    "example_cz_sm5_sheet_nmt_5_m_bpv": Text(
        "CZ SM5 sheet: NMT 5 m in Bpv",
        "Arkusz CZ SM5: NMT 5 m w Bpv",
    ),
    "example_cz_cutout_s_jtsk": Text("CZ cutout in S-JTSK", "Wycinek CZ w S-JTSK"),
    "example_cz_laz_point_cloud_dmr_5g_model_rectangle": Text(
        "CZ LAZ point cloud: DMR 5G model for a rectangle",
        "Chmura LAZ CZ: model DMR 5G dla prostokąta",
    ),
    "sheet_description_2": Text(
        "Sheet code: PL (PL-1992 or PL-2000), CZ SM5 (`CTES96`) or TM33 tile "
        "(`760_5518`); the area is the sheet frame.",
        "Godło arkusza: PL (PL-1992 albo PL-2000), CZ SM5 (np. CTES96) albo kafel "
        "TM33 (np. 760_5518); obszar = rama arkusza",
    ),
    "geometry_description_2": Text(
        "Vector file (SHP, GPKG or GeoJSON): the area is its features (a polygon, "
        "not its extent; LAZ: the extent of the whole layer; CZ: of the geometry), as "
        "in `elevation download`.",
        "Plik geometrii obszaru (SHP, GPKG albo GeoJSON): obszar = obiekty (wielobok, "
        "nie jego obwiednia; LAZ: obwiednia całej warstwy; CZ: obwiednia geometrii) - "
        "jak w elevation download",
    ),
    "availability_year_description": Text(
        "Only this year (the yearly layer of the GUGiK index). Excludes `min_year` "
        "and `max_year`.",
        "Tylko ten rok (warstwa roczna skorowidza GUGiK); skrót --min-year ROK "
        "--max-year ROK",
    ),
    "availability_min_year_description": Text(
        "Lower bound of the year (inclusive).",
        "Dolna granica roku (włącznie)",
    ),
    "availability_max_year_description": Text(
        "Upper bound of the year (inclusive).",
        "Górna granica roku (włącznie)",
    ),
    "details_description": Text(
        "For every combination: the sheet codes of the incomplete sheets (CZ: sheets "
        "without a file), the area without sheets and every download command",
        "Dla każdej kombinacji: godła arkuszy niepełnych (CZ: arkuszy bez pliku), "
        "obszar bez arkuszy i wszystkie polecenia pobrania",
    ),
    "json_description": Text(
        "Print the report as JSON (kartograf-availability/1, the same shape as "
        "check_availability)",
        "Wypisz raport jako JSON (kartograf-availability/1, ten sam kształt co "
        "check_availability)",
    ),
    "force_description": Text(
        "Skip the metadata cache: query the indexes, PRG and CUZK files again and "
        "overwrite the cache entries.",
        "Pomiń cache metadanych (odpytaj skorowidze, PRG i pliki CUZK ponownie, "
        "nadpisz cache)",
    ),
    "elevation_download_summary": Text(
        "Download NMT, NMPT, LAZ or contours as sheets, tiles or one WCS cutout",
        "Pobierz NMT, NMPT, LAZ albo warstwice (arkusze, kafle albo wycinek)",
    ),
    "elevation_download_rule_1": Text(
        "Run `elevation availability` first if you do not know which years, grids and "
        "CRSs exist.",
        "Najpierw `elevation availability`, gdy nie wiesz, jakie lata, siatki i "
        "układy są dostępne.",
    ),
    "elevation_download_rule_2": Text(
        "Set `vertical_crs` and `resolution` yourself: nothing is guessed.",
        "Podaj `vertical_crs` i `resolution` jawnie: nic nie jest zgadywane.",
    ),
    "elevation_availability_summary": Text(
        "Report the years, grids, CRSs and formats of NMT, NMPT or LAZ for an area",
        "Raport dostępności NMT, NMPT i LAZ dla obszaru (bez pobierania)",
    ),
    "elevation_availability_description": Text(
        "Read only. PL: the years, grids, CRSs and formats for which the area has "
        "full sheets (LAZ: tiles) in the GUGiK index; CZ: which SM5 sheets and TM33 "
        "tiles have CUZK files, with date and size. Use it before `elevation "
        "download`; it fetches no data. `country=auto` reports both parts together.",
        "Bez pobierania danych: PL - dla jakich lat, układów, rozdzielczości, układów "
        "wysokości i formatów obszar ma komplet pełnych arkuszy (LAZ: kafli) wg "
        "skorowidza GUGiK (skorowidz WFS i maska lądu PRG; kompletna kombinacja: cały "
        "ląd obszaru leży w arkuszach pełnych, calyArkuszWypelnionyTrescia); CZ - "
        "które arkusze SM5 i kafle TM33 obszaru (indeks KladyMapovychListu) mają "
        "pliki CUZK, z datą publikacji i rozmiarem z nagłówków HEAD (CUZK nie "
        "publikuje lat nalotu). --country auto: części PL i CZ obszaru w jednym "
        "raporcie. Stopka podaje polecenia pobrania kompletnych kombinacji (PL: "
        "najnowszej).",
    ),
    "elevation_availability_rule": Text(
        "Take `year`, `resolution`, `vertical_crs` and `format` of a complete "
        "combination.",
        "Weź `year`, `resolution`, `vertical_crs` i `format` kompletnej kombinacji.",
    ),
    "example_nmt_availability_pl_rectangle": Text(
        "NMT availability in PL for a rectangle",
        "Dostępność NMT PL dla prostokąta",
    ),
    "example_nmpt_availability_cz_sheet": Text(
        "NMPT availability for a CZ sheet",
        "Dostępność NMPT dla arkusza CZ",
    ),
    "example_laz_availability_pl_since_2020_geometry": Text(
        "LAZ availability in PL since 2020 for a geometry",
        "Dostępność LAZ PL od 2020 dla geometrii",
    ),
    "elevation_group_summary": Text(
        "Elevation: DTM, DSM and LAZ point clouds (PL and CZ), contours (CZ)",
        "Wysokości: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)",
    ),
    "elevation_group_description": Text(
        "Elevation data from GUGiK (PL) and CUZK (CZ): DTM (NMT), DSM (NMPT), LAZ "
        "point clouds and ZABAGED contours (CZ).",
        "Dane wysokościowe NMT/NMPT i chmury punktów LAZ z GUGiK (PL) i CUZK (CZ) "
        "oraz warstwice ZABAGED (CZ).",
    ),
    "country_description": Text(
        "Country of the source; required with `bbox` or `geometry`, implied by a "
        "sheet code (a given value must agree). `auto` splits the area between PL and "
        "CZ.{country_choices:skip}",
        "Kraj źródła danych - wymagany z --bbox/--geometry: {country_choices}. Z "
        "--sheet kraj wynika z godła (podana wartość musi się z nim zgadzać)",
    ),
    "availability_country_description": Text(
        "Country; required with `bbox` or `geometry`, implied by a sheet code. `auto` "
        "reports the PL and CZ parts together.{countries:skip}",
        "Kraj - wymagany z --bbox/--geometry: {countries}. Z --sheet kraj wynika z "
        "godła",
    ),
    "download_upgrade_description": Text(
        "Fetch newer content when the source signals it (default: information only); "
        "files without a cheap signal stay local (fetch them with --force); with "
        "--plan run the saved plan",
        "Pobierz nowszą treść, gdy sygnał źródła ją wskazuje (domyślnie tylko "
        "informacja); pliki bez taniego sygnału zostają lokalne (pobranie: --force); "
        "z --plan wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file of the task again (sheets, LAZ tiles, cutouts) and refresh "
        "the list of campaigns from GUGiK; the same content = unchanged, other "
        "content = a new version; nothing is overwritten",
        "Pobierz ponownie każdy plik zadania (arkusze, kafle LAZ, wycinki) i odśwież "
        "listę kampanii z GUGiK; ta sama treść = bez zmian, inna = nowa wersja; nic "
        "nie jest nadpisywane",
    ),
    "download_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (JSON kartograf-plan/1, "
        "przy --country auto jeden plan PL i CZ); z --upgrade: wykonaj plan (pozycje "
        "zmienione od planu = błąd, bez pobrania)",
    ),
    "elevation_download_description": Text(
        "Fetches the DTM (NMT), DSM (NMPT), LAZ point clouds or CZ contours of GUGiK "
        "(PL) and CUZK (CZ) into the versioned store; `cutout` gives one WCS raster "
        "instead of sheets. Never overwrites: new content is a new version. {note} "
        "Not for imagery (`imagery download`).",
        "Pobierz NMT, NMPT i chmury punktów LAZ z GUGiK (PL) albo CUZK (CZ) do "
        "magazynu wersji. PL: --bbox/--geometry wybiera arkusze/kafle LAZ, --cutout "
        "--horizontal-crs daje wycinek 1 m z WCS GUGiK; NMT 100 m (--resolution 100m) "
        "to pliki XYZ województw obszaru. CZ: rastry SM5/TM33 z plików CUZK albo "
        "ImageServer (kafle TM33 DMR 4G i DMP OK z plików ETRS89/EVRF2007); dla "
        "obszaru rastra --cutout wymagane. LAZ CZ: --model i arkusz SM5/TM33 albo "
        "obszar (arkusze z indeksu), bez --cutout i bez transformacji chmur. "
        "Warstwice CZ (--product contours --format SHP|DGN): ZIP arkusza SM5 1:1, "
        "obszar = arkusze SM5 z indeksu, bez --cutout. {note}",
    ),
}
