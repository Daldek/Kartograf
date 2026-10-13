# Katalog produktow GUGiK i CUZK - inwentaryzacja z probkami (2026-10-13)

**Cel:** kompletna lista produktow udostepnianych przez GUGiK (PL) i CUZK
(CZ) z klasyfikacja wzgledem Kartografa (obslugiwany / do dodania / poza
zakresem / do ponownej weryfikacji) i probka danych dla kazdego produktu
jako dowodem dostepnosci. Wejscie do specu
`docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`.

**Stan kodu:** `develop`, 0.8.0-dev (`kartograf/sources/registry.py`).
**Log dowodow:** `probki.md` (ten katalog) - kazda probka z URL-em,
rozmiarem, sha256, wynikiem `gdalinfo`/`ogrinfo`/listy ZIP i czasem.
Pliki probek leza poza repo: `<katalog-probek>/probki/<id>/`
(STANDARDS 6.4).

## 1. Metoda

- Lista produktow pochodzi z oficjalnych katalogow (odczyt 2026-10-13,
  kopie w `<katalog-probek>/catalogs/`):
  - GUGiK: 23 strony `https://www.geoportal.gov.pl/pl/dane/...` (sekcja
    "Dane"), strony uslug `https://www.geoportal.gov.pl/pl/usluga/...`
    (WFS, WCS, ATOM, OGC API Features, INSPIRE), oraz **32 uslugi WMS
    modulu "Pobierz dane"** odczytane z ruchu sieciowego aplikacji
    `https://mapy.geoportal.gov.pl/imapnext/imap/index.html?moduleId=modulPD`
    (to one podaja linki do plikow przez `GetFeatureInfo`); dla kazdej
    warstwy wykonano `GetFeatureInfo` w punkcie Krakow (EPSG:2180
    E 566500, N 244500; powiat 1261) i zebrano linki do plikow.
  - CUZK: `https://atom.cuzk.gov.cz/getcapabilities.ashx` - **114 uslug
    ATOM** (pelna lista stahovacich sluzeb), katalog ArcGIS
    `ags.cuzk.gov.cz/arcgis{,1,2}/rest/services` (73 uslugi) i dokument
    `https://geoportal.cuzk.gov.cz/Dokumenty/Formy_poskytovani_dat_ZU.pdf`
    (formy i odplatnosc kazdego produktu ZU). Dla kazdej uslugi ATOM
    pobrano feed uslugi, feed zbioru (arkusz `CTES96`/kafel `760_5518`/KU
    `623164`/obec `598933`, inaczej pierwszy) i pierwszy plik danych.
- Probka: maly obszar (arkusz/kafel/powiat/KU/bbox). Plik > 100 MB:
  pierwsze 1 MiB przez `Range` + pelny rozmiar z naglowka (CUZK `openzu`
  obsluguje `Range`); wyjatek: GUGiK `opendata.geoportal.gov.pl`
  **ignoruje `Range`** (zwraca 200 i cala tresc), a TIFF ma IFD na koncu
  pliku - dlatego ortofotomapy pobrano w calosci (1,1 GB) i zweryfikowano
  `gdalinfo`.
- Produkty obslugiwane: dodatkowo probka przez CLI Kartografa
  (`probki.md`, wiersze `(CLI)`): arkusz NMT 1 m i 5 m, wycinek NMPT,
  kafle LAZ, BDOT10k (powiat 1261, PTWP+SWRS), DMR 4G `CTES96`, wycinek
  DMR 5G.
- Odpowiedz HTML / wyjatek OGC / pusty plik = porazka (nie probka).
  Porazka uslugi: 3 proby (odstepy 5 s, 30 s, 90 s), potem ponowna seria
  po >= 10 min. Brak skutku = `do ponownej weryfikacji`, nie odrzucenie.
- Odrzucenie (`poza zakresem`) tylko z powodu merytorycznego: dane
  odplatne/na wniosek, wylacznie podglad (brak uslugi pobierania), dane
  nieprzestrzenne, duplikat innego zbioru w schemacie INSPIRE, inny
  producent.

**Wynik:** 212 probek z weryfikacja tresci, 4 zbiory CUZK
`do ponownej weryfikacji`. Probek nie ma dla produktow odplatnych
(udostepnianych na wniosek) - pobranie wymaga oplaty, dowodem jest cytat
z katalogu producenta.

## 2. Najwazniejsze ustalenia

