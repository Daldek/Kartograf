# Spec: Katalog produktow GUGiK i CUZK oraz raport dostepnosci (podprojekt 3 roadmapy v1.0.0)

**Data:** 2026-10-13
**Status:** PROJEKT - do akceptacji uzytkownika (decyzje otwarte: sekcja 9)
**Wersja docelowa:** od 0.9.0 (strumien; kazdy plan = osobne wydanie)
**Warunek wstepny:** wydanie 0.8.0 (magazyn wersjonowany ADR-036, CLI = API
ADR-037, jawny tryb wycinka ADR-038, grupy komend CLI wg typu danych -
backlog "Do 0.8.0", decyzja 2026-10-13)
**Dokumenty zrodlowe:**
- `docs/research/2026-10-13-katalog-produktow/raport.md` (inwentaryzacja,
  statusy produktow) i `probki.md` (dowody dostepnosci, 212 probek)
- `docs/SCOPE.md` 3.3 (podprojekt 3: "Katalog GUGiK i gotowe dane";
  kazdy nowy produkt od razu wersjonowany, z wycinkiem i sidecarem)
- `docs/ARCHITECTURE.md` 1 (deskryptory jako dane), 3.1 (`storage_subdir`),
  3.3 (uklad `data/`), 5 (nowe zrodlo); STANDARDS 7.3 (CLI tylko tlumaczy)
- backlog `docs/PROGRESS.md`: "NMT 0,5 m i wszystkie rozdzielczosci GUGiK",
  "Sprawdzenie dostepnosci danych dla obszaru przed pobraniem"

---

## 1. Kontekst i cel

Inwentaryzacja 2026-10-13 objela pelne katalogi obu producentow: GUGiK
(sekcja "Dane" geoportalu, 32 uslugi modulu "Pobierz dane", listy WFS/WCS/
ATOM/OGC API) i CUZK (114 uslug ATOM, 73 uslugi ArcGIS, dokument form
udostepniania ZU). Kartograf obsluguje dzis 6 produktow GUGiK (NMT 1 m,
NMT 5 m, NMPT 1 m, orto, LAZ, BDOT10k) i 2 produkty CUZK (DMR 5G raster,
DMR 4G TIFF). Raport klasyfikuje ok. 30 produktow GUGiK i 20 grup CUZK jako
`do dodania`.

Trzy obserwacje ksztaltuja ten spec:

1. **Luka w produkcie obslugiwanym.** Skorowidze GUGiK 2025 maja NMT
   wylacznie w 0,5 m i 5 m, a NMPT w 73% w 0,5 m; Kartograf zna tylko 1 m
   i 5 m. Nowe loty sa niewidoczne.
2. **Uzytkownik nie widzi, co jest dostepne, zanim pobierze.** Dla bboxa
   chce znac lata nalotow, uklady, rozdzielczosci i uklady wysokosci oraz
   kombinacje z pelnym pokryciem (prosba 2026-10-13).
3. **Kanaly sie powtarzaja.** Wszystkie produkty `do dodania` korzystaja
   z szesciu wzorcow dostepu (raport sekcja 6). Dodawanie produktow ma byc
   wpisem deskryptora + konfiguracja kanalu, nie nowym providerem per
   produkt.

Cel: (a) jeden rejestr wariantow produktu (rozdzielczosc, uklady, warstwa
skorowidza) jako zrodlo prawdy dla walidacji, `--help`, segmentu i wyboru
rekordu; (b) raport dostepnosci obszaru bez pobierania; (c) generyczne
silniki kanalow; (d) produkty z raportu w falach wg priorytetu.

**Poza zakresem tego specu:** produkty `poza zakresem` z raportu (odplatne,
tylko podglad, duplikaty INSPIRE, dane nieprzestrzenne), manifest projektu
(podprojekt 2), scalanie PL+CZ (R6), wtyczka QGIS i GUI (4, 5).

## 2. Decyzje proponowane

