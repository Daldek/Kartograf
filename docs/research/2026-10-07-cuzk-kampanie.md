# CUZK: czy istnieja "kampanie" DMR 5G/4G — rekonesans na zywo (2026-10-07)

Cel: ustalic, czy CUZK udostepnia daty/kampanie (na potrzeby ADR-030: `newest`/`all`/`--min-year`)
i zaproponowac wspolny model kampanii dla PL/CZ/DE/SK. Bez zmian w kodzie, bez pobierania rastrow.

Surowe odpowiedzi: `<katalog-danych>/kartograf/e2e/2026-10-07-cuzk-kampanie/` (dalej `$E/`).
Zapytania male (najwiekszy plik: naglowek feedu ATOM 6 KB, odpowiedzi CSW ~45 KB).

## 0. Wniosek w skrocie

1. **ImageServer (dmr5g/dmr4g/dmp1g) NIE ma kampanii.** Katalog rastrow to 3 rekordy: jeden raster
   "Primary" na caly kraj + 2 poziomy przegladowe. Brak pol z data/rokiem/zrodlem. `mosaicRule`
   (lockRaster/where) nie ma czego wybierac. Usluga serwuje jedna, biezaca mozaike.
2. **Rok aktualizacji jest dostepny osobna usluga**: `ags.cuzk.gov.cz/arcgis/rest/services/Metadata/MapServer/20`
   ("Digitalni model reliefu CR", pole `ROK` = "Rok aktualizace", 14 poligonow, lata 2010-2026,
   zapytanie po punkcie/bboxie, `returnGeometry` dziala, SR 5514). Poligony sie NIE nakladaja
   (60 losowych punktow: 0 trafien wielokrotnych) — to mapa "rok ostatniej aktualizacji w danym
   miejscu", nie stos kampanii. Historii poprzednich wersji nie ma.
3. Pliki (`openzu`, ATOM) tez nie niosa roku pozyskania: ATOM `<updated>`/`Last-Modified` pliku =
   data publikacji/przetworzenia (masowo 2026-01-19, wybrane arkusze 2026-07-09), nie data skanowania.
4. Dla CZ: `all` = niewykonalne (brak historii), `newest` = jedyna dostepna wersja, `--min-year`
   mozna stosowac wobec `ROK` z Metadata/20 (granularnosc: rok, semantyka: "rok aktualizacji",
   nie dokladnie "rok pozyskania" — patrz 5).

## 1. Metadane ImageServer (`https://ags.cuzk.gov.cz/arcgis2/rest/services/{dmr5g,dmr4g,dmp1g}/ImageServer?f=json`)

Pliki: `$E/{dmr5g,dmr4g,dmp1g,dmp,dmp_obrazova_korelace,INSPIRE_Nadmorska_vyska}.service.json`,
lista uslug `$E/services.json`, `$E/root_arcgis.json`, `$E/root_arcgis2.json`.

| pole | dmr5g | dmr4g | dmp1g |
|---|---|---|---|
| `capabilities` | Catalog,Mensuration,Image,Metadata | to samo | Catalog,Image,Metadata |
| `hasMultidimensions` | false | false | false |
| `allowRasterFunction` | true | true | true |
| `mosaicMethods` | null | null | null |
| `allowedMosaicMethods` | NorthWest,Center,LockRaster,ByAttribute,Nadir,Viewpoint,Seamline,None | to samo | to samo |
| `defaultMosaicMethod` | Northwest | Northwest | Northwest |
| `pixelSizeX` | 2 | 5 | 2 |
| `maxImageWidth x Height` | 15000 x 4100 | to samo | to samo |
| `fields` katalogu | OBJECTID, Shape, Name, MinPS, MaxPS, LowPS, HighPS, Category, Tag, GroupName, ProductName, CenterX, CenterY, ZOrder, Shape_Length, Shape_Area | identyczne | identyczne |

Brak jakiegokolwiek pola daty/roku/zrodla. Opis uslugi (`description`) deklaruje jedynie
"skanowanie laserowe w latach 2009 az 2013" (dmr5g, dmr4g, dmp1g) — nieaktualne wobec punktu 2.
Inne uslugi: `dmp` (DMP z korelacji obrazu, tez jeden raster), `INSPIRE_Nadmorska_vyska` (ImageServer, to samo).

### Operacja `query` na katalogu rastrow — DZIALA, ale 3 rekordy