1. **NMT/NMPT 0,5 m to dzis glowna produkcja GUGiK.** Skorowidz WFS
   `NumerycznyModelTerenuEVRF2007` warstwa `SkorowidzNMT2025` (pierwsze
   3000 rekordow): 787 x `0.50 m`, 2213 x `5.00 m`, 0 x `1.00 m`;
   `SkorowidzNMPT2025`: 2180 x `0.50 m`, 820 x `1.00 m`. Arkusz NMPT 2025
   `M-34-64-D-d-1-2` ma piksel 0,5 m (4528x4686, 148 MB). Kartograf
   obsluguje tylko 1 m i 5 m - nowe loty sa dla niego niewidoczne
   (backlog "NMT 0,5 m" potwierdzony).
2. **Ortofotomapa 2025 ma piksel 5 cm i 1,1 GB na arkusz 1:10000**
   (`83139_1483338_M-34-64-D-d-1-2.tif`, 45282x46866 px). Bez `Range` po
   stronie serwera nie da sie pobrac fragmentu - wycinek orto tylko z WCS.
3. **Nowe zbiory bezplatne GUGiK** (od 2025-2026): EGiB dzialki i budynki
   jako paczki GPKG (powiat/woj.) i GeoParquet (woj./kraj) w
   `opendata.geoportal.gov.pl/InneDane/latest_exports/eziudp_wfs/`,
   zbiorcza WFS EGiB, Rejestr Cen Nieruchomosci (bez oplat od 02.2026),
   modele 3D budynkow LoD1 (2019-2024) i LoD2, modele 3D drzew, modele
   siatkowe 3D (OBJ), obrazy intensywnosci, ortofotomapa ukosna, true
   ortho, NMT 100 m (ATOM), wizualizacje BDOT10k 1:10000-1:100000
   (GeoTIFF/PDF), archiwum BDOT10k 2014-2025 (GML/SHP per powiat), BDOO
   2015 i 2021-2026.
4. **CUZK publikuje wszystko w ATOM** (114 uslug), w tym LAZ DMR 5G/4G,
   DMP 1G, DMP OK (TIFF 0,5 m i LAZ), ortofoto JPEG 0,125 m (SM5),
   ZABAGED krajowo (GPKG 5,8 GB / FGDB 4,0 GB), RUIAN, katastralni mapa per
   KU (SHP/DXF/DGN/VFK), ZTM 1:5000-1:250000 (TIFF/DGN/PDF/SHP). URL-e
   sa przewidywalne (`openzu.cuzk.gov.cz/opendata/<PRODUKT>/epsg-<5514|3045>/<arkusz>.zip`).
5. **Pulapki uslug** (wplyw na implementacje):
   - GUGiK `opendata` bez `Range` (patrz wyzej).
   - GUGiK WFS PRNG: typ `ms:Wsie` z przykladu na stronie katalogu daje
     HTTP 400; aktualne typy to `ms:M1_UrzedoweNazwyMiejscowosci`,
     `ms:M2_...`, `ms:O1_...`-`ms:O3_...` (przyklad w katalogu nieaktualny).
   - GUGiK WFS EGiB (`.../PZGIK/EGIB/WFS/UslugaZbiorcza`) bez parametrow
     zwraca strone HTML RCN; z `SERVICE=WFS` dziala (`ms:dzialki`,
     `ms:budynki`).
   - GUGiK WCS `POLSA/WCS/LandCover`: pokrycie z przykladu katalogu
     (`Land_use_classification`) nie istnieje; sa `..._2019`-`..._2023`.
   - GUGiK ATOM (`mapy.geoportal.gov.pl/wss/service/ATOM/...`) bywa wolny:
     `NazwyGeograficzne` - timeout 120 s (15:3x UTC), ponowienie 16:22 OK.
   - CUZK ArcGIS WFS z `urn:ogc:def:crs:EPSG::5514`: BBOX w kolejnosci
     X,Y (ujemne E, potem N), mimo osi EPSG; odwrotna kolejnosc daje 0
     obiektow bez bledu.
   - CUZK: 4 feedy ATOM RUIAN wskazuja usuniete pliki (HTTP 404, sekcja 5).
   - Probka `StatystykiSieciWodnej` (WFS statystyk BDOT10k) zwraca 0
     obiektow dla `ms:rzeki_woj` i `ms:rzeki_pow` - usluga pochodna, poza
     zakresem.

## 3. GUGiK (PL)

Kolumna "Probki" = identyfikatory z `probki.md`. Priorytet dla `do dodania`:
W - wysoki (dane wejsciowe hydrologii/Hydrografa lub luka w obslugiwanym
produkcie), S - sredni, N - niski.