| # | Decyzja | Odrzucone |
|---|---|---|
| K1 | Wariant produktu = rekord rejestru (`ProductVariant`: produkt, kraj, rozdzielczosc w m jako `Decimal`, uklad poziomy, uklad wysokosci, format, kanal, warstwa/typ skorowidza, pole rozdzielczosci w skorowidzu). Walidacja CLI/API, `--help`, `storage_subdir` i filtr rekordow skorowidza czytaja rejestr | kolejne stale `("1m","5m")` w `options.py`, providerze i `FileStorage` (dzis 7 miejsc - backlog) |
| K2 | Etykieta rozdzielczosci w CLI i segmencie: `0.5m`, `1m`, `5m` (kropka dozwolona w segmencie `[a-z0-9.-]`, regula 8 ARCHITECTURE 3.3); API przyjmuje te same napisy | `50cm` (dwie jednostki w jednym parametrze); `0_5m` |
| K3 | Raport dostepnosci jako funkcja biblioteki `check_availability(...) -> AvailabilityReport` + podkomenda grupy CLI `kartograf <grupa> availability` (np. `kartograf elevation availability`; ADR-037: decyzje w bibliotece, CLI drukuje) | flaga `--dry-run` w `download` (miesza dwa wyniki w jednym typie); rozszerzenie `--check-updates` (ten porownuje z magazynem, nie z obszarem) |
| K4 | Raport odpowiada na pytanie "czy dla obszaru jest komplet PELNYCH arkuszy danej kombinacji" (rok x uklad poziomy x rozdzielczosc x uklad wysokosci) wylacznie ze skorowidza: kombinacja jest kompletna, gdy suma poligonow jej arkuszy z `czy_ark_wypelniony = TAK` pokrywa obszar przeciety z ladem PL (maska PRG, jak wycinki ADR-035). Arkusze `NIE` i brakujace arkusze sa wypisane z godlami; zadnych pobran ani pomiaru tresci. Podstawa: pomiar `pokrycie.md` (arkusze TAK = 100% danych na ladzie, poligony TAK stykaja sie bez szczelin; "pelny" = w granicach PL) | procent pikseli z pomiaru tresci i opcja `--measure` (pobieranie w raporcie, wbrew "bez pobierania"); prog 99,9%; obszar bez maski ladu (bbox przy brzegu nigdy kompletny) |
| K5 | Nowe kanaly jako generyczne silniki sterowane deskryptorem (`AccessChannel.endpoint` + nowe pole `params`): `index_files` (skorowidz WMS/WFS -> plik), `unit_package` (paczka per jednostka administracyjna: URL z szablonu albo z `GetFeatureInfo`), `wcs_bbox`, `feature_bbox` (WFS / OGC API Features / ArcGIS query z paginacja), `atom_files` (CUZK: szablon URL arkusz/kafel/KU/obec/kraj), `arcgis_image` (istniejacy) | provider per produkt (dzis wzorzec `providers/pl/*.py`) |
| K6 | Kazdy nowy produkt od razu w magazynie wersjonowanym (ADR-036), z sidecarem i sygnalem swiezosci kanalu: skorowidz `index` (akt_data/nr_zglosz), CUZK `http` (ETag/Last-Modified - openzu je podaje), ATOM `<updated>` jako `metadata`, WFS/OGC API bez sygnalu = `none` | wyjatki od magazynu dla danych wektorowych |
| K7 | Dane krajowe w jednym pliku (ZABAGED 5,8 GB, Data50, HY-NET, PRG kraj) domyslnie przez kanal obszarowy (`feature_bbox`); plik krajowy na jawne zadanie `--whole-country` z ostrzezeniem o rozmiarze (z `HEAD`) - decyzja uzytkownika 2026-10-13: udostepniamy | domyslne pobieranie calego kraju dla malego bboxa; brak opcji krajowej |
| K8 | Wybor wariantu pozostaje jawny (zasada "bez wartosci domyslnych wplywajacych na dane", 0.8.0): `--resolution` wymagane tam, gdzie produkt ma >1 rozdzielczosc; raport dostepnosci podpowiada wartosci | automatyczny wybor "najlepszej" rozdzielczosci |
| K9 | Pobieranie bez `Range` po stronie GUGiK `opendata` (zmierzone): ortofotomapa 5 cm = 1,1 GB/arkusz; wycinek orto wylacznie przez WCS (`orto` + `--cutout`), arkusze orto z ostrzezeniem o rozmiarze z `HEAD Content-Length` przed pobraniem | czesciowe pobieranie arkusza (serwer nie wspiera) |
| K10 | Produkty spoza GUGiK hostowane na geoportalu (POLSA LandCover) - pominiete na razie (decyzja uzytkownika 2026-10-13); powrot dopiero z potwierdzona licencja | traktowanie jako produkt GUGiK |