`GET .../dmr5g/ImageServer/query?where=1=1&outFields=*&returnGeometry=false&resultRecordCount=5&f=json`
(pliki: `$E/dmr5g.query5.json`, `dmr4g.query5.json`, `dmp1g.query5.json`, `dmr5g.query_geom.json`;
`returnCountOnly` -> `{"count":3}` dla wszystkich trzech).

```
{'OBJECTID': 1, 'Name': 'dmr5g_raster', 'MinPS': 0, 'MaxPS': 384, 'LowPS': 2, 'HighPS': 128,
 'Category': 1 (Primary), 'Tag': 'Dataset', 'GroupName': '', 'ProductName': '', 'ZOrder': None, ...}
{'OBJECTID': 2, 'Name': 'Ov_i02_L01_R00000010_C00000010.tif', 'Category': 2 (Overview), ...}
{'OBJECTID': 3, 'Name': 'Ov_i02_L02_R00000005_C00000005.tif', 'Category': 2 (Overview), ...}
```
Geometria rastra 1 = jeden prostokat calego kraju (EPSG:5514: x -904703.6..-431605.6,
y -1227414.12..-935118.12). `GroupName`/`ProductName` puste. `identify` z `returnCatalogItems=true`
w punkcie zwraca te same 3 rekordy (`$E/identify.json`). `.../1/info/keyProperties`:
`_FileList: dmr5g_raster.RASTER.1`, `ParentRasterType: Raster Dataset` — jeden zmozaikowany dataset.
`.../ImageServer/metadata` (XML Esri, `$E/dmr5g.metadata.json`): `CreaDate 20260710` = data
przebudowy uslugi (nie kampanii); `.../1/info/metadata` -> `CreaDate 20261007` (data dzisiejsza, generowane).

## 2. Wybor rastra / kampanii (`mosaicRule`, `download`, `file`)

`exportImage` z `mosaicRule` (bbox 100 m, size 8x8, odpowiedzi: `$E/exportImage_mosaicRule.txt`):
- `esriMosaicLockRaster` + `lockRasterIds:[1]` -> OK (ten sam raster, jedyny primary),
- `esriMosaicAttribute` + `where:"OBJECTID=1"` -> OK,
- `lockRasterIds:[2]` (overview) -> HTTP 200, brak bledu (nie badano, czy tresc inna),
- `where:"Name='xx'"` -> HTTP 200 bez bledu (where bez dopasowania nie dal komunikatu).
Wniosek: mechanizm istnieje, ale dostepne sa tylko elementy: 1 = dane, 2-3 = piramida.
Operacja `download` / `file`: `.../ImageServer/download` zwraca blad 400
("Requested operation is not supported by this service" — wywolanie bez parametrow, nie
potwierdza ostatecznie nieobecnosci operacji; `capabilities` nie zawiera `Download`, wiec nieobslugiwane).

## 3. Inne zrodla wersji/aktualizacji

