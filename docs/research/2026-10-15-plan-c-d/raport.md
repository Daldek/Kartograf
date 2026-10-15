# Plany C i D - rekonesans uslug GUGiK i CUZK (2026-10-15)

**Zakres:** archiwum BDOT10k, modele 3D budynkow, PRG (WFS i paczki), EGiB
(WFS i eksport powiatowy), ZABAGED (REST, WFS, plik krajowy), RUIAN, HY-NET,
ortofoto CZ (ATOM SM5), wycinek ortofotomapy PL z WCS. Cel: fakty potrzebne
do planow `docs/superpowers/plans/2026-10-15-plan-c-silniki-i-dane-pl.md`
i `...-plan-d-dane-cz.md` (silniki `unit_package`, `feature_bbox`,
`atom_files`, ADR-042).

**Metoda:** zapytania HTTP z jawnym limitem czasu (2026-10-15, 14:05-19:30
UTC); odpowiedzi i fragmenty plikow zapisane wylacznie poza repo w
`<katalog-danych>`. Duzych paczek nie pobierano w calosci (wyjatek: eksport
EGiB 1261, bo serwer zignorowal `Range`). Zrodla wczesniejsze:
[`raport.md`](../2026-10-13-katalog-produktow/raport.md),
[`probki.md`](../2026-10-13-katalog-produktow/probki.md),
[`bdot10k-archiwum.md`](../2026-10-13-katalog-produktow/bdot10k-archiwum.md),
[`2026-08-10-czechy-dmr-zabaged.md`](../2026-08-10-czechy-dmr-zabaged.md).
Przyklady BBOX GUGiK WFS w kolejnosci osi EPSG (**N,E**).

## 1. Proby na zywo

