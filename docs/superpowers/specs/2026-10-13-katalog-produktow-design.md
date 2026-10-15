# Spec: Katalog produktow GUGiK i CUZK oraz raport dostepnosci (podprojekt 3 roadmapy v1.0.0)

**Data:** 2026-10-13
**Status:** ZAAKCEPTOWANY przez uzytkownika 2026-10-13 (decyzje 9.1-9.7
rozstrzygniete); rewizja 2026-10-15 (wersja docelowa, sekcje 3, 4, 6 i 7
doprecyzowane pomiarami planow A/B); plany A-E realizowane przed wydaniem
0.8.0
**Wersja docelowa:** 0.8.0 (wszystkie plany A-E w jednym wydaniu; decyzja
uzytkownika 2026-10-15)
**Warunek wstepny:** grupy komend CLI (ADR-039) scalone do `develop`;
magazyn wersjonowany ADR-036, CLI = API ADR-037 i jawny tryb wycinka
ADR-038 sa juz w 0.8.0-dev; manifest projektu (ADR-040) w tym samym wydaniu
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
| K2 | Etykieta rozdzielczosci w CLI i segmencie: `0.5m`, `1m`, `5m` (i kazda inna z rejestru: `0.15m`, `0.6m`, `10m`, CZ `2m`; kropka dozwolona w segmencie `[a-z0-9.-]`, regula 8 ARCHITECTURE 3.3); API przyjmuje te same napisy | `50cm` (dwie jednostki w jednym parametrze); `0_5m` |
| K3 | Raport dostepnosci jako funkcja biblioteki `check_availability(...) -> AvailabilityReport` + podkomenda grupy CLI `kartograf <grupa> availability` (np. `kartograf elevation availability`; ADR-037: decyzje w bibliotece, CLI drukuje) | flaga `--dry-run` w `download` (miesza dwa wyniki w jednym typie); rozszerzenie `--check-updates` (ten porownuje z magazynem, nie z obszarem) |
| K4 | Raport odpowiada na pytanie "czy dla obszaru jest komplet PELNYCH arkuszy danej kombinacji" (rok x uklad poziomy x rozdzielczosc x uklad wysokosci) wylacznie ze skorowidza: kombinacja jest kompletna, gdy suma poligonow jej arkuszy z `czy_ark_wypelniony = TAK` pokrywa obszar przeciety z ladem PL (maska PRG, jak wycinki ADR-035). Arkusze `NIE` i brakujace arkusze sa wypisane z godlami; zadnych pobran ani pomiaru tresci. Podstawa: pomiar `pokrycie.md` (arkusze TAK = 100% danych na ladzie, poligony TAK stykaja sie bez szczelin; "pelny" = w granicach PL) | procent pikseli z pomiaru tresci i opcja `--measure` (pobieranie w raporcie, wbrew "bez pobierania"); prog 99,9%; obszar bez maski ladu (bbox przy brzegu nigdy kompletny) |
| K5 | Nowe kanaly jako generyczne silniki sterowane deskryptorem (`AccessChannel.endpoint` + nowe pole `params`): `index_files` (skorowidz WMS/WFS -> plik), `unit_package` (paczka per jednostka administracyjna: URL z szablonu albo z `GetFeatureInfo`), `wcs_bbox`, `feature_bbox` (WFS / OGC API Features / ArcGIS query z paginacja), `atom_files` (CUZK: szablon URL arkusz/kafel/KU/obec/kraj), `arcgis_image` (istniejacy) | provider per produkt (dzis wzorzec `providers/pl/*.py`) |
| K6 | Kazdy nowy produkt od razu w magazynie wersjonowanym (ADR-036), z sidecarem i sygnalem swiezosci kanalu: skorowidz `index` (akt_data/nr_zglosz), CUZK `http` (ETag/Last-Modified - openzu je podaje), ATOM `<updated>` jako `metadata`, WFS/OGC API bez sygnalu = `none` | wyjatki od magazynu dla danych wektorowych |
| K7 | Dane krajowe w jednym pliku (ZABAGED 5,8 GB, Data50, HY-NET, PRG kraj) domyslnie przez kanal obszarowy (`feature_bbox`); plik krajowy na jawne zadanie `--whole-country` z ostrzezeniem o rozmiarze (z `HEAD`) - decyzja uzytkownika 2026-10-13: udostepniamy | domyslne pobieranie calego kraju dla malego bboxa; brak opcji krajowej |
| K8 | Wybor wariantu pozostaje jawny (zasada "bez wartosci domyslnych wplywajacych na dane", 0.8.0): `--resolution` wymagane tam, gdzie produkt ma >1 rozdzielczosc; raport dostepnosci podpowiada wartosci | automatyczny wybor "najlepszej" rozdzielczosci |
| K9 | Pobieranie bez `Range` po stronie GUGiK `opendata` (zmierzone): ortofotomapa 5 cm = 1,1 GB/arkusz; wycinek orto wylacznie przez WCS (`orto` + `--cutout`), arkusze orto z ostrzezeniem o rozmiarze z `HEAD Content-Length` przed pobraniem | czesciowe pobieranie arkusza (serwer nie wspiera) |
| K10 | Produkty spoza GUGiK hostowane na geoportalu (POLSA LandCover) - pominiete na razie (decyzja uzytkownika 2026-10-13); powrot dopiero z potwierdzona licencja | traktowanie jako produkt GUGiK |