| ID | Produkt | Warianty | Kanal(y) pobierania | Ziarno | Status | Uzasadnienie | Probki |
|---|---|---|---|---|---|---|---|
| `pl.gugik.nmt_1m` | NMT 1 m | EVRF2007, KRON86; ASC; PL-1992/PL-2000 | WMS/WFS skorowidz -> `opendata` ASC; WCS (ASC/TIFF) | arkusz 1:10000 (PL-2000 1:500-1:5000); bbox | obslugiwany | arkusze, kampanie, wycinek WCS z maska PRG | `pl.gugik.nmt_1m_sheet`, `pl.gugik.nmt_wcs`, `pl.gugik.nmt_1m (CLI)` |
| `pl.gugik.nmt_5m` | NMT 5 m | EVRF2007; ASC | WMS `SheetsGrid5mEVRF2007` | arkusz | obslugiwany | - | `pl.gugik.nmt_5m`, `pl.gugik.nmt_5m (CLI)` |
| `pl.gugik.nmt_0_5m` | NMT 0,5 m | EVRF2007; ASC | te same skorowidze (`char_przestrz = 0.50 m`) | arkusz | do dodania (W) | nowe loty 2024-2026 wylacznie 0,5 m (pkt 2.1) | `pl.gugik.nmt_0_5m` |
| `pl.gugik.nmt_100m` | NMT siatka 100 m | EVRF2007; TXT XYZ | ATOM `GUGIK_NMT100` | wojewodztwo | do dodania (N) | przeglad calego kraju / zlewnie duze | `pl.gugik.nmt_100m` |
| `pl.gugik.nmpt` | NMPT | 1 m i 0,5 m; EVRF2007, KRON86; ASC | WMS/WFS skorowidz; WCS | arkusz; bbox | obslugiwany czesciowo | brak 0,5 m (73% rekordow 2025) | `pl.gugik.nmpt_1m_sheet`, `pl.gugik.nmpt_0_5m`, `pl.gugik.nmpt_wcs`, `pl.gugik.nmpt (CLI --cutout)` |
| `pl.gugik.laz` | Chmury punktow LIDAR | EVRF2007, KRON86; LAZ | WFS skorowidz | kafel | obslugiwany | - | `pl.gugik.laz`, `pl.gugik.laz (CLI)` |
| `pl.gugik.intensity` | Obrazy intensywnosci | GeoTIFF 0,25 m, 1 pasmo | WMS/WFS `SkorowidzeObrazowIntensywnosci` | arkusz | do dodania (N) | pochodna ALS, interpretacja pokrycia | `pl.gugik.intensity` |
| `pl.gugik.orto` | Ortofotomapa (arkusze) | RGB/CIR/B-W; piksel 5 cm-1 m; wszystkie kampanie | WMS skorowidze (wg aktualnosci/rozdzielczosci), WFS | arkusz | obslugiwany | CIR/B-W tylko w API (CLI: RGB) | `pl.gugik.orto`, `pl.gugik.orto_by_resolution` |
| `pl.gugik.orto_wcs` | Ortofotomapa - wycinek WCS | Standard, High Resolution; GeoTIFF RGB | WCS `ORTO/WCS/StandardResolution`, `HighResolution` | bbox | obslugiwany czesciowo | tylko `provider.download_bbox` poza magazynem (D27); brak wycinka w magazynie | `pl.gugik.orto_wcs_standard`, `pl.gugik.orto_wcs_high` |
| `pl.gugik.orto_true` | Prawdziwa ortofotomapa | GeoTIFF RGB | WCS `TrueOrto`; WMS/WFS skorowidz | bbox; arkusz | do dodania (N) | miasta, bez przesuniec budynkow | `pl.gugik.orto_true` |
| `pl.gugik.orto_oblique` | Ortofotomapa ukosna | 4 kierunki N/E/S/W; GeoTIFF | WMS/WFS skorowidz | arkusz PL-2000 | do dodania (N) | 300 MB/arkusz | `pl.gugik.orto_oblique` |
| `pl.gugik.aerial_photos` | Zdjecia lotnicze (pionowe, ukosne) | 1951-2026 | WMS skorowidze (miniatury); pelne - portal PZGiK | zdjecie | poza zakresem | pelne zdjecia odplatnie na wniosek (art. 40a); miniatura JPG 283x212 bez georeferencji | `pl.gugik.aerial_photo_thumbs` |
| `pl.gugik.photogrammetry_aux` | Linie mozaikowania, aerotriangulacja, fotopunkty | SHZ/ZIP/WFS | WMS/WFS skorowidze | blok/zgloszenie | poza zakresem | dane pomocnicze procesu fotogrametrycznego, nie produkt analityczny | `pl.gugik.mosaic_lines`, `pl.gugik.aerotriangulation`, `pl.gugik.photo_control_points` |
| `pl.gugik.mesh_3d` | Modele siatkowe 3D | OBJ + JPG | WMS/WFS `ModeleSiatkowe3D` | kafel | do dodania (N) | 3D miast; poza hydrologia | `pl.gugik.mesh_3d` |
| `pl.gugik.buildings_3d` | Modele 3D budynkow | LoD1 2019/2021/2022/2024, LoD2 2017; CityGML | WMS `FOTO/WMS/ModeleBudynkow3D` (link per powiat) | powiat, kraj | do dodania (S) | wysokosci zabudowy (szorstkosc, NMPT) | `pl.gugik.buildings_3d_lod1`, `pl.gugik.buildings_3d_lod2` |
| `pl.gugik.trees_3d` | Modele 3D drzew | LoD1 2023; ZIP | WMS `ModeleDrzew3D` | powiat | do dodania (N) | 218 MB/powiat | `pl.gugik.trees_3d` |
| `pl.gugik.bdot10k` | BDOT10k | GML, GPKG, SHP (schemat 2021); powiat, woj., kraj (+ GeoParquet krajowe) | WMS/WFS `PobieranieBDOT10k`; ATOM per woj. | powiat | obslugiwany | powiat GPKG/SHP; GML i paczki woj./kraj nieuzywane | `pl.gugik.bdot10k_raw`, `pl.gugik.bdot10k (CLI)`, `pl.gugik.atom_bdot10k_woj` |
| `pl.gugik.bdot10k_archive` | BDOT10k archiwalny | 2014-2025; GML, SHP | WMS `BDOT10k/WMS/DaneArchiwalne` | powiat x rok | do dodania (S) | analizy zmian pokrycia (CN w czasie) | `pl.gugik.bdot10k_archive` |
| `pl.gugik.bdot10k_maps` | Mapy topograficzne z BDOT10k | 1:10000, 1:25000, 1:50000, 1:100000; GeoTIFF, PDF | WMS `PobieranieArkuszeMapBDOT10k` | arkusz | do dodania (N) | podklad kartograficzny | `pl.gugik.bdot10k_maps` |
| `pl.gugik.bdot10k_derived` | Uslugi pochodne BDOT10k | statystyki sieci wodnej/komunikacyjnej/budynkow, nowe budynki, strefy wylaczone wokol turbin | WFS | woj./powiat | poza zakresem | pochodne tematyczne, nie zbior zrodlowy; statystyki sieci wodnej zwracaja 0 obiektow | `pl.gugik.bdot10k_stats`, `pl.gugik.bdot10k_new_buildings`, `pl.gugik.wind_turbine_zones` |
| `pl.gugik.bdoo` | BDOO (1:250000) | 2015, 2021-2026; GML | WMS `PobieranieBDOO`; ATOM `GUGIK_BDOO` | woj., kraj | do dodania (N) | przeglad, duze zlewnie | `pl.gugik.bdoo`, `pl.gugik.atom_bdoo` |
| `pl.gugik.prg_units` | PRG - granice jednostek | woj./powiat/gmina/jedn. i obreby ewid.; GML (woj.), SHP (kraj); WFS; OGC API | `integracja.gugik.gov.pl/PRG/pobierz.php`, WFS `PRG/WFS/AdministrativeBoundaries`, OGC API `PRG` | woj., kraj; bbox | do dodania (W) | dzis tylko wewnetrznie (maska, TERYT); granice zlewni/gmin w Hydrografie | `pl.gugik.prg_units`, `pl.gugik.prg_wfs`, `pl.gugik.prg_ogcapi`, `pl.gugik.atom_prg` |
| `pl.gugik.prg_addresses` | PRG - adresy i ulice | gmina, powiat, woj., kraj; GML/SHP; WFS KIN | `pobierz.php?...&adresy*`, WFS `KrajowaIntegracjaNumeracjiAdresowej` | gmina-kraj; bbox | do dodania (N) | geokodowanie obiektow | `pl.gugik.prg_addresses`, `pl.gugik.prg_addresses_wfs` |
| `pl.gugik.prg_special` | PRG - granice specjalne | sady, prokuratury, policja, rejony statystyczne; SHP/GML | `pobierz.php?granice_specjalne_*`; OGC API `PRG` | kraj | do dodania (N) | - | `pl.gugik.prg_special_boundaries` |
| `pl.gugik.prng` | PRNG - nazwy geograficzne RP | miejscowosci, obiekty fizjograficzne; GML/SHP/XLSX; WFS; OGC API | `opendata/prng/*.zip`, WFS `PRNG/WFS/GeographicalNames`, OGC API `PRNG` | kraj; bbox | do dodania (N) | nazwy rzek/jezior do etykiet | `pl.gugik.prng`, `pl.gugik.prng_wfs`, `pl.gugik.prng_ogcapi`, `pl.gugik.atom_prng` |
| `pl.gugik.prng_world` | Polskie nazwy geograficzne swiata | OGC API, pliki | OGC API `PolskaNazwaGeograficznaSwiata` | swiat | do dodania (N) | - | `pl.gugik.prng_world` |
| `pl.gugik.prpog` | Osnowy podstawowe | pozioma, wysokosciowa (paczki powiatowe: wykazy + opisy), grawimetryczna, magnetyczna (WFS); kartoteki archiwalne 1942/Kronsztadt60 | `integracja.gugik.gov.pl/osnowa/?teryt=&typ=`, WFS, `opendata/bdpog/` | powiat; bbox; arkusz 1:100000 | do dodania (N) | kontrola wysokosci NMT (osnowa wysokosciowa) | `pl.gugik.prpog_packages`, `pl.gugik.prpog_wfs`, `pl.gugik.gravity_network`, `pl.gugik.magnetic_network`, `pl.gugik.prpog_archive_catalogs` |
| `pl.gugik.egib` | EGiB - dzialki i budynki | GPKG (powiat, woj.), GeoParquet (woj., kraj); WFS zbiorcza; ULDK | `opendata/InneDane/latest_exports/eziudp_wfs/`, WFS `EGIB/WFS/UslugaZbiorcza`, `uldk.gugik.gov.pl` | powiat; bbox; dzialka | do dodania (S) | granice wlasnosci w projektach; zakres jak w powiatowych WFS (niepelne pokrycie) | `pl.gugik.egib_county_exports`, `pl.gugik.egib_wfs`, `pl.gugik.uldk` |
| `pl.gugik.rcn` | Rejestr Cen Nieruchomosci | transakcje i ceny; GPKG (powiat, woj.), GeoParquet (woj., kraj) | `opendata/InneDane/latest_exports/rcn_transakcje_ceny/` | powiat | do dodania (N) | poza hydrologia; bezplatny od 02.2026 | `pl.gugik.rcn` |
| `pl.gugik.egib_summary` | Zestawienia zbiorcze EGiB | XLSX 2020-2026 | WMS `KrajoweZestawienieZbiorcze*` | powiat, woj., kraj | poza zakresem | dane tabelaryczne bez geometrii | `pl.gugik.egib_summary_stats` |
| `pl.gugik.quasigeoid` | Model quasi-geoidy PL-geoid2021 | TXT siatka (fi, lambda, zeta) | `opendata/InneDane/ModeleQuasiGeoidy/` | kraj | do dodania (N) | transformacje wysokosci elipsoidalnych (LIDAR, GNSS) | `pl.gugik.quasigeoid` |
| `pl.gugik.landcover_polsa` | Pokrycie terenu (POLSA) | 2019-2023; GeoTIFF 20 m | WCS `POLSA/WCS/LandCover` (hostowany na geoportalu) | bbox | poza zakresem (na razie) | spoza GUGiK (POLSA), licencja niepotwierdzona; pominiete decyzja uzytkownika 2026-10-13 | `pl.gugik.landcover_polsa` |
| `pl.gugik.inspire` | Tematy INSPIRE: AU, GN, TN, OI, EL, LC, BU, PF, US, AM, SO, PS, SR, HY | GML (schematy INSPIRE/ELF) | ATOM `.../atom/<temat>`, WFS `wfs<temat>/guest` | woj., kraj | poza zakresem | przeksztalcenia BDOT10k/PRG/PRNG/NMT/orto do schematow INSPIRE (duplikaty zbiorow natywnych); SO = kilka profili glebowych z Atlasu Polski (51 KB), SR = obszary morskie | `pl.gugik.inspire_*` (14) |
| `pl.gugik.sheet_grids` | Siatki podzialu arkuszowego | WFS (1992, 2000, rozszerzone NMT/ORTO) | WFS `mapy/WFS/SiatkiPodzialuArkuszowego` | bbox | poza zakresem | Kartograf liczy siatki sam (`SheetParser`) | `pl.gugik.sheet_grids` |
| `pl.gugik.tactile_maps` | Mapy tyflologiczne | ZIP do druku wypuklego | WMS `SkorowidzMapTyflologicznych` | atlas | poza zakresem | material do druku dla niewidomych, nie dane GIS | `pl.gugik.tactile_maps` |
| `pl.gugik.shaded_relief` | Cieniowanie/hipsometria NMT | WMS/WMTS | `NMT/GRID1/WMS/ShadedRelief` | - | poza zakresem | tylko podglad (render), dane = NMT | - |
| `pl.gugik.topo_maps` | Mapy topograficzne, ogolnogeograficzne, tematyczne (skany, archiwalne), mapy hydrograficzne i sozologiczne | raster/wektor | wniosek (`gov.pl/web/gugik/dane-udostepniane-na-wniosek`) | arkusz | poza zakresem | odplatne na wniosek (art. 40a ust. 1); bez probki | - |
| `pl.gugik.bdot500_gesut` | BDOT500, GESUT | wektor | starostwa (odplatnie); KIBDOT/KIUT tylko WMS | powiat | poza zakresem | odplatne u starostow; bez probki | - |
| `pl.gugik.bdsog` | Szczegolowe osnowy (BDSOG) | WMS KISOG; WFS powiatowe | 385 uslug powiatowych | powiat | poza zakresem | brak centralnej uslugi pobierania; heterogeniczne uslugi powiatowe | - |