| Produkt / usluga | Zapytanie i wynik | Konsekwencja dla planu |
|---|---|---|
| BDOT10k archiwum | `HEAD .../Archiwum/bdot10k/<R>/<FMT>/12/1261_<FMT>_<R>.zip`: 2014 GML 38 913 857 B, 2024 GML 42 585 266 B, 2024 SHP 47 404 309 B, 2025 GML 46 808 424 B, 2025 SHP 30 561 298 B - HTTP 200; `2024/GPKG/...`, `2013/SHP/...`, `2026/SHP/...` - 404. Brak `ETag`/`Last-Modified`. | Roczniki 2014-2025, formaty GML/SHP (spec 9.3 potwierdzona); sygnal `none`; szablon URL wystarcza (bez WMS). |
| Modele 3D LoD1 | WMS `FOTO/WMS/ModeleBudynkow3D` (GetCapabilities): warstwy `Modele_3D_budynkow_LoD1_{2019,2021,2022,2024}`, `..._LoD2_2017`. `GetFeatureInfo` (1261): LoD1 2019 `LOD1/2019/12/1261_gml.zip`, LoD1 2021 `LOD1/2021/12/1261.zip`, LoD2 `LOD2/1261_gml.zip`; pliki krajowe `LOD1/LOD1_<R>.zip`, `LOD2/LOD2_2017.zip`. `HEAD`: LoD1 2021/2022/2024 dla 1261 - 200 (28,7-28,9 MB); 2019 bez `_gml` - 404, z `_gml` (0401, 1465) - 200; 2023/2025 - 404; LoD1 kraj 2024 3 529 624 029 B, LoD2 kraj 4 074 880 133 B. | Szablon URL zalezy od rocznika (2019 ma sufiks `_gml`) - wariant = jawna para (szablon, rocznik) w deskryptorze. Brak `ETag`. |
| Modele 3D LoD2 | `HEAD LOD2/0401_gml.zip` 200 (12,5 MB), `LOD2/3262_gml.zip` **404** (Szczecin bez LoD2), `LOD2/2017/...` 404. | LoD2 nie pokrywa kraju: 404 powiatu = blad tego powiatu z podpowiedzia, nie awaria zadania. Jedyny rocznik katalogowy 2017. |
| PRG paczki | `HEAD prg/granice/12_GraniceAdministracyjne.zip` 22 070 839 B, `02_...` 13 100 936 B, `00_jednostki_administracyjne.zip` 377 419 459 B; brak `ETag`/`Last-Modified`. Paczka woj. = 5 plikow GML (A01, A02, A03, A05, A06; probka 2026-10-13). | Woj. = GML wszystkich poziomow (bez A00/A04), kraj = SHP; ZIP 1:1; sygnal `none`; kraj tylko jawnie (K7). |
| PRG WFS | `AdministrativeBoundaries` GetCapabilities: 52 typy, poziomy `ms:A00_Granice_panstwa` ... `ms:A06_Granice_obrebow_ewidencyjnych`, DefaultCRS `urn:ogc:def:crs:EPSG::2180`, tylko GML. BBOX N,E daje obiekt, E,N - `numberReturned=0` bez bledu. Duzy bbox gmin (`220000,550000,270000,590000`): `RESULTTYPE=hits` -> `numberMatched=39`; `COUNT=1000` -> 39 obiektow; stronicowanie `COUNT=10`: strona `STARTINDEX=0` ma `next`, strona `STARTINDEX=10` **nie ma `next`** (choc obiektow jest 39), `STARTINDEX=20` znow ma `next`, `STARTINDEX=30` zwraca 10 obiektow (powinno 9: jeden **duplikat**), `STARTINDEX=40` - 0. A02 (jeden powiat w bbox): `STARTINDEX=1` zwraca **ten sam** powiat co `STARTINDEX=0`, z `numberMatched=2`. `gml:id` = `.1`, `.2` (nie identyfikuje obiektu); stabilny klucz: `IIP_IDENTY` (+ `IIP_WERSJA`). Zwracane sa pelne geometrie przecinajacych jednostek. | Nie wolno opierac konca stron na `next` ani dedupe na `gml:id`. Algorytm: `hits` -> N, strony `STARTINDEX` po `COUNT`, dedupe po polu identyfikatora kanalu, koniec gdy zebrano N unikalnych; inna liczba = `DownloadError`. |
| EGiB WFS | `UslugaZbiorcza` GetCapabilities: typy `ms:dzialki`, `ms:budynki`, `CountDefault=1000`, DefaultCRS 2180, tylko GML. `hits` (bbox 2x2 km Krakow `243000,565000,245000,567000`): 3306 dzialek; `COUNT=5000` przyciete do 1000 (+`next`); strony 0/1000/2000/3000 = 3306 unikalnych `gml:id` (`dzialki.<ID_DZIALKI>`), ostatnia strona `numberMatched=3306`. Bbox 500x500 m: 213 dzialek, 202 budynki. Pole `DATA` = **data odpowiedzi** (wszystkie 3306 obiektow: 2026-10-15); `POLE_EWIDENYJNE`, `KLASOUZYTKI_EGIB`, `GRUPA_REJESTROWA`, `KONDYGNACJE_*` = `brak_uprawnien` (w zrodle z diakrytykiem). Geometrie typu `CurvePolygon` (probka 2026-10-13). | Strona 1000; klucz `gml:id`; `DATA` poza GPKG (inaczej kazde pobranie = nowa wersja), wartosc w sidecarze; atrybuty zastrzezone opisac w USAGE; luki w powiatach bez integracji (usluga zbiorcza). |
| EGiB eksport | `HEAD latest_exports/eziudp_wfs/GPKG/1261.gpkg.zip` 87 175 594 B; `GET` z `Range` -> **200 i caly plik** (GUGiK ignoruje `Range`, K9). ZIP: jeden `1261.gpkg` (284 045 312 B, data wpisu 2026-10-14 22:58), sha256 ZIP `0ca84cfcd9d2...` (2026-10-13: `429ea82c6a8e...`, 79,4 MB). Warstwy (ogrinfo): `dzialki` 215 626, `budynki` 116 673, `transakcje` 233 604; EPSG:2180. Paczka woj. `12.gpkg.zip` 1 406 135 287 B, powiat 1465 107 671 024 B. | Eksport odswiezany co dobe (inny sha dzien po dniu) - `none`, `--force` zwykle daje nowa wersje. Zawartosc inna niz WFS (dodatkowo `transakcje`) - osobny segment. Rozpakowanie jednego GPKG lokalnie. |
| ZABAGED REST | `ZABAGED_POLOHOPIS/MapServer?f=pjson`: 149 warstw (bez grup), nazwy czeskie z diakrytykami; `maxRecordCount=2000`. Bbox 30x30 km Czeski Cieszyn (`-470000,-1130000,-440000,-1100000`, 5514): `returnCountOnly` Vodni tok 4979, Orna puda 2310; strony `resultOffset` 0/2000/4000 z `orderByFields=OBJECTID` = 4979 unikalnych, `exceededTransferLimit=true` na stronach pelnych. 22 warstwy pokrycia/hydrografii (tabela w planie D) potwierdzone w metadanych (typy geometrii). Klucz obiektu: `fid_zbg` (OBJECTID dla porzadku). | REST zamiast WFS (limit 2000 vs 1000). Liczba z `returnCountOnly` = kontrola kompletnosci. |
| ZABAGED WFS | `Vodni_tok`, BBOX `-448000,-1115000,-444000,-1111000,urn:ogc:def:crs:EPSG::5514`: `numberMatched=29`; po zamianie osi 0 (bez bledu). | EPSG:5514 ma osie **X=wschod, Y=polnoc** (pyproj `axis_info`) - kolejnosc X,Y jest zgodna z EPSG, to nie wyjatek uslugi (korekta specu sekcja 5). Zamiana osi daje cichy pusty wynik - test na prawdziwej odpowiedzi obowiazkowy. |
| ZABAGED kraj | ATOM `ZABAGED-GPKG/ZABAGED-GPKG.xml` -> feed zbioru -> `.../epsg-5514/ZABAGED-5514-gpkg-20261004.zip` (`length` 5 805 826 649, `updated` 2026-10-04T18:51:04+02:00) i `.../epsg-3045/...` (6 742 892 709). `Range` dziala (206). Centralny katalog: jeden `ZABAGED_RESULTS.gpkg`; poczatek GPKG (rozpakowane 108 MB z 40 MB ZIP): warstwy ASCII CamelCase (`VodniPlocha_c`, `TrvalyTravniPorost_c`, `Vinice_c`, ...). | URL datowany tylko z feedu (nie z szablonu); wydanie = `updated`; 5514 zgodny z wynikiem bbox. Nazwy warstw pliku krajowego inne niz REST (opis w USAGE). |
| RUIAN | `RUIAN/MapServer?f=pjson`: 12 `Obec`, 15 `Okres`, 17 `VyssiUzemneSamospravnyCelek` (kraj), 7 `KatastralniUzemi`, 19 `Stat`; warstwa 3 = `StavebniObjekt` (budynki, nie granice - probka 2026-10-13 mierzyla budynki). Bbox 30x30 km: obce 68, okresy 3, kraje 1 (`returnCountOnly`); pola `kod`, `nazev`, `okres`/`vusc`, `platiod`; `maxRecordCount` 1 000 000, `supportsPagination`. `HEAD services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` 253 029 856 B, `ETag`, `Last-Modified` 2026-10-14. | Poziomy z warstw 17/15/12/7; strona 1000 z `orderByFields=objectid`; kraj = SHP z sygnalem `http`. |
| HY-NET | WFS `geoserver/hy-n/wfs`: typy `HydroNode`, `WatercourseLink`, `WatercourseSeparatedCrossing`; `CountDefault=1000`. Bbox 30x30 km: `hits` 3783 / 3509 / 0; strony `STARTINDEX` 0..3000 = 3783 unikalnych `gml:id`; **ostatnia strona (783 obiekty) tez ma `next`**, a linki `next` maja schemat `http://`. ATOM `HY-NET` -> `.../HY-NET/HY-NET.zip` 194 208 037 B, `ETag`; kategoria CRS wpisu **ETRS89/TM33 (EPSG:3045)**; ZIP = jeden `HY-NET/HY-NET.gpkg`. | Ten sam algorytm co PRG (hits + STARTINDEX), `next` ignorowany. Wynik bbox w EPSG:5514 (DefaultCRS WFS), plik krajowy w EPSG:3045 - sidecar podaje faktyczny uklad kazdego pliku. |
| Ortofoto CZ | ATOM `ORTOFOTO/ORTOFOTO.xml` (23,7 MB, `ETag`): 16 301 wpisow, id `CUZK_ORTOFOTO_WRTO24.<rok>.<arkusz>`, rok 2025: 8494, 2024: 7708 (jeden aktualny plik na arkusz). Feed zbioru arkusza: link `openzu.cuzk.cz/opendata/ORTOFOTO/WRTO24.2024.CTES96.zip` (`length` 63 870 664, `updated` 2025-02-06). ZIP (koniec pliku, `Range`): `.jpg`, `.jgw` (S-JTSK), `.TM33N.jgw`, `.TM34N.jgw` - takze dla arkusza zachodniego `AS91`. | Rok w nazwie pliku - URL tylko z feedu; wydanie = rok + `updated` (`metadata`). Zapis JPEG + wszystkie JGW bez konwersji. |
| Indeks SM5 | `KladyMapovychListu/MapServer/24` (16 299 arkuszy): 99 godel ma **2 litery** (`AS22` ... `AS94`, As). | `core/parser_registry.py::CZ_SM5_PATTERN = ^[A-Z]{4}[0-9]{2}$` ich nie rozpoznaje: `detect_system("AS91")` zwraca `pl1992` (fallback), wiec arkusz konczy sie bledem godla PL (blad istniejacy, dotyczy tez DMR) - poprawka w planie D. |
| Ortofoto PL WCS | `DescribeCoverage` 2.0.1: `Orthoimagery_StandardResolution` i `Orthoimagery_High_Resolution` - ta sama siatka krajowa, krok **0,1 m**. Abstrakty: Standard = "najnowsze dostepne ortofotomapy", High = "ortofotomapy o pikselu 10 cm i mniejszym". `GetCoverage` 2.0.1 `SUBSET` 100x100 m (1000x1000 px): Standard 16,9 s, High 29,0 s, identyczne bajty (Krakow, sha `8f2a42855cf9`); 200x200 m (4 Mpx) Standard 64 s; 500x500 m z `SCALEFACTOR=0.4` (2000x2000 px, piksel 0,25 m) 176 s. Rano tego dnia Standard dawal timeouty 60 s (3 proby), High odpowiadal. | Wariant (`standard`/`high`) i piksel wyniku jawne; limit kawalka liczony w pikselach natywnych (4 Mpx = 200x200 m), timeout odczytu kawalka 300 s; Standard = ryzyko przejsciowe, nie zmiana zakresu (koordynator 2026-10-15). |

