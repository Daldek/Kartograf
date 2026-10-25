"""Messages of the command catalog: the declarations of ``soil``."""

from kartograf.messages import Text

MESSAGES = {
    "rule_give_exactly_one_area_sheet_bbox_geometry": Text(
        "Give exactly one area: --sheet, --bbox or --geometry",
        "Podaj dokladnie jeden obszar: --sheet, --bbox albo --geometry",
    ),
    "check_description": Text(
        "Compares the local versions with the SoilGrids release.",
        "Porownaj lokalne wersje z wydaniem SoilGrids bez pobierania",
    ),
    "property_description": Text(
        "SoilGrids property (required). Values stay in the SoilGrids units of the "
        "file; the meaning of each property gives its unit and "
        "conversion.{described:skip}",
        "Wymagane: {described:join(; )}",
    ),
    "stat_description": Text(
        "Statistic of the prediction (required).{described:skip}",
        "Wymagane: {described:join(; )}",
    ),
    "check_description_2": Text(
        "Compares the clay, sand and silt inputs with the SoilGrids release and the "
        "HSG with its inputs; nothing is computed.",
        "Porownaj wejscia clay/sand/silt z wydaniem SoilGrids i HSG z wejsciami bez "
        "pobierania i bez liczenia",
    ),
    "summary_description": Text(
        "Add the HSG summary after the calculation: the share and area of the groups "
        "A-D and of the cells without data.",
        "Wypisz podsumowanie HSG po obliczeniu: udzial i powierzchnia grup A-D oraz "
        "brak danych",
    ),
    "soil_download_summary": Text(
        "Download one SoilGrids layer (property, depth, statistic) for an area",
        "Pobierz warstwe SoilGrids (wlasciwosc, glebokosc, statystyka)",
    ),
    "soil_download_rule": Text(
        "Take `property`, `depth` and `stat` from `soil list-layers`.",
        "Wez `property`, `depth` i `stat` z `soil list-layers`.",
    ),
    "example_clay_content_0_5_cm_rectangle": Text(
        "Clay content at 0-5 cm for a rectangle",
        "Zawartosc ilu 0-5 cm dla prostokata",
    ),
    "example_organic_carbon_15_30_cm_median_sheet": Text(
        "Organic carbon at 15-30 cm (median) for a sheet",
        "Wegiel organiczny 15-30 cm (mediana) dla arkusza",
    ),
    "soil_hsg_summary": Text(
        "Compute hydrologic soil groups (HSG) from SoilGrids texture for an area",
        "Oblicz grupy hydrologiczne gleb (HSG) z uziarnienia",
    ),
    "soil_hsg_description": Text(
        "Fetches the clay, sand and silt layers (statistic `mean`) of one depth for "
        "an area and computes the groups A-D for the SCS-CN method. Inputs and the "
        "HSG raster are stored as versions; the HSG is recomputed only when the "
        "inputs change. With `output_dir` only the HSG raster is written, as a plain "
        "file. For one SoilGrids layer use `soil download`.",
        "Pobierz clay (il), sand (piasek), silt (pyl) z SoilGrids dla wybranej "
        "glebokosci; uzyj statystyki mean (srednia) i oblicz grupy hydrologiczne HSG "
        "dla metody SCS-CN. Z --output-dir zapisuje tylko raster HSG, jako zwykly "
        "plik.",
    ),
    "soil_hsg_rule": Text(
        "Give `depth`; add `summary` for the share and area of each group.",
        "Podaj `depth`; `summary` dodaje udzial i powierzchnie kazdej grupy.",
    ),
    "example_hsg_rectangle_summary": Text(
        "HSG for a rectangle with the summary",
        "HSG dla prostokata z podsumowaniem",
    ),
    "soil_list_layers_summary": Text(
        "List the SoilGrids properties, depths and statistics (offline)",
        "Wypisz wlasciwosci, glebokosci i statystyki SoilGrids",
    ),
    "soil_list_layers_description": Text(
        "Lists the values of `property`, `depth` and `stat` of `soil download` with "
        "the units of each property. Use it to choose a layer.",
        "Wypisz wlasciwosci, glebokosci i statystyki SoilGrids (wartosci --property, "
        "--depth, --stat; bez sieci)",
    ),
    "group_description": Text(
        "Command group (here: soil); list_layers serves landcover and soil",
        "Grupa komend (tu: soil); list_layers obsluguje landcover i soil",
    ),
    "example_soilgrids_properties_depths_statistics": Text(
        "The SoilGrids properties, depths and statistics",
        "Wlasciwosci, glebokosci i statystyki SoilGrids",
    ),
    "soil_group_summary": Text(
        "Soil: SoilGrids and hydrologic soil groups (HSG)",
        "Gleby: SoilGrids i grupy hydrologiczne HSG",
    ),
    "soil_group_description": Text(
        "Soil in the versioned store: the SoilGrids property layers (ISRIC, 250 m) "
        "and the hydrologic soil groups (HSG) computed from the texture.",
        "Gleby: warstwy wlasciwosci SoilGrids (ISRIC, 250 m) i grupy hydrologiczne "
        "HSG obliczone z uziarnienia, w magazynie wersji.",
    ),
    "depth_description": Text(
        "Depth interval below the surface (required); `0-30cm` only for "
        "`ocs`.{depths:skip}",
        "Wymagane: {depths}",
    ),
    "depths_text": Text(
        "{names:join} ({explanations:join}{note})",
        "{names:join} ({explanations:join}{note})",
    ),
    "depths_ocs_note": Text("; 0-30cm only for ocs", "; 0-30cm tylko dla ocs"),
    "described_item": Text("{value}: {text}", "{value}: {text}"),
    "download_upgrade_description": Text(
        "Fetch a newer release of SoilGrids (default: information only); with --plan "
        "run the saved plan",
        "Pobierz nowsze wydanie SoilGrids (domyslnie tylko informacja); z --plan "
        "wykonaj zapisany plan",
    ),
    "download_force_description": Text(
        "Fetch every file again; the same content = unchanged, other content = a new "
        "version",
        "Pobierz ponownie kazdy plik; ta sama tresc = bez zmian, inna = nowa wersja",
    ),
    "plan_description": Text(
        "{common}",
        "{common:skip}Z --check: zapisz plan aktualizacji (kartograf-plan/1); z "
        "--upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
    ),
    "hsg_upgrade_description": Text(
        "Fetch a newer release of the inputs (default: information only); HSG is "
        "computed only for a new set of inputs; with --plan run the plan",
        "Pobierz nowsze wydanie wejsc (domyslnie tylko informacja); HSG liczony tylko "
        "dla nowego zestawu wejsc; z --plan wykonaj plan",
    ),
    "hsg_force_description": Text(
        "Fetch the inputs again; HSG is computed only when the content of the inputs "
        "changed (otherwise reused)",
        "Pobierz ponownie wejscia; HSG liczony tylko, gdy tresc wejsc sie zmienila "
        "(inaczej uzyta ponownie)",
    ),
    "soil_download_description": Text(
        "Fetches one SoilGrids layer (ISRIC, 250 m) for an area given by `sheet`, "
        "`bbox` or `geometry`; values keep the SoilGrids units. For hydrologic soil "
        "groups use `soil hsg`. Never overwrites: new content is a new version. {note}",
        "Pobierz jedna warstwe SoilGrids (--property, --depth, --stat; lista: "
        "kartograf soil list-layers) dla jednego obszaru: --sheet, --bbox albo "
        "--geometry. {note}",
    ),
}