Spoza GUGiK, opisane na geoportalu (poza zakresem): EuroBoundaryMap i
EuroGlobalMap (EuroGeographics), model WRF METEOPG (prognoza
meteorologiczna CI TASK), przejazdy kolejowe (PKP PLK), strefa buforowa
przy granicy z Bialorusia (Straz Graniczna). Bez probek - inni producenci
i licencje.

## 4. CUZK (CZ)

Licencja otwartych danych ZU: CC BY 4.0. Identyfikatory probek z ATOM:
`cz.cuzk.atom.<NAZWA_USLUGI>`; ArcGIS: `cz.cuzk.img.*`, `cz.cuzk.ms.*`,
WFS: `cz.cuzk.wfs.*`.

| ID | Produkt | Warianty | Kanal(y) pobierania | Ziarno | Status | Uzasadnienie | Probki |
|---|---|---|---|---|---|---|---|
| `cz.cuzk.dmr5g` | DMR 5G (NMT) | raster 2 m (ImageServer); LAZ S-JTSK/Bpv i ETRS89-TM33/EVRS | ImageServer `dmr5g`; ATOM `DMR5G-SJTSK`, `DMR5G-ETRS89` | bbox; SM5; kafel 2x2 km | obslugiwany czesciowo | raster obslugiwany; LAZ nie | `cz.cuzk.dmr5g (CLI --cutout)`, `cz.cuzk.atom.DMR5G-SJTSK`, `cz.cuzk.atom.DMR5G-ETRS89` |
| `cz.cuzk.dmr4g` | DMR 4G (NMT 5 m) | TIFF S-JTSK i ETRS89; LAZ obu ukladow; ImageServer | ATOM `DMR4G-*-TIFF`, `DMR4G-SJTSK/ETRS89`; ImageServer `dmr4g` | SM5; kafel | obslugiwany czesciowo | TIFF S-JTSK + ImageServer obslugiwane; TIFF ETRS89/EVRS i LAZ nie | `cz.cuzk.dmr4g (CLI)`, `cz.cuzk.atom.DMR4G-*`, `cz.cuzk.img.dmr4g` |
| `cz.cuzk.dmp1g` | DMP 1G (NMPT z ALS) | LAZ S-JTSK, ETRS89; ImageServer 2 m | ATOM `DMP1G-*`; ImageServer `dmp1g` | SM5; kafel; bbox | do dodania (S) | odpowiednik NMPT | `cz.cuzk.atom.DMP1G-SJTSK`, `cz.cuzk.atom.DMP1G-ETRS89`, `cz.cuzk.img.dmp1g` |
| `cz.cuzk.dmpok` | DMP z korelacji obrazowej | TIFF 0,5 m i LAZ, S-JTSK i ETRS89; ImageServer | ATOM `DMPOK-*`; ImageServer `dmp_obrazova_korelace`, `dmp` | SM5; kafel; bbox | do dodania (W) | aktualny NMPT CZ (pary z NMPT PL przy granicy) | `cz.cuzk.atom.DMPOK-*`, `cz.cuzk.img.dmp_ok`, `cz.cuzk.img.dmp` |
| `cz.cuzk.ortofoto` | Ortofoto CR | JPEG + JGW (S-JTSK i TM33N), 0,125 m | ATOM `ORTOFOTO` | SM5 | do dodania (S) | odpowiednik orto PL | `cz.cuzk.atom.ORTOFOTO` |
| `cz.cuzk.zabaged` | ZABAGED polohopis | 149 warstw; GPKG/FGDB krajowe; WFS; MapServer query | ATOM `ZABAGED-GPKG/FGDB`; WFS `ZABAGED_POLOHOPIS/MapServer/WFSServer`; REST query | kraj (5,8 GB); bbox | do dodania (W) | odpowiednik BDOT10k (land cover CZ dla CN) | `cz.cuzk.atom.ZABAGED-GPKG`, `cz.cuzk.atom.ZABAGED-FGDB`, `cz.cuzk.wfs.zabaged`, `cz.cuzk.ms.zabaged_polohopis` |
| `cz.cuzk.zabaged_contours` | ZABAGED vyskopis - warstwice | SHP, DGN | ATOM `ZABAGED-vyskopis`, `-DGN`; MapServer `ZABAGED_VRSTEVNICE` | SM5; bbox | do dodania (N) | - | `cz.cuzk.atom.ZABAGED-vyskopis`, `cz.cuzk.atom.ZABAGED-vyskopis-DGN`, `cz.cuzk.ms.zabaged_vrstevnice` |
| `cz.cuzk.data50_250` | Data50, Data250 | SHP (ZIP krajowy 516/230 MB; Data50 takze ETRS89); MapServer | ATOM `Data50`, `Data250`; MapServer `DATA50/DATA250` | kraj; bbox | do dodania (N) | przegladowe (odpowiednik BDOO) | `cz.cuzk.atom.Data50`, `cz.cuzk.atom.Data250`, `cz.cuzk.ms.data50`, `cz.cuzk.ms.data250` |
| `cz.cuzk.hydro_inspire` | INSPIRE HY-NET, HY-P (siec hydrograficzna) | GPKG krajowe (191 MB / 445 MB); WFS geoserver | ATOM `HY-NET`, `HY-P`; WFS `geoserver/hy-n`, `hy-p` | kraj; bbox | do dodania (S) | gotowa topologiczna siec rzek CZ dla zlewni transgranicznych | `cz.cuzk.atom.HY-NET`, `cz.cuzk.atom.HY-P`, `cz.cuzk.wfs.inspire_hy_n` |
| `cz.cuzk.ruian` | RUIAN - jednostki, adresy, budynki | VFR XML (stan/zmiany, podstawowy/kompletny, historia), CSV adresy, SHP obec/stat | ATOM `RUIAN-*`; MapServer `RUIAN` | obec; kraj; bbox | do dodania (S) | granice administracyjne CZ (odpowiednik PRG) | `cz.cuzk.atom.RUIAN-*` (12), `cz.cuzk.ms.ruian` |
| `cz.cuzk.ruian_uup_ad` | RUIAN - ucelove uzemni prvky, specjalne adresy | VFR XML | ATOM `RUIAN-S-UUP-U/Z`, `RUIAN-SP-AD-U/Z` | kraj | do ponownej weryfikacji | feedy wskazuja pliki z 2025 usuniete z serwera (HTTP 404, sekcja 5) | - |
| `cz.cuzk.cadastral_map` | Katastralni mapa | SHP, DXF, DGN, VFK, VKM | ATOM `KM-KU-*` | katastralne uzemi | do dodania (N) | granice dzialek CZ (odpowiednik EGiB) | `cz.cuzk.atom.KM-KU-*` (5) |
| `cz.cuzk.geonames` | Geonames (nazwy) | GPKG, FGDB; MapServer | ATOM `GEONAMES-*`; MapServer `GEONAMES/Geonames` | kraj; bbox | do dodania (N) | odpowiednik PRNG | `cz.cuzk.atom.GEONAMES-GPKG`, `cz.cuzk.atom.GEONAMES-FGDB`, `cz.cuzk.ms.geonames` |
| `cz.cuzk.ztm` | ZTM 1:5000-1:250000 | TIFF, DGN, PDF, SHP; S-JTSK i ETRS89-TMzn | ATOM `ZTM<skala>-<uklad>-<format>` (36 uslug) | arkusz | do dodania (N) | podklad kartograficzny | `cz.cuzk.atom.ZTM*` (36) |
| `cz.cuzk.qgzu` | Kwazigeoida QGZU-2013 | TXT siatki | ATOM `QGZU` | kraj | do dodania (N) | transformacje wysokosci | `cz.cuzk.atom.QGZU` |
| `cz.cuzk.survey_control` | Bodova pole (osnowy) | MapServer/WFS | `BodovaPole/MapServer` | bbox | do dodania (N) | odpowiednik osnow PL | `cz.cuzk.ms.survey_control` |
| `cz.cuzk.geomorphology` | Jednostki geomorfologiczne | MapServer | `GeomorfologickeJednotky/MapServer` | bbox | do dodania (N) | - | `cz.cuzk.ms.geomorphology` |
| `cz.cuzk.inspire_dup` | INSPIRE CP, CPX, BU, AD, AU, GN, LU, TN-*, EL-GRID, EL-TIN, OI, GGS | GML/GPKG/JP2 | ATOM; WFS `services.cuzk.gov.cz`, `geoportal.cuzk.gov.cz/geoserver` | KU; obec; kraj; kafel | poza zakresem | przeksztalcenia KN/RUIAN/ZABAGED/DMR/ortofoto do schematow INSPIRE (duplikaty); EL-GRID krajowo 7,7 GB | `cz.cuzk.atom.{CP,CPX,BU,AD,AU,GN,LU,TN-*,EL-GRID,EL-TIN,OI,GGS}`, `cz.cuzk.wfs.cp`, `cz.cuzk.wfs.inspire_elu`, `cz.cuzk.img.inspire_el` |
| `cz.cuzk.print_maps` | Mapy do druku: MCR 1:500000/1:1M/1:2M, MK250, MSR250, MORP50, FGM500 | PDF, TIFF | ATOM | kraj; kraj (wojewodztwo CZ); ORP | poza zakresem | mapy przegladowe/administracyjne do druku | `cz.cuzk.atom.MCR*`, `MK250`, `MSR250`, `MORP50`, `FGM500-PDF` |
| `cz.cuzk.cadastre_admin` | Geometricke plany (VFK), UZSVM, UHDP, volebni okrsky, ciselniky, uredni desky | VFK, SHP, CSV | ATOM | KU; kraj | poza zakresem | dane administracyjne/procesowe katastru i wyborcze, tabele, ogloszenia | `cz.cuzk.atom.{GMPL-KU-VFK,UZSVM,UHDP,VO,CIS,RUIAN-SP-VO-U,RUIAN-SP-CIS-U}` (UD: feed bez plikow) |
| `cz.cuzk.view_only` | Historicka jmena, Jmena sveta, Klady mapovych listu | MapServer | ArcGIS REST | - | poza zakresem | wg ZU tylko usluga mapowa (prezentacja); klady uzywane wewnetrznie | `cz.cuzk.ms.historical_names`, `cz.cuzk.ms.world_names`, `cz.cuzk.ms.sheet_index` |
| `cz.cuzk.paid` | Letecke merickie snimky, archivni ortofoto, ortofoto CIR, archivni mapy, dane KN (wlasciciele) | - | ESHOP / zamowienie | - | poza zakresem | LMS, archiwalne orto i mapy - odplatnie; CIR bezplatnie, ale tylko na wniosek przez ESHOP (brak uslugi pobierania); `Formy_poskytovani_dat_ZU.pdf` | - |