## 3. Rejestr wariantow i NMT/NMPT 0,5 m (plan A)

### 3.1 Model

`ProductVariant` w `kartograf/sources/` (dane, zero IO):

```python
@dataclass(frozen=True)
class ProductVariant:
    product: str               # "nmt", "nmpt", "orto", ...
    country: str               # "PL" | "CZ"
    resolution_m: Decimal | None
    horizontal: str            # "pl_1992" | "pl_2000" | "cz_sjtsk" | "cz_tm33"
    vertical_crs: str | None   # "EPSG:9651" | "EPSG:9650" | "EPSG:8357" | None
    channel: TransportKind
    index_ref: IndexRef | None # WFS/WMS skorowidza + filtr pola rozdzielczosci
    label: str                 # "0.5m" | "1m" | "5m" (CLI, segment)
```

Rejestr wypelnia sie z deskryptorow (`SourceDescriptor.variants`).
`download/options.py` buduje z niego dopuszczalne wartosci i komunikaty
`Error:`; `FileStorage` - segment `nmt/pl_<uklad>_<label>_<vcrs>`;
`GugikProvider` - filtr rekordow skorowidza po `char_przestrz`.

### 3.2 Zakres

- PL: NMT 0,5 m (EVRF2007; KRON86 jesli skorowidz ma rekordy - do
  zmierzenia w planie), NMPT 0,5 m (EVRF2007, KRON86), istniejace 1 m
  i 5 m przeniesione do rejestru bez zmiany zachowania.
- Wycinek WCS (`--cutout`) zostaje 1 m: WCS GUGiK serwuje kompozycje 1 m
  (ADR-035); `--cutout --resolution 0.5m` = `Error:` z podpowiedzia
  (arkusze bez `--cutout`).
- Kampanie, wybor roku (ADR-032), `full_sheet/` (ADR-033) dzialaja per
  wariant bez zmian - wariant to inny segment, wiec inne wersje.

### 3.3 Kryteria akceptacji

- `kartograf elevation download --sheet N-33-58-A-c-1-4 --product nmt --resolution
  0.5m --vertical-crs EVRF2007 -o <dir>` zapisuje
  `nmt/pl_1992_0.5m_evrf2007/.../N-33-58-A-c-1-4.asc` (probka
  `pl.gugik.nmt_0_5m`: 4202x2600 px, piksel 0,5 m) jako wersje z etykieta
  `<akt_data>_84020` (ADR-036).
- Zadne miejsce w kodzie poza rejestrem nie wymienia literalow
  rozdzielczosci; test zgodnosci rejestr <-> `--help` <-> walidacja CLI
  i API.
- Test zgodnosci CLI = API (`tests/test_parity.py`) dla 0,5 m.

## 4. Raport dostepnosci danych wysokosciowych (plan A, CZ w planie B)

Cel (prosba uzytkownika 2026-10-13): przed pobraniem wiedziec, dla jakich
lat, ukladow, rozdzielczosci i ukladow wysokosci obszar ma **komplet
pelnych arkuszy** - na podstawie skorowidza, bez pobierania danych.
Zakres: grupa `elevation` (NMT, NMPT, LAZ). Inne grupy - tylko gdy pojawi
sie potrzeba.

### 4.1 API

```python
check_availability(
    *, product: str, country: str,
    bbox: BBox | None = None, geometry: Path | None = None,
    sheet: str | None = None,
    year: int | None = None, min_year: int | None = None, max_year: int | None = None,
    cache: bool | MetadataCache = True,
) -> AvailabilityReport
```

