# Plan E - weryfikacja zrodel przed implementacja 0.8.0 (2026-10-15)

Zakres: 24 pozycje planu E ze [specu podprojektu 3](../../superpowers/specs/2026-10-13-katalog-produktow-design.md)
(sekcja 6). Punkt wyjscia: [inwentaryzacja](../2026-10-13-katalog-produktow/raport.md)
i [probki](../2026-10-13-katalog-produktow/probki.md) z 2026-10-13. Ten raport
dopisuje pomiary z 2026-10-15: `HEAD` plikow, `GetCapabilities`,
`GetFeatureInfo`, `DescribeCoverage`, feedy ATOM, metadane ArcGIS REST i OGC
API. Pobrane odpowiedzi leza poza repo (`<katalog-danych>`). Pelne pliki
pobrano tylko tam, gdzie podano SHA-256; pozostale rozmiary sa z naglowka
`Content-Length` albo z atrybutu `length` w ATOM. Plan:
[`2026-10-15-plan-e-produkty.md`](../../superpowers/plans/2026-10-15-plan-e-produkty.md).

Licencje wg deskryptora (`kartograf/sources/registry.py`): PL `_GUGIK_LICENSE`
(`PL-PGiK-40a`), CZ `_CUZK_LICENSE` (`CC-BY-4.0`). Zaden produkt E nie wymaga
logowania ani oplaty. RCN jest nieodplatny od 2026 (ustawa z 26.09.2025,
Dz.U. poz. 1542; [strona RCN](https://www.geoportal.gov.pl/pl/dane/rejestr-cen-nieruchomosci-rcn/)).

Skroty: `opendata` = `https://opendata.geoportal.gov.pl`,
`mapy` = `https://mapy.geoportal.gov.pl/wss/service`,
`ogcapi` = `https://ogcapi.geoportal.gov.pl/res/ims/maps`,
`openzu` = `https://openzu.cuzk.gov.cz/opendata`,
`ags` = `https://ags.cuzk.gov.cz/arcgis/rest/services`,
`atom` = `https://atom.cuzk.gov.cz`.

## 1. Produkty

Sygnal swiezosci (K6): `index` = rekord indeksu (data/zgloszenie),
`metadata` = `<updated>` wpisu ATOM, `http` = `ETag`/`Last-Modified`,
`none` = brak taniego sygnalu.

| # | Produkt | Kanal i format (pomiar 2026-10-15) | Rozmiar | Sygnal | Status |
|---|---|---|---|---|---|
| 1 | NMT 100 m (`pl.gugik.nmt_100m`) | ATOM `mapy/ATOM/httpauth/atom/GUGIK_NMT100`: 16 wpisow, id zbioru `NMT100_<TERYT woj.>`, kazdy wpis prowadzi do feedu zbioru z jednym linkiem `.../download/?fileId=<skrot>&name=<woj>_grid100.zip` (`length`, kategoria EPSG:2180); ZIP z jednym TXT XYZ. Linki w feedzie sa `http://`; ten sam URL przez `https` odpowiada 200 (feed i plik). Uklad wysokosci nie jest podany ani w ATOM, ani w CSW (rekord `249a7212-...`: "wygenerowano na podstawie danych ASCII NMT projektu LPIS", utworzenie 2015). | malopolskie 7 619 580 B | `metadata` (wpis 2019-05-14) | pytanie P1 |
| 2 | Obrazy intensywnosci (`pl.gugik.intensity`) | WMS `mapy/PZGIK/OI/WMS/SkorowidzeObrazowIntensywnosci`, warstwa `SkorowidzeOI` (GFI w szablonie `skor.push`: `url`, `godlo`, `aktualnosc`, `aktualnoscRok`, `wielkoscPiksela` 0.25, `ukladWspolrzednych` PL-1992 albo PL-2000:Sx, `numerZgloszeniaPracy`, `dt_pzgik`); TIFF 1 pasmo. Ten sam punkt ma arkusze PL-1992 (np. `M-34-64-D-d-1-4`, lata 2023 i 2025) i PL-2000 (`7.125.11.13`). | 84 985 518 B/arkusz | `index` | do implementacji |
| 3 | True orto (`pl.gugik.orto_true`) | Arkusze: WMS `mapy/PZGIK/ORTO/WMS/TrueOrtho`, warstwa `Skorowidze` (GFI `skor.push`, godlo 8-czlonowe PL-1992, np. `N-34-50-A-c-3-2-3`, `wielkoscPiksela` 0.05, bez `dt_pzgik`); pokrycie tylko wybrane miasta (punkty w Krakowie i Warszawie: brak rekordow). Wycinek: WCS `mapy/PZGIK/ORTO/WCS/TrueOrto`, coverage `True_Orthoimagery`, siatka natywna 0,05 m w EPSG:2180 (`DescribeCoverage` 1.0.0 i 2.0.1), GeoTIFF 24-bit. | arkusz 296 853 152 B; wycinek probki 1,2 MiB | `index` (arkusz), `none` (wycinek) | do implementacji |
| 4 | Orto ukosna (`pl.gugik.orto_oblique`) | WMS `mapy/PZGIK/ORTO/WMS/SkorowidzeOrtofotomapyUkosnej`, warstwy `SkorowidzeOrtofotomapyUkosnej-Polnoc`, `-Wschod`, `-Poludnie`, `-Zachod` (GFI `skor.push`: `godlo` PL-2000 1:2000, `kierunek`, `charakterystykaPrzestrzenna` 0.05, `ukladWspolrzednychPoziomych`, `calyArkuszWypelnionyTrescia`, `kolor`). | 287,7 MiB/arkusz/kierunek | `index` | do implementacji |
| 5 | Mesh 3D (`pl.gugik.mesh_3d`) | WFS `mapy/PZGIK/NMT/WFS/ModeleSiatkowe3D`, typ `gugik:SkorowidzModeleSiatkowe3D` (BBOX N,E, stronicowanie `next`, `numberMatched=unknown`; pola `modul`, `URL_do_pobrania`, `Aktualnosc`, `akt_rok`, `format` OBJ, `uklad_xy` PL-2000:S7, `uklad_h` PL-EVRF2007-NH, `Numer_zgloszenia_pracy`); WMS `mapy/PZGIK/NMT/WMS/ModeleSiatkowe3D`. ZIP: OBJ, MTL, 4 JPG. | 37 672 494 B/kafel | `index` | do implementacji |
| 6 | Modele drzew 3D (`pl.gugik.trees_3d`) | `opendata/InneDane/Drzewa3D/LOD1/2023/{woj}/{teryt}.zip` (CityGML 2.0 LoD1). Lata 2021, 2022, 2024-2026 i `LOD2`: 404. `HEAD` trwa 6-40 s. | 2261: 3 408 621 873 B; 0264: 3 622 615 862 B; 1261: 3 740 502 509 B; 1201: 7 299 958 184 B; 1465: 8 567 682 928 B | `none` | do implementacji |
| 7 | Wizualizacje BDOT10k (`pl.gugik.bdot10k_maps`) | WMS `mapy/PZGIK/BDOT/WMS/PobieranieArkuszeMapBDOT10k`, warstwy `Mapy10k`, `Mapy25k`, `Mapy50k`, `Mapy100k`. GFI to tabela HTML: godlo, link PDF, link GeoTIFF, "Stan bazy BDOT10k na dzien: 2026-05-27". Plik: `opendata/Mapy/Topograficzne/Wizualizacja_BDOT10k_<skala>/<folder>/<godlo>.{tif,pdf}` (godla z 3-cyfrowym numerem 1:100000, np. `M-34-064-D-d-1`). PDF i GeoTIFF sa w kazdej skali. | 1:10000 TIFF 63,5 MiB; 1:100000 PDF 29 406 436 B, TIFF 85 267 044 B | `index` (data stanu bazy) | do implementacji |
| 8 | BDOO (`pl.gugik.bdoo`) | `opendata/bdoo/{rok}/PL.PZGiK.201.{woj}.zip` (GML, pliki `..._OT_<KLASA>_<typ>.xml`). Roczniki 2015, 2021, 2022, 2023, 2024, 2025, 2026; 2016-2020: 404. Pliku krajowego w tym schemacie brak (404). ATOM `GUGIK_BDOO` daje tylko biezace wydanie. | woj. 12: 9,2-14,6 MB | `none` | do implementacji |
| 9 | PRG punkty adresowe (`pl.gugik.prg_addresses`) | WFS `mapy.geoportal.gov.pl/wss/ext/wfs/KrajowaIntegracjaNumeracjiAdresowej`, typy `adresyUlice:A07_Punkty_adresowe`, `adresyUlice:A08_Ulice` (EPSG:2180, osie N,E); powiat SHP `opendata/prg/adresy/PunktyAdresowe/{woj}/{teryt}.zip` (paczki woj. `.../PunktyAdresowe/12.zip`: 404); kraj `.../PunktyAdresowe/POLSKA.zip` (SHP) i `opendata/prg/adresy/PRG-punkty_adresowe.zip` (format wg katalogu GML - niepotwierdzony, bo `opendata` nie obsluguje `Range`). | powiat 1261: 6 066 872 B; kraj 563 803 725 B / 803 390 540 B | `none` | do implementacji |
| 10 | PRG granice specjalne (`pl.gugik.prg_special`) | OGC API `ogcapi/PRG/apiFeatures`: 52 kolekcje w CRS84 (przechowywanie EPSG:4258); 6 kolekcji `Granica{Panstwa,Wojewodztwa,Powiatu,Gminy,JednostkiEwidencyjnej,ObrebuEwidencyjnego}` to granice administracyjne (plan C), pozostale 46: rejony statystyczne, obwody spisowe, sady, prokuratury, policja, PSP, Straz Graniczna, obrona cywilna, administracja skarbowa, Lasy Panstwowe, Wody Polskie, obszary morskie. Kraj: `opendata/prg/granice/00_granice_specjalne_shp.zip` i `00_granice_specjalne_xml.zip`. | 734 171 465 B / 757 744 521 B | `none` | do implementacji |
| 11 | PRNG - nazwy RP (`pl.gugik.prng`) | OGC API `ogcapi/PRNG/apiFeatures`, kolekcja `NazwaGeograficznaRP` (wyjscie tylko CRS84, przechowywanie EPSG:2180). Pliki krajowe z GFI WMS `mapy/PZGIK/PRNG/WMS/DaneDoPobrania`: `opendata/prng/PRNG_{MIEJSCOWOSCI,OBIEKTY_FIZJOGRAFICZNE}_{GML,SHP,XLSX}.zip`. WFS `ms:Wsie` z katalogu GUGiK jest nieaktualny. | MIEJSCOWOSCI_GML 20 358 653 B; OBIEKTY_FIZJOGRAFICZNE_SHP 29 417 448 B | `none` | do implementacji |
| 12 | PRNG - nazwy swiata (`pl.gugik.prng_world`) | OGC API, kolekcja `PolskaNazwaGeograficznaSwiata` (CRS84, przechowywanie EPSG:4326); pliki `opendata/prng/PRNG_SWIAT_{GML,SHP,XLSX}.zip`. | GeoJSON 38,7 KiB/20 obiektow | `none` | do implementacji |
| 13 | Osnowy podstawowe (`pl.gugik.prpog`) | Paczki powiatowe `opendata/bdpog/Pozioma/{teryt}_PodstawowaOsnowaPozioma.zip` i `opendata/bdpog/Wysokosciowa/{teryt}_PodstawowaOsnowaWysokosciowa.zip` (wykazy i opisy topograficzne JPG; `integracja.gugik.gov.pl/osnowa/?teryt=1261&typ=H` odpowiada 302 na ten URL). WFS (EPSG:2180, N,E): `mapy/PZGIK/PodstawowaOsnowaGeodezyjnaPozioma` (`ms:Fundamentalna_pozioma`, `ms:Bazowa_pozioma`), `...Wysokosciowa` (`ms:Fundamentalna_wysokosciowa`, `ms:Bazowa_wysokosciowa`), `mapy/PZGIK/OsnowaGrawimetryczna` (`ms:Fundamentalna_grawimetryczna`, `ms:Bazowa_grawimetryczna`), `mapy/PZGIK/OsnowaMagnetyczna` (`ms:Fundamentalna_magnetyczna`, `ms:Bazowa_magnetyczna`, `ms:izogony`, `ms:izogony_etykiety`). Archiwa per arkusz 1:100000: `opendata/bdpog/MaterialyArchiwalne/Katalogi_Kartoteki1942/{godlo}.zip` i `.../Katalogi_Kronsztadt60/{godlo}.zip` (godlo bez zera wiodacego, np. `M-34-64`; `M-34-064`: 404). | 1201: 2 883 814 B (pozioma), 14 190 226 B (wysokosciowa); M-34-64: 1 069 061 020 B (1942), 26 007 952 B (Kronsztadt60) | `none` | do implementacji |
| 14 | RCN (`pl.gugik.rcn`) | `opendata/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/{teryt}_transakcje_ceny.gpkg.zip`, powiat i wojewodztwo; GPKG z warstwami `transakcje_dzialki`, `transakcje_budynki`, `transakcje_lokale` (EPSG:2180). GeoParquet tylko dla wojewodztw i kraju. Rejestr cen to plik GPKG, nie WMS z cenami. | 1261: 236 404 584 B (pelne pobranie: SHA-256 `667fa2ab543ee27e0dac3a6b675e2a020dfb958a65158d68a01547bf6329a7d3`, `unzip -t` OK); 1201: 9 690 385 B; woj. 12: 548 970 792 B | `none` | do implementacji |
| 15 | Quasi-geoida PL-geoid2021 (`pl.gugik.quasigeoid`) | `opendata/InneDane/ModeleQuasiGeoidy/PL-geoid2021/Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt`: naglowek szerokosc/dlugosc/zeta, 962 001 wezlow (801 x 1201, krok 0,01 stopnia, 48-56 N, 13-25 E). PROJ 9.5.1 zna oficjalna siatke `pl_gugik_geoid2021-PL-EVRF2007-NH.tif` (CDN PROJ, otwarta licencja) dla operacji "ETRF2000-PL to EVRF2007-PL height (2)". | 42 328 086 B (SHA-256 `d695cf81c7952043bea14b2213730586d01ac538560b2e405f58d76044465ea6`) | `none` | do implementacji |
| 16 | CZ warstwice (`cz.cuzk.zabaged_contours`) | Arkusze SM5: `openzu/ZABAGED-vyskopis/epsg-5514/{sm5}.zip` (SHP, 8 plikow) i `openzu/ZABAGED-vyskopis-DGN/epsg-5514/{sm5}.zip` (DGN). Feed ATOM ma 16 301 wpisow (23,8 MB), wiec zostaje nieuzywany (szablon URL i indeks SM5 jak w planie B). REST `ags/ZABAGED_VRSTEVNICE/MapServer/0`. | CTES96: 1,5 MB SHP / 1,4 MB DGN | `http` | do implementacji |
| 17 | CZ Data50 (`cz.cuzk.data50`) | ATOM `atom/Data50/Data50.xml` -> feed zbioru -> `openzu/Data50/epsg-5514/data50.zip` i `.../epsg-3045/data50.zip` (SHP; kategorie CRS w feedzie). REST `ags/DATA50/MapServer`: 69 warstw obiektowych, `maxRecordCount` 2000. | 515 542 917 B / 756 987 213 B | `metadata` (kraj), `none` (obszar) | do implementacji |
| 18 | CZ Data250 (`cz.cuzk.data250`) | ATOM `atom/Data250/Data250.xml`: `openzu/Data250/epsg-5514/data250.zip`, `.../epsg-3045/data250.zip`. REST `ags/DATA250/MapServer`: 116 warstw obiektowych. | 230 485 722 B / 320 374 437 B | `metadata` (kraj), `none` (obszar) | do implementacji |
| 19 | CZ mapa katastralna (`cz.cuzk.cadastral_map`) | Per katastralni uzemi: SHP `services.cuzk.gov.cz/shp/ku/epsg-5514/{ku}.zip`, DXF `.../dxf/ku/{ku}.zip`, DGN `.../dgn/ku/{ku}.zip`, VFK `.../vfk/stavy/aktualni/{ku}.zip`; kazdy z `ETag` i `Last-Modified`. Kody KU dla obszaru: `ags/RUIAN/MapServer/7` (`KatastralniUzemi`). VKM: feed `atom/KM-KU-VKM` ma 10 KU (pilot, wpisy z 2026-10-15 17:02), a pliki `vkm/ku/aktualni/{ku}.zip` i `vkm/ku_zdroje/aktualni/{ku}.zip` daja 404 (tez KU 737950, ktory 2026-10-13 dzialal). | 623164: SHP 4 537 652, DXF 1 919 899, DGN 6 455 904, VFK 7 940 312 B | `http` | do implementacji; VKM: pytanie P2 |
| 20 | CZ Geonames (`cz.cuzk.geonames`) | ATOM `atom/GEONAMES-GPKG` i `GEONAMES-FGDB`: URL z data w nazwie (`openzu/GEONAMES-GPKG/epsg-5514/GEONAMES-5514-gpkg-20260930.zip`, takze `epsg-3045`). REST `ags/GEONAMES/Geonames/MapServer`: 25 warstw obiektowych. | GPKG 36 209 564 B (5514) / 37 060 649 B (3045) | `metadata` (kraj), `none` (obszar) | do implementacji |
| 21 | CZ ZTM (`cz.cuzk.ztm`) | 36 uslug `ZTM<5,10,25,50,100,250>-SJTSK-<TIFF,PDF,DGN,SHP>` i `-ETRS89-<TIFF,PDF>`; plik `openzu/<usluga>/<MAPNOM>.zip` (TIFF+TFW, DGN, SHP) albo `.pdf`. Indeks `ags/KladyMapovychListu/MapServer`: warstwy 0, 2, 4, 6, 8, 10 (S-JTSK 1:5000-1:250000) i 12, 14, 16, 18, 20, 22 (ETRS89), pole `MAPNOM`. Feed `ZTM10-SJTSK-TIFF` ma 4194 wpisy (6,4 MB) - nieuzywany. Uklad wynika z godla (`0301-B-01` S-JTSK, `NM-33-11-4-A-20` ETRS89). | ZTM10 S-JTSK TIFF 37,6 MiB | `http` | do implementacji |
| 22 | CZ QGZU (`cz.cuzk.qgzu`) | ATOM `atom/QGZU/QGZU.xml` -> `openzu.cuzk.cz/opendata/QGZU/KVAZIGEOID.zip` (17 siatek TXT, EPSG:4258). | 58 190 406 B (SHA-256 `aacfba6bdd47a6b89a3bcb079f133c9d549520b56794b7ef72f46d9185c2dfa3`, `unzip -t` OK) | `metadata` (wpis 2021-02-22) | do implementacji |
| 23 | CZ Bodove pole (`cz.cuzk.survey_control`) | REST `ags/BodovaPole/MapServer` (EPSG:5514): punkty CZEPOS 0; ZPBP 18 (warianty ETRS89/RTK, przydruzone i zrusene 2-21); ZhB 38 (22-41); PPBP 42; ZVBP 44; PVBP 46; ZTBP 48. Warstwy "Cisla ..." to etykiety. | GeoJSON 9,4 KiB/20 punktow | `none` | do implementacji |
| 24 | CZ jednostki geomorfologiczne (`cz.cuzk.geomorphology`) | REST `ags/GeomorfologickeJednotky/MapServer` (EPSG:5514): 33 subprovincie, 34 oblasti, 39 celek, 35 podcelek, 36 okrsek, 37 podokrsek, 38 casti. Warstwy 0-21 to adnotacje, 22-25 mozaika cieniowania. | 52,4 KiB/1 poligon | `none` | do implementacji |

## 2. Korekty inwentaryzacji z 2026-10-13

- NMT 100 m: inwentaryzacja podala EVRF2007 bez zrodla. ATOM i CSW nie
  deklaruja ukladu wysokosci. Pochodzenie z NMT LPIS, a GUGiK opisuje NMT
  z lat 2000-2019 jako PL-KRON86-NH
  ([strona NMT](https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/)).
  Patrz pytanie P1.
- Drzewa 3D: tylko LoD1 2023. Paczka powiatu ma 3,4-8,6 GB, nie 218 MB.
- Wizualizacje BDOT10k: PDF i GeoTIFF sa w kazdej skali; skale
  1:10000-1:100000.
- PRNG swiat ma pliki (GML, SHP, XLSX), nie tylko OGC API.
- PRG granice specjalne maja kanal obszarowy: kolekcje OGC API `PRG`.
- Osnowy: dwie serie archiwalne per arkusz 1:100000 (1942 i Kronsztadt60).
- True orto: arkusze sa 8-czlonowymi godlami PL-1992. `SheetParser`
  odrzuca je dzis (`ParseError`), a arkusz ma ok. 283 MiB.
- Mapa katastralna CZ VKM: pliki 404 (P2).

## 3. Pytania do uzytkownika

- **P1 - uklad wysokosci NMT 100 m.** Zrodlo go nie podaje (ATOM, CSW).
  Pochodzenie LPIS wskazuje PL-KRON86-NH. Rekomendacja: wariant rejestru
  `vertical_crs = KRON86` z segmentem `nmt/pl_1992_100m_kron86`. W sidecarze
  zapisac `extra.vertical_crs_basis`: uklad wywnioskowany z pochodzenia,
  GUGiK go nie deklaruje. Alternatywa: wariant bez ukladu wysokosci
  (segment `nmt/pl_1992_100m`). Wtedy `--vertical-crs` nie dotyczy 100 m,
  a dane nie wejda w zadna transformacje wysokosci. Od odpowiedzi zalezy
  tylko wpis wariantu (uklad wysokosci i segment); reszte Task E1 mozna
  wykonac wczesniej (patrz plan, Task E1).
- **P2 - format VKM mapy katastralnej CZ.** To pilot: 10 KU w feedzie,
  a pliki 15.10 zwracaly 404. Rekomendacja: VKM poza 0.8.0. Pozostale
  4 formaty (SHP, DXF, DGN, VFK) obejmuja caly kraj. Przy wykonaniu E3
  sprawdzic VKM ponownie. Jesli uzytkownik zdecyduje "tak" i pliki
  odpowiadaja 200, dopisac piaty kanal (ten sam szablon, lista KU z feedu
  `KM-KU-VKM`).

## 4. Granice dowodu

- `opendata.geoportal.gov.pl` ignoruje `Range`
  ([raport katalogu, sekcja 1](../2026-10-13-katalog-produktow/raport.md)).
  Nie pobierano pelnych paczek drzew, plikow krajowych PRG, Data50/250
  ani archiwum 1942. Ich rozmiar i istnienie potwierdza `HEAD`, a zawartosc
  sprawdzi dopiero E2E. Format `PRG-punkty_adresowe.zip` jest niepotwierdzony.
- GUGiK (`opendata`) nie podaje `ETag` ani `Last-Modified`. Bez rekordu
  indeksu albo ATOM sygnal to `none`, a `Content-Length` nim nie jest. CUZK
  (`openzu`, `services.cuzk.gov.cz`) podaje oba naglowki.
- Pokrycie true orto, orto ukosnej i mesh 3D obejmuje tylko wybrane miasta.
  Punkty kontrolne: Gdansk (true orto), Krakow (mesh, orto ukosna,
  intensywnosc).