## 5. Do ponownej weryfikacji

| ID | Problem | Proby (UTC) | Nastepny krok |
|---|---|---|---|
| `cz.cuzk.ruian_uup_ad` (`RUIAN-S-UUP-U`, `RUIAN-S-UUP-Z`, `RUIAN-SP-AD-U`, `RUIAN-SP-AD-Z`) | feed zbioru wskazuje pliki `20251031_ST_UUUS_1.xml.zip`, `20250605_ST_ZUUS_1.xml.zip`, `20250603_ST_UADS.xml.zip`, `20250603_ST_ZADS.xml.zip` - HTTP 404; strona katalogu `vdp.cuzk.gov.cz/vymenny_format/soucasnaUUP/` - "stranka nebyla nalezena" | 16:07-16:10 (3 proby kazdy), 16:22 (HEAD 404) | sprawdzic feed ponownie (CUZK moze odswiezyc feed); zbiory niszowe, nie blokuja specu |

Rozwiazane w ponowieniu (nie sa w tabeli): GUGiK ATOM
`NazwyGeograficzne` - timeout 120 s, ponowienie 16:22 OK
(`pl.gugik.inspire_gn`); GUGiK WMS `Skorowidze_BDOT10k` warstwa `0` -
timeout, ponowienie 16:22 OK (brak rekordow w punkcie probki - skorowidz
aktualizacji, nie zbior danych).