`AvailabilityReport`: `area` (obszar w EPSG:2180 przeciety z ladem PL),
`combinations: list[AvailabilityCombination]`, `notices`, `ok`.

`AvailabilityCombination`: `year`, `acquisition_dates` (min-max
`akt_data`), `campaigns` (`nr_zglosz`), `horizontal` (`PL-1992`/`PL-2000`
+ strefa), `resolution` (etykieta K2), `vertical_crs`, `format`,
`complete` (K4), `sheets_full` (godla `TAK`), `sheets_partial` (godla
`NIE`), `uncovered` (czy czesc obszaru nie ma w tej kombinacji zadnego
arkusza), `download_hint` (gotowe flagi `kartograf elevation download`).

Kompletnosc liczona geometrycznie na poligonach skorowidza (rasteryzacja
na siatce 1 m obszaru albo operacje wektorowe - do wyboru w planie;
pomiar w `pokrycie.md` uzywal rasteryzacji).

### 4.2 CLI

```
kartograf elevation availability --product nmt --country pl --bbox 566000,243000,569000,246000
```

Tabela posortowana: rok malejaco; kolumna "komplet pelnych" (`tak` /
`nie: 2 niepelne, brak arkuszy dla czesci obszaru`); `--details`
wypisuje godla arkuszy niepelnych i kombinacje bez pokrycia; stopka
z `download_hint` dla najnowszej kompletnej kombinacji. `--json` wypisuje
strukture `AvailabilityReport` (ten sam ksztalt co API). Kod wyjscia 0
takze przy braku danych (to raport), 1 przy bledzie zrodla.

### 4.3 Zrodla danych raportu

- PL NMT/NMPT/LAZ: skorowidze WFS (`NumerycznyModelTerenu{EVRF2007,KRON86}`,
  `NumerycznyModelPokryciaTerenu*`, `DanePomiaroweLidar*`) - pola `godlo`,
  `akt_rok`, `akt_data`, `char_przestrz`, `uklad_xy`, `uklad_h`,
  `nr_zglosz`, `czy_ark_wypelniony`, geometria arkusza; zapytanie BBOX
  z paginacja (`next`), wynik w cache metadanych (ADR-037); maska ladu:
  `providers/pl/prg.py::fetch_land_mask`.
- CZ (plan B): DMR/DMP nie maja lotow ani flagi pelnosci - raport podaje
  dostepne produkty i arkusze dla obszaru (indeks `KladyMapovychListu`,
  `PODIL`) oraz date z `<updated>` feedu ATOM i `Last-Modified` pliku.

### 4.4 Kryteria akceptacji

- Krakow (bbox E 565000-569000, N 242000-246000): kombinacje 2019, 2022,
  2023, 2024, 2025 (1 m, PL-1992, EVRF2007) kompletne; 2018 1 m
  niekompletna (czesc obszaru bez arkuszy) - zgodnie ze skorowidzem
  z 2026-10-13 (`pokrycie.md`); test offline z fixtur prawdziwych
  odpowiedzi WFS.
- Pomorze (E 339000-343000, N 744800-747000): 2025 0,5 m - niekompletna,
  4 arkusze niepelne z godlami (skorowidz pokrywa caly lad, ale wszystkie
  arkusze `NIE`); 2022 1 m - niekompletna wylacznie przez brak arkusza
  dla 35 153 px ladu (ok. 0,9 ha przy pikselu 0,5 m), 3 arkusze `TAK`;
  morze (ok. 35% bboxa) nie wplywa na wynik.
- Brak pobran plikow danych (test: atrapa transportu odrzuca kazdy URL
  `opendata`).
- Zgodnosc CLI `--json` = API (bajtowo przy zamrozonym zegarze).

## 5. Silniki kanalow (wchodza razem z pierwszym produktem, ktory ich uzywa)