**Prototyp konwersji GML -> GPKG.** `pyogrio` 0.13.0 (GDAL 3.12.4, wheel
manylinux dla Python 3.13, ok. 100 MB na dysku) instaluje sie obok
`rasterio` 1.5.0 (GDAL 3.12.1) i oba dzialaja w jednym procesie. GDAL czyta
strony GML wszystkich czterech uslug z poprawna zamiana osi (PRG/EGiB
`urn:...:2180` N,E -> x=E; HY-NET i ZABAGED 5514 bez zamiany), krzywe EGiB
i typ "Unknown (any)" PRG. Scalenie 4 stron PRG z dedupe po `IIP_IDENTY`
(39 obiektow) zapisane `pyogrio.raw.write` dwa razy dalo identyczne bajty
GPKG przy `OGR_CURRENT_DATE` ustawionym na stala; `ogrinfo` czyta wynik
(MultiPolygon, EPSG:2180, zasieg E,N).

## 2. Licencje i koszty

GUGiK: istniejacy `_GUGIK_LICENSE` (`PL-PGiK-40a`, dane bezplatne na
podstawie art. 40a). CUZK: `_CUZK_LICENSE` (`CC-BY-4.0`); karty
[ZABAGED](https://geoportal.cuzk.gov.cz/Default.aspx?lng=EN&menu=24&mode=TextMeta&side=zabaged&text=dSady_zabaged),
[Ortofoto CR](https://geoportal.cuzk.gov.cz/Default.aspx?lng=EN&metadataID=CZ-CUZK-ORTOFOTO-R&metadataXSL=full&mode=TextMeta&side=ortofoto)
i [HY-NET](https://geoportal.cuzk.gov.cz/Default.aspx?lng=EN&metadataID=CZ-CUZK-HY_NET-V&mode=TextMeta&side=INSPIRE_dSady)
deklaruja dane otwarte CC BY 4.0; feedy ATOM maja `rights` "zadne podminky
neplati". Zaden produkt planow C i D nie wymaga oplaty ani logowania.
Licencje przenosi deskryptor (naglowek HTTP `License` nie wystepuje).

## 3. Wnioski dla planow

1. **Stronicowanie bez `next`.** Oba serwery WFS (MapServer GUGiK,
   GeoServer CUZK) maja bledny `next` (brak w srodku albo obecny na
   ostatniej stronie, schemat `http`), MapServer duplikuje obiekt za
   koncem wyniku. Kompletnosc wynika z liczby (`hits` /
   `returnCountOnly`) i unikalnych identyfikatorow, nie z linkow.
2. **Os BBOX = parametr kanalu, zgodny z EPSG** dla obu dostawcow
   (2180: N,E; 5514: X,Y). Zamiana daje pusty wynik bez bledu.
3. **GPKG z WFS/REST** wymaga biblioteki wektorowej: GML GUGiK/CUZK ma
   krzywe, typy mieszane i osie URN. Wybor: `pyogrio` (GDAL) jako nowa
   zaleznosc; bajty deterministyczne (sort po identyfikatorze, staly
   `OGR_CURRENT_DATE`, schemat z metadanych uslugi).
4. **Pola zmienne w czasie odpowiedzi** (EGiB `DATA`) poza GPKG, do
   sidecara - inaczej `unchanged` nigdy nie wystapi.
5. **Paczki GUGiK** bez `ETag`/`Last-Modified` (`none`); **pliki CUZK**
   z `ETag` (`http`); **pliki wskazywane feedem ATOM** z rokiem albo data
   w nazwie (ortofoto, ZABAGED kraj) - wydanie z feedu (`metadata`).
6. **Pliki krajowe** (PRG 377 MB, RUIAN 253 MB, HY-NET 194 MB, ZABAGED
   5,8 GB) tylko przez `--whole-country`, z rozmiarem z `HEAD`/feedu przed
   transferem (K7).
7. **Korekty dokumentow:** spec sekcja 5 ("X,Y mimo osi EPSG:5514") -
   X,Y jest zgodne z EPSG; plik krajowy HY-NET jest w EPSG:3045
   (kategoria feedu), nie w ukladzie wyniku WFS (5514); tabela klas ZABAGED ->
   BDOT10k w research 2026-08-10 sekcja 5.1 ma bledne odpowiedniki
   (np. 138 orna puda -> PTGN zamiast PTTR, 118 lom -> PTKM zamiast PTWZ,
   130 skaly -> PTKM) - nie nadaje sie na mapowanie danych.

## 4. Pytania (rekomendacje w planach)

1. **ZABAGED "mapowanie klas jak BDOT10k PT*" (spec 6, plan D).**
   Rekomendacja: Kartograf zapisuje 22 warstwy pokrycia/hydrografii
   ZABAGED pod nazwami zrodla, bez przeliczania klas na kody BDOT10k
   (tabela 5.1 research 2026-08-10 ma bledy); mapowanie po stronie
   konsumenta albo osobna, zweryfikowana decyzja.
2. **Nowa zaleznosc `pyogrio`** (GDAL wektorowy, ok. 100 MB). Rekomendacja:
   przyjac (alternatywa - wlasny parser GML z krzywymi i zapis GPKG przez
   SQLite - jest dluzsza i ryzykowniejsza).