## 3. Rejestr wariantow i siatki NMT/NMPT (plan A)

Rewizja 2026-10-15 (plany A/B): sekcje 3 i 4 doprecyzowane pelna
inwentaryzacja skorowidzy WFS i sondami uslug
(`docs/research/2026-10-15-plan-a-b/raport.md`); plany:
`docs/superpowers/plans/2026-10-15-plan-a-elevation-pl.md`,
`docs/superpowers/plans/2026-10-15-plan-b-elevation-cz.md`.

### 3.1 Model

`ProductVariant` w `kartograf/sources/variants.py` (dane, zero IO):

```python
@dataclass(frozen=True)
class ProductVariant:
    source: str                   # klucz deskryptora = sidecar `dataset`
    product: str                  # "nmt" | "nmpt" | "laz"
    country: str                  # "PL" | "CZ"
    resolution_m: Decimal | None  # None: LAZ
    vertical_crs: str             # "EVRF2007" | "KRON86" | "Bpv"
    format: str                   # "ASC" | "TIFF" | "LAZ"
    systems: tuple[str, ...]      # PL: ("1992", "2000"); CZ: ("sm5",) | ("tm33",)
    channel: TransportKind
    index_ref: IndexRef | None    # PL: skorowidz WFS (usluga + prefiks warstw rocznych)
    model: str | None             # CZ: "dmr5g" | "dmr4g" | "dmp1g" | "dmpok" (plan B)
    # label (wlasciwosc): "0.15m" | "0.5m" | "0.6m" | "1m" | "2m" | "5m" | "10m"
```

Rejestr wypelnia sie z deskryptorow (`SourceDescriptor.variants`; jeden
deskryptor na produkt i rozdzielczosc). `download/options.py` buduje
z niego dopuszczalne wartosci, `--help` i komunikaty `Error:`;
`FileStorage` - segment `nmt/pl_<uklad>_<label>_<vcrs>`; providery -
filtr rekordow skorowidza (rozdzielczosc z `char_przestrz`, format,
uklad) i kanal (CZ).

### 3.2 Zakres

- PL: arkusze NMT i NMPT we WSZYSTKICH rozdzielczosciach publikowanych
  przez GUGiK jako siatka `ARC/INFO ASCII GRID` (inwentaryzacja WFS
  2026-10-15): NMT EVRF2007 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; NMT KRON86
  0.5m, 1m; NMPT EVRF2007 0.5m, 0.6m, 1m; NMPT KRON86 0.5m, 1m. Istniejace
  1 m i 5 m bez zmiany zachowania; regula "NMT 5 m tylko EVRF2007" zostaje
  prawda, ale jako dane rejestru (siatki 5 m KRON86 nie istnieja).
