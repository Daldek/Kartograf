"""Messages of the command catalog: the declarations of ``elevation``."""

from kartograf.messages import Text

MESSAGES = {
    "sheet_description": Text(
        "Sheet code: PL-1992 (`N-34-130-D-d-2-4`), PL-2000 (`6.129.30.25.3`), CZ SM5 "
        "(`CTES96`) or CZ TM33 (`302_5550`). A coarser PL code expands to the source "
        "sheets; contours take SM5 sheets only.",
        "Godlo arkusza - pliki tego arkusza ze zrodla (grubsze godlo rozwija sie na "
        "arkusze zrodla; LAZ PL: kafle przecinajace arkusz, LAZ CZ: plik godla; NMT "
        "100 m: pliki wojewodztw arkusza): PL-1992 (np. N-34-130-D-d-2-4), PL-2000 "
        "(np. 6.129.30.25.3), CZ SM5 (np. CTES96; warstwice tylko SM5) albo CZ TM33 "
        "(np. 302_5550)",
    ),
    "geometry_description": Text(
        "Vector file (SHP or GPKG): PL sheets and LAZ tiles that intersect its "
        "features; CZ LAZ and contours: the sheets that intersect its extent; cutout: "
        "its extent.",
        "Plik geometrii obszaru (SHP albo GPKG): PL - arkusze i kafle LAZ "
        "przecinajace obiekty; CZ LAZ i warstwice - arkusze przecinajace obwiednie "
        "geometrii; wycinek (--cutout) - obwiednia geometrii",
    ),
    "resolution_description": Text(
        "Grid resolution label such as `1m`; required where the product offers a "
        'choice. One value applies to every country of the task, or give {{"pl": '
        '"1m", "cz": "2m"}}. Choices per source: `elevation list-sources`. Not used '
        "for LAZ and contours.{resolution_text:skip}{cz_resolution_help:skip}",
        "Rozdzielczosc siatki - wymagana tam, gdzie jest wybor. PL (siatki ASC; NMT "
        "100m - pliki XYZ wojewodztw): {resolution_text}; wycinek --cutout tylko 1m "
        "(mozna pominac); archiwa (--format): rozdzielczosci w kartograf elevation "
        "list-sources. CZ: {cz_resolution_help}. LAZ i warstwice bez rozdzielczosci. "
        "Jedna wartosc dotyczy kazdego kraju zadania; zadanie PL+CZ z roznymi: "
        "pl=WARTOSC,cz=WARTOSC (np. pl=1m,cz=2m)",
    ),
    "model_description": Text(
        "CZ LAZ point-cloud model; required with `product=laz` when the task reaches "
        "CZ. Not for other products.{cz_model_text:skip}",
        "Model chmury LAZ CZ (wymagany z --product laz gdy zadanie siega CZ): "
        "{cz_model_text}. Z --product laz PL i innym produktem: blad",
    ),
    "vertical_crs_description": Text(
        "Height system; required (omit for NMT 100 m: GUGiK declares none). One value "
        'must exist in every country of the task, or give {{"pl": "EVRF2007", "cz": '
        '"Bpv"}}. CZ LAZ: Bpv is SM5 files, EVRF2007 TM33 files (clouds are not '
        "transformed); CZ contours: Bpv, may be "
        "omitted.{vertical_crs_text:skip}{cz_vertical_text:skip}",
        "Uklad wysokosci (wymagany). PL: {vertical_crs_text}; NMT 100 m: pomin (GUGiK "
        "nie deklaruje ukladu). CZ: {cz_vertical_text}. LAZ CZ: Bpv = pliki SM5, "
        "EVRF2007 = pliki TM33; chmury nie sa transformowane. Warstwice CZ: Bpv "
        "(mozna pominac). Jedna wartosc dotyczy kazdego kraju zadania i musi byc dla "
        "niego dostepna; PL+CZ z roznymi ukladami: pl=WARTOSC,cz=WARTOSC (np. "
        "pl=EVRF2007,cz=Bpv)",
    ),
    "format_description": Text(
        "File format. Without it NMT/NMPT PL are ASC grids. Source archives (XYZ, "
        "TIN, ...) are fetched as published, without conversion, and not with "
        "`cutout`; contours (required): SHP or DGN, the ZIP of an SM5 sheet. "
        "Variants: `elevation list-sources`.{format_text:skip}{contours_formats:skip}",
        "Format pliku. NMT/NMPT PL: bez flagi siatka ASC (format produktu); archiwa "
        "GUGiK - pliki zrodlowe jak w skorowidzu (bez konwersji, bez --cutout; "
        "arkusze roznych skal wynikaja ze skorowidza, bez --scale): {format_text}. "
        "Warstwice CZ (--product contours, wymagany): {contours_formats} - ZIP "
        "arkusza SM5 bez konwersji. Warianty: kartograf elevation list-sources",
    ),
    "sheet_system_description": Text(
        "Sheet system of PL sheets: `1992` (1:10000 sheets) or `2000` (zones "
        "EPSG:2176-2179, needs `scale`). Required with `bbox` or `geometry` for PL "
        "(not with `cutout` or LAZ); implied by a sheet "
        "code.{sheet_system_choices:skip}",
        "Uklad godel arkuszy PL - wymagany z --bbox/--geometry dla PL (bez --cutout): "
        "{sheet_system_choices}. Wycinek --cutout: tylko 1992 (mozna pominac). Z "
        "--sheet uklad wynika z godla (podana wartosc musi sie z nim zgadzac). Nie "
        "dotyczy LAZ (uklad kazdego kafla z WFS) ani CZ",
    ),
    "scale_description": Text(
        "Scale of PL-2000 sheets: required with `bbox` or `geometry` and "
        "`sheet_system=2000`, and with a PL-2000 1:10000 code; optional with a finer "
        "code (expands it to its descendants). Not for PL-1992 (always 1:10000), CZ, "
        "LAZ and `cutout`.{scale_2000_choices:skip}",
        "Skala arkuszy PL-2000 do pobrania - wymagana z --bbox/--geometry "
        "--sheet-system 2000 i z godlem PL-2000 1:10000 (np. 7.171.21): "
        "{scale_2000_choices}; z drobniejszym godlem PL-2000 opcjonalna (rozwija "
        "godlo do potomkow w tej skali). PL-1992: niedozwolona - GUGiK publikuje "
        "arkusze PL-1992 tylko w 1:10000 (godlo 7-czlonowe), grubsze godlo rozwija "
        "sie do 1:10000 samo. Nie dotyczy CZ, LAZ i --cutout. Szczegoly: "
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
        "tylko --sheet-system 1992 i --resolution 1m) na siatce arkuszy, maska ladu "
        "PL (poza ladem nodata), plik <wsp>.tif (wersje w versions/, ponowne "
        "uruchomienie uzywa lokalnej wersji; --force pobiera); kompozycja lotow "
        "serwera (najnowszy lot arkuszy: pobierz arkusze bez --cutout); w trybie "
        "--geometry obejmuje CALA obwiednie geometrii. CZ: wycinek rastra exportImage "
        "- obszar CZ z NMT/NMPT (takze czesc CZ przy --country auto) wymaga --cutout; "
        "LAZ bez wycinka",
    ),
    "horizontal_crs_description": Text(
        "CRS of the cutout; required with `cutout`, refused without it. Reprojected "
        "locally; the CZ native CRS is EPSG:5514.",
        "Uklad poziomy wycinka - wymagany z --cutout (bez --cutout blad); reprojekcja "
        "lokalna przypieta operacja; natywny CZ: EPSG:5514",
    ),
    "year_description": Text(
        "Only this data year (acquisition year; `akt_rok` for LAZ): the newest flight "
        "of that year. A sheet or tile without it stops the run before any download. "
        "Excludes `min_year` and `max_year`; not with `cutout`.",
        "Tylko ten rok danych (rok pozyskania: aktualnosc NMT/NMPT, akt_rok LAZ); "
        "skrot --min-year ROK --max-year ROK; najnowszy lot z tego roku (wszystkie: "
        "--all-campaigns); brak roku na ktoryms arkuszu/kaflu = blad przed pobraniem; "
        "nie dziala z --cutout",
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
        "one per sheet. LAZ: coverage is not deduplicated. Not with `cutout`.",
        "Bez flagi najnowszy lot na arkusz w zakresie lat (jeden lot); z flaga "
        "wszystkie loty z zakresu lat do <segment>/versions/; flagi roku ograniczaja "
        "tylko dopuszczalne lata; LAZ: bez deduplikacji pokrycia; nie dziala z "
        "--cutout",
    ),
    "full_sheet_description": Text(
        "NMT/NMPT: when the newest flight of a sheet is not full "
        "(`calyArkuszWypelnionyTrescia`), also fetch the newest full flight of the "
        "range (one more per sheet at most) and link it under `full_sheet/`. Not with "
        "`cutout` and LAZ.",
        "NMT/NMPT: gdy najnowszy lot arkusza nie jest pelny "
        "(calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot z zakresu lat "
        "(najwyzej jeden dodatkowy lot na arkusz) i dowiaz go w "
        "<segment>/full_sheet/; pelny = w granicach Polski; nie dziala z --cutout ani "
        "z LAZ",
    ),
    "min_density_description": Text(
        "LAZ PL only: keep the tiles with at least this point density (points per m2).",
        "Tylko LAZ PL (--product laz; z innym produktem blad): zostaw kafle o "
        "gestosci punktow >= N pkt/m2",
    ),
    "check_description": Text(
        "Cheap signal: the ETag of SM5 sheets, TM33 DMR 4G and DMP OK EVRF2007 tiles "
        "and CZ LAZ; cutouts and ImageServer tiles have none.",
        "Porownaj lokalne wersje ze zrodlem i wypisz raport (aktualne / nowsza / do "
        "pobrania / nie da sie sprawdzic bez pobrania); niczego nie pobiera. Pliki "
        "arkuszy SM5, kafle TM33 DMR 4G/DMP OK EVRF2007 i LAZ CZ: ETag; wycinki i "
        "kafle z ImageServer: bez taniego sygnalu",
    ),
    "workers_description": Text(
        "Parallel transfers (default 4; 1 = one by one).",
        "Liczba rownoleglych pobran (domyslnie 4; 1 = po kolei)",
    ),
    "rule_give_exactly_one_area_sheet_bbox_geometry": Text(
        "Give exactly one area: --sheet, --bbox or --geometry",
        "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    "rule_cutout_needs_horizontal_crs": Text(
        "--cutout needs --horizontal-crs",
        "--cutout wymaga --horizontal-crs",
    ),
    "rule_horizontal_crs_works_only_cutout": Text(
        "--horizontal-crs works only with --cutout",
        "--horizontal-crs dziala tylko z --cutout",
    ),
    "rule_cutout_works_only_bbox_geometry": Text(
        "--cutout works only with --bbox/--geometry",
        "--cutout dziala tylko z --bbox/--geometry",
    ),
    "rule_year_excludes_min_year_max_year": Text(
        "--year excludes --min-year/--max-year",
        "--year wyklucza sie z --min-year/--max-year",
    ),
    "rule_min_density_works_only_product_laz": Text(
        "--min-density works only with --product laz",
        "--min-density dziala tylko z --product laz",
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
        "Chmura LAZ PL dla prostokata",
    ),
    "example_pl_area_nmt_5_m_sheets_1992_system": Text(
        "PL area: NMT 5 m sheets in the 1992 system",
        "Obszar PL: arkusze NMT 5 m w ukladzie 1992",
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
        "Chmura LAZ CZ: model DMR 5G dla prostokata",
    ),
    "sheet_description_2": Text(
        "Sheet code: PL (PL-1992 or PL-2000), CZ SM5 (`CTES96`) or TM33 tile "
        "(`760_5518`); the area is the sheet frame.",
        "Godlo arkusza: PL (PL-1992 albo PL-2000), CZ SM5 (np. CTES96) albo kafel "
        "TM33 (np. 760_5518); obszar = rama arkusza",
    ),
    "geometry_description_2": Text(
        "Vector file (SHP or GPKG): the area is the extent of its features (LAZ: of "
        "the whole layer; CZ: of the geometry), as in `elevation download`.",
        "Plik geometrii obszaru (SHP albo GPKG): obszar = obwiednie obiektow (LAZ: "
        "obwiednia calej warstwy; CZ: obwiednia geometrii) - jak w elevation download",
    ),
    "availability_year_description": Text(
        "Only this year (the yearly layer of the GUGiK index). Excludes `min_year` "
        "and `max_year`.",
        "Tylko ten rok (warstwa roczna skorowidza GUGiK); skrot --min-year ROK "
        "--max-year ROK",
    ),
    "availability_min_year_description": Text(
        "Lower bound of the year (inclusive).",
        "Dolna granica roku (wlacznie)",
    ),
    "availability_max_year_description": Text(
        "Upper bound of the year (inclusive).",
        "Gorna granica roku (wlacznie)",
    ),
    "details_description": Text(
        "For every combination: the sheet codes of the incomplete sheets (CZ: sheets "
        "without a file), the area without sheets and every download command",
        "Dla kazdej kombinacji: godla arkuszy niepelnych (CZ: arkuszy bez pliku), "
        "obszar bez arkuszy i wszystkie polecenia pobrania",
    ),
    "json_description": Text(
        "Print the report as JSON (kartograf-availability/1, the same shape as "
        "check_availability)",
        "Wypisz raport jako JSON (kartograf-availability/1, ten sam ksztalt co "
        "check_availability)",
    ),
    "force_description": Text(
        "Skip the metadata cache: query the indexes, PRG and CUZK files again and "
        "overwrite the cache entries.",
        "Pomin cache metadanych (odpytaj skorowidze, PRG i pliki CUZK ponownie, "
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
        "uklady sa dostepne.",
    ),
    "elevation_download_rule_2": Text(
        "Set `vertical_crs` and `resolution` yourself: nothing is guessed.",
        "Podaj `vertical_crs` i `resolution` jawnie: nic nie jest zgadywane.",
    ),
    "elevation_availability_summary": Text(
        "Report the years, grids, CRSs and formats of NMT, NMPT or LAZ for an area",
        "Raport dostepnosci NMT, NMPT i LAZ dla obszaru (bez pobierania)",
    ),
    "elevation_availability_description": Text(
        "Read only. PL: the years, grids, CRSs and formats for which the area has "
        "full sheets (LAZ: tiles) in the GUGiK index; CZ: which SM5 sheets and TM33 "
        "tiles have CUZK files, with date and size. Use it before `elevation "
        "download`; it fetches no data. `country=auto` reports both parts together.",
        "Bez pobierania danych: PL - dla jakich lat, ukladow, rozdzielczosci, ukladow "
        "wysokosci i formatow obszar ma komplet pelnych arkuszy (LAZ: kafli) wg "
        "skorowidza GUGiK (skorowidz WFS i maska ladu PRG; kompletna kombinacja: caly "
        "lad obszaru lezy w arkuszach pelnych, calyArkuszWypelnionyTrescia); CZ - "
        "ktore arkusze SM5 i kafle TM33 obszaru (indeks KladyMapovychListu) maja "
        "pliki CUZK, z data publikacji i rozmiarem z naglowkow HEAD (CUZK nie "
        "publikuje lat nalotu). --country auto: czesci PL i CZ obszaru w jednym "
        "raporcie. Stopka podaje polecenia pobrania kompletnych kombinacji (PL: "
        "najnowszej).",
    ),
    "elevation_availability_rule": Text(
        "Take `year`, `resolution`, `vertical_crs` and `format` of a complete "
        "combination.",
        "Wez `year`, `resolution`, `vertical_crs` i `format` kompletnej kombinacji.",
    ),
    "example_nmt_availability_pl_rectangle": Text(
        "NMT availability in PL for a rectangle",
        "Dostepnosc NMT PL dla prostokata",
    ),
    "example_nmpt_availability_cz_sheet": Text(
        "NMPT availability for a CZ sheet",
        "Dostepnosc NMPT dla arkusza CZ",
    ),
    "example_laz_availability_pl_since_2020_geometry": Text(
        "LAZ availability in PL since 2020 for a geometry",
        "Dostepnosc LAZ PL od 2020 dla geometrii",
    ),
    "elevation_group_summary": Text(
        "Elevation: DTM, DSM and LAZ point clouds (PL and CZ), contours (CZ)",
        "Wysokosci: NMT, NMPT i chmury LAZ (PL i CZ), warstwice (CZ)",
    ),
    "elevation_group_description": Text(
        "Elevation data from GUGiK (PL) and CUZK (CZ): DTM (NMT), DSM (NMPT), LAZ "
        "point clouds and ZABAGED contours (CZ).",
        "Dane wysokosciowe NMT/NMPT i chmury punktow LAZ z GUGiK (PL) i CUZK (CZ) "
        "oraz warstwice ZABAGED (CZ).",
    ),
    "country_description": Text(
        "Country of the source; required with `bbox` or `geometry`, implied by a "
        "sheet code (a given value must agree). `auto` splits the area between PL and "
        "CZ.{country_choices:skip}",
        "Kraj zrodla danych - wymagany z --bbox/--geometry: {country_choices}. Z "
        "--sheet kraj wynika z godla (podana wartosc musi sie z nim zgadzac)",
    ),
    "availability_country_description": Text(
        "Country; required with `bbox` or `geometry`, implied by a sheet code. `auto` "
        "reports the PL and CZ parts together.{countries:skip}",
        "Kraj - wymagany z --bbox/--geometry: {countries}. Z --sheet kraj wynika z "
        "godla",
    ),
    "download_upgrade_description": Text(
        "Fetch newer content when the source signals it (default: information only); "
        "files without a cheap signal stay local (fetch them with --force); with "
        "--plan run the saved plan",
        "Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje (domyslnie tylko "
        "informacja); pliki bez taniego sygnalu zostaja lokalne (pobranie: --force); "
        "z --plan wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file of the task again (sheets, LAZ tiles, cutouts) and refresh "
        "the list of campaigns from GUGiK; the same content = unchanged, other "
        "content = a new version; nothing is overwritten",
        "Pobierz ponownie kazdy plik zadania (arkusze, kafle LAZ, wycinki) i odswiez "
        "liste kampanii z GUGiK; ta sama tresc = bez zmian, inna = nowa wersja; nic "
        "nie jest nadpisywane",
    ),
    "download_plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (JSON kartograf-plan/1, "
        "przy --country auto jeden plan PL i CZ); z --upgrade: wykonaj plan (pozycje "
        "zmienione od planu = blad, bez pobrania)",
    ),
    "elevation_download_description": Text(
        "Fetches the DTM (NMT), DSM (NMPT), LAZ point clouds or CZ contours of GUGiK "
        "(PL) and CUZK (CZ) into the versioned store; `cutout` gives one WCS raster "
        "instead of sheets. Never overwrites: new content is a new version. {note} "
        "Not for imagery (`imagery download`).",
        "Pobierz NMT, NMPT i chmury punktow LAZ z GUGiK (PL) albo CUZK (CZ) do "
        "magazynu wersji. PL: --bbox/--geometry wybiera arkusze/kafle LAZ, --cutout "
        "--horizontal-crs daje wycinek 1 m z WCS GUGiK; NMT 100 m (--resolution 100m) "
        "to pliki XYZ wojewodztw obszaru. CZ: rastry SM5/TM33 z plikow CUZK albo "
        "ImageServer (kafle TM33 DMR 4G i DMP OK z plikow ETRS89/EVRF2007); dla "
        "obszaru rastra --cutout wymagane. LAZ CZ: --model i arkusz SM5/TM33 albo "
        "obszar (arkusze z indeksu), bez --cutout i bez transformacji chmur. "
        "Warstwice CZ (--product contours --format SHP|DGN): ZIP arkusza SM5 1:1, "
        "obszar = arkusze SM5 z indeksu, bez --cutout. {note}",
    ),
}