| Silnik (`TransportKind`) | Wejscie z deskryptora | Produkty |
|---|---|---|
| `WMS_SHEET_INDEX` / `WFS` (istnieja) | skorowidz, pola rekordu | NMT/NMPT 0,5 m, OI, orto ukosna, mesh 3D |
| `DIRECT_FILES` + `unit_package` | szablon URL per jednostka (`{teryt}`, `{woj}`, `{rok}`) albo warstwa WMS z linkiem w `GetFeatureInfo` | BDOT10k archiwalny, modele 3D budynkow/drzew, EGiB paczki, PRG paczki, osnowy, BDOO |
| `WCS` (istnieje) | coverage, format, siatka | orto Standard/High/True |
| `WFS` / `OGC_API_FEATURES` / `ARCGIS_QUERY` (`feature_bbox`) | typ/kolekcja/warstwa, limit strony, kolejnosc osi BBOX | PRG, PRNG, EGiB WFS; CZ ZABAGED, RUIAN, HY-NET, Geonames, Bodova pole |
| `DIRECT_FILES` (`atom_files`, CZ) | szablon `openzu.../<PRODUKT>/epsg-<5514/3045>/<arkusz>.zip`, indeks arkuszy | DMR 5G/4G LAZ, DMP 1G, DMP OK, ortofoto, ZTM, warstwice |
| `ARCGIS_IMAGE` (istnieje) | usluga ImageServer | DMP 1G/OK raster (wycinek) |

Wymagania wspolne (z pulapek raportu):
- Kolejnosc osi BBOX jest parametrem kanalu i ma test na prawdziwej
  odpowiedzi (CUZK ArcGIS WFS: X,Y mimo osi EPSG:5514; GUGiK WFS: N,E).
- Typy/kolekcje WFS i coverage WCS czytane z `GetCapabilities` (wzorzec
  ADR-020 errata) - przyklady z katalogow GUGiK bywaja nieaktualne (PRNG
  `ms:Wsie`, POLSA `Land_use_classification`).
- Odpowiedz HTML/wyjatek OGC przy kodzie 200 = blad pobrania (EGiB WFS bez
  parametrow zwraca HTML RCN).
- Timeouty i ponowienia jak dzis (STANDARDS 13.4); ATOM GUGiK z dluzszym
  timeoutem (zmierzony timeout 120 s).

## 6. Produkty - fale (plany A-E, rewizja kolejnosci 2026-10-13)

Kazdy plan = jedna grupa CLI (6.1) albo jej czesc + wydanie. Kolejnosc
wynika z priorytetow raportu (W/S/N) i zaleznosci: plany A i B rozszerzaja
istniejace tory (skorowidz GUGiK, arkusze CZ z `openzu`, `exportImage`)
i nie potrzebuja nowych silnikow; silniki `unit_package` i `feature_bbox`
(sekcja 5) powstaja w planie C razem z pierwszymi produktami - silnik bez
produktu nie ma czym byc zweryfikowany na zywo.

**Plan A - `elevation` PL (W), od 0.9.0:** rejestr wariantow (K1-K2),
NMT i NMPT 0,5 m (sekcja 3), `kartograf elevation availability` dla PL
(sekcja 4, K4: komplet pelnych arkuszy wg skorowidza, maska ladu PRG).

**Plan B - `elevation` CZ (W/S):** `cz.cuzk.dmpok` (TIFF 0,5 m arkusze
SM5/TM33 + wycinek ImageServer), `cz.cuzk.dmp1g` (LAZ + wycinek
ImageServer), DMR 4G TIFF ETRS89/EVRS, LAZ CZ (DMR 5G/4G, DMP 1G/OK;
`elevation download --product laz --country cz`), raport dostepnosci CZ.
Wszystko na istniejacym torze arkuszy CZ (`download/cz_sheets.py`,
indeks `KladyMapovychListu`, szablon `openzu`) i rejestrze wariantow
z planu A. Zaleznosc tylko od A.