### 3a. Metadata MapServer — NAJWAZNIEJSZE ZNALEZISKO
`https://ags.cuzk.gov.cz/arcgis/rest/services/Metadata/MapServer` ("Prostorova metadata produktu
Zememericskeho uradu"; capabilities Map,Query,Data; formaty JSON/geoJSON/PBF). Warstwy m.in.:
12 Ortofoto CR, 13 Archivni ortofoto, 14 Ortofoto CIR, 15/16 ZABAGED, **19 DMP - obrazova korelace**
(`rok`), **20 Digitalni model reliefu CR**, **21 Digitalni model povrchu CR**, 22-33 ZTM.

**Warstwa 20 (DMR)** — pola: `OBJECTID`, `ID`, `ROK` ("Rok aktualizace"), `SHAPE_Length/Area`;
poligony. Pliki: `$E/metadata_layer20.json` (opis), `metadata_layer20_all.json`,
`metadata_layer20_geom_generalized.json` (maxAllowableOffset=500 m, 2 KB — geometria jest uproszczona),
`metadata20_point_queries.txt`, `metadata20_multihit_sample.txt`.
```
id   rok   pole km2        id   rok   pole km2
525  2010  27699           518  2019   603
524  2011  22368           517  2020   812  ... 516 2022 1310, 515 2023 872,
523  2012    546           514  2024   311,  513 2025 1305
522  2013  23897           552  2026   223
521  2017   189            520  2018  1240
```
(14 rekordow; brak 2014-2016; suma ~81 600 km2 vs ~78 870 km2 powierzchni CR — rozbieznosc ~3 %
nie wyjasniona, prawdopodobnie nadmiarowe obwiednie; nie badano.) Zapytanie punktowe
(`geometry=x,y&geometryType=esriGeometryPoint&inSR=5514&spatialRel=esriSpatialRelIntersects&outFields=rok,id&returnGeometry=false`):
`-600000,-1100000` -> `[{'rok': 2024, 'id': 514}]`; `-745000,-1040000` -> `[{'rok': 2010}]`;
punkt poza krajem -> `[]`. 60 losowych punktow: 0 trafien wielokrotnych (wiec jeden rok na miejsce).
Zgodne z metadanymi ISO (3c): zakres czasowy zbioru 2010-2025.

**Warstwa 21 (DMP 1G, per arkusz SM5)** — pola: `SM5`, `JMENO`, `ROK_AKTUALIZACE`
(tekst), `VELIKOST_SOUBORU`, `POCET_BODU`, bbox S-JTSK, `MIN_H/MAX_H`; 16 301 rekordow;
rozne wartosci roku: `2009, 2010, 2011, 2013` (`$E/metadata_layer21_query.json`) — tu rok
pozyskania skanowania jest PER ARKUSZ. Przyklad: `AS00 -> 2011`. **Warstwa 19** (DMP z korelacji):
`rok` w {2024, 2025} (2 poligony). Dla DMR odpowiednika per arkusz SM5 NIE znaleziono
(warstwa 20 to ~14 poligonow regionalnych) — "nie ustalono", czy DMR 5G ma gdzies tabele per SM5.

### 3b. ATOM (`https://atom.cuzk.gov.cz/`) i openzu
- Feed `DMR5G-SJTSK/DMR5G-SJTSK.xml` (24,2 MB, `last-modified: 2026-07-10`): `<updated>` feedu
  2026-07-09, per `<entry>` (arkusz SM5, np. BENE09) `<updated>` + `inspire_dls:spatial_dataset_identifier_code`
  + `georss:polygon` + link `describedby` (CSW). Wzor wpisu: `$E/dmr5g_sjtsk_feed_head.xml`,
  per-arkusz: `$E/ds_BENE09.xml` (`openzu.../DMR5G/epsg-5514/BENE09.zip`, `length=4194194`).
- Rozklad `<updated>` (6 probek Range po 30 KB, `$E/updated_samples.txt`): prawie wszystkie
  2026-01-19 13:xx-14:xx (jednorazowa przebudowa), kilka 2026-07-09 07:55-07:56 (np. BENE09).
  `HEAD` zipow (`$E/openzu_head.txt`): `Last-Modified` zgodny z `<updated>` (BENE09 2026-07-09,
  BENE10 2026-01-19; DMR4G-TIFF BENE09 2026-07-09). **To data publikacji pliku, nie pozyskania.**
  Przydatna jedynie do wykrywania zmiany pliku (ETag/Last-Modified) — cache-busting, nie kampanie.
- Nazwa pliku nie niesie daty (`BENE09.zip`); `DMR4G-TIFF` `last-modified` j.w.
- Nazwy tematow ATOM: `DMR5G-SJTSK`, `DMR5G-ETRS89`, `DMR4G-*` (feedy `DMR5G-TIFF`/`DMR5G-ASC` -> 404;
  strona glowna atom.cuzk.gov.cz jest SPA bez linkow w HTML).
- `openzu.../opendata/` -> 403 (brak listingu).

### 3c. Geoportal CSW (ISO 19139) — wymaga "przegladarkowego" User-Agenta
`https://geoportal.cuzk.gov.cz/SDIProCSW/service.svc/get?REQUEST=GetRecordById&SERVICE=CSW&VERSION=2.0.2&OUTPUTSCHEMA=http://www.isotc211.org/2005/gmd&ELEMENTSETNAME=full&Id=<ID>`
— z domyslnym UA curl: 302 -> `Dokumenty/Podminky.pdf`; z UA `Mozilla/5.0 ... Kartograf-research`: 200.
Pliki: `$E/csw_DMR5G-V.xml` (Id `CZ-CUZK-DMR5G-V`), `csw_CZ-CUZK-DMR5G-ETRS89-V.xml`,
`csw_CZ-CUZK-DMR4G-V.xml`, `csw_CZ-CUZK-DMP1G-V.xml`.
- DMR 5G/4G: `gml:TimePeriod` **2010-2025**; data rewizji 2026-06-01, `maintenanceAndUpdateFrequency=continual`,
  `dateOfNextUpdate 2026-12-31`; lineage: "DMR 5G je Zememerickym uradem prubezne verifikovan v souvislosti
  s plosnou aktualizaci ZABAGED a aktualizovan metodami digitalni stereofotogrammetrie a na vybranych
  uzemich metodou leteckeho laseroveho skenovani." Abstrakt: "Model vznikl z dat porizenych ... v letech
  2009 az 2013. Dokoncen byl k 30. 6. 2016 na cele uzemi CR."
- DMP 1G: okres czasowy **2009-2013**, bez aktualizacji.
Wniosek: dokumentowo CUZK potwierdza, ze DMR to produkt "zywy" (rolling update), bez archiwum wersji.

### 3d. Czego nie znaleziono
Brak uslug "Aktualizace DMR 5G" ani osobnego feedu z datami kampanii; brak wersjonowanych URL-i
(`.../DMR5G/2013/...`); brak archiwum starych mozaik. `ZABAGED_VRSTEVNICE` i uslugi 3D nie badane.

## 4. Wspolny model kampanii (propozycja dla PL/CZ/DE/SK)

Zrodla PL (skorowidz GUGiK), CZ (Metadata/20), DE (notatki: skorowidze tylko do pokrycia/rocznika:
BB CSV, SN shapefile; nazwy kafli arytmetyczne; federacja 17 modeli), SK (WCS caly kraj, pliki tylko
caly kraj/LOT 9-15 GB, `LOT` = naturalna kampania) pokazuja, ze kampania jest jednostka WYBORU
(zakres + rok + sposob pobrania), a nie zawsze jednostka PLIKU.

### Pola `Campaign` (dataclass, kraj-niezalezna)
Obowiazkowe:
- `id: str` — stabilny identyfikator w obrebie zrodla: PL `<id zlecenia>` z URL (lub `u<sha1>`);
  CZ `cz-<rok>` albo `current`; DE `<land>-<rocznik>`; SK `lot-<nr>` / `current`.
- `acquired_year: int | None` i `acquired: date | None` — **data/rok pozyskania** (PL: `aktualnosc`,
  dokladna data; CZ: rok z Metadata/20; DE: rocznik; SK: rok LOT). Pelna data opcjonalna, rok
  wystarcza do `--min-year`. `None` = "nie znamy" (nie 0).
- `date_kind: "acquisition" | "update" | "publication"` — **semantyka** daty (PL acquisition; CZ `update`
  — "rok aktualizacji"; ATOM-owy `<updated>` to `publication` i NIE nadaje sie do `--min-year`).
- `source: str` — slownik: `als` (skan laserowy), `photogrammetry`, `image_correlation`, `mixed`, `unknown`
  (PL: z URL/warstwy; CZ: `unknown`/`mixed` — lineage CUZK mowi o stereofotogrametrii i wybranym ALS).
- `access: AccessRef` — jak pobrac: PL URL pliku; CZ ImageServer+bbox, openzu-zip; SK WCS; DE WCS/kafle.
Opcjonalne:
- `extent`/`completeness` — `full | partial | unknown` i/lub geometria zasiegu (PL: flaga
  `calyArkuszWypelnionyTrescia` tylko jako podpowiedz, nie miara; CZ: poligon z Metadata/20 przecinany
  z arkuszem — **zasieg znany a priori**, w przeciwienstwie do PL).
- `product_generation`, `native_crs`, `vertical_crs`, `license` — maja juz deskryptory/sidecar.
- `scope: "sheet" | "region" | "country"` — czy kampania dotyczy arkusza (PL), poligonu regionalnego (CZ, DE-landy),
  czy calego kraju/produktu (SK, brak historii).
- `selectable: bool` — czy da sie pobrac TA kampanie osobno (PL tak; CZ nie: tylko biezaca mozaika,
  nawet gdy rok znamy z Metadata/20; DE per land rozne).

### Interfejs zrodla (provider)
`campaigns_for(sheet_or_bbox) -> list[Campaign]` z flaga `history: "full" | "current_only" | "none"`:
- `full` (PL): wszystkie rekordy skorowidza -> `newest` = max, `all` = lista.
- `current_only` (CZ DMR, SK, DE-WCS): dokladnie 1 kampania "biezaca" (mozaika) z rokiem z metadanych,
  jesli dostepny; `all` == `newest` (jedna pozycja, bez bledu), `selectable=False`.
- `none`: brak jakichkolwiek dat -> pojedyncza kampania `id="current"`, `acquired_year=None`.

### Mapowanie `newest` / `all` / `--min-year`
| strategia | PL | CZ (DMR 5G/4G) | kraj bez dat |
|---|---|---|---|
| `newest` | najnowsza `aktualnosc` (ADR-028) | biezaca mozaika; `acquired_year` = `ROK` z Metadata/20 (lub `None`) | biezaca, `None` |
| `all` | wszystkie rekordy | rowne `newest` (1 kampania) + `Info:` "zrodlo nie udostepnia historii" | j.w. |
| `--min-year N` | odrzuc kampanie z `acquired_year < N` | patrz nizej | patrz nizej |

`--min-year` dla zrodel o rocznej granularnosci i niepewnym `date_kind`:
- CZ: porownuj `ROK` (update-year) z N; jesli `ROK < N` -> **brak pokrycia** (`NoCoverageError` z podpowiedzia:
  "najnowsze dane CZ z <ROK>, wymagane >= N") — NIE cicha degradacja. `ROK` jest dolnym oszacowaniem
  roku pozyskania? Nie: rok aktualizacji >= rok pozyskania tego fragmentu najczesciej rowny (2010-2013 ALS),
  ale dla aktualizacji stereofotogrametrycznych to rok opracowania — **nie ustalono**, czy rowny dacie lotu.
  Zalecenie: filtrowac wg `ROK`, w sidecarze zapisac `date_kind="update"` i `extra.year_source="cuzk.Metadata/20"`.
- Arkusz/bbox przecinajacy kilka poligonow: kampania CZ per wycinek -> `acquired_years=[...]`;
  `--min-year` stosowac do **minimum** (wszystkie czesci musza spelniac) albo wymagac `--allow-mixed`; decyzja produktowa.
- Zrodlo bez roku (`None`): przy `--min-year` zachowanie jawne: odrzucic z `Warning:` (domyslnie) —
  uzytkownik, ktory podaje dolna granice, oczekuje gwarancji; flaga `--include-undated` jako wyjscie.

### Gdzie model wymaga ostroznosci wobec ADR-030
- Uklad `kampanie/<data>_<id>/...` (ADR-030 c): CZ `current_only` ma jedna kampanie — katalog moglby byc
  `kampanie/<ROK>_current/` albo bez `kampanie/` (dla `selectable=False` i `scope!="sheet"` rozsadniej
  pomijac `kampanie/`, bo pliki to wycinki bbox, a nie dostawy; **do decyzji**). Wycinek CZ zmienia sie pod
  tym samym URL (rolling update), wiec `data` w nazwie nie gwarantuje niezmiennosci: zapisac w sidecarze
  `ROK` i date pobrania; kontrola zmiany przez ETag/Last-Modified plikow openzu (nie dla exportImage).
- `newest` "sprawdza, czy jest nowsza kampania" (ADR-030 b): dla CZ odpowiednik = ponowne zapytanie Metadata/20
  (maly JSON) + porownanie `ROK`; cache `record_cache` 7 d jak w PL.
- ATOM `<updated>` mozna uzyc wylacznie jako sygnalu "plik zmieniony" (dla DMR 4G z plikow), nie jako daty kampanii.

## 5. Wnioski i luki ("nie ustalono")
- Ustalono: ImageServer = 1 mozaika; rok aktualizacji dostepny przez Metadata/20 (rok, regionalnie); DMP per SM5 (Metadata/21);
  ATOM/openzu = tylko data publikacji pliku; CSW = rolling update 2010-2025.
- Nie ustalono: (1) czy `ROK` oznacza dokladnie rok lotu/skanowania, czy rok opracowania aktualizacji;
  (2) przyczyna sumy powierzchni ~3 % > powierzchnia CR (nakladanie/obwiednie; probka 60 pkt bez nakladan);
  (3) czy istnieje warstwa/tabela rocznika DMR per arkusz SM5 (jak dla DMP, warstwa 21);
  (4) czy `exportImage` z `lockRasterIds` na pozycjach 2/3 zwraca inna tresc (przegladowa) — nieistotne dla kampanii;
  (5) wielkosc i stabilnosc identyfikatorow `id` w Metadata/20 (np. 552 dla 2026 poza ciagiem 513-525 — rekord dodany pozniej;
  nie zakladac stalosci id, kluczowac po `ROK`);
  (6) geometria pelna poligonow (pobrana tylko uogolniona 500 m; pelna wymagalaby wiekszej odpowiedzi — zalecane `query` per bbox
  z `outSR=5514` zamiast pobierania calosci);
  (7) DE/SK: wnioski o modelu oparte wylacznie na notatkach z pamieci, bez nowych zapytan.