- Formaty archiwalne skorowidzy (`ASCII XYZ GRID`, `ASCII NMT`,
  `ASCII TBD`, `ESRI TIN`, `Intergraph TTN/GRD`, warstwice DXF/DGN; lata
  2000-2020, jedyne zrodlo 15-50 m, czesc w arkuszach 1:25000) nie sa
  pobierane; raport dostepnosci podaje je jako informacje. Pobieranie
  archiwow - osobna decyzja uzytkownika (poza 0.8.0, jesli nie zdecyduje
  inaczej). NMT 100 m z ATOM - plan E.
- Rekordy arkuszy NMT/NMPT pobierane ze skorowidza WFS (nadzbior WMS dla
  siatek, jedyne zrodlo 10 m) - ten sam indeks dla pobierania i raportu;
  format i rozdzielczosc to twardy filtr rekordu (ADR-028), bo ten sam
  arkusz i zgloszenie bywa opublikowany w dwoch formatach.
- Wycinek WCS (`--cutout`) pozostaje 1 m jako decyzja produktowa:
  WCS GUGiK daje kompozycje lotow, nie wybor arkusza 0,5 m wg roku
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
- `--product nmpt` wymaga `--resolution` (0.5m, 0.6m, 1m) - zmiana lamiaca
  z "Co zrobic".