**Plan C - dane jednostkowe i obszarowe PL (W/S) + silniki:**
`unit_package` z `landcover --source bdot10k --year` (archiwum 2014-2025,
GML/SHP, decyzja 9.3) i `models3d` (budynki LoD1/LoD2 per powiat);
`feature_bbox` z `boundaries` (PRG: WFS bbox, paczki woj./kraj,
`--whole-country`, K7) i `cadastre` (EGiB: paczki powiatowe GPKG, WFS
bbox).

**Plan D - CZ dane obszarowe i obrazy (W/S):** `landcover --source
zabaged` (`feature_bbox` ArcGIS WFS/REST z kolejnoscia osi X,Y;
`--whole-country` = GPKG 5,8 GB; mapowanie klas jak BDOT10k PT*, research
2026-08-10 sekcja 5), `boundaries` RUIAN, siec HY-NET, `imagery`:
ortofoto CZ (SM5, zapis jak w zrodle: JPEG + JGW S-JTSK i TM33N) oraz
wycinek ortofotomapy PL z WCS w magazynie (`imagery download --product
orto --cutout`, Standard/High; dzis tylko poza magazynem, D27).
Zaleznosc: silniki z C.

**Plan E - niski priorytet (N), pojedynczo wg potrzeb:** NMT 100 m,
obrazy intensywnosci, true orto, orto ukosna, mesh 3D, modele drzew,
wizualizacje BDOT10k, BDOO, PRG adresy i granice specjalne, PRNG (RP
i swiat), osnowy, RCN, quasi-geoida PL-geoid2021; CZ: warstwice,
Data50/250, katastralni mapa, Geonames, ZTM, QGZU, Bodova pole,
geomorfologia.

Dla kazdego produktu plan zawiera: wpis deskryptora (klucz z raportu),
segment `data/` (regula ARCHITECTURE 3.3), sygnal swiezosci (K6), fixtury
z prawdziwych odpowiedzi (probki z `probki.md` jako zrodlo), scenariusz
zgodnosci CLI = API, wpis CHANGELOG/USAGE/SCOPE.

### 6.1 CLI - grupy komend wg typu danych (decyzja uzytkownika 2026-10-13)

Kazdy typ danych ma grupe z podkomendami `download`, `list-sources`
i `availability` (sekcja 4), wylacznie z flagami tej grupy. Istniejace
komendy przebudowane w 0.8.0 (backlog "Do 0.8.0", BREAKING, bez
aliasow); nowe grupy powstaja razem z produktami:

| Grupa | Produkty (dzis -> z planow A-E) |
|---|---|
| `elevation` | NMT, NMPT, LAZ PL; DMR 5G/4G CZ (dzis `kartograf download`) -> NMT/NMPT 0,5 m, NMT 100 m, DMP 1G, DMP OK, LAZ CZ |
| `imagery` | ortofotomapa PL (dzis `download --product orto`) -> true orto, orto ukosna, obrazy intensywnosci, ortofoto CZ |
| `landcover` | BDOT10k, CORINE -> archiwum BDOT10k (`--year`), ZABAGED |
| `soil` | SoilGrids i HSG (dzis `landcover --source soilgrids`, `soilgrids hsg`) |
| `boundaries` | PRG, RUIAN |
| `cadastre` | EGiB, katastralni mapa CZ |
| `models3d` | modele 3D budynkow LoD1/LoD2, drzewa, mesh 3D |
| `names` | PRNG, Geonames |
| `maps` | wizualizacje BDOT10k, ZTM |

Mniejsze zbiory (osnowy, quasi-geoidy, siec HY-NET) dostaja grupe przy
wejsciu do planu. Biblioteka bez zmian ksztaltu (CLI tlumaczy na
`download_data`, menedzery i kalkulatory, ADR-037).

## 7. Uklad `data/` (nowe segmenty)