## 6. Wnioski do specu

1. Najwieksza luka w produktach juz obslugiwanych: NMT/NMPT 0,5 m (PL) -
   nowe loty sa poza zasiegiem Kartografa.
2. Brak sposobu, zeby przed pobraniem zobaczyc, co jest dostepne dla
   obszaru (lata, uklady, rozdzielczosci, pokrycie) - prosba uzytkownika
   2026-10-13 (backlog PROGRESS).
3. Nowe produkty dla toolchainu hydrologicznego: PRG (granice), BDOT10k
   archiwalny, modele 3D budynkow, EGiB, pokrycie POLSA (po potwierdzeniu
   licencji); CZ: ZABAGED, DMP OK/DMP 1G, LAZ CZ, RUIAN, siec HY-NET,
   ortofoto.
4. Wzorce kanalow sie powtarzaja: (a) skorowidz WMS/WFS -> plik
   `opendata` per arkusz (NMT/NMPT/orto/OI/LAZ/orto ukosna/mesh), (b) link
   per jednostka administracyjna z `GetFeatureInfo`/sciezki (BDOT10k,
   archiwum BDOT10k, 3D, EGiB, RCN, PRG, osnowy), (c) WCS bbox (NMT/NMPT,
   orto, true orto, POLSA), (d) WFS/OGC API bbox (PRG, PRNG, EGiB), (e)
   CUZK ATOM z przewidywalnym URL-em (arkusz/kafel/KU/obec/kraj), (f) CUZK
   ArcGIS REST (exportImage / query). Spec powinien dodac produkty przez
   te kanaly, nie przez osobny kod per produkt.
