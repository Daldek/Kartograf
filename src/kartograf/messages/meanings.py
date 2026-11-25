"""Messages of the area ``meanings``: what each allowed value of an option means.

The ``enum`` of an option in ``kartograf-commands/1`` gives every allowed value its
one-line meaning in English and, on the page of a form (``commands schema --form``),
in Polish (AGI-2.3); ``kartograf.catalog.meanings`` maps the values of each option to
these entries. The name of an entry is ``<option>_<value>``; a value of a regular form
(a grid label, a depth interval, a scale, a year, a release) has one entry per form,
with the value as ``{value}``.
"""

from kartograf.messages import Text

MESSAGES = {
    # ``product``
    "product_nmt": Text(
        "Digital terrain model (bare earth); PL and CZ.",
        "Numeryczny model terenu (sam grunt, bez obiektów); PL i CZ.",
    ),
    "product_nmpt": Text(
        "Digital surface model (with the objects on the ground); PL and CZ.",
        "Numeryczny model pokrycia terenu (z obiektami na powierzchni); PL i CZ.",
    ),
    "product_laz": Text(
        "LIDAR point cloud; PL and CZ.",
        "Chmura punktów LIDAR; PL i CZ.",
    ),
    "product_contours": Text(
        "ZABAGED contours, 2D vector, SM5 sheets, SHP or DGN; CZ.",
        "Warstwice ZABAGED, wektor 2D, arkusze SM5, SHP albo DGN; CZ.",
    ),
    "product_orto": Text("RGB orthophoto; PL and CZ.", "Ortofotomapa RGB; PL i CZ."),
    "product_intensity": Text(
        "LIDAR intensity images, one band, 0.25 m; PL.",
        "Obrazy intensywności LIDAR, jedno pasmo, 0,25 m; PL.",
    ),
    "product_true_orto": Text(
        "True orthophoto of selected cities, 0.05 m; PL.",
        "Prawdziwa ortofotomapa (true orto) wybranych miast, 0,05 m; PL.",
    ),
    "product_oblique_orto": Text(
        "Oblique orthophoto of selected cities; a sheet is four files (n, e, s, w); "
        "PL.",
        "Ortofotomapa ukośna wybranych miast; arkusz to cztery pliki (n, e, s, w); PL.",
    ),
    "product_bdot10k": Text(
        "BDOT10k topographic object database; PL.",
        "Baza danych obiektów topograficznych BDOT10k; PL.",
    ),
    "product_bdoo": Text(
        "BDOO general geographic object database (1:250000); PL.",
        "Baza danych obiektów ogólnogeograficznych BDOO (1:250000); PL.",
    ),
    "product_corine": Text(
        "CORINE Land Cover; EU.",
        "Pokrycie terenu CORINE Land Cover; UE.",
    ),
    "product_zabaged": Text(
        "ZABAGED, the basic geographic database of Czechia (land cover, waters); CZ.",
        "ZABAGED, podstawowa baza danych geograficznych Czech (pokrycie terenu, "
        "wody); CZ.",
    ),
    "product_data50": Text(
        "Data50, the digital geographic model of Czechia at 1:50000; CZ.",
        "Data50, cyfrowy model geograficzny Czech w skali 1:50000; CZ.",
    ),
    "product_data250": Text(
        "Data250, the digital geographic model of Czechia at 1:250000; CZ.",
        "Data250, cyfrowy model geograficzny Czech w skali 1:250000; CZ.",
    ),
    "product_soil": Text(
        "SoilGrids soil property layers (ISRIC); global.",
        "Warstwy właściwości gleb SoilGrids (ISRIC); cały świat.",
    ),
    "product_admin": Text(
        "Administrative and cadastral unit boundaries: PRG (PL), RUIAN (CZ).",
        "Granice jednostek administracyjnych i ewidencyjnych: PRG (PL), RUIAN (CZ).",
    ),
    "product_addresses": Text(
        "PRG address points and streets; PL.",
        "Punkty adresowe i ulice z PRG; PL.",
    ),
    "product_special": Text(
        "PRG special boundaries (44 kinds); PL.",
        "Granice specjalne PRG (44 rodzaje); PL.",
    ),
    "product_geomorphology": Text(
        "Geomorphological units of Czechia, subprovince to part; CZ.",
        "Jednostki geomorfologiczne Czech, od podprowincji do części; CZ.",
    ),
    "product_map": Text(
        "Cadastral map: EGiB (PL) and the cadastral map of Czechia (CZ).",
        "Mapa ewidencyjna EGiB (PL) i mapa katastralna Czech (CZ).",
    ),
    "product_prices": Text(
        "RCN register of real-estate transaction prices; PL.",
        "Rejestr cen nieruchomości RCN (ceny transakcyjne); PL.",
    ),
    "product_buildings": Text(
        "3D building models (CityGML, LoD1 and LoD2); PL.",
        "Modele 3D budynków (CityGML, LoD1 i LoD2); PL.",
    ),
    "product_mesh": Text(
        "3D city mesh models (OBJ with textures); PL.",
        "Siatkowe modele 3D miast (OBJ z teksturami); PL.",
    ),
    "product_trees": Text(
        "3D tree models (CityGML, LoD1); PL.",
        "Modele 3D drzew (CityGML, LoD1); PL.",
    ),
    "product_network": Text(
        "HY-NET hydrographic network (INSPIRE Hydrography - Network); CZ.",
        "Sieć hydrograficzna HY-NET (INSPIRE Hydrografia - sieć); CZ.",
    ),
    "product_pgw": Text(
        "IIaPGW geodatabase of the water management plans (PGW); PL.",
        "Geobaza IIaPGW planów gospodarowania wodami (PGW); PL.",
    ),
    "product_camels": Text(
        "CAMELS-PL catchment boundaries and gauging stations of the gauges of "
        "IMGW-PIB, as published on Zenodo; PL.",
        "Granice zlewni i stacje wodowskazowe IMGW-PIB z CAMELS-PL, jak opublikowano "
        "je w Zenodo; PL.",
    ),
    "product_geographic": Text(
        "Geographic names: PRNG (PL), Geonames (CZ).",
        "Nazwy geograficzne: PRNG (PL), Geonames (CZ).",
    ),
    "product_world": Text(
        "Polish geographic names of the world (PRNG); PL.",
        "Polskie nazwy geograficzne świata (PRNG); PL.",
    ),
    "product_topographic": Text(
        "Topographic maps: BDOT10k visualisations (PL), ZTM (CZ).",
        "Mapy topograficzne: wizualizacje BDOT10k (PL), ZTM (CZ).",
    ),
    "product_control": Text(
        "Geodetic control networks: GUGiK (PL), Bodove pole (CZ).",
        "Osnowy geodezyjne: GUGiK (PL), Bodove pole (CZ).",
    ),
    "product_geoid": Text(
        "Quasi-geoid model: PL-geoid2021 (PL), QGZU-2013 (CZ).",
        "Model quasi-geoidy: PL-geoid2021 (PL), QGZU-2013 (CZ).",
    ),
    # ``country``
    "country_pl": Text("Poland (GUGiK sources).", "Polska (źródła GUGiK)."),
    "country_cz": Text("Czechia (CUZK sources).", "Czechy (źródła CUZK)."),
    "country_auto": Text(
        "Both: the area is split by the bounding boxes of PL and CZ, one file per "
        "country.",
        "Oba kraje: obszar jest dzielony prostokątnymi obwiedniami PL i CZ, osobny "
        "plik dla każdego kraju.",
    ),
    # ``format``
    "format_asc": Text("ESRI ASCII grid.", "Siatka ESRI ASCII."),
    "format_xyz": Text("ASCII XYZ grid, ZIP.", "Siatka ASCII XYZ, ZIP."),
    "format_ascii_nmt": Text(
        "ASCII NMT points X Y Z, ZIP.",
        "Punkty NMT X Y Z w ASCII, ZIP.",
    ),
    "format_tbd": Text(
        "ASCII TBD structure points and lines, ZIP.",
        "Punkty i linie struktury TBD w ASCII, ZIP.",
    ),
    "format_tin": Text("ESRI TIN, ZIP.", "Siatka trójkątów ESRI TIN, ZIP."),
    "format_ttn": Text("Intergraph TTN.", "Siatka trójkątów Intergraph TTN."),
    "format_grd": Text("Intergraph GRD.", "Siatka Intergraph GRD."),
    "format_dxf": Text(
        "DXF (contours; CZ cadastral map).",
        "DXF (warstwice; mapa katastralna CZ).",
    ),
    "format_dgn": Text(
        "DGN (contours, cadastral map, topographic map).",
        "DGN (warstwice, mapa katastralna, mapa topograficzna).",
    ),
    "format_shp": Text("Shapefile.", "Format Shapefile."),
    "format_gpkg": Text("GeoPackage.", "Format GeoPackage."),
    "format_gml": Text("GML.", "Format GML."),
    "format_tiff": Text("GeoTIFF.", "Format GeoTIFF."),
    "format_pdf": Text("PDF.", "Dokument PDF."),
    "format_xlsx": Text("Excel workbook.", "Skoroszyt programu Excel."),
    "format_fgdb": Text("ESRI file geodatabase.", "Plikowa geobaza ESRI."),
    "format_vfk": Text(
        "VFK exchange format of the Czech cadastre.",
        "Format wymiany VFK czeskiego katastru.",
    ),
    "format_agents": Text(
        "AGENTS.md: the full guide for agents.",
        "AGENTS.md: pełny przewodnik dla agentów.",
    ),
    "format_llms": Text(
        "llms.txt: the short guide in the llmstxt.org layout.",
        "llms.txt: krótki przewodnik w układzie llmstxt.org.",
    ),
    "format_agents_md_block": Text(
        "The compact block for the AGENTS.md of a repository that uses Kartograf.",
        "Zwięzły blok do AGENTS.md repozytorium, które korzysta z Kartografa.",
    ),
    # ``sheet_system``
    "sheet_system_1992": Text(
        "PL-1992 sheets (1:10000 and coarser).",
        "Arkusze PL-1992 (1:10000 i mniej szczegółowe).",
    ),
    "sheet_system_2000": Text(
        "PL-2000 sheets (zones EPSG:2176-2179).",
        "Arkusze PL-2000 (strefy EPSG:2176-2179).",
    ),
    "sheet_system_sjtsk": Text(
        "ZTM sheets in S-JTSK.",
        "Arkusze ZTM w układzie S-JTSK.",
    ),
    "sheet_system_etrs89": Text(
        "ZTM sheets in ETRS89.",
        "Arkusze ZTM w układzie ETRS89.",
    ),
    # ``lang``
    "lang_pl": Text(
        "Polish text for people (the default).",
        "Teksty dla ludzi po polsku (domyślnie).",
    ),
    "lang_en": Text("English text for people.", "Teksty dla ludzi po angielsku."),
    # ``bbox_crs``
    "bbox_crs_epsg_2176": Text("PL-2000 zone 5.", "PL-2000, strefa 5."),
    "bbox_crs_epsg_2177": Text("PL-2000 zone 6.", "PL-2000, strefa 6."),
    "bbox_crs_epsg_2178": Text("PL-2000 zone 7.", "PL-2000, strefa 7."),
    "bbox_crs_epsg_2179": Text("PL-2000 zone 8.", "PL-2000, strefa 8."),
    "bbox_crs_epsg_2180": Text(
        "PL-1992 (ETRS89 / Poland CS92).",
        "Układ PL-1992 (ETRS89 / Poland CS92).",
    ),
    "bbox_crs_epsg_3045": Text("ETRS89 / UTM zone 33N.", "ETRS89 / UTM, strefa 33N."),
    "bbox_crs_epsg_4326": Text(
        "WGS 84 geographic coordinates, in degrees.",
        "Współrzędne geograficzne WGS 84, w stopniach.",
    ),
    "bbox_crs_epsg_5514": Text(
        "S-JTSK / Krovak East North (CZ).",
        "Układ S-JTSK / Krovak East North (CZ).",
    ),
    # ``vertical_crs``
    "vertical_crs_evrf2007": Text(
        "European Vertical Reference Frame 2007: the current PL height system "
        "(PL-EVRF2007-NH) and the native one of CZ TM33 files.",
        "Europejski układ wysokości EVRF2007: obowiązujący układ wysokości PL "
        "(PL-EVRF2007-NH) i natywny układ plików CZ TM33.",
    ),
    "vertical_crs_kron86": Text(
        "Kronstadt 86: the historical PL height system (PL-KRON86-NH).",
        "Kronsztadt 86: historyczny układ wysokości PL (PL-KRON86-NH).",
    ),
    "vertical_crs_bpv": Text(
        "Baltic after adjustment: native for CZ S-JTSK, SM5 and ImageServer data.",
        "Bałtycki po wyrównaniu: natywny dla danych CZ w S-JTSK, SM5 i ImageServer.",
    ),
    # ``model``
    "model_dmr5g": Text("Terrain model DMR 5G.", "Model terenu DMR 5G."),
    "model_dmr4g": Text(
        "Terrain model on a 5 m grid (DMR 4G).",
        "Model terenu w siatce 5 m (DMR 4G).",
    ),
    "model_dmp1g": Text("Surface model DMP 1G.", "Model powierzchni DMP 1G."),
    "model_dmpok": Text(
        "Surface model from image correlation (DMP OK).",
        "Model powierzchni z korelacji obrazów (DMP OK).",
    ),
    # ``coverage``
    "coverage_standard": Text(
        "The newest available orthophotos.",
        "Najnowsze dostępne ortofotomapy.",
    ),
    "coverage_high": Text(
        "Orthophotos with a pixel of 10 cm or finer.",
        "Ortofotomapy z pikselem 10 cm albo mniejszym.",
    ),
    # ``direction``
    "direction_n": Text("North.", "Północ."),
    "direction_e": Text("East.", "Wschód."),
    "direction_s": Text("South.", "Południe."),
    "direction_w": Text("West.", "Zachód."),
    # ``level``
    "level_wojewodztwo": Text("Voivodeship (PL).", "Województwo (PL)."),
    "level_powiat": Text("County (PL).", "Powiat (PL)."),
    "level_gmina": Text("Municipality (PL).", "Gmina (PL)."),
    "level_jednostka_ewidencyjna": Text(
        "Cadastral unit (PL).",
        "Jednostka ewidencyjna (PL).",
    ),
    "level_obreb": Text("Cadastral precinct (PL).", "Obręb ewidencyjny (PL)."),
    "level_kraj": Text("Region, kraj (CZ).", "Kraj, odpowiednik województwa (CZ)."),
    "level_okres": Text("District, okres (CZ).", "Okres, odpowiednik powiatu (CZ)."),
    "level_obec": Text("Municipality, obec (CZ).", "Obec, odpowiednik gminy (CZ)."),
    "level_katastralni_uzemi": Text(
        "Cadastral area, katastralni uzemi (CZ).",
        "Obszar katastralny, katastralni uzemi (CZ).",
    ),
    "level_subprovincie": Text(
        "Geomorphological subprovince (CZ).",
        "Podprowincja geomorfologiczna (CZ).",
    ),
    "level_oblast": Text(
        "Geomorphological area, oblast (CZ).",
        "Obszar geomorfologiczny, oblast (CZ).",
    ),
    "level_celek": Text(
        "Geomorphological unit, celek (CZ).",
        "Jednostka geomorfologiczna, celek (CZ).",
    ),
    "level_podcelek": Text(
        "Geomorphological subunit, podcelek (CZ).",
        "Podjednostka geomorfologiczna, podcelek (CZ).",
    ),
    "level_okrsek": Text(
        "Geomorphological district, okrsek (CZ).",
        "Okręg geomorfologiczny, okrsek (CZ).",
    ),
    "level_podokrsek": Text(
        "Geomorphological subdistrict, podokrsek (CZ).",
        "Podokręg geomorfologiczny, podokrsek (CZ).",
    ),
    "level_cast": Text(
        "Geomorphological part, cast (CZ).",
        "Część geomorfologiczna, cast (CZ).",
    ),
    # ``lod``
    "lod_1": Text("Level of detail 1 (LoD1).", "Poziom szczegółowości 1 (LoD1)."),
    "lod_2": Text("Level of detail 2 (LoD2).", "Poziom szczegółowości 2 (LoD2)."),
    # ``network``
    "network_horizontal": Text("Horizontal control network.", "Osnowa pozioma."),
    "network_vertical": Text(
        "Vertical (height) control network.",
        "Osnowa wysokościowa.",
    ),
    "network_gravity": Text("Gravimetric control network.", "Osnowa grawimetryczna."),
    "network_magnetic": Text("Magnetic control network.", "Osnowa magnetyczna."),
    "network_archive_1942": Text(
        "Archive catalogues of the control points, 1942 (sheets 1:100000).",
        "Archiwalne katalogi punktów osnowy, 1942 (arkusze 1:100000).",
    ),
    "network_archive_kronsztadt60": Text(
        "Archive catalogues of the control points, Kronstadt 60 (sheets 1:100000).",
        "Archiwalne katalogi punktów osnowy, Kronsztadt 60 (arkusze 1:100000).",
    ),
    "network_gnss": Text("GNSS control points (CZ).", "Punkty osnowy GNSS (CZ)."),
    "network_densification": Text(
        "Densification control network (CZ).",
        "Osnowa zagęszczająca (CZ).",
    ),
    "network_horizontal_detailed": Text(
        "Detailed horizontal control network (CZ).",
        "Szczegółowa osnowa pozioma (CZ).",
    ),
    "network_vertical_detailed": Text(
        "Detailed vertical control network (CZ).",
        "Szczegółowa osnowa wysokościowa (CZ).",
    ),
    # ``property``
    "property_bdod": Text(
        "Bulk density of the fine earth; file unit cg/cm3 (kg/dm3 = value / 100).",
        "Gęstość objętościowa części ziemistych; jednostka pliku cg/cm3 (kg/dm3 = "
        "wartość / 100).",
    ),
    "property_cec": Text(
        "Cation exchange capacity; file unit mmol(c)/kg (cmol(c)/kg = value / 10).",
        "Pojemność sorpcyjna (wymiany kationów); jednostka pliku mmol(c)/kg "
        "(cmol(c)/kg = wartość / 10).",
    ),
    "property_cfvo": Text(
        "Coarse fragments by volume; file unit cm3/dm3 (cm3/100cm3 = value / 10).",
        "Objętościowy udział frakcji szkieletowej; jednostka pliku cm3/dm3 "
        "(cm3/100cm3 = wartość / 10).",
    ),
    "property_clay": Text(
        "Clay content; file unit g/kg (percent = value / 10).",
        "Zawartość iłu; jednostka pliku g/kg (procent = wartość / 10).",
    ),
    "property_nitrogen": Text(
        "Total nitrogen; file unit cg/kg (g/kg = value / 100).",
        "Azot całkowity; jednostka pliku cg/kg (g/kg = wartość / 100).",
    ),
    "property_ocd": Text(
        "Organic carbon density; file unit hg/m3 (kg/m3 = value / 10).",
        "Gęstość węgla organicznego; jednostka pliku hg/m3 (kg/m3 = wartość / 10).",
    ),
    "property_ocs": Text(
        "Organic carbon stock, depth 0-30cm only; file unit t/ha (kg/m2 = value / 10).",
        "Zasób węgla organicznego, tylko głębokość 0-30cm; jednostka pliku t/ha "
        "(kg/m2 = wartość / 10).",
    ),
    "property_phh2o": Text(
        "Soil pH in water; the file holds pH x 10 (pH = value / 10).",
        "Odczyn gleby (pH w wodzie); plik zawiera pH x 10 (pH = wartość / 10).",
    ),
    "property_sand": Text(
        "Sand content; file unit g/kg (percent = value / 10).",
        "Zawartość piasku; jednostka pliku g/kg (procent = wartość / 10).",
    ),
    "property_silt": Text(
        "Silt content; file unit g/kg (percent = value / 10).",
        "Zawartość pyłu; jednostka pliku g/kg (procent = wartość / 10).",
    ),
    "property_soc": Text(
        "Soil organic carbon; file unit dg/kg (g/kg = value / 10).",
        "Węgiel organiczny gleby; jednostka pliku dg/kg (g/kg = wartość / 10).",
    ),
    # ``stat``
    "stat_mean": Text("Mean.", "Średnia."),
    "stat_q0_05": Text("5th percentile.", "5. percentyl."),
    "stat_q0_5": Text("Median.", "Mediana."),
    "stat_q0_95": Text("95th percentile.", "95. percentyl."),
    "stat_uncertainty": Text(
        "Prediction uncertainty: the file holds 10 * (Q0.95 - Q0.05) / Q0.5, unitless.",
        "Niepewność predykcji: plik zawiera 10 * (Q0.95 - Q0.05) / Q0.5, bez "
        "jednostki.",
    ),
    # ``depth_rule``
    "depth_rule_least_permeable": Text(
        "Classify the SoilGrids layers 0-5cm to 60-100cm and take, per cell, the "
        "group of the layer with the lowest saturated hydraulic conductivity of its "
        "USDA texture class (Rawls, Brakensiek & Saxton 1982).",
        "Klasyfikuje warstwy SoilGrids od 0-5cm do 60-100cm i bierze w każdej "
        "komórce grupę warstwy o najmniejszej przewodności hydraulicznej w stanie "
        "nasycenia jej klasy uziarnienia USDA (Rawls, Brakensiek i Saxton 1982).",
    ),
    # ``update``
    "update_upgrade": Text(
        "Fetch newer content when the source signals it.",
        "Pobiera nowszą treść, gdy źródło ją sygnalizuje.",
    ),
    "update_force": Text(
        "Fetch every file again; nothing is overwritten.",
        "Pobiera każdy plik ponownie; nic nie jest nadpisywane.",
    ),
    # ``shell``
    "shell_bash": Text(
        "A bash script (Linux, macOS; Git Bash or WSL on Windows).",
        "Skrypt bash (Linux, macOS; Git Bash albo WSL w Windows).",
    ),
    "shell_powershell": Text(
        "A PowerShell script, in ASCII (Windows PowerShell 5.1 or PowerShell 7).",
        "Skrypt PowerShell, w ASCII (Windows PowerShell 5.1 albo PowerShell 7).",
    ),
    # values of a regular form
    "resolution": Text(
        "Cell or pixel size {value} (metres).",
        "Rozmiar komórki albo piksela {value} (metry).",
    ),
    "depth": Text(
        "Depth interval {value} below the surface.",
        "Przedział głębokości {value} poniżej powierzchni.",
    ),
    "scale": Text(
        "Sheets or maps at the scale {value}.",
        "Arkusze albo mapy w skali {value}.",
    ),
    "year": Text("Year {value}.", "Rok {value}."),
    "version": Text(
        "Release {value} of the published data set (CAMELS-PL), as its publisher "
        "numbers it.",
        "Wydanie {value} opublikowanego zbioru danych (CAMELS-PL), w numeracji "
        "wydawcy.",
    ),
}