```
nmt/pl_1992_0.5m_evrf2007/...            # K2
nmpt/pl_1992_0.5m_evrf2007/...
intensity/pl_<uklad>/...                 # arkusze OI
orto/pl_1992_true/bbox/<wsp>.tif         # wariant orto (regula 5)
orto/pl_1992/bbox/<wsp>.tif              # wycinek WCS w magazynie
models3d/pl_buildings_lod1_<rok>/teryt/<T>.zip
boundaries/pl_prg_units/bbox/<wsp>.gpkg  # wynik feature_bbox jako GPKG
cadastre/pl_egib/teryt/<T>.gpkg
landcover/pl_bdot10k_<format>_<rok>/teryt/<T>...   # archiwum (9.3)
nmpt/cz_dmpok_bpv/CTES/96/CTES96.tif
laz/cz_dmr5g_bpv/CTES/96/CTES96.laz
landcover/cz_zabaged_gpkg/bbox/<wsp>.gpkg
```

Wynik `feature_bbox` zawsze jako jeden GPKG w ukladzie natywnym zrodla,
skladany lokalnie (jak BDOT10k - SQLite nie na udziale sieciowym).

## 8. Testy i weryfikacja

- Offline: fixtury z prawdziwych odpowiedzi (skorowidze WFS z polami
  0,5 m, feedy ATOM CUZK, odpowiedzi GetFeatureInfo z linkami, WFS CUZK
  z kolejnoscia osi) - `tests/fixtures/<kraj>/...`; zakaz sieci jak dzis.
- Testy zgodnosci CLI = API dla kazdego nowego toru.
- Na zywo (`-m live`, swiadomie): po jednym scenariuszu na produkt,
  porownanie z `probki.md` (sha256 tam, gdzie zrodlo jest niezmienne).
- E2E per plan do `<katalog-danych>/kartograf/e2e/<data>-<plan>/`
  z raportem w `docs/research/`.

## 9. Decyzje do podjecia przez uzytkownika

1. **Kolejnosc planow** (rewizja 2026-10-13 po decyzjach 9.2-9.7):
   0.8.0 grupy CLI -> A `elevation` PL -> B `elevation` CZ -> C dane
   jednostkowe/obszarowe PL + silniki -> D CZ obszarowe i obrazy -> E.
   Zmiana wzgledem pierwszej wersji: plan "B - silniki" usuniety jako
   osobny etap (silniki w C z pierwszymi produktami), wysokosci CZ
   przesuniete z D do B (ta sama grupa i rejestr co A, istniejacy tor
   CZ), POLSA usunieta, archiwum BDOT10k jako `--year` w C. Alternatywa:
   C przed B, jesli dane referencyjne PL sa pilniejsze niz NMPT CZ.
   Do potwierdzenia przez uzytkownika.
2. ~~**Nazwy w CLI**~~ - rozstrzygniete 2026-10-13: grupy wg typu danych
   (6.1), LAZ w `elevation`, `models3d`, przebudowa istniejacych komend
   w 0.8.0.
3. ~~**BDOT10k archiwalny**~~ - rozstrzygniete 2026-10-13
   (`bdot10k-archiwum.md`): `landcover download --source bdot10k --year R`,
   format zrodlowy (`--format GML|SHP` - archiwum nie ma GPKG, sprawdzone
   dla 4 powiatow i lat 2014-2025), rok w segmencie
   (`landcover/pl_bdot10k_<format>_<rok>/`), bo GUGiK publikuje jedna
   paczke na rocznik (stan z poczatku roku); identyczne roczniki =
   `relabeled` (D23); sygnal `none`; zmiany TERYT od roku R - tylko opis
   w dokumentacji.
4. ~~**Ortofoto CZ**~~ - rozstrzygniete 2026-10-13: zapis jak w zrodle
   (JPEG + JGW), bez konwersji.
5. ~~**Prog "pelnego pokrycia"**~~ - rozstrzygniete 2026-10-13: bez
   progu; raport sprawdza komplet arkuszy `TAK` wg skorowidza wzgledem
   ladu PL (K4, `pokrycie.md`). `--measure` odrzucone - uzytkownikowi
   chodzi o komplet pelnych arkuszy danych wysokosciowych, ktory wynika
   ze skorowidza.
6. ~~**POLSA LandCover**~~ - pominiete na razie (K10).
7. ~~**Pliki krajowe**~~ - udostepniamy przez `--whole-country` (K7).