- Zadne miejsce w kodzie poza rejestrem nie utrzymuje drugiej listy
  wariantow rozdzielczosci; parametry siatki 1 m WCS moga pozostac
  stalymi silnika. Test zgodnosci rejestr <-> `--help` <-> walidacja CLI i API.
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
    sheet: str | None = None, bbox: BBox | None = None,
    geometry: str | Path | None = None, layer: str | None = None,
    year: int | None = None, min_year: int | None = None, max_year: int | None = None,
    cache: bool | MetadataCache = True, force: bool = False,
    on_notice: Callable[[Notice], None] | None = None,
) -> AvailabilityReport
```

`AvailabilityReport`: `request`, `checked_at`, `areas` (per kraj: uklad,
obwiednia, powierzchnia obszaru i ladu - PL: przeciecie z ladem PRG),
`combinations`, `notices`, `ok`, `schema = "kartograf-availability/1"`;
`to_json()`.

`AvailabilityCombination`: `country`, `product`, `source` (klucz
deskryptora), `year` (PL: rok warstwy skorowidza; CZ: brak),
`acquisition_dates` (min-max `akt_data`), `published` (PL: min-max
`dt_pzgik`; CZ: `Last-Modified` plikow), `campaigns` (`nr_zglosz`),
`horizontal` (`PL-1992`/`PL-2000`; CZ `S-JTSK`/`ETRS89-TM33`), `resolution`
(etykieta K2; LAZ brak), `vertical_crs`, `format`, `densities` (LAZ PL),
`complete` (K4), `sheets_full` (godla `TAK`; CZ: arkusze z plikiem),
`sheets_partial` (godla wylacznie `NIE`), `sheets_missing` (CZ: arkusze
indeksu bez pliku), `uncovered` i `uncovered_m2` (czesc obszaru bez
zadnego arkusza kombinacji), `size_bytes` (CZ), `download_hint` (gotowe
komendy `elevation download ...` BEZ `--output` - do wklejenia po
`kartograf ` albo po `kartograf project add NAZWA `).

Kompletnosc liczona rasteryzacja na siatce 1 m obszaru (srodki pikseli,
pasy wierszy), jak pomiar w `pokrycie.md`.

### 4.2 CLI

```
kartograf elevation availability --product nmt --country pl --bbox 566000,243000,569000,246000
```

Tabela posortowana: rok malejaco; kolumna "komplet pelnych" (`tak` /
`nie: 2 niepelne, brak arkuszy dla 0,88 ha`); `--details`
wypisuje godla arkuszy niepelnych i kombinacje bez pokrycia; stopka
z `download_hint` dla najnowszej kompletnej kombinacji w dwoch postaciach:
`kartograf <hint>` (z dopiskiem "dodaj --output KATALOG") i
`kartograf project add NAZWA <hint>`. `--json` wypisuje
strukture `AvailabilityReport` (ten sam ksztalt co API). Kod wyjscia 0
takze przy braku danych (to raport), 1 przy bledzie zrodla. Komenda nie
jest komenda danych manifestu projektu (bez `_task`, ADR-040).

### 4.3 Zrodla danych raportu

- PL NMT/NMPT/LAZ: skorowidze WFS (`NumerycznyModelTerenu{EVRF2007,KRON86}`,
  `NumerycznyModelPokryciaTerenu*`, `DanePomiaroweLidar*`) - pola `godlo`,
  `akt_rok`, `akt_data`, `dt_pzgik`, `char_przestrz`, `uklad_xy`, `uklad_h`,
  `format`, `nr_zglosz`, `czy_ark_wypelniony`, geometria arkusza; jedno
  zapytanie `GetFeature` z `TYPENAMES` wszystkich warstw rocznych, BBOX N,E,
  paginacja (`next`), filtry po stronie klienta (serwer ignoruje `FILTER`),
  wynik w cache metadanych (ADR-037); maska ladu:
  `providers/pl/prg.py::fetch_land_mask`. Rekordy archiwalne - tylko
  `Info:`.
- CZ (plan B): DMR/DMP nie maja lotow ani flagi pelnosci - raport podaje
  dostepne produkty i arkusze dla obszaru (indeks `KladyMapovychListu`,
  `PODIL`/`IN_CZ`) oraz date publikacji i rozmiar z `HEAD` pliku
  (`Last-Modified`, `Content-Length`; `<updated>` ATOM jest ta sama data,
  a feed ma 24-31 MB - nieuzywany).

### 4.4 Kryteria akceptacji

- Krakow (bbox E 565000-569000, N 242000-246000; pomiar 2026-10-15):
  NMT EVRF2007 PL-1992 1m 2025, 2024, 2023, 2022, 2019 kompletne (po 6
  `TAK`); PL-2000 1m 2023 i 2021 kompletne (po 15 `TAK`); 5m 2019
  kompletna; rocznik 2018 ma wylacznie archiwa (XYZ 1 m i 5 m, TBD 25 m) -
  `Info:`, nie kombinacja; test offline z fixtur prawdziwych odpowiedzi WFS.
- Pomorze (E 339000-343000, N 744800-747000; lad 863 767 m2): NMT 2025
  0,5 m - niekompletna, 4 arkusze niepelne z godlami (`N-33-58-A-c-1-3`,
  `-1-4`, `-2-3`, `-3-1`; skorowidz pokrywa caly lad, wszystkie `NIE`);
  2022 1 m - niekompletna wylacznie przez brak arkusza dla 8 782 m2 ladu
  (ok. 0,9 ha), 3 arkusze `TAK`; morze nie wplywa na wynik.
- Brak pobran plikow danych (test: atrapa transportu odrzuca kazdy URL
  `opendata`).
- Zgodnosc CLI `--json` = API (bajtowo przy zamrozonym zegarze).

## 5. Silniki kanalow (wchodza razem z pierwszym produktem, ktory ich uzywa)

| Silnik (`TransportKind`) | Wejscie z deskryptora | Produkty |
|---|---|---|
| `WMS_SHEET_INDEX` / `WFS` (istnieja) | skorowidz, pola rekordu | NMT/NMPT (od planu A z WFS), OI, orto ukosna, mesh 3D |
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

**Errata 1 (2026-10-15, rekonesans planow C/D, ADR-042 D1/D4):**
(1) EPSG:5514 ma osie X = wschod, Y = polnoc (pyproj `axis_info`), wiec
kolejnosc X,Y w BBOX uslug CUZK jest ZGODNA z EPSG, a nie wyjatkiem
("X,Y mimo osi EPSG:5514" wyzej jest bledne); GUGiK
`urn:ogc:def:crs:EPSG::2180` = N,E - tez wg EPSG. Zamiana osi daje pusty
wynik BEZ bledu, dlatego kolejnosc jest parametrem kanalu
(`FeatureBBoxParams.axis_order`: `yx` GUGiK, `xy` CUZK) z testem na
prawdziwej odpowiedzi (ADR-042 D4; pomiary:
`docs/research/2026-10-15-plan-c-d/raport.md`). (2) Szablon URL paczki
jednostki ma tylko tokeny `{teryt}` i `{woj}`; rok, format i LoD sa
wartosciami wariantu (`PackageVariant.choice`, ADR-042 D1), a nie tokenem
`{rok}` z tabeli wyzej.

## 6. Produkty - fale (plany A-E, rewizja kolejnosci 2026-10-13)

Plany A-E wchodza razem do 0.8.0; kazdy rozszerza jedna grupe CLI (6.1).
Kolejnosc wynika z priorytetow raportu (W/S/N) i zaleznosci: plany A i B rozszerzaja
istniejace tory (skorowidz GUGiK, arkusze CZ z `openzu`, `exportImage`)
i nie potrzebuja nowych silnikow; silniki `unit_package` i `feature_bbox`
(sekcja 5) powstaja w planie C razem z pierwszymi produktami - silnik bez
produktu nie ma czym byc zweryfikowany na zywo.

**Plan A - `elevation` PL (W), 0.8.0:** rejestr wariantow (K1-K2),
siatki NMT i NMPT we wszystkich rozdzielczosciach GUGiK (sekcja 3),
rekordy ze skorowidza WFS, `kartograf elevation availability` dla PL
(sekcja 4, K4: komplet pelnych arkuszy wg skorowidza, maska ladu PRG).

**Plan B - `elevation` CZ (W/S):** `cz.cuzk.dmpok` (TIFF 0,5 m arkusze
SM5/TM33 + wycinek ImageServer `dmp_obrazova_korelace`), `cz.cuzk.dmp1g`
(kafel TM33 i wycinek z ImageServer), kafle TM33 DMR 4G z plikow ETRS89
(wysokosci EVRF2007 natywnie, zamiast warpu), LAZ CZ (DMR 5G/4G, DMP 1G/OK;
`elevation download --product laz --country cz --model ...`; S-JTSK = Bpv,
ETRS89-TM33 = EVRF2007, bez transformacji chmur), raport dostepnosci CZ
i `--country auto`. Wszystko na istniejacym torze arkuszy CZ
(`download/cz_sheets.py`, indeks `KladyMapovychListu`, szablon `openzu`)
i rejestrze wariantow z planu A. Zaleznosc tylko od A.

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
nmt/pl_1992_0.5m_evrf2007/...            # K2 (takze 0.15m, 0.6m, 10m)
nmpt/pl_1992_0.5m_evrf2007/...
intensity/pl_<uklad>/...                 # arkusze OI
orto/pl_1992_true/bbox/<wsp>.tif         # wariant orto (regula 5)
orto/pl_1992/bbox/<wsp>.tif              # wycinek WCS w magazynie
models3d/pl_buildings_lod1_<rok>/teryt/<T>.zip
boundaries/pl_prg_units/bbox/<wsp>.gpkg  # wynik feature_bbox jako GPKG
cadastre/pl_egib/teryt/<T>.gpkg
landcover/pl_bdot10k_<format>_<rok>/teryt/<T>...   # archiwum (9.3)
nmpt/cz_dmpok_bpv/CTES/96/CTES96.tif
nmpt/cz_dmpok_evrf2007/760/5518/760_5518.tif       # plik ETRS89-TM33 natywnie
nmpt/cz_dmp1g_bpv/302/5550/302_5550.tif
laz/cz_dmr5g_bpv/CTES/96/CTES96.laz                # laz/cz_<model>_<vcrs>
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

## 9. Decyzje (rozstrzygniete 2026-10-13)

1. ~~**Kolejnosc planow**~~ - zaakceptowana 2026-10-13: 0.8.0 grupy CLI
   -> A `elevation` PL -> B `elevation` CZ -> C dane jednostkowe/obszarowe
   PL + silniki -> D CZ obszarowe i obrazy -> E. Zmiana wzgledem pierwszej
   wersji: plan "B - silniki" usuniety jako osobny etap (silniki w C
   z pierwszymi produktami), wysokosci CZ przesuniete z D do B (ta sama
   grupa i rejestr co A, istniejacy tor CZ), POLSA usunieta, archiwum
   BDOT10k jako `--year` w C.
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
